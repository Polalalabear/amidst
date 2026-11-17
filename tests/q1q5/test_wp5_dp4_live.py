"""DP4 runner wiring: fake providers only; no network, no environment key access."""

import importlib
import json

import pytest

from amidst.agent_eval import wp5, wp5_fake, wp5_runner as runner
from amidst.q1q5 import api_budget as ab, attention_ranking as ar

ad = importlib.import_module("amidst.q1q5.agent_decision")


class Provider:
    last_error = None

    def __init__(self, method, seen, invalid=False):
        self.method, self.seen, self.invalid = method, seen, invalid

    def call(self, payload, *, timeout_ms, max_output_tokens):
        self.seen.append((payload, timeout_ms, max_output_tokens))
        req = payload["request"] if self.method == "AGENT" else payload
        ranking = ar.rank_attention(req)["ranking"]
        if self.invalid:
            response = {"ranking": []}
        elif self.method == "AGENT" and payload["step"] == 1:
            response = {
                "action": "TOOL",
                "tool": "get_graph_neighbors",
                "args": {"camera_id": "CAM_B"},
            }
        elif self.method == "AGENT":
            assert payload["tool_results"]
            response = {"action": "FINAL", "ranking": ranking}
        else:
            response = {"ranking": ranking}
        return ad.Attempt("OK", 2.0, response, 42, 11)


def guard(tmp_path, *, enabled=True, calls=1000):
    return ab.ApiGuard(
        ab.GuardConfig(
            enabled=enabled,
            max_usd_total=10,
            max_calls_per_min=1000,
            max_calls_per_day=calls,
            prices=wp5.load_json(wp5.load_config()["price_table_path"])["models"],
        ),
        usage_dir=tmp_path,
    )


def setup_run(tmp_path, monkeypatch, model, method="API", invalid=False):
    seen = []
    monkeypatch.setattr(
        runner, "make_dp4_provider", lambda cfg, m, method: Provider(method, seen, invalid)
    )
    g = guard(tmp_path / "ledger")
    monkeypatch.setattr(runner, "make_api_guard", lambda *a, **kw: g)
    q = tmp_path / "questions.jsonl"
    q.write_text("".join(json.dumps(r) + "\n" for r in wp5_fake.synthetic_rows(4)))
    arm = "mac" if model == "terra6.1" else "colab_l4"
    args = [
        "--set",
        "pilot",
        "--live",
        "--arm",
        arm,
        "--models",
        model,
        "--skip-types",
        "DP1,DP3,NL",
        "--dp4-method",
        method,
        "--questions",
        str(q),
        "--out",
        str(tmp_path / "out"),
    ]
    if arm == "mac":
        args += ["--approved-usd", "10"]
    return args, seen, g


@pytest.mark.parametrize("model", ["terra6.1", "qwen2.5:7b-instruct-q4_K_M"])
@pytest.mark.parametrize("method", ["API", "AGENT"])
def test_live_fake_provider_writes_dp4_calls_summary_and_usage(
    tmp_path, monkeypatch, model, method
):
    args, seen, g = setup_run(tmp_path, monkeypatch, model, method)
    assert runner.main(args) == 0
    rows = [json.loads(s) for s in (tmp_path / "out/calls.jsonl").read_text().splitlines()]
    steps = 1 if method == "API" else 2
    assert len(rows) == 24 and len(seen) == 24 * steps
    assert all(r["decision_source"] == method and r["steps"] == steps for r in rows)
    assert all(
        r["prompt_tokens"] == 42 * steps and r["completion_tokens"] == 11 * steps for r in rows
    )
    assert all(len(r["dp4_attempts"]) == steps for r in rows)
    assert all(len(a["prompt_sha256"]) == 64 for r in rows for a in r["dp4_attempts"])
    summary = json.loads((tmp_path / "out/summary.json").read_text())
    assert summary["cells"][0]["format_error_fallback"]["rate"] == 0
    assert (tmp_path / "out/summary.md").is_file()
    if model == "terra6.1":
        assert len(g.ledger_path.read_text().splitlines()) == len(seen)
    else:
        assert not g.ledger_path.exists()


def test_closed_api_guard_blocks_every_dp4_provider_call(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(runner, "make_dp4_provider", lambda cfg, m, method: Provider(method, seen))
    cfg = wp5.load_config()
    g = guard(tmp_path, enabled=False)
    ctx = runner.live_context(cfg, wp5.load_json(cfg["price_table_path"]), g)
    ranker = ctx.dp4_ranker(wp5.model_by_id(cfg, "terra6.1"), cfg["timeout_profiles"]["formal"])
    resp = ranker.rank(wp5_fake.dp4_request(0))
    assert resp["method"] == "RULE" and not seen
    assert json.loads(g.ledger_path.read_text().splitlines()[0])["reason"] == "API_DISABLED"


def test_agent_guards_each_tool_round_and_keeps_billed_usage(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(runner, "make_dp4_provider", lambda cfg, m, method: Provider(method, seen))
    cfg = wp5.load_config()
    g = guard(tmp_path, calls=1)
    ctx = runner.live_context(cfg, wp5.load_json(cfg["price_table_path"]), g, dp4_method="AGENT")
    ranker = ctx.dp4_ranker(wp5.model_by_id(cfg, "terra6.1"), cfg["timeout_profiles"]["formal"])
    resp = ranker.rank(wp5_fake.dp4_request(0))
    assert resp["method"] == "RULE" and len(seen) == 1
    assert ranker.last_usage == {"prompt_tokens": 42, "completion_tokens": 11}
    rows = [json.loads(s) for s in g.ledger_path.read_text().splitlines()]
    assert len(rows) == 2 and rows[-1]["outcome"] == "DENIED"


def test_bad_dp4_response_is_counted_as_format_error(tmp_path, monkeypatch):
    args, seen, g = setup_run(tmp_path, monkeypatch, "terra6.1", invalid=True)
    assert runner.main(args) == 0  # preserve WP5's format-error summary policy
    summary = json.loads((tmp_path / "out/summary.json").read_text())
    assert summary["cells"][0]["format_error_fallback"]["rate"] == 1


def test_dp4_dry_run_keeps_config_counts_and_records_serialized_token_estimate(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        runner, "make_dp4_provider", lambda *a: pytest.fail("dry-run constructed provider")
    )
    assert (
        runner.main(
            [
                "--set",
                "pilot",
                "--models",
                "terra6.1",
                "--skip-types",
                "DP1,DP3,NL",
                "--out",
                str(tmp_path),
            ]
        )
        == 0
    )
    estimate = json.loads((tmp_path / "estimate.json").read_text())
    cfg = wp5.load_config()
    row = estimate["estimate"]["models"][0]
    assert estimate["provider_calls"] == 0 and row["model_calls_nominal"] == 24
    assert row["model_calls_worst"] == 120 and row["prompt_tokens_nominal"] == 24 * 2500
    assert estimate["dp4_input_estimate"]["configured_prompt_tokens_per_call"] == 2500
    assert estimate["dp4_input_estimate"]["first_call_tokens_heuristic"]["max"] > 0


@pytest.mark.parametrize("kind", ["OPENAI", "LOCAL"])
def test_dp4_transport_payload_uses_ranking_schema_and_correct_endpoint(kind):
    cfg = wp5.load_config()
    model = wp5.model_by_id(cfg, "terra6.1" if kind == "OPENAI" else "qwen2.5:7b-instruct-q4_K_M")
    provider = runner.make_dp4_provider(cfg, model, "API")
    sent = []
    request = wp5_fake.dp4_request(0)
    response = {"ranking": ar.rank_attention(request)["ranking"]}

    def transport(**kwargs):
        body = json.loads(kwargs["body"])
        sent.append((kwargs["url"], body))
        data = (
            {
                "choices": [{"message": {"content": json.dumps(response)}}],
                "usage": {"prompt_tokens": 123, "completion_tokens": 17},
            }
            if kind == "OPENAI"
            else {
                "message": {"content": json.dumps(response)},
                "prompt_eval_count": 123,
                "eval_count": 17,
            }
        )
        return 200, json.dumps(data).encode(), 2.0

    provider.base._transport = transport
    if kind == "OPENAI":
        provider.base._read_api_key_now = lambda: "synthetic-test-value"  # no environment read
    attempt = provider.call(request, timeout_ms=5000, max_output_tokens=300)
    assert (
        attempt.response == response
        and attempt.prompt_tokens == 123
        and attempt.completion_tokens == 17
    )
    url, body = sent[0]
    assert body["model"] == ("gpt-6.1-terra" if kind == "OPENAI" else model["id"])
    assert (
        "ranking"
        in (
            body["response_format"]["json_schema"]["schema"] if kind == "OPENAI" else body["format"]
        )["properties"]
    )
    assert url == (
        "https://api.openai.com/v1/chat/completions"
        if kind == "OPENAI"
        else "http://127.0.0.1:11434/api/chat"
    )


def test_dp4_forbidden_input_fails_before_key_or_transport():
    cfg = wp5.load_config()
    provider = runner.make_dp4_provider(cfg, wp5.model_by_id(cfg, "terra6.1"), "API")
    provider.base._read_api_key_now = lambda: pytest.fail("read key")
    provider.base._transport = lambda **kw: pytest.fail("transport")
    bad = wp5_fake.dp4_request(0)
    bad["truth"] = 1
    with pytest.raises(ar.AttentionInputError):
        provider.call(bad, timeout_ms=5000, max_output_tokens=300)


def test_agent_respects_total_profile_time_and_five_step_cap(tmp_path, monkeypatch):
    seen = []

    class ToolProvider(Provider):
        def call(self, payload, *, timeout_ms, max_output_tokens):
            self.seen.append(timeout_ms)
            return ad.Attempt(
                "OK",
                2.0,
                {"action": "TOOL", "tool": "get_graph_neighbors", "args": {"camera_id": "CAM_B"}},
                42,
                11,
            )

    monkeypatch.setattr(
        runner, "make_dp4_provider", lambda cfg, m, method: ToolProvider(method, seen)
    )
    cfg = wp5.load_config()
    table = wp5.load_json(cfg["price_table_path"])
    ctx = runner.live_context(cfg, table, None, dp4_method="AGENT")
    model = wp5.model_by_id(cfg, "qwen2.5:7b-instruct-q4_K_M")
    r = ctx.dp4_ranker(model, dict(cfg["timeout_profiles"]["formal"], per_step_ms=4))
    result = r.rank(wp5_fake.dp4_request(0))
    assert len(seen) == 2 and result["fallback_reason"] == "TIME_BUDGET" and result["steps"] == 2
    seen.clear()
    r = ctx.dp4_ranker(model, cfg["timeout_profiles"]["formal"])
    assert r.rank(wp5_fake.dp4_request(0))["fallback_reason"] == "ROUND_LIMIT" and len(seen) == 5


def test_dp4_openai_requires_guard_before_constructing_provider(monkeypatch):
    monkeypatch.setattr(
        runner, "make_dp4_provider", lambda *a: pytest.fail("constructed paid provider")
    )
    cfg = wp5.load_config()
    ctx = runner.live_context(cfg, wp5.load_json(cfg["price_table_path"]))
    with pytest.raises(wp5.Wp5Error, match="LIVE_NEEDS_API_GUARD"):
        ctx.dp4_ranker(wp5.model_by_id(cfg, "terra6.1"), cfg["timeout_profiles"]["formal"])


@pytest.mark.parametrize("status,expected", [(400, 0), (429, None)])
def test_dp4_rejection_usage_is_zero_only_when_known_unbilled(
    tmp_path, monkeypatch, status, expected
):
    import urllib.error

    cfg = wp5.load_config()
    model = wp5.model_by_id(cfg, "terra6.1")
    provider = runner.make_dp4_provider(cfg, model, "API")
    provider.base._read_api_key_now = lambda: "synthetic-test-value"

    def transport(**kw):
        raise urllib.error.HTTPError(kw["url"], status, "test", None, None)

    provider.base._transport = transport
    monkeypatch.setattr(runner, "make_dp4_provider", lambda *a: provider)
    g = guard(tmp_path)
    ctx = runner.live_context(cfg, wp5.load_json(cfg["price_table_path"]), g)
    r = ctx.dp4_ranker(model, cfg["timeout_profiles"]["formal"])
    r.rank(wp5_fake.dp4_request(0))
    assert r.last_usage["prompt_tokens"] is expected
    row = json.loads(g.ledger_path.read_text().splitlines()[0])
    assert row["prompt_tokens"] is expected
    assert (row["est_cost_usd"] == 0) if status == 400 else (row["est_cost_usd"] > 0)


def test_dp4_all_provider_unavailable_is_failed_not_a_valid_comparison(tmp_path, monkeypatch):
    args, seen, _ = setup_run(tmp_path, monkeypatch, "terra6.1")

    class Unavailable(Provider):
        def call(self, payload, **kw):
            seen.append(payload)
            return ad.Attempt("UNAVAILABLE", 0.0)

    monkeypatch.setattr(
        runner, "make_dp4_provider", lambda cfg, m, method: Unavailable(method, seen)
    )
    assert runner.main(args) == 3
    summary = json.loads((tmp_path / "out/summary.json").read_text())
    assert summary["status"] == "FAILED" and summary["cells"][0]["provider_unavailable_rate"] == 1

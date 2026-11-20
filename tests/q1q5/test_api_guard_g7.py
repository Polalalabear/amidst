"""G7: every attempted OpenAI dispatch in both formerly unguarded paths is gated.

Only synthetic prices, fake keys and fake transports; sockets are forbidden.
"""

from __future__ import annotations

import contextvars
import json
import socket
from dataclasses import replace

import pytest
from test_agent_run_provider_wp3 import _dp1_request, _load_cli_module
from test_openai_prediction_t import ENV, GOOD, completion, request

from amidst.q1q5.api_budget import ApiGuard, GuardConfig
from amidst.q1q5.openai_prediction import OpenAIPredictionAdapter

IN_GUARD = contextvars.ContextVar("g7_guard_active", default=False)
PRICES = {
    m: {"input_usd_per_mtok": 0.1, "output_usd_per_mtok": 0.2}
    for m in ("test-model", "gpt-6-astra")
}


@pytest.fixture(autouse=True)
def no_network_and_guard_boundary(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("real network is forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    original = ApiGuard.run

    def observed(self, caller, model, prompt, output, invoke):
        def inside():
            token = IN_GUARD.set(True)
            try:
                return invoke()
            finally:
                IN_GUARD.reset(token)

        return original(self, caller, model, prompt, output, inside)

    monkeypatch.setattr(ApiGuard, "run", observed)


def guard_at(root, **changes):
    cfg = GuardConfig(
        enabled=True,
        max_usd_total=1,
        max_tokens_per_call=100000,
        max_calls_per_min=100,
        prices=PRICES,
    )
    return ApiGuard(replace(cfg, **changes), usage_dir=root)


def rows(guard):
    return [json.loads(row) for row in guard.ledger_path.read_text().splitlines()]


def invoke_route(route, tmp_path, guard, *, retry=False, cached=False):
    calls = []

    def transport(**kwargs):
        assert IN_GUARD.get(), "OpenAI dispatch bypassed ApiGuard.run"
        calls.append(kwargs)
        if retry and len(calls) == 1:
            return (503, b"{}") if route == "cli" else b"not json"
        if route == "cli":
            answer = {
                "action": "SELECT",
                "candidate_id": "B1",
                "reason_codes": ["GRAPH_EDGE"],
                "rationale": "ok",
            }
            return 200, json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps(answer)}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 30},
                }
            ).encode()
        result = json.loads(completion(GOOD))
        result["usage"] = {"prompt_tokens": 1000, "completion_tokens": 30}
        return json.dumps(result).encode()

    if route == "prediction":
        adapter = OpenAIPredictionAdapter(
            enabled=True, model="test-model", env=ENV, transport=transport, guard=guard
        )
        result = adapter.predict(session_id="S", query_id="Q", request=request())
        if cached:
            assert (
                adapter.predict(session_id="S", query_id="Q2", request=request())["source"]
                == "CACHE"
            )
        return result, calls, adapter.last_estimate
    cli = _load_cli_module()
    source = tmp_path / "requests.jsonl"
    source.write_text(json.dumps(_dp1_request()) + "\n")
    output = tmp_path / "summary.json"
    rc = cli.main(
        [
            "--live",
            "--requests",
            str(source),
            "--model",
            "astra6",
            "--models",
            "1",
            "--recording",
            str(tmp_path / "record.jsonl"),
            "--out",
            str(output),
        ],
        transport=transport,
        env=ENV,
        api_guard=guard,
    )
    result = json.loads(output.read_text())
    assert rc == (2 if result["status"] in ("REFUSED", "PARTIAL") else 0)
    return result, calls, result["api_guard"][0]["dry_run"]


@pytest.mark.parametrize("route", ["cli", "prediction"])
@pytest.mark.parametrize(
    "config,reason",
    [
        ({"enabled": False}, "API_DISABLED"),
        ({"prices": None}, "PRICE_UNKNOWN"),
        ({"max_usd_total": 0}, "TOTAL_BUDGET"),
        ({"max_tokens_per_call": 1}, "PER_CALL_TOKEN_CAP"),
    ],
)
def test_guard_denial_never_dispatches_and_is_recorded(route, config, reason, tmp_path):
    guard = guard_at(tmp_path / "ledger", **config)
    result, calls, estimate = invoke_route(route, tmp_path, guard)
    assert calls == []
    assert result["reason"] == reason
    assert rows(guard)[-1]["outcome"] == "DENIED"
    assert estimate["calls"] == 1
    assert "OPENAI_API_KEY" not in guard.ledger_path.read_text()


@pytest.mark.parametrize("route", ["cli", "prediction"])
@pytest.mark.parametrize("retry", [False, True])
def test_every_openai_attempt_is_inside_guard_and_charged(route, retry, tmp_path):
    guard = guard_at(tmp_path / "ledger")
    result, calls, estimate = invoke_route(route, tmp_path, guard, retry=retry)
    assert len(calls) == (2 if retry else 1)
    ledger = rows(guard)
    assert len(ledger) == len(calls)
    assert ledger[-1]["prompt_tokens"] == 1000
    assert ledger[-1]["completion_tokens"] == 30
    assert ledger[-1]["est_cost_usd"] == pytest.approx(0.000106)
    assert result["status"] in ("OK", "AVAILABLE")
    assert estimate["price_known"] is True
    assert ledger[0]["est_cost_usd"] > 0
    if route == "prediction":
        assert (
            json.loads(calls[-1]["body"])["max_completion_tokens"] == estimate["avg_output_tokens"]
        )


@pytest.mark.parametrize("route", ["cli", "prediction"])
def test_retry_is_rechecked_and_cannot_bypass_spent_call_cap(route, tmp_path):
    guard = guard_at(tmp_path / "ledger", max_calls_per_day=1)
    result, calls, _ = invoke_route(route, tmp_path, guard, retry=True)
    assert len(calls) == 1
    assert result["reason"] == "DAILY_CALL_CAP"
    assert [r["outcome"] for r in rows(guard)] == ["OK", "DENIED"]


def test_prediction_cache_has_no_new_paid_attempt(tmp_path):
    guard = guard_at(tmp_path / "ledger")
    _, calls, _ = invoke_route("prediction", tmp_path, guard, cached=True)
    assert len(calls) == len(rows(guard)) == 1


def test_default_cli_and_adapter_are_closed_without_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("AMIDST_API_USAGE_DIR", str(tmp_path / "usage"))
    adapter = OpenAIPredictionAdapter(
        enabled=True,
        model="test-model",
        env=ENV,
        transport=lambda **kw: pytest.fail("default adapter must never dispatch"),
    )
    result = adapter.predict(session_id="S", query_id="Q", request=request())
    assert result["reason"] == "API_DISABLED"
    cli = _load_cli_module()
    source = tmp_path / "requests.jsonl"
    source.write_text(json.dumps(_dp1_request()) + "\n")
    assert (
        cli.main(
            ["--live", "--requests", str(source), "--recording", str(tmp_path / "record.jsonl")],
            env=ENV,
            provider=lambda *a, **kw: pytest.fail("default CLI must never call provider"),
        )
        == 2
    )


@pytest.mark.parametrize("outcome", ["missing_usage", "timeout", "connection_error"])
def test_unknown_usage_and_transport_failures_are_charged_at_reserve(tmp_path, outcome):
    guard = guard_at(tmp_path / "ledger")

    def transport(**kwargs):
        assert IN_GUARD.get()
        if outcome == "timeout":
            raise TimeoutError("synthetic timeout")
        if outcome == "connection_error":
            raise ConnectionError("synthetic failure")
        return completion(GOOD)

    adapter = OpenAIPredictionAdapter(
        enabled=True, model="test-model", env=ENV, transport=transport, guard=guard
    )
    result = adapter.predict(session_id="S", query_id="Q", request=request())
    ledger = rows(guard)
    assert len(ledger) == (2 if outcome == "connection_error" else 1)
    assert result["attempts"] == len(ledger)
    assert all(row["prompt_tokens"] is None and row["completion_tokens"] is None for row in ledger)
    assert all(row["est_cost_usd"] > 0 for row in ledger)
    assert all(
        row["outcome"] == ("OK" if outcome == "missing_usage" else "ERROR") for row in ledger
    )


def test_injected_cli_provider_cannot_skip_guard(tmp_path):
    from amidst.q1q5 import agent_decision as ad

    guard = guard_at(tmp_path / "ledger")
    source = tmp_path / "requests.jsonl"
    source.write_text(json.dumps(_dp1_request()) + "\n")
    calls = []

    def provider(*args, **kwargs):
        assert IN_GUARD.get()
        calls.append(1)
        return ad.Attempt(
            ad.CALL_OK,
            1,
            {
                "action": "SELECT",
                "candidate_id": "B1",
                "reason_codes": ["GRAPH_EDGE"],
                "rationale": "synthetic only",
            },
            1000,
            30,
        )

    cli = _load_cli_module()
    assert (
        cli.main(
            ["--live", "--requests", str(source), "--recording", str(tmp_path / "record.jsonl")],
            provider=provider,
            env=ENV,
            api_guard=guard,
        )
        == 0
    )
    assert len(calls) == len(rows(guard)) == 1

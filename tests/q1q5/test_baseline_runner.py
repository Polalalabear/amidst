"""Mechanical control cases, never a formal Q3 dataset or model-quality test."""

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from amidst.q1q5.api import QAPI, raw_json
from amidst.q1q5.ollama_runtime import bind_runs
from amidst.q1q5.q3_rules import parse_rule
from test_api import TOKEN, authorize, q1, q2, run_binding
from test_q5_agent import auto, bindings
from test_q5_controller import repin, seal_parameters, seed_id

from amidst.q1q5.baseline_runner import execute_sample, load_cases, load_plan, verify_composition
from amidst.q1q5.llm_provider import QWEN3_MODEL, FakeProvider
from amidst.q1q5.store import DetectionSnapshot, canonical_hash

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "configs/q1q5/baseline_v1_protocol.json"
PATTERNS = {
    "supported_candidate": None,
    "empty_candidates": {"A": {0: "STRONG", 1: "STRONG"}},
    "temporary_loss_recovery": {
        "A": {0: "STRONG", 1: "STRONG", **dict.fromkeys(range(4, 10), "STRONG")}
    },
    "incomplete_candidate_frames": {
        "A": {0: "STRONG", 1: "STRONG"},
        "B": dict.fromkeys(range(10), "MISSING"),
    },
    "no_seed": {},
}


class ScriptedQwen:
    """Exercise Qwen3's real wire/audit parser with synthetic transport only."""

    def __init__(self, catalog, mode):
        self.catalog, self.mode, self.requests = catalog, mode, []

    def generate(self, **args):
        self.requests.append(deepcopy(args))
        if self.mode in {"timeout", "unavailable"}:
            responses = [TimeoutError() if self.mode == "timeout" else ConnectionError()]
        else:
            if args["template_version"].startswith("q3"):
                text = json.loads(args["prompt"].split("\nUSER_TEXT=")[-1])
                output = parse_rule(
                    text,
                    **{
                        key: self.catalog[key]
                        for key in (
                            "class_aliases",
                            "color_aliases",
                            "camera_aliases",
                            "region_aliases",
                        )
                    },
                ).output
            else:
                payload = json.loads(args["prompt"].split("\n")[-1])
                last = payload["last_tool_result"]
                empty = (
                    last.get("schema_version") == "q-demo.candidate-evidence.v1"
                    and not last.get("entry_observation_id")
                    and not last.get("best_observations")
                )
                output = auto(
                    payload, len(self.requests), "RETURN_TO_ORIGIN" if empty else "SWITCH"
                )
                if output.get("action"):
                    output["rationale"] = {
                        "SWITCH": "Strong observed evidence.",
                        "RETURN_TO_ORIGIN": "Stop without a cut.",
                    }[output["action"]]
            tags = raw_json({"models": [{"name": QWEN3_MODEL, "digest": "a" * 64}]})
            text = "not JSON" if self.mode == "invalid" else json.dumps(output)
            body = raw_json(
                {
                    "model": QWEN3_MODEL,
                    "message": {"role": "assistant", "content": text},
                    "done": True,
                    "done_reason": "stop",
                }
            )
            responses = [tags, body, tags]
        return FakeProvider(responses, clock=lambda: 0).generate(**args)


def fixture_api(mode="scripted", case_id="supported_candidate"):
    scenario = case_id.split(":")[0]
    b = bindings(PATTERNS.get(scenario), session_max_agent_rounds=12)
    rows = deepcopy(list(b.index.records))
    for row in rows:
        if row["frame_state"] == "MISSING":
            row["rgb_file_sha256"] = None
    index = repin(DetectionSnapshot(deepcopy(b.index.manifest), tuple(rows)))
    ps = deepcopy(b.parameter_set)
    ps["applies_to"]["detection_index_ids"] = [index.manifest["index_id"]]
    seal_parameters(ps)
    b = replace(
        b,
        index=index,
        index_sha256=index.manifest["content_sha256"],
        parameter_set=ps,
        parameter_sha256=ps["content_sha256"],
    )
    run = run_binding(b=b)
    b = run.bindings
    provider = ScriptedQwen(run.catalog, mode)

    def template(name, version):
        text = (ROOT / "configs/q1q5/prompts" / name).read_text()
        return {
            "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "version": version,
        }

    config = {
        "schema_version": "q-demo.ollama-runtime.v1",
        "applies_to": {
            "scene_id": run.catalog["scene_id"],
            "scene_revision": run.catalog["scene_revision"],
            "run_id": b.clock.run_id,
            "detection_index_sha256": b.index_sha256,
            "parameter_set_sha256": b.parameter_sha256,
            "clock_mapping_sha256": b.clock_sha256,
        },
        "base_url": "http://127.0.0.1:11437",
        "model": QWEN3_MODEL,
        "model_digest": "a" * 64,
        "options": {"temperature": 0, "seed": 7},
        "enable_q3": True,
        "enable_q5": True,
        "q3_template": template("q3_parse_v2.txt", "q3-parse.v2"),
        "q5_template": template("q5_agent_v2.txt", "q5-agent-v2"),
        "agent_authorization_ref": "SYNTHETIC_G3_TEST_ONLY",
    }
    config["content_sha256"] = canonical_hash(config)
    run = bind_runs(
        [run],
        config,
        provider_factory=lambda url: provider,
        scheduler_factory=lambda: lambda *values: None,
    )[0]
    return QAPI([run], max_responses=128, max_media_refs=4096), authorize, TOKEN


def control_case(api, *, task="CONTINUOUS_PURSUIT", text=True, scenario="supported_candidate"):
    run = next(iter(api.runs.values()))
    b = run.bindings
    selected = seed_id(b) if task == "CONTINUOUS_PURSUIT" and scenario != "no_seed" else None
    row = next(
        (
            row
            for row in b.index.records
            if any(obs["observation_id"] == selected for obs in row["detections"] or [])
        ),
        None,
    )
    seed = (
        None
        if row is None
        else {
            "observation_id": selected,
            "frame_ref": row["frame_ref"],
            "run_id": b.clock.run_id,
            "camera_id": row["camera_id"],
            "timestamp_us": row["timestamp_us"],
            "source_response_sha256": None,
        }
    )
    return {
        "case_id": scenario + ":" + task,
        "task": task,
        "data_kind": "SYNTHETIC",
        "binding_id": b.index_sha256,
        "run_id": b.clock.run_id,
        "camera_ids": ["A", "B"],
        "source_range_us": [0, b.clock.duration_us],
        "query": {
            "kind": "TEXT" if text else "PRESET",
            "question_id": "SYNTHETIC_CONTROL_LITERAL_NOT_Q3_TESTSET" if text else None,
            "text": (
                "哪幾台拍到人13:00:00到13:00:02"
                if task == "ONCE_SEARCH"
                else "紅衣人13:00:00到13:00:02"
            )
            if text
            else None,
            "request_ref": None if text else "request.json",
            "request_file_sha256": None,
            "context_sha256": b.clock_sha256,
        },
        "selected_seed": seed,
    }


def protocol():
    raw = PROTOCOL.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def sample(
    tmp_path,
    *,
    mode="scripted",
    task="CONTINUOUS_PURSUIT",
    rule=False,
    scenario="supported_candidate",
    text=True,
    mutate=None,
):
    api, auth, token = fixture_api(mode, scenario)
    plan, pin = protocol()
    profile = plan["profiles"][1 if rule else 0]
    case = control_case(api, task=task, text=text, scenario=scenario)
    if mutate:
        mutate(case)
    run = next(iter(api.runs.values()))
    request = q1(run) if task == "ONCE_SEARCH" else q2(run)
    result = execute_sample(
        api,
        auth,
        case,
        profile,
        plan,
        request_loader=lambda value: request,
        session_ref=token,
        output=tmp_path / "sample",
        iteration=0,
        protocol_sha256=pin,
        lost_after_us=600000,
    )
    return result, api, case, profile, plan, pin


def test_q3_q5_are_separate_and_both_recorded_kernels_replay_without_live_provider(tmp_path):
    result, api, *_ = sample(tmp_path)
    assert result["execution_status"] == "COMPLETE", result["errors"]
    assert result["q3"]["used"] and result["q5"]["used"] and result["q5"]["provider_calls"] == 2
    assert (
        result["replay"]["status"] == "PASS"
        and result["replay"]["provider_calls"] == result["replay"]["network_calls"] == 0
    )
    assert result["downstream_lineage_status"] == "UNRESOLVED_SECTION_14_23"
    assert result["fps"]["display_fps"] is result["fps"]["model_inference_fps"] is None
    assert result["evaluation"]["status"] == "UNREVIEWED"
    provider = next(iter(api.runs.values())).q3_options["provider"]
    assert len(provider.requests) == 3  # Replay did not call this provider again.


@pytest.mark.parametrize("mode", ["timeout", "invalid", "unavailable"])
def test_faults_keep_model_failure_and_rule_session_fallback_separate(tmp_path, mode):
    result, *_ = sample(tmp_path, mode=mode)
    assert result["execution_status"] == "COMPLETE", result["errors"]
    assert not result["q3"]["used"] and not result["q5"]["used"]
    assert result["q3"]["fallback_used"] and result["q5"]["fallback_used"]
    assert result["q5"]["provider_calls"] == 1 and result["replay"]["journals_equal"]
    assert result["q3"]["timeout_calls"] == (1 if mode == "timeout" else 0)


def test_rule_only_independent_control_never_calls_configured_model(tmp_path):
    result, api, *_ = sample(tmp_path, rule=True)
    assert result["execution_status"] == "COMPLETE", result["errors"]
    assert result["q3"]["provider_calls"] == result["q5"]["provider_calls"] == 0
    assert not next(iter(api.runs.values())).q3_options["provider"].requests


def test_warm_iteration_gets_fresh_api_not_cached_session_result(tmp_path):
    result, api, case, profile, plan, pin = sample(tmp_path)
    provider = next(iter(api.runs.values())).q3_options["provider"]
    before = len(provider.requests)
    again = execute_sample(
        api,
        authorize,
        case,
        profile,
        plan,
        request_loader=lambda value: None,
        session_ref=TOKEN,
        output=tmp_path / "warm",
        iteration=1,
        protocol_sha256=pin,
        lost_after_us=600000,
    )
    assert again["execution_status"] == "COMPLETE", again["errors"]
    assert len(provider.requests) == before + 3
    assert again["phase"] == "WARM_REPEAT" and again["output_sha256"] == result["output_sha256"]
    assert again["wait_ms"]["completion"] >= again["stages"]["q5"]["wall_ms"]
    assert set(again["stage_replays"]) == {"q3", "q5"}


@pytest.mark.parametrize("scenario", list(PATTERNS))
@pytest.mark.parametrize("task", ["ONCE_SEARCH", "CONTINUOUS_PURSUIT"])
def test_existing_five_control_scenarios_keep_original_replay_and_unknowns(
    tmp_path, scenario, task
):
    result, *_ = sample(tmp_path, scenario=scenario, task=task)
    assert result["execution_status"] == "COMPLETE", result["errors"]
    assert result["replay"]["status"] == "PASS" and result["evaluation"]["accuracy"] is None
    if scenario == "no_seed" and task == "CONTINUOUS_PURSUIT":
        assert result["domain_status"] == "NO_SEED" and result["events"]["lost_episodes"] == 0
    if scenario == "incomplete_candidate_frames" and task == "CONTINUOUS_PURSUIT":
        assert result["domain_status"] == "PARTIAL"


def test_nonparsed_never_executes_downstream(tmp_path):
    result, *_ = sample(tmp_path, mutate=lambda case: case["query"].update(text="找他"))
    assert (
        result["execution_status"] == "COMPLETE"
        and result["domain_status"] == "NEEDS_CLARIFICATION"
    )
    assert not result["downstream_executed"] and result["stages"]["q5"]["wall_ms"] is None


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(run_id="foreign"),
        lambda c: c.update(camera_ids=["A"]),
        lambda c: c["query"].update(context_sha256="b" * 64),
    ],
)
def test_source_scope_or_clock_mismatch_never_claims_success(tmp_path, change):
    result, *_ = sample(tmp_path, mutate=change)
    assert result["execution_status"] == "ERROR" and result["errors"]


def test_protocol_refuses_formal_before_any_model_call_and_cases_refuse_answers(tmp_path):
    plan, pin = protocol()
    assert load_plan(PROTOCOL, pin, engineering=True) == plan
    with pytest.raises(ValueError):
        load_plan(PROTOCOL, pin, engineering=False)
    api, *_ = fixture_api()
    row = control_case(api)
    row["expected_status"] = "PARSED"
    path = tmp_path / "cases.jsonl"
    path.write_bytes(raw_json(row) + b"\n")
    with pytest.raises(ValueError):
        load_cases(path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_preset_skips_q3_and_output_cannot_be_overwritten(tmp_path):
    result, *_ = sample(tmp_path, text=False)
    assert result["execution_status"] == "COMPLETE", result["errors"]
    assert result["q3"]["task_status"] == "SKIPPED_PRESET" and not result["q3"]["attempted"]
    with pytest.raises(FileExistsError):
        sample(tmp_path, text=False)


def test_seed_metadata_mismatch_rejected_before_provider(tmp_path):
    result, api, *_ = sample(
        tmp_path, mutate=lambda case: case["selected_seed"].update(frame_ref="foreign")
    )
    assert (
        result["execution_status"] == "ERROR" and result["errors"][0]["code"] == "SEED_METADATA_PIN"
    )
    assert not next(iter(api.runs.values())).q3_options["provider"].requests


def test_composition_bytes_and_symlink_fail_closed(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    code = root / "example.py"
    code.write_bytes(b"x = 1\n")
    manifest = tmp_path / "composition.json"
    manifest.write_bytes(
        raw_json(
            {
                "scope": "ENGINEERING_COMPOSITION_NOT_INTEGRATED_PRODUCT",
                "files": {
                    "example.py": {
                        "commit": "SYNTHETIC",
                        "sha256": hashlib.sha256(code.read_bytes()).hexdigest(),
                    }
                },
            }
        )
    )
    pin = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert verify_composition(manifest, pin, root)["verified_files"] == 1
    code.write_bytes(b"x = 2\n")
    with pytest.raises(ValueError):
        verify_composition(manifest, pin, root)


@pytest.mark.parametrize("timeout", [False, True])
def test_parent_missing_report_or_worker_timeout_never_reports_complete(
    tmp_path, monkeypatch, timeout
):
    import importlib.util
    import subprocess
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "baseline_cli", ROOT / "scripts/run_q1q5_baseline.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    api, *_ = fixture_api()
    cases = tmp_path / "cases.jsonl"
    cases.write_bytes(raw_json(control_case(api)) + b"\n")
    composition = tmp_path / "composition.json"
    code = ROOT / "scripts/run_q1q5_baseline.py"
    composition.write_bytes(
        raw_json(
            {
                "scope": "ENGINEERING_COMPOSITION_NOT_INTEGRATED_PRODUCT",
                "files": {
                    "scripts/run_q1q5_baseline.py": {
                        "sha256": hashlib.sha256(code.read_bytes()).hexdigest()
                    }
                },
            }
        )
    )
    calls = []

    def worker(command, **kwargs):
        calls.append(command)
        if timeout:
            raise subprocess.TimeoutExpired(command, 1)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", worker)
    # Keep df measurements independent of the worker subprocess mock.
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: "SYNTHETIC_DF")
    plan, pin = protocol()
    output = tmp_path / "run"
    argv = [
        "--protocol",
        str(PROTOCOL),
        "--protocol-sha256",
        pin,
        "--cases",
        str(cases),
        "--cases-sha256",
        hashlib.sha256(cases.read_bytes()).hexdigest(),
        "--composition",
        str(composition),
        "--composition-sha256",
        hashlib.sha256(composition.read_bytes()).hexdigest(),
        "--synthetic",
        "--fixture",
        "scripted",
        "--worker-timeout-ms",
        "1000",
        "--lost-after-us",
        "600000",
        "--output",
        str(output),
    ]
    assert module.main(argv) == 1
    report = json.loads((output / "REPORT.json").read_bytes())
    assert report["status"] == "ERROR" and report["expected_workers"] == 2
    assert len(calls) == (1 if timeout else 2)
    assert (output / "df-before.json").exists() and (output / "df-after.json").exists()

"""CX-8-T artificial recording JSON only; no model, media, GT or formal cases."""
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_baseline_freeze.py"
PARAMETERS = ROOT / "configs/q1q5/parameter_set_v1.json"


def raw(doc):
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def seal(doc, field="content_sha256"):
    doc[field] = sha(raw({k: v for k, v in doc.items() if k != field}))
    return doc


def save(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw(doc))


def fixture(tmp_path, version="q-demo.q2-response.v1"):
    home = tmp_path / "SYNTHETIC"
    recordings = home / "recordings"
    recordings.mkdir(parents=True)
    parameters = json.loads(PARAMETERS.read_bytes())
    save(home / "parameters.json", parameters)
    budgets = {p["name"]: p["value"] for p in parameters["parameters"]
               if p["name"] in {"agent_call_timeout_ms", "agent_total_budget_ms"}}
    save(home / "registry.json", {"fixture_role": "SYNTHETIC_ONLY", "budgets": budgets,
         "parameter_file_sha256": sha((home / "parameters.json").read_bytes())})
    cases = []
    for i, (mode, owner, error) in enumerate([
        ("RULE_ONLY", "RULE_ONLY", None),
        ("AGENT_SEQUENTIAL", "RULE_FALLBACK", "PROVIDER_TIMEOUT"),
        ("AGENT_SEQUENTIAL", "AGENT", None),
    ], start=1):
        sid = f"SYNTHETIC_SESSION_{i}"
        decision = seal(dict(session_id=sid, accepted=True, decided_by=owner,
                             executed_action="RETURN_TO_ORIGIN", llm_calls=[]))
        decisions = raw(decision).decode() + "\n"
        links = raw({"fixture_role": "SYNTHETIC_ONLY", "session_id": sid}).decode() + "\n"
        response = dict(schema_version=version, session_id=sid, switch_mode=mode,
                        identity_verdict="UNCONFIRMED", provenance={"gt_read": False},
                        resolved_scope={"scene_id": "SYNTHETIC_SCENE", "run_ids": ["SYNTHETIC_RUN"],
                                        "parameter_set_sha256": parameters["content_sha256"]},
                        decisions_ref=f"SYNTHETIC_{i}.decisions.jsonl", links_ref=f"SYNTHETIC_{i}.links.jsonl",
                        decisions_sha256=sha(decisions.encode()), links_sha256=sha(links.encode()))
        seal(response, "output_sha256")
        request = {"switch_mode": mode}
        trace = None
        if mode == "AGENT_SEQUENTIAL":
            record = seal({"validation": error or "PROVIDER_VALIDATED"})
            trace = seal(dict(schema_version="q-demo.q5-agent-trace.v1", session_id=sid,
                              events=[{"record": record, "error_code": error}], clock_ticks=[]))
        recording = seal(dict(schema_version="q-demo.api-recording.v1", data_origin="RECORDED",
            recorded_at="2026-10-29T06:00:00+00:00", source_kind="SYNTHETIC",
            scene_id="SYNTHETIC_SCENE", run_id="SYNTHETIC_RUN", request=request,
            request_sha256=sha(raw(request)), response=response, decisions=decisions, links=links,
            snapshots=[], evidence=[], observations={}, media_refs={}, agent_trace=trace,
            q3_provider_audit=[]))
        name = f"{i:032x}.json"
        save(recordings / name, recording)
        save(recordings / f"SYNTHETIC_{i}.response.json", response)
        (recordings / f"SYNTHETIC_{i}.decisions.jsonl").write_bytes(decisions.encode())
        (recordings / f"SYNTHETIC_{i}.links.jsonl").write_bytes(links.encode())
        cases.append(dict(run_id="SYNTHETIC_RUN", mode=mode, response_version=version,
             recording={"recording_id": name[:-5], "file": name,
                        "file_sha256": sha(raw(recording))},
             response_ref=f"SYNTHETIC_{i}.response.json",
             decisions_ref=f"SYNTHETIC_{i}.decisions.jsonl", links_ref=f"SYNTHETIC_{i}.links.jsonl",
             counts={"timeout_calls": int(error is not None), "rule_fallback_decisions": int(owner == "RULE_FALLBACK"),
                     "llm_success_decisions": int(owner == "AGENT")}))
    outputs = {p.name: sha(p.read_bytes()) for p in recordings.iterdir()}
    kit_inputs = {name: pin for name, pin in outputs.items() if name.startswith("SYNTHETIC_")}
    checks = [{"check_id": "SYNTHETIC_CHECK", "document": name, "status": "PASS"}
              for name in sorted(kit_inputs)]
    save(home / "kit.json", {"report_schema": "q1q5-conformance.report.v1",
        "inputs": [{"path": name, "file_sha256": pin} for name, pin in sorted(kit_inputs.items())],
        "checks": checks, "summary": {"by_status": {"PASS": len(checks)}}})
    save(home / "merge_decision.json", {"fixture_role": "SYNTHETIC_ONLY",
         "decision": "DO_NOT_MERGE" if version.endswith(".v1") else "MERGE",
         "response_version": version, "reference": "SYNTHETIC:D98-3"})
    save(home / "score_observation.json", {"fixture_role": "SYNTHETIC_ONLY",
         "freeze_outputs_sha256": sha(raw(outputs)),
         "script_first_read_at": "2026-10-29T06:01:00+00:00"})
    receipt = dict(fixture_role="SYNTHETIC_ONLY", frozen_at="2026-10-29T06:00:30+00:00",
                   outputs=outputs, recordings=cases, kit_not_applicable={})
    save(home / "receipt.json", receipt)
    contract = dict(fixture_role="SYNTHETIC_ONLY", projection="SYNTHETIC_BASELINE_FREEZE_V1",
                    run_ids=["SYNTHETIC_RUN"], response_version=version,
                    kit_input_refs=sorted(kit_inputs),
                    required_kit_checks=[[c["check_id"], c["document"]] for c in checks])
    for key, filename in [("parameters", "parameters.json"), ("registry", "registry.json"),
        ("kit", "kit.json"), ("response_decision", "merge_decision.json")]:
        contract[key] = {"filename": filename, "file_sha256": sha((home / filename).read_bytes())}
    contract["scoring_observations"] = [{"filename": "score_observation.json",
        "file_sha256": sha((home / "score_observation.json").read_bytes())}]
    contract["receipt_file_sha256"] = sha(raw(receipt))
    save(home / "contract.json", contract)
    return home


def checker():
    if not SCRIPT.is_file():
        if os.environ.get("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail("CX8T_IMPLEMENTATION_MISSING")
        pytest.skip("CX8T_IMPLEMENTATION_MISSING")
    spec = importlib.util.spec_from_file_location("baseline_freeze_checker", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(home, **kwargs):
    return checker().inspect_freeze(home / "receipt.json", home / "recordings",
        contract_path=home / "contract.json", contract_sha256=sha((home / "contract.json").read_bytes()), **kwargs)


def mutate(home, filename, change, *, external=None):
    path = home / filename
    doc = json.loads(path.read_bytes())
    change(doc)
    save(path, doc)
    contract = json.loads((home / "contract.json").read_bytes())
    if filename == "receipt.json":
        contract["receipt_file_sha256"] = sha(path.read_bytes())
    elif external:
        if external == "scoring_observations":
            contract[external][0]["file_sha256"] = sha(path.read_bytes())
        else:
            contract[external]["file_sha256"] = sha(path.read_bytes())
    save(home / "contract.json", contract)


@pytest.mark.parametrize("version", ["q-demo.q2-response.v1", "q-demo.q2-response.v2"])
def test_synthetic_positive_replays_only_recorded_bytes(tmp_path, version, monkeypatch):
    home = fixture(tmp_path, version)
    before = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: pytest.fail("NETWORK_FORBIDDEN"))
    result = inspect(home)
    assert result["status"] == "SYNTHETIC_VALID"
    assert result["counts"] == {"timeout_calls": 1, "rule_fallback_decisions": 1, "llm_success_decisions": 1}
    assert result["provider_calls"] == result["network_calls"] == 0
    assert result["formal_run_allowed"] is False and result["human_approval_verified"] is False
    assert all(p.read_bytes() == data for p, data in before.items())


def test_default_contract_unselected(tmp_path):
    home = fixture(tmp_path)
    result = checker().inspect_freeze(home / "receipt.json", home / "recordings")
    assert result["code"] == "CONTRACT_UNSELECTED"


@pytest.mark.parametrize("mode", ["RULE_ONLY", "AGENT_SEQUENTIAL"])
def test_each_run_requires_both_modes(tmp_path, mode):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d.update(recordings=[r for r in d["recordings"] if r["mode"] != mode]))
    assert inspect(home)["code"] == "RUN_MODES_INCOMPLETE"


def test_missing_required_run_cannot_be_omitted(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "contract.json", lambda d: d.update(run_ids=["SYNTHETIC_RUN", "SYNTHETIC_OTHER"]))
    assert inspect(home)["code"] == "RUN_MODES_INCOMPLETE"


@pytest.mark.parametrize("field", ["response_ref", "decisions_ref", "links_ref"])
def test_replay_compares_actual_bytes_even_after_all_file_pins_resealed(tmp_path, field):
    home = fixture(tmp_path)
    receipt = json.loads((home / "receipt.json").read_bytes())
    filename = receipt["recordings"][0][field]
    path = home / "recordings" / filename
    path.write_bytes(path.read_bytes() + b"\n")
    mutate(home, "receipt.json", lambda d: d["outputs"].update({filename: sha(path.read_bytes())}))
    updated = json.loads((home / "receipt.json").read_bytes())["outputs"]
    mutate(home, "score_observation.json", lambda d: d.update(freeze_outputs_sha256=sha(raw(updated))), external="scoring_observations")
    assert inspect(home)["code"] == "REPLAY_BYTES_CHANGED"


@pytest.mark.parametrize("key", ["agent_call_timeout_ms", "agent_total_budget_ms"])
def test_budget_drift_against_pinned_d65_source(tmp_path, key):
    home = fixture(tmp_path)
    def change(doc):
        next(p for p in doc["parameters"] if p["name"] == key)["value"] += 1
    mutate(home, "parameters.json", change, external="parameters")
    assert inspect(home)["code"] == "BUDGET_CHANGED"


def test_registry_budget_must_match_parameters(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "registry.json", lambda d: d["budgets"].update(agent_call_timeout_ms=1), external="registry")
    assert inspect(home)["code"] == "REGISTRY_BUDGET_MISMATCH"


def test_fallback_cannot_be_counted_as_llm_success(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d["recordings"][1]["counts"].update(llm_success_decisions=1))
    assert inspect(home)["code"] == "COUNTS_MISMATCH"


def test_timeout_count_cannot_be_lost(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d["recordings"][1]["counts"].update(timeout_calls=0))
    assert inspect(home)["code"] == "COUNTS_MISMATCH"


def test_counts_require_integers_not_boolean_equivalence(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d["recordings"][1]["counts"].update(timeout_calls=True))
    assert inspect(home)["code"] == "COUNTS_MISMATCH"


def test_every_output_has_exact_bytes_pin_and_inventory(tmp_path):
    home = fixture(tmp_path)
    receipt = json.loads((home / "receipt.json").read_bytes())
    name = next(iter(receipt["outputs"]))
    (home / "recordings" / name).write_bytes(b"tamper")
    assert inspect(home)["code"] == "OUTPUT_PIN_MISMATCH"


def test_unlisted_output_fails(tmp_path):
    home = fixture(tmp_path)
    save(home / "recordings/extra.json", {})
    assert inspect(home)["code"] == "OUTPUT_SET_MISMATCH"


@pytest.mark.parametrize("read_at", ["2026-10-29T06:00:29+00:00", "2026-10-29T06:00:30+00:00", "2026-10-29T06:01:00"])
def test_freeze_precedes_every_scoring_script_read(tmp_path, read_at):
    home = fixture(tmp_path)
    mutate(home, "score_observation.json", lambda d: d.update(script_first_read_at=read_at), external="scoring_observations")
    assert inspect(home)["code"] in {"FREEZE_ORDER_INVALID", "TIMESTAMP_INVALID"}


def test_no_scoring_observation_is_unknown_not_vacuous_pass(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "contract.json", lambda d: d.update(scoring_observations=[]))
    assert inspect(home)["code"] == "SCORING_READ_ORDER_UNKNOWN"


def test_recording_timestamp_must_precede_freeze(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d.update(frozen_at="2026-10-29T05:00:00+00:00"))
    assert inspect(home)["code"] == "RECORDING_AFTER_FREEZE"


def test_kit_fail_is_not_hidden_by_forged_zero_summary(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "kit.json", lambda d: d["checks"][0].update(status="FAIL"), external="kit")
    assert inspect(home)["code"] == "KIT_HAS_FAIL"


def test_kit_missing_input_or_check_fails(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "kit.json", lambda d: d["inputs"].pop(), external="kit")
    assert inspect(home)["code"] == "KIT_INPUT_SCOPE_MISMATCH"


def test_kit_missing_required_check_fails(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "kit.json", lambda d: d["checks"].pop(), external="kit")
    assert inspect(home)["code"] == "KIT_CHECK_SCOPE_MISMATCH"


def test_kit_report_absence_fails(tmp_path):
    home = fixture(tmp_path)
    (home / "kit.json").unlink()
    assert inspect(home)["status"] == "FAIL"


def test_scoring_observation_from_other_freeze_cannot_satisfy_order(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "score_observation.json", lambda d: d.update(freeze_outputs_sha256="0" * 64), external="scoring_observations")
    assert inspect(home)["code"] == "SCORING_OBSERVATION_SCOPE_MISMATCH"


def test_llm_success_requires_a_validated_non_timeout_call(tmp_path):
    home = fixture(tmp_path)
    bundle = json.loads((home / "recordings" / f"{2:032x}.json").read_bytes())
    decision = json.loads(bundle["decisions"])
    decision["decided_by"] = "AGENT"
    bundle["decisions"] = raw(decision).decode() + "\n"
    module = checker()
    with pytest.raises(module.FreezeError, match="LLM_SUCCESS_WITHOUT_VALIDATED_CALL"):
        module.recorded_counts(bundle)


def test_unknown_projection_never_selects_production(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "contract.json", lambda d: d.update(projection="FORMAL_FREEZE_V1"))
    assert inspect(home)["code"] == "CONTRACT_UNSELECTED"


def test_kit_na_requires_each_check_reason(tmp_path):
    home = fixture(tmp_path)
    kit = json.loads((home / "kit.json").read_bytes())
    kit["checks"][0]["status"] = "SKIPPED_PARAM_UNSET"
    kit["summary"]["by_status"] = dict(Counter(c["status"] for c in kit["checks"]))
    save(home / "kit.json", kit)
    mutate(home, "kit.json", lambda d: None, external="kit")
    assert inspect(home)["code"] == "KIT_NOT_APPLICABLE_REASON_MISSING"
    key = kit["checks"][0]["check_id"] + ":" + kit["checks"][0]["document"]
    mutate(home, "receipt.json", lambda d: d["kit_not_applicable"].update({key: "SYNTHETIC ONLY: no corresponding context in this control case"}))
    assert inspect(home)["status"] == "SYNTHETIC_VALID"


@pytest.mark.parametrize("version", ["q-demo.q2-response.v2", "UNKNOWN", None])
def test_explicit_response_version_must_match_selected_decision(tmp_path, version):
    home = fixture(tmp_path)
    mutate(home, "receipt.json", lambda d: d["recordings"][0].update(response_version=version))
    assert inspect(home)["code"] == "RESPONSE_VERSION_MISMATCH"


def test_unselected_or_contradictory_merge_decision_fails(tmp_path):
    home = fixture(tmp_path)
    mutate(home, "merge_decision.json", lambda d: d.update(decision="MERGE"), external="response_decision")
    assert inspect(home)["code"] == "RESPONSE_DECISION_UNSELECTED"


def test_recording_directory_cannot_be_inside_repo_or_symlink(tmp_path):
    home = fixture(tmp_path)
    assert inspect(home, repo_root=home)["code"] == "OUTPUT_OUTSIDE_REPO_REQUIRED"
    link = home / "linked"
    link.symlink_to(home / "recordings", target_is_directory=True)
    result = checker().inspect_freeze(home / "receipt.json", link,
        contract_path=home / "contract.json", contract_sha256=sha((home / "contract.json").read_bytes()))
    assert result["code"] == "SYMLINK_REJECTED"


def test_symlink_output_file_is_rejected_before_read(tmp_path):
    home = fixture(tmp_path)
    target = home / "recordings/SYNTHETIC_1.response.json"
    outside = home / "outside.json"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)
    assert inspect(home)["code"] == "SYMLINK_REJECTED"


def test_new_report_directory_is_exclusive_and_outside_repo(tmp_path):
    module = checker()
    target = tmp_path / "SYNTHETIC_NEW_REPORT"
    module.write_new_report(target, {"status": "SYNTHETIC_VALID"})
    original = (target / "check.json").read_bytes()
    with pytest.raises(module.FreezeError, match="NEW_OUTPUT_REQUIRED"):
        module.write_new_report(target, {"status": "changed"})
    assert (target / "check.json").read_bytes() == original
    with pytest.raises(module.FreezeError, match="OUTPUT_OUTSIDE_REPO_REQUIRED"):
        module.write_new_report(tmp_path / "in_repo", {}, repo_root=tmp_path)
    alias = tmp_path / "linked_report"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(module.FreezeError, match="SYMLINK_REJECTED"):
        module.write_new_report(alias, {})


def test_cli_relative_paths_and_default_failclosed(tmp_path):
    home = fixture(tmp_path)
    command = [sys.executable, str(SCRIPT), "--receipt", "receipt.json", "--recordings", "recordings"]
    result = subprocess.run(command, cwd=home, capture_output=True, text=True)
    assert result.returncode == 1 and json.loads(result.stdout)["code"] == "CONTRACT_UNSELECTED"
    result = subprocess.run(command + ["--contract-options", "contract.json", "--contract-sha256",
        sha((home / "contract.json").read_bytes()), "--output", "SYNTHETIC_REPORT"], cwd=home, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["human_approval_verified"] is False
    assert (home / "SYNTHETIC_REPORT/check.json").is_file()

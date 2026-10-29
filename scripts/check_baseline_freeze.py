#!/usr/bin/env python3
"""CX-8-T mechanical synthetic freeze checks; production contract UNSELECTED.

Uses recorded API playback only, never a live run, provider, script or evaluator.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.api import APIError, QAPI, RecordingStore, raw_json
from amidst.q1q5.production_preflight import strict_json
from amidst.q1q5.store import canonical_hash

VERSION = "cx8t-synthetic-v1"
PARAMETERS_SHA256 = "960d823c17c181c6b0b128a3cc7f39fb0d5f7af19828073b884d74aa8336ee6e"
PARAMETERS = ROOT / "configs/q1q5/parameter_set_v1.json"
BUDGET_NAMES = {"agent_call_timeout_ms", "agent_total_budget_ms"}
MAX_FILE = 16_777_216
SHA = re.compile(r"[0-9a-f]{64}")


class FreezeError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise FreezeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(path):
    path = Path(path).absolute()
    require(path.resolve() == path, "SYMLINK_REJECTED")
    return path


def read(path):
    path = canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_FILE, "FILE_SIZE_OR_TYPE")
        raw = stream.read(MAX_FILE + 1)
    require(len(raw) == info.st_size, "FILE_CHANGED_DURING_READ")
    return raw


def pinned(path, pin, code):
    require(isinstance(pin, str) and SHA.fullmatch(pin), code)
    raw = read(path)
    require(sha(raw) == pin, code)
    return strict_json(raw)


def relative(root, name):
    require(isinstance(name, str) and name and "\\" not in name, "RELATIVE_PATH_REQUIRED")
    parts = PurePosixPath(name)
    require(not parts.is_absolute() and parts.as_posix() == name and ".." not in parts.parts,
            "RELATIVE_PATH_REQUIRED")
    return canonical(root / name)


def external(root, ref):
    require(isinstance(ref, dict) and set(ref) == {"filename", "file_sha256"},
            "EXTERNAL_REFERENCE_MISSING")
    return pinned(relative(root, ref["filename"]), ref["file_sha256"], "EXTERNAL_PIN_MISMATCH")


def instant(value):
    require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value),
        "TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FreezeError("TIMESTAMP_INVALID") from exc
    require(parsed.utcoffset() is not None, "TIMESTAMP_INVALID")
    return parsed


def budgets(doc):
    require(isinstance(doc, dict) and isinstance(doc.get("parameters"), list), "BUDGET_CHANGED")
    rows = [p for p in doc["parameters"] if p.get("name") in BUDGET_NAMES]
    require(len(rows) == len(BUDGET_NAMES) and {p["name"] for p in rows} == BUDGET_NAMES
            and all(p.get("status") == "APPROVED" and p.get("unit") == "ms"
                    and type(p.get("value")) is int and p["value"] > 0 for p in rows), "BUDGET_CHANGED")
    return {p["name"]: p["value"] for p in rows}


def check_kit(kit, receipt, contract):
    require(kit.get("report_schema") == "q1q5-conformance.report.v1", "KIT_REPORT_MISSING")
    inputs = kit.get("inputs")
    selected = contract.get("kit_input_refs")
    require(isinstance(selected, list) and selected and len(selected) == len(set(selected))
            and set(selected) <= receipt["outputs"].keys(), "KIT_INPUT_SCOPE_MISMATCH")
    require(isinstance(inputs, list) and len(inputs) == len(selected)
            and {i.get("path"): i.get("file_sha256") for i in inputs}
            == {name: receipt["outputs"][name] for name in selected},
            "KIT_INPUT_SCOPE_MISMATCH")
    checks = kit.get("checks")
    require(isinstance(checks, list) and checks, "KIT_REPORT_MISSING")
    require(not any(c.get("status") == "FAIL" for c in checks), "KIT_HAS_FAIL")
    required = contract.get("required_kit_checks")
    require(isinstance(required, list) and required and len(required) == len(checks)
            and {tuple(pair) for pair in required}
            == {(c.get("check_id"), c.get("document")) for c in checks}, "KIT_CHECK_SCOPE_MISMATCH")
    require(len({tuple(pair) for pair in required}) == len(required), "KIT_CHECK_SCOPE_MISMATCH")
    reasons = receipt.get("kit_not_applicable")
    require(isinstance(reasons, dict), "KIT_NOT_APPLICABLE_REASON_MISSING")
    for check in checks:
        status = check.get("status")
        if status != "PASS":
            require(status in {"SKIPPED_NO_CONTEXT", "SKIPPED_PARAM_UNSET"}, "KIT_STATUS_UNKNOWN")
            reason = reasons.get(str(check.get("check_id")) + ":" + str(check.get("document")))
            require(isinstance(reason, str) and reason.strip(), "KIT_NOT_APPLICABLE_REASON_MISSING")
    require(kit.get("summary", {}).get("by_status") == dict(Counter(c["status"] for c in checks)),
            "KIT_SUMMARY_MISMATCH")


def recorded_counts(bundle):
    decisions = [strict_json(line.encode()) for line in bundle["decisions"].splitlines() if line.strip()]
    trace = bundle.get("agent_trace")
    events = trace.get("events", []) if trace else []
    require(isinstance(events, list), "RECORDING_INVALID")
    for event in events:
        require(isinstance(event, dict) and isinstance(event.get("record"), dict), "RECORDING_INVALID")
        require(event["record"].get("content_sha256") == canonical_hash(event["record"],
                exclude=("content_sha256", "stats")), "PROVIDER_AUDIT_PIN_MISMATCH")
        require((event["record"].get("validation") == "PROVIDER_TIMEOUT")
                == (event.get("error_code") == "PROVIDER_TIMEOUT"), "PROVIDER_AUDIT_INCONSISTENT")
    counts = {
        "timeout_calls": sum(e["record"].get("validation") == "PROVIDER_TIMEOUT" for e in events),
        "rule_fallback_decisions": sum(d.get("decided_by") == "RULE_FALLBACK"
                                       and d.get("executed_action") is not None for d in decisions),
        "llm_success_decisions": sum(d.get("accepted") is True and d.get("decided_by") == "AGENT"
                                     for d in decisions),
    }
    successful_calls = sum(e["record"].get("validation") == "PROVIDER_VALIDATED"
                           and e.get("error_code") is None for e in events)
    require(counts["llm_success_decisions"] <= successful_calls, "LLM_SUCCESS_WITHOUT_VALIDATED_CALL")
    return counts


def _inspect(receipt_path, recordings, contract_path, contract_sha256, repo_root):
    require(contract_path is not None and contract_sha256 is not None, "CONTRACT_UNSELECTED")
    contract_path = canonical(contract_path)
    contract = pinned(contract_path, contract_sha256, "CONTRACT_PIN_MISMATCH")
    require(isinstance(contract, dict) and contract.get("fixture_role") == "SYNTHETIC_ONLY"
            and contract.get("projection") == "SYNTHETIC_BASELINE_FREEZE_V1", "CONTRACT_UNSELECTED")
    receipt = pinned(canonical(receipt_path), contract.get("receipt_file_sha256"), "RECEIPT_PIN_MISMATCH")
    require(isinstance(receipt, dict) and receipt.get("fixture_role") == "SYNTHETIC_ONLY",
            "SYNTHETIC_ROLE_REQUIRED")
    recordings, repo_root = canonical(recordings), canonical(repo_root)
    require(recordings.is_dir() and not recordings.is_relative_to(repo_root), "OUTPUT_OUTSIDE_REPO_REQUIRED")
    parameters = external(contract_path.parent, contract.get("parameters"))
    golden = pinned(PARAMETERS, PARAMETERS_SHA256, "BUDGET_SOURCE_PIN_MISMATCH")
    expected_budgets = budgets(golden)
    require(budgets(parameters) == expected_budgets, "BUDGET_CHANGED")
    require(parameters.get("content_sha256") == canonical_hash(parameters,
            exclude=("content_sha256", "parameter_set_id")), "PARAMETER_CONTENT_PIN_MISMATCH")
    registry = external(contract_path.parent, contract.get("registry"))
    require(registry.get("fixture_role") == "SYNTHETIC_ONLY"
            and registry.get("budgets") == expected_budgets
            and all(type(v) is int for v in registry["budgets"].values())
            and registry.get("parameter_file_sha256") == contract["parameters"]["file_sha256"],
            "REGISTRY_BUDGET_MISMATCH")
    version = contract.get("response_version")
    decision = external(contract_path.parent, contract.get("response_decision"))
    require(version in {"q-demo.q2-response.v1", "q-demo.q2-response.v2"}
            and decision.get("fixture_role") == "SYNTHETIC_ONLY"
            and decision.get("response_version") == version and decision.get("reference")
            and decision.get("decision") == ("DO_NOT_MERGE" if version.endswith(".v1") else "MERGE"),
            "RESPONSE_DECISION_UNSELECTED")
    frozen = instant(receipt.get("frozen_at"))
    observations = contract.get("scoring_observations")
    require(isinstance(observations, list) and observations, "SCORING_READ_ORDER_UNKNOWN")
    for ref in observations:
        observation = external(contract_path.parent, ref)
        require(observation.get("fixture_role") == "SYNTHETIC_ONLY", "SYNTHETIC_ROLE_REQUIRED")
        require(observation.get("freeze_outputs_sha256") == sha(raw_json(receipt.get("outputs"))),
                "SCORING_OBSERVATION_SCOPE_MISMATCH")
        require(frozen < instant(observation.get("script_first_read_at")), "FREEZE_ORDER_INVALID")
    entries = receipt.get("recordings")
    runs = contract.get("run_ids")
    require(isinstance(runs, list) and runs and len(runs) == len(set(runs))
            and all(isinstance(r, str) and r for r in runs)
            and isinstance(entries, list) and entries, "RUN_MODES_INCOMPLETE")
    actual_modes = {run: {r.get("mode") for r in entries if r.get("run_id") == run} for run in runs}
    require({r.get("run_id") for r in entries} == set(runs)
            and all(modes == {"RULE_ONLY", "AGENT_SEQUENTIAL"} for modes in actual_modes.values()),
            "RUN_MODES_INCOMPLETE")
    outputs = receipt.get("outputs")
    require(isinstance(outputs, dict) and outputs, "OUTPUT_PINS_MISSING")
    actual = set()
    for path in recordings.rglob("*"):
        require(not path.is_symlink(), "SYMLINK_REJECTED")
        require(path.is_dir() or path.is_file(), "FILE_SIZE_OR_TYPE")
        if path.is_file():
            actual.add(path.relative_to(recordings).as_posix())
    require(actual == set(outputs), "OUTPUT_SET_MISMATCH")
    for name, pin in outputs.items():
        require(isinstance(pin, str) and SHA.fullmatch(pin)
                and sha(read(relative(recordings, name))) == pin, "OUTPUT_PIN_MISMATCH")
    store = RecordingStore(recordings, repo_root=repo_root, max_bytes=MAX_FILE)
    total = Counter(timeout_calls=0, rule_fallback_decisions=0, llm_success_decisions=0)
    seen_recordings, consumed_outputs = set(), set()
    for entry in entries:
        require(entry.get("response_version") == version, "RESPONSE_VERSION_MISMATCH")
        pin = entry.get("recording")
        require(isinstance(pin, dict) and pin.get("file") in outputs
                and pin.get("file_sha256") == outputs[pin["file"]]
                and pin.get("file") not in seen_recordings, "RECORDING_PIN_MISMATCH")
        seen_recordings.add(pin["file"])
        bundle = store.load(pin)
        require(bundle.get("source_kind") == "SYNTHETIC" and bundle.get("run_id") == entry["run_id"]
                and bundle.get("request", {}).get("switch_mode") == entry["mode"], "RECORDING_SCOPE_MISMATCH")
        require(instant(bundle.get("recorded_at")) <= frozen, "RECORDING_AFTER_FREEZE")
        response = bundle["response"]
        require(response.get("schema_version") == version and response.get("switch_mode") == entry["mode"],
                "RESPONSE_VERSION_MISMATCH")
        require(response.get("resolved_scope", {}).get("parameter_set_sha256") == parameters["content_sha256"],
                "RECORDING_PARAMETER_PIN_MISMATCH")
        for kind in ("decisions", "links"):
            require(sha(bundle[kind].encode()) == response.get(kind + "_sha256"), "JOURNAL_PIN_MISMATCH")
        # No live runs, provider or model is available to this API instance.
        api = QAPI(max_responses=128, max_media_refs=4096, recording_store=store, recordings=[pin])
        token = "SYNTHETIC_OFFLINE_CHECKER"
        auth = lambda supplied, scene, *args, **kwargs: supplied == token and scene == bundle["scene_id"]
        repeated = api.call("q_recorded_response", {"session_ref": token, "recording_id": pin["recording_id"]}, auth)
        require(raw_json(repeated) == read(relative(recordings, entry["response_ref"])), "REPLAY_BYTES_CHANGED")
        consumed_outputs.update({pin["file"], entry["response_ref"]})
        for kind in ("decisions", "links"):
            result = api.call("q2_artifact", {"session_ref": token, "response_ref": repeated["session_id"],
                              "kind": kind, "ref": repeated[kind + "_ref"]}, auth)
            require(result["jsonl"].encode() == read(relative(recordings, entry[kind + "_ref"])), "REPLAY_BYTES_CHANGED")
            consumed_outputs.add(entry[kind + "_ref"])
        counts = recorded_counts(bundle)
        declared = entry.get("counts")
        require(isinstance(declared, dict) and declared == counts
                and all(type(v) is int and v >= 0 for v in declared.values()), "COUNTS_MISMATCH")
        if entry["mode"] == "RULE_ONLY":
            require(not bundle.get("agent_trace") and not any(counts.values()), "RULE_MODE_PROVIDER_EVENTS")
        total.update(counts)
    require(consumed_outputs == set(outputs), "OUTPUT_SET_MISMATCH")
    kit = external(contract_path.parent, contract.get("kit"))
    check_kit(kit, receipt, contract)
    return {"status": "SYNTHETIC_VALID", "run_count": len(runs), "recording_count": len(entries),
            "counts": dict(total), "replay": "RECORDED_API_PLAYBACK_BYTES_ONLY",
            "provider_calls": 0, "network_calls": 0, "expected_budgets_ms": expected_budgets}


def inspect_freeze(receipt, recordings, *, contract_path=None, contract_sha256=None, repo_root=ROOT):
    try:
        result = _inspect(receipt, recordings, contract_path, contract_sha256, repo_root)
    except FreezeError as exc:
        result = {"status": "FAIL", "code": str(exc)}
    except APIError:
        result = {"status": "FAIL", "code": "RECORDING_INVALID"}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        result = {"status": "FAIL", "code": "INPUT_INVALID"}
    return {**result, "checker_version": VERSION, "human_approval_verified": False,
            "formal_run_allowed": False, "production_contract": "UNSELECTED",
            "historical_producer_no_overwrite": "UNKNOWN", "independent_kit_execution": False}


def write_new_report(output, result, *, repo_root=ROOT):
    output, repo_root = canonical(output), canonical(repo_root)
    require(not output.is_relative_to(repo_root), "OUTPUT_OUTSIDE_REPO_REQUIRED")
    require(output.parent.is_dir() and not output.exists(), "NEW_OUTPUT_REQUIRED")
    try:
        output.mkdir(mode=0o700)
        fd = os.open(output / "check.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw_json(result))
    except FileExistsError as exc:
        raise FreezeError("NEW_OUTPUT_REQUIRED") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--recordings", type=Path, required=True)
    parser.add_argument("--contract-options", type=Path)
    parser.add_argument("--contract-sha256")
    parser.add_argument("--output", type=Path, help="Optional new report directory outside repo; never overwrite")
    args = parser.parse_args()
    result = inspect_freeze(args.receipt, args.recordings, contract_path=args.contract_options,
                            contract_sha256=args.contract_sha256)
    if args.output:
        try:
            write_new_report(args.output, result)
        except (FreezeError, OSError) as exc:
            result = {**result, "status": "FAIL", "code": str(exc) if isinstance(exc, FreezeError) else "OUTPUT_WRITE_FAILED"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "SYNTHETIC_VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())

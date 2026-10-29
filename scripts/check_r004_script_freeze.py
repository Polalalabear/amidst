"""Evaluation-only consistency check for the CQ-24 r004 freeze candidate.

PASS describes the candidate and pinned inputs only. It never approves a
freeze, supplies physical evidence, or authorizes rendering. Unmaterialized
safe bundles are reported separately as NOT_RUN, never as privacy PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from amidst.evaluation.q5_script_adapter import derive_windows, load_plan, precheck  # noqa: E402

SCENARIOS = {
    "A4-1": {"duration_us": 50_000_000, "scored": {"A4-c1", "A4-n1"},
             "unscored": {"A4-e", "A4-c2"}, "d96_event": "A4-c2"},
    "B4-1": {"duration_us": 42_000_000, "scored": {"B4-n1", "B4-b"},
             "unscored": {"B4-d", "B4-e"}, "d96_event": "B4-e"},
}
INTERVAL_US = 200_000


class FreezeError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FreezeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY: " + key)
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(FreezeError("NONFINITE_JSON")))
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def read_ref(root, ref):
    require(isinstance(ref, dict), "FILE_REF_REQUIRED")
    name, expected = ref.get("path"), ref.get("sha256")
    require(isinstance(name, str) and bool(name), "FILE_PATH_REQUIRED")
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "RELATIVE_FILE_PATH_REQUIRED")
    path = root / relative
    require(path.resolve() == path and path.is_file(), "REGULAR_PINNED_FILE_REQUIRED: " + name)
    require(isinstance(expected, str) and len(expected) == 64
            and all(c in "0123456789abcdef" for c in expected), "SHA256_REQUIRED: " + name)
    raw = path.read_bytes()
    require(sha(raw) == expected, "FILE_HASH_MISMATCH: " + name)
    return raw


def integer(value):
    return type(value) is int


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def check_run(root, row, source_pins, tracking, private_tokens):
    scenario = row.get("scenario")
    require(scenario in SCENARIOS, "UNKNOWN_SCENARIO")
    expected = SCENARIOS[scenario]
    prefix = scenario + ": "
    producer_raw = read_ref(root, row.get("producer_script"))
    plan_raw = read_ref(root, row.get("adapter_plan"))
    producer = json_object(producer_raw)
    plan = load_plan(plan_raw)
    clock = json_object(read_ref(root, row.get("clock")))
    run = json_object(read_ref(root, row.get("run_declaration")))
    for key, raw in [("producer_script", producer_raw), ("adapter_plan", plan_raw)]:
        private_tokens.update([Path(row[key]["path"]).name.casefold(), sha(raw)])
    require(producer.get("scenario") == scenario, prefix + "PRODUCER_SCENARIO_MISMATCH")
    require(producer.get("status") == "UNFROZEN_DRAFT_NOT_EXECUTABLE"
            and producer.get("producer_execution_enabled") is False
            and producer.get("freeze_sha256") is None and producer.get("approval_ref") is None,
            prefix + "PRODUCER_MUST_REMAIN_UNFROZEN")
    context = producer.get("declared_run_context", {})
    require(all(d.get("source_duration_us") == expected["duration_us"] for d in [row, context, plan, clock, run]),
            prefix + "DURATION_MISMATCH")
    require(context.get("fps") == row.get("fps") == 5
            and context.get("sample_interval_us") == row.get("sample_interval_us") == INTERVAL_US
            and plan.get("parameters", {}).get("index_interval_us") == INTERVAL_US,
            prefix + "FIVE_FPS_GRID_REQUIRED")
    require(context.get("sample_count_per_camera") == expected["duration_us"] // INTERVAL_US,
            prefix + "SAMPLE_COUNT_MISMATCH")
    require(plan.get("status") == "PLANNED", prefix + "ADAPTER_PLAN_MUST_REMAIN_PLANNED")
    require(plan.get("run_id") == run.get("run_id") == context.get("run_id")
            and plan.get("clock_id") == clock.get("clock_id") == run.get("clock_id"),
            prefix + "RUN_CLOCK_BINDING_MISMATCH")
    require(clock.get("run_id") == run.get("run_id")
            and clock.get("mapping_kind") == "DECLARED_DEMO_CLOCK"
            and clock.get("timezone") == "Asia/Taipei", prefix + "CLOCK_DECLARATION_MISMATCH")
    require(run.get("source_sha256") == source_pins.get("source_sha256")
            and run.get("camera_catalog_sha256") == source_pins.get("catalog_sha256"),
            prefix + "SOURCE_CATALOG_MISMATCH")
    require(plan.get("query_range_us") == context.get("query_source_range_us") == run.get("query_source_range_us"),
            prefix + "QUERY_RANGE_MISMATCH")
    require(set(producer.get("render_camera_ids", [])) == set(run.get("camera_ids", [])),
            prefix + "RENDER_CAMERA_SCOPE_MISMATCH")
    allowed = row.get("auto_switch_candidate_camera_ids")
    require(isinstance(allowed, list) and len(allowed) == len(set(allowed))
            and "CAM_ENTRY" not in allowed
            and set(allowed) == set(run["camera_ids"]) & set(tracking["tracking_camera_ids"]),
            prefix + "D74_AUTO_SWITCH_SCOPE_INVALID")
    require(producer.get("runtime_seed_intent", {}).get("camera_id") != "CAM_ENTRY",
            prefix + "D74_SEED_INVALID")
    scored = plan.get("events", [])
    unscored = plan.get("unscored_events", [])
    require({e.get("event_id") for e in scored} == expected["scored"]
            and {e.get("event_id") for e in unscored} == expected["unscored"],
            prefix + "D92_D96_SCORING_SPLIT_MISMATCH")
    require(row.get("scored_event_ids") == sorted(expected["scored"])
            and row.get("unscored_event_ids") == sorted(expected["unscored"])
            and row.get("declared_scored_event_count") == len(scored), prefix + "DECLARED_EVENT_COUNT_MISMATCH")
    require(all(e.get("scoring_status") in {"NONSCORING", "NONSCORING_PENDING_VERIFICATION"} for e in unscored),
            prefix + "UNSCORED_STATUS_REQUIRED")
    cues = {e.get("card_event_id"): e for e in producer.get("planning_cues", [])}
    require(set(cues) == expected["scored"] | expected["unscored"], prefix + "PRODUCER_CUE_SET_MISMATCH")
    for event in scored + unscored:
        event_id = event["event_id"]
        times = [event.get("t_x_us")]
        if event.get("action") in {"SWITCH", "RETURN_TO_ORIGIN"}:
            times.append(event.get("t_n_us"))
        require(all(integer(t) and 0 <= t < expected["duration_us"] and t % INTERVAL_US == 0 for t in times),
                prefix + "EVENT_TIME_OUTSIDE_RUN_OR_GRID: " + event_id)
        cue = cues[event_id]
        require(cue.get("planned_leave_cue_us", cue.get("planned_time_us")) == event["t_x_us"]
                and (event["action"] == "NO_SWITCH" or cue.get("planned_arrive_cue_us") == event["t_n_us"]),
                prefix + "PRODUCER_ADAPTER_TIME_MISMATCH: " + event_id)
        require("CAM_ENTRY" not in event.get("allowed_camera_ids", [])
                and set(event.get("allowed_camera_ids", [])) <= set(allowed),
                prefix + "D74_EVENT_CAMERA_INVALID: " + event_id)
    # Continuous authored control points are not RGB sample or scoring anchors.
    waypoints = producer.get("planning_waypoints", [])
    times = [p.get("planned_source_time_us") for p in waypoints]
    require(len(times) >= 2 and all(integer(t) for t in times)
            and times[0] == 0 and times[-1] == expected["duration_us"]
            and all(a < b for a, b in zip(times, times[1:])), prefix + "PRODUCER_CONTROL_TIME_INVALID")
    require(all(isinstance(p.get("foot_anchor_world_m"), list) and len(p["foot_anchor_world_m"]) == 3
                and all(type(x) in {int, float} and math.isfinite(x) for x in p["foot_anchor_world_m"])
                for p in waypoints), prefix + "PRODUCER_CONTROL_POINT_INVALID")
    verification = row.get("d96_verification", {})
    require(verification.get("event_id") == expected["d96_event"]
            and verification.get("scoring_enabled") is False
            and verification.get("verdict") in {"UNKNOWN", "NOT_PASSED"}, prefix + "D96_FAIL_CLOSED_REQUIRED")
    reference = verification.get("verification_ref", {})
    require(isinstance(reference.get("pr"), str) and isinstance(reference.get("head"), str)
            and len(reference["head"]) == 40, prefix + "D96_VERIFICATION_REF_REQUIRED")
    read_ref(root, reference.get("evidence_file"))
    report = precheck(plan)
    require(report.get("ok") is True, prefix + "ADAPTER_PRECHECK_FAILED: " + "; ".join(report.get("errors", [])))
    windows, errors = derive_windows(plan)
    require(not errors and all(0 <= e["decision_window_us"][0] < e["decision_window_us"][1] <= expected["duration_us"] for e in windows),
            prefix + "D79_WINDOW_INVALID")
    require(all(a["decision_window_us"][1] <= b["decision_window_us"][0] for a, b in zip(windows, windows[1:])),
            prefix + "D79_WINDOWS_OVERLAP")
    declared_windows = [{"event_id": e["event_id"], "range_us": e["decision_window_us"]} for e in windows]
    require(row.get("derived_scored_decision_windows") == declared_windows,
            prefix + "DECLARED_WINDOWS_MISMATCH")
    require(report.get("total_planned_searching") == row.get("declared_planned_search_count") == 3,
            prefix + "SEARCH_BUDGET_MISMATCH")
    return {"scenario": scenario, "status": "PASS", "scored_event_count": len(scored),
            "unscored_event_ids": sorted(expected["unscored"]), "planned_search_count": 3,
            "run_materialization_status": run.get("status"), "run_rendered": run.get("rendered"),
            "decision_windows": declared_windows}


def check_freeze(freeze_path, *, root=ROOT, expected_freeze_sha256=None):
    root = Path(root).resolve()
    freeze_path = Path(freeze_path)
    report = {"candidate_status": "FAIL", "ok": False, "production_ready": False,
              "freeze_approval": "PENDING_USER", "errors": [], "run_checks": [], "safe_bundle_checks": []}
    try:
        raw = freeze_path.read_bytes()
        require(expected_freeze_sha256 is None or sha(raw) == expected_freeze_sha256, "FREEZE_FILE_HASH_MISMATCH")
        doc = json_object(raw)
        require(doc.get("status") == "PROPOSED" and doc.get("production_ready") is False
                and doc.get("freeze_approval") == "PENDING_USER" and doc.get("approval_ref") is None,
                "CANDIDATE_MUST_NOT_DECLARE_APPROVAL")
        source = doc.get("source_pins", {})
        camera = json_object(read_ref(root, source.get("camera_graph")))
        json_object(read_ref(root, source.get("region_graph")))
        tracking = json_object(read_ref(root, source.get("tracking_scope")))
        require(source.get("catalog_sha256") == camera.get("camera_catalog_sha256"), "GRAPH_CATALOG_MISMATCH")
        rows = doc.get("runs")
        require(isinstance(rows, list) and len(rows) == 2
                and {r.get("scenario") for r in rows} == set(SCENARIOS), "BOTH_SCENARIOS_REQUIRED")
        private_tokens = {freeze_path.name.casefold(), sha(raw)}
        for row in rows:
            report["run_checks"].append(check_run(root, row, source, tracking, private_tokens))
        require(doc.get("declared_total_scored_events") == sum(r["scored_event_count"] for r in report["run_checks"]) == 4,
                "TOTAL_EVENT_COUNT_MISMATCH")
        manifests = doc.get("safe_bundle_manifests")
        require(isinstance(manifests, list), "EXPLICIT_SAFE_BUNDLE_SCOPE_REQUIRED")
        if not manifests:
            require(doc.get("safe_bundle_materialization") == "NOT_MATERIALIZED"
                    and all(r["run_materialization_status"] == "DECLARED_NOT_RENDERED"
                            and r["run_rendered"] is False for r in report["run_checks"]),
                    "SAFE_BUNDLE_SCOPE_UNRESOLVED")
            report["safe_bundle_checks"].append({"status": "NOT_RUN", "reason": "MISSING_NOT_MATERIALIZED",
                                                "privacy_verified": False})
        for reference in manifests:
            manifest = json_object(read_ref(root, reference))
            require(not any(token in text.casefold() for text in _strings(manifest) for token in private_tokens),
                    "PRIVATE_SCRIPT_IN_SAFE_BUNDLE: " + reference["path"])
            report["safe_bundle_checks"].append({"path": reference["path"], "status": "PASS", "privacy_verified": True})
        report.update(ok=True, candidate_status="PASS", freeze_file_sha256=sha(raw))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        report["errors"].append(str(exc))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--expected-freeze-sha256")
    parser.add_argument("--root", default=ROOT, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = check_freeze(args.freeze, root=args.root, expected_freeze_sha256=args.expected_freeze_sha256)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(text)
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

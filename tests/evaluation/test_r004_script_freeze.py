"""評分端；與推論隔離。SYNTHETIC freeze inputs, no original assets or GT bytes."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[2] / "scripts/check_r004_script_freeze.py"
spec = importlib.util.spec_from_file_location("script_freeze_check", CHECKER)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def write_ref(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}


def update_ref(root, row, key, change):
    ref = row[key]
    data = json.loads((root / ref["path"]).read_bytes())
    change(data)
    row[key] = write_ref(root, ref["path"], data)


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path / "SYNTHETIC"
    root.mkdir()
    catalog, source = "a" * 64, "b" * 64
    camera_ids = ["CAM_EXT_CAR", "CAM_EXT_CLEAR", "CAM_W1", "CAM_W2", "CAM_BRANCH", "CAM_WIDE", "CAM_R101_IN"]
    pins = {"source_sha256": source, "catalog_sha256": catalog,
            "camera_graph": write_ref(root, "SYNTHETIC-camera.json", {"camera_catalog_sha256": catalog}),
            "region_graph": write_ref(root, "SYNTHETIC-region.json", {"SYNTHETIC": True}),
            "tracking_scope": write_ref(root, "SYNTHETIC-scope.json", {"tracking_camera_ids": camera_ids})}
    doc = {"status": "PROPOSED", "production_ready": False, "freeze_approval": "PENDING_USER", "approval_ref": None,
           "source_pins": pins, "runs": [], "declared_total_scored_events": 4,
           "safe_bundle_manifests": [], "safe_bundle_materialization": "NOT_MATERIALIZED"}
    for name, duration, cameras, scheduled in [
        ("A4-1", 50_000_000, ["CAM_ENTRY", "CAM_EXT_CAR", "CAM_EXT_CLEAR", "CAM_W1"],
         [("A4-c1", "SWITCH", 8_000_000, 11_000_000, ["CAM_W1"]),
          ("A4-n1", "NO_SWITCH", 16_000_000, None, []),
          ("A4-e", "SWITCH", 26_000_000, 29_000_000, ["CAM_EXT_CAR", "CAM_EXT_CLEAR"]),
          ("A4-c2", "SWITCH", 36_000_000, 39_000_000, ["CAM_W1"])]),
        ("B4-1", 42_000_000, ["CAM_W1", "CAM_W2", "CAM_BRANCH", "CAM_WIDE", "CAM_R101_IN"],
         [("B4-n1", "NO_SWITCH", 4_000_000, None, []),
          ("B4-b", "SWITCH", 11_000_000, 14_000_000, ["CAM_BRANCH", "CAM_WIDE"]),
          ("B4-d", "SWITCH", 21_000_000, 24_000_000, ["CAM_W1", "CAM_W2"]),
          ("B4-e", "SWITCH", 30_000_000, 32_000_000, ["CAM_R101_IN"])])]:
        expected = m.SCENARIOS[name]
        run_id, clock_id = "SYNTHETIC-" + name, "SYNTHETIC-clock-" + name
        query = [0, duration - 2_000_000]
        context = {"run_id": run_id, "source_duration_us": duration, "fps": 5,
                   "sample_interval_us": 200_000, "sample_count_per_camera": duration // 200_000,
                   "query_source_range_us": query}
        events = [{"event_id": eid, "action": action, "t_x_us": tx, "t_n_us": tn, "allowed_camera_ids": cams}
                  for eid, action, tx, tn, cams in scheduled]
        for event in events[2:]:
            event["scoring_status"] = "NONSCORING_PENDING_VERIFICATION" if event["event_id"] == expected["d96_event"] else "NONSCORING"
        plan = {"schema_version": "q5-script-plan.v1", "plan_id": "SYNTHETIC-" + name,
                "status": "PLANNED", "run_id": run_id, "clock_id": clock_id,
                "source_duration_us": duration, "query_range_us": query,
                "parameters": {"index_interval_us": 200_000, "link_max_gap_us": 600_000,
                               "research_interval_us": 1_000_000, "search_window_us": 6_000_000},
                "events": events[:2], "unscored_events": events[2:]}
        cues = [{"card_event_id": e["event_id"], **({"planned_time_us": e["t_x_us"]} if e["action"] == "NO_SWITCH"
                else {"planned_leave_cue_us": e["t_x_us"], "planned_arrive_cue_us": e["t_n_us"]})} for e in events]
        producer = {"SYNTHETIC": True, "scenario": name, "status": "UNFROZEN_DRAFT_NOT_EXECUTABLE",
                    "producer_execution_enabled": False, "freeze_sha256": None, "approval_ref": None,
                    "declared_run_context": context, "render_camera_ids": cameras,
                    "runtime_seed_intent": {"camera_id": "CAM_EXT_CLEAR" if name == "A4-1" else "CAM_W2"},
                    "planning_cues": cues,
                    "planning_waypoints": [{"planned_source_time_us": t, "foot_anchor_world_m": [0, 0, 0]}
                                           for t in [0, 111_111, duration]]}
        row = {"scenario": name, "source_duration_us": duration, "fps": 5, "sample_interval_us": 200_000,
               "producer_script": write_ref(root, name + "-SYNTHETIC-producer.json", producer),
               "adapter_plan": write_ref(root, name + "-SYNTHETIC-plan.json", plan),
               "clock": write_ref(root, name + "-SYNTHETIC-clock.json", {"clock_id": clock_id, "run_id": run_id,
                   "source_duration_us": duration, "mapping_kind": "DECLARED_DEMO_CLOCK", "timezone": "Asia/Taipei"}),
               "run_declaration": write_ref(root, name + "-SYNTHETIC-run.json", {"run_id": run_id, "clock_id": clock_id,
                   "source_duration_us": duration, "source_sha256": source, "camera_catalog_sha256": catalog,
                   "camera_ids": cameras, "query_source_range_us": query, "rendered": False, "status": "DECLARED_NOT_RENDERED"}),
               "scored_event_ids": sorted(expected["scored"]), "unscored_event_ids": sorted(expected["unscored"]),
               "declared_scored_event_count": 2, "declared_planned_search_count": 3,
               "auto_switch_candidate_camera_ids": sorted(set(cameras) & set(camera_ids)),
               "d96_verification": {"event_id": expected["d96_event"], "verdict": "UNKNOWN", "scoring_enabled": False,
                   "verification_ref": {"pr": "SYNTHETIC", "head": "c" * 40,
                       "evidence_file": write_ref(root, name + "-SYNTHETIC-evidence.json", {"SYNTHETIC": True, "verdict": "UNKNOWN"})}}}
        windows, errors = m.derive_windows(plan)
        assert not errors
        row["derived_scored_decision_windows"] = [
            {"event_id": e["event_id"], "range_us": e["decision_window_us"]} for e in windows]
        doc["runs"].append(row)
    path = root / "SYNTHETIC-freeze.json"
    return root, path, doc


def run(candidate):
    root, path, doc = candidate
    path.write_text(json.dumps(doc))
    return m.check_freeze(path, root=root)


def test_candidate_pass_is_not_approval_or_safe_bundle_pass(candidate):
    report = run(candidate)
    assert report["ok"] and report["candidate_status"] == "PASS"
    assert report["production_ready"] is False and report["freeze_approval"] == "PENDING_USER"
    assert report["safe_bundle_checks"] == [{"status": "NOT_RUN", "reason": "MISSING_NOT_MATERIALIZED", "privacy_verified": False}]
    assert [r["scored_event_count"] for r in report["run_checks"]] == [2, 2]
    assert [r["planned_search_count"] for r in report["run_checks"]] == [3, 3]


def test_subframe_control_points_are_preserved_but_scoring_anchors_are_on_grid(candidate):
    assert run(candidate)["ok"]
    root, _, doc = candidate
    update_ref(root, doc["runs"][0], "adapter_plan", lambda p: p["events"][0].update(t_x_us=8_000_001))
    assert "EVENT_TIME_OUTSIDE_RUN_OR_GRID" in run(candidate)["errors"][0]


@pytest.mark.parametrize("mutation,needle", [
    (lambda d: d.update(source_duration_us=30_000_000), "DURATION_MISMATCH"),
    (lambda d: d.update(fps=6), "FIVE_FPS_GRID_REQUIRED"),
    (lambda d: d.update(declared_scored_event_count=3), "DECLARED_EVENT_COUNT_MISMATCH"),
    (lambda d: d.update(declared_planned_search_count=2), "SEARCH_BUDGET_MISMATCH"),
    (lambda d: d["auto_switch_candidate_camera_ids"].append("CAM_ENTRY"), "D74_AUTO_SWITCH_SCOPE_INVALID"),
    (lambda d: d["d96_verification"].update(scoring_enabled=True), "D96_FAIL_CLOSED_REQUIRED"),
    (lambda d: d["d96_verification"].pop("verification_ref"), "D96_VERIFICATION_REF_REQUIRED"),
    (lambda d: d["derived_scored_decision_windows"][0]["range_us"].__setitem__(0, 0), "DECLARED_WINDOWS_MISMATCH"),
])
def test_candidate_semantic_mutations_fail(candidate, mutation, needle):
    mutation(candidate[2]["runs"][0])
    report = run(candidate)
    assert not report["ok"] and needle in report["errors"][0]


@pytest.mark.parametrize("key", ["producer_script", "adapter_plan", "clock", "run_declaration"])
def test_one_raw_byte_change_fails(candidate, key):
    root, _, doc = candidate
    ref = doc["runs"][0][key]
    path = root / ref["path"]
    path.write_bytes(path.read_bytes() + b" ")
    assert "FILE_HASH_MISMATCH" in run(candidate)["errors"][0]


def test_raw_freeze_pin_detects_whitespace_byte_change(candidate):
    root, path, _ = candidate
    assert run(candidate)["ok"]
    expected = m.sha(path.read_bytes())
    path.write_bytes(path.read_bytes() + b" ")
    report = m.check_freeze(path, root=root, expected_freeze_sha256=expected)
    assert report["errors"] == ["FREEZE_FILE_HASH_MISMATCH"]


@pytest.mark.parametrize("key,value,needle", [
    ("clock", 30_000_000, "DURATION_MISMATCH"),
    ("run_declaration", 30_000_000, "DURATION_MISMATCH"),
])
def test_clock_or_run_duration_mismatch_fails_even_with_fresh_file_hash(candidate, key, value, needle):
    root, _, doc = candidate
    update_ref(root, doc["runs"][0], key, lambda p: p.update(source_duration_us=value))
    assert needle in run(candidate)["errors"][0]


def test_restore_pending_event_is_rejected(candidate):
    root, _, doc = candidate
    def restore(plan):
        event = plan["unscored_events"].pop()
        event.pop("scoring_status")
        plan["events"].append(event)
    update_ref(root, doc["runs"][0], "adapter_plan", restore)
    assert "D92_D96_SCORING_SPLIT_MISMATCH" in run(candidate)["errors"][0]


def test_run_end_event_time_is_rejected(candidate):
    root, _, doc = candidate
    update_ref(root, doc["runs"][0], "adapter_plan", lambda p: p["unscored_events"][0].update(t_n_us=50_000_000))
    assert "EVENT_TIME_OUTSIDE_RUN_OR_GRID" in run(candidate)["errors"][0]


def test_adaptor_d79_validation_cannot_be_bypassed(candidate):
    root, _, doc = candidate
    update_ref(root, doc["runs"][0], "adapter_plan", lambda p: p["events"][0].update(t_n_us=20_000_000))
    update_ref(root, doc["runs"][0], "producer_script", lambda p: p["planning_cues"][0].update(planned_arrive_cue_us=20_000_000))
    assert "ADAPTER_PRECHECK_FAILED" in run(candidate)["errors"][0]


def test_explicit_nonoverlap_check(candidate, monkeypatch):
    original = m.derive_windows
    def bad_windows(plan):
        windows, errors = original(plan)
        windows = deepcopy(windows)
        windows[1]["decision_window_us"][0] = windows[0]["decision_window_us"][1] - 1
        return windows, errors
    monkeypatch.setattr(m, "derive_windows", bad_windows)
    assert "D79_WINDOWS_OVERLAP" in run(candidate)["errors"][0]


@pytest.mark.parametrize("leak", ["producer_filename", "producer_hash", "plan_filename", "plan_hash"])
def test_private_script_names_or_hashes_are_rejected_inside_safe_manifests(candidate, leak):
    root, _, doc = candidate
    key = "producer_script" if leak.startswith("producer") else "adapter_plan"
    ref = doc["runs"][0][key]
    token = Path(ref["path"]).name if leak.endswith("filename") else ref["sha256"].upper()
    doc["safe_bundle_manifests"] = [write_ref(root, "SYNTHETIC-safe.json", {"nested": [{"file": token}]})]
    assert "PRIVATE_SCRIPT_IN_SAFE_BUNDLE" in run(candidate)["errors"][0]


def test_clean_synthetic_safe_manifest_can_be_checked(candidate):
    root, _, doc = candidate
    doc["safe_bundle_manifests"] = [write_ref(root, "SYNTHETIC-safe.json", {"schema_version": "SYNTHETIC", "frames": []})]
    report = run(candidate)
    assert report["ok"] and report["safe_bundle_checks"][0]["status"] == "PASS"
    assert report["production_ready"] is False


def test_unresolved_safe_bundle_scope_is_not_silently_empty(candidate):
    doc = candidate[2]
    doc.pop("safe_bundle_manifests")
    assert "EXPLICIT_SAFE_BUNDLE_SCOPE_REQUIRED" in run(candidate)["errors"][0]


def test_not_rendered_declaration_is_required_for_unmaterialized_scope(candidate):
    root, _, doc = candidate
    update_ref(root, doc["runs"][0], "run_declaration", lambda p: p.update(rendered=True))
    assert "SAFE_BUNDLE_SCOPE_UNRESOLVED" in run(candidate)["errors"][0]


def test_forged_approved_candidate_is_rejected(candidate):
    candidate[2].update(status="APPROVED", production_ready=True)
    assert "CANDIDATE_MUST_NOT_DECLARE_APPROVAL" in run(candidate)["errors"][0]


def test_symlink_input_escape_fails(candidate, tmp_path):
    root, _, doc = candidate
    ref = doc["runs"][0]["clock"]
    original = root / ref["path"]
    outside = tmp_path / "outside.json"
    outside.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(outside)
    assert "REGULAR_PINNED_FILE_REQUIRED" in run(candidate)["errors"][0]


def test_cli_produces_candidate_only_report(candidate, tmp_path, capsys):
    root, path, _ = candidate
    assert run(candidate)["ok"]
    report = tmp_path / "report.json"
    assert m.main(["--freeze", str(path), "--root", str(root), "--report", str(report)]) == 0
    assert json.loads(report.read_bytes())["production_ready"] is False
    assert '"status": "NOT_RUN"' in capsys.readouterr().out

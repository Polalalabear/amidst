"""Focused safety/precision checks for opt-in offline proposal analysis."""
import copy
import importlib.util
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).parents[2] / "scripts/analyze_l2_detection_options.py"
SPEC = importlib.util.spec_from_file_location("l2_detection_options", PATH)
options = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = options
SPEC.loader.exec_module(options)


def diagnosis():
    return {
        "thresholds": dict(options.BASELINE), "index_score_floor": 0.3,
        "rows": [
            {"frame_ref": "A:1", "person_scores": [], "geometry": [],
             "category": "NO_STORED_PERSON_AT_INDEX_FLOOR"},
            {"frame_ref": "B:2", "person_scores": [0.384, 0.362], "geometry": [],
             "category": "PERSON_BELOW_LINK_SCORE"},
            {"frame_ref": "B:3", "person_scores": [0.5],
             "category": "LINK_GEOMETRY_REJECTION", "geometry": [{
                 "last": {"iou": 0.249997614, "center_distance_diag_ratio": 0.2},
                 "reference": {"iou": 0.239, "center_distance_diag_ratio": 0.2}}]},
        ],
    }


def test_default_preserves_all_gates_and_input():
    source = diagnosis()
    before = copy.deepcopy(source)
    result = options.analyze(source)
    assert result["changed_gate_frame_count"] == 0
    assert result["runtime_changed"] is False
    assert source == before


def test_score_eligibility_is_not_recovery_or_confirmed_ambiguity():
    result = options.analyze(diagnosis(), options.Options(link_min_score=0.35))
    assert result["newly_score_eligible_frame_count"] == 1
    assert result["newly_score_eligible_observation_count"] == 2
    assert result["multiple_score_eligible_person_frames"] == ["B:2"]
    assert result["multiple_score_eligible_is_confirmed_ambiguity"] is False
    assert result["recovered_links"] is None
    assert result["geometry_for_newly_score_eligible_frames"].startswith("MISSING")


def test_iou_threshold_uses_full_precision_without_rounding():
    assert options.analyze(diagnosis(), options.Options(link_iou_min=0.25))[
        "newly_passing_geometry_gate_frame_count"] == 0
    assert options.analyze(diagnosis(), options.Options(link_iou_min=0.24))[
        "newly_passing_geometry_gate_frames"] == ["B:3"]


def test_center_guard_is_not_bypassed_by_lower_iou():
    source = diagnosis()
    source["rows"][2]["geometry"][0]["last"]["center_distance_diag_ratio"] = 0.6
    source["rows"][2]["geometry"][0]["reference"]["center_distance_diag_ratio"] = 0.6
    assert options.analyze(source, options.Options(link_iou_min=0.1))[
        "newly_passing_geometry_gate_frame_count"] == 0


def test_missing_raw_never_becomes_zero_score_or_recovery():
    result = options.analyze(diagnosis(), options.Options(audit_index_floor=0.1))
    assert result["floor_censored_person_frame_count"] == 1
    assert result["low_floor_recovered_person_frames"] is None
    assert result["low_floor_analysis_status"] == "INCOMPLETE_RAW_BELOW_FLOOR_MISSING"
    assert result["changed_gate_frame_count"] == 0


@pytest.mark.parametrize("value", [float("nan"), -0.1, 0.29, 0.41, True])
def test_invalid_or_out_of_scope_score_is_rejected(value):
    with pytest.raises(ValueError):
        options.analyze(diagnosis(), options.Options(link_min_score=value))


def test_changed_historical_context_rejected():
    source = diagnosis()
    source["thresholds"]["link_max_gap_us"] = 800_000
    with pytest.raises(ValueError, match="context changed"):
        options.analyze(source)


def test_duplicate_frames_and_false_category_rejected():
    source = diagnosis()
    source["rows"].append(copy.deepcopy(source["rows"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        options.analyze(source)
    source = diagnosis()
    source["rows"][1]["category"] = "LINK_GEOMETRY_REJECTION"
    with pytest.raises(ValueError, match="disagree"):
        options.analyze(source)


def test_unpinned_source_rejected(tmp_path):
    source = tmp_path / "wrong.json"
    source.write_text("{}")
    with pytest.raises(ValueError, match="pin mismatch"):
        options.load_diagnosis(source.resolve())

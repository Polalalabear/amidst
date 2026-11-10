"""Frozen report separates absent frames and D17 endpoint eligibility."""

from types import SimpleNamespace

import freeze_person_hybrid_contact as report


def estimate():
    return {
        "observation_ref": "o",
        "camera_id": "CAM_REAR",
        "timestamp_s": 8.6,
        "status": "READY",
        "reason": None,
        "estimate_kind": "SEGMENT",
        "basis": "FOOT_RAY_PIXEL_BAND",
        "image_anchor_px": [11, 2],
        "contact_quality": {"reasons": ["LOW_INCIDENCE"]},
        "segment": {"near_m": [3, 4, 0], "far_m": [6, 8, 0], "length_m": 5},
        "constraints_applied": [{"kind": "OCCLUDER_BEHIND", "effect": "NOT_APPLICABLE"}],
        "diagnostics": {"raw_interval_length_m": 5},
    }


def test_frame_table_preserves_empty_frames_and_r1_eligibility():
    scene = SimpleNamespace(
        index=SimpleNamespace(
            observations=[
                {"observation_ref": "o", "frame_ref": "f1", "bbox_xyxy": [10, 2, 13, 20]}
            ],
            frame_records=[
                {"frame_ref": "f1", "camera_id": "CAM_REAR", "timestamp": 8.6},
                {"frame_ref": "f2", "camera_id": "CAM_REAR", "timestamp": 8.8},
            ],
        )
    )
    rows = report.frame_table(scene, {"o": estimate()})
    assert rows[0]["status"] == "SEGMENT" and rows[0]["head_anchor_px"] == [11, 2]
    assert rows[0]["k1_endpoint"]["eligible"] is True
    assert rows[1]["status"] == "NO_OBSERVATION" and rows[1]["observation_ref"] is None
    assert rows[1]["interval_length_m"] is None and rows[1]["head_anchor_px"] is None


def test_summary_counts_observations_only_and_distance_is_calibrated_interval():
    rows = [
        {"camera": "CAM_REAR", "timestamp_s": 8.6, "observation_ref": "o"},
        {"camera": "CAM_REAR", "timestamp_s": 8.8, "observation_ref": None},
    ]
    camera = {
        "camera_id": "CAM_REAR",
        "calibration": {
            "camera_to_world": [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 3.5],
                [0, 0, 0, 1],
            ]
        },
    }
    result = report.summary({"o": estimate()}, rows, [camera], 0.5)
    assert result["observation_count"] == 1 and result["empty_frame_slots"] == 1
    assert (
        result["counts"] == {"POINT": 0, "SEGMENT": 1, "UNKNOWN": 0}
        and result["k1_eligible_count"] == 1
    )
    geometry = result["camera_geometry"]["CAM_REAR"]
    assert geometry["height_above_floor_m"] == 3.0
    record = geometry["timestamp_8_6_calibrated_interval"][0]
    assert record["horizontal_distance_to_interval_m"] == [5, 10]
    assert record["unique_actual_target_distance_m"] == "UNKNOWN_NO_GT_USED"

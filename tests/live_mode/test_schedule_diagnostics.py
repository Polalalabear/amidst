"""Missing observations retain uncertainty rather than becoming detector failures."""

from scripts.live_mode.joint_schedule_diagnostics import classify, entry_diagnostics, paired_times


def test_missing_camera_is_unknown_and_observed_target_like_projection_is_tracking_issue():
    row = {"status": "LOST", "tVisible": ["A", "B"], "red_actors": []}
    response = {"dets": {"A": []}}
    assert (
        classify(row, response, ["A", "B"])["attribution"]
        == "SKIPPED_VISIBLE_CAMERA_COUNTERFACTUAL_UNKNOWN"
    )
    assert (
        classify(row, {"dets": {"A": [], "B": []}}, ["A", "B"])["attribution"]
        == "DETECTOR_COLOR_OR_PROJECTION_TARGET_NOT_OBSERVED"
    )
    assert (
        classify(dict(row, red_actors=["T"]), response, ["A", "B"])["attribution"]
        == "TRACKER_DESPITE_TARGET_LIKE_RED_PROJECTION"
    )


def test_nearest_time_description_never_reuses_source_tick_or_extrapolates():
    rows = [
        {"i": i, "tSec": t, "status": "LOST", "red_actors": []} for i, t in enumerate([0.0, 1.0])
    ]
    other = [dict(rows[0], tSec=t) for t in [0.01, 0.02, 2.0]]
    paired = paired_times(rows, other)
    assert len(paired["pairs"]) == 1
    assert paired["unpaired_all"] == 1
    assert paired["unpaired_adaptive"] == 2


def test_initial_entry_excluded_and_failed_reentry_censored_even_with_target_detections():
    raw = {
        "ticks": [
            {"tick": i, "t_capture": i * 100, "gt_visible": v}
            for i, v in enumerate([["CAM_ENTRY"], [], ["CAM_ENTRY"]])
        ],
        "infer": [
            {
                "t_resp": i * 100 + 10,
                "tracking": {"est_xy": [10, 0]},
                "gt_xy": [0, 0],
                "dets": {"CAM_ENTRY": [{"color": "red", "est_xy": [0, 0]}]},
            }
            for i in range(3)
        ],
    }
    rows = [
        {"tSec": i, "status": s} for i, s in enumerate(["ON_TARGET", "TARGET_NOT_VISIBLE", "LOST"])
    ]
    events = entry_diagnostics(raw, rows)
    assert len(events) == 1
    assert events[0]["target_lock_ms"] is None and events[0]["censored"]
    assert events[0]["episode"][0]["nearest_target_candidate_to_previous_est_m"] == 10
    rows[2]["status"] = "ON_TARGET"
    measured = entry_diagnostics(raw, rows)[0]
    assert not measured["censored"] and measured["target_lock_ms"] == 10

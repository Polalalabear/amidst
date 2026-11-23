"""Focused boundary and temporal tests for the independent F4 caller."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verification/f4_independent_recompute.py"
spec = importlib.util.spec_from_file_location("cx_f4_caller", SCRIPT)
caller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(caller)
SCORER = SCRIPT.parents[2] / "src/amidst/evaluation/e3_scoring.py"


def test_frozen_scorer_rejects_changed_bytes(tmp_path):
    changed = tmp_path / "scorer.py"
    changed.write_bytes(SCORER.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="FROZEN_SCORER_SHA_MISMATCH"):
        caller.load_scorer(changed)


def test_source_escape_rejected(tmp_path):
    with pytest.raises(ValueError, match="SOURCE_PATH_ESCAPE"):
        caller.safe_path(tmp_path, "../private.json")


def test_reappearance_uses_pre_return_ranking_and_counts_empty_hint():
    sc = caller.load_scorer(SCORER)
    # At the return, post-observation ranking switches to the right camera.
    # It must not rescue the empty pre-return search order.
    gt = {
        "ticks": [
            {
                "tick": i,
                "actors": [
                    {
                        "id": "T",
                        "present": True,
                        "xy": [0, 0],
                        "gt_visible": ["RIGHT"],
                        "gt_boxes": {"RIGHT": [0, 0, 20, 20]},
                    }
                ],
            }
            for i in range(3)
        ]
    }
    run = {
        "tick_us": 200_000,
        "size": [320, 180],
        "identity": "UNCONFIRMED",
        "rows": [
            {
                "tick": i,
                "tracking": {
                    "state": "TRACKING",
                    "active_cam": "RIGHT",
                    "lost_ticks": 0,
                    "est_xy": [0, 0],
                    "box": [1, 1, 19, 19],
                },
                "ranking": [] if i == 0 else ["RIGHT"],
            }
            for i in range(3)
        ],
    }
    case = {
        "duration_s": 0.6,
        "cameras": ["RIGHT", "OTHER"],
        "decision_points": [
            {"type": "REAPPEAR", "tick": 1, "evaluation_window_us": [200_000, 600_000]}
        ],
    }
    result = caller.summarize_run(sc, run, gt, case)
    assert result["decision_points"] == [True]
    assert result["ranking_points"][0]["ranked"] == []
    assert result["ranking_points"][0]["top1"] is False
    summary = caller.average_runs(sc, [result, result, result])
    assert (summary["rank_n"], summary["no_ranking"], summary["top1"]) == (3, 3, 0)


def test_missing_gt_tick_stops_instead_of_changing_denominator():
    sc = caller.load_scorer(SCORER)
    run = {
        "tick_us": 200_000,
        "size": [320, 180],
        "identity": "UNCONFIRMED",
        "rows": [{"tick": 0, "tracking": {}, "ranking": []}],
    }
    with pytest.raises(AssertionError, match="GT_ALIGNMENT_MISSING"):
        caller.summarize_run(sc, run, {"ticks": []}, {"duration_s": 0.2})

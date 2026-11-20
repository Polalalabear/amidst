"""Replay safety, deterministic receipts and the optional LIVE advisor shortlist."""

import inspect
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from amidst.live_mode.advisor import LiveDecider
from amidst.live_mode.relock import RelockConfig

SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts/live_mode")
sys.path.insert(0, SCRIPTS)
try:
    from replay_advisor import PoolRecorder, replay_pools, score_questions
    from replay_relock import episodes, observation_records, recovery_comparison, replay_safe
finally:
    sys.path.remove(SCRIPTS)


def raw_recording():
    return {
        "ticks": [{"tick": i, "t_capture": i * 500, "gt_visible": ["cam"]} for i in range(4)],
        "infer": [
            {
                "gt_xy": [99, 99],
                "dets": {
                    "cam": [
                        {
                            "color": "red",
                            "bbox": [2 * i, 0, 2 * i + 10, 20],
                            "score": 0.9,
                            "red_ratio": 0.8,
                            "blue_ratio": 0.1,
                            "actor_id": "PRIVATE",
                            "est_xy": [99, 99],
                        }
                    ]
                },
            }
            for i in range(4)
        ],
    }


def test_replay_policy_has_no_scoring_inputs_and_is_repeatable():
    raw = raw_recording()
    records = observation_records(raw)
    projector = SimpleNamespace(ground=lambda _cam, u, _v, *_args: [u / 10, 0])
    graph = {"cameras": [{"camera_id": "cam"}], "transitions": []}
    kwargs = {
        "cameras": ["cam"],
        "size": (100, 60),
        "projector": projector,
        "graph": graph,
        "config": RelockConfig(),
    }
    first = replay_safe(records, **kwargs)
    assert first[0]["tracking"]["est_xy"] == [0.5, 0]
    assert raw["infer"][0]["dets"]["cam"][0]["est_xy"] == [99, 99]
    assert first == replay_safe(records, **kwargs)
    assert "gt" not in str(inspect.signature(replay_safe)).lower()
    assert "scenario" not in str(inspect.signature(replay_pools)).lower()
    assert all(
        set(d) == {"bbox", "score", "color", "red_ratio", "blue_ratio"}
        for record in records
        for d in record["dets"]["cam"]
    )


def test_visible_failed_episode_starts_only_after_a_correct_track():
    labels = [
        "LOST",
        "ON_TARGET",
        "WRONG_PERSON",
        "LOST",
        "TARGET_NOT_VISIBLE",
        "LOST",
        "ON_TARGET",
    ]
    assert episodes([{"status": label} for label in labels]) == [[2, 3], [5]]


def test_r5a_distinguishes_existing_and_new_wrong_recoveries_and_rejects_clock_mismatch():
    entries = [
        (
            "one",
            Path("one.t1raw.json"),
            {"ticks": [{"tick": i, "t_capture": i * 500} for i in range(3)]},
        )
    ]
    rows = [
        {
            "i": i,
            "t_capture": i * 500,
            "state": state,
            "matched": state == "TRACKING",
            "following": who,
            "status": "WRONG_PERSON" if who else "LOST",
            "events": ["REACQUIRE"] if i == 2 else [],
        }
        for i, (state, who) in enumerate(
            [("TRACKING", "A"), ("NEEDS_CONFIRM", None), ("TRACKING", "A")]
        )
    ]
    trace = [
        {
            "tracking": {
                "state": row["state"],
                "events": [
                    {
                        "type": "REACQUIRE",
                        "detail": {"mode": "short_gate", "unseen_s": 1, "dist_m": 0.5},
                    }
                ]
                if i == 2
                else [],
            }
        }
        for i, row in enumerate(rows)
    ]
    result = recovery_comparison(entries, [trace], {"one": rows}, {"one": rows})
    assert result["new_wrong"] == 0 and result["wrong_before_loss"] == 1
    assert (
        result["relock_counts"] == result["main_counts"] == {"correct": 0, "wrong": 1, "unknown": 0}
    )
    event = result["events"][0]
    assert event["previous_state"] == "NEEDS_CONFIRM"
    assert event["last_match_before_loss"]["i"] == 0
    main = [dict(row) for row in rows]
    main[2]["following"] = "T"
    assert recovery_comparison(entries, [trace], {"one": rows}, {"one": main})["new_wrong"] == 1
    main[2]["t_capture"] += 1
    with pytest.raises(ValueError, match="MAIN_COMPARISON_CLOCK"):
        recovery_comparison(entries, [trace], {"one": rows}, {"one": main})


def test_pool_report_scores_only_after_asks_and_uses_one_metre_oracle():
    recording = raw_recording()
    recording["infer"][2]["gt_xy"] = [0, 0]
    entries = [("session", Path("session.t1raw.json"), recording)]
    trace = [{}, {}, {"dets": {"cam": [{"color": "red", "est_xy": [0, 0]}]}}, {}]

    def receipt(pool):
        ask = {"tick": 2, "cam": "cam", "pool_xy": pool}
        return score_questions(entries, [trace], [[ask]], oracle_m=1)[0]

    assert receipt([[2, 0]])["pool_miss"] is True
    within_pool_distance = receipt([[1.3, 0]])
    assert within_pool_distance["pool_miss"] is False
    assert within_pool_distance["evaluation_oracle_choice"] == 0
    assert receipt([[4, 0], [0.7, 0]])["evaluation_oracle_choice"] == 2


def test_decider_shortlist_contains_the_outside_candidate_when_prediction_enabled():
    detections = []
    people_now = []
    for pid, x in ((1, 2.0), (2, 4.7)):
        det = {
            "bbox": [x * 10, 0, x * 10 + 10, 30],
            "score": 0.9,
            "color": "red",
            "est_xy": [x, 0],
        }
        detections.append(det)
        people_now.append({"pid": pid, "dets": [("cam", det)], "xy": [x, 0]})

    def run(horizon):
        people = SimpleNamespace(
            tracks={p["pid"]: p for p in people_now},
            velocity=lambda pid: (1.2, 0) if pid == 1 else None,
            update=lambda *_: people_now,
        )
        recorder = PoolRecorder(people, delay_s=3.5)
        recorder.set_reference(b"reference")
        recorder.now = 1.0
        decider = LiveDecider("review", recorder, people, gate_m=4, predict_horizon_s=horizon)
        decider.prev_est, decider.target_pid, decider.target_seen_s = [0, 0], 1, 0.0
        tr = {
            "state": "TRACKING",
            "active_cam": "cam",
            "est_xy": [2, 0],
            "lost_ticks": 0,
            "events": [],
        }
        output = decider.step(
            0, 1, None, tr, {"cam": detections}, {"cam": Image.new("RGB", (100, 60))}
        )
        return output, recorder.questions

    baseline, no_asks = run(0)
    assert no_asks == [] and baseline["events"] == []
    predicted, asks = run(1)
    assert len(asks) == 1 and any(math.isclose(xy[0], 4.7) for xy in asks[0]["pool_xy"])
    assert predicted["events"][0]["detail"] == {"kind": "SILENT_PICK", "candidates": 2}
    assert set(predicted) == set(baseline)

"""Parameterized rule tracking and pixel-derived red/blue candidate grouping."""
from types import SimpleNamespace

import pytest

from amidst.live_mode.candidates import group_candidates
from amidst.live_mode.tracker import Tracker


@pytest.mark.parametrize(("target", "other"), [("red", "blue"), ("blue", "red")])
def test_rule_tracker_acquires_follows_loses_and_switches_for_either_color(target, other):
    projector = SimpleNamespace(ground=lambda _cam, u, v, *_: [u / 10, v / 10])
    tracker = Tracker(projector, hold_ticks=1, lost_after=2, target_color=target)
    initial = {
        "a": [{"color": target, "score": 0.8, "bbox": [0, 0, 10, 20]}],
        "b": [{"color": other, "score": 0.9, "bbox": [50, 0, 60, 20]}],
    }
    first = tracker.update(0, initial, (100, 50))
    assert first["est_xy"] == [0.5, 2] and first["active_cam"] == "a"
    assert [event["type"] for event in first["events"]] == ["ACQUIRE"]
    assert initial["b"][0]["est_xy"] == [5.5, 2]
    next_ = tracker.update(1, {
        "b": [{"color": target, "score": 0.9, "bbox": [2, 0, 12, 20]}],
        "a": [{"color": other, "score": 0.99, "bbox": [0, 0, 10, 20]}],
    }, (100, 50))
    assert next_["est_xy"] == [0.7, 2] and next_["active_cam"] == "b"
    assert [event["type"] for event in next_["events"]] == ["SWITCH"]
    for tick in (2, 3):
        out = tracker.update(tick, {"a": initial["b"]}, (100, 50))
        assert out["lost_ticks"] == tick - 1
    assert out["state"] == "LOST" and [event["type"] for event in out["events"]] == ["LOST"]
    out = tracker.update(4, initial, (100, 50))
    assert out["state"] == "TRACKING" and out["lost_ticks"] == 0
    assert [event["type"] for event in out["events"]] == ["REACQUIRE"]


def test_group_uses_highest_score_at_less_than_1_5_and_never_mixes_colors():
    def det(color, x, score):
        return {"color": color, "score": score, "est_xy": [x, 0], "bbox": [0, 0, 5, 5]}

    groups = group_candidates({
        "a": [det("red", 0, 0.7), det("blue", 0.2, 0.8), det("red", 2.9, 0.6)],
        "b": [det("red", 1.4, 0.9), det("red", float("nan"), 0.91), det("blue", 5, float("inf"))],
    })
    assert [(group["color"], group["cam"], group["est_xy"]) for group in groups] == [
        ("red", "b", [1.4, 0]), ("blue", "a", [0.2, 0]), ("red", "a", [2.9, 0]),
    ]


@pytest.mark.parametrize("invalid_projection", [None, [float("nan"), 4], [4, float("inf")]])
def test_missing_or_nonfinite_projection_does_not_seed(invalid_projection):
    tracker = Tracker(SimpleNamespace(ground=lambda *_: invalid_projection), target_color="blue")
    data = {"a": [{"color": "blue", "score": 0.7, "bbox": [0, 0, 10, 20]}]}
    tracking = tracker.update(0, data, (100, 50))
    assert tracking["est_xy"] is None and data["a"][0]["est_xy"] is None
    assert group_candidates(data) == []

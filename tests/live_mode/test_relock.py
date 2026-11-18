"""Synthetic pixel observations for the pure relock state machine and prediction."""

from types import SimpleNamespace

import pytest

from amidst.live_mode.people import PeopleTracker
from amidst.live_mode.relock import RelockConfig, distance, reference_points
from amidst.live_mode.tracker import Tracker


def det(x, red=0.8, blue=0.05, **other):
    return {
        "bbox": [x * 10, 0, x * 10, 40],
        "score": 0.9,
        "color": "red",
        "red_ratio": red,
        "blue_ratio": blue,
        **other,
    }


def make(**cfg):
    projector = SimpleNamespace(ground=lambda _cam, u, _v, *_size: [u / 10, 0])
    return Tracker(
        projector, gate_m=4.0, lost_after=3, relock=RelockConfig(ref_ticks=1, **cfg)
    )


def step(tracker, tick, t_s, *observations, cam="left"):
    return tracker.update(tick, {cam: list(observations)}, (1280, 720), t_s)


def event(out, kind):
    return next(item["detail"] for item in out["events"] if item["type"] == kind)


def test_r1_extra_private_fields_have_identical_outputs():
    clean, foreign = make(t_short_s=1), make(t_short_s=1)
    for i, x in enumerate([0, None, 4.76, 4.6, None, 1]):
        allowed = () if x is None else (det(x),)
        injected = (
            ()
            if x is None
            else (
                det(
                    x,
                    actor_id="T",
                    gt_visible=["other"],
                    xy=[333, 222],
                    scenario={"tracks": []},
                ),
            )
        )
        assert step(clean, i, i, *allowed) == step(foreign, i, i, *injected)


def test_r2_short_gate_only_when_unique_after_loss():
    tracker = make(t_short_s=2)
    step(tracker, 0, 0, det(0))
    missing = step(tracker, 1, 1)
    assert missing["lost_phase"] == "short" and missing["lost_ticks"] == 1
    result = step(tracker, 2, 2, det(1))
    assert result["state"] == "TRACKING" and result["lost_ticks"] == 0
    assert event(result, "REACQUIRE") == {"mode": "short_gate", "unseen_s": 2.0, "dist_m": 1.0}

    step(tracker, 3, 3)
    result = step(tracker, 4, 4, det(0), det(3))
    assert result["state"] == "NEEDS_CONFIRM" and result["est_xy"] == [1, 0]
    assert result["lost_phase"] == "long" and result["lost_ticks"] == 2
    assert event(result, "NEEDS_CONFIRM")["reason"] == "APPEARANCE_NOT_SEPARABLE"
    assert [item["rank"] for item in result["confirm_candidates"]] == [1, 2]
    again = step(tracker, 5, 5, det(0), det(3))
    assert all(e["type"] != "NEEDS_CONFIRM" for e in again["events"])
    assert [item["type"] for item in again["events"]] == ["LOST"]


def test_r3_outside_gate_can_reacquire_with_unique_appearance():
    tr = make(t_short_s=2, v_walk_m_s=1, tau_app=0.1, margin_app=0.1)
    step(tr, 0, 0, det(0))
    step(tr, 1, 1)
    result = step(tr, 2, 2, det(4.76), cam="return")
    assert result["state"] == "TRACKING" and result["active_cam"] == "return"
    detail = event(result, "REACQUIRE")
    assert detail["mode"] == "appearance" and detail["dist_m"] == pytest.approx(4.76)
    assert detail["d_app"] == 0


def test_r3_multiple_pass_low_margin_rejected_and_beyond_radius():
    tr = make(t_short_s=1, v_walk_m_s=1, tau_app=0.12, margin_app=0.15)
    step(tr, 0, 0, det(0))
    step(tr, 1, 1)
    ambiguous = step(tr, 2, 2, det(1, red=0.88), det(3, red=0.8), det(12))
    assert ambiguous["state"] == "NEEDS_CONFIRM"
    assert event(ambiguous, "NEEDS_CONFIRM")["reason"] == "MULTIPLE_PASS"
    assert [item["est_xy"] for item in ambiguous["confirm_candidates"]] == [[3, 0], [1, 0]]
    low_margin = step(tr, 3, 3, det(1, red=0.94), det(3, red=0.8))
    assert low_margin["state"] == "NEEDS_CONFIRM"
    assert low_margin["est_xy"] == [0, 0] and low_margin["lost_ticks"] == 3
    rejected = step(tr, 4, 4, det(1, red=0.3), det(3, red=0.35))
    assert rejected["state"] == "LOST" and "confirm_candidates" not in rejected
    reacquired = step(tr, 5, 5, det(3, red=0.81))
    assert event(reacquired, "REACQUIRE")["mode"] == "appearance"


def test_r7_needs_confirm_has_no_timeout_and_can_be_resolved():
    tr = make(t_short_s=1, v_walk_m_s=0.02, tau_app=0.1, margin_app=0.1)
    step(tr, 0, 0, det(0))
    values = [step(tr, i, t)["unseen_s"] for i, t in enumerate([1, 15, 60, 599], 1)]
    assert values == [1, 15, 60, 599]
    ambiguity = step(tr, 5, 600, det(6), det(8))
    assert ambiguity["state"] == "NEEDS_CONFIRM" and ambiguity["unseen_s"] == 600
    cand_id = ambiguity["confirm_candidates"][0]["cand_id"]
    cleared = step(tr, 6, 601)
    assert cleared["state"] == "NEEDS_CONFIRM" and cleared["confirm_candidates"] == []
    with pytest.raises(ValueError, match="CONFIRM_CANDIDATE_UNKNOWN"):
        tr.confirm(cand_id, 6, 601, by="user")
    final = step(tr, 7, 602, det(6))
    assert event(final, "REACQUIRE")["mode"] == "appearance" and final["lost_ticks"] == 0


def test_user_confirmation_fixes_the_estimate_and_discards_old_reference():
    tr = make(t_short_s=1)
    step(tr, 0, 0, det(0))
    waited = step(tr, 1, 2, det(5))
    candidate = waited["confirm_candidates"][0]
    out = tr.confirm(candidate["cand_id"], 1, 2.01, by="user")
    assert out["est_xy"] == [5, 0] and out["lost_ticks"] == 0
    assert event(out, "REACQUIRE")["mode"] == "confirmed"
    assert event(out, "REACQUIRE")["by"] == "user"
    assert tr.relock.reference is None


def test_r8_unknown_parameters_use_gate_8m_and_no_automatic_appearance():
    tr = make()
    step(tr, 0, 0, det(0))
    step(tr, 1, 1)
    short = step(tr, 2, 50, det(2))
    assert event(short, "REACQUIRE")["mode"] == "short_gate"
    out = step(tr, 3, 600, det(10), det(12))
    assert [x["est_xy"] for x in out["confirm_candidates"]] == [[10, 0]]
    assert out["state"] == "NEEDS_CONFIRM"


def test_zero_short_threshold_disables_short_relock_without_breaking_continuity():
    tr = make(t_short_s=0)
    step(tr, 0, 0, det(0))
    assert step(tr, 1, 0.5, det(1))["state"] == "TRACKING"
    step(tr, 2, 1)
    assert step(tr, 3, 1.5, det(1))["state"] == "NEEDS_CONFIRM"


def test_r11_r12_prediction_only_expands_eligibility_and_caps_time():
    est = (0, 0)
    points = reference_points(est, (1.2, 0), 3, 2)
    assert points == (est, [2.4, 0])
    assert reference_points(est, None, 2, 2) == (est,)
    assert reference_points(est, (1.2, 0), 40, 2) == points
    xs = [(x / 10, 0) for x in range(-60, 110)]
    assert {p for p in xs if distance(p, (est,)) <= 4} < {
        p for p in xs if distance(p, points) <= 4
    }
    assert distance((4.7, 0), points) <= 4 < distance((4.7, 0), (est,))


def test_people_velocity_is_a_snapshot_or_none():
    people = PeopleTracker()
    (tracked,) = people.update(0, [("c", det(0), [0, 0])])
    pid = tracked["pid"]
    people.update(1, [("c", det(1), [1, 0])])
    assert people.velocity(pid) == (0.5, 0)
    people.update(4, [])
    assert people.velocity(pid) is None

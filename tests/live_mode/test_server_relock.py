"""#589 R2 server wiring: --relock off keeps the rule tracker unchanged; fallback enables the 4.5 UNKNOWN state machine. No model, network or scene truth."""
from types import SimpleNamespace

import pytest

from amidst.live_mode.server import State
from amidst.live_mode.tracker import Tracker

IMG = (320, 180)


def make(color, relock=None):
    args = SimpleNamespace(gate_m=4.0, gate_growth=0.0, max_gate=8.0)
    if relock is not None:
        args.relock = relock
    s = State.__new__(State)
    s.args, s.projector = args, SimpleNamespace(ground=lambda *_: None)
    return s._new_tracker(color)


def row(color, x):
    return {"A": [{"color": color, "bbox": [0, 0, 10, 20], "score": .9, "est_xy": [x, 0], "red_ratio": .5, "blue_ratio": .5}]}


# Fixed script: seed, brief loss, in-gate return, long loss, far return (6 m), wrong colour, in-gate return again.
SCRIPT = [(1, None, 0.5), (2, "T", 5.0), (3, "O", 1.0), (4, None, 3.0), (5, "T", 24.0), (6, "T", 25.0), (7, "T", 1.0)]


def run(tracker, color):
    other = "blue" if color == "red" else "red"
    tracker.seed({"tick": 0, "cam": "A", "est_xy": [0, 0]}, 0, "USER_PICK")
    out = []
    for tick, who, x in SCRIPT:
        dets = {"A": []} if who is None else row({"T": color, "O": other}[who], x)
        out.append(tracker.update(tick, dets, IMG, tick * .5, projected=True))
    return out


def test_default_is_the_unchanged_rule_tracker_for_red():
    for relock in (None, "off"):
        t = make("red", relock)
        assert t.relock is None and isinstance(t, Tracker)
        got = run(t, "red")
        assert all(set(r) == {"state", "active_cam", "seen_cams", "est_xy", "events", "lost_ticks"} for r in got)
        # Frozen from main @10a1384c (tracker.py is untouched by this PR): the exact per-tick output of the default path.
        assert [[r["state"], r["lost_ticks"], r["est_xy"], [e["type"] for e in r["events"]]] for r in got] == GOLDEN_RED


GOLDEN_RED = [
    ["TRACKING", 1, [0, 0], ["TARGET_OUT_OF_VIEW"]],
    ["TRACKING", 2, [0, 0], []],
    ["TRACKING", 3, [0, 0], []],
    ["TRACKING", 4, [0, 0], []],
    ["TRACKING", 5, [0, 0], []],
    ["TRACKING", 6, [0, 0], []],
    ["TRACKING", 0, [1.0, 0], []],
]


def test_fallback_flag_enables_relock_with_unknown_thresholds():
    t = make("blue", "fallback")
    assert t.relock is not None
    c = t.relock.config
    assert (c.t_short_s, c.v_walk_m_s, c.tau_app, c.margin_app, c.predict) == (None, None, None, None, False)


def test_fallback_blue_far_return_needs_confirm_then_in_gate_return_reacquires():
    got = run(make("blue", "fallback"), "blue")
    assert got[1]["state"] == "NEEDS_CONFIRM"          # 5 m > gate 4 m, inside R(u)=8 m: asked, never silently picked
    assert got[1]["lost_phase"] == "long" and got[1]["confirm_candidates"][0]["est_xy"] == [5.0, 0]
    assert got[2]["state"] == "NEEDS_CONFIRM"          # wrong colour is invisible to a blue session
    assert got[-1]["state"] == "TRACKING" and got[-1]["lost_ticks"] == 0
    ev = got[-1]["events"][0]
    assert ev["type"] == "REACQUIRE" and ev["detail"]["mode"] == "short_gate"

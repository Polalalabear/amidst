"""People track ids, the advisor's question lifecycle and the live decider (no network, no model, no ground truth)."""
import types

import pytest

from amidst.live_mode.advisor import Advisor, LiveDecider
from amidst.live_mode.people import PeopleTracker

Image = pytest.importorskip("PIL.Image")


def det(x0, score=0.9, h=60):
    return {"bbox": [x0, 40, x0 + 20, 40 + h], "score": score, "color": "red"}


def cand(cam, xy, x0=10, score=0.9, h=60):
    d = det(x0, score, h); d["est_xy"] = list(xy)
    return cam, d, xy


# ---------------------------------------------------------------- people
def test_people_keep_ids_while_moving_and_merge_cameras():
    pt = PeopleTracker()
    a = pt.update(0.0, [cand("W1", (0, 0)), cand("W2", (0.3, 0.1), score=0.8), cand("W1", (5, 0), x0=100)])
    assert len(a) == 2 and {len(p["dets"]) for p in a} == {1, 2}          # one person seen by two cameras
    ids = {tuple(round(v) for v in p["xy"]): p["pid"] for p in a}
    b = pt.update(0.5, [cand("W1", (0.6, 0)), cand("W1", (4.4, 0), x0=100)])  # both walk towards each other
    assert {tuple(round(v) for v in p["xy"]): p["pid"] for p in b} == {(1, 0): ids[(0, 0)], (4, 0): ids[(5, 0)]}


def test_people_drop_after_keep_and_new_id_for_far_jump():
    pt = PeopleTracker(keep_s=2.0)
    p0 = pt.update(0.0, [cand("W1", (0, 0))])[0]["pid"]
    assert pt.update(0.5, [cand("W1", (9, 9))])[0]["pid"] != p0           # 12.7 m in 0.5 s is not the same person
    assert pt.last_seen(p0) == 0.0
    pt.update(3.0, [])
    assert pt.last_seen(p0) is None


# ---------------------------------------------------------------- advisor
class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def make(provider, guard=None, **kw):
    c = Clock()
    return Advisor(provider, guard, clock=c, run_async=False, **kw), c


def test_advisor_needs_reference_one_question_at_a_time_and_polls_once():
    seen = []

    def provider(ref, frame, k, timeout_s):
        seen.append((ref, frame, k, timeout_s))
        return {"choice": 2, "reason": "r" * 80, "prompt_tokens": 800, "completion_tokens": 40, "api_model": "m"}
    adv, _ = make(provider)
    assert adv.ask("SILENT_PICK", "W1", [7, 9], b"frame") is False        # no reference yet
    adv.set_reference(b"ref")
    assert adv.ask("SILENT_PICK", "W1", [7, 9], b"frame") is True and adv.busy()
    assert adv.ask("SILENT_PICK", "W1", [7, 9], b"frame") is False        # still open
    r = adv.poll()
    assert r["source"] == "AGENT" and r["choice"] == 2 and r["pids"] == [7, 9] and len(r["reason"]) == 40
    assert adv.poll() is None and not adv.busy()
    # the provider gets two JPEG byte strings, the number of candidates and a timeout: no coordinates, no ids
    assert seen == [(b"ref", b"frame", 2, 5.0)]


def test_advisor_min_interval():
    adv, clock = make(lambda *a: {"choice": 0})
    adv.set_reference(b"r")
    assert adv.ask("K", "W1", [1], b"f") and adv.poll()["choice"] == 0
    assert adv.ask("K", "W1", [1], b"f") is False
    clock.t += 1.1
    assert adv.ask("K", "W1", [1], b"f") is True


@pytest.mark.parametrize("reply,reason", [({"choice": 5}, "INVALID_RESPONSE"), ({"choice": True}, "INVALID_RESPONSE"), ({"choice": "1"}, "INVALID_RESPONSE"), ({}, "INVALID_RESPONSE")])
def test_advisor_invalid_reply_falls_back(reply, reason):
    adv, _ = make(lambda *a: reply)
    adv.set_reference(b"r"); adv.ask("K", "W1", [1, 2], b"f")
    r = adv.poll()
    assert r["source"] == "RULE_FALLBACK" and r["fallback_reason"] == reason and r["choice"] is None


def test_advisor_provider_errors_fall_back():
    def boom(*a):
        raise RuntimeError("x")

    def slow(*a):
        raise TimeoutError()
    for provider, reason in ((boom, "PROVIDER_UNAVAILABLE"), (slow, "PROVIDER_TIMEOUT")):
        adv, _ = make(provider)
        adv.set_reference(b"r"); adv.ask("K", "W1", [1], b"f")
        assert adv.poll()["fallback_reason"] == reason


def test_advisor_time_budget_drops_late_reply():
    adv, clock = make(lambda *a: {"choice": 1})
    adv.set_reference(b"r")
    adv.run_async = True                      # nothing finishes: simulate a call still in flight
    adv._work = lambda *a: None
    adv.run_async = False
    adv.ask("K", "W1", [1], b"f")
    assert adv.poll() is None
    clock.t += 5.1
    r = adv.poll()
    assert r["source"] == "RULE_FALLBACK" and r["fallback_reason"] == "TIME_BUDGET" and r["latency_ms"] >= 5000
    Advisor._work(adv, 1, b"r", b"f", 1)      # the late reply for question 1 arrives now
    assert adv.poll() is None and not adv.busy()


def test_advisor_guard_denial_maps_to_fallback_reason():
    class Guard:
        def __init__(self, reason):
            self.reason = reason

        def run(self, caller, model, est, max_out, fn):
            assert caller == "live_adjudication"
            return types.SimpleNamespace(allowed=False, reason=self.reason)
    for g, want in (("API_DISABLED", "MODE_NOT_AUTHORIZED"), ("TOTAL_BUDGET", "CALL_BUDGET_EXHAUSTED"), ("RATE_LIMIT", "PROVIDER_UNAVAILABLE")):
        called = []
        adv, _ = make(lambda *a: called.append(1) or {"choice": 1}, Guard(g))
        adv.set_reference(b"r"); adv.ask("K", "W1", [1], b"f")
        assert adv.poll()["fallback_reason"] == want and not called   # the provider is never reached


# ---------------------------------------------------------------- decider
FRAME = {"W1": Image.new("RGB", (960, 540), (200, 200, 200))}


def tracker_stub(est=None):
    return types.SimpleNamespace(est=est, state="TRACKING", lost=0, active="W1", last_seen={})


def tracking(est, state="TRACKING", lost=0, events=()):
    return {"state": state, "active_cam": "W1", "seen_cams": ["W1"], "est_xy": est, "events": list(events), "lost_ticks": lost}


def dets_of(*cs):
    out = {}
    for cam, d, _ in cs:
        out.setdefault(cam, []).append(d)
    return out


def decider(mode="review", reply=None, **kw):
    replies = reply if isinstance(reply, list) else [reply or {"choice": 2, "reason": "背包相符"}]
    calls = []

    def provider(ref, frame, k, timeout_s):
        calls.append((len(ref) > 100, len(frame) > 100, k))
        return replies[min(len(calls), len(replies)) - 1]
    adv, clock = make(provider)
    return LiveDecider(mode, adv, PeopleTracker(), **kw), calls, clock


def lock(d, tr, t=0.0):
    """Tick 0: one red person at (0,0); the rule acquires it."""
    return d.step(0, t, tr, tracking([0, 0], events=[{"tick": 0, "type": "ACQUIRE", "cam": "W1"}]), dets_of(cand("W1", (0, 0), x0=300)), FRAME)


def test_decider_reference_then_silent_pick_then_follows_the_chosen_person():
    d, calls, _ = decider()
    tr = tracker_stub([0, 0])
    out = lock(d, tr)
    assert d.advisor.reference and out["decision_source"] == "RULE_ONLY" and out["advisor"]["state"] == "IDLE"
    # tick 1: two red people (more than 1.5 m apart) within the gate; the rule silently follows the left one (x0=100)
    two = [cand("W1", (0.5, 0), x0=100), cand("W1", (2.2, 0.5), x0=500)]
    out = d.step(1, 0.5, tr, tracking([0.5, 0]), dets_of(*two), FRAME)
    assert [e["type"] for e in out["events"]] == ["ADJUDICATE_ASK"] and out["advisor"]["state"] == "ASKING"
    assert out["state"] == "TRACKING" and out["est_xy"] == [0.5, 0]       # review mode: the rule's answer is still shown
    assert calls == [(True, True, 2)]
    # tick 2: the answer (candidate 2 = the right-hand person) is applied; the rule tracker is moved onto that person
    two = [cand("W1", (1.0, 0), x0=100), cand("W1", (2.7, 0.5), x0=500)]
    out = d.step(2, 1.0, tr, tracking([1.0, 0]), dets_of(*two), FRAME)
    assert out["decision_source"] == "AGENT" and out["est_xy"] == [2.7, 0.5] and tr.est == [2.7, 0.5] and tr.lost == 0
    assert out["advisor"]["last"]["applied"] is True and out["advisor"]["last"]["choice"] == 2
    assert "ADJUDICATED" in [e["type"] for e in out["events"]]
    # tick 3: the chosen person is missed by the detector once: hold the position, do not jump to the other person
    out = d.step(3, 1.5, tr, tracking([1.5, 0]), dets_of(cand("W1", (1.5, 0), x0=100)), FRAME)
    assert out["est_xy"] == [2.7, 0.5] and out["lost_ticks"] >= 1 and tr.est == [2.7, 0.5] and out["decision_source"] == "AGENT"
    # tick 4: seen again -> followed again
    out = d.step(4, 2.0, tr, tracking([2.7, 0.5]), dets_of(cand("W1", (1.5, 0), x0=100), cand("W1", (3.3, 0.5), x0=500)), FRAME)
    assert out["est_xy"] == [3.3, 0.5] and out["lost_ticks"] == 0


def test_decider_lead_mode_holds_the_view_while_asking():
    d, _, _ = decider("lead")
    tr = tracker_stub([0, 0]); lock(d, tr)
    out = d.step(1, 0.5, tr, tracking([0.5, 0]), dets_of(cand("W1", (0.5, 0), x0=100), cand("W1", (2.2, 0.5), x0=500)), FRAME)
    assert out["state"] == "ADJUDICATING" and out["est_xy"] == [0, 0] and out["active_cam"] == "W1"
    assert out["advisor"]["pending_ms"] is not None


def test_decider_answer_for_a_person_no_longer_tracked_is_not_applied():
    d, _, _ = decider()
    tr = tracker_stub([0, 0]); lock(d, tr)
    d.step(1, 0.5, tr, tracking([0.5, 0]), dets_of(cand("W1", (0.5, 0), x0=100), cand("W1", (2.2, 0.5), x0=500)), FRAME)
    # the answer is read 3 s later; person 2 has not been seen since 0.5 s
    out = d.step(2, 3.5, tr, tracking([3.0, 0]), dets_of(cand("W1", (3.0, 0), x0=100)), FRAME)
    last = out["advisor"]["last"]
    assert last["applied"] is False and last["source"] == "RULE_FALLBACK" and last["fallback_reason"] == "TIME_BUDGET"
    assert out["decision_source"] == "RULE_FALLBACK" and out["fallback_reason"] == "TIME_BUDGET" and out["est_xy"] == [3.0, 0]


def test_decider_choice_zero_releases_and_invalid_reply_keeps_rule():
    d, _, _ = decider(reply={"choice": 0, "reason": "都不是"})
    tr = tracker_stub([0, 0]); lock(d, tr)
    d.step(1, 0.5, tr, tracking([0.5, 0]), dets_of(cand("W1", (0.5, 0), x0=100), cand("W1", (2.2, 0.5), x0=500)), FRAME)
    out = d.step(2, 1.0, tr, tracking([1.0, 0]), dets_of(cand("W1", (1.0, 0), x0=100), cand("W1", (2.7, 0.5), x0=500)), FRAME)
    assert out["advisor"]["last"]["applied"] is True and out["decision_source"] == "RULE_ONLY" and out["est_xy"] == [1.0, 0]
    d2, _, _ = decider(reply={"choice": 9})
    tr = tracker_stub([0, 0]); lock(d2, tr)
    d2.step(1, 0.5, tr, tracking([0.5, 0]), dets_of(cand("W1", (0.5, 0), x0=100), cand("W1", (2.2, 0.5), x0=500)), FRAME)
    out = d2.step(2, 1.0, tr, tracking([1.0, 0]), dets_of(cand("W1", (1.0, 0), x0=100), cand("W1", (2.7, 0.5), x0=500)), FRAME)
    assert out["decision_source"] == "RULE_FALLBACK" and out["fallback_reason"] == "INVALID_RESPONSE" and out["est_xy"] == [1.0, 0]


def test_decider_asks_when_lost_with_a_candidate_and_not_when_one_person_is_tracked():
    d, calls, _ = decider(reply={"choice": 1, "reason": "相符"})
    tr = tracker_stub([0, 0]); lock(d, tr)
    out = d.step(1, 0.5, tr, tracking([0.5, 0]), dets_of(cand("W1", (0.5, 0), x0=100)), FRAME)     # one person, matched: no question
    assert not calls and out["advisor"]["state"] == "IDLE"
    far = cand("W1", (8, 3), x0=600)                                                               # outside the 3 m gate: the rule is lost
    d.step(2, 1.0, tr, tracking([0.5, 0], lost=1), dets_of(far), FRAME)
    assert not calls                                                                              # lost for one tick only
    out = d.step(3, 1.5, tr, tracking([0.5, 0], lost=2), dets_of(far), FRAME)
    assert calls == [(True, True, 1)] and out["events"][-1]["detail"]["kind"] == "LOST_WITH_CANDIDATES"
    out = d.step(4, 2.0, tr, tracking([0.5, 0], lost=3), dets_of(cand("W1", (8.5, 3), x0=600)), FRAME)
    assert out["decision_source"] == "AGENT" and out["est_xy"] == [8.5, 3] and out["state"] == "TRACKING" and tr.state == "TRACKING"


def test_decider_candidates_are_numbered_left_to_right():
    d, _, _ = decider(reply={"choice": 1, "reason": "x"})
    tr = tracker_stub([0, 0]); lock(d, tr)
    right_first = [cand("W1", (2.2, 0.5), x0=500), cand("W1", (0.5, 0), x0=100)]
    d.step(1, 0.5, tr, tracking([0.5, 0]), dets_of(*right_first), FRAME)
    out = d.step(2, 1.0, tr, tracking([1.0, 0]), dets_of(cand("W1", (2.7, 0.5), x0=500), cand("W1", (1.0, 0), x0=100)), FRAME)
    assert out["est_xy"] == [1.0, 0]      # candidate 1 is the left-hand box, whatever order the detections came in


def test_server_builds_no_decider_when_the_advisor_is_off():
    server = pytest.importorskip("amidst.live_mode.server")
    st = object.__new__(server.State)
    st.args, st.guard = types.SimpleNamespace(advisor="off"), None
    assert st._new_decider() is None
    st.args = types.SimpleNamespace(advisor="lead", advisor_provider="fake", advisor_model="sol6.1", advisor_timeout_s=5.0, advisor_fake_delay_s=0.0)
    dec = st._new_decider()
    assert dec.mode == "lead" and dec.advisor.model_id == "fake" and dec.advisor.guard is None

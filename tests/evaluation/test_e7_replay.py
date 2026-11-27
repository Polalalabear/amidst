"""#767 R1: E7 answers replayed through the unchanged E5 AOpenDecider (simlive)."""
from __future__ import annotations

import pytest

from amidst.evaluation import e7_replay as RP


class _Proj:
    def ground(self, camera, cx, by, w, h):
        return [cx / w * 10.0, by / h * 10.0]


def _snap(box, latency, *, answer="SELECT", fallback=None):
    parsed = None if fallback else {"answer": answer, "camera_id": "C1", "detection_id": "D1", "box_xyxy": None,
                                    "next_camera_ranking": ["C2"], "confidence": 0.9, "reason": ""}
    return {"parsed": parsed, "fallback_reason": fallback, "latency_s": latency,
            "candidates": [{"camera_id": "C1", "detection_id": "D1", "box": box or [0, 0, 1, 1], "score": 0.9}]}


def _dets(x):  # one person on C1, moving right by x px
    return {"C1": [{"bbox": [x, 40, x + 20, 100], "score": 0.9}]}


def _run(snapshots, chain_start, n=40, speed=2, gap=()):
    d = RP.ReplayAOpenDecider(snapshots, {"scene": 1}, _Proj(), chain_start=chain_start, poll_s=2.0, min_interval_s=1.0,
                              call_cap=50, timeout_s=30.0)
    d.reference = b"stub"  # the E5 reference crop is not used by a replay
    rows = [d.step(t, ({"C1": []} if t in gap else _dets(10 + speed * t)), {}, {"state": "TRACKING", "active_cam": "C1", "lost_ticks": 0}) for t in range(n)]
    return d, rows


@pytest.fixture(autouse=True)
def _sx(monkeypatch):
    monkeypatch.setattr(RP.sx, "sha256_of", lambda scene: "0" * 64)


def test_uses_latest_snapshot_at_or_before_ask_and_delivers_after_latency():
    snaps = {0: _snap([10, 40, 30, 100], 0.5), 10: _snap([30, 40, 50, 100], 0.5)}
    d, rows = _run(snaps, "ask")
    first = d.calls[0]
    assert first["ask_tick"] == 0 and first["snapshot_tick"] == 0
    assert first["applied_tick"] == 3  # (3-0)/5 = 0.6 s > 0.5 s latency, first such tick
    second = next(c for c in d.calls if c["ask_tick"] >= 10)
    assert second["snapshot_tick"] == (second["ask_tick"] // 10) * 10
    assert d.pending is None or d.pending["tick"] > first["ask_tick"]
    assert all(c["ask_tick"] >= p["applied_tick"] for p, c in zip(d.calls, d.calls[1:]) if "applied_tick" in p)  # one pending at a time


def test_format_fallback_is_no_answer_but_blocks_for_its_latency():
    snaps = {0: _snap(None, 1.0, fallback="UNKNOWN_DETECTION"), 10: _snap([30, 40, 50, 100], 0.2)}
    d, rows = _run(snaps, "snapshot", n=30)
    f = d.calls[0]
    assert f["fallback_reason"] == "UNKNOWN_DETECTION" and f["applied"] is False and f["answer"] is None
    assert f["applied_tick"] == 6  # 1.0 s latency -> (6-0)/5 = 1.2 > 1.0
    assert d.neutral.target is None or d.calls[0]["source"] == "NEUTRAL"


def test_chain_start_snapshot_is_stricter_than_ask():
    # snapshot 0 box at x=10; the person moves 8 px per tick, so after many ticks the 0->t chain breaks (IoU < 0.3).
    snaps = {0: _snap([10, 40, 30, 100], 1.0)}
    # ask tick == snapshot tick (0): both variants chain the same ticks
    d_snap, _ = _run(snaps, "snapshot", n=25, speed=8)
    d_ask, _ = _run(snaps, "ask", n=25, speed=8)
    assert d_snap.calls[0]["ticks_chained"] == d_ask.calls[0]["ticks_chained"]
    # later asks reuse a stale snapshot: snapshot variant also chains the s+1..ask ticks, ask variant only the ticks after the ask
    snaps2 = {0: _snap([10, 40, 30, 100], 0.2)}
    a, _ = _run(snaps2, "ask", n=40, speed=2, gap=(3,))
    s, _ = _run(snaps2, "snapshot", n=40, speed=2, gap=(3,))
    late = [c for c in s.calls if 0 < c["ask_tick"] and c["snapshot_tick"] == 0]
    # the stale snapshot chain (ticks 1..ask) crosses the one-tick detection gap at tick 3 and expires; the ask-tick chain does not
    assert late and late[0]["fallback_reason"] == "EXPIRED"
    late_a = [c for c in a.calls if c["ask_tick"] > 0 and c["snapshot_tick"] == 0]
    # ticks walked by the chain: snapshot variant s+1..delivery, ask variant ask+1..delivery
    assert late[0]["ticks_chained"] == late[0]["applied_tick"] - 0
    assert late_a[0]["ticks_chained"] == late_a[0]["applied_tick"] - late_a[0]["ask_tick"]


def test_bad_inputs():
    with pytest.raises(ValueError):
        RP.ReplayAOpenDecider({}, {}, _Proj())
    with pytest.raises(ValueError):
        RP.ReplayAOpenDecider({0: _snap([0, 0, 1, 1], 0.1)}, {}, _Proj(), chain_start="x")

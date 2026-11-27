"""E7 real-latency replay (#767, R1): recorded E7 answers through the unchanged E5 AO-L machinery.

``ReplayAOpenDecider`` subclasses ``amidst.live_mode.aopen.decider.AOpenDecider`` (mode ``simlive``) and replaces ONLY
the model call: ``_ask`` returns the recorded answer of the latest E7 snapshot at or before the ask tick, delivered after
that request's MEASURED latency. Everything else is inherited unchanged: ask schedule (FIRST / LOST_EARLY / POLL,
one pending call), ``_poll`` delivery rule ((tick-ask)/5 > delay), ``chain_box`` (IoU >= 0.3), ``NeutralTracker``.

Stubs (answers are pre-recorded, so these inputs never reach a model):
* frames: the caller passes blank 320x180 images; they are only cropped to seed the (unused) reference.
* prompt/body building (``build_input``) is bypassed.

Chain start (``chain_start``):
* ``"snapshot"`` (primary, stricter): the recorded box belongs to the snapshot tick s, so it is chained over the
  detections of ticks s+1 .. delivery tick (stale-snapshot penalty).
* ``"ask"``: the box is treated as if it were drawn at the ask tick (AO-L's own convention; sensitivity column).

No GT is read here. Scoring (``scripts/evaluation/e7_replay_run.py``) is Mac-only.
"""
from __future__ import annotations

import bisect
import math
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from amidst.live_mode.aopen.decider import MODEL, AOpenDecider
from amidst.q1q5 import scene_context as sx

CHAIN_STARTS = ("snapshot", "ask")


def snapshot_table(raw_comparison: dict[str, Any], requests: list[dict[str, Any]], case_id: str,
                   *, block: str = "accelerated") -> dict[int, dict[str, Any]]:
    """tick -> {parsed, fallback_reason, latency_s, candidates} for one case, from an E7 checkpoint block + request rows."""
    cands = {r["request_id"]: r.get("candidates") or [] for r in requests if r["case_id"] == case_id}
    out: dict[int, dict[str, Any]] = {}
    for rec in raw_comparison[block]["records"]:
        if rec["case_id"] != case_id:
            continue
        out[int(rec["tick"])] = {
            "parsed": rec.get("parsed"),
            "fallback_reason": rec.get("fallback_reason"),
            "latency_s": float(rec["latency_ms"]) / 1000.0,
            "candidates": cands.get(rec["request_id"], []),
        }
    return out


class ReplayAOpenDecider(AOpenDecider):
    def __init__(self, snapshots: dict[int, dict[str, Any]], scene, projector, *, chain_start: str = "snapshot", **kw):
        if chain_start not in CHAIN_STARTS:
            raise ValueError("BAD_CHAIN_START")
        if not snapshots:
            raise ValueError("NO_SNAPSHOTS")
        kw["mode"] = "simlive"
        super().__init__(None, scene, projector, **kw)
        self.snapshots = snapshots
        self._snap_ticks = sorted(snapshots)
        self.chain_start = chain_start
        self._dets: dict[int, dict[str, list[dict]]] = {}

    def step(self, tick, dets, frames, rule_state):
        self._dets[tick] = {c: [{"bbox": list(d["bbox"])} for d in ds] for c, ds in dets.items()}
        return super().step(tick, dets, frames, rule_state)

    def _snapshot_for(self, tick: int) -> int:
        i = bisect.bisect_right(self._snap_ticks, tick) - 1
        if i < 0:
            raise ValueError(f"NO_SNAPSHOT_AT_OR_BEFORE:{tick}")
        return self._snap_ticks[i]

    def _ask(self, tick, kind, frames, dets, rule_state):
        s = self._snapshot_for(tick)
        snap = self.snapshots[s]
        parsed, latency = snap.get("parsed"), float(snap["latency_s"])
        cands = [SimpleNamespace(camera_id=c["camera_id"], id=c["detection_id"], box=tuple(c["box"]))
                 for c in snap.get("candidates") or []]
        rec = {"tick": tick, "ask_tick": tick, "snapshot_tick": s, "kind": kind, "answer": None, "camera_id": None,
               "detection_id": None, "box_xyxy": None, "next_camera_ranking": [], "ranking_supplied": False,
               "next_camera_hint_raw": None, "confidence": None, "reason_codes": [], "reason": "", "applied": False,
               "source": "NEUTRAL", "fallback_reason": None, "usage": {},
               "scene_context_sha256": sx.sha256_of(self.scene),
               "request": {"t_s": tick / 5, "snapshot_tick": s, "candidates": len(cands), "images": {}},
               "error": None, "model": "e7-replay", "pending_at_end": True}
        if not math.isfinite(latency) or latency < 0:
            raise ValueError("BAD_LATENCY")
        if latency > self.timeout_s:
            rec["fallback_reason"] = "PROVIDER_TIMEOUT"
        elif parsed is None:
            rec["fallback_reason"] = snap.get("fallback_reason") or "FORMAT_INVALID"  # no answer, still consumes latency
        else:
            rec.update({k: parsed.get(k) for k in ("answer", "camera_id", "detection_id", "box_xyxy", "confidence", "reason")
                        if k in parsed})
            rec["next_camera_ranking"] = list(parsed.get("next_camera_ranking") or [])
            rec["ranking_supplied"] = bool(rec["next_camera_ranking"])
            rec["reason_codes"] = list(parsed.get("reason_codes") or [])
            rec["source"] = "AGENT"
        rec.update(latency_ms=round(latency * 1000), model_latency_s=latency)
        self.calls.append(rec)
        history = []
        if self.chain_start == "snapshot":
            history = [deepcopy(self._dets[k]) for k in range(s + 1, tick + 1) if k in self._dets]
        self.pending = {"rec": rec, "inp": SimpleNamespace(candidates=cands), "tick": tick, "history": history,
                        "delay_s": min(latency, self.timeout_s)}
        self.last_ask_tick = tick

"""Per-person track ids for live mode (pixel-derived only).

The rule tracker follows "the nearest red detection to the last estimate" and has no notion of who is who. An image
adjudication takes seconds, so its answer must refer to something that still exists when it arrives: a track id.
This module groups the red detections of one tick into people and links people across ticks. Inputs are detections
and their projected ground points; nothing here knows actor ids, scripted positions or ground truth. A track id is a
tracking handle, never an identity.

Three things keep ids from swapping when two people pass each other (the failure seen in the second live run, where
a correct answer was applied to the wrong person, docs/evaluation/LIVE_MODE_ADVISOR_20261116.md):
  - two boxes in the same camera are always two people, however close their ground points are;
  - tracks are linked to where they were heading (constant-velocity prediction), not to where they last were;
  - a track that came within ``contest_m`` of another person is marked contested at that time, so a caller can
    refuse to trust an id across such a moment.
"""
from __future__ import annotations

import math


class PeopleTracker:
    def __init__(self, same_m: float = 1.5, vmax_m_s: float = 2.5, keep_s: float = 2.0, max_gate_m: float = 6.0, contest_m: float = 0.7):
        self.same, self.vmax, self.keep, self.max_gate, self.contest = same_m, vmax_m_s, keep_s, max_gate_m, contest_m
        self.tracks: dict[int, dict] = {}   # pid -> {xy, t, v, contested_t}
        self._next = 1

    @staticmethod
    def group(cands: list[tuple], same_m: float) -> list[dict]:
        """cands: (cam, det, xy). Highest score first. A detection joins the nearest person within ``same_m`` that has
        no box from the same camera yet (one person seen by several cameras); otherwise it is a new person."""
        people: list[dict] = []
        for cam, det, xy in sorted(cands, key=lambda c: -c[1]["score"]):
            near = [p for p in people if math.dist(p["xy"], xy) < same_m and all(c != cam for c, _ in p["dets"])]
            if near:
                min(near, key=lambda p: math.dist(p["xy"], xy))["dets"].append((cam, det))
            else:
                people.append({"xy": list(xy), "dets": [(cam, det)], "score": det["score"]})
        return people

    def _predict(self, tr: dict, t_s: float) -> list[float]:
        dt = max(0.0, t_s - tr["t"])
        return [tr["xy"][0] + tr["v"][0] * dt, tr["xy"][1] + tr["v"][1] * dt]

    def update(self, t_s: float, cands: list[tuple]) -> list[dict]:
        """Returns the people seen this tick, each with a stable ``pid``."""
        people = self.group(cands, self.same)
        for pid in [p for p, tr in self.tracks.items() if t_s - tr["t"] > self.keep]:
            del self.tracks[pid]
        pairs = []
        for pid, tr in self.tracks.items():
            gate = min(self.max_gate, self.same + self.vmax * max(0.0, t_s - tr["t"]))
            pred = self._predict(tr, t_s)
            for i, p in enumerate(people):
                if math.dist(tr["xy"], p["xy"]) <= gate:      # reachable from where it was
                    pairs.append((math.dist(pred, p["xy"]), pid, i))   # ranked by where it was heading
        used_t, used_p = set(), set()
        for d, pid, i in sorted(pairs):  # closest pairs first
            if pid in used_t or i in used_p:
                continue
            used_t.add(pid); used_p.add(i)
            people[i]["pid"] = pid
        for p in people:
            old = self.tracks.get(p.get("pid"))
            if old is None:
                p["pid"] = self._next
                self._next += 1
                v, contested = [0.0, 0.0], -1e9
            else:
                dt = t_s - old["t"]
                if dt > 1e-6:
                    raw = [(p["xy"][0] - old["xy"][0]) / dt, (p["xy"][1] - old["xy"][1]) / dt]
                    sp = math.hypot(*raw)
                    if sp > self.vmax:    # projection jitter must not turn into an impossible speed
                        raw = [raw[0] * self.vmax / sp, raw[1] * self.vmax / sp]
                    v = [0.5 * old["v"][0] + 0.5 * raw[0], 0.5 * old["v"][1] + 0.5 * raw[1]]
                else:
                    v = old["v"]
                contested = old["contested_t"]
            self.tracks[p["pid"]] = {"xy": p["xy"], "t": t_s, "v": v, "contested_t": contested}
        for i, a in enumerate(people):   # mark tracks that are too close to another person to tell apart reliably
            for b in people[i + 1:]:
                if math.dist(a["xy"], b["xy"]) < self.contest:
                    self.tracks[a["pid"]]["contested_t"] = self.tracks[b["pid"]]["contested_t"] = t_s
        return people

    def last_seen(self, pid: int) -> float | None:
        tr = self.tracks.get(pid)
        return tr["t"] if tr else None

    def contested_since(self, pid: int, t_s: float) -> bool:
        """True when the track came close to another person at or after ``t_s`` (its id may have changed hands)."""
        tr = self.tracks.get(pid)
        return tr is None or tr["contested_t"] >= t_s

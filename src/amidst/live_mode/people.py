"""Per-person track ids for live mode (pixel-derived only).

The rule tracker follows "the nearest red detection to the last estimate" and has no notion of who is who. An image
adjudication takes seconds, so its answer must refer to something that still exists when it arrives: a track id.
This module groups the red detections of one tick into people (ground points closer than ``same_m`` are one person
seen by several cameras) and links people across ticks by nearest ground distance inside a gate that grows with the
time since the track was last seen. Inputs are detections and their projected ground points; nothing here knows actor
ids, scripted positions or ground truth. A track id is a tracking handle, never an identity.
"""
from __future__ import annotations

import math


class PeopleTracker:
    def __init__(self, same_m: float = 1.5, vmax_m_s: float = 2.5, keep_s: float = 2.0, max_gate_m: float = 6.0):
        self.same, self.vmax, self.keep, self.max_gate = same_m, vmax_m_s, keep_s, max_gate_m
        self.tracks: dict[int, dict] = {}   # pid -> {xy, t}
        self._next = 1

    @staticmethod
    def group(cands: list[tuple], same_m: float) -> list[dict]:
        """cands: (cam, det, xy). Highest score first; a detection within ``same_m`` of a person joins it."""
        people: list[dict] = []
        for cam, det, xy in sorted(cands, key=lambda c: -c[1]["score"]):
            hit = next((p for p in people if math.dist(p["xy"], xy) < same_m), None)
            if hit is None:
                people.append({"xy": list(xy), "dets": [(cam, det)], "score": det["score"]})
            elif all(c != cam for c, _ in hit["dets"]):  # one box per camera for one person
                hit["dets"].append((cam, det))
        return people

    def update(self, t_s: float, cands: list[tuple]) -> list[dict]:
        """Returns the people seen this tick, each with a stable ``pid``."""
        people = self.group(cands, self.same)
        for pid in [p for p, tr in self.tracks.items() if t_s - tr["t"] > self.keep]:
            del self.tracks[pid]
        pairs = []
        for pid, tr in self.tracks.items():
            gate = min(self.max_gate, self.same + self.vmax * max(0.0, t_s - tr["t"]))
            for i, p in enumerate(people):
                d = math.dist(tr["xy"], p["xy"])
                if d <= gate:
                    pairs.append((d, pid, i))
        used_t, used_p = set(), set()
        for d, pid, i in sorted(pairs):  # closest pairs first
            if pid in used_t or i in used_p:
                continue
            used_t.add(pid); used_p.add(i)
            people[i]["pid"] = pid
        for i, p in enumerate(people):
            if "pid" not in p:
                p["pid"] = self._next
                self._next += 1
            self.tracks[p["pid"]] = {"xy": p["xy"], "t": t_s}
        return people

    def last_seen(self, pid: int) -> float | None:
        tr = self.tracks.get(pid)
        return tr["t"] if tr else None

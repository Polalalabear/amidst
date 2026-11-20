"""Per-person track ids for live mode (pixel-derived only).

The rule tracker follows "the nearest red detection to the last estimate" and has no notion of who is who. An image
adjudication takes seconds, so its answer must refer to something that still exists when it arrives: a track id.
This module groups the red detections of one tick into people and links people across ticks. Inputs are detections
and their projected ground points; nothing here knows actor ids, scripted positions or ground truth. A track id is a
tracking handle, never an identity.

Three things keep ids from swapping when two people pass each other (the failure seen in the second live run, where
a correct answer was applied to the wrong person, docs/evaluation/LIVE_MODE_ADVISOR_20261116.md):
  - two boxes in the same camera are two people, however close their ground points are, unless they are duplicates of
    one detection (IoU >= ``dup_iou``, the lower-scored one is dropped first);
  - tracks are linked to where they were heading (constant-velocity prediction), not to where they last were;
  - a track that came within ``contest_m`` of another person is marked contested at that time, so a caller can
    refuse to trust an id across such a moment.
"""
from __future__ import annotations

import math


# Cross-camera merge distance. 1.0 m was picked from the two scripted routes (A4/B4), not from independent data: on A4 a
# bystander walks 1.28-1.42 m from the target, so 1.0 m sits in the 0.64-1.28 m gap of the observed distances
# (docs/evaluation/LIVE_MODE_A4_REGRESSION_20261116.md). Other scenes may need another value.
SAME_M = 1.0
DUP_IOU = 0.6
LINK_BASE_M = 1.5   # base of the frame-to-frame link gate; kept at the old merge distance so linking is unchanged


def _iou(a: list, b: list) -> float:
    iw, ih = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


class PeopleTracker:
    def __init__(self, same_m: float = SAME_M, vmax_m_s: float = 2.5, keep_s: float = 2.0, max_gate_m: float = 6.0, contest_m: float = 0.7,
                 dup_iou: float = DUP_IOU):
        self.same, self.vmax, self.keep, self.max_gate, self.contest, self.dup_iou = same_m, vmax_m_s, keep_s, max_gate_m, contest_m, dup_iou
        # counters, summed over all ticks: boxes dropped as same-camera duplicates; cross-camera merges; merges in which two
        # member boxes are more than ``same_m`` apart (a merge decided by the group mean, not by the pair)
        self.stats = {"dup_dropped": 0, "merges": 0, "far_merges": 0}
        self.tracks: dict[int, dict] = {}   # pid -> {xy, t, v, contested_t}
        self._next = 1

    @staticmethod
    def group(cands: list[tuple], same_m: float, dup_iou: float = DUP_IOU, stats: dict | None = None) -> list[dict]:
        """cands: (cam, det, xy). 1) In each camera a box whose IoU with a higher-scored box is >= ``dup_iou`` is a duplicate
        and is dropped. 2) Every remaining box starts as a person; the closest pair of people (distance between their mean
        ground points, < ``same_m``) that share no camera is merged, repeated until none is left, so distance, not score
        order, decides who is merged. A person's ``xy`` is the mean of its members' ground points."""
        st = stats if stats is not None else {}
        for k in ("dup_dropped", "merges", "far_merges"):
            st.setdefault(k, 0)
        kept: list[tuple] = []
        for c in sorted(cands, key=lambda c: -c[1]["score"]):
            if any(k[0] == c[0] and _iou(k[1]["bbox"], c[1]["bbox"]) >= dup_iou for k in kept):
                st["dup_dropped"] += 1
            else:
                kept.append(c)
        people = [{"xy": list(c[2]), "dets": [(c[0], c[1])], "score": c[1]["score"], "_pts": [c[2]]} for c in kept]
        while True:
            best = None
            for i, a in enumerate(people):
                cams = {c for c, _ in a["dets"]}
                for j in range(i + 1, len(people)):
                    b = people[j]
                    d = math.dist(a["xy"], b["xy"])
                    if d < same_m and (best is None or d < best[0]) and not cams & {c for c, _ in b["dets"]}:
                        best = (d, i, j)
            if best is None:
                break
            _, i, j = best
            a, b = people[i], people.pop(j)
            if max(math.dist(p, q) for p in a["_pts"] for q in b["_pts"]) > same_m:
                st["far_merges"] += 1
            st["merges"] += 1
            a["dets"] = sorted(a["dets"] + b["dets"], key=lambda x: -x[1]["score"])
            a["_pts"] += b["_pts"]
            a["score"] = a["dets"][0][1]["score"]
            a["xy"] = [sum(p[0] for p in a["_pts"]) / len(a["_pts"]), sum(p[1] for p in a["_pts"]) / len(a["_pts"])]
        for p in people:
            del p["_pts"]
        return sorted(people, key=lambda p: -p["score"])

    def _predict(self, tr: dict, t_s: float) -> list[float]:
        dt = max(0.0, t_s - tr["t"])
        return [tr["xy"][0] + tr["v"][0] * dt, tr["xy"][1] + tr["v"][1] * dt]

    def update(self, t_s: float, cands: list[tuple]) -> list[dict]:
        """Returns the people seen this tick, each with a stable ``pid``."""
        people = self.group(cands, self.same, self.dup_iou, self.stats)
        for pid in [p for p, tr in self.tracks.items() if t_s - tr["t"] > self.keep]:
            del self.tracks[pid]
        pairs = []
        for pid, tr in self.tracks.items():
            gate = min(self.max_gate, LINK_BASE_M + self.vmax * max(0.0, t_s - tr["t"]))
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

    def velocity(self, pid: int | None) -> tuple[float, float] | None:
        """Velocity of an active observation track, in metres per capture second."""
        track = self.tracks.get(pid)
        return tuple(track["v"]) if track is not None else None

    def contested_since(self, pid: int, t_s: float) -> bool:
        """True when the track came close to another person at or after ``t_s`` (its id may have changed hands)."""
        tr = self.tracks.get(pid)
        return tr is None or tr["contested_t"] >= t_s

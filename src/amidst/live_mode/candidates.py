"""Pixel-derived LIVE candidates and session-scoped selection references."""
from __future__ import annotations

import hashlib
import hmac
import math
import re
import secrets
from collections import deque
from dataclasses import dataclass
from numbers import Real

COLORS = ("red", "blue")
STALE_TICKS = 6
SAME_PERSON_M = 1.5
SESSION_RE = re.compile(r"[0-9a-fA-F]{16}")
CAND_RE = re.compile(r"([0-9a-f]{16})\.([0-9a-f]+)\.([0-9a-f]+)\.([0-9a-f]+)\.([0-9a-f]{16})")


class TrackRequestError(Exception):
    def __init__(self, status, error, *, fields=None):
        self.status = status
        self.response = {"error": error}
        if fields is not None:
            self.response["fields"] = fields
        super().__init__(error)


def finite_point(values, size):
    if not isinstance(values, (list, tuple)) or len(values) != size:
        return False
    try:
        return all(isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
                   for value in values)
    except OverflowError:
        return False


def group_candidates(dets):
    """Connected groups of same-color projected detections; keep the best scored box."""
    candidates = []
    for cam, detections in dets.items():
        for det in detections:
            color, bbox, xy, score = (det.get(key) for key in ("color", "bbox", "est_xy", "score"))
            if color in COLORS and finite_point(bbox, 4) and finite_point(xy, 2) and finite_point([score], 1):
                candidates.append({
                    "cam": cam, "bbox": [float(value) for value in bbox], "score": float(score),
                    "color": color, "est_xy": [float(value) for value in xy],
                })
    candidates.sort(key=lambda item: (-item["score"], item["cam"], item["bbox"]))
    groups = []
    for candidate in candidates:
        matching = [
            group for group in groups if any(
                item["color"] == candidate["color"]
                and math.dist(item["est_xy"], candidate["est_xy"]) < SAME_PERSON_M
                for item in group
            )
        ]
        if not matching:
            groups.append([candidate])
            continue
        matching[0].append(candidate)
        for group in matching[1:]:
            matching[0].extend(group)
            groups.remove(group)
    return [group[0] for group in groups]


@dataclass(frozen=True)
class Generation:
    tick: int
    capture_s: float
    candidates: list[dict]


class TrackSelection:
    """Caller holds the State lock for every read and write."""

    def __init__(self):
        self.session_id = secrets.token_hex(8)
        self._signing_key = secrets.token_bytes(32)
        self.epoch = 0
        self.mode = "IDLE"
        self.color = None
        self.reselecting = False
        self.generations = deque(maxlen=STALE_TICKS + 1)

    @property
    def latest(self):
        return self.generations[-1] if self.generations else None

    @property
    def tracking_active(self):
        return self.mode == "TRACKING" or self.reselecting

    def require_session(self, requested):
        if not isinstance(requested, str) or not SESSION_RE.fullmatch(requested):
            raise TrackRequestError(400, "SESSION_REQUIRED")
        if requested != self.session_id:
            raise TrackRequestError(409, "SESSION_MISMATCH")

    def observe(self, tick, capture_s, dets):
        if self.latest is None or tick > self.latest.tick:
            self.generations.append(Generation(tick, capture_s, group_candidates(dets)))

    def _sign(self, prefix):
        return hmac.new(self._signing_key, prefix.encode("ascii"), hashlib.sha256).hexdigest()[:16]

    def _public_candidate(self, generation, index):
        prefix = f"{self.session_id}.{self.epoch:x}.{generation.tick:x}.{index:x}"
        return {
            "cand_id": f"{prefix}.{self._sign(prefix)}", "tick": generation.tick,
            **generation.candidates[index],
        }

    def snapshot(self, color):
        generation = self.latest
        return {
            "tick": generation.tick if generation else None,
            "color": color,
            "candidates": [
                self._public_candidate(generation, index)
                for index, item in enumerate(generation.candidates)
                if color == "any" or item["color"] == color
            ] if generation else [],
        }

    def state(self):
        return {"session_id": self.session_id, "mode": self.mode, "color": self.color,
                "tick": self.latest.tick if self.latest else None}

    def start(self, color, reselect):
        if reselect and (self.mode != "TRACKING" or self.color != color):
            raise TrackRequestError(409, "TRACK_MODE_CONFLICT")
        self.epoch += 1
        self.mode = "NEEDS_PICK" if reselect else "ACQUIRING"
        self.color = color
        self.reselecting = reselect

    def pick(self, cand_id):
        if self.mode != "NEEDS_PICK":
            raise TrackRequestError(409, "TRACK_MODE_CONFLICT")
        match = CAND_RE.fullmatch(cand_id)
        if not match or match[1] != self.session_id or not hmac.compare_digest(
            match[5], self._sign(cand_id.rsplit(".", 1)[0])
        ):
            raise TrackRequestError(404, "CANDIDATE_UNKNOWN")
        epoch, tick, index = (int(match[n], 16) for n in (2, 3, 4))
        if epoch != self.epoch or (self.latest and self.latest.tick - tick > STALE_TICKS):
            raise TrackRequestError(409, "CANDIDATE_STALE")
        generation = next((item for item in self.generations if item.tick == tick), None)
        if (
            generation is None or index >= len(generation.candidates)
            or generation.candidates[index]["color"] != self.color
        ):
            raise TrackRequestError(404, "CANDIDATE_UNKNOWN")
        candidate = self._public_candidate(generation, index)
        self.epoch += 1
        return candidate, generation.capture_s

    def locked(self):
        self.mode = "TRACKING"
        self.reselecting = False

    def stop(self):
        self.epoch += 1
        self.mode, self.color, self.reselecting = "IDLE", None, False

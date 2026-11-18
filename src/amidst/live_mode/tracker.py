"""Simplified system-side tracking and camera switching for the spike.

This is NOT associate()/Q4/Q5 (their inputs are offline detection indexes); it is a minimal
stand-in so end-to-end latency can be measured: red person seeded when exactly one red person is
visible; follow by ground-plane continuity; switch when the active camera lost the target for
`hold_ticks` and another camera sees it (the Q5 decision-window analogue). Inputs are pixels-derived
detections only.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .candidates import COLORS, finite_point


CATALOG_REL = "r004-build-v2-20261021/safe_static/cameras.json"


def catalog_path(arg: str | None = None) -> Path:
    """Camera catalog the runtime may read (safe_static, controlled-scene.cameras.v1); --cameras overrides it."""
    if arg:
        return Path(arg)
    from amidst.paths import data_dir
    return data_dir() / CATALOG_REL


def load_cameras(arg: str | None = None) -> list[dict]:
    """Calibration only (camera_to_world, fx/fy/cx/cy, width/height) from the safe_static catalog; raises if it is absent."""
    path = catalog_path(arg)
    if not path.is_file():
        raise FileNotFoundError(f"camera catalog not found: {path} (pass --cameras or restore local/data/{CATALOG_REL})")
    return json.loads(path.read_text())["cameras"]


class Projector:
    """Pixel foot point -> ground (z=0) world XY using catalog calibration (inference-side only)."""

    def __init__(self, cameras: list[dict]):
        self.cams = {}
        for c in cameras:
            M = np.array(c["camera_to_world"], dtype=float)
            self.cams[c["camera_id"]] = (M, c["fx"], c["fy"], c["cx"], c["cy"], c["width"], c["height"])

    def ground(self, cam: str, u: float, v: float, img_w: int, img_h: int):
        M, fx, fy, cx, cy, W, H = self.cams[cam]
        u, v = u * W / img_w, v * H / img_h
        d_cam = np.array([(u - cx) / fx, -(v - cy) / fy, -1.0])  # Blender cam: -Z fwd, +Y up
        d = M[:3, :3] @ d_cam
        o = M[:3, 3]
        if d[2] >= -1e-6:
            return None
        t = -o[2] / d[2]
        if t <= 0 or t > 80:
            return None
        p = o + t * d
        return [float(p[0]), float(p[1])]


class Tracker:
    def __init__(self, projector: Projector, hold_ticks: int = 2, gate_m: float = 3.0, lost_after: int = 15,
                 gate_growth_m_s: float = 0.0, max_gate_m: float = 8.0, target_color: str = "red"):
        if target_color not in COLORS:
            raise ValueError("COLOR_UNSUPPORTED")
        self.target_color = target_color
        # The gate is how far from the last estimate a detection may be and still count as the target. With
        # gate_growth_m_s > 0 it widens while the target is unseen (gate_m + growth * seconds, up to max_gate_m), so
        # a target that walked on while undetected can be picked up again. 0 keeps the fixed gate of the spike.
        self.proj, self.hold, self.gate, self.lost_after = projector, hold_ticks, gate_m, lost_after
        self.growth, self.max_gate = gate_growth_m_s, max_gate_m
        self.t_seen = None
        self.state = "SEARCHING"
        self.est = None
        self.active = None
        self.last_seen = {}      # cam -> tick last seen target
        self.lost = 0
        self.events: list[dict] = []

    def _emit(self, tick, typ, cam=None, detail=None):
        self.events.append({"tick": tick, "type": typ, "cam": cam, "detail": detail})

    def project_detections(self, dets: dict, img_size: tuple[int, int]):
        W, H = img_size
        for cam, lst in dets.items():
            for d in lst:
                if d.get("color") not in COLORS:
                    continue
                bbox = d.get("bbox")
                xy = None
                if finite_point(bbox, 4):
                    x0, _, x1, y1 = bbox
                    xy = self.proj.ground(cam, x0 / 2 + x1 / 2, y1, W, H)
                d["est_xy"] = xy if finite_point(xy, 2) else None

    def seed(self, candidate: dict, capture_s: float, by: str) -> dict:
        tick = candidate["tick"]
        self.est = list(candidate["est_xy"])
        self.active = candidate["cam"]
        self.t_seen = capture_s
        self.state = "TRACKING"
        self.lost = 0
        self.last_seen = {self.active: tick}
        self.events = []
        self._emit(tick, "ACQUIRE", self.active, {"by": by})
        return self._result([self.active])

    def update(self, tick: int, dets: dict, img_size: tuple[int, int], t_s: float | None = None,
               *, projected: bool = False) -> dict:
        self.events = []
        t = tick * 0.5 if t_s is None else t_s
        gate = self.gate if not self.growth or self.t_seen is None else min(self.max_gate, self.gate + self.growth * max(0.0, t - self.t_seen))
        if not projected:
            self.project_detections(dets, img_size)
        cands = [
            (cam, det, det["est_xy"]) for cam, detections in dets.items() for det in detections
            if det.get("color") == self.target_color and det.get("est_xy") is not None
        ]
        seen = {}
        if self.state == "SEARCHING":
            # Standalone replays retain automatic acquisition for a single projected person.
            same = bool(cands) and all(math.dist(c[2], cands[0][2]) < 1.5 for c in cands)
            if same:
                best = max(cands, key=lambda c: c[1]["score"])
                self.est, self.state, self.active = best[2], "TRACKING", best[0]
                self.t_seen = t
                seen[best[0]] = best
                self._emit(tick, "ACQUIRE", best[0])
        else:
            near = [c for c in cands if math.dist(c[2], self.est) <= gate]
            if near:
                tgt = min(near, key=lambda c: math.dist(c[2], self.est))
                self.est = tgt[2]
                self.t_seen = t
                for c in near:
                    if math.dist(c[2], tgt[2]) < 1.5:
                        seen[c[0]] = c
                self.lost = 0
                if self.state == "LOST":
                    self.state = "TRACKING"
                    self._emit(tick, "REACQUIRE", tgt[0])
                    self.active = tgt[0]
            else:
                self.lost += 1
                if self.lost == 1:
                    self._emit(tick, "TARGET_OUT_OF_VIEW", self.active)
                if self.lost >= self.lost_after and self.state != "LOST":
                    self.state = "LOST"
                    self._emit(tick, "LOST", self.active)
        for cam in seen:
            self.last_seen[cam] = tick
        if self.state == "TRACKING" and self.active is not None:
            gap = tick - self.last_seen.get(self.active, -10**9)
            if gap >= self.hold and seen:
                new = max(seen.values(), key=lambda c: c[1]["bbox"][3] - c[1]["bbox"][1])[0]
                if new != self.active:
                    self._emit(tick, "SWITCH", new, {"from": self.active, "gap_ticks": gap})
                    self.active = new
        return self._result(seen)

    def _result(self, seen) -> dict:
        return {"state": self.state, "active_cam": self.active, "seen_cams": sorted(seen),
                "est_xy": self.est, "events": list(self.events), "lost_ticks": self.lost}

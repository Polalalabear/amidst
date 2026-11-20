"""Pinhole camera projection helpers (calibration only; no scoring, no Ground Truth).

Shared by the scene-context builder (inference side) and the offline coverage analysis in
``amidst.evaluation.live_coverage_gap``. Lives under ``q1q5`` so inference code never imports the evaluation package.
"""
from __future__ import annotations

import math


class Camera:
    """Pinhole camera; `c2w` is a Blender-convention 4x4 (camera looks along -Z, +Y up)."""

    def __init__(self, camera_id, c2w, fx, fy, width, height, near=0.05, far=100.0):
        self.camera_id = camera_id
        self.fx, self.fy = fx, fy
        self.cx, self.cy = width / 2.0, height / 2.0
        self.width, self.height = width, height
        self.near, self.far = near, far
        self.pos = tuple(c2w[i][3] for i in range(3))
        self.rot = [[c2w[r][c] for c in range(3)] for r in range(3)]  # columns = camera axes in world

    def to_camera(self, x, y, z):
        d = (x - self.pos[0], y - self.pos[1], z - self.pos[2])
        return tuple(sum(self.rot[r][c] * d[r] for r in range(3)) for c in range(3))  # R^T d

    def sees_point(self, x, y, z):
        px, py, pz = self.to_camera(x, y, z)
        depth = -pz
        if depth <= self.near or depth > self.far:
            return False
        u = self.cx + self.fx * px / depth
        v = self.cy - self.fy * py / depth
        return 0 <= u <= self.width and 0 <= v <= self.height


def make_camera(camera_id, pos, yaw_deg, pitch_deg, fx, fy, width=960, height=540):
    """Camera at `pos` (Blender x, y, z) looking along heading `yaw_deg` (0 = +x, 90 = +y), pitched down."""
    yaw, pit = math.radians(yaw_deg), math.radians(pitch_deg)
    fwd = (math.cos(yaw) * math.cos(pit), math.sin(yaw) * math.cos(pit), -math.sin(pit))
    right = (math.sin(yaw), -math.cos(yaw), 0.0)
    up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2], right[0] * fwd[1] - right[1] * fwd[0])
    back = tuple(-v for v in fwd)
    c2w = [[right[i], up[i], back[i], pos[i]] for i in range(3)] + [[0, 0, 0, 1]]
    return Camera(camera_id, c2w, fx, fy, width, height)

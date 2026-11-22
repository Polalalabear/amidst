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


# --------------------------------------------------------------------------------------------- wall-clipped coverage (F2, #656)
# Same algorithm as frontend/live-mode/src/coverage.mjs (tests compare the two): a ground point is covered when a body point at
# COVER_Z projects inside the image and the 2D sight line from the camera crosses no wall. Static geometry + calibration only.
COVER_Z = 0.9
STEP_DEG = 1.0
MARCH_M = 0.25
MAX_RANGE_M = 14.0


def is_wall(segment: dict) -> bool:
    """Vehicles (R004_ENV_*, 1.5 m high) are not walls; every other clearance segment is a full-height wall or screen."""
    return not str(segment.get('collider', '')).startswith('R004_ENV_')


def walls_of(geometry: dict) -> list:
    return [(s['a'][0], s['a'][1], s['b'][0], s['b'][1]) for s in geometry['clearance_segments'] if is_wall(s)]


def pose_of(entry: dict):
    m = entry['camera_to_world']
    pos = (m[0][3], m[1][3], m[2][3])
    fwd = (-m[0][2], -m[1][2], -m[2][2])
    return pos, math.atan2(fwd[1], fwd[0]), 2 * math.atan(entry['width'] / 2 / entry['fx'])


def sees_point(entry: dict, x: float, y: float, z: float) -> bool:
    m = entry['camera_to_world']
    d = (x - m[0][3], y - m[1][3], z - m[2][3])
    c = [m[0][j] * d[0] + m[1][j] * d[1] + m[2][j] * d[2] for j in range(3)]
    depth = -c[2]
    if depth <= entry.get('clip_start', 0.05) or depth > entry.get('clip_end', 100.0):
        return False
    u = entry['width'] / 2 + entry['fx'] * c[0] / depth
    v = entry['height'] / 2 - entry['fy'] * c[1] / depth
    return 0 <= u <= entry['width'] and 0 <= v <= entry['height']


def ray_hit(ox: float, oy: float, angle: float, walls) -> float:
    dx, dy = math.cos(angle), math.sin(angle)
    best = math.inf
    for ax, ay, bx, by in walls:
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((ax - ox) * ey - (ay - oy) * ex) / den
        s = ((ax - ox) * dy - (ay - oy) * dx) / den
        if t > 1e-9 and -1e-9 <= s <= 1 + 1e-9 and t < best:
            best = t
    return best


def visibility_polygon(entry: dict, walls, step_deg=STEP_DEG, march=MARCH_M, max_range=MAX_RANGE_M, z=COVER_Z) -> list:
    """Ring polygon [(x, y), ...] of the wall-clipped ground coverage (far boundary then near boundary); [] when nothing is seen."""
    pos, yaw, hfov = pose_of(entry)
    n = max(1, round(hfov / math.radians(step_deg)))
    near, far = [], []
    for i in range(n + 1):
        a = yaw - hfov / 2 + hfov * i / n
        wall = min(max_range, ray_hit(pos[0], pos[1], a, walls))
        first = last = None
        r = march
        while r < wall - 1e-9:
            x, y = pos[0] + r * math.cos(a), pos[1] + r * math.sin(a)
            if sees_point(entry, x, y, z):
                first = first or (x, y)
                last = (x, y)
            r += march
        if first:
            near.append(first)
            far.append(last)
    return far + near[::-1] if far else []


def point_in_polygon(x: float, y: float, poly) -> bool:
    inside, j = False, len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside

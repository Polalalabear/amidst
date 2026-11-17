import json
import math
from pathlib import Path

import numpy as np

from amidst.live_mode.color import judge
from amidst.live_mode.tracker import Projector, Tracker

GEOM = json.loads((Path(__file__).resolve().parents[2] / "docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json").read_text())


def _project(cam, x, y, z=0.0):
    M = np.array(cam["camera_to_world"])
    p = np.linalg.inv(M) @ np.array([x, y, z, 1.0])
    return cam["fx"] * p[0] / -p[2] + cam["cx"], -cam["fy"] * p[1] / -p[2] + cam["cy"]


def test_projector_round_trip_all_cameras():
    proj = Projector(GEOM["cameras"])
    for cam in GEOM["cameras"]:
        M = np.array(cam["camera_to_world"])
        look = M[:3, :3] @ np.array([0, 0, -1.0])
        # a floor point ~6 m along the camera heading
        t = 6.0
        x, y = M[0, 3] + look[0] * t, M[1, 3] + look[1] * t
        u, v = _project(cam, x, y)
        got = proj.ground(cam["camera_id"], u, v, cam["width"], cam["height"])
        assert got is not None and math.dist(got, [x, y]) < 1e-3


def _img(rgb, w=64, h=128):
    a = np.zeros((h, w, 3), np.uint8)
    a[:] = (120, 120, 120)
    a[10:70, 10:54] = rgb  # upper body
    return a


def test_color_red_and_blue_and_none():
    assert judge(_img((192, 24, 24)), [8, 8, 56, 120])["color"] == "red"
    assert judge(_img((37, 71, 200)), [8, 8, 56, 120])["color"] == "blue"
    assert judge(_img((120, 120, 120)), [8, 8, 56, 120])["color"] == "none"


def _det(box, color="red"):
    return {"bbox": box, "score": 0.9, "color": color, "red_ratio": 0.7, "blue_ratio": 0.0}


def test_tracker_acquires_then_switches_after_hold():
    proj = Projector(GEOM["cameras"])
    tr = Tracker(proj, hold_ticks=2)
    cam_a, cam_b = GEOM["cameras"][5], GEOM["cameras"][6]  # CAM_W1, CAM_W2
    M = np.array(cam_a["camera_to_world"])
    look = M[:3, :3] @ np.array([0, 0, -1.0])
    x, y = M[0, 3] + look[0] * 6, M[1, 3] + look[1] * 6
    ua, va = _project(cam_a, x, y); ub, vb = _project(cam_b, x, y)
    box = lambda u, v: [u - 8, v - 40, u + 8, v]
    W, H = cam_a["width"], cam_a["height"]
    out = tr.update(0, {cam_a["camera_id"]: [_det(box(ua, va))]}, (W, H))
    assert out["state"] == "TRACKING" and out["active_cam"] == cam_a["camera_id"]
    # target now only seen by camera B: switch only after the hold window
    seq = [tr.update(i, {cam_b["camera_id"]: [_det(box(ub, vb))]}, (W, H)) for i in (1, 2, 3)]
    assert seq[0]["active_cam"] == cam_a["camera_id"]
    assert seq[-1]["active_cam"] == cam_b["camera_id"]
    assert any(e["type"] == "SWITCH" for s in seq for e in s["events"])


def test_tracker_ignores_blue_and_far_red():
    proj = Projector(GEOM["cameras"])
    tr = Tracker(proj)
    cam = GEOM["cameras"][5]
    out = tr.update(0, {cam["camera_id"]: [_det([100, 100, 116, 140], "blue")]}, (cam["width"], cam["height"]))
    assert out["state"] == "SEARCHING"

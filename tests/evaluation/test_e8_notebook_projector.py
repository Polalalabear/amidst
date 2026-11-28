"""E8 (#780): Part 2 projector arithmetic in the Colab notebook (B1 gate stop on Colab, 2026-11-28; design §6.3.2).

Cell 8 swaps tracker.Projector.ground for ``ground_ieee``: the same maths with one fixed, plain-Python summation order,
so the B1 replay is bit-identical on arm64 (where B1 was frozen) and x86_64 (Colab). The gate itself stays exact.
"""

from __future__ import annotations

import ast
import json
import math
import random
from pathlib import Path

from amidst.evaluation import e8_handoff as H
from amidst.live_mode.tracker import Projector

NOTEBOOK = Path(__file__).resolve().parents[2] / "notebooks" / "e8_colab_eval.ipynb"


def cell8() -> str:
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    hits = ["".join(c["source"]) for c in cells if "".join(c["source"]).lstrip().startswith("# === CELL 8:")]
    assert len(hits) == 1
    return hits[0]


def ground_ieee():
    fn = [n for n in ast.parse(cell8()).body if isinstance(n, ast.FunctionDef) and n.name == "ground_ieee"]
    assert len(fn) == 1
    ns: dict = {}
    exec(compile(ast.Module(body=fn, type_ignores=[]), str(NOTEBOOK), "exec"), ns)
    return ns["ground_ieee"]


def camera(rng: random.Random, cid: str) -> dict:
    yaw, pitch = rng.uniform(-math.pi, math.pi), rng.uniform(0.3, 1.2)        # looking down at the floor
    cy_, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    R = [[cy_, -sy * cp, sy * sp], [sy, cy_ * cp, -cy_ * sp], [0.0, sp, cp]]
    t = [rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(2.5, 4.0)]
    M = [R[0] + [t[0]], R[1] + [t[1]], R[2] + [t[2]], [0.0, 0.0, 0.0, 1.0]]
    return {"camera_id": cid, "camera_to_world": M, "fx": 600.0, "fy": 600.0, "cx": 480.0, "cy": 270.0, "width": 960, "height": 540}


def test_ground_ieee_is_the_same_maths_with_a_fixed_order():
    rng = random.Random(780)
    proj = Projector([camera(rng, f"C{i}") for i in range(6)])
    g = ground_ieee()
    n_hit = 0
    for _ in range(3000):
        cam, u, v = f"C{rng.randrange(6)}", rng.uniform(0, 320), rng.uniform(0, 180)
        a, b = g(proj, cam, u, v, 320, 180), proj.ground(cam, u, v, 320, 180)
        assert (a is None) == (b is None)
        if a is None:
            continue
        n_hit += 1
        assert all(abs(x - y) <= 1e-9 * max(1.0, abs(y)) for x, y in zip(a, b))
        # the exact left-to-right reference: what every IEEE-754 CPU computes for plain Python floats
        M, fx, fy, cx, cy, W, Hh = proj.cams[cam]
        R, o = M[:3, :3].tolist(), M[:3, 3].tolist()
        x = ((u * W / 320 - cx) / fx, -(v * Hh / 180 - cy) / fy, -1.0)
        d = [(R[i][0] * x[0] + R[i][1] * x[1]) + R[i][2] * x[2] for i in range(3)]
        t = -o[2] / d[2]
        assert a == [o[0] + t * d[0], o[1] + t * d[1]]
    assert n_hit > 1000


def test_override_is_installed_before_the_b1_gate_and_recorded():
    src = cell8()
    assert 0 < src.index("_tracker.Projector.ground = ground_ieee") < src.index("RUN.b1_gate(PACK, _graph)")
    assert "design §6.3.2" in src and "RUN_DEVIATIONS.append" in src[: src.index("RUN.b1_gate(PACK, _graph)")]
    cells = ["".join(c["source"]) for c in json.loads(NOTEBOOK.read_text())["cells"]]
    cell9 = next(c for c in cells if c.lstrip().startswith("# === CELL 9:"))
    assert '"projector_arithmetic"' in cell9


def test_the_b1_gate_stays_exact():
    row = {"tracking": {"state": "TRACKING", "active_cam": "C1", "est_xy": [1.0, 2.0], "lost_ticks": 0, "box": None}}
    off = {"tracking": dict(row["tracking"], est_xy=[math.nextafter(1.0, 2.0), 2.0])}            # one ulp
    assert H.b1_reproduced([row], [row])["ok"] is True
    assert H.b1_reproduced([off], [row]) == {"ok": False, "n_rows": 1, "n_frozen": 1, "first_diff_index": 0}

"""K7 controlled-scene adapter on synthetic scenes only (no r003 assets)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from amidst.evaluation import k7_controlled_scene as k7

RULES = k7.RULES

BOX_FACES = [[0, 1, 3, 2], [2, 3, 7, 6], [6, 7, 5, 4], [4, 5, 1, 0], [2, 6, 4, 0], [7, 3, 1, 5]]


def box_vertices(lo: list[float], hi: list[float]) -> list[list[float]]:
    return [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def box_mesh(lo: list[float], hi: list[float]) -> k7.Mesh:
    return k7.Mesh(np.array(box_vertices(lo, hi), float), tuple(map(tuple, BOX_FACES)), "X", {})


def solid(sid: str, lo: list[float], hi: list[float], cls: str = "WALL") -> k7.Solid:
    return k7.Solid(
        sid, cls, np.array(lo, float), np.array(hi, float), box(lo[0], lo[1], hi[0], hi[1])
    )


def merged(meshes: list[k7.Mesh]) -> k7.Mesh:
    verts, faces = [], []
    for mesh in meshes:
        base = len(verts)
        verts.extend(mesh.vertices.tolist())
        faces.extend(tuple(i + base for i in f) for f in mesh.faces)
    return k7.Mesh(np.array(verts), tuple(faces), "X", {})


# ----------------------------------------------------------------------------- loading


def _write_bundle(root: Path, *, ref: str = "geometry/WALL_A.json", bad_hash: bool = False) -> None:
    (root / "geometry").mkdir(parents=True)
    wall = {"vertices_m": box_vertices([0, 0, 0], [1, 0.1, 3]), "faces": BOX_FACES, "encoding": "E"}
    floor = {"vertices_m": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], "faces": [[0, 1, 2, 3]]}
    blobs = {}
    for name, doc in (("WALL_A", wall), ("FLOOR_GROUND", floor)):
        data = json.dumps(doc).encode()
        (root / "geometry" / f"{name}.json").write_bytes(data)
        blobs[name] = hashlib.sha256(data).hexdigest()
    scene = {
        "floors": [
            {
                "floor_id": "FLOOR_GROUND",
                "geometry_ref": "geometry/FLOOR_GROUND.json",
                "geometry_sha256": blobs["FLOOR_GROUND"],
            }
        ],
        "objects": [
            {
                "id": "WALL_A",
                "geometry_ref": ref,
                "geometry_sha256": "0" * 64 if bad_hash else blobs["WALL_A"],
            }
        ],
        "walkable": [],
        "portals": [],
    }
    (root / "scene_static.json").write_text(json.dumps(scene))
    cams = {"cameras": [], "run_bindings": [{"run_id": "run-x", "camera_id": "CAM_A"}]}
    (root / "cameras.json").write_text(json.dumps(cams))


def test_load_verifies_geometry_hashes(tmp_path: Path) -> None:
    _write_bundle(tmp_path)
    scene = k7.load_safe_scene(tmp_path)
    assert scene.run_id == "run-x"
    assert all(c["match"] for c in scene.geometry_hash_checks)
    assert set(scene.meshes) == {"WALL_A", "FLOOR_GROUND"}


def test_load_reports_hash_mismatch_and_skips_mesh(tmp_path: Path) -> None:
    _write_bundle(tmp_path, bad_hash=True)
    scene = k7.load_safe_scene(tmp_path)
    assert [c["id"] for c in scene.geometry_hash_checks if not c["match"]] == ["WALL_A"]
    assert "WALL_A" not in scene.meshes


@pytest.mark.parametrize("ref", ["../outside.json", "/abs/WALL_A.json", "private/WALL_A.json"])
def test_load_rejects_refs_outside_geometry(tmp_path: Path, ref: str) -> None:
    _write_bundle(tmp_path, ref=ref)
    with pytest.raises(k7.InputError):
        k7.load_safe_scene(tmp_path)


def test_load_rejects_symlinked_geometry(tmp_path: Path) -> None:
    _write_bundle(tmp_path / "b", ref="geometry/LINK.json")
    (tmp_path / "b" / "geometry" / "LINK.json").symlink_to(
        tmp_path / "b" / "geometry" / "WALL_A.json"
    )
    with pytest.raises(k7.InputError):
        k7.load_safe_scene(tmp_path / "b")


# ----------------------------------------------------------------------------- solids


def test_mesh_box_check_matches_footprint_extrusion() -> None:
    s = solid("WALL_A", [0, 0, 0], [2, 0.12, 3.2])
    assert k7.mesh_box_check(box_mesh([0, 0, 0], [2, 0.12, 3.2]), s, 1e-6)["pass"]
    moved = k7.mesh_box_check(box_mesh([0, 0, 0], [2, 0.12, 3.0]), s, 1e-6)
    assert not moved["pass"]
    assert moved["max_deviation_from_footprint_extrusion_m"] == pytest.approx(0.2)


def test_mesh_box_check_rejects_open_mesh() -> None:
    s = solid("WALL_A", [0, 0, 0], [1, 1, 1])
    mesh = box_mesh([0, 0, 0], [1, 1, 1])
    open_mesh = k7.Mesh(mesh.vertices, mesh.faces[:5], "X", {})
    assert not k7.mesh_box_check(open_mesh, s, 1e-6)["edge_manifold_closed"]


def test_shell_equivalence_detects_missing_component() -> None:
    walls = [solid("WALL_A", [0, 0, 0], [2, 0.12, 3]), solid("WALL_B", [3, 0, 0], [5, 0.12, 3])]
    rules = {**RULES, "shell_samples_per_box": 400, "shell_samples_uniform": 400}
    full = merged([box_mesh(list(w.lo), list(w.hi)) for w in walls])
    assert k7.shell_equivalence(full, walls, rules)["pass"]
    partial = box_mesh(list(walls[0].lo), list(walls[0].hi))
    res = k7.shell_equivalence(partial, walls, rules)
    assert not res["pass"] and res["disagreements"] > 0


def test_seam_gaps_split_float_noise_from_real_gaps() -> None:
    a = solid("WALL_A", [0, 0, 0], [1, 0.12, 3])
    b = solid("WALL_B", [1 + 4.8e-7, 0, 0], [2, 0.12, 3])
    c = solid("WALL_C", [2 + 5e-4, 0, 0], [3, 0.12, 3])
    gaps = {(g["a"], g["b"]): g for g in k7.seam_gaps([a, b, c], 1e-3, 1e-5)}
    assert gaps[("WALL_A", "WALL_B")]["severity"] == "INFO"
    assert gaps[("WALL_A", "WALL_B")]["contact"] == "FACE"
    assert gaps[("WALL_B", "WALL_C")]["severity"] == "ERROR"
    assert ("WALL_A", "WALL_C") not in gaps


# ----------------------------------------------------------------------------- walkable


def _room_with_pocket(gap: float) -> tuple[Polygon, Polygon]:
    """Corridor y<3, wall y=[3,3.12] with a 1.2 m door at x=[5.4,6.6]; inside the room a
    screen x=[5,7] parallel to the wall, ``gap`` metres from the wall face."""
    corridor = box(0, 0, 10, 3)
    room = box(4, 3.12, 8, 7).union(box(5.4, 3.0, 6.6, 3.12))
    screen = box(5, 3.12 + gap, 7, 3.12 + gap + 0.15)
    return corridor, room.difference(screen)


def test_critical_radius_reports_pocket_behind_door() -> None:
    corridor, room = _room_with_pocket(0.48)
    crit = k7.critical_radius(corridor, room, 1e-3, 1.5)
    assert crit == pytest.approx(0.24, abs=2e-3)
    pair = corridor.union(room)
    assert k7.reach_fraction(pair, corridor, room, 0.30) < 0.99
    assert k7.reach_fraction(pair, corridor, room, 0.20) == pytest.approx(1.0)


def test_critical_radius_wide_gap_is_door_limited() -> None:
    corridor, room = _room_with_pocket(0.88)
    assert k7.critical_radius(corridor, room, 1e-3, 1.5) >= 0.30


def _walk_scene(walk_ring: list[tuple[float, float]]) -> tuple[dict[str, Any], dict[str, k7.Mesh]]:
    scene = {
        "floors": [{"floor_id": "FLOOR_GROUND"}],
        "walkable": [{"id": "WALK_C", "polygon_m": walk_ring, "holes_m": []}],
    }
    floor = k7.Mesh(
        np.array([[0, 0, 0], [10, 0, 0], [10, 3, 0], [0, 3, 0]], float), ((0, 1, 2, 3),), "X", {}
    )
    walk_mesh = k7.Mesh(
        np.array([[x, y, 0.0] for x, y in walk_ring]), (tuple(range(len(walk_ring))),), "X", {}
    )
    return scene, {"FLOOR_GROUND": floor, "WALK_C": walk_mesh}


def test_walk_checks_matches_floor_minus_footprint() -> None:
    ring = [(0, 0), (5, 0), (5, 1), (5.15, 1), (5.15, 0), (10, 0), (10, 3), (0, 3)]
    scene, meshes = _walk_scene(ring)
    screen = solid("OBSTACLE_S", [5, 0, 0], [5.15, 1, 3.2], "OBSTACLE")
    lintel = solid("WALL_L", [0, 2.9, 2.4], [10, 3, 3.2])
    res = k7.walk_checks(
        scene, meshes, [screen, lintel], RULES, {"WALK_C": [(0, 0), (10, 0), (10, 3), (0, 3)]}
    )
    walk = res["per_walk"]["WALK_C"]
    assert walk["derived_iou"] == pytest.approx(1.0)
    assert walk["solid_penetration_m"] == 0.0
    assert walk["mesh_symmetric_difference_m2"] == pytest.approx(0.0)
    assert res["above_band_solid_ids"] == ["WALL_L"]


def test_walk_checks_flags_walk_over_solid() -> None:
    scene, meshes = _walk_scene([(0, 0), (10, 0), (10, 3), (0, 3)])
    screen = solid("OBSTACLE_S", [5, 0, 0], [5.15, 1, 3.2], "OBSTACLE")
    res = k7.walk_checks(
        scene, meshes, [screen], RULES, {"WALK_C": [(0, 0), (10, 0), (10, 3), (0, 3)]}
    )
    walk = res["per_walk"]["WALK_C"]
    assert walk["solid_penetration_m"] == pytest.approx(0.15, abs=1e-6)
    assert walk["derived_iou"] < 0.999
    assert walk["extra_vs_derived"][0]["area_m2"] == pytest.approx(0.15)


def test_derived_adjacency_ignores_edges_behind_solids() -> None:
    a, b = box(0, 0, 2, 2), box(2, 0, 4, 2)
    wall = box(1.9, 0, 2.1, 2)
    assert k7.derived_adjacency({"A": a, "B": b}, wall, 0.05) == {}
    assert k7.derived_adjacency({"A": a, "B": b}, box(1.9, 0, 2.1, 1), 0.05)[
        ("A", "B")
    ] == pytest.approx(1.0)


# ----------------------------------------------------------------------------- cameras


def _camera(pos: list[float]) -> dict[str, Any]:
    # Looking along +x, horizontal: camera -Z = world +x, camera +Y = world +z.
    rot = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], float)
    m = np.eye(4)
    m[:3, :3] = rot
    m[:3, 3] = pos
    return {
        "camera_id": "CAM_T",
        "camera_to_world": m.tolist(),
        "fx": 300.0,
        "fy": 300.0,
        "cx": 320.0,
        "cy": 240.0,
        "width": 640,
        "height": 480,
        "clip_start": 0.05,
        "clip_end": 60.0,
    }


def test_segment_box_hits_blocks_floor_behind_screen() -> None:
    screen = solid("OBSTACLE_S", [4, -1, 0], [4.15, 1, 3.2], "OBSTACLE")
    origin = np.array([0.0, 0.0, 1.5])
    pts = np.array([[3.0, 0.0, 0.0], [8.0, 0.0, 0.0], [8.0, 5.0, 0.0]])
    blocked, _ = k7.segment_box_hits(origin, pts, [screen])
    assert blocked.tolist() == [False, True, False]


def test_camera_visibility_and_crosscheck_agree() -> None:
    screen = solid("OBSTACLE_S", [4, -1, 0], [4.15, 1, 3.2], "OBSTACLE")
    floor = box(0.5, -3, 12, 3)
    grid = k7.floor_grid(floor.difference(screen.footprint), 0.1)
    cam = _camera([0.0, 0.0, 1.5])
    res = k7.camera_visibility(cam, grid, 0.1, [screen], {"FLOOR": floor})
    assert 0 < res.summary["visible_floor_m2"] < res.summary["in_view_floor_m2"]
    assert not res.summary["inside_solid"]
    cross = k7.raycast_crosscheck(cam, grid, [screen], [box_mesh([4, -1, 0], [4.15, 1, 3.2])], 1e-4)
    assert cross["disagreements"] == 0 and cross["blocked_boxes"] > 0


def test_camera_rays_rejects_points_behind_camera() -> None:
    rays = k7.camera_rays(_camera([0.0, 0.0, 1.5]), np.array([[5.0, 0.0, 1.5], [-5.0, 0.0, 1.5]]))
    assert rays["in_view"].tolist() == [True, False]
    assert rays["u"][0] == pytest.approx(320.0)


# ----------------------------------------------------------------------------- portals


def _door_scene() -> tuple[dict[str, Any], dict[str, Polygon], list[k7.Solid], dict[str, k7.Mesh]]:
    solids = [
        solid("WALL_W1", [0, 3, 0], [5.4, 3.12, 3.2]),
        solid("WALL_W2", [6.6, 3, 0], [10, 3.12, 3.2]),
        solid("WALL_LINTEL", [5.4, 3, 2.4], [6.6, 3.12, 3.2]),
    ]
    walks = {"WALK_C": box(0, 0, 10, 3), "WALK_R": box(4, 3.12, 8, 7).union(box(5.4, 3, 6.6, 3.12))}
    portal = {
        "id": "PORTAL_D",
        "opening_m": {
            "a": [5.4, 3.0],
            "b": [6.6, 3.0],
            "width_m": 1.2,
            "sill_z_m": 0.0,
            "height_m": 2.4,
        },
        "connects": ["WALK_C", "WALK_R"],
    }
    marker = k7.Mesh(
        np.array([[5.4, 3, 0], [6.6, 3, 0], [6.6, 3, 2.4], [5.4, 3, 2.4]], float),
        ((0, 1, 2, 3),),
        "X",
        {},
    )
    return {"portals": [portal]}, walks, solids, {"PORTAL_D": marker}


def test_portal_checks_on_clean_door() -> None:
    scene, walks, solids, meshes = _door_scene()
    rows = [{"via_portal_id": "PORTAL_D", "critical_radius_m": 0.6, "passable_envelope_r030": True}]
    res = k7.portal_checks(scene, meshes, walks, solids, rows, RULES)["PORTAL_D"]
    assert res["measured_clear_width_m"] == pytest.approx(1.2)
    assert res["jambs_present"] and res["lintel_above_opening"] and res["marker_mesh_matches"]
    assert res["crossing_walks"] == ["WALK_C", "WALK_R"] and res["crossing_matches_connects"]


def test_portal_checks_detect_narrowed_opening() -> None:
    scene, walks, solids, meshes = _door_scene()
    solids.append(solid("OBSTACLE_IN_DOOR", [6.3, 3, 0], [6.6, 3.12, 2.0], "OBSTACLE"))
    res = k7.portal_checks(scene, meshes, walks, solids, [], RULES)["PORTAL_D"]
    assert res["measured_clear_width_m"] == pytest.approx(0.9)
    assert not res["clear_width_matches"]


# ----------------------------------------------------------------------------- verdicts


def _matrix(*, mesh_pass: bool = True, passable: bool = True) -> dict[tuple[str, str], str]:
    scene = {
        "objects": [
            {
                "id": "WALL_A",
                "class": "WALL",
                "allowed_purposes": ["OCCLUSION", "COLLISION", "DISPLAY"],
                "collision_scope": "EXACT_MESH",
            },
            {"id": "PORTAL_D", "class": "PORTAL", "allowed_purposes": ["WALKABILITY"]},
            {"id": "WALK_C", "class": "WALKABLE", "allowed_purposes": ["WALKABILITY"]},
        ],
        "walkable": [{"id": "WALK_C"}],
    }
    walks = {
        "body_band_solid_ids": ["WALL_A"],
        "per_walk": {
            "WALK_C": {
                "mesh_symmetric_difference_m2": 0.0,
                "mesh_hausdorff_m": 0.0,
                "outside_floor_m2": 0.0,
                "solid_penetration_m": 1.9e-6,
                "derived_iou": 0.9999995,
            }
        },
    }
    portal = {
        "clear_width_matches": True,
        "jambs_present": True,
        "lintel_above_opening": True,
        "marker_mesh_matches": True,
        "crossing_matches_connects": True,
        "crossing_inside_walkable": True,
        "passable_envelope_r030": passable,
        "critical_radius_m": 0.6 if passable else 0.24,
    }
    rows = k7.purpose_matrix(
        scene,
        {"WALL_A": True, "PORTAL_D": True, "WALK_C": True},
        {"WALL_A": {"pass": mesh_pass}},
        {"WALL_A": {"pass": True}},
        {"pass": True},
        [{"severity": "INFO"}],
        [{"disagreements": 0}],
        walks,
        {"declared": [], "undeclared_adjacency": []},
        {"PORTAL_D": portal},
        RULES,
    )
    return {(r["id"], r["purpose"]): r["verdict"] for r in rows}


def test_purpose_matrix_approves_clean_scene() -> None:
    verdicts = _matrix()
    assert set(verdicts.values()) == {"APPROVE"}


def test_purpose_matrix_fix_when_mesh_fails() -> None:
    verdicts = _matrix(mesh_pass=False)
    assert verdicts[("WALL_A", "OCCLUSION")] == "FIX"
    assert verdicts[("WALL_A", "DISPLAY")] == "APPROVE"


def test_purpose_matrix_rejects_impassable_portal_only() -> None:
    verdicts = _matrix(passable=False)
    assert verdicts[("PORTAL_D", "WALKABILITY")] == "REJECT"
    assert verdicts[("WALK_C", "WALKABILITY")] == "APPROVE"


def test_canonical_hash_ignores_private_keys_and_order() -> None:
    a = k7.strip_private({"b": 1, "a": [1, {"_g": object(), "c": 2}]})
    b = {"a": [1, {"c": 2}], "b": 1}
    assert k7.canonical_sha256(a) == k7.canonical_sha256(b)

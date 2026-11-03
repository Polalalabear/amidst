"""K7 map verification adapter for the controlled scene (``controlled-l-corridor``).

Pure functions over the safe static side only: ``scene_static.json``, the ``geometry/*.json``
files it references (hash-verified) and ``cameras.json``.  No RGB content, Ground Truth,
person routes, renderer visibility or depth is read.  The verifier never edits its inputs; it
reports per object and per purpose so a human can approve purposes (contract v1.1 §3.3, §3.4,
O10).  ``RULES`` and ``DECISION_RULES`` are fixed before any scene is judged.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from amidst.evaluation.map_verification import iou, polygons_of

REACH_FRACTION_MIN = 0.99

VERIFIER = "amidst.evaluation.k7_controlled_scene"
VERIFIER_VERSION = "k7-controlled-scene.v1"
SCHEMA = "controlled-scene.k7-map-verification.v1"

RULES: dict[str, Any] = {
    "version": "k7-controlled-scene-rules.v1.1",
    # D42: "not visible" envelope 1.80 m / r 0.30; "visible" nominal body r 0.25.
    "body_band_z_m": [0.0, 1.80],
    "envelope_radius_m": 0.30,
    "nominal_radius_m": 0.25,
    # D58: penetration (max inscribed circle diameter) <= 1e-5 m is float32 noise.
    "penetration_tol_m": 1e-5,
    "vertex_match_tol_m": 1e-6,
    "polygon_match_area_tol_m2": 1e-6,
    "polygon_match_hausdorff_m": 1e-5,
    "derived_iou_min": 0.9999,
    "report_block_min_area_m2": 1e-4,
    "adjacency_min_shared_m": 0.05,
    # Gaps between solids up to 1 mm are reported; <= penetration_tol_m is float32 noise (INFO,
    # same basis as D58), larger is ERROR.  rules v1.1 change, see RULES_CHANGELOG.
    "seam_gap_max_m": 1e-3,
    "shell_samples_per_box": 1500,
    "shell_samples_uniform": 20000,
    "shell_sample_pad_m": 0.03,
    "shell_boundary_exclusion_m": 1e-5,
    "sample_seed": 20261020,
    "floor_grid_step_m": 0.05,
    "crosscheck_grid_step_m": 0.10,
    "grazing_chord_m": 1e-4,
    "portal_probe_m": 0.02,
    "critical_radius_tol_m": 1e-3,
    "critical_radius_max_m": 1.5,
    "reach_fraction_min": 0.99,
}

RULES_CHANGELOG: list[str] = [
    "v1 -> v1.1 (after the first r003 run, before any verdict was reported): seam gaps "
    "<= penetration_tol_m (1e-5 m, D58 float32 basis) are INFO instead of failing the "
    "no_seam_gap gate; every gap is still listed with its measured width.  No other "
    "threshold changed.",
    "v1 -> v1.1 (implementation bug, found on the first r003 run): connection reachability "
    "now requires the component joining both walks to hold >= reach_fraction_min of both "
    "walks' eroded interiors; v1 counted a doorway sliver / pocket of the far walk as reached.",
]

DECISION_RULES: dict[str, str] = {
    "OCCLUSION": (
        "APPROVE when the geometry file hash matches, the mesh is a closed edge-manifold solid "
        "equal to its footprint x [base_z, base_z + height] within vertex_match_tol_m, walls "
        "agree with the joined shell on every non-boundary sample, every seam gap between solids "
        "is <= penetration_tol_m (INFO), and camera-to-floor raycasts over component meshes and "
        "over shell + obstacle meshes disagree on 0 non-grazing rays; otherwise FIX."
    ),
    "VISIBILITY_INDEX": "Same object-level gates as OCCLUSION (it is the same raycast geometry).",
    "COLLISION": (
        "APPROVE when the OCCLUSION mesh gates pass and, for solids intersecting the body band, "
        "the penetration into walkable is <= penetration_tol_m; solids entirely above the band "
        "are APPROVE with note ABOVE_BODY_BAND; otherwise FIX."
    ),
    "WALKABILITY": (
        "Walk: APPROVE when polygon_m equals its mesh (sym. diff <= polygon_match_area_tol_m2, "
        "Hausdorff <= polygon_match_hausdorff_m), lies on the floor, is not penetrated by "
        "body-band solids, matches floor - solids within its design pre-cut owner region "
        "(IoU >= derived_iou_min), and every derived adjacency is declared; otherwise FIX. "
        "Portal: APPROVE when the opening is a clear gap of width_m between two jambs, its "
        "marker mesh equals opening_m, the crossing joins exactly connects[], and the two walks "
        "stay connected for a body-centre disc of envelope_radius_m; when only the last gate "
        "fails the portal is REJECT for metric reachability (topology only)."
    ),
    "DISPLAY": (
        "APPROVE when the geometry file hash matches and the geometry bounds equal bounds_m "
        "within vertex_match_tol_m; DISPLAY never feeds inference."
    ),
}

VERDICT_TEXT = {"APPROVE": "建議核准", "REJECT": "建議不核准", "FIX": "需修正"}

# Design reference (#54, CONTROLLED_SCENE_B_DESIGN_20261018.md @ 812817f, appendix A
# WALK_POLYGONS): literal pre-cut walk polygons.  Used only to assign derived free floor to an
# owner walk; the design boxes are not used (OBS-004 already compares them).
DESIGN_REFERENCE: dict[str, Any] = {
    "commit": "812817f29c74b8589f6cdf613966eba5d936755f",
    "path": "docs/engineering/CONTROLLED_SCENE_B_DESIGN_20261018.md",
    "file_sha256": "da262df528d9ad0aac3482c6932f29aa73ddd0d9f6f1bf6c847acc5de7263d29",
    "section": "附錄A WALK_POLYGONS（§1.1 扣除前 polygon）",
}
DESIGN_PRECUT_WALKS: dict[str, list[tuple[float, float]]] = {
    "WALK_VEST_W": [(-3.2, -2), (5, -2), (5, 0), (0, 0), (0, 2.4), (-3.2, 2.4)],
    "WALK_CORR_W": [(0, 0), (15, 0), (15, 2.4), (0, 2.4)],
    "WALK_CORNER": [(15, 0), (17.4, 0), (17.4, 2.4), (15, 2.4)],
    "WALK_CORR_N": [(15, 2.4), (17.4, 2.4), (17.4, 12), (15, 12)],
    "WALK_R101": [(5, -5), (11, -5), (11, 0), (5, 0)],
    "WALK_R102": [(17.4, 7), (22.4, 7), (22.4, 11), (17.4, 11)],
}

PURPOSE_USES: dict[str, list[str]] = {
    "OCCLUSION": [
        "2b：腳點像素帶 +2 px 的靜態遮擋檢查與 occlusion_near（契約 §6.3.1 第 1–2 步）",
        "2c：靜態 raycast 可見範圍索引的遮擋面",
    ],
    "VISIBILITY_INDEX": [
        "2c：SOURCE_MESH_RAYCAST 地面足跡（visibility_index_ref）",
        "2d：負證據 visible_floor（盲區假設契約 §3.3）",
    ],
    "COLLISION": ["2d：K1 人體中心可達區（walkable 依包絡半徑內縮）與淨空判定"],
    "WALKABILITY": [
        "2d：K1 polygon_floor_map 的 regions／portals",
        "2c：O11 以 portal 連通定義的通路",
    ],
    "DISPLAY": ["前端 3D 場景顯示；不進任何推論"],
}

VALIDATOR_COVERAGE: dict[str, list[str]] = {
    "OCCLUSION": ["OBS-001", "OBS-004", "SCH-005", "APR-001", "APR-002", "HSH-001"],
    "VISIBILITY_INDEX": ["OBS-001", "OBS-004", "CAM-001", "CAM-002", "CAM-004", "CAM-005"],
    "COLLISION": ["OBS-001", "OBS-002", "OBS-003", "OBS-004", "SCH-005"],
    "WALKABILITY": [
        "FLR-001",
        "WLK-001",
        "WLK-002",
        "WLK-003",
        "WLK-004",
        "WLK-005",
        "WLK-006",
        "PRT-001",
        "PRT-002",
    ],
    "DISPLAY": ["ID-002", "ID-003", "ID-005", "APR-002", "APR-003"],
}


# ----------------------------------------------------------------------------- loading


class InputError(ValueError):
    """A safe input is missing, outside the bundle, or fails its pinned hash."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(text.encode("utf-8"))


def _safe_ref(root: Path, ref: str) -> Path:
    """Resolve a bundle-relative ``geometry/*.json`` ref; reject traversal and symlinks."""
    posix = PurePosixPath(ref)
    if posix.is_absolute() or ".." in posix.parts or posix.parts[:1] != ("geometry",):
        raise InputError(f"geometry ref outside geometry/: {ref!r}")
    path = root.joinpath(*posix.parts)
    if path.is_symlink():
        raise InputError(f"geometry ref is a symlink: {ref!r}")
    resolved = path.resolve()
    if root.resolve() not in resolved.parents:
        raise InputError(f"geometry ref escapes the bundle: {ref!r}")
    return resolved


@dataclass(frozen=True)
class Mesh:
    vertices: np.ndarray  # (n, 3)
    faces: tuple[tuple[int, ...], ...]
    encoding: str
    meta: Mapping[str, Any]

    def triangles(self) -> np.ndarray:
        tris = [(f[0], f[k], f[k + 1]) for f in self.faces for k in range(1, len(f) - 1)]
        return self.vertices[np.asarray(tris, dtype=int)]  # (t, 3, 3)


@dataclass(frozen=True)
class SafeScene:
    """The safe static inputs of one run, hash-verified."""

    run_id: str
    scene: Mapping[str, Any]
    cameras: Mapping[str, Any]
    meshes: Mapping[str, Mesh]
    input_hashes: Mapping[str, str]
    geometry_hash_checks: tuple[dict[str, Any], ...]


def _geometry_refs(scene: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    refs: list[tuple[str, str, str]] = []
    for item in scene.get("floors", []):
        refs.append((item["floor_id"], item["geometry_ref"], item["geometry_sha256"]))
    for key in ("objects", "walkable", "portals"):
        for item in scene.get(key, []):
            refs.append((item["id"], item["geometry_ref"], item["geometry_sha256"]))
    if scene.get("active_wall_geometry_ref"):
        refs.append(
            (
                "ACTIVE_WALL_SHELL",
                scene["active_wall_geometry_ref"],
                scene["active_wall_geometry_sha256"],
            )
        )
    return refs


def load_safe_scene(safe_dir: Path) -> SafeScene:
    """Read ``scene_static.json``, ``cameras.json`` and the referenced geometry files only."""
    files: dict[str, bytes] = {}
    for name in ("scene_static.json", "cameras.json"):
        path = safe_dir / name
        if path.is_symlink() or not path.is_file():
            raise InputError(f"missing or symlinked safe file: {name}")
        files[name] = path.read_bytes()
    scene = json.loads(files["scene_static.json"])
    cameras = json.loads(files["cameras.json"])
    run_ids = sorted({b["run_id"] for b in cameras.get("run_bindings", [])})
    if len(run_ids) != 1:
        raise InputError("cameras.json must bind exactly one run")
    hashes = {name: sha256_bytes(data) for name, data in files.items()}
    meshes: dict[str, Mesh] = {}
    checks: list[dict[str, Any]] = []
    for owner, ref, expected in _geometry_refs(scene):
        path = _safe_ref(safe_dir, ref)
        data = path.read_bytes()
        actual = sha256_bytes(data)
        hashes[ref] = actual
        checks.append({"id": owner, "ref": ref, "match": actual == expected})
        if actual != expected:
            continue
        doc = json.loads(data)
        meshes[owner] = Mesh(
            vertices=np.asarray(doc["vertices_m"], dtype=float),
            faces=tuple(tuple(int(i) for i in f) for f in doc["faces"]),
            encoding=str(doc.get("encoding")),
            meta={k: v for k, v in doc.items() if k not in ("vertices_m", "faces")},
        )
    return SafeScene(run_ids[0], scene, cameras, meshes, hashes, tuple(checks))


# ----------------------------------------------------------------------------- geometry


def _ring(points: Iterable[Sequence[float]]) -> list[tuple[float, float]]:
    return [(float(p[0]), float(p[1])) for p in points]


def walk_polygon(walk: Mapping[str, Any]) -> Polygon:
    return Polygon(_ring(walk["polygon_m"]), [_ring(h) for h in walk.get("holes_m") or []])


def mesh_xy_union(mesh: Mesh) -> BaseGeometry:
    """Union of the mesh faces projected to XY (for flat marker meshes)."""
    polys = []
    for face in mesh.faces:
        poly = Polygon([tuple(mesh.vertices[i][:2]) for i in face])
        if poly.area > 0:
            polys.append(poly if poly.is_valid else shapely.make_valid(poly))
    return polygons_of(unary_union(polys)) if polys else Polygon()


@dataclass(frozen=True)
class Solid:
    id: str
    cls: str
    lo: np.ndarray  # (3,)
    hi: np.ndarray  # (3,)
    footprint: Polygon

    def in_body_band(self, band: Sequence[float]) -> bool:
        return bool(self.lo[2] < band[1] and self.hi[2] > band[0])


def solids_of(scene: Mapping[str, Any]) -> list[Solid]:
    out = []
    for obj in scene["objects"]:
        if obj["class"] not in ("WALL", "OBSTACLE"):
            continue
        fp = Polygon(_ring(obj["footprint_m"]))
        x0, y0, x1, y1 = fp.bounds
        base = float(obj["base_z_m"])
        top = base + float(obj["height_m"])
        out.append(
            Solid(obj["id"], obj["class"], np.array([x0, y0, base]), np.array([x1, y1, top]), fp)
        )
    return out


def mesh_box_check(mesh: Mesh, solid: Solid, tol: float) -> dict[str, Any]:
    """Is the mesh a closed edge-manifold axis-aligned box equal to the footprint extrusion?"""
    v = mesh.vertices
    lo, hi = v.min(axis=0), v.max(axis=0)
    at_corner = bool(np.all(np.isclose(v, lo, atol=tol) | np.isclose(v, hi, atol=tol)))
    edges: dict[tuple[int, int], int] = {}
    for face in mesh.faces:
        for a, b in zip(face, face[1:] + face[:1], strict=True):
            key = (min(a, b), max(a, b))
            edges[key] = edges.get(key, 0) + 1
    manifold = bool(edges) and all(count == 2 for count in edges.values())
    deviation = float(np.abs(np.r_[lo - solid.lo, hi - solid.hi]).max())
    rectangle = bool(abs(solid.footprint.area - box(*solid.footprint.bounds).area) <= tol)
    return {
        "vertices": int(len(v)),
        "faces": len(mesh.faces),
        "axis_aligned_box": at_corner and len(v) == 8,
        "edge_manifold_closed": manifold,
        "footprint_is_rectangle": rectangle,
        "max_deviation_from_footprint_extrusion_m": deviation,
        "pass": at_corner and len(v) == 8 and manifold and rectangle and deviation <= tol,
    }


def points_in_boxes(points: np.ndarray, solids: Sequence[Solid]) -> np.ndarray:
    lo = np.stack([s.lo for s in solids])
    hi = np.stack([s.hi for s in solids])
    inside = (points[:, None, :] > lo[None]) & (points[:, None, :] < hi[None])
    return np.asarray(inside.all(axis=2).any(axis=1))


def _boundary_distance(points: np.ndarray, solids: Sequence[Solid]) -> np.ndarray:
    lo = np.stack([s.lo for s in solids])[None]
    hi = np.stack([s.hi for s in solids])[None]
    p = points[:, None, :]
    outside = np.linalg.norm(np.maximum(np.maximum(lo - p, p - hi), 0.0), axis=2)
    inside = np.minimum(p - lo, hi - p).min(axis=2)
    dist = np.where(outside > 0, outside, np.abs(inside))
    return np.asarray(dist.min(axis=1))


def ray_triangle_hits(
    origins: np.ndarray, directions: np.ndarray, tris: np.ndarray, t_max: float, chunk: int = 512
) -> np.ndarray:
    """Count Möller–Trumbore hits with 1e-9 < t < t_max (directions need not be unit)."""
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = b - a, c - a
    out = np.zeros(len(origins), dtype=int)
    for start in range(0, len(origins), chunk):
        o = origins[start : start + chunk, None, :]
        d = directions[start : start + chunk, None, :]
        h = np.cross(d, e2[None])
        det = np.einsum("ijk,jk->ij", h, e1)
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = o - a[None]
        u = inv * np.einsum("ijk,ijk->ij", s, h)
        q = np.cross(s, e1[None])
        v = inv * np.einsum("ijk,ijk->ij", d, q)
        t = inv * np.einsum("ijk,jk->ij", q, e2)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9) & (t < t_max)
        out[start : start + chunk] = hit.sum(axis=1)
    return out


def points_in_mesh(points: np.ndarray, mesh: Mesh) -> np.ndarray:
    direction = np.array([0.937, 0.283, 0.205])
    direction = direction / np.linalg.norm(direction)
    dirs = np.broadcast_to(direction, points.shape).copy()
    hits = ray_triangle_hits(points, dirs, mesh.triangles(), t_max=1e6)
    return np.asarray(hits % 2 == 1)


def shell_equivalence(
    shell: Mesh, walls: Sequence[Solid], rules: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare occupancy of the joined wall shell with the union of wall component boxes."""
    rng = np.random.default_rng(int(rules["sample_seed"]))
    pad = float(rules["shell_sample_pad_m"])
    samples = [
        rng.uniform(s.lo - pad, s.hi + pad, size=(int(rules["shell_samples_per_box"]), 3))
        for s in walls
    ]
    lo, hi = shell.vertices.min(axis=0) - pad, shell.vertices.max(axis=0) + pad
    samples.append(rng.uniform(lo, hi, size=(int(rules["shell_samples_uniform"]), 3)))
    points = np.concatenate(samples)
    keep = _boundary_distance(points, walls) > float(rules["shell_boundary_exclusion_m"])
    points = points[keep]
    in_boxes = points_in_boxes(points, walls)
    in_shell = points_in_mesh(points, shell)
    edges: dict[tuple[int, int], int] = {}
    for face in shell.faces:
        for a, b in zip(face, face[1:] + face[:1], strict=True):
            key = (min(a, b), max(a, b))
            edges[key] = edges.get(key, 0) + 1
    shell_lo, shell_hi = shell.vertices.min(axis=0), shell.vertices.max(axis=0)
    comp_lo = np.min([s.lo for s in walls], axis=0)
    comp_hi = np.max([s.hi for s in walls], axis=0)
    return {
        "samples": int(len(points)),
        "excluded_near_boundary": int((~keep).sum()),
        "inside_components": int(in_boxes.sum()),
        "inside_shell": int(in_shell.sum()),
        "disagreements": int((in_boxes != in_shell).sum()),
        "shell_vertices": int(len(shell.vertices)),
        "shell_faces": len(shell.faces),
        "shell_edge_use_counts": sorted({int(v) for v in edges.values()}),
        "bounds_deviation_m": float(np.abs(np.r_[shell_lo - comp_lo, shell_hi - comp_hi]).max()),
        "pass": bool((in_boxes == in_shell).all()),
    }


def seam_gaps(solids: Sequence[Solid], max_gap: float, noise_max: float) -> list[dict[str, Any]]:
    """Pairs of solids separated by a positive gap <= max_gap (a ray could slip through).

    Gaps <= ``noise_max`` (the D58 float32 tolerance) are ``INFO``; larger ones are ``ERROR``.
    The thinner of the two solids bounds the angle a ray needs to pass: gap / thickness."""
    out = []
    for i, a in enumerate(solids):
        for b in solids[i + 1 :]:
            sep = np.maximum(np.maximum(a.lo - b.hi, b.lo - a.hi), 0.0)
            gap = float(np.linalg.norm(sep))
            if 0.0 < gap <= max_gap:
                axis = int(np.argmax(sep))
                depth = float(min(a.hi[axis] - a.lo[axis], b.hi[axis] - b.lo[axis]))
                others = [k for k in range(3) if k != axis]
                thick = min(float(min(a.hi[k], b.hi[k]) - max(a.lo[k], b.lo[k])) for k in others)
                out.append(
                    {
                        "a": a.id,
                        "b": b.id,
                        "gap_m": gap,
                        "gap_axis": "xyz"[axis],
                        "contact": "FACE" if thick > 0 else "EDGE_OR_CORNER",
                        "max_pass_angle_rad": gap / max(thick, 1e-12) if thick > 0 else 0.0,
                        "solid_depth_along_gap_m": depth,
                        "severity": "INFO" if gap <= noise_max else "ERROR",
                    }
                )
    return out


def max_penetration(geom: BaseGeometry) -> float:
    widest = 0.0
    for part in getattr(polygons_of(geom), "geoms", [polygons_of(geom)]):
        if part.is_empty or part.area <= 0:
            continue
        radius = shapely.maximum_inscribed_circle(part, 1e-9).length
        widest = max(widest, 2.0 * float(radius))
    return widest


# ----------------------------------------------------------------------------- walkable


def _blocks(geom: BaseGeometry, min_area: float) -> list[dict[str, Any]]:
    out = []
    for part in getattr(polygons_of(geom), "geoms", [polygons_of(geom)]):
        if part.is_empty or part.area < min_area:
            continue
        x0, y0, x1, y1 = part.bounds
        out.append(
            {
                "area_m2": float(part.area),
                "bounds_xy_m": [x0, y0, x1, y1],
                "penetration_m": max_penetration(part),
            }
        )
    return sorted(out, key=lambda b: -b["area_m2"])


def walk_checks(
    scene: Mapping[str, Any],
    meshes: Mapping[str, Mesh],
    solids: Sequence[Solid],
    rules: Mapping[str, Any],
    precut_walks: Mapping[str, Sequence[tuple[float, float]]] | None = None,
) -> dict[str, Any]:
    band = rules["body_band_z_m"]
    floor_id = scene["floors"][0]["floor_id"]
    floor = mesh_xy_union(meshes[floor_id]) if floor_id in meshes else Polygon()
    floor_z = (
        sorted({float(z) for z in meshes[floor_id].vertices[:, 2]}) if floor_id in meshes else []
    )
    band_solids = [s for s in solids if s.in_body_band(band)]
    solid_union = unary_union([s.footprint for s in band_solids])
    free = floor.difference(solid_union)
    walks = {w["id"]: walk_polygon(w) for w in scene["walkable"]}
    walk_union = unary_union(list(walks.values()))
    precut = {k: Polygon(v) for k, v in (precut_walks or DESIGN_PRECUT_WALKS).items()}
    per_walk: dict[str, dict[str, Any]] = {}
    for wid, poly in sorted(walks.items()):
        mesh = meshes.get(wid)
        mesh_poly = mesh_xy_union(mesh) if mesh is not None else Polygon()
        sym = poly.symmetric_difference(mesh_poly).area if mesh is not None else None
        haus = poly.hausdorff_distance(mesh_poly) if mesh is not None else None
        derived = free.intersection(precut[wid]) if wid in precut else Polygon()
        per_walk[wid] = {
            "area_m2": float(poly.area),
            "holes": len(poly.interiors),
            "mesh_symmetric_difference_m2": sym,
            "mesh_hausdorff_m": haus,
            "outside_floor_m2": float(poly.difference(floor).area),
            "solid_penetration_m": max_penetration(poly.intersection(solid_union)),
            "solid_overlap_m2": float(poly.intersection(solid_union).area),
            "derived_area_m2": float(derived.area),
            "derived_iou": iou(poly, derived),
            "missing_vs_derived": _blocks(
                derived.difference(poly), rules["report_block_min_area_m2"]
            ),
            "extra_vs_derived": _blocks(
                poly.difference(derived), rules["report_block_min_area_m2"]
            ),
        }
    outside_design = free.difference(unary_union(list(precut.values())))
    return {
        "floor": {
            "area_m2": float(floor.area),
            "z_values_m": floor_z,
            "covers_walkable": float(walk_union.difference(floor).area) <= 1e-9,
        },
        "body_band_solid_ids": sorted(s.id for s in band_solids),
        "above_band_solid_ids": sorted(s.id for s in solids if not s.in_body_band(band)),
        "free_floor_area_m2": float(free.area),
        "walkable_area_m2": float(walk_union.area),
        "iou_walkable_vs_free_floor": iou(walk_union, free),
        "iou_walkable_vs_derived_in_design_scope": iou(
            walk_union, free.intersection(unary_union(list(precut.values())))
        ),
        "free_floor_outside_design_walks": _blocks(
            outside_design, rules["report_block_min_area_m2"]
        ),
        "per_walk": per_walk,
        "_geoms": {"floor": floor, "free": free, "walk_union": walk_union, "walks": walks},
    }


def inset_comparison(walk_union: BaseGeometry, radii: Iterable[float]) -> list[dict[str, Any]]:
    out = []
    for r in radii:
        inset = walk_union.buffer(-r)
        parts = [p for p in getattr(inset, "geoms", [inset]) if not p.is_empty]
        out.append(
            {
                "radius_m": r,
                "inset_area_m2": float(inset.area),
                "iou_walkable_vs_inset": iou(walk_union, inset),
                "area_not_reachable_by_body_centre_m2": float(walk_union.area - inset.area),
                "components": len(parts),
            }
        )
    return out


def reach_fraction(pair_union: BaseGeometry, a: BaseGeometry, b: BaseGeometry, r: float) -> float:
    """Share of the eroded interiors of ``a`` and ``b`` lying in components of the eroded
    ``a ∪ b`` that touch both walks (body-centre disc of radius ``r``).  1.0 means every place a
    body can stand in either walk is reachable from the other; a doorway pocket of the far walk
    does not count as reaching the rest of it."""
    a_in, b_in = a.buffer(-r), b.buffer(-r)
    if a_in.is_empty or b_in.is_empty:
        return 0.0
    total = unary_union([a_in, b_in]).area
    inset = pair_union.buffer(-r)
    joined = 0.0
    for part in getattr(inset, "geoms", [inset]):
        if part.is_empty:
            continue
        if part.intersection(a_in).area > 1e-6 and part.intersection(b_in).area > 1e-6:
            joined += part.intersection(unary_union([a_in, b_in])).area
    return float(joined / total) if total > 0 else 0.0


def _connected(pair_union: BaseGeometry, a: BaseGeometry, b: BaseGeometry, r: float) -> bool:
    return reach_fraction(pair_union, a, b, r) >= REACH_FRACTION_MIN


def critical_radius(a: BaseGeometry, b: BaseGeometry, tol: float, r_max: float) -> float:
    """Largest body-centre disc radius (to ``tol``) for which walk ``a`` still reaches ``b``."""
    pair = unary_union([a, b])
    if not _connected(pair, a, b, 1e-9):
        return 0.0
    lo, hi = 0.0, r_max
    if _connected(pair, a, b, hi):
        return hi
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if _connected(pair, a, b, mid):
            lo = mid
        else:
            hi = mid
    return lo


def derived_adjacency(
    walks: Mapping[str, BaseGeometry], solid_union: BaseGeometry, min_shared: float
) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    ids = sorted(walks)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            shared = walks[a].boundary.intersection(walks[b].boundary)
            length = float(shared.difference(solid_union).length) if not shared.is_empty else 0.0
            if length >= min_shared:
                out[(a, b)] = length
    return out


def connection_checks(
    scene: Mapping[str, Any],
    walks: Mapping[str, BaseGeometry],
    solids: Sequence[Solid],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    band = rules["body_band_z_m"]
    solid_union = unary_union([s.footprint for s in solids if s.in_body_band(band)])
    declared: dict[tuple[str, str], str | None] = {}
    for walk in scene["walkable"]:
        for conn in walk["connections"]:
            key = tuple(sorted((walk["id"], conn["to_walk_id"])))
            declared[(key[0], key[1])] = conn.get("via_portal_id")
    derived = derived_adjacency(walks, solid_union, rules["adjacency_min_shared_m"])
    envelope = float(rules["envelope_radius_m"])
    nominal = float(rules["nominal_radius_m"])
    rows = []
    for (a, b), via in sorted(declared.items()):
        crit = critical_radius(
            walks[a], walks[b], rules["critical_radius_tol_m"], rules["critical_radius_max_m"]
        )
        pair = unary_union([walks[a], walks[b]])
        rows.append(
            {
                "walks": [a, b],
                "via_portal_id": via,
                "reach_fraction_r025": reach_fraction(pair, walks[a], walks[b], nominal),
                "reach_fraction_r030": reach_fraction(pair, walks[a], walks[b], envelope),
                "derived_shared_free_boundary_m": derived.get((a, b), 0.0),
                "critical_radius_m": crit,
                "clear_width_m": 2.0 * crit,
                "passable_envelope_r030": crit >= envelope,
                "passable_nominal_r025": crit >= nominal,
            }
        )
    undeclared = [
        {"walks": [a, b], "shared_free_boundary_m": length}
        for (a, b), length in sorted(derived.items())
        if (a, b) not in declared
    ]
    walk_union = unary_union(list(walks.values()))
    components = {}
    for r in (envelope, nominal):
        inset = walk_union.buffer(-r)
        parts = [p for p in getattr(inset, "geoms", [inset]) if not p.is_empty and p.area > 1e-6]
        groups = []
        for part in sorted(parts, key=lambda p: -p.area):
            members = sorted(
                w for w, g in walks.items() if part.intersection(g.buffer(-r)).area > 1e-6
            )
            groups.append({"area_m2": float(part.area), "walks": members})
        components[f"r={r:.2f}"] = groups
    return {
        "declared": rows,
        "undeclared_adjacency": undeclared,
        "inset_components": components,
    }


def portal_checks(
    scene: Mapping[str, Any],
    meshes: Mapping[str, Mesh],
    walks: Mapping[str, BaseGeometry],
    solids: Sequence[Solid],
    connection_rows: Sequence[Mapping[str, Any]],
    rules: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    band = rules["body_band_z_m"]
    band_solids = [s for s in solids if s.in_body_band(band)]
    probe = float(rules["portal_probe_m"])
    tol = float(rules["vertex_match_tol_m"])
    out: dict[str, dict[str, Any]] = {}
    for portal in scene["portals"]:
        op = portal["opening_m"]
        a, b = np.array(op["a"], float), np.array(op["b"], float)
        u = (b - a) / np.linalg.norm(b - a)
        n = np.array([-u[1], u[0]])
        # Which side is the wall?  Probe both normal sides just past the jamb ends.
        result: dict[str, Any] = {"width_m": float(op["width_m"])}
        side = None
        for sign in (1.0, -1.0):
            inner = a - u * probe + sign * n * 0.05
            if any(s.footprint.contains(Point(*inner)) for s in band_solids):
                side = sign
                break
        result["wall_side_found"] = side is not None
        if side is not None:
            mid_line_a = a + side * n * 0.05
            line = LineString([mid_line_a - u * 1.0, mid_line_a + (b - a) + u * 1.0])
            free = line.difference(unary_union([s.footprint for s in band_solids]))
            centre = Point(*(mid_line_a + 0.5 * (b - a)))
            pieces = [p for p in getattr(free, "geoms", [free]) if p.distance(centre) < 1e-9]
            clear = float(pieces[0].length) if pieces else 0.0
            result["measured_clear_width_m"] = clear
            result["clear_width_matches"] = abs(clear - float(op["width_m"])) <= 1e-5
            jambs = [
                any(s.footprint.contains(Point(*p)) for s in band_solids)
                for p in (mid_line_a - u * probe, mid_line_a + (b - a) + u * probe)
            ]
            result["jambs_present"] = all(jambs)
            lintel_pt = np.r_[
                mid_line_a + 0.5 * (b - a), float(op["sill_z_m"]) + float(op["height_m"]) + probe
            ]
            result["lintel_above_opening"] = bool(points_in_boxes(lintel_pt[None], solids)[0])
        else:
            result.update(
                measured_clear_width_m=None,
                clear_width_matches=False,
                jambs_present=False,
                lintel_above_opening=False,
            )
        mesh = meshes.get(portal["id"])
        if mesh is not None:
            expected = np.array(
                [
                    [*op["a"], op["sill_z_m"]],
                    [*op["b"], op["sill_z_m"]],
                    [*op["b"], op["sill_z_m"] + op["height_m"]],
                    [*op["a"], op["sill_z_m"] + op["height_m"]],
                ],
                float,
            )
            dev = max(float(np.min(np.linalg.norm(expected - v, axis=1))) for v in mesh.vertices)
            result["marker_mesh_max_deviation_m"] = dev
            result["marker_mesh_matches"] = dev <= max(tol, 1e-5)
            result["physical_geometry_authority"] = mesh.meta.get("physical_geometry_authority")
        centre = a + 0.5 * (b - a)
        reach = 0.12 + float(rules["envelope_radius_m"])
        ends = [Point(*(centre + n * reach)), Point(*(centre - n * reach))]
        owners = sorted({w for p in ends for w, g in walks.items() if g.covers(p)})
        crossing = LineString([tuple(centre + n * reach), tuple(centre - n * reach)])
        result["crossing_walks"] = owners
        result["crossing_matches_connects"] = owners == sorted(portal["connects"])
        result["crossing_inside_walkable"] = bool(
            unary_union(list(walks.values())).buffer(1e-7).covers(crossing)
        )
        row = next(
            (r for r in connection_rows if r["via_portal_id"] == portal["id"]),
            None,
        )
        result["critical_radius_m"] = row["critical_radius_m"] if row else None
        result["passable_envelope_r030"] = bool(row and row["passable_envelope_r030"])
        out[portal["id"]] = result
    return out


# ----------------------------------------------------------------------------- cameras


def camera_rays(camera: Mapping[str, Any], points: np.ndarray) -> dict[str, np.ndarray]:
    """Project world points; return in-image mask, depth and pixel coordinates."""
    m = np.asarray(camera["camera_to_world"], float)
    rot, centre = m[:3, :3], m[:3, 3]
    local = (points - centre) @ rot  # world -> camera (rows)
    depth = -local[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = camera["cx"] + camera["fx"] * local[:, 0] / depth
        v = camera["cy"] - camera["fy"] * local[:, 1] / depth
    in_view = (
        (depth > camera["clip_start"])
        & (depth < camera["clip_end"])
        & (u >= 0)
        & (u < camera["width"])
        & (v >= 0)
        & (v < camera["height"])
    )
    return {"in_view": in_view, "depth": depth, "u": u, "v": v, "centre": centre}


def segment_box_hits(
    origin: np.ndarray, points: np.ndarray, solids: Sequence[Solid]
) -> tuple[np.ndarray, np.ndarray]:
    """Per point: is the open segment origin->point blocked by a box; and the min chord (m)."""
    lo = np.stack([s.lo for s in solids])[None]
    hi = np.stack([s.hi for s in solids])[None]
    d = (points - origin)[:, None, :]
    length = np.linalg.norm(points - origin, axis=1)
    o = origin[None, None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        t1 = (lo - o) / d
        t2 = (hi - o) / d
    parallel = np.abs(d) < 1e-15
    inside_slab = (o > lo) & (o < hi)
    t1 = np.where(parallel, np.where(inside_slab, -np.inf, np.inf), t1)
    t2 = np.where(parallel, np.where(inside_slab, np.inf, -np.inf), t2)
    t_enter = np.minimum(t1, t2).max(axis=2)
    t_exit = np.maximum(t1, t2).min(axis=2)
    t_enter = np.maximum(t_enter, 0.0)
    t_exit = np.minimum(t_exit, 1.0)
    chord = (t_exit - t_enter) * length[:, None]
    blocked = (chord > 1e-9).any(axis=1)
    chord_pos = np.where(chord > 0, chord, np.inf)
    return np.asarray(blocked), np.asarray(chord_pos.min(axis=1))


def floor_grid(region: BaseGeometry, step: float) -> np.ndarray:
    x0, y0, x1, y1 = region.bounds
    xs = np.arange(math.floor(x0 / step) * step + step / 2, x1, step)
    ys = np.arange(math.floor(y0 / step) * step + step / 2, y1, step)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    gx, gy = gx.ravel(), gy.ravel()
    keep = shapely.contains_xy(region, gx, gy)
    return np.column_stack([gx[keep], gy[keep], np.zeros(int(keep.sum()))])


@dataclass
class CameraResult:
    summary: dict[str, Any]
    visible_points: np.ndarray = field(repr=False)


def camera_visibility(
    camera: Mapping[str, Any],
    grid: np.ndarray,
    step: float,
    solids: Sequence[Solid],
    regions: Mapping[str, BaseGeometry],
) -> CameraResult:
    rays = camera_rays(camera, grid)
    centre = rays["centre"]
    in_view = rays["in_view"]
    blocked = np.zeros(len(grid), bool)
    idx = np.nonzero(in_view)[0]
    if len(idx):
        blocked[idx], _ = segment_box_hits(centre, grid[idx], solids)
    visible = in_view & ~blocked
    cell = step * step
    per_region = {}
    for rid, geom in sorted(regions.items()):
        inside = shapely.contains_xy(geom, grid[:, 0], grid[:, 1])
        per_region[rid] = {
            "in_view_m2": float((inside & in_view).sum() * cell),
            "visible_floor_m2": float((inside & visible).sum() * cell),
        }
    position = Point(float(centre[0]), float(centre[1]))
    location = sorted(rid for rid, geom in regions.items() if geom.covers(position))
    in_solid = bool(points_in_boxes(centre[None], solids)[0])
    gaps = [
        float(np.linalg.norm(np.maximum(np.maximum(s.lo - centre, centre - s.hi), 0.0)))
        for s in solids
    ]
    summary = {
        "camera_id": camera["camera_id"],
        "position_m": [float(c) for c in centre],
        "located_in": location,
        "inside_solid": in_solid,
        "min_gap_to_solid_m": min(gaps),
        "in_view_floor_m2": float(in_view.sum() * cell),
        "visible_floor_m2": float(visible.sum() * cell),
        "occluded_in_view_m2": float((in_view & blocked).sum() * cell),
        "per_region": per_region,
    }
    return CameraResult(summary, grid[visible])


def raycast_crosscheck(
    camera: Mapping[str, Any],
    grid: np.ndarray,
    solids: Sequence[Solid],
    tri_meshes: Sequence[Mesh],
    grazing: float,
) -> dict[str, Any]:
    """Box (component/footprint) raycast vs triangle raycast over shell + obstacle meshes."""
    rays = camera_rays(camera, grid)
    idx = np.nonzero(rays["in_view"])[0]
    centre = rays["centre"]
    pts = grid[idx]
    box_blocked, chord = segment_box_hits(centre, pts, solids)
    tris = np.concatenate([m.triangles() for m in tri_meshes])
    dirs = pts - centre
    tri_blocked = ray_triangle_hits(np.broadcast_to(centre, pts.shape).copy(), dirs, tris, 1.0) > 0
    grazing_mask = box_blocked & (chord < grazing)
    compare = ~grazing_mask
    return {
        "camera_id": camera["camera_id"],
        "rays": int(len(pts)),
        "blocked_boxes": int(box_blocked.sum()),
        "blocked_triangles": int(tri_blocked.sum()),
        "grazing_excluded": int(grazing_mask.sum()),
        "disagreements": int((box_blocked != tri_blocked)[compare].sum()),
    }


# ----------------------------------------------------------------------------- verdicts


def _verdict(gates: Mapping[str, bool], reject_only: Sequence[str] = ()) -> str:
    failed = [k for k, ok in gates.items() if not ok]
    if not failed:
        return "APPROVE"
    if reject_only and set(failed) <= set(reject_only):
        return "REJECT"
    return "FIX"


def purpose_matrix(
    scene: Mapping[str, Any],
    hash_ok: Mapping[str, bool],
    mesh_checks: Mapping[str, Mapping[str, Any]],
    display_checks: Mapping[str, Mapping[str, Any]],
    shell: Mapping[str, Any],
    seams: Sequence[Mapping[str, Any]],
    crosschecks: Sequence[Mapping[str, Any]],
    walks: Mapping[str, Any],
    connections: Mapping[str, Any],
    portals: Mapping[str, Mapping[str, Any]],
    rules: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raycast_ok = all(c["disagreements"] == 0 for c in crosschecks)
    seam_ok = all(g["severity"] == "INFO" for g in seams)
    band_ids = set(walks["body_band_solid_ids"])
    rows = []
    walkable_ids = {w["id"] for w in scene["walkable"]}
    declared_pairs = {tuple(r["walks"]) for r in connections["declared"]}
    undeclared = {w for u in connections["undeclared_adjacency"] for w in u["walks"]}
    for obj in scene["objects"]:
        oid = obj["id"]
        for purpose in obj["allowed_purposes"]:
            gates: dict[str, bool] = {"geometry_hash": bool(hash_ok.get(oid))}
            notes: list[str] = []
            reject_only: list[str] = []
            if purpose in ("OCCLUSION", "VISIBILITY_INDEX", "COLLISION"):
                mc = mesh_checks.get(oid, {})
                gates["exact_box_mesh"] = bool(mc.get("pass"))
                gates["collision_scope_exact_mesh"] = obj.get("collision_scope") == "EXACT_MESH"
                if obj["class"] == "WALL":
                    gates["shell_equivalence"] = bool(shell.get("pass"))
                gates["seam_gaps_within_float32_tol"] = seam_ok
                if purpose != "COLLISION":
                    gates["raycast_crosscheck"] = raycast_ok
                elif oid in band_ids:
                    pen = max(
                        (pw["solid_penetration_m"] for pw in walks["per_walk"].values()),
                        default=0.0,
                    )
                    gates["walkable_penetration_within_tol"] = pen <= rules["penetration_tol_m"]
                else:
                    notes.append("ABOVE_BODY_BAND：整個物件在 1.80 m 人體帶以上，不影響可走範圍")
            elif purpose == "WALKABILITY" and oid in walkable_ids:
                pw = walks["per_walk"][oid]
                gates["polygon_equals_mesh"] = (
                    pw["mesh_symmetric_difference_m2"] is not None
                    and pw["mesh_symmetric_difference_m2"] <= rules["polygon_match_area_tol_m2"]
                    and pw["mesh_hausdorff_m"] <= rules["polygon_match_hausdorff_m"]
                )
                gates["on_floor"] = pw["outside_floor_m2"] <= rules["polygon_match_area_tol_m2"]
                gates["no_solid_penetration"] = (
                    pw["solid_penetration_m"] <= rules["penetration_tol_m"]
                )
                gates["matches_derived_free_floor"] = (
                    pw["derived_iou"] is not None and pw["derived_iou"] >= rules["derived_iou_min"]
                )
                gates["no_undeclared_adjacency"] = oid not in undeclared
                notes.append(
                    "語意是地板佔用區（地板扣實體 footprint），不是人體中心可達區；K1 與可達性用途"
                    "要先依包絡半徑內縮"
                )
                blocked = [
                    p
                    for p in declared_pairs
                    if oid in p
                    and not next(r for r in connections["declared"] if tuple(r["walks"]) == p)[
                        "passable_envelope_r030"
                    ]
                ]
                if blocked:
                    notes.append(
                        "連通 "
                        + "、".join("↔".join(p) for p in sorted(blocked))
                        + " 在 r=0.30 m 下不成立（見 portal 列）；本 walk 在內縮圖上是獨立分量"
                    )
            elif purpose == "WALKABILITY" and obj["class"] == "PORTAL":
                pc = portals.get(oid, {})
                gates["clear_gap_between_jambs"] = bool(
                    pc.get("clear_width_matches") and pc.get("jambs_present")
                )
                gates["lintel_above_opening"] = bool(pc.get("lintel_above_opening"))
                gates["marker_mesh_matches"] = bool(pc.get("marker_mesh_matches"))
                gates["crossing_matches_connects"] = bool(
                    pc.get("crossing_matches_connects") and pc.get("crossing_inside_walkable")
                )
                gates["passable_envelope_r030"] = bool(pc.get("passable_envelope_r030"))
                reject_only = ["passable_envelope_r030"]
                if not pc.get("passable_envelope_r030"):
                    notes.append(
                        f"淨寬 {2 * (pc.get('critical_radius_m') or 0):.3f} m 小於 2×0.30 m；"
                        "只能當拓撲連通（O11），不能當人體可通行證據"
                    )
            elif purpose == "DISPLAY":
                dc = display_checks.get(oid, {})
                gates["bounds_match_geometry"] = bool(dc.get("pass"))
            else:
                gates["purpose_check_defined"] = False
            verdict = _verdict(gates, reject_only)
            rows.append(
                {
                    "id": oid,
                    "class": obj["class"],
                    "purpose": purpose,
                    "needed_by": PURPOSE_USES.get(purpose, []),
                    "validator_rules": VALIDATOR_COVERAGE.get(purpose, []),
                    "k7_gates": gates,
                    "notes": notes,
                    "verdict": verdict,
                    "verdict_zh": VERDICT_TEXT[verdict],
                }
            )
    return rows


def display_check(obj: Mapping[str, Any], mesh: Mesh | None, tol: float) -> dict[str, Any]:
    if mesh is None:
        return {"pass": False, "reason": "GEOMETRY_UNAVAILABLE"}
    lo, hi = mesh.vertices.min(axis=0), mesh.vertices.max(axis=0)
    bounds = np.asarray(obj["bounds_m"], float)
    dev = float(np.abs(np.r_[lo - bounds[0], hi - bounds[1]]).max())
    return {"max_bounds_deviation_m": dev, "pass": dev <= max(tol, 1e-5)}


def strip_private(value: Any) -> Any:
    """Drop ``_``-prefixed working geometry from a result tree before serialisation."""
    if isinstance(value, dict):
        return {k: strip_private(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [strip_private(v) for v in value]
    return value

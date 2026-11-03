"""K7 map verification for the controlled scene r003 safe static geometry (O10 evidence).

Reads only ``scene_static.json``, ``cameras.json`` and the hash-pinned ``geometry/*.json`` of
each safe bundle.  No RGB content, Ground Truth, person route, renderer visibility or depth.
Writes one result JSON (no absolute paths) and optional overlay PNGs; inputs are never edited.

    PYTHONPATH=src python scripts/verify_controlled_scene_k7.py \
        --safe-dir <runs>/ctrl-lcorr-s1-a-5fps-v1-r001/safe_bundle \
        --safe-dir <runs>/ctrl-lcorr-s1-b1-5fps-v1-r001/safe_bundle \
        --output docs/engineering/CONTROLLED_SCENE_R003_K7_VERIFICATION_20261020.json \
        --figures-dir docs/engineering/figures/k7_r003
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from amidst.evaluation import k7_controlled_scene as k7

MAX_FIGURE_BYTES = 500_000


def verify(scene: k7.SafeScene, rules: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    static = scene.scene
    solids = k7.solids_of(static)
    by_id = {s.id: s for s in solids}
    hash_ok = {c["id"]: c["match"] for c in scene.geometry_hash_checks}
    mesh_checks = {
        s.id: k7.mesh_box_check(scene.meshes[s.id], s, rules["vertex_match_tol_m"])
        for s in solids
        if s.id in scene.meshes
    }
    walls = [s for s in solids if s.cls == "WALL"]
    shell = k7.shell_equivalence(scene.meshes["ACTIVE_WALL_SHELL"], walls, rules)
    seams = k7.seam_gaps(solids, rules["seam_gap_max_m"], rules["penetration_tol_m"])
    walks = k7.walk_checks(static, scene.meshes, solids, rules)
    geoms = walks.pop("_geoms")
    insets = k7.inset_comparison(
        geoms["walk_union"], [0.0, rules["nominal_radius_m"], rules["envelope_radius_m"]]
    )
    connections = k7.connection_checks(static, geoms["walks"], solids, rules)
    portals = k7.portal_checks(
        static, scene.meshes, geoms["walks"], solids, connections["declared"], rules
    )
    regions: dict[str, Any] = dict(geoms["walks"])
    for obj in static["objects"]:
        if obj["class"] == "AREA" and obj["id"] in scene.meshes:
            regions[obj["id"]] = k7.mesh_xy_union(scene.meshes[obj["id"]])
    occupied = geoms["floor"].difference(
        unary_union([s.footprint for s in solids if s.lo[2] <= 0.0])
    )
    grid = k7.floor_grid(occupied, rules["floor_grid_step_m"])
    coarse = k7.floor_grid(occupied, rules["crosscheck_grid_step_m"])
    tri_meshes = [scene.meshes["ACTIVE_WALL_SHELL"]] + [
        scene.meshes[s.id] for s in solids if s.cls == "OBSTACLE"
    ]
    cameras, visible, crosschecks = [], {}, []
    for cam in scene.cameras["cameras"]:
        res = k7.camera_visibility(cam, grid, rules["floor_grid_step_m"], solids, regions)
        cameras.append(res.summary)
        visible[cam["camera_id"]] = res.visible_points
        crosschecks.append(
            k7.raycast_crosscheck(cam, coarse, solids, tri_meshes, rules["grazing_chord_m"])
        )
    display = {
        obj["id"]: k7.display_check(obj, scene.meshes.get(obj["id"]), rules["vertex_match_tol_m"])
        for obj in static["objects"]
    }
    matrix = k7.purpose_matrix(
        static,
        hash_ok,
        mesh_checks,
        display,
        shell,
        seams,
        crosschecks,
        walks,
        connections,
        portals,
        rules,
    )
    floor = static["floors"][0]
    result = {
        "run_id": scene.run_id,
        "input_sha256": dict(sorted(scene.input_hashes.items())),
        "geometry_hash_checks": {
            "total": len(scene.geometry_hash_checks),
            "mismatched": [c["ref"] for c in scene.geometry_hash_checks if not c["match"]],
        },
        "scene_scope": {
            "geometry_scope": static.get("geometry_scope"),
            "floor_approved_scope_ref": floor.get("approved_scope_ref"),
            "camera_static_validity": {
                c["camera_id"]: (c.get("static_validity") or {}).get("status")
                for c in scene.cameras["cameras"]
            },
            "visibility_index_refs": {
                b["camera_id"]: b.get("visibility_index_ref") for b in scene.cameras["run_bindings"]
            },
        },
        "solids": {
            "count": len(solids),
            "mesh_checks": mesh_checks,
            "shell_equivalence": shell,
            "seam_gaps": seams,
        },
        "walkable": walks,
        "inset": insets,
        "connections": connections,
        "portals": portals,
        "cameras": cameras,
        "raycast_crosscheck": crosschecks,
        "display_checks": display,
        "purposes": matrix,
    }
    figure_data = {
        "geoms": geoms,
        "solids": by_id,
        "visible": visible,
        "cameras": scene.cameras["cameras"],
        "portals": static["portals"],
        "envelope": rules["envelope_radius_m"],
    }
    return result, figure_data


def summarise(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for row in matrix:
        bucket = out.setdefault(row["purpose"], {"APPROVE": [], "REJECT": [], "FIX": []})
        bucket[row["verdict"]].append(row["id"])
    return {
        purpose: {k: sorted(v) for k, v in counts.items()}
        for purpose, counts in sorted(out.items())
    }


def _patch(ax: Any, geom: Any, **kw: Any) -> None:
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MplPath

    for part in getattr(geom, "geoms", [geom]):
        if not isinstance(part, Polygon) or part.is_empty:
            continue
        verts, codes = [], []
        for ring in [part.exterior, *part.interiors]:
            xy = list(ring.coords)
            verts += xy
            codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(xy) - 2) + [MplPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MplPath(verts, codes), **kw))


def figures(data: dict[str, Any], out_dir: Path) -> list[Path]:
    from matplotlib.figure import Figure

    out_dir.mkdir(parents=True, exist_ok=True)
    geoms, solids = data["geoms"], data["solids"]
    written = []
    fig = Figure(figsize=(11, 8), dpi=90)
    ax = fig.add_subplot()
    _patch(ax, geoms["floor"], facecolor="#eeeeee", edgecolor="none")
    _patch(ax, geoms["walk_union"], facecolor="#cfe3f5", edgecolor="#5b8db8", lw=0.6)
    inset = geoms["walk_union"].buffer(-data["envelope"])
    _patch(ax, inset, facecolor="#7fb27f", edgecolor="#2f6b2f", lw=0.6, alpha=0.8)
    for s in solids.values():
        colour = "#333333" if s.lo[2] < 1.8 else "#bbbbbb"
        _patch(ax, s.footprint, facecolor=colour, edgecolor="none")
    for p in data["portals"]:
        a, b = p["opening_m"]["a"], p["opening_m"]["b"]
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#d62728", lw=2.5)
        ax.annotate(p["id"], a, fontsize=7, color="#d62728")
    for c in data["cameras"]:
        m = np.asarray(c["camera_to_world"])
        ax.plot(m[0, 3], m[1, 3], marker="^", color="#9467bd")
        ax.annotate(c["camera_id"], (m[0, 3], m[1, 3]), fontsize=7, color="#9467bd")
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_title(
        "r003 walkable (blue) vs body-centre inset r=0.30 m (green); solids < 1.8 m black; "
        "portals red",
        fontsize=9,
    )
    path = out_dir / "r003_walkable_inset.png"
    fig.savefig(path)
    written.append(path)
    fig = Figure(figsize=(12, 9), dpi=80)
    for i, (cid, pts) in enumerate(sorted(data["visible"].items())):
        ax = fig.add_subplot(2, 2, i + 1)
        _patch(ax, geoms["floor"], facecolor="#eeeeee", edgecolor="none")
        _patch(ax, geoms["walk_union"], facecolor="none", edgecolor="#5b8db8", lw=0.5)
        for s in solids.values():
            _patch(ax, s.footprint, facecolor="#333333", edgecolor="none")
        if len(pts):
            ax.scatter(pts[:, 0], pts[:, 1], s=0.15, color="#ff7f0e", linewidths=0)
        cam = next(c for c in data["cameras"] if c["camera_id"] == cid)
        m = np.asarray(cam["camera_to_world"])
        ax.plot(m[0, 3], m[1, 3], marker="^", color="#9467bd")
        ax.set_title(f"{cid}: static floor raycast (orange = visible floor)", fontsize=8)
        ax.set_aspect("equal")
        ax.autoscale_view()
    path = out_dir / "r003_camera_floor_visibility.png"
    fig.savefig(path)
    written.append(path)
    for p in written:
        if p.stat().st_size > MAX_FIGURE_BYTES:
            raise SystemExit(f"figure too large: {p.name}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safe-dir", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--figures-dir", type=Path)
    args = parser.parse_args()
    rules = dict(k7.RULES)
    runs, figure_data = [], None
    for safe_dir in args.safe_dir:
        scene = k7.load_safe_scene(safe_dir)
        result, data = verify(scene, rules)
        runs.append(result)
        figure_data = figure_data or data
    static_hashes = {r["input_sha256"]["scene_static.json"] for r in runs}
    geometry_sets = {
        json.dumps({k: v for k, v in r["input_sha256"].items() if k.startswith("geometry/")})
        for r in runs
    }
    comparable = [
        {k: v for k, v in r.items() if k not in ("run_id", "input_sha256", "scene_scope")}
        for r in runs
    ]
    identical = len({k7.canonical_sha256(c) for c in comparable}) == 1
    doc: dict[str, Any] = {
        "schema_version": k7.SCHEMA,
        "verifier": {"name": k7.VERIFIER, "version": k7.VERIFIER_VERSION},
        "rules": rules,
        "rules_changelog": k7.RULES_CHANGELOG,
        "decision_rules": k7.DECISION_RULES,
        "design_reference": k7.DESIGN_REFERENCE,
        "read_scope": {
            "read": ["scene_static.json", "cameras.json", "geometry/*.json (hash-pinned refs)"],
            "not_read": [
                "RGB content",
                "rgb_index.json",
                "Ground Truth",
                "person routes / persons.sim.json",
                "renderer visibility",
                "depth",
                "private_evaluation/",
            ],
        },
        "runs_static_identical": {
            "scene_static_sha256_identical": len(static_hashes) == 1,
            "geometry_files_identical": len(geometry_sets) == 1,
            "results_identical_except_run_scope": identical,
        },
        "runs": runs,
        "summary_by_purpose": summarise(runs[0]["purposes"]),
    }
    doc["output_sha256"] = k7.canonical_sha256(k7.strip_private(doc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(k7.strip_private(doc), indent=1, ensure_ascii=False, allow_nan=False)
    args.output.write_text(text + "\n", encoding="utf-8")
    if args.figures_dir and figure_data is not None:
        for path in figures(figure_data, args.figures_dir):
            print("figure", path)
    print("output_sha256", doc["output_sha256"])


if __name__ == "__main__":
    main()

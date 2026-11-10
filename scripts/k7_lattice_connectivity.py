"""K7: does K1's real 0.25 m lattice connect the pieces that a C7 map pinches into narrow necks?

Builds K1's own ``_Lattice`` (floor map, cell centres, edge validity) from a C7 map variant and
reports lattice connected components.  No hypotheses are generated.  ``--k1-src`` is a directory
holding an export of ``origin/claude/k1-hypothesis`` (``src/`` and ``configs/``); nothing is
imported from C7.  Read-only on every input.

    git archive claude/k1-hypothesis src/amidst/blind_hypothesis configs | tar -x -C <dir>
    PYTHONPATH=src python scripts/k7_lattice_connectivity.py --k1-src <dir> --map <map.json> \
        --variant person --anchor 34.58 49.0 --output <result.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import shapely
from shapely.geometry import Point

from amidst.evaluation import map_verification as mv


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--k1-src", type=Path, required=True)
    ap.add_argument("--k1-commit", required=True)
    ap.add_argument("--map", type=Path, required=True)
    ap.add_argument("--variant", default="person")
    ap.add_argument("--anchor", type=float, nargs=2, required=True, metavar=("X", "Y"))
    ap.add_argument("--duration-s", type=float, default=20.0)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    mv.ensure_output_outside_inputs(args.output, [args.map, args.k1_src / "x"])
    import amidst

    amidst.__path__.append(str(args.k1_src / "src" / "amidst"))
    from amidst.blind_hypothesis import engine
    from amidst.blind_hypothesis.floor_map import FloorMapDescriptor, PolygonFloorMap

    config_path = args.k1_src / "configs" / "blind_hypothesis_v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    cfg = engine.parse_config(
        config, scene_id="blender-office", config_sha256=sha256_of(config_path)
    )

    doc = json.loads(args.map.read_text(encoding="utf-8"))
    variant = mv.load_variant(doc, args.variant)
    regions = {
        r["region_id"]: shapely.from_geojson(json.dumps(r["geometry"]))
        for r in doc["variants"][args.variant]["regions"]
        if r.get("walkable") == "TRUE"
    }
    portals = {
        p["portal_id"]: shapely.from_geojson(json.dumps(p["geometry"]))
        for p in doc["variants"][args.variant]["portals"]
    }
    floor_map = PolygonFloorMap(
        FloorMapDescriptor("SOURCE_DERIVED", "k7-check", sha256_of(args.map), "k7", "k7", "1F"),
        float(doc["variants"][args.variant]["floor_z_m"]),
        regions,
        portals,
        {},
        {name: "SOURCE_DERIVED" for name in regions},
    )
    anchor = tuple(args.anchor)
    endpoint = SimpleNamespace(region=Point(anchor), anchor=anchor)
    walk_union = shapely.union_all([*regions.values(), *portals.values()])
    lattice = engine._Lattice(floor_map, cfg, endpoint, endpoint, args.duration_s, walk_union)
    moves = [
        (dx, dy, d)
        for dx, dy, d in lattice.offsets(lattice.g * math.sqrt(5.0))
        if math.gcd(dx, dy) == 1
    ]
    adjacency = [lattice.neighbours(k, moves) for k in range(len(lattice))]
    # union-find over lattice cells
    parent = list(range(len(lattice)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for k, nbrs in enumerate(adjacency):
        for other, _ in nbrs:
            ra, rb = find(k), find(other)
            if ra != rb:
                parent[ra] = rb
    roots = [find(k) for k in range(len(lattice))]
    sizes: dict[int, int] = {}
    for r in roots:
        sizes[r] = sizes.get(r, 0) + 1

    h = cfg.grid_step_m / 2
    walk = variant.walkable
    opened = walk.buffer(-h, quad_segs=16).buffer(h, quad_segs=16)
    pieces = sorted(mv._parts(opened), key=lambda p: -p.area)
    xs, ys = lattice.xs, lattice.ys
    piece_rows: list[dict[str, Any]] = []
    main_root_counts: dict[int, int] = {}
    for i, piece in enumerate(pieces):
        mask = shapely.intersects_xy(piece, xs, ys)
        cells = [k for k in range(len(lattice)) if mask[k]]
        comps = sorted({roots[k] for k in cells})
        if i == 0:
            for k in cells:
                main_root_counts[roots[k]] = main_root_counts.get(roots[k], 0) + 1
        piece_rows.append(
            {
                "piece": i,
                "area_m2": round(piece.area, 3),
                "bounds_m": [round(v, 3) for v in piece.bounds],
                "lattice_cells": len(cells),
                "lattice_components": len(comps),
                "component_ids": comps,
            }
        )
    main_root = max(main_root_counts, key=lambda r: main_root_counts[r]) if main_root_counts else -1
    for row in piece_rows:
        row["connected_to_main_piece_lattice"] = bool(
            row["lattice_cells"] > 0 and main_root in row["component_ids"]
        )
    component_rows = sorted(
        (
            {
                "component_id": r,
                "cells": n,
                "approx_area_m2": round(n * cfg.grid_step_m**2, 2),
                "centroid_m": [
                    round(float(xs[[k for k in range(len(lattice)) if roots[k] == r]].mean()), 2),
                    round(float(ys[[k for k in range(len(lattice)) if roots[k] == r]].mean()), 2),
                ],
            }
            for r, n in sizes.items()
        ),
        key=lambda row: -int(row["cells"]),
    )
    result = {
        "schema_version": "office-demo.k7-lattice-connectivity.v1",
        "k1_commit": args.k1_commit,
        "k1_config_sha256": cfg.config_sha256,
        "map": {"file": args.map.name, "sha256": sha256_of(args.map), "variant": args.variant},
        "grid_step_m": cfg.grid_step_m,
        "lattice_cells": len(lattice),
        "primitive_moves": len(moves),
        "continuous_region_count": len(regions),
        "opening_0p125_pieces": piece_rows,
        "lattice_component_count": len(sizes),
        "lattice_components_largest": component_rows[:10],
        "method": (
            "K1 _Lattice built from the map with a dummy endpoint at the anchor; adjacency uses "
            "K1's own neighbours()/edge() with the engine's primitive moves; union-find "
            "components. Pieces are the connected components of the walkable area after a "
            "-0.125 m / +0.125 m buffer."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("lattice_cells", "opening_0p125_pieces")}, indent=1))
    print("components:", len(sizes), [r["cells"] for r in component_rows[:6]])


if __name__ == "__main__":
    main()

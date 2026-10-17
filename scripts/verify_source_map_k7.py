"""K7: independent verification of C7 source-derived floor maps (issue #30).

Read-only on every input.  Writes a machine-readable result JSON and one overlay PNG per
evaluated zone.  Ground Truth routes are read for offline evaluation only (CP1 D10): the result
holds violation summaries (time, distance, zone), never route coordinates, and nothing is fed
back to a map.

    PYTHONPATH=src python scripts/verify_source_map_k7.py \
        --map office=C7_OFFICE.json --map demo=C7_DEMO.json \
        --annotation geometry.json --route RUN=trajectory_plan.json ... \
        --c7-commit 7214ef7 --output result.json --figures-dir docs/engineering/figures/k7
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath
from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry

from amidst.evaluation import map_verification as mv

SCHEMA = "office-demo.k7-map-verification.v1"
MAX_FIGURE_BYTES = 500_000


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_named(items: list[str]) -> list[tuple[str, Path]]:
    out = []
    for item in items:
        name, _, path = item.partition("=")
        if not path:
            raise SystemExit(f"expected NAME=PATH, got {item!r}")
        out.append((name, Path(path)))
    return out


def load_route(path: Path, unit: float) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    samples = plan.get("samples") or []
    cfg = plan.get("run_configuration") or {}
    if "body_radius_m" in cfg:
        radius = float(cfg["body_radius_m"])
    else:
        radius = float(plan["target"]["radius_scene_units"]) * unit
    return {
        "source_sha256": plan.get("source_asset_sha256"),
        "trajectory_id": plan.get("trajectory_id"),
        "radius_m": radius,
        "points": [(s["foot_position"][0] * unit, s["foot_position"][1] * unit) for s in samples],
        "times": [float(s["timestamp"]) for s in samples],
    }


def draw(ax: Any, geom: BaseGeometry, **kwargs: Any) -> None:
    for part in mv._parts(geom):
        if isinstance(part, Polygon):
            verts: list[tuple[float, float]] = []
            codes: list[int] = []
            for ring in [part.exterior, *part.interiors]:
                coords = list(ring.coords)
                verts += coords
                codes += (
                    [MplPath.MOVETO] + [MplPath.LINETO] * (len(coords) - 2) + [MplPath.CLOSEPOLY]
                )
            ax.add_patch(PathPatch(MplPath(verts, codes), **kwargs))
        elif part.geom_type == "LineString":
            xs, ys = part.xy
            ax.plot(xs, ys, color=kwargs.get("edgecolor", "k"), lw=kwargs.get("linewidth", 1))


def render_zone_figure(
    path: Path,
    zone_name: str,
    zone: BaseGeometry,
    variant: mv.VariantMap,
    annotation: mv.Annotation,
    evidence: dict[str, Any],
    routes: list[dict[str, Any]],
    map_name: str,
) -> int:
    x0, y0, x1, y1 = zone.bounds
    window = box(x0 - 2, y0 - 2, x1 + 2, y1 + 2).intersection(variant.roi.buffer(2))
    wx0, wy0, wx1, wy1 = window.bounds
    ratio = max(0.5, min(1.4, (wy1 - wy0) / max(wx1 - wx0, 1e-6)))
    fig = Figure(figsize=(8, 8 * ratio))
    ax = fig.subplots()
    clip = window
    draw(ax, variant.support.intersection(clip), facecolor="#eeeeee", edgecolor="none")
    draw(
        ax,
        variant.walkable.intersection(clip),
        facecolor="#7fc97f",
        alpha=0.55,
        edgecolor="#2d7a2d",
        linewidth=0.5,
    )
    draw(
        ax,
        variant.obstacle_polygons.intersection(clip),
        facecolor="#bbbbbb",
        edgecolor="#666666",
        linewidth=0.3,
    )
    draw(ax, variant.obstacle_lines.intersection(clip), edgecolor="#444444", linewidth=0.8)
    ann_obst = mv.union_all(annotation.obstacles.values())
    draw(
        ax,
        ann_obst.intersection(clip),
        facecolor="none",
        edgecolor="#d62728",
        hatch="//",
        linewidth=0.8,
    )
    draw(
        ax,
        zone.intersection(clip),
        facecolor="none",
        edgecolor="#1f77b4",
        linewidth=1.4,
        linestyle="--",
    )
    draw(ax, variant.roi.intersection(clip).boundary, edgecolor="#999999", linewidth=0.8)
    draw(
        ax,
        evidence["ann_blocks_geom"].intersection(clip),
        facecolor="#ff7f0e",
        alpha=0.6,
        edgecolor="none",
    )
    draw(
        ax,
        evidence["der_blocks_geom"].intersection(clip),
        facecolor="#e377c2",
        alpha=0.6,
        edgecolor="none",
    )
    draw(
        ax,
        evidence["thin_geom"].intersection(clip),
        facecolor="#ffd92f",
        edgecolor="#b8860b",
        linewidth=0.8,
    )
    for hull in evidence["hulls"]:
        if hull.intersects(clip):
            draw(ax, hull, facecolor="none", edgecolor="#6a3d9a", linewidth=1.4, linestyle=":")
    for name, p in annotation.portals.items():
        bx = box(*p["bounds_m"])
        if bx.intersects(clip):
            draw(ax, bx, facecolor="none", edgecolor="#17becf", linewidth=1.4)
            ax.annotate(
                name.replace("PORTAL_1F_", "P:"),
                (bx.centroid.x, bx.centroid.y),
                fontsize=6,
                color="#0b6a73",
            )
    for d in variant.portals:
        (ax_, ay_), (bx_, by_) = d["crossing_line_m"]
        if clip.covers(box(min(ax_, bx_), min(ay_, by_), max(ax_, bx_), max(ay_, by_)).centroid):
            ax.plot([ax_, bx_], [ay_, by_], color="black", linewidth=1.2)
    for route in routes:
        xs = [p[0] for p in route["points"]]
        ys = [p[1] for p in route["points"]]
        ax.plot(xs, ys, color="#08306b", linewidth=0.9, linestyle="-.")
        for idx in route["violation_indices"]:
            ax.plot(xs[idx], ys[idx], marker="x", color="red", markersize=5)
        ax.annotate(route["id"], (xs[0], ys[0]), fontsize=5, color="#08306b")
    ax.set_xlim(wx0, wx1)
    ax.set_ylim(wy0, wy1)
    ax.set_aspect("equal")
    ax.set_title(
        f"{zone_name}  map={map_name}/{variant.name} r={variant.radius_m:g}  "
        f"IoU={evidence['iou']}  grade={evidence['grade']}",
        fontsize=8,
    )
    ax.tick_params(labelsize=6)
    ax.legend(
        handles=[
            Rectangle((0, 0), 1, 1, fc="#7fc97f", alpha=0.55, label="derived body-centre"),
            Rectangle((0, 0), 1, 1, fc="none", ec="#1f77b4", ls="--", label="WALK annotation"),
            Rectangle(
                (0, 0), 1, 1, fc="none", ec="#d62728", hatch="//", label="OBSTACLE annotation"
            ),
            Rectangle((0, 0), 1, 1, fc="#ff7f0e", alpha=0.6, label="annotation-only >0.25 m2"),
            Rectangle((0, 0), 1, 1, fc="#e377c2", alpha=0.6, label="derived-only >0.25 m2"),
            Rectangle((0, 0), 1, 1, fc="#ffd92f", ec="#b8860b", label="thinner than 0.25 m"),
            Rectangle((0, 0), 1, 1, fc="none", ec="#6a3d9a", ls=":", label="seating hull (D11)"),
            Rectangle((0, 0), 1, 1, fc="none", ec="#17becf", label="PORTAL annotation"),
        ],
        fontsize=5,
        loc="upper right",
    )
    fig.tight_layout()
    dpi = 110
    while True:
        fig.savefig(path, dpi=dpi)
        if path.stat().st_size <= MAX_FIGURE_BYTES or dpi <= 50:
            break
        dpi -= 10
    return path.stat().st_size


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--map", action="append", required=True, help="NAME=PATH (first has priority)")
    ap.add_argument("--annotation", type=Path, required=True)
    ap.add_argument("--route", action="append", default=[], help="NAME=PATH to a trajectory plan")
    ap.add_argument("--c7-commit", required=True)
    ap.add_argument("--floor-id", default="1F")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--figures-dir", type=Path, required=True)
    args = ap.parse_args()

    maps = parse_named(args.map)
    route_inputs = parse_named(args.route)
    inputs = [p for _, p in maps] + [args.annotation] + [p for _, p in route_inputs]
    mv.ensure_output_outside_inputs(args.output, inputs)
    mv.ensure_output_outside_inputs(args.figures_dir / "x.png", inputs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)
    rules = mv.GRADING_RULES

    ann_doc = json.loads(args.annotation.read_text(encoding="utf-8"))
    unit = float(ann_doc["unit_scale_m"])
    annotation = mv.load_annotation(ann_doc, args.floor_id)
    walk_union = mv.union_all([*annotation.zones.values(), *annotation.thresholds.values()])
    obst_list = list(annotation.obstacles.values())
    all_zones = {**annotation.zones, **annotation.thresholds}

    map_docs: dict[str, dict[str, Any]] = {}
    variants: dict[str, dict[str, mv.VariantMap]] = {}
    for name, path in maps:
        doc = json.loads(path.read_text(encoding="utf-8"))
        map_docs[name] = doc
        variants[name] = {v: mv.load_variant(doc, v) for v in doc["variants"]}
    source_sha = {d["source_sha256"] for d in map_docs.values()}

    # Routes (offline GT, summaries only).
    routes: list[dict[str, Any]] = []
    route_results: dict[str, Any] = {}
    for rid, path in route_inputs:
        info = load_route(path, unit)
        entry: dict[str, Any] = {
            "input": path.name,
            "trajectory_id": info["trajectory_id"],
            "radius_m": round(info["radius_m"], 4),
        }
        if info["source_sha256"] not in source_sha:
            entry["status"] = "EXCLUDED_DIFFERENT_SOURCE_SHA256"
            route_results[rid] = entry
            continue
        chosen = None
        for mname, _ in maps:
            vname = mv.pick_variant(map_docs[mname], info["radius_m"])
            if vname is None:
                continue
            var = variants[mname][vname]
            if all(var.roi.covers(Point(p)) for p in info["points"]):
                chosen = (mname, vname, var)
                break
        if chosen is None:
            entry["status"] = "OUTSIDE_MAP_SCOPE_OR_NO_MATCHING_RADIUS_VARIANT"
            route_results[rid] = entry
            continue
        mname, vname, var = chosen
        result = mv.evaluate_route(info["points"], info["times"], var, all_zones, rules)
        primary = (
            max(result["zones_hit"], key=result["zones_hit"].get) if result["zones_hit"] else None
        )
        entry.update(
            {
                "status": "EVALUATED",
                "map": mname,
                "variant": vname,
                "primary_zone": primary,
                **result,
            }
        )
        entry.pop("violations")  # per-sample list stays out of the record; intervals remain
        route_results[rid] = entry
        routes.append(
            {
                "id": rid,
                "points": info["points"],
                "times": info["times"],
                "map": mname,
                "variant": vname,
                "primary_zone": primary,
                "result": result,
                "violation_indices": [
                    i
                    for i, t in enumerate(info["times"])
                    if any(v["t_s"] == round(t, 3) for v in result["violations"])
                ],
            }
        )

    # Map-level checks.
    map_level: dict[str, Any] = {}
    thin_cache: dict[tuple[str, str], dict[str, Any]] = {}
    contexts: dict[tuple[str, str], mv.ComparisonContext] = {}
    for mname, vs in variants.items():
        map_level[mname] = {}
        for vname, var in vs.items():
            portals = mv.match_portals(annotation, var, rules)
            thin_cache[(mname, vname)] = mv.thin_features(var, rules)
            contexts[(mname, vname)] = mv.build_context(walk_union, obst_list, var)
            map_level[mname][vname] = {
                "radius_m": var.radius_m,
                "effective_buffer_m": var.effective_buffer_m,
                "region_count": var.region_count,
                "reconstruction": mv.reconstruction_check(var),
                "thin_features": mv.strip_geometry(thin_cache[(mname, vname)]),
                "seating": mv.strip_geometry(mv.seating_check(var, rules)),
                "portals": portals,
                "unannotated_derived": mv.mismatch_blocks(
                    var.walkable.intersection(var.roi.buffer(-var.radius_m)).difference(
                        walk_union.buffer(0.0)
                    ),
                    "DERIVED_OUTSIDE_ANY_WALK_ANNOTATION",
                    rules["min_mismatch_block_m2"],
                    rules["mismatch_opening_m"],
                ),
            }
            map_level[mname][vname]["unannotated_derived"].pop("_geometry")

    # Per-zone comparison.
    zone_results: dict[str, Any] = {}
    figure_sizes: dict[str, int] = {}
    for zname, zone in sorted(annotation.zones.items()):
        coverage = {
            m: zone.intersection(variants[m]["person"].roi).area / zone.area for m, _ in maps
        }
        best = max(coverage, key=lambda m: coverage[m])  # max() keeps the first map on ties
        entry = {"coverage_by_map": {m: round(c, 4) for m, c in coverage.items()}, "map": best}
        if coverage[best] <= 0:
            entry.update(
                {"grade": "ANNOTATION_ONLY", "reasons": ["OUTSIDE_C7_MAP_SCOPE"], "figure": None}
            )
            zone_results[zname] = entry
            continue
        person = variants[best]["person"]
        legacy = variants[best]["legacy_office"]
        hulls = [
            h
            for _, h in mv.seating_hulls(person.chairs, rules["seating_link_distance_m"])
            if h.intersects(zone)
        ]
        exclusion = mv.union_all(hulls) if hulls else Polygon()
        comp = mv.compare_zone(zone, contexts[(best, "person")], exclusion, rules)
        legacy_hulls = [
            h
            for _, h in mv.seating_hulls(legacy.chairs, rules["seating_link_distance_m"])
            if h.intersects(zone)
        ]
        comp_legacy = mv.compare_zone(
            zone,
            contexts[(best, "legacy_office")],
            mv.union_all(legacy_hulls) if legacy_hulls else Polygon(),
            rules,
        )
        # portals adjacent to the zone
        near = zone.buffer(rules["portal_perpendicular_slack_m"])
        zone_portals = sorted(
            n for n, p in annotation.portals.items() if box(*p["bounds_m"]).intersects(near)
        )
        pmatch = map_level[best]["person"]["portals"]
        unpaired = [u for u in pmatch["unmatched_annotation"] if u["portal"] in zone_portals]
        paired = {n: pmatch["paired"][n] for n in zone_portals if n in pmatch["paired"]}
        # routes
        zone_routes = [
            r for r in routes if r["primary_zone"] == zname or zname in r["result"]["zones_hit"]
        ]
        violations = 0
        route_rows = []
        for r in zone_routes:
            count = sum(
                1
                for v in r["result"]["violations"]
                if v["zone"] == zname or (v["zone"] is None and r["primary_zone"] == zname)
            )
            violations += count
            route_rows.append(
                {"route": r["id"], "variant": r["variant"], "violations_in_zone": count}
            )
        graded = mv.grade_zone(
            coverage=comp["coverage"],
            iou_value=comp["iou_eroded"],
            unmatched_annotation_portals=len(unpaired),
            route_violations=violations,
            rules=rules,
        )
        seat = map_level[best]["person"]["seating"]["hulls"]
        seat_in_zone = [h for h in seat if box(*h["hull_bounds_m"]).intersects(zone)]
        thin = thin_cache[(best, "person")]
        thin_in_zone = zone.buffer(0.0)
        thin_summary = {
            k: {
                "count": sum(
                    1 for p in mv._parts(thin[k]["_geometry"]) if p.intersects(thin_in_zone)
                ),
                "area_m2": round(
                    sum(
                        p.area
                        for p in mv._parts(thin[k]["_geometry"])
                        if p.intersects(thin_in_zone)
                    ),
                    4,
                ),
            }
            for k in (
                "narrow_walkable",
                "thin_barrier_in_walkable",
                "raw_obstacle_thinner_than_cell",
            )
        }
        entry.update(
            {
                **graded,
                "comparison_person": mv.strip_geometry(comp),
                "comparison_legacy": mv.strip_geometry(comp_legacy),
                "portals_adjacent": zone_portals,
                "portals_paired": paired,
                "portals_unpaired_annotation": unpaired,
                "routes": route_rows,
                "route_violations": violations,
                "seating_hulls": seat_in_zone,
                "thin_features_in_zone": thin_summary,
            }
        )
        fig_path = args.figures_dir / f"{zname}.png"
        evidence = {
            "iou": comp["iou_eroded"],
            "grade": graded["grade"],
            "ann_blocks_geom": comp["annotation_only_blocks"]["_geometry"],
            "der_blocks_geom": comp["derived_only_blocks"]["_geometry"],
            "thin_geom": mv.union_all(
                [
                    thin["narrow_walkable"]["_geometry"],
                    thin["thin_barrier_in_walkable"]["_geometry"],
                ]
            ),
            "hulls": hulls,
        }
        size = render_zone_figure(
            fig_path,
            zname,
            zone,
            person,
            annotation,
            evidence,
            [r for r in routes if r["map"] == best],
            best,
        )
        entry["figure"] = str(fig_path.name)
        figure_sizes[fig_path.name] = size
        zone_results[zname] = entry

    result = {
        "schema_version": SCHEMA,
        "c7_commit": args.c7_commit,
        "grading_rules": rules,
        "inputs": {
            **{f"map:{n}": {"file": p.name, "sha256": sha256_of(p)} for n, p in maps},
            "annotation": {"file": args.annotation.name, "sha256": sha256_of(args.annotation)},
            **{
                f"route:{n}": {
                    "file": f"{p.parent.name}/{p.name}",
                    "sha256": sha256_of(p),
                    "classification": "GT_OFFLINE_EVALUATION_ONLY",
                }
                for n, p in route_inputs
            },
        },
        "annotation_notes": {
            "unit_scale_m": unit,
            "area_objects_present": any(
                s["surface_id"].startswith("AREA_") for s in ann_doc["surfaces"]
            ),
            "walk_zone_count": len(annotation.zones),
            "threshold_strip_count": len(annotation.thresholds),
            "obstacle_count": len(annotation.obstacles),
            "portal_count": len(annotation.portals),
        },
        "gt_policy": "Route files are renderer ground truth, read for offline evaluation only; "
        "this record holds violation time/distance/zone and no route coordinates; "
        "nothing here modifies a map (CP1 D10).",
        "map_level": mv.strip_geometry(map_level),
        "routes": route_results,
        "zones": zone_results,
        "grade_table": {
            z: {"grade": e["grade"], "reasons": e["reasons"], "map": e.get("map")}
            for z, e in zone_results.items()
        },
        "figure_bytes": figure_sizes,
        "deviations": [
            "Comparison domain (zone plus touching OBSTACLE annotations) was fixed after a first "
            "partial run on the Office map showed that the zone polygon alone hid a 66 m2 "
            "disagreement; the zone-polygon-only IoU is kept as iou_eroded_zone_polygon_only. "
            "Thresholds were not changed.",
        ],
    }
    args.output.write_text(
        json.dumps(mv.strip_geometry(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output} and {len(figure_sizes)} figures")


if __name__ == "__main__":
    main()

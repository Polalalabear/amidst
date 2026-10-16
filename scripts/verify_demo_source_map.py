"""Post-freeze C7 cross-checks; annotations/observations never enter map derivation."""

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

from shapely.geometry import LineString, MultiPoint, Point, shape
from shapely.ops import nearest_points, unary_union

from amidst.geometry.source_floor_map import digest, load_polygon_floor_map


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--annotation-geometry", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--safe-inputs", required=True, type=Path)
    parser.add_argument("--k1-ref", default="origin/claude/k1-hypothesis")
    parser.add_argument("--c6-ref", default="codex/c6-multicamera-feasibility")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    frozen_sha = sha(args.map)
    data = json.loads(args.map.read_text())
    if data["output_sha256"] != digest({k: v for k, v in data.items() if k != "output_sha256"}):
        raise ValueError("MAP_HASH_INVALID")
    k1_commit = subprocess.check_output(["git", "rev-parse", args.k1_ref], text=True).strip()
    source = subprocess.check_output(
        ["git", "show", args.k1_ref + ":src/amidst/blind_hypothesis/floor_map.py"]
    )
    module = types.ModuleType("c7_verified_k1_map_types")
    sys.modules[module.__name__] = module
    exec(compile(source, "K1-floor-map-" + k1_commit, "exec"), module.__dict__)
    maps = {
        key: load_polygon_floor_map(
            args.map,
            variant=key,
            expected_sha256=frozen_sha,
            expected_source_sha256=data["source_sha256"],
            map_class=module.PolygonFloorMap,
            descriptor_class=module.FloorMapDescriptor,
        )
        for key in data["variants"]
    }
    # All diagnostic inputs are opened only after the map and its K1 adapter load.
    annotation = json.loads(args.annotation_geometry.read_text())
    safe = json.loads(args.safe_inputs.read_text())
    if (
        annotation["source_sha256"] != data["source_sha256"]
        or safe["source_binding"]["source_sha256"] != data["source_sha256"]
    ):
        raise ValueError("DIAGNOSTIC_SOURCE_MISMATCH")
    scale = data["config"]["metres_per_blender_unit"]
    surfaces = {r["surface_id"]: r for r in annotation["surfaces"]}

    def polygon(name):
        value = surfaces[name]
        return MultiPoint([(v[0] * scale, v[1] * scale) for v in value["vertices"]]).convex_hull

    coarse = polygon("OBSTACLE_1F_OFFICE_01")
    all_queries = json.loads(args.observations.read_text())
    matched = []

    def walk(value):
        if isinstance(value, dict):
            if value.get("observation_ref") == "observation:997166541f223b4f923d8bff":
                matched.append(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(all_queries)
    points = {tuple(r["world_position"]) for r in matched}
    if len(points) != 1:
        raise ValueError("ENDPOINT_DIAGNOSTIC_NOT_UNIQUE")
    point = Point(next(iter(points))[:2])
    variant_reports = {}
    for key, variant in data["variants"].items():
        floor_map = maps[key]
        free = unary_union(list(floor_map.regions.values()))
        furniture = unary_union([shape(r["geometry"]) for r in variant["furniture"]])
        obstacles = unary_union([shape(r["footprint"]) for r in variant["obstacle_footprints"]])
        variant_reports[key] = {
            "body_radius_m": variant["parameters"]["body_radius_m"],
            "body_height_m": variant["parameters"]["body_height_m"],
            "k1_regions": len(floor_map.regions),
            "k1_portals": len(floor_map.portals),
            "legacy_8_6_point_in_body_centre_domain": free.covers(point),
            "legacy_8_6_point_in_source_obstacle_footprint": obstacles.covers(point),
            "coarse_annotation_overlap_furniture_area_m2": coarse.intersection(furniture).area,
            "coarse_annotation_overlap_source_obstacle_area_m2": coarse.intersection(
                obstacles
            ).area,
            "coarse_annotation_overlap_body_centre_area_m2": coarse.intersection(free).area,
            "furniture_assemblies_intersecting_coarse_annotation": [
                r["assembly_id"]
                for r in variant["furniture"]
                if shape(r["geometry"]).intersects(coarse)
            ],
        }
    gaps = []
    for a, b in [
        ("WALK_1F_AUDITORIUM_OFFICE_THRESHOLD", "WALK_1F_AUDITORIUM"),
        ("WALK_1F_CORRIDOR_03", "WALK_1F_AUDITORIUM_THRESHOLD"),
    ]:
        left, right = polygon(a), polygon(b)
        distance = left.distance(right)
        near = nearest_points(left, right)
        band = (
            left.buffer(distance + 1e-6)
            .intersection(right.buffer(distance + 1e-6))
            .difference(left.union(right))
        )
        result = {
            "annotation_pair": [a, b],
            "annotation_gap_m": distance,
            "nearest_gap_segment_m": [list(p.coords)[0] for p in near],
            "comparison_band": band.__geo_interface__,
            "source_floor_fraction_of_band": shape(data["floor"]["geometry"])
            .intersection(band)
            .area
            / band.area,
            "variants": {},
        }
        for key, variant in data["variants"].items():
            free = unary_union(list(maps[key].regions.values()))
            portals = []
            for p in variant["portals"]:
                geometry = shape(p["geometry"])
                d = geometry.distance(band)
                if d <= 0.5:
                    portals.append(
                        {
                            "portal_id": p["portal_id"],
                            "distance_to_annotation_gap_band_m": d,
                            "intersects_gap_band": geometry.intersects(band),
                            "opening_width_m": p["opening_width_m"],
                        }
                    )
            result["variants"][key] = {
                "source_openings_within_0_5m_of_gap_band": portals,
                "body_centre_fraction_of_gap_band": free.intersection(band).area / band.area,
                "nearest_gap_segment_body_clear": free.covers(
                    LineString([p.coords[0] for p in near])
                ),
                "interpretation": "GEOMETRIC_CROSSCHECK_NOT_SEMANTIC_PORTAL_APPROVAL",
            }
        gaps.append(result)
    c6_raw = subprocess.check_output(
        ["git", "show", args.c6_ref + ":docs/engineering/C6_FIXED_FRAME_SCREEN_20261017.json"]
    )
    c6 = json.loads(c6_raw)
    checks = []
    support = shape(data["floor"]["geometry"])
    for route in c6["candidates"]:
        path = LineString([p[:2] for p in route["waypoints_m"]])
        inside = support.covers(path)
        checks.append(
            {
                "benchmark_id": route["benchmark_id"],
                "status": "OUTSIDE_SOURCE_MAP_SCOPE"
                if not inside
                else "PASS"
                if unary_union(list(maps["person"].regions.values())).covers(path)
                else "REJECT_BODY_CENTRE_DOMAIN",
                "source_supported_length_m": support.intersection(path).length,
                "route_length_m": path.length,
            }
        )
    planner = Path("scripts/plan_blender_pilot_sites.py")
    spec = None
    for node in ast.walk(ast.parse(planner.read_text())):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Tuple)
            and [getattr(e, "id", None) for e in t.elts]
            == ["radius", "height", "probe_height", "margin"]
            for t in node.targets
        ):
            spec = ast.literal_eval(node.value)
    if spec is None:
        raise ValueError("LEGACY_MARKER_DECLARATION_NOT_FOUND")
    radius, height, probe, margin = spec
    result = {
        "schema_version": "office-demo.c7-source-map-verification.v1",
        "authority": "POST_FREEZE_DIAGNOSTIC_NOT_MAP_INPUT",
        "map_sha256": frozen_sha,
        "source_sha256": data["source_sha256"],
        "producer_sha256": sha(__file__),
        "k1_commit": k1_commit,
        "k1_floor_map_module_sha256": hashlib.sha256(source).hexdigest(),
        "k1_types_constructed_without_modification": True,
        "annotations_sha256": sha(args.annotation_geometry),
        "observations_sha256": sha(args.observations),
        "safe_inputs_sha256": sha(args.safe_inputs),
        "diagnostic_inputs_opened_after_map_freeze": True,
        "gt_read": False,
        "floor_height": {
            "derived_m": data["floor"]["evidence"]["height_m"],
            "annotation_1F_m": next(
                f["point"][2] * scale for f in annotation["floors"] if f["floor_id"] == "1F"
            ),
            "source_bound_projection_plane_m": safe["floor_plane"]["point"][2],
            "annotation_minus_derived_m": next(
                f["point"][2] * scale for f in annotation["floors"] if f["floor_id"] == "1F"
            )
            - data["floor"]["evidence"]["height_m"],
            "derived_minus_projection_m": data["floor"]["evidence"]["height_m"]
            - safe["floor_plane"]["point"][2],
        },
        "legacy_proxy_origin": {
            "planner_sha256": sha(planner),
            "renderer_sha256": sha("scripts/export_blender_pilot.py"),
            "radius_bu": radius,
            "height_bu": height,
            "probe_height_bu": probe,
            "foot_clearance_bu": margin,
            "height_formula": "2 * probe_height_bu + 1.5 * radius_bu",
            "formula_matches": height == 2 * probe + 1.5 * radius,
            "height_m": height * scale,
            "radius_m": radius * scale,
            "unit_conversion_error": False,
            "original_design_rationale_for_native_size": "UNKNOWN",
            "actual_proxy_kind": "CYLINDER_PLUS_SPHERE_CAPSULE_ENVELOPE",
        },
        "legacy_endpoint": {
            "observation_ref": "observation:997166541f223b4f923d8bff",
            "world_position_m": list(next(iter(points))),
            "inside_coarse_obstacle_annotation": coarse.covers(point),
        },
        "coarse_annotation_area_m2": coarse.area,
        "variant_comparison": variant_reports,
        "doorway_gap_comparison": gaps,
        "c6_routes_sha256": hashlib.sha256(c6_raw).hexdigest(),
        "c6_rechecks": checks,
        "physical_navigation": "NOT_CERTIFIED",
        "map_unchanged": sha(args.map) == frozen_sha,
    }
    result["output_sha256"] = digest(result)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "floor_height": result["floor_height"],
                "variant_comparison": variant_reports,
                "gaps": [{k: v for k, v in g.items() if k != "comparison_band"} for g in gaps],
                "c6_statuses": {
                    s: sum(r["status"] == s for r in checks)
                    for s in sorted({r["status"] for r in checks})
                },
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

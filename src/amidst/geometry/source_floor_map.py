"""Bounded source-mesh floor maps; no annotation, observation or GT inputs.

This derives a nominal upright-body centre domain. It does not certify real
navigation, room semantics, completeness outside its explicit camera ROI, or
all possible door orientations. Source material transparency is not collision.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPoint, Polygon, box, mapping, shape
from shapely.ops import unary_union


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def z_clip(points, boundary, above):
    result = []
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        va, vb = a[2] - boundary, b[2] - boundary
        inside_a, inside_b = (va >= 0, vb >= 0) if above else (va <= 0, vb <= 0)
        if inside_a:
            result.append(a)
        if inside_a != inside_b:
            fraction = va / (va - vb)
            result.append([a[k] + fraction * (b[k] - a[k]) for k in range(3)])
    return result


def world_triangles(obj, definitions, scale, roi):
    geometry = definitions[obj["geometry_sha256"]]
    if digest(geometry) != obj["geometry_sha256"]:
        raise ValueError("EVALUATED_GEOMETRY_HASH_MISMATCH")
    if not geometry["triangles"]:
        return np.empty((0, 3, 3))
    matrix = np.asarray(obj["matrix_world_bu"], dtype=float)
    points = (np.asarray(geometry["vertices"]) @ matrix[:3, :3].T + matrix[:3, 3]) * scale
    triangles = points[np.asarray(geometry["triangles"], dtype=int)]
    low, high = np.asarray(roi[0]), np.asarray(roi[1])
    selected = np.all(triangles.max(axis=1) >= low, axis=1) & np.all(
        triangles.min(axis=1) <= high, axis=1
    )
    return triangles[selected]


def floor_from_triangles(objects, config, roi, roi_polygon=None):
    patches = []
    all_patches = []
    bins = defaultdict(float)
    normal_min = config["floor_normal_min_abs_z"]
    if roi_polygon is None:
        roi_polygon = box(roi[0][0], roi[0][1], roi[1][0], roi[1][1])
    low, high = config["floor_top_search_z_m"]
    for obj, triangles in objects:
        if any(
            (obj.get("parent") or "").startswith(p) for p in config["furniture_assembly_prefixes"]
        ):
            continue
        object_patches = []
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        accepted = (
            (lengths > 1e-12)
            & (np.abs(normals[:, 2]) >= normal_min * lengths)
            & (
                triangles[:, :, 2].max(axis=1) - triangles[:, :, 2].min(axis=1)
                <= config["floor_height_tolerance_m"]
            )
        )
        for tri in triangles[accepted]:
            z = float(tri[:, 2].mean())
            if not low <= z <= high:
                continue
            footprint = Polygon(tri[:, :2]).intersection(roi_polygon)
            if footprint.area <= 1e-10:
                continue
            key = round(z / config["floor_mode_bin_m"])
            object_patches.append((key, z, footprint, obj["instance_ref"]))
        all_patches.extend((z, footprint, ref) for _, z, footprint, ref in object_patches)
        for key in sorted({p[0] for p in object_patches}):
            level = [p for p in object_patches if p[0] == key]
            union = unary_union([p[2] for p in level])
            if (
                max((p.area for p in polygon_components(union)), default=0)
                < config["minimum_floor_patch_area_m2"]
            ):
                continue
            for _, z, footprint, ref in level:
                bins[key] += footprint.area
                patches.append((z, footprint, ref))
    if not bins:
        raise ValueError("SOURCE_FLOOR_SUPPORT_UNAVAILABLE")
    mode = max(sorted(bins), key=lambda k: bins[k])
    chosen = [
        r
        for r in patches
        if abs(r[0] - mode * config["floor_mode_bin_m"]) <= config["floor_height_tolerance_m"]
    ]
    height = sum(z * p.area for z, p, _ in chosen) / sum(p.area for _, p, _ in chosen)
    anchors = unary_union([p for _, p, _ in chosen])
    candidates = [
        r for r in all_patches if abs(r[0] - height) <= config["floor_height_tolerance_m"]
    ]
    support = unary_union([p for _, p, _ in candidates])
    geometry = shapely.set_precision(
        unary_union(
            [part for part in polygon_components(support) if part.intersection(anchors).area > 1e-8]
        ),
        config["precision_grid_m"],
    )
    support_refs = sorted({ref for _, p, ref in candidates if p.intersection(geometry).area > 1e-8})
    return (
        height,
        geometry,
        {
            "height_m": height,
            "height_range_m": [min(r[0] for r in chosen), max(r[0] for r in chosen)],
            "source_instance_refs": support_refs,
            "level_anchor_instance_refs": sorted({r[2] for r in chosen}),
            "selected_horizontal_triangles": len(chosen),
            "candidate_height_bin_area_m2": {
                str(k * config["floor_mode_bin_m"]): v for k, v in sorted(bins.items())
            },
        },
    )


def body_footprint(triangles, z_low, z_high, roi_polygon, *, convex=False, precision=1e-5):
    if not len(triangles):
        return Polygon()
    low = triangles[:, :, 2].min(axis=1)
    high = triangles[:, :, 2].max(axis=1)
    keep = (high >= z_low) & (low <= z_high)
    tris = triangles[keep]
    low = low[keep]
    high = high[keep]
    inside = (low >= z_low) & (high <= z_high)
    polygons = []
    points = []
    lines = []
    for tri in tris[~inside]:
        polygon = z_clip(z_clip(tri.tolist(), z_low, True), z_high, False)
        if polygon:
            points.extend([p[:2] for p in polygon])
        if not convex and len(polygon) >= 2:
            g = MultiPoint([p[:2] for p in polygon]).convex_hull
            if not g.is_empty:
                polygons.append(g)
    if convex:
        if inside.any():
            points.extend(tris[inside, :, :2].reshape(-1, 2).tolist())
        return MultiPoint(points).convex_hull.intersection(roi_polygon) if points else Polygon()
    xy = tris[inside, :, :2]
    if len(xy):
        u, v = xy[:, 1] - xy[:, 0], xy[:, 2] - xy[:, 0]
        areas = np.abs(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0])
        if (areas > 1e-10).any():
            polygons.extend(shapely.polygons(xy[areas > 1e-10]).tolist())
        for tri in xy[areas <= 1e-10]:
            pairs = [(tri[a], tri[b]) for a, b in ((0, 1), (0, 2), (1, 2))]
            a, b = max(pairs, key=lambda pair: np.linalg.norm(pair[1] - pair[0]))
            if np.linalg.norm(b - a) > 1e-8:
                lines.append(LineString([a, b]))
    # Dense evaluated furniture can have near-coincident projected edges. Apply
    # the declared coordinate grid during noding, before union (not afterwards).
    return (
        shapely.union_all(polygons + lines, grid_size=precision).intersection(roi_polygon)
        if polygons or lines
        else Polygon()
    )


def wall_flanks(objects, floor_z, config):
    """Low body-height architectural faces; potential doorway flanks, not labels."""
    result = []
    tol = config["portal"]["axis_tolerance_m"]
    minimum = config["portal"]["min_flank_length_m"]
    for obj, tris in objects:
        parent = obj.get("parent") or ""
        if any(parent.startswith(p) for p in config["furniture_assembly_prefixes"]):
            continue
        for tri in tris:
            if tri[:, 2].min() > floor_z + 0.15 or tri[:, 2].max() < floor_z + 0.25:
                continue
            xy = tri[:, :2]
            span = xy.max(axis=0) - xy.min(axis=0)
            for axis in (0, 1):
                if span[axis] >= minimum and span[1 - axis] <= tol:
                    result.append(
                        (
                            axis,
                            float(xy[:, 1 - axis].mean()),
                            float(xy[:, axis].min()),
                            float(xy[:, axis].max()),
                        )
                    )
    return result


def derive_portals(flanks, free, roi_polygon, config, radius):
    policy = config["portal"]
    tol = policy["axis_tolerance_m"]
    groups = defaultdict(list)
    for axis, constant, low, high in flanks:
        groups[(axis, round(constant / tol))].append((low, high, constant))
    found = []
    for (axis, _), intervals in sorted(groups.items()):
        merged = []
        for lo, hi, c in sorted(intervals):
            if merged and lo <= merged[-1][1] + tol:
                merged[-1][1] = max(hi, merged[-1][1])
            else:
                merged.append([lo, hi, c])
        for a, b in zip(merged, merged[1:], strict=False):
            width = b[0] - a[1]
            if not policy["min_width_m"] <= width <= policy["max_width_m"] or width <= 2 * radius:
                continue
            constant = (a[2] + b[2]) / 2
            middle = (a[1] + b[0]) / 2
            depth = policy["half_depth_m"]
            if axis == 0:
                crossing = LineString([(middle, constant - depth), (middle, constant + depth)])
                aperture = box(a[1] + radius, constant - depth, b[0] - radius, constant + depth)
            else:
                crossing = LineString([(constant - depth, middle), (constant + depth, middle)])
                aperture = box(constant - depth, a[1] + radius, constant + depth, b[0] - radius)
            if not free.covers(crossing):
                continue
            polygon = aperture.intersection(free).intersection(roi_polygon)
            if polygon.is_empty or polygon.area <= 1e-6:
                continue
            if any(
                polygon.intersection(shape(old["geometry"])).area
                / min(polygon.area, shape(old["geometry"]).area)
                > 0.5
                for old in found
            ):
                continue
            found.append(
                {
                    "portal_id": "portal:" + digest([axis, constant, a[1], b[0]])[:16],
                    "tier": "SOURCE_DERIVED",
                    "geometry": mapping(polygon),
                    "opening_width_m": width,
                    "nominal_body_diameter_m": 2 * radius,
                    "axis": axis,
                    "wall_coordinate_m": constant,
                    "opening_interval_m": [a[1], b[0]],
                    "crossing_line_m": list(crossing.coords),
                    "evidence": "SOURCE_LOW_WALL_FLANK_GAP_AND_FULL_BODY_FREE_CROSSING",
                    "semantic_door_status": "GEOMETRIC_OPENING_NOT_DOOR_LABEL",
                }
            )
    return found


def polygon_components(geometry):
    if geometry.geom_type == "Polygon":
        return [geometry] if geometry.area > 1e-8 else []
    return [p for g in getattr(geometry, "geoms", []) for p in polygon_components(g)]


def derive_source_map(extract, *, extract_sha256):
    config = extract["config"]
    if (
        extract["annotations_as_inputs"]
        or extract["gt_read"]
        or extract["source_saved"]
        or extract["render_executed"]
    ):
        raise ValueError("SOURCE_ONLY_EVIDENCE_REQUIRED")
    if extract["source_sha256"] != config["source_sha256"]:
        raise ValueError("SOURCE_HASH_MISMATCH")
    scale = config["metres_per_blender_unit"]
    roi = extract["roi_m"]
    roi_polygon = unary_union(
        [box(b[0][0], b[0][1], b[1][0], b[1][1]) for b in extract.get("roi_xy_boxes_m", [roi])]
    )
    objects = [
        (obj, world_triangles(obj, extract["geometry_definitions"], scale, roi))
        for obj in extract["objects"]
    ]
    objects = [r for r in objects if len(r[1])]
    floor_z, floor, floor_evidence = floor_from_triangles(objects, config, roi, roi_polygon)
    flanks = wall_flanks(objects, floor_z, config)
    variants = {}
    for variant, parameters in config["run_parameters"].items():
        footprints = []
        furniture = defaultdict(list)
        source_ledger = []
        for obj, triangles in objects:
            parent = obj.get("parent") or ""
            is_furniture = any(parent.startswith(p) for p in config["furniture_assembly_prefixes"])
            footprint = body_footprint(
                triangles,
                floor_z + config["body_floor_exclusion_m"],
                floor_z + parameters["body_height_m"],
                roi_polygon,
                convex=is_furniture,
                precision=config["precision_grid_m"],
            )
            if footprint.is_empty:
                continue
            footprint = shapely.set_precision(footprint, config["precision_grid_m"])
            if footprint.is_empty:
                continue
            footprints.append(footprint)
            source_ledger.append(
                {
                    **obj,
                    "footprint": mapping(footprint),
                    "footprint_area_m2": footprint.area,
                    "footprint_method": "CONSERVATIVE_COMPONENT_XY_HULL"
                    if is_furniture
                    else "BODY_SLAB_PROJECTED_TRIANGLE_UNION_WITH_ZERO_THICKNESS_LINES",
                }
            )
            if is_furniture:
                furniture[parent].append((obj, footprint))
        radius = parameters["body_radius_m"]
        quad = config["buffer_quadrant_segments"]
        effective = radius / math.cos(math.pi / (4 * quad)) + 2 * config["precision_grid_m"]
        obstacles = unary_union(footprints)
        free = shapely.set_precision(
            floor.buffer(-effective, quad_segs=quad).difference(
                obstacles.buffer(effective, quad_segs=quad)
            ),
            config["precision_grid_m"],
        )
        regions = [
            {
                "region_id": "region:" + digest(mapping(p))[:16],
                "tier": "SOURCE_DERIVED",
                "walkable": "TRUE",
                "geometry": mapping(p),
                "area_m2": p.area,
            }
            for p in sorted(polygon_components(free), key=lambda p: (p.bounds, p.area))
        ]
        portals = derive_portals(flanks, free, roi_polygon, config, radius)
        furniture_records = []
        for assembly, parts in sorted(furniture.items()):
            geom = unary_union([g for _, g in parts])
            furniture_records.append(
                {
                    "assembly_id": assembly,
                    "kind_from_source_parent": "CHAIR"
                    if assembly.startswith("Theatre Chair")
                    else "LECTERN",
                    "tier": "SOURCE_DERIVED",
                    "semantic_authority": "SOURCE_PARENT_LABEL_ONLY",
                    "source_instance_refs": [o["instance_ref"] for o, _ in parts],
                    "geometry": mapping(geom),
                    "area_m2": geom.area,
                    "bounds_m": list(geom.bounds),
                }
            )
        variants[variant] = {
            "parameters": parameters,
            "floor_z_m": floor_z,
            "effective_conservative_buffer_radius_m": effective,
            "body_centre_domain": True,
            "physical_navigation": "NOT_CERTIFIED",
            "regions": regions,
            "unknown_regions": [],
            "portals": portals,
            "obstacle_footprints": source_ledger,
            "furniture": furniture_records,
            "walkable_area_m2": free.area,
            "floor_support_area_m2": floor.area,
            "limitations": [
                "AXIS_ALIGNED_PORTAL_CANDIDATES_ONLY",
                "SEMANTIC_ROOM_AND_DOOR_LABELS_NOT_CERTIFIED",
                "OUTSIDE_ROI_UNKNOWN",
                "SOURCE_MESH_NOMINAL_BODY_MODEL_NOT_REAL_NAVIGATION",
            ],
        }
    result = {
        "schema_version": "office-demo.source-floor-map.v1",
        "source_sha256": extract["source_sha256"],
        "source_size": extract["source_size"],
        "source_mtime_ns": extract["source_mtime_ns"],
        "source_identity_unchanged": extract["source_identity_unchanged"],
        "source_saved": False,
        "render_executed": False,
        "annotations_as_inputs": False,
        "gt_read": False,
        "physical_navigation": "NOT_CERTIFIED",
        "config_sha256": extract["config_sha256"],
        "extract_sha256": extract_sha256,
        "extract_producer_sha256": extract["producer_sha256"],
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "evaluated_scene": extract["evaluated_scene"],
        "config": config,
        "roi_m": roi,
        "roi_geometry": mapping(roi_polygon),
        "cameras": extract.get("cameras", []),
        "source_objects": extract["objects"],
        "geometry_definition_summary": {
            h: {"vertices": len(g["vertices"]), "triangles": len(g["triangles"])}
            for h, g in extract["geometry_definitions"].items()
        },
        "floor": {"geometry": mapping(floor), "evidence": floor_evidence},
        "variants": variants,
    }
    result["output_sha256"] = digest(result)
    return result


def load_polygon_floor_map(
    path, *, variant, expected_sha256, expected_source_sha256, map_class=None, descriptor_class=None
):
    """Construct K1 PolygonFloorMap without modifying or importing K1 on build.

    map_class / descriptor_class allow the unmerged K1 module to be injected for
    verification; defaults import the real K1 types once both PRs are integrated.
    """
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("MAP_BUNDLE_HASH_MISMATCH")
    bundle = json.loads(raw)
    if digest({k: v for k, v in bundle.items() if k != "output_sha256"}) != bundle["output_sha256"]:
        raise ValueError("MAP_OUTPUT_HASH_MISMATCH")
    if (
        bundle["source_sha256"] != expected_source_sha256
        or bundle["annotations_as_inputs"]
        or bundle["gt_read"]
    ):
        raise ValueError("MAP_SOURCE_AUTHORITY_MISMATCH")
    if map_class is None or descriptor_class is None:
        from amidst.blind_hypothesis.floor_map import FloorMapDescriptor, PolygonFloorMap

        map_class, descriptor_class = PolygonFloorMap, FloorMapDescriptor
    chosen = bundle["variants"][variant]
    ref = "source-map:" + expected_sha256[:24]
    descriptor = descriptor_class(
        kind="SOURCE_DERIVED",
        map_ref=ref,
        sha256=expected_sha256,
        walkable_ref=ref + "#" + variant + "/regions",
        portal_ref=ref + "#" + variant + "/portals",
        floor_id="1F",
    )
    return map_class(
        descriptor=descriptor,
        floor_z_m=chosen["floor_z_m"],
        regions={r["region_id"]: shape(r["geometry"]) for r in chosen["regions"]},
        portals={r["portal_id"]: shape(r["geometry"]) for r in chosen["portals"]},
        unknown_regions={r["region_id"]: shape(r["geometry"]) for r in chosen["unknown_regions"]},
        region_tiers={
            r["region_id"]: r["tier"] for r in chosen["regions"] + chosen["unknown_regions"]
        },
    )

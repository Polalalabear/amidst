"""Source-bound static geometry supplements for the r004 review packet.

Everything produced here is PROPOSED. No actor, event, GT, detector, model,
runtime approval, physical traversal certification, or new timeout policy.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import itertools
import json
import math
import shutil
from collections import deque
from copy import deepcopy
from html import escape
from pathlib import Path


class ReviewError(ValueError):
    pass


def rectangle_supported(bounds, z, mesh):
    """Exact rectangular-cell union check, including interior holes."""
    x0, x1, y0, y1 = bounds
    rectangles = []
    for face in mesh["triangles_or_polygons"]:
        pts = [mesh["vertices_world_m"][i] for i in face]
        if not all(abs(p[2] - z) < 1e-5 for p in pts):
            continue
        xs, ys = sorted({p[0] for p in pts}), sorted({p[1] for p in pts})
        if len(pts) != 4 or len(xs) != 2 or len(ys) != 2:
            raise ReviewError("Exact rectangular source cells required")
        rectangles.append((xs[0], xs[1], ys[0], ys[1]))
    xs = sorted({x0, x1} | {x for r in rectangles for x in r[:2] if x0 < x < x1})
    ys = sorted({y0, y1} | {y for r in rectangles for y in r[2:] if y0 < y < y1})
    return all(any(a <= (l + r) / 2 <= b and c <= (s + t) / 2 <= d
                   for a, b, c, d in rectangles)
               for l, r in zip(xs, xs[1:], strict=False) for s, t in zip(ys, ys[1:], strict=False))


def rectangle_patch(cal, support, bounds, triangles):
    x0, x1, y0, y1 = bounds
    if not all(math.isfinite(x) for x in bounds) or not (x0 < x1 and y0 < y1):
        raise ReviewError("Finite nonempty rectangle required")
    z = max(v[2] for v in support["vertices_world_m"])
    if not rectangle_supported(bounds, z, support):
        raise ReviewError("Rectangle crosses unsupported floor")
    xy = [(x0, y0), (x1, y0), (x1, y1), (x0, y1),
          ((x0+x1)/2, (y0+y1)/2), ((x0+x1)/2, y0), (x1, (y0+y1)/2),
          ((x0+x1)/2, y1), (x0, (y0+y1)/2)]
    points = [[x, y, z] for x, y in xy]
    if not all(static_witness(cal, point, triangles) for point in points):
        raise ReviewError("Rectangle lacks nine unoccluded in-frame witnesses")
    polygon = [project(cal, point) for point in points[:4]]
    return {"polygon_world_m": points[:4], "roi_polygon_px": polygon,
            "support_object_ref": support["object_ref"], "support_sha256": digest(support),
            "witness_world_m": points, "static_witness_count": 9, "status": "PROPOSED",
            "method": "EXPLICIT_STATIC_RECTANGLE_V3", "support_coverage": "EXACT_CELL_UNION",
            "limits": "Nine static foot witnesses; not whole-person or first-appearance authority."}


def pair_inventory(catalog_ids, transitions):
    """Account for all 8*7 directed pairs without inventing new transitions."""
    existing = {(t["from_camera_id"], t["to_camera_id"]): t["transition_id"] for t in transitions}
    deferred = {frozenset(pair) for pair in [("CAM_BRANCH", "CAM_WIDE"),
                                            ("CAM_EXT_CAR", "CAM_EXT_CLEAR")]}
    result = []
    for source, target in itertools.permutations(sorted(catalog_ids), 2):
        if (source, target) in existing:
            row = {"transition_id": existing[source, target], "disposition": "TRANSITION"}
        elif "CAM_ENTRY" in (source, target):
            row = {"disposition": "EXCLUDED", "reason": "D74_CAM_ENTRY_QUERY_ONLY"}
        elif frozenset((source, target)) in deferred:
            row = {"disposition": "EXCLUDED", "reason": "D77_OVERLAP_DEFERRED_UNTIL_Q5_STABLE"}
        elif {source, target} == {"CAM_W1", "CAM_W2"}:
            row = {"disposition": "EXCLUDED", "reason": "SAME_REGION_OVERLAP_NOT_IN_BLIND_SEARCH_V1"}
        else:
            row = {"disposition": "EXCLUDED", "reason": "OUTSIDE_INHERITED_V2_DIRECT_PAIR_SCOPE_NOT_PROOF_OF_IMPOSSIBILITY"}
        result.append({"from_camera_id": source, "to_camera_id": target, **row})
    return result


def build_graph_v3(config_path, config_sha256, membership_path, membership_sha256,
                   prior_pack, prior_manifest_sha256, output):
    """D74/D77 graph data only; safe static inputs, no events or approvals."""
    config = pinned(config_path, config_sha256)
    if config.get("schema_version") != "q-demo.r004-graph-v3-build.v1":
        raise ReviewError("Explicit v3 plan required")
    prior = Path(prior_pack).absolute()
    output = Path(output).absolute()
    if prior.resolve() != prior or output.resolve() != output or output.exists():
        raise ReviewError("Canonical source and new output required")
    if shutil.disk_usage(output.parent).free < 8 * 1024**3:
        raise ReviewError("DISK_BELOW_8_GIB")
    manifest = pinned(prior / "MANIFEST.json", prior_manifest_sha256)
    for name, pin in manifest["files"].items():
        path = prior / name
        if not path.resolve().is_relative_to(prior) or path.is_symlink():
            raise ReviewError("Prior path scope mismatch")
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ReviewError("Prior immutable packet mismatch")
    names = ["source_static_geometry", "static_membership", "region_meshes", "region_graph",
             "camera_graph", "camera_catalog", "static_patches"]
    docs = {}
    source_pins = {}
    for name in names:
        relative = "provenance/" + name + ".json"
        pin = manifest["files"][relative]
        docs[name] = pinned(prior / relative, pin)
        source_pins[relative] = pin
    record = pinned(membership_path, membership_sha256)
    if record != docs["static_membership"]:
        raise ReviewError("Membership must be the pinned prior record")
    static = docs["source_static_geometry"]
    blend = Path(config["source_blend_path"])
    if (blend.suffix != ".blend" or blend.is_symlink() or not blend.is_file()
            or hashlib.sha256(blend.read_bytes()).hexdigest() != static["source_sha256"]):
        raise ReviewError("Source blend file pin mismatch")
    scope = membership(static, record)
    if tuple(map(len, [scope["render_enabled_objects"], scope["support_annotation_meshes"],
                       scope["excluded_source_only_objects"]])) != (15, 6, 22):
        raise ReviewError("Unexpected static membership scope")
    triangles = triangles_for(scope["render_enabled_objects"])
    cals = {c["camera_id"]: c for c in docs["camera_catalog"]["cameras"]}
    if set(cals) != set(config["query_camera_ids"]) or len(cals) != 8:
        raise ReviewError("Exactly eight pinned query cameras required")
    if abs(cals["CAM_WIDE"]["fx"] - 480) > 1e-8:
        raise ReviewError("D76 wide camera must retain 90 degree pinhole")
    meshes = docs["region_meshes"]["meshes"]
    patches, pixels = {}, {}
    for zone in config["zones"]:
        cid, rid, zid = zone["camera_id"], zone["region_id"], zone["zone_id"]
        if cid == "CAM_ENTRY" or cid not in cals or zid in patches:
            raise ReviewError("Invalid/duplicate tracking ROI")
        if "from_v2" in zone:
            old = docs["static_patches"][zone["from_v2"]]
            world = old["polygon_world_m"]
            bounds = [min(p[0] for p in world), max(p[0] for p in world),
                      min(p[1] for p in world), max(p[1] for p in world)]
        elif "bounds" in zone:
            bounds = zone["bounds"]
        else:
            patch = find_patch(cals[cid], meshes[rid], zone["anchor"], triangles)
            world = patch["polygon_world_m"]
            bounds = [min(p[0] for p in world), max(p[0] for p in world),
                      min(p[1] for p in world), max(p[1] for p in world)]
        patch = rectangle_patch(cals[cid], meshes[rid], bounds, triangles)
        patches[zid] = {"camera_id": cid, "region_id": rid, "role": zone["role"],
                        "edge_id": zone.get("edge_id"), **patch}
        uv = patch["roi_polygon_px"]
        heights, depths = [], []
        for point in patch["witness_world_m"]:
            matrix = cals[cid]["camera_to_world"]
            depths.append(-sum(matrix[i][2] * (point[i] - matrix[i][3]) for i in range(3)))
            foot = project(cals[cid], point)
            head = project(cals[cid], [point[0], point[1], point[2] + 1.7])
            heights.append(abs(foot[1] - head[1]) if head else None)
        pixels[zid] = {"bbox_xyxy_px": [min(p[0] for p in uv), min(p[1] for p in uv),
                                         max(p[0] for p in uv), max(p[1] for p in uv)],
                       "person_height_assumption_m": 1.7, "height_px_at_nine_witnesses": heights,
                       "camera_depth_m_at_nine_witnesses": depths,
                       "review_zoom": "Open static ROI SVG and use browser zoom up to 400%; display only, no detector improvement claim.",
                       "recognition": "UNVALIDATED; unresolved actual evidence stays AMBIGUOUS/UNKNOWN"}
    region, camera = deepcopy(docs["region_graph"]), deepcopy(docs["camera_graph"])
    cameras = {c["camera_id"]: c for c in camera["cameras"] if c["camera_id"] != "CAM_ENTRY"}
    static_frames = {c["camera_id"]: c["exit_zones"][0]["static_frame_sha256"]
                     for c in docs["camera_graph"]["cameras"]}
    for cid, cam in cameras.items():
        cam["entry_zones"], cam["exit_zones"] = [], []
        covers = {r["region_id"] for r in cam["covered_regions"]}
        for zid, patch in patches.items():
            if patch["camera_id"] != cid:
                continue
            covers.add(patch["region_id"])
            if patch["role"] == "ENTRY":
                cam["entry_zones"].append({"entry_zone_id": zid, "roi_polygon_px": patch["roi_polygon_px"]})
            else:
                cam["exit_zones"].append({"exit_zone_id": zid, "roi_polygon_px": patch["roi_polygon_px"],
                    "leads_to_edge_ids": [patch["edge_id"]], "mapping_basis": "STATIC_CALIBRATION_PROJECTION",
                    "static_frame_ref": "static-image:r004:" + cid,
                    "static_frame_sha256": static_frames[cid]})
        for rid in config.get("additional_covered_regions", {}).get(cid, []):
            proof = find_patch(cals[cid], meshes[rid], config["coverage_anchors"][cid][rid], triangles)
            covers.add(rid)
            pixels[cid + ":COVER:" + rid] = {"witness_world_m": proof["witness_world_m"],
                                            "static_witness_count": 9, "region_id": rid}
        cam["covered_regions"] = [{"region_id": rid, "basis": "MANUAL_ON_STATIC_FRAME",
                                  "visibility_ref": "static-review:v3:" + cid + ":" + rid,
                                  "visible_area_m2": None} for rid in sorted(covers)]
        if not cam["exit_zones"] or not cam["entry_zones"]:
            raise ReviewError("Tracking cameras need visible entry/exit evidence")
    camera["cameras"] = [cameras[cid] for cid in sorted(cameras)]
    transitions = []
    for old in docs["camera_graph"]["transitions"]:
        source, target = old["from_camera_id"], old["to_camera_id"]
        if "CAM_ENTRY" in (source, target):
            continue
        route = config["transition_routes"][old["transition_id"]]
        row = deepcopy(old)
        row.update(region_path=route["region_path"], edge_path=route["edge_path"],
                   region_hops=len(route["edge_path"]), via_exit_zone_ids=route["via_exit_zone_ids"],
                   to_entry_zone_ids=route["to_entry_zone_ids"], relation="UNKNOWN",
                   ranking_area_m2=None, ranking_area_refs=[], nominal_path_length_m=None,
                   path_traversability="TOPOLOGICAL_ONLY", path_has_unknown_state=True,
                   basis_refs=["static-review:v3:route-and-zones"])
        transitions.append(row)
    camera["transitions"] = sorted(transitions, key=lambda r: r["transition_id"])
    pairs = pair_inventory(cals, transitions)
    tracking = {"schema_version": "q-demo.r004-tracking-scope.v3", "status": "PROPOSED",
                "query_camera_ids": sorted(cals), "tracking_camera_ids": sorted(cameras),
                "query_only_camera_ids": ["CAM_ENTRY"], "directed_pairs": pairs,
                "north_floor_y_gt_12": "OUT_OF_GRAPH; camera retained, no edge/region invented",
                "overlap_pairs_deferred": "D77; no camera pose/FOV changes", "G4_approved": False}
    patch_raw, tracking_raw = canonical(patches) + b"\n", canonical(tracking) + b"\n"
    extra = [{"ref": "static-patches:r004:v3", "sha256": hashlib.sha256(patch_raw).hexdigest()},
             {"ref": "tracking-scope:r004:v3", "sha256": hashlib.sha256(tracking_raw).hexdigest()}]
    region["inputs"] += extra
    seal_graph(region, "rgraph")
    camera["inputs"] += extra
    camera["region_graph_sha256"] = region["content_sha256"]
    seal_graph(camera, "cgraph")
    if any(e["traversability"] != "TOPOLOGICAL_ONLY" or e["state"] != "UNKNOWN"
           for e in region["edges"]):
        raise ReviewError("V3 cannot grant edge authority")
    source_receipt = {"schema_version": "q-demo.r004-v3-source-pins.v1", "files": source_pins,
        "prior_manifest_sha256": prior_manifest_sha256, "source_sha256": static["source_sha256"],
        "plan_sha256": config_sha256, "gt_read": False, "events_read": False, "rendered": False,
        "source_saved": False, "legal_auto_switch_paths": 0, "authority": "PROPOSED_ONLY"}
    output.mkdir(parents=True)
    for name, value in [("region_graph_v3.json", region), ("camera_graph_v3.json", camera),
                        ("static_patches_v3.json", patches), ("roi_report_v3.json", pixels),
                        ("tracking_scope_v3.json", tracking), ("source_pins_v3.json", source_receipt)]:
        (output / name).write_bytes(canonical(value) + b"\n")
    if hashlib.sha256(blend.read_bytes()).hexdigest() != static["source_sha256"]:
        raise ReviewError("Source changed during graph generation")
    return {"roi_count": len(patches), "tracking_cameras": len(cameras), "query_cameras": len(cals),
            "transitions": len(transitions), "directed_pairs": len(pairs), "G4_approved": False}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pinned(path, sha256):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024**2:
        raise ReviewError("Bounded regular input required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ReviewError("Input pin mismatch")
    return json.loads(raw)


def subtract(a, b):
    return [a[i] - b[i] for i in range(3)]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=False))


def segment_triangle(origin, target, triangle):
    """Two-sided segment intersection, excluding the camera and target endpoints."""
    a, b, c = triangle
    direction = subtract(target, origin)
    e1, e2 = subtract(b, a), subtract(c, a)
    h = cross(direction, e2)
    det = dot(e1, h)
    if abs(det) < 1e-10:
        return False
    inv = 1 / det
    s = subtract(origin, a)
    u = inv * dot(s, h)
    if u < -1e-8 or u > 1 + 1e-8:
        return False
    q = cross(s, e1)
    v = inv * dot(direction, q)
    t = inv * dot(e2, q)
    return v >= -1e-8 and u + v <= 1 + 1e-8 and 1e-6 < t < 1 - 1e-6


def triangulate_face(points):
    """Ear-clip a planar simple polygon; do not fan-fill concave gaps."""
    if len(points) < 3 or any(len(p) != 3 or not all(math.isfinite(x) for x in p) for p in points):
        raise ReviewError("Invalid face vertices")
    normal = [0.0, 0.0, 0.0]
    for a, b in zip(points, points[1:] + points[:1], strict=False):
        for i in range(3):
            normal[i] += (a[(i + 1) % 3] - b[(i + 1) % 3]) * (a[(i + 2) % 3] + b[(i + 2) % 3])
    length = math.sqrt(dot(normal, normal))
    if length < 1e-9:
        return []
    if any(abs(dot(normal, subtract(p, points[0]))) / length > 1e-4 for p in points):
        raise ReviewError("Non-planar source face")
    axis = max(range(3), key=lambda i: abs(normal[i]))
    axes = [i for i in range(3) if i != axis]
    xy = [[p[i] for i in axes] for p in points]

    def turn(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    area = sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(xy, xy[1:] + xy[:1], strict=False))
    orientation = 1 if area > 0 else -1
    indices, triangles = list(range(len(points))), []
    while len(indices) > 3:
        found = False
        for n, current in enumerate(indices):
            before, after = indices[n - 1], indices[(n + 1) % len(indices)]
            a, b, c = xy[before], xy[current], xy[after]
            if orientation * turn(a, b, c) <= 1e-10:
                continue
            if any(
                all(orientation * turn(x, y, xy[k]) >= -1e-10 for x, y in [(a, b), (b, c), (c, a)])
                for k in indices
                if k not in (before, current, after)
            ):
                continue
            triangles.append([points[before], points[current], points[after]])
            indices.pop(n)
            found = True
            break
        if not found:
            # Collinear boundary vertices may be removed without filling any area.
            for n, k in enumerate(indices):
                if abs(turn(xy[indices[n - 1]], xy[k], xy[indices[(n + 1) % len(indices)]])) < 1e-9:
                    indices.pop(n)
                    found = True
                    break
        if not found:
            raise ReviewError("Cannot triangulate source face without guessing")
    if len(indices) == 3:
        triangles.append([points[i] for i in indices])
    return triangles


def membership(static, record):
    if static["source_sha256"] != record["source_sha256"]:
        raise ReviewError("Membership source mismatch")
    refs = {o["object_ref"] for o in static["objects"]}
    rows = {o["object_ref"]: o for o in record["objects"]}
    if refs != rows.keys() or len(rows) != len(record["objects"]):
        raise ReviewError("Exact static membership scope required")
    active, support, excluded = [], [], []
    for obj in static["objects"]:
        row = rows[obj["object_ref"]]
        if obj["object_ref"].startswith("WALK_"):
            support.append(obj)
        elif not row["hide_render"] and row["render_collection_enabled"]:
            active.append(obj)
        else:
            excluded.append(obj["object_ref"])
    return {
        "render_enabled_objects": active,
        "support_annotation_meshes": support,
        "excluded_source_only_objects": sorted(excluded),
        "authority": "PROPOSED_STATIC_REVIEW_ONLY",
        "approval_granted": False,
    }


def aperture(shell, axis, plane, other, search, portal_id):
    """Derive the clear rectangular low opening from the actual wall face cells.

    The search interval is an explicit static review locator, not a trajectory.
    Surface face IDs and vertices remain available for independent inspection.
    """
    faces, refs = [], []
    vertices = shell["vertices_world_m"]
    for index, face in enumerate(shell["triangles_or_polygons"]):
        points = [vertices[i] for i in face]
        if (
            all(abs(p[axis] - plane) < 1e-4 for p in points)
            and max(p[other] for p in points) > search[0] + 1e-5
            and min(p[other] for p in points) < search[1] - 1e-5
        ):
            faces.append(points)
            refs.append(index)
    if not faces:
        raise ReviewError("No bound wall face cells for portal")
    us = sorted(
        {round(p[other], 5) for f in faces for p in f if search[0] <= p[other] <= search[1]}
    )
    zs = sorted({round(p[2], 5) for f in faces for p in f})

    def covered(u, z):
        for f in faces:
            poly = [[p[other], p[2]] for p in f]
            if inside_polygon([u, z], poly):
                return True
        return False

    gaps = []
    for a, b in zip(us, us[1:], strict=False):
        height = 0.0
        for low, high in zip(zs, zs[1:], strict=False):
            if low < -1e-5:
                continue
            if covered((a + b) / 2, (low + high) / 2):
                break
            height = high
        if height > 0.1:
            if gaps and abs(gaps[-1][1] - a) < 1e-5 and abs(gaps[-1][2] - height) < 1e-5:
                gaps[-1] = [gaps[-1][0], b, height]
            else:
                gaps.append([a, b, height])
    if len(gaps) != 1:
        raise ReviewError("Portal locator must resolve exactly one bounded opening")
    lo, hi, height = gaps[0]
    if lo <= search[0] or hi >= search[1]:
        raise ReviewError("Opening is not bounded by the inspected wall")
    corners = []
    for u, z in [(lo, 0), (hi, 0), (hi, height), (lo, height)]:
        point = [0.0, 0.0, float(z)]
        point[axis], point[other] = float(plane), float(u)
        corners.append(point)
    return {
        "portal_id": portal_id,
        "status": "PROPOSED",
        "object_ref": shell["object_ref"],
        "mesh_sha256": digest(shell),
        "plane_axis": axis,
        "plane_m": plane,
        "opening_polygon_world_m": corners,
        "width_m": round(hi - lo, 5),
        "height_m": height,
        "source_face_indices": refs,
        "measurement": "WALL_SURFACE_CELL_COMPLEMENT_V1",
        "approval_granted": False,
        ("limits"): (
            "Nominal geometric opening; not physical clearance, navigation or visibility approval."
        ),
    }


def inside_polygon(point, poly):
    x, y = point
    inside = False
    for a, b in zip(poly, poly[1:] + poly[:1], strict=False):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if (
            abs(dx * (y - a[1]) - dy * (x - a[0])) < 1e-8
            and min(a[0], b[0]) - 1e-8 <= x <= max(a[0], b[0]) + 1e-8
            and min(a[1], b[1]) - 1e-8 <= y <= max(a[1], b[1]) + 1e-8
        ):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def on_support(point, mesh):
    vs = mesh["vertices_world_m"]
    return any(
        all(abs(vs[i][2] - point[2]) < 1e-4 for i in face)
        and inside_polygon(point[:2], [vs[i][:2] for i in face])
        for face in mesh["triangles_or_polygons"]
    )


def square_supported(center, half_width, mesh):
    """Exact union coverage for the source's axis-aligned rectangular floor cells."""
    vertices = mesh["vertices_world_m"]
    rectangles = []
    for face in mesh["triangles_or_polygons"]:
        points = [vertices[i] for i in face]
        if not all(abs(p[2] - center[2]) < 1e-5 for p in points):
            continue
        xs, ys = sorted({p[0] for p in points}), sorted({p[1] for p in points})
        if len(points) != 4 or len(xs) != 2 or len(ys) != 2:
            raise ReviewError("Unsupported floor cell: exact rectangular union required")
        rectangles.append((xs[0], xs[1], ys[0], ys[1]))
    left, right = center[0] - half_width, center[0] + half_width
    bottom, top = center[1] - half_width, center[1] + half_width
    xs = sorted({left, right} | {x for r in rectangles for x in r[:2] if left < x < right})
    ys = sorted({bottom, top} | {y for r in rectangles for y in r[2:] if bottom < y < top})
    return all(
        any(
            r[0] - 1e-8 <= (a + b) / 2 <= r[1] + 1e-8 and r[2] - 1e-8 <= (c + d) / 2 <= r[3] + 1e-8
            for r in rectangles
        )
        for a, b in zip(xs, xs[1:], strict=False)
        for c, d in zip(ys, ys[1:], strict=False)
    )


def project(cal, point):
    m = cal["camera_to_world"]
    delta = [point[i] - m[i][3] for i in range(3)]
    local = [sum(m[i][j] * delta[i] for i in range(3)) for j in range(3)]
    if local[2] >= -1e-6:
        return None
    return [
        cal["cx"] + cal["fx"] * local[0] / -local[2],
        cal["cy"] - cal["fy"] * local[1] / -local[2],
    ]


def static_witness(cal, point, triangles):
    uv = project(cal, point)
    if uv is None or not (2 <= uv[0] < cal["width"] - 2 and 2 <= uv[1] < cal["height"] - 2):
        return False
    origin = [cal["camera_to_world"][i][3] for i in range(3)]
    return not any(segment_triangle(origin, point, triangle) for triangle in triangles)


def find_patch(cal, support, anchor, triangles):
    """Find a supported square with nine in-frame unoccluded static witnesses.

    Deterministic 0.25m locator grid and 0.40m half-width are review sampling
    choices, not runtime thresholds. Eight perimeter witnesses plus center.
    No interpolation from unobserved event frames or person route is used.
    """
    vs = support["vertices_world_m"]
    z = max(v[2] for v in vs)
    xs = range(math.ceil(min(v[0] for v in vs) * 4), math.floor(max(v[0] for v in vs) * 4) + 1)
    ys = range(math.ceil(min(v[1] for v in vs) * 4), math.floor(max(v[1] for v in vs) * 4) + 1)
    candidates = sorted(
        ([x / 4, y / 4, z] for x in xs for y in ys),
        key=lambda p: (sum((p[i] - anchor[i]) ** 2 for i in range(2)), p[0], p[1]),
    )
    for center in candidates:
        points = [
            [center[0] + x * 0.4, center[1] + y * 0.4, z]
            for x, y in [
                (-1, -1),
                (1, -1),
                (1, 1),
                (-1, 1),
                (0, 0),
                (0, -1),
                (1, 0),
                (0, 1),
                (-1, 0),
            ]
        ]
        if not square_supported(center, 0.4, support):
            continue
        if not all(static_witness(cal, p, triangles) for p in points):
            continue
        polygon = [project(cal, p) for p in points[:4]]
        area = (
            abs(
                sum(
                    a[0] * b[1] - b[0] * a[1]
                    for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=False)
                )
            )
            / 2
        )
        if area < 4:
            continue
        return {
            "polygon_world_m": points[:4],
            "roi_polygon_px": [[round(v, 4) for v in p] for p in polygon],
            "support_object_ref": support["object_ref"],
            "support_sha256": digest(support),
            "area_px2": round(area, 4),
            "witness_world_m": points,
            "static_witness_count": len(points),
            "locator_anchor_world_m": anchor,
            "support_coverage": "EXACT_SOURCE_RECTANGULAR_CELL_UNION",
            "center_to_locator_m": round(math.dist(center, anchor), 4),
            ("limits"): (
                "9 static foot-plane ray witnes"
                "ses only; not whole-person vis"
                "ibility or first appearance bo"
                "undary."
            ),
            "status": "PROPOSED",
            "method": "STATIC_PATCH_GRID_025_HALF_WIDTH_040_V1",
        }
    raise ReviewError("No safe static patch for " + cal["camera_id"])


def triangles_for(active_objects):
    triangles = []
    for obj in active_objects:
        if obj["object_ref"] in {"FLOOR_GROUND", "R004_EXTERIOR_FLOOR"}:
            continue
        vs = obj["vertices_world_m"]
        for face in obj["triangles_or_polygons"]:
            triangles.extend(triangulate_face([vs[i] for i in face]))
    return triangles


def import_helper(name):
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENTRY_LOCATORS = {
    "CAM_ENTRY": ("OUT_W", [-3.2, 0, -0.06]),
    "CAM_EXT_CAR": ("OUT_W", [-3.2, 0, -0.06]),
    "CAM_EXT_CLEAR": ("OUT_W", [-3.2, 0, -0.06]),
    "CAM_W1": ("CORR_W", [0, 1.2, 0]),
    "CAM_W2": ("CORR_W", [8, 0.6, 0]),
    "CAM_R101_IN": ("R101", [8, -0.4, 0]),
    "CAM_BRANCH": ("CORR_N", [16.2, 2.4, 0]),
    "CAM_WIDE": ("CORR_N", [16.2, 2.4, 0]),
}
EDGE_LOCATORS = {
    "E_OUT_VEST": [-3.2, 0, -0.06],
    "E_VEST_CORR": [0, 1.2, 0],
    "E_W_CORNER": [15, 1.2, 0],
    "E_CORNER_N": [16.2, 2.4, 0],
    "E_PORTAL_R101": [8, 0, 0],
    "E_PORTAL_R102": [17.4, 9, 0],
}


def region_route(edges, origin, target):
    queue = deque([(origin, [origin], [])])
    seen = {origin}
    while queue:
        current, path, eids = queue.popleft()
        if current == target:
            return path, eids
        for edge in sorted(edges, key=lambda e: e["edge_id"]):
            if edge["edge_id"] == "E_PORTAL_R102" or current not in edge["regions"]:
                continue
            other = next(x for x in edge["regions"] if x != current)
            if other not in seen:
                seen.add(other)
                queue.append((other, path + [other], eids + [edge["edge_id"]]))
    raise ReviewError("No scoped static route")


def seal_graph(graph, prefix):
    body = {k: v for k, v in graph.items() if k not in {"content_sha256", "graph_id", "stats"}}
    graph["content_sha256"] = digest(body)
    graph["graph_id"] = prefix + ":r004:static:" + graph["content_sha256"][:16]
    return graph


def make_graphs(old_region, old_camera, cals, meshes, triangles, config):
    region = deepcopy(old_region)
    camera = deepcopy(old_camera)
    patches, entry_by_camera, exits_by_camera = {}, {}, {}
    for cam in camera["cameras"]:
        cid = cam["camera_id"]
        rid, anchor = ENTRY_LOCATORS[cid]
        patch = find_patch(cals[cid], meshes[rid], anchor, triangles)
        entry_id = cid + ":ENTRY_V2"
        patches[entry_id] = {"camera_id": cid, "region_id": rid, "role": "ENTRY", **patch}
        cam["entry_zones"] = [
            {"entry_zone_id": entry_id, "roi_polygon_px": patch["roi_polygon_px"]}
        ]
        entry_by_camera[cid] = entry_id
        cam["exit_zones"] = []
        exits_by_camera[cid] = {}
        for edge in region["edges"]:
            eid = edge["edge_id"]
            if rid not in edge["regions"] or eid == "E_PORTAL_R102":
                continue
            anchor = list(EDGE_LOCATORS[eid])
            if rid != "OUT_W":
                anchor[2] = 0
            patch = find_patch(cals[cid], meshes[rid], anchor, triangles)
            zid = cid + ":EXIT_V2:" + eid
            patches[zid] = {
                "camera_id": cid,
                "region_id": rid,
                "role": "EXIT",
                "edge_id": eid,
                **patch,
            }
            cam["exit_zones"].append(
                {
                    "exit_zone_id": zid,
                    "roi_polygon_px": patch["roi_polygon_px"],
                    "leads_to_edge_ids": [eid],
                    "mapping_basis": "STATIC_CALIBRATION_PROJECTION",
                    "static_frame_ref": "static-image:r004:" + cid,
                    "static_frame_sha256": config["static_frames"][cid]["sha256"],
                }
            )
            exits_by_camera[cid][eid] = zid
        if not cam["exit_zones"]:
            raise ReviewError("Every camera must have a supported exit patch")
        cam["covered_regions"] = [
            {
                "region_id": rid,
                "basis": "MANUAL_ON_STATIC_FRAME",
                "visibility_ref": "static-review:v2:" + cid,
                "visible_area_m2": None,
            }
        ]
    pairs = {(t["from_camera_id"], t["to_camera_id"]) for t in old_camera["transitions"]}
    pairs |= {(b, a) for a, b in list(pairs)}
    pairs |= {("CAM_W1", "CAM_W2"), ("CAM_W2", "CAM_W1")}
    camera["transitions"] = []
    for source, target in sorted(pairs):
        path, eids = region_route(
            region["edges"], ENTRY_LOCATORS[source][0], ENTRY_LOCATORS[target][0]
        )
        # Same-region overlap has not been independently measured/approved.
        # Keep those six pairs in the review scope note, outside the runtime
        # graph, rather than emitting a vacuous APPROVED_WALKABLE label.
        if not eids:
            continue
        via = (
            [exits_by_camera[source][eids[0]]]
            if eids
            else [next(iter(exits_by_camera[source].values()))]
        )
        camera["transitions"].append(
            {
                "transition_id": "T_" + source + "__" + target,
                "from_camera_id": source,
                "to_camera_id": target,
                "via_exit_zone_ids": via,
                "to_entry_zone_ids": [entry_by_camera[target]],
                "region_path": path,
                "edge_path": eids,
                "region_hops": len(eids),
                "relation": "UNKNOWN",
                "ranking_area_m2": None,
                "ranking_area_refs": [],
                "nominal_path_length_m": None,
                "path_traversability": "TOPOLOGICAL_ONLY",
                "path_has_unknown_state": bool(eids),
                "basis_refs": ["static-review:v2:route-and-zones"],
            }
        )
    # No graph or edge approval is changed.
    seal_graph(region, "rgraph")
    camera["region_graph_sha256"] = region["content_sha256"]
    seal_graph(camera, "cgraph")
    return region, camera, patches


def zone_svg(cid, png, patches):
    uri = "data:image/png;base64," + base64.b64encode(png).decode()
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 720">',
        '<rect width="960" height="720" fill="white"/>',
        f'<image href="{uri}" width="960" height="540"/>',
    ]
    selected = [p for p in patches.values() if p["camera_id"] == cid]
    selected.sort(key=lambda p: (p["role"] != "ENTRY", p.get("edge_id", "")))
    exit_number = 0
    for n, patch in enumerate(selected):
        entry = patch["role"] == "ENTRY"
        if not entry:
            exit_number += 1
        tag = "E1" if entry else "X" + str(exit_number)
        color = "#007cda" if entry else "#e87900"
        coords = " ".join(f"{p[0]:.3f},{p[1]:.3f}" for p in patch["roi_polygon_px"])
        style = 'stroke-width="7" stroke-dasharray="8,4"' if entry else 'stroke-width="3"'
        parts.append(
            f'<polygon points="{coords}" fill="{color}" fill-opacity=".08" '
            f'stroke="{color}" {style}/>'
        )
        u, v = patch["roi_polygon_px"][0]
        x = min(925, max(8, u + (-28 if entry else 14)))
        y = min(525, max(18, v - 12))
        parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="16" '
            f'stroke="white" stroke-width="3" paint-order="stroke" fill="{color}">{tag}</text>'
        )
        role = "ENTRY (blue dashed)" if entry else "EXIT " + patch["edge_id"]
        legend = f"{tag}: {role}; locator distance {patch['center_to_locator_m']:.2f} m"
        parts.append(
            f'<text x="15" y="{588 + 23 * n}" font-family="sans-serif" '
            f'font-size="14" fill="{color}">{escape(legend)}</text>'
        )
    parts += [
        f'<text x="15" y="562" font-family="sans-serif" font-size="17">'
        f"{escape(cid)} · PROPOSED · blue dashed ENTRY / orange EXIT</text>",
        '<text x="15" y="681" font-family="sans-serif" font-size="12">'
        "ENTRY and EXIT may share the same patch; roles are reviewed separately.</text>",
        '<text x="15" y="704" font-family="sans-serif" font-size="12">'
        "9 static foot-plane rays per patch; not first appearance, "
        "whole-person visibility, or G4 approval.</text>",
        "</svg>",
    ]
    return "\n".join(parts).encode()


def portal_svg(portal, shell):
    axis = 1 if portal["plane_axis"] == 0 else 0
    points = portal["opening_polygon_world_m"]
    lo, hi = points[0][axis] - 1.5, points[1][axis] + 1.5
    scale = min(750 / (hi - lo), 380 / 3.2)

    def xy(u, z):
        return 50 + (u - lo) * scale, 450 - z * scale

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 560">',
        '<rect width="1000" height="560" fill="#f8fafc"/>',
        '<g font-family="sans-serif" fill="#172033">',
        f'<text x="25" y="30" font-size="22">{escape(portal["portal_id"])} · PROPOSED</text>',
    ]
    vs = shell["vertices_world_m"]
    for fi in portal["source_face_indices"]:
        face = [vs[i] for i in shell["triangles_or_polygons"][fi]]
        coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in [xy(p[axis], p[2]) for p in face])
        parts.append(
            f'<polygon points="{coords}" fill="#cbd5e1" stroke="#64748b" stroke-width=".5"/>'
        )
    coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in [xy(p[axis], p[2]) for p in points])
    parts += [
        f'<polygon points="{coords}" fill="#bbf7d0" fill-opacity=".65" '
        'stroke="#15803d" stroke-width="3"/>',
        f'<text x="680" y="110" font-size="20">width = {portal["width_m"]:.2f} m</text>',
        f'<text x="680" y="145" font-size="20">height = {portal["height_m"]:.2f} m</text>',
        (
            '<text x="25" y="485" font-size'
            '="16">Source: WALL_JOINED_SHEL'
            "L exact face cells; green = bo"
            "unded low opening complement.<"
            "/text>"
        ),
        (
            '<text x="25" y="515" font-size'
            '="15">Nominal dimensions only.'
            " No physical clearance, walkin"
            "g, identity, or G4 approval.</"
            "text>"
        ),
        "</g></svg>",
    ]
    return "\n".join(parts).encode()


def supplement_map(svg, meshes, portals, patches):
    vertices = [p for mesh in meshes.values() for p in mesh["vertices_world_m"]]
    left, right = min(p[0] for p in vertices), max(p[0] for p in vertices)
    bottom, top = min(p[1] for p in vertices), max(p[1] for p in vertices)
    scale = min(850 / max(right - left, 1), 570 / max(top - bottom, 1))

    def xy(point):
        return 35 + (point[0] - left) * scale, 90 + (top - point[1]) * scale

    extra = []
    for n, portal in enumerate(portals):
        coords = " ".join(
            f"{x:.2f},{y:.2f}" for x, y in map(xy, portal["opening_polygon_world_m"][:2])
        )
        extra.append(f'<polyline points="{coords}" stroke="#16a34a" stroke-width="5" fill="none"/>')
        line = f"{portal['portal_id']}: {portal['width_m']:.2f} x {portal['height_m']:.2f} m"
        extra.append(
            f'<text x="895" y="{420 + n * 25}" font-size="12" fill="#166534">{escape(line)}</text>'
        )
    for patch in patches.values():
        if patch["role"] != "ENTRY":
            continue
        coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in map(xy, patch["polygon_world_m"]))
        extra.append(
            f'<polygon points="{coords}" stroke="#007cda" fill="#007cda" '
            'fill-opacity=".35" stroke-width="1.5"/>'
        )
    extra.append('<text x="895" y="525" font-size="12">Green = portal; blue = entry patch</text>')
    svg = svg.replace(
        ("GT, portal width, overlap ratio"), ("GT, approved traversal, overlap ratio")
    )
    return svg.replace("</g></svg>", "\n".join(extra) + "</g></svg>").encode()


def build_review(
    config_path,
    config_sha256,
    membership_path,
    membership_sha256,
    prior_pack,
    prior_manifest_sha256,
    output,
):
    engine, checker = import_helper("r004_prereview_pack"), import_helper("q1q5_graph_check")
    config = pinned(config_path, config_sha256)
    checker.check_graphs(config_path, config_sha256)
    old_manifest, _ = engine.verify_pack(prior_pack, prior_manifest_sha256)
    previous = json.loads((Path(prior_pack) / "DATA.json").read_bytes())
    record = pinned(membership_path, membership_sha256)
    static = pinned(
        **{
            "path": config["files"]["static_geometry"]["path"],
            "sha256": config["files"]["static_geometry"]["sha256"],
        }
    )
    scope = membership(static, record)
    objects = {o["object_ref"]: o for o in static["objects"]}
    shell = objects["WALL_JOINED_SHELL"]
    portals = [
        aperture(shell, 0, -3.2, 1, [-2, 2.4], "R004_WEST_ENTRY"),
        aperture(shell, 1, 0, 0, [5, 11], "PORTAL_R101"),
        aperture(shell, 0, 17.4, 1, [7, 11], "PORTAL_R102"),
    ]
    documents = {
        name: pinned(ref[("path")], ref[("sha256")]) for name, ref in config[("files")].items()
    }
    cals = {c["camera_id"]: c for c in documents["camera_catalog"]["cameras"]}
    tris = triangles_for(scope["render_enabled_objects"])
    region, camera, patches = make_graphs(
        documents["region_graph"],
        documents["camera_graph"],
        cals,
        documents["region_meshes"]["meshes"],
        tris,
        config,
    )
    extra_inputs = [
        {"ref": "static-membership:r004:v2", "sha256": membership_sha256},
        {
            "ref": "portal-openings:r004:v2",
            "sha256": hashlib.sha256(canonical(portals) + b"\n").hexdigest(),
        },
        {
            "ref": "static-patches:r004:v2",
            "sha256": hashlib.sha256(canonical(patches) + b"\n").hexdigest(),
        },
    ]
    region["inputs"] += extra_inputs
    seal_graph(region, "rgraph")
    camera["inputs"] += extra_inputs
    camera["region_graph_sha256"] = region["content_sha256"]
    seal_graph(camera, "cgraph")
    # Reuse the exact production loader, not a review-only acceptance shortcut.
    # Its package dependencies are supplied by the normal source PYTHONPATH.
    from amidst.q1q5.graphs import load_graphs

    bundle = load_graphs(
        region,
        camera,
        region_sha256=region["content_sha256"],
        camera_sha256=camera["content_sha256"],
    )
    if bundle.approval_status != "DRAFT":
        raise ReviewError("Review must not grant approval")
    for cid, cal in cals.items():
        checker._calibration_check(cal)
        for patch in patches.values():
            if patch["camera_id"] == cid:
                checker.polygon_area(patch["roi_polygon_px"], cal["width"], cal["height"])
    payloads = {}
    for name in old_manifest["files"]:
        if name.startswith("images/static/") or name.startswith("images/hsv/"):
            payloads[name] = (Path(prior_pack) / name).read_bytes()
    for cid in sorted(cals):
        payloads[f"images/zones/{cid}.svg"] = zone_svg(
            cid, payloads[f"images/static/{cid}.png"], patches
        )
    for portal in portals:
        payloads[f"images/portals/{portal['portal_id']}.svg"] = portal_svg(portal, shell)
    payloads["images/region_map.svg"] = supplement_map(
        checker.render_static_map(config_path, config_sha256),
        documents["region_meshes"]["meshes"],
        portals,
        patches,
    )
    rows = []

    def item(identifier, category, object_id, images, statement, **details):
        rows.append(
            {
                "item_id": identifier,
                "category": category,
                "object_id": object_id,
                "image_refs": images,
                "statement": statement,
                **details,
            }
        )

    for cid in sorted(cals):
        refs = [f"images/static/{cid}.png", f"images/zones/{cid}.svg"]
        item(
            "CAM_V2_" + cid,
            "CAMERA_IDENTITY",
            cid,
            refs,
            f"{cid} 的原圖與藍色入口／橘色出口標示對應正確。",
        )
    for zid, patch in sorted(patches.items()):
        cid = patch["camera_id"]
        item(
            "ZONE_" + zid,
            "ENTRY_ROI" if patch["role"] == "ENTRY" else "EXIT_ROI",
            zid,
            [f"images/static/{cid}.png", f"images/zones/{cid}.svg"],
            "這個靜態可見地面接近區適合作為本版"
            + ("接回入口" if patch["role"] == "ENTRY" else "離開搜尋的出口支持區")
            + "提案。",
            context="不是門檻線或首次可見邊界。點位來自靜態支撐面與校正；不代表人物一定經過。",
            details=patch,
        )
    for portal in portals:
        item(
            "PORTAL_" + portal["portal_id"],
            "PORTAL_DIMENSIONS",
            portal["portal_id"],
            [f"images/portals/{portal['portal_id']}.svg", "images/region_map.svg"],
            (
                f"所列門洞名義寬 {portal['width_m']:.2f} m、"
                f"高 {portal['height_m']:.2f} m 與來源牆殼的開口相符。"
            ),
            details=portal,
            context="只確認幾何尺寸來源，不代替物理通行核准。R102仍排除於本版追蹤。",
        )
    item(
        "STATIC_MEMBERSHIP_V2",
        "STATIC_MEMBERSHIP",
        "r004",
        ["images/region_map.svg"],
        "22個隱藏聯集輸入不當作有效遮擋體；本版分開列出15個render-enabled物件及6個支撐標記mesh。",
        details={
            "render_enabled": [o["object_ref"] for o in scope["render_enabled_objects"]],
            ("support_annotations"): [
                o[("object_ref")] for o in scope[("support_annotation_meshes")]
            ],
            "excluded": scope["excluded_source_only_objects"],
        },
    )
    for edge in region["edges"]:
        refs = ["images/region_map.svg"]
        if edge["via"]["kind"] == "PORTAL":
            refs.append("images/portals/" + edge["via"]["ref"] + ".svg")
        item(
            "EDGE_V2_" + edge["edge_id"],
            "REGION_EDGE",
            edge["edge_id"],
            refs,
            "此區域連結及其來源引用適合列為待核准拓撲提案。",
            details=edge,
            context="T不改TOPOLOGICAL_ONLY，也不解除R102限制。",
        )
    for transition in camera["transitions"]:
        source, target = transition["from_camera_id"], transition["to_camera_id"]
        item(
            "PATH_V2_" + transition["transition_id"],
            "CAMERA_TRANSITION",
            transition["transition_id"],
            [f"images/zones/{source}.svg", f"images/zones/{target}.svg", ("images/region_map.svg")],
            f"{source} → {target} 的方向、區域路徑、來源出口與目標入口引用相符。",
            details=transition,
            context="候選提案，不代表目標下一站；本版路徑均待指定用途核定，不授予G4。",
        )
    item(
        "BASELINE_SCOPE_V2",
        "BASELINE_SCOPE",
        "RULE_ONLY",
        [
            "images/zones/CAM_W2.svg",
            "images/zones/CAM_R101_IN.svg",
            "images/portals/PORTAL_R101.svg",
        ],
        (
            "第一版持續追查先以CAM_W2與CAM_R101_IN、一次"
            "一個目標與固定run／時間範圍驗證；R102與其他未核定用途"
            "保持排除。"
        ),
        context=(
            "範圍提案待核定；只是一版可驗證的空間候選範圍，未保證RT辨識"
            "或接回成功。原A4/B4產製規格不改。"
        ),
    )
    item(
        "SAME_REGION_SCOPE_V2",
        "BASELINE_SCOPE",
        "SAME_REGION_PAIRS",
        ["images/region_map.svg"],
        "本版追蹤排除6個尚未核定完整重疊關係的同區方向；一次查找仍可列出RGB模型找到的所有相符鏡頭。",
        details={
            "excluded_pairs": [
                ["CAM_ENTRY", "CAM_EXT_CAR"],
                ["CAM_EXT_CAR", "CAM_ENTRY"],
                ["CAM_ENTRY", "CAM_EXT_CLEAR"],
                ["CAM_EXT_CLEAR", "CAM_ENTRY"],
                ["CAM_W1", "CAM_W2"],
                ["CAM_W2", "CAM_W1"],
            ]
        },
        context="這是保守範圍限制，不是證明它們不能接回；本版不藉空邊路徑標籤取得通行權限。",
    )
    # Existing HSV system claims are unchanged, never filled human answers.
    rows += deepcopy(
        [x for x in previous[("items")] if x[("category")] in {("HSV_RED"), ("HSV_BLUE")}]
    )
    report = {
        "status": "ENGINEERING_EVIDENCE_READY_FOR_REVIEW",
        "gt_read": False,
        "counts": {
            "cameras": len(cals),
            "entry_rois": len(cals),
            "exit_rois": sum(len(c["exit_zones"]) for c in camera["cameras"]),
            "portal_bindings": len(portals),
            "transitions": len(camera["transitions"]),
            "excluded_same_region_pairs": 6,
            "excluded_templates": 22,
            "render_enabled_objects": len(scope["render_enabled_objects"]),
            "support_annotation_meshes": 6,
            "occluder_triangles": len(tris),
            "static_witnesses": len(patches) * 9,
            "legal_auto_switch_paths": 0,
        },
        "unresolved": [
            {
                "id": "G4_AND_NEW_HSV_G6_PENDING",
                "severity": "APPROVAL_PENDING",
                "summary": "工程材料備齊供審，不自動核准。",
            },
            {
                "id": "BASELINE_INTEGRATION_AND_145_PENDING",
                "severity": "SOFTWARE_BLOCKER",
                ("summary"): (
                    "產品Draft整合與獨立契約測試對齊仍須同步完成；本包不聲稱baseline已可跑。"
                ),
            },
            {
                "id": "RGB_INDEX_AND_HUMAN_METRICS_PENDING",
                "severity": "PRODUCTION_PENDING",
                "summary": "凍結與核定後才產正式RGB／索引；實際接回、正確率與顯示fps未知。",
            },
        ],
        "limits": [
            ("Static point-ray witnesses are not whole-person visibility or exhaustive coverage."),
            "No empirical reacquisition timeout or complete overlap ratio is inferred.",
            "All region edges remain TOPOLOGICAL_ONLY and graphs DRAFT.",
        ],
    }
    data = {
        "schema_version": "q-demo.r004-prereview-data.v1",
        "title": "r004 完整靜態審查 v2 · yyin",
        ("notice"): (
            "PROPOSED：入口／出口、門洞尺寸、有效幾何與方向已補件"
            "供審；本包不授權G4／G6，也不是正式辨識評估。"
        ),
        "columns": engine.COLUMNS,
        "items": rows,
        "report": report,
        "summary": report["counts"],
        "known_gaps": report["unresolved"],
        "scope": {
            "evaluation_eligible": False,
            "human_approval": False,
            "event_rgb_included": False,
            "gt_included": False,
            "formal_detector_tf": False,
        },
        "source_pins": {
            "base_config_sha256": config_sha256,
            "membership_sha256": membership_sha256,
            "prior_pack_manifest_sha256": prior_manifest_sha256,
            **{name: ref["sha256"] for name, ref in config["files"].items()},
        },
    }
    payloads.update(
        {
            "DATA.json": canonical(data) + b"\n",
            "data.js": b"window.R004_REVIEW_DATA=" + canonical(data) + b";\n",
            "provenance/region_graph.json": canonical(region) + b"\n",
            "provenance/camera_graph.json": canonical(camera) + b"\n",
            "provenance/portals.json": canonical(portals) + b"\n",
            "provenance/static_membership.json": Path(membership_path).read_bytes(),
            "provenance/static_scope.json": canonical(scope) + b"\n",
            "provenance/static_patches.json": canonical(patches) + b"\n",
            "provenance/engineering_report.json": canonical(report) + b"\n",
            "provenance/source_static_geometry.json": Path(
                config["files"]["static_geometry"]["path"]
            ).read_bytes(),
            **{
                f"provenance/{role}.json": Path(config["files"][role]["path"]).read_bytes()
                for role in ["camera_catalog", "region_meshes", "hsv_report", "hsv_config"]
            },
            "provenance/media_exports.json": canonical(
                {
                    k: v
                    for k, v in json.loads(
                        (Path(prior_pack) / "provenance/media_exports.json").read_bytes()
                    ).items()
                    if k in payloads
                }
            )
            + b"\n",
        }
    )
    input_files = {
        "static:r004:proposal": "provenance/source_static_geometry.json",
        "calibration:r004:catalog": "provenance/camera_catalog.json",
        "static-membership:r004:v2": "provenance/static_membership.json",
        "portal-openings:r004:v2": "provenance/portals.json",
        "static-patches:r004:v2": "provenance/static_patches.json",
    }
    external_pins = {
        ref: hashlib.sha256(payloads[name]).hexdigest() for ref, name in input_files.items()
    }
    media = json.loads(payloads["provenance/media_exports.json"])
    external_pins.update(
        {
            "static-image:r004:" + cid: media[f"images/static/{cid}.png"]["source_sha256"]
            for cid in cals
        }
    )
    for graph in [region, camera]:
        for ref in graph["inputs"]:
            if external_pins.get(ref["ref"]) != ref["sha256"]:
                raise ReviewError("Graph input differs from distributed source bytes")
    payloads["provenance/build_sources.json"] = (
        canonical(
            {
                "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "inspection_script_sha256": hashlib.sha256(
                    (
                        Path(__file__).parents[3] / "scripts/inspect_r004_static_membership.py"
                    ).read_bytes()
                ).hexdigest(),
                "inspection_allowlist_sha256": record["allowlist_sha256"],
                "static_source_sha256": static["source_sha256"],
                "source_saved": False,
                "rendered": False,
                "gt_read": False,
            }
        )
        + b"\n"
    )
    assets = Path(__file__).parents[3] / "scripts/r004_prereview_ui"
    html = (assets / "index.html").read_text()
    start = html.index('<section class="notice" aria-label="這份工作內容與要提交項目">')
    end = html.index('<header class="page-header">', start)
    intro = f"""<section class="notice" aria-label="工作內容與提交項目">
<h2>這份工作內容（yyin）</h2>
<p>審查新版 {len(rows)} 項：8台對應、8入口、
{report["counts"]["exit_rois"]}出口、3門洞尺寸、有效幾何、6區域邊、22相機轉移及6組同區方向排除、
baseline範圍與70項HSV預覽。按靜態圖與證據填T／F／不確定；F／不確定必填理由。
新入口／出口是地面接近區，不冒稱實際門檻或首次可見邊界。</p>
<h2>要提交項目</h2><ol><li>匯出CSV放RETURN/：審查表_yyin_YYYY-MM-DD.csv。保留全部{len(rows)}列；未完成保留_INCOMPLETE。</li><li>整包資料夾或ZIP，包含CSV、圖片與不可改材料。</li><li>交件說明：已審分類、未完成項及原因。OWNER_DECISIONS.csv交指定核定者，組員不代簽。</li></ol><p>本包已有實際入口與門洞證據。核准／產品整合／正式RGB索引尚未完成，詳見BASELINE_READINESS.md。關頁前先匯出，沒有自動儲存。</p></section>
"""
    payloads["START_HERE.html"] = (html[:start] + intro + html[end:]).encode()
    app = (
        (assets / "app.js")
        .read_text()
        .replace(
            "const CATEGORY_NAMES = {",
            (
                "const CATEGORY_NAMES = { ENTRY"
                '_ROI: "入口區域", PORTAL_DIMENSION'
                'S: "門洞尺寸", STATIC_MEMBERSHIP: '
                '"有效幾何", BASELINE_SCOPE: "basel'
                'ine範圍",'
            ),
        )
    )
    payloads["app.js"] = app.encode()
    payloads["style.css"] = (assets / "style.css").read_bytes()
    csv_rows = [
        {
            **{
                k: (("|").join(row[k]) if k == ("image_refs") else row[k])
                for k in engine.FIXED_COLUMNS
            },
            **{k: "" for k in engine.EDITABLE_COLUMNS},
        }
        for row in rows
    ]
    payloads["templates/審查表.csv"] = engine._csv(csv_rows)
    owner_columns = ["gate", "scope", "decision", "reason", "reviewer", "date"]
    payloads["templates/OWNER_DECISIONS.csv"] = engine._csv(
        [
            {
                "gate": "G4",
                ("scope"): (
                    "Review baseline W2/R101 and ex"
                    "plicitly allowed purposes; oth"
                    "er paths remain restricted"
                ),
            },
            {
                "gate": "G6_NEW_HSV",
                "scope": "Review preview parameters separately; no formal accuracy claim",
            },
        ],
        owner_columns,
    )
    for name in ["tools/r004_prereview_pack.py", "tools/verify_bundle.py"]:
        payloads[name] = (Path(prior_pack) / name).read_bytes()
    readiness = (
        "# baseline啟動條件與審查期間可做事項\n\n工程補件已"
        "包含：8台入口、每台出口、3門洞尺寸及來源面、22個隱藏聯集"
        "輸入的排除證據、R101入向與反向轉移、baseline範圍"
        "提案。\n這是完整靜態材料供審，不是執行核准或正式成效。\n幾何"
        "物件名稱只用於靜態遮擋與來源核對；目標存在、類別與框一律由R"
        "GB模型產生，不以場景物件名查找目標。\n\n仍需：yyin意見"
        "回收、Claude獨立檢查與使用者G4／新HSV核定；產品D"
        "raft與#145獨立契約測試對齊；之後凍結正式圖／參數，依"
        "已有授權產A4/B4 RGB／safe bundles，再建"
        "正式索引與跑兩模式。\n\n審查期間可同步做（不得改這包或先看事"
        "件回改圖）：\n1. 固定source composition"
        "，整合RULE_ONLY、Q1/Q4/Q2、HTTP與UI；"
        "用synthetic fixtures和既有錄製驗失敗路徑，"
        "不聲稱正式成效。\n2. Codex提供#145最小重現、修產"
        "品端違規；Claude對齊#127。Codex不改測試包或#"
        "135。\n3. 完成渲染／索引配置與磁碟、來源hash、ru"
        "n/camera/time scope預檢；未凍結前不產正式"
        "事件影像。\n4. 準備一次查找／持續追查共用測量入口：模型呼"
        "叫、冷暖耗時、推論與顯示fps分列、RSS、逐次接回／切鏡、"
        "無模型replay與失敗紀錄。\n\n審查核定後：凍結 → 正式"
        "RGB與safe bundle → 正式索引 → 一次查找／"
        "持續追查baseline → 輸出凍結 → 人工T/F與評分"
        "。\nWindows可執行包、Qwen／YOLO-World／"
        "進階ReID比較後排，不作本版前置。\n"
    )
    payloads["BASELINE_READINESS.md"] = readiness.encode()
    payloads["README.txt"] = (
        f"""這份工作內容（審查者：yyin）
逐項審查新版{len(rows)}項。新入口／出口、門洞尺寸及來源、有效幾何與R101入向都已實際補入，不再只有缺口文字。
入口／出口是可見地面接近區提案，不是精確門檻、人體可見性或目標必經路線。

要提交項目
1. 填好的RETURN/審查表_yyin_YYYY-MM-DD.csv（未完成保留_INCOMPLETE）；
全部{len(rows)}列不得刪除。姓名yyin，日期填實際日期。
2. 完整資料夾或ZIP（CSV已放RETURN/），保留固定材料。
3. 交件訊息：已審類別、未完成項及原因。OWNER_DECISIONS.csv供指定核定者使用，不代簽。

操作：完整解壓 → 開START_HERE.html → 填日期 → 按類別判讀與填T/F/不確定
→ 匯出CSV → 放RETURN/ → 整包交回。
T=支持敘述，F=反駁，不確定=證據不足；F/不確定必填理由，不要猜。非負責列可空白但保留，回收會列INCOMPLETE。
不會自動儲存；關頁前先匯出。續填用匯入CSV，舊版CSV不能直接匯入新版（固定材料已改）；舊包與回覆留存供對照，不自動沿用已變更項目的T。
只修改回覆欄decision/reason/reviewer/date，不改templates、DATA、圖檔、provenance或MANIFEST。
本包與全部圖仍PROPOSED，不自動核准G4／新HSV G6，不當正式辨識T/F或準確率。R102限制保持。
已跑程式／CSV與實際資料檢查；Windows及真瀏覽器離線實機仍待驗（不把工具測試當瀏覽器驗收）。
審查期間可並行工作與baseline啟動條件見BASELINE_READINESS.md。
"""
    ).encode()
    manifest = {
        "schema_version": "q-demo.r004-prereview-manifest.v1",
        "evaluation_eligible": False,
        "human_approval": False,
        "config_sha256": config_sha256,
        ("report_sha256"): hashlib.sha256(
            payloads[("provenance/engineering_report.json")]
        ).hexdigest(),
        "item_count": len(rows),
        "columns": engine.COLUMNS,
        "locked_columns": engine.FIXED_COLUMNS,
        "editable_files": ["RETURN/審查表.csv", "RETURN/OWNER_DECISIONS.csv"],
        "files": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(payloads.items())},
    }
    output = engine._no_symlinks(output)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ReviewError("New output directory required")
    if shutil.disk_usage(output.parent).free < 8 * 1024**3:
        raise ReviewError("DISK_BELOW_8_GIB")
    output.mkdir()
    for name, raw in {
        **payloads,
        "MANIFEST.json": canonical(manifest) + b"\n",
        "RETURN/審查表.csv": payloads["templates/審查表.csv"],
        "RETURN/OWNER_DECISIONS.csv": payloads["templates/OWNER_DECISIONS.csv"],
    }.items():
        if shutil.disk_usage(output).free < 8 * 1024**3:
            raise ReviewError("DISK_BELOW_8_GIB")
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    manifest_sha = hashlib.sha256((output / "MANIFEST.json").read_bytes()).hexdigest()
    engine.verify_pack(output, manifest_sha)
    return {
        "status": "REVIEW_REQUIRED",
        "manifest_sha256": manifest_sha,
        "items": len(rows),
        "counts": report["counts"],
        "output": str(output),
        "approval_granted": False,
    }

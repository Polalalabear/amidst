"""C6 step 1: source-mesh planning rays and candidate routes; never render/save.

Run via Blender --background --disable-autoexec blender/school_v3.blend --python
scripts/plan_office_demo_feasibility.py -- --output <new JSON path>.
This simulation-side artifact is not a C5 index or an inference input.
"""

from __future__ import annotations

import argparse
import collections
import functools
import hashlib
import json
import math
import sys
from pathlib import Path

CAMERA_IDS = (
    "CAM_1F_CLASS101",
    "CAM_1F_CORRIDOR_02",
    "CAM_1F_CORRIDOR_03",
    "CAM_1F_CORRIDOR_04",
    "CAM_1F_SIDE_ENTRANCE",
)
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def neighbors(node):
    x, y = node
    return ((x - 1, y), (x, y - 1), (x, y + 1), (x + 1, y))


def gap_span(visible):
    """Require a single interior blind interval, with visible endpoints."""
    if not visible or not visible[0] or not visible[-1]:
        return None
    blind = [i for i, value in enumerate(visible) if not value]
    if not blind or blind != list(range(blind[0], blind[-1] + 1)):
        return None
    return blind[0], blind[-1]


def turns(path):
    directions = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:], strict=False)]
    return sum(a != b for a, b in zip(directions, directions[1:], strict=False))


def find_routes(graph, seen, spacing, config, control_seen=None):
    """Bounded deterministic BFS through blind nodes; controls use visible edges.

    Search caps bound *planning*, not completeness: no candidate means UNKNOWN.
    A route has exactly one blind interval and at least 1m visible approach/exit.
    """
    limit = math.floor(config["max_route_length_m"] / spacing)
    boundary = sorted(n for n in graph if seen[n] and any(not seen[m] for m in graph[n]))

    def extend(start, forbidden, count=2):
        queue = collections.deque([[start]])
        visited = {start}
        while queue:
            path = queue.popleft()
            if len(path) == count + 1:
                return path
            for n in sorted(graph[path[-1]]):
                if n not in visited and n not in forbidden and seen[n]:
                    visited.add(n)
                    queue.append(path + [n])
        return None

    pool = []
    # Uniformly sample boundary entries when necessary, never claim exhaustive search.
    stride = max(1, math.ceil(len(boundary) / 256))
    for start in boundary[::stride]:
        queue = collections.deque([[start]])
        visited = {start}
        exits = 0
        while queue and exits < 16:
            path = queue.popleft()
            if len(path) > limit - 3:
                continue
            for node in sorted(graph[path[-1]]):
                if node in visited:
                    continue
                visited.add(node)
                candidate = path + [node]
                if seen[node]:
                    if len(candidate) < 4:
                        continue
                    first = extend(start, set(candidate[1:]))
                    last = extend(node, set(candidate[:-1]) | set(first or []))
                    if first is None or last is None:
                        continue
                    candidate = first[:0:-1] + candidate + last[1:]
                    span = gap_span([bool(seen[n]) for n in candidate])
                    if (
                        span
                        and (span[1] - span[0] + 1) * spacing >= config["min_blind_length_m"]
                        and (len(candidate) - 1) * spacing <= config["max_route_length_m"]
                    ):
                        pool.append(candidate)
                        exits += 1
                else:
                    queue.append(candidate)
    # Keep spatially distinct routes; preference for different endpoint cameras and turns.
    pool.sort(
        key=lambda p: (
            not bool(set(seen[p[0]]) & set(seen[p[-1]])),
            bool(turns(p)),
            len(p),
            tuple(p),
        ),
        reverse=True,
    )
    selected = []
    for path in pool:
        cells = set(path)
        if any(len(cells & set(old)) / min(len(cells), len(old)) > 0.65 for old in selected):
            continue
        selected.append(path)
        if len(selected) == config["max_gap_routes"]:
            break
    control_visible = seen if control_seen is None else control_seen
    control_pool = []
    count = math.ceil(config["min_control_length_m"] / spacing)
    for start in sorted(graph):
        for dx, dy in ((1, 0), (0, 1)):
            path = [(start[0] + dx * i, start[1] + dy * i) for i in range(count + 1)]
            if all(n in graph and control_visible[n] for n in path) and all(
                b in graph[a] for a, b in zip(path, path[1:], strict=False)
            ):
                common = set.intersection(*(set(control_visible[n]) for n in path))
                if common:
                    control_pool.append((path, common))
    controls = []
    used_cameras = set()
    while control_pool and len(controls) < config["max_controls"]:

        def priority(item):
            path, common = item
            distance = min((math.dist(path[0], old[0]) for old in controls), default=0)
            return bool(common - used_cameras), distance, tuple(path)

        path, common = max(control_pool, key=priority)
        controls.append(path)
        used_cameras.update(common)
        control_pool = [
            (p, cameras) for p, cameras in control_pool if len(set(p) & set(path)) <= count // 2
        ]
    return selected, controls, len(pool), len(boundary[::stride])


def main():
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "src"))
    from c6_prescreen import (
        adjacent_exits,
        classify_route,
        probe_visibility,
        search_paths,
        select_benchmarks,
    )
    from plan_blender_pilot import triangle_intersects_box
    from plan_blender_pilot_sites import (
        ANNOTATION_COLLECTIONS,
        ANNOTATION_PREFIXES,
        verify_immutable_source,
    )

    from amidst.simulation.blender_camera import extract_camera_dict

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/c6_feasibility_v1.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    config = json.loads(args.config.read_text())
    if tuple(r["camera_id"] for r in config["regions"]) != CAMERA_IDS:
        raise ValueError("C6_SCOPE_REQUIRES_EXACT_FIVE_CAMERAS")
    if config["render"] or config["source_saved"] or config["annotations_as_inputs"]:
        raise ValueError("PLANNING_ONLY_REQUIRED")
    for key in ("metres_per_blender_unit", "grid_spacing_m", "target_height_m", "body_radius_m"):
        if not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f"INVALID_CONFIG: {key}")
    source = Path(bpy.data.filepath).resolve()
    stat = source.stat()
    source_sha = digest(source)
    if source_sha != config["source_sha256"]:
        raise ValueError("SOURCE_HASH_MISMATCH")
    output = args.output.resolve()
    if output.suffix != ".json" or output.exists() or output == source:
        raise ValueError("OUTPUT_MUST_BE_NEW_JSON")
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    scale = config["metres_per_blender_unit"]
    spacing = config["grid_spacing_m"]
    step = spacing / scale
    floor = config["floor_search_z_m"] / scale
    tolerance = config["floor_search_tolerance_m"] / scale
    radius = config["body_radius_m"] / scale
    height = config["target_height_m"] / scale
    clearance = config["foot_clearance_m"] / scale
    cameras = [bpy.data.objects[name] for name in CAMERA_IDS]
    calibrations = [extract_camera_dict(scene, c) for c in cameras]
    regions = []
    nodes = set()
    for region, camera in zip(config["regions"], cameras, strict=True):
        matrix = camera.evaluated_get(depsgraph).matrix_world
        origin = matrix.translation
        direction = matrix.to_quaternion() @ Vector((0, 0, -1))
        if direction.z >= -1e-6:
            raise ValueError("CAMERA_AXIS_DOES_NOT_INTERSECT_1F")
        center = origin + direction * ((floor - origin.z) / direction.z)
        half = config["camera_neighborhood_half_width_m"] / scale
        lo = [math.ceil((center[a] - half) / step) for a in (0, 1)]
        hi = [math.floor((center[a] + half) / step) for a in (0, 1)]
        local = {(x, y) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1)}
        nodes.update(local)
        regions.append(
            {
                **region,
                "grid_bounds": [lo, hi],
                "grid_nodes": len(local),
                "axis_floor_intersection_m": [v * scale for v in center],
            }
        )
    if len(nodes) > 40000:
        raise ValueError("GRID_BUDGET_EXCEEDED")

    excluded = set()
    for name in ANNOTATION_COLLECTIONS:
        collection = bpy.data.collections.get(name)
        if collection:
            excluded.update(o.original.as_pointer() for o in collection.all_objects)
    for obj in scene.objects:
        if obj.name.startswith(ANNOTATION_PREFIXES) or obj.get("annotation_only"):
            excluded.add(obj.original.as_pointer())
    vertices, triangles, owners = [], [], []
    # XY buckets contain exact triangles that might intersect a body/swept edge.
    buckets = collections.defaultdict(list)
    physical_objects = set()
    grid_lo = [min(n[a] for n in nodes) for a in (0, 1)]
    grid_hi = [max(n[a] for n in nodes) for a in (0, 1)]
    for instance in depsgraph.object_instances:
        obj = instance.object
        if (
            obj.type != "MESH"
            or not instance.show_self
            or obj.hide_render
            or (obj.original.as_pointer() in excluded)
            or (instance.parent and instance.parent.original.as_pointer() in excluded)
        ):
            continue
        mesh = obj.to_mesh()
        mesh.calc_loop_triangles()
        world = [instance.matrix_world @ v.co for v in mesh.vertices]
        offset = len(vertices)
        vertices.extend(world)
        for tri in mesh.loop_triangles:
            points = tuple(world[i] for i in tri.vertices)
            index = len(triangles)
            triangles.append(tuple(offset + i for i in tri.vertices))
            owners.append(obj.original.name)
            if (
                max(p.z for p in points) < floor + clearance
                or min(p.z for p in points) > floor + tolerance + height
            ):
                continue
            lo = [
                max(grid_lo[a], math.ceil((min(p[a] for p in points) - radius) / step) - 1)
                for a in (0, 1)
            ]
            hi = [
                min(grid_hi[a], math.floor((max(p[a] for p in points) + radius) / step) + 1)
                for a in (0, 1)
            ]
            for x in range(lo[0], hi[0] + 1):
                for y in range(lo[1], hi[1] + 1):
                    if (x, y) in nodes:
                        buckets[x, y].append((index, points))
        physical_objects.add(obj.original.name)
        obj.to_mesh_clear()
    print(
        f"C6_BVH {len(physical_objects)} objects {len(triangles)} triangles; "
        f"{len(nodes)} grid nodes",
        flush=True,
    )
    bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=0)

    def support(x, y):
        hit, normal, index, _ = bvh.ray_cast(
            Vector((x, y, floor + tolerance)), Vector((0, 0, -1)), 2 * tolerance
        )
        if hit is None or abs(normal.z) < 0.95:
            return None
        return float(hit.z), owners[index]

    def body_clear(a, b, z, triangle_rows):
        minimum = (min(a[0], b[0]) - radius, min(a[1], b[1]) - radius, z + clearance)
        maximum = (max(a[0], b[0]) + radius, max(a[1], b[1]) + radius, z + clearance + height)
        return not any(
            triangle_intersects_box(points, minimum, maximum) for _, points in triangle_rows
        )

    supported = {}
    rejected = collections.Counter()
    for node in sorted(nodes):
        x, y = (v * step for v in node)
        hits = [
            support(x + dx, y + dy)
            for dx, dy in (
                (0, 0),
                (-radius, -radius),
                (-radius, radius),
                (radius, -radius),
                (radius, radius),
            )
        ]
        if any(h is None for h in hits):
            rejected["MISSING_SUPPORT"] += 1
            continue
        z = hits[0][0]
        if any(abs(h[0] - z) * scale > config["support_height_tolerance_m"] for h in hits):
            rejected["NONPLANAR_SUPPORT"] += 1
            continue
        if not body_clear((x, y), (x, y), z, buckets[node]):
            rejected["BODY_BOX_INTERSECTS_SOURCE"] += 1
            continue
        supported[node] = {"floor_z_bu": z, "support_objects": sorted({h[1] for h in hits})}
    print(f"C6_SUPPORT {len(supported)} body-clear supported nodes; {dict(rejected)}", flush=True)

    @functools.lru_cache(maxsize=50000)
    def visibility(x, y, z):
        states = []
        for camera, calibration in zip(cameras, calibrations, strict=True):
            origin = camera.evaluated_get(depsgraph).matrix_world.translation
            probes = []
            for offset in (clearance, clearance + height / 2, clearance + height):
                point = Vector((x, y, z + offset))
                ndc = world_to_camera_view(scene, camera, point)
                delta = point - origin
                incidence = abs(delta.z) / delta.length

                def cast(origin=origin, delta=delta):
                    hit, _, index, _ = bvh.ray_cast(
                        origin, delta.normalized(), max(0, delta.length - 0.001)
                    )
                    return owners[index] if hit is not None else None

                state = probe_visibility(
                    tuple(ndc), calibration["clip_start"], calibration["clip_end"], cast
                )
                probes.append({**state, "incidence": round(incidence, 6)})
            states.append(probes)
        return states

    seen = {}
    for node, row in supported.items():
        states = visibility(node[0] * step, node[1] * step, row["floor_z_bu"])
        row["rays"] = states
        seen[node] = [
            i for i, probes in enumerate(states) if any(p["status"] == "VISIBLE" for p in probes)
        ]
    graph = {n: [] for n in supported}
    edge_rejections = collections.Counter()
    for node in sorted(graph):
        a = (node[0] * step, node[1] * step)
        for other in neighbors(node):
            if other <= node or other not in graph:
                continue
            b = (other[0] * step, other[1] * step)
            z = supported[node]["floor_z_bu"]
            middle = support((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if middle is None or any(
                abs(v - z) * scale > config["support_height_tolerance_m"]
                for v in (middle[0], supported[other]["floor_z_bu"])
            ):
                edge_rejections["MISSING_OR_NONPLANAR_MIDPOINT_SUPPORT"] += 1
                continue
            if not body_clear(
                a, b, min(z, supported[other]["floor_z_bu"]), buckets[node] + buckets[other]
            ):
                edge_rejections["CONTINUOUS_SWEPT_BOX_INTERSECTION"] += 1
                continue
            graph[node].append(other)
            graph[other].append(node)
    print(f"C6_GRAPH {sum(map(len, graph.values())) // 2} edges", flush=True)
    control_seen = {
        n: [
            i
            for i, probes in enumerate(row["rays"])
            if all(p["status"] == "VISIBLE" for p in probes)
            and probes[0]["incidence"] >= config["min_bottom_incidence"]
        ]
        for n, row in supported.items()
    }
    gaps, controls, pool_count, boundary_count = find_routes(
        graph, seen, spacing, config, control_seen
    )
    prescreen_policy = config.get("prescreen")
    if prescreen_policy:
        eligible = {
            n: [
                i
                for i, probes in enumerate(row["rays"])
                if probes[0]["status"] == "VISIBLE"
                and probes[0]["incidence"] >= config["min_bottom_incidence"]
            ]
            for n, row in supported.items()
        }
        gaps, boundary_count, search_truncated = search_paths(
            graph, seen, eligible, spacing, prescreen_policy
        )
        pool_count = len(gaps)
        print(f"C6_PRESCREEN_POOL {pool_count}; eligible boundaries {boundary_count}", flush=True)

    def route_record(path, role, index):
        # Include mid-edge rays to catch blind/visible changes missed by graph nodes.
        samples = []
        for j in range(2 * len(path) - 1):
            a, b = path[j // 2], path[min(j // 2 + 1, len(path) - 1)]
            t = (j % 2) / 2
            x, y = ((a[k] * (1 - t) + b[k] * t) * step for k in (0, 1))
            z = supported[a]["floor_z_bu"] * (1 - t) + supported[b]["floor_z_bu"] * t
            states = visibility(x, y, z)
            active = [
                CAMERA_IDS[i]
                for i, probes in enumerate(states)
                if any(p["status"] == "VISIBLE" for p in probes)
            ]
            bottom = [
                CAMERA_IDS[i]
                for i, probes in enumerate(states)
                if probes[0]["status"] == "VISIBLE"
                and probes[0]["incidence"] >= config["min_bottom_incidence"]
            ]
            samples.append(
                {
                    "distance_m": j * spacing / 2,
                    "foot_position_m": [x * scale, y * scale, (z + clearance) * scale],
                    "visible_cameras": active,
                    "v2_bottom_eligible_cameras": bottom,
                    "rays": states,
                }
            )
        span = gap_span([bool(s["visible_cameras"]) for s in samples])
        if role == "VISIBLE_BLIND_VISIBLE":
            valid = span is not None and (
                samples[span[1]]["distance_m"] - samples[span[0]]["distance_m"]
                >= config["min_blind_length_m"]
            )
        else:
            valid = all(
                any(
                    all(p["status"] == "VISIBLE" for p in probes)
                    and probes[0]["incidence"] >= config["min_bottom_incidence"]
                    for probes in s["rays"]
                )
                for s in samples
            )
        if not valid:
            return None
        positions = [samples[0]["foot_position_m"]]
        for i in range(1, len(path) - 1):
            if turns(path[i - 1 : i + 2]):
                positions.append(samples[2 * i]["foot_position_m"])
        positions.append(samples[-1]["foot_position_m"])
        return {
            "candidate_id": f"c6-{role.lower()}-{index:02}",
            "role": role,
            "status": "PRELIMINARY_SOURCE_GEOMETRY_ONLY",
            "turn_count": turns(path),
            "length_m": (len(path) - 1) * spacing,
            "blind_distance_bounds_m": [samples[i]["distance_m"] for i in span] if span else None,
            "waypoints_m": positions,
            "samples": samples,
            "continuous_swept_box": "CLEAR_ON_EVALUATED_SOURCE_MESH",
            "continuous_floor_support": "UNKNOWN_SAMPLED_CENTRE_AND_CORNERS_ONLY",
            "rgb_detection": "UNKNOWN_NOT_RENDERED",
            "physical_navigation": "NOT_CERTIFIED",
        }

    candidates = []
    for role, paths in (("VISIBLE_BLIND_VISIBLE", gaps), ("FULLY_VISIBLE_CONTROL", controls)):
        for i, path in enumerate(paths, 1):
            record = route_record(path, role, i)
            if record:
                candidates.append(record)
    prescreen_result = None
    if prescreen_policy:
        raw = [r for r in candidates if r["role"] == "VISIBLE_BLIND_VISIBLE"]
        path_by_id = {f"c6-visible_blind_visible-{i:02}": p for i, p in enumerate(gaps, 1)}
        for record in raw:
            record["raw_gap_id"] = record["candidate_id"].replace("c6-", "c6-v2-", 1)
            record["prescreen"] = classify_route(record, prescreen_policy)
            record["turns_in_blind"] = record["prescreen"]["turns_in_blind"]
        selected = select_benchmarks(raw, prescreen_policy)
        legacy_path = ROOT / "docs/engineering/C6_FEASIBILITY_20261016.json"
        legacy = json.loads(legacy_path.read_text())
        legacy_records = [r for r in legacy["candidates"] if r["role"] == "VISIBLE_BLIND_VISIBLE"]
        legacy_audit = [
            {"gap_id": r["candidate_id"], **classify_route(r, prescreen_policy)}
            for r in legacy_records
        ]

        def material_risks(name):
            obj = bpy.data.objects.get(name)
            findings = []
            if obj is None:
                return [{"material": None, "reasons": ["SOURCE_OBJECT_UNRESOLVED"]}]
            for slot in obj.material_slots:
                material = slot.material
                if material is None:
                    continue
                reasons = []
                if material.diffuse_color[3] < 0.999:
                    reasons.append("DIFFUSE_ALPHA_BELOW_ONE")
                if getattr(material, "blend_method", "OPAQUE") != "OPAQUE":
                    reasons.append("NON_OPAQUE_BLEND_METHOD")
                trees = [material.node_tree] if material.use_nodes and material.node_tree else []
                visited = set()
                while trees:
                    tree = trees.pop()
                    if tree.as_pointer() in visited:
                        continue
                    visited.add(tree.as_pointer())
                    for node in tree.nodes:
                        if node.type in {
                            "BSDF_TRANSPARENT",
                            "BSDF_GLASS",
                            "BSDF_REFRACTION",
                            "HOLDOUT",
                        }:
                            reasons.append(node.type)
                        if node.type == "GROUP" and node.node_tree:
                            trees.append(node.node_tree)
                        for key in ("Alpha", "Transmission Weight", "Transmission"):
                            socket = node.inputs.get(key)
                            if socket is None:
                                continue
                            if socket.is_linked:
                                reasons.append(key.upper().replace(" ", "_") + "_LINKED_UNKNOWN")
                            else:
                                value = socket.default_value
                                if isinstance(value, (int, float)) and (
                                    (key == "Alpha" and value < 0.999)
                                    or (key != "Alpha" and value > 0.001)
                                ):
                                    reasons.append(key.upper().replace(" ", "_") + "_NON_OPAQUE")
                if reasons:
                    findings.append({"material": material.name, "reasons": sorted(set(reasons))})
            return findings

        for audit, old in zip(legacy_audit, legacy_records, strict=True):
            old_blockers = sorted(
                {
                    p["occluder"]
                    for s in old["samples"]
                    for probes in s["rays"]
                    for p in probes
                    if p.get("occluder")
                }
            )
            audit["transparent_occluders"] = [
                {"object": name, "materials": risks}
                for name in old_blockers
                if (risks := material_risks(name))
            ]
            audit["rgb_material_spotcheck_required"] = bool(audit["transparent_occluders"])
        edge_audits = []
        qualified_records = [r for r in raw if r["prescreen"]["qualified"]]
        diagnostic_records = (
            selected
            + [r for r in qualified_records if r not in selected][
                : prescreen_policy.get("max_full_diagnostic_records", 4096)
            ]
        )
        for record in diagnostic_records:
            path = path_by_id[record["candidate_id"]]
            blind_path = [n for n in path if not seen[n]]
            record["adjacent_visible_regions_and_potential_exits"] = adjacent_exits(
                graph, seen, blind_path, spacing
            )
            blockers = sorted(
                {
                    p["occluder"]
                    for s in record["samples"]
                    for probes in s["rays"]
                    for p in probes
                    if p["occluder"]
                }
            )
            record["transparent_occluders"] = [
                {"object": name, "materials": risks}
                for name in blockers
                if (risks := material_risks(name))
            ]
            record["rgb_material_spotcheck_required"] = bool(record["transparent_occluders"])
            record["c7_map_recheck"] = {
                "status": "PENDING_C7",
                "deadline": "2026-10-22",
                "map_sha256": None,
                "route_not_modified_from_gt": True,
            }
            record["legacy_gap_ids"] = []
            positions = {tuple(s["foot_position_m"][:2]) for s in record["samples"]}
            for old in legacy_records:
                old_positions = {tuple(s["foot_position_m"][:2]) for s in old["samples"]}
                if len(positions & old_positions) / min(len(positions), len(old_positions)) >= 0.5:
                    record["legacy_gap_ids"].append(old["candidate_id"])
            # Select narrow edges by actual nearest source mesh distance at torso height.
            nearby = []
            for a, b in zip(path, path[1:], strict=False):
                x, y = ((a[k] + b[k]) * step / 2 for k in (0, 1))
                z = supported[a]["floor_z_bu"]
                hit, _, index, distance = bvh.find_nearest(Vector((x, y, z + height / 2)))
                if hit is not None:
                    nearby.append((distance, a, b, owners[index]))
            for distance, a, b, nearest in sorted(nearby)[:2]:
                tests = []
                for part in range(9):
                    t = part / 8
                    x, y = ((a[k] * (1 - t) + b[k] * t) * step for k in (0, 1))
                    for angle in range(0, 360, 45):
                        hit = support(
                            x + radius * math.cos(math.radians(angle)),
                            y + radius * math.sin(math.radians(angle)),
                        )
                        tests.append(
                            hit is not None
                            and abs(hit[0] - supported[a]["floor_z_bu"]) * scale
                            <= config["support_height_tolerance_m"]
                        )
                edge_audits.append(
                    {
                        "benchmark_id": record.get("benchmark_id"),
                        "raw_gap_id": record["raw_gap_id"],
                        "edge_xy_m": [[v * spacing for v in n] for n in (a, b)],
                        "nearest_torso_height_source_object": nearest,
                        "nearest_distance_m": distance * scale,
                        "support_ring_samples": len(tests),
                        "all_support_samples_pass": all(tests),
                        "continuous_swept_box_clear": body_clear(
                            tuple(v * step for v in a),
                            tuple(v * step for v in b),
                            supported[a]["floor_z_bu"],
                            buckets[a] + buckets[b],
                        ),
                        "semantic_door_or_seating_classification": "UNKNOWN_UNTIL_C7",
                    }
                )
        cross_count = sum(r["prescreen"]["cross_camera"] for r in selected)
        prescreen_result = {
            "status": "READY_FOR_REVIEW"
            if len(selected) >= prescreen_policy["min_selected"]
            else "NOT_READY_INSUFFICIENT_QUALIFIED_ROUTES",
            "policy": prescreen_policy,
            "legacy_artifact_sha256": digest(legacy_path),
            "legacy_candidate_audit": legacy_audit,
            "raw_records_passing_gap_shape": len(raw),
            "qualified_before_diversity": sum(r["prescreen"]["qualified"] for r in raw),
            "qualified_cross_camera_before_diversity": sum(
                r["prescreen"]["qualified"] and r["prescreen"]["cross_camera"] for r in raw
            ),
            "selected_count": len(selected),
            "cross_camera_count": cross_count,
            "search_truncated": search_truncated,
            "rejection_reasons": dict(
                collections.Counter(reason for r in raw for reason in r["prescreen"]["reasons"])
            ),
            "rejected_records": [
                {"raw_gap_id": r["raw_gap_id"], "prescreen": r["prescreen"]}
                for r in raw
                if r not in selected
            ],
            "diagnostic_candidates_not_for_benchmark": [
                r for r in diagnostic_records if r not in selected
            ],
            "benchmark_id_mapping": [
                {
                    "benchmark_id": r["benchmark_id"],
                    "raw_gap_id": r["raw_gap_id"],
                    "legacy_gap_ids": r["legacy_gap_ids"],
                }
                for r in selected
            ],
            "narrow_edge_audits": edge_audits,
            "c5_acceptance": "ANY_BOTTOM_TORSO_OR_HEAD_VISIBLE_MEANS_NOT_BLIND",
            "benchmark_render_executed": False,
        }
        candidates = selected + [r for r in candidates if r["role"] == "FULLY_VISIBLE_CONTROL"]
        print("C6_PRESCREEN_SELECTED " + str(len(selected)), flush=True)
    for region in regions:
        lo, hi = region["grid_bounds"]
        local = [n for n in supported if all(lo[a] <= n[a] <= hi[a] for a in (0, 1))]
        coverage = {}
        for i, name in enumerate(CAMERA_IDS):
            coverage[name] = {
                "any_probe_visible": sum(i in seen[n] for n in local),
                "probe_status_counts": [
                    dict(collections.Counter(supported[n]["rays"][i][k]["status"] for n in local))
                    for k in range(3)
                ],
                "bottom_v2_incidence_eligible": sum(
                    supported[n]["rays"][i][0]["status"] == "VISIBLE"
                    and supported[n]["rays"][i][0]["incidence"] >= config["min_bottom_incidence"]
                    for n in local
                ),
            }
        region["supported_body_clear_nodes"] = len(local)
        region["camera_coverage"] = coverage
        region["all_five_blind_nodes"] = sum(not seen[n] for n in local)
        region["candidate_ids_touching_neighborhood"] = [
            c["candidate_id"]
            for c in candidates
            if any(
                all(lo[a] * spacing <= s["foot_position_m"][a] <= hi[a] * spacing for a in (0, 1))
                for s in c["samples"]
            )
        ]
    verify_immutable_source(source, source_sha, stat.st_size, stat.st_mtime_ns)
    result = {
        "schema_version": "office-demo.c6-feasibility.v1",
        "authority": config["authority"],
        "inference_input_eligible": False,
        "source_sha256": source_sha,
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "source_identity_unchanged": True,
        "config_sha256": digest(args.config),
        "planner_sha256": digest(__file__),
        "dependencies_sha256": {
            p: digest(ROOT / p)
            for p in (
                "scripts/c6_prescreen.py",
                "scripts/plan_blender_pilot.py",
                "scripts/plan_blender_pilot_sites.py",
                "src/amidst/simulation/blender_camera.py",
            )
        },
        "blender_version": bpy.app.version_string,
        "evaluated_scene_frame": scene.frame_current,
        "calibrations_scene_units": calibrations,
        "config": config,
        "camera_order": list(CAMERA_IDS),
        "probe_order": ["BOTTOM", "TORSO", "HEAD"],
        "regions": regions,
        "candidates": candidates,
        "search": {
            "grid_nodes": len(nodes),
            "supported_body_clear_nodes": len(supported),
            "physical_objects": len(physical_objects),
            "physical_triangles": len(triangles),
            "edges": sum(map(len, graph.values())) // 2,
            "node_rejections": dict(rejected),
            "edge_rejections": dict(edge_rejections),
            "gap_candidate_pool": pool_count,
            "boundary_entries_searched": boundary_count,
            "search_complete": False,
            "candidate_count_before_midpoint_check": len(gaps),
            "gap_candidate_count": sum(c["role"] == "VISIBLE_BLIND_VISIBLE" for c in candidates),
            "control_count": sum(c["role"] == "FULLY_VISIBLE_CONTROL" for c in candidates),
        },
        "geometry_policy": "EVALUATED_INSTANCES_EXCLUDING_ANNOTATIONS_AND_HIDE_RENDER",
        "grid_evidence": [
            {
                "grid_xy": list(n),
                "floor_z_m": row["floor_z_bu"] * scale,
                "support_objects": row["support_objects"],
                "visible_camera_indices_by_probe": [
                    [i for i, probes in enumerate(row["rays"]) if probes[k]["status"] == "VISIBLE"]
                    for k in range(3)
                ],
            }
            for n, row in sorted(supported.items())
        ],
        "not_verified": [
            "RGB_DETECTION",
            "FULL_SILHOUETTE_VISIBILITY",
            "CONTINUOUS_FLOOR_SUPPORT",
            "C7_MAP",
            "K1_READY",
            "FORMAL_BENCHMARK",
            "REAL_WORLD_NAVIGATION",
        ],
        "render_executed": False,
        "source_saved": False,
    }
    if prescreen_result is not None:
        result["schema_version"] = "office-demo.c6-feasibility.v2"
        result["prescreen"] = prescreen_result
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    print("C6_FEASIBILITY_OK " + json.dumps(result["search"]), flush=True)


if __name__ == "__main__":
    main()

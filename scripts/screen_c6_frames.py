"""Evaluate a frozen route pool at exact render frames and between-frame source samples.

Runs inside Blender. No rendering, source save, annotation geometry, or GT input.
"""

import argparse
import collections
import functools
import hashlib
import json
import math
import sys
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / "scripts"), str(root / "src")]
    from c6_frame_screen import check_k1_alignment, classify_frames, frame_times
    from c6_prescreen import (
        adjacent_exits,
        classify_route,
        probe_visibility,
        select_benchmarks,
        simplified_indices,
    )
    from plan_blender_pilot_sites import ANNOTATION_COLLECTIONS, ANNOTATION_PREFIXES

    from amidst.simulation.blender_camera import extract_camera_dict

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--edge-audit", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists():
        raise FileExistsError(args.output)
    data = json.loads(args.input.read_text())
    audit = json.loads(args.edge_audit.read_text())
    config = json.loads(args.config.read_text())
    if audit["input_sha256"] != sha(args.input):
        raise ValueError("EDGE_AUDIT_PARENT_MISMATCH")
    source = Path(bpy.data.filepath)
    before = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if before != (data["source_sha256"], data["source_size"], data["source_mtime_ns"]):
        raise ValueError("PHYSICAL_GRAPH_SOURCE_MISMATCH")
    scene = bpy.context.scene
    if scene.frame_current != data["evaluated_scene_frame"]:
        raise ValueError("PHYSICAL_GRAPH_FRAME_MISMATCH")
    for key in (
        "metres_per_blender_unit",
        "grid_spacing_m",
        "target_height_m",
        "body_radius_m",
        "foot_clearance_m",
        "floor_search_z_m",
        "support_height_tolerance_m",
    ):
        if config[key] != data["config"][key]:
            raise ValueError("PHYSICAL_GRAPH_CONFIG_MISMATCH: " + key)
    scale, spacing = config["metres_per_blender_unit"], config["grid_spacing_m"]
    step = spacing / scale
    height = config["target_height_m"] / scale
    clearance = config["foot_clearance_m"] / scale
    nodes = {tuple(r["grid_xy"]): r for r in data["grid_evidence"]}
    graph = {
        n: [
            m
            for m in ((n[0] - 1, n[1]), (n[0] + 1, n[1]), (n[0], n[1] - 1), (n[0], n[1] + 1))
            if m in nodes
        ]
        for n in nodes
    }
    if (
        data["search"]["edge_rejections"]
        or sum(map(len, graph.values())) // 2 != data["search"]["edges"]
    ):
        raise ValueError("PHYSICAL_GRAPH_EDGE_RECONSTRUCTION_FAILED")
    seen = {
        n: sorted({i for probe in r["visible_camera_indices_by_probe"] for i in probe})
        for n, r in nodes.items()
    }
    camera_ids = data["camera_order"]
    cameras = [bpy.data.objects[name] for name in camera_ids]
    calibration = [extract_camera_dict(scene, c) for c in cameras]
    if calibration != data["calibrations_scene_units"]:
        raise ValueError("CAMERA_CALIBRATION_CHANGED")
    excluded = set()
    for name in ANNOTATION_COLLECTIONS:
        collection = bpy.data.collections.get(name)
        if collection:
            excluded.update(o.original.as_pointer() for o in collection.all_objects)
    for obj in scene.objects:
        if obj.name.startswith(ANNOTATION_PREFIXES) or obj.get("annotation_only"):
            excluded.add(obj.original.as_pointer())
    vertices, triangles, owners = [], [], []
    depsgraph = bpy.context.evaluated_depsgraph_get()
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
        offset = len(vertices)
        vertices.extend(instance.matrix_world @ v.co for v in mesh.vertices)
        for tri in mesh.loop_triangles:
            triangles.append(tuple(offset + i for i in tri.vertices))
            owners.append(obj.original.name)
        obj.to_mesh_clear()
    if len(triangles) != data["search"]["physical_triangles"]:
        raise ValueError("STATIC_TRIANGLE_COUNT_CHANGED")
    bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=0)
    print("C6_REFINEMENT_BVH_READY", flush=True)

    @functools.lru_cache(maxsize=50000)
    def visibility(x, y, z):
        result = []
        for cam, cal in zip(cameras, calibration, strict=True):
            origin = cam.evaluated_get(depsgraph).matrix_world.translation
            probes = []
            for h in (clearance, clearance + height / 2, clearance + height):
                point = Vector((x, y, z + h))
                ndc = world_to_camera_view(scene, cam, point)
                delta = point - origin

                def cast(origin=origin, delta=delta):
                    hit, _, index, _ = bvh.ray_cast(
                        origin, delta.normalized(), delta.length - 0.001
                    )
                    return owners[index] if hit is not None else None

                probes.append(
                    {
                        **probe_visibility(tuple(ndc), cal["clip_start"], cal["clip_end"], cast),
                        "incidence": round(abs(delta.z) / delta.length, 6),
                    }
                )
            result.append(probes)
        return result

    pool_path = root / config["frozen_pool"]["path"]
    if sha(pool_path) != config["frozen_pool"]["sha256"]:
        raise ValueError("FROZEN_POOL_HASH_MISMATCH")
    pool = json.loads(pool_path.read_text())
    if pool["parent_sha256"] != sha(args.input):
        raise ValueError("FROZEN_POOL_PARENT_MISMATCH")
    policy = config["prescreen"]
    clock = config["render_clock"]
    speed = clock["speed_m_s"]
    records = []
    for route in pool["routes"]:
        path = [tuple(n) for n in route["grid_path"]]
        if any(b not in graph[a] for a, b in zip(path, path[1:], strict=False)):
            raise ValueError("FROZEN_PATH_NOT_PHYSICALLY_CHECKED")
        length = (len(path) - 1) * spacing
        duration = length / speed

        @functools.cache
        def sample(t, length=length, path=path):
            distance = min(length, max(0, (t - clock["route_start_s"]) * speed))
            i = min(len(path) - 2, int(distance / spacing))
            f = (distance - i * spacing) / spacing
            a, b = path[i : i + 2]
            x, y = ((a[c] * (1 - f) + b[c] * f) * step for c in (0, 1))
            z = (nodes[a]["floor_z_m"] * (1 - f) + nodes[b]["floor_z_m"] * f) / scale
            rays = visibility(x, y, z)
            return {
                "timestamp_s": t,
                "distance_m": distance,
                "foot_position_m": [x * scale, y * scale, (z + clearance) * scale],
                "rays": rays,
                "visible_cameras": [
                    camera_ids[j]
                    for j, p in enumerate(rays)
                    if any(v["status"] == "VISIBLE" for v in p)
                ],
                "v2_bottom_eligible_cameras": [
                    camera_ids[j]
                    for j, p in enumerate(rays)
                    if p[0]["status"] == "VISIBLE"
                    and p[0]["incidence"] >= config["min_bottom_incidence"]
                ],
            }

        times = frame_times(duration, clock)
        check_k1_alignment(times, clock, config["k1_alignment"]["time_step_s"])
        frames = [sample(t) for t in times]
        dt = config["temporal_sampling"]["diagnostic_step_s"]
        dense_times = sorted(
            set(
                times
                + [round(i * dt, 9) for i in range(math.floor(duration / dt) + 1)]
                + [duration]
            )
        )
        dense = [sample(t) for t in dense_times]
        record = {
            "candidate_id": route["raw_gap_id"],
            "raw_gap_id": route["raw_gap_id"],
            "role": "VISIBLE_BLIND_VISIBLE",
            "length_m": length,
            "grid_path": route["grid_path"],
            "waypoints_m": [
                [n[0] * spacing, n[1] * spacing, nodes[n]["floor_z_m"] + config["foot_clearance_m"]]
                for n in path
            ],
            "samples": frames,
            "physical_navigation": "NOT_CERTIFIED",
            "continuous_floor_support": "UNKNOWN_SAMPLED_SUPPORT_ONLY",
            "rgb_detection": "UNKNOWN_NOT_RENDERED",
        }
        record["contains_revisited_grid_nodes"] = len(set(path)) < len(path)
        record["revisited_grid_node_count"] = len(path) - len(set(path))
        record["prescreen"] = classify_frames(record, dense, config)
        # Measure turns on the original source-checked polyline, never on a
        # chord connecting frame samples across a corner.
        points = record["waypoints_m"]
        indices = simplified_indices(points, policy["simplification_tolerance_m"])
        blind_indices = record["prescreen"].get("blind_sample_indices")
        events = []
        if blind_indices:
            low, high = [frames[j]["distance_m"] for j in blind_indices]
            for a, b, c in zip(indices, indices[1:], indices[2:], strict=False):
                v = [points[b][k] - points[a][k] for k in (0, 1)]
                w = [points[c][k] - points[b][k] for k in (0, 1)]
                denom = math.hypot(*v) * math.hypot(*w)
                if not denom:
                    continue
                angle = math.degrees(
                    math.acos(
                        max(-1, min(1, sum(x * y for x, y in zip(v, w, strict=True)) / denom))
                    )
                )
                if low <= b * spacing <= high and angle > policy["min_turn_angle_degrees"]:
                    events.append(
                        {"path_vertex_index": b, "distance_m": b * spacing, "angle_degrees": angle}
                    )
        record["prescreen"].update(
            turns_in_blind=len(events),
            turn_events_in_blind=events,
            simplified_turn_measurement_indices=indices,
            turn_measurement_basis="ORIGINAL_POLYLINE_WITHIN_FRAME_BLIND_ENVELOPE",
        )
        dense_policy = dict(policy)
        dense_policy["speed_band_m_s"] = [policy["speed_band_m_s"][0], speed]
        record["continuous_diagnostic"] = classify_route({**record, "samples": dense}, dense_policy)
        blind_frames = [j for j, s in enumerate(frames) if not s["visible_cameras"]]
        fragments = []
        # Inspect each camera separately; aggregate ANY-probe visibility is the
        # admission test. Transition brackets are diagnostics, not an exhaustive
        # proof that no still shorter fragment exists between source samples.
        if blind_frames:
            lo, hi = times[blind_frames[0]], times[blind_frames[-1]]
            for ci, camera in enumerate(camera_ids):

                def visible(t, ci=ci, sample=sample):
                    return any(p["status"] == "VISIBLE" for p in sample(t)["rays"][ci])

                spans = []
                run = None
                for j, t in enumerate(dense_times):
                    v = visible(t)
                    if v and run is None:
                        run = j
                    if run is not None and (not v or j == len(dense_times) - 1):
                        end = j - 1 if not v else j
                        if dense_times[end] >= lo and dense_times[run] <= hi:
                            spans.append((run, end))
                        run = None
                for first, last in spans:
                    if any(
                        visible(t)
                        for t in times
                        if dense_times[first] - 1e-9 <= t <= dense_times[last] + 1e-9
                    ):
                        continue

                    def transition(a, b):
                        va = visible(a)
                        while b - a > config["temporal_sampling"]["transition_tolerance_s"]:
                            mid = (a + b) / 2
                            if visible(mid) == va:
                                a = mid
                            else:
                                b = mid
                        return [a, b]

                    left = (
                        transition(dense_times[first - 1], dense_times[first])
                        if first
                        else [dense_times[first]] * 2
                    )
                    right = (
                        transition(dense_times[last], dense_times[last + 1])
                        if last + 1 < len(dense_times)
                        else [dense_times[last]] * 2
                    )
                    begin = sum(left) / 2
                    end = sum(right) / 2
                    if not (lo < begin < end < hi):
                        continue
                    nearest = min(times, key=lambda t: min(abs(t - begin), abs(t - end)))
                    fragments.append(
                        {
                            "camera_id": camera,
                            "start_s": begin,
                            "end_s": end,
                            "duration_s": end - begin,
                            "length_m": (end - begin) * speed,
                            "start_transition_bracket_s": left,
                            "end_transition_bracket_s": right,
                            "nearest_frame_s": nearest,
                            "nearest_frame_delta_s": min(abs(nearest - begin), abs(nearest - end)),
                            "enclosing_frame_times_s": [
                                max(t for t in times if t < begin),
                                min(t for t in times if t > end),
                            ],
                        }
                    )
        record["between_frame_visible_fragments"] = fragments
        record["turns_in_blind"] = record["prescreen"]["turns_in_blind"]
        record["source_ray_occluders"] = sorted(
            {p["occluder"] for s in dense for probes in s["rays"] for p in probes if p["occluder"]}
        )
        records.append(record)
        if len(records) % 64 == 0:
            print("C6_FRAME_PROGRESS", len(records), flush=True)
    selected = select_benchmarks(records, policy)
    for r in selected:
        r["adjacent_visible_regions_and_potential_exits"] = adjacent_exits(
            graph, seen, [tuple(n) for n in r["grid_path"] if not seen[tuple(n)]], spacing
        )
        r["transparent_occluders"] = [
            {"object": name, "materials": [{"reasons": ["READ_SOURCE_SLOTS_REQUIRED"]}]}
            for name in r["source_ray_occluders"]
            if bpy.data.objects.get(name) and bpy.data.objects[name].material_slots
        ]
        r["rgb_material_spotcheck_required"] = bool(r["transparent_occluders"])
        r["c7_map_recheck"] = {"status": "PENDING_C7", "deadline": "2026-10-22"}
        r["legacy_gap_ids"] = []
    after = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if after != before:
        raise RuntimeError("SOURCE_CHANGED")
    qualified = [r for r in records if r["prescreen"]["qualified"]]
    summary = {
        "status": "READY_FOR_COORDINATOR_REVIEW"
        if len(selected) >= policy["min_selected"]
        else "NOT_READY_INSUFFICIENT_QUALIFIED_ROUTES",
        "raw_records_evaluated": len(records),
        "frame_qualified_count": len(qualified),
        "frame_qualified_cross_camera_count": sum(
            r["prescreen"]["cross_camera"] for r in qualified
        ),
        "continuous_diagnostic_qualified_count": sum(
            r["continuous_diagnostic"]["qualified"] for r in records
        ),
        "continuous_diagnostic_qualified_cross_camera_count": sum(
            r["continuous_diagnostic"]["qualified"] and r["continuous_diagnostic"]["cross_camera"]
            for r in records
        ),
        "selected_count": len(selected),
        "cross_camera_count": sum(r["prescreen"]["cross_camera"] for r in selected),
        "selected_with_between_frame_fragments": sum(
            bool(r["between_frame_visible_fragments"]) for r in selected
        ),
        "rejection_reasons": dict(
            collections.Counter(reason for r in records for reason in r["prescreen"]["reasons"])
        ),
        "benchmark_id_mapping": [
            {
                "benchmark_id": r["benchmark_id"],
                "raw_gap_id": r["raw_gap_id"],
                "legacy_gap_ids": r["legacy_gap_ids"],
            }
            for r in selected
        ],
        "legacy_candidate_audit": [],
        "diagnostic_candidates_not_for_benchmark": [],
        "all_candidate_results": [
            {
                k: r[k]
                for k in (
                    "raw_gap_id",
                    "prescreen",
                    "continuous_diagnostic",
                    "between_frame_visible_fragments",
                )
            }
            for r in records
        ],
        "policy": policy,
        "narrow_edge_audits": [],
    }
    result = {
        "schema_version": "office-demo.c6-fixed-frame-screen.v1",
        "source_sha256": before[0],
        "source_size": before[1],
        "source_mtime_ns": before[2],
        "source_identity_unchanged": True,
        "source_saved": False,
        "render_executed": False,
        "inference_input_eligible": False,
        "physical_graph_parent_sha256": sha(args.input),
        "frozen_pool_sha256": sha(pool_path),
        "config_sha256": sha(args.config),
        "producer_sha256": sha(__file__),
        "policy_module_sha256": sha(root / "scripts/c6_prescreen.py"),
        "frame_module_sha256": sha(root / "scripts/c6_frame_screen.py"),
        "config": config,
        "camera_order": camera_ids,
        "calibrations_scene_units": calibration,
        "candidates": selected,
        "prescreen": summary,
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    print(
        "C6_FIXED_FRAME_RESULT",
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in ("all_candidate_results", "policy", "benchmark_id_mapping")
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

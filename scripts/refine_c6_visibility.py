"""Refine C6 routes using actual midpoint visibility, reusing pinned body-graph evidence.

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
    from c6_prescreen import (
        adjacent_exits,
        classify_route,
        probe_visibility,
        search_paths,
        select_benchmarks,
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

    eligible = {}
    for n, row in nodes.items():
        p = [n[0] * spacing, n[1] * spacing, row["floor_z_m"] + config["foot_clearance_m"]]
        eligible[n] = []
        for i in row["visible_camera_indices_by_probe"][0]:
            origin = [calibration[i]["camera_to_world"][k][3] * scale for k in (0, 1, 2)]
            if (
                round(abs(p[2] - origin[2]) / math.dist(p, origin), 6)
                >= config["min_bottom_incidence"]
            ):
                eligible[n].append(i)
    cuts = {
        tuple(sorted(tuple(round(v / spacing) for v in n) for n in edge))
        for edge in audit["blind_node_edges_with_visible_midpoint"]
    }
    initial_cut_count = len(cuts)
    trials, selected, final_records = [], [], []
    policy = config["prescreen"]
    for trial in range(1, policy["max_visibility_refinement_passes"] + 1):
        proposal_graph = {
            n: [m for m in graph[n] if tuple(sorted((n, m))) not in cuts] for n in graph
        }
        paths, boundaries, truncated = search_paths(proposal_graph, seen, eligible, spacing, policy)
        records = []
        discovered = set()
        for k, path in enumerate(paths, 1):
            samples = []
            for j in range(2 * len(path) - 1):
                a, b = path[j // 2], path[min(j // 2 + 1, len(path) - 1)]
                t = (j % 2) / 2
                x, y = ((a[c] * (1 - t) + b[c] * t) * step for c in (0, 1))
                z = (nodes[a]["floor_z_m"] * (1 - t) + nodes[b]["floor_z_m"] * t) / scale
                rays = visibility(x, y, z)
                active = [
                    camera_ids[i]
                    for i, probes in enumerate(rays)
                    if any(p["status"] == "VISIBLE" for p in probes)
                ]
                bottom = [
                    camera_ids[i]
                    for i, probes in enumerate(rays)
                    if probes[0]["status"] == "VISIBLE"
                    and probes[0]["incidence"] >= config["min_bottom_incidence"]
                ]
                samples.append(
                    {
                        "distance_m": j * spacing / 2,
                        "foot_position_m": [x * scale, y * scale, (z + clearance) * scale],
                        "rays": rays,
                        "visible_cameras": active,
                        "v2_bottom_eligible_cameras": bottom,
                    }
                )
            for j, (a, b) in enumerate(zip(path, path[1:], strict=False)):
                mid = samples[2 * j + 1]
                active = bool(mid["visible_cameras"])
                both_blind = not seen[a] and not seen[b]
                both_visible = bool(seen[a]) and bool(seen[b])
                common = set(eligible[a]) & set(eligible[b])
                mid_indices = {camera_ids.index(name) for name in mid["v2_bottom_eligible_cameras"]}
                transition_eligible = set(eligible[a]) | set(eligible[b])
                if (
                    (both_blind and active)
                    or (both_visible and not active)
                    or (both_visible and common and not common & mid_indices)
                    or (
                        not both_blind
                        and not both_visible
                        and active
                        and not transition_eligible & mid_indices
                    )
                ):
                    discovered.add(tuple(sorted((a, b))))
            record = {
                "candidate_id": f"c6-refinement-{trial}-gap-{k:04}",
                "raw_gap_id": f"c6-refinement-{trial}-gap-{k:04}",
                "role": "VISIBLE_BLIND_VISIBLE",
                "length_m": (len(path) - 1) * spacing,
                "samples": samples,
                "waypoints_m": [s["foot_position_m"] for s in samples],
                "contains_revisited_grid_nodes": len(set(path)) < len(path),
                "continuous_swept_box": "REUSES_SOURCE_PINNED_PHYSICAL_GRAPH_EDGE_EVIDENCE",
                "continuous_floor_support": "UNKNOWN_SAMPLED_SUPPORT_ONLY",
                "physical_navigation": "NOT_CERTIFIED",
                "rgb_detection": "UNKNOWN_NOT_RENDERED",
            }
            record["prescreen"] = classify_route(record, policy)
            record["turns_in_blind"] = record["prescreen"]["turns_in_blind"]
            records.append(record)
        selected = select_benchmarks(records, policy)
        new_cuts = discovered - cuts
        trials.append(
            {
                "pass": trial,
                "candidate_count": len(records),
                "boundaries": boundaries,
                "search_truncated": truncated,
                "qualified_count": sum(r["prescreen"]["qualified"] for r in records),
                "qualified_cross_camera_count": sum(
                    r["prescreen"]["qualified"] and r["prescreen"]["cross_camera"] for r in records
                ),
                "selected_count": len(selected),
                "new_visibility_edge_cuts": len(new_cuts),
                "rejection_reasons": dict(
                    collections.Counter(
                        reason for r in records for reason in r["prescreen"]["reasons"]
                    )
                ),
            }
        )
        print("C6_REFINEMENT_PASS " + json.dumps(trials[-1]), flush=True)
        final_records = records
        if len(selected) >= policy["min_selected"] or not new_cuts:
            break
        cuts.update(new_cuts)
    edge_audits = []
    for record in selected:
        path = [
            tuple(round(v / spacing) for v in s["foot_position_m"][:2])
            for s in record["samples"][::2]
        ]
        record["adjacent_visible_regions_and_potential_exits"] = adjacent_exits(
            graph, seen, [n for n in path if not seen[n]], spacing
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
        record["transparent_occluders"] = []
        for name in blockers:
            obj = bpy.data.objects.get(name)
            materials = []
            for slot in obj.material_slots if obj else []:
                mat = slot.material
                if mat is not None and (
                    mat.diffuse_color[3] < 0.999
                    or getattr(mat, "blend_method", "OPAQUE") != "OPAQUE"
                    or mat.use_nodes
                ):
                    materials.append(
                        {
                            "material": mat.name,
                            "reasons": ["SOURCE_MATERIAL_PROPERTIES_SPOTCHECK_REQUIRED"],
                        }
                    )
            if materials:
                record["transparent_occluders"].append({"object": name, "materials": materials})
        record["rgb_material_spotcheck_required"] = bool(record["transparent_occluders"])
        record["c7_map_recheck"] = {"status": "PENDING_C7", "deadline": "2026-10-22"}
        record["legacy_gap_ids"] = []
        positions = {tuple(s["foot_position_m"][:2]) for s in record["samples"]}
        legacy = json.loads((root / "docs/engineering/C6_FEASIBILITY_20261016.json").read_text())
        for old in legacy["candidates"]:
            if old["role"] != "VISIBLE_BLIND_VISIBLE":
                continue
            old_points = {tuple(s["foot_position_m"][:2]) for s in old["samples"]}
            if len(positions & old_points) / min(len(positions), len(old_points)) >= 0.5:
                record["legacy_gap_ids"].append(old["candidate_id"])
        # Fresh dense support checks on route edges; body evidence is pinned above.
        nearby = []
        for a, b in zip(path, path[1:], strict=False):
            x, y = ((a[c] + b[c]) * step / 2 for c in (0, 1))
            z = nodes[a]["floor_z_m"] / scale
            hit, _, index, distance = bvh.find_nearest(Vector((x, y, z + height / 2)))
            if hit is not None:
                nearby.append((distance, a, b, owners[index]))
        for distance, a, b, owner in sorted(nearby)[:2]:
            tests = []
            for part in range(9):
                t = part / 8
                x, y = ((a[c] * (1 - t) + b[c] * t) * step for c in (0, 1))
                floor = nodes[a]["floor_z_m"] / scale
                for angle in range(0, 360, 45):
                    radius = config["body_radius_m"] / scale
                    hit, normal, _, _ = bvh.ray_cast(
                        Vector(
                            (
                                x + radius * math.cos(math.radians(angle)),
                                y + radius * math.sin(math.radians(angle)),
                                floor + 0.08 / scale,
                            )
                        ),
                        Vector((0, 0, -1)),
                        0.16 / scale,
                    )
                    tests.append(
                        hit is not None
                        and abs(normal.z) >= 0.95
                        and abs(hit.z - floor) * scale <= config["support_height_tolerance_m"]
                    )
            edge_audits.append(
                {
                    "benchmark_id": record["benchmark_id"],
                    "edge_xy_m": [[v * spacing for v in n] for n in (a, b)],
                    "nearest_source_object": owner,
                    "nearest_distance_m": distance * scale,
                    "support_samples": len(tests),
                    "all_support_samples_pass": all(tests),
                    "semantic_door_or_seating_classification": "UNKNOWN_UNTIL_C7",
                }
            )
    after = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if after != before:
        raise RuntimeError("SOURCE_CHANGED")
    result = {
        "schema_version": "office-demo.c6-visibility-refinement.v1",
        "source_sha256": before[0],
        "source_size": before[1],
        "source_mtime_ns": before[2],
        "source_identity_unchanged": True,
        "physical_graph_parent_sha256": sha(args.input),
        "edge_audit_parent_sha256": sha(args.edge_audit),
        "config_sha256": sha(args.config),
        "producer_sha256": sha(__file__),
        "policy_module_sha256": sha(root / "scripts/c6_prescreen.py"),
        "config": config,
        "camera_order": camera_ids,
        "calibrations_scene_units": calibration,
        "grid_evidence": data["grid_evidence"],
        "source_saved": False,
        "render_executed": False,
        "inference_input_eligible": False,
        "authority": config["authority"],
        "candidates": selected
        + [r for r in data["candidates"] if r["role"] == "FULLY_VISIBLE_CONTROL"],
        "prescreen": {
            "status": "READY_FOR_REVIEW"
            if len(selected) >= policy["min_selected"]
            else "NOT_READY_INSUFFICIENT_QUALIFIED_ROUTES",
            "policy": policy,
            "legacy_candidate_audit": data["prescreen"]["legacy_candidate_audit"],
            "diagnostic_candidates_not_for_benchmark": [],
            "trials": trials,
            "initial_visibility_edge_cuts": initial_cut_count,
            "visibility_edge_cuts": len(cuts),
            "selected_count": len(selected),
            "cross_camera_count": sum(r["prescreen"]["cross_camera"] for r in selected),
            "benchmark_id_mapping": [
                {
                    "benchmark_id": r["benchmark_id"],
                    "raw_gap_id": r["raw_gap_id"],
                    "legacy_gap_ids": r["legacy_gap_ids"],
                }
                for r in selected
            ],
            "narrow_edge_audits": edge_audits,
            "rejected_records": [
                {"raw_gap_id": r["raw_gap_id"], "prescreen": r["prescreen"]}
                for r in final_records
                if r not in selected
            ],
        },
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    print("C6_VISIBILITY_REFINEMENT_OK " + result["prescreen"]["status"], flush=True)


if __name__ == "__main__":
    main()

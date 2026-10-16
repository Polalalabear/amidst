"""Evaluate a frozen route pool at exact render frames and between-frame source samples.

Runs inside Blender. No rendering, source save, annotation geometry, or GT input.
"""

import argparse
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
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / "scripts"), str(root / "src")]
    from plan_blender_pilot_sites import ANNOTATION_COLLECTIONS, ANNOTATION_PREFIXES

    from amidst.simulation.blender_camera import extract_camera_dict

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--edge-audit", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selected", required=True, type=Path)
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

    selected_data = json.loads(args.selected.read_text())
    if selected_data["physical_graph_parent_sha256"] != sha(args.input):
        raise ValueError("SELECTED_PARENT_MISMATCH")
    edge_audits = []
    for record in selected_data["candidates"]:
        path = [tuple(n) for n in record["grid_path"]]
        # Fresh source support checks on narrow selected edges; body evidence is pinned.
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
    if before != after:
        raise RuntimeError("SOURCE_CHANGED")
    result = {
        "schema_version": "c6-selected-edge-audit.v1",
        "source_sha256": before[0],
        "source_identity_unchanged": True,
        "selected_sha256": sha(args.selected),
        "physical_graph_parent_sha256": sha(args.input),
        "producer_sha256": sha(__file__),
        "narrow_edge_audits": edge_audits,
        "render_executed": False,
        "source_saved": False,
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        "C6_SELECTED_EDGE_AUDIT",
        len(edge_audits),
        sum(r["all_support_samples_pass"] for r in edge_audits),
        flush=True,
    )


if __name__ == "__main__":
    main()

"""C5 independent inference-side static source rays; no render/save/target data."""

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def opaque_material(material):
    if material is None:
        return True
    if material.diffuse_color[3] < 0.999:
        return False
    if material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type in {"BSDF_GLASS", "BSDF_TRANSPARENT", "BSDF_REFRACTION"}:
                return False
            if node.type == "BSDF_PRINCIPLED":
                for name, threshold in [
                    ("Alpha", 0.999),
                    ("Transmission Weight", 0.001),
                    ("Transmission", 0.001),
                ]:
                    value = node.inputs.get(name)
                    if value and (
                        value.is_linked
                        or (
                            value.default_value < threshold
                            if name == "Alpha"
                            else value.default_value > threshold
                        )
                    ):
                        return False
    return True


def main():
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / "src"), str(root / "scripts")]
    from plan_blender_pilot_sites import ANNOTATION_COLLECTIONS, ANNOTATION_PREFIXES

    from amidst.geometry.visibility_policy import probe_status, union_status

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "safe-inputs", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists():
        raise FileExistsError(args.output)
    config = json.loads(args.config.read_text())
    safe = json.loads(args.safe_inputs.read_text())
    source = Path(bpy.data.filepath)
    before = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if (
        before[0] != config["source_sha256"]
        or sha(args.safe_inputs) != config["safe_inputs_sha256"]
    ):
        raise ValueError("SOURCE_OR_SAFE_INPUTS_HASH_MISMATCH")
    if (
        config["target_visibility_or_trajectory_input"]
        or config["annotations_as_occluders"]
        or config["render"]
        or config["source_saved"]
    ):
        raise ValueError("STATIC_SOURCE_ONLY_REQUIRED")
    if (
        safe["source_binding"]["run_id"] != config["run_id"]
        or bpy.context.scene.frame_current != config["source_frame"]
    ):
        raise ValueError("RUN_OR_SOURCE_FRAME_MISMATCH")
    scene = bpy.context.scene
    graph = bpy.context.evaluated_depsgraph_get()
    scale = config["metres_per_blender_unit"]
    cameras = {c["camera_id"]: c["calibration"] for c in safe["cameras"]}
    for name, cal in cameras.items():
        matrix = scene.objects[name].evaluated_get(graph).matrix_world
        if (
            max(
                abs(
                    float(matrix[i][j]) * (scale if j == 3 and i < 3 else 1)
                    - cal["camera_to_world"][i][j]
                )
                for i in range(4)
                for j in range(4)
            )
            > 1e-5
        ):
            raise ValueError("SOURCE_CAMERA_CALIBRATION_MISMATCH")
    excluded = set()
    for name in ANNOTATION_COLLECTIONS:
        collection = bpy.data.collections.get(name)
        if collection:
            excluded.update(o.original.as_pointer() for o in collection.all_objects)
    for obj in scene.objects:
        if (
            obj.name.startswith(ANNOTATION_PREFIXES)
            or obj.get("annotation_only")
            or obj.get("phase1_annotation_only")
        ):
            excluded.add(obj.original.as_pointer())
    roi = config["roi_m"]
    z0 = config["floor_z_m"]
    z1 = max(c["camera_to_world"][2][3] for c in cameras.values())
    vertices = []
    triangles = []
    opaque = []
    counts = {"objects": 0, "triangles": 0, "nonopaque_triangles": 0, "excluded_annotations": 0}
    for instance in graph.object_instances:
        obj = instance.object
        if obj.type != "MESH" or not instance.show_self or obj.hide_render:
            continue
        if obj.original.as_pointer() in excluded or (
            instance.parent and instance.parent.original.as_pointer() in excluded
        ):
            counts["excluded_annotations"] += 1
            continue
        corners = [instance.matrix_world @ Vector(p) for p in obj.bound_box]
        bounds = [[f(p[a] * scale for p in corners) for a in range(3)] for f in (min, max)]
        if (
            any(bounds[1][a] < roi[0][a] or bounds[0][a] > roi[1][a] for a in (0, 1))
            or bounds[1][2] < z0
            or bounds[0][2] > z1
        ):
            continue
        if obj.original.animation_data and obj.original.animation_data.action:
            raise ValueError("DYNAMIC_SOURCE_GEOMETRY_UNRESOLVED")
        mesh = obj.to_mesh()
        try:
            mesh.calc_loop_triangles()
            offset = len(vertices)
            vertices.extend([(instance.matrix_world @ v.co) * scale for v in mesh.vertices])
            materials = [opaque_material(slot.material) for slot in obj.material_slots]
            for tri in mesh.loop_triangles:
                triangles.append(tuple(offset + i for i in tri.vertices))
                opaque.append(
                    materials[tri.material_index] if tri.material_index < len(materials) else True
                )
            counts["objects"] += 1
        finally:
            obj.to_mesh_clear()
    counts["triangles"] = len(triangles)
    counts["nonopaque_triangles"] = sum(not v for v in opaque)
    print("C5_STATIC_BVH", counts, flush=True)
    bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=0)
    del vertices, triangles
    step = config["subcell_step_m"]
    origin = [math.floor(roi[0][a] / step) * step for a in (0, 1)]
    nx, ny = [math.ceil((roi[1][a] - origin[a]) / step) + 1 for a in (0, 1)]
    codes = {"NOT_VISIBLE": 0, "VISIBLE": 1, "UNKNOWN": 2}
    probe_codes = {"OCCLUDED": 0, "VISIBLE": 1, "UNKNOWN": 2, "OUTSIDE_FOV": 3, "CLIPPED": 4}
    results = []
    for camera_id, cal in cameras.items():
        eye = Vector([cal["camera_to_world"][i][3] for i in range(3)])
        statuses = []
        per_probe = []
        combinations = Counter({f"{i:03b}": 0 for i in range(8)})
        head_only = 0
        ray_count = 0
        for ix in range(nx):
            for iy in range(ny):
                x, y = origin[0] + ix * step, origin[1] + iy * step
                probes = []
                for height in config["probe_offsets_m"]:
                    point = [x, y, z0 + height]

                    def raycast(point=point, eye=eye):
                        nonlocal ray_count
                        ray_count += 1
                        delta = Vector(point) - eye
                        hit, _, face, _ = bvh.ray_cast(
                            eye, delta.normalized(), max(0, delta.length - 1e-5)
                        )
                        if hit is None:
                            return "VISIBLE"
                        return "OCCLUDED" if opaque[face] else "UNKNOWN"

                    probes.append(probe_status(cal, point, raycast))
                status = union_status(probes)
                per_probe.append([probe_codes[p] for p in probes])
                combinations["".join("1" if p == "VISIBLE" else "0" for p in probes)] += 1
                statuses.append(codes[status])
                head_only += status == "VISIBLE" and probes[0] != "VISIBLE"
        print(
            "C5_CAMERA",
            camera_id,
            "samples",
            len(statuses),
            "rays",
            ray_count,
            "head_or_torso_only",
            head_only,
            flush=True,
        )
        results.append(
            {
                "camera_id": camera_id,
                "sample_status_codes": statuses,
                "probe_status_codes": per_probe,
                "probe_order": ["foot", "waist", "head"],
                "probe_code_legend": probe_codes,
                "probe_visible_counts": dict(sorted(combinations.items())),
                "head_or_torso_only_visible_samples": head_only,
                "rays_tested": ray_count,
            }
        )
    after = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if before != after:
        raise RuntimeError("SOURCE_IDENTITY_CHANGED")
    result = {
        "schema_version": "office-demo.floor-visibility-rays.v1",
        "config": config,
        "config_sha256": sha(args.config),
        "safe_inputs_sha256": sha(args.safe_inputs),
        "source_sha256": before[0],
        "source_identity_unchanged": True,
        "source_saved": False,
        "render_executed": False,
        "gt_read": False,
        "renderer_visibility_read": False,
        "producer_sha256": sha(__file__),
        "policy_sha256": sha(root / "src/amidst/geometry/visibility_policy.py"),
        "sample_grid": {
            "origin_m": origin,
            "step_m": step,
            "nx": nx,
            "ny": ny,
            "order": "X_MAJOR_Y_MINOR",
            "codes": codes,
        },
        "mesh_counts": counts,
        "cameras": results,
    }
    result["output_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    with args.output.open("x") as stream:
        json.dump(result, stream, separators=(",", ":"), allow_nan=False)
        stream.write("\n")
    print("C5_COMPLETE", sha(args.output), flush=True)


if __name__ == "__main__":
    main()

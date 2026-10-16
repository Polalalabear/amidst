"""C7 bounded evaluated source mesh export; no annotation or target/run data.

Read-only Blender process; selected by camera-derived ROI. Output is a new
LOCAL gzip intermediate, not a source asset copy or a navigation certificate.
"""

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    import bpy
    from mathutils import Vector

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from plan_blender_pilot_sites import ANNOTATION_COLLECTIONS, ANNOTATION_PREFIXES

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists():
        raise FileExistsError(args.output)
    config = json.loads(args.config.read_text())
    if (
        config["annotations_as_inputs"]
        or config["target_trajectories_as_inputs"]
        or config["render"]
        or config["source_saved"]
    ):
        raise ValueError("SOURCE_ONLY_POLICY_REQUIRED")
    source = Path(bpy.data.filepath)
    before = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if before[0] != config["source_sha256"]:
        raise ValueError("SOURCE_HASH_MISMATCH")
    scene = bpy.context.scene
    scale = config["metres_per_blender_unit"]
    if {
        "name": scene.name,
        "frame": scene.frame_current,
        "subframe": scene.frame_subframe,
    } != config["evaluated_scene"]:
        raise ValueError("SOURCE_FRAME_MISMATCH")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    cameras = [
        {
            "camera_id": name,
            "matrix_world_bu": [
                list(r) for r in scene.objects[name].evaluated_get(depsgraph).matrix_world
            ],
        }
        for name in config["scope_camera_ids"]
    ]
    positions = [[c["matrix_world_bu"][a][3] * scale for a in range(3)] for c in cameras]
    margin = config["roi_from_camera_origins_m"]
    low = [
        min(p[0] for p in positions) - margin["west"],
        min(p[1] for p in positions) - margin["south"],
        config["floor_top_search_z_m"][0],
    ]
    high = [
        max(p[0] for p in positions) + margin["east"],
        max(p[1] for p in positions) + margin["north"],
        config["floor_top_search_z_m"][1]
        + max(p["body_height_m"] for p in config["run_parameters"].values()),
    ]
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
    objects = []
    definitions = {}
    counts = {
        "evaluated_instances_seen": 0,
        "physical_meshes_in_roi": 0,
        "outside_roi": 0,
        "excluded_annotations_or_hidden": 0,
    }
    for instance in depsgraph.object_instances:
        obj = instance.object
        counts["evaluated_instances_seen"] += 1
        if (
            obj.type != "MESH"
            or not instance.show_self
            or obj.hide_render
            or obj.original.as_pointer() in excluded
            or (instance.parent and instance.parent.original.as_pointer() in excluded)
        ):
            counts["excluded_annotations_or_hidden"] += 1
            continue
        corners = [instance.matrix_world @ Vector(p) for p in obj.bound_box]
        bounds = [[f(p[a] * scale for p in corners) for a in range(3)] for f in (min, max)]
        if any(bounds[1][a] < low[a] or bounds[0][a] > high[a] for a in range(3)):
            counts["outside_roi"] += 1
            continue
        mesh = obj.to_mesh()
        try:
            mesh.calc_loop_triangles()
            geometry = {
                "vertices": [list(v.co) for v in mesh.vertices],
                "triangles": [list(t.vertices) for t in mesh.loop_triangles],
            }
            digest = hashlib.sha256(encoded(geometry)).hexdigest()
            if digest not in definitions:
                definitions[digest] = geometry
            matrix = [list(r) for r in instance.matrix_world]
            parent = obj.original.parent.name if obj.original.parent else None
            identity = {
                "object_id": obj.original.name,
                "parent": parent,
                "persistent_id": list(instance.persistent_id),
                "matrix_world_bu": matrix,
            }
            # Independent Python arithmetic vs Blender evaluated Vector transform.
            error = max(
                (
                    abs(
                        (sum(matrix[a][k] * v.co[k] for k in range(3)) + matrix[a][3]) * scale
                        - (instance.matrix_world @ v.co)[a] * scale
                    )
                    for v in mesh.vertices
                    for a in range(3)
                ),
                default=0,
            )
            if error > 1e-4:
                raise ValueError("WORLD_TRANSFORM_MISMATCH")
            objects.append(
                {
                    **identity,
                    "instance_ref": "mesh:" + hashlib.sha256(encoded(identity)).hexdigest()[:24],
                    "geometry_sha256": digest,
                    "source_bounds_m": bounds,
                    "transform_max_error_m": error,
                    "evaluated_triangle_count": len(geometry["triangles"]),
                }
            )
            counts["physical_meshes_in_roi"] += 1
        finally:
            obj.to_mesh_clear()
    after = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if before != after:
        raise RuntimeError("SOURCE_CHANGED")
    result = {
        "schema_version": "office-demo.source-mesh-extract.v1",
        "source_sha256": before[0],
        "source_size": before[1],
        "source_mtime_ns": before[2],
        "source_identity_unchanged": True,
        "source_saved": False,
        "render_executed": False,
        "annotations_as_inputs": False,
        "gt_read": False,
        "evaluated_scene": config["evaluated_scene"],
        "blender_version": bpy.app.version_string,
        "blender_build_hash": bpy.app.build_hash.decode(),
        "config_sha256": sha(args.config),
        "producer_sha256": sha(__file__),
        "policy_dependency_sha256": sha(Path(__file__).with_name("plan_blender_pilot_sites.py")),
        "config": config,
        "roi_m": [low, high],
        "cameras": cameras,
        "objects": sorted(objects, key=lambda r: r["instance_ref"]),
        "geometry_definitions": definitions,
        "counts": counts,
    }
    raw = encoded(result) + b"\n"
    packed = gzip.compress(raw, mtime=0)
    with args.output.open("xb") as stream:
        stream.write(packed)
    print(
        "C7_SOURCE_EXTRACT",
        json.dumps(
            {
                **counts,
                "unique_geometries": len(definitions),
                "gzip_bytes": len(packed),
                "expanded_triangles": sum(o["evaluated_triangle_count"] for o in objects),
                "source_unchanged": True,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

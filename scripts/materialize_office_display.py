"""Bounded display-only export in Blender; never saves/renders the source scene.

blender --background --factory-startup --disable-autoexec school_v3.blend \
  --python-exit-code 2 --python scripts/materialize_office_display.py -- \
  --repo CHECKOUT --evidence EXISTING_EVIDENCE --output NEW_ASSET
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def clip(poly, axis, edge, above):
    result = []
    for start, end in zip(poly, poly[1:] + poly[:1], strict=True):
        a, b = start[axis] - edge, end[axis] - edge
        inside_a, inside_b = (a >= 0, b >= 0) if above else (a <= 0, b <= 0)
        if inside_a:
            result.append(start)
        if inside_a != inside_b:
            t = a / (a - b)
            result.append([start[k] + t * (end[k] - start[k]) for k in range(3)])
    return result


def architecture_outside_office(presentation, office_bounds):
    """Partition each source triangle outside Office; no duplicate interiors or caps."""
    meshes = []
    for source in presentation["meshes"]:
        vertices, triangles, identities = [], [], {}
        for triangle in source["triangles"]:
            inside = [source["vertices"][i] for i in triangle]
            outside = []
            for axis in range(3):
                for edge, above in ((office_bounds[0][axis], True),
                                    (office_bounds[1][axis], False)):
                    if not inside:
                        break
                    part = clip(inside, axis, edge, not above)
                    # Coplanar boundary faces belong to Office, not both layers.
                    if part and not all(abs(p[axis] - edge) < 1e-10 for p in part):
                        outside.append(part)
                    inside = clip(inside, axis, edge, above)
            for polygon in outside:
                for fan in range(1, len(polygon) - 1):
                    corners = [polygon[0], polygon[fan], polygon[fan + 1]]
                    u = [corners[1][k] - corners[0][k] for k in range(3)]
                    v = [corners[2][k] - corners[0][k] for k in range(3)]
                    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2],
                             u[0]*v[1]-u[1]*v[0]]
                    if math.hypot(*cross) < 1e-12:
                        continue
                    indices = []
                    for point in corners:
                        key = tuple(point)
                        if key not in identities:
                            identities[key] = len(vertices)
                            vertices.append(point)
                        indices.append(identities[key])
                    triangles.append(indices)
        if triangles:
            meshes.append({"vertices": vertices, "triangles": triangles,
                           "source_mesh_ref": source["mesh_ref"],
                           "source_geometry_sha256": source["geometry_sha256"],
                           "derivation": source["derivation"],
                           "supplemental_crop": "AUDITORIUM_MINUS_OFFICE_VOLUME_NO_CAPS",
                           "excluded_office_bounds_metres": office_bounds,
                           "authority": "PARTIAL_DISPLAY_CONTEXT", "display_only": True})
    return meshes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    config = json.loads((args.repo / "configs/office_demo_display_v1.json").read_bytes())
    assert not args.output.exists(), "Never overwrite an existing artifact"
    assert shutil.disk_usage(args.output.parent).free >= config["min_free_bytes"]
    source = Path(bpy.data.filepath)
    before = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    assert before[0] == config["source_sha256"]
    scene = bpy.context.scene
    assert {"name": scene.name, "frame": scene.frame_current,
            "subframe": scene.frame_subframe} == config["evaluated_scene"]
    assert (scene.unit_settings.system, scene.unit_settings.scale_length) == ("METRIC", 1.0)
    bundles = {}
    for site in ("office", "auditorium"):
        path = args.evidence / "data/engineering/local_run/blender_camera_v1" / site
        assert sha(path / "safe_inputs.json") == config[site + "_inputs_sha256"]
        bundles[site] = json.loads((path / "safe_inputs.json").read_bytes())
    office, auditorium = bundles["office"], bundles["auditorium"]
    for key in ("source_sha256", "scale_sha256", "model_revision", "metres_per_bu"):
        assert office["source_binding"][key] == auditorium["source_binding"][key] == config[key]
    assert {c["camera_id"]: c["calibration"] for c in office["cameras"]} == {
        c["camera_id"]: c["calibration"] for c in auditorium["cameras"]}
    scale = config["metres_per_bu"]
    for camera in office["cameras"]:
        actual = scene.objects[camera["camera_id"]].matrix_world
        expected = camera["calibration"]["camera_to_world"]
        assert max(abs(actual[a][3] * scale - expected[a][3]) for a in range(3)) < 1e-9
    definitions, instances, world_points = {}, [], []
    graph = bpy.context.evaluated_depsgraph_get()
    for spec in config["objects"]:
        obj = scene.objects[spec["object_id"]]
        assert obj.type == "MESH" and obj.parent.name == spec["assembly"]
        assert not obj.get("phase1_annotation_only", False)
        evaluated = obj.evaluated_get(graph)
        matrix = [list(row) for row in evaluated.matrix_world]
        assert matrix == spec["matrix_world_bu"]
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            geometry = {"vertices": [list(v.co) for v in mesh.vertices],
                        "triangles": [list(t.vertices) for t in mesh.loop_triangles]}
            digest = hashlib.sha256(encoded(geometry)).hexdigest()
            assert digest == spec["geometry_sha256"]
            assert len(geometry["triangles"]) == spec["triangles"]
            definitions[digest] = geometry
            matrix_metres = [[v * scale if a < 3 else v for v in row]
                             for a, row in enumerate(matrix)]
            points = [[sum(matrix_metres[a][k] * p[k] for k in range(3))
                       + matrix_metres[a][3] for a in range(3)]
                      for p in geometry["vertices"]]
            # Independent Blender world evaluation checks the serialized transform arithmetic.
            error = max(abs(point[a] - (evaluated.matrix_world @ vertex.co)[a] * scale)
                        for vertex, point in zip(mesh.vertices, points, strict=True)
                        for a in range(3))
            assert error < 1e-5
            corners = [evaluated.matrix_world @ Vector(p) for p in evaluated.bound_box]
            bounds = [[f(p[a] for p in corners) * scale for a in range(3)] for f in (min, max)]
            assert max(abs(x-y) for row, exp in zip(bounds, spec["source_bounds_metres"],
                       strict=True) for x, y in zip(row, exp, strict=True)) < 1e-5
            instances.append({"object_id": spec["object_id"], "assembly": spec["assembly"],
                              "kind": spec["kind"], "geometry_ref": digest,
                              "matrix_world_metres": matrix_metres,
                              "source_bounds_metres": bounds,
                              "transform_max_error_metres": error})
            world_points.extend(points)
        finally:
            evaluated.to_mesh_clear()
    assert len(instances) == 94 and len(definitions) == 19
    assert sum(len(g["triangles"]) for g in definitions.values()) == 117103
    architecture = architecture_outside_office(auditorium["presentation"],
                                               office["presentation"]["bounds_metres"])
    world_points.extend(p for mesh in architecture for p in mesh["vertices"])
    policy = {k: v for k, v in config.items() if k not in {"asset_sha256", "exporter_sha256"}}
    result = {"schema_version": "office-supplemental-display.v1",
              "authority": "PARTIAL_DISPLAY_CONTEXT", "display_only": True,
              "physical_authority_changed": False, "navigation_authority": "UNKNOWN",
              "whole_auditorium_complete": False, "source_geometry_modified": False,
              "source_sha256": config["source_sha256"],
              "scale_sha256": config["scale_sha256"],
              "source_archive_sha256": config["source_archive_sha256"],
              "office_inputs_sha256": config["office_inputs_sha256"],
              "auditorium_inputs_sha256": config["auditorium_inputs_sha256"],
              "config_policy_sha256": hashlib.sha256(encoded(policy)).hexdigest(),
              "exporter_sha256": sha(Path(__file__)),
              "blender_version": bpy.app.version_string,
              "blender_build_hash": bpy.app.build_hash.decode(),
              "evaluated_scene": config["evaluated_scene"],
              "model_revision": config["model_revision"], "units": "METRES",
              "geometry_local_units": "NATIVE_BU", "metres_per_bu": scale,
              "coordinate_frame": config["coordinate_frame"],
              "architecture": architecture, "geometries": definitions, "instances": instances,
              "bounds_metres": [[f(p[a] for p in world_points) for a in range(3)]
                                for f in (min, max)]}
    assert before == (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    raw = encoded(result) + b"\n"
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    assert len(raw) <= config["max_raw_bytes"] and len(packed) <= config["max_asset_bytes"]
    assert shutil.disk_usage(args.output.parent).free - len(packed) >= config["min_free_bytes"]
    with args.output.open("xb") as stream:
        stream.write(packed)
    print("DISPLAY_EXPORT_OK", json.dumps({"raw_bytes": len(raw), "gzip_bytes": len(packed),
          "asset_sha256": hashlib.sha256(packed).hexdigest(), "instances": len(instances),
          "geometries": len(definitions), "architecture_triangles": sum(
              len(m["triangles"]) for m in architecture), "source_unchanged": True}))


if __name__ == "__main__":
    main()

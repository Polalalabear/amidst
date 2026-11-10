"""Read-only, bounded Blender inventory. No rendering, saving or mesh export."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

EXPECTED = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
source = Path(bpy.data.filepath).resolve()


def fingerprint():
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stat = source.stat()
    return [digest, stat.st_size, stat.st_mtime_ns]


before = fingerprint()
assert before[0] == EXPECTED
assert shutil.disk_usage("/private/tmp").free > 2 * 1024**3
scene = bpy.context.scene
assert (scene.name, scene.frame_current, scene.frame_subframe) == ("Scene", 220, 0.0)
depsgraph = bpy.context.evaluated_depsgraph_get()
scale = 0.0247
lo, hi = [37.044, 38.4025, 0.47594758], [50.641, 57.6805, 4.2]
rows = []
for obj in sorted(scene.objects, key=lambda x: x.name):
    if obj.type not in {"MESH", "CAMERA", "EMPTY"}:
        continue
    points = (
        [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        if obj.type == "MESH"
        else [obj.matrix_world.translation]
    )
    bounds = [
        [min(p[a] for p in points) * scale for a in range(3)],
        [max(p[a] for p in points) * scale for a in range(3)],
    ]
    if not all(bounds[1][a] >= lo[a] and bounds[0][a] <= hi[a] for a in range(3)):
        continue
    row = dict(
        name=obj.name,
        type=obj.type,
        collections=[c.name for c in obj.users_collection],
        parent=obj.parent.name if obj.parent else None,
        phase1_annotation_only=bool(obj.get("phase1_annotation_only", False)),
        hide_render=obj.hide_render,
        hide_viewport=obj.hide_viewport,
        hide_get=obj.hide_get(),
        visible_get=obj.visible_get(),
        collection_flags=[
            dict(name=c.name, hide_render=c.hide_render, hide_viewport=c.hide_viewport)
            for c in obj.users_collection
        ],
        bounds_m=bounds,
        matrix_world=[list(r) for r in obj.matrix_world],
        instance_type=obj.instance_type,
        instance_collection=obj.instance_collection.name if obj.instance_collection else None,
    )
    if obj.type == "MESH":
        row.update(
            data=obj.data.name,
            vertices=len(obj.data.vertices),
            polygons=len(obj.data.polygons),
            modifiers=[(m.name, m.type, m.show_viewport, m.show_render) for m in obj.modifiers],
            materials=[m.name if m else None for m in obj.data.materials],
        )
        if any(c.name in {"Theatre Chair", "N1 Hamburg"} for c in obj.users_collection):
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles()
                row["evaluated_triangles"] = len(mesh.loop_triangles)
                row["evaluated_local_geometry_sha256"] = hashlib.sha256(
                    json.dumps(
                        {
                            "vertices": [list(v.co) for v in mesh.vertices],
                            "triangles": [list(t.vertices) for t in mesh.loop_triangles],
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                corners = [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
                row["evaluated_bounds_m"] = [
                    [min(p[a] for p in corners) * scale for a in range(3)],
                    [max(p[a] for p in corners) * scale for a in range(3)],
                ]
            finally:
                evaluated.to_mesh_clear()
    rows.append(row)
after = fingerprint()
assert before == after
result = dict(
    source_sha256=before[0],
    source_size=before[1],
    source_mtime_ns=before[2],
    source_unchanged=True,
    blender_version=bpy.app.version_string,
    scene=dict(name=scene.name, frame=scene.frame_current, subframe=scene.frame_subframe),
    unit_system=scene.unit_settings.system,
    unit_scale_length=scene.unit_settings.scale_length,
    roi_metres=[lo, hi],
    total_scene_objects=len(scene.objects),
    objects=rows,
)
result["diagnostic_profiles"] = {}
for label, names in [
    ("chair", ["Accoudoir", "Assise", "Dossier", "Fond Dossier", "Pied"]),
    (
        "lectern",
        ["Main Board", "inner boards", "Door.l", "door.r", "conference mic L", "conference mic R"],
    ),
]:
    profiles = []
    for name in names:
        obj = scene.objects[name]
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        stride = max(1, len(obj.data.edges) // 400)
        profiles.append(
            dict(
                name=name,
                edges=[
                    [[round(points[i][a] * scale, 6) for a in range(3)] for i in e.vertices]
                    for e in list(obj.data.edges)[::stride]
                ],
            )
        )
    result["diagnostic_profiles"][label] = profiles
raw = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
assert len(raw.encode()) < 1024 * 1024
output = Path(sys.argv[sys.argv.index("--") + 1])
with output.open("x") as stream:
    stream.write(raw)
print("AUDITORIUM_INVENTORY_OK", len(rows), "objects", len(raw.encode()), "bytes", before[0])

"""Blender-only read-only inspection of explicitly pinned static object names.

No actor lookup, animation, event, render, save, visibility/depth pass, or GT.
Run with --factory-startup --disable-autoexec and the pinned derived r004 file.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist", required=True)
    parser.add_argument("--allowlist-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    raw = Path(args.allowlist).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.allowlist_sha256:
        raise ValueError("Allowlist pin mismatch")
    allowed = json.loads(raw)
    source = Path(bpy.data.filepath)
    if hashlib.sha256(source.read_bytes()).hexdigest() != allowed["source_sha256"]:
        raise ValueError("Source pin mismatch")
    names = allowed["allowed_object_refs"]
    if len(names) != len(set(names)) or any(not isinstance(n, str) for n in names):
        raise ValueError("Invalid allowlist")

    def collection_paths(collection, name, parents=()):
        path = (*parents, {"name": collection.name, "hide_render": collection.hide_render})
        result = [list(path)] if name in collection.objects else []
        for child in collection.children:
            result.extend(collection_paths(child, name, path))
        return result

    rows = []
    for name in sorted(names):
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise ValueError("Missing/non-mesh static allowlist member")
        paths = collection_paths(bpy.context.scene.collection, name)
        vertices = [list(obj.matrix_world @ v.co) for v in obj.data.vertices]
        rows.append(
            {
                "object_ref": name,
                "hide_render": obj.hide_render,
                "hide_viewport": obj.hide_viewport,
                "hide_get": obj.hide_get(),
                "viewport_visible": obj.visible_get(),
                "collection_paths": paths,
                "render_collection_enabled": any(
                    all(not c["hide_render"] for c in path) for path in paths
                ),
                "matrix_world": [list(row) for row in obj.matrix_world],
                "raw_mesh_world_bounds_m": [
                    [min(v[i] for v in vertices) for i in range(3)],
                    [max(v[i] for v in vertices) for i in range(3)],
                ],
                "raw_mesh_vertex_count": len(vertices),
                "modifiers": [
                    {"type": m.type, "show_render": m.show_render} for m in obj.modifiers
                ],
            }
        )
    result = {
        "schema_version": "q-demo.r004-static-membership.v1",
        "source_sha256": allowed["source_sha256"],
        "allowlist_sha256": args.allowlist_sha256,
        "blender_version": bpy.app.version_string,
        "objects": rows,
        "gt_read": False,
        "source_saved": False,
        "rendered": False,
        "limits": [
            "Render flags and static membership only; not a visibility pass.",
            "Enabled geometry does not establish traversal or collision authority.",
            "No animation or actor data is inspected.",
        ],
    }
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    if hashlib.sha256(source.read_bytes()).hexdigest() != allowed["source_sha256"]:
        raise ValueError("Source changed during read-only inspection")
    print("R004_STATIC_MEMBERSHIP_EXPORTED", len(rows))


if __name__ == "__main__":
    main()

"""Post-freeze C7 annotation-height diagnostic; never a map derivation input."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    import bpy
    from mathutils import Vector

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists():
        raise FileExistsError(args.output)
    before_map = sha(args.map)
    data = json.loads(args.map.read_text())
    source = Path(bpy.data.filepath)
    before = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if before[0] != data["source_sha256"]:
        raise ValueError("SOURCE_MISMATCH")
    scale = data["config"]["metres_per_blender_unit"]
    rows = []
    for name in (
        "WALK_1F_OFFICE",
        "WALK_1F_AUDITORIUM",
        "WALK_1F_CORRIDOR_03",
        "OBSTACLE_1F_OFFICE_01",
    ):
        obj = bpy.context.scene.objects.get(name)
        if obj is None:
            rows.append({"object_id": name, "status": "MISSING"})
            continue
        corners = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
        safe_props = {
            k: obj[k]
            for k in obj.keys()
            if any(
                t in k.lower()
                for t in ("role", "floor", "annotation", "authority", "approval", "basis")
            )
            and isinstance(obj[k], (str, int, float, bool))
            and "path" not in k.lower()
        }
        rows.append(
            {
                "object_id": name,
                "z_bounds_native_bu": [min(p.z for p in corners), max(p.z for p in corners)],
                "z_bounds_m": [
                    min(p.z for p in corners) * scale,
                    max(p.z for p in corners) * scale,
                ],
                "source_properties": safe_props,
            }
        )
    if (
        before != (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
        or sha(args.map) != before_map
    ):
        raise RuntimeError("INPUT_CHANGED")
    result = {
        "schema_version": "office-demo.c7-annotation-origins-diagnostic.v1",
        "authority": "POST_FREEZE_DIAGNOSTIC_NOT_MAP_INPUT",
        "map_sha256": before_map,
        "source_sha256": before[0],
        "source_identity_unchanged": True,
        "source_saved": False,
        "render_executed": False,
        "producer_sha256": sha(__file__),
        "annotations": rows,
        "authoring_intent_for_z_25_bu": "UNKNOWN_NO_AUTHORING_RECORD_FOUND_IN_TRACKED_SCRIPTS",
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("C7_ANNOTATION_ORIGINS_DIAGNOSTIC_OK", flush=True)


if __name__ == "__main__":
    main()

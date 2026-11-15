"""Blender-only, read-only r004 character audit; never reads authored routes."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True

SOURCE_SHA = "466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b"
CATALOG_SHA = "3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source = Path(bpy.data.filepath)
    assert sha(source) == SOURCE_SHA
    assert sha(args.catalog) == CATALOG_SHA
    assert not args.output.exists(), "Refuse to overwrite evidence"
    root = bpy.data.objects["PRODUCTION_P1_ROOT"]
    parts = list(root.children_recursive)
    inv = root.matrix_world.inverted()
    rows = []
    for obj in sorted(parts, key=lambda obj: obj.name):
        assert obj.type == "MESH"
        matrix = inv @ obj.matrix_world
        vertices = [matrix @ vertex.co for vertex in obj.data.vertices]
        lower = [min(v[i] for v in vertices) for i in range(3)]
        upper = [max(v[i] for v in vertices) for i in range(3)]
        parent = list(range(len(vertices)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for edge in obj.data.edges:
            a, b = edge.vertices
            parent[find(a)] = find(b)
        rows.append({
            "part": obj.name.removeprefix("PRODUCTION_P1_"),
            "vertices": len(vertices), "edges": len(obj.data.edges),
            "polygons": len(obj.data.polygons),
            "connected_components": len({find(i) for i in range(len(vertices))}),
            "local_aabb_min_m": lower, "local_aabb_max_m": upper,
            "local_dimensions_m": [b - a for a, b in zip(lower, upper)],
            "vertex_groups": [group.name for group in obj.vertex_groups],
            "modifiers": [modifier.type for modifier in obj.modifiers],
            "parent_type": obj.parent_type,
            "materials": [material.name if material else None for material in obj.data.materials],
        })
    armatures_before = sum(obj.type == "ARMATURE" for obj in bpy.data.objects)
    from n6_character_rig import articulation_probe, build
    rig, meshes = build()
    probes = articulation_probe(rig, meshes)
    assert all(row["max_skin_error_m"] < 1e-5 for row in probes)
    report = {
        "schema": "amidst.n6-character-audit.v1",
        "source_sha256_before": SOURCE_SHA,
        "source_sha256_after": sha(source),
        "catalog_sha256_before": CATALOG_SHA,
        "catalog_sha256_after": sha(args.catalog),
        "blender_version": bpy.app.version_string,
        "blender_build_hash": bpy.app.build_hash.decode(),
        "coordinate_system": "Character root-local, Z-up, +X forward; meters",
        "scene_unit_system": bpy.context.scene.unit_settings.system,
        "scene_unit_scale": bpy.context.scene.unit_settings.scale_length,
        "armatures_in_source": armatures_before,
        "character_parts": rows,
        "prototype_bones": len(rig.data.bones),
        "articulation_probes": probes,
        "feasibility": "FEASIBLE_ARTICULATED_MANNEQUIN",
        "limitations": ["Rigid one-bone weights; no continuous skin or clothing deformation",
                       "Knee/elbow caps match the #529 adapter, not a photorealistic human",
                       "Running gait and visual naturalness require subsequent clip/viewer verification"],
        "source_saved": False, "render_invoked": False,
        "routes_visibility_depth_exported": False,
    }
    assert report["source_sha256_after"] == SOURCE_SHA
    assert report["catalog_sha256_after"] == CATALOG_SHA
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

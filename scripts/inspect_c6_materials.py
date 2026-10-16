"""Read source material properties for C6 ray occluders; never render or save."""

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

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists() or args.output.suffix != ".json":
        raise ValueError("OUTPUT_MUST_BE_NEW_JSON")
    source = Path(bpy.data.filepath)
    before = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    data = json.loads(args.input.read_text())
    if before[0] != data["source_sha256"]:
        raise ValueError("SOURCE_HASH_MISMATCH")
    records = (
        data["prescreen"]["legacy_candidate_audit"]
        + data["prescreen"]["diagnostic_candidates_not_for_benchmark"]
        + [r for r in data["candidates"] if r["role"] == "VISIBLE_BLIND_VISIBLE"]
    )
    names = sorted({o["object"] for r in records for o in r["transparent_occluders"]})
    objects = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError("OCCLUDER_NOT_FOUND: " + name)
        materials = []
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None:
                continue
            sockets, special = [], []
            trees = [mat.node_tree] if mat.use_nodes and mat.node_tree else []
            visited = set()
            while trees:
                tree = trees.pop()
                if tree.as_pointer() in visited:
                    continue
                visited.add(tree.as_pointer())
                for node in tree.nodes:
                    if node.type == "GROUP" and node.node_tree:
                        trees.append(node.node_tree)
                    if node.type in {
                        "BSDF_TRANSPARENT",
                        "BSDF_GLASS",
                        "BSDF_REFRACTION",
                        "HOLDOUT",
                    }:
                        special.append(node.type)
                    for key in ("Alpha", "Transmission Weight", "Transmission"):
                        socket = node.inputs.get(key)
                        if socket is not None:
                            value = socket.default_value
                            sockets.append(
                                {
                                    "node_type": node.type,
                                    "input": key,
                                    "is_linked": socket.is_linked,
                                    "default_value": value
                                    if isinstance(value, (int, float))
                                    else None,
                                }
                            )
            explicit = (
                mat.diffuse_color[3] < 0.999
                or bool(special)
                or any(
                    s["is_linked"]
                    or (
                        s["default_value"] is not None
                        and (
                            s["default_value"] < 0.999
                            if s["input"] == "Alpha"
                            else s["default_value"] > 0.001
                        )
                    )
                    for s in sockets
                )
            )
            materials.append(
                {
                    "name": mat.name,
                    "diffuse_alpha": mat.diffuse_color[3],
                    "blend_method": getattr(mat, "blend_method", None),
                    "surface_render_method": getattr(mat, "surface_render_method", None),
                    "special_shader_nodes": sorted(set(special)),
                    "sockets": sockets,
                    "explicit_alpha_or_transmission_or_linked_unknown": explicit,
                }
            )
        objects.append(
            {
                "object": name,
                "materials": materials,
                "dimensions_m": [
                    v * data["config"]["metres_per_blender_unit"] for v in obj.dimensions
                ],
            }
        )
    after = (sha(source), source.stat().st_size, source.stat().st_mtime_ns)
    if after != before:
        raise RuntimeError("SOURCE_CHANGED")
    result = {
        "schema_version": "c6-material-properties.v1",
        "source_sha256": before[0],
        "prescreen_sha256": sha(args.input),
        "producer_sha256": sha(__file__),
        "source_unchanged": True,
        "source_saved": False,
        "render_executed": False,
        "objects": objects,
        "warning": "Non-opaque blend configuration alone does not prove transparency; "
        "object-wide slot presence does not identify the material on a hit face. "
        "Workbench OBJECT-color renders use an opaque snapshot policy.",
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("C6_MATERIAL_PROPERTIES_OK " + str(len(objects)))


if __name__ == "__main__":
    main()

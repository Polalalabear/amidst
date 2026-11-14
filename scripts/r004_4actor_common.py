"""Producer-only four-actor appearance; never import from inference."""

import colorsys
import json
from pathlib import Path

B_BAG = {"center": (0, -0.19, 0.95), "dimensions": (0.12, 0.08, 0.18), "rgb": (0.045, 0.065, 0.075)}
SOURCE_SHA = "466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b"
CATALOG_SHA = "3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f"


def configure_people(bpy, repo):
    from mathutils import Matrix
    from render_r004_d124 import make_appearance

    scene = bpy.context.scene
    scene.frame_set(1)
    root = bpy.data.objects["PRODUCTION_P1_ROOT"]
    originals = [root] + list(root.children_recursive)
    assert len(originals) == 17 and all(o.parent == root for o in originals if o != root)
    for obj in bpy.data.objects:
        if obj.name.startswith("PRODUCTION_"):
            obj.animation_data_clear()
            obj.hide_render = not obj.name.startswith("PRODUCTION_P1_")
    bpy.context.view_layer.update()
    base = {o: root.matrix_world.inverted() @ o.matrix_world for o in originals}
    people = {"T": {"root": root, "objects": list(originals)}}
    for actor, hsv in [("A", None), ("B", (0.012, 0.75, 0.65)), ("C", (0.62, 0.75, 0.65))]:
        copies = {}
        shirt = None
        if hsv:
            shirt = material(bpy, actor + "_SHIRT", colorsys.hsv_to_rgb(*hsv))
        pants = material(
            bpy,
            actor + "_PANTS",
            {"A": (0.65, 0.65, 0.65), "B": (0.035, 0.055, 0.14), "C": (0.65, 0.58, 0.4)}[actor],
        )
        for obj in originals:
            new = obj.copy()
            new.name = "V22_" + actor + "_" + obj.name
            new.animation_data_clear()
            if obj.type == "MESH":
                new.data = obj.data.copy()
            scene.collection.objects.link(new)
            copies[obj] = new
        for obj, new in copies.items():
            new.parent = copies.get(obj.parent)
            if obj.parent:
                new.matrix_parent_inverse = Matrix.Identity(4)
                new.matrix_basis = base[obj]
            else:
                new.matrix_world = obj.matrix_world.copy()
            new.hide_render = False
            if obj.type == "MESH":
                for i, mat in enumerate(new.data.materials):
                    if mat and "SHIRT" in mat.name and shirt:
                        new.data.materials[i] = shirt
                    elif mat and mat.name == "MAT_BOTH_PERSONS_NEUTRAL":
                        new.data.materials[i] = pants
        people[actor] = {"root": copies[root], "objects": list(copies.values())}
    before = set(bpy.data.objects)
    cfg = json.loads((Path(repo) / "configs/q1q5/producers/r004_d124_v1.json").read_text())
    make_appearance(bpy, root, cfg["appearance"], "+X")
    people["T"]["objects"].extend(o for o in bpy.data.objects if o not in before)
    bpy.ops.mesh.primitive_cube_add(size=1)
    bag = bpy.context.object
    bag.name = "V22_B_SIDEBAG"
    bag.parent = people["B"]["root"]
    bag.location = B_BAG["center"]
    bag.scale = B_BAG["dimensions"]
    bag.data.materials.append(material(bpy, "B_BAG", B_BAG["rgb"]))
    people["B"]["objects"].append(bag)
    bpy.context.view_layer.update()
    return people


def material(bpy, name, rgb):
    m = bpy.data.materials.new("V22_" + name)
    m.use_nodes = True
    m.diffuse_color = (*rgb, 1)
    node = m.node_tree.nodes["Principled BSDF"]
    node.inputs["Base Color"].default_value = m.diffuse_color
    node.inputs["Roughness"].default_value = 0.8
    return m

"""Read-only Blender mesh audit for #516; never renders or saves a blend.

All outputs are producer/design evidence. They must not enter inference or safe bundles.
"""

import argparse
import colorsys
import hashlib
import json
import math
from pathlib import Path
import resource
import sys

sys.dont_write_bytecode = True
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def audit(repo, scenario, output, check_recording_end=False):
    sys.path.insert(0, str(repo / "scripts"))
    from render_r004_d124 import make_appearance, route_pose
    from r004_4actor_common import B_BAG

    source = Path(bpy.data.filepath)
    before = sha(source)
    assert before == "466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b"
    catalog_path = Path(
        "/Users/polalabear/amidst/local/data/r004-build-v2-20261021/safe_static/cameras.json"
    )
    assert sha(catalog_path) == "3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f"
    cameras = {c["camera_id"]: c for c in json.loads(catalog_path.read_text())["cameras"]}
    doc = json.loads(scenario.read_text())
    scene = bpy.context.scene
    scene.frame_set(1)
    original_mats = {m.name: list(m.diffuse_color) for m in bpy.data.materials}
    for obj in bpy.data.objects:
        if obj.name.startswith("PRODUCTION_"):
            obj.animation_data_clear()
            obj.hide_render = not obj.name.startswith("PRODUCTION_P1_")
    root = bpy.data.objects["PRODUCTION_P1_ROOT"]
    originals = [root] + list(root.children_recursive)
    bpy.context.view_layer.update()
    base = {o: root.matrix_world.inverted() @ o.matrix_world for o in originals}
    clone_rows = []
    for actor, hsv in [("A", None), ("B", (0.012, 0.75, 0.65)), ("C", (0.62, 0.75, 0.65))]:
        copies = {}
        shirt = None
        if hsv:
            shirt = bpy.data.materials.new("AUDIT_" + actor + "_SHIRT")
            shirt.use_nodes = True
            shirt.diffuse_color = (*colorsys.hsv_to_rgb(*hsv), 1)
            shirt.node_tree.nodes["Principled BSDF"].inputs[
                "Base Color"
            ].default_value = shirt.diffuse_color
        pants = bpy.data.materials.new("AUDIT_" + actor + "_PANTS")
        pants.use_nodes = True
        pants.diffuse_color = {
            "A": (0.65, 0.65, 0.65, 1),
            "B": (0.035, 0.055, 0.14, 1),
            "C": (0.65, 0.58, 0.4, 1),
        }[actor]
        pants.node_tree.nodes["Principled BSDF"].inputs[
            "Base Color"
        ].default_value = pants.diffuse_color
        for obj in originals:
            new = obj.copy()
            new.name = "AUDIT_" + actor + "_" + obj.name
            new.animation_data_clear()
            if obj.type == "MESH":
                new.data = obj.data.copy()
            scene.collection.objects.link(new)
            copies[obj] = new
        for obj, new in copies.items():
            new.parent = copies.get(obj.parent)
            new.matrix_world = obj.matrix_world.copy()
            if obj.type == "MESH":
                for i, mat in enumerate(new.data.materials):
                    if mat and "SHIRT" in mat.name and shirt:
                        new.data.materials[i] = shirt
                    elif mat and mat.name == "MAT_BOTH_PERSONS_NEUTRAL":
                        new.data.materials[i] = pants
        clone_rows.append(
            {
                "actor_id": actor,
                "objects": len(copies),
                "meshes": sum(o.type == "MESH" for o in copies),
                "independent_meshes": all(
                    n.data != o.data for o, n in copies.items() if o.type == "MESH"
                ),
                "same_red_material": actor == "A"
                and copies[bpy.data.objects["PRODUCTION_P1_TORSO"]].data.materials[0]
                == bpy.data.objects["PRODUCTION_P1_TORSO"].data.materials[0],
            }
        )
    cfg = json.loads((repo / "configs/q1q5/producers/r004_d124_v1.json").read_text())
    make_appearance(bpy, root, cfg["appearance"], "+X")
    # Static opaque surfaces only; no actor can supply an occlusion pass.
    vertices, triangles, tri_names, polygons, boxes = [], [], [], [], []
    poly_map = {}
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.data.objects:
        if (
            obj.type != "MESH"
            or obj.hide_render
            or obj.name.startswith(("PRODUCTION_", "AUDIT_", "D124_"))
        ):
            continue
        eo = obj.evaluated_get(deps)
        mesh = eo.to_mesh()
        vv = [eo.matrix_world @ v.co for v in mesh.vertices]
        offset = len(vertices)
        vertices.extend(vv)
        mesh.calc_loop_triangles()
        for t in mesh.loop_triangles:
            triangles.append(tuple(offset + i for i in t.vertices))
            tri_names.append((obj.name, t.polygon_index))
        for face in mesh.polygons:
            pts = [vv[i] for i in face.vertices]
            normal = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if normal.length < 1e-8:
                continue
            normal.normalize()
            # Only planar convex polygons provide a full-triangle shadow proof.
            if any(abs((p - pts[0]).dot(normal)) > 1e-5 for p in pts):
                continue
            turns = [
                (pts[(i + 1) % len(pts)] - pts[i])
                .cross(pts[(i + 2) % len(pts)] - pts[(i + 1) % len(pts)])
                .dot(normal)
                for i in range(len(pts))
            ]
            if not (all(v >= -1e-7 for v in turns) or all(v <= 1e-7 for v in turns)):
                continue
            polygons.append((obj.name, pts, normal))
            poly_map[(obj.name, face.index)] = (obj.name, pts, normal)
        if obj.name.startswith("OBSTACLE_SCREEN_"):
            lo = Vector([min(p[i] for p in vv) for i in range(3)])
            hi = Vector([max(p[i] for p in vv) for i in range(3)])
            assert all(
                all(abs(p[i] - lo[i]) < 1e-5 or abs(p[i] - hi[i]) < 1e-5 for i in range(3))
                for p in vv
            )
            boxes.append((obj.name, lo, hi))
        eo.to_mesh_clear()
    bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    derived_by_object = {}
    proof_file = output.parent / "occlusion_faces.json"
    proof = json.loads(proof_file.read_text())
    assert proof["source_blend_sha256"] == before
    for face in proof["faces"]:
        pts = [Vector(v) for v in face["vertices_world_m"]]
        normal = (pts[1] - pts[0]).cross(pts[2] - pts[0]).normalized()
        derived_by_object.setdefault(face["object_ref"], []).append((pts, normal))

    def box_blocks(origin, point, low, high):
        d = point - origin
        near, far = 0.0, 1.0
        for i in range(3):
            if abs(d[i]) < 1e-12:
                if origin[i] < low[i] or origin[i] > high[i]:
                    return False
            else:
                a, b = sorted(((low[i] - origin[i]) / d[i], (high[i] - origin[i]) / d[i]))
                near, far = max(near, a), min(far, b)
        return near < far and far > 1e-6 and near < 1 - 1e-6

    def face_blocks(origin, point, pts, n):
        d = point - origin
        den = n.dot(d)
        if abs(den) < 1e-12:
            return False
        t = n.dot(pts[0] - origin) / den
        if not 1e-7 < t < 1 - 1e-7:
            return False
        hit = origin + t * d
        vals = [
            (pts[(i + 1) % len(pts)] - pts[i]).cross(hit - pts[i]).dot(n) for i in range(len(pts))
        ]
        return all(v >= -1e-7 for v in vals) or all(v <= 1e-7 for v in vals)

    camera_checks = []
    for name, c in cameras.items():
        obj = bpy.data.objects[name]
        camera_checks.append(
            {
                "camera_id": name,
                "matrix_error_max": max(
                    abs(obj.matrix_world[i][j] - c["camera_to_world"][i][j])
                    for i in range(4)
                    for j in range(4)
                ),
                "fx_error": abs(960 * obj.data.lens / obj.data.sensor_width - c["fx"]),
            }
        )
    results = []
    for run in doc["runs"]:
        for actor in run["actors"]:
            if actor["actor_id"] == "T":
                continue
            for kind, index in [("first", 0), ("last", -1)]:
                wp = actor["waypoints"][index]
                if kind == "last" and wp["t_us"] == run["duration_us"] and not check_recording_end:
                    results.append(
                        {
                            "run_id": run["run_id"],
                            "actor_id": actor["actor_id"],
                            "kind": kind,
                            "time_us": wp["t_us"],
                            "xy": wp["xy"],
                            "status": "PASS_STAYS_TO_RECORDING_END",
                            "cameras": [],
                        }
                    )
                    continue
                wps = [
                    {
                        "planned_source_time_us": w["t_us"],
                        "foot_anchor_world_m": [
                            *w["xy"],
                            w.get("z_m", -0.06 if w["xy"][0] < -3.2 else 0),
                        ],
                    }
                    for w in actor["waypoints"]
                ]
                pos, yaw = route_pose(wps, wp["t_us"])
                pose = Matrix.Translation(Vector(pos)) @ Matrix.Rotation(yaw, 4, "Z")
                tris = []
                for obj in originals:
                    if obj.type != "MESH":
                        continue
                    obj.data.calc_loop_triangles()
                    pts = [pose @ base[obj] @ v.co for v in obj.data.vertices]
                    tris.extend([[pts[i] for i in f.vertices] for f in obj.data.loop_triangles])
                if actor["actor_id"] == "B":
                    from itertools import product

                    center, dims = B_BAG["center"], B_BAG["dimensions"]
                    bag_vertices = [
                        pose @ Vector([center[i] + signs[i] * dims[i] / 2 for i in range(3)])
                        for signs in product((-1, 1), repeat=3)
                    ]
                    for face in [
                        (0, 1, 3, 2),
                        (4, 6, 7, 5),
                        (0, 4, 5, 1),
                        (2, 3, 7, 6),
                        (0, 2, 6, 4),
                        (1, 5, 7, 3),
                    ]:
                        tris.extend(
                            [
                                [
                                    bag_vertices[face[0]],
                                    bag_vertices[face[j]],
                                    bag_vertices[face[j + 1]],
                                ]
                                for j in (1, 2)
                            ]
                        )
                row = {
                    "run_id": run["run_id"],
                    "actor_id": actor["actor_id"],
                    "kind": kind,
                    "time_us": wp["t_us"],
                    "xy": wp["xy"],
                    "cameras": [],
                }
                for name in run["render_camera_ids"]:
                    cam = cameras[name]
                    inv = Matrix(cam["camera_to_world"]).inverted()
                    origin = Vector([cam["camera_to_world"][i][3] for i in range(3)])

                    # Clip triangles against all six camera-frustum half-spaces.
                    def plane_values(p):
                        q = inv @ p
                        d = -q.z
                        return [
                            d - cam["clip_start"],
                            cam["clip_end"] - d,
                            cam["fx"] * q.x + cam["cx"] * d,
                            (cam["width"] - cam["cx"]) * d - cam["fx"] * q.x,
                            cam["cy"] * d - cam["fy"] * q.y,
                            (cam["height"] - cam["cy"]) * d + cam["fy"] * q.y,
                        ]

                    def clip(poly):
                        for k in range(6):
                            new = []
                            for a, b in zip(poly, poly[1:] + poly[:1]):
                                da, db = plane_values(a)[k], plane_values(b)[k]
                                if da >= 0:
                                    new.append(a)
                                if (da < 0) != (db < 0):
                                    new.append(a + (b - a) * (da / (da - db)))
                            poly = new
                            if not poly:
                                break
                        return poly

                    inside = []
                    for tri in tris:
                        clipped = clip(tri)
                        inside.extend(
                            [
                                [clipped[0], clipped[i], clipped[i + 1]]
                                for i in range(1, len(clipped) - 1)
                            ]
                        )
                    witness, hidden_by, unknown = None, set(), 0
                    ray_cache = {}

                    # A convex opaque face/box's shadow volume is convex: if all triangle
                    # vertices are behind the same blocker, the entire triangle is hidden.
                    # Split unresolved triangles; never claim pass from samples alone.
                    def check_tri(tri, level=0):
                        nonlocal witness, unknown
                        for blocker, low, high in boxes:
                            if all(box_blocks(origin, p, low, high) for p in tri):
                                hidden_by.add(blocker)
                                return
                        center = sum(tri, Vector()) / 3
                        candidates = set()
                        for p in tri + [center]:
                            key = tuple(p)
                            if key not in ray_cache:
                                direction = p - origin
                                ray_cache[key] = bvh.ray_cast(
                                    origin, direction.normalized(), max(0, direction.length - 1e-4)
                                )
                            hit = ray_cache[key]
                            if hit[0] is None:
                                q = inv @ p
                                witness = {
                                    "world_m": list(p),
                                    "pixel_xy": [
                                        cam["cx"] + cam["fx"] * q.x / -q.z,
                                        cam["cy"] - cam["fy"] * q.y / -q.z,
                                    ],
                                }
                                return
                            candidates.add(tri_names[hit[2]])
                        for name in {key[0] for key in candidates}:
                            for pts, n in derived_by_object.get(name, []):
                                if all(face_blocks(origin, p, pts, n) for p in tri):
                                    hidden_by.add(name)
                                    return
                        for key in candidates:
                            if key in poly_map:
                                blocker, pts, n = poly_map[key]
                                if all(face_blocks(origin, p, pts, n) for p in tri):
                                    hidden_by.add(blocker)
                                    return
                        if level == 4:
                            unknown += 1
                            return
                        a, b, c = tri
                        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
                        for child in [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]:
                            check_tri(child, level + 1)
                            if witness:
                                return

                    for tri in inside:
                        check_tri(tri)
                        if witness:
                            break
                    status = "FAIL" if witness else "UNKNOWN" if unknown else "PASS"
                    row["cameras"].append(
                        {
                            "camera_id": name,
                            "status": status,
                            "triangles_in_frustum": len(inside),
                            "reason": "VISIBLE_MESH_WITNESS"
                            if witness
                            else "UNRESOLVED_SUBTRIANGLES"
                            if unknown
                            else "CONVEX_STATIC_OCCLUSION_PROOF"
                            if inside
                            else "OUT_OF_FRUSTUM",
                            "blockers": sorted(hidden_by),
                            "unknown_triangle_count": unknown,
                            "visible_witness": witness,
                        }
                    )
                states = {c["status"] for c in row["cameras"]}
                row["status"] = (
                    "FAIL" if "FAIL" in states else "UNKNOWN" if "UNKNOWN" in states else "PASS"
                )
                results.append(row)
    assert all(list(bpy.data.materials[n].diffuse_color) == c for n, c in original_mats.items())
    output.write_text(
        json.dumps(
            {
                "schema": "amidst.r004-v21-mesh-audit.v1",
                "scenario_sha256": sha(scenario),
                "source_sha256_before": before,
                "source_sha256_after": sha(source),
                "catalog_sha256": sha(catalog_path),
                "camera_checks": camera_checks,
                "clone_checks": clone_rows,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "rendered": False,
                "blend_saved": False,
                "gt_read": False,
                "actor_mutual_occlusion_used": False,
                "endpoints": results,
            },
            indent=2,
        )
        + "\n"
    )
    for r in results:
        print(
            r["run_id"],
            r["actor_id"],
            r["kind"],
            r["status"],
            [
                (x["camera_id"], x["status"], x["reason"], x["visible_witness"])
                for x in r["cameras"]
            ],
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--scenario", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--check-recording-end", action="store_true")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    audit(args.repo, args.scenario, args.out, args.check_recording_end)

"""Natural-walk endpoints: #523 convex occlusion proof, actual approved posed meshes. Never renders/saves a blend.

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


def audit(repo, scenario, output, baseline_snapshot, geometry, check_recording_end=False):
    sys.path.insert(0, str(repo / "scripts"))
    import importlib.util
    from render_r004_natural_walk_sample import Person, SOURCE_SHA, CATALOG_SHA, APPEARANCE_SHA
    from r004_natural_walk import WalkPlan
    source=Path(bpy.data.filepath)
    before=sha(source)
    assert before==SOURCE_SHA
    catalog_path=Path.home()/"amidst/local/data/r004-build-v2-20261021/safe_static/cameras.json"
    assert sha(catalog_path)==CATALOG_SHA
    cameras={c["camera_id"]:c for c in json.loads(catalog_path.read_text())["cameras"]}
    doc=json.loads(scenario.read_text())
    scene=bpy.context.scene
    scene.frame_set(1)
    original_mats={m.name:list(m.diffuse_color) for m in bpy.data.materials}
    appearance=baseline_snapshot/"scripts/r004_4actor_common.py"
    assert sha(appearance)==APPEARANCE_SHA
    spec=importlib.util.spec_from_file_location("endpoint_appearance",appearance)
    common=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    people=common.configure_people(bpy,repo)
    adapters={who:Person(p) for who,p in people.items()}
    mesh_data={who:{o.data for o in p['objects'] if o.type=='MESH'} for who,p in people.items()}
    clone_rows=[{"actor_id":who,"objects":len(p["objects"]),
                 "independent_meshes":all(not (mesh_data[who]&data) for other,data in mesh_data.items() if other!=who),
                 "torso_materials":[m.name for m in adapters[who].parts['TORSO'].data.materials]}
                for who,p in people.items() if who!="T"]
    assert all(r['independent_meshes'] for r in clone_rows)
    floors=json.loads(geometry.read_text())["floors"]
    plans={}
    for run in doc["runs"]:
        for actor in run["actors"]:
            points=[]
            for w in actor["waypoints"]:
                heights=[f["top_z_m"] for f in floors if min(f["x_m"])<=w["xy"][0]<=max(f["x_m"]) and min(f["y_m"])<=w["xy"][1]<=max(f["y_m"])]
                points.append({**w,"z_m":w.get("z_m",max(heights) if heights else 0)})
            plans[(run["run_id"],actor["actor_id"])]=WalkPlan(points)
    # Static opaque surfaces only; no actor can supply an occlusion pass.
    vertices, triangles, tri_names, polygons, boxes = [], [], [], [], []
    poly_map = {}
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.data.objects:
        if (
            obj.type != "MESH"
            or obj.hide_render
            or obj.name.startswith(("PRODUCTION_", "V22_", "NATURAL_", "D124_"))
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
                who=actor["actor_id"]
                adapters[who].apply(plans[(run["run_id"],who)].pose(wp["t_us"]/1e6))
                bpy.context.view_layer.update()
                tris=[]
                for obj in people[who]["objects"]:
                    if obj.type!="MESH":
                        continue
                    obj.data.calc_loop_triangles()
                    pts=[obj.matrix_world@v.co for v in obj.data.vertices]
                    tris.extend([[pts[i] for i in tri.vertices] for tri in obj.data.loop_triangles])
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
                "schema": "amidst.r004-natural-walk-endpoint-audit.v1",
                "scenario_sha256": sha(scenario),
                "gait_code_sha256":sha(repo/"scripts/r004_natural_walk.py"),
                "pose_producer_sha256":sha(repo/"scripts/render_r004_natural_walk_sample.py"),
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
    assert sha(source)==before
    assert all(c["matrix_error_max"]==0 and c["fx_error"]==0 for c in camera_checks)
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

    assert all(r["status"].startswith("PASS") for r in results), "endpoint mesh visibility FAIL/UNKNOWN"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--scenario", type=Path, required=True)
    p.add_argument("--baseline-snapshot",type=Path,required=True)
    p.add_argument("--geometry",type=Path,required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--check-recording-end", action="store_true")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    audit(args.repo, args.scenario, args.out, args.baseline_snapshot, args.geometry, args.check_recording_end)

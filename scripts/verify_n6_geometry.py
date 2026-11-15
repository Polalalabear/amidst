"""Blender round-trip comparison of all exported static source surfaces."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector, kdtree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_n6_character import CATALOG_SHA, SOURCE_SHA, sha


def area(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    result = 0.
    for triangle in mesh.loop_triangles:
        a,b,c = (obj.matrix_world@mesh.vertices[i].co for i in triangle.vertices)
        result += (b-a).cross(c-a).length*.5
    return result


def tree(points):
    result = kdtree.KDTree(len(points))
    for i,p in enumerate(points):
        result.insert(p,i)
    result.balance()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    assert sha(bpy.data.filepath)==SOURCE_SHA and sha(args.catalog)==CATALOG_SHA
    originals = {o.name:o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render
                 and not o.name.startswith('PRODUCTION_')}
    assert len(originals)==15
    for obj in originals.values():
        for modifier in obj.modifiers:
            modifier.show_viewport = modifier.show_render
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_meshes = {obj:bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph),
                        preserve_all_data_layers=True,depsgraph=depsgraph) for obj in originals.values()}
    for obj,data in evaluated_meshes.items():
        obj.data = data
        obj.modifiers.clear()
    bpy.context.view_layer.update()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.assets/'scene.glb'))
    imported = set(bpy.data.objects)-before
    rows = []
    all_points = []
    for obj in imported:
        if obj.type!='MESH':
            continue
        name = obj.get('sourceComponent')
        assert name in originals and obj.get('n6Collider') is True
        source = originals[name]
        a = [source.matrix_world@v.co for v in source.data.vertices]
        b = [obj.matrix_world@v.co for v in obj.data.vertices]
        a_tree,b_tree = tree(a),tree(b)
        distance = max([a_tree.find(p)[2] for p in b]+[b_tree.find(p)[2] for p in a])
        area_error = abs(area(source)-area(obj))
        assert distance<1e-5 and area_error<1e-3,(name,distance,area_error)
        rows.append(dict(component=name,bidirectional_vertex_error_m=distance,surface_area_error_m2=area_error))
        all_points.extend(a)
    assert len(rows)==15
    catalog = json.loads(args.catalog.read_text())
    converted = json.loads((args.assets/'cameras.three.json').read_text())
    camera_rows = {c['camera_id']:c for c in converted['cameras']}
    basis = np.array([[1.,0.,0.,0.],[0.,0.,1.,0.],[0.,-1.,0.,0.],[0.,0.,0.,1.]])
    camera_errors = []
    for camera in catalog['cameras']:
        row = camera_rows[camera['camera_id']]
        source_inv = np.linalg.inv(np.array(camera['camera_to_world'],dtype=np.float64))
        target_inv = np.array(row['world_to_camera'],dtype=np.float64)
        errors = []
        for point in all_points:
            world = np.array([*point,1.],dtype=np.float64)
            p = source_inv@world
            if -p[2]<camera['clip_start']:
                continue
            u = camera['cx']+camera['fx']*p[0]/-p[2]
            v = camera['cy']-camera['fy']*p[1]/-p[2]
            q = np.array(row['projection_matrix'])@(target_inv@basis@world)
            uv = ((q[0]/q[3]+1)*row['width']/2,(1-q[1]/q[3])*row['height']/2)
            errors.append(math.hypot(u-uv[0],v-uv[1]))
        assert errors and max(errors)<.05,(camera['camera_id'],max(errors))
        camera_errors.append(dict(camera_id=camera['camera_id'],projected_vertices=len(errors),max_error_px=max(errors)))
    assert sha(bpy.data.filepath)==SOURCE_SHA and sha(args.catalog)==CATALOG_SHA
    report = dict(schema='amidst.n6-static-roundtrip.v1',status='PASS',components=sorted(rows,key=lambda r:r['component']),
                  cameras=camera_errors,source_sha256=SOURCE_SHA,catalog_sha256=CATALOG_SHA,
                  source_saved=False,video_rendered=False,index_built=False)
    (args.assets/'verification/GEOMETRY_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],components=len(rows),cameras=len(camera_errors),
                         max_vertex_error_m=max(r['bidirectional_vertex_error_m'] for r in rows),
                         max_camera_error_px=max(r['max_error_px'] for r in camera_errors)),indent=2))


if __name__=='__main__':
    main()

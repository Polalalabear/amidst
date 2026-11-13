"""Memory-only #516 natural-walk sample. Keeps the v2.2 root route and source blend.

This producer consumes the exact published #523 appearance snapshot. Its private
mesh probe is not an inference input. It does not save/copy a blend or build an index.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from r004_natural_walk import WalkPlan

SOURCE_SHA='466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b'
CATALOG_SHA='3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f'
SCENARIO_SHA='14fc3a1eee450923ce799e2e6ca32adae99d8f25afc2dce7a210fb78776eef6c'
APPEARANCE_SHA='e893fd48f99e93d0d68d9eb0bbfa9f34d93abd423c26530b596531e09ff9baed'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def dump(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def bvh(objects):
    from mathutils.bvhtree import BVHTree
    verts,faces=[],[]
    for obj in objects:
        if obj.type!='MESH':
            continue
        start=len(verts)
        verts.extend(obj.matrix_world@v.co for v in obj.data.vertices)
        faces.extend(tuple(start+i for i in poly.vertices) for poly in obj.data.polygons)
    return BVHTree.FromPolygons(verts,faces,all_triangles=False)


class Person:
    def __init__(self,person):
        from mathutils import Matrix
        self.root=person['root']
        self.objects=person['objects']
        inv=self.root.matrix_world.inverted()
        self.base={o:inv@o.matrix_world for o in self.objects if o!=self.root}
        self.parts={o.name.split('PRODUCTION_P1_')[-1]:o for o in self.base if 'PRODUCTION_P1_' in o.name}
        needed=['HEAD','NECK','TORSO','PELVIS']+[side+'_'+part for side in ['L','R']
                 for part in ['THIGH','SHIN','SHOE','UPPER_ARM','FOREARM','HAND']]
        if sorted(self.parts)!=sorted(needed):
            raise ValueError('unexpected source mesh parts')
        self.identity=Matrix.Identity(4)

    def segment(self,name,a,b):
        from mathutils import Matrix,Vector
        obj=self.parts[name]
        old=self.base[obj].to_3x3().to_4x4()
        old_axis=old.to_3x3()@Vector((0,0,1))
        delta=Vector(b)-Vector(a)
        rot=old_axis.normalized().rotation_difference(delta.normalized()).to_matrix().to_4x4()
        stretch=Matrix.Diagonal((1.,1.,delta.length/old_axis.length,1.))
        obj.matrix_basis=Matrix.Translation((Vector(a)+Vector(b))*.5)@rot@old@stretch

    def apply(self,pose):
        from mathutils import Matrix,Vector
        self.root.location=pose['root']
        self.root.rotation_euler=(0,0,pose['yaw'])
        pivot=Vector((0,0,.88))
        body=Matrix.Translation((0,0,pose['body_z']))@Matrix.Translation(pivot)@Matrix.Rotation(pose['body_pitch'],4,'Y')@Matrix.Translation(-pivot)
        for obj,base in self.base.items():
            obj.matrix_parent_inverse=self.identity
            obj.matrix_basis=body@base
        for side,s in [('L',1),('R',-1)]:
            leg=pose['legs'][s]
            arm=pose['arms'][s]
            self.segment(side+'_THIGH',leg['hip'],leg['knee'])
            self.segment(side+'_SHIN',leg['knee'],leg['ankle'])
            self.segment(side+'_UPPER_ARM',arm['shoulder'],arm['elbow'])
            self.segment(side+'_FOREARM',arm['elbow'],arm['wrist'])
            for name,pos,yaw in [(side+'_SHOE',leg['foot'],leg['yaw']),(side+'_HAND',arm['wrist'],0)]:
                obj=self.parts[name]
                linear=self.base[obj].to_3x3().to_4x4()
                obj.matrix_basis=Matrix.Translation(Vector(pos))@Matrix.Rotation(yaw,4,'Z')@linear


def main():
    import bpy
    from mathutils import Matrix
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--baseline-snapshot',type=Path,required=True)
    p.add_argument('--scenario',type=Path,required=True)
    p.add_argument('--geometry',type=Path,required=True)
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--camera',choices=['CAM_W1','CAM_ENTRY'],required=True)
    p.add_argument('--start-s',type=float,required=True)
    p.add_argument('--duration-s',type=float,default=6)
    p.add_argument('--fps',type=int,default=15)
    p.add_argument('--probe-only',action='store_true')
    p.add_argument('--indices',default='all')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    source=Path(bpy.data.filepath)
    assert sha(source)==SOURCE_SHA and sha(a.catalog)==CATALOG_SHA
    assert sha(a.scenario)==SCENARIO_SHA
    appearance=a.baseline_snapshot/'scripts/r004_4actor_common.py'
    assert sha(appearance)==APPEARANCE_SHA
    assert a.output.resolve().parent.parent==Path.home()/'amidst/local/evidence'
    a.output.mkdir(parents=True,exist_ok=True)
    assert shutil.disk_usage(a.output).free>=8*1024**3+350*1024**2
    sys.path.append(str(appearance.parent))
    from r004_4actor_common import configure_people
    people=configure_people(bpy,a.repo)
    adapters={k:Person(v) for k,v in people.items()}
    run=next(r for r in json.loads(a.scenario.read_text())['runs'] if r['scenario']=='A4-1')
    geo=json.loads(a.geometry.read_text())
    plans={}
    for actor in run['actors']:
        points=[]
        for w in actor['waypoints']:
            heights=[f['top_z_m'] for f in geo['floors'] if min(f['x_m'])<=w['xy'][0]<=max(f['x_m'])
                     and min(f['y_m'])<=w['xy'][1]<=max(f['y_m'])]
            points.append({**w,'z_m':w.get('z_m',max(heights) if heights else 0)})
        plans[actor['actor_id']]=WalkPlan(points)
    # Only actual render-visible wall/screen/car geometry, excluding floors (contact allowed).
    static=[o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render and
            (o.name.startswith(('WALL_','OBSTACLE_','R004_ENV_')))]
    static_tree=bvh(static)
    scene=bpy.context.scene
    camera=bpy.data.objects[a.camera]
    catalog=json.loads(a.catalog.read_text())
    # Catalog structure is validated by exact hash and source camera matrices below.
    camera_matrix=[list(row) for row in camera.matrix_world]
    assert a.camera in run['render_camera_ids']
    scene.camera=camera
    scene.render.resolution_x=960
    scene.render.resolution_y=540
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.color_depth='8'
    scene.render.use_stamp=False
    scene.render.fps=a.fps
    scene.eevee.taa_render_samples=16
    count=round(a.duration_s*a.fps)
    indices=list(range(count)) if a.indices=='all' else [int(x) for x in a.indices.split(',')]
    assert all(0<=n<count for n in indices)
    failures=[]
    checked=0
    for n in indices:
        time=a.start_s+n/a.fps
        active=[]
        for who,person in people.items():
            plan=plans[who]
            present=plan.times[0]<=time<=plan.times[-1]
            for obj in person['objects']:
                obj.hide_render=not present
            if present:
                adapters[who].apply(plan.pose(time))
                active.append(who)
        bpy.context.view_layer.update()
        trees={who:bvh(people[who]['objects']) for who in active}
        for who,tree in trees.items():
            hits=tree.overlap(static_tree)
            if hits:
                failures.append({'frame':n,'time_s':time,'actor':who,'static_surface_intersections':len(hits)})
        for i,who in enumerate(active):
            for other in active[i+1:]:
                hits=trees[who].overlap(trees[other])
                if hits:
                    failures.append({'frame':n,'time_s':time,'actors':[who,other],'surface_intersections':len(hits)})
        checked+=1
        if n%15==0:
            print(f'NATURAL_PROBE frame={n} time={time:.3f} failures={len(failures)}',flush=True)
        if not a.probe_only:
            if failures:
                break
            png=a.output/f'{n:06d}.png'
            assert not png.exists()
            assert shutil.disk_usage(a.output).free>=8*1024**3+32*1024**2
            scene.render.filepath=str(png)
            bpy.ops.render.render(write_still=True)
    assert sha(source)==SOURCE_SHA and sha(a.catalog)==CATALOG_SHA
    assert camera_matrix==[list(row) for row in camera.matrix_world]
    report={'schema':'amidst.natural-walk-sample-probe.v1','source_sha256':SOURCE_SHA,
            'scenario_sha256':SCENARIO_SHA,'appearance_sha256':APPEARANCE_SHA,
            'gait_code_sha256':sha(Path(__file__).with_name('r004_natural_walk.py')),
            'producer_code_sha256':sha(__file__),'camera':a.camera,'start_s':a.start_s,
            'duration_s':a.duration_s,'fps':a.fps,'frames_checked':checked,
            'rendered':not a.probe_only,'source_blend_saved':False,'source_blend_copied':False,
            'root_route_changed':False,'camera_matrix_changed':False,
            'static_mesh_objects':[o.name for o in static],
            'surface_intersections':failures,
            'scope':'Sample mesh surface-intersection check only; not >=0.35m articulated surface clearance or full-run/navigation acceptance'}
    dump(a.output/('probe.json' if a.probe_only else 'render_receipt.json'),report)
    if failures:
        raise RuntimeError(f'{len(failures)} posed mesh intersections; see probe')


if __name__=='__main__':
    main()

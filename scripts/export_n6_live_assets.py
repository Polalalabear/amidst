"""Blender producer: independent locomotion clips and static baked r004 surfaces.

Run in background Blender with --factory-startup --disable-autoexec SOURCE.blend.
Never saves/copies the source, evaluates its timeline, or reads scenario routes.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
from audit_n6_character import CATALOG_SHA, SOURCE_SHA, sha


def write(path, value):
    assert not path.exists(), f'Refuse overwrite: {path}'
    path.write_text(json.dumps(value, indent=2)+'\n')


def select(objects):
    if bpy.context.object and bpy.context.object.mode!='OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def export(path, objects, animations=False):
    assert not path.exists()
    select(objects)
    result = bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', use_selection=True,
        export_yup=True, export_extras=True, export_cameras=False, export_lights=False,
        export_animations=animations, export_animation_mode='ACTIONS',
        export_frame_range=False, export_force_sampling=True,
        export_anim_single_armature=True, export_rest_position_armature=True,
        export_def_bones=True)
    assert result=={'FINISHED'}


def character(args):
    from n6_character_rig import apply, build
    from n6_gait import PROFILES, duration, pose
    from render_r004_d124 import make_appearance
    root = bpy.data.objects['PRODUCTION_P1_ROOT']
    root.animation_data_clear()
    root.location = (0,0,0)
    root.rotation_euler = (0,0,0)
    bpy.context.view_layer.update()
    cfg = json.loads((args.repo/'configs/q1q5/producers/r004_d124_v1.json').read_text())
    make_appearance(bpy,root,cfg['appearance'],'+X')
    rig, meshes = build()
    # B's optional shoulder bag: a material variant makes it transparent for T/A/C.
    bpy.ops.mesh.primitive_cube_add(size=1)
    bag = bpy.context.object
    bag.name = 'N6_B_SIDEBAG'
    bag.location,bag.scale = (0,-.19,.95),(.12,.08,.18)
    material = bpy.data.materials.new('N6_BAG')
    material.use_nodes = True
    material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.045,.065,.075,1)
    material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .8
    bag.data.materials.append(material)
    bag.parent = rig
    group = bag.vertex_groups.new(name='pelvis')
    group.add(list(range(len(bag.data.vertices))),1,'REPLACE')
    bag.modifiers.new('N6_Skin','ARMATURE').object = rig
    meshes.append(bag)
    bpy.context.view_layer.update()
    for obj in [rig,*meshes]:
        for key in list(obj.keys()):
            del obj[key]
        if obj.type=='MESH':
            for key in list(obj.data.keys()):
                del obj.data[key]
            # glTF skinning ignores a skinned node's local transform. Bake it
            # into private mesh data, leaving all skin nodes at scene root.
            matrix = obj.matrix_world.copy()
            obj.data = obj.data.copy()
            obj.data.transform(matrix)
            obj.parent = None
            obj.matrix_world = Matrix.Identity(4)
    scene = bpy.context.scene
    scene.render.fps = 960
    scene.render.fps_base = 1
    # Exact clip durations are restored in GLB postprocessing; samples use 960Hz.
    metrics = {}
    for name in ('walk','run','idle'):
        frames = round(duration(name)*960)
        rig.animation_data_clear()
        first = None
        max_seam = 0.
        flight = 0
        slip = 0.
        min_foot = 100.
        for n in range(frames+1):
            phase = n/frames
            sample = pose(name,phase)
            apply(rig,sample)
            if n==0:
                first = {p.name:p.matrix.copy() for p in rig.pose.bones}
            if n==frames:
                max_seam = max(abs(first[p.name][i][j]-p.matrix[i][j])
                               for p in rig.pose.bones for i in range(4) for j in range(4))
            supports = sample.get('supports', {1:True,-1:True})
            if not any(supports.values()):
                flight += 1
            min_foot = min(min_foot, *(sample['legs'][s]['ankle'][2]-.10 for s in (1,-1)))
            if name!='idle':
                for s in (1,-1):
                    if supports[s] and ((phase+(.5 if s==-1 else 0))%1)<PROFILES[name]['duty']-1e-4:
                        next_pose = pose(name,phase+1e-6)
                        velocity = (next_pose['legs'][s]['ankle'][0]-sample['legs'][s]['ankle'][0])/(duration(name)*1e-6)
                        slip = max(slip,abs(velocity+PROFILES[name]['speed_m_s']))
            for pb in rig.pose.bones:
                pb.rotation_mode = 'QUATERNION'
                pb.keyframe_insert('location',frame=n,group=pb.name)
                pb.keyframe_insert('rotation_quaternion',frame=n,group=pb.name)
                pb.keyframe_insert('scale',frame=n,group=pb.name)
        action = rig.animation_data.action
        action.name = name
        action.use_fake_user = True
        metrics[name] = dict(**PROFILES[name],duration_s=duration(name),samples=frames+1,
                             seam_matrix_error=max_seam,flight_samples=flight,
                             support_slip_m_s=slip,min_shoe_height_m=min_foot)
        assert max_seam<1e-5 and slip<1e-5 and min_foot>=-1e-7
    assert metrics['run']['flight_samples']>0 and metrics['walk']['flight_samples']==0
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    export(args.output/'character.raw.glb',[rig,*meshes],True)
    return dict(bones=len(rig.data.bones),meshes=len(meshes),clips=metrics,
                skinning='Rigid one-bone weights with #529 knee/elbow caps',
                appearance_source='r004_4actor_common.py + r004_d124_v1.json; v2.3',
                controller='In-place +X forward (also +X after Y-up conversion); speed = stride / duration')


def scene(args):
    start = time.monotonic()
    source_objects = [o for o in bpy.data.objects if o.type=='MESH' and not o.hide_render
                      and not o.name.startswith('PRODUCTION_')]
    expected = {'CEILING_STATIC','FLOOR_GROUND','WALL_JOINED_SHELL','R004_EXTERIOR_FLOOR',
                'OBSTACLE_SCREEN_CORNER_N','OBSTACLE_SCREEN_N','OBSTACLE_SCREEN_R102',
                'OBSTACLE_SCREEN_W','OBSTACLE_SCREEN_W_HOOD','R004_ENV_VEHICLE_BODY',
                'R004_ENV_VEHICLE_CABIN','R004_ENV_WHEEL','R004_ENV_WHEEL.001',
                'R004_ENV_WHEEL.002','R004_ENV_WHEEL.003'}
    assert {o.name for o in source_objects}==expected
    source_objects.sort(key=lambda o:o.name)
    evaluated_modifiers = {}
    for obj in source_objects:
        evaluated_modifiers[obj.name] = [m.type for m in obj.modifiers if m.show_render]
        for modifier in obj.modifiers:
            modifier.show_viewport = modifier.show_render
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_meshes = {obj:bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph),
                        preserve_all_data_layers=True,depsgraph=depsgraph) for obj in source_objects}
    for obj,data in evaluated_meshes.items():
        obj.data = data
        obj.modifiers.clear()
    bpy.context.view_layer.update()
    vertices,faces,indices,materials,components = [],[],[],[],[]
    for obj in source_objects:
        offset = len(vertices)
        vertices.extend(tuple(obj.matrix_world@v.co) for v in obj.data.vertices)
        mapping = []
        for material in obj.data.materials:
            if material not in materials:
                materials.append(material)
            mapping.append(materials.index(material))
        first_face = len(faces)
        faces.extend(tuple(offset+i for i in polygon.vertices) for polygon in obj.data.polygons)
        indices.extend(mapping[polygon.material_index] for polygon in obj.data.polygons)
        components.append(dict(source_component=obj.name,first_polygon=first_face,
                               polygon_count=len(obj.data.polygons),vertex_count=len(obj.data.vertices)))
    mesh = bpy.data.meshes.new('N6_BakeMesh')
    mesh.from_pydata(vertices,[],faces)
    atlas = bpy.data.objects.new('N6_BakeAtlas',mesh)
    bpy.context.scene.collection.objects.link(atlas)
    for material in materials:
        mesh.materials.append(material.copy())
    for polygon,index in zip(mesh.polygons,indices):
        polygon.material_index = index
    for obj,component in zip(source_objects,components):
        for polygon in obj.data.polygons:
            mesh.polygons[component['first_polygon']+polygon.index].use_smooth = polygon.use_smooth
    for obj in bpy.data.objects:
        if obj.type=='MESH' and obj!=atlas:
            obj.hide_render = True
    select([atlas])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.006)
    bpy.ops.uv.pack_islands(margin=.006,rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh.uv_layers.active.name = 'BakedUV'
    # Keep large coplanar floor/ceiling faces continuous. Independent smart-UV
    # islands per source panel produce visible seams under atlas filtering.
    uv_layer = mesh.uv_layers.active
    for uv in uv_layer.data:
        uv.uv = (.51+.48*uv.uv.x,.51+.48*uv.uv.y)
    tiles = {'FLOOR_GROUND':(.01,.01,1), 'CEILING_STATIC':(.51,.01,-1),
             'R004_EXTERIOR_FLOOR':(.01,.51,1)}
    for obj,component in zip(source_objects,components):
        if obj.name not in tiles:
            continue
        ox,oy,sign = tiles[obj.name]
        polys = [mesh.polygons[component['first_polygon']+p.index] for p in obj.data.polygons]
        main = [p for p in polys if p.normal.z*sign>.999]
        assert main
        points = [mesh.vertices[i].co for p in main for i in p.vertices]
        xmin,xmax = min(p.x for p in points),max(p.x for p in points)
        ymin,ymax = min(p.y for p in points),max(p.y for p in points)
        for p in main:
            for index in p.loop_indices:
                point = mesh.vertices[mesh.loops[index].vertex_index].co
                uv_layer.data[index].uv = (ox+.48*(point.x-xmin)/(xmax-xmin),
                                           oy+.48*(point.y-ymin)/(ymax-ymin))
    s = bpy.context.scene
    s.render.engine = 'CYCLES'
    s.cycles.device = 'CPU'
    s.cycles.samples = 32
    s.cycles.seed = 0
    s.render.bake.margin = 8
    s.render.bake.use_clear = True
    results = {}
    for kind,bake_type in [('irradiance','DIFFUSE'),('appearance','COMBINED')]:
        image = bpy.data.images.new('N6_'+kind,width=4096,height=4096,float_buffer=True,alpha=False)
        image.colorspace_settings.name = 'Linear Rec.709'
        for material in mesh.materials:
            material.use_nodes = True
            node = material.node_tree.nodes.new('ShaderNodeTexImage')
            node.image = image
            material.node_tree.nodes.active = node
        s.render.bake.use_pass_direct = True
        s.render.bake.use_pass_indirect = True
        s.render.bake.use_pass_color = kind!='irradiance'
        print('N6_BAKE_START '+kind,flush=True)
        assert bpy.ops.object.bake(type=bake_type)=={'FINISHED'}
        path = args.output/('lightmap_irradiance.exr' if kind=='irradiance' else 'baked_appearance.png')
        s.render.image_settings.file_format = 'OPEN_EXR' if kind=='irradiance' else 'PNG'
        s.render.image_settings.color_depth = '16' if kind=='irradiance' else '8'
        s.render.image_settings.color_mode = 'RGB'
        image.save_render(str(path),scene=s)
        results[kind] = dict(path=path.name,sha256=sha(path),size_bytes=path.stat().st_size)
        print('N6_BAKE_DONE '+kind,flush=True)
    # A standard unlit baked appearance preserves the display transform in any viewer.
    # Separate linear irradiance is delivered for clients that implement a lightMap.
    material = bpy.data.materials.new('N6_BakedLighting_AgX')
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(args.output/'baked_appearance.png'))
    emission = nodes.new('ShaderNodeEmission')
    output = nodes.new('ShaderNodeOutputMaterial')
    material.node_tree.links.new(tex.outputs['Color'],emission.inputs['Color'])
    material.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
    outputs = []
    uv_source = mesh.uv_layers.active
    for obj,component in zip(source_objects,components):
        data = bpy.data.meshes.new('N6_'+obj.name)
        data.from_pydata([tuple(v.co) for v in obj.data.vertices],[],[list(p.vertices) for p in obj.data.polygons])
        for a,b in zip(data.polygons,obj.data.polygons):
            a.use_smooth = b.use_smooth
        data.materials.append(material)
        first = component['first_polygon']
        for uv_name in ('BakedUV','LightmapUV'):
            uv = data.uv_layers.new(name=uv_name)
            for polygon in data.polygons:
                source_polygon = mesh.polygons[first+polygon.index]
                for a,b in zip(polygon.loop_indices,source_polygon.loop_indices):
                    uv.data[a].uv = uv_source.data[b].uv
        clean = bpy.data.objects.new(obj.name+'_LIVE',data)
        bpy.context.scene.collection.objects.link(clean)
        clean.matrix_world = obj.matrix_world.copy()
        clean['n6Collider'] = True
        clean['sourceComponent'] = obj.name
        clean['colliderRole'] = 'STATIC_SOURCE_TRIANGLES_DEMO_ONLY'
        outputs.append(clean)
    export(args.output/'scene.raw.glb',outputs)
    cameras = json.loads(args.catalog.read_text())
    write(args.output/'cameras.catalog.json',cameras)
    basis = np.array([[1.,0.,0.,0.],[0.,0.,1.,0.],[0.,-1.,0.,0.],[0.,0.,0.,1.]])
    converted = []
    for camera in cameras['cameras']:
        source_camera = bpy.data.objects[camera['camera_id']]
        delta = max(abs(source_camera.matrix_world[i][j]-camera['camera_to_world'][i][j])
                    for i in range(4) for j in range(4))
        assert delta<1e-6
        n,f,w,h = camera['clip_start'],camera['clip_end'],camera['width'],camera['height']
        projection = [[2*camera['fx']/w,0,1-2*camera['cx']/w,0],
                      [0,2*camera['fy']/h,2*camera['cy']/h-1,0],
                      [0,0,-(f+n)/(f-n),-2*f*n/(f-n)],[0,0,-1,0]]
        matrix = basis@np.array(camera['camera_to_world'],dtype=np.float64)
        converted.append(dict(camera_id=camera['camera_id'],width=w,height=h,
                              fx=camera['fx'],fy=camera['fy'],cx=camera['cx'],cy=camera['cy'],
                              near=n,far=f,camera_to_world=[list(row) for row in matrix],
                              world_to_camera=np.linalg.inv(matrix).tolist(),
                              projection_matrix=projection,source_matrix_error=delta))
    write(args.output/'cameras.three.json',dict(schema='amidst.n6-cameras.v1',
          source_catalog_sha256=CATALOG_SHA,world='Y-up meters; (x,y,z) Blender -> (x,z,-y) glTF',
          matrices='row-major arrays; THREE.Matrix4.set(...rows.flat()); camera looks local -Z, local +Y up',
          cameras=converted))
    return dict(components=components,textures=results,atlas_px=[4096,4096],evaluated_modifiers=evaluated_modifiers,
                samples=32,engine='Cycles CPU',bake_types=['DIFFUSE color disabled','COMBINED'],
                view_transform='AgX / None / exposure 0 / gamma 1; applied to appearance PNG only',
                collider_geometry='Exact visible source triangles; no hidden WALK proxies exported',
                elapsed_s=time.monotonic()-start)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stage',choices=['character','scene'],required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    assert sha(bpy.data.filepath)==SOURCE_SHA and sha(args.catalog)==CATALOG_SHA
    expected_parent = Path.home()/'amidst/local/data'
    assert args.output.parent==expected_parent and args.output.name.startswith('live-assets-')
    assert not args.output.is_symlink()
    assert shutil.disk_usage(expected_parent).free>8*1024**3+512*1024**2
    args.output.mkdir(exist_ok=True)
    receipt_path = args.output/('export_'+args.stage+'.json')
    assert not receipt_path.exists()
    details = character(args) if args.stage=='character' else scene(args)
    assert sha(bpy.data.filepath)==SOURCE_SHA and sha(args.catalog)==CATALOG_SHA
    write(receipt_path,dict(schema='amidst.n6-export.v1',stage=args.stage,details=details,
          blender_version=bpy.app.version_string,blender_build=bpy.app.build_hash.decode(),
          source_sha256=SOURCE_SHA,catalog_sha256=CATALOG_SHA,
          source_saved=False,source_copied=False,video_rendered=False,index_built=False,
          coordinate_system='Y-up meters; same origin; Blender(x,y,z)->glTF(x,z,-y)',
          exporter=dict(format='GLB',selection_only=True,yup=True,extras='N6 allowlist only',
                        cameras=False,lights=False,animations=args.stage=='character')))
    print('N6_EXPORT_COMPLETE '+args.stage,flush=True)


if __name__=='__main__':
    main()

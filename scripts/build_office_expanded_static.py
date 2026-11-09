"""Build only the approved #418 procedural scene and seven static PNGs.

The approved parameter bytes are immutable. No source blend, actors, animation,
model, inference, or existing media is loaded. Import/help does not need bpy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = ROOT / 'docs/engineering/d127_418_parameters.proposed.json'
PARAMETER_SHA = '57df9d291e198c8e56b6767fac37ae07c461e9aa87239da7e910544f81e06b26'
APPROVAL = 'https://github.com/Polalalabear/amidst/issues/418#issuecomment-6634899000'
sys.path.insert(0, str(ROOT / 'src'))
from amidst.paths import data_dir  # noqa: E402

OUTPUT = data_dir() / 'd127-418-office-expanded-r005'
GIB = 1024**3


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def no_links(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'SYMLINK_FORBIDDEN')
    return path


def new_output(path, approved=OUTPUT):
    path = no_links(path)
    require(path == Path(approved).absolute(), 'OUTPUT_NOT_APPROVED')
    require(not path.exists(), 'OUTPUT_EXISTS')
    require(path.parent.is_dir(), 'OUTPUT_PARENT_MISSING')
    return path


def parameters(path=PARAMETERS):
    path = no_links(path)
    raw = path.read_bytes()
    require(sha(raw) == PARAMETER_SHA, 'PARAMETER_PIN_MISMATCH')
    data = json.loads(raw)
    require(data['scene_id'] == 'office_expanded_r005' and data['parent_asset'] is None,
            'SCENE_SCOPE_MISMATCH')
    require(len(data['rooms']) == 4 and len(data['corridor_cameras']) == 2
            and data['render']['animation_frames'] == 0, 'STATIC_SCOPE_MISMATCH')
    return data


def allocated(root):
    return sum(p.stat().st_blocks * 512 for p in root.rglob('*') if p.is_file()) if root.exists() else 0


def disk_record(root, stage, *, start=False):
    free = shutil.disk_usage(root.parent).free
    used = allocated(root)
    require(free >= (8.5 if start else 8) * GIB, 'DISK_GATE')
    require(used <= 256 * 1024**2, 'OUTPUT_BUDGET_EXCEEDED')
    return {'stage': stage, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'free_bytes': free, 'output_allocated_bytes': used}


def strip_png(raw):
    """Validate chunks/CRC; strip ancillary metadata without changing IDAT bytes."""
    require(raw[:8] == b'\x89PNG\r\n\x1a\n', 'PNG_SIGNATURE')
    pos = 8; out = bytearray(raw[:8]); removed = []; tags = []
    while pos < len(raw):
        require(pos + 12 <= len(raw), 'PNG_TRUNCATED')
        n = struct.unpack('>I', raw[pos:pos+4])[0]
        end = pos + 12 + n
        require(end <= len(raw), 'PNG_TRUNCATED')
        tag = raw[pos+4:pos+8]; data = raw[pos+8:pos+8+n]
        require(zlib.crc32(tag+data) & 0xffffffff == struct.unpack('>I', raw[end-4:end])[0],
                'PNG_CRC')
        tags.append(tag)
        if tag in {b'IHDR', b'IDAT', b'IEND', b'sRGB', b'gAMA', b'pHYs'}:
            out.extend(raw[pos:end])
        elif tag[0] & 32:
            removed.append(tag.decode('ascii'))
        else:
            raise ValueError('PNG_UNKNOWN_CRITICAL_CHUNK')
        pos = end
        if tag == b'IEND':
            require(n == 0 and pos == len(raw), 'PNG_IEND_OR_TRAILING')
            break
    require(tags[0] == b'IHDR' and tags[-1] == b'IEND' and b'IDAT' in tags, 'PNG_STRUCTURE')
    return bytes(out), removed


def build(data, output):
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view

    records = [disk_record(output, 'before_build', start=True)]
    output.mkdir()
    (output/'rgb').mkdir(); (output/'human_layout').mkdir(); (output/'static').mkdir()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 1
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = data['render']['samples']
    scene.render.resolution_x, scene.render.resolution_y = data['render']['resolution_px']
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'; scene.render.image_settings.color_depth = '8'
    scene.render.use_stamp = False
    scene.view_settings.view_transform = 'Standard'
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = data['render']['world_strength']

    def material(name, rgb):
        m = bpy.data.materials.new(name); m.use_nodes = True
        node = m.node_tree.nodes.get('Principled BSDF')
        node.inputs['Base Color'].default_value = (*rgb, 1)
        node.inputs['Roughness'].default_value = 0.7
        return m

    wall = material('wall', (0.72, 0.73, 0.70)); floor = material('floor', (0.32, 0.34, 0.35))
    furniture = data['object_placement']
    chair_mat = material('chair', furniture['chair_rgb'])
    table_mat = material('table', furniture['table_rgb'])
    target_mat = material('target', furniture['target_rgb'])
    dark = material('screen', (0.03, 0.06, 0.10))

    def box(name, xyz, size, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
        obj = bpy.context.object; obj.name = name; obj.dimensions = size
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(mat)
        return obj

    def cylinder(name, xy, z, radius, height, mat):
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=height,
                                           location=(*xy, z+height/2))
        obj = bpy.context.object; obj.name = name; obj.data.materials.append(mat)
        return obj

    regions = []; portals = []
    height = data['wall_height_m']; thick = data['wall_thickness_m']
    door_width = data['door_width_m']; door_height = data['door_height_m']

    def region(name, bounds, kind):
        x0, x1, y0, y1 = bounds
        poly = [[x0,y0,0],[x1,y0,0],[x1,y1,0],[x0,y1,0]]
        regions.append({'region_id': name, 'kind': kind, 'polygon_world_m': poly})
        box('floor_'+name, ((x0+x1)/2,(y0+y1)/2,-0.05), (x1-x0,y1-y0,0.1), floor)

    for name, bounds in [('CORR_W',[0,8,0,2]),('CORR_E',[8,16,0,2])]:
        region(name, bounds, 'CORRIDOR_SEGMENT')
    for room in data['rooms']:
        name = room['region_id']; x0,x1,y0,y1 = room['bounds_xy_m']; cx,cy=(x0+x1)/2,(y0+y1)/2
        region(name, room['bounds_xy_m'], 'ROOM')
        dx,dy = room['door_center_xy_m']
        for x in [x0,x1]:box(name+'_sidewall', (x,cy,height/2), (thick,y1-y0,height), wall)
        for y in [y0,y1]:
            if y != dy:box(name+'_backwall', (cx,y,height/2), (x1-x0,thick,height), wall)
            else:
                left,right=dx-door_width/2,dx+door_width/2
                for a,b in [(x0,left),(right,x1)]:
                    box(name+'_doorwall',((a+b)/2,y,height/2),(b-a,thick,height),wall)
                box(name+'_lintel',(dx,y,(height+door_height)/2),
                    (door_width,thick,height-door_height),wall)
        portal={'edge_id':'E_'+name,'regions':[name,'CORR_W' if cx<8 else 'CORR_E'],
                'quad_world_m':[[dx-door_width/2,dy,0],[dx+door_width/2,dy,0],
                                [dx+door_width/2,dy,door_height],[dx-door_width/2,dy,door_height]]}
        portals.append(portal)
        light=bpy.data.lights.new(name+'_area','AREA');light.energy=data['render']['room_area_light_w']
        light.shape='DISK';light.size=data['render']['room_area_light_size_m']
        obj=bpy.data.objects.new(light.name,light);scene.collection.objects.link(obj)
        obj.location=(cx,cy,data['render']['room_area_light_z_m'])
        # Labels are ordinary authored signs, never fed to graph/inference as answers.
        text=bpy.data.curves.new(name+'_sign','FONT');text.body=name;text.size=0.26
        obj=bpy.data.objects.new(name+'_sign',text);scene.collection.objects.link(obj)
        obj.location=(dx-0.55,dy+(0.10 if dy==y1 else -0.10),2.42)
        obj.rotation_euler=(math.pi/2 if dy==y1 else -math.pi/2,0,0)
        obj.data.materials.append(dark)
        w,d,h=furniture['table_dimensions_xyz_m'];tx,ty=furniture['table_offset_xy_m'];tx+=cx;ty+=cy
        box(name+'_tabletop',(tx,ty,h-0.035),(w,d,0.07),table_mat)
        for sx in [-1,1]:
            for sy in [-1,1]:box(name+'_tableleg',(tx+sx*(w/2-0.09),ty+sy*(d/2-0.09),h/2),(.07,.07,h-.07),table_mat)
        for ox,oy in furniture['chair_offsets_xy_m']:
            x,y=cx+ox,cy+oy;cw,cd,ch=furniture['chair_dimensions_xyz_m']
            box(name+'_seat',(x,y,0.45),(cw,cd,0.07),chair_mat)
            box(name+'_back',(x,y+cd/2,0.69),(cw,0.07,ch-0.45),chair_mat)
            for sx in [-1,1]:
                for sy in [-1,1]:box(name+'_chairleg',(x+sx*(cw/2-.04),y+sy*(cd/2-.04),.225),(.05,.05,.45),chair_mat)
        for category,(ox,oy) in zip(room['object_categories'][3:],furniture['target_offsets_xy_m'],strict=True):
            x,y,z=cx+ox,cy+oy,furniture['target_base_height_m']
            w,d,h=furniture[category+'_dimensions_xyz_m'];label=name+'_'+category
            if category=='bottle':
                cylinder(label,(x,y),z,w/2,h*.78,target_mat)
                cylinder(label+'_neck',(x,y),z+h*.78,w*.22,h*.22,target_mat)
            elif category=='cup':
                cylinder(label,(x,y),z,w/2,h,target_mat)
                bpy.ops.mesh.primitive_torus_add(major_radius=h*.28,minor_radius=.012,
                    location=(x+w*.6,y,z+h*.55),rotation=(math.pi/2,0,0))
                bpy.context.object.data.materials.append(target_mat)
            elif category=='laptop':
                box(label+'_base',(x,y,z+.014),(w,d,.028),dark)
                box(label+'_screen',(x,y+d/2-.01,z+h/2),(w,.025,h),dark)
            elif category=='book':
                box(label,(x,y,z+h/2),(w,d,h),target_mat)
            else:
                obj=box(label,(x,y,z+h/2),(w,d,h),target_mat)
                bevel=obj.modifiers.new('soft_edges','BEVEL');bevel.width=.06;bevel.segments=4
                box(label+'_pocket',(x,y-d/2-.02,z+h*.4),(w*.7,.04,h*.45),dark)

    # Fill corridor wall segments between approved room doors; no new entrance is claimed.
    for y in [0,2]:
        box('corridor_middle_wall',(8,y,height/2),(2,thick,height),wall)
    for x in [0,16]:box('corridor_endwall',(x,1,height/2),(thick,2,height),wall)
    portals.append({'edge_id':'E_CORR_JOIN','regions':['CORR_W','CORR_E'],
                    'quad_world_m':[[8,0,0],[8,2,0],[8,2,2.2],[8,0,2.2]]})
    cameras=[]; objects={}
    for item in data['rooms']+data['corridor_cameras']:
        name=item['camera_id'];cam=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,cam)
        scene.collection.objects.link(obj);obj.location=item['camera_xyz_m']
        obj.rotation_euler=(Vector(item['look_at_xyz_m'])-obj.location).to_track_quat('-Z','Y').to_euler()
        angle=data['camera']['indoor_hfov_deg' if 'region_id' in item else 'corridor_hfov_deg']
        cam.sensor_fit='HORIZONTAL';cam.sensor_width=36
        cam.lens=36/(2*math.tan(math.radians(angle)/2));cam.clip_start,cam.clip_end=data['camera']['clip_m']
        objects[name]=obj
    overview=data['overhead'];cam=bpy.data.cameras.new('HUMAN_LAYOUT');obj=bpy.data.objects.new(cam.name,cam)
    scene.collection.objects.link(obj);obj.location=overview['camera_xyz_m']
    obj.rotation_euler=(Vector(overview['look_at_xyz_m'])-obj.location).to_track_quat('-Z','Y').to_euler()
    cam.type='ORTHO';cam.ortho_scale=overview['scale_m'];objects['HUMAN_LAYOUT']=obj
    bpy.context.view_layer.update()
    scene.camera=objects[data['rooms'][0]['camera_id']]
    # No pre-existing blend is opened; this is the sole newly generated source.
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'scene.blend'))
    source_sha=sha((output/'scene.blend').read_bytes())
    width,height=data['render']['resolution_px']
    for name,obj in objects.items():
        if name=='HUMAN_LAYOUT':continue
        fx=width*obj.data.lens/obj.data.sensor_width
        rois=[]
        relevant=[p for p in portals if (name=='CAM_'+p['regions'][0]+'_IN') or
                  (name=='CAM_CORR_W' and 'CORR_W' in p['regions']) or
                  (name=='CAM_CORR_E' and 'CORR_E' in p['regions'])]
        for p in relevant:
            projected=[world_to_camera_view(scene,obj,Vector(v)) for v in p['quad_world_m']]
            require(all(v.z>0 for v in projected),'PORTAL_BEHIND_CAMERA')
            xs=[max(0,min(width,v.x*width)) for v in projected]
            ys=[max(0,min(height,(1-v.y)*height)) for v in projected]
            require(max(xs)>min(xs) and max(ys)>min(ys),'PORTAL_OUTSIDE_FRAME')
            rois.append({'edge_id':p['edge_id'],'roi_polygon_px':[[min(xs),min(ys)],[max(xs),min(ys)],
                         [max(xs),max(ys)],[min(xs),max(ys)]], 'basis':'STATIC_CALIBRATION_PROJECTION'})
        entry={'camera_id':name,'camera_to_world':[list(r) for r in obj.matrix_world],
               'convention':'BLENDER_NEG_Z_UP_Y','width':width,'height':height,'fx':fx,'fy':fx,
               'cx':width/2,'cy':height/2,'focal_length_mm':obj.data.lens,'sensor_width_mm':36,
               'clip_m':[obj.data.clip_start,obj.data.clip_end],'source_sha256':source_sha,'portal_rois':rois}
        entry['calibration_sha256']=sha(canonical(entry));cameras.append(entry)
    files={};rendered=[]
    for name,obj in objects.items():
        records.append(disk_record(output,'before_'+name));scene.camera=obj
        rel=('human_layout/overview.png' if name=='HUMAN_LAYOUT' else 'rgb/'+name+'.png')
        path=output/rel;scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        raw=path.read_bytes();clean,removed=strip_png(raw);path.write_bytes(clean)
        files[rel]={'sha256':sha(clean),'bytes':len(clean)}
        rendered.append({'camera_id':name,'file':rel,'raw_sha256':sha(raw),'sha256':sha(clean),
                         'removed_chunk_types':removed,'purpose':'HUMAN_LAYOUT_ONLY' if name=='HUMAN_LAYOUT' else 'STATIC_CAMERA_RGB'})
        records.append(disk_record(output,'after_'+name))
    docs={'static/cameras.json':{'scene_id':data['scene_id'],'source_sha256':source_sha,'run_bindings':[], 'cameras':cameras},
          'static/regions.json':{'scene_id':data['scene_id'],'source_sha256':source_sha,'regions':regions,'portals':portals}}
    for rel,doc in docs.items():
        raw=json.dumps(doc,indent=2,allow_nan=False).encode()+b'\n';(output/rel).write_bytes(raw)
        files[rel]={'sha256':sha(raw),'bytes':len(raw)}
    files['scene.blend']={'sha256':source_sha,'bytes':(output/'scene.blend').stat().st_size}
    receipt={'issue':418,'scene_id':data['scene_id'],'parameter_sha256':PARAMETER_SHA,
        'authorization_ref':APPROVAL,'builder_sha256':sha(Path(__file__).read_bytes()),
        'source_sha256':source_sha,'blender_version':bpy.app.version_string,'blender_build_hash':bpy.app.build_hash.decode(),
        'engine':scene.render.engine,'samples':scene.eevee.taa_render_samples,'seed_requested':7,
        'seed_status':'NO_PUBLIC_EEVEE_SEED_SETTING','camera_image_count':6,'human_layout_image_count':1,
        'animation_rendered':False,'rendered':rendered,'files':files,'disk_samples':records,
        'coverage_status':'NOT_EVALUATED','physical_navigation':'UNKNOWN','collision':'UNKNOWN','gt_read':False}
    (output/'build_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'STATIC_RENDER_COMPLETE','source_sha256':source_sha,
                      'output':str(output),'image_count':len(rendered),'allocated_bytes':allocated(output)}))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parameters',type=Path,default=PARAMETERS)
    p.add_argument('--output',type=Path,default=OUTPUT)
    p.add_argument('--check-only',action='store_true')
    p.add_argument('--execute',action='store_true')
    p.add_argument('--authorization-ref')
    args=p.parse_args(argv)
    require(args.check_only or (args.execute and args.authorization_ref==APPROVAL), 'EXPLICIT_AUTHORIZATION_REQUIRED')
    require(not (args.check_only and args.execute),'MODE_CONFLICT')
    data=parameters(args.parameters);output=new_output(args.output,approved=args.output)  # --output redefines the approved location
    snapshot=disk_record(output,'preflight',start=True)
    if args.check_only:
        print(json.dumps({'status':'APPROVED_INPUTS_VERIFIED','parameter_sha256':PARAMETER_SHA,'disk':snapshot}))
        return 0
    build(data,output)
    return 0


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    raise SystemExit(main(args))

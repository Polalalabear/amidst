"""Apply the approved #418 display correction to a new v2 derivative only.

The v1 producer and all v1 bytes stay unchanged. No original/historical scene,
actors, animation, video, detector, or private namespace is used.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_office_expanded_static import (
    ROOT, OUTPUT as SOURCE, PARAMETER_SHA, parameters, sha, canonical, no_links,
    new_output, disk_record, allocated, strip_png, require,
)

CORRECTION=ROOT/'docs/engineering/d127_418_preview_correction.proposed.json'
CORRECTION_SHA='e07218a16875a79aac474a0f5ab1ae714248571414a2d775f1ab2f2c8295aa74'
SOURCE_SHA='5daf1c58d767ce9783259381fac81ed27b09d3ec86bdeaa1fb388b94e3eedd1a'
SOURCE_RECEIPT_SHA='79c5a9020fd78c19427c54a5c776f1344733eacc71d0b3f8226e9290f493fdc0'
AUTHORIZATION='https://github.com/Polalalabear/amidst/issues/418#issuecomment-6636456072'
from amidst.paths import data_dir  # noqa: E402
OUTPUT=data_dir()/'d127-418-office-expanded-r005-preview-v2'


def correction(path=CORRECTION):
    raw=no_links(path).read_bytes();require(sha(raw)==CORRECTION_SHA,'CORRECTION_PIN')
    data=json.loads(raw)
    require(data['base_parameter_sha256']==PARAMETER_SHA and data['evidence_source_sha256']==SOURCE_SHA,
            'CORRECTION_SOURCE_PIN')
    require(data['scope']=={'camera_static_pngs':6,'human_overhead_pngs':1,'actors':0,'animation':False,'video':False},
            'CORRECTION_SCOPE')
    return data


def source_inputs():
    root=no_links(SOURCE)
    raw=no_links(root/'build_receipt.json').read_bytes()
    require(sha(raw)==SOURCE_RECEIPT_SHA,'V1_RECEIPT_PIN')
    receipt=json.loads(raw)
    require(receipt['source_sha256']==SOURCE_SHA,'V1_SOURCE_PIN')
    # Every pathname below is bound by the exact pre-approved v1 receipt hash.
    for rel,entry in receipt['files'].items():
        p=no_links(root/rel)
        require(p.is_file() and sha(p.read_bytes())==entry['sha256']
                and p.stat().st_size==entry['bytes'],'V1_FILE_PIN')
    return receipt,json.loads((root/'static/cameras.json').read_bytes()),json.loads((root/'static/regions.json').read_bytes())


def revise(output,profile,original,catalog,geometry):
    import bpy

    records=[disk_record(output,'before_v2',start=True)];output.mkdir()
    for name in ['rgb','human_layout','static']:(output/name).mkdir()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'scene.blend'),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;override=profile['overrides']
    scene.view_settings.exposure=override['view_exposure_ev']
    bpy.data.objects['HUMAN_LAYOUT'].data.ortho_scale=override['human_overhead_orthographic_scale_m']
    for i,item in enumerate(override['corridor_area_lights']):
        name='V2_CORRIDOR_LIGHT_'+str(i+1)
        require(bpy.data.objects.get(name) is None,'CORRECTION_LIGHT_EXISTS')
        light=bpy.data.lights.new(name,'AREA');light.energy=item['energy_w'];light.size=item['size_m']
        light.shape='SQUARE';obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj)
        obj.location=item['position_xyz_m']  # default local -Z points down
    base=parameters()
    for room in base['rooms']:
        sign=bpy.data.objects[room['region_id']+'_sign']
        south=room['door_center_xy_m'][1]==room['bounds_xy_m'][3]
        sign.rotation_euler=(math.pi/2,0,math.pi if south else 0)
    bpy.context.view_layer.update()
    for camera in catalog['cameras']:
        obj=bpy.data.objects[camera['camera_id']]
        require([list(row) for row in obj.matrix_world]==camera['camera_to_world'], 'CAMERA_TRANSFORM_CHANGED')
        require(abs(obj.data.lens-camera['focal_length_mm'])<1e-7,'CAMERA_LENS_CHANGED')
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'scene.blend'))
    source_sha=sha((output/'scene.blend').read_bytes())
    rendered=[];files={}
    for old in original['rendered']:
        name=old['camera_id'];scene.camera=bpy.data.objects[name]
        records.append(disk_record(output,'before_'+name));path=output/old['file']
        scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
        raw=path.read_bytes();clean,removed=strip_png(raw);path.write_bytes(clean)
        files[old['file']]={'sha256':sha(clean),'bytes':len(clean)}
        rendered.append({'camera_id':name,'file':old['file'],'raw_sha256':sha(raw),'sha256':sha(clean),
                         'removed_chunk_types':removed,'purpose':old['purpose']})
        records.append(disk_record(output,'after_'+name))
    catalog=deepcopy(catalog);catalog['source_sha256']=source_sha
    for row in catalog['cameras']:
        row['source_sha256']=source_sha
        row['calibration_sha256']=sha(canonical({k:v for k,v in row.items() if k!='calibration_sha256'}))
    geometry=deepcopy(geometry);geometry['source_sha256']=source_sha
    for rel,doc in [('static/cameras.json',catalog),('static/regions.json',geometry)]:
        raw=json.dumps(doc,indent=2,allow_nan=False).encode()+b'\n';(output/rel).write_bytes(raw)
        files[rel]={'sha256':sha(raw),'bytes':len(raw)}
    files['scene.blend']={'sha256':source_sha,'bytes':(output/'scene.blend').stat().st_size}
    result={**deepcopy(original),'preview_revision':'v2','parent_source_sha256':SOURCE_SHA,
        'parent_receipt_sha256':SOURCE_RECEIPT_SHA,'preview_correction_sha256':CORRECTION_SHA,
        'authorization_ref':AUTHORIZATION,'builder_source_name':Path(__file__).name,
        'builder_sha256':sha(Path(__file__).read_bytes()),'source_sha256':source_sha,
        'rendered':rendered,'files':files,'disk_samples':records,
        'display_correction':override,'blender_version':bpy.app.version_string,
        'blender_build_hash':bpy.app.build_hash.decode(),'coverage_status':'NOT_EVALUATED'}
    (output/'build_receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    # Verify original v1 files again after Blender execution; never write there.
    source_inputs()
    print(json.dumps({'status':'STATIC_V2_RENDER_COMPLETE','source_sha256':source_sha,
                      'images':len(rendered),'output':str(output),'allocated_bytes':allocated(output)}))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--correction',type=Path,default=CORRECTION)
    p.add_argument('--output',type=Path,default=OUTPUT)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--authorization-ref')
    p.add_argument('--check-only',action='store_true')
    args=p.parse_args(argv)
    require(args.check_only or (args.execute and args.authorization_ref==AUTHORIZATION),'EXPLICIT_AUTHORIZATION_REQUIRED')
    require(not(args.execute and args.check_only),'MODE_CONFLICT')
    parameters();profile=correction(args.correction)
    output=new_output(args.output,approved=args.output)  # --output redefines the approved location
    record=disk_record(output,'preflight_v2',start=True)
    receipt,catalog,geometry=source_inputs()
    if args.check_only:
        print(json.dumps({'status':'APPROVED_V2_INPUTS_VERIFIED','correction_sha256':CORRECTION_SHA,'disk':record}))
    else:revise(output,profile,receipt,catalog,geometry)
    return 0


if __name__=='__main__':
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    raise SystemExit(main(argv))

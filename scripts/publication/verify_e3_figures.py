"""Focused source/pixel/projection checks for the #668 delivered figures."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from e3_figures import ROOT_PINS
from e3_coverage import BOUNDS, CELL, HEIGHTS, SCENE_SHA, camera_position, load_triangles, segment_blocked


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(output, evidence, assets):
    manifest = json.loads((output/'MANIFEST.json').read_bytes())
    provenance = json.loads((output/'PROVENANCE.json').read_bytes())
    for entry in manifest['files']:
        data = (output/entry['path']).read_bytes()
        assert len(data)==entry['bytes'] and sha(data)==entry['sha256'], entry['path']
    assert manifest['bytes']==sum(e['bytes'] for e in manifest['files'])
    assert manifest['file_count']==len(manifest['files'])
    assert set(p.name for p in output.iterdir())=={'MANIFEST.json',*(e['path'] for e in manifest['files'])}
    # Recheck only consumed source files, never unselected outputs in input manifests.
    for path,expected in provenance['source_files'].items():
        rel=Path(path).relative_to('local/evidence')
        assert rel.parts[0] in {v[0] for v in ROOT_PINS.values()}
        assert rel.name=='MANIFEST.json' or rel.parts[1] in {'rgb','gt-boxes'}
        data=(evidence/rel).read_bytes()
        assert sha(data)==expected['sha256'] and len(data)==expected['bytes']
    artifacts=provenance['artifacts']
    assert len(artifacts)==26
    assert len([a for a in artifacts if a['kind']=='multicamera_rgb'])==16
    assert len([a for a in artifacts if a['kind']=='evaluation_gt_map'])==8
    assert sorted(p['figure_id'][0] for p in provenance['selection']['points'])==list('AABBCCDD')
    pixels=0
    for art in artifacts:
        data=(output/art['path']).read_bytes();assert sha(data)==art['sha256']
        im=Image.open(io.BytesIO(data)).convert('RGB')
        assert im.size==(art['width'],art['height'])
        if art['kind']=='multicamera_rgb':
            assert not art['gt_overlay'] and len(art['sources'])==8
            assert len(set(r['camera_id'] for r in art['sources']))==8
            for i,rec in enumerate(art['sources']):
                root=ROOT_PINS[rec['root_ref']][0]
                src=(evidence/root/rec['relative_path']).read_bytes()
                assert sha(src)==rec['file_sha256']
                assert rec['frame_index']*200000==art['timestamp_us']==round(rec['timestamp_s']*1e6)
                source=Image.open(io.BytesIO(src)).convert('RGB').resize((640,360),Image.Resampling.NEAREST)
                x,y=48+(i%4)*664,274+(i//4)*442
                actual=im.crop((x,y,x+640,y+360))
                assert np.array_equal(np.array(actual),np.array(source)), (art['path'],rec['camera_id'])
                pixels+=1
        if art['kind']=='evaluation_gt_map':
            assert art['gt_label']=='GT，評分端' and art['occlusion_clipped']
            assert len(art['panels'])==3 and art['gt_trajectory_color']=='#a01b70'
            assert not art['trajectory_interpolation']
    cal=json.loads((assets/'cameras.three.json').read_bytes())
    region=json.loads((output/'COVERAGE.json').read_bytes())
    assert sha((assets/'scene.glb').read_bytes())==SCENE_SHA==region['scene_sha256']
    assert sha((assets/'cameras.three.json').read_bytes())==region['calibration_sha256']
    assert region['cell_m']==CELL and region['body_heights_m']==list(HEIGHTS)
    assert region['minimum_visible_heights']==2 and not region['dynamic_person_occlusion']
    triangles,_=load_triangles(assets/'scene.glb');assert len(triangles)==region['triangles']==6176
    samples=0;per_camera={};mask_checks=0
    for c in cal['cameras']:
        shape=tuple(region['mask_shape'])
        packed=np.frombuffer(base64.b64decode(region['masks'][c['camera_id']]),dtype='uint8')
        mask=np.unpackbits(packed)[:shape[0]*shape[1]].reshape(shape).astype(bool)
        assert int(mask.sum())==region['visible_cells'][c['camera_id']]
        bitmap=Image.fromarray(mask.astype('uint8')*255)
        # Boundary cells represent a 5cm raster approximation, not exact boundaries.
        eroded=np.asarray(bitmap.filter(ImageFilter.MinFilter(5)))>0
        dilated=np.asarray(bitmap.filter(ImageFilter.MaxFilter(5)))>0
        checked=blocked=visible_count=excluded=0
        origin=camera_position(c)
        for iy in range(11,shape[0],31):
            for ix in range(13,shape[1],31):
                if eroded[iy,ix]!=dilated[iy,ix]:excluded+=1;continue
                x=BOUNDS[0]+(ix+.5)*CELL;y=BOUNDS[3]-(iy+.5)*CELL
                visible=inside_count=0
                for height in HEIGHTS:
                    gltf=np.array([x,height,-y,1.])
                    clip=np.array(c['projection_matrix'])@np.array(c['world_to_camera'])@gltf
                    inside=clip[3]>0 and np.all(np.abs(clip[:3])<=clip[3])
                    inside_count+=inside
                    visible+=inside and not segment_blocked(triangles,origin,np.array([x,y,height]))
                expected=visible>=2
                assert bool(mask[iy,ix])==expected,(c['camera_id'],x,y)
                visible_count+=expected;blocked+=inside_count>=2 and not expected;checked+=1
        assert checked>400 and visible_count>0 and blocked>0,c['camera_id']
        per_camera[c['camera_id']]={'independent_rays_checked_cells':checked,'visible_cells_sampled':int(visible_count),'occluded_in_frustum_cells_sampled':int(blocked),'boundary_cells_excluded':excluded}
        samples+=checked
        # Check that every displayed panel points along calibrated optical -Z.
        m=np.array(c['camera_to_world']);expected=np.array([-m[0,2],m[2,2]]);expected/=np.linalg.norm(expected)
        for art in artifacts:
            for panel in art.get('panels',[]):
                if panel['camera_id']==c['camera_id']:
                    assert np.allclose(panel['position_blender_xyz_m'],origin)
                    assert np.allclose(panel['forward_xy_unit'],expected)
                    mask_checks+=1
    assert mask_checks==32
    with (output/'overview.csv').open() as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==16 and sum(int(r['primary_decision_points']) for r in rows)==68
    assert round(sum(float(r['duration_s']) for r in rows),1)==1044.6
    for point in provenance['selection']['points']:
        row=next(r for r in rows if r['case_id']==point['case_id'])
        assert row['type']==point['figure_id'][0]
    assert pixels==128
    assert not provenance['agent_rule_outputs_read']
    assert provenance['paid_api_calls']==provenance['blender_renders']==0
    return {'manifest_entries_verified':len(manifest['files']),
            'source_files_verified':len(provenance['source_files']),
            'pngs_verified':len(artifacts),'exact_full_tile_pixel_comparisons':pixels,
            'independent_mesh_visibility_cells':samples,'camera_heading_panel_checks':mask_checks,
            'coverage_checks_by_camera':per_camera,
            'corpus_cases':16,'primary_decision_points':68,'duration_s':1044.6,
            'mismatches':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--evidence-root',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(verify(a.output,a.evidence_root,a.assets),ensure_ascii=False))


if __name__=='__main__':
    main()

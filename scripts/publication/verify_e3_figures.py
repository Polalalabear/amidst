"""Focused source/pixel/projection checks for the #668 delivered figures."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from e3_figures import ROOT_PINS, footprint


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
    assert len(artifacts)==25
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
            assert art['gt_label']=='GT，評分端' and not art['occlusion_clipped']
            assert not art['trajectory_interpolation']
    # Independent sample-grid membership vs homogeneous projection: catches
    # transpose, world-axis inversion and frustum clipping sign mistakes.
    cal=json.loads((assets/'cameras.three.json').read_bytes())
    samples=0
    for c in cal['cameras']:
        bounds=(-15,23,-10,18);poly=footprint(c,bounds)
        assert len(poly)>=3
        for x in np.linspace(-14.91,22.91,21):
            for y in np.linspace(-9.89,17.89,21):
                gltf=np.array([x,0,-y,1.])
                clip=np.array(c['projection_matrix']) @ np.array(c['world_to_camera']) @ gltf
                expected=clip[3]>0 and all(abs(clip[k])<=clip[3] for k in range(3))
                # Convex polygon inclusion by all edge cross products.
                crosses=[(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]) for a,b in zip(poly,poly[1:]+poly[:1])]
                actual=all(v>=-1e-8 for v in crosses) or all(v<=1e-8 for v in crosses)
                assert bool(actual)==bool(expected),(c['camera_id'],x,y)
                samples+=1
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
            'fov_projection_grid_comparisons':samples,
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

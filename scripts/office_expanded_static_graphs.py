"""Source-bound graph compilation/verification for #418, separate from r004.

Static coverage requires an explicit per-frame review. Calibration projections
only locate proposed portal ROIs; all edges/transitions remain topological/DRAFT.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from amidst.q1q5.graphs import load_graphs
from amidst.q1q5.store import canonical_hash
from build_office_expanded_static import PARAMETERS, PARAMETER_SHA, OUTPUT, canonical, no_links, require, sha
from revise_office_static_preview import CORRECTION, CORRECTION_SHA, SOURCE_SHA, SOURCE_RECEIPT_SHA, AUTHORIZATION

ROOT=Path(__file__).resolve().parents[1]
DESTINATION=ROOT/'configs/q1q5/graphs/office_expanded_r005'
REVIEW=ROOT/'docs/engineering/d127_418_static_review.json'


def parse(raw):
    def unique(items):
        out={}
        for k,v in items:
            require(k not in out,'DUPLICATE_KEY');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=unique,
                      parse_constant=lambda _:require(False,'NONFINITE_JSON'))


def verify_local(root, expected_receipt_sha=None):
    """Read only this new scene's exact allowlist; never search other run roots."""
    root=no_links(root);require(root.is_dir(),'BUNDLE_MISSING')
    raw=no_links(root/'build_receipt.json').read_bytes()
    if expected_receipt_sha is not None:require(sha(raw)==expected_receipt_sha,'RECEIPT_PIN')
    receipt=parse(raw)
    require(receipt['scene_id']=='office_expanded_r005' and receipt['parameter_sha256']==PARAMETER_SHA,
            'WRONG_SCENE_OR_PARAMETERS')
    names={'scene.blend','static/cameras.json','static/regions.json','human_layout/overview.png'}
    names|={'rgb/'+name+'.png' for name in ['CAM_R101_IN','CAM_R102_IN','CAM_R103_IN','CAM_R104_IN','CAM_CORR_W','CAM_CORR_E']}
    require(set(receipt['files'])==names,'EXACT_FILE_SET')
    for rel,entry in receipt['files'].items():
        p=no_links(root/rel);require(p.is_file(),'SOURCE_FILE_MISSING')
        payload=p.read_bytes()
        require(sha(payload)==entry['sha256'] and len(payload)==entry['bytes'],'SOURCE_FILE_PIN')
        if rel.endswith('.png'):
            from PIL import Image
            with Image.open(p) as img:
                require(img.size==(960,540) and img.mode=='RGB','RGB_FORMAT')
                img.load()
    require(receipt['source_sha256']==receipt['files']['scene.blend']['sha256'],'BLEND_PIN')
    catalog=parse((root/'static/cameras.json').read_bytes())
    geometry=parse((root/'static/regions.json').read_bytes())
    require(catalog['source_sha256']==geometry['source_sha256']==receipt['source_sha256'],'SOURCE_CROSS_PIN')
    require(receipt['camera_image_count']==6 and receipt['human_layout_image_count']==1
            and receipt['animation_rendered'] is False and receipt['gt_read'] is False,'STATIC_RENDER_SCOPE')
    producer=receipt.get('builder_source_name','build_office_expanded_static.py')
    require(producer in {'build_office_expanded_static.py','revise_office_static_preview.py'},'PRODUCER_SOURCE_NAME')
    require(sha((ROOT/'scripts'/producer).read_bytes())==receipt['builder_sha256'],'PRODUCER_SOURCE_PIN')
    return receipt,catalog,geometry


def compile_graphs(receipt,catalog,geometry,review,*,catalog_sha,geometry_sha,review_sha,receipt_sha):
    require(sha(PARAMETERS.read_bytes())==PARAMETER_SHA,'APPROVED_PARAMETER_BYTES_CHANGED')
    source=receipt['source_sha256'];scene='office_expanded_r005'
    require(review['scene_id']==catalog['scene_id']==geometry['scene_id']==scene,'CROSS_SCENE')
    require(review['source_sha256']==catalog['source_sha256']==geometry['source_sha256']==source,'REVIEW_SOURCE_PIN')
    require(review['build_receipt_sha256']==receipt_sha and review['parameter_sha256']==PARAMETER_SHA,
            'REVIEW_RECEIPT_PIN')
    require(review['review_method']=='MANUAL_VISUAL_INSPECTION_OF_RENDERED_STATIC_RGB'
            and review['reviewer'] and review['reviewed_at_utc'],'EXPLICIT_REVIEW_REQUIRED')
    require(catalog['run_bindings']==[],'STATIC_ONLY_CATALOG')
    cameras={x['camera_id']:x for x in catalog['cameras']}
    approvals={x['camera_id']:x for x in review['camera_reviews']}
    expected={'CAM_R101_IN':'R101','CAM_R102_IN':'R102','CAM_R103_IN':'R103',
              'CAM_R104_IN':'R104','CAM_CORR_W':'CORR_W','CAM_CORR_E':'CORR_E'}
    require(len(catalog['cameras'])==len(review['camera_reviews'])==6
            and cameras.keys()==approvals.keys()==expected.keys(),'CAMERA_REVIEW_SET')
    inputs=[{'ref':kind+':'+scene,'sha256':pin} for kind,pin in
            [('static',geometry_sha),('calibration',catalog_sha),('static-review',review_sha),
             ('build-receipt',receipt_sha),('authoring-parameters',PARAMETER_SHA)]]
    revision=receipt.get('preview_revision')
    require(revision in {None,'v2'},'PREVIEW_REVISION')
    if revision=='v2':
        require(sha(CORRECTION.read_bytes())==CORRECTION_SHA
                and receipt['preview_correction_sha256']==review['preview_correction_sha256']==CORRECTION_SHA,
                'PREVIEW_CORRECTION_PIN')
        require(receipt['parent_source_sha256']==SOURCE_SHA
                and receipt['parent_receipt_sha256']==SOURCE_RECEIPT_SHA,'PREVIEW_PARENT_PIN')
        require(receipt['authorization_ref']==review['authorization_ref']==AUTHORIZATION,'PREVIEW_AUTHORIZATION')
        inputs.append({'ref':'preview-correction:'+scene,'sha256':CORRECTION_SHA})
    regions=[{'region_id':r['region_id'],'kind':r['kind'],'floor_id':'FLOOR_GROUND',
              'walk_ids':['floor_'+r['region_id']],'polygon_ref':'static-polygon:'+r['region_id'],
              'polygon_sha256':sha(canonical(r['polygon_world_m']))} for r in geometry['regions']]
    edges=[{'edge_id':p['edge_id'],'regions':p['regions'],
            'via':{'kind':'ADJACENT' if p['edge_id']=='E_CORR_JOIN' else 'PORTAL','ref':'static:'+p['edge_id']},
            'direction':'BIDIRECTIONAL','state':'UNKNOWN','traversability':'TOPOLOGICAL_ONLY',
            'basis_refs':['static:'+geometry_sha]} for p in geometry['portals']]
    common={'scene_id':scene,'scene_revision':'r005','approval_status':'DRAFT','approval_ref':None,'inputs':inputs}
    r={**deepcopy(common),'schema_version':'q-demo.region-graph.v1','scene_static_sha256':source,
       'regions':regions,'edges':edges}
    rows=[]
    for name,camera in cameras.items():
        rec=approvals[name];rel='rgb/'+name+'.png'
        require(camera['source_sha256']==source,'CAMERA_SOURCE_PIN')
        require(rec['static_frame_file']==rel and rec['static_frame_sha256']==receipt['files'][rel]['sha256']
                and rec['calibration_sha256']==camera['calibration_sha256'],'REVIEW_FRAME_OR_CALIBRATION_PIN')
        require(rec['region_id']==expected[name] and rec['region_visible'] is True,'REGION_NOT_REVIEWED_VISIBLE')
        require(sha(canonical({k:v for k,v in camera.items() if k!='calibration_sha256'}))==camera['calibration_sha256'],
                'CALIBRATION_CONTENT_PIN')
        exits=[];entries=[]
        for roi in camera['portal_rois']:
            require(roi['basis']=='STATIC_CALIBRATION_PROJECTION','ROI_BASIS')
            eid=roi['edge_id'];poly=roi['roi_polygon_px']
            require(all(0<=x<=960 and 0<=y<=540 for x,y in poly),'ROI_BOUNDS')
            exits.append({'exit_zone_id':name+':EXIT:'+eid,'roi_polygon_px':poly,'leads_to_edge_ids':[eid],
                'mapping_basis':'STATIC_CALIBRATION_PROJECTION','static_frame_ref':'static-frame:'+name,
                'static_frame_sha256':rec['static_frame_sha256']})
            entries.append({'entry_zone_id':name+':ENTRY:'+eid,'roi_polygon_px':poly})
        rows.append({'camera_id':name,'calibration_sha256':camera['calibration_sha256'],
                     'covered_regions':[{'region_id':rec['region_id'],'basis':'MANUAL_ON_STATIC_FRAME',
                       'visibility_ref':'static-review:'+review_sha+':'+name,'visible_area_m2':None}],
                     'exit_zones':exits,'entry_zones':entries})
    transitions=[]
    for edge in edges:
        left,right=edge['regions']
        a=next(cam for cam,region in expected.items() if region==left)
        b=next(cam for cam,region in expected.items() if region==right)
        for source_camera,target_camera,path in [(a,b,[left,right]),(b,a,[right,left])]:
            eid=edge['edge_id']
            transitions.append({'transition_id':'T_'+source_camera+'_'+target_camera,
                'from_camera_id':source_camera,'to_camera_id':target_camera,
                'via_exit_zone_ids':[source_camera+':EXIT:'+eid],'to_entry_zone_ids':[target_camera+':ENTRY:'+eid],
                'region_path':path,'edge_path':[eid],'relation':'UNKNOWN','region_hops':1,
                'path_traversability':'TOPOLOGICAL_ONLY','path_has_unknown_state':True,
                'ranking_area_m2':None,'ranking_area_refs':[],'nominal_path_length_m':None,
                'basis_refs':['static:'+geometry_sha,'calibration:'+catalog_sha]})
    c={**deepcopy(common),'schema_version':'q-demo.camera-transition-graph.v1',
       'region_graph_sha256':None,'camera_catalog_sha256':catalog_sha,'cameras':rows,'transitions':transitions}
    for doc,prefix in [(r,'rgraph'),(c,'cgraph')]:
        if prefix=='cgraph':doc['region_graph_sha256']=r['content_sha256']
        doc['content_sha256']=canonical_hash(doc,exclude=('graph_id','content_sha256','stats'))
        doc['graph_id']=f"{prefix}:r005:static:{doc['content_sha256'][:16]}"
    load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'])
    return r,c


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle-root',type=Path,default=OUTPUT)
    p.add_argument('--review',type=Path,default=REVIEW)
    p.add_argument('--destination',type=Path,default=DESTINATION)
    p.add_argument('--verify-only',action='store_true')
    args=p.parse_args(argv)
    receipt,catalog,geometry=verify_local(args.bundle_root)
    review_raw=no_links(args.review).read_bytes();review=parse(review_raw)
    receipt_raw=(args.bundle_root/'build_receipt.json').read_bytes()
    catalog_raw=(args.bundle_root/'static/cameras.json').read_bytes()
    geometry_raw=(args.bundle_root/'static/regions.json').read_bytes()
    r,c=compile_graphs(receipt,catalog,geometry,review,catalog_sha=sha(catalog_raw),
          geometry_sha=sha(geometry_raw),review_sha=sha(review_raw),receipt_sha=sha(receipt_raw))
    raw_files={'cameras.json':catalog_raw,'regions.json':geometry_raw,'build_receipt.json':receipt_raw,
               'coverage_review.json':review_raw,'region_graph.json':json.dumps(r,indent=2).encode()+b'\n',
               'camera_graph.json':json.dumps(c,indent=2).encode()+b'\n'}
    pins={'scene_id':'office_expanded_r005','source_sha256':receipt['source_sha256'],
          'parameter_sha256':PARAMETER_SHA,'authorization_ref':receipt['authorization_ref'],
          'files':{name:sha(raw) for name,raw in raw_files.items()},
          'region_content_sha256':r['content_sha256'],'camera_content_sha256':c['content_sha256'],
          'physical_navigation':'UNKNOWN','collision':'UNKNOWN','gt_read':False}
    if receipt.get('preview_revision')=='v2':
        pins.update(preview_revision='v2',preview_correction_sha256=CORRECTION_SHA,
                    parent_source_sha256=SOURCE_SHA,parent_receipt_sha256=SOURCE_RECEIPT_SHA)
    raw_files['source_pins.json']=json.dumps(pins,indent=2).encode()+b'\n'
    destination=no_links(args.destination)
    if args.verify_only:
        require(destination.is_dir(),'GRAPH_DESTINATION_MISSING')
        require(all((destination/name).read_bytes()==raw for name,raw in raw_files.items()),'GRAPH_OUTPUT_PIN')
    else:
        require(not destination.exists(),'GRAPH_DESTINATION_EXISTS');destination.mkdir(parents=True)
        for name,raw in raw_files.items():(destination/name).write_bytes(raw)
    print(json.dumps({'status':'SOURCE_BOUND_STATIC_GRAPHS_VERIFIED','rooms':4,'cameras':6,
                      'transitions':len(c['transitions']),'physical_navigation':'UNKNOWN',
                      'region_pin':r['content_sha256'],'camera_pin':c['content_sha256']}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())

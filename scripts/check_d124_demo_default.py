#!/usr/bin/env python3
"""Explicit DEMO_DEFAULT mechanical index / local RULE_ONLY profile, not formal approval."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from amidst.q1q5.demo_default_index import D124DemoRun, require, sha, loads, canonical, free_space
from amidst.q1q5.linker import LinkParameters, LocalLinker

INDEX_CHECKS = {'DOCUMENT_LOADABLE', 'SCHEMA_VALID', 'NO_FORBIDDEN_CONTENT',
 'CONTENT_HASH_RECOMPUTE', 'ID_DERIVED_FROM_HASH', 'COMMON_GT_READ_FALSE',
 'INDEX_MANIFEST_RULES', 'INDEX_RECORDS_FILE_HASH', 'RECORDS_FRAME_STATE',
 'RECORDS_OBSERVATION_IDS', 'RECORDS_INDEX_GRID', 'RECORDS_COLOR_RULES',
 'RECORDS_MATCH_MANIFEST', 'RECORDS_SCORE_FLOOR'}


def read_bound(root, cfg):
    receipt = loads((root / 'demo_default_receipt.json').read_bytes())
    require(receipt['profile'] == 'DEMO_DEFAULT' and receipt['formal_eligible'] is False, 'DEMO_SCOPE')
    raw = (root / 'detection_index.json').read_bytes()
    records_raw = (root / 'detection_index.records.jsonl').read_bytes()
    manifest = loads(raw)
    require(sha(raw) == receipt['index_manifest_sha256'], 'INDEX_BYTE_PIN')
    require(sha(records_raw) == manifest['records_file_sha256'] == receipt['records_file_sha256'], 'RECORDS_BYTE_PIN')
    require(all(manifest[k] == cfg[k] for k in ['scene_id','run_id','clock_id','scene_revision']), 'SCOPE')
    require(manifest['detector']['index_score_floor'] == cfg['index_score_floor'], 'SCORE_CONFIG')
    return receipt, raw, records_raw, manifest


def conformance(raw, records_raw, cfg):
    # Load the two named checker modules only; avoid evaluation package side effects.
    def module(name, rel):
        spec = importlib.util.spec_from_file_location(name, ROOT / rel)
        obj = importlib.util.module_from_spec(spec);sys.modules[name] = obj;spec.loader.exec_module(obj)
        return obj
    module('amidst.evaluation.response_versions', 'src/amidst/evaluation/response_versions.py')
    kit = module('_d131_index_conformance', 'src/amidst/evaluation/q1q5_conformance.py')
    docs = [kit.Doc('detection_index.json','detection_index',loads(raw),sha(raw),stem='detection_index'),
            kit.Doc('detection_index.records.jsonl','detection_records',[loads(r) for r in records_raw.splitlines() if r],sha(records_raw),stem='detection_index',role='records')]
    checks = kit.run_checks(docs, params=cfg, only=INDEX_CHECKS)
    require(checks and all(c['status']=='PASS' for c in checks), 'QT25_DEMO_PROFILE_FAILED:' + json.dumps([c for c in checks if c['status']!='PASS']))
    return {'status':'PASS','checks':checks,'checker_source_sha256':sha((ROOT/'src/amidst/evaluation/q1q5_conformance.py').read_bytes()),'scope':'14 named index contract checks; DEMO_DEFAULT parameters are not approved'}


def local_rule_tracks(manifest, records_raw, cfg):
    values = {p['name']:p['value'] for p in cfg['parameters']}
    digest = sha(canonical(cfg))
    params = LinkParameters('demo-default:'+digest[:16],digest,manifest['index_id'],cfg['run_id'],200000,
        values['link_max_gap_us'],values['link_max_gap_samples'],values['link_iou_min'],
        values['link_center_dist_max_diag_ratio'],values['link_min_score'],values['link_color_rule'],values['link_ambiguity_margin'])
    rows = [loads(line) for line in records_raw.splitlines() if line]
    output = []
    for camera in sorted(c['camera_id'] for c in manifest['sampling']['per_camera']):
        sequence = sorted((dict(r,run_id=cfg['run_id'],clock_id=cfg['clock_id']) for r in rows if r['camera_id']==camera),key=lambda r:r['frame_index'])
        selected = None
        for i,row in enumerate(sequence):
            eligible = [o for o in row.get('detections') or [] if o['class_label']=='person' and o['score']>=values['link_min_score']]
            if eligible:
                selected=(i,row,eligible);break
        if selected is None:
            output.append({'camera_id':camera,'status':'NO_SIGHTING','seed':None,'steps':[]});continue
        i,seed,candidates=selected
        if len(candidates)!=1:
            output.append({'camera_id':camera,'status':'UNKNOWN_AMBIGUOUS_SEED','seed':None,'steps':[]});continue
        selected_id=candidates[0]['observation_id']
        linker=LocalLinker(seed,selected_id,parameters=params,stride_samples=cfg['stride_samples'],index_grid_origin_frame=cfg['index_grid_origin_frame'])
        steps=[]
        for row in sequence[i+1:]:
            step=linker.step(row);steps.append(asdict(step))
            if step.state=='SEARCHING':break
        output.append({'camera_id':camera,'status':'LOCAL_SEGMENT','seed':{'observation_id':selected_id,'timestamp_us':seed['timestamp_us'],'frame_ref':seed['frame_ref']},'steps':steps})
    return {'mode':'RULE_ONLY','parameter_mode':'DEMO_DEFAULT','formal_eligible':False,
        'scope':'CAMERA_LOCAL_SELECTED_SEED','selection_policy':'FIRST_FRAME_WITH_PERSON; EXACTLY_ONE_ELSE_UNKNOWN',
        'identity_verdict':'UNCONFIRMED','cross_camera_association':'NOT_EVALUATED','physical_navigation':'UNKNOWN',
        'source_index_sha256':sha(canonical(manifest)),'source_records_sha256':sha(records_raw),'config_content_sha256':digest,'tracks':output}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index-dir',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--config-sha256',required=True);p.add_argument('--safe-bundle',type=Path,required=True)
    p.add_argument('--produce-local-tracks',action='store_true')
    a=p.parse_args();cfg_raw=a.config.read_bytes();require(sha(cfg_raw)==a.config_sha256,'CONFIG_BYTE_PIN');cfg=loads(cfg_raw)
    receipt,raw,records_raw,manifest=read_bound(a.index_dir,cfg)
    source=D124DemoRun(a.safe_bundle,cfg)
    require(manifest['rgb_index_sha256']==source.source_projection['rgb_index_projection_sha256'],'SOURCE_PROJECTION')
    require(receipt['config_file_sha256']==a.config_sha256,'CONFIG_RECEIPT')
    qt=conformance(raw,records_raw,cfg)
    tracks=local_rule_tracks(manifest,records_raw,cfg)
    target=a.index_dir/'cx8_rule_only.json'
    if a.produce_local_tracks:
        free_space(a.index_dir)
        with target.open('xb') as f:f.write(canonical(tracks)+b'\n')
    actual=loads(target.read_bytes());require(canonical(actual)==canonical(tracks),'CX8_SOURCE_REPLAY_MISMATCH')
    result={'profile':'DEMO_DEFAULT','formal_eligible':False,'production_gate':'NOT_RUN','qt25t':qt,
        'cx8t':{'status':'PASS','scope':tracks['scope'],'camera_tracks':len(tracks['tracks']),
        'local_segments':sum(t['status']=='LOCAL_SEGMENT' for t in tracks['tracks']),
        'steps':sum(len(t['steps']) for t in tracks['tracks']),'cross_camera_association':'NOT_EVALUATED'},
        'cx8_file_sha256':sha(target.read_bytes()),'config_sha256':a.config_sha256}
    with (a.index_dir/'demo_checker.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps({'QT25_DEMO':qt['status'],'CX8_DEMO':result['cx8t'],'formal_eligible':False}))

if __name__=='__main__':main()

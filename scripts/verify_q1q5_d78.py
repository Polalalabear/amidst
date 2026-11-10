"""Pinned engineering-index execution/replay; no detector, RGB, GT or labels read."""
import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from amidst.q1q5.api import QAPI, RecordingStore, from_environment
from amidst.q1q5.production_preflight import read_pinned, strict_json


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2)+"\n")


def metrics(response, links, decisions):
    switches=[d for d in decisions if d['accepted'] and d['executed_action']=='SWITCH']
    entries=[d for d in decisions if d.get('cause_decision_id') in {s['decision_id'] for s in switches}]
    return {'gaps_us':[s['range_us'] for s in response['timeline'] if s['kind']=='GAP'],
        'first_gap_us':next((s['range_us'][0] for s in response['timeline'] if s['kind']=='GAP'),None),
        'switch_decision_times_us':[s['decision_time_us'] for s in switches],
        'switch_entry_times_us':[s['source_time_us'] for s in entries] or [s['source_time_us'] for s in switches],
        'first_gap_after_seed_us':next((s['range_us'][0] for s in response['timeline'] if s['kind']=='GAP' and s['range_us'][0]>=next((x['range_us'][0] for x in response['timeline'] if x['kind']=='ON_CAMERA'),0)),None),
        'reacquired_count':sum(d['accepted'] and d['state_before']=='TEMP_LOST' and d['state_after']=='PLAYING' for d in decisions),
        'motion_reacquired_count':sum((l.get('matching_audit') or {}).get('event')=='REACQUIRED' and l['matching_audit']['method']=='CENTER_TRANSLATION_V1' for l in links),
        'motion_reference_count':sum((l.get('matching_audit') or {}).get('method')=='CENTER_TRANSLATION_V1' for l in links),
        'false_reacquisition':None,'independent_correctness':None,'agent_attempted':response['agent_attempted'],
        'agent_used':response['agent_used'],'fallback_used':response['fallback_used'],'fallback_reason':response['fallback_reason'],
        'output_sha256':response['output_sha256'],'decisions_sha256':response['decisions_sha256'],'links_sha256':response['links_sha256']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['registry','request']:
        p.add_argument('--'+name,type=Path,required=True);p.add_argument('--'+name+'-sha256',required=True)
    p.add_argument('--runtime',type=Path);p.add_argument('--runtime-sha256')
    p.add_argument('--allow-local-model-calls',action='store_true')
    p.add_argument('--selected-observation-id',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference-response',type=Path);p.add_argument('--reference-response-sha256')
    p.add_argument('--reference-links',type=Path);p.add_argument('--reference-links-sha256')
    p.add_argument('--reference-decisions',type=Path);p.add_argument('--reference-decisions-sha256')
    a=p.parse_args(argv)
    if a.output.exists() or a.output.resolve()!=a.output or not a.output.parent.is_dir():p.error('new canonical output required')
    if bool(a.runtime)!=bool(a.runtime_sha256) or bool(a.runtime)!=a.allow_local_model_calls:p.error('runtime pins and explicit model permission must agree')
    if shutil.disk_usage(a.output.parent).free<8*1024**3:p.error('DISK_BELOW_8_GIB')
    a.output.mkdir();save(a.output/'df-before.json',{'df_k':subprocess.check_output(['df','-k',str(a.output)],text=True)})
    read_pinned(a.registry,a.registry_sha256);request=strict_json(read_pinned(a.request,a.request_sha256))
    os.environ['AMIDST_Q1Q5_REGISTRY']=str(a.registry);os.environ['AMIDST_Q1Q5_REGISTRY_SHA256']=a.registry_sha256
    for key in ['AMIDST_Q1Q5_OLLAMA_RUNTIME','AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256']:os.environ.pop(key,None)
    if a.runtime:
        read_pinned(a.runtime,a.runtime_sha256)
        os.environ['AMIDST_Q1Q5_OLLAMA_RUNTIME']=str(a.runtime);os.environ['AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256']=a.runtime_sha256
    api=from_environment(None,Path(__file__).resolve().parents[1]);(a.output/'recordings').mkdir();store=RecordingStore(a.output/'recordings',repo_root=Path(__file__).resolve().parents[1],max_bytes=16_777_216)
    api.recording_store=store
    def auth(token,scene,*,audit=False):
        if token!=request['session_ref'] or scene!=request['scene_id']:raise ValueError('denied')
    rows={}
    for mode in (['RULE_ONLY','AGENT_SEQUENTIAL'] if a.runtime else ['RULE_ONLY']):
        q=json.loads(json.dumps(request));q['switch_mode']=mode;started=time.perf_counter()
        response=api.call('q2_select_seed',{'request':q,'selected_observation_id':a.selected_observation_id},auth)
        wall_ms=(time.perf_counter()-started)*1000;directory=a.output/mode;directory.mkdir()
        key=(q['session_ref'],response['session_id']);bundle=api.responses[key]
        for name in ['decisions','links']:(directory/(name+'.jsonl')).write_text(bundle[name])
        save(directory/'response.json',response);save(directory/'request.json',q)
        receipt=api.call('q_record_response',{'session_ref':q['session_ref'],'response_ref':response['session_id']},auth)
        descriptor={k:receipt[k] for k in ['recording_id','file','file_sha256']}
        replay=QAPI(max_responses=128,max_media_refs=4096,recording_store=store,recordings=[descriptor])
        played=replay.call('q_recorded_response',{'session_ref':q['session_ref'],'recording_id':receipt['recording_id']},auth)
        assert response==played
        row=metrics(response,[json.loads(l) for l in bundle['links'].splitlines()],[json.loads(l) for l in bundle['decisions'].splitlines()])
        row.update(wall_latency_ms=wall_ms,recording=descriptor,replay_equal=True,replay_output_sha256=played['output_sha256'],model_calls=len((bundle.get('agent_trace') or {}).get('events',[])))
        rows[mode]=row
    # Reference outputs are opened only after new outputs/recordings are frozen.
    if a.reference_response:
        old=strict_json(read_pinned(a.reference_response,a.reference_response_sha256))
        links=[json.loads(l) for l in read_pinned(a.reference_links,a.reference_links_sha256).splitlines()]
        decisions=[json.loads(l) for l in read_pinned(a.reference_decisions,a.reference_decisions_sha256).splitlines()]
        rows['REFERENCE']=metrics(old,links,decisions)
    report={'schema_version':'q-demo.d78-engineering-receipt.v1','source_kind':'SYNTHETIC','formal_eligible':False,'gt_read':False,
        'registry_file_sha256':a.registry_sha256,'request_file_sha256':a.request_sha256,'selected_observation_id':a.selected_observation_id,
        'runtime_file_sha256':a.runtime_sha256,'modes':rows,'independent_correctness':None,'provider_cancellation_confirmed':None}
    save(a.output/'RESULT.json',report);save(a.output/'df-after.json',{'df_k':subprocess.check_output(['df','-k',str(a.output)],text=True)})
    print(json.dumps(report))
    return 0


if __name__=='__main__':raise SystemExit(main())

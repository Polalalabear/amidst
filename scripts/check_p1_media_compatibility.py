"""Compare original and stripped P1 using only existing RGB/index/replay evidence.

No detector/model/renderer runs. Both P1 instances get new external state roots.
Source clocks, timeline and decisions must stay equal; served media use separate
source/served pins. This checks current behavior, not formal demo acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from amidst.q1q5.p1_workbench import P1
from amidst.q1q5.store import canonical_hash


def capture(root,pin,state,scope):
    app=P1(root,pin,state,tracking_scope=scope,
           tracking_scope_pin=hashlib.sha256(scope.read_bytes()).hexdigest() if scope else None)
    run=app.bootstrap()['runs'][0]
    token=app.call('session',{'role':'demo'})['session_ref']
    if scope:
        request={'schema_version':'q-demo.q2-request.v1','session_ref':token,
            'scene_id':run['scene_id'],'run_ids':[run['run_id']],
            'time':{'kind':'SOURCE','run_id':run['run_id'],'range_us':[0,8_000_000]},
            'seed':{'kind':'APPEARANCE','class_label':'person','color':{'label':'red','min_verdict':'STRONG'}},
            'switch_mode':'RULE_ONLY','parameter_set_id':run['parameter_set_id']}
        choices=app.call('q2_seed_candidates',request)['candidates']
        selected=next(c for c in choices if c['camera_id']=='A')
        response=app.call('q2_select_seed',{'request':request,'selected_observation_id':selected['observation_id']})
    else:
        response=app.call('q_recorded_response',{'session_ref':token,'recording_id':'2777741d96ac9aff5bffb2f61a4d2938'})
    bundle=app.api.responses[(token,response['session_id'])]
    media=[]
    for time_us in [2_450_000,2_500_000,5_100_000,5_150_000,5_200_000]:
        result=app.call('q_frames',{'session_ref':token,'scene_id':run['scene_id'],
            'run_id':run['run_id'],'timestamp_us':time_us,'camera_ids':['A','B']})
        for tile in result['tiles']:
            if tile['status']=='READY':
                # Read through the actual adapter grant; its returned bytes are what HTTP serves.
                grant=tile['media_url'].split('token=',1)[1]
                raw=app.rgb.media(grant)
                assert hashlib.sha256(raw).hexdigest()==tile['served_sha256']
                media.append({'time_us':time_us,'camera_id':tile['camera_id'],
                              'source_sha256':tile['file_sha256'],'served_sha256':tile['served_sha256']})
    # P1 intentionally generates per-session references. Preserve their aliasing
    # bijectively by position, while comparing every evidence/time/state field.
    references = {response['session_id']: 'SESSION'}
    for i, segment in enumerate(response['timeline']):
        if segment.get('segment_id'):
            references.setdefault(segment['segment_id'], f'TIMELINE_SEGMENT:{i}')
    for i, snapshot in enumerate(bundle['snapshots']):
        if snapshot.get('candidate_snapshot_sha256'):
            references.setdefault(snapshot['candidate_snapshot_sha256'], f'SNAPSHOT:{i}')
    def stable(value):
        if isinstance(value, dict):return {key:stable(item) for key,item in value.items()}
        if isinstance(value, list):return [stable(item) for item in value]
        if isinstance(value, str):return references.get(value, value.replace(response['session_id'], 'SESSION'))
        return value
    decisions=[json.loads(line) for line in bundle['decisions'].splitlines() if line.strip()]
    for record in decisions:
        if canonical_hash(record, exclude=('content_sha256',)) != record['content_sha256']:
            raise ValueError('ORIGINAL_DECISION_INTEGRITY_FAILED')
    decisions = stable(decisions)
    for record in decisions:
        record['content_sha256'] = canonical_hash(record, exclude=('content_sha256',))
    return {'status':response['status'],'timeline':stable(response['timeline']),
            'decisions':decisions,'snapshots':stable(bundle['snapshots']),
            'clock':run['clock_mapping'],'media':media}



def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--source-manifest-sha256',required=True)
    p.add_argument('--target',type=Path,required=True);p.add_argument('--target-manifest-sha256',required=True)
    p.add_argument('--scope',type=Path,required=True);p.add_argument('--state-parent',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    args=p.parse_args(argv)
    args.state_parent.mkdir(exist_ok=False)
    results={}
    for mode,scope in [('recorded',None),('live',args.scope)]:
        original=capture(args.source,args.source_manifest_sha256,args.state_parent/('source-'+mode),scope)
        stripped=capture(args.target,args.target_manifest_sha256,args.state_parent/('target-'+mode),scope)
        equal={key:original[key]==stripped[key] for key in original}
        if not all(equal.values()):
            def differences(a,b,path=''):
                if type(a)!=type(b):return [path+':TYPE']
                if isinstance(a,dict):
                    if a.keys()!=b.keys():return [path+':KEYS']
                    return [v for key in a for v in differences(a[key],b[key],path+'/'+key)]
                if isinstance(a,list):
                    if len(a)!=len(b):return [path+':LENGTH']
                    return [v for i,(x,y) in enumerate(zip(a,b)) for v in differences(x,y,path+'/'+str(i))]
                return [] if a==b else [path]
            print(json.dumps({'mode':mode,'mismatch_paths':differences(original,stripped)[:40]}),flush=True)
            raise ValueError('COMPATIBILITY_MISMATCH:'+str(equal))
        results[mode]={'equal':equal,'status':stripped['status'],
                       'timeline':stripped['timeline'],
                       'decisions_sha256':canonical_hash(stripped['decisions']),
                       'snapshots_sha256':canonical_hash(stripped['snapshots']),
                       'clock_sha256':canonical_hash(stripped['clock']),
                       'media_checks':stripped['media']}
    report={'status':'EQUAL','source_manifest_sha256':args.source_manifest_sha256,
            'target_manifest_sha256':args.target_manifest_sha256,'modes':results,
            'model_executed':False,'rendered':False,
            'comparison_policy':'Session ID and generated segment/snapshot refs mapped bijectively by position; raw decision hashes verified before reference normalization; normalized decision hashes recomputed; all evidence/time/state/source fields compared exactly.'}
    args.report.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'modes':{k:v['equal'] for k,v in results.items()}}))


if __name__=='__main__':main()

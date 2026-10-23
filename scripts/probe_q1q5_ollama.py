"""Real local Qwen on SYNTHETIC bindings; original budgets, private audit replay."""
import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--synthetic',action='store_true',required=True)
    p.add_argument('--base-url',required=True)
    p.add_argument('--model',required=True,choices=['qwen3:1.7b-q4_K_M'])
    p.add_argument('--model-digest',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():p.error('new output directory with existing parent required')
    args.output.mkdir()
    def disk(tag):
        raw=subprocess.check_output(['df','-k',str(args.output)],text=True);(args.output/('df-'+tag+'.txt')).write_text(raw)
        if int(raw.splitlines()[-1].split()[3])<8*1024*1024:raise RuntimeError('DISK_SPACE_BELOW_8_GIB')
    disk('before')
    try:
        root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tests/q1q5'))
        from test_api import run_binding, q2, seed_id, authorize, TOKEN
        from amidst.q1q5.api import QAPI, raw_json
        from amidst.q1q5.ollama_runtime import bind_runs, load_config, RecordedParseProvider
        from amidst.q1q5.q5_agent import AgentController, AgentSettings, RecordedProvider
        from amidst.q1q5.q3_parse import parse_query
        from amidst.q1q5.q4_evidence import candidate_evidence
        from amidst.q1q5.q5_controller import jsonl
        from amidst.q1q5.store import canonical_hash

        def private(name,value):
            fd=os.open(args.output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(raw_json(value))
        base=replace(run_binding(agent=True),agent_factory=None);b=base.bindings;m=b.index.manifest
        def template(name,version):
            text=(root/'configs/q1q5/prompts'/name).read_text()
            return {'text':text,'version':version,'sha256':hashlib.sha256(text.encode()).hexdigest()}
        config={'schema_version':'q-demo.ollama-runtime.v1','applies_to':{'scene_id':m['scene_id'],'scene_revision':m['scene_revision'],'run_id':m['run_id'],
            'detection_index_sha256':b.index_sha256,'parameter_set_sha256':b.parameter_sha256,'clock_mapping_sha256':b.clock_sha256},
            'base_url':args.base_url,'model':args.model,'model_digest':args.model_digest,'options':{'temperature':0,'seed':7},
            'q3_template':template('q3_parse_v1.txt','q3-parse.v1'),'q5_template':template('q5_agent_v1.txt','q5-agent-v1'),
            'agent_authorization_ref':'SYNTHETIC_G3_TEST_ONLY','enable_q3':True,'enable_q5':True}
        config['content_sha256']=canonical_hash(config);private('runtime.json',config)
        runtime_pin=hashlib.sha256((args.output/'runtime.json').read_bytes()).hexdigest()
        config=load_config((args.output/'runtime.json').resolve(),runtime_pin)
        run=bind_runs([base],config)[0];api=QAPI([run],max_responses=128,max_media_refs=4096)
        req={'schema_version':'q-demo.q3-parse-request.v1','session_ref':TOKEN,'text':'車13:00:00到13:00:01','locale':'zh-TW',
             'context':{'scene_id':m['scene_id'],'run_ids':[m['run_id']],'clock_mapping_sha256':b.clock_sha256},'parser_mode':'LLM_WITH_RULE_FALLBACK'}
        q3=api.call('q3_parse',req,authorize);bundle=deepcopy(api.responses[(TOKEN,q3['output_sha256'])]);audit=bundle['q3_provider_audit']
        replay=RecordedParseProvider(audit,expected_sha256=canonical_hash(audit));options=dict(run.q3_options);options['provider']=replay
        q3_replayed,_=parse_query(req,catalog=run.catalog,settings=run.parse_settings,clock_mapping=b.clock,**options)
        replay.assert_consumed();assert q3==q3_replayed
        private('q3-bundle.json',bundle)
        query=q2(run);query['switch_mode']='AGENT_SEQUENTIAL';selected=seed_id(b)
        q5=api.call('q2_select_seed',{'request':query,'selected_observation_id':selected},authorize)
        bundle=deepcopy(api.responses[(TOKEN,q5['session_id'])]);trace=bundle['agent_trace'];private('q5-bundle.json',bundle)
        provider=RecordedProvider(trace,expected_sha256=trace['content_sha256'])
        settings=AgentSettings(config['model'],config['model_digest'],config['options'],config['q5_template']['text'],config['q5_template']['sha256'],config['q5_template']['version'],config['agent_authorization_ref'])
        controller=AgentController(query,bindings=b,evidence_provider=lambda i,s,r,c:candidate_evidence(i,s,r,**c),selected_observation_id=selected,
            provider=provider,agent_settings=settings,round_scheduler=lambda *x:None,clock=provider.clock)
        repeated=controller.run();provider.assert_consumed()
        assert repeated.response['output_sha256']==q5['output_sha256'] and repeated.decisions_bytes.decode()==bundle['decisions'] and repeated.links_bytes.decode()==bundle['links']
        for name,response,request,bundle_name in [('q3',q3,req,'q3-bundle.json'),('q5',q5,query,'q5-bundle.json')]:
            out=args.output/name;out.mkdir();bundle=json.loads((args.output/bundle_name).read_bytes())
            docs={'probe.request.json':request,'probe.response.json':response,'parameter_set.json':b.parameter_set,'detection_index.json':b.index.manifest,
                  'clock_mapping.json':dict(b.clock.document),'region_graph.json':b.graphs.region,'camera_graph.json':b.graphs.camera}
            if name=='q5':
                for i,x in enumerate(bundle['snapshots']):docs[f'{i}.snapshot.json']=x
                for i,x in enumerate(bundle['evidence']):docs[f'{i}.evidence.json']=x
                (out/response['decisions_ref']).write_text(bundle['decisions']);(out/response['links_ref']).write_text(bundle['links'])
            for filename,doc in docs.items():(out/filename).write_bytes(raw_json(doc))
            (out/b.index.manifest['records_ref']).write_bytes(jsonl(b.index.records))
        report={'source_kind':'SYNTHETIC','provider_kind':'REAL_LOCAL_OLLAMA','model':args.model,'model_digest':args.model_digest,
            'runtime_file_sha256':runtime_pin,'q3':{k:q3[k] for k in ['status','parsed_by','llm_parse_used','fallback_used','fallback_reason']},
            'q5':{k:q5[k] for k in ['status','agent_attempted','agent_used','fallback_used','fallback_reason']},
            'q3_provider_calls':len(audit),'q5_provider_calls':len(trace['events']),'q3_replay_equal':True,'q5_replay_equal':True,
            'actual_model_quality_measured':False,'budgets_changed':False,'downstream_q3_provenance':'UNRESOLVED_SECTION_14_23'}
        private('REPORT.json',report);print(json.dumps(report))
    finally:
        disk('after')



if __name__=='__main__':main()

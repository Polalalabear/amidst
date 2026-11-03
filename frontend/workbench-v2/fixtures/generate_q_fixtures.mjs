// Generate mechanical UI recordings from the actual synthetic kernels.
// Requires the Q backend dependencies (#154/#157/#169/#172/#174) plus their tests.
// No model, GT, human question bank, expected answers or original media is read.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { existsSync } from 'node:fs';
const args=process.argv.slice(2);const at=args.indexOf('--output');
if(at<0||!args[at+1])throw new Error('Use --output <new directory> [--python <existing interpreter>]');
const output=resolve(args[at+1]);if(existsSync(output))throw new Error('Output must be a new directory');
const index=args.indexOf('--python');const interpreter=index>=0?args[index+1]:process.env.AMIDST_TEST_PYTHON;
if(!interpreter)throw new Error('An existing Python interpreter is required; no packages are installed');
const repo=fileURLToPath(new URL('../../../',import.meta.url));
const python=String.raw`"""Mechanical UI recordings from actual kernels; no expected answers/labels."""
from pathlib import Path
from dataclasses import replace
from copy import deepcopy
import sys,json,hashlib
s=Path(sys.argv[1]);root=Path(sys.argv[2]);sys.path.insert(0,str(s/'tests/q1q5'))
from test_api import run_binding,q1,q2,authorize,TOKEN,seed_id
from test_q5_agent import bindings,PolicyProvider,auto,AgentController,settings
from amidst.q1q5.api import QAPI,raw_json
from amidst.q1q5.store import canonical_hash
from amidst.q1q5.q3_parse import parse_query
from amidst.q1q5.q3_rules import parse_rule
from amidst.q1q5.llm_provider import FakeProvider
root.mkdir(parents=True,exist_ok=False)
b=bindings(cameras=('A','B','E'));run=run_binding(b,agent=True);catalog=deepcopy(run.catalog);catalog['camera_ids']=['A','B','E'];run=replace(run,catalog=catalog)
api=QAPI([run],max_responses=128,max_media_refs=4096)
bootstrap=api.bootstrap();bootstrap['data_origin']='SYNTHETIC_FIXTURE'
(root/'q-bootstrap.json').write_text(json.dumps({'schema_version':'q-demo.ui-bootstrap-fixture.v1','fixture_id':'FICT_BOOTSTRAP','data_origin':'SYNTHETIC_FIXTURE','bootstrap_json':raw_json(bootstrap).decode()},indent=2))
written={}
def write(name,cases):
 doc={'schema_version':'q-demo.ui-fixture.v1','fixture_id':'FICT_'+name.upper().replace('-','_'),'data_origin':'SYNTHETIC_FIXTURE','not_for_evaluation':True,'cases':cases}
 raw=json.dumps(doc,ensure_ascii=True,indent=2).encode();(root/(name+'.json')).write_bytes(raw);written[name]={'sha256':hashlib.sha256(raw).hexdigest(),'statuses':[json.loads(c['response_json'])['status'] for c in cases]}
def case(request,response,artifacts=None,selected=None,seeds=None):
 if artifacts is None and response.get('schema_version')=='q-demo.q1-response.v1':
  observations=api.responses[(TOKEN,response['output_sha256'])]['observations']
  artifacts={'observation':{k:raw_json(v).decode() for k,v in observations.items()}}
 response=deepcopy(response);response.pop('stats',None)
 return {'request_json':raw_json(request).decode(),'response_json':raw_json(response).decode(),'selected_observation_id':selected,'seed_candidates_json':raw_json(seeds).decode() if seeds else None,'artifacts':artifacts or {}}
q=q1(run)
for name,change in [('q1-ready',{}),('q1-partial',{'time':{'kind':'SOURCE','run_id':run.catalog['run_id'],'range_us':[1000000,3000000]}}),('q1-no-match',{'condition':q['condition']|{'class_label':'car'}}),('q1-out-of-range',{'time':{'kind':'SOURCE','run_id':run.catalog['run_id'],'range_us':[2000000,3000000]}})]:
 request=deepcopy(q)|change;response=api.call('q1_camera_search',request,authorize);write(name,[case(request,response)])
q3cases={}
# Literals reused from existing kernel unit probes, never a human question set.
for name,text in [('q3-parsed','車13:00:00到13:00:10'),('q3-clarification','人'),('q3-unsupported','紅車13:00:00到13:00:10'),('q3-failed','xyzzy')]:
 request={'schema_version':'q-demo.q3-parse-request.v1','session_ref':TOKEN,'text':text,'locale':'zh-TW','context':{'scene_id':run.catalog['scene_id'],'run_ids':[run.catalog['run_id']],'clock_mapping_sha256':run.bindings.clock_sha256},'parser_mode':'RULE_ONLY'}
 response=api.call('q3_parse',request,authorize);q3cases[name]=[case(request,response)]
 if name=='q3-parsed':
  executed=response['structured_query'];no_match=api.call('q1_camera_search',executed,authorize)
  existing=json.loads((root/'q1-no-match.json').read_text())['cases'];write('q1-no-match',existing+[case(executed,no_match)])
for name,cases in q3cases.items():write(name,cases)
def q2case(request,api=api,selected=None):
 seeds=api.call('q2_seed_candidates',request,authorize)
 response=api.call('q2_select_seed',{'request':request,'selected_observation_id':selected},authorize) if selected else api.call('q2_session',request,authorize)
 bundle=api.responses[(TOKEN,response['session_id'])]
 artifacts={'decisions':bundle['decisions'],'links':bundle['links'],'snapshot':{x['candidate_snapshot_sha256']:raw_json(x).decode() for x in bundle['snapshots']},'evidence':{x['evidence_sha256']:raw_json(x).decode() for x in bundle['evidence']},'observation':{k:raw_json(v).decode() for k,v in bundle['observations'].items()}}
 return case(request,response,artifacts,selected,seeds)
request=q2(run);request['seed']={'kind':'OBSERVATION','observation_id':seed_id(run.bindings)}
rule=[q2case(request)]
second=deepcopy(request);second['seed']['observation_id']=seed_id(run.bindings,'B',5);rule.append(q2case(second))
appearance=q2(run)
rule += [q2case(appearance),q2case(appearance,selected=seed_id(run.bindings))]
write('q2-rule',rule)
short=deepcopy(request);short['time']['range_us']=[0,1000000];write('q2-no-support',[q2case(short)])
provider=PolicyProvider(lambda payload,n:auto(payload,n,candidate_index=1))
def factory(q,**args):return AgentController(q,**args,provider=provider,agent_settings=settings(),round_scheduler=lambda *x:None,clock=lambda:0)
agent_api=QAPI([replace(run,agent_factory=factory)],max_responses=128,max_media_refs=4096)
agent=deepcopy(request);agent['switch_mode']='AGENT_SEQUENTIAL';write('q2-agent',[q2case(agent,api=agent_api)])
# Exact Python canonical matrix. These are serialization probes, not answers.
vectors=[]
for value in [{'中文':'雪☃','😀':'𝄞','\ue000':'\x7f'}, {'a':[1,1.0,-0.0,0.00001,0.0001,1000000000000000.0,1e16,1e20,5e-324]}, {'stats':{'latency_ms':1.2},'value':3},[True,None,'\\\n\t']]:
 raw=json.dumps(value,ensure_ascii=True,allow_nan=False);canonical=json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)
 vectors.append({'raw':raw,'canonical':canonical,'sha256':hashlib.sha256(canonical.encode()).hexdigest()})
(root/'q-canonical-vectors.json').write_text(json.dumps(vectors,indent=2))
(root/'q-fixture-receipt.json').write_text(json.dumps({'schema_version':'q-demo.fixture-receipt.v1','source':'ACTUAL_SYNTHETIC_KERNEL_RECORDINGS','not_for_evaluation':True,'files':written},indent=2));print(written)
`;
const result=spawnSync('uv',['--no-cache','run','--no-project','--offline','--python',interpreter,'python','-c',python,repo,output],{
  cwd:repo,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:resolve(repo,'src')},maxBuffer:4000000});
process.stdout.write(result.stdout??'');process.stderr.write(result.stderr??'');if(result.error)throw result.error;
process.exitCode=result.status??1;

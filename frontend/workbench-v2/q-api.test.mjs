import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createQApi,FIXTURE_ORIGIN,buildQ1,buildQ2,buildQ3 } from './q-api.mjs';
import { parseRaw,contentHash,canonicalJSON } from './q-validate.mjs';
const read=async name=>readFile(new URL(`fixtures/${name}.json`,import.meta.url),'utf8');
const localFetch=async path=>({ok:true,status:200,text:()=>read(path.split('/').at(-1).replace('.json',''))});
async function setup(){const api=createQApi({source:FIXTURE_ORIGIN,fetchImpl:localFetch});assert.equal((await api.bootstrap()).ok,true);await api.createSession();return api;}

async function v2Raw(raw){
 const r=parseRaw(raw);r.schema_version=r.schema_version.replace('.v1','.v2');r.reasons=r.reason?[r.reason]:[];
 const time=r.resolved_scope.requested_time;r.resolved_scope.time_range_source=time?`EXPLICIT_${time.kind}`:null;
 r.resolved_scope.tracking_scope_sha256??=null;r.output_sha256=await contentHash(r,{excludeRoot:['output_sha256','stats']});
 return canonicalJSON(r);
}

test('v2 registered Q1/Q2/Q3 replay uses its exact kind and keeps immutable output pins',async()=>{
 for(const name of ['q1-ready','q2-rule','q3-parsed']){
  const b=parseRaw(JSON.parse(await read('q-bootstrap')).bootstrap_json);b.data_origin='LIVE';b.recordings=[{recording_id:'FICT_V2'}];
  const raw=await v2Raw(JSON.parse(await read(name)).cases[0].response_json),calls=[];
  const api=createQApi({fetchImpl:async path=>{calls.push(path);return {ok:true,text:async()=>path==='/api/q_bootstrap'?canonicalJSON(b):raw};}});
  await api.bootstrap();const replay=await api.replay('FICT_V2');assert.equal(replay.ok,true,JSON.stringify(replay.error));
  assert.equal(replay.data.schema_version,parseRaw(raw).schema_version);assert.equal(replay.data.output_sha256,parseRaw(raw).output_sha256);
  assert.deepEqual(calls,['/api/q_bootstrap','/api/q_recorded_response']);
 }
});

test('v2 Q1 fixture artifacts are looked up in Q1 packs',async()=>{
 const doc=JSON.parse(await read('q1-ready'));doc.cases[0].response_json=await v2Raw(doc.cases[0].response_json);
 const api=createQApi({source:FIXTURE_ORIGIN,fetchImpl:async path=>({ok:true,text:async()=>path.endsWith('/q1-ready.json')?JSON.stringify(doc):read(path.split('/').at(-1).replace('.json',''))})});
 await api.bootstrap();await api.createSession();const request=await api.initialRequest('q1');
 const result=await api.query('q1',request);assert.equal(result.ok,true,JSON.stringify(result.error));
 const ref=Object.keys(doc.cases[0].artifacts.observation)[0];
 const artifact=await api.artifact(result.data,'observation',ref);assert.equal(artifact.ok,true,JSON.stringify(artifact.error));
 assert.equal(artifact.data.observation_id,ref);
});

test('fixture is explicit and all actions have typed request fields without review mode',async()=>{
 const api=await setup(),run=api.getBootstrap().runs[0],sid=api.getSession();
 for(const q of [buildQ1(run,sid),buildQ2(run,sid,{kind:'OBSERVATION',observation_id:'example'}),buildQ3(run,sid,'example')])assert.equal(Object.hasOwn(q,'mode'),false);
 const q=await api.initialRequest('q1');const first=await api.query('q1',q);assert.equal(first.ok,true);
 q.origin='Q3_PARSED';assert.equal((await api.query('q1',q)).data.output_sha256,first.data.output_sha256);
 assert.equal((await api.query('q1',{...q,mode:'review'})).ok,false);
 assert.equal((await api.query('q1',{...q,condition:{...q.condition,class_label:'not recorded'}})).error.code,'FIXTURE_REQUEST_NOT_RECORDED');
 assert.equal((await api.mediaGrant('any')).error.code,'FIXTURE_HAS_NO_RGB');
 assert.equal((await api.frames(run,0,run.camera_ids)).data.tiles[0].reason,'FIXTURE_HAS_NO_RGB');
});

test('fixture explicit selection and raw journal/evidence/snapshot pins validate',async()=>{
 const api=await setup();const q=await api.initialRequest('q2');
 q.seed={kind:'APPEARANCE',class_label:'person',color:{label:'red',min_verdict:'STRONG'}};
 const choices=await api.seedCandidates(q);assert.equal(choices.data.status,'CHOICE_REQUIRED');
 assert.equal((await api.query('q2',q)).data.reason,'SEED_SELECTION_REQUIRED');
 const selected=await api.query('q2',q,{selected_observation_id:choices.data.candidates[0].observation_id});assert.equal(selected.ok,true);
 const r=selected.data;const journal=await api.artifact(r,'decisions',r.decisions_ref);assert.equal(journal.ok,true);
 const d=journal.data.find(x=>x.executed_action==='SWITCH');const snapshot=await api.artifact(r,'snapshot',d.candidate_snapshot_sha256);assert.equal(snapshot.ok,true);
 const e=await api.artifact(r,'evidence',d.candidates_considered[0].evidence_sha256);assert.equal(e.ok,true);
 assert.equal((await api.artifact(r,'observation',d.entry_observation_id)).ok,true);
 assert.equal((await api.artifact(r,'evidence','foreign')).ok,false);
});

test('live errors never fetch fixtures and review has no path into outgoing requests',async()=>{
 const calls=[];const api=createQApi({fetchImpl:async(path,options)=>{calls.push([path,options]);return {ok:false,status:503,text:async()=>'{"error_code":"NOT_READY"}'};}});
 assert.equal((await api.bootstrap()).ok,false);assert.equal(calls.length,1);assert.equal(calls[0][0],'/api/q_bootstrap');
 assert.equal(calls.some(([p])=>p.includes('fixtures')||p.includes('review')),false);
});

test('outdated network response is discarded even when its domain hash is valid',async()=>{
 const wrapper=JSON.parse(await read('q-bootstrap'));const bootstrap=parseRaw(wrapper.bootstrap_json);bootstrap.data_origin='LIVE';
 const pack=JSON.parse(await read('q1-ready'));const q=JSON.parse(pack.cases[0].request_json);let release;let calls=0;
 const api=createQApi({fetchImpl:async path=>{
  if(path==='/api/q_bootstrap')return {ok:true,text:async()=>JSON.stringify(bootstrap)};
  calls++;if(calls===1)await new Promise(resolve=>{release=resolve;});return {ok:true,text:async()=>pack.cases[0].response_json};
 }});
 assert.equal((await api.bootstrap()).ok,true);
 const older=api.query('q1',q);await new Promise(resolve=>setTimeout(resolve,0));const newer=await api.query('q1',q);release();
 assert.equal(newer.ok,true,JSON.stringify(newer.error));assert.equal((await older).error.code,'STALE_RESPONSE');
});

test('a valid-hash response for a different live query is rejected',async()=>{
 const wrapper=JSON.parse(await read('q-bootstrap'));const bootstrap=parseRaw(wrapper.bootstrap_json);bootstrap.data_origin='LIVE';
 const pack=JSON.parse(await read('q1-ready'));const q=JSON.parse(pack.cases[0].request_json);q.condition.query_min_score=.6;
 const api=createQApi({fetchImpl:async path=>({ok:true,text:async()=>path==='/api/q_bootstrap'?JSON.stringify(bootstrap):pack.cases[0].response_json})});
 await api.bootstrap();assert.equal((await api.query('q1',q)).error.code,'QUERY_BINDING');
});

test('server mode rejects a fixture-origin bootstrap instead of switching sources',async()=>{
 const wrapper=JSON.parse(await read('q-bootstrap'));
 const api=createQApi({fetchImpl:async()=>({ok:true,text:async()=>wrapper.bootstrap_json})});
 assert.equal((await api.bootstrap()).error.code,'DATA_ORIGIN_MISMATCH');
});

test('late seed choices are discarded after a source/query invalidation',async()=>{const wrapper=JSON.parse(await read('q-bootstrap')),bootstrap=parseRaw(wrapper.bootstrap_json);bootstrap.data_origin='LIVE';const c=JSON.parse(await read('q2-rule')).cases[0];let release;const api=createQApi({fetchImpl:async path=>{if(path==='/api/q_bootstrap')return {ok:true,text:async()=>JSON.stringify(bootstrap)};await new Promise(resolve=>{release=resolve;});return {ok:true,text:async()=>c.seed_candidates_json};}});await api.bootstrap();const pending=api.seedCandidates(parseRaw(c.request_json));await new Promise(resolve=>setTimeout(resolve,0));api.invalidate();release();assert.equal((await pending).error.code,'STALE_RESPONSE');});

test('a registered recording replays while live sources remain available, without provider calls',async()=>{const b=parseRaw(JSON.parse(await read('q-bootstrap')).bootstrap_json);b.data_origin='LIVE';b.recordings=[{recording_id:'FICT_RECORDING',source_kind:'SYNTHETIC'}];const raw=JSON.parse(await read('q2-rule')).cases[0].response_json,calls=[];const api=createQApi({fetchImpl:async(path,opts={})=>{calls.push([path,opts.body]);return {ok:true,text:async()=>path==='/api/q_bootstrap'?JSON.stringify(b):raw};}});await api.bootstrap();const replay=await api.replay('FICT_RECORDING');assert.equal(replay.ok,true);assert.equal(replay.data.output_sha256,parseRaw(raw).output_sha256);assert.deepEqual(calls.map(x=>x[0]),['/api/q_bootstrap','/api/q_recorded_response']);assert.equal((await api.replay('FICT_UNREGISTERED')).error.code,'RECORDED_ONLY');assert.equal(calls.length,2);});

test('recorded output cannot select a changed registered run just because scene/run names match',async()=>{const b=parseRaw(JSON.parse(await read('q-bootstrap')).bootstrap_json);b.data_origin='LIVE';b.recordings=[{recording_id:'FICT_RECORDING'}];b.runs[0].parameter_set_sha256='f'.repeat(64);const raw=JSON.parse(await read('q2-rule')).cases[0].response_json;const api=createQApi({fetchImpl:async path=>({ok:true,text:async()=>path==='/api/q_bootstrap'?JSON.stringify(b):raw})});await api.bootstrap();assert.equal((await api.replay('FICT_RECORDING')).error.code,'REPLAY_SOURCE_BINDING');});

test('D78 live query uses start/poll and authenticated stop invalidates late results',async()=>{
 const {sha256Hex}=await import('./q-validate.mjs');const wrapper=JSON.parse(await read('q-bootstrap'));
 const bootstrap=parseRaw(wrapper.bootstrap_json);bootstrap.data_origin='LIVE';const pack=JSON.parse(await read('q2-rule'));
 const request=JSON.parse(pack.cases[0].request_json);const calls=[];let stopped=false;
 const api=createQApi({fetchImpl:async(path,options)=>{
  const payload=options?.body?JSON.parse(options.body):null;calls.push([path,payload]);let data;
  if(path==='/api/q_bootstrap')data=bootstrap;
  else if(path==='/api/session')data={session_ref:'operator-session'};
  else if(path==='/api/q2_start_session'||path==='/api/q2_poll_session')data={schema_version:'q-demo.session-job.v1',session_id:'sess-stoppable',status:stopped?'STOPPED':'RUNNING',response:null,error_code:stopped?'USER_STOPPED':null};
  else if(path==='/api/q2_stop_session'){stopped=true;data={schema_version:'q-demo.stop-receipt.v1',session_id:'sess-stoppable',reason:'USER_STOPPED',provider_cancelled:null,decisions_jsonl:'',links_jsonl:'',decisions_sha256:await sha256Hex(''),links_sha256:await sha256Hex('')};}
  else throw new Error('Unexpected route '+path);
  return {ok:true,text:async()=>JSON.stringify(data)};
 }});
 await api.bootstrap();await api.createSession();request.session_ref=api.getSession();const pending=api.query('q2',request);
 while(!api.activeJob())await new Promise(resolve=>setTimeout(resolve,1));
 assert.equal((await api.stopSession()).ok,true);assert.equal((await pending).error.code,'STALE_RESPONSE');
 assert.equal(calls.some(([path])=>path==='/api/q2_session'||path==='/api/q2_select_seed'),false);
 assert.deepEqual(calls.find(([path])=>path==='/api/q2_stop_session')[1],{session_ref:'operator-session',response_ref:'sess-stoppable'});
});

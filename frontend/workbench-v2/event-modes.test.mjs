import test from 'node:test';
import assert from 'node:assert/strict';
import {validateSuite,stateAt,comparisonEnd} from './event-modes.mjs';
import {contentHash} from './q-validate.mjs';
async function seal(object,key='content_sha256',exclude=[key]){object[key]=await contentHash(object,{excludeRoot:exclude});return object;}
async function fixture(){
 const scope={scene_id:'SYNTHETIC',run_ids:['SYNTHETIC']},modes=[];
 for(const mode of ['BACKEND_FLAGS','AGENT_DECISIONS']){
  const response=await seal({schema_version:'q-demo.q2-response.v1',identity_verdict:'UNCONFIRMED',provenance:{gt_read:false},resolved_scope:scope,timeline:[{kind:'ON_CAMERA',camera_id:'A',range_us:[0,10]},{kind:'GAP',camera_shown:'A',range_us:[10,30]},{kind:'ON_CAMERA',camera_id:'B',range_us:[30,40]}]},'output_sha256',['output_sha256','stats']);
  modes.push(await seal({mode,response,flags:[],metrics:{provider_calls:mode==='BACKEND_FLAGS'?0:2}}));
 }
 const comparison=await seal({schema_version:'q-demo.event-mode-comparison.v1',source_kind:'SYNTHETIC',counts_for_acceptance:false,gt_read:false,identity_verdict:'UNCONFIRMED',accuracy:null,scope,lost_after_us:20,threshold_status:'EXPERIMENT_ONLY_NOT_APPROVED',modes});
 return seal({schema_version:'q-demo.event-mode-suite.v1',source_kind:'SYNTHETIC',counts_for_acceptance:false,provider_kind:'MECHANICAL_FAKE_PROVIDER',cases:[{case_id:'FICT',offline_trace_replay_equal:true,provider_kind:'MECHANICAL_FAKE_PROVIDER',comparison}]});
}
test('pins all layers and exposes only frozen experimental data',async()=>{const s=await validateSuite(JSON.stringify(await fixture()));assert(Object.isFrozen(s.cases[0].comparison.modes[0]));assert.equal(s.counts_for_acceptance,false);});
test('tampered report is rejected before rendering',async()=>{const s=await fixture();s.cases[0].comparison.modes[0].response.timeline[0].camera_id='OTHER';await assert.rejects(validateSuite(JSON.stringify(s)),/SUITE_HASH/);});
test('formal source or unspecified threshold cannot masquerade as this experiment',async()=>{const s=await fixture();s.source_kind='LIVE';await assert.rejects(validateSuite(JSON.stringify(s)),/SUITE_BOUNDARY/);const x=await fixture();x.cases[0].comparison.lost_after_us=0;await seal(x.cases[0].comparison);await seal(x);await assert.rejects(validateSuite(JSON.stringify(x)),/LOST_POLICY/);});
test('playback retains last camera through GAP and hard cuts at source entry',()=>{const m={response:{timeline:[{kind:'ON_CAMERA',range_us:[0,10],camera_id:'A'},{kind:'GAP',range_us:[10,30]},{kind:'ON_CAMERA',range_us:[30,40],camera_id:'B'}]},flags:[{type:'LOST',timestamp_us:20},{type:'FOUND',timestamp_us:30}]};assert.equal(stateAt(m,19).camera,'A');assert.equal(stateAt(m,19).lost,false);assert.equal(stateAt(m,20).lost,true);assert.equal(stateAt(m,29).camera,'A');assert.equal(stateAt(m,30).camera,'B');assert.equal(stateAt(m,30).lost,false);assert.equal(comparisonEnd({modes:[m]}),40);assert.equal(stateAt(m,0).flags.length,0);});
test('outside timeline and before seed retain unknown support rather than fake observations',()=>{const m={response:{timeline:[{kind:'GAP',range_us:[0,10]}]},flags:[]};assert.equal(stateAt(m,0).camera,'UNKNOWN');assert.equal(stateAt(m,10).supported,false);});

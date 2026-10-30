import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {projectRecordedTimeline,decodeRecordedTimeline,loadP1Recording} from './long-timeline-data.mjs';
import {canonicalJSON,contentHash,sha256Hex} from './q-validate.mjs';
import {wallCells} from './monitor-wall-model.mjs';
const H='1'.repeat(64),C='2'.repeat(64);
function fixture(){
  return {
    clock:{run_id:'run',clock_id:'clock',t0_us:0,source_duration_us:10e6,content_sha256:C},
    index:{run_id:'run',scene_id:'scene',scene_revision:'rSYN',clock_id:'clock',index_id:'index',content_sha256:H,provenance:{gt_read:false},sampling:{per_camera:[
      {camera_id:'A',index_interval_us:1e6,inferred_ranges_us:[[0,4e6]],not_inferred:[{range_us:[4e6,5e6],reason:'MISSING'},{range_us:[5e6,6e6],reason:'DETECTOR_FAILED'}]},
      {camera_id:'B',index_interval_us:1e6,inferred_ranges_us:[[0,10e6]],not_inferred:[]},
    ]}},
    response:{identity_verdict:'UNCONFIRMED',provenance:{gt_read:false},session_id:'session',resolved_scope:{run_ids:['run'],scene_id:'scene',scene_revision:'rSYN',clock_ids:['clock'],camera_ids:['A','B'],clock_mapping_sha256:C,detection_index_sha256:H,detection_index_id:'index',resolved_source_ranges_us:[{run_id:'run',range_us:[0,10e6]}]},timeline:[
      {kind:'ON_CAMERA',range_us:[0,2e6],camera_id:'A',observation_ids:['o0']},
      {kind:'GAP',range_us:[2e6,4e6],camera_shown:'A',position:null},
      {kind:'GAP',range_us:[6e6,10e6],camera_shown:'A',position:null},
    ]},
    observations:{o0:{observation_id:'o0',camera_id:'A',timestamp_us:0}},
    decisions:[{session_id:'session',decision_id:'d0',accepted:true,source_time_us:3e6,decision_time_us:2e6,executed_action:'SWITCH',state_after:'SWITCHING',decided_by:'RULE_ONLY'}],
  };
}
const at=(view,t,c=0)=>wallCells(view.cameras,t)[c].state;
test('explicit observation cells, gaps, missing frames, failures and uncovered time remain distinct',()=>{
  const v=projectRecordedTimeline(fixture());assert.deepEqual(v.cameras[0].segments,[
    {range_us:[0,1e6],state:'OBSERVED'},{range_us:[1e6,2e6],state:'UNKNOWN'},
    {range_us:[2e6,4e6],state:'GAP'},{range_us:[4e6,5e6],state:'MISSING'},
    {range_us:[5e6,10e6],state:'UNKNOWN'},
  ]);
  assert.equal(at(v,0),'OBSERVED');assert.equal(at(v,1e6),'UNKNOWN');assert.equal(at(v,2e6),'GAP');assert.equal(at(v,4e6),'MISSING');assert.equal(at(v,6e6),'UNKNOWN');
  assert.equal(at(v,0,1),'UNKNOWN','indexed camera alone is not an observed target');assert.equal(at(v,10e6),'UNKNOWN');
});
test('gt_track getter bait is never read, serialized, or displayed by projection',()=>{
  const f=fixture();let reads=0;
  for(const obj of [f,f.response,f.response.timeline[0],f.index,f.index.sampling.per_camera[0],f.clock,f.observations,f.observations.o0,f.decisions[0]]){
    Object.defineProperty(obj,'gt_track',{enumerable:true,get(){reads++;throw new Error('GT_READ');}});
  }
  const rendered=JSON.stringify(projectRecordedTimeline(f));assert.equal(reads,0);assert.ok(!rendered.includes('gt_track'));assert.ok(!rendered.includes('GT_READ'));
});
test('accepted action uses decision time and preserves source time separately; rejected rows do not create events',()=>{
  const f=fixture();f.decisions.push({...f.decisions[0],decision_id:'rejected',accepted:false});const v=projectRecordedTimeline(f);
  assert.equal(v.events.length,1);assert.equal(v.events[0].t_us,2e6);assert.match(v.events[0].label,/source 3000000 µs/);assert.equal(v.identity_verdict,'UNCONFIRMED');assert.deepEqual(v.q1_clips,{});
});
test('scope restricts coverage, including missing rows, and retains integers',()=>{
  const f=fixture();f.response.resolved_scope.resolved_source_ranges_us[0].range_us=[500000,3500000];
  const v=projectRecordedTimeline(f);assert.equal(at(v,0),'UNKNOWN');assert.equal(at(v,500000),'OBSERVED');assert.equal(at(v,3500000),'UNKNOWN');assert.equal(at(v,4500000),'UNKNOWN');
  assert.ok(v.cameras.every(c=>c.segments.every(s=>s.range_us.every(Number.isSafeInteger))));
});
for(const [name,mutate,code] of [
  ['fractional time',f=>f.response.timeline[0].range_us[0]=0.5,'SOURCE_INTEGER_RANGE'],
  ['unsafe duration',f=>f.clock.source_duration_us=Number.MAX_SAFE_INTEGER+1,'SOURCE_RANGE'],
  ['run mismatch',f=>f.index.run_id='other','SCOPE_MISMATCH'],
  ['clock pin mismatch',f=>f.clock.content_sha256=H,'PIN_BINDING'],
  ['ninth camera',f=>f.response.resolved_scope.camera_ids=['A','B','C','D','E','F','G','H','I'],'CAMERA_SCOPE'],
  ['missing observation',f=>delete f.observations.o0,'OBSERVATION_BINDING'],
  ['wrong observation camera',f=>f.observations.o0.camera_id='B','OBSERVATION_BINDING'],
  ['overlapping contradictory coverage',f=>f.index.sampling.per_camera[0].not_inferred.push({range_us:[0,1e6],reason:'MISSING'}),'COVERAGE_CONFLICT'],
  ['identity promotion',f=>f.response.identity_verdict='CONFIRMED','INFERENCE_BOUNDARY'],
])test(`${name} fails closed`,()=>{const f=fixture();mutate(f);assert.throws(()=>projectRecordedTimeline(f),new RegExp(code));});

// Synthetic raw recording uses the existing v1 response fixture/schema. These
// integrity tests do not register the fixture as an authorized P1/formal source.
async function rawFixture(){
  const f=fixture();
  Object.assign(f.clock,{schema_version:'q-demo.clock-mapping.v1',mapping_kind:'DECLARED_DEMO_CLOCK',rate:1,timezone:'Asia/Taipei',wall_origin:'2026-11-01T13:00:00+08:00',mapping_version:'SYNTHETIC',declaration_source:'SYNTHETIC',declared_by:'SYNTHETIC',declared_at:'2026-10-24T00:00:00+08:00'});
  f.clock.content_sha256=await contentHash(f.clock,{excludeRoot:['content_sha256']});f.index.schema_version='q-demo.detection-index.v1';f.index.content_sha256=await contentHash(f.index,{excludeRoot:['content_sha256','index_id']});
  const base=JSON.parse(JSON.parse(await readFile(new URL('fixtures/q2-rule.json',import.meta.url),'utf8')).cases[0].response_json);
  const response={...base,...f.response};Object.assign(response.resolved_scope,{clock_mapping_sha256:f.clock.content_sha256,detection_index_sha256:f.index.content_sha256});
  response.decisions_sha256=await sha256Hex('');response.output_sha256=await contentHash(response,{excludeRoot:['output_sha256','stats']});
  const recording={schema_version:'q-demo.api-recording.v1',data_origin:'RECORDED',source_kind:'SYNTHETIC',run_id:'run',scene_id:'scene',response,decisions:'',observations:f.observations};
  recording.content_sha256=await contentHash(recording);
  return {recordingRaw:canonicalJSON(recording),indexRaw:canonicalJSON(f.index),clockRaw:canonicalJSON(f.clock)};
}
test('raw recording verifies canonical hashes and projects the exact coverage',async()=>{
  const raw=await rawFixture(),v=await decodeRecordedTimeline(raw);assert.equal(at(v,0),'OBSERVED');assert.equal(at(v,4e6),'MISSING');assert.equal(v.events.length,0);
});
test('modified raw recording/index/clock cannot produce a view',async()=>{
  const raw=await rawFixture();
  for(const key of ['recordingRaw','indexRaw','clockRaw'])await assert.rejects(()=>decodeRecordedTimeline({...raw,[key]:raw[key].replace('run','other')}));
});
test('rehashed recording with journal tampering still fails the response journal pin',async()=>{
  const raw=await rawFixture(),r=JSON.parse(raw.recordingRaw);r.decisions='{}\n';r.content_sha256=await contentHash(r,{excludeRoot:['content_sha256']});
  await assert.rejects(()=>decodeRecordedTimeline({...raw,recordingRaw:canonicalJSON(r)}),/JOURNAL_HASH/);
});
test('self-declared formal or arbitrary manifest cannot grant source authority',async()=>{
  for(const formal_eligible of [true,false])await assert.rejects(()=>loadP1Recording({manifestRaw:JSON.stringify({formal_eligible,gt_read:false})}),/SOURCE_UNSELECTED/);
});

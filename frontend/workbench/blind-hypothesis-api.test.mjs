import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {blindHypothesisPlan,blindHypothesisRegionAt,blindHypothesisStatusHTML,blindHypothesisRequest,runBlindHypotheses,invalidateBlindHypothesis,blindHypothesisFromResponse} from './blind-hypothesis.mjs';

// Frozen C4b output (PR #44 @ 0942f5a), real backend data, not MOCK. Outer envelope UNKNOWN, nested layer READY.
const fixture=JSON.parse(readFileSync(new URL('./fixtures/c4b-person-target-reconstruction.fixture.json',import.meta.url),'utf8'));
const response=()=>structuredClone(fixture.response);
const REF='observation:218abc805d72fe39c4496da0';
const selection={camera_ids:['CAM_1F_AUDITORIUM_FRONT','CAM_1F_AUDITORIUM_REAR'],start:0,end:9.8,top_k:3};
const target=()=>({sceneEpoch:1,sceneId:'blender-office-person',session:{session_ref:'session-A'},blindHypothesisEpoch:0});

test('fixture records its source commit and hashes',()=>{
  assert.equal(fixture.fixture_source.commit,'0942f5a');assert.match(fixture.fixture_source.file_sha256,/^[0-9a-f]{64}$/);
  assert.equal(fixture.fixture_source.nested_output_sha256,response().blind_hypotheses.output_sha256);
});

test('outer UNKNOWN does not discard the nested READY layer: 3 paths, 17 time slices, outer status shown beside it',()=>{
  const r=response();
  assert.equal(r.status,'UNKNOWN');assert.equal(r.reason,'SELECTED_PROJECTION_UNAVAILABLE');assert.equal(r.blind_hypotheses.status,'READY');
  const plan=blindHypothesisPlan(r);
  assert.equal(plan.status,'READY');assert.equal(plan.paths.length,3);assert.equal(plan.regions.length,17);
  assert.deepEqual([plan.interval.start_s,plan.interval.end_s],[4.6,8.2]);
  assert.deepEqual([plan.regions[0].timestamp_s,plan.regions.at(-1).timestamp_s],[4.8,8]);
  assert.deepEqual(plan.outer,{status:'UNKNOWN',reason:'SELECTED_PROJECTION_UNAVAILABLE',reasonText:plan.outer.reasonText});
  assert.match(plan.outer.reasonText,/MISSING/);
  const html=blindHypothesisStatusHTML(plan);
  assert.match(html,/data-status="READY"/);assert.match(html,/data-blind-outer="UNKNOWN"/);assert.match(html,/SELECTED_PROJECTION_UNAVAILABLE/);assert.match(html,/假設層獨立為 READY/);
  // The target envelope itself is not repaired: no position appears anywhere in the plan.
  assert.equal('position' in plan,false);assert.equal(blindHypothesisRegionAt(plan,4.6),null);assert.equal(blindHypothesisRegionAt(plan,4.8).timestamp_s,4.8);
  // No real negative evidence in this run: nothing says "unseen".
  assert.ok(plan.paths.every(path=>path.walkable==='PASS'));
  assert.equal(blindHypothesisFromResponse(r),r.blind_hypotheses);
});

test('nested UNKNOWN is shown as UNKNOWN with its reason; an absent nested field is shown, not dropped',async()=>{
  const nestedUnknown=response();nestedUnknown.blind_hypotheses={...nestedUnknown.blind_hypotheses,status:'UNKNOWN',reason:'ENDPOINTS_UNREACHABLE',hypotheses:[],reachable_regions:[]};
  const plan=blindHypothesisPlan(nestedUnknown);
  assert.equal(plan.status,'UNKNOWN');assert.equal(plan.reason,'ENDPOINTS_UNREACHABLE');assert.deepEqual(plan.paths,[]);assert.deepEqual(plan.regions,[]);
  assert.match(blindHypothesisStatusHTML(plan),/data-blind-reason="ENDPOINTS_UNREACHABLE"/);assert.match(blindHypothesisStatusHTML(plan),/data-blind-outer="UNKNOWN"/);
  const absent=response();delete absent.blind_hypotheses;
  assert.equal(blindHypothesisPlan(absent),null);
  const state=target();await runBlindHypotheses(state,selection,REF,async()=>absent);
  assert.equal(state.blindHypothesis.status,'UNKNOWN');assert.equal(state.blindHypothesis.reason,'BLIND_HYPOTHESES_ABSENT');assert.equal(state.blindHypothesis.outer.status,'UNKNOWN');
  assert.equal(state.blindHypothesisSha256,null);assert.deepEqual(state.blindHypothesis.paths,[]);
});

test('request carries observation_ref and the selection only; invalid or missing refs are refused before sending',async()=>{
  const sent=[],state=target();
  await runBlindHypotheses(state,selection,REF,async request=>{sent.push(request);return response();});
  assert.deepEqual(sent,[{scene_id:'blender-office-person',camera_ids:selection.camera_ids,start:0,end:9.8,top_k:3,observation_ref:REF}]);
  for(const key of ['negative_evidence_refs','previous_response_sha256','negative_evidence','speed','path','endpoints'])assert.equal(key in sent[0],false);
  for(const bad of [null,undefined,'',123,'observation:xyz','observation:218abc805d72fe39c4496d','track:218abc805d72fe39c4496da0']){
    assert.throws(()=>blindHypothesisRequest('s',selection,bad),/來源觀測/);
    await assert.rejects(runBlindHypotheses(target(),selection,bad,async()=>{throw new Error('must not send');}),/來源觀測/);
  }
});

test('the nested output_sha256 is stored for later pruning re-runs; state holds the plan',async()=>{
  const state=target();
  assert.equal(await runBlindHypotheses(state,selection,REF,async()=>response()),true);
  assert.equal(state.blindHypothesisSha256,'63d9080be8910c88f3c743d1e03691333d5559a7fe71aabf17c5afd9bfa387f6');
  assert.equal(state.blindHypothesisPending,false);assert.equal(state.blindHypothesis.paths.length,3);
  const bad=response();bad.blind_hypotheses.output_sha256='nothex';
  await runBlindHypotheses(state,selection,REF,async()=>bad);assert.equal(state.blindHypothesisSha256,null);
});

test('stale replies are dropped after a scene/session change or invalidation; failures clear pending and keep no layer',async()=>{
  const state=target();let release;
  const slow=runBlindHypotheses(state,selection,REF,()=>new Promise(resolve=>{release=()=>resolve(response());}));
  assert.equal(state.blindHypothesisPending,true);
  invalidateBlindHypothesis(state);release();
  assert.equal(await slow,false);assert.equal(state.blindHypothesis,null);assert.equal(state.blindHypothesisSha256,null);
  const moved=target();let go;
  const second=runBlindHypotheses(moved,selection,REF,()=>new Promise(resolve=>{go=()=>resolve(response());}));
  moved.sceneEpoch=2;go();assert.equal(await second,false);assert.equal(moved.blindHypothesis,null);
  const failing=target();
  await assert.rejects(runBlindHypotheses(failing,selection,REF,async()=>{throw new Error('denied');}),/denied/);
  assert.equal(failing.blindHypothesisPending,false);assert.equal(failing.blindHypothesis,null);
});

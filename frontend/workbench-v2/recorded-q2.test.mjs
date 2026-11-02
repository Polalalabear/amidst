// D113 B-05b: a recorded Q2 response plays in the same single-screen view as live tracking.
// Root cause (verified): the search phase only left 'wall' on SEARCH_START, which a recording load never dispatches,
// so #monitor-room-slot stayed on and #q2-slot / #track-map-slot stayed hidden. `seeds` is not involved.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createPhaseStore,phaseReduce,initialPhase,recordedResultAction,attachPhase} from './search-phase-model.mjs';
import {createStore,initialState} from './store.mjs';
import {sessionModel,camerasFor} from './q2-session-model.mjs';
import {stepRows} from './q5-steps-model.mjs';
import {buildScene} from './track-map-model.mjs';
import {renderPanelHtml} from './track-map-render.mjs';

const S=1e6,us=s=>Math.round(s*S);
const seg=(kind,camera,a,b,extra={})=>kind==='ON_CAMERA'?{kind,camera_id:camera,range_us:[us(a),us(b)],observation_ids:[`obs:${camera}:${a}`],...extra}:{kind,camera_shown:camera,range_us:[us(a),us(b)],position:null,...extra};
// Engineering-scene shaped recording: A lost at 2.5 s, three returns to A, MATCH_STRONG on B at 4.25 s, B shown from 5.15 s.
const q2={schema_version:'q-demo.q2-response.v1',status:'COMPLETE',output_sha256:'a'.repeat(64),
  timeline:[seg('ON_CAMERA','A',0,2.5),seg('GAP','A',2.5,3.05),seg('ON_CAMERA','A',3.05,3.2),seg('GAP','A',3.2,3.45),seg('ON_CAMERA','A',3.45,3.6),seg('GAP','A',3.6,3.85),seg('ON_CAMERA','A',3.85,4.0),seg('GAP','A',4.0,5.15),seg('ON_CAMERA','B',5.15,9)]};
const dec=(i,t,before,after,over={})=>({schema_version:'q-demo.decision-record.v1',decision_id:`d${i}`,step_index:i,source_time_us:us(t),state_before:before,state_after:after,decided_by:'RULE_ONLY',accepted:true,rejection_code:null,
  executed_action:null,candidates_considered:[],tool_calls:[],llm_calls:[],submitted:null,fallback_reason:null,...over});
const decisions=[dec(0,0,null,'PLAYING'),dec(1,2.5,'PLAYING','TEMP_LOST'),dec(2,2.9,'TEMP_LOST','SEARCHING'),dec(3,3.05,'SEARCHING','RETURNED_TO_ORIGIN'),dec(4,3.45,'SEARCHING','RETURNED_TO_ORIGIN'),dec(5,3.85,'SEARCHING','RETURNED_TO_ORIGIN'),
  dec(6,4.25,'SEARCHING','SWITCHING',{executed_action:'SWITCH',candidates_considered:[{candidate_ref:'c1',rank:1,action:'SWITCH',target_presence:'MATCH_STRONG',decided_by:'RULE_ONLY'}]}),dec(7,5.15,'SWITCHING','PLAYING')];
const recorded=(over={})=>({...initialState(),responseOrigin:'RECORDED',recordedKind:'SYNTHETIC',task:'q2',q2,...over});

test('a recorded Q2 with an ON_CAMERA hit leaves the wall for the tracking result (SHOW_RESULT)',()=>{
  const action=recordedResultAction(recorded());assert.deepEqual(action,{type:'SHOW_RESULT',mode:'track'});
  const p=phaseReduce(initialPhase(),action);assert.equal(p.phase,'result');assert.equal(p.mode,'track');
});
test('Q1 recordings, live responses and recordings without tracking data stay on the wall',()=>{
  assert.equal(recordedResultAction(recorded({task:'q1',q2:null,q1:{status:'READY',results:[{camera_id:'A',rank:1,matched_segments:[]}],no_match_cameras:[],not_evaluated_cameras:[]}})),null);
  assert.equal(recordedResultAction(recorded({responseOrigin:null})),null);
  assert.equal(recordedResultAction(recorded({q2:{...q2,timeline:[seg('GAP','A',0,1)]}})),null);
  assert.equal(recordedResultAction(recorded({q2:null})),null);
  assert.equal(phaseReduce(initialPhase(),{type:'SHOW_RESULT',mode:'bogus'}).phase,'wall');
  const searching=phaseReduce(initialPhase(),{type:'SEARCH_START',mode:'track'});assert.equal(phaseReduce(searching,{type:'SHOW_RESULT',mode:'track'}),searching);
});
test('SEARCH_END returns a recorded result to the wall, and the phase store stays usable',()=>{
  const p=createPhaseStore();p.dispatch(recordedResultAction(recorded()));assert.equal(p.getState().phase,'result');
  p.dispatch({type:'SEARCH_END'});assert.equal(p.getState().phase,'wall');
});

test('single screen shows A until 5.15 s and B after, with the lost/search states between',()=>{
  const at=t=>sessionModel(q2,us(t));
  assert.equal(at(2.0).camera,'A');assert.equal(at(2.0).state,'PLAYING');
  for(const t of [2.6,3.3,3.7,4.5,5.14])assert.equal(at(t).camera,'A',`${t}`);
  assert.equal(at(5.15).camera,'B');assert.equal(at(5.15).state,'PLAYING');assert.equal(at(8).camera,'B');
  assert.deepEqual(camerasFor(at(5.1),{camera_ids:['A','B']},{mode:'single'}),['A']);
  assert.deepEqual(camerasFor(at(5.2),{camera_ids:['A','B']},{mode:'single'}),['B']);
});

test('normal-mode decision log: steps appear as time passes and disappear when the timeline goes back',()=>{
  const ids=t=>stepRows(decisions,q2,us(t)).map(r=>r.id);
  assert.deepEqual(ids(0),['d0']);assert.deepEqual(ids(2.6),['d0','d1']);
  assert.equal(ids(4.3).includes('d6'),true);assert.equal(ids(4.3).includes('d7'),false);
  assert.equal(ids(5.2).length,8);assert.deepEqual(ids(1),['d0']);
  assert.equal(stepRows(decisions,q2,us(3.9)).filter(r=>r.transition.endsWith('RETURNED_TO_ORIGIN')).length,3);
});
test('log text: SWITCH with MATCH_STRONG at 4.25 s, B shown at 5.15 s; no rationale or raw JSON',()=>{
  const rows=stepRows(decisions,q2,us(6)),sw=rows.find(r=>r.id==='d6'),shown=rows.find(r=>r.id==='d7');
  assert.match(sw.text,/SWITCH/);assert.match(sw.text,/MATCH_STRONG/);assert.equal(sw.source_time_us,us(4.25));assert.match(shown.text,/B/);
  assert.equal(sw.badge,'ⓡ 規則');
  const leaky=stepRows([dec(0,0,null,'PLAYING',{submitted:{rationale:'secret reasoning'}})],q2,0);
  assert.doesNotMatch(JSON.stringify(leaky),/secret reasoning|submitted|tool_calls/);
});
test('log rows keep rejected submissions visible and refuse a fallback without a reason',()=>{
  const rejected=dec(9,1,'PLAYING','PLAYING',{decided_by:'AGENT',accepted:false,rejection_code:'ILLEGAL_ORDER'});
  assert.match(stepRows([rejected],q2,us(2))[0].text,/拒絕 ILLEGAL_ORDER/);
  assert.throws(()=>stepRows([dec(9,1,'PLAYING','PLAYING',{decided_by:'RULE_FALLBACK'})],q2,us(2)),/FALLBACK_REASON_REQUIRED/);
});

test('top-down solid line extends from A to B with time and shrinks when the timeline goes back',()=>{
  const html=t=>renderPanelHtml(buildScene({cameraMap:null,timeline:q2.timeline,tUs:us(t),origin:'SYNTHETIC',runCameraIds:['A','B']}));
  const solid=h=>(h.match(/class="tm-observed"/g)??[]).length;
  assert.equal(solid(html(2)),0);assert.ok(solid(html(6))>=1);assert.equal(solid(html(2)),0);
});

test('GT-like fields injected into the recording change neither the camera nor the log nor the line',()=>{
  const dirty=structuredClone(q2);for(const s of dirty.timeline)Object.assign(s,{gt_position:{x:9,y:9},gt_camera:'Z',visibility:0.1,depth:3,renderer_trajectory:[[1,2]]});
  const dirtyDec=decisions.map(d=>({...d,gt_state:'LOST',visibility:0,depth:1}));
  for(const t of [1,2.6,5.1,5.2])assert.equal(sessionModel(dirty,us(t)).camera,sessionModel(q2,us(t)).camera);
  assert.deepEqual(stepRows(dirtyDec,dirty,us(6)),stepRows(decisions,q2,us(6)));
  assert.doesNotMatch(JSON.stringify(stepRows(dirtyDec,dirty,us(6))),/gt_|visibility|depth|renderer_trajectory/);
  const scene=t=>renderPanelHtml(buildScene({cameraMap:null,timeline:dirty.timeline,tUs:us(t),origin:'SYNTHETIC',runCameraIds:['A','B']}));
  assert.doesNotMatch(scene(6),/gt_|renderer_trajectory|visibility/);
});

test('wiring: recording load drives the phase and loads decisions outside review mode; the log slot is not inside the review section',()=>{
  const app=readFileSync(new URL('./app.mjs',import.meta.url),'utf8'),html=readFileSync(new URL('./index.html',import.meta.url),'utf8'),shell=readFileSync(new URL('./shell-view.mjs',import.meta.url),'utf8');
  const rec=app.slice(app.indexOf('handlers.recording='),app.indexOf('const manualButton'));
  assert.match(rec,/recordedResultAction/);assert.match(rec,/phase\.dispatch/);assert.doesNotMatch(rec,/kind==='q2'&&reviewMode\)await loadArtifacts/);assert.match(rec,/loadArtifacts/);
  const load=app.slice(app.indexOf('async function loadArtifacts'),app.indexOf('handlers.run='));
  assert.doesNotMatch(load,/REVIEW_ONLY/);assert.match(load,/if\(!reviewMode\)\{store\.dispatch\(\{type:'Q_ARTIFACTS'[^]*?snapshots:\{\},evidence:\{\}/);
  const reviewSection=html.slice(html.indexOf('id="q-review-section"'),html.indexOf('</section>',html.indexOf('id="q-review-section"')));
  assert.doesNotMatch(reviewSection,/q5-slot/);assert.match(html,/id="q5-slot"/);
  assert.doesNotMatch(shell,/\$\('#q5-slot'\)\.hidden=!s\.reviewMode/);
});
test('phase attach is unaffected: a live search still needs SEARCH_START',()=>{
  const main=createStore(initialState()),p=createPhaseStore();attachPhase(main,p);assert.equal(p.getState().phase,'wall');
});

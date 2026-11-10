import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {observationRecordsFromResponse,intervalEndRef,knownObservations,selectedObservation,stepSelectionRef,observationOverlayItems,observationOverlaySVG,groundHighlightPlan,observationPanelHTML,fixed2} from './observation-selection.mjs';
import {demoBlindRequest,ensureDemoBlind,stepsForGroup} from './demo-mode.mjs';

const FRONT='observation:218abc805d72fe39c4496da0',REAR='observation:a012bc1b71556a46191bc68a';
const ground=(ref,cam,t,len,basis)=>({observation_ref:ref,camera_id:cam,timestamp_s:t,status:'READY',basis,segment:{near_m:[1,2,0.5],far_m:[2,3,0.5],length_m:len},contact_quality:{status:'FLAGGED',reasons:['LOW_INCIDENCE']}});
const response=()=>({
  selected_observation:{observation_ref:FRONT,frame_ref:'frame:8e5517c6b5f9d791958f14dd',camera_id:'CAM_FRONT',timestamp:4.6,bbox_xyxy:[824,71,843,147],contact_pixel:[825,146],world_position:null,measurement_status:'MERGED_OR_PARTIAL',ground_estimate:ground(FRONT,'CAM_FRONT',4.6,0.7384191729883363,'FOOT_RAY_PIXEL_BAND')},
  review_evidence:{endpoints:[{ground_estimate:ground(FRONT,'CAM_FRONT',4.6,0.7384,'FOOT_RAY_PIXEL_BAND')},{ground_estimate:ground(REAR,'CAM_REAR',8.2,2.4926122151184877,'HEAD_RAY_HEIGHT_PRIOR')}]},
  blind_hypotheses:{interval:{start_observation_ref:FRONT,end_observation_ref:REAR,start_s:4.6,end_s:8.2}}});
const stateWith=(extra={})=>({sceneId:'s',demoBlindRuns:{sceneId:'s',NONE:{observations:observationRecordsFromResponse(response()),interval_end_ref:intervalEndRef(response())}},...extra});

test('records come from the response by ref; the selected observation wins and endpoints add only a ground estimate',()=>{
  const r=observationRecordsFromResponse(response());
  assert.deepEqual(Object.keys(r).sort(),[FRONT,REAR].sort());
  assert.deepEqual(r[FRONT].bbox_xyxy,[824,71,843,147]);assert.equal(r[FRONT].world_position,null);assert.equal(r[FRONT].source,'selected_observation');
  assert.equal(r[REAR].bbox_xyxy,null);assert.equal(r[REAR].camera_id,'CAM_REAR');assert.equal(r[REAR].world_position,undefined);
  assert.equal(intervalEndRef(response()),REAR);assert.equal(intervalEndRef({}),null);
  assert.deepEqual(observationRecordsFromResponse({selected_observation:{observation_ref:FRONT,bbox_xyxy:[5,5,1,1]}})[FRONT].bbox_xyxy,null);
  assert.deepEqual(observationRecordsFromResponse(null),{});
});
test('steps select by ref: step 2 the fixed ref, step 4 the interval end the backend reported',()=>{
  const steps=stepsForGroup(JSON.parse(readFileSync(new URL('./demo-steps.office.json',import.meta.url),'utf8')));
  const [s2,,s4]=steps.slice(1,4);
  assert.equal(stepSelectionRef(s2,stateWith()),FRONT);assert.equal(stepSelectionRef(s4,stateWith()),REAR);
  assert.equal(stepSelectionRef(s4,{sceneId:'s'}),null,'no NONE run → nothing to select');
  assert.equal(stepSelectionRef(steps[0],stateWith()),null);
});
test('selection is found only in the current scene’s records',()=>{
  assert.equal(selectedObservation(stateWith({selectedObservationRef:FRONT})).camera_id,'CAM_FRONT');
  assert.equal(selectedObservation(stateWith({selectedObservationRef:FRONT,sceneId:'other'})),null);
  assert.equal(selectedObservation(stateWith({selectedObservationRef:'observation:'+'0'.repeat(24)})),null);
  assert.equal(Object.keys(knownObservations(stateWith())).length,2);
});
test('2D outline: exact frame on its own camera only, thicker when selected, needs a bbox',()=>{
  const frame={frame_ref:'frame:8e5517c6b5f9d791958f14dd',timestamp:4.6};
  const off=observationOverlayItems(stateWith(),'CAM_FRONT',frame);
  assert.equal(off.length,1);assert.equal(off[0].selected,false);
  assert.equal(observationOverlayItems(stateWith({selectedObservationRef:FRONT}),'CAM_FRONT',frame)[0].selected,true);
  assert.deepEqual(observationOverlayItems(stateWith(),'CAM_REAR',frame),[]);
  assert.deepEqual(observationOverlayItems(stateWith(),'CAM_FRONT',{frame_ref:'frame:other',timestamp:4.6}),[]);
  assert.deepEqual(observationOverlayItems(stateWith(),'CAM_FRONT',null),[]);
  const svgOff=observationOverlaySVG(off,{width:1920,height:1080}),svgOn=observationOverlaySVG(observationOverlayItems(stateWith({selectedObservationRef:FRONT}),'CAM_FRONT',frame),{width:1920,height:1080});
  assert.match(svgOff,new RegExp(`data-observation-ref="${FRONT}" data-observation-selected="false"`));assert.match(svgOn,/data-observation-selected="true"/);
  assert.equal(observationOverlaySVG([],{width:1,height:1}),'');
  const w=svg=>Number(/stroke-width="([\d.]+)"/.exec(svg)[1]);assert.ok(w(svgOn)>w(svgOff));
});
test('panel lists ref, camera, time, ground basis and 2-decimal length, MISSING world position, UNCONFIRMED identity',()=>{
  const html=observationPanelHTML(stateWith({selectedObservationRef:FRONT}));
  for(const text of [FRONT,'CAM_FRONT','4.6 s','FOOT_RAY_PIXEL_BAND','0.74 m','world_position：MISSING','UNCONFIRMED','LOW_INCIDENCE'])assert.ok(html.includes(text),text);
  assert.ok(!html.includes('0.738'));assert.match(html,/data-ground-highlight="OFF"/);
  const rear=observationPanelHTML(stateWith({selectedObservationRef:REAR}),{groundLayer:true});
  assert.ok(rear.includes('2.49 m'));assert.ok(rear.includes('HEAD_RAY_HEIGHT_PRIOR'));assert.match(rear,/UNKNOWN（此來源未提供）/);assert.match(rear,/data-ground-highlight="ON"/);
  assert.equal(observationPanelHTML(stateWith()),'');
  assert.match(observationPanelHTML(stateWith({selectedObservationRef:'observation:'+'0'.repeat(24)})),/UNAVAILABLE/);
  assert.equal(fixed2(0.7384),'0.74');assert.equal(fixed2(null),'UNKNOWN');
});
test('ground highlight plan only for a READY segment',()=>{
  const r=observationRecordsFromResponse(response());
  assert.deepEqual(groundHighlightPlan(r[FRONT]),{observation_ref:FRONT,near_m:[1,2,0.5],far_m:[2,3,0.5],length_m:0.7384191729883363,basis:'FOOT_RAY_PIXEL_BAND'});
  assert.equal(groundHighlightPlan({...r[FRONT],ground_estimate:{...r[FRONT].ground_estimate,status:'UNKNOWN'}}),null);assert.equal(groundHighlightPlan(null),null);
});
test('selection never changes a request: builders ignore it, and app.mjs never mixes it into an api() call',async()=>{
  const sel={camera_ids:['a','b'],start:0,end:9.8,top_k:3};
  const a=demoBlindRequest('s',sel,FRONT,{mode:'NONE'});
  assert.deepEqual(Object.keys(a).sort(),['camera_ids','end','negative_evidence_mode','observation_ref','scene_id','start','top_k']);
  const sent=[];const target={sceneId:'s',sceneEpoch:1,selectedObservationRef:null};
  const send=async r=>{sent.push(JSON.stringify(r));return response();};
  const step={blind_mode:'NONE',selection:FRONT};
  await ensureDemoBlind(target,step,sel,send,{show:false});
  const target2={sceneId:'s',sceneEpoch:1,selectedObservationRef:REAR};
  await ensureDemoBlind(target2,step,sel,send,{show:false});
  assert.equal(sent[0],sent[1],'same request with or without a selection');
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8');
  for(const line of source.split('\n'))if(/api\(/.test(line))assert.ok(!/selectedObservation/.test(line),line.slice(0,120));
});
test('show:false loads the records but leaves the displayed hypothesis plan alone',async()=>{
  const target={sceneId:'s',sceneEpoch:1,blindHypothesis:{status:'READY',marker:1},blindHypothesisSha256:'x'};
  await ensureDemoBlind(target,{blind_mode:'NONE',selection:FRONT},{camera_ids:['a','b'],start:0,end:9.8,top_k:3},async()=>response(),{show:false});
  assert.deepEqual(target.blindHypothesis,{status:'READY',marker:1});assert.equal(target.blindHypothesisSha256,'x');
  assert.ok(target.demoBlindRuns.NONE.observations[FRONT]);assert.equal(target.demoBlindRuns.NONE.interval_end_ref,REAR);
});

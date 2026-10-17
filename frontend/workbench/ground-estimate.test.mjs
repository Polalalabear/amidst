import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from 'three';
import {collectGroundObservations,groundObservationsAt,loadGroundObservations,groundEstimateTileSVG,displayLabel,groundEstimatePlan,groundEstimatePlans,groundEstimateReadout,groundEstimateOverlaySVG,syncGroundEstimateGroup} from './ground-estimate.mjs';
import {candidateEvidenceSVG} from './cross-camera.mjs';

const fixture=JSON.parse(readFileSync(new URL('./fixtures/ground-estimate.fixture.json',import.meta.url),'utf8'));
const byId=id=>fixture.entries.find(entry=>entry.fixture_id===id).ground_estimate;
const tooLong=fixture.entries.find(entry=>entry.fixture_id.startsWith('segment_too_long')).ground_estimate;
const anchorBad=fixture.entries.find(entry=>entry.fixture_id.startsWith('head_anchor')).ground_estimate;
const point=byId('mock-point'),segment=byId('mock-segment-ready');

test('fixture entries state their source; hand-made ones are marked MOCK',()=>{
  for(const entry of fixture.entries){
    assert.ok(entry.fixture_source);
    if(entry.fixture_source.startsWith('MOCK'))assert.equal(entry.fixture_note,'MOCK, contract-shaped');
  }
  assert.equal(fixture.entries.filter(e=>e.fixture_source.startsWith('REAL')).length,3);
});

test('POINT, SEGMENT and UNKNOWN produce distinct plans; absent field gives null',()=>{
  const p=groundEstimatePlan(point),s=groundEstimatePlan(segment);
  assert.equal(p.kind,'POINT');assert.deepEqual(p.point,[10.5,4,0.4959475898742676]);
  assert.equal(s.kind,'SEGMENT');assert.equal(s.label,'區間 2.1 m');assert.deepEqual(s.near,segment.segment.near_m);assert.deepEqual(s.far,segment.segment.far_m);
  assert.deepEqual(s.details,['依據 HEAD_RAY_HEIGHT_PRIOR','約束 HEIGHT_PRIOR:BOUNDED → OCCLUDER_BEHIND:CLIPPED → WALKABLE_AREA:CLIPPED','高度先驗 1.60–1.80 m','像素靈敏度 0.24 m/px']);
  for(const [estimate,reason] of [[tooLong,'SEGMENT_TOO_LONG'],[anchorBad,'HEAD_ANCHOR_UNRELIABLE']]){
    const u=groundEstimatePlan(estimate);
    assert.equal(u.kind,'UNKNOWN');assert.equal(u.reason,reason);assert.equal(u.label,`接地 UNKNOWN（${reason}）`);
    assert.equal(u.point,null);assert.equal(u.near,null);assert.equal(u.far,null);
  }
  assert.equal(groundEstimatePlan(undefined),null);assert.equal(groundEstimatePlan(null),null);assert.equal(groundEstimatePlan([]),null);
});

test('malformed READY estimates fall back to UNKNOWN instead of being repaired',()=>{
  assert.equal(groundEstimatePlan({...segment,segment:{...segment.segment,far_m:null}}).reason,'SEGMENT_MALFORMED');
  assert.equal(groundEstimatePlan({...point,point_m:null}).reason,'POINT_MISSING');
  assert.equal(groundEstimatePlan({...point,schema_version:'other'}).reason,'SCHEMA_UNSUPPORTED');
  assert.equal(groundEstimatePlan({...point,estimate_kind:'NONE'}).reason,'ESTIMATE_KIND_UNSUPPORTED');
});

test('R2: raw_near_m / raw_far_m and diagnostics are never drawn or shown as coordinates',()=>{
  const samples=[{state:'PROJECTED_OBSERVATION',camera_id:'CAM_1F_AUDITORIUM_FRONT',timestamp:4.4,ground_estimate:segment},{state:'PROJECTED_OBSERVATION',ground_estimate:tooLong}];
  const rawCoords=[segment.segment.raw_near_m,segment.segment.raw_far_m,tooLong.diagnostics.raw_near_m,tooLong.diagnostics.raw_far_m];
  assert.ok(tooLong.diagnostics.raw_near_m,'real fixture carries diagnostics.raw_near_m');
  const plans=JSON.stringify(groundEstimatePlans(samples)),readout=groundEstimateReadout(samples).join('\n');
  const svg=groundEstimateOverlaySVG({ground_estimate:segment},{arm:10,stroke:1,font:12})+groundEstimateOverlaySVG({ground_estimate:tooLong},{arm:10,stroke:1,font:12});
  const group=syncGroundEstimateGroup(THREE,null,new THREE.Group(),samples,{span:50});
  const geometry=JSON.stringify(group.children.map(c=>c.children.map(o=>[o.position.x,o.position.y])));
  for(const [x,y] of rawCoords)for(const output of [plans,readout,svg,geometry]){
    assert.ok(!output.includes(String(x)),`raw x ${x} leaked`);assert.ok(!output.includes(String(y)),`raw y ${y} leaked`);
  }
  assert.ok(!/raw_|diagnostics/.test(plans+readout+svg));
});

test('blind ticks and inferred samples draw nothing',()=>{
  assert.deepEqual(groundEstimatePlans([]),[]);assert.deepEqual(groundEstimatePlans(undefined),[]);
  assert.deepEqual(groundEstimatePlans([{state:'INFERRED_INTERPOLATION',ground_estimate:segment},{state:'MISSING',ground_estimate:point}]),[]);
  assert.equal(syncGroundEstimateGroup(THREE,null,new THREE.Group(),[],{span:50}),null);
});

test('readout: UNKNOWN is a neutral line, SEGMENT lists basis, constraints and pixel sensitivity',()=>{
  const lines=groundEstimateReadout([{state:'PROJECTED_OBSERVATION',camera_id:'C1',timestamp:4.4,ground_estimate:segment},{state:'PROJECTED_OBSERVATION',camera_id:'C1',timestamp:0,ground_estimate:tooLong}]);
  assert.match(lines[0],/區間 2\.1 m · CAM_1F_AUDITORIUM_FRONT · 4\.4 s\n  依據 HEAD_RAY_HEIGHT_PRIOR；約束 .*OCCLUDER_BEHIND:CLIPPED.*；像素靈敏度 0\.24 m\/px/);
  assert.equal(lines[1],`接地 UNKNOWN（SEGMENT_TOO_LONG） · ${tooLong.camera_id} · ${tooLong.timestamp_s.toFixed(1)} s`);
});

test('2D overlay: POINT hollow square, SEGMENT marker with length label, UNKNOWN tooltip only; no field means no output',()=>{
  const options={arm:10,stroke:1,font:12};
  const p=groundEstimateOverlaySVG({ground_estimate:point},options),s=groundEstimateOverlaySVG({ground_estimate:segment},options),u=groundEstimateOverlaySVG({ground_estimate:tooLong},options);
  assert.match(p,/data-ground-estimate="POINT"/);assert.match(p,/<rect[^>]*fill="none"/);
  assert.match(s,/data-ground-estimate="SEGMENT"/);assert.match(s,/區間 2\.1 m/);
  assert.match(u,/data-ground-estimate="UNKNOWN"/);assert.ok(!/<rect|<path|<text/.test(u));
  assert.equal(groundEstimateOverlaySVG({},options),'');
});

test('candidateEvidenceSVG is unchanged without ground_estimate and adds only the fragment with it',()=>{
  const item={key:'a',caption:'候選 1',associated:true,color:'#76d9cf',timestamp:4.4,bbox_xyxy:[100,100,200,300],contact_pixel:[150,299],measurement_status:'OK',segment_start:true,contact_basis:'BBOX_BOTTOM_CENTER'};
  const options={camera_id:'C1',width:1000,height:800};
  const plain=candidateEvidenceSVG([item],options),withEstimate=candidateEvidenceSVG([{...item,ground_estimate:segment}],options);
  assert.ok(!plain.includes('data-ground-estimate'));
  assert.ok(withEstimate.includes('data-ground-estimate="SEGMENT"'));
  assert.equal(withEstimate.replace(/<g data-ground-estimate.*?<\/g>/,''),plain);
});

test('3D: POINT is a hollow box, SEGMENT a bar with two end caps on the floor, UNKNOWN adds none; world_position untouched',()=>{
  const parent=new THREE.Group(),samples=[
    {state:'PROJECTED_OBSERVATION',world_position:[1,2,3],ground_estimate:point},
    {state:'PROJECTED_OBSERVATION',world_position:[1,2,3],ground_estimate:segment},
    {state:'PROJECTED_OBSERVATION',world_position:[1,2,3],ground_estimate:tooLong}];
  const before=JSON.stringify(samples.map(s=>s.world_position));
  const group=syncGroundEstimateGroup(THREE,null,parent,samples,{span:50});
  assert.equal(parent.children[0],group);assert.equal(group.children.length,2);
  const [pt,sg]=group.children;
  assert.equal(pt.userData.groundEstimate,'POINT');assert.ok(pt.children[0].isLineSegments);
  assert.equal(sg.userData.groundEstimate,'SEGMENT');assert.equal(sg.children.length,3);
  assert.ok(Math.abs(sg.children[0].position.x-(segment.segment.near_m[0]+segment.segment.far_m[0])/2)<1e-9);
  assert.equal(JSON.stringify(samples.map(s=>s.world_position)),before);
  const again=syncGroundEstimateGroup(THREE,group,parent,[],{span:50});
  assert.equal(again,group);assert.equal(group.children.length,0);
});

// ---- Person scene: per-observation ground_estimate from `query` (A2) ----
const person=JSON.parse(readFileSync(new URL('./fixtures/ground-estimate-person.fixture.json',import.meta.url),'utf8'));
const FRONT='CAM_1F_AUDITORIUM_FRONT',REAR='CAM_1F_AUDITORIUM_REAR';
const byCamera=id=>person.observations.filter(o=>o.camera_id===id);
const all=collectGroundObservations(byCamera(FRONT),byCamera(REAR));

test('person scene: all 33 observations carry a READY SEGMENT; world_position stays null (never filled from an interval)',()=>{
  assert.equal(all.length,33);
  assert.ok(person.observations.every(o=>o.world_position===null));
  const plans=all.map(o=>groundEstimatePlan(o.ground_estimate));
  assert.ok(plans.every(plan=>plan.kind==='SEGMENT'));
  assert.equal(plans.filter(p=>p.basis==='FOOT_RAY_PIXEL_BAND').length,29);assert.equal(plans.filter(p=>p.basis==='HEAD_RAY_HEIGHT_PRIOR').length,4);
  assert.deepEqual(new Set(plans.map(p=>p.basis_label)),new Set(['腳點像素帶','頭頂射線']));
  assert.ok(plans.every(p=>[...p.basis_label].length<=6));
  const foot=plans.find(p=>p.basis==='FOOT_RAY_PIXEL_BAND'),head=plans.find(p=>p.basis==='HEAD_RAY_HEIGHT_PRIOR');
  assert.match(displayLabel(foot),/^腳點像素帶 區間 \d\.\d m$/);assert.match(displayLabel(head),/^頭頂射線 區間 \d\.\d m$/);
  assert.ok(foot.details.some(line=>line.startsWith('像素帶 ±')));assert.ok(head.details.some(line=>line.startsWith('高度先驗')));
});

test('person scene: blind interval 4.8-8.0 s yields no observation, hence nothing drawn; 4.6 s and 8.2 s are the two endpoints',()=>{
  for(const t of [4.8,5.0,6.4,7.8,8.0])assert.deepEqual(groundObservationsAt(all,t),[],`t=${t}`);
  const at46=groundObservationsAt(all,4.6),at82=groundObservationsAt(all,8.2);
  assert.deepEqual(at46.map(o=>o.camera_id),[FRONT]);assert.deepEqual(at82.map(o=>o.camera_id),[REAR]);
  assert.equal(groundEstimatePlan(at46[0].ground_estimate).basis,'FOOT_RAY_PIXEL_BAND');assert.equal(groundEstimatePlan(at82[0].ground_estimate).basis,'HEAD_RAY_HEIGHT_PRIOR');
  assert.deepEqual(groundObservationsAt(all,4.6,{cameraId:REAR}),[]);
  assert.deepEqual(groundObservationsAt(all,4.6,{frameRef:'frame:other'}),[]);
  assert.equal(groundObservationsAt(all,4.6,{frameRef:at46[0].frame_ref}).length,1);
  const parent=new THREE.Group();
  assert.equal(syncGroundEstimateGroup(THREE,null,parent,groundObservationsAt(all,6.4),{span:100}),null);
  assert.equal(syncGroundEstimateGroup(THREE,null,parent,at46,{span:100}).children.length,1);
});

test('person scene: 2D tile overlay projects the floor segment through the calibration near the observation\'s own pixel, labelled, no midpoint position',()=>{
  const obs=groundObservationsAt(all,4.6,{cameraId:FRONT}),cal=person.calibrations[FRONT];
  const svg=groundEstimateTileSVG(obs,{calibration:cal,width:cal.width,height:cal.height,cameraId:FRONT});
  assert.match(svg,/data-ground-estimate="SEGMENT"/);assert.match(svg,/data-ground-basis="FOOT_RAY_PIXEL_BAND"/);assert.match(svg,/腳點像素帶 區間 0\.7 m/);
  const raw=person.observations.find(o=>o.observation_ref===obs[0].observation_ref),[x1,y1,x2,y2]=svg.match(/<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"/).slice(1).map(Number);
  const [u,v]=raw.contact_pixel;
  assert.ok(Math.hypot((x1+x2)/2-u,(y1+y2)/2-v)<12,'projected interval sits at the observation pixel');
  assert.ok(!/raw_|diagnostics/.test(svg));
  assert.equal(groundEstimateTileSVG([],{calibration:cal,width:cal.width,height:cal.height}),'');
  assert.equal(groundEstimateTileSVG(groundObservationsAt(all,6.4,{cameraId:FRONT}),{calibration:cal,width:cal.width,height:cal.height}),'');
});

test('person scene R2: raw_near_m / raw_far_m of every observation appear nowhere in plans, readout, tile SVG or 3D marks',()=>{
  const cal=person.calibrations[FRONT],items=groundObservationsAt(all,4.6);
  const outputs=[JSON.stringify(groundEstimatePlans(all)),groundEstimateReadout(all).join('\n'),
    groundEstimateTileSVG(groundObservationsAt(all,4.6,{cameraId:FRONT}),{calibration:cal,width:cal.width,height:cal.height}),
    JSON.stringify(syncGroundEstimateGroup(THREE,null,new THREE.Group(),items,{span:100}).children.map(c=>c.children.map(o=>[o.position.x,o.position.y,o.position.z])))];
  for(const o of all)for(const raw of [o.ground_estimate.diagnostics.raw_near_m,o.ground_estimate.segment.raw_near_m])
    for(const out of outputs)if(raw[0]!==o.ground_estimate.segment.near_m[0])assert.ok(!out.includes(String(raw[0])),`raw coordinate leaked: ${raw}`);
});

test('collect/load: observations without the field are dropped; extra cameras are queried only when the primary carries the field',async()=>{
  assert.deepEqual(collectGroundObservations([{timestamp:1,camera_id:'A'}],undefined,null),[]);
  const calls=[];
  const query=async id=>{calls.push(id);return {observations:byCamera(id)};};
  assert.deepEqual(await loadGroundObservations([{timestamp:1}],{cameraIds:[FRONT,REAR],cameraId:FRONT,query}),[]);assert.deepEqual(calls,[]);
  const loaded=await loadGroundObservations(byCamera(FRONT),{cameraIds:[FRONT,REAR],cameraId:FRONT,query});
  assert.deepEqual(calls,[REAR]);assert.equal(loaded.length,33);
  const failing=await loadGroundObservations(byCamera(FRONT),{cameraIds:[FRONT,REAR],cameraId:FRONT,query:async()=>{throw Error('x');}});
  assert.equal(failing.length,24);
});

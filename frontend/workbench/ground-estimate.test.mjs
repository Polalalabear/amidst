import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as THREE from 'three';
import {groundEstimatePlan,groundEstimatePlans,groundEstimateReadout,groundEstimateOverlaySVG,syncGroundEstimateGroup} from './ground-estimate.mjs';
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
  assert.deepEqual(s.details,['依據 HEAD_RAY_HEIGHT_PRIOR','約束 HEIGHT_PRIOR:BOUNDED → OCCLUDER_BEHIND:CLIPPED → WALKABLE_AREA:CLIPPED','像素靈敏度 0.24 m/px']);
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

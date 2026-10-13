import test from 'node:test';
import assert from 'node:assert/strict';
import {workspaceInvestigationScope,normalizeInvestigationScope,savedInvestigationScope,
  investigationWorkspaceScope} from './investigation-scope.mjs';

const snapshot={scene_id:'accuracy-v2',run_id:'source-run',time_range:[2,50],
  cameras:['CAM_A','CAM_B','CAM_C'].map(camera_id=>({camera_id}))};
const context={scene_id:snapshot.scene_id,source:{run_id:snapshot.run_id,time_range:snapshot.time_range},
  observation_mode:'photos_plus_observations',available_modes:['photos_only','photos_plus_observations'],
  product_context:{session_ref:'product-session',run_ref:'v2-product-run',product_freeze_ref:'v2-freeze'},
  cameras:snapshot.cameras.map(camera=>({...camera,camera_ref:'ref:'+camera.camera_id}))};
const binding={session_ref:context.product_context.session_ref,
  freeze_ref:context.product_context.product_freeze_ref,observation_mode:context.observation_mode};

test('workspace camera selection, time range and cursor roundtrip through resolved product references',()=>{
  const selection={cameraId:'CAM_B',cameraIds:['CAM_A','CAM_C'],start:8,end:19,timestamp:11};
  const initial=workspaceInvestigationScope(snapshot,selection);
  const scoped=normalizeInvestigationScope(context,initial);
  assert.equal(scoped.camera_ref,'ref:CAM_B');
  assert.deepEqual(scoped.camera_ids,['CAM_B','CAM_A','CAM_C']);
  assert.deepEqual(scoped.time_range,[8,19]);assert.equal(scoped.timestamp,11);
  assert.equal(scoped.run_ref,'v2-product-run');assert.equal(scoped.freeze_ref,'v2-freeze');
  assert.deepEqual(investigationWorkspaceScope(snapshot,scoped),{
    cameraId:'CAM_B',cameraIds:['CAM_B','CAM_A','CAM_C'],start:8,end:19,timestamp:11});
  assert.deepEqual(selection.cameraIds,['CAM_A','CAM_C']);
});

test('same named camera cannot restore a scope from another scene, source run, product run, freeze or mode',()=>{
  const scoped=normalizeInvestigationScope(context);
  for(const change of [{scene_id:'other-scene'},{run_id:'other-source'},
    {run_ref:'other-product'},{freeze_ref:'other-freeze'},{observation_mode:'photos_only'}])
    assert.throws(()=>normalizeInvestigationScope(context,{...scoped,...change}),/SCOPE_MISMATCH/);
  assert.throws(()=>investigationWorkspaceScope({...snapshot,run_id:'other-source'},scoped),/SCOPE_MISMATCH/);
});

test('invalid or outside-source windows and cameras fail closed without choosing substitute data',()=>{
  for(const time_range of [[0,8],[5,51],[20,19],[NaN,9],[5,Infinity]])
    assert.throws(()=>normalizeInvestigationScope(context,{time_range}),/INVALID_INVESTIGATION_RANGE/);
  assert.throws(()=>normalizeInvestigationScope({...context,source:{...context.source,time_range:[0,500]}},
    {time_range:[0,121]}),/INVALID_INVESTIGATION_RANGE/);
  assert.throws(()=>normalizeInvestigationScope(context,{camera_ids:['CAM_UNKNOWN']}),/CAMERA_DENIED/);
  assert.throws(()=>normalizeInvestigationScope(context,{timestamp:51}),/INVALID_INVESTIGATION_TIMESTAMP/);
});

test('saved cases restore exact camera/window/cursor only after binding, camera and source checks',()=>{
  const previous=normalizeInvestigationScope(context,{camera_ids:['CAM_A','CAM_C'],time_range:[5,12],timestamp:6});
  const saved={binding,camera_ref:'ref:CAM_B',time_range:[19,31]};
  const scope=savedInvestigationScope(context,saved,previous);
  assert.equal(scope.camera_ref,'ref:CAM_B');assert.deepEqual(scope.camera_ids,['CAM_B','CAM_A','CAM_C']);
  assert.deepEqual(scope.time_range,[19,31]);assert.equal(scope.timestamp,19);
  assert.deepEqual(previous.time_range,[5,12]);
  assert.throws(()=>savedInvestigationScope(context,{...saved,time_range:[19,51]},previous),/INVALID_INVESTIGATION_RANGE/);
  assert.throws(()=>savedInvestigationScope(context,{...saved,camera_ref:'ref:OTHER'},previous),/REFERENCE_DENIED/);
  assert.throws(()=>savedInvestigationScope(context,{...saved,binding:{...binding,observation_mode:'photos_only'}},previous),/PRODUCT_BINDING_DENIED/);
});

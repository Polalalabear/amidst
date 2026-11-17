import test from 'node:test';
import assert from 'node:assert/strict';
import { chooseCaptureIds } from '../src/capture-plan.mjs';
import { buildSystemMessage, validateSystemMessage, buildInferHeader } from '../src/protocol.mjs';

test('capture follows backend next ids, limited to explicitly registered cameras',()=>{
  assert.deepEqual(chooseCaptureIds(['A','B','C'],{next_camera_ids:['B','X']}),['B']);
  assert.deepEqual(chooseCaptureIds(['A','B'],null),['A','B']);
  assert.deepEqual(chooseCaptureIds(['A','B'],{next_camera_ids:['X']}),['A','B']);
});

test('schedule crosses protocol whitelist without operator data',()=>{
  const result={schedule:{mode:'adaptive',camera_ids:['A'],next_camera_ids:['A','B'],
    reason:'ACTIVE_NEIGHBORS',lost_rounds:0,radius:1,graph_sha256:'a'.repeat(64),operator_xy:[1,2]}};
  const msg=buildSystemMessage({tick:1,tCaptureMs:1,frames:[],result});
  assert.equal(msg.schedule.reason,'ACTIVE_NEIGHBORS');
  assert.ok(!('operator_xy' in msg.schedule));
  assert.deepEqual(validateSystemMessage(msg),[]);
  msg.schedule.truth='X';assert.ok(validateSystemMessage(msg).includes('schedule.truth'));
});

test('inference header may carry only available camera ids in addition to old fields',()=>{
  const h=buildInferHeader({tick:1,tCaptureMs:2,frames:[],availableCameras:['A','B']});
  assert.deepEqual(h.available_cameras,['A','B']);
});

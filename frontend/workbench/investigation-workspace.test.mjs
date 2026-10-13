import test from 'node:test';
import assert from 'node:assert/strict';
import {applyInvestigationWorkspaceScope} from './app.mjs';

const snapshot={scene_id:'v2',run_id:'source',time_range:[0,10],cameras:[{camera_id:'A'},{camera_id:'B'}]};
const target=()=>({cameraId:'A',cameraIds:['A'],start:0,end:4,timestamp:0,queryEpoch:2,timelineEpoch:3,eventEpoch:4,guideEpoch:5,events:[1],observations:[2],frames:[3],test:{old:true},guide:{old:true},selectedEvent:'old',event:{old:true},notes:[4],queryPending:true});
const scope=(fields={})=>({scene_id:'v2',run_id:'source',camera_ids:['B'],camera_id:'B',time_range:[2,6],timestamp:3,observation_mode:'photos_plus_observations',...fields});

test('scope return clears old query, test and event results and remains dirty across intermediate pages',()=>{
  const state=target();assert.equal(applyInvestigationWorkspaceScope(state,snapshot,scope()),true);
  assert.deepEqual([state.cameraId,state.start,state.end,state.timestamp],['B',2,6,3]);
  assert.deepEqual(state.events,[]);assert.deepEqual(state.observations,[]);assert.deepEqual(state.frames,[]);
  assert.equal(state.test,null);assert.equal(state.guide,null);assert.equal(state.selectedEvent,null);assert.equal(state.queryPending,false);
  assert.equal(state.investigationScopeDirty,true);state.page='test';state.page='dashboard';
  assert.equal(state.investigationScopeDirty,true);assert.equal(state.queryEpoch,3);assert.equal(state.timelineEpoch,4);
});
test('cursor-only changes invalidate late frame replies without clearing valid query records',()=>{
  const state=target();applyInvestigationWorkspaceScope(state,snapshot,scope({camera_id:'A',camera_ids:['A'],time_range:[0,4],timestamp:2}));
  assert.equal(state.queryEpoch,2);assert.equal(state.timelineEpoch,4);assert.deepEqual(state.frames,[]);assert.deepEqual(state.events,[1]);assert.equal(state.investigationScopeDirty,true);
});
test('foreign source scope cannot partially mutate the workspace',()=>{
  const state=target(),before=structuredClone(state);
  assert.throws(()=>applyInvestigationWorkspaceScope(state,snapshot,scope({run_id:'other'})),/SCOPE_MISMATCH/);
  assert.deepEqual(state,before);
});

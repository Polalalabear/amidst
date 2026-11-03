import test from 'node:test';
import assert from 'node:assert/strict';
import {gapStateAt,gapCaption} from './gap-state-model.mjs';
import {renderPanelHtml} from './track-map-render.mjs';
const decisions=[
  {source_time_us:4250000,step_index:0,state_after:'TEMP_LOST'},
  {source_time_us:6000000,step_index:1,state_after:'RETURNED_TO_ORIGIN'},
  {source_time_us:7900000,step_index:2,state_after:'ENDED'}];
test('GAP caption follows the decision journal at t, never later states',()=>{
  assert.equal(gapStateAt(decisions,5200000),'TEMP_LOST');
  assert.equal(gapStateAt(decisions,6000000),'RETURNED_TO_ORIGIN');
  assert.equal(gapStateAt(decisions,8000000),'ENDED');
  assert.equal(gapStateAt(decisions,1000000),null);
  assert.equal(gapStateAt(undefined,5200000),null);
  assert.equal(gapStateAt([{source_time_us:0,state_after:'NOT_A_STATE'}],5),null);
});
test('caption shows the single current state and UNKNOWN without a journal',()=>{
  const text=gapCaption(gapStateAt(decisions,5200000));
  assert.match(text,/TEMP_LOST/);assert.doesNotMatch(text,/RETURNED_TO_ORIGIN|ENDED/);
  assert.match(gapCaption(null),/UNKNOWN/);
});
test('track-map panel lists only the current state, not the segment history',()=>{
  const scene={notes:[],empty:true,layoutNote:'x',inGap:true,gap:{camera_shown:'A',states:['TEMP_LOST','RETURNED_TO_ORIGIN','ENDED']},gapNow:'TEMP_LOST',externalEnabled:false,legend:'l',identityLine:'i'};
  const html=renderPanelHtml(scene);
  assert.match(html,/目前狀態：暫失（TEMP_LOST）/);assert.doesNotMatch(html,/RETURNED_TO_ORIGIN|ENDED/);
  assert.match(renderPanelHtml({...scene,gapNow:null}),/UNKNOWN/);
});

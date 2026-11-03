import test from 'node:test';
import assert from 'node:assert/strict';
import {createStore,initialState} from './store.mjs';
import {createPhaseStore,attachPhase,outcomeOf,initialPhase,progressPercent,PROGRESS_CEILING} from './search-phase-model.mjs';

const tick=(p,ms,n=1)=>{for(let i=0;i<n;i++)p.dispatch({type:'TICK',dtMs:ms});};
const hitQ1={status:'READY',results:[{camera_id:'cam1',rank:1,matched_segments:[]}],no_match_cameras:[],not_evaluated_cameras:[],results_total:1,returned_count:1};
const hitQ2={status:'READY',timeline:[{kind:'ON_CAMERA',camera_id:'cam1',range_us:[0,10]}]};

test('wall -> searching on start; unknown mode ignored',()=>{
  const p=createPhaseStore();assert.equal(p.getState().phase,'wall');
  p.dispatch({type:'SEARCH_START',mode:'bogus'});assert.equal(p.getState().phase,'wall');
  p.dispatch({type:'SEARCH_START',mode:'find'});assert.equal(p.getState().phase,'searching');assert.equal(p.getState().progress,0);
});
test('progress creeps but never reaches 100% while waiting',()=>{
  const p=createPhaseStore();p.dispatch({type:'SEARCH_START',mode:'track'});
  tick(p,100,2000);const v=p.getState();
  assert.ok(v.progress>0.8&&v.progress<=PROGRESS_CEILING);assert.equal(v.phase,'searching');assert.ok(progressPercent(v.progress)<100);
});
test('find result: found -> progress runs to full within ~0.3 s -> result',()=>{
  const p=createPhaseStore();p.dispatch({type:'SEARCH_START',mode:'find'});tick(p,100,5);
  p.dispatch({type:'SEARCH_ARMED'});p.dispatch({type:'SEARCH_FOUND',mode:'find'});
  assert.equal(p.getState().phase,'searching');
  tick(p,100,1);assert.ok(p.getState().progress>0.3);
  tick(p,100,3);assert.equal(p.getState().progress,1);assert.equal(p.getState().phase,'result');assert.equal(p.getState().mode,'find');
});
test('a miss stays on the loading screen with the reason, never returns to wall or result',()=>{
  const p=createPhaseStore();p.dispatch({type:'SEARCH_START',mode:'find'});p.dispatch({type:'SEARCH_ARMED'});
  p.dispatch({type:'SEARCH_MISS',code:'NO_MATCH',message:'在已推論的影格中沒有找到；不代表目標不存在。'});
  tick(p,100,200);const s=p.getState();
  assert.equal(s.phase,'searching');assert.equal(s.miss.code,'NO_MATCH');assert.ok(s.progress<1);
  const frozen=s.progress;tick(p,100,50);assert.equal(p.getState().progress,frozen);
});
test('only an explicit SEARCH_END returns to the wall',()=>{
  const p=createPhaseStore();p.dispatch({type:'SEARCH_START',mode:'track'});p.dispatch({type:'SEARCH_ARMED'});p.dispatch({type:'SEARCH_MISS',code:'UNKNOWN'});
  tick(p,100,10);assert.equal(p.getState().phase,'searching');
  p.dispatch({type:'SEARCH_END'});assert.deepEqual(p.getState(),initialPhase());
});
test('outcomes are ignored until the new request starts loading (stale response guard)',()=>{
  const main=createStore(initialState({q1:hitQ1})),p=createPhaseStore();attachPhase(main,p);
  p.dispatch({type:'SEARCH_START',mode:'find'});assert.equal(p.getState().resolved,false);
  main.dispatch({type:'SET_TASK',task:'q1'});assert.equal(p.getState().resolved,false);
});
test('store wiring: loading arms, response resolves, error is a miss',()=>{
  const main=createStore(initialState()),p=createPhaseStore();attachPhase(main,p);
  p.dispatch({type:'SEARCH_START',mode:'track'});
  main.dispatch({type:'Q_LOADING',request:{},kind:'q2'});assert.equal(p.getState().armed,true);assert.equal(p.getState().resolved,false);
  main.dispatch({type:'Q_ERROR',error:{code:'MISSING',message:'來源缺失'}});
  assert.equal(p.getState().miss.code,'MISSING');assert.equal(p.getState().phase,'searching');
});
test('outcomeOf classifies Q1/Q2/Q3 states',()=>{
  assert.equal(outcomeOf({loading:true}).kind,'pending');
  assert.equal(outcomeOf({q1:hitQ1}).kind,'found');
  assert.equal(outcomeOf({q1:{...hitQ1,status:'NO_MATCH',results:[]}}).kind,'miss');
  assert.equal(outcomeOf({q2:hitQ2}).mode,'track');
  assert.equal(outcomeOf({q2:{status:'UNKNOWN',timeline:[{kind:'GAP'}]}}).kind,'miss');
  assert.equal(outcomeOf({seeds:{candidates:[]}}).kind,'found');
  assert.equal(outcomeOf({q3:{status:'PARSED'}}).kind,'pending');
  assert.equal(outcomeOf({q3:{status:'UNSUPPORTED_CLASS'}}).kind,'miss');
  assert.equal(outcomeOf({error:{code:'X'}}).kind,'miss');
  assert.equal(outcomeOf({}).kind,'idle');
});

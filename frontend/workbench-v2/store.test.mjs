import test from 'node:test';
import assert from 'node:assert/strict';
import { createStore, initialState, reduce } from './store.mjs';

const RUN = { run_id: 'R', fps: 5, duration_s: 20 };
const run = (s, ...actions) => actions.reduce(reduce, s);
const base = () => reduce(initialState(), { type: 'SET_RUN', run: RUN });

test('initial state: browse, 2D, pinned rail, t=0, grid null', () => {
  const s = initialState();
  assert.equal(s.mode, 'browse'); assert.equal(s.main, '2d'); assert.equal(s.rail, 'pinned');
  assert.equal(s.tMs, 0); assert.equal(s.speed, 1); assert.equal(s.grid, null);
  assert.equal(initialState({ rail: 'rail' }).rail, 'rail');
  assert.equal(initialState({ rail: 'overlay' }).rail, 'pinned'); // floating is never an initial state
});

test('switching 2D/3D changes only `main` (time, selection, pin, query, size, grid unchanged)', () => {
  let s = run(base(), { type: 'SET_T', tMs: 12470 }, { type: 'SELECT', selection: 'obs-1' }, { type: 'PIN', id: 'CAM_W1' },
    { type: 'SET_QUERY', query: { area: 'AREA_R101_FRONT' } }, { type: 'SET_SIZE', size: 8 }, { type: 'SET_SPEED', speed: 2 });
  for (const action of [{ type: 'SET_MAIN', main: '3d' }, { type: 'TOGGLE_MAIN' }, { type: 'TOGGLE_MAIN' }]) {
    const next = reduce(s, action);
    assert.deepEqual({ ...next, main: s.main }, s, 'only main differs');
    s = next;
  }
  assert.equal(s.main, '3d');
  assert.equal(s.tMs, 12470);
  assert.equal(s.selection, 'obs-1');
});

test('SET_MAIN with an unknown value or same value is a no-op (same object)', () => {
  const s = base();
  assert.equal(reduce(s, { type: 'SET_MAIN', main: 'vr' }), s);
  assert.equal(reduce(s, { type: 'SET_MAIN', main: '2d' }), s);
});

test('rail: burger cycles pinned -> collapsed -> floating -> collapsed', () => {
  let s = initialState();
  s = reduce(s, { type: 'TOGGLE_BURGER' }); assert.equal(s.rail, 'rail');
  s = reduce(s, { type: 'TOGGLE_BURGER' }); assert.equal(s.rail, 'overlay');
  s = reduce(s, { type: 'TOGGLE_BURGER' }); assert.equal(s.rail, 'rail');
});

test('rail: `[` toggles pinned <-> collapsed; floating closes to collapsed', () => {
  let s = initialState();
  s = reduce(s, { type: 'TOGGLE_PIN_RAIL' }); assert.equal(s.rail, 'rail');
  s = reduce(s, { type: 'TOGGLE_PIN_RAIL' }); assert.equal(s.rail, 'pinned');
  s = run(initialState({ rail: 'rail' }), { type: 'SET_RAIL', rail: 'overlay' }, { type: 'TOGGLE_PIN_RAIL' });
  assert.equal(s.rail, 'rail');
});

test('rail: Esc and main-area pointer close the floating panel; other states ignore them', () => {
  const floating = run(initialState({ rail: 'rail' }), { type: 'SET_RAIL', rail: 'overlay' });
  assert.equal(reduce(floating, { type: 'ESCAPE' }).rail, 'rail');
  assert.equal(reduce(floating, { type: 'MAIN_POINTER' }).rail, 'rail');
  const pinned = initialState();
  assert.equal(reduce(pinned, { type: 'ESCAPE' }), pinned);
  assert.equal(reduce(pinned, { type: 'MAIN_POINTER' }), pinned);
  const collapsed = initialState({ rail: 'rail' });
  assert.equal(reduce(collapsed, { type: 'MAIN_POINTER' }), collapsed);
});

test('rail: pinned/collapsed panel buttons; floating is not remembered as the preference', () => {
  let s = initialState();
  s = reduce(s, { type: 'SET_RAIL', rail: 'overlay' }); assert.equal(s.rail, 'overlay'); assert.equal(s.railPref, 'pinned');
  s = reduce(s, { type: 'SET_RAIL', rail: 'rail' }); assert.equal(s.railPref, 'rail');
  s = reduce(s, { type: 'SET_RAIL', rail: 'overlay' }); assert.equal(s.railPref, 'rail');
  assert.equal(reduce(s, { type: 'SET_RAIL', rail: 'sideways' }), s);
});

test('icons: when collapsed any icon opens the floating panel at that section; pinned stays pinned', () => {
  let s = reduce(initialState({ rail: 'rail' }), { type: 'ICON_CLICK', id: 'layers' });
  assert.equal(s.rail, 'overlay'); assert.equal(s.panelSection, 'layers');
  s = reduce(initialState(), { type: 'ICON_CLICK', id: 'prov' });
  assert.equal(s.rail, 'pinned'); assert.equal(s.panelSection, 'prov');
});

test('icons: find and demo also switch mode', () => {
  let s = reduce(initialState(), { type: 'ICON_CLICK', id: 'find' });
  assert.equal(s.mode, 'find'); assert.equal(s.panelSection, 'find');
  s = reduce(s, { type: 'ICON_CLICK', id: 'demo' });
  assert.equal(s.mode, 'demo'); assert.equal(s.panelSection, 'demo');
});

test('modes: browse -> find -> return restores time, size, pin; query survives a switch back to browse', () => {
  let s = run(base(), { type: 'SET_T', tMs: 4000 }, { type: 'SET_SIZE', size: 2 }, { type: 'PIN', id: 'CAM_W1' });
  s = run(s, { type: 'SET_MODE', mode: 'find' });
  assert.deepEqual(s.preQuery, { tMs: 4000, size: 2, pin: 'CAM_W1', tempPin: null, grid: null });
  s = run(s, { type: 'SET_QUERY', query: { q: 1 } }, { type: 'SET_T', tMs: 9000 }, { type: 'SET_SIZE', size: 8 }, { type: 'SET_MODE', mode: 'browse' });
  assert.deepEqual(s.query, { q: 1 });
  s = reduce(s, { type: 'REENTER_QUERY' });
  assert.equal(s.mode, 'find');
  s = reduce(s, { type: 'RETURN_FROM_QUERY' });
  assert.equal(s.mode, 'browse'); assert.equal(s.tMs, 4000); assert.equal(s.size, 2); assert.equal(s.pin, 'CAM_W1'); assert.equal(s.preQuery, null);
  assert.deepEqual(s.query, { q: 1 }, 'query kept for re-entry');
});

test('REENTER_QUERY without a query and RETURN_FROM_QUERY without a snapshot do nothing', () => {
  const s = initialState();
  assert.equal(reduce(s, { type: 'REENTER_QUERY' }), s);
  assert.equal(reduce(s, { type: 'RETURN_FROM_QUERY' }), s);
});

test('leaving demo clears the demo step; steps are 1-7', () => {
  let s = run(initialState(), { type: 'SET_MODE', mode: 'demo' }, { type: 'SET_DEMO_STEP', step: 3 });
  assert.equal(s.demoStep, 3);
  assert.equal(reduce(s, { type: 'SET_DEMO_STEP', step: 8 }).demoStep, null);
  assert.equal(reduce(s, { type: 'SET_MODE', mode: 'browse' }).demoStep, null);
});

test('pin and temporary pin: temp pin overrides, clearing restores the user pin', () => {
  let s = reduce(base(), { type: 'PIN', id: 'CAM_W1' });
  s = reduce(s, { type: 'TEMP_PIN', id: 'CAM_N1' });
  assert.equal(s.pin, 'CAM_N1'); assert.deepEqual(s.tempPin, { id: 'CAM_N1', prevPin: 'CAM_W1' });
  s = reduce(s, { type: 'TEMP_PIN', id: 'CAM_W2' }); // second temp pin still restores the original user pin
  assert.equal(s.tempPin.prevPin, 'CAM_W1');
  assert.equal(reduce(s, { type: 'CLEAR_TEMP_PIN' }).pin, 'CAM_W1');
  assert.equal(reduce(s, { type: 'CLEAR_TEMP_PIN' }).tempPin, null);
  assert.equal(reduce(s, { type: 'PIN', id: 'CAM_R102' }).tempPin, null, 'user pin supersedes temp pin');
});

test('time: SET_T clamps to [0, duration*1000-1]; SET_RUN re-clamps and stops playback', () => {
  let s = reduce(base(), { type: 'SET_T', tMs: 25000 });
  assert.equal(s.tMs, 19999);
  assert.equal(reduce(s, { type: 'SET_T', tMs: -3 }).tMs, 0);
  s = run(s, { type: 'PLAY' });
  assert.equal(s.tMs, 0, 'PLAY at the end restarts');
  s = run(s, { type: 'SET_T', tMs: 19000 }, { type: 'SET_RUN', run: { run_id: 'S', fps: 5, duration_s: 10 } });
  assert.equal(s.tMs, 9999); assert.equal(s.playing, false);
});

test('play/pause/speed; PLAY needs a run; only 0.5/1/2 speeds', () => {
  assert.equal(reduce(initialState(), { type: 'PLAY' }).playing, false);
  let s = run(base(), { type: 'TOGGLE_PLAY' }); assert.equal(s.playing, true);
  s = reduce(s, { type: 'TOGGLE_PLAY' }); assert.equal(s.playing, false);
  assert.equal(reduce(s, { type: 'SET_SPEED', speed: 2 }).speed, 2);
  assert.equal(reduce(s, { type: 'SET_SPEED', speed: 3 }), s);
});

test('SET_SIZE accepts 1/2/4/8 only', () => {
  const s = base();
  for (const n of [1, 2, 4, 8]) assert.equal(reduce(s, { type: 'SET_SIZE', size: n }).size, n);
  assert.equal(reduce(s, { type: 'SET_SIZE', size: 3 }), s);
});

test('createStore: notifies on change, not on no-op; unsubscribe works', () => {
  const store = createStore(base());
  const seen = [];
  const off = store.subscribe((s, prev, a) => seen.push(a.type));
  store.dispatch({ type: 'SET_MAIN', main: '3d' });
  store.dispatch({ type: 'SET_MAIN', main: '3d' });
  store.dispatch({ type: 'UNKNOWN_ACTION' });
  off();
  store.dispatch({ type: 'SET_MAIN', main: '2d' });
  assert.deepEqual(seen, ['SET_MAIN']);
});

test('Q task/playback state preserves exact microseconds and does not expose unvalidated responses',async()=>{
 const {readFile}=await import('node:fs/promises');const {validateQResponse}=await import('./q-validate.mjs');
 const doc=JSON.parse(await readFile(new URL('fixtures/q2-rule.json',import.meta.url),'utf8'));const checked=await validateQResponse('q2',doc.cases[0].response_json);assert.equal(checked.ok,true);
 let s=initialState({reviewMode:true});assert.equal(s.task,'q1');assert.equal(s.switchMode,'RULE_ONLY');
 assert.equal(reduce(s,{type:'Q_RESPONSE',kind:'q2',data:JSON.parse(doc.cases[0].response_json)}),s);
 s=reduce(s,{type:'Q_RESPONSE',kind:'q2',data:checked.data});assert.equal(s.task,'q2');
 s=reduce(s,{type:'SET_T_US',tUs:200001});assert.equal(s.tUs,200001);assert.equal(s.tMs,200.001);
 const copy=reduce(s,{type:'SET_PLAYBACK_MODE',value:'single'});assert.equal(copy.tUs,s.tUs);assert.equal(copy.q2,s.q2);assert.equal(copy.reviewMode,true);
 assert.equal(reduce(s,{type:'SET_T_US',tUs:.5}),s);
 assert.equal(reduce(s,{type:'Q_ARTIFACTS',for_hash:'foreign',data:{}}),s);
});

test('new Q query clears drawable data and source change resets switch mode',()=>{
 let s=initialState({q1:{old:true},q2:{old:true},switchMode:'AGENT_SEQUENTIAL',playing:true});
 s=reduce(s,{type:'Q_LOADING',kind:'q1',request:{schema_version:'SYNTHETIC'}});assert.equal(s.q1,null);assert.equal(s.q2,null);assert.equal(s.playing,false);
 s=reduce(s,{type:'SET_Q_RUN',run:{clock_mapping:{source_duration_us:2000000}}});assert.equal(s.switchMode,'RULE_ONLY');
 s=reduce(s,{type:'PLAY'});assert.equal(s.playing,false);s=reduce(s,{type:'PAUSE'});assert.equal(s.playing,false);
});

test('Q playback restarts at the actual short session or selected segment boundary',()=>{const activeRun={clock_mapping:{source_duration_us:2000000}};let s=initialState({task:'q2',activeRun,q2:{timeline:[{range_us:[200000,1000000]}]},tUs:1000000});s=reduce(s,{type:'PLAY'});assert.equal(s.tUs,200000);assert.equal(s.playing,true);let q1=initialState({activeRun,task:'q1',q1:{},selection:{kind:'Q1_SEGMENT',range_us:[400000,800000]},tUs:800000});q1=reduce(q1,{type:'PLAY'});assert.equal(q1.tUs,400000);assert.equal(q1.playing,true);});

test('manual query clears stale Q3 parse; parser child execution preserves only its own parse',()=>{const parse={status:'PARSED'},s=initialState({q3:parse});assert.equal(reduce(s,{type:'Q_LOADING',kind:'q1',request:{}}).q3,null);const child=reduce(s,{type:'Q_LOADING',kind:'q2',request:{},keepParse:true});assert.equal(child.q3,parse);assert.equal(child.task,'q2');});

test('recorded source banner is per response and clears for the next live query',async()=>{const {readFile}=await import('node:fs/promises'),{validateQResponse}=await import('./q-validate.mjs');const raw=JSON.parse(await readFile(new URL('./fixtures/q2-rule.json',import.meta.url),'utf8')).cases[0].response_json;const checked=await validateQResponse('q2',raw);let s=reduce(initialState(),{type:'Q_RESPONSE',kind:'q2',data:checked.data,source_origin:'RECORDED',source_kind:'SYNTHETIC',recorded_at:'2026-10-22T00:00:00Z'});assert.equal(s.responseOrigin,'RECORDED');assert.equal(s.recordedKind,'SYNTHETIC');assert.equal(s.recordedAt,'2026-10-22T00:00:00Z');s=reduce(s,{type:'Q_LOADING',kind:'q1',request:{}});assert.equal(s.responseOrigin,null);assert.equal(s.recordedKind,null);assert.equal(s.recordedAt,null);});

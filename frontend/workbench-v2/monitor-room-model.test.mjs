import test from 'node:test';
import assert from 'node:assert/strict';
import {gridFor,wallCameras,normalizeSettings,createSettingsStore,resolveRun,advanceClock,tileEntries,skippedFrames,frameIntervalUs,stampFor,SETTINGS_KEY} from './monitor-room-model.mjs';

const run=(id,cams,extra={})=>({scene_id:'S',run_id:id,camera_ids:cams,sampling:{per_camera:cams.map(c=>({camera_id:c,source_frame_interval_us:50000}))},clock_mapping:{source_duration_us:8000000},...extra});
const memory=()=>{const m=new Map();return {getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v),m};};

test('layout auto-arranges 2..8 cameras and never leaves a ragged column count', () => {
  const expected={1:[1,1],2:[2,1],3:[2,2],4:[2,2],5:[3,2],6:[3,2],7:[4,2],8:[4,2]};
  for(const [n,[cols,rows]] of Object.entries(expected))assert.deepEqual(gridFor(Number(n)),{cols,rows},`n=${n}`);
  assert.deepEqual(gridFor(0),{cols:0,rows:0});
});

test('wall cameras follow the data: run order, admin subset, cap of 8', () => {
  const ten=Array.from({length:10},(_,i)=>'C'+i);
  assert.deepEqual(wallCameras(run('r',['A','B'])),['A','B']);
  assert.equal(wallCameras(run('r',ten)).length,8);
  assert.deepEqual(wallCameras(run('r',['A','B','C']),['C','A','Z']),['A','C']);
  assert.deepEqual(wallCameras(null),[]);
});

test('a camera without RGB is MISSING, an unprobed camera is PENDING, never READY by default', () => {
  const frames=new Map([['A','READY'],['B','MISSING']]);
  assert.deepEqual(tileEntries(['A','B','C'],frames).map(e=>e.status),['READY','MISSING','PENDING']);
  assert.equal(tileEntries(['A'],new Map([['A','BUFFERING']]))[0].status,'MISSING');
});

test('settings are normalised; bad values fall back to defaults', () => {
  const s=normalizeSettings({selection:{kind:'run',scene_id:'S',run_id:'r',extra:1},speed:3,startUs:-5,loop:'yes',cameras:['A','A',1],playing:false});
  assert.deepEqual(s.selection,{kind:'run',scene_id:'S',run_id:'r'});
  assert.equal(s.speed,1);assert.equal(s.startUs,0);assert.equal(s.loop,true);assert.equal(s.cameras,null);assert.equal(s.playing,false);
  assert.equal(normalizeSettings({selection:{kind:'recording'}}).selection,null);
  assert.equal(normalizeSettings(null).playing,true);
});

test('admin selection switches the wall content (settings store -> resolved run)', () => {
  const bootstrap={runs:[run('small',['A','B']),run('big',['A','B','C','D','E'])]};
  const store=createSettingsStore(memory());
  assert.equal(resolveRun(bootstrap,store.get().selection).run_id,'big','auto picks the run with most cameras');
  const seen=[];store.subscribe(s=>seen.push(s.selection));
  store.set({selection:{kind:'run',scene_id:'S',run_id:'small'}});
  assert.equal(resolveRun(bootstrap,store.get().selection).run_id,'small');
  assert.equal(seen.length,1);
  assert.equal(resolveRun(bootstrap,{kind:'run',scene_id:'S',run_id:'gone'}),null,'unknown run is null, not a fallback');
  const scopes={rec1:{scene_id:'S',run_id:'big'}};
  assert.equal(resolveRun(bootstrap,{kind:'recording',recording_id:'rec1'},id=>scopes[id]??null).run_id,'big');
  assert.equal(resolveRun(bootstrap,{kind:'recording',recording_id:'unplayed'},id=>scopes[id]??null),null);
  assert.equal(resolveRun({runs:[]},null),null);
});

test('settings persist to storage and a storage event from another tab re-reads them', () => {
  const storage=memory();let fire;
  const a=createSettingsStore(storage,{listen:fn=>{fire=fn;return()=>{};}});
  const b=createSettingsStore(storage);
  b.set({speed:2,playing:false});
  assert.equal(a.get().speed,1);
  const seen=[];a.subscribe(s=>seen.push(s.speed));fire();
  assert.deepEqual(seen,[2]);assert.equal(a.get().playing,false);
  assert.ok(storage.m.has(SETTINGS_KEY));
  assert.equal(createSettingsStore({getItem(){throw new Error('x');},setItem(){throw new Error('x');}}).set({speed:2}).speed,2,'storage failure is swallowed');
});

test('restart bumps the counter so a held start time can be re-applied', () => {
  const s=createSettingsStore(memory());const r0=s.get().restart;s.restart();s.restart();assert.equal(s.get().restart,r0+2);
});

test('clock: speed scales, loop wraps to the start time, no-loop holds the last frame', () => {
  const o={speed:2,startUs:1000000,durationUs:8000000,loop:true};
  assert.equal(advanceClock(0,100,o).tUs,200000);
  const w=advanceClock(7900000,100,o);assert.equal(w.tUs,1100000);assert.equal(w.ended,false);
  const h=advanceClock(7900000,100,{...o,loop:false});assert.equal(h.tUs,7999999);assert.equal(h.ended,true);
  assert.deepEqual(advanceClock(5,10,{...o,durationUs:0}),{tUs:0,ended:true});
});

test('frame stamps use the smallest source interval; skipped frames are counted, not hidden', () => {
  const r=run('r',['A','B']);r.sampling.per_camera[1].source_frame_interval_us=100000;
  assert.equal(frameIntervalUs(r),50000);assert.equal(frameIntervalUs(r,['B']),100000);assert.equal(frameIntervalUs({}),null);
  assert.equal(stampFor(123456,50000),100000);
  assert.equal(skippedFrames(null,200000,50000),0);
  assert.equal(skippedFrames(100000,100000,50000),0);
  assert.equal(skippedFrames(100000,150000,50000),0);
  assert.equal(skippedFrames(100000,250000,50000),2);
  assert.equal(skippedFrames(7950000,0,50000,{wrapped:true}),0);
});

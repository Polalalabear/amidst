import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {advanceUs,formatVirtual} from './q-time.mjs';
import {createStore,initialState} from './store.mjs';
const read=n=>readFileSync(new URL(n,import.meta.url),'utf8');
const mapping={mapping_kind:'DECLARED_DEMO_CLOCK',timezone:'Asia/Taipei',wall_origin:'2026-11-01T13:00:00+08:00',t0_us:0,rate:1};

test('1.5× is accepted by the store and the playback clock; unknown speeds are still refused',()=>{
  const store=createStore(initialState());
  for(const speed of [1,1.5,2]){store.dispatch({type:'SET_SPEED',speed});assert.equal(store.getState().speed,speed);}
  store.dispatch({type:'SET_SPEED',speed:3});assert.equal(store.getState().speed,2);
  assert.equal(advanceUs(0,1000,1.5,50e6).tUs,1500000);
  assert.throws(()=>advanceUs(0,1000,3,50e6),/PLAYBACK_CLOCK_INVALID/);
});

test('speed never makes source time or the virtual-world time drift: 1× and 1.5× and 2× land on the same source instants',()=>{
  for(const speed of [1,1.5,2]){
    let t=0,carry=0,wall=0;
    while(t<5150000){const r=advanceUs(t,16.667,speed,50e6,carry);t=r.tUs;carry=r.carry;wall+=16.667;}
    assert.ok(t>=5150000&&t<5150000+16.667*1000*speed+1,`${speed}x overshoots by more than one tick`);
    assert.ok(Math.abs(wall-5150/speed)<20,`${speed}x wall time ${wall}`);
  }
  assert.equal(formatVirtual(5150000,mapping),'2026-11-01 13:00:05.15（UTC+8）');   // the label is a pure function of source µs
});

test('the speed selectors offer 1×/1.5×/2× on the workbench transport and the admin page',()=>{
  for(const [file,id] of [['index.html','q-speed'],['admin.html','admin-speed']]){
    const html=read(file),select=html.slice(html.indexOf(`id="${id}"`),html.indexOf('</select>',html.indexOf(`id="${id}"`)));
    for(const v of ['value="1"','value="1.5"','value="2"'])assert.ok(select.includes(v),`${file} ${v}`);
  }
});

import {createSpeedMeter,formatSpeedNote} from './speed-meter.mjs';
test('actual speed: steady 2× reads 2×; a decode that only keeps up with 1.4× reads 1.4× (never skips); stall lowers it; pause/seek restart the window',()=>{
  const m=createSpeedMeter();let ms=0,us=0;
  for(let i=0;i<100;i++){ms+=20;us+=40000;m.record(us,ms);}            // 20 ms wall -> 40 ms source = 2×
  assert.ok(Math.abs(m.actual()-2)<0.01);
  const slow=createSpeedMeter();ms=0;us=0;
  for(let i=0;i<150;i++){ms+=20;us+=28000;slow.record(us,ms);}          // set 2× but only 1.4× source per wall
  assert.ok(Math.abs(slow.actual()-1.4)<0.01);
  assert.equal(formatSpeedNote(2,slow.actual()),'設定 2× · 實際 1.4×');
  assert.ok(slow.actual(ms+1500)<0.7);                                   // stalled for 1.5 s: the figure falls, no stale 1.4×
  const seek=createSpeedMeter();seek.record(0,0);seek.record(40000,20);seek.record(30000000,40);   // a seek restarts, it is not "1500×"
  assert.equal(seek.actual(),null);
  slow.reset();assert.equal(slow.actual(),null);
  assert.equal(formatSpeedNote(1.5,null),'設定 1.5×');assert.equal(formatSpeedNote(1,0.96),'設定 1× · 實際 1×');
  for(const bad of [NaN,undefined])assert.doesNotThrow(()=>slow.record(bad,1));
});
test('playback never skips to catch up: playbackDelta waits for a ready frame, so the source clock simply runs slower',async()=>{
  const {playbackDelta}=await import('./q-playback.mjs');
  const s={speed:2,activeRun:{sampling:{per_camera:[{source_frame_interval_us:50000}]}}};
  assert.equal(playbackDelta(s,500,false),0);                            // frame not ready: no advance, no jump
  assert.ok(playbackDelta(s,500,true)<=25+1e-9);                         // when ready: at most one frame interval per tick
});
test('the playback bar shows the setting and the actual speed; the label clock is untouched',()=>{
  assert.match(read('index.html'),/id="q-speed-note"/);
  assert.match(read('app.mjs'),/formatSpeedNote\(s\.speed/);
  assert.doesNotMatch(read('speed-meter.mjs'),/virtualTime|wall_origin|stamp/);
});

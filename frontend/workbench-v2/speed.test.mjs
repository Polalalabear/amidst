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

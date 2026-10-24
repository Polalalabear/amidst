import test from 'node:test';
import assert from 'node:assert/strict';
import {seekSource} from './shell-view.mjs';
import {createFrameBuffer,canPlay,lastSourceTime} from './q-playback.mjs';
const run={scene_id:'S',run_id:'R',detection_index_sha256:'i',clock_mapping:{content_sha256:'c'}};
const tile=(camera_id,pin='p')=>({camera_id,status:'READY',media_url:'/test',served_sha256:pin});
test('empty query cannot play; half-open endpoint resolves only for display, never at a future frame',()=>{
 assert.equal(canPlay({task:'q1',activeRun:run}),false);assert.equal(canPlay({task:'q2',q2:{timeline:[1]}}),true);
 assert.equal(canPlay({task:'q1',q1:{},selection:{kind:'Q1_SEGMENT'}}),true);assert.equal(canPlay({task:'q2',loading:true,q2:{timeline:[1]}}),false);
 assert.equal(lastSourceTime(6000000,0,6000000),5999999);assert.equal(lastSourceTime(100,0,6000000),100);
});
test('parallel frame requests resolve independently and repeated pixels decode once',async()=>{
 let calls=0,decodes=0;const buffer=createFrameBuffer({frames:async(r,t,c)=>{calls++;return {ok:true,data:{tiles:c.map(x=>tile(x))}};}},{decode:async()=>{decodes++;return {image:'decoded'};}});
 const [a,b]=await Promise.all([buffer.prepare(run,0,['A']),buffer.prepare(run,200000,['B'])]);
 assert.equal(a.get('A').status,'READY');assert.equal(b.get('B').status,'READY');assert.equal(decodes,1);
 await buffer.prepare(run,0,['A']);assert.equal(calls,2);buffer.destroy();
});
test('missing and decode failure never reuse another camera or timestamp',async()=>{
 const buffer=createFrameBuffer({frames:async()=>({ok:true,data:{tiles:[tile('A'),{camera_id:'B',status:'MISSING'}]}})},{decode:async()=>{throw Error('tampered');}});
 const result=await buffer.prepare(run,0,['A','B']);assert.equal(result.get('A').status,'MISSING');assert.equal(result.get('B').status,'MISSING');assert.equal(buffer.stats.errors,1);buffer.destroy();
});
test('changing pinned source rejects an in-flight old result',async()=>{
 let complete;const buffer=createFrameBuffer({frames:()=>new Promise(resolve=>{complete=resolve;})},{decode:async()=>({})});
 const old=buffer.prepare(run,0,['A']);buffer.reset({...run,detection_index_sha256:'changed'});complete({ok:true,data:{tiles:[tile('A')]}});await assert.rejects(old,/STALE_RGB_SCOPE/);buffer.destroy();
});

test('source scrub captures the new value before PAUSE subscribers repaint the controlled slider',()=>{
 const event={target:{value:'2500000'}},actions=[];
 seekSource(event,action=>{actions.push(action);if(action.type==='PAUSE')event.target.value='0';});
 assert.deepEqual(actions,[{type:'PAUSE'},{type:'SET_T_US',tUs:2500000}]);
});

test('320 distinct dynamic frames evict old pixels and remain below 64 MiB',async()=>{
 let released=0;const buffer=createFrameBuffer({frames:async(r,t,c)=>({ok:true,data:{tiles:c.map(x=>tile(x,x+t))}})},{decode:async()=>({image:{naturalWidth:960,naturalHeight:540},release:()=>released++})});
 for(let i=0;i<160;i++){const result=await buffer.prepare(run,i*50000,['A','B']);assert.equal(result.get('A').status,'READY');assert.equal(result.get('B').status,'READY');result.release();}
 assert.equal(buffer.stats.errors,0);assert.equal(buffer.stats.media_loads,320);assert.ok(buffer.stats.peak_decoded_bytes<=67108864);assert.ok(buffer.stats.pixel_entries<=32);assert.ok(released>=288);buffer.destroy();assert.equal(buffer.stats.decoded_bytes,0);assert.equal(released,320);
});
test('active frame lease survives eviction and releases once after decode consumer finishes',async()=>{
 const released=[];const buffer=createFrameBuffer({frames:async(r,t,c)=>({ok:true,data:{tiles:c.map(x=>tile(x,String(t)))}})},{limit:2,maxBytes:12,decode:async t=>({image:{naturalWidth:1,naturalHeight:1},release:()=>released.push(t.served_sha256)})});
 const visible=await buffer.prepare(run,0,['A']);for(let t=1;t<10;t++)await buffer.prefetch(run,t,['A']);assert.equal(visible.get('A').status,'READY');assert.ok(!released.includes('0'));visible.release();visible.release();buffer.destroy();assert.equal(released.filter(x=>x==='0').length,1);assert.equal(buffer.stats.errors,0);assert.ok(buffer.stats.peak_decoded_bytes<=12);
});

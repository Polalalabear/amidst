import test from 'node:test';
import assert from 'node:assert/strict';
import {seekSource} from './shell-view.mjs';
import {createFrameBuffer,canPlay,lastSourceTime,playbackDelta,mediaSettled,afterTick} from './q-playback.mjs';
import {advanceUs} from './q-time.mjs';
import {createStore,initialState} from './store.mjs';
import {stepRows} from './q5-steps-model.mjs';
import {gapStateAt} from './gap-state-model.mjs';
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

test('buffering pauses source clock; RAF stalls and 2x never skip a source frame',()=>{
 const s={speed:1,activeRun:{sampling:{per_camera:[{source_frame_interval_us:50000}]}}};
 assert.equal(playbackDelta(s,800,false),0);assert.equal(playbackDelta(s,800,true),50);assert.equal(playbackDelta(s,16.67,true),16.67);assert.equal(playbackDelta({...s,speed:2},80,true),25);
});

test('settled missing can resume playback; buffering/undecoded/empty cannot',()=>{
 assert.equal(mediaSettled([]),false);assert.equal(mediaSettled([{status:'BUFFERING',imageReady:true}]),false);assert.equal(mediaSettled([{status:'READY',imageReady:false}]),false);assert.equal(mediaSettled([{status:'READY',imageReady:true},{status:'MISSING',imageReady:false}]),true);
});

// Same step the app's rAF frame() takes, driven against the real store.
function tick(store,{loop,deltaMs=100,end=8000000,start=0}){
 const s=store.getState(),step=afterTick(advanceUs(s.tUs,deltaMs,1,end,0),{loop,start,end});
 store.dispatch({type:'SET_T_US',tUs:step.tUs});if(step.pause)store.dispatch({type:'PAUSE'});return step;
}
const journal=[{source_time_us:4250000,step_index:0,state_before:null,state_after:'TEMP_LOST',accepted:true,decided_by:'RULE_ONLY'},
 {source_time_us:5150000,step_index:1,state_before:'TEMP_LOST',state_after:'SWITCHING',accepted:true,decided_by:'RULE_ONLY',executed_action:'SWITCH'}];
function playingStore(){
 const q2={timeline:[{kind:'ON_CAMERA',camera_id:'A',range_us:[0,4000000]},{kind:'GAP',range_us:[4000000,5150000],gap_states:[],camera_shown:'A',position:null},{kind:'ON_CAMERA',camera_id:'B',range_us:[5150000,8000000]}],output_sha256:'x'};
 const store=createStore({...initialState({}),task:'q2',q2,tUs:7850000,tMs:7850,playing:true,activeRun:{clock_mapping:{source_duration_us:8000000}}});return store;
}
test('loop on: reaching the end wraps to 0 and keeps playing, with switch state and log reset',()=>{
 const store=playingStore();
 assert.equal(stepRows(journal,store.getState().q2,store.getState().tUs).length,2);
 const step=tick(store,{loop:true,deltaMs:200});
 assert.equal(step.pause,false);assert.equal(store.getState().tUs,0);assert.equal(store.getState().playing,true);
 assert.equal(stepRows(journal,store.getState().q2,store.getState().tUs).length,0);assert.equal(gapStateAt(journal,store.getState().tUs),null);
 tick(store,{loop:true});assert.equal(store.getState().tUs,100000);assert.equal(store.getState().playing,true);
});
test('loop off: reaching the end holds at the end and pauses',()=>{
 const store=playingStore();const step=tick(store,{loop:false,deltaMs:200});
 assert.equal(step.pause,true);assert.equal(store.getState().tUs,8000000);assert.equal(store.getState().playing,false);
});
test('loop follows the setting each tick: unticking then ticking again changes the outcome',()=>{
 let store=playingStore();tick(store,{loop:false,deltaMs:200});assert.equal(store.getState().playing,false);
 store=playingStore();tick(store,{loop:true,deltaMs:200});assert.equal(store.getState().tUs,0);
 assert.deepEqual(afterTick({ended:true,tUs:5,carry:.5},{loop:true,start:5,end:5}),{tUs:5,carry:.5,pause:true});// empty range never loops
});

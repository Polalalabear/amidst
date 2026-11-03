import test from 'node:test';
import assert from 'node:assert/strict';
import {paintBoxes,watchBoxes} from './q2-box-redraw.mjs';
import {placeBox} from './q2-session-model.mjs';
const mkTarget=(w,h)=>{const t={clientWidth:w,clientHeight:h,children:[],dataset:{status:'READY'},
  querySelectorAll:()=>t.children.filter(c=>c.className==='q2-box'),
  append(...c){for(const x of c){x.parentNode=t;t.children.push(x);}}};return t;};
const create=(tag,text,cls)=>({tag,className:cls,style:{},remove(){const i=target0.children.indexOf(this);if(i>=0)target0.children.splice(i,1);}});
let target0;
const OBS=[{bbox_xyxy_px:[100,100,300,500]}];
test('paintBoxes places the box in the letterboxed contain frame',()=>{
  target0=mkTarget(800,450);const img={naturalWidth:1600,naturalHeight:900,parentNode:target0};
  paintBoxes(target0,img,OBS,create);
  const want=placeBox(OBS[0].bbox_xyxy_px,1600,900,800,450);
  assert.equal(target0.children.length,1);assert.equal(target0.children[0].style.left,want.left+'%');assert.equal(target0.children[0].style.top,want.top+'%');
});
test('a resize of the container (dock opening) re-lays out the paused frame instead of leaving the old box',()=>{
  target0=mkTarget(1000,562);const img={naturalWidth:1600,naturalHeight:900,parentNode:target0};
  const entries=new Map([[target0,{img,observations:OBS}]]);let fire;
  class RO{constructor(f){fire=f;}observe(){}disconnect(){this.off=true;}}
  const stop=watchBoxes(target0,entries,create,RO);
  paintBoxes(target0,img,OBS,create);const before={...target0.children[0].style};
  target0.clientWidth=700;target0.clientHeight=700;fire();   // narrower, taller: different letterbox
  const want=placeBox(OBS[0].bbox_xyxy_px,1600,900,700,700);
  assert.equal(target0.children.length,1,'old box replaced, not duplicated');
  assert.equal(target0.children[0].style.left,want.left+'%');assert.equal(target0.children[0].style.top,want.top+'%');
  assert.notEqual(target0.children[0].style.top,before.top,'box moved with the letterbox');
  img.parentNode=null;target0.children.length=0;fire();assert.equal(target0.children.length,0,'no boxes for a frame replaced by text');
  assert.doesNotThrow(stop);
});
test('no ResizeObserver: watcher is a harmless no-op',()=>{assert.doesNotThrow(watchBoxes(mkTarget(1,1),new Map(),create,undefined));});

test('a resize while the cell is BUFFERING (boxes cleared by pending) does not bring the old box back',()=>{
  target0=mkTarget(1000,562);target0.dataset={status:'READY'};const img={naturalWidth:1600,naturalHeight:900,parentNode:target0};
  const entries=new Map([[target0,{img,observations:OBS}]]);let fire;
  class RO{constructor(f){fire=f;}observe(){}disconnect(){}}
  watchBoxes(target0,entries,create,RO);paintBoxes(target0,img,OBS,create);assert.equal(target0.children.length,1);
  // what q-playback.pending does, and q2-view then forgets the drawn entry
  target0.dataset.status='BUFFERING';target0.children.length=0;
  target0.clientWidth=700;fire();assert.equal(target0.children.length,0,'status guard');
  entries.delete(target0);target0.dataset.status='READY';fire();assert.equal(target0.children.length,0,'entry guard');
});

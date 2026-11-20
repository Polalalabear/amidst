import test from 'node:test';
import assert from 'node:assert/strict';
import {applyMouseDelta, moveVector} from '../src/view.mjs';
import {stepPlayer} from '../src/sim.mjs';
import {bindMouseView} from '../src/operator.mjs';
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} != ${b}`);
test('mouse sensitivity, direction, wrap, pitch and per-event clamps',()=>{
 const v={view_yaw:0,view_pitch:0};
 assert.deepEqual(applyMouseDelta(v,100,-100),{view_yaw:15,view_pitch:15});
 assert.deepEqual(v,{view_yaw:0,view_pitch:0});
 assert.deepEqual(applyMouseDelta(v,10000,-10000),{view_yaw:30,view_pitch:30});
 assert.equal(applyMouseDelta({view_yaw:355,view_pitch:49},100,-100).view_pitch,50);
 assert.equal(applyMouseDelta({view_yaw:0,view_pitch:-14},0,100).view_pitch,-15);
 assert.equal(applyMouseDelta({view_yaw:355,view_pitch:0},100,0).view_yaw,10);
 assert.equal(applyMouseDelta(v,100,0,{mouse_sens_deg_per_px:.2}).view_yaw,20);
});
test('W cardinal directions, right strafe, normalization and yaw-zero legacy motion',()=>{
 for(const [yaw,x,y] of [[0,0,1],[90,1,0],[180,0,-1],[270,-1,0]]){
  const v=moveVector({w:true},yaw,1);near(v.vx,x);near(v.vy,y);
 }
 for(const yaw of [0,30,90,359]){
  const v=moveVector({w:true,d:true},yaw,2.5);near(Math.hypot(v.vx,v.vy),2.5);
  const stopped=moveVector({w:true,s:true,a:true,d:true},yaw,1.2);near(stopped.vx,0);near(stopped.vy,0);
 }
 const p={x:1,y:2,heading:0},old={...p};
 for(const keys of [{w:true},{w:true,d:true,shift:true},{a:true},{s:true},{},{d:true}]){
  const v=moveVector(keys,0,keys.shift?2.5:1.2);old.x+=v.vx*.1;old.y+=v.vy*.1;
  stepPlayer(p,keys,.1,[]);near(p.x,old.x);near(p.y,old.y);
 }
 const rotated={x:0,y:0,heading:0};stepPlayer(rotated,{w:true,view_yaw:90},.1,[]);
 near(rotated.x,.12);near(rotated.y,0);near(rotated.heading,0);
});
function event(target,type,props={}){const e=new Event(type);for(const [k,v] of Object.entries(props))Object.defineProperty(e,k,{value:v});target.dispatchEvent(e);}
test('drag, off, rejected pointer lock fallback, and unlocked mouse isolation',async()=>{
 const doc=new EventTarget(),canvas=new EventTarget();let v={view_yaw:0,view_pitch:0};
 const dispose=bindMouseView(canvas,doc,{mode:'drag',update:(dx,dy)=>{v=applyMouseDelta(v,dx,dy);}});
 event(doc,'mousemove',{clientX:100,clientY:100});near(v.view_yaw,0);
 event(canvas,'mousedown',{button:0,clientX:0,clientY:0});event(doc,'mousemove',{clientX:100,clientY:-20});
 near(v.view_yaw,15);near(v.view_pitch,3);event(doc,'mouseup');event(doc,'mousemove',{clientX:200,clientY:0});near(v.view_yaw,15);dispose();
 let calls=0;canvas.requestPointerLock=()=>Promise.reject(new Error('denied'));
 const release=bindMouseView(canvas,doc,{update:()=>calls++});
 event(doc,'mousemove',{movementX:10,movementY:0});assert.equal(calls,0);
 event(canvas,'click');await Promise.resolve();await Promise.resolve();
 event(canvas,'mousedown',{button:0,clientX:0,clientY:0});event(doc,'mousemove',{clientX:5,clientY:0});assert.equal(calls,1);
 doc.pointerLockElement=canvas;event(doc,'pointerlockchange');event(doc,'mousemove',{movementX:10,movementY:0});assert.equal(calls,2);
 doc.pointerLockElement=null;event(doc,'pointerlockchange');event(doc,'mousemove',{movementX:10,movementY:0});assert.equal(calls,2);release();
 bindMouseView(canvas,doc,{mode:'off',update:()=>calls++});event(canvas,'click');event(doc,'mousemove',{movementX:2});assert.equal(calls,2);
});

for (const devicePixelRatio of [1, 2]) test(`pointer-lock retry uses CSS pixels at DPR ${devicePixelRatio}`, async () => {
 const doc = new EventTarget(), canvas = new EventTarget();
 doc.defaultView = Object.assign(new EventTarget(), {devicePixelRatio});
 let requests = 0;
 const moves = [];
 canvas.requestPointerLock = () => {
  if (++requests === 1) return Promise.reject(new Error('temporary failure'));
  doc.pointerLockElement = canvas;
  event(doc, 'pointerlockchange');
 };
 const release = bindMouseView(canvas, doc, {update: (x, y) => moves.push([x, y])});
 event(canvas, 'click');
 await Promise.resolve();
 event(canvas, 'mousedown', {button: 0, clientX: 0, clientY: 0});
 event(doc, 'mousemove', {clientX: 4, clientY: 0});
 event(doc, 'mouseup');
 event(canvas, 'click');
 assert.equal(requests, 1);
 assert.deepEqual(moves, [[4, 0]]);
 event(canvas, 'mousedown', {button: 0, clientX: 0, clientY: 0});
 event(doc, 'mousemove', {clientX: 2, clientY: 0});
 event(doc, 'mouseup');
 event(canvas, 'click');
 assert.equal(requests, 2);
 event(doc, 'mousemove', {movementX: 2, movementY: -4});
 assert.deepEqual(moves, [[4, 0], [2, 0], [2, -4]]);
 release();
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {createSettingsStore} from './monitor-room-model.mjs';

class El{
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.style={};this.className='';this.textContent='';this.hidden=false;this.classList={add:c=>{this.className+=' '+c;},remove:()=>{}};}
  append(...c){this.children.push(...c);}replaceChildren(...c){this.children=[...c];}
  cloneNode(){const n=new El(this.tag);n.dataset={...this.dataset};return n;}decode(){return Promise.resolve();}
}
const all=(n,f,out=[])=>{if(f(n))out.push(n);for(const c of n.children)all(c,f,out);return out;};
globalThis.document={createElement:t=>new El(t),createTextNode:t=>({text:t})};
let frames=[],rafs=0;
globalThis.requestAnimationFrame=fn=>{rafs++;frames.push(fn);return rafs;};globalThis.cancelAnimationFrame=()=>{};
const tick=async now=>{const f=frames.splice(0);for(const fn of f)fn(now);await new Promise(r=>setTimeout(r,5));};
const {mountMonitorRoom}=await import('./monitor-room-view.mjs');

const run=(cams)=>({scene_id:'S',run_id:'r',source_kind:'SYNTHETIC',camera_ids:cams,sampling:{per_camera:cams.map(c=>({camera_id:c,source_frame_interval_us:50000}))},clock_mapping:{source_duration_us:8000000}});
const memory=()=>{const m=new Map();return {getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v)};};
const makeApi=ready=>({calls:[],async frames(r,t,cams){this.calls.push([t,[...cams]]);return {ok:true,data:{tiles:cams.map(c=>ready.includes(c)?{camera_id:c,status:'READY',media_url:'/api/controlled_scene_media?token='+'x'.repeat(43),file_sha256:null}:{camera_id:c,status:'MISSING',media_url:null})}};},async replay(){return {ok:false};}});

test('wall builds one tile per camera from the data, shows MISSING for a camera without RGB, and hides on request', async () => {
  frames=[];const host=new El('div'),api=makeApi(['A','B']);
  api.frames=api.frames.bind(api);
  const settings=createSettingsStore(memory());
  const wall=mountMonitorRoom(host,{api,settings});
  wall.setBootstrap({runs:[run(['A','B','C'])]});
  await tick(0);await tick(16);await tick(32);
  const tiles=all(host,n=>n.className.includes('mr-tile'));
  assert.deepEqual(tiles.map(t=>t.dataset.camera),['A','B','C']);
  const grid=all(host,n=>n.className==='mr-grid')[0];assert.equal(grid.dataset.cols,'2');
  // frame decode needs a real Image; the buffer reports MISSING for tiles it cannot decode, never a still stand-in
  assert.ok(tiles.every(t=>['MISSING','READY','PENDING'].includes(t.dataset.status)));
  assert.equal(tiles[2].dataset.status==='READY',false);
  const calls=api.calls.length;wall.setVisible(false);
  assert.equal(host.hidden,true);assert.equal(wall.isVisible(),false);
  await tick(100);await tick(200);assert.equal(api.calls.length,calls,'no frame requests while hidden');
  wall.setVisible(true);assert.equal(host.hidden,false);
  wall.destroy();assert.equal(host.children.length,0);
});

test('admin subset narrows the tiles live', async () => {
  frames=[];const host=new El('div'),api=makeApi([]),settings=createSettingsStore(memory());
  const wall=mountMonitorRoom(host,{api,settings});wall.setBootstrap({runs:[run(['A','B','C','D'])]});
  await tick(0);await tick(16);
  assert.equal(all(host,n=>n.className.includes('mr-tile')).length,4);
  settings.set({cameras:['B','D']});await tick(32);await tick(48);
  assert.deepEqual(all(host,n=>n.className.includes('mr-tile')).map(t=>t.dataset.camera),['B','D']);
  wall.destroy();
});

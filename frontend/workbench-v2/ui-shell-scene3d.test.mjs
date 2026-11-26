// Default front desk DOM integration in Node; no browser, HTTP service or assets.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mountUi} from './ui-shell.mjs';
import {createStore, initialState} from './store.mjs';
import {buildCoreTrackingViewModel} from './core-search-track-model.mjs';

function documentFixture() {
  let doc;
  class Element {
    constructor(tag) { this.tagName = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.events = {}; this.ownerDocument = doc; this.text = ''; this.style = {setProperty(k,v) {this[k]=v;}, removeProperty(k) {delete this[k];}}; }
    get classList() { const node=this; return {add(...v) {node.className=[...new Set([...(node.className??'').split(' '),...v])].join(' ');}, remove(v) {node.className=(node.className??'').split(' ').filter(x=>x!==v).join(' ');}, toggle(v,on) {const yes=on??!(node.className??'').split(' ').includes(v);this.remove(v);if(yes)this.add(v);return yes;}}; }
    append(...nodes) { for (let n of nodes) { if (typeof n === 'string') {const t=new Element('#text');t.text=n;n=t;} if(n.tagName==='#fragment'){this.append(...n.children);continue;} n.remove();n.parentNode=this;this.children.push(n); } }
    prepend(...nodes) { const rest=[...this.children];this.replaceChildren(...nodes,...rest); }
    replaceChildren(...nodes) {for(const n of this.children)n.parentNode=null;this.children=[];this.text='';this.append(...nodes);}
    insertBefore(n,ref) { n.remove();const at=this.children.indexOf(ref);n.parentNode=this;this.children.splice(at<0?this.children.length:at,0,n); }
    remove() {if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(x=>x!==this);this.parentNode=null;}
    set textContent(t) {this.replaceChildren();this.text=String(t);}
    get textContent() {return this.text+this.children.map(n=>n.textContent).join(' ');}
    get firstElementChild() {return this.children[0]??null;} get lastChild() {return this.children.at(-1)??null;}
    setAttribute(k,v) {this.attributes[k]=String(v);if(k==='id')this.id=String(v);if(k==='class')this.className=String(v);if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(v);}
    getAttribute(k) {return k==='id'?this.id??null:this.attributes[k]??null;} removeAttribute(k) {delete this.attributes[k];}
    addEventListener(k,fn) {(this.events[k]??=[]).push(fn);} removeEventListener(k,fn) {this.events[k]=(this.events[k]??[]).filter(x=>x!==fn);}
    dispatchEvent(e) {for(const fn of this.events[e.type]??[])fn(e);return true;} click(){this.dispatchEvent({type:'click',target:this});}
    matches(selector) {
      const absent=/:not\(([^)]+)\)/.exec(selector); if(absent&&this.matches(absent[1]))return false;selector=selector.replace(/:not\([^)]+\)/g,'');
      const attrs=[...selector.matchAll(/\[([^=\]]+)(?:=["']?([^\]"']+)["']?)?\]/g)];selector=selector.replace(/\[[^\]]+\]/g,'');
      for(const [,key,value]of attrs){const actual=key.startsWith('data-')?this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]:this.getAttribute(key);if(actual==null||(value!=null&&actual!==value))return false;}
      const id=/#([\w-]+)/.exec(selector);if(id&&this.id!==id[1])return false;
      for(const [,cls]of selector.matchAll(/\.([\w-]+)/g))if(!(this.className??'').split(' ').includes(cls))return false;
      const tag=/^[\w-]+/.exec(selector);return !tag||this.tagName===tag[0];
    }
    querySelectorAll(selector) {const out=[];for(const n of this.children){if(n.matches(selector))out.push(n);out.push(...n.querySelectorAll(selector));}return out;}
    querySelector(selector) {return this.querySelectorAll(selector)[0]??null;}
  }
  doc=new Element('#document');doc.ownerDocument=doc;doc.createElement=tag=>new Element(tag);doc.createElementNS=(_ns,tag)=>new Element(tag);doc.createDocumentFragment=()=>new Element('#fragment');doc.baseURI='http://localhost/workbench-v2/';
  doc.body=doc.createElement('body');doc.append(doc.body);const host=doc.createElement('div');host.id='ui-v1';doc.body.append(host);return {doc,host};
}

const asset={cameras:[{camera_id:'CAM_A',width:960,height:540,cy:270,fy:625,camera_to_world:[[1,0,0,0],[0,1,0,2],[0,0,1,0],[0,0,0,1]]}]};
test('mountUi at the default URL uses the new floor panel: estimate/UNKNOWN, toggle and route teardown', async t => {
  t.mock.method(globalThis,'setInterval',()=>0);t.mock.method(globalThis,'clearInterval',()=>{});
  const {doc,host}=documentFixture();
  const run={run_id:'A4',scene_id:'S',camera_ids:['CAM_A'],camera_map:{layout:'NODE_GRAPH',display_note:'示意圖，非實際座標',cameras:[{camera_id:'CAM_A',display_position:{status:'CALIBRATED_STATIC',xy_m:[0,0]}},{camera_id:'CAM_B',display_position:{status:'CALIBRATED_STATIC',xy_m:[4,4]}}]},clock_mapping:{clock_id:'C',wall_origin:'2026-11-24T00:00:00+08:00',t0_us:0,rate:1,source_duration_us:5e6}};
  const response={status:'TRACKING',as_of_us:5e6,output_sha256:'synthetic',single_view:[{kind:'ON_CAMERA',camera_id:'CAM_A',range_us:[0,5e6]}],sightings:[],display_estimate:{est_xy:[2,1],uncertainty_m:0.8,last_observed_us:1e6,source_clock_id:'C'}};
  const store=createStore(initialState({activeRun:run,bootstrap:{runs:[run]},coreTrackResponse:response,
    coreTrackingView:buildCoreTrackingViewModel(response,{tUs:1e6,cameraGraph:run.camera_map,runClockId:'C'}),cameraGraph:run.camera_map,tUs:1e6}));
  let disposals=0, mounts=0; const updates=[];
  const ui=mountUi({root:doc,store,url:doc.baseURI,coreCatalog:()=>({regions:[],classes:['person'],colors:[],aliases:{},run}),
    scene3dFactory:()=>{mounts++;return {ready:Promise.resolve(),cameraAsset:()=>asset,update(m){updates.push(m);},destroy(){disposals++;}};}});
  try {
    ui.go('case2');assert.equal(ui.screen,'case2');
    const plan=host.querySelector('#ui-floorplan');assert.ok(plan);assert.equal(plan.dataset.mode,'2d');
    assert.equal(plan.querySelectorAll('.ui-estimate-point').length,1);assert.equal(plan.querySelectorAll('.ui-estimate-range').length,1);
    assert.match(plan.textContent,/系統估計（推論）/);
    assert.equal(plan.querySelectorAll('.cam.is-active').length,1);
    assert.equal(plan.querySelector('.ui-plan-display-note').textContent,'示意圖，非實際座標');
    plan.querySelector('[data-mode="3d"]').click();await Promise.resolve();await Promise.resolve();
    assert.equal(plan.dataset.mode,'3d');assert.equal(mounts,1);
    store.dispatch({type:'SET_T_US',tUs:0.5e6});
    assert.equal(updates.at(-1).estimate.xy,null);assert.equal(updates.at(-1).estimate.uncertaintyM,null);
    assert.match(plan.querySelector('.ui-estimate-summary').textContent,/ESTIMATE_IN_FUTURE/);
    assert.match(plan.querySelector('.ui-scene3d-hud').textContent,/估計位置：UNKNOWN/);
    plan.querySelector('[data-mode="2d"]').click();
    assert.equal(plan.querySelectorAll('.ui-estimate-point').length,0);assert.equal(plan.querySelectorAll('.ui-estimate-range').length,0);
    store.dispatch({type:'SET_T_US',tUs:1e6});
    assert.equal(plan.querySelectorAll('.ui-estimate-point').length,1);
    ui.go('case1');assert.equal(disposals,1);ui.go('case2');
    assert.equal(host.querySelector('#ui-floorplan').dataset.mode,'2d');
    const unknown={...response,status:'NO_SIGHTING',single_view:[],output_sha256:'unknown',display_estimate:{est_xy:'UNKNOWN',uncertainty_m:'UNKNOWN',reason:'NO_PROJECTABLE_SELECTED_OBSERVATION'}};
    store.dispatch({type:'SET_CORE_TRACK_RESPONSE',response:unknown,displayPositions:{CAM_A:[0,0]}});
    const next=host.querySelector('#ui-floorplan');assert.equal(next.querySelectorAll('.ui-estimate-point').length,0);
    assert.equal(next.querySelectorAll('.ui-estimate-range').length,0);
    assert.match(next.textContent,/目前沒有觀測紀錄/);assert.match(next.textContent,/NO_PROJECTABLE_SELECTED_OBSERVATION/);
    next.querySelector('[data-mode="3d"]').click();await Promise.resolve();await Promise.resolve();
  } finally {ui.destroy();}
  assert.equal(disposals,2);assert.equal(host.children.length,0);
});

test('B-05: the entire #ui-floorplan is hidden without usable camera positions, even with a valid estimate', t => {
  t.mock.method(globalThis,'setInterval',()=>0);t.mock.method(globalThis,'clearInterval',()=>{});
  const {doc,host}=documentFixture();
  const run={run_id:'B-05',scene_id:'S',camera_ids:['A'],clock_mapping:{clock_id:'C',source_duration_us:5e6},
    camera_map:{layout:'NODE_GRAPH',cameras:[{camera_id:'A',display_position:{status:'UNKNOWN',xy_m:[0,0]}}]}};
  const response={status:'TRACKING',as_of_us:5e6,output_sha256:'b05',single_view:[],sightings:[],
    display_estimate:{est_xy:[2,1],uncertainty_m:1,last_observed_us:1e6,source_clock_id:'C'}};
  const store=createStore(initialState({activeRun:run,bootstrap:{runs:[run]},cameraGraph:run.camera_map,tUs:1e6}));
  store.dispatch({type:'SET_CORE_TRACK_RESPONSE',response});
  let mounts=0;
  const ui=mountUi({root:doc,store,url:doc.baseURI,coreCatalog:()=>({regions:[],classes:['person'],colors:[],aliases:{},run}),
    scene3dFactory:()=>{mounts++;throw new Error('hidden floor plan must not mount 3D');}});
  try {
    ui.go('case2');
    const plan=host.querySelector('#ui-floorplan');assert.ok(plan);assert.equal(plan.hidden,true);
    assert.equal(plan.querySelectorAll('.ui-estimate-point').length,0);assert.equal(mounts,0);
    store.dispatch({type:'SET_T_US',tUs:2e6});assert.equal(plan.hidden,true);
    assert.equal(mounts,0);
  } finally {ui.destroy();}
});

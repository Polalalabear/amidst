import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {buildScene,observedPath,layoutNodes,readCameraMap,hms,windowText,EXTERNAL_LABEL,EXTERNAL_UNAVAILABLE,SYNTHETIC_NOTE,NODE_GRAPH_NOTE,PHYSICAL_LEGEND,RANK_UNKNOWN_NOTE,IDENTITY_LINE} from './track-map-model.mjs';
import {renderPanelHtml,renderSvg} from './track-map-render.mjs';
import {createTrackMapData,syntheticPhysical,syntheticExternal,ROUTES} from './track-map-data.mjs';
import {mount} from './track-map-view.mjs';

const fixture=JSON.parse(await readFile(new URL('fixtures/track-map/synthetic.json',import.meta.url),'utf8'));
const q2=JSON.parse(JSON.parse(await readFile(new URL('fixtures/q2-rule.json',import.meta.url),'utf8')).cases[0].response_json);
const timeline=q2.timeline; // A [0,0.4s], GAP, B [1s,2s]
const physicalDoc=(over={})=>({schema_version:'q-demo.physical-prediction.v1',as_of_us:400000,last_camera_id:'A',last_observed_us:400000,status:'PREDICTED',graph_approval_status:'DRAFT',direction:{status:'KNOWN'},
  candidates:[{camera_id:'B',rank:1,confidence:'MEDIUM',relation:'BLIND_GAP',window_us:[1400000,5400000],path_has_unknown_state:true},{camera_id:'E',rank:2,confidence:'UNKNOWN',relation:'UNKNOWN',window_us:[1400000,8400000],path_has_unknown_state:true}],
  used_for:'DISPLAY_ONLY',identity_verdict:'UNCONFIRMED',physical_navigation:'UNKNOWN',gt_read:false,...over});
const extDoc=(over={})=>({schema_version:'q-demo.external-prediction.v1',status:'AVAILABLE',reason:null,as_of_us:400000,candidates:[{camera_id:'E',likelihood:'LOW',reason:'x'}],used_for:'DISPLAY_ONLY',scoring_use:false,identity_verdict:'UNCONFIRMED',gt_read:false,...over});
const scene=(t,extra={})=>buildScene({cameraMap:fixture.camera_map,timeline,tUs:t,origin:'SYNTHETIC',...extra});

test('observed solid lines use only segments that began at or before t, and shrink when t goes back',()=>{
  assert.deepEqual(scene(200000).observed,[]);
  assert.deepEqual(scene(999999).observed,[]);               // GAP: nothing observed on B yet
  assert.deepEqual(scene(1000000).observed.map(e=>e.from+e.to),['AB']);
  assert.deepEqual(scene(2000000).observed.map(e=>e.from+e.to),['AB']);
  assert.deepEqual(scene(200000).observed,[]);               // back again: line removed
  assert.equal(scene(1000000).current,'B');assert.equal(scene(200000).current,'A');
  assert.equal(scene(700000).inGap,true);
});
test('without a map the node set comes from the run list, never from segments after t',()=>{
  const s=buildScene({cameraMap:null,timeline,tUs:200000,origin:'SYNTHETIC'});
  assert.deepEqual(s.nodes.map(n=>n.camera_id),['A']);
  const withRun=buildScene({cameraMap:null,timeline,tUs:200000,origin:'SYNTHETIC',runCameraIds:['A','B','E']});
  assert.deepEqual(withRun.nodes.map(n=>n.camera_id),['A','B','E']);
});
test('physical prediction from a later as_of is hidden; one for an unobserved camera is hidden',()=>{
  assert.equal(scene(400000,{physical:physicalDoc()}).predicted.length,1);  // only the most likely (rank 1) path is drawn
  assert.equal(scene(200000,{physical:physicalDoc()}).predicted.length,0);          // scrubbed back before as_of
  assert.equal(scene(400000,{physical:physicalDoc({last_camera_id:'B'})}).predicted.length,0); // B not observed yet at t
  assert.equal(scene(400000,{physical:physicalDoc({gt_read:true})}).predicted.length,0);
  assert.equal(scene(400000,{physical:physicalDoc({used_for:'SCORING'})}).predicted.length,0);
});
test('confidence layers: the single drawn path keeps its confidence style and warnings; UNKNOWN confidence has its own muted style',()=>{
  const p=scene(400000,{physical:physicalDoc()}).predicted;assert.equal(p.length,1);
  assert.equal(p[0].label,'#1 00:00:01–00:00:05 · 中');assert.equal(p[0].style.tone,'int');
  assert.match(p[0].title,/圖未核准（DRAFT）/);assert.match(p[0].title,/通行狀態未知/);
  const unk=physicalDoc();unk.candidates=[{...unk.candidates[1],rank:1}];
  const u=scene(400000,{physical:unk}).predicted;assert.equal(u[0].confidence,'UNKNOWN');assert.notEqual(u[0].style.dash,p[0].style.dash);assert.equal(u[0].style.tone,'unk');assert.match(u[0].title,/信心未知/);
  const svg=renderSvg(scene(400000,{physical:unk}));
  assert.match(svg,/tm-conf-UNKNOWN/);assert.match(svg,/stroke-dasharray="1.5 4"/);assert.equal((svg.match(/tm-pred /g)||[]).length,1);
  assert.ok(!svg.includes('NaN'));
});
test('NODE_GRAPH fallback: no metre text, fixed note, deterministic layout independent of time',()=>{
  const a=scene(200000),b=scene(2000000);
  assert.equal(a.layout,'NODE_GRAPH');assert.equal(a.layoutNote,NODE_GRAPH_NOTE);
  assert.deepEqual(a.nodes.map(n=>n.xy),b.nodes.map(n=>n.xy));
  assert.doesNotMatch(renderPanelHtml(a),/\d\s*m\b|xy_m|公尺/);
  const partial=structuredClone(fixture.camera_map);partial.layout='METRIC_STATIC';partial.cameras[0].display_position={status:'CALIBRATED_STATIC',xy_m:[1,2]};
  assert.equal(buildScene({cameraMap:partial,timeline,tUs:0}).layout,'NODE_GRAPH'); // not all cameras placed → fall back
});
test('METRIC_STATIC uses calibrated positions only when every camera has one',()=>{
  const m=structuredClone(fixture.camera_map);m.layout='METRIC_STATIC';m.cameras=m.cameras.filter(c=>c.role==='TRACKING');
  m.cameras.forEach((c,i)=>{c.display_position={status:'CALIBRATED_STATIC',xy_m:[i*3,i%2*4]};});
  const s=buildScene({cameraMap:m,timeline,tUs:2000000,origin:'API'});
  assert.equal(s.layout,'METRIC_STATIC');assert.match(s.layoutNote,/靜態校正位置/);
  const [A,B]=[s.nodes[0].xy,s.nodes[1].xy];assert.ok(A[0]<B[0]);
  assert.ok(s.nodes.every(n=>n.xy.every(Number.isFinite)));
});
test('non-tracking cameras are grey points without connections; DRAFT / unknown edges are labelled',()=>{
  const s=scene(2000000);const d=s.nodes.find(n=>n.camera_id==='D');
  assert.equal(d.role,'QUERY_ONLY');assert.ok(s.graphEdges.every(e=>e.from!=='D'&&e.to!=='D'));
  assert.match(s.graphEdges[0].title,/圖未核准（DRAFT）.*通行狀態未知/);
  assert.match(renderSvg(s),/僅查詢/);
});
test('SYNTHETIC marker shown unless every part came from the API; identity and legend lines are fixed',()=>{
  const html=renderPanelHtml(scene(0));
  assert.match(html,new RegExp(SYNTHETIC_NOTE));assert.ok(html.includes(IDENTITY_LINE));assert.ok(html.includes(PHYSICAL_LEGEND));
  assert.doesNotMatch(renderPanelHtml(scene(0,{origin:'API'})),new RegExp(SYNTHETIC_NOTE));
});
test('external guess: off by default, drawn only when enabled+AVAILABLE, always labelled, never when UNAVAILABLE',()=>{
  const base={physical:physicalDoc(),external:extDoc()};
  assert.equal(scene(400000,base).externalLines.length,0);                       // default off
  assert.equal(scene(400000,base).externalEnabled,false);
  assert.doesNotMatch(renderPanelHtml(scene(400000,base)),new RegExp(EXTERNAL_LABEL));
  const on=scene(400000,{...base,externalEnabled:true});
  assert.equal(on.externalLines.length,1);assert.ok(on.externalLines[0].label.startsWith(EXTERNAL_LABEL));
  const html=renderPanelHtml(on);assert.match(html,/tm-ext/);assert.ok(html.includes(EXTERNAL_LABEL));
  const down=scene(400000,{physical:physicalDoc(),external:extDoc({status:'UNAVAILABLE',reason:'TIMEOUT',candidates:[]}),externalEnabled:true});
  assert.equal(down.externalLines.length,0);assert.match(renderPanelHtml(down),new RegExp(EXTERNAL_UNAVAILABLE));
  assert.doesNotMatch(renderPanelHtml(down),/class="tm-ext"/);
  assert.equal(scene(400000,{physical:physicalDoc(),external:extDoc({scoring_use:true}),externalEnabled:true}).externalLines.length,0);
  assert.equal(scene(200000,{physical:physicalDoc({as_of_us:100000,last_observed_us:100000}),external:extDoc({as_of_us:400000}),externalEnabled:true}).externalLines.length,0);
});
test('decoy fields (gt_*, actor_id, renderer_trajectory, visibility, depth, script) never reach the drawing',()=>{
  const decoy={gt_position:[1,2],actor_id:'ACTOR_9',renderer_trajectory:[[0,0]],visibility:'FULL',depth:3,event_script:'t_X'};
  const map=structuredClone(fixture.camera_map);Object.assign(map,decoy);map.cameras.forEach(c=>Object.assign(c,decoy));map.transitions.forEach(t=>Object.assign(t,decoy));
  const phys=physicalDoc(decoy);phys.candidates.forEach(c=>Object.assign(c,decoy));
  const tl=structuredClone(timeline).map(s=>({...s,...decoy}));
  const clean=buildScene({cameraMap:fixture.camera_map,timeline,tUs:400000,physical:physicalDoc(),origin:'SYNTHETIC'});
  const noisy=buildScene({cameraMap:map,timeline:tl,tUs:400000,physical:phys,origin:'SYNTHETIC'});
  assert.deepEqual(noisy,clean);
  const html=renderPanelHtml(noisy);assert.doesNotMatch(html,/ACTOR_9|gt_position|renderer_trajectory|t_X|FULL/);
  assert.equal(readCameraMap({...fixture.camera_map,gt_read:true}),null);
});
test('modules do not read scripts, trajectories, GT, depth or event-specific top-down images',async()=>{
  for(const f of ['track-map-model.mjs','track-map-render.mjs','track-map-data.mjs','track-map-view.mjs']) {
    const text=await readFile(new URL(f,import.meta.url),'utf8');
    assert.doesNotMatch(text.replace(/\/\/.*$/gm,'').replace(/'gt_read'|gt_read/g,''),/topdown\.svg|persons\.sim|configs\/|ground_truth|renderer_trajectory|\bdepth\b|\.svg['"]/,f);
  }
});
test('formatting helpers',()=>{assert.equal(hms(3661e6),'01:01:01');assert.equal(hms(-1),'UNKNOWN');assert.equal(windowText(null),'時間窗 UNKNOWN');});

// ---- data adapter -------------------------------------------------------------------------------------------------
test('synthetic stand-ins use the timeline only up to as_of_us',()=>{
  assert.equal(syntheticPhysical(fixture,timeline,200000).last_camera_id,'A');
  assert.equal(syntheticPhysical(fixture,timeline,200000).last_observed_us,200000);
  assert.equal(syntheticPhysical(fixture,timeline,1500000).last_camera_id,'B');
  assert.equal(syntheticExternal(fixture,timeline,200000).candidates[0].camera_id,'E');
  assert.equal(syntheticExternal(fixture,[],0).status,'UNAVAILABLE');
  assert.equal(syntheticPhysical(fixture,[],0),null);
});
test('missing backend routes fall back to SYNTHETIC once; later calls do not hit the route again',async()=>{
  const calls=[];const fetchImpl=async(url)=>{calls.push(url);return {ok:false,status:404,text:async()=>'{}'};};
  const d=createTrackMapData({fetchImpl,getSession:()=>'S',fixture});
  const m=await d.cameraMap({scene_id:'s',run_id:'r'});assert.equal(m.origin,'SYNTHETIC');
  await d.physical({responseRef:'r1',asOfUs:400000,timeline});await d.physical({responseRef:'r1',asOfUs:500000,timeline});
  assert.deepEqual(calls,[ROUTES.map,ROUTES.physical]);
});
test('backend answers are used when they exist; only same-origin /api/ routes; external is one call per response and second',async()=>{
  const calls=[];const fetchImpl=async(url,opts)=>{calls.push([url,JSON.parse(opts.body)]);
    const doc=url===ROUTES.physical?physicalDoc():url===ROUTES.external?extDoc():{...fixture.camera_map};return {ok:true,status:200,text:async()=>JSON.stringify(doc)};};
  const d=createTrackMapData({fetchImpl,getSession:()=>'S',fixture});
  assert.equal((await d.physical({responseRef:'r1',asOfUs:400000,timeline})).origin,'API');
  await d.external({responseRef:'r1',asOfUs:1100000,timeline});await d.external({responseRef:'r1',asOfUs:1900000,timeline});await d.external({responseRef:'r1',asOfUs:2100000,timeline});
  assert.equal(calls.filter(c=>c[0]===ROUTES.external).length,2);
  assert.ok(calls.every(([url])=>url.startsWith('/api/')));
  assert.deepEqual(Object.keys(calls[0][1]).sort(),['as_of_us','response_ref','session_ref']);
});
test('offline (fixture) mode never calls fetch',async()=>{
  const d=createTrackMapData({fetchImpl:()=>{throw new Error('NO_FETCH');},fixture,offline:true});
  assert.equal((await d.cameraMap({scene_id:'s',run_id:'r'})).origin,'SYNTHETIC');assert.equal((await d.physical({responseRef:'r',asOfUs:0,timeline})).origin,'SYNTHETIC');
});

// ---- view ---------------------------------------------------------------------------------------------------------
class El{constructor(t){this.tag=t;this.children=[];this.attributes={};this.listeners={};this.hidden=false;this.innerHTML='';this.textContent='';this.checked=false;this.style={};this.parentElement=null;this.classList={add(){},remove(){},toggle(){}};this.offsetWidth=0;this.offsetHeight=0;}
  append(...c){this.children.push(...c);}replaceChildren(...c){this.children=[...c];}setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,f){this.listeners[k]=f;}remove(){}before(){}}
function setup({origin='SYNTHETIC_FIXTURE',fetchImpl}={}) {
  globalThis.document={createElement:t=>new El(t)};
  let state={q2:{...q2,session_id:'sess-1'},tUs:200000,bootstrap:{data_origin:origin},activeRun:{camera_ids:['A','B','E']}};const subs=[];
  const store={getState:()=>state,subscribe:f=>{subs.push(f);return()=>{};}};
  const slot=new El('div'),root={querySelector:q=>q==='#track-map-slot'?slot:null};
  const timers=[];const view=mount({store,api:{getSession:()=> 'S'},root,fetchImpl,fixture,setTimer:(f)=>{timers.push(f);return timers.length;},clearTimer:()=>{}});
  return {slot,view,timers,set:async u=>{state={...state,...u};subs.forEach(f=>f());await Promise.resolve();await Promise.resolve();},body:()=>slot.children[1].innerHTML,toggle:()=>slot.children[2].children[0],run:async()=>{const t=timers.splice(0);for(const f of t)await f();}};
}
const settle=()=>new Promise(r=>setImmediate(r));
test('view: shows SYNTHETIC, external switch is off by default, lines follow t both ways',async()=>{
  const s=setup();await settle();
  assert.equal(s.toggle().checked,false);assert.match(s.body(),new RegExp(SYNTHETIC_NOTE));assert.doesNotMatch(s.body(),new RegExp(EXTERNAL_LABEL));
  await s.set({tUs:400000});await s.run();await settle();
  assert.match(s.body(),/tm-pred /);assert.doesNotMatch(s.body(),/class="tm-observed"/);
  await s.set({tUs:1500000});await s.run();await settle();assert.match(s.body(),/class="tm-observed"/);
  await s.set({tUs:200000});assert.doesNotMatch(s.body(),/class="tm-observed"/);assert.doesNotMatch(s.body(),/tm-pred /); // scrubbed back: later lines gone at once
});
test('view: turning the external switch on shows the labelled replay line ; a new response turns it off again',async()=>{
  const s=setup();await settle();await s.set({tUs:400000});await s.run();await settle();
  s.toggle().checked=true;s.toggle().checked=true;s.slot.children[2].children[0].listeners.change();await settle();await s.run();await settle();
  assert.match(s.body(),/class="tm-ext"/);assert.ok(s.body().includes(EXTERNAL_LABEL));
  await s.set({q2:{...q2,session_id:'sess-2'}});await settle();assert.equal(s.toggle().checked,false);assert.doesNotMatch(s.body(),/class="tm-ext"/);
});
test('D109-3: external route denied/missing (403/404) → 外部推測不可用, no line, never the SYNTHETIC replay',async()=>{
  for(const status of [403,404]) {
    const d=createTrackMapData({fetchImpl:async()=>({ok:false,status,text:async()=>'{}'}),getSession:()=>'S',fixture});
    const r=await d.external({responseRef:'r1',asOfUs:400000,timeline});
    assert.equal(r.doc.status,'UNAVAILABLE');assert.equal(r.doc.candidates.length,0);
  }
  const s=setup({origin:'API',fetchImpl:async(url)=>({ok:false,status:url===ROUTES.external?403:404,text:async()=>'{}'})});await settle();await s.set({tUs:400000});await s.run();await settle();
  s.toggle().checked=true;s.toggle().listeners.change();await settle();await s.run();await settle();
  assert.doesNotMatch(s.body(),/class="tm-ext"/);assert.doesNotMatch(s.body(),/SYNTHETIC 錄製重播/);assert.ok(s.body().includes(EXTERNAL_UNAVAILABLE));
});
test('view: without a q2 result the panel stays empty and hidden controls',async()=>{
  const s=setup();await s.set({q2:null});assert.equal(s.body(),'');assert.equal(s.slot.children[2].hidden,true);
});

test('only the lowest-rank candidate is drawn, whatever the data order; no rank -> UNKNOWN and nothing drawn',()=>{
  const reorder=physicalDoc();reorder.candidates=[...reorder.candidates].reverse();
  const p=scene(400000,{physical:reorder}).predicted;assert.equal(p.length,1);assert.equal(p[0].rank,1);assert.equal(p[0].to,'B');
  const noRank=physicalDoc();noRank.candidates=noRank.candidates.map(({rank,...c})=>c);
  const sc=scene(400000,{physical:noRank});assert.equal(sc.predicted.length,0);assert.ok(sc.notes.includes(RANK_UNKNOWN_NOTE));
  assert.match(PHYSICAL_LEGEND,/最可能/);
});

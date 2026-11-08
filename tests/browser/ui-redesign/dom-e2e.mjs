// Browser DOM/lifecycle tests for mountUi and mountTabs; no new DOM shim dependency.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {ownedRuntime} from '../core-preview/owned-runtime.mjs';
const owned=ownedRuntime(),out=process.env.UI_DOM_OUTPUT??owned.evidenceRoot+'/ui-dom',base=process.env.CORE_BASE_URL??'http://127.0.0.1:8785';
const {chromium}=await import(pathToFileURL(owned.playwrightModule).href);await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
let checks=0;const check=(ok,msg)=>{assert.ok(ok,msg);checks++;};
try{
 const p=await browser.newPage();await p.goto(base+'/workbench-v2/?run=B-05');await p.locator('#ui-enter').waitFor();
 const dom=await p.evaluate(async()=>{
  const {mountUi}=await import('/workbench-v2/ui-shell.mjs'),{createStore}=await import('/workbench-v2/store.mjs'),{mountTabs}=await import('/workbench-v2/admin-ui.mjs');
  const iframe=document.createElement('iframe');document.body.append(iframe);const doc=iframe.contentDocument;doc.body.innerHTML='<div id="ui-v1"></div>';
  const timers=new Set(),listeners=new Set(),docListeners=new Set();let subs=0,submitted=0;
  const original={setInterval:globalThis.setInterval,clearInterval:globalThis.clearInterval,add:globalThis.addEventListener,remove:globalThis.removeEventListener,docAdd:doc.addEventListener,docRemove:doc.removeEventListener};
  globalThis.setInterval=(...args)=>{const id=original.setInterval.call(globalThis,...args);timers.add(id);return id;};globalThis.clearInterval=id=>{timers.delete(id);return original.clearInterval.call(globalThis,id);};
  globalThis.addEventListener=(type,fn,...rest)=>{listeners.add(fn);return original.add.call(globalThis,type,fn,...rest);};globalThis.removeEventListener=(type,fn,...rest)=>{listeners.delete(fn);return original.remove.call(globalThis,type,fn,...rest);};
  doc.addEventListener=(type,fn,...rest)=>{docListeners.add(fn);return original.docAdd.call(doc,type,fn,...rest);};doc.removeEventListener=(type,fn,...rest)=>{docListeners.delete(fn);return original.docRemove.call(doc,type,fn,...rest);};
  let ui,tabs;
  try{
   const store=createStore(),subscribe=store.subscribe;store.subscribe=fn=>{subs++;const un=subscribe(fn);return()=>{subs--;un();};};
   ui=mountUi({root:doc,store,url:location.origin+'/workbench-v2/',storage:null,synthetic:true,submitCore:()=>{submitted++;},coreCatalog:()=>({regions:[],classes:['person'],colors:[],aliases:{}})});
   const cover=ui.screen==='cover';doc.querySelector('#ui-enter').click();const chooser=ui.screen==='choose'&&doc.querySelectorAll('[data-case]').length===3;
   doc.querySelector('[data-case=case1]').click();doc.querySelector('#ui-search-submit').click();const validation=doc.querySelector('#ui-search-feedback').textContent.includes('請輸入開始與結束時間')&&submitted===0;
   ui.go('case2');const trackWindowFields=!!doc.querySelector('#ui-track-end')&&doc.querySelector('#ui-track-start')&&!doc.body.textContent.includes('空白＝現在')&&/^到錄影結尾/.test(doc.querySelector('#ui-track-end').placeholder);const manual=doc.querySelector('#ui-manual-target').disabled&&doc.querySelector('#ui-manual-note').textContent==='追蹤起點由系統自動選擇，目前還不能手動改選目標';
   const stop=doc.querySelector('#ui-stop-track').disabled;
   // D139-6: blind route end label. A→GAP→B response with a blind curve, played to before / inside / after the gap.
   store.dispatch({type:'SET_Q_RUN',run:{scene_id:'S',run_id:'R',title:'A4-1 教室走廊事件',camera_ids:['CAM_W1','CAM_W2'],camera_map:{CAM_W1:[10,3],CAM_W2:[20,3]},source_kind:'SYNTHETIC',clock_mapping:{wall_origin:'2026-11-01T13:00:00+08:00',t0_us:0,rate:1,source_duration_us:42000000,timezone:'Asia/Taipei'}}});
   const sv=[{kind:'ON_CAMERA',camera_id:'CAM_W1',range_us:[3000000,9000000],evidence_state:'OBSERVED'},{kind:'GAP',camera_id:null,range_us:[9000000,15000000],evidence_state:'UNKNOWN'},{kind:'ON_CAMERA',camera_id:'CAM_W2',range_us:[15000000,30000000],evidence_state:'OBSERVED'}];
   store.dispatch({type:'SET_CORE_TRACK_RESPONSE',response:{schema_version:'q-core.track-response.v1',status:'TRACKING',reasons:[],as_of_us:42000000,resolved_time:{kind:'WALL',source_range_us:[0,42000000]},sightings:sv.filter(x=>x.kind==='ON_CAMERA').map(x=>({camera_id:x.camera_id,range_us:x.range_us,evidence_state:'OBSERVED',observation_ids:['o']})),multi_view:[{camera_id:'CAM_W1',first_us:3000000,last_us:9000000},{camera_id:'CAM_W2',first_us:15000000,last_us:30000000}],single_view:sv,blind:{status:'ESTIMATED',reason:null,estimate:{schema_version:'q-core.blind-estimate.v1',evidence_state:'INFERRED',confidence:'LOW',used_for:'DISPLAY_ONLY',display_label:'x',as_of_us:10000000,last_camera_id:'CAM_W1',last_observed_us:9000000,curve:{basis:'DISPLAY_POSITIONS_STRAIGHT_LINE',points:[[12.5,3.0],[18.0,3.0]]},candidates:[{camera_id:'CAM_W2',rank:1,window_us:[10000000,14000000],confidence:'LOW'}],identity_verdict:'UNCONFIRMED',physical_navigation:'UNKNOWN'}},identity_verdict:'UNCONFIRMED',physical_navigation:'UNKNOWN',output_sha256:'d139blind'},cameraGraph:{CAM_W1:[10,3],CAM_W2:[20,3]}});
   const endNote=()=>doc.querySelector('#ui-blind-end'),chipText=()=>doc.querySelector('#ui-plan-chip')?.textContent??'';
   store.dispatch({type:'SET_T_US',tUs:12000000});const blindNoEnd=!endNote()&&chipText().startsWith('推測路線');
   store.dispatch({type:'SET_T_US',tUs:20000000});const blindEnd=endNote()?.textContent==='已由 W2 鏡頭於 13:00:15 觀測到'&&chipText()==='兩端已觀測，中段為推測'&&doc.querySelector('.reacq-end')!==null;
   const rangeText=doc.querySelector('#ui-track-range')?.textContent==='查詢時段 13:00:00～13:00:42';
   const visible=(()=>{const c=doc.querySelector('#ui-case2').cloneNode(true);c.querySelectorAll('.ui-info-pop').forEach(n=>n.remove());return c.textContent;})();const noTech=!/自動種子|DEMO_DEFAULT|GRAPH_NOT_APPROVED|ASSOCIATION_IDENTITY_UNCONFIRMED|ACTUAL_BLENDER|D124|INFERRED|OBSERVED|UNKNOWN|MISSING/.test(visible)&&doc.querySelectorAll('#ui-case2 .ui-info').length>=1;const mountedTimers=timers.size;ui.destroy();ui=null;
   const destroyed=doc.querySelector('#ui-v1').children.length===0&&subs===0&&timers.size===0&&listeners.size===0&&docListeners.size===0;
   doc.body.innerHTML='<h1 id="admin-title"></h1><span id="admin-clock"></span><section data-pane="overview"></section><section data-pane="settings"></section><a data-tab="overview"></a><a data-tab="settings"></a>';
   tabs=mountTabs(doc);const adminTimer=timers.size===1,adminClock=doc.querySelector('#admin-clock').textContent.length>0;tabs.destroy();tabs=null;
   return {noTech,cover,chooser,validation,trackWindowFields,blindNoEnd,blindEnd,rangeText,manual,stop,mountedTimers,destroyed,adminTimer,adminClock,adminDestroyed:timers.size===0&&listeners.size===0};
  }finally{
   ui?.destroy();tabs?.destroy();for(const id of timers)original.clearInterval.call(globalThis,id);
   globalThis.setInterval=original.setInterval;globalThis.clearInterval=original.clearInterval;globalThis.addEventListener=original.add;globalThis.removeEventListener=original.remove;doc.addEventListener=original.docAdd;doc.removeEventListener=original.docRemove;iframe.remove();
  }
 });
 for(const [key,value]of Object.entries(dom))check(key==='mountedTimers'?value>0:value,'DOM lifecycle '+key);
 const legacy=await browser.newPage();await legacy.goto(base+'/workbench-v2/?ui=legacy&run=B-05');await legacy.locator('#q-core-class').waitFor({state:'attached'});
 const colors=()=>legacy.evaluate(()=>({body:getComputedStyle(document.body).backgroundColor,text:getComputedStyle(document.body).color,link:getComputedStyle(document.querySelector('.topbar a')).color}));
 const withUiCss=await colors();await legacy.route('**/ui.css',r=>r.fulfill({contentType:'text/css',body:''}));await legacy.reload();await legacy.locator('#q-core-class').waitFor({state:'attached'});const originalColors=await colors();check(JSON.stringify(withUiCss)===JSON.stringify(originalColors),'legacy palette unchanged by ui.css');
 const result={status:'PASS',checks,source_head:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),dom,withUiCss,originalColors};await writeFile(out+'/results.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}

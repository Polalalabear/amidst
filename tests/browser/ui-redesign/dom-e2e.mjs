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
   const stop=doc.querySelector('#ui-stop-track').disabled;const mountedTimers=timers.size;ui.destroy();ui=null;
   const destroyed=doc.querySelector('#ui-v1').children.length===0&&subs===0&&timers.size===0&&listeners.size===0&&docListeners.size===0;
   doc.body.innerHTML='<h1 id="admin-title"></h1><span id="admin-clock"></span><section data-pane="overview"></section><section data-pane="settings"></section><a data-tab="overview"></a><a data-tab="settings"></a>';
   tabs=mountTabs(doc);const adminTimer=timers.size===1,adminClock=doc.querySelector('#admin-clock').textContent.length>0;tabs.destroy();tabs=null;
   return {cover,chooser,validation,trackWindowFields,manual,stop,mountedTimers,destroyed,adminTimer,adminClock,adminDestroyed:timers.size===0&&listeners.size===0};
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

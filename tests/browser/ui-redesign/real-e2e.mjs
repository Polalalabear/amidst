// Real server acceptance: only visible UI controls, source-bound API, and decoded RGB.
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const {chromium}=await import(process.env.PLAYWRIGHT_CORE_MODULE?pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE).href:'playwright-core');
const out=process.env.UI_QA_OUTPUT;if(!out)throw Error('UI_QA_OUTPUT_REQUIRED');await mkdir(out+'/screenshots',{recursive:true});
const base=new URL('/workbench-v2/',process.env.UI_QA_BASE_URL??'http://127.0.0.1:8785').href;
const b=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const results=[],errors=[],http=[],playbacks=[];let checks=0;const check=(ok,text)=>{assert.ok(ok,text);checks++;};
const capture=async(p,name,data={})=>{const file=out+'/screenshots/'+name+'.png';await p.screenshot({path:file,fullPage:true});const raw=await readFile(file);const r={name,url:p.url(),bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex'),...data};results.push(r);console.log(JSON.stringify(r));};
const seek=async(p,t)=>{await p.locator('#ui-scrub').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input',{bubbles:true}));},t);check(Number(await p.locator('#ui-scrub').inputValue())===t,'range input preserves requested timestamp');};
const decoded=async(p,selector,n)=>{await p.waitForFunction(({selector,n})=>{const xs=[...document.querySelectorAll(selector)];return xs.length===n&&xs.every(i=>!i.hidden&&i.complete&&i.naturalWidth>0);},{selector,n});check(true,selector+' decoded RGB');};
try{
for(const [event,start,end,cameras]of[['B-05','13:00:00','13:00:08',2],['A4-1','14:00:00','14:00:50',4],['B4-1','14:10:00','14:10:42',5]]){
 const ctx=await b.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1}),p=await ctx.newPage();
 p.on('pageerror',e=>errors.push({event,error:String(e)}));p.on('response',r=>{if(r.url().includes('/api/')&&r.status()!==200)http.push({event,path:new URL(r.url()).pathname,status:r.status()});});
 await p.goto(base+'?run='+event,{waitUntil:'domcontentloaded'});await p.locator('#ui-enter').waitFor();await p.waitForTimeout(650);
 check((await p.locator('.ui-tagline').innerText()).includes('Agentic'),'cover tagline');await capture(p,event+'-cover');
 await p.locator('#ui-enter').click();await p.locator('[data-case=case1]').click();
 await p.locator('#ui-q-search [data-role=classes] [data-value=person]').click();await p.locator('#ui-search-start').fill(start);await p.locator('#ui-search-end').fill(end);
 const sr=p.waitForResponse(r=>r.url().endsWith('/api/q_core_search')&&r.request().method()==='POST');await p.locator('#ui-search-submit').click();const search=await(await sr).json();
 check(search.hits?.length>0,event+' real search');await decoded(p,'#ui-case1 .ui-shot img',search.hits.length);
 await capture(p,event+'-case1',{status:search.status,hits:search.hits.length});
 await p.goto(base+'?run='+event+'&screen=case2',{waitUntil:'domcontentloaded'});
 await p.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await p.locator('#ui-track-start').fill(start);
 const tr=p.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST');await p.locator('#ui-track-submit').click();const track=await(await tr).json();
 check(track.sightings?.length>0,event+' track sightings');check(track.single_view.some(s=>s.kind==='GAP')&&track.single_view.some(s=>s.kind==='LOST'),'missing states retained');
 const first=track.sightings[0],t=first.range_us[0]+Math.floor((first.range_us[1]-first.range_us[0])/2);await seek(p,t);await decoded(p,'#ui-case2 .ui-stage-img',1);
 check(await p.locator('#ui-play').isEnabled(),event+' source playback enabled');
 await capture(p,event+'-case2-single',{status:track.status,reasons:track.reasons,current:await p.locator('#ui-scrub').inputValue()});
 const firstCamera=track.single_view.find(s=>s.kind==='ON_CAMERA').camera_id,ni=track.single_view.findIndex(s=>s.kind==='ON_CAMERA'&&s.camera_id!==firstCamera);
 check(ni>0,'cross-camera event');const previous=track.single_view.slice(0,ni).filter(s=>s.kind==='ON_CAMERA').at(-1),next=track.single_view[ni];
 await seek(p,Math.max(previous.range_us[0],previous.range_us[1]-200000));await decoded(p,'#ui-case2 .ui-stage-img',1);
 for(const speed of ['1','1.5','2']){await p.locator('#ui-case2 [data-speed="'+speed+'"]').click();check(await p.locator('#ui-case2 [data-speed="'+speed+'"]').getAttribute('aria-pressed')==='true','source speed '+speed);}
 await p.locator('#ui-play').click();await p.waitForFunction(cam=>document.querySelector('#ui-case2 .ui-stamp')?.textContent.includes(cam),next.camera_id,{timeout:15000});
 await p.locator('#ui-play').click();await decoded(p,'#ui-case2 .ui-stage-img',1);check(true,event+' automatic camera switch');playbacks.push({event,camera:next.camera_id,tUs:Number(await p.locator('#ui-scrub').inputValue())});
 await p.locator('#ui-layout [data-layout=multi]').click();await decoded(p,'#ui-case2 .ui-multi-tile img',2);
 const multiStart=Number(await p.locator('#ui-scrub').inputValue());await p.locator('#ui-play').click();await p.waitForFunction(t=>Number(document.querySelector('#ui-scrub')?.value)>=t+200000,multiStart,{timeout:15000});await p.locator('#ui-play').click();await decoded(p,'#ui-case2 .ui-multi-tile img',2);check(true,event+' multi-view playback advances with decoded source RGB');
 await capture(p,event+'-case2-multi',{tiles:2,decoded:2});
 await p.locator('#ui-layout [data-layout=single]').click();
 const stamp=event==='A4-1'?9400000:event==='B4-1'?2100000:3000000;await seek(p,stamp);
 // Empty start means re-query at the visible source clock; no API or store injection.
 await p.locator('#ui-context').click();await p.locator('#ui-track-start').fill('');const br=p.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST');await p.locator('#ui-track-submit').click();const blind=await(await br).json();
 await writeFile(out+'/'+event+'-blind-response.json',JSON.stringify(blind,null,2));
 await seek(p,stamp);await p.waitForTimeout(300);const curves=await p.locator('#ui-floorplan .is-inferred').count();
 check(event==='B-05'?curves===0:curves>0,event+' blind evidence / UNKNOWN preserved');await capture(p,event+'-blind',{curves,status:blind.blind?.status,confidence:blind.blind?.confidence});
 await p.goto(base+'?run='+event+'&screen=case3',{waitUntil:'domcontentloaded'});await p.waitForFunction(n=>document.querySelectorAll('.mr-tile[data-status=READY]').length===n,cameras);check(true,event+' real wall camera count');
 check(await p.locator('#ui-events button:disabled').count()===0,'integrated sources selectable');await capture(p,event+'-case3',{readyCameras:cameras});
 const dest=event==='A4-1'?'B4-1':'A4-1', destButton=p.locator('#ui-events button').filter({hasText:dest}), destRun=await destButton.getAttribute('data-event');await destButton.click();await p.waitForURL(u=>u.searchParams.get('run')===destRun);await p.waitForFunction(()=>document.querySelectorAll('.mr-tile[data-status=READY]').length>0);check(true,'event selection loads source');
 await p.goto(base+'admin.html',{waitUntil:'domcontentloaded'});await p.locator('#admin-title').waitFor();await p.waitForTimeout(300);await capture(p,event+'-admin-overview');
 await p.locator('[data-tab=settings]').click();await capture(p,event+'-admin-settings');await ctx.close();
}
check(errors.length===0,'no page errors');check(http.length===0,'no failed API responses');
}finally{await writeFile(out+'/browser-results.json',JSON.stringify({source_head:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),checks,results,playbacks,errors,http},null,2));console.log(JSON.stringify({checks,screenshots:results.length,errors,http}));await b.close();}

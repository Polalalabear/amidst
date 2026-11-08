// Real server acceptance: only visible UI controls, source-bound API, and decoded RGB.
import assert from 'node:assert/strict';
import {ownedRuntime} from '../core-preview/owned-runtime.mjs';
const owned=ownedRuntime();
import {pathToFileURL} from 'node:url';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE??owned.playwrightModule).href);
const out=process.env.UI_QA_OUTPUT??owned.evidenceRoot+'/ui-real';await mkdir(out+'/screenshots',{recursive:true});
const base=new URL('/workbench-v2/',process.env.UI_QA_BASE_URL??process.env.CORE_BASE_URL??'http://127.0.0.1:8785').href;
const b=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const viewportHeight=Number(process.env.UI_QA_HEIGHT??900);
const results=[],errors=[],http=[],playbacks=[],backendStopRequests=[],blindReview=[];let checks=0;const check=(ok,text)=>{assert.ok(ok,text);checks++;};
const capture=async(p,name,data={})=>{const file=out+'/screenshots/'+name+'.png';await p.screenshot({path:file,fullPage:true});const raw=await readFile(file);const r={name,url:p.url(),bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex'),...data};results.push(r);console.log(JSON.stringify(r));};
// D139: blank times select the full recording. A later snapshot must stay hidden at an earlier playhead; endpoint persistence is recorded separately as a review finding.
const seek=async(p,t)=>{await p.locator('#ui-scrub').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input',{bubbles:true}));},t);check(Number(await p.locator('#ui-scrub').inputValue())===t,'range input preserves requested timestamp');};
const decoded=async(p,selector,n)=>{await p.waitForFunction(({selector,n})=>{const xs=[...document.querySelectorAll(selector)];return xs.length===n&&xs.every(i=>!i.hidden&&i.complete&&i.naturalWidth>0);},{selector,n});check(true,selector+' decoded RGB');};
try{
for(const [event,start,end,cameras]of[['B-05','13:00:00','13:00:08',2],['A4-1','14:00:00','14:00:50',4],['B4-1','14:10:00','14:10:42',5]]){
 const ctx=await b.newContext({viewport:{width:1440,height:viewportHeight},deviceScaleFactor:1}),p=await ctx.newPage();
 p.on('request',r=>{if(/\/api\/.*(?:stop|manual)/.test(r.url()))backendStopRequests.push(new URL(r.url()).pathname);});
 p.on('pageerror',e=>errors.push({event,error:e.stack??String(e)}));p.on('response',r=>{if(r.url().includes('/api/')&&r.status()!==200)http.push({event,path:new URL(r.url()).pathname,status:r.status()});});
 await p.goto(base+'?run='+event,{waitUntil:'domcontentloaded'});await p.locator('#ui-enter').waitFor();await p.waitForTimeout(650);
 check((await p.locator('.ui-tagline').innerText()).includes('Agentic'),'cover tagline');await capture(p,event+'-cover');
 await p.locator('#ui-enter').click();await p.locator('[data-case=case1]').click();
 await p.locator('#ui-q-search [data-role=classes] [data-value=person]').click();await p.locator('#ui-search-start').fill(start);await p.locator('#ui-search-end').fill(end);
 const sr=p.waitForResponse(r=>r.url().endsWith('/api/q_core_search')&&r.request().method()==='POST');await p.locator('#ui-search-submit').click();const search=await(await sr).json();
 check(search.hits?.length>0,event+' real search');await decoded(p,'#ui-case1 .ui-shot img',search.hits.length);
 await capture(p,event+'-case1',{status:search.status,hits:search.hits.length});
 if(await p.locator('#ui-q-search').getAttribute('data-open')==='true')await p.locator('#ui-q-search [aria-label=收起查詢窗]').click();
 await p.locator('#ui-case1 .ui-shot').first().click();await decoded(p,'.ui-lb-img',1);await p.getByRole('button',{name:'下一張',exact:true}).click();await decoded(p,'.ui-lb-img',1);await p.getByRole('button',{name:'上一張',exact:true}).click();await decoded(p,'.ui-lb-img',1);await p.keyboard.press('Escape');check(await p.locator('.ui-lightbox').count()===0,'lightbox arrows and Escape');
 await p.goto(base+'?run='+event+'&screen=case2',{waitUntil:'domcontentloaded'});
 await p.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await p.locator('#ui-track-start').fill(start);
 const tr=p.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST');await p.locator('#ui-track-submit').click();const track=await(await tr).json();
 check(track.sightings?.length>0,event+' track sightings');check(track.single_view.some(s=>s.kind==='GAP')&&track.single_view.some(s=>s.kind==='LOST'),'missing states retained');
 const first=track.sightings[0],t=first.range_us[0]+Math.floor((first.range_us[1]-first.range_us[0])/2);await seek(p,t);await decoded(p,'#ui-case2 .ui-stage-img',1);
 check(await p.locator('#ui-play').isEnabled(),event+' source playback enabled');
 check(await p.locator('#ui-stop-track').isEnabled(),'front-end stop available');
 check(await p.locator('#ui-manual-target').isDisabled()&&(await p.locator('#ui-manual-note').innerText())==='追蹤起點由系統自動選擇，目前還不能手動改選目標','D137 manual seed disabled with plain explanation (D139)');
 const singleBar=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(singleBar.y+singleBar.height-viewportHeight)<2,'single bar at viewport bottom');
 await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=el.scrollHeight;});const singleScrolled=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(singleScrolled.y+singleScrolled.height-viewportHeight)<2&&await p.locator('#ui-v1').evaluate(el=>el.scrollTop===0),'single bar fixed while only content scrolls');await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=0;});
 await capture(p,event+'-case2-single',{bar:singleBar,barAfterScroll:singleScrolled,status:track.status,reasons:track.reasons,current:await p.locator('#ui-scrub').inputValue()});
 const firstCamera=track.single_view.find(s=>s.kind==='ON_CAMERA').camera_id,ni=track.single_view.findIndex(s=>s.kind==='ON_CAMERA'&&s.camera_id!==firstCamera);
 check(ni>0,'cross-camera event');const previous=track.single_view.slice(0,ni).filter(s=>s.kind==='ON_CAMERA').at(-1),next=track.single_view[ni];
 await seek(p,Math.max(previous.range_us[0],previous.range_us[1]-200000));await decoded(p,'#ui-case2 .ui-stage-img',1);
 for(const speed of ['0.5','1','1.5','2']){await p.locator('#ui-speed').selectOption(speed);check(await p.locator('#ui-speed').inputValue()===speed,'source speed '+speed);}
 await p.locator('#ui-play').click();await p.waitForFunction(cam=>document.querySelector('#ui-case2 .ui-stamp')?.textContent.includes(cam),next.camera_id,{timeout:15000});
 await p.locator('#ui-play').click();await decoded(p,'#ui-case2 .ui-stage-img',1);check(true,event+' automatic camera switch');playbacks.push({event,camera:next.camera_id,tUs:Number(await p.locator('#ui-scrub').inputValue())});
 await p.locator('#ui-layout [data-layout=multi]').click();await decoded(p,'#ui-case2 .ui-multi-tile img',2);
 const multiStart=Number(await p.locator('#ui-scrub').inputValue());await p.locator('#ui-play').click();await p.waitForFunction(t=>Number(document.querySelector('#ui-scrub')?.value)>=t+200000,multiStart,{timeout:15000});await p.locator('#ui-play').click();await decoded(p,'#ui-case2 .ui-multi-tile img',2);check(true,event+' multi-view playback advances with decoded source RGB');
 const multiBar=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(multiBar.y+multiBar.height-viewportHeight)<2,'multi bar at viewport bottom');
 await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=el.scrollHeight;});const multiScrolled=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(multiScrolled.y+multiScrolled.height-viewportHeight)<2&&await p.locator('#ui-v1').evaluate(el=>el.scrollTop===0),'multi bar fixed while only content scrolls');await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=0;});
 await capture(p,event+'-case2-multi',{tiles:2,decoded:2,bar:multiBar,barAfterScroll:multiScrolled});
 await p.locator('#ui-layout [data-layout=single]').click();
 const stamp=event==='A4-1'?9400000:event==='B4-1'?2100000:3000000;await seek(p,stamp);
 // Empty start/end now mean a concrete full-recording WALL window, not playback_now.
 await p.locator('.ui-burger').click();await p.locator('#ui-track-start').fill('');await p.locator('#ui-track-end').fill('');const br=p.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST');await p.locator('#ui-track-submit').click();const blindResponse=await br,blind=await blindResponse.json(),blankPayload=blindResponse.request().postDataJSON();
 check(blankPayload.time?.kind==='WALL'&&!('playback_now_us' in blankPayload),'blank times send WALL rather than playback now');
 check(blankPayload.time.wall_range?.length===2&&blankPayload.time.wall_range.every((value,i)=>value.includes('T'+[start,end][i])),'blank times select full recording wall bounds');
 await writeFile(out+'/'+event+'-blind-response.json',JSON.stringify(blind,null,2));
 await seek(p,stamp);await p.waitForTimeout(300);const curves=await p.locator('#ui-floorplan .is-inferred').count();
 check(curves===0,event+' future snapshot is not shown at earlier playhead');
 if(event==='B-05')check(await p.locator('#ui-floorplan').isHidden(),'no camera positions: the whole floor-plan panel is hidden');
 await capture(p,event+'-blind',{curves,status:blind.blind?.status,confidence:blind.blind?.confidence,asOfUs:blind.as_of_us,blankPayload});
 if(event!=='B-05'){
  const at=blind.single_view.findIndex((segment,i,xs)=>i>0&&segment.kind==='ON_CAMERA'&&xs[i-1].kind==='GAP');
  check(at>0,event+' recorded reappearance exists');const reacquired=blind.single_view[at],after=reacquired.range_us[0]+10000;await seek(p,after);await p.waitForTimeout(100);
  const evidence={event,atUs:after,reacquiredCamera:reacquired.camera_id,reacquiredAtUs:reacquired.range_us[0],estimateAsOfUs:blind.blind?.estimate?.as_of_us??blind.blind?.as_of_us,label:await p.locator('#ui-blind-end').count(),curves:await p.locator('#ui-floorplan .is-inferred').count()};
  evidence.status=evidence.label?'PASS':'NEEDS_FIX';blindReview.push(evidence);await capture(p,event+'-reacquired-review',evidence);
 }
 const beforeStop=backendStopRequests.length,selected=await p.locator('#ui-run-select').inputValue();await p.locator('#ui-stop-track').click();
 check(await p.locator('#ui-stop-track').isDisabled()&&await p.locator('#ui-case2 .ui-stage-img').count()===0&&(await p.locator('#ui-case2').innerText()).includes('追蹤顯示已停止'),'D137 stops playback and clears tracking display');
 check(await p.locator('#ui-run-select').inputValue()===selected&&backendStopRequests.length===beforeStop,'stop preserves source and makes no backend stop call');
 await p.getByRole('button',{name:'回查詢窗重新輸入特徵',exact:true}).click();await p.locator('#ui-track-start').fill(start);const restarted=p.waitForResponse(r=>r.url().endsWith('/api/q_core_track'));await p.locator('#ui-track-submit').click();await restarted;await seek(p,t);await decoded(p,'#ui-case2 .ui-stage-img',1);check(true,'new query restarts tracking after stop');await p.locator('#ui-stop-track').click();await capture(p,event+'-stopped',{backendStopRequests:backendStopRequests.length-beforeStop});
 await p.locator('#ui-modes [data-mode=case3]').click();check(await p.locator('#ui-v1').getAttribute('data-screen')==='case3','mode control opens real wall');await p.waitForFunction(n=>document.querySelectorAll('.mr-tile[data-status=READY]').length===n,cameras);check(true,event+' real wall camera count');
 check(await p.locator('#ui-events button:disabled').count()===0,'integrated sources selectable');for (const speed of ['0.5','1','1.5','2']) { await p.locator('#ui-wall-speed').selectOption(speed);check(await p.locator('#ui-wall-speed').inputValue()===speed,'case3 playback speed '+speed); }
 const transport=await p.locator('#ui-case3 .transport').boundingBox();check(Math.abs(transport.y+transport.height-viewportHeight)<2,'case3 transport at viewport bottom');
 await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=el.scrollHeight;});const scrolled=await p.locator('#ui-case3 .transport').boundingBox();check(Math.abs(scrolled.y+scrolled.height-viewportHeight)<2,'case3 transport remains fixed while content scrolls');await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=0;});
 await capture(p,event+'-case3',{readyCameras:cameras,bar:transport,barAfterScroll:scrolled});
 const dest=event==='A4-1'?'B4-1':'A4-1', destButton=p.locator('#ui-events button').filter({hasText:dest}), destRun=await destButton.getAttribute('data-event');await destButton.click();await p.waitForURL(u=>u.searchParams.get('run')===destRun);await p.waitForFunction(()=>document.querySelectorAll('.mr-tile[data-status=READY]').length>0);check(true,'event selection loads source');
 await p.goto(base+'admin.html',{waitUntil:'domcontentloaded'});await p.locator('#admin-title').waitFor();await p.waitForTimeout(300);await capture(p,event+'-admin-overview');
 await p.locator('[data-tab=settings]').click();await capture(p,event+'-admin-settings');
 await p.locator('.ui-set-row').filter({hasText:'預設進入'}).getByRole('button',{name:'case2',exact:true}).click();await p.getByRole('button',{name:'儲存',exact:true}).click();check((await p.locator('#settings-saved').innerText()).includes('已儲存'),'settings saved');
 await p.goto(base+'?run='+event);await p.locator('#ui-enter').click();check(await p.locator('#ui-v1').getAttribute('data-screen')==='case2','default case persisted');
 await p.goto(base+'admin.html#settings');await p.getByRole('button',{name:'還原預設',exact:true}).click();await p.getByRole('button',{name:'儲存',exact:true}).click();await p.goto(base+'?run='+event);await p.locator('#ui-enter').click();check(await p.locator('#ui-v1').getAttribute('data-screen')==='choose','restore defaults persisted');await ctx.close();
}
const extra=await b.newContext({viewport:{width:1440,height:viewportHeight}}),p=await extra.newPage();p.on('pageerror',e=>errors.push({event:'deep-links',error:e.stack??String(e)}));
for(const [event,stamp]of[['B-05',3000000],['A4-1',9400000],['B4-1',2100000]]){
 await p.goto(base+'?run='+event+'&screen=blind&as_of_us='+stamp);await p.waitForFunction(()=>document.querySelector('#q-core-feedback')?.textContent.includes('追蹤回應：'));
 check(await p.locator('#ui-v1').getAttribute('data-screen')==='case2','blind deep link opens new tracking screen');await p.waitForTimeout(150);await capture(p,event+'-blind-link');check(event==='B-05'?(await p.locator('#ui-floorplan').innerText()).includes('尚無鏡頭位置資料'):await p.locator('#ui-floorplan .is-inferred').count()>0,'blind deep link shows declared uncertainty');
}
for(const [name,query,n]of[['r005-location','region=R101',1],['r005-laptop','class=laptop',2]]){
 await p.goto(base+'?run=r005&screen=search&'+query);await decoded(p,'#ui-case1 .ui-shot img',n);check(await p.locator('#ui-v1').getAttribute('data-screen')==='case1','r005 deep link opens result wall');await capture(p,name,{cards:n});
}
await extra.close();check(errors.length===0,'no page errors');check(http.length===0,'no failed API responses');
}finally{await writeFile(out+'/browser-results.json',JSON.stringify({source_head:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),viewport:{width:1440,height:viewportHeight},checks,results,playbacks,blindReview,errors,http},null,2));console.log(JSON.stringify({checks,screenshots:results.length,errors,http}));await b.close();}

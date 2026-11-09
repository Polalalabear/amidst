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
const results=[],errors=[],http=[],playbacks=[],backendStopRequests=[],blindReview=[],d146Review=[],assertions=[],observerErrors=[];let checks=0;const check=(ok,text)=>{assert.ok(ok,text);checks++;assertions.push(text);};
const capture=async(p,name,data={})=>{const file=out+'/screenshots/'+name+'.png';await p.screenshot({path:file,fullPage:true});const raw=await readFile(file);const r={name,url:p.url(),bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex'),...data};results.push(r);console.log(JSON.stringify(r));};
// D139: blank times select the full recording. A later snapshot must stay hidden at an earlier playhead; endpoint persistence is recorded separately as a review finding.
const seek=async(p,t)=>{await p.locator('#ui-scrub').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input',{bubbles:true}));},t);check(Number(await p.locator('#ui-scrub').inputValue())===t,'range input preserves requested timestamp');};
const decoded=async(p,selector,n)=>{await p.waitForFunction(({selector,n})=>{const xs=[...document.querySelectorAll(selector)];return xs.length===n&&xs.every(i=>!i.hidden&&i.complete&&i.naturalWidth>0);},{selector,n});check(true,selector+' decoded RGB');};
const pinnedEvidence=JSON.parse(await readFile(new URL('../../../tests/q1q5/fixtures/d147-d149-track-receipt.engineering.json',import.meta.url),'utf8'));
const checkZoom=async(p,event,screen)=>{
 const metrics=[];
 for(const z of [60,80,100,125,150]){
  await p.locator('#ui-zoom').selectOption(String(z));await p.waitForTimeout(100);
  const m=await p.evaluate(()=>{const scr=document.querySelector('.ui-screens'),top=[...document.querySelectorAll('.ui-top-right > *')].filter(n=>n.getClientRects().length).map(n=>n.getBoundingClientRect().right);return {pageH:document.documentElement.scrollWidth>innerWidth,screensH:scr.scrollWidth>scr.clientWidth+1,topRight:Math.max(...top),vw:innerWidth};});
  metrics.push({zoom:z,...m});check(!m.pageH&&!m.screensH&&m.topRight<=m.vw+.5,`${event} ${screen} ${z}% has no horizontal overflow`);
  if(z===60||z===150)await capture(p,`${event}-${screen}-zoom-${z}`);
 }
 await p.locator('#ui-zoom').selectOption('100');d146Review.push({event,kind:'zoom',screen,metrics});
};
const sourcePixel=async(p,event,t,kind,cam,frames)=>{
 await seek(p,t);
 await p.waitForFunction(({kind,cam})=>{const stage=document.querySelector('.ui-stagebox'),img=stage?.querySelector('img'),stamp=stage?.querySelector('.ui-stamp');return stage?.dataset.kind===kind&&stamp?.textContent.startsWith(cam+' ·')&&img&&!img.hidden&&img.complete&&img.naturalWidth>0;},{kind,cam});
 // A paused seek must finish the request for this exact source timestamp, not leave a stale picture.
 await p.waitForFunction(({t})=>Number(document.querySelector('#ui-scrub')?.value)===t,{t});
 let row;const FRAME_STEP_US=200000;   // recorded runs are 5 fps
 for(let n=0;n<100;n++){
  const url=await p.locator('.ui-stage-img').getAttribute('src');row=frames.findLast(f=>f.tUs<=t&&t-f.tUs<FRAME_STEP_US&&f.cam===cam&&f.mediaUrl===url);   // D147 frameTUs: requests snap to the frame floor
  if(row)break;await p.waitForTimeout(50);
 }
 check(!!row,`${event} ${kind} ${t} uses the requested source frame`);
 const img=await p.locator('.ui-stage-img').getAttribute('src'),res=await p.request.get(new URL(img,base).href),raw=await res.body();
 check(res.status()===200&&createHash('sha256').update(raw).digest('hex')===row.servedSha256,`${event} ${kind} ${t} RGB bytes match the bound frame hash`);
 if(kind==='GAP'||kind==='LOST'){
  check(await p.locator('.ui-tag-obs').isHidden(),`${event} ${kind} is not labelled observed`);
  check((await p.locator('.ui-live-note').innerText()).includes('持續播放'),`${event} ${kind} explains continued camera playback`);
 }
 if(kind==='LOST')check((await p.locator('.ui-track-title').innerText()).includes(`已跟丟 · 最後出現在 ${cam.replace(/^CAM_/,'')} 鏡頭`),`${event} LOST title names the last camera`);
 return {event,kind,tUs:t,cam,frameIndex:row.frameIndex,sourceTimeS:row.sourceTimeS,servedSha256:row.servedSha256};
};
const continuous=async(p,event,track,frames)=>{
 const start=track.single_view.find(s=>s.kind==='ON_CAMERA').range_us[0];
 await seek(p,start);await decoded(p,'#ui-case2 .ui-stage-img',1);await p.locator('#ui-speed').selectOption('2');
 await p.evaluate(()=>{window.__d146={running:true,total:0,missing:0,notDecoded:0,samples:[],lastKey:null};const tick=()=>{const r=window.__d146;if(!r.running)return;const stage=document.querySelector('.ui-stagebox'),img=stage?.querySelector('img'),stamp=stage?.querySelector('.ui-stamp')?.textContent??'',tag=stage?.querySelector('.ui-tag-obs');r.total++;if(!img||img.hidden||!img.getAttribute('src'))r.missing++;if(!img?.complete||!img?.naturalWidth)r.notDecoded++;const sample={tUs:Number(document.querySelector('#ui-scrub')?.value),kind:stage?.dataset.kind,stamp,observed:!!tag&&!tag.hidden,decoded:!!img?.complete&&img.naturalWidth>0};const key=JSON.stringify([Math.floor(sample.tUs/200000),sample.kind,sample.stamp,sample.observed]);if(key!==r.lastKey){r.samples.push(sample);r.lastKey=key;}requestAnimationFrame(tick);};requestAnimationFrame(tick);});
 const firstFrame=frames.length;await p.locator('#ui-play').click();
 await p.waitForFunction(end=>Number(document.querySelector('#ui-scrub')?.value)>=end-300000,track.as_of_us,{timeout:90000});
 if((await p.locator('#ui-play').innerText()).includes('❚'))await p.locator('#ui-play').click();
 const sample=await p.evaluate(()=>{window.__d146.running=false;return window.__d146;});
 check(sample.total>100&&sample.missing===0,`${event} continuous playback never clears or hides the stage image (${sample.total} sampled renders)`);
 for(const kind of [...new Set(track.single_view.map(s=>s.kind))])check(sample.samples.some(s=>s.kind===kind&&s.decoded),`${event} continuous playback includes decoded ${kind} images`);
 check(sample.samples.filter(s=>s.kind==='GAP'||s.kind==='LOST').every(s=>!s.observed),`${event} continued GAP/LOST playback never claims observation`);
 const served=frames.slice(firstFrame);
 for(const kind of [...new Set(track.single_view.map(s=>s.kind))]){
  const xs=served.filter(f=>track.single_view.some(s=>s.kind===kind&&s.range_us[0]<=f.tUs&&f.tUs<s.range_us[1]));
  check(new Set(xs.map(f=>f.frameIndex)).size>=Math.min(2,Math.max(...track.single_view.filter(s=>s.kind===kind).map(s=>Math.ceil((s.range_us[1]-s.range_us[0])/200000)))),`${event} ${kind} source frame indices advance across available grid cells`);
 }
 const review={event,kind:'continuous',sample,frameResponses:served.map(({mediaUrl,...f})=>f)};d146Review.push(review);
 await capture(p,event+'-continuous-end',{sampledRenders:sample.total,missing:sample.missing,notDecodedRenders:sample.notDecoded});
};
try{
for(const [event,start,end,cameras]of[['B-05','13:00:00','13:00:08',2],['A4-1','14:00:00','14:00:50',4],['B4-1','14:10:00','14:10:42',5]]){
 const ctx=await b.newContext({viewport:{width:1440,height:viewportHeight},deviceScaleFactor:1}),p=await ctx.newPage(),frames=[],frameJobs=[];
 p.on('response',r=>{if(r.url().endsWith('/api/q_frames')&&r.status()===200)frameJobs.push(r.json().then(doc=>{for(const tile of doc.tiles??[])frames.push({tUs:doc.t_us,cam:tile.camera_id,status:tile.status,frameIndex:tile.frame_index,sourceTimeS:tile.timestamp_s,servedSha256:tile.served_sha256,mediaUrl:tile.media_url});}).catch(error=>observerErrors.push({event,error:String(error),kind:'RESPONSE_BODY_CAPTURE_UNAVAILABLE'})));});
 p.on('request',r=>{if(/\/api\/.*(?:stop|manual)/.test(r.url()))backendStopRequests.push(new URL(r.url()).pathname);});
 p.on('pageerror',e=>errors.push({event,error:e.stack??String(e)}));p.on('response',r=>{if(r.url().includes('/api/')&&r.status()!==200)http.push({event,path:new URL(r.url()).pathname,status:r.status()});});
 await p.goto(base+'?run='+event,{waitUntil:'domcontentloaded'});await p.locator('#ui-enter').waitFor();await p.waitForTimeout(650);
 check((await p.locator('.ui-tagline').innerText()).includes('Agentic'),'cover tagline');await capture(p,event+'-cover');
 await p.locator('#ui-enter').click();await p.locator('[data-case=case1]').click();
 const bootResponse=await p.request.get(new URL('/api/q_bootstrap',base).href);check(bootResponse.status()===200,'bootstrap available');const boot=await bootResponse.json(),run=boot.runs.find(r=>r.title?.startsWith(event+' '));check(!!run,event+' source-bound bootstrap run');
 const shownCounts=await p.locator('#ui-q-search [data-role=classes] [data-value]').evaluateAll(xs=>Object.fromEntries(xs.map(x=>[x.dataset.value,x.querySelector('.ui-class-count')?.textContent.trim()??null])));
 // D147: only the scene's featured classes sit on top with camera counts; D149: a featured count is the union of detected and annotated cameras
 const featured={'B-05':['person'],'A4-1':['person','car'],'B4-1':['person']}[event];
 for(const label of featured){const row=run.detected_class_counts.find(r=>r.class_label===label),cams=new Set([...(row?.camera_ids??[]),...(run.scene_annotations??[]).filter(a=>a.class_label===label).flatMap(a=>a.camera_ids)]);
  check(Number(shownCounts[label])===cams.size,`${event} featured ${label} camera count equals bootstrap detected∪annotated ${cams.size}`);}
 check(Object.entries(shownCounts).every(([k,v])=>v===null||featured.includes(k)),`${event} only the featured classes carry camera counts`);
 const otherToggle=p.locator('#ui-q-search [data-role=other-toggle]');if(await otherToggle.count()&&await otherToggle.getAttribute('aria-expanded')!=='true')await otherToggle.click();
 const listed=new Set(await p.locator('#ui-q-search [data-role=classes] [data-value], #ui-q-search [data-value]').evaluateAll(xs=>xs.map(x=>x.dataset.value)));
 for(const row of run.detected_class_counts)check(listed.has(row.class_label),`${event} detected class ${row.class_label} listed (top or 其他類別)`);
 if(await otherToggle.count())await otherToggle.click();
 if(event==='B4-1')check(Number(shownCounts.person)===5,'B4-1 search person shows 5 cameras');
 await capture(p,event+'-search-camera-counts');await checkZoom(p,event,'search');
 await p.locator('#ui-q-search [data-role=classes] [data-value=person]').click();await p.locator('#ui-search-start').fill(start);await p.locator('#ui-search-end').fill(end);
 const sr=p.waitForResponse(r=>r.url().endsWith('/api/q_core_search')&&r.request().method()==='POST');await p.locator('#ui-search-submit').click();const search=await(await sr).json();
 check(search.hits?.length>0,event+' real search');await decoded(p,'#ui-case1 .ui-shot img',search.hits.length);
 await capture(p,event+'-case1',{status:search.status,hits:search.hits.length});
 if(await p.locator('#ui-q-search').getAttribute('data-open')==='true')await p.locator('#ui-q-search [aria-label=收起查詢窗]').click();
 await p.locator('#ui-case1 .ui-shot').first().click();await decoded(p,'.ui-lb-img',1);await p.getByRole('button',{name:'下一張',exact:true}).click();await decoded(p,'.ui-lb-img',1);await p.getByRole('button',{name:'上一張',exact:true}).click();await decoded(p,'.ui-lb-img',1);await p.keyboard.press('Escape');check(await p.locator('.ui-lightbox').count()===0,'lightbox arrows and Escape');
 await p.goto(base+'?run='+event+'&screen=case2',{waitUntil:'domcontentloaded'});
 check(await p.locator('#ui-q-track .ui-class-count').count()===0,event+' tracking features contain names without counts');
 await p.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await p.locator('#ui-track-start').fill(start);
 const tr=p.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST');await p.locator('#ui-track-submit').click();const track=await(await tr).json();
 await writeFile(out+'/'+event+'-track-response.json',JSON.stringify(track,null,2));
 if(event!=='B-05'){const expected=pinnedEvidence.runs.find(r=>r.label===event);check(track.resolved_scope?.detection_index_sha256===expected.index_content_sha256,event+' exact original index pin');assert.deepEqual(track.single_view,expected.single_view);check(true,event+' complete single_view matches D147/D148/D150 backend receipt');}
 check(track.sightings?.length>0,event+' track sightings');check(track.single_view.some(s=>s.kind==='GAP'),'source gaps retained');check(track.single_view.at(-1).kind==='LOST'?track.status==='LOST':track.status==='TRACKING','terminal state follows current source evidence');
 const first=track.sightings[0],t=first.range_us[0]+Math.floor((first.range_us[1]-first.range_us[0])/2);await seek(p,t);await decoded(p,'#ui-case2 .ui-stage-img',1);
 check(await p.locator('#ui-play').isEnabled(),event+' source playback enabled');
 check(await p.locator('#ui-stop-track').isEnabled(),'front-end stop available');
 check(await p.locator('#ui-manual-target').isDisabled()&&(await p.locator('#ui-manual-note').innerText())==='追蹤起點由系統自動選擇，目前還不能手動改選目標','D137 manual seed disabled with plain explanation (D139)');
 const singleBar=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(singleBar.y+singleBar.height-viewportHeight)<2,'single bar at viewport bottom');
 await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=el.scrollHeight;});const singleScrolled=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(singleScrolled.y+singleScrolled.height-viewportHeight)<2&&await p.locator('#ui-v1').evaluate(el=>el.scrollTop===0),'single bar fixed while only content scrolls');await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=0;});
 await capture(p,event+'-case2-single',{bar:singleBar,barAfterScroll:singleScrolled,status:track.status,reasons:track.reasons,current:await p.locator('#ui-scrub').inputValue()});
 check(event==='B-05'?await p.locator('#ui-floorplan').isHidden():await p.locator('#ui-floorplan').isVisible(),event+' floor-plan visibility follows camera position availability');
 await checkZoom(p,event,'track');
 if(event!=='B-05'){
  await continuous(p,event,track,frames);
  const gap=track.single_view.filter(s=>s.kind==='GAP').sort((a,b)=>(b.range_us[1]-b.range_us[0])-(a.range_us[1]-a.range_us[0]))[0],last=track.single_view.slice(0,track.single_view.indexOf(gap)).filter(s=>s.kind==='ON_CAMERA').at(-1).camera_id;
  const gapTimes=gap.range_us[1]-gap.range_us[0]>=400000?[gap.range_us[0]+10000,gap.range_us[1]-10000]:[gap.range_us[0]+10000],gapPixels=[];for(const stamp of gapTimes)gapPixels.push(await sourcePixel(p,event,stamp,'GAP',last,frames));check(gapPixels.length===1||gapPixels[0].frameIndex!==gapPixels[1].frameIndex,event+' GAP displays its actual source samples (one grid cell for a 0.2 s GAP)');d146Review.push({event,kind:'gap-source-pixels',frames:gapPixels});await capture(p,event+'-gap-live');
  const lost=track.single_view.find(s=>s.kind==='LOST');if(lost){const lastCam=track.single_view.filter(s=>s.kind==='ON_CAMERA').at(-1).camera_id,lostPixels=[];for(const stamp of [lost.range_us[0]+10000,Math.min(lost.range_us[0]+1210000,lost.range_us[1]-10000)])lostPixels.push(await sourcePixel(p,event,stamp,'LOST',lastCam,frames));check(lostPixels[0].frameIndex!==lostPixels[1].frameIndex,event+' LOST continues advancing last-camera source frames');d146Review.push({event,kind:'lost-source-pixels',frames:lostPixels});await capture(p,event+'-lost-live');}else check(track.status==='TRACKING'&&track.blind===null,event+' D148 evidence reaches query end without an invented LOST tail');
  const same=track.sightings.find(s=>s.link_kind==='SAME_CAMERA_REACQUISITION');if(event==='A4-1'){check(!!same&&track.reasons.includes('SAME_CAMERA_REACQUISITION'),'A4-1 D145 reacquisition explicitly marked');d146Review.push(await sourcePixel(p,event,same.range_us[0]+10000,'ON_CAMERA',same.camera_id,frames));check(await p.locator('.ui-tag-obs').isVisible(),'A4-1 reacquisition is shown as observed inside its new local segment');await capture(p,event+'-same-camera-reacquisition');}
 }
 const firstCamera=track.single_view.find(s=>s.kind==='ON_CAMERA').camera_id,ni=track.single_view.findIndex(s=>s.kind==='ON_CAMERA'&&s.camera_id!==firstCamera);
 check(ni>0,'cross-camera event');const previous=track.single_view.slice(0,ni).filter(s=>s.kind==='ON_CAMERA').at(-1),next=track.single_view[ni];
 await seek(p,Math.max(previous.range_us[0],previous.range_us[1]-200000));await decoded(p,'#ui-case2 .ui-stage-img',1);
 for(const speed of ['0.5','1','1.5','2']){await p.locator('#ui-speed').selectOption(speed);check(await p.locator('#ui-speed').inputValue()===speed,'source speed '+speed);}
 await p.locator('#ui-play').click();await p.waitForFunction(cam=>document.querySelector('#ui-case2 .ui-stamp')?.textContent.includes(cam),next.camera_id,{timeout:15000});
 await p.locator('#ui-play').click();await decoded(p,'#ui-case2 .ui-stage-img',1);check(true,event+' automatic camera switch');playbacks.push({event,camera:next.camera_id,tUs:Number(await p.locator('#ui-scrub').inputValue())});
 await p.locator('#ui-layout [data-layout=multi]').click();await decoded(p,'#ui-case2 .ui-multi-tile img',track.multi_view.length);
 const multiStart=Number(await p.locator('#ui-scrub').inputValue());await p.locator('#ui-play').click();await p.waitForFunction(t=>Number(document.querySelector('#ui-scrub')?.value)>=t+200000,multiStart,{timeout:15000});await p.locator('#ui-play').click();await decoded(p,'#ui-case2 .ui-multi-tile img',track.multi_view.length);check(true,event+' multi-view playback advances with decoded source RGB');
 const multiBar=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(multiBar.y+multiBar.height-viewportHeight)<2,'multi bar at viewport bottom');
 await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=el.scrollHeight;});const multiScrolled=await p.locator('#ui-track-bar').boundingBox();check(Math.abs(multiScrolled.y+multiScrolled.height-viewportHeight)<2&&await p.locator('#ui-v1').evaluate(el=>el.scrollTop===0),'multi bar fixed while only content scrolls');await p.locator('.ui-screens').evaluate(el=>{el.scrollTop=0;});
 await capture(p,event+'-case2-multi',{tiles:track.multi_view.length,decoded:track.multi_view.length,bar:multiBar,barAfterScroll:multiScrolled});
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
 await capture(p,event+'-case3',{readyCameras:cameras,bar:transport,barAfterScroll:scrolled});await checkZoom(p,event,'wall');await Promise.all(frameJobs);
 const dest=event==='A4-1'?'B4-1':'A4-1', destButton=p.locator('#ui-events button').filter({hasText:dest}), destRun=await destButton.getAttribute('data-event');await destButton.click();await p.waitForURL(u=>u.searchParams.get('run')===destRun);await p.waitForFunction(()=>document.querySelectorAll('.mr-tile[data-status=READY]').length>0);check(true,'event selection loads source');
 await p.goto(base+'admin.html',{waitUntil:'domcontentloaded'});await p.locator('#admin-title').waitFor();await p.waitForTimeout(300);await capture(p,event+'-admin-overview');
 await p.locator('[data-tab=settings]').click();await capture(p,event+'-admin-settings');
 await p.locator('.ui-set-row').filter({hasText:'預設進入'}).getByRole('button',{name:'case2',exact:true}).click();await p.getByRole('button',{name:'儲存',exact:true}).click();check((await p.locator('#settings-saved').innerText()).includes('已儲存'),'settings saved');
 await p.goto(base+'?run='+event);await p.locator('#ui-enter').click();check(await p.locator('#ui-v1').getAttribute('data-screen')==='case2','default case persisted');
 await p.goto(base+'admin.html#settings');await p.getByRole('button',{name:'還原預設',exact:true}).click();await p.getByRole('button',{name:'儲存',exact:true}).click();await p.goto(base+'?run='+event);await p.locator('#ui-enter').click();check(await p.locator('#ui-v1').getAttribute('data-screen')==='choose','restore defaults persisted');await ctx.close();
}
const extra=await b.newContext({viewport:{width:1440,height:viewportHeight}}),p=await extra.newPage();p.on('pageerror',e=>errors.push({event:'deep-links',error:e.stack??String(e)}));
for(const [event,stamp]of[['B-05',3000000],...pinnedEvidence.runs.map(r=>{const g=r.single_view.find(s=>s.kind==='GAP');return [r.label,Math.floor((g.range_us[0]+g.range_us[1])/2)];})]){
 await p.goto(base+'?run='+event+'&screen=blind&as_of_us='+stamp);await p.waitForFunction(()=>document.querySelector('#q-core-feedback')?.textContent.includes('追蹤回應：'));
 check(await p.locator('#ui-v1').getAttribute('data-screen')==='case2','blind deep link opens new tracking screen');await p.waitForTimeout(150);await capture(p,event+'-blind-link');check(event==='B-05'?await p.locator('#ui-floorplan').isHidden():await p.locator('#ui-floorplan .is-inferred').count()>0,'blind deep link respects plan availability and declared uncertainty');
}
for(const [name,query,n]of[['r005-location','region=R101',1],['r005-laptop','class=laptop',2]]){
 await p.goto(base+'?run=r005&screen=search&'+query);await decoded(p,'#ui-case1 .ui-shot img',n);check(await p.locator('#ui-v1').getAttribute('data-screen')==='case1','r005 deep link opens result wall');await capture(p,name,{cards:n});
}
await p.goto(base+'?run=A4-1&screen=search&class=car');await decoded(p,'#ui-case1 .ui-shot img',1);check((await p.locator('#ui-case1').innerText()).includes('場景標註：車輛（非偵測）'),'D149 car card explicitly marked as scene annotation');await capture(p,'a4-car-annotation');
await extra.close();check(errors.length===0,'no page errors');check(http.length===0,'no failed API responses');
}finally{await writeFile(out+'/browser-results.json',JSON.stringify({source_head:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),test_script_sha256:createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex'),viewport:{width:1440,height:viewportHeight},checks,assertions,results,playbacks,blindReview,d146Review,observerErrors,errors,http},null,2));console.log(JSON.stringify({checks,screenshots:results.length,errors,http}));await b.close();}

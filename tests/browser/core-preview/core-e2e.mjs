// Synthetic API conformance through the redesigned visible front desk.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {ownedRuntime} from './owned-runtime.mjs';
const owned=ownedRuntime();
import {pathToFileURL} from 'node:url';
import {startPreview} from './preview-server.mjs';
const source=process.env.CORE_SOURCE;if(!source)throw Error('CORE_SOURCE_REQUIRED');
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE??owned.playwrightModule).href);
const out=process.env.SCREENSHOT_DIR??join(owned.evidenceRoot,'ui-synthetic');await mkdir(out,{recursive:true});
const preview=await startPreview({source,port:0}),browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
const viewportHeight=Number(process.env.CORE_VIEWPORT_HEIGHT??900);
const page=await browser.newPage({viewport:{width:1440,height:viewportHeight},deviceScaleFactor:1}),errors=[],shots=[];let checks=0,result=null;
const check=(ok,msg)=>{assert.ok(ok,msg);checks++;console.log(JSON.stringify({check:checks,message:msg}));};page.on('pageerror',e=>errors.push(String(e)));const iconRequests=[];page.on('request',r=>{if(/favicon\.ico/.test(r.url()))iconRequests.push(r.url());});
const shot=async name=>{const path=join(out,name+'.png');await page.screenshot({path,fullPage:true});const b=await readFile(path);shots.push({path,bytes:b.length,sha256:createHash('sha256').update(b).digest('hex')});};

// D139: the query window keeps time fields and the submit button fixed; only the feature list scrolls (all features expanded).
const stickyCheck=async kind=>{
 const win='#ui-q-'+kind,btn='#ui-'+kind+'-submit';
 await page.locator(win+' [data-role=classes]').evaluate(box=>{for(let i=0;i<80;i++){const b=document.createElement('button');b.type='button';b.className='ui-chip-btn';b.dataset.injected='1';b.textContent='coco-class-'+i;box.append(b);}});
 const rects=async()=>page.evaluate(([win,btn,kind])=>{const r=s=>{const b=document.querySelector(s).getBoundingClientRect();return {y:Math.round(b.y),bottom:Math.round(b.bottom)};};const feat=document.querySelector(win+' .ui-qfeat'),w=document.querySelector(win),b=document.querySelector(btn).getBoundingClientRect();const hit=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return {submit:r(btn),time:r('#ui-'+kind+'-start'),vh:innerHeight,scrollable:feat.scrollHeight>feat.clientHeight+10,featOverflow:getComputedStyle(feat).overflowY,winScrolls:w.scrollHeight>w.clientHeight+1,hit:hit===document.querySelector(btn)};},[win,btn,kind]);
 const before=await rects();
 check(before.submit.bottom<=before.vh&&before.hit,'D139 '+kind+' submit button visible and hittable at open with all features expanded (vh '+before.vh+')');
 check(before.scrollable&&before.featOverflow==='auto'&&!before.winScrolls,'D139 '+kind+' only the feature list scrolls');
 await page.locator(win+' .ui-qfeat').evaluate(el=>{el.scrollTop=el.scrollHeight;});
 const after=await rects();check(after.submit.y===before.submit.y&&after.time.y===before.time.y&&after.hit,'D139 '+kind+' time fields and button stay fixed while the feature list scrolls');
 await page.locator(btn).click({trial:true});
 await page.locator(win+' [data-injected]').evaluateAll(n=>n.forEach(x=>x.remove()));
 // burger / Esc: closed window is not interactive
 const where=await page.locator(btn).boundingBox();await page.keyboard.press('Escape');
 const closed=await page.evaluate(([win,x,y])=>{const w=document.querySelector(win),cs=getComputedStyle(w);return {open:w.dataset.open,inert:w.inert,vis:cs.visibility,pe:cs.pointerEvents,hit:w.contains(document.elementFromPoint(x,y))};},[win,where.x+where.width/2,where.y+where.height/2]);
 check(closed.open==='false'&&closed.inert&&closed.vis==='hidden'&&closed.pe==='none'&&!closed.hit,'D139 '+kind+' Esc closes the query window and it is no longer interactive');
 await page.locator('.ui-burger').click();check(await page.locator(win).getAttribute('data-open')==='true'&&!(await page.locator(win).evaluate(w=>w.inert)),'D139 burger reopens the '+kind+' query window');
};
const calls=route=>preview.routeCalls.filter(c=>c.route===route);
const open=async kind=>{if(await page.locator('#ui-q-'+kind).getAttribute('data-open')!=='true')await page.locator('.ui-burger').click();};
const submit=async(kind,n)=>{await open(kind==='search'?'search':'track');const resp=page.waitForResponse(r=>r.url().endsWith('/api/q_core_'+kind)&&r.request().method()==='POST');await page.locator('#ui-'+kind+'-submit').click();await resp;if(kind==='search')await page.waitForFunction(n=>document.querySelectorAll('#ui-case1 .ui-shot').length===n,n);else await page.locator('#ui-scrub').waitFor();};
const seek=async t=>{await page.locator('#ui-scrub').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input',{bubbles:true}));},t);check(Number(await page.locator('#ui-scrub').inputValue())===t,'seek value preserved');};
const feature=async value=>{const b=page.locator('#ui-q-search [data-role=classes] [data-value="'+value+'"]');if(await b.getAttribute('aria-pressed')!=='true')await b.click();};
try{
 await page.goto(preview.url,{waitUntil:'domcontentloaded'});await page.locator('#ui-enter').waitFor();
 check(await page.locator('#synthetic-api-banner').isVisible(),'synthetic banner visible above new UI');check((await page.locator('.ui-tagline').innerText()).includes('Agentic'),'approved cover tagline');await shot('00-cover');
 await page.locator('#ui-enter').click();await page.locator('[data-case=case1]').click();await page.locator('#ui-q-search [data-role=regions] button').first().waitFor();
 await stickyCheck('search');const initial=calls('/api/q_core_search').length;
 await page.locator('#ui-search-submit').click();check((await page.locator('#ui-search-feedback').innerText()).includes('地點與特徵至少選一項'),'empty criteria validation');check(calls('/api/q_core_search').length===initial,'empty criteria sends no request');
 await feature('person');await page.locator('#ui-search-end').fill('');await page.locator('#ui-search-submit').click();check((await page.locator('#ui-search-feedback').innerText()).includes('請輸入開始與結束時間'),'missing time validation');check(calls('/api/q_core_search').length===initial,'missing time sends no request');
 await page.locator('#ui-search-start').fill('13:00:00');await page.locator('#ui-search-end').fill('13:00:02');await feature('');
 const region=()=>page.locator('#ui-q-search [data-role=regions] [data-value=SYNTHETIC_ROOM_A]');await region().click();await submit('search',1);
 check(calls('/api/q_core_search').at(-1).payload.feature===null,'location only feature null');check(await page.locator('#ui-wall').isVisible(),'result wall visible');await shot('01-location-only');
 await open('search');await region().click();await feature('person');await submit('search',2);check(calls('/api/q_core_search').at(-1).payload.region_ids.length===0,'feature only no region');check(await page.locator('#ui-case1 .ui-shot').count()===2,'feature two cameras');await shot('02-feature-only');
 await open('search');await region().click();await submit('search',1);check(calls('/api/q_core_search').at(-1).payload.feature.class_label==='person','combined feature');check(calls('/api/q_core_search').at(-1).payload.region_ids.length===1,'combined region');await shot('03-combined');
 await page.route('**/api/q_core_search',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error_code:'Q_RESOURCE_UNAVAILABLE'})}));await open('search');await page.locator('#ui-search-submit').click();await page.waitForFunction(()=>document.querySelector('#ui-search-feedback')?.textContent.includes('Q_RESOURCE_UNAVAILABLE'));check(await page.locator('#ui-case1 .ui-shot').count()===0,'failed search clears result wall');await shot('04-unavailable');await page.unroute('**/api/q_core_search');
 let intercepted=0,releaseFirst;await page.route('**/api/q_core_search',async r=>{if(++intercepted===1)await new Promise(done=>{releaseFirst=done;});await r.continue();});
 await open('search');await page.locator('#ui-search-submit').click();await open('search');await region().click();const newer=page.waitForResponse(r=>r.url().endsWith('/api/q_core_search'));await page.locator('#ui-search-submit').click();await newer;releaseFirst();await page.waitForTimeout(150);check(intercepted===2,'two overlapping browser requests');check(await page.locator('#ui-case1 .ui-shot').count()===2,'late response cannot replace new result');await page.unroute('**/api/q_core_search');
 // Selection must not rebuild already decoded result tiles.
 if(await page.locator('#ui-q-search').getAttribute('data-open')==='true')await page.locator('#ui-q-search [aria-label=收起查詢窗]').click();
 const mediaBefore=calls('/api/q_media_grant').length;
 const handle=await page.locator('#ui-case1 .ui-shot img').first().elementHandle();await page.waitForTimeout(400);check(await handle.evaluate(img=>img.isConnected)&&calls('/api/q_media_grant').length===mediaBefore,'phase completion retains image node and media grants');await page.locator('#ui-case1 .ui-shot').first().click();check(await handle.evaluate(img=>img.isConnected),'selection retains image node');check(calls('/api/q_media_grant').length===mediaBefore,'unchanged result does not request images again');check(await page.locator('.ui-lightbox').isVisible(),'new UI lightbox');await page.getByRole('button',{name:'回到結果牆'}).click();
 await page.locator('.ui-brand').click();await page.locator('#ui-enter').click();await page.locator('[data-case=case2]').click();await page.locator('#ui-q-track [data-role=classes] [data-value=person]').waitFor();await stickyCheck('track');
 {const win='#ui-q-track',inp=win+' .ui-feat-search',chips=()=>page.locator(win+' [data-role=classes] .ui-chip-btn:visible').allInnerTexts();
  const y0=(await page.locator(inp).boundingBox()).y,fy0=(await page.locator(win+' #ui-track-start').boundingBox()).y;
  await page.locator(inp).fill('人');check((await chips()).some(t=>t.startsWith('人物'))&&!(await chips()).some(t=>/^(筆電|背包)/.test(t)),'D139 search "人" keeps 人物 only: '+(await chips()).join('|'));
  await page.locator(inp).fill('PERSON');check((await chips()).some(t=>t.startsWith('人物')),'D139 search "PERSON" matches case-insensitively');
  await page.locator(inp).fill('zzzzz');check(await page.locator(win+' .ui-feat-empty').innerText()==='沒有符合的特徵','D139 no match shows 沒有符合的特徵');
  await page.locator(inp).fill('');check((await chips()).some(t=>t.startsWith('人物')),'D139 clearing the search restores the list');
  await page.locator(win+' .ui-qfeat').evaluate(el=>{el.scrollTop=el.scrollHeight;});
  check((await page.locator(inp).boundingBox()).y===y0&&(await page.locator(win+' #ui-track-start').boundingBox()).y===fy0,'D139 search box stays pinned with the time fields while the list scrolls');}
 await page.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await page.locator('#ui-track-start').fill('13:00:00');await submit('track');
 {/* D143: no dragging needed — the playhead already sits at the first appearance and the stage shows its image */const jumped=await page.waitForFunction(()=>{const i=document.querySelector('.ui-stage-img'),n=document.querySelector('#ui-jump-note');return !!i&&!i.hidden&&i.complete&&i.naturalWidth>0&&!!n&&!n.hidden;},null,{timeout:10000}).then(()=>true,()=>false);check(jumped,'D143 after tracking starts the stage shows a loaded image with no seek');check(await page.locator('.ui-stagebox').getAttribute('data-kind')==='ON_CAMERA','D143 stage is on an ON_CAMERA segment right away');check(Number(await page.locator('#ui-scrub').inputValue())>=200000,'D143 playhead is not at window start (0)');check(/^已跳到第一次出現（\d\d:\d\d:\d\d）$/.test(await page.locator('#ui-jump-note').innerText()),'D143 jump note shows HH:MM:SS');const kinds0=await page.locator('.ui-tl-seg').evaluateAll(n=>n.map(x=>x.dataset.kind));check(kinds0[0]==='PENDING','D143 timeline still shows the unseen start first');}
 await seek(2000000);await page.locator('.ui-burger').click();await page.locator('#ui-track-start').fill('');await submit('track');check(/到錄影結尾（13:00:02）/.test(await page.locator('#ui-track-end').getAttribute('placeholder')),'track end placeholder shows the recording end');
 {const payload=calls('/api/q_core_track').at(-1).payload,range=payload.time?.wall_range??[];check(payload.time?.kind==='WALL'&&!('playback_now_us' in payload)&&/T13:00:00/.test(range[0])&&/T13:00:02/.test(range[1]),'D139 blank track times are sent as concrete recording start and end, never empty');
  check((await page.locator('#ui-track-range').innerText()).includes('13:00:00～13:00:02'),'D139 result shows the queried time range');check(await page.locator('#ui-journal').innerText().then(t=>!t.includes('時間窗內無觀測紀錄')),'D139 blank-time track no longer reports an empty window');}
 for(const [t,kind]of[[300000,'ON_CAMERA'],[800000,'GAP'],[1200000,'ON_CAMERA'],[1800000,'LOST']]){await seek(t);check(await page.locator('.ui-stagebox').getAttribute('data-kind')===kind,'visible '+kind+' state');await shot('05-track-'+t);}
 // D139 frames: inside an OBSERVED segment the stage loads a real image; before the first sighting it is PENDING (not LOST, no "無").
 {const loaded=()=>page.waitForFunction(()=>{const i=document.querySelector('.ui-stage-img');return !!i&&!i.hidden&&i.complete&&i.naturalWidth>0;},null,{timeout:10000}).then(()=>true,()=>false);
  await seek(300000);check(await page.locator('.ui-stagebox').getAttribute('data-kind')==='ON_CAMERA'&&await loaded(),'D139 OBSERVED segment loads a frame image (complete, naturalWidth>0)');
  check(await page.locator('.ui-stage-empty').isHidden(),'D139 no empty-frame note inside an OBSERVED segment');
  await seek(100000);check(await page.locator('.ui-stagebox').getAttribute('data-kind')==='PENDING','D139 before the first sighting the state is PENDING, not LOST');
  await page.waitForFunction(()=>{const i=document.querySelector('.ui-stage-img'),n=document.querySelector('.ui-live-note');return !!i&&!i.hidden&&i.complete&&i.naturalWidth>0&&!!n&&!n.hidden;},null,{timeout:10000});{const note=await page.locator('.ui-live-note').innerText();check(note==='目標尚未出現'&&!/跟丟|無$/.test(note)&&await page.locator('.ui-tag-obs').isHidden(),'D146 before the first sighting the first camera plays, labelled 目標尚未出現 and not observed: '+note);}
  const kinds=await page.locator('.ui-tl-seg').evaluateAll(n=>n.map(x=>x.dataset.kind));check(kinds[0]==='PENDING'&&kinds[1]==='ON_CAMERA','D139 camera timeline draws the unseen start first: '+kinds.join(','));
  await seek(1800000);{await page.waitForFunction(()=>{const h=document.querySelector('.ui-live-note');return h&&!h.hidden;},null,{timeout:10000});const title=await page.locator('.ui-track-title').innerText(),live=await page.locator('.ui-live-note').innerText();check(/已跟丟 · 最後出現在 [A-Z0-9_]+ 鏡頭/.test(title)&&!/無/.test(title),'D146 LOST title names the real camera: '+title);check(/^目標已跟丟，持續播放 [A-Z0-9_]+ 鏡頭$/.test(live)&&await page.locator('.ui-stage-img').isVisible()&&await page.locator('.ui-tag-obs').isHidden(),'D146 LOST keeps playing the last camera live, not labelled observed: '+live);}
  // D139 whole-interface zoom replaces the image-ratio control: text, layout and images scale together; no horizontal scroll; the bar stays at the window bottom.
  await seek(300000);await loaded();
  {const sel='#ui-zoom';check(await page.locator('.ui-fit-ctl').count()===0&&await page.locator('.ui-fit-btn').count()===0,'D139 old image-ratio control (符合/填滿/原始) is gone');
   check(await page.locator(sel).inputValue()==='100'&&(await page.locator(sel+' option').allInnerTexts()).join()==='60%,80%,100%,125%,150%','D147 camera-picture size default 100% with 60/80/100/125/150');
   const heights=[];
   const stages=[];for(const z of [60,80,100,125,150]){await page.locator(sel).selectOption(String(z));await page.waitForTimeout(100);
    const m=await page.evaluate(()=>{const r=n=>document.querySelector(n).getBoundingClientRect(),scr=document.querySelector('.ui-screens'),top=[...document.querySelectorAll('.ui-top-right > *')].filter(n=>n.getClientRects().length).map(n=>n.getBoundingClientRect().right);return {pageH:document.documentElement.scrollWidth>innerWidth,screensH:scr.scrollWidth>scr.clientWidth+1,topRight:Math.max(...top),vw:innerWidth,barBottom:r('#ui-track-bar').bottom,vh:innerHeight,brand:r('.ui-brand').height,stage:r('.ui-stagebox').height};});
    heights.push(m.brand);stages.push(m.stage);check(!m.pageH&&!m.screensH&&m.topRight<=m.vw+0.5,'D147 picture '+z+'% no horizontal scroll (top bar right edge '+Math.round(m.topRight)+' <= '+m.vw+')');check(Math.abs(m.barBottom-m.vh)<2.5,'D147 picture '+z+'% bottom play bar meets the window bottom ('+Math.round(m.barBottom)+' vs '+m.vh+')');}
   check(Math.max(...heights)-Math.min(...heights)<0.5,'D147 text size does not change with the camera-picture size ('+heights.map(h=>Math.round(h)).join('/')+')');
   check(Math.abs(stages[4]/stages[2]-1.5)<0.02&&Math.abs(stages[0]/stages[2]-0.6)<0.02,'D147 camera picture scales 60%..150% (stage height '+stages.map(h=>Math.round(h)).join('/')+')');
   await page.locator(sel).selectOption('125');check(await page.evaluate(()=>localStorage.getItem('amidst.ui.zoom.v1'))==='125'&&await page.evaluate(()=>document.querySelector('#ui-v1').dataset.zoom)==='125','D147 picture size remembered in localStorage');
   await page.reload({waitUntil:'domcontentloaded'});await page.locator('#ui-v1').waitFor();check(await page.evaluate(()=>document.querySelector('#ui-v1').dataset.zoom)==='125','D147 picture size restored after reload');
   await page.evaluate(()=>{try{localStorage.removeItem('amidst.ui.zoom.v1');}catch{}});await page.reload({waitUntil:'domcontentloaded'});await page.locator('#ui-v1').waitFor();check(await page.evaluate(()=>document.querySelector('#ui-v1').dataset.zoom)==='100','D139 cleared storage falls back to 100%');
   await page.locator('#ui-enter').click();await page.locator('[data-case=case2]').click();await page.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await page.locator('#ui-track-start').fill('13:00:00');await submit('track');await page.locator('#ui-scrub').waitFor();await seek(300000);await loaded();}}
 // D139 playback: while playing, every observed moment shows a loaded image and the image URL keeps changing with time (the server answers
 // slowly, so a reply is never back before the playhead has moved on: the old picture stays and the newest wanted frame is fetched next).
 {await seek(200000);await page.waitForFunction(()=>{const i=document.querySelector('.ui-stage-img');return !!i&&!i.hidden&&i.complete&&i.naturalWidth>0;},null,{timeout:10000});await page.locator('#ui-speed').selectOption('0.5');await page.locator('#ui-play').click();
  const samples=await page.evaluate(async()=>{const out=[],t0=performance.now();while(performance.now()-t0<3600){await new Promise(r=>setTimeout(r,120));const i=document.querySelector('.ui-stage-img'),st=document.querySelector('.ui-stagebox'),h=document.querySelector('.ui-live-note');out.push({ms:Math.round(performance.now()-t0),kind:st.dataset.kind,ok:!!i&&!i.hidden&&i.complete&&i.naturalWidth>0,src:i?.getAttribute('src')??'',liveNote:h&&!h.hidden?h.textContent:'',tagHidden:document.querySelector('.ui-tag-obs').hidden,stamp:document.querySelector('.ui-stamp').textContent,cam:(document.querySelector('.ui-stamp').textContent.split(' · ')[0]||'')});}return out;});
  await page.locator('#ui-play').click();
  const warm=samples.filter(x=>x.ms>900&&x.kind!=='PENDING'),observed=warm.filter(x=>x.kind==='ON_CAMERA'),blind=warm.filter(x=>x.kind==='GAP'),urls=new Set(samples.filter(x=>x.ok).map(x=>x.src));
  check(samples.at(-1).ms>=3400&&observed.length>=3,'D139 playback ran 3.4 s+ with '+samples.length+' samples, '+observed.length+' of them while observed (kinds '+[...new Set(samples.map(x=>x.kind))].join('/')+')');
  check(warm.every(x=>x.ok),'D139 during playback every sampled moment has a loaded image (complete, naturalWidth>0): '+warm.filter(x=>!x.ok).map(x=>x.ms+'ms '+x.kind).join(',')+' failed');
  check(urls.size>=4,'D139 playback image URL changes with time: '+urls.size+' different URLs');
  { // D146: the blind interval keeps playing LIVE video of the previous camera: the URL keeps changing and the camera never changes
    const blindUrls=new Set(blind.filter(x=>x.ok).map(x=>x.src)),obsCam=samples.filter(x=>x.kind==='ON_CAMERA'&&x.ms<(blind[0]?.ms??0)).at(-1)?.cam;
    check(blind.length>=3&&blind.every(x=>x.ok&&/^目標暫時不在畫面中，持續播放 [A-Z0-9_]+ 鏡頭$/.test(x.liveNote)&&x.tagHidden),'D146 blind interval plays live with the plain note and no observed tag ('+blind.length+' samples)');
    check(blindUrls.size>=2,'D146 blind interval image URL keeps changing (not frozen): '+blindUrls.size+' URLs');
    check(new Set(blind.map(x=>x.cam)).size===1&&blind[0]?.cam===obsCam,'D146 blind interval stays on the camera of the previous segment: '+blind[0]?.cam+' vs '+obsCam);}
  check(observed.every(x=>x.liveNote==='')&&observed.some(x=>!x.tagHidden),'D146 observed moments carry no blind note and are labelled 已觀測');
  await page.locator('#ui-layout [data-layout=multi]').click();await seek(200000);await page.locator('#ui-play').click();
  const multi=await page.evaluate(async()=>{const out=[],t0=performance.now();while(performance.now()-t0<2400){await new Promise(r=>setTimeout(r,150));const i=document.querySelector('.ui-multi-tile[data-active=true] .ui-img');out.push({ms:Math.round(performance.now()-t0),active:!!i,ok:!!i&&!i.hidden&&i.complete&&i.naturalWidth>0,src:i?.getAttribute('src')??''});}return out;});
  await page.locator('#ui-play').click();await page.locator('#ui-layout [data-layout=single]').click();
  check(multi.filter(x=>x.ms>900&&x.active).length>=3&&multi.filter(x=>x.ms>900&&x.active).every(x=>x.ok)&&new Set(multi.map(x=>x.src)).size>=3,'D139 multi view: the active tile keeps a loaded image while playing, URL changes with time ('+new Set(multi.map(x=>x.src)).size+' URLs)');await page.locator('#ui-speed').selectOption('1');await seek(300000);}
 // D139-3 presentation mode and D139-6 label is asserted in dom-e2e (the synthetic server has no blind estimate).
 await seek(800000);{const t=await page.locator('#ui-case2').innerText();check(!/自動種子|DEMO_DEFAULT|GRAPH_NOT_APPROVED|ASSOCIATION_IDENTITY_UNCONFIRMED|ACTUAL_BLENDER|D124|UNKNOWN|MISSING|INFERRED/.test(t),'D139 no technical tags on the front desk');await page.waitForFunction(()=>{const h=document.querySelector('.ui-live-note'),i=document.querySelector('.ui-stage-img');return h&&!h.hidden&&i&&!i.hidden&&i.complete&&i.naturalWidth>0;},null,{timeout:10000});{const live=await page.locator('.ui-live-note').innerText();check(/^目標暫時不在畫面中，持續播放 [A-Z0-9_]+ 鏡頭$/.test(live)&&await page.locator('.ui-stage-img').isVisible()&&await page.locator('.ui-stage-empty').isHidden()&&await page.locator('.ui-tag-obs').isHidden(),'D146 blind interval keeps playing the previous camera live, not labelled observed: '+live);}
  const icon=page.locator('#ui-case2 .ui-info').first();check(await icon.count()===1,'D139 technical tags collected in one ⓘ');await icon.hover();check(await icon.locator('.ui-info-pop').isVisible()&&(await icon.locator('.ui-info-pop').innerText()).includes('自動種子'),'D139 ⓘ shows the technical tags on hover');await page.mouse.move(5,5);
  check(await page.locator('#ui-blind-end').count()===0,'D139 no reappearance label while still blind');}
 await seek(300000);await page.locator('#ui-play').click();await page.waitForFunction(()=>document.querySelector('.ui-stamp')?.textContent.startsWith('B ·'));await page.locator('#ui-play').click();check(true,'automatic camera switch via visible play control');
 await page.locator('#ui-layout [data-layout=multi]').click();check(await page.locator('.ui-multi-tile').count()===2,'multi two cameras');await page.locator('#ui-speed').selectOption('1.5');check(await page.locator('#ui-speed').inputValue()==='1.5'&&await page.locator('#ui-case2 [data-speed]').count()===0&&await page.locator('#ui-case2 #ui-speed option').count()===4,'one speed dropdown (0.5/1/1.5/2), 1.5x selected');await page.locator('#ui-speed').selectOption('0.5');check(await page.locator('#ui-speed').inputValue()==='0.5','D139 0.5x selectable');await page.locator('#ui-speed').selectOption('1.5');check(await page.locator('#ui-modes [data-mode]').count()===3&&await page.locator('#ui-modes .on').getAttribute('data-mode')==='case2','D139 header mode switch shows three modes, tracking active');check(await page.locator('#ui-case2 .ui-tl-row').count()===1&&await page.locator('#ui-case2 input[type=range]').count()===1,'D139 a single timeline');check(!(await page.locator('#ui-case2').innerText()).includes('設定 1'),'D139 no 設定 1× text');await shot('06-multi');
 const bar=await page.locator('#ui-track-bar').boundingBox();check(Math.abs(bar.y+bar.height-viewportHeight)<2,'short-content bar meets viewport bottom');
 check(await page.locator('#ui-run-select option').count()===3,'three source choices');
 for(const [runId,n]of[['SYNTHETIC_B05',2],['SYNTHETIC_A4_1',3],['SYNTHETIC_B4_1',2]]){
  await page.goto(preview.url+'?run='+runId+'&screen=case1',{waitUntil:'domcontentloaded'});await page.locator('#ui-q-search [data-role=classes] [data-value=person]').click();await submit('search',n);check(calls('/api/q_core_search').at(-1).payload.run_id===runId,'selected search source '+runId);await shot('07-'+runId+'-search');
  await page.goto(preview.url+'?run='+runId+'&screen=case2',{waitUntil:'domcontentloaded'});await page.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await page.locator('#ui-track-start').fill('13:00:00');await submit('track');check(calls('/api/q_core_track').at(-1).payload.run_id===runId,'selected tracking source '+runId);await seek(300000);check(await page.locator('.ui-stagebox').getAttribute('data-kind')==='ON_CAMERA','selected source single state');await page.locator('#ui-layout [data-layout=multi]').click();check(await page.locator('.ui-multi-tile').count()===n,'selected source multi count');await shot('08-'+runId+'-multi');
 }
 {await page.goto(preview.url+'?run=SYNTHETIC_B05&screen=case1',{waitUntil:'domcontentloaded'});await page.locator('#ui-q-search [data-role=classes] [data-value=person]').click();await submit('search',2);
  await page.locator('#ui-case1 .ui-shot').first().click();await page.locator('#ui-zoom').selectOption('150');check(await page.locator('.ui-lightbox').isVisible()&&await page.locator('.ui-lb-img').evaluate(i=>{const r=i.getBoundingClientRect();return r.right<=innerWidth&&r.bottom<=innerHeight;}),'D147 enlarged view fits the window at 150% picture size');await page.locator('#ui-zoom').selectOption('100');
  await page.goto(preview.url+'?run=SYNTHETIC_B05&screen=case3',{waitUntil:'domcontentloaded'});check(await page.locator('#ui-zoom').count()===1&&await page.locator('#ui-case3 .ui-fit-ctl').count()===0,'D147 monitor wall (case3) has the camera-picture size control and no image-ratio control');}
 check(iconRequests.length===0,'D139 no /favicon.ico request (page declares its icon)');
 {await page.goto(new URL('admin.html',preview.url).toString(),{waitUntil:'domcontentloaded'});check(await page.locator('link[rel=icon]').count()===1,'D139 admin declares an icon');await page.locator('a.ui-side-brand').click();await page.locator('#ui-v1').waitFor();await page.waitForFunction(()=>document.querySelector('#ui-v1')?.dataset.screen);check(/\/workbench-v2\/(index\.html)?$/.test(new URL(page.url()).pathname)&&await page.locator('#ui-v1').getAttribute('data-screen')==='cover','D139 admin Amidst brand returns to the front-desk cover');check(iconRequests.length===0,'D139 still no /favicon.ico request after admin');}
 check(errors.length===0,'no browser page errors');
 result={status:'PASS',checks,viewport:{width:1440,height:viewportHeight},bar_rect:bar,source_head:preview.head,url:preview.url,screenshots:shots,page_errors:errors,source_kind:'SYNTHETIC API FIXTURE',physical_display_fps:null};
}finally{
 try {
  await page.unrouteAll({behavior:'ignoreErrors'});
  await page.context().close();
  await browser.close();
 } finally {
  await new Promise((done,reject)=>{preview.server.close(e=>e?reject(e):done());preview.server.closeAllConnections?.();});
 }
}
// PASS is emitted only after context, browser and owned HTTP server have closed.
await writeFile(join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));

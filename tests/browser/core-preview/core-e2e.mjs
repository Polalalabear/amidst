// Synthetic API conformance through the redesigned visible front desk.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {startPreview} from './preview-server.mjs';
const source=process.env.CORE_SOURCE;const VIEWPORT_H=Number(process.env.VIEWPORT_H??1000);if(![900,1000,1300].includes(VIEWPORT_H))throw Error('VIEWPORT_H must be 900, 1000 or 1300');if(!source)throw Error('CORE_SOURCE_REQUIRED');
const {chromium}=await import(process.env.PLAYWRIGHT_CORE_MODULE?pathToFileURL(process.env.PLAYWRIGHT_CORE_MODULE).href:'playwright-core');
const out=process.env.SCREENSHOT_DIR??join(tmpdir(),'amidst-new-ui-synthetic');await mkdir(out,{recursive:true});
const preview=await startPreview({source,port:0}),browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
const page=await browser.newPage({viewport:{width:1440,height:VIEWPORT_H},deviceScaleFactor:1}),errors=[],shots=[];let checks=0;
const check=(ok,msg)=>{assert.ok(ok,msg);checks++;console.log(JSON.stringify({check:checks,message:msg}));};page.on('pageerror',e=>errors.push(String(e)));
const shot=async name=>{const path=join(out,name+'.png');await page.screenshot({path,fullPage:true});const b=await readFile(path);shots.push({path,bytes:b.length,sha256:createHash('sha256').update(b).digest('hex')});};
const calls=route=>preview.routeCalls.filter(c=>c.route===route);
const open=async kind=>{if(await page.locator('#ui-q-'+kind).getAttribute('data-open')!=='true')await page.locator('.ui-burger').click();};
const submit=async(kind,n)=>{await open(kind==='search'?'search':'track');const resp=page.waitForResponse(r=>r.url().endsWith('/api/q_core_'+kind)&&r.request().method()==='POST');await page.locator('#ui-'+kind+'-submit').click();await resp;if(kind==='search')await page.waitForFunction(n=>document.querySelectorAll('#ui-case1 .ui-shot').length===n,n);else await page.locator('#ui-scrub').waitFor();};
const seek=async t=>{await page.locator('#ui-scrub').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input',{bubbles:true}));},t);check(Number(await page.locator('#ui-scrub').inputValue())===t,'seek value preserved');};
const feature=async value=>{const b=page.locator('#ui-q-search [data-role=classes] [data-value="'+value+'"]');if(await b.getAttribute('aria-pressed')!=='true')await b.click();};
try{
 await page.goto(preview.url,{waitUntil:'domcontentloaded'});await page.locator('#ui-enter').waitFor();
 check(await page.locator('#synthetic-api-banner').isVisible(),'synthetic banner visible above new UI');check((await page.locator('.ui-tagline').innerText()).includes('Agentic'),'approved cover tagline');await shot('00-cover');
 await page.locator('#ui-enter').click();await page.locator('[data-case=case1]').click();await page.locator('#ui-q-search [data-role=regions] button').first().waitFor();
 const initial=calls('/api/q_core_search').length;
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
 const handle=await page.locator('#ui-case1 .ui-shot img').first().elementHandle();await page.locator('#ui-case1 .ui-shot').first().click();check(await handle.evaluate(img=>img.isConnected),'selection retains image node');check(await page.locator('.ui-lightbox').isVisible(),'new UI lightbox');await page.getByRole('button',{name:'回到結果牆'}).click();
 await page.locator('.ui-brand').click();await page.locator('#ui-enter').click();await page.locator('[data-case=case2]').click();await page.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await page.locator('#ui-track-start').fill('13:00:00');await submit('track');await seek(2000000);await page.locator('#ui-context').click();await page.locator('#ui-track-start').fill('');await submit('track');check(calls('/api/q_core_track').at(-1).payload.playback_now_us===2000000,'track now uses visible source clock');
 for(const [t,kind]of[[300000,'ON_CAMERA'],[800000,'GAP'],[1200000,'ON_CAMERA'],[1800000,'LOST']]){await seek(t);check(await page.locator('.ui-stagebox').getAttribute('data-kind')===kind,'visible '+kind+' state');await shot('05-track-'+t);}
 await seek(300000);await page.locator('#ui-play').click();await page.waitForFunction(()=>document.querySelector('.ui-stamp')?.textContent.startsWith('B ·'));await page.locator('#ui-play').click();check(true,'automatic camera switch via visible play control');
 await page.locator('#ui-layout [data-layout=multi]').click();check(await page.locator('.ui-multi-tile').count()===2,'multi two cameras');await page.locator('#ui-case2 [data-speed="1.5"]').click();check(await page.locator('#ui-case2 [data-speed="1.5"]').getAttribute('aria-pressed')==='true','visible speed selected');await shot('06-multi');
 const bar=await page.locator('#ui-track-bar').boundingBox();const vp=page.viewportSize().height,scroller=await page.locator('.ui-screens').evaluate(e=>({sh:e.scrollHeight,ch:e.clientHeight}));check(bar.y+bar.height<=vp+2&&bar.y>=0,'bar stays inside viewport at '+vp);if(scroller.sh<=scroller.ch+1)check(Math.abs(bar.y+bar.height-vp)<2,'short-content bar meets viewport bottom at '+vp);else check(await page.locator('#ui-track-bar').evaluate(b=>{const r=b.getBoundingClientRect(),q=document.elementFromPoint(r.left+r.width/2,r.bottom-4);return b.contains(q);}),'long content: bar not covered at '+vp);
 check(await page.locator('#ui-run-select option').count()===3,'three source choices');
 for(const [runId,n]of[['SYNTHETIC_B05',2],['SYNTHETIC_A4_1',3],['SYNTHETIC_B4_1',2]]){
  await page.goto(preview.url+'?run='+runId+'&screen=case1',{waitUntil:'domcontentloaded'});await page.locator('#ui-q-search [data-role=classes] [data-value=person]').click();await submit('search',n);check(calls('/api/q_core_search').at(-1).payload.run_id===runId,'selected search source '+runId);await shot('07-'+runId+'-search');
  await page.goto(preview.url+'?run='+runId+'&screen=case2',{waitUntil:'domcontentloaded'});await page.locator('#ui-q-track [data-role=classes] [data-value=person]').click();await page.locator('#ui-track-start').fill('13:00:00');await submit('track');check(calls('/api/q_core_track').at(-1).payload.run_id===runId,'selected tracking source '+runId);await seek(300000);check(await page.locator('.ui-stagebox').getAttribute('data-kind')==='ON_CAMERA','selected source single state');await page.locator('#ui-layout [data-layout=multi]').click();check(await page.locator('.ui-multi-tile').count()===n,'selected source multi count');await shot('08-'+runId+'-multi');
 }
 check(errors.length===0,'no browser page errors');
 const result={status:'PASS',checks,source_head:preview.head,url:preview.url,screenshots:shots,page_errors:errors,source_kind:'SYNTHETIC API FIXTURE',physical_display_fps:null};await writeFile(join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close();await new Promise((done,reject)=>preview.server.close(e=>e?reject(e):done()));}

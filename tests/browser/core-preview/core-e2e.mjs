import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {startPreview} from './preview-server.mjs';

const source=process.env.CORE_SOURCE;
if(!source)throw Error('CORE_SOURCE_REQUIRED');
const moduleId=process.env.PLAYWRIGHT_CORE_MODULE;
const {chromium}=await import(moduleId?pathToFileURL(moduleId).href:'playwright-core');
const screenshotDir=process.env.SCREENSHOT_DIR??join(tmpdir(),'amidst-459-screenshots');
const browserOptions={headless:true};
if(process.env.CHROME_EXECUTABLE)browserOptions.executablePath=process.env.CHROME_EXECUTABLE;
const preview=await startPreview({source,port:0});
const browser=await chromium.launch(browserOptions);
const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
const pageErrors=[],shots=[];page.on('pageerror',error=>pageErrors.push(String(error)));
await mkdir(screenshotDir,{recursive:true});
const shot=async name=>{const path=join(screenshotDir,name+'.png');await page.screenshot({path,fullPage:true});const hash=createHash('sha256').update(await readFile(path)).digest('hex');shots.push({path,sha256:hash});};
const feedback=()=>page.locator('#q-core-feedback').innerText();
const awaitFeedback=async phrase=>{await page.waitForFunction(value=>document.querySelector('#q-core-feedback')?.textContent?.includes(value),phrase);};
const seek=async t=>page.locator('#q-scrub').evaluate((element,value)=>{element.value=String(value);element.dispatchEvent(new Event('input',{bubbles:true}));},t);
const coreSearch=async expected=>{const response=page.waitForResponse(r=>r.url().endsWith('/api/q_core_search')&&r.request().method()==='POST');await page.locator('#q-core-search').click();await response;await page.waitForFunction(n=>document.querySelector('#q-core-feedback')?.textContent?.includes('查找回應：READY')&&document.querySelectorAll('#core-search-wall-slot .q-core-card').length===n,expected);};
let checks=0;const check=(value,message)=>{assert.ok(value,message);checks++;};
try{
  await page.goto(preview.url,{waitUntil:'networkidle'});
  await page.locator('#q-core-region:not([disabled])').waitFor();
  check((await page.locator('#synthetic-api-banner').innerText()).includes('SYNTHETIC API FIXTURE'),'fixed synthetic banner');
  check((await page.locator('#q-origin').innerText()).includes('SYNTHETIC'),'source badge synthetic');

  // Contract field errors must stay in the normal control flow without a route request.
  const initialCalls=preview.routeCalls.filter(c=>c.route==='/api/q_core_search').length;
  await page.locator('#q-core-search').click();await awaitFeedback('地點區域與特徵至少需提供一項');
  check(preview.routeCalls.filter(c=>c.route==='/api/q_core_search').length===initialCalls,'empty search sends no request');
  await page.locator('#q-core-class').selectOption('person');await page.locator('#q-core-search').click();await awaitFeedback('請輸入時間範圍');
  check(preview.routeCalls.filter(c=>c.route==='/api/q_core_search').length===initialCalls,'missing time sends no request');
  await page.locator('#q-core-start').fill('13:00:00');await page.locator('#q-core-end').fill('13:00:02');

  // Three menu combinations use real controls and the validated API client.
  await page.locator('#q-core-class').selectOption('');
  await page.locator('#q-core-region').selectOption(['SYNTHETIC_ROOM_A']);
  await coreSearch(1);
  check((await page.locator('#core-search-wall-slot .q-core-card').count())===1,'location only one camera');check(await page.locator('#core-search-wall-slot').isVisible(),'search result visible above monitor wall');
  check(preview.routeCalls.filter(c=>c.route==='/api/q_core_search').at(-1).payload.feature===null,'location only feature null');
  await shot('01-location-only');

  await page.locator('#q-core-region').selectOption([]);
  await page.locator('#q-core-class').selectOption('person');
  await coreSearch(2);
  check((await page.locator('#core-search-wall-slot .q-core-card').count())===2,'feature only two cameras');
  check(preview.routeCalls.filter(c=>c.route==='/api/q_core_search').at(-1).payload.region_ids.length===0,'feature only no region');
  await shot('02-feature-only');

  await page.locator('#q-core-region').selectOption(['SYNTHETIC_ROOM_A']);
  await coreSearch(1);
  check((await page.locator('#core-search-wall-slot .q-core-card').count())===1,'combined one camera');
  check(preview.routeCalls.filter(c=>c.route==='/api/q_core_search').at(-1).payload.feature?.class_label==='person','combined feature');
  await shot('03-location-and-feature');

  // A route failure must be shown as an error; it must not keep a success wall.
  await page.route('**/api/q_core_search',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error_code:'Q_RESOURCE_UNAVAILABLE'})}));
  await page.locator('#q-core-search').click();await awaitFeedback('Q_RESOURCE_UNAVAILABLE');
  check(await page.locator('#core-search-wall-slot').getAttribute('hidden')!==null,'failed search clears wall');
  await shot('04-route-unavailable');
  await page.unroute('**/api/q_core_search');

  // Two overlapping requests: the late first response must not replace the later result.
  let intercepted=0;
  await page.route('**/api/q_core_search',async route=>{intercepted++;if(intercepted===1)await new Promise(r=>setTimeout(r,250));await route.continue();});
  await page.locator('#q-core-search').click();await page.waitForTimeout(20);await page.locator('#q-core-region').selectOption([]);await page.locator('#q-core-search').click();
  await awaitFeedback('查找回應：READY');await page.waitForTimeout(300);
  check(intercepted===2,'two browser requests issued');
  check((await page.locator('#core-search-wall-slot .q-core-card').count())===2,'late response did not corrupt wall');
  await page.unroute('**/api/q_core_search');

  // Track at the source clock's current point, then inspect the four single-view states.
  await page.locator('#q-core-region').selectOption([]);
  await page.locator('#q-core-start').fill('');await page.locator('#q-core-end').fill('');
  await seek(2000000);await page.locator('#q-core-track').click();await awaitFeedback('追蹤回應：LOST');
  check(preview.routeCalls.filter(c=>c.route==='/api/q_core_track').at(-1).payload.playback_now_us===2000000,'track now uses displayed source clock');
  for(const [t,camera,kind,name] of [[300000,'A','ON_CAMERA','05-track-a'],[800000,'無畫面（盲區／遺失）','GAP','06-track-gap'],[1200000,'B','ON_CAMERA','07-track-b'],[1800000,'無畫面（盲區／遺失）','LOST','08-track-lost']]){
    await seek(t);
    check((await page.locator('#core-tracking-slot .q-core-active-cam-id').innerText())===camera,`${kind} camera`);
    check((await page.locator('#core-tracking-slot .q-core-segment-badge').getAttribute('data-kind'))===kind,`${kind} state`);
    await shot(name);
  }
  await seek(200000);await page.locator('#q-play').click();await page.waitForFunction(()=>document.querySelector('.q-core-active-cam-id')?.textContent==='B');await page.locator('#q-play').click();check((await page.locator('#q-core-rate').innerText()).includes('實際'),'actual synthetic clock rate displayed');
  await page.locator('#core-tracking-slot [data-mode="multi"]').click();
  check((await page.locator('#core-tracking-slot .q-core-multi-cam-tile').count())===2,'multi-view two cameras');
  await page.locator('#core-tracking-slot [data-speed="1.5"]').click();
  check((await page.locator('#core-tracking-slot [data-speed="1.5"]').getAttribute('aria-pressed'))==='true','1.5x speed setting');
  check(await page.locator('#q-speed').inputValue()==='1.5','global speed agrees with core control');
  await seek(200000);await page.locator('#q-play').click();await page.waitForFunction(()=>document.querySelector('#q-core-rate')?.textContent?.includes('1.5'));await page.waitForTimeout(400);await page.locator('#q-play').click();
  await shot('09-track-multi');
  await page.locator('#view-seg [data-view="simple"]').click();
  check((await page.locator('body').getAttribute('data-view'))==='simple','simple view mode');
  await shot('10-simple-view');
  await page.locator('#view-seg [data-view="system"]').click();
  check((await page.locator('body').getAttribute('data-view'))==='system','system view restored');
  // Use the actual source menu for all three explicitly synthetic events.
  check(await page.locator('#q-run option').count()===3,'three synthetic event scopes');
  for(const [index,runId,count] of [['0','SYNTHETIC_B05',2],['1','SYNTHETIC_A4_1',3],['2','SYNTHETIC_B4_1',2]]){
    await page.locator('#q-run').selectOption(index);
    await page.waitForFunction(id=>document.querySelector('#q-source-state')?.textContent?.includes(id),runId);
    check(await page.locator('#core-search-wall-slot').getAttribute('hidden')!==null,'event switch clears old results '+runId);
    await page.locator('#q-core-region:not([disabled])').waitFor();
    await page.locator('#q-core-region').selectOption([]);await page.locator('#q-core-class').selectOption('person');
    await page.locator('#q-core-start').fill('13:00:00');await page.locator('#q-core-end').fill('13:00:02');
    await coreSearch(count);
    check(preview.routeCalls.filter(c=>c.route==='/api/q_core_search').at(-1).payload.run_id===runId,'search uses selected event '+runId);
    check(await page.locator('#core-search-wall-slot').isVisible(),'event search visible '+runId);
    await shot('11-'+runId+'-search');
    await page.locator('#q-core-track').click();await awaitFeedback('追蹤回應：LOST');
    check(preview.routeCalls.filter(c=>c.route==='/api/q_core_track').at(-1).payload.run_id===runId,'track uses selected event '+runId);
    await page.locator('#core-tracking-slot [data-mode="single"]').click();await seek(300000);
    check(await page.locator('#core-tracking-slot .q-core-active-cam-id').innerText()==='A','event single view '+runId);
    await page.locator('#core-tracking-slot [data-mode="multi"]').click();
    check(await page.locator('#core-tracking-slot .q-core-multi-cam-tile').count()===count,'event multi camera count '+runId);
    await shot('12-'+runId+'-track-multi');
  }
  check(pageErrors.length===0,'no browser page errors: '+pageErrors.join('; '));
  console.log(JSON.stringify({status:'PASS',checks,source_head:preview.head,url:preview.url,screenshots:shots,not_verified:['Windows','Linux','real RGB','physical display fps; measured rate is the synthetic source clock only']},null,2));
}finally{await browser.close();await new Promise((done,reject)=>preview.server.close(error=>error?reject(error):done()));}

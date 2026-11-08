import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {ownedRuntime} from './owned-runtime.mjs';
const owned=ownedRuntime();
const moduleId=process.env.PLAYWRIGHT_CORE_MODULE??owned.playwrightModule;
const baseUrl=process.env.CORE_BASE_URL??'http://127.0.0.1:8785';
const {chromium}=await import(pathToFileURL(moduleId).href);
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const out=process.env.INTEGRATION_OUTPUT??owned.evidenceRoot+'/real';await mkdir(out+'/screenshots',{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const page=await browser.newPage({viewport:{width:1600,height:1100},deviceScaleFactor:1});
await page.addInitScript(()=>localStorage.clear());
const errors=[],http=[],results=[],playbacks=[];let checks=0;const check=(x,msg)=>{assert.ok(x,msg);checks++;};
page.on('pageerror',e=>errors.push(String(e)));
page.on('response',r=>{if(r.url().includes('/api/')&&r.status()!==200)http.push({status:r.status(),path:new URL(r.url()).pathname});});
const shot=async(name,extra={})=>{await page.screenshot({path:out+'/screenshots/'+name+'.png',fullPage:true});const b=await readFile(out+'/screenshots/'+name+'.png'); const row={name,url:page.url(),sha256:createHash('sha256').update(b).digest('hex'),bytes:b.length,...extra};results.push(row); console.log(JSON.stringify(row));};
const seek=async t=>{await page.locator('#q-scrub').evaluate((el,t)=>{el.value=String(t);el.dispatchEvent(new Event('input',{bubbles:true}));},t);};
try{
for(const event of ['B-05','A4-1','B4-1']){
  await page.goto(baseUrl+'/workbench-v2/?run='+event,{waitUntil:'domcontentloaded'});
  await page.locator('#q-core-class option[value=person]').waitFor({state:'attached'});
  await page.waitForFunction(()=>document.querySelectorAll('.mr-tile[data-status="READY"]').length>0,{timeout:30000});
  await page.locator('.mr-toggle').click();
  check(await page.locator('.mr-tile[data-status=READY]').count()===({'B-05':2,'A4-1':4,'B4-1':5})[event],event+' RGB view count');
  await shot(event+'-view',{readyTiles:await page.locator('.mr-tile[data-status="READY"]').count(),source:await page.locator('#q-source-state').innerText()});
  const search=page.waitForResponse(r=>r.url().endsWith('/api/q_core_search')&&r.request().method()==='POST');
  await page.locator('#q-core-class').selectOption('person');
  const times=event==='B-05'?['13:00:00','13:00:08']:event==='A4-1'?['14:00:00','14:00:50']:['14:10:00','14:10:42'];
  await page.locator('#q-core-start').fill(times[0]);await page.locator('#q-core-end').fill(times[1]);await page.locator('#q-core-search').click();
  const sr=await search,sd=await sr.json();await page.waitForTimeout(700);check(sr.status()===200&&sd.hits?.length>0,event+' real search');check((await page.locator('#q-core-feedback').innerText()).includes(sd.status),event+' visible search');
  await page.waitForFunction(()=>{const xs=[...document.querySelectorAll('#core-search-wall-slot img')];return xs.length>0&&xs.every(x=>x.naturalWidth>0);});
  check(await page.locator('#core-search-wall-slot img').evaluateAll(xs=>xs.every(x=>x.naturalWidth>0)),event+' decoded search RGB');
  await shot(event+'-search',{http:sr.status(),status:sd.status,reasons:sd.reasons,hits:sd.hits?.length,feedback:await page.locator('#q-core-feedback').innerText(),images:await page.locator('#core-search-wall-slot img').count()});
  const track=page.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST');
  await page.locator('#q-core-track').click();const tr=await track,td=await tr.json();await page.waitForTimeout(200);check(tr.status()===200&&td.sightings?.length>0,event+' real track');check(td.single_view.some(s=>s.kind==='GAP')&&td.single_view.some(s=>s.kind==='LOST'),event+' missing intervals preserved');check(td.sightings.every(s=>s.range_us[1]<=td.as_of_us),event+' as-of bound');
  if(td.sightings?.length){const first=td.sightings[0];await seek(first.range_us[0]+Math.floor((first.range_us[1]-first.range_us[0])/2));}
  await page.waitForTimeout(700);
  await page.waitForFunction(()=>{const xs=[...document.querySelectorAll('#core-tracking-slot img')];return xs.length>0&&xs.every(x=>x.naturalWidth>0);});
  check(await page.locator('#core-tracking-slot img').evaluateAll(xs=>xs.length>0&&xs.every(x=>x.naturalWidth>0)),event+' decoded single RGB');
  await shot(event+'-track-single',{http:tr.status(),status:td.status,reasons:td.reasons,sightings:td.sightings?.length,blind:td.blind?.status,feedback:await page.locator('#q-core-feedback').innerText(),images:await page.locator('#core-tracking-slot img').count(),single_view:td.single_view});
  const firstCamera=td.single_view.find(s=>s.kind==='ON_CAMERA')?.camera_id;
  const nextIndex=td.single_view.findIndex(s=>s.kind==='ON_CAMERA'&&s.camera_id!==firstCamera);
  if(nextIndex>0){
    const previous=td.single_view.slice(0,nextIndex).filter(s=>s.kind==='ON_CAMERA').at(-1),next=td.single_view[nextIndex];
    await seek(Math.max(previous.range_us[0],previous.range_us[1]-200000));
    for(const speed of ['1','1.5','2']){await page.locator('#core-tracking-slot [data-speed="'+speed+'"]').click();check(await page.locator('#q-speed').inputValue()===speed,event+' source speed '+speed);}
    await page.locator('#q-play').click();
    await page.waitForFunction(camera=>document.querySelector('#core-tracking-slot .q-core-active-cam-id')?.textContent===camera,next.camera_id,{timeout:15000});
    playbacks.push({event,camera:next.camera_id,source_time:await page.locator('#q-time').innerText(),speed_note:await page.locator('#q-speed-note').innerText()});
    await page.locator('#q-play').click();
    check(true,event+' automatic camera switch over missing interval');
    await page.waitForFunction(()=>document.querySelector('#core-tracking-slot img')?.naturalWidth>0);
    check(true,event+' decoded destination RGB');
  }else throw Error(event+' no cross-camera switch');
  const multi=page.locator('#core-tracking-slot [data-mode="multi"]');
  if(await multi.count())await multi.click();await page.waitForTimeout(700);
  await page.waitForFunction(()=>{const xs=[...document.querySelectorAll('#core-tracking-slot img')];return xs.length===2&&xs.every(x=>x.naturalWidth>0);});
  check(await page.locator('#core-tracking-slot .q-core-multi-cam-tile').count()===2,event+' two found cameras');check(await page.locator('#core-tracking-slot img').evaluateAll(xs=>xs.length===2&&xs.every(x=>x.naturalWidth>0)),event+' decoded multi RGB');
  await shot(event+'-track-multi',{tiles:await page.locator('#core-tracking-slot .q-core-multi-cam-tile').count(),images:await page.locator('#core-tracking-slot img').count()});
  await writeFile(out+'/'+event+'-search.json',JSON.stringify(sd,null,2));await writeFile(out+'/'+event+'-track.json',JSON.stringify(td,null,2));
}
for(const [event,stamp] of [['B-05',3000000],['A4-1',9400000],['B4-1',2100000]]){
await page.goto(baseUrl+'/workbench-v2/?run='+event+'&screen=blind&as_of_us='+stamp,{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>document.querySelector('#q-core-feedback')?.textContent.includes('追蹤回應：'));await page.waitForTimeout(700);
const curves=await page.locator('#core-tracking-slot polyline').count();
if(event!=='B-05')check(curves>0,event+' actual-index blind curve');
await shot(event+'-blind',{feedback:await page.locator('#q-core-feedback').innerText(),curves,text:(await page.locator('#core-tracking-slot').innerText()).slice(0,1800)});
}
for(const [name,q]of[['r005-location','region=R101'],['r005-laptop','class=laptop']]){
await page.goto(baseUrl+'/workbench-v2/?run=r005&screen=search&'+q,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>document.querySelector('#q-core-feedback')?.textContent.includes('查找回應：'));await page.waitForTimeout(700);
check(await page.locator('#core-search-wall-slot .q-core-card').count()===(name==='r005-location'?1:2),name+' actual search cards');
await page.waitForFunction(()=>{const xs=[...document.querySelectorAll('#core-search-wall-slot img')];return xs.length>0&&xs.every(x=>x.naturalWidth>0);});
check(await page.locator('#core-search-wall-slot img').evaluateAll(xs=>xs.length>0&&xs.every(x=>x.naturalWidth>0)),name+' decoded static RGB');
await shot(name,{feedback:await page.locator('#q-core-feedback').innerText(),cards:await page.locator('#core-search-wall-slot .q-core-card').count(),images:await page.locator('#core-search-wall-slot img').count(),regions:await page.locator('#q-core-region option').allTextContents()});
}
check(errors.length===0,'no page errors');check(http.length===0,'no failed API responses');
}finally{
await writeFile(out+'/browser-results.json',JSON.stringify({checks,results,playbacks,errors,http},null,2));console.log(JSON.stringify({checks,errors,http}));await browser.close();
}

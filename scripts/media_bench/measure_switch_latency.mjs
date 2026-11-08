import {readFile,writeFile,mkdir,statfs} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {probe} from './browser_probe.mjs';
const args=Object.fromEntries(process.argv.slice(2).map(x=>x.replace(/^--/,'').split('=',2)));
const {chromium}=await import(pathToFileURL(args.playwright));
const toolPins={};for(const name of ['measure_switch_latency.mjs','browser_probe.mjs'])toolPins[name]=createHash('sha256').update(await readFile(new URL(name,import.meta.url))).digest('hex');
async function disk(){const s=await statfs(path.dirname(args.output));if(s.bavail*s.bsize<8*1024**3)throw Error('DISK_BELOW_8_GIB');}await disk();
const recordingRaw=await readFile(args.recording),recordingPin=createHash('sha256').update(recordingRaw).digest('hex');
if(recordingPin!=='ffe5e693a80031e707cddb531925cb97bc6d8295b69777ad3afa1d885bd5a55a')throw Error('EXACT_B05B_RECORDING_REQUIRED');
const recorded=JSON.parse(recordingRaw),response=typeof recorded.response==='string'?JSON.parse(recorded.response):recorded.response;
const change=response.timeline.find(s=>s.kind==='ON_CAMERA'&&s.entered_by==='SWITCH');
const observed=change.observation_ids.map(id=>recorded.observations[id]).sort((a,b)=>a.timestamp_us-b.timestamp_us)[0];
await mkdir(args.output,{recursive:false});
const headful=args.visible==='true';
const browser=await chromium.launch({headless:!headful,executablePath:args.chrome,args:['--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']});
const trials=[];const count=Number(args.repeats??30);
const quantile=(v,p)=>v.length?[...v].sort((a,b)=>a-b)[Math.ceil(p*v.length)-1]:null;
const median=v=>{if(!v.length)return null;const a=[...v].sort((x,y)=>x-y),i=Math.floor(a.length/2);return a.length%2?a[i]:(a[i-1]+a[i])/2;};
try{
 for(const kind of (args.profiles??'legacy,core').split(','))for(let i=0;i<count;i++){
  await disk();
  const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});await context.addInitScript(probe,{kind});
  const page=await context.newPage();if(headful)await page.bringToFront();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  let target;
  if(kind==='legacy'){
   await page.goto('http://127.0.0.1:8781/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938',{waitUntil:'domcontentloaded'});
   await page.locator('.q2-screen .q2-media img').first().waitFor({state:'visible'});
   target={sourceUs:observed.timestamp_us,camera:observed.camera_id,frame:Number(observed.frame_ref.split(':').at(-1))};
  }else{
   await page.goto('http://127.0.0.1:8765/workbench-v2/',{waitUntil:'networkidle'});
   await page.locator('#q-core-class').selectOption('person');await page.locator('#q-core-start').fill('13:00:00');await page.locator('#q-core-end').fill('13:00:02');
   const received=page.waitForResponse(r=>r.url().endsWith('/api/q_core_track')&&r.request().method()==='POST');await page.locator('#q-core-track').click();const data=await (await received).json();
   await page.waitForFunction(()=>document.querySelector('.q-core-active-cam-id'));
   const first=data.sightings[0],next=data.sightings.find(s=>s.camera_id!==first.camera_id);
   target={sourceUs:next.range_us[0],camera:next.camera_id,frame:null};
  }
  await page.locator('#q-speed').selectOption('1');
  await page.locator('#q-scrub').evaluate((node,time)=>{node.value=String(time);node.dispatchEvent(new Event('input',{bubbles:true}));},target.sourceUs-(kind==='legacy'?50000:200000));
  if(kind==='legacy')await page.waitForFunction(()=>[...document.querySelectorAll('.q2-screen .q2-media')].filter(n=>getComputedStyle(n).visibility!=='hidden').every(n=>n.dataset.status==='READY'));
  await page.evaluate(t=>{Object.assign(window.__mediaBench,{targetSourceUs:t.sourceUs,targetCamera:t.camera,targetFrame:t.frame});window.__mediaBench.begin();},target);
  await page.locator('#q-play').click();
  let timeout=false;try{await page.waitForFunction(()=>window.__mediaBench.completeAt!==null,{},{timeout:10000});}catch{timeout=true;}
  if(kind==='legacy'&&!timeout){try{await page.waitForFunction(()=>window.__mediaBench.nativeCompleteAt!==null,{},{timeout:1000});}catch{}}
  await page.locator('#q-play').click();
  const raw=await page.evaluate(()=>({...window.__mediaBench,begin:undefined}));
  const renderMs=raw.completeAt!==null&&raw.availabilityAt!==null?raw.completeAt-raw.availabilityAt:null;
  const nativeMs=raw.nativeCompleteAt!==null?raw.nativeCompleteAt-raw.availabilityAt:null;
  const row={kind,repeat:i+1,target,availability_wall_ms:raw.availabilityAt,decoded_visible_wall_ms:raw.completeAt,native_paint_wall_ms:raw.nativeCompleteAt,
   render_ready_latency_ms:renderMs,native_image_paint_latency_ms:nativeMs===null?null:Math.max(0,nativeMs),coarse_native_negative:nativeMs!==null&&nativeMs<0,
   timeout,page_errors:errors,metric:kind==='legacy'?'recorded observation frame availability at replay clock -> matching new camera PNG rendered; no detector execution':'SYNTHETIC fixture state -> schematic image ready; not real camera latency'};
  await writeFile(path.join(args.output,`${kind}-${String(i+1).padStart(2,'0')}.json`),JSON.stringify({summary:row,raw},null,2));
  if(i===0||i===count-1)await page.screenshot({path:path.join(args.output,`${kind}-${i+1}.png`),fullPage:true});
  trials.push(row);console.log(JSON.stringify(row));await context.close();
 }
 const summary={browser:await browser.version(),node:process.version,hardware:{platform:os.platform(),release:os.release(),arch:os.arch(),cpu:os.cpus()[0].model,logical_cpus:os.cpus().length,memory_bytes:os.totalmem()},executed_tool_sha256:toolPins,headful,recording_sha256:recordingPin,source_appearance_basis:'first matching source observation referenced by recorded switch segment; unlabelled earlier pixel appearance UNKNOWN',
  profiles:['legacy','core'].map(kind=>{const rows=trials.filter(t=>t.kind===kind),ready=rows.map(t=>t.render_ready_latency_ms).filter(t=>t!==null),native=rows.map(t=>t.native_image_paint_latency_ms).filter(t=>t!==null);return {kind,trials:rows.length,timeouts:rows.filter(r=>r.timeout).length,ready_n:ready.length,ready_median_ms:median(ready),ready_p90_ms:quantile(ready,.9),native_n:native.length,native_median_ms:median(native),native_p90_ms:quantile(native,.9)};}),trials};
 await writeFile(path.join(args.output,'summary.json'),JSON.stringify(summary,null,2));
}finally{await browser.close();}

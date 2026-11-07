import {readFile,writeFile,mkdir,statfs} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {probe} from './browser_probe.mjs';
const options=Object.fromEntries(process.argv.slice(2).map(x=>x.replace(/^--/,'').split('=',2)));
const {chromium}=await import(pathToFileURL(options.playwright));
const manifestRaw=await readFile(options.manifest),manifest=JSON.parse(manifestRaw);
const toolPins={};for(const name of ['measure_playback.mjs','browser_probe.mjs'])toolPins[name]=createHash('sha256').update(await readFile(new URL(name,import.meta.url))).digest('hex');
async function disk(){const s=await statfs(path.dirname(options.output));if(s.bavail*s.bsize<8*1024**3)throw Error('DISK_BELOW_8_GIB');}
await disk();
await mkdir(options.output,{recursive:false});
const headful=options.visible==='true';
const browser=await chromium.launch({headless:!headful,executablePath:options.chrome,args:['--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']});
const rows=[];const quantile=(a,p)=>a.length?[...a].sort((x,y)=>x-y)[Math.ceil(p*a.length)-1]:null;
try{
 for(const [ci,c] of manifest.cases.entries())for(const [si,speed] of [1,1.5,2].entries()){
  for(const format of ['png','jpeg','webp'].map((_,i)=>['png','jpeg','webp'][(i+ci+si)%3])){
   if(options.only&&`${c.key}:${format}:${speed}`!==options.only)continue;
   await disk();
   const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});
   await context.addInitScript(probe,{kind:'viewer'});const page=await context.newPage();if(headful)await page.bringToFront();
   const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   const cdp=await context.newCDPSession(page);await cdp.send('Network.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
   await page.goto(`http://127.0.0.1:8780/?run=${c.key}&format=${format}`,{waitUntil:'networkidle'});
   await page.waitForFunction(()=>document.querySelectorAll('#grid img').length&&[...document.querySelectorAll('#grid img')].every(i=>i.complete&&i.naturalWidth));
   await page.locator('#speed').selectOption(String(speed));
   await page.evaluate(()=>window.__mediaBench.begin());await page.locator('#play').click();
   await page.waitForFunction(()=>window.__mediaBench.end!==null,{},{timeout:c.frames/c.fps/speed*4000+15000});
   let nativeComplete=true;
   try{await page.waitForFunction(({cameras,last})=>cameras.every(camera=>window.__mediaBench.paints.some(p=>p.camera===camera&&p.index===last)),{cameras:c.cameras,last:c.frames-1},{timeout:1500});}catch{nativeComplete=false;}
   const data=await page.evaluate(()=>({...window.__mediaBench,begin:undefined,resources:performance.getEntriesByType('resource').filter(e=>e.name.includes('/media/')).map(e=>({duration:e.duration,bytes:e.encodedBodySize}))}));
   const seconds=(data.end-data.start)/1000,perCamera={};
   const nativeEnd=nativeComplete?Math.max(...data.paints.filter(p=>p.index===c.frames-1).map(p=>p.renderTime)):null;
   const nativeSeconds=nativeComplete?(nativeEnd-data.start)/1000:null;
   for(const camera of c.cameras){const frames=new Set(data.promotions.filter(p=>p.camera===camera).map(p=>p.index)),painted=new Set(data.paints.filter(p=>p.camera===camera&&p.index>0).map(p=>p.index));perCamera[camera]={unique_frames:frames.size,displayed_advances_fps:Math.max(0,frames.size-1)/seconds,native_painted_advances:painted.size,native_image_paint_fps:nativeComplete?painted.size/nativeSeconds:null};}
   const gaps=data.raf.slice(1).map((t,i)=>t-data.raf[i]);
   const row={case:c.key,source_kind:c.source_kind,format,speed,wall_seconds:seconds,source_seconds:(c.frames-1)/c.fps,
    actual_source_multiplier:((c.frames-1)/c.fps)/seconds,expected_per_camera_fps:c.fps*speed,per_camera:perCamera,
    aggregate_displayed_advances_fps:Object.values(perCamera).reduce((n,v)=>n+v.displayed_advances_fps,0),
    native_image_paint_events:data.paints.length,native_last_frame_complete:nativeComplete,native_wall_seconds:nativeSeconds,decode_calls:data.decode.length,decode_wait_p50_ms:quantile(data.decode.map(d=>d.end-d.start),.5),
    decode_wait_p90_ms:quantile(data.decode.map(d=>d.end-d.start),.9),raf_p90_gap_ms:quantile(gaps,.9),raf_max_gap_ms:Math.max(...gaps),
    http_requests:data.resources.length,http_bytes:data.resources.reduce((n,r)=>n+r.bytes,0),http_p90_ms:quantile(data.resources.map(r=>r.duration),.9),
    visibility_changes:data.visibility,page_errors:errors,metric:'decoded-visible source frame promotions sampled at rAF; native image render events separately recorded; physical display fps NOT_MEASURED'};
   await disk();const name=`${c.key}-${format}-${speed}`;await writeFile(path.join(options.output,name+'.json'),JSON.stringify({summary:row,raw:data},null,2));
   await page.screenshot({path:path.join(options.output,name+'.png'),fullPage:true});rows.push(row);console.log(JSON.stringify(row));
   await context.close();
  }
 }
 await writeFile(path.join(options.output,'summary.json'),JSON.stringify({browser:await browser.version(),node:process.version,hardware:{platform:os.platform(),release:os.release(),arch:os.arch(),cpu:os.cpus()[0].model,logical_cpus:os.cpus().length,memory_bytes:os.totalmem()},executed_tool_sha256:toolPins,headful,viewport:[1440,1000],cache:'fresh context, HTTP cache disabled per trial',source_head:'eb10d4c62ce09a765488cdd0548cfdd3abfd5109',manifest_sha256:createHash('sha256').update(manifestRaw).digest('hex'),trials:rows},null,2));
}finally{await browser.close();}

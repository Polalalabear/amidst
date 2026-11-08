import {readFile,writeFile,mkdir,statfs} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import os from 'node:os';
import {probe} from './browser_probe.mjs';
const args=Object.fromEntries(process.argv.slice(2).map(x=>x.replace(/^--/,'').split('=',2)));
const {chromium}=await import(pathToFileURL(args.playwright));
const pins={};for(const name of ['measure_legacy_playback.mjs','browser_probe.mjs'])pins[name]=createHash('sha256').update(await readFile(new URL(name,import.meta.url))).digest('hex');
await mkdir(args.output,{recursive:false});
const browser=await chromium.launch({headless:true,executablePath:args.chrome,args:['--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']});
const trials=[];const q=(v,p)=>v.length?[...v].sort((a,b)=>a-b)[Math.ceil(p*v.length)-1]:null;
try{
 for(const speed of [1,1.5,2])for(const format of ['png','jpeg','webp']){
  if(args.only&&`${format}:${speed}`!==args.only)continue;
  const disk=await statfs(path.dirname(args.output));if(disk.bavail*disk.bsize<8*1024**3)throw Error('DISK_BELOW_8_GIB');
  const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});await context.addInitScript(probe,{kind:'legacy'});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  const cdp=await context.newCDPSession(page);await cdp.send('Network.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
  await page.goto(`http://127.0.0.1:8782/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938&format=${format}`,{waitUntil:'domcontentloaded'});
  await page.locator('.q2-screen .q2-media img').first().waitFor({state:'visible'});
  await page.locator('#q-speed').selectOption(String(speed));
  await page.locator('#q-scrub').evaluate(node=>{node.value='0';node.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.waitForFunction(()=>[...document.querySelectorAll('.q2-screen .q2-media')].filter(n=>getComputedStyle(n).visibility!=='hidden').every(n=>n.dataset.status==='READY'));
  await page.evaluate(()=>{
   window.__mediaBench.begin();
   const watch=()=>{const images=[...document.querySelectorAll('.q2-screen .q2-media img')].filter(i=>i.complete&&i.naturalWidth&&getComputedStyle(i).visibility!=='hidden');
    if(images.some(i=>Number(i.dataset.frameIndex)===159)){window.__mediaBench.end=performance.now();window.__mediaBench.active=false;}else requestAnimationFrame(watch);};requestAnimationFrame(watch);
  });
  await page.locator('#q-play').click();await page.waitForFunction(()=>window.__mediaBench.end!==null,{},{timeout:60000});
  let nativeComplete=true;try{await page.waitForFunction(()=>window.__mediaBench.paints.some(p=>p.camera==='B'&&p.index===159),{},{timeout:1500});}catch{nativeComplete=false;}
  await page.locator('#q-play').click();
  const data=await page.evaluate(()=>({...window.__mediaBench,begin:undefined,playback:JSON.parse(document.querySelector('#q-playback-metrics').textContent)}));
  const seconds=(data.end-data.start)/1000,ready=new Set(data.promotions.filter(p=>p.index>0).map(p=>`${p.camera}:${p.index}`)),paints=new Set(data.paints.filter(p=>p.index>0).map(p=>`${p.camera}:${p.index}`));
  const nativeEnd=nativeComplete?Math.max(...data.paints.filter(p=>p.camera==='B'&&p.index===159).map(p=>p.renderTime)):null;
  const row={profile:'B-05b recorded workbench single view',format,speed,wall_seconds:seconds,actual_source_multiplier:7.95/seconds,expected_fps:20*speed,decoded_visible_frames:ready.size,decoded_visible_fps:ready.size/seconds,native_paint_frames:paints.size,native_last_frame_complete:nativeComplete,native_image_paint_fps:nativeComplete?paints.size/((nativeEnd-data.start)/1000):null,decode_wait_p90_ms:q(data.decode.map(d=>d.end-d.start),.9),page_errors:errors,headful:false};
  const name=`B-05b-workbench-${format}-${speed}`;await writeFile(path.join(args.output,name+'.json'),JSON.stringify({summary:row,raw:data},null,2));await page.screenshot({path:path.join(args.output,name+'.png'),fullPage:true});trials.push(row);console.log(JSON.stringify(row));await context.close();
 }
 await writeFile(path.join(args.output,'summary.json'),JSON.stringify({browser:await browser.version(),headful:false,source_head:'eb10d4c62ce09a765488cdd0548cfdd3abfd5109',executed_tool_sha256:pins,hardware:{cpu:os.cpus()[0].model,memory_bytes:os.totalmem(),logical_cpus:os.cpus().length},trials},null,2));
}finally{await browser.close();}

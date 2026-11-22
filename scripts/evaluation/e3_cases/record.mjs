// Capture the frozen cases through the unchanged LIVE A page. This private loopback sink
// stores camera pixels; it never estimates detections, answers or tracking success.
import fs from 'node:fs';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {ROOT,read,sha} from './generate.mjs';
const require=createRequire(new URL('../../../frontend/live-mode/package.json',import.meta.url));
const {default:puppeteer}=await import(require.resolve('puppeteer-core'));
const [outArg,assetsArg,...wanted]=process.argv.slice(2);
if(!outArg||!assetsArg)throw new Error('usage: record.mjs OUT ASSETS [CASE_IDS...]');
const out=path.resolve(outArg),assets=path.resolve(assetsArg),front=path.join(ROOT,'frontend/live-mode');
const cases=wanted.length?wanted:read(path.join(out,'input-replay.json')).map(r=>r.case_id);
let active=null;
const sourceFiles={'/data/scenario.json':path.join(ROOT,'docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json'),
 '/data/geometry.json':path.join(ROOT,'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json')};
for(const name of ['scene.glb','character.glb','cameras.three.json'])sourceFiles['/data/'+name]=path.join(assets,name);
function safeJoin(root,suffix){const p=path.resolve(root,suffix);return p.startsWith(root+path.sep)?p:null;}
const server=createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost').pathname;
  const json=x=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(x));};
  if(url==='/config')return json({n6:true,schedule_mode:'all'});
  if(url==='/reset')return json({ok:true,session_id:'0652065206520652'});
  if(url==='/track/start')return json({mode:'ACQUIRING',color:'red'});
  if(url==='/infer'){
   const chunks=[];for await(const c of req)chunks.push(c);const packet=Buffer.concat(chunks);
   const size=packet.readUInt32LE(),header=JSON.parse(packet.subarray(4,4+size));
   const permitted=['schema_version','tick','t_capture_ms','frames','available_cameras'];
   if(Object.keys(header).some(k=>!permitted.includes(k)))throw new Error('PRIVATE_WIRE_FIELD');
   let offset=4+size;const frames=[];
   for(const f of header.frames){
    const bytes=packet.subarray(offset,offset+f.bytes);offset+=f.bytes;
    if(bytes.length!==f.bytes||bytes[0]!==255||bytes[1]!==216)throw new Error('JPEG_PACKET_INVALID');
    const rel=`pixels/${active.id}/${header.tick.toString().padStart(5,'0')}-${f.cam}.jpg`;
    if(active.repeat===0){fs.mkdirSync(path.dirname(path.join(out,rel)),{recursive:true});fs.writeFileSync(path.join(out,rel),bytes);}
    frames.push({cam:f.cam,bytes:f.bytes,sha256:sha(bytes),path:rel});
   }
   if(offset!==packet.length)throw new Error('PACKET_LENGTH');
   active.wire.push({...header,frames});
   return json({tracking:{state:'IDLE',lost_ticks:0},events:[],timing_ms:{server_total:0}});
  }
  const file=sourceFiles[url]||(url==='/'?path.join(front,'index.html'):
   url.startsWith('/src/')?safeJoin(front,url.slice(1)):
   url.startsWith('/vendor/three/')?safeJoin(path.join(front,'node_modules/three'),url.slice('/vendor/three/'.length)):null);
  if(!file||!fs.existsSync(file)){res.statusCode=404;return res.end();}
  res.setHeader('Content-Type',file.endsWith('.css')?'text/css':/\.(mjs|js)$/.test(file)?'text/javascript':file.endsWith('.html')?'text/html':file.endsWith('.json')?'application/json':'model/gltf-binary');
  fs.createReadStream(file).pipe(res);
 }catch(error){res.statusCode=500;res.end(JSON.stringify({error:error.message}));console.error(error);}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
try{
 browser=await puppeteer.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,
  args:['--use-angle=metal','--ignore-gpu-blocklist','--disable-background-timer-throttling'],defaultViewport:{width:960,height:640}});
 const receipts=[];
 for(const id of cases){
  let data=read(path.join(out,`${id}.case.json`));const replays=[];
  const inputData={...data};delete inputData.expected;
  fs.writeFileSync(path.join(out,`${id}.input.case.json`),JSON.stringify(inputData));
  for(let repeat=0;repeat<3;repeat++){
   active={id,repeat,wire:[]};const page=await browser.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   // Accelerate wall pacing only. Production playback still advances 0.05 s inputs
   // behind its capture barrier and compares every expected resolver state.
   await page.evaluateOnNewDocument(()=>{const raf=requestAnimationFrame.bind(window);let t=performance.now();window.requestAnimationFrame=cb=>raf(()=>{t+=100;cb(t);});});
   await page.goto(`http://127.0.0.1:${server.address().port}/?auto=recorded`);
   await page.waitForSelector('#case-file');await (await page.$('#case-file')).uploadFile(path.join(out,repeat===0?`${id}.input.case.json`:`${id}.case.json`));
   await page.waitForFunction(()=>window.__recordingDone||window.__recordingError||document.querySelector('#case-status')?.textContent,{timeout:600000});
   const result=await page.evaluate(()=>({error:window.__recordingError||document.querySelector('#case-status')?.textContent,done:window.__recordingDone,
    data:window.__case?.(),log:window.__log}));
   if(result.error||!result.done||errors.length)throw new Error(`${id}:BROWSER:${JSON.stringify({error:result.error,errors})}`);
   if(JSON.stringify(result.data.inputs)!==JSON.stringify(data.inputs)||(repeat>0&&JSON.stringify(result.data.expected)!==JSON.stringify(data.expected)))throw new Error('BROWSER_STATE_MISMATCH');
   if(repeat===0){data=result.data;fs.writeFileSync(path.join(out,`${id}.case.json`),JSON.stringify(data));}
   const logical=result.log.ticks.map(t=>({tick:t.tick,t_sim:t.t_sim,t_infer_capture_ms:t.t_infer_capture_ms,actors:t.actors,
    pause_total_i:t.pause_total_i,pause_player_i:t.pause_player_i,pause_script_i:t.pause_script_i,active_passes:t.active_passes,forced_pairs:t.forced_pairs}));
   if(active.wire.length!==data.inputs.length/4+1)throw new Error('CAPTURE_COUNT');
   for(const [i,h]of active.wire.entries())if(h.tick!==i||h.t_capture_ms!==i*200||h.frames.length!==8)throw new Error('CAPTURE_CLOCK');
   fs.writeFileSync(path.join(out,`${id}.replay${repeat+1}.a-log.json`),JSON.stringify(result.log));
   fs.writeFileSync(path.join(out,`${id}.replay${repeat+1}.wire.json`),JSON.stringify(active.wire));
   replays.push({logical_sha256:sha(JSON.stringify(logical)),captures:active.wire.length,frames:active.wire.length*8,errors});
   if(repeat===0)await page.screenshot({path:path.join(out,`${id}.operator.png`)});
   await page.close();console.log(id,'replay',repeat+1,'captures',replays.at(-1).captures,replays.at(-1).logical_sha256);
  }
  if(replays.some(r=>r.logical_sha256!==replays[0].logical_sha256))throw new Error('BROWSER_LOGICAL_REPLAY_MISMATCH');
  receipts.push({case_id:id,case_sha256:sha(fs.readFileSync(path.join(out,`${id}.case.json`))),replays,inference:'PIXEL_SINK_ONLY_NO_DETECTOR_NO_AGENT'});
  fs.writeFileSync(path.join(out,'browser-replay.json'),JSON.stringify(receipts,null,2)+'\n');
 }
}finally{if(browser)await browser.close();await new Promise(r=>server.close(r));}

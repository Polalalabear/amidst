import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from 'three';
import {createSessionGate, menuOptions, variantSwatches, privateTick, makeOperatorView} from '../src/operator.mjs';
import {createCrowd} from '../src/crowd.mjs';
import {headlessMode} from '../../../scripts/browser_options.mjs';
import {buildInferHeader,buildSystemMessage} from '../src/protocol.mjs';
const scenario=JSON.parse(fs.readFileSync(new URL('../../../docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json',import.meta.url)));
test('scene defaults, legacy and short URL bypasses and role validation',()=>{
 assert.deepEqual(menuOptions(new URLSearchParams()),{run_id:'A4-1-v2-4actor',actor_id:null,skip:false,mouse:'lock'});
 for(const actor of ['T','A','B','C'])assert.equal(menuOptions(new URLSearchParams(`actor=${actor}`)).actor_id,actor);
 assert.equal(menuOptions(new URLSearchParams('run=B4-1')).run_id,'B4-1-v2-4actor');
 assert.equal(menuOptions(new URLSearchParams('run=A4-1-v2-4actor&actor=C')).skip,true);
 assert.equal(menuOptions(new URLSearchParams('auto=B4')).run_id,'B4-1-v2-4actor');
 assert.equal(menuOptions(new URLSearchParams('auto=A4&mouse=drag')).mouse,'off');
 assert.throws(()=>menuOptions(new URLSearchParams('actor=X')),/ACTOR/);
 assert.throws(()=>menuOptions(new URLSearchParams('run=X')),/RUN/);
});
test('Begin gate: no requests before selection; one reset, immutable session, no infer until token',async()=>{
 const calls=[];let ready;const reset=new Promise(r=>{ready=r;});
 const gate=createSessionGate(scenario,menuOptions(new URLSearchParams()),async(url,opt)=>{calls.push([url,opt]);return reset;});
 assert.equal(calls.length,0);await assert.rejects(gate.begin(),/ACTOR_REQUIRED/);assert.equal(calls.length,0);
 gate.chooseRun('B4-1');gate.chooseActor('C');const pending=gate.begin();
 assert.equal(calls.length,1);assert.equal(calls[0][0],'/reset');assert.equal(calls[0][1].method,'POST');
 assert.throws(()=>gate.chooseActor('A'),/SESSION_LOCKED/);await assert.rejects(gate.begin(),/SESSION_LOCKED/);
 ready({ok:true,json:async()=>({session_id:'0123456789abcdef'})});const session=await pending;
 assert.deepEqual(session,{run_id:'B4-1-v2-4actor',actor_id:'C',session_id:'0123456789abcdef'});assert.ok(Object.isFrozen(session));
 assert.throws(()=>{session.actor_id='T';},TypeError);assert.throws(()=>gate.chooseRun('A4-1'),/SESSION_LOCKED/);
});
test('missing/failed reset token fails closed, requires reload',async()=>{
 for(const response of [{ok:true,json:async()=>({ok:true})},{ok:false,json:async()=>({})}]){
  const gate=createSessionGate(scenario,menuOptions(new URLSearchParams('actor=T')),async()=>response);
  await assert.rejects(gate.begin(),/RESET/);await assert.rejects(gate.begin(),/SESSION_LOCKED/);
 }
});
test('variant fallback colors come from GLB material metadata, including linear-to-sRGB conversion',()=>{
 const json={extensions:{KHR_materials_variants:{variants:['T','A','B','C'].map(name=>({name}))}},materials:[.1,.2,.3,.4].map(x=>({name:'SHIRT',pbrMetallicRoughness:{baseColorFactor:[x,.02,.01,1]}})),meshes:[{primitives:[{material:0,extensions:{KHR_materials_variants:{mappings:[0,1,2,3].map(i=>({material:i,variants:[i]}))}}}]}]};
 const bytes=new TextEncoder().encode(JSON.stringify(json));const size=Math.ceil(bytes.length/4)*4;const buf=new ArrayBuffer(20+size);const dv=new DataView(buf);dv.setUint32(0,0x46546c67,true);dv.setUint32(4,2,true);dv.setUint32(8,buf.byteLength,true);dv.setUint32(12,size,true);dv.setUint32(16,0x4e4f534a,true);new Uint8Array(buf,20).fill(32);new Uint8Array(buf,20,bytes.length).set(bytes);
 const colors=variantSwatches(buf);assert.equal(Object.keys(colors).length,4);assert.notEqual(colors.T,colors.C);assert.match(colors.T,/^#[0-9a-f]{6}$/);assert.throws(()=>variantSwatches(new ArrayBuffer(20)),/GLB/);
});
test('selected actor is sole player; all actors and visibility stay in private log, never header/channel',()=>{
 for(const run of scenario.runs)for(const actorId of ['T','A','B','C']){
  const crowd=createCrowd(run,{actorId});const snap=crowd.step({},.1);const row=privateTick(snap,0,100,(a)=>a.present?['CAM_TEST']:[]);
  assert.equal(row.actors.length,4);assert.equal(snap.actors.filter(a=>a.is_player).length,1);assert.equal(snap.actors.find(a=>a.is_player).variant,actorId);
  assert.ok(row.actors.every(a=>a.id&&typeof a.present==='boolean'&&'xy'in a&&'gt_visible'in a));
  const scripts = snap.actors.filter(a => !a.is_player);
  assert.equal(scripts.length, 3);
  for (const actor of scripts) {
   const id = actor.actor_id;
   assert.equal(row.pause_player_i[id] + row.pause_script_i[id], row.pause_total_i[id]);
  }
  const frame={cam:'CAM_TEST',jpeg:'opaque'};
  const header=buildInferHeader({tick:0,tCaptureMs:100,frames:[frame],...row});
  const message=buildSystemMessage({tick:0,tCaptureMs:100,frames:[frame],result:{...row}});
  for(const value of [header,message]){const raw=JSON.stringify(value);for(const banned of ['actor_id','actors','gt_visible','pause_total_i','pause_player_i','pause_script_i','spawn_adjusted','view_yaw'])assert.ok(!raw.includes(banned),banned);}
 }
});

test('operator transparency restores opaque virtual-camera materials even after render failure',()=>{
 const scene=new THREE.Scene(),shared=new THREE.MeshBasicMaterial(),wall=new THREE.Mesh(new THREE.BoxGeometry(),shared),floor=new THREE.Mesh(new THREE.PlaneGeometry(),shared),ceiling=new THREE.Group();
 wall.name='WALL_JOINED_SHELL_LIVE';ceiling.name='CEILING_STATIC_LIVE';scene.add(wall,floor,ceiling);
 const draw=makeOperatorView({scene,wallMats:[]},{xray:true});assert.notEqual(wall.material,shared);
 assert.throws(()=>draw(()=>{assert.equal(wall.material.opacity,.18);assert.equal(floor.material.opacity,1);assert.equal(ceiling.visible,false);throw new Error('render failed');}),/render failed/);
 assert.equal(wall.material.opacity,1);assert.equal(wall.material.transparent,false);assert.equal(wall.material.depthWrite,true);assert.equal(ceiling.visible,true);
});
test('A source has no tracking endpoint or target controls',()=>{
 const source=fs.readFileSync(new URL('../src/operator.mjs',import.meta.url),'utf8');
 assert.ok(!source.includes('/track/'));assert.ok(!/id=[\"'](?:sentence|who)[\"']/.test(source));
});

// Opt-in local UI test: real renderer/assets, deterministic fake backend, no model/API calls.
test('browser menu, Begin, drag movement, private log and URL bypass', {skip: !process.env.LIVE_AB_BROWSER, timeout: 120000}, async () => {
 const {createServer}=await import('node:http');const path=await import('node:path');const {fileURLToPath}=await import('node:url');
 const {default:puppeteer}=await import('puppeteer-core');
 const root=fileURLToPath(new URL('../',import.meta.url));const repo=path.resolve(root,'../..');
 const assets=process.env.AMIDST_LIVE_ASSETS, out=process.env.LIVE_AB_TEST_OUTPUT;
 assert.ok(assets&&out,'set AMIDST_LIVE_ASSETS and LIVE_AB_TEST_OUTPUT');fs.mkdirSync(out,{recursive:true});
 const requests=[],headers=[],errors=[];
 const files={'/':path.join(root,'index.html'),'/data/scenario.json':path.join(repo,'docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json'),'/data/geometry.json':path.join(repo,'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json')};
 for(const name of ['character.glb','scene.glb','cameras.three.json'])files[`/data/${name}`]=path.join(assets,name);
 const server=createServer(async(req,res)=>{
  const url=new URL(req.url,'http://localhost').pathname;requests.push({url,method:req.method});
  const json=value=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(value));};
  if(url==='/config')return json({n6:true,schedule_mode:'all'});
  if(url==='/reset')return json({ok:true,session_id:'0123456789abcdef'});
  if(url==='/track/start')return json({mode:'TRACKING',color:'red',candidates:[
   {tick:0,cand_id:'fresh',est_xy:[4,1]}]});
  if(url==='/track/stop')return json({mode:'IDLE'});
  if(url==='/infer'){
   const chunks=[];for await(const c of req)chunks.push(c);const b=Buffer.concat(chunks);headers.push(JSON.parse(b.subarray(4,4+b.readUInt32LE(0)).toString()));
   if(headers.length===1){res.statusCode=409;return json({error:'NON_MONOTONIC_TICK',next_tick:1});}
   return json({tracking:{state:'SEARCHING',lost_ticks:0},events:[],timing_ms:{server_total:0}});
  }
  const file=files[url]||(url.startsWith('/src/')?path.join(root,url.slice(1)):url.startsWith('/vendor/three/')?path.join(root,'node_modules/three',url.slice('/vendor/three/'.length)):null);
  if(!file||!fs.existsSync(file)){res.statusCode=404;return res.end();}
  res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.mjs')||file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':file.endsWith('.json')?'application/json':'model/gltf-binary');fs.createReadStream(file).pipe(res);
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{
  browser=await puppeteer.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:headlessMode(),args:['--use-angle=metal','--ignore-gpu-blocklist'],defaultViewport:{width:1440,height:1000}});
  if(headlessMode())assert.ok(browser.process().spawnargs.some(arg=>arg==='--headless=new'||arg==='--headless'));
  const page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));const base=`http://127.0.0.1:${server.address().port}`;
  await page.goto(`${base}/?mouse=drag&fps=2`);await page.waitForSelector('[data-actor="C"]');
  await page.waitForFunction(()=>document.querySelector('#ab-status')?.textContent!=='載入外觀…');
  assert.equal(await page.$eval('#ab-begin',b=>b.disabled),true);assert.equal(requests.filter(r=>r.url==='/infer'||r.url==='/reset').length,0);
  await page.click('[data-run="B4-1-v2-4actor"]');await page.click('[data-actor="T"]');
  await page.waitForFunction(()=>!document.querySelector('#ab-begin').disabled);
  await page.screenshot({path:path.join(out,'menu.png')});await page.click('#ab-begin');
  await page.waitForFunction(()=>window.__ready===true,{timeout:60000});await page.waitForFunction(()=>window.__log?.ticks.length>0);
  assert.equal(await page.$eval('#op',el=>getComputedStyle(el).display),'grid','shared LIVE styles load in fixture');
  assert.equal(await page.$('#ab-menu'),null);assert.equal(await page.$('#sentence'),null);assert.equal(await page.$('#who'),null);
  const initial=await page.evaluate(()=>({p:__op.P0,keys:Object.keys(__op),run:__log.run_id,actor:__log.actor_id,session:__log.session_id}));
  assert.deepEqual(initial.keys,['P0']);assert.equal(initial.run,'B4-1-v2-4actor');assert.equal(initial.actor,'T');
  await page.screenshot({path:path.join(out,'before-drag.png')});
  await page.mouse.move(200,400);await page.mouse.down();await page.mouse.move(800,400,{steps:6});await page.mouse.up();
  const afterLook=await page.evaluate(()=>__op.P0);assert.deepEqual(afterLook,initial.p);
  await page.screenshot({path:path.join(out,'after-drag.png')});
  await page.evaluate(()=>__setKeys({w:true}));await new Promise(r=>setTimeout(r,350));await page.evaluate(()=>__setKeys({w:false}));
  const afterMove=await page.evaluate(()=>__op.P0);assert.ok(afterMove.x>initial.p.x+.02,JSON.stringify({initial,afterMove}));assert.ok(Math.abs(afterMove.y-initial.p.y)<.01);
  await page.keyboard.press('Escape');assert.equal(await page.$('#ab-menu'),null);
  const log=await page.evaluate(()=>__log);assert.equal(log.schema_version,'live-ab.a-log.v1');assert.equal(log.session_id,initial.session);assert.ok(log.ticks.every(t => !('gt_visible' in t) && t.actors.length === 4
    && t.actors.every(actor => Array.isArray(actor.gt_visible))
    && Object.keys(t.pause_player_i).length === 3 && Object.keys(t.pause_script_i).length === 3
    && Array.isArray(t.forced_overlap) && Array.isArray(t.spawn_adjusted) && Array.isArray(t.block_wait)
    && Array.isArray(t.pass_end) && Array.isArray(t.crowd_error)));
  assert.deepEqual(headers.slice(0,2).map(h=>h.tick),[0,1]);
  assert.equal(log.ticks[0].tick,1);
  assert.deepEqual(log.errors,[{tick:0,error:'NON_MONOTONIC_TICK'}]);
  fs.writeFileSync(path.join(out,'a-browser.json'),JSON.stringify(log,null,2));
  const downloads=path.join(out,'downloads');fs.mkdirSync(downloads,{recursive:true});
  const cdp=await page.createCDPSession();await cdp.send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});
  await page.click('#ab-download');const downloaded=path.join(downloads,`live-ab-a-${initial.session}.json`);
  for(let i=0;i<30&&!fs.existsSync(downloaded);i++)await new Promise(r=>setTimeout(r,100));
  const saved=JSON.parse(fs.readFileSync(downloaded,'utf8'));assert.equal(saved.schema_version,'live-ab.a-log.v1');assert.equal(saved.session_id,initial.session);
  assert.ok(headers.length>0);for(const h of headers)for(const key of ['actors','actor_id','run_id','gt_visible','view_yaw','pause_total_i'])assert.ok(!JSON.stringify(h).includes(key),key);
  assert.equal(requests.filter(r=>r.url.startsWith('/track/')).length,0);assert.equal(errors.length,0,errors.join('\n'));
  const fallback=await browser.newPage();
  await fallback.evaluateOnNewDocument(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type.includes('webgl')?null:original.call(this,type,...args);};});
  await fallback.goto(`${base}/?mouse=drag`);await fallback.waitForSelector('[data-actor=\"C\"]');await fallback.click('[data-actor=\"A\"]');
  await fallback.waitForFunction(()=>!document.querySelector('#ab-begin').disabled);
  assert.equal(await fallback.$$eval('[data-preview][hidden]',nodes=>nodes.length),4);
  await fallback.screenshot({path:path.join(out,'fallback-swatches.png')});
  // A second page exercises the real start() URL bypass, with the same fake reset contract.
  const automatic=await browser.newPage();automatic.on('pageerror',e=>errors.push(e.message));await automatic.goto(`${base}/?run=A4-1&actor=C&auto=A4&mouse=drag&fps=1`);
  await automatic.waitForFunction(()=>window.__ready===true,{timeout:60000});assert.equal(await automatic.$('#ab-menu'),null);
  const selected=await automatic.evaluate(()=>({actor:__log.actor_id,run:__log.run_id,mouse:__log.config.view.mouse}));assert.deepEqual(selected,{actor:'C',run:'A4-1-v2-4actor',mouse:'off'});
  await Promise.all([page.close(),fallback.close(),automatic.close()]);
  const recorder=await browser.newPage();
  recorder.on('pageerror',e=>{errors.push(e.message);fs.writeFileSync(path.join(out,'record-errors.json'),JSON.stringify(errors));});
  await recorder.goto(base+'/?script=H1-1&record=1&fps=5&mouse=off');
  try { await recorder.waitForFunction(()=>window.__log?.ticks.length>=6,{timeout:20000}); }
  catch (error) {
   fs.writeFileSync(path.join(out,'record-debug.json'),JSON.stringify(await recorder.evaluate(()=>({
    ready:window.__ready,error:window.__recordingError,log:window.__log,
    case:window.__case?.(),text:document.body.innerText})),null,2));
   throw error;
  }
  await recorder.evaluate(()=>__setKeys({w:true}));
  await recorder.waitForFunction(()=>window.__log?.ticks.length>=19,{timeout:60000});
  await recorder.click('#record-stop');
  await recorder.waitForFunction(()=>window.__recordingDone===true);
  const caseData=await recorder.evaluate(()=>__case());
  assert.equal(caseData.script_id,'H1-1');
  assert.ok(caseData.inputs.some(row=>row.keys.w));
  caseData.actions=[{tick:0,action:'start',color:'red'},
   {tick:Math.floor(caseData.inputs.length/4),action:'stop'}];
  const caseFile=path.join(out,'browser.case.json');
  fs.writeFileSync(caseFile,JSON.stringify(caseData,null,2));
  await recorder.close();
  const sequences=[];
  for(let repeat=0;repeat<2;repeat++){
   const replay=await browser.newPage();
   await replay.goto(base+'/?auto=recorded');
   await replay.waitForSelector('#case-file');
   await (await replay.$('#case-file')).uploadFile(caseFile);
   await replay.waitForFunction(()=>window.__recordingDone===true||window.__recordingError,{timeout:60000});
   const result=await replay.evaluate(()=>({error:window.__recordingError,a:__log,b:__replayLog,recorded:__case()}));
   assert.equal(result.error,undefined);
   assert.deepEqual(result.recorded.expected,caseData.expected);
   assert.ok(result.a.ticks.every(row=>Math.abs(row.t_sim-row.tick/5)<1e-9));
   assert.equal(result.b.actions.length,2);
   assert.doesNotMatch(JSON.stringify(result.b),/gt_visible|actor_id|pause_total|expected|bindings/);
   sequences.push(result.a.ticks.map(row=>({tick:row.tick,t_sim:row.t_sim,actors:row.actors,
    pause_total_i:row.pause_total_i,t_infer_capture_ms:row.t_infer_capture_ms})));
   const aFile=path.join(out,'replay-'+repeat+'-a.json'),bFile=path.join(out,'replay-'+repeat+'-b.json');
   fs.writeFileSync(aFile,JSON.stringify(result.a,null,2));fs.writeFileSync(bFile,JSON.stringify(result.b,null,2));
   const {spawnSync}=await import('node:child_process');
   const scored=spawnSync(path.join(repo,'.venv/bin/python'),['-B','scripts/live_ab_score.py',
    '--operator-json',aFile,'--system-json',bFile,'--out',path.join(out,'replay-'+repeat+'-score.json')],{cwd:repo,encoding:'utf8'});
   assert.equal(scored.status,0,scored.stderr);
   await replay.close();
  }
  assert.deepEqual(sequences[0],sequences[1]);
  assert.equal(errors.length,0,errors.join('\n'));fs.writeFileSync(path.join(out,'browser-receipt.json'),JSON.stringify({initial,afterLook,afterMove,selected,headers,requests,errors},null,2));
 }finally{await browser?.close();await new Promise(r=>server.close(r));}
});

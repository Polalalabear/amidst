// #652: A-side input recordings only. No inference, scorer or model calls.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createCrowd} from '../../../frontend/live-mode/src/crowd.mjs';
import {createScriptOperator} from '../../../frontend/live-mode/src/script_operator.mjs';
import {createInputRecording,createPlayback,hashBinding,RECORD_DT} from '../../../frontend/live-mode/src/recording.mjs';
import {buildWorld} from '../../../frontend/live-mode/src/world.mjs';
import {buildN6Cameras} from '../../../frontend/live-mode/src/n6.mjs';
import {E3_ROUTES} from './routes.mjs';
export const ROOT = fileURLToPath(new URL('../../../',import.meta.url));
export const sha = value => createHash('sha256').update(value).digest('hex');
export const read = p => JSON.parse(fs.readFileSync(p));
export function setup(assets) {
 const runs=read(path.join(ROOT,'docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json')).runs;
 const geometry=read(path.join(ROOT,'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'));
 const world=buildWorld(geometry);
 const cams=buildN6Cameras(read(path.join(assets,'cameras.three.json')),world.scene,320,180);
 world.scene.updateMatrixWorld(true);
 return {runs,world,cams};
}
export async function generate(route,caseId,env) {
 const {runs,world,cams}=env;
 const run=route.run??runs.find(r=>r.run_id===route.run_id+'-v2-4actor');
 const make=()=>createCrowd(run,{actorId:'T',segments:world.segments});
 const crowd=make(),op=createScriptOperator(route);
 const bindings={scene_sha256:await hashBinding({run,segments:world.segments}),
  cameras_sha256:await hashBinding(Object.fromEntries(Object.entries(cams).map(([id,c])=>
   [id,{world:c.camera.matrixWorld.toArray(),projection:c.camera.projectionMatrix.toArray()}])))};
 const config={w:320,h:180,fps:5,cams:Object.keys(cams),model:'glb',scene:'n6',quality:.85,auto:null,crowd:crowd.snapshot().config};
 const recording=createInputRecording({case_id:caseId,script_id:null,run_id:run.run_id,actor_id:'T',seed:0,bindings,config},crowd.snapshot());
 let doneAt=null;
 for(let n=0;n<2400;n++){
  const s=crowd.snapshot(),p=s.actors.find(a=>a.is_player);
  const keys=op.keys(p,s.t_sim);
  if(op.done&&doneAt===null)doneAt=s.tick;
  if(doneAt!==null&&s.tick>=doneAt+Math.round(route.tail_s/RECORD_DT)&&s.tick%4===0)break;
  recording.append(keys,crowd.step(keys,RECORD_DT));
 }
 if(!op.done)throw new Error(`${caseId}:ROUTE_INCOMPLETE`);
 const stalls=op.events.filter(e=>e.type==='script_stall');
 if(stalls.length)throw new Error(`${caseId}:SCRIPT_STALL:${JSON.stringify(stalls)}`);
 const data=recording.export([{tick:0,action:'start',color:'red'}]);
 // Both replays exercise the production input reader, source binding, resolver and every expected state.
 const replays=[];
 for(let k=0;k<2;k++){
  const c=make(),p=createPlayback(data,c,bindings),h=createHash('sha256');
  h.update(JSON.stringify(c.snapshot()));
  while(!p.done)h.update(JSON.stringify(p.step()));
  replays.push(h.digest('hex'));
 }
 if(replays[0]!==replays[1])throw new Error('REPLAY_HASH_MISMATCH');
 return {data,receipt:{case_id:caseId,family:route.family,run_id:run.run_id,steps:data.inputs.length,
  duration_s:data.inputs.length*RECORD_DT,capture_ticks:data.inputs.length/4+1,route_complete:true,
  route_events:op.events,stalls,replay_state_sha256:replays}};
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const [out,assets]=process.argv.slice(2);if(!out||!assets)throw new Error('usage: generate.mjs OUT ASSETS');
 fs.mkdirSync(out,{recursive:true});const env=setup(assets),receipts=[];
 for(const [id,route]of Object.entries(E3_ROUTES)){
  const {data,receipt}=await generate(route,id,env);const bytes=JSON.stringify(data);
  fs.writeFileSync(path.join(out,`${id}.case.json`),bytes);
  receipts.push({...receipt,case_sha256:sha(bytes),bytes:Buffer.byteLength(bytes)});
  console.log(id,receipt.duration_s,receipt.capture_ticks,receipt.replay_state_sha256[0]);
 }
 fs.writeFileSync(path.join(out,'input-replay.json'),JSON.stringify(receipts,null,2)+'\n');
}

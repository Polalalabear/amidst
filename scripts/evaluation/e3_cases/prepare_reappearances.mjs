// GT-only design/preflight: never reads old corpus catalog, baseline files or B logs.
import fs from 'node:fs';import path from 'node:path';
import {generate,setup,sha,ROOT} from './generate.mjs';
import {groundTruthVisible} from '../../../frontend/live-mode/src/world.mjs';
import {REAPPEARANCE_ROUTES,REAPPEARANCE_POLICY} from './reappearance_routes.mjs';
import {extractReappearances} from './reappearance_events.mjs';
const [out,assets]=process.argv.slice(2);if(!out||!assets)throw new Error('usage: prepare_reappearances.mjs OUT ASSETS');
if(fs.existsSync(path.join(out,'MANIFEST.json'))||fs.existsSync(path.join(out,'GT_FREEZE.json')))throw new Error('REFUSE_FROZEN_CORPUS');
fs.mkdirSync(out,{recursive:true});const env=setup(assets),receipts=[],cases=[];
for(const [id,route]of Object.entries(REAPPEARANCE_ROUTES)){
 const file=path.join(out,`${id}.case.json`);if(fs.existsSync(file))throw new Error('REFUSE_EXISTING_CASE');
 const {data,receipt}=await generate(route,id,env);
 const rows=data.expected.filter(s=>s.tick%4===0).map((s,i)=>({tick:i,actors:s.actors.map(a=>({
  id:a.actor_id,present:a.present,gt_visible:a.present?groundTruthVisible(env.cams,env.world.blockers,env.world.root,a.x,a.y):[]}))}));
 const events=extractReappearances(rows,REAPPEARANCE_POLICY,{family:route.family});
 fs.writeFileSync(file,JSON.stringify(data));receipts.push({...receipt,case_sha256:sha(JSON.stringify(data))});
 cases.push({case_id:id,family:route.family,route,planned_points:events.points,diagnostics:events.diagnostics});
 console.log(id,receipt.duration_s,'s',events.points.length,'reappearances',JSON.stringify(events.diagnostics));
}
const count=cases.reduce((n,c)=>n+c.planned_points.length,0);
fs.writeFileSync(path.join(out,'input-replay.json'),JSON.stringify(receipts,null,2)+'\n');
fs.writeFileSync(path.join(out,'DESIGN.json'),JSON.stringify({status:'GT_ONLY_DESIGN_BEFORE_CAPTURE',counting_stage:'RAW_TRANSITIONS_BEFORE_WINDOW_DEDUPLICATION',policy:REAPPEARANCE_POLICY,cases,
 producer_files:Object.fromEntries(['reappearance_routes.mjs','reappearance_events.mjs','prepare_reappearances.mjs','generate.mjs'].map(f=>[f,sha(fs.readFileSync(path.join(ROOT,'scripts/evaluation/e3_cases',f)))])),
 new_reappearance_points:count,combined_reappearance_points:count+3,combined_primary_points:count+38},null,2)+'\n');
if(count<REAPPEARANCE_POLICY.minimum_new_points)throw new Error(`INSUFFICIENT_GT_PREFLIGHT:${count}`);

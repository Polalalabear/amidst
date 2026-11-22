// Freeze actual renderer GT and primary points BEFORE detection/index production.
// No baseline, B logs, group outputs, ranking or original evaluation catalog reads.
import fs from 'node:fs';import path from 'node:path';
import {setup,read,sha,ROOT} from './generate.mjs';
import {projectBox} from '../../../frontend/live-mode/src/person.mjs';
import {REAPPEARANCE_ROUTES,REAPPEARANCE_POLICY} from './reappearance_routes.mjs';
import {extractReappearances,deduplicateGTWindows} from './reappearance_events.mjs';
const [outArg,assets]=process.argv.slice(2);if(!outArg||!assets)throw new Error('usage: freeze_reappearances.mjs OUT ASSETS');
const out=path.resolve(outArg),freezeFile=path.join(out,'GT_FREEZE.json');
if(fs.existsSync(freezeFile)||fs.existsSync(path.join(out,'indexes')))throw new Error('GT_MUST_FREEZE_BEFORE_DETECTION');
const designPath=path.join(out,fs.existsSync(path.join(out,'DESIGN_V2.json'))?'DESIGN_V2.json':'DESIGN.json');
const design=read(designPath),env=setup(assets),summaries=[],windowItems=[];
const browser=read(path.join(out,'browser-replay.json'));
for(const [id,route]of Object.entries(REAPPEARANCE_ROUTES)){
 if(JSON.stringify(design.cases.find(c=>c.case_id===id)?.route)!==JSON.stringify(route))throw new Error('DESIGN_ROUTE_CHANGED');
 const caseFile=path.join(out,`${id}.case.json`),data=read(caseFile),logFile=path.join(out,`${id}.replay1.a-log.json`),log=read(logFile);
 const events=extractReappearances(log.ticks,REAPPEARANCE_POLICY,{family:route.family});
 if(!events.points.length)throw new Error(`${id}:NO_ELIGIBLE_RETURNS`);
 for(const p of events.points)p.point_id=`${id}-RETURN-${String(p.tick).padStart(5,'0')}`;
 const gt={schema_version:'live-ab.a-log.v1',session_id:log.session_id,run_id:log.run_id,actor_id:'T',
  config:{...log.config,case_id:id},ticks:log.ticks.map(r=>({tick:r.tick,t_capture:r.t_capture,t_sim:r.tick/5,
   actors:r.actors.map(a=>({...a,gt_boxes:Object.fromEntries(a.gt_visible.map(cam=>[cam,
    projectBox(env.cams[cam].camera,env.world.root,a.xy[0],a.xy[1],320,180)]))}))})),
  provenance:{role:'EVALUATION_ONLY',visibility:'THREE_BODY_POINT_RAYS_STATIC_WALLS_NOT_ACTOR_OCCLUSION',
   gt_box_kind:'EXISTING_PROJECTBOX_0_5_X_0_5_X_1_75_M_PROXY_NOT_PIXEL_MASK',image_size_px:[320,180],
   identity_verdict:'UNCONFIRMED',physical_verdict:'UNKNOWN',source_a_log_sha256:sha(fs.readFileSync(logFile))}};
 const gtPath=`gt-boxes/${id}.a-log.json`;fs.mkdirSync(path.join(out,'gt-boxes'),{recursive:true});
 fs.writeFileSync(path.join(out,gtPath),JSON.stringify(gt));
 data.status='FORMAL_RECORDED_FROZEN';data.production_protocol='SCRIPT_AND_GT_ONLY_NO_GROUP_OUTPUTS';
 fs.writeFileSync(caseFile,JSON.stringify(data));
 windowItems.push({case_id:id,renderer_run_id:data.run_id,rows:gt.ticks,points:events.points});
 const receipt=browser.find(r=>r.case_id===id);if(!receipt||receipt.replays.length!==3)throw new Error('THREE_RENDERER_RUNS_REQUIRED');
 const hashes=receipt.replays.map(r=>r.logical_sha256);if(new Set(hashes).size!==1)throw new Error('REPLAY_DIVERGENCE');
 receipt.case_sha256=sha(fs.readFileSync(caseFile));
 summaries.push({case_id:id,family:route.family,renderer_run_id:data.run_id,status:data.status,
  case_path:`${id}.case.json`,case_sha256:receipt.case_sha256,gt_path:gtPath,gt_sha256:sha(JSON.stringify(gt)),
  duration_s:data.inputs.length*.05,cameras:data.config.cams,decision_points:events.points,diagnostic_gaps:events.diagnostics,
  source_plan_sha256:sha(JSON.stringify(design.cases.find(c=>c.case_id===id).route)),
  script_wrap_times_s:Array.from({length:Math.floor(data.inputs.length*.05/(route.run_id==='A4-1'?50:42))},(_,i)=>(i+1)*(route.run_id==='A4-1'?50:42)),
  ranking_status:'UNKNOWN_NOT_RUN_OR_READ',replay_logical_sha256:hashes[0]});
}
const unique=deduplicateGTWindows(windowItems,{round_m:REAPPEARANCE_POLICY.gt_window_round_m});
for(const summary of summaries){const row=unique.find(x=>x.case_id===summary.case_id);summary.raw_return_count=summary.decision_points.length;summary.decision_points=row.points;summary.excluded_duplicate_returns=row.duplicates;}
const count=summaries.reduce((n,c)=>n+c.decision_points.length,0);
if(count<REAPPEARANCE_POLICY.minimum_new_points)throw new Error(`INSUFFICIENT_REAPPEARANCES:${count}`);
const producerFiles=['reappearance_routes.mjs','reappearance_events.mjs','prepare_reappearances.mjs','record.mjs','freeze_reappearances.mjs'];
const result={status:'GT_AND_SCRIPT_FROZEN_BEFORE_DETECTION_AND_E3',frozen_at_utc:new Date().toISOString(),base_source_commit:'8af69ea42cfb06a799952ddb27f97a32a721bde4',
 design_sha256:sha(fs.readFileSync(designPath)),design_file:path.basename(designPath),policy:REAPPEARANCE_POLICY,
 producer_files:Object.fromEntries(producerFiles.map(f=>[f,sha(fs.readFileSync(path.join(ROOT,'scripts/evaluation/e3_cases',f)))])),
 cases:summaries,new_reappearance_points:count,combined_declared_reappearance_points:count+3,
 combined_declared_primary_points:count+38,base_counts_source:'USER_CHAT_20261122_3_AND_38_NO_BASE_OUTPUTS_READ',
 boundary:{selection:'SCRIPT_AND_GT_ONLY',agent_group_runs:0,rule_group_runs:0,experiment_output_files_opened:[],
  c_scope:'New multi-exit returns validated by GT camera-set change; top3 rank UNKNOWN because no group outputs are read.',
  independence:'Repeated events in seven authored clips; cluster by clip. GT windows are deduplicated at 1 cm position resolution; not independent trials or proven identical pixels.',
  gt:'A-private renderer/evaluation only; no GT in shared PNG/index or prompts'}};
fs.writeFileSync(path.join(out,'browser-replay.json'),JSON.stringify(browser,null,2)+'\n');
fs.writeFileSync(freezeFile,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({new_points:count,combined_h4:count+3,combined_primary:count+38,gt_freeze_sha256:sha(fs.readFileSync(freezeFile))}));

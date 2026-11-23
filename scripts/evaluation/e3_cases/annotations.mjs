// Evaluation-only event annotations. Never imported by LIVE, indexing or ranking.
import fs from 'node:fs';
import path from 'node:path';
import {read,sha} from './generate.mjs';
import {E3_ROUTES} from './routes.mjs';
import {setup} from './generate.mjs';
import {projectBox} from '../../../frontend/live-mode/src/person.mjs';
const [outArg,assets,...ids]=process.argv.slice(2),out=path.resolve(outArg);
if(!assets)throw new Error('usage: annotations.mjs OUT ASSETS [CASE_IDS...]');
const env=setup(assets);
const actor=(r,id='T')=>r.actors.find(a=>a.id===id);
const distance=(a,b)=>Math.hypot(a.xy[0]-b.xy[0],a.xy[1]-b.xy[1]);
function point(rows,index,type,expected){
 const r=rows[index];if(!r)throw new Error('POINT_OUTSIDE_RECORDING');
 return {tick:r.tick,timestamp_us:r.tick*200000,type,expected,
  cameras:actor(r).gt_visible,source_ref:`ticks[${index}]`};
}
const summaries=[];
for(const id of ids.length?ids:Object.keys(E3_ROUTES)){
 const log=read(path.join(out,`${id}.replay1.a-log.json`)),rows=log.ticks,route=E3_ROUTES[id],gaps=[];
 for(let i=1,start=null;i<rows.length;i++){
  if(!actor(rows[i]).gt_visible.length){if(start===null)start=i;}
  else if(start!==null){gaps.push({start,end:i,duration_s:(i-start)/5});start=null;}
 }
 let points=[],diagnostic_events=[],metrics={script_wrap_times_s:Array.from({length:Math.floor(rows.at(-1).tick/5/(route.run_id==='A4-1'?50:42))},(_,i)=>(i+1)*(route.run_id==='A4-1'?50:42)),gaps:gaps.map(g=>({start_tick:rows[g.start].tick,end_tick:rows[g.end].tick,duration_s:g.duration_s}))};
 if(route.family==='A'){
  const pairs=rows.flatMap((r,i)=>['A','B'].flatMap(who=>{const a=actor(r,who),t=actor(r);
   return a.present&&t.gt_visible.some(c=>a.gt_visible.includes(c))?[{i,who,d:distance(t,a)}]:[];}));
  const closest=pairs.reduce((a,b)=>a.d<b.d?a:b);
  if(closest.d>1)throw new Error(`${id}:NO_SIMILAR_CROSSING`);
  const near=pairs.filter(p=>p.who===closest.who&&p.i<=closest.i&&p.d<=2).at(0).i;
  const close=pairs.filter(p=>p.who===closest.who&&p.i<=closest.i&&p.d<=1).at(0).i;
  const split=rows.findIndex((r,i)=>i>closest.i&&(!actor(r,closest.who).present||distance(actor(r),actor(r,closest.who))>=3));
  if(split<0||split+25>=rows.length)throw new Error(`${id}:NO_SPLIT_FOLLOWUP`);
  points=[point(rows,near,'SIMILAR_APPROACH','KEEP_T_UNCONFIRMED'),
   point(rows,close,'CROSS_AMBIGUITY','DO_NOT_CONFIRM_SAME_COLOR_IDENTITY'),
   point(rows,Math.max(close+1,closest.i),'CLOSEST_CROSSING','KEEP_T_OR_ABSTAIN'),
   point(rows,split,'CROSS_SPLIT','FOLLOW_T_NOT_DISTRACTOR'),
   point(rows,split+25,'POST_SPLIT_5S','REACQUIRE_T_WITHIN_REGISTERED_WINDOW')];
  metrics={...metrics,distractor:closest.who,min_separation_m:closest.d};
 }else if(route.family==='B'){
  const qualifying=gaps.filter(g=>g.duration_s>=3&&g.duration_s<=10);
  if(!qualifying.length)throw new Error(`${id}:NO_3_TO_10_SECOND_GAP`);
  const g=qualifying[0];
  points=qualifying.map(g=>point(rows,g.end,'REAPPEAR','REACQUIRE_T_WITHIN_3S'));
  diagnostic_events=qualifying.flatMap(g=>[
   point(rows,g.start,'BLIND_START','DECLARE_UNSEEN'),point(rows,g.start+5,'BLIND_1S','ABSTAIN_FROM_DISTRACTORS'),
   point(rows,g.start+15,'BLIND_3S','CONTINUE_SEARCH_WITH_UNCERTAINTY')]);
 }else if(route.family==='C'){
  const g=gaps.at(-1);if(!g)throw new Error(`${id}:NO_BRANCH_GAP`);
  points=[point(rows,g.start-1,'BRANCH_BEFORE_EXIT','FREEZE_B1_BASELINE'),point(rows,g.start,'BRANCH_UNSEEN','DO_NOT_FABRICATE_MATCH'),
   point(rows,g.end,'BRANCH_RETURN','SEARCH_OUTSIDE_ORIGINAL_TOP3'),
   point(rows,g.end+5,'BRANCH_RETURN_1S','FOLLOW_OBSERVED_T'),point(rows,g.end+15,'BRANCH_RETURN_3S','VERIFY_HANDOFF')];
  metrics={...metrics,baseline_tick:rows[g.start].tick,return_tick:rows[g.end].tick,return_cameras:actor(rows[g.end]).gt_visible};
 }else{
  const g=gaps[0];if(!g)throw new Error(`${id}:NO_OCCLUSION`);
  // D1 contrasts hiding behind a screen with entry into the separate room;
  // D2 contrasts that screen with physically walking out of every camera frustum.
  const after=g.end+1;
  let exit=rows.findIndex((r,i)=>i>after&&actor(rows[i-1]).gt_visible.some(c=>!actor(r).gt_visible.includes(c)));
  if(id==='E3-D2')exit=rows.findIndex((r,i)=>i>after&&!actor(r).gt_visible.length);
  if(exit<0)throw new Error(`${id}:NO_TRUE_EXIT`);
  diagnostic_events=[point(rows,g.start,'SCREEN_OCCLUSION','ABSTAIN_WHILE_OCCLUDED'),
   point(rows,g.start+5,'SCREEN_OCCLUSION_1S','DO_NOT_CALL_DISTRACTOR_T'),
   point(rows,exit,'TRUE_CAMERA_EXIT','SWITCH_OR_DECLARE_UNSEEN'),
   point(rows,exit+5,'EXIT_1S','DO_NOT_CLAIM_OLD_CAMERA_STILL_SEES_T')];
  points=[point(rows,g.start-1,'SCREEN_BEFORE_OCCLUSION','KEEP_T_THEN_ABSTAIN'),
   point(rows,g.end,'SCREEN_RETURN','REACQUIRE_AFTER_OCCLUSION'),
   point(rows,g.end+2,'SCREEN_RETURN_0_4S','VERIFY_RETURNED_T'),
   point(rows,id==='E3-D2'?exit-6:exit,'TRUE_EXIT_APPROACH','FOLLOW_T_OR_SWITCH'),
   point(rows,id==='E3-D2'?exit-1:exit+5,'TRUE_EXIT_BOUNDARY','FOLLOW_T_OR_DECLARE_EXIT')];
  metrics={...metrics,true_exit_tick:rows[exit].tick,true_exit_kind:id==='E3-D2'?'LEAVES_ALL_CAMERAS_NORTH_FRUSTUM':'LEAVES_CORRIDOR_CAMERA_ENTERING_ROOM',old_cameras:actor(rows[exit-1]).gt_visible,
   after_exit_cameras:actor(rows[exit]).gt_visible};
 }
 if(new Set(points.map(p=>p.tick)).size!==points.length)throw new Error(`${id}:DUPLICATE_POINTS`);
 const gt={schema_version:'live-ab.a-log.v1',session_id:log.session_id,run_id:log.run_id,actor_id:'T',
  config:{...log.config,case_id:id},ticks:rows.map(r=>({tick:r.tick,t_capture:r.t_capture,t_sim:r.tick/5,actors:r.actors.map(a=>({...a,gt_boxes:Object.fromEntries(a.gt_visible.map(cam=>[cam,projectBox(env.cams[cam].camera,env.world.root,a.xy[0],a.xy[1],320,180)]))}))})),
  provenance:{role:'EVALUATION_ONLY',visibility:'THREE_BODY_POINT_RAYS_STATIC_WALLS_NOT_ACTOR_OCCLUSION',
   gt_box_kind:'EXISTING_PROJECTBOX_0_5_X_0_5_X_1_75_M_PROXY_NOT_PIXEL_MASK',image_size_px:[320,180],
   identity_verdict:'UNCONFIRMED',physical_verdict:'UNKNOWN',source_a_log_sha256:sha(fs.readFileSync(path.join(out,`${id}.replay1.a-log.json`)))}};
 const legacy=structuredClone(gt);
 for(const r of legacy.ticks)for(const a of r.actors)delete a.gt_boxes;
 delete legacy.provenance.gt_box_kind;delete legacy.provenance.image_size_px;
 fs.mkdirSync(path.join(out,'gt'),{recursive:true});
 fs.writeFileSync(path.join(out,'gt',`${id}.a-log.json`),JSON.stringify(legacy));
 fs.mkdirSync(path.join(out,'gt-boxes'),{recursive:true});
 fs.writeFileSync(path.join(out,'gt-boxes',`${id}.a-log.json`),JSON.stringify(gt));
 summaries.push({case_id:id,family:route.family,duration_s:rows.at(-1).tick/5,cameras:log.config.cams,
  decision_points:points.map(p=>({...p,evaluation_window_us:[p.timestamp_us,p.timestamp_us+3000000]})),diagnostic_events,metrics,gt_path:`gt-boxes/${id}.a-log.json`,gt_sha256:sha(JSON.stringify(gt))});
}
fs.writeFileSync(path.join(out,ids.length?'annotations-sample.json':'annotations.json'),JSON.stringify(summaries,null,2)+'\n');
console.log(summaries.map(s=>({case_id:s.case_id,decision_points:s.decision_points.length,metrics:s.metrics})));

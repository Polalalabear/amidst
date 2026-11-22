import {createHash} from 'node:crypto';
// Evaluation-only GT event extraction. No inference, ranking, scores or B logs.
export function extractReappearances(rows,policy,{family='B'}={}){
 const target=r=>r.actors?.find(a=>(a.id??a.actor_id)==='T');
 const visible=r=>!!target(r)?.present&&target(r).gt_visible.length>0;
 for(const [i,r]of rows.entries())if(r.tick!==i||!target(r)||!Array.isArray(target(r).gt_visible))throw new Error('GT_GRID_REQUIRED');
 const points=[],diagnostics=[];
 let start=null;
 for(let i=1;i<rows.length;i++){
  if(!visible(rows[i])){if(start===null&&visible(rows[i-1]))start=i;continue;}
  if(start===null)continue;
  const gapStart=start;start=null;const duration=(i-gapStart)/5;
  const pre=Math.round(policy.pre_visible_s*5),post=Math.round(policy.post_visible_s*5);
  const before=target(rows[gapStart-1]).gt_visible,after=target(rows[i]).gt_visible;
  const reasons=[];
  if(duration<policy.min_blind_s||duration>policy.max_blind_s)reasons.push('BLIND_DURATION');
  if(!rows.slice(gapStart,i).every(r=>target(r).present))reasons.push('TARGET_NOT_PRESENT');
  if(gapStart<pre||!rows.slice(gapStart-pre,gapStart).every(visible))reasons.push('PRE_VISIBLE');
  if(i+post>=rows.length||!rows.slice(i,i+post+1).every(visible))reasons.push('POST_VISIBLE');
  if(family==='C'&&before.some(c=>after.includes(c)))reasons.push('NO_CAMERA_BRANCH_CHANGE');
  const event={gap_start_tick:gapStart,last_visible_tick:gapStart-1,return_tick:i,blind_duration_s:duration,
   from_cameras:before,to_cameras:after};
  if(reasons.length){diagnostics.push({...event,reasons});continue;}
  points.push({...event,tick:i,timestamp_us:i*200000,type:'REAPPEAR',expected:'REACQUIRE_T_WITHIN_3S',
   cameras:after,evaluation_window_us:[i*200000,i*200000+3000000],source_ref:`ticks[${i}]`,
   h4_reappearance:true});
 }
 return {points,diagnostics};
}

// Conservative anti-repeat check over the full three-second GT scene window.
// Actor positions are quantized to 1 cm; this is not a pixel-identity claim.
export function deduplicateGTWindows(items,{round_m=.01,window_s=3}={}){
 const seen=new Map(),result=[];
 for(const item of items){
  const points=[],duplicates=[];
  for(const point of item.points){
   const window=item.rows.slice(point.tick,point.tick+Math.round(window_s*5)+1).map(row=>
    [...row.actors].sort((a,b)=>a.id.localeCompare(b.id)).map(actor=>{
     if(actor.present&&(!Array.isArray(actor.xy)||actor.xy.length!==2))throw new Error('GT_POSITION_REQUIRED');
     return [actor.id,actor.present,actor.xy?.map(v=>Math.round(v/round_m)*round_m)??null,[...actor.gt_visible].sort()];
    }));
   const digest=createHash('sha256').update(JSON.stringify([item.renderer_run_id,window])).digest('hex');
   const entry={...point,gt_window_sha256:digest};
   if(seen.has(digest))duplicates.push({...entry,duplicate_of:seen.get(digest),exclusion_reason:'DUPLICATE_GT_WINDOW_1CM'});
   else{seen.set(digest,point.point_id);points.push(entry);}
  }
  result.push({case_id:item.case_id,points,duplicates});
 }
 return result;
}

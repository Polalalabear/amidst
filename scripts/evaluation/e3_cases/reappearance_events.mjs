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

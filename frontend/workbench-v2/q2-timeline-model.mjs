export function timelineModel(response,decisions=[],{review=false}={}) {
  const timeline=response?.timeline??[];if(!timeline.length)return {range_us:null,segments:[],points:[]};
  const start=timeline[0].range_us[0],end=timeline.at(-1).range_us[1],span=end-start;
  return {range_us:[start,end],segments:timeline.map(s=>({id:s.segment_id,kind:s.kind,range_us:s.range_us,left:(s.range_us[0]-start)/span*100,width:(s.range_us[1]-s.range_us[0])/span*100,
    label:s.kind==='ON_CAMERA'?`OBS ${s.camera_id}`:'GAP · 觀測缺失',camera:s.kind==='ON_CAMERA'?s.camera_id:s.camera_shown,position:null})),
    points:review?decisions.filter(d=>d.source_time_us>=start&&d.source_time_us<=end).map(d=>({decision_id:d.decision_id,source_time_us:d.source_time_us,left:(d.source_time_us-start)/span*100,step_index:d.step_index,decided_by:d.decided_by,action:d.executed_action,accepted:d.accepted})):[]};
}

import {createGridState,pageView} from './player-grid.mjs';
import {buildQ2} from './q-api.mjs';
export function wallModel(response,{size=4,page=0}={}) {
  if(!response)return {message:'尚未載入查詢結果。',groups:{matches:[],noMatch:[],notEvaluated:[]},tiles:[],page:0,pages:1};
  const messages={NO_MATCH:'在已推論的影格中沒有找到；不代表目標不存在。',OUT_OF_RANGE:'請求時間和資料沒有交集，沒有查詢。',PARTIAL:response.reason==='TIME_BUDGET'?'搜尋時間已用完，僅顯示已評估部分。':'只涵蓋部分時間或影格；未涵蓋部分沒有資料，不代表沒有目標。',UNKNOWN:'資料不足，無法判定。',GRAPH_NOT_APPROVED:'區域圖尚未核准，沒有執行區域查詢。',UNSUPPORTED_CLASS:'不支援此類別。',UNSUPPORTED_CONDITION:'不支援此條件。',INVALID_QUERY:'查詢條件無效。',READY:'片段表示取樣影格有相符，不表示每一格皆相符。'};
  const results=response.results??[];const grid=pageView(createGridState({candidates:results.map(x=>x.camera_id),size,page}));
  return {status:response.status,message:messages[response.status]??'資料不足，沒有執行。',reason:response.reason,
    groups:{matches:results,noMatch:response.no_match_cameras,notEvaluated:response.not_evaluated_cameras},
    tiles:grid.slots.map(x=>x.kind==='EMPTY'?null:results.find(r=>r.camera_id===x.camera_id)),layout:grid.layout,page:grid.page,pages:grid.page_count,
    total:response.results_total,returned:response.returned_count,nextCursor:response.next_cursor,
    ranking:'排序依據：第一次相符時間 → camera_id；建議檢視順序，非機率。'};
}
export function seedRequest(response,result,segment,run,session,switchMode='RULE_ONLY',observationId=null) {
  if(!response.results.includes(result)||!result.matched_segments.includes(segment))throw new Error('UNBOUND_SEGMENT');
  const ids=segment.representative.observation_ids;
  if(!ids.length||!observationId&&ids.length!==1)throw new Error('OBSERVATION_SELECTION_REQUIRED');
  const id=observationId??ids[0];if(!ids.includes(id))throw new Error('UNBOUND_OBSERVATION');
  if(response.resolved_scope.scene_id!==run.scene_id||!response.resolved_scope.run_ids.includes(run.run_id))throw new Error('SOURCE_MISMATCH');
  return buildQ2(run,session,{kind:'OBSERVATION',observation_id:id},{time:response.resolved_scope.requested_time,switch_mode:switchMode});
}
export function segmentSelection(result,segment){return {kind:'Q1_SEGMENT',camera_id:result.camera_id,range_us:segment.range_us};}
// Union of one camera's matched segments; used to clamp that camera's frame while the shared wall clock runs.
export function cameraRange(result){const r=result.matched_segments.map(x=>x.range_us);return r.length?[Math.min(...r.map(x=>x[0])),Math.max(...r.map(x=>x[1]))]:null;}
// Play every hit camera of the page on one clock (no single highlighted camera).
export function wallSelection(results){const ranges=results.map(cameraRange).filter(Boolean);return ranges.length?{kind:'Q1_SEGMENT',camera_id:null,range_us:[Math.min(...ranges.map(x=>x[0])),Math.max(...ranges.map(x=>x[1]))]}:null;}
// Per-camera source stamp at clock tUs. Hit = tUs lies in the union of the camera's half-open segments [a,b); gaps between segments are NOT hits
// (cameraRange's min/max envelope only sets the wall's overall play range). In a gap or outside, freeze on the nearest legal frame and flag outside:true.
// Legal points are a (segment start) and b-1 (last legal microsecond of a segment). Equal distance → the earlier point (previous segment's end) wins.
export function wallStamps(results,tUs,intervalFor){
  return results.map(result=>{const segs=result.matched_segments.map(x=>x.range_us).filter(r=>r[1]>r[0]);if(!segs.length)return null;const interval=intervalFor(result.camera_id);
    const hit=segs.some(([a,b])=>tUs>=a&&tUs<b);let legal=tUs;
    if(!hit){const pts=segs.map(([a,b])=>tUs<a?a:b-1);legal=pts.reduce((best,p)=>{const d=Math.abs(p-tUs),e=Math.abs(best-tUs);return d<e||d===e&&p<best?p:best;});}
    return {camera_id:result.camera_id,stamp:Math.floor(legal/interval)*interval,outside:!hit};}).filter(Boolean);
}
export function groupByStamp(stamps){const g=new Map();for(const x of stamps){if(!g.has(x.stamp))g.set(x.stamp,[]);g.get(x.stamp).push(x.camera_id);}return g;}
export function coverageText(c={}) {return `已推論 ${c.evaluated_frames??0} · 未取樣 ${c.not_sampled_frames??0} · 未推論 ${c.not_inferred_frames??0} · MISSING ${c.missing_frames??0}`;}
// Raw detector boxes may be outside the image. Clipping is presentation only.
export function overlayBoxes(observations,{width,height,frameRef,cameraId,containerWidth=width,containerHeight=height}={}) {
  if(!(width>0&&height>0))return [];
  return observations.filter(x=>x.frame_ref===frameRef&&x.camera_id===cameraId&&Array.isArray(x.bbox_xyxy_px)&&x.bbox_xyxy_px.every(Number.isFinite)).map(x=>{
    const [l,t,r,b]=x.bbox_xyxy_px,scale=Math.min(containerWidth/width,containerHeight/height),padX=(containerWidth-width*scale)/2,padY=(containerHeight-height*scale)/2;return {observation_id:x.observation_id,raw:x.bbox_xyxy_px,left:(padX+Math.max(0,l)*scale)/containerWidth*100,top:(padY+Math.max(0,t)*scale)/containerHeight*100,right:(padX+Math.min(width,r)*scale)/containerWidth*100,bottom:(padY+Math.min(height,b)*scale)/containerHeight*100};
  }).filter(x=>x.right>x.left&&x.bottom>x.top);
}

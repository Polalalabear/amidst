// Pure model of the tracking 俯視圖 (UI-C, DEMO_UI_SUPPORT_V1 §7). Display only: no scoring, no Q5 input.
// Every field is read through a whitelist, so decoy keys (gt_*, actor_id, renderer_trajectory, visibility, depth, script…)
// can neither be drawn nor change the drawing. Replay at time t uses only data with source_time_us <= t.
export const SYNTHETIC_NOTE='SYNTHETIC／待接後端';
export const PHYSICAL_LEGEND='虛線＝最可能的一條物理預測（排序第 1；示意，非實際路徑）';
export const RANK_UNKNOWN_NOTE='預測排序 UNKNOWN，不畫虛線';
export const EXTERNAL_LABEL='外部模型推測（非系統判斷）';
export const EXTERNAL_UNAVAILABLE='外部推測不可用';
export const IDENTITY_LINE='身分未確認 · 物理通行與碰撞 UNKNOWN';
export const NODE_GRAPH_NOTE='示意圖，非實際座標';
export const METRIC_NOTE='靜態校正位置（示意，無遮擋計算）';
export const CONFIDENCE_STYLE=Object.freeze({
  HIGH:Object.freeze({label:'較高',dash:'7 4',opacity:1,width:2.4,tone:'int'}),
  MEDIUM:Object.freeze({label:'中',dash:'7 4',opacity:.85,width:2,tone:'int'}),
  LOW:Object.freeze({label:'低',dash:'4 5',opacity:.55,width:1.6,tone:'int'}),
  UNKNOWN:Object.freeze({label:'未知',dash:'1.5 4',opacity:.9,width:1.6,tone:'unk'}),
});
export const LIKELIHOOD_ZH=Object.freeze({HIGH:'高',MEDIUM:'中',LOW:'低'});
export const VIEW_W=320,VIEW_H=200;
const PAD=34;
const isNum=x=>typeof x==='number'&&Number.isFinite(x);
const isObj=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const str=x=>typeof x==='string'&&x.length>0?x:null;
export function hms(us) {
  if(!isNum(us)||us<0)return 'UNKNOWN';
  const s=Math.floor(us/1e6),p=n=>String(n).padStart(2,'0');
  return `${p(Math.floor(s/3600))}:${p(Math.floor(s/60)%60)}:${p(s%60)}`;
}
export function windowText(w) {
  return Array.isArray(w)&&w.length===2&&w.every(isNum)?`${hms(w[0])}–${hms(w[1])}`:'時間窗 UNKNOWN';
}
// ---- whitelist readers --------------------------------------------------------------------------------------------
export function readCameraMap(doc) {
  if(!isObj(doc)||doc.schema_version!=='q-demo.camera-map.v1'||doc.gt_read!==false)return null;
  const cameras=(Array.isArray(doc.cameras)?doc.cameras:[]).filter(c=>isObj(c)&&str(c.camera_id)).map(c=>{
    const p=isObj(c.display_position)?c.display_position:{};
    const xy=p.status==='CALIBRATED_STATIC'&&Array.isArray(p.xy_m)&&p.xy_m.length===2&&p.xy_m.every(isNum)?[p.xy_m[0],p.xy_m[1]]:null;
    return {camera_id:c.camera_id,role:['TRACKING','QUERY_ONLY','NOT_IN_GRAPH'].includes(c.role)?c.role:'NOT_IN_GRAPH',xy_m:xy};
  }).sort((a,b)=>a.camera_id<b.camera_id?-1:1);
  const transitions=(Array.isArray(doc.transitions)?doc.transitions:[]).filter(t=>isObj(t)&&str(t.from_camera_id)&&str(t.to_camera_id)).map(t=>({
    transition_id:str(t.transition_id),from:t.from_camera_id,to:t.to_camera_id,relation:str(t.relation),authority:t.authority==='APPROVED'?'APPROVED':'DRAFT',
    unknown_state:t.path_has_unknown_state!==false||(isObj(t.edge_states)||Array.isArray(t.edge_states)?JSON.stringify(t.edge_states).includes('UNKNOWN'):false)}));
  return {layout:doc.layout==='METRIC_STATIC'?'METRIC_STATIC':'NODE_GRAPH',cameras,transitions,g4_approved:doc.graph?.g4_approved===true,graph_status:str(doc.graph?.approval_status)};
}
export function readPhysical(doc) {
  if(!isObj(doc)||doc.schema_version!=='q-demo.physical-prediction.v1'||doc.gt_read!==false||doc.used_for!=='DISPLAY_ONLY')return null;
  if(!isNum(doc.as_of_us)||!str(doc.last_camera_id))return null;
  const candidates=(Array.isArray(doc.candidates)?doc.candidates:[]).filter(c=>isObj(c)&&str(c.camera_id)).map((c,i)=>({
    camera_id:c.camera_id,rank:isNum(c.rank)?c.rank:i+1,rank_known:isNum(c.rank),window_us:c.window_us,confidence:Object.hasOwn(CONFIDENCE_STYLE,c.confidence)?c.confidence:'UNKNOWN',
    relation:str(c.relation),traversability:str(c.path_traversability),unknown_state:c.path_has_unknown_state!==false}));
  return {as_of_us:doc.as_of_us,last_camera_id:doc.last_camera_id,last_observed_us:isNum(doc.last_observed_us)?doc.last_observed_us:null,
    candidates,status:str(doc.status),graph_approved:doc.graph_approval_status==='APPROVED',direction_known:doc.direction?.status==='KNOWN'};
}
export function readExternal(doc) {
  if(!isObj(doc)||doc.schema_version!=='q-demo.external-prediction.v1'||doc.gt_read!==false||doc.used_for!=='DISPLAY_ONLY'||doc.scoring_use!==false)return null;
  if(doc.status!=='AVAILABLE')return {status:'UNAVAILABLE',reason:str(doc.reason),candidates:[],as_of_us:isNum(doc.as_of_us)?doc.as_of_us:null};
  const candidates=(Array.isArray(doc.candidates)?doc.candidates:[]).filter(c=>isObj(c)&&str(c.camera_id)&&Object.hasOwn(LIKELIHOOD_ZH,c.likelihood)).slice(0,3)
    .map(c=>({camera_id:c.camera_id,likelihood:c.likelihood}));
  return {status:'AVAILABLE',reason:null,candidates,as_of_us:isNum(doc.as_of_us)?doc.as_of_us:null};
}
// ---- observed path ------------------------------------------------------------------------------------------------
// Only ON_CAMERA/GAP segments that began at or before t count; later segments are never read past the filter.
export function observedPath(timeline,tUs) {
  const seen=(Array.isArray(timeline)?timeline:[]).filter(s=>isObj(s)&&Array.isArray(s.range_us)&&isNum(s.range_us[0])&&s.range_us[0]<=tUs);
  const cameras=[];let gap=null,last=null;
  for(const s of seen) {
    if(s.kind==='ON_CAMERA'&&str(s.camera_id)){if(cameras.at(-1)!==s.camera_id)cameras.push(s.camera_id);last={camera_id:s.camera_id,start_us:s.range_us[0],end_us:s.range_us[1]};gap=null;}
    else if(s.kind==='GAP')gap={camera_shown:str(s.camera_shown),states:Array.isArray(s.gap_states)?s.gap_states.filter(x=>typeof x==='string'):[]};
  }
  const lastObservedUs=last?Math.min(last.end_us,tUs):null;
  return {cameras,edges:cameras.slice(1).map((to,i)=>({from:cameras[i],to})),current:last?.camera_id??null,inGap:Boolean(gap),gap,lastObservedUs};
}
// ---- layout -------------------------------------------------------------------------------------------------------
export function layoutNodes(map,ids) {
  const all=[...new Set(ids)].sort();
  const withXy=map?.cameras.filter(c=>c.xy_m)??[];
  const metric=map?.layout==='METRIC_STATIC'&&all.length>0&&all.every(id=>withXy.some(c=>c.camera_id===id));
  if(metric) {
    const pts=all.map(id=>withXy.find(c=>c.camera_id===id).xy_m);
    const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const x0=Math.min(...xs),y0=Math.min(...ys);
    const sx=Math.max(Math.max(...xs)-x0,1e-9),sy=Math.max(Math.max(...ys)-y0,1e-9);
    const k=Math.min((VIEW_W-2*PAD)/sx,(VIEW_H-2*PAD-30)/sy);
    const ox=(VIEW_W-sx*k)/2,oy=(VIEW_H-30-sy*k)/2;
    return {mode:'METRIC_STATIC',note:METRIC_NOTE,positions:Object.fromEntries(all.map((id,i)=>[id,[ox+(pts[i][0]-x0)*k,VIEW_H-30-oy-(pts[i][1]-y0)*k]]))};
  }
  // Fixed fallback: ids on an ellipse in sorted order. Depends on nothing but the id list.
  const n=all.length,cx=VIEW_W/2,cy=(VIEW_H-30)/2,rx=VIEW_W/2-PAD-8,ry=cy-PAD+4;
  return {mode:'NODE_GRAPH',note:NODE_GRAPH_NOTE,positions:Object.fromEntries(all.map((id,i)=>{
    const a=n===1?0:-Math.PI/2+i*2*Math.PI/n;return [id,[round(cx+rx*Math.cos(a)),round(cy+ry*Math.sin(a))]];}))};
}
const round=x=>Math.round(x*10)/10;
// ---- scene --------------------------------------------------------------------------------------------------------
export function buildScene({cameraMap=null,timeline=[],tUs,physical=null,external=null,externalEnabled=false,origin='SYNTHETIC',sourceNote=null,runCameraIds=null}) {
  const map=cameraMap?readCameraMap(cameraMap):null;
  const path=observedPath(timeline,tUs);
  // Cameras come from the map, else from the run's camera list (bootstrap), else only from segments already begun at t.
  // The full timeline is never used for the node set: a camera first seen after t must not appear before t.
  const ids=map?map.cameras.map(c=>c.camera_id):(Array.isArray(runCameraIds)&&runCameraIds.length?runCameraIds.filter(str):path.cameras);
  const layout=layoutNodes(map,ids);
  const roleOf=id=>map?.cameras.find(c=>c.camera_id===id)?.role??'TRACKING';
  const nodes=[...new Set(ids)].sort().map(id=>({camera_id:id,xy:layout.positions[id],role:roleOf(id),current:id===path.current,observed:path.cameras.includes(id)}));
  const has=id=>nodes.some(n=>n.camera_id===id);
  const observed=path.edges.filter(e=>has(e.from)&&has(e.to));
  const seenPair=new Set(),graphEdges=[];
  for(const t of map?.transitions??[]) {
    const key=[t.from,t.to].sort().join('|');if(seenPair.has(key)||!has(t.from)||!has(t.to)||roleOf(t.from)!=='TRACKING'||roleOf(t.to)!=='TRACKING')continue;
    seenPair.add(key);graphEdges.push({from:t.from,to:t.to,title:`${t.from}→${t.to} · ${t.authority==='APPROVED'?'圖已核准':'圖未核准（DRAFT）'}${t.unknown_state?' · 通行狀態未知':''}`});
  }
  const notes=[];
  if(origin!=='API')notes.push(sourceNote?`${SYNTHETIC_NOTE} · ${sourceNote}`:SYNTHETIC_NOTE);
  // Physical prediction: ignored when computed for a later time than t (scrubbed backwards) or from a camera not yet observed.
  const pred=physical?readPhysical(physical):null;
  const usable=pred&&pred.as_of_us<=tUs&&(pred.last_observed_us===null||pred.last_observed_us<=tUs)&&path.cameras.includes(pred.last_camera_id)&&has(pred.last_camera_id);
  const predicted=[];
  // Only the most likely path is drawn: the candidate with the lowest data-provided rank (first in data order on a tie).
  // No rank in the data -> rank UNKNOWN, nothing is drawn (no new metric is invented).
  const ranked=usable?pred.candidates.filter(c=>c.rank_known):[];
  const top=ranked.length?ranked.reduce((a,c)=>c.rank<a.rank?c:a):null;
  const rankUnknown=Boolean(usable&&pred.candidates.length&&!top);
  if(top)for(const c of [top]) {
    if(!has(c.camera_id))continue;
    const st=CONFIDENCE_STYLE[c.confidence];
    const warn=[!pred.graph_approved?'圖未核准（DRAFT）':null,c.unknown_state?'通行狀態未知':null,c.confidence==='UNKNOWN'?'方向未知，信心未知':null].filter(Boolean);
    predicted.push({from:pred.last_camera_id,to:c.camera_id,rank:c.rank,confidence:c.confidence,style:st,
      label:`#${c.rank} ${windowText(c.window_us)} · ${st.label}`,title:`物理預測 #${c.rank} → ${c.camera_id}${warn.length?' · '+warn.join(' · '):''}`});
  }
  if(rankUnknown)notes.push(RANK_UNKNOWN_NOTE);
  if(usable&&pred.as_of_us<tUs)notes.push(`預測取自 ${hms(pred.as_of_us)}`);
  // External guess: off by default; when on, drawn only if AVAILABLE and not computed after t.
  const ext=externalEnabled&&external?readExternal(external):null;
  const extOk=ext&&ext.status==='AVAILABLE'&&(ext.as_of_us===null||ext.as_of_us<=tUs);
  const extFrom=usable?pred.last_camera_id:path.current;
  const externalLines=extOk&&extFrom&&has(extFrom)?ext.candidates.filter(c=>has(c.camera_id)&&c.camera_id!==extFrom)
    .map(c=>({from:extFrom,to:c.camera_id,likelihood:c.likelihood,label:`${EXTERNAL_LABEL} · ${LIKELIHOOD_ZH[c.likelihood]}`,title:`${EXTERNAL_LABEL} → ${c.camera_id}`})):[];
  const externalUnavailable=Boolean(externalEnabled&&(!ext||(ext.status==='UNAVAILABLE')));
  return {layout:layout.mode,layoutNote:layout.note,origin,nodes,graphEdges,observed,predicted,externalLines,externalUnavailable,externalEnabled:Boolean(externalEnabled),
    current:path.current,inGap:path.inGap,gap:path.gap,notes,tUs,identityLine:IDENTITY_LINE,legend:PHYSICAL_LEGEND,
    empty:nodes.length===0,placeholderNote:path.cameras.length?null:'尚無已觀測的鏡頭段'};
}

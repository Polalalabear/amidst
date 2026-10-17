// A5: selecting one source observation is display-only. Everything here reads records the backend already returned
// (POST /api/target_reconstruction: selected_observation and review_evidence.endpoints); nothing is guessed from time,
// and the selection is never part of any request. Missing fields stay MISSING / UNKNOWN.
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const REF=/^observation:[0-9a-f]{24}$/;
const box=v=>Array.isArray(v)&&v.length===4&&v.every(finite)&&v[2]>v[0]&&v[3]>v[1]?[...v]:null;
const pair=v=>Array.isArray(v)&&v.length===2&&v.every(finite)?[...v]:null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fixed2=v=>finite(v)?v.toFixed(2):'UNKNOWN';

// ref -> record. selected_observation carries bbox/contact; the interval endpoints carry only a ground estimate.
export function observationRecordsFromResponse(response) {
  const records={};
  const sel=response?.selected_observation;
  const endpoints=Array.isArray(response?.review_evidence?.endpoints)?response.review_evidence.endpoints:[];
  for(const item of endpoints){
    const g=item?.ground_estimate,ref=g?.observation_ref??item?.observation_ref;
    if(typeof ref!=='string'||!REF.test(ref))continue;
    records[ref]={observation_ref:ref,camera_id:g?.camera_id??item?.camera_id??null,timestamp:finite(g?.timestamp_s)?g.timestamp_s:(finite(item?.timestamp_s)?item.timestamp_s:null),
      frame_ref:null,bbox_xyxy:null,contact_pixel:null,ground_estimate:g??null,world_position:undefined,source:'review_evidence.endpoints'};
  }
  if(sel&&typeof sel.observation_ref==='string'&&REF.test(sel.observation_ref)){
    records[sel.observation_ref]={observation_ref:sel.observation_ref,camera_id:sel.camera_id??null,timestamp:finite(sel.timestamp)?sel.timestamp:null,
      frame_ref:typeof sel.frame_ref==='string'?sel.frame_ref:null,bbox_xyxy:box(sel.bbox_xyxy),contact_pixel:pair(sel.contact_pixel),
      ground_estimate:sel.ground_estimate??null,world_position:sel.world_position===null?null:Array.isArray(sel.world_position)?sel.world_position:undefined,
      measurement_status:sel.measurement_status??null,projection_status:sel.projection_status??null,projection_reason:sel.projection_reason??null,source:'selected_observation'};
  }
  return records;
}
export const intervalEndRef=response=>{const ref=response?.blind_hypotheses?.interval?.end_observation_ref;return typeof ref==='string'&&REF.test(ref)?ref:null;};

const runsOf=state=>state?.demoBlindRuns&&state.demoBlindRuns.sceneId===state.sceneId?state.demoBlindRuns:{};
export function knownObservations(state) {
  const out={};
  for(const mode of ['BASELINE','NONE'])Object.assign(out,runsOf(state)[mode]?.observations??{});
  return out;
}
export const selectedObservation=state=>state?.selectedObservationRef?knownObservations(state)[state.selectedObservationRef]??null:null;

// Which observation a step selects: a fixed ref, or the interval's far endpoint as the backend reported it.
export function stepSelectionRef(step,state) {
  if(step?.select_observation==='selection')return step.selection??null;
  if(step?.select_observation==='interval_end')return runsOf(state).NONE?.interval_end_ref??null;
  return null;
}

// Overlay on the observation's own camera tile and exact frame (frame_ref, else the identical timestamp). Needs a source bbox.
export function observationOverlayItems(state,cameraId,frame) {
  if(!frame)return [];
  const selected=state?.selectedObservationRef;
  return Object.values(knownObservations(state)).filter(r=>r.bbox_xyxy&&r.camera_id===cameraId&&
    (r.frame_ref&&(frame.frame_ref??frame.ref)?r.frame_ref===(frame.frame_ref??frame.ref):finite(r.timestamp)&&finite(frame.timestamp)&&Math.abs(r.timestamp-frame.timestamp)<1e-6))
    .map(r=>({observation_ref:r.observation_ref,bbox_xyxy:r.bbox_xyxy,contact_pixel:r.contact_pixel,selected:r.observation_ref===selected}));
}
export function observationOverlaySVG(items,{width,height}={}) {
  if(!items.length||!finite(width)||!finite(height)||width<=0||height<=0)return '';
  const n=v=>Number(v.toFixed(2)),size=Math.max(width,height),thin=n(size*.002),thick=n(size*.006),arm=n(size*.012);
  const shapes=items.map(item=>{
    const [x0,y0,x1,y1]=item.bbox_xyxy,c=item.contact_pixel,sw=item.selected?thick:thin,color=item.selected?'#ffd23f':'#76d9cf';
    const cross=c?`<path d="M${n(c[0]-arm)},${n(c[1])} H${n(c[0]+arm)} M${n(c[0])},${n(c[1]-arm)} V${n(c[1]+arm)}" stroke="${color}" stroke-width="${sw}" fill="none"/>`:'';
    return `<g data-observation-ref="${esc(item.observation_ref)}" data-observation-selected="${item.selected}"><rect x="${n(x0)}" y="${n(y0)}" width="${n(x1-x0)}" height="${n(y1-y0)}" fill="${item.selected?'rgba(255,210,63,.12)':'none'}" stroke="${color}" stroke-width="${sw}" style="pointer-events:all;cursor:pointer"/>${cross}</g>`;
  }).join('');
  return `<svg class="observation-overlay" data-observation-overlay viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none" aria-label="選定觀測框：像素 bbox 與接觸像素；僅供顯示">${shapes}</svg>`;
}

// What a 3D layer would draw for the ground interval. Returned only for a READY segment; scene layers that do not exist draw nothing.
export function groundHighlightPlan(record) {
  const g=record?.ground_estimate,s=g?.segment;
  if(!g||g.status!=='READY'||!s||!Array.isArray(s.near_m)||!Array.isArray(s.far_m))return null;
  return {observation_ref:record.observation_ref,near_m:[...s.near_m],far_m:[...s.far_m],length_m:finite(s.length_m)?s.length_m:null,basis:g.basis??null};
}

export function observationPanelHTML(state,{groundLayer=false}={}) {
  const r=selectedObservation(state);
  if(!state?.selectedObservationRef)return '';
  if(!r)return `<div data-observation-panel><strong>選定觀測</strong> <code>${esc(state.selectedObservationRef)}</code><br>詳細資料 UNAVAILABLE：尚未取得此觀測的後端紀錄。身分 UNCONFIRMED。</div>`;
  const g=r.ground_estimate,s=g?.segment;
  const ground=g&&g.status==='READY'&&s?`${esc(g.basis??'UNKNOWN')} · 長度 ${fixed2(s.length_m)} m`:`UNKNOWN${g?.reason?`（${esc(g.reason)}）`:''}`;
  const world=r.world_position===null?'MISSING':Array.isArray(r.world_position)?r.world_position.map(fixed2).join(', '):'UNKNOWN（此來源未提供）';
  const quality=g?.contact_quality?.status?` · 接地品質旗標 ${esc(g.contact_quality.status)}${(g.contact_quality.reasons??[]).length?`（${g.contact_quality.reasons.map(esc).join('、')}）`:''}`:'';
  return `<div data-observation-panel><strong>選定觀測</strong> <code>${esc(r.observation_ref)}</code>`+
    `<br>鏡頭 ${esc(r.camera_id??'UNKNOWN')} · 時間 ${finite(r.timestamp)?r.timestamp.toFixed(1):'UNKNOWN'} s`+
    `<br>接地區間：${ground}${quality}`+
    `<br>world_position：${world}`+
    `<br>身分 UNCONFIRMED · 僅影響顯示，不改變任何請求、排序或推論`+
    `<br><small data-ground-highlight="${groundLayer?'ON':'OFF'}">${groundLayer?'3D 接地區間已高亮':'3D 接地區間高亮：圖層尚未接上（待 K3 ground-estimate 圖層），目前只在 2D 標示'}</small></div>`;
}

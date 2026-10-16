import {presentationData} from './presentation-data.mjs';
import {cameraCoverageHTML} from './blender-motion.mjs';
import {contactQualityStyle} from './scene-presets.mjs';

const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list=value=>Array.isArray(value)?value:[];
const finitePoint=point=>Array.isArray(point)&&point.length===3&&point.every(Number.isFinite);
const range=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)&&value[1]>=value[0]?value:null;
const seconds=value=>Number.isFinite(value)?value.toFixed(1)+' s':'時間未知';
const interval=value=>range(value)?value.map(seconds).join('–'):'範圍未提供';
const states=new Set(['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION','INFERRED_CROSS_CAMERA']);
const derivativeStates=new Set(['INFERRED_FINITE_DIFFERENCE','INFERRED_CROSS_CAMERA']);
const colors=['#76d9cf','#c5a7f0','#e8c07c','#ef9da7','#96bded'];
const refKey=key=>/(?:^|_)(?:track|node|edge|path|candidate|association|event|observation|frame|interval|gap|geometry)_(?:ref|refs|id|ids)$/i.test(key);
export function crossCameraPresentation(value) {
  const refs=new Set();
  const collect=item=>{if(!item||typeof item!=='object')return;for(const [key,child] of Object.entries(item)){
    if(refKey(key))for(const ref of Array.isArray(child)?child:[child])if(typeof ref==='string')refs.add(ref);
    collect(child);
  }};
  collect(value);
  const clean=item=>{
    if(typeof item==='string'){
      let text=item.replace(/\b(?:track|motion-track|blender-track|association|association-node|association-edge|association-path|association-candidate|candidate|path|node|edge):[A-Za-z0-9_.:/-]+/g,'內部識別碼（見 log）');
      for(const ref of refs)if(ref)text=text.split(ref).join('內部識別碼（見 log）');return text;
    }
    if(Array.isArray(item))return item.map(clean);
    if(!item||typeof item!=='object')return item;
    return Object.fromEntries(Object.entries(item).filter(([key])=>!refKey(key)).map(([key,child])=>[key,clean(child)]));
  };
  return clean(presentationData(value));
}
const details=(label,value)=>`<details class="technical"><summary>${h(label)}</summary><pre>${h(JSON.stringify(crossCameraPresentation(value),null,2))}</pre></details>`;

export function invalidateCrossCamera(target) {
  target.crossCameraEpoch=(target.crossCameraEpoch??0)+1;target.crossCameraResult=null;target.crossCameraPending=false;target.crossCameraRank=1;target.crossCameraTimestamp=null;
}
export function crossCameraRequestIsCurrent(target,ticket) {
  return target.role==='research'&&target.sceneEpoch===ticket.sceneEpoch&&target.sceneId===ticket.sceneId&&
    target.session?.session_ref===ticket.sessionRef&&target.crossCameraEpoch===ticket.crossCameraEpoch;
}
export function validateCrossCameraResponse(result,request,snapshot) {
  const expected=snapshot?.source_binding??{},binding=result?.source_binding??{},selected=result?.selection??{};
  const candidates=list(result?.candidates);
  const selectedCameras=new Set(request.camera_ids);
  const invalidPaths=candidate=>!Array.isArray(candidate.paths)||candidate.paths.length>128||
    candidate.paths.some(path=>!Array.isArray(path.samples)||path.samples.length>4000||
      !Array.isArray(path.camera_ids)||path.camera_ids.some(id=>!selectedCameras.has(id))||
      path.samples.some(sample=>!Number.isFinite(sample?.timestamp)||sample.timestamp<request.start||sample.timestamp>request.end||sample.camera_id!==undefined&&sample.camera_id!==null&&!selectedCameras.has(sample.camera_id)));
  if(result?.schema_version!=='workbench.blender-association.v1'||result.agent_used!==false||
    !['READY','NO_RESULT','NO_CROSS_CAMERA_EVIDENCE'].includes(result.status)||
    !expected.run_id||!expected.source_sha256||binding.run_id!==expected.run_id||binding.source_sha256!==expected.source_sha256||
    JSON.stringify([...list(selected.camera_ids)].sort())!==JSON.stringify([...request.camera_ids].sort())||
    JSON.stringify(selected.time_range)!==JSON.stringify([request.start,request.end])||selected.top_k!==request.top_k||
    !Array.isArray(result.candidates)||candidates.length>request.top_k||
    candidates.some((candidate,index)=>candidate.rank!==index+1||invalidPaths(candidate))||
    result.baseline_candidate&&invalidPaths(result.baseline_candidate)||
    list(result.graph?.nodes).some(node=>node.camera_id&&!selectedCameras.has(node.camera_id)))throw Error('跨鏡頭還原的來源、鏡頭或查詢範圍不相符。');
  if(snapshot.baseline?.source_features&&result.source_features!==snapshot.baseline.source_features)throw Error('跨鏡頭還原使用了不同的像素索引。');
  if(result.status==='NO_RESULT'&&candidates.length)throw Error('缺失結果包含不相符的候選。');
  if(result.status==='NO_CROSS_CAMERA_EVIDENCE'&&candidates.length>1)throw Error('無跨鏡頭證據結果包含重複候選。');
  return result;
}
export async function runCrossCameraReconstruction(target,selection,send) {
  target.crossCameraResult=null;target.crossCameraPending=true;target.crossCameraRank=1;target.crossCameraTimestamp=null;
  const ticket={sceneEpoch:target.sceneEpoch,sceneId:target.sceneId,sessionRef:target.session?.session_ref,crossCameraEpoch:++target.crossCameraEpoch};
  const request={scene_id:ticket.sceneId,camera_ids:[...selection.camera_ids],start:selection.start,end:selection.end,top_k:selection.top_k};
  const snapshot=target.snapshot;
  try {
    const result=await send(request);if(!crossCameraRequestIsCurrent(target,ticket))return false;
    target.crossCameraResult=validateCrossCameraResponse(result,request,snapshot);target.crossCameraPending=false;return true;
  } catch(error) {if(!crossCameraRequestIsCurrent(target,ticket))return false;target.crossCameraPending=false;throw error;}
}
export function selectedCrossCameraCandidate(result,rank=1) {
  if(rank===0&&result?.baseline_candidate)return {...result.baseline_candidate,rank:0};
  return list(result?.candidates).find(candidate=>candidate.rank===rank)??list(result?.candidates)[0]??null;
}
export function crossCameraSegments(samples,timeRange) {
  const selected=range(timeRange),segments=[];let previous=null;
  for(const sample of list(samples)){
    if(!selected||!Number.isFinite(sample?.timestamp)||sample.timestamp<selected[0]||sample.timestamp>selected[1]||
      !finitePoint(sample.world_position)||!states.has(sample.state)){previous=null;continue;}
    if(previous&&sample.connect_from_previous===true&&sample.timestamp>previous.timestamp)segments.push({from:previous,to:sample,
      inferred:previous.state!=='PROJECTED_OBSERVATION'||sample.state!=='PROJECTED_OBSERVATION',
      crossCamera:previous.state==='INFERRED_CROSS_CAMERA'||sample.state==='INFERRED_CROSS_CAMERA'});
    previous=sample;
  }
  return segments;
}
export function crossCameraVelocitySegments(samples,timeRange) {
  const selected=range(timeRange),segments=[];let previous=null;
  for(const sample of list(samples)){
    const window=range(sample?.time_range);
    if(!selected||!window||!Number.isFinite(sample.timestamp)||sample.timestamp<selected[0]||sample.timestamp>selected[1]||
      !Number.isFinite(sample.speed_m_s)||sample.speed_m_s<0||!finitePoint(sample.velocity_xyz)||!derivativeStates.has(sample.state)){previous=null;continue;}
    if(previous&&sample.timestamp>previous.timestamp&&Math.abs(previous.time_range[1]-window[0])<1e-7)segments.push({from:previous,to:sample});
    previous=sample;
  }
  return segments;
}
const usableCursorSample=sample=>Number.isFinite(sample?.timestamp)&&finitePoint(sample.world_position)&&states.has(sample.state);
// Last sample of each connected run, using the same connection rule as the drawn path segments (connect_from_previous===true, later timestamp).
function cursorSegmentEnds(samples) {
  const ends=new Set();let previous=null;
  for(const sample of list(samples)){
    if(!usableCursorSample(sample)){if(previous)ends.add(previous);previous=null;continue;}
    if(previous&&!(sample.connect_from_previous===true&&sample.timestamp>previous.timestamp))ends.add(previous);
    previous=sample;
  }
  if(previous)ends.add(previous);
  return ends;
}
// The single cursor rule for the 3D cursor, panel clock and 2D evidence box: nearest usable sample within the sampling tolerance.
// A segment start never shows before its own time and a run's last sample is not held afterwards; a missing path is never extrapolated.
export function crossCameraCursor(path,timestamp,timeRange,{tolerance=.100001}={}) {
  const selected=range(timeRange);if(!selected||!Number.isFinite(timestamp)||timestamp<selected[0]||timestamp>selected[1])return null;
  const ends=cursorSegmentEnds(path?.samples);let best=null;
  for(const sample of list(path?.samples)){
    if(!usableCursorSample(sample)||Math.abs(sample.timestamp-timestamp)>tolerance)continue;
    if(sample.connect_from_previous!==true&&sample.timestamp>timestamp+1e-8)continue;
    if(ends.has(sample)&&sample.timestamp<timestamp-1e-8)continue;
    const distance=Math.abs(sample.timestamp-timestamp);
    if(!best||distance<best.distance-1e-9||Math.abs(distance-best.distance)<=1e-9&&sample.timestamp<best.sample.timestamp)best={sample,distance};
  }
  return best?.sample??null;
}
// Ground contact is never measured here. The producer's contact_pixel is the bottom centre of a visible pixel component's bbox,
// [(xmin+xmax-1)/2, ymax-1]; seats or other occluders move that edge, so its floor intersection is not a verified foot position.
// The basis is reported only when the sample's own bbox reproduces its contact pixel; otherwise it stays UNKNOWN.
export function groundContactBasis(sample) {
  const box=sample?.bbox_xyxy,contact=sample?.contact_pixel;
  const bottomCentre=Array.isArray(box)&&box.length===4&&box.every(Number.isFinite)&&Array.isArray(contact)&&contact.length===2&&contact.every(Number.isFinite)&&
    Math.abs(contact[0]-(box[0]+box[2]-1)/2)<=1e-6&&Math.abs(contact[1]-(box[3]-1))<=1e-6;
  return {contact_basis:bottomCentre?'VISIBLE_COMPONENT_BBOX_BOTTOM_CENTER':'UNKNOWN',ground_contact:'UNKNOWN'};
}
export const groundContactLabel=sample=>groundContactBasis(sample).contact_basis==='VISIBLE_COMPONENT_BBOX_BOTTOM_CENTER'?
  '接地 UNKNOWN（可見像素區塊 bbox 底緣中心，非已驗證腳點）':'接地 UNKNOWN（接觸像素來源未提供）';
// Short display name for a camera id (last token), used only in compact 3D/2D labels; the full id stays in panels.
export const cameraShortLabel=id=>typeof id==='string'&&id?id.split('_').filter(Boolean).pop()??id:'鏡頭未知';
const pathAssociated=(candidate,path)=>candidate.rank!==0&&list(path.edge_refs).length>0;
export function crossCameraScenePlan(result,rank=1) {
  const selected=selectedCrossCameraCandidate(result,rank),timeRange=range(result?.selection?.time_range);
  if(!selected||!timeRange)return {paths:[],time_range:timeRange,selected_rank:null};
  const candidates=[...list(result.candidates),...(rank===0?[selected]:[])];
  const edges=list(result.graph?.edges);
  return {time_range:timeRange,selected_rank:selected.rank,paths:candidates.flatMap(candidate=>list(candidate.paths).map((path,index)=>({
    key:`${candidate.rank}:${index+1}`,rank:candidate.rank,ordinal:index+1,selected:candidate.rank===selected.rank,associated:pathAssociated(candidate,path),
    color:colors[Math.max(0,candidate.rank-1)%colors.length],caption:`${candidate.rank===0?'未關聯基線':'候選 '+candidate.rank} · 路徑 ${index+1}`,
    samples:list(path.samples),segments:crossCameraSegments(path.samples,timeRange),
    associationCaptions:edges.filter(edge=>list(path.edge_refs).includes(edge.edge_ref)&&edge.bridge_missing!==true&&finitePoint(edge.from_world_position)&&finitePoint(edge.to_world_position)&&edge.from_timestamp>=timeRange[0]&&edge.to_timestamp<=timeRange[1])
      .map(edge=>({from:edge.from_world_position,to:edge.to_world_position,caption:edge.kind==='CROSS_CAMERA_CORROBORATING_OVERLAP'?'重疊觀測相容假設':'跨鏡頭關聯假設'})),
    missingAssociations:edges.filter(edge=>list(path.edge_refs).includes(edge.edge_ref)&&edge.bridge_missing===true&&
      finitePoint(edge.from_world_position)&&finitePoint(edge.to_world_position)&&edge.from_timestamp>=timeRange[0]&&edge.to_timestamp<=timeRange[1])
      .map(edge=>({from:edge.from_world_position,to:edge.to_world_position,caption:'關聯假設／中間位置缺失'})),
  })))};
}
// 2D counterpart of the 3D cursor: the selected candidate's displayed source sample on one camera tile, bound by exact frame_ref.
// Only original bbox/contact pixels are drawn; nothing is drawn for inferred or missing states or a frame from another time.
const pixelBox=box=>Array.isArray(box)&&box.length===4&&box.every(Number.isFinite)&&box[2]>=box[0]&&box[3]>=box[1];
export function candidateEvidenceOverlays(plan,timestamp,cameraId,frameRef) {
  if(!range(plan?.time_range)||typeof frameRef!=='string'||!frameRef||typeof cameraId!=='string')return [];
  return list(plan.paths).filter(path=>path.selected).flatMap(path=>{
    const sample=crossCameraCursor(path,timestamp,plan.time_range);
    if(!sample||sample.state!=='PROJECTED_OBSERVATION'||sample.camera_id!==cameraId||sample.frame_ref!==frameRef||!pixelBox(sample.bbox_xyxy)||
      !Array.isArray(sample.contact_pixel)||sample.contact_pixel.length!==2||!sample.contact_pixel.every(Number.isFinite))return [];
    return [{key:path.key,caption:path.caption,associated:path.associated===true,color:path.color,timestamp:sample.timestamp,
      bbox_xyxy:[...sample.bbox_xyxy],contact_pixel:[...sample.contact_pixel],measurement_status:sample.measurement_status??null,
      segment_start:sample.connect_from_previous!==true,...groundContactBasis(sample),
      ...(sample.contact_quality&&typeof sample.contact_quality==='object'?{contact_quality:sample.contact_quality}:{})}];
  });
}
export function candidateEvidenceSVG(items,{camera_id=null,width,height}={}) {
  if(!list(items).length||!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)return '';
  const n=value=>Number(value.toFixed(2)),size=Math.max(width,height),font=n(size*.02),stroke=n(size*.0025);
  // Captions stack in one column below the lowest box (or above the highest when it would leave the image), so simultaneous boxes never overlap text.
  const bottom=Math.max(...items.map(item=>item.bbox_xyxy[3])),top=Math.min(...items.map(item=>item.bbox_xyxy[1])),below=bottom+font*1.25*items.length<height;
  const shapes=items.map((item,index)=>{
    const [x0,y0,x1,y1]=item.bbox_xyxy,[u,v]=item.contact_pixel,arm=n(size*.012),color=/^#[0-9a-f]{6}$/i.test(item.color??'')?item.color:'#76d9cf';
    const quality=contactQualityStyle(item.contact_quality);
    const text=`${item.caption.replace(/ /g,'')}${item.associated?'':' · 未關聯'} · ${item.measurement_status??'量測狀態未提供'} · 接地 UNKNOWN${quality.label?' · '+quality.label:''}`;
    const ty=n(below?bottom+font*1.25*(index+1):Math.max(font*(index+1),top-font*.4-font*1.25*(items.length-1-index)));
    const tx=n(Math.min(Math.max(x0,0),Math.max(0,width-text.length*font*.62)));
    // A FLAGGED contact gets a dashed ring around the same contact pixel; the pixel itself is drawn where the source put it.
    const ring=quality.hollow?`<circle data-contact-flag cx="${n(u)}" cy="${n(v)}" r="${n(arm*1.6)}" fill="none" stroke="#ffc266" stroke-width="${stroke}" stroke-dasharray="${n(arm*.5)} ${n(arm*.35)}"/>`:'';
    return `<g data-candidate-evidence="${h(item.key)}" data-contact-basis="${h(item.contact_basis)}" data-ground-contact="UNKNOWN"${quality.status?` data-contact-quality="${h(quality.status)}"`:''} stroke="${color}">${ring}<rect x="${n(x0)}" y="${n(y0)}" width="${n(Math.max(1,x1-x0))}" height="${n(Math.max(1,y1-y0))}" fill="none" stroke-width="${stroke}"${item.segment_start?` stroke-dasharray="${n(size*.006)} ${n(size*.004)}"`:''}/><path d="M${n(u-arm)},${n(v)} H${n(u+arm)} M${n(u)},${n(v-arm)} V${n(v+arm)}" stroke="#f6f0d4" stroke-width="${stroke}" fill="none"/><text x="${tx}" y="${ty}" font-size="${font}" fill="${color}">${h(text)}</text></g>`;
  }).join('');
  return `<svg class="candidate-evidence-overlay" data-candidate-evidence-overlay="${h(camera_id??'')}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="候選來源觀測框：像素 bbox 與底緣接觸像素；接地 UNKNOWN">${shapes}</svg>`;
}
function chart(path,timeRange,kind) {
  const selected=range(timeRange);if(!selected)return '<p>沒有可用來源時間範圍。</p>';
  const position=kind==='position',rows=list(position?path.samples:path.velocities);
  const points=rows.filter(point=>Number.isFinite(point?.timestamp)&&point.timestamp>=selected[0]&&point.timestamp<=selected[1]&&
    (position?finitePoint(point.world_position)&&states.has(point.state):finitePoint(point.velocity_xyz)&&Number.isFinite(point.speed_m_s)&&point.speed_m_s>=0&&derivativeStates.has(point.state)));
  if(!points.length)return `<div class="motion-chart-empty">此範圍沒有可用${position?'位置投影':'有限差分速度'}；保留缺失。</div>`;
  const width=640,height=225,left=58,right=16,top=20,bottom=42;
  const values=points.flatMap(point=>position?point.world_position:[point.speed_m_s]);let lo=position?Math.min(...values):0,hi=Math.max(...values);
  if(hi-lo<1e-9){lo-=position?.5:0;hi+=.5;}const padding=(hi-lo)*.08;hi+=padding;if(position)lo-=padding;
  const x=t=>left+(t-selected[0])/(selected[1]-selected[0]||1)*(width-left-right),y=v=>height-bottom-(v-lo)/(hi-lo)*(height-top-bottom);
  const axisColors=position?colors.slice(0,3):[colors[0]];
  const segments=position?crossCameraSegments(rows,selected):crossCameraVelocitySegments(rows,selected);
  const lines=segments.flatMap(segment=>axisColors.map((color,axis)=>`<path d="M${x(segment.from.timestamp).toFixed(2)},${y(position?segment.from.world_position[axis]:segment.from.speed_m_s).toFixed(2)} L${x(segment.to.timestamp).toFixed(2)},${y(position?segment.to.world_position[axis]:segment.to.speed_m_s).toFixed(2)}" stroke="${color}" stroke-width="1.8" fill="none"${!position||segment.inferred?' stroke-dasharray="5 4"':''}/>`)).join('');
  const markers=points.flatMap(point=>axisColors.map((color,axis)=>`<circle cx="${x(point.timestamp).toFixed(2)}" cy="${y(position?point.world_position[axis]:point.speed_m_s).toFixed(2)}" r="2.3" fill="${position&&point.state==='PROJECTED_OBSERVATION'&&!contactQualityStyle(point.contact_quality).hollow?color:'none'}" stroke="${color}"${position&&contactQualityStyle(point.contact_quality).dashed?' stroke-dasharray="1.5 1" data-contact-quality="FLAGGED"':''}><title>${h(seconds(point.timestamp))} · ${(position?point.world_position[axis]:point.speed_m_s).toFixed(3)} ${position?'m':'m/s'} · ${position?(point.state==='PROJECTED_OBSERVATION'?'像素接地投影':point.state==='INFERRED_CROSS_CAMERA'?'跨鏡頭推斷':'短缺口推斷'):'有限差分衍生值'}${position&&contactQualityStyle(point.contact_quality).label?' · '+h(contactQualityStyle(point.contact_quality).label):''}</title></circle>`)).join('');
  return `<svg class="motion-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${position?'候選來源時間與 XYZ 位置曲線，公尺':'候選來源時間與速度曲線，公尺每秒'}" data-cross-camera-chart data-time-start="${selected[0]}" data-time-end="${selected[1]}" data-chart-left="${left}" data-chart-right="${width-right}"><path d="M${left},${top} V${height-bottom} H${width-right}" stroke="#60738b" fill="none"/><text x="${left}" y="14" fill="#a8b8cd" font-size="11">${position?'XYZ 位置 (m)':'速度 (m/s)'}</text>${[0,.5,1].map(r=>{const value=lo+(hi-lo)*r,py=y(value);return `<path d="M${left},${py} H${width-right}" stroke="#2d3b50"/><text x="${left-8}" y="${py+4}" text-anchor="end" fill="#8195ae" font-size="10">${value.toFixed(2)}</text>`;}).join('')}${[selected[0],(selected[0]+selected[1])/2,selected[1]].map(t=>`<text x="${x(t)}" y="${height-20}" text-anchor="middle" fill="#8195ae" font-size="10">${t.toFixed(1)}</text>`).join('')}<text x="${width-right}" y="${height-4}" text-anchor="end" fill="#a8b8cd" font-size="10">來源時間 (s)</text>${lines}${markers}<line data-cross-camera-cursor x1="${left}" x2="${left}" y1="${top}" y2="${height-bottom}" stroke="#f6f0d4" stroke-width="1.2" opacity="0"/></svg>`;
}
const reason=value=>({LONG_GAP:'長缺口，保持斷線',CROSS_CAMERA_LONG_GAP:'跨鏡頭長缺口，只有關聯假設；中間位置缺失',INVALID_PROJECTION:'投影缺失',SPEED_CAP:'超過設定速度限制',PROJECTION_MISSING:'投影不可用',NO_MEASUREMENT:'沒有像素量測',UNASSOCIATED:'未關聯片段',SAME_CAMERA:'相同鏡頭',TIME_ORDER:'時間順序不相符',OVERLAPPING_TIME:'時間重疊未通過限制',GEOMETRY_LIMIT:'幾何限制未通過'})[value]??value??'原因未提供';
export function crossCameraCandidateHTML(result,rank=1,{cameraLabel=id=>id}={}) {
  const candidate=selectedCrossCameraCandidate(result,rank),timeRange=result?.selection?.time_range;
  if(!candidate)return '<div class="notice warning"><p>此範圍沒有可還原候選；保留缺失，不建立路徑。</p></div>';
  return `<div class="cross-camera-candidate-summary"><h3>${candidate.rank===0?'未關聯基線（排序外）':'候選 '+h(candidate.rank)} · ${list(candidate.paths).length} 條路徑</h3><p>排序分數 ${Number.isFinite(candidate.score)?candidate.score.toFixed(4):'未提供'}，不是機率。${list(candidate.selected_edge_refs).length} 個可能跨鏡頭關聯；${list(candidate.unassociated_node_refs).length} 個未關聯片段保留。身分未確認、行為 UNKNOWN。重疊鏡頭的投影保留原值，不平均成新的觀測位置。</p></div>${list(candidate.unresolved_local_gaps).length?`<div class="motion-missing"><h3>原局部追蹤的未解缺口</h3>${list(candidate.unresolved_local_gaps).map(gap=>`<p>${gap.camera_id?h(cameraLabel(gap.camera_id))+' · ':''}缺失 ${h(interval(gap.time_range))} · ${h(crossCameraPresentation(reason(gap.reason)))}</p>`).join('')}<p>跨鏡頭候選保留這些速度或投影缺口；不因片段分拆而移除。</p></div>`:''}${list(candidate.paths).map((path,index)=>`<article class="motion-track"><h3>路徑 ${index+1} · ${h(list(path.camera_ids).map(cameraLabel).join(' → '))}${pathAssociated(candidate,path)?'':' · 未關聯片段'}</h3>${pathAssociated(candidate,path)?'':'<p class="status-text">未關聯片段：此路徑沒有跨鏡頭或局部關聯，不代表與其他路徑為同一人或連續移動。</p>'}<p class="status-text">片段範圍 ${h(interval(path.canonical_time_range))}；本次曲線 ${h(interval(timeRange))}。地板交點限制，尚未證明碰撞、遮擋或人物身分。</p><p class="status-text" data-cross-camera-path-clock="${index}">此路徑時間游標尚未同步。</p><div class="motion-chart-grid"><div>${chart(path,timeRange,'position')}<p class="motion-chart-key"><span style="color:#76d9cf">X</span> · <span style="color:#c5a7f0">Y</span> · <span style="color:#e8c07c">Z</span> · 實線／實心：觀測像素衍生投影 · 虛線／空心：短缺口或跨鏡頭推斷</p></div><div>${chart(path,timeRange,'velocity')}<p class="motion-chart-key">速度為有限差分推斷；缺失區間不連線。</p></div></div>${list(path.gaps).length?`<div class="motion-missing">${list(path.gaps).map(gap=>`<p>缺失 ${h(interval(gap.time_range))} · ${h(crossCameraPresentation(reason(gap.reason)))}</p>`).join('')}</div>`:''}${details('路徑資料、像素量測分數與接地狀態',{identity_verdict:path.identity_verdict,behavior_verdict:path.behavior_verdict,
    note:'pixel_measurement_uncertainty 是 0–1 像素量測啟發式分數，不是公尺誤差或機率；ray_floor_incidence 只描述視線與地板夾角幾何，不是位置準確度。ground_contact 未經腳點或獨立證據驗證，保持 UNKNOWN。',
    samples:list(path.samples).map(point=>({timestamp:point.timestamp,world_position:point.world_position,state:point.state,pixel_observed:point.pixel_observed,camera:cameraLabel(point.camera_id),
      measurement_status:point.measurement_status,pixel_measurement_uncertainty:point.uncertainty,bbox_xyxy:point.bbox_xyxy,contact_pixel:point.contact_pixel,
      ...(point.pixel_observed===true?groundContactBasis(point):{}),ray_floor_incidence:point.projection_incidence,missing_reason:point.missing_reason})),gaps:path.gaps})}</article>`).join('')}`;
}
export function availableCrossCameraArtifacts(result) {
  if(result?.artifacts?.status!=='AVAILABLE')return [];
  if(result.artifacts.source_binding&&(result.artifacts.source_binding.source_sha256!==result.source_binding?.source_sha256||
    result.artifacts.source_binding.run_id!==result.source_binding?.run_id))return [];
  if(result.artifacts.source_features&&result.artifacts.source_features!==result.source_features)return [];
  if(result.artifacts.association_sha256&&result.artifacts.association_sha256!==result.association_sha256)return [];
  return list(result.artifacts.items).filter(item=>typeof item.media_ref==='string'&&/^[A-Za-z0-9_.:-]{1,200}$/.test(item.media_ref)&&range(item.time_range)&&
    ((['POSITION_VELOCITY_CURVES','ASSOCIATION_CURVES','CROSS_CAMERA_CURVES','ASSOCIATION_POSITION_VELOCITY_CURVES'].includes(item.kind)&&(item.mime_type??item.mime)==='image/png')||
      (['RECONSTRUCTION_VIDEO','ASSOCIATION_VIDEO','CROSS_CAMERA_RECONSTRUCTION_VIDEO'].includes(item.kind)&&(item.mime_type??item.mime)==='video/mp4')));
}
export function crossCameraArtifactsHTML(result,{urlFor=()=>'',cameraLabel=id=>id}={}) {
  const artifacts=availableCrossCameraArtifacts(result);
  if(!artifacts.length)return '<div class="notice warning"><p>跨鏡頭多解影片／曲線圖片尚未物化或來源不相符；上方路徑與曲線保留本次查詢結果。</p></div>';
  const cameras=ids=>list(ids).length?list(ids).map(cameraLabel).join('、'):'鏡頭範圍未提供';
  return `<div class="motion-artifacts">${artifacts.map(item=>`<figure><figcaption>${(item.mime_type??item.mime)==='video/mp4'?'跨鏡頭多解還原影片':'跨鏡頭候選位置／速度曲線'} · 完整來源 ${h(interval(item.time_range))}<br>素材鏡頭：${h(cameras(result.artifacts.selection?.camera_ids))} · 素材 Top-K ${h(result.artifacts.selection?.top_k??3)}<br>本次查詢鏡頭：${h(cameras(result.selection?.camera_ids))} · 範圍 ${h(interval(result.selection?.time_range))} · 請求 Top-K ${h(result.selection?.top_k)}；素材未依本次鏡頭、時間窗或 K 重新產生。影片顯示全部素材候選，工作台使用上方選定候選。</figcaption>${(item.mime_type??item.mime)==='video/mp4'?`<video controls preload="metadata" data-cross-camera-video data-time-start="${item.time_range[0]}" data-time-end="${item.time_range[1]}" src="${h(urlFor(item.media_ref))}" aria-label="完整來源範圍的跨鏡頭多解還原影片"></video><label class="motion-sync"><input type="checkbox" data-cross-camera-sync checked> 播放時同步 3D 候選、曲線與 camera 截圖</label><p class="status-text" data-cross-camera-video-clock></p>`:`<img src="${h(urlFor(item.media_ref))}" alt="完整來源範圍的跨鏡頭多解位置與速度曲線" loading="lazy">`}</figure>`).join('')}</div>`;
}
export function crossCameraPanelHTML(result,{pending=false,rank=1,cameraLabel,urlFor}={}) {
  const candidates=list(result?.candidates),selected=selectedCrossCameraCandidate(result,rank);
  return `<section class="panel cross-camera-panel"><div class="panel-head"><div><h2>跨鏡頭多解 Top-K 事件還原</h2><p>時間、速度與地板幾何限制 · 本機基底演算法</p></div><span class="badge cyan">無 Agent · 身分未確認</span></div><div class="panel-body"><p class="status-text">每組 Blender 情況獨立關聯，不跨場景合併。來源 RGB、校正與局部模型為實際 Blender 資料；橙色目標為預設替代資料。投影位置、速度與跨鏡頭連線為衍生或推斷，缺失保持斷線。不確定性與排序分數不是機率。關聯與排名採所選鏡頭完整來源時間；本次時間窗只切曲線。</p>${pending?'<p aria-live="polite">正在整理選定範圍內的多解候選…</p>':result?`${result.status==='NO_CROSS_CAMERA_EVIDENCE'?'<div class="notice warning"><p>NO_CROSS_CAMERA_EVIDENCE：沒有通過限制的跨鏡頭連線，只保留一個未關聯基線；不補出 Top-K 個解。</p></div>':''}<p>${h(result.status)} · 請求 ${h(result.selection?.top_k)} 解／實得 ${candidates.length} 解 · 查詢 ${h(interval(result.selection?.time_range))}</p>${result.search?.truncated===true?'<div class="notice warning"><p>候選搜尋在設定上限停止；Top-K 只在已探索集合排序，尚未證明是全部可行解的全域排名。</p></div>':''}${cameraCoverageHTML(result,{cameraLabel})}${candidates.length?`<div class="cross-camera-rank-controls"><label class="field"><span>選取候選（同步 3D 路徑與下方曲線）</span><select data-cross-camera-rank aria-label="選取跨鏡頭還原候選">${candidates.map(candidate=>`<option value="${candidate.rank}" ${candidate.rank===selected?.rank?'selected':''}>候選 ${candidate.rank} · ${list(candidate.selected_edge_refs).length} 關聯 · ${list(candidate.unassociated_node_refs).length} 未關聯</option>`).join('')}${result.baseline_candidate?`<option value="0" ${rank===0?'selected':''}>未關聯基線（排序外） · 不作跨鏡頭身分假設</option>`:''}</select></label><p class="status-text" data-cross-camera-clock>來源時間：尚未同步</p></div>`:''}<div data-cross-camera-candidate>${crossCameraCandidateHTML(result,rank,{cameraLabel})}</div>${crossCameraArtifactsHTML(result,{urlFor,cameraLabel})}${details('關聯限制、候選搜尋與來源',{source_binding:result.source_binding,source_features:result.source_features,association_sha256:result.association_sha256,policy:result.policy,search:result.search,summary:result.summary,limitations:result.limitations,agent_used:result.agent_used,formal_acceptance:result.formal_acceptance})}`:'<p class="status-text">選取上方鏡頭、時間與 Top-K，再按「跨鏡頭多解還原」。候選不足時保留實際解數。</p>'}</div></section>`;
}
export function updateCrossCameraCursor(container,timestamp,candidate=null) {
  const clock=container?.querySelector('[data-cross-camera-clock]');if(clock)clock.textContent='來源時間：'+seconds(timestamp)+' · 游標只顯示有資料的候選；不填補缺失';
  for(const node of container?.querySelectorAll('[data-cross-camera-path-clock]')??[]){
    const path=list(candidate?.paths)[Number(node.dataset.crossCameraPathClock)],sample=crossCameraCursor(path,timestamp,candidate?.display_time_range??path?.canonical_time_range);
    node.textContent=seconds(timestamp)+' · '+(sample?sample.state==='PROJECTED_OBSERVATION'?
      `觀測像素衍生投影 · ${sample.camera_id??'鏡頭未知'}${sample.measurement_status?' · '+sample.measurement_status:''} · ${groundContactLabel(sample)}`:
      sample.state==='INFERRED_CROSS_CAMERA'?'推斷：跨鏡頭位置假設':'推斷：短缺口插值':'MISSING：此時間沒有可用位置，不延伸上一個點');
  }
  for(const svg of container?.querySelectorAll('[data-cross-camera-chart]')??[]){
    const start=Number(svg.dataset.timeStart),end=Number(svg.dataset.timeEnd),left=Number(svg.dataset.chartLeft),right=Number(svg.dataset.chartRight),cursor=svg.querySelector('[data-cross-camera-cursor]');
    if(!cursor)continue;const valid=Number.isFinite(timestamp)&&timestamp>=start&&timestamp<=end;
    cursor.setAttribute('opacity',valid?'1':'0');if(valid){const x=left+(timestamp-start)/(end-start||1)*(right-left);cursor.setAttribute('x1',String(x));cursor.setAttribute('x2',String(x));}
  }
}
export function sourceTimeForCrossCameraVideo(video) {
  if(!video.dataset.timeStart||!video.dataset.timeEnd)return null;
  const start=Number(video.dataset.timeStart),end=Number(video.dataset.timeEnd),timestamp=video.currentTime;
  return Number.isFinite(start)&&Number.isFinite(end)&&end>=start&&Number.isFinite(timestamp)&&timestamp>=0?Math.min(end,start+timestamp):null;
}
export function bindCrossCameraMedia(container,{current=()=>true,onSourceTime=()=>{},getCandidate=()=>null}={}) {
  const disposers=[];
  for(const video of container.querySelectorAll('[data-cross-camera-video]')){
    let lastImageTime=null;
    const update=(forceImages=false)=>{
      if(!current()||!video.isConnected)return;
      const timestamp=sourceTimeForCrossCameraVideo(video),figure=video.closest('figure'),clock=figure?.querySelector('[data-cross-camera-video-clock]');
      if(clock)clock.textContent='影片對應來源時間：'+seconds(timestamp);
      if(timestamp!==null&&figure?.querySelector('[data-cross-camera-sync]')?.checked){
        updateCrossCameraCursor(container,timestamp,getCandidate());
        const fetchImages=forceImages===true||Math.abs(timestamp-(lastImageTime??-Infinity))>=.19;if(fetchImages)lastImageTime=timestamp;
        onSourceTime(timestamp,{fetchImages});
      }
    };
    // Native playback may end after its last timeupdate. Fetch the final source frame even within the image throttle.
    const ended=()=>update(true);
    video.addEventListener('timeupdate',update);video.addEventListener('seeked',update);video.addEventListener('ended',ended);
    disposers.push(()=>{video.removeEventListener('timeupdate',update);video.removeEventListener('seeked',update);video.removeEventListener('ended',ended);video.pause();video.removeAttribute('src');video.load();});
  }
  return ()=>disposers.forEach(dispose=>dispose());
}

const physicalVerdicts=new Set(['REJECTED','UNKNOWN','SUPPORTED_LOCAL_ONLY']);
const physicalVerdictLabel=value=>({REJECTED:'已拒絕：僅供核對',UNKNOWN:'未知保留：尚無充分物理支持',SUPPORTED_LOCAL_ONLY:'僅支持已檢查的局部範圍'})[value]??'物理判斷未提供';
export function invalidatePhysicalCrossCamera(target) {
  target.physicalEpoch=(target.physicalEpoch??0)+1;target.physicalResult=null;target.physicalPending=false;target.physicalChoice='accepted:1';target.physicalTimestamp=null;
}
export function physicalRequestIsCurrent(target,ticket) {
  return target.role==='research'&&target.sceneEpoch===ticket.sceneEpoch&&target.sceneId===ticket.sceneId&&
    target.session?.session_ref===ticket.sessionRef&&target.physicalEpoch===ticket.physicalEpoch;
}
export function validatePhysicalResponse(result,request,snapshot) {
  if(result?.schema_version!=='workbench.blender-physical.v1'||result.formal_acceptance!==false||!['READY','NO_CROSS_CAMERA_EVIDENCE','NO_RESULT','ALL_CANDIDATES_REJECTED'].includes(result.status)||!Array.isArray(result.rejected_candidates)||result.rejected_candidates.length>5||
    !/^[a-f0-9]{64}$/.test(result.physical_sha256??'')||!/^[a-f0-9]{64}$/.test(result.base_association_sha256??'')||
    list(result.candidates).some(candidate=>!physicalVerdicts.has(candidate.physical?.verdict)||candidate.physical.verdict==='REJECTED')||
    result.rejected_candidates.some(candidate=>candidate.physical?.verdict!=='REJECTED')||
    result.baseline_candidate&&!physicalVerdicts.has(result.baseline_candidate.physical?.verdict))throw Error('物理篩選的候選或來源契約無效。');
  validateCrossCameraResponse({...result,schema_version:'workbench.blender-association.v1',status:list(result.candidates).length?'READY':'NO_RESULT'},request,snapshot);
  if(result.rejected_candidates.length)validateCrossCameraResponse({...result,schema_version:'workbench.blender-association.v1',status:'READY',
    selection:{...result.selection,top_k:5},candidates:result.rejected_candidates.map((candidate,index)=>({...candidate,rank:index+1}))},
    {...request,top_k:5},snapshot);
  return result;
}
export async function runPhysicalReconstruction(target,selection,send) {
  target.physicalResult=null;target.physicalPending=true;target.physicalChoice='accepted:1';target.physicalTimestamp=null;
  const ticket={sceneEpoch:target.sceneEpoch,sceneId:target.sceneId,sessionRef:target.session?.session_ref,physicalEpoch:++target.physicalEpoch};
  const request={scene_id:ticket.sceneId,camera_ids:[...selection.camera_ids],start:selection.start,end:selection.end,top_k:selection.top_k};
  const snapshot=target.snapshot;
  try {
    const result=await send(request);if(!physicalRequestIsCurrent(target,ticket))return false;
    target.physicalResult=validatePhysicalResponse(result,request,snapshot);target.physicalPending=false;
    if(!list(result.candidates).length)target.physicalChoice=list(result.rejected_candidates).length?'rejected:1':'baseline';
    return true;
  } catch(error){if(!physicalRequestIsCurrent(target,ticket))return false;target.physicalPending=false;throw error;}
}
export function selectedPhysicalCandidate(result,choice='accepted:1') {
  if(choice==='baseline'&&result?.baseline_candidate)return {...result.baseline_candidate,rank:0,physical_display_label:'未關聯基線（排序外）'};
  const match=/^(accepted|rejected):([1-5])$/.exec(choice),rows=match?.[1]==='rejected'?list(result?.rejected_candidates):list(result?.candidates);
  const index=match?Number(match[2])-1:0,candidate=rows[index];
  return candidate?{...candidate,physical_display_label:match?.[1]==='rejected'?`拒絕解 ${index+1}（只供核對）`:`物理保留候選 ${candidate.rank??index+1}`}:
    list(result?.candidates)[0]?{...result.candidates[0],physical_display_label:'物理保留候選 1'}:null;
}
export function physicalScenePlan(result,choice='accepted:1') {
  const chosen=selectedPhysicalCandidate(result,choice),accepted=list(result?.candidates),rejected=list(result?.rejected_candidates);
  if(!chosen)return {paths:[],time_range:range(result?.selection?.time_range),selected_rank:null};
  const rows=[...accepted.map((candidate,index)=>({...candidate,rank:index+1,physical_display_label:`物理候選 ${index+1}`})),
    ...rejected.map((candidate,index)=>({...candidate,rank:accepted.length+index+1,physical_display_label:`拒絕解 ${index+1}（核對）`}))];
  let rank=choice==='baseline'?0:choice.startsWith('rejected:')?accepted.length+Number(choice.split(':')[1]):Number(choice.split(':')[1]);
  if(!Number.isInteger(rank)||rank<0)rank=1;
  const normalized={...result,candidates:rows};const plan=crossCameraScenePlan(normalized,rank);
  return {...plan,physical:true,paths:plan.paths.map(path=>{
    const candidate=path.rank===0?result.baseline_candidate:rows[path.rank-1],verdict=candidate?.physical?.verdict;
    return {...path,key:'physical:'+path.key,physicalVerdict:verdict,color:verdict==='REJECTED'?'#ef9da7':verdict==='SUPPORTED_LOCAL_ONLY'?'#76d9cf':'#e8c07c',
      caption:`${path.rank===0?'未關聯基線':candidate?.physical_display_label??'物理候選'} · 路徑 ${path.ordinal}`};
  })};
}
export function physicalGeometryPlan(result) {
  const context=result?.geometry_context;
  if(context?.units!=='METRES'||context.source_sha256!==result.source_binding?.source_sha256||
    typeof context.physical_source_sha256!=='string'||!/^[a-f0-9]{64}$/.test(context.physical_source_sha256)||
    result.authority_coverage?.physical_source_sha256&&result.authority_coverage.physical_source_sha256!==context.physical_source_sha256)return {polygons:[],authority:'UNKNOWN'};
  const validRing=ring=>Array.isArray(ring)&&ring.length>=3&&ring.length<=512&&ring.every(finitePoint);
  return {authority:'PARTIAL_SOURCE_PERMISSION_NOT_COLLISION_FREE',polygons:list(context.support_polygons).slice(0,16)
    .filter(polygon=>polygon.authority==='APPROVED'&&polygon.role==='SOURCE_SUPPORTED_WALKABLE_ONLY'&&validRing(polygon.exterior)&&
      list(polygon.holes).length<=16&&list(polygon.holes).every(validRing))
    .map((polygon,index)=>({exterior:polygon.exterior,holes:list(polygon.holes),caption:'來源局部支持面 '+(index+1)+' · 已批准',
      physical_authority:'SOURCE_SUPPORTED_WALKABLE_ONLY',complete_collision_validation:false}))};
}
const physicalReasonLabel=code=>({APPROVED_SOURCE_SUPPORT:'已批准來源局部支持面',APPROVED_SUPPORT_UNAVAILABLE:'缺少已批准支持面',APPROVED_COLLIDER_SCOPE_UNAVAILABLE:'缺少已批准碰撞檢查範圍',KNOWN_COMPONENTS_NOT_INTERSECTED:'列出的已知組件未相交（非無碰撞證明）',KNOWN_COMPONENTS_OUTSIDE_SWEPT_BOUNDS:'已知組件在本段掃掠範圍外（非無碰撞證明）',MISSING_GAP_ROUTE_UNOBSERVED:'缺失路段沒有觀測位置',WHOLE_SCENE_BODY_CLEARANCE_UNKNOWN:'全場身體通行淨空未知',SOURCE_EVIDENCE_UNAVAILABLE:'來源物理證據不可用',ORIGINAL_LOCAL_HARD_GAP_UNRESOLVED:'原局部追蹤硬缺口未解',PHYSICAL_CHECK_BUDGET:'物理檢查達設定上限',APERTURE_HUMAN_REVIEW:'門洞仍待人工核對'})[code]??code??'原因未提供';
function physicalReasonRows(rows) {
  return list(rows).map(row=>`<tr><td>${h(physicalReasonLabel(row.code))}${row.occurrence_count?`<br>來源檢查 ${h(row.occurrence_count)} 次`:''}</td><td>${h(row.status??'UNKNOWN')}</td><td>${h(interval(row.time_range))}</td><td>${h(row.authority??'權威未提供')}</td></tr>`).join('');
}
export function physicalCandidateHTML(result,choice='accepted:1',{cameraLabel=id=>id}={}) {
  const candidate=selectedPhysicalCandidate(result,choice);
  if(!candidate)return '<div class="notice warning"><p>沒有可檢視的物理候選；不以未知資料補出可通行路徑。</p></div>';
  const physical=candidate.physical??{},verdict=physical.verdict;
  const curveRank=candidate.rank??candidate.rejection_rank??1;
  const adapted={...result,candidates:[{...candidate,rank:curveRank}],baseline_candidate:candidate.rank===0?candidate:result.baseline_candidate};
  const curves=crossCameraCandidateHTML(adapted,curveRank,{cameraLabel});
  return `<div class="physical-verdict ${verdict==='REJECTED'?'rejected':verdict==='SUPPORTED_LOCAL_ONLY'?'supported':'unknown'}"><h3>${h(candidate.physical_display_label)} · ${h(physicalVerdictLabel(verdict))}</h3><p>${verdict==='REJECTED'?'下方曲線保留被排除解的來源位置，只供核對原因，未當作保留路線。':verdict==='SUPPORTED_LOCAL_ONLY'?'支持限於列出的來源局部檢查；仍未確認人物身分、全場通行與遮擋。':'未知候選仍在重排集合內；沒有已知碰撞不代表已驗證可通行。'}</p><div class="gallery-table"><table><thead><tr><th>檢查理由</th><th>結果</th><th>來源時間</th><th>來源權威</th></tr></thead><tbody>${physicalReasonRows(physical.reasons)}</tbody></table></div>${list(physical.checks).some(row=>row.status==='SUPPORTED_LOCAL_ONLY')?`<h4>已支持的局部檢查（不是全場通行證明）</h4><div class="gallery-table"><table><tbody>${physicalReasonRows(list(physical.checks).filter(row=>row.status==='SUPPORTED_LOCAL_ONLY'))}</tbody></table></div>`:''}${list(physical.unknowns).length?`<h4>仍未知的項目</h4><div class="gallery-table"><table><tbody>${physicalReasonRows(physical.unknowns)}</tbody></table></div>`:''}<p>原探索集合序位 ${h(candidate.original_rank??'未提供')}；原集合包含舊 Top-K 之外的解。基底相容 ${Number.isFinite(physical.scores?.base_compatibility)?physical.scores.base_compatibility.toFixed(4):'未知'} ＋ 局部支持 ${Number.isFinite(physical.scores?.support_evidence_bonus)?physical.scores.support_evidence_bonus.toFixed(4):'未知'} − 缺位置扣分 ${Number.isFinite(physical.scores?.missing_position_penalty)?physical.scores.missing_position_penalty.toFixed(4):'未知'} ＝ 重排 ${Number.isFinite(physical.scores?.ranking_score)?physical.scores.ranking_score.toFixed(4):'未知'}；分數不是機率。</p>${details('本解檢查與排序分數',{physical,original_rank:candidate.original_rank,base_score:candidate.base_score})}</div>${curves}`;
}
export function availablePhysicalArtifacts(result) {
  if(result?.artifacts?.status!=='AVAILABLE')return [];
  const artifacts=result.artifacts;
  if(artifacts.source_binding&&(artifacts.source_binding.source_sha256!==result.source_binding?.source_sha256||artifacts.source_binding.run_id!==result.source_binding?.run_id))return [];
  if(artifacts.source_features&&artifacts.source_features!==result.source_features)return [];
  if(artifacts.physical_sha256&&artifacts.physical_sha256!==result.physical_sha256)return [];
  if(artifacts.base_association_sha256&&artifacts.base_association_sha256!==result.base_association_sha256)return [];
  if(artifacts.physical_source_sha256&&artifacts.physical_source_sha256!==(result.physical_source_sha256??result.geometry_context?.physical_source_sha256))return [];
  if(artifacts.evidence_hashes&&JSON.stringify(Object.entries(artifacts.evidence_hashes).sort())!==JSON.stringify(Object.entries(result.evidence_hashes??{}).sort()))return [];
  return list(artifacts.items).filter(item=>typeof item.media_ref==='string'&&/^physical-media:[a-f0-9]{24}$/.test(item.media_ref)&&range(item.time_range)&&
    ((item.kind==='PHYSICAL_POSITION_VELOCITY_CURVES'&&(item.mime_type??item.mime)==='image/png')||
      (item.kind==='PHYSICAL_CROSS_CAMERA_VIDEO'&&(item.mime_type??item.mime)==='video/mp4')));
}
export function physicalArtifactsHTML(result,{urlFor=()=>'',cameraLabel=id=>id}={}) {
  const items=availablePhysicalArtifacts(result);if(!items.length)return '<div class="notice warning"><p>物理篩選影片／曲線尚未物化或來源不符；本次候選與未知狀態仍保留。</p></div>';
  const cameras=ids=>list(ids).map(cameraLabel).join('、')||'範圍未提供';
  return `<div class="motion-artifacts">${items.map(item=>`<figure><figcaption>門／走廊／碰撞篩選 ${(item.mime_type??item.mime)==='video/mp4'?'回放影片':'曲線圖片'} · 完整素材 ${h(interval(item.time_range))}<br>素材鏡頭：${h(cameras(result.artifacts.selection?.camera_ids))} · 素材 Top-K ${h(result.artifacts.selection?.top_k??3)}<br>查詢鏡頭：${h(cameras(result.selection?.camera_ids))} · ${h(interval(result.selection?.time_range))} · 請求 Top-K ${h(result.selection?.top_k)}。影片呈現完整素材保留候選及最多 2 個拒絕對照（實際 ${h(result.artifacts.rejected_candidate_count_video??'未提供')} 個）；未加入不存在的拒絕解，不會隨工作台選取的候選或拒絕解重新產生。</figcaption>${(item.mime_type??item.mime)==='video/mp4'?`<video controls preload="metadata" data-physical-video data-cross-camera-video data-time-start="${item.time_range[0]}" data-time-end="${item.time_range[1]}" src="${h(urlFor(item.media_ref))}" aria-label="完整來源範圍的門走廊碰撞篩選回放"></video><label class="motion-sync"><input type="checkbox" data-cross-camera-sync checked> 播放時同步物理候選 3D、曲線與來源影像</label><p class="status-text" data-cross-camera-video-clock></p>`:`<img src="${h(urlFor(item.media_ref))}" alt="門走廊碰撞篩選的候選位置速度曲線" loading="lazy">`}</figure>`).join('')}</div>`;
}
export function physicalPanelHTML(result,{available=true,pending=false,choice='accepted:1',cameraLabel,urlFor}={}) {
  const accepted=list(result?.candidates),rejected=list(result?.rejected_candidates),coverage=result?.authority_coverage?.coverage??result?.authority_coverage??{},portals=result?.authority_coverage?.portals_summary??result?.geometry_context?.portals??{};
  return `<section class="panel physical-cross-camera-panel"><div class="panel-head"><div><h2>來源門／走廊／碰撞篩選與重排</h2><p>來源權威與局部物理檢查 · 本機基底演算法</p></div><span class="badge cyan">UNKNOWN 保留 · 無 Agent</span></div><div class="panel-body"><p class="status-text">物理支持限於來源已有且通過權威檢查的幾何。未批准的門洞、走廊或不完整碰撞場景明列 UNKNOWN；0 已知碰撞不等於可通行證明。來源 RGB、校正與局部模型為實際 Blender 資料，目標活動為替代資料；位置與路徑為衍生／推斷。</p>${!available?'<div class="notice warning"><p>本場景的物理來源尚不可用；門／走廊／碰撞篩選未完成，原跨鏡頭候選仍可檢視。</p></div>':pending?'<p aria-live="polite">正在檢查候選的來源幾何限制與未知項目…</p>':result?`<p>${h(result.status??'UNKNOWN')} · 請求 ${h(result.selection?.top_k)} 解／保留 ${accepted.length} 解／可核對拒絕 ${rejected.length} 解。</p><p class="status-text">關聯及物理重排使用所選鏡頭完整來源時間；本次時間窗只切曲線。來源局部檢查不構成全場物理認證。</p>${result.search?.truncated?'<div class="notice warning"><p>來源候選池或搜尋達設定上限；重排僅涵蓋實際檢查集合，不能聲稱全域最佳解。</p></div>':''}${cameraCoverageHTML(result,{cameraLabel})}<div class="notice warning"><p>來源完整碰撞驗證：${coverage.physical_complete===true?'來源仍須依局部檢查範圍判讀':'未完成'}；門洞標註 ${h(portals.count??'未知')}（${h(portals.state??portals.status??'UNKNOWN')}）／已批准門洞 ${h(result.geometry_context?.portals?.approved_apertures??portals.approved_apertures??'未知')}；已知碰撞組件 ${h(coverage.known_collider_component_count??'未知')}（不等同全場完整）。局部支持面描邊只顯示已批准範圍，未提供已驗證走廊動線。描邊高度採批准地板錨點供顯示；物理檢查仍使用來源三角形實際高度。鏡頭與軌跡的房間歸屬仍未確認。</p></div>${details('本場景物理來源權威與覆蓋',{authority_coverage:result.authority_coverage,evidence_hashes:result.evidence_hashes,geometry_context:result.geometry_context})}<div class="cross-camera-rank-controls"><label class="field"><span>核對保留、拒絕或未關聯解</span><select data-physical-choice aria-label="選取物理篩選候選">${accepted.map((candidate,index)=>`<option value="accepted:${index+1}" ${choice==='accepted:'+(index+1)?'selected':''}>保留 ${index+1} · ${h(physicalVerdictLabel(candidate.physical?.verdict))}</option>`).join('')}${rejected.map((candidate,index)=>`<option value="rejected:${index+1}" ${choice==='rejected:'+(index+1)?'selected':''}>拒絕 ${index+1} · 只供核對</option>`).join('')}${result.baseline_candidate?`<option value="baseline" ${choice==='baseline'?'selected':''}>未關聯基線（排序外）</option>`:''}</select></label><p class="status-text" data-cross-camera-clock>來源時間尚未同步。</p></div><div data-physical-candidate>${physicalCandidateHTML(result,choice,{cameraLabel})}</div>${physicalArtifactsHTML(result,{urlFor,cameraLabel})}${physicalLedgerHTML(result)}${details('物理重排來源、限制與實際讀取',{base_association_sha256:result.base_association_sha256,physical_sha256:result.physical_sha256,search:result.search,summary:result.summary,decision_ledger:result.decision_ledger,limitations:result.limitations,agent_used:result.agent_used})}`:'<p class="status-text">使用上方鏡頭、時間與 K，再按「門／走廊／碰撞篩選」。未知不會自動變成通過。</p>'}</div></section>`;
}
export function physicalLedgerHTML(result) {
  const ledger=list(result?.decision_ledger).slice(0,256),selected=new Map(list(result?.candidates).map(candidate=>[candidate.candidate_ref,candidate.rank]));
  if(!ledger.length)return '<p class="status-text">尚未提供完整探索集合的物理判斷摘要；不由目前 Top-K 推定其他解已拒絕。</p>';
  const codes=value=>Object.entries(value??{}).map(([code,count])=>physicalReasonLabel(code)+' × '+count).join('；')||'無';
  return `<details class="physical-ledger"><summary>探索集合與重排判斷摘要 · ${ledger.length} 解</summary><p>未入 Top-K ≠ 拒絕。UNKNOWN 仍保留在探索集合內；下表排名由基底演算法回傳，工作台不另行決策。</p><div class="gallery-table"><table><thead><tr><th>原探索序位</th><th>物理重排</th><th>結果</th><th>本次顯示</th><th>排序分數</th><th>拒絕／未知原因</th></tr></thead><tbody>${ledger.map(row=>{
    const shown=selected.get(row.candidate_ref),verdict=row.verdict,score=row.scores??{};
    const membership=verdict==='REJECTED'?'已拒絕':row.is_unassociated_baseline&&row.rerank===null?'未關聯基線／排序外':shown?'本次 Top-K':'仍保留／未入本次 Top-K';
    return `<tr><td>${h(row.original_rank??'未知')}</td><td>${h(row.rerank??shown??(row.rerank===null?'排序外':'未提供'))}</td><td>${h(physicalVerdictLabel(verdict))}</td><td>${h(membership)}</td><td>基底 ${Number.isFinite(score.base_compatibility)?score.base_compatibility.toFixed(4):'未知'}<br>支持 +${Number.isFinite(score.support_evidence_bonus)?score.support_evidence_bonus.toFixed(4):'未知'}<br>缺失 −${Number.isFinite(score.missing_position_penalty)?score.missing_position_penalty.toFixed(4):'未知'}<br>重排 ${Number.isFinite(score.ranking_score)?score.ranking_score.toFixed(4):'未知'}</td><td>${h(codes(row.reason_codes))}<br>${h(codes(row.unknown_codes))}</td></tr>`;
  }).join('')}</tbody></table></div></details>`;
}

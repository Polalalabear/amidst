import {presentationData} from './presentation-data.mjs';
import {cameraCoverageHTML} from './blender-motion.mjs';

const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list=value=>Array.isArray(value)?value:[];
const finitePoint=point=>Array.isArray(point)&&point.length===3&&point.every(Number.isFinite);
const range=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)&&value[1]>=value[0]?value:null;
const seconds=value=>Number.isFinite(value)?value.toFixed(1)+' s':'時間未知';
const interval=value=>range(value)?value.map(seconds).join('–'):'範圍未提供';
const states=new Set(['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION','INFERRED_CROSS_CAMERA']);
const derivativeStates=new Set(['INFERRED_FINITE_DIFFERENCE','INFERRED_CROSS_CAMERA']);
const colors=['#76d9cf','#c5a7f0','#e8c07c','#ef9da7','#96bded'];
const refKey=key=>/(?:^|_)(?:track|node|edge|path|candidate|association|event|observation|frame|interval|gap)_(?:ref|refs|id|ids)$/i.test(key);
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
// The visual cursor selects a source/inference sample. It never extrapolates a missing path.
export function crossCameraCursor(path,timestamp,timeRange,{tolerance=.100001}={}) {
  const selected=range(timeRange);if(!selected||!Number.isFinite(timestamp)||timestamp<selected[0]||timestamp>selected[1])return null;
  const eligible=list(path?.samples).filter(sample=>Number.isFinite(sample?.timestamp)&&Math.abs(sample.timestamp-timestamp)<=tolerance);
  eligible.sort((a,b)=>Math.abs(a.timestamp-timestamp)-Math.abs(b.timestamp-timestamp));
  const nearest=eligible[0];
  return nearest&&finitePoint(nearest.world_position)&&states.has(nearest.state)?nearest:null;
}
export function crossCameraScenePlan(result,rank=1) {
  const selected=selectedCrossCameraCandidate(result,rank),timeRange=range(result?.selection?.time_range);
  if(!selected||!timeRange)return {paths:[],time_range:timeRange,selected_rank:null};
  const candidates=[...list(result.candidates),...(rank===0?[selected]:[])];
  const edges=list(result.graph?.edges);
  return {time_range:timeRange,selected_rank:selected.rank,paths:candidates.flatMap(candidate=>list(candidate.paths).map((path,index)=>({
    key:`${candidate.rank}:${index+1}`,rank:candidate.rank,ordinal:index+1,selected:candidate.rank===selected.rank,
    color:colors[Math.max(0,candidate.rank-1)%colors.length],caption:`${candidate.rank===0?'未關聯基線':'候選 '+candidate.rank} · 路徑 ${index+1}`,
    samples:list(path.samples),segments:crossCameraSegments(path.samples,timeRange),
    associationCaptions:edges.filter(edge=>list(path.edge_refs).includes(edge.edge_ref)&&edge.bridge_missing!==true&&finitePoint(edge.from_world_position)&&finitePoint(edge.to_world_position)&&edge.from_timestamp>=timeRange[0]&&edge.to_timestamp<=timeRange[1])
      .map(edge=>({from:edge.from_world_position,to:edge.to_world_position,caption:edge.kind==='CROSS_CAMERA_CORROBORATING_OVERLAP'?'重疊觀測相容假設':'跨鏡頭關聯假設'})),
    missingAssociations:edges.filter(edge=>list(path.edge_refs).includes(edge.edge_ref)&&edge.bridge_missing===true&&
      finitePoint(edge.from_world_position)&&finitePoint(edge.to_world_position)&&edge.from_timestamp>=timeRange[0]&&edge.to_timestamp<=timeRange[1])
      .map(edge=>({from:edge.from_world_position,to:edge.to_world_position,caption:'關聯假設／中間位置缺失'})),
  })))};
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
  const markers=points.flatMap(point=>axisColors.map((color,axis)=>`<circle cx="${x(point.timestamp).toFixed(2)}" cy="${y(position?point.world_position[axis]:point.speed_m_s).toFixed(2)}" r="2.3" fill="${position&&point.state==='PROJECTED_OBSERVATION'?color:'none'}" stroke="${color}"><title>${h(seconds(point.timestamp))} · ${(position?point.world_position[axis]:point.speed_m_s).toFixed(3)} ${position?'m':'m/s'} · ${position?(point.state==='PROJECTED_OBSERVATION'?'像素接地投影':point.state==='INFERRED_CROSS_CAMERA'?'跨鏡頭推斷':'短缺口推斷'):'有限差分衍生值'}</title></circle>`)).join('');
  return `<svg class="motion-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${position?'候選來源時間與 XYZ 位置曲線，公尺':'候選來源時間與速度曲線，公尺每秒'}" data-cross-camera-chart data-time-start="${selected[0]}" data-time-end="${selected[1]}" data-chart-left="${left}" data-chart-right="${width-right}"><path d="M${left},${top} V${height-bottom} H${width-right}" stroke="#60738b" fill="none"/><text x="${left}" y="14" fill="#a8b8cd" font-size="11">${position?'XYZ 位置 (m)':'速度 (m/s)'}</text>${[0,.5,1].map(r=>{const value=lo+(hi-lo)*r,py=y(value);return `<path d="M${left},${py} H${width-right}" stroke="#2d3b50"/><text x="${left-8}" y="${py+4}" text-anchor="end" fill="#8195ae" font-size="10">${value.toFixed(2)}</text>`;}).join('')}${[selected[0],(selected[0]+selected[1])/2,selected[1]].map(t=>`<text x="${x(t)}" y="${height-20}" text-anchor="middle" fill="#8195ae" font-size="10">${t.toFixed(1)}</text>`).join('')}<text x="${width-right}" y="${height-4}" text-anchor="end" fill="#a8b8cd" font-size="10">來源時間 (s)</text>${lines}${markers}<line data-cross-camera-cursor x1="${left}" x2="${left}" y1="${top}" y2="${height-bottom}" stroke="#f6f0d4" stroke-width="1.2" opacity="0"/></svg>`;
}
const reason=value=>({LONG_GAP:'長缺口，保持斷線',CROSS_CAMERA_LONG_GAP:'跨鏡頭長缺口，只有關聯假設；中間位置缺失',INVALID_PROJECTION:'投影缺失',SPEED_CAP:'超過設定速度限制',PROJECTION_MISSING:'投影不可用',NO_MEASUREMENT:'沒有像素量測',UNASSOCIATED:'未關聯片段',SAME_CAMERA:'相同鏡頭',TIME_ORDER:'時間順序不相符',OVERLAPPING_TIME:'時間重疊未通過限制',GEOMETRY_LIMIT:'幾何限制未通過'})[value]??value??'原因未提供';
export function crossCameraCandidateHTML(result,rank=1,{cameraLabel=id=>id}={}) {
  const candidate=selectedCrossCameraCandidate(result,rank),timeRange=result?.selection?.time_range;
  if(!candidate)return '<div class="notice warning"><p>此範圍沒有可還原候選；保留缺失，不建立路徑。</p></div>';
  return `<div class="cross-camera-candidate-summary"><h3>${candidate.rank===0?'未關聯基線（排序外）':'候選 '+h(candidate.rank)} · ${list(candidate.paths).length} 條路徑</h3><p>排序分數 ${Number.isFinite(candidate.score)?candidate.score.toFixed(4):'未提供'}，不是機率。${list(candidate.selected_edge_refs).length} 個可能跨鏡頭關聯；${list(candidate.unassociated_node_refs).length} 個未關聯片段保留。身分未確認、行為 UNKNOWN。重疊鏡頭的投影保留原值，不平均成新的觀測位置。</p></div>${list(candidate.unresolved_local_gaps).length?`<div class="motion-missing"><h3>原局部追蹤的未解缺口</h3>${list(candidate.unresolved_local_gaps).map(gap=>`<p>${gap.camera_id?h(cameraLabel(gap.camera_id))+' · ':''}缺失 ${h(interval(gap.time_range))} · ${h(crossCameraPresentation(reason(gap.reason)))}</p>`).join('')}<p>跨鏡頭候選保留這些速度或投影缺口；不因片段分拆而移除。</p></div>`:''}${list(candidate.paths).map((path,index)=>`<article class="motion-track"><h3>路徑 ${index+1} · ${h(list(path.camera_ids).map(cameraLabel).join(' → '))}</h3><p class="status-text">片段範圍 ${h(interval(path.canonical_time_range))}；本次曲線 ${h(interval(timeRange))}。地板交點限制，尚未證明碰撞、遮擋或人物身分。</p><p class="status-text" data-cross-camera-path-clock="${index}">此路徑時間游標尚未同步。</p><div class="motion-chart-grid"><div>${chart(path,timeRange,'position')}<p class="motion-chart-key"><span style="color:#76d9cf">X</span> · <span style="color:#c5a7f0">Y</span> · <span style="color:#e8c07c">Z</span> · 實線／實心：觀測像素衍生投影 · 虛線／空心：短缺口或跨鏡頭推斷</p></div><div>${chart(path,timeRange,'velocity')}<p class="motion-chart-key">速度為有限差分推斷；缺失區間不連線。</p></div></div>${list(path.gaps).length?`<div class="motion-missing">${list(path.gaps).map(gap=>`<p>缺失 ${h(interval(gap.time_range))} · ${h(crossCameraPresentation(reason(gap.reason)))}</p>`).join('')}</div>`:''}${details('路徑資料與不確定性',{identity_verdict:path.identity_verdict,behavior_verdict:path.behavior_verdict,samples:list(path.samples).map(point=>({timestamp:point.timestamp,world_position:point.world_position,state:point.state,pixel_observed:point.pixel_observed,camera:cameraLabel(point.camera_id),uncertainty:point.uncertainty,missing_reason:point.missing_reason})),gaps:path.gaps})}</article>`).join('')}`;
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
    node.textContent=seconds(timestamp)+' · '+(sample?sample.state==='PROJECTED_OBSERVATION'?'觀測像素衍生投影':sample.state==='INFERRED_CROSS_CAMERA'?'推斷：跨鏡頭位置假設':'推斷：短缺口插值':'MISSING：此時間沒有可用位置，不延伸上一個點');
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
    const update=()=>{
      if(!current()||!video.isConnected)return;
      const timestamp=sourceTimeForCrossCameraVideo(video),figure=video.closest('figure'),clock=figure?.querySelector('[data-cross-camera-video-clock]');
      if(clock)clock.textContent='影片對應來源時間：'+seconds(timestamp);
      if(timestamp!==null&&figure?.querySelector('[data-cross-camera-sync]')?.checked){
        updateCrossCameraCursor(container,timestamp,getCandidate());
        const fetchImages=Math.abs(timestamp-(lastImageTime??-Infinity))>=.19;if(fetchImages)lastImageTime=timestamp;
        onSourceTime(timestamp,{fetchImages});
      }
    };
    video.addEventListener('timeupdate',update);video.addEventListener('seeked',update);
    disposers.push(()=>{video.removeEventListener('timeupdate',update);video.removeEventListener('seeked',update);video.pause();video.removeAttribute('src');video.load();});
  }
  return ()=>disposers.forEach(dispose=>dispose());
}

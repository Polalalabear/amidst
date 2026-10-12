import {presentationData} from './presentation-data.mjs';

const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list=value=>Array.isArray(value)?value:[];
const finitePoint=p=>Array.isArray(p)&&p.length===3&&p.every(Number.isFinite);
const range=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)&&value[1]>=value[0]?value:null;
const seconds=value=>Number.isFinite(value)?value.toFixed(1)+' s':'時間未知';
const interval=value=>range(value)?value.map(seconds).join('–'):'範圍未提供';
const technicalData=value=>{
  const clean=item=>{
    if(typeof item==='string')return item.replace(/\b(?:track|motion-track|blender-track):[A-Za-z0-9_.:/-]+/g,'局部軌跡識別碼（見 log）');
    if(Array.isArray(item))return item.map(clean);
    if(!item||typeof item!=='object')return item;
    return Object.fromEntries(Object.entries(item).filter(([key])=>!/(?:^|_)track_(?:ref|refs|id|ids)$/i.test(key)).map(([key,child])=>[key,clean(child)]));
  };
  return clean(presentationData(value));
};
const details=(label,value)=>`<details class="technical"><summary>${h(label)}</summary><pre>${h(JSON.stringify(technicalData(value),null,2))}</pre></details>`;

export function invalidateMotion(target) {
  target.motionEpoch=(target.motionEpoch??0)+1;target.motionResult=null;target.motionPending=false;
}
export function motionRequestIsCurrent(target,ticket) {
  return target.role==='research'&&target.sceneEpoch===ticket.sceneEpoch&&target.sceneId===ticket.sceneId&&
    target.session?.session_ref===ticket.sessionRef&&target.motionEpoch===ticket.motionEpoch;
}
export function validateMotionResponse(result,request,snapshot) {
  const expected=snapshot?.source_binding??{},binding=result?.source_binding??{};
  const selected=result?.selection??{};
  if(result?.schema_version!=='workbench.blender-motion.v1'||result.agent_used!==false||
    !expected.run_id||!expected.source_sha256||binding.run_id!==expected.run_id||binding.source_sha256!==expected.source_sha256||
    JSON.stringify([...list(selected.camera_ids)].sort())!==JSON.stringify([...request.camera_ids].sort())||
    JSON.stringify(selected.time_range)!==JSON.stringify([request.start,request.end])||
    !Array.isArray(result.tracks)||result.tracks.length>32||
    result.tracks.some(track=>!request.camera_ids.includes(track.camera_id)))throw Error('還原資料的來源或查詢範圍不相符。');
  if(snapshot.baseline?.source_features&&result.source_features!==snapshot.baseline.source_features)throw Error('還原資料使用了不同的像素索引。');
  return result;
}
export async function runMotionReconstruction(target,selection,send) {
  target.motionResult=null;target.motionPending=true;
  const ticket={sceneEpoch:target.sceneEpoch,sceneId:target.sceneId,sessionRef:target.session?.session_ref,motionEpoch:++target.motionEpoch};
  const request={scene_id:ticket.sceneId,camera_ids:[...selection.camera_ids],start:selection.start,end:selection.end};
  const snapshot=target.snapshot;
  try {
    const result=await send(request);
    if(!motionRequestIsCurrent(target,ticket))return false;
    target.motionResult=validateMotionResponse(result,request,snapshot);target.motionPending=false;return true;
  } catch(error) {
    if(!motionRequestIsCurrent(target,ticket))return false;
    target.motionPending=false;throw error;
  }
}

// Draw only explicit source-derived samples. Missing values break every series.
export function positionSegments(samples,timeRange) {
  const selected=range(timeRange),segments=[];let prior=null;
  for(const sample of list(samples)){
    const valid=selected&&Number.isFinite(sample?.timestamp)&&sample.timestamp>=selected[0]&&sample.timestamp<=selected[1]&&
      finitePoint(sample.world_position)&&['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION'].includes(sample.state);
    if(!valid){prior=null;continue;}
    if(prior&&sample.connect_from_previous===true&&sample.timestamp>prior.timestamp){
      segments.push({from:prior,to:sample,inferred:sample.state==='INFERRED_INTERPOLATION'||prior.state==='INFERRED_INTERPOLATION'});
    }
    prior=sample;
  }
  return segments;
}
export function velocitySegments(velocities,timeRange) {
  const selected=range(timeRange),segments=[];let prior=null;
  for(const sample of list(velocities)){
    const window=range(sample?.time_range);
    if(!selected||!window||!Number.isFinite(sample.timestamp)||sample.timestamp<selected[0]||sample.timestamp>selected[1]||
      !Number.isFinite(sample.speed_m_s)||sample.speed_m_s<0||!finitePoint(sample.velocity_xyz)||
      sample.state!=='INFERRED_FINITE_DIFFERENCE'){prior=null;continue;}
    if(prior&&sample.timestamp>prior.timestamp&&Math.abs(prior.time_range[1]-window[0])<1e-7)segments.push({from:prior,to:sample});
    prior=sample;
  }
  return segments;
}
function chart(track,timeRange,kind){
  const selected=range(timeRange);if(!selected)return '<p>沒有可用來源時間範圍。</p>';
  const position=kind==='position',rows=list(position?track.samples:track.velocities);
  const points=rows.filter(s=>Number.isFinite(s?.timestamp)&&s.timestamp>=selected[0]&&s.timestamp<=selected[1]&&
    (position?finitePoint(s.world_position)&&['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION'].includes(s.state):
      Number.isFinite(s.speed_m_s)&&s.speed_m_s>=0&&finitePoint(s.velocity_xyz)&&s.state==='INFERRED_FINITE_DIFFERENCE'));
  if(!points.length)return `<div class="motion-chart-empty">此範圍沒有可用${position?'位置投影':'有限差分速度'}；保留缺失狀態。</div>`;
  const width=640,height=230,left=56,right=16,top=20,bottom=42;
  const values=points.flatMap(p=>position?p.world_position:[p.speed_m_s]);
  let lo=Math.min(...values),hi=Math.max(...values);if(!position)lo=0;
  if(hi-lo<1e-9){lo-=position?0.5:0;hi+=.5;}
  const padding=(hi-lo)*.08;hi+=padding;if(position)lo-=padding;
  const x=t=>left+(t-selected[0])/(selected[1]-selected[0]||1)*(width-left-right);
  const y=v=>height-bottom-(v-lo)/(hi-lo)*(height-top-bottom);
  const colors=position?['#76d9cf','#c5a7f0','#e8c07c']:['#76d9cf'];
  const segments=position?positionSegments(rows,selected):velocitySegments(rows,selected);
  const lines=segments.flatMap(segment=>colors.map((color,axis)=>{
    const a=position?segment.from.world_position[axis]:segment.from.speed_m_s,b=position?segment.to.world_position[axis]:segment.to.speed_m_s;
    return `<path d="M${x(segment.from.timestamp).toFixed(2)},${y(a).toFixed(2)} L${x(segment.to.timestamp).toFixed(2)},${y(b).toFixed(2)}" stroke="${color}" stroke-width="1.8" fill="none"${!position||segment.inferred?' stroke-dasharray="5 4"':''}/>`;
  })).join('');
  const markers=points.flatMap(point=>colors.map((color,axis)=>`<circle cx="${x(point.timestamp).toFixed(2)}" cy="${y(position?point.world_position[axis]:point.speed_m_s).toFixed(2)}" r="2.4" fill="${position&&point.state==='INFERRED_INTERPOLATION'?'none':color}" stroke="${color}"><title>${h(seconds(point.timestamp))} · ${(position?point.world_position[axis]:point.speed_m_s).toFixed(3)} ${position?'m':'m/s'} · ${position&&point.state==='INFERRED_INTERPOLATION'?'短缺口推論':'投影衍生值'}</title></circle>`)).join('');
  return `<svg class="motion-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${position?'來源時間與 XYZ 投影位置，公尺':'來源時間與有限差分速度，公尺每秒'}"><path d="M${left},${top} V${height-bottom} H${width-right}" stroke="#60738b" fill="none"/><text x="${left}" y="14" fill="#a8b8cd" font-size="11">${position?'XYZ 位置 (m)':'速度 (m/s)'}</text>${[0,.5,1].map(r=>{const value=lo+(hi-lo)*r,py=y(value);return `<path d="M${left},${py} H${width-right}" stroke="#2d3b50"/><text x="${left-8}" y="${py+4}" text-anchor="end" fill="#8195ae" font-size="10">${value.toFixed(2)}</text>`;}).join('')}${[selected[0],(selected[0]+selected[1])/2,selected[1]].map(t=>`<text x="${x(t)}" y="${height-20}" text-anchor="middle" fill="#8195ae" font-size="10">${t.toFixed(1)}</text>`).join('')}<text x="${width-right}" y="${height-4}" text-anchor="end" fill="#a8b8cd" font-size="10">來源時間 (s)</text>${lines}${markers}</svg>`;
}
const reason=value=>({LONG_GAP:'長缺口，保持斷線',INVALID_PROJECTION:'投影缺失',SPEED_CAP:'超過設定速度限制',TRACK_BREAK:'局部 track 已中斷',PROJECTION_MISSING:'投影不可用',NO_MEASUREMENT:'沒有像素量測'})[value]??value??'原因未提供';
export function cameraCoverageHTML(result,{cameraLabel=id=>id}={}) {
  const rows=list(result?.camera_coverage);
  if(!rows.length)return '<p class="status-text">未提供各鏡頭的投影覆蓋統計；不以其他鏡頭的軌跡數推定。</p>';
  return `<section class="motion-camera-coverage"><h3>各鏡頭資料與缺失狀態</h3>${rows.filter(row=>row.state==='MISSING').map(row=>`<div class="notice warning"><p>${h(cameraLabel(row.camera_id))} · MISSING · 來源 ${h(row.source_frame_count??'未知')} 張／投影 ${h(row.projected_frame_count??'未知')} 幀／缺失 ${h(row.missing_projected_frame_count??'未知')} 幀。${row.pixel_observation_count===0?'沒有像素追蹤或 3D 投影；不由其他鏡頭補值。':'沒有可用 3D 投影；僅保留像素量測。'}</p></div>`).join('')}<div class="gallery-table"><table><thead><tr><th>鏡頭</th><th>來源影格</th><th>像素觀測</th><th>投影影格</th><th>缺失投影</th><th>狀態</th></tr></thead><tbody>${rows.map(row=>`<tr><td>${h(cameraLabel(row.camera_id))}<br>${h(interval(row.time_range))}</td><td>${h(row.source_frame_count??'未提供')}</td><td>${h(row.pixel_observation_count??'未提供')}</td><td>${h(row.projected_frame_count??'未提供')}</td><td>${h(row.missing_projected_frame_count??'未提供')}</td><td>${h(row.state??'UNKNOWN')}${row.state==='MISSING'?`<br>${row.pixel_observation_count===0?'沒有像素追蹤或 3D 投影；不由其他鏡頭補值。':'沒有可用 3D 投影；僅保留像素量測。'}`:''}</td></tr>`).join('')}</tbody></table></div><p class="status-text">統計屬於各鏡頭的查詢範圍。其他鏡頭有曲線，不代表缺失鏡頭已有追蹤。</p></section>`;
}
export function motionTracksHTML(result,{cameraLabel=id=>id}={}) {
  const timeRange=result?.selection?.time_range;
  if(!list(result?.tracks).length)return '<p class="status-text">此範圍沒有可還原的局部軌跡；未補上其他鏡頭或人物。</p>';
  return list(result.tracks).map((track,index)=>`<article class="motion-track"><h3>${h(cameraLabel(track.camera_id))} · 局部軌跡 ${index+1}</h3><p class="status-text">原始片段範圍 ${h(interval(track.canonical_time_range))}；本次曲線範圍 ${h(interval(timeRange))}。身分與行為未確認。</p><div class="motion-chart-grid"><div>${chart(track,timeRange,'position')}<p class="motion-chart-key"><span style="color:#76d9cf">X</span> · <span style="color:#c5a7f0">Y</span> · <span style="color:#e8c07c">Z</span> · 實線：像素接地投影 · 虛線／空心點：短缺口推論</p></div><div>${chart(track,timeRange,'velocity')}<p class="motion-chart-key">速度為位置有限差分；虛線表示衍生值，缺口不連線。</p></div></div>${list(track.gaps).length?`<div class="motion-missing">${list(track.gaps).map(gap=>`<p>缺失 ${h(interval(gap.time_range))} · ${h(presentationData(reason(gap.reason)))}</p>`).join('')}</div>`:''}${details('本軌跡量測與不確定性',{source_track_status:track.source_track_status,samples:list(track.samples).map(s=>({timestamp:s.timestamp,world_position:s.world_position,state:s.state,pixel_observed:s.pixel_observed,missing_reason:s.missing_reason,uncertainty:s.uncertainty})),events:list(track.events).map(event=>({kind:event.kind,canonical_time_range:event.canonical_time_range}))})}</article>`).join('');
}
export function availableMotionArtifacts(result) {
  if(result?.artifacts?.status!=='AVAILABLE')return [];
  return list(result.artifacts.items).filter(item=>typeof item.media_ref==='string'&&/^[A-Za-z0-9_.:-]{1,200}$/.test(item.media_ref)&&
    range(item.time_range)&&((item.kind==='POSITION_VELOCITY_CURVES'&&(item.mime_type??item.mime)==='image/png')||
      (item.kind==='RECONSTRUCTION_VIDEO'&&(item.mime_type??item.mime)==='video/mp4')));
}
export function motionArtifactsHTML(result,{urlFor=()=>'',cameraLabel=id=>id}={}) {
  const artifacts=availableMotionArtifacts(result),selected=result?.selection?.time_range;
  if(!artifacts.length)return '<div class="notice warning"><p>曲線圖片／還原影片尚未物化或來源不相符；上方動態曲線仍依本次查詢顯示。</p></div>';
  const cameras=ids=>list(ids).length?list(ids).map(cameraLabel).join('、'):'鏡頭範圍未提供';
  return `<div class="motion-artifacts">${artifacts.map(item=>`<figure><figcaption>${item.kind==='RECONSTRUCTION_VIDEO'?'預先物化的事件還原影片':'預先物化的位置／速度曲線'} · 完整來源範圍 ${h(interval(item.time_range))}<br>完整素材鏡頭：${h(cameras(result.artifacts.selection?.camera_ids))}<br>本次查詢鏡頭：${h(cameras(result.selection?.camera_ids))} · 本次查詢範圍 ${h(interval(selected))}；素材沒有依本次鏡頭或窄範圍重新產生。</figcaption>${item.kind==='RECONSTRUCTION_VIDEO'?`<video controls preload="metadata" data-motion-video data-motion-start="${item.time_range[0]}" data-motion-end="${item.time_range[1]}" src="${h(urlFor(item.media_ref))}" aria-label="完整來源範圍的預先物化還原影片"></video><label class="motion-sync"><input type="checkbox" data-motion-sync> 播放時同步既有 camera 截圖的來源時間</label><p class="status-text" data-motion-clock></p>`:`<img src="${h(urlFor(item.media_ref))}" alt="完整來源範圍的位置與速度曲線" loading="lazy">`}</figure>`).join('')}</div>`;
}
export function motionPanelHTML(result,{pending=false,cameraLabel,urlFor}={}) {
  return `<section class="panel motion-reconstruction-panel"><div class="panel-head"><div><h2>位置、速度曲線與事件還原</h2><p>像素接地投影與設定物理限制 · 本機基底演算法</p></div><span class="badge cyan">無 Agent · 候選還原</span></div><div class="panel-body"><p class="status-text">XYZ 是來源校正與地面交點衍生的位置，尚未直接量測 3D。短缺口推論使用虛線，長缺口斷開。速度是有限差分；不確定性與速度限制不是機率或行為分類。</p>${pending?'<p aria-live="polite">正在還原選定鏡頭與時間範圍…</p>':result?`${cameraCoverageHTML(result,{cameraLabel})}${motionTracksHTML(result,{cameraLabel})}${motionArtifactsHTML(result,{urlFor,cameraLabel})}${details('本次還原的來源、限制與實際讀取',{source_binding:result.source_binding,source_features:result.source_features,reconstruction_sha256:result.reconstruction_sha256,policy:result.policy,summary:result.summary,retrieval:result.retrieval,limitations:result.limitations,agent_used:result.agent_used})}`:'<p class="status-text">先在上方選取鏡頭與時間，再按「產生物理曲線與還原」。HTTP 只取得還原資料與已物化素材。</p>'}</div></section>`;
}

export function sourceTimeForVideo(video) {
  if(!video.dataset.motionStart||!video.dataset.motionEnd)return null;
  const start=Number(video.dataset.motionStart),end=Number(video.dataset.motionEnd),time=video.currentTime;
  return Number.isFinite(start)&&Number.isFinite(end)&&end>=start&&Number.isFinite(time)&&time>=0?
    Math.min(end,start+time):null;
}
export function bindMotionMedia(container,{current=()=>true,onSourceTime=()=>{}}={}) {
  const disposers=[];
  for(const video of container.querySelectorAll('[data-motion-video]')){
    let last=null;
    const update=()=>{
      if(!current()||!video.isConnected)return;
      const timestamp=sourceTimeForVideo(video),parent=video.closest('figure'),clock=parent?.querySelector('[data-motion-clock]');
      if(clock)clock.textContent='影片對應來源時間：'+seconds(timestamp);
      if(timestamp!==null&&parent?.querySelector('[data-motion-sync]')?.checked&&Math.abs(timestamp-(last??-Infinity))>=.19){last=timestamp;onSourceTime(timestamp);}
    };
    video.addEventListener('timeupdate',update);video.addEventListener('seeked',update);
    disposers.push(()=>{video.removeEventListener('timeupdate',update);video.removeEventListener('seeked',update);video.pause();video.removeAttribute('src');video.load();});
  }
  return ()=>disposers.forEach(dispose=>dispose());
}

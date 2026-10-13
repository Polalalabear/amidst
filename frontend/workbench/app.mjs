import {invalidateVersionResults} from './motion.mjs';
import {presentationData,presentationJSON,prepareFrames,retainElements,requestIsCurrent,guidanceGraph,updateGuidanceInputs} from './presentation-data.mjs';
import {invalidateMotion,runMotionReconstruction,motionPanelHTML,bindMotionMedia,motionRequestIsCurrent} from './blender-motion.mjs';
import {invalidateCrossCamera,runCrossCameraReconstruction,crossCameraPanelHTML,crossCameraCandidateHTML,crossCameraScenePlan,selectedCrossCameraCandidate,bindCrossCameraMedia,crossCameraRequestIsCurrent,updateCrossCameraCursor,invalidatePhysicalCrossCamera,runPhysicalReconstruction,physicalPanelHTML,physicalCandidateHTML,physicalScenePlan,physicalGeometryPlan,selectedPhysicalCandidate,physicalRequestIsCurrent} from './cross-camera.mjs';
import {physicalReviewPanelHTML,bindPhysicalReviewPanel,physicalReviewScenePlan,physicalReviewSelection,physicalReviewLocalDecisions,physicalReviewDisplayKey} from './physical-review.mjs';
import {invalidatePhysicalReview,runPhysicalReviewLoad,runPhysicalReviewSave} from './physical-review-flow.mjs';
const ICONS = {
  home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-8h6v8"/>',
  layers:'<path d="m12 3 10 6-10 6L2 9Z"/><path d="m2 13 10 6 10-6M2 17l10 6 10-6"/>',
  cube:'<path d="m12 3 9 5v10l-9 5-9-5V8Z"/><path d="m3 8 9 5 9-5M12 13v10M7.5 5.5l9 5"/>',
  camera:'<path d="M3 7h12v12H3Z"/><path d="m15 10 6-3v12l-6-3"/>',
  review:'<path d="M14 3H5v18h14V9"/><path d="m10 14 1-4 8-8 3 3-8 8Z"/><path d="M8 17h5"/>',
  test:'<path d="M9 3h6M10 3v7L4 20h16l-6-10V3M7 15h10"/>',
  arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
  switch:'<path d="M4 7h16l-4-4M20 17H4l4 4"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  time:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  person:'<circle cx="12" cy="7" r="4"/><path d="M4 21v-3a8 8 0 0 1 16 0v3"/>',
  event:'<path d="m12 3-3 7H4l5 4-2 7 5-4 5 4-2-7 5-4h-5Z"/>',
  link:'<path d="m9 15 6-6m-8 4-2 2a4 4 0 0 0 6 6l3-3m-4-12 3-3a4 4 0 0 1 6 6l-2 2"/>',
  check:'<path d="m5 12 4 4L20 5"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  play:'<path d="m8 4 12 8-12 8Z"/>',
  pause:'<path d="M8 4v16M16 4v16"/>',
  reset:'<path d="M4 11a8 8 0 1 1 2 7M4 4v7h7"/>',
  region:'<path d="M3 5h18v14H3Z"/><path d="M8 5v14m8-14v14M3 12h18"/>',
  portal:'<path d="M5 21V3h14v18M3 21h18M14 12h.01"/>',
  log:'<path d="M5 3h14v18H5ZM8 7h8M8 11h8M8 15h5"/>',
  expand:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
};
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
export const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const h = escapeHTML;
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] ?? ICONS.info}</svg>`;
const json = (value) => h(presentationJSON(value));
const safeList = (value) => Array.isArray(value) ? value : [];
export function normalizeRange(value) {
  const start = Number(Array.isArray(value) ? value[0] : value?.start ?? 0);
  const end = Number(Array.isArray(value) ? value[1] : value?.end ?? start);
  return Number.isFinite(start) && Number.isFinite(end) && end >= start ? [start, end] : [0, 0];
}
export function eventLabel(value) {
  return ({ENTER_DOOR:'進門',EXIT_DOOR:'出門',TURN_CORNER:'轉角',POSSIBLE_LOITERING:'可能遊蕩',DWELL:'停留',LOST_NEAR_CORNER:'轉角附近失去觀測',INFERRED_GAP_ALTERNATIVES:'盲區路線候選'})[value] ?? String(value ?? '事件');
}
export function objectLabel(value) {
  return ({REGION:'區域',PORTAL:'門／通道',WALKABLE:'可行走面',CAMERA:'鏡頭'})[value] ?? String(value ?? '物件');
}
const objectIcon = (value) => ({REGION:'region',PORTAL:'portal',WALKABLE:'layers',CAMERA:'camera'})[value] ?? 'cube';
const fmt = (value, precision = 1) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value).toFixed(precision) : '—';
const time = (value) => `${fmt(value)} s`;
export const frameTimeLabel = (timestamp) => Number.isFinite(timestamp) ? time(timestamp) : '時間未知';
export function evidenceLabel(value, research = false) {
  if (research) return value ?? '候選事件 · 待檢視';
  return ({INFERRED_GAP:'盲區推論',PROJECTED:'可見投影',OBSERVED:'可見證據',UNKNOWN:'證據不足',UNRESOLVED:'待確認'})[value] ?? '候選事件 · 待檢視';
}
export const supportLabel=value=>({SUPPORTED:'可見證據支持此候選',UNKNOWN:'證據不足／未定',GAP_ALTERNATIVES:'保留盲區替代路徑'})[value]??'';
const short = (value, length = 22) => String(value ?? '').length > length ? `${String(value).slice(0, length)}…` : String(value ?? '—');
const technical = (label, value, log = false) => `<details class="technical"><summary>${h(label)}</summary><pre>${log?h(JSON.stringify(value,null,2)):json(value)}</pre></details>`;
const badge = (text, tone = '') => `<span class="badge ${tone}">${h(text)}</span>`;
const empty = (title, description = '', glyph = 'layers') => `<div class="empty-state">${icon(glyph)}<div>${h(title)}</div>${description ? `<small>${h(description)}</small>` : ''}</div>`;
const sourceVersion = (s) => s.review?.current_version ?? 0;
const state = {
  bootstrap:null,session:null,role:null,sceneId:null,snapshot:null,review:null,page:'workspace',mode:'display',
  resourceTab:'objects',events:[],observations:[],retrieval:null,frames:[],cameraId:null,cameraIds:[],start:0,end:0,timestamp:0,
  selectedObject:null,selectedEvent:null,event:null,notes:[],draft:null,validation:null,publication:null,previewVersion:null,draftPreview:false,
  test:null,evaluation:null,logs:null,loading:false,error:null,scopeMessage:null,reviewDecision:'UNKNOWN',
  sceneEpoch:0,queryEpoch:0,eventEpoch:0,timelineEpoch:0,controller:null,playTimer:null,view:null,viewPose:null,toastTimer:null,panel:null,presentationMode:'source',
  queryPending:false,eventPending:false,presets:null,presetsError:null,guide:null,guideEpoch:0,guideSelection:null,portTest:null,storageProbe:null,storageStage:'all',showGraphLabels:false,
  frameQuery:null,frameQuerySelection:null,frameQueryEpoch:0,frameQueryPending:false,
  visualMode:'3d',wallSlotCount:8,frameWall:null,frameWallSelection:null,frameWallEpoch:0,frameWallPending:false,frameWallError:null,
  motionResult:null,motionEpoch:0,motionPending:false,motionTimestamp:null,motionDispose:null,motionPanelResult:null,motionPanelEpoch:null,motionPanelScene:null,
  crossCameraResult:null,crossCameraEpoch:0,crossCameraPending:false,crossCameraRank:1,crossCameraTimestamp:null,crossCameraDispose:null,crossCameraPanelResult:null,crossCameraPanelEpoch:null,crossCameraPanelScene:null,
  physicalResult:null,physicalEpoch:0,physicalPending:false,physicalChoice:'accepted:1',physicalTimestamp:null,physicalDispose:null,physicalPanelResult:null,physicalPanelEpoch:null,physicalPanelScene:null,reconstructionMode:'association',reconstructionClockOwner:'source',
  physicalReviewResult:null,physicalReviewEpoch:0,physicalReviewPending:false,physicalReviewError:null,physicalReviewSelected:null,physicalReviewSelection:null,physicalReviewDispose:null,physicalReviewPanelKey:null,
  physicalReviewDisplayAlignments:{},
};
export function invalidateEventState(target) {
  target.eventEpoch=(target.eventEpoch??0)+1;
  target.selectedEvent=null;target.event=null;target.notes=[];target.eventPending=false;
}
export function eventRequestIsCurrent(target,ticket) {
  return target.sceneEpoch===ticket.sceneEpoch && target.eventEpoch===ticket.eventEpoch && target.selectedEvent===ticket.eventRef;
}
const isResearch = () => state.role === 'research';
export const supportsFrameQuery = snapshot => snapshot?.capabilities?.frame_query === true;
export const sceneReviewAllowed = snapshot => snapshot?.capabilities?.scene_review !== false && !supportsFrameQuery(snapshot);
const isBlenderQuery = () => supportsFrameQuery(state.snapshot);
const activeReview = () => state.page === 'review' || state.page === 'workspace' && state.mode === 'review';
const previewVersion = () => state.previewVersion ?? sourceVersion(state);
const historicalPreview = () => activeReview() && previewVersion() !== sourceVersion(state);
const objects = () => {
  if (!activeReview()) return safeList(state.snapshot?.objects);
  const version = safeList(state.review?.versions).find((item) => item.version === previewVersion());
  return safeList(version?.objects ?? state.review?.objects ?? state.snapshot?.objects);
};
const cameras = () => safeList(state.snapshot?.cameras);
const selectedObject = () => objects().find((item) => item.object_id === state.selectedObject);
const renderedObjects = () => activeReview() && state.draft && state.draftPreview ? objects().map((item)=>item.object_id===state.draft.object_id ? state.draft.after : item) : objects();
const cameraName = (id) => cameras().find((camera) => camera.camera_id === id)?.label ?? id ?? '鏡頭未知';
const selectedScene = () => safeList(state.bootstrap?.scenes).find((scene) => scene.scene_id === state.sceneId);
const mediaURL = (ref) => `/api/media?${new URLSearchParams({session_ref:state.session?.session_ref ?? '',scene_id:state.sceneId ?? '',ref})}`;

async function api(action, payload = {}, options = {}) {
  const response = await fetch(`/api/${action}`, {
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({session_ref:state.session?.session_ref,...payload}),
    signal:options.signal ?? state.controller?.signal,
  });
  let result;
  try { result = await response.json(); } catch { throw new Error('服務回應無法讀取，請確認本機工作台服務。'); }
  if (!response.ok || result.error) {const error=new Error(result.error?.message ?? `請求失敗 (${response.status})`);error.code=result.error?.code;throw error;}
  return result;
}
function toast(message) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.add('visible');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => node.classList.remove('visible'), 4200);
}
function stopPlayback() {
  clearTimeout(state.playTimer);
  state.playTimer = null;
  const button = $('[data-action="play"]');
  if (button) { button.innerHTML = icon('play'); button.setAttribute('aria-label','開始回放'); }
}
function clearContext() {
  state.physicalReviewDispose?.();state.physicalReviewDispose=null;invalidatePhysicalReview(state);state.physicalReviewPanelKey=null;
  state.motionDispose?.();state.motionDispose=null;invalidateMotion(state);
  state.crossCameraDispose?.();state.crossCameraDispose=null;invalidateCrossCamera(state);
  state.physicalDispose?.();state.physicalDispose=null;invalidatePhysicalCrossCamera(state);state.reconstructionMode='association';state.reconstructionClockOwner='source';
  state.panel?.dispose();state.panel=null;
  stopPlayback();
  state.controller?.abort();
  state.controller = new AbortController();
  state.sceneEpoch += 1;
  state.queryEpoch += 1;
  state.timelineEpoch += 1;
  state.guideEpoch += 1;
  state.frameQueryEpoch += 1;state.frameWallEpoch += 1;
  invalidateEventState(state);
  state.view?.dispose(); state.view = null; state.viewPose = null;
  Object.assign(state,{snapshot:null,review:null,events:[],observations:[],retrieval:null,frames:[],event:null,notes:[],
    selectedObject:null,selectedEvent:null,draft:null,validation:null,publication:null,test:null,evaluation:null,logs:null,
    error:null,scopeMessage:null,cameraIds:[],previewVersion:null,draftPreview:false,queryPending:false,eventPending:false,
    presets:null,presetsError:null,guide:null,guideSelection:null,portTest:null,storageProbe:null,storageStage:'all',showGraphLabels:false,
    frameQuery:null,frameQuerySelection:null,frameQueryPending:false,frameWall:null,frameWallSelection:null,frameWallPending:false,frameWallError:null});
}
async function selectRole(role) {
  clearContext();
  state.loading = true;
  const buttons = $$('[data-role]'); buttons.forEach((button) => button.disabled = true);
  try {
    const session = await api('session',{role});
    Object.assign(state,{session,role:session.role ?? role,page:'workspace',mode:'display'});
    const first = safeList(state.bootstrap?.scenes)[0];
    if (!first) throw new Error('尚未註冊可用場景。');
    await loadScene(first.scene_id);
  } catch (error) {
    if (error.name !== 'AbortError') { state.error = error.message; state.loading = false; render(); }
  }
}
async function loadScene(sceneId) {
  clearContext(); state.sceneId = sceneId; state.loading = true; render();
  const epoch = state.sceneEpoch;
  try {
    const result = await api('scene',{scene_id:sceneId});
    if (epoch !== state.sceneEpoch) return;
    state.snapshot = result.snapshot;
    if(isBlenderQuery()&&['review','investigation','presentations'].includes(state.page)){state.page='workspace';state.mode='display';}
    if(!sceneReviewAllowed(state.snapshot)&&state.page==='review'){state.page='workspace';state.mode='display';}
    state.review = isResearch() ? result.review_state : null;
    state.cameraId = cameras()[0]?.camera_id ?? null;
    state.cameraIds = cameras().slice(0,3).map((camera) => camera.camera_id);
    const range = normalizeRange(state.snapshot.time_range);
    state.start = range[0]; state.end = Math.min(range[1],range[0]+10); state.timestamp = range[0];
    if(isBlenderQuery())state.frameQuerySelection={camera_ids:[...state.cameraIds],start:range[0],end:range[1],target_timestamp:(range[0]+range[1])/2,top_k:3,behavior_intent:'walking'};
    state.selectedObject = objects()[0]?.object_id ?? null;
    state.loading = false; render();
    await Promise.allSettled([queryScope(),isResearch() ? fetchTimeline(state.timestamp) : Promise.resolve(),isResearch()&&!isBlenderQuery()?loadPresets():Promise.resolve(),isResearch()&&isBlenderQuery()?fetchFrameWall():Promise.resolve(),isResearch()&&state.snapshot?.capabilities?.physical_review===true?loadPhysicalReview():Promise.resolve()]);
  } catch (error) {
    if (error.name !== 'AbortError' && epoch === state.sceneEpoch) { state.error = error.message; state.loading = false; render(); }
  }
}
async function queryScope() {
  if (!state.snapshot || !state.cameraId) return;
  const epoch = ++state.queryEpoch; const sceneEpoch = state.sceneEpoch;
  invalidateEventState(state);state.timelineEpoch+=1;
  Object.assign(state,{scopeMessage:'範圍更新中，保留上一個完整 3D 畫面。',test:null,queryPending:true,guide:null});state.guideEpoch+=1;render();
  try {
    const result = await api('query',{scene_id:state.sceneId,camera_id:state.cameraId,start:state.start,end:state.end});
    if (epoch !== state.queryEpoch || sceneEpoch !== state.sceneEpoch) return;
    state.events = safeList(result.events); state.observations = safeList(result.observations); state.retrieval = result.retrieval;
    state.scopeMessage = result.message ?? null;state.queryPending=false;
    render();
  } catch (error) {
    if (error.name !== 'AbortError' && epoch === state.queryEpoch && sceneEpoch === state.sceneEpoch) { state.error = error.message;state.queryPending=false;render(); }
  }
}
async function fetchTimeline(timestamp) {
  if (!isResearch() || !state.snapshot || !state.cameraIds.length) return;
  const sceneEpoch = state.sceneEpoch; const epoch = ++state.timelineEpoch;
  try {
    const result = await api('timeline',{scene_id:state.sceneId,camera_ids:state.cameraIds,timestamp});
    if (sceneEpoch !== state.sceneEpoch || epoch !== state.timelineEpoch) return;
    const frames=safeList(result.frames);
    if(!await prepareFrames(frames,mediaURL,{current:()=>sceneEpoch===state.sceneEpoch&&epoch===state.timelineEpoch}))return;
    state.frames = frames; state.timestamp = timestamp;
    updateTimelineDOM();
  } catch (error) {
    if (error.name !== 'AbortError' && epoch === state.timelineEpoch && sceneEpoch === state.sceneEpoch) toast(error.message);
  }
}
async function selectEvent(ref) {
  stopPlayback();
  invalidateEventState(state);state.timelineEpoch+=1;
  state.selectedEvent=ref;state.selectedObject=null;
  state.eventPending=true;
  const ticket={sceneEpoch:state.sceneEpoch,eventEpoch:state.eventEpoch,eventRef:ref};
  render();
  try {
    const result = await api('event',{scene_id:state.sceneId,event_ref:ref});
    if (!eventRequestIsCurrent(state,ticket)) return;
    Object.assign(state,{event:result.event,eventPending:false,notes:safeList(result.notes),selectedEvent:ref,selectedObject:null,page:'workspace',mode:'display',resourceTab:'events'});
    const range = normalizeRange(result.event.time_range);
    state.timestamp = range[0]; render();
    if (isResearch()) await fetchTimeline(state.timestamp);
  } catch (error) { if (error.name !== 'AbortError' && eventRequestIsCurrent(state,ticket)){state.eventPending=false;toast(error.message);} }
}

function gateway() {
  return `<main class="gateway"><section class="gateway-left"><div class="brand"><span class="brand-mark">A</span><div>AMIDST<small>SPATIAL RESEARCH WORKBENCH</small></div></div>
    <div class="gateway-copy"><div class="eyebrow">ONE WORKSPACE. EVERY SCENE.</div><h1>從每個畫面，<br>看見<span>空間裡的脈絡。</span></h1><p>在同一個工作台，探索場景、檢視證據，<br>讓每一次人工審查都有跡可循。</p>
    <div class="scene-motif" aria-hidden="true"><div class="motif-plane"><div class="motif-zone"></div><div class="motif-zone two"></div><div class="motif-dot"></div></div></div></div>
    <div class="gateway-footer"><span>DESKTOP WORKSPACE</span><span>LOCAL · VERSION 01</span></div></section>
    <section class="gateway-right"><div class="eyebrow">CHOOSE YOUR WORKSPACE</div><h2>選擇你的工作身份</h2><p class="gateway-caption">直接進入，隨時可以切換身份。</p>
    ${state.error ? `<div class="inline-error">${h(state.error)}</div>` : ''}
    <button class="role-card" data-role="research"><span class="role-icon">${icon('test')}</span><span class="arrow">${icon('arrow')}</span><h3>研究 <small>RESEARCH</small></h3><p>從影像與空間證據出發，測試候選結果，編輯及發布人工審查版本。</p><span class="tags"><span class="tag">完整研究資料</span><span class="tag">場景人審</span><span class="tag">測試與診斷</span></span></button>
    <button class="role-card management" data-role="management"><span class="role-icon">${icon('layers')}</span><span class="arrow">${icon('arrow')}</span><h3>管理 <small>MANAGEMENT</small></h3><p>掌握場域與事件概況，檢視必要證據，記錄備註與處理狀態。</p><span class="tags"><span class="tag">事件摘要</span><span class="tag">證據檢視</span><span class="tag">處理紀錄</span></span></button>
    <p class="gateway-note">本機展示採直接身份切換，無需登入。<br>研究與管理使用各自的資料視圖；此入口不作為帳號驗證。</p></section></main>`;
}
function sidebar() {
  const nav = [ ['dashboard','home','主控板','OVERVIEW'],['workspace','cube','共用工作區','WORKSPACE'],
    ...(isResearch() ? [...(!isBlenderQuery()?[['investigation','event','人物調查','INVESTIGATION'],['presentations','play','實驗展示','PRESENTATIONS']]:[]),...(sceneReviewAllowed(state.snapshot)?[['review','review','人工審查','REVIEW']]:[]),['test','test','測試與評估','TEST']] : []) ];
  if(isResearch())return `<header class="research-navigation"><div class="brand"><span class="brand-mark">A</span><div>AMIDST<small>研究／工程工作台</small></div></div><nav class="top-nav" aria-label="研究工作台導覽">${nav.map(([id,glyph,label])=>`<button class="nav-button ${state.page===id?'active':''}" data-page="${id}" ${state.page===id?'aria-current="page"':''}>${icon(glyph)}<span>${label}</span></button>`).join('')}</nav><button class="role-switch" data-action="switch-role">${icon('switch')}研究身份 · 切換</button></header>`;
  return `<aside class="sidebar"><div class="brand"><span class="brand-mark">A</span><div>AMIDST<small>SHARED WORKBENCH</small></div></div><div class="nav-label">WORKSPACE</div><nav class="side-nav">${nav.map(([id,glyph,label]) => `<button class="nav-button ${state.page === id ? 'active' : ''}" data-page="${id}">${icon(glyph)}<span>${label}</span>${state.page === id ? '<span class="tiny">●</span>' : ''}</button>`).join('')}</nav>
    <div class="sidebar-context"><div class="nav-label" style="padding:0">CURRENT SCENE</div><div class="context-title"><span class="status-dot"></span>${h(short(state.snapshot?.label ?? selectedScene()?.label ?? '載入中',20))}</div><div class="context-sub">${isResearch() ? isBlenderQuery()?'來源模型唯讀<br>多鏡頭 · 有界畫面檢索':`標註版本 v${h(sourceVersion(state))}<br>局部範圍 · 按需載入` : '事件與必要證據<br>精簡管理視圖'}</div></div>
    <div class="sidebar-bottom"><div class="role-current"><div class="avatar">${isResearch() ? '研' : '管'}</div><div><strong>${isResearch() ? '研究工作台' : '管理主控板'}</strong><small>${isResearch() ? 'Research · full workspace' : 'Management · overview'}</small></div></div><button class="role-switch" data-action="switch-role">${icon('switch')}切換身份</button></div></aside>`;
}
function topbar() {
  const title = ({dashboard:'主控板',workspace:'共用工作區',review:'人工審查',test:'測試與評估',presentations:'實驗展示',investigation:'人物調查'})[state.page];
  return `<header class="topbar"><div class="breadcrumb">工作台 ${icon('chevron')} <strong>${title}</strong></div><div class="topbar-tools"><label class="select-shell">${icon('layers')}<select id="scene-select" aria-label="切換場景">${safeList(state.bootstrap?.scenes).map((scene) => `<option value="${h(scene.scene_id)}" ${scene.scene_id === state.sceneId ? 'selected' : ''}>${h(scene.label ?? scene.scene_id)}</option>`).join('')}</select></label>${badge('本機資料','cyan')}</div></header>`;
}
function pageHead(eyebrow,title,description,actions = '') {
  return `<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>${actions ? `<div class="head-actions">${actions}</div>` : ''}</div>`;
}
function eventRows(limit = 6) {
  if (!state.events.length) return empty('目前範圍沒有事件','可切換鏡頭或調整時間窗。','event');
  return `<div class="event-list">${state.events.slice(0,limit).map((event) => {
    const [start,end] = normalizeRange(event.time_range);
    return `<button class="event-row ${event.event_ref === state.selectedEvent ? 'selected' : ''}" data-event="${h(event.event_ref)}"><span class="event-icon">${icon(event.kind === 'INFERRED_GAP_ALTERNATIVES' ? 'link' : 'event')}</span><span class="event-text"><strong>${h(eventLabel(event.kind))}</strong><small>${h(safeList(event.camera_ids).map(cameraName).join(' · '))}<br>${h(evidenceLabel(event.evidence_state,isResearch()))}${event.support_state?' · '+h(supportLabel(event.support_state)):''}</small></span><span>${fmt(start)}–${fmt(end)} s</span></button>`;
  }).join('')}</div>`;
}
export function frameSourceLabel(frame,snapshot={}) {
  const blender=frame.media_kind==='BLENDER_CAMERA_IMAGE'||frame.source_kind==='BLENDER_CAMERA_IMAGE'||snapshot.media_kind==='BLENDER_CAMERA_IMAGE'||supportsFrameQuery(snapshot);
  return blender?'Blender camera 截圖 · 原模型幾何'+(frame.substitute_target!==false?' · 橙色目標為替代資料':''):'模擬來源影像';
}
function frameHTML(frame) {
  const ref = frame.media_ref ?? frame.ref;
  const kind=frameSourceLabel(frame,state.snapshot);
  return `<div class="frame" data-frame-camera="${h(frame.camera_id)}" data-frame-ref="${h(ref??'')}">${ref ? `<button class="frame-enlarge" data-image="${h(ref)}" aria-label="放大 ${h(cameraName(frame.camera_id))} 來源影像"><img src="${h(mediaURL(ref))}" alt="${h(cameraName(frame.camera_id))}，${h(frameTimeLabel(frame.timestamp))} 的${kind}" loading="lazy"></button>` : `<div class="frame-empty">${icon('camera')}<span>${h(frame.status ?? '此時間沒有影像')}</span></div>`}<div class="frame-caption"><strong>${h(cameraName(frame.camera_id))}</strong><span>${h(frameTimeLabel(frame.timestamp))}</span></div><small class="frame-kind">${kind}</small></div>`;
}
function currentFrames(limit = 3) {
  return state.frames.slice(0,limit).map(frameHTML).join('') || `<div class="frame-empty" style="grid-column:1/-1">${icon('camera')}<span>此場景尚未提供可同步的來源影像</span></div>`;
}
function dashboard() {
  const cameraCount = cameras().length;
  const isSceneOnly = !state.events.length && !state.observations.length;
  const scope = state.cameraId ? `${h(cameraName(state.cameraId))} · ${fmt(state.start)}–${fmt(state.end)} s` : '場景資料';
  const stats = [
    ['已載入鏡頭',cameraCount,'個','camera','場景資料包提供的鏡頭'],
    [isResearch() ? '可審查物件' : '範圍內事件',isResearch() ? objects().length : state.events.length,'項',isResearch() ? 'cube' : 'event',isResearch() ? '區域、門、可行走面與鏡頭' : scope],
    [isResearch() ? '範圍內事件' : '來源場景',isResearch() ? state.events.length : 1,isResearch() ? '項' : '個','event',isResearch() ? scope : h(state.snapshot.label)],
    [isResearch() ? '標註版本' : '證據狀態',isResearch() ? `v${sourceVersion(state)}` : '待檢視','','review',isResearch() ? '原始資料與歷史版本保留' : '候選事件需人工確認'],
  ];
  return `${pageHead(isResearch() ? 'RESEARCH OVERVIEW' : 'MANAGEMENT OVERVIEW',isResearch() ? '研究主控板' : '場域概況',isResearch() ? '把場景、證據與人工判定放在同一個脈絡裡。' : '查看目前場景的事件摘要，從必要證據了解每個候選事件。',`<button class="btn primary" data-page="workspace">開啟工作區 ${icon('arrow')}</button>`)}
    <div class="stats-grid">${stats.map(([label,value,unit,glyph,caption],i) => `<article class="stat-card ${i===0?'highlight':''}"><span class="stat-icon">${icon(glyph)}</span><div class="stat-label">${label}</div><div class="stat-value">${h(value)}<small>${unit}</small></div><div class="stat-caption">${caption}</div></article>`).join('')}</div>
    <div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h2>目前場景</h2><p>共用畫面，依場景能力顯示資料</p></div>${badge(isSceneOnly ? '場景審查' : '影像與事件','purple')}</div><div class="context-cover"><div class="eyebrow">ACTIVE SCENE</div><h3>${h(state.snapshot.label)}</h3><p>${h(state.snapshot.description ?? '檢視此場景已提供的資產、鏡頭與審查對象。')}</p></div>
    <div class="source-strip"><div><span>資料範圍</span><strong>${scope}</strong></div><div><span>${isResearch() ? '標註版本' : '顯示模式'}</span><strong>${isResearch() ? `v${sourceVersion(state)} · 版本綁定` : '管理 · 事件摘要'}</strong></div><div><span>可用能力</span><strong>${cameraCount} 個鏡頭${isResearch() ? ` · ${objects().length} 個物件` : ''}</strong></div></div>
    ${isResearch() ? `<div class="snapshot-frames" data-frames="dashboard">${currentFrames()}</div>` : `<div class="panel-body" style="padding-top:18px"><p class="muted" style="font-size:11px;margin:0">點選右側事件，即可檢視來源畫面及處理紀錄。</p></div>`}</section>
    <section class="panel"><div class="panel-head"><div><h2>事件速覽</h2><p>${scope}</p></div>${badge(`${state.events.length} 項`)}</div>${eventRows(5)}<div class="panel-foot"><span>顯示目前局部查詢結果</span><button class="micro-link" data-page="workspace">檢視全部 ${icon('arrow')}</button></div></section></div>
    ${isResearch() ? `<div class="workflow"><button class="workflow-card" data-page="workspace"><span class="step-number">01</span><div><h3>探索與展示</h3><p>同步查看來源影像、局部空間與候選事件。</p></div></button><button class="workflow-card" data-page="${isBlenderQuery()?'workspace':'review'}"><span class="step-number">02</span><div><h3>${isBlenderQuery()?'Top-K 畫面檢索':'人工審查'}</h3><p>${isBlenderQuery()?'用預設鏡頭與時間，取得基底演算法的畫面結果。':'編輯草案，驗證差異後發布新標註版本。'}</p></div></button><button class="workflow-card" data-page="test"><span class="step-number">03</span><div><h3>測試與追溯</h3><p>執行範圍檢查，獨立查看評估與工具紀錄。</p></div></button></div>` : managementPlaceholder()}
    ${isResearch() ? technical('場景來源與版本資訊',{scene_id:state.snapshot.scene_id,source_hash:state.snapshot.source_hash,model_revision:state.snapshot.model_revision,run_id:state.snapshot.run_id,capabilities:state.snapshot.capabilities}) : ''}`;
}
function managementPlaceholder() {
  return `<section class="panel placeholder-panel"><div class="panel-head"><div><h2>空間與多鏡頭展示</h2><p>為後續管理展示保留一致的空間</p></div>${badge('尚未接入')}</div><div class="placeholder-space"><div class="placeholder-main">${icon('cube')}<h3>3D 場景展示區</h3><p>此版本先提供事件與必要證據。<br>空間模型及多鏡頭模擬畫面將在此呈現。</p></div><div class="placeholder-cameras">${[1,2,3].map((i) => `<div class="placeholder-camera">${icon('camera')}CAMERA ${String(i).padStart(2,'0')} · 預留</div>`).join('')}</div></div></section>`;
}
function scopeBar() {
  return `<form id="scope-form" class="scope-bar"><label class="field"><span>查詢鏡頭</span><select name="camera_id" ${!cameras().length?'disabled':''}>${cameras().map((camera) => `<option value="${h(camera.camera_id)}" ${camera.camera_id === state.cameraId?'selected':''}>${h(camera.label ?? camera.camera_id)}</option>`).join('')}</select></label>${isResearch()?timeSegmentField({start:state.start,end:state.end}):`<label class="field time-input"><span>起始秒數</span><input name="start" type="number" step="0.1" value="${state.start}" required></label><label class="field time-input"><span>結束秒數</span><input name="end" type="number" step="0.1" value="${state.end}" required></label>`}<button class="btn primary" type="submit" ${!state.cameraId?'disabled':''}>更新範圍</button><div class="scope-note">${icon('info')} 僅載入選定範圍；擴展鏡頭需主動選取。</div></form>${state.scopeMessage ? `<div class="notice">${icon('info')}<p>${h(state.scopeMessage)}</p></div>` : ''}`;
}
function workspaceTabs() {
  if (!isResearch()) return '';
  return `<div class="tabs" role="tablist" aria-label="工作模式">${[['display','cube','展示'],...(sceneReviewAllowed(state.snapshot)?[['review','review','人審']]:[]),['test','test','測試']].map(([id,glyph,label]) => `<button class="tab ${state.mode===id?'active':''}" data-mode="${id}" role="tab" aria-selected="${state.mode===id}">${icon(glyph)}${label}</button>`).join('')}</div>`;
}
function resourceList() {
  return `<aside class="resources"><div class="resource-head">場景資源 ${badge(state.resourceTab==='objects' ? objects().length : state.events.length)}</div><div class="resource-tabs"><button class="resource-tab ${state.resourceTab==='objects'?'active':''}" data-resource-tab="objects">物件</button><button class="resource-tab ${state.resourceTab==='events'?'active':''}" data-resource-tab="events">事件</button></div><div class="resource-items">${state.resourceTab === 'objects' ? objects().map((item) => `<button class="resource-item ${item.object_id === state.selectedObject?'selected':''}" data-object="${h(item.object_id)}">${icon(objectIcon(item.kind))}<span><strong>${h(item.label ?? item.object_id)}</strong><small>${h(objectLabel(item.kind))}</small></span></button>`).join('') || empty('沒有可選物件') : state.events.map((event) => `<button class="resource-item ${event.event_ref === state.selectedEvent?'selected':''}" data-event="${h(event.event_ref)}">${icon('event')}<span><strong>${h(eventLabel(event.kind))}</strong><small>${normalizeRange(event.time_range).map((v)=>fmt(v)).join('–')} s${event.support_state?' · '+h(supportLabel(event.support_state)):''}</small></span></button>`).join('') || empty('範圍內没有事件')}</div></aside>`;
}
function viewport() {
  const source=isBlenderQuery();
  return `<div class="viewport"><div class="viewport-overlay">${badge(source?'原 .blend 局部模型 · 預設平滑材質':'模擬 3D · 公尺','cyan')} ${badge(activeReview() ? state.draft && state.draftPreview ? '草案預覽 · 尚未發布' : `標註 v${previewVersion()} · 審查預覽` : source?'來源幾何 · PARTIAL':'來源基線 · 凍結結果')}${state.guide?badge('節點與邊 · DISPLAY_ONLY','cyan'):''}${state.reconstructionMode==='physical'&&state.physicalResult?'<span class="badge cyan cross-camera-badge">物理篩選 · '+h(selectedPhysicalCandidate(state.physicalResult,state.physicalChoice)?.physical?.verdict??'UNKNOWN')+'</span>':state.crossCameraResult?'<span class="badge cyan cross-camera-badge">跨鏡頭候選 '+state.crossCameraRank+' · 未確認</span>':''}</div><div data-scene-stage style="height:100%"><div class="viewport-fallback">正在載入場景…</div></div><div class="viewport-help">拖曳旋轉 · Shift＋拖曳平移 · 滾輪縮放 · 點選物件</div><div class="viewport-controls">${state.guide?`<button class="btn small ghost" data-action="toggle-graph-labels" aria-pressed="${state.showGraphLabels}">${state.showGraphLabels?'收起關聯標註':'標註目前鏡頭關聯'}</button>`:''}<button class="btn small ghost" data-action="reset-view" title="重設視角">${icon('reset')}</button></div></div><p class="body-caption">${source?'來源模型僅呈現本場景已提供的局部 mesh；平滑材質只用於顯示。camera 截圖中的橙色目標為預設替代資料，未確認真實人物或行為。':'人形與節點／邊文字為 DISPLAY_ONLY。節點與邊只呈現來源已有關聯；骨架、步態與插值為展示，候選仍未確認身分。'}</p><div class="legend"><span>${source?'原模型局部幾何':'區域'}</span><span class="teal">可行走面／節點</span><span class="pink">門／通道</span><span class="amber">${source?'替代目標／未定結果':'候選路線'}</span></div>`;
}
function timeline() {
  const [start,end] = normalizeRange(state.snapshot.time_range);
  return `<div class="timeline-panel"><div class="timeline-top"><button class="play-button" data-action="play" aria-label="開始回放" ${end<=start || !state.cameraIds.length?'disabled':''}>${icon(state.playTimer?'pause':'play')}</button><strong>同步時間軸</strong><span data-current-time>${time(state.timestamp)}</span></div><input class="timeline-range" id="timeline-range" aria-label="影像回放時間" type="range" min="${start}" max="${end}" step="${isBlenderQuery()?'.2':'.4'}" value="${state.timestamp}" ${end<=start?'disabled':''}><div class="timeline-labels"><span>${time(start)}</span><span>${time(end)}</span></div><div class="time-lanes" data-time-lanes>${timeLanes()}</div><p class="replay-status">以來源時間選取可用影格；無資料時保留缺圖狀態。${isBlenderQuery()?'此處回放既有 camera 截圖；下方可查看本次查詢的物理曲線與預先物化還原影片。':''}</p></div>`;
}
function timeLanes() {
  const [start,end] = normalizeRange(state.snapshot.time_range); const length = Math.max(.001,end-start);
  return state.cameraIds.map((cameraId) => `<div class="time-lane"><span>${h(cameraName(cameraId))}</span><div class="time-track">${state.events.filter((event) => safeList(event.camera_ids).includes(cameraId)).map((event) => {
    const [a,b] = normalizeRange(event.time_range);
    return `<span class="time-mark ${event.kind==='INFERRED_GAP_ALTERNATIVES'?'gap':''}" title="${h(eventLabel(event.kind))}" style="left:${Math.max(0,Math.min(100,(a-start)/length*100))}%;width:${Math.max(.6,Math.min(100,(b-a)/length*100))}%"></span>`;
  }).join('')}<span class="time-mark current" style="left:${Math.max(0,Math.min(100,(state.timestamp-start)/length*100))}%"></span></div></div>`).join('');
}
function cameraSelectors() {
  return `<div class="camera-selectors">${cameras().map((camera) => `<button class="camera-chip ${state.cameraIds.includes(camera.camera_id)?'selected':''}" data-toggle-camera="${h(camera.camera_id)}" aria-pressed="${state.cameraIds.includes(camera.camera_id)}">${icon('camera')} ${h(camera.label ?? camera.camera_id)}</button>`).join('')}</div>`;
}
function researchDisplay() {
  if(isBlenderQuery())return workspaceDisplay();
  return `${scopeBar()}${sourceVersion(state)>0 ? `<div class="notice warning">${icon('info')}<p>標註 v${sourceVersion(state)} 已發布，研究結果尚未重跑。此展示保留來源基線與原本凍結推論；新版幾何請至人審模式預覽。</p></div>` : ''}<div class="workspace-grid">${resourceList()}<div class="workspace-center">${viewport()}${timeline()}${cameraSelectors()}<details class="source-evidence"><summary>來源影像 · 輔助核對</summary><div class="camera-grid" data-frames="workspace">${currentFrames(4)}</div></details>${state.retrieval ? technical('局部查詢收據',state.retrieval) : ''}</div>${inspector()}</div>${guidancePanel()}`;
}
// This host stays separate from the primary scene and media nodes for local review integration.
function workspaceDisplay() {
  return `<div class="blender-workspace"><section class="primary-visual" aria-label="來源模型與分時影格主畫面"><div class="visual-toolbar"><div class="visual-modes" role="group" aria-label="主畫面模式"><button class="btn ${state.visualMode==='3d'?'primary':''}" data-visual-mode="3d" aria-pressed="${state.visualMode==='3d'}">${icon('cube')}3D 模型</button><button class="btn ${state.visualMode==='wall'?'primary':''}" data-visual-mode="wall" aria-pressed="${state.visualMode==='wall'}">${icon('camera')}2D 分時畫面牆</button></div><label class="field visual-time"><span>查詢時間段</span><select data-workspace-time-segment aria-label="主畫面查詢時間段">${timeSegmentOptions(state.frameQuerySelection)}</select></label><div class="wall-sizes" role="group" aria-label="畫面牆格數">${[8,12,16].map(count=>`<button class="btn small ${state.wallSlotCount===count?'cyan':''}" data-wall-slots="${count}" aria-pressed="${state.wallSlotCount===count}">${count} 格</button>`).join('')}</div></div><div data-visual-surface="3d" ${state.visualMode!=='3d'?'hidden':''}>${viewport()}</div><div data-visual-surface="wall" ${state.visualMode!=='wall'?'hidden':''}><p class="wall-caption" data-frame-wall-caption>${frameWallCaption()}</p><div class="frame-wall-grid" data-frame-wall-grid data-slot-count="${state.wallSlotCount}">${frameWallItemsHTML(state.frameWall,{slotCount:state.wallSlotCount,cameraLabel:cameraName,urlFor:mediaURL})}</div><p class="body-caption">每格是同一組登錄鏡頭在不同時間的來源截圖，不代表新增鏡頭。模型與 camera 截圖為實際 Blender 資料；橙色目標為替代資料。最近來源時間影格以框線標示，未確認身分與行為。</p></div></section>${timeline()}${cameraSelectors()}<div id="physical-review-host"></div><div class="workspace-auxiliary"><div class="workspace-center">${frameQueryPanel()}${physicalPanelHTML(state.physicalResult,{available:state.snapshot?.capabilities?.physical_cross_camera_reconstruction===true,pending:state.physicalPending,choice:state.physicalChoice,cameraLabel:cameraName,urlFor:physicalMediaURL})}${crossCameraPanelHTML(state.crossCameraResult,{pending:state.crossCameraPending,rank:state.crossCameraRank,cameraLabel:cameraName,urlFor:crossCameraMediaURL})}${motionPanelHTML(state.motionResult,{pending:state.motionPending,cameraLabel:cameraName,urlFor:motionMediaURL})}<details class="source-evidence blender-source-evidence"><summary>目前同步時間的來源鏡頭 · 輔助核對</summary><div class="camera-grid" data-frames="workspace">${currentFrames(4)}</div></details><details class="technical"><summary>來源場景物件</summary>${resourceList()}</details></div>${inspector()}</div></div>`;
}
export function timeSegments(snapshot) {
  const [start,end]=normalizeRange(snapshot?.time_range),step=supportsFrameQuery(snapshot) ? .2 : .1;
  const boundary=fraction=>Math.max(start,Math.min(end,Number((start+Math.round((end-start)*fraction/step)*step).toFixed(6))));
  const a=boundary(1/3),b=boundary(2/3);
  return [{value:'full',label:'完整',start,end},{value:'early',label:'前段',start,end:a},{value:'middle',label:'中段',start:a,end:b},{value:'late',label:'後段',start:b,end}];
}
export function resolveTimeSegment(values,snapshot) {
  if(values.time_segment===undefined)return {...values};
  const segment=timeSegments(snapshot).find(item=>item.value===values.time_segment);
  if(!segment)throw Error('請選取完整、前段、中段或後段。');
  return {...values,start:segment.start,end:segment.end};
}
function selectedTimeSegment(selection={},snapshot=state.snapshot) {
  return timeSegments(snapshot).find(segment=>Number(selection?.start)===segment.start&&Number(selection?.end)===segment.end)?.value??'full';
}
function timeSegmentOptions(selection={},snapshot=state.snapshot) {
  const selected=selectedTimeSegment(selection,snapshot);
  return timeSegments(snapshot).map(segment=>`<option value="${segment.value}" ${segment.value===selected?'selected':''}>${segment.label} · ${fmt(segment.start)}–${fmt(segment.end)} s</option>`).join('');
}
function timeSegmentField(selection={},snapshot=state.snapshot) {
  const segment=timeSegments(snapshot).find(item=>item.value===selectedTimeSegment(selection,snapshot));
  return `<label class="field time-segment"><span>查詢時間段</span><select name="time_segment" data-time-segment>${timeSegmentOptions(selection,snapshot)}</select><small data-time-segment-detail>${fmt(segment.start)}–${fmt(segment.end)} s · 來源時間</small></label><input name="start" type="hidden" value="${segment.start}"><input name="end" type="hidden" value="${segment.end}">`;
}
export function frameWallSelection(values,snapshot,slotCount=8) {
  values=resolveTimeSegment(values,snapshot);
  const camera_ids=safeList(values.camera_ids),ids=new Set(safeList(snapshot?.cameras).map(camera=>camera.camera_id));
  const [lower,upper]=normalizeRange(snapshot?.time_range),start=Number(values.start),end=Number(values.end);
  if(!supportsFrameQuery(snapshot)||!camera_ids.length||camera_ids.length>4||new Set(camera_ids).size!==camera_ids.length||camera_ids.some(id=>!ids.has(id)))throw Error('畫面牆需選取本場景的鏡頭。');
  if(typeof values.start==='boolean'||typeof values.end==='boolean'||values.start===''||values.start===null||values.start===undefined||values.end===''||values.end===null||values.end===undefined||!Number.isFinite(start)||!Number.isFinite(end)||start<lower||end>upper||end<start||end-start>120)throw Error('畫面牆時間段超出來源範圍。');
  if(![8,12,16].includes(slotCount))throw Error('畫面牆格數必須為 8、12 或 16。');
  return {camera_ids:[...camera_ids],start,end,slot_count:slotCount};
}
export function validateFrameWallResponse(result,selection,snapshot) {
  const binding=result?.source_binding??{},expected=snapshot?.source_binding??{},chosen=result?.selection??{},frames=result?.frames;
  const [lower,upper]=normalizeRange(snapshot?.time_range),ids=new Set(selection.camera_ids);
  const sameCameras=JSON.stringify(safeList(chosen.camera_ids))===JSON.stringify(selection.camera_ids);
  const badBinding=!expected.run_id||!expected.source_sha256||['run_id','source_sha256','site_id','dataset_sha256','clock_id','scale_sha256'].some(key=>expected[key]!==undefined&&binding[key]!==expected[key]);
  if(result?.schema_version!=='workbench.camera-frame-wall.v1'||result.temporal_mosaic!==true||result.data_kind!=='ACTUAL_SOURCE_RGB_TIME_SAMPLES'||result.agent_used!==false||result.real_stream!==false||badBinding||snapshot.scene_id&&result.scope?.scene_id!==snapshot.scene_id||snapshot.baseline?.source_features&&result.scope?.source_features!==snapshot.baseline.source_features||!sameCameras||chosen.slot_count!==selection.slot_count||JSON.stringify(chosen.time_range)!==JSON.stringify([selection.start,selection.end])||result.source_camera_count!==ids.size||!Array.isArray(frames)||frames.length>selection.slot_count||result.retrieval?.indexed!==true||result.retrieval?.source_rgb_scan!==false||!Number.isInteger(result.retrieval?.frame_records_read)||result.retrieval.frame_records_read>16||result.retrieval.frame_records_read<frames.length)throw Error('畫面牆來源、時間段或有界索引不相符。');
  const slots=new Set();
  // Interpolated sample endpoints can differ by a few floating-point ULPs.
  const rangeRoundingTolerance=8*Number.EPSILON*Math.max(1,Math.abs(selection.start),Math.abs(selection.end));
  for(const frame of frames){
    if(!Number.isInteger(frame.slot_index)||frame.slot_index<0||frame.slot_index>=selection.slot_count||slots.has(frame.slot_index)||!ids.has(frame.camera_id)||!Number.isFinite(frame.requested_timestamp)||frame.requested_timestamp<selection.start-rangeRoundingTolerance||frame.requested_timestamp>selection.end+rangeRoundingTolerance||frame.status!=='MISSING'&&(!Number.isFinite(frame.timestamp)||frame.timestamp<lower||frame.timestamp>upper||Math.abs(frame.timestamp-frame.requested_timestamp)>.21||typeof frame.media_ref!=='string')||frame.status==='MISSING'&&(frame.timestamp!==null||frame.media_ref!==null))throw Error('畫面牆影格超出所選來源範圍。');
    slots.add(frame.slot_index);
  }
  return result;
}
export function frameWallRequestIsCurrent(target,ticket) {
  return target.role==='research'&&target.sceneEpoch===ticket.sceneEpoch&&target.sceneId===ticket.sceneId&&target.session?.session_ref===ticket.sessionRef&&target.frameWallEpoch===ticket.frameWallEpoch;
}
export async function runFrameWall(target,selection,send,prepare=async()=>true) {
  target.frameWallSelection={...selection,camera_ids:[...selection.camera_ids]};target.frameWallPending=true;target.frameWallError=null;
  const ticket={sceneEpoch:target.sceneEpoch,sceneId:target.sceneId,sessionRef:target.session?.session_ref,frameWallEpoch:++target.frameWallEpoch},snapshot=target.snapshot;
  const current=()=>frameWallRequestIsCurrent(target,ticket);
  try {
    const result=await send({scene_id:ticket.sceneId,...selection,camera_ids:[...selection.camera_ids]});
    if(!current())return false;
    validateFrameWallResponse(result,selection,snapshot);
    const prepared=await prepare(result.frames,current);if(!current())return false;if(!prepared)throw Error('來源影格尚未完成載入。');
    target.frameWall=result;target.frameWallPending=false;return true;
  }catch(error){if(!current())return false;target.frameWallPending=false;target.frameWall=null;target.frameWallError=error.message;throw error;}
}
export function frameWallNearestSlots(frames,timestamp) {
  if(!Number.isFinite(timestamp))return [];
  const nearest=new Map();
  for(const frame of safeList(frames)){
    if(frame.status==='MISSING'||!Number.isFinite(frame.timestamp)||!frame.media_ref)continue;
    const prior=nearest.get(frame.camera_id),distance=Math.abs(frame.timestamp-timestamp);
    if(!prior||distance<prior.distance||distance===prior.distance&&frame.slot_index<prior.slot_index)nearest.set(frame.camera_id,{slot_index:frame.slot_index,distance});
  }
  return [...nearest.values()].map(frame=>frame.slot_index);
}
export function frameWallItemsHTML(result,{slotCount=8,cameraLabel=id=>id,urlFor=()=>''}={}) {
  const rows=new Map(safeList(result?.frames).map(frame=>[frame.slot_index,frame]));
  return Array.from({length:slotCount},(_,slot)=>{
    const frame=rows.get(slot),ref=frame?.media_ref;
    return `<article class="frame wall-frame" data-wall-slot="${slot}" data-wall-key="${h(ref??'missing')}@${h(frame?.requested_timestamp??slot)}"><div class="wall-slot-label">第 ${slot+1} 格${frame?.repeated_source_frame?' · 重複來源影格':''}</div>${ref?`<button class="frame-enlarge" data-image="${h(ref)}" aria-label="放大 ${h(cameraLabel(frame.camera_id))}，${h(frameTimeLabel(frame.timestamp))}"><img src="${h(urlFor(ref))}" alt="${h(cameraLabel(frame.camera_id))}，${h(frameTimeLabel(frame.timestamp))} 的來源截圖" loading="lazy"></button>`:`<div class="frame-empty">${icon('camera')}<span>MISSING · ${frame?'此時間沒有來源影格':'本次尚無影格資料'}</span></div>`}<div class="frame-caption"><strong>${frame?h(cameraLabel(frame.camera_id)):'鏡頭資料待載入'}</strong><span>${frame?h(frameTimeLabel(frame.timestamp)):'時間未知'}</span></div>${frame?.status==='MISSING'?`<small class="frame-kind">請求 ${h(frameTimeLabel(frame.requested_timestamp))} · 保留缺失</small>`:''}</article>`;
  }).join('');
}
function frameWallCaption() {
  const result=state.frameWall,selection=state.frameWallSelection??state.frameQuerySelection;
  const range=result?.selection?.time_range??[Number(selection?.start),Number(selection?.end)];
  return state.frameWallPending?'正在載入本次時間段；保留上次完整影格，尚未更新。':state.frameWallError?`MISSING · ${state.frameWallError}`:`${result?.source_camera_count??safeList(selection?.camera_ids).length} 個實際鏡頭 · ${state.wallSlotCount} 格分時影格 · ${fmt(range[0])}–${fmt(range[1])} s${result?` · ${result.unique_source_frames??result.frames.filter(frame=>frame.media_ref).length} 個不同來源影格`:''}。僅讀有界來源索引。`;
}
function updateFrameWallCursor(timestamp) {
  const active=new Set(frameWallNearestSlots(state.frameWall?.frames,timestamp));
  $$('[data-wall-slot]').forEach(node=>{const selected=active.has(Number(node.dataset.wallSlot));node.classList.toggle('nearest-source-time',selected);if(selected)node.setAttribute('aria-current','true');else node.removeAttribute('aria-current');});
}
export function syncFrameWallNodes(grid,freshRows) {
  const prior=new Map([...grid.children].map(node=>[node.dataset.wallSlot,node]));
  const selected=freshRows.map(fresh=>{
    const old=prior.get(fresh.dataset.wallSlot);
    return old?.dataset.wallKey===fresh.dataset.wallKey?old:fresh;
  });
  const existing=[...grid.children];
  if(existing.length!==selected.length||selected.some((node,index)=>node!==existing[index]))grid.replaceChildren(...selected);
}
function updateFrameWallDOM() {
  const grid=$('[data-frame-wall-grid]'),caption=$('[data-frame-wall-caption]');
  if(caption)caption.textContent=frameWallCaption();
  if(!grid)return;
  grid.dataset.slotCount=state.wallSlotCount;grid.setAttribute('aria-busy',String(state.frameWallPending));
  if(!state.frameWallPending){
    const template=document.createElement('template');template.innerHTML=frameWallItemsHTML(state.frameWall,{slotCount:state.wallSlotCount,cameraLabel:cameraName,urlFor:mediaURL});
    syncFrameWallNodes(grid,[...template.content.children]);
  }
  updateFrameWallCursor(activeReconstructionTime());
}
async function fetchFrameWall() {
  if(!isResearch()||!isBlenderQuery())return;
  let selection;
  try {selection=frameWallSelection(state.frameQuerySelection??{camera_ids:state.cameraIds,start:state.start,end:state.end},state.snapshot,state.wallSlotCount);}
  catch(error){state.frameWallEpoch++;state.frameWall=null;state.frameWallPending=false;state.frameWallError=error.message;updateFrameWallDOM();return;}
  const pending=runFrameWall(state,selection,payload=>api('camera_frame_wall',payload),(frames,current)=>prepareFrames(frames,mediaURL,{current}));
  updateFrameWallDOM();
  try{if(await pending)updateFrameWallDOM();}catch{updateFrameWallDOM();}
}
function setVisualMode(mode) {
  if(!isResearch()||!isBlenderQuery()||!['3d','wall'].includes(mode))return;
  state.visualMode=mode;
  $$('[data-visual-surface]').forEach(node=>{node.hidden=node.dataset.visualSurface!==mode;});
  $$('[data-visual-mode]').forEach(node=>{const active=node.dataset.visualMode===mode;node.classList.toggle('primary',active);node.setAttribute('aria-pressed',String(active));});
  if(mode==='3d')state.view?.resize();
}
function applyTimeSegment(form,value) {
  const segment=timeSegments(state.snapshot).find(item=>item.value===value);if(!form||!segment)return;
  const select=$('[name="time_segment"]',form);if(select)select.value=value;
  for(const key of ['start','end']){const input=$(`[name="${key}"]`,form);if(input)input.value=segment[key];}
  const detail=$('[data-time-segment-detail]',form);if(detail)detail.textContent=`${fmt(segment.start)}–${fmt(segment.end)} s · 來源時間`;
  const target=$('[name="target_timestamp"]',form);if(target){target.min=segment.start;target.max=segment.end;if(Number(target.value)<segment.start||Number(target.value)>segment.end||target.value==='')target.value=(segment.start+segment.end)/2;}
  const visual=$('[data-workspace-time-segment]');if(visual)visual.value=value;
}
export function frameQuerySelection(values,snapshot) {
  if(!supportsFrameQuery(snapshot))throw Error('此場景未提供畫面檢索。');
  values=resolveTimeSegment(values,snapshot);
  const supplied=Array.isArray(values.camera_ids)?values.camera_ids:[];
  const selection={camera_ids:[...supplied],start:Number(values.start),end:Number(values.end),target_timestamp:Number(values.target_timestamp),top_k:Number(values.top_k),behavior_intent:values.behavior_intent};
  const [start,end]=normalizeRange(snapshot.time_range),ids=new Set(safeList(snapshot.cameras).map(camera=>camera.camera_id));
  if(!supplied.length||supplied.length>4||new Set(supplied).size!==supplied.length||supplied.some(id=>!ids.has(id)))throw Error('請選取本場景的 1–4 個鏡頭。');
  if(['start','end','target_timestamp','top_k'].some(key=>values[key]===''||values[key]===null||values[key]===undefined))throw Error('請填寫完整時間與 Top-K。');
  if(!Number.isFinite(selection.start)||!Number.isFinite(selection.end)||selection.start<start||selection.end>end||selection.end<selection.start||selection.end-selection.start>120)throw Error('請選取資料範圍內、不超過 120 秒的有效時間窗。');
  if(!Number.isFinite(selection.target_timestamp)||selection.target_timestamp<selection.start||selection.target_timestamp>selection.end)throw Error('指定時間必須位於選定時間窗內。');
  if(!Number.isInteger(selection.top_k)||selection.top_k<1||selection.top_k>5)throw Error('Top-K 必須為 1–5 的整數。');
  if(!['walking','running','enter_exit'].includes(selection.behavior_intent))throw Error('請選取行走、跑步或出入。');
  return selection;
}
export function motionSelection(values,snapshot) {
  values=resolveTimeSegment(values,snapshot);
  const selected=frameQuerySelection({...values,target_timestamp:values.start,top_k:1,behavior_intent:'walking'},snapshot);
  return {camera_ids:selected.camera_ids,start:selected.start,end:selected.end};
}
export function crossCameraSelection(values,snapshot) {
  values=resolveTimeSegment(values,snapshot);
  const selected=frameQuerySelection({...values,target_timestamp:values.start,behavior_intent:'walking'},snapshot);
  return {camera_ids:selected.camera_ids,start:selected.start,end:selected.end,top_k:selected.top_k};
}
export function invalidateFrameQuery(target,values) {
  target.frameQueryEpoch=(target.frameQueryEpoch??0)+1;target.frameQuery=null;target.frameQueryPending=false;
  if(values)target.frameQuerySelection={...values,camera_ids:[...(values.camera_ids??[])]};
}
export function frameQueryRequestIsCurrent(target,ticket) {
  return target.role==='research'&&target.sceneEpoch===ticket.sceneEpoch&&target.sceneId===ticket.sceneId&&target.session?.session_ref===ticket.sessionRef&&target.frameQueryEpoch===ticket.frameQueryEpoch;
}
export async function runFrameQuery(target,selection,send) {
  target.frameQuerySelection={...selection,camera_ids:[...selection.camera_ids]};target.frameQuery=null;target.frameQueryPending=true;
  const ticket={sceneEpoch:target.sceneEpoch,sceneId:target.sceneId,sessionRef:target.session?.session_ref,frameQueryEpoch:++target.frameQueryEpoch};
  const request={scene_id:ticket.sceneId,...selection,camera_ids:[...selection.camera_ids]};
  try {
    const result=await send(request);
    if(!frameQueryRequestIsCurrent(target,ticket))return false;
    target.frameQuery=result;target.frameQueryPending=false;return true;
  } catch(error) {
    if(!frameQueryRequestIsCurrent(target,ticket))return false;
    target.frameQueryPending=false;throw error;
  }
}
export function frameQueryItemsHTML(result,{cameraLabel=id=>id,urlFor=()=>'',snapshot={}}={}) {
  const items=safeList(result?.items);
  if(!items.length)return empty('此範圍沒有符合的畫面','可調整時間與鏡頭；不以其他場景補圖。','camera');
  return items.map((item,index)=>{
    const names={RELIABLE_COMPONENT_FIRST:'優先選取可靠像素區塊',PARTIAL_OR_MERGED_COMPONENT:'像素區塊部分可見或發生合併',VALID_FLOOR_PROJECTION:'具備有效地面投影',FLOOR_PROJECTION_UNAVAILABLE:'尚無可用地面投影',NEAREST_REQUESTED_TIME_WITH_STABLE_TIE_BREAK:'接近指定來源時間，同分時固定排序'};
    const reason=safeList(item.rank_reasons??item.reasons).map(value=>typeof value==='string'?names[value]??value:presentationJSON(value)).join('；');
    const ref=item.media_ref;
    return `<article class="baseline-frame-result"><div class="baseline-frame-text"><h3>第 ${h(item.rank??index+1)} 個畫面 · ${h(cameraLabel(item.camera_id))}</h3><p>來源時間：${h(frameTimeLabel(item.timestamp))}</p><p>排序理由：${h(presentationData(reason||'依來源時間與量測品質排序'))}</p>${item.selection_reason?`<p>${item.selection_reason==='FIRST_BEST_PER_CAMERA'?'保留此鏡頭的最佳代表畫面':'依目前範圍排序補足 Top-K'}</p>`:''}<p>資料來源：${h(frameSourceLabel({...item,substitute_target:true},snapshot))}</p><p>投影：${h(item.projection_status??'未提供')} · 行為未確認</p>${technical('本畫面的實際像素量測與投影',{measurement_status:item.measurement_status,bbox_xyxy:item.bbox_xyxy??item.bbox,contact_pixel:item.contact_pixel??item.contact,projection_status:item.projection_status,world_position:item.world_position})}</div>${ref?`<button class="frame-enlarge baseline-preview" data-image="${h(ref)}" aria-label="放大第 ${h(item.rank??index+1)} 個檢索畫面"><img src="${h(urlFor(ref))}" alt="${h(cameraLabel(item.camera_id))} ${h(frameTimeLabel(item.timestamp))} 的檢索畫面" loading="lazy"></button>`:''}</article>`;
  }).join('');
}
function frameQueryPanel() {
  const selection=state.frameQuerySelection??{},[start,end]=normalizeRange(state.snapshot.time_range),result=state.frameQuery;
  return `<section class="panel baseline-query-panel"><div class="panel-head"><div><h2>查詢與檢索 Top-K 畫面</h2><p>使用固定基底演算法判斷與排序</p></div>${badge('本機演算法 · 無 Agent','cyan')}</div><div class="panel-body"><form id="frame-query-form" class="baseline-query-form"><fieldset class="baseline-cameras"><legend>檢索鏡頭（本場景預設）</legend>${cameras().map(camera=>`<label><input type="checkbox" name="camera_ids" value="${h(camera.camera_id)}" ${safeList(selection.camera_ids).includes(camera.camera_id)?'checked':''}>${h(camera.label??camera.camera_id)}</label>`).join('')}</fieldset>${timeSegmentField(selection)}<label class="field"><span>指定搜尋時間</span><input name="target_timestamp" type="number" step=".1" min="${start}" max="${end}" value="${selection.target_timestamp??start}" required></label><label class="field"><span>Top-K（1–5）</span><input name="top_k" type="number" min="1" max="5" step="1" value="${selection.top_k??3}" required></label><label class="field"><span>行為意圖</span><select name="behavior_intent">${[['walking','行走'],['running','跑步'],['enter_exit','出入']].map(([value,label])=>`<option value="${value}" ${selection.behavior_intent===value?'selected':''}>${label}</option>`).join('')}</select></label><button class="btn primary" type="submit" ${state.frameQueryPending?'disabled':''}>${state.frameQueryPending?'檢索中…':'檢索 Top-K 畫面'}</button><button class="btn" type="button" data-action="motion-reconstruct" ${state.motionPending?'disabled':''}>產生物理曲線與還原</button><button class="btn" type="button" data-action="cross-camera-reconstruct" ${state.crossCameraPending?'disabled':''}>跨鏡頭多解還原</button><button class="btn" type="button" data-action="physical-reconstruct" ${state.physicalPending||state.snapshot?.capabilities?.physical_cross_camera_reconstruction!==true?'disabled':''}>門／走廊／碰撞篩選</button></form><p class="status-text">只在所選鏡頭與時間窗檢索。行為選項為查詢意圖；排序不是機率，人物身分與行為仍為未定。Top-K 輸出畫面訊息；物理曲線依本次範圍，還原影片標示預先物化的完整範圍。</p><div class="baseline-query-result" aria-live="polite">${result?`<p>${h(result.status)} · ${safeList(result.items).length} 個畫面 · 基底演算法</p>${frameQueryItemsHTML(result,{cameraLabel:cameraName,urlFor:mediaURL,snapshot:state.snapshot})}${technical('有界檢索的實際讀取',result.retrieval)}${technical('本次資料來源與替代資料',{scope:result.scope??result.source_binding,source_types:result.source_types??result.source_layers,provider:result.provider,agent_used:result.agent_used,behavior_verdict:result.behavior_verdict,score_is_probability:result.ranking?.score_is_probability??result.scores_are_probabilities})}`:empty('尚未檢索','選取預設鏡頭與時間，取得 Top-K 畫面。','camera')}</div></div></section>`;
}
async function loadPresets() {
  const epoch=state.sceneEpoch;
  try {
    const result=await api('semantic_presets',{scene_id:state.sceneId});
    if(epoch!==state.sceneEpoch)return;
    state.presets=result.presets;state.presetsError=null;state.guideSelection={...result.presets.defaults};render();
  } catch(error){if(error.name!=='AbortError'&&epoch===state.sceneEpoch){state.presetsError=error.message;render();}}
}
export const resultStatus=result=>result?.status??(result?.passed===true?'PASS':result?.passed===false?'FAIL':'UNKNOWN');
export function guidanceSelection(values,presets) {
  const selection={label:String(values.label??'').trim(),camera_id:values.camera_id,start:Number(values.start),end:Number(values.end),behavior:values.behavior,top_k:Number(values.top_k)};
  const [start,end]=presets.time_range;
  if(!selection.label||!presets.cameras.some(camera=>camera.camera_id===selection.camera_id))throw Error('請選取來源資料中的鏡頭與 label。');
  if(!Number.isFinite(selection.start)||!Number.isFinite(selection.end)||selection.end<selection.start||selection.start<start||selection.end>end||selection.end-selection.start>120)throw Error('請選取資料範圍內、不超過 120 秒的有效時間窗。');
  if(!presets.behaviors.some(item=>item.value===selection.behavior))throw Error('請選取行走、跑步或出入。');
  if(!Number.isInteger(selection.top_k)||selection.top_k<1||selection.top_k>8)throw Error('Top-K 必須為 1–8 的整數。');
  return selection;
}
const probeStageLabel=value=>({readers:'併發讀取',appends:'併發新增',publish_conflict:'同版本發布衝突',reopen_replay:'重開與差異還原'})[value]??value;
const optionValue=item=>typeof item==='string'?item:item.value??item.label;
export function guidanceRelationsHTML(input,snapshot) {
  const nodes=safeList(input?.navigation_nodes),edges=safeList(input?.navigation_edges);
  const labels=new Map(nodes.map(node=>[node.node_ref,node.resource_id]));
  const graph=guidanceGraph(input,snapshot);
  return `<details class="technical"><summary>節點與邊的來源關聯 · ${nodes.length} 節點／${edges.length} 邊</summary><div class="panel-body"><p>3D 可定位 ${graph.nodes.length} 個節點；未知位置保留為文字。此關聯用於快速檢索。</p><p>節點：${nodes.map(node=>h(node.resource_id)).join(' · ')||'無'}</p>${edges.map(edge=>`<p>${h(labels.get(edge.from_ref)??'來源節點')} → ${h(labels.get(edge.to_ref)??'來源節點')} · ${h(({CONFIGURED_CAMERA_LINK:'預設鏡頭連結',REGISTERED_COVERAGE:'登錄涵蓋關聯',CONFIGURED_REGION_LINK:'預設區域連結'})[edge.relation]??edge.relation)}</p>`).join('')||'<p>沒有已提供的邊。</p>'}</div></details>`;
}
function guidancePanel() {
  const presets=state.presets;if(!presets)return `<section class="panel wide-section"><div class="panel-body"><p>${h(state.presetsError??'預設時間、地點與行為載入中。')}</p></div></section>`;
  const selection=state.guideSelection??presets.defaults??{},labels=presets.labels??['navigation'];
  const [start,end]=presets.time_range??normalizeRange(state.snapshot?.time_range);
  const guide=state.guide;
  return `<section class="panel wide-section"><div class="panel-head"><div><h2>從預設線索快速查找</h2><p>圖形演算法先整理有限資料，再交給 MockAgent 判斷</p></div>${badge('本機 · 有界檢索','cyan')}</div><div class="panel-body"><form id="guidance-form" class="guidance-form">
    <label class="field"><span>地點（資料內預設）</span><select name="place"><option>${h(presets.place?.label??state.snapshot?.label)}</option></select></label>
    <label class="field"><span>鏡頭</span><select name="camera_id">${safeList(presets.cameras).map(camera=>`<option value="${h(camera.camera_id)}" ${camera.camera_id===(selection.camera_id??state.cameraId)?'selected':''}>${h(camera.label??camera.camera_id)}</option>`).join('')}</select></label>
    ${timeSegmentField(selection,{time_range:[start,end]})}
    <label class="field"><span>行為（使用者選取）</span><select name="behavior">${safeList(presets.behaviors).map(item=>`<option value="${h(item.value)}" ${item.value===selection.behavior?'selected':''}>${h(item.label)}</option>`).join('')}</select></label>
    <label class="field"><span>檢索 label</span><input name="label" list="guidance-labels" value="${h(selection.label??'navigation')}" maxlength="160" required><datalist id="guidance-labels">${labels.map(item=>`<option value="${h(optionValue(item))}"></option>`).join('')}</datalist></label>
    <label class="field"><span>Top-K</span><input name="top_k" type="number" min="1" max="8" step="1" value="${selection.top_k??3}" required></label><button class="btn primary" type="submit">整理目標指引</button></form>
    <p class="status-text">行走、跑步、出入是查詢意圖；選取不會確認畫面中的行為。Agent 只讀有限指引，禁止全場景掃描。</p>
    ${guide?`<div class="guidance-result"><div class="split-title"><h3>目標指引 · ${h(guide.status??'已建立')}</h3><button class="btn cyan" data-action="agent-decision" ${!guide.guide_ref?'disabled':''}>執行 MockAgent 判斷</button></div><p>${guide.status==='READY'?'已整理有限檢索目標；候選與未定狀態保留。':'需要補充 label 或範圍；未進行全場景掃描。'}</p>${guidanceRelationsHTML(guide.agent_input,state.snapshot)}${technical('實際送給 Agent 的輸入',guide.agent_input)}${guide.agent_output?technical('Agent 實際輸出',guide.agent_output):'<p class="status-text">指引已整理；尚未取得 Agent 輸出。</p>'}${guide.executed_actions?technical('本次有限工具呼叫的實際結果',guide.executed_actions):''}</div>`:''}
    </div></section>`;
}
export function portFlowHTML(result) {
  if(!result)return '';
  return safeList(result.ports).map((port,index)=>`<article class="port-flow"><div class="split-title"><h3>${index+1}. ${h(port.port??port.name)}</h3>${badge(port.status??'UNKNOWN',port.status==='PASS'?'cyan':'amber')}</div><p>${h(port.from_layer)} → ${h(port.to_layer)}</p>${port.data_kind||port.source_kind||port.data_source?`<p>本層資料：${h(port.data_kind??port.source_kind??port.data_source)}</p>`:''}<div class="port-io">${technical('實際輸入',port.input)}${technical('實際輸出',port.output)}</div></article>`).join('');
}
function systemPortsPanel() {
  const result=state.portTest,probe=state.storageProbe;
  const blender=isBlenderQuery();
  return `<section class="panel wide-section"><div class="panel-head"><div><h2>整個系統的端口測試</h2><p>${blender?'以目前場景的 Blender camera 截圖重跑，逐層標示實際與替代資料':'固定替代資料逐層通過實際服務；輸入與輸出均可核對'}</p></div>${badge(blender?'Blender 資料與替代資料':'模擬測試','purple')}</div><div class="panel-body"><button class="btn primary" data-action="system-ports">執行整條資料流</button><p class="status-text">${blender?'本場景截圖輸入實際量測、投影與畫面檢索；圖與歷史若使用隔離 fixture 會明標 SUBSTITUTE；物理曲線與還原影片依本次物化狀態顯示。此流程不使用 Agent。':'範圍：本機端口與資料契約，使用 SYNTHETIC_PORT_TEST。'}此結果不代表學校研究驗收或實體攝影機資料。</p>${result?`<div class="notice"><p>${h(result.status)} · ${h(result.data_kind)}</p></div>${technical('本次摘要與來源',{...result.summary,source_layers:result.source_layers,scene_used_as_input:result.scene_used_as_input})}${portFlowHTML(result)}${!blender&&result.agent_input?technical('送給 Agent 的實際輸入',result.agent_input):''}${!blender&&result.agent_output?technical('Agent 實際輸出',result.agent_output):''}`:empty('尚未執行系統端口測試','執行後可逐層展開具體資料。','test')}
    <div class="subtle-rule"></div><h3>儲存層階段性併發測試</h3><div class="investigation-controls"><label class="field"><span>測試階段</span><select id="storage-probe-stage">${['all','readers','appends','publish_conflict','reopen_replay'].map(stage=>`<option value="${stage}" ${stage===state.storageStage?'selected':''}>${stage==='all'?'全階段':probeStageLabel(stage)}</option>`).join('')}</select></label><button class="btn" data-action="storage-probe">執行隔離資料庫測試</button></div><p class="status-text">每次使用獨立暫存資料庫與假資料；結果只描述本次併發負載。</p>${probe?`<p>本次狀態：${h(resultStatus(probe))}</p>${safeList(probe.phases).map(phase=>`<article class="port-flow"><h3>${h(probeStageLabel(phase.stage))} · ${h(resultStatus(phase))}</h3><div class="port-io">${technical('測試輸入',phase.input)}${technical('實際輸出',phase.output)}</div></article>`).join('')}${technical('完整併發測試收據',probe)}`:''}</div></section>`;
}
function notesForm() {
  if (!state.event) return '';
  return `<div class="detail-line"><h4>事件處理</h4><form id="note-form"><label class="field"><span>處理狀態</span><select name="status"><option value="OPEN">待處理</option><option value="IN_PROGRESS">處理中</option><option value="RESOLVED">已處理</option></select></label><label class="field"><span>記錄者</span><input name="reviewer" placeholder="填寫名稱" required maxlength="100"></label><label class="field"><span>備註</span><textarea name="note" placeholder="記錄目前處理進度或待補證據" required maxlength="2000"></textarea></label><button class="btn full-button" type="submit">儲存處理紀錄</button></form>${state.notes.map((note) => `<div class="history-item"><strong>${h(({OPEN:'待處理',IN_PROGRESS:'處理中',RESOLVED:'已處理'})[note.status] ?? note.status)} · ${h(note.reviewer)}</strong><p>${h(note.note)}</p></div>`).join('')}</div>`;
}
function uncertainty(event) {
  const value = presentationData(event.uncertainty);
  if (Array.isArray(value)) return value.map((item)=>typeof item==='string'?item:JSON.stringify(item)).join('；');
  return typeof value==='string' ? value : value ? JSON.stringify(value) : '此結果為候選解釋，應依來源影像與支持證據進行判讀。';
}
function inspector() {
  if (state.event) return eventInspector();
  const object = selectedObject();
  if (!object) return `<aside class="inspector">${empty('選取一個對象','從左側資源列或 3D 場景，選取物件與候選事件。','cube')}</aside>`;
  const editable=sceneReviewAllowed(state.snapshot)&&object.read_only!==true&&!(Array.isArray(object.editable_fields)&&object.editable_fields.length===0);
  return `<aside class="inspector"><div class="inspector-head"><div class="eyebrow">SELECTED OBJECT</div><h3>${h(object.label ?? object.object_id)}</h3>${badge(objectLabel(object.kind),'purple')}</div><div class="inspector-body"><div class="detail-grid"><div><span>語意</span><strong>${h(object.semantic ?? '未標註')}</strong></div><div><span>顯示版本</span><strong>${editable?(activeReview() ? `標註 v${previewVersion()}` : '來源基線 v0'):'來源唯讀'}</strong></div></div><div class="detail-line"><h4>來源權限</h4><p>${h(typeof object.authority==='string'?object.authority:JSON.stringify(object.authority ?? '未核准'))}</p></div>${editable?`<p>選取既有場景物件，在人審模式中編輯標註草案，驗證後另存新版本。</p><button class="btn primary full-button" data-mode="review">${icon('review')}開始審查</button>`:'<p>原來源唯讀；校正已綁定，不改動原模型。此處可核對來源權限與技術資料。</p>'}${technical('物件 ID 與來源資料',object)}</div></aside>`;
}
function eventInspector() {
  const event = state.event; const [start,end] = normalizeRange(event.time_range);
  return `<aside class="inspector"><div class="inspector-head"><div class="eyebrow">EVENT EVIDENCE</div><h3>${h(eventLabel(event.kind))}</h3>${badge(evidenceLabel(event.evidence_state,isResearch()),'amber')}${event.support_state?badge(supportLabel(event.support_state),'amber'):''}</div><div class="inspector-body"><div class="detail-grid"><div><span>時間範圍</span><strong>${fmt(start)}–${fmt(end)} s</strong></div><div><span>鏡頭</span><strong>${h(safeList(event.camera_ids).map(cameraName).join('、'))}</strong></div></div><div class="detail-line"><h4>行為摘要</h4><p>${h(presentationData(event.summary ?? event.description ?? eventLabel(event.kind)))}</p></div><div class="detail-line"><h4>判讀限制</h4><p>${h(uncertainty(event))}</p></div>
    ${isResearch() ? `<div class="detail-line"><h4>研究結果審查</h4><p>人工判定另存，保留原始演算法候選。</p><div class="review-toggle">${[['SUPPORT','支持'],['REJECT','否定'],['UNKNOWN','未知'],['MORE_EVIDENCE','需要證據']].map(([value,label])=>`<button class="decision-button ${state.reviewDecision===value?'selected':''}" data-decision="${value}">${label}</button>`).join('')}</div><form id="result-review-form"><label class="field"><span>審查者</span><input name="reviewer" required placeholder="填寫名稱" maxlength="100"></label><label class="field"><span>判定理由</span><textarea name="reason" required maxlength="2000" placeholder="說明支持、衝突或缺少的證據"></textarea></label><button class="btn full-button" type="submit">儲存人工判定</button></form></div>` : ''}${notesForm()}${isResearch() ? technical('來源、候選與診斷資料',event) : ''}</div></aside>`;
}
export function eventMediaFrames(event) {
  const sourceByRef = new Map(safeList(event?.source_frames).map((frame)=>[frame.frame_ref,frame]));
  return safeList(event?.media_refs).map((item) => {
    const ref = typeof item === 'string' ? item : item.media_ref ?? item.frame_ref;
    const source = sourceByRef.get(ref);
    return {
      media_ref:ref,
      camera_id:typeof source?.camera_id === 'string' && source.camera_id ? source.camera_id : null,
      timestamp:Number.isFinite(source?.timestamp) ? source.timestamp : null,
    };
  });
}
function managementDisplay() {
  return `${scopeBar()}<div class="management-detail"><section class="panel"><div class="panel-head"><h2>${state.event ? '來源證據' : '目前範圍的事件'}</h2>${state.event ? `<button class="btn small ghost" data-action="clear-event">返回事件列表</button>` : badge(`${state.events.length} 項`)}</div>${state.event ? `<div class="panel-body"><div class="snapshot-frames">${eventMediaFrames(state.event).map(frameHTML).join('') || empty('此事件沒有可用影像')}</div><p class="status-text">來源影像是候選事件的檢視依據，事件解釋仍需人工確認。</p></div>` : eventRows(state.events.length)}</section>${state.event ? eventInspector() : `<aside class="inspector">${empty('選取事件查看細節','提供必要影像、判讀限制及事件處理紀錄。','event')}</aside>`}</div>${managementPlaceholder()}`;
}
function reviewMode() {
  const object = selectedObject() ?? objects()[0];
  if (!state.selectedObject && object) state.selectedObject = object.object_id;
  return `<div class="notice">${icon('info')}<p>場景編輯另存為 annotation／config 版本。來源資產與已凍結研究結果保留原來的版本綁定。</p></div><div class="review-process"><span class="current">01 選取對象</span>${icon('chevron')}<span>02 編輯草案</span>${icon('chevron')}<span>03 驗證差異</span>${icon('chevron')}<span>04 人工核准並發布</span></div><div class="review-grid"><section class="panel review-preview"><div class="panel-head"><div><h2>場景審查</h2><p>從場景或下方清單選取審查對象</p></div><label class="select-shell"><select id="review-version" aria-label="預覽標註版本">${safeList(state.review?.versions).slice().reverse().map((version)=>`<option value="${version.version}" ${version.version===previewVersion()?'selected':''}>標註 v${version.version}${version.version===sourceVersion(state)?' · 目前版本':' · 歷史預覽'}</option>`).join('')}</select></label></div>${viewport()}<div class="review-list">${objects().map((item)=>`<button class="resource-item ${item.object_id===state.selectedObject?'selected':''}" data-object="${h(item.object_id)}">${icon(objectIcon(item.kind))}<span><strong>${h(item.label ?? item.object_id)}</strong><small>${h(objectLabel(item.kind))}</small></span></button>`).join('')}</div>${state.draft ? draftDifference() : ''}<div class="panel-body"><div class="split-title"><h3>版本與來源</h3><button class="btn small ghost" data-action="export-annotation" ${previewVersion()<1?'disabled':''}>${icon('log')}匯出修改差異 v${previewVersion()}</button></div>${technical('版本紀錄與來源綁定',{current_version:sourceVersion(state),versions:state.review?.versions,history:state.review?.history})}</div></section><aside class="inspector">${object ? reviewEditor(object) : empty('目前沒有可審查物件')}</aside></div>${state.publication ? publicationSummary() : ''}`;
}
function editable(object, field) {
  if (historicalPreview()) return false;
  const fields = safeList(object.editable_fields);
  return fields.includes(field) || (field.startsWith('properties.') && fields.includes('properties'));
}
function reviewEditor(object) {
  const edited = state.draft?.object_id===object.object_id ? state.draft.after : object;
  const intrinsics = edited.properties?.intrinsics ?? edited.properties ?? {};
  const canGeometry = editable(object,'geometry');
  const fields = object.kind === 'CAMERA' && (intrinsics.calibration_kind === 'PINHOLE' || ['fx','fy'].every((key)=>Number.isFinite(intrinsics[key]))) ? ['fx','fy','cx','cy'].filter((key) => editable(object,`properties.${key}`) || editable(object,`properties.intrinsics.${key}`)) : [];
  const noFields = !editable(object,'label') && !editable(object,'semantic') && !canGeometry && !fields.length;
  return `<div class="inspector-head"><div class="eyebrow">ANNOTATION EDITOR</div><h3>${h(object.label ?? object.object_id)}</h3>${badge(objectLabel(object.kind),'purple')}</div><div class="inspector-body"><form id="draft-form"><label class="field"><span>顯示名稱</span><input name="label" value="${h(edited.label)}" ${editable(object,'label')?'':'disabled'} required maxlength="200"></label><label class="field"><span>語意</span><input name="semantic" value="${h(edited.semantic)}" ${editable(object,'semantic')?'':'disabled'} required maxlength="200"></label>${canGeometry ? `<label class="field"><span>幾何範圍 · XYZ 公尺</span><textarea class="mono" name="geometry" rows="7" spellcheck="false">${json(edited.geometry)}</textarea><small class="hint-label">編輯此物件的 type 與 points；驗證器會檢查幾何結構。</small></label>` : ''}${fields.length ? `<div class="form-two">${fields.map((key)=>`<label class="field"><span>${key} · 像素</span><input name="intrinsic_${key}" type="number" step="any" value="${h(intrinsics[key] ?? '')}" required></label>`).join('')}</div>` : ''}${editable(object,'properties') ? `<details class="technical"><summary>進階：物件屬性</summary><label class="field" style="padding:0 10px 10px"><textarea name="properties" class="mono" rows="8" spellcheck="false">${json(edited.properties ?? {})}</textarea></label></details>` : ''}<div class="subtle-rule"></div><label class="field"><span>審查者</span><input name="reviewer" required placeholder="填寫名稱" maxlength="100" value="${h(state.draft?._reviewer ?? state.draft?.reviewer ?? '')}"></label><label class="field"><span>修改理由</span><textarea name="reason" required placeholder="依據哪些來源證據修改？" maxlength="2000">${h(state.draft?._reason ?? state.draft?.reason ?? '')}</textarea></label><button class="btn primary full-button" type="submit" ${noFields?'disabled':''}>${icon('review')}建立審查草案</button></form>${noFields ? `<p class="hint-label">${historicalPreview()?'歷史版本為唯讀預覽。請切回目前版本以編輯新草案。':'此來源未開放可編輯欄位。'}</p>` : ''}<div class="review-note">尚未發布的草案不會改變場景版本。核准後會產生新版本，既有凍結結果保持原樣。</div>${state.draft ? reviewValidationControls() : ''}${technical('物件來源與允許編輯欄位',object)}</div>`;
}
function diffEntries() {
  if (!state.draft) return [];
  const explicit = state.draft.diff ?? state.draft.differences;
  if (Array.isArray(explicit)) return explicit.map((entry)=>({field:entry.field ?? entry.path,before:entry.before ?? entry.old,after:entry.after ?? entry.new}));
  const object = objects().find((item)=>item.object_id===state.draft.object_id) ?? selectedObject() ?? {};
  return Object.entries(state.draft.changes ?? {}).map(([field,after])=>({field,before:state.draft.before?.[field] ?? object[field],after}));
}
const displayValue = (value) => typeof value === 'string' ? value : JSON.stringify(value,null,2);
function draftDifference() {
  return `<div class="panel-body"><div class="split-title"><h3>草案差異</h3><button class="btn small ghost" data-action="toggle-draft-preview">${state.draftPreview?'查看修改前':'預覽草案'}</button></div><table class="diff-table"><thead><tr><th style="width:20%">欄位</th><th>目前版本</th><th>草案</th></tr></thead><tbody>${diffEntries().map((entry)=>`<tr><td>${h(entry.field)}</td><td>${h(displayValue(entry.before))}</td><td>${h(displayValue(entry.after))}</td></tr>`).join('')}</tbody></table></div>`;
}
function validationPassed() {
  return state.validation?.valid === true || state.validation?.passed === true || ['PASS','VALID'].includes(state.validation?.status);
}
function reviewValidationControls() {
  return `<div class="detail-line"><h4>草案驗證與發布</h4><button class="btn full-button" data-action="validate-draft">${icon('check')}驗證此草案</button>${state.validation ? `<div class="validation-banner ${validationPassed()?'':'fail'}">${validationPassed()?'草案驗證通過，可由人工核准發布。':'草案未通過驗證，請查看差異與錯誤。'}</div>${technical('驗證結果',state.validation)}` : ''}${validationPassed() ? `<form id="publish-form"><label class="confirm-row"><input name="confirm" type="checkbox" required><span>我已查看修改前後差異，核准此草案並發布為新的標註版本。</span></label><button class="btn cyan full-button" type="submit">核准並發布新版本</button></form>` : ''}</div>`;
}
function publicationSummary() {
  return `<section class="panel wide-section"><div class="panel-head"><div><h2>新版本已發布</h2><p>目前場景已套用標註 v${sourceVersion(state)}，既有結果仍保留原來版本。</p></div>${badge('發布完成','cyan')}</div><div class="panel-body"><div class="review-lock">使用舊標註版本的凍結結果並未重新計算。請依影響清單決定是否建立新的研究 run。</div>${technical('發布版本與影響清單',state.publication)}</div></section>`;
}
function testMode() {
  const checks = safeList(state.test?.checks);
  return `${scopeBar()}${systemPortsPanel()}<div class="test-grid"><section class="panel"><div class="panel-head"><div><h2>共用測試面板</h2><p>對目前場景與選定範圍執行可重現檢查</p></div>${badge('範圍檢查','purple')}</div><div class="panel-body"><div class="test-options"><div class="test-feature"><h3>場景與標註</h3><p>檢查場景資料、版本綁定與可用能力。</p></div><div class="test-feature"><h3>局部資料查詢</h3><p>檢查鏡頭、時間窗與回傳資料的來源。</p></div></div><button class="btn primary" data-action="run-test">${icon('test')}執行目前範圍檢查</button><p class="status-text">此處執行工作台的資料與接口檢查，結果不代表研究精度或 formal gates 通過。</p></div><div class="test-result">${state.test ? `<div class="notice">${icon('info')}<p>${h(typeof state.test.summary === 'string' ? state.test.summary : JSON.stringify(state.test.summary ?? '檢查完成'))}</p></div>${checks.map((check) => { const pass = check.passed === true || check.valid === true || ['PASS','PASSED'].includes(check.status); return `<div class="check-item ${pass?'':'fail'}">${icon(pass?'check':'info')}<div><strong>${h(check.label ?? check.name ?? check.check ?? '資料檢查')}</strong><p>${h(check.message ?? check.detail ?? (typeof check.details === 'string' ? check.details : JSON.stringify(check.details ?? {})))}</p></div>${badge(check.status ?? (pass?'PASS':'CHECK'))}</div>`; }).join('')}${technical('完整檢查結果',state.test)}` : empty('尚未執行檢查','檢查結果將綁定目前的場景與範圍。','test')}</div></section>
    <section class="panel"><div class="panel-head"><div><h2>獨立評估區</h2><p>凍結研究結果與評估資料分開存取</p></div>${badge('RESEARCH')}</div><div class="panel-body"><div class="notice warning">${icon('info')}<p>此處只讀已認證的 aggregate 評估摘要；完整 GT debug 與實驗執行不在此入口，Agent 權限維持原範圍。</p></div><button class="btn" data-action="load-evaluation">查看已凍結評估</button>${state.evaluation ? `<div class="wide-section">${evaluationDisplay()}</div>` : '<p class="status-text">由你主動開啟後，才讀取此場景可用的評估結果。</p>'}</div></section></div><section class="panel wide-section"><div class="panel-head"><div><h2>工具紀錄</h2><p>追溯目前 session 的工作台操作</p></div><button class="btn small ghost" data-action="load-logs">${icon('log')}載入紀錄</button></div><div class="panel-body">${state.logs ? technical('Log · 請求與操作紀錄（含事件識別碼）',state.logs,true) : '<p class="status-text">紀錄保留在研究视圖；管理介面不提供技術 ID 與原始 log。</p>'}</div></section>`;
}
function evaluationDisplay() {
  const evaluation = state.evaluation;
  return `${evaluation.message || evaluation.status ? `<div class="notice">${icon('info')}<p>${h(evaluation.message ?? evaluation.status)}</p></div>` : ''}${technical('評估內容與來源範圍',evaluation)}`;
}
function workspace() {
  let mode = state.page === 'review' ? 'review' : state.page === 'test' ? 'test' : state.mode;
  if(mode==='review'&&!sceneReviewAllowed(state.snapshot)){mode='display';state.page='workspace';}
  state.mode = mode;
  if(isResearch()&&isBlenderQuery()&&mode==='display')return researchDisplay();
  return `${pageHead('SHARED WORKSPACE',!isResearch()?'檢視事件與來源證據':mode==='review'?'讓每次修改，都有依據。':mode==='test'?'測試、比較與追溯。':isBlenderQuery()?'從預設鏡頭，查到對應畫面。':'把畫面放回空間脈絡。',!isResearch()?'選取事件，查看必要影像、判讀限制與處理紀錄。':mode==='review'?'同一套審查流程，套用至不同場景的區域、門與鏡頭。':mode==='test'?'以當前版本與局部範圍檢查資料，獨立查看評估證據。':isBlenderQuery()?'同步檢視 Blender camera 截圖與來源局部模型，用本機基底演算法檢索 Top-K 畫面。':'選取物件或事件，同步檢視影像、時間與局部空間。')}${workspaceTabs()}${!isResearch() ? managementDisplay() : mode==='review' ? reviewMode() : mode==='test' ? testMode() : researchDisplay()}`;
}
function render() {
  const app = $('#app');
  const priorPage=state.renderedPage;
  const panelKey=`${state.sceneEpoch}:${state.page}:${state.presentationMode}`;
  const preservePanel=state.panel&&state.panelKey===panelKey;
  if(!preservePanel){state.panel?.dispose();state.panel=null;}
  const stage=state.view?.container;
  const preserveMotion=isResearch()&&isBlenderQuery()&&state.page==='workspace'&&state.mode==='display'&&state.motionPanelResult===state.motionResult&&state.motionPanelEpoch===state.motionEpoch&&state.motionPanelScene===state.sceneEpoch;
  if(!preserveMotion){state.motionDispose?.();state.motionDispose=null;}
  const preserveCrossCamera=isResearch()&&isBlenderQuery()&&state.page==='workspace'&&state.mode==='display'&&state.crossCameraPanelResult===state.crossCameraResult&&state.crossCameraPanelEpoch===state.crossCameraEpoch&&state.crossCameraPanelScene===state.sceneEpoch;
  if(!preserveCrossCamera){state.crossCameraDispose?.();state.crossCameraDispose=null;}
  const preservePhysical=isResearch()&&isBlenderQuery()&&state.page==='workspace'&&state.mode==='display'&&state.physicalPanelResult===state.physicalResult&&state.physicalPanelEpoch===state.physicalEpoch&&state.physicalPanelScene===state.sceneEpoch;
  if(!preservePhysical){state.physicalDispose?.();state.physicalDispose=null;}
  const preservePhysicalReview=isResearch()&&isBlenderQuery()&&physicalReviewPanelCanPersist(state,$('#physical-review-host'),physicalReviewPanelKey());
  if(!preservePhysicalReview){state.physicalReviewDispose?.();state.physicalReviewDispose=null;}
  const scroll=priorPage===state.page?$('.main-scroll')?.scrollTop??0:0;
  if (!state.role) { app.innerHTML = gateway(); return; }
  const content=!state.snapshot?'':state.page==='investigation'&&isResearch()?`${pageHead('BOUNDED INVESTIGATION','從線索，逐步查到證據。','有限 typed plans、全部替代候選與實際影片共用本機來源綁定。')}<div data-investigation-panel></div>`:state.page==='presentations'&&isResearch()?`${pageHead('SOURCE MODEL PRESENTATION','讓人物回到場景裡。','局部建築幾何、公開投影與盲區候選使用同一時間軸；來源與推論綁定分別顯示。')}<div class="mode-tabs"><button class="btn ${state.presentationMode==='source'?'primary':''}" data-presentation-mode="source">模型與行走</button><button class="btn ${state.presentationMode==='gallery'?'primary':''}" data-presentation-mode="gallery">歷史圖表與展示库</button></div><div ${state.presentationMode==='source'?'data-presentation-panel':'data-gallery-panel'}></div>`:state.page==='dashboard'?dashboard():workspace();
  const markup = `<div class="shell ${isResearch()?'research-shell':''}">${sidebar()}<main class="main-scroll">${topbar()}${state.error ? `<div class="inline-error" style="margin-top:22px">${h(state.error)}</div>` : ''}${state.snapshot ? content : '<div class="initial-loading" style="height:65vh"><span class="brand-mark">A</span><p>正在載入場景資料…</p></div>'}<footer class="page-footer"><span>AMIDST · SHARED RESEARCH WORKBENCH</span><span>來源可追溯 · 判定可比較 · 版本可回看</span></footer></main>${state.loading?'<div class="loading-bar"></div>':''}</div>`;
  const selectors=['details.source-evidence','[data-frames="dashboard"]','[data-frame-wall-grid]'];
  if(preserveMotion)selectors.push('.motion-reconstruction-panel');
  if(preserveCrossCamera)selectors.push('.cross-camera-panel');
  if(preservePhysical)selectors.push('.physical-cross-camera-panel');
  if(preservePhysicalReview)selectors.push('#physical-review-host');
  if(preservePanel)selectors.push('[data-investigation-panel]','[data-gallery-panel]','[data-presentation-panel]');
  retainElements(app,markup,selectors);
  const newStage=$('[data-scene-stage]');
  if(stage&&newStage)newStage.replaceWith(stage);
  $('.main-scroll').scrollTop=scroll;state.renderedPage=state.page;state.panelKey=panelKey;
  updateTimelineDOM();updateFrameWallDOM();mountScene();
  if(!preserveMotion)mountMotionMedia();
  if(!preserveCrossCamera)mountCrossCameraMedia();
  if(!preservePhysical)mountPhysicalMedia();
  if(!preservePhysicalReview)mountPhysicalReviewPanel();
  if(!preservePanel)mountPanel();
}
function physicalReviewPanelKey() {
  return JSON.stringify([state.sceneEpoch,state.physicalReviewEpoch,state.physicalReviewPending,
    state.physicalReviewResult?.review_sha256,state.physicalReviewResult?.review_state?.revision,
    state.physicalReviewSelected,state.physicalReviewError]);
}
export function physicalReviewPanelCanPersist(target,host,key) {
  return target.page==='workspace'&&target.mode==='display'&&host?.isConnected===true&&
    typeof target.physicalReviewDispose==='function'&&target.physicalReviewPanelKey===key;
}
async function loadPhysicalReview() {
  if(!isResearch()||!isBlenderQuery()||state.snapshot?.capabilities?.physical_review!==true)return;
  const selection=state.frameQuerySelection??{camera_ids:state.cameraIds,start:state.start,end:state.end};
  if(!selection.camera_ids?.length){invalidatePhysicalReview(state);state.physicalReviewError='請先選取至少一個來源鏡頭。';mountPhysicalReviewPanel();state.view?.setPhysicalReview?.(null);return;}
  state.physicalReviewPending=true;mountPhysicalReviewPanel();
  try {
    const committed=await runPhysicalReviewLoad(state,selection,payload=>api('physical_review',payload));
    if(committed){mountPhysicalReviewPanel();mountScene();}
  } catch(error) {
    if(error.name!=='AbortError'){mountPhysicalReviewPanel();state.view?.setPhysicalReview?.(null);}
  }
}
async function selectPhysicalReviewItem(ref) {
  const result=state.physicalReviewResult;
  const selection=physicalReviewSelection(result,ref,activeReconstructionTime(),state.snapshot?.physical_constraints,physicalReviewDisplayOptions(ref));
  if(!selection)return;
  stopPlayback();claimSourceClock();state.physicalReviewSelected=selection.item_ref;
  setVisualMode('3d');
  state.view?.setPhysicalReview?.(selection.scene_plan);
  state.view?.focusPhysicalReview?.(selection.scene_plan);
  mountPhysicalReviewPanel();
  await fetchTimeline(selection.timestamp);
}
function physicalReviewDisplayOptions(ref=state.physicalReviewSelected) {
  const presentation=state.snapshot?.presentation,key=physicalReviewDisplayKey(state.physicalReviewResult,ref,presentation);
  let alignAnnotationTop=key?state.physicalReviewDisplayAlignments[key]:false;
  if(key&&alignAnnotationTop===undefined){try{alignAnnotationTop=typeof localStorage!=='undefined'&&localStorage.getItem(key)==='true';}catch{alignAnnotationTop=false;}}
  return {presentation,alignAnnotationTop:alignAnnotationTop===true};
}
function mountPhysicalReviewPanel() {
  const host=$('#physical-review-host');if(!host||!isResearch())return;
  const key=physicalReviewPanelKey();if(state.physicalReviewPanelKey===key&&state.physicalReviewDispose)return;
  state.physicalReviewDispose?.();state.physicalReviewDispose=null;
  if(state.snapshot?.capabilities?.physical_review!==true){host.innerHTML='';state.physicalReviewPanelKey=key;return;}
  const result=state.physicalReviewResult;
  host.innerHTML=physicalReviewPanelHTML(result,{selectedRef:state.physicalReviewSelected,
    sourceSummary:state.snapshot?.physical_constraints,
    sourcePresentation:state.snapshot?.presentation,alignAnnotationTop:physicalReviewDisplayOptions().alignAnnotationTop,
    pending:state.physicalReviewPending,error:state.physicalReviewError??'',
    decisionsByRef:physicalReviewLocalDecisions(result,state.physicalReviewSelected)});
  state.physicalReviewPanelKey=key;
  const epoch=state.sceneEpoch,reviewEpoch=state.physicalReviewEpoch,sceneId=state.sceneId,sessionRef=state.session?.session_ref;
  const current=()=>host.isConnected&&state.role==='research'&&state.sceneEpoch===epoch&&state.sceneId===sceneId&&state.session?.session_ref===sessionRef&&state.physicalReviewEpoch===reviewEpoch;
  state.physicalReviewDispose=bindPhysicalReviewPanel(host,{current,getResult:()=>state.physicalReviewResult,
    onSelect:ref=>selectPhysicalReviewItem(ref).catch(error=>toast(error.message)),
    onDisplayAlign:enabled=>{
      if(!current())return;
      const key=physicalReviewDisplayKey(result,state.physicalReviewSelected,state.snapshot?.presentation);if(!key)return;
      state.physicalReviewDisplayAlignments[key]=enabled;
      try{if(typeof localStorage!=='undefined'){enabled?localStorage.setItem(key,'true'):localStorage.removeItem(key);}}catch{}
      state.view?.setPhysicalReview?.(physicalReviewScenePlan(result,state.physicalReviewSelected,state.snapshot?.physical_constraints,physicalReviewDisplayOptions()));
    },
    onSave:async payload=>{
      const committed=await runPhysicalReviewSave(state,payload,value=>api('physical_review_decision',value));
      if(committed){mountPhysicalReviewPanel();toast('已儲存核對差異；未確認部分仍未知，尚未重跑。');}
    },
    onExport:async payload=>{
      try{
        const exported=await api('physical_review_delta',{scene_id:sceneId,...payload});
        if(!current())return;
        const blob=new Blob([JSON.stringify(exported.delta,null,2)+'\n'],{type:'application/json'});
        const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=exported.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      }catch(error){if(current())toast(error.message);}
    },onError:error=>{if(current())toast(error.message);}});
}
const motionMediaURL=ref=>`/api/motion_media?${new URLSearchParams({session_ref:state.session?.session_ref??'',scene_id:state.sceneId??'',ref})}`;
function mountMotionMedia() {
  const container=$('.motion-reconstruction-panel');if(!container||!isResearch())return;
  state.motionPanelResult=state.motionResult;state.motionPanelEpoch=state.motionEpoch;state.motionPanelScene=state.sceneEpoch;
  const result=state.motionResult,ticket={sceneEpoch:state.sceneEpoch,sceneId:state.sceneId,sessionRef:state.session?.session_ref,motionEpoch:state.motionEpoch};
  const current=()=>container.isConnected&&motionRequestIsCurrent(state,ticket)&&state.motionResult===result;
  const ownership=bindVideoOwnership(container,'motion',current);
  const media=bindMotionMedia(container,{current:()=>current()&&videoClockMayUpdate(container,'motion'),
    onSourceTime:timestamp=>{if(current()){claimVideoClock('motion',timestamp);updateReconstructionCursors(timestamp);state.view?.setTimestamp(timestamp);fetchTimeline(timestamp);}}});
  state.motionDispose=()=>{ownership();media();};
}
const crossCameraMediaURL=ref=>`/api/cross_camera_media?${new URLSearchParams({session_ref:state.session?.session_ref??'',scene_id:state.sceneId??'',ref})}`;
function mountCrossCameraMedia() {
  const container=$('.cross-camera-panel');if(!container||!isResearch())return;
  state.crossCameraPanelResult=state.crossCameraResult;state.crossCameraPanelEpoch=state.crossCameraEpoch;state.crossCameraPanelScene=state.sceneEpoch;
  const result=state.crossCameraResult,ticket={sceneEpoch:state.sceneEpoch,sceneId:state.sceneId,sessionRef:state.session?.session_ref,crossCameraEpoch:state.crossCameraEpoch};
  const current=()=>container.isConnected&&crossCameraRequestIsCurrent(state,ticket)&&state.crossCameraResult===result;
  const ownership=bindVideoOwnership(container,'association',current);
  const media=bindCrossCameraMedia(container,{getCandidate:()=>crossCameraCurrentCandidate(),current:()=>current()&&videoClockMayUpdate(container,'association'),
    onSourceTime:(timestamp,{fetchImages})=>{if(current()){claimVideoClock('association',timestamp);updateReconstructionCursors(timestamp);state.view?.setTimestamp(timestamp);if(fetchImages)fetchTimeline(timestamp);}}});
  state.crossCameraDispose=()=>{ownership();media();};
  updateCrossCameraCursor(container,activeReconstructionTime(),crossCameraCurrentCandidate());
}
function crossCameraCurrentCandidate() {
  const candidate=selectedCrossCameraCandidate(state.crossCameraResult,state.crossCameraRank);
  return candidate?{...candidate,display_time_range:state.crossCameraResult.selection.time_range}:null;
}
function selectCrossCameraRank(rank) {
  if(!Number.isInteger(rank)||!(rank===0&&state.crossCameraResult?.baseline_candidate)&&!safeList(state.crossCameraResult?.candidates).some(candidate=>candidate.rank===rank))return;
  state.crossCameraRank=rank;
  activateReconstruction('association');
  const container=$('.cross-camera-panel'),candidate=$('[data-cross-camera-candidate]',container);
  if(candidate)candidate.innerHTML=crossCameraCandidateHTML(state.crossCameraResult,rank,{cameraLabel:cameraName});
  updateCrossCameraCursor(container,activeReconstructionTime(),crossCameraCurrentCandidate());
  // Only this overlay changes; preserve the model, camera pose and playing video node.
  state.view?.setTimestamp(activeReconstructionTime());
  const badge=$('.viewport-overlay .cross-camera-badge');if(badge)badge.textContent=(rank===0?'未關聯基線':'跨鏡頭候選 '+rank)+' · 未確認';
}
const physicalMediaURL=ref=>`/api/physical_cross_camera_media?${new URLSearchParams({session_ref:state.session?.session_ref??'',scene_id:state.sceneId??'',ref})}`;
function activeReconstructionTime() {
  return (state.reconstructionClockOwner==='physical'?state.physicalTimestamp:state.reconstructionClockOwner==='association'?state.crossCameraTimestamp:state.reconstructionClockOwner==='motion'?state.motionTimestamp:null)??state.timestamp;
}
function activeReconstructionPlan() {
  return state.reconstructionMode==='physical'?physicalScenePlan(state.physicalResult,state.physicalChoice):crossCameraScenePlan(state.crossCameraResult,state.crossCameraRank);
}
function activateReconstruction(mode) {
  if(state.reconstructionMode!==mode){claimSourceClock();state.reconstructionMode=mode;}
  state.view?.setCrossCamera(activeReconstructionPlan());
  state.view?.setPhysicalGeometry?.(mode==='physical'?physicalGeometryPlan(state.physicalResult):null);
}
function claimSourceClock() {
  state.reconstructionClockOwner='source';state.crossCameraTimestamp=null;state.physicalTimestamp=null;state.motionTimestamp=null;
  $$('[data-cross-camera-video]').forEach(video=>video.pause());
  $$('[data-motion-video]').forEach(video=>video.pause());
}
function claimVideoClock(mode,timestamp) {
  stopPlayback();const changed=mode!=='motion'&&state.reconstructionMode!==mode;
  state.reconstructionClockOwner=mode;if(mode!=='motion')state.reconstructionMode=mode;
  state.crossCameraTimestamp=mode==='association'?timestamp:null;state.physicalTimestamp=mode==='physical'?timestamp:null;
  state.motionTimestamp=mode==='motion'?timestamp:null;
  for(const video of $$('[data-cross-camera-video]'))if((('physicalVideo' in video.dataset)?'physical':'association')!==mode)video.pause();
  if(mode!=='motion')$$('[data-motion-video]').forEach(video=>video.pause());
  if(changed){state.view?.setCrossCamera(activeReconstructionPlan());state.view?.setPhysicalGeometry?.(mode==='physical'?physicalGeometryPlan(state.physicalResult):null);}
}
function videoClockMayUpdate(container,mode) {
  const video=container.querySelector(mode==='motion'?'[data-motion-video]':'[data-cross-camera-video]');
  return state.reconstructionClockOwner===mode||!video?.paused;
}
function bindVideoOwnership(container,mode,current) {
  const handlers=[];
  for(const video of container.querySelectorAll(mode==='motion'?'[data-motion-video]':'[data-cross-camera-video]')){
    const takeControl=()=>{if(current()&&video.isConnected){const start=Number(video.dataset.timeStart??video.dataset.motionStart),end=Number(video.dataset.timeEnd??video.dataset.motionEnd);claimVideoClock(mode,Math.min(end,start+video.currentTime));}};
    video.addEventListener('play',takeControl);video.addEventListener('seeking',takeControl);
    handlers.push(()=>{video.removeEventListener('play',takeControl);video.removeEventListener('seeking',takeControl);});
  }
  return ()=>handlers.forEach(dispose=>dispose());
}
function physicalCurrentCandidate() {
  const candidate=selectedPhysicalCandidate(state.physicalResult,state.physicalChoice);
  return candidate?{...candidate,display_time_range:state.physicalResult.selection.time_range}:null;
}
function updateReconstructionCursors(timestamp) {
  updateCrossCameraCursor($('.cross-camera-panel'),timestamp,crossCameraCurrentCandidate());
  updateCrossCameraCursor($('.physical-cross-camera-panel'),timestamp,physicalCurrentCandidate());updateFrameWallCursor(timestamp);
}
function mountPhysicalMedia() {
  const container=$('.physical-cross-camera-panel');if(!container||!isResearch())return;
  state.physicalPanelResult=state.physicalResult;state.physicalPanelEpoch=state.physicalEpoch;state.physicalPanelScene=state.sceneEpoch;
  const result=state.physicalResult,ticket={sceneEpoch:state.sceneEpoch,sceneId:state.sceneId,sessionRef:state.session?.session_ref,physicalEpoch:state.physicalEpoch};
  const current=()=>container.isConnected&&physicalRequestIsCurrent(state,ticket)&&state.physicalResult===result;
  const ownership=bindVideoOwnership(container,'physical',current);
  const media=bindCrossCameraMedia(container,{getCandidate:()=>physicalCurrentCandidate(),current:()=>current()&&videoClockMayUpdate(container,'physical'),
    onSourceTime:(timestamp,{fetchImages})=>{if(current()){claimVideoClock('physical',timestamp);updateReconstructionCursors(timestamp);state.view?.setTimestamp(timestamp);if(fetchImages)fetchTimeline(timestamp);}}});
  state.physicalDispose=()=>{ownership();media();};updateReconstructionCursors(activeReconstructionTime());
}
function selectPhysicalChoice(choice) {
  if(choice!=='baseline'&&!/^(accepted|rejected):[1-5]$/.test(choice))return;
  const match=/^(accepted|rejected):([1-5])$/.exec(choice);
  if(choice==='baseline'?!state.physicalResult?.baseline_candidate:!safeList(match[1]==='accepted'?state.physicalResult?.candidates:state.physicalResult?.rejected_candidates)[Number(match[2])-1])return;
  state.physicalChoice=choice;activateReconstruction('physical');
  const container=$('.physical-cross-camera-panel'),candidate=$('[data-physical-candidate]',container);
  if(candidate)candidate.innerHTML=physicalCandidateHTML(state.physicalResult,choice,{cameraLabel:cameraName});
  updateReconstructionCursors(activeReconstructionTime());state.view?.setTimestamp(activeReconstructionTime());
  const badge=$('.cross-camera-badge');if(badge)badge.textContent='物理篩選 · '+(selectedPhysicalCandidate(state.physicalResult,choice)?.physical?.verdict??'UNKNOWN');
}
async function mountPanel(){
  if(!isResearch())return;
  const container=$('[data-presentation-panel],[data-gallery-panel],[data-investigation-panel]');if(!container)return;
  const token=state.session.session_ref,sceneId=state.sceneId,epoch=state.sceneEpoch;
  const current=()=>container.isConnected&&isResearch()&&state.session?.session_ref===token&&state.sceneEpoch===epoch;
  const call=async(action,payload={})=>{if(!current())throw Error('SESSION_CHANGED');const result=await api(action,{...payload,session_ref:token});if(!current())throw Error('SESSION_CHANGED');return result;};
  const binaryURL=(route,ref)=>`/api/${route}?${new URLSearchParams({session_ref:token,scene_id:sceneId,ref})}`;
  try{
    if(container.hasAttribute('data-investigation-panel')){
      const {InvestigationPanel}=await import('./investigation.mjs');if(!current())return;
      state.panel=new InvestigationPanel(container,{call:(action,payload)=>call('product_'+action,{...payload,scene_id:sceneId}),snapshot:state.snapshot,
        mediaURL:ref=>binaryURL('product_media',ref),videoURL:ref=>binaryURL('product_video',ref),exportReport:async(ref,isCurrent=()=>true)=>{
          const response=await fetch('/api/product_export_report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_ref:token,scene_id:sceneId,report_ref:ref})});
          if(!response.ok)throw Error('REPORT_EXPORT_DENIED');const html=await response.blob();if(!current()||!isCurrent())throw Error('SESSION_CHANGED');
          const url=URL.createObjectURL(html),link=document.createElement('a');link.href=url;link.download='amidst-investigation.html';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        }});
    }else if(container.hasAttribute('data-gallery-panel')){
      const {GalleryPanel}=await import('./gallery.mjs');if(!current())return;
      state.panel=new GalleryPanel(container,{call,mediaURL:ref=>`/api/gallery_media?${new URLSearchParams({session_ref:token,ref})}`});
    }else{
      const {PresentationPanel}=await import('./presentation.mjs');if(!current())return;
      state.panel=new PresentationPanel(container,{call,mediaURL:ref=>`/api/presentation_media?${new URLSearchParams({session_ref:token,ref})}`});
    }
  }catch(error){if(current())container.innerHTML=`<div class="notice warning">${h(error.message)}</div>`;}
}
async function mountScene() {
  const container = $('[data-scene-stage]');
  if (!container || !state.snapshot || !isResearch()) return;
  const epoch = state.sceneEpoch;
  const onReviewSelect=ref=>{
    if(epoch!==state.sceneEpoch||!state.physicalReviewResult?.items.some(item=>item.item_ref===ref))return;
    selectPhysicalReviewItem(ref).catch(error=>{if(epoch===state.sceneEpoch)toast(error.message);});
  };
  const options=()=>({snapshot:state.snapshot,objects:renderedObjects(),event:activeReview()?null:state.event,
    presentation:isBlenderQuery()?state.snapshot.presentation:null,crossCamera:isBlenderQuery()?activeReconstructionPlan():null,physicalGeometry:isBlenderQuery()&&state.reconstructionMode==='physical'?physicalGeometryPlan(state.physicalResult):null,
    physicalReview:isBlenderQuery()&&state.physicalReviewResult?physicalReviewScenePlan(state.physicalReviewResult,state.physicalReviewSelected,state.snapshot?.physical_constraints,physicalReviewDisplayOptions()):null,
    observations:activeReview()?[]:state.observations,graph:activeReview()?null:guidanceGraph(state.guide?.agent_input,state.snapshot,{showRelations:state.showGraphLabels}),
    selectedId:state.selectedObject,pose:state.viewPose,onReviewSelect,onSelect:(id)=>selectObject(id)});
  if(state.view){
    if(!state.queryPending&&!state.eventPending)state.view.setData(options());
    state.view.resize();state.view.setTimestamp(activeReconstructionTime());return;
  }
  try {
    const {SceneView} = await import('./scene.mjs');
    if (epoch !== state.sceneEpoch || !container.isConnected) return;
    if(state.view)return;
    state.view = new SceneView(container,options());
    state.view.setTimestamp(activeReconstructionTime());
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<div class="viewport-fallback">${icon('cube')}<p>3D 顯示暫時無法載入。<br>你仍可由資源清單檢視物件與進行人審。</p><small>${h(error.message)}</small></div>`;
  }
}
function selectObject(id) {
  invalidateEventState(state);state.timelineEpoch+=1;
  Object.assign(state,{selectedObject:id,selectedEvent:null,event:null,notes:[],draft:null,validation:null,draftPreview:false}); render();
}
function updateFrameGrid(node,frames) {
  if(!frames.length){if(!node.querySelector('.frame-empty'))node.innerHTML=currentFrames();return;}
  const prior=new Map([...node.querySelectorAll('[data-frame-camera]')].map(card=>[card.dataset.frameCamera,card]));
  const active=new Set();
  for(const frame of frames){
    const key=String(frame.camera_id??''),ref=frame.media_ref??frame.ref??'';active.add(key);
    let card=prior.get(key);
    if(card&&card.dataset.frameRef===ref){
      const label=card.querySelector('.frame-caption span');if(label)label.textContent=frameTimeLabel(frame.timestamp);continue;
    }
    if(card&&ref&&card.querySelector('img')){
      const image=card.querySelector('img');image.src=mediaURL(ref);image.alt=cameraName(frame.camera_id)+'，'+frameTimeLabel(frame.timestamp)+' 的來源影像';
      card.querySelector('[data-image]').dataset.image=ref;card.dataset.frameRef=ref;
      card.querySelector('.frame-caption span').textContent=frameTimeLabel(frame.timestamp);
      const kind=card.querySelector('.frame-kind');if(kind)kind.textContent=frameSourceLabel(frame,state.snapshot);continue;
    }
    const template=document.createElement('template');template.innerHTML=frameHTML(frame);
    const replacement=template.content.firstElementChild;
    if(card)card.replaceWith(replacement);else node.append(replacement);
  }
  for(const [key,card] of prior)if(!active.has(key))card.remove();
  for(const placeholder of node.children)if(!placeholder.hasAttribute('data-frame-camera'))placeholder.remove();
}
function updateTimelineDOM() {
  $$('[data-frames]').forEach(node=>updateFrameGrid(node,state.frames.slice(0,node.dataset.frames==='dashboard'?3:4)));
  const range = $('#timeline-range'); if (range) range.value = state.timestamp;
  const label = $('[data-current-time]'); if (label) label.textContent = time(state.timestamp);
  const lanes = $('[data-time-lanes]'); if (lanes) lanes.innerHTML = timeLanes();
  state.view?.setTimestamp(activeReconstructionTime());
  updateReconstructionCursors(activeReconstructionTime());
}
async function togglePlayback() {
  if (state.playTimer) { stopPlayback(); return; }
  claimSourceClock();
  const epoch = state.sceneEpoch; const [start,end] = normalizeRange(state.snapshot.time_range);
  if (state.timestamp >= end) state.timestamp = start;
  const step = async () => {
    if (epoch !== state.sceneEpoch || !state.playTimer) return;
    const next = Math.min(end,state.timestamp+.4);
    await fetchTimeline(next);
    if (epoch !== state.sceneEpoch || !state.playTimer) return;
    if (next>=end) stopPlayback(); else state.playTimer = setTimeout(step,400);
  };
  state.playTimer = setTimeout(step,0);
  const button = $('[data-action="play"]'); if (button) { button.innerHTML=icon('pause'); button.setAttribute('aria-label','暫停回放'); }
}
function formValues(form) { return resolveTimeSegment(Object.fromEntries(new FormData(form).entries()),state.snapshot); }
export function changesForObject(object, values) {
  const changes = {};
  for (const field of ['label','semantic']) if (field in values && values[field] !== String(object[field] ?? '')) changes[field] = values[field].trim();
  if ('geometry' in values) {
    let parsed;
    try { parsed = JSON.parse(values.geometry); } catch { throw new Error('幾何資料必須是有效的 JSON。'); }
    if (!parsed || !['polygon','line','point'].includes(parsed.type) || !Array.isArray(parsed.points)) throw new Error('幾何資料必須包含 type 與 points。');
    if (!parsed.points.every((point)=>Array.isArray(point) && point.length===3 && point.every(Number.isFinite))) throw new Error('每個幾何座標都必須包含三個有效數字 [x, y, z]。');
    if (JSON.stringify(parsed)!==JSON.stringify(object.geometry)) changes.geometry=parsed;
  }
  let props = structuredClone(object.properties ?? {});
  if ('properties' in values) {
    try { props=JSON.parse(values.properties); } catch { throw new Error('物件屬性必須是有效的 JSON。'); }
    if(!props || typeof props!=='object' || Array.isArray(props))throw new Error('物件屬性必須是 JSON 物件。');
  }
  let changedProps=JSON.stringify(props)!==JSON.stringify(object.properties ?? {});
  for (const key of ['fx','fy','cx','cy']) if (`intrinsic_${key}` in values) {
    const numeric = Number(values[`intrinsic_${key}`]);
    if (!Number.isFinite(numeric)) throw new Error(`${key} 必須是有效數字。`);
    const target = props.intrinsics ?? props;
    if (numeric !== target[key]) { target[key]=numeric; changedProps=true; }
  }
  if (changedProps) changes.properties=props;
  return changes;
}
async function handleSubmit(event) {
  const form = event.target;
  if (!['scope-form','guidance-form','frame-query-form','draft-form','publish-form','note-form','result-review-form'].includes(form.id)) return;
  event.preventDefault(); const values=formValues(form); const button=$('button[type="submit"]',form);
  if (button) button.disabled=true;
  const epoch=state.sceneEpoch;
  const eventTicket={sceneEpoch:state.sceneEpoch,eventEpoch:state.eventEpoch,eventRef:state.selectedEvent};
  try {
    if (form.id==='scope-form') {
      const start=Number(values.start),end=Number(values.end);
      if (!Number.isFinite(start)||!Number.isFinite(end)||end<start) throw new Error('結束時間必須大於或等於起始時間。');
      Object.assign(state,{cameraId:values.camera_id,start,end,error:null}); stopPlayback(); await queryScope();
    } else if (form.id==='frame-query-form') {
      if(!isResearch())throw Error('此操作僅供研究工作台。');
      values.camera_ids=new FormData(form).getAll('camera_ids');
      const selection=frameQuerySelection(values,state.snapshot);
      const result=$('.baseline-query-result');if(result)result.textContent='正在檢索本場景的指定範圍…';
      if(button)button.textContent='檢索中…';
      const committed=await runFrameQuery(state,selection,payload=>api('frame_query',payload));
      if(committed)render();
    } else if (form.id==='guidance-form') {
      const selection=guidanceSelection(values,state.presets);
      state.guideSelection=selection;const ticket={sceneEpoch:state.sceneEpoch,queryEpoch:state.queryEpoch,guideEpoch:++state.guideEpoch};
      const result=await api('navigation_guide',{scene_id:state.sceneId,...selection});
      if(!requestIsCurrent(state,ticket))return;state.guide=result;render();
    } else if (form.id==='draft-form') {
      const object=selectedObject(); const changes=changesForObject(object,values);
      if (!Object.keys(changes).length) throw new Error('請先修改至少一個欄位，再建立草案。');
      const result=await api('draft',{scene_id:state.sceneId,object_id:object.object_id,changes,base_version:sourceVersion(state),reviewer:values.reviewer.trim(),reason:values.reason.trim()});
      if(epoch!==state.sceneEpoch)return;
      state.draft={...result.draft,_reviewer:values.reviewer.trim(),_reason:values.reason.trim()}; state.validation=null; state.publication=null; state.draftPreview=true; render(); toast('草案已建立，請檢視差異並驗證。');
    } else if (form.id==='publish-form') {
      if (!values.confirm || !validationPassed()) throw new Error('請先通過驗證，並確認已核對草案差異。');
      const result=await api('publish',{draft_id:state.draft.draft_id,expected_version:sourceVersion(state),reviewer:state.draft._reviewer ?? state.draft.reviewer,reason:state.draft._reason ?? state.draft.reason});
      if(epoch!==state.sceneEpoch)return;
      state.publication=result.publication; state.review=result.review_state; state.previewVersion=null; state.draft=null; state.validation=null; state.draftPreview=false; invalidateVersionResults(state); render(); toast(`標註版本 v${sourceVersion(state)} 已發布。`);
    } else if(form.id==='note-form') {
      const result=await api('note',{scene_id:state.sceneId,event_ref:eventTicket.eventRef,status:values.status,note:values.note.trim(),reviewer:values.reviewer.trim()});
      if(!eventRequestIsCurrent(state,eventTicket))return;
      state.notes.push(result.note); render(); toast('事件處理紀錄已儲存。');
    } else if(form.id==='result-review-form') {
      await api('result_review',{scene_id:state.sceneId,event_ref:eventTicket.eventRef,decision:state.reviewDecision,reason:values.reason.trim(),reviewer:values.reviewer.trim()});
      if(!eventRequestIsCurrent(state,eventTicket))return;
      form.reset(); toast('人工判定已另存，原始候選結果保留。');
    }
  } catch(error) { if(error.name!=='AbortError' && epoch===state.sceneEpoch && (!['note-form','result-review-form'].includes(form.id) || eventRequestIsCurrent(state,eventTicket)))toast(error.message); }
  finally { if(button?.isConnected&&!(form.id==='frame-query-form'&&state.frameQueryPending)){button.disabled=false;if(form.id==='frame-query-form')button.textContent='檢索 Top-K 畫面';} }
}
async function handleClick(event) {
  const button=event.target.closest('button'); if(!button || button.disabled)return;
  if(button.dataset.visualMode){setVisualMode(button.dataset.visualMode);return;}
  if(button.dataset.wallSlots){if(!isResearch()||!isBlenderQuery())return;const count=Number(button.dataset.wallSlots);if(![8,12,16].includes(count)||count===state.wallSlotCount)return;state.wallSlotCount=count;$$('[data-wall-slots]').forEach(node=>{const active=Number(node.dataset.wallSlots)===count;node.classList.toggle('cyan',active);node.setAttribute('aria-pressed',String(active));});await fetchFrameWall();return;}
  if(button.dataset.presentationMode){if(!isResearch())return;state.presentationMode=button.dataset.presentationMode;render();return;}
  if(button.dataset.role) { await selectRole(button.dataset.role); return; }
  if(button.dataset.page) {
    if(button.dataset.page==='review'&&!sceneReviewAllowed(state.snapshot))return;
    stopPlayback();state.eventEpoch+=1; state.page=button.dataset.page;
    if(state.page==='workspace')state.mode='display';
    if(state.page==='review')state.mode='review';
    if(state.page==='test')state.mode='test';
    state.error=null; render(); $('.main-scroll')?.scrollTo(0,0); return;
  }
  if(button.dataset.mode) {
    if(!isResearch())return;
    if(button.dataset.mode==='review'&&!sceneReviewAllowed(state.snapshot))return;
    stopPlayback();state.eventEpoch+=1; state.mode=button.dataset.mode; state.page=state.mode==='display'?'workspace':state.mode; render(); return;
  }
  if(button.dataset.object) { selectObject(button.dataset.object); return; }
  if(button.dataset.event) { await selectEvent(button.dataset.event); return; }
  if(button.dataset.resourceTab) { state.resourceTab=button.dataset.resourceTab;render();return; }
  if(button.dataset.decision) { state.reviewDecision=button.dataset.decision;$$('[data-decision]').forEach((node)=>node.classList.toggle('selected',node.dataset.decision===state.reviewDecision));return; }
  if(button.dataset.toggleCamera) {
    stopPlayback();const id=button.dataset.toggleCamera;
    state.cameraIds=state.cameraIds.includes(id)?state.cameraIds.filter((item)=>item!==id):[...state.cameraIds,id].slice(-4);
    if(isBlenderQuery()){const form=$('#frame-query-form');if(form){$$('[name="camera_ids"]',form).forEach(input=>{input.checked=state.cameraIds.includes(input.value);});invalidateFrameQueryUI(form);}else invalidateFrameQuery(state,{...state.frameQuerySelection,camera_ids:[...state.cameraIds]});}
    render();if(!state.cameraIds.length){state.frames=[];updateTimelineDOM();}await Promise.allSettled([state.cameraIds.length?fetchTimeline(state.timestamp):Promise.resolve(),isBlenderQuery()?fetchFrameWall():Promise.resolve(),isBlenderQuery()?loadPhysicalReview():Promise.resolve()]);return;
  }
  if(button.dataset.image) {
    const dialog=document.createElement('dialog');dialog.className='media-dialog';dialog.innerHTML=`<img src="${h(mediaURL(button.dataset.image))}" alt="放大的來源影像"><button class="btn" autofocus>關閉影像</button>`;
    dialog.querySelector('button').addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();return;
  }
  const action=button.dataset.action;if(!action)return;
  if(action==='switch-role'){clearContext();state.role=null;state.session=null;state.loading=false;render();return;}
  if(action==='reset-view'){state.view?.reset();return;}
  if(action==='toggle-graph-labels'){state.showGraphLabels=!state.showGraphLabels;render();return;}
  if(action==='play'){await togglePlayback();return;}
  if(action==='clear-event'){invalidateEventState(state);state.timelineEpoch+=1;render();return;}
  if(action==='toggle-draft-preview'&&isResearch()){state.draftPreview=!state.draftPreview;render();return;}
  if(!isResearch())return;
  button.disabled=true; const epoch=state.sceneEpoch;const queryEpoch=state.queryEpoch;
  try {
    if(action==='validate-draft') {
      const result=await api('validate',{draft_id:state.draft.draft_id});
      if(epoch!==state.sceneEpoch)return;state.validation=result.validation;render();
    }else if(action==='run-test') {
      const result=await api('test',{scene_id:state.sceneId,camera_id:state.cameraId,start:state.start,end:state.end});
      if(epoch!==state.sceneEpoch||queryEpoch!==state.queryEpoch)return;state.test=result;render();toast('目前範圍檢查已完成。');
    }else if(action==='load-evaluation') {
      const result=await api('evaluation',{scene_id:state.sceneId});if(epoch!==state.sceneEpoch)return;state.evaluation=result.evaluation;render();
    }else if(action==='export-annotation') {
      const result=await api('export_delta',{scene_id:state.sceneId,version:previewVersion()});
      if(epoch!==state.sceneEpoch)return;
      const blob=new Blob([JSON.stringify(result.delta,null,2)],{type:'application/json'});
      const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=result.filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('已匯出修改差異文件及來源綁定。');
    }else if(action==='agent-decision') {
      const guide=state.guide,ticket={sceneEpoch:state.sceneEpoch,queryEpoch:state.queryEpoch,guideEpoch:state.guideEpoch};
      const result=await api('agent_decision',{scene_id:state.sceneId,guide_ref:guide.guide_ref});
      if(!requestIsCurrent(state,ticket)||state.guide!==guide)return;state.guide={...guide,...result};render();
    }else if(action==='system-ports') {
      const result=await api('system_ports',{scene_id:state.sceneId});
      if(epoch!==state.sceneEpoch)return;state.portTest=result;render();toast(`系統端口測試 ${result.status}。`);
    }else if(action==='motion-reconstruct') {
      const form=$('#frame-query-form'),values=formValues(form);values.camera_ids=new FormData(form).getAll('camera_ids');
      const selection=motionSelection(values,state.snapshot);
      state.motionDispose?.();state.motionDispose=null;
      const panel=$('.motion-reconstruction-panel .panel-body');if(panel)panel.textContent='正在還原選定鏡頭與來源時間…';
      const committed=await runMotionReconstruction(state,selection,payload=>api('motion_reconstruction',payload));
      if(committed)render();
    }else if(action==='cross-camera-reconstruct') {
      const form=$('#frame-query-form'),values=formValues(form);values.camera_ids=new FormData(form).getAll('camera_ids');
      const selection=crossCameraSelection(values,state.snapshot);
      state.crossCameraDispose?.();state.crossCameraDispose=null;
      state.view?.setCrossCamera(null);
      const panel=$('.cross-camera-panel .panel-body');if(panel)panel.textContent='正在整理選定範圍內的多解候選…';
      const badge=$('.cross-camera-badge');if(badge)badge.textContent='跨鏡頭候選更新中…';
      const committed=await runCrossCameraReconstruction(state,selection,payload=>api('cross_camera_reconstruction',payload));
      if(committed){activateReconstruction('association');render();}
    }else if(action==='physical-reconstruct') {
      const form=$('#frame-query-form'),values=formValues(form);values.camera_ids=new FormData(form).getAll('camera_ids');
      const selection=crossCameraSelection(values,state.snapshot);
      state.physicalDispose?.();state.physicalDispose=null;
      const panel=$('.physical-cross-camera-panel .panel-body');if(panel)panel.textContent='正在檢查來源門／走廊／碰撞限制與未知項目…';
      const committed=await runPhysicalReconstruction(state,selection,payload=>api('physical_cross_camera_reconstruction',payload));
      if(committed){activateReconstruction('physical');render();}
    }else if(action==='storage-probe') {
      state.storageStage=$('#storage-probe-stage').value;
      const result=await api('storage_probe',{scene_id:state.sceneId,stage:state.storageStage});
      if(epoch!==state.sceneEpoch)return;state.storageProbe=result;render();toast(`儲存層測試 ${resultStatus(result)}。`);
    }else if(action==='load-logs') {
      const result=await api('logs',{scene_id:state.sceneId});if(epoch!==state.sceneEpoch)return;state.logs=result.items;render();
    }
  }catch(error){if(error.name!=='AbortError'&&epoch===state.sceneEpoch&&(action!=='run-test'||queryEpoch===state.queryEpoch)){if(['motion-reconstruct','cross-camera-reconstruct','physical-reconstruct'].includes(action))render();toast(error.message);}}finally{if(button.isConnected&&!(action==='motion-reconstruct'&&state.motionPending)&&!(action==='cross-camera-reconstruct'&&state.crossCameraPending)&&!(action==='physical-reconstruct'&&state.physicalPending))button.disabled=false;}
}
async function bootstrap() {
  document.addEventListener('click',handleClick);document.addEventListener('submit',handleSubmit);
  document.addEventListener('change',async(event)=>{
    if(event.target.hasAttribute?.('data-workspace-time-segment')){const form=$('#frame-query-form');applyTimeSegment(form,event.target.value);if(form)invalidateFrameQueryUI(form);await Promise.allSettled([fetchFrameWall(),loadPhysicalReview()]);return;}
    const segmentForm=event.target.closest?.('form');if(event.target.hasAttribute?.('data-time-segment'))applyTimeSegment(segmentForm,event.target.value);
    const guideForm=event.target.closest?.('#guidance-form');if(guideForm)invalidateGuideUI(guideForm);
    const frameForm=event.target.closest?.('#frame-query-form');if(frameForm){invalidateFrameQueryUI(frameForm);if(event.target.name==='camera_ids'){state.cameraIds=[...state.frameQuerySelection.camera_ids];$$('[data-toggle-camera]').forEach(node=>{const active=state.cameraIds.includes(node.dataset.toggleCamera);node.classList.toggle('selected',active);node.setAttribute('aria-pressed',String(active));});if(!state.cameraIds.length){state.frames=[];updateTimelineDOM();}}if(['time_segment','camera_ids'].includes(event.target.name))await Promise.allSettled([fetchFrameWall(),loadPhysicalReview(),event.target.name==='camera_ids'?fetchTimeline(state.timestamp):Promise.resolve()]);}
    if(event.target.hasAttribute?.('data-physical-choice'))selectPhysicalChoice(event.target.value);
    if(event.target.hasAttribute?.('data-cross-camera-rank'))selectCrossCameraRank(Number(event.target.value));
    if(event.target.id==='scene-select')await loadScene(event.target.value);
    if(event.target.id==='review-version'){state.previewVersion=Number(event.target.value);state.draft=null;state.validation=null;state.selectedObject=objects()[0]?.object_id??null;render();}
    if(event.target.id==='timeline-range'){stopPlayback();claimSourceClock();await fetchTimeline(Number(event.target.value));}
  });
  document.addEventListener('input',(event)=>{
    const guideForm=event.target.closest?.('#guidance-form');if(guideForm)invalidateGuideUI(guideForm);
    const frameForm=event.target.closest?.('#frame-query-form');if(frameForm)invalidateFrameQueryUI(frameForm);
    if(event.target.id==='timeline-range'){stopPlayback();claimSourceClock();updateFrameWallCursor(Number(event.target.value));const label=$('[data-current-time]');if(label)label.textContent=time(event.target.value);state.view?.setTimestamp(Number(event.target.value));updateReconstructionCursors(Number(event.target.value));}
  });
  try {
    const response=await fetch('/api/bootstrap');if(!response.ok)throw new Error('工作台初始化失敗。');
    state.bootstrap=await response.json();render();
  }catch(error){state.error=error.message;render();}
}
function invalidateGuideUI(form) {
  updateGuidanceInputs(state,formValues(form));
  const result=$('.guidance-result');if(result)result.textContent='選取已變更，請重新整理目標指引。';
  // Update only the graph overlay. Preserve focused input nodes and the last complete 3D frame.
  if(state.view&&!state.queryPending&&!state.eventPending&&$('[data-scene-stage]'))mountScene();
}
function invalidateFrameQueryUI(form) {
  const values=formValues(form);values.camera_ids=new FormData(form).getAll('camera_ids');
  invalidateFrameQuery(state,values);
  const reviewScope=state.physicalReviewSelection;
  if(reviewScope&&(JSON.stringify([...reviewScope.camera_ids].sort())!==JSON.stringify([...values.camera_ids].sort())||reviewScope.start!==Number(values.start)||reviewScope.end!==Number(values.end))){
    state.physicalReviewDispose?.();state.physicalReviewDispose=null;invalidatePhysicalReview(state);state.physicalReviewPanelKey=null;
    state.view?.setPhysicalReview?.(null);mountPhysicalReviewPanel();
  }
  const wallScope=state.frameWallSelection;
  if(wallScope&&(JSON.stringify(wallScope.camera_ids)!==JSON.stringify(values.camera_ids)||wallScope.start!==Number(values.start)||wallScope.end!==Number(values.end))){state.frameWallEpoch++;state.frameWallPending=true;state.frameWallError=null;updateFrameWallDOM();}
  state.motionDispose?.();state.motionDispose=null;invalidateMotion(state);
  state.crossCameraDispose?.();state.crossCameraDispose=null;invalidateCrossCamera(state);
  state.physicalDispose?.();state.physicalDispose=null;invalidatePhysicalCrossCamera(state);state.reconstructionMode='association';state.reconstructionClockOwner='source';
  state.view?.setCrossCamera(null);
  const crossCamera=$('.cross-camera-panel .panel-body');if(crossCamera)crossCamera.textContent='鏡頭、時間或 Top-K 已變更，請重新整理跨鏡頭多解。';
  const crossCameraBadge=$('.cross-camera-badge');if(crossCameraBadge)crossCameraBadge.textContent='跨鏡頭選取已變更 · 待重跑';
  const crossCameraButton=$('[data-action="cross-camera-reconstruct"]',form);if(crossCameraButton)crossCameraButton.disabled=false;
  state.view?.setPhysicalGeometry?.(null);
  const physical=$('.physical-cross-camera-panel .panel-body');if(physical)physical.textContent='鏡頭、時間或 Top-K 已變更，請重新檢查來源物理限制。';
  const physicalButton=$('[data-action="physical-reconstruct"]',form);if(physicalButton)physicalButton.disabled=state.snapshot?.capabilities?.physical_cross_camera_reconstruction!==true;
  const motion=$('.motion-reconstruction-panel .panel-body');if(motion)motion.textContent='鏡頭或查詢選取已變更，請重新產生物理曲線與還原。';
  const motionButton=$('[data-action="motion-reconstruct"]',form);if(motionButton)motionButton.disabled=false;
  const result=$('.baseline-query-result');if(result)result.textContent='選取已變更，請重新檢索 Top-K 畫面。';
  const button=$('button[type="submit"]',form);if(button){button.disabled=false;button.textContent='檢索 Top-K 畫面';}
}
if(typeof document!=='undefined')bootstrap();

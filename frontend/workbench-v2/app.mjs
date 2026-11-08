// Q composition root. Review code has a separate dynamic boundary and receives
// immutable state/read-only subscriptions, never the API object or query dispatch.
import {createStore,initialState} from './store.mjs';
import {mountQShell,loadRailPref} from './shell-view.mjs';
import {createQApi,FIXTURE_ORIGIN} from './q-api.mjs';
import {responseKind,contentHash} from './q-validate.mjs';
import {advanceUs,stepUs,formatSource,displayClock,virtualTime,DECLARED_TAG} from './q-time.mjs';
import {setStampClock} from './cam-stamp.mjs';
import {createSpeedMeter,formatSpeedNote} from './speed-meter.mjs';
import {createPlayback,canPlay,playbackDelta,afterTick} from './q-playback.mjs';
import {Q_LEGEND} from './q-tokens.mjs';
import {mount as mountQ1} from './q1-wall-view.mjs';
import {mount as mountQ2} from './q2-view.mjs';
import {mount as mountQ3} from './q3-bar-view.mjs';
import {mount as mountQ5} from './q5-log-view.mjs';
import {createPhaseStore,attachPhase,recordedResultAction} from './search-phase-model.mjs';
import {mount as mountSearchDialog} from './search-dialog-view.mjs';
import {mount as mountSearchPhase} from './search-phase-view.mjs';
import {createSettingsStore,SETTINGS_KEY} from './monitor-room-model.mjs';
import {mountMonitorRoom} from './monitor-room-view.mjs';
import {mount as mountTrackMap} from './track-map-view.mjs';
import {mountSimpleView} from './simple-view.mjs';
import {mountEventMenu} from './event-menu.mjs';
import {mountCoreScreens} from './core-screens-view.mjs';
import {buildCoreSearchRequest,buildCoreTrackRequest,ERROR_TEXT} from './core-search-track-model.mjs';
import {createBoundMediaResolver} from './core-media.mjs';

export function playbackBounds(s) {
  if(s.coreTrackResponse)return [s.coreTrackResponse.resolved_time?.source_range_us?.[0]??0,s.coreTrackResponse.as_of_us];
  if(s.task==='q2'&&s.q2?.timeline.length)return [s.q2.timeline[0].range_us[0],s.q2.timeline.at(-1).range_us[1]];
  if(s.selection?.kind==='Q1_SEGMENT')return s.selection.range_us;
  return [0,s.activeRun?.clock_mapping?.source_duration_us??0];
}
export function parsedExecutionRequest(response,switchMode) {
  if(response?.status!=='PARSED'||!response.structured_query)throw new Error('PARSED_QUERY_REQUIRED');
  const request=structuredClone(response.structured_query);
  if(request.schema_version==='q-demo.q2-request.v1'){
    if(!['RULE_ONLY','AGENT_SEQUENTIAL'].includes(switchMode))throw new Error('SWITCH_MODE');
    request.switch_mode=switchMode;
  }
  return request;
}
export function isCoreSearchRequest(request) {
  return request?.schema_version==='q-core.search-request.v1'||request?.action==='core_search'||request?.kind==='core_search';
}
export function isCoreTrackRequest(request) {
  return request?.schema_version==='q-core.track-request.v1'||request?.action==='core_track'||request?.kind==='core_track';
}
export function produceCoreSearchResponse(store,response,options={}) {
  return store.dispatch({
    type:'SET_CORE_SEARCH_RESPONSE',
    response,
    regionGraph:options.regionGraph??store.getState().regionGraph,
  });
}
export function produceCoreTrackResponse(store,response,options={}) {
  return store.dispatch({
    type:'SET_CORE_TRACK_RESPONSE',
    response,
    cameraGraph:options.cameraGraph??store.getState().cameraGraph,
    displayPositions:options.displayPositions??store.getState().displayPositions,
  });
}
export async function bootstrap(root=document,{api:providedApi=null,url=root.baseURI??globalThis.location?.href??'http://localhost/'}={}) {
  const config=new URL(url),reviewMode=config.searchParams.get('mode')==='review';
  const source=config.searchParams.get('source')==='fixture'?FIXTURE_ORIGIN:'SERVER';
  const api=providedApi??createQApi({source});const store=createStore(initialState({rail:loadRailPref(),reviewMode}));
  const handlers={};const shell=mountQShell(root,store,handlers);const $=selector=>root.querySelector(selector);
  let destroyed=false,raf=null,previous=null,carry=0,review=null,requestGeneration=0;
  const syncStampClock=s=>setStampClock(s.activeRun?.clock_mapping??null);syncStampClock(store.getState());const unsyncStamp=store.subscribe(syncStampClock);
  const playback=createPlayback({api,store,root,onReady:()=>renderTime(store.getState())});
  const context={
    store,
    slots:shell.slots,
    shell,
    api,
    execute,
    loadArtifacts,
    playback,
    produceCoreSearchResponse:(resp,opts)=>produceCoreSearchResponse(store,resp,opts),
    produceCoreTrackResponse:(resp,opts)=>produceCoreTrackResponse(store,resp,opts),
  };
  const views=[mountQ1,mountQ2,mountQ3,mountQ5].map(mount=>mount(context));
  const phase=createPhaseStore(),detachPhase=attachPhase(store,phase);
  views.push(mountSearchDialog({store,api,execute,phase}),mountSearchPhase({phase}),mountTrackMap({store,api}));
  const simpleView=mountSimpleView({doc:root,store,url});views.push(simpleView);  // 單純顯示模式 toggle; presentation only (simple-view.mjs)
  views.push(mountEventMenu({doc:root,simple:simpleView,store,url}));  // 事件選單: page events reload this page; live / complex events are embedded (event-menu.mjs)
  const coreScreens=mountCoreScreens({wallSlot:$('#core-search-wall-slot'),trackSlot:$('#core-tracking-slot'),store,api,playback,mediaResolver:createBoundMediaResolver({store,api}),synthetic:source===FIXTURE_ORIGIN});
  views.push(coreScreens);
  const syncCoreSlots=()=>{
    const s=store.getState();
    const cw=$('#core-search-wall-slot'),ct=$('#core-tracking-slot');
    if(cw)cw.hidden=!(s.coreSearchResponse||s.coreSearchWall);
    if(ct)ct.hidden=!(s.coreTrackResponse||s.coreTrackingView);
    if(s.coreSearchResponse||s.coreTrackResponse){if($('#q1-slot'))$('#q1-slot').hidden=true;if($('#q2-slot'))$('#q2-slot').hidden=true;}
  };
  const unsubCoreSlots=store.subscribe(syncCoreSlots);syncCoreSlots();
  // Monitor room (default main screen). Settings come from the admin page through localStorage; context.monitorRoom.setVisible() is the UI-A hook.
  const wallSlot=$('#monitor-room-slot'),wallSettings=createSettingsStore(globalThis.localStorage??null,{listen:fn=>{const on=e=>{if(!e.key||e.key===SETTINGS_KEY)fn();};globalThis.addEventListener?.('storage',on);return()=>globalThis.removeEventListener?.('storage',on);}});
  const monitorRoom=wallSlot?mountMonitorRoom(wallSlot,{api,settings:wallSettings}):null;context.monitorRoom=monitorRoom;
  // The wall follows the search phase: WALL shows the wall; SEARCHING and RESULT hide it (loading shows no camera frames; RESULT shows the hit wall or the tracking view).
  const syncWall=p=>{if(!monitorRoom)return;const s=store.getState();const on=p.phase==='wall'&&!s.coreSearchResponse&&!s.coreTrackResponse;monitorRoom.setVisible(on);root.querySelector('#q-root')?.setAttribute?.('data-monitor-wall',on?'on':'off');};
  const unsyncWall=phase.subscribe(syncWall);const unsyncCoreWall=store.subscribe(()=>syncWall(phase.getState()));syncWall(phase.getState());
  const legend=$('#legend');legend.replaceChildren();for(const item of Q_LEGEND){const el=document.createElement('span');el.className='it q-legend-'+item.code;el.textContent=`${item.code} ${item.label}`;legend.append(el);}
  const identity=document.createElement('span');identity.className='id';identity.textContent='身分未確認 · 物理通行與碰撞 UNKNOWN';legend.append(identity);
  async function execute(request,{selected_observation_id=null,keepParse=false}={}) {
    if(api.activeJob?.())await api.stopSession();
    const requestToken=++requestGeneration;
    const isCoreSearch=isCoreSearchRequest(request);
    const isCoreTrack=isCoreTrackRequest(request);
    const kind=isCoreSearch?'core_search':isCoreTrack?'core_track':request.schema_version==='q-demo.q1-request.v1'?'q1':request.schema_version==='q-demo.q2-request.v1'?'q2':'q3';
    const outgoing=structuredClone(request);outgoing.session_ref=api.getSession?.()??null;
    store.dispatch({type:'Q_LOADING',request:outgoing,kind,keepParse});
    if(isCoreSearch){
      const response=typeof api.coreSearch==='function'?await api.coreSearch(outgoing):{ok:false,error:{code:'CORE_SEARCH_UNSUPPORTED'}};
      if(destroyed||requestToken!==requestGeneration)return response;
      if(!response.ok){store.dispatch({type:'Q_ERROR',error:response.error});return response;}
      produceCoreSearchResponse(store,response.data);
      return response;
    }
    if(isCoreTrack){
      const response=typeof api.coreTrack==='function'?await api.coreTrack(outgoing):{ok:false,error:{code:'CORE_TRACK_UNSUPPORTED'}};
      if(destroyed||requestToken!==requestGeneration)return response;
      if(!response.ok){store.dispatch({type:'Q_ERROR',error:response.error});return response;}
      produceCoreTrackResponse(store,response.data);
      return response;
    }
    if(kind==='q2'&&outgoing.seed.kind==='APPEARANCE'){
      const choices=await api.seedCandidates(outgoing);if(destroyed||requestToken!==requestGeneration)return {ok:false,error:{code:'STALE_RESPONSE'}};if(!choices.ok){store.dispatch({type:'Q_ERROR',error:choices.error});return choices;}
      const picker=$('#q-manual-seed');if(picker){picker.replaceChildren();for(const c of choices.data.candidates){const option=document.createElement('option');option.value=c.observation_id;option.textContent=`${c.camera_id} · ${formatSource(c.timestamp_us)} · ${c.observation_id}`;picker.append(option);}}
      if(!selected_observation_id&&choices.data.status==='CHOICE_REQUIRED'){store.dispatch({type:'Q_SEEDS',data:choices.data});return choices;}
      if(!selected_observation_id&&choices.data.candidates.length===1)selected_observation_id=choices.data.candidates[0].observation_id;
    }
    const response=await api.query(kind,outgoing,{selected_observation_id});
    if(destroyed||requestToken!==requestGeneration||response.error?.code==='STALE_RESPONSE')return response;
    if(!response.ok){store.dispatch({type:'Q_ERROR',error:response.error});return response;}
    store.dispatch({type:'Q_RESPONSE',kind,data:response.data});
    if(kind==='q3'&&response.data.status==='PARSED')return execute(parsedExecutionRequest(response.data,store.getState().switchMode),{keepParse:true});
    if(kind==='q2')await loadArtifacts(response.data);  // normal mode keeps only the journal: the plain step log and the GAP caption read it
    if(kind==='q2'){
      const selectedId=selected_observation_id??(outgoing.seed.kind==='OBSERVATION'?outgoing.seed.observation_id:null);
      if(selectedId){const observed=await api.artifact(response.data,'observation',selectedId);
        if(observed.ok&&!destroyed&&requestToken===requestGeneration)store.dispatch({type:'SET_T_US',tUs:observed.data.timestamp_us});}
    }
    return response;
  }
  async function loadArtifacts(response) {
    const journal=await api.artifact(response,'decisions',response.decisions_ref);
    if(!journal.ok)return journal;
    // Normal mode keeps only the journal (plain step log); snapshots and evidence stay review-only.
    if(!reviewMode){store.dispatch({type:'Q_ARTIFACTS',for_hash:response.output_sha256,data:{decisions:journal.data,snapshots:{},evidence:{}}});return journal;}
    const snapshots={},evidence={};
    for(const d of journal.data){if(d.candidate_snapshot_sha256&&!snapshots[d.candidate_snapshot_sha256]){
      const item=await api.artifact(response,'snapshot',d.candidate_snapshot_sha256);if(item.ok)snapshots[d.candidate_snapshot_sha256]=item.data;
    }for(const candidate of d.candidates_considered){if(candidate.evidence_sha256&&!evidence[candidate.evidence_sha256]){const item=await api.artifact(response,'evidence',candidate.evidence_sha256);if(item.ok)evidence[candidate.evidence_sha256]=item.data;}}}
    store.dispatch({type:'Q_ARTIFACTS',for_hash:response.output_sha256,data:{decisions:journal.data,snapshots,evidence}});return journal;
  }
  handlers.run=index=>{const run=store.getState().bootstrap?.runs[index];if(!run)return;requestGeneration++;api.invalidate();store.dispatch({type:'SET_Q_RUN',run});};
  handlers.fixture=async name=>{
    if(name==='core-search'||name==='core-track'){
      const isSearch=name==='core-search';
      const request=(await api.initialRequest?.(name))??{
        schema_version:isSearch?'q-core.search-request.v1':'q-core.track-request.v1',
      };
      return execute(request);
    }
    const kind=name.slice(0,2);const request=await api.initialRequest(kind,name);if(kind==='q2')request.switch_mode=name==='q2-agent'?'AGENT_SEQUENTIAL':'RULE_ONLY';store.dispatch({type:'SET_SWITCH_MODE',value:request.switch_mode??'RULE_ONLY'});await execute(request);
  };
  const coreControl=$('#q-core-query');
  const coreFeedback=$('#q-core-feedback');
  const verifiedRegions=new WeakMap();
  const coreRegionCatalog=run=>verifiedRegions.get(run)??[];
  async function verifyCoreRegions(run){
    const attached=Boolean(run?.region_graph),graph=run?.region_graph??store.getState().regionGraph;
    if(!graph||typeof run?.region_graph_sha256!=='string'||graph.content_sha256!==run.region_graph_sha256||!Array.isArray(graph.regions)||(!attached&&(graph.scene_id!==run.scene_id||graph.run_id!==run.run_id))||graph.scene_id&&graph.scene_id!==run.scene_id||graph.run_id&&graph.run_id!==run.run_id)return;
    if(await contentHash(graph,{excludeRoot:['content_sha256','stats']})!==run.region_graph_sha256)return;
    if(destroyed||store.getState().activeRun!==run)return;
    verifiedRegions.set(run,graph.regions.filter(r=>typeof r.region_id==='string').map(r=>({value:r.region_id,label:r.display_name??r.region_id})));
    renderCoreRegions(run);
  }
  const coreForm=()=>({start:$('#q-core-start')?.value??'',end:$('#q-core-end')?.value??'',classLabel:$('#q-core-class')?.value??'',colorLabel:$('#q-core-color')?.value??'',regionIds:[...($('#q-core-region')?.selectedOptions??[])].map(option=>option.value)});
  const coreMenus=run=>({regions:coreRegionCatalog(run),classes:run.supported_classes?.class_labels??[],colors:run.supported_classes?.color_vocabulary?.labels??[]});
  let displayedRun=null;
  function renderCoreRegions(run){
    const regions=$('#q-core-region');if(!regions)return;
    regions.replaceChildren();const catalog=coreRegionCatalog(run);regions.disabled=catalog.length===0;
    for(const region of catalog){const option=document.createElement('option');option.value=region.value;option.textContent=region.label;regions.append(option);}
    if(!catalog.length){const option=document.createElement('option');option.value='';option.textContent='UNKNOWN · 地點目錄未就緒';regions.append(option);}
  }
  function updateCoreMenus(){
    if(!coreControl)return;
    const run=store.getState().activeRun;
    if(run===displayedRun)return;displayedRun=run;
    const classes=$('#q-core-class'),colors=$('#q-core-color');
    classes.replaceChildren();colors.replaceChildren();renderCoreRegions(run);
    if(!run)return;
    for(const label of ['',...(run.supported_classes?.class_labels??[])]){const option=document.createElement('option');option.value=label;option.textContent=label||'不限類別';classes.append(option);}
    for(const label of ['',...(run.supported_classes?.color_vocabulary?.labels??[])]){const option=document.createElement('option');option.value=label;option.textContent=label||'不限';colors.append(option);}
    verifyCoreRegions(run).catch(()=>{});
  }
  const unsubCoreMenus=store.subscribe(updateCoreMenus);updateCoreMenus();
  async function submitCore(kind){
    const run=store.getState().activeRun;
    if(!run||!api.getSession?.()){if(coreFeedback)coreFeedback.textContent='UNKNOWN · 來源或 session 未就緒';return;}
    try{
      const request=kind==='search'?buildCoreSearchRequest(run,api.getSession(),coreForm(),coreMenus(run)):buildCoreTrackRequest(run,api.getSession(),coreForm(),coreMenus(run),store.getState().tUs);
      const result=await execute(request);
      if(coreFeedback)coreFeedback.textContent=result.ok?`${kind==='search'?'查找':'追蹤'}回應：${result.data.status}`:`UNKNOWN · ${result.error?.code??'REQUEST_FAILED'}`;
    }catch(error){if(coreFeedback)coreFeedback.textContent=ERROR_TEXT[error.message]??`UNKNOWN · ${error.message}`;}
  }
  const coreSearchButton=$('#q-core-search'),coreTrackButton=$('#q-core-track');
  if(coreControl){coreSearchButton?.addEventListener('click',()=>submitCore('search'));coreTrackButton?.addEventListener('click',()=>submitCore('track'));}
  handlers.recording=async id=>{const requestToken=++requestGeneration;api.invalidate();const result=await api.replay(id);if(destroyed||requestToken!==requestGeneration)return;if(!result.ok){store.dispatch({type:'Q_ERROR',error:result.error});return;}
    const kind=responseKind(result.data);
    const recording=store.getState().bootstrap?.recordings.find(x=>x.recording_id===id);
    const run=store.getState().bootstrap?.runs.find(r=>r.scene_id===result.data.resolved_scope.scene_id&&r.run_id===result.data.resolved_scope.run_ids?.[0]);
    store.dispatch({type:'SET_Q_RUN',run:run??null});store.dispatch({type:'Q_RESPONSE',kind,data:result.data,source_origin:'RECORDED',source_kind:recording?.source_kind,recorded_at:recording?.recorded_at??null});if(['RULE_ONLY','AGENT_SEQUENTIAL'].includes(recording?.switch_mode)&&(recording.switch_mode==='RULE_ONLY'||run?.agent_available))store.dispatch({type:'SET_SWITCH_MODE',value:recording.switch_mode});if(kind==='q2')await loadArtifacts(result.data);const toResult=recordedResultAction(store.getState());if(toResult)phase.dispatch(toResult);};
  const manualButton=$('#q-manual-apply');if(manualButton)manualButton.onclick=async()=>{const result=await api.manualSeed(api.activeJob?.(),$('#q-manual-seed').value,{restartAgent:$('#q-manual-restart').checked});$('#q-manual-result').textContent=result.ok?'已排入手動改選；session 累計不歸零。':`未套用：${result.error?.code??'UNKNOWN'}`;};
  handlers.stop=async()=>{const stopped=await api.stopSession();if(!stopped.ok){store.dispatch({type:'Q_ERROR',error:stopped.error});return;}requestGeneration++;store.dispatch({type:'PAUSE'});store.dispatch({type:'Q_ERROR',error:{code:'USER_STOPPED',message:'追查已停止；模型是否已停止運算未知。'}});};
  handlers.step=direction=>{const state=store.getState(),interval=state.activeRun?.sampling?.per_camera[0]?.source_frame_interval_us;const [start,end]=playbackBounds(state);if(!interval||!end)return;store.dispatch({type:'PAUSE'});store.dispatch({type:'SET_T_US',tUs:Math.max(start,stepUs(state.tUs,interval,direction,end))});};
  handlers.review=async()=>{
    if(!reviewMode||review)return;
    try {const module=await import('./review/review-view.mjs');
      const readReviewState=()=>{const s=store.getState();return Object.freeze({q1:s.q1,q2:s.q2,q3:s.q3,artifacts:s.artifacts,bootstrap:s.bootstrap,activeRun:s.activeRun,recordedKind:s.recordedKind,responseOrigin:s.responseOrigin,recordedAt:s.recordedAt});};
      review=module.mount(Object.freeze({root:shell.slots.review,getState:readReviewState,subscribe:fn=>store.subscribe(()=>fn(readReviewState())),getRequests:api.getRequests,
        seek:tUs=>{store.dispatch({type:'PAUSE'});store.dispatch({type:'SET_T_US',tUs});}}));
    }catch{$('#q-review-slot').textContent='審核功能尚未準備好。';}
  };
  const speedMeter=createSpeedMeter();let meterKey='';
  let measuredCoreRate=null,coreRateSample=null;
  const coreRate=document.createElement('span');coreRate.id='q-core-rate';coreRate.className='note';$('#q-play').after(coreRate);
  function renderTime(s) {
    // 播放列小字：設定倍速與實際倍速（暫停、換倍速或跳轉時重新量測）。
    const key=`${s.playing}|${s.speed}`;if(key!==meterKey){meterKey=key;speedMeter.reset();}
    if(s.playing)speedMeter.record(s.tUs,performance.now());const note=$('#q-speed-note');if(note)note.textContent=formatSpeedNote(s.speed,s.playing?speedMeter.actual(performance.now()):null);
    $('#q-speed').value=String(s.speed);
    coreRate.hidden=!(s.coreTrackResponse&&s.activeRun?.source_kind==='SYNTHETIC');
    coreRate.textContent=`設定 ${s.speed}× · 實際 ${measuredCoreRate===null?'UNKNOWN':measuredCoreRate.toFixed(2)+'×'}（${s.playing?'合成時鐘':'已暫停；上次合成時鐘'}）`;
    $('#q-time').textContent=formatSource(s.tUs);const v=virtualTime(s.tUs,s.activeRun?.clock_mapping);$('#q-wall').textContent=v?`${v.text}（${v.tz}）`:displayClock(s.tUs,s.activeRun?.clock_mapping);$('#q-wall').dataset.tag=v?.declared?DECLARED_TAG:'';$('#q-scrub').title=v?`演示時間 ${v.text}（${v.tz}）`:'演示時間 UNKNOWN';
    const [start,end]=playbackBounds(s);const scrub=$('#q-scrub');scrub.min=String(start);scrub.max=String(end);scrub.value=String(s.tUs);
    const stop=$('#q-stop');if(stop)stop.disabled=!api.activeJob?.();
    const ready=playback.clockReady();
    $('#q-play').disabled=end<=start||!canPlay(s)||(!s.playing&&!ready);$('#q-play').title=canPlay(s)?'播放已載入的來源片段':'請先開啟錄製事件或選擇查詢片段';$('#q-play').textContent=s.playing?'Ⅱ 暫停':'▶ 播放';
    const unavailable=!s.activeRun?.sampling?.per_camera[0]?.source_frame_interval_us;$('#q-prev').disabled=unavailable;$('#q-next').disabled=unavailable;
  }
  const unsubscribe=store.subscribe(renderTime);renderTime(store.getState());
  const noteTimer=setInterval(()=>{const n=$('#q-speed-note'),s=store.getState();if(n&&s.playing)n.textContent=formatSpeedNote(s.speed,speedMeter.actual(performance.now()));},500);
  function frame(now){if(destroyed)return;const running=Boolean(api.activeJob?.());const stop=$('#q-stop');if(stop)stop.disabled=!running;if(manualButton)manualButton.disabled=!running||!$('#q-manual-seed').value;const s=store.getState();if(s.playing&&s.coreTrackResponse&&s.activeRun?.source_kind==='SYNTHETIC'){if(!coreRateSample)coreRateSample={wall:now,source:s.tUs};else if(now-coreRateSample.wall>=300){const dt=s.tUs-coreRateSample.source;if(dt>=0)measuredCoreRate=dt/(1000*(now-coreRateSample.wall));coreRateSample={wall:now,source:s.tUs};}}else coreRateSample=null;if(s.playing&&previous!==null){const [start,end]=playbackBounds(s);const step=afterTick(advanceUs(s.tUs,playbackDelta(s,now-previous,playback.clockReady()),s.speed,end,carry),{loop:wallSettings.get().loop,start,end});carry=step.carry;store.dispatch({type:'SET_T_US',tUs:step.tUs});if(step.pause)store.dispatch({type:'PAUSE'});}else carry=0;previous=now;raf=requestAnimationFrame(frame);}
  raf=requestAnimationFrame(frame);
  const [loaded,session]=await Promise.all([api.bootstrap(),api.createSession()]);
  if(!loaded.ok||!session.ok)store.dispatch({type:'Q_ERROR',error:loaded.error??session.error});
  else{store.dispatch({type:'SET_Q_BOOTSTRAP',data:loaded.data});monitorRoom?.setBootstrap(loaded.data);if(loaded.data.runs.length)store.dispatch({type:'SET_Q_RUN',run:loaded.data.runs[0]});
    const requestedRecording=config.searchParams.get('recording');
    if(requestedRecording&&loaded.data.recordings.some(x=>x.recording_id===requestedRecording)){store.dispatch({type:'SET_PLAYBACK_MODE',value:'single'});await handlers.recording(requestedRecording);}
    else if(loaded.data.recordings.length===1&&loaded.data.runs.length===1&&loaded.data.runs[0].source_kind==='SYNTHETIC'){store.dispatch({type:'SET_PLAYBACK_MODE',value:'single'});await handlers.recording(loaded.data.recordings[0].recording_id);}}
  return {...context,destroy(){destroyed=true;requestGeneration++;cancelAnimationFrame(raf);unsubscribe();unsubCoreSlots();unsubCoreMenus();clearInterval(noteTimer);unsyncStamp();detachPhase();unsyncWall();unsyncCoreWall();monitorRoom?.destroy();wallSettings.destroy();playback.destroy();review?.destroy?.();views.forEach(v=>v?.destroy?.());shell.destroy();}};
}
if(typeof document!=='undefined')bootstrap();

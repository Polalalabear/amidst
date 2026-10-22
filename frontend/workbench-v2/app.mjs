// Q composition root. Review code has a separate dynamic boundary and receives
// immutable state/read-only subscriptions, never the API object or query dispatch.
import {createStore,initialState} from './store.mjs';
import {mountQShell,loadRailPref} from './shell-view.mjs';
import {createQApi,FIXTURE_ORIGIN} from './q-api.mjs';
import {advanceUs,stepUs,formatSource,displayClock} from './q-time.mjs';
import {Q_LEGEND} from './q-tokens.mjs';
import {mount as mountQ1} from './q1-wall-view.mjs';
import {mount as mountQ2} from './q2-view.mjs';
import {mount as mountQ3} from './q3-bar-view.mjs';
import {mount as mountQ5} from './q5-log-view.mjs';

export function playbackBounds(s) {
  if(s.task==='q2'&&s.q2?.timeline.length)return [s.q2.timeline[0].range_us[0],s.q2.timeline.at(-1).range_us[1]];
  if(s.selection?.kind==='Q1_SEGMENT')return s.selection.range_us;
  return [0,s.activeRun?.clock_mapping?.source_duration_us??0];
}
export async function bootstrap(root=document,{api:providedApi=null,url=root.baseURI??globalThis.location?.href??'http://localhost/'}={}) {
  const config=new URL(url),reviewMode=config.searchParams.get('mode')==='review';
  const source=config.searchParams.get('source')==='fixture'?FIXTURE_ORIGIN:'SERVER';
  const api=providedApi??createQApi({source});const store=createStore(initialState({rail:loadRailPref(),reviewMode}));
  const handlers={};const shell=mountQShell(root,store,handlers);const $=selector=>root.querySelector(selector);
  let destroyed=false,raf=null,previous=null,carry=0,review=null,requestGeneration=0;
  const context={store,slots:shell.slots,shell,api,execute,loadArtifacts};
  const views=[mountQ1,mountQ2,mountQ3,mountQ5].map(mount=>mount(context));
  const legend=$('#legend');legend.replaceChildren();for(const item of Q_LEGEND){const el=document.createElement('span');el.className='it q-legend-'+item.code;el.textContent=`${item.code} ${item.label}`;legend.append(el);}
  const identity=document.createElement('span');identity.className='id';identity.textContent='身分未確認 · 物理通行與碰撞 UNKNOWN';legend.append(identity);
  async function execute(request,{selected_observation_id=null,keepParse=false}={}) {
    const requestToken=++requestGeneration;
    const kind=request.schema_version==='q-demo.q1-request.v1'?'q1':request.schema_version==='q-demo.q2-request.v1'?'q2':'q3';
    const outgoing=structuredClone(request);outgoing.session_ref=api.getSession();
    store.dispatch({type:'Q_LOADING',request:outgoing,kind,keepParse});
    if(kind==='q2'&&outgoing.seed.kind==='APPEARANCE'&&!selected_observation_id){
      const choices=await api.seedCandidates(outgoing);if(destroyed||requestToken!==requestGeneration)return {ok:false,error:{code:'STALE_RESPONSE'}};if(!choices.ok){store.dispatch({type:'Q_ERROR',error:choices.error});return choices;}
      if(choices.data.status==='CHOICE_REQUIRED'){store.dispatch({type:'Q_SEEDS',data:choices.data});return choices;}
      if(choices.data.candidates.length===1)selected_observation_id=choices.data.candidates[0].observation_id;
    }
    const response=await api.query(kind,outgoing,{selected_observation_id});
    if(destroyed||requestToken!==requestGeneration||response.error?.code==='STALE_RESPONSE')return response;
    if(!response.ok){store.dispatch({type:'Q_ERROR',error:response.error});return response;}
    store.dispatch({type:'Q_RESPONSE',kind,data:response.data});
    if(kind==='q3'&&response.data.status==='PARSED')return execute(response.data.structured_query,{keepParse:true});
    if(kind==='q2'&&reviewMode)await loadArtifacts(response.data);
    return response;
  }
  async function loadArtifacts(response) {
    if(!reviewMode)return {ok:false,error:{code:'REVIEW_ONLY'}};
    const journal=await api.artifact(response,'decisions',response.decisions_ref);
    if(!journal.ok)return journal;
    const snapshots={},evidence={};
    for(const d of journal.data){if(d.candidate_snapshot_sha256&&!snapshots[d.candidate_snapshot_sha256]){
      const item=await api.artifact(response,'snapshot',d.candidate_snapshot_sha256);if(item.ok)snapshots[d.candidate_snapshot_sha256]=item.data;
    }for(const candidate of d.candidates_considered){if(candidate.evidence_sha256&&!evidence[candidate.evidence_sha256]){const item=await api.artifact(response,'evidence',candidate.evidence_sha256);if(item.ok)evidence[candidate.evidence_sha256]=item.data;}}}
    store.dispatch({type:'Q_ARTIFACTS',for_hash:response.output_sha256,data:{decisions:journal.data,snapshots,evidence}});return journal;
  }
  handlers.run=index=>{const run=store.getState().bootstrap?.runs[index];if(!run)return;requestGeneration++;api.invalidate();store.dispatch({type:'SET_Q_RUN',run});};
  handlers.fixture=async name=>{const kind=name.slice(0,2);const request=await api.initialRequest(kind,name);if(kind==='q2')request.switch_mode=name==='q2-agent'?'AGENT_SEQUENTIAL':'RULE_ONLY';store.dispatch({type:'SET_SWITCH_MODE',value:request.switch_mode??'RULE_ONLY'});await execute(request);};
  handlers.recording=async id=>{const requestToken=++requestGeneration;api.invalidate();const result=await api.replay(id);if(destroyed||requestToken!==requestGeneration)return;if(!result.ok){store.dispatch({type:'Q_ERROR',error:result.error});return;}
    const kind=result.data.schema_version==='q-demo.q1-response.v1'?'q1':result.data.schema_version==='q-demo.q2-response.v1'?'q2':'q3';
    const run=store.getState().bootstrap?.runs.find(r=>r.scene_id===result.data.resolved_scope.scene_id&&r.run_id===result.data.resolved_scope.run_ids?.[0]);
    store.dispatch({type:'SET_Q_RUN',run:run??null});store.dispatch({type:'Q_RESPONSE',kind,data:result.data,source_origin:'RECORDED',source_kind:store.getState().bootstrap?.recordings.find(x=>x.recording_id===id)?.source_kind});if(kind==='q2'&&reviewMode)await loadArtifacts(result.data);};
  handlers.step=direction=>{const state=store.getState(),interval=state.activeRun?.sampling?.per_camera[0]?.source_frame_interval_us;const [start,end]=playbackBounds(state);if(!interval||!end)return;store.dispatch({type:'PAUSE'});store.dispatch({type:'SET_T_US',tUs:Math.max(start,stepUs(state.tUs,interval,direction,end))});};
  handlers.review=async()=>{
    if(!reviewMode||review)return;
    try {const module=await import('./review/review-view.mjs');
      const readReviewState=()=>{const s=store.getState();return Object.freeze({q1:s.q1,q2:s.q2,q3:s.q3,artifacts:s.artifacts,bootstrap:s.bootstrap,activeRun:s.activeRun,recordedKind:s.recordedKind,responseOrigin:s.responseOrigin});};
      review=module.mount(Object.freeze({root:shell.slots.review,getState:readReviewState,subscribe:fn=>store.subscribe(()=>fn(readReviewState())),getRequests:api.getRequests,
        seek:tUs=>{store.dispatch({type:'PAUSE'});store.dispatch({type:'SET_T_US',tUs});}}));
    }catch{$('#q-review-slot').textContent='審核功能尚未準備好。';}
  };
  function renderTime(s) {
    $('#q-time').textContent=formatSource(s.tUs);$('#q-wall').textContent=displayClock(s.tUs,s.activeRun?.clock_mapping);
    const [start,end]=playbackBounds(s);const scrub=$('#q-scrub');scrub.min=String(start);scrub.max=String(end);scrub.value=String(s.tUs);
    $('#q-play').disabled=end<=start;$('#q-play').textContent=s.playing?'Ⅱ 暫停':'▶ 播放';
    const unavailable=!s.activeRun?.sampling?.per_camera[0]?.source_frame_interval_us;$('#q-prev').disabled=unavailable;$('#q-next').disabled=unavailable;
  }
  const unsubscribe=store.subscribe(renderTime);renderTime(store.getState());
  function frame(now){if(destroyed)return;const s=store.getState();if(s.playing&&previous!==null){const [,end]=playbackBounds(s);const next=advanceUs(s.tUs,now-previous,s.speed,end,carry);carry=next.carry;store.dispatch({type:'SET_T_US',tUs:next.tUs});if(next.ended)store.dispatch({type:'PAUSE'});}else carry=0;previous=now;raf=requestAnimationFrame(frame);}
  raf=requestAnimationFrame(frame);
  const [loaded,session]=await Promise.all([api.bootstrap(),api.createSession()]);
  if(!loaded.ok||!session.ok)store.dispatch({type:'Q_ERROR',error:loaded.error??session.error});
  else{store.dispatch({type:'SET_Q_BOOTSTRAP',data:loaded.data});if(loaded.data.runs.length)store.dispatch({type:'SET_Q_RUN',run:loaded.data.runs[0]});}
  return {...context,destroy(){destroyed=true;requestGeneration++;cancelAnimationFrame(raf);unsubscribe();review?.destroy?.();views.forEach(v=>v?.destroy?.());shell.destroy();}};
}
if(typeof document!=='undefined')bootstrap();

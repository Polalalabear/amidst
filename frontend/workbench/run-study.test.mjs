import test from 'node:test';
import assert from 'node:assert/strict';
import {RunStudyPanel,runStudySceneSupported,validateRunParameters,validateRunResult,
  runComparisonHTML,runTrajectoryHTML,validateStudyAnswer,studyReportHTML,studyComparisonHTML,studyTaskPrompt} from './run-study.mjs';

const deferred=()=>{let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};};
const hash='a'.repeat(64);
const snapshot={scene_id:'synthetic-lab',run_id:'source-run'};
const runContext={schema_version:'workbench.synthetic-jobs.v1',available:true,scene_id:snapshot.scene_id,
  source_run_id:snapshot.run_id,source_sha256:hash,current_annotation_version:2,
  supported_parameters:{max_speed_m_s:{default:3,min:.1,max:20}}};
const binding={scene_id:snapshot.scene_id,run_id:snapshot.run_id,source_sha256:hash,
  dataset_sha256:hash,config_sha256:hash,freeze_ref:'freeze:a',clock_id:'clock:a',
  registry_sha256:hash,media_sha256:hash,frame_metadata_sha256:hash};
const task={task_ref:'task:a',family:'source_frame_order',prompt:'Open original frames A/B',answer_type:'order',
  camera_ids:['CAM_A'],time_range:[0,8],targets:[{label:'A',camera_id:'CAM_A',frame_ref:'frame:a'},
    {label:'B',camera_id:'CAM_A',frame_ref:'frame:b'}]};
const studyContext={schema_version:'operator.study.context.v1',available:true,status:'PREPARATION_REHEARSAL',
  binding,tasks:[task],actual_operator_acceptance:false};
const job=(state='COMPLETED',ref='job:a')=>({job_ref:ref,scene_id:snapshot.scene_id,source_run_id:snapshot.run_id,
  new_run_id:'new:'+ref,annotation_version:2,annotation_sha256:hash,input_sha256:hash,config_sha256:hash,
  state,result_available:state==='COMPLETED',progress:{completed:3,total:3}});
const result=(ref='job:a')=>({schema_version:'workbench.synthetic-run-result.v1',...job('COMPLETED',ref),
  source_sha256:hash,deterministic_sha256:hash,view_only:true,formal_phase1_acceptance:false,
  comparison:{baseline:{events:2,local_tracks:4},new:{events:3,local_tracks:5},delta:{events:1,local_tracks:1}},
  observations:[{observation_ref:'observation:new',projected_path:[{world_position:[1,2,0]},{world_position:[2,3,0]}]}],
  events:[{event_ref:'event:new',observation_refs:['observation:new'],kind:'GAP',time_range:[0,8],camera_ids:['CAM_A'],
    source_frames:[{frame_ref:'original:a',camera_id:'CAM_A',timestamp:0}],candidates:[{polyline:[[2,3,0],[5,4,0]],
      path_length:3,minimum_travel_time:1,estimated_travel_time:2}],trajectories:[]}]});
const attempt=(mode='manual',status='RUNNING')=>({schema_version:'operator.study.report.v1',study_ref:'study:a',task,mode,status,
  phase:'PREPARATION_REHEARSAL',binding,actual_operator_acceptance:false,protocol_valid:true,
  metrics:{duration_ms:800,camera_view_count:1,frame_open_count:1,distinct_camera_count:1,correction_count:0,
    evidence_open_count:0,correctness:status==='COMPLETED'?'UNKNOWN':'NOT_SUBMITTED',completed_denominator:status==='COMPLETED'?1:0,
    unresolved_count:status==='COMPLETED'?1:0,protocol_excluded_count:0,excluded_resume_gap_ms:0,eligible_completed_denominator:0,correct_count:0}});
const view=(mode='manual')=>({schema_version:'operator.study.view.v1',study_ref:'study:a',phase:'PREPARATION_REHEARSAL',mode,binding,
  frame:{frame_ref:'frame:a',camera_id:'CAM_A',timestamp:0,media_ref:'original:a'},assistance:mode==='manual'?null:
    {evidence_ref:'evidence:a',registered_timestamps:[0,4,8]}});

function panel(transport=async()=>undefined){
  const nodes=new Map(),calls=[],images=[];
  class Element{
    constructor(){this.innerHTML='';this.textContent='';this.value='';this.checked=false;this.disabled=false;this.dataset={};this.listeners=new Map();}
    replaceChildren(){this.innerHTML='';this.textContent='';}
    addEventListener(event,handler){this.listeners.set(event,handler);}
    removeEventListener(event,handler){if(this.listeners.get(event)===handler)this.listeners.delete(event);}
    emit(event){this.complete=true;this.listeners.get(event)?.();}
  }
  const get=selector=>{if(!nodes.has(selector))nodes.set(selector,new Element());return nodes.get(selector);};
  const params=[Object.assign(new Element(),{value:'3',dataset:{runParam:'max_speed_m_s'}})];
  const container=new Element();container.querySelector=get;container.querySelectorAll=selector=>selector==='[data-run-param]'?params:
    selector==='[data-run-comparison] img'?images:[];
  const ui=Object.create(RunStudyPanel.prototype);
  Object.assign(ui,{container,snapshot,reviewVersion:2,closed:false,serial:1,runEpoch:0,studyEpoch:0,pollTimer:null,
    runContext,studyContext,job:null,jobs:[],attempt:null,runResult:null,studyReport:null,studyFrame:null,studyAssistance:null,
    selectedStudyMode:'manual',runBusy:false,studyBusy:false,manualStudyPending:false,runRequests:new Set(),
    runImageRequests:new Set(),imageLoads:new WeakMap(),studies:[],
    mediaURL:(ref,studyRef)=>studyRef?'/study-media/'+studyRef+'/'+ref:'/base-media/'+ref,
    call:async(action,payload)=>{
      calls.push({action,payload:structuredClone(payload)});
      const value=await transport(action,payload);if(value!==undefined)return value;
      if(action==='run_context')return runContext;
      if(action==='operator_study_context')return studyContext;
      if(action==='run_list')return {items:[]};
      if(action==='operator_study_list')return {items:[]};
      if(action==='operator_study_report')return attempt('manual','COMPLETED');
      throw Error('UNEXPECTED_REQUEST:'+action);
    }});
  get('[data-run-version]').value='2';get('[data-study-task]').value=task.task_ref;
  get('[data-study-mode]').value='manual';get('[data-study-camera]').value='CAM_A';get('[data-study-timestamp]').value='0';
  return {ui,get,calls,params,container,images,Element};
}

test('only E0 is capability-enabled; unsupported scenes make no backend requests',async()=>{
  for(const scene_id of ['local-camera-e1','local-camera-accuracy-v2','blender-school']){
    const {ui,calls,container}=panel();ui.snapshot={scene_id,run_id:'other'};
    await ui.initialize();assert.equal(calls.length,0);assert.match(container.innerHTML,/此場景尚未接入/);
  }
  assert.equal(runStudySceneSupported(snapshot),true);
});

test('only complete, finite and bounded known run parameters are accepted',()=>{
  assert.deepEqual(validateRunParameters(runContext,{max_speed_m_s:3}),{max_speed_m_s:3});
  for(const parameters of [{},{max_speed_m_s:Infinity},{max_speed_m_s:21},{max_speed_m_s:0},
    {max_speed_m_s:3,private_path:'/tmp/forbidden'}])assert.throws(()=>validateRunParameters(runContext,parameters));
});

test('source/config/annotation/job binding mismatches cannot become a comparison',()=>{
  validateRunResult(runContext,job(),result());
  for(const changed of [{job_ref:'job:other'},{source_run_id:'other'},{source_sha256:'b'.repeat(64)},
    {annotation_version:1},{config_sha256:'b'.repeat(64)},{view_only:false},{formal_phase1_acceptance:true}])
    assert.throws(()=>validateRunResult(runContext,job(),{...result(),...changed}),/不一致/);
});

test('same-result observations supply projected points and source images without old event lookups',()=>{
  const html=runComparisonHTML(result(),ref=>'/source/'+ref);
  assert.match(html,/<circle/);assert.match(html,/<polyline/);assert.match(html,/原來源影格/);
  assert.match(html,/\/source\/original:a/);assert.match(html,/事件候選 1/);assert.match(html,/替代 1/);
  assert.match(html,/數量變化不代表精度/);assert.doesNotMatch(html,/api\/event/);
  assert.match(runTrajectoryHTML({projected_path:[[NaN,1,0]],candidates:[]}),/不補造動線/);
});

test('late job selection replies cannot overwrite a newer opened run',async()=>{
  const old=deferred(),recent=deferred(),{ui,get}=panel((action,payload)=>{
    if(action==='run_get')return payload.job_ref==='job:old'?old.promise:recent.promise;
    if(action==='run_result')return result(payload.job_ref);
  });
  get('[data-run-history]').value='job:old';const first=ui.openJob().catch(error=>error.message);
  get('[data-run-history]').value='job:new';const second=ui.openJob();
  recent.resolve(job('COMPLETED','job:new'));await second;old.resolve(job('COMPLETED','job:old'));
  assert.equal(await first,'SESSION_CHANGED');assert.equal(ui.job.job_ref,'job:new');assert.equal(ui.runResult.job_ref,'job:new');
});

test('unconfirmed start retries reuse the exact idempotency key and changed input creates another',async()=>{
  const {ui,calls,params}=panel(action=>{if(action==='run_start')throw Error('NETWORK_UNAVAILABLE');});
  await assert.rejects(ui.startRun(),/NETWORK/);await assert.rejects(ui.startRun(),/NETWORK/);
  params[0].value='4';await assert.rejects(ui.startRun(),/NETWORK/);
  const starts=calls.filter(call=>call.action==='run_start');
  assert.equal(starts[0].payload.idempotency_key,starts[1].payload.idempotency_key);
  assert.notEqual(starts[1].payload.idempotency_key,starts[2].payload.idempotency_key);
  assert.equal(starts[0].payload.annotation_version,2);
});

test('stop invalidates an earlier polling reply and preserves the cancelled status',async()=>{
  const pending=deferred(),{ui}=panel(action=>action==='run_get'?pending.promise:action==='run_cancel'?job('CANCELLED'):undefined);
  ui.job=job('RUNNING');const polling=ui.refreshRun().catch(error=>error.message);
  await ui.stopRun();pending.resolve(job('RUNNING'));
  assert.equal(await polling,'SESSION_CHANGED');assert.equal(ui.job.state,'CANCELLED');assert.equal(ui.pollTimer,null);
});

test('scheduled status checks stop after disposal and cannot request another run',async t=>{
  const callbacks=[];t.mock.method(globalThis,'setTimeout',callback=>{callbacks.push(callback);return 1;});
  t.mock.method(globalThis,'clearTimeout',()=>{});
  const {ui,calls}=panel();ui.job=job('RUNNING');ui.schedulePoll();ui.dispose();await callbacks[0]();
  assert.equal(calls.length,0);assert.equal(ui.pollTimer,null);
});

test('manual start waits for earlier run requests, stops polling and blocks subsequent assisted requests',async()=>{
  const pending=deferred(),{ui,calls,get}=panel(action=>{
    if(action==='run_get')return pending.promise;
    if(action==='operator_study_start')return {...attempt(),recovery_token:'private-recovery'};
  });
  ui.job=job('RUNNING');const polling=ui.refreshRun().catch(error=>error.message),starting=ui.startStudy();
  await Promise.resolve();assert.equal(calls.some(call=>call.action==='operator_study_start'),false);
  assert.equal(ui.manualStudyPending,true);assert.equal(get('[data-run-start]').disabled,true);
  pending.resolve(job('RUNNING'));await starting;assert.equal(await polling,'SESSION_CHANGED');
  assert.equal(ui.attempt.mode,'manual');assert.equal(ui.pollTimer,null);
  await assert.rejects(ui.request('run_get',{job_ref:'job:a'}),/人工搜尋/);
  assert.equal(get('[data-study-current-token]').value,'private-recovery');
  assert.doesNotMatch(get('[data-study-status]').innerHTML,/private-recovery/);
});

test('unfinished manual history is checked before run context so returning cannot contaminate it',async()=>{
  const {ui,calls,get}=panel(action=>action==='operator_study_list'?{items:[{study_ref:'study:a',mode:'manual',status:'RUNNING'}]}:undefined);
  ui.runContext=null;await ui.initialize();
  assert.equal(calls.some(call=>call.action.startsWith('run_')),false);
  assert.match(get('[data-run-body]').textContent,/人工搜尋任務/);
});

test('manual views reject assisted metadata, wrong camera and changed freeze before displaying them',async()=>{
  for(const bad of [{...view(),assistance:{expected_answer:0}},
    {...view(),frame:{...view().frame,camera_id:'CAM_UNKNOWN'}},{...view(),binding:{...binding,freeze_ref:'other'}}]){
    const {ui,get}=panel(action=>action==='operator_study_view'?bad:undefined);ui.attempt=attempt();
    await assert.rejects(ui.viewStudy(),/不符合/);assert.equal(get('[data-study-view]').innerHTML,'');
  }
});

test('actual view DTO uses the study-only media route and does not duplicate server view counters',async()=>{
  const {ui,get,calls}=panel(action=>action==='operator_study_view'?view():undefined);ui.attempt=attempt();
  await ui.viewStudy();assert.match(get('[data-study-view]').innerHTML,/\/study-media\/study:a\/original:a/);
  assert.equal(calls.filter(call=>call.action==='operator_study_record').length,0);
  assert.doesNotMatch(get('[data-study-view]').innerHTML,/data-study-evidence/);
});

test('manual mode cannot record assisted evidence or access another report before submission',async()=>{
  const {ui,calls,get}=panel();ui.attempt=attempt();ui.studyFrame=view().frame;
  await assert.rejects(ui.recordStudy('evidence_open'),/沒有可查看/);
  get('[data-study-history]').value='other';await assert.rejects(ui.openStudyReport(),/先提交/);
  assert.equal(calls.length,0);
});

test('late source view after disposal cannot restore media or assistance',async()=>{
  const pending=deferred(),{ui,get}=panel(action=>action==='operator_study_view'?pending.promise:undefined);
  ui.attempt=attempt('assisted');const loading=ui.viewStudy().catch(error=>error.message);ui.dispose();
  pending.resolve(view('assisted'));assert.equal(await loading,'SESSION_CHANGED');assert.equal(get('[data-study-view]').innerHTML,'');
});

test('assisted evidence opens only after a validated source view and records its exact issued references',async()=>{
  const {ui,get,calls}=panel(action=>action==='operator_study_view'?view('assisted'):
    action==='operator_study_record'?attempt('assisted'):undefined);ui.attempt=attempt('assisted');
  await assert.rejects(ui.recordStudy('correction'),/請先查看/);
  await ui.viewStudy();await ui.recordStudy('evidence_open');
  const record=calls.find(call=>call.action==='operator_study_record');
  assert.deepEqual(record.payload,{study_ref:'study:a',action:'evidence_open',evidence_ref:'evidence:a'});
  assert.match(get('[data-study-assistance]').innerHTML,/0、4、8/);
});

test('structured answer validation keeps UNKNOWN explicit and rejects invalid alternatives',()=>{
  for(const answer_type of ['timestamp','presence','count','order'])assert.deepEqual(validateStudyAnswer({...task,answer_type},{unknown:true}),{unknown:true});
  assert.deepEqual(validateStudyAnswer(task,{order:['B','A']}),{order:['B','A']});
  for(const answer of [{order:['A','A']},{order:['A','C']},{unknown:true,count:1}])assert.throws(()=>validateStudyAnswer(task,answer));
  assert.throws(()=>validateStudyAnswer({...task,answer_type:'timestamp'},{timestamp:9}));
  assert.throws(()=>validateStudyAnswer({...task,answer_type:'count'},{count:.5}));
  assert.throws(()=>validateStudyAnswer({...task,answer_type:'count'},{count:65}));
});

test('UNKNOWN submission displays its full denominator and does not export recovery credentials',async()=>{
  const {ui,get,calls}=panel(action=>action==='operator_study_submit'?{...attempt('manual','COMPLETED'),recovery_token:'never-export'}:undefined);
  ui.attempt=attempt();ui.manualStudyPending=true;get('[data-study-unknown]').checked=true;
  await ui.submitStudy();
  assert.deepEqual(calls.find(call=>call.action==='operator_study_submit').payload.answer,{unknown:true});
  const html=get('[data-study-report]').innerHTML;assert.match(html,/已完成分母/);assert.match(html,/未定答案/);
  assert.doesNotMatch(html,/never-export|recovery_token/);assert.equal(ui.manualStudyPending,false);
});

test('cross-session recovery uses explicit reference and credential but does not expose it in reports',async()=>{
  const {ui,get,calls}=panel(action=>action==='operator_study_resume'?attempt():undefined);
  get('[data-study-recovery-ref]').value='study:a';get('[data-study-recovery-input]').value='private-token';
  await ui.resumeStudy();
  assert.deepEqual(calls.find(call=>call.action==='operator_study_resume').payload,{study_ref:'study:a',recovery_token:'private-token'});
  assert.equal(ui.manualBlocked(),true);assert.equal(get('[data-study-recovery-input]').value,'');
  assert.doesNotMatch(get('[data-study-status]').innerHTML,/private-token/);
});

test('paired comparison retains incorrect/UNKNOWN/excluded denominators and refuses mismatched sources',()=>{
  const mode={attempt_count:5,completed_denominator:3,eligible_completed_denominator:2,correct_count:1,
    incorrect_count:1,unresolved_count:1,protocol_excluded_count:1,stopped_count:1,correct_duration_ms:[1000]};
  const comparison={same_binding:true,same_task:true,eligible_for_duration_comparison:true,modes:{manual:mode,assisted:mode}};
  assert.match(studyComparisonHTML(comparison),/3／2/);assert.match(studyComparisonHTML(comparison),/1／1／1/);
  assert.match(studyComparisonHTML(comparison),/1\.000/);assert.match(studyComparisonHTML(comparison),/學習效應尚未控制/);
  assert.doesNotMatch(studyComparisonHTML({...comparison,same_binding:false}),/<table/);
  const reportHTML=studyReportHTML({...attempt('manual','COMPLETED'),comparison,recovery_token:'credential'});
  assert.doesNotMatch(reportHTML,/credential|recovery_token/);
});

test('public timestamp task translation preserves the requested exact second without inferring an answer',()=>{
  const text=studyTaskPrompt({...task,family:'exact_registration_presence',prompt:'Does this camera have a frame at exactly 0.5 seconds?'});
  assert.match(text,/精確的 0\.5 秒/);assert.doesNotMatch(text,/PRESENT|MISSING/);
});

test('terminal recovery preserves completion, renders only issued original media, and keeps counters closed',async()=>{
  const completed={...attempt('manual','COMPLETED'),issued_frames:[view().frame]};
  const {ui,get,calls}=panel(action=>action==='operator_study_resume'?completed:undefined);
  get('[data-study-recovery-ref]').value='study:a';get('[data-study-recovery-input]').value='recovery-token';
  await ui.resumeStudy();
  assert.equal(ui.attempt.status,'COMPLETED');assert.equal(ui.manualBlocked(),false);
  assert.match(get('[data-study-view]').innerHTML,/\/study-media\/study:a\/original:a/);
  assert.match(get('[data-study-view]').innerHTML,/已查閱紀錄，唯讀/);
  assert.equal(get('[data-study-submit]').disabled,true);
  assert.equal(calls.some(call=>call.action==='operator_study_view'||call.action==='operator_study_record'),false);
  assert.doesNotMatch(get('[data-study-report]').innerHTML,/recovery-token/);
});

test('pending source context and late report replies cannot repopulate a disposed panel',async()=>{
  const pending=deferred(),{ui,get}=panel(action=>action==='operator_study_context'?pending.promise:undefined);
  ui.studyContext=null;const loading=ui.loadStudyContext().catch(error=>error.message);ui.dispose();
  pending.resolve(studyContext);assert.equal(await loading,'SESSION_CHANGED');assert.equal(ui.studyContext,null);
  assert.equal(get('[data-study-body]').innerHTML,'');
  const other=deferred(),second=panel(action=>action==='operator_study_report'?other.promise:undefined);
  const reporting=second.ui.loadStudyReport('study:a').catch(error=>error.message);second.ui.dispose();
  other.resolve(attempt('manual','COMPLETED'));assert.equal(await reporting,'SESSION_CHANGED');
  assert.equal(second.ui.studyReport,null);assert.equal(second.get('[data-study-report]').innerHTML,'');
});

test('changing a study input mode invalidates earlier source-only requests and clears old media',async()=>{
  const pending=deferred(),{ui,get}=panel(action=>action==='operator_study_context'?pending.promise:undefined);
  const loading=ui.loadStudyContext().catch(error=>error.message);
  get('[data-study-view]').innerHTML='OLD SOURCE';ui.changeStudyMode('assisted');pending.resolve(studyContext);
  assert.equal(await loading,'SESSION_CHANGED');assert.equal(get('[data-study-view]').innerHTML,'');
  assert.equal(ui.selectedStudyMode,'assisted');
});

test('invalid recovery credential releases run controls only after the ledger confirms no active manual',async()=>{
  const {ui,get,calls}=panel(action=>{if(action==='operator_study_resume')throw Error('STUDY_RECOVERY_DENIED');});
  get('[data-study-recovery-ref]').value='study:a';get('[data-study-recovery-input]').value='wrong-token';
  await assert.rejects(ui.resumeStudy(),/RECOVERY_DENIED/);
  assert.equal(ui.manualStudyPending,false);assert.equal(get('[data-run-start]').disabled,false);
  assert.equal(calls.at(-1).action,'operator_study_list');
});

test('known manual start rejection releases run controls after a clean ledger read',async()=>{
  const {ui,get}=panel(action=>{if(action==='operator_study_start')throw Error('STUDY_TASK_SCOPE_DENIED');});
  await assert.rejects(ui.startStudy(),/TASK_SCOPE_DENIED/);
  assert.equal(ui.manualStudyPending,false);assert.equal(get('[data-run-start]').disabled,false);
});

test('unknown start outcome remains run-blocked when the ledger contains an active manual or cannot be read',async()=>{
  for(const active of [true,false]){
    const {ui,get}=panel(action=>{
      if(action==='operator_study_start')throw Error('NETWORK_UNAVAILABLE');
      if(action==='operator_study_list'){
        if(!active)throw Error('LEDGER_UNAVAILABLE');
        return {items:[{study_ref:'study:new',mode:'manual',status:'RUNNING'}]};
      }
    });
    await assert.rejects(ui.startStudy(),/NETWORK_UNAVAILABLE/);
    assert.equal(ui.manualStudyPending,true);assert.equal(get('[data-run-start]').disabled,true);
  }
});

test('ordinary historical report restores issued photos without another view or counter mutation',async()=>{
  const report={...attempt('manual','COMPLETED'),issued_frames:[view().frame]};
  const {ui,get,calls}=panel(action=>action==='operator_study_report'?report:undefined);
  get('[data-study-history]').value='study:a';await ui.openStudyReport();
  assert.match(get('[data-study-view]').innerHTML,/\/study-media\/study:a\/original:a/);
  assert.equal(calls.filter(call=>call.action==='operator_study_view'||call.action==='operator_study_record').length,0);
});

test('the summary stays visible while all event/candidate details are collapsed and source photos are lazy',()=>{
  const value=result();value.events.push({...value.events[0],event_ref:'event:second'});
  const html=runComparisonHTML(value,ref=>'/source/'+ref);
  assert.match(html,/新 run 的 2 個事件與全部替代、來源影格/);
  assert.equal(html.slice(0,html.indexOf('<details')).includes('原凍結結果'),true);
  assert.doesNotMatch(html,/<details[^>]*\bopen\b/);
  assert.match(html,/loading="lazy"/);assert.match(html,/事件候選 1/);assert.match(html,/事件候選 2/);
});

test('manual start hides and settles in-flight source photos before creating the trial',async()=>{
  const {ui,get,calls,images,Element}=panel(action=>action==='operator_study_start'?attempt():undefined);
  const image=new Element();image.complete=false;image.loading='lazy';images.push(image);
  get('[data-run-comparison]').innerHTML='OPEN SOURCE';const starting=ui.startStudy();
  assert.equal(image.loading,'eager');assert.equal(get('[data-run-comparison]').hidden,true);
  await Promise.resolve();assert.equal(calls.some(call=>call.action==='operator_study_start'),false);
  image.emit('load');await starting;
  assert.equal(calls.some(call=>call.action==='operator_study_start'),true);
  assert.equal(ui.runImageRequests.size,0);assert.equal(get('[data-run-comparison]').innerHTML,'');
});

test('image-drain timeout creates no trial and a retry still waits for the old queued request to settle',async t=>{
  const timers=[];t.mock.method(globalThis,'setTimeout',callback=>{timers.push(callback);return timers.length;});
  t.mock.method(globalThis,'clearTimeout',()=>{});
  const {ui,calls,images,Element}=panel(action=>action==='operator_study_start'?attempt():undefined);
  const image=new Element();image.complete=false;images.push(image);
  const first=ui.startStudy().catch(error=>error.message);timers[0]();
  assert.match(await first,/本次任務尚未開始/);assert.equal(ui.manualStudyPending,false);
  assert.equal(calls.some(call=>call.action==='operator_study_start'),false);assert.equal(ui.runImageRequests.size,1);
  const retry=ui.startStudy();await Promise.resolve();
  assert.equal(calls.some(call=>call.action==='operator_study_start'),false);
  image.emit('error');await retry;assert.equal(ui.runImageRequests.size,0);
  assert.equal(calls.filter(call=>call.action==='operator_study_start').length,1);
});

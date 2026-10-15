import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {presentationData,presentationJSON,retainElements} from './presentation-data.mjs';
import {crossCameraSelection} from './app.mjs';
import {invalidateCrossCamera,runCrossCameraReconstruction,validateCrossCameraResponse,crossCameraRequestIsCurrent,crossCameraSegments,
  crossCameraVelocitySegments,crossCameraCursor,crossCameraScenePlan,crossCameraPanelHTML,crossCameraCandidateHTML,
  selectedCrossCameraCandidate,availableCrossCameraArtifacts,crossCameraArtifactsHTML,crossCameraPresentation,
  sourceTimeForCrossCameraVideo,bindCrossCameraMedia,updateCrossCameraCursor,selectedPhysicalCandidate,physicalScenePlan,physicalGeometryPlan,invalidatePhysicalCrossCamera,runPhysicalReconstruction,validatePhysicalResponse,physicalPanelHTML,physicalCandidateHTML,availablePhysicalArtifacts,physicalArtifactsHTML,physicalRequestIsCurrent,physicalLedgerHTML,
  groundContactBasis,groundContactLabel,cameraShortLabel,candidateEvidenceOverlays,candidateEvidenceSVG} from './cross-camera.mjs';
const selection={camera_ids:['CAM_A','CAM_B'],start:2,end:4,top_k:3};
const snapshot={source_binding:{run_id:'run-A',source_sha256:'source-A'},baseline:{source_features:'pixel-A'},
  capabilities:{frame_query:true},time_range:[0,9.8],cameras:[{camera_id:'CAM_A'},{camera_id:'CAM_B'}]};
const target=()=>({role:'research',sceneEpoch:1,sceneId:'blender-office',session:{session_ref:'session-A'},crossCameraEpoch:0,snapshot});
const projected=(timestamp,world_position,connect=true)=>({timestamp,world_position,state:'PROJECTED_OBSERVATION',camera_id:'CAM_A',connect_from_previous:connect});
const path=()=>({path_ref:'path:PRIVATE',camera_ids:['CAM_A','CAM_B'],canonical_time_range:[0,9.8],node_refs:['node:A','node:B'],edge_refs:['edge:AB'],identity_verdict:'UNCONFIRMED',behavior_verdict:'UNKNOWN',samples:[projected(2,[0,0,.5],false),projected(2.2,[1,0,.5])],velocities:[],gaps:[]});
const candidate=rank=>({rank,candidate_ref:'candidate:PRIVATE'+rank,score:1/rank,selected_edge_refs:['edge:AB'],unassociated_node_refs:['node:C'],paths:[path()]});
const response=()=>({schema_version:'workbench.blender-association.v1',status:'READY',agent_used:false,formal_acceptance:false,
  source_binding:structuredClone(snapshot.source_binding),source_features:'pixel-A',selection:{camera_ids:[...selection.camera_ids],time_range:[2,4],top_k:3},
  candidates:[candidate(1),candidate(2),candidate(3)],baseline_candidate:{selected_edge_refs:[],unassociated_node_refs:['node:A','node:B'],score:0,paths:[path()]},graph:{nodes:[],edges:[]},camera_coverage:[]});

test('cross-camera selection uses exact selected cameras, time and K without granting behavior or search timestamp authority',()=>{
  const values={camera_ids:['CAM_B','CAM_A'],start:'2',end:'4',top_k:'3',target_timestamp:'INVALID',behavior_intent:'UNKNOWN'};
  assert.deepEqual(crossCameraSelection(values,snapshot),{camera_ids:['CAM_B','CAM_A'],start:2,end:4,top_k:3});
  for(const change of [{top_k:''},{top_k:0},{top_k:6},{top_k:1.5},{camera_ids:['OTHER']},{end:10},{start:''}])assert.throws(()=>crossCameraSelection({...values,...change},snapshot));
});

test('candidate request commits only a source-bound scope and sends no Agent or semantics payload',async()=>{
  const state=target(),requests=[];
  assert.equal(await runCrossCameraReconstruction(state,selection,async request=>{requests.push(request);return response();}),true);
  assert.deepEqual(requests,[{scene_id:'blender-office',camera_ids:['CAM_A','CAM_B'],start:2,end:4,top_k:3}]);
  assert.equal(state.crossCameraRank,1);assert.equal(state.crossCameraPending,false);
  for(const change of [{agent_used:true},{schema_version:'old'},{status:'UNKNOWN'},{source_features:'old'},
    {source_binding:{run_id:'run-B',source_sha256:'source-A'}},{source_binding:{run_id:'run-A',source_sha256:'source-B'}},
    {selection:{...selection,time_range:[0,9.8]}},{selection:{camera_ids:['CAM_A'],time_range:[2,4],top_k:3}},
    {selection:{camera_ids:['CAM_A','CAM_B'],time_range:[2,4],top_k:5}},
    {candidates:[{...candidate(1),paths:[{...path(),camera_ids:['OTHER']}]}]},
    {baseline_candidate:{paths:[{...path(),samples:[{...projected(2,[1,1,.5]),camera_id:'OTHER'}]}]}},
    {graph:{nodes:[{camera_id:'OTHER'}]}}])assert.throws(()=>validateCrossCameraResponse({...response(),...change},selection,snapshot));
});

test('unsaved edits and late success or failure cannot overwrite a newer candidate request',async()=>{
  const state=target(),promises=[];
  const old=runCrossCameraReconstruction(state,selection,()=>new Promise(resolve=>promises.push(resolve)));
  invalidateCrossCamera(state);
  const next=runCrossCameraReconstruction(state,selection,()=>new Promise(resolve=>promises.push(resolve)));
  promises[1]({...response(),summary:{generation:'new'}});assert.equal(await next,true);
  promises[0]({...response(),summary:{generation:'old'}});assert.equal(await old,false);assert.equal(state.crossCameraResult.summary.generation,'new');
  let reject;const pending=runCrossCameraReconstruction(state,selection,()=>new Promise((_,fail)=>{reject=fail;}));
  invalidateCrossCamera(state);reject(Error('late old error'));assert.equal(await pending,false);assert.equal(state.crossCameraResult,null);
});

test('late scene, role and session replies cannot revive old candidates or videos',async()=>{
  for(const mutate of [state=>state.sceneEpoch++,state=>state.sceneId='blender-auditorium',state=>state.role='management',state=>state.session={session_ref:'session-B'}]){
    const state=target();let resolve;
    const pending=runCrossCameraReconstruction(state,selection,()=>new Promise(done=>{resolve=done;}));
    mutate(state);resolve(response());assert.equal(await pending,false);assert.equal(state.crossCameraResult,null);
  }
});

test('explicit projected segments remain solid, inferred samples dashed, missing gaps never become position paths',()=>{
  const samples=[projected(2,[0,0,.5],false),projected(2.2,[1,0,.5]),{...projected(2.4,[2,0,.5]),state:'INFERRED_CROSS_CAMERA',camera_id:null},
    {timestamp:2.6,world_position:null,state:'MISSING'},projected(3.4,[3,0,.5]),projected(3.6,[4,0,.5],false),projected(3.8,[5,0,.5])];
  assert.deepEqual(crossCameraSegments(samples,[2,4]).map(segment=>[segment.from.timestamp,segment.to.timestamp,segment.inferred]),[[2,2.2,false],[2.2,2.4,true],[3.6,3.8,false]]);
  const result=response();result.candidates[0].paths[0].samples=samples;result.candidates[0].paths[0].gaps=[{time_range:[2.6,3.4],reason:'CROSS_CAMERA_LONG_GAP'}];
  const html=crossCameraCandidateHTML(result);assert.match(html,/stroke-dasharray/);assert.match(html,/中間位置缺失/);
  assert.equal(crossCameraCursor({samples},2.6,[2,4]),null);assert.equal(crossCameraCursor({samples},3,[2,4]),null);
  assert.equal(crossCameraCursor({samples},2.4,[2,4]).state,'INFERRED_CROSS_CAMERA');
  assert.equal(crossCameraCursor({samples},4.1,[2,4]),null);assert.equal(crossCameraCursor({samples},1.9,[2,4]),null);
});

test('speed curves accept explicit cross-camera finite differences but break unrelated windows and invalid values',()=>{
  const velocity=(timestamp,time_range,speed_m_s,state='INFERRED_FINITE_DIFFERENCE')=>({timestamp,time_range,speed_m_s,velocity_xyz:[speed_m_s,0,0],state});
  const rows=[velocity(2.1,[2,2.2],1),velocity(2.3,[2.2,2.4],2,'INFERRED_CROSS_CAMERA'),velocity(3.5,[3.4,3.6],3),velocity(3.7,[3.6,3.8],4)];
  assert.deepEqual(crossCameraVelocitySegments(rows,[2,4]).map(segment=>[segment.from.timestamp,segment.to.timestamp]),[[2.1,2.3],[3.5,3.7]]);
  assert.deepEqual(crossCameraVelocitySegments([rows[0],{...rows[1],speed_m_s:Infinity}],[2,4]),[]);
});

test('3D plans preserve every ranked alternative and metres; long missing associations stay distinct from trajectories',()=>{
  const result=response();result.graph.edges=[{edge_ref:'edge:AB',bridge_missing:true,from_timestamp:2.2,to_timestamp:3.8,from_world_position:[1,2,.5],to_world_position:[3,4,.5]}];
  const plan=crossCameraScenePlan(result,2);assert.equal(plan.paths.length,3);assert.equal(plan.paths.filter(row=>row.selected).length,1);
  assert.deepEqual(plan.paths[0].segments[0].to.world_position,[1,0,.5]);assert.equal(plan.paths[0].missingAssociations[0].caption,'關聯假設／中間位置缺失');
  assert.deepEqual(plan.paths[0].missingAssociations[0].from,[1,2,.5]);
  const baseline=crossCameraScenePlan(result,0);assert.equal(baseline.selected_rank,0);assert.equal(baseline.paths.length,4);assert.match(baseline.paths[3].caption,/未關聯基線/);
  const narrow={...result,selection:{...result.selection,time_range:[3,4]}};assert.deepEqual(crossCameraScenePlan(narrow).paths[0].missingAssociations,[]);
});

test('candidate privacy removes nested internal refs and escapes HTML without mutating canonical data',()=>{
  const result=response();result.candidates[0].paths[0].samples[0].uncertainty={note:'<script>alert(1)</script>',node_ref:'node:PRIVATE',event_ref:'event:PRIVATE',extra:'related node:PRIVATE'};
  result.policy={edge_ref:'edge:AB',note:'edge:AB and track:PRIVATE'};
  const original=structuredClone(result),html=crossCameraPanelHTML(result,{cameraLabel:()=>'<Camera>'});
  assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;Camera&gt;/);assert.match(html,/身分未確認/);assert.match(html,/未關聯基線/);
  assert.doesNotMatch(html,/node:PRIVATE|track:PRIVATE|candidate:PRIVATE|path:PRIVATE|edge:AB|event:PRIVATE|<script>/);
  assert.deepEqual(result,original);assert.deepEqual(crossCameraPresentation({nested:{candidate_ref:'candidate:A',note:'candidate:A'}}),{nested:{note:'內部識別碼（見 log）'}});
});

test('one unassociated result and absent corridor projection remain explicit instead of fabricated Top-K',()=>{
  const result=response();result.status='NO_CROSS_CAMERA_EVIDENCE';result.candidates=[{...candidate(1),selected_edge_refs:[]}];
  result.camera_coverage=[{camera_id:'CAM_B',time_range:[2,4],source_frame_count:11,pixel_observation_count:0,projected_frame_count:0,missing_projected_frame_count:11,state:'MISSING'}];
  const html=crossCameraPanelHTML(result);assert.match(html,/請求 3 解／實得 1 解/);assert.match(html,/沒有通過限制的跨鏡頭連線/);assert.match(html,/0 個可能跨鏡頭關聯/);assert.match(html,/MISSING/);
  assert.match(html,/沒有像素追蹤或 3D 投影；不由其他鏡頭補值/);
  assert.equal(selectedCrossCameraCandidate(result,0).rank,0);
  const missing={...response(),status:'NO_RESULT',candidates:[]};assert.equal(crossCameraScenePlan(missing).paths.length,0);assert.match(crossCameraPanelHTML(missing),/沒有可還原候選/);
});

test('full materialized movie describes its own camera/time/K while preserving a narrow differently ranked query',()=>{
  const result={...response(),selection:{camera_ids:['CAM_A'],time_range:[2,4],top_k:1},artifacts:{status:'AVAILABLE',selection:{camera_ids:['CAM_A','CAM_B'],time_range:[0,9.8],top_k:3},items:[
    {kind:'RECONSTRUCTION_VIDEO',media_ref:'cross-camera-media:ABC',mime_type:'video/mp4',time_range:[0,9.8]},
    {kind:'POSITION_VELOCITY_CURVES',media_ref:'cross-camera-media:DEF',mime_type:'image/png',time_range:[0,9.8]},
    {kind:'RECONSTRUCTION_VIDEO',media_ref:'/private/raw.mp4',mime_type:'video/mp4',time_range:[0,9.8]},
  ]}};
  assert.equal(availableCrossCameraArtifacts(result).length,2);
  const html=crossCameraArtifactsHTML(result,{urlFor:ref=>'/api/cross_camera_media?ref='+encodeURIComponent(ref)});
  assert.match(html,/素材鏡頭：CAM_A、CAM_B · 素材 Top-K 3/);assert.match(html,/本次查詢鏡頭：CAM_A · 範圍 2\.0 s–4\.0 s · 請求 Top-K 1/);
  assert.match(html,/影片顯示全部素材候選/);assert.match(html,/素材未依本次鏡頭、時間窗或 K 重新產生/);assert.doesNotMatch(html,/\/private\//);
  assert.match(crossCameraArtifactsHTML({...result,artifacts:{status:'UNAVAILABLE'}}),/尚未物化或來源不相符/);
});

test('live video seeks synchronize curve cursor and source clock, throttling only image fetches; disposal revokes callbacks',()=>{
  const handlers=new Map(),sync={checked:true},clock={textContent:''},sourceClock={textContent:''},attributes={},cursor={setAttribute:(name,value)=>{attributes[name]=value;}};
  const svg={dataset:{timeStart:'2',timeEnd:'4',chartLeft:'58',chartRight:'624'},querySelector:()=>cursor};let live=true;
  const video={dataset:{timeStart:'0',timeEnd:'9.8'},currentTime:2.2,isConnected:true,
    closest:()=>({querySelector:selector=>selector==='[data-cross-camera-sync]'?sync:clock}),
    addEventListener:(name,callback)=>handlers.set(name,callback),removeEventListener:name=>handlers.delete(name),
    pause(){this.paused=true;},removeAttribute(name){this.removed=name;},load(){this.loaded=true;}};
  const container={querySelector:()=>sourceClock,querySelectorAll:selector=>selector==='[data-cross-camera-video]'?[video]:[svg]},calls=[];
  const dispose=bindCrossCameraMedia(container,{current:()=>live,onSourceTime:(time,options)=>calls.push({time,...options})});
  handlers.get('seeked')();assert.deepEqual(calls,[{time:2.2,fetchImages:true}]);assert.equal(attributes.opacity,'1');assert.match(sourceClock.textContent,/2\.2 s/);
  video.currentTime=2.25;handlers.get('timeupdate')();assert.deepEqual(calls[1],{time:2.25,fetchImages:false});
  live=false;video.currentTime=3;handlers.get('seeked')();assert.equal(calls.length,2);
  live=true;sync.checked=false;handlers.get('seeked')();assert.equal(calls.length,2);
  updateCrossCameraCursor(container,5);assert.equal(attributes.opacity,'0');
  assert.equal(sourceTimeForCrossCameraVideo({...video,currentTime:10}),9.8);assert.equal(sourceTimeForCrossCameraVideo({...video,dataset:{}}),null);
  dispose();assert.equal(handlers.size,0);assert.equal(video.paused,true);assert.equal(video.removed,'src');assert.equal(video.loaded,true);
});

test('routine DOM refresh retains exact source renderer, decoded image and cross-camera video panel',()=>{
  const canvas={},image={},video={},old={'.source-stage':{canvas},'details.source-evidence':{image},'.cross-camera-panel':{video}};let nodes={...old};
  const root={querySelector:selector=>nodes[selector],set innerHTML(_){nodes=Object.fromEntries(Object.keys(old).map(key=>[key,{replaceWith:node=>{nodes[key]=node;}}]));}};
  retainElements(root,'surrounding controls',Object.keys(old));assert.equal(nodes['.source-stage'].canvas,canvas);assert.equal(nodes['details.source-evidence'].image,image);assert.equal(nodes['.cross-camera-panel'].video,video);
});

test('candidate rank switches update only curves and 3D overlay, preserving the exact playing movie and model view',()=>{
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const candidateNode={innerHTML:''},clock={textContent:''},badge={textContent:''},movie={},viewCalls=[];
  const panel={video:movie,querySelector:selector=>selector==='[data-cross-camera-candidate]'?candidateNode:selector==='[data-cross-camera-clock]'?clock:null,querySelectorAll:()=>[]};
  const document={querySelector:selector=>selector==='.cross-camera-panel'?panel:selector==='.viewport-overlay .cross-camera-badge'?badge:null,querySelectorAll:()=>[],addEventListener(){}};
  const environment={presentationData,presentationJSON,crossCameraCandidateHTML,crossCameraScenePlan,selectedCrossCameraCandidate,updateCrossCameraCursor,selectedPhysicalCandidate,physicalScenePlan,physicalGeometryPlan,invalidatePhysicalCrossCamera,runPhysicalReconstruction,validatePhysicalResponse,physicalPanelHTML,physicalCandidateHTML,availablePhysicalArtifacts,physicalArtifactsHTML,physicalRequestIsCurrent,physicalLedgerHTML};
  // Avoid bootstrap; attach only the explicit selectors needed by a rank change.
  runInNewContext(source+'\nglobalThis.api={state,selectCrossCameraRank};',environment);environment.document=document;
  const {state,selectCrossCameraRank}=environment.api;Object.assign(state,{crossCameraResult:response(),crossCameraRank:1,timestamp:2.2,snapshot,
    view:{setCrossCamera:plan=>viewCalls.push(plan),setTimestamp:timestamp=>viewCalls.push(timestamp)}});
  selectCrossCameraRank(2);assert.equal(state.crossCameraRank,2);assert.match(candidateNode.innerHTML,/候選 2/);assert.equal(panel.video,movie);assert.equal(viewCalls[0].selected_rank,2);assert.equal(viewCalls[1],2.2);
  selectCrossCameraRank(0);assert.equal(state.crossCameraRank,0);assert.match(candidateNode.innerHTML,/未關聯基線/);assert.equal(panel.video,movie);
  selectCrossCameraRank(99);assert.equal(state.crossCameraRank,0);
});

test('original speed/projection gaps and bounded incomplete search remain visible in ranked and unassociated views',()=>{
  const result=response();result.search={truncated:true,complete:false,canonical_search_scope:'SELECTED_CAMERAS_FULL_SOURCE_TIME'};
  const gaps=[{time_range:[2.4,2.6],reason:'SPEED_CAP',camera_id:'CAM_A'},{time_range:[3,3.2],reason:'INVALID_PROJECTION',camera_id:'CAM_B'}];
  result.candidates[0].unresolved_local_gaps=gaps;result.baseline_candidate.unresolved_local_gaps=gaps;
  const html=crossCameraPanelHTML(result);assert.match(html,/候選搜尋在設定上限停止/);assert.match(html,/完整來源時間；本次時間窗只切曲線/);
  assert.match(html,/原局部追蹤的未解缺口/);assert.match(html,/2\.4 s–2\.6 s · 超過設定速度限制/);assert.match(html,/3\.0 s–3\.2 s · 投影缺失/);
  assert.match(crossCameraCandidateHTML(result,0),/不因片段分拆而移除/);
  assert.throws(()=>validateCrossCameraResponse({...result,candidates:[{...candidate(1),paths:[{...path(),samples:[projected(1,[0,0,.5])]}]}]},selection,snapshot));
});

test('curve clock distinguishes measured projection, inferred point and missing time; wrong-source media remain unavailable',()=>{
  const clock={dataset:{crossCameraPathClock:'0'},textContent:''},container={querySelector:()=>null,querySelectorAll:selector=>selector==='[data-cross-camera-path-clock]'?[clock]:[]};
  const chosen={display_time_range:[2,4],paths:[{samples:[projected(2,[1,2,.5],false),{...projected(2.2,[2,2,.5]),state:'INFERRED_CROSS_CAMERA'},
    {timestamp:2.4,state:'MISSING',world_position:null}]}]};
  updateCrossCameraCursor(container,2,chosen);assert.match(clock.textContent,/觀測像素衍生投影/);
  updateCrossCameraCursor(container,2.2,chosen);assert.match(clock.textContent,/推斷：跨鏡頭位置假設/);
  updateCrossCameraCursor(container,2.4,chosen);assert.match(clock.textContent,/MISSING/);
  updateCrossCameraCursor(container,1.9,chosen);assert.match(clock.textContent,/不延伸上一個點/);
  const result=response();result.artifacts={status:'AVAILABLE',source_binding:{run_id:'OTHER',source_sha256:'source-A'},items:[{kind:'CROSS_CAMERA_RECONSTRUCTION_VIDEO',mime_type:'video/mp4',media_ref:'cross-media:ABC',time_range:[0,9.8]}]};
  assert.deepEqual(availableCrossCameraArtifacts(result),[]);
  result.artifacts.source_binding=result.source_binding;result.artifacts.source_features='OLD';assert.deepEqual(availableCrossCameraArtifacts(result),[]);
  result.artifacts.source_features='pixel-A';assert.equal(availableCrossCameraArtifacts(result).length,1);
});

test('source timeline Play takes back video clock control, pauses the movie and advances RGB, 3D and curves together',async()=>{
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const timers=new Map(),videoHandlers=new Map(),attributes={},drawTimes=[];let nextTimer=0;
  const sourceClock={textContent:''},videoClock={textContent:''},timelineLabel={textContent:''},timelineRange={value:0},toastNode={textContent:'',classList:{add(){},remove(){}}};
  const curveCursor={setAttribute:(name,value)=>{attributes[name]=value;}},svg={dataset:{timeStart:'2',timeEnd:'4',chartLeft:'58',chartRight:'624'},querySelector:()=>curveCursor};
  const video={dataset:{timeStart:'0',timeEnd:'9.8'},isConnected:true,currentTime:3,paused:false,pauseCalls:0,
    closest:()=>({querySelector:selector=>selector==='[data-cross-camera-sync]'?{checked:true}:videoClock}),
    addEventListener:(name,handler)=>videoHandlers.set(name,handler),removeEventListener:name=>videoHandlers.delete(name),
    pause(){this.paused=true;this.pauseCalls++;},removeAttribute(){},load(){}};
  const panel={isConnected:true,querySelector:selector=>selector==='[data-cross-camera-clock]'?sourceClock:selector==='[data-cross-camera-video]'?video:null,
    querySelectorAll:selector=>selector==='[data-cross-camera-video]'?[video]:selector==='[data-cross-camera-chart]'?[svg]:[]};
  const document={querySelector:selector=>selector==='.cross-camera-panel'?panel:selector==='#timeline-range'?timelineRange:selector==='[data-current-time]'?timelineLabel:selector==='#toast'?toastNode:null,
    querySelectorAll:selector=>selector==='[data-cross-camera-video]'?[video]:[],addEventListener(){}};
  const environment={presentationData,presentationJSON,crossCameraCandidateHTML,crossCameraScenePlan,selectedCrossCameraCandidate,updateCrossCameraCursor,bindCrossCameraMedia,crossCameraRequestIsCurrent,selectedPhysicalCandidate,physicalScenePlan,physicalGeometryPlan,
    prepareFrames:async()=>true,fetch:async()=>({ok:true,json:async()=>({frames:[]})}),
    setTimeout:(callback)=>{const id=++nextTimer;timers.set(id,callback);return id;},clearTimeout:id=>timers.delete(id)};
  runInNewContext(source+'\nglobalThis.testControls={state,mountCrossCameraMedia,togglePlayback};',environment);environment.document=document;
  const {state,mountCrossCameraMedia,togglePlayback}=environment.testControls;
  Object.assign(state,{role:'research',sceneId:'blender-office',sceneEpoch:1,crossCameraEpoch:1,crossCameraRank:1,
    session:{session_ref:'session-A'},snapshot,cameraIds:['CAM_A','CAM_B'],timestamp:3,crossCameraResult:response(),
    view:{setTimestamp:timestamp=>drawTimes.push(timestamp)}});
  mountCrossCameraMedia();videoHandlers.get('seeked')();assert.equal(state.crossCameraTimestamp,3);
  await togglePlayback();
  assert.equal(state.crossCameraTimestamp,null);assert.equal(video.paused,true);assert.equal(video.pauseCalls,1);
  // Browsers can queue a final timeupdate when pause() runs. It must not reclaim the movie clock.
  const sourceTimer=state.playTimer;videoHandlers.get('timeupdate')();assert.equal(state.playTimer,sourceTimer);assert.equal(state.crossCameraTimestamp,null);
  await timers.get(sourceTimer)();
  assert.equal(toastNode.textContent,'');
  assert.equal(state.timestamp,3.2);assert.equal(drawTimes.at(-1),3.2);assert.equal(Number(timelineRange.value),3.2);
  assert.match(timelineLabel.textContent,/3\.2 s/);assert.match(sourceClock.textContent,/3\.2 s/);
  assert.equal(Number(attributes.x1),58+(3.2-2)/2*(624-58));
  const pauseCalls=video.pauseCalls;await togglePlayback();assert.equal(state.playTimer,null);assert.equal(video.pauseCalls,pauseCalls);
  // A fresh movie play can take control again after the source playback is stopped.
  video.paused=false;video.currentTime=3.8;videoHandlers.get('timeupdate')();assert.equal(state.crossCameraTimestamp,3.8);assert.equal(drawTimes.at(-1),3.8);
  state.crossCameraDispose();
});

const physicalDecision=(verdict='UNKNOWN')=>({verdict,reasons:verdict==='REJECTED'?[{code:'KNOWN_COMPONENT_COLLISION',status:'REJECTED',time_range:[2,2.2],geometry_ref:'geometry:PRIVATE',authority:'APPROVED'}]:[],
  unknowns:verdict==='UNKNOWN'?[{code:'WHOLE_SCENE_BODY_CLEARANCE_UNKNOWN',status:'UNKNOWN',time_range:[2,4],authority:'PARTIAL_SOURCE_AUTHORITY'}]:[],
  checks:[{code:'APPROVED_SOURCE_SUPPORT',status:'SUPPORTED_LOCAL_ONLY',time_range:[2,2.2],authority:'APPROVED',occurrence_count:2}],
  scores:{base_compatibility:1,support_evidence_bonus:.02,missing_position_penalty:.1,ranking_score:.92},evidence_counts:{known_collision_rejections:verdict==='REJECTED'?1:0},complete_physical_validation:false});
const physicalResponse=()=>({...response(),schema_version:'workbench.blender-physical.v1',base_association_sha256:'a'.repeat(64),physical_sha256:'b'.repeat(64),
  candidates:[{...candidate(1),original_rank:3,score:.92,physical:physicalDecision()}],rejected_candidates:[],
  baseline_candidate:{...response().baseline_candidate,physical:physicalDecision()},authority_coverage:{physical_complete:false,known_collider_component_count:58},
  geometry_context:{units:'METRES',source_sha256:'source-A',physical_source_sha256:'c'.repeat(64),support_polygons:[],colliders:[],portals:{approved_apertures:0,status:'UNKNOWN'}},
  evidence_hashes:{physical_source:'c'.repeat(64)},search:{pool_budget:256,considered:10,retained:10,rejected:0,unknown:10,complete:false,truncated:true}});

test('physical requests keep baseline results separate, enforce exact source and scope, and never turn UNKNOWN into PASS',async()=>{
  const state={...target(),physicalEpoch:0,crossCameraResult:response()},requests=[];
  assert.equal(await runPhysicalReconstruction(state,selection,async request=>{requests.push(request);return physicalResponse();}),true);
  assert.deepEqual(requests,[{scene_id:'blender-office',camera_ids:['CAM_A','CAM_B'],start:2,end:4,top_k:3}]);
  assert.equal(state.physicalResult.candidates[0].physical.verdict,'UNKNOWN');assert.equal(state.crossCameraResult.schema_version,'workbench.blender-association.v1');
  for(const change of [{schema_version:'workbench.blender-association.v1'},{status:'CERTIFIED'}, {physical_sha256:'BAD'},
    {base_association_sha256:'BAD'},{agent_used:true},{source_features:'WRONG'},
    {source_binding:{run_id:'WRONG',source_sha256:'source-A'}},
    {selection:{...physicalResponse().selection,time_range:[0,9.8]}},
    {candidates:[{...candidate(1),physical:physicalDecision('REJECTED')}]},
    {rejected_candidates:[{...candidate(1),physical:physicalDecision('UNKNOWN')}]},
    {rejected_candidates:[{...candidate(1),physical:physicalDecision('REJECTED'),paths:[{...path(),camera_ids:['WRONG']}]}]},
    {baseline_candidate:{...response().baseline_candidate,physical:{verdict:'PASS'}}},
  ])assert.throws(()=>validatePhysicalResponse({...physicalResponse(),...change},selection,snapshot));
});

test('physical late replies, input invalidation, role and session switches cannot revive old geometry or video',async()=>{
  for(const mutate of [state=>invalidatePhysicalCrossCamera(state),state=>state.sceneEpoch++,state=>state.sceneId='OTHER',state=>state.role='management',state=>state.session={session_ref:'new'}]){
    const state={...target(),physicalEpoch:0};let resolve;
    const pending=runPhysicalReconstruction(state,selection,()=>new Promise(done=>{resolve=done;}));mutate(state);resolve(physicalResponse());
    assert.equal(await pending,false);assert.equal(state.physicalResult,null);
  }
  const state={...target(),physicalEpoch:0};let reject;
  const pending=runPhysicalReconstruction(state,selection,()=>new Promise((_,fail)=>{reject=fail;}));invalidatePhysicalCrossCamera(state);reject(Error('late failure'));
  assert.equal(await pending,false);assert.equal(state.physicalPending,false);
});

test('physical accepted, rejected and independent baseline choices preserve original source samples and explicit verdicts',()=>{
  const result=physicalResponse();result.rejected_candidates=[{...candidate(2),rejection_rank:1,physical:physicalDecision('REJECTED')}];
  const original=structuredClone(result);
  assert.equal(selectedPhysicalCandidate(result,'accepted:1').physical.verdict,'UNKNOWN');
  assert.equal(selectedPhysicalCandidate(result,'rejected:1').physical.verdict,'REJECTED');
  assert.equal(selectedPhysicalCandidate(result,'baseline').rank,0);
  const rejected=physicalScenePlan(result,'rejected:1');assert.equal(rejected.paths.filter(row=>row.selected).length,1);
  assert.equal(rejected.paths.find(row=>row.selected).color,'#ef9da7');assert.match(rejected.paths.find(row=>row.selected).caption,/拒絕解/);
  assert.deepEqual(rejected.paths.find(row=>row.selected).segments[0].to.world_position,[1,0,.5]);
  const html=physicalCandidateHTML(result,'rejected:1');assert.match(html,/已拒絕：僅供核對/);assert.match(html,/未當作保留路線/);assert.match(html,/KNOWN_COMPONENT_COLLISION/);
  const baseline=physicalCandidateHTML(result,'baseline');assert.match(baseline,/未關聯基線（排序外）/);assert.match(baseline,/未知保留/);
  assert.doesNotMatch(html,/geometry:PRIVATE|candidate:PRIVATE|path:PRIVATE|edge:AB/);assert.deepEqual(result,original);
});

test('actual zero rejected candidates stay zero; known component counts never imply collision-free doors or corridors',()=>{
  const result=physicalResponse(),html=physicalPanelHTML(result);
  assert.match(html,/保留 1 解／可核對拒絕 0 解/);assert.match(html,/已批准門洞 0/);assert.match(html,/已知碰撞組件 58/);
  assert.match(html,/0 已知碰撞不等於可通行證明/);assert.match(html,/來源完整碰撞驗證：未完成/);assert.match(html,/全場身體通行淨空未知/);
  assert.match(html,/已支持的局部檢查（不是全場通行證明）/);assert.match(html,/來源檢查 2 次/);
  assert.doesNotMatch(html,/<option value="rejected:/);
  const supported=physicalCandidateHTML({...result,candidates:[{...result.candidates[0],physical:physicalDecision('SUPPORTED_LOCAL_ONLY')}]});
  assert.match(supported,/僅支持已檢查的局部範圍/);assert.match(supported,/支持限於列出的來源局部檢查/);
});

test('approved metre support outlines require exact source authority, preserve holes, and never synthesize doors or colliders',()=>{
  const result=physicalResponse(),polygon={authority:'APPROVED',role:'SOURCE_SUPPORTED_WALKABLE_ONLY',exterior:[[1,2,.5],[3,2,.5],[3,4,.5]],holes:[[[1.5,2.5,.5],[2,2.5,.5],[2,3,.5]]]};
  result.geometry_context.support_polygons=[polygon];const original=structuredClone(result);
  const plan=physicalGeometryPlan(result);assert.equal(plan.polygons.length,1);assert.deepEqual(plan.polygons[0].exterior,polygon.exterior);assert.deepEqual(plan.polygons[0].holes,polygon.holes);
  assert.equal(plan.polygons[0].complete_collision_validation,false);assert.equal('colliders' in plan,false);assert.equal('portals' in plan,false);
  for(const change of [{units:'BLENDER_UNITS'},{source_sha256:'WRONG'}, {physical_source_sha256:null},
    {support_polygons:[{...polygon,authority:'HUMAN_REVIEW'}]},{support_polygons:[{...polygon,role:'DISPLAY_ONLY'}]},
    {support_polygons:[{...polygon,exterior:[[1,2,.5],[3,2,.5],[NaN,4,.5]]}]},
    {support_polygons:[{...polygon,holes:[[[1,1,1]]]}]},
  ])assert.equal(physicalGeometryPlan({...result,geometry_context:{...result.geometry_context,...change}}).polygons.length,0);
  assert.deepEqual(result,original);
});

test('all rejected candidates retain inspectable curves while producing no fabricated retained path',async()=>{
  const result=physicalResponse();result.status='ALL_CANDIDATES_REJECTED';result.rejected_candidates=[{...result.candidates[0],physical:physicalDecision('REJECTED'),rejection_rank:1}];result.candidates=[];
  const state={...target(),physicalEpoch:0};assert.equal(await runPhysicalReconstruction(state,selection,async()=>result),true);assert.equal(state.physicalChoice,'rejected:1');
  const html=physicalPanelHTML(result,{choice:state.physicalChoice});assert.match(html,/保留 0 解／可核對拒絕 1 解/);assert.match(html,/只供核對/);
  assert.equal(physicalScenePlan(result,'rejected:1').paths.filter(row=>row.selected).length,1);
  const absent={...physicalResponse(),status:'NO_RESULT',candidates:[],rejected_candidates:[],baseline_candidate:null};
  assert.equal(physicalScenePlan(absent).paths.length,0);assert.match(physicalPanelHTML(absent),/沒有可檢視的物理候選/);
});

test('physical materialized media has independent ref/hash scope and describes full movie camera/time/K separately from query',()=>{
  const result=physicalResponse();result.selection={camera_ids:['CAM_A'],time_range:[2,4],top_k:1};
  result.artifacts={status:'AVAILABLE',source_binding:result.source_binding,source_features:result.source_features,physical_sha256:result.physical_sha256,
    selection:{camera_ids:['CAM_A','CAM_B'],time_range:[0,9.8],top_k:3},items:[{kind:'PHYSICAL_CROSS_CAMERA_VIDEO',mime_type:'video/mp4',media_ref:'physical-media:'+'a'.repeat(24),time_range:[0,9.8]},
      {kind:'PHYSICAL_POSITION_VELOCITY_CURVES',mime_type:'image/png',media_ref:'physical-media:'+'b'.repeat(24),time_range:[0,9.8]}]};
  assert.equal(availablePhysicalArtifacts(result).length,2);const html=physicalArtifactsHTML(result,{urlFor:ref=>'/api/physical_cross_camera_media?ref='+encodeURIComponent(ref)});
  assert.match(html,/素材鏡頭：CAM_A、CAM_B · 素材 Top-K 3/);assert.match(html,/查詢鏡頭：CAM_A · 2\.0 s–4\.0 s · 請求 Top-K 1/);
  assert.match(html,/不會隨工作台選取的候選或拒絕解重新產生/);assert.match(html,/data-physical-video/);
  for(const change of [{physical_sha256:'WRONG'},{source_features:'OLD'}, {source_binding:{run_id:'WRONG',source_sha256:'source-A'}}, {status:'UNAVAILABLE'}])
    assert.equal(availablePhysicalArtifacts({...result,artifacts:{...result.artifacts,...change}}).length,0);
  assert.equal(availablePhysicalArtifacts({...result,artifacts:{...result.artifacts,items:[{...result.artifacts.items[0],media_ref:'cross-media:'+'a'.repeat(24)}]}}).length,0);
});

test('physical and original movies hand off one source clock; paused old callbacks cannot overwrite source Play or a new explicit seek',async()=>{
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const timers=new Map(),drawTimes=[],plans=[];let timerId=0;
  const makeVideo=physical=>{
    const handlers=new Map(),clock={textContent:''};const video={dataset:{timeStart:'0',timeEnd:'9.8',...(physical?{physicalVideo:''}:{})},currentTime:physical?3:2.4,isConnected:true,paused:true,
      pause(){this.paused=true;},addEventListener:(name,handler)=>handlers.set(name,handler),removeEventListener:name=>handlers.delete(name),
      closest:()=>({querySelector:selector=>selector==='[data-cross-camera-sync]'?{checked:true}:clock}),removeAttribute(){},load(){}};
    const sourceClock={textContent:''},panel={isConnected:true,querySelector:selector=>selector==='[data-cross-camera-video]'?video:selector==='[data-cross-camera-clock]'?sourceClock:null,
      querySelectorAll:selector=>selector==='[data-cross-camera-video]'?[video]:[]};
    return {video,panel,handlers,sourceClock};
  };
  const original=makeVideo(false),physical=makeVideo(true),toast={textContent:'',classList:{add(){},remove(){}}};
  const document={querySelector:selector=>selector==='.cross-camera-panel'?original.panel:selector==='.physical-cross-camera-panel'?physical.panel:selector==='#toast'?toast:null,
    querySelectorAll:selector=>selector==='[data-cross-camera-video]'?[original.video,physical.video]:[],addEventListener(){}};
  const environment={presentationData,presentationJSON,crossCameraCandidateHTML,crossCameraScenePlan,selectedCrossCameraCandidate,updateCrossCameraCursor,bindCrossCameraMedia,crossCameraRequestIsCurrent,
    selectedPhysicalCandidate,physicalScenePlan,physicalGeometryPlan,physicalRequestIsCurrent,prepareFrames:async()=>true,fetch:async()=>({ok:true,json:async()=>({frames:[]})}),
    setTimeout:callback=>{const id=++timerId;timers.set(id,callback);return id;},clearTimeout:id=>timers.delete(id)};
  runInNewContext(source+'\nglobalThis.testControls={state,mountCrossCameraMedia,mountPhysicalMedia,togglePlayback};',environment);environment.document=document;
  const {state,mountCrossCameraMedia,mountPhysicalMedia,togglePlayback}=environment.testControls;
  Object.assign(state,{role:'research',sceneId:'blender-office',sceneEpoch:1,crossCameraEpoch:1,physicalEpoch:1,session:{session_ref:'session-A'},snapshot,
    cameraIds:['CAM_A','CAM_B'],timestamp:3,crossCameraResult:response(),physicalResult:physicalResponse(),view:{setTimestamp:time=>drawTimes.push(time),setCrossCamera:plan=>plans.push(plan),setPhysicalGeometry(){}}});
  mountCrossCameraMedia();mountPhysicalMedia();
  original.video.paused=false;original.handlers.get('play')();original.handlers.get('timeupdate')();assert.equal(state.reconstructionClockOwner,'association');assert.equal(state.crossCameraTimestamp,2.4);
  physical.video.paused=false;physical.handlers.get('play')();physical.handlers.get('timeupdate')();assert.equal(state.reconstructionClockOwner,'physical');assert.equal(state.reconstructionMode,'physical');assert.equal(original.video.paused,true);
  assert.equal(state.physicalTimestamp,3);assert.equal(state.crossCameraTimestamp,null);assert.equal(plans.at(-1).physical,true);
  const draws=drawTimes.length;original.handlers.get('timeupdate')();assert.equal(drawTimes.length,draws);assert.equal(state.physicalTimestamp,3);
  await Promise.resolve();await Promise.resolve();await Promise.resolve();await Promise.resolve();
  await togglePlayback();assert.equal(state.reconstructionClockOwner,'source');assert.equal(state.physicalTimestamp,null);assert.equal(physical.video.paused,true);
  const id=state.playTimer;physical.handlers.get('timeupdate')();assert.equal(state.playTimer,id);assert.equal(state.physicalTimestamp,null);
  await timers.get(id)();assert.equal(state.timestamp,3.2);assert.equal(drawTimes.at(-1),3.2);assert.match(original.sourceClock.textContent,/3\.2 s/);assert.match(physical.sourceClock.textContent,/3\.2 s/);
  physical.video.currentTime=3.8;physical.handlers.get('seeking')();assert.equal(state.playTimer,null);physical.handlers.get('seeked')();
  assert.equal(state.physicalTimestamp,3.8);assert.equal(drawTimes.at(-1),3.8);assert.equal(state.reconstructionClockOwner,'physical');
  state.physicalEpoch++;const stale=drawTimes.length;physical.video.currentTime=4;physical.handlers.get('seeking')();physical.handlers.get('seeked')();assert.equal(drawTimes.length,stale);
  state.crossCameraDispose();state.physicalDispose();assert.equal(original.handlers.size,0);assert.equal(physical.handlers.size,0);assert.equal(toast.textContent,'');
});

test('a paused physical movie ending at ten seconds synchronizes the final 9.8-second RGB, 3D and curve state without reclaiming source Play',async()=>{
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const handlers=new Map(),requests=[],prepared=[],drawTimes=[],attributes={},timers=new Map();let timerId=0;
  const clock={textContent:''},sourceClock={textContent:''},timelineLabel={textContent:''},timelineRange={value:9.6},toast={textContent:'',classList:{add(){},remove(){}}};
  const cursor={setAttribute:(name,value)=>{attributes[name]=value;}},svg={dataset:{timeStart:'0',timeEnd:'9.8',chartLeft:'58',chartRight:'624'},querySelector:()=>cursor};
  const video={dataset:{timeStart:'0',timeEnd:'9.8',physicalVideo:''},currentTime:9.6,duration:10,paused:false,ended:false,error:null,isConnected:true,
    pause(){this.paused=true;},addEventListener:(name,handler)=>handlers.set(name,handler),removeEventListener:name=>handlers.delete(name),
    closest:()=>({querySelector:selector=>selector==='[data-cross-camera-sync]'?{checked:true}:clock}),removeAttribute(){},load(){}};
  const panel={isConnected:true,querySelector:selector=>selector==='[data-cross-camera-video]'?video:selector==='[data-cross-camera-clock]'?sourceClock:null,
    querySelectorAll:selector=>selector==='[data-cross-camera-video]'?[video]:selector==='[data-cross-camera-chart]'?[svg]:[]};
  const document={querySelector:selector=>selector==='.physical-cross-camera-panel'?panel:selector==='#timeline-range'?timelineRange:selector==='[data-current-time]'?timelineLabel:selector==='#toast'?toast:null,
    querySelectorAll:selector=>selector==='[data-cross-camera-video]'?[video]:[],addEventListener(){}};
  const environment={presentationData,presentationJSON,selectedCrossCameraCandidate,crossCameraScenePlan,updateCrossCameraCursor,bindCrossCameraMedia,
    selectedPhysicalCandidate,physicalScenePlan,physicalGeometryPlan,physicalRequestIsCurrent,
    prepareFrames:async frames=>{prepared.push(frames[0].timestamp);return true;},
    fetch:async(_url,{body})=>{const request=JSON.parse(body);requests.push(request.timestamp);return {ok:true,json:async()=>({frames:[{camera_id:'CAM_A',timestamp:request.timestamp,media_ref:'frame:final'}]})};},
    setTimeout:callback=>{const id=++timerId;timers.set(id,callback);return id;},clearTimeout:id=>timers.delete(id)};
  runInNewContext(source+'\nglobalThis.testControls={state,mountPhysicalMedia,togglePlayback};',environment);environment.document=document;
  const {state,mountPhysicalMedia,togglePlayback}=environment.testControls,result=physicalResponse();result.selection.time_range=[0,9.8];
  Object.assign(state,{role:'research',sceneId:'blender-classroom101',sceneEpoch:1,physicalEpoch:1,session:{session_ref:'session-A'},snapshot,cameraIds:['CAM_A','CAM_B'],timestamp:9.6,
    physicalResult:result,view:{setTimestamp:time=>drawTimes.push(time),setCrossCamera(){},setPhysicalGeometry(){}}});
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  mountPhysicalMedia();handlers.get('play')();handlers.get('timeupdate')();await settle();
  video.currentTime=9.7;handlers.get('timeupdate')();await settle();
  assert.equal(state.timestamp,9.6);assert.equal(state.physicalTimestamp,9.7);assert.deepEqual(requests,[9.6]);
  video.currentTime=10;video.paused=true;video.ended=true;handlers.get('ended')();await settle();
  assert.equal(toast.textContent,'');
  assert.equal(state.reconstructionClockOwner,'physical');assert.equal(state.physicalTimestamp,9.8);assert.equal(state.timestamp,9.8);
  assert.deepEqual(requests,[9.6,9.8]);assert.deepEqual(prepared,[9.6,9.8]);assert.equal(state.frames[0].timestamp,9.8);
  assert.equal(drawTimes.at(-1),9.8);assert.equal(Number(timelineRange.value),9.8);assert.equal(Number(attributes.x1),624);
  assert.match(timelineLabel.textContent,/9\.8 s/);assert.match(sourceClock.textContent,/9\.8 s/);assert.match(clock.textContent,/9\.8 s/);
  await togglePlayback();const timer=state.playTimer,count=requests.length;handlers.get('ended')();await settle();
  assert.equal(state.reconstructionClockOwner,'source');assert.equal(state.physicalTimestamp,null);assert.equal(state.playTimer,timer);assert.equal(requests.length,count);
  state.physicalDispose();assert.equal(handlers.size,0);assert.equal(toast.textContent,'');
});

test('physical choice replaces only inspected curves and overlays while retaining original and physical video panels',()=>{
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const candidateNode={innerHTML:''},clock={textContent:''},movie={},originalMovie={},calls=[];
  const panel={video:movie,querySelector:selector=>selector==='[data-physical-candidate]'?candidateNode:selector==='[data-cross-camera-clock]'?clock:null,querySelectorAll:()=>[]};
  const originalPanel={video:originalMovie,querySelector:()=>null,querySelectorAll:()=>[]};
  const document={querySelector:selector=>selector==='.physical-cross-camera-panel'?panel:selector==='.cross-camera-panel'?originalPanel:null,querySelectorAll:()=>[],addEventListener(){}};
  const environment={presentationData,presentationJSON,crossCameraScenePlan,selectedCrossCameraCandidate,updateCrossCameraCursor,selectedPhysicalCandidate,physicalScenePlan,physicalGeometryPlan,physicalCandidateHTML};
  runInNewContext(source+'\nglobalThis.testControls={state,selectPhysicalChoice};',environment);environment.document=document;
  const {state,selectPhysicalChoice}=environment.testControls;const result=physicalResponse();result.rejected_candidates=[{...candidate(1),physical:physicalDecision('REJECTED')}];
  Object.assign(state,{physicalResult:result,crossCameraResult:response(),snapshot,timestamp:2.2,view:{setCrossCamera:plan=>calls.push(plan),setPhysicalGeometry(){},setTimestamp(){}}});
  selectPhysicalChoice('rejected:1');assert.equal(state.reconstructionMode,'physical');assert.equal(state.physicalChoice,'rejected:1');assert.match(candidateNode.innerHTML,/已拒絕/);assert.equal(calls.at(-1).paths.find(row=>row.selected).color,'#ef9da7');
  selectPhysicalChoice('baseline');assert.match(candidateNode.innerHTML,/未關聯基線/);assert.equal(panel.video,movie);assert.equal(originalPanel.video,originalMovie);
  selectPhysicalChoice('accepted:5');assert.equal(state.physicalChoice,'baseline');
  let nodes={'.physical-cross-camera-panel':panel,'.cross-camera-panel':originalPanel};
  const root={querySelector:selector=>nodes[selector],set innerHTML(_){nodes=Object.fromEntries(Object.keys(nodes).map(key=>[key,{replaceWith:node=>{nodes[key]=node;}}]));}};
  retainElements(root,'routine refresh',Object.keys(nodes));assert.equal(nodes['.physical-cross-camera-panel'].video,movie);assert.equal(nodes['.cross-camera-panel'].video,originalMovie);
});

test('decision ledger displays the core rerank and retained candidates outside Top-K without converting them into rejected routes',()=>{
  const result=physicalResponse();result.decision_ledger=[
    {candidate_ref:'candidate:OUTSIDE',original_rank:1,rerank:4,verdict:'UNKNOWN',scores:{base_compatibility:1,support_evidence_bonus:.01,missing_position_penalty:.15,ranking_score:.86},unknown_codes:{WHOLE_SCENE_BODY_CLEARANCE_UNKNOWN:20},reason_codes:{}},
    {candidate_ref:result.candidates[0].candidate_ref,original_rank:3,rerank:1,verdict:'UNKNOWN',scores:result.candidates[0].physical.scores,unknown_codes:{MISSING_GAP_ROUTE_UNOBSERVED:1},reason_codes:{}},
    {candidate_ref:'candidate:BASELINE',original_rank:5,rerank:null,is_unassociated_baseline:true,selected_for_ranking:false,verdict:'UNKNOWN',scores:{ranking_score:0},unknown_codes:{WHOLE_SCENE_BODY_CLEARANCE_UNKNOWN:26},reason_codes:{}},
  ];
  const original=structuredClone(result),html=physicalLedgerHTML(result);
  assert.match(html,/未入 Top-K ≠ 拒絕/);assert.match(html,/仍保留／未入本次 Top-K/);assert.match(html,/<td>1<\/td><td>4<\/td>/);
  assert.match(html,/<td>3<\/td><td>1<\/td>/);assert.match(html,/未關聯基線／排序外/);assert.match(html,/全場身體通行淨空未知 × 20/);
  assert.doesNotMatch(html,/candidate:OUTSIDE|candidate:BASELINE|candidate:PRIVATE|已拒絕：僅供核對/);assert.deepEqual(result,original);
  result.authority_coverage={coverage:{known_collider_component_count:58,physical_complete:false},portals_summary:{count:28,state:'HUMAN_REVIEW',approved_apertures:0}};
  const panel=physicalPanelHTML(result);assert.match(panel,/門洞標註 28（HUMAN_REVIEW）／已批准門洞 0/);assert.match(panel,/已知碰撞組件 58/);
  assert.match(panel,/描邊高度採批准地板錨點供顯示/);assert.match(panel,/來源三角形實際高度/);
});

// Office demo visual acceptance: one cursor rule for 3D, panel and 2D evidence; ground contact is never presented as verified.
test('Office panel path clock uses the 3D cursor rule: no early restart, no held end, MISSING through the long gap',async()=>{
  const {OFFICE_CANDIDATE_PATHS:paths}=await import('./cross-camera-office.fixture.mjs');
  const at=(index,t)=>crossCameraCursor(paths[index],t,[0,9.8])?.timestamp??null;
  assert.equal(at(0,0.4),0.4);assert.equal(at(0,0.5),null);assert.equal(at(1,0.5),null);assert.equal(at(1,0.6),0.6);
  for(const t of [4.5,5,6.5,8.4,8.5])assert.equal(at(0,t),null,`t=${t}`);
  assert.equal(at(0,8.6),8.6);assert.equal(at(2,4.4),4.4);assert.equal(at(3,4.4),4.4);assert.equal(at(3,4.5),null);
  const nodes=paths.map((_,index)=>({dataset:{crossCameraPathClock:String(index)},textContent:''}));
  const container={querySelector:()=>null,querySelectorAll:selector=>selector==='[data-cross-camera-path-clock]'?nodes:[]};
  updateCrossCameraCursor(container,8.5,{paths,display_time_range:[0,9.8]});
  assert.ok(nodes.every(node=>/MISSING/.test(node.textContent)));
  updateCrossCameraCursor(container,8.6,{paths,display_time_range:[0,9.8]});
  assert.match(nodes[0].textContent,/CAM_1F_AUDITORIUM_REAR · DETECTED · 接地 UNKNOWN（可見像素區塊 bbox 底緣中心，非已驗證腳點）/);
});

test('ground contact stays UNKNOWN; the bbox-bottom basis is reported only when the sample reproduces it',async()=>{
  const {OFFICE_CANDIDATE_PATHS:paths}=await import('./cross-camera-office.fixture.mjs');
  for(const sample of paths.flatMap(path=>path.samples).filter(sample=>sample.pixel_observed))
    assert.deepEqual(groundContactBasis(sample),{contact_basis:'VISIBLE_COMPONENT_BBOX_BOTTOM_CENTER',ground_contact:'UNKNOWN'});
  assert.deepEqual(groundContactBasis({bbox_xyxy:[765,11,799,136],contact_pixel:[781.5,120]}),{contact_basis:'UNKNOWN',ground_contact:'UNKNOWN'});
  assert.deepEqual(groundContactBasis({}),{contact_basis:'UNKNOWN',ground_contact:'UNKNOWN'});
  assert.match(groundContactLabel({}),/接地 UNKNOWN（接觸像素來源未提供）/);
  assert.equal(cameraShortLabel('CAM_1F_AUDITORIUM_FRONT'),'FRONT');assert.equal(cameraShortLabel(null),'鏡頭未知');
});

test('Office 2D evidence boxes bind the cursor sample by exact frame_ref and keep simultaneous fragments separate',async()=>{
  const {officeCandidateResult}=await import('./cross-camera-office.fixture.mjs');
  const result=officeCandidateResult(),original=structuredClone(result),plan=crossCameraScenePlan(result,1);
  assert.deepEqual(plan.paths.map(path=>path.associated),[true,false,false,false]);
  const F='CAM_1F_AUDITORIUM_FRONT',R='CAM_1F_AUDITORIUM_REAR';
  const first=candidateEvidenceOverlays(plan,0.4,F,'frame:e973251d18e6e6799200ddfc');
  assert.deepEqual(first.map(item=>[item.caption,item.associated,item.bbox_xyxy,item.contact_pixel,item.contact_basis,item.ground_contact,item.segment_start]),
    [['候選 1 · 路徑 1',true,[765,11,799,136],[781.5,135],'VISIBLE_COMPONENT_BBOX_BOTTOM_CENTER','UNKNOWN',false]]);
  assert.deepEqual(candidateEvidenceOverlays(plan,0.4,F,'frame:other'),[]);assert.deepEqual(candidateEvidenceOverlays(plan,0.4,R,'frame:e973251d18e6e6799200ddfc'),[]);
  assert.deepEqual(candidateEvidenceOverlays(plan,0.6,F,'frame:1f3dd2e2abe6e495ad264dcb').map(item=>[item.caption,item.associated,item.segment_start]),[['候選 1 · 路徑 2',false,true]]);
  assert.deepEqual(candidateEvidenceOverlays(plan,8.5,R,'frame:c78a5503c0bfa91f81df6bae'),[]);
  assert.deepEqual(candidateEvidenceOverlays(plan,8.6,R,'frame:c78a5503c0bfa91f81df6bae').map(item=>item.segment_start),[true]);
  const split=candidateEvidenceOverlays(plan,4.4,F,'frame:6722beac04849d9bee47dd06');
  assert.deepEqual(split.map(item=>[item.caption,item.bbox_xyxy]),[['候選 1 · 路徑 3',[826,119,832,147]],['候選 1 · 路徑 4',[832,23,853,119]]]);
  const svg=candidateEvidenceSVG(split,{camera_id:F,width:960,height:540});
  assert.equal((svg.match(/data-ground-contact="UNKNOWN"/g)??[]).length,2);assert.match(svg,/viewBox="0 0 960 540"/);
  assert.match(svg,/<rect x="826" y="119" width="6" height="28"/);assert.match(svg,/候選1·路徑4 · 未關聯 · DETECTED · 接地 UNKNOWN/);
  const ys=[...svg.matchAll(/<text x="[^"]+" y="([^"]+)"/g)].map(match=>Number(match[1]));assert.equal(new Set(ys).size,2);
  assert.equal(candidateEvidenceSVG([],{width:960,height:540}),'');
  assert.equal(candidateEvidenceSVG(split,{width:Number.NaN,height:540}),'');
  plan.paths[2].selected=false;assert.equal(candidateEvidenceOverlays(plan,4.4,F,'frame:6722beac04849d9bee47dd06').length,1);
  assert.deepEqual(result,original);
});

test('Office candidate panel separates unassociated fragments and labels pixel scores and incidence as non-accuracy',async()=>{
  const {officeCandidateResult}=await import('./cross-camera-office.fixture.mjs');
  const html=crossCameraCandidateHTML(officeCandidateResult(),1);
  assert.equal((html.match(/· 未關聯片段<\/h3>/g)??[]).length,3);assert.match(html,/不代表與其他路徑為同一人或連續移動/);
  assert.match(html,/路徑資料、像素量測分數與接地狀態/);assert.match(html,/不是公尺誤差或機率/);assert.match(html,/不是位置準確度/);
  assert.match(html,/&quot;pixel_measurement_uncertainty&quot;: 0\.6/);assert.match(html,/&quot;ray_floor_incidence&quot;: 0\.178/);
  assert.match(html,/&quot;contact_basis&quot;: &quot;VISIBLE_COMPONENT_BBOX_BOTTOM_CENTER&quot;/);assert.match(html,/&quot;ground_contact&quot;: &quot;UNKNOWN&quot;/);
  assert.doesNotMatch(html,/&quot;uncertainty&quot;:/);
});

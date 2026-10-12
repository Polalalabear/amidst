import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {presentationData,presentationJSON,retainElements} from './presentation-data.mjs';
import {crossCameraSelection} from './app.mjs';
import {invalidateCrossCamera,runCrossCameraReconstruction,validateCrossCameraResponse,crossCameraRequestIsCurrent,crossCameraSegments,
  crossCameraVelocitySegments,crossCameraCursor,crossCameraScenePlan,crossCameraPanelHTML,crossCameraCandidateHTML,
  selectedCrossCameraCandidate,availableCrossCameraArtifacts,crossCameraArtifactsHTML,crossCameraPresentation,
  sourceTimeForCrossCameraVideo,bindCrossCameraMedia,updateCrossCameraCursor} from './cross-camera.mjs';
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
  const environment={presentationData,presentationJSON,crossCameraCandidateHTML,crossCameraScenePlan,selectedCrossCameraCandidate,updateCrossCameraCursor};
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
  const environment={presentationData,presentationJSON,crossCameraCandidateHTML,crossCameraScenePlan,selectedCrossCameraCandidate,updateCrossCameraCursor,bindCrossCameraMedia,crossCameraRequestIsCurrent,
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
  assert.equal(state.timestamp,3.4);assert.equal(drawTimes.at(-1),3.4);assert.equal(Number(timelineRange.value),3.4);
  assert.match(timelineLabel.textContent,/3\.4 s/);assert.match(sourceClock.textContent,/3\.4 s/);
  assert.equal(Number(attributes.x1),58+(3.4-2)/2*(624-58));
  const pauseCalls=video.pauseCalls;await togglePlayback();assert.equal(state.playTimer,null);assert.equal(video.pauseCalls,pauseCalls);
  // A fresh movie play can take control again after the source playback is stopped.
  video.paused=false;video.currentTime=3.8;videoHandlers.get('timeupdate')();assert.equal(state.crossCameraTimestamp,3.8);assert.equal(drawTimes.at(-1),3.8);
  state.crossCameraDispose();
});

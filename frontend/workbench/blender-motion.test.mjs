import test from 'node:test';
import assert from 'node:assert/strict';
import {invalidateMotion,runMotionReconstruction,validateMotionResponse,positionSegments,velocitySegments,
  motionPanelHTML,motionTracksHTML,motionArtifactsHTML,availableMotionArtifacts,sourceTimeForVideo,bindMotionMedia} from './blender-motion.mjs';
import {retainElements} from './presentation-data.mjs';

const selection={camera_ids:['CAM_A','CAM_B'],start:2,end:4};
const state=()=>({role:'research',sceneEpoch:1,sceneId:'blender-office',session:{session_ref:'s-A'},motionEpoch:0,
  snapshot:{source_binding:{run_id:'run-A',source_sha256:'source-A'},baseline:{source_features:'features-A'}}});
const response=()=>({schema_version:'workbench.blender-motion.v1',agent_used:false,
  source_binding:{run_id:'run-A',source_sha256:'source-A'},source_features:'features-A',
  selection:{camera_ids:['CAM_A','CAM_B'],time_range:[2,4]},tracks:[]});
const projected=(timestamp,world_position,connect=true)=>({timestamp,world_position,state:'PROJECTED_OBSERVATION',connect_from_previous:connect});

test('reconstruction request sends only the selected camera/time scope and validates the exact source before display',async()=>{
  const target=state(),requests=[];
  assert.equal(await runMotionReconstruction(target,selection,async request=>{requests.push(request);return response();}),true);
  assert.deepEqual(requests,[{scene_id:'blender-office',camera_ids:['CAM_A','CAM_B'],start:2,end:4}]);
  assert.equal(target.motionResult.agent_used,false);assert.equal(target.motionPending,false);
  for(const change of [
    {agent_used:true},{source_binding:{run_id:'run-B',source_sha256:'source-A'}},
    {source_binding:{run_id:'run-A',source_sha256:'source-B'}},{source_features:'old-features'},
    {selection:{camera_ids:['CAM_A'],time_range:[2,4]}},
    {selection:{camera_ids:['CAM_A','CAM_B'],time_range:[0,9.8]}},
    {tracks:[{camera_id:'OTHER_CAMERA'}]},
  ])assert.throws(()=>validateMotionResponse({...response(),...change},selection,target.snapshot));
});

test('unsaved edits, new selections and late errors cannot replace newer motion results',async()=>{
  const target=state(),pending=[];
  const old=runMotionReconstruction(target,selection,()=>new Promise(resolve=>pending.push(resolve)));
  invalidateMotion(target);
  const next=runMotionReconstruction(target,selection,()=>new Promise(resolve=>pending.push(resolve)));
  pending[1]({...response(),summary:{generation:'new'}});assert.equal(await next,true);
  pending[0]({...response(),summary:{generation:'old'}});assert.equal(await old,false);
  assert.equal(target.motionResult.summary.generation,'new');
  let reject;
  const rejected=runMotionReconstruction(target,selection,()=>new Promise((_,fail)=>{reject=fail;}));
  invalidateMotion(target);reject(Error('late old request failed'));
  assert.equal(await rejected,false);assert.equal(target.motionResult,null);
});

test('scene, role or session replacement rejects a late curve/video response',async()=>{
  for(const mutate of [target=>target.sceneEpoch++,target=>target.sceneId='blender-auditorium',
    target=>target.session={session_ref:'s-B'},target=>target.role='management']){
    const target=state();let resolve;
    const pending=runMotionReconstruction(target,selection,()=>new Promise(done=>{resolve=done;}));
    mutate(target);resolve(response());assert.equal(await pending,false);assert.equal(target.motionResult,null);
  }
});

test('position curves use explicit connectivity, dash short interpolation and never connect long or missing gaps',()=>{
  const samples=[projected(2,[0,0,0],false),projected(2.2,[1,0,0]),
    {timestamp:2.4,world_position:[2,0,0],state:'INFERRED_INTERPOLATION',connect_from_previous:true},
    {timestamp:2.6,world_position:null,state:'MISSING'},projected(3.4,[3,0,0]),
    projected(3.6,[4,0,0],false),projected(3.8,[5,0,0])];
  const segments=positionSegments(samples,[2,4]);
  assert.deepEqual(segments.map(s=>[s.from.timestamp,s.to.timestamp,s.inferred]),[[2,2.2,false],[2.2,2.4,true],[3.6,3.8,false]]);
  assert.deepEqual(positionSegments(samples,[2.3,3.5]),[]);
  const html=motionTracksHTML({...response(),tracks:[{camera_id:'CAM_A',canonical_time_range:[0,9.8],samples,velocities:[],gaps:[{time_range:[2.6,3.4],reason:'LONG_GAP'}]}]});
  assert.match(html,/stroke-dasharray="5 4"/);assert.match(html,/長缺口，保持斷線/);assert.match(html,/本次曲線範圍 2\.0 s–4\.0 s/);
  assert.doesNotMatch(html,/NaN|Infinity/);
});

test('finite-difference speed lines cannot span discontinuous derivative windows',()=>{
  const velocity=(timestamp,time_range,speed_m_s)=>({timestamp,time_range,speed_m_s,velocity_xyz:[speed_m_s,0,0],state:'INFERRED_FINITE_DIFFERENCE'});
  const samples=[velocity(2.1,[2,2.2],1),velocity(2.3,[2.2,2.4],2),velocity(3.5,[3.4,3.6],3),velocity(3.7,[3.6,3.8],4)];
  assert.deepEqual(velocitySegments(samples,[2,4]).map(s=>[s.from.timestamp,s.to.timestamp]),[[2.1,2.3],[3.5,3.7]]);
  assert.deepEqual(velocitySegments([samples[0],{...samples[1],speed_m_s:Infinity},samples[2]],[2,4]),[]);
});

test('curve/uncertainty presentation escapes HTML and hides canonical track/event refs while retaining their original input',()=>{
  const result={...response(),tracks:[{track_ref:'track:private:ABC',camera_id:'CAM_A',canonical_time_range:[0,9.8],
    samples:[{...projected(2,[1,2,3],false),uncertainty:{source:'<script>alert(1)</script>',track_ref:'track:private:ABC',event_ref:'event:private:ABC'}}],
    velocities:[],gaps:[],events:[{event_ref:'event:private:ABC',kind:'PROVISIONAL_LOCAL_MOTION_SEGMENT',canonical_time_range:[0,9.8]}]}]};
  const before=structuredClone(result),html=motionPanelHTML(result,{cameraLabel:()=>'<CAM A>'});
  assert.match(html,/局部軌跡 1/);assert.match(html,/&lt;CAM A&gt;/);assert.match(html,/&lt;script&gt;/);
  assert.doesNotMatch(html,/track:private:ABC|event:private:ABC|<script>|NaN|Infinity/);
  assert.deepEqual(result,before);
});

test('full-run materialized PNG/video disclose both full scope and narrow query and never invent missing artifacts',()=>{
  const result={...response(),artifacts:{status:'AVAILABLE',items:[
    {kind:'POSITION_VELOCITY_CURVES',media_ref:'motion:curves:123',mime_type:'image/png',time_range:[0,9.8]},
    {kind:'RECONSTRUCTION_VIDEO',media_ref:'motion:video:123',mime:'video/mp4',time_range:[0,9.8]},
    {kind:'RECONSTRUCTION_VIDEO',media_ref:'/private/invalid.mp4',mime:'video/mp4',time_range:[0,9.8]},
  ]}};
  assert.equal(availableMotionArtifacts(result).length,2);
  const html=motionArtifactsHTML(result,{urlFor:ref=>'/api/motion_media?ref='+encodeURIComponent(ref)});
  assert.match(html,/完整來源範圍 0\.0 s–9\.8 s/);assert.match(html,/本次查詢範圍 2\.0 s–4\.0 s/);
  assert.match(html,/<video controls preload="metadata"/);assert.match(html,/素材沒有依本次鏡頭或窄範圍重新產生/);
  assert.doesNotMatch(html,/\/private\//);
  assert.match(motionArtifactsHTML({...response(),artifacts:{status:'UNAVAILABLE',items:result.artifacts.items}}),/尚未物化或來源不相符/);
});

test('a camera with source images and no projected track remains explicitly missing alongside another camera curve',()=>{
  const result={...response(),camera_coverage:[
    {camera_id:'CLASS101',time_range:[0,9.8],source_frame_count:50,pixel_observation_count:70,projected_frame_count:46,missing_projected_frame_count:4,state:'PARTIAL'},
    {camera_id:'CORRIDOR04',time_range:[0,9.8],source_frame_count:50,pixel_observation_count:0,projected_frame_count:0,missing_projected_frame_count:50,state:'MISSING'},
  ],tracks:[{camera_id:'CLASS101',canonical_time_range:[0,9.8],samples:[projected(2,[1,2,0],false)],velocities:[],gaps:[]}]};
  const html=motionPanelHTML(result),missingRow=html.match(/<tr><td>CORRIDOR04[\s\S]*?<\/tr>/)?.[0];
  assert.ok(missingRow);assert.match(missingRow,/<td>50<\/td><td>0<\/td><td>0<\/td><td>50<\/td>/);
  assert.match(missingRow,/MISSING/);assert.match(missingRow,/沒有像素追蹤或 3D 投影/);
  assert.match(html,/其他鏡頭有曲線，不代表缺失鏡頭已有追蹤/);
});

test('single-camera narrow query displays full materialized camera selection separately from queried camera selection',()=>{
  const result={...response(),selection:{camera_ids:['CAM_A'],time_range:[2,4]},artifacts:{status:'AVAILABLE',
    selection:{camera_ids:['CAM_A','CAM_B'],time_range:[0,9.8]},items:[
      {kind:'RECONSTRUCTION_VIDEO',media_ref:'motion:video:123',mime:'video/mp4',time_range:[0,9.8]},
    ]}};
  const html=motionArtifactsHTML(result);
  assert.match(html,/完整素材鏡頭：CAM_A、CAM_B/);assert.match(html,/本次查詢鏡頭：CAM_A · 本次查詢範圍 2\.0 s–4\.0 s/);
  assert.match(html,/完整來源範圍 0\.0 s–9\.8 s/);
});

test('video seek synchronizes only valid source time while its live scope owns the panel, and disposal stops media',()=>{
  const handlers=new Map(),sync={checked:true},clock={textContent:''};let live=true;
  const video={dataset:{motionStart:'0',motionEnd:'9.8'},currentTime:2.2,isConnected:true,
    closest:()=>({querySelector:selector=>selector==='[data-motion-sync]'?sync:clock}),
    addEventListener:(name,callback)=>handlers.set(name,callback),removeEventListener:name=>handlers.delete(name),
    pause(){this.paused=true;},removeAttribute(name){this.removed=name;},load(){this.loaded=true;}};
  const calls=[],dispose=bindMotionMedia({querySelectorAll:()=>[video]},{current:()=>live,onSourceTime:time=>calls.push(time)});
  handlers.get('seeked')();assert.deepEqual(calls,[2.2]);assert.match(clock.textContent,/2\.2 s/);
  video.currentTime=2.25;handlers.get('timeupdate')();assert.deepEqual(calls,[2.2]);
  video.currentTime=3;live=false;handlers.get('seeked')();assert.deepEqual(calls,[2.2]);
  live=true;sync.checked=false;handlers.get('seeked')();assert.deepEqual(calls,[2.2]);
  video.currentTime=10;assert.equal(sourceTimeForVideo(video),9.8);
  assert.equal(sourceTimeForVideo({...video,dataset:{}}),null);
  dispose();assert.equal(handlers.size,0);assert.equal(video.paused,true);assert.equal(video.removed,'src');assert.equal(video.loaded,true);
});

test('routine rerender retains exact source canvas, decoded camera image and motion video panel',()=>{
  const canvas={kind:'source-canvas'},image={kind:'decoded-camera'},video={kind:'playing-video'};
  const old={'.source-stage':{canvas},'details.source-evidence':{image},'.motion-reconstruction-panel':{video}};
  let nodes={...old};
  const root={querySelector:selector=>nodes[selector],set innerHTML(_value){nodes=Object.fromEntries(Object.keys(old).map(key=>[key,{replaceWith:node=>{nodes[key]=node;}}]));}};
  retainElements(root,'new surrounding controls',['.source-stage','details.source-evidence','.motion-reconstruction-panel']);
  assert.equal(nodes['.source-stage'].canvas,canvas);assert.equal(nodes['details.source-evidence'].image,image);
  assert.equal(nodes['.motion-reconstruction-panel'].video,video);
});

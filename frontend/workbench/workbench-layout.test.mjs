import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {presentationData,presentationJSON,retainElements} from './presentation-data.mjs';
import {motionPanelHTML} from './blender-motion.mjs';
import {crossCameraPanelHTML,physicalPanelHTML,updateCrossCameraCursor,selectedCrossCameraCandidate,selectedPhysicalCandidate} from './cross-camera.mjs';
import {timeSegments,resolveTimeSegment,frameQuerySelection,motionSelection,crossCameraSelection,frameWallSelection,
  validateFrameWallResponse,frameWallRequestIsCurrent,runFrameWall,frameWallNearestSlots,frameWallItemsHTML,syncFrameWallNodes,physicalReviewPanelCanPersist} from './app.mjs';

const snapshot={scene_id:'blender-office',capabilities:{frame_query:true},time_range:[0,9.8],
  source_binding:{run_id:'run-OFFICE',source_sha256:'source',site_id:'office',dataset_sha256:'office-pixels',clock_id:'office-clock',scale_sha256:'office-scale'},
  baseline:{source_features:'office-index'},cameras:[{camera_id:'CAM_A',label:'來源 A'},{camera_id:'CAM_B',label:'來源 B'}]};
const input={camera_ids:['CAM_A','CAM_B'],start:0,end:9.8,target_timestamp:4.9,top_k:3,behavior_intent:'walking'};
const selection=(slots=8)=>frameWallSelection(input,snapshot,slots);
function response(selected=selection()){
  return {schema_version:'workbench.camera-frame-wall.v1',selection:{camera_ids:[...selected.camera_ids],time_range:[selected.start,selected.end],slot_count:selected.slot_count},
    data_kind:'ACTUAL_SOURCE_RGB_TIME_SAMPLES',temporal_mosaic:true,source_camera_count:selected.camera_ids.length,unique_source_frames:selected.slot_count,
    frames:Array.from({length:selected.slot_count},(_,slot)=>{
      const requested_timestamp=Number((selected.start+(selected.end-selected.start)*Math.floor(slot/2)/(selected.slot_count/2-1)).toFixed(6));
      return {slot_index:slot,camera_id:selected.camera_ids[slot%2],requested_timestamp,timestamp:Number((Math.round(requested_timestamp/.2)*.2).toFixed(1)),media_ref:'media:'+slot,frame_ref:'frame:opaque:'+slot,status:'NEAREST_AVAILABLE',repeated_source_frame:false};
    }),missing_slots:[],retrieval:{indexed:true,source_rgb_scan:false,frame_records_read:selected.slot_count},agent_used:false,real_stream:false,
    source_binding:{...snapshot.source_binding},scope:{scene_id:snapshot.scene_id,source_features:snapshot.baseline.source_features}};
}
const target=()=>({role:'research',sceneEpoch:1,sceneId:snapshot.scene_id,session:{session_ref:'SESSION'},snapshot,frameWallEpoch:0,frameWall:null});
test('returning from dashboard remounts review panels instead of retaining an absent or disposed host',()=>{
  const state={page:'workspace',mode:'display',physicalReviewPanelKey:'source:revision',physicalReviewDispose:()=>{}};
  assert.equal(physicalReviewPanelCanPersist(state,{isConnected:true},'source:revision'),true);
  assert.equal(physicalReviewPanelCanPersist({...state,page:'dashboard'},{isConnected:true},'source:revision'),false);
  assert.equal(physicalReviewPanelCanPersist(state,null,'source:revision'),false);
  assert.equal(physicalReviewPanelCanPersist(state,{isConnected:false},'source:revision'),false);
  assert.equal(physicalReviewPanelCanPersist({...state,physicalReviewDispose:null},{isConnected:true},'source:revision'),false);
  assert.equal(physicalReviewPanelCanPersist(state,{isConnected:true},'other:revision'),false);
});
test('decoded temporal cells replace stale placeholders and resized walls never accumulate duplicate slots',()=>{
  const rows=(count,prefix)=>Array.from({length:count},(_,slot)=>({dataset:{wallSlot:String(slot),wallKey:prefix+slot},image:{}}));
  const grid={children:rows(8,'missing'),changes:0,replaceChildren(...children){this.children=children;this.changes++;}};
  const decoded=rows(8,'frame');syncFrameWallNodes(grid,decoded);
  assert.deepEqual(grid.children,decoded);assert.equal(grid.children.length,8);
  syncFrameWallNodes(grid,rows(8,'frame'));assert.equal(grid.changes,1);assert.equal(grid.children[0].image,decoded[0].image);
  syncFrameWallNodes(grid,rows(16,'resized'));assert.equal(grid.children.length,16);assert.equal(new Set(grid.children.map(n=>n.dataset.wallSlot)).size,16);
  const retained=grid.children[0];syncFrameWallNodes(grid,rows(8,'resized'));assert.equal(grid.children.length,8);assert.equal(grid.children[0],retained);
  grid.children.push(...rows(8,'obsolete'));syncFrameWallNodes(grid,rows(8,'resized'));
  assert.equal(grid.children.length,8);assert.ok(grid.children.every(n=>n.dataset.wallKey.startsWith('resized')));
});
const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
function appVM(exports,extra={}){
  const environment={presentationData,presentationJSON,motionPanelHTML,crossCameraPanelHTML,physicalPanelHTML,updateCrossCameraCursor,selectedCrossCameraCandidate,selectedPhysicalCandidate,...extra};
  runInNewContext(source+`\nglobalThis.controls={${exports}};`,environment);
  return environment;
}
const node=dataset=>({dataset,hidden:false,attributes:{},classes:new Set(),classList:{toggle(name,active){active?this.owner.classes.add(name):this.owner.classes.delete(name);}},
  setAttribute(name,value){this.attributes[name]=value;},removeAttribute(name){delete this.attributes[name];}});
function visualNode(dataset){const item=node(dataset);item.classList.owner=item;return item;}

test('four preset segments map to source seconds and feed every existing query/reconstruction contract',()=>{
  assert.deepEqual(timeSegments(snapshot),[
    {value:'full',label:'完整',start:0,end:9.8},{value:'early',label:'前段',start:0,end:3.2},
    {value:'middle',label:'中段',start:3.2,end:6.6},{value:'late',label:'後段',start:6.6,end:9.8},
  ]);
  for(const segment of timeSegments(snapshot)){
    const values={...input,time_segment:segment.value,start:'IGNORED',end:'IGNORED',target_timestamp:(segment.start+segment.end)/2};
    assert.deepEqual(resolveTimeSegment(values,snapshot),{...values,start:segment.start,end:segment.end});
    assert.equal(frameQuerySelection(values,snapshot).start,segment.start);
    assert.equal(motionSelection({...values,target_timestamp:'INVALID',top_k:''},snapshot).end,segment.end);
    assert.deepEqual(crossCameraSelection(values,snapshot),{camera_ids:input.camera_ids,start:segment.start,end:segment.end,top_k:3});
    assert.equal(frameWallSelection(values,snapshot,16).end,segment.end);
  }
  assert.throws(()=>resolveTimeSegment({...input,time_segment:'custom'},snapshot),/完整/);
  assert.deepEqual(resolveTimeSegment(input,snapshot),input); // Existing numeric API callers remain valid.
  assert.deepEqual(timeSegments({...snapshot,time_range:[5,5]}).map(item=>[item.start,item.end]),[[5,5],[5,5],[5,5],[5,5]]);
});

test('8/12/16 temporal slots are bounded source frames, not extra cameras, with strict source/clock/selection validation',()=>{
  for(const count of [8,12,16]){
    const selected=selection(count),result=response(selected);
    assert.equal(validateFrameWallResponse(result,selected,snapshot),result);
    assert.equal(new Set(result.frames.map(frame=>frame.camera_id)).size,2);
    assert.equal(result.frames.length,count);
  }
  for(const values of [{...input,camera_ids:[]},{...input,camera_ids:['OTHER']},{...input,camera_ids:['CAM_A','CAM_A']},{...input,start:''},{...input,end:10},{...input,start:false},{...input,end:true}])assert.throws(()=>frameWallSelection(values,snapshot,8));
  for(const slots of [0,7,17,'8',true])assert.throws(()=>frameWallSelection(input,snapshot,slots));
  for(const change of [
    {source_binding:{...snapshot.source_binding,site_id:'auditorium'}},{source_binding:{...snapshot.source_binding,run_id:'other'}},
    {source_binding:{...snapshot.source_binding,dataset_sha256:'auditorium-pixels'}},{source_binding:{...snapshot.source_binding,clock_id:'other'}},
    {source_binding:{...snapshot.source_binding,scale_sha256:'other'}},{scope:{scene_id:'blender-auditorium',source_features:'office-index'}},
    {scope:{scene_id:snapshot.scene_id,source_features:'other'}},{selection:{camera_ids:['CAM_A'],time_range:[0,9.8],slot_count:8}},
    {selection:{camera_ids:input.camera_ids,time_range:[2,4],slot_count:8}},{source_camera_count:8},{temporal_mosaic:false},
    {retrieval:{indexed:true,source_rgb_scan:true,frame_records_read:8}},{retrieval:{indexed:true,source_rgb_scan:false,frame_records_read:100}},
    {agent_used:true},{real_stream:true},
  ])assert.throws(()=>validateFrameWallResponse({...response(),...change},selection(),snapshot));
  for(const mutate of [r=>r.frames[0].camera_id='OTHER',r=>r.frames[0].timestamp=10,r=>r.frames[0].requested_timestamp=10,
    r=>r.frames[1].slot_index=0,r=>r.frames[0].slot_index=8,r=>r.frames.push({...r.frames[0],slot_index:8}),
    r=>{r.frames[0].status='MISSING';r.frames[0].timestamp=null;}]){
    const result=response();mutate(result);assert.throws(()=>validateFrameWallResponse(result,selection(),snapshot));
  }
});

test('frame wall sends only the bounded scope and commits only after source image preparation',async()=>{
  const state=target(),requests=[];let imageDone;
  const pending=runFrameWall(state,selection(),async request=>{requests.push(request);return response();},()=>new Promise(resolve=>{imageDone=resolve;}));
  await Promise.resolve();await Promise.resolve();assert.equal(state.frameWall,null);assert.equal(state.frameWallPending,true);
  imageDone(true);assert.equal(await pending,true);assert.equal(state.frameWall.frames.length,8);
  assert.deepEqual(requests,[{scene_id:snapshot.scene_id,camera_ids:['CAM_A','CAM_B'],start:0,end:9.8,slot_count:8}]);
  assert.equal('top_k' in requests[0],false);assert.equal('agent_input' in requests[0],false);assert.equal(state.frameWallPending,false);
});

test('late scene/session/role/selection responses and image decodes cannot restore stale frame walls',async()=>{
  for(const mutate of [state=>state.sceneId='blender-auditorium',state=>state.sceneEpoch++,state=>state.role='management',state=>state.session={session_ref:'NEW'},state=>state.frameWallEpoch++]){
    const state=target();let done;const pending=runFrameWall(state,selection(),()=>new Promise(resolve=>{done=resolve;}));
    mutate(state);done(response());assert.equal(await pending,false);assert.equal(state.frameWall,null);
    assert.equal(frameWallRequestIsCurrent(state,{sceneId:snapshot.scene_id,sceneEpoch:1,sessionRef:'SESSION',frameWallEpoch:1}),false);
  }
  const state=target();let decode;
  const pending=runFrameWall(state,selection(),async()=>response(),()=>new Promise(resolve=>{decode=resolve;}));
  await Promise.resolve();await Promise.resolve();state.frameWallEpoch++;decode(true);assert.equal(await pending,false);assert.equal(state.frameWall,null);
  let fail;const staleError=runFrameWall(state,selection(),()=>new Promise((_,reject)=>{fail=reject;}));state.frameWallEpoch++;fail(Error('late error'));
  assert.equal(await staleError,false);assert.equal(state.frameWallError,null);
});

test('wall reload failures keep explicit missing states; short-window repeated frames remain disclosed',async()=>{
  const state=target();state.frameWall=response();
  await assert.rejects(runFrameWall(state,selection(),async()=>{throw Error('SOURCE_UNAVAILABLE');}),/SOURCE_UNAVAILABLE/);
  assert.equal(state.frameWall,null);assert.equal(state.frameWallError,'SOURCE_UNAVAILABLE');assert.equal(state.frameWallPending,false);
  await assert.rejects(runFrameWall(state,selection(),async()=>response(),async()=>false),/來源影格/);assert.equal(state.frameWallPending,false);
  const result=response();result.frames[1]={...result.frames[0],slot_index:1,repeated_source_frame:true};
  result.frames[2]={slot_index:2,camera_id:'CAM_A',requested_timestamp:3.2,timestamp:null,media_ref:null,status:'MISSING'};
  const html=frameWallItemsHTML(result,{slotCount:8,cameraLabel:id=>id,urlFor:ref=>'/api/media?ref='+ref});
  assert.equal((html.match(/data-wall-slot=/g)??[]).length,8);assert.match(html,/重複來源影格/);assert.match(html,/MISSING/);assert.match(html,/請求 3\.2 s/);
  assert.match(html,/CAM_A/);assert.match(html,/0\.0 s/);assert.doesNotMatch(html,/frame:opaque|event:|track:/);
  assert.equal((frameWallItemsHTML(null,{slotCount:16}).match(/MISSING/g)??[]).length,16);
});

test('research navigation is above a visual-first workspace with a local review host and no fine start/end controls',()=>{
  const environment=appVM('state,sidebar,workspace'),{state,sidebar,workspace}=environment.controls;
  Object.assign(state,{role:'research',snapshot,frameQuerySelection:input,sceneId:snapshot.scene_id,mode:'display',page:'workspace'});
  const nav=sidebar(),html=workspace();
  assert.match(nav,/<header class="research-navigation">/);assert.match(nav,/aria-label="研究工作台導覽"/);assert.doesNotMatch(nav,/<aside class="sidebar">/);
  assert.ok(html.indexOf('primary-visual')<html.indexOf('baseline-query-panel'));
  assert.ok(html.indexOf('id="physical-review-host"')>html.indexOf('primary-visual'));
  assert.match(html,/data-visual-mode="3d" aria-pressed="true"/);assert.match(html,/data-visual-mode="wall"/);
  assert.match(html,/同一組登錄鏡頭在不同時間/);assert.match(html,/不代表新增鏡頭/);
  assert.match(html,/name="time_segment"/);assert.doesNotMatch(html,/<input name="(?:start|end)" type="number"/);
  assert.match(html,/name="start" type="hidden"/);assert.match(html,/橙色目標為替代資料/);assert.doesNotMatch(html,/data-mode="review"/);
  state.role='management';assert.match(sidebar(),/<aside class="sidebar">/);
});

test('switching 3D/wall visibility retains exact renderer, camera pose, decoded image and playing video without fetching',()=>{
  const surfaces=[visualNode({visualSurface:'3d'}),visualNode({visualSurface:'wall'})],buttons=[visualNode({visualMode:'3d'}),visualNode({visualMode:'wall'})];
  const canvas={},renderer={},pose={},image={},movie={paused:false,currentTime:4.8};let resize=0,fetches=0;
  const environment=appVM('state,setVisualMode',{fetch:()=>{fetches++;throw Error('UNEXPECTED_FETCH');}});
  environment.document={querySelectorAll:selector=>selector==='[data-visual-surface]'?surfaces:selector==='[data-visual-mode]'?buttons:[]};
  const {state,setVisualMode}=environment.controls;Object.assign(state,{role:'research',snapshot,view:{canvas,renderer,pose,resize(){resize++;}},frameWall:{image},physicalResult:{movie}});
  setVisualMode('wall');assert.equal(surfaces[0].hidden,true);assert.equal(surfaces[1].hidden,false);assert.equal(resize,0);
  setVisualMode('3d');assert.equal(surfaces[0].hidden,false);assert.equal(surfaces[1].hidden,true);assert.equal(resize,1);
  assert.equal(state.view.renderer,renderer);assert.equal(state.view.pose,pose);assert.equal(state.view.canvas,canvas);assert.equal(state.frameWall.image,image);assert.equal(state.physicalResult.movie,movie);
  assert.equal(movie.paused,false);assert.equal(movie.currentTime,4.8);assert.equal(fetches,0);
});

test('source and movie clocks highlight only nearest metadata samples without rebuilding image/video nodes or re-querying',()=>{
  const result=response(),cells=result.frames.map(frame=>visualNode({wallSlot:String(frame.slot_index)}));
  const image={},movie={},renderer={};let fetches=0;
  const environment=appVM('state,updateFrameWallCursor,updateReconstructionCursors',{fetch:()=>{fetches++;}});
  environment.document={querySelector:()=>null,querySelectorAll:selector=>selector==='[data-wall-slot]'?cells:[]};
  const {state,updateFrameWallCursor,updateReconstructionCursors}=environment.controls;
  Object.assign(state,{frameWall:result,view:{renderer},physicalResult:{movie},frames:[{image}]});
  updateFrameWallCursor(0);assert.deepEqual(cells.filter(cell=>cell.classes.has('nearest-source-time')).map(cell=>Number(cell.dataset.wallSlot)),[0,1]);
  updateReconstructionCursors(9.8);assert.deepEqual(cells.filter(cell=>cell.classes.has('nearest-source-time')).map(cell=>Number(cell.dataset.wallSlot)),[6,7]);
  assert.equal(state.view.renderer,renderer);assert.equal(state.physicalResult.movie,movie);assert.equal(state.frames[0].image,image);assert.equal(fetches,0);
  assert.deepEqual(frameWallNearestSlots([{slot_index:0,camera_id:'CAM_A',timestamp:null,status:'MISSING'},
    {slot_index:1,camera_id:'CAM_A',timestamp:2,media_ref:'frame'},{slot_index:2,camera_id:'CAM_A',timestamp:4,media_ref:'frame'},
    {slot_index:3,camera_id:'CAM_B',timestamp:3,media_ref:'frame'}],3),[1,3]);
  assert.deepEqual(frameWallNearestSlots(result.frames,NaN),[]);
});

test('routine workbench render preserves exact frame-wall images and source/physical movie panels',()=>{
  const image={},sourceImage={},movie={},old={'[data-frame-wall-grid]':{image},'details.source-evidence':{sourceImage},'.physical-cross-camera-panel':{movie}};let nodes={...old};
  const root={querySelector:selector=>nodes[selector],set innerHTML(_){nodes=Object.fromEntries(Object.keys(old).map(key=>[key,{replaceWith:node=>{nodes[key]=node;}}]));}};
  retainElements(root,'updated controls',Object.keys(old));assert.equal(nodes['[data-frame-wall-grid]'].image,image);assert.equal(nodes['details.source-evidence'].sourceImage,sourceImage);assert.equal(nodes['.physical-cross-camera-panel'].movie,movie);
});

test('segment controls clamp only the search target, synchronize hidden request fields and leave the source play clock unchanged',()=>{
  const fields={'[name="time_segment"]':{value:'full'},'[name="start"]':{value:0},'[name="end"]':{value:9.8},
    '[data-time-segment-detail]':{textContent:''},'[name="target_timestamp"]':{value:4.9,min:0,max:9.8}},form={querySelector:selector=>fields[selector]??null};
  const visual={value:'full'},environment=appVM('state,applyTimeSegment');
  environment.document={querySelector:selector=>selector==='[data-workspace-time-segment]'?visual:null};
  const {state,applyTimeSegment}=environment.controls;Object.assign(state,{snapshot,timestamp:4.8,reconstructionClockOwner:'source'});
  applyTimeSegment(form,'early');assert.equal(fields['[name="start"]'].value,0);assert.equal(fields['[name="end"]'].value,3.2);
  assert.equal(fields['[name="target_timestamp"]'].value,1.6);assert.equal(visual.value,'early');assert.match(fields['[data-time-segment-detail]'].textContent,/0\.0–3\.2 s/);
  applyTimeSegment(form,'full');assert.equal(fields['[name="target_timestamp"]'].value,1.6);assert.equal(state.timestamp,4.8);assert.equal(state.reconstructionClockOwner,'source');
});

test('grid size controls fetch the exact new bounded wall once and preserve current reconstruction and source clocks',async()=>{
  const sizes=[8,12,16].map(count=>visualNode({wallSlots:String(count)})),requests=[],caption={textContent:''};
  const environment=appVM('state,handleClick,updateFrameWallCursor',{prepareFrames:async()=>true,fetch:async(url,options)=>{
    const request=JSON.parse(options.body);requests.push({url,request});return {ok:true,json:async()=>response(request)};
  }});
  environment.document={querySelector:selector=>selector==='[data-frame-wall-caption]'?caption:null,querySelectorAll:selector=>selector==='[data-wall-slots]'?sizes:[]};
  const {state,handleClick,updateFrameWallCursor}=environment.controls,movie={},view={renderer:{},pose:{}};
  Object.assign(state,{role:'research',snapshot,session:{session_ref:'SESSION'},sceneId:snapshot.scene_id,sceneEpoch:1,
    frameQuerySelection:input,frameWall:response(),frameWallSelection:selection(),wallSlotCount:8,timestamp:4.8,
    reconstructionClockOwner:'physical',physicalTimestamp:4.8,physicalResult:{movie},view});
  await handleClick({target:{closest:()=>sizes[2]}});
  assert.deepEqual(requests,[{url:'/api/camera_frame_wall',request:{session_ref:'SESSION',scene_id:snapshot.scene_id,...selection(16)}}]);
  assert.equal(state.wallSlotCount,16);assert.equal(state.frameWall.frames.length,16);assert.match(caption.textContent,/2 個實際鏡頭 · 16 格分時影格/);
  await handleClick({target:{closest:()=>sizes[2]}});updateFrameWallCursor(6);assert.equal(requests.length,1);
  assert.equal(state.view,view);assert.equal(state.physicalResult.movie,movie);assert.equal(state.timestamp,4.8);assert.equal(state.physicalTimestamp,4.8);assert.equal(state.reconstructionClockOwner,'physical');
});

test('actual Office early-segment wall accepts arithmetic endpoint noise while rejecting real time-scope overflow',()=>{
  const selected={...selection(),end:3.2},result=response(selected);
  // Exact metadata values observed from source-index sampling at 0..3.2 s / 8 slots.
  const samples=[
    [0,0,0,'EXACT'],
    [1.0666666666666667,1,-0.06666666666666665,'NEAREST_AVAILABLE'],
    [2.1333333333333333,2.2,0.06666666666666687,'NEAREST_AVAILABLE'],
    [3.2000000000000006,3.2,-4.440892098500626e-16,'NEAREST_AVAILABLE'],
  ];
  result.frames.forEach((frame,slot)=>{
    const [requested_timestamp,timestamp,time_offset_s,status]=samples[Math.floor(slot/2)];
    Object.assign(frame,{requested_timestamp,timestamp,time_offset_s,status});
  });
  const original=structuredClone(result);
  assert.equal(result.frames[6].requested_timestamp>selected.end,true);
  assert.equal(validateFrameWallResponse(result,selected,snapshot),result);
  assert.deepEqual(result,original); // Validation must not rewrite actual source metadata.
  for(const timestamp of [-0.00001,3.20001]){
    const outside=structuredClone(result);outside.frames[6].requested_timestamp=timestamp;
    assert.throws(()=>validateFrameWallResponse(outside,selected,snapshot),/範圍/);
  }
  const wrongScope=structuredClone(result);wrongScope.selection.time_range=[0,3.20001];
  assert.throws(()=>validateFrameWallResponse(wrongScope,selected,snapshot),/來源|範圍/);
});

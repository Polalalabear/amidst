import {sourceAnnotations,cameraOverlayModel,cameraOverlaySVG,FRUSTUM_LABEL,ANNOTATION_LABEL} from './geometry.mjs';
import {contactQualityStyle,controlGate,unavailableLayers,LAYER_LABELS,defaultSceneId,sceneEntryState} from './scene-presets.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {presentationData,presentationJSON} from './presentation-data.mjs';
import {motionPanelHTML} from './blender-motion.mjs';
import {crossCameraPanelHTML,physicalPanelHTML} from './cross-camera.mjs';
import {
  supportsFrameQuery,frameQuerySelection,invalidateFrameQuery,frameQueryRequestIsCurrent,
  runFrameQuery,frameQueryItemsHTML,frameSourceLabel,portFlowHTML,sceneReviewAllowed,motionSelection,
} from './app.mjs';

const snapshot={capabilities:{frame_query:true},time_range:[0,9.8],cameras:[{camera_id:'CAM_A'},{camera_id:'CAM_B'}]};
const values={camera_ids:['CAM_A','CAM_B'],start:'0',end:'9.8',target_timestamp:'4.9',top_k:'3',behavior_intent:'walking'};
const selection=()=>frameQuerySelection(values,snapshot);
const target=()=>({role:'research',sceneEpoch:2,sceneId:'blender-office',session:{session_ref:'session-A'},frameQueryEpoch:0,frameQuery:null});

test('baseline query validates exact scene scope and preserves camera ordering',()=>{
  const result=selection();
  assert.deepEqual(result,{camera_ids:['CAM_A','CAM_B'],start:0,end:9.8,target_timestamp:4.9,top_k:3,behavior_intent:'walking'});
  result.camera_ids.pop();assert.equal(values.camera_ids.length,2);
  assert.equal(supportsFrameQuery({}),false);
  assert.throws(()=>frameQuerySelection(values,{...snapshot,capabilities:{}}),/未提供/);
  for(const cameras of [[],['OTHER'],['CAM_A','CAM_A'],['CAM_A','CAM_B','CAM_A','CAM_B','CAM_A']]){
    assert.throws(()=>frameQuerySelection({...values,camera_ids:cameras},snapshot),/鏡頭/);
  }
});

test('empty, unbounded and malformed baseline input cannot silently become a zero-time query',()=>{
  for(const change of [
    {start:''},{end:null},{target_timestamp:undefined},{top_k:''},{start:'-0.1'},
    {end:'10'},{start:'5',end:'4'},{target_timestamp:'10'},{target_timestamp:'NaN'},
    {top_k:'6'},{top_k:'1.2'},{behavior_intent:'confirmed_running'},
  ])assert.throws(()=>frameQuerySelection({...values,...change},snapshot));
});

test('motion reconstruction validates only its own camera/time inputs, independent of Top-K and target timestamp',()=>{
  assert.deepEqual(motionSelection({...values,start:'2',end:'4',target_timestamp:'4.9',top_k:'',behavior_intent:''},snapshot),{
    camera_ids:['CAM_A','CAM_B'],start:2,end:4,
  });
  assert.throws(()=>motionSelection({...values,start:'',end:'4'},snapshot));
  assert.throws(()=>motionSelection({...values,camera_ids:['OTHER']},snapshot));
});

test('complete baseline request has no Agent contract and commits only its current response',async()=>{
  const state=target(),requests=[];
  const result={provider:'LOCAL_DETERMINISTIC_BASELINE',agent_used:false,status:'OK',items:[{rank:1,camera_id:'CAM_A',timestamp:4.8}]};
  assert.equal(await runFrameQuery(state,selection(),async request=>{requests.push(request);return result;}),true);
  assert.deepEqual(requests,[{scene_id:'blender-office',...selection()}]);
  assert.equal('agent_input' in requests[0],false);assert.equal('guide_ref' in requests[0],false);
  assert.equal(state.frameQuery,result);assert.equal(state.frameQueryPending,false);
});

test('rapid unsaved form edits reject an old response, even if the user returns to the same values',async()=>{
  const state=target(),pending=[];
  const old=runFrameQuery(state,selection(),()=>new Promise(resolve=>pending.push(resolve)));
  invalidateFrameQuery(state,{...values,target_timestamp:''});
  assert.equal(state.frameQuerySelection.target_timestamp,'');assert.equal(state.frameQueryPending,false);
  invalidateFrameQuery(state,values);
  const fresh=runFrameQuery(state,selection(),()=>new Promise(resolve=>pending.push(resolve)));
  pending[1]({status:'OK',items:[{camera_id:'CAM_B',timestamp:5}]});assert.equal(await fresh,true);
  pending[0]({status:'OK',items:[{camera_id:'CAM_A',timestamp:4}]});assert.equal(await old,false);
  assert.equal(state.frameQuery.items[0].camera_id,'CAM_B');
});

test('scene, session and role changes reject all late baseline replies and late errors',async()=>{
  for(const mutate of [
    state=>state.sceneEpoch++,state=>state.sceneId='blender-auditorium',
    state=>state.session={session_ref:'session-B'},state=>state.role='management',
  ]){
    const state=target();let finish;
    const old=runFrameQuery(state,selection(),()=>new Promise(resolve=>{finish=resolve;}));
    mutate(state);finish({status:'OK',items:[{camera_id:'CAM_A'}]});
    assert.equal(await old,false);assert.equal(state.frameQuery,null);
    const ticket={sceneEpoch:2,sceneId:'blender-office',sessionRef:'session-A',frameQueryEpoch:state.frameQueryEpoch};
    assert.equal(frameQueryRequestIsCurrent(state,ticket),false);
  }
  const state=target();let reject;
  const old=runFrameQuery(state,selection(),()=>new Promise((_,fail)=>{reject=fail;}));
  invalidateFrameQuery(state,values);reject(Error('old scope failed'));
  assert.equal(await old,false);
});

test('current errors preserve intent and clear pending state instead of inventing another scene result',async()=>{
  const state=target();
  await assert.rejects(runFrameQuery(state,selection(),async()=>{throw Error('SOURCE_UNAVAILABLE');}),/SOURCE_UNAVAILABLE/);
  assert.equal(state.frameQuery,null);assert.equal(state.frameQueryPending,false);
  assert.deepEqual(state.frameQuerySelection.camera_ids,['CAM_A','CAM_B']);
});

test('Top-K messages distinguish source image, substitute target and unknown behavior without exposing record IDs',()=>{
  const html=frameQueryItemsHTML({items:[{rank:1,camera_id:'CAM_A',timestamp:4.8,
    frame_ref:'internal-frame-secret',event_ref:'event:private:123',projection_status:'PROJECTED',
    rank_reasons:['RELIABLE_COMPONENT_FIRST','VALID_FLOOR_PROJECTION','event:private:123','<script>bad()</script>'],
    bbox_xyxy:[10,20,30,40],contact_pixel:[20,39],world_position:[1,2,0],
    selection_reason:'FIRST_BEST_PER_CAMERA'}]},{snapshot,cameraLabel:()=>'<CAM A>'});
  assert.match(html,/第 1 個畫面/);assert.match(html,/4\.8 s/);
  assert.match(html,/Blender camera 截圖/);assert.match(html,/橙色目標為替代資料/);assert.match(html,/行為未確認/);
  assert.doesNotMatch(html,/internal-frame-secret|event:private:123|<script>|<CAM A>/);
  assert.match(html,/&lt;CAM A&gt;/);assert.match(html,/&lt;script&gt;/);
  assert.match(html,/可靠像素區塊/);assert.match(html,/有效地面投影/);assert.match(html,/最佳代表畫面/);
  assert.match(html,/bbox_xyxy/);assert.match(html,/contact_pixel/);
  assert.match(frameQueryItemsHTML({items:[]}),/不以其他場景補圖/);
  assert.equal(frameSourceLabel({},{}),'模擬來源影像');
});

test('source port receipt renders per-layer actual, substitute and deferred designations',()=>{
  const html=portFlowHTML({ports:[
    {port:'source.rgb',from_layer:'source',to_layer:'measurement',status:'PASS',data_kind:'ACTUAL_BLENDER',input:{},output:{}},
    {port:'graph.gaps',from_layer:'graph',to_layer:'history',status:'PASS',source_kind:'SUBSTITUTE',input:{},output:{}},
    {port:'reconstruction.video',from_layer:'curve',to_layer:'video',status:'DEFERRED',data_source:'DEFERRED',input:{},output:{}},
  ]});
  assert.match(html,/本層資料：ACTUAL_BLENDER/);assert.match(html,/本層資料：SUBSTITUTE/);assert.match(html,/本層資料：DEFERRED/);
});

test('read-only Blender source exposes no human-review entry and rejects stale review controls',async()=>{
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const environment={contactQualityStyle,controlGate,unavailableLayers,LAYER_LABELS,defaultSceneId,sceneEntryState,sourceAnnotations,cameraOverlayModel,cameraOverlaySVG,FRUSTUM_LABEL,ANNOTATION_LABEL,presentationData,presentationJSON,motionPanelHTML,crossCameraPanelHTML,physicalPanelHTML};
  runInNewContext(source+'\nglobalThis.api={state,sidebar,workspaceTabs,inspector,dashboard,workspace,handleClick};',environment);
  const {state,sidebar,workspaceTabs,inspector,dashboard,workspace,handleClick}=environment.api;
  Object.assign(state,{role:'research',sceneId:'blender-office',selectedObject:'camera:CAM_A',
    snapshot:{...snapshot,capabilities:{frame_query:true,scene_review:false},label:'Blender Office',objects:[{
      object_id:'camera:CAM_A',kind:'CAMERA',label:'CAM_A',semantic:'CAMERA',editable_fields:[],
      authority:'SOURCE_BOUND_CALIBRATION',properties:{fx:500},
    }]}});
  const html=[sidebar(),workspaceTabs(),inspector(),dashboard()].join('\n');
  assert.doesNotMatch(html,/data-mode="review"|data-page="review"|開始審查|在人審模式中編輯/);
  assert.match(html,/原來源唯讀/);assert.match(html,/校正已綁定/);assert.match(html,/SOURCE_BOUND_CALIBRATION/);
  for(const dataset of [{page:'review'},{mode:'review'}]){
    await handleClick({target:{closest:()=>({dataset,disabled:false})}});
    assert.equal(state.page,'workspace');assert.equal(state.mode,'display');
  }
  state.page='review';state.mode='review';
  assert.doesNotMatch(workspace(),/id="draft-form"|data-mode="review"/);
  assert.equal(state.page,'workspace');assert.equal(state.mode,'display');
  assert.equal(sceneReviewAllowed(state.snapshot),false);
  assert.equal(sceneReviewAllowed({capabilities:{scene_review:true}}),true);
});

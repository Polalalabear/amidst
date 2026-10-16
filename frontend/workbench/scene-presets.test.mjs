import test from 'node:test';
import assert from 'node:assert/strict';
import {CONTACT_FLAG_TAG,CONTACT_UNEVALUATED_TAG,contactQualityStyle,styleContactSample,contactQualityReadout,layerAvailability,unavailableLayers,controlGate,unavailableNotice,defaultSceneId,sceneEntryState} from './scene-presets.mjs';
import {candidateEvidenceOverlays,candidateEvidenceSVG,crossCameraCursor} from './cross-camera.mjs';
import {physicalReviewScenePlan,physicalReviewEvidenceFrame} from './physical-review.mjs';
import {officeReviewResult} from './physical-review-office.fixture.mjs';
import {layerAvailabilityHTML,unavailablePanelHTML,contactQualityHTML} from './app.mjs';

const quality=(status,reasons=[])=>({version:'rgb-mask-contact-v2',status,reasons,pixel_sensitivity_m:status==='NOT_EVALUATED'?null:.15,authority:'QUALITY_FLAG_ONLY_POSITION_UNCHANGED'});
const AT_4_4=['LOW_INCIDENCE','CONTACT_OCCLUDED','AMBIGUOUS_MERGE'];
// Office flags from the C3 acceptance record: 0.4/0.6/1.8/2.0 s LOW_INCIDENCE; 4.4 s all three reasons on both observations.
const officeFlag=t=>Math.abs(t-4.4)<1e-9?quality('FLAGGED',AT_4_4):[0.4,0.6,1.8,2].some(v=>Math.abs(v-t)<1e-9)?quality('FLAGGED',['LOW_INCIDENCE']):null;
function flaggedOfficeResult() {
  const result=officeReviewResult();
  for(const sample of result.synchronized_evidence.samples){const q=officeFlag(sample.timestamp);if(q&&sample.state==='PROJECTED_OBSERVATION')sample.contact_quality=q;}
  return result;
}

test('contact_quality maps FLAGGED to a hollow dashed marker with 接地點不可靠 and reasons, PASS to normal, NOT_EVALUATED to a neutral tag',()=>{
  const flagged=contactQualityStyle(quality('FLAGGED',AT_4_4));
  assert.deepEqual({...flagged},{status:'FLAGGED',marker:'flagged',hollow:true,dashed:true,tag:CONTACT_FLAG_TAG,reasons:AT_4_4,
    label:'接地點不可靠（LOW_INCIDENCE、CONTACT_OCCLUDED、AMBIGUOUS_MERGE）'});
  assert.equal(CONTACT_FLAG_TAG,'接地點不可靠');
  assert.deepEqual(contactQualityStyle(quality('PASS')),{status:'PASS',marker:'normal',hollow:false,dashed:false,tag:null,reasons:[],label:''});
  const neutral=contactQualityStyle(quality('NOT_EVALUATED',['AMBIGUOUS_MAPPING']));
  assert.equal(neutral.marker,'neutral');assert.equal(neutral.hollow,false);assert.equal(neutral.tag,CONTACT_UNEVALUATED_TAG);
  assert.equal(neutral.label,'接地未評估（AMBIGUOUS_MAPPING）');
  // No field or an unknown status: drawn exactly as before.
  for(const value of [undefined,null,{},{status:'SOMETHING'}])assert.deepEqual(contactQualityStyle(value),{status:null,marker:'normal',hollow:false,dashed:false,tag:null,reasons:[],label:''});
});
test('a flag never moves, hides or interpolates a position',()=>{
  const position=[34.285480667483995,48.18377357389123,0.4959475898742678];
  const sample={timestamp:.4,state:'PROJECTED_OBSERVATION',world_position:position,bbox_xyxy:[10,20,30,60],contact_pixel:[19.5,59],contact_quality:quality('FLAGGED',['LOW_INCIDENCE'])};
  const styled=styleContactSample(sample);
  assert.equal(styled.world_position,position);assert.deepEqual(styled.world_position,[34.285480667483995,48.18377357389123,0.4959475898742678]);
  assert.deepEqual(styled.contact_pixel,[19.5,59]);assert.deepEqual(styled.bbox_xyxy,[10,20,30,60]);assert.equal(styled.timestamp,.4);
  assert.equal(styled.contact_style.marker,'flagged');assert.equal(sample.contact_style,undefined);

  // Physical review: the same samples are shown at the same ticks and XYZ with or without flags; flags ride along.
  const plain=physicalReviewScenePlan(officeReviewResult()),flagged=physicalReviewScenePlan(flaggedOfficeResult());
  assert.deepEqual(flagged.samples.map(({contact_quality,...rest})=>rest),plain.samples);
  for(const t of [0,0.2,0.4,0.6,1.8,2,4.4,6,8.6]){
    const a=physicalReviewEvidenceFrame(plain,t),b=physicalReviewEvidenceFrame(flagged,t);
    assert.deepEqual(b.samples.map(s=>[s.evidence_key,s.world_position]),a.samples.map(s=>[s.evidence_key,s.world_position]));
    assert.equal(b.total,a.total);
  }
  const at44=physicalReviewEvidenceFrame(flagged,4.4).samples;
  assert.equal(at44.length,2);assert.ok(at44.every(s=>s.contact_quality.status==='FLAGGED'));
  const lines=contactQualityReadout(at44,{cameraLabel:id=>id.split('_').pop()});
  assert.ok(lines.length>=1&&lines.every(line=>line.startsWith('接地點不可靠（LOW_INCIDENCE、CONTACT_OCCLUDED、AMBIGUOUS_MERGE）')&&line.endsWith('4.4 s')));
  for(const t of [0.4,0.6,1.8,2])assert.deepEqual(contactQualityReadout(physicalReviewEvidenceFrame(flagged,t).samples,{cameraLabel:id=>id.split('_').pop()}),[`接地點不可靠（LOW_INCIDENCE） · FRONT · ${t.toFixed(1)} s`]);
  assert.deepEqual(contactQualityReadout(physicalReviewEvidenceFrame(flagged,0.2).samples),[]);

  // 2D tile overlay: same bbox and contact pixel; a dashed ring is added around that same pixel with the tag and reasons.
  const path={key:'1:1',caption:'候選 1 · 路徑 1',associated:true,color:'#76d9cf',selected:true,samples:[
    {timestamp:4.4,state:'PROJECTED_OBSERVATION',camera_id:'CAM_FRONT',frame_ref:'frame:a',world_position:[1,2,0],connect_from_previous:false,bbox_xyxy:[100,40,140,120],contact_pixel:[119.5,119],contact_quality:quality('FLAGGED',AT_4_4)},
    {timestamp:4.6,state:'PROJECTED_OBSERVATION',camera_id:'CAM_FRONT',frame_ref:'frame:b',world_position:[1.1,2,0],connect_from_previous:true,bbox_xyxy:[102,40,142,120],contact_pixel:[121.5,119],contact_quality:quality('PASS')}]};
  const plan={time_range:[0,9.8],paths:[path]};
  assert.equal(crossCameraCursor(path,4.4,plan.time_range),path.samples[0]);
  const [item]=candidateEvidenceOverlays(plan,4.4,'CAM_FRONT','frame:a');
  assert.deepEqual(item.bbox_xyxy,[100,40,140,120]);assert.deepEqual(item.contact_pixel,[119.5,119]);assert.equal(item.contact_quality.status,'FLAGGED');
  const svg=candidateEvidenceSVG([item],{camera_id:'CAM_FRONT',width:960,height:540});
  assert.match(svg,/data-contact-quality="FLAGGED"/);assert.match(svg,/<circle data-contact-flag cx="119.5" cy="119"/);
  assert.match(svg,/接地點不可靠（LOW_INCIDENCE、CONTACT_OCCLUDED、AMBIGUOUS_MERGE）/);
  const [passItem]=candidateEvidenceOverlays(plan,4.6,'CAM_FRONT','frame:b');
  const passSVG=candidateEvidenceSVG([passItem],{camera_id:'CAM_FRONT',width:960,height:540});
  assert.doesNotMatch(passSVG,/data-contact-flag|接地點不可靠/);assert.match(passSVG,/data-contact-quality="PASS"/);
  assert.equal(contactQualityHTML(undefined),'');assert.match(contactQualityHTML(quality('FLAGGED',['LOW_INCIDENCE'])),/接地點不可靠（LOW_INCIDENCE）/);
});

const controlSnapshot={scene_id:'blender-contact-control',time_range:[0,9.8],cameras:[{camera_id:'CAM_1F_AUDITORIUM_FRONT'},{camera_id:'CAM_1F_AUDITORIUM_REAR'}],
  layer_availability:{perception:{status:'AVAILABLE',version:'rgb-mask-contact-v2'},
    ...Object.fromEntries(['motion','association','physical_source','physical'].map(layer=>[layer,{status:'UNAVAILABLE',reason:'NOT_MATERIALIZED_FOR_RUN'}]))},
  demo_defaults:{observation_ref:'observation:9cbc96c1203351023dc6114b',selected_timestamp:3.6,camera_ids:['CAM_1F_AUDITORIUM_FRONT','CAM_1F_AUDITORIUM_REAR'],time_range:[0,9.8],top_k:3}};
const officeSnapshot={scene_id:'blender-office',time_range:[0,9.8],cameras:[{camera_id:'CAM_1F_AUDITORIUM_FRONT'},{camera_id:'CAM_1F_AUDITORIUM_REAR'}]};

test('UNAVAILABLE layers disable their controls and show the reason; available scenes are not gated',()=>{
  assert.equal(unavailableNotice('NOT_MATERIALIZED_FOR_RUN'),'此場景未提供：NOT_MATERIALIZED_FOR_RUN');
  assert.deepEqual(unavailableLayers(controlSnapshot).map(row=>[row.layer,row.reason]),
    [['motion','NOT_MATERIALIZED_FOR_RUN'],['association','NOT_MATERIALIZED_FOR_RUN'],['physical_source','NOT_MATERIALIZED_FOR_RUN'],['physical','NOT_MATERIALIZED_FOR_RUN']]);
  assert.equal(layerAvailability(controlSnapshot,'perception').available,true);
  for(const [control,layer] of [['motion-reconstruct','motion'],['cross-camera-reconstruct','association'],['physical-reconstruct','physical_source'],['physical-review','physical_source']])
    assert.deepEqual(controlGate(controlSnapshot,control),{disabled:true,layer,reason:'NOT_MATERIALIZED_FOR_RUN',notice:'此場景未提供：NOT_MATERIALIZED_FOR_RUN'});
  // Only the unavailable layer is gated.
  const partial={layer_availability:{association:{status:'UNAVAILABLE',reason:'NOT_MATERIALIZED_FOR_RUN'}}};
  assert.equal(controlGate(partial,'motion-reconstruct').disabled,false);assert.equal(controlGate(partial,'cross-camera-reconstruct').disabled,true);
  // Office (no layer_availability) keeps every control.
  assert.deepEqual(unavailableLayers(officeSnapshot),[]);
  for(const control of ['motion-reconstruct','cross-camera-reconstruct','physical-reconstruct','physical-review'])assert.equal(controlGate(officeSnapshot,control).disabled,false);
  assert.equal(layerAvailabilityHTML(officeSnapshot),'');
  const notice=layerAvailabilityHTML(controlSnapshot);
  assert.match(notice,/data-layer-availability/);assert.equal(notice.match(/此場景未提供：NOT_MATERIALIZED_FOR_RUN/g).length,4);
  for(const layer of ['motion','association','physical_source','physical'])assert.match(notice,new RegExp(`data-unavailable-layer="${layer}"`));
  const panel=unavailablePanelHTML('跨鏡頭多解還原',controlGate(controlSnapshot,'cross-camera-reconstruct'));
  assert.match(panel,/data-unavailable-panel="association"/);assert.match(panel,/此場景未提供：NOT_MATERIALIZED_FOR_RUN/);
});

test('a scene switch keeps an in-range timestamp and applies demo_defaults without borrowing other scene data',()=>{
  assert.equal(defaultSceneId({scenes:[{scene_id:'blender-office'},{scene_id:'blender-contact-control'}]}),'blender-office');
  assert.equal(defaultSceneId({default_scene_id:'blender-contact-control',scenes:[{scene_id:'blender-office'},{scene_id:'blender-contact-control'}]}),'blender-contact-control');
  assert.equal(defaultSceneId({default_scene_id:'missing',scenes:[{scene_id:'blender-office'}]}),'blender-office');
  assert.equal(defaultSceneId({scenes:[]}),null);

  // Office 4.4 s → control: kept; demo cameras, window and Top-K applied; query target uses the demo timestamp.
  const toControl=sceneEntryState(controlSnapshot,{previousTimestamp:4.4,frameQuery:true});
  assert.equal(toControl.timestamp,4.4);assert.equal(toControl.timestampSource,'KEPT');
  assert.deepEqual(toControl.cameraIds,['CAM_1F_AUDITORIUM_FRONT','CAM_1F_AUDITORIUM_REAR']);assert.equal(toControl.cameraId,'CAM_1F_AUDITORIUM_FRONT');
  assert.deepEqual(toControl.frameQuerySelection,{camera_ids:['CAM_1F_AUDITORIUM_FRONT','CAM_1F_AUDITORIUM_REAR'],start:0,end:9.8,target_timestamp:3.6,top_k:3,behavior_intent:'walking'});
  assert.equal(toControl.demoObservationRef,'observation:9cbc96c1203351023dc6114b');
  // And back to Office: kept, no demo values carried over.
  const back=sceneEntryState(officeSnapshot,{previousTimestamp:4.4,frameQuery:true});
  assert.equal(back.timestamp,4.4);assert.equal(back.demoObservationRef,null);
  assert.deepEqual(back.frameQuerySelection,{camera_ids:['CAM_1F_AUDITORIUM_FRONT','CAM_1F_AUDITORIUM_REAR'],start:0,end:9.8,target_timestamp:4.9,top_k:3,behavior_intent:'walking'});
  // Boundaries are in range.
  assert.equal(sceneEntryState(officeSnapshot,{previousTimestamp:9.8}).timestamp,9.8);
  assert.equal(sceneEntryState(officeSnapshot,{previousTimestamp:0}).timestampSource,'KEPT');
  // Out of range or first load: demo timestamp when available, otherwise the range start.
  assert.deepEqual([sceneEntryState(controlSnapshot,{previousTimestamp:12}).timestamp,sceneEntryState(controlSnapshot,{previousTimestamp:12}).timestampSource],[3.6,'DEMO_DEFAULT']);
  assert.deepEqual([sceneEntryState(controlSnapshot).timestamp,sceneEntryState(controlSnapshot).timestampSource],[3.6,'DEMO_DEFAULT']);
  assert.deepEqual([sceneEntryState(officeSnapshot,{previousTimestamp:-1}).timestamp,sceneEntryState(officeSnapshot,{previousTimestamp:-1}).timestampSource],[0,'RANGE_START']);
  assert.equal(sceneEntryState(officeSnapshot,{previousTimestamp:NaN}).timestamp,0);
  // Demo cameras not in this scene are ignored; a frame query is only prepared for frame-query scenes.
  const foreign=sceneEntryState({...controlSnapshot,demo_defaults:{...controlSnapshot.demo_defaults,camera_ids:['CAM_ELSEWHERE'],time_range:[0,50],selected_timestamp:40}},{frameQuery:true});
  assert.deepEqual(foreign.cameraIds,['CAM_1F_AUDITORIUM_FRONT','CAM_1F_AUDITORIUM_REAR']);assert.equal(foreign.timestamp,0);
  assert.deepEqual([foreign.frameQuerySelection.start,foreign.frameQuerySelection.end,foreign.frameQuerySelection.target_timestamp],[0,9.8,4.9]);
  assert.equal(sceneEntryState(officeSnapshot).frameQuerySelection,null);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import * as Three from 'three';
import {calibratedFrustum,planarPolygon} from './geometry.mjs';
import {bodyMarkers,serverBodyMarkers} from './motion.mjs';
import {graphCaptionPlan} from './presentation-data.mjs';
import {crossCameraCursor,crossCameraScenePlan,physicalGeometryPlan} from './cross-camera.mjs';
import {physicalReviewEvidenceAt} from './physical-review.mjs';

function makeView(options={}) {
  const renderers=[];
  class Renderer {
    constructor(){this.domElement={addEventListener(){},removeEventListener(){}};this.draws=0;renderers.push(this);}
    setPixelRatio(){}setSize(){}render(){this.draws++;}dispose(){this.disposed=true;}forceContextLoss(){this.contextLost=true;}
  }
  const source=readFileSync(new URL('./scene.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const environment={THREE:{...Three,WebGLRenderer:Renderer},calibratedFrustum,planarPolygon,bodyMarkers,serverBodyMarkers,graphCaptionPlan,crossCameraCursor,physicalReviewEvidenceAt,
    window:{devicePixelRatio:1},ResizeObserver:class {observe(){}disconnect(){}},
    document:{createElement:()=>({getContext:()=>({fillRect(){},fillText(){},measureText:label=>({width:label.length*12})})})}};
  runInNewContext(source+'\nglobalThis.View=SceneView;',environment);
  const container={clientWidth:640,clientHeight:400,children:[],replaceChildren(...children){this.children=children;}};
  const objects=[{object_id:'floor',kind:'WALKABLE',geometry:{type:'polygon',points:[[0,0,0],[5,0,0],[5,5,0],[0,5,0]]}}];
  const settings={snapshot:{bounds:[0,0,5,5]},objects,onSelect(){},...options};
  return {view:new environment.View(container,settings),settings,renderers,container};
}

test('routine selections, event details and timestamps retain canvas, renderer and user camera pose',()=>{
  const {view,settings,renderers,container}=makeView();
  view.yaw=.4;view.distance=7;view.target.set(2,3,1);view.updateCamera();
  const pose=JSON.stringify(view.getPose()),canvas=container.children[0],staticObject=view.objectLayer.children[0];
  for(let i=0;i<5;i++){view.setData(settings);view.setTimestamp(i/2);}
  assert.equal(renderers.length,1);assert.equal(container.children[0],canvas);assert.equal(view.objectLayer.children[0],staticObject);
  view.setData({...settings,event:{candidates:[{polyline:[[0,0,0],[2,2,0]]}]} });
  assert.equal(view.eventLayer.children.length,1);assert.equal(view.objectLayer.children[0],staticObject);
  view.setData({...settings,selectedId:'floor'});view.setTimestamp(2);
  assert.equal(JSON.stringify(view.getPose()),pose);assert.equal(renderers[0].disposed,undefined);
  view.dispose();assert.equal(renderers[0].disposed,true);assert.equal(renderers[0].contextLost,true);
});

test('source mesh smoothing affects display materials and leaves all source vertices unchanged',()=>{
  const mesh={vertices:[[0,0,0],[1,0,0],[0,1,0]],triangles:[[0,1,2]]},original=structuredClone(mesh);
  const {view,settings}=makeView({presentation:{meshes:[mesh],routes:[]}});
  const sourceMesh=view.sourceLayer.children[0];
  assert.equal(sourceMesh.material.flatShading,false);assert.ok(sourceMesh.geometry.attributes.normal);
  assert.deepEqual(mesh,original);view.setData({...settings,presentation:{meshes:[mesh],routes:[]}});
  assert.equal(view.sourceLayer.children[0],sourceMesh);view.dispose();
});

test('renderer retains all eleven source edges with one default caption and at most five on-demand captions',()=>{
  const nodes=Array.from({length:7},(_,i)=>({id:'n'+i,position:[i,0,0],label:'CAMERA_'+i}));
  const edges=[...Array.from({length:6},(_,i)=>({from:'n0',to:'n'+(i+1),label:'登錄涵蓋關聯'})),
    ...Array.from({length:5},(_,i)=>({from:'n'+(i+1),to:'n'+(i+2),label:'預設鏡頭連結'}))];
  const graph={nodes,edges,focus_node_id:'n0',show_relation_captions:false};
  const {view,settings,renderers}=makeView({graph});
  const count=type=>view.graphLayer.children.filter(child=>child.type===type).length;
  assert.equal(count('Line'),11);assert.equal(count('Sprite'),1);
  assert.ok(view.graphLayer.children.filter(child=>child.type==='Line').every(line=>line.material.opacity<=.38));
  view.setData({...settings,graph:{...graph,show_relation_captions:true}});
  assert.equal(count('Line'),11);assert.equal(count('Sprite'),5);assert.equal(renderers.length,1);
  view.dispose();
});

test('ranked cross-camera paths and time cursors retain source geometry, renderer and camera pose across updates',()=>{
  const samples=[{timestamp:2,world_position:[1,2,.5],state:'PROJECTED_OBSERVATION',connect_from_previous:false},
    {timestamp:2.2,world_position:[1.2,2,.5],state:'INFERRED_CROSS_CAMERA',connect_from_previous:true},
    {timestamp:2.4,world_position:null,state:'MISSING',connect_from_previous:false}];
  const candidate=rank=>({rank,paths:[{camera_ids:['CAM_A','CAM_B'],samples,edge_refs:[]}]});
  const result={selection:{time_range:[2,4]},candidates:[candidate(1),candidate(2)],graph:{edges:[]}};
  const mesh={vertices:[[0,0,0],[1,0,0],[0,1,0]],triangles:[[0,1,2]]};
  const plan=crossCameraScenePlan(result,1),{view,settings,renderers,container}=makeView({crossCamera:plan,presentation:{meshes:[mesh],routes:[]}});
  const sourceMesh=view.sourceLayer.children[0],canvas=container.children[0],overlay=view.crossCameraLayer.children[0];
  view.yaw=.31;view.pitch=.85;view.distance=7;view.target.set(2,3,1);view.updateCamera();const pose=JSON.stringify(view.getPose());
  const lines=view.crossCameraLayer.children.filter(child=>child.type==='Line');
  assert.equal(lines.length,2);assert.ok(lines.every(line=>line.material.type==='LineDashedMaterial'));
  assert.deepEqual(Array.from(lines[0].geometry.attributes.position.array).map(value=>Math.round(value*1e5)/1e5),[1,2,.5,1.2,2,.5]);
  for(let i=0;i<3;i++)view.setData(settings);
  assert.equal(view.crossCameraLayer.children[0],overlay);assert.equal(view.sourceLayer.children[0],sourceMesh);assert.equal(container.children[0],canvas);
  view.setTimestamp(2.2);assert.equal(view.crossCameraCursors[0].cursor.visible,true);assert.equal(view.crossCameraCursors[0].cursor.position.x,1.2);
  view.setTimestamp(2.4);assert.equal(view.crossCameraCursors[0].cursor.visible,false);
  view.setTimestamp(3.2);assert.equal(view.crossCameraCursors[0].cursor.visible,false);
  view.setCrossCamera(crossCameraScenePlan(result,2));assert.equal(view.crossCameraPlan.selected_rank,2);
  assert.equal(view.sourceLayer.children[0],sourceMesh);assert.equal(renderers.length,1);assert.equal(JSON.stringify(view.getPose()),pose);
  view.dispose();
});

test('a long missing association is a grey hypothesis edge and never supplies a middle-time 3D position',()=>{
  const samples=[{timestamp:2,world_position:[1,2,.5],state:'PROJECTED_OBSERVATION',connect_from_previous:false},
    {timestamp:2.9,world_position:null,state:'MISSING',connect_from_previous:false},
    {timestamp:3.8,world_position:[3,4,.5],state:'PROJECTED_OBSERVATION',connect_from_previous:false}];
  const result={selection:{time_range:[2,4]},candidates:[{rank:1,paths:[{camera_ids:['CAM_A','CAM_B'],samples,edge_refs:['edge:ABC']}]}],
    graph:{edges:[{edge_ref:'edge:ABC',bridge_missing:true,from_timestamp:2,to_timestamp:3.8,from_world_position:[1,2,.5],to_world_position:[3,4,.5]}]}};
  const {view}=makeView({crossCamera:crossCameraScenePlan(result)});
  const lines=view.crossCameraLayer.children.filter(child=>child.type==='Line');assert.equal(lines.length,1);
  assert.equal(lines[0].material.type,'LineDashedMaterial');assert.equal(lines[0].material.color.getHex(),0x8292a9);
  assert.deepEqual(Array.from(lines[0].geometry.attributes.position.array),[1,2,.5,3,4,.5]);
  view.setTimestamp(2);assert.equal(view.crossCameraCursors[0].cursor.visible,true);
  view.setTimestamp(2.9);assert.equal(view.crossCameraCursors[0].cursor.visible,false);
  view.setTimestamp(3.8);assert.equal(view.crossCameraCursors[0].cursor.visible,true);
  view.setCrossCamera(null);assert.equal(view.crossCameraLayer.children.length,0);assert.equal(view.crossCameraCursors.length,0);
  view.dispose();
});

test('physical support outlines preserve source metres, holes, renderer and display mesh without becoming collision proof',()=>{
  const outline={authority:'APPROVED',role:'SOURCE_SUPPORTED_WALKABLE_ONLY',exterior:[[1,2,.5],[4,2,.5],[4,4,.5],[1,4,.5]],holes:[[[2,2.5,.5],[3,2.5,.5],[3,3.5,.5],[2,3.5,.5]]]};
  const result={source_binding:{source_sha256:'source-A'},geometry_context:{units:'METRES',source_sha256:'source-A',physical_source_sha256:'a'.repeat(64),support_polygons:[outline]}};
  const mesh={vertices:[[0,0,0],[1,0,0],[0,1,0]],triangles:[[0,1,2]]},original=structuredClone(mesh);
  const plan=physicalGeometryPlan(result),{view,settings,renderers,container}=makeView({physicalGeometry:plan,presentation:{meshes:[mesh],routes:[]}});
  const display=view.sourceLayer.children[0],canvas=container.children[0],outlineNode=view.physicalGeometryLayer.children[0];
  const loops=view.physicalGeometryLayer.children.filter(child=>child.type==='LineLoop');assert.equal(loops.length,2);
  assert.deepEqual(Array.from(loops[0].geometry.attributes.position.array),outline.exterior.flat());
  assert.deepEqual(Array.from(loops[1].geometry.attributes.position.array),outline.holes[0].flat());
  assert.equal(view.physicalGeometryLayer.children.filter(child=>child.type==='Mesh').length,0);
  view.yaw=.4;view.distance=7;view.updateCamera();const pose=JSON.stringify(view.getPose());
  for(let i=0;i<3;i++){view.setData(settings);view.setTimestamp(i/2);}
  assert.equal(view.physicalGeometryLayer.children[0],outlineNode);assert.equal(view.sourceLayer.children[0],display);assert.equal(container.children[0],canvas);assert.equal(renderers.length,1);
  view.setPhysicalGeometry(null);assert.equal(view.physicalGeometryLayer.children.length,0);assert.equal(view.sourceLayer.children[0],display);assert.deepEqual(mesh,original);assert.equal(JSON.stringify(view.getPose()),pose);
  view.dispose();
});

function reviewPlan() {
  return {review_sha256:'b'.repeat(64),source_sha256:'a'.repeat(64),selected_ref:'review-item:'+'1'.repeat(24),display_only:true,physical_certification:false,
    focus:{target:[2,3,1.5],radius:1.5,purpose:'DISPLAY_FOCUS_ONLY'},overlays:[{
      geometry_ref:'review-geometry:'+'2'.repeat(24),item_ref:'review-item:'+'1'.repeat(24),kind:'SOURCE_ANNOTATION',units:'METRES',
      vertices:[[1,2,.5],[3,2,.5],[3,4,2.5]],triangles:[[0,1,2]],rings:[],caption:'門洞 1 · 原標註範圍',authority:'HUMAN_REVIEW',display_only:true,is_aperture:false,is_collider:false,truncated:false}]};
}
test('pending review source wires remain separate, pickable and stable across source-clock ticks without moving the view',()=>{
  const plan=reviewPlan(),original=structuredClone(plan),mesh={vertices:[[0,0,0],[1,0,0],[0,1,0]],triangles:[[0,1,2]]};
  const {view,settings,renderers,container}=makeView({snapshot:{bounds:[0,0,5,5],source_binding:{source_sha256:'a'.repeat(64)}},physicalReview:plan,presentation:{meshes:[mesh],routes:[]}});
  const source=view.sourceLayer.children[0],wire=view.physicalReviewLayer.children[0],canvas=container.children[0];
  assert.equal(wire.type,'LineSegments');assert.equal(wire.material.type,'LineDashedMaterial');assert.equal(view.reviewPickables.length,1);
  assert.equal(view.physicalReviewLayer.children.filter(node=>node.type==='Mesh').length,0);
  assert.deepEqual(Array.from(wire.geometry.attributes.position.array),[1,2,.5,3,2,.5,3,2,.5,3,4,2.5,3,4,2.5,1,2,.5]);
  view.yaw=.45;view.pitch=.8;view.target.set(0,1,2);view.distance=7;view.updateCamera();const pose=JSON.stringify(view.getPose());
  for(let i=0;i<5;i++){view.setData(settings);view.setTimestamp(i*.2);}
  assert.equal(JSON.stringify(view.getPose()),pose);assert.equal(view.physicalReviewLayer.children[0],wire);assert.equal(view.sourceLayer.children[0],source);assert.equal(container.children[0],canvas);assert.equal(renderers.length,1);
  assert.equal(view.focusPhysicalReview(structuredClone(plan)),true);assert.deepEqual(Array.from(view.target.toArray()),[2,3,1.5]);
  const focused=JSON.stringify(view.getPose());view.setTimestamp(8);assert.equal(JSON.stringify(view.getPose()),focused);
  assert.deepEqual(plan,original);view.setPhysicalReview(null);assert.equal(view.physicalReviewLayer.children.length,0);assert.equal(view.reviewPickables.length,0);assert.equal(view.sourceLayer.children[0],source);
  view.dispose();
});
test('pending review source rings keep holes and rejects changed source, unbounded or certified plans',()=>{
  const plan=reviewPlan();plan.overlays[0].kind='APPROVED_SUPPORT_RING';plan.overlays[0].vertices=[];plan.overlays[0].triangles=[];
  plan.overlays[0].rings=[[[0,0,.5],[5,0,.5],[5,5,.5]],[[1,1,.5],[2,1,.5],[2,2,.5]]];
  const {view}=makeView({snapshot:{bounds:[0,0,5,5],source_binding:{source_sha256:'a'.repeat(64)}},physicalReview:plan});
  assert.equal(view.physicalReviewLayer.children.filter(node=>node.type==='LineLoop').length,2);
  assert.deepEqual(Array.from(view.physicalReviewLayer.children[1].geometry.attributes.position.array),plan.overlays[0].rings[1].flat());
  for(const mutate of [p=>p.source_sha256='stale',p=>p.overlays[0].is_collider=true,p=>p.overlays[0].rings='invalid',p=>p.overlays[0].vertices=Array.from({length:8193},()=>[0,0,0])]){
    const invalid=structuredClone(plan);mutate(invalid);view.setPhysicalReview(invalid);assert.equal(view.physicalReviewLayer.children.length,0);assert.equal(view.focusPhysicalReview(invalid),false);
  }
  view.dispose();
});
test('review source-clock markers show nominal policy wire body only at usable source samples and leave missing motion empty',()=>{
  const plan=reviewPlan();plan.selected_kind='BODY_CLEARANCE';plan.time_range=[0,2];plan.nominal_body={radius_m:.3,height_m:1.7,authority:'APPROVED_POLICY_NOT_MEASURED_BODY',measured_body:false};
  plan.samples=[{timestamp:0,world_position:[1,2,.5],state:'PROJECTED_OBSERVATION',camera_id:'CAM_A',source_camera_ids:[],candidate_refs:['candidate:A']},
    {timestamp:.2,world_position:[1.2,2,.5],state:'INFERRED_INTERPOLATION',camera_id:'CAM_A',source_camera_ids:[],candidate_refs:['candidate:A']},
    {timestamp:1,world_position:null,state:'MISSING',camera_id:null,source_camera_ids:['CAM_A','CAM_B'],candidate_refs:['candidate:A']},
    {timestamp:2,world_position:[3,2,.5],state:'PROJECTED_OBSERVATION',camera_id:'CAM_B',source_camera_ids:[],candidate_refs:['candidate:A']}];
  plan.missing_intervals=[{time_range:[.2,2],camera_ids:['CAM_A','CAM_B'],candidate_ref:'candidate:A'}];
  const {view,renderers}=makeView({snapshot:{bounds:[0,0,5,5],source_binding:{source_sha256:'a'.repeat(64)}},physicalReview:plan});
  const marker=view.reviewEvidenceMarkers[0],wire=marker.children.find(child=>child.userData.nominalBody);
  assert.equal(wire.type,'LineSegments');wire.geometry.computeBoundingBox();
  assert.ok(Math.abs(wire.geometry.boundingBox.max.z-.85)<1e-6);assert.ok(Math.abs(wire.geometry.boundingBox.min.x+.3)<1e-6);assert.equal(wire.position.z,.85);
  assert.equal(marker.visible,true);assert.equal(wire.visible,true);assert.deepEqual(Array.from(marker.position.toArray()),[1,2,.5]);
  assert.equal(marker.children[0].material.color.getHex(),0x66dfd0);
  const pose=JSON.stringify(view.getPose());view.setTimestamp(.2);
  assert.equal(marker.visible,true);assert.equal(wire.visible,false);assert.equal(marker.children[0].material.color.getHex(),0xffc266);assert.equal(marker.userData.evidenceState,'INFERRED_INTERPOLATION');
  view.setTimestamp(.25);assert.equal(marker.visible,false);view.setTimestamp(1);assert.equal(marker.visible,false);
  view.setTimestamp(2);assert.equal(marker.visible,true);assert.equal(wire.visible,true);assert.equal(marker.position.x,3);assert.equal(JSON.stringify(view.getPose()),pose);
  assert.equal(renderers.length,1);assert.equal(view.reviewEvidenceMarkers[0],marker);
  const noPolicy={...plan,nominal_body:null};view.setPhysicalReview(noPolicy);assert.ok(view.reviewEvidenceMarkers.every(row=>row.children.every(child=>!child.userData.nominalBody)));
  view.dispose();
});

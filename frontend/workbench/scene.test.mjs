import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import * as Three from 'three';
import {calibratedFrustum,planarPolygon,worldDirectionSVG} from './geometry.mjs';
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
  const environment={THREE:{...Three,WebGLRenderer:Renderer},calibratedFrustum,planarPolygon,worldDirectionSVG,bodyMarkers,serverBodyMarkers,graphCaptionPlan,crossCameraCursor,physicalReviewEvidenceAt,
    window:{devicePixelRatio:1},ResizeObserver:class {observe(){}disconnect(){}},
    document:{createElement:tag=>tag==='div'?{style:{},attributes:{},setAttribute(key,value){this.attributes[key]=value;},remove(){const nodes=this.parentNode?.children;if(nodes)nodes.splice(nodes.indexOf(this),1);},set innerHTML(value){this.markup=value;this.writes=(this.writes??0)+1;}}:({getContext:()=>({fillRect(){},fillText(){},measureText:label=>({width:label.length*12})})})}};
  runInNewContext(source+'\nglobalThis.View=SceneView;',environment);
  const container={clientWidth:640,clientHeight:400,children:[],style:{position:''},replaceChildren(...children){this.children=children;},append(node){node.parentNode=this;this.children.push(node);}};
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

test('Blender world compass follows orbit bearing while retaining canvas, source geometry and pose on time and resize updates',()=>{
  const snapshot={bounds:[0,0,5,5],evidence_level:'BLENDER_CAMERA_RGB_PIXEL_BASELINE',
    coordinates:{coordinate_frame:'RIGHT_HANDED_XYZ_Z_UP'},source_binding:{units:'METRES',source_sha256:'a'.repeat(64)}};
  const originalSnapshot=structuredClone(snapshot),mesh={vertices:[[0,0,0],[1,0,0],[0,1,0]],triangles:[[0,1,2]]},original=structuredClone(mesh);
  const {view,settings,renderers,container}=makeView({snapshot,presentation:{meshes:[mesh],routes:[]}});
  const compass=view.worldDirectionsCompass,canvas=container.children[0],sourceMesh=view.sourceLayer.children[0];
  assert.equal(compass.className,'world-directions-compass');assert.equal(container.children[1],compass);
  assert.ok(compass.style.cssText.includes('pointer-events:none'));assert.ok(compass.attributes['aria-label'].includes('僅表示方向'));
  assert.equal(container.style.position,'relative');assert.ok(compass.markup.includes('來源世界軸'));
  const markup=compass.markup,writes=compass.writes,pose=JSON.stringify(view.getPose());
  for(let i=0;i<4;i++){view.setTimestamp(i/2);view.setData(settings);container.clientWidth+=10;view.resize();}
  assert.equal(view.worldDirectionsCompass,compass);assert.equal(compass.writes,writes);
  assert.equal(compass.markup,markup);assert.equal(JSON.stringify(view.getPose()),pose);
  view.yaw+=.31;view.pitch=.85;view.updateCamera();view.render();
  assert.equal(view.worldDirectionsCompass,compass);assert.notEqual(compass.markup,markup);
  const orbitPose=JSON.stringify(view.getPose());view.target.set(2,3,.5);view.distance=7;view.updateCamera();view.render();
  const translatedPose=JSON.stringify(view.getPose()),bearingMarkup=compass.markup;
  assert.notEqual(translatedPose,orbitPose);view.resize();view.setTimestamp(2.4);
  assert.equal(compass.markup,bearingMarkup);assert.equal(JSON.stringify(view.getPose()),translatedPose);
  assert.equal(renderers.length,1);assert.equal(container.children[0],canvas);assert.equal(view.sourceLayer.children[0],sourceMesh);
  assert.deepEqual(mesh,original);assert.deepEqual(snapshot,originalSnapshot);
  view.setData({...settings,snapshot:{...snapshot,evidence_level:'SYNTHETIC'}});
  assert.equal(view.worldDirectionsCompass,null);assert.equal(container.children.length,1);assert.equal(container.style.position,'');
  view.setData(settings);const remounted=view.worldDirectionsCompass;
  assert.notEqual(remounted,compass);assert.equal(container.children.length,2);assert.equal(view.sourceLayer.children[0],sourceMesh);
  view.dispose();view.dispose();assert.equal(view.worldDirectionsCompass,null);assert.equal(container.children.length,1);
  assert.equal(container.style.position,'');assert.equal(renderers[0].disposed,true);
});

test('world compass is absent for unbound sources or unsupported coordinate conventions',()=>{
  const valid={bounds:[0,0,5,5],evidence_level:'BLENDER_CAMERA_RGB_PIXEL_BASELINE',
    coordinates:{coordinate_frame:'RIGHT_HANDED_XYZ_Z_UP'},source_binding:{units:'METRES',source_sha256:'a'.repeat(64)}};
  const {view,settings,container}=makeView();
  assert.equal(view.worldDirectionsCompass,undefined);assert.equal(container.children.length,1);
  for(const snapshot of [{...valid,source_binding:null},{...valid,source_binding:{...valid.source_binding,source_sha256:'unverified'}},
    {...valid,source_binding:{...valid.source_binding,units:'BLENDER_UNITS'}},{...valid,coordinates:{coordinate_frame:'OTHER'}}]){
    view.setData({...settings,snapshot});assert.equal(container.children.length,1);assert.equal(container.style.position,'');
  }
  view.dispose();
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

function clippedAnnotationPlan() {
  const plan=reviewPlan(),overlay=plan.overlays[0];
  const min=.3705,max=3.8285,target=3.29594759;
  overlay.vertices=[[1,2,min],[3,2,min],[3,4,min],[1,4,min],[1,2,max],[3,2,max],[3,4,max],[1,4,max]];
  overlay.triangles=[[0,1,2],[0,2,3],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]];
  overlay.display_adjustment={kind:'ANNOTATION_DISPLAY_TOP_CLIP',original_top_z:max,target_top_z:target,authority:'LOCAL_DISPLAY_ONLY_NOT_APERTURE'};
  overlay.display_vertices=overlay.vertices.map(([x,y,z])=>[x,y,Math.min(z,target)]);
  overlay.caption='門洞顯示框 · 上緣對齊局部顯示上限，非門孔量測';
  plan.selected_kind='PORTAL_APERTURE';return plan;
}
function wireTop(view) {
  const wire=view.physicalReviewLayer.children.find(node=>node.type==='LineSegments');
  const coordinates=wire.geometry.attributes.position.array;
  return Math.max(...Array.from(coordinates).filter((_,index)=>index%3===2));
}
test('local annotation top clipping lowers only the displayed wire while retaining raw vertices, source mesh, renderer and pose',()=>{
  const clipped=clippedAnnotationPlan(),raw=structuredClone(clipped);delete raw.overlays[0].display_vertices;delete raw.overlays[0].display_adjustment;
  const sourceMesh={vertices:[[0,0,0],[1,0,0],[0,1,0]],triangles:[[0,1,2]]},originalMesh=structuredClone(sourceMesh),originalRaw=structuredClone(raw),originalClipped=structuredClone(clipped);
  const {view,settings,renderers,container}=makeView({snapshot:{bounds:[0,0,5,5],source_binding:{source_sha256:'a'.repeat(64)}},physicalReview:raw,presentation:{meshes:[sourceMesh],routes:[]}});
  const mesh=view.sourceLayer.children[0],canvas=container.children[0];
  assert.ok(Math.abs(wireTop(view)-3.8285)<1e-6);
  view.yaw=.27;view.pitch=.85;view.distance=7;view.target.set(2,3,1);view.updateCamera();const pose=JSON.stringify(view.getPose());
  view.setPhysicalReview(clipped);assert.ok(Math.abs(wireTop(view)-3.29594759)<1e-6);
  assert.equal(view.physicalReviewPlan.physical_certification,false);assert.equal(view.physicalReviewPlan.overlays[0].is_aperture,false);assert.equal(view.physicalReviewPlan.overlays[0].is_collider,false);
  const wire=view.physicalReviewLayer.children.find(node=>node.type==='LineSegments');
  assert.equal(wire.material.type,'LineDashedMaterial');assert.equal(view.physicalReviewLayer.children.filter(node=>node.type==='Mesh').length,0);
  for(let tick=0;tick<3;tick++){view.setData({...settings,physicalReview:clipped});view.setTimestamp(tick*.2);}
  assert.equal(view.physicalReviewLayer.children.find(node=>node.type==='LineSegments'),wire);
  assert.equal(view.sourceLayer.children[0],mesh);assert.equal(container.children[0],canvas);assert.equal(renderers.length,1);assert.equal(JSON.stringify(view.getPose()),pose);
  assert.deepEqual(raw,originalRaw);assert.deepEqual(clipped,originalClipped);assert.deepEqual(sourceMesh,originalMesh);
  assert.equal(clipped.overlays[0].vertices[4][2],3.8285);
  view.setPhysicalReview(raw);assert.ok(Math.abs(wireTop(view)-3.8285)<1e-6);assert.equal(JSON.stringify(view.getPose()),pose);view.dispose();
});

test('derived review vertices reject changed XY/lower edges, non-annotation kinds, invalid caps and authority upgrades',()=>{
  const {view}=makeView({snapshot:{bounds:[0,0,5,5],source_binding:{source_sha256:'a'.repeat(64)}}});
  const changes=[
    plan=>plan.source_sha256='f'.repeat(64),
    plan=>plan.overlays[0].display_vertices[0][0]+=.1,
    plan=>plan.overlays[0].display_vertices[0][1]+=.1,
    plan=>plan.overlays[0].display_vertices[0][2]-=.1,
    plan=>plan.overlays[0].display_vertices[4][2]+=.1,
    plan=>plan.overlays[0].display_vertices.pop(),
    plan=>plan.overlays[0].display_vertices[0].push(1),
    plan=>plan.overlays[0].display_vertices[4][2]=NaN,
    plan=>plan.overlays[0].kind='SOURCE_TRIANGLES',
    plan=>plan.overlays[0].kind='APPROVED_SUPPORT_RING',
    plan=>plan.overlays[0].display_adjustment.original_top_z=3.8,
    plan=>plan.overlays[0].display_adjustment.target_top_z=NaN,
    plan=>plan.overlays[0].display_adjustment.target_top_z=.3705,
    plan=>plan.overlays[0].display_adjustment.target_top_z=3.8285,
    plan=>plan.overlays[0].display_adjustment.target_top_z=4,
    plan=>plan.overlays[0].display_adjustment.authority='APPROVED',
    plan=>plan.overlays[0].display_adjustment.kind='APERTURE_GEOMETRY',
    plan=>plan.overlays[0].display_adjustment.approved=true,
    plan=>delete plan.overlays[0].display_vertices,
    plan=>delete plan.overlays[0].display_adjustment,
    plan=>plan.overlays[0].is_aperture=true,
    plan=>plan.overlays[0].is_collider=true,
  ];
  for(const mutate of changes){
    const invalid=clippedAnnotationPlan();mutate(invalid);const before=structuredClone(invalid);
    view.setPhysicalReview(invalid);assert.equal(view.physicalReviewPlan,null);assert.equal(view.physicalReviewLayer.children.length,0);assert.equal(view.reviewPickables.length,0);assert.equal(view.focusPhysicalReview(invalid),false);
    assert.deepEqual(invalid,before);
  }
  view.setPhysicalReview(clippedAnnotationPlan());assert.ok(Math.abs(wireTop(view)-3.29594759)<1e-6);view.dispose();
});

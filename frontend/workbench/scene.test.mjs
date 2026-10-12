import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import * as Three from 'three';
import {calibratedFrustum,planarPolygon} from './geometry.mjs';
import {bodyMarkers,serverBodyMarkers} from './motion.mjs';
import {graphCaptionPlan} from './presentation-data.mjs';
import {crossCameraCursor,crossCameraScenePlan,physicalGeometryPlan} from './cross-camera.mjs';

function makeView(options={}) {
  const renderers=[];
  class Renderer {
    constructor(){this.domElement={addEventListener(){},removeEventListener(){}};this.draws=0;renderers.push(this);}
    setPixelRatio(){}setSize(){}render(){this.draws++;}dispose(){this.disposed=true;}forceContextLoss(){this.contextLost=true;}
  }
  const source=readFileSync(new URL('./scene.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const environment={THREE:{...Three,WebGLRenderer:Renderer},calibratedFrustum,planarPolygon,bodyMarkers,serverBodyMarkers,graphCaptionPlan,crossCameraCursor,
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

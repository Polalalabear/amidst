import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import * as Three from 'three';
import {calibratedFrustum,planarPolygon} from './geometry.mjs';
import {bodyMarkers,serverBodyMarkers} from './motion.mjs';
import {graphCaptionPlan} from './presentation-data.mjs';

function makeView(options={}) {
  const renderers=[];
  class Renderer {
    constructor(){this.domElement={addEventListener(){},removeEventListener(){}};this.draws=0;renderers.push(this);}
    setPixelRatio(){}setSize(){}render(){this.draws++;}dispose(){this.disposed=true;}forceContextLoss(){this.contextLost=true;}
  }
  const source=readFileSync(new URL('./scene.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const environment={THREE:{...Three,WebGLRenderer:Renderer},calibratedFrustum,planarPolygon,bodyMarkers,serverBodyMarkers,graphCaptionPlan,
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

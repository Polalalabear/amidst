import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import * as Three from 'three';
import {calibratedFrustum,planarPolygon,worldDirectionSVG,cameraFrustumOverlay,FRUSTUM_LABEL,ANNOTATION_LABEL} from './geometry.mjs';
import {bodyMarkers,serverBodyMarkers} from './motion.mjs';
import {graphCaptionPlan,contactQualityStyle,contactQualityReadout} from './presentation-data.mjs';
import {crossCameraCursor,cameraShortLabel} from './cross-camera.mjs';
import {physicalReviewEvidenceFrame} from './physical-review.mjs';
import {blindHypothesisPlan,blindHypothesisRegionAt,HYPOTHESIS_COLOR,UNCONFIRMED_LABEL,RESTRICTED_COLOR,RESTRICTED_LABEL} from './blind-hypothesis.mjs';

// Same harness as scene.test.mjs: scene.mjs is evaluated with a stub renderer. Fixtures are MOCK, contract-shaped, not real data.
const fixture=JSON.parse(readFileSync(new URL('./fixtures/blind-hypothesis.fixture.json',import.meta.url),'utf8'));
const plans=()=>Object.fromEntries(Object.entries(structuredClone(fixture.cases)).map(([name,response])=>[name,blindHypothesisPlan(response)]));
function makeView(options={}) {
  const renderers=[];
  class Renderer {
    constructor(){this.domElement={addEventListener(){},removeEventListener(){}};this.draws=0;renderers.push(this);}
    setPixelRatio(){}setSize(){}render(){this.draws++;}dispose(){this.disposed=true;}forceContextLoss(){}
  }
  const source=readFileSync(new URL('./scene.mjs',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const labels=[];
  const environment={THREE:{...Three,WebGLRenderer:Renderer},calibratedFrustum,planarPolygon,worldDirectionSVG,cameraFrustumOverlay,FRUSTUM_LABEL,ANNOTATION_LABEL,bodyMarkers,serverBodyMarkers,graphCaptionPlan,crossCameraCursor,cameraShortLabel,physicalReviewEvidenceFrame,contactQualityStyle,contactQualityReadout,
    blindHypothesisRegionAt,HYPOTHESIS_COLOR,RESTRICTED_COLOR,
    window:{devicePixelRatio:1},ResizeObserver:class {observe(){}disconnect(){}},
    document:{createElement:tag=>tag==='div'?{style:{},attributes:{},setAttribute(key,value){this.attributes[key]=value;},remove(){},set innerHTML(value){this.markup=value;}}:({getContext:()=>({fillRect(){},fillText(text){labels.push(text);},measureText:label=>({width:label.length*12})})})}};
  runInNewContext(source+'\nglobalThis.View=SceneView;',environment);
  const container={clientWidth:640,clientHeight:400,children:[],style:{position:''},replaceChildren(...children){this.children=children;},append(node){node.parentNode=this;this.children.push(node);}};
  const objects=[{object_id:'floor',kind:'WALKABLE',geometry:{type:'polygon',points:[[0,0,0],[10,0,0],[10,6,0],[0,6,0]]}}];
  const settings={snapshot:{bounds:[0,0,10,6]},objects,onSelect(){},...options};
  return {view:new environment.View(container,settings),settings,renderers,labels};
}
const visibleGroups=view=>view.blindHypothesisLayer.children.filter(child=>child.isGroup&&child.visible);
const lines=view=>view.blindHypothesisLayer.children.filter(child=>child.isLine);

test('without a hypothesis plan the layer is empty and setTimestamp stays inert',()=>{
  const {view,settings}=makeView();
  assert.equal(view.blindHypothesisLayer.children.length,0);assert.equal(view.blindHypothesisShown,null);
  for(const t of [0,4.4,6,8.6])view.setTimestamp(t);
  view.setData({...settings,blindHypothesis:null});assert.equal(view.blindHypothesisLayer.children.length,0);
  view.dispose();
});

test('READY draws K translucent paths whose opacity falls with rank, in the hypothesis colour',()=>{
  const {ready}=plans(),{view}=makeView({blindHypothesis:ready});
  const drawn=lines(view);
  assert.equal(drawn.length,ready.paths.length);assert.ok(drawn.length>=3);
  const opacities=drawn.map(line=>line.material.opacity);
  assert.deepEqual(opacities,[...opacities].sort((a,b)=>b-a));assert.equal(new Set(opacities).size,opacities.length);
  for(const line of drawn){assert.equal(line.material.transparent,true);assert.ok(line.material.opacity<1);assert.equal(line.material.color.getHexString(),HYPOTHESIS_COLOR.slice(1));assert.equal(line.material.isLineDashedMaterial,undefined);}
  view.dispose();
});

test('time-sliced reachable region follows setTimestamp, and no target position is drawn in the blind interval',()=>{
  const {ready}=plans(),{view}=makeView({blindHypothesis:ready});
  const sliceAt=t=>{view.setTimestamp(t);return visibleGroups(view);};
  assert.equal(sliceAt(4.4).length,0);assert.equal(view.blindHypothesisShown,null);
  assert.equal(sliceAt(8.6).length,0);assert.equal(sliceAt(2).length,0);
  const first=sliceAt(4.6);assert.equal(first.length,1);assert.equal(first[0].userData.timestamp,4.6);
  const shownFirst=view.blindHypothesisShown;
  const mid=sliceAt(6);assert.equal(mid.length,1);assert.equal(mid[0].userData.timestamp,6);assert.notEqual(mid[0],first[0]);
  assert.notDeepEqual(view.blindHypothesisShown,shownFirst);
  assert.equal(sliceAt(8.4)[0].userData.timestamp,8.4);
  assert.equal(sliceAt(8.6).length,0);
  // Scrubbing back and forth keeps exactly one (or no) region visible and never rebuilds the layer.
  const children=[...view.blindHypothesisLayer.children];
  for(const t of [5,7,6.2,4.4,4.6,8.5,3])assert.ok(sliceAt(t).length<=1);
  assert.deepEqual(view.blindHypothesisLayer.children,children);
  // Only path lines, labels and region quads exist: no sphere/marker/cursor stands for the target.
  for(const child of view.blindHypothesisLayer.children){
    if(child.isGroup)for(const mesh of child.children){assert.equal(mesh.geometry.type,'BufferGeometry');assert.equal(mesh.isMesh,true);}
    else assert.ok(child.isLine||child.isSprite,child.type);
  }
  view.dispose();
});

test('region is taken from the plan at the current time and a plan arriving late picks up the last timestamp',()=>{
  const {ready}=plans(),{view,settings}=makeView();
  view.setTimestamp(6);assert.equal(visibleGroups(view).length,0);
  view.setData({...settings,blindHypothesis:ready});
  assert.equal(visibleGroups(view).length,1);assert.equal(visibleGroups(view)[0].userData.timestamp,6);
  assert.equal(view.blindHypothesisShown.timestamp_s,blindHypothesisRegionAt(ready,6).timestamp_s);
  // Same plan again: layer kept; removed plan: layer cleared.
  const children=[...view.blindHypothesisLayer.children];view.setData({...settings,blindHypothesis:ready});assert.deepEqual(view.blindHypothesisLayer.children,children);
  view.setData({...settings,blindHypothesis:null});assert.equal(view.blindHypothesisLayer.children.length,0);assert.equal(view.blindHypothesisShown,null);
  view.setTimestamp(6.2);assert.equal(view.blindHypothesisLayer.children.length,0);
  view.dispose();
});

test('UNKNOWN response draws nothing at any time',()=>{
  const {unknown}=plans(),{view}=makeView({blindHypothesis:unknown});
  assert.equal(view.blindHypothesisLayer.children.length,0);
  for(const t of [4.4,4.6,6,8.4,8.6]){view.setTimestamp(t);assert.equal(view.blindHypothesisLayer.children.length,0);assert.equal(view.blindHypothesisShown,null);}
  view.dispose();
});

test('only links through an unconfirmed area are dashed and captioned; verified links are solid; captions stay within six characters',()=>{
  const {substituted_unconfirmed:plan}=plans(),{view,labels}=makeView({blindHypothesis:plan});
  const drawn=lines(view),dashed=drawn.filter(line=>line.material.isLineDashedMaterial);
  const flaggedPaths=plan.paths.filter(path=>path.unconfirmed);
  assert.equal(dashed.length,flaggedPaths.length);assert.ok(dashed.length>=1);
  // A flagged path keeps its verified stretch as a solid line; the fully verified path has no dashed line.
  for(const path of plan.paths){
    const own=drawn.filter(line=>line.userData.blindHypothesisPath===path.ref);
    assert.equal(own.some(line=>line.material.isLineDashedMaterial),path.unconfirmed);
    assert.equal(own.some(line=>!line.material.isLineDashedMaterial),path.links.some(link=>!link.unconfirmed));
    const dashedPoints=own.filter(line=>line.material.isLineDashedMaterial).reduce((n,line)=>n+line.geometry.attributes.position.count/2,0);
    assert.equal(dashedPoints,path.links.filter(link=>link.unconfirmed).length);
  }
  assert.ok(labels.includes(UNCONFIRMED_LABEL));assert.ok(labels.includes('端點已替代'));assert.ok(labels.some(text=>/^假設 \d$/.test(text)));
  for(const text of labels)assert.ok([...text].length<=6,text);
  // Unconfirmed region cells are a wireframe, distinct from the filled confirmed cells.
  const flagged=plan.regions.find(region=>region.cells.some(cell=>cell.unconfirmed)&&region.cells.some(cell=>!cell.unconfirmed));
  view.setTimestamp(flagged.timestamp_s);
  const [group]=visibleGroups(view);assert.ok(group.children.some(mesh=>mesh.material.wireframe===true&&mesh.userData.unconfirmedCells));
  assert.ok(group.children.some(mesh=>mesh.material.wireframe===false));
  view.dispose();
});

test('ENDPOINT_SUBSTITUTION_INVALID and an older-format response render safely',()=>{
  const {substitution_invalid}=plans(),{view}=makeView({blindHypothesis:substitution_invalid});
  assert.equal(view.blindHypothesisLayer.children.length,0);view.setTimestamp(6);assert.equal(view.blindHypothesisShown,null);view.dispose();
  const old=structuredClone(fixture.cases.ready);delete old.endpoint_substitutions;
  for(const h of old.hypotheses){delete h.route_m;delete h.checks.walkable.segments;}
  const {view:legacy}=makeView({blindHypothesis:blindHypothesisPlan(old)});
  assert.equal(lines(legacy).length,old.hypotheses.length);legacy.setTimestamp(6);assert.equal(visibleGroups(legacy).length,1);legacy.dispose();
});

test('plan changes rebuild the layer, dispose releases it, and other layers are untouched',()=>{
  const {ready,substituted_unconfirmed:other}=plans(),{view,settings}=makeView({blindHypothesis:ready});
  const floor=view.objectLayer.children[0],first=[...view.blindHypothesisLayer.children];
  view.setData({...settings,blindHypothesis:other});
  assert.notDeepEqual(view.blindHypothesisLayer.children,first);assert.equal(view.objectLayer.children[0],floor);
  assert.equal(view.crossCameraLayer.children.length,0);assert.equal(view.eventLayer.children.length,0);
  view.dispose();view.dispose();
});

test('restricted-policy links are dashed in their own colour and labelled; the path stays visible and cells are tinted',()=>{
  const {restricted_policy:plan}=plans(),{view,labels}=makeView({blindHypothesis:plan});
  const drawn=lines(view);
  for(const path of plan.paths){
    const own=drawn.filter(l=>l.userData.blindHypothesisPath===path.ref),dashed=own.filter(l=>l.userData.linkKind==='restricted');
    assert.equal(dashed.length,1);assert.equal(dashed[0].material.isLineDashedMaterial,true);assert.equal(dashed[0].material.color.getHexString(),RESTRICTED_COLOR.slice(1));
    assert.equal(dashed[0].geometry.attributes.position.count/2,path.links.filter(l=>l.restricted).length);
    assert.ok(own.some(l=>l.userData.linkKind==='verified'&&l.material.color.getHexString()===HYPOTHESIS_COLOR.slice(1)));
    assert.equal(own.reduce((n,l)=>n+l.geometry.attributes.position.count/2,0),path.links.length);
  }
  assert.ok(labels.includes(RESTRICTED_LABEL));for(const text of labels)assert.ok([...text].length<=6,text);
  const region=plan.regions.find(r=>r.cells.some(c=>c.restricted)&&r.cells.some(c=>!c.restricted));
  view.setTimestamp(region.timestamp_s);
  const [group]=visibleGroups(view),tinted=group.children.filter(m=>m.userData.cellKind==='restricted');
  assert.equal(tinted.length,1);assert.equal(tinted[0].material.color.getHexString(),RESTRICTED_COLOR.slice(1));
  assert.equal(tinted[0].geometry.attributes.position.count/6,region.cells.filter(c=>c.restricted).length);
  assert.ok(group.children.some(m=>m.userData.cellKind==='confirmed'));
  view.dispose();
});

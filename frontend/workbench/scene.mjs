import * as THREE from '/vendor/three.module.js';
import {calibratedFrustum,planarPolygon,worldDirectionSVG,cameraFrustumOverlay,FRUSTUM_LABEL,ANNOTATION_LABEL} from './geometry.mjs';
import {bodyMarkers,serverBodyMarkers} from './motion.mjs';
import {graphCaptionPlan} from './presentation-data.mjs';
import {physicalReviewEvidenceFrame} from './physical-review.mjs';
import {crossCameraCursor,cameraShortLabel} from './cross-camera.mjs';
import {contactQualityStyle,contactQualityReadout} from './presentation-data.mjs';
import {blindHypothesisRegionAt,HYPOTHESIS_COLOR,RESTRICTED_COLOR} from './blind-hypothesis.mjs';

const finitePoint = (point) => Array.isArray(point) && point.length >= 3 && point.slice(0,3).every(Number.isFinite);
const vector = (point) => new THREE.Vector3(...point.slice(0,3));
// Unflagged captions keep the plain camera key; a tagged caption adds its contact-quality tag.
const cursorCaptionKey=(camera,tag)=>tag?JSON.stringify([camera,tag]):camera;
// A local annotation preview may cap its top, never edit the source vertices or gain geometry authority.
function validReviewDisplayVertices(overlay) {
  const hasVertices=overlay.display_vertices!==undefined,hasAdjustment=overlay.display_adjustment!==undefined;
  if(!hasVertices&&!hasAdjustment)return true;
  const adjustment=overlay.display_adjustment,raw=overlay.vertices,derived=overlay.display_vertices;
  if(!hasVertices||!hasAdjustment||overlay.kind!=='SOURCE_ANNOTATION'||!adjustment||typeof adjustment!=='object'||Array.isArray(adjustment)||
    Object.keys(adjustment).some(key=>!['kind','original_top_z','target_top_z','authority'].includes(key))||
    adjustment.kind!=='ANNOTATION_DISPLAY_TOP_CLIP'||adjustment.authority!=='LOCAL_DISPLAY_ONLY_NOT_APERTURE'||
    !Number.isFinite(adjustment.original_top_z)||!Number.isFinite(adjustment.target_top_z)||
    !Array.isArray(raw)||!raw.length||!raw.every(finitePoint)||!Array.isArray(derived)||derived.length!==raw.length)return false;
  const lower=Math.min(...raw.map(point=>point[2])),upper=Math.max(...raw.map(point=>point[2]));
  return adjustment.original_top_z===upper&&adjustment.target_top_z>lower&&adjustment.target_top_z<upper&&
    derived.every((point,index)=>Array.isArray(point)&&point.length===3&&point.every(Number.isFinite)&&
      point[0]===raw[index][0]&&point[1]===raw[index][1]&&point[2]===Math.min(raw[index][2],adjustment.target_top_z));
}
const COLORS = {REGION:0x9487d3,PORTAL:0xd49bd2,WALKABLE:0x65c6c0,CAMERA:0x82b9dc};
function boundsOf(snapshot, objects) {
  const bounds=snapshot.bounds;
  const display=snapshot.presentation?.supplemental_display;
  if(display?.authority==='PARTIAL_DISPLAY_CONTEXT'&&display.display_only===true){
    const base=Array.isArray(bounds)&&bounds.length===4?bounds:null;
    const extra=display.bounds_metres;
    const cameras=(snapshot.cameras??[]).map(c=>c.position).filter(finitePoint);
    if(base&&Array.isArray(extra)&&extra.length===2&&extra.every(finitePoint))return [
      Math.min(base[0],extra[0][0],...cameras.map(p=>p[0])),Math.min(base[1],extra[0][1],...cameras.map(p=>p[1])),
      Math.max(base[2],extra[1][0],...cameras.map(p=>p[0])),Math.max(base[3],extra[1][1],...cameras.map(p=>p[1]))];
  }
  if(Array.isArray(bounds)&&bounds.length===4&&bounds.every(Number.isFinite))return [bounds[0],bounds[1],bounds[2],bounds[3]];
  if(Array.isArray(bounds)&&bounds.length===2&&bounds.every(finitePoint))return [bounds[0][0],bounds[0][1],bounds[1][0],bounds[1][1]];
  if(bounds?.min&&bounds?.max)return [bounds.min[0],bounds.min[1],bounds.max[0],bounds.max[1]];
  const points=objects.flatMap((item)=>item.geometry?.points??[]).filter(finitePoint);
  if(!points.length)return [-1,-1,1,1];
  return [Math.min(...points.map((p)=>p[0])),Math.min(...points.map((p)=>p[1])),Math.max(...points.map((p)=>p[0])),Math.max(...points.map((p)=>p[1]))];
}

export class SceneView {
  constructor(container,{snapshot,objects,event,events=[],observations=[],presentation=null,graph=null,crossCamera=null,physicalGeometry=null,physicalReview=null,geometryOverlay=null,blindHypothesis=null,selectedId,pose,onSelect,onReviewSelect}) {
    this.container=container;this.snapshot=snapshot;this.onSelect=onSelect;this.onReviewSelect=onReviewSelect;this.disposed=false;this.pickables=[];this.reviewPickables=[];this.event=event;
    this.scene=new THREE.Scene();this.scene.background=new THREE.Color(0x121927);
    this.events=events.length?events:[event].filter(Boolean);this.observations=observations;this.presentation=presentation;this.bodies=new THREE.Group();
    this.scene.add(this.bodies);this.bodyInstances=new Map();
    this.camera=new THREE.PerspectiveCamera(43,1,.01,10000);this.camera.up.set(0,0,1);
    this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    container.replaceChildren(this.renderer.domElement);
    this.bounds=boundsOf(snapshot,objects);const [x0,y0,x1,y1]=this.bounds;
    this.span=Math.max(x1-x0,y1-y0,2);this.center=new THREE.Vector3((x0+x1)/2,(y0+y1)/2,0);
    const supplemental=snapshot.presentation?.supplemental_display;
    if(supplemental?.display_only&&supplemental?.authority==='PARTIAL_DISPLAY_CONTEXT'){
      const tops=[supplemental.bounds_metres[1][2],...(snapshot.cameras??[]).map(c=>c.position?.[2]).filter(Number.isFinite)];
      this.center.z=(supplemental.bounds_metres[0][2]+Math.max(...tops))/2;
    }
    this.target=this.center.clone();this.yaw=-Math.PI/2.8;this.pitch=.77;this.distance=this.span*1.5;
    this.scene.add(new THREE.HemisphereLight(0xd6e6ff,0x222b45,2.2));
    const light=new THREE.DirectionalLight(0xcad9ff,2);light.position.set(0,-10,20);this.scene.add(light);
    const gridSize=Math.ceil(this.span*1.35);const grid=new THREE.GridHelper(gridSize,Math.min(gridSize*2,80),0x37445a,0x222f43);
    grid.rotation.x=Math.PI/2;grid.position.copy(this.center);grid.position.z=-.04;grid.material.transparent=true;grid.material.opacity=.6;this.scene.add(grid);
    this.addAxes();
    this.objectLayer=new THREE.Group();this.sourceLayer=new THREE.Group();this.supplementalLayer=new THREE.Group();this.eventLayer=new THREE.Group();this.graphLayer=new THREE.Group();this.crossCameraLayer=new THREE.Group();this.physicalGeometryLayer=new THREE.Group();this.physicalReviewLayer=new THREE.Group();this.geometryOverlayLayer=new THREE.Group();this.blindHypothesisLayer=new THREE.Group();
    this.scene.add(this.objectLayer,this.sourceLayer,this.supplementalLayer,this.eventLayer,this.graphLayer,this.crossCameraLayer,this.physicalGeometryLayer,this.physicalReviewLayer,this.geometryOverlayLayer,this.blindHypothesisLayer);
    this.setData({snapshot,objects,event,events,observations,presentation,graph,crossCamera,physicalGeometry,physicalReview,geometryOverlay,blindHypothesis,selectedId});
    if(pose){this.target.fromArray(pose.target);this.yaw=pose.yaw;this.pitch=pose.pitch;this.distance=pose.distance;}
    this.updateCamera();this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(container);this.resize();
    this.pointerDown=this.onPointerDown.bind(this);this.pointerMove=this.onPointerMove.bind(this);this.pointerUp=this.onPointerUp.bind(this);this.wheel=this.onWheel.bind(this);this.contextMenu=(e)=>e.preventDefault();
    const canvas=this.renderer.domElement;canvas.addEventListener('pointerdown',this.pointerDown);canvas.addEventListener('pointermove',this.pointerMove);canvas.addEventListener('pointerup',this.pointerUp);canvas.addEventListener('pointercancel',this.pointerUp);canvas.addEventListener('wheel',this.wheel,{passive:false});canvas.addEventListener('contextmenu',this.contextMenu);
    this.render();
  }
  clearLayer(layer) {
    const geometries=new Set(),materials=new Set(),textures=new Set();
    layer.traverse(child=>{if(child.geometry)geometries.add(child.geometry);
      for(const material of Array.isArray(child.material)?child.material:[child.material].filter(Boolean)){
        materials.add(material);if(material.map)textures.add(material.map);
      }});
    geometries.forEach(item=>item.dispose());materials.forEach(item=>item.dispose());textures.forEach(item=>item.dispose());
    layer.clear();
  }
  setData({snapshot=this.snapshot,objects=[],event=null,events=[],observations=[],presentation=null,graph=null,crossCamera=null,physicalGeometry=null,physicalReview=this.physicalReviewPlan??null,geometryOverlay=this.geometryOverlayPlan??null,blindHypothesis=null,selectedId}={}) {
    if(this.disposed)return;
    this.snapshot=snapshot;this.event=event;this.events=events.length?events:[event].filter(Boolean);
    this.observations=observations;this.presentation=presentation;
    const objectSignature=JSON.stringify([objects,selectedId]);
    if(objectSignature!==this.objectSignature){
      this.clearLayer(this.objectLayer);this.pickables=[];
      objects.forEach(object=>this.addObject(object,object.object_id===selectedId));
      this.addCalibratedCameras(objects.filter(object=>object.kind==='CAMERA').map(object=>({camera_id:object.object_id,position:object.geometry?.points?.[0]??null,properties:object.properties})));
      this.objectSignature=objectSignature;
    }
    const {supplemental_display:supplemental,...originalPresentation}=presentation??{};
    const sourceSignature=JSON.stringify(presentation?originalPresentation:null);
    const supplementalSignature=supplemental?.asset_sha256??null;
    if(supplementalSignature!==this.supplementalSignature){
      this.clearLayer(this.supplementalLayer);this.addSupplementalDisplay(supplemental);
      this.supplementalSignature=supplementalSignature;
    }
    if(sourceSignature!==this.sourceSignature){
      this.clearLayer(this.sourceLayer);this.addSourceMeshes(presentation?.meshes??[]);
      this.addSourceRoutes(presentation,snapshot);this.sourceSignature=sourceSignature;
    }
    const eventSignature=JSON.stringify(this.events);
    if(eventSignature!==this.eventSignature){
      this.clearLayer(this.eventLayer);this.projected=[];this.timeMarker=null;
      this.events.forEach(item=>this.addEvent(item));this.eventSignature=eventSignature;
    }
    const graphSignature=JSON.stringify(graph);
    if(graphSignature!==this.graphSignature){this.clearLayer(this.graphLayer);this.addGraph(graph);this.graphSignature=graphSignature;}
    this.setCrossCamera(crossCamera);
    this.setPhysicalGeometry(physicalGeometry);
    this.setPhysicalReview(physicalReview);
    this.setGeometryOverlay(geometryOverlay);
    this.setBlindHypothesis(blindHypothesis);
    if(this.resizeObserver)this.render();
  }
  addSourceRoutes(presentation,snapshot) {
    for(const [index,route] of (presentation?.routes??[]).entries()){
      const points=(route.points??[]).filter(finitePoint).map(vector);
      if(points.length<2)continue;
      const path=new THREE.CurvePath();for(let i=1;i<points.length;i++)path.add(new THREE.LineCurve3(points[i-1],points[i]));
      const geometry=new THREE.TubeGeometry(path,Math.max(12,points.length*12),.018,5,false);
      const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color:[0xffc36b,0xb49cff,0x66d4c7][index%3],depthTest:false,transparent:true,opacity:.9}));
      mesh.renderOrder=6;this.sourceLayer.add(mesh);
    }
    if(presentation)for(const camera of snapshot.cameras??[]){
      if(finitePoint(camera.position)){
        const marker=new THREE.Mesh(new THREE.BoxGeometry(this.span*.025,this.span*.017,this.span*.017),new THREE.MeshStandardMaterial({color:COLORS.CAMERA}));
        marker.position.copy(vector(camera.position));this.sourceLayer.add(marker);
      }
    }

  }
  addGraph(graph) {
    const data=graphCaptionPlan(graph),nodes=new Map(data.nodes.map(node=>[node.id,node]));
    for(const node of data.nodes){
      const point=vector(node.position),mesh=new THREE.Mesh(new THREE.SphereGeometry(this.span*.012,12,8),new THREE.MeshBasicMaterial({color:0x7ce1cc,depthTest:false}));
      mesh.position.copy(point);mesh.position.z+=.16;mesh.renderOrder=8;this.graphLayer.add(mesh);
    }
    for(const edge of data.edges){
      const a=vector(nodes.get(edge.from).position),b=vector(nodes.get(edge.to).position);
      const focused=edge.from===graph?.focus_node_id||edge.to===graph?.focus_node_id;
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([a,b]),new THREE.LineBasicMaterial({color:0x8cb4df,transparent:true,opacity:focused?.38:.16,depthTest:false}));
      line.position.z=.13;line.renderOrder=7;this.graphLayer.add(line);
    }
    for(const node of data.nodeCaptions)this.addGraphLabel(node.label??node.id,vector(node.position),.2,false);
    for(const edge of data.edgeCaptions){
      const midpoint=vector(nodes.get(edge.from).position).add(vector(nodes.get(edge.to).position)).multiplyScalar(.5);
      this.addGraphLabel(edge.label??edge.relation,midpoint,.17,true);
    }
  }
  addGraphLabel(text,position,lift,relation=false,layer=this.graphLayer,limit=18) {
    const sprite=this.labelSprite(text,relation,limit);if(!sprite)return;
    sprite.position.copy(position);sprite.position.z+=lift;layer.add(sprite);
  }
  labelSprite(text,relation=false,limit=18) {
    const label=String(text).length>limit?String(text).slice(0,limit-1)+'…':String(text);
    const canvas=document.createElement('canvas');canvas.width=limit>18?640:384;canvas.height=56;
    const context=canvas.getContext('2d');if(!context)return null;
    context.font='22px sans-serif';canvas.width=Math.max(72,Math.min(limit>18?640:384,Math.ceil(context.measureText(label).width)+24));
    context.fillStyle='rgba(14,23,39,.72)';context.fillRect(0,0,canvas.width,56);
    context.font='22px sans-serif';context.textAlign='center';context.fillStyle=relation?'#a8bfd5':'#bde7df';context.fillText(label,canvas.width/2,36);
    const material=new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),depthTest:false,transparent:true});
    const sprite=new THREE.Sprite(material);sprite.userData.captionSize={width:canvas.width,height:56,relation};sprite.renderOrder=9;
    return sprite;
  }
  setCrossCamera(plan) {
    if(this.disposed)return;
    const signature=JSON.stringify(plan);
    if(signature===this.crossCameraSignature)return;
    this.clearLayer(this.crossCameraLayer);this.crossCameraCursors=[];this.crossCameraPlan=plan;
    let captionBudget=6;
    for(const path of plan?.paths??[]){
      const color=new THREE.Color(path.color),opacity=path.selected?.92:.17,lift=.07+(path.rank??0)*.012;
      for(const segment of path.segments??[]){
        if(!finitePoint(segment.from?.world_position)||!finitePoint(segment.to?.world_position))continue;
        const material=segment.inferred?new THREE.LineDashedMaterial({color,dashSize:Math.max(.025,this.span*.007),gapSize:Math.max(.016,this.span*.004),transparent:true,opacity,depthTest:false}):
          new THREE.LineBasicMaterial({color,transparent:true,opacity,depthTest:false});
        const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([vector(segment.from.world_position),vector(segment.to.world_position)]),material);
        line.position.z=lift;line.renderOrder=10;if(segment.inferred)line.computeLineDistances();this.crossCameraLayer.add(line);
      }
      for(const association of path.missingAssociations??[]){
        const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([vector(association.from),vector(association.to)]),
          new THREE.LineDashedMaterial({color:0x8292a9,dashSize:Math.max(.02,this.span*.006),gapSize:Math.max(.03,this.span*.009),transparent:true,opacity:path.selected?.55:.1,depthTest:false}));
        line.position.z=lift+.01;line.renderOrder=9;line.computeLineDistances();this.crossCameraLayer.add(line);
        if(path.selected&&captionBudget>0){const midpoint=vector(association.from).add(vector(association.to)).multiplyScalar(.5);this.addGraphLabel(association.caption,midpoint,lift+.07,true,this.crossCameraLayer);captionBudget--;}
      }
      if(path.selected)for(const association of path.associationCaptions??[]){
        if(captionBudget<=0)break;
        const midpoint=vector(association.from).add(vector(association.to)).multiplyScalar(.5);
        this.addGraphLabel(association.caption,midpoint,lift+.09,true,this.crossCameraLayer);captionBudget--;
      }
      const points=(path.samples??[]).filter(sample=>finitePoint(sample.world_position)&&['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION','INFERRED_CROSS_CAMERA'].includes(sample.state));
      if(path.selected){
        for(const point of points){
          // FLAGGED contact quality: hollow (wireframe) marker at the unchanged position.
          const hollow=contactQualityStyle(point.contact_quality).hollow;
          const marker=new THREE.Mesh(new THREE.SphereGeometry(this.span*(hollow?.005:.0035),8,6),new THREE.MeshBasicMaterial({color:point.state==='PROJECTED_OBSERVATION'?color:0xffc266,transparent:true,opacity:hollow?.95:.7,wireframe:hollow,depthTest:false}));
          marker.userData.contactQuality=contactQualityStyle(point.contact_quality).status;
          marker.position.copy(vector(point.world_position));marker.position.z+=lift;marker.renderOrder=11;this.crossCameraLayer.add(marker);
        }
        if(points.length&&captionBudget>0){this.addGraphLabel(path.caption,vector(points[0].world_position),lift+.11,false,this.crossCameraLayer);captionBudget--;}
        const cursor=new THREE.Mesh(new THREE.SphereGeometry(this.span*.012,12,8),new THREE.MeshBasicMaterial({color,depthTest:false}));
        const ring=new THREE.Mesh(new THREE.RingGeometry(this.span*.019,this.span*.025,24),new THREE.MeshBasicMaterial({color:0xe9f0ff,side:THREE.DoubleSide,depthTest:false,transparent:true,opacity:.9}));
        ring.visible=false;ring.renderOrder=12;cursor.add(ring);
        // One caption per source camera on this path: the cursor names its candidate path, evidence camera, association and unverified ground contact.
        const labels=new Map();
        // Captions are keyed by camera and contact-quality tag, so a flagged observation names 接地點不可靠 on its own caption.
        for(const point of points.filter(point=>point.state==='PROJECTED_OBSERVATION')){
          const camera=point.camera_id??null,tag=contactQualityStyle(point.contact_quality).tag,key=cursorCaptionKey(camera,tag);
          if(labels.has(key))continue;
          const sprite=this.labelSprite(`${path.caption.replace(/ /g,'')} · ${cameraShortLabel(camera)}${path.associated?'':' · 未關聯'} · ${tag??'接地UNKNOWN'}`,false,40);
          if(!sprite)continue;sprite.center.set(.5,-.55);sprite.visible=false;sprite.renderOrder=13;sprite.userData.cursorCaption=true;cursor.add(sprite);labels.set(key,sprite);
        }
        cursor.visible=false;cursor.renderOrder=12;this.crossCameraLayer.add(cursor);this.crossCameraCursors.push({path,cursor,ring,lift,labels});
      }
    }
    this.crossCameraSignature=signature;if(this.resizeObserver)this.render();
  }
  updateCrossCamera(timestamp) {
    let shown=0;this.contactQualitySamples=[];
    for(const {path,cursor,ring,lift,labels} of this.crossCameraCursors??[]){
      const sample=crossCameraCursor(path,timestamp,this.crossCameraPlan?.time_range);
      const key=sample?cursorCaptionKey(sample.camera_id??null,contactQualityStyle(sample.contact_quality).tag):null;
      for(const [captionKey,label] of labels??[]){
        label.visible=Boolean(sample)&&sample.state==='PROJECTED_OBSERVATION'&&captionKey===key;
        // Simultaneous observations stack their captions so one never hides another.
        if(label.visible)label.center.set(.5,-.55-1.15*shown++);
      }
      cursor.visible=Boolean(sample);
      // The ring marks the first sample of a disconnected segment: a new observation, not the cursor having moved from the previous point.
      ring.visible=Boolean(sample)&&sample.connect_from_previous!==true;
      if(sample){cursor.position.copy(vector(sample.world_position));cursor.position.z+=lift+.05;cursor.material.color.set(sample.state==='PROJECTED_OBSERVATION'?path.color:0xffc266);
        cursor.material.wireframe=contactQualityStyle(sample.contact_quality).hollow;}
      if(sample)this.contactQualitySamples.push(sample);
    }
  }
  // Blind-interval hypotheses (INFERRED_HYPOTHESIS): a translucent path bundle plus the reachable region of the current time.
  // The region follows the timeline; no target position, marker or cursor is ever drawn inside the interval.
  setBlindHypothesis(plan) {
    if(this.disposed)return;
    const signature=plan?.key??null;
    if(signature===this.blindHypothesisSignature)return;
    this.clearLayer(this.blindHypothesisLayer);this.blindHypothesisRegions=[];this.blindHypothesisPlan=plan??null;this.blindHypothesisShown=null;
    if(plan?.status==='READY'){
      const color=new THREE.Color(HYPOTHESIS_COLOR),restrictedColor=new THREE.Color(RESTRICTED_COLOR),lift=.09,dash=Math.max(.025,this.span*.007),gap=Math.max(.016,this.span*.004);
      for(const path of plan.paths){
        // Opacity falls with rank. Links through a walkable:UNKNOWN area (D11 segments) are dashed; verified links stay solid.
        // Restricted-policy links (D15) win the style: dashed in their own colour. Still drawn, never hidden or treated as an obstacle.
        const restricted=path.links.filter(link=>link.restricted),unconfirmed=path.links.filter(link=>link.unconfirmed&&!link.restricted),verified=path.links.filter(link=>!link.unconfirmed&&!link.restricted);
        const build=(links,material,kind)=>{
          if(!links.length)return;
          const line=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(links.flatMap(link=>[vector(link.a),vector(link.b)])),material);
          line.position.z=lift+path.rank*.004;line.renderOrder=14;line.userData.blindHypothesisPath=path.ref;line.userData.linkKind=kind;line.userData.unconfirmedLinks=kind==='unconfirmed';
          if(material.isLineDashedMaterial)line.computeLineDistances();this.blindHypothesisLayer.add(line);
        };
        build(verified,new THREE.LineBasicMaterial({color,transparent:true,opacity:path.opacity,depthTest:false}),'verified');
        build(unconfirmed,new THREE.LineDashedMaterial({color,dashSize:dash,gapSize:gap,transparent:true,opacity:path.opacity,depthTest:false}),'unconfirmed');
        build(restricted,new THREE.LineDashedMaterial({color:restrictedColor,dashSize:dash*1.6,gapSize:gap*.7,transparent:true,opacity:Math.max(.5,path.opacity),depthTest:false}),'restricted');
        const middle=path.points[Math.floor(path.points.length/2)];
        if(finitePoint(middle))this.addGraphLabel(path.label,vector(middle),lift+.1+path.rank*.004,false,this.blindHypothesisLayer,6);
        if(restricted.length){const link=restricted[Math.floor(restricted.length/2)];
          this.addGraphLabel(path.restrictedLabel,vector(link.a).add(vector(link.b)).multiplyScalar(.5),lift+.4+path.rank*.004,true,this.blindHypothesisLayer,6);}
        if(unconfirmed.length){const link=unconfirmed[Math.floor(unconfirmed.length/2)];
          this.addGraphLabel(path.unconfirmedLabel,vector(link.a).add(vector(link.b)).multiplyScalar(.5),lift+.3+path.rank*.004,true,this.blindHypothesisLayer,6);}
      }
      // D7: the substituted endpoint is flagged next to its region (details are in the status block).
      for(const item of plan.substitutions??[])if(finitePoint(item.anchor))this.addGraphLabel(item.label,vector(item.anchor),lift+.45,true,this.blindHypothesisLayer,6);
      for(const region of plan.regions){
        const half=region.cell_size_m/2,confirmed=[],unconfirmed=[],restricted=[];
        for(const cell of region.cells)(cell.restricted?restricted:cell.unconfirmed?unconfirmed:confirmed).push(cell);
        const group=new THREE.Group();group.visible=false;group.userData.timestamp=region.timestamp_s;
        const quads=cells=>{const positions=[];for(const {x,y} of cells)positions.push(x-half,y-half,0,x+half,y-half,0,x+half,y+half,0,x-half,y-half,0,x+half,y+half,0,x-half,y+half,0);return positions;};
        for(const [cells,wireframe,opacity,tint,kind] of [[confirmed,false,.34,color,'confirmed'],[unconfirmed,true,.8,color,'unconfirmed'],[restricted,false,.5,restrictedColor,'restricted']]){
          if(!cells.length)continue;
          const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(quads(cells),3));
          const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color:tint,transparent:true,opacity,wireframe,side:THREE.DoubleSide,depthTest:false}));
          mesh.position.z=plan.floorZ+lift*.5;mesh.renderOrder=13;mesh.userData.unconfirmedCells=kind==='unconfirmed';mesh.userData.cellKind=kind;group.add(mesh);
        }
        this.blindHypothesisLayer.add(group);this.blindHypothesisRegions.push({region,group});
      }
    }
    this.blindHypothesisSignature=signature;this.updateBlindHypothesis(this.currentTimestamp);
    if(this.resizeObserver)this.render();
  }
  updateBlindHypothesis(timestamp) {
    if(!this.blindHypothesisPlan){this.blindHypothesisShown=null;return;}
    const shown=blindHypothesisRegionAt(this.blindHypothesisPlan,timestamp);
    for(const {region,group} of this.blindHypothesisRegions??[])group.visible=region===shown;
    this.blindHypothesisShown=shown?{timestamp_s:shown.timestamp_s,cells:shown.cells.length}:null;
  }
  // Camera frusta + source annotation outlines. Pinhole geometry only: no occlusion, visibility or traversability is implied.
  setGeometryOverlay(plan) {
    if(this.disposed)return;
    this.geometryOverlayLayer.visible=plan?.enabled!==false&&Boolean(plan);
    const signature=JSON.stringify([plan?.cameras,plan?.annotations]);if(signature===this.geometryOverlaySignature)return;
    this.geometryOverlaySignature=signature;this.geometryOverlayPlan=plan;this.clearLayer(this.geometryOverlayLayer);
    const depth=this.span*.2,tint={FRONT:0x6fd3ff,REAR:0xffb066};
    for(const camera of plan?.cameras??[]){
      const frustum=cameraFrustumOverlay(camera,depth);if(!frustum)continue;
      const color=tint[frustum.role]??0xb7c4d9,apex=vector(frustum.apex),corners=frustum.corners.map(vector),segments=[];
      for(let i=0;i<4;i++)segments.push(apex,corners[i],corners[i],corners[(i+1)%4]);
      const material=new THREE.LineBasicMaterial({color,transparent:true,opacity:.85,depthTest:false});
      const lines=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(segments),material);lines.renderOrder=15;lines.userData.geometryOverlay='FRUSTUM';this.geometryOverlayLayer.add(lines);
      const forward=new THREE.Vector3(...frustum.forward).normalize();
      const arrow=new THREE.ArrowHelper(forward,apex,depth*1.15,color,depth*.16,depth*.08);arrow.renderOrder=16;
      arrow.traverse(child=>{child.renderOrder=16;if(child.material){child.material.depthTest=false;}});arrow.userData.geometryOverlay='VIEW_DIRECTION';this.geometryOverlayLayer.add(arrow);
      this.addGraphLabel(`${frustum.role??frustum.camera_id} · 視線方向 →`,apex.clone(),.25,false,this.geometryOverlayLayer,48);
      this.addGraphLabel(FRUSTUM_LABEL,apex.clone(),.0,true,this.geometryOverlayLayer,48);
    }
    for(const annotation of plan?.annotations??[]){
      const points=annotation.edges.flat().map(vector);if(!points.length)continue;
      const line=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineDashedMaterial({color:0xf4d37a,dashSize:Math.max(.03,this.span*.006),gapSize:Math.max(.02,this.span*.004),transparent:true,opacity:.95,depthTest:false}));
      line.computeLineDistances();line.renderOrder=15;line.userData.geometryOverlay='SOURCE_ANNOTATION';line.userData.sourceId=annotation.source_id;this.geometryOverlayLayer.add(line);
      const centre=points.reduce((sum,p)=>sum.add(p),new THREE.Vector3()).multiplyScalar(1/points.length);
      this.addGraphLabel(`${annotation.source_id} · ${ANNOTATION_LABEL}`,centre,.1,true,this.geometryOverlayLayer,48);
    }
    if(this.resizeObserver)this.render();
  }
  setGeometryOverlayVisible(enabled) {
    if(this.disposed)return;this.geometryOverlayLayer.visible=Boolean(enabled)&&Boolean(this.geometryOverlayPlan);this.render();
  }
  setPhysicalGeometry(plan) {
    if(this.disposed)return;
    const signature=JSON.stringify(plan);if(signature===this.physicalGeometrySignature)return;
    this.clearLayer(this.physicalGeometryLayer);let captions=2;
    for(const polygon of plan?.polygons??[]){
      if(polygon.physical_authority!=='SOURCE_SUPPORTED_WALKABLE_ONLY')continue;
      for(const [index,ring] of [polygon.exterior,...polygon.holes??[]].entries()){
        if(!Array.isArray(ring)||ring.length<3||ring.length>512||!ring.every(finitePoint))continue;
        const line=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ring.map(vector)),
          new THREE.LineBasicMaterial({color:index===0?0x83c4a7:0xdcc086,transparent:true,opacity:.55,depthTest:false}));
        line.position.z=.045;line.renderOrder=8;this.physicalGeometryLayer.add(line);
      }
      if(captions>0&&polygon.exterior?.length&&finitePoint(polygon.exterior[0])){
        this.addGraphLabel(polygon.caption,vector(polygon.exterior[0]),.09,true,this.physicalGeometryLayer);captions--;
      }
    }
    this.physicalGeometrySignature=signature;if(this.resizeObserver)this.render();
  }
  setPhysicalReview(plan) {
    if(this.disposed)return;
    const signature=JSON.stringify(plan);if(signature===this.physicalReviewSignature)return;
    this.clearLayer(this.physicalReviewLayer);this.reviewPickables=[];this.reviewEvidenceMarkers=[];this.reviewEvidenceByKey=new Map();this.reviewEvidenceStatus=null;this.reviewNominalBody=null;this.physicalReviewPlan=null;
    this.physicalReviewSignature=signature;
    if(!plan){if(this.resizeObserver)this.render();return;}
    const overlays=plan.overlays;
    const shape=Array.isArray(overlays)&&overlays.length<=64&&overlays.every(p=>p&&Array.isArray(p.vertices)&&Array.isArray(p.triangles)&&Array.isArray(p.rings)&&p.rings.every(Array.isArray));
    const valid=shape&&plan.display_only===true&&plan.physical_certification===false&&plan.source_sha256===this.snapshot.source_binding?.source_sha256&&
      (!plan.samples||(Array.isArray(plan.samples)&&plan.samples.length<=400&&plan.samples.every(sample=>Number.isFinite(sample.timestamp)&&
        ['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION','INFERRED_CROSS_CAMERA','MISSING'].includes(sample.state)&&(sample.world_position===null||finitePoint(sample.world_position))&&
        (sample.observation_ref===undefined||sample.observation_ref===null||typeof sample.observation_ref==='string'&&sample.observation_ref.length<=256))))&&
      (!plan.missing_intervals||(Array.isArray(plan.missing_intervals)&&plan.missing_intervals.length<=256))&&
      overlays.reduce((n,p)=>n+p.vertices.length+p.rings.reduce((m,r)=>m+r.length,0),0)<=8192&&
      overlays.reduce((n,p)=>n+(p.triangles?.length??0),0)<=4096&&overlays.every(p=>
        /^review-geometry:[a-f0-9]{24}$/.test(p.geometry_ref??'')&&/^review-item:[a-f0-9]{24}$/.test(p.item_ref??'')&&
        ['SOURCE_ANNOTATION','SOURCE_TRIANGLES','APPROVED_SUPPORT_RING','SOURCE_WITNESS'].includes(p.kind)&&p.units==='METRES'&&
        p.display_only===true&&p.is_aperture===false&&p.is_collider===false&&Array.isArray(p.vertices)&&p.vertices.every(finitePoint)&&
        Array.isArray(p.triangles)&&p.triangles.every(face=>Array.isArray(face)&&face.length===3&&face.every(i=>Number.isInteger(i)&&i>=0&&i<p.vertices.length))&&
        Array.isArray(p.rings)&&p.rings.every(ring=>Array.isArray(ring)&&ring.length>=3&&ring.length<=512&&ring.every(finitePoint))&&validReviewDisplayVertices(p));
    if(!valid){if(this.resizeObserver)this.render();return;}
    this.physicalReviewPlan=plan;let captions=2;
    for(const overlay of overlays){
      const displayVertices=overlay.display_vertices??overlay.vertices;
      const annotation=overlay.kind==='SOURCE_ANNOTATION',color=annotation?0xe6b96b:overlay.kind==='APPROVED_SUPPORT_RING'?0x83c4a7:0x9bb9da;
      const edges=new Map();
      for(const face of overlay.triangles)for(const [a,b]of[[face[0],face[1]],[face[1],face[2]],[face[2],face[0]]]){
        if(a!==b)edges.set(a<b?`${a}:${b}`:`${b}:${a}`,[displayVertices[a],displayVertices[b]]);
      }
      if(edges.size){
        const material=annotation?new THREE.LineDashedMaterial({color,dashSize:Math.max(.015,this.span*.004),gapSize:Math.max(.01,this.span*.003),transparent:true,opacity:.7,depthTest:false}):
          new THREE.LineBasicMaterial({color,transparent:true,opacity:.6,depthTest:false});
        const line=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([...edges.values()].flat().map(vector)),material);
        if(annotation)line.computeLineDistances();line.renderOrder=13;line.userData.reviewRef=overlay.item_ref;line.userData.pickPriority=-1;
        this.physicalReviewLayer.add(line);this.reviewPickables.push(line);
      }
      for(const ring of overlay.rings){
        const line=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ring.map(vector)),new THREE.LineBasicMaterial({color,transparent:true,opacity:.8,depthTest:false}));
        line.renderOrder=13;line.userData.reviewRef=overlay.item_ref;line.userData.pickPriority=-1;this.physicalReviewLayer.add(line);this.reviewPickables.push(line);
      }
      if(!edges.size&&!overlay.rings.length&&overlay.vertices.length===1){
        const marker=new THREE.Mesh(new THREE.SphereGeometry(Math.max(.025,this.span*.006),8,6),new THREE.MeshBasicMaterial({color,wireframe:true,depthTest:false}));
        marker.position.copy(vector(displayVertices[0]));marker.renderOrder=13;marker.userData.reviewRef=overlay.item_ref;marker.userData.pickPriority=-1;this.physicalReviewLayer.add(marker);this.reviewPickables.push(marker);
      }
      if(captions>0&&overlay.vertices.length){this.addGraphLabel(overlay.caption,vector(displayVertices[0]),.1,true,this.physicalReviewLayer);captions--;}
    }
    const policy=plan.nominal_body,nominal=plan.selected_kind==='BODY_CLEARANCE'&&policy?.authority==='APPROVED_POLICY_NOT_MEASURED_BODY'&&policy.measured_body===false&&
      Number.isFinite(policy.radius_m)&&policy.radius_m>0&&policy.radius_m<=2&&Number.isFinite(policy.height_m)&&policy.height_m>0&&policy.height_m<=4;
    this.reviewNominalBody=nominal?policy:null;
    this.setPhysicalReviewTime(this.reviewTimestamp??0);
    if(this.resizeObserver)this.render();
  }
  // One marker per source observation key, created on first use: a marker is never handed to a different observation, so a segment
  // start or a camera change cannot read as the same body moving. No marker is held or interpolated across missing evidence.
  reviewEvidenceMarker(sample) {
    let marker=this.reviewEvidenceByKey.get(sample.evidence_key);
    if(marker)return marker;
    marker=new THREE.Group();marker.visible=false;
    const radius=Math.max(.025,this.span*.005);
    const dot=new THREE.Mesh(new THREE.SphereGeometry(radius,8,6),new THREE.MeshBasicMaterial({color:0x66dfd0,depthTest:false,transparent:true,opacity:.9}));
    dot.position.z=.03;marker.add(dot);
    const ring=new THREE.Mesh(new THREE.RingGeometry(radius*1.7,radius*2.2,24),new THREE.MeshBasicMaterial({color:0xe9f0ff,side:THREE.DoubleSide,depthTest:false,transparent:true,opacity:.9}));
    ring.position.z=.03;ring.visible=false;ring.userData.segmentRing=true;marker.add(ring);
    // FLAGGED contact quality: dashed ring and a short tag; the marker keeps the sample's own position.
    const flagRing=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(Array.from({length:32},(_,i)=>new THREE.Vector3(Math.cos(i/32*Math.PI*2)*radius*2.8,Math.sin(i/32*Math.PI*2)*radius*2.8,.03))),
      new THREE.LineDashedMaterial({color:0xffc266,dashSize:radius*.6,gapSize:radius*.4,depthTest:false,transparent:true,opacity:.95}));
    flagRing.computeLineDistances();flagRing.visible=false;flagRing.userData.contactFlagRing=true;marker.add(flagRing);
    const style=contactQualityStyle(sample.contact_quality);
    if(style.tag){const tag=this.labelSprite(style.tag,false,8);if(tag){tag.center.set(.5,-.6);tag.visible=false;tag.userData.contactQualityTag=true;marker.add(tag);}}
    const policy=this.reviewNominalBody;
    if(policy){
      const cylinder=new THREE.CylinderGeometry(policy.radius_m,policy.radius_m,policy.height_m,16,1,false);cylinder.rotateX(Math.PI/2);
      const wire=new THREE.LineSegments(new THREE.EdgesGeometry(cylinder),new THREE.LineBasicMaterial({color:0x66dfd0,depthTest:false,transparent:true,opacity:.55}));
      cylinder.dispose();wire.position.z=policy.height_m/2;wire.userData.nominalBody=true;marker.add(wire);
    }
    marker.renderOrder=14;marker.traverse(child=>{child.renderOrder=14;});
    this.physicalReviewLayer.add(marker);this.reviewEvidenceMarkers.push(marker);this.reviewEvidenceByKey.set(sample.evidence_key,marker);
    return marker;
  }
  setPhysicalReviewTime(timestamp) {
    this.reviewTimestamp=timestamp;
    const frame=physicalReviewEvidenceFrame(this.physicalReviewPlan,timestamp),active=new Set();
    for(const sample of frame.samples){
      const marker=this.reviewEvidenceMarker(sample);active.add(marker);marker.visible=true;
      marker.position.copy(vector(sample.world_position));
      marker.userData={...marker.userData,evidenceState:sample.state,evidenceKey:sample.evidence_key,observationRef:sample.observation_ref??null,cameraId:sample.camera_id??null,
        candidateRefs:[...sample.candidate_refs],segmentStart:sample.segment_start};
      const color=sample.state==='PROJECTED_OBSERVATION'?0x66dfd0:0xffc266,quality=contactQualityStyle(sample.contact_quality);
      marker.userData.contactQuality=quality.status;
      marker.traverse(child=>{
        if(child.userData.segmentRing){child.visible=sample.segment_start;return;}
        if(child.userData.contactFlagRing){child.visible=quality.dashed;return;}
        if(child.userData.contactQualityTag){child.visible=Boolean(quality.tag);return;}
        if(child.isMesh&&child.geometry?.type==='SphereGeometry')child.material.wireframe=quality.hollow;
        if(child.material?.color)child.material.color.set(color);
        if(child.userData.nominalBody)child.visible=sample.state==='PROJECTED_OBSERVATION';
      });
    }
    for(const marker of this.reviewEvidenceMarkers??[])if(!active.has(marker))marker.visible=false;
    this.reviewEvidenceStatus={timestamp,shown:frame.samples.length,total:frame.total,omitted:frame.omitted};
    this.reviewContactSamples=frame.samples;
  }
  focusPhysicalReview(plan=this.physicalReviewPlan) {
    const focus=plan?.focus;
    if(this.disposed||!this.physicalReviewPlan||JSON.stringify(plan)!==this.physicalReviewSignature||focus?.purpose!=='DISPLAY_FOCUS_ONLY'||!finitePoint(focus.target)||!Number.isFinite(focus.radius)||focus.radius<=0)return false;
    this.target.copy(vector(focus.target));this.distance=Math.max(.5,focus.radius*3.2);this.updateCamera();this.render();return true;
  }
  addAxes() {
    const origin=new THREE.Vector3(this.bounds[0],this.bounds[1],.02);const len=this.span*.08;
    [[new THREE.Vector3(1,0,0),0xc77589],[new THREE.Vector3(0,1,0),0x77bdac],[new THREE.Vector3(0,0,1),0x869ade]].forEach(([dir,color])=>this.scene.add(new THREE.ArrowHelper(dir,origin,len,color,len*.17,len*.07)));
  }
  addObject(object,selected) {
    const points=(object.geometry?.points??[]).filter(finitePoint);if(!points.length)return;
    const color=selected?0xe7dcff:COLORS[object.kind]??0x8d93b6;const vectors=points.map(vector);const group=new THREE.Group();group.userData.objectId=object.object_id;
    if(object.geometry.type==='polygon'&&points.length>=3){
      const polygon=planarPolygon(points);if(!polygon)return;
      const triangles=THREE.ShapeUtils.triangulateShape(polygon.projected.map((point)=>new THREE.Vector2(...point)),[]);
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(polygon.positions,3));geometry.setIndex(triangles.flat());geometry.computeVertexNormals();
      const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,transparent:true,opacity:selected?.29:.13,side:THREE.DoubleSide,depthWrite:false,roughness:1,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1}));
      mesh.userData.objectId=object.object_id;group.add(mesh);this.pickables.push(mesh);
      const line=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(vectors),new THREE.LineBasicMaterial({color,transparent:true,opacity:selected?1:.75}));line.userData.objectId=object.object_id;group.add(line);this.pickables.push(line);
    }else if(vectors.length>1){
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(vectors),new THREE.LineBasicMaterial({color,linewidth:selected?3:2}));line.position.z=.035;line.userData.objectId=object.object_id;group.add(line);this.pickables.push(line);
      if(object.kind==='PORTAL'){vectors.forEach((p)=>{const dot=new THREE.Mesh(new THREE.SphereGeometry(this.span*.009,10,8),new THREE.MeshBasicMaterial({color}));dot.position.copy(p);dot.position.z+=.04;dot.userData.objectId=object.object_id;group.add(dot);this.pickables.push(dot);});}
    }else {
      const mesh=new THREE.Mesh(object.kind==='CAMERA'?new THREE.BoxGeometry(this.span*.025,this.span*.017,this.span*.017):new THREE.SphereGeometry(this.span*.012,12,8),new THREE.MeshStandardMaterial({color}));mesh.position.copy(vectors[0]);mesh.userData.objectId=object.object_id;group.add(mesh);this.pickables.push(mesh);
    }
    group.traverse((child)=>{child.userData.pickPriority=({CAMERA:0,PORTAL:1,REGION:2,WALKABLE:3})[object.kind]??4;});this.objectLayer.add(group);
  }
  addCalibratedCameras(cameras) {
    for(const camera of cameras){
      if(!finitePoint(camera.position))continue;
      const p=vector(camera.position);
      // Frusta require explicit calibrated camera-to-world matrices. Unknown affine poses stay absent.
      const converted=calibratedFrustum(camera.properties,this.span*.13);
      // Unsupported conventions intentionally have no frustum; camera markers remain selectable.
      if(!converted)continue;
      const corners=converted.map(vector);
      const segments=[];for(let i=0;i<4;i++){segments.push(p,corners[i],corners[i],corners[(i+1)%4]);}
      this.objectLayer.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(segments),new THREE.LineBasicMaterial({color:0x78c1c4,transparent:true,opacity:.38})));
    }
  }
  addEvent(event) {
    if(!event)return;
    const detail=event.detail??event;const projected=detail.projected_path??event.projected_path??[];
    this.projected=projected.filter((point)=>finitePoint(point.world_position));
    for(const point of this.projected){const marker=new THREE.Mesh(new THREE.SphereGeometry(this.span*.009,10,8),new THREE.MeshBasicMaterial({color:0xc4e6e2}));marker.position.copy(vector(point.world_position));marker.position.z+=.08;this.eventLayer.add(marker);}
    const candidates=detail.candidates??event.candidates??[];
    candidates.forEach((candidate,index)=>{
      const points=(candidate.polyline??[]).filter(finitePoint).map(vector);if(points.length<2)return;
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineDashedMaterial({color:[0xddbc83,0xa59ce0,0x70bdb5,0xc996bf][index%4],dashSize:this.span*.025,gapSize:this.span*.015,transparent:true,opacity:.8,depthTest:false}));line.position.z=.09+index*.006;line.renderOrder=5;line.computeLineDistances();this.eventLayer.add(line);
    });
    if(this.projected.length){this.timeMarker=new THREE.Mesh(new THREE.SphereGeometry(this.span*.018,14,10),new THREE.MeshBasicMaterial({color:0x80eadb}));this.timeMarker.position.copy(vector(this.projected[0].world_position));this.timeMarker.position.z+=.1;this.eventLayer.add(this.timeMarker);}
  }
  addSourceMeshes(meshes,layer=this.sourceLayer) {
    for(const source of meshes){
      if(!Array.isArray(source.vertices)||!Array.isArray(source.triangles))continue;
      if(!source.vertices.every(finitePoint))continue;
      const indices=source.triangles.flat();
      if(indices.some(i=>!Number.isInteger(i)||i<0||i>=source.vertices.length))continue;
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(source.vertices.flat(),3));
      geometry.setIndex(indices);geometry.computeVertexNormals();
      const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x71838b,roughness:.82,flatShading:false,side:THREE.DoubleSide,transparent:true,opacity:.48,depthWrite:false}));
      layer.add(mesh);
      const edges=new THREE.LineSegments(new THREE.EdgesGeometry(geometry,25),new THREE.LineBasicMaterial({color:0xa7bec9,transparent:true,opacity:.18}));layer.add(edges);
    }
  }
  addSupplementalDisplay(display) {
    this.displayContextLabel?.remove();this.displayContextLabel=null;
    if(!display||display.authority!=='PARTIAL_DISPLAY_CONTEXT'||display.display_only!==true)return;
    this.addSourceMeshes(display.architecture??[],this.supplementalLayer);
    for(const [ref,source] of Object.entries(display.geometries??{})){
      const rows=(display.instances??[]).filter(row=>row.geometry_ref===ref);
      if(!rows.length)continue;
      const geometry=new THREE.BufferGeometry();
      geometry.setAttribute('position',new THREE.Float32BufferAttribute(source.vertices.flat(),3));
      geometry.setIndex(source.triangles.flat());geometry.computeVertexNormals();
      const material=new THREE.MeshStandardMaterial({color:rows[0].kind==='CHAIR'?0x63718a:0x958570,
        roughness:.85,side:THREE.DoubleSide});
      const mesh=new THREE.InstancedMesh(geometry,material,rows.length);
      rows.forEach((row,index)=>mesh.setMatrixAt(index,new THREE.Matrix4().set(...row.matrix_world_metres.flat())));
      mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();
      mesh.userData={authority:'PARTIAL_DISPLAY_CONTEXT',displayOnly:true,geometryRef:ref,
        sourceObjectIds:rows.map(row=>row.object_id),assemblies:rows.map(row=>row.assembly)};
      this.supplementalLayer.add(mesh);
    }
    if(typeof this.container.append==='function'){
      const label=document.createElement('div');label.className='supplemental-display-status';
      label.setAttribute('role','status');label.textContent='PARTIAL_DISPLAY_CONTEXT · Auditorium：16 椅＋講台；全區覆蓋／物理／導航 UNKNOWN';
      label.style.cssText='position:absolute;left:8px;bottom:8px;max-width:85%;z-index:3;pointer-events:none;padding:5px 8px;background:rgba(15,23,37,.9);color:#b7c5d8;font-size:11px;';
      this.container.append(label);this.displayContextLabel=label;
    }
  }
  makeBody(inferred) {
    const root=new THREE.Group(),color=inferred?0xffc266:0x63dfdd;
    const material=new THREE.MeshStandardMaterial({color,roughness:.5,transparent:inferred,opacity:inferred?.62:1});
    const sphere=(radius,z)=>{const mesh=new THREE.Mesh(new THREE.SphereGeometry(radius,12,8),material);mesh.position.z=z;root.add(mesh);return mesh;};
    sphere(.11,1.58);sphere(.13,.84);
    const torso=new THREE.Mesh(new THREE.CapsuleGeometry(.14,.38,4,10),material);torso.rotation.x=Math.PI/2;torso.position.z=1.14;root.add(torso);
    const limb=(x,z,length,radius)=>{const pivot=new THREE.Group();pivot.position.set(x,0,z);const mesh=new THREE.Mesh(new THREE.CapsuleGeometry(radius,length,3,8),material);mesh.rotation.x=Math.PI/2;mesh.position.z=-length/2; pivot.add(mesh);root.add(pivot);return pivot;};
    root.userData.legs=[limb(-.09,.79,.68,.055),limb(.09,.79,.68,.055)];
    root.userData.arms=[limb(-.22,1.33,.49,.045),limb(.22,1.33,.49,.045)];
    const ring=new THREE.Mesh(new THREE.RingGeometry(.24,.27,24),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.55,side:THREE.DoubleSide}));ring.position.z=.015;root.add(ring);
    return root;
  }
  updateBodies(timestamp) {
    let markers=this.serverMarkers??bodyMarkers(this.observations,this.events,timestamp);
    if(this.presentation?.frames?.length){
      const frames=this.presentation.frames;const step=this.presentation.frame_step_s??.2;
      const frame=frames.slice().sort((a,b)=>Math.abs(a.timestamp-timestamp)-Math.abs(b.timestamp-timestamp))[0];
      if(frame&&Math.abs(frame.timestamp-timestamp)<=step/2+.00001)markers=[{ref:'source-display-body',world_position:frame.world_position,
        evidence_state:frame.evidence_state,joint_pose_authority:'DISPLAY_ONLY',presentation_only:true}];
    }
    const active=new Set();
    for(const marker of markers){
      if(!finitePoint(marker.world_position))continue;
      const inferred=marker.evidence_state==='INFERRED_GAP',key=marker.ref+':'+inferred;
      active.add(key);let body=this.bodyInstances.get(key);
      if(!body){body=this.makeBody(inferred);this.bodies.add(body);this.bodyInstances.set(key,body);}
      body.visible=true;body.position.copy(vector(marker.world_position));
      // Gait and anatomy are schematic presentation, never image-measured pose.
      const previous=body.userData.previous;
      const moved=previous?Math.hypot(marker.world_position[0]-previous[0],marker.world_position[1]-previous[1]):0;
      if(moved>.0001)body.rotation.z=Math.atan2(-(marker.world_position[0]-previous[0]),marker.world_position[1]-previous[1]);
      if(moved>.0001)body.userData.movingUntil=timestamp+.25;
      // The historical diagnostic track is not a selected candidate, so it never gets a walking animation.
      const phase=Math.sin(timestamp*7),swing=!marker.presentation_only&&timestamp<=(body.userData.movingUntil??-1)?phase*.24:0;
      body.userData.legs.forEach((limb,i)=>limb.rotation.x=swing*(i?1:-1));
      body.userData.arms.forEach((limb,i)=>limb.rotation.x=swing*(i?-1:1));
      body.userData.previous=[...marker.world_position];
    }
    for(const [key,body] of this.bodyInstances)body.visible=active.has(key);
  }
  setTimestamp(timestamp){
    this.currentTimestamp=timestamp;this.updateBlindHypothesis(timestamp);
    this.updateBodies(timestamp);
    this.updateCrossCamera(timestamp);
    this.setPhysicalReviewTime(timestamp);
    this.updateContactQualityStatus();
    if(!this.timeMarker||!this.projected?.length){this.render();return;}
    const eligible=this.projected.filter((point)=>Number.isFinite(point.timestamp)&&Math.abs(point.timestamp-timestamp)<=.6);
    this.timeMarker.visible=eligible.length>0;
    if(eligible.length){eligible.sort((a,b)=>Math.abs(a.timestamp-timestamp)-Math.abs(b.timestamp-timestamp));this.timeMarker.position.copy(vector(eligible[0].world_position));this.timeMarker.position.z+=.1;}
    this.render();
  }
  // Inspector label for the markers shown now: 接地點不可靠 with reasons. Text only; no marker is moved or hidden by it.
  updateContactQualityStatus() {
    const lines=contactQualityReadout([...(this.reviewContactSamples??[]),...(this.contactQualitySamples??[])],{cameraLabel:cameraShortLabel});
    this.contactQualityLines=lines;
    if(!lines.length){this.contactQualityLabel?.remove();this.contactQualityLabel=null;return;}
    if(!this.contactQualityLabel&&typeof this.container.append==='function'&&typeof document!=='undefined'){
      const label=document.createElement('div');label.className='contact-quality-status';label.setAttribute('role','status');label.setAttribute('data-contact-quality-status','');
      label.style.cssText='position:absolute;right:8px;top:8px;max-width:60%;z-index:3;pointer-events:none;padding:5px 8px;background:rgba(15,23,37,.9);color:#ffc266;font-size:11px;white-space:pre-line;';
      this.container.append(label);this.contactQualityLabel=label;
    }
    if(this.contactQualityLabel)this.contactQualityLabel.textContent=lines.join('\n');
  }
  setMarkers(markers,timestamp){this.serverMarkers=serverBodyMarkers(markers);this.setTimestamp(timestamp);}
  updateCamera(){this.camera.position.set(this.target.x+this.distance*Math.cos(this.pitch)*Math.cos(this.yaw),this.target.y+this.distance*Math.cos(this.pitch)*Math.sin(this.yaw),this.target.z+this.distance*Math.sin(this.pitch));this.camera.lookAt(this.target);}
  clearWorldDirectionsCompass() {
    this.worldDirectionsCompass?.remove();this.worldDirectionsCompass=null;this.worldDirectionsSignature=null;
    if(this.worldDirectionsPositionApplied&&this.container.style?.position==='relative')this.container.style.position=this.worldDirectionsPreviousPosition;
    this.worldDirectionsPositionApplied=false;
  }
  updateWorldDirectionsCompass() {
    const binding=this.snapshot?.source_binding;
    const allowed=this.snapshot?.evidence_level==='BLENDER_CAMERA_RGB_PIXEL_BASELINE'&&
      this.snapshot?.coordinates?.coordinate_frame==='RIGHT_HANDED_XYZ_Z_UP'&&binding?.units==='METRES'&&
      /^[a-f0-9]{64}$/.test(binding?.source_sha256??'');
    if(!allowed||typeof this.container.append!=='function'){if(this.worldDirectionsCompass)this.clearWorldDirectionsCompass();return;}
    if(!this.worldDirectionsCompass){
      const node=document.createElement('div');if(!node.style||typeof node.setAttribute!=='function')return;
      node.className='world-directions-compass';node.setAttribute('role','img');node.setAttribute('aria-label','來源世界軸 ±X、±Y、+Z；依目前視角投影，僅表示方向。');
      node.style.cssText='position:absolute;top:12px;right:12px;width:116px;height:116px;z-index:3;pointer-events:none;user-select:none;border:1px solid #45516b;border-radius:9px;background:rgba(15,23,37,.82);';
      if(this.container.style&&!this.container.style.position){this.worldDirectionsPreviousPosition=this.container.style.position;this.container.style.position='relative';this.worldDirectionsPositionApplied=true;}
      this.container.append(node);this.worldDirectionsCompass=node;
    }
    const signature=JSON.stringify([this.yaw,this.pitch]);if(signature===this.worldDirectionsSignature)return;
    this.worldDirectionsCompass.innerHTML=worldDirectionSVG(this.yaw,this.pitch);this.worldDirectionsSignature=signature;
  }
  resize(){if(this.disposed)return;const w=this.container.clientWidth,h=this.container.clientHeight;if(!w||!h)return;this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.render();}
  render(){if(!this.disposed){
    this.updateWorldDirectionsCompass();
    const perPixel=this.distance*2*Math.tan(this.camera.fov*Math.PI/360)/Math.max(this.container.clientHeight,1);
    for(const child of [...this.graphLayer?.children??[],...this.crossCameraLayer?.children??[],...(this.crossCameraCursors??[]).flatMap(item=>[...item.labels?.values()??[]]),...this.physicalGeometryLayer?.children??[],...this.physicalReviewLayer?.children??[],...this.geometryOverlayLayer?.children??[],...this.blindHypothesisLayer?.children??[]]){const size=child.userData.captionSize;if(size){
      const height=perPixel*(size.relation?23:26);child.scale.set(height*size.width/size.height,height,1);
    }}
    this.renderer.render(this.scene,this.camera);
  }}
  getPose(){return {target:this.target.toArray(),yaw:this.yaw,pitch:this.pitch,distance:this.distance};}
  reset(){this.target.copy(this.center);this.yaw=-Math.PI/2.8;this.pitch=.77;this.distance=this.span*1.5;this.updateCamera();this.render();}
  onPointerDown(e){this.drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,pan:e.button!==0||e.shiftKey};this.renderer.domElement.setPointerCapture(e.pointerId);}
  onPointerMove(e){if(!this.drag)return;const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;if(this.drag.pan){const scale=this.distance/Math.max(this.container.clientHeight,1)*.9;const right=new THREE.Vector3(-Math.sin(this.yaw),Math.cos(this.yaw),0);const forward=new THREE.Vector3(Math.cos(this.yaw),Math.sin(this.yaw),0);this.target.addScaledVector(right,-dx*scale).addScaledVector(forward,dy*scale);}else{this.yaw-=dx*.006;this.pitch=Math.max(.08,Math.min(1.48,this.pitch+dy*.006));}this.updateCamera();this.render();}
  onPointerUp(e){if(!this.drag)return;const moved=Math.hypot(e.clientX-this.drag.startX,e.clientY-this.drag.startY);const pan=this.drag.pan;this.drag=null;if(moved>5||pan)return;const rect=this.renderer.domElement.getBoundingClientRect();const cursor=new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);const raycaster=new THREE.Raycaster();raycaster.params.Line.threshold=this.span*.012;raycaster.setFromCamera(cursor,this.camera);const hits=raycaster.intersectObjects([...this.reviewPickables,...this.pickables],false);hits.sort((a,b)=>(a.object.userData.pickPriority??4)-(b.object.userData.pickPriority??4)||a.distance-b.distance);if(hits.length){const data=hits[0].object.userData;if(data.reviewRef)this.onReviewSelect?.(data.reviewRef);else this.onSelect(data.objectId);}}
  onWheel(e){e.preventDefault();this.distance=Math.max(this.span*.15,Math.min(this.span*8,this.distance*Math.exp(e.deltaY*.001)));this.updateCamera();this.render();}
  dispose(){if(this.disposed)return;this.disposed=true;this.displayContextLabel?.remove();this.contactQualityLabel?.remove();this.clearWorldDirectionsCompass();this.resizeObserver.disconnect();const canvas=this.renderer.domElement;canvas.removeEventListener('pointerdown',this.pointerDown);canvas.removeEventListener('pointermove',this.pointerMove);canvas.removeEventListener('pointerup',this.pointerUp);canvas.removeEventListener('pointercancel',this.pointerUp);canvas.removeEventListener('wheel',this.wheel);canvas.removeEventListener('contextmenu',this.contextMenu);this.clearLayer(this.scene);this.renderer.dispose();this.renderer.forceContextLoss();}
}

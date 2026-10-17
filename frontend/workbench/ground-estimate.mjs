// K3 (issue #20): display of the C4a `ground_estimate` sibling field (office-demo.interval-observation.v1).
// ground_estimate is a PROJECTED_OBSERVATION quality-annotated projection, never a position authority: nothing here moves,
// replaces or hides world_position, curves or existing markers. A POINT or SEGMENT is drawn only for a sample that is observed now.
// Only whitelisted fields are read. `diagnostics` (raw_interval_length_m, raw_near_m, raw_far_m, ...) and `segment.raw_*` are
// pre-clipping intermediates (R2): they are never drawn as positions and never shown as coordinates.
import {projectSegmentToImage,projectWorldPoint} from './geometry.mjs';
export const GROUND_ESTIMATE_SCHEMA='office-demo.interval-observation.v1';
export const GROUND_COLOR=0x66dfd0;
export const GROUND_COLOR_CSS='#76d9cf';

const isObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const point3=value=>Array.isArray(value)&&value.length>=3&&value.slice(0,3).every(Number.isFinite)?value.slice(0,3):null;
const point2=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)?[value[0],value[1]]:null;
const text=value=>typeof value==='string'&&value?value:null;
const metres=value=>Number.isFinite(value)?value.toFixed(1):null;

// Short names (<= 6 characters) so the two bases are told apart: foot-pixel band vs head ray with a height prior.
export const BASIS_LABELS={FOOT_RAY_PIXEL_BAND:'腳點像素帶',HEAD_RAY_HEIGHT_PRIOR:'頭頂射線',FOOT_POINT:'腳點'};
export const basisLabel=basis=>BASIS_LABELS[basis]??'接地區間';
export const unknownLabel=reason=>`接地 UNKNOWN（${reason}）`;
export const segmentLabel=length=>`區間 ${metres(length)} m`;

function details(estimate,segment) {
  const lines=[`依據 ${text(estimate.basis)??'UNKNOWN'}`];
  const constraints=(Array.isArray(estimate.constraints_applied)?estimate.constraints_applied:[]).flatMap(item=>
    isObject(item)&&text(item.kind)?[`${item.kind}:${text(item.effect)??'UNKNOWN'}`]:[]);
  if(constraints.length)lines.push(`約束 ${constraints.join(' → ')}`);
  const band=isObject(segment)?segment.foot_band:null,prior=isObject(segment)?segment.height_prior:null;
  if(isObject(band)&&Number.isFinite(band.band_px))lines.push(`像素帶 ±${band.band_px} px${Number.isFinite(band.body_radius_m)?' · 身體半徑 '+band.body_radius_m+' m':''}`);
  if(isObject(prior)&&Number.isFinite(prior.min_m)&&Number.isFinite(prior.max_m))lines.push(`高度先驗 ${prior.min_m.toFixed(2)}–${prior.max_m.toFixed(2)} m`);
  if(Number.isFinite(estimate.pixel_sensitivity_m))lines.push(`像素靈敏度 ${estimate.pixel_sensitivity_m.toFixed(2)} m/px`);
  if(isObject(segment)){
    const unknownLength=(Array.isArray(estimate.constraints_applied)?estimate.constraints_applied:[]).map(item=>item?.walkable_unknown_length_m).find(Number.isFinite);
    if(unknownLength>0)lines.push(`可行走未知段 ${unknownLength.toFixed(1)} m（保留）`);
  }
  return lines;
}

// Returns null when the sample has no ground_estimate (drawing stays exactly as before).
// kind: POINT | SEGMENT | UNKNOWN. A READY estimate whose geometry is malformed is shown as UNKNOWN, never repaired or guessed.
export function groundEstimatePlan(estimate) {
  if(!isObject(estimate))return null;
  const ref=text(estimate.observation_ref),anchor=point2(estimate.image_anchor_px);
  const base={observation_ref:ref,camera_id:text(estimate.camera_id),timestamp:Number.isFinite(estimate.timestamp_s)?estimate.timestamp_s:null,image_anchor_px:anchor,
    authority:'PROJECTION_ONLY_NOT_POSITION_AUTHORITY'};
  const unknown=reason=>({...base,kind:'UNKNOWN',reason,label:unknownLabel(reason),basis:null,basis_label:null,details:[],point:null,near:null,far:null,length_m:null});
  if(estimate.schema_version!==GROUND_ESTIMATE_SCHEMA)return unknown('SCHEMA_UNSUPPORTED');
  if(estimate.status!=='READY')return unknown(text(estimate.reason)??'REASON_MISSING');
  if(estimate.estimate_kind==='POINT'){
    const point=point3(estimate.point_m);
    if(!point)return unknown('POINT_MISSING');
    return {...base,kind:'POINT',reason:null,label:'接地點',basis:text(estimate.basis),basis_label:basisLabel(estimate.basis),details:details(estimate,null),point,near:null,far:null,length_m:null};
  }
  if(estimate.estimate_kind==='SEGMENT'&&isObject(estimate.segment)){
    const near=point3(estimate.segment.near_m),far=point3(estimate.segment.far_m);
    if(!near||!far||!Number.isFinite(estimate.segment.length_m)||estimate.segment.length_m<0)return unknown('SEGMENT_MALFORMED');
    return {...base,kind:'SEGMENT',reason:null,label:segmentLabel(estimate.segment.length_m),basis:text(estimate.basis),basis_label:basisLabel(estimate.basis),details:details(estimate,estimate.segment),point:null,near,far,length_m:estimate.segment.length_m};
  }
  return unknown('ESTIMATE_KIND_UNSUPPORTED');
}

// What is drawn/listed next to a SEGMENT: which basis produced it, then the interval length. POINT and UNKNOWN keep their own labels.
export const displayLabel=plan=>plan.kind==='SEGMENT'?`${plan.basis_label} ${plan.label}`:plan.label;

const observed=sample=>sample?.state===undefined||sample.state==='PROJECTED_OBSERVATION';

// Plans for the samples shown at one tick. Blind-interval ticks have no sample, so nothing is drawn; an inferred sample is skipped.
export function groundEstimatePlans(samples) {
  const seen=new Set();
  return (Array.isArray(samples)?samples:[]).flatMap(sample=>{
    if(!observed(sample))return [];
    const plan=groundEstimatePlan(sample?.ground_estimate);if(!plan)return [];
    const key=plan.observation_ref??JSON.stringify([plan.camera_id,plan.timestamp,plan.kind]);
    if(seen.has(key))return [];seen.add(key);return [plan];
  });
}

// Inspector lines. UNKNOWN is a neutral text line only. POINT/SEGMENT list basis, constraints and pixel sensitivity.
export function groundEstimateReadout(samples,{cameraLabel=id=>id??'鏡頭未知'}={}) {
  return groundEstimatePlans(samples).map(plan=>{
    const where=`${cameraLabel(plan.camera_id)}${plan.timestamp===null?'':' · '+plan.timestamp.toFixed(1)+' s'}`;
    return plan.kind==='UNKNOWN'?`${plan.label} · ${where}`:`${displayLabel(plan)} · ${where}\n  ${plan.details.join('；')}`;
  });
}

// 2D overlay fragment for one candidate-evidence item (SVG user space = image pixels). No ground geometry can be placed in the image
// without a camera model, so the marker sits at the estimate's own image anchor: the contact pixel for POINT, the head pixel for SEGMENT.
// UNKNOWN draws nothing, only a tooltip.
export function groundEstimateOverlaySVG(item,{n=value=>Number(value.toFixed(2)),arm,stroke,font,escape=value=>String(value)}={}) {
  const plan=groundEstimatePlan(item?.ground_estimate);if(!plan)return '';
  const tooltip=`<title>${escape([plan.label,...plan.details].join(' · '))}</title>`;
  if(plan.kind==='UNKNOWN'||!plan.image_anchor_px)return `<g data-ground-estimate="UNKNOWN" data-ground-reason="${escape(plan.reason??'UNKNOWN')}">${tooltip}</g>`;
  const [u,v]=plan.image_anchor_px,r=n(arm*.9);
  const shape=plan.kind==='POINT'
    ?`<rect x="${n(u-r)}" y="${n(v-r)}" width="${n(r*2)}" height="${n(r*2)}" fill="none"/>`
    :`<path d="M${n(u)},${n(v-r)} L${n(u+r)},${n(v)} L${n(u)},${n(v+r)} L${n(u-r)},${n(v)} Z" fill="rgba(118,217,207,.25)"/>`;
  return `<g data-ground-estimate="${plan.kind}" stroke="${GROUND_COLOR_CSS}" stroke-width="${n(stroke*1.2)}">${tooltip}${shape}`+
    `<text x="${n(u+r*1.4)}" y="${n(v-r*.4)}" font-size="${n(font*.85)}" fill="${GROUND_COLOR_CSS}" stroke="none">${escape(plan.label)}</text></g>`;
}

// 3D: one group per scene, rebuilt for the samples shown now. THREE is injected so this module stays importable under node.
// POINT: hollow square at the floor point (distinct from the solid world_position sphere). SEGMENT: translucent thick bar on the floor
// with an end cap at each end. UNKNOWN and absent estimates add no geometry.
export function syncGroundEstimateGroup(THREE,group,parent,samples,{span=10,lift=.03,label=null}={}) {
  const plans=groundEstimatePlans(samples).filter(plan=>plan.kind!=='UNKNOWN');
  if(!plans.length&&!group)return null;
  if(!group){group=new THREE.Group();group.userData.groundEstimateLayer=true;parent.add(group);}
  const signature=JSON.stringify([span,plans.map(plan=>[plan.observation_ref,plan.kind,plan.near,plan.far,plan.point])]);
  if(group.userData.signature===signature)return group;
  group.userData.signature=signature;
  for(const child of [...group.children]){group.remove(child);child.traverse?.(part=>{part.geometry?.dispose?.();part.material?.map?.dispose?.();part.material?.dispose?.();});}
  const side=span*.012,width=span*.006,material=opacity=>new THREE.MeshBasicMaterial({color:GROUND_COLOR,transparent:true,opacity,depthTest:false});
  for(const plan of plans){
    const mark=new THREE.Group();mark.userData={groundEstimate:plan.kind,observationRef:plan.observation_ref,label:plan.label};
    if(plan.kind==='POINT'){
      const box=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(side,side,side*.25)),new THREE.LineBasicMaterial({color:GROUND_COLOR,depthTest:false}));
      box.position.set(plan.point[0],plan.point[1],plan.point[2]+lift);mark.add(box);
    }else{
      const [a,b]=[plan.near,plan.far],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
      const bar=new THREE.Mesh(new THREE.BoxGeometry(Math.max(length,width*.5),width,width*.4),material(.55));
      bar.position.set((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2+lift);bar.rotation.z=Math.atan2(dy,dx);mark.add(bar);
      const sprite=typeof label==='function'?label(`${displayLabel(plan)}`):null;
      if(sprite){sprite.position.set((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2+lift+width*2);sprite.renderOrder=13;mark.add(sprite);}
      for(const end of [a,b]){
        const cap=new THREE.Mesh(new THREE.SphereGeometry(Math.min(width*.9,Math.max(length*.2,width*.3)),10,8),material(.9));cap.position.set(end[0],end[1],end[2]+lift);mark.add(cap);
      }
    }
    mark.traverse(part=>{part.renderOrder=13;});group.add(mark);
  }
  return group;
}

// Observations (from `query`, any camera) that carry a ground_estimate, reduced to what the display needs. Order and refs are kept;
// an observation without the field is dropped, so scenes that never provide it return an empty list and change nothing.
export function collectGroundObservations(...lists) {
  const seen=new Set();
  return lists.flatMap(list=>Array.isArray(list)?list:[]).flatMap(item=>{
    if(!isObject(item?.ground_estimate)||!Number.isFinite(item.timestamp))return [];
    const key=text(item.observation_ref)??JSON.stringify([item.camera_id,item.timestamp]);
    if(seen.has(key))return [];seen.add(key);
    return [{observation_ref:text(item.observation_ref),camera_id:text(item.camera_id),frame_ref:text(item.frame_ref),timestamp:item.timestamp,ground_estimate:item.ground_estimate}];
  }).sort((a,b)=>a.timestamp-b.timestamp||String(a.camera_id).localeCompare(String(b.camera_id)));
}
// Observations shown at one cursor time. A blind interval has no observation, so it yields nothing; nothing is held or extrapolated.
export function groundObservationsAt(observations,timestamp,{tolerance=.100001,cameraId=null,frameRef=null}={}) {
  if(!Number.isFinite(timestamp))return [];
  return (Array.isArray(observations)?observations:[]).filter(item=>
    Number.isFinite(item?.timestamp)&&Math.abs(item.timestamp-timestamp)<=tolerance&&(cameraId===null||item.camera_id===cameraId)&&(frameRef===null||item.frame_ref===frameRef));
}

// 2D camera-tile overlay for one camera: the SEGMENT's floor endpoints projected through the bound calibration (so the drawn line is the
// floor interval as the camera sees it, not the midpoint), end caps, and a basis + length label. POINT: hollow square. UNKNOWN: nothing.
export function groundEstimateTileSVG(items,{calibration,width,height,cameraId=null,escape=value=>String(value)}={}) {
  if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)return '';
  const n=value=>Number(value.toFixed(2)),size=Math.max(width,height),stroke=n(size*.004),cap=n(size*.005),font=n(size*.02);
  const shapes=groundEstimatePlans(items).flatMap((plan,index)=>{
    if(plan.kind==='SEGMENT'){
      const line=projectSegmentToImage(calibration,plan.near,plan.far);if(!line)return [];
      const [[u0,v0],[u1,v1]]=[line.from,line.to],tx=n(Math.min(Math.max((u0+u1)/2,0),width)),ty=n(Math.max(font*(index+1.2),Math.min(v0,v1)-cap*2-font*index*1.2));
      return [`<g data-ground-estimate="SEGMENT" data-ground-basis="${escape(plan.basis??'')}" stroke="${GROUND_COLOR_CSS}"><title>${escape([displayLabel(plan),...plan.details].join(' · '))}</title>`+
        `<line x1="${n(u0)}" y1="${n(v0)}" x2="${n(u1)}" y2="${n(v1)}" stroke-width="${stroke}" stroke-opacity=".7" stroke-linecap="round"/>`+
        `<circle cx="${n(u0)}" cy="${n(v0)}" r="${cap}" fill="none" stroke-width="${n(stroke*.6)}"/><circle cx="${n(u1)}" cy="${n(v1)}" r="${cap}" fill="none" stroke-width="${n(stroke*.6)}"/>`+
        `<text x="${tx}" y="${ty}" font-size="${font}" fill="${GROUND_COLOR_CSS}" stroke="none" text-anchor="middle">${escape(displayLabel(plan))}</text></g>`];
    }
    if(plan.kind==='POINT'){
      const at=projectWorldPoint(calibration,plan.point);if(!at)return [];
      return [`<g data-ground-estimate="POINT" stroke="${GROUND_COLOR_CSS}"><title>${escape([plan.label,...plan.details].join(' · '))}</title><rect x="${n(at.u-cap)}" y="${n(at.v-cap)}" width="${n(cap*2)}" height="${n(cap*2)}" fill="none" stroke-width="${stroke}"/></g>`];
    }
    return [];
  });
  if(!shapes.length)return '';
  return `<svg class="ground-estimate-overlay" data-ground-estimate-overlay="${escape(cameraId??'')}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="接地區間：觀測推得的範圍，不是單一位置">${shapes.join('')}</svg>`;
}

// Loads the ground_estimate-bearing observations of every selected camera. Only when the primary camera's answer already carries the
// field are the other cameras queried (older scenes cost no extra request). A failed extra query keeps what was already obtained.
export async function loadGroundObservations(primaryObservations,{cameraIds=[],cameraId=null,query}) {
  const primary=collectGroundObservations(primaryObservations);
  if(!primary.length||typeof query!=='function')return primary;
  const others=[...new Set(cameraIds)].filter(id=>id&&id!==cameraId);
  const results=await Promise.all(others.map(id=>Promise.resolve().then(()=>query(id)).then(result=>result?.observations,()=>[])));
  return collectGroundObservations(primaryObservations,...results);
}

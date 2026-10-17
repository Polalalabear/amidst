// K3 (issue #20): display of the C4a `ground_estimate` sibling field (office-demo.interval-observation.v1).
// ground_estimate is a PROJECTED_OBSERVATION quality-annotated projection, never a position authority: nothing here moves,
// replaces or hides world_position, curves or existing markers. A POINT or SEGMENT is drawn only for a sample that is observed now.
// Only whitelisted fields are read. `diagnostics` (raw_interval_length_m, raw_near_m, raw_far_m, ...) and `segment.raw_*` are
// pre-clipping intermediates (R2): they are never drawn as positions and never shown as coordinates.
export const GROUND_ESTIMATE_SCHEMA='office-demo.interval-observation.v1';
export const GROUND_COLOR=0x66dfd0;
export const GROUND_COLOR_CSS='#76d9cf';

const isObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const point3=value=>Array.isArray(value)&&value.length>=3&&value.slice(0,3).every(Number.isFinite)?value.slice(0,3):null;
const point2=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)?[value[0],value[1]]:null;
const text=value=>typeof value==='string'&&value?value:null;
const metres=value=>Number.isFinite(value)?value.toFixed(1):null;

export const unknownLabel=reason=>`接地 UNKNOWN（${reason}）`;
export const segmentLabel=length=>`區間 ${metres(length)} m`;

function details(estimate,segment) {
  const lines=[`依據 ${text(estimate.basis)??'UNKNOWN'}`];
  const constraints=(Array.isArray(estimate.constraints_applied)?estimate.constraints_applied:[]).flatMap(item=>
    isObject(item)&&text(item.kind)?[`${item.kind}:${text(item.effect)??'UNKNOWN'}`]:[]);
  if(constraints.length)lines.push(`約束 ${constraints.join(' → ')}`);
  if(Number.isFinite(estimate.pixel_sensitivity_m))lines.push(`像素靈敏度 ${estimate.pixel_sensitivity_m.toFixed(2)} m/px`);
  if(segment){
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
  const unknown=reason=>({...base,kind:'UNKNOWN',reason,label:unknownLabel(reason),details:[],point:null,near:null,far:null,length_m:null});
  if(estimate.schema_version!==GROUND_ESTIMATE_SCHEMA)return unknown('SCHEMA_UNSUPPORTED');
  if(estimate.status!=='READY')return unknown(text(estimate.reason)??'REASON_MISSING');
  if(estimate.estimate_kind==='POINT'){
    const point=point3(estimate.point_m);
    if(!point)return unknown('POINT_MISSING');
    return {...base,kind:'POINT',reason:null,label:'接地點',details:details(estimate,false),point,near:null,far:null,length_m:null};
  }
  if(estimate.estimate_kind==='SEGMENT'&&isObject(estimate.segment)){
    const near=point3(estimate.segment.near_m),far=point3(estimate.segment.far_m);
    if(!near||!far||!Number.isFinite(estimate.segment.length_m)||estimate.segment.length_m<0)return unknown('SEGMENT_MALFORMED');
    return {...base,kind:'SEGMENT',reason:null,label:segmentLabel(estimate.segment.length_m),details:details(estimate,true),point:null,near,far,length_m:estimate.segment.length_m};
  }
  return unknown('ESTIMATE_KIND_UNSUPPORTED');
}

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
    return plan.kind==='UNKNOWN'?`${plan.label} · ${where}`:`${plan.label} · ${where}\n  ${plan.details.join('；')}`;
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
export function syncGroundEstimateGroup(THREE,group,parent,samples,{span=10,lift=.03}={}) {
  const plans=groundEstimatePlans(samples).filter(plan=>plan.kind!=='UNKNOWN');
  if(!plans.length&&!group)return null;
  if(!group){group=new THREE.Group();group.userData.groundEstimateLayer=true;parent.add(group);}
  for(const child of [...group.children]){group.remove(child);child.traverse?.(part=>{part.geometry?.dispose?.();part.material?.dispose?.();});}
  const side=span*.012,width=span*.008,material=opacity=>new THREE.MeshBasicMaterial({color:GROUND_COLOR,transparent:true,opacity,depthTest:false});
  for(const plan of plans){
    const mark=new THREE.Group();mark.userData={groundEstimate:plan.kind,observationRef:plan.observation_ref,label:plan.label};
    if(plan.kind==='POINT'){
      const box=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(side,side,side*.25)),new THREE.LineBasicMaterial({color:GROUND_COLOR,depthTest:false}));
      box.position.set(plan.point[0],plan.point[1],plan.point[2]+lift);mark.add(box);
    }else{
      const [a,b]=[plan.near,plan.far],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
      const bar=new THREE.Mesh(new THREE.BoxGeometry(Math.max(length,width*.5),width,width*.4),material(.55));
      bar.position.set((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2+lift);bar.rotation.z=Math.atan2(dy,dx);mark.add(bar);
      for(const end of [a,b]){
        const cap=new THREE.Mesh(new THREE.SphereGeometry(width*.9,10,8),material(.9));cap.position.set(end[0],end[1],end[2]+lift);mark.add(cap);
      }
    }
    mark.traverse(part=>{part.renderOrder=13;});group.add(mark);
  }
  return group;
}

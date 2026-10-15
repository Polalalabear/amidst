// Pure geometry conversions shared by the renderer and numerical regression tests.
const finitePoint = (point) => Array.isArray(point) && point.length === 3 && point.every(Number.isFinite);

export function calibratedPixelPoint(calibration, pixel, depth) {
  const k=calibration??{},matrix=k.camera_to_world;
  if(k.calibration_kind!=='PINHOLE'||k.convention!=='BLENDER_NEG_Z_UP_Y')return null;
  if(!Array.isArray(matrix)||matrix.length!==4||!matrix.every((row)=>Array.isArray(row)&&row.length===4&&row.every(Number.isFinite)))return null;
  if(![k.fx,k.fy,k.cx,k.cy,depth,...pixel].every(Number.isFinite)||k.fx<=0||k.fy<=0||depth<=0)return null;
  const [u,v]=pixel;
  const local=[(u-k.cx)/k.fx*depth,-(v-k.cy)/k.fy*depth,-depth,1];
  const transformed=matrix.map((row)=>row.reduce((sum,value,index)=>sum+value*local[index],0));
  if(!transformed.every(Number.isFinite)||Math.abs(transformed[3])<1e-12)return null;
  return transformed.slice(0,3).map((value)=>value/transformed[3]);
}

export function calibratedFrustum(calibration,depth) {
  if(!Number.isFinite(calibration?.width)||!Number.isFinite(calibration?.height)||calibration.width<=0||calibration.height<=0)return null;
  const corners=[[0,0],[calibration.width,0],[calibration.width,calibration.height],[0,calibration.height]].map((pixel)=>calibratedPixelPoint(calibration,pixel,depth));
  return corners.every((point)=>point!==null)?corners:null;
}

export function planarPolygon(points) {
  if(!Array.isArray(points)||points.length<3||!points.every(finitePoint))return null;
  // Newell's normal remains stable for vertical/tilted contours; triangulate only
  // on its dominant projection and retain the original XYZ for every vertex.
  const normal=[0,0,0];
  for(let i=0;i<points.length;i++){
    const a=points[i],b=points[(i+1)%points.length];
    normal[0]+=(a[1]-b[1])*(a[2]+b[2]);
    normal[1]+=(a[2]-b[2])*(a[0]+b[0]);
    normal[2]+=(a[0]-b[0])*(a[1]+b[1]);
  }
  const magnitude=Math.hypot(...normal);
  if(magnitude<1e-12)return null;
  const unit=normal.map((value)=>value/magnitude);
  const dropAxis=normal.map(Math.abs).indexOf(Math.max(...normal.map(Math.abs)));
  const axes=[0,1,2].filter((axis)=>axis!==dropAxis);
  return {
    positions:points.flat(),
    projected:points.map((point)=>axes.map((axis)=>point[axis])),
    normal:unit,
    dropAxis,
  };
}

// Dimensionless world directions in the renderer's Z-up orbit view. Screen Y points down.
export function worldDirectionProjection(yaw,pitch) {
  if(!Number.isFinite(yaw)||!Number.isFinite(pitch)||Math.abs(pitch)>=Math.PI/2)return null;
  const sinYaw=Math.sin(yaw),cosYaw=Math.cos(yaw),sinPitch=Math.sin(pitch),cosPitch=Math.cos(pitch);
  const right=[-sinYaw,cosYaw,0],up=[-sinPitch*cosYaw,-sinPitch*sinYaw,cosPitch],towardViewer=[cosPitch*cosYaw,cosPitch*sinYaw,sinPitch];
  return [['X',0,1],['X',0,-1],['Y',1,1],['Y',1,-1],['Z',2,1]].map(([axis,index,sign])=>({
    axis,sign,label:(sign>0?'+':'−')+axis,x:right[index]*sign,y:-up[index]*sign,depth:towardViewer[index]*sign,
  }));
}
export function worldDirectionSVG(yaw,pitch) {
  const directions=worldDirectionProjection(yaw,pitch);if(!directions)return '';
  const colors={X:'#e7a0ad',Y:'#8fdbbd',Z:'#acbaff'},number=value=>Number(value.toFixed(3));
  const arrows=[...directions].sort((a,b)=>a.depth-b.depth).map(direction=>{
    const length=Math.hypot(direction.x,direction.y),dx=length>1e-10?direction.x/length:0,dy=length>1e-10?direction.y/length:direction.sign;
    const x=58+direction.x*31,y=65+direction.y*31,color=colors[direction.axis],opacity=direction.sign>0?1:.7;
    const head=length>1e-10?`<path d="M ${number(x-dx*5-dy*2.5)} ${number(y-dy*5+dx*2.5)} L ${number(x)} ${number(y)} L ${number(x-dx*5+dy*2.5)} ${number(y-dy*5-dx*2.5)}" fill="none" stroke="${color}" stroke-width="1.6"/>`:
      `<circle cx="${number(x)}" cy="${number(y)}" r="2" fill="${direction.depth>0?color:'none'}" stroke="${color}"/>`;
    return `<g data-world-axis="${direction.label}" opacity="${opacity}"><line x1="58" y1="65" x2="${number(x)}" y2="${number(y)}" stroke="${color}" stroke-width="1.5"/>${head}<text x="${number(x+dx*8)}" y="${number(y+dy*8+3)}" text-anchor="middle" font-size="10" fill="${color}" stroke="#121b2b" stroke-width="2" paint-order="stroke">${direction.label}</text></g>`;
  }).join('');
  return `<svg viewBox="0 0 116 116" width="116" height="116" aria-hidden="true"><text x="58" y="14" text-anchor="middle" font-size="10" fill="#c6d1e3">來源世界軸</text>${arrows}<circle cx="58" cy="65" r="2" fill="#c6d1e3"/><text x="58" y="112" text-anchor="middle" font-size="8" fill="#9aabc4">視角投影 · Z-up</text></svg>`;
}

// ---- Evidence-grounded camera/annotation overlays (display only) ----
// Wording is fixed: a frustum is pinhole geometry, never occlusion-aware visibility or a traversable opening.
export const FRUSTUM_LABEL='GEOMETRIC FRUSTUM · VISIBILITY UNKNOWN';
export const ANNOTATION_LABEL='SOURCE ANNOTATION · UNVERIFIED';
const PORTAL_SOURCE_ID=/^PORTAL_[A-Z0-9_]{1,64}$/;
const validCalibration=(k)=>{
  if(!k||k.convention!=='BLENDER_NEG_Z_UP_Y'||(k.pixel_origin!==undefined&&k.pixel_origin!=='TOP_LEFT_CONTINUOUS'))return false;
  const m=k.camera_to_world;
  if(!Array.isArray(m)||m.length!==4||!m.every((row)=>Array.isArray(row)&&row.length===4&&row.every(Number.isFinite)))return false;
  if(![k.fx,k.fy,k.cx,k.cy,k.width,k.height].every(Number.isFinite)||k.fx<=0||k.fy<=0||k.width<=0||k.height<=0)return false;
  // The inverse below is the transpose, so only (near-)orthonormal rotations are accepted.
  for(let a=0;a<3;a++)for(let b=a;b<3;b++){
    const dot=m[0][a]*m[0][b]+m[1][a]*m[1][b]+m[2][a]*m[2][b];
    if(Math.abs(dot-(a===b?1:0))>1e-3)return false;
  }
  return true;
};
export const cameraRole=(cameraId)=>/(?:^|_)(FRONT|REAR)(?:_|$)/.exec(String(cameraId??'').toUpperCase())?.[1]??null;

// Frustum corners, apex and unit viewing direction (-Z column of camera_to_world) at a display depth.
export function cameraFrustumOverlay(camera,depth) {
  const k=camera?.calibration;
  if(!validCalibration(k)||!Number.isFinite(depth)||depth<=0)return null;
  // snapshot.cameras[].calibration omits calibration_kind; validCalibration() already pinned the pinhole convention.
  const pinhole={...k,calibration_kind:'PINHOLE'},corners=calibratedFrustum(pinhole,depth);if(!corners)return null;
  const m=k.camera_to_world,apex=[m[0][3],m[1][3],m[2][3]],forward=[-m[0][2],-m[1][2],-m[2][2]],up=[m[0][1],m[1][1],m[2][1]];
  const centre=calibratedPixelPoint(pinhole,[k.cx,k.cy],depth);
  return {camera_id:camera.camera_id,camera_ref:camera.camera_ref??null,role:cameraRole(camera.camera_id),apex,corners,forward,up,centre,
    label:FRUSTUM_LABEL,authority:camera.authority??null,coverage_status:camera.coverage_status??null};
}

// World point -> continuous top-left pixel; null when it is at/behind the camera plane.
export function projectWorldPoint(calibration,point,minDepth=1e-6) {
  if(!validCalibration(calibration)||!finitePoint(point))return null;
  const m=calibration.camera_to_world,rel=point.map((value,index)=>value-m[index][3]);
  const local=[0,1,2].map((column)=>rel[0]*m[0][column]+rel[1]*m[1][column]+rel[2]*m[2][column]);
  const depth=-local[2];
  if(!(depth>minDepth))return null;
  return {u:calibration.fx*local[0]/depth+calibration.cx,v:calibration.cy-calibration.fy*local[1]/depth,depth};
}

// Clip a world segment to the camera near plane, project it, then clip to [0,width]x[0,height] (Liang-Barsky).
export function projectSegmentToImage(calibration,a,b) {
  if(!validCalibration(calibration)||!finitePoint(a)||!finitePoint(b))return null;
  const m=calibration.camera_to_world;
  const depthOf=(p)=>-([0,1,2].reduce((sum,row)=>sum+(p[row]-m[row][3])*m[row][2],0));
  const near=Math.max(Number.isFinite(calibration.clip_start)?calibration.clip_start:0,1e-3);
  const da=depthOf(a),db=depthOf(b);
  if(da<near&&db<near)return null;
  let p=a,q=b;
  if(da<near||db<near){
    const t=(near-da)/(db-da),hit=a.map((value,index)=>value+(b[index]-value)*t);
    if(da<near)p=hit;else q=hit;
  }
  const pa=projectWorldPoint(calibration,p,near*0.5),pb=projectWorldPoint(calibration,q,near*0.5);
  if(!pa||!pb)return null;
  let t0=0,t1=1;const dx=pb.u-pa.u,dy=pb.v-pa.v;
  for(const [pp,qq] of [[-dx,pa.u],[dx,calibration.width-pa.u],[-dy,pa.v],[dy,calibration.height-pa.v]]){
    if(Math.abs(pp)<1e-12){if(qq<0)return null;continue;}
    const r=qq/pp;
    if(pp<0){if(r>t1)return null;if(r>t0)t0=r;}else{if(r<t0)return null;if(r<t1)t1=r;}
  }
  return {from:[pa.u+dx*t0,pa.v+dy*t0],to:[pa.u+dx*t1,pa.v+dy*t1]};
}

// Outline = triangle edges used by exactly one face; interior triangulation diagonals are not drawn.
export function boundaryEdges(vertices,triangles) {
  const counts=new Map();
  for(const face of triangles??[])for(const [x,y] of [[face[0],face[1]],[face[1],face[2]],[face[2],face[0]]]){
    if(x===y)continue;const key=x<y?`${x}:${y}`:`${y}:${x}`;
    const entry=counts.get(key);if(entry)entry.n++;else counts.set(key,{n:1,pair:[x,y]});
  }
  return [...counts.values()].filter((entry)=>entry.n===1).map((entry)=>entry.pair.map((index)=>vertices[index]));
}

// Source portal annotations from the public physical-review response. Entries without a reliable
// PORTAL_* source id (the primitive's own `label`) or with unsupported structure are dropped, never guessed.
export function sourceAnnotations(review) {
  const out=[];
  for(const primitive of Array.isArray(review?.geometry_primitives)?review.geometry_primitives:[]){
    if(primitive?.kind!=='SOURCE_ANNOTATION'||!PORTAL_SOURCE_ID.test(primitive.label??'')||primitive.units!=='METRES'||
      primitive.is_aperture!==false||primitive.is_collider!==false||!Array.isArray(primitive.vertices)||!primitive.vertices.length||!primitive.vertices.every(finitePoint)||
      !Array.isArray(primitive.triangles)||primitive.triangles.some((face)=>!Array.isArray(face)||face.length!==3||face.some((i)=>!Number.isInteger(i)||i<0||i>=primitive.vertices.length)))continue;
    const edges=boundaryEdges(primitive.vertices,primitive.triangles);if(!edges.length)continue;
    out.push({source_id:primitive.label,geometry_ref:primitive.geometry_ref??null,edges,label:ANNOTATION_LABEL});
  }
  return out;
}

// Per-camera 2D overlay in image pixels; the SVG viewBox (width x height) makes it independent of tile size.
export function cameraOverlayModel(camera,annotations) {
  const k=camera?.calibration;
  if(!validCalibration(k))return {camera_id:camera?.camera_id??null,supported:false,width:null,height:null,segments:[]};
  const segments=[];
  for(const annotation of annotations??[])for(const [a,b] of annotation.edges){
    const clipped=projectSegmentToImage(k,a,b);
    if(clipped)segments.push({source_id:annotation.source_id,...clipped});
  }
  return {camera_id:camera.camera_id,supported:true,width:k.width,height:k.height,segments};
}

const esc=(value)=>String(value).replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
export function cameraOverlaySVG(model) {
  if(!model?.supported)return '';
  const n=(value)=>Number(value.toFixed(2)),size=Math.max(model.width,model.height),font=n(size*0.022);
  const lines=model.segments.map((s)=>`<line data-source-id="${esc(s.source_id)}" x1="${n(s.from[0])}" y1="${n(s.from[1])}" x2="${n(s.to[0])}" y2="${n(s.to[1])}"/>`).join('');
  const seen=new Set(),labels=model.segments.filter((s)=>!seen.has(s.source_id)&&seen.add(s.source_id)).map((s,index)=>{
    const x=Math.min(Math.max((s.from[0]+s.to[0])/2,font*8),model.width-font*8),y=Math.min(Math.max((s.from[1]+s.to[1])/2,font*(2+2*index)),model.height-font);
    return `<text data-source-label="${esc(s.source_id)}" x="${n(x)}" y="${n(y)}" text-anchor="middle" font-size="${font}">${esc(s.source_id)} · ${ANNOTATION_LABEL}</text>`;
  }).join('');
  if(!lines)return `<svg class="geometry-overlay" data-geometry-overlay="${esc(model.camera_id)}" data-segments="0" viewBox="0 0 ${model.width} ${model.height}" preserveAspectRatio="xMidYMid meet" aria-hidden="true"></svg>`;
  return `<svg class="geometry-overlay" data-geometry-overlay="${esc(model.camera_id)}" data-segments="${model.segments.length}" viewBox="0 0 ${model.width} ${model.height}" preserveAspectRatio="xMidYMid meet" aria-hidden="true"><g class="geometry-annotation" fill="none" stroke-width="${n(size*0.003)}" stroke-dasharray="${n(size*0.012)} ${n(size*0.007)}">${lines}</g><g class="geometry-annotation-label">${labels}</g></svg>`;
}

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

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {cameraFrustumOverlay,projectWorldPoint,projectSegmentToImage,boundaryEdges,sourceAnnotations,cameraOverlayModel,cameraOverlaySVG,cameraRole,FRUSTUM_LABEL,ANNOTATION_LABEL} from './geometry.mjs';

// Camera at (10,-4,8) looking along world +X: local -Z -> world +X, local +Y -> world +Z, local +X -> world +Y.
const pose=[[0,0,-1,10],[1,0,0,-4],[0,1,0,8],[0,0,0,1]];
const calibration={convention:'BLENDER_NEG_Z_UP_Y',pixel_origin:'TOP_LEFT_CONTINUOUS',meters_per_unit:1,clip_start:.1,clip_end:100,fx:500,fy:500,cx:320,cy:240,width:640,height:480,camera_to_world:pose};
const camera={camera_id:'CAM_1F_AUDITORIUM_FRONT',camera_ref:'camera:abc',authority:'SOURCE_CAMERA_CALIBRATION',coverage_status:'UNKNOWN',calibration};
const near=(a,b,t=1e-6)=>assert.ok(Math.abs(a-b)<t,`${a} != ${b}`);

test('frustum apex, viewing direction and dimensions follow the calibrated pose',()=>{
  const f=cameraFrustumOverlay(camera,4);
  assert.deepEqual(f.apex,[10,-4,8]);assert.deepEqual(f.forward.map(v=>Math.abs(v)<1e-12?0:v),[1,0,0]);
  assert.equal(f.role,'FRONT');assert.equal(f.label,FRUSTUM_LABEL);
  // Half extents at depth d are d*w/2/fx and d*h/2/fy; all corners lie on the plane x = apex.x + d.
  for(const c of f.corners)near(c[0],14);
  near(Math.hypot(f.corners[0][1]-f.corners[1][1],f.corners[0][2]-f.corners[1][2]),4*640/500);
  near(Math.hypot(f.corners[1][1]-f.corners[2][1],f.corners[1][2]-f.corners[2][2]),4*480/500);
  // Image top-left (u=0,v=0) is world +Z up (local +Y) and local -X = world -Y.
  assert.ok(f.corners[0][2]>f.centre[2]&&f.corners[0][1]<f.centre[1]);
  assert.equal(cameraRole('CAM_1F_AUDITORIUM_REAR'),'REAR');assert.equal(cameraRole('CAM_A'),null);
});
test('unsupported or non-rigid calibrations produce no frustum and no projection',()=>{
  assert.equal(cameraFrustumOverlay({...camera,calibration:{...calibration,convention:'OPENCV'}},4),null);
  assert.equal(cameraFrustumOverlay({...camera,calibration:{...calibration,pixel_origin:'CENTER'}},4),null);
  assert.equal(cameraFrustumOverlay({camera_id:'x'},4),null);
  const skew={...calibration,camera_to_world:[[2,0,-1,0],[1,0,0,0],[0,1,0,0],[0,0,0,1]]};
  assert.equal(projectWorldPoint(skew,[1,0,0]),null);
});
test('world-to-image projection uses top-left continuous pixels with image Y downward',()=>{
  const centre=projectWorldPoint(calibration,[20,-4,8]);near(centre.u,320);near(centre.v,240);near(centre.depth,10);
  const above=projectWorldPoint(calibration,[20,-4,9]);assert.ok(above.v<240,'higher world Z lands higher in the image (smaller v)');near(above.v,240-500*1/10);
  const right=projectWorldPoint(calibration,[20,-3,8]);assert.ok(right.u>320);near(right.u,320+500*1/10);
  // Roundtrip against the existing back-projection of the same pixel.
  const back=cameraFrustumOverlay(camera,10).corners[2],p=projectWorldPoint(calibration,back);near(p.u,640);near(p.v,480);
});
test('behind-camera points are hidden and segments are clipped at the near plane and image border',()=>{
  assert.equal(projectWorldPoint(calibration,[5,-4,8]),null);
  assert.equal(projectSegmentToImage(calibration,[2,-4,8],[5,-4,8]),null,'fully behind');
  const straddle=projectSegmentToImage(calibration,[5,-4,8.5],[20,-4,8.5]);
  assert.ok(straddle,'the in-front part survives');for(const [u,v] of [straddle.from,straddle.to]){assert.ok(u>=0&&u<=640&&v>=0&&v<=480);}
  const crossing=projectSegmentToImage(calibration,[20,-4,8],[20,-4+40,8]);
  near(crossing.from[0],320);near(crossing.to[0],640);near(crossing.to[1],240);
  assert.equal(projectSegmentToImage(calibration,[20,-100,8],[20,-90,8]),null,'wholly outside the image');
});
test('source annotations need a PORTAL_* source id; others are dropped, never invented',()=>{
  const prim=(label,extra={})=>({kind:'SOURCE_ANNOTATION',label,units:'METRES',is_aperture:false,is_collider:false,geometry_ref:'review-geometry:'+'a'.repeat(24),
    vertices:[[20,-5,7],[20,-3,7],[20,-3,9],[20,-5,9]],triangles:[[0,1,2],[0,2,3]],...extra});
  const found=sourceAnnotations({geometry_primitives:[prim('PORTAL_1F_OFFICE'),prim('原標註範圍'),prim('PORTAL_1F_X',{is_aperture:true}),prim('PORTAL_1F_Y',{kind:'SOURCE_TRIANGLES'}),prim('PORTAL_1F_AUDITORIUM_OFFICE')]});
  assert.deepEqual(found.map(a=>a.source_id),['PORTAL_1F_OFFICE','PORTAL_1F_AUDITORIUM_OFFICE']);
  assert.equal(found[0].label,ANNOTATION_LABEL);assert.equal(found[0].edges.length,4,'quad outline only; the diagonal is interior');
  assert.deepEqual(sourceAnnotations(null),[]);assert.deepEqual(sourceAnnotations({geometry_primitives:[prim('PORTAL_1F_OFFICE',{triangles:[[0,1,9]]})]}),[]);
  assert.equal(boundaryEdges([[0,0,0],[1,0,0],[1,1,0]],[[0,1,2]]).length,3);
});
test('overlay SVG is tile-size independent, dashed, labelled unverified, and unsupported cameras stay explicit',()=>{
  const [annotation]=sourceAnnotations({geometry_primitives:[{kind:'SOURCE_ANNOTATION',label:'PORTAL_1F_OFFICE',units:'METRES',is_aperture:false,is_collider:false,
    vertices:[[20,-5,7],[20,-3,7],[20,-3,9]],triangles:[[0,1,2]]}]});
  const model=cameraOverlayModel(camera,[annotation]),svg=cameraOverlaySVG(model);
  assert.equal(model.supported,true);assert.ok(model.segments.length>0);
  // Pixel coordinates live in a fixed viewBox that the browser letterboxes exactly like object-fit: contain,
  // so any responsive tile size or seek keeps the geometry on the same image pixels.
  assert.match(svg,/viewBox="0 0 640 480" preserveAspectRatio="xMidYMid meet"/);assert.match(svg,/stroke-dasharray/);
  assert.ok(svg.includes('PORTAL_1F_OFFICE · SOURCE ANNOTATION · UNVERIFIED'));assert.equal(svg,cameraOverlaySVG(cameraOverlayModel(camera,[annotation])));
  const bad=cameraOverlayModel({camera_id:'CAM_X',calibration:{...calibration,convention:'OPENCV'}},[annotation]);
  assert.equal(bad.supported,false);assert.equal(cameraOverlaySVG(bad),'');
  assert.equal(cameraOverlayModel(camera,[]).segments.length,0);
});
test('overlay toggle is a presentation-only action that never re-renders the workspace',()=>{
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8');
  const branch=source.slice(source.indexOf("action==='toggle-geometry-overlay'"),source.indexOf("action==='toggle-graph-labels'"));
  assert.ok(branch.length>40);assert.doesNotMatch(branch,/render\(\)|stopPlayback|fetchTimeline|reset\(\)|viewPose/);
  assert.match(branch,/setGeometryOverlayVisible/);assert.match(source,/data-action="toggle-geometry-overlay" aria-pressed/);
});

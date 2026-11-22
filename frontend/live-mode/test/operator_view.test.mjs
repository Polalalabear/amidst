// F2 (#656) user report: A could see people through walls. Virtual-camera (detector) walls must always be opaque;
// operator x-ray is an explicit toggle (default off) and the coverage overlay never reaches a detector frame.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from 'three';
import {makeOperatorView, XRAY_NOTICE} from '../src/operator.mjs';
import {buildCoverageOverlay, OVERLAY_NAME} from '../src/coverage_overlay.mjs';
import {coverageOf} from '../src/coverage.mjs';
import {cameraColors, drawCoverageMap, mapTransform} from '../src/coverage_map.mjs';

const GEOM = JSON.parse(fs.readFileSync(new URL('../../../docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json', import.meta.url), 'utf8'));

function scene() {
  const s = new THREE.Scene(), shared = new THREE.MeshBasicMaterial(), screen = new THREE.MeshBasicMaterial();
  const wall = new THREE.Mesh(new THREE.BoxGeometry(), shared), floor = new THREE.Mesh(new THREE.PlaneGeometry(), shared), ceiling = new THREE.Group();
  wall.name = 'WALL_JOINED_SHELL_LIVE'; ceiling.name = 'CEILING_STATIC_LIVE'; s.add(wall, floor, ceiling);
  return {world: {scene: s, wallMats: [screen]}, wall, floor, ceiling, screen};
}
// What a virtual camera would render right now: every wall material opaque, ceiling as authored, no overlay.
function cameraState(world, wall, screen, ceiling) {
  const overlay = world.scene.getObjectByName(OVERLAY_NAME);
  return {opaque: [wall.material, screen].every(m => m.opacity === 1 && !m.transparent && m.depthWrite), ceiling: ceiling.visible, overlay: !!overlay?.visible};
}
const coverage = coverageOf(GEOM), overlay = () => buildCoverageOverlay(coverage, cameraColors(coverage.cameras.map(c => c.camera_id)));

test('default operator view keeps walls opaque (no x-ray) and shows the overlay only inside the operator render', () => {
  const {world, wall, floor, ceiling, screen} = scene(), draw = makeOperatorView(world, {overlay: overlay()});
  assert.equal(draw.xray, false);
  draw(() => {
    assert.equal(wall.material.opacity, 1); assert.equal(screen.opacity, 1); assert.equal(floor.material.opacity, 1);
    assert.equal(ceiling.visible, true); assert.equal(world.scene.getObjectByName(OVERLAY_NAME).visible, true);
  });
  assert.deepEqual(cameraState(world, wall, screen, ceiling), {opaque: true, ceiling: true, overlay: false});
});

test('x-ray toggle: see-through only inside the operator render, restored for virtual cameras, also on throw', () => {
  const {world, wall, ceiling, screen} = scene(), draw = makeOperatorView(world, {overlay: overlay()});
  assert.equal(draw.setXray(true), true);
  draw(() => { assert.equal(wall.material.opacity, .18); assert.equal(screen.transparent, true); assert.equal(ceiling.visible, false); });
  assert.deepEqual(cameraState(world, wall, screen, ceiling), {opaque: true, ceiling: true, overlay: false});
  assert.throws(() => draw(() => { throw new Error('render failed'); }), /render failed/);
  assert.deepEqual(cameraState(world, wall, screen, ceiling), {opaque: true, ceiling: true, overlay: false});
  // a virtual camera shoot between operator frames (as captureTick does) always sees the restored state
  for (let i = 0; i < 20; i++) {
    draw(() => {});
    assert.deepEqual(cameraState(world, wall, screen, ceiling), {opaque: true, ceiling: true, overlay: false});
  }
  assert.equal(draw.setXray(false), false);
  draw(() => assert.equal(wall.material.opacity, 1));
});

test('operator loop: virtual-camera shoots never run inside the operator render callback; notice text present', () => {
  const src = fs.readFileSync(new URL('../src/operator.mjs', import.meta.url), 'utf8');
  const calls = [...src.matchAll(/drawOperator\(([^;]*)\);/g)].map(m => m[1]);
  assert.deepEqual(calls, ['() => renderer.render(world.scene, vcam)']);
  assert.match(src, /xray: false/);
  assert.equal(XRAY_NOTICE, '操作者透視視角，鏡頭看不到');
  assert.match(src, /id="xray-notice" role="status" hidden/);
  // capture renders the shared scene synchronously at the start of shoot(), outside any drawOperator call
  assert.match(fs.readFileSync(new URL('../src/capture.mjs', import.meta.url), 'utf8'), /async shoot\(camId\) \{\s*const c = cams\[camId\];\s*renderer\.setRenderTarget\(rt\);\s*renderer\.render\(world\.scene, c\.camera\);/);
});

test('overlay has an icon and FOV polygon per camera, blind cells, hidden by default', () => {
  const g = overlay();
  assert.equal(g.visible, false);
  for (const c of coverage.cameras) { assert.ok(g.getObjectByName('ICON_' + c.camera_id)); if (c.polygon.length >= 3) assert.ok(g.getObjectByName('FOV_' + c.camera_id)); }
  assert.equal(g.getObjectByName('BLIND_CELLS').count, coverage.blind.length);
  // three z = -world y: an icon sits at the camera's world position
  const c = coverage.cameras[0], icon = g.getObjectByName('ICON_' + c.camera_id);
  assert.deepEqual([icon.position.x, icon.position.z].map(v => +v.toFixed(6)), [c.pose.pos[0], -c.pose.pos[1]].map(v => +v.toFixed(6)));
});

test('minimap draws every camera, walls, blind cells and the player inside the canvas', () => {
  const ops = [], ctx = new Proxy({}, {get: (_, k) => typeof k === 'string' && !['fillStyle', 'strokeStyle', 'lineWidth', 'globalAlpha', 'font'].includes(k) ? (...a) => ops.push([k, a]) : undefined, set: () => true});
  const w = 320, h = 320, walls = GEOM.clearance_segments.map(s => [s.a[0], s.a[1], s.b[0], s.b[1]]);
  drawCoverageMap(ctx, {geometry: GEOM, walls, coverage, colors: cameraColors(coverage.cameras.map(c => c.camera_id)), player: {x: 0, y: 0}, w, h});
  const labels = ops.filter(([k]) => k === 'fillText').map(([, a]) => a[0]);
  assert.deepEqual(labels.sort(), coverage.cameras.map(c => c.camera_id.replace('CAM_', '')).sort());
  assert.ok(ops.filter(([k]) => k === 'arc').length === 1);
  const {map} = mapTransform(GEOM.floors, w, h);
  for (const f of GEOM.floors) for (const [x, y] of [[f.x_m[0], f.y_m[0]], [f.x_m[1], f.y_m[1]]]) { const [a, b] = map(x, y); assert.ok(a >= 0 && a <= w && b >= 0 && b <= h); }
});

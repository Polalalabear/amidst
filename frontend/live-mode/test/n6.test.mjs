// P2-2 integration contract for N6 (#539) in live mode. Asset-dependent tests read the LOCAL N6 folder
// ($AMIDST_ARTIFACTS/data/live-assets-20261115, or $AMIDST_LIVE_ASSETS) and skip when it is absent (CI).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { softenBakedCeiling } from '../src/n6-ceiling.mjs';
import { makeLoader, makeCharacter, buildN6Cameras, rowMajor, blenderToGltf, BLENDER_TO_GLTF, NOMINAL } from '../src/n6.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(here, '../../..');
const ASSETS = process.env.AMIDST_LIVE_ASSETS
  || path.join(process.env.AMIDST_ARTIFACTS || path.join(os.homedir(), 'amidst', 'local'), 'data', 'live-assets-20261115');
const have = (f) => fs.existsSync(path.join(ASSETS, f));
const skipN6 = have('character.glb') && have('cameras.three.json') ? false : 'N6 LOCAL assets not found';
const GEOM = JSON.parse(fs.readFileSync(path.join(REPO, 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'), 'utf8'));
const loadGlb = async (f) => { const b = fs.readFileSync(path.join(ASSETS, f)); return makeLoader().parseAsync(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength), ''); };
const camJson = () => JSON.parse(fs.readFileSync(path.join(ASSETS, 'cameras.three.json'), 'utf8'));
const maxAbs = (a, b) => a.reduce((m, v, i) => Math.max(m, Math.abs(v - b[i])), 0);

// ---- coordinates (no assets needed)
test('coordinates: Blender (x,y,z) -> (x,z,-y); +X stays forward', () => {
  assert.deepEqual(blenderToGltf(3, 4, 1.7), [3, 1.7, -4]);
  const R = rowMajor(BLENDER_TO_GLTF);
  const v = new THREE.Vector3(3, 4, 1.7).applyMatrix4(R);
  assert.deepEqual([v.x, v.y, v.z].map((n) => +n.toFixed(9)), [3, 1.7, -4]);
  // heading theta (CCW from +X in Blender) == rotation.y = theta in glTF: local +X lands on (cos,0,-sin)
  for (const th of [0, 0.7, Math.PI / 2, 2.4, -1.1]) {
    const o = new THREE.Object3D(); o.rotation.set(0, th, 0); o.updateMatrixWorld(true);
    const f = new THREE.Vector3(1, 0, 0).transformDirection(o.matrixWorld);
    assert.ok(Math.abs(f.x - Math.cos(th)) < 1e-9 && Math.abs(f.z + Math.sin(th)) < 1e-9);
  }
});

test('coordinates: character handle puts (x,y) at (x,0,-y), facing +X at heading 0', { skip: skipN6 }, async () => {
  const ch = makeCharacter(await loadGlb('character.glb'));
  ch.setPose(5, 2, 0); ch.object.updateMatrixWorld(true);
  assert.deepEqual(ch.object.position.toArray(), [5, 0, -2]);
  // forward = +X: shoes' toes extend toward +X (shoe mesh bbox centre is ahead of its shin bone)
  ch.setPose(0, 0, 0); ch.object.updateMatrixWorld(true);
  const box = new THREE.Box3(); const bones = {};
  ch.object.traverse((o) => { if (o.isBone) bones[o.name] = o; });
  const shoe = []; ch.object.traverse((o) => { if (o.isMesh && /SHOE/.test(o.name)) shoe.push(o); });
  ch.object.updateMatrixWorld(true);
  for (const s of shoe) { s.geometry.computeBoundingBox(); const b = s.geometry.boundingBox.clone(); s.skeleton || 0; box.union(b); }
  const ankle = new THREE.Vector3().setFromMatrixPosition(bones.L_foot.matrixWorld);
  const bb = new THREE.Box3(); shoe.forEach((s) => bb.union(s.geometry.boundingBox));
  assert.ok(bb.max.x - ankle.x > ankle.x - bb.min.x, 'toe side (+X) longer than heel side');
});

// ---- cameras
test('cameras: row-major matrices, three Matrix4.set vs fromArray differ, inverse + projection agree', { skip: skipN6 }, () => {
  const cj = camJson();
  assert.equal(cj.cameras.length, 8);
  const scene = new THREE.Scene();
  const cams = buildN6Cameras(cj, scene, 960, 540);
  for (const c of cj.cameras) {
    const cam = cams[c.camera_id].camera;
    const M = rowMajor(c.camera_to_world);
    assert.ok(maxAbs(cam.matrixWorld.elements, M.elements) === 0);
    // translation sits in column 3 of the row-major rows, i.e. elements[12..14] after set()
    assert.deepEqual([cam.matrixWorld.elements[12], cam.matrixWorld.elements[13], cam.matrixWorld.elements[14]].map((n) => +n.toFixed(6)),
      [c.camera_to_world[0][3], c.camera_to_world[1][3], c.camera_to_world[2][3]].map((n) => +n.toFixed(6)));
    // the wrong reading (fromArray on row-major rows) would transpose -> translation lands in the bottom row
    const wrong = new THREE.Matrix4().fromArray(c.camera_to_world.flat());
    assert.ok(maxAbs(wrong.elements, M.elements) > 1, 'fromArray would have been wrong');
    // world_to_camera is the inverse of camera_to_world
    assert.ok(maxAbs(cam.matrixWorldInverse.elements, rowMajor(c.world_to_camera).elements) < 1e-5);
    // projection matrix: three's projection from fy/cy at 960x540 equals the JSON one
    const P = rowMajor(c.projection_matrix);
    assert.ok(maxAbs(cam.projectionMatrix.elements, P.elements) < 1e-6, `${c.camera_id} projection`);
    // camera looks along local -Z, +Y up
    const look = new THREE.Vector3(0, 0, -1).transformDirection(cam.matrixWorld);
    const up = new THREE.Vector3(0, 1, 0).transformDirection(cam.matrixWorld);
    assert.ok(up.y > 0.5 && Math.abs(look.length() - 1) < 1e-9);
  }
});

test('cameras: all 8 intrinsics/extrinsics match the source catalog (R * Blender camera_to_world)', { skip: skipN6 }, () => {
  const cj = camJson();
  const R = rowMajor(BLENDER_TO_GLTF);
  const byId = Object.fromEntries(cj.cameras.map((c) => [c.camera_id, c]));
  assert.equal(GEOM.cameras.length, 8);
  for (const g of GEOM.cameras) {
    const c = byId[g.camera_id];
    assert.ok(c, g.camera_id);
    for (const k of ['fx', 'fy', 'cx', 'cy', 'width', 'height']) assert.ok(Math.abs(c[k] - g[k]) < 1e-6, `${g.camera_id} ${k}`);
    const Mb = rowMajor(g.camera_to_world);
    const expect = R.clone().multiply(Mb); // glTF = R * Blender
    assert.ok(maxAbs(rowMajor(c.camera_to_world).elements, expect.elements) < 1e-5, `${g.camera_id} extrinsics`);
  }
});

test('cameras: a Blender floor point projects to the same pixel through catalog and N6 cameras', { skip: skipN6 }, () => {
  const cj = camJson();
  const scene = new THREE.Scene();
  const cams = buildN6Cameras(cj, scene, 960, 540);
  let n = 0;
  for (const g of GEOM.cameras) {
    const Mb = new THREE.Matrix4().set(...g.camera_to_world.flat());
    const look = new THREE.Vector3(0, 0, -1).transformDirection(Mb);
    const eye = new THREE.Vector3().setFromMatrixPosition(Mb);
    const p = eye.clone().addScaledVector(look, 6); // 6 m ahead (Blender coordinates)
    const inv = Mb.clone().invert();
    const q = p.clone().applyMatrix4(inv); // catalog pinhole
    const u0 = g.fx * q.x / -q.z + g.cx, v0 = -g.fy * q.y / -q.z + g.cy;
    const [gx, gy, gz] = blenderToGltf(p.x, p.y, p.z);
    const ndc = new THREE.Vector3(gx, gy, gz).project(cams[g.camera_id].camera);
    const u1 = (ndc.x * 0.5 + 0.5) * 960, v1 = (-ndc.y * 0.5 + 0.5) * 540;
    assert.ok(Math.hypot(u0 - u1, v0 - v1) < 0.01, `${g.camera_id}: (${u0},${v0}) vs (${u1},${v1})`); n++;
  }
  assert.equal(n, 8);
});

// ---- variants
test('variants: KHR_materials_variants T/A/B/C switch materials, independently per person', { skip: skipN6 }, async () => {
  const gltf = await loadGlb('character.glb');
  assert.deepEqual(gltf.userData.variants, ['T', 'A', 'B', 'C']);
  const a = makeCharacter(gltf, 'T'), b = makeCharacter(gltf, 'T');
  const top = (ch) => { let m; ch.object.traverse((o) => { if (o.isMesh && o.name === 'N6_TORSO') m = o.material; }); return m; };
  const pants = (ch) => { let m; ch.object.traverse((o) => { if (o.isMesh && o.name === 'N6_L_THIGH') m = o.material; }); return m; };
  const rgb = (m) => m.color.getHex();
  assert.ok(top(a).isMeshStandardMaterial && pants(a).isMeshStandardMaterial, 'real materials after clone');
  const seen = {};
  for (const v of ['T', 'A', 'B', 'C']) { a.setVariant(v); seen[v] = { top: rgb(top(a)), pants: rgb(pants(a)), name: pants(a).name }; assert.equal(a.variant, v); }
  // spec (N6 doc): A = same red top, light-grey trousers; B = other colours, C = other colours
  assert.equal(seen.A.top, seen.T.top);
  assert.notEqual(seen.A.pants, seen.T.pants);
  for (const v of ['B', 'C']) assert.ok(JSON.stringify(seen[v]) !== JSON.stringify(seen.T), `${v} differs from T`);
  assert.equal(new Set(Object.values(seen).map((s) => s.name)).size, 4, 'four distinct pants materials');
  // independence: switching a does not touch b
  a.setVariant('C'); b.setVariant('A');
  assert.equal(pants(a).name.startsWith('C_'), true); assert.equal(pants(b).name.startsWith('A_'), true);
  assert.throws(() => a.setVariant('Z'));
});

// ---- locomotion
test('locomotion: action.timeScale = actualSpeed / nominalSpeed (walk 1.2, run 2.5)', { skip: skipN6 }, async () => {
  const gltf = await loadGlb('character.glb');
  assert.deepEqual(NOMINAL, { walk: 1.2, run: 2.5 });
  const meta = JSON.parse(fs.readFileSync(path.join(ASSETS, 'MANIFEST.json'), 'utf8')) && true;
  assert.ok(meta);
  const ch = makeCharacter(gltf);
  const cases = [[1.2, undefined, 'walk', 1], [0.6, undefined, 'walk', 0.5], [1.5, false, 'walk', 1.25], [2.5, undefined, 'run', 1], [1.25, true, 'run', 0.5], [3.0, true, 'run', 1.2], [0, undefined, 'idle', 1]];
  for (const [v, running, clip, ts] of cases) {
    const r = ch.setSpeed(v, running);
    assert.equal(r.clip, clip); assert.ok(Math.abs(r.timeScale - ts) < 1e-9, `${v} m/s`);
    assert.ok(Math.abs(ch.actions[clip].timeScale - ts) < 1e-9);
    assert.equal(ch.current, ch.actions[clip]);
  }
  // timeScale really scales clip advance: after dt the walk action time advanced dt*timeScale
  const c2 = makeCharacter(gltf); c2.setSpeed(0.6, false); const act = c2.actions.walk; act.time = 0;
  c2.update(0.2); assert.ok(Math.abs(act.time - 0.2 * 0.5) < 1e-6);
});

function footSlip(gltf, speed, running, forceScale) {
  const ch = makeCharacter(gltf);
  const feet = []; ch.object.traverse((o) => { if (o.isBone && /_foot$/.test(o.name)) feet.push(o); });
  const { clip } = ch.setSpeed(speed, running);
  // skip the 0.15 s crossfade: restart the action cleanly
  ch.actions[clip].reset().play(); ch.actions[clip].timeScale = forceScale ?? speed / NOMINAL[clip];
  ch.mixer.update(0); const dt = 1 / 240, N = Math.round(2.5 / dt);
  let x = 0, prev = null; const slips = [];
  for (let i = 0; i < N; i++) {
    x += speed * dt; ch.object.position.set(x, 0, 0); ch.mixer.update(dt); ch.object.updateMatrixWorld(true);
    const p = feet.map((f) => new THREE.Vector3().setFromMatrixPosition(f.matrixWorld));
    if (prev) {
      const k = p[0].y < p[1].y ? 0 : 1; // lower foot = stance foot
      const lo = Math.min(p[0].y, p[1].y);
      if (lo < 0.12 + 0.0) slips.push(Math.abs((p[k].x - prev[k].x) / dt));
    }
    prev = p;
  }
  slips.sort((a, b) => a - b);
  return { median: slips[Math.floor(slips.length / 2)], n: slips.length };
}
test('locomotion: stance-foot world speed ~ 0 when timeScale = speed/nominal (no sliding), at 0.6/1.2/2.0/2.5 m/s', { skip: skipN6 }, async () => {
  const gltf = await loadGlb('character.glb');
  const rows = [];
  for (const [v, run] of [[0.6, false], [1.2, false], [2.0, true], [2.5, true]]) {
    const r = footSlip(gltf, v, run); rows.push({ speed: v, median_stance_foot_world_speed_mps: +r.median.toFixed(4), samples: r.n });
    assert.ok(r.n > 50, 'has stance samples');
    assert.ok(r.median < 0.15 * v + 0.05, `${v} m/s slip ${r.median}`);
  }
  console.log('FOOT_SLIP ' + JSON.stringify(rows));
  // control: a mismatched timeScale (1.0 at 2.5 m/s walk) does slide
  const bad = footSlip(gltf, 2.5, false, 1.0); // walk clip (1.2 m/s) forced at 2.5 m/s: feet slide
  console.log('FOOT_SLIP_CONTROL ' + JSON.stringify({ speed: 2.5, clip: 'walk', timeScale: 1.0, median_mps: +bad.median.toFixed(3) }));
  assert.ok(bad.median > 0.5, 'control: a wrong timeScale must slide');
});

test('scene.glb: baked scene carries unlit material, n6Collider nodes and the lighting extras contract', { skip: have('scene.glb') ? false : 'no scene.glb' }, () => {
  const b = fs.readFileSync(path.join(ASSETS, 'scene.glb'));
  const len = b.readUInt32LE(12); const j = JSON.parse(b.subarray(20, 20 + len).toString('utf8'));
  assert.ok(j.extensionsUsed.includes('KHR_materials_unlit'));
  assert.equal(j.nodes.length, 15);
  assert.ok(j.nodes.some((n) => n.extras?.n6Collider === true && n.name === 'CEILING_STATIC_LIVE'));
  assert.ok(j.asset.extras.n6Lighting.linearIrradiance);
});

test('ceiling treatment isolates the shared baked material from walls and floor', () => {
  const map = new THREE.Texture();
  const shared = new THREE.MeshBasicMaterial({map, side: THREE.DoubleSide});
  const scene = new THREE.Group();
  const ceiling = new THREE.Mesh(undefined, shared);
  ceiling.name = 'CEILING_STATIC_LIVE';
  const wall = new THREE.Mesh(undefined, shared);
  scene.add(ceiling, wall);

  softenBakedCeiling(scene);

  assert.notEqual(ceiling.material, shared);
  assert.equal(ceiling.material.map, map);
  assert.equal(ceiling.material.side, THREE.DoubleSide);
  assert.equal(wall.material, shared);
  assert.equal(ceiling.visible, true);
});

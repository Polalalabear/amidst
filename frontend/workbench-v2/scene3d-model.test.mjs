import test from 'node:test';
import assert from 'node:assert/strict';
import { buildScene3dModel, buildCameraModels, clipUncertaintyFan, readEstimate, readTransitions, cameraGroundXy } from './scene3d-model.mjs';

const mat = (x, y, z) => [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]];
const asset = {
  source_catalog_sha256: 'abc',
  cameras: [
    { camera_id: 'CAM_A', width: 960, height: 540, fy: 625, cx: 480, cy: 270, camera_to_world: mat(-10, 2.5, -4) },
    { camera_id: 'CAM_B', width: 960, height: 540, fy: 625, cx: 480, cy: 270, camera_to_world: mat(0, 2.5, 6) },
  ],
};
const T = [
  { from_kind: 'ON_CAMERA', from_camera: 'CAM_A', to_kind: 'GAP', to_camera: null, switch_at_us: 8e6 },
  { from_kind: 'GAP', from_camera: null, to_kind: 'ON_CAMERA', to_camera: 'CAM_B', switch_at_us: 13e6 },
];
const view = (kind, active, t, last = null) => ({ currentTUs: t, singleView: { segmentKind: kind, activeCameraId: active, lastObservedCameraId: last, transitions: T } });

test('camera ground xy converts three (x,z) to Blender (x,-z)', () => {
  assert.deepEqual(cameraGroundXy(asset.cameras[0]), [-10, 4]);
  const [a, b] = buildCameraModels(asset.cameras, { activeCameraId: 'CAM_B' });
  assert.equal(a.isActive, false); assert.equal(b.isActive, true);
  assert.ok(Math.abs(a.fovYRad - 2 * Math.atan(270 / 625)) < 1e-5); assert.equal(a.aspect, 1.777778);
});

test('no estimate: UNKNOWN, no human/trail, legend says so; active frustum only', () => {
  const m = buildScene3dModel({ view: view('ON_CAMERA', 'CAM_A', 5e6), cameraAsset: asset });
  assert.equal(m.estimate.status, 'UNKNOWN'); assert.equal(m.estimate.xy, null); assert.deepEqual(m.estimate.trail, []);
  assert.deepEqual(m.estimate.uncertaintyFan, []);
  assert.ok(m.legend.some(l => l.includes('估計位置 UNKNOWN')));
  assert.equal(m.cameras.filter(c => c.isActive).length, 1); assert.equal(m.switchMarker, null);
});

test('blind interval, last observed camera highlight and switch marker', () => {
  const gap = buildScene3dModel({ view: view('GAP', null, 10e6, 'CAM_A'), cameraAsset: asset });
  assert.equal(gap.cameras.find(c => c.id === 'CAM_A').isGapLast, true);
  assert.deepEqual(gap.blindIntervals, [{ startUs: 8e6, endUs: 13e6, lastCamera: 'CAM_A' }]);
  const sw = buildScene3dModel({ view: view('ON_CAMERA', 'CAM_B', 14e6), cameraAsset: asset });
  assert.deepEqual(sw.switchMarker, { tUs: 13e6, from: null, to: 'CAM_B', groundXy: [0, -6] });
  assert.equal(readTransitions(T, 7e6).switches.length, 0);
});

test('estimate present: trail cut at current time, circle without walls says UNKNOWN walls', () => {
  const est = { est_xy: [1, 2], uncertainty_m: 1.5, track: [{ t_us: 1e6, est_xy: [0, 0] }, { t_us: 20e6, est_xy: [9, 9] }] };
  const m = buildScene3dModel({ view: view('ON_CAMERA', 'CAM_A', 5e6), cameraAsset: asset, estimate: est });
  assert.equal(m.estimate.status, 'INFERRED'); assert.deepEqual(m.estimate.trail, [[0, 0]]);
  assert.equal(m.estimate.clipped, false); assert.ok(m.legend.some(l => l.includes('未考慮牆')));
});

test('uncertainty fan is clipped by wall segments', () => {
  const fan = clipUncertaintyFan([0, 0], 2, [[[1, -5], [1, 5]]], 8);
  assert.equal(fan.length, 8);
  assert.ok(fan.every(([x]) => x <= 1.0001));
  assert.deepEqual(fan[0], [1, 0]);
  const open = clipUncertaintyFan([0, 0], 2, [], 4);
  assert.deepEqual(open[0], [2, 0]);
  const m = buildScene3dModel({ view: view('GAP', null, 10e6, 'CAM_A'), cameraAsset: asset, estimate: { est_xy: [0, 0], uncertainty_m: 2, wall_segments_xy: [[[1, -5], [1, 5]]] } });
  assert.equal(m.estimate.clipped, true); assert.equal(m.estimate.uncertaintyFan.length, 48);
});

test('missing/invalid uncertainty stays UNKNOWN, bad est_xy stays UNKNOWN', () => {
  assert.equal(readEstimate({ est_xy: [1, 2] }).uncertaintyM, 'UNKNOWN');
  assert.equal(readEstimate({ est_xy: ['a', 2] }).status, 'UNKNOWN');
  assert.equal(readEstimate(null).reason, 'ESTIMATE_SOURCE_MISSING');
});

test('isolation: GT-like keys reject the estimate; output never carries GT field names', () => {
  const GT = ['ground', '_truth'].join(''), REND = ['renderer', '_trajec', 'tory'].join(''), VIS = ['visib', 'ility'].join(''), DEP = ['dep', 'th'].join('');
  for (const key of [GT, REND, VIS, DEP, ['g', 't_position'].join('')]) {
    const e = readEstimate({ est_xy: [1, 2], uncertainty_m: 1, [key]: 1 });
    assert.equal(e.status, 'UNKNOWN', key); assert.equal(e.reason, 'FORBIDDEN_KEYS_REJECTED', key);
  }
  const m = buildScene3dModel({ view: view('ON_CAMERA', 'CAM_A', 5e6), cameraAsset: asset, estimate: { est_xy: [1, 2], uncertainty_m: 1, [GT]: [3, 3] } });
  const text = JSON.stringify(m).toLowerCase();
  for (const word of ['ground_truth', 'renderer_trajectory', 'visibility', 'depth', 'gt_position']) assert.ok(!text.includes(word), word);
  assert.equal(m.estimate.xy, null);
});

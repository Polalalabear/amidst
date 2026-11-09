import test from 'node:test';
import assert from 'node:assert/strict';
import {classGroups, featuredClasses, SCENE_FEATURED_CLASSES} from './ui-model.mjs';
import {frameTUs} from './ui-shell.mjs';

test('D147-1 featured scene classes: declared classes on top in order, everything else under 其他', () => {
  assert.deepEqual(featuredClasses('ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1'), ['person', 'car']);
  assert.deepEqual(featuredClasses('ENGINEERING_DYNAMIC_RUN_20261025'), ['person']);
  assert.deepEqual(featuredClasses('ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1'), ['person']);
  assert.equal(featuredClasses('r005-static-reviewed-v2'), null);
  assert.ok(Object.isFrozen(SCENE_FEATURED_CLASSES));
  const classes = ['person', 'car', 'clock', 'refrigerator', 'bench'];
  const counts = [{class_label: 'clock', detection_count: 236, camera_count: 1}, {class_label: 'person', detection_count: 125, camera_count: 3}, {class_label: 'refrigerator', detection_count: 179, camera_count: 1}];
  const g = classGroups(classes, counts, undefined, ['person', 'car']);
  assert.equal(g.grouped, true); assert.equal(g.featured, true);
  assert.deepEqual(g.detected.map(d => [d.label, d.cameraCount]), [['person', 3], ['car', 0]]);   // car never detected: 0 cameras, still listed
  assert.deepEqual(g.others.map(o => o.label), ['clock', 'refrigerator', 'bench']);               // detected non-scene classes first (by count), then the rest
  const t = classGroups(classes, counts, c => c === 'person', ['person', 'car']);
  assert.deepEqual(t.detected.map(d => d.supported), [true, false]);
  assert.equal(classGroups(classes, counts, undefined, ['nope']).featured, undefined);             // unknown featured labels fall back to D139-1
  assert.equal(classGroups(classes, null, undefined, ['person']).detected[0].cameraCount, null);  // no counts at all: no fake 0
});

test('D147-3 frameTUs snaps to the source frame grid and leaves unusable input alone', () => {
  const run = {sampling: {per_camera: [{camera_id: 'CAM_W1', index_grid_origin_frame: 0, source_frame_interval_us: 200000}]}};
  assert.equal(frameTUs(run, 'CAM_W1', 0), 0);
  assert.equal(frameTUs(run, 'CAM_W1', 199999), 0);
  assert.equal(frameTUs(run, 'CAM_W1', 200000), 200000);
  assert.equal(frameTUs(run, 'CAM_W1', 14810123), 14800000);
  assert.equal(frameTUs(run, 'CAM_OTHER', 14810123), 14800000);   // falls back to the first camera's grid
  assert.equal(frameTUs({}, 'CAM_W1', 123), 123);
  assert.equal(frameTUs(run, 'CAM_W1', 1.5), 1.5);
  const shifted = {sampling: {per_camera: [{camera_id: 'C', index_grid_origin_frame: 2, source_frame_interval_us: 100}]}};
  assert.equal(frameTUs(shifted, 'C', 350), 300); assert.equal(frameTUs(shifted, 'C', 150), 150);
});

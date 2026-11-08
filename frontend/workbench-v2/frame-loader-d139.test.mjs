import test from 'node:test';
import assert from 'node:assert/strict';
// ui-shell.mjs only touches the DOM inside mountUi, so its pure helpers can be imported directly.
import {createFrameLoader} from './ui-shell.mjs';
import {classGroups, CAMERA_COUNT_NOTE} from './ui-model.mjs';

const tick = () => new Promise(r => setTimeout(r, 0));

test('frame loader: one request in flight, always followed by the newest wanted frame; slow replies are still shown', async () => {
  const calls = [], shown = [], gates = [];
  const loader = createFrameLoader(w => new Promise(res => { calls.push(w.t); gates.push(() => res('url-' + w.t)); }), (url, w) => shown.push([w.t, url]));
  loader.request({t: 1}); loader.request({t: 2}); loader.request({t: 3});   // playhead moves on while the first reply is pending
  await tick(); assert.deepEqual(calls, [1]);                                  // not three parallel requests
  gates[0](); await tick(); await tick();
  assert.deepEqual(shown, [[1, 'url-1']]);                                     // the slow reply is displayed, not discarded
  assert.deepEqual(calls, [1, 3]);                                             // next request is the newest wanted frame; 2 was skipped
  gates[1](); await tick(); await tick();
  assert.deepEqual(shown.at(-1), [3, 'url-3']);
});

test('frame loader: failures report null and keep the loop alive; cancel and dispose stop it', async () => {
  const shown = [];
  const loader = createFrameLoader(async w => { if (w.t === 1) throw new Error('boom'); return 'u' + w.t; }, (url, w) => shown.push([w.t, url]));
  loader.request({t: 1}); await tick(); await tick(); loader.request({t: 2}); await tick(); await tick();
  assert.deepEqual(shown, [[1, null], [2, 'u2']]);
  loader.dispose(); loader.request({t: 3}); await tick(); await tick();
  assert.equal(shown.length, 2);
});

test('classGroups: camera_count is carried only when it is a positive integer; ranking still uses detection_count', () => {
  const classes = ['person', 'car', 'laptop'];
  const g = classGroups(classes, [{class_label: 'laptop', detection_count: 12, camera_count: 2}, {class_label: 'person', detection_count: 123, camera_count: 3}, {class_label: 'car', detection_count: 12}]);
  assert.deepEqual(g.detected.map(d => [d.label, d.count, d.cameraCount]), [['person', 123, 3], ['car', 12, null], ['laptop', 12, 2]]);
  for (const bad of [0, -1, 1.5, '2', NaN]) assert.equal(classGroups(classes, [{class_label: 'person', detection_count: 5, camera_count: bad}]).detected[0].cameraCount, null);
  assert.equal(CAMERA_COUNT_NOTE, '照到這個類別的鏡頭數（模型偵測，可能含誤判）');
});

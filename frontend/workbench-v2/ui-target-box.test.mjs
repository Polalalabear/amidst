import test from 'node:test';
import assert from 'node:assert/strict';
import {selectedObservationIds, pickBox, createTargetBoxSource} from './ui-target-box.mjs';

const sightings = [
  {camera_id: 'A', range_us: [0, 300], observation_ids: ['a0', 'a1', 'a2'], selected_for_single_view: true},
  {camera_id: 'A', range_us: [0, 300], observation_ids: ['x0'], selected_for_single_view: false},
  {camera_id: 'B', range_us: [300, 600], observation_ids: ['b3'], selected_for_single_view: true},
];
const box = (id, cam, t) => ({observation_id: id, camera_id: cam, timestamp_us: t, bbox_xyxy_px: [1, 2, 3, 4], score: .9});

test('only selected sightings of that camera and time contribute ids', () => {
  assert.deepEqual(selectedObservationIds(sightings, 'A', 100), ['a0', 'a1', 'a2']);
  assert.deepEqual(selectedObservationIds(sightings, 'A', 300), []);
  assert.deepEqual(selectedObservationIds(sightings, 'B', 300), ['b3']);
  assert.deepEqual(selectedObservationIds(null, 'A', 0), []);
});

test('a box is picked only at exactly its frame time (no interpolation)', () => {
  const cache = new Map([['a0', box('a0', 'A', 0)], ['a1', box('a1', 'A', 100)], ['x0', box('x0', 'A', 0)]]);
  assert.equal(pickBox(sightings, cache, 'A', 100).observation_id, 'a1');
  assert.equal(pickBox(sightings, cache, 'A', 150), null);
  assert.equal(pickBox(sightings, cache, 'A', 0).observation_id, 'a0');   // x0 is not selected -> never drawn
  assert.equal(pickBox(sightings, new Map([['a1', box('a1', 'B', 100)]]), 'A', 100), null);   // camera mismatch
});

test('the source asks the server once per id, caches, and repaints when boxes arrive', async () => {
  const calls = []; let updates = 0;
  const api = {trackBoxes: async (run, ids) => { calls.push(ids); return {ok: true, data: {observations: Object.fromEntries(ids.map((id, i) => [id, box(id, 'A', i * 100)]))}}; }};
  const src = createTargetBoxSource({api, onUpdate: () => { updates++; }});
  const state = {coreTrackResponse: {sightings}, activeRun: {run_id: 'r'}};
  assert.equal(src.box(state, 'A', 100), null);   // first call: nothing cached yet
  assert.equal(src.box(state, 'A', 100), null);   // still pending: no second request
  await new Promise(r => setTimeout(r, 5));
  assert.equal(calls.length, 1); assert.deepEqual(calls[0], ['a0', 'a1', 'a2']); assert.equal(updates, 1);
  assert.equal(src.box(state, 'A', 100).observation_id, 'a1');
  assert.equal(calls.length, 1);
});

test('a failed or unsupported box request leaves no box and is not retried', async () => {
  let n = 0;
  const src = createTargetBoxSource({api: {trackBoxes: async () => { n++; return {ok: false, error: {code: 'X'}}; }}});
  const state = {coreTrackResponse: {sightings}, activeRun: {run_id: 'r'}};
  src.box(state, 'A', 100); await new Promise(r => setTimeout(r, 5));
  assert.equal(src.box(state, 'A', 100), null); assert.equal(n, 1);
  assert.equal(createTargetBoxSource({api: {}}).box(state, 'A', 100), null);
});

test('a new response drops the old cache', async () => {
  const api = {trackBoxes: async (run, ids) => ({ok: true, data: {observations: Object.fromEntries(ids.map(id => [id, box(id, 'A', 100)]))}})};
  const src = createTargetBoxSource({api}), state = {coreTrackResponse: {sightings}, activeRun: {}};
  src.box(state, 'A', 100); await new Promise(r => setTimeout(r, 5));
  assert.ok(src.box(state, 'A', 100)); assert.ok(src.cache().size > 0);
  src.box({coreTrackResponse: {sightings: []}, activeRun: {}}, 'A', 100);   // a different response object
  assert.equal(src.cache().size, 0);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {stagePlan, trackStateChip} from './ui-model.mjs';
import {gapLiveNote, lostLiveNote, pendingLiveNote} from './ui-present.mjs';
import {buildCoreTrackingViewModel} from './core-search-track-model.mjs';

// A4-1 shape after Codex #496: many GAPs and same-camera reacquisitions (SAME_CAMERA_REACQUISITION), then LOST.
const ON = (c, a, b) => ({camera_id: c, evidence_state: 'OBSERVED', kind: 'ON_CAMERA', range_us: [a * 1e6, b * 1e6]});
const GAP = (a, b) => ({camera_id: null, evidence_state: 'UNKNOWN', kind: 'GAP', range_us: [a * 1e6, b * 1e6]});
const SV = [ON('CAM_EXT_CLEAR', 5.8, 9.0), GAP(9.0, 10.2), ON('CAM_W1', 10.2, 10.4), GAP(10.4, 14.8), ON('CAM_W1', 14.8, 15.0), GAP(15.0, 20.0), ON('CAM_W2', 20.0, 22.8),
  {camera_id: null, evidence_state: 'UNKNOWN', kind: 'LOST', range_us: [22.8e6, 50e6]}];
const resp = {status: 'LOST', as_of_us: 50e6, resolved_time: {source_range_us: [0, 50e6]}, sightings: [], single_view: SV, multi_view: [], reasons: []};
const at = s => stagePlan(SV, s * 1e6);

test('D146: before the first sighting the stage plays the FIRST camera, labelled not-yet-appeared, never observed', () => {
  assert.deepEqual(at(2), {kind: 'PENDING', cam: 'CAM_EXT_CLEAR', observed: false, last: null});
  assert.equal(pendingLiveNote, '目標尚未出現');
});
test('D146: ON_CAMERA plays that segment camera and is the only observed state', () => {
  for (const [s, cam] of [[5.8, 'CAM_EXT_CLEAR'], [8.9, 'CAM_EXT_CLEAR'], [10.3, 'CAM_W1'], [14.9, 'CAM_W1'], [21, 'CAM_W2']]) assert.deepEqual(at(s), {kind: 'ON_CAMERA', cam, observed: true, last: cam}, String(s));
});
test('D146: every GAP keeps playing the camera the target left, including same-camera reacquisition gaps', () => {
  for (const [s, cam] of [[9.0, 'CAM_EXT_CLEAR'], [9.6, 'CAM_EXT_CLEAR'], [10.4, 'CAM_W1'], [12, 'CAM_W1'], [14.79, 'CAM_W1'], [15.0, 'CAM_W1'], [17, 'CAM_W1']]) { const p = at(s); assert.equal(p.kind, 'GAP', String(s)); assert.equal(p.cam, cam, String(s)); assert.equal(p.observed, false); }
  assert.equal(gapLiveNote('CAM_W1'), '目標暫時不在畫面中，持續播放 W1 鏡頭');
});
test('D146: LOST keeps playing the last camera (to the end of the window too)', () => {
  for (const s of [22.8, 30, 49.9, 50, 60]) { const p = at(s); assert.deepEqual([p.kind, p.cam, p.observed], ['LOST', 'CAM_W2', false], String(s)); }
  assert.equal(lostLiveNote('CAM_W2'), '目標已跟丟，持續播放 W2 鏡頭');
});
test('D146: the evidence state is never OBSERVED outside ON_CAMERA', () => {
  const v = s => buildCoreTrackingViewModel(resp, {tUs: s * 1e6, playbackMode: 'single', speed: 1});
  assert.equal(trackStateChip(v(8)).text, 'OBSERVED');
  for (const s of [2, 9.5, 12, 30]) assert.notEqual(trackStateChip(v(s)).text, 'OBSERVED', String(s));
  assert.equal(v(30).singleView.lastObservedCameraId, 'CAM_W2');
});
test('D146: a response with no camera sighting at all has nothing to play', () => {
  assert.deepEqual(stagePlan([{kind: 'LOST', camera_id: null, range_us: [0, 5e6]}], 1e6), {kind: 'LOST', cam: null, observed: false, last: null});
  assert.equal(stagePlan([], 1).cam, null);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {cameraTimeline, filterClasses, trackStateChip} from './ui-model.mjs';
import {lostNote, gapNote, pendingNote} from './ui-present.mjs';
import {buildCoreTrackingViewModel} from './core-search-track-model.mjs';

// Real A4-1 shape (8787): window 0–50 s, first sighting at 5.8 s. The first 5.8 s is "not yet seen", not LOST and not EXT_CLEAR.
const SV = [
  {camera_id: 'CAM_EXT_CLEAR', evidence_state: 'OBSERVED', kind: 'ON_CAMERA', range_us: [5.8e6, 9.0e6]},
  {camera_id: null, evidence_state: 'UNKNOWN', kind: 'GAP', range_us: [9.0e6, 10.2e6]},
  {camera_id: 'CAM_W1', evidence_state: 'OBSERVED', kind: 'ON_CAMERA', range_us: [10.2e6, 10.4e6]},
  {camera_id: null, evidence_state: 'UNKNOWN', kind: 'LOST', range_us: [10.4e6, 50e6]},
];
const resp = () => ({status: 'LOST', as_of_us: 50e6, resolved_time: {source_range_us: [0, 50e6]}, sightings: [], single_view: SV, multi_view: [], reasons: []});
const view = tUs => buildCoreTrackingViewModel(resp(), {tUs, playbackMode: 'single', speed: 1});

test('timeline: the time before the first sighting is a PENDING segment at the start, so green sits where the sighting really is', () => {
  const tl = cameraTimeline(SV, {startUs: 0, asOfUs: 50e6, currentUs: 2e6});
  assert.deepEqual(tl.segments.map(s => s.kind), ['PENDING', 'ON_CAMERA', 'GAP', 'ON_CAMERA', 'LOST']);
  assert.ok(Math.abs(tl.segments[0].flex - 5.8 / 50) < 1e-9); assert.ok(tl.segments[0].current); assert.ok(!tl.segments[1].current);
  assert.equal(tl.uncovered, 0);
  assert.ok(Math.abs(tl.segments.reduce((n, s) => n + s.flex, 0) - 1) < 1e-9);
  const g = tl.segments[1]; assert.equal(g.startUs, 5.8e6); assert.equal(g.endUs, 9e6);
});
test('timeline: a hole between segments and a non-zero start are placed in time order', () => {
  const tl = cameraTimeline([{kind: 'ON_CAMERA', camera_id: 'A', range_us: [2e6, 3e6]}, {kind: 'ON_CAMERA', camera_id: 'B', range_us: [5e6, 6e6]}], {startUs: 1e6, asOfUs: 7e6, currentUs: 4e6});
  assert.deepEqual(tl.segments.map(s => [s.kind, s.startUs, s.endUs]), [['PENDING', 1e6, 2e6], ['ON_CAMERA', 2e6, 3e6], ['PENDING', 3e6, 5e6], ['ON_CAMERA', 5e6, 6e6], ['PENDING', 6e6, 7e6]]);
  assert.deepEqual(tl.segments.map(s => s.current), [false, false, true, false, false]);
  assert.deepEqual(cameraTimeline([], {startUs: 0, asOfUs: 10}).segments, []);
});
test('before the first sighting the state is PENDING, never LOST; the camera names are real', () => {
  const v0 = view(2e6).singleView;
  assert.equal(v0.segmentKind, 'PENDING'); assert.equal(v0.activeCameraId, null); assert.equal(v0.lastObservedCameraId, null);
  assert.equal(trackStateChip({singleView: v0}).text, 'UNKNOWN');
  assert.equal(view(7.4e6).singleView.segmentKind, 'ON_CAMERA'); assert.equal(view(7.4e6).singleView.activeCameraId, 'CAM_EXT_CLEAR');
  const gap = view(9.5e6).singleView; assert.equal(gap.segmentKind, 'GAP'); assert.equal(gap.lastObservedCameraId, 'CAM_EXT_CLEAR');
  const lost = view(20e6).singleView; assert.equal(lost.segmentKind, 'LOST'); assert.equal(lost.lastObservedCameraId, 'CAM_W1');
  assert.equal(lostNote(lost.lastObservedCameraId), '目標已跟丟 · 最後出現在 W1 鏡頭');
  assert.ok(!/無/.test(lostNote(null))); assert.equal(lostNote(null), pendingNote); assert.ok(!/無/.test(gapNote(null)));
});
test('feature search: English label, Chinese name and alias all match, case-insensitive; empty query keeps everything', () => {
  const classes = ['person', 'backpack', 'handbag', 'cell phone', 'tv', 'sports ball'];
  assert.deepEqual(filterClasses(classes, '人'), ['person']);
  assert.deepEqual(filterClasses(classes, 'PERSON'), ['person']);
  assert.deepEqual(filterClasses(classes, 'bag'), ['handbag']); assert.deepEqual(filterClasses(classes, 'pack'), ['backpack']); assert.deepEqual(filterClasses(classes, '背包'), ['backpack']);
  assert.deepEqual(filterClasses(classes, '手機'), ['cell phone']);
  assert.deepEqual(filterClasses(classes, 'cell_phone'), ['cell phone']);
  assert.deepEqual(filterClasses(classes, '  '), classes); assert.deepEqual(filterClasses(classes, undefined), classes);
  assert.deepEqual(filterClasses(classes, 'zzz'), []);
  assert.deepEqual(filterClasses(classes, '電視', {電視: 'tv'}), ['tv']);
  assert.deepEqual(filterClasses(null, 'a'), []);
});

import {initialPlayheadUs} from './ui-model.mjs';
test('D143: playhead starts at the first ON_CAMERA segment (A4-1: 5.8 s); no observation → window start', () => {
  assert.deepEqual(initialPlayheadUs(SV, {startUs: 0, asOfUs: 50e6}), {us: 5.8e6, jumped: true});
  assert.deepEqual(initialPlayheadUs([...SV].reverse(), {startUs: 0, asOfUs: 50e6}), {us: 5.8e6, jumped: true});
  assert.deepEqual(initialPlayheadUs([{kind: 'LOST', range_us: [0, 50e6]}], {startUs: 0, asOfUs: 50e6}), {us: 0, jumped: false});
  assert.deepEqual(initialPlayheadUs([], {startUs: 2e6, asOfUs: 9e6}), {us: 2e6, jumped: false});
  assert.deepEqual(initialPlayheadUs(undefined, {startUs: 0, asOfUs: 9e6}), {us: 0, jumped: false});
  // a segment that began before the window clamps to the window start
  assert.equal(initialPlayheadUs([{kind: 'ON_CAMERA', camera_id: 'A', range_us: [0.5e6, 4e6]}], {startUs: 1e6, asOfUs: 9e6}).us, 1e6);
  // the timeline itself is unchanged: the leading PENDING segment stays, and the jump position is not inside it
  const tl = cameraTimeline(SV, {startUs: 0, asOfUs: 50e6, currentUs: 5.8e6});
  assert.equal(tl.segments[0].kind, 'PENDING'); assert.ok(!tl.segments[0].current); assert.ok(tl.segments[1].current);
});

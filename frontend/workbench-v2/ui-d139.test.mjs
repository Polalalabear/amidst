// D139 front-desk presentation changes: pure model parts (times, blind end, plain wording). DOM behaviour is in tests/browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  trackWindow, recordingWindow, endPlaceholder, startPlaceholder, timeRangeText, blindReacquire, normalizeSettings, DEFAULT_SETTINGS, clockSeconds, padClock,
} from './ui-model.mjs';
import {PLAIN, plainState, PLAIN_STATE, planHeadText, reacquiredText, speedNoteText, techSummary, gapNote} from './ui-present.mjs';

const clock = {wall_origin: '2026-11-01T14:00:00+08:00', t0_us: 0, rate: 1, source_duration_us: 5 * 60e6, timezone: 'Asia/Taipei'};

test('D139-5 regression: a blank track window is never sent empty (was 14:00:00～14:00:00 / 時間窗內無觀測紀錄)', () => {
  const w = trackWindow('', '', clock);
  assert.equal(w.ok, true);
  assert.equal(w.start, '14:00:00'); assert.equal(w.end, '14:05:00');
  assert.notEqual(w.start, ''); assert.notEqual(w.end, ''); assert.notEqual(w.start, w.end);
  assert.equal(timeRangeText(w.start, w.end), '14:00:00～14:05:00');
});
test('D139-5: start blank + end typed, start typed + end blank, both typed', () => {
  assert.deepEqual([trackWindow('', '14:02', clock).start, trackWindow('', '14:02', clock).end], ['14:00:00', '14:02:00']);
  assert.deepEqual([trackWindow('14:01:30', '', clock).start, trackWindow('14:01:30', '', clock).end], ['14:01:30', '14:05:00']);
  assert.deepEqual([trackWindow('14:01', '14:03', clock).start, trackWindow('14:01', '14:03', clock).end], ['14:01:00', '14:03:00']);
});
test('D139-5: end = clock start + source_duration, also with a non-zero t0', () => {
  const shifted = {...clock, t0_us: 7e6};
  assert.deepEqual(recordingWindow(shifted), {start: '14:00:00', end: '14:05:00'});
  assert.deepEqual(recordingWindow({...clock, rate: 2}), {start: '14:00:00', end: '14:02:30'});
});
test('D139-5: without a clock mapping or with end before start the form is refused, never sent empty', () => {
  const none = trackWindow('', '', null); assert.equal(none.ok, false); assert.equal(none.code, 'CLOCK_UNKNOWN'); assert.equal(none.start, ''); 
  assert.equal(trackWindow('14:03', '14:02', clock).code, 'END_BEFORE_START');
  assert.equal(trackWindow('14:03', '14:03', clock).code, 'END_BEFORE_START');
});
test('D139-5: end placeholder reads 到錄影結尾（HH:MM:SS） and start placeholder is the recording start', () => {
  assert.equal(endPlaceholder(clock), '到錄影結尾（14:05:00）');
  assert.equal(startPlaceholder(clock), '14:00:00');
  assert.equal(endPlaceholder(null), '到錄影結尾'); assert.equal(startPlaceholder(null), 'HH:MM:SS');
});
test('clock helpers', () => {
  assert.equal(clockSeconds('13:05'), 13 * 3600 + 5 * 60); assert.equal(clockSeconds('abc'), null); assert.equal(padClock('9:05'), '09:05:00');
});

test('D139-6: blind route end is labelled with the camera and the real observation time once the target reappears', () => {
  const sv = [
    {kind: 'ON_CAMERA', camera_id: 'CAM_A', range_us: [0, 60e6]},
    {kind: 'GAP', camera_id: null, range_us: [60e6, 120e6]},
    {kind: 'ON_CAMERA', camera_id: 'CAM_B', range_us: [120e6, 240e6]},
  ];
  assert.equal(blindReacquire(sv, 30e6, clock), null);          // still on A: no blind interval yet
  assert.equal(blindReacquire(sv, 90e6, clock), null);          // inside the gap: not reappeared yet
  const r = blindReacquire(sv, 150e6, clock);
  assert.deepEqual(r, {cameraId: 'CAM_B', atUs: 120e6, atText: '14:02:00'});
  assert.equal(reacquiredText(r), '已由 B 鏡頭於 14:02:00 觀測到');
  assert.equal(PLAIN.bothEndsObserved, '兩端已觀測，中段為推測');
  // a gap that ends in LOST is not a reappearance
  assert.equal(blindReacquire([{kind: 'GAP', range_us: [0, 10e6]}, {kind: 'LOST', range_us: [10e6, 20e6]}], 15e6, clock), null);
  assert.equal(blindReacquire(null, 0, clock), null);
});

test('D139-3: plain wording; the four evidence states stay distinct', () => {
  assert.equal(new Set(['OBSERVED', 'INFERRED', 'MISSING', 'UNKNOWN'].map(plainState)).size, 4);
  assert.equal(PLAIN_STATE.MISSING, '此時段沒有畫面');
  assert.equal(plainState('whatever'), PLAIN_STATE.UNKNOWN);
  assert.equal(planHeadText('LOW'), '推測路線 · 信心低');
  assert.match(gapNote('CAM_A'), /此時段沒有畫面/);
  const tech = techSummary(['自動種子', {text: 'GRAPH_NOT_APPROVED'}, '自動種子', 'ASSOCIATION_IDENTITY_UNCONFIRMED']);
  assert.equal(tech, '自動種子 · GRAPH_NOT_APPROVED · ASSOCIATION_IDENTITY_UNCONFIRMED');
  for (const plain of Object.values(PLAIN)) for (const code of ['DEMO_DEFAULT', 'GRAPH_NOT_APPROVED', 'UNKNOWN', 'ACTUAL_BLENDER', 'D124', 'MISSING']) assert.ok(!plain.includes(code), `${plain} leaks ${code}`);
});
test('D139-2: speed note drops the 設定 N× part and keeps only a measured actual speed', () => {
  assert.equal(speedNoteText('設定 1×'), ''); assert.equal(speedNoteText('設定 1.5×'), ''); assert.equal(speedNoteText(''), '');
  assert.equal(speedNoteText('設定 1× · 實際 0.9×'), '實際 0.9×');
});
test('D139-3: presentation mode defaults on for the front desk and can be switched off', () => {
  assert.equal(DEFAULT_SETTINGS.presentationMode, true);
  assert.equal(normalizeSettings(null).presentationMode, true);
  assert.equal(normalizeSettings({presentationMode: false}).presentationMode, false);
  assert.equal(normalizeSettings({presentationMode: 'no'}).presentationMode, true);
});

test('D139 static wiring: one speed dropdown, one timeline, ⓘ for tags, concrete track window, no GT words', () => {
  const shell = readFileSync(new URL('./ui-shell.mjs', import.meta.url), 'utf8');
  assert.match(shell, /ui-speed'/); assert.doesNotMatch(shell, /data-speed/); assert.doesNotMatch(shell, /ui-speeds/);
  assert.match(shell, /trackWindow\(form\.start, form\.end, run\?\.clock_mapping\)/);
  assert.match(shell, /ui-scrub-overlay/); assert.match(shell, /ui-info/); assert.match(shell, /ui-blind-end/); assert.match(shell, /ui-track-range/);
  assert.match(shell, /ui-manual-target/); assert.match(shell, /button\.disabled = true|disabled = true/);   // D137 button stays disabled
  const present = readFileSync(new URL('./ui-present.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(present + shell, /gt_private|ground_truth|renderer_trajectory|visibility_|depth_map/i);
});

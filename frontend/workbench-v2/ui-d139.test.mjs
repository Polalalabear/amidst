// D139 front-desk presentation changes: pure model parts (times, blind end, plain wording). DOM behaviour is in tests/browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  trackWindow, recordingWindow, endPlaceholder, startPlaceholder, timeRangeText, blindReacquire, reacquireMarker, floorPlan, clockRateSupported, RATE_UNSUPPORTED_TEXT, classGroups, DETECTION_COUNT_NOTE, normalizeSettings, DEFAULT_SETTINGS, clockSeconds, padClock,
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
  // wall_origin is the wall time of t0 (not of source 0): the valid source range [0, duration] starts t0 earlier
  assert.deepEqual(recordingWindow(shifted), {start: '13:59:53', end: '14:04:53'});
});
test('D139 P2: non-zero t0 (Codex case) gives 13:59:58～14:00:48', () => {
  const cm = {wall_origin: '2026-11-01T14:00:00+08:00', t0_us: 2000000, rate: 1, source_duration_us: 50000000};
  assert.deepEqual(recordingWindow(cm), {start: '13:59:58', end: '14:00:48'});
  const w = trackWindow('', '', cm); assert.equal(w.ok, true); assert.deepEqual([w.start, w.end], ['13:59:58', '14:00:48']);
  assert.equal(endPlaceholder(cm), '到錄影結尾（14:00:48）'); assert.equal(startPlaceholder(cm), '13:59:58');
});
test('D139 P2: rate other than 1 is refused with plain words (backend supports rate 1 only)', () => {
  const cm = {wall_origin: '2026-11-01T14:00:00+08:00', t0_us: 0, rate: 2, source_duration_us: 50000000};
  for (const [a, b] of [['', ''], ['14:00:00', '14:00:10']]) {
    const w = trackWindow(a, b, cm); assert.equal(w.ok, false); assert.equal(w.code, 'RATE_UNSUPPORTED'); assert.equal(w.text, RATE_UNSUPPORTED_TEXT);
  }
  assert.match(RATE_UNSUPPORTED_TEXT, /不支援/); assert.doesNotMatch(RATE_UNSUPPORTED_TEXT, /rate|UNKNOWN|ClockMapping/);
  assert.equal(clockRateSupported({rate: 1}), true); assert.equal(clockRateSupported({}), true); assert.equal(clockRateSupported(null), true); assert.equal(clockRateSupported({rate: 0.5}), false);
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
  // The negative source-word check lives in tests/q1q5/test_ui_d139_boundary.py (the guard scans this folder for those words).
});

import {mergeFlicker, JOURNAL_MERGE_GAP_US, homeScreen, trackJournal} from './ui-model.mjs';
test('D139 journal: short same-camera GAPs merge into one row; raw segments are untouched', () => {
  // B-05 shape: A appears / leaves / appears ... within 2 s (≈20 flickers)
  const raw = []; let t = 0;
  for (let i = 0; i < 20; i++) { raw.push({kind: 'ON_CAMERA', camera_id: 'A', range_us: [t, t + 60000]}); t += 60000; if (i < 19) { raw.push({kind: 'GAP', camera_id: null, range_us: [t, t + 40000]}); t += 40000; } }
  const copy = JSON.stringify(raw);
  const {segments, merged} = mergeFlicker(raw);
  assert.equal(JSON.stringify(raw), copy);                       // input not mutated
  assert.equal(segments.length, 1); assert.equal(merged, 19);
  assert.deepEqual(segments[0].range_us, [0, raw.at(-1).range_us[1]]);
  const rows = trackJournal(segments, clock);
  assert.equal(rows.length, 1); assert.match(rows[0].text, /鎖定於 A/);
  assert.equal(trackJournal(raw, clock).length, 39);             // the raw journal (admin / present=0 data) still has every row
});
test('D139 journal merge rule: only GAP <= 1 s between the SAME camera; different camera, long gap and LOST stay', () => {
  assert.equal(JOURNAL_MERGE_GAP_US, 1e6);
  const seg = (kind, cam, a, b) => ({kind, camera_id: cam, range_us: [a, b]});
  assert.equal(mergeFlicker([seg('ON_CAMERA', 'A', 0, 5e6), seg('GAP', null, 5e6, 6e6), seg('ON_CAMERA', 'A', 6e6, 9e6)]).merged, 1);      // exactly 1 s merges
  assert.equal(mergeFlicker([seg('ON_CAMERA', 'A', 0, 5e6), seg('GAP', null, 5e6, 6.1e6), seg('ON_CAMERA', 'A', 6.1e6, 9e6)]).merged, 0);  // 1.1 s stays
  assert.equal(mergeFlicker([seg('ON_CAMERA', 'A', 0, 5e6), seg('GAP', null, 5e6, 5.5e6), seg('ON_CAMERA', 'B', 5.5e6, 9e6)]).merged, 0);  // camera change stays
  assert.equal(mergeFlicker([seg('ON_CAMERA', 'A', 0, 5e6), seg('GAP', null, 5e6, 5.5e6), seg('LOST', null, 5.5e6, 9e6)]).segments.length, 3);
  assert.deepEqual(mergeFlicker(null), {segments: [], merged: 0});
});
test('D139 brand: home is the cover while it is on, else the entry setting', () => {
  assert.equal(homeScreen({coverAnimation: true, defaultCase: 'case2'}), 'cover');
  assert.equal(homeScreen({coverAnimation: false, defaultCase: null}), 'choose');
  assert.equal(homeScreen({coverAnimation: false, defaultCase: 'case1'}), 'case1');
});
test('D139 static: favicon on both pages, admin brand links to the front desk, query window layout', () => {
  const read = f => readFileSync(new URL(f, import.meta.url), 'utf8');
  for (const f of ['./index.html', './admin.html']) assert.match(read(f), /<link rel="icon" href="data:image\/svg\+xml;base64,/, f);
  assert.match(read('./admin.html'), /<a class="ui-side-brand" href="index\.html"/);
  const shell = read('./ui-shell.mjs');
  assert.match(shell, /go\(homeScreen\(settings\)\)/); assert.match(shell, /qWin1\.inert = !open1/); assert.match(shell, /ui-qfeat/);
  assert.match(read('./ui.css'), /\.ui-qfeat\{[^}]*overflow-y:auto/);
});

import {SPEEDS as UI_SPEEDS} from './ui-model.mjs';
import {SUPPORTED_SPEEDS} from './core-search-track-model.mjs';
import {advanceUs} from './q-time.mjs';
import {createStore, initialState} from './store.mjs';
test('D139 0.5× speed: offered by the front desk, accepted by store and clock, source time advances at half rate', () => {
  assert.deepEqual([...UI_SPEEDS], [0.5, 1, 1.5, 2]); assert.deepEqual([...SUPPORTED_SPEEDS], [0.5, 1, 1.5, 2]);
  assert.equal(normalizeSettings({trackSpeed: 0.5}).trackSpeed, 0.5);
  const store = createStore(initialState()); store.dispatch({type: 'SET_SPEED', speed: 0.5}); assert.equal(store.getState().speed, 0.5);
  assert.equal(advanceUs(0, 1000, 0.5, 50e6).tUs, 500000);
});
test('D139 mode switch replaces the 追蹤新目標 chip: three cover modes in the header', () => {
  const shell = readFileSync(new URL('./ui-shell.mjs', import.meta.url), 'utf8');
  assert.match(shell, /modeSeg\.id = 'ui-modes'/); assert.match(shell, /for \(const c of CASES\)/); assert.doesNotMatch(shell, /追蹤新目標…'/);
});

// ---- P1: the observed re-acquisition end is independent of the (future-guarded) inferred curve ----------------------
import {buildTopdownView} from './topdown-model.mjs';
test('D139 P1: A4 10.21 s / B4 2.21 s — end shown from the tracked segment while the future snapshot stays refused', () => {
  const cases = [
    {name: 'A4-1', gap: [8.0e6, 10.2e6], reacqAt: 10.2e6, play: 10.21e6, asOf: 50e6},
    {name: 'B4-1', gap: [1.4e6, 2.2e6], reacqAt: 2.2e6, play: 2.21e6, asOf: 42e6},
  ];
  for (const c of cases) {
    const sv = [{kind: 'ON_CAMERA', camera_id: 'CAM_W2', range_us: [0, c.gap[0]]}, {kind: 'GAP', camera_id: null, range_us: c.gap}, {kind: 'ON_CAMERA', camera_id: 'CAM_W1', range_us: [c.reacqAt, c.asOf]}];
    // the whole-window estimate carries as_of = window end, later than the playhead → the guard refuses it
    const estimate = {status: 'ESTIMATED', estimate: {as_of_us: c.asOf, last_camera_id: 'CAM_W2', last_observed_us: c.gap[0] - 1, confidence: 'LOW', candidates: [{camera_id: 'CAM_W1', rank: 1, confidence: 'LOW'}]}};
    const model = buildTopdownView({estimate, currentTUs: c.play, cameraPositions: {CAM_W1: [20, 3], CAM_W2: [10, 3]}, observedCameras: ['CAM_W2', 'CAM_W1']});
    assert.equal(model.blind_curve?.visible ?? false, false, c.name + ' curve must stay hidden (FUTURE_AS_OF)');
    assert.equal(model.blind_status, 'UNAVAILABLE', c.name);
    const plan = floorPlan(model, {currentTUs: c.play});
    assert.equal(plan.blindVisible, false, c.name);
    const r = blindReacquire(sv, c.play, clock);
    assert.equal(r.cameraId, 'CAM_W1', c.name); assert.equal(r.atUs, c.reacqAt);
    assert.equal(reacquiredText(r), `已由 W1 鏡頭於 ${r.atText} 觀測到`);
    // before the reappearance the playhead has not reached it
    assert.equal(blindReacquire(sv, c.reacqAt - 1, clock), null);
  }
});
test('D139 P1: end marker is the observed camera node, never another prediction\'s end point', () => {
  const nodes = [{cameraId: 'CAM_W1', x: 70, y: 30, isActive: true}, {cameraId: 'CAM_W2', x: 20, y: 30}];
  const reacq = {cameraId: 'CAM_W1', atUs: 1, atText: '14:00:01'};
  assert.deepEqual(reacquireMarker({nodes, blindVisible: false, blind: []}, reacq), [70, 30]);
  assert.deepEqual(reacquireMarker({nodes, blindVisible: false, blind: [[1, 1], [2, 2]]}, reacq), [70, 30]);   // hidden curve points are ignored
  assert.deepEqual(reacquireMarker({nodes, blindVisible: true, blind: [[20, 30], [65, 30]]}, reacq), [65, 30]); // a legal curve keeps its own end
  assert.equal(reacquireMarker({nodes, blindVisible: false, blind: []}, {cameraId: 'CAM_X'}), null);
  assert.equal(reacquireMarker({nodes}, null), null);
});

// ---- D139-1: feature groups by detected_class_counts ------------------------------------------------------------------
test('D139-1 classGroups: detected first by count, others after; tracking disables non-person; missing counts fall back', () => {
  const classes = ['person', 'car', 'laptop', 'chair', 'cup'];
  const counts = [{class_label: 'laptop', detection_count: 12}, {class_label: 'person', detection_count: 123}, {class_label: 'car', detection_count: 12}];
  const g = classGroups(classes, counts);
  assert.equal(g.grouped, true);
  assert.deepEqual(g.detected.map(d => [d.label, d.count]), [['person', 123], ['car', 12], ['laptop', 12]]);   // count desc, label asc on ties
  assert.deepEqual(g.others.map(o => o.label), ['chair', 'cup']);
  const t = classGroups(classes, counts, c => c === 'person');
  assert.deepEqual(t.detected.map(d => d.supported), [true, false, false]); assert.deepEqual(t.others.map(o => o.supported), [false, false]);
  for (const bad of [undefined, null, [], 'x', [{class_label: 'person'}], [{class_label: 'bogus', detection_count: 3}], [{class_label: 'person', detection_count: 0}], [{class_label: 'person', detection_count: 1.5}]]) {
    const f = classGroups(classes, bad); assert.equal(f.grouped, false); assert.deepEqual(f.detected, []); assert.deepEqual(f.others.map(o => o.label), classes);
  }
  assert.equal(classGroups(classes, [{class_label: 'person', detection_count: 2}, {class_label: 'person', detection_count: 9}]).detected[0].count, 2);   // first wins, no double entry
  assert.equal(classGroups(undefined, counts).grouped, false);
  assert.equal(DETECTION_COUNT_NOTE, '模型偵測筆數，含誤判，不是實際物件數');
});

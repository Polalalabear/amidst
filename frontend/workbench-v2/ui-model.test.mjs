import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  normalizeSettings, DEFAULT_SETTINGS, validateSearchForm, validateTrackForm, trackWindow, wallClockText, stagesModel,
  cameraTimeline, blindShare, floorPlan, trackStateChip, trackJournal, parseRoute, nextAfterCover, wallCards, classDisplay,
  pushEvent, normalizeLog, EVENTLOG_LIMIT, loadSettings, saveSettings,
} from './ui-model.mjs';
import {buildOverview, missingRate, countsFromSearch, bins10s, sparkPoints} from './admin-overview-model.mjs';

const clock = {wall_origin: '2026-11-01T13:00:00+08:00', t0_us: 0, rate: 1, source_duration_us: 30 * 60e6, timezone: 'Asia/Taipei'};

test('settings: defaults, clamping and garbage input', () => {
  assert.deepEqual(normalizeSettings(null), DEFAULT_SETTINGS);
  const s = normalizeSettings({defaultCase: 'x', trackSpeed: 3, keepBlindSec: 99999, resultLimit: -4, coverAnimation: 'no'});
  assert.equal(s.defaultCase, null); assert.equal(s.trackSpeed, 1); assert.equal(s.keepBlindSec, 600); assert.equal(s.resultLimit, 1); assert.equal(s.coverAnimation, true);
  assert.equal(normalizeSettings({defaultCase: 'case2', trackLayout: 'multi', trackSpeed: 1.5}).defaultCase, 'case2');
});
test('settings persist in a browser-like storage and survive a throwing one', () => {
  const mem = new Map(), storage = {getItem: k => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v)};
  assert.equal(saveSettings(storage, {...DEFAULT_SETTINGS, defaultCase: 'case1'}), true);
  assert.equal(loadSettings(storage).defaultCase, 'case1');
  const broken = {getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); }};
  assert.deepEqual(loadSettings(broken), DEFAULT_SETTINGS); assert.equal(saveSettings(broken, DEFAULT_SETTINGS), false);
});
test('case1 needs time plus a place or a feature; case2 needs a feature and may leave time blank', () => {
  assert.equal(validateSearchForm({start: '13:00', end: '', classLabel: 'person'}).code, 'TIME_REQUIRED');
  assert.equal(validateSearchForm({start: '13:00', end: '13:30'}).code, 'LOCATION_OR_FEATURE_REQUIRED');
  assert.ok(validateSearchForm({start: '13:00', end: '13:30', regionIds: ['R101']}).ok);
  assert.ok(validateSearchForm({start: '13:00', end: '13:30', classLabel: 'person'}).ok);
  assert.equal(validateTrackForm({}).code, 'FEATURE_REQUIRED'); assert.ok(validateTrackForm({classLabel: 'person'}).ok);
  assert.deepEqual(trackWindow('', clock), {start: '', end: ''});
  assert.deepEqual(trackWindow('13:05', clock), {start: '13:05', end: '13:30:00'});
});
test('wall clock text comes from the declared clock mapping only', () => {
  assert.equal(wallClockText(clock, 5 * 60e6), '13:05:00'); assert.equal(wallClockText(null, 0), null);
  assert.equal(classDisplay('person', {}), '人物'); assert.equal(classDisplay('toaster', {烤箱: 'toaster'}), '烤箱');
});
test('progress: four stages, monotonic, a miss freezes (stalled), done only when full', () => {
  const at = p => stagesModel(p).map(s => s.state);
  assert.deepEqual(at(0), ['pending', 'pending', 'pending', 'pending']); assert.deepEqual(at(0.4), ['done', 'active', 'pending', 'pending']);
  assert.deepEqual(stagesModel(0.4, {miss: true}).map(s => s.state), ['done', 'stalled', 'pending', 'pending']);
  let prev = -1; for (let p = 0; p <= 1; p += 0.05) { const f = stagesModel(p).reduce((n, s) => n + s.filled, 0); assert.ok(f >= prev); prev = f; }
  assert.ok(stagesModel(1, {resolved: true}).every(s => s.state === 'done'));
});
test('camera timeline: proportional segments, GAP and LOST kept, current segment marked', () => {
  const sv = [{kind: 'ON_CAMERA', camera_id: 'A', range_us: [0, 3e6]}, {kind: 'GAP', camera_id: null, range_us: [3e6, 5e6]}, {kind: 'ON_CAMERA', camera_id: 'B', range_us: [5e6, 10e6]}];
  const tl = cameraTimeline(sv, {startUs: 0, asOfUs: 10e6, currentUs: 4e6});
  assert.deepEqual(tl.segments.map(s => s.kind), ['ON_CAMERA', 'GAP', 'ON_CAMERA']); assert.deepEqual(tl.segments.map(s => s.current), [false, true, false]);
  assert.ok(Math.abs(tl.segments[0].flex - 0.3) < 1e-9); assert.equal(tl.marker, 0.4); assert.ok(Math.abs(blindShare(sv) - 0.2) < 1e-9);
  assert.equal(blindShare([]), null);
});
test('floor plan: UNKNOWN without camera positions; dashed route only when inferred and fresh; solid route is observed only', () => {
  assert.equal(floorPlan({nodes: []}).available, false); assert.equal(floorPlan(null).available, false);
  const td = {nodes: [{cameraId: 'A', x: 10, y: 10, isActive: false}, {cameraId: 'B', x: 90, y: 90, isActive: true}], observed_cameras: ['A', 'B'], blind_curve: {visible: true, svgPoints: [[10, 10], [50, 60], [90, 90]], stroke_dasharray: '4 5'}, last_observed_us: 1e6};
  const p = floorPlan(td, {settings: {...DEFAULT_SETTINGS}, currentTUs: 2e6});
  assert.equal(p.blindVisible, true); assert.equal(p.observed.length, 2); assert.deepEqual(p.current, [90, 90]);
  assert.equal(floorPlan(td, {settings: {...DEFAULT_SETTINGS, keepBlindSec: 1}, currentTUs: 5e6}).blindVisible, false);
  assert.equal(floorPlan(td, {settings: {...DEFAULT_SETTINGS, blindPlan: false}, currentTUs: 2e6}).blindVisible, false);
});
test('state chips and journal map only to OBSERVED / INFERRED / MISSING / UNKNOWN', () => {
  const k = kind => trackStateChip({singleView: {segmentKind: kind}}).text;
  assert.deepEqual(['ON_CAMERA', 'GAP', 'LOST', 'x'].map(k), ['OBSERVED', 'INFERRED', 'LOST', 'UNKNOWN']);
  const j = trackJournal([{kind: 'ON_CAMERA', camera_id: 'A', range_us: [0, 1]}, {kind: 'GAP', range_us: [1, 2]}, {kind: 'LOST', range_us: [2, 3]}], clock);
  assert.deepEqual(j.map(r => r.state), ['OBSERVED', 'INFERRED', 'MISSING']); assert.match(j[0].text, /鎖定於 A/);
});
test('routing: ?ev / ?recording open 查看; ?screen picks a case; ?ui=legacy keeps the old page', () => {
  assert.equal(parseRoute('?ev=b05b').initial, 'case3'); assert.equal(parseRoute('?screen=case2').initial, 'case2');
  for (const [screen, target] of [['search', 'case1'], ['track-single', 'case2'], ['track-multi', 'case2'], ['blind', 'case2']]) assert.equal(parseRoute('?screen='+screen).initial, target);
  assert.equal(parseRoute('').initial, null); assert.equal(parseRoute('?ui=legacy').legacy, true); assert.equal(parseRoute('?screen=zzz').initial, null);
  assert.equal(nextAfterCover({defaultCase: null}), 'choose'); assert.equal(nextAfterCover({defaultCase: 'case1'}), 'case1');
});
test('result limit and the event log are bounded', () => {
  const m = {allCards: Array.from({length: 30}, (_, i) => ({rank: i}))};
  assert.deepEqual([wallCards(m, 24).shown, wallCards(m, 24).truncated, wallCards(m, 50).truncated], [24, true, false]);
  let log = []; for (let i = 0; i < EVENTLOG_LIMIT + 10; i++) log = pushEvent(log, {at: i, text: 't', state: 'OBSERVED'});
  assert.equal(log.length, EVENTLOG_LIMIT); assert.equal(normalizeLog([{at: 1, text: 'x', state: 'BAD'}, null]).length, 0);
});

test('admin overview: no figure without a source — metrics are null, never example values', () => {
  const m = buildOverview({});
  assert.equal(m.metrics.length, 8); assert.ok(m.metrics.every(x => x.measured === false)); assert.equal(m.cameras.total, 0); assert.equal(m.tracking, null);
  assert.equal(m.perCamera.length, 0); assert.equal(m.timeline.bins.length, 0);
});
test('admin overview: figures come from bootstrap, the local snapshot and the event log', () => {
  const run = {scene_id: 'S', run_id: 'R', camera_ids: ['A', 'B', 'C'], detection_index_sha256: 'x', supported_classes: {aliases: {}}, region_graph: {regions: [{region_id: 'r1', display_name: '區 1'}]},
    sampling: {per_camera: [{camera_id: 'A', inferred_ranges_us: [[0, 90]], not_inferred: [[90, 100]]}, {camera_id: 'B', inferred_ranges_us: [[0, 100]], not_inferred: []}]}};
  const boot = {data_origin: 'RECORDED', status: 'READY', runs: [run]};
  assert.ok(Math.abs(missingRate(run) - 10 / 200) < 1e-9);
  const snap = {sceneId: 'S', runId: 'R', lastSearch: {ms: 4200, perCamera: [{cameraId: 'A', person: 5, object: 1}]}, lastTrack: {lockMs: 6800, cameraId: 'B', state: 'OBSERVED', blindShare: 0.18, classLabel: 'person', reasons: ['GRAPH_NOT_APPROVED']}, history: {lock: [6000, 6800], find: [4000]}};
  const m = buildOverview({bootstrap: boot, snapshot: snap, log: [{at: 1000, text: '切到 B', state: 'OBSERVED'}], now: 12000});
  const by = Object.fromEntries(m.metrics.map(x => [x.key, x]));
  assert.equal(by.lock.value, '6.80'); assert.equal(by.find.value, '4.20'); assert.equal(by.blind.value, 18); assert.equal(by.missing.value, '5.0'); assert.equal(by.index.value, '1 / 1');
  assert.equal(by.speed.measured, false); assert.equal(by.agent.measured, false); assert.equal(by.switch.measured, false);
  assert.ok(by.lock.spark && !by.find.spark); assert.deepEqual(m.cameras.list.map(c => c.state), ['data', 'tracking', 'missing']);
  assert.equal(m.perCamera[0].total, 6); assert.equal(m.tracking.cameraId, 'B'); assert.deepEqual(m.tracking.reasons, ['GRAPH_NOT_APPROVED']);
  assert.deepEqual(m.regions, [{id: 'r1', name: '區 1'}]); assert.ok(m.timeline.bins.length >= 2); assert.equal(m.events[0].text, '切到 B');
  assert.equal(sparkPoints([1]), null); assert.equal(bins10s([]).bins.length, 0);
  assert.deepEqual(countsFromSearch({hits: [{camera_id: 'A', segments: [{matched_frames: 3}], basis: [{kind: 'OBJECT', class_label: 'person'}]}, {camera_id: 'A', segments: [{matched_frames: 2}], basis: [{kind: 'OBJECT', class_label: 'laptop'}]}]}), [{cameraId: 'A', person: 3, object: 2}]);
});

const read = f => readFileSync(new URL('./' + f, import.meta.url), 'utf8');
test('static: new front desk is wired, tokens match the approved design, no CDN, no GT words, one legacy bridge', () => {
  const html = read('index.html'), admin = read('admin.html'), css = read('ui.css');
  assert.match(html, /id="ui-v1"/); assert.match(html, /href="ui\.css"/); assert.match(html, /<body id="q-root">/); assert.doesNotMatch(html + admin, /https?:\/\//);
  for (const token of ['#141413', '#d97757', '#d4724f', '#5a95d8']) assert.ok(css.toLowerCase().includes(token), token);
  for (const font of ['Source Serif 4', 'Inter', 'Noto Sans TC', 'JetBrains Mono']) assert.ok(css.includes(font), font);
  assert.doesNotMatch(css, /@media[^{]*max-width/, 'desktop only');
  const shell = read('ui-shell.mjs'), app = read('app.mjs');
  assert.doesNotMatch(shell, /querySelector\(['"]#(q-|monitor-room|q1-slot|q2-slot|core-)/, 'ui-shell reaches legacy DOM only through ctx.legacy');
  assert.doesNotMatch(shell, /from '\.\/app\.mjs'/); assert.match(app, /LEGACY BRIDGE/);
  const banned = new RegExp(['gt'+'_', 'ground'+'_truth', 'visib'+'ility', '\\bdep'+'th\\b', 'trajec'+'tory', 'gt'+'_private', 'api[_-]?key', 'OPEN'+'AI'].join('|'), 'i');
  for (const f of ['ui-shell.mjs', 'ui-model.mjs', 'admin-ui.mjs', 'admin-overview-model.mjs']) assert.doesNotMatch(read(f), banned, f);
  for (const id of ['admin-overview', 'admin-settings']) assert.match(admin, new RegExp(`id="${id}"`));
});
test('static: cover entrance finishes within 0.6 s and the chooser transition is about 0.25 s', () => {
  const css = read('ui.css'); const dur = Number(/\.ui-rise\{animation:uiRise (\.\d+)s/.exec(css)[1]);
  const delays = [...css.matchAll(/\.ui-d\d\{animation-delay:(\.?\d*\.?\d+)s\}/g)].map(m => Number(m[1]));
  assert.ok(Math.max(...delays) + dur <= 0.6 + 1e-9); assert.match(css, /\.ui-layer\{[^}]*transition:opacity \.25s/);
});

test('static: cover subtitle, sticky bottom bar and design camera sizes', () => {
  const shell = read('ui-shell.mjs'), css = read('ui.css');
  assert.ok(shell.includes('Agentic 驅動之智慧監控數位孿生系統'));
  assert.match(css, /\.ui-bottombar\{position:sticky;bottom:0/); assert.match(shell, /sCase2\.append\(layout, bar\)/);
  assert.match(css, /\.ui-media\{height:300px;flex:0 0 auto/); assert.match(css, /\.ui-stagebox\{position:relative;height:520px;flex:0 0 auto/);
});

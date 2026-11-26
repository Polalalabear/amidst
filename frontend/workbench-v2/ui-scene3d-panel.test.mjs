import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {mountUiScene3dPanel} from './ui-scene3d-panel.mjs';
import {buildCoreTrackingViewModel} from './core-search-track-model.mjs';
import {floorPlan} from './ui-model.mjs';
import {ESTIMATE_REASON_TEXT, scene3dStateText} from './scene3d-model.mjs';

function host() {
  const doc = {createElement: tag => new Element(tag)};
  class Element {
    constructor(tag) { this.tag = tag; this.ownerDocument = doc; this.children = []; this.dataset = {}; this.attrs = {}; this.events = {}; this.value = ''; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.value = ''; this.children = nodes; }
    set textContent(value) { this.value = String(value); this.children = []; }
    get textContent() { return this.value + this.children.map(n => n.textContent).join(' '); }
    setAttribute(k, v) { this.attrs[k] = String(v); }
    addEventListener(k, fn) { this.events[k] = fn; }
    click() { this.events.click?.(); }
  }
  return new Element('section');
}
const walk = n => [n, ...n.children.flatMap(walk)];
const modeButton = (n, mode) => walk(n).find(x => x.tag === 'button' && x.dataset.mode === mode);
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return {promise, resolve, reject}; };
const flush = async () => { await Promise.resolve(); await Promise.resolve(); };
const cameraAsset = {cameras: [{camera_id: 'CAM_A', width: 960, height: 540, cy: 270, fy: 625,
  camera_to_world: [[1,0,0,0],[0,1,0,2],[0,0,1,0],[0,0,0,1]]}]};
const response = estimate => ({status: 'TRACKING', as_of_us: 5e6, single_view: [{kind: 'ON_CAMERA', camera_id: 'CAM_A', range_us: [0, 5e6]}],
  sightings: [], display_estimate: estimate == null ? estimate : {last_observed_us: 5e6, source_clock_id: 'C', ...estimate}});
const cameraGraph = {layout: 'NODE_GRAPH', cameras: [{camera_id: 'CAM_A', display_position: {status: 'CALIBRATED_STATIC', xy_m: [0,0]}}, {camera_id: 'CAM_B', display_position: {status: 'CALIBRATED_STATIC', xy_m: [4,4]}}]};
const model = estimate => buildCoreTrackingViewModel(response(estimate), {tUs: 5e6, cameraGraph, runClockId: 'C'});
function setup() {
  const root = host(), views = [], flatModels = [];
  const panel = mountUiScene3dPanel({host: root, scene3dFactory: () => {
    const loading = deferred(), instance = {ready: loading.promise, loading, updates: [], dead: 0,
      cameraAsset: () => cameraAsset, update(m) { this.updates.push(m); }, destroy() { this.dead++; }};
    views.push(instance); return instance;
  }});
  const update = (view, runKey = 'A4', cameraIds = ['CAM_A']) => panel.update({view, runKey, cameraIds, render2d: (_host, m) => flatModels.push(m)});
  return {root, views, flatModels, panel, update};
}

test('new front desk defaults to 2D, toggles 3D lazily, reuses the shared estimate model', async () => {
  const s = setup(), view = model({est_xy: [2, 1], uncertainty_m: 0.8}); s.update(view);
  assert.equal(s.root.dataset.mode, '2d'); assert.equal(s.views.length, 0);
  assert.match(s.root.textContent, /系統估計（推論）.*0.8 m/);
  assert.deepEqual(s.flatModels.at(-1).estimate.xy, [2,1]);
  modeButton(s.root, '3d').click(); assert.equal(s.views.length, 1); assert.match(s.root.textContent, /載入 3D/);
  s.views[0].loading.resolve(); await flush();
  assert.equal(s.root.dataset.mode, '3d'); assert.equal(modeButton(s.root, '3d').attrs['aria-pressed'], 'true');
  assert.deepEqual(s.views[0].updates.at(-1).estimate.xy, [2,1]);
  assert.equal(s.views[0].updates.at(-1).estimate.uncertaintyM, 0.8);
  modeButton(s.root, '2d').click(); modeButton(s.root, '3d').click(); assert.equal(s.views.length, 1);
  s.panel.destroy(); assert.equal(s.views[0].dead, 1);
});

test('UNKNOWN removes an earlier estimate and keeps all #709 reason texts (no invented point)', () => {
  const s = setup(); s.update(model({est_xy: [2,1], uncertainty_m: 1}));
  for (const [reason, text] of Object.entries(ESTIMATE_REASON_TEXT)) {
    const view = model({est_xy: 'UNKNOWN', uncertainty_m: 'UNKNOWN', reason}); s.update(view);
    assert.match(s.root.textContent, /估計位置 UNKNOWN/); assert.ok(s.root.textContent.includes(text));
    assert.equal(s.flatModels.at(-1).estimate.xy, null); assert.equal(view.topdown.estimate_marker, null);
  }
  s.update(model(null)); assert.match(s.root.textContent, /沒有系統估計/); s.panel.destroy();
});

test('asset rejection falls back to 2D with explicit missing-assets text', async () => {
  const s = setup(); s.update(model(null)); modeButton(s.root, '3d').click(); s.views[0].loading.reject(new Error('404')); await flush();
  assert.equal(s.root.dataset.mode, '2d'); assert.equal(modeButton(s.root, '2d').attrs['aria-pressed'], 'true');
  assert.match(s.root.textContent, /3D 資產不存在/); assert.equal(s.views[0].dead, 1); s.panel.destroy();
});

test('unsupported camera catalog and synchronous renderer failures stay in 2D', async () => {
  const s = setup(); s.update(model(null), 'B05', ['UNREGISTERED']); modeButton(s.root, '3d').click(); s.views[0].loading.resolve(); await flush();
  assert.equal(s.root.dataset.mode, '2d'); assert.match(s.root.textContent, /3D 資產不存在/); s.panel.destroy();
  const root = host(), panel = mountUiScene3dPanel({host: root, scene3dFactory: () => { throw new Error('WebGL unavailable'); }});
  panel.update({view: model(null), runKey: 'A4', render2d() {}}); modeButton(root, '3d').click();
  assert.equal(root.dataset.mode, '2d'); assert.match(root.textContent, /3D 資產不存在/); panel.destroy();
});

test('run change / teardown release instances; late ready callbacks cannot revive disposed views', async () => {
  const s = setup(); s.update(model(null)); modeButton(s.root, '3d').click();
  s.update(model(null), 'B4'); assert.equal(s.views[0].dead, 1); assert.equal(s.root.dataset.mode, '2d');
  s.views[0].loading.resolve(); await flush(); assert.equal(s.views[0].updates.length, 0);
  modeButton(s.root, '3d').click(); s.panel.destroy(); s.panel.destroy();
  s.views[1].loading.resolve(); await flush(); assert.equal(s.views[1].dead, 1); assert.equal(s.views[1].updates.length, 0);
  assert.equal(s.root.children.length, 0);
});

test('metric 2D estimate and uncertainty use one projection, not the active camera node', () => {
  const view = model({est_xy: [2,1], uncertainty_m: 0.8}), plan = floorPlan(view.topdown);
  assert.notDeepEqual(plan.estimate.xy, [plan.nodes[0].x, plan.nodes[0].y]);
  assert.ok(Math.abs(plan.estimate.radius - 0.8 * 80 / 4) < 1e-9); assert.ok(plan.estimate.xy.every(x => x > 0 && x < 100));
  const unknown = floorPlan(model({est_xy: 'UNKNOWN', reason: 'CALIBRATION_MISSING'}).topdown);
  assert.equal(unknown.estimate, null);
});

test('out-of-bounds estimate is not plotted or clamped; 2D summary says why without changing 3D coordinates', async () => {
  const s = setup(), view = model({est_xy: [20, 20], uncertainty_m: 1}); s.update(view);
  assert.equal(view.topdown.estimate_marker, null);
  assert.match(s.root.textContent, /估計位置超出圖面/);
  modeButton(s.root, '3d').click(); s.views[0].loading.resolve(); await flush();
  assert.deepEqual(s.views[0].updates.at(-1).estimate.xy, [20,20]);
  assert.doesNotMatch(s.root.textContent, /估計位置超出圖面/);
  s.panel.destroy();
});

test('schematic coordinates leave only estimate text and explain why there is no metric 2D point', () => {
  const s = setup(), view = buildCoreTrackingViewModel(response({est_xy: [2,1], uncertainty_m: 1}), {
    tUs: 5e6, runClockId: 'C', displayPositions: {CAM_A: [0,0]}});
  s.update(view);
  assert.equal(view.topdown.estimate_marker, null);
  assert.match(s.root.textContent, /沒有已校正鏡頭位置，2D 不畫估計點/);
  s.panel.destroy();
});

test('t=1 s NO_SIGHTING and unobserved states never claim tracking', () => {
  const view = buildCoreTrackingViewModel({status: 'NO_SIGHTING', as_of_us: 1e6, single_view: [], sightings: []}, {tUs: 1e6});
  assert.equal(scene3dStateText(view), '目前沒有觀測紀錄');
  for (const kind of ['UNKNOWN', 'PENDING', 'GAP', 'LOST']) assert.notEqual(scene3dStateText({singleView: {segmentKind: kind}}), '追蹤中');
  assert.equal(scene3dStateText({singleView: {segmentKind: 'ON_CAMERA'}}), '追蹤中');
});

test('default UI wiring stays inside its own panel and legacy bridge; cleanup covers run/page exit', () => {
  const shell = readFileSync(new URL('./ui-shell.mjs', import.meta.url), 'utf8');
  assert.match(shell, /mountUiScene3dPanel\(\{host: plan/); assert.match(shell, /scenePanel\?\.update/);
  assert.match(shell, /next !== 'case2'\) releasePlan\(\)/); assert.match(shell, /'pagehide', onPageHide/);
  assert.doesNotMatch(shell, /querySelector\(['"]#(q-|monitor-room|q1-slot|q2-slot|core-)/);
  const legacy = readFileSync(new URL('./core-tracking-view.mjs', import.meta.url), 'utf8');
  assert.match(legacy, /m3\.stateText/);
});


test('3D follows the latest system estimate without mutating the response', async () => {
  const s = setup(), raw = response({est_xy: [2,1], uncertainty_m: 0.8}), before = JSON.stringify(raw);
  s.update(buildCoreTrackingViewModel(raw, {tUs: 5e6, runClockId: 'C'})); modeButton(s.root, '3d').click(); s.views[0].loading.resolve(); await flush();
  s.update(model({est_xy: [3,2], uncertainty_m: 1.2}));
  assert.deepEqual(s.views[0].updates.at(-1).estimate.xy, [3,2]);
  s.update(model({est_xy: 'UNKNOWN', reason: 'GROUND_PROJECTION_UNDEFINED'}));
  assert.equal(s.views[0].updates.at(-1).estimate.xy, null);
  assert.equal(s.views[0].updates.at(-1).estimate.trail.length, 0);
  assert.equal(JSON.stringify(raw), before); s.panel.destroy();
});

test('a rejected old run cannot overwrite a newer run or its loading state', async () => {
  const s = setup(); s.update(model(null)); modeButton(s.root, '3d').click();
  s.update(model(null), 'B4'); modeButton(s.root, '3d').click();
  s.views[0].loading.reject(new Error('stale failure')); await flush();
  assert.equal(s.root.dataset.mode, '3d'); assert.doesNotMatch(s.root.textContent, /3D 資產不存在/);
  s.views[1].loading.resolve(); await flush(); assert.equal(s.views[1].updates.length, 1); s.panel.destroy();
});

test('a renderer update failure releases the instance and leaves the 2D panel usable', async () => {
  const s = setup(); s.update(model(null)); modeButton(s.root, '3d').click();
  s.views[0].update = () => { throw new Error('render failed'); };
  s.views[0].loading.resolve(); await flush();
  assert.equal(s.root.dataset.mode, '2d'); assert.equal(s.views[0].dead, 1);
  assert.match(s.root.textContent, /3D 資產不存在/); s.panel.destroy();
});


test('clock-only ticks update the HUD without rebuilding unchanged 3D geometry', async () => {
  const s = setup(), view = model({est_xy: [2,1], uncertainty_m: 0.8}); s.update(view);
  modeButton(s.root, '3d').click(); s.views[0].loading.resolve(); await flush();
  const count = s.views[0].updates.length;
  s.update({...view, currentTUs: 5.5e6});
  assert.equal(s.views[0].updates.length, count); assert.match(s.root.textContent, /t = 5.5 s/);
  s.panel.destroy();
});

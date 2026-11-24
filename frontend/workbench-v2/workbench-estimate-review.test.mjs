// #714 Opus coordinate/time decisions: pure models, no backend, service or assets.
import test from 'node:test';
import assert from 'node:assert/strict';
import {buildCoreTrackingViewModel, projectTopdown} from './core-search-track-model.mjs';
import {buildScene3dModel, readEstimate} from './scene3d-model.mjs';
import {floorPlan} from './ui-model.mjs';
import {createStore, initialState} from './store.mjs';

const cam = (id, status, xy_m) => ({camera_id: id, display_position: {status, xy_m}});
const graph = layout => ({layout, display_note: '示意圖，非實際座標', cameras: [
  cam('A', 'CALIBRATED_STATIC', [0, 0]), cam('B', 'CALIBRATED_STATIC', [4, 4]),
  cam('SKETCH', 'SCHEMATIC', [100, 100]), cam('UNKNOWN', 'UNKNOWN', [200, 200]),
  cam('BAD', 'CALIBRATED_STATIC', [NaN, 2]),
]});
const estimate = (extra = {}) => ({est_xy: [2, 1], uncertainty_m: 0.8,
  last_observed_us: 5e6, source_clock_id: 'C', ...extra});
const response = e => ({status: 'TRACKING', as_of_us: 6e6, single_view: [
  {kind: 'ON_CAMERA', camera_id: 'A', range_us: [0, 6e6]}], sightings: [], display_estimate: e});
const model = (e = estimate(), extra = {}) => buildCoreTrackingViewModel(response(e), {
  tUs: 5e6, cameraGraph: graph('NODE_GRAPH'), runClockId: 'C', ...extra});

for (const layout of ['NODE_GRAPH', 'METRIC_STATIC']) {
  test(`${layout}: only calibrated finite camera positions anchor a metric estimate; note stays verbatim`, () => {
    const m = model(estimate(), {cameraGraph: graph(layout), displayPositions: {SKETCH: [999, 999]}});
    assert.deepEqual(m.topdown.nodes.map(n => n.cameraId), ['A', 'B']);
    assert.deepEqual(m.topdown.estimate_marker.xy, [50, 70]);
    assert.equal(m.topdown.estimate_marker.radius, 16);
    assert.equal(m.topdown.display_note, '示意圖，非實際座標');
  });
}

test('+y is up for cameras, blind curve and estimate; all share the same fixed projection', () => {
  const topdown = {blind: {usable: true, curve_segments: [{points: [[0, 0], [4, 4]]}]}};
  const positions = {A: [0, 0], B: [4, 4]};
  const m = projectTopdown(topdown, positions, 'A', estimate({est_xy: [4, 4]}), {
    currentTUs: 5e6, runClockId: 'C', calibratedPositions: positions});
  assert.ok(m.nodes[1].y < m.nodes[0].y);
  assert.deepEqual(m.blind_curve.svgPoints, [[10, 90], [90, 10]]);
  assert.deepEqual(m.estimate_marker.xy, [m.nodes[1].x, m.nodes[1].y]);
});

test('estimate and radius never change camera/curve bounds; out-of-bounds points are omitted, not clamped', () => {
  const absent = model(null).topdown;
  const inside = model(estimate()).topdown;
  for (const xy of [[-1, 2], [5, 2], [2, -1], [2, 5]]) {
    const outside = model(estimate({est_xy: xy, uncertainty_m: 1000})).topdown;
    assert.deepEqual(outside.nodes, absent.nodes);
    assert.deepEqual(outside.blind_curve, inside.blind_curve);
    assert.equal(outside.estimate_marker, null);
    assert.equal(outside.estimate_display_reason, 'ESTIMATE_OUTSIDE_PLAN');
  }
  assert.deepEqual(inside.nodes, absent.nodes);
  assert.deepEqual(model(estimate({uncertainty_m: 1000})).topdown.nodes, inside.nodes);
});

test('a bare schematic coordinate map cannot anchor a metric point; estimate-only is never an available floor plan', () => {
  const m = model(estimate(), {cameraGraph: null, displayPositions: {A: [0, 0], B: [4, 4]}});
  assert.equal(m.topdown.estimate_marker, null);
  assert.equal(m.topdown.estimate_display_reason, 'CALIBRATED_CAMERA_POSITION_MISSING');
  const noPositions = model(estimate(), {cameraGraph: {layout: 'NODE_GRAPH', cameras: [cam('A', 'UNKNOWN', [0, 0])]}, displayPositions: {A: [0, 0]}});
  assert.equal(floorPlan(noPositions.topdown).available, false);
  assert.equal(floorPlan({nodes: [], estimate_marker: {xy: [50, 50]}}).available, false);
});

const invalid = [
  ['LAST_OBSERVED_US_INVALID', {last_observed_us: undefined}, {}],
  ['LAST_OBSERVED_US_INVALID', {last_observed_us: null}, {}],
  ['LAST_OBSERVED_US_INVALID', {last_observed_us: NaN}, {}],
  ['LAST_OBSERVED_US_INVALID', {last_observed_us: Infinity}, {}],
  ['LAST_OBSERVED_US_INVALID', {last_observed_us: -1}, {}],
  ['SOURCE_CLOCK_MISSING', {source_clock_id: undefined}, {}],
  ['SOURCE_CLOCK_MISMATCH', {source_clock_id: 'OTHER'}, {}],
  ['RUN_CLOCK_MISSING', {}, {runClockId: null}],
  ['ESTIMATE_IN_FUTURE', {}, {tUs: 1e6}],
];
test('time/clock invalidity clears 2D and shared new/legacy 3D point, trail and radius with one explicit reason', () => {
  for (const [reason, fields, options] of invalid) {
    const m = model(estimate({...fields, track: [{t_us: 0, est_xy: [0, 0]}]}), options);
    const shared = buildScene3dModel({view: m});
    assert.equal(m.topdown.est_xy, 'UNKNOWN', reason);
    assert.equal(m.topdown.uncertainty_m, 'UNKNOWN', reason);
    assert.equal(m.topdown.estimate_marker, null, reason);
    assert.equal(shared.estimate.status, 'UNKNOWN', reason);
    assert.equal(shared.estimate.reason, reason);
    assert.equal(shared.estimate.xy, null);
    assert.deepEqual(shared.estimate.trail, []);
    assert.deepEqual(shared.estimate.uncertaintyFan, []);
    assert.ok(shared.estimateText.includes(reason));
    assert.ok(shared.legend.some(s => s.includes(reason)));
  }
  for (const current of [null, NaN, Infinity]) assert.equal(readEstimate(estimate(), current, 'C').reason, 'CURRENT_TIME_INVALID');
});

test('tUs 1e6 / as_of_us 5e6 never draws the estimate at 5e6; exact observation time is permitted', () => {
  const raw = {...response(estimate()), as_of_us: 5e6};
  const early = buildCoreTrackingViewModel(raw, {tUs: 1e6, cameraGraph: graph('NODE_GRAPH'), runClockId: 'C'});
  assert.equal(early.topdown.estimate_marker, null);
  assert.equal(buildScene3dModel({view: early}).estimate.reason, 'ESTIMATE_IN_FUTURE');
  assert.deepEqual(model(estimate(), {tUs: 5e6}).topdown.estimate_marker.xy, [50, 70]);
});

test('store passes the active run clock on response, seek, layout and speed changes; reverse seek clears the point', () => {
  for (const clockFields of [{clock_mapping: {clock_id: 'C', source_duration_us: 6e6}}, {clock_id: 'C'}]) {
    const store = createStore(initialState({activeRun: {run_id: 'R', ...clockFields}, cameraGraph: graph('NODE_GRAPH'), tUs: 5e6}));
    store.dispatch({type: 'SET_CORE_TRACK_RESPONSE', response: response(estimate())});
    assert.ok(store.getState().coreTrackingView.topdown.estimate_marker);
    for (const action of [{type: 'SET_T_US', tUs: 5e6}, {type: 'SET_PLAYBACK_MODE', value: 'multi'}, {type: 'SET_SPEED', value: 2}]) {
      store.dispatch(action);
      assert.equal(store.getState().coreTrackingView.runClockId, 'C');
      assert.equal(buildScene3dModel({view: store.getState().coreTrackingView}).estimate.status, 'INFERRED');
    }
    store.dispatch({type: 'SET_T_US', tUs: 1e6});
    assert.equal(store.getState().coreTrackingView.topdown.estimate_marker, null);
    assert.equal(buildScene3dModel({view: store.getState().coreTrackingView}).estimate.reason, 'ESTIMATE_IN_FUTURE');
  }
});

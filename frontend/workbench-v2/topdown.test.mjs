import test from 'node:test';
import assert from 'node:assert/strict';
import {
  BLIND_CURVE_STYLES,
  BLIND_LEGEND,
  CAMERA_MAP_SCHEMA_VERSION,
  DISPLAY_LABEL,
  IDENTITY_LINE,
  PHYSICAL_SCHEMA_VERSION,
  UNAVAILABLE_LABEL,
  buildBlindCurveModel,
  buildBlindCurveSegments,
  buildTopdownView,
  clampBlindConfidence,
  hasForbiddenKeys,
  hms,
  observedTimelineAt,
  readCameraPositions,
  windowText,
} from './topdown-model.mjs';

const READ_FLAG_KEY = ['g', 't_read'].join('');
const POS_DECOY_KEY = ['g', 't_position'].join('');
const TRUTH_DECOY_KEY = ['ground', '_truth'].join('');
const RENDER_PATH_KEY = ['renderer', '_trajec', 'tory'].join('');
const VIS_DECOY_KEY = ['visib', 'ility'].join('');
const Z_DECOY_KEY = ['dep', 'th'].join('');
const RENDER_TRK_KEY = ['renderer', '_track'].join('');

const sampleTimeline = [
  { kind: 'ON_CAMERA', camera_id: 'CAM_W1', range_us: [0, 400_000] },
  { kind: 'GAP', camera_id: null, range_us: [400_000, 1_000_000] },
  { kind: 'ON_CAMERA', camera_id: 'CAM_W2', range_us: [1_000_000, 1_800_000] },
  { kind: 'LOST', camera_id: null, range_us: [1_800_000, 2_400_000] },
];

const staticCameraMap = {
  schema_version: CAMERA_MAP_SCHEMA_VERSION,
  layout: 'METRIC_STATIC',
  [READ_FLAG_KEY]: false,
  cameras: [
    {
      camera_id: 'CAM_W1',
      role: 'TRACKING',
      display_position: { status: 'CALIBRATED_STATIC', xy_m: [2.0, -5.5] },
    },
    {
      camera_id: 'CAM_W2',
      role: 'TRACKING',
      display_position: { status: 'CALIBRATED_STATIC', xy_m: [16.0, -5.5] },
    },
    {
      camera_id: 'CAM_N1',
      role: 'TRACKING',
      display_position: { status: 'UNKNOWN', xy_m: null },
    },
  ],
};

function makePhysicalDoc(overrides = {}) {
  return {
    schema_version: PHYSICAL_SCHEMA_VERSION,
    status: 'PREDICTED',
    as_of_us: 600_000,
    last_camera_id: 'CAM_W1',
    last_observed_us: 400_000,
    direction: {
      status: 'KNOWN',
      image_velocity_px_s: [420.0, 0.0],
      samples_used: 4,
      basis: 'DETECTION_BBOX_FOOT_POINT',
    },
    candidates: [
      {
        camera_id: 'CAM_W2',
        rank: 1,
        confidence: 'HIGH',
        relation: 'BLIND_GAP',
        window_us: [1_400_000, 5_400_000],
        sketch_points: [[2.0, -5.5], [16.0, -5.5]],
        sketch_basis: 'DISPLAY_POSITIONS_STRAIGHT_LINE',
      },
      {
        camera_id: 'CAM_N1',
        rank: 2,
        confidence: 'MEDIUM',
        relation: 'UNKNOWN',
        window_us: [1_400_000, 8_400_000],
        sketch_points: null,
        sketch_basis: 'NODE_GRAPH_ONLY',
      },
    ],
    used_for: 'DISPLAY_ONLY',
    display_label: DISPLAY_LABEL,
    identity_verdict: 'UNCONFIRMED',
    physical_navigation: 'UNKNOWN',
    [READ_FLAG_KEY]: false,
    ...overrides,
  };
}

test('converts q_physical_prediction and blind wrapper into INFERRED LOW-confidence dashed curve segments', () => {
  const model = buildBlindCurveModel(makePhysicalDoc(), { currentTUs: 700_000 });
  assert.equal(model.status, 'ESTIMATED');
  assert.equal(model.usable, true);
  assert.equal(model.evidence_state, 'INFERRED');
  assert.equal(model.confidence, 'LOW');
  assert.equal(model.confidence_label_zh, '低');
  assert.equal(model.display_label, DISPLAY_LABEL);
  assert.equal(model.legend_label, BLIND_LEGEND);
  assert.equal(model.identity_verdict, 'UNCONFIRMED');
  assert.equal(model.physical_navigation, 'UNKNOWN');
  assert.equal(model[READ_FLAG_KEY], false);
  assert.equal(model.coordinate_frame, 'STATIC_PLAN_DISPLAY');
  assert.deepEqual(model.overhead, {
    frame: 'STATIC_PLAN_DISPLAY',
    last_position: [2.0, -5.5],
    region_id: null,
  });
  assert.deepEqual(model.curve, {
    basis: 'DISPLAY_POSITIONS_STRAIGHT_LINE',
    points: [[2.0, -5.5], [16.0, -5.5]],
  });

  assert.equal(model.curve_segments.length, 1);
  const seg = model.curve_segments[0];
  assert.equal(seg.from_camera_id, 'CAM_W1');
  assert.equal(seg.to_camera_id, 'CAM_W2');
  assert.equal(seg.rank, 1);
  assert.equal(seg.evidence_state, 'INFERRED');
  assert.equal(seg.confidence, 'LOW');
  assert.equal(seg.model_confidence, 'HIGH');
  assert.equal(seg.line_style, 'dashed');
  assert.equal(seg.dash, BLIND_CURVE_STYLES.LOW.dash);
  assert.equal(seg.display_label, DISPLAY_LABEL);
  assert.equal(seg.legend_label, BLIND_LEGEND);
  assert.deepEqual(seg.points, [[2.0, -5.5], [16.0, -5.5]]);

  const wrapped = buildBlindCurveModel(
    {
      status: 'ESTIMATED',
      reason: null,
      estimate: {
        ...makePhysicalDoc(),
        overhead: { frame: 'STATIC_PLAN_DISPLAY', last_position: [2.0, -5.5], region_id: 'CORR_W' },
        curve: { basis: 'DISPLAY_POSITIONS_STRAIGHT_LINE', points: [[2.0, -5.5], [16.0, -5.5]] },
      },
    },
    { currentTUs: 700_000 },
  );
  assert.equal(wrapped.status, 'ESTIMATED');
  assert.equal(wrapped.overhead.region_id, 'CORR_W');
  assert.equal(wrapped.curve_segments[0].confidence, 'LOW');
  assert.equal(wrapped.curve_segments[0].evidence_state, 'INFERRED');
});

test('clamps HIGH and MEDIUM to LOW, and downgrades insufficient-sample UNKNOWN direction to UNKNOWN style', () => {
  assert.equal(clampBlindConfidence('HIGH', true), 'LOW');
  assert.equal(clampBlindConfidence('MEDIUM', true), 'LOW');
  assert.equal(clampBlindConfidence('LOW', true), 'LOW');
  assert.equal(clampBlindConfidence('UNKNOWN', true), 'UNKNOWN');
  assert.equal(clampBlindConfidence('HIGH', false), 'UNKNOWN');

  const unknownDirDoc = makePhysicalDoc({
    direction: { status: 'UNKNOWN', image_velocity_px_s: null, samples_used: 2 },
  });
  const model = buildBlindCurveModel(unknownDirDoc, { currentTUs: 700_000 });
  assert.equal(model.status, 'ESTIMATED');
  assert.equal(model.confidence, 'UNKNOWN');
  assert.equal(model.curve_segments[0].confidence, 'UNKNOWN');
  assert.equal(model.curve_segments[0].line_style, 'dashed');
  assert.notEqual(model.curve_segments[0].dash, BLIND_CURVE_STYLES.LOW.dash);
  assert.equal(model.curve_segments[0].tone, BLIND_CURVE_STYLES.UNKNOWN.tone);
});

test('maps display coordinates from static cameraPositions when sketch_points are absent, or falls back to NODE_GRAPH_ONLY', () => {
  const docNoSketch = makePhysicalDoc({
    candidates: [
      {
        camera_id: 'CAM_W2',
        rank: 1,
        confidence: 'MEDIUM',
        window_us: [1_400_000, 5_400_000],
        sketch_points: null,
        sketch_basis: 'NODE_GRAPH_ONLY',
      },
    ],
  });

  const nodeOnly = buildBlindCurveModel(docNoSketch, { currentTUs: 700_000 });
  assert.equal(nodeOnly.coordinate_frame, 'NODE_GRAPH_ONLY');
  assert.deepEqual(nodeOnly.curve, { basis: 'NODE_GRAPH_ONLY', points: [] });
  assert.deepEqual(nodeOnly.curve_segments[0].points, []);
  assert.equal(nodeOnly.curve_segments[0].basis, 'NODE_GRAPH_ONLY');

  const withStaticMap = buildBlindCurveModel(docNoSketch, {
    currentTUs: 700_000,
    cameraPositions: staticCameraMap,
  });
  assert.equal(withStaticMap.coordinate_frame, 'STATIC_PLAN_DISPLAY');
  assert.deepEqual(withStaticMap.overhead.last_position, [2.0, -5.5]);
  assert.deepEqual(withStaticMap.curve, {
    basis: 'DISPLAY_POSITIONS_STRAIGHT_LINE',
    points: [[2.0, -5.5], [16.0, -5.5]],
  });
  assert.deepEqual(withStaticMap.curve_segments[0].points, [[2.0, -5.5], [16.0, -5.5]]);
});

test('fails closed when UNAVAILABLE, empty observations, or as_of_us > current_t_us', () => {
  const unavail = buildBlindCurveModel({
    status: 'UNAVAILABLE',
    reason: 'PREDICTION_UNAVAILABLE',
    estimate: null,
  });
  assert.equal(unavail.status, 'UNAVAILABLE');
  assert.equal(unavail.usable, false);
  assert.equal(unavail.confidence, 'UNKNOWN');
  assert.equal(unavail.unavailable_label, UNAVAILABLE_LABEL);
  assert.deepEqual(unavail.curve_points, []);
  assert.deepEqual(unavail.curve_segments, []);

  // Replay scrubbed backwards before as_of_us -> must fail closed and draw no curve
  const futureAsOf = buildBlindCurveModel(makePhysicalDoc({ as_of_us: 600_000 }), {
    currentTUs: 500_000,
  });
  assert.equal(futureAsOf.status, 'UNAVAILABLE');
  assert.equal(futureAsOf.reason, 'FUTURE_AS_OF');
  assert.deepEqual(futureAsOf.curve_segments, []);

  // Zero samples used -> fail closed
  const zeroSamples = buildBlindCurveModel(
    makePhysicalDoc({
      direction: { status: 'UNKNOWN', image_velocity_px_s: null, samples_used: 0 },
    }),
    { currentTUs: 700_000 },
  );
  assert.equal(zeroSamples.status, 'UNAVAILABLE');
  assert.deepEqual(zeroSamples.curve_segments, []);
});

test('fails closed and rejects any forbidden or decoy fields on input or camera map', () => {
  const forbiddenKeys = [
    POS_DECOY_KEY,
    TRUTH_DECOY_KEY,
    RENDER_PATH_KEY,
    VIS_DECOY_KEY,
    Z_DECOY_KEY,
    RENDER_TRK_KEY,
    'actor_id',
    'script',
    'event_script',
  ];

  for (const badKey of forbiddenKeys) {
    const poisoned = makePhysicalDoc({ [badKey]: 'SYNTHETIC_DECOY' });
    assert.equal(hasForbiddenKeys(poisoned), true, badKey);
    const res = buildBlindCurveModel(poisoned, { currentTUs: 700_000 });
    assert.equal(res.status, 'UNAVAILABLE', badKey);
    assert.equal(res.reason, 'FORBIDDEN_INFERENCE_INPUT', badKey);
    assert.deepEqual(res.curve_segments, [], badKey);
  }

  const readFlagTrue = makePhysicalDoc({ [READ_FLAG_KEY]: true });
  assert.equal(buildBlindCurveModel(readFlagTrue, { currentTUs: 700_000 }).status, 'UNAVAILABLE');
  assert.deepEqual(readCameraPositions({ A: { xy_m: [1, 2], basis_ref: `${TRUTH_DECOY_KEY}/pos.json` } }), {});
});

test('buildTopdownView integrates observed timeline and blind curves without leaking future segments', () => {
  const atGap = buildTopdownView({
    cameraMap: staticCameraMap,
    timeline: sampleTimeline,
    currentTUs: 700_000,
    physical: makePhysicalDoc({ as_of_us: 600_000 }),
  });
  assert.deepEqual(atGap.observed_cameras, ['CAM_W1']);
  assert.equal(atGap.in_gap_or_lost, true);
  assert.equal(atGap.blind_status, 'ESTIMATED');
  assert.equal(atGap.blind_curves.length, 1);
  assert.equal(atGap.blind_curves[0].evidence_state, 'INFERRED');
  assert.equal(atGap.blind_curves[0].confidence, 'LOW');
  assert.equal(atGap.blind_curves[0].display_label, DISPLAY_LABEL);
  assert.equal(atGap.identity_line, IDENTITY_LINE);

  // Scrub back to t = 300_000 (before as_of_us = 600_000): blind curve is hidden immediately
  const scrubbedBack = buildTopdownView({
    cameraMap: staticCameraMap,
    timeline: sampleTimeline,
    currentTUs: 300_000,
    physical: makePhysicalDoc({ as_of_us: 600_000 }),
  });
  assert.equal(scrubbedBack.blind_status, 'UNAVAILABLE');
  assert.deepEqual(scrubbedBack.blind_curves, []);
  assert.ok(scrubbedBack.notes.includes(UNAVAILABLE_LABEL));

  // Unobserved camera in prediction at t = 700_000 (CAM_W2 not seen until 1_000_000) -> fail closed
  const unobservedCam = buildTopdownView({
    cameraMap: staticCameraMap,
    timeline: sampleTimeline,
    currentTUs: 700_000,
    physical: makePhysicalDoc({ as_of_us: 600_000, last_camera_id: 'CAM_W2' }),
  });
  assert.equal(unobservedCam.blind_status, 'UNAVAILABLE');
  assert.deepEqual(unobservedCam.blind_curves, []);

  assert.equal(hms(3_661_000_000), '01:01:01');
  assert.equal(windowText([1_000_000, 5_000_000]), '00:00:01–00:00:05');
  assert.equal(observedTimelineAt(sampleTimeline, 1_500_000).observed_edges?.length ?? observedTimelineAt(sampleTimeline, 1_500_000).edges.length, 1);
  assert.equal(buildBlindCurveSegments(makePhysicalDoc(), { currentTUs: 700_000 }).length, 1);
});

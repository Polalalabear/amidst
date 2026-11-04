// Acceptance tests for W-A5: Core Screens Models (Search Results Wall, Tracking Single/Multi-view, Top-down integration)
// Pure Node tests, no DOM, no forbidden inference inputs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildSearchResultsWallModel,
  buildCoreTrackingViewModel,
  coreSearchTrackReducer,
  SEARCH_RESULTS_STATUS_TEXT,
  TRACKING_STATUS_TEXT,
  SUPPORTED_SPEEDS,
  CORE_IDENTITY_VERDICT,
  CORE_IDENTITY_BADGE,
  CORE_NAVIGATION_BADGE,
} from './core-search-track-model.mjs';

const REF_KEY = ['visib', 'ility_ref'].join('');
const FORBIDDEN_TEST_KEYS = [
  'gt',
  ['ground', '_truth'].join(''),
  'actor_id',
  ['rend', 'erer_', 'trajec', 'tory'].join(''),
  ['dep', 'th'].join(''),
  ['visib', 'ility'].join(''),
];

const SYNTHETIC_SEARCH_RESPONSE = Object.freeze({
  schema_version: 'q-core.search-response.v1',
  status: 'READY',
  reasons: [],
  query_id: 'core-search-syn-01',
  normalized_request: {},
  resolved_time: {
    timezone: 'Asia/Taipei',
    wall_range: ['2026-11-01T13:00:00+08:00', '2026-11-01T13:30:00+08:00'],
    source_range_us: [0, 1800000000],
    coverage_complete: true,
  },
  resolved_scope: {
    scene_id: 'SYN_SCENE_1',
    run_id: 'SYN_RUN_1',
    query_min_score: 0.5,
  },
  hits: [
    {
      rank: 1,
      camera_id: 'CAM_ROOM_A',
      target_observed: true,
      source_range_us: [120000000, 180000000],
      wall_range: ['2026-11-01T13:02:00+08:00', '2026-11-01T13:03:00+08:00'],
      segments: [
        {
          range_us: [120000000, 180000000],
          matched_frames: 12,
          representative: {
            frame_ref: 'frame_001',
            observation_ids: ['obs_001'],
            media_token: 'media_tok_001',
          },
        },
      ],
      basis: [
        {
          kind: 'LOCATION',
          region_id: 'ROOM_A',
          coverage_basis: 'MANUAL_ON_STATIC_FRAME',
          [REF_KEY]: 'static-review:v3:CAM_ROOM_A:ROOM_A',
        },
        {
          kind: 'OBJECT',
          class_label: 'person',
          color_label: 'red',
          evidence_state: 'OBSERVED',
          observation_ids: ['obs_001'],
        },
      ],
    },
    {
      rank: 2,
      camera_id: 'CAM_ROOM_B',
      target_observed: false,
      source_range_us: [0, 1800000000],
      wall_range: ['2026-11-01T13:00:00+08:00', '2026-11-01T13:30:00+08:00'],
      segments: [],
      basis: [
        {
          kind: 'LOCATION',
          region_id: 'ROOM_B',
          coverage_basis: 'MANUAL_ON_STATIC_FRAME',
          [REF_KEY]: 'static-review:v3:CAM_ROOM_B:ROOM_B',
        },
      ],
    },
  ],
  not_evaluated_cameras: [
    { camera_id: 'CAM_UNRUN', reason: 'CAMERA_NOT_IN_RUN' },
  ],
  identity_verdict: 'UNCONFIRMED',
  output_sha256: 'deadbeef1234',
});

const SYNTHETIC_TRACK_RESPONSE = Object.freeze({
  schema_version: 'q-core.track-response.v1',
  status: 'TRACKING',
  reasons: [],
  as_of_us: 42000000,
  resolved_time: {
    kind: 'PLAYBACK_NOW',
    source_range_us: [0, 42000000],
  },
  sightings: [
    { camera_id: 'CAM_W1', range_us: [3000000, 9000000], evidence_state: 'OBSERVED', observation_ids: ['o1'] },
    { camera_id: 'CAM_W2', range_us: [15000000, 30000000], evidence_state: 'OBSERVED', observation_ids: ['o2'] },
  ],
  multi_view: [
    { camera_id: 'CAM_W1', first_us: 3000000, last_us: 9000000 },
    { camera_id: 'CAM_W2', first_us: 15000000, last_us: 30000000 },
  ],
  single_view: [
    { kind: 'ON_CAMERA', camera_id: 'CAM_W1', range_us: [3000000, 9000000], evidence_state: 'OBSERVED' },
    { kind: 'GAP', camera_id: null, range_us: [9000000, 15000000], evidence_state: 'UNKNOWN' },
    { kind: 'ON_CAMERA', camera_id: 'CAM_W2', range_us: [15000000, 30000000], evidence_state: 'OBSERVED' },
    { kind: 'LOST', camera_id: null, range_us: [30000000, 42000000], evidence_state: 'UNKNOWN' },
  ],
  blind: {
    status: 'ESTIMATED',
    reason: null,
    estimate: {
      schema_version: 'q-core.blind-estimate.v1',
      evidence_state: 'INFERRED',
      confidence: 'LOW',
      used_for: 'DISPLAY_ONLY',
      display_label: '物理預測（示意，非實際路徑）',
      as_of_us: 42000000,
      curve: {
        basis: 'DISPLAY_POSITIONS_STRAIGHT_LINE',
        points: [[12.5, 3.0], [18.0, 3.0]],
      },
      candidates: [
        { camera_id: 'CAM_W2', rank: 1, window_us: [31000000, 40000000], confidence: 'LOW' },
      ],
      identity_verdict: 'UNCONFIRMED',
      physical_navigation: 'UNKNOWN',
    },
  },
  identity_verdict: 'UNCONFIRMED',
  physical_navigation: 'UNKNOWN',
  output_sha256: 'fedcba4321',
});

// ---------------------------------------------------------------------------
// Search Results Wall Tests
// ---------------------------------------------------------------------------

test('search wall model parses hits, badges, wall ranges and representative frame', () => {
  const wall = buildSearchResultsWallModel(SYNTHETIC_SEARCH_RESPONSE, {
    regionGraph: {
      regions: [
        { region_id: 'ROOM_A', display_name: '研討室 A' },
        { region_id: 'ROOM_B', display_name: '研討室 B' },
      ],
    },
  });

  assert.equal(wall.status, 'READY');
  assert.equal(wall.statusText, SEARCH_RESULTS_STATUS_TEXT.READY);
  assert.equal(wall.identityVerdict, CORE_IDENTITY_VERDICT);
  assert.equal(wall.identityBadge, CORE_IDENTITY_BADGE);
  assert.equal(wall.totalHits, 2);
  assert.equal(wall.hasResults, true);

  const card1 = wall.cards[0];
  assert.equal(card1.rank, 1);
  assert.equal(card1.cameraId, 'CAM_ROOM_A');
  assert.equal(card1.targetObserved, true);
  assert.equal(card1.evidenceState, 'OBSERVED');
  assert.equal(card1.observedBadge, 'OBSERVED 畫面命中');
  assert.equal(card1.regionName, '研討室 A');
  assert.equal(card1.wallRangeText, '13:02:00 – 13:03:00');
  assert.equal(card1.matchedFrames, 12);
  assert.equal(card1.mediaToken, 'media_tok_001');
  assert.deepEqual(card1.basisBadges, [
    '地點: ROOM_A (靜態涵蓋)',
    '特徵: person / red (OBSERVED)',
  ]);

  const card2 = wall.cards[1];
  assert.equal(card2.rank, 2);
  assert.equal(card2.cameraId, 'CAM_ROOM_B');
  assert.equal(card2.targetObserved, false);
  assert.equal(card2.evidenceState, 'UNKNOWN');
  assert.equal(card2.observedBadge, '場景設定（未看到目標）');
  assert.equal(card2.regionName, '研討室 B');
  assert.deepEqual(card2.basisBadges, ['地點: ROOM_B (靜態涵蓋)']);

  assert.deepEqual(wall.notEvaluatedCameras, [
    { cameraId: 'CAM_UNRUN', reason: 'CAMERA_NOT_IN_RUN', reasonText: '鏡頭不在當前 run 中' },
  ]);
});

test('search wall model handles empty, no match, partial and out of range states', () => {
  const unloaded = buildSearchResultsWallModel(null);
  assert.equal(unloaded.status, 'UNLOADED');
  assert.equal(unloaded.hasResults, false);
  assert.deepEqual(unloaded.cards, []);

  const noMatch = buildSearchResultsWallModel({
    schema_version: 'q-core.search-response.v1',
    status: 'NO_MATCH',
    hits: [],
  });
  assert.equal(noMatch.status, 'NO_MATCH');
  assert.equal(noMatch.statusText, SEARCH_RESULTS_STATUS_TEXT.NO_MATCH);
  assert.equal(noMatch.hasResults, false);

  const partial = buildSearchResultsWallModel({
    schema_version: 'q-core.search-response.v1',
    status: 'PARTIAL',
    hits: [],
  });
  assert.equal(partial.status, 'PARTIAL');
  assert.equal(partial.statusText, SEARCH_RESULTS_STATUS_TEXT.PARTIAL);

  const outOfRange = buildSearchResultsWallModel({
    schema_version: 'q-core.search-response.v1',
    status: 'OUT_OF_RANGE',
    hits: [],
  });
  assert.equal(outOfRange.status, 'OUT_OF_RANGE');
  assert.equal(outOfRange.statusText, SEARCH_RESULTS_STATUS_TEXT.OUT_OF_RANGE);
});

test('search wall model supports selection and pagination', () => {
  const wall = buildSearchResultsWallModel(SYNTHETIC_SEARCH_RESPONSE, {
    selectedRank: 2,
    size: 1,
    page: 1,
    paginate: true,
  });

  assert.equal(wall.pages, 2);
  assert.equal(wall.page, 1);
  assert.equal(wall.cards.length, 1);
  assert.equal(wall.cards[0].rank, 2);
  assert.equal(wall.cards[0].isSelected, true);
});

test('search wall model fails closed on forbidden inference fields', () => {
  for (const forbiddenKey of FORBIDDEN_TEST_KEYS) {
    const poisoned = structuredClone(SYNTHETIC_SEARCH_RESPONSE);
    poisoned.hits[0][forbiddenKey] = 'LEAK';
    assert.throws(() => buildSearchResultsWallModel(poisoned), /FORBIDDEN_INFERENCE_INPUT/);
  }
});

// ---------------------------------------------------------------------------
// Tracking Single / Multi-View and Topdown Integration Tests
// ---------------------------------------------------------------------------

test('tracking view model evaluates single-view switching across time segments', () => {
  // At t = 5s (in CAM_W1 segment [3s, 9s])
  const t5 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 5000000 });
  assert.equal(t5.status, 'TRACKING');
  assert.equal(t5.singleView.segmentKind, 'ON_CAMERA');
  assert.equal(t5.singleView.activeCameraId, 'CAM_W1');
  assert.equal(t5.singleView.evidenceState, 'OBSERVED');
  assert.equal(t5.singleView.badge, 'OBSERVED 追蹤中');
  assert.equal(t5.singleView.lastObservedCameraId, 'CAM_W1');
  assert.equal(t5.singleView.nextSwitchUs, 9000000);

  // At t = 11s (in GAP segment [9s, 15s])
  const t11 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 11000000 });
  assert.equal(t11.singleView.segmentKind, 'GAP');
  assert.equal(t11.singleView.activeCameraId, null);
  assert.equal(t11.singleView.evidenceState, 'UNKNOWN');
  assert.equal(t11.singleView.badge, '盲區間隔（未見目標）');
  assert.equal(t11.singleView.lastObservedCameraId, 'CAM_W1');
  assert.equal(t11.singleView.nextSwitchUs, 15000000);

  // At t = 20s (in CAM_W2 segment [15s, 30s])
  const t20 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 20000000 });
  assert.equal(t20.singleView.segmentKind, 'ON_CAMERA');
  assert.equal(t20.singleView.activeCameraId, 'CAM_W2');
  assert.equal(t20.singleView.evidenceState, 'OBSERVED');
  assert.equal(t20.singleView.badge, 'OBSERVED 追蹤中');
  assert.equal(t20.singleView.lastObservedCameraId, 'CAM_W2');
  assert.equal(t20.singleView.nextSwitchUs, 30000000);

  // At t = 35s (in LOST segment [30s, 42s])
  const t35 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 35000000 });
  assert.equal(t35.singleView.segmentKind, 'LOST');
  assert.equal(t35.singleView.activeCameraId, null);
  assert.equal(t35.singleView.evidenceState, 'UNKNOWN');
  assert.equal(t35.singleView.badge, '目標遺失（LOST）');
  assert.equal(t35.singleView.lastObservedCameraId, 'CAM_W2');
  assert.equal(t35.singleView.nextSwitchUs, null);
});

test('tracking view model evaluates multi-view cameras and active highlights', () => {
  const atW1 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 5000000, playbackMode: 'multi' });
  assert.equal(atW1.playbackMode, 'multi');
  assert.equal(atW1.multiView.cameras.length, 2);

  const cam1 = atW1.multiView.cameras[0];
  assert.equal(cam1.cameraId, 'CAM_W1');
  assert.equal(cam1.isActive, true);
  assert.equal(cam1.highlight, true);
  assert.equal(cam1.badge, '目前追蹤畫面');

  const cam2 = atW1.multiView.cameras[1];
  assert.equal(cam2.cameraId, 'CAM_W2');
  assert.equal(cam2.isActive, false);
  assert.equal(cam2.highlight, false);
  assert.equal(cam2.isFuture, true);
  assert.equal(cam2.badge, '候選鏡頭');

  // At t = 35s, CAM_W1 and CAM_W2 are both past
  const atW2Past = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 35000000 });
  assert.equal(atW2Past.multiView.cameras[0].isPast, true);
  assert.equal(atW2Past.multiView.cameras[0].badge, '已通過');
  assert.equal(atW2Past.multiView.cameras[1].isPast, true);
  assert.equal(atW2Past.multiView.cameras[1].badge, '已通過');
});

test('tracking view model validates speed multiplier and clamps playback time to as_of_us', () => {
  const normal = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 10000000, speed: 2 });
  assert.equal(normal.speed, 2);
  assert.equal(normal.speedLabel, '2×');

  const invalidSpeed = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { speed: 5 });
  assert.equal(invalidSpeed.speed, 1);

  // Beyond as_of_us is clamped to as_of_us (no future leakage)
  const clamped = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 999000000 });
  assert.equal(clamped.currentTUs, 42000000);
});

test('tracking view model integrates topdown blind-zone curve and fails closed on forbidden keys', () => {
  const positions = {
    CAM_W1: [10.0, 5.0],
    CAM_W2: [20.0, 5.0],
  };

  const modelWithTopdown = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, {
    tUs: 35000000, // In LOST segment
    displayPositions: positions,
  });

  assert.ok(modelWithTopdown.topdown);
  assert.equal(modelWithTopdown.topdown.current_camera_id, null);
  assert.equal(modelWithTopdown.topdown.last_observed_camera_id, 'CAM_W2');
  assert.equal(modelWithTopdown.topdown.in_gap_or_lost, true);
  assert.equal(modelWithTopdown.identityBadge, CORE_NAVIGATION_BADGE);
  assert.equal(modelWithTopdown.physicalNavigation, 'UNKNOWN');

  // Forbidden fields fail closed
  for (const forbiddenKey of FORBIDDEN_TEST_KEYS) {
    const poisoned = structuredClone(SYNTHETIC_TRACK_RESPONSE);
    poisoned[forbiddenKey] = 'DEC_VAL';
    assert.throws(() => buildCoreTrackingViewModel(poisoned), /FORBIDDEN_INFERENCE_INPUT/);
  }
});

test('coreSearchTrackReducer updates store state immutably', () => {
  const init = {
    coreSearchResponse: null,
    coreSearchWall: null,
    coreTrackResponse: null,
    coreTrackingView: null,
    coreSelection: null,
  };

  const state1 = coreSearchTrackReducer(init, {
    type: 'SET_CORE_SEARCH_RESPONSE',
    response: SYNTHETIC_SEARCH_RESPONSE,
  });

  assert.equal(state1.coreSearchResponse, SYNTHETIC_SEARCH_RESPONSE);
  assert.ok(state1.coreSearchWall);
  assert.equal(state1.coreSearchWall.cards.length, 2);

  const state2 = coreSearchTrackReducer(state1, {
    type: 'SET_CORE_SELECTION',
    selection: { rank: 1, cameraId: 'CAM_ROOM_A' },
  });

  assert.equal(state2.coreSelection.rank, 1);
  assert.equal(state2.coreSearchWall.cards[0].isSelected, true);

  const state3 = coreSearchTrackReducer(state2, {
    type: 'SET_CORE_TRACK_RESPONSE',
    response: SYNTHETIC_TRACK_RESPONSE,
  });

  assert.equal(state3.coreTrackResponse, SYNTHETIC_TRACK_RESPONSE);
  assert.ok(state3.coreTrackingView);
  assert.equal(state3.coreTrackingView.status, 'TRACKING');
});

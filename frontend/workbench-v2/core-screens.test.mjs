// Acceptance tests for W-A5: Core Screens Models (Search Results Wall, Tracking Single/Multi-view, Top-down integration)
// Pure Node tests, no DOM, no forbidden inference inputs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createQApi} from './q-api.mjs';
import {contentHash} from './q-validate.mjs';
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
import { mountCoreSearchWallView } from './core-search-wall-view.mjs';
import { mountCoreTrackingView } from './core-tracking-view.mjs';
import { mountCoreScreens } from './core-screens-view.mjs';
import { createStore, initialState } from './store.mjs';
import {
  bootstrap,
  produceCoreSearchResponse,
  produceCoreTrackResponse,
  isCoreSearchRequest,
  isCoreTrackRequest,
} from './app.mjs';
import {
  createSyntheticFrameDataUri,
  resolveCardImageSrc,
  resolveFrameImageSrc,
  createBoundMediaResolver,
} from './core-media.mjs';

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

// ---------------------------------------------------------------------------
// DOM Rendering & Interaction Tests for W-A5
// ---------------------------------------------------------------------------

class MockElement {
  constructor(tag, cls = '') {
    this.tagName = tag.toUpperCase();
    this.tag = tag;
    this._className = '';
    this.classList = {
      _classes: new Set(),
      add: (...classes) => { for (const c of classes) this.classList._classes.add(c); this._className = [...this.classList._classes].join(' '); },
      remove: (...classes) => { for (const c of classes) this.classList._classes.delete(c); this._className = [...this.classList._classes].join(' '); },
      contains: (c) => this.classList._classes.has(c),
      toggle: (c, on) => { on ? this.classList.add(c) : this.classList.remove(c); },
    };
    if (cls) this.className = cls;
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this.min = '0';
    this.max = '0';
    this._value = undefined;
    this._textContent = undefined;
  }
  before(...nodes) {
    if (!this.parentElement) return;
    const idx = this.parentElement.children.indexOf(this);
    if (idx >= 0) {
      this.parentElement.children.splice(idx, 0, ...nodes);
      for (const n of nodes) {
        if (n && typeof n === 'object') n.parentElement = this.parentElement;
      }
    }
  }
  after(...nodes) {
    if (!this.parentElement) return;
    const idx = this.parentElement.children.indexOf(this);
    if (idx >= 0) {
      this.parentElement.children.splice(idx + 1, 0, ...nodes);
      for (const n of nodes) {
        if (n && typeof n === 'object') n.parentElement = this.parentElement;
      }
    }
  }
  get value() { return this._value ?? this.options?.[0]?.value ?? ''; }
  set value(v) { this._value = String(v); }
  get options() { return this.children.filter(c => c.tag?.toLowerCase() === 'option'); }
  get textContent() {
    if (this._textContent !== undefined) return this._textContent;
    if (this.children.length === 0) return '';
    return this.children.map(c => c.textContent ?? '').join('');
  }
  set textContent(val) {
    this._textContent = val;
    if (val !== undefined && this.children.length > 0) {
      this.children = [];
    }
  }
  get className() { return this._className; }
  set className(val) {
    this._className = val ?? '';
    this.classList._classes = new Set(this._className.split(' ').filter(Boolean));
  }
  append(...children) {
    if (children.length > 0) this._textContent = undefined;
    for (const c of children) {
      if (typeof c === 'string') {
        const textNode = new MockElement('#text');
        textNode.textContent = c;
        this.children.push(textNode);
      } else if (c) {
        c.parentElement = this;
        this.children.push(c);
      }
    }
  }
  replaceChildren(...children) {
    this.children = [];
    this.append(...children);
  }
  remove() {
    if (this.parentElement) {
      this.parentElement.children = this.parentElement.children.filter(c => c !== this);
      this.parentElement = null;
    }
  }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] ?? null; }
  removeAttribute(k) { delete this.attributes[k]; }
  addEventListener(event, fn) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(fn);
  }
  removeEventListener(event, fn) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(l => l !== fn);
    }
  }
  dispatchEvent(event) {
    const list = this.listeners[event.type] ?? [];
    for (const fn of list) fn(event);
  }
  click() {
    this.dispatchEvent({ type: 'click', target: this });
  }
  querySelector(selector) {
    const parts = selector.trim().split(/\s+/).filter(Boolean);
    if (parts.length > 1) {
      let current = this;
      for (let i = 0; i < parts.length; i++) {
        if (!current) return null;
        current = current.querySelector(parts[i]);
      }
      return current;
    }
    const sel = selector.trim();
    if (sel.startsWith('#')) {
      const id = sel.slice(1);
      if (this.getAttribute('id') === id) return this;
      const res = queryAll(this, n => n.getAttribute('id') === id);
      return res[0] ?? null;
    }
    if (sel.startsWith('.')) {
      const cls = sel.slice(1);
      const res = queryAll(this, n => n.classList?.contains?.(cls));
      return res[0] ?? null;
    }
    const attrMatch = sel.match(/^([a-zA-Z0-9_-]+)?\[([^\]]+)\]$/);
    if (attrMatch) {
      const tag = attrMatch[1]?.toLowerCase();
      const inner = attrMatch[2];
      const eq = inner.indexOf('=');
      if (eq >= 0) {
        const k = inner.slice(0, eq).trim();
        const v = inner.slice(eq + 1).replace(/^['"]|['"]$/g, '').trim();
        const res = queryAll(this, n => {
          if (tag && n.tag?.toLowerCase() !== tag) return false;
          if (k.startsWith('data-')) {
            const dataKey = k.slice(5).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
            return n.dataset?.[dataKey] === v || n.dataset?.[k.slice(5)] === v || n.attributes?.[k] === v;
          }
          return n.getAttribute?.(k) === v;
        });
        return res[0] ?? null;
      }
      const k = inner.trim();
      const res = queryAll(this, n => {
        if (tag && n.tag?.toLowerCase() !== tag) return false;
        return n.getAttribute?.(k) !== null || (k.startsWith('data-') && Object.hasOwn(n.dataset ?? {}, k.slice(5)));
      });
      return res[0] ?? null;
    }
    const res = queryAll(this, n => n.tag?.toLowerCase() === sel.toLowerCase());
    return res[0] ?? null;
  }
  querySelectorAll(selector) {
    const parts = selector.trim().split(/\s+/).filter(Boolean);
    if (parts.length > 1) {
      let currentNodes = [this];
      for (const part of parts) {
        const nextNodes = [];
        for (const node of currentNodes) {
          nextNodes.push(...node.querySelectorAll(part));
        }
        currentNodes = nextNodes;
      }
      return currentNodes;
    }
    const sel = selector.trim();
    if (sel.startsWith('#')) {
      const id = sel.slice(1);
      return queryAll(this, n => n.getAttribute('id') === id);
    }
    if (sel.startsWith('.')) {
      const cls = sel.slice(1);
      return queryAll(this, n => n.classList?.contains?.(cls));
    }
    const attrMatch = sel.match(/^([a-zA-Z0-9_-]+)?\[([^\]]+)\]$/);
    if (attrMatch) {
      const tag = attrMatch[1]?.toLowerCase();
      const inner = attrMatch[2];
      const eq = inner.indexOf('=');
      if (eq >= 0) {
        const k = inner.slice(0, eq).trim();
        const v = inner.slice(eq + 1).replace(/^['"]|['"]$/g, '').trim();
        return queryAll(this, n => {
          if (tag && n.tag?.toLowerCase() !== tag) return false;
          if (k.startsWith('data-')) {
            const dataKey = k.slice(5).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
            return n.dataset?.[dataKey] === v || n.dataset?.[k.slice(5)] === v || n.attributes?.[k] === v;
          }
          return n.getAttribute?.(k) === v;
        });
      }
      const k = inner.trim();
      return queryAll(this, n => {
        if (tag && n.tag?.toLowerCase() !== tag) return false;
        return n.getAttribute?.(k) !== null || (k.startsWith('data-') && Object.hasOwn(n.dataset ?? {}, k.slice(5)));
      });
    }
    return queryAll(this, n => n.tag?.toLowerCase() === sel.toLowerCase());
  }
}

function queryAll(root, predicate, acc = []) {
  if (!root) return acc;
  if (predicate(root)) acc.push(root);
  for (const child of root.children ?? []) {
    queryAll(child, predicate, acc);
  }
  return acc;
}

function findByClass(root, cls) {
  return queryAll(root, n => (n.className ?? '').split(' ').includes(cls));
}

function findByTag(root, tag) {
  return queryAll(root, n => n.tag?.toLowerCase() === tag.toLowerCase());
}

function findByData(root, key, val) {
  return queryAll(root, n => val === undefined ? Object.hasOwn(n.dataset ?? {}, key) : n.dataset?.[key] === String(val));
}

const savedDoc = globalThis.document;
const savedRaf = globalThis.requestAnimationFrame;
const savedCaf = globalThis.cancelAnimationFrame;
function setupDoc(rootEl = null) {
  const doc = new MockElement('#document');
  doc.createElement = (tag) => new MockElement(tag);
  doc.createElementNS = (ns, tag) => new MockElement(tag);
  doc.querySelector = (sel) => (rootEl ? rootEl.querySelector(sel) : null);
  doc.querySelectorAll = (sel) => (rootEl ? rootEl.querySelectorAll(sel) : []);
  doc.body = rootEl ?? new MockElement('body');
  globalThis.document = doc;
  let rafId = 0;
  globalThis.requestAnimationFrame = (fn) => ++rafId;
  globalThis.cancelAnimationFrame = (id) => {};
}
function tearDownDoc() {
  if (savedDoc) globalThis.document = savedDoc;
  else delete globalThis.document;
  if (savedRaf) globalThis.requestAnimationFrame = savedRaf;
  else delete globalThis.requestAnimationFrame;
  if (savedCaf) globalThis.cancelAnimationFrame = savedCaf;
  else delete globalThis.cancelAnimationFrame;
}

test('DOM: search result wall view renders header, hit cards, basis tags, and handles card selection', () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const model = buildSearchResultsWallModel(SYNTHETIC_SEARCH_RESPONSE, {
      regionGraph: {
        regions: [
          { region_id: 'ROOM_A', display_name: '研討室 A' },
          { region_id: 'ROOM_B', display_name: '研討室 B' },
        ],
      },
    });

    let selected = null;
    const view = mountCoreSearchWallView({
      container: host,
      onSelectCard: (card) => { selected = card; },
    });
    view.update(model);

    // Header verification
    const badge = findByClass(host, 'q-core-identity-badge')[0];
    assert.ok(badge);
    assert.equal(badge.textContent, CORE_IDENTITY_BADGE);

    const rankingNote = findByClass(host, 'q-core-ranking-note')[0];
    assert.ok(rankingNote);
    assert.equal(rankingNote.textContent, model.rankingNote);

    // Cards verification
    const cards = findByClass(host, 'q-core-card');
    assert.equal(cards.length, 2);

    // Card 1: OBSERVED
    const card1 = cards[0];
    assert.equal(card1.dataset.cameraId, 'CAM_ROOM_A');
    assert.equal(card1.dataset.rank, '1');
    assert.equal(card1.dataset.observed, 'true');
    const obsBadge1 = findByClass(card1, 'q-core-observed-badge')[0];
    assert.equal(obsBadge1.textContent, 'OBSERVED 畫面命中');
    const basisTags = findByClass(card1, 'q-core-basis-badge');
    assert.ok(basisTags.length >= 2);
    assert.ok(basisTags[0].textContent.includes('ROOM_A'));

    // Card 2: static coverage
    const card2 = cards[1];
    assert.equal(card2.dataset.cameraId, 'CAM_ROOM_B');
    assert.equal(card2.dataset.rank, '2');
    assert.equal(card2.dataset.observed, 'false');
    const obsBadge2 = findByClass(card2, 'q-core-observed-badge')[0];
    assert.equal(obsBadge2.textContent, '場景設定（未看到目標）');

    // Selection interaction
    card1.click();
    assert.ok(selected);
    assert.equal(selected.cameraId, 'CAM_ROOM_A');
    assert.equal(selected.rank, 1);

    view.destroy();
    assert.equal(host.children.length, 0);
  } finally {
    tearDownDoc();
  }
});

test('DOM: search result wall view renders pagination and not-evaluated cameras', () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const model = buildSearchResultsWallModel(SYNTHETIC_SEARCH_RESPONSE, {
      size: 1,
      page: 0,
      paginate: true,
    });

    const view = mountCoreSearchWallView({ container: host, synthetic: true });
    view.update(model);

    // Pagination controls
    const pag = findByClass(host, 'q-core-pagination')[0];
    assert.ok(pag);
    const indicator = findByClass(pag, 'q-core-page-indicator')[0];
    assert.equal(indicator.textContent, '1 / 2');

    // Not evaluated cameras
    const notEval = findByClass(host, 'q-core-not-evaluated')[0];
    assert.ok(notEval);
    const notEvalItems = findByClass(notEval, 'q-core-not-eval-item');
    assert.equal(notEvalItems.length, 1);
    assert.ok(notEvalItems[0].textContent.includes('CAM_UNRUN'));
    assert.ok(notEvalItems[0].textContent.includes('鏡頭不在當前 run 中'));

    view.destroy();
  } finally {
    tearDownDoc();
  }
});

test('DOM: search result wall view renders empty / NO_MATCH state', () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const noMatchResponse = {
      schema_version: 'q-core.search-response.v1',
      status: 'NO_MATCH',
      hits: [],
      identity_verdict: 'UNCONFIRMED',
    };
    const model = buildSearchResultsWallModel(noMatchResponse);

    const view = mountCoreSearchWallView({ container: host });
    view.update(model);

    const cards = findByClass(host, 'q-core-card');
    assert.equal(cards.length, 0);
    const emptyMsg = findByClass(host, 'q-core-empty-message')[0];
    assert.ok(emptyMsg);
    assert.equal(emptyMsg.textContent, SEARCH_RESULTS_STATUS_TEXT.NO_MATCH);

    view.destroy();
  } finally {
    tearDownDoc();
  }
});

test('DOM: tracking single-view renders active camera, ON_CAMERA / GAP / LOST states, and transitions', () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const view = mountCoreTrackingView({ container: host });

    // 1. At t = 5s (ON_CAMERA CAM_W1)
    const m1 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 5000000 });
    view.update(m1);

    const activeCam = findByClass(host, 'q-core-active-cam-id')[0];
    assert.equal(activeCam.textContent, 'CAM_W1');
    const badge1 = findByClass(host, 'q-core-segment-badge')[0];
    assert.equal(badge1.textContent, 'OBSERVED 追蹤中');
    assert.equal(badge1.dataset.kind, 'ON_CAMERA');
    const nextSwitch = findByClass(host, 'q-core-next-switch')[0];
    assert.ok(nextSwitch);
    assert.ok(nextSwitch.textContent.includes('9.00 s'));

    // Transitions drawer
    const transList = findByClass(host, 'q-core-trans-list')[0];
    assert.ok(transList);
    const transItems = findByClass(transList, 'q-core-trans-item');
    assert.equal(transItems.length, 3);

    // 2. At t = 12s (GAP)
    const m2 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 12000000 });
    view.update(m2);
    const badge2 = findByClass(host, 'q-core-segment-badge')[0];
    assert.equal(badge2.textContent, '盲區間隔（未見目標）');
    assert.equal(badge2.dataset.kind, 'GAP');
    const frame2 = findByClass(host, 'q-core-frame-display')[0];
    assert.ok(frame2.textContent.includes('CAM_W1'));

    // 3. At t = 35s (LOST)
    const m3 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 35000000 });
    view.update(m3);
    const badge3 = findByClass(host, 'q-core-segment-badge')[0];
    assert.equal(badge3.textContent, '目標遺失（LOST）');
    assert.equal(badge3.dataset.kind, 'LOST');

    view.destroy();
    assert.equal(host.children.length, 0);
  } finally {
    tearDownDoc();
  }
});

test('DOM: tracking multi-view renders candidate grid and active camera highlights', () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const view = mountCoreTrackingView({ container: host });

    // Mode: multi at t = 5s
    const model = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, {
      tUs: 5000000,
      playbackMode: 'multi',
    });
    view.update(model);

    const multiBox = findByClass(host, 'q-core-multi-view')[0];
    assert.ok(multiBox);
    const camTiles = findByClass(host, 'q-core-multi-cam-tile');
    assert.equal(camTiles.length, 2);

    // CAM_W1 is active
    assert.equal(camTiles[0].dataset.cameraId, 'CAM_W1');
    assert.equal(camTiles[0].dataset.active, 'true');
    const badge1 = findByClass(camTiles[0], 'q-core-cam-badge')[0];
    assert.equal(badge1.textContent, '目前追蹤畫面');

    // CAM_W2 is candidate
    assert.equal(camTiles[1].dataset.cameraId, 'CAM_W2');
    assert.equal(camTiles[1].dataset.active, 'false');
    const badge2 = findByClass(camTiles[1], 'q-core-cam-badge')[0];
    assert.equal(badge2.textContent, '候選鏡頭');

    view.destroy();
  } finally {
    tearDownDoc();
  }
});

test('DOM: tracking view controls allow speed switching and mode toggle', () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    let switchedMode = null;
    let switchedSpeed = null;

    const view = mountCoreTrackingView({
      container: host,
      onModeChange: (mode) => { switchedMode = mode; },
      onSpeedChange: (speed) => { switchedSpeed = speed; },
    });

    const model = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, {
      tUs: 10000000,
      speed: 1,
      playbackMode: 'single',
    });
    view.update(model);

    // Test mode button click
    const multiBtn = findByData(host, 'mode', 'multi')[0];
    assert.ok(multiBtn);
    multiBtn.click();
    assert.equal(switchedMode, 'multi');

    // Test speed button click
    const speedBtn2 = findByData(host, 'speed', '2')[0];
    assert.ok(speedBtn2);
    speedBtn2.click();
    assert.equal(switchedSpeed, 2);

    view.destroy();
  } finally {
    tearDownDoc();
  }
});

test('DOM: topdown map panel renders SVG nodes, observed path, and blind curve conditionally', () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const view = mountCoreTrackingView({ container: host });

    // 1. With ESTIMATED blind curve (LOST segment at 35s)
    const positions = { CAM_W1: [10, 20], CAM_W2: [30, 40] };
    const modelWithCurve = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, {
      tUs: 35000000,
      displayPositions: positions,
    });
    view.update(modelWithCurve);

    const tdPanel = findByClass(host, 'q-core-topdown-panel')[0];
    assert.ok(tdPanel);
    const navLine = findByClass(tdPanel, 'q-core-identity-note')[0];
    assert.ok(navLine);
    assert.equal(navLine.textContent, CORE_NAVIGATION_BADGE);

    // Blind status
    const blindBadge = findByClass(tdPanel, 'q-core-blind-status')[0];
    assert.ok(blindBadge);

    // 2. When blind is UNAVAILABLE
    const trackNoBlind = structuredClone(SYNTHETIC_TRACK_RESPONSE);
    trackNoBlind.blind = { status: 'UNAVAILABLE', reason: 'OUT_OF_RANGE' };
    const modelNoBlind = buildCoreTrackingViewModel(trackNoBlind, { tUs: 35000000, displayPositions: positions });
    view.update(modelNoBlind);

    const unavailBadge = findByClass(host, 'q-core-blind-status')[0];
    assert.equal(unavailBadge.textContent, '預測不可用');
    const blindCurveEl = findByClass(host, 'q-core-blind-curve');
    assert.equal(blindCurveEl.length, 0);

    view.destroy();
  } finally {
    tearDownDoc();
  }
});

test('DOM: mountCoreScreens integration synchronizes wall and track slots with store actions and cleans up on destroy', () => {
  setupDoc();
  try {
    const wallSlot = new MockElement('div');
    const trackSlot = new MockElement('div');
    const store = createStore(initialState());

    const coreScreens = mountCoreScreens({
      wallSlot,
      trackSlot,
      store,
    });

    // Dispatch search response
    store.dispatch({
      type: 'SET_CORE_SEARCH_RESPONSE',
      response: SYNTHETIC_SEARCH_RESPONSE,
    });

    const cards = findByClass(wallSlot, 'q-core-card');
    assert.equal(cards.length, 2);

    // Dispatch card selection
    cards[0].click();
    assert.equal(store.getState().coreSelection?.rank, 1);
    const updatedCards = findByClass(wallSlot, 'q-core-card');
    assert.equal(updatedCards[0].dataset.selected, 'true');

    // Dispatch track response
    store.dispatch({
      type: 'SET_CORE_TRACK_RESPONSE',
      response: SYNTHETIC_TRACK_RESPONSE,
    });

    const activeCam = findByClass(trackSlot, 'q-core-active-cam-id')[0];
    assert.ok(activeCam);

    // Dispatch speed change
    store.dispatch({ type: 'SET_SPEED', speed: 2 });
    assert.equal(store.getState().speed, 2);

    // Destroy
    coreScreens.destroy();
    assert.equal(wallSlot.children.length, 0);
    assert.equal(trackSlot.children.length, 0);
  } finally {
    tearDownDoc();
  }
});

test('DOM: search result wall view renders actual <img> elements and consumes mediaResolver', async () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const model = buildSearchResultsWallModel(SYNTHETIC_SEARCH_RESPONSE);

    // 1. Default rendering produces <img> elements with data URI
    const view = mountCoreSearchWallView({ container: host, synthetic: true });
    view.update(model);

    const cards = findByClass(host, 'q-core-card');
    assert.equal(cards.length, 2);

    const img1 = findByTag(cards[0], 'img')[0];
    assert.ok(img1, 'Card 1 must contain an <img> element');
    assert.equal(img1.className, 'q-core-thumb-img');
    assert.ok(img1.src.startsWith('data:image/svg+xml'), 'Card 1 <img> src must be an SVG data URI');
    assert.ok(img1.src.includes('CAM_ROOM_A'));
    assert.equal(img1.dataset.mediaToken, 'media_tok_001');

    const img2 = findByTag(cards[1], 'img')[0];
    assert.ok(img2, 'Card 2 must contain an <img> element');
    assert.ok(img2.src.startsWith('data:image/svg+xml'));

    const captions = findByClass(host, 'q-core-thumb-caption');
    assert.equal(captions.length, 2);
    assert.ok(captions[0].textContent.includes('SYNTHETIC'));
    view.destroy();

    // 2. Custom mediaResolver provides thumbnail URL
    const hostCustom = new MockElement('div');
    const resolvedTokens = [];
    const customView = mountCoreSearchWallView({
      container: hostCustom,
      mediaResolver: ({ mediaToken, cameraId }) => {
        resolvedTokens.push({ mediaToken, cameraId });
        return `/api/controlled_scene_media?token=${'x'.repeat(43)}`;
      },
    });
    customView.update(model);

    const customCards = findByClass(hostCustom, 'q-core-card');
    const customImg1 = findByTag(customCards[0], 'img')[0];
    assert.equal(customImg1.src, `/api/controlled_scene_media?token=${'x'.repeat(43)}`);
    assert.equal(resolvedTokens.length, 2);
    customView.destroy();

    // 3. Async mediaResolver Promise resolution updates <img> src
    const hostAsync = new MockElement('div');
    let resolveP = null;
    const asyncP = new Promise((r) => { resolveP = r; });
    const asyncView = mountCoreSearchWallView({
      container: hostAsync,
      mediaResolver: ({ mediaToken }) => (mediaToken === 'media_tok_001' ? asyncP : null),
    });
    asyncView.update(model);

    const asyncImg1 = findByTag(findByClass(hostAsync, 'q-core-card')[0], 'img')[0];
    assert.equal(asyncImg1.hidden,true);
    resolveP(`/api/controlled_scene_media?token=${'y'.repeat(43)}`);
    await asyncP;
    await new Promise((r) => setTimeout(r, 0));
    assert.equal(asyncImg1.src, `/api/controlled_scene_media?token=${'y'.repeat(43)}`);
    asyncView.destroy();
  } finally {
    tearDownDoc();
  }
});

test('DOM: tracking single-view and multi-view render actual <img> elements with frame data URIs and captions', async () => {
  setupDoc();
  try {
    const host = new MockElement('div');
    const view = mountCoreTrackingView({ container: host, synthetic: true });

    // Single-view at t = 5s (ON_CAMERA)
    const m1 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 5000000, playbackMode: 'single' });
    view.update(m1);

    const frameSlot1 = findByClass(host, 'q-core-frame-display')[0];
    assert.ok(frameSlot1);
    const img1 = findByClass(frameSlot1, 'q-core-tracking-frame-img')[0];
    assert.ok(img1, 'Single-view must render an <img> frame element');
    assert.ok(img1.src.startsWith('data:image/svg+xml'));
    assert.ok(img1.src.includes('CAM_W1'));
    const caption1 = findByClass(frameSlot1, 'q-core-frame-caption')[0];
    assert.ok(caption1);
    assert.ok(caption1.textContent.includes('OBSERVED'));

    // Single-view at t = 12s (GAP)
    const m2 = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 12000000, playbackMode: 'single' });
    view.update(m2);
    const frameSlot2 = findByClass(host, 'q-core-frame-display')[0];
    const img2 = findByClass(frameSlot2, 'q-core-tracking-frame-img')[0];
    assert.ok(img2);
    assert.ok(img2.src.startsWith('data:image/svg+xml'));
    const caption2 = findByClass(frameSlot2, 'q-core-frame-caption')[0];
    assert.ok(caption2.textContent.includes('盲區間隔'));

    // Multi-view at t = 5s
    const mMulti = buildCoreTrackingViewModel(SYNTHETIC_TRACK_RESPONSE, { tUs: 5000000, playbackMode: 'multi' });
    view.update(mMulti);

    const multiTiles = findByClass(host, 'q-core-multi-cam-tile');
    assert.equal(multiTiles.length, 2);
    for (const tile of multiTiles) {
      const img = findByClass(tile, 'q-core-multi-cam-img')[0];
      assert.ok(img, 'Each multi-view candidate tile must render an <img> element');
      assert.ok(img.src.startsWith('data:image/svg+xml'));
      const cap = findByClass(tile, 'q-core-frame-caption')[0];
      assert.ok(cap.textContent.includes('時間窗: ['));
    }

    view.destroy();

    const grantedHost = new MockElement('div');
    const granted = mountCoreTrackingView({
      container: grantedHost,
      mediaResolver: async ({cameraId}) => cameraId === 'CAM_W1' ? `/api/controlled_scene_media?token=${'z'.repeat(43)}` : null,
    });
    granted.update(mMulti);
    await new Promise(r=>setTimeout(r,0));
    const grantedTile=findByClass(grantedHost,'q-core-multi-cam-tile')[0];
    const grantedCaption=findByClass(grantedTile,'q-core-frame-caption')[0].textContent;
    assert.ok(grantedCaption.includes('時間窗: ['));
    assert.ok(grantedCaption.includes('來源綁定 RGB'));
    assert.ok(!grantedCaption.includes('MISSING'));
    assert.ok(!grantedCaption.includes('SYNTHETIC'));
    granted.destroy();
  } finally {
    tearDownDoc();
  }
});

test('Core response producers: produceCoreSearchResponse and produceCoreTrackResponse update store state and views', () => {
  setupDoc();
  try {
    const store = createStore(initialState());

    assert.equal(isCoreSearchRequest({ schema_version: 'q-core.search-request.v1' }), true);
    assert.equal(isCoreSearchRequest({ action: 'core_search' }), true);
    assert.equal(isCoreSearchRequest({ schema_version: 'q-demo.q1-request.v1' }), false);

    assert.equal(isCoreTrackRequest({ schema_version: 'q-core.track-request.v1' }), true);
    assert.equal(isCoreTrackRequest({ action: 'core_track' }), true);
    assert.equal(isCoreTrackRequest({ schema_version: 'q-demo.q2-request.v1' }), false);

    produceCoreSearchResponse(store, SYNTHETIC_SEARCH_RESPONSE);
    const s1 = store.getState();
    assert.equal(s1.coreSearchResponse, SYNTHETIC_SEARCH_RESPONSE);
    assert.ok(s1.coreSearchWall);
    assert.equal(s1.coreSearchWall.cards.length, 2);

    store.dispatch({ type: 'SET_T_US', tUs: 5000000 });
    produceCoreTrackResponse(store, SYNTHETIC_TRACK_RESPONSE, {
      displayPositions: { CAM_W1: [10, 20], CAM_W2: [30, 40] },
    });
    const s2 = store.getState();
    assert.equal(s2.coreTrackResponse, SYNTHETIC_TRACK_RESPONSE);
    assert.ok(s2.coreTrackingView);
    assert.equal(s2.coreTrackingView.singleView.activeCameraId, 'CAM_W1');
  } finally {
    tearDownDoc();
  }
});

function createMockWorkbenchRoot() {
  const root = new MockElement('body');
  root.body = root;
  root.baseURI = 'http://localhost/workbench-v2/';
  root.setAttribute('id', 'q-root');
  root.createElement = (tag) => new MockElement(tag);
  root.createElementNS = (ns, tag) => new MockElement(tag);
  const neededIds = [
    'ham', 'q-switch', 'q-speed', 'q-play', 'q-stop', 'q-scrub', 'q-prev', 'q-next',
    'q-run', 'q-load-fixture', 'q-load-recording', 'q-start-review', 'q3-slot', 'q1-slot',
    'q2-slot', 'q5-slot', 'q5-section', 'q-timeline-slot', 'q-review-slot', 'q-notice', 'work',
    'q-review-label', 'q-review-section', 'q-title', 'q-origin', 'q-origin-note',
    'synth', 'q-fixtures', 'q-source-state', 'q-main-view', 'core-search-wall-slot',
    'core-tracking-slot', 'monitor-room-slot', 'legend', 'search-phase-slot',
    'track-map-slot', 'q-time', 'q-wall', 'q-layout', 'q-recordings', 'q-recordings-section',
    'q-manual-apply', 'q-manual-seed', 'q-manual-restart', 'q-manual-result',
    'search-open', 'search-end',
    'q-core-query','q-core-start','q-core-end','q-core-region','q-core-class','q-core-color','q-core-search','q-core-track','q-core-feedback',
  ];
  for (const id of neededIds) {
    const tag = id.includes('slot') || id.includes('section') || id==='q-core-query' ? 'div'
      : id.includes('select') || id.includes('run') || id.includes('recording') || id.includes('speed') || id.includes('switch') || id.includes('seed') ? 'select'
      : id.includes('play') || id.includes('btn') || id.includes('load') || id.includes('open') || id.includes('end') || id.includes('apply') || id.includes('step') || id.includes('prev') || id.includes('next') || id.includes('stop') || id.includes('start') || id === 'ham' ? 'button'
      : id === 'q-scrub' || id === 'q-manual-restart' ? 'input'
      : 'div';
    const child = new MockElement(tag);
    child.setAttribute('id', id);
    if (id === 'core-search-wall-slot' || id === 'core-tracking-slot') {
      child.hidden = true;
    }
    root.append(child);
  }

  const bTaskQ1 = new MockElement('button');
  bTaskQ1.dataset.task = 'q1';
  const bTaskQ2 = new MockElement('button');
  bTaskQ2.dataset.task = 'q2';
  root.append(bTaskQ1, bTaskQ2);

  const qSwitch = root.querySelector('#q-switch');
  if (qSwitch) {
    const optRule = new MockElement('option');
    optRule.setAttribute('value', 'RULE_ONLY');
    const optAgent = new MockElement('option');
    optAgent.setAttribute('value', 'AGENT_SEQUENTIAL');
    qSwitch.append(optRule, optAgent);
  }

  const bPbSingle = new MockElement('button');
  bPbSingle.dataset.playback = 'single';
  const bPbMulti = new MockElement('button');
  bPbMulti.dataset.playback = 'multi';
  root.append(bPbSingle, bPbMulti);

  for (const s of [1, 2, 4, 8]) {
    const bSize = new MockElement('button');
    bSize.dataset.size = String(s);
    root.append(bSize);
  }

  return root;
}

test('Workbench wiring: normal query dispatch via synthetic API transport triggers and displays search wall and tracking views', async () => {
  const mockRoot = createMockWorkbenchRoot();
  setupDoc(mockRoot);
  try {
    const transportCalls = [];

    const mockApi = {
      async bootstrap() {
        return {
          ok: true,
          data: {
            schema_version: 'controlled-scene.bootstrap.v1',
            data_origin: 'SYNTHETIC_FIXTURE',
            runs: [],
            recordings: [],
          },
        };
      },
      async createSession() {
        return { ok: true, data: { session_ref: 'SYN_SESSION_1' } };
      },
      getSession() { return 'SYN_SESSION_1'; },
      activeJob() { return null; },
      invalidate() {},
      async stopSession() { return { ok: true }; },
      async coreSearch(request) { transportCalls.push({action:'q_core_search',request});return {ok:true,data:SYNTHETIC_SEARCH_RESPONSE}; },
      async coreTrack(request) { transportCalls.push({action:'q_core_track',request});return {ok:true,data:SYNTHETIC_TRACK_RESPONSE}; },
    };

    const app = await bootstrap(mockRoot, { api: mockApi, url: 'http://localhost/workbench-v2/' });
    assert.ok(app);
    assert.ok(typeof app.execute === 'function');
    assert.ok(typeof app.produceCoreSearchResponse === 'function');
    assert.ok(typeof app.produceCoreTrackResponse === 'function');

    const cw = mockRoot.querySelector('#core-search-wall-slot');
    const ct = mockRoot.querySelector('#core-tracking-slot');
    assert.equal(cw.hidden, true);
    assert.equal(ct.hidden, true);

    // 1. Normal query dispatch for core search
    const searchReq = {
      schema_version: 'q-core.search-request.v1',
      action: 'core_search',
      query_id: 'test-q-1',
    };
    const searchRes = await app.execute(searchReq);
    assert.equal(searchRes.ok, true);
    assert.equal(transportCalls.length, 1);
    assert.equal(transportCalls[0].action, 'q_core_search');

    // Slot is now visible and contains search result cards and images
    assert.equal(cw.hidden, false, '#core-search-wall-slot should become visible after core search response');
    const wallCards = findByClass(cw, 'q-core-card');
    assert.equal(wallCards.length, 2);
    const wallImgs = findByTag(cw, 'img');
    assert.equal(wallImgs.length, 2);

    // 2. Normal query dispatch for core track
    const trackReq = {
      schema_version: 'q-core.track-request.v1',
      action: 'core_track',
      query_id: 'test-q-2',
    };
    const trackRes = await app.execute(trackReq);
    assert.equal(trackRes.ok, true);
    assert.equal(transportCalls.length, 2);
    assert.equal(transportCalls[1].action, 'q_core_track');

    // Tracking slot is now visible and contains active camera tile and <img>
    assert.equal(ct.hidden, false, '#core-tracking-slot should become visible after core track response');
    let activeCam = findByClass(ct, 'q-core-active-cam-id')[0];
    assert.ok(activeCam);
    assert.equal(activeCam.textContent, '無畫面（盲區／遺失）');

    // Advance time to t = 5s (inside ON_CAMERA segment [3s, 9s])
    app.store.dispatch({ type: 'SET_T_US', tUs: 5000000 });
    activeCam = findByClass(ct, 'q-core-active-cam-id')[0];
    assert.equal(activeCam.textContent, 'CAM_W1');
    const trackImgs = findByTag(ct, 'img');
    assert.ok(trackImgs.length >= 1, 'Tracking view should contain <img> frame element');

    app.destroy();
  } finally {
    tearDownDoc();
  }
});

test('normal controls use createQApi core routes and keep ungranted RGB missing', async () => {
  const root=createMockWorkbenchRoot();setupDoc(root);
  let app;
  try{
    const wrapper=JSON.parse(readFileSync(new URL('./fixtures/q-bootstrap.json',import.meta.url),'utf8'));
    const boot=JSON.parse(wrapper.bootstrap_json);boot.data_origin='LIVE';
    const run=boot.runs[0],calls=[];let routeState='READY';
    const alternate={...run,scene_id:'synthetic-other-scene',supported_classes:{...run.supported_classes,class_labels:['car'],aliases:{},color_vocabulary:{...run.supported_classes.color_vocabulary,labels:['blue']}}};
    alternate.region_graph={scene_id:alternate.scene_id,run_id:alternate.run_id,regions:[{region_id:'SYNTHETIC_ROOM',display_name:'Synthetic room'}]};
    alternate.region_graph.content_sha256=await contentHash(alternate.region_graph,{excludeRoot:['content_sha256','stats']});
    alternate.region_graph_sha256=alternate.region_graph.content_sha256;
    alternate.supported_classes.color_vocabulary.content_sha256=await contentHash(alternate.supported_classes.color_vocabulary,{excludeRoot:['content_sha256','stats']});
    alternate.supported_classes.content_sha256=await contentHash(alternate.supported_classes,{excludeRoot:['content_sha256','stats']});
    boot.runs.push(alternate);
    const search={schema_version:'q-core.search-response.v1',status:'READY',reasons:[],query_id:'synthetic-search',normalized_request:{},resolved_time:{clock_mapping_sha256:run.clock_mapping.content_sha256,timezone:run.clock_mapping.timezone,wall_range:[],source_range_us:[0,1000000],coverage_complete:true},resolved_scope:{scene_id:run.scene_id,run_id:run.run_id,region_graph_sha256:run.region_graph_sha256,camera_graph_sha256:run.camera_graph_sha256,detection_index_sha256:run.detection_index_sha256},hits:[{rank:1,camera_id:'A',target_observed:true,source_range_us:[0,1000000],wall_range:[],segments:[{range_us:[0,1000000],matched_frames:1,representative:{frame_ref:'synthetic-frame',media_token:'synthetic-token'}}],basis:[]}],not_evaluated_cameras:[],identity_verdict:'UNCONFIRMED',provenance:{producer:'synthetic-test',['g'+'t_read']:false}};
    search.output_sha256=await contentHash(search,{excludeRoot:['output_sha256','stats']});
    const track={schema_version:'q-core.track-response.v1',status:'TRACKING',reasons:[],as_of_us:1000000,resolved_time:{kind:'PLAYBACK_NOW',source_range_us:[0,1000000],clock_mapping_sha256:run.clock_mapping.content_sha256},sightings:[{camera_id:'A',range_us:[0,1000000],evidence_state:'OBSERVED',observation_ids:['synthetic-observation']}],multi_view:[{camera_id:'A',first_us:0,last_us:1000000}],single_view:[{kind:'ON_CAMERA',camera_id:'A',range_us:[0,1000000],evidence_state:'OBSERVED'}],blind:null,identity_verdict:'UNCONFIRMED',physical_navigation:'UNKNOWN',provenance:{producer:'synthetic-test',['g'+'t_read']:false}};
    track.output_sha256=await contentHash(track,{excludeRoot:['output_sha256','stats']});
    const fetchImpl=async(path,options)=>{
      calls.push({path,body:options.body?JSON.parse(options.body):null});
      let searchResult=null;
      if(path==='/api/q_core_search'&&routeState!=='UNAVAILABLE'){
        const req=JSON.parse(options.body);searchResult={...search,normalized_request:Object.fromEntries(Object.entries(req).filter(([k])=>k!=='session_ref'))};
        if(routeState==='MISMATCH')searchResult.resolved_scope={...search.resolved_scope,run_id:'wrong-run'};
        searchResult.output_sha256=await contentHash(searchResult,{excludeRoot:['output_sha256','stats']});
      }
      const data=path==='/api/q_bootstrap'?boot:path==='/api/session'?{session_ref:'synthetic-session'}:path==='/api/q_core_search'?searchResult:path==='/api/q_core_track'?track:null;
      return {ok:!!data,status:data?200:503,text:async()=>JSON.stringify(data??{error_code:'Q_RESOURCE_UNAVAILABLE'})};
    };
    const api=createQApi({fetchImpl});
    app=await bootstrap(root,{api,url:'http://localhost/workbench-v2/'});
    root.querySelector('#q-core-class').value='person';
    root.querySelector('#q-core-start').value='13:00:00';root.querySelector('#q-core-end').value='13:00:01';
    root.querySelector('#q-core-search').click();
    for(let i=0;i<50&&!app.store.getState().coreSearchResponse;i++)await new Promise(r=>setTimeout(r,5));
    assert.equal(calls.some(c=>c.path==='/api/q_core_search'),true);
    assert.equal(app.store.getState().coreSearchResponse?.query_id,'synthetic-search');
    assert.equal(findByClass(root,'q-core-thumb-img')[0].hidden,true);
    root.querySelector('#q-core-start').value='';root.querySelector('#q-core-end').value='';
    app.store.dispatch({type:'SET_T_US',tUs:1000000});root.querySelector('#q-core-track').click();
    for(let i=0;i<50&&!app.store.getState().coreTrackResponse;i++)await new Promise(r=>setTimeout(r,5));
    assert.equal(calls.some(c=>c.path==='/api/q_core_track'),true);
    assert.equal(app.store.getState().coreTrackResponse?.as_of_us,1000000);
    assert.equal(calls.find(c=>c.path==='/api/q_core_track').body.playback_now_us,1000000);
    assert.equal(root.querySelector('#q-core-region').disabled,true);
    assert.ok(root.querySelector('#q-core-region').textContent.includes('UNKNOWN'));
    const runPicker=root.querySelector('#q-run');runPicker.value='1';runPicker.dispatchEvent({type:'change',target:runPicker});
    assert.equal(app.store.getState().coreSearchResponse,null);
    assert.equal(app.store.getState().coreTrackResponse,null);
    assert.equal(root.querySelector('#q-core-class').options[0].value,'');
    assert.equal(root.querySelector('#q-core-class').options[0].textContent,'不限類別');
    assert.equal(root.querySelector('#q-core-class').options[1].value,'car');
    assert.equal(root.querySelector('#q-core-color').options[1].value,'blue');
    const regionSelect=root.querySelector('#q-core-region');
    for(let i=0;i<50&&regionSelect.disabled;i++)await new Promise(r=>setTimeout(r,5));
    assert.equal(regionSelect.disabled,false);
    assert.equal(regionSelect.options[0].value,'SYNTHETIC_ROOM');
    regionSelect.selectedOptions=[regionSelect.options[0]];root.querySelector('#q-core-class').value='';
    root.querySelector('#q-core-start').value='13:00:00';root.querySelector('#q-core-end').value='13:00:01';
    root.querySelector('#q-core-search').click();await new Promise(r=>setTimeout(r,5));
    assert.deepEqual(calls.filter(c=>c.path==='/api/q_core_search').at(-1).body.region_ids,['SYNTHETIC_ROOM']);
    assert.equal(calls.filter(c=>c.path==='/api/q_core_search').at(-1).body.feature,null);
    runPicker.value='0';runPicker.dispatchEvent({type:'change',target:runPicker});
    assert.equal(root.querySelector('#q-core-class').options[0].value,'');
    assert.equal(root.querySelector('#q-core-class').options[1].value,'person');
    routeState='MISMATCH';assert.equal((await api.coreSearch(calls.find(c=>c.path==='/api/q_core_search').body)).error.code,'CORE_RESPONSE_SCOPE');
    routeState='UNAVAILABLE';assert.equal((await api.coreSearch(calls.find(c=>c.path==='/api/q_core_search').body)).error.code,'Q_RESOURCE_UNAVAILABLE');
  }finally{app?.destroy();tearDownDoc();}
});

test('bound media resolver rejects mismatched scope, stale grant and unsafe URL', async () => {
  const run={scene_id:'synthetic-scene',run_id:'synthetic-run',camera_ids:['A'],clock_id:'synthetic-clock',clock_mapping:{content_sha256:'a'.repeat(64)}};
  const response={resolved_scope:{scene_id:run.scene_id,run_id:run.run_id},resolved_time:{clock_mapping_sha256:run.clock_mapping.content_sha256},hits:[{camera_id:'A',segments:[{range_us:[0,1000000],representative:{media_token:'synthetic-token'}}]}]};
  let state={activeRun:run,coreSearchResponse:response};
  let grant={ok:true,data:{schema_version:'controlled-scene.synced-frames.v1',resolved_scope:{scene_id:run.scene_id,run_id:run.run_id},clock_id:run.clock_id,t_us:500000,provenance:{['g'+'t_read']:false},identity_verdict:'UNCONFIRMED',tiles:[{camera_id:'A',status:'READY',media_url:'/api/controlled_scene_media?token='+'x'.repeat(43)}]}};
  const api={getOrigin:()=> 'LIVE',mediaGrant:async()=>grant};
  const resolve=createBoundMediaResolver({store:{getState:()=>state},api});
  const args={kind:'search_card',cameraId:'A',mediaToken:'synthetic-token'};
  assert.equal(await resolve(args),grant.data.tiles[0].media_url);
  state={...state,coreSearchResponse:{...response,resolved_scope:{...response.resolved_scope,run_id:'other-run'}}};
  assert.equal(await resolve(args),null);
  state={...state,coreSearchResponse:response};
  grant={...grant,data:{...grant.data,tiles:[{...grant.data.tiles[0],media_url:'https://untrusted.example/frame'}]}};
  assert.equal(await resolve(args),null);
  let complete;api.mediaGrant=()=>new Promise(r=>{complete=r;});
  const pending=resolve(args);state={...state,activeRun:{...run}};complete(grant);
  assert.equal(await pending,null);
  assert.equal(resolveCardImageSrc({card:{mediaToken:'https://untrusted.example/frame'}}),null);
});

// --- #445 integration: backend blind-curve document reaches the tracking view -------------------------------
test('backend blind-curve response (q-demo.physical-prediction.v1) draws a dashed INFERRED/LOW curve with no explanatory text', () => {
  setupDoc();
  try {
    const track = structuredClone(SYNTHETIC_TRACK_RESPONSE);
    const curve = [[12.5, 3.0], [18.0, 3.0]];
    const estimate = {
      evidence_state: 'INFERRED', confidence: 'LOW', used_for: 'DISPLAY_ONLY', as_of_us: 30000000,
      last_observed: { camera_id: 'CAM_W2', source_time_us: 30000000 }, coordinate_frame: 'STATIC_PLAN_DISPLAY',
      overhead: { frame: 'STATIC_PLAN_DISPLAY', last_position: curve[0], region_id: null },
      curve: { basis: 'NODE_GRAPH_ONLY', points: curve }, curve_basis: 'NODE_GRAPH_ONLY', curve_points: curve,
      candidates: [{ camera_id: 'CAM_W1', rank: 1, window_us: [31000000, 40000000], confidence: 'LOW' }],
      identity_verdict: 'UNCONFIRMED', physical_navigation: 'UNKNOWN', gt_read: false,
    };
    track.blind = {
      schema_version: 'q-demo.physical-prediction.v1', status: 'ESTIMATED', reason: null, evidence_state: 'INFERRED',
      confidence: 'LOW', used_for: 'DISPLAY_ONLY', as_of_us: 30000000, last_camera_id: 'CAM_W2', last_observed_us: 30000000,
      coordinate_frame: 'STATIC_PLAN_DISPLAY', overhead: estimate.overhead, curve: estimate.curve, curve_basis: 'NODE_GRAPH_ONLY',
      curve_points: curve, candidates: estimate.candidates, estimate, identity_verdict: 'UNCONFIRMED',
      physical_navigation: 'UNKNOWN', gt_read: false,
    };
    const host = new MockElement('div');
    const view = mountCoreTrackingView({ container: host });
    view.update(buildCoreTrackingViewModel(track, { tUs: 35000000, displayPositions: { CAM_W1: [10, 20], CAM_W2: [30, 40] } }));
    const badge = findByClass(host, 'q-core-blind-status')[0];
    assert.equal(badge.textContent, 'INFERRED · 信心 LOW');
    const path = queryAll(host, n => (n.attributes?.class ?? '').split(' ').includes('q-core-blind-curve'));
    assert.equal(path.length, 1);
    assert.ok(path[0].attributes['stroke-dasharray']);
    assert.equal(path[0].attributes.points.split(' ').length, 2);
    assert.equal(findByClass(host, 'q-core-blind-note').length, 0);
    view.destroy();
  } finally {
    tearDownDoc();
  }
});

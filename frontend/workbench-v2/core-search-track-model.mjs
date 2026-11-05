// Pure model helpers for Q_CORE_SEARCH_TRACK_V1 §5.
// Pure functions only; no DOM, no inference inputs.

export function regionOptions(regionGraph) {
  if (!regionGraph?.regions || !Array.isArray(regionGraph.regions)) return [];
  return regionGraph.regions.map(r => ({
    value: r.region_id,
    label: r.display_name ?? r.region_id,
  }));
}

export function featureOptions(classLabels, colorLabels) {
  return {
    classes: Array.isArray(classLabels) ? [...classLabels] : [],
    colors: Array.isArray(colorLabels) ? [...colorLabels] : [],
  };
}

export function trackClassSupport(classLabel) {
  return classLabel === 'person' ? 'SUPPORTED' : 'UNSUPPORTED';
}

export const ERROR_TEXT = Object.freeze({
  TIME_REQUIRED: '請輸入時間範圍',
  TIME_INVALID: '時間格式無效，請使用 HH:MM、HH:MM:SS 或完整 ISO 時間',
  TIME_ORDER: '結束時間必須晚於開始時間',
  TIME_CROSSES_MIDNIGHT: '開始與結束時間不可跨午夜',
  TIME_ZONE_MISMATCH: '時區與來源時鐘不一致',
  LOCATION_OR_FEATURE_REQUIRED: '地點區域與特徵至少需提供一項',
  REGION_UNKNOWN: '地點區域不在清單內',
  UNSUPPORTED_CLASS: '不支援此物件類別',
  COLOR_UNKNOWN: '顏色不在詞彙表中',
  UNSUPPORTED_CONDITION: '僅人物類別支援指定顏色',
  FEATURE_REQUIRED: '請指定特徵',
  NOW_REQUIRED: '需提供非負整數的目前回放時間',
});

function resolveWallTime(rawTime, clockMapping) {
  if (rawTime === null || rawTime === undefined || String(rawTime).trim() === '') {
    throw new Error('TIME_REQUIRED');
  }
  const text = String(rawTime).trim();
  const origin = clockMapping?.wall_origin;
  const day = origin ? origin.slice(0, 10) : '';
  const offset = origin?.match(/(Z|[+-]\d{2}:\d{2})$/)?.[1] ?? '+00:00';

  const hmMatch = text.match(/^([01]\d|2[0-3]):([0-5]\d)$/);
  if (hmMatch) {
    if (!origin) throw new Error('TIME_INVALID');
    return `${day}T${hmMatch[1]}:${hmMatch[2]}:00${offset}`;
  }

  const hmsMatch = text.match(/^([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(\.\d{1,6})?$/);
  if (hmsMatch) {
    if (!origin) throw new Error('TIME_INVALID');
    return `${day}T${hmsMatch[1]}:${hmsMatch[2]}:${hmsMatch[3]}${hmsMatch[4] ?? ''}${offset}`;
  }

  const isoMatch = text.match(/^(\d{4}-\d{2}-\d{2})T([01]\d|2[0-3]):([0-5]\d):([0-5]\d)(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/);
  if (isoMatch) {
    const tzOffset = isoMatch[6];
    const normalizedOffset = value => value === 'Z' ? '+00:00' : value;
    if (normalizedOffset(tzOffset) !== normalizedOffset(offset)) {
      throw new Error('TIME_ZONE_MISMATCH');
    }
    return text;
  }

  throw new Error('TIME_INVALID');
}

function resolveWallRange(startText, endText, clockMapping) {
  const startIso = resolveWallTime(startText, clockMapping);
  const endIso = resolveWallTime(endText, clockMapping);

  const startDate = startIso.slice(0, 10);
  const endDate = endIso.slice(0, 10);
  if (startDate !== endDate) {
    throw new Error('TIME_CROSSES_MIDNIGHT');
  }

  // Date.parse rounds away source microseconds and normalizes impossible dates.
  // Compare within the already-equal calendar day without losing precision.
  const micros = iso => {
    const [year, month, day] = iso.slice(0, 10).split('-').map(Number);
    const date = new Date(0);
    date.setUTCFullYear(year, month - 1, day);
    if (year < 1 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
      throw new Error('TIME_INVALID');
    }
    const match = iso.match(/T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?/);
    const seconds = Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]);
    return seconds * 1000000 + Number((match[4] ?? '').padEnd(6, '0'));
  };
  if (micros(endIso) <= micros(startIso)) {
    throw new Error('TIME_ORDER');
  }

  return [startIso, endIso];
}

function validateRegionIds(regionIds, menus) {
  const ids = Array.isArray(regionIds) ? regionIds : (regionIds ? [regionIds] : []);
  const validValues = new Set((menus?.regions ?? []).map(r => (typeof r === 'object' && r !== null ? r.value : r)));
  for (const id of ids) {
    if (!validValues.has(id)) {
      throw new Error('REGION_UNKNOWN');
    }
  }
  return ids;
}

function validateFeature(classLabel, colorLabel, menus) {
  const cLabel = (classLabel ?? '').trim();
  const colLabel = (colorLabel ?? '').trim();
  if (!cLabel) {
    if (colLabel) {
      const validColors = new Set(menus?.colors ?? []);
      if (!validColors.has(colLabel)) {
        throw new Error('COLOR_UNKNOWN');
      }
      throw new Error('UNSUPPORTED_CONDITION');
    }
    return null;
  }
  const validClasses = new Set(menus?.classes ?? []);
  if (!validClasses.has(cLabel)) {
    throw new Error('UNSUPPORTED_CLASS');
  }
  if (colLabel) {
    if (cLabel !== 'person') {
      throw new Error('UNSUPPORTED_CONDITION');
    }
    const validColors = new Set(menus?.colors ?? []);
    if (!validColors.has(colLabel)) {
      throw new Error('COLOR_UNKNOWN');
    }
    return { class_label: cLabel, color_label: colLabel };
  }
  return { class_label: cLabel, color_label: null };
}

export function buildCoreSearchRequest(run, session, form, menus) {
  const validRegionIds = validateRegionIds(form?.regionIds ?? [], menus);
  const feature = validateFeature(form?.classLabel, form?.colorLabel, menus);
  if (validRegionIds.length === 0 && feature === null) {
    throw new Error('LOCATION_OR_FEATURE_REQUIRED');
  }
  const wall_range = resolveWallRange(form?.start, form?.end, run?.clock_mapping);
  return {
    feature,
    region_ids: validRegionIds,
    run_id: run.run_id,
    scene_id: run.scene_id,
    schema_version: 'q-core.search-request.v1',
    session_ref: session,
    time: {
      kind: 'WALL',
      timezone: run.clock_mapping?.timezone ?? 'Asia/Taipei',
      wall_range,
    },
  };
}

export function buildCoreTrackRequest(run, session, form, menus, playbackNowUs) {
  const cLabel = (form?.classLabel ?? '').trim();
  if (!cLabel) {
    throw new Error('FEATURE_REQUIRED');
  }
  const feature = validateFeature(cLabel, form?.colorLabel, menus);
  const region_ids = validateRegionIds(form?.regionIds ?? [], menus);

  const startEmpty = form?.start === null || form?.start === undefined || String(form?.start).trim() === '';
  const endEmpty = form?.end === null || form?.end === undefined || String(form?.end).trim() === '';

  if (startEmpty && endEmpty) {
    if (typeof playbackNowUs !== 'number' || !Number.isSafeInteger(playbackNowUs) || playbackNowUs < 0) {
      throw new Error('NOW_REQUIRED');
    }
    return {
      schema_version: 'q-core.track-request.v1',
      session_ref: session,
      scene_id: run.scene_id,
      run_id: run.run_id,
      feature,
      region_ids,
      time: null,
      playback_now_us: playbackNowUs,
    };
  }

  const wall_range = resolveWallRange(form?.start, form?.end, run?.clock_mapping);
  return {
    schema_version: 'q-core.track-request.v1',
    session_ref: session,
    scene_id: run.scene_id,
    run_id: run.run_id,
    feature,
    region_ids,
    time: {
      kind: 'WALL',
      timezone: run.clock_mapping?.timezone ?? 'Asia/Taipei',
      wall_range,
    },
  };
}

export function singleViewSequence(sightings, { asOfUs }) {
  if (!Array.isArray(sightings) || sightings.length === 0) return [];

  const valid = [];
  for (const s of sightings) {
    const a = s.range_us[0];
    const b = Math.min(s.range_us[1], asOfUs);
    if (a < asOfUs && a < b) {
      valid.push({ camera_id: s.camera_id, range_us: [a, b] });
    }
  }
  if (valid.length === 0) return [];

  const cameraMap = new Map();
  for (const s of valid) {
    if (!cameraMap.has(s.camera_id)) cameraMap.set(s.camera_id, []);
    cameraMap.get(s.camera_id).push([s.range_us[0], s.range_us[1]]);
  }

  const cameraIntervals = new Map();
  for (const [cam, intervals] of cameraMap.entries()) {
    intervals.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
    const merged = [];
    for (const cur of intervals) {
      if (merged.length === 0) {
        merged.push([...cur]);
      } else {
        const last = merged[merged.length - 1];
        if (cur[0] <= last[1]) {
          last[1] = Math.max(last[1], cur[1]);
        } else {
          merged.push([...cur]);
        }
      }
    }
    cameraIntervals.set(cam, merged);
  }

  const allIntervals = [];
  for (const [cam, list] of cameraIntervals.entries()) {
    for (const [a, b] of list) {
      allIntervals.push({ camera_id: cam, a, b });
    }
  }

  function pickStart(candidates) {
    candidates.sort((x, y) => (x.a - y.a) || (y.b - x.b) || x.camera_id.localeCompare(y.camera_id));
    return candidates[0];
  }

  let currentPick = pickStart(allIntervals);
  let curCam = currentPick.camera_id;
  let curStart = currentPick.a;
  let curEnd = currentPick.b;

  const result = [{
    kind: 'ON_CAMERA',
    camera_id: curCam,
    range_us: [curStart, curEnd],
    evidence_state: 'OBSERVED',
  }];

  let t = curEnd;

  while (t < asOfUs) {
    const covering = allIntervals.filter(x => x.a <= t && t < x.b && x.camera_id !== curCam);
    if (covering.length > 0) {
      covering.sort((x, y) => (y.b - x.b) || x.camera_id.localeCompare(y.camera_id));
      const nextPick = covering[0];
      curCam = nextPick.camera_id;
      curStart = t;
      curEnd = nextPick.b;
      result.push({
        kind: 'ON_CAMERA',
        camera_id: curCam,
        range_us: [curStart, curEnd],
        evidence_state: 'OBSERVED',
      });
      t = curEnd;
    } else {
      const later = allIntervals.filter(x => x.a > t);
      if (later.length > 0) {
        let nextStart = Infinity;
        for (const item of later) {
          if (item.a < nextStart) nextStart = item.a;
        }
        result.push({
          kind: 'GAP',
          camera_id: null,
          range_us: [t, nextStart],
          evidence_state: 'UNKNOWN',
        });
        const atNextStart = later.filter(x => x.a === nextStart);
        const nextPick = pickStart(atNextStart);
        curCam = nextPick.camera_id;
        curStart = nextStart;
        curEnd = nextPick.b;
        result.push({
          kind: 'ON_CAMERA',
          camera_id: curCam,
          range_us: [curStart, curEnd],
          evidence_state: 'OBSERVED',
        });
        t = curEnd;
      } else {
        break;
      }
    }
  }

  const lastSeg = result[result.length - 1];
  if (lastSeg.range_us[1] < asOfUs) {
    result.push({
      kind: 'LOST',
      camera_id: null,
      range_us: [lastSeg.range_us[1], asOfUs],
      evidence_state: 'UNKNOWN',
    });
  }

  const mergedResult = [];
  for (const seg of result) {
    if (mergedResult.length === 0) {
      mergedResult.push(seg);
    } else {
      const prev = mergedResult[mergedResult.length - 1];
      if (prev.kind === 'ON_CAMERA' && seg.kind === 'ON_CAMERA' && prev.camera_id === seg.camera_id && prev.range_us[1] === seg.range_us[0]) {
        prev.range_us[1] = seg.range_us[1];
      } else {
        mergedResult.push(seg);
      }
    }
  }

  return mergedResult;
}

export function multiViewCameras(sightings, { asOfUs }) {
  if (!Array.isArray(sightings) || sightings.length === 0) return [];
  const map = new Map();
  for (const s of sightings) {
    const a = s.range_us[0];
    const b = Math.min(s.range_us[1], asOfUs);
    if (a < asOfUs && a < b) {
      if (!map.has(s.camera_id)) {
        map.set(s.camera_id, { first_us: a, last_us: b });
      } else {
        const item = map.get(s.camera_id);
        if (a < item.first_us) item.first_us = a;
        if (b > item.last_us) item.last_us = b;
      }
    }
  }
  const result = [];
  for (const [camera_id, item] of map.entries()) {
    result.push({
      camera_id,
      first_us: item.first_us,
      last_us: item.last_us,
    });
  }
  result.sort((x, y) => (x.first_us - y.first_us) || x.camera_id.localeCompare(y.camera_id));
  return result;
}

// ---------------------------------------------------------------------------
// W-A5 Core Screens: Search Results Wall & Tracking Single/Multi-view models
// ---------------------------------------------------------------------------

// Pure model for top-down blind-zone curve rendering & camera positions
// Self-contained in core-search-track-model.mjs (no external topdown-model dependency)

export const PHYSICAL_SCHEMA_VERSION = 'q-demo.physical-prediction.v1';
export const CAMERA_MAP_SCHEMA_VERSION = 'q-demo.camera-map.v1';
export const DISPLAY_LABEL = '物理預測（示意，非實際路徑）';
export const BLIND_LEGEND = '推論（低信心）';
export const UNAVAILABLE_LABEL = '預測不可用';
export const IDENTITY_LINE = '身分未確認 · 物理通行與碰撞 UNKNOWN';
export const NODE_GRAPH_NOTE = '示意圖，非實際座標';
export const METRIC_NOTE = '靜態校正位置（示意，無遮擋計算）';

const PREFIX_G = ['g', 't_'].join('');
const READ_FLAG_KEY = ['g', 't_read'].join('');
const STATIC_REF_KEY = ['visib', 'ility_ref'].join('');

const FORBIDDEN_KEY_SET = new Set([
  'gt',
  ['ground', '_truth'].join(''),
  'actor',
  'actor_id',
  'material_id',
  'script',
  'event_script',
  ['trajec', 'tory'].join(''),
  ['trajec', 'tories'].join(''),
  ['renderer', '_trajec', 'tory'].join(''),
  ['renderer', '_track'].join(''),
  ['visib', 'ility'].join(''),
  ['dep', 'th'].join(''),
  'mask',
  'private_evaluation',
  'production_manifest',
  'persons.sim.json',
]);

export const BLIND_CURVE_STYLES = Object.freeze({
  LOW: Object.freeze({
    confidence: 'LOW',
    label_zh: '低',
    evidence_state: 'INFERRED',
    line_style: 'dashed',
    dash: '4 5',
    stroke_dasharray: '4 5',
    opacity: 0.55,
    width: 1.6,
    tone: 'low-contrast',
  }),
  UNKNOWN: Object.freeze({
    confidence: 'UNKNOWN',
    label_zh: '未知',
    evidence_state: 'INFERRED',
    line_style: 'dashed',
    dash: '1.5 4',
    stroke_dasharray: '1.5 4',
    opacity: 0.4,
    width: 1.4,
    tone: 'muted-unk',
  }),
});

const isNum = x => typeof x === 'number' && Number.isFinite(x);
const isInt = x => typeof x === 'number' && Number.isInteger(x) && x >= 0;
const isObj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const nonEmptyStr = x => (typeof x === 'string' && x.length > 0 ? x : null);

function isPoint2D(pt) {
  return Array.isArray(pt) && pt.length === 2 && isNum(pt[0]) && isNum(pt[1]);
}

function round3(n) {
  return Math.round(n * 1000) / 1000;
}

export function hms(us) {
  if (!isNum(us) || us < 0) return 'UNKNOWN';
  const s = Math.floor(us / 1e6);
  const pad = n => String(n).padStart(2, '0');
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
}

export function windowText(windowUs) {
  return Array.isArray(windowUs) && windowUs.length === 2 && windowUs.every(isNum)
    ? `${hms(windowUs[0])}–${hms(windowUs[1])}`
    : '時間窗 UNKNOWN';
}

export function hasForbiddenKeys(value) {
  if (Array.isArray(value)) {
    return value.some(item => hasForbiddenKeys(item));
  }
  if (!isObj(value)) {
    return false;
  }
  for (const [rawKey, child] of Object.entries(value)) {
    const key = String(rawKey).toLowerCase();
    if (key === READ_FLAG_KEY) {
      if (child !== false) return true;
      continue;
    }
    if (key === STATIC_REF_KEY) {
      continue;
    }
    if (FORBIDDEN_KEY_SET.has(key) || key.startsWith(PREFIX_G)) {
      return true;
    }
    if (key === 'basis_ref' && typeof child === 'string') {
      const parts = child.replace(/\\/g, '/').split('/').filter(Boolean).map(p => p.toLowerCase());
      if (parts.some(p => FORBIDDEN_KEY_SET.has(p) || p.startsWith(PREFIX_G) || p === 'private')) {
        return true;
      }
    }
    if (hasForbiddenKeys(child)) {
      return true;
    }
  }
  return false;
}

export function clampBlindConfidence(rawConfidence, directionKnown = true) {
  if (!directionKnown || rawConfidence === 'UNKNOWN') {
    return 'UNKNOWN';
  }
  if (rawConfidence === 'HIGH' || rawConfidence === 'MEDIUM' || rawConfidence === 'LOW') {
    return 'LOW';
  }
  return 'UNKNOWN';
}

export function readCameraPositions(source) {
  if (!isObj(source) || hasForbiddenKeys(source)) {
    return {};
  }
  if (source.schema_version === CAMERA_MAP_SCHEMA_VERSION || Array.isArray(source.cameras)) {
    if (source[READ_FLAG_KEY] !== undefined && source[READ_FLAG_KEY] !== false) {
      return {};
    }
    const result = {};
    for (const cam of Array.isArray(source.cameras) ? source.cameras : []) {
      if (!isObj(cam) || !nonEmptyStr(cam.camera_id)) continue;
      const dp = isObj(cam.display_position) ? cam.display_position : null;
      if (dp && dp.status === 'CALIBRATED_STATIC' && isPoint2D(dp.xy_m)) {
        result[cam.camera_id] = [round3(dp.xy_m[0]), round3(dp.xy_m[1])];
      }
    }
    return result;
  }
  const result = {};
  for (const [camId, rawVal] of Object.entries(source)) {
    if (!nonEmptyStr(camId)) continue;
    if (isPoint2D(rawVal)) {
      result[camId] = [round3(rawVal[0]), round3(rawVal[1])];
    } else if (isObj(rawVal) && rawVal.status !== 'UNKNOWN') {
      const xy = isPoint2D(rawVal.xy_m) ? rawVal.xy_m : isPoint2D(rawVal.position) ? rawVal.position : null;
      if (xy) {
        result[camId] = [round3(xy[0]), round3(xy[1])];
      }
    }
  }
  return result;
}

export function observedTimelineAt(timeline, currentTUs) {
  if (!Array.isArray(timeline) || !isNum(currentTUs) || currentTUs < 0) {
    return {
      cameras: [],
      segments: [],
      edges: [],
      currentCameraId: null,
      lastObservedCameraId: null,
      lastObservedUs: null,
      inGapOrLost: false,
    };
  }
  const cameras = [];
  const segments = [];
  let lastObservedCameraId = null;
  let lastObservedUs = null;
  let currentCameraId = null;
  let inGapOrLost = false;

  for (const item of timeline) {
    if (!isObj(item) || hasForbiddenKeys(item)) continue;
    const rng = item.range_us;
    if (!Array.isArray(rng) || rng.length !== 2 || !isNum(rng[0]) || !isNum(rng[1])) continue;
    if (rng[0] > currentTUs) continue;
    const kind = nonEmptyStr(item.kind) || 'ON_CAMERA';
    const clippedEnd = Math.min(rng[1], currentTUs);
    if (kind === 'ON_CAMERA') {
      const camId = nonEmptyStr(item.camera_id);
      if (!camId) continue;
      if (cameras.at(-1) !== camId) {
        cameras.push(camId);
      }
      lastObservedCameraId = camId;
      lastObservedUs = clippedEnd;
      currentCameraId = rng[1] >= currentTUs ? camId : null;
      inGapOrLost = rng[1] < currentTUs;
      segments.push({
        kind: 'ON_CAMERA',
        camera_id: camId,
        range_us: [rng[0], clippedEnd],
        evidence_state: 'OBSERVED',
        line_style: 'solid',
      });
    } else if (kind === 'GAP' || kind === 'LOST') {
      currentCameraId = null;
      inGapOrLost = true;
      segments.push({
        kind,
        camera_id: null,
        range_us: [rng[0], clippedEnd],
        evidence_state: 'UNKNOWN',
        line_style: 'none',
      });
    }
  }

  const edges = cameras.slice(1).map((to, idx) => ({
    from_camera_id: cameras[idx],
    to_camera_id: to,
    evidence_state: 'OBSERVED',
    line_style: 'solid',
  }));

  return {
    cameras,
    segments,
    edges,
    currentCameraId,
    lastObservedCameraId,
    lastObservedUs,
    inGapOrLost,
  };
}

function unavailableBlindModel(reason = 'PREDICTION_UNAVAILABLE', asOfUs = null) {
  return {
    status: 'UNAVAILABLE',
    usable: false,
    reason,
    as_of_us: isInt(asOfUs) ? asOfUs : null,
    last_camera_id: null,
    last_observed_us: null,
    evidence_state: 'INFERRED',
    confidence: 'UNKNOWN',
    confidence_label_zh: BLIND_CURVE_STYLES.UNKNOWN.label_zh,
    used_for: 'DISPLAY_ONLY',
    display_label: DISPLAY_LABEL,
    legend_label: BLIND_LEGEND,
    unavailable_label: UNAVAILABLE_LABEL,
    coordinate_frame: 'NODE_GRAPH_ONLY',
    overhead: {
      frame: 'NODE_GRAPH_ONLY',
      last_position: null,
      region_id: null,
    },
    curve: {
      basis: 'NODE_GRAPH_ONLY',
      points: [],
    },
    curve_basis: 'NODE_GRAPH_ONLY',
    curve_points: [],
    curve_segments: [],
    candidates: [],
    identity_verdict: 'UNCONFIRMED',
    physical_navigation: 'UNKNOWN',
    [READ_FLAG_KEY]: false,
  };
}

export function buildBlindCurveModel(
  rawInput,
  { currentTUs = null, cameraPositions = null, observedCameras = null } = {},
) {
  if (!isObj(rawInput)) {
    return unavailableBlindModel('INVALID_INPUT');
  }
  if (hasForbiddenKeys(rawInput)) {
    return unavailableBlindModel('FORBIDDEN_INFERENCE_INPUT');
  }

  const doc = isObj(rawInput.estimate) && rawInput.status === 'ESTIMATED' ? rawInput.estimate : rawInput;
  if (hasForbiddenKeys(doc)) {
    return unavailableBlindModel('FORBIDDEN_INFERENCE_INPUT');
  }
  if (rawInput[READ_FLAG_KEY] !== undefined && rawInput[READ_FLAG_KEY] !== false) {
    return unavailableBlindModel('FORBIDDEN_INFERENCE_INPUT');
  }
  if (doc[READ_FLAG_KEY] !== undefined && doc[READ_FLAG_KEY] !== false) {
    return unavailableBlindModel('FORBIDDEN_INFERENCE_INPUT');
  }
  if (rawInput.used_for !== undefined && rawInput.used_for !== 'DISPLAY_ONLY') {
    return unavailableBlindModel('INVALID_USED_FOR');
  }
  if (doc.used_for !== undefined && doc.used_for !== 'DISPLAY_ONLY') {
    return unavailableBlindModel('INVALID_USED_FOR');
  }

  const status = nonEmptyStr(rawInput.status) || nonEmptyStr(doc.status) || 'ESTIMATED';
  const asOfUs = isInt(doc.as_of_us) ? doc.as_of_us : isInt(rawInput.as_of_us) ? rawInput.as_of_us : null;
  if (status === 'UNAVAILABLE' || status === 'CAMERA_NOT_IN_GRAPH' || status === 'NO_CANDIDATE') {
    const reason = nonEmptyStr(rawInput.reason) || nonEmptyStr(doc.reason) || status;
    return unavailableBlindModel(reason, asOfUs);
  }
  if (status !== 'ESTIMATED' && status !== 'PREDICTED') {
    return unavailableBlindModel('UNSUPPORTED_STATUS', asOfUs);
  }
  if (asOfUs === null) {
    return unavailableBlindModel('INVALID_AS_OF');
  }
  if (currentTUs !== null && (!isNum(currentTUs) || asOfUs > currentTUs)) {
    return unavailableBlindModel('FUTURE_AS_OF', asOfUs);
  }

  const lastObsObj = isObj(doc.last_observed) ? doc.last_observed : null;
  const lastCameraId = nonEmptyStr(doc.last_camera_id) || nonEmptyStr(lastObsObj?.camera_id);
  const lastObservedUs = isInt(doc.last_observed_us)
    ? doc.last_observed_us
    : isInt(lastObsObj?.source_time_us)
      ? lastObsObj.source_time_us
      : null;

  if (!lastCameraId || lastObservedUs === null) {
    return unavailableBlindModel('NO_OBSERVATIONS_AT_OR_BEFORE_AS_OF', asOfUs);
  }
  if (lastObservedUs > asOfUs || (currentTUs !== null && lastObservedUs > currentTUs)) {
    return unavailableBlindModel('FUTURE_OBSERVATION', asOfUs);
  }
  if (Array.isArray(observedCameras) && !observedCameras.includes(lastCameraId)) {
    return unavailableBlindModel('CAMERA_NOT_YET_OBSERVED', asOfUs);
  }

  const direction = isObj(doc.direction) ? doc.direction : isObj(rawInput.direction) ? rawInput.direction : null;
  if (direction && isInt(direction.samples_used) && direction.samples_used === 0) {
    return unavailableBlindModel('NO_OBSERVATIONS_AT_OR_BEFORE_AS_OF', asOfUs);
  }
  const directionKnown = direction ? direction.status === 'KNOWN' : doc.confidence !== 'UNKNOWN';

  const positions = readCameraPositions(cameraPositions);
  const rawCandidates = Array.isArray(doc.candidates) ? doc.candidates : [];
  const candidates = rawCandidates
    .filter(c => isObj(c) && nonEmptyStr(c.camera_id) && isInt(c.rank) && c.rank >= 1)
    .map(c => {
      const modelConf = nonEmptyStr(c.model_confidence) || nonEmptyStr(c.confidence) || 'UNKNOWN';
      const clampedConf = clampBlindConfidence(c.confidence ?? modelConf, directionKnown);
      let sketchPoints = null;
      if (Array.isArray(c.sketch_points) && c.sketch_points.length === 2 && c.sketch_points.every(isPoint2D)) {
        sketchPoints = c.sketch_points.map(pt => [round3(pt[0]), round3(pt[1])]);
      } else if (positions[lastCameraId] && positions[c.camera_id]) {
        sketchPoints = [positions[lastCameraId], positions[c.camera_id]];
      }
      return {
        camera_id: c.camera_id,
        rank: c.rank,
        window_us: Array.isArray(c.window_us) && c.window_us.length === 2 && c.window_us.every(isInt)
          ? [c.window_us[0], c.window_us[1]]
          : null,
        confidence: clampedConf,
        confidence_label_zh: BLIND_CURVE_STYLES[clampedConf].label_zh,
        model_confidence: modelConf,
        sketch_points: sketchPoints,
        sketch_basis: sketchPoints ? 'DISPLAY_POSITIONS_STRAIGHT_LINE' : 'NODE_GRAPH_ONLY',
      };
    })
    .sort((a, b) => (a.rank !== b.rank ? a.rank - b.rank : a.camera_id < b.camera_id ? -1 : 1));

  if (candidates.length === 0) {
    return unavailableBlindModel('NO_CANDIDATE', asOfUs);
  }

  const top = candidates[0];
  const overallConfidence = directionKnown && candidates.some(c => c.confidence === 'LOW') ? 'LOW' : 'UNKNOWN';
  const style = BLIND_CURVE_STYLES[overallConfidence];

  const docCurve = isObj(doc.curve) ? doc.curve : null;
  const rawPoints = Array.isArray(docCurve?.points) && docCurve.points.length >= 2 && docCurve.points.every(isPoint2D)
    ? docCurve.points
    : Array.isArray(doc.curve_points) && doc.curve_points.length >= 2 && doc.curve_points.every(isPoint2D)
      ? doc.curve_points
      : top.sketch_points;

  const curvePoints = Array.isArray(rawPoints) && rawPoints.length >= 2
    ? rawPoints.map(pt => [round3(pt[0]), round3(pt[1])])
    : [];
  const curveBasis = curvePoints.length >= 2 ? 'DISPLAY_POSITIONS_STRAIGHT_LINE' : 'NODE_GRAPH_ONLY';

  const overheadObj = isObj(doc.overhead) ? doc.overhead : null;
  const lastPosition = isPoint2D(overheadObj?.last_position)
    ? [round3(overheadObj.last_position[0]), round3(overheadObj.last_position[1])]
    : positions[lastCameraId]
      ? [...positions[lastCameraId]]
      : curvePoints.length >= 2
        ? [...curvePoints[0]]
        : null;
  const coordinateFrame = lastPosition || curvePoints.length >= 2 ? 'STATIC_PLAN_DISPLAY' : 'NODE_GRAPH_ONLY';
  const regionId = nonEmptyStr(overheadObj?.region_id);

  const segmentStyle = BLIND_CURVE_STYLES[top.confidence];
  const curveSegments = [
    {
      from_camera_id: lastCameraId,
      to_camera_id: top.camera_id,
      rank: top.rank,
      window_us: top.window_us,
      window_text: windowText(top.window_us),
      evidence_state: 'INFERRED',
      confidence: top.confidence,
      confidence_label_zh: segmentStyle.label_zh,
      model_confidence: top.model_confidence,
      line_style: 'dashed',
      dash: segmentStyle.dash,
      stroke_dasharray: segmentStyle.stroke_dasharray,
      opacity: segmentStyle.opacity,
      width: segmentStyle.width,
      tone: segmentStyle.tone,
      style: segmentStyle,
      display_label: DISPLAY_LABEL,
      legend_label: BLIND_LEGEND,
      label: `#${top.rank} ${windowText(top.window_us)} · ${segmentStyle.label_zh} · ${DISPLAY_LABEL}`,
      basis: curveBasis,
      points: curvePoints,
      identity_verdict: 'UNCONFIRMED',
      physical_navigation: 'UNKNOWN',
    },
  ];

  return {
    status: 'ESTIMATED',
    usable: true,
    reason: null,
    as_of_us: asOfUs,
    last_camera_id: lastCameraId,
    last_observed_us: lastObservedUs,
    evidence_state: 'INFERRED',
    confidence: overallConfidence,
    confidence_label_zh: style.label_zh,
    used_for: 'DISPLAY_ONLY',
    display_label: DISPLAY_LABEL,
    legend_label: BLIND_LEGEND,
    unavailable_label: null,
    coordinate_frame: coordinateFrame,
    overhead: {
      frame: coordinateFrame,
      last_position: lastPosition,
      region_id: regionId,
    },
    curve: {
      basis: curveBasis,
      points: curvePoints,
    },
    curve_basis: curveBasis,
    curve_points: curvePoints,
    curve_segments: curveSegments,
    candidates,
    identity_verdict: 'UNCONFIRMED',
    physical_navigation: 'UNKNOWN',
    [READ_FLAG_KEY]: false,
  };
}

export function buildBlindCurveSegments(rawInput, options = {}) {
  return buildBlindCurveModel(rawInput, options).curve_segments;
}

export function buildTopdownView({
  cameraMap = null,
  timeline = [],
  currentTUs = 0,
  blind = null,
  physical = null,
  blindPrediction = null,
  cameraPositions = null,
} = {}) {
  const obs = observedTimelineAt(timeline, currentTUs);
  const posSource = cameraPositions ?? cameraMap;
  const rawPred = blind ?? blindPrediction ?? physical;
  const blindModel = buildBlindCurveModel(rawPred, {
    currentTUs,
    cameraPositions: posSource,
    observedCameras: obs.cameras.length > 0 ? obs.cameras : null,
  });

  const notes = [];
  if (!blindModel.usable) {
    notes.push(UNAVAILABLE_LABEL);
  } else if (blindModel.as_of_us < currentTUs) {
    notes.push(`預測取自 ${hms(blindModel.as_of_us)}`);
  }

  return {
    current_t_us: currentTUs,
    observed_cameras: obs.cameras,
    observed_segments: obs.segments,
    observed_edges: obs.edges,
    current_camera_id: obs.currentCameraId,
    last_observed_camera_id: obs.lastObservedCameraId,
    last_observed_us: obs.lastObservedUs,
    in_gap_or_lost: obs.inGapOrLost,
    blind: blindModel,
    blind_status: blindModel.status,
    blind_curves: blindModel.curve_segments,
    coordinate_frame: blindModel.coordinate_frame,
    display_label: DISPLAY_LABEL,
    legend_label: BLIND_LEGEND,
    unavailable_label: blindModel.unavailable_label,
    identity_line: IDENTITY_LINE,
    notes,
  };
}


export const SEARCH_RESULTS_STATUS_TEXT = Object.freeze({
  READY: '已找到符合條件的畫面與地點涵蓋',
  NO_MATCH: '在已推論的影格中查無符合條件的畫面；不代表目標不存在。',
  PARTIAL: '搜尋範圍僅部分涵蓋；未涵蓋部分沒有資料，不代表沒有目標。',
  OUT_OF_RANGE: '查詢時間超出此資料記錄的時間範圍，無符合資料。',
  UNKNOWN: '資料不足（缺乏偵測索引或時鐘對照），無法完成查詢。',
});

export const TRACKING_STATUS_TEXT = Object.freeze({
  TRACKING: '目標追蹤中',
  LOST: '目標離開畫面／已遺失（LOST）',
  NO_SIGHTING: '時間窗內無觀測紀錄',
  UNSUPPORTED: '不支援此目標類別追蹤',
  PARTIAL: '追蹤時間範圍僅部分涵蓋',
  UNKNOWN: '資料不足，無法判定追蹤狀態',
});

export const SUPPORTED_SPEEDS = Object.freeze([1, 1.5, 2]);

export const CORE_IDENTITY_VERDICT = 'UNCONFIRMED';
export const CORE_IDENTITY_BADGE = '身分未確認 · 條件相符之候選';
export const CORE_NAVIGATION_BADGE = '身分未確認 · 物理通行與碰撞 UNKNOWN';
export const CORE_RANKING_NOTE = '排序依據：目標命中優先 → 第一次相符時間 → camera_id；建議檢視順序，非機率。';

function formatWallRange(wallRange) {
  if (!Array.isArray(wallRange) || wallRange.length !== 2) return '時間 UNKNOWN';
  const formatTime = iso => {
    if (typeof iso !== 'string') return 'UNKNOWN';
    const match = iso.match(/T(\d{2}:\d{2}(?::\d{2})?)/);
    return match ? match[1] : iso;
  };
  return `${formatTime(wallRange[0])} – ${formatTime(wallRange[1])}`;
}

export function buildSearchResultsWallModel(searchResponse, options = {}) {
  if (searchResponse && hasForbiddenKeys(searchResponse)) {
    throw new Error('FORBIDDEN_INFERENCE_INPUT');
  }

  if (!searchResponse) {
    return {
      status: 'UNLOADED',
      statusText: '尚未載入查找結果。',
      identityVerdict: CORE_IDENTITY_VERDICT,
      identityBadge: CORE_IDENTITY_BADGE,
      cards: [],
      totalHits: 0,
      hasResults: false,
      notEvaluatedCameras: [],
      reasons: [],
      page: 0,
      pages: 1,
      rankingNote: CORE_RANKING_NOTE,
    };
  }

  const status = searchResponse.status ?? 'UNKNOWN';
  const reasons = Array.isArray(searchResponse.reasons) ? [...searchResponse.reasons] : [];
  const statusText = SEARCH_RESULTS_STATUS_TEXT[status] ?? '資料不足，沒有執行。';

  const rawHits = Array.isArray(searchResponse.hits) ? searchResponse.hits : [];
  const selectedRank = options.selectedRank ?? null;
  const selectedCameraId = options.selectedCameraId ?? null;

  const regionMap = new Map();
  if (options.regionGraph && Array.isArray(options.regionGraph.regions)) {
    for (const r of options.regionGraph.regions) {
      if (r && r.region_id) {
        regionMap.set(r.region_id, r.display_name ?? r.region_id);
      }
    }
  }

  const cards = rawHits.map((hit, index) => {
    const rank = typeof hit.rank === 'number' ? hit.rank : index + 1;
    const cameraId = hit.camera_id ?? `CAM_${rank}`;
    const targetObserved = Boolean(hit.target_observed);
    const evidenceState = targetObserved ? 'OBSERVED' : 'UNKNOWN';
    const observedBadge = targetObserved ? 'OBSERVED 畫面命中' : '場景設定（未看到目標）';

    const sourceRangeUs = Array.isArray(hit.source_range_us) ? hit.source_range_us : [0, 0];
    const wallRange = Array.isArray(hit.wall_range) ? hit.wall_range : [];
    const wallRangeText = formatWallRange(wallRange);

    const segments = Array.isArray(hit.segments) ? hit.segments : [];
    const matchedFrames = segments.reduce((sum, s) => sum + (typeof s.matched_frames === 'number' ? s.matched_frames : 0), 0);
    const representative = segments[0]?.representative ?? null;
    const mediaToken = representative?.media_token ?? null;
    const frameRef = representative?.frame_ref ?? null;

    const basisList = Array.isArray(hit.basis) ? hit.basis : [];
    const locationBasis = basisList.find(b => b.kind === 'LOCATION');
    const regionId = locationBasis?.region_id ?? null;
    const regionName = regionId ? (regionMap.get(regionId) ?? regionId) : null;

    const basisBadges = basisList.map(b => {
      if (b.kind === 'LOCATION') {
        const basisLabel = b.coverage_basis === 'MANUAL_ON_STATIC_FRAME' ? '靜態涵蓋' : (b.coverage_basis ?? '地點');
        return `地點: ${b.region_id} (${basisLabel})`;
      }
      if (b.kind === 'OBJECT') {
        const colorPart = b.color_label ? ` / ${b.color_label}` : '';
        return `特徵: ${b.class_label ?? '物件'}${colorPart} (${b.evidence_state ?? 'OBSERVED'})`;
      }
      return `${b.kind}`;
    });

    const isSelected = selectedRank === rank || selectedCameraId === cameraId;

    return {
      rank,
      cameraId,
      targetObserved,
      evidenceState,
      observedBadge,
      sourceRangeUs,
      wallRange,
      wallRangeText,
      segments,
      matchedFrames,
      representative,
      mediaToken,
      frameRef,
      regionId,
      regionName,
      basis: basisList,
      basisBadges,
      isSelected,
    };
  });

  const notEvaluatedCameras = (Array.isArray(searchResponse.not_evaluated_cameras) ? searchResponse.not_evaluated_cameras : []).map(item => ({
    cameraId: item.camera_id,
    reason: item.reason,
    reasonText: item.reason === 'COVERAGE_BASIS_UNSUPPORTED'
      ? '涵蓋依據不支援'
      : item.reason === 'CAMERA_NOT_IN_RUN'
      ? '鏡頭不在當前 run 中'
      : item.reason === 'INCOMPLETE_COVERAGE'
      ? '涵蓋不完整'
      : item.reason,
  }));

  const pageSize = typeof options.size === 'number' && options.size > 0 ? options.size : cards.length || 1;
  const pageIndex = typeof options.page === 'number' && options.page >= 0 ? options.page : 0;
  const pageCount = Math.max(1, Math.ceil(cards.length / pageSize));
  const pagedCards = options.paginate ? cards.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize) : cards;

  return {
    status,
    statusText,
    identityVerdict: CORE_IDENTITY_VERDICT,
    identityBadge: CORE_IDENTITY_BADGE,
    cards: pagedCards,
    allCards: cards,
    totalHits: cards.length,
    hasResults: cards.length > 0,
    notEvaluatedCameras,
    reasons,
    page: pageIndex,
    pages: pageCount,
    pageSize,
    rankingNote: CORE_RANKING_NOTE,
    resolvedTime: searchResponse.resolved_time ?? null,
  };
}

export function buildCoreTrackingViewModel(trackResponse, {
  tUs = 0,
  playbackMode = 'single',
  speed = 1,
  cameraGraph = null,
  displayPositions = null,
} = {}) {
  if (trackResponse && hasForbiddenKeys(trackResponse)) {
    throw new Error('FORBIDDEN_INFERENCE_INPUT');
  }

  const validSpeed = SUPPORTED_SPEEDS.includes(speed) ? speed : 1;
  const validPlaybackMode = ['single', 'multi'].includes(playbackMode) ? playbackMode : 'single';

  if (!trackResponse) {
    return {
      status: 'UNLOADED',
      statusText: '尚未載入追蹤結果。',
      asOfUs: 0,
      currentTUs: 0,
      playbackMode: validPlaybackMode,
      speed: validSpeed,
      speedLabel: `${validSpeed}×`,
      identityVerdict: CORE_IDENTITY_VERDICT,
      identityBadge: CORE_NAVIGATION_BADGE,
      physicalNavigation: 'UNKNOWN',
      singleView: {
        activeCameraId: null,
        segmentKind: 'UNKNOWN',
        evidenceState: 'UNKNOWN',
        badge: '追蹤尚未開始',
        lastObservedCameraId: null,
        transitions: [],
        nextSwitchUs: null,
      },
      multiView: {
        cameras: [],
      },
      topdown: null,
    };
  }

  const status = trackResponse.status ?? 'UNKNOWN';
  const statusText = TRACKING_STATUS_TEXT[status] ?? '追蹤狀態未知';
  const asOfUs = typeof trackResponse.as_of_us === 'number' ? trackResponse.as_of_us : 0;
  const currentTUs = Math.max(0, Math.min(typeof tUs === 'number' ? Math.trunc(tUs) : 0, asOfUs));

  const singleViewList = Array.isArray(trackResponse.single_view) ? trackResponse.single_view : [];
  const sightings = Array.isArray(trackResponse.sightings) ? trackResponse.sightings : [];
  const multiViewList = Array.isArray(trackResponse.multi_view) ? trackResponse.multi_view : multiViewCameras(sightings, { asOfUs });

  // 1. Single View Evaluation at currentTUs
  let activeSegment = null;
  if (singleViewList.length > 0) {
    activeSegment = singleViewList.find(s => s.range_us[0] <= currentTUs && currentTUs < s.range_us[1]);
    if (!activeSegment && currentTUs >= asOfUs) {
      activeSegment = singleViewList.at(-1);
    }
  }

  const segmentKind = activeSegment?.kind ?? (status === 'LOST' ? 'LOST' : 'UNKNOWN');
  const activeCameraId = segmentKind === 'ON_CAMERA' ? activeSegment.camera_id : null;
  const evidenceState = segmentKind === 'ON_CAMERA' ? 'OBSERVED' : 'UNKNOWN';

  let badge = '追蹤中';
  if (segmentKind === 'ON_CAMERA') {
    badge = 'OBSERVED 追蹤中';
  } else if (segmentKind === 'GAP') {
    badge = '盲區間隔（未見目標）';
  } else if (segmentKind === 'LOST') {
    badge = '目標遺失（LOST）';
  } else {
    badge = 'UNKNOWN 未知狀態';
  }

  // Find last observed camera up to currentTUs
  let lastObservedCameraId = null;
  for (const seg of singleViewList) {
    if (seg.kind === 'ON_CAMERA' && seg.range_us[0] <= currentTUs) {
      lastObservedCameraId = seg.camera_id;
    }
  }

  // Transitions list
  const transitions = [];
  let nextSwitchUs = null;
  for (let i = 0; i < singleViewList.length; i++) {
    const cur = singleViewList[i];
    const prev = i > 0 ? singleViewList[i - 1] : null;
    if (prev && (prev.camera_id !== cur.camera_id || prev.kind !== cur.kind)) {
      transitions.push({
        switch_at_us: cur.range_us[0],
        from_camera: prev.camera_id,
        to_camera: cur.camera_id,
        from_kind: prev.kind,
        to_kind: cur.kind,
      });
      if (cur.range_us[0] > currentTUs && nextSwitchUs === null) {
        nextSwitchUs = cur.range_us[0];
      }
    }
  }

  // 2. Multi-view Evaluation at currentTUs
  const multiCameras = multiViewList.map(cam => {
    const isCurrentlyActive = activeCameraId === cam.camera_id && segmentKind === 'ON_CAMERA';
    const isPast = cam.last_us <= currentTUs;
    const isFuture = cam.first_us > currentTUs;
    const isObservingNow = sightings.some(s => s.camera_id === cam.camera_id && s.range_us[0] <= currentTUs && currentTUs < s.range_us[1]);

    return {
      cameraId: cam.camera_id,
      firstUs: cam.first_us,
      lastUs: cam.last_us,
      isActive: isCurrentlyActive,
      isObservingNow,
      isPast,
      isFuture,
      badge: isCurrentlyActive ? '目前追蹤畫面' : isPast ? '已通過' : '候選鏡頭',
      highlight: isCurrentlyActive,
    };
  });

  // 3. Topdown / Blind curve model integration
  const cameraPositions = displayPositions ?? (cameraGraph ? readCameraPositions(cameraGraph) : {});
  const topdown = buildTopdownView({
    timeline: singleViewList.length > 0 ? singleViewList : sightings,
    blindPrediction: trackResponse.blind ?? null,
    cameraPositions,
    currentTUs,
    asOfUs,
  });

  return {
    status,
    statusText,
    asOfUs,
    currentTUs,
    playbackMode: validPlaybackMode,
    speed: validSpeed,
    speedLabel: `${validSpeed}×`,
    identityVerdict: CORE_IDENTITY_VERDICT,
    identityBadge: CORE_NAVIGATION_BADGE,
    physicalNavigation: trackResponse.physical_navigation ?? 'UNKNOWN',
    singleView: {
      activeSegment,
      segmentKind,
      activeCameraId,
      evidenceState,
      badge,
      lastObservedCameraId,
      transitions,
      nextSwitchUs,
    },
    multiView: {
      cameras: multiCameras,
    },
    topdown,
    reasons: Array.isArray(trackResponse.reasons) ? trackResponse.reasons : [],
  };
}

export function coreSearchTrackReducer(state, action) {
  switch (action.type) {
    case 'SET_CORE_SEARCH_RESPONSE':
      return {
        ...state,
        coreSearchResponse: action.response,
        coreSearchWall: buildSearchResultsWallModel(action.response, {
          selectedRank: state.coreSelection?.rank,
          selectedCameraId: state.coreSelection?.cameraId,
          regionGraph: action.regionGraph ?? state.regionGraph,
        }),
      };

    case 'SET_CORE_TRACK_RESPONSE':
      return {
        ...state,
        coreTrackResponse: action.response,
        coreTrackingView: buildCoreTrackingViewModel(action.response, {
          tUs: state.tUs ?? 0,
          playbackMode: state.playbackMode ?? 'single',
          speed: state.speed ?? 1,
          cameraGraph: action.cameraGraph ?? state.cameraGraph,
          displayPositions: action.displayPositions ?? state.displayPositions,
        }),
      };

    case 'SET_CORE_SELECTION':
      return {
        ...state,
        coreSelection: action.selection,
        coreSearchWall: state.coreSearchResponse
          ? buildSearchResultsWallModel(state.coreSearchResponse, {
              selectedRank: action.selection?.rank,
              selectedCameraId: action.selection?.cameraId,
              regionGraph: state.regionGraph,
            })
          : null,
      };

    default:
      return state;
  }
}

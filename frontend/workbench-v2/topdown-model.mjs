// Pure model for top-down blind-zone curve rendering (DEMO_UI_SUPPORT_V1 §6.4 / §7).
// Display only: no scoring and no Q5 switching authority.

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
  cameraPositions = null,
} = {}) {
  const obs = observedTimelineAt(timeline, currentTUs);
  const posSource = cameraPositions ?? cameraMap;
  const rawPred = blind ?? physical;
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

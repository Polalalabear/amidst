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

import {
  buildTopdownView,
  readCameraPositions,
  hasForbiddenKeys,
} from './topdown-model.mjs';

export { buildTopdownView, readCameraPositions, hasForbiddenKeys };

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
    blind: trackResponse.blind ?? null,
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

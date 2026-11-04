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

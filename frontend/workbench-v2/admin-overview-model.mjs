// Pure model for the admin overview. Inputs are the bootstrap payload (what the server declares), a snapshot and an
// event log that the front desk writes into this browser's localStorage, nothing else. A figure with no measured
// source stays null; the view prints 尚未量測 for it. No example values.
import { NOT_MEASURED, classDisplay, normalizeLog } from './ui-model.mjs';

export const HISTORY_LIMIT = 12;
const sum = list => list.reduce((n, x) => n + x, 0);
const rangeLen = r => (Array.isArray(r) ? r[1] - r[0] : Array.isArray(r?.range_us) ? r.range_us[1] - r.range_us[0] : 0);

export function activeRunOf(bootstrap, snapshot = null) {
  const runs = bootstrap?.runs ?? [];
  return runs.find(r => r.scene_id === snapshot?.sceneId && r.run_id === snapshot?.runId) ?? runs[0] ?? null;
}

// Fraction of the index grid with no inference (MISSING), across the run's cameras. Null when the run says nothing.
export function missingRate(run) {
  const cams = run?.sampling?.per_camera ?? [];
  const inferred = sum(cams.flatMap(c => (c.inferred_ranges_us ?? []).map(rangeLen)));
  const missing = sum(cams.flatMap(c => (c.not_inferred ?? []).map(rangeLen)));
  return inferred + missing > 0 ? missing / (inferred + missing) : null;
}

export function cameraStatus(run, trackingCamera = null) {
  const per = new Map((run?.sampling?.per_camera ?? []).map(c => [c.camera_id, c]));
  return (run?.camera_ids ?? []).map(id => {
    const cam = per.get(id);
    const has = cam ? (cam.inferred_ranges_us ?? []).length > 0 : false;
    return { id, state: id === trackingCamera ? 'tracking' : has ? 'data' : 'missing' };
  });
}

export function perCameraCounts(snapshot, run) {
  const rows = snapshot?.lastSearch?.perCamera;
  if (Array.isArray(rows) && rows.length) {
    return rows.map(r => ({ cameraId: r.cameraId, person: r.person ?? 0, object: r.object ?? 0, total: (r.person ?? 0) + (r.object ?? 0), measured: true }))
      .sort((a, b) => b.total - a.total || a.cameraId.localeCompare(b.cameraId));
  }
  return (run?.camera_ids ?? []).map(id => ({ cameraId: id, person: 0, object: 0, total: 0, measured: false }));
}
// Matched frames of one search response by camera and class (person / other objects). Built by the front desk.
export function countsFromSearch(response) {
  const rows = new Map();
  for (const hit of response?.hits ?? []) {
    const row = rows.get(hit.camera_id) ?? { cameraId: hit.camera_id, person: 0, object: 0 };
    const frames = sum((hit.segments ?? []).map(s => (typeof s.matched_frames === 'number' ? s.matched_frames : 0)));
    const klass = (hit.basis ?? []).find(b => b.kind === 'OBJECT')?.class_label;
    if (klass === 'person') row.person += frames; else if (klass) row.object += frames;
    rows.set(hit.camera_id, row);
  }
  return [...rows.values()];
}

export function bins10s(log, now = Date.now()) {
  const entries = normalizeLog(log);
  if (!entries.length) return { bins: [], from: null, to: null };
  const first = Math.floor(entries[0].at / 10000) * 10000, last = Math.floor(Math.max(entries.at(-1).at, now) / 10000) * 10000;
  const count = Math.min(24, Math.floor((last - first) / 10000) + 1), origin = last - (count - 1) * 10000;
  const bins = Array.from({ length: count }, (_, i) => ({ at: origin + i * 10000, OBSERVED: 0, INFERRED: 0, MISSING: 0, UNKNOWN: 0 }));
  for (const e of entries) { const i = Math.floor((e.at - origin) / 10000); if (i >= 0 && i < count) bins[i][e.state]++; }
  return { bins, from: origin, to: last + 10000 };
}

const fmtSec = ms => (ms == null ? null : (ms / 1000).toFixed(ms < 10000 ? 2 : 1));
export function sparkPoints(values, w = 220, h = 40, pad = 4) {
  const v = (values ?? []).filter(Number.isFinite);
  if (v.length < 2) return null;
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  return v.map((x, i) => `${(i * w / (v.length - 1)).toFixed(1)},${(h - pad - ((x - lo) / span) * (h - 2 * pad)).toFixed(1)}`).join(' ');
}

export function buildOverview({ bootstrap = null, snapshot = null, log = [], now = Date.now() } = {}) {
  const run = activeRunOf(bootstrap, snapshot);
  const entries = normalizeLog(log);
  const track = snapshot?.lastTrack ?? null, search = snapshot?.lastSearch ?? null;
  const cams = cameraStatus(run, track?.cameraId ?? null);
  const withData = cams.filter(c => c.state !== 'missing').length;
  const runs = bootstrap?.runs ?? [];
  const indexed = runs.filter(r => typeof r.detection_index_sha256 === 'string' && r.detection_index_sha256).length;
  const missing = missingRate(run);
  const share = track?.blindShare ?? null;
  const lock = track?.lockMs ?? null, find = search?.ms ?? null;
  const metric = (key, label, value, unit, note, history = null, target = null) => ({ key, label, value, unit, note, history, spark: sparkPoints(history), target, measured: value !== null && value !== undefined });
  const latest = entries.at(-1) ?? null;
  const regions = (run?.region_graph?.regions ?? []).map(r => ({ id: r.region_id, name: r.display_name ?? r.region_id }));
  return {
    originText: bootstrap ? `${bootstrap.data_origin} · ${bootstrap.status}` : 'UNKNOWN',
    sceneText: run ? `${run.scene_id} · ${run.run_id}` : null,
    cameras: { total: cams.length, withData, list: cams },
    tracking: track ? { target: classDisplay(track.classLabel ?? '目標', run?.supported_classes?.aliases), cameraId: track.cameraId ?? null, state: track.state ?? 'UNKNOWN', autoSeed: Boolean(track.autoSeed), reasons: track.reasons ?? [] } : null,
    latest,
    regions,
    metrics: [
      metric('speed', '偵測速度', null, '張/秒', '尚無偵測速度的實測來源'),
      metric('switch', '鏡頭切換 P90', null, '秒', '尚無切換延遲的實測來源'),
      metric('lock', '首次鎖定', fmtSec(lock), '秒', '本機量測：送出到追蹤結果', snapshot?.history?.lock ?? null),
      metric('find', '查找耗時', fmtSec(find), '秒', '本機量測：送出到結果牆', snapshot?.history?.find ?? null),
      metric('agent', 'Agent 回應', null, '秒', '尚無 Agent 回應時間的實測來源'),
      metric('missing', '缺幀率', missing === null ? null : (missing * 100).toFixed(1), '%', 'MISSING 幀 ÷ 全部幀（來源宣告）'),
      metric('blind', '盲區占比', share === null ? null : Math.round(share * 100), '%', '追蹤時間中沒有任何鏡頭看到'),
      metric('index', '索引狀態', runs.length ? `${indexed} / ${runs.length}` : null, '來源', '已綁定偵測索引的來源'),
    ],
    perCamera: perCameraCounts(snapshot, run),
    perCameraNote: search ? '最近一次查找的相符影格數' : NOT_MEASURED,
    timeline: bins10s(entries, now),
    events: entries.slice().reverse(),
  };
}

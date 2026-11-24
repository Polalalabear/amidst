// Pure model: topdown/track view model + N6 camera asset -> 3D scene data (#605, D316).
// Only system output goes in: camera calibration, active camera, switch events and the OPTIONAL system
// estimate (est_xy / uncertainty_m). Ground Truth and renderer-side data never enter;
// input carrying the keys the inference guard forbids makes the estimate UNKNOWN. Coordinates: Blender metres (x, y) for ground
// points; three world (Y-up) for camera poses straight from cameras.three.json.
import { hasForbiddenKeys } from './topdown-model.mjs';

export const SCENE3D_UNKNOWN = 'UNKNOWN';
export const SCENE3D_LEGEND = Object.freeze({
  estimateAbsent: '沒有系統估計',
  noWalls: '不確定範圍為圓形，未考慮牆（UNKNOWN：可達區域資料缺少）',
  clipped: '不確定範圍已依牆線裁切（可達區域資料）',
  frustum: '視野錐長度僅為示意，不是實際可見範圍',
});

// Reason codes of display_estimate (docs/contracts/Q_CORE_SEARCH_TRACK_V1.md, 相容新增：display_estimate). Unknown codes are shown raw.
export const ESTIMATE_REASON_TEXT = Object.freeze({
  CALIBRATION_MISSING: '無對應校正，無法估計位置',
  NO_PROJECTABLE_SELECTED_OBSERVATION: '目前時間點之前沒有被選中的觀測，無法估計位置',
  AMBIGUOUS_SELECTED_OBSERVATIONS: '最新時間點有多個可投影的已選觀測，無法決定唯一位置',
  FOOT_TRUNCATED_AT_FRAME_BOTTOM: '腳點被畫面底邊截斷，無法估計位置',
  GROUND_PROJECTION_UNDEFINED: '地面投影無定義（框座標或投影結果不是有限數），無法估計位置',
});
export function estimateUnknownText(reason) {
  if (reason == null || reason === 'ESTIMATE_SOURCE_MISSING') return SCENE3D_LEGEND.estimateAbsent;
  const text = Object.hasOwn(ESTIMATE_REASON_TEXT, reason) ? ESTIMATE_REASON_TEXT[reason] : null;
  return text ? `估計位置 UNKNOWN：${text}（${reason}）` : `估計位置 UNKNOWN（${reason}）`;
}

const isPair = v => Array.isArray(v) && v.length === 2 && v.every(Number.isFinite);
const round = (n, d = 4) => Math.round(n * 10 ** d) / 10 ** d;

/** Blender (x, y) ground point of a catalog camera (three world is (x, z, -y)). */
export function cameraGroundXy(camera) {
  const m = camera?.camera_to_world;
  return [m[0][3], -m[2][3]];
}

export function buildCameraModels(cameras, { activeCameraId = null, gapCameraId = null } = {}) {
  return (Array.isArray(cameras) ? cameras : []).map(c => {
    const m = c.camera_to_world;
    return {
      id: c.camera_id,
      position: [m[0][3], m[1][3], m[2][3]],
      groundXy: cameraGroundXy(c),
      cameraToWorld: m.flat(),
      fovYRad: round(2 * Math.atan(c.cy / c.fy), 6),
      aspect: round(c.width / c.height, 6),
      isActive: c.camera_id === activeCameraId,
      isGapLast: c.camera_id === gapCameraId && c.camera_id !== activeCameraId,
    };
  });
}

/** Ray-march an uncertainty disc against wall segments: each ray stops at the nearest wall hit. */
export function clipUncertaintyFan(center, radius, wallSegments, rays = 48) {
  if (!isPair(center) || !Number.isFinite(radius) || radius <= 0) return [];
  const segs = (Array.isArray(wallSegments) ? wallSegments : []).filter(s => Array.isArray(s) && isPair(s[0]) && isPair(s[1]));
  const pts = [];
  for (let i = 0; i < rays; i++) {
    const a = (i / rays) * Math.PI * 2, dx = Math.cos(a), dy = Math.sin(a);
    let best = radius;
    for (const [[ax, ay], [bx, by]] of segs) {
      const ex = bx - ax, ey = by - ay, den = dx * ey - dy * ex;
      if (Math.abs(den) < 1e-12) continue;
      const t = ((ax - center[0]) * ey - (ay - center[1]) * ex) / den;
      const u = ((ax - center[0]) * dy - (ay - center[1]) * dx) / den;
      if (t > 1e-9 && u >= 0 && u <= 1 && t < best) best = t;
    }
    pts.push([round(center[0] + dx * best), round(center[1] + dy * best)]);
  }
  return pts;
}

/** Validates the optional system estimate; anything malformed or GT-tainted becomes UNKNOWN. */
export function readEstimate(estimate, currentTUs = null) {
  const unknown = reason => ({ status: SCENE3D_UNKNOWN, reason, xy: null, uncertaintyM: null, track: [], wallSegments: [] });
  if (estimate == null) return unknown('ESTIMATE_SOURCE_MISSING');
  if (hasForbiddenKeys(estimate)) return unknown('FORBIDDEN_KEYS_REJECTED');
  if (!isPair(estimate.est_xy)) return unknown('EST_XY_MISSING');
  const u = estimate.uncertainty_m;
  const track = (Array.isArray(estimate.track) ? estimate.track : [])
    .filter(p => p && Number.isFinite(p.t_us) && isPair(p.est_xy) && (currentTUs == null || p.t_us <= currentTUs))
    .map(p => ({ tUs: p.t_us, xy: p.est_xy }));
  return {
    status: 'INFERRED',
    reason: null,
    xy: estimate.est_xy,
    uncertaintyM: Number.isFinite(u) && u >= 0 ? u : SCENE3D_UNKNOWN,
    track,
    wallSegments: Array.isArray(estimate.wall_segments_xy) ? estimate.wall_segments_xy : [],
  };
}

/** Blind (GAP) intervals and switch events from the single-view transition list. */
export function readTransitions(transitions, currentTUs) {
  const list = (Array.isArray(transitions) ? transitions : []).filter(t => Number.isFinite(t?.switch_at_us)).sort((a, b) => a.switch_at_us - b.switch_at_us);
  const switches = list.filter(t => t.switch_at_us <= currentTUs && t.to_camera).map(t => ({ tUs: t.switch_at_us, from: t.from_camera ?? null, to: t.to_camera }));
  const blind = [];
  for (let i = 0; i < list.length; i++) {
    if (list[i].to_kind !== 'GAP') continue;
    const next = list.slice(i + 1).find(t => t.to_kind !== 'GAP');
    blind.push({ startUs: list[i].switch_at_us, endUs: next?.switch_at_us ?? null, lastCamera: list[i].from_camera ?? null });
  }
  return { switches, blind };
}

export function scene3dStateText(view) {
  if (view?.status === 'NO_SIGHTING') return '目前沒有觀測紀錄';
  return ({ON_CAMERA: '追蹤中', GAP: '盲區（未見目標）', LOST: '目標遺失', PENDING: '目標尚未出現'})[view?.singleView?.segmentKind] ?? '追蹤狀態 UNKNOWN';
}

export function buildScene3dModel({ view = null, cameraAsset = null, estimate = null } = {}) {
  const single = view?.singleView ?? {};
  const currentTUs = Number.isFinite(view?.currentTUs) ? view.currentTUs : 0;
  const kind = single.segmentKind ?? SCENE3D_UNKNOWN;
  const { switches, blind } = readTransitions(single.transitions, currentTUs);
  const topdownReason = view?.topdown?.estimate_reason;
  const raw = estimate ?? view?.topdown?.estimate ?? null;
  const est = raw == null && typeof topdownReason === 'string' && topdownReason
    ? { status: SCENE3D_UNKNOWN, reason: topdownReason, xy: null, uncertaintyM: null, track: [], wallSegments: [] }
    : readEstimate(raw, currentTUs);
  const cameras = buildCameraModels(cameraAsset?.cameras, {
    activeCameraId: single.activeCameraId ?? null,
    gapCameraId: kind === 'GAP' ? single.lastObservedCameraId ?? null : null,
  });
  const byId = new Map(cameras.map(c => [c.id, c]));
  const lastSwitch = switches.at(-1) ?? null;
  const clipped = est.status === 'INFERRED' && est.wallSegments.length > 0 && Number.isFinite(est.uncertaintyM);
  const legend = [SCENE3D_LEGEND.frustum];
  if (est.status === SCENE3D_UNKNOWN) legend.push(estimateUnknownText(est.reason));
  else legend.push(clipped ? SCENE3D_LEGEND.clipped : SCENE3D_LEGEND.noWalls);
  return {
    available: cameras.length > 0,
    catalogSha256: cameraAsset?.source_catalog_sha256 ?? SCENE3D_UNKNOWN,
    currentTUs,
    segmentKind: kind,
    stateText: scene3dStateText(view),
    activeCameraId: single.activeCameraId ?? null,
    lastObservedCameraId: single.lastObservedCameraId ?? null,
    cameras,
    estimate: {
      status: est.status,
      reason: est.reason,
      xy: est.xy,
      uncertaintyM: est.uncertaintyM,
      trail: est.track.map(p => p.xy),
      uncertaintyFan: clipped ? clipUncertaintyFan(est.xy, est.uncertaintyM, est.wallSegments) : [],
      clipped,
    },
    blindIntervals: blind,
    switchMarker: lastSwitch && byId.has(lastSwitch.to) ? { ...lastSwitch, groundXy: byId.get(lastSwitch.to).groundXy } : null,
    legend,
  };
}

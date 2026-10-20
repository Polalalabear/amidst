// D44/D45 uncertainty rules for the v2 workbench. Pure; no DOM.
// Field names follow contract v1.1 (#65 @ 98451bd §2.4, §6.3.1, §6.4). The validation mirrors the backend
// skeleton `controlled_scene_api.py` @ 6e1c439 (#75): same error codes, same grade thresholds, same closed
// curve kinds. Where this file is stricter than #75 the rule is marked `STRICTER_THAN_75` below.

// OPEN (CS-Q15): the name of the composed-ground evidence state. Change it here only.
export const COMPOSED_EVIDENCE_STATE = 'INFERRED_CONSTRAINED';

export const EXTENT_KINDS = Object.freeze(['LENGTH_M', 'AREA_M2', 'ANGLE_DEG']);
// D56 Q13: [HIGH upper bound, MEDIUM upper bound]; larger is LOW; null extent is UNKNOWN.
export const QUALITY_LIMITS = Object.freeze({ LENGTH_M: [0.25, 1.0], AREA_M2: [0.25, 4.0], ANGLE_DEG: [15, 45] });
export const QUALITY_GRADES = Object.freeze(['HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']);
export const QUALITY_RULE_REF = 'quality-grade-rule-v1';
// D56 Q25
export const HUMANOID_DISPLAY_MAX_INTERVAL_M = 0.25;

// §6.3.1: the five fixed condition kinds. Curves may also use two more (§2.4).
export const CONSTRAINT_KINDS = Object.freeze(['prior', 'track_height', 'occlusion_near', 'lowest_visible_far', 'speed']);
export const CURVE_CONSTRAINT_KINDS = Object.freeze(['endpoint_estimates', 'k1_reachability']);
export const CONSTRAINT_LABELS = Object.freeze({
  prior: '先驗',
  track_height: '軌跡身高',
  occlusion_near: '遮擋邊界',
  lowest_visible_far: '最低可見點',
  speed: '速度界',
  endpoint_estimates: '兩端估計',
  k1_reachability: 'K1 可達範圍',
  foot_pixel_band: '腳點像素帶',
});
// The readout omits lowest_visible_far because it usually does not tighten the extent (design §5.3.1).
const READOUT_OMITTED = new Set(['lowest_visible_far']);

// Same names as #75's DataIntegrityError reasons.
export const ERR = Object.freeze({
  MISSING: 'UNCERTAINTY_FIELDS_MISSING',
  INVALID: 'UNCERTAINTY_FIELDS_INVALID',
  ITEM: 'INFERENCE_ITEM_INVALID',
  LAYER: 'LAYER_SCHEMA_INVALID',
  CURVE_KIND: 'CURVE_KIND_INVALID',
  CONSTRAINT_KIND: 'CONSTRAINT_KIND_INVALID', // STRICTER_THAN_75
});

export const CURVE_KINDS = Object.freeze(['OBSERVED', 'INFERRED_CONNECTOR', 'BLIND_HYPOTHESIS', 'MISSING_GAP', 'PREDICTION']);
const INFERRED_CURVE_KINDS = new Set(['INFERRED_CONNECTOR', 'BLIND_HYPOTHESIS', 'PREDICTION']);

const UNCERTAINTY_KEYS = new Set(['extent_kind', 'extent_value', 'constraints_used', 'quality_grade', 'quality_rule_ref', 'quality_rule_sha256', 'per_sample_ref', 'reason']);
const REQUIRED_KEYS = ['extent_kind', 'extent_value', 'constraints_used', 'quality_grade', 'quality_rule_ref', 'quality_rule_sha256'];

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isFiniteNumber = (v) => typeof v === 'number' && Number.isFinite(v);
const isNonEmptyString = (v) => typeof v === 'string' && v.length > 0;
const isSha256 = (v) => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v);

export function gradeFor(extentKind, extentValue) {
  if (extentValue === null || extentValue === undefined) return 'UNKNOWN';
  const limits = QUALITY_LIMITS[extentKind];
  if (!limits) return 'UNKNOWN';
  const [high, medium] = limits;
  return extentValue <= high ? 'HIGH' : extentValue <= medium ? 'MEDIUM' : 'LOW';
}

function fail(code, ref, field) {
  const e = { code };
  if (ref !== undefined) e.estimate_ref = ref;
  if (field !== undefined) e.field = field;
  return e;
}

// Validate one inference item (composed_ground, heading, curve segment). Returns null or {code, field}.
// `expectedExtent`: heading must be ANGLE_DEG; everything else must not be ANGLE_DEG.
export function validateInferenceItem(item, { expectedExtent = null } = {}) {
  if (!isObj(item)) return fail(ERR.ITEM, undefined, 'item');
  const u = item.uncertainty;
  if (!isObj(u)) return fail(ERR.MISSING, undefined, 'uncertainty');
  const extra = Object.keys(u).filter((k) => !UNCERTAINTY_KEYS.has(k));
  if (extra.length) return fail(ERR.INVALID, undefined, `uncertainty.${extra[0]}`);
  if ('status' in item && !(item.status === 'READY' || item.status === 'UNKNOWN')) return fail(ERR.INVALID, undefined, 'status');
  for (const k of ['per_sample_ref', 'reason']) {
    if (k in u && !isNonEmptyString(u[k])) return fail(ERR.INVALID, undefined, `uncertainty.${k}`);
  }
  if (item.status === 'UNKNOWN') {
    if (!('geometry' in item) || item.geometry !== null || !('extent_value' in u) || u.extent_value !== null
        || u.quality_grade !== 'UNKNOWN' || !isNonEmptyString(item.reason)) return fail(ERR.INVALID, undefined, 'uncertainty');
    return null;
  }
  for (const k of REQUIRED_KEYS) if (!(k in u)) return fail(ERR.MISSING, undefined, `uncertainty.${k}`);
  const { extent_kind: kind, extent_value: value } = u;
  const bad = (field) => fail(ERR.INVALID, undefined, `uncertainty.${field}`);
  if (typeof kind !== 'string' || !EXTENT_KINDS.includes(kind)) return bad('extent_kind');
  if (expectedExtent !== null && kind !== expectedExtent) return bad('extent_kind');
  if (expectedExtent === null && kind === 'ANGLE_DEG') return bad('extent_kind');
  if (!isFiniteNumber(value) || value < 0) return bad('extent_value');
  if (!Array.isArray(u.constraints_used) || u.constraints_used.some((c) => !isNonEmptyString(c))) return bad('constraints_used');
  if (!isNonEmptyString(u.quality_rule_ref)) return bad('quality_rule_ref');
  if (!isSha256(u.quality_rule_sha256)) return bad('quality_rule_sha256');
  if (u.quality_grade !== gradeFor(kind, value)) return bad('quality_grade');
  return null;
}

// STRICTER_THAN_75: composed_ground.constraints_used[].kind must be one of the five fixed names (§6.3.1).
function validateConstraintKinds(composed) {
  for (const list of ['constraints_used', 'constraints_unavailable']) {
    if (!(list in composed)) return fail(ERR.MISSING, undefined, `composed_ground.${list}`);
    if (!Array.isArray(composed[list])) return fail(ERR.ITEM, undefined, `composed_ground.${list}`);
    for (const c of composed[list]) {
      if (!isObj(c) || !CONSTRAINT_KINDS.includes(c.kind)) return fail(ERR.CONSTRAINT_KIND, undefined, `composed_ground.${list}.kind`);
    }
  }
  return null;
}

// Person layer. Every estimate must carry composed_ground (STRICTER_THAN_75: #75 only checks it when present)
// and, when heading is not UNKNOWN, a heading uncertainty in degrees.
export function validatePersonLayer(layer) {
  if (!isObj(layer) || !Array.isArray(layer.estimates)) return fail(ERR.LAYER, undefined, 'estimates');
  for (const e of layer.estimates) {
    if (!isObj(e)) return fail(ERR.LAYER, undefined, 'estimates[]');
    const ref = e.estimate_ref;
    if (!('composed_ground' in e)) return { ...fail(ERR.MISSING, ref, 'composed_ground') };
    const c = e.composed_ground;
    if (!isObj(c) || !(c.status === 'READY' || c.status === 'UNKNOWN')) return fail(ERR.ITEM, ref, 'composed_ground.status');
    let err = validateInferenceItem(c);
    if (err) return { ...err, estimate_ref: ref, field: `composed_ground.${err.field}` };
    if (c.status === 'READY') {
      err = validateConstraintKinds(c);
      if (err) return { ...err, estimate_ref: ref };
      if (c.evidence_state !== COMPOSED_EVIDENCE_STATE) return fail(ERR.ITEM, ref, 'composed_ground.evidence_state');
    }
    if ('heading' in e) {
      const h = e.heading;
      if (!isObj(h) || !['UNKNOWN', 'INFERRED', 'READY'].includes(h.state)) return fail(ERR.ITEM, ref, 'heading.state');
      if (h.state === 'UNKNOWN') {
        if (h.direction_xy !== null && h.direction_xy !== undefined) return fail(ERR.ITEM, ref, 'heading.direction_xy');
      } else {
        const d = h.direction_xy;
        if ((h.status ?? 'READY') !== 'READY' || !Array.isArray(d) || d.length !== 2 || !d.every(isFiniteNumber) || (d[0] === 0 && d[1] === 0)) {
          return fail(ERR.ITEM, ref, 'heading.direction_xy');
        }
        err = validateInferenceItem(h, { expectedExtent: 'ANGLE_DEG' });
        if (err) return { ...err, estimate_ref: ref, field: `heading.${err.field}` };
      }
    }
  }
  return null;
}

export function validateCurveLayer(layer) {
  if (!isObj(layer) || !Array.isArray(layer.curves)) return fail(ERR.LAYER, undefined, 'curves');
  for (const curve of layer.curves) {
    if (!isObj(curve) || !Array.isArray(curve.segments)) return fail(ERR.LAYER, undefined, 'curves[].segments');
    for (const seg of curve.segments) {
      if (!isObj(seg) || typeof seg.kind !== 'string' || !CURVE_KINDS.includes(seg.kind)) return fail(ERR.CURVE_KIND, curve.curve_ref, 'segments[].kind');
      if (INFERRED_CURVE_KINDS.has(seg.kind)) {
        const err = validateInferenceItem(seg);
        if (err) return { ...err, estimate_ref: curve.curve_ref, field: `segments[].${err.field}` };
      }
    }
  }
  return null;
}

// Validate whichever layers a response contains (same walk as #75's validate_uncertainty).
export function validateUncertainty(payload) {
  if (!isObj(payload)) return fail(ERR.LAYER, undefined, 'payload');
  if ('estimates' in payload) { const e = validatePersonLayer(payload); if (e) return e; }
  if ('curves' in payload) { const e = validateCurveLayer(payload); if (e) return e; }
  return null;
}

// D56 Q25: draw the humanoid range only for a HIGH-grade LENGTH_M interval, and only for the current sample.
export function humanoidRangeAllowed(composed, { isCurrentSample = true } = {}) {
  if (!isCurrentSample || !isObj(composed) || composed.status !== 'READY') return false;
  const u = composed.uncertainty;
  return isObj(u) && u.extent_kind === 'LENGTH_M' && u.quality_grade === 'HIGH'
    && isFiniteNumber(u.extent_value) && u.extent_value <= HUMANOID_DISPLAY_MAX_INTERVAL_M;
}

// D56 Q24: display precision 0.01 m / 0.1 m² / 1°, always rounded outward (up). Returns a string.
const PRECISION = Object.freeze({ LENGTH_M: [0.01, 2], AREA_M2: [0.1, 1], ANGLE_DEG: [1, 0] });
export function roundOutward(value, extentKind) {
  const [step, decimals] = PRECISION[extentKind];
  const n = Math.ceil(value / step - 1e-9);
  return (n * step).toFixed(decimals);
}

export function conditionLabel(kind) { return CONSTRAINT_LABELS[kind] ?? kind; }

function readoutConditions(item) {
  const used = (item.uncertainty?.constraints_used ?? []).filter((k) => !READOUT_OMITTED.has(k));
  const names = used.map(conditionLabel);
  if (item.foot_status === 'VISIBLE') names.unshift(CONSTRAINT_LABELS.foot_pixel_band);
  return names;
}

const READOUT_UNITS = Object.freeze({ LENGTH_M: ' m', AREA_M2: ' m²', ANGLE_DEG: '°' });

// Readout text next to the geometry (contract §2.4 UI rule + design §5.3.1, with the contract's wording:
// "區間 0.49 m", "範圍帶 7.2 m²"). `label` overrides the noun; `rangeLabel` is chosen from the item.
export function readoutText(item, { label = null } = {}) {
  const u = item?.uncertainty;
  if (!isObj(u)) return null;
  if (u.extent_value === null || u.extent_value === undefined) return `UNKNOWN${item.reason ? `（${item.reason}）` : ''}`;
  const noun = label ?? (u.extent_kind === 'LENGTH_M' ? '區間' : u.extent_kind === 'ANGLE_DEG' ? '方向範圍'
    : item.geometry?.kind === 'POLYGON' ? '窄帶' : item.kind === 'INFERRED_CONNECTOR' ? '緞帶' : '範圍帶');
  const names = readoutConditions(item);
  return `${noun} ${roundOutward(u.extent_value, u.extent_kind)}${READOUT_UNITS[u.extent_kind]}${names.length ? `（${names.join('＋')}）` : ''}`;
}

export const DESIGN_ESTIMATE_LINE = '設計估計：輸出凍結前沒有以 GT 驗證';

function valuesText(values) {
  if (!isObj(values)) return '';
  return Object.entries(values).map(([k, v]) => `${k} ${JSON.stringify(v)}`).join('、');
}

// Inspector "誤差來源" list for one inference. The last line is always the design-estimate notice.
export function errorSources(item, { clockErrorS = null, calibrationError = 'UNKNOWN（未評估）' } = {}) {
  const lines = [];
  const text = readoutText(item);
  lines.push(text ? `範圍：${text}` : '範圍：UNKNOWN');
  for (const c of item?.constraints_used ?? []) {
    lines.push(`用到：${conditionLabel(c.kind)}${c.values ? `（${valuesText(c.values)}）` : ''}`);
  }
  for (const c of item?.constraints_unavailable ?? []) lines.push(`沒用到：${conditionLabel(c.kind)}（${c.reason}）`);
  if (item?.foot_status === 'VISIBLE') lines.push(`用到：${CONSTRAINT_LABELS.foot_pixel_band}`);
  lines.push(`校正誤差：${calibrationError}`);
  lines.push(`同步誤差 clock_error_s：${clockErrorS === null ? 'UNKNOWN' : `${clockErrorS} s`}`);
  lines.push(DESIGN_ESTIMATE_LINE);
  return lines;
}

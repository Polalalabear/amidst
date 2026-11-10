// The only place v2 reads data (design §6.1). Builds the five consumer requests (contract §6.1–§6.5) and
// validates responses; any failure is fail-closed: `{ok:false, error:{code, message, ...}}` and no drawable data.
// Requests/responses follow the backend skeleton `controlled_scene_api.py` @ 6e1c439 (#75).
// No DOM. Does not import player-grid.mjs: `syncedFrames` is raw JSON in, raw JSON out (V2-3 composes).

import { validateUncertainty } from './uncertainty.mjs';

export const ACTIONS = Object.freeze(['candidate_cameras', 'synced_frames', 'person_layer', 'curve_layer', 'evidence_lookup']);
export const FIXTURE_ORIGIN = 'SYNTHETIC_FIXTURE';
export const SURROUND_POLICY_REF_FIELD = 'surrounding_policy_ref';

const kebab = (action) => action.replaceAll('_', '-');
export const requestSchema = (action) => `controlled-scene.${kebab(action)}-request.v1`;
export const responseSchema = (action) => `controlled-scene.${kebab(action)}.v1`;

// ---- time ----
// Integer milliseconds in the store; the wire carries decimal seconds (shortest representation, e.g. 12470 -> 12.47).
export const tMsToSeconds = (tMs) => tMs / 1000;
// Contract §2 / D56 Q14: comparisons use integer microseconds.
export const secondsToUs = (s) => Math.round(s * 1e6);

// ---- errors ----
export function apiError(code, message, extra = {}) {
  return { ok: false, error: { code, message: message ?? code, ...extra } };
}

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const nonEmpty = (v) => typeof v === 'string' && v.length > 0;

// ---- request building (mirrors #75 `_validate_request`) ----
const ACTION_FIELDS = {
  candidate_cameras: ['target_region_ref', 'target_polygon', 'time_range_s', 'query_intent', 'surrounding_policy_ref', 'camera_ids', 'page_size', 'cursor', 'layout_capacity'],
  synced_frames: ['t_s', 'camera_ids'],
  person_layer: ['time_range_s'],
  curve_layer: ['time_range_s', 't_s'],
  evidence_lookup: ['pick'],
};
export const PICK_KEYS = Object.freeze(['layer', 'ref', 'result_sha256', 'segment_index', 't_click_s']);
export const MAX_CAMERAS_PER_REQUEST = 8;
export const MAX_POLYGON_VERTICES = 64;

function checkTimeRange(span, durationS) {
  if (!Array.isArray(span) || span.length !== 2 || !span.every(finite)) return false;
  const [a, b] = span.map(secondsToUs);
  return a >= 0 && a < b && (durationS === undefined || b <= secondsToUs(durationS));
}

// scope: { session_ref, scene_id, run_id, duration_s? }. Returns {ok:true, request} or an apiError.
export function buildRequest(action, scope, args = {}) {
  if (!ACTIONS.includes(action)) return apiError('UNKNOWN_ACTION', action);
  for (const k of ['session_ref', 'scene_id', 'run_id']) {
    if (!nonEmpty(scope?.[k])) return apiError('INVALID_REQUEST', `scope.${k}`, { field: k });
  }
  const allowed = new Set(ACTION_FIELDS[action]);
  const extra = Object.keys(args).find((k) => !allowed.has(k));
  if (extra) return apiError('INVALID_REQUEST', `unexpected field ${extra}`, { field: extra });
  const request = { schema_version: requestSchema(action), session_ref: scope.session_ref, scene_id: scope.scene_id, run_id: scope.run_id, ...args };

  if (['candidate_cameras', 'person_layer', 'curve_layer'].includes(action) && !checkTimeRange(args.time_range_s, scope.duration_s)) {
    return apiError('INVALID_TIME_RANGE', 'time_range_s must be a half-open range inside the run', { field: 'time_range_s' });
  }
  if ((action === 'synced_frames' || 't_s' in args) && !finite(args.t_s)) return apiError('INVALID_TIME', 't_s', { field: 't_s' });
  if (action === 'synced_frames' || (args.camera_ids !== undefined && args.camera_ids !== null)) {
    const c = args.camera_ids;
    if (!Array.isArray(c) || c.length < 1 || c.length > MAX_CAMERAS_PER_REQUEST || !c.every((x) => typeof x === 'string') || new Set(c).size !== c.length) {
      return apiError('INVALID_CAMERA_SCOPE', 'camera_ids must be 1–8 unique strings', { field: 'camera_ids' });
    }
  }
  if (action === 'candidate_cameras') {
    const hasRegion = Boolean(args.target_region_ref);
    const hasPolygon = Boolean(args.target_polygon);
    if (hasRegion === hasPolygon || !['PASS_THROUGH', 'ENTER_EXIT'].includes(args.query_intent) || !nonEmpty(args.surrounding_policy_ref)
        || !Number.isInteger(args.page_size) || args.page_size < 1 || args.page_size > MAX_CAMERAS_PER_REQUEST
        || ![1, 2, 4, 8].includes(args.layout_capacity)) {
      return apiError('INVALID_CANDIDATE_QUERY', 'candidate query fields are invalid');
    }
    if (hasPolygon) {
      const p = args.target_polygon;
      const ok = isObj(p) && ['floor_id', 'frame_id', 'length_unit', 'polygon_m'].every((k) => k in p) && Object.keys(p).length === 4
        && p.length_unit === 'm' && Array.isArray(p.polygon_m) && p.polygon_m.length >= 3 && p.polygon_m.length <= MAX_POLYGON_VERTICES
        && p.polygon_m.every((v) => Array.isArray(v) && v.length === 2 && v.every(finite));
      if (!ok) return apiError('INVALID_POLYGON', 'target_polygon is invalid', { field: 'target_polygon' });
    }
  }
  if (action === 'evidence_lookup') {
    const p = args.pick;
    const ok = isObj(p) && Object.keys(p).length === PICK_KEYS.length && PICK_KEYS.every((k) => k in p)
      && nonEmpty(p.layer) && nonEmpty(p.ref) && Number.isInteger(p.segment_index) && finite(p.t_click_s)
      && p.t_click_s >= 0 && (scope.duration_s === undefined || secondsToUs(p.t_click_s) < secondsToUs(scope.duration_s));
    if (!ok) return apiError('INVALID_EVIDENCE_PICK', 'pick is invalid', { field: 'pick' });
  }
  return { ok: true, request };
}

// ---- response validation ----
const HEX64 = /^[0-9a-f]{64}$/;

// expected: { run_id, clock_id?, scene_id?, data_origin? } where data_origin 'SYNTHETIC_FIXTURE' for fixture mode.
export function validateResponse(action, payload, expected = {}) {
  if (!isObj(payload)) return apiError('RESPONSE_NOT_OBJECT');
  if (isObj(payload.error)) return errorFromBody(payload, undefined);
  if (payload.schema_version !== responseSchema(action)) return apiError('SCHEMA_MISMATCH', `expected ${responseSchema(action)}`, { ref: payload.schema_version });
  const scope = payload.resolved_scope;
  if (!isObj(scope)) return apiError('SCOPE_MISSING', 'resolved_scope missing');
  if (expected.run_id !== undefined && scope.run_id !== expected.run_id) return apiError('SCOPE_MISMATCH', 'resolved_scope.run_id differs from the requested run', { field: 'resolved_scope.run_id' });
  if (expected.scene_id !== undefined && scope.scene_id !== undefined && scope.scene_id !== expected.scene_id) return apiError('SCOPE_MISMATCH', 'resolved_scope.scene_id differs', { field: 'resolved_scope.scene_id' });
  if (expected.clock_id !== undefined && scope.clock_id !== expected.clock_id) return apiError('SCOPE_MISMATCH', 'resolved_scope.clock_id differs', { field: 'resolved_scope.clock_id' });
  if (!isObj(payload.provenance) || payload.provenance.gt_read !== false) return apiError('GT_READ_NOT_FALSE', 'provenance.gt_read must be false', { field: 'provenance.gt_read' });
  if (payload.identity_verdict !== 'UNCONFIRMED') return apiError('IDENTITY_VERDICT_INVALID', 'identity_verdict must be UNCONFIRMED', { field: 'identity_verdict' });
  if (payload.agent_used !== false) return apiError('AGENT_USED_INVALID', 'agent_used must be false', { field: 'agent_used' });
  if (typeof payload.output_sha256 !== 'string' || !HEX64.test(payload.output_sha256)) return apiError('OUTPUT_HASH_INVALID', 'output_sha256 missing or malformed', { field: 'output_sha256' });
  // Real and fixture data are never mixed (UX §7): the origin must match what this api instance was created for.
  const fixtureExpected = expected.data_origin === FIXTURE_ORIGIN;
  if (fixtureExpected && payload.data_origin !== FIXTURE_ORIGIN) return apiError('DATA_ORIGIN_MISMATCH', 'fixture mode requires data_origin SYNTHETIC_FIXTURE', { field: 'data_origin' });
  if (!fixtureExpected && (payload.data_origin === FIXTURE_ORIGIN || scope.data_origin === FIXTURE_ORIGIN)) return apiError('DATA_ORIGIN_MISMATCH', 'a fixture payload arrived on a non-fixture source', { field: 'data_origin' });
  if (action === 'person_layer' || action === 'curve_layer') {
    const u = validateUncertainty(payload);
    if (u) return apiError(u.code, `uncertainty check failed at ${u.field ?? '?'}`, { integrity: true, estimate_ref: u.estimate_ref, field: u.field });
  }
  return { ok: true, data: payload };
}

// HTTP error bodies (#75 service): 409 {schema_version:'controlled-scene.error.v1', error:{error_class, reason}};
// 503 same with RequiredInputUnavailable; 400/403 {error:{code,message}}. Also accepts error.code (#71 fixtures).
export function errorFromBody(body, httpStatus) {
  const e = isObj(body) && isObj(body.error) ? body.error : {};
  const code = e.reason ?? e.code ?? (httpStatus ? `HTTP_${httpStatus}` : 'REQUEST_FAILED');
  const cls = e.error_class ?? null;
  const integrity = cls === 'DataIntegrityError' || httpStatus === 409;
  return apiError(String(code), e.message ?? String(code), { error_class: cls, http_status: httpStatus ?? null, integrity, unavailable: cls === 'RequiredInputUnavailable' || httpStatus === 503 });
}

// ---- stale responses ----
// Each action has its own counter; a response is current only if no newer request of that action was started.
export function createEpoch() {
  const n = new Map();
  return {
    begin(key) { const v = (n.get(key) ?? 0) + 1; n.set(key, v); return v; },
    isCurrent(key, token) { return n.get(key) === token; },
  };
}

// ---- fixture file names ----
const FIXTURE_FILES = {
  candidate_cameras: (ev) => `candidate_cameras_${ev}.json`,
  person_layer: (ev) => `person_layer_${ev}.json`,
  curve_layer: (ev) => `curve_layer_${ev}.json`,
};
export const EVIDENCE_FIXTURES = Object.freeze({
  IS_OBSERVATION: 'evidence_lookup_B1_is_observation.json',
  SUPPORTS_OBSERVED_SEGMENT: 'evidence_lookup_B1_supports_observed_segment.json',
  ENDPOINTS_OF_CONNECTOR: 'evidence_lookup_B1_endpoints_of_connector.json',
  HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE: 'evidence_lookup_B1_hypothesis_endpoints_and_negative_evidence.json',
  NO_SUPPORT: 'evidence_lookup_B1_no_support.json',
});
const KIND_TO_RELATION = {
  OBSERVED: 'SUPPORTS_OBSERVED_SEGMENT',
  INFERRED_CONNECTOR: 'ENDPOINTS_OF_CONNECTOR',
  BLIND_HYPOTHESIS: 'HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE',
  MISSING_GAP: 'NO_SUPPORT',
};

function filterByTime(action, data, span) {
  if (!Array.isArray(span)) return data;
  const [a, b] = span.map(secondsToUs);
  const out = { ...data, time_range_s: span };
  if (action === 'person_layer') out.estimates = data.estimates.filter((e) => secondsToUs(e.timestamp_s) >= a && secondsToUs(e.timestamp_s) < b);
  if (action === 'curve_layer') {
    out.curves = data.curves.map((c) => ({
      ...c,
      segments: c.segments.filter((s) => {
        const [s0, s1] = s.t_s ?? [s.sample_timestamps_s[0], s.sample_timestamps_s.at(-1) + 0.2];
        return secondsToUs(s0) < b && secondsToUs(s1) > a;
      }),
    }));
  }
  return out;
}

// ---- the api object ----
// opts: { mode: 'live'|'fixture', scope:{session_ref, scene_id, run_id, clock_id?, duration_s?, event?}, fetchFn, baseUrl,
//         fixtureBase }. In fixture mode `scope.event` ('A'|'B1') selects the fixture set.
export function createApi(opts) {
  const mode = opts.mode ?? 'live';
  const scope = opts.scope;
  const fetchFn = opts.fetchFn ?? globalThis.fetch?.bind(globalThis);
  const baseUrl = opts.baseUrl ?? '';
  const fixtureBase = opts.fixtureBase ?? new URL('./fixtures/', import.meta.url).href;
  const epoch = createEpoch();
  const expected = { run_id: scope.run_id, scene_id: scope.scene_id, clock_id: scope.clock_id, data_origin: mode === 'fixture' ? FIXTURE_ORIGIN : 'REAL' };

  async function readJson(url, init) {
    let res;
    try { res = await fetchFn(url, init); } catch (e) { return apiError('NETWORK_ERROR', String(e?.message ?? e), { unavailable: true }); }
    let body = null;
    try { body = await res.json(); } catch { /* handled below */ }
    if (!res.ok) return errorFromBody(body, res.status);
    if (body === null) return apiError('RESPONSE_NOT_JSON');
    return { ok: true, body };
  }

  async function fixtureFile(name) {
    const r = await readJson(new URL(name, fixtureBase).href);
    return r.ok ? { ok: true, body: r.body } : r;
  }

  async function call(action, allArgs = {}) {
    const { fixture_name: fixtureName, ...args } = allArgs; // fixture_name is local only, never sent
    const built = buildRequest(action, scope, args);
    if (!built.ok) return built;
    const token = epoch.begin(action);
    let r;
    if (mode === 'fixture') r = await fixtureResponse(action, args, fixtureName);
    else r = await readJson(`${baseUrl}/api/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(built.request) });
    if (!epoch.isCurrent(action, token)) return { ...apiError('STALE_RESPONSE', 'a newer request superseded this one'), stale: true };
    if (!r.ok) return r;
    return validateResponse(action, r.body, expected);
  }

  async function fixtureResponse(action, args, fixtureName) {
    const ev = scope.event;
    if (action === 'synced_frames') {
      if (!fixtureName) return apiError('FIXTURE_NOT_AVAILABLE', 'synced_frames fixtures belong to #71; pass fixture_name');
      return fixtureFile(fixtureName);
    }
    if (action === 'evidence_lookup') {
      const curves = await fixtureFile(FIXTURE_FILES.curve_layer(ev));
      if (!curves.ok) return curves;
      const curve = curves.body.curves.find((c) => c.curve_ref === args.pick.ref);
      const kind = curve?.segments[args.pick.segment_index]?.kind;
      const relation = args.pick.layer === 'observation' ? 'IS_OBSERVATION' : KIND_TO_RELATION[kind];
      if (!relation) return apiError('FIXTURE_PICK_UNKNOWN', 'the pick does not match any fixture curve segment');
      const r = await fixtureFile(EVIDENCE_FIXTURES[relation]);
      return r.ok ? { ok: true, body: { ...r.body, fixture_canned: true } } : r;
    }
    const r = await fixtureFile(FIXTURE_FILES[action](ev));
    if (!r.ok) return r;
    return { ok: true, body: filterByTime(action, r.body, args.time_range_s) };
  }

  return {
    mode,
    candidateCameras: (args) => call('candidate_cameras', args),
    syncedFrames: (args) => call('synced_frames', args),
    personLayer: (args) => call('person_layer', args),
    curveLayer: (args) => call('curve_layer', args),
    evidenceLookup: (args) => call('evidence_lookup', args),
  };
}

// Bootstrap (service `controlled_scene_bootstrap`): decides fixture vs. real before any layer is requested.
export function validateBootstrap(b) {
  if (!isObj(b) || b.schema_version !== 'controlled-scene.bootstrap.v1') return apiError('BOOTSTRAP_INVALID');
  if (b.gt_read !== false) return apiError('GT_READ_NOT_FALSE', 'bootstrap.gt_read must be false');
  const origin = b.data_origin;
  if (origin !== FIXTURE_ORIGIN && origin !== 'UNCONFIGURED' && !nonEmpty(origin)) return apiError('BOOTSTRAP_INVALID', 'data_origin');
  return { ok: true, data: b, fixture: origin === FIXTURE_ORIGIN, configured: origin !== 'UNCONFIGURED' };
}

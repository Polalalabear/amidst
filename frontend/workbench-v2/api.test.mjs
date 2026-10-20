import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import {
  ACTIONS, EVIDENCE_FIXTURES, FIXTURE_ORIGIN, buildRequest, createApi, createEpoch, errorFromBody, requestSchema, responseSchema, secondsToUs, tMsToSeconds, validateBootstrap, validateResponse,
} from './api.mjs';
import { buildAll, canonicalJson, sha } from './fixtures/generate_v2_fixtures.mjs';

const FIX = new URL('./fixtures/', import.meta.url);
const load = (n) => JSON.parse(readFileSync(new URL(n, FIX), 'utf8'));
const B1 = { session_ref: 'sess-1', scene_id: 'controlled-l-corridor', run_id: 'fixture-ctrl-b1-5fps-v1-r001', duration_s: 20 };
const EXPECT = { run_id: B1.run_id, scene_id: B1.scene_id, clock_id: `clock:${B1.run_id}`, data_origin: FIXTURE_ORIGIN };
const diskFetch = async (url) => {
  try { const text = readFileSync(new URL(url), 'utf8'); return { ok: true, status: 200, json: async () => JSON.parse(text) }; }
  catch { return { ok: false, status: 404, json: async () => ({ error: { code: 'NOT_FOUND' } }) }; }
};
const fixtureApi = (extra = {}) => createApi({ mode: 'fixture', scope: { ...B1, clock_id: EXPECT.clock_id, event: 'B1' }, fetchFn: diskFetch, fixtureBase: FIX.href, ...extra });
const candQuery = { target_region_ref: 'AREA_R101_FRONT', target_polygon: null, time_range_s: [8, 20], query_intent: 'ENTER_EXIT', surrounding_policy_ref: 'surround-policy-v1', camera_ids: null, page_size: 4, cursor: null, layout_capacity: 4 };

test('time: ms on the wire as shortest decimal seconds; comparisons in integer microseconds', () => {
  assert.equal(tMsToSeconds(12470), 12.47);
  assert.equal(tMsToSeconds(0), 0);
  assert.equal(secondsToUs(12.47), 12470000);
  assert.equal(secondsToUs(0.2), 200000);
});

test('schema names follow controlled-scene.<action-kebab>[-request].v1', () => {
  assert.equal(requestSchema('candidate_cameras'), 'controlled-scene.candidate-cameras-request.v1');
  assert.equal(responseSchema('evidence_lookup'), 'controlled-scene.evidence-lookup.v1');
  assert.equal(ACTIONS.length, 5);
});

test('buildRequest: valid requests for all five actions', () => {
  const pick = { layer: 'curve', ref: 'cv-1', result_sha256: 'a'.repeat(64), segment_index: 0, t_click_s: 10.27 };
  const ok = (action, args) => { const r = buildRequest(action, B1, args); assert.equal(r.ok, true, `${action}: ${r.error?.message}`); return r.request; };
  assert.equal(ok('synced_frames', { t_s: 12.47, camera_ids: ['CAM_W1'] }).schema_version, 'controlled-scene.synced-frames-request.v1');
  ok('person_layer', { time_range_s: [12, 13] });
  ok('curve_layer', { time_range_s: [0, 20], t_s: 12.47 });
  ok('evidence_lookup', { pick });
  const cand = ok('candidate_cameras', candQuery);
  assert.equal(cand.session_ref, 'sess-1');
  assert.equal(cand.run_id, B1.run_id);
});

test('buildRequest: invalid requests are refused before any network call', () => {
  const code = (action, args, scope = B1) => buildRequest(action, scope, args).error?.code;
  assert.equal(code('nope', {}), 'UNKNOWN_ACTION');
  assert.equal(code('person_layer', { time_range_s: [5, 5] }), 'INVALID_TIME_RANGE');
  assert.equal(code('person_layer', { time_range_s: [0, 20.001] }), 'INVALID_TIME_RANGE');
  assert.equal(code('person_layer', { time_range_s: [-1, 2] }), 'INVALID_TIME_RANGE');
  assert.equal(code('person_layer', { time_range_s: [0, NaN] }), 'INVALID_TIME_RANGE');
  assert.equal(code('person_layer', { time_range_s: [0, 1], gt: true }), 'INVALID_REQUEST');
  assert.equal(code('synced_frames', { t_s: 'x', camera_ids: ['a'] }), 'INVALID_TIME');
  assert.equal(code('synced_frames', { t_s: 1, camera_ids: [] }), 'INVALID_CAMERA_SCOPE');
  assert.equal(code('synced_frames', { t_s: 1, camera_ids: Array.from({ length: 9 }, (_, i) => `c${i}`) }), 'INVALID_CAMERA_SCOPE');
  assert.equal(code('synced_frames', { t_s: 1, camera_ids: ['a', 'a'] }), 'INVALID_CAMERA_SCOPE');
  assert.equal(code('person_layer', { time_range_s: [0, 1] }, { ...B1, session_ref: '' }), 'INVALID_REQUEST');
  assert.equal(code('candidate_cameras', { ...candQuery, target_region_ref: null }), 'INVALID_CANDIDATE_QUERY', 'region xor polygon');
  assert.equal(code('candidate_cameras', { ...candQuery, query_intent: 'GUESS' }), 'INVALID_CANDIDATE_QUERY');
  assert.equal(code('candidate_cameras', { ...candQuery, page_size: 9 }), 'INVALID_CANDIDATE_QUERY');
  assert.equal(code('candidate_cameras', { ...candQuery, layout_capacity: 3 }), 'INVALID_CANDIDATE_QUERY');
  const poly = (polygon_m, extra = {}) => ({ ...candQuery, target_region_ref: null, target_polygon: { floor_id: 'F', frame_id: 'w', length_unit: 'm', polygon_m, ...extra } });
  assert.equal(code('candidate_cameras', candQuery.target_polygon === null ? poly([[0, 0], [1, 0], [1, 1]]) : null), undefined);
  assert.equal(code('candidate_cameras', poly([[0, 0], [1, 0]])), 'INVALID_POLYGON');
  assert.equal(code('candidate_cameras', poly(Array.from({ length: 65 }, (_, i) => [i, i]))), 'INVALID_POLYGON');
  assert.equal(code('candidate_cameras', poly([[0, 0], [1, 0], [1, NaN]])), 'INVALID_POLYGON');
  assert.equal(code('candidate_cameras', poly([[0, 0], [1, 0], [1, 1]], { length_unit: 'ft' })), 'INVALID_POLYGON');
  assert.equal(code('evidence_lookup', { pick: { layer: 'curve', ref: 'x' } }), 'INVALID_EVIDENCE_PICK');
  assert.equal(code('evidence_lookup', { pick: { layer: 'curve', ref: 'x', result_sha256: 'h', segment_index: 0, t_click_s: 20 } }), 'INVALID_EVIDENCE_PICK');
});

test('validateResponse accepts every good fixture and tags them SYNTHETIC_FIXTURE', () => {
  const good = { candidate_cameras: 'candidate_cameras_B1.json', person_layer: 'person_layer_B1.json', curve_layer: 'curve_layer_B1.json' };
  for (const [action, file] of Object.entries(good)) { const r = validateResponse(action, load(file), EXPECT); assert.equal(r.ok, true, `${file}: ${r.error?.code}`); assert.equal(r.data.data_origin, FIXTURE_ORIGIN); }
  for (const f of Object.values(EVIDENCE_FIXTURES)) assert.equal(validateResponse('evidence_lookup', load(f), EXPECT).ok, true, f);
});

test('validateResponse fails closed on every guard', () => {
  const code = (mut, action = 'curve_layer', expected = EXPECT) => { const d = load('curve_layer_B1.json'); mut(d); return validateResponse(action, d, expected).error?.code; };
  assert.equal(validateResponse('curve_layer', null, EXPECT).error.code, 'RESPONSE_NOT_OBJECT');
  assert.equal(code((d) => { d.schema_version = 'controlled-scene.curve-layer.v2'; }), 'SCHEMA_MISMATCH');
  assert.equal(code(() => {}, 'person_layer'), 'SCHEMA_MISMATCH');
  assert.equal(code((d) => { delete d.resolved_scope; }), 'SCOPE_MISSING');
  assert.equal(code((d) => { d.resolved_scope.run_id = 'other'; }), 'SCOPE_MISMATCH');
  assert.equal(code((d) => { d.resolved_scope.clock_id = 'clock:other'; }), 'SCOPE_MISMATCH');
  assert.equal(code((d) => { d.resolved_scope.scene_id = 'other-scene'; }), 'SCOPE_MISMATCH');
  assert.equal(code((d) => { d.provenance.gt_read = true; }), 'GT_READ_NOT_FALSE');
  assert.equal(code((d) => { delete d.provenance; }), 'GT_READ_NOT_FALSE');
  assert.equal(code((d) => { d.identity_verdict = 'CONFIRMED'; }), 'IDENTITY_VERDICT_INVALID');
  assert.equal(code((d) => { d.agent_used = true; }), 'AGENT_USED_INVALID');
  assert.equal(code((d) => { d.output_sha256 = 'zz'; }), 'OUTPUT_HASH_INVALID');
  assert.equal(code((d) => { delete d.data_origin; }), 'DATA_ORIGIN_MISMATCH', 'fixture mode needs the fixture origin');
  assert.equal(code(() => {}, 'curve_layer', { ...EXPECT, data_origin: 'REAL' }), 'DATA_ORIGIN_MISMATCH', 'fixture payload on a real source');
  assert.equal(code((d) => { d.curves[0].segments.push({ kind: 'UI_SPAN', t_s: [0, 1] }); }), 'CURVE_KIND_INVALID');
  assert.equal(code((d) => { for (const c of d.curves) for (const s of c.segments) if (s.kind === 'INFERRED_CONNECTOR') delete s.uncertainty; }), 'UNCERTAINTY_FIELDS_MISSING');
  assert.equal(validateResponse('person_layer', load('person_layer_gt_read_true.json'), EXPECT).error.code, 'GT_READ_NOT_FALSE');
  const miss = validateResponse('person_layer', load('person_layer_missing_uncertainty.json'), EXPECT);
  assert.equal(miss.ok, false);
  assert.equal(miss.error.code, 'UNCERTAINTY_FIELDS_MISSING');
  assert.equal(miss.error.integrity, true);
  assert.match(miss.error.estimate_ref, /^pe-/);
  assert.equal(miss.data, undefined, 'no drawable data on failure');
});

test('a real (non-fixture) payload is accepted on a real source and refused on a fixture source', () => {
  const real = load('curve_layer_B1.json'); delete real.data_origin; delete real.fixture_marker; delete real.resolved_scope.data_origin;
  assert.equal(validateResponse('curve_layer', real, { ...EXPECT, data_origin: 'REAL' }).ok, true);
  assert.equal(validateResponse('curve_layer', real, EXPECT).error.code, 'DATA_ORIGIN_MISMATCH');
});

test('errorFromBody maps the #75 service error shapes', () => {
  const e409 = errorFromBody({ schema_version: 'controlled-scene.error.v1', error: { error_class: 'DataIntegrityError', reason: 'RGB_RECORD_HASH_MISMATCH' } }, 409);
  assert.deepEqual([e409.ok, e409.error.code, e409.error.integrity, e409.error.unavailable], [false, 'RGB_RECORD_HASH_MISMATCH', true, false]);
  const e503 = errorFromBody({ error: { error_class: 'RequiredInputUnavailable', reason: 'CONTROLLED_RUN_NOT_CONFIGURED' } }, 503);
  assert.deepEqual([e503.error.code, e503.error.integrity, e503.error.unavailable], ['CONTROLLED_RUN_NOT_CONFIGURED', false, true]);
  const e400 = errorFromBody({ error: { code: 'INVALID_OR_STALE_REQUEST', message: 'x' } }, 400);
  assert.deepEqual([e400.error.code, e400.error.integrity, e400.error.http_status], ['INVALID_OR_STALE_REQUEST', false, 400]);
  assert.equal(errorFromBody({ error: { code: 'RGB_RECORD_HASH_MISMATCH' } }, 409).error.integrity, true, '#71 error.code form, still an integrity error at 409');
  assert.equal(errorFromBody(null, 502).error.code, 'HTTP_502');
  assert.equal(validateResponse('person_layer', { error: { error_class: 'DataIntegrityError', reason: 'RGB_INDEX_INCOMPLETE' } }, EXPECT).error.integrity, true);
});

test('fixture api: person layer is filtered by the half-open time range', async () => {
  const r = await fixtureApi().personLayer({ time_range_s: [12, 13] });
  assert.equal(r.ok, true);
  assert.ok(r.data.estimates.length > 0);
  assert.ok(r.data.estimates.every((e) => e.timestamp_s >= 12 && e.timestamp_s < 13));
  assert.deepEqual(r.data.time_range_s, [12, 13]);
  assert.equal(r.data.data_origin, FIXTURE_ORIGIN);
});

test('fixture api: curve layer filters segments; candidate cameras follow D28 order', async () => {
  const api = fixtureApi();
  const c = await api.curveLayer({ time_range_s: [9, 10] });
  assert.equal(c.ok, true);
  for (const cv of c.data.curves) for (const s of cv.segments) { const [a, b] = s.t_s ?? [s.sample_timestamps_s[0], s.sample_timestamps_s.at(-1) + 0.2]; assert.ok(a < 10 && b > 9); }
  const q = await api.candidateCameras(candQuery);
  assert.equal(q.ok, true);
  const rel = q.data.candidates.map((x) => x.relation);
  assert.equal(q.data.status, 'PARTIAL');
  assert.deepEqual(q.data.unknown_camera_ids, ['CAM_R102_CTRL']);
  assert.equal(rel.at(-1), 'UNKNOWN');
  assert.ok(q.data.candidates.every((x) => x.image_evidence.frames_with_detection === null), 'null, not 0');
  assert.deepEqual(q.data.ranking_basis, ['relation_tier', 'overlap_area_m2_desc', 'camera_id']);
  const tiers = { TARGET_FOOTPRINT_INTERSECT: 1, ACCESS_PATH_INTERSECT: 2, NO_INTERSECTION: 3, UNKNOWN: 4 };
  assert.deepEqual(rel.map((r) => tiers[r]), [...rel.map((r) => tiers[r])].sort((a, b) => a - b));
});

test('fixture api: evidence lookup picks the canned file by segment kind', async () => {
  const api = fixtureApi();
  const curves = load('curve_layer_B1.json');
  const find = (kind) => { for (const cv of curves.curves) { const i = cv.segments.findIndex((s) => s.kind === kind); if (i >= 0) return { cv, i }; } return null; };
  const expectRel = { OBSERVED: 'SUPPORTS_OBSERVED_SEGMENT', INFERRED_CONNECTOR: 'ENDPOINTS_OF_CONNECTOR', BLIND_HYPOTHESIS: 'HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE', MISSING_GAP: 'NO_SUPPORT' };
  for (const [kind, relation] of Object.entries(expectRel)) {
    const { cv, i } = find(kind);
    const r = await api.evidenceLookup({ pick: { layer: 'curve', ref: cv.curve_ref, result_sha256: cv.result_sha256, segment_index: i, t_click_s: 10.27 } });
    assert.equal(r.ok, true, `${kind}: ${r.error?.code}`);
    assert.equal(r.data.relation, relation);
    assert.equal(r.data.fixture_canned, true);
  }
  const obs = await api.evidenceLookup({ pick: { layer: 'observation', ref: 'cv-x', result_sha256: 'x', segment_index: 0, t_click_s: 1 } });
  assert.equal(obs.data.relation, 'IS_OBSERVATION');
  const unknown = await api.evidenceLookup({ pick: { layer: 'curve', ref: 'cv-nope', result_sha256: 'x', segment_index: 0, t_click_s: 1 } });
  assert.equal(unknown.error.code, 'FIXTURE_PICK_UNKNOWN');
  assert.equal(load(EVIDENCE_FIXTURES.HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE).jump, null, 'no automatic jump for a blind hypothesis');
  assert.equal(load(EVIDENCE_FIXTURES.NO_SUPPORT).jump, null);
});

test('fixture api: synced frames are #71 fixtures and need an explicit file name', async () => {
  const r = await fixtureApi().syncedFrames({ t_s: 1, camera_ids: ['CAM_W1'] });
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'FIXTURE_NOT_AVAILABLE');
  const seen = [];
  const api = fixtureApi({ fetchFn: async (u) => { seen.push(u); return { ok: true, status: 200, json: async () => ({ schema_version: 'wrong' }) }; } });
  const bad = await api.syncedFrames({ t_s: 1, camera_ids: ['CAM_W1'], fixture_name: 'synced_frames_4.json' });
  assert.equal(bad.error.code, 'SCHEMA_MISMATCH');
  assert.match(seen[0], /synced_frames_4\.json$/);
});

test('invalid requests never reach the network', async () => {
  let calls = 0;
  const api = fixtureApi({ fetchFn: async () => { calls++; return { ok: false, status: 500, json: async () => ({}) }; } });
  assert.equal((await api.personLayer({ time_range_s: [3, 1] })).error.code, 'INVALID_TIME_RANGE');
  assert.equal(calls, 0);
});

test('live api: POSTs the request JSON, maps 409/503, refuses fixture payloads and network failures', async () => {
  const sent = [];
  const mk = (status, body) => createApi({ mode: 'live', scope: { ...B1, clock_id: EXPECT.clock_id }, baseUrl: 'http://x', fetchFn: async (url, init) => { sent.push({ url, init }); return { ok: status < 400, status, json: async () => body }; } });
  const conflict = await mk(409, { schema_version: 'controlled-scene.error.v1', error: { error_class: 'DataIntegrityError', reason: 'PINNED_RGB_RECORD_MISSING' } }).personLayer({ time_range_s: [0, 1] });
  assert.equal(conflict.ok, false);
  assert.equal(conflict.error.code, 'PINNED_RGB_RECORD_MISSING');
  assert.equal(conflict.error.integrity, true);
  assert.equal(sent[0].url, 'http://x/api/person_layer');
  assert.equal(sent[0].init.method, 'POST');
  const body = JSON.parse(sent[0].init.body);
  assert.equal(body.schema_version, 'controlled-scene.person-layer-request.v1');
  assert.deepEqual(Object.keys(body).sort(), ['run_id', 'scene_id', 'schema_version', 'session_ref', 'time_range_s']);
  const unavailable = await mk(503, { error: { error_class: 'RequiredInputUnavailable', reason: 'CONTROLLED_RUN_NOT_CONFIGURED' } }).personLayer({ time_range_s: [0, 1] });
  assert.equal(unavailable.error.unavailable, true);
  const mixed = await mk(200, load('person_layer_B1.json')).personLayer({ time_range_s: [0, 1] });
  assert.equal(mixed.error.code, 'DATA_ORIGIN_MISMATCH');
  const net = await createApi({ mode: 'live', scope: B1, fetchFn: async () => { throw new Error('offline'); } }).personLayer({ time_range_s: [0, 1] });
  assert.equal(net.error.code, 'NETWORK_ERROR');
  assert.equal(net.error.unavailable, true);
});

test('epoch: a newer request of the same action discards the older response', async () => {
  const e = createEpoch();
  const a = e.begin('person_layer'), b = e.begin('person_layer'), other = e.begin('curve_layer');
  assert.equal(e.isCurrent('person_layer', a), false);
  assert.equal(e.isCurrent('person_layer', b), true);
  assert.equal(e.isCurrent('curve_layer', other), true);
  let release; const gate = new Promise((r) => { release = r; });
  let n = 0;
  const api = fixtureApi({ fetchFn: async (u) => { n++; if (n === 1) await gate; return diskFetch(u); } });
  const first = api.personLayer({ time_range_s: [0, 1] });
  const second = await api.personLayer({ time_range_s: [1, 2] });
  release();
  const stale = await first;
  assert.equal(second.ok, true);
  assert.equal(stale.ok, false);
  assert.equal(stale.stale, true);
  assert.equal(stale.error.code, 'STALE_RESPONSE');
});

test('bootstrap: fixture origin is detected; gt_read must be false', () => {
  const b = load('bootstrap_fixture.json');
  const r = validateBootstrap(b);
  assert.equal(r.ok, true);
  assert.equal(r.fixture, true);
  assert.equal(r.configured, true);
  assert.equal(validateBootstrap({ ...b, gt_read: true }).error.code, 'GT_READ_NOT_FALSE');
  assert.equal(validateBootstrap({ schema_version: 'x' }).error.code, 'BOOTSTRAP_INVALID');
  const un = validateBootstrap({ ...b, data_origin: 'UNCONFIGURED' });
  assert.equal(un.fixture, false);
  assert.equal(un.configured, false);
});

// ---- fixtures ----
test('generator is deterministic: a fresh run equals the committed files byte for byte', () => {
  const fresh = buildAll();
  const second = buildAll();
  assert.deepEqual(Object.keys(fresh), Object.keys(second));
  for (const [name, text] of Object.entries(fresh)) {
    assert.equal(text, second[name], `${name} differs between two runs`);
    assert.equal(readFileSync(new URL(name, FIX), 'utf8'), text, `${name} differs from the committed file; run generate_v2_fixtures.mjs`);
  }
  const onDisk = readdirSync(FIX).filter((n) => n.endsWith('.json') && !n.startsWith('synced_frames_'));
  assert.deepEqual(onDisk.sort(), Object.keys(fresh).sort(), 'no stray fixture files');
});

test('every fixture is marked SYNTHETIC and its output_sha256 is the canonical hash of the rest (contract §2.1)', () => {
  for (const name of Object.keys(buildAll())) {
    const d = load(name);
    assert.equal(typeof d.SYNTHETIC, 'string', name);
    assert.equal(d.data_origin, FIXTURE_ORIGIN, name);
    const { output_sha256: h, ...rest } = d;
    assert.equal(h, sha(canonicalJson(rest)), `${name} hash`);
  }
});

test('fixtures carry no GT, actor, renderer or private-path fields; composed grounds never depend on a pose model', () => {
  const bad = /actor|persons\.sim|renderer|depth|visibility_mask|designed_blind|\/Users\//i;
  const walk = (v, name) => {
    if (Array.isArray(v)) v.forEach((x) => walk(x, name));
    else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) { assert.doesNotMatch(k, bad, `${name}: key ${k}`); if (typeof x === 'string') assert.doesNotMatch(x, bad, `${name}: value ${x}`); walk(x, name); }
  };
  for (const name of Object.keys(buildAll())) walk(load(name), name);
  for (const e of load('person_layer_B1.json').estimates) assert.equal(e.composed_ground.pose_model, 'NOT_USED');
});

test('fixture content: states, humanoid rule, blind interval and missing gap are present as designed', () => {
  const p = load('person_layer_B1.json');
  assert.ok(p.estimates.some((e) => e.display.humanoid_range_allowed) && p.estimates.some((e) => !e.display.humanoid_range_allowed));
  assert.ok(p.estimates.every((e) => e.identity_verdict === 'UNCONFIRMED' && e.physical_verdict === 'UNKNOWN'));
  assert.ok(p.estimates.some((e) => e.heading.state === 'INFERRED') && p.estimates.some((e) => e.heading.state === 'UNKNOWN'));
  const c = load('curve_layer_B1.json');
  const blind = c.curves.find((x) => x.curve_ref === 'cv-B1-blind-01');
  assert.equal(blind.segments[0].unassociated_baseline, true);
  assert.equal(blind.association.identity_verdict, 'UNCONFIRMED');
  assert.ok(c.curves.some((x) => x.segments.some((s) => s.kind === 'MISSING_GAP')));
  assert.ok(!load('curve_layer_A.json').curves.some((x) => x.curve_ref === 'cv-B1-blind-01'));
  assert.equal(load('candidate_cameras_A.json').status, 'READY');
});

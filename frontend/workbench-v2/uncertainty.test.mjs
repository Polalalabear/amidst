import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  COMPOSED_EVIDENCE_STATE, DESIGN_ESTIMATE_LINE, ERR, QUALITY_LIMITS, errorSources, gradeFor, humanoidRangeAllowed, readoutText, roundOutward,
  validateCurveLayer, validateInferenceItem, validatePersonLayer, validateUncertainty,
} from './uncertainty.mjs';

const load = (n) => JSON.parse(readFileSync(new URL(`./fixtures/${n}`, import.meta.url), 'utf8'));
const clone = (v) => structuredClone(v);
const SHA = 'a'.repeat(64);
const u = (kind, value, extra = {}) => ({ extent_kind: kind, extent_value: value, constraints_used: ['speed'], quality_grade: gradeFor(kind, value), quality_rule_ref: 'quality-grade-rule-v1', quality_rule_sha256: SHA, ...extra });
const ready = (extra = {}) => ({ status: 'READY', uncertainty: u('LENGTH_M', 0.49), ...extra });

test('quality grades follow D56 Q13 at the boundaries', () => {
  assert.deepEqual(QUALITY_LIMITS, { LENGTH_M: [0.25, 1.0], AREA_M2: [0.25, 4.0], ANGLE_DEG: [15, 45] });
  const cases = [['LENGTH_M', 0.25, 'HIGH'], ['LENGTH_M', 0.2500001, 'MEDIUM'], ['LENGTH_M', 1.0, 'MEDIUM'], ['LENGTH_M', 1.01, 'LOW'],
    ['AREA_M2', 0.25, 'HIGH'], ['AREA_M2', 4, 'MEDIUM'], ['AREA_M2', 4.01, 'LOW'], ['ANGLE_DEG', 15, 'HIGH'], ['ANGLE_DEG', 45, 'MEDIUM'], ['ANGLE_DEG', 46, 'LOW']];
  for (const [k, v, g] of cases) assert.equal(gradeFor(k, v), g, `${k} ${v}`);
  assert.equal(gradeFor('LENGTH_M', null), 'UNKNOWN');
});

test('the composed-ground state name is one constant (CS-Q15 is OPEN)', () => {
  assert.equal(COMPOSED_EVIDENCE_STATE, 'INFERRED_CONSTRAINED');
});

test('display precision rounds outward: 0.01 m, 0.1 m², 1°', () => {
  assert.equal(roundOutward(0.49, 'LENGTH_M'), '0.49');
  assert.equal(roundOutward(0.491, 'LENGTH_M'), '0.50');
  assert.equal(roundOutward(0.07, 'LENGTH_M'), '0.07');
  assert.equal(roundOutward(7.2, 'AREA_M2'), '7.2');
  assert.equal(roundOutward(7.21, 'AREA_M2'), '7.3');
  assert.equal(roundOutward(0.01, 'AREA_M2'), '0.1');
  assert.equal(roundOutward(14.1, 'ANGLE_DEG'), '15');
  assert.equal(roundOutward(15, 'ANGLE_DEG'), '15');
  for (const [kind, value] of [['LENGTH_M', 0.333], ['AREA_M2', 3.01], ['ANGLE_DEG', 22.2]]) assert.ok(Number(roundOutward(value, kind)) >= value, 'never smaller than the true value');
});

test('readoutText: contract wording and conditions', () => {
  const seg = { status: 'READY', foot_status: 'OCCLUDED_BY_STATIC', geometry: { kind: 'SEGMENT' }, uncertainty: u('LENGTH_M', 0.49, { constraints_used: ['track_height', 'occlusion_near', 'lowest_visible_far', 'speed'] }) };
  assert.equal(readoutText(seg), '區間 0.49 m（軌跡身高＋遮擋邊界＋速度界）'); // lowest_visible_far is inspector-only
  assert.equal(readoutText({ ...seg, foot_status: 'VISIBLE', uncertainty: u('LENGTH_M', 0.44, { constraints_used: [] }) }), '區間 0.44 m（腳點像素帶）');
  assert.equal(readoutText({ geometry: { kind: 'POLYGON' }, uncertainty: u('AREA_M2', 0.41, { constraints_used: ['prior'] }) }), '窄帶 0.5 m²（先驗）');
  assert.equal(readoutText({ kind: 'BLIND_HYPOTHESIS', uncertainty: u('AREA_M2', 7.2, { constraints_used: ['endpoint_estimates', 'k1_reachability', 'speed'] }) }), '範圍帶 7.2 m²（兩端估計＋K1 可達範圍＋速度界）');
  assert.equal(readoutText({ kind: 'INFERRED_CONNECTOR', uncertainty: u('AREA_M2', 0.11, { constraints_used: ['endpoint_estimates'] }) }), '緞帶 0.2 m²（兩端估計）');
  assert.equal(readoutText({ uncertainty: u('ANGLE_DEG', 12.3, { constraints_used: ['endpoint_estimates'] }) }), '方向範圍 13°（兩端估計）');
  assert.equal(readoutText({ status: 'UNKNOWN', reason: 'CONSTRAINTS_INCONSISTENT', uncertainty: { extent_value: null, quality_grade: 'UNKNOWN' } }), 'UNKNOWN（CONSTRAINTS_INCONSISTENT）');
  assert.equal(readoutText({}), null);
});

test('errorSources lists used and unused conditions and always ends with the design-estimate line', () => {
  const p = load('person_layer_B1.json');
  const oof = p.estimates.find((e) => e.composed_ground.foot_status === 'OUT_OF_FRAME').composed_ground;
  const lines = errorSources(oof);
  assert.equal(lines.at(-1), DESIGN_ESTIMATE_LINE);
  assert.match(lines[0], /^範圍：區間 /);
  assert.ok(lines.some((l) => l.startsWith('用到：')) && lines.some((l) => l.startsWith('沒用到：')));
  assert.ok(lines.some((l) => l.includes('校正誤差：UNKNOWN')));
  assert.ok(lines.some((l) => l.includes('clock_error_s：UNKNOWN')));
  assert.ok(errorSources({}, { clockErrorS: 0 }).some((l) => l.includes('clock_error_s：0 s')));
  assert.equal(errorSources({}).at(-1), DESIGN_ESTIMATE_LINE);
});

test('humanoid range (D56 Q25): only HIGH LENGTH_M, only the current sample', () => {
  const c = (kind, v) => ({ status: 'READY', uncertainty: u(kind, v) });
  assert.equal(humanoidRangeAllowed(c('LENGTH_M', 0.25)), true);
  assert.equal(humanoidRangeAllowed(c('LENGTH_M', 0.26)), false);
  assert.equal(humanoidRangeAllowed(c('AREA_M2', 0.2)), false);
  assert.equal(humanoidRangeAllowed(c('LENGTH_M', 0.1), { isCurrentSample: false }), false);
  assert.equal(humanoidRangeAllowed({ status: 'UNKNOWN', uncertainty: { extent_value: null, quality_grade: 'UNKNOWN' } }), false);
  assert.equal(humanoidRangeAllowed(null), false);
});

test('fixtures: all good layers pass; humanoid_range_allowed follows the HIGH rule', () => {
  for (const n of ['person_layer_A.json', 'person_layer_B1.json', 'curve_layer_A.json', 'curve_layer_B1.json']) assert.equal(validateUncertainty(load(n)), null, n);
  for (const n of ['person_layer_A.json', 'person_layer_B1.json']) {
    for (const e of load(n).estimates) assert.equal(e.display.humanoid_range_allowed, humanoidRangeAllowed(e.composed_ground), e.estimate_ref);
  }
});

test('validateInferenceItem: each of the six required fields missing -> UNCERTAINTY_FIELDS_MISSING', () => {
  for (const f of ['extent_kind', 'extent_value', 'constraints_used', 'quality_grade', 'quality_rule_ref', 'quality_rule_sha256']) {
    const item = ready(); delete item.uncertainty[f];
    assert.equal(validateInferenceItem(item).code, ERR.MISSING, f);
  }
  assert.equal(validateInferenceItem({ status: 'READY' }).code, ERR.MISSING);
});

test('validateInferenceItem: invalid values -> UNCERTAINTY_FIELDS_INVALID (same cases as #75)', () => {
  const bad = (patch, opts) => { const item = ready(); Object.assign(item.uncertainty, patch); return validateInferenceItem(item, opts)?.code; };
  assert.equal(bad({ extent_value: -0.1, quality_grade: 'HIGH' }), ERR.INVALID);
  assert.equal(bad({ extent_value: NaN }), ERR.INVALID);
  assert.equal(bad({ extent_value: Infinity }), ERR.INVALID);
  assert.equal(bad({ extent_value: '0.49' }), ERR.INVALID);
  assert.equal(bad({ extent_value: true }), ERR.INVALID);
  assert.equal(bad({ extent_value: null }), ERR.INVALID);
  assert.equal(bad({ extent_kind: 'WIDTH' }), ERR.INVALID);
  assert.equal(bad({ extent_kind: 'ANGLE_DEG', extent_value: 10, quality_grade: 'HIGH' }), ERR.INVALID, 'ANGLE_DEG only for heading');
  assert.equal(bad({}, { expectedExtent: 'ANGLE_DEG' }), ERR.INVALID, 'heading must be ANGLE_DEG');
  assert.equal(bad({ quality_grade: 'HIGH' }), ERR.INVALID, 'grade must match the rule');
  assert.equal(bad({ constraints_used: 'speed' }), ERR.INVALID);
  assert.equal(bad({ constraints_used: [''] }), ERR.INVALID);
  assert.equal(bad({ quality_rule_ref: '' }), ERR.INVALID);
  assert.equal(bad({ quality_rule_sha256: 'abc' }), ERR.INVALID);
  assert.equal(bad({ quality_rule_sha256: 'A'.repeat(64) }), ERR.INVALID);
  assert.equal(bad({ per_sample_ref: '' }), ERR.INVALID);
  assert.equal(bad({ surprise: 1 }), ERR.INVALID);
  assert.equal(validateInferenceItem({ status: 'DONE', uncertainty: u('LENGTH_M', 0.1) }).code, ERR.INVALID);
});

test('UNKNOWN items: geometry null, extent null, grade UNKNOWN, reason listed', () => {
  const ok = { status: 'UNKNOWN', geometry: null, reason: 'ALL_CONSTRAINTS_UNAVAILABLE', uncertainty: { extent_value: null, quality_grade: 'UNKNOWN' } };
  assert.equal(validateInferenceItem(ok), null);
  assert.equal(validateInferenceItem({ ...ok, reason: '' }).code, ERR.INVALID);
  assert.equal(validateInferenceItem({ ...ok, geometry: { kind: 'SEGMENT' } }).code, ERR.INVALID);
  assert.equal(validateInferenceItem({ ...ok, uncertainty: { extent_value: 0.2, quality_grade: 'UNKNOWN' } }).code, ERR.INVALID);
  assert.equal(validateInferenceItem({ ...ok, uncertainty: { extent_value: null, quality_grade: 'LOW' } }).code, ERR.INVALID);
  const noGeometryKey = { ...ok }; delete noGeometryKey.geometry;
  assert.equal(validateInferenceItem(noGeometryKey).code, ERR.INVALID);
});

test('person layer: deleting uncertainty or composed_ground fails closed with the estimate ref', () => {
  const p = load('person_layer_B1.json');
  const one = (mut) => { const c = clone(p); c.estimates = c.estimates.slice(0, 8); mut(c.estimates.find((e) => e.composed_ground.status === 'READY')); return validatePersonLayer(c); };
  assert.equal(one((e) => { delete e.composed_ground.uncertainty; }).code, ERR.MISSING);
  assert.match(one((e) => { delete e.composed_ground.uncertainty; }).estimate_ref, /^pe-B1-/);
  assert.equal(one((e) => { delete e.composed_ground; }).code, ERR.MISSING);
  assert.equal(one((e) => { e.composed_ground.uncertainty.quality_grade = 'LOW'; }).code, ERR.INVALID);
  assert.equal(one((e) => { e.composed_ground.evidence_state = 'INFERRED_HYPOTHESIS'; }).code, ERR.ITEM);
  assert.equal(one((e) => { e.composed_ground.status = 'MAYBE'; }).code, ERR.ITEM);
});

test('person layer: constraint kinds are the five fixed names (stricter than #75)', () => {
  const p = load('person_layer_B1.json'); p.estimates = p.estimates.slice(0, 8);
  const e = p.estimates.find((x) => x.composed_ground.status === 'READY');
  e.composed_ground.constraints_unavailable.push({ kind: 'height_prior', reason: 'X' });
  assert.equal(validatePersonLayer(p).code, ERR.CONSTRAINT_KIND);
  const q = load('person_layer_B1.json'); q.estimates = q.estimates.slice(0, 8);
  const f = q.estimates.find((x) => x.composed_ground.status === 'READY'); delete f.composed_ground.constraints_used;
  assert.equal(validatePersonLayer(q).code, ERR.MISSING);
});

test('heading: UNKNOWN has no direction; inferred needs a unit-less non-zero direction and an ANGLE_DEG uncertainty', () => {
  const full = load('person_layer_B1.json');
  const idx = full.estimates.findIndex((x) => x.heading.state === 'INFERRED');
  const sub = (mut) => { const c = clone(full); c.estimates = [c.estimates[idx]]; mut(c.estimates[0]); return validatePersonLayer(c)?.code ?? null; };
  assert.equal(sub(() => {}), null);
  assert.equal(sub((x) => { x.heading.direction_xy = [0, 0]; }), ERR.ITEM);
  assert.equal(sub((x) => { x.heading.direction_xy = [1]; }), ERR.ITEM);
  assert.equal(sub((x) => { delete x.heading.uncertainty; }), ERR.MISSING);
  assert.equal(sub((x) => { x.heading.uncertainty = u('LENGTH_M', 0.2); }), ERR.INVALID);
  assert.equal(sub((x) => { x.heading = { state: 'UNKNOWN', reason: 'R', direction_xy: [1, 0] }; }), ERR.ITEM);
  assert.equal(sub((x) => { x.heading = { state: 'GUESS' }; }), ERR.ITEM);
});

test('curve layer: closed kind set; inferred kinds need uncertainty; OBSERVED/MISSING_GAP do not', () => {
  const c = load('curve_layer_B1.json');
  const kinds = new Set(c.curves.flatMap((x) => x.segments.map((s) => s.kind)));
  assert.deepEqual([...kinds].sort(), ['BLIND_HYPOTHESIS', 'INFERRED_CONNECTOR', 'MISSING_GAP', 'OBSERVED']);
  const mutate = (kind, mut) => { const d = clone(c); const cv = d.curves.find((x) => x.segments.some((s) => s.kind === kind)); mut(cv.segments.find((s) => s.kind === kind)); return validateCurveLayer(d)?.code ?? null; };
  assert.equal(mutate('INFERRED_CONNECTOR', (s) => { delete s.uncertainty; }), ERR.MISSING);
  assert.equal(mutate('BLIND_HYPOTHESIS', (s) => { delete s.uncertainty.extent_value; }), ERR.MISSING);
  assert.equal(mutate('BLIND_HYPOTHESIS', (s) => { s.kind = 'UI_UNKNOWN_SPAN'; }), ERR.CURVE_KIND);
  assert.equal(mutate('BLIND_HYPOTHESIS', (s) => { s.kind = 'PREDICTION'; delete s.uncertainty; }), ERR.MISSING);
  assert.equal(mutate('INFERRED_CONNECTOR', (s) => { s.uncertainty.extent_kind = 'ANGLE_DEG'; }), ERR.INVALID);
  assert.equal(mutate('OBSERVED', () => {}), null);
  assert.equal(mutate('MISSING_GAP', () => {}), null);
  assert.equal(validateCurveLayer({ curves: [{ segments: 'x' }] }).code, ERR.LAYER);
  assert.equal(validateCurveLayer({}).code, ERR.LAYER);
});

test('validateUncertainty handles non-objects and layers it does not know', () => {
  assert.equal(validateUncertainty(null).code, ERR.LAYER);
  assert.equal(validateUncertainty({ candidates: [] }), null);
  assert.equal(validateUncertainty({ estimates: 'x' }).code, ERR.LAYER);
});

test('deliberately broken fixtures are rejected', () => {
  assert.equal(validateUncertainty(load('person_layer_missing_uncertainty.json')).code, ERR.MISSING);
});

test('blind-hypothesis area peaks in the fixture match the curve uncertainty', () => {
  const h = load('blind_hypothesis_B1.json');
  const seg = load('curve_layer_B1.json').curves.find((c) => c.curve_ref === 'cv-B1-blind-01').segments[0];
  assert.equal(seg.uncertainty.extent_value, Math.max(...h.reachable_regions.map((r) => r.area_m2)));
  assert.equal(seg.uncertainty.extent_kind, 'AREA_M2');
  assert.equal(seg.hypothesis_response_sha256, h.output_sha256);
});

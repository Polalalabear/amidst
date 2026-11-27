// E6 routes (#732 G1+G2, D396). Structural and E3-disjointness checks need no assets; the simulation check reads the
// LOCAL N6 folder ($AMIDST_LIVE_ASSETS or $AMIDST_ARTIFACTS/data/live-assets-20261115) and skips when it is absent (CI).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {loadE6} from '../../../scripts/evaluation/e3_cases/e6_routes.mjs';
import {E3_ROUTES} from '../../../scripts/evaluation/e3_cases/routes.mjs';
import {REAPPEARANCE_ROUTES} from '../../../scripts/evaluation/e3_cases/reappearance_routes.mjs';
import {HARDSET_ROUTES} from '../src/hardset_routes.mjs';
import {createCrowd} from '../src/crowd.mjs';

const root = new URL('../../../', import.meta.url).pathname;
const spec = JSON.parse(fs.readFileSync(path.join(root, 'configs/evaluation/e6_scenarios_spec_v1.json')));
const {doc, routes} = loadE6();
const assets = process.env.AMIDST_LIVE_ASSETS
  || path.join(process.env.AMIDST_ARTIFACTS || path.join(os.homedir(), 'amidst', 'local'), 'data', 'live-assets-20261115');
const skipAssets = ['scene.glb', 'character.glb', 'cameras.three.json'].every(f => fs.existsSync(path.join(assets, f))) ? false : 'N6 LOCAL assets not found';

test('E6 routes: 12 cases, ids and dp ids match the frozen spec, every decision point has a kind', () => {
  assert.deepEqual(doc.cases.map(c => c.case_id), spec.formal_cases.map(c => c.case_id));
  for (const c of doc.cases) {
    const sc = spec.formal_cases.find(x => x.case_id === c.case_id);
    assert.equal(c.family_id, sc.family_id);
    assert.deepEqual(c.spec_start_xy, sc.start_xy);
    for (const dp of sc.planned_decision_points) assert.ok(['reappear', 'handoff', 'cross', 'split', 'blind', 'visible'].includes(c.dp_kinds[dp.dp_id]), dp.dp_id);
    assert.equal(Object.keys(c.dp_kinds).length, sc.planned_decision_points.length);
  }
});

test('E6 routes: distractors follow has_similar_distractor; birth after the seed window; times increase', () => {
  for (const c of doc.cases) {
    const sc = spec.formal_cases.find(x => x.case_id === c.case_id);
    const red = c.actors.filter(a => a.actor_id === 'A');
    assert.equal(red.length, sc.has_similar_distractor ? 1 : 0, c.case_id);
    assert.ok(c.actors.every(a => a.actor_id !== 'B'), 'no orange-red B in E6');
    for (const a of c.actors) {
      assert.ok(a.waypoints[0][0] >= doc.min_actor_birth_s);
      for (let i = 1; i < a.waypoints.length; i++) assert.ok(a.waypoints[i][0] >= a.waypoints[i - 1][0]);
    }
    const run = routes[c.case_id].run;
    assert.ok(run.duration_us / 1e6 > c.planned_duration_s, 'scripted actors must not loop inside the recording');
  }
});

test('E6 routes: start points are on a floor, clear of walls, distinct, and not near any E3 start', () => {
  const geometry = JSON.parse(fs.readFileSync(path.join(root, 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json')));
  const onFloor = ([x, y]) => geometry.floors.some(f => x >= f.x_m[0] && x <= f.x_m[1] && y >= f.y_m[0] && y <= f.y_m[1]);
  const e3 = [...Object.values(E3_ROUTES), ...Object.values(REAPPEARANCE_ROUTES), ...Object.values(HARDSET_ROUTES)].map(r => r.start_xy);
  const seen = new Set();
  for (const c of doc.cases) {
    assert.ok(onFloor(c.start_xy), `${c.case_id} start on floor`);
    assert.ok(!seen.has(c.start_xy.join()), 'distinct starts'); seen.add(c.start_xy.join());
    for (const s of e3) assert.ok(Math.hypot(s[0] - c.start_xy[0], s[1] - c.start_xy[1]) >= 0.5, `${c.case_id} too near an E3 start`);
    const crowd = createCrowd(routes[c.case_id].run, {actorId: 'T', segments: geometry.clearance_segments});
    assert.equal(crowd.snapshot().spawn_adjusted.length, 0, `${c.case_id} spawn must not need adjustment`);
  }
});

test('E6 routes: no E3 or hard-set route shares more than 2 contiguous waypoints with any E6 target route', () => {
  const tok = r => r.steps.filter(s => s.to_xy).map(s => `${s.to_xy[0]},${s.to_xy[1]}`);
  const common = (a, b) => { let best = 0; const d = Array(b.length + 1).fill(0);
    for (let i = 1; i <= a.length; i++) { let prev = 0; for (let j = 1; j <= b.length; j++) { const t = d[j]; d[j] = a[i - 1] === b[j - 1] ? prev + 1 : 0; best = Math.max(best, d[j]); prev = t; } } return best; };
  const others = [...Object.values(E3_ROUTES), ...Object.values(REAPPEARANCE_ROUTES), ...Object.values(HARDSET_ROUTES)];
  for (const [id, r] of Object.entries(routes)) for (const o of others) assert.ok(common(tok(r), tok(o)) <= 2, id);
});

test('E6 routes: design check on the production crowd (every planned decision point realized, no stalls)', {skip: skipAssets}, async () => {
  const {setup} = await import('../../../scripts/evaluation/e3_cases/generate.mjs');
  const {simulate, summarize} = await import('../../../scripts/evaluation/e3_cases/e6_design_check.mjs');
  const env = setup(assets);
  for (const c of doc.cases) {
    const r = summarize(c, simulate(routes[c.case_id], env, c.case_id));
    assert.ok(r.all_ok, `${c.case_id}: ${JSON.stringify(r.decision_points.filter(d => !d.ok))}`);
  }
});

test('E6 routes: frozen (D399) - detector source pinned, distractor speed <= 2.1 m/s, decision-point windows cannot overlap', () => {
  assert.equal(doc.status, 'FROZEN_ROUTES_V1');
  const sha = createHash('sha256').update(fs.readFileSync(path.join(root, doc.detector_source.path))).digest('hex');
  assert.equal(sha, doc.detector_source.sha256, 'e6_design_check.mjs changed after the freeze');
  for (const c of doc.cases) for (const a of c.actors) for (let i = 1; i < a.waypoints.length; i++) {
    const [t0, x0, y0] = a.waypoints[i - 1], [t1, x1, y1] = a.waypoints[i];
    if (t1 > t0) assert.ok(Math.hypot(x1 - x0, y1 - y0) / (t1 - t0) <= doc.actor_max_speed_mps + 1e-9, `${c.case_id} actor ${a.actor_id} segment ${i}`);
  }
});

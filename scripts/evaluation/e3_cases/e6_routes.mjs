// E6 (#732 G1+G2, D396): A-private route plans for the 12 new E6 cases. No scored answers; never imported by
// inference or ranking. The data lives in configs/evaluation/e6_routes_v1.json; this module only compiles it into
// the same {run, route} shapes the E3 generator already consumes. E3 routes and recordings are untouched.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const ROOT = fileURLToPath(new URL('../../../', import.meta.url));
export const E6_ROUTES_PATH = path.join(ROOT, 'configs/evaluation/e6_routes_v1.json');
const finite = v => Number.isFinite(v);
const xy = (p, why) => { if (!Array.isArray(p) || p.length !== 2 || !p.every(finite)) throw new Error(`E6_BAD_XY:${why}`); return [...p]; };

export function compileSteps(steps, caseId) {
 return steps.map((s, i) => {
  const [mode, a] = s;
  if (mode === 'walk' || mode === 'run') return {mode, to_xy: xy(a, `${caseId}.steps[${i}]`)};
  if (mode === 'hold') { if (!finite(a) || a < 0) throw new Error(`E6_BAD_HOLD:${caseId}[${i}]`); return {mode, seconds: a}; }
  if (mode === 'until') { if (!finite(a) || a < 0) throw new Error(`E6_BAD_UNTIL:${caseId}[${i}]`); return {mode: 'hold_until', t_s: a}; }
  throw new Error(`E6_BAD_STEP_MODE:${caseId}[${i}]:${mode}`);
 });
}

// Synthetic scenario run in the same schema as R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json: T is the operator-controlled
// target (only waypoints[0] is read), A is the new red-vest distractor (same red top material as T, D124 variant A),
// C is the blue control pedestrian. Scripted actors loop at duration_us, so duration exceeds the recording length.
export function buildRun(c, doc) {
 const dur = Math.round((c.planned_duration_s + doc.run_margin_s) * 1e6);
 const actors = [{actor_id: 'T', role: 'TARGET', waypoints: [{t_us: 0, xy: xy(c.start_xy, c.case_id)}, {t_us: dur, xy: xy(c.start_xy, c.case_id)}]}];
 for (const d of c.actors ?? []) {
  const wps = d.waypoints.map(([t, x, y]) => ({t_us: Math.round(t * 1e6), xy: xy([x, y], `${c.case_id}.${d.actor_id}`)}));
  for (let i = 1; i < wps.length; i++) if (wps[i].t_us < wps[i - 1].t_us) throw new Error(`E6_WAYPOINT_ORDER:${c.case_id}.${d.actor_id}[${i}]`);
  if (wps[0].t_us < doc.min_actor_birth_s * 1e6) throw new Error(`E6_ACTOR_BORN_BEFORE_SEED_WINDOW:${c.case_id}.${d.actor_id}`);
  actors.push({actor_id: d.actor_id, role: d.role, kind: d.kind, waypoints: wps});
 }
 return {run_id: c.case_id, scenario: c.case_id, duration_us: dur, actors};
}

export function buildRoute(c, doc) {
 const run = buildRun(c, doc);
 return {run, run_id: run.run_id, start_xy: xy(c.start_xy, c.case_id), family: c.family_id, tail_s: c.tail_s ?? 0,
  steps: compileSteps(c.target_steps, c.case_id)};
}

export function loadE6(file = E6_ROUTES_PATH) {
 const doc = JSON.parse(fs.readFileSync(file));
 if (doc.schema !== 'amidst.e6-routes.v1') throw new Error('E6_ROUTES_SCHEMA');
 const spec = JSON.parse(fs.readFileSync(path.join(ROOT, doc.spec_ref.path))), routes = {}, runs = [];
 for (const c of doc.cases) {
  const sc = spec.formal_cases.find(x => x.case_id === c.case_id);
  if (!sc) throw new Error(`E6_CASE_NOT_IN_SPEC:${c.case_id}`);
  c.planned_decision_points = sc.planned_decision_points; c.spec_start_xy = sc.start_xy; c.planned_duration_s ??= sc.planned_duration_s; const r = buildRoute(c, doc); routes[c.case_id] = r; runs.push(r.run); }
 // Scenario document served to the LIVE A page for E6 recording (same layout as the A4/B4 draft, runs replaced).
 return {doc, routes, runs};
}

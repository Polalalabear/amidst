// E6 design check (#732): simulates each route on the production crowd and reports, per case, where the target is
// visible/blind and how it meets the distractor. Uses the evaluation-only GT visibility function; the output is a
// DESIGN CHECK for Opus review, never an input to inference, ranking, scoring or the frozen answer table.
// usage: e6_design_check.mjs OUT.json ASSETS [CASE_IDS...]
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {setup} from './generate.mjs';
import {loadE6} from './e6_routes.mjs';
import {createCrowd} from '../../../frontend/live-mode/src/crowd.mjs';
import {createScriptOperator} from '../../../frontend/live-mode/src/script_operator.mjs';
import {RECORD_DT} from '../../../frontend/live-mode/src/recording.mjs';
import {groundTruthVisible} from '../../../frontend/live-mode/src/world.mjs';

const WINDOW_TICKS = 15, FPS = 5;
const fmt = a => a.length ? a.join('+') : '-';
const dist = (a, b) => a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : null;

export function simulate(route, env, id) {
 const {world, cams} = env, crowd = createCrowd(route.run, {actorId: 'T', segments: world.segments}), op = createScriptOperator(route);
 const rows = []; let doneAt = null;
 const vis = a => a.present ? groundTruthVisible(cams, world.blockers, world.root, a.x, a.y) : [];
 for (let n = 0; n < 4000; n++) {
  const s = crowd.snapshot(), p = s.actors.find(a => a.is_player), keys = op.keys(p, s.t_sim);
  if (op.done && doneAt === null) doneAt = s.tick;
  if (s.tick % 4 === 0) rows.push({tick: s.tick / 4, t: s.t_sim, actors: Object.fromEntries(s.actors.map(a => [a.actor_id, {present: a.present, xy: a.present ? [a.x, a.y] : null, vis: vis(a)}]))});
  if (doneAt !== null && s.tick >= doneAt + Math.round(route.tail_s / RECORD_DT) && s.tick % 4 === 0) break;
  crowd.step(keys, RECORD_DT);
 }
 return {rows, complete: op.done, stalls: op.events.filter(e => e.type === 'script_stall'), spawn_adjusted: crowd.snapshot().spawn_adjusted};
}

export function summarize(c, sim) {
 const {rows} = sim, T = r => r.actors.T, A = r => r.actors.A ?? r.actors.C;
 const segs = [];   // runs of identical T camera set
 for (const r of rows) {
  const k = T(r).present ? fmt(T(r).vis) : 'ABSENT', last = segs.at(-1);
  if (last && last.k === k) last.end = r.tick / FPS; else segs.push({k, start: r.tick / FPS, end: r.tick / FPS});
 }
 const blind = segs.filter(s => s.k === '-').map(s => ({start_s: s.start, end_s: s.end + 1 / FPS, duration_s: +(s.end - s.start + 1 / FPS).toFixed(2)}));
 let closest = null, co = null;
 for (const r of rows) if (A(r)?.present) {
  const d = dist(T(r).xy, A(r).xy); if (d !== null && (!closest || d < closest.d)) closest = {d: +d.toFixed(2), t: r.tick / FPS};
  const shared = T(r).vis.filter(v => A(r).vis.includes(v));
  if (shared.length && d !== null && (!co || d < co.d)) co = {d: +d.toFixed(2), t: r.tick / FPS, cams: shared};
 }
 const aVisible = rows.filter(r => A(r)?.present && A(r).vis.length).map(r => r.tick / FPS);
 const firstAVis = aVisible.length ? aVisible[0] : null;
 const seedClean = !rows.slice(0, 11).some(r => A(r)?.present && A(r).vis.length);   // no other person visible in the first 2 s
 const specDps = c.planned_decision_points;   // merged from the spec by loadE6; kinds are this design's mapping
 const vTick = r => T(r).present && T(r).vis.length > 0;
 const events = {reappear: [], handoff: [], cross: [], split: []};
 // handoff: a camera that saw T for >= 2 s stops seeing it while another camera still does (source camera hands over).
 const hand = []; for (let i = 10; i < rows.length; i++) {
  if (!vTick(rows[i])) continue;
  const lost = T(rows[i - 1]).vis.filter(v => !T(rows[i]).vis.includes(v) && rows.slice(i - 11, i).every(r => T(r).vis.includes(v)));
  if (lost.length && (!hand.length || rows[i].tick / FPS - hand.at(-1) >= 3)) hand.push(rows[i].tick / FPS);
 }
 // short-gap handoff: T leaves one camera set, is unseen for <= 1.5 s, and returns in a disjoint set (e.g. W2 -> BRANCH behind the corner screen)
 for (let i = 1; i < rows.length; i++) if (vTick(rows[i]) && !vTick(rows[i - 1])) {
  let j = i - 1; while (j > 0 && !vTick(rows[j])) j--;
  const g = (i - j - 1) / FPS; if (g <= 1.5 && !T(rows[j]).vis.some(v => T(rows[i]).vis.includes(v))) hand.push(rows[i].tick / FPS);
 }
 hand.sort((a, b) => a - b); events.handoff = hand.filter((x, k) => k === 0 || x - hand[k - 1] >= 3 || (hand[k] = hand[k - 1], false));
 for (let i = 1; i < rows.length; i++) {
  if (vTick(rows[i]) && !vTick(rows[i - 1])) { let j = i - 1; while (j > 0 && !vTick(rows[j])) j--; const g = (i - j - 1) / FPS; if (g >= 3 && g <= 10) events.reappear.push(rows[i].tick / FPS); }
 }
 const dco = r => A(r)?.present && T(r).present && T(r).vis.some(v => A(r).vis.includes(v)) ? dist(T(r).xy, A(r).xy) : null;
 for (let i = 1; i < rows.length - 1; i++) { const m = dco(rows[i]); if (m !== null && m <= 2.0 && (dco(rows[i - 1]) ?? 99) >= m && (dco(rows[i + 1]) ?? 99) >= m) events.cross.push(rows[i].tick / FPS); }
 // split: first tick after >= 2 s of proximity (<= 2.5 m, both present, camera sets may differ) where the distance exceeds 3.5 m
 const dpr = r => A(r)?.present && T(r).present ? dist(T(r).xy, A(r).xy) : null;
 for (let i = 10; i < rows.length; i++) { const d = dpr(rows[i]); if (d !== null && d > 3.5 && rows.slice(i - 10, i).every(r => (dpr(r) ?? 99) <= 3.5) && rows.slice(i - 10, i).some(r => (dpr(r) ?? 99) <= 2.5)) { events.split.push(rows[i].tick / FPS); break; } }
 const regimeAt = t => { const k = Math.round(t * FPS), win = rows.slice(k, k + WINDOW_TICKS);
  if (win.length < WINDOW_TICKS) return 'WINDOW_OUT_OF_RECORDING'; return win.some(vTick) ? 'VISIBLE' : win.some(r => T(r).present) ? 'FULL_BLIND' : 'TRUE_DEPARTURE'; };
 const TOL = c.dp_tolerance_s ?? 3.0;
 const dps = specDps.map(dp => {
  const kind = c.dp_kinds[dp.dp_id], plannedRegime = dp.gt_regime === 'TRUE_DEPARTURE' ? 'FULL_BLIND' : dp.gt_regime;
  let at = null;
  if (kind === 'visible') at = dp.t_plan_s;
  else if (kind === 'blind') { let best = null; for (const g of blind) { const lo = g.start_s, hi = g.end_s - 3; if (hi < lo - 1e-9) continue; const t = Math.min(Math.max(dp.t_plan_s, lo), hi); if (best === null || Math.abs(t - dp.t_plan_s) < Math.abs(best - dp.t_plan_s)) best = t; } at = best; }
  else { const e = events[kind] ?? []; at = e.length ? e.reduce((x, y) => Math.abs(y - dp.t_plan_s) < Math.abs(x - dp.t_plan_s) ? y : x) : null; }
  const reg = at === null ? 'NO_EVENT' : regimeAt(at), dt = at === null ? null : +(at - dp.t_plan_s).toFixed(2);
  return {dp_id: dp.dp_id, type: dp.type, kind, t_plan_s: dp.t_plan_s, realized_t_s: at, delta_s: dt, planned_regime: plannedRegime, spec_regime: dp.gt_regime, observed_regime: reg,
   ok: at !== null && Math.abs(dt) <= TOL && reg === plannedRegime};
 });
 const ticksUsed = dps.map(d => d.realized_t_s === null ? null : Math.round(d.realized_t_s * FPS)); const distinct = new Set(ticksUsed.filter(x => x !== null)).size === ticksUsed.length;
 return {case_id: c.case_id, duration_s: +(rows.at(-1).tick / FPS).toFixed(1), complete: sim.complete, stalls: sim.stalls.length, stall_detail: sim.stalls, spawn_adjusted: sim.spawn_adjusted,
  seed_clean_first_2s: seedClean, visible_first_2s: rows.slice(0, 10).every(r => T(r).present && T(r).vis.length > 0), opening_camera: c.opening_camera, opening_camera_sees_t0: T(rows[0]).vis.includes(c.opening_camera), t_camera_sequence: segs.map(s => `${s.start.toFixed(1)}-${(s.end + 0.2).toFixed(1)}:${s.k}`),
  t_blind_intervals: blind, distractor_first_visible_s: firstAVis, closest_any: closest, closest_co_visible: co, decision_points: dps, events, distinct_ticks: distinct,
  all_ok: dps.every(d => d.ok) && distinct && T(rows[0]).vis.includes(c.opening_camera) && seedClean && rows.slice(0, 10).every(r => T(r).present && T(r).vis.length > 0) && sim.complete && sim.stalls.length === 0};
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
 const [out, assets, ...ids] = process.argv.slice(2);
 if (!out || !assets) throw new Error('usage: e6_design_check.mjs OUT.json ASSETS [CASE_IDS...]');
 const {doc, routes} = loadE6(), env = setup(assets), results = [];
 for (const c of doc.cases) {
  if (ids.length && !ids.includes(c.case_id)) continue;
  const r = summarize(c, simulate(routes[c.case_id], env, c.case_id)); results.push(r);
  if (r.stall_detail.length) console.log('  STALL', JSON.stringify(r.stall_detail));
  console.log(c.case_id, `dur=${r.duration_s}`, r.complete ? 'complete' : 'INCOMPLETE', `stalls=${r.stalls}`, `seedClean=${r.seed_clean_first_2s}`, `dps=${r.all_ok ? 'OK' : 'CHECK'}`);
  console.log('  T cams:', r.t_camera_sequence.join(' | '));
  console.log('  events:', JSON.stringify(r.events));
  console.log('  blind:', r.t_blind_intervals.map(b => `${b.start_s}-${b.end_s}(${b.duration_s}s)`).join(' ') || '-', ' A firstVis:', r.distractor_first_visible_s, ' closest:', JSON.stringify(r.closest_any), ' coVis:', JSON.stringify(r.closest_co_visible));
  for (const d of r.decision_points) console.log(`   ${d.dp_id} ${d.type}[${d.kind}] plan=${d.t_plan_s} real=${d.realized_t_s} d=${d.delta_s} ${d.planned_regime}->${d.observed_regime}${d.ok ? '' : ' !!'}`);
 }
 fs.writeFileSync(out, JSON.stringify({schema: 'amidst.e6-design-check.v1', role: 'DESIGN_CHECK_NOT_GT_INPUT', results}, null, 2) + '\n');
}

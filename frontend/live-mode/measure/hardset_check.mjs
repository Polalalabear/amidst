// #597 offline check of a scripted segment's success conditions from its A log, and (when given) the B log
// (GT, evaluation only). node measure/hardset_check.mjs <a-log.json> [<b-log.json>] ... -> JSON report on stdout.
// Pairs: each A log may be followed by its B log (file name ending .b-log.json).
// Implements the H1 / H4 / H5 / H5c conditions of docs/evaluation/LIVE_HARDSET_V1.md §4 in two readings:
//   strict: every camera counts as seeing the target (CAM_ENTRY included)  -> verdict
//   graph : CAM_ENTRY is removed first, as in graph v3                    -> verdict_graph
// COMMON.pre (B ON_TARGET for the 3 s before the hard point) uses the B log; the classification copies
// scripts/live_ab_score.py classify() (match 1.5 m, TRACKING with lost_ticks 0).
import fs from 'node:fs';

const read = rel => JSON.parse(fs.readFileSync(new URL(rel, import.meta.url)));
const graph = read('../../../configs/q1q5/graphs/r004/camera_graph_v3.json');
const table = read('../../../configs/evaluation/live_hardset_v1.json');
const EDGES = new Set(graph.transitions.map(t => `${t.from_camera_id}>${t.to_camera_id}`));
const RED = ['A', 'B'];
const READINGS = {strict: [], graph: ['CAM_ENTRY']};
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const actor = (tick, id) => tick.actors.find(a => a.id === id);
const cams = (a, ignore = []) => (a && a.present && Array.isArray(a.gt_visible) ? a.gt_visible.filter(c => !ignore.includes(c)) : []);
const visible = (a, ignore = []) => cams(a, ignore).length > 0;

export function gaps(ticks, ignore = []) {
  const out = [];
  let start = null;
  for (let i = 0; i < ticks.length; i++) {
    const t = actor(ticks[i], 'T');
    if (!visible(t, ignore)) { if (start === null && i > 0) start = i; continue; }
    if (start !== null) {
      const before = actor(ticks[start - 1], 'T'), first = ticks[start];
      out.push({start_tick: first.tick, t_last_seen: ticks[start - 1].t_sim, t_start: first.t_sim, t_reappear: ticks[i].t_sim,
        unseen_s: ticks[i].t_sim - first.t_sim, last_xy: before.xy, last_cams: cams(before, ignore), reappear_xy: t.xy,
        reappear_cams: cams(t, ignore), start_index: start, end_index: i});
      start = null;
    }
  }
  return out;
}

// H1.c: seconds visible within windowS after reappearing (short blind gaps between cameras do not reset it).
function visibleAfter(ticks, from, ignore, windowS = 10) {
  const t0 = ticks[from].t_sim;
  let total = 0;
  for (let i = from; i + 1 < ticks.length && ticks[i].t_sim < t0 + windowS; i++)
    if (visible(actor(ticks[i], 'T'), ignore)) total += Math.min(ticks[i + 1].t_sim, t0 + windowS) - ticks[i].t_sim;
  return total;
}

function redNear(ticks, g, windowS = 3, gate = 4) {
  let best = 0;
  for (let i = g.start_index; i < g.end_index && ticks[i].t_sim <= g.t_start + windowS + 1e-9; i++) {
    const n = RED.filter(id => { const a = actor(ticks[i], id); return visible(a) && dist(a.xy, g.last_xy) <= gate; }).length;
    best = Math.max(best, n);
  }
  return best;
}

function skipped(x, z) {
  const xs = x.filter(c => c !== 'CAM_ENTRY'), zs = z.filter(c => c !== 'CAM_ENTRY'); // H4.a: CAM_ENTRY removed first
  if (!xs.length || !zs.length) return false;
  if (xs.some(c => zs.includes(c))) return false;
  return !xs.some(a => zs.some(b => EDGES.has(`${a}>${b}`)));
}

function overlap(ticks) {
  // H4.b (GT only, same for every mode): T is seen by one corner camera, then only by the other for >= 3 s.
  const pair = {CAM_BRANCH: 'CAM_WIDE', CAM_WIDE: 'CAM_BRANCH'};
  let best = 0, run = null, prev = [], at = null;
  for (const tick of ticks) {
    const c = cams(actor(tick, 'T'), ['CAM_ENTRY']);
    const only = c.length === 1 && pair[c[0]] ? c[0] : null;
    if (only && (run?.cam === only || prev.includes(pair[only]))) {
      if (run?.cam !== only) run = {cam: only, t: tick.t_sim};
      if (tick.t_sim - run.t > best) { best = tick.t_sim - run.t; at = run.t; }
    } else run = null;
    prev = c;
  }
  return {s: best, t_start: at};
}

// B side (copy of scripts/live_ab_score.py classify for the target T).
function classify(bRow, aRow) {
  const gt = aRow && actor(aRow, 'T');
  if (!gt) return 'UNKNOWN';
  if (!visible(gt)) return 'TARGET_OUT_OF_VIEW';
  const tr = bRow.tracking;
  if (!tr || typeof tr !== 'object') return 'UNKNOWN';
  if (['IDLE', 'ACQUIRING', 'SEARCHING', 'NEEDS_PICK'].includes(tr.state)) return 'UNKNOWN';
  if (['LOST', 'TARGET_OUT_OF_VIEW'].includes(tr.state) || tr.lost_ticks > 0 || tr.est_xy == null) return 'LOST';
  if (dist(tr.est_xy, gt.xy) <= 1.5) return 'ON_TARGET';
  if (aRow.actors.some(a => a.present && a.id !== 'T' && dist(tr.est_xy, a.xy) <= 1.5)) return 'WRONG_PERSON';
  return 'UNMATCHED';
}

function bSide(aLog, bLog) {
  if (!bLog) return null;
  const aByTick = new Map(aLog.ticks.map(t => [t.tick, t]));
  const rows = bLog.ticks.filter(r => aByTick.has(r.tick)).map(r => ({tick: r.tick, t_sim: aByTick.get(r.tick).t_sim, status: classify(r, aByTick.get(r.tick)),
    events: (r.tracking?.events || []).map(e => e.type + (e.detail?.by ? `:${e.detail.by}` : ''))})).sort((x, y) => x.t_sim - y.t_sim);
  // The B log starts with the first tick B receives after its start op; the ACQUIRE event itself can fall
  // before that, so the lock is also read as "first B tick is TRACKING and ON_TARGET within 3 s".
  const lock = rows.find(r => r.events.includes('ACQUIRE:AUTO_SINGLE')) || null;
  const first = rows[0] || null;
  const firstOn = rows.find(r => r.status === 'ON_TARGET') || null;
  const counts = {};
  for (const r of rows) counts[r.status] = (counts[r.status] || 0) + 1;
  return {session_match: aLog.session_id === bLog.session_id, b_ticks: bLog.ticks.length, joined: rows.length,
    lock_auto_single_t: lock?.t_sim ?? null, first_b_tick: first && {t_sim: first.t_sim, status: first.status},
    locked_on_t: !!first && first.t_sim <= 3 && first.status === 'ON_TARGET', first_on_target_t: firstOn?.t_sim ?? null, counts, actions: (bLog.actions || []).map(a => ({type: a.type, mode: a.mode})), rows};
}

function pre(b, tPoint, windowS = 3) {
  if (!b || tPoint == null) return {status: 'NOT_CHECKED', reason: b ? 'no hard point' : 'needs B log'};
  const win = b.rows.filter(r => r.t_sim >= tPoint - windowS - 1e-9 && r.t_sim < tPoint);
  const on = win.filter(r => r.status === 'ON_TARGET').length;
  return {status: win.length && on === win.length ? 'PASS' : 'FAIL', t_point: tPoint, window_ticks: win.length, on_target: on,
    statuses: win.map(r => r.status)};
}

function family(meta, ticks, ignore, b) {
  const all = gaps(ticks, ignore), c = {}, r = {conditions: c};
  r.gaps = all.map(({start_index, end_index, ...g}) => ({...g, jump_m: +dist(g.last_xy, g.reappear_xy).toFixed(2)}));
  if (meta.family === 'H1') {
    const g = all.filter(g => g.unseen_s >= 15).sort((x, y) => y.unseen_s - x.unseen_s)[0]
      || all.sort((x, y) => y.unseen_s - x.unseen_s)[0];
    c['H1.a unseen >= 15 s'] = !!g && g.unseen_s >= 15;
    c['H1.b jump >= 8 m'] = !!g && dist(g.last_xy, g.reappear_xy) >= 8;
    r.h1_visible_after_s = g ? +visibleAfter(ticks, g.end_index, ignore).toFixed(2) : null;
    c['H1.c visible >= 5 s within 10 s after'] = !!g && r.h1_visible_after_s >= 5;
    r.hard_point_t = g?.t_start ?? null;
    r.verdict = c['H1.a unseen >= 15 s'] && c['H1.c visible >= 5 s within 10 s after'] ? (c['H1.b jump >= 8 m'] ? 'H1' : 'H1n') : 'NOT_PRODUCED';
  } else if (meta.family === 'H5' || meta.family === 'H5c') {
    const want = meta.family === 'H5' ? n => n >= 2 : n => n === 1;
    const hits = all.filter(g => g.unseen_s >= 3).map(g => ({t_start: g.t_start, red_near: redNear(ticks, g)}));
    r.h5_gaps = hits;
    c[`${meta.family}.a unseen >= 3 s`] = hits.length > 0;
    c[`${meta.family}.b red within 4 m (${meta.family === 'H5' ? '>= 2' : '== 1'})`] = hits.some(h => want(h.red_near));
    r.hard_point_t = (hits.find(h => want(h.red_near)) || hits[0])?.t_start ?? null;
    r.verdict = Object.values(c).every(Boolean) ? meta.family : 'NOT_PRODUCED';
  } else if (meta.family === 'H4') {
    const skips = all.filter(g => g.unseen_s >= 1 && skipped(g.last_cams, g.reappear_cams))
      .map(g => ({t_start: g.t_start, unseen_s: +g.unseen_s.toFixed(2), from: g.last_cams, to: g.reappear_cams}));
    const ov = overlap(ticks);
    r.h4_skips = skips;
    r.h4_overlap_s = ov.s;
    c['H4.a skip with gap >= 1 s'] = skips.length > 0;
    c['H4.b overlap >= 3 s'] = ov.s >= 3;
    r.hard_point_t = skips[0]?.t_start ?? (ov.s >= 3 ? ov.t_start : null);
    r.verdict = c['H4.a skip with gap >= 1 s'] || c['H4.b overlap >= 3 s'] ? 'H4' : 'NOT_PRODUCED';
  } else r.verdict = 'NOT_APPLICABLE';
  r.common_pre = pre(b, r.hard_point_t);
  return r;
}

export function check(log, bLog = null) {
  const caseId = log.config?.script?.case_id ?? log.smoke?.case_id;
  const meta = table.cases.find(c => c.case_id === caseId);
  if (!meta) throw new Error(`unknown case ${caseId}`);
  const ticks = [...log.ticks].sort((a, b) => a.t_sim - b.t_sim);
  const b = bSide(log, bLog);
  const out = {case_id: caseId, family: meta.family, ticks: ticks.length,
    pause_player_max_s: Math.max(0, ...ticks.flatMap(t => Object.values(t.pause_player_i || {}))),
    forced_overlap: (log.forced_overlap || []).length, script_stalls: (log.script_events || []).filter(e => e.type === 'script_stall').length};
  for (const [name, ignore] of Object.entries(READINGS)) out[name] = family(meta, ticks, ignore, b);
  out.verdict = out.strict.verdict;
  out.verdict_graph = out.graph.verdict;
  if (b) { const {rows, ...rest} = b; out.b = rest; }
  return out;
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  const files = process.argv.slice(2), reports = [];
  for (let i = 0; i < files.length; i++) {
    const a = JSON.parse(fs.readFileSync(files[i]));
    const next = files[i + 1]?.endsWith('.b-log.json') ? JSON.parse(fs.readFileSync(files[++i])) : null;
    reports.push(check(a, next));
  }
  console.log(JSON.stringify(reports, null, 1));
}

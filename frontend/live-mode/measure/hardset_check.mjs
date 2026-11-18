// #597 offline check of a scripted segment's success conditions from its A log (GT, evaluation only).
// node measure/hardset_check.mjs <a-log.json>...  -> JSON report on stdout.
// Implements the H1 / H4 / H5 / H5c conditions of docs/evaluation/LIVE_HARDSET_V1.md §4. COMMON.pre (ON_TARGET
// before the hard point) needs the B log and is reported as NOT_CHECKED here.
import fs from 'node:fs';

const read = rel => JSON.parse(fs.readFileSync(new URL(rel, import.meta.url)));
const graph = read('../../../configs/q1q5/graphs/r004/camera_graph_v3.json');
const table = read('../../../configs/evaluation/live_hardset_v1.json');
const EDGES = new Set(graph.transitions.map(t => `${t.from_camera_id}>${t.to_camera_id}`));
const RED = ['A', 'B'];
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const actor = (tick, id) => tick.actors.find(a => a.id === id);
const visible = a => !!a && a.present && Array.isArray(a.gt_visible) && a.gt_visible.length > 0;

export function gaps(ticks) {
  const out = [];
  let start = null;
  for (let i = 0; i < ticks.length; i++) {
    const t = actor(ticks[i], 'T');
    if (!visible(t)) { if (start === null && i > 0) start = i; continue; }
    if (start !== null) {
      const before = actor(ticks[start - 1], 'T'), first = ticks[start];
      out.push({start_tick: first.tick, t_start: first.t_sim, t_reappear: ticks[i].t_sim, unseen_s: ticks[i].t_sim - first.t_sim,
        last_xy: before.xy, last_cams: before.gt_visible, reappear_xy: t.xy, reappear_cams: t.gt_visible, start_index: start, end_index: i});
      start = null;
    }
  }
  return out;
}

// H1.c: seconds the target is visible within windowS after reappearing (sum of visible tick intervals; short
// blind gaps between cameras do not reset it).
function visibleAfter(ticks, from, windowS = 10) {
  const t0 = ticks[from].t_sim;
  let total = 0;
  for (let i = from; i + 1 < ticks.length && ticks[i].t_sim < t0 + windowS; i++)
    if (visible(actor(ticks[i], 'T'))) total += Math.min(ticks[i + 1].t_sim, t0 + windowS) - ticks[i].t_sim;
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
  const xs = x.filter(c => c !== 'CAM_ENTRY'), zs = z.filter(c => c !== 'CAM_ENTRY');
  if (!xs.length || !zs.length) return false;
  if (xs.some(c => zs.includes(c))) return false;
  return !xs.some(a => zs.some(b => EDGES.has(`${a}>${b}`)));
}

function overlap(ticks) {
  // H4.b (GT only, same for every mode): T is seen by one corner camera, then only by the other for >= 3 s.
  const pair = {CAM_BRANCH: 'CAM_WIDE', CAM_WIDE: 'CAM_BRANCH'};
  let best = 0, run = null, prev = [];
  for (const tick of ticks) {
    const t = actor(tick, 'T'), cams = visible(t) ? t.gt_visible.filter(c => c !== 'CAM_ENTRY') : [];
    const only = cams.length === 1 && pair[cams[0]] ? cams[0] : null;
    if (only && (run?.cam === only || prev.includes(pair[only]))) {
      if (run?.cam !== only) run = {cam: only, t: tick.t_sim};
      best = Math.max(best, tick.t_sim - run.t);
    } else run = null;
    prev = cams;
  }
  return best;
}

export function check(log) {
  const caseId = log.config?.script?.case_id ?? log.smoke?.case_id;
  const meta = table.cases.find(c => c.case_id === caseId);
  if (!meta) throw new Error(`unknown case ${caseId}`);
  const ticks = [...log.ticks].sort((a, b) => a.t_sim - b.t_sim);
  const all = gaps(ticks), r = {case_id: caseId, family: meta.family, ticks: ticks.length,
    pause_player_max_s: Math.max(0, ...ticks.flatMap(t => Object.values(t.pause_player_i || {}))),
    forced_overlap: (log.forced_overlap || []).length, script_stalls: (log.script_events || []).filter(e => e.type === 'script_stall').length,
    gaps: all.map(({start_index, end_index, ...g}) => ({...g, jump_m: dist(g.last_xy, g.reappear_xy)})), conditions: {}, common_pre: 'NOT_CHECKED (needs B log)'};
  const c = r.conditions;
  if (meta.family === 'H1') {
    const g = all.filter(g => g.unseen_s >= 15).sort((a, b) => b.unseen_s - a.unseen_s)[0];
    c['H1.a unseen >= 15 s'] = !!g;
    c['H1.b jump >= 8 m'] = !!g && dist(g.last_xy, g.reappear_xy) >= 8;
    r.h1_visible_after_s = g ? visibleAfter(ticks, g.end_index) : null;
    c['H1.c visible >= 5 s within 10 s after'] = !!g && r.h1_visible_after_s >= 5;
    r.verdict = c['H1.a unseen >= 15 s'] && c['H1.c visible >= 5 s within 10 s after'] ? (c['H1.b jump >= 8 m'] ? 'H1' : 'H1n') : 'NOT_PRODUCED';
  } else if (meta.family === 'H5' || meta.family === 'H5c') {
    const want = meta.family === 'H5' ? n => n >= 2 : n => n === 1;
    const hits = all.filter(g => g.unseen_s >= 3).map(g => ({t_start: g.t_start, red_near: redNear(ticks, g)}));
    r.h5_gaps = hits;
    c[`${meta.family}.a unseen >= 3 s`] = hits.length > 0;
    c[`${meta.family}.b red within 4 m (${meta.family === 'H5' ? '>= 2' : '== 1'})`] = hits.some(h => want(h.red_near));
    r.verdict = Object.values(c).every(Boolean) ? meta.family : 'NOT_PRODUCED';
  } else if (meta.family === 'H4') {
    const skips = all.filter(g => g.unseen_s >= 1 && skipped(g.last_cams, g.reappear_cams)).map(g => ({t_start: g.t_start, from: g.last_cams, to: g.reappear_cams}));
    r.h4_skips = skips;
    r.h4_overlap_s = overlap(ticks);
    c['H4.a skip with gap >= 1 s'] = skips.length > 0;
    c['H4.b overlap >= 3 s'] = r.h4_overlap_s >= 3;
    r.verdict = c['H4.a skip with gap >= 1 s'] || c['H4.b overlap >= 3 s'] ? 'H4' : 'NOT_PRODUCED';
  } else r.verdict = 'NOT_APPLICABLE';
  return r;
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  const reports = process.argv.slice(2).map(f => check(JSON.parse(fs.readFileSync(f))));
  console.log(JSON.stringify(reports, null, 1));
}

// T1 analysis (docs/design/LIVE_MODE_LLM_DECISION_V1.md §4). node measure/t1_analyze.mjs <dir with *.t1raw.json> <scenario.json>
// Two kinds of numbers, kept apart:
//  - pixel-only: what the backend itself could know (red detections, their ground points, tracker state);
//  - evaluation-only: uses the scripted actor positions (ground truth) to say who the tracker is following.
import fs from 'node:fs';
import path from 'node:path';
import { scriptedPose } from '../src/sim.mjs';
import { pct } from './lib.mjs';

const [dir, scenarioPath] = process.argv.slice(2);
const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));
const GATE = 3.0, SAME = 1.5; // tracker gate_m and its same-person radius (src/amidst/live_mode/tracker.py)
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

function clusters(points) { // single-link clustering of ground points at SAME metres
  const cl = [];
  for (const p of points) {
    const hit = cl.filter((c) => c.some((q) => dist(p, q) < SAME));
    if (!hit.length) cl.push([p]);
    else { hit[0].push(p); for (const h of hit.slice(1)) { hit[0].push(...h); cl.splice(cl.indexOf(h), 1); } }
  }
  return cl.map((c) => [c.reduce((s, p) => s + p[0], 0) / c.length, c.reduce((s, p) => s + p[1], 0) / c.length]);
}
function episodes(flags) { // [start, endExclusive] runs of true
  const out = []; let s = -1;
  flags.forEach((f, i) => { if (f && s < 0) s = i; if (!f && s >= 0) { out.push([s, i]); s = -1; } });
  if (s >= 0) out.push([s, flags.length]);
  return out;
}

function analyze(raw) {
  const run = scenario.runs.find((r) => r.run_id === raw.cfg.run);
  const dur = run.duration_us / 1e6;
  const n = Math.min(raw.ticks.length, raw.infer.length);
  const T = run.actors.find((a) => a.actor_id === 'T');
  // clock offset between the page's scenario clock and fpsStart: fit to the recorded target position
  let best = [1e9, 0];
  for (let d = -0.5; d <= 1.5; d += 0.02) {
    let e = 0, k = 0;
    for (let i = 0; i < n; i++) {
      const p = scriptedPose(T, (raw.ticks[i].t_capture - raw.t0) / 1000 + d, dur);
      if (p && raw.infer[i].gt_xy) { e += dist([p.x, p.y], raw.infer[i].gt_xy); k++; }
    }
    if (k && e / k < best[0]) best = [e / k, d];
  }
  const rows = [];
  let prevEst = null;
  for (let i = 0; i < n; i++) {
    const tk = raw.ticks[i], inf = raw.infer[i], tr = inf.tracking;
    const tSec = (tk.t_capture - raw.t0) / 1000 + best[1];
    const actors = Object.fromEntries(run.actors.map((a) => { const p = scriptedPose(a, tSec, dur); return [a.actor_id, p ? [p.x, p.y] : null]; }));
    const reds = [];
    for (const [cam, list] of Object.entries(inf.dets)) for (const d of list) if (d.color === 'red' && d.est_xy) reds.push({ cam, xy: d.est_xy, score: d.score });
    const cl = clusters(reds.map((r) => r.xy));
    const nearPrev = prevEst ? cl.filter((c) => dist(c, prevEst) <= GATE) : [];
    const who = (xy) => { // evaluation only
      let b = null;
      for (const [id, p] of Object.entries(actors)) if (p && (!b || dist(p, xy) < b[1])) b = [id, dist(p, xy)];
      return b && b[1] <= SAME ? b[0] : null;
    };
    const tVisible = tk.gt_visible.filter((c) => raw.cfg.cams.includes(c));
    const matched = tr.state === 'TRACKING' && tr.lost_ticks === 0;
    const following = matched && tr.est_xy ? who(tr.est_xy) : null;
    const status = !actors.T ? 'TARGET_ABSENT' : !tVisible.length ? 'TARGET_NOT_VISIBLE'
      : !matched ? 'LOST' : following === 'T' ? 'ON_TARGET' : 'WRONG_PERSON';
    rows.push({ i, tSec, t_capture: tk.t_capture, t_resp: inf.t_resp, rt_ms: inf.t_resp - inf.t_call, state: tr.state, lost: tr.lost_ticks, active: tr.active_cam,
      events: tr.events.map((e) => e.type), n_red_clusters: cl.length, n_near_prev: nearPrev.length, matched, following, status,
      red_actors: [...new Set(reds.map((r) => who(r.xy)).filter(Boolean))].sort(), tVisible });
    prevEst = tr.est_xy || prevEst;
  }
  const secs = (rows.at(-1).t_resp - rows[0].t_capture) / 1000;
  const vis = rows.filter((r) => ['ON_TARGET', 'WRONG_PERSON', 'LOST'].includes(r.status));
  const share = (s) => (vis.length ? vis.filter((r) => r.status === s).length / vis.length : null);
  const epi = (pred) => episodes(rows.map(pred)).map(([s, e]) => ({ start_s: +rows[s].tSec.toFixed(2), ticks: e - s, censored: e === rows.length,
    seconds: +(((e < rows.length ? rows[e].t_resp : rows.at(-1).t_resp) - rows[s].t_capture) / 1000).toFixed(2),
    ended_on: e < rows.length ? rows[e].status : null, started_ambiguous: rows[s].n_near_prev >= 2,
    start_target_detected: rows[s].red_actors.includes('T'), start_red_people: rows[s].n_red_clusters }));
  // pixel-only decision moments the backend could detect by itself
  const silentPick = rows.map((r) => r.matched && r.n_near_prev >= 2);                 // rule silently takes the nearest of >=2 red people
  const lostWithCand = rows.map((r) => !r.matched && r.state !== 'SEARCHING' && r.n_red_clusters >= 1); // lost while red people are in view
  const lostWithMany = rows.map((r) => !r.matched && r.state !== 'SEARCHING' && r.n_red_clusters >= 2);
  const seedBlocked = rows.map((r) => r.state === 'SEARCHING' && r.n_red_clusters >= 2);
  const perMin = (flags) => +(episodes(flags).length / (secs / 60)).toFixed(2);
  return {
    label: raw.label, run: raw.cfg.run, cams: raw.cfg.cams.length, fps_set: raw.cfg.fps, seconds: +secs.toFixed(1), ticks: rows.length, dropped: raw.dropped,
    achieved_hz: +((rows.length - 1) / secs).toFixed(2), roundtrip_ms_p50: Math.round(pct(rows.map((r) => r.rt_ms), 0.5)), load1_end: raw.load1_end,
    clock_fit: { offset_s: +best[1].toFixed(2), mean_err_m: +best[0].toFixed(3) },
    pixel_only: {
      ticks_with_2plus_red_people: +(rows.filter((r) => r.n_red_clusters >= 2).length / rows.length).toFixed(3),
      silent_pick_episodes_per_min: perMin(silentPick), silent_pick_ticks: silentPick.filter(Boolean).length,
      lost_with_candidate_episodes_per_min: perMin(lostWithCand), lost_with_2plus_candidates_episodes_per_min: perMin(lostWithMany),
      seed_blocked_ticks: seedBlocked.filter(Boolean).length,
      lost_episodes: epi((r) => r.state !== 'SEARCHING' && !r.matched),
    },
    evaluation_only: {
      target_visible_ticks: vis.length, on_target: share('ON_TARGET'), wrong_person: share('WRONG_PERSON'), lost: share('LOST'),
      wrong_person_episodes: epi((r) => r.status === 'WRONG_PERSON'),
      not_on_target_episodes: epi((r) => r.status === 'WRONG_PERSON' || r.status === 'LOST'),
      first_tick_following: rows.find((r) => r.matched)?.following ?? null,
      followed_actor_ticks: Object.fromEntries(['T', 'A', 'B', 'C', 'null'].map((k) => [k, rows.filter((r) => r.matched && String(r.following) === k).length])),
    },
    rows,
  };
}

const files = fs.readdirSync(dir).filter((f) => f.endsWith('.t1raw.json')).sort();
const all = files.map((f) => analyze(JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'))));
const groups = {};
for (const a of all) (groups[a.label.replace(/_r\d+$/, '')] ||= []).push(a);
const summary = Object.entries(groups).map(([g, runs]) => {
  const cat = (f) => runs.flatMap(f);
  const mean = (f) => +(runs.reduce((s, r) => s + f(r), 0) / runs.length).toFixed(3);
  const notOn = cat((r) => r.evaluation_only.not_on_target_episodes), lost = cat((r) => r.pixel_only.lost_episodes), wrong = cat((r) => r.evaluation_only.wrong_person_episodes);
  const secsOf = (e) => e.map((x) => x.seconds);
  return { group: g, runs: runs.length, achieved_hz: mean((r) => r.achieved_hz), roundtrip_ms_p50: mean((r) => r.roundtrip_ms_p50),
    on_target: mean((r) => r.evaluation_only.on_target), wrong_person: mean((r) => r.evaluation_only.wrong_person), lost: mean((r) => r.evaluation_only.lost),
    ticks_with_2plus_red_people: mean((r) => r.pixel_only.ticks_with_2plus_red_people),
    silent_pick_episodes_per_min: mean((r) => r.pixel_only.silent_pick_episodes_per_min),
    lost_with_candidate_episodes_per_min: mean((r) => r.pixel_only.lost_with_candidate_episodes_per_min),
    lost_with_2plus_candidates_episodes_per_min: mean((r) => r.pixel_only.lost_with_2plus_candidates_episodes_per_min),
    lost_episodes: { n: lost.length, censored: lost.filter((x) => x.censored).length, started_with_target_detected: lost.filter((x) => x.start_target_detected).length, seconds_p50: pct(secsOf(lost), 0.5), seconds_max: Math.max(0, ...secsOf(lost)) },
    wrong_person_episodes: { n: wrong.length, started_ambiguous: wrong.filter((x) => x.started_ambiguous).length, started_target_not_detected: wrong.filter((x) => !x.start_target_detected).length, seconds_p50: pct(secsOf(wrong), 0.5), seconds_max: Math.max(0, ...secsOf(wrong)) },
    not_on_target_episodes: { n: notOn.length, censored: notOn.filter((x) => x.censored).length, seconds_p50: pct(secsOf(notOn), 0.5), seconds_max: Math.max(0, ...secsOf(notOn)),
      recovered_on_target: notOn.filter((x) => x.ended_on === 'ON_TARGET').length },
    load1_end: runs.map((r) => r.load1_end) };
});
fs.writeFileSync(path.join(dir, 't1_summary.json'), JSON.stringify({ gate_m: GATE, same_person_m: SAME, groups: summary,
  runs: all.map(({ rows, ...r }) => r) }, null, 1));
fs.writeFileSync(path.join(dir, 't1_rows.json'), JSON.stringify(all.map((a) => ({ label: a.label, rows: a.rows }))));
for (const s of summary) console.log(JSON.stringify(s));

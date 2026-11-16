// Evaluation of each adjudication question in advisor runs (t1_record.mjs output with --advisor review|lead).
// node measure/adv_analyze.mjs <dir with *.t1raw.json> <scenario.json>
// Rebuilds the candidate list of every ADJUDICATE_ASK from the recorded detections (same grouping and left-to-right
// order as src/amidst/live_mode/advisor.py), then uses the scripted actor positions (evaluation only) to say whether
// the target was among the candidates and who the model picked.
import fs from 'node:fs';
import path from 'node:path';
import { scriptedPose } from '../src/sim.mjs';

const [dir, scenarioPath] = process.argv.slice(2);
const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));
const SAME = 1.5, GATE = 3.0, MAXC = 4;
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const out = [];
for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.t1raw.json')).sort()) {
  const raw = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  const run = scenario.runs.find((r) => r.run_id === raw.cfg.run), dur = run.duration_us / 1e6, T = run.actors.find((a) => a.actor_id === 'T');
  const n = Math.min(raw.ticks.length, raw.infer.length);
  let best = [1e9, 0];
  for (let d = -0.5; d <= 1.5; d += 0.02) {
    let e = 0, k = 0;
    for (let i = 0; i < n; i++) { const p = scriptedPose(T, (raw.ticks[i].t_capture - raw.t0) / 1000 + d, dur); if (p && raw.infer[i].gt_xy) { e += dist([p.x, p.y], raw.infer[i].gt_xy); k++; } }
    if (k && e / k < best[0]) best = [e / k, d];
  }
  const who = (i, xy) => {
    const t = (raw.ticks[i].t_capture - raw.t0) / 1000 + best[1]; let b = null;
    for (const a of run.actors) { const p = scriptedPose(a, t, dur); if (p && (!b || dist([p.x, p.y], xy) < b[1])) b = [a.actor_id, dist([p.x, p.y], xy)]; }
    return b && b[1] <= SAME ? b[0] : null;
  };
  let open = null, prevEst = null;
  for (let i = 0; i < n; i++) {
    const tr = raw.infer[i].tracking;
    for (const e of tr.events) {
      if (e.type === 'ADJUDICATE_ASK') {
        const cands = [];
        for (const [cam, list] of Object.entries(raw.infer[i].dets)) for (const d of list) if (d.color === 'red' && d.est_xy) cands.push({ cam, d });
        const people = [];
        for (const c of cands.sort((a, b) => b.d.score - a.d.score)) {
          const hit = people.find((p) => dist(p.xy, c.d.est_xy) < SAME);
          if (!hit) people.push({ xy: c.d.est_xy, dets: [c] }); else if (!hit.dets.some((x) => x.cam === c.cam)) hit.dets.push(c);
        }
        let pool = people;
        if (e.detail.kind === 'SILENT_PICK' && prevEst) pool = people.filter((p) => dist(p.xy, prevEst) <= GATE);
        const inCam = pool.map((p) => ({ p, det: p.dets.find((x) => x.cam === e.cam) })).filter((x) => x.det)
          .sort((a, b) => (a.det.d.bbox[0] + a.det.d.bbox[2]) - (b.det.d.bbox[0] + b.det.d.bbox[2])).slice(0, MAXC);
        open = { run: raw.label, tick: i, kind: e.detail.kind, cam: e.cam, n_candidates: e.detail.candidates, rebuilt: inCam.length,
          actors: inCam.map((x) => who(i, x.p.xy)), target_visible_in_cam: raw.ticks[i].gt_visible.includes(e.cam) };
        open.target_among_candidates = open.actors.includes('T');
      }
      if (e.type === 'ADJUDICATED' && open) {
        const c = e.detail.choice;
        out.push({ ...open, source: e.detail.source, applied: e.detail.applied, choice: c, latency_ms: e.detail.latency_ms,
          picked: c ? open.actors[c - 1] ?? 'UNKNOWN' : c === 0 ? 'NONE' : null,
          correct: e.detail.source !== 'AGENT' ? null : c === 0 ? !open.target_among_candidates : open.actors[c - 1] === 'T' });
        open = null;
      }
    }
    if (tr.est_xy && tr.state !== 'ADJUDICATING') prevEst = tr.est_xy;
  }
}
fs.writeFileSync(path.join(dir, 'adv_questions.json'), JSON.stringify(out, null, 1));
const ans = out.filter((q) => q.source === 'AGENT');
const tab = (rows) => ({ n: rows.length, correct: rows.filter((q) => q.correct).length });
console.log(JSON.stringify({ questions: out.length, answered: ans.length, rebuilt_mismatch: out.filter((q) => q.rebuilt !== q.n_candidates).length,
  by_candidates: Object.fromEntries([1, 2, 3, 4].map((k) => [k, tab(ans.filter((q) => q.n_candidates === k))])),
  target_among: tab(ans.filter((q) => q.target_among_candidates)), target_absent: tab(ans.filter((q) => !q.target_among_candidates)),
  absent_answers: ans.filter((q) => !q.target_among_candidates).reduce((m, q) => ({ ...m, [q.picked]: (m[q.picked] || 0) + 1 }), {}),
  among_answers: ans.filter((q) => q.target_among_candidates).reduce((m, q) => ({ ...m, [q.picked]: (m[q.picked] || 0) + 1 }), {}),
  by_kind: Object.fromEntries(['SILENT_PICK', 'LOST_WITH_CANDIDATES'].map((k) => [k, tab(ans.filter((q) => q.kind === k))])) }));
for (const q of ans) console.log(q.run, q.tick, q.kind, q.cam, 'n', q.n_candidates, 'actors', JSON.stringify(q.actors), 'choice', q.choice, 'picked', q.picked, q.correct ? 'OK' : 'WRONG', q.applied ? '' : 'not applied');

// Build adjudication questions from adj_record.mjs output. node measure/adj_build.mjs <record dir> <scenario.json> <out dir>
// Output (out dir):
//   questions.jsonl        what a model may see: numbered candidates in one camera frame, a reference crop of the
//                          target taken at first lock, and pixel-derived features. No actor ids, no scripted positions.
//   answers_private.jsonl  evaluation only: which number is the scripted target (0 = not among the candidates).
//   img/<qid>_frame.jpg, img/<qid>_ref.jpg
// A question is a tick where one camera shows >= 2 distinct red people and the rule tracker either silently picks the
// nearest of >= 2 people inside its gate, or is lost. At most one question per run and camera every 2 s.
import fs from 'node:fs';
import path from 'node:path';
import { scriptedPose } from '../src/sim.mjs';
import { launch } from './lib.mjs';

const [dir, scenarioPath, outDir] = process.argv.slice(2);
const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));
fs.mkdirSync(path.join(outDir, 'img'), { recursive: true });
const GATE = 3.0, SAME = 1.5, MIN_GAP_S = 2.0, K = 3; // K: 320 -> 960
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const b64 = (f) => fs.readFileSync(f).toString('base64');

const questions = [], answers = [], skipped = [];
const browser = await launch();
try {
const page = await browser.newPage();
await page.goto('about:blank');
await page.evaluate(() => {
  window.load = (b) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = 'data:image/jpeg;base64,' + b; });
  window.hsv = (r, g, b) => { // mean RGB (0-255) -> h deg, s, v
    r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn; let h = 0;
    if (d > 1e-6) h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return { h_deg: Math.round(((h * 60) + 360) % 360), s: +(mx ? d / mx : 0).toFixed(2), v: +mx.toFixed(2) };
  };
  window.region = (ctx, x0, y0, x1, y1) => { // mean colour of the central 60% width of a box part
    const w = x1 - x0, cx0 = Math.round(x0 + w * 0.2), cw = Math.max(1, Math.round(w * 0.6)), ch = Math.max(1, Math.round(y1 - y0));
    const d = ctx.getImageData(Math.max(0, cx0), Math.max(0, Math.round(y0)), cw, ch).data; let r = 0, g = 0, b = 0, n = d.length / 4;
    for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; }
    return window.hsv(r / n, g / n, b / n);
  };
  window.parts = (ctx, [x0, y0, x1, y1]) => { const h = y1 - y0; return { upper: window.region(ctx, x0, y0 + h * 0.18, x1, y0 + h * 0.5), lower: window.region(ctx, x0, y0 + h * 0.55, x1, y0 + h * 0.92) }; };
  window.compose = async (frameB64, boxes) => {
    const img = await window.load(frameB64); const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
    const ctx = c.getContext('2d', { willReadFrequently: true }); ctx.drawImage(img, 0, 0);
    const feats = boxes.map((b) => window.parts(ctx, b));
    boxes.forEach((b, i) => {
      ctx.lineWidth = 3; ctx.strokeStyle = '#ffe600'; ctx.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]);
      const lx = Math.max(0, b[0]), ly = Math.max(26, b[1]);
      ctx.fillStyle = '#000'; ctx.fillRect(lx, ly - 26, 26, 26); ctx.fillStyle = '#ffe600'; ctx.font = 'bold 22px sans-serif'; ctx.fillText(String(i + 1), lx + 7, ly - 6);
    });
    return { jpeg: c.toDataURL('image/jpeg', 0.9).split(',')[1], feats };
  };
  window.crop = async (frameB64, b) => {
    const img = await window.load(frameB64); const w = b[2] - b[0], h = b[3] - b[1], p = 0.15;
    const x0 = Math.max(0, b[0] - w * p), y0 = Math.max(0, b[1] - h * p), x1 = Math.min(img.width, b[2] + w * p), y1 = Math.min(img.height, b[3] + h * p);
    const full = document.createElement('canvas'); full.width = img.width; full.height = img.height; const fctx = full.getContext('2d', { willReadFrequently: true }); fctx.drawImage(img, 0, 0);
    const feat = window.parts(fctx, b);
    const s = Math.max(1, Math.min(4, 300 / (y1 - y0))); const c = document.createElement('canvas'); c.width = Math.round((x1 - x0) * s); c.height = Math.round((y1 - y0) * s);
    c.getContext('2d').drawImage(img, x0, y0, x1 - x0, y1 - y0, 0, 0, c.width, c.height);
    return { jpeg: c.toDataURL('image/jpeg', 0.9).split(',')[1], feat, height_px: Math.round(h) };
  };
});


for (const label of fs.readdirSync(dir).filter((d) => fs.existsSync(path.join(dir, d, 'raw.json'))).sort()) {
  const raw = JSON.parse(fs.readFileSync(path.join(dir, label, 'raw.json'), 'utf8'));
  const run = scenario.runs.find((r) => r.run_id === raw.cfg.run), dur = run.duration_us / 1e6, T = run.actors.find((a) => a.actor_id === 'T');
  const n = Math.min(raw.ticks.length, raw.rows.length);
  const rows = [...raw.rows].sort((a, b) => a.idx - b.idx).slice(0, n);
  let best = [1e9, 0];
  for (let d = -0.5; d <= 1.5; d += 0.02) {
    let e = 0, k = 0;
    for (let i = 0; i < n; i++) { const p = scriptedPose(T, (raw.ticks[i].t_capture - raw.t0) / 1000 + d, dur); if (p && rows[i].gt_xy) { e += dist([p.x, p.y], rows[i].gt_xy); k++; } }
    if (k && e / k < best[0]) best = [e / k, d];
  }
  const has = new Set(raw.frames.map((f) => `${f.idx}_${f.cam}`));
  const file = (idx, cam) => path.join(dir, label, `${String(idx).padStart(3, '0')}_${cam}.jpg`);
  const actorsAt = (i) => { const t = (raw.ticks[i].t_capture - raw.t0) / 1000 + best[1]; return Object.fromEntries(run.actors.map((a) => { const p = scriptedPose(a, t, dur); return [a.actor_id, p ? [p.x, p.y] : null]; })); };
  const who = (actors, xy) => { let b = null; for (const [id, p] of Object.entries(actors)) if (p && (!b || dist(p, xy) < b[1])) b = [id, dist(p, xy)]; return b && b[1] <= SAME ? b[0] : null; }; // evaluation only
  // reference: the detection the tracker locked on first
  const li = rows.findIndex((r) => (r.tracking.events || []).some((e) => e.type === 'ACQUIRE'));
  if (li < 0) { skipped.push({ label, why: 'no lock' }); continue; }
  const lr = rows[li], lcam = lr.tracking.active_cam;
  const ldet = (lr.dets[lcam] || []).filter((d) => d.color === 'red' && d.est_xy).sort((a, b) => dist(a.est_xy, lr.tracking.est_xy) - dist(b.est_xy, lr.tracking.est_xy))[0];
  if (!ldet || !has.has(`${lr.idx}_${lcam}`)) { skipped.push({ label, why: 'no reference frame' }); continue; }
  const refIsTarget = who(actorsAt(li), ldet.est_xy) === 'T';
  if (!refIsTarget) { skipped.push({ label, why: 'first lock was not on the scripted target (evaluation only)' }); continue; }
  const ref = await page.evaluate((f, b) => window.crop(f, b), b64(file(lr.idx, lcam)), ldet.bbox.map((v) => v * K));
  let prevEst = null, lastMatchT = null; const lastQ = {};
  for (let i = 0; i < n; i++) {
    const r = rows[i], tr = r.tracking, matched = tr.state === 'TRACKING' && tr.lost_ticks === 0, tNow = raw.ticks[i].t_capture / 1000;
    if (i > li && prevEst) {
      for (const [cam, list] of Object.entries(r.dets)) {
        if (!has.has(`${r.idx}_${cam}`)) continue;
        const people = [];
        for (const d of list.filter((x) => x.color === 'red' && x.est_xy).sort((a, b) => b.score - a.score)) if (!people.some((p) => dist(p.est_xy, d.est_xy) < SAME)) people.push(d);
        if (people.length < 2 || people.length > 4) continue;
        const near = people.filter((p) => dist(p.est_xy, prevEst) <= GATE).length;
        const kind = matched && near >= 2 ? 'SILENT_PICK' : !matched ? 'LOST_WITH_CANDIDATES' : null;
        if (!kind || (lastQ[cam] != null && tNow - lastQ[cam] < MIN_GAP_S)) continue;
        lastQ[cam] = tNow;
        people.sort((a, b) => (a.bbox[0] + a.bbox[2]) - (b.bbox[0] + b.bbox[2])); // left to right
        const boxes = people.map((p) => p.bbox.map((v) => v * K));
        const comp = await page.evaluate((f, bx) => window.compose(f, bx), b64(file(r.idx, cam)), boxes);
        const qid = `${label}_${String(r.idx).padStart(3, '0')}_${cam}`;
        fs.writeFileSync(path.join(outDir, 'img', `${qid}_frame.jpg`), Buffer.from(comp.jpeg, 'base64'));
        fs.writeFileSync(path.join(outDir, 'img', `${qid}_ref.jpg`), Buffer.from(ref.jpeg, 'base64'));
        const since = lastMatchT == null ? null : +(tNow - lastMatchT).toFixed(2);
        questions.push({ qid, kind, camera: cam, n_candidates: people.length, frame: `img/${qid}_frame.jpg`, reference: `img/${qid}_ref.jpg`,
          reference_features: { upper: ref.feat.upper, lower: ref.feat.lower, box_height_px: ref.height_px, camera: lcam },
          seconds_since_last_match: since,
          candidates: people.map((p, j) => { const dd = dist(p.est_xy, prevEst); return { number: j + 1, box_height_px: Math.round((p.bbox[3] - p.bbox[1]) * K), detector_score: +p.score.toFixed(2),
            upper: comp.feats[j].upper, lower: comp.feats[j].lower, metres_from_last_estimate: +dd.toFixed(1), speed_needed_m_s: since ? +(dd / Math.max(since, 0.3)).toFixed(1) : null }; }) });
        const actors = actorsAt(i), labels = people.map((p) => who(actors, p.est_xy));
        answers.push({ qid, answer: labels.indexOf('T') + 1, candidate_actors: labels, rule_matched: matched,
          rule_pick: matched ? people.map((p) => dist(p.est_xy, tr.est_xy)).reduce((bi, v, j, a) => (v < a[bi] ? j : bi), 0) + 1 : 0 });
      }
    }
    if (tr.est_xy) prevEst = tr.est_xy;
    if (matched) lastMatchT = tNow;
  }
}
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(outDir, 'questions.jsonl'), questions.map((q) => JSON.stringify(q)).join('\n') + '\n');
fs.writeFileSync(path.join(outDir, 'answers_private.jsonl'), answers.map((a) => JSON.stringify(a)).join('\n') + '\n');
const c = (f) => answers.filter(f).length;
console.log(JSON.stringify({ questions: questions.length, skipped_runs: skipped, by_kind: { SILENT_PICK: questions.filter((q) => q.kind === 'SILENT_PICK').length, LOST_WITH_CANDIDATES: questions.filter((q) => q.kind === 'LOST_WITH_CANDIDATES').length },
  answer_is_none: c((a) => a.answer === 0), rule_pick_correct_when_matched: `${c((a) => a.rule_matched && a.rule_pick === a.answer)}/${c((a) => a.rule_matched)}`,
  by_camera: Object.fromEntries([...new Set(questions.map((q) => q.camera))].map((k) => [k, questions.filter((q) => q.camera === k).length])) }));

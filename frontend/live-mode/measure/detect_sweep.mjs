// Detection-rate sweep. node measure/detect_sweep.mjs <label> <model:capsule|glb> <w> <h> [step] [headings]
// Output: JSON rows + summary in $OUT (default ./out).
import fs from 'node:fs';
import { launch, BASE, pct } from './lib.mjs';
const [label, model = 'capsule', w = '320', h = '180', step = '1.0', headings = '0,90,180,270', scene = 'n6', variant = 'T'] = process.argv.slice(2);
const out = process.env.OUT || 'out'; fs.mkdirSync(out, { recursive: true });
const b = await launch();
const page = await b.newPage(); page.on('pageerror', (e) => console.log('[err]', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.log('[console]', m.text()); });
await page.goto(`${BASE}/?role=sweep&model=${model}&scene=${scene}&w=${w}&h=${h}&variant=${variant}`);
await page.waitForFunction('window.__ready === true', { timeout: 60000 });
const tris = await page.evaluate('window.__tris');
const n6_scene = await page.evaluate('window.__n6');
const t0 = Date.now();
const { rows, times } = await page.evaluate(`window.__runSweep({step:${step}, headings:[${headings}], region:${process.env.REGION || 'null'}})`);
await b.close();
const elig = rows.filter((r) => r.inside >= 0.6 && r.gt_h_px >= 16);
const THR = Number(process.env.THR || 0.35); // live display threshold (server --min-score)
const rate = (a, t = THR) => (a.length ? a.filter((r) => r.iou >= 0.3 && r.score >= t).length / a.length : null);
const bins = (key, edges) => Object.fromEntries(edges.slice(0, -1).map((lo, i) => {
  const a = elig.filter((r) => r[key] >= lo && r[key] < edges[i + 1]);
  return [`${lo}-${edges[i + 1]}`, { n: a.length, rate: rate(a) }];
}));
const byCam = {};
for (const r of elig) (byCam[r.cam] ||= []).push(r);
const byHeading = {};
for (const r of elig) (byHeading[r.heading] ||= []).push(r);
const red = elig.filter((r) => r.iou >= 0.3 && r.score >= THR);
const summary = {
  label, model, scene, n6_scene, tris, res: [Number(w), Number(h)], step: Number(step), headings, samples_all: rows.length, eligible: elig.length,
  threshold: THR, detection_rate: rate(elig),
  rate_by_threshold: Object.fromEntries([0.1, 0.2, 0.3, 0.35, 0.5, 0.7].map((t) => [t, rate(elig, t)])),
  by_camera: Object.fromEntries(Object.entries(byCam).map(([k, a]) => [k, { n: a.length, rate: rate(a) }])),
  by_distance_m: bins('dist_m', [0, 4, 8, 12, 16, 40]),
  by_height_px: bins('gt_h_px', [16, 24, 32, 48, 80, 1000]),
  by_heading: Object.fromEntries(Object.entries(byHeading).map(([k, a]) => [k, { n: a.length, rate: rate(a) }])),
  red_label_rate_given_detected: red.length ? red.filter((r) => r.color === 'red').length / red.length : null,
  false_positives_per_frame: elig.length ? elig.reduce((s, r) => s + r.fp_scores.filter((v) => v >= THR).length, 0) / elig.length : null,
  mean_score_when_detected: red.length ? red.reduce((s, r) => s + r.score, 0) / red.length : null,
  eligible_n_by_camera_note: 'eligible = ray-visible, >=60% of GT box inside frame, GT height >= 16 px; detected = IoU>=0.3 and score>=threshold',
  request_ms: { p50: pct(times, 0.5), p95: pct(times, 0.95) }, wall_s: (Date.now() - t0) / 1000,
};
fs.writeFileSync(`${out}/${label}.rows.json`, JSON.stringify(rows));
fs.writeFileSync(`${out}/${label}.summary.json`, JSON.stringify(summary, null, 1));
console.log(JSON.stringify({ label, tris, eligible: elig.length, rate: summary.detection_rate, red_label: summary.red_label_rate_given_detected, wall_s: summary.wall_s }));

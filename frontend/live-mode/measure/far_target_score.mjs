// #619 offline scorer: join the smoke's A log (T's floor xy and GT-visible cameras: evaluation only), the recorded
// /infer detections and B's tracking state, and report, per tick and per distance, whether T was detected in each
// camera that GT says can see it. GT is read here only for scoring; nothing here feeds inference.
// node measure/far_target_score.mjs <dir> <case_id>...   (LIVE_BASE as in lib.mjs)
import fs from 'node:fs';
import {launch, BASE} from './lib.mjs';
const [dir, ...cases] = process.argv.slice(2);
const THR = Number(process.env.THR || 0.15);
const GRAPH_CAMS = new Set(['CAM_BRANCH', 'CAM_EXT_CAR', 'CAM_EXT_CLEAR', 'CAM_R101_IN', 'CAM_W1', 'CAM_W2', 'CAM_WIDE']); // graph v3 (no CAM_ENTRY, D74)
const W = Number(process.env.W || 320), H = Number(process.env.H || 180);
const iou = (a, b) => {
  const w = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])), h = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const i = w * h, u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i;
  return u > 0 ? i / u : 0;
};
const browser = await launch();
const page = await browser.newPage();
await page.goto(`${BASE}/?role=sweep&model=glb&scene=n6&w=${W}&h=${H}`);
await page.waitForFunction('window.__ready === true', {timeout: 60000});
const report = {thr: THR, size: [W, H], cases: {}};
for (const c of cases) {
  const a = JSON.parse(fs.readFileSync(`${dir}/${c}.a-log.json`));
  const b = JSON.parse(fs.readFileSync(`${dir}/${c}.b-log.json`));
  const d = Object.fromEntries(JSON.parse(fs.readFileSync(`${dir}/${c}.dets.json`)).map(x => [x.tick, x]));
  const bt = Object.fromEntries(b.ticks.map(t => [t.tick, t]));
  const ticks = [];
  for (const t of a.ticks) {
    const T = t.actors.find(x => x.id === 'T');
    if (!T?.present) continue;
    const vis = T.gt_visible.filter(v => GRAPH_CAMS.has(v));
    const proj = vis.length ? await page.evaluate(l => window.__project(l), vis.map(cam => ({cam, x: T.xy[0], y: T.xy[1]}))) : [];
    const per = vis.map((cam, i) => {
      const gt = proj[i].box; if (!gt) return null;
      const clip = [Math.max(0, gt[0]), Math.max(0, gt[1]), Math.min(W, gt[2]), Math.min(H, gt[3])];
      const full = (gt[2] - gt[0]) * (gt[3] - gt[1]);
      const inside = clip[2] > clip[0] && clip[3] > clip[1] ? (clip[2] - clip[0]) * (clip[3] - clip[1]) / full : 0;
      const sched = d[t.tick]?.schedule?.includes(cam) ?? null;
      const ds = d[t.tick]?.dets?.[cam] || [];
      let best = 0, score = 0, color = null, hsv = null;
      for (const x of ds) { const v = iou(x.bbox, clip); if (v > best) { best = v; score = x.score; color = x.color ?? null; hsv = x.red_ratio ?? null; } }
      return {cam, dist_m: +proj[i].dist_m.toFixed(1), h_px: +(clip[3] - clip[1]).toFixed(0), inside: +inside.toFixed(2), scheduled: sched, detected: best >= 0.3 && score >= THR, red: best >= 0.3 && score >= THR && color === 'red', color, red_ratio: hsv == null ? null : +hsv.toFixed(2), iou: +best.toFixed(2), score: +score.toFixed(2)};
    }).filter(Boolean);
    const tr = bt[t.tick]?.tracking || {};
    const err = tr.est_xy && T.xy ? +Math.hypot(tr.est_xy[0] - T.xy[0], tr.est_xy[1] - T.xy[1]).toFixed(1) : null;
    ticks.push({tick: t.tick, t_sim: +t.t_sim.toFixed(1), xy: T.xy.map(v => +v.toFixed(1)), gt_vis_all: T.gt_visible, gt_vis_graph: vis, per, state: tr.state, active: tr.active_cam, err_m: err});
  }
  report.cases[c] = ticks;
}
await browser.close();
fs.writeFileSync(`${dir}/far_target_score.json`, JSON.stringify(report));
// summary
const bins = [[0, 6], [6, 10], [10, 14], [14, 40]];
const out = {};
for (const [c, ticks] of Object.entries(report.cases)) {
  const rows = ticks.flatMap(t => t.per.map(p => ({...p, state: t.state}))).filter(p => p.inside >= 0.6);
  const rate = a => a.length ? +(a.filter(p => p.detected).length / a.length).toFixed(2) : null;
  const tk = ticks.length, anyVis = ticks.filter(t => t.gt_vis_graph.length).length;
  out[c] = {ticks: tk, ticks_visible_by_graph_cam: anyVis, ticks_no_graph_cam: tk - anyVis,
    ticks_entry_only: ticks.filter(t => !t.gt_vis_graph.length && t.gt_vis_all.includes('CAM_ENTRY')).length,
    ticks_visible_and_detected_any: ticks.filter(t => t.per.some(p => p.inside >= 0.6 && p.detected)).length,
    cam_frames: rows.length, detect_rate: rate(rows), red_rate: +(rows.filter(p => p.red).length / (rows.length || 1)).toFixed(2), scheduled_rate: rows.length ? +(rows.filter(p => p.scheduled).length / rows.length).toFixed(2) : null,
    by_dist: Object.fromEntries(bins.map(([lo, hi]) => { const a = rows.filter(p => p.dist_m >= lo && p.dist_m < hi); return [`${lo}-${hi}m`, {n: a.length, detect: rate(a), red: a.length ? +(a.filter(p => p.red).length / a.length).toFixed(2) : null}]; }))};
}
console.log(JSON.stringify(out, null, 1));

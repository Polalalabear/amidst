// Measurement page: a single person placed on a grid of floor positions and headings, rendered by
// every camera that can see it (ground-truth ray test), sent to /detect. Evaluation only.
import { groundTruthVisible } from './world.mjs';
import { setupWorld } from './setup.mjs';
import { blocked } from './sim.mjs';
import { makePerson, projectBox } from './person.mjs';
import { makeCapture, packInfer } from './capture.mjs';
import { params } from './common.mjs';

const iou = (a, b) => {
  const w = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])), h = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const i = w * h, u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i;
  return u > 0 ? i / u : 0;
};

export async function start() {
  const P = params();
  const { geometry, world, cams, n6 } = await setupWorld(P);
  window.__n6 = n6;
  const person = await makePerson(P.model, world, 'red', new URLSearchParams(location.search).get('variant') || 'T'); // #619: ?variant=T|A|B|C (glb)
  const cap = makeCapture(world, cams, P.w, P.h, P.quality);
  person.update(0.5); // apply the idle clip once (glb)
  window.__tris = person.tris;
  // #619: GT pixel boxes of a person standing at given floor points, for offline scoring of recorded detections.
  window.__project = (list) => { person.update(0.5); world.scene.updateMatrixWorld(true);
    return list.map(({ cam, x, y }) => { const cc = cams[cam].camera.matrixWorld.elements;
      return { box: projectBox(cams[cam].camera, world.root, x, y, P.w, P.h), dist_m: Math.hypot(cc[12] - x, cc[14] + y) }; }); };
  window.__runSweep = async ({ step = 1.0, headings = [0, 90, 180, 270], limit = 1e9, region = null } = {}) => {
    const rows = [];
    let n = 0;
    const times = [];
    for (const f of geometry.floors) {
      if (f.floor_id === 'R004_EXTERIOR_FLOOR' && false) continue;
      for (let x = f.x_m[0] + step / 2; x < f.x_m[1]; x += step) for (let y = f.y_m[0] + step / 2; y < f.y_m[1]; y += step) {
        if (region && (x < region[0] || x > region[1] || y < region[2] || y > region[3])) continue;
        if (blocked(x, y, world.segments, 0.3)) continue;
        for (const hd of headings) {
          if (n++ >= limit) return { rows, times };
          const h = hd * Math.PI / 180;
          person.setPose(x, y, h);
          world.scene.updateMatrixWorld(true);
          const vis = groundTruthVisible(cams, world.blockers, world.root, x, y);
          if (!vis.length) continue;
          const frames = [];
          for (const id of vis) frames.push({ cam: id, jpeg: await cap.shoot(id) });
          const header = { tick: n, t_capture_ms: 0, frames: frames.map((fr) => ({ cam: fr.cam, bytes: fr.jpeg.byteLength })) };
          const t0 = performance.now();
          const res = await fetch('/detect', { method: 'POST', body: packInfer(header, frames.map((fr) => fr.jpeg)) }).then((r) => r.json());
          times.push(performance.now() - t0);
          for (const cam of vis) {
            const gt = projectBox(cams[cam].camera, world.root, x, y, P.w, P.h);
            if (!gt) continue;
            const clip = [Math.max(0, gt[0]), Math.max(0, gt[1]), Math.min(P.w, gt[2]), Math.min(P.h, gt[3])];
            const full = (gt[2] - gt[0]) * (gt[3] - gt[1]);
            const inside = clip[2] > clip[0] && clip[3] > clip[1] ? (clip[2] - clip[0]) * (clip[3] - clip[1]) / full : 0;
            const cc = cams[cam].camera.matrixWorld.elements;
            const dist = Math.hypot(cc[12] - x, cc[14] + y);
            const ds = res.dets[cam] || [];
            let best = null, bi = 0;
            for (const d of ds) { const v = iou(d.bbox, clip); if (v > bi) { bi = v; best = d; } }
            rows.push({ cam, x, y, heading: hd, dist_m: +dist.toFixed(2), gt_h_px: +(clip[3] - clip[1]).toFixed(1), inside: +inside.toFixed(2),
              iou: +bi.toFixed(2), score: best ? +best.score.toFixed(3) : 0, color: best ? best.color : null, red_ratio: best ? +(best.red_ratio ?? 0).toFixed(3) : null,
              n_dets: ds.length, fp_scores: ds.filter((d) => iou(d.bbox, clip) < 0.1).map((d) => +d.score.toFixed(2)) });
          }
        }
      }
    }
    return { rows, times };
  };
  window.__ready = true;
}

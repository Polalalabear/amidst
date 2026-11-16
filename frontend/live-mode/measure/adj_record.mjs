// Adjudication question harvest (docs/design/LIVE_MODE_LLM_DECISION_V1.md): like t1_record.mjs, and additionally keeps a
// 960x540 capture of every enabled camera for the ticks where a decision could be needed (>= 2 red detections in one
// camera) and for the first lock (reference crop). The tracker is unchanged; the extra captures are not sent to the backend.
// node measure/adj_record.mjs <label> "<operator query>" <seconds>
import fs from 'node:fs';
import { launch, BASE, sleep } from './lib.mjs';
const [label, query, secs = '41'] = process.argv.slice(2);
const out = `${process.env.OUT || 'out'}/${label}`; fs.mkdirSync(out, { recursive: true });
const b = await launch();
const op = await b.newPage(); op.on('pageerror', (e) => console.log('[op err]', e.message));
await op.evaluateOnNewDocument(() => {
  window.__adj = { rows: [], frames: [], hi: null, n: 0 };
  const f = window.fetch.bind(window);
  window.fetch = async (url, init) => {
    const isInfer = typeof url === 'string' && url.startsWith('/infer');
    if (!isInfer) return f(url, init);
    const A = window.__adj, idx = A.n++;
    const gt = window.__op ? [window.__op.P0.x, window.__op.P0.y] : null;
    const hi = {};
    if (A.hi) for (const id of window.__log.config.cams) hi[id] = await A.hi.shoot(id); // right after the low-res captures
    const tCall = performance.timeOrigin + performance.now();
    const r = await f(url, init);
    r.clone().json().then((j) => {
      A.rows.push({ idx, t_call: tCall, t_resp: performance.timeOrigin + performance.now(), gt_xy: gt, dets: j.dets, tracking: j.tracking });
      const acquire = (j.tracking.events || []).some((e) => e.type === 'ACQUIRE');
      for (const [cam, list] of Object.entries(j.dets)) {
        const reds = list.filter((d) => d.color === 'red').length;
        if (hi[cam] && (reds >= 2 || (acquire && cam === j.tracking.active_cam))) {
          const u8 = new Uint8Array(hi[cam]); let s = '';
          for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
          A.frames.push({ idx, cam, b64: btoa(s) });
        }
      }
    });
    return r;
  };
});
await op.goto(`${BASE}/?${query}`);
await op.waitForFunction('window.__ready === true', { timeout: 90000 });
await op.evaluate(async () => {
  const { makeCapture } = await import('/src/capture.mjs');
  window.__adj.hi = makeCapture(window.__op.world, window.__op.cams, 960, 540, 0.9);
});
await sleep(Number(secs) * 1000);
const data = await op.evaluate(() => ({ cfg: { ...__log.config, n6: !!__log.config.n6 }, t0: __log.fpsStart, dropped: __log.dropped,
  ticks: __log.ticks.map((t) => ({ tick: t.tick, t_capture: t.t_capture, gt_visible: t.gt_visible })), rows: __adj.rows, frames: __adj.frames }));
await b.close();
for (const fr of data.frames) fs.writeFileSync(`${out}/${String(fr.idx).padStart(3, '0')}_${fr.cam}.jpg`, Buffer.from(fr.b64, 'base64'));
fs.writeFileSync(`${out}/raw.json`, JSON.stringify({ label, query, secs: Number(secs), cfg: data.cfg, t0: data.t0, dropped: data.dropped, ticks: data.ticks,
  rows: data.rows, frames: data.frames.map((f) => ({ idx: f.idx, cam: f.cam })) }));
console.log(label, 'ticks', data.ticks.length, 'rows', data.rows.length, 'frames kept', data.frames.length, 'dropped', data.dropped);

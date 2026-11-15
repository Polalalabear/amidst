// T1 (docs/design/LIVE_MODE_LLM_DECISION_V1.md §4): record what the rule-only tracker sees and decides on a
// scripted route, without changing the tracker. node measure/t1_record.mjs <label> "<operator query>" <seconds>
// Wraps fetch in the operator page to keep every /infer response (pixel-derived detections + tracking), and
// reads the operator's own evaluation-only state (target position, ground-truth visibility). Nothing here
// is sent to the backend.
import fs from 'node:fs';
import { launch, BASE, sleep } from './lib.mjs';
const [label, query, secs = '41'] = process.argv.slice(2);
const out = process.env.OUT || 'out'; fs.mkdirSync(out, { recursive: true });
const b = await launch();
const op = await b.newPage(); op.on('pageerror', (e) => console.log('[op err]', e.message));
await op.evaluateOnNewDocument(() => {
  window.__t1 = [];
  const f = window.fetch.bind(window);
  window.fetch = async (url, init) => {
    const isInfer = typeof url === 'string' && url.startsWith('/infer');
    const gt = isInfer && window.__op ? [window.__op.P0.x, window.__op.P0.y] : null;
    const tCall = performance.timeOrigin + performance.now();
    const r = await f(url, init);
    if (isInfer) r.clone().json().then((j) => window.__t1.push({ t_call: tCall, t_resp: performance.timeOrigin + performance.now(),
      gt_xy: gt, dets: j.dets, tracking: j.tracking, timing: j.timing_ms }));
    return r;
  };
});
await op.goto(`${BASE}/?${query}`);
await op.waitForFunction('window.__ready === true', { timeout: 90000 });
await sleep(Number(secs) * 1000);
const data = await op.evaluate(() => ({ cfg: { ...__log.config, n6: !!__log.config.n6 }, t0: __log.fpsStart, sent: __log.sent, dropped: __log.dropped,
  ticks: __log.ticks.map((t) => ({ tick: t.tick, t_capture: t.t_capture, gt_visible: t.gt_visible })), infer: __t1 }));
await b.close();
const load1 = Number(fs.existsSync('/proc') ? 0 : (await import('node:child_process')).execSync('sysctl -n vm.loadavg').toString().trim().split(' ')[1]);
fs.writeFileSync(`${out}/${label}.t1raw.json`, JSON.stringify({ label, query, secs: Number(secs), load1_end: load1, ...data }));
console.log(label, 'ticks', data.ticks.length, 'infer', data.infer.length, 'dropped', data.dropped, 'load1', load1);

// Fixed route RGB packets plus separate evaluation GT. No GT is sent to the server.
// node scripts/live_mode/record_detection_route.mjs <out> <label> '<query>' <seconds>
import fs from 'node:fs';
import path from 'node:path';
import { launch, BASE, sleep } from '../../frontend/live-mode/measure/lib.mjs';
const [out, label, query, seconds] = process.argv.slice(2);
const packets = path.join(out, 'packets', label);
fs.mkdirSync(packets, { recursive: true });
fs.mkdirSync(path.join(out, 'raw'), { recursive: true });
const browser = await launch();
try {
  const page = await browser.newPage();
  await page.exposeFunction('savePacket', (base64) => {
    const buf = Buffer.from(base64, 'base64');
    const n = buf.readUInt32LE();
    const h = JSON.parse(buf.subarray(4, 4+n).toString());
    fs.writeFileSync(path.join(packets, `${h.tick}.bin`), buf);
  });
  await page.evaluateOnNewDocument(() => {
    window.__recorded = [];
    const fetchOriginal = window.fetch.bind(window);
    window.fetch = async (url, init) => {
      if (typeof url !== 'string' || !url.startsWith('/infer')) return fetchOriginal(url, init);
      const truth = window.__op ? [window.__op.P0.x, window.__op.P0.y] : null;
      let s = ''; for (const b of new Uint8Array(init.body)) s += String.fromCharCode(b);
      await window.savePacket(btoa(s));
      const t = performance.timeOrigin + performance.now();
      const response = await fetchOriginal(url, init);
      const j = await response.clone().json();
      window.__recorded.push({ tick: j.tick, t_call: t, t_resp: performance.timeOrigin+performance.now(),
        gt_xy: truth, dets: j.dets, tracking: j.tracking, timing: j.timing_ms });
      return response;
    };
  });
  await page.goto(`${BASE}/?${query}`);
  await page.waitForFunction('window.__ready === true', { timeout: 90000 });
  await sleep(Number(seconds)*1000);
  const data = await page.evaluate(() => ({ cfg: __log.config, t0: __log.fpsStart, sent: __log.sent,
    dropped: __log.dropped, ticks: __log.ticks.map(t => ({ tick: t.tick, t_capture: t.t_capture, gt_visible: t.gt_visible })),
    infer: __recorded }));
  fs.writeFileSync(path.join(out, 'raw', `${label}.t1raw.json`), JSON.stringify({ label, query, secs: Number(seconds), ...data }));
  console.log(JSON.stringify({ label, ticks: data.ticks.length, infer: data.infer.length, dropped: data.dropped }));
} finally { await browser.close(); }

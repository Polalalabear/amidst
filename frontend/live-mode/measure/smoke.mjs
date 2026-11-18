import { launch, BASE, sleep, pct } from './lib.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const outputDir = process.env.AMIDST_ARTIFACTS
  ? path.join(process.env.AMIDST_ARTIFACTS, 'evidence', 'live-mode', 'smoke')
  : fileURLToPath(new URL('../../../local/evidence/live-mode/smoke/', import.meta.url));
const outputPrefix = process.env.OUT || path.join(outputDir, 'smoke');
fs.mkdirSync(path.dirname(`${outputPrefix}_sys.png`), { recursive: true });
const b = await launch();
const sys = await b.newPage(); sys.on('pageerror', (e) => console.log('[sys err]', e.message));
await sys.goto(`${BASE}/?role=system`);
const op = await b.newPage(); op.on('pageerror', (e) => console.log('[op err]', e.message));
const q = process.env.Q || 'auto=B4&duration=42';
await op.goto(`${BASE}/?${q}`);
await sleep(Number(process.env.T || 30000));
const o = await op.evaluate(() => ({ sent: __log.sent, dropped: __log.dropped, ticks: __log.ticks.map((t) => [t.t_capture, t.t_resp, t.timing.forward, t.timing.server_total]) }));
const s = await sys.evaluate(() => ({ n: __log.displays.length, viol: __log.violations.length, d: __log.displays.map((x) => x.t_display - x.t_capture) }));
console.log(JSON.stringify({ sent: o.sent, dropped: o.dropped, fwd_p50: pct(o.ticks.slice(3).map((t) => t[2]), .5), srv_p50: pct(o.ticks.slice(3).map((t) => t[3]), .5), disp_p50: pct(s.d.slice(3), .5), disp_p95: pct(s.d.slice(3), .95), viol: s.viol }));
await sys.screenshot({ path: `${outputPrefix}_sys.png` });
await op.screenshot({ path: `${outputPrefix}_op.png` });
await b.close();

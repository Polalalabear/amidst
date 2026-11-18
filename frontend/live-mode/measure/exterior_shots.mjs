// #602 evidence: operator views (A look-west, B look-north) with/without the exterior, a system camera tile,
// and detection-candidate counts on the scripted A4 route. node measure/exterior_shots.mjs <outdir>
// (LIVE_BASE selects the server, never 8785/8791). The operator view override is injected into the served
// operator.mjs by request interception for this measurement only; the shipped operator is unchanged.
import fs from 'node:fs';
import { launch, BASE, sleep } from './lib.mjs';
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
const b = await launch();
async function operatorShot(name, ext, start, dir) {
  const op = await b.newPage(); await op.setViewport({ width: 1280, height: 720 });
  await op.setRequestInterception(true);
  op.on('request', async (r) => {
    if (!r.url().includes('/src/operator.mjs')) return r.continue();
    const src = await (await fetch(r.url())).text();
    const line = 'vcam.position.set(P0.x, n6 ? 9 : 3.5, -(P0.y - (n6 ? 2.2 : 4.5))); vcam.lookAt(P0.x, 1, -P0.y);';
    if (!src.includes(line)) throw new Error('operator view line not found');
    r.respond({ status: 200, contentType: 'text/javascript', body: src.replace(line, 'if (window.__eye) { vcam.position.set(...window.__eye.p); vcam.lookAt(...window.__eye.t); } else { ' + line + ' }') });
  });
  op.on('pageerror', (e) => console.log('[op err]', e.message));
  await op.goto(`${BASE}/?model=glb&w=320&h=180&fps=1&ext=${ext}`);
  await op.waitForFunction('window.__ready === true', { timeout: 120000 });
  // eye 1.7 m above the start point, looking along the horizon (three Y-up: blender (x,y) -> (x,-y))
  await op.evaluate(([x, y, d]) => { __op.P0.x = x; __op.P0.y = y; window.__eye = { p: [x, 1.7, -y], t: [x + d[0] * 20, 1.7, -(y + d[1] * 20)] }; }, [...start, dir]);
  await sleep(1500);
  await (await op.$('#view')).screenshot({ path: `${out}/${name}.png` });
  await op.close();
}
const A = [-10, -0.4], B = [-8, 2]; // both inside the N6 yard (blender x,y)
for (const ext of process.env.DET_ONLY ? [] : [0, 1]) {
  const tag = ext ? 'after' : 'before';
  await operatorShot(`${tag}_A_look-west`, ext, A, [-1, 0]);
  await operatorShot(`${tag}_B_look-north`, ext, B, [0, 1]);
}
// system camera tile + detection candidates. The scripted clock is frozen (as in n6_ceiling_compare) so the
// ext on/off captures show the same actors at the same poses; candidates = all detections returned per camera frame.
const CLOCK = 'const tSec = (tn - t0) / 1000;', DELTA = 'const dt = Math.min(0.1, (tn - last) / 1000); last = tn;';
const detCount = {};
for (const frozen of [12, 30]) for (const ext of [0, 1]) {
  const sys = await b.newPage(); await sys.setViewport({ width: 1600, height: 900 });
  await sys.goto(`${BASE}/?role=system&view=grid`); await sys.waitForFunction('window.__ready === true');
  const op = await b.newPage(); await op.setRequestInterception(true);
  op.on('request', async (r) => {
    if (!r.url().includes('/src/operator.mjs')) return r.continue();
    const src = await (await fetch(r.url())).text();
    if (!src.includes(CLOCK) || !src.includes(DELTA)) throw new Error('operator clock lines not found');
    r.respond({ status: 200, contentType: 'text/javascript', body: src.replace(CLOCK, `const tSec = ${frozen};`).replace(DELTA, 'const dt = 0; last = tn;') });
  });
  const stats = { ticks: 0, frames: {}, dets: {} };
  op.on('response', async (res) => {
    if (!res.url().endsWith('/infer')) return;
    try { const j = await res.json(); stats.ticks++;
      for (const [cam, arr] of Object.entries(j.dets || {})) { stats.frames[cam] = (stats.frames[cam] || 0) + 1; stats.dets[cam] = (stats.dets[cam] || 0) + (Array.isArray(arr) ? arr.length : 0); } } catch { /* ignore */ }
  });
  await op.goto(`${BASE}/?auto=A4&run=A4-1-v2-4actor&model=glb&w=640&h=360&fps=2&ext=${ext}`);
  await op.waitForFunction('window.__ready === true', { timeout: 120000 });
  await sleep(14000);
  await sys.screenshot({ path: `${out}/${ext ? 'after' : 'before'}_system_grid_cameras_t${frozen}.png` });
  stats.total_dets = Object.values(stats.dets).reduce((x, y) => x + y, 0);
  stats.total_frames = Object.values(stats.frames).reduce((x, y) => x + y, 0);
  detCount[`t${frozen}_ext_${ext ? 'on' : 'off'}`] = stats;
  await op.close(); await sys.close();
}
await b.close();
fs.writeFileSync(`${out}/detection_candidates.json`, JSON.stringify(detCount, null, 1));
console.log(JSON.stringify(detCount));

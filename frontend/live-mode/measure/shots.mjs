// Operator + system screenshots for the N6 integration: idle, walk, run (WASD on the operator), then one
// camera switch on the scripted B4 route. node measure/shots.mjs <outdir>   (LIVE_BASE selects the server)
import fs from 'node:fs';
import { launch, BASE, sleep } from './lib.mjs';
const out = process.argv[2] || 'shots'; fs.mkdirSync(out, { recursive: true });
const Q = 'model=glb&w=320&h=180&fps=3&cams=CAM_W1,CAM_W2,CAM_R101_IN';
const b = await launch();
const meta = {};
async function pair(query) {
  const sys = await b.newPage(); await sys.goto(`${BASE}/?role=system`); await sys.waitForFunction('window.__ready === true');
  const op = await b.newPage(); op.on('pageerror', (e) => console.log('[op err]', e.message));
  await op.goto(`${BASE}/?${query}`); await op.waitForFunction('window.__ready === true', { timeout: 120000 });
  return { sys, op };
}
const state = (op) => op.evaluate(() => { const p = __op.player, c = p.current; return { x: +__op.P0.x.toFixed(2), y: +__op.P0.y.toFixed(2), speed: +(__op.P0.speed || 0).toFixed(3),
  clip: c ? Object.keys(p.actions).find((k) => p.actions[k] === c) : null, timeScale: c ? +c.timeScale.toFixed(4) : null, variant: p.variant, tris: p.tris }; });
async function snap(name, sys, op) {
  await sys.screenshot({ path: `${out}/${name}_system.png` }); await op.screenshot({ path: `${out}/${name}_operator.png` });
  meta[name] = await state(op); console.log(name, JSON.stringify(meta[name]));
}
{ // manual: idle -> walk -> run
  const { sys, op } = await pair(Q);
  await sleep(6000); await snap('idle', sys, op);
  await op.evaluate(() => __setKeys({ d: true })); await sleep(2500); await snap('walk', sys, op);
  await op.evaluate(() => __setKeys({ shift: true })); await sleep(2500); await snap('run', sys, op);
  await op.evaluate(() => __setKeys({ d: false, shift: false }));
  await sys.close(); await op.close();
}
{ // scripted B4 route: wait for the first system SWITCH, shoot just before the active camera changes and just after
  const { sys, op } = await pair(`auto=B4&duration=42&${Q}`);
  let before = null, shot = false; const t0 = Date.now();
  while (Date.now() - t0 < 80000 && !shot) {
    await sleep(700);
    const last = await sys.evaluate(() => { const d = __log.displays; const l = d[d.length - 1]; const sw = d.flatMap((x) => (x.events || []).filter((e) => e.type === 'SWITCH')); return { active: l && l.active, tick: l && l.tick, sw }; });
    if (last.sw.length) { await snap('switch_after', sys, op); meta.switch_event = last.sw[0]; shot = true; break; }
    if (last.active && !before) { await snap('switch_before', sys, op); before = last.active; }
    else if (last.active) { await sys.screenshot({ path: `${out}/switch_before_system.png` }); await op.screenshot({ path: `${out}/switch_before_operator.png` }); meta.switch_before = await state(op); }
  }
  meta.switch_found = shot;
  await sys.close(); await op.close();
}
await b.close();
fs.writeFileSync(`${out}/shots.meta.json`, JSON.stringify(meta, null, 1));

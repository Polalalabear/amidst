// #677 headless screenshots of the LIVE UI pass. node measure/live_ui_shots.mjs <outdir>   (LIVE_BASE selects the server; never 8785/8791)
import fs from 'node:fs';
import { launch, BASE, sleep } from './lib.mjs';
const out = process.argv[2] || 'shots'; fs.mkdirSync(out, { recursive: true });
const Q = 'model=glb&w=320&h=180&fps=3&cams=CAM_W1,CAM_W2,CAM_R101_IN';
const meta = {};
const b = await launch();
const view = async (page, w, h) => { await page.setViewport({ width: w, height: h }); await sleep(600); };
const pick = async page => { const c = await page.$('#target-candidates button'); if (c) await c.click(); };
const shot = async (page, name) => { await page.screenshot({ path: `${out}/${name}.png` }); console.log(name); };
try {
  // 1. operator HUD, 1280 and 1920, then a window resize
  const op = await b.newPage(); op.on('pageerror', e => console.log('[op err]', e.message));
  await op.goto(`${BASE}/?role=operator&run=A4-1&actor=T&${Q}`); await op.waitForFunction('window.__ready === true', { timeout: 120000 });
  await sleep(5000);
  await view(op, 1280, 720); await shot(op, 'operator_hud_1280x720');
  await view(op, 1920, 1080); await shot(op, 'operator_hud_1920x1080');
  await view(op, 1280, 720); await shot(op, 'operator_resize_before_1280x720');
  await view(op, 900, 640); await shot(op, 'operator_resize_after_900x640');
  await op.click('#map-toggle'); await sleep(300); await shot(op, 'operator_minimap_off_900x640');
  await op.click('#map-toggle'); await view(op, 1280, 720);
  // 2. system panel
  let sys = await b.newPage(); sys.on('pageerror', e => console.log('[sys err]', e.message));
  await sys.goto(`${BASE}/?role=system`); await sys.waitForFunction('window.__ready === true', { timeout: 180000 });
  await sys.evaluate(() => { try { localStorage.clear(); } catch {} });
  await sys.reload(); await sys.waitForFunction('window.__ready === true', { timeout: 180000 });
  await sys.waitForFunction('window.__hud && __hud.cfg', {}); await sleep(1500);
  await sys.click('[data-target-color=red]'); await sys.click('#target-start'); await sleep(2500); await pick(sys); await sleep(5000);
  await view(sys, 1280, 720); await shot(sys, 'system_panel_open_1280x720');
  await view(sys, 1920, 1080); await shot(sys, 'system_panel_open_1920x1080');
  await view(sys, 1280, 720); await sys.click('#side-toggle'); await sleep(500); await shot(sys, 'system_panel_collapsed_1280x720');
  await view(sys, 1920, 1080); await shot(sys, 'system_panel_collapsed_1920x1080');
  await view(sys, 1280, 720); await sys.click('#side-toggle'); await sleep(500);
  const h = await sys.$('#side-resize'), bb = await h.boundingBox();
  await sys.mouse.move(bb.x + 3, bb.y + 200); await sys.mouse.down(); await sys.mouse.move(bb.x - 120, bb.y + 200, { steps: 6 }); await sys.mouse.up(); await sleep(400);
  await shot(sys, 'system_panel_resized_wider_1280x720');
  meta.prefs = await sys.evaluate(() => localStorage.getItem('amidst.live.system.panel.v1'));
  meta.model = await sys.evaluate(() => document.getElementById('llmmodel').value);
  await sys.reload(); await sys.waitForFunction('window.__ready === true', { timeout: 180000 }); await sleep(800);
  meta.afterReload = await sys.evaluate(() => ({ cls: document.getElementById('bs').className, w: getComputedStyle(document.getElementById('bs')).getPropertyValue('--side-w') }));
  // 3. wait for lost / same-colour hints on the real route
  await op.close();
  const op2 = await b.newPage(); await op2.goto(`${BASE}/?role=operator&auto=A4&duration=50&${Q}`); await op2.waitForFunction('window.__ready === true', { timeout: 120000 });
  await sys.close(); sys = await b.newPage(); await sys.goto(`${BASE}/?role=system`); await sys.waitForFunction('window.__ready === true', { timeout: 180000 }); await sleep(2500);
  await view(sys, 1280, 720); await sys.click('[data-target-color=red]'); await sys.click('#target-start'); await sleep(2500); await pick(sys);
  // The real A4 route does not lose the target or show two same-colour people at once within a short run, so the two hint screens
  // use the real page and a real TRACKING session, then stop the operator and inject display-only detections (synthetic fixture, labelled in the PR).
  const seen = {};
  await sleep(6000); await op2.close(); await sleep(1500);
  const d = (color, xy, cam = 'CAM_W2') => ({ bbox: [0, 0, 1, 1], score: .9, color, est_xy: xy, red_ratio: .5, blue_ratio: 0 });
  await sys.evaluate(d2 => { __hud.setDets(d2); }, { CAM_W2: [d('red', [-11.5, -0.5]), d('red', [-7, 1])], CAM_W1: [d('blue', [12.4, 2])] });
  await sleep(600); await shot(sys, 'system_same_colour_hint_1280x720'); seen.same = true;
  await sys.evaluate(() => { const tr = { state: 'LOST', active_cam: 'CAM_W2', seen_cams: [], est_xy: [-11.5, -0.5], events: [], lost_ticks: 4, target: { color: 'red', mode: 'TRACKING' }, decision_source: 'RULE_ONLY', fallback_reason: null };
    setInterval(() => { __hud.st.tr = tr; __hud.st.lostSince = __hud.st.lostSince || Date.now() - 4000; }, 50); });
  await sleep(800); await sys.evaluate(() => __hud.setDets({ CAM_W2: [{ bbox: [0,0,1,1], score: .9, color: 'red', est_xy: [-11.5, -0.5] }, { bbox: [0,0,1,1], score: .9, color: 'red', est_xy: [-7, 1] }], CAM_W1: [{ bbox: [0,0,1,1], score: .9, color: 'blue', est_xy: [12.4, 2] }] })); await sleep(300); await shot(sys, 'system_lost_hint_1280x720');
  meta.lostText = await sys.evaluate(() => document.getElementById('lost-hint').innerText);
  meta.sameText = await sys.evaluate(() => document.getElementById('same-color').innerText);
  meta.seen = seen;
  await sys.close();
} finally { await b.close(); }
fs.writeFileSync(`${out}/live_ui_shots.meta.json`, JSON.stringify(meta, null, 1));

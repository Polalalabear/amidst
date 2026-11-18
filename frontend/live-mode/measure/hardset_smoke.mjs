// #597 browser smoke: run the A window with the scripted operator and save its private A log.
// node measure/hardset_smoke.mjs <case_id> [extra query]   (LIVE_BASE, OUT, CHROME as in lib.mjs)
// The A log holds GT for offline evaluation only; nothing here is sent to the backend beyond what A already sends.
import fs from 'node:fs';
import puppeteer from 'puppeteer-core';
import {launch, BASE, CHROME, sleep} from './lib.mjs';
import {HARDSET_ROUTES} from '../src/hardset_routes.mjs';

const [caseId, extra = 'model=glb&w=320&h=180&fps=5'] = process.argv.slice(2);
if (!HARDSET_ROUTES[caseId]) throw new Error(`unknown case ${caseId}`);
const out = process.env.OUT || 'out';
fs.mkdirSync(out, {recursive: true});
const steps = HARDSET_ROUTES[caseId].steps.length;
// HEADLESS=0 opens a visible window: headless Chrome throttles animation frames, which slows the fixed-step sim.
const browser = process.env.HEADLESS === '0'
  ? await puppeteer.launch({executablePath: CHROME, headless: false, protocolTimeout: 3_600_000, defaultViewport: {width: 1280, height: 720},
    args: ['--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows', '--no-first-run']})
  : await launch();
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  // main's backend has no /reset session_id yet (AB §5.3 lands with #610). Fill a test id only when it is missing,
  // and record that it was filled; with a backend that returns one, nothing changes.
  await page.evaluateOnNewDocument(() => {
    const original = window.fetch.bind(window);
    window.__resetShim = false;
    window.fetch = async (url, init) => {
      const response = await original(url, init);
      if (url !== '/reset') return response;
      const body = await response.clone().json().catch(() => ({}));
      if (body.session_id) return response;
      window.__resetShim = true;
      const id = Array.from(crypto.getRandomValues(new Uint8Array(8)), b => b.toString(16).padStart(2, '0')).join('');
      return new Response(JSON.stringify({...body, session_id: id}), {status: response.status, headers: {'content-type': 'application/json'}});
    };
  });
  await page.goto(`${BASE}/?script=${encodeURIComponent(caseId)}&${extra}`);
  await page.waitForFunction('window.__ready === true', {timeout: 120000});
  const t0 = Date.now();
  // Finish when every route step is done and one more second of simulation has been captured.
  await page.waitForFunction(n => {
    const done = (window.__log.script_events || []).filter(e => e.type === 'script_step_done');
    const last = window.__log.ticks.at(-1);
    return done.length >= n && last && last.t_sim >= done.at(-1).t_sim + 1;
  }, {timeout: 600000, polling: 500}, steps);
  await sleep(300);
  const log = await page.evaluate(() => JSON.parse(JSON.stringify(window.__log)));
  log.smoke = {case_id: caseId, query: extra, wall_s: (Date.now() - t0) / 1000, page_errors: errors,
    reset_session_shim: await page.evaluate(() => window.__resetShim)};
  const file = `${out}/${caseId}.a-log.json`;
  fs.writeFileSync(file, JSON.stringify(log));
  console.log(caseId, 'ticks', log.ticks.length, 'sent', log.sent, 'dropped', log.dropped, 'errors', (log.errors || []).length, 'page_errors', errors.length, '->', file);
} finally {
  await browser.close();
}

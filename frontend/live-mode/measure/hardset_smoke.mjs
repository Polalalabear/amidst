// #597 browser smoke: run the A window with the scripted operator and the B window (?role=system, rules only),
// start red-top tracking in B as soon as it has A's session, and save both private logs.
// node measure/hardset_smoke.mjs <case_id> [extra A query]   (LIVE_BASE, OUT, CHROME as in lib.mjs)
// The A log holds GT for offline evaluation only; nothing here is sent to the backend beyond what A and B
// already send. B's LLM switch is checked to be off (the server also runs with --advisor off).
import fs from 'node:fs';
import {launch, BASE, sleep} from './lib.mjs';
import {HARDSET_ROUTES} from '../src/hardset_routes.mjs';

const [caseId, extra = 'model=glb&w=320&h=180&fps=5'] = process.argv.slice(2);
if (!HARDSET_ROUTES[caseId]) throw new Error(`unknown case ${caseId}`);
const out = process.env.OUT || 'out';
fs.mkdirSync(out, {recursive: true});
const steps = HARDSET_ROUTES[caseId].steps.length;
// Headless only (D331: no windows on the user's desktop). lib.mjs launches headless 'new' with background
// throttling disabled, so animation frames are not slowed by occlusion.
const browser = await launch();
async function openWindow() {
  const cdp = await browser.target().createCDPSession();
  const {targetId} = await cdp.send('Target.createTarget', {url: 'about:blank', newWindow: true});
  const target = await browser.waitForTarget(t => t._targetId === targetId || t._getTargetInfo?.().targetId === targetId);
  return target.page();
}
try {
  const errors = {a: [], b: []};
  // B in its own (headless) window of the same context: A sends frames to B over a BroadcastChannel (same
  // storage partition).
  const b = await openWindow();
  b.on('pageerror', e => errors.b.push(e.message));
  await b.goto(`${BASE}/?role=system`);
  await b.waitForFunction('window.__ready === true', {timeout: 120000});
  console.error('B ready');
  const a = await openWindow();
  a.on('pageerror', e => errors.a.push(e.message));
  await a.goto(`${BASE}/?script=${encodeURIComponent(caseId)}&${extra}`);
  await a.waitForFunction('window.__ready === true', {timeout: 120000});
  const session = await a.evaluate(() => window.__log.session_id);
  console.error('A ready, session', session);
  await b.waitForFunction(s => window.__log.session_id === s, {timeout: 30000, polling: 100}, session);
  const llmOn = await b.evaluate(() => document.getElementById('llmon').checked);
  if (llmOn) throw new Error('B_LLM_SWITCH_ON');
  await b.click('[data-target-color="red"]');
  await b.click('#target-start');
  await a.bringToFront();
  console.error('B started');
  const tStart = await a.evaluate(() => window.__log.ticks.at(-1)?.t_sim ?? 0);
  const t0 = Date.now();
  const progress = setInterval(async () => {
    try {
      const p = await a.evaluate(() => ({t: window.__log.ticks.at(-1)?.t_sim, n: window.__log.ticks.length, done: (window.__log.script_events || []).filter(e => e.type === 'script_step_done').length, sim: window.__op?.t_sim}));
      console.error('progress', JSON.stringify(p));
    } catch (e) { console.error('progress err', e.message); }
  }, 10000);
  // Finish when every route step is done and one more second of simulation has been captured.
  await a.waitForFunction(n => {
    const done = (window.__log.script_events || []).filter(e => e.type === 'script_step_done');
    const last = window.__log.ticks.at(-1);
    return done.length >= n && last && last.t_sim >= done.at(-1).t_sim + 1;
  }, {timeout: 600000, polling: 500}, steps);
  clearInterval(progress);
  await sleep(1500); // let B receive the last ticks
  const aLog = await a.evaluate(() => JSON.parse(JSON.stringify(window.__log)));
  const bLog = await b.evaluate(() => JSON.parse(JSON.stringify(window.__log)));
  aLog.smoke = {case_id: caseId, query: extra, wall_s: (Date.now() - t0) / 1000, page_errors: errors.a, b_start_at_t_sim: tStart, b_llm_switch: llmOn};
  bLog.smoke = {case_id: caseId, page_errors: errors.b};
  fs.writeFileSync(`${out}/${caseId}.a-log.json`, JSON.stringify(aLog));
  fs.writeFileSync(`${out}/${caseId}.b-log.json`, JSON.stringify(bLog));
  console.log(caseId, 'session', session, 'A ticks', aLog.ticks.length, 'dropped', aLog.dropped, 'B ticks', bLog.ticks.length,
    'B actions', (bLog.actions || []).map(x => `${x.type}:${x.mode}`).join(','), 'B start t_sim', tStart.toFixed(2), 'errors', errors.a.length, errors.b.length);
} finally {
  await browser.close();
}

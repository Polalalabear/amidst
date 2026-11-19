// #597 comparison runner: replay one scripted hard case in the rules-only mode and in the LLM review modes (terra, sol),
// K times each, and save the A (GT, evaluation only) and B logs per run for scripts/live_hardset_compare.py.
//
//   LIVE_BASE=http://127.0.0.1:<port> OUT=<dir> node measure/hardset_compare.mjs <case[,case...]|all> [--modes rule,terra,sol] [--k 3]
//
// Same flow as measure/hardset_smoke.mjs (not modified: #608/#617 are changing it): headless Chrome, A runs ?script=<case>,
// B (?role=system) starts red-top tracking as soon as it has A's session. The only difference is that this runner sets the
// backend mode with POST /config before the pages open and checks GET /config says it is in force.
//
// Safety: LLM modes on the real provider need HARDSET_PAID_APPROVED_USD (see hardset_compare_lib.paidGate); the server's
// ApiGuard still enforces its own caps. Rule mode and --advisor-provider fake cost nothing. Nothing from the A log (GT) is
// sent anywhere: A and B only exchange what they already send in the normal live flow.
import fs from 'node:fs';
import path from 'node:path';
import {launch, BASE, sleep} from './lib.mjs';
import {HARDSET_ROUTES} from '../src/hardset_routes.mjs';
import {MODES, configBody, effectiveProblem, paidGate, planRuns, ledgerDelta} from './hardset_compare_lib.mjs';

const args = process.argv.slice(2);
const flag = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const caseArg = args[0]?.startsWith('--') ? undefined : args[0];
const cases = caseArg === 'all' ? Object.keys(HARDSET_ROUTES) : (caseArg || '').split(',').filter(Boolean);
const modes = flag('--modes', 'rule,terra,sol').split(',');
const k = Number(flag('--k', '3'));
const query = flag('--query', 'model=glb&w=320&h=180&fps=5');
const out = process.env.OUT || 'out';
if (!cases.length) throw new Error('usage: hardset_compare.mjs <case[,case...]|all> [--modes ...] [--k N]');
for (const c of cases) if (!HARDSET_ROUTES[c]) throw new Error(`unknown case ${c}`);
for (const m of modes) if (!MODES[m]) throw new Error(`unknown mode ${m}`);
fs.mkdirSync(out, {recursive: true});
const ledger = process.env.HARDSET_LEDGER;   // optional path of the server's ApiGuard usage.jsonl, for per-run spend
const readLedger = () => { try { return fs.readFileSync(ledger, 'utf8'); } catch { return ''; } };

async function getConfig() { return (await fetch(`${BASE}/config`)).json(); }

async function runOne({caseId, mode, rep, name}) {
  const before = await getConfig();
  const provider = before.advisor_provider || before.llm_switch?.provider || 'openai';
  const gate = paidGate(mode, provider, process.env);
  if (!gate.ok) throw new Error(gate.reason);
  const resp = await fetch(`${BASE}/config`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(configBody(mode))});
  if (!resp.ok) throw new Error(`CONFIG_REJECTED ${resp.status}`);
  const cfg = await getConfig();
  const problem = effectiveProblem(mode, cfg);
  if (problem) throw new Error(problem);
  const steps = HARDSET_ROUTES[caseId].steps.length;
  const ledgerBefore = ledger ? readLedger() : '';
  const wallStart = Date.now();
  const browser = await launch();
  try {
    const errors = {a: [], b: []};
    // Two pages of one browser context: A sends frames to B over a BroadcastChannel (same storage partition).
    const b = await browser.newPage();
    b.on('pageerror', e => errors.b.push(e.message));
    await b.goto(`${BASE}/?role=system`);
    await b.waitForFunction('window.__ready === true', {timeout: 120000});
    const a = await browser.newPage();
    a.on('pageerror', e => errors.a.push(e.message));
    await a.goto(`${BASE}/?script=${encodeURIComponent(caseId)}&${query}`);
    await a.waitForFunction('window.__ready === true', {timeout: 120000});
    const session = await a.evaluate(() => window.__log.session_id);
    await b.waitForFunction(s => window.__log.session_id === s, {timeout: 30000, polling: 100}, session);
    await b.click('[data-target-color="red"]');
    await b.click('#target-start');
    const tStart = await a.evaluate(() => window.__log.ticks.at(-1)?.t_sim ?? 0);
    await a.waitForFunction(n => {
      const done = (window.__log.script_events || []).filter(e => e.type === 'script_step_done');
      const last = window.__log.ticks.at(-1);
      return done.length >= n && last && last.t_sim >= done.at(-1).t_sim + 1;
    }, {timeout: 900000, polling: 500}, steps);
    await sleep(6000);   // an answer that is still on its way (<= 5 s timeout) lands in B's log
    const aLog = await a.evaluate(() => JSON.parse(JSON.stringify(window.__log)));
    const bLog = await b.evaluate(() => JSON.parse(JSON.stringify(window.__log)));
    const after = await getConfig();
    const meta = {case_id: caseId, mode, rep, session, query, wall_s: (Date.now() - wallStart) / 1000, b_start_at_t_sim: tStart,
      config_applied: {advisor: cfg.advisor, advisor_model: cfg.advisor_model, provider}, config_after_advisor: after.advisor, paid_approved_usd: process.env.HARDSET_PAID_APPROVED_USD ?? null,
      page_errors: errors, ...(ledger ? ledgerDelta(ledgerBefore, readLedger()) : {cost_usd: null, ledger: 'UNKNOWN (HARDSET_LEDGER not set)'})};
    fs.writeFileSync(path.join(out, `${name}.a-log.json`), JSON.stringify(aLog));
    fs.writeFileSync(path.join(out, `${name}.b-log.json`), JSON.stringify(bLog));
    fs.writeFileSync(path.join(out, `${name}.meta.json`), JSON.stringify(meta));
    console.log(name, 'session', session, 'A ticks', aLog.ticks.length, 'B ticks', bLog.ticks.length, 'errors', errors.a.length, errors.b.length,
      'calls', meta.calls ?? 'UNKNOWN', 'cost', meta.cost_usd ?? 'UNKNOWN');
  } finally {
    await browser.close();
    await fetch(`${BASE}/config`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(configBody('rule'))}).catch(() => {});
  }
}

for (const run of planRuns(cases, modes, k)) await runOne(run);

// #597 comparison runner, pure helpers (no browser, no network): modes, the /config request, the paid-run gate, run names,
// and the ApiGuard ledger delta. Tested by test/hardset_compare.test.mjs.
//
// Decision injection point (already in main, nothing new here): the backend's LiveDecider/Advisor (src/amidst/live_mode/advisor.py)
// is created by POST /config {advisor, advisor_model} (llm_switch.py decides what is effective). off = no decider, rules only.
// The provider is the server flag --advisor-provider (openai | fake). The runner only sets the mode before a run.

export const MODES = {
  rule: {advisor: 'off'},
  terra: {advisor: 'review', advisor_model: 'terra6.1'},
  sol: {advisor: 'review', advisor_model: 'sol6.1'},
};

export const MODE_NAMES = Object.keys(MODES);

export function configBody(mode) {
  if (!MODES[mode]) throw new Error(`UNKNOWN_MODE ${mode}`);
  return {...MODES[mode]};
}

// The mode a GET /config reply says is in force. null when it matches the request, else the reason it does not.
export function effectiveProblem(mode, cfg = {}) {
  const want = MODES[mode];
  if (!want) return `UNKNOWN_MODE ${mode}`;
  const got = cfg.advisor || 'off';
  if (want.advisor === 'off') return got === 'off' ? null : `ADVISOR_NOT_OFF (${got})`;
  if (got !== want.advisor) return `LLM_NOT_EFFECTIVE (${cfg.llm_switch?.reason_text || cfg.llm_switch?.reason || 'unknown reason'})`;
  if (cfg.advisor_model !== want.advisor_model) return `WRONG_MODEL (${cfg.advisor_model})`;
  return null;
}

// Fail closed: an LLM mode on the real provider runs only when the operator exported HARDSET_PAID_APPROVED_USD > 0
// (the amount the user approved in chat for #597; the server's ApiGuard enforces the actual caps). Rule mode and the fake
// provider (no network, no cost) are always allowed.
export function paidGate(mode, provider, env = {}) {
  if (mode === 'rule' || provider === 'fake') return {ok: true, reason: null};
  const usd = Number(env.HARDSET_PAID_APPROVED_USD);
  if (Number.isFinite(usd) && usd > 0) return {ok: true, reason: null, approved_usd: usd};
  return {ok: false, reason: 'PAID_RUN_NOT_APPROVED: set HARDSET_PAID_APPROVED_USD only after the user approved the amount in chat (AGENTS.md, D242)'};
}

export const runName = (caseId, mode, rep) => `${caseId}.${mode}.${rep}`;

export function planRuns(cases, modes, k) {
  const out = [];
  for (const c of cases) for (let rep = 1; rep <= k; rep++) for (const m of modes) out.push({caseId: c, mode: m, rep, name: runName(c, m, rep)});
  return out;
}

// Spend between two reads of the ApiGuard ledger (usage.jsonl text), counting only the live adjudication caller.
export function ledgerDelta(before = '', after = '', caller = 'live_adjudication') {
  const rows = text => text.split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  const a = rows(before).length;
  const fresh = rows(after).slice(a).filter(r => r.caller === caller);
  const charged = fresh.filter(r => r.outcome !== 'DENIED');
  return {calls: charged.length, denied: fresh.length - charged.length, cost_usd: charged.reduce((s, r) => s + (Number(r.est_cost_usd) || 0), 0),
    prompt_tokens: charged.reduce((s, r) => s + (Number(r.prompt_tokens) || 0), 0), completion_tokens: charged.reduce((s, r) => s + (Number(r.completion_tokens) || 0), 0)};
}

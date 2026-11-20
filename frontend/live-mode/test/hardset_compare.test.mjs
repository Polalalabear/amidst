import test from 'node:test';
import assert from 'node:assert/strict';
import {MODES, configBody, effectiveProblem, paidGate, planRuns, runName, ledgerDelta} from '../measure/hardset_compare_lib.mjs';
import {HARDSET_ROUTES} from '../src/hardset_routes.mjs';

test('each mode requests exactly what llm_switch accepts: advisor and advisor_model, nothing else', () => {
  assert.deepEqual(configBody('rule'), {advisor: 'off'});
  assert.deepEqual(configBody('terra'), {advisor: 'review', advisor_model: 'terra6.1'});
  assert.deepEqual(configBody('sol'), {advisor: 'review', advisor_model: 'sol6.1'});
  assert.throws(() => configBody('lead'), /UNKNOWN_MODE/);
  for (const m of Object.keys(MODES)) assert.ok(Object.keys(configBody(m)).every(key => ['advisor', 'advisor_model'].includes(key)));
});

test('effective check: a run whose mode did not take effect is refused, with the backend reason', () => {
  assert.equal(effectiveProblem('rule', {advisor: 'off'}), null);
  assert.match(effectiveProblem('rule', {advisor: 'review'}), /ADVISOR_NOT_OFF/);
  assert.equal(effectiveProblem('terra', {advisor: 'review', advisor_model: 'terra6.1'}), null);
  assert.match(effectiveProblem('terra', {advisor: 'off', llm_switch: {reason_text: '後台沒有核准付費呼叫'}}), /LLM_NOT_EFFECTIVE.*沒有核准/);
  assert.match(effectiveProblem('sol', {advisor: 'review', advisor_model: 'terra6.1'}), /WRONG_MODEL/);
});

test('paid gate fails closed; rule mode and the fake provider never need approval', () => {
  assert.equal(paidGate('rule', 'openai', {}).ok, true);
  assert.equal(paidGate('terra', 'fake', {}).ok, true);
  for (const env of [{}, {HARDSET_PAID_APPROVED_USD: ''}, {HARDSET_PAID_APPROVED_USD: '0'}, {HARDSET_PAID_APPROVED_USD: 'abc'}]) {
    const g = paidGate('sol', 'openai', env);
    assert.equal(g.ok, false); assert.match(g.reason, /PAID_RUN_NOT_APPROVED/);
  }
  assert.equal(paidGate('sol', 'openai', {HARDSET_PAID_APPROVED_USD: '3'}).ok, true);
});

test('run plan: K runs per case and mode, stable names the scorer parses', () => {
  const plan = planRuns(['H5-1', 'H1-1'], ['rule', 'terra', 'sol'], 3);
  assert.equal(plan.length, 18);
  assert.equal(runName('H5-1', 'terra', 2), 'H5-1.terra.2');
  assert.ok(plan.every(r => /^H\d-\d\.(rule|terra|sol)\.[1-3]$/.test(r.name)));
  assert.ok(plan.every(r => HARDSET_ROUTES[r.caseId]));
});

test('ledger delta counts only new live_adjudication rows and separates denials', () => {
  const row = o => JSON.stringify({caller: 'live_adjudication', outcome: 'OK', est_cost_usd: 0.003, prompt_tokens: 800, completion_tokens: 100, ...o});
  const before = [row({})].join('\n') + '\n';
  const after = before + [row({}), row({est_cost_usd: 0.002}), row({outcome: 'DENIED', est_cost_usd: null}), row({caller: 'nl_parse'})].join('\n') + '\n';
  const d = ledgerDelta(before, after);
  assert.equal(d.calls, 2); assert.equal(d.denied, 1);
  assert.ok(Math.abs(d.cost_usd - 0.005) < 1e-9); assert.equal(d.prompt_tokens, 1600);
  assert.deepEqual(ledgerDelta('', ''), {calls: 0, denied: 0, cost_usd: 0, prompt_tokens: 0, completion_tokens: 0});
});

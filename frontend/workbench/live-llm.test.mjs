import test from 'node:test';
import assert from 'node:assert/strict';
import {liveLlmView, liveLlmRequest, liveLlmHTML, loadLiveLlm, saveLiveLlm} from './live-llm.mjs';

const off = {reachable: true, advisor: 'off', llm_switch: {requested: 'off', effective: 'off', available: true, provider: 'openai', model: 'sol6.1', models: ['astra6', 'sol6.1', 'terra6.1']}};

test('default is off: unchecked, enabled, says 關閉; an unchecked box always requests off', () => {
  const v = liveLlmView(off);
  assert.equal(v.checked, false); assert.equal(v.disabled, false); assert.equal(v.text, 'LLM 決策：關閉');
  assert.doesNotMatch(liveLlmHTML(v), /data-live-llm="on" checked/);
  assert.deepEqual(liveLlmRequest(false, 'lead', null), {advisor: 'off'});
  assert.equal(liveLlmRequest(true, 'bogus', 'sol6.1').advisor, 'off');
  assert.deepEqual(Object.keys(liveLlmRequest(true, 'review', 'sol6.1')).sort(), ['advisor', 'advisor_model']);
});

test('live server unreachable: shown as unavailable with the reason, disabled, never looks on', () => {
  for (const resp of [{reachable: false, llm_switch: {reason_text: 'live 伺服器沒有啟動或連不上（127.0.0.1:8791）'}}, {reachable: false}, {reachable: true, advisor: 'review', llm_switch: {}, x: 1}].slice(0, 2)) {
    const v = liveLlmView(resp);
    assert.equal(v.checked, false); assert.equal(v.disabled, true); assert.equal(v.text, 'LLM 決策：不可用'); assert.ok(v.detail);
    const html = liveLlmHTML(v);
    assert.doesNotMatch(html, /data-live-llm="on" checked/); assert.match(html, /disabled/); assert.match(html, /不可用/);
  }
  assert.match(liveLlmView({reachable: false, llm_switch: {reason_text: '連不上'}}).detail, /連不上/);
  assert.equal(liveLlmView(null).checked, false);   // before the first answer: not on either
});

test('requested on but no usable provider: on, unavailable, rules, with the reason', () => {
  const v = liveLlmView({reachable: true, advisor: 'off', llm_switch: {requested: 'review', effective: 'off', reason_text: '後台沒有核准付費呼叫', models: []}});
  assert.equal(v.text, 'LLM 決策：開啟（不可用，使用規則）'); assert.equal(v.tone, 'fallback'); assert.match(v.detail, /沒有核准/);
});

test('fetch failures become unavailable, and the page text is escaped', async () => {
  const boom = async () => { throw new Error('refused'); };
  assert.equal((await loadLiveLlm(boom)).reachable, false);
  assert.equal((await saveLiveLlm({advisor: 'review'}, boom)).reachable, false);
  assert.equal((await loadLiveLlm(async () => ({ok: false}))).reachable, false);
  const html = liveLlmHTML(liveLlmView({reachable: false, llm_switch: {reason_text: '<img src=x onerror=bad()>'}}));
  assert.doesNotMatch(html, /<img/);
});

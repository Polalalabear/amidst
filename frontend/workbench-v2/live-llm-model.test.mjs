import test from 'node:test';
import assert from 'node:assert/strict';
import {liveLlmView, liveLlmRequest, loadLiveLlm, saveLiveLlm, liveBase, reduceConfig} from './live-llm-model.mjs';

const off = {reachable: true, advisor: 'off', llm_switch: {requested: 'off', effective: 'off', available: true, provider: 'openai', model: 'sol6.1', models: ['astra6', 'sol6.1', 'terra6.1']}};

test('default is off: unchecked, enabled, says 關閉; an unchecked box always requests off', () => {
  const v = liveLlmView(off);
  assert.equal(v.checked, false); assert.equal(v.disabled, false); assert.equal(v.text, 'LLM 決策：關閉');
  assert.deepEqual(liveLlmRequest(false, 'lead', null), {advisor: 'off'});
  assert.equal(liveLlmRequest(true, 'bogus', 'sol6.1').advisor, 'off');
  assert.deepEqual(Object.keys(liveLlmRequest(true, 'review', 'sol6.1')).sort(), ['advisor', 'advisor_model']);
});

test('live server unreachable: shown as unavailable with the reason, disabled, never looks on', () => {
  for (const resp of [{reachable: false, llm_switch: {reason_text: 'live 伺服器沒有啟動或連不上（127.0.0.1:8791）'}}, {reachable: false}, {reachable: true, advisor: 'review', llm_switch: {}, x: 1}].slice(0, 2)) {
    const v = liveLlmView(resp);
    assert.equal(v.checked, false); assert.equal(v.disabled, true); assert.equal(v.text, 'LLM 決策：不可用'); assert.ok(v.detail);
  }
  assert.match(liveLlmView({reachable: false, llm_switch: {reason_text: '連不上'}}).detail, /連不上/);
  assert.equal(liveLlmView(null).checked, false);   // before the first answer: not on either
});

test('requested on but no usable provider: on, unavailable, rules, with the reason', () => {
  const v = liveLlmView({reachable: true, advisor: 'off', llm_switch: {requested: 'review', effective: 'off', reason_text: '後台沒有核准付費呼叫', models: []}});
  assert.equal(v.text, 'LLM 決策：開啟（不可用，使用規則）'); assert.equal(v.tone, 'fallback'); assert.match(v.detail, /沒有核准/);
});

test('fetch failures and bad status become unavailable (never on)', async () => {
  const base = liveBase('', '8785');
  const boom = async () => { throw new Error('refused'); };
  for (const r of [await loadLiveLlm(boom, base), await saveLiveLlm({advisor: 'review'}, boom, base), await loadLiveLlm(async () => ({ok: false}), base)]) {
    assert.equal(r.reachable, false); assert.equal(r.llm_switch.effective, 'off'); assert.equal(r.llm_switch.available, false);
    assert.match(liveLlmView(r).text, /不可用/); assert.equal(liveLlmView(r).checked, false);
  }
  assert.equal(reduceConfig({advisor: 'off'}, '127.0.0.1:8791').reachable, false);   // an older live server without the switch
});

test('only local, unprivileged, non-demo ports are accepted as the live address', () => {
  assert.deepEqual(liveBase(''), {origin: 'http://127.0.0.1:8791', host: '127.0.0.1:8791'});
  assert.equal(liveBase('?live_port=8797').origin, 'http://127.0.0.1:8797');
  for (const q of ['?live_port=8785', '?live_port=80', '?live_port=99999', '?live_port=abc', '?live_port=8791.5', '?live_port=']) assert.equal(liveBase(q), null, q);
  assert.equal(liveBase('?live_port=8797', '8797'), null);   // not the page's own port
});

test('requests go only to the allowed live origin and carry only advisor and advisor_model; extra config fields are dropped', async () => {
  const base = liveBase('?live_port=8797'), calls = [];
  const fetchFn = async (url, init = {}) => { calls.push({url, method: init.method || 'GET', body: init.body}); return {ok: true, json: async () => ({advisor: 'off', device: 'mps', threads: 4, llm_switch: {requested: 'off', effective: 'off', secret: 'x', models: ['sol6.1']}})}; };
  const r = await saveLiveLlm({advisor: 'review', advisor_model: 'sol6.1', extra_field: 1, api_key: 'k'}, fetchFn, base);
  assert.deepEqual(calls.map((c) => c.url), ['http://127.0.0.1:8797/config', 'http://127.0.0.1:8797/config']);
  assert.deepEqual(JSON.parse(calls[0].body), {advisor: 'review', advisor_model: 'sol6.1'});
  assert.equal(calls[0].method, 'POST'); assert.equal(calls[1].method, 'GET');
  assert.ok(!('device' in r) && !('secret' in r.llm_switch));
  assert.deepEqual(JSON.parse((await (async () => { calls.length = 0; await saveLiveLlm({advisor: 'bogus'}, fetchFn, base); return calls[0]; })()).body), {advisor: 'off'});
  assert.equal((await loadLiveLlm(fetchFn, null)).llm_switch.reason, 'LIVE_URL_NOT_ALLOWED');
});

// 後台設定畫面（mountSettings）：用最小的 DOM 替身，看開關的初始狀態與連不上時的樣子。
function fakeDom() {
  const node = (tag) => ({ tag, children: [], attrs: {}, listeners: {}, className: '', textContent: '', disabled: false, id: '', style: {},
    setAttribute(k, v) { this.attrs[k] = v; }, append(...c) { this.children.push(...c); }, replaceChildren(...c) { this.children = c; },
    addEventListener(t, f) { this.listeners[t] = f; }, querySelectorAll(sel) { return all(this).filter((n) => n.tag === sel); } });
  const all = (n) => n.children.flatMap((c) => [c, ...all(c)]);
  globalThis.document = { createElement: node };
  return { node, all };
}
const tick = () => new Promise((r) => setTimeout(r, 0));

test('settings pane: default off, switch is enabled and not on; after load it shows 關閉', async () => {
  const { node, all } = fakeDom();
  const {mountSettings} = await import('./admin-ui.mjs');
  const box = node('div'); let saved = null;
  const storage = {getItem: () => null, setItem: () => {}};
  mountSettings(box, {getBootstrap: () => null, storage, liveLlm: {load: async () => off, save: async (b) => { saved = b; return off; }}});
  await tick(); await tick();
  const sw = all(box).find((n) => n.id === 'live-llm-switch'), st = all(box).find((n) => n.id === 'live-llm-status');
  assert.equal(sw.attrs['aria-checked'], 'false'); assert.equal(sw.disabled, false); assert.match(st.textContent, /LLM 決策：關閉/);
  sw.listeners.click(); await tick();   // the user turns it on: exactly one request, mode review
  assert.deepEqual(saved, {advisor: 'review', advisor_model: 'sol6.1'});
});

test('settings pane: live server unreachable shows 不可用, switch off and disabled', async () => {
  const { node, all } = fakeDom();
  const {mountSettings} = await import('./admin-ui.mjs');
  const box = node('div');
  mountSettings(box, {getBootstrap: () => null, storage: {getItem: () => null, setItem: () => {}},
    liveLlm: {load: async () => ({reachable: false, llm_switch: {reason_text: 'live 伺服器沒有啟動或連不上（127.0.0.1:8791）'}}), save: async () => { throw new Error('must not be called'); }}});
  await tick(); await tick();
  const sw = all(box).find((n) => n.id === 'live-llm-switch'), st = all(box).find((n) => n.id === 'live-llm-status');
  assert.equal(sw.attrs['aria-checked'], 'false'); assert.equal(sw.disabled, true);
  assert.match(st.textContent, /不可用/); assert.match(st.textContent, /8791/);
});

test('F3 #657: workbench LIVE switch can request agent mode', () => {
  assert.deepEqual(liveLlmRequest(true, 'agent'), {advisor: 'agent'});
  assert.deepEqual(liveLlmRequest(true, 'constructor'), {advisor: 'off'});
  const v = liveLlmView({reachable: true, advisor: 'agent', llm_switch: {requested: 'agent', effective: 'agent', provider: 'openai', model: 'terra6.1', models: []}});
  assert.equal(v.mode, 'agent'); assert.match(v.text, /Agent 決策/);
});

// Epic D path (b) frontend tests (spec §9 T-N1, T-N2, T-E3 logic part). Pure model + a tiny fake DOM; the real browser is
// covered by tests/browser/core-preview/nl-e2e.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {
  buildNlRequest, validateNlResponse, describeNlResponse, requestNlParse, mountNlInput, reasonText, NL_ROUTE, NL_RESPONSE_SCHEMA,
} from './nl-input.mjs';

const GT_READ = ['gt', '_read'].join('');
const run = {scene_id: 'SC', run_id: 'RUN'};
const catalog = {regions: [{value: 'R_A', label: '合成區 A'}], classes: ['person', 'car'], colors: ['red', 'blue'], aliases: {人: 'person'}};
const labels = {evidence: 'EXPLORATORY', identity_verdict: 'UNCONFIRMED', [GT_READ]: false};
const provider = (extra = {}) => ({kind: 'RECORDED', model: 'SYNTHETIC_FIXTURE', recorded: true, synthetic_fixture: true, latency_ms: null, ...extra});
const response = (extra = {}) => ({
  schema_version: NL_RESPONSE_SCHEMA, status: 'PARSED', kind: 'search', form: {start: '13:00:00', end: '13:30:00', regionIds: ['R_A'], classLabel: 'person', colorLabel: ''},
  missing: [], warnings: [], ignored_terms: [], decided_by: 'LLM', fallback_reason: null, manual_reason: null, provider: provider(),
  requires_confirmation: true, executed: false, labels, trace: {steps: [{step: 0, decided_by: 'LLM', arguments: {a: 1}, result_summary: 'x', fallback_reason: null, llm_call: {latency_ms: 1200}}]}, ...extra,
});

test('request carries only the whitelisted keys and refuses empty / oversized / not-ready input', () => {
  const r = buildNlRequest({run, session: 'S', kind: 'search', text: ' 下午一點 '});
  assert.deepEqual(Object.keys(r).sort(), ['kind', 'run_id', 'scene_id', 'schema_version', 'session_ref', 'text']);
  assert.equal(r.text, '下午一點');
  assert.throws(() => buildNlRequest({run, session: 'S', kind: 'search', text: '  '}), /INVALID_REQUEST/);
  assert.throws(() => buildNlRequest({run, session: 'S', kind: 'search', text: 'x'.repeat(201)}), /INVALID_REQUEST/);
  assert.throws(() => buildNlRequest({run: null, session: 'S', kind: 'search', text: 'x'}), /SOURCE_NOT_READY/);
  assert.throws(() => buildNlRequest({run, session: 'S', kind: 'other', text: 'x'}), /INVALID_REQUEST/);
});

test('validateNlResponse accepts a good parse and rejects anything off-menu, unconfirmed, executed or private', () => {
  assert.deepEqual(validateNlResponse(response(), 'search', catalog), {ok: true, code: null});
  assert.equal(validateNlResponse(response(), 'track', catalog).code, 'BAD_RESPONSE');                       // wrong kind
  assert.equal(validateNlResponse(response({executed: true}), 'search', catalog).code, 'BAD_RESPONSE');       // must never be pre-executed
  assert.equal(validateNlResponse(response({requires_confirmation: false}), 'search', catalog).code, 'BAD_RESPONSE');
  assert.equal(validateNlResponse(response({labels: {...labels, evidence: 'CONFIRMED'}}), 'search', catalog).code, 'BAD_RESPONSE');
  assert.equal(validateNlResponse(response({actor_id: 'x'}), 'search', catalog).code, 'BAD_RESPONSE');       // private key anywhere
  assert.equal(validateNlResponse(response({form: {...response().form, classLabel: 'laptop'}}), 'search', catalog).code, 'NOT_IN_MENU');
  assert.equal(validateNlResponse(response({form: {...response().form, regionIds: ['R_Z']}}), 'search', catalog).code, 'NOT_IN_MENU');
  assert.equal(validateNlResponse(response({form: {...response().form, colorLabel: 'pink'}}), 'search', catalog).code, 'NOT_IN_MENU');
  assert.deepEqual(validateNlResponse(response({status: 'FALLBACK_MANUAL', form: null}), 'search', catalog), {ok: true, code: null});
  assert.equal(validateNlResponse(response({status: 'FALLBACK_MANUAL'}), 'search', catalog).code, 'BAD_RESPONSE'); // a manual fallback must not carry a form
  assert.equal(validateNlResponse(null, 'search', catalog).code, 'BAD_RESPONSE');
});

test('T-N1: three decision sources render as three different chips with provider, model and label chips', () => {
  const llm = describeNlResponse(response(), catalog), rule = describeNlResponse(response({decided_by: 'RULE', provider: {kind: 'NONE', model: null}}), catalog);
  const fb = describeNlResponse(response({decided_by: 'RULE_FALLBACK', fallback_reason: 'TIMEOUT'}), catalog);
  const manual = describeNlResponse(response({status: 'FALLBACK_MANUAL', form: null, manual_reason: 'UNSUPPORTED_CONDITION', fallback_reason: 'UNSUPPORTED_CONDITION', decided_by: 'RULE_FALLBACK'}), catalog);
  assert.deepEqual([llm.decision.source, rule.decision.source, fb.decision.source, manual.decision.source], ['LLM', 'RULE', 'FALLBACK', 'FALLBACK']);
  assert.equal(llm.decision.text, 'LLM 決定'); assert.equal(rule.decision.text, '規則'); assert.equal(fb.decision.text, '退回規則：模型逾時');
  assert.equal(manual.decision.text, '退回手動選單：句子含有目前不支援的條件'); assert.equal(manual.state, 'MANUAL');
  assert.equal(new Set([llm, rule, fb].map(v => v.decision.source)).size, 3);
  assert.ok(llm.providerChips.some(c => c.text === '錄製重播') && llm.providerChips.some(c => c.text === 'SYNTHETIC_FIXTURE' && c.cls === 'is-synthetic') && llm.providerChips.some(c => c.text === 'EXPLORATORY'));
  assert.ok(rule.providerChips.some(c => c.text === '未使用模型'));
  const real = describeNlResponse(response({provider: provider({model: 'qwen3:1.7b-q4_K_M', synthetic_fixture: false})}), catalog);
  assert.ok(real.providerChips.some(c => c.text === 'qwen3:1.7b-q4_K_M') && !real.providerChips.some(c => c.text === 'SYNTHETIC_FIXTURE'));
  assert.ok(describeNlResponse(response({provider: {kind: 'OPENAI', model: 'm'}}), catalog).providerChips.some(c => c.text.startsWith('OpenAI')));
  assert.equal(llm.summary, '特徵：人物　·　地點：合成區 A　·　時間：13:00:00 → 13:30:00');
  assert.equal(llm.steps[0].source, 'LLM'); assert.equal(fb.steps[0].source, 'LLM');
  assert.match(reasonText('NOPE'), /UNKNOWN/);
});

test('requestNlParse: ok, http error code, bad json, network error and a hung server (CLIENT_TIMEOUT)', async () => {
  const fetchOk = async (url, init) => { assert.equal(url, NL_ROUTE); assert.equal(init.method, 'POST'); return {ok: true, text: async () => JSON.stringify(response())}; };
  assert.equal((await requestNlParse({fetchImpl: fetchOk, request: {}, timeoutMs: 1000})).ok, true);
  const http = await requestNlParse({fetchImpl: async () => ({ok: false, status: 422, text: async () => '{"error_code":"INVALID_REQUEST"}'}), request: {}, timeoutMs: 1000});
  assert.deepEqual(http, {ok: false, code: 'INVALID_REQUEST'});
  assert.equal((await requestNlParse({fetchImpl: async () => ({ok: true, text: async () => 'nope'}), request: {}, timeoutMs: 1000})).code, 'BAD_RESPONSE');
  assert.equal((await requestNlParse({fetchImpl: async () => { throw new TypeError('x'); }, request: {}, timeoutMs: 1000})).code, 'NETWORK_ERROR');
  const hung = await requestNlParse({fetchImpl: (u, init) => new Promise((_, rej) => init.signal.addEventListener('abort', () => rej(new Error('aborted')))), request: {}, timeoutMs: 30});
  assert.deepEqual(hung, {ok: false, code: 'CLIENT_TIMEOUT'});
});

// ---- tiny fake DOM, just enough for mountNlInput -------------------------------------------------------------------
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.attrs = {}; this.listeners = {}; this.hidden = false; this.disabled = false; this.value = ''; this._text = ''; this.className = ''; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  append(...k) { this.children.push(...k); } prepend(...k) { this.children.unshift(...k); }
  replaceChildren(...k) { this.children = k; this._text = ''; } remove() { this.removed = true; }
  setAttribute(k, v) { this.attrs[k] = v; } get id() { return this.attrs.id; } set id(v) { this.attrs.id = v; }
  get firstChild() { return this.children[0]; }
  addEventListener(t, f) { (this.listeners[t] ??= []).push(f); }
  async click() { if (this.disabled) return; for (const f of this.listeners.click ?? []) await f({}); }
  find(pred, out = []) { if (pred(this)) out.push(this); for (const c of this.children) c.find?.(pred, out); return out; }
}
const fakeDoc = () => ({createElement: t => new Node(t), head: new Node('head'), querySelector: () => null});
const mount = (kind, fetchImpl, over = {}) => {
  const doc = fakeDoc(), win = new Node('aside'), submitted = [];
  const w = {kind, form: {regions: new Set(), classLabel: '', colorLabel: ''}, start: new Node('input'), end: new Node('input')};
  let refreshed = 0;
  const ctx = {store: {getState: () => ({activeRun: run})}, api: {getSession: () => 'S'}, coreCatalog: () => catalog, url: 'http://x/?nl_timeout_ms=200', ...over};
  const h = mountNlInput({ctx, doc, win, w, refresh: () => { refreshed++; }, submit: async x => { submitted.push(x); }, fetchImpl});
  const ids = id => win.find(n => n.id === id)[0];
  return {h, w, win, submitted, ids, refreshed: () => refreshed, doc};
};
const okFetch = (resp, seen = []) => async (u, init) => { seen.push(JSON.parse(init.body)); return {ok: true, text: async () => JSON.stringify(resp)}; };

test('T-N2: parsing only fills the form; the shell submit runs once, and only from the confirm button', async () => {
  const seen = [], t = mount('search', okFetch(response(), seen));
  t.h.input.value = '下午一點到一點半 合成區 A 的人'; await t.h.parse();
  assert.equal(seen.length, 1); assert.equal(seen[0].kind, 'search');
  assert.equal(t.w.start.value, '13:00:00'); assert.equal(t.w.end.value, '13:30:00'); assert.deepEqual([...t.w.form.regions], ['R_A']); assert.equal(t.w.form.classLabel, 'person');
  assert.ok(t.refreshed() >= 1); assert.equal(t.submitted.length, 0, 'no query before confirm');
  const confirm = t.ids('ui-nl-search-confirm'); assert.equal(confirm.disabled, false);
  assert.equal(t.ids('ui-nl-search-result').dataset.source, 'LLM');
  await confirm.click(); assert.equal(t.submitted.length, 1); assert.equal(t.submitted[0], t.w);
  await confirm.click(); assert.equal(t.submitted.length, 1, 'confirm is single-use');
});

test('incomplete parse keeps confirm disabled until the missing field is filled by hand; cancel clears', async () => {
  const t = mount('search', okFetch(response({form: {start: '', end: '', regionIds: [], classLabel: 'person', colorLabel: 'red'}, missing: ['time']})));
  t.h.input.value = '追蹤紅衣服的人'; await t.h.parse();
  assert.equal(t.ids('ui-nl-search-confirm').disabled, true); assert.match(t.ids('ui-nl-search-result').textContent, /尚缺：時間/);
  await t.ids('ui-nl-search-confirm').click(); assert.equal(t.submitted.length, 0);
  await t.ids('ui-nl-search-cancel').click(); assert.equal(t.ids('ui-nl-search-result').hidden, true); assert.equal(t.submitted.length, 0);
  const tr = mount('track', okFetch(response({kind: 'track', form: {start: '', end: '', regionIds: [], classLabel: 'person', colorLabel: 'red'}})));
  tr.h.input.value = '追蹤紅衣服的人'; await tr.h.parse();
  assert.equal(tr.ids('ui-nl-track-confirm').disabled, false, 'track needs only a feature; blank time = now');
});

test('failures fall back to the manual menu with a reason and never touch the form or submit', async () => {
  const cases = [
    [async () => { throw new TypeError('down'); }, 'NETWORK_ERROR'],
    [async () => ({ok: false, status: 503, text: async () => '{"error_code":"SYNTHETIC_FIXTURE_ERROR"}'}), 'SYNTHETIC_FIXTURE_ERROR'],
    [okFetch(response({executed: true})), 'BAD_RESPONSE'],
    [okFetch(response({form: {...response().form, classLabel: 'laptop'}})), 'NOT_IN_MENU'],
    [(u, init) => new Promise((_, rej) => init.signal.addEventListener('abort', () => rej(new Error('aborted')))), 'CLIENT_TIMEOUT'],
  ];
  for (const [fetchImpl, code] of cases) {
    const t = mount('search', fetchImpl, {url: 'http://x/?nl_timeout_ms=100'});
    t.h.input.value = '下午一點到一點半 合成區 A 的人'; await t.h.parse();
    const r = t.ids('ui-nl-search-result');
    assert.equal(r.dataset.state, 'MANUAL', code); assert.equal(r.dataset.source, 'FALLBACK');
    assert.match(r.textContent, /退回手動選單/); assert.equal(t.w.start.value, ''); assert.equal(t.w.form.classLabel, ''); assert.equal(t.submitted.length, 0);
    assert.equal(t.ids('ui-nl-search-confirm'), undefined, 'no confirm on a fallback');
  }
  const t = mount('search', okFetch(response()), {store: {getState: () => ({activeRun: null})}});
  t.h.input.value = 'x'; await t.h.parse(); assert.match(t.ids('ui-nl-search-result').textContent, /來源或 session 未就緒/);
});

test('server-side manual fallback is shown with its reason and chips', async () => {
  const t = mount('search', okFetch(response({status: 'FALLBACK_MANUAL', form: null, manual_reason: 'UNSUPPORTED_CONDITION', fallback_reason: 'UNSUPPORTED_CONDITION', decided_by: 'RULE_FALLBACK'})));
  t.h.input.value = '戴眼鏡的人'; await t.h.parse();
  const r = t.ids('ui-nl-search-result'); assert.equal(r.dataset.state, 'MANUAL'); assert.match(r.textContent, /句子含有目前不支援的條件/); assert.match(r.textContent, /SYNTHETIC_FIXTURE/);
});

test('module boundaries: no GT words, no key access, no direct core calls; the shell only adds a mount point', () => {
  const src = readFileSync(new URL('nl-input.mjs', import.meta.url), 'utf8'), shell = readFileSync(new URL('ui-shell.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(src, /localStorage|OPENAI_API_KEY|api_key|Authorization|q_core_search|q_core_track|submitCore/i);
  assert.match(shell, /mountNlInput\(\{ctx, doc, win, w, refresh: renderCatalog, submit: submitQuery\}\)/);
  assert.equal((shell.match(/mountNlInput/g) ?? []).length, 2);   // import + one mount line
});

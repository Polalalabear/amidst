// 2026-11-17: 「開始追蹤」 showed UNKNOWN · FORBIDDEN_DATA_SCOPE after 8785 restarted under an open page. The server keeps
// sessions in memory, so the page's session_ref was stale. q-api renews once and resends; a second refusal still surfaces.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createQApi} from './q-api.mjs';
import {failureText} from './core-search-track-model.mjs';

const reply = {schema_version: 'q-demo.nl-query-parse.v1', action: '查找', location: [], target: ['person'], time: null, unrecognized: [], parser: 'RULES', latency_ms: 1, cost_usd: 0, fallback_trail: []};
function server({alwaysRefuse = false} = {}) {
  let n = 0; const valid = new Set(); const sent = [];
  const fetchImpl = async (path, options) => {
    const body = JSON.parse(options.body);
    if (path === '/api/session') { const t = `S${++n}`; valid.add(t); return {ok: true, text: async () => JSON.stringify({session_ref: t, role: 'research'})}; }
    sent.push(body.session_ref);
    if (alwaysRefuse || !valid.has(body.session_ref)) return {ok: false, status: 403, text: async () => '{"error_code":"FORBIDDEN_DATA_SCOPE"}'};
    return {ok: true, text: async () => JSON.stringify(reply)};
  };
  return {fetchImpl, sent, restart() { valid.clear(); }};
}

test('a stale session (server restarted) is renewed once and the same call is resent', async () => {
  const s = server(); const api = createQApi({fetchImpl: s.fetchImpl});
  await api.createSession(); assert.equal(api.getSession(), 'S1');
  s.restart();
  const r = await api.nlParse({scene_id: 'sc', run_id: 'ru'}, '找人', 'RULES');
  assert.equal(r.ok, true);
  assert.deepEqual(s.sent, ['S1', 'S2']);
  assert.equal(api.getSession(), 'S2');
});

test('a refusal that survives renewal is reported, with plain-language text', async () => {
  const s = server({alwaysRefuse: true}); const api = createQApi({fetchImpl: s.fetchImpl});
  await api.createSession();
  const r = await api.nlParse({scene_id: 'sc', run_id: 'ru'}, '找人', 'RULES');
  assert.equal(r.ok, false); assert.equal(r.error.code, 'FORBIDDEN_DATA_SCOPE');
  assert.deepEqual(s.sent, ['S1', 'S2']);   // exactly one retry
  assert.doesNotMatch(failureText('FORBIDDEN_DATA_SCOPE'), /UNKNOWN/);
  assert.match(failureText('FORBIDDEN_DATA_SCOPE'), /重試後仍被拒/);   // #578 P3-2: it is shown only after the one retry
  assert.match(failureText('AUTOMATIC_SEED_PRESET_ONLY'), /人物/);
});

test('track refusal: the masked FORBIDDEN_DATA_SCOPE names the form condition the replay preset does not accept', async () => {
  const {trackRefusalText} = await import('./core-search-track-model.mjs');
  const red = trackRefusalText('FORBIDDEN_DATA_SCOPE', {classLabel: 'person', colorLabel: 'red', start: '14:10:00', regionIds: []}, '14:10:00', c => (c === 'red' ? '紅色' : c));
  assert.match(red, /人物、不指定顏色、從錄影開頭開始/); assert.match(red, /紅色/); assert.doesNotMatch(red, /開始時間/);
  assert.match(trackRefusalText('FORBIDDEN_DATA_SCOPE', {classLabel: 'person', start: '14:10:05'}, '14:10:00'), /不是錄影開頭（14:10:00）/);
  assert.equal(trackRefusalText('FORBIDDEN_DATA_SCOPE', {classLabel: 'person', start: '14:10:00'}, '14:10:00'), null);   // nothing in the form explains it: generic text
  assert.equal(trackRefusalText('TIME_SCOPE', {colorLabel: 'red'}, null), null);
});

test('raw code note: the three masked codes get their code back as small print (#578 P3-2)', async () => {
  const {rawCodeNote, setRefusalFeedback} = await import('./core-search-track-model.mjs');
  for (const c of ['FORBIDDEN_DATA_SCOPE', 'AUTOMATIC_SEED_PRESET_ONLY', 'TIME_SCOPE']) assert.equal(rawCodeNote(c), c);
  assert.equal(rawCodeNote('Q_RESPONSE_EXPIRED'), null); assert.equal(rawCodeNote(undefined), null);
  const made = [];
  const doc = {createElement: () => { const n = {className: '', textContent: ''}; made.push(n); return n; }};
  const el = {ownerDocument: doc, textContent: '', appended: [], append(n) { this.appended.push(n); }};
  setRefusalFeedback(el, '文字', 'TIME_SCOPE');
  assert.equal(el.textContent, '文字'); assert.equal(el.appended[0].textContent, ' · TIME_SCOPE');
  const el2 = {ownerDocument: doc, textContent: '', appended: [], append(n) { this.appended.push(n); }};
  setRefusalFeedback(el2, '文字', 'Q_RESPONSE_EXPIRED'); assert.equal(el2.appended.length, 0);
});

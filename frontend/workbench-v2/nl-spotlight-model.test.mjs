import test from 'node:test';
import assert from 'node:assert/strict';
import {chipsFromParse, planFromParse, createSpotlight, PARSER_MODES, UNRECOGNIZED_LABEL} from './nl-spotlight-model.mjs';
import {loadSettings, normalizeSettings, DEFAULT_SETTINGS} from './ui-model.mjs';

const run = {supported_classes: {class_labels: ['person', 'car'], aliases: {人: 'person', 車: 'car'}, color_vocabulary: {labels: ['red', 'blue']}},
  region_catalog: {regions: [{region_id: 'R1', label: '西入口'}, {region_id: 'R2', label: '東入口'}]},
  clock_mapping: {wall_origin: '2026-11-01T13:00:00+08:00', t0_us: 0, rate: 1, source_duration_us: 50e6}};
const parse = (o = {}) => ({action: '追蹤', location: ['R1'], target: ['person', 'red'], time: {start: 10, end: 30}, unrecognized: [], ...o});

test('chips show action, region label, class, colour, time and 未辨識 pieces', () => {
  const chips = chipsFromParse(parse({unrecognized: ['戴眼鏡']}), run);
  assert.deepEqual(chips.map(c => c.kind), ['action', 'location', 'target', 'target', 'time', 'unrecognized']);
  assert.equal(chips[1].text, '西入口'); assert.equal(chips[2].text, '人物'); assert.equal(chips[3].text, '紅色'); assert.equal(chips[4].text, '0:00:10 – 0:00:30');
  assert.equal(chips[5].text, `${UNRECOGNIZED_LABEL}：戴眼鏡`);
  assert.deepEqual(chipsFromParse(null, run), []);
});

test('plan: search fills regions, class, colour and wall-clock times; track drops regions', () => {
  const s = planFromParse(parse({action: '查找'}), run);
  assert.deepEqual([s.kind, s.screen, s.regionIds, s.classLabel, s.colorLabel, s.start, s.end], ['search', 'case1', ['R1'], 'person', 'red', '13:00:10', '13:00:30']);
  const t = planFromParse(parse(), run);
  assert.deepEqual([t.kind, t.screen, t.regionIds, t.notes.length], ['track', 'case2', [], 1]);
});

test('plan: no action cue means search, in every tab; colour alone means person; unsupported track class is not filled', () => {
  assert.equal(planFromParse(parse({action: null}), run, 'case2').kind, 'search');   // 2026-11-17: the 追蹤 tab no longer swallows searches
  assert.equal(planFromParse(parse({action: null}), run, 'case1').kind, 'search');
  assert.equal(planFromParse(parse({action: null}), run, null).kind, 'search');
  assert.equal(planFromParse(parse({action: '查找', target: ['blue']}), run).classLabel, 'person');
  const car = planFromParse(parse({target: ['car'], location: []}), run);
  assert.equal(car.classLabel, '') ; assert.match(car.notes.join(), /只支援人物/);
});

test('plan: no time keeps times untouched; unrecognized goes into notes', () => {
  const p = planFromParse(parse({time: null, unrecognized: ['x']}), run);
  assert.equal(p.start, null); assert.equal(p.end, null); assert.ok(p.notes.some(n => n.startsWith('未辨識')));
});

test('controller: open / toggle / close and Esc-style reset', () => {
  const seen = []; const c = createSpotlight({parsePreview: async () => ({}), parseFinal: async () => ({}), apply() {}, onChange: s => seen.push(s.open)});
  c.toggle(); assert.equal(c.state.open, true); c.setText('abc'); c.close(); assert.equal(c.state.open, false); assert.equal(c.state.text, '');
  c.toggle(); assert.equal(c.state.open, true); assert.deepEqual(seen.filter((v, i) => v !== seen[i - 1]), [true, false, true]);
});

test('controller: preview chips follow typing, stale answers are dropped, Enter applies and closes', async () => {
  const applied = []; const calls = []; let release;
  const c = createSpotlight({
    parsePreview: text => { calls.push(text); return text === 'slow' ? new Promise(r => { release = () => r({chips: [{kind: 'action', text: 'OLD'}], parser: 'RULES'}); }) : Promise.resolve({chips: [{kind: 'action', text: text}], parser: 'RULES', latency_ms: 1, cost_usd: 0}); },
    parseFinal: async text => ({chips: [{kind: 'action', text}], parse: {text}, parser: 'RULES'}), apply: (p, r, o) => applied.push([p, r.parser, o]),
  });
  c.open(); c.setText('slow'); c.setText('fast'); await new Promise(r => setTimeout(r, 0)); release(); await new Promise(r => setTimeout(r, 0));
  assert.deepEqual(c.state.chips, [{kind: 'action', text: 'fast'}]);
  assert.equal(await c.submit(), true); assert.deepEqual(applied, [[{text: 'fast'}, 'RULES', {kind: 'search', run: true}]]); assert.equal(c.state.open, false);
});

test('controller: empty text does nothing; a failed parse keeps the bar open and shows the error', async () => {
  const c = createSpotlight({parsePreview: async () => ({chips: []}), parseFinal: async () => { throw new Error('PARSE_FAILED'); }, apply() { throw new Error('must not apply'); }});
  c.open(); assert.equal(await c.submit(), false); c.setText('x'); assert.equal(await c.submit(), false);
  assert.equal(c.state.open, true); assert.equal(c.state.error, 'PARSE_FAILED'); assert.equal(c.state.status, 'error');
});

test('settings: nlParser defaults to the fixed-pattern parser and normalizes unknown values', () => {
  assert.equal(DEFAULT_SETTINGS.nlParser, 'RULES');
  assert.equal(normalizeSettings({nlParser: 'API'}).nlParser, 'API');
  assert.equal(normalizeSettings({nlParser: 'LOCAL'}).nlParser, 'LOCAL');
  assert.equal(normalizeSettings({nlParser: 'gpt'}).nlParser, 'RULES');
  assert.equal(loadSettings(null).nlParser, 'RULES');
  assert.deepEqual(PARSER_MODES.map(m => m[0]), ['RULES', 'LOCAL', 'API']);
});

test('q-api nlParse posts the run scope, never a key, and validates the fixed shape', async () => {
  const {createQApi} = await import('./q-api.mjs');
  const sent = [];
  const reply = {schema_version: 'q-demo.nl-query-parse.v1', action: '查找', location: [], target: ['person'], time: null, unrecognized: [], parser: 'RULES', latency_ms: 1, cost_usd: 0, fallback_trail: []};
  const fetchImpl = async (path, options) => {
    if (path === '/api/session') return {ok: true, text: async () => JSON.stringify({session_ref: 'S1', role: 'research'})};
    sent.push([path, JSON.parse(options.body)]);
    return {ok: true, text: async () => JSON.stringify(reply)};
  };
  const api = createQApi({fetchImpl}); await api.createSession();
  const r = await api.nlParse({scene_id: 'sc', run_id: 'ru'}, '找人', 'API');
  assert.equal(r.ok, true); assert.equal(r.data.parser, 'RULES');
  assert.deepEqual(sent[0], ['/api/nl_query_parse', {session_ref: 'S1', context: {scene_id: 'sc', run_ids: ['ru']}, text: '找人', mode: 'API'}]);
  assert.equal((await api.nlParse({scene_id: 'sc', run_id: 'ru'}, '找人', 'BOGUS')).ok, false);
  const bad = createQApi({fetchImpl: async () => ({ok: true, text: async () => '{"schema_version":"x"}'})});
  assert.equal((await bad.nlParse({scene_id: 'sc', run_id: 'ru'}, 'x')).ok, false);
});

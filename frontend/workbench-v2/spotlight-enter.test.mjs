// 2026-11-17 user report: Enter in the top search bar enters the highlighted result and runs it; typing in the 追蹤 tab
// reaches 查找. Model-level (no DOM harness in this folder).
import test from 'node:test';
import assert from 'node:assert/strict';
import {createSpotlight, optionsFromParse, planFromParse, chipsFromParse} from './nl-spotlight-model.mjs';

const run = {supported_classes: {class_labels: ['person'], aliases: {人: 'person'}, color_vocabulary: {labels: ['red']}},
  region_catalog: {regions: [{region_id: 'R1', label: '西入口'}]}, clock_mapping: {wall_origin: '2026-11-01T13:00:00+08:00', t0_us: 0, rate: 1, source_duration_us: 50e6}};
const parse = o => ({action: null, location: ['R1'], target: ['person', 'red'], time: null, unrecognized: [], ...o});
const tick = () => new Promise(r => setTimeout(r, 0));
const make = (p, applied) => createSpotlight({
  parsePreview: async () => ({parse: p, chips: chipsFromParse(p, run), parser: 'RULES'}),
  parseFinal: async () => ({parse: p, chips: chipsFromParse(p, run), parser: 'RULES'}),
  apply: (pp, r, opts) => applied.push(opts),
});

test('rows: search first without a cue, track first with 追蹤; detail lists the parsed conditions', () => {
  const plain = optionsFromParse(parse(), chipsFromParse(parse(), run));
  assert.deepEqual(plain.map(o => o.kind), ['search', 'track']);
  assert.equal(plain[0].detail, '西入口 · 人物 · 紅色');
  assert.equal(plain[1].detail, '人物 · 紅色');   // tracking ignores places
  assert.deepEqual(optionsFromParse(parse({action: '追蹤'}), []).map(o => o.kind), ['track', 'search']);
  assert.deepEqual(optionsFromParse(null), []);
});

test('Enter without arrow keys enters the first row and asks for the query to run', async () => {
  const applied = []; const c = make(parse(), applied);
  c.open(); c.setText('紅衣的人 西入口'); await tick();
  assert.equal(c.state.selected, 0);
  assert.equal(await c.submit(), true);
  assert.deepEqual(applied, [{kind: 'search', run: true}]);
  assert.equal(c.state.open, false);
});

test('ArrowDown highlights the next row (wrapping) and Enter enters that row', async () => {
  const applied = []; const c = make(parse(), applied);
  c.open(); c.setText('紅衣的人'); await tick();
  c.move(1); assert.equal(c.state.selected, 1);
  c.move(1); assert.equal(c.state.selected, 0);
  c.move(-1); assert.equal(c.state.selected, 1);
  await c.submit();
  assert.deepEqual(applied, [{kind: 'track', run: true}]);
});

test('typing again drops the manual pick; Esc-style close resets rows', async () => {
  const applied = []; const c = make(parse(), applied);
  c.open(); c.setText('a'); await tick(); c.move(1); c.setText('ab'); await tick();
  assert.equal(c.state.selected, 0);
  c.close(); assert.deepEqual(c.state.options, []); assert.equal(c.state.selected, 0);
});

test('a sentence typed in the 追蹤 tab plans the 查找 window with its conditions', () => {
  const p = planFromParse(parse(), run, 'case2');
  assert.deepEqual([p.kind, p.screen, p.regionIds, p.classLabel, p.colorLabel], ['search', 'case1', ['R1'], 'person', 'red']);
  assert.equal(planFromParse(parse(), run, 'case2', 'track').kind, 'track');       // explicit row pick still wins
  assert.equal(planFromParse(parse({action: '追蹤'}), run, 'case1').kind, 'track');  // explicit cue still wins
});

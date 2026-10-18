import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { RAIL_STORAGE_KEY, loadRailPref, saveRailPref, sectionsForMode, timeReadout } from './shell-view.mjs';
import { initialState, reduce } from './store.mjs';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const read = (name) => readFileSync(new URL(name, import.meta.url), 'utf8');

const memory = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), m }; };

test('rail preference: only pinned/collapsed are stored; floating is not; storage failures are swallowed', () => {
  const st = memory();
  assert.equal(loadRailPref(st), 'pinned');
  saveRailPref('rail', st); assert.equal(st.m.get(RAIL_STORAGE_KEY), 'rail'); assert.equal(loadRailPref(st), 'rail');
  saveRailPref('overlay', st); assert.equal(st.m.get(RAIL_STORAGE_KEY), 'rail');
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(loadRailPref(broken), 'pinned');
  assert.doesNotThrow(() => saveRailPref('pinned', broken));
  assert.equal(loadRailPref(null), 'pinned');
});

test('time readout: no run, on a sample, between samples, out of range', () => {
  assert.equal(timeReadout(initialState()).status, 'NO_RUN');
  const run = { run_id: 'R', fps: 5, duration_s: 20 };
  const at = (tMs) => timeReadout({ ...initialState(), run, tMs });
  assert.deepEqual(at(12400), { now: '12.40 s', total: '/ 20 s', sub: '影格 #062 · sample_age +0.00 s', status: 'IN_RANGE' });
  assert.equal(at(12470).sub, '影格 #062 · sample_age +0.07 s');
  assert.equal(at(20000).status, 'OUT_OF_RANGE');
});

test('panel sections follow the mode', () => {
  assert.deepEqual(sectionsForMode('browse'), ['evidence', 'layers', 'prov']);
  assert.ok(sectionsForMode('find').includes('find'));
  assert.ok(sectionsForMode('demo').includes('demo'));
  assert.deepEqual(sectionsForMode('nope'), sectionsForMode('browse'));
});

test('index.html: transport directly follows the main view; legend is the last element and is outside the main section', () => {
  const idx = (s) => html.indexOf(s);
  assert.ok(idx('id="view"') > 0 && idx('id="transport"') > idx('id="view"'));
  assert.ok(idx('id="vhead"') < idx('id="view"'), 'main head above main view');
  assert.ok(idx('id="legend"') > idx('id="transport"'));
  assert.ok(idx('<footer') > idx('</main>'));
  // The transport is the next sibling after the view's closing block: nothing but whitespace between view end and transport.
  assert.match(html, /<div class="blocker"[^>]*><\/div>\s*<\/div>\s*<div class="transport"/);
});

test('index.html: mount points for every later task, SYNTHETIC strip, FIXTURE/uncertainty containers, three mode buttons', () => {
  for (const slot of ['synthetic-strip', 'grid-2d', 'plan-3d', 'pip', 'uncertainty-readouts', 'timeline', 'panel-body', 'caption', 'blocker', 'pager']) {
    assert.match(html, new RegExp(`data-slot="${slot}"`), slot);
  }
  for (const m of ['browse', 'find', 'demo']) assert.match(html, new RegExp(`data-mode="${m}"`));
  for (const r of ['pinned', 'overlay', 'rail']) assert.match(html, new RegExp(`data-rail="${r}"`));
  assert.match(html, /id="legacy"/);
});

test('index.html: local only (no CDN, no external fonts); dark color-scheme; importmap names three', () => {
  assert.doesNotMatch(html, /https?:\/\//);
  assert.match(html, /name="color-scheme" content="dark"/);
  assert.match(html, /"three":"\/vendor\/three\.module\.js"/);
});

test('rail icon dot shows only with a selection (store side)', () => {
  assert.equal(initialState().selection, null);
  assert.equal(reduce(initialState(), { type: 'SELECT', selection: 'x' }).selection, 'x');
});

test('app.mjs mounts every view stub and imports no legacy workbench files', () => {
  const app = read('app.mjs');
  for (const f of ['grid-view', 'plan-view', 'timeline-view', 'inspector', 'query', 'demo']) {
    assert.match(app, new RegExp(`from './${f}\\.mjs'`));
    assert.match(read(`${f}.mjs`), /export function mount\(/);
  }
  assert.doesNotMatch(app, /\.\.\/workbench\//);
  assert.doesNotMatch(app, /player-grid/);
});

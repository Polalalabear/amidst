import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {EVENT_NAMES, shortEventName, eventDisplayName} from './event-names.mjs';
import {runCatalog, recordingCatalog} from './admin.model.mjs';

const A4 = 'ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1', B4 = 'ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1';
const TECH = /D\d{3}|ACTUAL_BLENDER|SYNTHETIC|自動種子|ENGINEERING|DEMO_DEFAULT|ctrl-lcorr|r004|v\d/;

test('names are keyed by run_id and use the repo/GitHub numbering', () => {
  assert.equal(EVENT_NAMES['ENGINEERING_DYNAMIC_RUN_20261025'].short, 'B-05');
  assert.equal(EVENT_NAMES[A4].short, 'A4-1');
  assert.equal(EVENT_NAMES[B4].short, 'B4-1');
  assert.equal(EVENT_NAMES['r005-static-reviewed-v2'].short, 'r005');
  assert.equal(EVENT_NAMES['SYNTHETIC_A4_1'].short, 'A4-1');
});
test('presentation mode shows only the short name, whatever the title says', () => {
  const run = {run_id: A4, title: 'A4-1 · D124 · ACTUAL_BLENDER · 自動種子'};
  const shown = eventDisplayName(run, {present: true});
  assert.equal(shown, 'A4-1 · 室外→入口→走廊');
  assert.doesNotMatch(shown, TECH);
  // title text is irrelevant: same run_id, different title → same name
  assert.equal(eventDisplayName({run_id: A4, title: 'whatever'}, {present: true}), shown);
});
test('every table entry is free of technical labels', () => {
  for (const id of Object.keys(EVENT_NAMES)) assert.doesNotMatch(shortEventName(id), TECH, id);
});
test('presentation mode off keeps the full title', () => {
  const run = {run_id: B4, title: 'B4-1 · D124 · ACTUAL_BLENDER · 自動種子'};
  assert.equal(eventDisplayName(run, {present: false}), run.title);
  assert.equal(eventDisplayName({run_id: 'x'}, {present: false}), 'x');
});
test('unknown run_id gets a neutral ordinal, never the raw id or title', () => {
  const run = {run_id: 'mystery-run-7', title: 'secret · D999 · ACTUAL_BLENDER'};
  assert.equal(eventDisplayName(run, {present: true, index: 2}), '事件 3');
});
test('admin catalogs carry an index for the ordinal fallback; titles untouched', () => {
  const boot = {runs: [{scene_id: 'S', run_id: A4, title: 'T1', camera_ids: []}, {scene_id: 'S', run_id: B4, camera_ids: []}], recordings: [{recording_id: 'r1'}]};
  const runs = runCatalog(boot);
  assert.deepEqual(runs.map(r => r.index), [0, 1]);
  assert.equal(runs[0].title, 'T1');
  assert.equal(recordingCatalog(boot)[0].index, 0);
});
test('server titles are not rewritten (real-e2e finds runs by title prefix)', () => {
  const src = readFileSync(new URL('../../scripts/serve_demo_integration.py', import.meta.url), 'utf8');
  assert.match(src, /spec\['label'\] \+ ' · D124 · ACTUAL_BLENDER · 自動種子'/);
});
test('front desk and admin route event names through eventDisplayName', () => {
  for (const f of ['ui-shell.mjs', 'admin.mjs']) assert.match(readFileSync(new URL('./' + f, import.meta.url), 'utf8'), /eventDisplayName\(/, f);
  const shell = readFileSync(new URL('./ui-shell.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(shell, /run\.title \?\? run\.run_id/);
});

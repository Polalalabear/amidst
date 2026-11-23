// #677: pure helpers of the LIVE UI/UX pass (panel prefs, back key, lost hint, same-colour notice, default model).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {defaultModel, clampSideWidth, loadPanelPrefs, savePanelPrefs, backUrl, isBackKey, peopleFromDets,
  sameColorCount, sameColorNotice, lostHint, SIDE_MIN, SIDE_MAX, SIDE_DEFAULT} from '../src/ui_state.mjs';

test('default model is terra6.1 (D237) unless the backend reports one that is on', () => {
  const models = ['astra6', 'sol6.1', 'terra6.1'];
  assert.equal(defaultModel(models), 'terra6.1');
  assert.equal(defaultModel(models, 'sol6.1'), 'sol6.1');
  assert.equal(defaultModel(models, 'nope'), 'terra6.1');
  assert.equal(defaultModel(['sol6.1']), 'sol6.1');
  assert.equal(defaultModel([]), null);
  assert.ok(!/sol6\.1/.test(fs.readFileSync(new URL('../src/system.mjs', import.meta.url), 'utf8')), 'no sol6.1 default left in the UI');
});

test('panel prefs survive a broken or missing localStorage', () => {
  const throwing = {getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }};
  assert.deepEqual(loadPanelPrefs(throwing), {collapsed: false, width: SIDE_DEFAULT});
  assert.equal(savePanelPrefs({collapsed: true, width: 400}, throwing), false);
  assert.deepEqual(loadPanelPrefs(undefined), {collapsed: false, width: SIDE_DEFAULT});
  const mem = {v: null, getItem() { return this.v; }, setItem(k, v) { this.v = v; }};
  assert.equal(savePanelPrefs({collapsed: true, width: 99999}, mem), true);
  assert.deepEqual(loadPanelPrefs(mem), {collapsed: true, width: SIDE_MAX});
  mem.v = 'not json'; assert.deepEqual(loadPanelPrefs(mem), {collapsed: false, width: SIDE_DEFAULT});
  assert.equal(clampSideWidth(10), SIDE_MIN);
  assert.equal(clampSideWidth('x'), SIDE_DEFAULT);
  assert.equal(clampSideWidth(900, 500), 500);
});

test('back: goes to the bare path; Esc only when the pointer is not locked', () => {
  assert.equal(backUrl({pathname: '/', search: '?role=operator&run=A4-1&actor=T'}), '/');
  assert.equal(isBackKey({key: 'Escape'}, {pointerLockElement: null}), true);
  assert.equal(isBackKey({key: 'Escape'}, {pointerLockElement: {}}), false);
  assert.equal(isBackKey({key: 'a'}, {pointerLockElement: null}), false);
});

const det = (color, xy, cam = 'CAM_A') => ({cam, color, est_xy: xy, score: .9, bbox: [0, 0, 1, 1]});
test('same-colour candidates are merged per person across cameras (1.5 m) and noticed from 2', () => {
  const dets = {CAM_A: [det('red', [0, 0]), det('red', [5, 0]), det('blue', [9, 9])], CAM_B: [det('red', [.5, 0])]};
  assert.equal(peopleFromDets(dets).length, 3);
  assert.equal(sameColorCount(dets, 'red'), 2);
  assert.equal(sameColorCount(dets, 'blue'), 1);
  assert.equal(sameColorCount(dets, null), 0);
  assert.equal(sameColorNotice(2), '同色候選 2 人，身分未確認');
  assert.equal(sameColorNotice(1), '');
  assert.equal(peopleFromDets({CAM_A: [{color: 'red', bbox: [0, 0, 1, 1]}]}).length, 0);
});

test('lost hint: reason from existing fields, UNKNOWN where the backend gives none', () => {
  const tr = {lost_ticks: 3, est_xy: [0, 0], target: {color: 'red', mode: 'TRACKING'}};
  assert.equal(lostHint({...tr, lost_ticks: 0}, {}), null);
  assert.equal(lostHint(null, {}), null);
  assert.equal(lostHint(tr, {}).reason, 'UNKNOWN');
  const dets = {CAM_A: [det('red', [6, 0]), det('blue', [1, 0])]};
  const noGate = lostHint(tr, dets, {});
  assert.equal(noGate.gate, null);
  assert.match(noGate.candidates[0].reason, /6\.0 m；gate：UNKNOWN/);
  assert.match(noGate.candidates[1].reason, /顏色不符/);
  const gated = lostHint(tr, dets, {gate_m: 4});
  assert.match(gated.candidates[0].reason, /超出 gate 2\.0 m/);
  assert.equal(gated.same, 1);
  assert.match(lostHint({...tr, est_xy: null}, dets, {}).candidates[0].reason, /UNKNOWN/);
  assert.match(lostHint(tr, {CAM_A: [det('red', [1, 0])]}, {gate_m: 4}).candidates[0].reason, /gate 內，原因：UNKNOWN/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { EVIDENCE_STATES, STATE_CODES, SYNTHETIC, UNCERTAINTY_LEGEND, legendItems, stateByContractState } from './tokens.mjs';

const css = readFileSync(new URL('./style.css', import.meta.url), 'utf8');

test('six evidence states in design order, with contract names', () => {
  assert.deepEqual(STATE_CODES, ['OBS', 'INC', 'INT', 'HYP', 'MISS', 'UNK']);
  assert.equal(stateByContractState('INFERRED_CONSTRAINED').code, 'INC');
  assert.equal(stateByContractState('NOPE'), null);
});

test('every state has token, line style, text code and symbol; INC is hollow, INT dashes 3-3, HYP 10-6', () => {
  for (const s of EVIDENCE_STATES) {
    assert.match(s.color_token, /^--[a-z]+$/);
    assert.ok(s.line.style && s.label && s.symbol && s.legend);
  }
  assert.equal(stateByContractState('INFERRED_CONSTRAINED').line.hollow, true);
  assert.deepEqual(stateByContractState('INFERRED_INTERPOLATION').line.dash_px, [3, 3]);
  assert.deepEqual(stateByContractState('INFERRED_HYPOTHESIS').line.dash_px, [10, 6]);
});

test('every color token exists in style.css :root, with the design §5.1 values', () => {
  const expected = { '--obs': '#8CCBFF', '--int': '#E39B2F', '--hyp': '#CC6FAE', '--miss': '#6C747C', '--unk': '#AEB7BF', '--ink': '#DCE3E9', '--bg': '#0A0D10' };
  for (const s of [...EVIDENCE_STATES, SYNTHETIC]) assert.match(css, new RegExp(`${s.color_token}:#[0-9A-Fa-f]{6}`));
  for (const [k, v] of Object.entries(expected)) assert.match(css, new RegExp(`${k}:${v}`, 'i'));
});

test('SYNTHETIC is ink only, never an evidence color', () => {
  assert.equal(SYNTHETIC.color_token, '--ink');
});

test('legend includes the D45 uncertainty item and SYNTHETIC', () => {
  const items = legendItems();
  assert.equal(items.at(-1).code, UNCERTAINTY_LEGEND.code);
  assert.match(items.at(-1).text, /±m 不確定度/);
  assert.ok(items.some((i) => i.code === 'SYNTHETIC'));
});

test('dark only: no light variant, no theme switch', () => {
  assert.match(css, /color-scheme:dark/);
  assert.doesNotMatch(css, /prefers-color-scheme/);
  assert.doesNotMatch(css, /color-scheme:\s*light/);
  assert.doesNotMatch(css, /data-theme/);
});

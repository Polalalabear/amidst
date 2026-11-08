import test from 'node:test';
import assert from 'node:assert/strict';
import {FIT_MODES, DEFAULT_FIT, normalizeFit} from './media-fit-model.mjs';
test('media fit: default is fit (no crop); unknown values fall back to it', () => {
  assert.equal(DEFAULT_FIT, 'fit'); assert.deepEqual(FIT_MODES.map(m => m.id), ['fit', 'fill', 'orig']);
  assert.equal(normalizeFit('fill'), 'fill'); assert.equal(normalizeFit('orig'), 'orig');
  for (const bad of [undefined, null, '', 'cover', 'FIT', 7]) assert.equal(normalizeFit(bad), 'fit');
});

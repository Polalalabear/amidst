import test from 'node:test';
import assert from 'node:assert/strict';
import {ZOOM_LEVELS, DEFAULT_ZOOM, ZOOM_STORAGE_KEY, normalizeZoom, wallColumns} from './ui-zoom-model.mjs';
test('camera-picture scale (D147): default 100; only the listed percentages are accepted (strings from storage too)', () => {
  assert.equal(DEFAULT_ZOOM, 100); assert.deepEqual([...ZOOM_LEVELS], [60, 80, 100, 125, 150]); assert.ok(ZOOM_STORAGE_KEY.length > 0);
  assert.equal(normalizeZoom('125'), 125); assert.equal(normalizeZoom(60), 60);
  for (const bad of [undefined, null, '', 'fit', 70, '110', 90, NaN, {}]) assert.equal(normalizeZoom(bad), 100);   // old 90/110 fall back to 100
});
test('search wall: bigger pictures, fewer columns; 100% keeps the original two columns', () => {
  assert.deepEqual(ZOOM_LEVELS.map(wallColumns), [4, 3, 2, 1, 1]);
  assert.equal(wallColumns('bogus'), 2);
});

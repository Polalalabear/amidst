import test from 'node:test';
import assert from 'node:assert/strict';
import {ZOOM_LEVELS, DEFAULT_ZOOM, ZOOM_STORAGE_KEY, normalizeZoom} from './ui-zoom-model.mjs';
test('ui zoom: default is 100; only the listed percentages are accepted (strings from storage too)', () => {
  assert.equal(DEFAULT_ZOOM, 100); assert.deepEqual([...ZOOM_LEVELS], [80, 90, 100, 110, 125]); assert.ok(ZOOM_STORAGE_KEY.length > 0);
  assert.equal(normalizeZoom('125'), 125); assert.equal(normalizeZoom(80), 80);
  for (const bad of [undefined, null, '', 'fit', 70, '150', NaN, {}]) assert.equal(normalizeZoom(bad), 100);
});

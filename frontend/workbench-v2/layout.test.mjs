import test from 'node:test';
import assert from 'node:assert/strict';
import { HEIGHTS, VERTICAL_ORDER, fitTiles, fixedChromeHeight, mainAreaSize, railWidth } from './layout.mjs';

const dims = (size, w, h, narrow) => { const r = fitTiles({ size, width: w, height: h, narrow }); return `${r.width}×${r.height}`; };

test('design §4.1 table: collapsed rail (1344×643)', () => {
  assert.equal(dims(1, 1344, 643), '1068×601');
  assert.equal(dims(2, 1344, 643), '669×376');
  assert.equal(dims(4, 1344, 643), '491×276');
  assert.equal(dims(8, 1344, 643), '331×186');
});

test('design §4.1 table: pinned rail (1044×643)', () => {
  assert.equal(dims(1, 1044, 643), '1044×587');
  assert.equal(dims(2, 1044, 643), '519×292');
  assert.equal(dims(4, 1044, 643), '491×276');
  assert.equal(dims(8, 1044, 643), '256×144');
});

test('grid shapes, narrow 8 becomes 2×4', () => {
  assert.deepEqual(fitTiles({ size: 8, width: 1344, height: 643 }), { cols: 4, rows: 2, width: 331, height: 186 });
  const n = fitTiles({ size: 8, width: 600, height: 900, narrow: true });
  assert.equal(`${n.cols}×${n.rows}`, '2×4');
  assert.throws(() => fitTiles({ size: 3, width: 100, height: 100 }), RangeError);
});

test('1440×900 main area: pinned 1044×643, collapsed and floating 1344×643', () => {
  const vp = { viewportWidth: 1440, viewportHeight: 900 };
  assert.deepEqual(mainAreaSize({ ...vp, rail: 'pinned' }), { width: 1044, height: 643, narrow: false });
  assert.deepEqual(mainAreaSize({ ...vp, rail: 'rail' }), { width: 1344, height: 643, narrow: false });
  assert.deepEqual(mainAreaSize({ ...vp, rail: 'overlay' }), { width: 1344, height: 643, narrow: false });
  assert.equal(railWidth('pinned'), 348);
});

test('fixed chrome leaves the main view ~660 px at 900 px and the transport follows the view', () => {
  assert.equal(fixedChromeHeight(), 24 + 44 + 32 + 112 + 28);
  assert.equal(900 - fixedChromeHeight(), 660);
  assert.equal(HEIGHTS.transport, 112);
  assert.ok(VERTICAL_ORDER.indexOf('transport') === VERTICAL_ORDER.indexOf('main-view') + 1);
  assert.equal(VERTICAL_ORDER.at(-1), 'legend');
});

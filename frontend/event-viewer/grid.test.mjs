import test from 'node:test';
import assert from 'node:assert/strict';
import { gridShape, fitGrid, cameraStatus, MISSING_TEXT } from './sync.mjs';

test('layout follows the camera count (not hard-coded to 8); old 4/5-camera runs keep their layout', () => {
  const shapes = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12].map((n) => { const { cols, rows } = gridShape(n); return `${n}:${cols}x${rows}`; });
  assert.deepEqual(shapes, ['0:0x0', '1:1x1', '2:2x1', '3:3x1', '4:2x2', '5:3x2', '6:3x2', '7:4x2', '8:4x2', '9:4x3', '12:4x3']);
  assert.deepEqual(gridShape('x'), { cols: 0, rows: 0 });
});

test('8 cameras fit without scrolling at 1440x900 and 1920x1080, tiles stay 16:9', () => {
  // main area = viewport minus header (~45), footer (~49), main padding 2x12 / 2x16
  for (const [vw, vh] of [[1440, 900], [1920, 1080]]) {
    const W = vw - 32, H = vh - 45 - 49 - 24, gap = 10;
    const f = fitGrid(8, W, H, gap);
    assert.equal(f.cols, 4); assert.equal(f.rows, 2);
    assert.ok(f.cols * f.width + gap * (f.cols - 1) <= W, 'fits width');
    assert.ok(f.rows * f.height + gap * (f.rows - 1) <= H, 'fits height');
    assert.ok(Math.abs(f.width / f.height - 16 / 9) < 0.02, '16:9');
    assert.ok(f.width >= 300, 'labels stay readable');
  }
});

test('height can be the binding limit; 4 and 5 camera runs also fit', () => {
  const f = fitGrid(4, 1400, 400, 10);
  assert.equal(f.rows * f.height + 10 <= 400, true);
  assert.equal(f.width, Math.floor(((400 - 10) / 2) * 16 / 9));
  for (const n of [4, 5]) { const g = fitGrid(n, 1408, 782, 10); assert.ok(g.rows * g.height + 10 * (g.rows - 1) <= 782); }
  assert.deepEqual(fitGrid(8, 0, 500), { cols: 4, rows: 2, width: 0, height: 0 });
});

test('a camera without footage is MISSING (無畫面), distinct from READY and PENDING', () => {
  assert.equal(cameraStatus(true), 'READY');
  assert.equal(cameraStatus(false), 'MISSING');
  assert.equal(cameraStatus(undefined), 'PENDING');
  assert.match(MISSING_TEXT, /無畫面/);
  assert.match(MISSING_TEXT, /MISSING/);
});

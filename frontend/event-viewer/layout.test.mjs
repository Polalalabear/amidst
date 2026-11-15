import test from 'node:test';
import assert from 'node:assert/strict';
import { adaptiveGrid, focusLayout, pickFocusCamera, layoutRects, readStoredLayout, writeStoredLayout, parseLayoutParams, LAYOUT_STORAGE_KEY, GAP } from './layout.mjs';

// 1920×1080 的查看區：扣掉頁首、播放列與 padding 後約 1888×962。
const W = 1888, H = 962;
const fits = (f, w, h, gap = GAP) => f.cols * f.width + gap * (f.cols - 1) <= w && f.rows * f.height + gap * (f.rows - 1) <= h;

test('A: 8 cameras at 1920x1080 → 3x3, 16:9, fits, no scroll', () => {
  const f = adaptiveGrid(8, W, H);
  assert.equal(f.cols, 3); assert.equal(f.rows, 3);
  assert.ok(fits(f, W, H));
  assert.ok(Math.abs(f.width / f.height - 16 / 9) < 0.02);
  assert.ok(f.width > 467, 'larger than the old 4x2 tile');
});

test('A: 4 and 5 camera runs keep a sensible shape (2x2, 3x2)', () => {
  const f4 = adaptiveGrid(4, W, H); assert.deepEqual([f4.cols, f4.rows], [2, 2]);
  const f5 = adaptiveGrid(5, W, H); assert.deepEqual([f5.cols, f5.rows], [3, 2]);
  assert.ok(fits(f4, W, H) && fits(f5, W, H));
});

test('A: extremely wide window picks 2 rows (ties prefer fewer empty cells, then fewer columns)', () => {
  const f = adaptiveGrid(8, 3000, 500);
  assert.deepEqual([f.cols, f.rows], [4, 2]);
  assert.equal(f.height, Math.floor((f.width * 9) / 16));
  assert.ok(fits(f, 3000, 500));
});

test('A: near-square window prefers fewer columns / more rows', () => {
  const f = adaptiveGrid(8, 1000, 900);
  assert.deepEqual([f.cols, f.rows], [2, 4]);
  assert.ok(fits(f, 1000, 900));
});

test('A: degenerate inputs never throw', () => {
  assert.deepEqual(adaptiveGrid(0, 100, 100), { cols: 0, rows: 0, width: 0, height: 0 });
  assert.equal(adaptiveGrid(8, 0, 500).width, 0);
  assert.equal(adaptiveGrid('x', 500, 500).cols, 0);
  assert.equal(adaptiveGrid(1, 500, 500).cols, 1);
});

test('layoutRects(grid): every camera gets a rect inside the area, none overlap', () => {
  const cams = Array.from({ length: 8 }, (_, i) => `C${i}`);
  const { rects } = layoutRects('grid', cams, null, W, H);
  assert.equal(Object.keys(rects).length, 8);
  const all = Object.values(rects);
  for (const r of all) assert.ok(r.x >= 0 && r.y >= 0 && r.x + r.width <= W && r.y + r.height <= H);
  for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
    const a = all[i], b = all[j];
    assert.ok(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y, 'no overlap');
  }
});

test('B: focus layout — main ≈65% wide, 16:9, side tiles 16:9 and inside, nothing overlaps', () => {
  const f = focusLayout(8, W, H);
  assert.ok(Math.abs(f.main.width / W - 0.65) < 0.01);
  assert.ok(Math.abs(f.main.width / f.main.height - 16 / 9) < 0.02);
  assert.equal(f.side.length, 7);
  for (const r of f.side) {
    assert.ok(r.x >= f.main.width + GAP && r.x + r.width <= W && r.y >= 0 && r.y + r.height <= H);
    assert.ok(Math.abs(r.width / r.height - 16 / 9) < 0.03);
  }
  assert.ok(f.main.y >= f.banner.y + f.banner.height - 1, 'banner sits above the main tile');
});

test('B: a short window limits the main tile by height (no stretching)', () => {
  const f = focusLayout(5, 1800, 400);
  assert.ok(f.main.height + f.banner.height <= 400);
  assert.ok(Math.abs(f.main.width / f.main.height - 16 / 9) < 0.02);
});

test('B: a single camera and 4/5-camera runs work', () => {
  assert.equal(focusLayout(1, W, H).side.length, 0);
  for (const n of [4, 5]) { const f = focusLayout(n, W, H); assert.equal(f.side.length, n - 1); assert.ok(f.main.width > 0 && f.side.every((r) => r.width > 0)); }
  assert.equal(focusLayout(0, W, H).side.length, 0);
});

test('focus camera: tracking → user selection → first camera; unknown names are ignored', () => {
  const cams = ['W1', 'W2', 'W3'];
  assert.deepEqual(pickFocusCamera(cams, 'W3', 'W2'), { camera: 'W3', source: 'tracking' });
  assert.deepEqual(pickFocusCamera(cams, null, 'W2'), { camera: 'W2', source: 'selected' });
  assert.deepEqual(pickFocusCamera(cams, null, null), { camera: 'W1', source: 'default' });
  assert.deepEqual(pickFocusCamera(cams, 'NOPE', 'ALSO_NOPE'), { camera: 'W1', source: 'default' });
  assert.deepEqual(pickFocusCamera([], 'W1', 'W1'), { camera: null, source: 'none' });
});

test('layoutRects(focus): the picked camera is the main tile; the others keep their order in the side column', () => {
  const cams = ['A', 'B', 'C', 'D'];
  const L = layoutRects('focus', cams, 'C', W, H);
  assert.equal(L.focus, 'C');
  assert.ok(L.rects.C.width > L.rects.A.width);
  assert.ok(L.rects.A.x < L.rects.D.x || L.rects.A.y < L.rects.D.y || L.rects.A.x === L.rects.D.x);
  assert.ok(L.banner);
  assert.equal(layoutRects('focus', cams, 'ZZZ', W, H).focus, 'A', 'unknown focus falls back to the first camera');
});

test('localStorage: reads and writes survive missing / throwing storage; invalid values fall back to grid', () => {
  const mem = new Map();
  const ok = { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v) };
  assert.equal(readStoredLayout(ok), 'grid');
  assert.equal(writeStoredLayout(ok, 'focus'), true);
  assert.equal(mem.get(LAYOUT_STORAGE_KEY), 'focus');
  assert.equal(readStoredLayout(ok), 'focus');
  mem.set(LAYOUT_STORAGE_KEY, 'bogus');
  assert.equal(readStoredLayout(ok), 'grid');
  const boom = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('quota'); } };
  assert.equal(readStoredLayout(boom), 'grid');
  assert.equal(writeStoredLayout(boom, 'focus'), false);
  assert.equal(readStoredLayout(null), 'grid');
  assert.equal(writeStoredLayout(null, 'focus'), false);
  assert.equal(writeStoredLayout(ok, 'bogus'), false);
});

test('URL params: layout and track are validated', () => {
  const cams = ['W1', 'W2'];
  assert.deepEqual(parseLayoutParams('?layout=focus&track=W2', cams), { layout: 'focus', track: 'W2' });
  assert.deepEqual(parseLayoutParams('?layout=zzz&track=NOPE', cams), { layout: null, track: null });
  assert.deepEqual(parseLayoutParams('', cams), { layout: null, track: null });
});

test('every module app.mjs imports is on the server static whitelist (a missing one blanks the page)', async () => {
  const { readFile } = await import('node:fs/promises');
  const app = await readFile(new URL('./app.mjs', import.meta.url), 'utf8');
  const server = await readFile(new URL('./server.mjs', import.meta.url), 'utf8');
  for (const m of app.matchAll(/from '\.\/([\w.-]+\.mjs)'/g)) assert.ok(server.includes(`'/${m[1]}'`), `${m[1]} must be served`);
});

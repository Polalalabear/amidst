import test from 'node:test';
import assert from 'node:assert/strict';
import { advance, clampTMs, classifyT, createPlayer, formatFrame, formatSeconds, frameIndexAt, frameStartMs, maxTMs, sampleAgeMs, stepTMs } from './clock.mjs';
import { createStore, initialState } from './store.mjs';

const FPS = 5;

test('frameIndexAt: integer floor, boundaries at 5 fps', () => {
  assert.equal(frameIndexAt(0, FPS), 0);
  assert.equal(frameIndexAt(199, FPS), 0);
  assert.equal(frameIndexAt(200, FPS), 1);
  assert.equal(frameIndexAt(12400, FPS), 62);
  assert.equal(frameIndexAt(12470, FPS), 62);
  assert.equal(frameIndexAt(19999, FPS), 99);
});

test('half-open run: max t_ms = duration*1000 - 1, beyond is OUT_OF_RANGE', () => {
  assert.equal(maxTMs(20), 19999);
  assert.equal(classifyT(0, 20), 'IN_RANGE');
  assert.equal(classifyT(19999, 20), 'IN_RANGE');
  assert.equal(classifyT(20000, 20), 'OUT_OF_RANGE');
  assert.equal(classifyT(-1, 20), 'OUT_OF_RANGE');
  assert.equal(classifyT(1.5, 20), 'OUT_OF_RANGE');
  assert.equal(clampTMs(99999, 20), 19999);
  assert.equal(clampTMs(-5, 20), 0);
});

test('sample age: on a sample, between samples, last ms', () => {
  assert.equal(sampleAgeMs(12400, FPS), 0);
  assert.equal(sampleAgeMs(12470, FPS), 70);
  assert.equal(sampleAgeMs(19999, FPS), 199);
  assert.equal(frameStartMs(62, FPS), 12400);
  assert.equal(frameStartMs(1, 30), 34); // ceil(33.33)
});

test('stepTMs aligns to the sample grid and clamps', () => {
  assert.equal(stepTMs(0, FPS, 1, 20), 200);
  assert.equal(stepTMs(12470, FPS, 1, 20), 12600);
  assert.equal(stepTMs(12470, FPS, -1, 20), 12400);
  assert.equal(stepTMs(12400, FPS, -1, 20), 12200);
  assert.equal(stepTMs(0, FPS, -1, 20), 0);
  assert.equal(stepTMs(19900, FPS, 1, 20), 19999);
});

test('advance: speed scaling, residual carry, end', () => {
  assert.deepEqual(advance(1000, 100, 2, 20), { tMs: 1200, ended: false, residualMs: 0 });
  const r = advance(1000, 3, 0.5, 20);
  assert.equal(r.tMs, 1001);
  assert.equal(r.residualMs, 0.5);
  assert.deepEqual(advance(19990, 100, 1, 20), { tMs: 19999, ended: true });
});

test('formatters', () => {
  assert.equal(formatSeconds(12470), '12.47');
  assert.equal(formatSeconds(0), '0.00');
  assert.equal(formatFrame(62), '#062');
});

test('player drives the store with a fake rAF and stops at the end', () => {
  const store = createStore(initialState());
  store.dispatch({ type: 'SET_RUN', run: { run_id: 'T', fps: FPS, duration_s: 1 } });
  let cb = null; let clock = 0;
  const player = createPlayer({ getState: store.getState, dispatch: store.dispatch, raf: (f) => { cb = f; return 1; }, caf: () => { cb = null; }, now: () => clock });
  store.dispatch({ type: 'PLAY' });
  player.sync();
  assert.equal(player.running, true);
  clock = 400; cb(clock);
  assert.equal(store.getState().tMs, 400);
  clock = 5000; cb(clock);
  assert.equal(store.getState().tMs, 999);
  assert.equal(store.getState().playing, false);
  assert.equal(player.running, false);
});

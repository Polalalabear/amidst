// Integer-millisecond clock (design §4.4). The run is a half-open interval [0, duration_s * 1000).
// Pure functions plus a thin rAF player; nothing here touches `document`.

export const SPEEDS = Object.freeze([0.5, 1, 2]);

export function durationMs(durationS) {
  return Math.round(durationS * 1000);
}

// Largest legal t_ms. Anything >= duration is OUT_OF_RANGE.
export function maxTMs(durationS) {
  return durationMs(durationS) - 1;
}

export function classifyT(tMs, durationS) {
  if (!Number.isInteger(tMs) || tMs < 0 || tMs > maxTMs(durationS)) return 'OUT_OF_RANGE';
  return 'IN_RANGE';
}

export function clampTMs(tMs, durationS) {
  const n = Math.trunc(Number.isFinite(tMs) ? tMs : 0);
  return Math.min(Math.max(n, 0), maxTMs(durationS));
}

// frame_index = floor(t_ms * fps / 1000), integer arithmetic, no epsilon.
export function frameIndexAt(tMs, fps) {
  const num = tMs * fps;
  return (num - (num % 1000)) / 1000;
}

// First millisecond at which frame k is the expected sample: ceil(k * 1000 / fps).
export function frameStartMs(k, fps) {
  const num = k * 1000;
  return (num + fps - 1 - ((num + fps - 1) % fps)) / fps;
}

export function sampleAgeMs(tMs, fps) {
  return tMs - frameStartMs(frameIndexAt(tMs, fps), fps);
}

// Step to the neighbouring sample boundary. Forward goes to the next frame; backward goes to the
// start of the current frame, or to the previous frame when already on a boundary.
export function stepTMs(tMs, fps, direction, durationS) {
  const k = frameIndexAt(tMs, fps);
  let target;
  if (direction > 0) target = frameStartMs(k + 1, fps);
  else target = tMs === frameStartMs(k, fps) ? frameStartMs(k - 1, fps) : frameStartMs(k, fps);
  return clampTMs(target, durationS);
}

// One playback tick. Returns the new position and whether the end was reached.
export function advance(tMs, dtMs, speed, durationS, residualMs = 0) {
  const next = tMs + residualMs + dtMs * speed;
  const max = maxTMs(durationS);
  if (next >= max) return { tMs: max, ended: true };
  return { tMs: Math.trunc(next), ended: false, residualMs: next - Math.trunc(next) };
}

export function formatSeconds(ms) {
  const sign = ms < 0 ? '-' : '';
  const abs = Math.abs(ms);
  return `${sign}${Math.floor(abs / 1000)}.${String(abs % 1000).padStart(3, '0').slice(0, 2)}`;
}

export function formatFrame(k) {
  return `#${String(k).padStart(3, '0')}`;
}

// rAF playback loop. Sub-millisecond remainders are carried so speeds 0.5x/2x do not drift.
export function createPlayer({ getState, dispatch, raf = globalThis.requestAnimationFrame, caf = globalThis.cancelAnimationFrame, now = () => globalThis.performance.now() }) {
  let handle = null;
  let last = 0;
  let residual = 0;

  function frame(ts) {
    const s = getState();
    if (!s.playing || !s.run) { handle = null; return; }
    const dt = ts - last;
    last = ts;
    const r = advance(s.tMs, dt, s.speed, s.run.duration_s, residual);
    residual = r.residualMs ?? 0;
    if (r.tMs !== s.tMs) dispatch({ type: 'SET_T', tMs: r.tMs });
    if (r.ended) { dispatch({ type: 'PAUSE' }); handle = null; return; }
    handle = raf(frame);
  }

  return {
    sync() {
      const s = getState();
      if (s.playing && handle === null) {
        last = now();
        residual = 0;
        handle = raf(frame);
      } else if (!s.playing && handle !== null) {
        caf(handle);
        handle = null;
      }
    },
    get running() { return handle !== null; },
  };
}

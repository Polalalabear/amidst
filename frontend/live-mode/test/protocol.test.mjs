import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSystemMessage, validateSystemMessage, buildInferHeader } from '../src/protocol.mjs';

const SENTINEL_XY = [1234.5678, 8765.4321];
const OPERATOR = { person_id: 'OPERATOR_SENTINEL_ID', x: SENTINEL_XY[0], y: SENTINEL_XY[1], heading: 7.7777 };

function backendResult() {
  return {
    dets: { CAM_W1: [{ bbox: [1, 2, 3, 4], score: 0.9, color: 'red', red_ratio: 0.7, est_xy: [3.1, 1.2],
      // a buggy backend that echoed operator data must still be stripped
      operator_xy: SENTINEL_XY, person_id: OPERATOR.person_id }] },
    tracking: { state: 'TRACKING', active_cam: 'CAM_W1', seen_cams: ['CAM_W1'], est_xy: [3.1, 1.2],
      events: [{ tick: 3, type: 'ACQUIRE', cam: 'CAM_W1', gt_xy: SENTINEL_XY }], lost_ticks: 0, truth: OPERATOR },
    timing_ms: { detect: 40 },
  };
}

test('system message carries no operator id or coordinates (extra keys stripped)', () => {
  const frames = [{ cam: 'CAM_W1', jpeg: new Uint8Array([1, 2, 3]).buffer, operator: OPERATOR }];
  const msg = buildSystemMessage({ tick: 3, tCaptureMs: 1, frames, result: backendResult() });
  const text = JSON.stringify(msg, (k, v) => (v instanceof ArrayBuffer ? 'bin' : v));
  assert.ok(!text.includes('OPERATOR_SENTINEL_ID'));
  assert.ok(!text.includes('1234.5678'));
  assert.ok(!text.includes('8765.4321'));
  assert.ok(!text.includes('operator'));
  assert.deepEqual(validateSystemMessage(msg), []);
});

test('validator flags any non-whitelisted key', () => {
  const msg = buildSystemMessage({ tick: 1, tCaptureMs: 1, frames: [], result: backendResult() });
  msg.operator_xy = SENTINEL_XY;
  msg.tracking.person_id = 'X';
  const bad = validateSystemMessage(msg);
  assert.ok(bad.includes('msg.operator_xy'));
  assert.ok(bad.includes('tracking.person_id'));
});

test('backend request header has only tick, clock, camera ids and byte sizes', () => {
  const h = buildInferHeader({ tick: 5, tCaptureMs: 9, frames: [{ cam: 'CAM_W1', jpeg: new ArrayBuffer(10), x: 1 }] });
  assert.deepEqual(Object.keys(h).sort(), ['frames', 't_capture_ms', 'tick']);
  assert.deepEqual(Object.keys(h.frames[0]).sort(), ['bytes', 'cam']);
});

test('advisor status passes; operator keys inside it are stripped and flagged', () => {
  const result = backendResult();
  Object.assign(result.tracking, { decision_source: 'AGENT', fallback_reason: null,
    advisor: { state: 'IDLE', pending_ms: null, operator_xy: SENTINEL_XY,
      last: { kind: 'SILENT_PICK', cam: 'CAM_W1', choice: 2, reason: 'r', latency_ms: 2900, applied: true, model: 'm', source: 'AGENT',
        fallback_reason: null, person_id: OPERATOR.person_id } } });
  const msg = buildSystemMessage({ tick: 4, tCaptureMs: 1, frames: [], result });
  assert.equal(msg.tracking.decision_source, 'AGENT');
  assert.equal(msg.tracking.advisor.last.choice, 2);
  const text = JSON.stringify(msg);
  assert.ok(!text.includes('OPERATOR_SENTINEL_ID') && !text.includes('1234.5678'));
  assert.deepEqual(validateSystemMessage(msg), []);
  msg.tracking.advisor.gt = 1; msg.tracking.advisor.last.actor_id = 'T';
  const bad = validateSystemMessage(msg);
  assert.ok(bad.includes('tracking.advisor.gt') && bad.includes('tracking.advisor.last.actor_id'));
});

test('advisor.last.cleared (answer 0, none of them) passes the whitelist; GT-like keys still do not', () => {
  const result = backendResult();
  Object.assign(result.tracking, { decision_source: 'AGENT', advisor: { state: 'IDLE', pending_ms: null,
    last: { kind: 'LOST_WITH_CANDIDATES', cam: 'CAM_W1', choice: 0, reason: 'r', latency_ms: 1200, applied: false, cleared: true, model: 'm', source: 'AGENT',
      fallback_reason: null, gt_visible: ['CAM_W1'], actor_id: 'T' } } });
  const msg = buildSystemMessage({ tick: 5, tCaptureMs: 1, frames: [], result });
  assert.equal(msg.tracking.advisor.last.cleared, true);
  assert.ok(!('gt_visible' in msg.tracking.advisor.last) && !('actor_id' in msg.tracking.advisor.last));
  assert.deepEqual(validateSystemMessage(msg), []);
});

const forbidden = ['actor_id', 'role', 'variant', 'person_id', 'operator_xy', 'player_xy', 'gt',
  'gt_visible', 'waypoints', 's_i', 'script_clock', 'pause_player_i', 'forced_overlap',
  'phase_offset_s', 'pass_end', 'crowd_error',
  'spawn_adjusted', 'run_id', 'view_yaw', 'view_pitch', 'session', 'session_id'];

function safeMessage() {
  return buildSystemMessage({ tick: 2, tCaptureMs: 5000, frames: [], result: {
    dets: {},
    tracking: { state: 'TRACKING', target: { color: 'blue', mode: 'TRACKING' },
      events: [{ tick: 2, type: 'ACQUIRE', cam: 'CAM_W1', detail: { by: 'USER_PICK' } }] },
    timing_ms: { forward: 50 },
  } });
}

for (const field of forbidden) {
  test(`forbidden field ${field} is rejected at every protocol depth`, () => {
    for (const place of [
      m => m, m => m.dets, m => m.timing_ms, m => m.tracking.target,
      m => m.tracking.events[0].detail,
    ]) {
      const msg = safeMessage();
      place(msg)[field] = 'private sentinel';
      assert.ok(validateSystemMessage(msg).length, field);
    }
  });
}

test('sender removes disallowed nested keys and nonfinite coordinates and timings', () => {
  const dirty = safeMessage();
  dirty.tracking.est_xy = [NaN, 1];
  dirty.tracking.target.run_id = 'sentinel';
  dirty.tracking.events[0].detail.gt = { private: 'sentinel' };
  dirty.timing_ms.forward = Infinity;
  dirty.timing_ms.actor_id = 'sentinel';
  dirty.dets.CAM_W1 = [{ bbox: [1, 2, 3, 4], color: 'blue', est_xy: [0, Infinity] }];
  assert.ok(validateSystemMessage(dirty).length);
  const sanitized = buildSystemMessage({ tick: 2, tCaptureMs: 5000, frames: [], result: dirty });
  assert.deepEqual(validateSystemMessage(sanitized), []);
  assert.equal(sanitized.tracking.est_xy, null);
  assert.equal(sanitized.dets.CAM_W1[0].est_xy, null);
  assert.deepEqual(sanitized.timing_ms, {});
  assert.equal(JSON.stringify(sanitized).includes('sentinel'), false);
  assert.throws(() => buildSystemMessage({ tick: Infinity, tCaptureMs: 5000, frames: [], result: dirty }),
    /INVALID_FRAME_ENVELOPE/);
});

test('operator crowd events cannot be sent to B as tracking events', () => {
  const msg = safeMessage();
  const trackingEvents = [...msg.tracking.events];
  msg.tracking.events.push(
    {type: 'crowd_error', code: 'CROWD_UNRESOLVED_PAIR', tick: 2, t_sim: 0.2},
    {type: 'pass_end', tick: 2, t_sim: 0.2, i: 'T', j: 'A', reason: 'timeout'},
  );
  assert.ok(validateSystemMessage(msg).length);
  const sanitized = buildSystemMessage({tick: 2, tCaptureMs: 5000, frames: [], result: msg});
  assert.deepEqual(sanitized.tracking.events, trackingEvents);
  assert.deepEqual(validateSystemMessage(sanitized), []);
});

test('known event details survive with typed fields, unknown shapes fail', () => {
  const details = [
    ['ACQUIRE', { by: 'AUTO_SINGLE' }],
    ['SWITCH', { from: 'CAM_WIDE', gap_ticks: 2 }],
    ['SWITCH', { from: 'CAM_WIDE', by: 'AGENT' }],
    ['TARGET_OUT_OF_VIEW', null], ['LOST', null], ['REACQUIRE', null],
    ['ADJUDICATE_ASK', { kind: 'SILENT_PICK', candidates: 2 }],
    ['ADJUDICATED', { choice: 1, applied: true, cleared: false, source: 'AGENT', latency_ms: 100 }],
  ];
  const msg = safeMessage();
  msg.tracking.events = details.map(([type, detail]) => ({ tick: 2, type, cam: 'CAM_W1', detail }));
  assert.deepEqual(validateSystemMessage(msg), []);
  msg.tracking.events[0].detail.by = 'MANUAL';
  msg.tracking.events[1].detail.gap_ticks = [2];
  msg.tracking.events.at(-1).detail.latency_ms = NaN;
  assert.deepEqual(validateSystemMessage(msg), [
    'tracking.events[0].detail.by', 'tracking.events[1].detail.gap_ticks',
    'tracking.events[7].detail.latency_ms',
  ]);
});

test('B entry and HUD have no imports or keys from A state or geometry simulation', async () => {
  const { readFile } = await import('node:fs/promises');
  for (const name of ['system.mjs', 'hud.mjs', 'system_grid.mjs']) {
    const text = await readFile(new URL(`../src/${name}`, import.meta.url), 'utf8');
    assert.doesNotMatch(text, /(?:world|sim|crowd|operator)\.mjs|groundTruthVisible|actor_id/);
  }
});

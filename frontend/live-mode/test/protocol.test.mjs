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

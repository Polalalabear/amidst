import test from 'node:test';
import assert from 'node:assert/strict';
import { switchView, buildRequest, hudModeNote } from '../src/llm_switch.mjs';
import { buildSystemMessage, validateSystemMessage } from '../src/protocol.mjs';
import { createHudState, reduce, view } from '../src/hud.mjs';

test('default: no config or backend off means the switch is off and says so', () => {
  for (const cfg of [{}, { advisor: 'off' }, { advisor: 'off', llm_switch: { requested: 'off', effective: 'off' } }]) {
    const v = switchView(cfg);
    assert.equal(v.checked, false); assert.equal(v.text, 'LLM 決策：關閉'); assert.equal(v.tone, 'rule');
  }
  // an unchecked box always requests off, whatever the select says; the request carries no other field
  assert.deepEqual(buildRequest(false, 'lead', null), { advisor: 'off' });
  assert.deepEqual(Object.keys(buildRequest(true, 'review', 'sol6.1')).sort(), ['advisor', 'advisor_model']);
  assert.equal(buildRequest(true, 'bogus', null).advisor, 'off');
});

test('off leaves the HUD exactly as before: rule source, no LLM note', () => {
  const st = createHudState();
  reduce(st, buildSystemMessage({ tick: 1, tCaptureMs: 5000, frames: [], result: { dets: {}, timing_ms: {},
    tracking: { state: 'TRACKING', active_cam: 'CAM_W1', seen_cams: ['CAM_W1'], est_xy: [3, 1], events: [], lost_ticks: 0 } } }), 5000);
  const cfg = { advisor: 'off', llm_switch: { requested: 'off', effective: 'off' } };
  const v = view(st, 5000, cfg);
  assert.equal(v.source.label, '規則'); assert.equal(v.mode.text, '規則（advisor off）'); assert.equal(hudModeNote(cfg), null);
});

test('on but no usable provider: shown as unavailable with the reason, rules in use', () => {
  const cfg = { advisor: 'off', llm_switch: { requested: 'review', effective: 'off', available: false, reason_text: '後台沒有核准付費呼叫', provider: 'openai' } };
  const v = switchView(cfg);
  assert.equal(v.text, 'LLM 決策：開啟（不可用，使用規則）'); assert.equal(v.tone, 'fallback'); assert.match(v.detail, /沒有核准/);
  assert.equal(hudModeNote(cfg), 'LLM 不可用：後台沒有核准付費呼叫');
  // a missing reason is still reported, not blank
  assert.equal(switchView({ advisor: 'off', llm_switch: { requested: 'lead', effective: 'off' } }).detail, '原因未知');
});

test('on and usable shows the effective mode; fake provider is labelled as no-network', () => {
  assert.equal(switchView({ advisor: 'review', advisor_model: 'sol6.1', llm_switch: { requested: 'review', effective: 'review', provider: 'openai', model: 'sol6.1' } }).text, 'LLM 決策：開啟（LLM 覆核）');
  const f = switchView({ advisor: 'lead', llm_switch: { requested: 'lead', effective: 'lead', provider: 'fake' } });
  assert.match(f.detail, /假模型/); assert.equal(f.fake, true);
});

test('the switch adds nothing to the B-screen protocol whitelist: switch/GT/key fields are stripped and flagged', () => {
  const tracking = { state: 'TRACKING', active_cam: 'CAM_W1', seen_cams: [], est_xy: [1, 1], events: [], lost_ticks: 0,
    llm_switch: { requested: 'review' }, advisor_api_key: 'x', gt_xy: [0, 0], operator_xy: [0, 0], person_id: 'P1' };
  const msg = buildSystemMessage({ tick: 1, tCaptureMs: 1, frames: [], result: { dets: {}, tracking, timing_ms: {} } });
  for (const k of ['llm_switch', 'advisor_api_key', 'gt_xy', 'operator_xy', 'person_id']) assert.ok(!(k in msg.tracking), k);
  assert.deepEqual(validateSystemMessage(msg), []);
  const dirty = JSON.parse(JSON.stringify(msg)); dirty.tracking.llm_switch = {}; dirty.tracking.gt_xy = [0, 0];
  const bad = validateSystemMessage(dirty); const text = JSON.stringify(bad);
  assert.match(text, /llm_switch/); assert.match(text, /gt_xy/);
});

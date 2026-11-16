import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHudState, reduce, view, pickTarget, reasonText } from '../src/hud.mjs';
import { buildSystemMessage, validateSystemMessage } from '../src/protocol.mjs';

const mk = (tick, tracking, extra = {}) => ({ type: 'frame-batch', tick, t_capture_ms: 1000 + tick * 500, frames: [], dets: {}, tracking, timing_ms: {}, ...extra });
const base = { state: 'TRACKING', active_cam: 'CAM_W1', seen_cams: ['CAM_W1'], est_xy: [3, 1], events: [], lost_ticks: 0 };
const run = (msgs, nowAfterMs = 0) => { const st = createHudState(); let t = 5000; for (const m of msgs) { reduce(st, m, t); t += 500; } return { st, now: t - 500 + nowAfterMs }; };

test('advisor off: source is rule, mode says off, nothing blank or throwing', () => {
  const { st, now } = run([mk(1, base)]);
  const v = view(st, now, { advisor: 'off' });
  assert.equal(v.track.text, '跟蹤中'); assert.equal(v.source.label, '規則'); assert.equal(v.mode.text, '規則（advisor off）');
  assert.equal(v.decision, null); assert.match(v.status.text, /LLM 沒開/);
  // no config at all (fetch failed) behaves as off
  assert.equal(view(st, now, {}).source.label, '規則');
});

test('waiting before any message', () => {
  assert.equal(view(createHudState(), 0, {}).track.kind, 'waiting');
});

test('searching before first lock has no camera', () => {
  const { st, now } = run([mk(0, { state: 'SEARCHING', active_cam: null, seen_cams: [], est_xy: null, events: [], lost_ticks: 0 })]);
  const v = view(st, now, { advisor: 'off' });
  assert.equal(v.track.kind, 'searching'); assert.equal(v.cam, null);
});

test('lost: counter starts at the previous tick capture and keeps running between messages', () => {
  const { st, now } = run([mk(1, base), mk(2, { ...base, lost_ticks: 1, events: [{ tick: 2, type: 'TARGET_OUT_OF_VIEW', cam: 'CAM_W1' }] }),
    mk(3, { ...base, lost_ticks: 2 })]);
  let v = view(st, now, { advisor: 'off' });
  assert.equal(v.track.kind, 'brief'); assert.match(v.track.text, /^失聯 \d+\.\d 秒$/);
  const s0 = v.track.seconds;
  v = view(st, now + 2000, { advisor: 'off' });
  assert.ok(Math.abs(v.track.seconds - s0 - 2) < 1e-9);
  const lostSt = run([mk(1, base), mk(2, { ...base, state: 'LOST', lost_ticks: 15 })]);
  assert.equal(view(lostSt.st, lostSt.now, {}).track.kind, 'lost');
  // reacquire stops the counter
  reduce(st, mk(4, { ...base, lost_ticks: 0 }), now + 500);
  assert.equal(view(st, now + 500, {}).track.kind, 'tracking');
});

test('camera switch notice lasts 2.5 s and names who switched', () => {
  const { st, now } = run([mk(1, base), mk(2, { ...base, active_cam: 'CAM_W2', events: [{ tick: 2, type: 'SWITCH', cam: 'CAM_W2', detail: { from: 'CAM_W1', gap_ticks: 2 } }] })]);
  const v = view(st, now, {});
  assert.deepEqual([v.switch.from, v.switch.to, v.switch.by], ['CAM_W1', 'CAM_W2', '規則']);
  assert.equal(view(st, now + 2600, {}).switch, null);
  const a = run([mk(1, base), mk(2, { ...base, active_cam: 'CAM_W2', events: [{ tick: 2, type: 'SWITCH', cam: 'CAM_W2', detail: { from: 'CAM_W1', by: 'AGENT' } }] })]);
  assert.equal(view(a.st, a.now, {}).switch.by, 'LLM');
});

const ask = { tick: 3, type: 'ADJUDICATE_ASK', cam: 'CAM_W1', detail: { kind: 'SILENT_PICK', candidates: 2 } };
const answered = (last, extra = {}) => mk(8, { ...base, decision_source: 'AGENT', fallback_reason: null,
  advisor: { state: 'IDLE', pending_ms: null, last }, events: [{ tick: 8, type: 'ADJUDICATED', cam: 'CAM_W1', detail: {} }], ...extra });
const goodLast = { kind: 'SILENT_PICK', cam: 'CAM_W1', choice: 2, reason: '紅色上衣、揹黑色背包，和參考圖相同', latency_ms: 1840, applied: true, cleared: false,
  model: 'gpt-6.1-sol', source: 'AGENT', fallback_reason: null };

test('review: pending timer, then applied decision with candidate count, reason, latency', () => {
  const asking = mk(3, { ...base, advisor: { state: 'ASKING', pending_ms: 400, last: null }, decision_source: 'RULE_ONLY', events: [ask] });
  const { st, now } = run([mk(2, base), asking]);
  const v = view(st, now + 1000, { advisor: 'review', advisor_model: 'sol6.1' });
  assert.match(v.status.text, /^LLM 判斷中 1\.4 秒（2 位候選人）$/);
  assert.match(v.source.label, /LLM 覆核中 1\.4 秒/);
  reduce(st, answered(goodLast), now + 2000);
  const w = view(st, now + 2000, { advisor: 'review', advisor_model: 'sol6.1' });
  assert.equal(w.source.label, 'LLM 覆核');
  assert.equal(w.decision.candidates, 2); assert.equal(w.decision.pick, '第 2 號（由左至右）'); assert.equal(w.decision.latencyMs, 1840);
  assert.equal(w.decision.outcome, '已採用'); assert.equal(Array.from(w.decision.reason).length <= 40, true);
  assert.match(w.status.text, /^LLM 選了第 2 號/);
  assert.equal(w.mode.line, 'LLM 覆核 · gpt-6.1-sol (sol6.1)');
  assert.equal(view(st, now + 2000, { advisor: 'lead' }).source.label, 'LLM 主導');
});

test('reason is clipped to 40 characters', () => {
  const { st, now } = run([mk(2, base), answered({ ...goodLast, reason: '字'.repeat(60) })]);
  assert.equal(Array.from(view(st, now, { advisor: 'review' }).decision.reason).length, 40);
});

test('choice 0 reads as none of them', () => {
  const { st, now } = run([mk(2, base), answered({ ...goodLast, choice: 0, applied: false, cleared: true, reason: '都不像' })]);
  const d = view(st, now, { advisor: 'review' }).decision;
  assert.equal(d.pick, '都不是'); assert.equal(d.outcome, '已採用（不跟隨任何人）');
});

test('fallback: algorithm stands in, with the reason, for each backend code', () => {
  const cases = { PROVIDER_TIMEOUT: '逾時', INVALID_RESPONSE: '回應不合法', CALL_BUDGET_EXHAUSTED: '額度用完', MODE_NOT_AUTHORIZED: '沒開', TIME_BUDGET: '逾時或答案太晚' };
  for (const [code, zh] of Object.entries(cases)) {
    const last = { kind: 'SILENT_PICK', cam: 'CAM_W1', choice: null, reason: null, latency_ms: 5000, applied: false, cleared: false, model: null, source: 'RULE_FALLBACK', fallback_reason: code };
    const { st, now } = run([mk(2, base), mk(8, { ...base, decision_source: 'RULE_FALLBACK', fallback_reason: code, advisor: { state: 'IDLE', pending_ms: null, last },
      events: [{ tick: 8, type: 'ADJUDICATED', cam: 'CAM_W1', detail: {} }] })]);
    const v = view(st, now, { advisor: 'review' });
    assert.equal(v.source.label, '演算法暫代'); assert.equal(v.source.reason, zh); assert.equal(reasonText(code), zh);
    assert.match(v.status.text, /^演算法暫代：/);
  }
});

test('late answer is shown as discarded, not as chosen-and-used', () => {
  const last = { ...goodLast, applied: false, source: 'RULE_FALLBACK', fallback_reason: 'TIME_BUDGET' };
  const { st, now } = run([mk(2, base), answered(last, { decision_source: 'RULE_FALLBACK', fallback_reason: 'TIME_BUDGET' })]);
  const v = view(st, now, { advisor: 'review' });
  assert.equal(v.decision.outcome, '太晚，已丟棄'); assert.equal(v.status.text, '演算法暫代：答案太晚，已丟棄');
});

test('lead: held view shows LLM judging with a running timer', () => {
  const m = mk(4, { ...base, state: 'ADJUDICATING', advisor: { state: 'ASKING', pending_ms: 1000, last: null }, decision_source: 'RULE_ONLY', events: [ask] });
  const { st, now } = run([mk(2, base), m]);
  const v = view(st, now + 500, { advisor: 'lead' });
  assert.equal(v.track.kind, 'adjudicating'); assert.equal(v.track.text, 'LLM 判斷中 1.5 秒'); assert.equal(v.source.label, 'LLM 判斷中');
});

test('fake provider is labelled as such', () => {
  const { st, now } = run([mk(1, base)]);
  assert.match(view(st, now, { advisor: 'review', advisor_provider: 'fake', advisor_model: 'sol6.1' }).mode.line, /假模型/);
});

test('pickTarget: nearest red within 1.5 m of the backend estimate; none while lost', () => {
  const dets = [{ color: 'blue', est_xy: [3, 1] }, { color: 'red', est_xy: [3.9, 1] }, { color: 'red', est_xy: [3.2, 1] }];
  assert.equal(pickTarget(dets, base), 2);
  assert.equal(pickTarget(dets, { ...base, lost_ticks: 1 }), -1);
  assert.equal(pickTarget([{ color: 'red', est_xy: [9, 9] }], base), -1);
});

test('B screen sources hold no ground truth, operator state or actor ids', () => {
  const dir = new URL('../src/', import.meta.url);
  for (const f of ['system.mjs', 'hud.mjs']) {
    const src = fs.readFileSync(new URL(f, dir), 'utf8');
    assert.ok(!/import[^;]*(world|operator|sim|person|setup|capture)\.mjs/.test(src), `${f} imports operator-side code`);
    assert.ok(!/gt_visible|groundTruth|operator_xy|person_id|actor_id|scenario|__op\b|P0\b/.test(src), `${f} mentions GT/operator state`);
  }
});

test('every field the HUD reads is on the protocol whitelist (a backend echo of GT is stripped and flagged)', () => {
  const result = { dets: {}, tracking: { ...base, decision_source: 'AGENT', fallback_reason: null, gt_visible: ['CAM_W1'], actor_id: 'T',
    advisor: { state: 'IDLE', pending_ms: null, last: { ...goodLast, actor_id: 'T' } } } };
  const msg = buildSystemMessage({ tick: 1, tCaptureMs: 1, frames: [], result });
  assert.deepEqual(validateSystemMessage(msg), []);
  const text = JSON.stringify(msg);
  assert.ok(!text.includes('gt_visible') && !text.includes('actor_id'));
  const { st, now } = run([msg]);
  assert.equal(view(st, now, { advisor: 'review' }).source.label, 'LLM 覆核');
  msg.tracking.gt_visible = ['CAM_W1'];
  assert.deepEqual(validateSystemMessage(msg), ['tracking.gt_visible']);
});

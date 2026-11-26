import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHudState, reduce, view, pickTarget, reasonText } from '../src/hud.mjs';
import { buildSystemMessage, validateSystemMessage } from '../src/protocol.mjs';

// 每則訊息都先走 buildSystemMessage（白名單），HUD 只看得到白名單放行的欄位；這樣被剝掉的欄位會讓測試失敗。
const mk = (tick, tracking) => buildSystemMessage({ tick, tCaptureMs: 5000 + (tick - 1) * 500, frames: [], result: { dets: {}, tracking, timing_ms: {} } });
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
  assert.equal(view(st, now + 4000, { advisor: 'off' }).track.kind, 'lost');   // 3 s and more: red
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

test('an applied answer keeps the LLM source visible for a while, then the rule label returns', () => {
  const { st, now } = run([mk(2, base), answered(goodLast, { decision_source: 'RULE_ONLY' })]);
  assert.equal(view(st, now + 1000, { advisor: 'review' }).source.label, 'LLM 覆核');
  assert.equal(view(st, now + 9000, { advisor: 'review' }).source.label, '規則');
  assert.equal(view(st, now + 1000, { advisor: 'off' }).source.label, '規則');
});

test('a timeout with no answer is not shown as an invalid answer', () => {
  const last = { kind: 'SILENT_PICK', cam: 'CAM_W1', choice: null, reason: null, latency_ms: 5000, applied: false, cleared: false, model: null, source: 'RULE_FALLBACK', fallback_reason: 'PROVIDER_TIMEOUT' };
  const { st, now } = run([mk(2, base), mk(8, { ...base, decision_source: 'RULE_FALLBACK', fallback_reason: 'PROVIDER_TIMEOUT', advisor: { state: 'IDLE', pending_ms: null, last }, events: [] })]);
  assert.equal(view(st, now, { advisor: 'review' }).decision.pick, '逾時，沒收到答案');
});

test('choice 0 reads as none of them', () => {
  const { st, now } = run([mk(2, base), answered({ ...goodLast, choice: 0, applied: false, cleared: true, reason: '都不像' })]);
  const d = view(st, now, { advisor: 'review' }).decision;
  assert.equal(d.pick, '都不是'); assert.equal(d.outcome, '已採用（不跟隨任何人）');   // cleared must survive the whitelist
  assert.equal(view(st, now, { advisor: 'review' }).status.text.startsWith('LLM 選了都不是'), true);
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

test('timeout without an answer reads as no answer, not as a late discard', () => {
  const last = { kind: 'SILENT_PICK', cam: 'CAM_W1', choice: null, reason: null, latency_ms: 1000, applied: false, cleared: false, model: null, source: 'RULE_FALLBACK', fallback_reason: 'TIME_BUDGET' };
  const { st, now } = run([mk(2, base), mk(8, { ...base, decision_source: 'RULE_FALLBACK', fallback_reason: 'TIME_BUDGET', advisor: { state: 'IDLE', pending_ms: null, last },
    events: [{ tick: 8, type: 'ADJUDICATED', cam: 'CAM_W1', detail: {} }] })]);
  const d = view(st, now, { advisor: 'review' }).decision;
  assert.equal(d.pick, '逾時，沒收到答案'); assert.match(d.outcome, /^沒收到答案，改用規則/); assert.equal(d.late, false);
});

test('every advisor.last field the HUD reads survives buildSystemMessage', () => {
  const read = ['kind', 'cam', 'choice', 'reason', 'latency_ms', 'applied', 'cleared', 'model', 'source', 'fallback_reason'];
  const last = { kind: 'LOST_WITH_CANDIDATES', cam: 'CAM_W1', choice: 0, reason: '都不是',
    latency_ms: 1200, applied: false, cleared: true, model: 'fake', source: 'AGENT', fallback_reason: null };
  const msg = mk(1, { ...base, advisor: { state: 'IDLE', pending_ms: null, last } });
  for (const k of read) assert.ok(k in msg.tracking.advisor.last, `${k} was stripped`);
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

test('A/B HUD displays IDLE, candidate count, and backend-selected color', () => {
  const idle = run([mk(1, { ...base, active_cam: null, state: 'IDLE', target: { color: null, mode: 'IDLE' } })]);
  assert.deepEqual(view(idle.st, idle.now).track, { kind: 'searching', text: '尚未開始追蹤' });
  const pick = run([mk(1, { ...base, active_cam: null, state: 'NEEDS_PICK', target: { color: 'blue', mode: 'NEEDS_PICK' } })]);
  const v = view(pick.st, pick.now, {}, 2);
  assert.equal(v.track.text, '請選擇要追蹤的人（2 位）');
  assert.equal(v.target, '目標：藍衣');
  const reselect = run([mk(1, { ...base, target: { color: 'blue', mode: 'NEEDS_PICK' } })]);
  assert.equal(view(reselect.st, reselect.now).track.kind, 'tracking');
});

test('blue follows the nearest blue observation and the HUD rolling median is inclusive', async () => {
  assert.equal(pickTarget([
    { color: 'red', est_xy: [0, 0] },
    { color: 'blue', est_xy: [1, 0] },
  ], { ...base, est_xy: [0, 0], target: { color: 'blue', mode: 'TRACKING' } }), 1);
  const { recordLatency } = await import('../src/hud.mjs');
  const st = createHudState();
  assert.equal(recordLatency(st, 1000, 400), 600);
  assert.equal(recordLatency(st, 1500, 1400), 350);
  assert.equal(recordLatency(st, 2000, 1500), 500);
  assert.equal(recordLatency(st, 2001, 1901), 100);
  assert.equal(recordLatency(st, 2010, 2040), null);
});

test('NEEDS_CONFIRM (#589 R2) shows as pending confirmation and counts as lost, never as tracking', () => {
  const { st, now } = run([mk(1, base), mk(2, { ...base, state: 'NEEDS_CONFIRM', lost_ticks: 2, unseen_s: 6, lost_phase: 'long', confirm_candidates: [] })], 1000);
  const v = view(st, now, { advisor: 'off' });
  assert.equal(v.track.kind, 'lost'); assert.match(v.track.text, /^待確認（失聯 \d+\.\d 秒）$/);
});

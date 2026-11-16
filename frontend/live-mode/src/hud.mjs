// B 畫面（系統端）的 HUD 狀態：純函式，沒有 DOM，方便用 node 測。
// 輸入只有後台經 protocol.mjs 白名單送來的訊息（validateSystemMessage 通過的那種）和 /config（後台的啟動參數）。
// 這裡不認識操作者的座標、角色代號或 GT；也沒有任何欄位可以放那些東西。

export const REASON_TEXT = {
  PROVIDER_TIMEOUT: '逾時',
  TIME_BUDGET: '逾時或答案太晚',
  INVALID_RESPONSE: '回應不合法',
  CALL_BUDGET_EXHAUSTED: '額度用完',
  MODE_NOT_AUTHORIZED: '沒開',
  PROVIDER_UNAVAILABLE: '服務無法使用',
};
export const reasonText = (code) => (code ? REASON_TEXT[code] || String(code) : null);
export const MODE_TEXT = { off: '規則（advisor off）', review: 'LLM 覆核', lead: 'LLM 主導' };
export const SOURCE_TEXT = { review: 'LLM 覆核', lead: 'LLM 主導' };
const REASON_MAX = 40;
const clip = (s) => (s ? Array.from(String(s)).slice(0, REASON_MAX).join('') : '');

export function createHudState() {
  return { cam: null, switchInfo: null, lostSince: null, prevCapture: null, tr: null, tick: null, tCapture: null, recvAt: null,
    pending: null, ask: null, decision: null };
}

// 每收到一則訊息呼叫一次。nowMs 用同一個 epoch 毫秒時鐘（common.mjs 的 now）。
export function reduce(st, msg, nowMs) {
  const tr = msg.tracking || {};
  const evs = tr.events || [];
  const cam = tr.active_cam || null;
  if (cam && st.cam && cam !== st.cam) {
    const ev = evs.find((e) => e.type === 'SWITCH' && e.cam === cam);
    const by = ev && ev.detail && ev.detail.by === 'AGENT' ? 'LLM' : '規則';
    st.switchInfo = { from: st.cam, to: cam, at: nowMs, by };
  }
  if (cam) st.cam = cam;
  const lost = tr.lost_ticks || 0;
  if (lost > 0) {
    if (st.lostSince == null) st.lostSince = st.prevCapture != null ? st.prevCapture : msg.t_capture_ms;
  } else st.lostSince = null;
  for (const e of evs) {
    if (e.type === 'ADJUDICATE_ASK') st.ask = { kind: e.detail && e.detail.kind, cam: e.cam, candidates: e.detail && e.detail.candidates };
    if (e.type === 'ADJUDICATED') {
      st.decision = { tick: e.tick, at: nowMs, candidates: st.ask && st.ask.cam === e.cam ? st.ask.candidates : null };
      st.ask = null;
    }
  }
  const adv = tr.advisor || null;
  st.pending = adv && adv.state === 'ASKING' && adv.pending_ms != null ? { ms: adv.pending_ms, at: nowMs } : null;
  st.prevCapture = msg.t_capture_ms;
  st.tr = tr; st.tick = msg.tick; st.tCapture = msg.t_capture_ms; st.recvAt = nowMs;
  return st;
}

const sec = (ms) => (ms / 1000).toFixed(1);

// 畫面要顯示的字。cfg 是 /config：{advisor: off|review|lead, advisor_model, advisor_provider}。
export function view(st, nowMs, cfg = {}) {
  const mode = cfg.advisor || 'off';
  const tr = st.tr;
  if (!tr) return { track: { kind: 'waiting', text: '等待後台資料' }, cam: null, source: { label: '規則', reason: null, tone: 'rule' },
    decision: null, mode: modeView(mode, cfg), status: { text: '等待後台資料', tone: 'rule' }, switch: null };
  const pendingMs = st.pending ? st.pending.ms + (nowMs - st.pending.at) : null;
  const lostMs = st.lostSince != null ? Math.max(0, nowMs - st.lostSince) : null;
  const count = st.decision && st.decision.candidates;

  let track;
  if (tr.state === 'ADJUDICATING') track = { kind: 'adjudicating', text: `LLM 判斷中 ${sec(pendingMs || 0)} 秒`, seconds: (pendingMs || 0) / 1000 };
  else if (tr.state === 'SEARCHING' || !tr.active_cam) track = { kind: 'searching', text: '尚未鎖定目標' };
  else if (lostMs != null) track = { kind: tr.state === 'LOST' ? 'lost' : 'brief', text: `失聯 ${sec(lostMs)} 秒`, seconds: lostMs / 1000 };
  else track = { kind: 'tracking', text: '跟蹤中' };

  const fb = reasonText(tr.fallback_reason);
  let source;
  if (mode === 'off') source = { label: '規則', reason: null, tone: 'rule' };
  else if (tr.state === 'ADJUDICATING') source = { label: 'LLM 判斷中', reason: null, tone: 'wait' };
  else if (tr.decision_source === 'AGENT') source = { label: SOURCE_TEXT[mode] || 'LLM', reason: null, tone: 'llm' };
  else if (tr.decision_source === 'RULE_FALLBACK') source = { label: '演算法暫代', reason: fb || '原因未知', tone: 'fallback' };
  else source = { label: pendingMs != null ? `規則（LLM 覆核中 ${sec(pendingMs)} 秒）` : '規則', reason: null, tone: pendingMs != null ? 'wait' : 'rule' };

  const last = tr.advisor && tr.advisor.last;
  let decision = null;
  if (last) {
    const late = last.source === 'RULE_FALLBACK' && last.fallback_reason === 'TIME_BUDGET';
    let pick;
    if (last.source === 'RULE_FALLBACK' && last.choice == null) pick = '沒有有效答案';
    else if (last.cleared || last.choice === 0) pick = '都不是';
    else pick = `第 ${last.choice} 號（由左至右）`;
    let outcome;
    if (last.applied) outcome = '已採用';
    else if (last.cleared) outcome = '已採用（不跟隨任何人）';
    else if (late) outcome = '太晚，已丟棄';
    else outcome = `未採用：${reasonText(last.fallback_reason) || '原因未知'}`;
    decision = { candidates: count == null ? null : count, camera: last.cam, pick, reason: clip(last.reason), latencyMs: last.latency_ms, outcome,
      applied: !!last.applied, fallback: last.source === 'RULE_FALLBACK', late, model: last.model || null, at: st.decision ? st.decision.at : null };
  }

  let status;
  if (pendingMs != null) status = { text: `LLM 判斷中 ${sec(pendingMs)} 秒${st.ask && st.ask.candidates ? `（${st.ask.candidates} 位候選人）` : ''}`, tone: 'wait' };
  else if (decision && st.decision && nowMs - st.decision.at < 8000) {
    if (decision.fallback) status = { text: `演算法暫代：${decision.late ? '答案太晚，已丟棄' : reasonText(last.fallback_reason) || '原因未知'}`, tone: 'fallback' };
    else status = { text: `LLM 選了${decision.pick}${decision.reason ? `：${decision.reason}` : ''}`, tone: 'llm' };
  } else if (mode === 'off') status = { text: '規則追蹤中（LLM 沒開）', tone: 'rule' };
  else status = { text: tr.decision_source === 'RULE_FALLBACK' ? `演算法暫代：${fb || '原因未知'}` : '規則追蹤中，LLM 待命', tone: tr.decision_source === 'RULE_FALLBACK' ? 'fallback' : 'rule' };

  const sw = st.switchInfo && nowMs - st.switchInfo.at < 2500 ? st.switchInfo : null;
  return { track, cam: tr.active_cam || null, source, decision, mode: modeView(mode, cfg, last), status, switch: sw };
}

function modeView(mode, cfg, last) {
  const fake = cfg.advisor_provider === 'fake';
  const model = mode === 'off' ? null : fake ? '假模型（測試，不連網）' : (last && last.model) || cfg.advisor_model || null;
  const cfgName = mode !== 'off' && !fake && cfg.advisor_model && model !== cfg.advisor_model ? ` (${cfg.advisor_model})` : '';
  return { mode, text: MODE_TEXT[mode] || mode, model, line: model ? `${MODE_TEXT[mode] || mode} · ${model}${cfgName}` : MODE_TEXT[mode] || mode };
}

// 主畫面上哪個框是目標：紅色、離後台估計位置 1.5 m 內最近的那個；失聯時不標。
export function pickTarget(dets, tr) {
  if (!tr || !tr.est_xy || (tr.lost_ticks || 0) > 0 || tr.state === 'ADJUDICATING') return -1;
  let best = -1, bd = 1.5;
  (dets || []).forEach((d, i) => {
    if (d.color !== 'red' || !d.est_xy) return;
    const dist = Math.hypot(d.est_xy[0] - tr.est_xy[0], d.est_xy[1] - tr.est_xy[1]);
    if (dist <= bd) { bd = dist; best = i; }
  });
  return best;
}

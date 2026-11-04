// 追蹤模式的資料入口（唯一入口）。追蹤畫面只能用系統既有的、非 GT 的追蹤決策輸出（Q2 決策與切鏡時點）；
// 絕不用劇本、情境卡的計畫時刻、GT、渲染軌跡、可見性或深度去產生或模擬切鏡。
//  - b05b（預錄）與 b05a（live）：決策由各自的 P1 工作台（Q2 回應、決策紀錄）提供，本模組只宣告「可用」。
//  - a41／b41（複雜事件）：#118 索引與 CX-8 RULE_ONLY 尚未產生任何系統追蹤輸出，輸出格式 UNKNOWN，所以回報 NOT_PRODUCED，不猜格式、不寫 adapter。
// 之後接 CX-8 輸出：只改這個檔案的 TRACKING，把該事件改為 AVAILABLE 並由這裡提供讀取；event-menu.mjs 只問 trackingStatus()。
export const NOT_PRODUCED_TEXT = '追蹤結果尚未產生（需 #118／CX-8 RULE_ONLY）· UNKNOWN';
export const TRACKING = Object.freeze({
  b05b: Object.freeze({status: 'AVAILABLE', via: 'Q2 錄製回應'}),
  b05a: Object.freeze({status: 'AVAILABLE', via: 'Q2 live 回應'}),
  a41: Object.freeze({status: 'NOT_PRODUCED', reason: NOT_PRODUCED_TEXT}),
  b41: Object.freeze({status: 'NOT_PRODUCED', reason: NOT_PRODUCED_TEXT}),
});
export function trackingStatus(eventId) {
  return TRACKING[eventId] ?? Object.freeze({status: 'NONE', reason: '這個事件的追蹤從「檢索」開始'});
}

// 查找（Q1 找相機）的可用性。B-05 在錄製伺服器（監控牆／B-05b）展示；live 進程只做 B-05a 追蹤。
// A4-1／B4-1 沒有 #118 索引，查找尚未支援：顯示 UNKNOWN，不用劇本、GT 或渲染資料猜命中。
export const FIND_NOT_SUPPORTED_TEXT = '查找尚未支援（需 #118 索引）· UNKNOWN';
export const FIND = Object.freeze({
  q1: Object.freeze({status: 'AVAILABLE', via: 'Q1 查詢'}),
  b05b: Object.freeze({status: 'AVAILABLE', via: 'Q1 查詢（錄製伺服器）'}),
  a41: Object.freeze({status: 'NOT_PRODUCED', reason: FIND_NOT_SUPPORTED_TEXT}),
  b41: Object.freeze({status: 'NOT_PRODUCED', reason: FIND_NOT_SUPPORTED_TEXT}),
});
export function findStatus(eventId) {
  return FIND[eventId] ?? Object.freeze({status: 'NONE', reason: '這個事件的查找在「監控牆／B-05b」展示'});
}
// CX-8 RULE_ONLY 收據（scripts/run_cx8_rule_tracking.py 的輸出）。只接受通過結構檢查、且身分仍為 UNCONFIRMED 的收據；
// 其餘一律維持 NOT_PRODUCED。本函式不發任何網路請求、不改 TRACKING，只回傳狀態與切鏡點。
export function cx8Tracking(eventId, receipt) {
  const base = trackingStatus(eventId);
  if (base.status !== 'NOT_PRODUCED') return base;
  const r = receipt;
  const ok = r && r.schema === 'cx8-rule-tracking.v1' && r.mode === 'RULE_ONLY' && r.identity === 'UNCONFIRMED'
    && Array.isArray(r.segments) && Array.isArray(r.switches);
  if (!ok) return base;
  return Object.freeze({status: 'AVAILABLE', via: 'CX-8 RULE_ONLY', segments: r.segments.length, switches: Object.freeze(r.switches.map((s) => Object.freeze({...s})))});
}
export function modeStatus(eventId, mode) {
  return mode === 'track' ? trackingStatus(eventId) : mode === 'find' ? findStatus(eventId) : Object.freeze({status: 'AVAILABLE'});
}

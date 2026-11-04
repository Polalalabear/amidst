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

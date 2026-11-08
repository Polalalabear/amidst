// D139 展示模式（front desk only）：plain wording for the audience; technical tags go into an ⓘ that shows on hover/focus.
// Presentation only. The four evidence states stay distinct inside the models (OBSERVED / INFERRED / MISSING / UNKNOWN);
// this module only chooses the words printed on the front desk. The admin pages do not use it and keep the full tags.

export const PLAIN_STATE = Object.freeze({
  OBSERVED: '已觀測',
  INFERRED: '推測',
  MISSING: '此時段沒有畫面',
  LOST: '已跟丟',
  UNKNOWN: '無法判定',
});
export const plainState = code => PLAIN_STATE[code] ?? PLAIN_STATE.UNKNOWN;

const CONFIDENCE_ZH = Object.freeze({ LOW: '低', MEDIUM: '中', HIGH: '高' });
export const confidenceText = c => CONFIDENCE_ZH[String(c ?? '').toUpperCase()] ?? '未知';

// Plain sentences for the wording that used to carry codes. `tech` is what ⓘ shows.
export const PLAIN = Object.freeze({
  noFrame: '此時段沒有畫面',
  syntheticFrame: '示意影像',
  regionsPending: '地點資料尚未就緒',
  noPlan: '尚無鏡頭位置資料',
  noPrediction: '無法預測',
  identity: '身分未確認',
  manualUnsupported: '追蹤起點由系統自動選擇，目前還不能手動改選目標',
  stopHint: '停止畫面上的追蹤顯示；不會影響原始錄影',
  bothEndsObserved: '兩端已觀測，中段為推測',
});
export const gapNote = last => `此時段沒有畫面（目標在盲區，上一個鏡頭 ${last ?? '無'}）`;
export const lostNote = last => `目標已跟丟 · 最後出現在 ${last ?? '無'}`;
export const planHeadText = confidence => `推測路線 · 信心${confidenceText(confidence)}`;
export const reacquiredText = ({ cameraId, atText }) => `已由 ${String(cameraId).replace(/^CAM_/, '')} 鏡頭於 ${atText} 觀測到`;

// Speed note: the legacy transport prints 設定 N× (· 實際 M×). The front desk drops the setting part.
export function speedNoteText(note) {
  const m = /實際\s*([\d.]+)\s*[×x]/i.exec(String(note ?? ''));
  return m ? `實際 ${m[1]}×` : '';
}

// A technical tag is { text, code }. In presentation mode tags are collected into one ⓘ tooltip text.
export function techSummary(tags) {
  const seen = new Set(), out = [];
  for (const t of tags ?? []) { const text = typeof t === 'string' ? t : t?.text; if (text && !seen.has(text)) { seen.add(text); out.push(text); } }
  return out.join(' · ');
}

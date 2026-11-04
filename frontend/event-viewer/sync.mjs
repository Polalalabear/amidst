// 純函式：frame index 與時間的換算，瀏覽器與 node 測試共用。
export const FRAME_PAD = 6;

export function frameName(index) {
  return String(index).padStart(FRAME_PAD, '0');
}

export function clampFrame(index, total) {
  if (!Number.isFinite(index) || total < 1) return 0;
  return Math.min(Math.max(Math.trunc(index), 0), total - 1);
}

export function stepFrame(index, delta, total) {
  return clampFrame(index + delta, total);
}

export function frameToSeconds(index, fps) {
  return index / fps;
}

// 顯示一律到小數點後兩位（與 FEAT-9 一致）；內部仍用 index / fps 原精度。
export function formatTime(index, fps) {
  return `${(index / fps).toFixed(2)} s`;
}

// 攝影機畫格左上角標籤：`<鏡頭> · <秒> s`。只用來源 frame index / fps，不顯示牆鐘；時間未知則 UNKNOWN。
export function stampText(camera, index, fps) {
  const ok = Number.isInteger(index) && index >= 0 && Number.isFinite(fps) && fps > 0;
  return `${camera} · ${ok ? formatTime(index, fps) : 'UNKNOWN'}`;
}

export function mediaUrl(runKey, camera, index) {
  return `/media/${runKey}/${camera}/${frameName(index)}.png`;
}

// 播放排程：永遠逐格前進、不跳格。下一格到期且就緒才換；
// 落後超過一個間隔時重新對齊到期時間，並回報 late。
export function planTick({ now, nextDue, frame, total, fps, ready }) {
  const interval = 1000 / fps;
  if (frame >= total - 1) return { action: 'end', frame, nextDue };
  if (now < nextDue) return { action: 'wait', frame, nextDue };
  if (!ready) return { action: 'stall', frame, nextDue };
  const late = now - nextDue >= interval;
  return { action: 'advance', frame: frame + 1, nextDue: late ? now + interval : nextDue + interval, late };
}

// 內嵌模式（workbench-v2 事件選單以 iframe 載入本頁）。只用 URL 參數與 postMessage 切換顯示方式，不讀不寫任何資料。
export const VIEW_MODES = Object.freeze(['system', 'simple']);
export const INSUFFICIENT_TEXT = '證據不足';

export function parseEmbed(search, runKeys) {
  let params;
  try { params = new URLSearchParams(search ?? ''); } catch { params = new URLSearchParams(); }
  const view = params.get('view');
  const run = params.get('run');
  return {
    embed: params.get('embed') === '1',
    view: VIEW_MODES.includes(view) ? view : 'system',
    run: runKeys.includes(run) ? run : null,
  };
}

// 只接受上層視窗（loopback）送來的 {type:'amidst.view', view}；其他來源、型別、值一律忽略。
export function acceptViewMessage(event, parentWindow) {
  if (!event || event.source !== parentWindow) return null;
  if (!/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(String(event.origin))) return null;
  const data = event.data;
  if (!data || data.type !== 'amidst.view' || !VIEW_MODES.includes(data.view)) return null;
  return data.view;
}

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

export function formatTime(index, fps) {
  const tenths = Math.round((index / fps) * 10);
  const minutes = Math.floor(tenths / 600);
  const seconds = (tenths % 600) / 10;
  return `${String(minutes).padStart(2, '0')}:${seconds.toFixed(1).padStart(4, '0')}`;
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

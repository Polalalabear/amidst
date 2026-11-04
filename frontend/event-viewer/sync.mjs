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

// 虛擬世界時間（宣告的展示時鐘起點 + 來源時間），格式 `YYYY-MM-DD HH:MM:SS.ff`＋`UTC+8`；時鐘缺失或無效時回 null，不假設日期。
export function virtualTime(index, fps, clock) {
  if (!Number.isInteger(index) || index < 0 || !Number.isFinite(fps) || fps <= 0 || !clock || clock.rate !== 1) return null;
  const m = String(clock.wall_origin ?? '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?([+-])(\d{2}):(\d{2})$/);
  if (!m) return null;
  try {
    const originMs = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0)) - (m[7] === '-' ? -1 : 1) * (+m[8] * 60 + +m[9]) * 60000;
    const hundredths = Math.floor(((index - (clock.t0_us ?? 0) / 1e6 * fps) / fps) * 100 + 1e-9);   // 兩位小數截斷
    const ms = originMs + hundredths * 10;
    const when = new Date(ms);
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: clock.timezone, calendar: 'iso8601', numberingSystem: 'latn', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(when).map((x) => [x.type, x.value]));
    const off = new Intl.DateTimeFormat('en-US', { timeZone: clock.timezone, timeZoneName: 'longOffset' }).formatToParts(when).find((x) => x.type === 'timeZoneName')?.value ?? '';
    const o = off.match(/^GMT([+-])(\d{2}):(\d{2})$/);
    const tz = off === 'GMT' ? 'UTC+0' : o ? `UTC${o[1]}${Number(o[2])}${o[3] === '00' ? '' : ':' + o[3]}` : null;
    if (!tz) return null;
    const frac = String(((hundredths % 100) + 100) % 100).padStart(2, '0');
    return { text: `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}.${frac}`, tz, declared: clock.mapping_kind === 'DECLARED_DEMO_CLOCK' };
  } catch { return null; }
}

// 攝影機畫格左上角標籤：第一行 `<鏡頭> · <虛擬世界時間>（UTC+8）`；第二行（次要，系統模式）`+<經過秒數> s · DECLARED_DEMO_CLOCK`。
// 只用來源 frame index / fps 與宣告的時鐘，不顯示牆鐘；時間未知則 UNKNOWN。
export function stampParts(camera, index, fps, clock) {
  const ok = Number.isInteger(index) && index >= 0 && Number.isFinite(fps) && fps > 0;
  if (!ok) return { main: `${camera} · UNKNOWN`, sub: '' };
  const v = virtualTime(index, fps, clock);
  return {
    main: `${camera} · ${v ? `${v.text}（${v.tz}）` : 'UNKNOWN'}`,
    sub: `+${formatTime(index, fps)} · ${v ? (v.declared ? 'DECLARED_DEMO_CLOCK' : 'CLOCK_UNDECLARED') : 'CLOCK_MAPPING_MISSING'}`,
  };
}
export function stampText(camera, index, fps, clock) {
  const p = stampParts(camera, index, fps, clock);
  return p.sub ? `${p.main}\n${p.sub}` : p.main;
}

export function mediaUrl(runKey, camera, index) {
  return `/media/${runKey}/${camera}/${frameName(index)}.png`;
}

// 播放排程：永遠逐格前進、不跳格。下一格到期且就緒才換；
// 落後超過一個間隔時重新對齊到期時間，並回報 late。
export const SPEEDS = Object.freeze([1, 1.5, 2]);
export function planTick({ now, nextDue, frame, total, fps, ready, speed = 1 }) {
  // 倍速只改變換格的牆鐘間隔；標籤與虛擬世界時間永遠由 frame index ÷ fps（來源時間）算出，不受倍速影響。
  const interval = 1000 / (fps * (SPEEDS.includes(speed) ? speed : 1));
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

// 實際倍速量測（只影響播放列小字）：視窗內「來源時間前進量 ÷ 牆鐘經過量」。影格沒就緒時播放會等待（不跳格），實際倍速自然降低；標籤與演示時間不受影響。
export function createSpeedMeter({ windowMs = 2000, minSpanMs = 500, maxStepFrames = 2 } = {}) {
  let samples = [];
  return {
    reset() { samples = []; },
    record(frame, fps, nowMs) {
      if (!Number.isFinite(frame) || !Number.isFinite(fps) || fps <= 0 || !Number.isFinite(nowMs)) return;
      const last = samples.at(-1);
      if (last && (frame < last.frame || frame - last.frame > maxStepFrames || nowMs < last.ms)) samples = [];   // 跳轉或倒退：重新量測
      samples.push({ frame, fps, ms: nowMs });
      while (samples.length > 2 && nowMs - samples[0].ms > windowMs) samples.shift();
    },
    // nowMs with nowMs the window ends at「now」で終わる：a stall (no new frame) lowers the figure instead of leaving a stale one。
    actual(nowMs = null) {
      if (samples.length < 2) return null;
      const live = Number.isFinite(nowMs) ? samples.filter((x) => nowMs - x.ms <= windowMs) : samples;
      if (live.length < 1) return null;
      const a = live[0], b = samples.at(-1), end = Number.isFinite(nowMs) ? Math.max(nowMs, b.ms) : b.ms, span = end - a.ms;
      if (span < minSpanMs) return null;
      return b === a ? 0 : ((b.frame - a.frame) / b.fps) / (span / 1000);
    },
  };
}
export function formatSpeedNote(setting, actual) {
  const x = (n) => `${Math.round(n * 10) / 10}×`;
  return Number.isFinite(actual) ? `設定 ${x(setting)} · 實際 ${x(actual)}` : `設定 ${x(setting)}`;
}

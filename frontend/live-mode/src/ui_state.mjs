// #677 LIVE UI/UX：沒有 DOM 的純函式（node 可測）。輸入只有後台經 protocol.mjs 白名單送來的欄位和 /config。
// 後台沒給的欄位一律顯示 UNKNOWN，不猜。

export const DEFAULT_MODEL = 'terra6.1';   // D237：UI 預設模型（後台 --advisor-model 預設不在這裡改）
export const SIDE_MIN = 240, SIDE_MAX = 640, SIDE_DEFAULT = 360;
export const PREFS_KEY = 'amidst.live.system.panel.v1';
const SAME_PERSON_M = 1.5;   // 與 candidates.py SAME_PERSON_M 相同：不同鏡頭、1.5 m 內視為同一人

export function defaultModel(models = [], current = null) {
  if (current && models.includes(current)) return current;
  return models.includes(DEFAULT_MODEL) ? DEFAULT_MODEL : (models[0] ?? null);
}

export const clampSideWidth = (w, max = SIDE_MAX) => {
  const n = Number(w);
  return Number.isFinite(n) ? Math.min(Math.min(SIDE_MAX, max), Math.max(SIDE_MIN, Math.round(n))) : SIDE_DEFAULT;
};

// localStorage 可能不存在、被擋或丟例外：讀寫都包起來，壞掉就用預設。
export function loadPanelPrefs(storage = globalThis.localStorage) {
  try {
    const raw = JSON.parse(storage.getItem(PREFS_KEY) || 'null');
    return { collapsed: raw?.collapsed === true, width: clampSideWidth(raw?.width ?? SIDE_DEFAULT) };
  } catch { return { collapsed: false, width: SIDE_DEFAULT }; }
}
export function savePanelPrefs(prefs, storage = globalThis.localStorage) {
  try { storage.setItem(PREFS_KEY, JSON.stringify({ collapsed: !!prefs.collapsed, width: clampSideWidth(prefs.width) })); return true; }
  catch { return false; }
}

// 操作端：回到選單＝同一頁去掉所有參數（有 run/actor/script/auto 的網址會跳過選單，所以返回一定清掉）。
export const backUrl = (loc = globalThis.location) => loc.pathname;
export const isBackKey = (event, doc) => event.key === 'Escape' && !doc?.pointerLockElement;   // Esc 先釋放滑鼠鎖定，再按一次才返回

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

// 把所有鏡頭的偵測合併成「人」：同色、1.5 m 內視為同一人。只用 est_xy（後台由像素投影，不是 GT）。
export function peopleFromDets(dets = {}) {
  const people = [];
  for (const [cam, list] of Object.entries(dets)) {
    for (const d of list || []) {
      if (!Array.isArray(d.est_xy) || !d.est_xy.every(Number.isFinite)) continue;
      const hit = people.find(p => p.color === d.color && dist(p.est_xy, d.est_xy) <= SAME_PERSON_M);
      if (hit) { hit.cams.push(cam); if ((d.score ?? 0) > hit.score) Object.assign(hit, { est_xy: d.est_xy, score: d.score ?? 0 }); }
      else people.push({ color: d.color, est_xy: d.est_xy, score: d.score ?? 0, cams: [cam] });
    }
  }
  return people;
}

export function sameColorCount(dets, color) {
  return color ? peopleFromDets(dets).filter(p => p.color === color).length : 0;
}

export const gateOf = (cfg = {}) => {
  const g = cfg.gate_m ?? cfg.tracker?.gate_m ?? cfg.schedule_policy?.gate_m;
  return Number.isFinite(g) ? g : null;
};

// 失聯時：列出畫面上的候選與沒接回的原因。
// 目前 API 沒有「每個候選為什麼被拒」，所以原因只能由前端用現有欄位推：顏色不符、距離。gate 不在 /config 時寫 UNKNOWN。
export function lostHint(tr, dets, cfg = {}) {
  if (!tr || (tr.lost_ticks || 0) <= 0) return null;
  const color = tr.target?.color ?? null, last = tr.est_xy ?? null, gate = gateOf(cfg);
  const people = peopleFromDets(dets);
  if (!people.length) return { color, last, gate, candidates: [], summary: '畫面沒有偵測到人', reason: 'UNKNOWN' };
  const candidates = people.map((p, i) => {
    const d = last ? dist(last, p.est_xy) : null;
    let reason;
    if (color && p.color !== color) reason = `顏色不符（${p.color === 'none' ? '無顏色' : p.color}）`;
    else if (d == null) reason = '原因：UNKNOWN（沒有上次位置）';
    else if (gate == null) reason = `距上次位置 ${d.toFixed(1)} m；gate：UNKNOWN`;
    else if (d > gate) reason = `超出 gate ${(d - gate).toFixed(1)} m（距離 ${d.toFixed(1)} m，gate ${gate} m）`;
    else reason = '在 gate 內，原因：UNKNOWN';
    return { number: i + 1, color: p.color, est_xy: p.est_xy, cams: p.cams, distance: d, reason };
  });
  const same = candidates.filter(c => c.color === color).length;
  return { color, last, gate, candidates, same, summary: `候選 ${candidates.length} 人，同色 ${same} 人`, reason: null };
}

export function sameColorNotice(n) { return n >= 2 ? `同色候選 ${n} 人，身分未確認` : ''; }

// 查看模式的兩種版面（純函式，不碰 DOM）。所有畫格維持 16:9，不拉伸、不裁切。
//   grid  ＝ A 自適應：依視窗長寬比比較各種欄數，選每格最大的排法。
//   focus ＝ B 焦點：主鏡頭放大在左（約 65%），其餘縮成小格排在右側。
export const LAYOUT_MODES = Object.freeze(['grid', 'focus']);
export const DEFAULT_LAYOUT = 'grid';
export const LAYOUT_STORAGE_KEY = 'amidst.eventViewer.layout';
export const GAP = 6;
export const FOCUS_RATIO = 0.65;
export const BANNER_H = 28;

const toInt = (n) => Math.max(0, Math.floor(Number(n) || 0));

// A：輸入視窗寬高、鏡頭數、間距；輸出欄數、列數、每格尺寸。
// 同樣大小時，空格少者優先，再取欄數少者（結果固定、與視窗無關的平手不會跳動）。
export function adaptiveGrid(count, width, height, gap = GAP) {
  const n = toInt(count);
  if (n === 0) return { cols: 0, rows: 0, width: 0, height: 0 };
  if (!(width > 0) || !(height > 0)) return { cols: Math.min(n, 4), rows: Math.ceil(n / Math.min(n, 4)), width: 0, height: 0 };
  let best = null;
  for (let cols = 1; cols <= n; cols++) {
    const rows = Math.ceil(n / cols);
    const byWidth = (width - gap * (cols - 1)) / cols;
    const byHeight = ((height - gap * (rows - 1)) / rows) * 16 / 9;
    const w = Math.max(0, Math.floor(Math.min(byWidth, byHeight)));
    const empty = cols * rows - n;
    if (!best || w > best.width || (w === best.width && (empty < best.empty || (empty === best.empty && cols < best.cols)))) best = { cols, rows, width: w, empty };
  }
  return { cols: best.cols, rows: best.rows, width: best.width, height: Math.floor((best.width * 9) / 16) };
}

// 把 count 個同尺寸畫格排進 width×height 內的矩形（置中，最後一列靠左）。
function placeGrid(count, f, originX, originY, areaW, areaH, gap) {
  const usedW = f.cols * f.width + gap * (f.cols - 1);
  const usedH = f.rows * f.height + gap * (f.rows - 1);
  const x0 = originX + Math.max(0, Math.floor((areaW - usedW) / 2));
  const y0 = originY + Math.max(0, Math.floor((areaH - usedH) / 2));
  return Array.from({ length: count }, (_, i) => ({
    x: x0 + (i % f.cols) * (f.width + gap), y: y0 + Math.floor(i / f.cols) * (f.height + gap), width: f.width, height: f.height,
  }));
}

// B：主畫面寬 ≈ 65%（受高度限制時縮小），上方留一條「追蹤中」標題；小格用同一個自適應演算法排進右側。
export function focusLayout(count, width, height, gap = GAP, ratio = FOCUS_RATIO, bannerH = BANNER_H) {
  const n = toInt(count);
  const empty = { main: { x: 0, y: 0, width: 0, height: 0 }, banner: { x: 0, y: 0, width: 0, height: 0 }, side: [], sideGrid: { cols: 0, rows: 0, width: 0, height: 0 } };
  if (n === 0 || !(width > 0) || !(height > 0)) return empty;
  if (n === 1) {
    const f = adaptiveGrid(1, width, Math.max(0, height - bannerH), gap);
    const [m] = placeGrid(1, f, 0, bannerH, width, height - bannerH, gap);
    return { ...empty, main: m, banner: { x: m.x, y: 0, width: m.width, height: bannerH } };
  }
  const availH = Math.max(0, height - bannerH);
  const mainW = Math.max(0, Math.min(Math.floor(width * ratio), Math.floor(availH * 16 / 9)));
  const mainH = Math.floor((mainW * 9) / 16);
  const sideW = Math.max(0, width - mainW - gap);
  const sideGrid = adaptiveGrid(n - 1, sideW, availH, gap);
  const side = placeGrid(n - 1, sideGrid, mainW + gap, bannerH, sideW, availH, gap).map((r) => ({ ...r, y: r.y }));
  const mainY = bannerH + Math.max(0, Math.floor((availH - mainH) / 2));
  return {
    main: { x: 0, y: mainY, width: mainW, height: mainH },
    banner: { x: 0, y: Math.max(0, mainY - bannerH), width: mainW, height: bannerH },
    side, sideGrid,
  };
}

// 主鏡頭：追蹤中的鏡頭 → 使用者點選的鏡頭 → 第一台。只接受目前 run 裡存在的鏡頭。
export function pickFocusCamera(cameras, tracked, selected) {
  const list = Array.isArray(cameras) ? cameras : [];
  if (tracked && list.includes(tracked)) return { camera: tracked, source: 'tracking' };
  if (selected && list.includes(selected)) return { camera: selected, source: 'selected' };
  return list.length ? { camera: list[0], source: 'default' } : { camera: null, source: 'none' };
}

// 每台鏡頭的矩形（相對於版面區左上角）。focus 模式主鏡頭 key 為 camera，其餘依原順序排在側欄。
export function layoutRects(mode, cameras, focusCamera, width, height, gap = GAP) {
  const list = Array.isArray(cameras) ? cameras : [];
  const rects = {};
  if (mode === 'focus' && list.length) {
    const focus = list.includes(focusCamera) ? focusCamera : list[0];
    const f = focusLayout(list.length, width, height, gap);
    rects[focus] = f.main;
    list.filter((c) => c !== focus).forEach((c, i) => { rects[c] = f.side[i]; });
    return { rects, banner: f.banner, focus, grid: f.sideGrid };
  }
  const g = adaptiveGrid(list.length, width, height, gap);
  placeGrid(list.length, g, 0, 0, width, height, gap).forEach((r, i) => { rects[list[i]] = r; });
  return { rects, banner: null, focus: null, grid: g };
}

// ---- localStorage（讀寫都可能丟例外：私密視窗、被封鎖、容量滿）；失敗就用預設值，頁面照常運作。
export function normalizeLayout(value) { return LAYOUT_MODES.includes(value) ? value : null; }

export function readStoredLayout(storage) {
  try { return normalizeLayout(storage.getItem(LAYOUT_STORAGE_KEY)) ?? DEFAULT_LAYOUT; } catch { return DEFAULT_LAYOUT; }
}

export function writeStoredLayout(storage, mode) {
  if (!normalizeLayout(mode)) return false;
  try { storage.setItem(LAYOUT_STORAGE_KEY, mode); return true; } catch { return false; }
}

// URL ?layout=grid|focus 優先（內嵌時由上層指定），其次 localStorage，最後預設格狀；?track=CAM_x 為追蹤中鏡頭（目前沒有來源，保留給 DP4）。
export function parseLayoutParams(search, cameras) {
  let p; try { p = new URLSearchParams(search ?? ''); } catch { p = new URLSearchParams(); }
  const track = p.get('track');
  return { layout: normalizeLayout(p.get('layout')), track: track && (cameras ?? []).includes(track) ? track : null };
}

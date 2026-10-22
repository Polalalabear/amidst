// Fixed chrome heights and the tile-size formula (design §4.1, §4.2). Pure; no DOM.

export const HEIGHTS = Object.freeze({ strip: 24, top: 44, q3bar: 40, vhead: 32, transport: 112, legend: 28 });
export const WIDTHS = Object.freeze({ icons: 48, panel: 300 });
export const NARROW_PX = 760;
export const GUTTER_PX = 16; // body side padding
export const MAIN_PADDING_PX = 8;
export const TILE_GAP_PX = 6;
export const TILE_CHROME_PX = 42; // 22 header + 18 footer + 2 border
export const WORK_BORDER_PX = 1;

export const GRID_SIZES = Object.freeze([1, 2, 4, 8]);

const GRID_SHAPES = Object.freeze({ 1: [1, 1], 2: [2, 1], 4: [2, 2], 8: [4, 2] });
const GRID_SHAPES_NARROW = Object.freeze({ 1: [1, 1], 2: [2, 1], 4: [2, 2], 8: [2, 4] });

export function gridShape(size, narrow = false) {
  const shape = (narrow ? GRID_SHAPES_NARROW : GRID_SHAPES)[size];
  if (!shape) throw new RangeError(`unsupported grid size: ${size}`);
  return { cols: shape[0], rows: shape[1] };
}

// W, H are the main area minus its 8 px padding. Tile image is 16:9.
// w = min((W - 6(c-1))/c, ((H - 6(r-1))/r - 42) * 16/9), floored; h = round(w * 9/16).
export function fitTiles({ size, width, height, narrow = false }) {
  const { cols, rows } = gridShape(size, narrow);
  const byWidth = (width - TILE_GAP_PX * (cols - 1)) / cols;
  const byHeight = ((height - TILE_GAP_PX * (rows - 1)) / rows - TILE_CHROME_PX) * 16 / 9;
  const w = Math.max(0, Math.floor(Math.min(byWidth, byHeight)));
  return { cols, rows, width: w, height: Math.round((w * 9) / 16) };
}

// Columns to the left of the main area for each rail state. Overlay floats above, so it costs only the icon strip.
export function railWidth(rail, narrow = false) {
  if (narrow) return 0;
  return rail === 'pinned' ? WIDTHS.icons + WIDTHS.panel : WIDTHS.icons;
}

export function fixedChromeHeight({ synthetic = true, q = false } = {}) {
  const { strip, top, vhead, transport, legend } = HEIGHTS;
  return (synthetic ? strip : 0) + top + vhead + transport + legend + (q ? HEIGHTS.q3bar : 0);
}

// Padded main-area size used by fitTiles, from the viewport. 1440x900 pinned -> 1044x643, otherwise 1344x643.
export function mainAreaSize({ viewportWidth, viewportHeight, rail, synthetic = true, q = false }) {
  const narrow = viewportWidth < NARROW_PX;
  const bodyWidth = viewportWidth - 2 * GUTTER_PX;
  return {
    width: bodyWidth - railWidth(rail, narrow) - 2 * MAIN_PADDING_PX,
    height: viewportHeight - fixedChromeHeight({ synthetic, q }) - WORK_BORDER_PX - 2 * MAIN_PADDING_PX,
    narrow,
  };
}

// Vertical order of the page, top to bottom. The transport bar sits directly under the main view.
export const VERTICAL_ORDER = Object.freeze(['synthetic-strip', 'topbar', 'main-head', 'main-view', 'transport', 'legend']);

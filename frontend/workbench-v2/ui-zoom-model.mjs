// D139 whole-interface scale (display only): the front desk is zoomed as one piece (text, layout, images). Percent values only;
// no data, no request and no inference input changes.
export const ZOOM_LEVELS = Object.freeze([80, 90, 100, 110, 125]);
export const DEFAULT_ZOOM = 100;
export const ZOOM_STORAGE_KEY = 'amidst.ui.zoom.v1';
export const normalizeZoom = v => { const n = Number(v); return ZOOM_LEVELS.includes(n) ? n : DEFAULT_ZOOM; };

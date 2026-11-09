// D147 (2026-11-09): camera-picture scale (display only). The user clarified that the size control resizes the camera pictures
// (tracking stage, multi-view tiles, search result cards, monitor wall), not the whole interface; text and layout stay put.
// Percent values only; no data, no request and no inference input changes.
export const ZOOM_LEVELS = Object.freeze([60, 80, 100, 125, 150]);
export const DEFAULT_ZOOM = 100;
export const ZOOM_STORAGE_KEY = 'amidst.ui.zoom.v1';
export const normalizeZoom = v => { const n = Number(v); return ZOOM_LEVELS.includes(n) ? n : DEFAULT_ZOOM; };
// search result wall: columns per camera-picture scale (bigger pictures, fewer columns)
export const WALL_COLUMNS = Object.freeze({60: 4, 80: 3, 100: 2, 125: 1, 150: 1});
export const wallColumns = z => WALL_COLUMNS[normalizeZoom(z)];

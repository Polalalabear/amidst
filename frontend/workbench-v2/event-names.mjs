// Short event names for presentation mode (D139). Pure; keyed by run_id / recording_id, never by title text.
// Provenance of each name: docs/operations/EVENT_NAMES.md. Titles from the bootstrap are NOT changed (real-e2e finds runs by title prefix).
const entry = (short, desc = null) => Object.freeze({short, desc});
export const EVENT_NAMES = Object.freeze({
  'ENGINEERING_DYNAMIC_RUN_20261025': entry('B-05', '8 秒工程場景'),
  'ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1': entry('A4-1', '室外→入口→走廊'),
  'ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1': entry('B4-1', '走廊→轉角→R101'),
  'r005-static-reviewed-v2': entry('r005', '六張靜態圖'),
  // Stand-ins served by tests/browser/core-preview/preview-server.mjs (synthetic, no description).
  'SYNTHETIC_B05': entry('B-05'),
  'SYNTHETIC_A4_1': entry('A4-1'),
  'SYNTHETIC_B4_1': entry('B4-1'),
  // Recorded response of the B-05 cut (event-menu.mjs B05B_RECORDING_ID).
  '2777741d96ac9aff5bffb2f61a4d2938': entry('B-05', '預錄切鏡'),
});

// Name shown in presentation mode. Unknown ids get a neutral ordinal, never the raw title or id.
export function shortEventName(id, index = 0) {
  const e = Object.hasOwn(EVENT_NAMES, id) ? EVENT_NAMES[id] : null;
  return e ? (e.desc ? `${e.short} · ${e.desc}` : e.short) : `事件 ${index + 1}`;
}
// present=false → the full technical title, as before.
export function eventDisplayName(run, {present, index = 0} = {}) {
  const id = run?.run_id ?? run?.recording_id;
  return present ? shortEventName(id, index) : (run?.title ?? id ?? '');
}

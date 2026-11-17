// Human-readable names for r004 places (graph v3 region ids) and cameras, shared by the front desk and the admin.
// Display only: requests, logs and evidence keep the technical code, and the code stays visible as a tooltip / small text.
//
// Every name is taken from an existing source; nothing is invented. `status`:
//   PROPOSED  — configs/q1q5/query_alias_v1.json (region aliases, status PROPOSED there).
//   DERIVED   — wording taken from docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md (the scene description), not a
//               declared official name. Needs the user's confirmation.
//   UNKNOWN   — no source gives a name or a distinguishing description; the code is shown as the name.
// `source` points at the line of evidence. A run's own region catalog label wins when it is not just the code.

const CARDS = 'docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md';
const ALIAS = 'configs/q1q5/query_alias_v1.json';
const row = (name, status, source) => Object.freeze({name, status, source});

export const PLACE_NAMES = Object.freeze({
  OUT_W: row('西入口外', 'DERIVED', `${CARDS} §2.1 A4-1 段 0、4：「OUT_W 車旁 → 西入口前」「入口外的共視區」`),
  VEST_W: row('門廳', 'DERIVED', `${CARDS} §2.1 A4-1 段 1：VEST_W「穿過門廳」`),
  CORR_W: row('走廊', 'DERIVED', `${CARDS} §2.1 A4-1 段 2：CORR_W「進走廊」；§3 標題「走廊 → 轉角 → R101」`),
  CORNER: row('轉角', 'DERIVED', `${CARDS} §3.1 B4-1 段 1–2：「轉進轉角」CORNER`),
  CORR_N: row('北段走廊', 'DERIVED', `${CARDS} §3.1 B4-1 偏離表：「走進 CORR_N 北段」`),
  R101: row('101 教室', 'PROPOSED', `${ALIAS}：「101教室」→ R101`),
  R102: row('102 教室', 'PROPOSED', `${ALIAS}：「102教室」→ R102`),
});

export const CAMERA_NAMES = Object.freeze({
  CAM_W1: row('走廊（門廳端）', 'DERIVED', `${CARDS} §1.5：「W1 從門廳端看向轉角」`),
  CAM_W2: row('走廊（轉角端）', 'DERIVED', `${CARDS} §1.5：「W2 從轉角端看向門廳」`),
  CAM_ENTRY: row('門廳', 'DERIVED', `${CARDS} §2.1 A4-1 段 1：VEST_W「ENTRY 看得到但只供查找」`),
  CAM_R101_IN: row('101 教室內', 'DERIVED', `${CARDS} §1.6：「R101 室內（只有 R101_IN 一台）」；教室名見 ${ALIAS}`),
  CAM_EXT_CAR: row('西入口外（車旁）', 'DERIVED', `${CARDS} §2.1 主要風險 3：「只有 EXT_CAR 看得到的車旁」`),
  CAM_EXT_CLEAR: row('CAM_EXT_CLEAR', 'UNKNOWN', `${CARDS} 只寫它看 OUT_W，沒有和 EXT_CAR 區分的描述`),
  CAM_BRANCH: row('CAM_BRANCH', 'UNKNOWN', `${CARDS} 只寫「轉角由 BRANCH 與 WIDE 共視」，沒有區分兩台的描述`),
  CAM_WIDE: row('CAM_WIDE', 'UNKNOWN', `${CARDS} 只寫「轉角由 BRANCH 與 WIDE 共視」，沒有區分兩台的描述`),
});

const entry = (table, id) => (typeof id === 'string' && Object.hasOwn(table, id) ? table[id] : null);

// Name for a region id. `catalogLabel` (run.region_catalog label) wins unless it only repeats the code.
export function placeName(id, catalogLabel = null) {
  if (typeof catalogLabel === 'string' && catalogLabel && catalogLabel !== id) return catalogLabel;
  const e = entry(PLACE_NAMES, id);
  return e && e.status !== 'UNKNOWN' ? e.name : id ?? '';
}

export function cameraName(id) {
  const e = entry(CAMERA_NAMES, id);
  return e && e.status !== 'UNKNOWN' ? e.name : id ?? '';
}

// {name, code, known}: `known` false means the name is the code itself (no readable name), so callers skip the small code.
export function placeLabel(id, catalogLabel = null) { const name = placeName(id, catalogLabel); return {name, code: id ?? '', known: name !== id}; }
export function cameraLabel(id) { const name = cameraName(id); return {name, code: id ?? '', known: name !== id}; }

// Tooltip text: name, code and where the name came from (so the user can tell a derived name from an official one).
export function nameTitle(id, kind = 'camera') {
  const e = entry(kind === 'camera' ? CAMERA_NAMES : PLACE_NAMES, id);
  if (!e) return id ?? '';
  return e.status === 'UNKNOWN' ? `${id} · 名稱 UNKNOWN（待確認）` : `${e.name} · ${id}${e.status === 'DERIVED' ? ' · 名稱取自場景卡，待確認' : ' · 名稱 PROPOSED'}`;
}

// Everything still waiting for the user's confirmation (listed in the PR).
export function namesToConfirm() {
  const out = [];
  for (const [kind, table] of [['place', PLACE_NAMES], ['camera', CAMERA_NAMES]])
    for (const [id, e] of Object.entries(table)) if (e.status !== 'CONFIRMED') out.push({kind, id, ...e});
  return out;
}

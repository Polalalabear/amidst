// 2D 同步畫面格數（1／2／4／8）的純邏輯。依據：OFFICE_CONTROLLED_SCENE_V1 §2.2、§2.3、§6.2、CS-Q13，
// 與 CONTROLLED_SCENE_UX_SKETCH §3、§7（均以 2643771 為準）。不依賴 DOM；renderGrid 只用呼叫端傳入的 container。
// 不改變任何證據狀態：這裡只決定「顯示哪些鏡頭、哪個 frame index、每格什麼狀態」。

export const GRID_SIZES = Object.freeze([1, 2, 4, 8]);
export const MAX_CAMERAS_PER_REQUEST = 8;
export const SYNCED_FRAMES_SCHEMA = "controlled-scene.synced-frames.v1";
export const SYNCED_FRAMES_REQUEST_SCHEMA = "controlled-scene.synced-frames-request.v1";
export const TILE_STATUSES = Object.freeze(["READY", "MISSING", "OUT_OF_RANGE", "UNKNOWN"]);
export const EMPTY_SLOT_LABEL = "無更多候選";

const LAYOUTS = Object.freeze({
  1: { cols: 1, rows: 1 },
  2: { cols: 2, rows: 1 },
  4: { cols: 2, rows: 2 },
  8: { cols: 4, rows: 2 },
});

export function layoutFor(size) {
  if (!GRID_SIZES.includes(size)) throw new RangeError(`格數必須是 ${GRID_SIZES.join("／")}，收到 ${size}`);
  return { size, ...LAYOUTS[size] };
}

// ---- 狀態（不可變） -------------------------------------------------------

function dedupe(ids) {
  const seen = new Set();
  const out = [];
  for (const id of ids) {
    if (typeof id !== "string" || id === "") throw new TypeError("camera_id 必須是非空字串");
    if (!seen.has(id)) { seen.add(id); out.push(id); }
  }
  return out;
}

// candidates：依排序的 camera_id 全集合（不因格數截斷）。
export function createGridState({ candidates, size = 4, pinned = null, page = 0, fixtureIds = [] }) {
  const state = {
    candidates: Object.freeze(dedupe(candidates)),
    size: layoutFor(size).size,
    pinned: null,
    page: 0,
    fixtureIds: Object.freeze([...fixtureIds]),
  };
  return withPage(withPin(state, pinned), page);
}

export function setCandidates(state, candidates) {
  const next = { ...state, candidates: Object.freeze(dedupe(candidates)) };
  if (next.pinned && !next.candidates.includes(next.pinned)) next.pinned = null;
  return withPage(next, next.page);
}

export function setSize(state, size) {
  return withPage({ ...state, size: layoutFor(size).size }, 0);
}

export function withPin(state, cameraId) {
  // 解除釘選會改變分頁數，頁碼一律重新夾回範圍。
  if (cameraId == null) return withPage({ ...state, pinned: null }, state.page);
  // 釘選一台不在候選集合內的鏡頭 → 忽略（不憑空加入候選）。
  if (!state.candidates.includes(cameraId)) return withPage({ ...state, pinned: null }, state.page);
  return withPage({ ...state, pinned: cameraId }, state.page);
}

export function withPage(state, page) {
  const count = pageCount(state);
  const clamped = Math.min(Math.max(Number.isInteger(page) ? page : 0, 0), count - 1);
  return { ...state, page: clamped };
}

// 釘選只改版面，不改排序。size>1：釘選鏡頭固定在每一頁第 1 格，其餘依排序遞補（每頁 size-1 台）。
// size=1：釘選鏡頭排到第 1 頁，其餘依序翻頁。（規格未說明 size=1 + 釘選的翻頁行為，見 PR 的 UNKNOWN。）
function pagination(state) {
  const { candidates, size, pinned } = state;
  if (candidates.length === 0) return { pinSlot: false, perPage: size, rest: [] };
  if (pinned && size > 1) {
    return { pinSlot: true, perPage: size - 1, rest: candidates.filter((id) => id !== pinned) };
  }
  if (pinned) {
    return { pinSlot: false, perPage: 1, rest: [pinned, ...candidates.filter((id) => id !== pinned)] };
  }
  return { pinSlot: false, perPage: size, rest: candidates };
}

export function pageCount(state) {
  const { perPage, rest } = pagination(state);
  return Math.max(1, Math.ceil(rest.length / perPage));
}

// 當頁的 slot 清單。不足的 slot 是 EMPTY，永遠不複製鏡頭補位。
export function pageView(state) {
  const { size } = state;
  const layout = layoutFor(size);
  const { pinSlot, perPage, rest } = pagination(state);
  const pageIds = rest.slice(state.page * perPage, (state.page + 1) * perPage);
  const slots = [];
  if (pinSlot) slots.push(cameraSlot(state, state.pinned));
  for (const id of pageIds) slots.push(cameraSlot(state, id));
  while (slots.length < size) slots.push({ kind: "EMPTY", label: EMPTY_SLOT_LABEL });
  slots.forEach((s, i) => { s.slot = i; });
  const cameraIds = slots.filter((s) => s.kind === "CAMERA").map((s) => s.camera_id);
  return {
    layout,
    page: state.page,
    page_count: pageCount(state),
    page_label: `第 ${state.page + 1}／${pageCount(state)} 頁`,
    total_candidates: state.candidates.length,
    slots,
    camera_ids: cameraIds,
  };
}

function cameraSlot(state, id) {
  return {
    kind: "CAMERA",
    camera_id: id,
    rank: state.candidates.indexOf(id) + 1,
    pinned: id === state.pinned,
    fixture: state.fixtureIds.includes(id),
  };
}

// ---- 時間游標 -------------------------------------------------------------

// 以數字的十進位最短表示轉成精確有理數，避免 0.6*5 之類的浮點誤差，也不偷加 epsilon（契約 §6.2）。
function toRational(x) {
  if (!Number.isFinite(x)) throw new RangeError("時間必須是有限數");
  const s = x.toString();
  const m = /^(-?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(s);
  if (!m) throw new RangeError(`無法解析時間 ${s}`);
  const frac = m[3] || "";
  let num = BigInt(m[2] + frac);
  let den = 10n ** BigInt(frac.length);
  const exp = m[4] ? Number(m[4]) : 0;
  if (exp > 0) num *= 10n ** BigInt(exp); else if (exp < 0) den *= 10n ** BigInt(-exp);
  if (m[1]) num = -num;
  return { num, den };
}

// LATEST_AT_OR_BEFORE：timestamp_s <= t 的最後一個 sample。run 為半開區間 [0, duration_s)。
// 缺檔不在這裡判斷，也不回退（契約 §2.2）。
export function expectedFrame(t_s, { fps, duration_s }) {
  if (!Number.isInteger(fps) || fps <= 0) throw new RangeError("fps 必須是正整數");
  const t = toRational(t_s);
  const d = toRational(duration_s);
  // 契約 §2：duration_s × fps 必須是整數，否則設定本身不合法。
  if ((d.num * BigInt(fps)) % d.den !== 0n) throw new RangeError("duration_s × fps 必須是整數");
  const below = t.num < 0n;
  const atOrAfterEnd = t.num * d.den >= d.num * t.den;
  if (below || atOrAfterEnd) return { in_range: false, expected_frame_index: null, expected_timestamp_s: null, sample_age_s: null };
  const index = Number((t.num * BigInt(fps)) / t.den);
  const timestamp = index / fps;
  return { in_range: true, expected_frame_index: index, expected_timestamp_s: timestamp, sample_age_s: Math.round((t_s - timestamp) * 1e9) / 1e9 };
}

// ---- 請求 -----------------------------------------------------------------

export function buildSyncedFramesRequest(view, { session_ref, scene_id, run_id, t_s }) {
  if (view.camera_ids.length === 0) throw new RangeError("當頁沒有鏡頭，不送請求");
  if (view.camera_ids.length > MAX_CAMERAS_PER_REQUEST) throw new RangeError("每次最多 8 台");
  return { schema_version: SYNCED_FRAMES_REQUEST_SCHEMA, session_ref, scene_id, run_id, t_s, camera_ids: [...view.camera_ids] };
}

// ---- response → 顯示模型 --------------------------------------------------

const BADGE = Object.freeze({
  READY: { label: "READY", showImage: true, hatched: false, mark: null },
  MISSING: { label: "MISSING", showImage: false, hatched: true, mark: null },
  OUT_OF_RANGE: { label: "OUT_OF_RANGE", showImage: false, hatched: false, mark: null },
  UNKNOWN: { label: "UNKNOWN", showImage: false, hatched: false, mark: "?" },
});

function failClosed(code, message, detail) {
  return Object.freeze({ ok: false, error: { code, message, ...(detail ? { detail } : {}) }, tiles: [] });
}

// 完整性錯誤的回應形狀契約沒有定義（見 PR UNKNOWN）；此處接受 {error:{code|error_class, reason}} 或 DataIntegrityError 字樣。
function integrityErrorOf(response) {
  const e = response && response.error;
  if (!e) return null;
  const code = e.error_class || e.code || e.type || "";
  const reason = e.reason || e.reason_code || e.message || "";
  return { code: String(code), reason: String(reason) };
}

// view：pageView() 的結果（要求的鏡頭與 slot）。response：POST /api/synced_frames 的 JSON。
// 任何不符都整頁 fail closed：不回傳任何 tile，更不降格成 MISSING。
// requestedTimeS：請求的 t_s。run：{fps, duration_s}，有給時用它核對 expected_frame_index。
export function toDisplayModel(view, response, { requestedTimeS = null, run = null } = {}) {
  if (!response || typeof response !== "object") return failClosed("MALFORMED_RESPONSE", "同步影格回應無法解析，整頁不顯示影格");
  const ie = integrityErrorOf(response);
  if (ie) return failClosed(ie.code || "DataIntegrityError", `完整性錯誤：${ie.reason || ie.code}。整個 run 無法載入，不顯示任何影格`, ie);
  if (response.schema_version !== SYNCED_FRAMES_SCHEMA) return failClosed("SCHEMA_MISMATCH", `schema_version 不符：${response.schema_version}`);
  if (!Array.isArray(response.tiles)) return failClosed("MALFORMED_RESPONSE", "回應缺少 tiles[]");

  if (requestedTimeS != null && response.t_s !== requestedTimeS) {
    return failClosed("STALE_RESPONSE", `回應的 t_s（${response.t_s}）與請求（${requestedTimeS}）不同，整頁不顯示影格`);
  }
  if (run && requestedTimeS != null) {
    const exp = expectedFrame(requestedTimeS, run);
    if (exp.in_range && response.expected_frame_index !== exp.expected_frame_index) {
      return failClosed("FRAME_NOT_ON_EXPECTED_GRID", `expected_frame_index（${response.expected_frame_index}）不是依 grid 算出的 ${exp.expected_frame_index}`);
    }
  }

  const wanted = view.camera_ids;
  const byId = new Map();
  for (const tile of response.tiles) {
    if (!tile || typeof tile.camera_id !== "string") return failClosed("MALFORMED_RESPONSE", "tile 缺少 camera_id");
    if (byId.has(tile.camera_id)) return failClosed("MALFORMED_RESPONSE", `tile 重複：${tile.camera_id}`);
    if (!wanted.includes(tile.camera_id)) return failClosed("UNREQUESTED_CAMERA", `回應含未請求的鏡頭：${tile.camera_id}`);
    if (!TILE_STATUSES.includes(tile.status)) return failClosed("UNKNOWN_TILE_STATUS", `未定義的 tile 狀態：${tile.status}`, { camera_id: tile.camera_id });
    const bad = tileInvariantViolation(tile);
    if (bad) return failClosed("MALFORMED_TILE", bad, { camera_id: tile.camera_id });
    // READY 必須就是預期 grid 上的那一格（契約 §2.2：不得回退到較早的可用影格）。
    if (tile.status === "READY" && tile.timestamp_s !== response.expected_timestamp_s) {
      return failClosed("FRAME_NOT_ON_EXPECTED_GRID", `${tile.camera_id} 的 READY 影格時間 ${tile.timestamp_s} ≠ 預期 ${response.expected_timestamp_s}`, { camera_id: tile.camera_id });
    }
    byId.set(tile.camera_id, tile);
  }
  for (const id of wanted) {
    if (!byId.has(id)) return failClosed("MISSING_TILE_IN_RESPONSE", `回應缺少已請求鏡頭的 tile：${id}（不自行補成 MISSING）`);
  }

  const tiles = view.slots.map((slot) => {
    if (slot.kind === "EMPTY") return { slot: slot.slot, kind: "EMPTY", label: slot.label };
    const t = byId.get(slot.camera_id);
    const b = BADGE[t.status];
    return {
      slot: slot.slot,
      kind: "CAMERA",
      camera_id: t.camera_id,
      rank: slot.rank,
      pinned: slot.pinned,
      fixture: slot.fixture,
      status: t.status,
      badge: b.label,
      show_image: b.showImage,
      hatched: b.hatched,
      mark: b.mark,
      frame_ref: t.frame_ref ?? null,
      timestamp_s: t.status === "READY" ? t.timestamp_s : null,
      clock_error_s: t.status === "READY" ? (t.clock_error_s ?? null) : null,
      file_sha256: t.status === "READY" ? t.file_sha256 : null,
      reason: t.reason ?? null,
    };
  });

  return Object.freeze({
    ok: true,
    t_s: response.t_s,
    clock_id: response.clock_id,
    sampling_version: response.sampling_version,
    expected_frame_index: response.expected_frame_index ?? null,
    expected_timestamp_s: response.expected_timestamp_s ?? null,
    sample_age_s: response.sample_age_s ?? null,
    time_matches_request: requestedTimeS == null ? null : response.t_s === requestedTimeS,
    page_label: view.page_label,
    layout: view.layout,
    watermark: response.fixture_marker || tiles.some((t) => t.fixture) ? "FIXTURE" : null,
    identity_verdict: "UNCONFIRMED",
    tiles,
  });
}

function tileInvariantViolation(tile) {
  if (tile.status === "READY") {
    if (!tile.frame_ref) return "READY 需要 frame_ref";
    if (!tile.file_sha256) return "READY 需要 file_sha256";
    if (typeof tile.timestamp_s !== "number") return "READY 需要 timestamp_s";
  } else {
    if (tile.frame_ref != null) return `${tile.status} 不得帶 frame_ref（不用其他影格補）`;
    if (!tile.reason) return `${tile.status} 需要 reason`;
  }
  return null;
}

// ---- 薄 render：只輸出結構與 data-* 屬性，不寫 class／style／配色（視覺由外框決定） ----
// 容器：data-grid-state="OK|ERROR"、data-cols/rows；每格：data-slot、data-kind、data-state、data-camera-id、
// data-hatched／data-mark／data-pinned／data-fixture。frameUrl 由呼叫端提供，這裡不組路徑。

export function renderGrid(container, model, { frameUrl = null, onPin = null } = {}) {
  const doc = container.ownerDocument;
  container.replaceChildren();
  if (!model.ok) {
    container.dataset.gridState = "ERROR";
    delete container.dataset.cols;
    delete container.dataset.rows;
    delete container.dataset.watermark;
    const err = doc.createElement("div");
    err.dataset.role = "error";
    err.dataset.errorCode = model.error.code;
    err.setAttribute("role", "alert");
    err.textContent = model.error.message;
    container.append(err);
    return;
  }
  container.dataset.gridState = "OK";
  container.dataset.cols = String(model.layout.cols);
  container.dataset.rows = String(model.layout.rows);
  if (model.watermark) container.dataset.watermark = model.watermark; else delete container.dataset.watermark;
  for (const tile of model.tiles) {
    const el = doc.createElement("div");
    el.dataset.slot = String(tile.slot);
    el.dataset.kind = tile.kind;
    if (tile.kind === "EMPTY") {
      el.dataset.state = "EMPTY";
      el.textContent = tile.label;
      container.append(el);
      continue;
    }
    el.dataset.state = tile.status;
    el.dataset.cameraId = tile.camera_id;
    if (tile.hatched) el.dataset.hatched = "true";
    if (tile.mark) el.dataset.mark = tile.mark;
    if (tile.pinned) el.dataset.pinned = "true";
    if (tile.fixture) el.dataset.fixture = "true";
    if (tile.show_image && frameUrl) {
      const img = doc.createElement("img");
      img.src = frameUrl(tile);
      img.alt = `${tile.camera_id} @ ${tile.timestamp_s}s`;
      el.append(img);
    }
    const tag = doc.createElement("div");
    tag.dataset.role = "tag";
    const ts = tile.timestamp_s == null ? "" : ` ${tile.timestamp_s.toFixed(1)} s`;
    tag.textContent = `${tile.camera_id}${ts} ${tile.badge}${tile.mark ? ` ${tile.mark}` : ""}`;
    el.append(tag);
    if (onPin) el.addEventListener("click", () => onPin(tile.camera_id));
    container.append(el);
  }
}

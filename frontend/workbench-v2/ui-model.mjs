// Pure model for the redesigned front desk (docs/specs/UI_REDESIGN_V1.md). No DOM, no network.
// Everything here derives from the existing API responses / view models; a number with no measured source is
// reported as null so the view can print 尚未量測 (never an example value).

export const SETTINGS_KEY = 'amidst.ui.settings.v1';
export const SNAPSHOT_KEY = 'amidst.ui.snapshot.v1';
export const EVENTLOG_KEY = 'amidst.ui.eventlog.v1';
export const EVENTLOG_LIMIT = 60;
export const NOT_MEASURED = '尚未量測';

export const CASES = Object.freeze([
  Object.freeze({ id: 'case1', no: 'case 1', title: '查找', blurb: '指定時間，再加上地點或特徵，找出出現過的畫面。' }),
  Object.freeze({ id: 'case2', no: 'case 2', title: '追蹤', blurb: '鎖定目標後鏡頭自動切換，盲區在俯視圖畫出推測路線。' }),
  Object.freeze({ id: 'case3', no: 'case 3', title: '查看', blurb: '回放整段事件，同時看所有鏡頭與時間軸。' }),
]);
export const CASE_IDS = Object.freeze(CASES.map(c => c.id));
export const SPEEDS = Object.freeze([0.5, 1, 1.5, 2]);
export const EVENT_CHOICES = Object.freeze([
  Object.freeze({ id: 'b05b', label: 'B-05' }),
  Object.freeze({ id: 'a41', label: 'A4-1' }),
  Object.freeze({ id: 'b41', label: 'B4-1' }),
]);

export const DEFAULT_SETTINGS = Object.freeze({
  defaultCase: null,          // null = show the three-way chooser
  defaultEvent: 'b05b',
  coverAnimation: true,
  trackLayout: 'single',
  trackSpeed: 1,
  blindPlan: true,
  keepBlindSec: 30,
  resultLimit: 24,
  searchPanelOpen: false,
  staggerResults: true,
  switchMode: 'RULE_ONLY',
  presentationMode: true,     // D139: front desk shows plain wording; technical tags move into ⓘ
});

const clampInt = (v, lo, hi, d) => { const n = Math.trunc(Number(v)); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d; };
export function normalizeSettings(raw) {
  const r = raw && typeof raw === 'object' ? raw : {};
  const d = DEFAULT_SETTINGS;
  return {
    defaultCase: CASE_IDS.includes(r.defaultCase) ? r.defaultCase : d.defaultCase,
    defaultEvent: EVENT_CHOICES.some(e => e.id === r.defaultEvent) ? r.defaultEvent : d.defaultEvent,
    coverAnimation: typeof r.coverAnimation === 'boolean' ? r.coverAnimation : d.coverAnimation,
    trackLayout: ['single', 'multi'].includes(r.trackLayout) ? r.trackLayout : d.trackLayout,
    trackSpeed: SPEEDS.includes(r.trackSpeed) ? r.trackSpeed : d.trackSpeed,
    blindPlan: typeof r.blindPlan === 'boolean' ? r.blindPlan : d.blindPlan,
    keepBlindSec: clampInt(r.keepBlindSec, 1, 600, d.keepBlindSec),
    resultLimit: clampInt(r.resultLimit, 1, 200, d.resultLimit),
    searchPanelOpen: typeof r.searchPanelOpen === 'boolean' ? r.searchPanelOpen : d.searchPanelOpen,
    staggerResults: typeof r.staggerResults === 'boolean' ? r.staggerResults : d.staggerResults,
    switchMode: ['RULE_ONLY', 'AGENT_SEQUENTIAL'].includes(r.switchMode) ? r.switchMode : d.switchMode,
    presentationMode: typeof r.presentationMode === 'boolean' ? r.presentationMode : d.presentationMode,
  };
}
// Browser-only storage (task: settings live in this browser). Every access is guarded: a blocked storage keeps defaults.
export function readJson(storage, key, fallback = null) {
  try { const t = storage?.getItem(key); return t ? JSON.parse(t) : fallback; } catch { return fallback; }
}
export function writeJson(storage, key, value) {
  try { storage?.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
}
export const loadSettings = storage => normalizeSettings(readJson(storage, SETTINGS_KEY));
export const saveSettings = (storage, s) => writeJson(storage, SETTINGS_KEY, normalizeSettings(s));

// ---- Query windows ----------------------------------------------------------------------------------------------
export const FORM_TEXT = Object.freeze({
  TIME_REQUIRED: '請輸入開始與結束時間',
  LOCATION_OR_FEATURE_REQUIRED: '地點與特徵至少選一項',
  FEATURE_REQUIRED: '請先選特徵',
});
const filled = v => String(v ?? '').trim() !== '';
export function validateSearchForm({ start = '', end = '', regionIds = [], classLabel = '' } = {}) {
  if (!filled(start) || !filled(end)) return { ok: false, code: 'TIME_REQUIRED', text: FORM_TEXT.TIME_REQUIRED };
  if (!(regionIds?.length > 0) && !filled(classLabel)) return { ok: false, code: 'LOCATION_OR_FEATURE_REQUIRED', text: FORM_TEXT.LOCATION_OR_FEATURE_REQUIRED };
  return { ok: true, code: null, text: '' };
}
export function validateTrackForm({ classLabel = '' } = {}) {
  return filled(classLabel) ? { ok: true, code: null, text: '' } : { ok: false, code: 'FEATURE_REQUIRED', text: FORM_TEXT.FEATURE_REQUIRED };
}
// D139-1: group the feature options by what this run's detector actually saw. `counts` is the bootstrap run's
// detected_class_counts ([{class_label, detection_count}], model detections incl. false positives, not object counts).
// Missing / empty / malformed counts → grouped:false and the caller keeps the single flat list. `supports(label)` marks
// classes the current operation cannot use (tracking: person only); they stay listed but disabled.
export const DETECTION_COUNT_NOTE = '模型偵測筆數，含誤判，不是實際物件數';
export const CAMERA_COUNT_NOTE = '照到這個類別的鏡頭數（模型偵測，可能含誤判）';
// D147-1: the classes each scene actually contains, as declared by the user from the authored scenes (2026-11-09). Presentation only:
// it decides which chips sit in the top group; it never filters detections, ranks results or feeds inference. Runs not listed keep D139-1.
export const SCENE_FEATURED_CLASSES = Object.freeze({
  ENGINEERING_DYNAMIC_RUN_20261025: Object.freeze(['person']),              // B-05
  'ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1': Object.freeze(['person', 'car']), // A4-1
  'ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1': Object.freeze(['person']),       // B4-1
});
export function featuredClasses(runId) { return SCENE_FEATURED_CLASSES[runId] ?? null; }
export function classGroups(classes, counts, supports = () => true, featured = null) {
  const all = (Array.isArray(classes) ? classes : []).filter(c => typeof c === 'string' && c);
  const known = new Set(all), seen = new Set(), detected = [];
  if (Array.isArray(counts)) for (const r of counts) {
    const label = r?.class_label, n = r?.detection_count;
    if (typeof label !== 'string' || !known.has(label) || seen.has(label) || !Number.isInteger(n) || n <= 0) continue;
    const cc = r?.camera_count; seen.add(label); detected.push({ label, count: n, cameraCount: Number.isInteger(cc) && cc > 0 ? cc : null, supported: supports(label) !== false });
  }
  detected.sort((a, b) => b.count - a.count || (a.label < b.label ? -1 : a.label > b.label ? 1 : 0));
  const pick = Array.isArray(featured) ? [...new Set(featured.filter(c => known.has(c)))] : [];
  if (pick.length) {
    // featured scene classes on top, in the declared order; a featured class the detector never saw shows 0 cameras rather than hiding.
    const byLabel = new Map(detected.map(d => [d.label, d])), top = pick.map(label => byLabel.get(label) ?? { label, count: 0, cameraCount: Array.isArray(counts) ? 0 : null, supported: supports(label) !== false });
    const rest = [...detected.filter(d => !pick.includes(d.label)).map(d => d.label), ...all.filter(c => !seen.has(c) && !pick.includes(c))];
    return { grouped: true, featured: true, detected: top, others: rest.map(label => ({ label, supported: supports(label) !== false })) };
  }
  if (!detected.length) return { grouped: false, detected: [], others: all.map(label => ({ label, supported: supports(label) !== false })) };
  return { grouped: true, detected, others: all.filter(c => !seen.has(c)).map(label => ({ label, supported: supports(label) !== false })) };
}
// D139 feature search: case-insensitive substring over the English label, the Chinese display name and any alias.
export function filterClasses(classes, query, aliases = {}) {
  const list = Array.isArray(classes) ? classes : [];
  const q = String(query ?? '').trim().toLowerCase().replace(/[_\s]+/g, ' ');
  if (!q) return list.slice();
  return list.filter(c => [c, classDisplay(c, aliases), ...Object.entries(aliases ?? {}).filter(([, v]) => v === c).map(([k]) => k)]
    .some(t => String(t).toLowerCase().replace(/[_\s]+/g, ' ').includes(q)));
}
const COLOR_ZH = Object.freeze({ red: '紅色', blue: '藍色', black: '黑色', white: '白色', green: '綠色', yellow: '黃色', gray: '灰色', grey: '灰色', orange: '橘色', purple: '紫色', brown: '棕色', pink: '粉紅色' });
const CLASS_ZH = Object.freeze({ person: '人物', laptop: '筆電', backpack: '背包', chair: '椅子', car: '車輛', bottle: '水瓶', cup: '杯子', cell_phone: '手機', 'cell phone': '手機' });
// Presentation only: the request still carries the vocabulary label from the run's supported_classes.
export function classDisplay(label, aliases = {}) {
  if (CLASS_ZH[label]) return CLASS_ZH[label];
  const alias = Object.entries(aliases ?? {}).find(([, v]) => v === label);
  return alias ? alias[0] : label;
}
export const colorDisplay = label => COLOR_ZH[String(label).toLowerCase()] ?? label;

// Time of a source-clock offset on the declared wall clock (Asia/Taipei), as HH:MM:SS. Null without a clock mapping.
export function wallClockText(clockMapping, sourceUs) {
  const origin = Date.parse(clockMapping?.wall_origin ?? '');
  if (!Number.isFinite(origin) || !Number.isFinite(sourceUs)) return null;
  const when = new Date(origin + ((sourceUs - (clockMapping.t0_us ?? 0)) / (clockMapping.rate || 1)) / 1000);
  return taipeiTime(when);
}
export function taipeiTime(date) {
  try {
    return new Intl.DateTimeFormat('zh-TW', { timeZone: 'Asia/Taipei', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(date).replace(/^24/, '00');
  } catch { return null; }
}
// D139: a track request always carries concrete times. Blank start = the recording's clock start; blank end = clock start
// plus source_duration (the recording's end). Never empty values: an empty window reached the backend as "now" and gave
// the 14:00:00～14:00:00 / 時間窗內無觀測紀錄 result.
export function recordingWindow(clockMapping) {
  // wall_origin is the wall time of t0 (not of source 0); the backend accepts source offsets [0, source_duration].
  const dur = clockMapping?.source_duration_us;
  const start = wallClockText(clockMapping, 0);
  const end = Number.isFinite(dur) ? wallClockText(clockMapping, dur) : null;
  return start && end ? { start, end } : null;
}
// The backend ClockMapping only supports rate 1 (clock_mapping.py); anything else is refused in plain words.
export const clockRateSupported = clockMapping => clockMapping?.rate === undefined || clockMapping?.rate === null || clockMapping.rate === 1;
export const RATE_UNSUPPORTED_TEXT = '這支錄影的時間倍率目前不支援，無法用時間範圍追蹤';
export const clockSeconds = text => { const m = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(String(text ?? '').trim()); return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3] ?? 0) : null; };
export const padClock = text => { const n = clockSeconds(text); return n === null ? String(text ?? '').trim() : [Math.floor(n / 3600), Math.floor(n / 60) % 60, n % 60].map(v => String(v).padStart(2, '0')).join(':'); };
export function trackWindow(startText, endText, clockMapping) {
  if (!clockRateSupported(clockMapping)) return { ok: false, start: '', end: '', code: 'RATE_UNSUPPORTED', text: RATE_UNSUPPORTED_TEXT };
  const rec = recordingWindow(clockMapping);
  const start = filled(startText) ? padClock(startText) : rec?.start ?? '';
  const end = filled(endText) ? padClock(endText) : rec?.end ?? '';
  if (!start || !end) return { ok: false, start, end, code: 'CLOCK_UNKNOWN', text: '尚無錄影時間資料，請手動輸入開始與結束時間' };
  const a = clockSeconds(start), b = clockSeconds(end);
  if (a !== null && b !== null && b <= a) return { ok: false, start, end, code: 'END_BEFORE_START', text: '結束時間要晚於開始時間' };
  return { ok: true, start, end, code: null, text: '' };
}
export const timeRangeText = (start, end) => `${start}～${end}`;
export const endPlaceholder = clockMapping => { const rec = recordingWindow(clockMapping); return rec ? `到錄影結尾（${rec.end}）` : '到錄影結尾'; };
export const startPlaceholder = clockMapping => recordingWindow(clockMapping)?.start ?? 'HH:MM:SS';

// ---- Search progress (示意：進度條只是等待回饋，不是實際進度) ------------------------------------------------------
export const SEARCH_STAGES = Object.freeze(['讀取鏡頭', '比對區域', '比對物件', '整理畫面']);
export const TRACK_STAGES = Object.freeze(['讀取鏡頭', '搜尋目標', '串接鏡頭', '整理畫面']);
export const SEGMENTS_PER_STAGE = 18;
// Four stages share one illustrative progress value (0..1). A miss freezes it; a resolved search fills it.
export function stagesModel(progress, { stages = SEARCH_STAGES, resolved = false, miss = false } = {}) {
  const p = Math.min(1, Math.max(0, Number.isFinite(progress) ? progress : 0));
  const per = 1 / stages.length;
  return stages.map((label, i) => {
    const local = Math.min(1, Math.max(0, (p - i * per) / per));
    const filledSegments = Math.round(local * SEGMENTS_PER_STAGE);
    const state = local >= 1 || (resolved && p >= 1) ? 'done' : local > 0 && !miss ? 'active' : local > 0 ? 'stalled' : 'pending';
    return { label, state, filled: filledSegments, total: SEGMENTS_PER_STAGE };
  });
}

// ---- Results wall -----------------------------------------------------------------------------------------------
export function wallCards(wallModel, limit = DEFAULT_SETTINGS.resultLimit) {
  const all = wallModel?.allCards ?? wallModel?.cards ?? [];
  const cards = all.slice(0, Math.max(1, limit));
  return { cards, shown: cards.length, total: all.length, truncated: all.length > cards.length };
}
// Chips under a card: only evidence actually carried by the response (地點覆蓋 / 偵測類別).
export function cardChips(card, aliases = {}) {
  const chips = [];
  for (const b of card?.basis ?? []) {
    if (b.kind === 'LOCATION') chips.push({ text: '地點覆蓋', tone: 'observed' });
    else if (b.kind === 'OBJECT') chips.push({ text: `偵測：${classDisplay(b.class_label ?? '物件', aliases)}${b.color_label ? ' · ' + colorDisplay(b.color_label) : ''}`, tone: 'observed' });
  }
  return chips;
}

// ---- Tracking: camera timeline ----------------------------------------------------------------------------------
// Segments come straight from track_response.single_view (ON_CAMERA / GAP / LOST). Widths are proportional to time.
export function cameraTimeline(singleView, { startUs = 0, asOfUs = 0, currentUs = 0 } = {}) {
  const span = Math.max(1, asOfUs - startUs);
  const list = (Array.isArray(singleView) ? singleView : []).filter(s => Array.isArray(s.range_us) && s.range_us[1] > s.range_us[0])
    .slice().sort((x, y) => x.range_us[0] - y.range_us[0]);
  const seg = (kind, cameraId, a, b, current) => ({ kind, cameraId, startUs: a, endUs: b, flex: Math.max(0.0001, (b - a) / span), current });
  const segments = [];
  let cursor = startUs;
  for (const s of list) {
    const a = Math.max(startUs, s.range_us[0]), b = Math.min(asOfUs, s.range_us[1]);
    if (b <= a) continue;
    // time with no segment (before the first sighting, or a hole) is PENDING, drawn where it happens — never moved to the end of the bar
    if (a > cursor) segments.push(seg('PENDING', null, cursor, a, cursor <= currentUs && currentUs < a));
    segments.push(seg(s.kind, s.camera_id ?? null, a, b, s.range_us[0] <= currentUs && currentUs < s.range_us[1]));
    cursor = Math.max(cursor, b);
  }
  if (list.length && cursor < asOfUs) segments.push(seg('PENDING', null, cursor, asOfUs, cursor <= currentUs && currentUs < asOfUs));
  const covered = segments.reduce((n, x) => n + (x.endUs - x.startUs), 0);
  return { segments, marker: Math.min(1, Math.max(0, (currentUs - startUs) / span)), uncovered: Math.max(0, span - covered) / span };
}
// Where the playhead starts after a track result loads: the start of the first ON_CAMERA (OBSERVED) segment inside the window.
// Returns { us, jumped }; no observed segment → the window start, jumped=false.
export function initialPlayheadUs(singleView, { startUs = 0, asOfUs = 0 } = {}) {
  const firsts = (Array.isArray(singleView) ? singleView : []).filter(s => s?.kind === 'ON_CAMERA' && Array.isArray(s.range_us) && s.range_us[1] > s.range_us[0] && s.range_us[1] > startUs && s.range_us[0] < asOfUs)
    .map(s => Math.max(startUs, s.range_us[0]));
  if (!firsts.length) return { us: startUs, jumped: false };
  return { us: Math.min(...firsts), jumped: true };
}
// Share of the tracked window with no camera seeing the target (GAP + LOST); null when there is no timeline.
export function blindShare(singleView) {
  const list = (Array.isArray(singleView) ? singleView : []).filter(s => Array.isArray(s.range_us));
  const total = list.reduce((n, s) => n + (s.range_us[1] - s.range_us[0]), 0);
  if (!total) return null;
  const blind = list.filter(s => s.kind !== 'ON_CAMERA').reduce((n, s) => n + (s.range_us[1] - s.range_us[0]), 0);
  return blind / total;
}

// ---- Tracking: floor plan ---------------------------------------------------------------------------------------
// Camera node positions are static display coordinates from the camera map (not measured paths). Without them the
// plan says UNKNOWN instead of drawing a made-up layout.
export function floorPlan(topdown, { settings = DEFAULT_SETTINGS, singleView = null, currentTUs = 0 } = {}) {
  const nodes = topdown?.nodes ?? [];
  if (!nodes.length) return { available: false, nodes: [], observed: [], blind: [], blindVisible: false, current: null };
  const at = new Map(nodes.map(n => [n.cameraId, n]));
  const observed = (topdown.observed_cameras ?? []).map(c => at.get(typeof c === 'string' ? c : c?.camera_id ?? c?.cameraId)).filter(Boolean).map(n => [n.x, n.y]);
  const curve = topdown.blind_curve;
  // 跟丟後保留推測路線：dashed route stops once the gap is older than the configured seconds.
  let blindVisible = Boolean(curve?.visible && curve.svgPoints?.length > 1 && settings.blindPlan !== false);
  if (blindVisible && topdown.last_observed_us != null && currentTUs - topdown.last_observed_us > settings.keepBlindSec * 1e6) blindVisible = false;
  const activeNode = nodes.find(n => n.isActive) ?? null;
  const current = activeNode ? [activeNode.x, activeNode.y] : (observed.at(-1) ?? null);
  return { available: true, nodes, observed, blind: blindVisible ? curve.svgPoints : [], blindVisible, dash: curve?.stroke_dasharray ?? '6 6', current };
}
// D139: where the blind interval ends. The newest GAP before the playhead; when the very next segment is ON_CAMERA and
// the playhead has reached it, the target has reappeared: returns that camera and the real observation time.
// Where the "blind ends" ring is drawn. A legal inferred curve keeps its own last point; otherwise the observed
// re-acquisition camera's node. Never another prediction's end point.
export function reacquireMarker(plan, reacq) {
  if (!reacq) return null;
  if (plan?.blindVisible && plan.blind?.length > 1) return plan.blind.at(-1);
  const n = (plan?.nodes ?? []).find(x => x.cameraId === reacq.cameraId);
  return n ? [n.x, n.y] : null;
}
export function blindReacquire(singleView, currentTUs, clockMapping) {
  const list = (Array.isArray(singleView) ? singleView : []).filter(x => Array.isArray(x.range_us)).sort((a, b) => a.range_us[0] - b.range_us[0]);
  let gap = -1; list.forEach((x, i) => { if (x.kind === 'GAP' && x.range_us[0] <= currentTUs) gap = i; });
  const next = gap >= 0 ? list[gap + 1] : null;
  if (!next || next.kind !== 'ON_CAMERA' || next.range_us[0] > currentTUs) return null;
  const atUs = next.range_us[0], atText = wallClockText(clockMapping, atUs) ?? `${(atUs / 1e6).toFixed(2)} s`;
  return { cameraId: next.camera_id, atUs, atText };
}
// D139 front-desk journal: a GAP no longer than maxGapUs that sits between two ON_CAMERA segments of the SAME camera
// is a flicker (the detector lost the target for a few frames). The GAP and the second segment are folded into the first,
// which then spans both. Longer gaps, gaps between different cameras and LOST are never merged. Presentation only: the
// response, the camera timeline and the admin event log keep the raw segments.
export const JOURNAL_MERGE_GAP_US = 1e6;
export function mergeFlicker(singleView, maxGapUs = JOURNAL_MERGE_GAP_US) {
  const list = (Array.isArray(singleView) ? singleView : []).filter(x => Array.isArray(x?.range_us)).map(x => ({ ...x, range_us: [...x.range_us] })).sort((a, b) => a.range_us[0] - b.range_us[0]);
  const out = []; let merged = 0;
  for (let i = 0; i < list.length; i++) {
    const cur = list[i], prev = out.at(-1), next = list[i + 1];
    const flicker = cur.kind === 'GAP' && prev?.kind === 'ON_CAMERA' && next?.kind === 'ON_CAMERA' && prev.camera_id === next.camera_id && cur.range_us[1] - cur.range_us[0] <= maxGapUs;
    if (flicker) { prev.range_us[1] = Math.max(prev.range_us[1], next.range_us[1]); merged++; i++; continue; }
    if (cur.kind === 'ON_CAMERA' && prev?.kind === 'ON_CAMERA' && prev.camera_id === cur.camera_id && cur.range_us[0] <= prev.range_us[1]) { prev.range_us[1] = Math.max(prev.range_us[1], cur.range_us[1]); continue; }
    out.push(cur);
  }
  return { segments: out, merged };
}
// Where the front desk lands when the user clicks the Amidst brand: the cover while it is enabled, else the entry setting.
export const homeScreen = settings => (settings?.coverAnimation !== false ? 'cover' : nextAfterCover(settings ?? {}));
export const isBlindNow = view => ['GAP', 'LOST'].includes(view?.singleView?.segmentKind);

// ---- Tracking: status / log -------------------------------------------------------------------------------------
export function trackStateChip(view) {
  const kind = view?.singleView?.segmentKind;
  if (kind === 'ON_CAMERA') return { text: 'OBSERVED', tone: 'observed' };
  if (kind === 'GAP') return { text: 'INFERRED', tone: 'inferred' };
  if (kind === 'LOST') return { text: 'LOST', tone: 'missing' };
  return { text: 'UNKNOWN', tone: 'unknown' };
}
// Journal rows derived from the response itself (selection of cameras over time).
export function trackJournal(singleView, clockMapping) {
  const rows = [];
  const list = Array.isArray(singleView) ? singleView : [];
  list.forEach((s, i) => {
    const t = wallClockText(clockMapping, s.range_us?.[0]) ?? `${((s.range_us?.[0] ?? 0) / 1e6).toFixed(2)} s`;
    if (s.kind === 'ON_CAMERA') rows.push({ t, text: i === 0 ? `鎖定於 ${s.camera_id}` : `出現於 ${s.camera_id}`, tone: 'observed', state: 'OBSERVED' });
    else if (s.kind === 'GAP') rows.push({ t, text: '離開畫面，盲區', tone: 'inferred', state: 'INFERRED' });
    else if (s.kind === 'LOST') rows.push({ t, text: '目標遺失', tone: 'missing', state: 'MISSING' });
  });
  return rows;
}

// ---- Event log shared with the admin page (localStorage) -------------------------------------------------------
export function pushEvent(log, entry, limit = EVENTLOG_LIMIT) {
  const next = [...(Array.isArray(log) ? log : []), entry].slice(-limit);
  return next;
}
export function normalizeLog(raw) {
  return (Array.isArray(raw) ? raw : []).filter(e => e && typeof e.at === 'number' && typeof e.text === 'string' && ['OBSERVED', 'INFERRED', 'MISSING', 'UNKNOWN'].includes(e.state)).slice(-EVENTLOG_LIMIT);
}

// ---- Case routing -----------------------------------------------------------------------------------------------
export function parseRoute(search = '', settings = DEFAULT_SETTINGS) {
  let p; try { p = new URLSearchParams(search); } catch { p = new URLSearchParams(); }
  const legacy = p.get('ui') === 'legacy';
  const screen = p.get('screen');
  // Event-menu links (?ev=…) belong to 查看.
  const wantsView = p.has('ev') || p.has('recording');
  const coreLinks = {search: 'case1', 'track-single': 'case2', 'track-multi': 'case2', blind: 'case2'};
  const initial = CASE_IDS.includes(screen) ? screen : Object.hasOwn(coreLinks, screen) ? coreLinks[screen] : wantsView ? 'case3' : null;
  return { legacy, initial, skipCover: initial !== null, settings };
}
export function nextAfterCover(settings) { return settings.defaultCase ?? 'choose'; }

// D146: continuous playback. Every camera plays on the one shared clock; the stage follows the target:
//  ON_CAMERA -> that segment's camera (observed). GAP / LOST -> keep playing the camera the target was last seen on (not observed).
//  PENDING (before the first sighting) -> the first camera that will see the target. `observed` is true only inside ON_CAMERA.
export function stagePlan(singleView, t) {
  const list = (Array.isArray(singleView) ? singleView : []).filter(x => Array.isArray(x.range_us)).sort((a, b) => a.range_us[0] - b.range_us[0]);
  if (!list.length) return { kind: 'UNKNOWN', cam: null, observed: false, last: null };
  let seg = list.find(x => x.range_us[0] <= t && t < x.range_us[1]);
  if (!seg && t >= list.at(-1).range_us[1]) seg = list.at(-1);
  const first = list.find(x => x.kind === 'ON_CAMERA');
  if (!seg) return { kind: 'PENDING', cam: first?.camera_id ?? null, observed: false, last: null };
  if (seg.kind === 'ON_CAMERA') return { kind: 'ON_CAMERA', cam: seg.camera_id, observed: true, last: seg.camera_id };
  let last = null; for (const x of list) if (x.kind === 'ON_CAMERA' && x.range_us[0] <= t) last = x.camera_id;
  const kind = ['GAP', 'LOST'].includes(seg.kind) ? seg.kind : 'UNKNOWN';
  return { kind, cam: last ?? first?.camera_id ?? null, observed: false, last };
}

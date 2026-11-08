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
export const SPEEDS = Object.freeze([1, 1.5, 2]);
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
// A track request with only a start needs an end; the run's own end on the declared clock is the widest honest bound.
export function trackWindow(startText, clockMapping) {
  if (!filled(startText)) return { start: '', end: '' };
  const end = wallClockText(clockMapping, clockMapping?.source_duration_us ?? NaN);
  return { start: String(startText).trim(), end: end ?? '' };
}

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
  const list = (Array.isArray(singleView) ? singleView : []).filter(s => Array.isArray(s.range_us) && s.range_us[1] > s.range_us[0]);
  const segments = list.map(s => {
    const a = Math.max(startUs, s.range_us[0]), b = Math.min(asOfUs, s.range_us[1]);
    return { kind: s.kind, cameraId: s.camera_id ?? null, startUs: a, endUs: b, flex: Math.max(0.0001, (b - a) / span), current: s.range_us[0] <= currentUs && currentUs < s.range_us[1] };
  });
  const covered = segments.reduce((n, s) => n + (s.endUs - s.startUs), 0);
  return { segments, marker: Math.min(1, Math.max(0, (currentUs - startUs) / span)), uncovered: Math.max(0, span - covered) / span };
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

// Legacy boundary: this module reaches the old workbench ONLY through ctx.legacy (built in one block in app.mjs).
// Deleting the old screens = delete that block and the engine DOM in index.html.
// Front desk for the redesigned workbench (docs/specs/UI_REDESIGN_V1.md): cover → chooser → case1 查找 / case2 追蹤 /
// case3 查看. Presentation only. Every figure on screen comes from the store (API responses and view models built by
// the existing models); the engine DOM in index.html keeps running underneath and is hidden. No inference inputs.
import {
  CASES, NOT_MEASURED, SEARCH_STAGES, TRACK_STAGES,
  loadSettings, readJson, writeJson, SNAPSHOT_KEY, EVENTLOG_KEY, pushEvent, normalizeLog,
  validateSearchForm, validateTrackForm, trackWindow, wallClockText, classDisplay, colorDisplay,
  stagesModel, wallCards, cardChips, cameraTimeline, blindShare, floorPlan, trackStateChip, trackJournal,
  parseRoute, nextAfterCover,
} from './ui-model.mjs';
import {countsFromSearch, HISTORY_LIMIT} from './admin-overview-model.mjs';
import {createPhaseStore, progressPercent} from './search-phase-model.mjs';
import {sourcePresentation} from './q-tokens.mjs';
import {resolveCardImageSrc, resolveFrameImageSrc} from './core-media.mjs';
import {canPlay} from './q-playback.mjs';
import {
  AUTO_SEED_LABEL, reasonChips, buildCoreTrackingViewModel, SUPPORTED_SPEEDS, ERROR_TEXT,
} from './core-search-track-model.mjs';
import {EVENTS, parseConfig, available, embedSrc, pageUrl, modeOf, B05B_RECORDING_ID} from './event-menu.mjs';

// Same range the player uses (app.mjs playbackBounds); kept here so this module does not import the composition root.
const playbackBounds = s => s.coreTrackResponse ? [s.coreTrackResponse.resolved_time?.source_range_us?.[0] ?? 0, s.coreTrackResponse.as_of_us] : [0, s.activeRun?.clock_mapping?.source_duration_us ?? 0];

const NS = 'http://www.w3.org/2000/svg';
const MEDIA = /^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/;

export function mountUi(ctx) {
  const {store, root = document, url = root.baseURI ?? 'http://localhost/', storage = null, synthetic = false, mediaResolver = null} = ctx;
  const host = root.querySelector('#ui-v1');
  if (!host) return {destroy() {}};
  const doc = host.ownerDocument;
  const el = (tag, text, cls, attrs) => { const n = doc.createElement(tag); if (text !== undefined && text !== null) n.textContent = text; if (cls) n.className = cls; if (attrs) for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  const svg = (tag, attrs = {}) => { const n = doc.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v)); return n; };
  const cfg = parseConfig(new URL(url).search);
  let settings = loadSettings(storage);
  const route = parseRoute(new URL(url).search, settings);
  const phase = createPhaseStore();
  const disposers = [];
  let screen = 'cover', queryOpen = false, destroyed = false, lightbox = null;
  let search = {startedAt: 0, lastForm: null, logged: null}, track = {startedAt: 0, lastForm: null, logged: null, segKey: null};
  let snapshot = readJson(storage, SNAPSHOT_KEY, {}) ?? {};
  let eventLog = normalizeLog(readJson(storage, EVENTLOG_KEY, []));

  // ---- persistence shared with the admin page ---------------------------------------------------------------------
  const saveSnapshot = patch => { snapshot = {...snapshot, ...patch, at: Date.now()}; writeJson(storage, SNAPSHOT_KEY, snapshot); };
  const logEvent = (text, state) => { eventLog = pushEvent(eventLog, {at: Date.now(), text, state}); writeJson(storage, EVENTLOG_KEY, eventLog); };
  const pushHistory = (key, ms) => { const h = {lock: [], find: [], ...(snapshot.history ?? {})}; h[key] = [...h[key], Math.round(ms)].slice(-HISTORY_LIMIT); saveSnapshot({history: h}); };
  const runIds = () => { const r = store.getState().activeRun; return r ? {sceneId: r.scene_id, runId: r.run_id} : {}; };

  // ---- skeleton ---------------------------------------------------------------------------------------------------
  host.replaceChildren();
  host.dataset.screen = 'cover';
  const cover = el('section', undefined, 'ui-layer ui-cover'), choose = el('section', undefined, 'ui-layer ui-choose');
  const top = el('header', undefined, 'ui-top'), screens = el('main', undefined, 'ui-screens');
  const sCase1 = el('section', undefined, 'ui-screen'), sCase2 = el('section', undefined, 'ui-screen'), sCase3 = el('section', undefined, 'ui-screen');
  sCase1.id = 'ui-case1'; sCase2.id = 'ui-case2'; sCase3.id = 'ui-case3'; cover.id = 'ui-cover'; choose.id = 'ui-choose';
  const qWin1 = el('aside', undefined, 'ui-float'), qWin2 = el('aside', undefined, 'ui-float');
  qWin1.id = 'ui-q-search'; qWin2.id = 'ui-q-track';
  screens.append(sCase1, sCase2, sCase3);
  host.append(cover, choose, top, screens, qWin1, qWin2);

  // ---- cover + chooser --------------------------------------------------------------------------------------------
  const backstage = el('a', '後台', 'ui-pill-link ui-admin-link', {href: 'admin.html'});
  const coverBar = el('div', undefined, 'ui-cover-bar'); coverBar.append(el('span'), backstage);
  const coverBody = el('div', undefined, 'ui-cover-body');
  const enter = el('button', '進入系統 →', 'ui-btn ui-btn-light ui-rise ui-d4', {type: 'button'}); enter.id = 'ui-enter';
  coverBody.append(el('span', '多鏡頭查找與追蹤', 'ui-kicker ui-rise ui-d1'), el('h1', 'Amidst', 'ui-hero ui-rise ui-d2'),
    el('p', 'Agentic 驅動之智慧監控數位孿生系統', 'ui-tagline ui-rise ui-d3'),
    el('p', '輸入時間、地點或特徵，系統幫你找出畫面；鎖定之後，鏡頭會自動切換。', 'ui-lede ui-rise ui-d3'), enter);
  cover.append(el('span', undefined, 'ui-glow'), coverBar, coverBody);
  const chooseBody = el('div', undefined, 'ui-choose-body'), cards = el('div', undefined, 'ui-choose-cards');
  for (const c of CASES) {
    const a = el('button', undefined, 'ui-choice', {type: 'button', 'data-case': c.id});
    a.append(el('span', c.no, 'ui-mono ui-muted'), el('span', c.title, 'ui-choice-title'), el('span', c.blurb, 'ui-choice-blurb'), el('span', '開始 →', 'ui-accent ui-choice-go'));
    a.addEventListener('click', () => go(c.id));
    cards.append(a);
  }
  const back = el('button', '← 回封面', 'ui-linkbtn', {type: 'button'}); back.id = 'ui-back-cover'; back.addEventListener('click', () => go('cover'));
  chooseBody.append(el('h2', '要做什麼？', 'ui-h2'), cards, back);
  choose.append(chooseBody);
  enter.addEventListener('click', () => { const next = nextAfterCover(settings); go(next); });

  // ---- header -----------------------------------------------------------------------------------------------------
  const burger = el('button', undefined, 'ui-burger', {type: 'button', 'aria-label': '開關查詢窗'});
  burger.append(el('span'), el('span'), el('span'));
  const brand = el('button', 'Amidst', 'ui-brand', {type: 'button'}); brand.addEventListener('click', () => go('cover'));
  const ctxChip = el('span', undefined, 'ui-chip-ctx'); ctxChip.id = 'ui-context';
  const progChip = el('span', undefined, 'ui-chip-prog'); progChip.id = 'ui-prog-chip'; progChip.hidden = true;
  const topLeft = el('div', undefined, 'ui-top-left'); topLeft.append(burger, brand, ctxChip);
  const layoutSeg = el('span', undefined, 'ui-seg'); layoutSeg.id = 'ui-layout';
  const segSingle = el('button', '單畫面', undefined, {type: 'button', 'data-layout': 'single'}), segMulti = el('button', '多畫面', undefined, {type: 'button', 'data-layout': 'multi'});
  layoutSeg.append(segSingle, segMulti);
  const badge = el('span', undefined, 'ui-badge'); badge.id = 'ui-source-badge';
  const sourceSelect = el('select', undefined, 'ui-input ui-small', {'aria-label': '資料來源'}); sourceSelect.id = 'ui-run-select';
  sourceSelect.addEventListener('change', () => selectSource(sourceSelect.value));
  let sourceKey = '';
  const integration = () => store.getState().bootstrap?.demo_integration === true;
  function selectSource(runId) {
    const run = store.getState().bootstrap?.runs?.find(r => r.run_id === runId); if (!run) return;
    const u = new URL(url); u.search = ''; u.searchParams.set('run', run.run_id); u.searchParams.set('screen', screen);
    globalThis.location?.assign?.(u.toString());
  }
  const topRight = el('div', undefined, 'ui-top-right'); topRight.append(sourceSelect, progChip, layoutSeg, badge);
  const topAdmin = el('a', '後台', 'ui-pill-link', {href: 'admin.html'});
  topRight.append(topAdmin);
  top.append(topLeft, topRight);
  burger.addEventListener('click', () => setQuery(!queryOpen));
  ctxChip.addEventListener('click', () => { if (screen === 'case2') setQuery(true); });
  for (const b of [segSingle, segMulti]) b.addEventListener('click', () => { store.dispatch({type: 'SET_PLAYBACK_MODE', value: b.dataset.layout}); });

  // ---- query windows ----------------------------------------------------------------------------------------------
  const chipBtn = (label, on, cls = '') => { const b = el('button', label, `ui-chip-btn ${cls}`.trim(), {type: 'button'}); b.setAttribute('aria-pressed', String(on)); return b; };
  const field = (label, ...kids) => { const l = el('label', undefined, 'ui-field'); l.append(el('span', label, 'ui-label'), ...kids); return l; };
  const timeInput = (id, value, label, ph) => { const i = el('input', undefined, 'ui-input ui-mono', {type: 'text', 'aria-label': label}); i.id = id; i.value = value ?? ''; if (ph) i.placeholder = ph; return i; };

  const searchForm = {regions: new Set(), classLabel: '', colorLabel: ''};
  const trackForm = {regions: new Set(), classLabel: '', colorLabel: ''};
  const q1 = buildQueryWindow({win: qWin1, title: '查找', form: searchForm, id: 'search', kind: 'search'});
  const q2 = buildQueryWindow({win: qWin2, title: '追蹤新目標', form: trackForm, id: 'track', kind: 'track'});

  function buildQueryWindow({win, title, form, id, kind}) {
    const card = el('div', undefined, 'ui-card ui-qcard');
    const head = el('span', undefined, 'ui-qhead'); const close = el('button', '×', 'ui-x', {type: 'button', 'aria-label': '收起查詢窗'});
    close.addEventListener('click', () => setQuery(false));
    head.append(el('span', title, 'ui-qtitle'), close);
    const regionsBox = el('div', undefined, 'ui-chips'); regionsBox.dataset.role = 'regions';
    const classBox = el('div', undefined, 'ui-chips'); classBox.dataset.role = 'classes';
    const colorBox = el('div', undefined, 'ui-chips'); colorBox.dataset.role = 'colors';
    const start = timeInput(`ui-${id}-start`, '', kind === 'search' ? '開始時間' : '開始時間', kind === 'track' ? '現在' : 'HH:MM:SS');
    const end = timeInput(`ui-${id}-end`, '', '結束時間', 'HH:MM:SS');
    const timeRow = el('span', undefined, 'ui-timerow');
    if (kind === 'search') timeRow.append(start, el('span', '→', 'ui-faint'), end); else timeRow.append(start);
    const submit = el('button', kind === 'search' ? '開始查找' : '開始追蹤', 'ui-btn ui-btn-light ui-btn-block', {type: 'button'}); submit.id = `ui-${id}-submit`;
    const feedback = el('p', '', 'ui-feedback'); feedback.id = `ui-${id}-feedback`; feedback.setAttribute('role', 'status');
    const timeField = field(kind === 'search' ? '時間範圍（必填）' : '從什麼時候開始（空白＝現在）', timeRow);
    const regionField = el('div', undefined, 'ui-field'); regionField.append(el('span', kind === 'search' ? '地點' : '地點（選填）', 'ui-label'), regionsBox);
    const featField = el('div', undefined, 'ui-field'); featField.append(el('span', kind === 'track' ? '特徵（必填）' : '特徵', 'ui-label'), classBox, colorBox);
    const note = kind === 'track' ? el('p', '第一次鎖定需要掃過全部鏡頭，會顯示進度；鎖定之後換鏡頭會立即切換。', 'ui-note') : null;
    card.append(head, ...(kind === 'search' ? [timeField, regionField, featField] : [featField, regionField, timeField]), submit, feedback);
    if (note) card.append(note);
    const progress = el('div', undefined, 'ui-card ui-progress'); progress.id = `ui-${id}-progress`; progress.hidden = true;
    win.append(card, progress);
    const api = {start, end, regionsBox, classBox, colorBox, feedback, submit, progress, form, kind, card, regionField};
    submit.addEventListener('click', () => submitQuery(api));
    for (const input of [start, end]) input.addEventListener('keydown', e => { if (e.key === 'Enter') submitQuery(api); });
    return api;
  }
  function renderCatalog() {
    const cat = ctx.coreCatalog?.() ?? {regions: [], classes: [], colors: [], aliases: {}};
    for (const w of [q1, q2]) {
      const {regionsBox, classBox, colorBox, form} = w;
      regionsBox.replaceChildren();
      if (!cat.regions.length) regionsBox.append(el('span', cat.run ? 'UNKNOWN · 地點目錄未就緒' : NOT_MEASURED, 'ui-faint ui-small'));
      for (const r of cat.regions) {
        const b = chipBtn(r.label, form.regions.has(r.value)); b.dataset.value = r.value;
        b.addEventListener('click', () => { form.regions.has(r.value) ? form.regions.delete(r.value) : form.regions.add(r.value); b.setAttribute('aria-pressed', String(form.regions.has(r.value))); b.classList.toggle('on', form.regions.has(r.value)); });
        b.classList.toggle('on', form.regions.has(r.value)); regionsBox.append(b);
      }
      classBox.replaceChildren();
      const classes = w.kind === 'search' ? ['', ...cat.classes] : cat.classes;
      for (const c of classes) {
        const b = chipBtn(c ? classDisplay(c, cat.aliases) : '不限', form.classLabel === c); b.dataset.value = c;
        b.addEventListener('click', () => { form.classLabel = form.classLabel === c && c !== '' ? '' : c; if (form.classLabel !== 'person') form.colorLabel = ''; renderCatalog(); });
        b.classList.toggle('on', form.classLabel === c); classBox.append(b);
      }
      colorBox.replaceChildren(); colorBox.hidden = form.classLabel !== 'person' || !cat.colors.length;
      for (const c of cat.colors) {
        const b = chipBtn(colorDisplay(c), form.colorLabel === c); b.dataset.value = c;
        b.addEventListener('click', () => { form.colorLabel = form.colorLabel === c ? '' : c; renderCatalog(); });
        b.classList.toggle('on', form.colorLabel === c); colorBox.append(b);
      }
    }
    const run = cat.run;
    if (run && !q1.start.value && !q1.end.value) { q1.start.value = wallClockText(run.clock_mapping, 0) ?? ''; q1.end.value = wallClockText(run.clock_mapping, run.clock_mapping?.source_duration_us) ?? ''; }
  }

  async function submitQuery(w) {
    const form = {start: w.start.value, end: w.kind === 'search' ? w.end.value : '', regionIds: [...w.form.regions], classLabel: w.form.classLabel, colorLabel: w.form.colorLabel};
    const run = store.getState().activeRun;
    const check = w.kind === 'search' ? validateSearchForm(form) : validateTrackForm(form);
    if (!check.ok) { w.feedback.textContent = check.text; w.feedback.dataset.state = 'error'; return; }
    if (w.kind === 'track') { const win = trackWindow(form.start, run?.clock_mapping); form.start = win.start; form.end = win.end; }
    w.feedback.textContent = ''; w.feedback.dataset.state = '';
    const now = performance.now();
    phase.dispatch({type: 'SEARCH_START', mode: w.kind === 'search' ? 'find' : 'track'});
    if (w.kind === 'search') { search = {startedAt: now, lastForm: {...form, classLabel: form.classLabel, regionIds: form.regionIds}, logged: null}; logEvent('送出查找', 'UNKNOWN'); }
    else { track = {startedAt: now, lastForm: {...form}, logged: null, segKey: null}; logEvent('送出追蹤', 'UNKNOWN'); }
    setQuery(settings.searchPanelOpen || w.kind === 'track' ? queryOpen : false);
    render();
    const result = await ctx.submitCore(w.kind, form);
    if (destroyed) return;
    if (!result?.ok) {
      const text = ERROR_TEXT[result?.code] ?? result?.text ?? 'UNKNOWN';
      w.feedback.textContent = text; w.feedback.dataset.state = 'error';
      phase.dispatch({type: 'SEARCH_END'}); setQuery(true); render();
    }
  }

  // ---- progress (示意) --------------------------------------------------------------------------------------------
  // Core responses are not part of the legacy outcome model, so the phase store is driven here: armed when the request
  // starts loading, resolved when the matching response lands, stalled on an error.
  function syncPhase() {
    const p = phase.getState(), s = store.getState();
    if (p.phase !== 'searching') return;
    if (!p.armed) { if (s.loading) phase.dispatch({type: 'SEARCH_ARMED'}); return; }
    if (s.error) { phase.dispatch({type: 'SEARCH_MISS', code: s.error.code ?? 'UNKNOWN', message: ERROR_TEXT[s.error.code] ?? s.error.message ?? 'UNKNOWN'}); return; }
    if (s.loading) return;
    if ((p.mode === 'find' && s.coreSearchResponse) || (p.mode === 'track' && s.coreTrackResponse)) phase.dispatch({type: 'SEARCH_FOUND', mode: p.mode});
  }
  disposers.push(store.subscribe(syncPhase), phase.subscribe(() => { syncPhase(); renderProgress(); }));
  let last = Date.now();
  const timer = setInterval(() => { const now = Date.now(); phase.dispatch({type: 'TICK', dtMs: now - last}); last = now; }, 100);
  disposers.push(() => clearInterval(timer));

  function renderProgress() {
    const p = phase.getState(), searching = p.phase === 'searching';
    const mode = p.mode;
    for (const w of [q1, q2]) {
      const mine = (w.kind === 'search') === (mode === 'find');
      w.progress.hidden = !(searching && mine);
      if (w.progress.hidden) continue;
      w.progress.replaceChildren();
      const cams = store.getState().activeRun?.camera_ids?.length;
      const head = p.miss ? '尚未找到' : mode === 'track' ? (cams ? `在 ${cams} 台鏡頭中尋找目標…` : '尋找目標…') : '進行中';
      w.progress.append(el('span', head, 'ui-eyebrow'));
      for (const st of stagesModel(p.progress, {stages: mode === 'track' ? TRACK_STAGES : SEARCH_STAGES, resolved: p.resolved, miss: Boolean(p.miss)})) {
        const row = el('div', undefined, `ui-stage is-${st.state}`);
        row.append(el('span', `${st.state === 'done' ? '✓' : st.state === 'pending' ? '○' : '●'} ${st.label}`, 'ui-stage-label'), segBar(st.filled, st.total));
        w.progress.append(row);
      }
      if (p.miss) w.progress.append(el('p', `${p.miss.code} · ${p.miss.message}`, 'ui-feedback', {'data-state': 'error'}));
      else w.progress.append(el('p', '進度為示意，不代表實際完成比例', 'ui-faint ui-small'));
    }
    const mineActive = searching && !p.miss;
    progChip.hidden = !mineActive;
    if (mineActive) {
      const stages = stagesModel(p.progress, {stages: mode === 'track' ? TRACK_STAGES : SEARCH_STAGES}); const active = stages.find(s => s.state === 'active') ?? stages.at(-1);
      progChip.replaceChildren(el('span', `● ${active.label}`), el('span', undefined, 'ui-minibar'));
      progChip.lastChild.append(el('span')); progChip.lastChild.firstChild.style.width = progressPercent(p.progress) + '%';
    }
  }
  function segBar(filled, total) {
    const bar = el('span', undefined, 'ui-segbar'); bar.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < total; i++) bar.append(el('i', undefined, i < filled ? 'on' : ''));
    return bar;
  }

  // ---- navigation -------------------------------------------------------------------------------------------------
  function setQuery(open) {
    queryOpen = open && (screen === 'case1' || screen === 'case2');
    qWin1.dataset.open = String(queryOpen && screen === 'case1'); qWin2.dataset.open = String(queryOpen && screen === 'case2');
    burger.setAttribute('aria-expanded', String(queryOpen));
  }
  let entered = {case2: false};
  function go(next) {
    if (destroyed) return;
    if (next === 'choose' && settings.defaultCase) next = settings.defaultCase;
    if (next === 'case2' && !entered.case2) { entered.case2 = true; store.dispatch({type: 'SET_PLAYBACK_MODE', value: settings.trackLayout}); store.dispatch({type: 'SET_SPEED', speed: settings.trackSpeed}); }
    if (next === 'case3' && !integration() && route.initial !== 'case3' && cfg.ev === null) {
      const wanted = EVENTS.find(e => e.id === settings.defaultEvent);
      if (wanted && available(wanted, cfg) && wanted.kind === 'page') { globalThis.location?.assign?.(case3Url(wanted)); return; }
    }
    screen = next; host.dataset.screen = next; host.dataset.chooser = String(next === 'choose');
    for (const [id, n] of [['case1', sCase1], ['case2', sCase2], ['case3', sCase3]]) n.hidden = id !== next;
    cover.dataset.on = String(next === 'cover'); choose.dataset.on = String(next === 'choose');
    const wasCase = next === 'case1' || next === 'case2' || next === 'case3';
    top.hidden = !wasCase;
    if (next === 'case1') setQuery(!store.getState().coreSearchResponse || settings.searchPanelOpen);
    else if (next === 'case2') setQuery(!store.getState().coreTrackResponse);
    else setQuery(false);
    if (next === 'case3') mountCase3(); else ctx.refreshWall?.();
    render();
    host.dispatchEvent(new CustomEvent('ui:screen', {detail: next}));
  }
  const case3Url = entry => { const u = new URL(pageUrl(entry, cfg, url, {mode: entry.recording ? 'track' : cfg.mode ?? 'view'})); u.searchParams.set('screen', 'case3'); return u.toString(); };

  // ---- case 1: results wall ---------------------------------------------------------------------------------------
  function renderCase1() {
    const s = store.getState(), resp = s.coreSearchResponse, model = s.coreSearchWall;
    sCase1.replaceChildren();
    const p = phase.getState();
    if (p.phase === 'searching' && p.mode === 'find' && !resp) {
      const wait = el('div', undefined, 'ui-empty'); wait.append(el('p', p.miss ? '尚未找到' : '正在查找…', 'ui-h3'), el('p', p.miss ? `${p.miss.code} · ${p.miss.message}` : '結果出來後會顯示在這裡', 'ui-muted'));
      sCase1.append(wait); return;
    }
    if (!resp || !model) {
      const empty = el('div', undefined, 'ui-empty'); empty.append(el('p', '查找', 'ui-h3'), el('p', '開啟查詢窗，填入時間，再加上地點或特徵。', 'ui-muted'));
      const open = el('button', '開啟查詢窗', 'ui-btn ui-btn-light', {type: 'button'}); open.addEventListener('click', () => setQuery(true)); empty.append(open);
      sCase1.append(empty); return;
    }
    const aliases = s.activeRun?.supported_classes?.aliases ?? {};
    const {cards, total, truncated} = wallCards(model, settings.resultLimit);
    const wall = el('div', undefined, 'ui-wall'); wall.id = 'ui-wall';
    const meta = el('div', undefined, 'ui-wall-meta');
    meta.append(el('span', model.statusText, 'ui-muted'), el('span', `${total} 個畫面`, 'ui-mono ui-muted'), el('span', model.identityBadge, 'ui-chip ui-chip-neutral'));
    for (const c of reasonChips(model.reasons)) meta.append(el('span', c.text, 'ui-chip ui-chip-neutral ui-mono'));
    sCase1.append(meta);
    if (!cards.length) { const e = el('div', undefined, 'ui-empty'); e.append(el('p', '這段時間沒有找到', 'ui-h3'), el('p', model.statusText, 'ui-muted')); sCase1.append(e); return; }
    cards.forEach((card, i) => {
      const art = el('article', undefined, 'ui-shot'); art.dataset.cameraId = card.cameraId; art.dataset.rank = String(card.rank);
      if (settings.staggerResults) art.style.animationDelay = Math.min(i, 12) * 45 + 'ms'; else art.classList.add('no-anim');
      const media = el('div', undefined, 'ui-media'); const img = el('img', undefined, 'ui-img'); img.alt = `${card.cameraId} 代表畫面`;
      const ph = el('span', synthetic ? 'SYNTHETIC · 影像示意' : 'MISSING · 來源 RGB 未取得', 'ui-media-note');
      const src = resolveCardImageSrc({card, mediaResolver, synthetic, onResolved: u => { if (MEDIA.test(u ?? '')) { img.src = u; img.hidden = false; ph.textContent = '來源綁定 RGB'; } }});
      if (src) img.src = src; else img.hidden = true;
      media.append(img, ph);
      const foot = el('div', undefined, 'ui-shot-foot'), id = el('span', undefined, 'ui-shot-id');
      id.append(el('span', card.cameraId, 'ui-mono'), el('span', card.wallRangeText, 'ui-mono ui-muted'));
      const chips = el('span', undefined, 'ui-shot-chips');
      for (const c of cardChips(card, aliases)) chips.append(el('span', c.text, `ui-chip ui-chip-${c.tone}`));
      if (!card.targetObserved) chips.append(el('span', '場景設定', 'ui-chip ui-chip-neutral'));
      foot.append(id, chips); art.append(media, foot);
      art.addEventListener('click', () => { store.dispatch({type: 'SET_CORE_SELECTION', selection: {rank: card.rank, cameraId: card.cameraId}}); openLightbox(cards, i, img.src); });
      wall.append(art);
    });
    sCase1.append(wall);
    if (truncated) sCase1.append(el('p', `只顯示前 ${cards.length} 個，共 ${total} 個（可到後台設定調整上限）`, 'ui-faint ui-small ui-wall-note'));
    if (model.notEvaluatedCameras.length) sCase1.append(el('p', `未評估：${model.notEvaluatedCameras.map(c => `${c.cameraId}（${c.reasonText}）`).join('、')}`, 'ui-faint ui-small ui-wall-note'));
  }
  function openLightbox(cards, index, currentSrc) {
    closeLightbox();
    const box = el('div', undefined, 'ui-lightbox', {role: 'dialog', 'aria-label': '大圖'}); lightbox = {box, index, cards};
    const stage = el('div', undefined, 'ui-lb-stage'), img = el('img', undefined, 'ui-lb-img'), cap = el('p', undefined, 'ui-mono ui-lb-cap');
    const prev = el('button', '◀', 'ui-btn ui-btn-ghost', {type: 'button', 'aria-label': '上一張'}), next = el('button', '▶', 'ui-btn ui-btn-ghost', {type: 'button', 'aria-label': '下一張'}), close = el('button', '回到結果牆', 'ui-btn ui-btn-light', {type: 'button'});
    const show = i => {
      lightbox.index = (i + cards.length) % cards.length; const c = cards[lightbox.index];
      cap.textContent = `${c.cameraId} · ${c.wallRangeText} · ${lightbox.index + 1} / ${cards.length}`;
      img.hidden = false; img.src = i === index && currentSrc ? currentSrc : (resolveCardImageSrc({card: c, mediaResolver, synthetic, onResolved: u => { if (MEDIA.test(u ?? '')) img.src = u; }}) ?? ''); if (!img.src) img.hidden = true;
    };
    prev.addEventListener('click', () => show(lightbox.index - 1)); next.addEventListener('click', () => show(lightbox.index + 1)); close.addEventListener('click', closeLightbox);
    box.addEventListener('click', e => { if (e.target === box) closeLightbox(); });
    stage.append(img, cap); const bar = el('div', undefined, 'ui-lb-bar'); bar.append(prev, close, next); box.append(stage, bar); host.append(box); show(index); close.focus();
  }
  function closeLightbox() { lightbox?.box.remove(); lightbox = null; }
  const onKey = e => { if (e.key === 'Escape') { if (lightbox) closeLightbox(); else if (queryOpen) setQuery(false); } else if (lightbox && e.key === 'ArrowRight') lightbox.box.querySelector('[aria-label="下一張"]')?.click(); else if (lightbox && e.key === 'ArrowLeft') lightbox.box.querySelector('[aria-label="上一張"]')?.click(); };
  doc.addEventListener('keydown', onKey); disposers.push(() => doc.removeEventListener('keydown', onKey));

  // ---- case 2: tracking -------------------------------------------------------------------------------------------
  const trackParts = {};
  function trackView() {
    const s = store.getState();
    return s.coreTrackResponse ? (s.coreTrackingView ?? buildCoreTrackingViewModel(s.coreTrackResponse, {tUs: s.tUs, playbackMode: s.playbackMode, speed: s.speed, cameraGraph: s.cameraGraph, displayPositions: s.displayPositions})) : null;
  }
  function renderCase2() {
    const s = store.getState(), resp = s.coreTrackResponse, view = trackView(), p = phase.getState();
    const searching = p.phase === 'searching' && p.mode === 'track' && !resp;
    // Structure is rebuilt when the response, playback layout or loading state changes; the clock-driven parts update in place.
    const key = `${resp?.output_sha256 ?? 'none'}|${s.playbackMode}|${searching}|${p.miss ? 'miss' : ''}|${s.error?.code ?? ''}`;
    if (trackParts.key !== key) { trackParts.key = key; buildCase2(s, resp, view, searching, p); }
    if (resp && view) updateCase2(s, resp, view);
  }
  function buildCase2(s, resp, view, searching, p) {
    sCase2.replaceChildren(); for (const k of Object.keys(trackParts)) if (k !== 'key') delete trackParts[k];
    if (!resp || !view) {
      const wait = el('div', undefined, 'ui-empty');
      if (searching) { const cams = s.activeRun?.camera_ids?.length; wait.append(el('p', p.miss ? '尚未找到' : cams ? `在 ${cams} 台鏡頭中尋找目標…` : '尋找目標…', 'ui-h3'), el('p', p.miss ? `${p.miss.code} · ${p.miss.message}` : '第一次鎖定需要一點時間；鎖定後換鏡頭會立即切換。', 'ui-muted')); }
      else { wait.append(el('p', '追蹤', 'ui-h3'), el('p', '開啟查詢窗，選好特徵就能開始追蹤；時間留空代表現在。', 'ui-muted')); const open = el('button', '開啟查詢窗', 'ui-btn ui-btn-light', {type: 'button'}); open.addEventListener('click', () => setQuery(true)); wait.append(open); }
      sCase2.append(wait); return;
    }
    const layout = el('div', undefined, 'ui-track'), main = el('section', undefined, 'ui-track-main'), aside = el('aside', undefined, 'ui-track-aside');
    const aliases = s.activeRun?.supported_classes?.aliases ?? {};
    const klass = track.lastForm?.classLabel ?? resp.normalized_request?.feature?.class_label ?? '';
    const head = el('div', undefined, 'ui-track-head'), title = el('h2', undefined, 'ui-h2 ui-track-title'); trackParts.title = title;
    head.append(title, el('span', view.identityBadge, 'ui-mono ui-muted'));
    const tags = el('div', undefined, 'ui-tags'); tags.append(el('span', AUTO_SEED_LABEL, 'ui-chip ui-chip-neutral', {'data-code': 'AUTO_SEED'}));
    for (const c of reasonChips(view.reasons)) tags.append(el('span', c.text, 'ui-chip ui-chip-neutral ui-mono', {'data-code': c.code}));
    trackParts.stateChip = el('span', undefined, 'ui-chip'); tags.append(trackParts.stateChip);
    trackParts.klass = classDisplay(klass, aliases) || '目標';
    main.append(head, tags);
    if (s.playbackMode === 'single') {
      const stage = el('div', undefined, 'ui-stagebox'), img = el('img', undefined, 'ui-img ui-stage-img'); img.alt = '追蹤畫面';
      const note = el('div', undefined, 'ui-stage-empty'); const stamp = el('span', undefined, 'ui-stamp ui-mono'), sw = el('span', undefined, 'ui-stamp ui-stamp-right'), tag = el('span', undefined, 'ui-tag-obs ui-mono');
      stage.append(img, note, stamp, sw, tag); Object.assign(trackParts, {img, note, stamp, sw, tag, stage}); main.append(stage);
    } else {
      const grid = el('div', undefined, 'ui-multi'); trackParts.multi = new Map();
      for (const cam of view.multiView.cameras) {
        const tile = el('article', undefined, 'ui-multi-tile'), img = el('img', undefined, 'ui-img'); img.alt = `${cam.cameraId} 畫面`;
        const cap = el('div', undefined, 'ui-multi-cap'); cap.append(el('span', cam.cameraId, 'ui-mono'), el('span', '', 'ui-chip ui-chip-neutral'));
        const empty = el('span', synthetic ? 'SYNTHETIC · 影像示意' : 'MISSING · 來源 RGB 未取得', 'ui-media-note');
        tile.append(img, empty, cap); grid.append(tile); trackParts.multi.set(cam.cameraId, {tile, img, cap, empty});
      }
      main.append(grid);
    }
    const tl = el('div', undefined, 'ui-timeline'); tl.id = 'ui-camera-timeline'; trackParts.timeline = tl;
    const ctl = el('div', undefined, 'ui-controls');
    const play = el('button', undefined, 'ui-play', {type: 'button', 'aria-label': '播放或暫停'}); play.id = 'ui-play'; play.addEventListener('click', () => store.dispatch({type: 'TOGGLE_PLAY'}));
    const speedSeg = el('span', undefined, 'ui-speeds'); trackParts.speeds = new Map();
    for (const sp of SUPPORTED_SPEEDS) { const b = el('button', `${sp}x`, 'ui-pillbtn', {type: 'button', 'data-speed': String(sp)}); b.addEventListener('click', () => store.dispatch({type: 'SET_SPEED', speed: sp})); speedSeg.append(b); trackParts.speeds.set(sp, b); }
    const actual = el('span', undefined, 'ui-mono ui-faint ui-small'); actual.id = 'ui-speed-note';
    const scrub = el('input', undefined, 'ui-scrub', {type: 'range', 'aria-label': '來源時間', step: '1'}); scrub.id = 'ui-scrub';
    scrub.addEventListener('input', () => { const tUs = Number(scrub.value); store.dispatch({type: 'PAUSE'}); store.dispatch({type: 'SET_T_US', tUs}); });
    ctl.append(play, speedSeg, actual, scrub); Object.assign(trackParts, {play, actual, scrub});
    const bar = el('div', undefined, 'ui-bottombar'); bar.id = 'ui-track-bar'; bar.append(tl, ctl);   // stays at the bottom while the content scrolls
    // aside: floor plan + journal
    const plan = el('div', undefined, 'ui-card ui-plan'); plan.id = 'ui-floorplan'; const journal = el('div', undefined, 'ui-card ui-journal'); journal.id = 'ui-journal';
    Object.assign(trackParts, {plan, journal}); aside.append(plan, journal);
    layout.append(main, aside); sCase2.append(layout, bar);
    trackParts.built = true;
  }
  function updateCase2(s, resp, view) {
    if (!trackParts.built) return;
    const cm = s.activeRun?.clock_mapping, [start] = playbackBounds(s), asOf = view.asOfUs, t = view.currentTUs;
    const chip = trackStateChip(view); trackParts.stateChip.textContent = chip.text; trackParts.stateChip.className = `ui-chip ui-chip-${chip.tone}`;
    const locked = view.singleView.segmentKind === 'ON_CAMERA';
    trackParts.title.textContent = `${trackParts.klass} · ${locked ? '已鎖定' : view.singleView.segmentKind === 'GAP' ? '盲區中' : view.singleView.segmentKind === 'LOST' ? '已跟丟' : view.statusText}`;
    const clock = wallClockText(cm, t) ?? `${(t / 1e6).toFixed(2)} s`;
    if (trackParts.stage) {
      const sv = view.singleView, cam = sv.activeCameraId;
      trackParts.stage.dataset.kind = sv.segmentKind;
      const fk = `${cam}|${t}|${sv.segmentKind}`;
      if (trackParts.frameKey !== fk) {   // one media request per frame, not per store tick
        trackParts.frameKey = fk; trackParts.img.hidden = true; trackParts.img.removeAttribute('src');
        const src = resolveFrameImageSrc({cameraId: cam, currentTUs: t, segmentKind: sv.segmentKind, lastObservedCameraId: sv.lastObservedCameraId, mediaResolver, synthetic, onResolved: u => { if (MEDIA.test(u ?? '') && trackParts.frameKey === fk && trackParts.img) { trackParts.img.src = u; trackParts.img.hidden = false; trackParts.note.hidden = true; } }});
        if (src) { trackParts.img.src = src; trackParts.img.hidden = false; trackParts.note.hidden = true; }
        else { trackParts.img.hidden = true; trackParts.img.removeAttribute('src'); trackParts.note.hidden = false; trackParts.note.textContent = sv.segmentKind === 'GAP' ? `盲區 · 沒有畫面（前一鏡頭 ${sv.lastObservedCameraId ?? '無'}）` : sv.segmentKind === 'LOST' ? `目標遺失（LOST）· 最後出現 ${sv.lastObservedCameraId ?? '無'}` : 'MISSING · 來源 RGB 未取得'; }
      }
      trackParts.stamp.textContent = `${cam ?? '—'} · ${clock}`;
      const prev = [...view.singleView.transitions].reverse().find(x => x.switch_at_us <= t && x.to_camera === cam && x.from_camera);
      trackParts.sw.textContent = prev ? `↳ 從 ${prev.from_camera} 切換` : ''; trackParts.sw.hidden = !prev;
      trackParts.tag.textContent = chip.text; trackParts.tag.dataset.tone = chip.tone; trackParts.tag.hidden = !locked;
    }
    if (trackParts.multi) for (const cam of view.multiView.cameras) {
      const part = trackParts.multi.get(cam.cameraId); if (!part) continue;
      part.tile.dataset.active = String(cam.isActive); part.cap.lastChild.textContent = cam.badge;
      const fk = `${t}|${cam.isActive}`; if (part.key === fk) continue; part.key = fk; part.img.hidden = true; part.img.removeAttribute('src');
      const src = resolveFrameImageSrc({cameraId: cam.cameraId, currentTUs: t, segmentKind: cam.isActive ? 'ON_CAMERA' : 'CANDIDATE', includeCandidate: true, mediaResolver, synthetic, onResolved: u => { if (MEDIA.test(u ?? '') && part.key === fk) { part.img.src = u; part.img.hidden = false; part.empty.hidden = true; } }});
      if (src) { part.img.src = src; part.img.hidden = false; part.empty.hidden = true; } else { part.img.hidden = true; part.empty.hidden = false; }
    }
    // camera timeline
    const tl = cameraTimeline(resp.single_view, {startUs: start, asOfUs: asOf, currentUs: t});
    const tlKey = JSON.stringify([tl.segments.map(x => [x.kind, x.cameraId, x.flex, x.current]), tl.marker.toFixed(3)]);
    if (trackParts.tlKey !== tlKey) {
      trackParts.tlKey = tlKey; const box = trackParts.timeline; box.replaceChildren();
      const labels = el('div', undefined, 'ui-tl-labels ui-mono'); labels.append(el('span', wallClockText(cm, start) ?? `${(start / 1e6).toFixed(1)} s`), el('span', '鏡頭時間軸'), el('span', wallClockText(cm, asOf) ?? `${(asOf / 1e6).toFixed(1)} s`));
      const row = el('div', undefined, 'ui-tl-row');
      for (const seg of tl.segments) { const k = seg.kind === 'ON_CAMERA' ? 'observed' : seg.kind === 'GAP' ? 'gap' : 'lost'; const b = el('span', seg.kind === 'ON_CAMERA' ? seg.cameraId.replace(/^CAM_/, '') : seg.kind === 'GAP' ? '盲區' : 'LOST', `ui-tl-seg is-${k}`, {'data-kind': seg.kind}); b.style.flex = `${seg.flex} 1 0`; if (seg.current) b.classList.add('current'); b.addEventListener('click', () => { store.dispatch({type: 'PAUSE'}); store.dispatch({type: 'SET_T_US', tUs: Math.min(seg.startUs, Math.max(0, asOf - 1))}); }); row.append(b); }
      if (tl.uncovered > 0.001) { const rest = el('span', undefined, 'ui-tl-seg is-empty'); rest.style.flex = `${tl.uncovered} 1 0`; row.append(rest); }
      const marker = el('span', undefined, 'ui-tl-marker'); marker.style.left = (tl.marker * 100).toFixed(2) + '%'; row.append(marker); box.append(labels, row);
    }
    // controls
    trackParts.play.textContent = s.playing ? '❚❚' : '▶'; trackParts.play.disabled = !canPlayNow(s);
    trackParts.play.title = canPlayNow(s) ? '' : '請先載入可播放的來源片段';
    for (const [sp, b] of trackParts.speeds) { b.classList.toggle('on', s.speed === sp); b.setAttribute('aria-pressed', String(s.speed === sp)); }
    const note = ctx.legacy?.speedNote?.() ?? ''; trackParts.actual.textContent = note;
    trackParts.scrub.min = String(start); trackParts.scrub.max = String(asOf); trackParts.scrub.value = String(s.tUs);
    // floor plan
    renderPlan(s, view, resp);
    renderJournal(resp, cm);
  }
  const canPlayNow = s => s.playing || canPlay(s);
  function renderPlan(s, view, resp) {
    const plan = floorPlan(view.topdown, {settings, singleView: resp.single_view, currentTUs: view.currentTUs});
    const key = JSON.stringify([plan.nodes, plan.observed, plan.blind, plan.blindVisible, plan.current, view.topdown?.blind_status]);
    if (trackParts.planKey === key) return; trackParts.planKey = key;
    const box = trackParts.plan; box.replaceChildren();
    const head = el('div', undefined, 'ui-card-head'); head.append(el('span', '樓層俯視圖'), el('span', plan.blindVisible ? 'INFERRED' : (view.topdown?.blind_status === 'UNAVAILABLE' || !view.topdown ? '預測不可用' : ''), plan.blindVisible ? 'ui-chip ui-chip-inferred' : 'ui-mono ui-faint ui-small')); box.append(head);
    if (!plan.available) { box.append(el('p', `UNKNOWN · 鏡頭位置未提供`, 'ui-muted ui-small')); return; }
    const g = svg('svg', {viewBox: '0 0 100 100', class: 'ui-plan-svg', role: 'img', 'aria-label': '樓層俯視圖：實線為已觀察路線，虛線為推測路線'});
    const grid = svg('pattern', {id: 'ui-grid', width: 10, height: 10, patternUnits: 'userSpaceOnUse'}); grid.append(svg('path', {d: 'M10 0H0V10', fill: 'none', stroke: 'var(--grid)', 'stroke-width': 0.4}));
    const defs = svg('defs'); defs.append(grid); g.append(defs, svg('rect', {x: 1, y: 1, width: 98, height: 98, rx: 2, fill: 'url(#ui-grid)', stroke: 'var(--line-strong)', 'stroke-width': 0.8}));
    if (plan.observed.length > 1) g.append(svg('polyline', {points: plan.observed.map(p => p.join(',')).join(' '), class: 'is-observed', fill: 'none', 'stroke-width': 1.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}));
    if (plan.blindVisible) g.append(svg('polyline', {points: plan.blind.map(p => p.join(',')).join(' '), class: 'is-inferred', fill: 'none', 'stroke-width': 1.4, 'stroke-dasharray': plan.dash, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}));
    for (const n of plan.nodes) {
      g.append(svg('rect', {x: n.x - 2, y: n.y - 1.5, width: 4, height: 3, rx: 0.8, class: n.isActive ? 'cam is-active' : 'cam'}));
      const t = svg('text', {x: n.x, y: n.y - 3, 'text-anchor': 'middle', class: 'cam-label'}); t.textContent = n.cameraId.replace(/^CAM_/, ''); g.append(t);
    }
    if (plan.current) { g.append(svg('circle', {cx: plan.current[0], cy: plan.current[1], r: 2.4, class: 'here'}), svg('circle', {cx: plan.current[0], cy: plan.current[1], r: 4, class: 'here-ring', fill: 'none'})); }
    box.append(g);
  }
  function renderJournal(resp, cm) {
    const rows = trackJournal(resp.single_view, cm), key = JSON.stringify(rows); if (trackParts.journalKey === key) return; trackParts.journalKey = key;
    const box = trackParts.journal; box.replaceChildren(el('span', '追蹤紀錄', 'ui-eyebrow'));
    if (!rows.length) box.append(el('p', '時間窗內無觀測紀錄', 'ui-muted ui-small'));
    for (const r of rows) { const row = el('div', undefined, 'ui-journal-row'); row.append(el('span', `${r.t} ${r.text}`, 'ui-mono'), el('span', r.state, `ui-chip ui-chip-${r.tone}`)); box.append(row); }
  }

  // ---- case 3: replay of existing events --------------------------------------------------------------------------
  let case3Built = false, case3Scope = null, frame = null;
  const eventLabel = e => e.label;
  function currentEventId() {
    if (integration()) return 'wall';
    if (cfg.ev) return cfg.ev;
    return new URL(url).searchParams.get('recording') === B05B_RECORDING_ID ? 'b05b' : 'wall';
  }
  function mountCase3() {
    const s = store.getState(), scope = JSON.stringify([integration(), s.activeRun?.run_id, s.bootstrap?.runs?.map(r => r.run_id)]);
    if (case3Scope !== scope) { case3Built = false; case3Scope = scope; }
    if (!case3Built) {
      case3Built = true; sCase3.replaceChildren();
      const bar = el('div', undefined, 'ui-events'); bar.id = 'ui-events'; bar.setAttribute('role', 'tablist');
      const cur = currentEventId();
      const entries = integration() ? (s.bootstrap?.runs ?? []).map(run => ({id: run.run_id, label: run.title ?? run.run_id, kind: 'page', run})) : EVENTS;
      for (const e of entries) {
        const ok = available(e, cfg), b = el('button', ok ? eventLabel(e) : `${eventLabel(e)}（未啟動）`, 'ui-pillbtn', {type: 'button', 'data-event': e.id, role: 'tab'});
        b.disabled = !ok; b.setAttribute('aria-pressed', String(e.id === cur)); b.classList.toggle('on', e.id === cur);
        b.addEventListener('click', () => e.run ? selectSource(e.run.run_id) : chooseEvent(e)); bar.append(b);
      }
      const note = el('p', undefined, 'ui-muted ui-small ui-event-note'); note.id = 'ui-event-note'; note.textContent = EVENTS.find(e => e.id === cur)?.note ?? '';
      const stage = el('div', undefined, 'ui-case3-stage'); stage.id = 'ui-case3-stage';
      sCase3.append(bar, note, stage);
      // The existing playback widgets are reused as they are (their ids and listeners stay): wall, Q1/Q2 slots and the transport.
      for (const n of [ctx.legacy?.wallSlot, ctx.legacy?.q1Slot, ctx.legacy?.q2Slot]) if (n) stage.append(n);
      if (ctx.legacy?.transport) sCase3.append(ctx.legacy.transport);
      frame = el('iframe', undefined, 'ui-embed', {title: '事件', referrerpolicy: 'no-referrer', sandbox: 'allow-scripts allow-same-origin allow-forms'}); frame.id = 'ui-event-frame'; frame.hidden = true;
      const notice = el('p', undefined, 'ui-feedback ui-embed-notice'); notice.id = 'ui-embed-notice'; notice.hidden = true; stage.append(frame, notice);
    }
    showEvent(currentEventId());
  }
  function showEvent(id) {
    const e = EVENTS.find(x => x.id === id) ?? EVENTS[0], stage = sCase3.querySelector('#ui-case3-stage'), embedded = e.kind === 'embed';
    for (const b of sCase3.querySelectorAll('[data-event]')) { const current = integration() ? b.dataset.event === store.getState().activeRun?.run_id : b.dataset.event === e.id; b.classList.toggle('on', current); b.setAttribute('aria-pressed', String(current)); }
    sCase3.querySelector('#ui-event-note').textContent = integration() ? `${store.getState().activeRun?.title ?? ''} · ${store.getState().activeRun?.source_kind ?? 'UNKNOWN'} · 身分未確認 · 物理通行與碰撞 UNKNOWN` : e.note;
    const src = embedded ? embedSrc(e, cfg, 'system', modeOf(e, cfg)) : null;
    frame.hidden = !embedded || !src;
    if (src && frame.getAttribute('src') !== src) frame.setAttribute('src', src); if (!src) frame.removeAttribute('src');
    const notice = sCase3.querySelector('#ui-embed-notice'); notice.hidden = !(embedded && !src); notice.textContent = embedded && !src ? 'UNKNOWN · 此事件尚未產生追蹤結果，或目標服務未啟動' : '';
    for (const n of [ctx.legacy?.wallSlot, ctx.legacy?.q1Slot, ctx.legacy?.q2Slot, ctx.legacy?.transport]) if (n) n.dataset.uiHiddenByEvent = String(embedded);
    stage.dataset.embedded = String(embedded);
    ctx.refreshWall?.();
  }
  function chooseEvent(e) {
    if (e.kind === 'page') { if (cfg.ev === e.id || (e.id === 'wall' && !cfg.ev && currentEventId() === 'wall')) return showEvent(e.id); globalThis.location?.assign?.(case3Url(e)); return; }
    showEvent(e.id);
  }
  ctx.setWallGate?.(() => screen === 'case3' && currentEventId() === 'wall' && !(sCase3.querySelector('#ui-case3-stage')?.dataset.embedded === 'true'));

  // ---- header context + badge -------------------------------------------------------------------------------------
  function renderHeader() {
    const s = store.getState();
    const runs = s.bootstrap?.runs ?? [], key = JSON.stringify(runs.map(r => [r.run_id, r.title]));
    if (sourceKey !== key) { sourceKey = key; sourceSelect.replaceChildren(...runs.map(r => el('option', r.title ?? r.run_id, undefined, {value: r.run_id}))); }
    sourceSelect.hidden = runs.length < 2; sourceSelect.value = s.activeRun?.run_id ?? '';
    const origin = s.responseOrigin ?? s.bootstrap?.data_origin ?? 'UNAVAILABLE', pres = sourcePresentation(origin, s.recordedKind ?? s.activeRun?.source_kind);
    const text = /SYNTHETIC/.test(pres.label) ? 'SYNTHETIC' : /PILOT/.test(pres.label) ? 'PILOT' : origin === 'RECORDED' ? 'REPLAY' : origin;
    badge.textContent = text; badge.title = pres.note;
    const parts = [];
    if (screen === 'case1') {
      const f = search.lastForm, cat = ctx.coreCatalog?.() ?? {regions: [], aliases: {}};
      if (f) { const names = (f.regionIds ?? []).map(id => cat.regions.find(r => r.value === id)?.label ?? id); parts.push(...names); if (f.classLabel) parts.push(classDisplay(f.classLabel, cat.aliases)); parts.push(`${f.start} → ${f.end}`); }
      ctxChip.textContent = parts.join(' · '); ctxChip.className = 'ui-chip-ctx';
    } else if (screen === 'case2') {
      ctxChip.textContent = '❯ 追蹤新目標…'; ctxChip.className = 'ui-chip-ctx is-cmd';
    } else { ctxChip.textContent = ''; }
    layoutSeg.hidden = screen !== 'case2' || !s.coreTrackResponse;
    segSingle.classList.toggle('on', s.playbackMode === 'single'); segMulti.classList.toggle('on', s.playbackMode === 'multi');
    segSingle.setAttribute('aria-pressed', String(s.playbackMode === 'single')); segMulti.setAttribute('aria-pressed', String(s.playbackMode === 'multi'));
    burger.hidden = screen === 'case3';
  }

  // ---- reactions to store changes ---------------------------------------------------------------------------------
  function afterStore(s, prev) {
    // search result landed
    if (s.coreSearchResponse && s.coreSearchResponse !== prev?.coreSearchResponse && search.startedAt && search.logged !== s.coreSearchResponse) {
      search.logged = s.coreSearchResponse; const ms = performance.now() - search.startedAt; const n = s.coreSearchResponse.hits?.length ?? 0;
      logEvent(`查找完成，${n} 個畫面`, n ? 'OBSERVED' : 'MISSING'); pushHistory('find', ms);
      saveSnapshot({...runIds(), lastSearch: {ms, total: n, perCamera: countsFromSearch(s.coreSearchResponse)}});
      if (screen === 'case1') setQuery(settings.searchPanelOpen);
    }
    if (s.coreTrackResponse && s.coreTrackResponse !== prev?.coreTrackResponse && track.startedAt && track.logged !== s.coreTrackResponse) {
      track.logged = s.coreTrackResponse; const ms = performance.now() - track.startedAt;
      pushHistory('lock', ms);
      const view = trackView();
      saveSnapshot({...runIds(), lastTrack: {lockMs: ms, classLabel: track.lastForm?.classLabel ?? null, cameraId: view?.singleView?.activeCameraId ?? null, state: trackStateChip(view).text, blindShare: blindShare(s.coreTrackResponse.single_view), autoSeed: true, reasons: view?.reasons ?? []}});
      logEvent(`追蹤${trackStateChip(view).text === 'UNKNOWN' ? '：' + s.coreTrackResponse.status : '已鎖定'}`, trackStateChip(view).text === 'OBSERVED' ? 'OBSERVED' : 'UNKNOWN');
      if (screen === 'case2') setQuery(false);
      // first lock: start playing when the source allows it
      const [startUs] = playbackBounds(s);
      if (canPlayNow(s) && !s.playing) { store.dispatch({type: 'SET_T_US', tUs: startUs}); store.dispatch({type: 'PLAY'}); }
    }
    // segment changes while playing → event log + snapshot
    if (s.coreTrackResponse && track.logged === s.coreTrackResponse) {
      const v = trackView(), seg = v?.singleView?.activeSegment; const key = seg ? `${seg.kind}|${seg.camera_id}|${seg.range_us?.[0]}` : null;
      if (key && key !== track.segKey) {
        const first = track.segKey === null; track.segKey = key;
        if (!first) { const chip = trackStateChip(v); logEvent(seg.kind === 'ON_CAMERA' ? `切到 ${seg.camera_id}` : seg.kind === 'GAP' ? '盲區，預測路線' : '目標遺失', seg.kind === 'ON_CAMERA' ? 'OBSERVED' : seg.kind === 'GAP' ? 'INFERRED' : 'MISSING');
          saveSnapshot({lastTrack: {...(snapshot.lastTrack ?? {}), cameraId: v.singleView.activeCameraId, state: chip.text}}); }
      }
    }
  }
  function render() {
    if (destroyed) return;
    renderHeader(); renderProgress();
    if (screen === 'case1') renderCase1();
    else if (screen === 'case2') renderCase2();
    else if (screen === 'case3') mountCase3();
  }
  let prevState = store.getState();
  disposers.push(store.subscribe(s => { afterStore(s, prevState); const prev = prevState; prevState = s; if (s.bootstrap !== prev.bootstrap || s.activeRun !== prev.activeRun) renderCatalog(); render(); }));
  const unsubCatalog = ctx.subscribeCatalog?.(renderCatalog); if (unsubCatalog) disposers.push(unsubCatalog);
  const noteTimer = setInterval(() => { if (screen === 'case2' && trackParts.actual) trackParts.actual.textContent = ctx.legacy?.speedNote?.() ?? ''; }, 500);
  disposers.push(() => clearInterval(noteTimer));
  const onStorage = e => { if (e.key === null || e.key === 'amidst.ui.settings.v1') settings = loadSettings(storage); };
  globalThis.addEventListener?.('storage', onStorage); disposers.push(() => globalThis.removeEventListener?.('storage', onStorage));

  // ---- start ------------------------------------------------------------------------------------------------------
  if (!settings.coverAnimation) host.classList.add('no-cover-anim');
  store.dispatch({type: 'SET_SWITCH_MODE', value: settings.switchMode});
  renderCatalog();
  const initial = route.initial ?? (settings.coverAnimation ? 'cover' : nextAfterCover(settings));
  go(initial);
  return {
    get screen() { return screen; }, go, setQuery,
    get settings() { return settings; },
    destroy() { destroyed = true; for (const d of disposers.splice(0)) d(); closeLightbox(); host.replaceChildren(); },
  };
}

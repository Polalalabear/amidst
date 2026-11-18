// Admin overview + settings panes. DOM only; figures come from admin-overview-model.mjs (bootstrap + this browser's
// own snapshot and event log). Anything without a measured source prints 尚未量測. Settings live only in this browser.
import {buildOverview} from './admin-overview-model.mjs';
import {liveLlmView, liveLlmRequest, loadLiveLlm, saveLiveLlm} from './live-llm-model.mjs';
import {NOT_MEASURED, SETTINGS_KEY, SNAPSHOT_KEY, EVENTLOG_KEY, DEFAULT_SETTINGS, EVENT_CHOICES, SPEEDS, CASES, loadSettings, saveSettings, readJson, taipeiTime} from './ui-model.mjs';

const NS = 'http://www.w3.org/2000/svg';
const el = (tag, text, cls, attrs) => { const n = document.createElement(tag); if (text !== undefined && text !== null) n.textContent = text; if (cls) n.className = cls; if (attrs) for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
const card = (...kids) => { const c = el('div', undefined, 'ui-stat'); c.append(...kids); return c; };
const chipFor = state => el('span', state, state === 'OBSERVED' ? 'ui-chip ui-chip-observed' : state === 'INFERRED' ? 'ui-chip ui-chip-inferred' : 'ui-chip ui-chip-missing');

export function mountTabs(root = document) {
  const titles = {overview: '系統概況', settings: '設定', playback: '鏡頭播放', records: '紀錄'};
  const show = () => {
    const tab = Object.hasOwn(titles, location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
    for (const p of root.querySelectorAll('[data-pane]')) p.hidden = p.dataset.pane !== tab;
    for (const a of root.querySelectorAll('[data-tab]')) a.toggleAttribute('aria-current', a.dataset.tab === tab), a.dataset.tab === tab ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
    root.querySelector('#admin-title').textContent = titles[tab];
  };
  globalThis.addEventListener('hashchange', show); show();
  const tick = () => { const t = taipeiTime(new Date()); if (t) root.querySelector('#admin-clock').textContent = t; };
  tick(); const timer = setInterval(tick, 1000);
  return {destroy() { clearInterval(timer); globalThis.removeEventListener('hashchange', show); }};
}

export function mountOverview(box, {getBootstrap, storage = globalThis.localStorage}) {
  function draw() {
    const m = buildOverview({bootstrap: getBootstrap(), snapshot: readJson(storage, SNAPSHOT_KEY, {}) ?? {}, log: readJson(storage, EVENTLOG_KEY, []) ?? []});
    box.replaceChildren();
    // status cards
    const top = el('section', undefined, 'ui-admin-sec'), grid = el('div', undefined, 'ui-grid4');
    const camDots = el('div', undefined, 'ui-camdots'); for (const c of m.cameras.list) camDots.append(el('span', undefined, c.state === 'tracking' ? 'is-tracking' : c.state === 'missing' ? 'is-missing' : '', {title: c.id}));
    grid.append(
      card(el('span', '鏡頭 · CAMERAS', 'ui-stat-label'), m.cameras.total ? el('span', `${m.cameras.withData}`, 'ui-stat-value') : el('span', NOT_MEASURED, 'ui-stat-value is-unmeasured'), m.cameras.total ? camDots : el('span'), el('span', m.cameras.total ? `${m.cameras.total} 台中有資料；橘色＝目前追蹤中的鏡頭` : '尚未載入來源', 'ui-stat-note')),
      // 2026-11-17 layout: target large, camera by readable name (code small), plain state chips that wrap, codes small below.
      (() => { const t = m.tracking, c = card(el('span', '目前追蹤 · TRACKING', 'ui-stat-label')); c.classList.add('ui-track-card');
        if (!t) { c.append(el('span', '尚未追蹤', 'ui-stat-value is-unmeasured')); return c; }
        const camRow = el('div', undefined, 'ui-track-cam'); camRow.append(el('span', t.camera?.name ?? '—', 'ui-track-cam-name ui-accent', {title: t.camera?.title ?? ''}), ...(t.camera?.known ? [el('span', t.camera.code, 'ui-mono ui-track-code')] : []));
        const chips = el('div', undefined, 'ui-chips ui-track-chips'); const st = chipFor(t.stateCode); st.textContent = t.stateText; st.title = t.stateCode; st.classList.add('ui-track-state');
        chips.append(st, el('span', '身分未確認', 'ui-chip ui-chip-neutral'), ...(t.autoSeed ? [el('span', '自動種子', 'ui-chip ui-chip-neutral')] : []), ...t.reasonChips.map(r => el('span', r.text, 'ui-chip ui-chip-neutral', {title: r.code})));
        c.append(el('span', t.target, 'ui-stat-value'), camRow, chips);
        if (t.reasons.length) c.append(el('p', `技術代碼：${t.stateCode} · ${t.reasons.join(' · ')}`, 'ui-mono ui-track-codes'));
        return c; })(),
      card(el('span', '最近事件 · LATEST', 'ui-stat-label'), m.latest ? el('span', m.latest.text, 'ui-stat-value is-unmeasured') : el('span', '尚無事件', 'ui-stat-value is-unmeasured'), m.latest ? el('span', taipeiTime(new Date(m.latest.at)) ?? '', 'ui-mono ui-stat-note') : el('span')),
      (() => { const c = card(el('span', '涵蓋區域 · COVERAGE', 'ui-stat-label')); const row = el('div', undefined, 'ui-chips'); for (const r of m.regions) row.append(el('span', r.name, 'ui-chip ui-chip-observed', {title: r.title ?? r.id})); c.append(m.regions.length ? row : el('span', NOT_MEASURED, 'ui-stat-value is-unmeasured')); return c; })());
    top.append(grid); box.append(top);
    // detection metrics
    const met = el('section', undefined, 'ui-admin-sec'); const mh = el('div', undefined, 'row'); mh.append(el('span', '偵測數據', 'ui-h3'), el('span', '沒有實測來源的欄位顯示「尚未量測」', 'note')); met.append(mh);
    const mg = el('div', undefined, 'ui-grid4');
    for (const x of m.metrics) {
      const v = x.measured ? (() => { const s = el('span', String(x.value), 'ui-stat-value'); s.append(el('small', ` ${x.unit}`)); return s; })() : el('span', NOT_MEASURED, 'ui-stat-value is-unmeasured');
      const c = card(el('span', x.label, 'ui-stat-label'), v);
      if (x.spark) { const s = document.createElementNS(NS, 'svg'); s.setAttribute('viewBox', '0 0 220 40'); s.setAttribute('preserveAspectRatio', 'none'); s.setAttribute('class', 'ui-spark'); const pl = document.createElementNS(NS, 'polyline'); pl.setAttribute('points', x.spark); s.append(pl); c.append(s); }
      c.append(el('span', x.note, 'ui-stat-note')); c.dataset.metric = x.key; c.dataset.measured = String(x.measured); mg.append(c);
    }
    met.append(mg); box.append(met);
    // per camera
    const pc = el('section', undefined, 'ui-admin-sec'), pcc = el('div', undefined, 'ui-stat'); const ph = el('div', undefined, 'row'); ph.append(el('span', '各鏡頭偵測數', 'ui-h3'), el('span', m.perCameraNote, 'note'), el('span', '■ 人物', 'note'), el('span', '■ 物件', 'note'));
    ph.children[2].style.color = 'var(--person)'; ph.children[3].style.color = 'var(--object)'; pcc.append(ph);
    const bars = el('div', undefined, 'ui-bars'), max = Math.max(1, ...m.perCamera.map(r => r.total));
    for (const r of m.perCamera) {
      const row = el('div', undefined, 'ui-bar-row'); row.append(el('span', r.cameraId, 'ui-bar-name'));
      if (!r.measured) row.append(el('span', NOT_MEASURED, 'badge'));
      else { const tr = el('span', undefined, 'ui-bar-track'); tr.style.width = Math.max(4, r.total / max * 88) + '%'; const p = el('span', undefined, 'p', {title: `${r.cameraId} 人物 ${r.person}`}), o = el('span', undefined, 'o', {title: `${r.cameraId} 物件 ${r.object}`}); p.style.flex = `${r.person} 0 0`; o.style.flex = `${r.object} 0 0`; tr.append(p, o); row.append(tr, el('span', String(r.total), 'ui-mono')); }
      bars.append(row);
    }
    pcc.append(m.perCamera.length ? bars : el('span', NOT_MEASURED, 'note')); pc.append(pcc); box.append(pc);
    // timeline + events
    const bot = el('section', undefined, 'ui-admin-sec'), two = el('div', undefined, 'ui-two');
    const tl = el('div', undefined, 'ui-stat'); tl.append(el('span', '時間軸 · 每 10 秒事件數（本機事件流）', 'ui-stat-label'));
    if (!m.timeline.bins.length) tl.append(el('span', '尚無事件', 'ui-stat-value is-unmeasured'));
    else { const h = el('div', undefined, 'ui-hist'), peak = Math.max(1, ...m.timeline.bins.map(b => b.OBSERVED + b.INFERRED + b.MISSING + b.UNKNOWN));
      for (const b of m.timeline.bins) { const col = el('div'); col.title = `${taipeiTime(new Date(b.at))}`; col.style.height = ((b.OBSERVED + b.INFERRED + b.MISSING + b.UNKNOWN) / peak * 100) + '%'; for (const k of ['OBSERVED', 'INFERRED', 'MISSING', 'UNKNOWN']) if (b[k]) { const s = el('span', undefined, `s-${k}`); s.style.flex = `${b[k]} 0 0`; col.append(s); } h.append(col); }
      tl.append(h, el('div', undefined, 'row ui-mono')); tl.lastChild.append(el('span', taipeiTime(new Date(m.timeline.from)) ?? '', 'note'), el('span', taipeiTime(new Date(m.timeline.to)) ?? '', 'note')); }
    const ev = el('div', undefined, 'ui-stat'); ev.id = 'log'; ev.append(el('span', '事件流 · EVENTS', 'ui-stat-label'));
    const list = el('div', undefined, 'ui-events-list'); for (const e of m.events.slice(0, 12)) { const r = el('div', undefined, 'ui-ev-row'); r.append(el('span', taipeiTime(new Date(e.at)) ?? '', 't'), el('span', e.text, 'x'), chipFor(e.state)); list.append(r); }
    ev.append(m.events.length ? list : el('span', '尚無事件', 'ui-stat-value is-unmeasured'));
    two.append(tl, ev); bot.append(two); box.append(bot);
  }
  draw();
  const on = e => { if (e.key === null || [SNAPSHOT_KEY, EVENTLOG_KEY].includes(e.key)) draw(); };
  globalThis.addEventListener('storage', on);
  return {draw, destroy() { globalThis.removeEventListener('storage', on); }};
}

export function mountSettings(box, {getBootstrap, storage = globalThis.localStorage, liveLlm = {load: loadLiveLlm, save: saveLiveLlm}}) {
  let draft = loadSettings(storage);
  // 即時 LLM 決策：狀態在 live 伺服器，不進瀏覽器設定、不屬於「儲存」；每次操作立即送出，畫面一律用後端回報的狀態。
  let live = null, liveBusy = false;
  const liveReload = async () => { live = await liveLlm.load(); draw(); };
  const liveSend = async body => { liveBusy = true; draw(); live = await liveLlm.save(body); liveBusy = false; draw(); };
  function seg(options, value, set) { const s = el('span', undefined, 'ui-seg'); for (const [v, label] of options) { const b = el('button', label, v === value ? 'on' : '', {type: 'button'}); b.addEventListener('click', () => { set(v); draw(); }); s.append(b); } return s; }
  function toggle(on, set) { const b = el('button', undefined, 'ui-toggle', {type: 'button', role: 'switch', 'aria-checked': String(on)}); b.addEventListener('click', () => { set(!on); draw(); }); return b; }
  function num(value, min, max, set, unit) { const i = el('input', undefined, 'ui-num', {type: 'number', min: String(min), max: String(max)}); i.value = String(value); i.addEventListener('change', () => { set(Number(i.value)); draw(); }); const w = el('span', undefined, 'row'); w.append(i, ...(unit ? [el('span', unit, 'note')] : [])); return w; }
  const row = (title, desc, control) => { const r = el('div', undefined, 'ui-set-row'), d = el('div', undefined, 'd'); d.append(el('b', title), el('span', desc)); r.append(d, control); return r; };
  const group = (label, ...rows) => { const g = el('div', undefined, 'ui-card'); g.append(el('span', label, 'ui-eyebrow'), ...rows); return g; };
  function draw() {
    const boot = getBootstrap(), run = boot?.runs?.[0] ?? null;
    box.replaceChildren();
    const head = el('header', undefined, 'ui-admin-head'); head.style.paddingTop = '0';
    const note = el('span', '設定值只存在這個瀏覽器裡', 'note'); const saved = el('span', '', 'note'); saved.id = 'settings-saved';
    const reset = el('button', '還原預設', 'ibtn', {type: 'button'}), save = el('button', '儲存', 'ibtn primary', {type: 'button'});
    reset.addEventListener('click', () => { draft = {...DEFAULT_SETTINGS}; draw(); }); save.addEventListener('click', () => { const ok = saveSettings(storage, draft); draft = loadSettings(storage); saved.textContent = ok ? '已儲存' : '儲存失敗（瀏覽器未開放儲存）'; });
    const act = el('div', undefined, 'row'); act.append(note, saved, reset, save); head.append(el('span'), act); box.append(head);
    const grid = el('div', undefined, 'ui-set-grid');
    const set = k => v => { draft = {...draft, [k]: v}; };
    grid.append(
      group('展示 · DEMO',
        row('預設進入', '封面點「進入系統」後直接打開的 case（不選＝顯示三選一）', seg([[null, '選擇'], ...CASES.map(c => [c.id, c.id])], draft.defaultCase, set('defaultCase'))),
        row('預設事件', '進入查看時先載入哪一個事件', seg(EVENT_CHOICES.map(e => [e.id, e.label]), draft.defaultEvent, set('defaultEvent'))),
        row('資料來源', '由伺服器宣告，這裡只顯示', el('span', boot ? `${boot.data_origin}` : 'UNKNOWN', 'badge')),
        row('封面動畫', '關掉後直接顯示選擇畫面', toggle(draft.coverAnimation, set('coverAnimation'))),
        row('前台展示模式', '開啟時前台和後台的事件名稱只顯示短名稱（如 A4-1），技術標籤收進 ⓘ', toggle(draft.presentationMode, set('presentationMode')))),
      group('追蹤 · TRACK',
        row('預設畫面', '鎖定後用單畫面或多畫面', seg([['single', '單畫面'], ['multi', '多畫面']], draft.trackLayout, set('trackLayout'))),
        row('預設播放速度', '實際速度會顯示在播放列旁', seg(SPEEDS.map(s => [s, `${s}x`]), draft.trackSpeed, set('trackSpeed'))),
        row('盲區顯示推測路線', '俯視圖上畫出虛線', toggle(draft.blindPlan, set('blindPlan'))),
        row('跟丟後保留推測路線', '秒數到了就停止畫虛線', num(draft.keepBlindSec, 1, 600, set('keepBlindSec'), '秒'))),
      group('查找 · SEARCH',
        row('結果上限', '結果牆最多顯示幾張', num(draft.resultLimit, 1, 200, set('resultLimit'))),
        row('查詢窗預設', '進入 case1 時查詢窗展開或收起（尚無結果時一律展開）', seg([[true, '展開'], [false, '收起']], draft.searchPanelOpen, set('searchPanelOpen'))),
        row('結果逐張淡入', '關掉則一次顯示', toggle(draft.staggerResults, set('staggerResults')))),
      group('即時模式 · LIVE', (() => {
        const v = liveLlmView(live), c = el('span', undefined, 'row');
        const sw = toggle(v.checked, () => liveSend(liveLlmRequest(!v.checked, v.mode, v.model))); sw.disabled = v.disabled || liveBusy; sw.id = 'live-llm-switch';
        const mode = seg([['review', 'LLM 覆核'], ['lead', 'LLM 主導']], v.mode, m => { if (v.checked) liveSend(liveLlmRequest(true, m, v.model)); });
        mode.querySelectorAll('button').forEach(b => { b.disabled = v.disabled || liveBusy; });
        c.append(sw, mode); return row('即時 LLM 決策', '預設關閉；只影響即時模式的 live 伺服器，不影響這頁的「追蹤方式」。連不上 live 伺服器時顯示不可用', c);
      })(), (() => { const s = el('div', undefined, 'ui-set-row'); const d = el('div', undefined, 'd'), v = liveLlmView(live); const st = el('span', `${v.text}${v.detail ? ` · ${v.detail}` : ''}`, `live-llm-status tone-${v.tone}`); st.id = 'live-llm-status'; st.setAttribute('role', 'status'); d.append(el('b', '狀態'), st); s.append(d); return s; })()),
      group('系統 · SYSTEM',
        row('物件偵測', '來源未宣告偵測器名稱', el('span', 'UNKNOWN', 'badge')),
        row('一句話查詢解析方式', '搜尋框（⌘K）怎麼解析句子；API／本機模型失敗或逾時會自動退到下一種，固定句型不需要金鑰', seg([['RULES', '固定句型'], ['LOCAL', '本機模型'], ['API', 'API']], draft.nlParser, set('nlParser'))),
        row('追蹤方式', '規則串接（RULE_ONLY）或 Agent（需來源支援）', seg([['RULE_ONLY', '規則'], ['AGENT_SEQUENTIAL', 'Agent']], draft.switchMode, set('switchMode'))),
        row('場景圖', run ? `${run.scene_id} · 區域圖 ${String(run.region_graph_sha256 ?? '').slice(0, 8) || 'UNKNOWN'} · 鏡頭圖 ${String(run.camera_graph_sha256 ?? '').slice(0, 8) || 'UNKNOWN'}` : '尚未載入來源', el('span', run ? '檢視' : NOT_MEASURED, 'badge'))));
    box.append(grid);
  }
  draw(); liveReload();
  return {draw, get draft() { return draft; }};
}

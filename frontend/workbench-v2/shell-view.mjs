// DOM shell: top bar, rail + panel (pinned / floating / collapsed), main area toggle, transport bar,
// legend. Content of the grid, 3D, timeline and panel sections is mounted by later tasks into the slots
// returned by mountShell(). Only the pinned/collapsed rail choice is stored in localStorage.

import { classifyT, formatFrame, formatSeconds, frameIndexAt, sampleAgeMs, stepTMs } from './clock.mjs';
import { NARROW_PX, MAIN_PADDING_PX, fitTiles } from './layout.mjs';
import { IDENTITY_LEGEND, legendItems } from './tokens.mjs';

export const RAIL_STORAGE_KEY = 'amidst.wb2.rail';

export function loadRailPref(storage = globalThis.localStorage) {
  try {
    const v = storage?.getItem(RAIL_STORAGE_KEY);
    return v === 'rail' ? 'rail' : 'pinned';
  } catch { return 'pinned'; }
}

export function saveRailPref(rail, storage = globalThis.localStorage) {
  if (rail !== 'pinned' && rail !== 'rail') return; // floating is never persisted
  try { storage?.setItem(RAIL_STORAGE_KEY, rail); } catch { /* storage unavailable: page still works */ }
}

const SECTION_TITLES = { find: '查找', demo: 'Demo', evidence: '證據', layers: '圖層', prov: '來源與隔離' };
const MODE_SECTIONS = {
  browse: ['evidence', 'layers', 'prov'],
  find: ['find', 'evidence', 'prov'],
  demo: ['demo', 'evidence', 'prov'],
};

export function sectionsForMode(mode) { return MODE_SECTIONS[mode] ?? MODE_SECTIONS.browse; }

// Text for the transport bar from state. `run` may be null before a source is loaded.
export function timeReadout(state) {
  const run = state.run;
  if (!run) return { now: `${formatSeconds(state.tMs)} s`, total: '/ — s', sub: '無來源（外框預覽）', status: 'NO_RUN' };
  const k = frameIndexAt(state.tMs, run.fps);
  return {
    now: `${formatSeconds(state.tMs)} s`,
    total: `/ ${run.duration_s} s`,
    sub: `影格 ${formatFrame(k)} · sample_age +${formatSeconds(sampleAgeMs(state.tMs, run.fps))} s`,
    status: classifyT(state.tMs, run.duration_s),
  };
}

function isTypingTarget(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable === true;
}

const SVG_NS = 'http://www.w3.org/2000/svg';
function swatch(item) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('width', '24'); svg.setAttribute('height', '10'); svg.setAttribute('viewBox', '0 0 24 10');
  const color = `var(${item.color_token})`;
  const line = (y, extra = {}) => {
    const l = document.createElementNS(SVG_NS, 'line');
    l.setAttribute('x1', '1'); l.setAttribute('x2', '23'); l.setAttribute('y1', y); l.setAttribute('y2', y);
    l.setAttribute('stroke', color);
    for (const [k, v] of Object.entries(extra)) l.setAttribute(k, v);
    svg.append(l);
  };
  const style = item.line?.style;
  if (style === 'solid' && item.line.hollow) { line(2.5); line(7.5); }
  else if (style === 'solid') line(5);
  else if (style === 'dash-short') line(5, { 'stroke-dasharray': '3 3' });
  else if (style === 'dash-long') { line(5, { 'stroke-dasharray': '10 6' }); line(2, { 'stroke-opacity': '.4' }); line(8, { 'stroke-opacity': '.4' }); }
  else if (style === 'dotted') line(5, { 'stroke-dasharray': '1.5 3' });
  else if (style === 'hatch' || style === 'hatch-ink') {
    for (let x = -4; x < 24; x += 5) {
      const l = document.createElementNS(SVG_NS, 'line');
      l.setAttribute('x1', x); l.setAttribute('y1', 10); l.setAttribute('x2', x + 8); l.setAttribute('y2', 0); l.setAttribute('stroke', color);
      svg.append(l);
    }
  } else return null;
  return svg;
}

export function renderLegend(el) {
  el.replaceChildren();
  for (const item of legendItems()) {
    const span = document.createElement('span');
    span.className = item.code === '±m' ? 'it uncert' : 'it';
    span.dataset.code = item.code;
    if (item.code !== '±m') {
      const sw = swatch(item);
      if (sw) span.append(sw);
      span.append(item.text);
      if (item.symbol) { const s = document.createElement('small'); s.textContent = item.symbol; span.append(s); }
    } else {
      span.textContent = item.text;
    }
    el.append(span);
  }
  const id = document.createElement('span');
  id.className = 'id';
  id.textContent = IDENTITY_LEGEND;
  el.append(id);
}

export function mountShell(root, store) {
  const $ = (sel) => root.querySelector(sel);
  const $$ = (sel) => [...root.querySelectorAll(sel)];
  const work = $('#work');
  const view = $('#view');
  const panelBody = $('#rail');

  renderLegend($('#legend'));

  const slots = {
    syntheticStrip: $('#synth'),
    grid2d: $('#view2d'),
    plan3d: $('#view3d .v3-stage'),
    view3d: $('#view3d'),
    pip: $('#pip'),
    uncertaintyReadouts: $('#uncert'),
    timeline: $('#tlwrap'),
    panelBody,
    pager: $('#pager'),
    caption: $('#caption'),
    blocker: $('#blocker'),
    eventSelect: $('#evseg'),
    sceneSelect: $('#scene'),
    tag3d: $('#v3tag'),
  };

  // --- panel sections (empty shells; later tasks fill the `.sec-body` of each) ---
  let renderedMode = null;
  function renderSections(mode) {
    if (renderedMode === mode) return;
    renderedMode = mode;
    panelBody.replaceChildren();
    for (const id of sectionsForMode(mode)) {
      const sec = document.createElement('section');
      sec.className = 'sec'; sec.dataset.section = id; sec.id = `sec-${id}`;
      const h = document.createElement('h3'); h.textContent = SECTION_TITLES[id];
      const body = document.createElement('div');
      body.className = 'sec-body'; body.dataset.slot = `section-${id}`; body.dataset.placeholder = `${SECTION_TITLES[id]}（後續任務掛載）`;
      sec.append(h, body);
      panelBody.append(sec);
    }
  }

  // --- events -> store ---
  const d = (a) => store.dispatch(a);
  $('#ham').addEventListener('click', () => d({ type: 'TOGGLE_BURGER' }));
  for (const b of $$('#icons [data-open]')) b.addEventListener('click', () => d({ type: 'ICON_CLICK', id: b.dataset.open }));
  for (const b of $$('#railseg [data-rail]')) b.addEventListener('click', () => d({ type: 'SET_RAIL', rail: b.dataset.rail }));
  for (const b of $$('#modeseg [data-mode]')) b.addEventListener('click', () => d({ type: 'SET_MODE', mode: b.dataset.mode }));
  for (const b of $$('#mainseg [data-main]')) b.addEventListener('click', () => d({ type: 'SET_MAIN', main: b.dataset.main }));
  for (const b of $$('#sizeseg [data-size]')) b.addEventListener('click', () => d({ type: 'SET_SIZE', size: Number(b.dataset.size) }));
  for (const b of $$('#speedseg [data-speed]')) b.addEventListener('click', () => d({ type: 'SET_SPEED', speed: Number(b.dataset.speed) }));
  $('#play').addEventListener('click', () => d({ type: 'TOGGLE_PLAY' }));
  const step = (dir) => { const s = store.getState(); if (s.run) { d({ type: 'PAUSE' }); d({ type: 'SET_T', tMs: stepTMs(s.tMs, s.run.fps, dir, s.run.duration_s) }); } };
  $('#prev').addEventListener('click', () => step(-1));
  $('#next').addEventListener('click', () => step(1));
  // Capture phase and no preventDefault: a click on the main area closes the floating panel and still takes effect.
  $('#mainsec').addEventListener('pointerdown', () => d({ type: 'MAIN_POINTER' }), true);

  const onKey = (e) => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
    if (e.key === 'Escape') d({ type: 'ESCAPE' });
    else if (e.key === 'v' || e.key === 'V') d({ type: 'TOGGLE_MAIN' });
    else if (e.key === '[') d({ type: 'TOGGLE_PIN_RAIL' });
    else if (e.key === ' ' && !(e.target instanceof HTMLButtonElement)) { e.preventDefault(); d({ type: 'TOGGLE_PLAY' }); }
    else if (e.key === 'ArrowLeft') step(-1);
    else if (e.key === 'ArrowRight') step(1);
  };
  document.addEventListener('keydown', onKey);

  // --- store -> DOM ---
  const pressed = (el, on) => el.setAttribute('aria-pressed', on ? 'true' : 'false');
  function measureTiles(s) {
    const narrow = globalThis.innerWidth < NARROW_PX;
    const width = view.clientWidth - 2 * MAIN_PADDING_PX;
    const height = view.clientHeight - 2 * MAIN_PADDING_PX;
    if (width <= 0 || height <= 0) return null;
    return fitTiles({ size: s.size, width, height, narrow });
  }

  function render(s) {
    work.dataset.rail = s.rail;
    work.dataset.mode = s.mode;
    work.dataset.main = s.main;
    for (const b of $$('#railseg [data-rail]')) pressed(b, b.dataset.rail === s.rail);
    for (const b of $$('#modeseg [data-mode]')) pressed(b, b.dataset.mode === s.mode);
    for (const b of $$('#mainseg [data-main]')) pressed(b, b.dataset.main === s.main);
    for (const b of $$('#sizeseg [data-size]')) pressed(b, Number(b.dataset.size) === s.size);
    for (const b of $$('#speedseg [data-speed]')) pressed(b, Number(b.dataset.speed) === s.speed);
    pressed($('#ham'), s.rail !== 'rail');
    for (const b of $$('#icons [data-open]')) pressed(b, s.rail !== 'rail' && b.dataset.open === s.panelSection);

    $('#evdot').hidden = s.selection === null;
    $('#paneltitle').textContent = SECTION_TITLES[s.panelSection] ?? '面板';
    renderSections(s.mode);

    const is2d = s.main === '2d';
    slots.grid2d.hidden = !is2d;
    slots.view3d.hidden = is2d;
    $('#h2d').hidden = !is2d;
    $('#dims').hidden = !is2d;
    $('#h3d').hidden = is2d;

    const t = timeReadout(s);
    $('#tnow').firstChild.nodeValue = t.now;
    $('#tnow small').textContent = t.total;
    $('#tsub').textContent = t.sub;
    $('#play').textContent = s.playing ? '❚❚ 暫停' : '▶ 播放';
    $('#play').setAttribute('aria-label', s.playing ? '暫停' : '播放');
    $('#runid').textContent = s.run ? `run_id ${s.run.run_id ?? 'UNKNOWN'}` : 'run_id UNKNOWN';
    $('#prev').disabled = $('#next').disabled = !s.run;

    updateTiles(s);
  }

  function updateTiles(s) {
    const fit = measureTiles(s);
    const dims = $('#dims');
    if (!fit) { dims.textContent = '—'; return; }
    dims.textContent = `每格 ${fit.width}×${fit.height} px · ${fit.cols}×${fit.rows}`;
    slots.grid2d.style.setProperty('--tile-w', `${fit.width}px`);
    slots.grid2d.style.setProperty('--tile-h', `${fit.height}px`);
    slots.grid2d.dataset.cols = String(fit.cols);
    slots.grid2d.dataset.rows = String(fit.rows);
  }

  store.subscribe(render);
  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => updateTiles(store.getState())) : null;
  ro?.observe(view);
  store.subscribe((s) => saveRailPref(s.rail));
  render(store.getState());

  return {
    slots,
    setSynthetic(note) {
      slots.syntheticStrip.hidden = !note;
      $('#synth-note').textContent = note ?? '';
      slots.tag3d.hidden = !note;
    },
    setBlocker(content) {
      slots.blocker.hidden = !content;
      if (content) slots.blocker.replaceChildren(content); else slots.blocker.replaceChildren();
    },
    setCaption(text) {
      slots.caption.hidden = !text;
      slots.caption.textContent = text ?? '';
    },
    destroy() {
      document.removeEventListener('keydown', onKey);
      ro?.disconnect();
    },
  };
}

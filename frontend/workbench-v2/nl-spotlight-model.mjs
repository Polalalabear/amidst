// N1 Spotlight: pure model. Turns a parse (docs/contracts/NL_QUERY_PARSE_V1.md) into chips and into a plan for the existing
// tag panel. Nothing here runs a query; vocabulary labels come from the run (same source as the tag panel menus).
import {classDisplay, colorDisplay, wallClockText} from './ui-model.mjs';
import {trackClassSupport} from './core-search-track-model.mjs';

export const PARSER_MODES = Object.freeze([['RULES', '固定句型'], ['LOCAL', '本機模型'], ['API', 'API']]);
export const UNRECOGNIZED_LABEL = '未辨識';

const clock = s => { const t = Math.round(s); return [Math.floor(t / 3600), Math.floor(t / 60) % 60, t % 60].map((v, i) => i ? String(v).padStart(2, '0') : String(v)).join(':'); };

export function chipsFromParse(parse, run) {
  if (!parse) return [];
  const chips = [];
  if (parse.action) chips.push({kind: 'action', text: parse.action});
  const regions = new Map((run?.region_catalog?.regions ?? []).map(r => [r.region_id, r.label]));
  const aliases = run?.supported_classes?.aliases ?? {}, classes = new Set(run?.supported_classes?.class_labels ?? []);
  for (const id of parse.location ?? []) chips.push({kind: 'location', text: regions.get(id) ?? id, value: id});
  for (const t of parse.target ?? []) chips.push({kind: 'target', text: classes.has(t) ? classDisplay(t, aliases) : colorDisplay(t), value: t});
  if (parse.time) chips.push({kind: 'time', text: `${clock(parse.time.start)} – ${clock(parse.time.end)}`});
  for (const u of parse.unrecognized ?? []) chips.push({kind: 'unrecognized', text: `${UNRECOGNIZED_LABEL}：${u}`, value: u});
  return chips;
}

// Result rows for the bar (arrow keys pick, Enter enters). The sentence's action cue goes first; without a cue the search
// window is first, whatever tab is open: the top search box is a search entry, tracking needs an explicit 「追蹤」 or a pick.
export function optionsFromParse(parse, chips = []) {
  if (!parse) return [];
  const detail = chips.filter(c => c.kind === 'location' || c.kind === 'target' || c.kind === 'time').map(c => c.text);
  const search = {kind: 'search', title: '查找', detail: detail.length ? detail.join(' · ') : '開啟查找窗'};
  const trackDetail = chips.filter(c => c.kind === 'target' || c.kind === 'time').map(c => c.text);
  const track = {kind: 'track', title: '追蹤', detail: trackDetail.length ? trackDetail.join(' · ') : '開啟追蹤窗'};
  return parse.action === '追蹤' ? [track, search] : [search, track];
}

// Plan for the existing query windows. `kind` (the row the user entered) wins; otherwise the action cue; otherwise search.
// `currentScreen` is kept for callers but no longer picks the window (2026-11-17: typing in the 追蹤 tab must reach 查找).
export function planFromParse(parse, run, currentScreen = null, kindOverride = null) {
  const classes = new Set(run?.supported_classes?.class_labels ?? []), colors = new Set(run?.supported_classes?.color_vocabulary?.labels ?? []);
  void currentScreen;
  const kind = kindOverride === 'track' || kindOverride === 'search' ? kindOverride : parse.action === '追蹤' ? 'track' : 'search';
  const notes = [];
  let classLabel = (parse.target ?? []).find(t => classes.has(t)) ?? '';
  const colorLabel = (parse.target ?? []).find(t => colors.has(t)) ?? '';
  if (colorLabel && !classLabel) classLabel = 'person';   // colour is a property of person in the tag panel
  let regionIds = [...(parse.location ?? [])];
  if (kind === 'track' && regionIds.length) { notes.push('追蹤不使用地點，已略過'); regionIds = []; }
  if (kind === 'track' && classLabel && trackClassSupport(classLabel) !== 'SUPPORTED') { notes.push('追蹤目前只支援人物，特徵未填入'); classLabel = ''; }
  const mapping = run?.clock_mapping;
  let start = null, end = null;
  if (parse.time) {
    const us = s => Math.round(s * 1e6);
    start = wallClockText(mapping, us(parse.time.start)); end = wallClockText(mapping, us(parse.time.end));
    if (!start || !end) { notes.push('此來源沒有時鐘對照，時間未填入'); start = end = null; }
  }
  if (parse.unrecognized?.length) notes.push(`${UNRECOGNIZED_LABEL}：${parse.unrecognized.join('、')}`);
  return {kind, screen: kind === 'track' ? 'case2' : 'case1', regionIds, classLabel, colorLabel: classLabel === 'person' ? colorLabel : '', start, end, notes};
}

// Controller: open/close state, debounced live preview (always RULES: no paid call per keystroke) and Enter. DOM-free.
export function createSpotlight({parsePreview, parseFinal, apply, schedule = fn => { fn(); }, onChange = () => {}}) {
  const state = {open: false, text: '', chips: [], options: [], selected: 0, manual: false, status: 'idle', parser: null, latency_ms: null, cost_usd: null, error: null};
  let seq = 0;
  const emit = () => onChange({...state, chips: [...state.chips], options: [...state.options]});
  const reset = () => { state.text = ''; state.chips = []; state.options = []; state.selected = 0; state.manual = false; state.status = 'idle'; state.parser = state.latency_ms = state.cost_usd = state.error = null; };
  const show = r => {
    const before = state.options[state.selected]?.kind;
    state.chips = r.chips ?? []; state.parser = r.parser ?? null; state.latency_ms = r.latency_ms ?? null; state.cost_usd = r.cost_usd ?? null;
    state.options = r.parse ? optionsFromParse(r.parse, state.chips) : [];
    const keep = state.options.findIndex(o => o.kind === before); state.selected = keep >= 0 && state.manual ? keep : 0;
  };
  return {
    get state() { return state; },
    open() { if (!state.open) { state.open = true; reset(); emit(); } },
    close() { seq++; state.open = false; reset(); emit(); },
    toggle() { state.open ? this.close() : this.open(); },
    // Arrow keys: move the highlighted row (wraps). A manual pick survives later previews of the same sentence.
    move(delta) { const n = state.options.length; if (!n) return; state.selected = ((state.selected + delta) % n + n) % n; state.manual = true; emit(); },
    select(index) { if (index >= 0 && index < state.options.length) { state.selected = index; state.manual = true; emit(); } },
    setText(text) {
      state.text = String(text); const mine = ++seq; state.manual = false;
      if (!state.text.trim()) { state.chips = []; state.options = []; state.selected = 0; state.status = 'idle'; emit(); return; }
      state.status = 'previewing'; emit();
      schedule(async () => {
        try { const r = await parsePreview(state.text.trim()); if (mine !== seq) return; show(r); state.status = 'previewed'; state.error = null; }
        catch (e) { if (mine !== seq) return; state.status = 'error'; state.error = e.message ?? String(e); }
        emit();
      });
    },
    // Enter: enter the highlighted row (first row when none was picked) and run it. The chosen window is fixed before the
    // final parse so a slower parser cannot change what the user picked.
    async submit() {
      const text = state.text.trim(); if (!text) return false;
      const picked = state.options[state.selected]?.kind ?? null, manual = Boolean(state.manual);
      const mine = ++seq; state.status = 'parsing'; emit();
      try {
        const r = await parseFinal(text); if (mine !== seq) return false;
        show(r); state.status = 'done'; state.error = null; emit();
        const kind = manual ? picked : optionsFromParse(r.parse, state.chips)[0]?.kind ?? picked;
        apply(r.parse, r, {kind, run: true}); this.close(); return true;
      } catch (e) { if (mine !== seq) return false; state.status = 'error'; state.error = e.message ?? String(e); emit(); return false; }
    },
  };
}

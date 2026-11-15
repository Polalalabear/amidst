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

// Plan for the existing query windows. `currentScreen` decides the window when the sentence has no action cue (nothing guessed).
export function planFromParse(parse, run, currentScreen = null) {
  const classes = new Set(run?.supported_classes?.class_labels ?? []), colors = new Set(run?.supported_classes?.color_vocabulary?.labels ?? []);
  const kind = parse.action === '追蹤' ? 'track' : parse.action === '查找' ? 'search' : currentScreen === 'case2' ? 'track' : 'search';
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
  const state = {open: false, text: '', chips: [], status: 'idle', parser: null, latency_ms: null, cost_usd: null, error: null};
  let seq = 0;
  const emit = () => onChange({...state, chips: [...state.chips]});
  const reset = () => { state.text = ''; state.chips = []; state.status = 'idle'; state.parser = state.latency_ms = state.cost_usd = state.error = null; };
  const show = r => { state.chips = r.chips; state.parser = r.parser ?? null; state.latency_ms = r.latency_ms ?? null; state.cost_usd = r.cost_usd ?? null; };
  return {
    get state() { return state; },
    open() { if (!state.open) { state.open = true; reset(); emit(); } },
    close() { seq++; state.open = false; reset(); emit(); },
    toggle() { state.open ? this.close() : this.open(); },
    setText(text) {
      state.text = String(text); const mine = ++seq;
      if (!state.text.trim()) { state.chips = []; state.status = 'idle'; emit(); return; }
      state.status = 'previewing'; emit();
      schedule(async () => {
        try { const r = await parsePreview(state.text.trim()); if (mine !== seq) return; show(r); state.status = 'previewed'; state.error = null; }
        catch (e) { if (mine !== seq) return; state.status = 'error'; state.error = e.message ?? String(e); }
        emit();
      });
    },
    async submit() {
      const text = state.text.trim(); if (!text) return false;
      const mine = ++seq; state.status = 'parsing'; emit();
      try {
        const r = await parseFinal(text); if (mine !== seq) return false;
        show(r); state.status = 'done'; state.error = null; emit();
        apply(r.parse, r); this.close(); return true;
      } catch (e) { if (mine !== seq) return false; state.status = 'error'; state.error = e.message ?? String(e); emit(); return false; }
    },
  };
}

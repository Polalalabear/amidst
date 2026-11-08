// Epic D path (b) (docs/specs/EPIC_D_AGENTIC_V1.md §3, §8): a one-sentence box above the case1/case2 query windows.
// The server (POST /api/q_nl_parse) turns the sentence into menu options; this module only PRE-FILLS the existing
// query form and shows who decided. Nothing is sent to the core query routes until the user presses
// 「確認後執行」. Any failure (error, timeout, bad shape, option not in the menus) leaves the manual menu untouched
// and says why. Presentation + a thin client only: no inference input, no GT, no key. Results are EXPLORATORY.
import {validateSearchForm, validateTrackForm, classDisplay, colorDisplay} from './ui-model.mjs';

export const NL_ROUTE = '/api/q_nl_parse';
export const NL_REQUEST_SCHEMA = 'q-core.nl-parse-request.v1';
export const NL_RESPONSE_SCHEMA = 'q-core.nl-parse-response.v1';
export const NL_DEFAULT_TIMEOUT_MS = 20000;
const PRIVATE_KEYS = new Set(['gt', 'ground_truth', 'actor', 'actor_id', 'material_id', 'script', 'event_script', 'trajectory', 'renderer_trajectory', 'visibility', 'depth', 'mask']);
const GT_READ = ['gt', '_read'].join('');
const FORM_KEYS = ['start', 'end', 'regionIds', 'classLabel', 'colorLabel'];

export const REASON_TEXT = Object.freeze({
  TIMEOUT: '模型逾時', CLIENT_TIMEOUT: '等候逾時', TIME_BUDGET: '超過時間預算', INVALID_RESPONSE: '模型輸出不合法',
  ILLEGAL_TOOL: '模型呼叫了不允許的工具', PROVIDER_UNAVAILABLE: '模型服務無法使用', DISABLED: '模型已關閉', REPLAY_MISS: '錄製檔沒有這句話',
  NETWORK_ERROR: '連不上伺服器', BAD_RESPONSE: '伺服器回應格式不符', NOT_IN_MENU: '解析結果不在目前的選單內', SOURCE_NOT_READY: '來源或 session 未就緒',
  UNSUPPORTED_CONDITION: '句子含有目前不支援的條件', INTENT_NOT_EXECUTABLE: '這句話不是查找或追蹤', CLASS_NOT_IN_CATALOG: '目錄裡沒有這個特徵',
  COLOR_NOT_IN_CATALOG: '目錄裡沒有這個顏色', COLOR_REQUIRES_PERSON: '顏色只能搭配人物', REGION_NOT_IN_CATALOG: '目錄裡沒有這個地點',
  TIME_EXPRESSION_INVALID: '時間無法解讀（12 小時制請加上午／下午）', NOTHING_PARSED: '看不出任何選項', FORBIDDEN_INFERENCE_INPUT: '句子含有不允許的內容',
  INVALID_REQUEST: '句子不符合格式（1–200 字）',
});
export const reasonText = code => REASON_TEXT[code] ?? `UNKNOWN（${code ?? '未知'}）`;
const MISSING_TEXT = Object.freeze({time: '時間', regionOrFeature: '地點或特徵', feature: '特徵'});

export function buildNlRequest({run, session, kind, text}) {
  if (!run || typeof session !== 'string' || !session) throw new Error('SOURCE_NOT_READY');
  if (!['search', 'track'].includes(kind)) throw new Error('INVALID_REQUEST');
  const t = String(text ?? '').trim();
  if (!t || t.length > 200) throw new Error('INVALID_REQUEST');
  return {schema_version: NL_REQUEST_SCHEMA, session_ref: session, scene_id: run.scene_id, run_id: run.run_id, kind, text: t};
}

const hasPrivate = v => Array.isArray(v) ? v.some(hasPrivate) : v && typeof v === 'object' && Object.entries(v).some(([k, c]) => PRIVATE_KEYS.has(k.toLowerCase()) || (k.toLowerCase().startsWith('gt_') && k !== GT_READ) || hasPrivate(c));
const known = (list, v) => list.some(x => (x?.value ?? x) === v);

// Shape + menu check. Anything that fails here is shown as a fallback to the manual menu, never applied.
export function validateNlResponse(resp, kind, catalog) {
  const bad = code => ({ok: false, code});
  if (!resp || typeof resp !== 'object' || resp.schema_version !== NL_RESPONSE_SCHEMA || resp.kind !== kind || hasPrivate(resp)) return bad('BAD_RESPONSE');
  if (resp.labels?.identity_verdict !== 'UNCONFIRMED' || resp.labels?.evidence !== 'EXPLORATORY' || resp.labels?.[GT_READ] !== false) return bad('BAD_RESPONSE');
  if (resp.executed !== false || resp.requires_confirmation !== true || !['PARSED', 'FALLBACK_MANUAL'].includes(resp.status)) return bad('BAD_RESPONSE');
  if (resp.status === 'FALLBACK_MANUAL') return resp.form === null ? {ok: true, code: null} : bad('BAD_RESPONSE');
  const f = resp.form;
  if (!f || FORM_KEYS.some(k => !(k in f)) || !Array.isArray(f.regionIds)) return bad('BAD_RESPONSE');
  if (f.classLabel && !known(catalog.classes ?? [], f.classLabel)) return bad('NOT_IN_MENU');
  if (f.colorLabel && !known(catalog.colors ?? [], f.colorLabel)) return bad('NOT_IN_MENU');
  if (f.regionIds.some(r => !known(catalog.regions ?? [], r))) return bad('NOT_IN_MENU');
  return {ok: true, code: null};
}

const latencyText = ms => Number.isFinite(ms) ? `${(ms / 1000).toFixed(1)} 秒` : '';
// View model for the result card: one decision chip (three visibly different sources), provider chips, summary, steps.
export function describeNlResponse(resp, catalog = {}) {
  const p = resp.provider ?? {};
  const providerChips = [];
  if (p.kind === 'RECORDED') providerChips.push({text: '錄製重播', cls: 'is-replay'});
  else if (p.kind === 'OLLAMA') providerChips.push({text: p.model ?? 'Ollama', cls: 'is-model'});
  else if (p.kind === 'OPENAI') providerChips.push({text: `OpenAI${p.model ? ' · ' + p.model : ''}`, cls: 'is-model'});
  else providerChips.push({text: '未使用模型', cls: 'is-none'});
  if (p.model && p.kind === 'RECORDED' && !p.synthetic_fixture) providerChips.push({text: p.model, cls: 'is-model'});
  if (p.synthetic_fixture) providerChips.push({text: 'SYNTHETIC_FIXTURE', cls: 'is-synthetic'});
  providerChips.push({text: 'EXPLORATORY', cls: 'is-label'});
  const manual = resp.status === 'FALLBACK_MANUAL';
  const reason = resp.fallback_reason ?? resp.manual_reason;
  let decision;
  if (manual) decision = {source: 'FALLBACK', text: `退回手動選單：${reasonText(resp.manual_reason ?? reason)}`, reason};
  else if (resp.decided_by === 'LLM') decision = {source: 'LLM', text: 'LLM 決定', reason: null};
  else if (resp.decided_by === 'RULE_FALLBACK') decision = {source: 'FALLBACK', text: `退回規則：${reasonText(reason)}`, reason};
  else decision = {source: 'RULE', text: '規則', reason: null};
  const f = resp.form;
  const regionLabel = id => (catalog.regions ?? []).find(r => r.value === id)?.label ?? id;
  const parts = [];
  if (f) {
    if (f.classLabel) parts.push(`特徵：${classDisplay(f.classLabel, catalog.aliases)}${f.colorLabel ? '・' + colorDisplay(f.colorLabel) : ''}`);
    if (f.regionIds.length) parts.push(`地點：${f.regionIds.map(regionLabel).join('、')}`);
    if (f.start || f.end) parts.push(`時間：${f.start || '現在'}${f.end ? ' → ' + f.end : ''}`);
    else if (resp.kind === 'track') parts.push('時間：現在');
  }
  const steps = (resp.trace?.steps ?? []).map(s => ({
    text: s.result_summary, reason: s.fallback_reason ?? null, latency: latencyText(s.llm_call?.latency_ms),
    source: s.decided_by === 'LLM' ? (s.arguments ? 'LLM' : 'FALLBACK') : s.decided_by === 'RULE_FALLBACK' ? 'FALLBACK' : 'RULE',
  }));
  return {
    state: manual ? 'MANUAL' : 'READY', decision, providerChips, summary: parts.join('　·　'),
    missing: (resp.missing ?? []).map(m => MISSING_TEXT[m] ?? m), warnings: resp.warnings ?? [], ignored: resp.ignored_terms ?? [], steps,
    recordedLatency: p.recorded && Number.isFinite(p.latency_ms) ? latencyText(p.latency_ms) : '',
  };
}

// Returns {ok:true, data} or {ok:false, code}. Never throws; a hung server becomes CLIENT_TIMEOUT.
export async function requestNlParse({fetchImpl = globalThis.fetch?.bind(globalThis), request, timeoutMs = NL_DEFAULT_TIMEOUT_MS, setTimer = setTimeout, clearTimer = clearTimeout}) {
  const ctl = typeof AbortController === 'function' ? new AbortController() : null;
  let timedOut = false, timer;
  const timeout = new Promise(resolve => { timer = setTimer(() => { timedOut = true; ctl?.abort(); resolve({ok: false, code: 'CLIENT_TIMEOUT'}); }, timeoutMs); });
  const call = (async () => {
    try {
      const res = await fetchImpl(NL_ROUTE, {method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(request), signal: ctl?.signal});
      const text = await res.text();
      if (!res.ok) { let code = 'HTTP_' + res.status; try { code = JSON.parse(text).error_code ?? code; } catch { /* keep HTTP code */ } return {ok: false, code}; }
      return {ok: true, data: JSON.parse(text)};
    } catch (error) { return {ok: false, code: timedOut ? 'CLIENT_TIMEOUT' : error instanceof SyntaxError ? 'BAD_RESPONSE' : 'NETWORK_ERROR'}; }
  })();
  const out = await Promise.race([call, timeout]);
  clearTimer(timer);
  return out;
}

const PLACEHOLDER = Object.freeze({search: '例：下午一點到一點半 101 教室的筆電', track: '例：追蹤紅衣服的人'});

// `w` is the query-window handle built by ui-shell (start/end inputs, form state, kind); `refresh` re-renders the menus;
// `submit` is the shell's own submitQuery, called only from the confirm button.
export function mountNlInput({ctx, doc, win, w, refresh, submit, fetchImpl}) {
  const el = (tag, text, cls, attrs) => { const n = doc.createElement(tag); if (text !== undefined && text !== null) n.textContent = text; if (cls) n.className = cls; if (attrs) for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  const kind = w.kind, id = kind;
  try {
    const href = new URL('./nl-input.css', import.meta.url).href;
    if (!doc.querySelector('link[data-nl-input]')) { const l = el('link', undefined, undefined, {rel: 'stylesheet', href, 'data-nl-input': ''}); doc.head.append(l); }
  } catch { /* styles are optional */ }
  const cfgMs = Number(new URL(ctx.url ?? 'http://localhost/').searchParams.get('nl_timeout_ms'));
  const timeoutMs = Number.isFinite(cfgMs) && cfgMs >= 100 && cfgMs <= 60000 ? cfgMs : (ctx.nlTimeoutMs ?? NL_DEFAULT_TIMEOUT_MS);
  const box = el('div', undefined, 'ui-card ui-nl'); box.id = `ui-nl-${id}`;
  const input = el('input', undefined, 'ui-input', {type: 'text', 'aria-label': '用一句話描述', placeholder: PLACEHOLDER[kind], maxlength: '200', autocomplete: 'off'}); input.id = `ui-nl-${id}-text`;
  const parseBtn = el('button', '解析', 'ui-btn ui-btn-light', {type: 'button'}); parseBtn.id = `ui-nl-${id}-parse`;
  const row = el('div', undefined, 'ui-nl-row'); row.append(input, parseBtn);
  const result = el('div', undefined, 'ui-nl-result'); result.id = `ui-nl-${id}-result`; result.hidden = true; result.setAttribute('role', 'status');
  box.append(el('span', '用一句話描述（會先填好下方選項，確認後才執行）', 'ui-label'), row, result);
  win.prepend(box);
  let seq = 0, last = null;

  const reset = () => { result.hidden = true; result.replaceChildren(); last = null; };
  const chip = (text, cls) => el('span', text, `ui-nl-chip ${cls}`);
  function setForm(f) {
    w.form.regions.clear(); for (const r of f.regionIds) w.form.regions.add(r);
    w.form.classLabel = f.classLabel; w.form.colorLabel = f.colorLabel;
    w.start.value = f.start; if (kind === 'search') w.end.value = f.end;
    refresh();
  }
  const currentForm = () => ({start: w.start.value, end: kind === 'search' ? w.end.value : '', regionIds: [...w.form.regions], classLabel: w.form.classLabel, colorLabel: w.form.colorLabel});
  function show(view, resp) {
    result.hidden = false; result.replaceChildren(); result.dataset.state = view.state; result.dataset.source = view.decision.source;
    const chips = el('div', undefined, 'ui-nl-chips');
    chips.append(chip(view.decision.text, `is-${view.decision.source.toLowerCase()}`), ...view.providerChips.map(c => chip(c.text, c.cls)));
    chips.firstChild.dataset.role = 'decision';
    result.append(chips);
    if (view.state === 'READY') {
      const check = (kind === 'search' ? validateSearchForm : validateTrackForm)(currentForm());
      result.append(el('p', view.summary || '（沒有可填入的選項）', 'ui-nl-summary'));
      const notes = [...view.warnings, ...(view.ignored.length ? [`未使用的詞：${view.ignored.join('、')}`] : []), ...(check.ok ? [] : [`尚缺：${view.missing.join('、') || check.text}，請在下方補上`])];
      if (notes.length) result.append(el('p', notes.join('；'), 'ui-nl-note'));
      const bar = el('div', undefined, 'ui-nl-confirm');
      const go = el('button', '確認後執行', 'ui-btn ui-btn-light', {type: 'button'}); go.id = `ui-nl-${id}-confirm`; go.disabled = !check.ok;
      const cancel = el('button', '取消', 'ui-linkbtn', {type: 'button'}); cancel.id = `ui-nl-${id}-cancel`;
      go.addEventListener('click', async () => {
        const again = (kind === 'search' ? validateSearchForm : validateTrackForm)(currentForm());
        if (!again.ok) { go.disabled = true; return; }
        go.disabled = true; result.dataset.state = 'SUBMITTED'; await submit(w);
      });
      cancel.addEventListener('click', reset);
      bar.append(go, cancel); result.append(bar, el('p', '尚未執行。按「確認後執行」才會送出查詢。', 'ui-nl-note'));
    } else {
      result.append(el('p', '選項沒有被改動，請直接使用下方手動選單。', 'ui-nl-summary'));
    }
    if (view.steps.length) {
      const d = el('details', undefined, 'ui-nl-steps'); d.append(el('summary', `解析步驟（${view.steps.length}）${view.recordedLatency ? '・錄製耗時 ' + view.recordedLatency : ''}`));
      for (const s of view.steps) { const li = el('p', undefined, 'ui-nl-step'); li.append(chip(s.source === 'LLM' ? 'LLM' : s.source === 'RULE' ? '規則' : '退回規則', `is-${s.source.toLowerCase()}`), el('span', `${s.text}${s.reason ? '（' + reasonText(s.reason) + '）' : ''}${s.latency ? ' · ' + s.latency : ''}`)); d.append(li); }
      result.append(d);
    }
  }
  function manualFallback(code, text) {
    const view = describeNlResponse({status: 'FALLBACK_MANUAL', kind, form: null, manual_reason: code, fallback_reason: code, provider: {kind: 'NONE'}, trace: {steps: []}}, {});
    view.providerChips = view.providerChips.filter(c => c.cls === 'is-label'); view.decision.text = `退回手動選單：${reasonText(code)}`;
    show(view, null); result.dataset.sentence = text ? 'kept' : '';
  }
  async function run() {
    const text = input.value.trim(); if (!text) return;
    const mine = ++seq; parseBtn.disabled = true; parseBtn.textContent = '解析中…'; result.hidden = false; result.replaceChildren(el('p', '解析中…', 'ui-nl-note')); result.dataset.state = 'PENDING';
    const state = ctx.store.getState(), run = state.activeRun, catalog = ctx.coreCatalog?.() ?? {};
    let out;
    try { out = await requestNlParse({fetchImpl: fetchImpl ?? ctx.fetchImpl ?? globalThis.fetch?.bind(globalThis), request: buildNlRequest({run, session: ctx.api?.getSession?.(), kind, text}), timeoutMs}); }
    catch (error) { out = {ok: false, code: error.message === 'SOURCE_NOT_READY' || error.message === 'INVALID_REQUEST' ? error.message : 'NETWORK_ERROR'}; }
    if (mine !== seq) return;
    parseBtn.disabled = false; parseBtn.textContent = '解析';
    if (!out.ok) { manualFallback(out.code, text); return; }
    const verdict = validateNlResponse(out.data, kind, catalog);
    if (!verdict.ok) { manualFallback(verdict.code, text); return; }
    last = out.data;
    if (out.data.status === 'PARSED') setForm(out.data.form);
    show(describeNlResponse(out.data, catalog), out.data);
  }
  parseBtn.addEventListener('click', run);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') run(); });
  return {box, input, parse: run, reset, last: () => last, destroy() { seq++; box.remove(); }};
}

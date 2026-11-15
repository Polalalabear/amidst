// N1 Spotlight bar (macOS-Spotlight style): ⌘K / Ctrl+K or the magnifier opens it, Esc closes, Enter fills the existing tag panel.
// DOM only; behaviour lives in nl-spotlight-model.mjs. The key never reaches the browser: parsing is a server call (api.nlParse).
import {PARSER_MODES, chipsFromParse, createSpotlight} from './nl-spotlight-model.mjs';

const MODE_NAME = Object.fromEntries(PARSER_MODES);
const ERRORS = Object.freeze({NO_RUN: '尚無來源，無法解析', NL_PARSE_REQUEST: '句子或來源不正確', NL_PARSE_SCHEMA: '伺服器回應格式不符', FORBIDDEN_INFERENCE_INPUT: '句子不合規則（1–200 字）'});
export const PLACEHOLDER = '例如：追蹤紅衣的人 從西入口 0:10 到 0:30';

export function mountSpotlight({host, store, api, getMode = () => 'RULES', apply, win = globalThis, debounceMs = 220}) {
  const doc = host.ownerDocument;
  const el = (tag, text, cls, attrs) => { const n = doc.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; for (const [k, v] of Object.entries(attrs ?? {})) n.setAttribute(k, v); return n; };
  const overlay = el('div', undefined, 'nl-spot', {'data-open': 'false', 'aria-hidden': 'true'}); overlay.id = 'nl-spot'; overlay.inert = true;
  const backdrop = el('div', undefined, 'nl-spot-backdrop');
  const panel = el('div', undefined, 'nl-spot-panel', {role: 'dialog', 'aria-modal': 'true', 'aria-label': '自然語言查詢'});
  const row = el('div', undefined, 'nl-spot-row');
  const input = el('input', undefined, 'nl-spot-input', {type: 'text', placeholder: PLACEHOLDER, autocomplete: 'off', spellcheck: 'false', maxlength: '200', 'aria-label': '用一句話描述要查找或追蹤的目標'}); input.id = 'nl-spot-input';
  row.append(el('span', '⌕', 'nl-spot-icon', {'aria-hidden': 'true'}), input);
  const chipsBox = el('div', undefined, 'nl-spot-chips', {'aria-live': 'polite'}); chipsBox.id = 'nl-spot-chips';
  const status = el('p', undefined, 'nl-spot-status', {role: 'status'}); status.id = 'nl-spot-status';
  const foot = el('div', undefined, 'nl-spot-foot'); const hint = el('span'), meta = el('span', undefined, 'nl-spot-meta'); meta.id = 'nl-spot-meta'; foot.append(hint, meta);
  panel.append(row, chipsBox, status, foot); overlay.append(backdrop, panel); host.append(overlay);

  let timer = null;
  const run = () => store.getState().activeRun;
  const call = mode => async text => {
    const r = run(); if (!r) throw new Error('NO_RUN');
    const res = await api.nlParse(r, text, mode); if (!res.ok) throw new Error(res.error?.code ?? 'PARSE_FAILED');
    return {parse: res.data, chips: chipsFromParse(res.data, r), parser: res.data.parser, latency_ms: res.data.latency_ms, cost_usd: res.data.cost_usd};
  };
  const controller = createSpotlight({
    parsePreview: call('RULES'),                         // live chips never spend an API call
    parseFinal: text => call(getMode())(text),
    apply,
    schedule: fn => { win.clearTimeout(timer); timer = win.setTimeout(fn, debounceMs); },
    onChange: render,
  });

  function render(s) {
    overlay.dataset.open = String(s.open); overlay.setAttribute('aria-hidden', String(!s.open)); overlay.inert = !s.open;
    if (!s.open) return;
    if (input.value !== s.text) input.value = s.text;
    chipsBox.replaceChildren(...s.chips.map(c => el('span', c.text, `nl-chip nl-chip-${c.kind}`, {'data-kind': c.kind})));
    const empty = s.text.trim() && !s.chips.length && (s.status === 'previewed' || s.status === 'done');
    status.textContent = s.status === 'previewing' ? '解析中…' : s.status === 'parsing' ? `解析中（${MODE_NAME[getMode()]}）…` : s.status === 'error' ? `解析失敗：${ERRORS[s.error] ?? s.error}` : empty ? '沒有辨識出任何條件' : '';
    status.dataset.state = s.status;
    hint.textContent = `Enter 填入查詢條件　Esc 關閉　解析方式：${MODE_NAME[getMode()]}`;
    meta.textContent = s.parser ? `${MODE_NAME[s.parser]} · ${s.latency_ms == null ? '—' : s.latency_ms.toFixed(1) + ' ms'} · ${s.cost_usd == null ? '費用 UNKNOWN' : '$' + s.cost_usd}` : '';
  }
  input.addEventListener('input', () => controller.setText(input.value));
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); controller.submit(); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); controller.close(); }
  });
  backdrop.addEventListener('click', () => controller.close());
  const toggle = () => { controller.toggle(); if (controller.state.open) win.requestAnimationFrame?.(() => input.focus()); };
  const onKey = e => { if ((e.metaKey || e.ctrlKey) && !e.altKey && String(e.key).toLowerCase() === 'k') { e.preventDefault(); toggle(); } };
  doc.addEventListener('keydown', onKey);
  return {controller, toggle, open: () => { if (!controller.state.open) toggle(); }, close: () => controller.close(),
    destroy() { win.clearTimeout(timer); doc.removeEventListener('keydown', onKey); overlay.remove(); }};
}

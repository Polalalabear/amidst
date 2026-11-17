// Entry to live mode (the separate live server, default 127.0.0.1:8791) from the admin header (2026-11-17).
// The admin badge 「LIVE · AVAILABLE」 is the data source of this page (bootstrap data_origin · status), not live mode;
// this module gives live mode its own, explicit buttons. Pure helpers + a small DOM mount.
//
// Base URL: ?live=<url> on the admin page, else localStorage `amidst.liveBase`, else the default. http(s) only.

export const LIVE_DEFAULT_BASE = 'http://127.0.0.1:8791';
export const LIVE_BASE_KEY = 'amidst.liveBase';

export function normalizeLiveBase(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const u = new URL(value.trim());
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    return u.origin;
  } catch { return null; }
}

export function resolveLiveBase({pageUrl = null, storage = null} = {}) {
  let fromQuery = null; try { fromQuery = pageUrl ? new URL(pageUrl).searchParams.get('live') : null; } catch {}
  let fromStore = null; try { fromStore = storage?.getItem?.(LIVE_BASE_KEY) ?? null; } catch {}
  return normalizeLiveBase(fromQuery) ?? normalizeLiveBase(fromStore) ?? LIVE_DEFAULT_BASE;
}

export function liveUrls(base) {
  const b = normalizeLiveBase(base) ?? LIVE_DEFAULT_BASE;
  return {base: b, operator: `${b}/?role=operator`, system: `${b}/?role=system`};
}

// Reachability only (cross-origin, so no body is read): an opaque answer means the server is up. Never sends data.
export async function probeLive(base, {fetchImpl = globalThis.fetch, timeoutMs = 2500, win = globalThis} = {}) {
  if (typeof fetchImpl !== 'function') return {available: false, reason: 'NO_FETCH'};
  let timer;
  try {
    await Promise.race([
      fetchImpl(`${liveUrls(base).base}/config`, {mode: 'no-cors', cache: 'no-store', credentials: 'omit'}),
      new Promise((_, rej) => { timer = win.setTimeout(() => rej(new Error('TIMEOUT')), timeoutMs); }),
    ]);
    return {available: true, reason: null};
  } catch (e) { return {available: false, reason: e?.message === 'TIMEOUT' ? 'TIMEOUT' : 'UNREACHABLE'}; }
  finally { win.clearTimeout(timer); }
}

export function liveEntryView(state) {
  if (state.checking) return {disabled: true, text: '檢查即時模式…', tone: 'wait'};
  if (state.available) return {disabled: false, text: `即時模式可用 · ${state.base.replace(/^https?:\/\//, '')}`, tone: 'ok'};
  return {disabled: true, text: `即時模式未啟動（${state.base.replace(/^https?:\/\//, '')} 連不上）`, tone: 'off'};
}

export function mountLiveEntry(host, {pageUrl = globalThis.location?.href ?? null, storage = globalThis.localStorage, fetchImpl = globalThis.fetch, open = (url) => globalThis.open?.(url, '_blank', 'noopener')} = {}) {
  const doc = host.ownerDocument;
  const el = (tag, text, cls, attrs) => { const n = doc.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; for (const [k, v] of Object.entries(attrs ?? {})) n.setAttribute(k, v); return n; };
  const base = resolveLiveBase({pageUrl, storage}), urls = liveUrls(base);
  const box = el('div', undefined, 'live-entry'); box.id = 'live-entry';
  const op = el('button', '開啟即時模式', 'live-entry-btn primary', {type: 'button', title: `新分頁開啟 ${urls.operator}`}); op.id = 'live-open-operator';
  const sys = el('button', '系統頁', 'live-entry-btn', {type: 'button', title: `新分頁開啟 ${urls.system}`}); sys.id = 'live-open-system';
  const status = el('span', '', 'live-entry-status', {role: 'status'}); status.id = 'live-entry-status';
  const retry = el('button', '重新檢查', 'live-entry-retry', {type: 'button'});
  box.append(op, sys, status, retry); host.append(box);
  const state = {base: urls.base, checking: true, available: false};
  const render = () => {
    const v = liveEntryView(state);
    op.disabled = sys.disabled = v.disabled; status.textContent = v.text; status.dataset.tone = v.tone; retry.hidden = state.checking || state.available;
    box.dataset.available = String(state.available);
  };
  const check = async () => { state.checking = true; render(); const r = await probeLive(state.base, {fetchImpl}); state.checking = false; state.available = r.available; render(); };
  op.addEventListener('click', () => { if (state.available) open(urls.operator); });
  sys.addEventListener('click', () => { if (state.available) open(urls.system); });
  retry.addEventListener('click', check);
  render(); const ready = check();
  return {ready, check, urls, get state() { return {...state}; }, destroy() { box.remove(); }};
}

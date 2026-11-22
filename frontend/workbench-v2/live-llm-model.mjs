// 工作台 v2 後台設定的「即時模式 LLM 決策」開關（D265、D267）。由瀏覽器直接讀寫 live 伺服器的 /config（只讀寫 advisor、advisor_model）。8785 後端的稽核掛鉤禁止任何 socket.connect，所以不能在後端做代理；live 伺服器只對指定的本機來源開 CORS。
// 純函式加兩個 fetch 包裝，沒有 DOM 依賴（畫面在 admin-ui.mjs），方便用 node 測。
// 預設關閉；連不上 live 伺服器時一律顯示「不可用」和原因，開關不會看起來是開的。
export const MODE_LABEL = { review: 'LLM 覆核', lead: 'LLM 主導', agent: 'Agent 決策' };   // agent：F3 #657 agent_service

// resp：reduceConfig 的結果，或 null（還沒讀到）。
export function liveLlmView(resp) {
  if (!resp) return { checked: false, disabled: true, mode: 'review', tone: 'wait', text: 'LLM 決策：讀取中', detail: '', models: [], model: null };
  const sw = resp.llm_switch || {};
  const models = Array.isArray(sw.models) ? sw.models : [];
  const base = { mode: 'review', models, model: sw.model || null };
  if (resp.reachable !== true) {   // live 伺服器沒啟動／連不上／版本不支援：不可用，不能看起來是開的
    return { ...base, checked: false, disabled: true, tone: 'fallback', text: 'LLM 決策：不可用', detail: sw.reason_text || 'live 伺服器連不上' };
  }
  const effective = resp.advisor || sw.effective || 'off', requested = sw.requested || effective;
  if (requested !== 'off' && effective === 'off') {
    return { ...base, checked: true, disabled: false, mode: requested, tone: 'fallback', text: 'LLM 決策：開啟（不可用，使用規則）', detail: sw.reason_text || '原因未知' };
  }
  if (effective === 'off') return { ...base, checked: false, disabled: false, tone: 'rule', text: 'LLM 決策：關閉', detail: '使用規則追蹤' };
  const fake = sw.provider === 'fake';
  return { ...base, checked: true, disabled: false, mode: effective, tone: 'llm', text: `LLM 決策：開啟（${MODE_LABEL[effective] || effective}）`,
    detail: fake ? '假模型（測試，不連網、不花錢）' : `模型 ${sw.model || '未知'}；後台仍受花費護欄限制` };
}

export function liveLlmRequest(checked, mode, model) {
  const body = { advisor: checked && Object.hasOwn(MODE_LABEL, mode) ? mode : 'off' };
  if (model) body.advisor_model = model;
  return body;
}

export const DEFAULT_LIVE_PORT = 8791;
const PINNED_DEMO_PORT = 8785;

// live 伺服器位址：預設 http://127.0.0.1:8791；頁面網址的 ?live_port=<埠> 可改，只接受 1024–65535，且不是 8785 和本頁自己的埠。
export function liveBase(search = '', ownPort = '') {
  const raw = new URLSearchParams(search).get('live_port');
  const port = raw == null ? DEFAULT_LIVE_PORT : Number(raw);
  if (!Number.isInteger(port) || port < 1024 || port > 65535 || port === PINNED_DEMO_PORT || String(port) === String(ownPort)) return null;
  return { origin: `http://127.0.0.1:${port}`, host: `127.0.0.1:${port}` };
}

const unreachable = (host, why) => ({ reachable: false, advisor: 'off', llm_switch: { requested: 'off', effective: 'off', available: false, reason: why,
  reason_text: why === 'LIVE_NO_SWITCH' ? `live 伺服器（${host}）版本不支援 LLM 決策開關`
    : why === 'LIVE_URL_NOT_ALLOWED' ? 'live 位址不被允許（只接受本機 1024–65535 的埠，不含 8785）' : `live 伺服器沒有啟動或連不上（${host}）` } });

// live /config 的回應縮成狀態欄位（沒有裝置、執行緒等其他欄位）。
export function reduceConfig(cfg, host) {
  const sw = cfg && cfg.llm_switch;
  if (!sw || typeof sw !== 'object') return unreachable(host, 'LIVE_NO_SWITCH');
  const keys = ['requested', 'effective', 'available', 'reason', 'reason_text', 'provider', 'model', 'models'];
  return { reachable: true, advisor: cfg.advisor, advisor_provider: cfg.advisor_provider, llm_switch: Object.fromEntries(keys.filter((k) => k in sw).map((k) => [k, sw[k]])) };
}

const where = () => { try { return liveBase(globalThis.location?.search ?? '', globalThis.location?.port ?? ''); } catch { return null; } };

export async function loadLiveLlm(fetchFn = globalThis.fetch, base = where()) {
  if (!base) return unreachable('?', 'LIVE_URL_NOT_ALLOWED');
  try {
    const r = await fetchFn(`${base.origin}/config`, { cache: 'no-store' });
    if (!r.ok) throw new Error(String(r.status));
    return reduceConfig(await r.json(), base.host);
  } catch { return unreachable(base.host, 'LIVE_UNREACHABLE'); }
}

export async function saveLiveLlm(body, fetchFn = globalThis.fetch, base = where()) {
  if (!base) return unreachable('?', 'LIVE_URL_NOT_ALLOWED');
  const safe = { advisor: ['off', 'review', 'lead'].includes(body && body.advisor) ? body.advisor : 'off' };   // nothing else is ever sent
  if (body && typeof body.advisor_model === 'string' && body.advisor_model.length <= 20) safe.advisor_model = body.advisor_model;
  try {
    const r = await fetchFn(`${base.origin}/config`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(safe) });
    if (!r.ok) throw new Error(String(r.status));
    return await loadLiveLlm(fetchFn, base);
  } catch { return unreachable(base.host, 'LIVE_UNREACHABLE'); }
}

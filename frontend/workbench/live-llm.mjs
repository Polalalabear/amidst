// 工作台的「即時模式 LLM 決策」開關（D265）。只和工作台自己的後端 /api/live_llm 說話（同源代理，轉到 live 伺服器的 /config）。
// 純函式加兩個 fetch 包裝，沒有 DOM 依賴，方便用 node 測。
// 預設關閉；連不上 live 伺服器時一律顯示「不可用」和原因，開關不會看起來是開的。
export const MODE_LABEL = { review: 'LLM 覆核', lead: 'LLM 主導' };
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

// resp：/api/live_llm 的回應，或 null（還沒讀到）。
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
  const body = { advisor: checked && (mode === 'review' || mode === 'lead') ? mode : 'off' };
  if (model) body.advisor_model = model;
  return body;
}

export function liveLlmHTML(view) {
  const opt = (v, l, sel) => `<option value="${esc(v)}" ${sel ? 'selected' : ''}>${esc(l)}</option>`;
  const models = view.models.map((m) => opt(m, m, m === view.model)).join('');
  return `<div class="live-llm" data-live-llm-root title="即時模式（live 伺服器）的 LLM 決策；預設關閉">
    <label><input type="checkbox" data-live-llm="on" ${view.checked ? 'checked' : ''} ${view.disabled ? 'disabled' : ''}> 即時 LLM</label>
    <select data-live-llm="mode" aria-label="LLM 決策模式" ${view.disabled ? 'disabled' : ''}>${opt('review', 'LLM 覆核', view.mode === 'review')}${opt('lead', 'LLM 主導', view.mode === 'lead')}</select>
    <select data-live-llm="model" aria-label="LLM 模型" ${view.disabled || !models ? 'disabled' : ''}>${models}</select>
    <span class="live-llm-status tone-${esc(view.tone)}" role="status" data-live-llm-status><strong>${esc(view.text)}</strong>${view.detail ? ` · ${esc(view.detail)}` : ''}</span></div>`;
}

export async function loadLiveLlm(fetchFn = fetch) {
  try {
    const r = await fetchFn('/api/live_llm');
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch { return { reachable: false, llm_switch: { reason_text: '工作台後端的代理沒有回應' } }; }
}

export async function saveLiveLlm(body, fetchFn = fetch) {
  try {
    const r = await fetchFn('/api/live_llm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch { return { reachable: false, llm_switch: { reason_text: '工作台後端的代理沒有回應' } }; }
}

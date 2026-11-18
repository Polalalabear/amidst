// 工作台「LLM 決策」開關：純函式（沒有 DOM），方便用 node 測。
// 開關只送 {advisor, advisor_model} 到後台的 /config；後台決定實際模式（src/amidst/live_mode/llm_switch.py）。
// 前端不存「已開啟」：重新整理後讀 /config，後台預設 off、重啟後回到 off，所以只有使用者明確打開才會是開。
// cfg 是 GET /config：{advisor: 實際模式, advisor_provider, llm_switch: {requested, effective, available, reason_text, provider, model, models}}

export const MODE_LABEL = { review: 'LLM 覆核', lead: 'LLM 主導' };

export function switchView(cfg = {}) {
  const sw = cfg.llm_switch || {};
  const effective = cfg.advisor || sw.effective || 'off';
  const requested = sw.requested || effective;
  const fake = (sw.provider || cfg.advisor_provider) === 'fake';
  if (requested !== 'off' && effective === 'off') {   // 想開但不能開：退回規則，顯示原因
    return { checked: true, mode: requested, tone: 'fallback', text: 'LLM 決策：開啟（不可用，使用規則）',
      detail: sw.reason_text || '原因未知', fake };
  }
  if (effective === 'off') return { checked: false, mode: 'review', tone: 'rule', text: 'LLM 決策：關閉', detail: '使用規則追蹤', fake };
  return { checked: true, mode: effective, tone: 'llm', text: `LLM 決策：開啟（${MODE_LABEL[effective] || effective}）`,
    detail: fake ? '假模型（測試，不連網、不花錢）' : `模型 ${sw.model || cfg.advisor_model || '未知'}；後台仍受花費護欄限制`, fake };
}

export function buildRequest(checked, mode, model) {
  const body = { advisor: checked && (mode === 'review' || mode === 'lead') ? mode : 'off' };
  if (model) body.advisor_model = model;
  return body;
}

// HUD 的「模式・模型」格在後台 off 時的說明：想開卻不可用時要說出原因，不能只寫「後台沒有開 advisor」。
export function hudModeNote(cfg = {}) {
  const v = switchView(cfg);
  return v.tone === 'fallback' ? `LLM 不可用：${v.detail}` : null;
}

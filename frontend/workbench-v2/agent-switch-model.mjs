// #620 / CL-B16: how the 追蹤方式 (RULE_ONLY | AGENT_SEQUENTIAL) control reads the run. Pure; no DOM, no network.
// The server says whether the Agent can run (`agent_available`, `agent_unavailable_reason`); this only words it.
export const AGENT_REASON = {
  GATEWAY_OFFLINE: 'OpenAI gateway 沒有在執行', GUARD_NOT_APPROVED: '後台沒有核准付費呼叫', NO_API_KEY: 'gateway 沒有 API key',
  MODEL_NOT_ENABLED: 'gateway 沒有啟用此模型', NOT_APPLICABLE_NO_DECIDER: '此事件沒有 Agent 決策點',
};

export function agentSwitchView(run, mode = 'RULE_ONLY') {
  const available = Boolean(run?.agent_available), why = run?.agent_unavailable_reason ?? null;
  const notApplicable = typeof why === 'string' && why.startsWith('NOT_APPLICABLE');
  const reason = why ? (AGENT_REASON[why] ?? why) : null;
  const effective = available && mode === 'AGENT_SEQUENTIAL' ? 'AGENT_SEQUENTIAL' : 'RULE_ONLY';
  let note;
  if (available) note = effective === 'AGENT_SEQUENTIAL' ? '換鏡由 Agent 決定（需 gateway 回應）' : '換鏡由規則決定（預設）';
  else if (!run) note = '尚未載入來源';
  else note = `Agent ${notApplicable ? '不適用' : '不可用'}${reason ? `：${reason}` : ''}；目前使用規則`;
  return {effective, agentEnabled: available, agentLabel: available ? 'Agent' : `Agent（${notApplicable ? '不適用' : '不可用'}）`, note, tone: available ? 'ok' : 'muted'};
}

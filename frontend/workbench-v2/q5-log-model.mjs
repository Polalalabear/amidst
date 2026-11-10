export function logModel(decisions,{review=false}={}) {
  if(!review)return [];
  return decisions.map(d=>{if(d.schema_version!=='q-demo.decision-record.v1'||!Number.isSafeInteger(d.source_time_us)||!Array.isArray(d.tool_calls)||!Array.isArray(d.llm_calls)||!Array.isArray(d.candidates_considered))throw new Error('DECISION_INVALID');if(d.decided_by==='RULE_FALLBACK'&&!d.fallback_reason)throw new Error('FALLBACK_REASON_REQUIRED');return {
    id:d.decision_id,step:d.step_index,source_time_us:d.source_time_us,transition:`${d.state_before??'START'} → ${d.state_after}`,
    badge:d.decided_by==='RULE_FALLBACK'?`ⓡ 規則兜底 · ${d.fallback_reason}`:d.decided_by==='RULE_ONLY'?'ⓡ 規則':d.decided_by==='USER'?'U 使用者':'AG Agent',
    accepted:d.accepted,rejection_code:d.rejection_code,submitted:d.submitted,executed_action:d.executed_action,
    candidates:d.candidates_considered,tools:d.tool_calls,llm_calls:d.llm_calls,rounds_used:d.rounds_used,session_agent_rounds_used:d.session_agent_rounds_used,
    budget_used_ms:d.budget_used_ms,rationale:d.submitted?.rationale??null,raw:d};
  });
}

// Normal-mode decision log (D113): one plain line per journal step up to the current source time. No candidates, tool calls,
// model output or rationale; the full record stays review-only (q5-log-model). Pure; input is the recorded response and its journal only.
import {segmentAt} from './q2-session-model.mjs';
const badgeOf=d=>d.decided_by==='RULE_FALLBACK'?`ⓡ 規則兜底 · ${d.fallback_reason}`:d.decided_by==='RULE_ONLY'?'ⓡ 規則':d.decided_by==='USER'?'U 使用者':'AG Agent';
export function stepRows(decisions,response,tUs) {
  return decisions.filter(d=>Number.isSafeInteger(d.source_time_us)&&d.source_time_us<=tUs).sort((a,b)=>a.source_time_us-b.source_time_us||a.step_index-b.step_index).map(d=>{
    if(d.decided_by==='RULE_FALLBACK'&&!d.fallback_reason)throw new Error('FALLBACK_REASON_REQUIRED');
    const transition=`${d.state_before??'START'} → ${d.state_after}`,parts=[transition];
    if(!d.accepted)parts.push(`拒絕 ${d.rejection_code}`);
    if(d.accepted&&d.executed_action){
      const presence=d.candidates_considered?.find(c=>c.candidate_ref===d.executed_candidate_ref)?.target_presence??d.candidates_considered?.find(c=>c.action===d.executed_action)?.target_presence;
      parts.push(`${d.executed_action}${presence?` · ${presence}`:''}`);
    }
    if(d.accepted&&d.state_before==='SWITCHING'&&d.state_after==='PLAYING'){const shown=segmentAt(response,d.source_time_us);if(shown?.kind==='ON_CAMERA')parts.push(`畫面換成 ${shown.camera_id}`);}
    return {id:d.decision_id,step:d.step_index,source_time_us:d.source_time_us,transition,text:parts.join(' · '),badge:badgeOf(d),accepted:d.accepted};
  });
}

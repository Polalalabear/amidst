export function provenanceModel(response,{review=false}={}) {
  if(!response)return {label:'尚未取得回應',details:null};
  return {label:'來源綁定 · 身分未確認 · 物理通行 UNKNOWN',details:review?{
    output_sha256:response.output_sha256,query_sha256:response.query_sha256??null,session_id:response.session_id??null,
    resolved_scope:response.resolved_scope,provenance:response.provenance,
    agent_attempted:response.agent_attempted,agent_used:response.agent_used,fallback_used:response.fallback_used,
    fallback_reason:response.fallback_reason,decision_source:response.decision_source}:null};
}
export function renderProvenance(container,response,options={}) {
  const m=provenanceModel(response,options);container.replaceChildren();const line=document.createElement('span');line.textContent=m.label;container.append(line);
  if(m.details){const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='來源與 hash';pre.textContent=JSON.stringify(m.details,null,2);details.append(summary,pre);container.append(details);}
}

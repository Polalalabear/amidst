// Blind-interval hypothesis layer: pure view model for `workbench.blind-hypothesis.v1`
// (docs/contracts/OFFICE_BLIND_HYPOTHESIS_V1.md, draft PR #10, not yet approved).
// Everything here is INFERRED_HYPOTHESIS display. A blind interval never gets a target position:
// only a bundle of candidate paths and a per-time reachable region. UNKNOWN draws nothing.
export const BLIND_HYPOTHESIS_SCHEMA='workbench.blind-hypothesis.v1';
// Fifth colour of the visual language (observed teal, inferred amber, missing grey, hypothesis rose).
export const HYPOTHESIS_COLOR='#ff6fa8';
export const LEGEND_ITEMS=Object.freeze([
  {key:'observed',label:'觀測',color:'#76d9cf',style:'solid'},
  {key:'inferred',label:'推論',color:'#ffc266',style:'solid'},
  {key:'missing',label:'缺失',color:'#8292a9',style:'dashed'},
  {key:'hypothesis',label:'假設',color:HYPOTHESIS_COLOR,style:'translucent'},
  {key:'region',label:'範圍',color:HYPOTHESIS_COLOR,style:'band'}]);
export const UNCONFIRMED_LABEL='穿過未確認區';
const REASON_TEXT=Object.freeze({
  ENDPOINT_UNUSABLE:'端點不可用，無法推估盲區',
  ENDPOINT_SUBSTITUTION_INVALID:'端點替代紀錄不符規則',
  INTERVAL_INVALID:'盲區時間區間無效',
  INTERVAL_TOO_LONG:'盲區過長，超過設定上限',
  WALKABLE_ANNOTATION_UNAVAILABLE:'缺少可行走區域地圖',
  SPEED_CONFIG_UNAVAILABLE:'缺少設定的速度範圍',
  ENDPOINT_OUTSIDE_WALKABLE:'端點落在可行走區域外',
  ENDPOINTS_UNREACHABLE:'依速度上限，兩端點無法連通',
  REACHABLE_SET_EMPTY:'負面證據排除了所有可能位置',
  NEGATIVE_EVIDENCE_INVALID:'負面證據不符規格',
  NEGATIVE_EVIDENCE_NOT_APPEND_ONLY:'負面證據不是只增不減',
  NO_HYPOTHESIS_PASSED_CHECKS:'沒有路徑通過全部檢查',
  PRUNING_RERUN_NOT_IMPLEMENTED:'尚未支援以新證據重算',
  SEARCH_BUDGET_EXHAUSTED:'搜尋超過上限，未完成',
  PROVENANCE_MISMATCH:'來源雜湊與場景不符',
  // Front-end only: the payload does not satisfy the contract, so nothing is drawn.
  INVALID_RESPONSE:'回應格式不符契約，不顯示'});
// FAIL_CLOSED.problem of ENDPOINT_SUBSTITUTION_INVALID (K1): why the caller's substitution record was refused.
const PROBLEM_TEXT=Object.freeze({SHAPE:'替代紀錄格式不符',RULE:'替代規則名稱不符',ORIGINAL_NOT_UNKNOWN:'原端點並非 UNKNOWN，不可替代',
  SUBSTITUTE_NOT_THE_ENDPOINT:'替代點與端點資料不一致',TIME_OFFSET_INCONSISTENT:'時間差與兩個時間不一致',NOT_OUTWARD:'替代點必須在區間外側',
  MAX_OFFSET_INCONSISTENT:'偏移上限數值不一致',OFFSET_TOO_LARGE:'偏移超過上限'});
const ORIGINAL_REASON_TEXT=Object.freeze({HEAD_ANCHOR_UNRELIABLE:'頭部錨點不可靠',AMBIGUOUS_MERGE:'合併歧義'});
const ENDPOINT_TEXT=Object.freeze({START:'起點',END:'終點'});
const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list=value=>Array.isArray(value)?value:[];
const finite=Number.isFinite;
const point3=p=>Array.isArray(p)&&p.length===3&&p.every(finite);
const point2=p=>Array.isArray(p)&&p.length>=2&&finite(p[0])&&finite(p[1]);
const round=value=>Math.round(value*1e6)/1e6;
const sec=value=>finite(value)?value.toFixed(1)+' s':'時間未知';
const signed=value=>finite(value)?(value>0?'+':value<0?'−':'')+Math.abs(value).toFixed(1)+' s':'時間差未知';

export const blindReasonText=reason=>REASON_TEXT[reason]??(reason?`未列入說明的原因 ${reason}`:'原因未提供');

// The hypothesis field of a larger response. BH-Q1 is OPEN: a standalone response (new endpoint), or an
// additive `blind_hypotheses` field on the target response. No other location is read. Absent → null → no layer.
export function blindHypothesisFromResponse(payload) {
  if(!payload||typeof payload!=='object')return null;
  if(payload.schema_version===BLIND_HYPOTHESIS_SCHEMA)return payload;
  const nested=payload.blind_hypotheses;
  return nested&&typeof nested==='object'&&nested.schema_version===BLIND_HYPOTHESIS_SCHEMA?nested:null;
}

function unknownPlan(reason,interval=null,extra={}) {
  const problem=extra.problem??null;
  return {schema:BLIND_HYPOTHESIS_SCHEMA,status:'UNKNOWN',reason,reasonText:blindReasonText(reason)+(problem?`（${PROBLEM_TEXT[problem]??problem}）`:''),problem,interval,
    paths:[],regions:[],substitutions:[],notices:[],timeStep:null,key:JSON.stringify(['UNKNOWN',reason,interval,extra.hash??null]),...extra};
}
function substitutionNotice(item) {
  const endpoint=ENDPOINT_TEXT[item?.endpoint]??'端點';
  const original=item?.original_reason?(ORIGINAL_REASON_TEXT[item.original_reason]??item.original_reason):'原因未提供';
  return {endpoint:item?.endpoint??null,original_observation_ref:item?.original_observation_ref??null,original_timestamp_s:item?.original_timestamp_s??null,
    original_reason:item?.original_reason??null,substitute_observation_ref:item?.substitute_observation_ref??null,
    substitute_timestamp_s:item?.substitute_timestamp_s??null,time_offset_s:item?.time_offset_s??null,
    // The original observation stays visible as an observed point with UNKNOWN ground; it is not the start of the hypothesis.
    text:`${endpoint}已替代：原 ${item?.original_observation_ref??'UNKNOWN'} · ${sec(item?.original_timestamp_s)}（地面位置 UNKNOWN：${original}）→ 改用 ${item?.substitute_observation_ref??'UNKNOWN'} · ${sec(item?.substitute_timestamp_s)}，時間差 ${signed(item?.time_offset_s)}`};
}
// Opacity falls with plausibility rank; it is an ordering cue only, never a probability.
const rankOpacity=index=>Math.max(.22,.85-.2*index);

// Contract response -> display model. Fail-closed: a malformed READY response draws nothing.
export function blindHypothesisPlan(response) {
  const source=blindHypothesisFromResponse(response);
  if(!source)return null;
  const interval=finite(source.interval?.start_s)&&finite(source.interval?.end_s)&&source.interval.end_s>source.interval.start_s?
    {start_s:source.interval.start_s,end_s:source.interval.end_s,duration_s:source.interval.end_s-source.interval.start_s}:null;
  const hash=source.output_sha256??null;
  if(source.status==='UNKNOWN') {
    const problem=list(source.trace).find(step=>step?.step==='FAIL_CLOSED')?.problem;
    return unknownPlan(typeof source.reason==='string'&&source.reason?source.reason:'INVALID_RESPONSE',interval,{hash,problem:typeof problem==='string'?problem:null});
  }
  if(source.status!=='READY'||!interval||source.evidence_state!=='INFERRED_HYPOTHESIS'||source.ranking_basis!=='CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY')
    return unknownPlan('INVALID_RESPONSE',interval,{hash});
  const hypotheses=list(source.hypotheses).filter(item=>item?.status==='ACTIVE').sort((a,b)=>a.rank-b.rank);
  const paths=[];
  for(const [index,item] of hypotheses.entries()) {
    const samples=list(item.samples);
    if(!samples.length||!samples.every(s=>finite(s?.timestamp_s)&&point3(s.position_m)&&s.evidence_state==='INFERRED_HYPOTHESIS'))return unknownPlan('INVALID_RESPONSE',interval,{hash});
    const walkable=item.checks?.walkable;
    // An ACTIVE path is never FAIL; a missing check (older format) is UNKNOWN, never promoted to PASS.
    const walkableResult=walkable?.result??'UNKNOWN';
    if(!['PASS','UNKNOWN'].includes(walkableResult))return unknownPlan('INVALID_RESPONSE',interval,{hash});
    const unconfirmed=Boolean(walkable)&&(walkable.unconfirmed_area_crossed===true||walkable.result==='UNKNOWN');
    const samplePoints=samples.map(s=>s.position_m.map(round));
    // Polyline: K1 guarantees route_m ends lie in the endpoint regions; they join the first/last sample so the
    // per-link D11 segments (len(samples)+1) line up. Without route_m (older format) only the samples are drawn.
    const route=list(item.route_m),first=route[0],last=route.at(-1);
    const withEnds=samples.length>=1&&point2(first)&&point2(last);
    const times=[...(withEnds?[interval.start_s]:[]),...samples.map(s=>s.timestamp_s),...(withEnds?[interval.end_s]:[])];
    const points=[...(withEnds?[[round(first[0]),round(first[1]),samplePoints[0][2]]]:[]),...samplePoints,...(withEnds?[[round(last[0]),round(last[1]),samplePoints.at(-1)[2]]]:[])];
    const unknownFrom=new Set(list(walkable?.segments).filter(s=>s?.walkable==='UNKNOWN'&&finite(s.from_timestamp_s)).map(s=>round(s.from_timestamp_s)));
    const haveSegments=list(walkable?.segments).length>0;
    // Link-level D11 marks. No segments (older format) but result UNKNOWN: the whole path is treated as unconfirmed.
    const links=points.slice(1).map((to,i)=>({from_timestamp_s:times[i],to_timestamp_s:times[i+1],a:points[i],b:to,
      unconfirmed:haveSegments?unknownFrom.has(round(times[i])):unconfirmed}));
    paths.push({ref:item.hypothesis_ref,rank:item.rank,label:`假設 ${item.rank}`,opacity:rankOpacity(index),unconfirmed:unconfirmed||links.some(l=>l.unconfirmed),
      walkable:walkableResult,unconfirmedLabel:null,links,
      samples:samples.map(s=>({timestamp_s:s.timestamp_s,position:s.position_m.map(round)})),points,withEnds});
    const path=paths.at(-1);path.unconfirmedLabel=path.unconfirmed?UNCONFIRMED_LABEL:null;
  }
  const regions=[];
  const floorZ=paths[0]?.points[0]?.[2]??null;
  for(const region of list(source.reachable_regions)) {
    // Only the contract's SAMPLE_SET kind is emitted in v1 (POLYGON is reserved); anything else is not drawn.
    const cells=region?.kind==='SAMPLE_SET'?list(region.samples):null;
    if(!finite(region?.timestamp_s)||!cells||!cells.length||!cells.every(point2)||!finite(region.cell_size_m)||region.cell_size_m<=0)return unknownPlan('INVALID_RESPONSE',interval,{hash});
    const flagged=new Set(list(region.walkable_unknown_sample_indices));
    regions.push({timestamp_s:region.timestamp_s,cell_size_m:region.cell_size_m,area_m2:region.area_m2??null,max_extent_m:region.max_extent_m??null,
      truncated:region.truncated===true,cells:cells.map((c,i)=>({x:c[0],y:c[1],unconfirmed:flagged.has(i)}))});
  }
  regions.sort((a,b)=>a.timestamp_s-b.timestamp_s);
  if(!paths.length||!regions.length||floorZ===null)return unknownPlan('INVALID_RESPONSE',interval,{hash});
  const steps=regions.slice(1).map((r,i)=>r.timestamp_s-regions[i].timestamp_s).filter(d=>d>1e-9);
  const timeStep=finite(source.configuration?.time_step_s)&&source.configuration.time_step_s>0?source.configuration.time_step_s:steps.length?Math.min(...steps):null;
  const top=paths[0];
  // Anchor of a substituted endpoint for the 3D caption: the route end inside that endpoint's region (null without route_m).
  const substitutions=list(source.endpoint_substitutions).map(item=>({...substitutionNotice(item),
    anchor:top?.withEnds?(item?.endpoint==='START'?top.points[0]:item?.endpoint==='END'?top.points.at(-1):null):null,label:'端點已替代'}));
  const notices=[...substitutions.map(s=>s.text),
    ...(paths.some(p=>p.unconfirmed)?[`${UNCONFIRMED_LABEL}：${paths.filter(p=>p.unconfirmed).map(p=>p.label).join('、')} 可走性未確認（walkable UNKNOWN），虛線段為未確認路段，仍列為假設，非驗證路徑`]:[]),
    ...(regions.some(r=>r.truncated)?['部分時刻的範圍取樣被截斷，顯示的範圍可能不完整']:[])];
  return {schema:BLIND_HYPOTHESIS_SCHEMA,status:'READY',reason:null,reasonText:null,interval,floorZ,timeStep,paths,regions,substitutions,notices,
    authority:{evidence_state:'INFERRED_HYPOTHESIS',ranking_basis:source.ranking_basis,physical_authority:source.physical_authority??'UNKNOWN',identity_verdict:source.identity_verdict??'UNCONFIRMED'},
    key:JSON.stringify(['READY',hash,interval,paths.map(p=>[p.ref,p.rank,p.unconfirmed,p.links.filter(l=>l.unconfirmed).length]),regions.map(r=>[r.timestamp_s,r.cells.length,r.cells.filter(c=>c.unconfirmed).length]),substitutions.map(item=>[item.endpoint,item.original_timestamp_s,item.substitute_timestamp_s])])};
}

// Region to draw at time t. Null at and outside the endpoints (those are observations) and between steps.
export function blindHypothesisRegionAt(plan,timestamp) {
  if(plan?.status!=='READY'||!finite(timestamp)||!(timestamp>plan.interval.start_s&&timestamp<plan.interval.end_s)||!plan.regions.length)return null;
  const tolerance=(plan.timeStep??0)/2+1e-9;let best=null;
  for(const region of plan.regions)if(!best||Math.abs(region.timestamp_s-timestamp)<Math.abs(best.timestamp_s-timestamp))best=region;
  return Math.abs(best.timestamp_s-timestamp)<=tolerance?best:null;
}
export const insideBlindInterval=(plan,timestamp)=>plan?.status==='READY'&&finite(timestamp)&&timestamp>plan.interval.start_s&&timestamp<plan.interval.end_s;

// Per-time [lo, hi] extents on X, Y and Z of the reachable region (x, y from the cells, z from the bundle): the band for the 2D XYZ curve.
export function blindHypothesisEnvelope(plan,timeRange=null) {
  if(plan?.status!=='READY')return [];
  const [t0,t1]=Array.isArray(timeRange)&&timeRange.length===2&&timeRange.every(finite)?timeRange:[-Infinity,Infinity];
  return plan.regions.filter(region=>region.timestamp_s>=t0&&region.timestamp_s<=t1).map(region=>{
    const half=region.cell_size_m/2,xs=region.cells.map(c=>c.x),ys=region.cells.map(c=>c.y);
    const zs=plan.paths.map(path=>path.samples.find(s=>Math.abs(s.timestamp_s-region.timestamp_s)<1e-6)?.position[2]).filter(finite);
    return {timestamp_s:region.timestamp_s,bounds:[[Math.min(...xs)-half,Math.max(...xs)+half],[Math.min(...ys)-half,Math.max(...ys)+half],
      [Math.min(...(zs.length?zs:[plan.floorZ])),Math.max(...(zs.length?zs:[plan.floorZ]))]]};
  });
}

export function blindHypothesisLegendHTML() {
  return `<ul class="blind-hypothesis-legend" data-blind-hypothesis-legend aria-label="證據圖例">${LEGEND_ITEMS.map(item=>`<li data-legend="${item.key}"><span class="swatch" style="--swatch:${item.color}" data-style="${item.style}"></span>${h(item.label)}</li>`).join('')}</ul>`;
}
// Status block: only for a recognised response. READY lists the bundle; UNKNOWN shows the reason and no position.
export function blindHypothesisStatusHTML(plan) {
  if(!plan)return '';
  const range=plan.interval?`${sec(plan.interval.start_s)}–${sec(plan.interval.end_s)}`:'區間未知';
  const head=plan.status==='READY'?
    `<p class="blind-hypothesis-head">盲區 ${h(range)} · 位置 UNKNOWN · ${plan.paths.length} 條假設路徑，依設定合理度排序，不是機率</p>`:
    `<p class="blind-hypothesis-head" data-blind-reason="${h(plan.reason)}">盲區 ${h(range)} · 位置 UNKNOWN · 不畫路徑與範圍 · ${h(plan.reasonText)}</p>`;
  const notices=plan.notices.map(text=>`<p class="blind-hypothesis-notice" data-blind-notice>${h(text)}</p>`).join('');
  return `<div class="blind-hypothesis" data-blind-hypothesis data-status="${plan.status}" role="status">${head}${notices}${blindHypothesisLegendHTML()}</div>`;
}

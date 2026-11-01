import {buildQ1,buildQ2,buildQ3} from './q-api.mjs';
import {checkRequest} from './q-validate.mjs';
export function parsePresentation(response,{review=false}={}) {
  if(!response)return {message:'輸入查詢，或開啟條件表單。',execute:false,options:[]};
  const status=response.status;
  const messages={PARSED:'已解析並執行。',NEEDS_CLARIFICATION:response.clarification?.question??'請補充條件與時間。',UNSUPPORTED_CLASS:'不支援此類別，請查看可用詞。',UNSUPPORTED_CONDITION:'不支援此條件組合，請查看可用詞。',PARSE_FAILED:'請改寫，或使用條件表單。',TIME_EXPRESSION_INVALID:'時間無法解析，請改寫或使用條件表單。',CLOCK_MAPPING_MISSING:'來源時鐘尚未提供，無法解析時間。',UNKNOWN:'資料不足，沒有執行。'};
  return {message:messages[status]??'資料不足，沒有執行。',execute:status==='PARSED',options:response.clarification?.options??[],
    audit:review?{status,parsed_by:response.parsed_by,fallback_reason:response.fallback_reason,llm_call:response.llm_call,unresolved_terms:response.unresolved_terms}:null};
}
// Demo shows a short 找／追 tag; review adds where the value came from. Contract §7 lists `intent` only in the LLM intermediate
// format, so a missing field falls back to the structured query kind (UNKNOWN when neither exists). Pending Codex confirmation.
export function intentPresentation(response,{review=false}={}) {
  if(!response)return null;
  const known={FIND_CAMERAS:{short:'找',long:'找鏡頭 · 哪些鏡頭拍到（Q1）'},FIND_PERSON:{short:'追',long:'追人 · 連續追蹤並切鏡（Q2）'},EXPLAIN:{short:'說明',long:'說明'},UNSUPPORTED:{short:'不支援',long:'不支援'}};
  const kind=response.structured_query?.schema_version;
  const derived=kind==='q-demo.q1-request.v1'?'FIND_CAMERAS':kind==='q-demo.q2-request.v1'?'FIND_PERSON':null;
  const code=response.intent??response.llm_output?.intent??response.parsed?.intent??derived;
  if(!known[code])return response.status==='PARSED'?{code:'UNKNOWN',short:'未判定',detail:review?'UNKNOWN · 回應沒有 intent 欄位，也無法由結構化查詢推得':''}:null;
  const from=response.intent!==undefined||response.llm_output?.intent!==undefined||response.parsed?.intent!==undefined?'intent 欄位':'由 structured_query 推得（回應未帶 intent）';
  return {code,short:known[code].short,detail:review?`${known[code].long} · ${code} · ${from}`:known[code].long};
}
export function manualRequest(run,session,{task='q1',classLabel='person',colorLabel='',startUs=0,endUs=run?.clock_mapping?.source_duration_us,switchMode='RULE_ONLY',cameraIds=null,regionIds=null}={}) {
  if(!run)throw new Error('SOURCE_REQUIRED');
  const catalog=run.supported_classes;
  if(!catalog.class_labels.includes(classLabel))throw new Error('UNSUPPORTED_CLASS');
  if(colorLabel&&(classLabel!=='person'||!catalog.color_vocabulary.labels.includes(colorLabel)))throw new Error('UNSUPPORTED_CONDITION');
  const color=colorLabel?{label:colorLabel,min_verdict:run.query_defaults.min_verdict}:null;
  const time={kind:'SOURCE',run_id:run.run_id,range_us:[startUs,endUs]};
  if(task==='q2')return buildQ2(run,session,{kind:'APPEARANCE',class_label:classLabel,color},{time,switch_mode:switchMode});
  return buildQ1(run,session,{time,condition:{class_label:classLabel,color,min_count_per_frame:run.query_defaults.min_count_per_frame,query_min_score:run.query_defaults.query_min_score},camera_ids:cameraIds,region_ids:regionIds});
}
export function editedRequest(text,session) {
  const q=JSON.parse(text);q.session_ref=session;
  const kind=q.schema_version==='q-demo.q1-request.v1'?'q1':q.schema_version==='q-demo.q2-request.v1'?'q2':null;
  if(!kind)throw new Error('QUERY_KIND');if(kind==='q1')q.origin='MANUAL';return checkRequest(kind,q);
}
export const textRequest=(run,session,text,parserMode='RULE_ONLY')=>buildQ3(run,session,text.trim(),parserMode);
export function vocabulary(run) {
  const c=run?.supported_classes;if(!c)return '尚無可用來源。';
  const alias=Object.entries(c.aliases??{}).map(([k,v])=>`${k} → ${v}`).join('、');
  return `類別：${c.class_labels.join('、')}。顏色（僅 person）：${c.color_vocabulary.labels.join('、')}。${alias}`;
}

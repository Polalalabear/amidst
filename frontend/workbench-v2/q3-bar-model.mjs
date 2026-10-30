import {buildQ1,buildQ2,buildQ3} from './q-api.mjs';
import {checkRequest} from './q-validate.mjs';
export function parsePresentation(response,{review=false}={}) {
  if(!response)return {message:'輸入查詢，或開啟條件表單。',execute:false,options:[]};
  const status=response.status;
  const messages={PARSED:'已解析並執行。',NEEDS_CLARIFICATION:response.clarification?.question??'請補充條件與時間。',UNSUPPORTED_CLASS:'不支援此類別，請查看可用詞。',UNSUPPORTED_CONDITION:'不支援此條件組合，請查看可用詞。',PARSE_FAILED:'請改寫，或使用條件表單。',TIME_EXPRESSION_INVALID:'時間無法解析，請改寫或使用條件表單。',CLOCK_MAPPING_MISSING:'來源時鐘尚未提供，無法解析時間。',UNKNOWN:'資料不足，沒有執行。'};
  return {message:messages[status]??'資料不足，沒有執行。',execute:status==='PARSED',options:response.clarification?.options??[],
    audit:review?{status,parsed_by:response.parsed_by,fallback_reason:response.fallback_reason,llm_call:response.llm_call,unresolved_terms:response.unresolved_terms}:null};
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

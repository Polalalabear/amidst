// Evaluation-only. No API, inference dispatch, filesystem, network or storage.
import {contentHash,sha256Hex,parseRaw,canonicalJSON,STATUS,validRange} from '../q-validate.mjs';
export const VERSION='1';
export const CONTRACT_COMMIT='09ae8e06a03c691cb23139305c10925cbf70d1a1';
export const CHECK_IDS=Object.freeze(['C-SCHEMA','C-IDENTITY','C-GT','C-HASH','C-ORIGIN','C-READY-SCOPE','C-NONE-SPLIT','C-RANK','C-TIMELINE','C-DECIDED-BY','C-FALLBACK','C-GUARD','C-ORDER']);
const fallbackReasons=new Set(['ROUND_LIMIT','TIME_BUDGET','PROVIDER_UNAVAILABLE','PROVIDER_TIMEOUT','INVALID_RESPONSE','ILLEGAL_CANDIDATE','EXPLANATION_INVALID','MODE_NOT_AUTHORIZED']);
const check=(id,value,detail='')=>({check_id:id,result:value===null?'NOT_APPLICABLE':value?'PASS':'FAIL',detail});
const kind=r=>r.schema_version==='q-demo.q1-response.v1'?'q1':r.schema_version==='q-demo.q2-response.v1'?'q2':r.schema_version==='q-demo.q3-parse-response.v1'?'q3':null;
const same=(a,b)=>canonicalJSON(a)===canonicalJSON(b);
const parameter=(parameters,name)=>parameters?.parameters?.find(x=>x.name===name&&x.status==='APPROVED')?.value;
export async function responseChecks(response,{decisions=null,evidence={},parameters=null,samples=[]}={}) {
  const r=response,k=kind(r),q2=k==='q2',q1=k==='q1';let hash=false;try{hash=await contentHash(r,{excludeRoot:['output_sha256','stats']})===r.output_sha256;}catch{}
  const out=[check('C-SCHEMA',Boolean(k&&STATUS[k].includes(r.status)),'封閉 schema/status'),check('C-IDENTITY',r.identity_verdict==='UNCONFIRMED','身分未確認'),check('C-GT',r.provenance?.gt_read===false,'推論 GT 邊界'),check('C-HASH',hash,'去掉 output_sha256 與根 stats 重算'),check('C-READY-SCOPE',!(r.status==='READY'&&r.resolved_scope?.time_coverage?.coverage_complete===false),'不完整涵蓋不得 READY')];
  let origin=null;
  for(let i=0;i<samples.length;i++)for(let j=i+1;j<samples.length;j++){
    const a=samples[i],b=samples[j];if(a.request?.origin===b.request?.origin||!a.request||!b.request)continue;
    const clean=x=>Object.fromEntries(Object.entries(x).filter(([key])=>!['origin','session_ref'].includes(key)));
    if(same(clean(a.request),clean(b.request))){const equal=a.response.output_sha256===b.response.output_sha256;origin=origin===false?false:equal;}
  }
  out.push(check('C-ORIGIN',origin,'只比較相同正規化請求及分頁、不同 origin 的已取得回應'));
  if(q1){const groups=[r.results??[],r.no_match_cameras??[],r.not_evaluated_cameras??[]],ids=groups.flat().map(x=>x.camera_id);out.push(check('C-NONE-SPLIT',new Set(ids).size===ids.length,'三區互斥'));
    const rows=r.results??[],first=x=>x.matched_segments?.[0]?.range_us[0]??Infinity;
    const rank=Array.isArray(r.ranking_basis)&&same(r.ranking_basis,['first_match_us_asc','camera_id'])&&rows.every((x,i)=>Number.isSafeInteger(x.rank)&&x.rank>=1&&(!i||x.rank===rows[i-1].rank+1&&(first(x)>first(rows[i-1])||first(x)===first(rows[i-1])&&x.camera_id>rows[i-1].camera_id)));
    out.push(check('C-RANK',rank,'本頁保留全域 rank；第一次相符時間與 camera_id 順序'));
  }else out.push(check('C-NONE-SPLIT',null),check('C-RANK',null));
  if(q2){const t=r.timeline??[];out.push(check('C-TIMELINE',Array.isArray(r.timeline)&&t.every((s,i)=>validRange(s.range_us)&&(!i||t[i-1].range_us[1]<=s.range_us[0])&&(['ON_CAMERA','GAP'].includes(s.kind))&&(s.kind!=='GAP'||s.position===null)),'半開、排序、不重疊、GAP 無位置'));
    if(decisions!==null){const accepted=decisions.filter(d=>d.accepted),switching=accepted.filter(d=>['SWITCH','RETURN_TO_ORIGIN'].includes(d.executed_action)),used=accepted.some(d=>d.decided_by==='AGENT');
      out.push(check('C-DECIDED-BY',r.agent_used===used&&r.decision_source===(switching.at(-1)?.decided_by??null),'使用紀錄推導 Agent used 與最後切鏡來源'));
      out.push(check('C-FALLBACK',decisions.every(d=>d.decided_by!=='RULE_FALLBACK'||fallbackReasons.has(d.fallback_reason)),'所有兜底紀錄有封閉原因'));
      const min=parameter(parameters,'switch_min_presence'),switches=accepted.filter(d=>d.executed_action==='SWITCH');
      const guard=min===undefined?null:switches.every(d=>{const c=d.candidates_considered.find(x=>x.candidate_ref===d.executed_candidate_ref),e=c&&evidence[c.evidence_sha256];const strengths={MATCH_WEAK:1,MATCH_STRONG:2};return Boolean(strengths[min])&&c&&e&&c.target_presence===e.target_presence&&strengths[c.target_presence]>=strengths[min]&&e.entry_observation_id===d.entry_observation_id&&e.entry_timestamp_us===d.source_time_us&&e.entry_timestamp_us>=d.decision_time_us&&e.window_us[0]<=e.entry_timestamp_us&&e.entry_timestamp_us<e.window_us[1];});
      out.push(check('C-GUARD',guard,min===undefined?'沒有核准參數原文，無法核對 guard':'以核准參數及獨立 evidence 核對執行的 SWITCH'));
      let order=true;const seen=new Map();for(const d of decisions){const group=seen.get(d.searching_index)??[];for(const c of d.candidates_considered??[]){if(!Number.isSafeInteger(c.rank)||c.rank<1){order=false;continue;}if(!group.includes(c.rank)){if(c.rank!==group.length+1)order=false;group.push(c.rank);}}seen.set(d.searching_index,group);}
      out.push(check('C-ORDER',order,'每次搜尋的首次取證候選依序；拒絕不消耗游標'));
    }else out.push(...['C-DECIDED-BY','C-FALLBACK','C-GUARD','C-ORDER'].map(id=>check(id,null,'缺少已驗證 journal')));
  }else out.push(...['C-TIMELINE','C-DECIDED-BY','C-FALLBACK','C-GUARD','C-ORDER'].map(id=>check(id,null)));
  return out;
}
export async function loadExpectations(text){
  if(typeof text!=='string'||text.length>2000000)throw new Error('EXPECTED_FILE_TOO_LARGE');const doc=parseRaw(text);
  if(doc.schema_version!=='q-demo.review-expectations.v1'||doc.local_only!==true||typeof doc.expectations_id!=='string'||!doc.applies_to||!Array.isArray(doc.items)||!Array.isArray(doc.leak_probes)||doc.leak_probes.some(x=>typeof x!=='string'||!x))throw new Error('EXPECTED_FILE_INVALID');
  const ids=doc.items.map(x=>x.expectation_id);if(ids.some(x=>typeof x!=='string'||!x)||new Set(ids).size!==ids.length)throw new Error('EXPECTED_IDS_INVALID');
  return {document:doc,file_sha256:await sha256Hex(text)};
}
export function expectationApplies(loaded,response){
  if(!loaded)return false;const expected=loaded.document.applies_to,actual=response.resolved_scope??{};
  const required=['scene_id','scene_revision','run_ids','detection_index_sha256','parameter_set_sha256','clock_mapping_sha256'];
  return required.every(key=>Object.hasOwn(expected,key)&&same(expected[key],actual[key]))&&Object.entries(expected).every(([key,value])=>Object.hasOwn(actual,key)&&same(value,actual[key]));
}
export function scanLeaks(values,probes){
  const hits=[];function walk(value,path){if(typeof value==='string'){if(probes.some(p=>value.includes(p)))hits.push(path);}else if(value&&typeof value==='object')for(const [key,child] of Object.entries(value))walk(child,path+'.'+key);}
  walk(values,'$');return hits;
}
function queryMatches(match,request,response){
  const q=match?.query??{};const values={class_label:request?.condition?.class_label??request?.seed?.class_label??response.normalized_condition?.class_label,seed_color:request?.seed?.color?.label,query_sha256:response.query_sha256};
  for(const [key,value] of Object.entries(q)){if(values[key]===undefined)return null;if(values[key]!==value)return false;}
  if(Object.keys(match??{}).some(k=>!['query','from_camera_id'].includes(k)))return null;return true;
}
export function expectationHints(loaded,response,{request=null,decisions=null}={}){
  if(!loaded||!expectationApplies(loaded,response))return [];
  return loaded.document.items.map(item=>{let answer=null;const match=queryMatches(item.match,request,response);
    if(match===true&&response.status!=='PARTIAL'){
      const expected=item.expected??{};
      if(kind(response)==='q1'&&['Q1_CAMERA_IN_RESULTS','Q1_CAMERA_NOT_IN_RESULTS'].includes(item.kind)&&['READY','NO_MATCH'].includes(response.status)){
        const hit=response.results.some(x=>x.camera_id===expected.camera_id);answer=item.kind==='Q1_CAMERA_IN_RESULTS'?hit:response.next_cursor===null?!hit:null;
        // A page without a camera cannot establish absence across earlier/later pages.
        if(!hit&&(response.returned_count!==response.results_total||response.next_cursor!==null))answer=null;
      }
      if(kind(response)==='q3'&&item.kind==='Q3_INTENT'&&response.intent!==undefined)answer=response.intent===expected.intent;
      if(kind(response)==='q2'&&decisions!==null){const switches=decisions.filter(d=>d.accepted&&d.executed_action==='SWITCH');
        if(item.kind==='Q2_NO_SWITCH_BEFORE'&&Number.isSafeInteger(expected.source_time_us))answer=!switches.some(d=>d.source_time_us<expected.source_time_us);
        if(item.kind==='Q2_RETURNS_TO_ORIGIN')answer=decisions.some(d=>d.accepted&&d.executed_action==='RETURN_TO_ORIGIN');
        if(item.kind==='Q5_SWITCH_TO'&&validRange(expected.within_source_range_us))answer=switches.some(d=>{
          const destination=response.timeline.find(s=>s.kind==='ON_CAMERA'&&s.decision_id===d.decision_id),previous=response.timeline.filter(s=>s.kind==='ON_CAMERA'&&s.range_us[1]<=d.source_time_us).at(-1);
          return destination?.camera_id===expected.to_camera_id&&(!item.match?.from_camera_id||previous?.camera_id===item.match.from_camera_id)&&expected.within_source_range_us[0]<=d.source_time_us&&d.source_time_us<expected.within_source_range_us[1];
        });
      }
    }
    return {expectation_id:item.expectation_id,hint:match===false?'CANNOT_EVALUATE':answer===null?'CANNOT_EVALUATE':answer?'MATCHES':'DIFFERS'};
  });
}
export async function buildAudit({responses=[],artifacts={},parameters=null,samples=[],loaded=null}={}){
  const items=[],metadata=[];
  for(const response of responses){const k=kind(response),q2=k==='q2',journal=q2?(artifacts.decisions??null):null,proof=q2?(artifacts.evidence??{}):{};
    const checks=await responseChecks(response,{decisions:journal,evidence:proof,parameters,samples});const hints=expectationHints(loaded,response,{request:samples.findLast(x=>x.response.output_sha256===response.output_sha256)?.request,decisions:journal});
    const leak=loaded?scanLeaks({response,artifacts:q2?artifacts:null},loaded.document.leak_probes):[];if(leak.length)checks.push(check('C-LEAK',false,'洩漏字串命中路徑：'+leak.join(', ')));
    const hash=checks.find(x=>x.check_id==='C-HASH');metadata.push({endpoint:k==='q3'?'q3_parse':k==='q2'?'q2_session':'q1_camera_search',schema_version:response.schema_version,query_id:response.query_id??null,session_id:response.session_id??null,output_sha256:response.output_sha256,output_sha256_recomputed:await contentHash(response,{excludeRoot:['output_sha256','stats']}),hash_match:hash.result==='PASS',decisions_sha256:response.decisions_sha256??null});
    const add=(targetKind,ref,index,auto=[],schema=response.schema_version)=>items.push({item_id:`rv:${response.output_sha256.slice(0,16)}:${targetKind}:${index}`,target:{kind:targetKind,schema_version:schema,response_output_sha256:response.output_sha256,ref},auto_checks:auto,expectation_refs:targetKind==='RESPONSE_COMMON'?hints:[],verdict:'UNREVIEWED',note:'',reviewed_at:null});
    add('RESPONSE_COMMON',{},0,checks);
    if(k==='q3')add('Q3_PARSE',{},0);
    if(k==='q1'){for(const [i,result] of response.results.entries())add('Q1_RESULT',{result_index:i,rank:result.rank},i);add('Q1_NO_MATCH_GROUP',{},0);add('Q1_NOT_EVALUATED_GROUP',{},0);}
    if(q2){for(const [i,segment] of response.timeline.entries())add('Q2_TIMELINE_SEGMENT',{segment_id:segment.segment_id,source_time_us:segment.range_us[0]},i);for(const [i,e] of Object.values(proof).entries())add('Q4_EVIDENCE',{evidence_sha256:e.evidence_sha256},i,[],e.schema_version);for(const d of journal??[])add('Q5_DECISION',{session_id:response.session_id,decision_id:d.decision_id,step_index:d.step_index,source_time_us:d.source_time_us},d.step_index,[],d.schema_version);}
  }
  return {items,responses:metadata,output_hashes:responses.map(x=>x.output_sha256),expectations:loaded?{loaded:true,expectations_id:loaded.document.expectations_id,file_sha256:loaded.file_sha256,applied:responses.some(r=>expectationApplies(loaded,r))}:{loaded:false}};
}
export function judge(items,id,verdict,note='',reviewedAt=null){
  if(!['UNREVIEWED','PASS','FAIL','UNSURE'].includes(verdict))throw new Error('VERDICT_INVALID');if(typeof note!=='string'||note.length>10000)throw new Error('NOTE_INVALID');
  return items.map(x=>x.item_id===id?{...x,verdict,note,reviewed_at:reviewedAt}:x);
}
function privateStrings(loaded){
  if(!loaded)return [];const strings=[...loaded.document.leak_probes];function leaves(x){if(typeof x==='string'&&x)strings.push(x);else if(x&&typeof x==='object')Object.values(x).forEach(leaves);}
  for(const item of loaded.document.items){if(typeof item.description==='string'&&item.description)strings.push(item.description);leaves(item.expected);}return strings;
}
export async function exportRecord({audit,allItems=audit.items,reviewer,reviewedAt,source={},parameterSet={},contractCommit=CONTRACT_COMMIT,uiCommit='UNKNOWN',loaded=null}={}){
  if(typeof reviewer!=='string'||!reviewer.trim())throw new Error('REVIEWER_REQUIRED');
  const hashes=new Set(audit.output_hashes),items=allItems.filter(x=>hashes.has(x.target.response_output_sha256));
  if(items.some(x=>x.verdict==='FAIL'&&!x.note.trim()))throw new Error('FAIL_NOTE_REQUIRED');
  // Explicit allowlist: no local descriptions, expected answers, probes or hint detail.
  const clean=items.map(x=>({item_id:x.item_id,target:x.target,auto_checks:x.auto_checks.map(c=>({check_id:c.check_id,result:c.result,detail:c.detail})),expectation_refs:x.expectation_refs.map(e=>({expectation_id:e.expectation_id,hint:e.hint})),verdict:x.verdict,note:x.note,reviewed_at:x.reviewed_at}));
  const synthetic=/SYNTHETIC|PILOT/.test(String(source.source_kind))||source.data_origin==='SYNTHETIC_FIXTURE';
  const eligible=!synthetic&&['LIVE','REAL','RECORDED'].includes(source.data_origin)&&source.source_kind&&source.source_kind!=='UNKNOWN';
  const record={schema_version:'q-demo.review-record.v1',contract:{name:'Q1_Q2_FIRST_DEMO_V1',status:'DRAFT',commit:contractCommit},ui:{app:'workbench-v2',commit:uiCommit,review_model_version:VERSION},reviewer:{name:reviewer.trim()},reviewed_at:reviewedAt,data_source:{data_origin:source.data_origin??'UNKNOWN',source_kind:source.source_kind??'UNKNOWN',recorded_at:source.recorded_at??null,counts_for_acceptance:Boolean(eligible)},parameter_set:{parameter_set_id:parameterSet.parameter_set_id??null,parameter_set_sha256:parameterSet.parameter_set_sha256??null},responses:audit.responses,expectations:audit.expectations,items:clean,
    summary:{items:clean.length,pass:clean.filter(x=>x.verdict==='PASS').length,fail:clean.filter(x=>x.verdict==='FAIL').length,unsure:clean.filter(x=>x.verdict==='UNSURE').length,unreviewed:clean.filter(x=>x.verdict==='UNREVIEWED').length,auto_check_fail:clean.flatMap(x=>x.auto_checks).filter(x=>x.result==='FAIL').length,leak_probe_hits:clean.flatMap(x=>x.auto_checks).filter(x=>x.check_id==='C-LEAK').length,stale_items_excluded:allItems.length-items.length}};
  const forbidden=privateStrings(loaded);const raw=JSON.stringify(record);if(forbidden.some(x=>raw.includes(x)))throw new Error('PRIVATE_EXPECTATION_EXPORT_COLLISION');
  const stable={...record,items:record.items.map(({reviewed_at,...x})=>x)};delete stable.reviewed_at;record.content_sha256=await contentHash(stable);record.review_id='rvw:'+record.content_sha256.slice(0,16);return record;
}
export async function validateRecord(text){
  const value=parseRaw(text);if(value.schema_version!=='q-demo.review-record.v1')throw new Error('REVIEW_RECORD_SCHEMA');
  const stable={...value,items:value.items.map(({reviewed_at,...x})=>x)};delete stable.reviewed_at;delete stable.content_sha256;delete stable.review_id;
  if(await contentHash(stable)!==value.content_sha256||value.review_id!=='rvw:'+value.content_sha256.slice(0,16))throw new Error('REVIEW_RECORD_HASH');return value;
}
export const reviewerPreference=name=>({key:'amidst.q-review.reviewer',value:String(name)});

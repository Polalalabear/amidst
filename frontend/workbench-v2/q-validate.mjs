// Q response boundary. Raw numeric types survive parsing for Python canonical hashes.
const lexemes = new WeakMap();
const validated = new WeakSet();
export const STATUS = Object.freeze({
  q1: Object.freeze(['READY','NO_MATCH','PARTIAL','UNSUPPORTED_CLASS','UNSUPPORTED_CONDITION','OUT_OF_RANGE','UNKNOWN']),
  q2: Object.freeze(['COMPLETE','PARTIAL','NO_SEED','ENDED_BY_LIMIT','UNKNOWN']),
  q3: Object.freeze(['PARSED','NEEDS_CLARIFICATION','UNSUPPORTED_CLASS','UNSUPPORTED_CONDITION','PARSE_FAILED','TIME_EXPRESSION_INVALID']),
});
export const isObject = v => v !== null && typeof v === 'object' && !Array.isArray(v);
export const integer = v => Number.isSafeInteger(v) && v >= 0;
const hex = v => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v);
const text = v => typeof v === 'string' && v.length > 0;
const demand = (ok, code) => { if (!ok) throw new Error(code); };
export function freezeDeep(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) freezeDeep(child);
    Object.freeze(value);
  }
  return value;
}
export const isValidated = value => validated.has(value);

function pythonFloat(n) {
  demand(Number.isFinite(n), 'NON_FINITE_NUMBER');
  if (Object.is(n,-0)) return '-0.0';
  const a=Math.abs(n);
  if (a!==0 && (a<1e-4 || a>=1e16)) {
    const [mantissa,exponent]=n.toExponential().split('e');
    const e=Number(exponent);
    return `${mantissa}e${e<0?'-':'+'}${String(Math.abs(e)).padStart(2,'0')}`;
  }
  const s=String(n);return s.includes('.')?s:s+'.0';
}

// Only canonical Python float tokens are accepted from this backend. Ambiguous
// cross-language number renderings fail closed rather than approving a bad pin.
export function parseRaw(raw) {
  demand(typeof raw==='string','RAW_JSON_REQUIRED');let i=0;
  const ws=()=>{while (/\s/.test(raw[i]??'') && i<raw.length) i++;};
  function string() {
    const start=i++;let escaped=false;
    while(i<raw.length){const c=raw[i++];if(escaped){escaped=false;continue;}if(c==='\\'){escaped=true;continue;}if(c==='"')return JSON.parse(raw.slice(start,i));}
    throw new Error('INVALID_JSON');
  }
  function node() {
    ws();const c=raw[i];
    if(c==='{' || c==='[') {
      const object=c==='{'?{}:[];const numbers=new Map();lexemes.set(object,numbers);i++;ws();
      const end=c==='{'?'}':']';if(raw[i]===end){i++;return object;}
      while(i<raw.length) {
        ws();let key;
        if(c==='{') { demand(raw[i]==='"','INVALID_JSON');key=string();demand(!Object.hasOwn(object,key),'DUPLICATE_KEY');demand(!['__proto__','constructor','prototype'].includes(key),'FORBIDDEN_KEY');ws();demand(raw[i++]===':','INVALID_JSON'); }
        else key=String(object.length);
        ws();const start=i;const value=node();const token=raw.slice(start,i);
        Object.defineProperty(object,key,{value,writable:true,enumerable:true,configurable:true});
        if(typeof value==='number') numbers.set(key,token);
        ws();if(raw[i]===end){i++;return object;}demand(raw[i++ ]===',','INVALID_JSON');
      }
      throw new Error('INVALID_JSON');
    }
    if(c==='"')return string();
    for(const [token,value] of [['null',null],['true',true],['false',false]]) if(raw.startsWith(token,i)){i+=token.length;return value;}
    const m=raw.slice(i).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    demand(m,'INVALID_JSON');i+=m[0].length;const n=Number(m[0]);demand(Number.isFinite(n),'NON_FINITE_NUMBER');
    if(/[.eE]/.test(m[0]))demand(pythonFloat(n)===m[0],'NUMBER_CANONICAL_AMBIGUOUS');
    else demand(Number.isSafeInteger(n),'UNSAFE_INTEGER');
    return n;
  }
  const value=node();ws();demand(i===raw.length,'INVALID_JSON');return value;
}
function ascii(value){return JSON.stringify(value).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));}
function compareCodepoints(a,b){const aa=Array.from(a),bb=Array.from(b);for(let i=0;i<Math.min(aa.length,bb.length);i++){const d=aa[i].codePointAt(0)-bb[i].codePointAt(0);if(d)return d;}return aa.length-bb.length;}
export function canonicalJSON(value,{excludeRoot=[],stripCandidateRefs=false}={}) {
  function walk(v,parent,key,path) {
    if(v===null)return 'null';
    if(typeof v==='string')return ascii(v);
    if(typeof v==='boolean')return v?'true':'false';
    if(typeof v==='number') {
      demand(Number.isFinite(v),'NON_FINITE_NUMBER');const token=parent&&lexemes.get(parent)?.get(key);
      if(token && /[.eE]/.test(token) && Number(token)===v && Object.is(Number(token),-0)===Object.is(v,-0))return token;
      demand(!Number.isInteger(v)||Number.isSafeInteger(v),'UNSAFE_INTEGER');
      return Number.isInteger(v)?String(v):pythonFloat(v);
    }
    if(Array.isArray(v))return '['+v.map((child,index)=>walk(child,v,String(index),path+'/'+index)).join(',')+']';
    demand(isObject(v),'INVALID_CANONICAL_VALUE');
    const keys=Object.keys(v).filter(k=>!(path===''&&excludeRoot.includes(k))&&!(stripCandidateRefs&&/^\/candidates\/\d+$/.test(path)&&k==='candidate_ref')).sort(compareCodepoints);
    return '{'+keys.map(k=>ascii(k)+':'+walk(v[k],v,k,path+'/'+k)).join(',')+'}';
  }
  return walk(value,null,'','');
}
export async function sha256Hex(raw) {
  demand(globalThis.crypto?.subtle,'CRYPTO_UNAVAILABLE');
  const bytes=typeof raw==='string'?new TextEncoder().encode(raw):raw;
  const result=await crypto.subtle.digest('SHA-256',bytes);
  return [...new Uint8Array(result)].map(x=>x.toString(16).padStart(2,'0')).join('');
}
export const contentHash=(value,options)=>sha256Hex(canonicalJSON(value,options));
const forbidden=new Set(['gt','ground_truth','actor_id','persons.sim.json','event_script','production_manifest','renderer_trajectory','depth','mask','visibility_map','private_evaluation']);
export function noPrivate(value) {
  if(value&&typeof value==='object')for(const [key,child] of Object.entries(value)) { demand(!forbidden.has(key.toLowerCase())&&(key.toLowerCase()!=='gt_read'||child===false),'FORBIDDEN_INPUT');noPrivate(child); }
}
export function validRange(r){return Array.isArray(r)&&r.length===2&&r.every(integer)&&r[0]<r[1];}
export function checkRequest(kind,q) {
  const fields={q1:['schema_version','session_ref','scene_id','run_ids','time','condition','camera_ids','region_ids','page_size','cursor','origin'],
    q2:['schema_version','session_ref','scene_id','run_ids','time','seed','switch_mode','parameter_set_id'],
    q3:['schema_version','session_ref','text','locale','context','parser_mode']}[kind];
  demand(fields&&isObject(q)&&Object.keys(q).length===fields.length&&fields.every(k=>Object.hasOwn(q,k)),'REQUEST_FIELDS');
  demand(q.schema_version===`q-demo.${kind==='q3'?'q3-parse':kind}-request.v1`&&text(q.session_ref),'REQUEST_SCHEMA');noPrivate(q);
  if(kind==='q3'){demand(text(q.text)&&q.locale==='zh-TW'&&['RULE_ONLY','LLM_WITH_RULE_FALLBACK'].includes(q.parser_mode),'REQUEST_Q3');return q;}
  demand(text(q.scene_id)&&Array.isArray(q.run_ids)&&q.run_ids.length===1&&q.run_ids.every(text),'REQUEST_SCOPE');
  demand(isObject(q.time)&&((q.time.kind==='SOURCE'&&q.time.run_id===q.run_ids[0]&&validRange(q.time.range_us))
    ||(q.time.kind==='WALL'&&Array.isArray(q.time.wall_range)&&q.time.wall_range.length===2&&q.time.wall_range.every(text))),'REQUEST_TIME');
  if(kind==='q1')demand(isObject(q.condition)&&text(q.condition.class_label)&&Number.isFinite(q.condition.query_min_score)
    &&q.condition.query_min_score>=0&&q.condition.query_min_score<=1&&integer(q.condition.min_count_per_frame)&&q.condition.min_count_per_frame>0
    &&integer(q.page_size)&&q.page_size>0&&['MANUAL','PREFILL','Q3_PARSED'].includes(q.origin),'REQUEST_Q1');
  if(kind==='q2')demand(isObject(q.seed)&&['OBSERVATION','APPEARANCE'].includes(q.seed.kind)&&['RULE_ONLY','AGENT_SEQUENTIAL'].includes(q.switch_mode)&&text(q.parameter_set_id),'REQUEST_Q2');
  return q;
}
function common(r,kind) {
  demand(r.schema_version===`q-demo.${kind==='q3'?'q3-parse':kind}-response.v1`&&STATUS[kind]?.includes(r.status),'RESPONSE_SCHEMA_STATUS');
  demand(r.provenance?.gt_read===false&&r.identity_verdict==='UNCONFIRMED','INFERENCE_BOUNDARY');noPrivate(r);
  for(const flag of ['agent_attempted','agent_used','fallback_used','llm_parse_used'])demand(typeof r[flag]==='boolean','RESPONSE_FLAGS');
  demand(!r.agent_used||r.agent_attempted,'AGENT_FLAGS');demand(r.fallback_used===Boolean(r.fallback_reason),'FALLBACK_FLAGS');
  demand([null,'ROUND_LIMIT','TIME_BUDGET','PROVIDER_UNAVAILABLE','PROVIDER_TIMEOUT','INVALID_RESPONSE','ILLEGAL_CANDIDATE','EXPLANATION_INVALID','MODE_NOT_AUTHORIZED'].includes(r.fallback_reason),'FALLBACK_REASON');
  demand([null,'AGENT','RULE_FALLBACK','RULE_ONLY','USER'].includes(r.decision_source),'DECISION_SOURCE');
  if(kind!=='q2')demand(!r.agent_used&&!r.agent_attempted&&r.decision_source===null,'NON_AGENT_RESPONSE');
  if(r.decision_source==='AGENT')demand(r.agent_used&&r.agent_attempted,'AGENT_FLAGS');
  if(r.decision_source==='RULE_FALLBACK')demand(r.fallback_used,'FALLBACK_FLAGS');
  demand(isObject(r.resolved_scope)&&hex(r.output_sha256),'SCOPE_HASH');
}
function q1(r) {
  demand(Array.isArray(r.results)&&Array.isArray(r.no_match_cameras)&&Array.isArray(r.not_evaluated_cameras),'Q1_GROUPS');
  demand(integer(r.results_total)&&integer(r.returned_count)&&r.returned_count===r.results.length&&r.results_total>=r.returned_count,'Q1_COUNTS');
  const cameras=[...r.results,...r.no_match_cameras,...r.not_evaluated_cameras].map(x=>x.camera_id);
  demand(cameras.every(text)&&new Set(cameras).size===cameras.length,'Q1_DISJOINT');
  let rank=r.results[0]?.rank??1;
  for(const result of r.results){demand(result.rank===rank++&&Array.isArray(result.matched_segments),'Q1_ORDER');let end=-1;
    for(const segment of result.matched_segments){demand(validRange(segment.range_us)&&segment.range_us[0]>=end,'Q1_SEGMENTS');end=segment.range_us[1];}
  }
}
function q2(r) {
  demand(Array.isArray(r.timeline)&&text(r.session_id)&&text(r.decisions_ref)&&hex(r.decisions_sha256)&&text(r.links_ref)&&hex(r.links_sha256),'Q2_FIELDS');
  let end=-1;
  for(const segment of r.timeline){demand(validRange(segment.range_us)&&segment.range_us[0]>=end,'Q2_TIMELINE');end=segment.range_us[1];
    demand(['ON_CAMERA','GAP'].includes(segment.kind),'Q2_SEGMENT_KIND');
    if(segment.kind==='GAP')demand(segment.position===null&&text(segment.camera_shown),'GAP_POSITION');
    else demand(text(segment.camera_id)&&Array.isArray(segment.observation_ids)&&segment.observation_ids.every(text),'OBSERVATION_REFS');
  }
}
export async function validateQResponse(kind,input,{scene_id,run_id}={}) {
  try {
    const r=typeof input==='string'?parseRaw(input):parseRaw(JSON.stringify(input));demand(isObject(r),'RESPONSE_OBJECT');common(r,kind);
    if(scene_id!==undefined)demand(r.resolved_scope.scene_id===scene_id,'SCOPE_MISMATCH');
    if(run_id!==undefined)demand(r.resolved_scope.run_ids?.length===1&&r.resolved_scope.run_ids[0]===run_id,'SCOPE_MISMATCH');
    if(kind==='q1')q1(r);if(kind==='q2')q2(r);
    if(kind==='q3') {
      demand((r.status==='PARSED')===(r.structured_query!==null),'Q3_EXECUTION_GATE');
      if(r.status==='PARSED')checkRequest(r.structured_query.schema_version==='q-demo.q1-request.v1'?'q1':'q2',r.structured_query);
      if(r.status==='NEEDS_CLARIFICATION')demand(text(r.clarification?.question)&&Array.isArray(r.clarification?.options),'CLARIFICATION_SCHEMA');
    }
    demand(await contentHash(r,{excludeRoot:['output_sha256','stats']})===r.output_sha256,'OUTPUT_HASH_MISMATCH');
    freezeDeep(r);validated.add(r);return {ok:true,data:r};
  } catch(error){return {ok:false,error:{code:error.message}};}
}

export async function checkDecision(row,sessionId,index) {
  const states=['PLAYING','TEMP_LOST','SEARCHING','SWITCHING','RETURNED_TO_ORIGIN','ENDED'];
  demand(row.schema_version==='q-demo.decision-record.v1'&&row.session_id===sessionId&&row.step_index===index,'DECISION_SCOPE');
  demand((row.state_before===null||states.includes(row.state_before))&&states.includes(row.state_after)&&integer(row.source_time_us),'DECISION_STATE');
  demand(row.decision_time_us===null||(integer(row.decision_time_us)&&row.source_time_us>=row.decision_time_us),'DECISION_TIME');
  demand(integer(row.searching_index)&&integer(row.session_agent_rounds_used)&&integer(row.rounds_used)&&integer(row.budget_used_ms),'DECISION_COUNTERS');
  demand(typeof row.accepted==='boolean'&&(row.accepted||row.rejection_code!==null&&row.state_before===row.state_after),'DECISION_REJECTION');
  demand(['AGENT','RULE_ONLY','RULE_FALLBACK','USER'].includes(row.decided_by)&&Array.isArray(row.llm_calls)&&Array.isArray(row.tool_calls),'DECISION_SOURCE');
  if(row.decided_by==='RULE_FALLBACK')demand(typeof row.fallback_reason==='string'&&row.fallback_reason.length>0,'DECISION_FALLBACK');
  if(row.decided_by==='AGENT')demand(row.llm_calls.length>0,'DECISION_LLM_AUDIT');
  demand(await contentHash(row,{excludeRoot:['content_sha256','stats']})===row.content_sha256,'DECISION_PIN');noPrivate(row);return row;
}

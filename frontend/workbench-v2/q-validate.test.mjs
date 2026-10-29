import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parseRaw,canonicalJSON,sha256Hex,contentHash,validateQResponse,isValidated,checkDecision } from './q-validate.mjs';
const fixture=async name=>JSON.parse(await readFile(new URL(`fixtures/${name}.json`,import.meta.url),'utf8'));

test('Python json.dumps cross-language matrix: Unicode codepoint keys, ASCII, floats, negative zero and exponents',async()=>{
  const vectors=await fixture('q-canonical-vectors');
  for(const v of vectors){const raw=parseRaw(v.raw);assert.equal(canonicalJSON(raw),v.canonical);assert.equal(await contentHash(raw),v.sha256);}
  assert.notEqual(JSON.stringify({'中文':'雪'}),canonicalJSON({'中文':'雪'}),'legacy raw Unicode stringify does not match ensure_ascii=True');
});

test('invalid/ambiguous numbers, duplicate keys, prototype keys and non-JSON values fail closed',()=>{
  for(const raw of ['{"x":1.00}','{"x":NaN}','{"x":Infinity}','{"x":9007199254740993}','{"x":1,"x":2}','{"__proto__":{}}','{"constructor":1}','{"x":01}','{"x":1} trailing'])assert.throws(()=>parseRaw(raw));
  for(const value of [{x:NaN},{x:undefined},{x:Infinity}])assert.throws(()=>canonicalJSON(value));
});

test('all actual kernel fixture responses verify and remain frozen; stats exclusion is root-only',async()=>{
  for(const name of ['q1-ready','q1-partial','q1-no-match','q1-out-of-range','q2-rule','q2-agent','q2-no-support','q3-parsed','q3-clarification','q3-unsupported','q3-failed']) {
    const doc=await fixture(name);
    for(const c of doc.cases){const result=await validateQResponse(name.slice(0,2),c.response_json);assert.equal(result.ok,true,`${name} ${JSON.stringify(result.error)}`);assert.ok(isValidated(result.data));assert.ok(Object.isFrozen(result.data.resolved_scope));}
  }
  const raw=(await fixture('q1-ready')).cases[0].response_json;const a=JSON.parse(raw);a.stats={latency_ms:1.234};
  assert.equal((await validateQResponse('q1',a)).ok,true);
  a.provenance.stats={latency_ms:1};assert.equal((await validateQResponse('q1',a)).error.code,'OUTPUT_HASH_MISMATCH');
});

test('status closed lists, GT, identity, hash and scope tampering return no drawable data',async()=>{
  const base=JSON.parse((await fixture('q1-ready')).cases[0].response_json);
  for(const patch of [{status:'PASS'},{identity_verdict:'CONFIRMED'},{provenance:{gt_read:true}},{output_sha256:'0'.repeat(64)},{ground_truth:{}},{fallback_used:true,fallback_reason:'made-up'}]){
    const r=await validateQResponse('q1',{...base,...patch});assert.equal(r.ok,false);assert.equal(r.data,undefined);
  }
  assert.equal((await validateQResponse('q1',base,{scene_id:'foreign'})).ok,false);
  for(const kind of ['q2','q3']){const b=JSON.parse((await fixture(kind==='q2'?'q2-rule':'q3-parsed')).cases[0].response_json);b.status='PASS';assert.equal((await validateQResponse(kind,b)).ok,false);}
});

test('last page can have total above returned count; Q1 categories remain disjoint',async()=>{
  const r=JSON.parse((await fixture('q1-ready')).cases[0].response_json);r.results=r.results.slice(1);r.returned_count=1;r.next_cursor=null;
  r.output_sha256=await contentHash(r,{excludeRoot:['output_sha256','stats']});assert.equal((await validateQResponse('q1',r)).ok,true);
  r.no_match_cameras.push({camera_id:r.results[0].camera_id});assert.equal((await validateQResponse('q1',r)).error.code,'Q1_DISJOINT');
});

test('Q2 gaps cannot acquire a hidden position and nonparsed Q3 cannot execute',async()=>{
  const q2=JSON.parse((await fixture('q2-rule')).cases[0].response_json);q2.timeline.find(s=>s.kind==='GAP').position=[1,2,3];assert.equal((await validateQResponse('q2',q2)).error.code,'GAP_POSITION');
  const q3=JSON.parse((await fixture('q3-clarification')).cases[0].response_json);q3.structured_query={};assert.equal((await validateQResponse('q3',q3)).error.code,'Q3_EXECUTION_GATE');
});

test('D69 journal checks preserve exact raw hashes and reject counters/rejections/time corruption',async()=>{
  const c=(await fixture('q2-agent')).cases[0];const r=parseRaw(c.response_json);const rows=c.artifacts.decisions.split('\n').filter(Boolean).map(parseRaw);
  assert.equal(await sha256Hex(c.artifacts.decisions),r.decisions_sha256);
  for(const [i,row] of rows.entries())assert.equal(await checkDecision(row,r.session_id,i),row);
  for(const patch of [{searching_index:-1},{session_agent_rounds_used:undefined},{source_time_us:-1},{state_after:'FAKE'},{content_sha256:'0'.repeat(64)}]){
    const d={...rows[0],...patch};await assert.rejects(()=>checkDecision(d,r.session_id,0));
  }
});

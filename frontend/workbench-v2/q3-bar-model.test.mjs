import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
import {parseRaw,checkRequest} from './q-validate.mjs';
import {parsePresentation,manualRequest,editedRequest,textRequest,vocabulary} from './q3-bar-model.mjs';
const pack=async n=>JSON.parse(await readFile(new URL(`./fixtures/${n}.json`,import.meta.url),'utf8'));
const run=parseRaw((await pack('q-bootstrap')).bootstrap_json).runs[0];
for(const [file,status,exec] of [['q3-parsed','PARSED',true],['q3-clarification','NEEDS_CLARIFICATION',false],['q3-unsupported','UNSUPPORTED_CONDITION',false],['q3-failed','PARSE_FAILED',false]])test(`${status} execution policy`,async()=>{const r=parseRaw((await pack(file)).cases[0].response_json),m=parsePresentation(r);assert.equal(m.execute,exec);assert.equal(m.audit,null);assert.equal(parsePresentation(r,{review:true}).audit.status,status);});
for(const status of ['TIME_EXPRESSION_INVALID','UNSUPPORTED_CLASS','CLOCK_MAPPING_MISSING','UNKNOWN'])test(`${status} never executes`,()=>assert.equal(parsePresentation({status}).execute,false));
test('rule parse audit is review-only and retains fallback reason',()=>{const r={status:'PARSED',parsed_by:'RULE',fallback_reason:'PROVIDER_TIMEOUT',llm_call:{attempts:1}};assert.equal(parsePresentation(r).audit,null);assert.equal(parsePresentation(r,{review:true}).audit.fallback_reason,'PROVIDER_TIMEOUT');});
test('manual requests use declared SOURCE microseconds and approved defaults',()=>{const q=manualRequest(run,'SYNTHETIC',{startUs:0,endUs:2000000,colorLabel:'red'});assert.equal(checkRequest('q1',q),q);assert.deepEqual(q.condition.color,{label:'red',min_verdict:'STRONG'});assert.equal(q.origin,'MANUAL');assert.equal(q.condition.query_min_score,run.query_defaults.query_min_score);});
test('manual Q2 is appearance and RULE_ONLY by default',()=>{const q=manualRequest(run,'SYNTHETIC',{task:'q2'});assert.equal(checkRequest('q2',q),q);assert.equal(q.seed.kind,'APPEARANCE');assert.equal(q.switch_mode,'RULE_ONLY');});
test('manual unsupported colors/classes and invalid intervals fail closed',()=>{assert.throws(()=>manualRequest(run,'SYNTHETIC',{classLabel:'dragon'}),/UNSUPPORTED_CLASS/);assert.throws(()=>manualRequest(run,'SYNTHETIC',{classLabel:'car',colorLabel:'red'}),/UNSUPPORTED_CONDITION/);assert.throws(()=>manualRequest(run,'SYNTHETIC',{startUs:2,endUs:2}),/REQUEST_TIME/);assert.throws(()=>manualRequest(null,'SYNTHETIC'),/SOURCE_REQUIRED/);});
test('edited request has manual origin, replacement auth, no GT',()=>{const q=manualRequest(run,'SYNTHETIC');q.origin='Q3_PARSED';assert.equal(editedRequest(JSON.stringify(q),'FICT_NEW').origin,'MANUAL');assert.equal(editedRequest(JSON.stringify(q),'FICT_NEW').session_ref,'FICT_NEW');assert.throws(()=>editedRequest(JSON.stringify({...q,gt:{}}),'FICT_NEW'));});
test('text parser requests default rules and declared scope; terms from pinned catalog',()=>{const q=textRequest(run,'SYNTHETIC',' 人 ');assert.equal(q.text,'人');assert.equal(q.parser_mode,'RULE_ONLY');assert.equal(q.context.clock_mapping_sha256,run.clock_mapping.content_sha256);assert.match(vocabulary(run),/person/);assert.match(vocabulary(run),/車 → car/);});
import {intentPresentation} from './q3-bar-model.mjs';
test('Q3 intent tag: derived only from structured_query.schema_version, never from an undefined intent field',()=>{
  assert.equal(intentPresentation(null),null);
  assert.equal(intentPresentation({status:'PARSED',intent:'FIND_PERSON'}).code,'UNKNOWN');// a stray intent field is ignored
  const q1={status:'PARSED',structured_query:{schema_version:'q-demo.q1-request.v1'}},q2={status:'PARSED',structured_query:{schema_version:'q-demo.q2-request.v1'}};
  assert.equal(intentPresentation(q1).short,'找');assert.equal(intentPresentation(q2).short,'追');
  assert.equal(intentPresentation(q1).detail.includes('structured_query'),false);assert.match(intentPresentation(q1,{review:true}).detail,/FIND_CAMERAS.*structured_query/);
  assert.equal(intentPresentation({status:'NEEDS_CLARIFICATION'}),null);assert.equal(intentPresentation({status:'PARSED',structured_query:{}}).code,'UNKNOWN');
});

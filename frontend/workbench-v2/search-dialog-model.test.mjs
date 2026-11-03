import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {parseHms,formatHms,buildSearchRequest} from './search-dialog-model.mjs';

test('H:MM:SS converts to integer microseconds and back',()=>{
  assert.equal(parseHms('0:00:00'),0);
  assert.equal(parseHms('1:02:03'),3723000000);
  assert.equal(parseHms('2:30'),150000000);
  assert.equal(parseHms('45'),45000000);
  assert.equal(parseHms('0:00:01.5'),1500000);
  assert.equal(formatHms(3723000000),'1:02:03');
  assert.equal(formatHms(1500000),'0:00:01.5');
  for(const us of [0,1,999999,50000000,3723000001])assert.equal(parseHms(formatHms(us)),us);
});
test('invalid time text is rejected, never guessed',()=>{
  for(const bad of ['','abc','1:60:00','1:00:60','0:99','-1','1:2:3:4','1.5.2','0:00:00.1234567'])assert.throws(()=>parseHms(bad),/TIME_INVALID/,bad);
  assert.throws(()=>formatHms(-1),/TIME_INVALID/);
});
async function run(){const w=JSON.parse(await readFile(new URL('fixtures/q-bootstrap.json',import.meta.url),'utf8'));return JSON.parse(w.bootstrap_json).runs[0];}
test('condition form builds a Q1 (find) or Q2 (track) request with converted µs',async()=>{
  const r=await run(),form={text:'',classLabel:'person',colorLabel:'',start:'0:00:01',end:'0:00:02'};
  const q1=buildSearchRequest(r,'S',{...form,mode:'find'}),q2=buildSearchRequest(r,'S',{...form,mode:'track'});
  assert.equal(q1.schema_version,'q-demo.q1-request.v1');assert.deepEqual(q1.time.range_us,[1000000,2000000]);
  assert.equal(q2.schema_version,'q-demo.q2-request.v1');assert.deepEqual(q2.time.range_us,[1000000,2000000]);
});
test('feature text takes the Q3 path; bad input throws before anything runs',async()=>{
  const r=await run();
  const t=buildSearchRequest(r,'S',{mode:'find',text:'紅衣的人',start:'x',end:'y'});
  assert.ok(t.schema_version.includes('q3'));
  const base={mode:'find',text:'',classLabel:'person',colorLabel:''};
  assert.throws(()=>buildSearchRequest(r,'S',{...base,start:'0:00:05',end:'0:00:05'}),/TIME_ORDER/);
  assert.throws(()=>buildSearchRequest(r,'S',{...base,start:'bad',end:'0:00:05'}),/TIME_INVALID/);
  assert.throws(()=>buildSearchRequest(null,'S',base),/SOURCE_REQUIRED/);
  assert.throws(()=>buildSearchRequest(r,'S',{...base,mode:'x'}),/MODE_REQUIRED/);
});

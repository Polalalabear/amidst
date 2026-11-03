import test from 'node:test';
import assert from 'node:assert/strict';
import {stampText,setStamp,failStamp} from './cam-stamp.mjs';
test('two decimals, truncated, from source µs',()=>{
  assert.equal(stampText('CAM_ENTRY',12400000),'CAM_ENTRY · 12.40 s');
  assert.equal(stampText('A',5150000),'A · 5.15 s');
  assert.equal(stampText('A',5109999),'A · 5.10 s');
  assert.equal(stampText('A',0),'A · 0.00 s');
});
test('unknown source time shows UNKNOWN, never 0 or blank',()=>{
  for(const bad of [null,undefined,NaN,-1,1.5,'5'])assert.equal(stampText('B',bad),'B · UNKNOWN');
  assert.equal(stampText(undefined,0),'UNKNOWN · 0.00 s');
});
test('each cell keeps its own value',()=>{
  const a={dataset:{}},b={dataset:{}};
  setStamp(a,'A',5100000);setStamp(b,'B',5150000);
  assert.equal(a.dataset.stamp,'A · 5.10 s');assert.equal(b.dataset.stamp,'B · 5.15 s');
  setStamp(a,'A',null);assert.equal(a.dataset.stamp,'A · UNKNOWN');assert.equal(b.dataset.stamp,'B · 5.15 s');
  assert.doesNotThrow(()=>setStamp(null,'A',1));
});
test('failed RGB load clears the stamp to UNKNOWN',()=>{
  const cell={dataset:{stamp:'A · 5.10 s'},textContent:''};
  failStamp(cell,'A','MISSING · RGB 載入失敗');
  assert.equal(cell.textContent,'MISSING · RGB 載入失敗');assert.equal(cell.dataset.stamp,'A · UNKNOWN');
  assert.doesNotThrow(()=>failStamp(null,'A','x'));
});
test('Q1 wall and Q4 evidence views route onerror through failStamp',async()=>{
  const {readFileSync}=await import('node:fs');
  for(const f of ['q1-wall-view.mjs','q4-evidence-view.mjs']){
    const src=readFileSync(new URL(`./${f}`,import.meta.url),'utf8');
    assert.match(src,/img\.onerror=\(\)=>[^;]*failStamp\(/,f);
    assert.doesNotMatch(src,/img\.onerror=\(\)=>\{[^}]*textContent='MISSING/,f);
  }
});

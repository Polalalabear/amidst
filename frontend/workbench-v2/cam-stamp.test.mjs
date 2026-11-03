import test from 'node:test';
import assert from 'node:assert/strict';
import {stampText,setStamp} from './cam-stamp.mjs';
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

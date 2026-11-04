import test from 'node:test';
import assert from 'node:assert/strict';
import {stampText,stampParts,setStamp,failStamp,setStampClock} from './cam-stamp.mjs';
const A4={mapping_kind:'DECLARED_DEMO_CLOCK',timezone:'Asia/Taipei',wall_origin:'2026-11-01T14:00:00+08:00',t0_us:0,rate:1};
test('virtual time = declared start + source time, two decimals truncated, secondary elapsed line + declared tag',()=>{
  setStampClock(A4);
  assert.equal(stampText('CAM_ENTRY',12400000),'CAM_ENTRY · 2026-11-01 14:00:12.40（UTC+8）\n+12.40 s · DECLARED_DEMO_CLOCK');
  assert.equal(stampParts('A',5109999).main,'A · 2026-11-01 14:00:05.10（UTC+8）');
  assert.equal(stampParts('A',0).main,'A · 2026-11-01 14:00:00.00（UTC+8）');
  assert.equal(stampParts('A',65150000).main,'A · 2026-11-01 14:01:05.15（UTC+8）');
  setStampClock({...A4,wall_origin:'2026-11-01T14:10:00+08:00'});assert.equal(stampParts('B',21000000).main,'B · 2026-11-01 14:10:21.00（UTC+8）');
  setStampClock(null);
});
test('no declared clock: the virtual time is UNKNOWN and no date is assumed; elapsed stays as secondary',()=>{
  setStampClock(null);
  assert.equal(stampText('A',5150000),'A · UNKNOWN\n+5.15 s · CLOCK_MAPPING_MISSING');
  assert.equal(stampParts('A',5150000).main,'A · UNKNOWN');
  setStampClock({...A4,timezone:'Not/AZone'});assert.equal(stampParts('A',0).main,'A · UNKNOWN');
  setStampClock(null);
});
test('unknown source time shows UNKNOWN, never 0 or blank',()=>{
  setStampClock(A4);
  for(const bad of [null,undefined,NaN,-1,1.5,'5'])assert.equal(stampText('B',bad),'B · UNKNOWN');
  assert.equal(stampParts(undefined,0).main,'UNKNOWN · 2026-11-01 14:00:00.00（UTC+8）');
  setStampClock(null);
});
test('each cell keeps its own value; the simple text is camera + time only',()=>{
  setStampClock(A4);
  const a={dataset:{}},b={dataset:{}};
  setStamp(a,'A',5100000);setStamp(b,'B',5150000);
  assert.equal(a.dataset.stamp,'A · 2026-11-01 14:00:05.10（UTC+8）\n+5.10 s · DECLARED_DEMO_CLOCK');
  assert.equal(a.dataset.stampSimple,'A · 2026-11-01 14:00:05.10（UTC+8）');assert.equal(b.dataset.stampSimple,'B · 2026-11-01 14:00:05.15（UTC+8）');
  setStamp(a,'A',null);assert.equal(a.dataset.stamp,'A · UNKNOWN');assert.equal(a.dataset.stampSimple,'A · UNKNOWN');assert.equal(b.dataset.stampSimple,'B · 2026-11-01 14:00:05.15（UTC+8）');
  assert.doesNotThrow(()=>setStamp(null,'A',1));
  setStampClock(null);
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

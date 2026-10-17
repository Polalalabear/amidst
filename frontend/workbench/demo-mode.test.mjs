import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {validateSteps,stepAvailability,acceptanceRecord,stateHash,canonicalJSON,stepFromKey,isTypingTarget,exportDocument,demoBarHTML,JUMP_TIMES} from './demo-mode.mjs';

const doc=JSON.parse(readFileSync(new URL('./demo-steps.office.json',import.meta.url),'utf8'));
const subtle=webcrypto.subtle;
const full={sceneId:'blender-office',timestamp:6,cameraIds:['b','a'],demoObservationRef:doc.steps[1].selection,blindHypothesis:{x:1},crossCameraResult:{},recommendedView:{},sceneIds:['n','h'],negativeSceneId:'n',humanoidSceneId:'h'};

test('step definitions are well formed with fixed jump times',()=>{
  assert.deepEqual(validateSteps(doc),[]);
  assert.equal(doc.steps.length,7);
  assert.deepEqual(doc.steps.slice(0,6).map(s=>s.timestamp_s),[0,4.6,6.4,8.2,8.2,8.2]);
  for(const t of JUMP_TIMES)assert.ok(doc.steps.some(s=>s.timestamp_s===t));
  assert.ok(validateSteps({...doc,steps:[{...doc.steps[0],label:'七個字的標籤啊啊'}]}).length>0);
});
test('missing layers are UNAVAILABLE with a reason; MOCK is explicit and never PASS',async()=>{
  const bare={sceneId:'blender-office'};
  for(const i of [0,1,2,3,4,5,6]){const a=stepAvailability(doc.steps[i],bare);assert.equal(a.available,false);assert.ok(a.reason);}
  assert.match(stepAvailability(doc.steps[0],bare).reason,/人形 run 場景尚未註冊/);
  assert.equal(stepAvailability(doc.steps[0],{sceneIds:['h'],humanoidSceneId:'h'}).available,true);
  assert.match(stepAvailability(doc.steps[2],bare).reason,/C4b/);assert.match(stepAvailability(doc.steps[5],bare).reason,/C5/);
  const m=stepAvailability(doc.steps[2],bare,{mock:true});assert.equal(m.mock,true);assert.match(m.reason,/^MOCK/);
  const rec=await acceptanceRecord(doc.steps[2],bare,{availability:m,result:'PASS',subtle});assert.equal(rec.result,'UNKNOWN');assert.equal(rec.mock,true);
  for(const step of doc.steps)assert.equal(stepAvailability(step,full).available,true);
});
test('acceptance record defaults to UNKNOWN and carries hashes',async()=>{
  const rec=await acceptanceRecord(doc.steps[0],full,{subtle});
  assert.equal(rec.result,'UNKNOWN');assert.match(rec.state_hash,/^[0-9a-f]{64}$/);
  assert.equal(rec.data_hashes.scene,'UNKNOWN');assert.match(rec.data_hashes.response,/^[0-9a-f]{64}$/);assert.equal(rec.data_hashes.fixture,'UNKNOWN');
  assert.deepEqual(Object.keys(rec).sort(),['available','data_hashes','expected','label','mock','operator_note','result','state_hash','step','timestamp_s','unavailable_reason']);
  assert.equal((await acceptanceRecord(doc.steps[0],full,{subtle,result:'PASS'})).result,'PASS');
  assert.equal((await acceptanceRecord(doc.steps[0],full,{subtle,result:'bogus'})).result,'UNKNOWN');
  assert.deepEqual(exportDocument('d',[{step:2},{step:1}]).records.map(r=>r.step),[1,2]);
});
test('state hash is stable and key-order independent',async()=>{
  assert.equal(canonicalJSON({b:1,a:[{d:1,c:2}]}),canonicalJSON({a:[{c:2,d:1}],b:1}));
  const h1=await stateHash({a:1,b:{c:2,d:3}},subtle),h2=await stateHash({b:{d:3,c:2},a:1},subtle);
  assert.equal(h1,h2);assert.notEqual(h1,await stateHash({a:2,b:{c:2,d:3}},subtle));
  const a=await acceptanceRecord(doc.steps[0],full,{subtle}),b=await acceptanceRecord(doc.steps[0],{...full,cameraIds:['a','b']},{subtle});
  assert.equal(a.state_hash,b.state_hash);
});
test('number keys jump only outside text inputs',()=>{
  const ev=(key,target={tagName:'DIV'},extra={})=>({key,target,...extra});
  assert.equal(stepFromKey(ev('3'),7),3);assert.equal(stepFromKey(ev('7'),7),7);
  assert.equal(stepFromKey(ev('0'),7),null);assert.equal(stepFromKey(ev('8'),7),null);assert.equal(stepFromKey(ev('a'),7),null);
  for(const tagName of ['INPUT','TEXTAREA','SELECT'])assert.equal(stepFromKey(ev('2',{tagName}),7),null);
  assert.equal(stepFromKey(ev('2',{tagName:'DIV',isContentEditable:true}),7),null);
  assert.equal(stepFromKey(ev('2',{tagName:'DIV'},{ctrlKey:true}),7),null);assert.equal(isTypingTarget(null),false);
});
test('bar shows UNAVAILABLE reason and MOCK state',()=>{
  const html=demoBarHTML({steps:doc.steps,current:3,availability:stepAvailability(doc.steps[2],{}),mock:false,records:new Map()});
  assert.match(html,/data-demo-availability="UNAVAILABLE"/);assert.match(html,/C4b/);assert.match(html,/data-demo-export/);
  assert.match(demoBarHTML({steps:doc.steps,current:3,availability:stepAvailability(doc.steps[2],{},{mock:true}),mock:true,records:new Map()}),/data-demo-availability="MOCK"/);
});

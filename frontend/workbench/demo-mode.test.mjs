import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {validateSteps,stepAvailability,acceptanceRecord,stateHash,canonicalJSON,stepFromKey,isTypingTarget,exportDocument,demoBarHTML,JUMP_TIMES,stepsForGroup,watermarkVisible,findObservation,demoState,installDemoMode,blindAutoSelection,reachableAreaM2,areaComparison,demoBlindRequest,runDemoBlind,ensureDemoBlind,demoNotes,NO_EXCLUSION_TEXT} from './demo-mode.mjs';

const doc=JSON.parse(readFileSync(new URL('./demo-steps.office.json',import.meta.url),'utf8'));
const subtle=webcrypto.subtle;
const full={sceneId:'blender-office',timestamp:6,cameraIds:['b','a'],physicalReviewResult:{synchronized_evidence:{samples:[{observation_ref:doc.steps[1].selection,timestamp:4.6,camera_id:'CAM_1F_AUDITORIUM_FRONT'}]}},demoObservationRef:null,blindHypothesis:{status:'READY'},demoBlindRuns:{sceneId:'blender-office',NONE:{sha:'a'.repeat(64),area_m2:281.125,plan:{status:'READY'}},BASELINE:{sha:'b'.repeat(64),area_m2:281.125,plan:{status:'READY'}}},recommendedView:{},sceneIds:['n','h'],negativeSceneId:'n',humanoidSceneId:'h'};

test('step definitions are well formed with fixed jump times',()=>{
  assert.deepEqual(validateSteps(doc),[]);
  assert.deepEqual(doc.steps.map(s=>s.key),['play_both','front_select','blind_bundle','rear_reappear','suggested_wall','negative_case']);
  assert.ok(!doc.steps.some(s=>s.key==='candidate_switch'),'D22');assert.match(doc.note_d22_d24,/K8e/);
  assert.deepEqual(doc.steps.slice(0,5).map(s=>s.timestamp_s),[0,4.6,6.4,8.2,8.2]);
  assert.deepEqual(doc.steps.filter(s=>s.blind_mode).map(s=>s.blind_mode),['NONE','BASELINE']);
  for(const t of JUMP_TIMES)assert.ok(doc.steps.some(s=>s.timestamp_s===t));
  assert.ok(validateSteps({...doc,steps:[{...doc.steps[0],label:'七個字的標籤啊啊'}]}).length>0);
});
test('missing layers are UNAVAILABLE with a reason; MOCK is explicit and never PASS',async()=>{
  const bare={sceneId:'blender-office'};
  for(const i of [0,1,2,3,4,5]){const a=stepAvailability(doc.steps[i],bare);assert.equal(a.available,false);assert.ok(a.reason);}
  assert.match(stepAvailability(doc.steps[0],bare).reason,/人形場景未載入（需 Demo presets）/);
  assert.equal(stepAvailability(doc.steps[0],{sceneIds:['h'],humanoidSceneId:'h'}).available,true);
  assert.match(stepAvailability(doc.steps[2],bare).reason,/盲區假設資料/);
  const wallOnly=stepAvailability(doc.steps[4],{...full,recommendedView:null});assert.equal(wallOnly.available,true);assert.equal(wallOnly.partial[0].part,'recommended_view');assert.match(wallOnly.partial[0].reason,/C5/);
  assert.equal((await acceptanceRecord(doc.steps[4],{...full,recommendedView:null},{subtle,result:'PASS'})).result,'UNKNOWN');
  const m=stepAvailability(doc.steps[2],bare,{mock:true});assert.equal(m.mock,true);assert.match(m.reason,/^MOCK/);
  const rec=await acceptanceRecord(doc.steps[2],bare,{availability:m,result:'PASS',subtle});assert.equal(rec.result,'UNKNOWN');assert.equal(rec.mock,true);
  for(const step of doc.steps)assert.equal(stepAvailability(step,full).available,true);
  assert.equal(stepAvailability(doc.steps[4],full).partial.length,0);
});
test('acceptance record defaults to UNKNOWN and carries hashes',async()=>{
  const rec=await acceptanceRecord(doc.steps[0],full,{subtle});
  assert.equal(rec.result,'UNKNOWN');assert.match(rec.state_hash,/^[0-9a-f]{64}$/);
  assert.equal(rec.data_hashes.scene,'UNKNOWN');assert.match(rec.data_hashes.response,/^[0-9a-f]{64}$/);assert.equal(rec.data_hashes.fixture,'UNKNOWN');
  assert.deepEqual(Object.keys(rec).sort(),['available','blind_runs','data_hashes','expected','label','mock','operator_note','result','state_hash','step','step_group','timestamp_s','unavailable_parts','unavailable_reason']);
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
  assert.match(html,/data-demo-availability="UNAVAILABLE"/);assert.match(html,/盲區假設資料/);assert.match(html,/data-demo-export/);
  assert.match(demoBarHTML({steps:doc.steps,current:3,availability:stepAvailability(doc.steps[2],{},{mock:true}),mock:true,records:new Map()}),/data-demo-availability="MOCK"/);
});

test('watermark display follows the MOCK switch, not the hidden attribute',()=>{
  const mark={hidden:true,style:{display:'flex'}};
  watermarkVisible(mark,false);assert.equal(mark.style.display,'none');
  watermarkVisible(mark,true);assert.equal(mark.style.display,'flex');assert.equal(mark.hidden,false);
  watermarkVisible(mark,false);watermarkVisible(mark,true);watermarkVisible(mark,false);assert.equal(mark.style.display,'none');
});
test('legacy step group uses legacy_run scene/times/selection and is still gated by real data',async()=>{
  const legacy=stepsForGroup(doc,'legacy'),main=stepsForGroup(doc,'humanoid');
  assert.deepEqual(legacy.slice(0,5).map(s=>s.timestamp_s),[0,4.4,6.0,8.6,8.6]);
  assert.ok(legacy.slice(0,5).every(s=>s.scene_id==='blender-office'&&s.group==='legacy'));
  assert.equal(legacy[1].selection,'observation:add9f687d311742321e80dff');assert.equal(main[1].selection,'observation:218abc805d72fe39c4496da0');
  assert.deepEqual(validateSteps({...doc,steps:legacy}),[]);
  const state={sceneId:'blender-office',sceneIds:['blender-office']};
  assert.equal(stepAvailability(legacy[0],state).available,true);
  assert.match(stepAvailability(legacy[2],state).reason,/盲區假設資料/);assert.match(stepAvailability(legacy[4],state).reason,/BASELINE/);
  assert.match(stepAvailability(main[0],state).reason,/人形場景未載入（需 Demo presets）/);
  const a=await acceptanceRecord(legacy[0],state,{subtle}),b=await acceptanceRecord({...legacy[0],group:'humanoid'},state,{subtle});
  assert.equal(a.step_group,'legacy');assert.notEqual(a.state_hash,b.state_hash);
  assert.equal(exportDocument('d',[],'legacy').step_group,'legacy');
  assert.match(demoBarHTML({steps:legacy,current:1,availability:{available:true},mock:false,records:new Map(),group:'legacy'}),/<option value="legacy" selected>舊 run（備援）/);
  assert.match(demoBarHTML({steps:main,current:1,availability:{available:true},mock:false,records:new Map()}),/<option value="humanoid" selected>人形（主線）/);
});

test('selection availability comes from loaded observations, not the backend demo field',async()=>{
  const step=doc.steps[1],ref=step.selection;
  const state=(extra={})=>({sceneId:'h',sceneIds:['h'],humanoidSceneId:'h',...extra});
  const sample={observation_ref:ref,timestamp:4.6,camera_id:'CAM_1F_AUDITORIUM_FRONT'};
  const present=state({physicalReviewResult:{synchronized_evidence:{samples:[sample]}},demoObservationRef:null});
  assert.equal(stepAvailability(step,present).available,true);
  assert.equal(findObservation(present,step).camera_id,'CAM_1F_AUDITORIUM_FRONT');
  assert.equal(stepAvailability(step,state({observations:[{observation_ref:ref,time_range:[4.4,4.8],camera_ids:['CAM_1F_AUDITORIUM_FRONT']}]})).available,true);
  const absent=stepAvailability(step,state({demoObservationRef:ref,observations:[]}));
  assert.equal(absent.available,false);assert.match(absent.reason,new RegExp(`觀測 ${ref} 在 blender-office-person@4.6s 不存在`));
  const wrongTime=stepAvailability(step,state({physicalReviewResult:{synchronized_evidence:{samples:[{...sample,timestamp:5.0}]}}}));
  assert.equal(wrongTime.available,false);
  const a=await acceptanceRecord(step,present,{subtle}),b=await acceptanceRecord(step,state({demoObservationRef:ref}),{subtle});
  assert.notEqual(a.state_hash,b.state_hash);
});

test('blind hypothesis step needs a READY nested plan; UNKNOWN or absent is UNAVAILABLE with a reason',()=>{
  const step=doc.steps[2],base={sceneId:'blender-office-person',sceneIds:['blender-office-person'],humanoidSceneId:'blender-office-person'};
  assert.equal(doc.humanoid_scene_id,'blender-office-person');assert.ok(doc.steps.slice(0,5).every(s=>s.scene_id==='blender-office-person'));
  assert.equal(stepAvailability(step,{...base,blindHypothesis:{status:'READY'}}).available,true);
  const unknown=stepAvailability(step,{...base,blindHypothesis:{status:'UNKNOWN',reasonText:'端點不可用'}});
  assert.equal(unknown.available,false);assert.match(unknown.reason,/UNKNOWN.*端點不可用/);
  assert.match(stepAvailability(step,base).reason,/尚無盲區假設資料/);
  assert.match(stepAvailability(doc.steps[0],{sceneIds:['blender-office']}).reason,/人形場景未載入/);
});

test('installDemoMode feeds humanoidSceneId from the step file (missing it marks every humanoid step unloaded)',async()=>{
  const appState={sceneId:'blender-office-person',sceneIds:['blender-office-person'],timestamp:0};
  assert.equal(demoState(doc,appState).humanoidSceneId,doc.humanoid_scene_id);
  assert.equal(stepAvailability(doc.steps[0],demoState(doc,appState)).available,true);
  assert.equal(stepAvailability(doc.steps[0],appState).available,false);
  const listeners={},mk=()=>({style:{},append(){},addEventListener(t,f){listeners[t]=f;},setAttribute(){},hasAttribute:()=>false});
  const bar=mk(),mark=mk();const els=[bar,mark];
  const fake={createElement:()=>els.shift(),body:{append(){}},addEventListener(){}};
  const demo=installDemoMode({document:fake,doc,getState:()=>appState,goto:async()=>{}});
  await demo.jump(1);
  assert.match(bar.innerHTML,/data-demo-availability="AVAILABLE"/);
});

test('step 3 auto-load scope: only steps that need blind hypotheses, full scene range, no fabricated selection',()=>{
  const snap={time_range:[0,9.8]};
  assert.deepEqual(blindAutoSelection(snap,doc.steps[2]),{camera_ids:doc.steps[2].camera_ids,start:0,end:9.8,top_k:3});
  assert.equal(blindAutoSelection(snap,doc.steps[0]),null);assert.equal(blindAutoSelection(snap,doc.steps[3]),null);
  assert.equal(blindAutoSelection({},doc.steps[2]),null);assert.equal(blindAutoSelection(snap,{...doc.steps[2],selection:null}),null);
});

const SHA_N='1'.repeat(64),SHA_B='2'.repeat(64);
const resp=(sha,areas,status='READY')=>({status:'UNKNOWN',blind_hypotheses:{schema_version:'workbench.blind-hypothesis.v1',status,output_sha256:sha,reachable_regions:areas.map((a,i)=>({timestamp_s:5+i,area_m2:a}))}});
test('reachable area is summed from the response, never hard-coded; missing or non-finite is null',()=>{
  assert.equal(reachableAreaM2(resp(SHA_N,[100.5,50.25])),150.75);
  assert.equal(reachableAreaM2(resp(SHA_N,[])),null);assert.equal(reachableAreaM2(resp(SHA_N,[1,null])),null);assert.equal(reachableAreaM2({}),null);
});
test('area comparison reports the real difference; zero difference says there was not enough exclusion evidence',()=>{
  const same=areaComparison({area_m2:281.125},{area_m2:281.125});
  assert.equal(same.state,'SAME');assert.equal(same.delta_m2,0);assert.ok(same.text.includes(NO_EXCLUSION_TEXT));assert.match(same.text,/281\.125 m².*281\.125 m²/);
  const changed=areaComparison({area_m2:200},{area_m2:150});
  assert.equal(changed.state,'CHANGED');assert.equal(changed.delta_m2,-50);assert.equal(changed.delta_pct,-25);assert.ok(!changed.text.includes(NO_EXCLUSION_TEXT));assert.match(changed.text,/-50\.000 m².*-25\.0%/);
  assert.equal(areaComparison({area_m2:1},null).state,'UNKNOWN');assert.equal(areaComparison(null,null).delta_m2,null);
});
test('requests: NONE is explicit; BASELINE carries the NONE output_sha256 and cannot be built without it',()=>{
  const sel={camera_ids:['a','b'],start:0,end:9.8,top_k:3},ref='observation:218abc805d72fe39c4496da0';
  const none=demoBlindRequest('s',sel,ref,{mode:'NONE'});assert.equal(none.negative_evidence_mode,'NONE');assert.ok(!('previous_response_sha256' in none));
  const base=demoBlindRequest('s',sel,ref,{mode:'BASELINE',previousSha256:SHA_N});assert.equal(base.negative_evidence_mode,'BASELINE');assert.equal(base.previous_response_sha256,SHA_N);
  assert.throws(()=>demoBlindRequest('s',sel,ref,{mode:'BASELINE'}));assert.throws(()=>demoBlindRequest('s',sel,ref,{mode:'BASELINE_AND_FEEDBACK'}));
});
test('ensureDemoBlind: step 3 sends one NONE request; step 5 sends BASELINE with the NONE hash and shows the comparison',async()=>{
  const sent=[],send=async r=>{sent.push(r);return r.negative_evidence_mode==='NONE'?resp(SHA_N,[281.125]):resp(SHA_B,[281.125]);};
  const target={sceneId:'blender-office-person',sceneEpoch:1,blindHypothesis:null};
  const sel={camera_ids:['a','b'],start:0,end:9.8,top_k:3};
  const step3=doc.steps[2],step5=doc.steps[4];
  assert.equal(await ensureDemoBlind(target,step3,sel,send),true);
  assert.deepEqual(sent.map(r=>r.negative_evidence_mode),['NONE']);assert.equal(target.demoBlindRuns.NONE.area_m2,281.125);assert.equal(target.blindHypothesisSha256,SHA_N);
  assert.match(demoNotes(step3,target),/NONE 可達面積 281\.125 m²/);
  await ensureDemoBlind(target,step5,sel,send);
  assert.deepEqual(sent.map(r=>r.negative_evidence_mode),['NONE','BASELINE']);assert.equal(sent[1].previous_response_sha256,SHA_N);
  assert.equal(target.blindHypothesisSha256,SHA_B);assert.ok(demoNotes(step5,target).includes(NO_EXCLUSION_TEXT));
  await ensureDemoBlind(target,step3,sel,send);assert.equal(sent.length,2,'existing runs are reused');assert.equal(target.blindHypothesisSha256,SHA_N);
  assert.equal(stepAvailability(step5,{...target,sceneIds:['blender-office-person'],humanoidSceneId:'blender-office-person'}).available,false,'BASELINE plan is not READY here: stub plan');
});
test('a stale reply (scene changed) is dropped and a failed request leaves nothing stored',async()=>{
  const target={sceneId:'x',sceneEpoch:1};
  const sel={camera_ids:['a','b'],start:0,end:9.8,top_k:3},ref=doc.steps[2].selection;
  const late=runDemoBlind(target,sel,ref,'NONE',async()=>{target.sceneEpoch=2;return resp(SHA_N,[1]);});
  assert.equal(await late,false);assert.ok(!target.demoBlindRuns.NONE);
  await assert.rejects(runDemoBlind(target,sel,ref,'NONE',async()=>{throw new Error('boom');}));assert.equal(target.blindHypothesisPending,false);assert.ok(!target.demoBlindRuns.NONE);
});

test('hint follows the step count; loading shows 載入中 instead of an error-like reason',()=>{
  const bare=demoBarHTML({steps:doc.steps,current:0,availability:{available:false,reason:null},mock:false,records:new Map()});
  assert.match(bare,new RegExp(`按 1–${doc.steps.length}`));assert.ok(!bare.includes('1–7'));
  const wait=stepAvailability(doc.steps[4],{sceneId:'x'},{loading:true});
  assert.equal(wait.pending,true);assert.equal(wait.reason,'載入中…');
  assert.match(demoBarHTML({steps:doc.steps,current:5,availability:wait,mock:false,records:new Map()}),/data-demo-availability="PENDING"[^>]*>載入中/);
  assert.ok(!demoBarHTML({steps:doc.steps,current:5,availability:wait,mock:false,records:new Map()}).includes('尚無 BASELINE'));
  assert.equal(stepAvailability(doc.steps[4],{sceneId:'x'}).pending,undefined);
});
test('installDemoMode shows 載入中 while goto runs and redraws on demo-redraw; jumping to step 5 first fills NONE then BASELINE',async()=>{
  const appState={sceneId:'blender-office-person',sceneIds:['blender-office-person'],timestamp:0};
  const listeners={},mk=()=>({style:{},append(){},addEventListener(t,f){listeners[t]=f;},setAttribute(){},hasAttribute:()=>false});
  const bar=mk(),mark=mk(),els=[bar,mark];
  const fake={createElement:()=>els.shift(),body:{append(){}},addEventListener(t,f){listeners[t]=f;}};
  let during=null;
  const demo=installDemoMode({document:fake,doc,getState:()=>appState,goto:async()=>{during=bar.innerHTML;}});
  await demo.jump(5);
  assert.match(during,/data-demo-availability="PENDING"/);assert.ok(!during.includes('尚無 BASELINE'));assert.ok(!during.includes('可達面積對照 UNKNOWN'));
  assert.match(bar.innerHTML,/data-demo-availability="UNAVAILABLE"/);
  appState.demoBlindRuns={sceneId:'blender-office-person',BASELINE:{plan:{status:'READY'}}};listeners['demo-redraw']();
  assert.match(bar.innerHTML,/data-demo-availability="AVAILABLE"/);
});

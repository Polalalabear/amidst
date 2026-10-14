import test from 'node:test';
import assert from 'node:assert/strict';
import {Phase2SuitePanel,validateSuiteContext,validateAgentCase,validateSuiteWindow,agentResultHTML,
  answerEvidenceHTML,researchDiagnosticsHTML,associationDiagnosticsHTML,repair05DiagnosticsHTML} from './phase2-suite.mjs';

const hash='a'.repeat(64),snapshot={scene_id:'s',run_id:'r',source_hash:hash};
const binding={scene_id:'s',run_id:'r',run_ref:'run:1',source_ref:'source:1',source_sha256:hash,
  freeze_ref:'freeze:1',product_freeze_ref:'freeze:2',config_sha256:hash,
  observation_mode:'photos_plus_observations',decision_stage:'RESULTS'};
const context={schema_version:'workbench.phase2-suite.v1',scene_id:'s',source_run_id:'r',source_sha256:hash,
  research:{binding:{scene_id:'s',source_run_id:'r',source_sha256:hash}},agent:{binding},storage:{backend:'POSTGRESQL'}};
const record={schema_version:'local.agent.case.v1',agent_ref:'agent:1',binding,state:'READY',recovery_token:'secret-not-for-display',tool_receipts:[]};
test('scene/run/source and actual database backend are all required',()=>{
  assert.equal(validateSuiteContext(snapshot,context),context);
  for(const altered of [{...context,scene_id:'other'},{...context,source_sha256:'b'.repeat(64)},
    {...context,agent:{binding:{...binding,run_id:'other'}}},{...context,storage:{backend:'SQLITE'}}])
    assert.throws(()=>validateSuiteContext(snapshot,altered));
});
test('repair05 source and mode cannot be replaced by the older research freeze',()=>{
  const repair05={binding:{scene_id:'s',source_run_id:'r',source_sha256:hash,mode:'photos_only',freeze_ref:'repair'}};
  assert.equal(validateSuiteContext(snapshot,{...context,agent:null,research:null,repair05,observation_mode:'photos_only'}).repair05,repair05);
  assert.throws(()=>validateSuiteContext(snapshot,{...context,repair05,observation_mode:'photos_plus_observations'}));
  assert.throws(()=>validateSuiteContext(snapshot,{...context,repair05:{binding:{...repair05.binding,source_sha256:'b'.repeat(64)}}}));
});
test('fixed repair05 candidate keeps failed gates, original population and baseline visible',()=>{
  const row=(switches,mixed)=>({pixels_and_local_identity:{within_local_track_id_switches:switches,measurement_count:150,bounded_labeled_measurements:144,eligible_visible_actor_contacts:160},
    pixel_population:{mixed_known_identity_tracks:mixed,fragmented_track_count:7,single_measurement_track_count:6},
    continuity_audit:{internal_missing_sample_count:11,noninitial_new_track_decisions:19,actor_track_membership_count:23,alternative_contact_count:20,unlabeled_contact_count:6}});
  const html=repair05DiagnosticsHTML({status:'CERTIFIED_AGGREGATE',evaluation:{variants:{baseline:{photos_only:row(4,3)},candidate:{photos_only:row(3,2)}}}},'photos_only');
  assert.ok(html.includes('尚未通過品質門檻'));assert.ok(html.includes('使用中仍為 baseline'));
  assert.ok(html.includes('144／160'));assert.ok(html.includes('150'));assert.ok(html.includes('首採樣後新軌決策'));
  assert.ok(html.includes('不是新合成封存測試集'));assert.ok(!html.includes('精度已達標'));
});
test('late case from another freeze or mode is rejected',()=>{
  assert.equal(validateAgentCase(context,record,'photos_plus_observations'),record);
  for(const field of ['scene_id','run_ref','source_sha256','freeze_ref','product_freeze_ref','config_sha256','decision_stage'])
    assert.throws(()=>validateAgentCase(context,{...record,binding:{...binding,[field]:'other'}},'photos_plus_observations'));
  assert.throws(()=>validateAgentCase(context,record,'photos_only'));
});
test('only a finite source-bound time window can be submitted',()=>{
  assert.deepEqual(validateSuiteWindow(1,5,[0,8]),[1,5]);
  for(const window of [[-1,5],[5,1],[1,Infinity],[0,121],[0,NaN]])assert.throws(()=>validateSuiteWindow(...window,[0,150]));
});
test('answers and receipt text are escaped; credentials never render',()=>{
  const html=agentResultHTML({...record,answer:{text:'<script>alert(1)</script>',citations:['receipt:1']},
    tool_receipts:[{receipt_ref:'receipt:1',tool:'query_events',result:{support_state:'UNKNOWN'}}]});
  assert.ok(html.includes('&lt;script&gt;'));assert.ok(html.includes('UNKNOWN'));
  assert.ok(!html.includes(record.recovery_token));assert.ok(!html.includes('<script>'));
});
test('truncated evidence remains visible when a completed model answer omits that caveat',()=>{
  const answer={text:'原始事件代碼與候選數字',citations:['receipt:1']};
  const html=agentResultHTML({...record,state:'COMPLETED',answer,
    tool_receipts:[{receipt_ref:'receipt:1',tool:'query_events',result:{data:{retrieval:{truncated:true}}}}]});
  assert.ok(html.includes('不代表全部事件'));assert.ok(html.includes('未定候選與身分限制'));
  assert.ok(!agentResultHTML({...record,answer}).includes('不代表全部事件'));
});
test('verified DTO fields preserve uncertainty and never turn an unexhausted page into a known total',()=>{
  const answer={schema_version:'local.agent.answer.v2',verification:{status:'VERIFIED_DTO_FIELDS'},
    rows:[{resource_ref:'event:1',receipt_ref:'receipt:1',fields:{kind:'INFERRED_GAP_ALTERNATIVES',candidate_count:2,uncertainty:.7,complete:false}}],
    coverage:{complete_for_selected_scope:true,collections:[{returned_count:3,selected_count:1,
      source_truncated:true,presentation_truncated:true,cursor_chain_complete:false,registered_total:36}]}};
  const html=agentResultHTML({...record,state:'COMPLETED',answer});
  assert.ok(html.includes('來源欄位已核對'));assert.ok(html.includes('INFERRED_GAP_ALTERNATIVES'));
  assert.ok(html.includes('0.7'));assert.ok(html.includes('此紀錄內容完整性'));
  assert.ok(html.includes('完整登錄分母 UNKNOWN'));assert.ok(html.includes('有截斷'));
  assert.ok(!html.includes('此為舊版'));assert.ok(!html.includes('全部事件'));
  answer.coverage.collections[0].cursor_chain_complete=true;
  assert.ok(answerEvidenceHTML(answer).includes('完整登錄分母 36'));
});
test('unverified historical answers cannot acquire a verified title and verified strings are escaped',()=>{
  const old=agentResultHTML({...record,state:'COMPLETED',answer:{text:'legacy'}});
  assert.ok(old.includes('舊版未核對'));assert.ok(!old.includes('流程完成・來源欄位已核對'));
  const answer={schema_version:'local.agent.answer.v2',verification:{status:'LEGACY_UNVERIFIED'},rows:[]};
  assert.equal(answerEvidenceHTML(answer),'');answer.verification.status='VERIFIED_DTO_FIELDS';
  answer.rows=[{fields:{kind:'<script>alert(1)</script>'}}];
  const html=answerEvidenceHTML(answer);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));
  assert.ok(agentResultHTML({...record,state:'REFUSED',refusal:{text:'This request cannot be supported.'}}).includes('已安全拒絕'));
});
test('request completion is distinct from literal verification and prior execution remains readonly',()=>{
  const answer={schema_version:'local.agent.answer.v2',verification:{status:'VERIFIED_DTO_FIELDS'},rows:[],
    requirement_verification:{status:'EXPLICIT_REQUEST_CONSTRAINTS_VERIFIED'}};
  const current={...record,state:'COMPLETED',can_continue:true,execution_version:'typed.evidence.v3',
    goal_completion_verification:'EXPLICIT_REQUEST_CONSTRAINTS_VERIFIED',answer};
  assert.ok(agentResultHTML(current).includes('來源與需求條件已核對'));
  const old={...current,can_continue:false,execution_version:'typed.evidence.v2',goal_completion_verification:'NOT_CHECKED'};
  const html=agentResultHTML(old);
  assert.ok(html.includes('歷史結果・來源欄位已核對'));
  assert.ok(html.includes('原需求完成條件未依目前規則核對'));
  assert.ok(!html.includes('來源與需求條件已核對'));
  assert.ok(!agentResultHTML({...current,goal_completion_verification:'NOT_CHECKED'}).includes('來源與需求條件已核對'));
});
function panel(call){
  const nodes=new Map(),q=selector=>{if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',textContent:'',disabled:false,hidden:false});return nodes.get(selector);};
  const ui=Object.create(Phase2SuitePanel.prototype);
  Object.assign(ui,{container:{querySelector:q},call,context,snapshot,record,mode:'photos_plus_observations',
    epoch:0,agentEpoch:0,closed:false,pollTimer:null,busy:false});return ui;
}
test('demo examples only fill the request and preserve the selected scope and current case',()=>{
  const ui=panel(()=>assert.fail('a demo example must not call the model'));
  ui.q('[data-agent-camera]').value='camera:chosen';ui.q('[data-agent-start]').value='8';ui.q('[data-agent-end]').value='16';
  ui.applyDemo('events_en');assert.match(ui.q('[data-agent-message]').value,/first page/);
  assert.equal(ui.q('[data-agent-camera]').value,'camera:chosen');assert.equal(ui.q('[data-agent-start]').value,'8');
  assert.equal(ui.q('[data-agent-end]').value,'16');assert.equal(ui.record,record);
  ui.applyDemo('clarify_zh');assert.match(ui.q('[data-agent-message]').value,/那個人/);
  const old=ui.q('[data-agent-message]').value;ui.applyDemo('__proto__');assert.equal(ui.q('[data-agent-message]').value,old);
});
test('reopening a saved case restores its bound camera, window and original goal without new inference',async()=>{
  const saved={...record,state:'COMPLETED',camera_refs:['camera:chosen'],time_range:[8,16],goal:{original_request:'Original registered event request'}};
  const actions=[],ui=panel(async action=>{actions.push(action);return saved;});
  await ui.open(saved.agent_ref);
  assert.deepEqual(actions,['suite_agent_get']);assert.equal(ui.q('[data-agent-camera]').value,'camera:chosen');
  assert.equal(ui.q('[data-agent-start]').value,8);assert.equal(ui.q('[data-agent-end]').value,16);
  assert.equal(ui.q('[data-agent-message]').value,saved.goal.original_request);
});
test('a response after scene disposal cannot update the panel',async()=>{
  let resolve;const pending=new Promise(done=>{resolve=done;});const ui=panel(()=>pending);
  const request=ui.request('agent_get',{agent_ref:'agent:1'});ui.dispose();resolve(record);
  await assert.rejects(request,/SESSION_CHANGED/);
});
test('stopping invalidates old polling and does not auto-advance',async()=>{
  const calls=[];const ui=panel(async(action)=>{calls.push(action);return {...record,state:'STOPPED'};});
  const before=ui.agentEpoch;await ui.control('stop');assert.ok(ui.agentEpoch>before);
  assert.equal(ui.record.state,'STOPPED');assert.deepEqual(calls,['suite_agent_stop']);
  await ui.poll(before);assert.deepEqual(calls,['suite_agent_stop']);ui.dispose();
});
test('legacy cases remain readable without automatically driving or enabling continuation',async()=>{
  const ui=panel(()=>assert.fail('legacy execution must not advance'));const legacy={...record,state:'READY',can_continue:false};
  ui.accept(legacy);await ui.drive();assert.equal(ui.q('[data-agent-stop]').disabled,true);
  assert.equal(ui.q('[data-agent-resume]').disabled,true);assert.equal(ui.q('[data-agent-reply]').hidden,true);
  assert.ok(ui.q('[data-agent-result]').innerHTML.includes('舊版執行契約'));ui.dispose();
});
test('immediate resume waits only after revalidating the owner-bound current model case',async()=>{
  let busy=true;const calls=[];
  const ui=panel(async(action)=>{
    calls.push(action);
    if(action==='suite_agent_advance'&&busy)throw Object.assign(Error('safe generic refusal'),{code:'INVALID_OR_STALE_REQUEST'});
    return {...record,model_version_current:true,state:action==='suite_agent_advance'?'RUNNING':'READY'};
  });
  await ui.drive();assert.equal(ui.record.waiting_for_model,true);assert.ok(ui.pollTimer);
  assert.deepEqual(calls,['suite_agent_advance','suite_agent_get']);
  busy=false;clearTimeout(ui.pollTimer);await ui.poll(ui.agentEpoch);
  assert.equal(ui.record.state,'RUNNING');assert.deepEqual(calls.slice(-2),['suite_agent_get','suite_agent_advance']);ui.dispose();
});
test('busy recovery never retries changed models, foreign freezes or other refusal codes',async()=>{
  for(const latest of [{...record,model_version_current:false},
    {...record,model_version_current:true,binding:{...binding,freeze_ref:'foreign'}}]){
    const ui=panel(async(action)=>{
      if(action==='suite_agent_advance')throw Object.assign(Error('refused'),{code:'INVALID_OR_STALE_REQUEST'});
      return latest;
    });
    await assert.rejects(ui.drive());assert.equal(ui.pollTimer,null);ui.dispose();
  }
  const calls=[];const ui=panel(async action=>{calls.push(action);throw Object.assign(Error('refused'),{code:'STUDY_MANUAL_ASSISTANCE_DENIED'});});
  await assert.rejects(ui.drive());assert.deepEqual(calls,['suite_agent_advance']);ui.dispose();
});
test('old owner or freeze response cannot be accepted from history',async()=>{
  const ui=panel(async()=>({...record,binding:{...binding,run_ref:'other'}}));
  await assert.rejects(ui.open('agent:1'),/凍結版本/);assert.equal(ui.record,record);ui.dispose();
});
test('paired association table requires both same pool and same denominators',()=>{
  const g={candidate_pool_sha256:hash,eligible_query_count:20,true_link_count:84,
    identity_candidate_recall_at_k:{1:.65,3:.9,5:1},pair_level_false_merge_count:5,pair_level_missed_link_count:71,unresolved_link_count:9};
  const row={association_feature_ablations:{full:g,without_appearance:{...g}}};
  assert.ok(associationDiagnosticsHTML(row).includes('<table>'));
  for(const field of ['candidate_pool_sha256','eligible_query_count','true_link_count']){
    row.association_feature_ablations.without_appearance={...g,[field]:'different'};
    assert.ok(!associationDiagnosticsHTML(row).includes('<table>'));
  }
});
test('diagnostic table preserves requested mode and labels rejected accuracy experiment',()=>{
  const row=n=>({pixels_and_local_identity:{within_local_track_id_switches:n},pixel_population:{fragmented_track_count:7}});
  const result={status:'CERTIFIED_AGGREGATE',evaluation:{variants:{baseline:{photos_only:row(111),photos_plus_observations:row(222)},selected:{photos_only:row(333),photos_plus_observations:row(444)}}}};
  const html=researchDiagnosticsHTML(result,'photos_only');
  const table=html.split('</table>')[0];
  assert.ok(table.includes('111')&&table.includes('333'));assert.ok(!table.includes('222')&&!table.includes('444'));
  assert.ok(html.includes('尚未達可接受'));assert.ok(html.includes('並非新的密封'));
});

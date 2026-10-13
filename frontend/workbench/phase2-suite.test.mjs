import test from 'node:test';
import assert from 'node:assert/strict';
import {Phase2SuitePanel,validateSuiteContext,validateAgentCase,validateSuiteWindow,agentResultHTML,
  researchDiagnosticsHTML,associationDiagnosticsHTML} from './phase2-suite.mjs';

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
function panel(call){
  const nodes=new Map(),q=selector=>{if(!nodes.has(selector))nodes.set(selector,{innerHTML:'',textContent:'',disabled:false,hidden:false});return nodes.get(selector);};
  const ui=Object.create(Phase2SuitePanel.prototype);
  Object.assign(ui,{container:{querySelector:q},call,context,snapshot,record,mode:'photos_plus_observations',
    epoch:0,agentEpoch:0,closed:false,pollTimer:null,busy:false});return ui;
}
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

import test from 'node:test';
import assert from 'node:assert/strict';
import {invalidatePhysicalReview,physicalReviewRequestIsCurrent,runPhysicalReviewLoad,runPhysicalReviewSave} from './physical-review-flow.mjs';

const itemRef='review-item:'+'a'.repeat(24),checkRef='review-check:'+'b'.repeat(24),reviewSha='e'.repeat(64);
const binding={source_sha256:'c'.repeat(64),site_id:'office',run_id:'SUBSTITUTE_RUN',clock_id:'SUBSTITUTE_CLOCK',dataset_sha256:'d'.repeat(64)};
const snapshot={source_binding:binding,time_range:[0,4],cameras:[{camera_id:'A'},{camera_id:'B'}]};
const selection={camera_ids:['A','B'],start:0,end:4};
function result(){
  return {schema_version:'workbench.blender-physical-review.v1',review_sha256:reviewSha,source_sha256:binding.source_sha256,
    physical_source_sha256:'f'.repeat(64),source_binding:{...binding},selection:{camera_ids:['A','B'],time_range:[0,4],clock_id:binding.clock_id,canonical_ranking_scope:'FULL_SOURCE_UNCHANGED'},
    prior_results:{status:'UNCHANGED_PRIOR_RESULTS',media_rerendered:false,ranking_recomputed:false},evidence_hashes:{fixture:'b'.repeat(64)},geometry_primitives:[],
    items:[{item_ref:itemRef,kind:'PORTAL_APERTURE',site_id:'office',status:'UNKNOWN',review_status:'PENDING',ownership_confirmed:false,
      source_authority:'HUMAN_REVIEW',geometry_refs:[],pending_gaps:[],evidence_refs:['evidence:fixture'],focus:{time_range:[0,4],camera_ids:['A','B'],geometry_refs:[]},
      checklist:[{check_ref:checkRef,default_decision:'UNKNOWN',required_evidence:['SUBSTITUTE evidence']}]}],
    review_state:{review_sha256:reviewSha,revision:0,records:[]},post_confirmation_rerun_performed:false,agent_used:false,formal_acceptance:false};
}
const target=()=>({role:'research',sceneEpoch:1,sceneId:'blender-office',session:{session_ref:'SUBSTITUTE_SESSION'},snapshot,physicalReviewEpoch:0,physicalReviewResult:null});
const payload=()=>({review_sha256:reviewSha,item_ref:itemRef,expected_revision:0,reviewer:'SUBSTITUTE tester',reason:'SUBSTITUTE only',checks:[{check_ref:checkRef,decision:'UNKNOWN',evidence_refs:[],comment:''}]});
const saved=()=>({authority_changed:false,rerun_authorized:false,post_confirmation_rerun_performed:false,
  record:{formal_approval:false,decision:{item_ref:itemRef}},review_state:{review_sha256:reviewSha,revision:1,records:[]}});

test('review loading sends only its bounded scene and display window without reranking or encoding',async()=>{
  const state=target(),requests=[];
  assert.equal(await runPhysicalReviewLoad(state,selection,async p=>{requests.push(p);return result();}),true);
  assert.deepEqual(requests,[{scene_id:'blender-office',camera_ids:['A','B'],start:0,end:4}]);
  assert.equal(state.physicalReviewSelected,itemRef);assert.equal(state.physicalReviewPending,false);
  assert.equal(state.physicalReviewResult.items[0].status,'UNKNOWN');
  assert.equal(state.physicalReviewResult.post_confirmation_rerun_performed,false);
});

test('late review loads cannot restore a previous scene, session, role or query scope',async()=>{
  for(const mutate of [s=>s.sceneEpoch++,s=>s.sceneId='other',s=>s.role='management',s=>s.session={session_ref:'NEW'},s=>invalidatePhysicalReview(s)]){
    const state=target();let done;
    const pending=runPhysicalReviewLoad(state,selection,()=>new Promise(resolve=>{done=resolve;}));
    mutate(state);done(result());assert.equal(await pending,false);assert.equal(state.physicalReviewResult,null);
    assert.equal(physicalReviewRequestIsCurrent(state,{sceneEpoch:1,sceneId:'blender-office',sessionRef:'SUBSTITUTE_SESSION',reviewEpoch:1}),false);
  }
});

test('source, display window and authority version mismatches clear unsafe review state',async()=>{
  for(const change of [r=>r.source_binding.site_id='auditorium',r=>r.selection.time_range=[1,4],r=>r.review_state.revision=true,r=>r.post_confirmation_rerun_performed=true]){
    const state=target(),wrong=result();change(wrong);
    await assert.rejects(runPhysicalReviewLoad(state,selection,async()=>wrong));
    assert.equal(state.physicalReviewResult,null);assert.equal(state.physicalReviewPending,false);
  }
});

test('explicit human save commits only a matching local delta and never authorizes a rerun',async()=>{
  const state=target();await runPhysicalReviewLoad(state,selection,async()=>result());
  const requests=[];assert.equal(await runPhysicalReviewSave(state,payload(),async p=>{requests.push(p);return saved();}),true);
  assert.equal(state.physicalReviewResult.review_state.revision,1);
  assert.deepEqual(requests,[{...payload(),scene_id:'blender-office'}]);
  assert.equal(state.physicalReviewResult.items[0].status,'UNKNOWN');
});

test('stale saves and fabricated approval or revision responses cannot overwrite current review',async()=>{
  for(const mutate of [s=>s.sceneEpoch++,s=>s.session={session_ref:'NEW'},s=>invalidatePhysicalReview(s)]){
    const state=target();await runPhysicalReviewLoad(state,selection,async()=>result());let done;
    const pending=runPhysicalReviewSave(state,payload(),()=>new Promise(resolve=>{done=resolve;}));
    mutate(state);done(saved());assert.equal(await pending,false);
  }
  for(const change of [r=>r.authority_changed=true,r=>r.rerun_authorized=true,r=>r.post_confirmation_rerun_performed=true,r=>r.review_state.revision=9,r=>r.record.formal_approval=true]){
    const state=target();await runPhysicalReviewLoad(state,selection,async()=>result());const wrong=saved();change(wrong);
    await assert.rejects(runPhysicalReviewSave(state,payload(),async()=>wrong));
    assert.equal(state.physicalReviewResult.review_state.revision,0);
  }
});

test('wrong source/item/revision human submissions do not even reach transport',async()=>{
  const state=target();await runPhysicalReviewLoad(state,selection,async()=>result());let calls=0;
  for(const extra of [{item_ref:'other'},{review_sha256:'b'.repeat(64)},{expected_revision:2}])
    await assert.rejects(runPhysicalReviewSave(state,{...payload(),...extra},async()=>{calls++;return saved();}));
  assert.equal(calls,0);
});

test('private locators in human metadata or comments are refused before any local save transport',async()=>{
  const state=target();await runPhysicalReviewLoad(state,selection,async()=>result());let calls=0;
  for(const key of ['reviewer','reason'])for(const value of ['/private/SUBSTITUTE','C:\\SUBSTITUTE\\review','file://SUBSTITUTE'])
    await assert.rejects(runPhysicalReviewSave(state,{...payload(),[key]:value},async()=>{calls++;return saved();}),/私有定位/);
  const input=payload();input.checks[0].comment='/SUBSTITUTE/source';
  await assert.rejects(runPhysicalReviewSave(state,input,async()=>{calls++;return saved();}),/私有定位/);
  assert.equal(calls,0);assert.equal(state.physicalReviewResult.review_state.revision,0);
});

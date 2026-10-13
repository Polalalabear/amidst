import test from 'node:test';
import assert from 'node:assert/strict';
import {validatePhysicalReviewResponse,validatePhysicalReviewInput,physicalReviewScenePlan,physicalReviewSelection,physicalReviewPanelHTML,physicalReviewLocalDecisions,physicalReviewEvidenceAt,physicalReviewDisplayLimit,physicalReviewDisplayKey,
  physicalReviewDecisionPayload,bindPhysicalReviewPanel} from './physical-review.mjs';

const ref=(prefix,n)=>prefix+':'+String(n).padStart(24,'0');
const snapshot={source_binding:{source_sha256:'a'.repeat(64),site_id:'office',run_id:'run-A',clock_id:'source-clock',dataset_sha256:'d'.repeat(64)},cameras:[{camera_id:'CAM_A'},{camera_id:'CAM_B'}],time_range:[0,9.8]};
function catalog() {
  return {schema_version:'workbench.blender-physical-review.v1',review_sha256:'b'.repeat(64),source_binding:structuredClone(snapshot.source_binding),
    source_sha256:'a'.repeat(64),physical_source_sha256:'c'.repeat(64),evidence_hashes:{geometry_archive:'f'.repeat(64)},
    selection:{camera_ids:['CAM_A','CAM_B'],time_range:[2,4],clock_id:'source-clock',canonical_ranking_scope:'FULL_SOURCE_UNCHANGED'},
    prior_results:{checkpoint:'2de9821',status:'UNCHANGED_PRIOR_RESULTS',media_rerendered:false,ranking_recomputed:false},
    review_state:{revision:0,records:[],rerun_authorized:false},agent_used:false,formal_acceptance:false,
    items:[{item_ref:ref('review-item',1),kind:'PORTAL_APERTURE',title:'原門洞標註 <核對>',site_id:'office',status:'UNKNOWN',review_status:'PENDING',source_authority:'HUMAN_REVIEW',
      geometry_refs:[ref('review-geometry',1)],evidence_refs:['evidence:geometry_archive'],pending_gaps:[{code:'MISSING_APERTURE',description:'實際門孔寬高缺失'}],ownership_confirmed:false,
      checklist:[{check_ref:ref('review-check',1),title:'實際門孔是否有來源依據？',required_evidence:['evidence:geometry_archive'],default_decision:'UNKNOWN'}],
      focus:{camera_ids:['CAM_A'],time_range:[2,4],geometry_refs:[ref('review-geometry',1)]}}],
    geometry_primitives:[{geometry_ref:ref('review-geometry',1),kind:'SOURCE_ANNOTATION',label:'原標註範圍',units:'METRES',vertices:[[1,2,.5],[3,2,.5],[3,4,2.5]],triangles:[[0,1,2]],authority:'HUMAN_REVIEW',display_only:true,is_aperture:false,is_collider:false,truncated:false}],
    synchronized_evidence:{samples:[{timestamp:2,world_position:[1,2,.5],state:'PROJECTED_OBSERVATION',camera_id:'CAM_A',candidate_ref:'candidate:PRIVATE'},
      {timestamp:2.2,world_position:[1.1,2,.5],state:'INFERRED_CROSS_CAMERA',camera_id:'CAM_B',candidate_ref:'candidate:PRIVATE'}],missing_intervals:[{time_range:[3,4],reason:'MISSING'}],truncated:false}};
}
function displayContext(result=catalog()) {
  const bounds=[[0,0,0],[4,5,2]],archive='e'.repeat(64);
  return {authority:'PARTIAL_DISPLAY_CONTEXT',source_geometry_modified:false,physical_authority_changed:false,source_archive_sha256:archive,bounds_metres:bounds,
    meshes:[{display_only:true,source_geometry_modified:false,authority:'PARTIAL_DISPLAY_CONTEXT',derivation:{method:'SOURCE_TRIANGLE_SIX_PLANE_CLIP_NO_CAPS_V1',
      source_sha256:result.source_sha256,archive_sha256:archive,crop_native_bu:structuredClone(bounds),metres_per_unit:1,new_caps_created:false,physical_authority_changed:false}}]};
}
test('manual upper-frame alignment uses verified display clipping and preserves raw source, focus and all physical results',()=>{
  const result=catalog(),presentation=displayContext(result),before=structuredClone(result),rawPlan=physicalReviewScenePlan(result);
  const options={presentation,alignAnnotationTop:true},plan=physicalReviewScenePlan(result,null,null,options),overlay=plan.overlays[0];
  assert.deepEqual(overlay.vertices,before.geometry_primitives[0].vertices);
  assert.deepEqual(overlay.display_vertices,[[1,2,.5],[3,2,.5],[3,4,2]]);
  assert.deepEqual(overlay.display_adjustment,{kind:'ANNOTATION_DISPLAY_TOP_CLIP',original_top_z:2.5,target_top_z:2,authority:'LOCAL_DISPLAY_ONLY_NOT_APERTURE'});
  assert.deepEqual(plan.focus,rawPlan.focus);assert.deepEqual(plan.samples,rawPlan.samples);assert.equal(plan.physical_certification,false);
  assert.deepEqual(result,before);assert.equal(result.items[0].status,'UNKNOWN');assert.equal(result.review_state.revision,0);
  assert.equal(physicalReviewScenePlan(result,null,null,{presentation}).overlays[0].display_vertices,undefined);
  assert.deepEqual(physicalReviewSelection(result,null,2,null,options).scene_plan.overlays[0].display_vertices,overlay.display_vertices);
  overlay.display_vertices[0][0]=99;assert.deepEqual(result,before);
  const html=physicalReviewPanelHTML(result,{sourcePresentation:presentation,alignAnnotationTop:true});
  assert.match(html,/data-review-align-display-top checked/);assert.match(html,/不是已確認牆頂或門孔高度/);
  assert.match(html,/value="UNKNOWN" selected/);assert.doesNotMatch(html,/value="CONFIRMED_LOCAL" selected/);
});
test('display alignment refuses mismatched source/crop authority and its local key changes with every source, review, item and display limit',()=>{
  const result=catalog(),presentation=displayContext(result),key=physicalReviewDisplayKey(result,null,presentation);
  assert.ok(key);assert.equal(physicalReviewDisplayLimit(result,null,presentation).target_top_z,2);
  for(const mutate of [p=>p.source_geometry_modified=true,p=>p.physical_authority_changed=true,p=>p.authority='APPROVED',
    p=>p.meshes[0].derivation.source_sha256='f'.repeat(64),p=>p.meshes[0].derivation.archive_sha256='f'.repeat(64),
    p=>p.meshes[0].derivation.new_caps_created=true,p=>p.meshes[0].derivation.method='ASSUMED_WALL_HEIGHT',p=>p.meshes[0].derivation.metres_per_unit=NaN,
    p=>p.bounds_metres[1][2]=1.9,p=>p.bounds_metres[1][2]=Infinity]){
    const wrong=structuredClone(presentation);mutate(wrong);assert.equal(physicalReviewDisplayLimit(result,null,wrong),null);
    assert.equal(physicalReviewScenePlan(result,null,null,{presentation:wrong,alignAnnotationTop:true}).overlays[0].display_vertices,undefined);
    assert.doesNotMatch(physicalReviewPanelHTML(result,{sourcePresentation:wrong}),/data-review-align-display-top/);
  }
  for(const mutate of [r=>r.source_sha256='f'.repeat(64),r=>r.review_sha256='f'.repeat(64),r=>r.items[0].item_ref=ref('review-item',2)]){
    const changed=structuredClone(result);mutate(changed);assert.notEqual(physicalReviewDisplayKey(changed,null,presentation),key);
  }
  const changed=structuredClone(presentation);changed.bounds_metres[1][2]=1.9;changed.meshes[0].derivation.crop_native_bu[1][2]=1.9;
  assert.notEqual(physicalReviewDisplayKey(result,null,changed),key);
  const other=catalog();other.items[0].kind='BODY_CLEARANCE';assert.equal(physicalReviewDisplayKey(other,null,presentation),null);
  assert.doesNotMatch(physicalReviewPanelHTML(other,{sourcePresentation:presentation}),/data-review-align-display-top/);
});
test('review binds exact source, camera, clock and immutable result version without auto approval',()=>{
  assert.equal(validatePhysicalReviewResponse(catalog(),snapshot).items[0].review_status,'PENDING');
  for(const mutate of [v=>v.source_sha256='e'.repeat(64),v=>v.source_binding.run_id='other',v=>v.selection.clock_id='wall-clock',v=>v.selection.camera_ids=['OTHER'],v=>v.items[0].status='APPROVED',v=>v.items[0].checklist[0].default_decision='CONFIRMED_LOCAL',v=>v.prior_results.ranking_recomputed=true,v=>v.ground_truth={position:[999,999,999]},v=>v.evidence_hashes.local_path='/private/source',v=>v.geometry_primitives[0].vertices[0][0]=Infinity]){
    const result=catalog();mutate(result);assert.throws(()=>validatePhysicalReviewResponse(result,snapshot));
  }
});
test('annotation geometry only supplies a copy for display focus and never an aperture, collider or actor position',()=>{
  const result=catalog(),original=structuredClone(result),plan=physicalReviewScenePlan(result,result.items[0].item_ref);
  assert.equal(plan.display_only,true);assert.equal(plan.physical_certification,false);assert.deepEqual(plan.focus.target,[2,3,1.5]);
  assert.equal(plan.focus.purpose,'DISPLAY_FOCUS_ONLY');assert.equal(plan.overlays[0].is_aperture,false);assert.equal(plan.overlays[0].is_collider,false);
  plan.overlays[0].vertices[0][0]=99;assert.deepEqual(result,original);
  const selected=physicalReviewSelection(result,result.items[0].item_ref,9);
  assert.equal(selected.timestamp,4);assert.equal(selected.clock_id,'source-clock');assert.deepEqual(selected.camera_ids,['CAM_A']);assert.equal(selected.ownership_confirmed,false);
  result.items[0].geometry_refs=[];result.items[0].focus.geometry_refs=[];
  assert.equal(physicalReviewScenePlan(result).focus,null);assert.equal(physicalReviewSelection(result).timestamp,2);
});
test('source rings retain holes and all preview budgets reject unbounded or falsely certified geometry',()=>{
  const result=catalog(),primitive=result.geometry_primitives[0];
  primitive.kind='APPROVED_SUPPORT_RING';primitive.rings=[[[0,0,.5],[8,0,.5],[8,8,.5]],[[3,3,.5],[4,3,.5],[4,4,.5]]];
  const plan=physicalReviewScenePlan(result);assert.deepEqual(plan.overlays[0].rings,primitive.rings);
  for(const mutate of [v=>v.geometry_primitives[0].is_collider=true,v=>v.geometry_primitives[0].is_aperture=true,v=>v.geometry_primitives[0].units='BLENDER_UNITS',v=>v.geometry_primitives[0].triangles=[[0,1,400]],v=>v.geometry_primitives[0].vertices=Array.from({length:8193},()=>[0,0,0])]){
    const bad=catalog();mutate(bad);assert.throws(()=>physicalReviewScenePlan(bad));
  }
});
test('pending human checklist exposes actual, inferred, substitute and missing evidence with no identity tokens',()=>{
  const result=catalog();result.items[0].title+=' event:PRIVATE';const html=physicalReviewPanelHTML(result);
  assert.match(html,/實際門孔寬高缺失/);assert.match(html,/原來源標註盒/);assert.match(html,/實際 Blender/);assert.match(html,/推斷 1 點/);assert.match(html,/模擬替代資料/);
  assert.match(html,/本機工程 revision/);assert.match(html,/物理 UNKNOWN/);assert.match(html,/不重跑/);assert.match(html,/&lt;核對&gt;/);
  assert.equal((html.match(/value="UNKNOWN" selected/g)??[]).length,1);assert.doesNotMatch(html,/value="CONFIRMED_LOCAL" selected/);assert.doesNotMatch(html,/event:PRIVATE|candidate:PRIVATE|<核對>/);
  assert.doesNotMatch(html,/data-review-evidence[^>]*checked/);assert.match(html,/data-physical-review-export disabled/);
  assert.match(physicalReviewPanelHTML({...result,source_sha256:'wrong'}),/未顯示/);
});
test('local human payload retains all explicit checklist choices and needs evidence plus reason for support',()=>{
  const result=catalog(),item=result.items[0],row={check_ref:item.checklist[0].check_ref,decision:'UNKNOWN',evidence_refs:[],comment:''};
  assert.deepEqual(physicalReviewDecisionPayload(result,item.item_ref,[row]),{review_sha256:result.review_sha256,item_ref:item.item_ref,checks:[row]});
  const support={...row,decision:'CONFIRMED_LOCAL',evidence_refs:['evidence:geometry_archive'],comment:'核對來源三角形'};
  assert.equal(physicalReviewDecisionPayload(result,item.item_ref,[support]).checks[0].decision,'CONFIRMED_LOCAL');
  for(const rows of [[],[support,support],[{...support,evidence_refs:[]}],[{...support,comment:''}],[{...support,evidence_refs:['evidence:GT']}],[{...support,decision:'APPROVED_SOURCE'}]])assert.throws(()=>physicalReviewDecisionPayload(result,item.item_ref,rows));
});
function dom(result,{decision='UNKNOWN',comment='',evidence=[],reviewer='local reviewer',reason='尚未確認完整淨空'}={}) {
  const handlers=new Map(),feedback={textContent:''},button={disabled:false};
  const field={dataset:{reviewCheck:result.items[0].checklist[0].check_ref},querySelector:selector=>selector==='[data-review-decision]'?{value:decision}:{value:comment},
    querySelectorAll:()=>evidence.map(value=>({value,checked:true}))};
  const form={dataset:{itemRef:result.items[0].item_ref},matches:()=>true,querySelectorAll:()=>[field],
    querySelector:selector=>selector==='[type="submit"]'?button:selector==='[data-review-feedback]'?feedback:selector==='[data-review-reviewer]'?{value:reviewer}:selector==='[data-review-reason]'?{value:reason}:null};
  const container={contains:()=>true,addEventListener:(type,fn)=>handlers.set(type,fn),removeEventListener:(type)=>handlers.delete(type)};
  return {container,handlers,form,feedback,button};
}
test('display alignment requires an explicit current UI change and never submits human decisions or exports',()=>{
  const result=catalog(),fixture=dom(result),display=[],saved=[],exported=[];let current=true;
  const dispose=bindPhysicalReviewPanel(fixture.container,{getResult:()=>result,current:()=>current,onDisplayAlign:enabled=>display.push(enabled),onSave:payload=>saved.push(payload),onExport:payload=>exported.push(payload)});
  assert.deepEqual(display,[]);
  const change=fixture.handlers.get('change');
  change({target:{matches:()=>false,checked:true}});assert.deepEqual(display,[]);
  change({target:{matches:()=>true,checked:true}});change({target:{matches:()=>true,checked:false}});
  assert.deepEqual(display,[true,false]);assert.deepEqual(saved,[]);assert.deepEqual(exported,[]);assert.equal(result.review_state.revision,0);
  current=false;change({target:{matches:()=>true,checked:true}});assert.deepEqual(display,[true,false]);
  dispose();assert.equal(fixture.handlers.size,0);current=true;change({target:{matches:()=>true,checked:true}});assert.deepEqual(display,[true,false]);
});
test('binding never submits on load or selection; only an explicit user submit creates a local revision',async()=>{
  const result=catalog(),{container,handlers,form,feedback}=dom(result),sent=[],selected=[],errors=[];
  const dispose=bindPhysicalReviewPanel(container,{getResult:()=>result,onSelect:ref=>selected.push(ref),onSave:async payload=>sent.push(payload),onError:error=>errors.push(error)});
  assert.equal(sent.length,0);assert.equal(selected.length,0);
  handlers.get('click')({target:{closest:selector=>selector==='[data-physical-review-item]'?{dataset:{physicalReviewItem:result.items[0].item_ref}}:null}});
  assert.deepEqual(selected,[result.items[0].item_ref]);assert.equal(sent.length,0);
  await handlers.get('submit')({target:form,preventDefault(){}});
  assert.equal(sent.length,1);assert.equal(sent[0].expected_revision,0);assert.equal(sent[0].checks[0].decision,'UNKNOWN');assert.equal(sent[0].reviewer,'local reviewer');assert.equal(errors.length,0);
  assert.match(feedback.textContent,/本機工程修訂/);assert.equal(result.items[0].status,'UNKNOWN');assert.equal(result.items[0].review_status,'PENDING');
  dispose();assert.equal(handlers.size,0);
});
test('stale views, double submit, missing human fields and late responses never auto approve or export',async()=>{
  const result=catalog(),fixture=dom(result),requests=[],exports=[];let current=true,finish;
  const dispose=bindPhysicalReviewPanel(fixture.container,{getResult:()=>result,current:()=>current,onSave:payload=>new Promise(resolve=>{requests.push(payload);finish=resolve;}),onExport:payload=>exports.push(payload)});
  const submit=fixture.handlers.get('submit'),pending=submit({target:fixture.form,preventDefault(){}});
  await submit({target:fixture.form,preventDefault(){}});assert.equal(requests.length,1);
  current=false;finish();await pending;assert.equal(fixture.feedback.textContent,'');assert.equal(exports.length,0);dispose();
  const missing=dom(result,{reviewer:''}),errors=[];
  bindPhysicalReviewPanel(missing.container,{getResult:()=>result,onSave:()=>requests.push('BAD'),onError:error=>errors.push(error)});
  await missing.handlers.get('submit')({target:missing.form,preventDefault(){}});assert.equal(errors.length,1);assert.equal(requests.length,1);
});

test('cross-camera missing samples have both source cameras, never an observed camera or filled position',()=>{
  const result=catalog();
  result.synchronized_evidence.samples.push({timestamp:3.2,world_position:null,state:'MISSING',camera_id:null,source_camera_ids:['CAM_A','CAM_B']});
  assert.equal(validatePhysicalReviewResponse(result),result);
  assert.match(physicalReviewPanelHTML(result),/缺失或未知 1 點/);
  const narrow=structuredClone(result);narrow.selection.camera_ids=['CAM_A'];narrow.items[0].focus.camera_ids=['CAM_A'];narrow.synchronized_evidence.samples=narrow.synchronized_evidence.samples.filter(s=>s.camera_id!=='CAM_B');
  assert.throws(()=>validatePhysicalReviewResponse(narrow));
  for(const changed of [{state:'PROJECTED_OBSERVATION'},{world_position:[1,1,.5]}]){
    const invalid=structuredClone(result);Object.assign(invalid.synchronized_evidence.samples.at(-1),changed);assert.throws(()=>validatePhysicalReviewResponse(invalid));
  }
});
test('saved local revision choices are restored as human records without changing source status or review defaults',()=>{
  const result=catalog(),item=result.items[0],check=item.checklist[0];
  result.review_state={revision:1,records:[{decision:{review_sha256:result.review_sha256,item_ref:item.item_ref,checks:[{check_ref:check.check_ref,decision:'CONFIRMED_LOCAL',evidence_refs:item.geometry_refs,comment:'只確認來源標註位置'}]}}],rerun_authorized:false};
  assert.equal(physicalReviewLocalDecisions(result,item.item_ref)[check.check_ref].decision,'CONFIRMED_LOCAL');
  assert.match(physicalReviewPanelHTML(result),/value="CONFIRMED_LOCAL" selected/);
  assert.match(physicalReviewPanelHTML(result),/物理 UNKNOWN/);
  assert.equal(item.review_status,'PENDING');assert.equal(check.default_decision,'UNKNOWN');
  result.review_state.records[0].decision.review_sha256='e'.repeat(64);assert.deepEqual(physicalReviewLocalDecisions(result),{});
});
test('delta export requires an explicit user click and an existing local revision',()=>{
  const result=catalog(),fixture=dom(result),exports=[];
  bindPhysicalReviewPanel(fixture.container,{getResult:()=>result,onExport:payload=>exports.push(payload)});
  const event={target:{closest:selector=>selector==='[data-physical-review-export]'?{disabled:false}:null}};
  fixture.handlers.get('click')(event);assert.equal(exports.length,0);
  result.review_state.revision=1;fixture.handlers.get('click')(event);
  assert.deepEqual(exports,[{review_sha256:result.review_sha256,revision:1}]);
});
test('review evidence cursor preserves observed and inferred points separately and never holds across a missing span',()=>{
  const result=catalog();result.items[0].kind='BODY_CLEARANCE';
  result.synchronized_evidence.samples=[{timestamp:2,world_position:[1,2,.5],state:'PROJECTED_OBSERVATION',camera_id:'CAM_A',candidate_refs:['candidate:A']},
    {timestamp:2.2,world_position:[1.2,2,.5],state:'INFERRED_INTERPOLATION',camera_id:'CAM_A',candidate_refs:['candidate:A']},
    {timestamp:3,world_position:null,state:'MISSING',camera_id:null,source_camera_ids:['CAM_A','CAM_B'],candidate_refs:['candidate:A']},
    {timestamp:4,world_position:[4,2,.5],state:'PROJECTED_OBSERVATION',camera_id:'CAM_B',candidate_refs:['candidate:A']}];
  result.synchronized_evidence.missing_intervals=[{time_range:[2.2,4],camera_ids:['CAM_A','CAM_B'],candidate_ref:'candidate:A',reason:'CROSS_CAMERA_LONG_GAP'}];
  const plan=physicalReviewScenePlan(result);
  assert.equal(physicalReviewEvidenceAt(plan,2)[0].state,'PROJECTED_OBSERVATION');
  assert.equal(physicalReviewEvidenceAt(plan,2.2)[0].state,'INFERRED_INTERPOLATION');
  assert.deepEqual(physicalReviewEvidenceAt(plan,2.25),[]);assert.deepEqual(physicalReviewEvidenceAt(plan,3),[]);assert.deepEqual(physicalReviewEvidenceAt(plan,3.95),[]);
  assert.deepEqual(physicalReviewEvidenceAt(plan,4)[0].world_position,[4,2,.5]);assert.deepEqual(physicalReviewEvidenceAt(plan,4.2),[]);
  assert.equal(plan.nominal_body,null);assert.equal(plan.samples[0].connect_from_previous,false);
});
test('source overlap points stay independent and a body envelope requires explicit approved nominal policy',()=>{
  const result=catalog();result.items[0].kind='BODY_CLEARANCE';
  result.synchronized_evidence.samples.push({...result.synchronized_evidence.samples[0],camera_id:'CAM_B',world_position:[5,2,.5]});
  const policy={radius_m:.3,height_m:1.7,authority:'APPROVED_POLICY_NOT_MEASURED_BODY',source_sha256:result.source_sha256};
  result.nominal_body_policy=policy;const plan=physicalReviewScenePlan(result);
  assert.deepEqual(physicalReviewEvidenceAt(plan,2).map(sample=>sample.world_position),[[1,2,.5],[5,2,.5]]);
  assert.deepEqual(plan.nominal_body,{radius_m:.3,height_m:1.7,authority:'APPROVED_POLICY_NOT_MEASURED_BODY',measured_body:false});
  result.nominal_body_policy={...policy,source_sha256:'e'.repeat(64)};assert.equal(physicalReviewScenePlan(result).nominal_body,null);
});
test('actual source summary binds body policy to all three source hashes and never treats inference or partial geometry as body measurement',()=>{
  const result=catalog();result.items[0].kind='BODY_CLEARANCE';result.evidence_hashes.body_policy='e'.repeat(64);
  const summary={schema_version:'workbench.blender-physical-source.v1',status:'AVAILABLE',units:'METRES',source_sha256:result.source_sha256,
    physical_source_sha256:result.physical_source_sha256,evidence_hashes:{body_policy:result.evidence_hashes.body_policy},
    policy:{authority:'APPROVED',units:'metres',body_model:'UPRIGHT_CYLINDER',trajectory_reference:'FLOOR_CONTACT_POINT',body_radius_m:.3,body_height_m:1.7}};
  const original=structuredClone(summary),ref=result.items[0].item_ref;
  const plan=physicalReviewScenePlan(result,ref,summary);
  assert.deepEqual(plan.nominal_body,{radius_m:.3,height_m:1.7,authority:'APPROVED_POLICY_NOT_MEASURED_BODY',measured_body:false});
  assert.deepEqual(physicalReviewSelection(result,ref,2,summary).scene_plan.nominal_body,plan.nominal_body);
  assert.deepEqual(summary,original);assert.equal(plan.physical_certification,false);
  const html=physicalReviewPanelHTML(result,{selectedRef:ref,sourceSummary:summary});
  assert.match(html,/半徑 0\.3 m、高度 1\.7 m/);assert.match(html,/並非量測身形或淨空認證/);assert.match(html,/推斷位置僅顯示琥珀色點/);
  result.nominal_body_policy={radius_m:.9,height_m:2,authority:'APPROVED_POLICY_NOT_MEASURED_BODY',source_sha256:result.source_sha256};
  for(const mutate of [v=>v.source_sha256='f'.repeat(64),v=>v.physical_source_sha256='f'.repeat(64),v=>v.evidence_hashes.body_policy='f'.repeat(64),
    v=>delete v.evidence_hashes.body_policy,v=>v.policy.authority='HUMAN_REVIEW',v=>v.policy.units='BLENDER_UNITS',v=>v.policy.body_radius_m=0,
    v=>v.policy.body_height_m=Infinity,v=>v.policy.body_model='MEASURED_BODY',v=>v.policy.trajectory_reference='LANDMARK_POINT']){
    const invalid=structuredClone(summary);mutate(invalid);
    assert.equal(physicalReviewScenePlan(result,ref,invalid).nominal_body,null);
    assert.match(physicalReviewPanelHTML(result,{selectedRef:ref,sourceSummary:invalid}),/只顯示可用位置點/);
  }
});
test('human input uses the same locator boundary as responses without confusing ordinary source reasoning with a path',()=>{
  const allowed={reviewer:'SUBSTITUTE reviewer',reason:'核對 camera 1／2；4.2 s 前後的來源投影',checks:[{comment:'寬高仍未知；先保留 A/B 候選'}]};
  assert.equal(validatePhysicalReviewInput(allowed),allowed);
  for(const value of ['/private/SUBSTITUTE_METADATA_PATH','/tmp/SUBSTITUTE_METADATA_PATH','C:\\SUBSTITUTE_METADATA_PATH','核對 /Users/SUBSTITUTE/source','file://SUBSTITUTE/source'])
    for(const field of ['reviewer','reason','comment'])assert.throws(()=>validatePhysicalReviewInput({[field]:value}),/私有定位資訊/);
  const result=catalog(),check=result.items[0].checklist[0];
  assert.throws(()=>physicalReviewDecisionPayload(result,result.items[0].item_ref,[{check_ref:check.check_ref,decision:'UNKNOWN',evidence_refs:[],comment:'/tmp/SUBSTITUTE_COMMENT_PATH'}]),/私有定位資訊/);
});
test('unsafe reviewer, reason or checklist comment never reaches save transport or persists a locked review revision',async()=>{
  for(const options of [{reviewer:'/private/SUBSTITUTE_REVIEWER'},{reason:'/tmp/SUBSTITUTE_REASON'},{comment:'來源位於 /Users/SUBSTITUTE/source'}]){
    const result=catalog(),fixture=dom(result,options),sent=[],errors=[];
    const dispose=bindPhysicalReviewPanel(fixture.container,{getResult:()=>result,onSave:async payload=>sent.push(payload),onError:error=>errors.push(error)});
    await fixture.handlers.get('submit')({target:fixture.form,preventDefault(){}});
    assert.equal(sent.length,0);assert.equal(errors.length,1);assert.match(errors[0].message,/私有定位資訊/);
    assert.equal(result.review_state.revision,0);assert.equal(fixture.button.disabled,false);assert.equal(result.items[0].review_status,'PENDING');dispose();
  }
});

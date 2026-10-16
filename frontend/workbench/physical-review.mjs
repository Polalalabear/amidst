// Source-bound engineering review. Decisions remain local and never approve source geometry.
const h=value=>String(value??'').replace(/\b(?:event|evt|track|candidate|association-candidate):[A-Za-z0-9_.:/-]+/g,'內部識別碼（見 log）').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list=value=>Array.isArray(value)?value:[];
const point=value=>Array.isArray(value)&&value.length===3&&value.every(Number.isFinite);
const range=value=>Array.isArray(value)&&value.length===2&&value.every(Number.isFinite)&&value[0]<=value[1]?value:null;
// Optional source provenance: absent or null stays null; a present value must be a bounded opaque string.
const validObservationRef=value=>value===undefined||value===null||typeof value==='string'&&value.length>0&&value.length<=256;
const sha=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const itemRef=value=>typeof value==='string'&&/^review-item:[a-f0-9]{24}$/.test(value);
const checkRef=value=>typeof value==='string'&&/^review-check:[a-f0-9]{24}$/.test(value);
const geometryRef=value=>typeof value==='string'&&/^review-geometry:[a-f0-9]{24}$/.test(value);
const kinds=new Set(['PORTAL_APERTURE','CORRIDOR_CONNECTIVITY','BODY_CLEARANCE']);
const geometryKinds=new Set(['SOURCE_ANNOTATION','SOURCE_TRIANGLES','APPROVED_SUPPORT_RING','SOURCE_WITNESS']);
const decisions=new Set(['CONFIRMED_LOCAL','CONTRADICTED_LOCAL','UNKNOWN']);
const kindLabel=kind=>({PORTAL_APERTURE:'門洞',CORRIDOR_CONNECTIVITY:'走廊連通',BODY_CLEARANCE:'人體淨空'})[kind]??'待確認';
const basisLabel=kind=>({SOURCE_ANNOTATION:'原來源標註盒／範圍（非實際門孔）',SOURCE_TRIANGLES:'實際來源三角形（局部預覽）',APPROVED_SUPPORT_RING:'已批准支撐範圍（非全身通行證明）',SOURCE_WITNESS:'來源幾何核對點／三角形（非已批准碰撞面）'})[kind]??'來源依據未知';
const statusLabel=status=>({PENDING:'待使用者確認',CONFIRMED_LOCAL:'本機支持紀錄',CONTRADICTED_LOCAL:'本機矛盾紀錄',UNKNOWN:'未知／資料不足'})[status]??'待使用者確認';
const evidenceLabel=value=>({geometry_archive:'實際來源幾何封存',floor_support:'來源支撐面與實際高度',portal_review:'待審門洞來源核對',local_scope_review:'局部完整性與淨空審查',body_policy:'目前人體包絡假設',architectural_scale:'Blender 與公尺比例'})[String(value).replace(/^evidence:/,'')]??value;
const itemEvidenceLabel=(item,ref)=>geometryRef(ref)?`目前來源幾何預覽 ${item.geometry_refs.indexOf(ref)+1}`:evidenceLabel(ref);
const seconds=value=>Number.isFinite(value)?`${value.toFixed(1)} s`:'時間未知';
const interval=value=>range(value)?value.map(seconds).join('–'):'時間範圍缺失';

function safeValue(value,depth=0) {
  if(depth>24)throw Error('人工確認資料超出允許結構。');
  if(Array.isArray(value)){for(const child of value)safeValue(child,depth+1);return;}
  if(value&&typeof value==='object'){
    for(const [key,child] of Object.entries(value)){
      if(/^(gt|ground_truth|trajectory|TrajectoryID|local_path|relative_path|raw_features|token|session_id|private_.*)$/.test(key))throw Error('人工確認資料包含未允許的私有或答案欄位。');
      safeValue(child,depth+1);
    }
  }else if(typeof value==='number'&&!Number.isFinite(value))throw Error('人工確認資料包含非有限數值。');
  else if(typeof value==='string'&&(/^(?:\/|[A-Za-z]:[\\/])/.test(value)||/\/Users\/|\/private\/|file:\/\//.test(value)))throw Error('人工確認資料包含私有定位資訊。');
}
export function validatePhysicalReviewInput(value) {
  safeValue(value);
  return value;
}
export function validatePhysicalReviewResponse(result,snapshot=null) {
  safeValue(result);
  const binding=result?.source_binding??{},selection=result?.selection??{},expected=snapshot?.source_binding;
  if(result?.schema_version!=='workbench.blender-physical-review.v1'||!sha(result.review_sha256)||
    !sha(result.source_sha256)||result.source_sha256!==binding.source_sha256||!sha(result.physical_source_sha256)||
    !range(selection.time_range)||!Array.isArray(selection.camera_ids)||!selection.camera_ids.length||selection.camera_ids.length>8||
    new Set(selection.camera_ids).size!==selection.camera_ids.length||selection.clock_id!==binding.clock_id||
    typeof binding.clock_id!=='string'||!binding.clock_id||!binding.run_id||!binding.site_id||
    selection.canonical_ranking_scope!=='FULL_SOURCE_UNCHANGED'||
    result.agent_used!==undefined&&result.agent_used!==false||result.gt_used!==undefined&&result.gt_used!==false||result.formal_acceptance!==undefined&&result.formal_acceptance!==false||
    result.rerun_authorized!==undefined&&result.rerun_authorized!==false||result.source_authority_changed!==undefined&&result.source_authority_changed!==false||
    !Array.isArray(result.items)||result.items.length>64||!Array.isArray(result.geometry_primitives)||result.geometry_primitives.length>64||
    !result.evidence_hashes||Object.keys(result.evidence_hashes).length>64||!Object.values(result.evidence_hashes).every(sha)||
    result.prior_results?.status!=='UNCHANGED_PRIOR_RESULTS'||result.prior_results.media_rerendered!==false||result.prior_results.ranking_recomputed!==false)
    throw Error('人工確認資料的來源、時鐘或版本契約不相符。');
  if(expected){
    for(const key of ['source_sha256','site_id','run_id','clock_id','dataset_sha256'])if(expected[key]!==undefined&&binding[key]!==expected[key])throw Error('人工確認資料屬於不同來源或場景。');
    const cameras=new Set(list(snapshot.cameras).map(camera=>camera.camera_id));
    if(selection.camera_ids.some(camera=>!cameras.has(camera)))throw Error('人工確認鏡頭未登錄於目前場景。');
    const sourceRange=range(snapshot.time_range);
    if(sourceRange&&(selection.time_range[0]<sourceRange[0]||selection.time_range[1]>sourceRange[1]))throw Error('人工確認時間超出來源範圍。');
    const physicalSource=snapshot.physical_constraints?.physical_source_sha256;
    if(physicalSource&&physicalSource!==result.physical_source_sha256)throw Error('人工確認使用不同的物理來源版本。');
  }
  let vertices=0,triangles=0;
  const refs=new Set();
  for(const primitive of result.geometry_primitives){
    if(!geometryRef(primitive.geometry_ref)||refs.has(primitive.geometry_ref)||!geometryKinds.has(primitive.kind)||primitive.units!=='METRES'||
      primitive.display_only!==true||primitive.is_aperture!==false||primitive.is_collider!==false||primitive.ownership_confirmed!==undefined&&primitive.ownership_confirmed!==false||typeof primitive.truncated!=='boolean'||
      primitive.source_geometry_sha256!==undefined&&(!sha(primitive.source_geometry_sha256)||result.evidence_hashes.geometry_model&&primitive.source_geometry_sha256!==result.evidence_hashes.geometry_model)||
      !Array.isArray(primitive.vertices)||!primitive.vertices.every(point)||!Array.isArray(primitive.triangles)||
      primitive.triangles.some(face=>!Array.isArray(face)||face.length!==3||face.some(index=>!Number.isInteger(index)||index<0||index>=primitive.vertices.length))||
      list(primitive.rings).some(ring=>!Array.isArray(ring)||ring.length<3||ring.length>512||!ring.every(point)))throw Error('人工確認幾何預覽無效；不推定可通行或碰撞。');
    refs.add(primitive.geometry_ref);vertices+=primitive.vertices.length+list(primitive.rings).reduce((n,ring)=>n+ring.length,0);triangles+=primitive.triangles.length;
  }
  if(vertices>8192||triangles>4096)throw Error('人工確認幾何超出預覽上限。');
  const items=new Set(),checks=new Set();
  for(const item of result.items){
    if(!itemRef(item.item_ref)||items.has(item.item_ref)||!kinds.has(item.kind)||item.site_id!==binding.site_id||item.status!=='UNKNOWN'||
      !['PENDING','CONFIRMED_LOCAL','CONTRADICTED_LOCAL','UNKNOWN'].includes(item.review_status)||item.ownership_confirmed!==false||
      !['HUMAN_REVIEW','PARTIAL_APPROVED'].includes(item.source_authority)||!Array.isArray(item.geometry_refs)||item.geometry_refs.some(ref=>!refs.has(ref))||
      !Array.isArray(item.checklist)||!item.checklist.length||item.checklist.length>32||!Array.isArray(item.pending_gaps)||
      !Array.isArray(item.evidence_refs)||item.evidence_refs.length>64||!range(item.focus?.time_range)||
      item.focus.time_range[0]<selection.time_range[0]||item.focus.time_range[1]>selection.time_range[1]||
      !Array.isArray(item.focus.camera_ids)||item.focus.camera_ids.some(camera=>!selection.camera_ids.includes(camera))||
      !Array.isArray(item.focus.geometry_refs)||item.focus.geometry_refs.some(ref=>!refs.has(ref)))throw Error('待確認項目或來源範圍無效。');
    items.add(item.item_ref);
    for(const check of item.checklist){
      if(!checkRef(check.check_ref)||checks.has(check.check_ref)||check.default_decision!=='UNKNOWN'||!Array.isArray(check.required_evidence))throw Error('人工確認清單不可預先核准或重複。');
      checks.add(check.check_ref);
    }
  }
  const evidence=result.synchronized_evidence;
  if(evidence){
    if(!Array.isArray(evidence.samples)||evidence.samples.length>400||!Array.isArray(evidence.missing_intervals)||evidence.missing_intervals.length>256||
      evidence.samples.some(sample=>!Number.isFinite(sample.timestamp)||sample.timestamp<selection.time_range[0]||sample.timestamp>selection.time_range[1]||
        !['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION','INFERRED_CROSS_CAMERA','MISSING'].includes(sample.state)||
        !validObservationRef(sample.observation_ref)||
        sample.camera_id!==null&&!selection.camera_ids.includes(sample.camera_id)||
        sample.camera_id===null&&(sample.state==='PROJECTED_OBSERVATION'||!Array.isArray(sample.source_camera_ids)||!sample.source_camera_ids.length||sample.source_camera_ids.some(camera=>!selection.camera_ids.includes(camera)))||
        (sample.state==='MISSING'?sample.world_position!==null:!point(sample.world_position))))throw Error('人工確認同步證據無效或超出來源範圍。');
  }
  return result;
}

export function selectedPhysicalReviewItem(result,selectedRef=null) {
  return list(result?.items).find(item=>item.item_ref===selectedRef)??list(result?.items)[0]??null;
}
export function physicalReviewLocalDecisions(result,itemRefValue=null) {
  const values={};
  for(const record of list(result?.review_state?.records)){
    const decision=record.decision;
    if(!decision||decision.review_sha256!==result.review_sha256||itemRefValue&&decision.item_ref!==itemRefValue)continue;
    for(const check of list(decision.checks))if(checkRef(check.check_ref)&&decisions.has(check.decision))values[check.check_ref]={decision:check.decision,evidence_refs:[...list(check.evidence_refs)],comment:check.comment??''};
  }
  return values;
}
function nominalBodyPolicy(result,sourceSummary=null) {
  let radius,height;
  if(sourceSummary!==null){
    const policy=sourceSummary?.policy;
    if(sourceSummary?.schema_version!=='workbench.blender-physical-source.v1'||sourceSummary.status!=='AVAILABLE'||sourceSummary.units!=='METRES'||
      sourceSummary.source_sha256!==result.source_sha256||sourceSummary.physical_source_sha256!==result.physical_source_sha256||
      !sha(result.evidence_hashes?.body_policy)||sourceSummary.evidence_hashes?.body_policy!==result.evidence_hashes.body_policy||
      policy?.authority!=='APPROVED'||policy.units!=='metres'||policy.body_model!=='UPRIGHT_CYLINDER'||policy.trajectory_reference!=='FLOOR_CONTACT_POINT')return null;
    radius=policy.body_radius_m;height=policy.body_height_m;
  }else{
    const policy=result.nominal_body_policy;
    if(policy?.authority!=='APPROVED_POLICY_NOT_MEASURED_BODY'||policy.source_sha256!==result.source_sha256)return null;
    radius=policy.radius_m;height=policy.height_m;
  }
  return Number.isFinite(radius)&&radius>0&&radius<=2&&Number.isFinite(height)&&height>0&&height<=4?
    {radius_m:radius,height_m:height,authority:'APPROVED_POLICY_NOT_MEASURED_BODY',measured_body:false}:null;
}
export function physicalReviewDisplayLimit(result,selectedRef=null,presentation=null) {
  const item=selectedPhysicalReviewItem(result,selectedRef),bounds=presentation?.bounds_metres,meshes=presentation?.meshes;
  if(item?.kind!=='PORTAL_APERTURE'||presentation?.authority!=='PARTIAL_DISPLAY_CONTEXT'||presentation.source_geometry_modified!==false||
    presentation.physical_authority_changed!==false||!sha(presentation.source_archive_sha256)||!Array.isArray(bounds)||bounds.length!==2||!bounds.every(point)||
    bounds[0].some((value,axis)=>value>=bounds[1][axis])||!Array.isArray(meshes)||!meshes.length||meshes.length>2)return null;
  for(const mesh of meshes){
    const derivation=mesh.derivation,crop=derivation?.crop_native_bu,scale=derivation?.metres_per_unit;
    if(mesh.display_only!==true||mesh.source_geometry_modified!==false||mesh.authority!=='PARTIAL_DISPLAY_CONTEXT'||
      derivation?.method!=='SOURCE_TRIANGLE_SIX_PLANE_CLIP_NO_CAPS_V1'||derivation.source_sha256!==result.source_sha256||
      derivation.archive_sha256!==presentation.source_archive_sha256||derivation.new_caps_created!==false||derivation.physical_authority_changed!==false||
      !Number.isFinite(scale)||scale<=0||!Array.isArray(crop)||crop.length!==2||!crop.every(point)||
      crop.some((p,index)=>p.some((value,axis)=>Math.abs(value*scale-bounds[index][axis])>1e-8)))return null;
  }
  const annotations=list(result.geometry_primitives).filter(p=>item.geometry_refs.includes(p.geometry_ref)&&p.kind==='SOURCE_ANNOTATION');
  const target_top_z=bounds[1][2];
  return annotations.some(p=>Math.min(...p.vertices.map(v=>v[2]))<target_top_z&&Math.max(...p.vertices.map(v=>v[2]))>target_top_z)?
    {target_top_z,authority:'LOCAL_DISPLAY_ONLY_NOT_APERTURE',source_archive_sha256:presentation.source_archive_sha256}:null;
}
export function physicalReviewDisplayKey(result,selectedRef=null,presentation=null) {
  const item=selectedPhysicalReviewItem(result,selectedRef),limit=physicalReviewDisplayLimit(result,selectedRef,presentation);
  return sha(result?.source_sha256)&&sha(result?.review_sha256)&&itemRef(item?.item_ref)&&limit?
    `amidst.review-display.v1:${result.source_sha256}:${result.review_sha256}:${item.item_ref}:${limit.source_archive_sha256}:${limit.target_top_z}`:null;
}
export function physicalReviewScenePlan(result,selectedRef=null,sourceSummary=null,displayOptions={}) {
  if(!result)return {overlays:[],display_only:true,physical_certification:false,focus:null};
  validatePhysicalReviewResponse(result);
  const selected=selectedPhysicalReviewItem(result,selectedRef),selectedRefs=new Set(selected?.geometry_refs??[]);
  const overlays=result.geometry_primitives.filter(primitive=>selectedRefs.has(primitive.geometry_ref)).map((primitive,index)=>({
    geometry_ref:primitive.geometry_ref,item_ref:selected.item_ref,kind:primitive.kind,units:'METRES',
    vertices:primitive.vertices.map(vertex=>[...vertex]),triangles:primitive.triangles.map(face=>[...face]),rings:list(primitive.rings).map(ring=>ring.map(vertex=>[...vertex])),
    caption:`${kindLabel(selected.kind)} ${index+1} · ${primitive.kind==='SOURCE_ANNOTATION'?'原標註範圍':primitive.kind==='APPROVED_SUPPORT_RING'?'局部支撐':'來源預覽'}`,
    authority:primitive.authority,display_only:true,is_aperture:false,is_collider:false,truncated:primitive.truncated}));
  const displayLimit=displayOptions.alignAnnotationTop===true?physicalReviewDisplayLimit(result,selectedRef,displayOptions.presentation):null;
  if(displayLimit)for(const overlay of overlays){
    const original_top_z=Math.max(...overlay.vertices.map(v=>v[2])),bottom=Math.min(...overlay.vertices.map(v=>v[2]));
    if(overlay.kind!=='SOURCE_ANNOTATION'||bottom>=displayLimit.target_top_z||original_top_z<=displayLimit.target_top_z)continue;
    overlay.display_vertices=overlay.vertices.map(v=>[v[0],v[1],Math.min(v[2],displayLimit.target_top_z)]);
    overlay.display_adjustment={kind:'ANNOTATION_DISPLAY_TOP_CLIP',original_top_z,target_top_z:displayLimit.target_top_z,authority:displayLimit.authority};
    overlay.caption='門洞核對框 · 上緣顯示對齊';
  }
  const focusRefs=new Set(selected?.focus.geometry_refs??[]),positions=overlays.filter(overlay=>focusRefs.has(overlay.geometry_ref)).flatMap(overlay=>[...overlay.vertices,...overlay.rings.flat()]);
  const bounds=positions.length?{min:[0,1,2].map(axis=>Math.min(...positions.map(p=>p[axis]))),max:[0,1,2].map(axis=>Math.max(...positions.map(p=>p[axis])))}:null;
  const focus=bounds?{target:bounds.min.map((v,i)=>(v+bounds.max[i])/2),radius:Math.max(.25,Math.hypot(...bounds.max.map((v,i)=>v-bounds.min[i]))/2),
    bounds,purpose:'DISPLAY_FOCUS_ONLY'}:null;
  const evidence=result.synchronized_evidence??{};
  const samples=list(evidence.samples).map(sample=>({timestamp:sample.timestamp,world_position:sample.world_position?[...sample.world_position]:null,state:sample.state,
    camera_id:sample.camera_id,source_camera_ids:[...list(sample.source_camera_ids)],candidate_refs:[...list(sample.candidate_refs)],observation_ref:typeof sample.observation_ref==='string'?sample.observation_ref:null,connect_from_previous:sample.connect_from_previous===true}));
  const missing=list(evidence.missing_intervals).map(gap=>({time_range:range(gap.time_range)?[...gap.time_range]:null,camera_ids:[...list(gap.camera_ids)],candidate_ref:gap.candidate_ref??null,reason:gap.reason??'MISSING'}));
  const nominalBody=selected?.kind==='BODY_CLEARANCE'?nominalBodyPolicy(result,sourceSummary):null;
  return {review_sha256:result.review_sha256,source_sha256:result.source_sha256,selected_ref:selected?.item_ref??null,selected_kind:selected?.kind??null,
    overlays,display_only:true,physical_certification:false,focus,time_range:[...result.selection.time_range],samples,missing_intervals:missing,sample_limits:sampleLimits(evidence,samples.length),nominal_body:nominalBody};
}
const USABLE_EVIDENCE=['PROJECTED_OBSERVATION','INFERRED_INTERPOLATION','INFERRED_CROSS_CAMERA'];
export const REVIEW_MARKER_LIMIT=24;
const sampleLimits=(evidence,received)=>({sample_count:Number.isInteger(evidence.sample_count)?evidence.sample_count:received,received_samples:received,
  maximum_samples:Number.isInteger(evidence.maximum_samples)?evidence.maximum_samples:null,truncated:evidence.truncated===true,marker_limit_per_timestamp:REVIEW_MARKER_LIMIT});
const textOf=value=>value===null||value===undefined?'':String(value);
const sortedUnique=values=>[...new Set(values)].sort();
const byText=(a,b)=>a<b?-1:a>b?1:0;
// Rows are one observation when they share a source observation_ref and the same projected record; candidate membership is unioned.
// Without observation_ref, candidate membership is part of identity, so matching XYZ alone never merges two evidence sources.
function evidenceRecordKey(sample) {
  const observation=typeof sample.observation_ref==='string'?sample.observation_ref:null;
  return JSON.stringify([sample.timestamp,observation,sample.camera_id??null,sample.state,sample.world_position,sample.connect_from_previous===true,
    observation===null?sortedUnique(list(sample.candidate_refs)):null,observation===null?sortedUnique(list(sample.source_camera_ids)):null]);
}
function evidenceFrameSamples(rows) {
  const records=new Map();
  for(const sample of rows){
    const key=evidenceRecordKey(sample),found=records.get(key);
    if(found){found.candidate_refs=sortedUnique([...found.candidate_refs,...list(sample.candidate_refs)]);found.source_camera_ids=sortedUnique([...found.source_camera_ids,...list(sample.source_camera_ids)]);continue;}
    records.set(key,{...sample,candidate_refs:sortedUnique(list(sample.candidate_refs)),source_camera_ids:sortedUnique(list(sample.source_camera_ids)),segment_start:sample.connect_from_previous!==true,record_key:key});
  }
  const ordered=[...records.values()].sort((a,b)=>byText(textOf(a.camera_id),textOf(b.camera_id))||byText(a.state,b.state)||byText(textOf(a.observation_ref),textOf(b.observation_ref))||
    byText(JSON.stringify(a.world_position),JSON.stringify(b.world_position))||byText(a.candidate_refs.join(','),b.candidate_refs.join(','))||byText(a.record_key,b.record_key));
  const used=new Map();
  return ordered.map(sample=>{
    // The key follows the source observation (never the array position); conflicting records sharing one reference get an ordinal.
    const base=typeof sample.observation_ref==='string'?`observation:${sample.timestamp}:${sample.observation_ref}`:
      `sample:${sample.timestamp}:${textOf(sample.camera_id)}:${sample.state}:${sample.candidate_refs.join(',')}`;
    const ordinal=used.get(base)??0;used.set(base,ordinal+1);
    const {record_key,...rest}=sample;return {...rest,evidence_key:ordinal?`${base}#${ordinal}`:base};
  });
}
export function physicalReviewEvidenceFrame(plan,timestamp) {
  const empty={samples:[],total:0,omitted:0};
  if(!Number.isFinite(timestamp)||!range(plan?.time_range)||timestamp<plan.time_range[0]||timestamp>plan.time_range[1])return empty;
  const samples=list(plan.samples);const stamps=[...new Set(samples.map(sample=>sample.timestamp))].sort((a,b)=>a-b);
  if(!stamps.length)return empty;
  const steps=stamps.slice(1).map((value,index)=>value-stamps[index]).filter(value=>value>1e-8),tolerance=Math.min(.100001,steps.length?Math.min(...steps)/2+.000001:.000001);
  const gaps=list(plan.missing_intervals).filter(gap=>range(gap.time_range));
  // A displayable row is a usable position within the sampling tolerance of the tick. A segment start (connect_from_previous!==true)
  // never shows before its own timestamp, so a restart cannot appear early and a gap's end is never presented as continued motion.
  const eligible=samples.filter(sample=>Math.abs(sample.timestamp-timestamp)<=tolerance&&point(sample.world_position)&&USABLE_EVIDENCE.includes(sample.state)&&
    !(sample.connect_from_previous!==true&&sample.timestamp>timestamp+1e-8)&&
    !gaps.some(gap=>timestamp>gap.time_range[0]+1e-8&&timestamp<gap.time_range[1]-1e-8&&Math.abs(sample.timestamp-timestamp)>1e-8&&
      (!list(gap.camera_ids).length||list(gap.camera_ids).includes(sample.camera_id)||list(sample.source_camera_ids).some(camera=>gap.camera_ids.includes(camera)))&&
      (!gap.candidate_ref||!list(sample.candidate_refs).length||sample.candidate_refs.includes(gap.candidate_ref))));
  if(!eligible.length)return empty;
  const nearest=eligible.reduce((best,sample)=>{
    const distance=Math.abs(sample.timestamp-timestamp),current=Math.abs(best-timestamp);
    return distance<current-1e-9||Math.abs(distance-current)<=1e-9&&sample.timestamp<best?sample.timestamp:best;
  },eligible[0].timestamp);
  const usable=evidenceFrameSamples(eligible.filter(sample=>sample.timestamp===nearest));
  return {samples:usable.slice(0,REVIEW_MARKER_LIMIT),total:usable.length,omitted:Math.max(0,usable.length-REVIEW_MARKER_LIMIT)};
}
export function physicalReviewEvidenceAt(plan,timestamp) {
  return physicalReviewEvidenceFrame(plan,timestamp).samples;
}
export function physicalReviewSelection(result,selectedRef=null,currentTimestamp=null,sourceSummary=null,displayOptions={}) {
  validatePhysicalReviewResponse(result);
  const item=selectedPhysicalReviewItem(result,selectedRef);if(!item)return null;
  const window=item.focus.time_range;
  const timestamp=Number.isFinite(currentTimestamp)?Math.max(window[0],Math.min(window[1],currentTimestamp)):
    list(result.synchronized_evidence?.samples).find(sample=>sample.timestamp>=window[0]&&sample.timestamp<=window[1]&&item.focus.camera_ids.includes(sample.camera_id))?.timestamp??window[0];
  return {item_ref:item.item_ref,review_sha256:result.review_sha256,clock_id:result.selection.clock_id,
    camera_ids:[...item.focus.camera_ids],time_range:[...window],timestamp,scene_plan:physicalReviewScenePlan(result,item.item_ref,sourceSummary,displayOptions),
    ownership_confirmed:false,physical_certification:false};
}

function provenanceHTML(result) {
  const samples=list(result.synchronized_evidence?.samples),observed=samples.filter(sample=>sample.state==='PROJECTED_OBSERVATION'&&point(sample.world_position)).length,
    inferred=samples.filter(sample=>['INFERRED_INTERPOLATION','INFERRED_CROSS_CAMERA'].includes(sample.state)&&point(sample.world_position)).length,missing=samples.length-observed-inferred,
    segmentStarts=evidenceFrameSamples(samples.filter(sample=>sample.state==='PROJECTED_OBSERVATION'&&point(sample.world_position))).filter(sample=>sample.segment_start).length,limits=sampleLimits(result.synchronized_evidence??{},samples.length);
  return `<div class="notice warning"><p>原 camera 截圖、校正與來源幾何是實際 Blender 資料；位置是影像投影衍生，跨鏡頭路徑是推斷，活動目標是模擬替代資料。觀測投影 ${observed} 點／推斷 ${inferred} 點／缺失或未知 ${missing} 點、${list(result.synchronized_evidence?.missing_intervals).length} 段。缺失與未分類幾何仍保留未知。</p><p>3D 標記：青綠＝影像投影觀測（來源取樣，非已確認的人員位置）、琥珀＝推斷；外環＝新片段起點（來源標示不與前一點連線，共 ${segmentStarts} 處，不代表同一人連續移動）；缺失區間不顯示任何位置。每個時間點最多顯示 ${REVIEW_MARKER_LIMIT} 個標記${limits.truncated?`；來源取樣已截斷（${limits.sample_count} 筆中僅收 ${samples.length} 筆）`:''}。</p></div>`;
}
function geometryDetailsHTML(primitives) {
  const keys=['kind','units','authority','source_object_id','source_surface_ids','source_face_indices','source_triangle_indices','source_geometry_sha256',
    'source_surface_metadata','triangle_sources','face_mapping','vertices','triangles','rings','truncated','omitted_triangle_count'];
  const data=primitives.map(primitive=>Object.fromEntries(keys.filter(key=>key in primitive).map(key=>[key,primitive[key]])));
  return `<details class="technical"><summary>實際來源頂點、三角形、物件與 face 依據（局部預覽）</summary><pre>${h(JSON.stringify(data,null,2))}</pre></details>`;
}
export function physicalReviewPanelHTML(result,{selectedRef=null,pending=false,error='',decisionsByRef=null,submitting=false,sourceSummary=null,sourcePresentation=null,alignAnnotationTop=false}={}) {
  const head='<div class="panel-head"><div><h2>門洞／走廊／人體淨空待確認</h2><p>來源依據、同步核對與人工清單</p></div><span class="badge purple">本機工程審查</span></div>';
  if(pending)return `<section class="panel physical-review-panel">${head}<div class="panel-body" aria-live="polite">正在載入來源待確認項目…</div></section>`;
  if(!result)return `<section class="panel physical-review-panel">${head}<div class="panel-body"><p>${h(error||'尚未載入待確認項目。')}</p></div></section>`;
  try{validatePhysicalReviewResponse(result);}catch{return `<section class="panel physical-review-panel">${head}<div class="panel-body"><p>來源或範圍不相符，待確認項目未顯示。</p></div></section>`;}
  const item=selectedPhysicalReviewItem(result,selectedRef),primitives=item?result.geometry_primitives.filter(primitive=>item.geometry_refs.includes(primitive.geometry_ref)):[];
  const nominalBody=item?.kind==='BODY_CLEARANCE'?nominalBodyPolicy(result,sourceSummary):null;
  const bodyCaption=item?.kind==='BODY_CLEARANCE'?`<p class="status-text">${nominalBody?`觀測投影點上的名義人體線框：半徑 ${h(nominalBody.radius_m)} m、高度 ${h(nominalBody.height_m)} m，採已批准政策；並非量測身形或淨空認證。推斷位置僅顯示琥珀色點。`:'目前未取得相符的已批准人體政策；只顯示可用位置點，名義身形與淨空保持未知。'}</p>`:'';
  const localDecisions=decisionsByRef??physicalReviewLocalDecisions(result,item?.item_ref);
  const displayLimit=physicalReviewDisplayLimit(result,item?.item_ref,sourcePresentation);
  const displayControl=displayLimit?`<div class="status-text"><label class="motion-sync"><input type="checkbox" data-review-align-display-top ${alignAnnotationTop?'checked':''}> 核對框上緣對齊目前模型的可見上緣</label><p>只調整黃色顯示框。模型上緣是局部顯示裁切邊界，不是已確認牆頂或門孔高度；原來源標註與物理 UNKNOWN 維持。此選項僅存本機，取消可還原來源框。</p></div>`:'';
  const sourceHashes=Object.entries(result.evidence_hashes).map(([name,value])=>`<li>${h(evidenceLabel(name))}：<code>${h(value)}</code></li>`).join('');
  const coverage=result.geometry_coverage??{};
  const context=`<p class="status-text">目前預覽 ${result.geometry_primitives.length} 組來源幾何；${coverage.preview_truncated?'預覽已截斷':'預覽仍只涵蓋列出的局部來源'}，省略 ${h(coverage.omitted_primitive_count??0)} 組。省略處保持未知，沒有全場碰撞或通行認證。</p>${list(result.camera_coverage).length?`<ul class="status-text">${result.camera_coverage.map(camera=>`<li>${h(camera.camera_id)}：原完整來源可用投影 ${h(camera.projected_frame_count??'未知')} 個 frame，${h(camera.state??'UNKNOWN')}。此數量是既有完整來源計數；目前只同步 ${h(interval(camera.display_time_range??result.selection.time_range))}。</li>`).join('')}</ul>`:''}`;
  const form=item?`${displayControl}<form data-physical-review-form data-item-ref="${h(item.item_ref)}"><h4>逐項確認（預設未知）</h4>${item.checklist.map((check,index)=>{
    const saved=localDecisions[check.check_ref]??{},decision=decisions.has(saved.decision)?saved.decision:'UNKNOWN';
    return `<fieldset data-review-check="${h(check.check_ref)}"><legend>${index+1}. ${h(check.title)}</legend><p>所需證據：${h(check.required_evidence.map(ref=>itemEvidenceLabel(item,ref)).join('、')||'尚未提供；保持未知')}</p><label class="field"><span>使用者判定</span><select data-review-decision aria-label="${h(check.title)}判定"><option value="UNKNOWN" ${decision==='UNKNOWN'?'selected':''}>未知／需要更多資料</option><option value="CONFIRMED_LOCAL" ${decision==='CONFIRMED_LOCAL'?'selected':''}>本機支持（不批准來源語意）</option><option value="CONTRADICTED_LOCAL" ${decision==='CONTRADICTED_LOCAL'?'selected':''}>本機矛盾（不改動來源）</option></select></label><p>本次人工核對的來源證據（未預先勾選）：</p>${[...item.evidence_refs,...item.geometry_refs].map(ref=>`<label class="motion-sync"><input type="checkbox" data-review-evidence value="${h(ref)}" ${list(saved.evidence_refs).includes(ref)?'checked':''}> ${h(itemEvidenceLabel(item,ref))}</label>`).join('')}<label class="field"><span>理由／仍缺少的資料</span><textarea data-review-comment maxlength="2000">${h(saved.comment??'')}</textarea></label></fieldset>`;
  }).join('')}<div class="form-two"><label class="field"><span>審查者</span><input data-review-reviewer required maxlength="100" placeholder="填寫本機審查者名稱"></label><label class="field"><span>本次整體理由／仍缺少的資料</span><textarea data-review-reason required maxlength="2000"></textarea></label></div><p class="status-text">提交僅產生本機工程 revision；正式 human semantic／physical 來源檔、既有排序與影片維持原版本。未完成確認不構成物理認證，確認前不重跑。</p><button class="btn primary" type="submit" ${submitting?'disabled':''}>${submitting?'正在儲存本機修訂…':'儲存本機人工判定'}</button><button class="btn ghost" type="button" data-physical-review-export ${(result.review_state?.revision??0)<1?'disabled':''}>匯出本機差異 revision ${h(result.review_state?.revision??0)}</button><p data-review-feedback role="status">${h(error)}</p></form>`:'';
  return `<section class="panel physical-review-panel">${head}<div class="panel-body"><p>所有未確認項目保持 pending／UNKNOWN。選取後聚焦來源 3D 預覽並沿同一 source clock 核對 camera 畫面；鏡頭與軌跡的房間歸屬仍未確認。</p>${provenanceHTML(result)}${context}<div class="physical-review-items">${result.items.map((row,index)=>`<button class="resource-item ${item?.item_ref===row.item_ref?'selected':''}" data-physical-review-item="${h(row.item_ref)}" type="button"><span><strong>${index+1}. ${h(row.title)}</strong><small>${h(kindLabel(row.kind))} · ${h(statusLabel(row.review_status))} · 物理 UNKNOWN</small></span></button>`).join('')}</div>${item?`<h3>${h(item.title)}</h3><p>來源權威：${h(item.source_authority)} · ${h(interval(item.focus.time_range))} · 未確認房間／鏡頭歸屬。</p>${bodyCaption}<h4>具體缺失與待確認</h4><ul>${item.pending_gaps.map(gap=>`<li>${h(gap.description??gap.code)}</li>`).join('')}</ul><h4>目前可見的幾何依據</h4><ul>${primitives.map(primitive=>`<li>${h(basisLabel(primitive.kind))}；${primitive.vertices.length} 頂點／${primitive.triangles.length} 來源三角形；${h(primitive.authority)}${primitive.truncated?'；預覽已截斷，省略處保持未知':''}</li>`).join('')||'<li>幾何缺失；不補造門孔、走廊或淨空。</li>'}</ul>${geometryDetailsHTML(primitives)}${form}`:'<p>目前沒有來源待確認項目；不自動產生核准項目。</p>'}<details class="technical"><summary>來源雜湊與版本綁定</summary><p>原 Blender SHA-256：<code>${h(result.source_sha256)}</code><br>物理來源：<code>${h(result.physical_source_sha256)}</code><br>審查清單：<code>${h(result.review_sha256)}</code><br>Source clock：${h(result.selection.clock_id)} · 既有結果 ${h(result.prior_results.checkpoint??'來源版本')} 保持不變。</p><ul>${sourceHashes}</ul></details></div></section>`;
}

export function physicalReviewDecisionPayload(result,selectedRef,checks) {
  validatePhysicalReviewResponse(result);
  validatePhysicalReviewInput(checks);
  const item=result.items.find(row=>row.item_ref===selectedRef);
  if(!item||!Array.isArray(checks)||checks.length!==item.checklist.length)throw Error('人工判定必須包含目前項目的全部清單。');
  const seen=new Set(),allowedEvidence=new Set([...item.evidence_refs,...item.geometry_refs]);
  const rows=checks.map(row=>{
    if(!checkRef(row.check_ref)||seen.has(row.check_ref)||!item.checklist.some(check=>check.check_ref===row.check_ref)||!decisions.has(row.decision)||
      !Array.isArray(row.evidence_refs)||row.evidence_refs.length>16||new Set(row.evidence_refs).size!==row.evidence_refs.length||row.evidence_refs.some(ref=>!allowedEvidence.has(ref))||typeof row.comment!=='string'||row.comment.length>2000||
      row.decision!=='UNKNOWN'&&(!row.comment.trim()||!row.evidence_refs.length))throw Error('本機人工判定的清單、證據或理由無效。');
    seen.add(row.check_ref);return {check_ref:row.check_ref,decision:row.decision,evidence_refs:[...row.evidence_refs],comment:row.comment.trim()};
  });
  return {review_sha256:result.review_sha256,item_ref:item.item_ref,checks:rows};
}
export function bindPhysicalReviewPanel(container,{getResult=()=>null,current=()=>true,onSelect=()=>{},onSubmit=async()=>{},onSave=null,onExport=()=>{},onDisplayAlign=()=>{},onError=()=>{}}={}) {
  let disposed=false,pending=false;
  const change=event=>{
    const control=event.target;if(!control.matches?.('[data-review-align-display-top]')||!container.contains(control)||disposed||!current())return;
    onDisplayAlign(control.checked===true);
  };
  const click=event=>{
    const exportButton=event.target.closest?.('[data-physical-review-export]');
    if(exportButton&&container.contains(exportButton)&&!exportButton.disabled&&!disposed&&current()){
      const result=getResult();if(result&&Number.isInteger(result.review_state?.revision)&&result.review_state.revision>0)onExport({review_sha256:result.review_sha256,revision:result.review_state.revision});return;
    }
    const button=event.target.closest?.('[data-physical-review-item]');if(!button||!container.contains(button)||disposed||!current())return;
    const result=getResult();if(!result?.items?.some(item=>item.item_ref===button.dataset.physicalReviewItem))return;
    onSelect(button.dataset.physicalReviewItem);
  };
  const submit=async event=>{
    const form=event.target;if(!form.matches?.('[data-physical-review-form]')||!container.contains(form))return;
    event.preventDefault();if(disposed||pending||!current())return;
    const result=getResult(),item=result?.items?.find(row=>row.item_ref===form.dataset.itemRef);
    if(!item)return;
    try{
      const rows=[...form.querySelectorAll('[data-review-check]')].map(field=>({check_ref:field.dataset.reviewCheck,
        decision:field.querySelector('[data-review-decision]')?.value??'UNKNOWN',evidence_refs:[...field.querySelectorAll('[data-review-evidence]')].filter(input=>input.checked).map(input=>input.value),comment:field.querySelector('[data-review-comment]')?.value??''}));
      const payload=physicalReviewDecisionPayload(result,item.item_ref,rows);
      const reviewer=form.querySelector('[data-review-reviewer]')?.value?.trim()??'',reason=form.querySelector('[data-review-reason]')?.value?.trim()??'';
      const revision=result.review_state?.revision;
      if(!reviewer||reviewer.length>100||!reason||reason.length>2000||!Number.isInteger(revision)||revision<0)throw Error('本機人工修訂需審查者、理由與目前 revision。');
      const input={...payload,expected_revision:revision,reviewer,reason};validatePhysicalReviewInput(input);
      pending=true;
      const button=form.querySelector('[type="submit"]');if(button)button.disabled=true;
      await (onSave??onSubmit)(input);
      if(!disposed&&current()&&getResult()?.review_sha256===result.review_sha256){const feedback=form.querySelector('[data-review-feedback]');if(feedback)feedback.textContent='已儲存本機工程修訂；來源權威與既有結果維持不變。';}
    }catch(error){if(!disposed&&current())onError(error);}
    finally{pending=false;const button=form.querySelector('[type="submit"]');if(button&&!disposed&&current())button.disabled=false;}
  };
  container.addEventListener('click',click);container.addEventListener('submit',submit);container.addEventListener('change',change);
  return ()=>{disposed=true;container.removeEventListener('click',click);container.removeEventListener('submit',submit);container.removeEventListener('change',change);};
}

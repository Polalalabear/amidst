// Demo mode (K6): step bookmarks, availability gating, per-step acceptance record. Pure functions first;
// installDemoMode is the only DOM-touching export. Missing data is shown as UNAVAILABLE with a reason, never faked.
export const DEMO_SCHEMA='workbench.demo-acceptance.v1';
export const RESULTS=Object.freeze(['PASS','FAIL','UNKNOWN']);
export const JUMP_TIMES=Object.freeze([0.0,4.6,6.4,8.2]);
export const LABEL_MAX=6;
// Each requirement is satisfied only by real state; reasons name the missing producer.
// The selection must exist in observations the workbench has actually loaded for that time (query observations or the
// physical-review evidence samples). Nothing is synthesised: no match means UNAVAILABLE. demoObservationRef is not consulted.
export function findObservation(state,step){
  if(!step?.selection)return null;
  const t=step.timestamp_s,cams=step.camera_ids??[];
  const inCam=id=>!id||!cams.length||cams.includes(id);
  const sample=(state.physicalReviewResult?.synchronized_evidence?.samples??[]).find(o=>o.observation_ref===step.selection&&Math.abs(o.timestamp-t)<1e-6&&inCam(o.camera_id));
  if(sample)return {observation_ref:step.selection,camera_id:sample.camera_id??null,timestamp:sample.timestamp,source:'physical_review'};
  const obs=(state.observations??[]).find(o=>o.observation_ref===step.selection&&(Number.isFinite(o.timestamp)?Math.abs(o.timestamp-t)<1e-6:Array.isArray(o.time_range)&&o.time_range[0]-1e-6<=t&&t<=o.time_range[1]+1e-6));
  return obs?{observation_ref:step.selection,camera_id:obs.camera_id??obs.camera_ids?.[0]??null,timestamp:t,source:'query'}:null;
}
const REQUIREMENTS=Object.freeze({
  humanoid_scene:s=>s.sceneIds?.includes?.(s.humanoidSceneId??'')?null:'人形場景未載入（需 Demo presets）',
  selection:(s,step)=>findObservation(s,step)?null:`觀測 ${step.selection} 在 ${step.scene_id??s.sceneId??'UNKNOWN'}@${step.timestamp_s}s 不存在`,
  // The outer response may be UNKNOWN by design; only the nested plan stored in state.blindHypothesis counts, and it must be READY.
  blind_hypothesis:s=>!s.blindHypothesis?'尚無盲區假設資料（需 target_reconstruction 回應）':s.blindHypothesis.status==='READY'?null:`盲區假設 ${s.blindHypothesis.status??'UNKNOWN'}：${s.blindHypothesis.reasonText??s.blindHypothesis.reason??'無原因'}`,
  cross_camera_result:s=>s.crossCameraResult?null:'尚未產生跨鏡頭候選結果',
  recommended_view:s=>s.recommendedView?null:'尚無建議檢視檢索結果（等 C5）',
  negative_scene:s=>s.sceneIds?.includes?.(s.negativeSceneId??'')?null:'負例場景 UNKNOWN／未登錄',
});
export function validateSteps(doc){
  const errors=[];
  if(doc?.schema_version!=='workbench.demo-steps.v1')errors.push('schema_version');
  const steps=Array.isArray(doc?.steps)?doc.steps:[];
  steps.forEach((step,i)=>{
    if(step.step!==i+1)errors.push(`step ${i+1}: 序號`);
    if(![...String(step.label??'')].length||[...String(step.label)].length>LABEL_MAX)errors.push(`step ${i+1}: label 需 1–${LABEL_MAX} 字`);
    if(typeof step.key!=='string'||!step.key)errors.push(`step ${i+1}: key`);
    if(!Number.isFinite(step.timestamp_s))errors.push(`step ${i+1}: timestamp_s`);
    if(!Array.isArray(step.camera_ids)||!Array.isArray(step.layers)||!Array.isArray(step.requires))errors.push(`step ${i+1}: 陣列欄位`);
    for(const need of step.requires??[])if(!REQUIREMENTS[need])errors.push(`step ${i+1}: 未知需求 ${need}`);
  });
  return errors;
}
export const GROUPS=Object.freeze({humanoid:'人形（主線）',legacy:'舊 run（備援）'});
// Step set for a group. Legacy uses legacy_run's scene/times/selection; availability is still judged from real state.
export function stepsForGroup(doc,group='humanoid'){
  if(group!=='legacy')return doc.steps.map(s=>({...s,group:'humanoid'}));
  const l=doc.legacy_run??{};
  return doc.steps.map(s=>s.step>6?{...s,group:'legacy'}:{...s,group:'legacy',scene_id:l.scene_id??null,
    timestamp_s:l.timestamps_s?.[s.step]??s.timestamp_s,selection:s.selection?l.selection??null:null,
    requires:s.requires.filter(r=>r!=='humanoid_scene'),expected:l.expected?.[s.step]??s.expected});
}
export function stepAvailability(step,state={},{mock=false}={}){
  const reasons=(step.requires??[]).map(need=>REQUIREMENTS[need]?.(state,step)).filter(Boolean);
  if(!reasons.length)return {available:true,mock:false,reason:null};
  if(mock)return {available:true,mock:true,reason:`MOCK 預覽：${reasons.join('；')}`};
  return {available:false,mock:false,reason:reasons.join('；')};
}
export function canonicalJSON(value){
  if(Array.isArray(value))return `[${value.map(canonicalJSON).join(',')}]`;
  if(value&&typeof value==='object')return `{${Object.keys(value).sort().filter(k=>value[k]!==undefined).map(k=>`${JSON.stringify(k)}:${canonicalJSON(value[k])}`).join(',')}}`;
  return JSON.stringify(value??null);
}
export async function sha256Hex(text,subtle=globalThis.crypto?.subtle){
  if(!subtle)return 'UNKNOWN';
  const digest=await subtle.digest('SHA-256',new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
}
export const stateHash=(value,subtle)=>sha256Hex(canonicalJSON(value),subtle);
export function stepViewState(step,state,availability){
  return {step_group:step.group??'humanoid',step:step.step,key:step.key,scene_id:state.sceneId??null,timestamp_s:state.timestamp??null,camera_ids:[...(state.cameraIds??[])].sort(),
    selection:findObservation(state,step)?step.selection:null,layers:[...step.layers].sort(),available:availability.available,mock:availability.mock};
}
export async function acceptanceRecord(step,state,{availability,result='UNKNOWN',operator_note='',subtle}={}){
  const avail=availability??stepAvailability(step,state);
  // A MOCK preview or an unavailable step can never be recorded as PASS.
  const safe=RESULTS.includes(result)?result:'UNKNOWN';
  const final=safe==='PASS'&&(avail.mock||!avail.available)?'UNKNOWN':safe;
  const hashOf=async v=>v==null?'UNKNOWN':sha256Hex(canonicalJSON(v),subtle);
  return {step_group:step.group??'humanoid',step:step.step,label:step.label,expected:step.expected,result:final,mock:avail.mock,available:avail.available,unavailable_reason:avail.reason,
    state_hash:await stateHash(stepViewState(step,state,avail),subtle),
    data_hashes:{scene:state.snapshot?.source_sha256??state.snapshot?.baseline?.source_features??'UNKNOWN',
      fixture:await hashOf(state.fixtureRef??null),response:state.blindHypothesisSha256??await hashOf(state.blindHypothesis??null)},
    timestamp_s:state.timestamp??null,operator_note:String(operator_note)};
}
export const exportDocument=(demoId,records,group='humanoid')=>({schema_version:DEMO_SCHEMA,demo_id:demoId,step_group:group,records:[...records].sort((a,b)=>a.step-b.step)});
// Set display directly: the overlay's inline display:flex would otherwise override the hidden attribute.
export function watermarkVisible(node,visible){node.style.display=visible?'flex':'none';node.hidden=!visible;}
export const isTypingTarget=t=>!!t&&(['INPUT','TEXTAREA','SELECT'].includes(t.tagName)||t.isContentEditable===true);
export function stepFromKey(event,count){
  if(event.ctrlKey||event.metaKey||event.altKey||isTypingTarget(event.target))return null;
  const n=Number(event.key);return Number.isInteger(n)&&n>=1&&n<=count&&String(n)===event.key?n:null;
}
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function demoBarHTML({steps,current,availability,mock,records,group='humanoid'}){
  const step=steps[current-1];
  const recorded=records.get?.(current);
  return `<div class="demo-bar-row"><strong>Demo ${current}/${steps.length} ${esc(step?.label??'')}</strong> `+
    (step?`<span data-demo-availability="${availability.available?(availability.mock?'MOCK':'AVAILABLE'):'UNAVAILABLE'}">${availability.available?(availability.mock?'MOCK':'可用'):'UNAVAILABLE'}</span>`:'<span>尚未選步驟（按 1–7）</span>')+
    (availability.reason?` <small>${esc(availability.reason)}</small>`:'')+
    ` <label>步驟組：<select data-demo-group>${Object.entries(GROUPS).map(([k,v])=>`<option value="${k}" ${k===group?'selected':''}>${v}</option>`).join('')}</select></label>`+
    ` <label><input type="checkbox" data-demo-mock ${mock?'checked':''}> MOCK 預覽</label>`+
    (step?` <button data-demo-result="PASS">通過</button><button data-demo-result="FAIL">失敗</button><button data-demo-result="UNKNOWN">UNKNOWN</button>`:'')+
    ` <button data-demo-export>匯出紀錄</button>`+(recorded?` <small>本步：${esc(recorded.result)}</small>`:'')+`</div>`;
}
// ctx: {document, steps(doc), getState(), goto(step)}. goto reuses the app's own scene-load / timeline functions.
// App state plus the ids the step file owns; without humanoidSceneId every humanoid step would read as "scene not loaded".
export const demoState=(stepsDoc,appState)=>({...appState,humanoidSceneId:stepsDoc.humanoid_scene_id,negativeSceneId:appState.negativeSceneId});
export function installDemoMode({document:doc,doc:stepsDoc,getState:getAppState,goto,download}){
  const getState=()=>demoState(stepsDoc,getAppState());
  let group='humanoid',steps=stepsForGroup(stepsDoc,group),current=0,mock=false;const records=new Map();
  const bar=doc.createElement('div');bar.className='demo-bar';bar.setAttribute('data-demo-bar','');
  bar.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:50;padding:6px 12px;background:#0b1220;color:#e6edf7;font:13px system-ui;border-top:1px solid #334';
  const mark=doc.createElement('div');mark.setAttribute('data-demo-watermark','');mark.hidden=true;mark.textContent='MOCK';
  mark.style.cssText='position:fixed;inset:0;z-index:49;pointer-events:none;align-items:center;justify-content:center;font:900 20vw system-ui;display:none;color:rgba(255,111,168,.12)';
  const avail=()=>stepAvailability(steps[current-1],getState(),{mock});
  const draw=()=>{watermarkVisible(mark,mock);bar.innerHTML=demoBarHTML({steps,current,availability:current?avail():{available:false,reason:null},mock,records,group});};
  const jump=async n=>{current=n;draw();await goto(steps[n-1]);draw();};
  doc.body.append(mark,bar);draw();
  doc.addEventListener('keydown',e=>{const n=stepFromKey(e,steps.length);if(n){e.preventDefault();jump(n);}});
  bar.addEventListener('change',e=>{
    if(e.target.hasAttribute?.('data-demo-mock')){mock=e.target.checked;draw();}
    if(e.target.hasAttribute?.('data-demo-group')&&GROUPS[e.target.value]){group=e.target.value;steps=stepsForGroup(stepsDoc,group);current=0;records.clear();draw();}
  });
  bar.addEventListener('click',async e=>{
    const b=e.target.closest?.('button');if(!b)return;
    if(b.hasAttribute('data-demo-result')&&current){records.set(current,await acceptanceRecord(steps[current-1],getState(),{availability:avail(),result:b.dataset.demoResult}));draw();}
    if(b.hasAttribute('data-demo-export')){
      // Steps never marked stay in the export as UNKNOWN records.
      const all=await Promise.all(steps.map(s=>records.get(s.step)??acceptanceRecord(s,getState(),{availability:stepAvailability(s,getState(),{mock})})));
      download?.(`demo-acceptance-${stepsDoc.demo_id}-${group}.json`,JSON.stringify(exportDocument(stepsDoc.demo_id,all,group),null,2));
    }
  });
  return {jump,records,get current(){return current;}};
}

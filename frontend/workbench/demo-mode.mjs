// Demo mode (K6): step bookmarks, availability gating, per-step acceptance record. Pure functions first;
// installDemoMode is the only DOM-touching export. Missing data is shown as UNAVAILABLE with a reason, never faked.
import {blindHypothesisFromResponse,blindHypothesisPlan,blindHypothesisAbsentPlan,blindHypothesisRequest} from './blind-hypothesis.mjs';
import {observationRecordsFromResponse,intervalEndRef} from './observation-selection.mjs';
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
const demoRuns=s=>s.demoBlindRuns&&s.demoBlindRuns.sceneId===s.sceneId?s.demoBlindRuns:{};
const REQUIREMENTS=Object.freeze({
  humanoid_scene:s=>s.sceneIds?.includes?.(s.humanoidSceneId??'')?null:'人形場景未載入（需 Demo presets）',
  selection:(s,step)=>findObservation(s,step)?null:`觀測 ${step.selection} 在 ${step.scene_id??s.sceneId??'UNKNOWN'}@${step.timestamp_s}s 不存在`,
  // The outer response may be UNKNOWN by design; only the nested plan stored in state.blindHypothesis counts, and it must be READY.
  blind_hypothesis:s=>!s.blindHypothesis?'尚無盲區假設資料（需 target_reconstruction 回應）':s.blindHypothesis.status==='READY'?null:`盲區假設 ${s.blindHypothesis.status??'UNKNOWN'}：${s.blindHypothesis.reasonText??s.blindHypothesis.reason??'無原因'}`,
  // D19: BASELINE is a second request that carries the NONE response's output_sha256; it counts only once its own plan is READY.
  blind_baseline:s=>{const run=demoRuns(s).BASELINE;return !run?'尚無 BASELINE 重算結果（需先有 NONE 回應）':run.plan?.status==='READY'?null:`BASELINE 重算 ${run.plan?.status??'UNKNOWN'}：${run.plan?.reasonText??run.plan?.reason??'無原因'}`;},
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
    for(const need of [...(step.requires??[]),...(step.optional_requires??[])])if(!REQUIREMENTS[need])errors.push(`step ${i+1}: 未知需求 ${need}`);
  });
  return errors;
}
export const GROUPS=Object.freeze({humanoid:'人形（主線）',legacy:'舊 run（備援）'});
// Step set for a group. Legacy uses legacy_run's scene/times/selection; availability is still judged from real state.
export function stepsForGroup(doc,group='humanoid'){
  if(group!=='legacy')return doc.steps.map(s=>({...s,group:'humanoid'}));
  const l=doc.legacy_run??{};
  return doc.steps.map(s=>s.key==='negative_case'?{...s,group:'legacy'}:{...s,group:'legacy',scene_id:l.scene_id??null,
    timestamp_s:l.timestamps_s?.[s.step]??s.timestamp_s,selection:s.selection?l.selection??null:null,
    requires:s.requires.filter(r=>r!=='humanoid_scene'),expected:l.expected?.[s.step]??s.expected});
}
export function stepAvailability(step,state={},{mock=false,loading=false}={}){
  const reasons=(step.requires??[]).map(need=>REQUIREMENTS[need]?.(state,step)).filter(Boolean);
  // optional_requires: parts of a step that may be UNAVAILABLE while the rest still runs; listed, and they block PASS.
  const partial=(step.optional_requires??[]).map(need=>({part:need,reason:REQUIREMENTS[need]?.(state,step)})).filter(p=>p.reason);
  if(!reasons.length)return {available:true,mock:false,reason:null,partial};
  if(mock)return {available:true,mock:true,reason:`MOCK 預覽：${reasons.join('；')}`,partial};
  if(loading)return {available:false,pending:true,mock:false,reason:'載入中…',partial:[]};
  return {available:false,mock:false,reason:reasons.join('；'),partial};
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
  const final=safe==='PASS'&&(avail.mock||!avail.available||avail.partial?.length)?'UNKNOWN':safe;
  const hashOf=async v=>v==null?'UNKNOWN':sha256Hex(canonicalJSON(v),subtle);
  return {step_group:step.group??'humanoid',step:step.step,label:step.label,expected:step.expected,result:final,mock:avail.mock,available:avail.available,unavailable_reason:avail.reason,unavailable_parts:(avail.partial??[]).map(p=>({part:p.part,reason:p.reason})),
    blind_runs:blindRunSummary(state),
    state_hash:await stateHash(stepViewState(step,state,avail),subtle),
    data_hashes:{scene:state.snapshot?.source_sha256??state.snapshot?.baseline?.source_features??'UNKNOWN',
      fixture:await hashOf(state.fixtureRef??null),response:state.blindHypothesisSha256??await hashOf(state.blindHypothesis??null)},
    timestamp_s:state.timestamp??null,operator_note:String(operator_note)};
}
export function blindRunSummary(state){
  const runs=demoRuns(state);
  return {none_sha256:runs.NONE?.sha??null,none_area_m2:runs.NONE?.area_m2??null,baseline_sha256:runs.BASELINE?.sha??null,baseline_area_m2:runs.BASELINE?.area_m2??null};
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
export function demoBarHTML({steps,current,availability,mock,records,group='humanoid',notes=''}){
  const step=steps[current-1];
  const recorded=records.get?.(current);
  return `<div class="demo-bar-row"><strong>Demo ${current}/${steps.length} ${esc(step?.label??'')}</strong> `+
    (step?`<span data-demo-availability="${availability.pending?'PENDING':availability.available?(availability.mock?'MOCK':'AVAILABLE'):'UNAVAILABLE'}">${availability.pending?'載入中':availability.available?(availability.mock?'MOCK':'可用'):'UNAVAILABLE'}</span>`:`<span>尚未選步驟（按 1–${steps.length}）</span>`)+
    (availability.reason?` <small>${esc(availability.reason)}</small>`:'')+
    (availability.partial?.length?` <small data-demo-partial>部分 UNAVAILABLE：${availability.partial.map(p=>`${esc(p.part)}（${esc(p.reason)}）`).join('；')}</small>`:'')+
    (notes?` <small data-demo-notes>${esc(notes)}</small>`:'')+
    ` <label>步驟組：<select data-demo-group>${Object.entries(GROUPS).map(([k,v])=>`<option value="${k}" ${k===group?'selected':''}>${v}</option>`).join('')}</select></label>`+
    ` <label><input type="checkbox" data-demo-mock ${mock?'checked':''}> MOCK 預覽</label>`+
    (step?` <button data-demo-result="PASS">通過</button><button data-demo-result="FAIL">失敗</button><button data-demo-result="UNKNOWN">UNKNOWN</button>`:'')+
    ` <button data-demo-export>匯出紀錄</button>`+(recorded?` <small>本步：${esc(recorded.result)}</small>`:'')+`</div>`;
}
// ctx: {document, steps(doc), getState(), goto(step)}. goto reuses the app's own scene-load / timeline functions.
// App state plus the ids the step file owns; without humanoidSceneId every humanoid step would read as "scene not loaded".
// Sum of the response's reachable_regions[].area_m2; null when absent or any area is not a finite number (never guessed).
export function reachableAreaM2(response){
  const regions=blindHypothesisFromResponse(response)?.reachable_regions;
  if(!Array.isArray(regions)||!regions.length||regions.some(r=>!Number.isFinite(r?.area_m2)))return null;
  return regions.reduce((sum,r)=>sum+r.area_m2,0);
}
const m2=v=>`${v.toFixed(3)} m²`;
export const NO_EXCLUSION_TEXT='這段影格沒有提供足夠的排除證據';
// NONE vs BASELINE comparison, computed from the responses; zero difference says so instead of implying convergence.
export function areaComparison(none,baseline){
  const a=none?.area_m2,b=baseline?.area_m2;
  if(!Number.isFinite(a)||!Number.isFinite(b))return {state:'UNKNOWN',none_m2:a??null,baseline_m2:b??null,delta_m2:null,delta_pct:null,text:`可達面積對照 UNKNOWN：${Number.isFinite(a)?'':'缺 NONE 面積'}${!Number.isFinite(a)&&!Number.isFinite(b)?'、':''}${Number.isFinite(b)?'':'缺 BASELINE 面積'}`};
  const delta=b-a,pct=a===0?null:delta/a*100,same=Math.abs(delta)<1e-6;
  const head=`NONE ${m2(a)} → BASELINE ${m2(b)}（差 ${m2(delta)}${pct===null?'':`，${pct.toFixed(1)}%`}）`;
  return {state:same?'SAME':'CHANGED',none_m2:a,baseline_m2:b,delta_m2:delta,delta_pct:pct,text:same?`${head}。${NO_EXCLUSION_TEXT}。`:head};
}
export function demoBlindRequest(sceneId,selection,observationRef,{mode,previousSha256=null}){
  if(mode!=='NONE'&&mode!=='BASELINE')throw new Error(`未知的負面證據模式 ${mode}`);
  if(mode==='BASELINE'&&!/^[0-9a-f]{64}$/.test(previousSha256??''))throw new Error('BASELINE 需要 NONE 回應的 output_sha256');
  return {...blindHypothesisRequest(sceneId,selection,observationRef),negative_evidence_mode:mode,...(mode==='BASELINE'?{previous_response_sha256:previousSha256}:{})};
}
// One explicit request per mode. The run is stored per scene; the displayed plan (state.blindHypothesis) follows the mode just run.
export async function runDemoBlind(target,selection,observationRef,mode,send,onChange=()=>{}){
  const runs=target.demoBlindRuns?.sceneId===target.sceneId?target.demoBlindRuns:(target.demoBlindRuns={sceneId:target.sceneId});
  const request=demoBlindRequest(target.sceneId,selection,observationRef,{mode,previousSha256:runs.NONE?.sha});
  const ticket={sceneEpoch:target.sceneEpoch,sceneId:target.sceneId,epoch:(target.demoBlindEpoch=(target.demoBlindEpoch??0)+1)};
  const current=()=>target.sceneEpoch===ticket.sceneEpoch&&target.sceneId===ticket.sceneId&&target.demoBlindEpoch===ticket.epoch;
  target.blindHypothesisPending=true;onChange();
  try{
    const result=await send(request);if(!current())return false;
    const nested=blindHypothesisFromResponse(result);
    const plan=blindHypothesisPlan(result)??blindHypothesisAbsentPlan(result);
    const sha=typeof nested?.output_sha256==='string'&&/^[0-9a-f]{64}$/.test(nested.output_sha256)?nested.output_sha256:null;
    runs[mode]={plan,sha,area_m2:reachableAreaM2(result),observations:observationRecordsFromResponse(result),interval_end_ref:intervalEndRef(result)};
    target.blindHypothesis=plan;target.blindHypothesisSha256=sha;target.blindHypothesisPending=false;onChange();return true;
  }catch(error){if(current()){target.blindHypothesisPending=false;onChange();}throw error;}
}
// What entering a step needs: NONE for step 3; NONE then BASELINE for step 5. Existing runs are reused, then shown.
export async function ensureDemoBlind(target,step,selection,send,{show=true,onChange=()=>{}}={}){
  if(!step?.blind_mode||!selection)return false;
  let changed=false;
  const keep={plan:target.blindHypothesis,sha:target.blindHypothesisSha256};
  const runs=()=>target.demoBlindRuns?.sceneId===target.sceneId?target.demoBlindRuns:{};
  if(!runs().NONE)changed=await runDemoBlind(target,selection,step.selection,'NONE',send,onChange)||changed;
  if(step.blind_mode==='BASELINE'&&runs().NONE?.sha&&!runs().BASELINE)changed=await runDemoBlind(target,selection,step.selection,'BASELINE',send,onChange)||changed;
  const shown=runs()[step.blind_mode];
  // show:false loads the records (for the selection panel) without changing which hypothesis plan is displayed.
  if(show&&shown){target.blindHypothesis=shown.plan;target.blindHypothesisSha256=shown.sha;changed=true;}
  else if(!show){target.blindHypothesis=keep.plan;target.blindHypothesisSha256=keep.sha;}
  return changed;
}
export function demoNotes(step,state){
  if(!step?.blind_mode)return '';
  const runs=demoRuns(state);
  if(step.blind_mode==='NONE')return runs.NONE?(Number.isFinite(runs.NONE.area_m2)?`NONE 可達面積 ${m2(runs.NONE.area_m2)}`:'NONE 可達面積 UNKNOWN'):'';
  return runs.NONE||runs.BASELINE?areaComparison(runs.NONE,runs.BASELINE).text:'';
}
// Request scope for the step-3 auto-load: the step's cameras over the scene's whole range, like the manual 盲區假設 button.
export function blindAutoSelection(snapshot,step){
  const range=snapshot?.time_range;
  if(!step?.selection||!step.blind_mode||!Array.isArray(range)||!Number.isFinite(range[0])||!Number.isFinite(range[1])||!step.camera_ids?.length)return null;
  return {camera_ids:[...step.camera_ids],start:range[0],end:range[1],top_k:3};
}
export const demoState=(stepsDoc,appState)=>({...appState,humanoidSceneId:stepsDoc.humanoid_scene_id,negativeSceneId:appState.negativeSceneId});
export function installDemoMode({document:doc,doc:stepsDoc,getState:getAppState,goto,download}){
  const getState=()=>demoState(stepsDoc,getAppState());
  let group='humanoid',steps=stepsForGroup(stepsDoc,group),current=0,mock=false;const records=new Map();
  const bar=doc.createElement('div');bar.className='demo-bar';bar.setAttribute('data-demo-bar','');
  bar.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:50;padding:6px 12px;background:#0b1220;color:#e6edf7;font:13px system-ui;border-top:1px solid #334';
  const mark=doc.createElement('div');mark.setAttribute('data-demo-watermark','');mark.hidden=true;mark.textContent='MOCK';
  mark.style.cssText='position:fixed;inset:0;z-index:49;pointer-events:none;align-items:center;justify-content:center;font:900 20vw system-ui;display:none;color:rgba(255,111,168,.12)';
  let loading=false;
  const avail=()=>stepAvailability(steps[current-1],getState(),{mock,loading});
  const draw=()=>{watermarkVisible(mark,mock);bar.innerHTML=demoBarHTML({steps,current,availability:current?avail():{available:false,reason:null},mock,records,group,notes:current?demoNotes(steps[current-1],getState()):''});};
  const jump=async n=>{current=n;loading=true;draw();try{await goto(steps[n-1]);}finally{loading=false;draw();}};
  doc.body.append(mark,bar);draw();
  doc.addEventListener('demo-redraw',()=>draw());
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

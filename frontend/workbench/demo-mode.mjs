// Demo mode (K6): step bookmarks, availability gating, per-step acceptance record. Pure functions first;
// installDemoMode is the only DOM-touching export. Missing data is shown as UNAVAILABLE with a reason, never faked.
export const DEMO_SCHEMA='workbench.demo-acceptance.v1';
export const RESULTS=Object.freeze(['PASS','FAIL','UNKNOWN']);
export const JUMP_TIMES=Object.freeze([0.0,4.6,6.4,8.2]);
export const LABEL_MAX=6;
// Each requirement is satisfied only by real state; reasons name the missing producer.
const REQUIREMENTS=Object.freeze({
  humanoid_scene:s=>s.sceneIds?.includes?.(s.humanoidSceneId??'')?null:'人形 run 場景尚未註冊',
  selection:(s,step)=>s.demoObservationRef&&s.demoObservationRef===step.selection?null:'場景預設觀測未載入或與步驟不符',
  blind_hypothesis:s=>s.blindHypothesis?null:'尚無盲區假設資料（等 C4b 後端整合）',
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
  return {step:step.step,key:step.key,scene_id:state.sceneId??null,timestamp_s:state.timestamp??null,camera_ids:[...(state.cameraIds??[])].sort(),
    selection:state.demoObservationRef??null,layers:[...step.layers].sort(),available:availability.available,mock:availability.mock};
}
export async function acceptanceRecord(step,state,{availability,result='UNKNOWN',operator_note='',subtle}={}){
  const avail=availability??stepAvailability(step,state);
  // A MOCK preview or an unavailable step can never be recorded as PASS.
  const safe=RESULTS.includes(result)?result:'UNKNOWN';
  const final=safe==='PASS'&&(avail.mock||!avail.available)?'UNKNOWN':safe;
  const hashOf=async v=>v==null?'UNKNOWN':sha256Hex(canonicalJSON(v),subtle);
  return {step:step.step,label:step.label,expected:step.expected,result:final,mock:avail.mock,available:avail.available,unavailable_reason:avail.reason,
    state_hash:await stateHash(stepViewState(step,state,avail),subtle),
    data_hashes:{scene:state.snapshot?.source_sha256??state.snapshot?.baseline?.source_features??'UNKNOWN',
      fixture:await hashOf(state.fixtureRef??null),response:await hashOf(state.blindHypothesis??null)},
    timestamp_s:state.timestamp??null,operator_note:String(operator_note)};
}
export const exportDocument=(demoId,records)=>({schema_version:DEMO_SCHEMA,demo_id:demoId,records:[...records].sort((a,b)=>a.step-b.step)});
export const isTypingTarget=t=>!!t&&(['INPUT','TEXTAREA','SELECT'].includes(t.tagName)||t.isContentEditable===true);
export function stepFromKey(event,count){
  if(event.ctrlKey||event.metaKey||event.altKey||isTypingTarget(event.target))return null;
  const n=Number(event.key);return Number.isInteger(n)&&n>=1&&n<=count&&String(n)===event.key?n:null;
}
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function demoBarHTML({steps,current,availability,mock,records}){
  const step=steps[current-1];
  const recorded=records.get?.(current);
  return `<div class="demo-bar-row"><strong>Demo ${current}/${steps.length} ${esc(step?.label??'')}</strong> `+
    (step?`<span data-demo-availability="${availability.available?(availability.mock?'MOCK':'AVAILABLE'):'UNAVAILABLE'}">${availability.available?(availability.mock?'MOCK':'可用'):'UNAVAILABLE'}</span>`:'<span>尚未選步驟（按 1–7）</span>')+
    (availability.reason?` <small>${esc(availability.reason)}</small>`:'')+
    ` <label><input type="checkbox" data-demo-mock ${mock?'checked':''}> MOCK 預覽</label>`+
    (step?` <button data-demo-result="PASS">通過</button><button data-demo-result="FAIL">失敗</button><button data-demo-result="UNKNOWN">UNKNOWN</button>`:'')+
    ` <button data-demo-export>匯出紀錄</button>`+(recorded?` <small>本步：${esc(recorded.result)}</small>`:'')+`</div>`;
}
// ctx: {document, steps(doc), getState(), goto(step)}. goto reuses the app's own scene-load / timeline functions.
export function installDemoMode({document:doc,doc:stepsDoc,getState,goto,download}){
  const steps=stepsDoc.steps;let current=0,mock=false;const records=new Map();
  const bar=doc.createElement('div');bar.className='demo-bar';bar.setAttribute('data-demo-bar','');
  bar.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:50;padding:6px 12px;background:#0b1220;color:#e6edf7;font:13px system-ui;border-top:1px solid #334';
  const mark=doc.createElement('div');mark.setAttribute('data-demo-watermark','');mark.hidden=true;mark.textContent='MOCK';
  mark.style.cssText='position:fixed;inset:0;z-index:49;pointer-events:none;display:flex;align-items:center;justify-content:center;font:900 20vw system-ui;color:rgba(255,111,168,.12)';
  const avail=()=>stepAvailability(steps[current-1],getState(),{mock});
  const draw=()=>{mark.hidden=!mock;bar.innerHTML=demoBarHTML({steps,current,availability:current?avail():{available:false,reason:null},mock,records});};
  const jump=async n=>{current=n;draw();await goto(steps[n-1]);draw();};
  doc.body.append(mark,bar);draw();
  doc.addEventListener('keydown',e=>{const n=stepFromKey(e,steps.length);if(n){e.preventDefault();jump(n);}});
  bar.addEventListener('change',e=>{if(e.target.hasAttribute?.('data-demo-mock')){mock=e.target.checked;draw();}});
  bar.addEventListener('click',async e=>{
    const b=e.target.closest?.('button');if(!b)return;
    if(b.hasAttribute('data-demo-result')&&current){records.set(current,await acceptanceRecord(steps[current-1],getState(),{availability:avail(),result:b.dataset.demoResult}));draw();}
    if(b.hasAttribute('data-demo-export')){
      // Steps never marked stay in the export as UNKNOWN records.
      const all=await Promise.all(steps.map(s=>records.get(s.step)??acceptanceRecord(s,getState(),{availability:stepAvailability(s,getState(),{mock})})));
      download?.(`demo-acceptance-${stepsDoc.demo_id}.json`,JSON.stringify(exportDocument(stepsDoc.demo_id,all),null,2));
    }
  });
  return {jump,records,get current(){return current;}};
}

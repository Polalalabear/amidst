// 俯視圖 panel for the tracking result (mount point #track-map-slot, UI-C of DEMO_UI_SUPPORT_V1 §7).
// Follows store.tUs: prediction requests use as_of_us=t, throttled; the drawing is rebuilt from data <= t on every change,
// so scrubbing backwards removes lines that only existed later. The external-guess switch is off for every new response.
import {buildScene,EXTERNAL_LABEL} from './track-map-model.mjs';
import {renderPanelHtml} from './track-map-render.mjs';
import {createTrackMapData} from './track-map-data.mjs';
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};
export async function loadFixture(fetchImpl=globalThis.fetch) {
  try{const r=await fetchImpl(new URL('./fixtures/track-map/synthetic.json',import.meta.url));return r.ok?await r.json():null;}catch{return null;}
}
export function mount({store,api,root=document,fetchImpl=globalThis.fetch,fixture=null,throttleMs=250,setTimer=globalThis.setTimeout,clearTimer=globalThis.clearTimeout}) {
  const slot=root.querySelector('#track-map-slot');
  if(!slot)return {destroy(){}};
  const body=el('div',undefined,'tm-body'),toggle=el('input'),toggleLabel=el('label',undefined,'tm-ext-toggle'),toggleText=el('span',EXTERNAL_LABEL),toggleNote=el('span',undefined,'note');
  toggle.type='checkbox';toggle.checked=false;toggle.setAttribute('aria-label',EXTERNAL_LABEL);toggleLabel.append(toggle,toggleText,toggleNote);
  slot.replaceChildren(body,toggleLabel);
  let fx=fixture,data=null,responseKey=null,mapKey=null,map=null,physical=null,external=null,timer=null,destroyed=false,generation=0;
  const offline=()=>store.getState().bootstrap?.data_origin==='SYNTHETIC_FIXTURE';
  const mkData=()=>createTrackMapData({fetchImpl,getSession:()=>api?.getSession?.()??null,fixture:fx,offline:offline()});
  const refOf=q2=>q2?.session_id??q2?.output_sha256??null;
  function scene(s) {
    const origins=[map?.origin,physical?.origin,toggle.checked?external?.origin:null].filter(Boolean);
    const synthetic=!origins.length||origins.includes('SYNTHETIC');
    return buildScene({cameraMap:map?.doc,timeline:s.q2?.timeline??[],tUs:s.tUs,physical:physical?.doc,external:external?.doc,externalEnabled:toggle.checked,
      origin:synthetic?'SYNTHETIC':'API',sourceNote:synthetic?'鏡頭圖／預測介面尚未接後端':null,runCameraIds:s.activeRun?.camera_ids??s.q2?.resolved_scope?.camera_ids??null});
  }
  function render() {
    if(destroyed)return;const s=store.getState();
    if(!s.q2){body.textContent='';toggleLabel.hidden=true;return;}
    toggleLabel.hidden=false;toggleNote.textContent=external?.doc?.status==='UNAVAILABLE'&&external?.origin==='API'?'（外部推測不可用）':offline()||!map||map.origin!=='API'||external?.origin!=='API'?'（SYNTHETIC 錄製重播示意）':'（錄製重播）';
    body.innerHTML=renderPanelHtml(scene(s));
  }
  async function fetchAt() {
    timer=null;if(destroyed)return;const s=store.getState(),ref=refOf(s.q2);if(!s.q2||!ref)return;
    const token=generation,asOfUs=s.tUs,timeline=s.q2.timeline;
    const scope=s.q2.resolved_scope??{};
    const key=`${scope.scene_id}:${scope.run_ids?.[0]}`;
    if(mapKey!==key){mapKey=key;map=await data.cameraMap({scene_id:scope.scene_id,run_id:scope.run_ids?.[0]});if(token!==generation)return;}
    physical=await data.physical({responseRef:ref,asOfUs,timeline});
    if(token!==generation)return;
    if(toggle.checked)external=await data.external({responseRef:ref,asOfUs,timeline});
    if(token===generation)render();
  }
  let ready=null;
  const init=()=>ready??=(async()=>{if(!fx)fx=await loadFixture(fetchImpl);data=mkData();})();
  async function onChange() {
    await init();if(destroyed)return;const s=store.getState();
    const key=refOf(s.q2);
    if(key!==responseKey){responseKey=key;mapKey=null;map=null;physical=null;external=null;toggle.checked=false;generation++;data.forget();}
    render();
    if(s.q2&&timer===null)timer=setTimer(fetchAt,throttleMs);
  }
  toggle.addEventListener('change',()=>{external=null;render();if(toggle.checked&&timer===null)timer=setTimer(fetchAt,0);});
  const unsubscribe=store.subscribe(()=>{onChange();});onChange();
  return {destroy(){destroyed=true;generation++;unsubscribe();if(timer!==null)clearTimer(timer);slot.replaceChildren();},_flush:fetchAt};
}

// 單純顯示模式 (simple view) vs 系統模式 (system view). Presentation only: both share one store and one DOM, so switching never reloads or moves playback.
// The simple view hides annotations with CSS (`body.view-simple`, simple-view.css) and adds one right-top "證據不足" line.
// That line is derived only from state the system view already has (the q2 timeline segment, the response error, a MISSING frame cell); it never reads GT, renderer trajectories, visibility or depth.
import {sessionModel} from './q2-session-model.mjs';
import {lastSourceTime} from './q-playback.mjs';

export const VIEW_KEY='amidst.workbench-v2.view.v1';
export const VIEWS=Object.freeze(['system','simple']);
export const INSUFFICIENT_TEXT='證據不足';
const norm=v=>VIEWS.includes(v)?v:null;

export function readStoredView(storage){try{return norm(storage?.getItem?.(VIEW_KEY));}catch{return null;}}
export function writeStoredView(view,storage){try{if(norm(view))storage?.setItem?.(VIEW_KEY,view);}catch{}}
// `?view=simple|system` wins over the remembered choice; the default is the system view.
export function resolveView(search,storage){
  let fromUrl=null;try{fromUrl=norm(new URLSearchParams(search??'').get('view'));}catch{}
  return fromUrl??readStoredView(storage)??'system';
}

// True when the q2 view at the current time shows no matching observation: GAP / TEMP_LOST / SEARCHING / UNKNOWN, an incomplete journal, or a fail-closed error.
// Same inputs as q2-view.render (shown time and artifacts), non-review model.
export function evidenceInsufficient(s,{missingFrame=false}={}){
  if(!s||s.task!=='q2')return false;
  if(s.error)return true;
  if(!s.q2)return false;
  if(missingFrame)return true;
  try{
    const end=s.q2.timeline.at(-1)?.range_us[1]??1,shown=lastSourceTime(s.tUs,s.q2.timeline[0]?.range_us[0]??0,end);
    const model=sessionModel(s.q2,shown,{...s.artifacts,review:false});
    return !model.segment||model.segment.kind!=='ON_CAMERA'||!model.camera;
  }catch{return true;}
}

const el=(doc,tag,text,cls)=>{const n=doc.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export function mountSimpleView({doc=document,store,url=doc.baseURI??globalThis.location?.href??'http://localhost/',storage=globalThis.localStorage??null}){
  const body=doc.body,main=doc.querySelector('#q-main-view'),bar=doc.querySelector('.topbar');
  let view=resolveView(new URL(url).search,storage),destroyed=false,observer=null;
  const seg=el(doc,'div',undefined,'seg view-seg');seg.id='view-seg';seg.setAttribute('aria-label','顯示方式');
  const buttons=new Map(VIEWS.map(v=>{const b=el(doc,'button',v==='simple'?'單純顯示':'系統模式');b.type='button';b.dataset.view=v;b.onclick=()=>set(v);seg.append(b);return [v,b];}));
  const anchor=doc.querySelector('#search-open');if(bar)anchor?bar.insertBefore(seg,anchor):bar.append(seg);
  const notice=el(doc,'div',INSUFFICIENT_TEXT,'simple-notice');notice.id='simple-notice';notice.hidden=true;notice.setAttribute('role','status');if(main)main.append(notice);
  const missing=()=>Boolean(doc.querySelector('#q2-slot .q2-media[data-status="MISSING"]'));
  function refresh(){
    if(destroyed)return;
    body.classList.toggle('view-simple',view==='simple');body.dataset.view=view;
    for(const [v,b] of buttons)b.setAttribute('aria-pressed',String(v===view));
    notice.hidden=!(view==='simple'&&evidenceInsufficient(store.getState(),{missingFrame:missing()}));
  }
  function set(next){if(!norm(next)||next===view)return;view=next;writeStoredView(view,storage);refresh();}
  const unsubscribe=store.subscribe(refresh);
  if(typeof MutationObserver==='function'){const slot=doc.querySelector('#q2-slot');if(slot){observer=new MutationObserver(refresh);observer.observe(slot,{subtree:true,attributes:true,attributeFilter:['data-status']});}}
  refresh();
  return {get view(){return view;},set,refresh,destroy(){destroyed=true;unsubscribe();observer?.disconnect();seg.remove();notice.remove();body.classList.remove('view-simple');delete body.dataset.view;}};
}

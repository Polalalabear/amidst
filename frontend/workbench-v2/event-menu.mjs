// 事件選單：把全部 demo 事件放進工作台。純呈現；不讀資料、不推論。
//  - 同源事件（監控牆、Q1、B-05b）以帶參數重新載入本頁切換（乾淨狀態）。
//  - 跨埠事件（B-05a live：另一個 P1 進程；複雜事件 A4-1／B4-1：唯讀 event-viewer）以 iframe 內嵌，不改它們的資料來源與讀取範圍，也不需要 CORS。
// 對方埠由啟動腳本用 ?ev_live=<埠>&ev_cx=<埠> 帶入；主機固定 127.0.0.1，埠只收 1024–65535 的整數。
export const B05B_RECORDING_ID='2777741d96ac9aff5bffb2f61a4d2938';
export const INSUFFICIENT='證據不足';
export const LOOPBACK='127.0.0.1';
import {trackingStatus,modeStatus} from './tracking-source.mjs';
const VIEWS=['system','simple'],MODES=['view','track','find'],LAYOUTS=['single','multi'];

export const EVENTS=Object.freeze([
  {id:'wall',label:'監控牆',kind:'page',note:'B-01：A、B 兩台預錄畫面同一時鐘播放，每格左上角是來源時間；沒有畫面的鏡頭標 MISSING，不是「沒人」。'},
  {id:'q1',label:'Q1 找相機',kind:'page',note:'B-02／B-03：按「檢索」→「查找」person、0:00:00–0:00:08；命中是條件相符的觀測，不是同一個人，身分 UNCONFIRMED；進度條是示意。'},
  {id:'b05b',label:'B-05b 預錄切鏡',kind:'page',recording:B05B_RECORDING_ID,note:'預錄、工程場景：5.10 s 單畫面是 A，5.15 s 起切到 B；虛線是輔助預測（示意，非實際路徑）；不是 G4、不是正式核定。'},
  {id:'b05a',label:'B-05a live 追蹤',kind:'embed',port:'live',path:'/workbench-v2/',note:'live 但預期 fail-closed：檢索→追蹤→點第一列起點→拖時間軸到 5.10／5.15／5.20 s；全程停在 A（5.20 s 仍是 A＋GAP），鏡頭關係圖未核准，系統不猜、不切鏡。'},
  {id:'a41',label:'複雜事件 A4-1',kind:'embed',port:'cx',path:'/',run:'A4-1',note:'只有影像、無推論、無身分（ENGINEERING）：4 鏡頭 5 fps；frame 62＝12.40 s、frame 100＝20.00 s；目前評分器與規則還判斷不了，是 Line 2 要研究的。'},
  {id:'b41',label:'複雜事件 B4-1',kind:'embed',port:'cx',path:'/',run:'B4-1',note:'只有影像、無推論、無身分（ENGINEERING）：5 鏡頭 5 fps，frame 0–209；frame 105＝21.00 s；資料是工程模擬，身分 UNCONFIRMED，物理通行 UNKNOWN。'},
]);

export function validPort(value){
  if(typeof value!=='string'||!/^\d{1,5}$/.test(value))return null;
  const n=Number(value);return n>=1024&&n<=65535?n:null;
}
export function parseConfig(search){
  let p;try{p=new URLSearchParams(search??'');}catch{p=new URLSearchParams();}
  const ev=p.get('ev'),view=p.get('view'),mode=p.get('mode'),layout=p.get('layout'),evmode=p.get('evmode');
  return {ev:EVENTS.some(e=>e.id===ev)?ev:null,embed:p.get('embed')==='1',view:VIEWS.includes(view)?view:null,mode:MODES.includes(mode)?mode:null,layout:LAYOUTS.includes(layout)?layout:'single',evmode:MODES.includes(evmode)?evmode:null,ports:{live:validPort(p.get('ev_live')),cx:validPort(p.get('ev_cx'))}};
}
export function available(entry,cfg){return entry.kind==='page'||cfg.ports[entry.port]!==null;}
export function embedOrigin(entry,cfg){const port=cfg.ports[entry.port];return port?`http://${LOOPBACK}:${port}`:null;}
export function defaultMode(entry){return entry.id==='q1'?'find':trackingStatus(entry.id).status==='AVAILABLE'?'track':'view';}
// view＝所有畫面一次全部顯示；track＝系統追蹤（單畫面鎖定／多畫面並標出追蹤所在鏡頭）。無追蹤輸出的事件只有 view。
export function modeOf(entry,cfg){
  const want=cfg.mode??defaultMode(entry);
  return modeStatus(entry.id,want).status==='NONE'?'view':want;
}
export function embedSrc(entry,cfg,view,mode='view'){
  const origin=embedOrigin(entry,cfg);if(!origin)return null;
  if(modeStatus(entry.id,mode).status==='NOT_PRODUCED')return null;  // 不捏造：沒有追蹤／查找輸出就不載入畫面
  const u=new URL(entry.path,origin);u.searchParams.set('embed','1');u.searchParams.set('view',VIEWS.includes(view)?view:'system');
  if(entry.run)u.searchParams.set('run',entry.run);
  if(entry.port==='live')u.searchParams.set('evmode',mode==='track'?'track':'view');
  return u.toString();
}
// Same-origin page URL for a page event; keeps the sibling-port config so the menu works after the reload.
export function pageUrl(entry,cfg,base,{mode=null,layout=null}={}){
  const m=mode??cfg.mode??defaultMode(entry),u=new URL(base);u.search='';
  u.searchParams.set('ev',entry.id);
  if(m==='track'&&entry.recording)u.searchParams.set('recording',entry.recording);
  if(cfg.ports.live)u.searchParams.set('ev_live',String(cfg.ports.live));
  if(cfg.ports.cx)u.searchParams.set('ev_cx',String(cfg.ports.cx));
  if(cfg.view)u.searchParams.set('view',cfg.view);
  u.searchParams.set('mode',m);
  if(m==='track')u.searchParams.set('layout',layout??cfg.layout);
  return u.toString();
}
// Embedded workbench side: accept a view switch only from the parent window on loopback.
export function acceptViewMessage(event,parentWindow){
  if(!event||event.source!==parentWindow)return null;
  if(!/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(String(event.origin)))return null;
  const d=event.data;return d&&d.type==='amidst.view'&&VIEWS.includes(d.view)?d.view:null;
}
export function acceptLayoutMessage(event,parentWindow){
  if(!event||event.source!==parentWindow)return null;
  if(!/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(String(event.origin)))return null;
  const d=event.data;return d&&d.type==='amidst.layout'&&LAYOUTS.includes(d.layout)?d.layout:null;
}

const el=(doc,tag,text,cls)=>{const n=doc.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const MODE_LABELS={view:'查看',track:'追蹤',find:'查找'},LAYOUT_LABELS={single:'單畫面鎖定',multi:'多畫面'};
export function mountEventMenu({doc=document,simple,store=null,url=doc.baseURI??globalThis.location?.href??'http://localhost/',win=globalThis.window}){
  const cfg=parseConfig(new URL(url).search),body=doc.body;
  if(cfg.embed){
    // Embedded in another workbench: no menu of our own; the parent drives the view and the tracking layout.
    body.classList.add('ev-embedded');
    if(cfg.evmode==='view')body.classList.add('ev-mode-view');
    const onMessage=e=>{const v=acceptViewMessage(e,win?.parent);if(v){simple?.set(v);return;}const l=acceptLayoutMessage(e,win?.parent);if(l)store?.dispatch({type:'SET_PLAYBACK_MODE',value:l});};
    win?.addEventListener?.('message',onMessage);
    return {destroy(){win?.removeEventListener?.('message',onMessage);}};
  }
  const bar=doc.querySelector('.topbar'),sectionMain=doc.querySelector('section.main');
  const label=el(doc,'label','','ev-field');label.append(el(doc,'span','事件','lbl'));
  const select=el(doc,'select');select.id='event-select';select.setAttribute('aria-label','事件');
  for(const e of EVENTS){const o=el(doc,'option',available(e,cfg)?e.label:`${e.label}（未啟動）`);o.value=e.id;o.disabled=!available(e,cfg);select.append(o);}
  label.append(select);
  const modeSeg=el(doc,'div','','seg ev-seg');modeSeg.id='ev-mode';modeSeg.setAttribute('aria-label','模式');
  const layoutSeg=el(doc,'div','','seg ev-seg');layoutSeg.id='ev-layout';layoutSeg.setAttribute('aria-label','追蹤版面');
  const modeBtns=new Map(MODES.map(m=>{const b=el(doc,'button',MODE_LABELS[m]);b.type='button';b.dataset.mode=m;modeSeg.append(b);return [m,b];}));
  const layoutBtns=new Map(LAYOUTS.map(l=>{const b=el(doc,'button',LAYOUT_LABELS[l]);b.type='button';b.dataset.layout=l;layoutSeg.append(b);return [l,b];}));
  const note=el(doc,'div','','ev-note');note.id='event-note';note.setAttribute('role','note');
  const stage=el(doc,'div','','ev-stage');stage.id='event-stage';stage.hidden=true;
  const frame=el(doc,'iframe');frame.id='event-frame';frame.title='事件';frame.setAttribute('referrerpolicy','no-referrer');frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms');
  const notice=el(doc,'div','','ev-notice');notice.id='ev-notice';notice.hidden=true;notice.setAttribute('role','status');
  const noticeFull=el(doc,'p','','ev-notice-full'),noticeSimple=el(doc,'span',INSUFFICIENT,'ev-notice-simple');notice.append(noticeFull,noticeSimple);
  stage.append(frame,notice);
  if(bar){const anchor=bar.querySelector('.field')??bar.querySelector('.spacer');for(const n of [label,modeSeg,layoutSeg])bar.insertBefore(n,anchor);}
  if(sectionMain){sectionMain.insertBefore(note,sectionMain.firstChild);sectionMain.append(stage);}
  const entryOf=id=>EVENTS.find(e=>e.id===id);
  let current=cfg.ev&&available(entryOf(cfg.ev),cfg)?cfg.ev:(cfg.ev===null&&new URL(url).searchParams.get('recording')===B05B_RECORDING_ID?'b05b':'wall');
  let layout=cfg.layout,mode=modeOf(entryOf(current),cfg),applied=false;
  const view=()=>body.dataset.view==='simple'?'simple':'system';
  const origin=()=>{const e=entryOf(current);return e.kind==='embed'?embedOrigin(e,cfg):null;};
  const push=()=>{const o=origin();if(!o||!frame.contentWindow)return;frame.contentWindow.postMessage({type:'amidst.view',view:view()},o);if(mode==='track')frame.contentWindow.postMessage({type:'amidst.layout',layout},o);};
  const pushLayout=()=>{
    const e=entryOf(current);
    if(e.kind==='embed'){const o=origin();if(o&&mode==='track')frame.contentWindow?.postMessage({type:'amidst.layout',layout},o);}
    else if(mode==='track'&&trackingStatus(e.id).status==='AVAILABLE')store?.dispatch({type:'SET_PLAYBACK_MODE',value:layout});
  };
  function refreshControls(){
    const e=entryOf(current),st=trackingStatus(e.id).status;
    for(const [m,b] of modeBtns){const ms=modeStatus(e.id,m);b.setAttribute('aria-pressed',String(m===mode));b.disabled=ms.status==='NONE';b.title=ms.status==='NONE'?ms.reason:'';}
    layoutSeg.hidden=!(mode==='track'&&st==='AVAILABLE');
    for(const [l,b] of layoutBtns)b.setAttribute('aria-pressed',String(l===layout));
  }
  function show(id){
    current=id;const e=entryOf(id);select.value=id;note.textContent=e.note;
    const embedded=e.kind==='embed',blocked=embedded&&mode!=='view'&&modeStatus(id,mode).status==='NOT_PRODUCED';
    body.classList.toggle('ev-embed-active',embedded);body.dataset.event=id;body.dataset.evMode=mode;stage.hidden=!embedded;
    notice.hidden=!blocked;noticeFull.textContent=blocked?modeStatus(id,mode).reason:'';
    if(embedded){const src=embedSrc(e,cfg,view(),mode);if(src){if(frame.getAttribute('src')!==src)frame.setAttribute('src',src);}else frame.removeAttribute('src');}
    else frame.removeAttribute('src');
    refreshControls();
  }
  function applyPageLayout(){
    // The recorded Q2 response sets the layout to single when it loads; apply the chosen layout once it is there.
    if(!store||applied||entryOf(current).kind!=='page'||mode!=='track')return;
    if(store.getState().q2){applied=true;if(layout!=='single')pushLayout();}
  }
  // 查找：本頁事件載入來源後，自動打開檢索對話框並選好「查找」（不送出，由使用者按「開始檢索」）。
  let findOpened=false;
  function applyPageFind(){
    if(findOpened||mode!=='find'||entryOf(current).kind!=='page'||modeStatus(current,'find').status!=='AVAILABLE'||!store?.getState().activeRun)return;
    findOpened=true;const radio=doc.querySelector('input[name="search-mode"][value="find"]');radio?.click?.();doc.querySelector('#search-open')?.click?.();
  }
  const unsubA=store?.subscribe?.(applyPageLayout),unsubB=store?.subscribe?.(applyPageFind),unsub=()=>{unsubA?.();unsubB?.();};
  select.onchange=()=>{
    const e=entryOf(select.value);if(!e||!available(e,cfg)){select.value=current;return;}
    const m=modeOf(e,{...cfg,mode:null});
    if(e.kind==='page'){win.location.assign(pageUrl(e,{...cfg,view:view()},url,{mode:m,layout}));return;}
    mode=m;show(e.id);
    try{win.history.replaceState(null,'',pageUrl(e,{...cfg,view:view()},url,{mode,layout}));}catch{/* history unavailable: the page still works */}
  };
  for(const [m,b] of modeBtns)b.onclick=()=>{
    const e=entryOf(current);if(m===mode||b.disabled)return;
    if(e.kind==='page'){win.location.assign(pageUrl(e,{...cfg,view:view()},url,{mode:m,layout}));return;}
    mode=m;show(current);try{win.history.replaceState(null,'',pageUrl(e,{...cfg,view:view()},url,{mode,layout}));}catch{}
  };
  for(const [l,b] of layoutBtns)b.onclick=()=>{layout=l;refreshControls();pushLayout();};
  frame.onload=push;
  let observer=null;
  if(typeof MutationObserver==='function'){observer=new MutationObserver(push);observer.observe(body,{attributes:true,attributeFilter:['data-view']});}
  show(current);applyPageLayout();applyPageFind();
  return {get current(){return current;},get mode(){return mode;},get layout(){return layout;},show,destroy(){unsub?.();observer?.disconnect();for(const n of [label,modeSeg,layoutSeg,note,stage])n.remove();body.classList.remove('ev-embed-active','ev-embedded','ev-mode-view');delete body.dataset.event;delete body.dataset.evMode;}};
}

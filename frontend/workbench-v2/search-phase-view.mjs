// Renders the search phase over the main view: loading screen + illustrative progress while searching,
// plus the 俯視圖 mount point (UI-C) once a tracking result is shown. Camera views stay hidden until a result exists.
import {progressPercent} from './search-phase-model.mjs';
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};
export function mount({phase,root=document,tickMs=100,setTimer=globalThis.setInterval,clearTimer=globalThis.clearInterval}) {
  const view=root.querySelector('#q-main-view'),slot=root.querySelector('#search-phase-slot'),map=root.querySelector('#track-map-slot'),end=root.querySelector('#search-end');
  if(!view||!slot)return {destroy(){}};
  const title=el('strong',undefined,'sp-title'),bar=el('div',undefined,'sp-bar'),fill=el('span'),label=el('p',undefined,'sp-label note'),reason=el('p',undefined,'sp-reason');
  bar.setAttribute('role','progressbar');bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');bar.append(fill);
  const spinner=el('span',undefined,'sp-spin');slot.append(spinner,title,bar,label,reason);
  function render(p){
    view.dataset.searchPhase=p.phase;
    slot.hidden=p.phase!=='searching';
    if(map){map.hidden=!(p.phase==='result'&&p.mode==='track');map.textContent='俯視圖 · UI-C 待接';}
    if(end)end.hidden=p.phase==='wall';
    if(p.phase!=='searching')return;
    const pct=progressPercent(p.progress);fill.style.width=pct+'%';bar.setAttribute('aria-valuenow',String(pct));
    title.textContent=p.miss?'尚未找到':'載入中…';
    label.textContent=p.miss?'進度條為示意，未完成。':`示意進度 ${pct}%（非實際進度）`;
    reason.hidden=!p.miss;reason.textContent=p.miss?`${p.miss.code} · ${p.miss.message}`:'';
    slot.dataset.state=p.miss?'miss':p.resolved?'done':'wait';
  }
  if(end)end.onclick=()=>phase.dispatch({type:'SEARCH_END'});
  const unsub=phase.subscribe(render);render(phase.getState());
  let last=Date.now();const timer=setTimer(()=>{const now=Date.now();phase.dispatch({type:'TICK',dtMs:now-last});last=now;},tickMs);
  return {destroy(){unsub();clearTimer(timer);if(end)end.onclick=null;slot.replaceChildren();}};
}

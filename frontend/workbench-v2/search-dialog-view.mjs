// Toolbar 檢索 icon + modal dialog (mode, condition, feature text, human-readable time range).
// Submitting hands the request to the shared execute() and starts the search phase; backend API is untouched.
import {SEARCH_MODES,buildSearchRequest,formatHms,ERROR_TEXT} from './search-dialog-model.mjs';
import {displayOptions,regionOptions} from './query-alias-model.mjs';
import {vocabulary} from './q3-bar-model.mjs';
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};
export function mount({store,api,execute,phase,root=document}) {
  const button=root.querySelector('#search-open');if(!button)return {destroy(){}};
  const dialog=el('dialog',undefined,'search-dialog');dialog.setAttribute('aria-label','檢索');
  const form=el('form',undefined,'search-form');form.method='dialog';
  const field=(label,control,cls)=>{const l=el('label',undefined,cls);l.append(el('span',label),control);return l;};
  const modeBox=el('div',undefined,'search-modes');modeBox.setAttribute('role','radiogroup');modeBox.setAttribute('aria-label','檢索模式');
  const modeInputs={};let chosen='track';
  for(const [key,m] of Object.entries(SEARCH_MODES)){const r=el('input');r.type='radio';r.name='search-mode';r.value=key;r.checked=key===chosen;r.onchange=()=>{chosen=key;};
    const l=el('label',undefined,'search-mode');l.append(r,el('strong',m.label),el('small',m.hint));modeBox.append(l);modeInputs[key]=r;}
  const regions=el('select');regions.setAttribute('aria-label','區域');
  const classes=el('select'),colors=el('select'),start=el('input'),end=el('input'),text=el('input'),parser=el('select');
  classes.setAttribute('aria-label','類別');colors.setAttribute('aria-label','顏色');
  start.setAttribute('aria-label','開始時間（時:分:秒）');end.setAttribute('aria-label','結束時間（時:分:秒）');text.setAttribute('aria-label','特徵描述');
  for(const x of [start,end]){x.type='text';x.inputMode='numeric';x.placeholder='0:00:00';x.autocomplete='off';}
  text.type='text';text.maxLength=4096;text.placeholder='例如：穿紅衣的人（填寫後以文字解析為準）';
  const rule=el('option','規則解析'),llm=el('option','Qwen3 解析（失敗時用規則）');rule.value='RULE_ONLY';llm.value='LLM_WITH_RULE_FALLBACK';parser.append(rule,llm);
  const times=el('div',undefined,'search-times');times.append(field('開始 時:分:秒',start),field('結束 時:分:秒',end));
  const hint=el('p',undefined,'note search-vocab'),error=el('p',undefined,'search-error');error.setAttribute('role','alert');error.hidden=true;
  const actions=el('div',undefined,'search-actions'),cancel=el('button','取消'),go=el('button','開始檢索');cancel.type='button';go.type='submit';go.className='ibtn primary';cancel.className='ibtn';actions.append(cancel,go);
  form.append(el('h2','檢索'),modeBox,field('條件：類別',classes),field('區域（僅查找）',regions),field('條件：顏色（person）',colors),field('特徵描述（選填）',text),field('解析方式',parser),times,hint,error,actions);dialog.append(form);root.body.append(dialog);
  let lastRun=null;
  function fill(s){
    go.disabled=!s.activeRun||s.loading;llm.disabled=!s.activeRun?.q3_llm_available;
    if(s.activeRun===lastRun)return;lastRun=s.activeRun;classes.replaceChildren();colors.replaceChildren();
    for(const c of s.activeRun?.supported_classes.class_labels??[]){const o=el('option',displayOptions(s.activeRun.supported_classes.class_labels,s.activeRun.supported_classes.aliases??{}).find(x=>x.value===c).label);o.value=c;classes.append(o);}classes.value='person';
    for(const c of ['',...(s.activeRun?.supported_classes.color_vocabulary.labels??[])]){const o=el('option',({'red':'紅色','blue':'藍色'}[c]??c)||'不指定');o.value=c;colors.append(o);}
    regions.replaceChildren();const catalog=regionOptions(s.activeRun);const any=el('option',catalog.status==='READY'?'不指定':'UNKNOWN · 區域資料未提供');any.value='';regions.append(any);for(const r of catalog.options){const o=el('option',r.label);o.value=r.value;regions.append(o);}regions.disabled=catalog.status!=='READY';
    start.value='0:00:00';end.value=formatHms(s.activeRun?.clock_mapping?.source_duration_us??0);hint.textContent=vocabulary(s.activeRun);
  }
  const open=()=>{fill(store.getState());error.hidden=true;if(typeof dialog.showModal==='function'&&!dialog.open)dialog.showModal();else dialog.setAttribute('open','');};
  const close=()=>{if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');};
  button.onclick=open;cancel.onclick=close;
  form.onsubmit=e=>{e.preventDefault();const s=store.getState();
    try {
      if(parser.value==='LLM_WITH_RULE_FALLBACK'&&!s.activeRun?.q3_llm_available)throw new Error('Q3_LLM_NOT_CONFIGURED');
      const request=buildSearchRequest(s.activeRun,api.getSession(),{mode:chosen,regionId:regions.value,text:text.value,classLabel:classes.value,colorLabel:colors.value,start:start.value,end:end.value,parserMode:parser.value},s.switchMode);
      if(chosen==='track')store.dispatch({type:'SET_PLAYBACK_MODE',value:'single'});
      phase.dispatch({type:'SEARCH_START',mode:chosen});close();execute(request);
    } catch(err){error.textContent=`未執行 · ${ERROR_TEXT[err.message]??err.message}`;error.hidden=false;}
  };
  const unsub=store.subscribe(fill);fill(store.getState());
  return {open,destroy(){unsub();button.onclick=null;dialog.remove();}};
}

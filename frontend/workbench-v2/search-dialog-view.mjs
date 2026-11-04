// Toolbar 檢索 icon + modal dialog (mode, condition, feature text, human-readable time range).
// Submitting hands the request to the shared execute() and starts the search phase; backend API is untouched.
import {SEARCH_MODES,buildSearchRequest,formatHms,formatVirtualInput,parseSearchTime,ERROR_TEXT} from './search-dialog-model.mjs';
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
  const classes=el('select'),colors=el('select'),regions=el('select'),start=el('input'),end=el('input'),text=el('input'),parser=el('select');
  classes.setAttribute('aria-label','類別');colors.setAttribute('aria-label','顏色');
  regions.setAttribute('aria-label','地點（區域）');regions.setAttribute('data-search-region','');
  start.setAttribute('aria-label','開始時間（演示時間或經過時間）');end.setAttribute('aria-label','結束時間（演示時間或經過時間）');text.setAttribute('aria-label','特徵描述');
  for(const x of [start,end]){x.type='text';x.inputMode='numeric';x.placeholder='2026-11-01 13:00:00 或 0:00:00';x.autocomplete='off';}
  text.type='text';text.maxLength=4096;text.placeholder='例如：穿紅衣的人（填寫後以文字解析為準）';
  const rule=el('option','規則解析'),llm=el('option','Qwen3 解析（失敗時用規則）');rule.value='RULE_ONLY';llm.value='LLM_WITH_RULE_FALLBACK';parser.append(rule,llm);
  // 選取優先：開始／結束用下拉選單（演示時間，附經過時間）；手動輸入收進「進階」，只是輔助，送出時以輸入框內容為準（與選單同步）。
  const startSel=el('select'),endSel=el('select');startSel.setAttribute('aria-label','開始時間');endSel.setAttribute('aria-label','結束時間');
  const times=el('div',undefined,'search-times'),adv=el('details',undefined,'search-adv');adv.append(el('summary','進階：手動輸入時間（演示時間或經過 時:分:秒）'),field('開始',start),field('結束',end));
  times.append(field('開始（選取）',startSel),field('結束（選取）',endSel),adv);
  const timeNote=el('p',undefined,'note search-time-note'),hint=el('p',undefined,'note search-vocab'),error=el('p',undefined,'search-error');error.setAttribute('role','alert');error.hidden=true;
  const actions=el('div',undefined,'search-actions'),cancel=el('button','取消'),go=el('button','開始檢索');cancel.type='button';go.type='submit';go.className='ibtn primary';cancel.className='ibtn';actions.append(cancel,go);
  form.append(el('h2','檢索'),modeBox,field('條件：類別',classes),field('條件：顏色（person）',colors),field('地點（區域）',regions),field('特徵描述（輔助，選填；填寫後以文字解析為準）',text),field('解析方式',parser),times,timeNote,hint,error,actions);dialog.append(form);root.body.append(dialog);
  let lastRun=null;
  function updatePlaceholders() {
    if (chosen === 'track') {
      start.placeholder = '空著代表現在（演示時間或經過時間）';
      end.placeholder = '空著代表現在（演示時間或經過時間）';
    } else {
      start.placeholder = '2026-11-01 13:00:00 或 0:00:00';
      end.placeholder = '2026-11-01 13:00:00 或 0:00:00';
    }
  }
  for(const [key,m] of Object.entries(SEARCH_MODES)){
    const r=modeInputs[key];
    if(r) r.onchange=()=>{
      chosen=key;
      updatePlaceholders();
      if(chosen==='track'){start.value='';end.value='';startSel.value='';endSel.value='';}
      else{const mapping=store.getState().activeRun?.clock_mapping,duration=mapping?.source_duration_us??0;start.value=formatVirtualInput(0,mapping)??'0:00:00';end.value=formatVirtualInput(duration,mapping)??formatHms(duration);startSel.value=formatHms(0);endSel.value=formatHms(duration);}
      showNote();
    };
  }
  updatePlaceholders();
  // Shows the other form of each typed time: virtual (declared DEMO clock, start + source time) <-> elapsed source time. Read-only; nothing is sent from here.
  function showNote(){
    if(chosen==='track'&&!start.value.trim()&&!end.value.trim()){
      timeNote.textContent='追蹤模式：時間空著代表現在（以目前播放時間為準）。';
      return;
    }
    const mapping=store.getState().activeRun?.clock_mapping,one=x=>{try{const us=parseSearchTime(x.value,mapping),vt=formatVirtualInput(us,mapping);return `${vt?`${vt}（UTC+8 以宣告時鐘換算）= `:''}經過 ${formatHms(us)}`.replace('UTC+8 以宣告時鐘換算','演示時間');}catch{return '格式無法辨識';}};
    timeNote.textContent=mapping?`演示時鐘（DECLARED_DEMO_CLOCK）：起點 + 來源時間。開始＝${one(start)}；結束＝${one(end)}`:'此來源沒有宣告的演示時鐘：演示時間 UNKNOWN，請用經過時間 時:分:秒。';
  }
  // Options every second (every 10 s for long runs); value = elapsed H:MM:SS, label = declared virtual time + elapsed.
  function fillTimes(mapping,duration){
    const step=duration>120e6?10e6:1e6;startSel.replaceChildren();endSel.replaceChildren();
    if(chosen==='track'){
      const nowOpt1=el('option','空著代表現在');nowOpt1.value='';startSel.append(nowOpt1);
      const nowOpt2=el('option','空著代表現在');nowOpt2.value='';endSel.append(nowOpt2);
    }
    const points=[];for(let us=0;us<=duration;us+=step)points.push(us);if(points.at(-1)!==duration)points.push(duration);
    for(const us of points)for(const sel of [startSel,endSel]){const vt=formatVirtualInput(us,mapping),o=el('option',`${vt?`${vt}（經過 ${formatHms(us)}）`:`經過 ${formatHms(us)}`}`);o.value=formatHms(us);sel.append(o);}
    if(chosen==='track'){startSel.value='';endSel.value='';start.value='';end.value='';}
    else{startSel.value=formatHms(0);endSel.value=formatHms(duration);}
  }
  const fromSel=(sel,input)=>()=>{input.value=sel.value;showNote();};
  startSel.onchange=fromSel(startSel,start);endSel.onchange=fromSel(endSel,end);
  start.oninput=showNote;end.oninput=showNote;
  function fill(s){
    go.disabled=!s.activeRun||s.loading;llm.disabled=!s.activeRun?.q3_llm_available;
    if(s.activeRun===lastRun)return;lastRun=s.activeRun;classes.replaceChildren();colors.replaceChildren();regions.replaceChildren();
    for(const c of s.activeRun?.supported_classes.class_labels??[]){const o=el('option',c);o.value=c;classes.append(o);}classes.value='person';
    for(const c of ['',...(s.activeRun?.supported_classes.color_vocabulary.labels??[])]){const o=el('option',c||'不指定');o.value=c;colors.append(o);}
    const emptyRegion=el('option','不指定');emptyRegion.value='';regions.append(emptyRegion);
    const regList=s.activeRun?.regions??s.regionGraph?.regions??s.activeRun?.region_graph?.regions??s.regions??[];
    for(const r of regList){
      const val=typeof r==='string'?r:(r.value??r.region_id);
      const lbl=typeof r==='string'?r:(r.label??r.display_name??r.region_id??val);
      const o=el('option',lbl);o.value=val;regions.append(o);
    }
    const mapping=s.activeRun?.clock_mapping,duration=mapping?.source_duration_us??0;
    hint.textContent=vocabulary(s.activeRun);fillTimes(mapping,duration);
    if(chosen==='track'){start.value='';end.value='';}
    else{start.value=formatVirtualInput(0,mapping)??'0:00:00';end.value=formatVirtualInput(duration,mapping)??formatHms(duration);}
    showNote();
  }
  const open=()=>{fill(store.getState());error.hidden=true;if(typeof dialog.showModal==='function'&&!dialog.open)dialog.showModal();else dialog.setAttribute('open','');};
  const close=()=>{if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');};
  button.onclick=open;cancel.onclick=close;
  form.onsubmit=e=>{e.preventDefault();const s=store.getState();
    try {
      if(parser.value==='LLM_WITH_RULE_FALLBACK'&&!s.activeRun?.q3_llm_available)throw new Error('Q3_LLM_NOT_CONFIGURED');
      const playbackNowUs=s.tUs??0;
      const request=buildSearchRequest(s.activeRun,api.getSession(),{
        mode:chosen,
        text:text.value,
        classLabel:classes.value,
        colorLabel:colors.value,
        regionId:regions.value||undefined,
        regionIds:regions.value?[regions.value]:[],
        start:start.value,
        end:end.value,
        parserMode:parser.value,
        playbackNowUs,
        allowNowTime:true,
      },s.switchMode,{allowNowTime:true,playbackNowUs});
      if(chosen==='track')store.dispatch({type:'SET_PLAYBACK_MODE',value:'single'});
      phase.dispatch({type:'SEARCH_START',mode:chosen});close();execute(request);
    } catch(err){error.textContent=`未執行 · ${ERROR_TEXT[err.message]??err.message}`;error.hidden=false;}
  };
  const unsub=store.subscribe(fill);fill(store.getState());
  return {open,destroy(){unsub();button.onclick=null;dialog.remove();}};
}

import {parsePresentation,manualRequest,editedRequest,textRequest,vocabulary} from './q3-bar-model.mjs';
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};
export function mount({store,slots,api,execute}) {
  const root=slots.query;root.replaceChildren();const form=el('form',undefined,'q3-form'),input=el('input'),submit=el('button','解析'),status=el('span','輸入查詢','q3-status');
  input.setAttribute('aria-label','文字查詢');input.placeholder='輸入類別、顏色與起訖時間';input.maxLength=4096;submit.type='submit';
  const parserMode=el('select');parserMode.setAttribute('aria-label','Q3 解析模式');
  const rule=el('option','規則解析'),llm=el('option','Qwen3 解析（失敗時用規則）');
  rule.value='RULE_ONLY';llm.value='LLM_WITH_RULE_FALLBACK';parserMode.append(rule,llm);parserMode.value='RULE_ONLY';
  const manual=el('details',undefined,'q3-popover'),summary=el('summary','條件表單'),panel=el('div',undefined,'q3-panel');manual.append(summary,panel);
  const classes=el('select'),colors=el('select'),start=el('input'),end=el('input'),send=el('button','執行條件');
  classes.setAttribute('aria-label','類別');colors.setAttribute('aria-label','顏色');start.setAttribute('aria-label','來源起點（微秒）');end.setAttribute('aria-label','來源終點（微秒）');for(const x of [start,end]){x.type='number';x.step='1';x.min='0';}
  const add=(label,control)=>{const l=el('label',label);l.append(control);panel.append(l);};add('類別',classes);add('顏色（person）',colors);add('來源起點 µs',start);add('來源終點 µs',end);send.type='button';panel.append(send);
  const terms=el('p',undefined,'q3-vocabulary');panel.append(terms);
  const audit=el('details',undefined,'q3-popover'),auditSummary=el('summary','解析與結構化查詢'),auditPanel=el('div',undefined,'q3-panel'),auditPre=el('pre'),editor=el('textarea'),rerun=el('button','以修改後的查詢執行');
  editor.setAttribute('aria-label','結構化查詢 JSON');rerun.type='button';auditPanel.append(auditPre,editor,rerun);audit.append(auditSummary,auditPanel);
  const options=el('div',undefined,'q3-options');form.append(input,parserMode,submit,status,manual,audit,options);root.append(form);
  const fail=e=>{status.textContent=`未執行 · ${e.message}`;};
  const onSubmit=e=>{e.preventDefault();try{const s=store.getState();if(parserMode.value==='LLM_WITH_RULE_FALLBACK'&&!s.activeRun?.q3_llm_available)throw new Error('Q3_LLM_NOT_CONFIGURED');execute(textRequest(s.activeRun,api.getSession(),input.value,parserMode.value));}catch(e){fail(e);}};
  form.addEventListener('submit',onSubmit);
  send.onclick=()=>{try{const s=store.getState();execute(manualRequest(s.activeRun,api.getSession(),{task:s.task,classLabel:classes.value,colorLabel:colors.value,startUs:Number(start.value),endUs:Number(end.value),switchMode:s.switchMode}));manual.open=false;}catch(e){fail(e);}};
  rerun.onclick=()=>{try{execute(editedRequest(editor.value,api.getSession()));audit.open=false;}catch(e){fail(e);}};
  let run=null,response=null,lastLoading=null;
  function render(s){
    submit.disabled=!s.activeRun||s.loading;send.disabled=!s.activeRun||s.loading;
    parserMode.disabled=!s.activeRun||s.loading;llm.disabled=!s.activeRun?.q3_llm_available;
    if(s.activeRun!==run){run=s.activeRun;classes.replaceChildren();colors.replaceChildren();
      parserMode.value='RULE_ONLY';
      for(const c of run?.supported_classes.class_labels??[]){const o=el('option',c);o.value=c;classes.append(o);}classes.value='person';
      for(const c of ['',...(run?.supported_classes.color_vocabulary.labels??[])]){const o=el('option',c||'不指定');o.value=c;colors.append(o);}
      start.value='0';end.value=String(run?.clock_mapping?.source_duration_us??0);terms.textContent=vocabulary(run);
    }
    if(s.q3===response&&s.loading===lastLoading)return;response=s.q3;lastLoading=s.loading;
    const m=parsePresentation(response,{review:s.reviewMode});status.textContent=s.loading?'處理中…':m.message;
    status.title=s.reviewMode?`${response?.status??''} · ${response?.reason??''}`:'';audit.hidden=!s.reviewMode||!response;auditSummary.textContent=response?`解析：${response.parsed_by==='RULE'?'規則 ⓡ':'LLM'}${response.fallback_reason?' · '+response.fallback_reason:''}`:'解析與結構化查詢';
    auditPre.textContent=JSON.stringify(m.audit,null,2);editor.value=response?.structured_query?JSON.stringify(response.structured_query,null,2):'';editor.hidden=!response?.structured_query;rerun.hidden=!response?.structured_query;
    options.replaceChildren();for(const choice of m.options){const text=typeof choice==='string'?choice:choice.label??choice.value;const button=el('button',text);button.type='button';button.onclick=()=>{input.value=text;input.focus();};options.append(button);}
  }
  const unsub=store.subscribe(render);render(store.getState());return {destroy(){unsub();form.removeEventListener('submit',onSubmit);root.replaceChildren();}};
}

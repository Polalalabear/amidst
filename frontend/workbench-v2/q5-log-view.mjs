import {logModel} from './q5-log-model.mjs';import {formatSource} from './q-time.mjs';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export function mount({store,slots}){
  const root=slots.log;let key='';function render(s){const next=JSON.stringify([s.task,s.reviewMode,s.q2?.output_sha256,s.artifacts.decisions?.length]);if(next===key)return;key=next;root.replaceChildren();if(!s.reviewMode||s.task!=='q2')return;
    root.className='q5-log';root.append(el('h3','Q5 逐步紀錄（錄製）'));let rows;try{rows=logModel(s.artifacts.decisions??[],{review:true});}catch{root.append(el('p','UNKNOWN · 決策紀錄不完整'));return;}
    if(!rows.length)root.append(el('p','尚無可用決策紀錄'));
    for(const row of rows){const details=el('details',undefined,'q5-step'),summary=el('summary',`#${row.step} ${row.transition} · ${row.badge}${row.accepted?'':' · 拒絕 '+row.rejection_code}`),jump=el('button',`${formatSource(row.source_time_us)} · 跳至此筆`);
      jump.onclick=()=>{store.dispatch({type:'PAUSE'});store.dispatch({type:'SET_T_US',tUs:row.source_time_us});store.dispatch({type:'SELECT',selection:{kind:'INSPECT_DECISION',decision_id:row.id}});};
      const pre=el('pre',JSON.stringify({submitted:row.submitted,accepted:row.accepted,rejection_code:row.rejection_code,executed_action:row.executed_action,candidates:row.candidates,rounds_used:row.rounds_used,session_agent_rounds_used:row.session_agent_rounds_used,budget_used_ms:row.budget_used_ms,llm_calls:row.llm_calls,tools:row.tools},null,2));details.append(summary,jump,pre);if(row.rationale)details.append(el('p',`Agent 說明，不是證據：${row.rationale}`));root.append(details);
    }
  }const unsub=store.subscribe(render);render(store.getState());return {destroy(){unsub();root.replaceChildren();}};
}

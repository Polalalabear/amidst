// GAP caption model. `timeline[].gap_states` is the union of every state the session passed through anywhere in the
// merged GAP segment (q5_controller._gap), so it includes later states; it is history, not the state at time t.
// The caption therefore reads only the decision journal: the latest decision at or before t.
import {Q_STATES} from './q-tokens.mjs';
export function gapStateAt(decisions,tUs){
  if(!Array.isArray(decisions)||!Number.isSafeInteger(tUs))return null;
  const past=decisions.filter(d=>d&&Number.isSafeInteger(d.source_time_us)&&d.source_time_us<=tUs)
    .sort((a,b)=>a.source_time_us-b.source_time_us||(a.step_index??0)-(b.step_index??0));
  const state=past.at(-1)?.state_after;
  return typeof state==='string'&&Object.hasOwn(Q_STATES,state)?state:null;
}
export function gapCaption(state){
  return state?`目前狀態：${Q_STATES[state].label}（${state}）`:'目前狀態：UNKNOWN（沒有此時間點的決策紀錄）';
}

// Search phase state machine: wall -> searching -> result. No DOM. The progress bar is an illustration (示意) only:
// it creeps toward a ceiling while waiting, runs to 100% quickly once a result arrives, and never claims completion
// when nothing was found. A miss stays on the loading screen with its reason (MISSING / UNKNOWN as reported).
import {wallModel} from './q1-wall-model.mjs';
import {parsePresentation} from './q3-bar-model.mjs';

export const PHASES=Object.freeze(['wall','searching','result']);
export const PROGRESS_CEILING=0.92;
const CREEP_TAU_MS=2500,FINISH_MS=300;

export const initialPhase=()=>({phase:'wall',mode:null,progress:0,armed:false,resolved:false,miss:null});

export function phaseReduce(state,action) {
  switch(action.type) {
    case 'SEARCH_START':return ['find','track'].includes(action.mode)?{...initialPhase(),phase:'searching',mode:action.mode}:state;
    case 'SEARCH_ARMED':return state.phase==='searching'&&!state.armed?{...state,armed:true}:state;
    case 'SEARCH_FOUND':return state.phase==='searching'&&state.armed&&!state.resolved?{...state,resolved:true,miss:null,mode:action.mode??state.mode}:state;
    case 'SEARCH_MISS':return state.phase==='searching'&&state.armed&&!state.resolved&&!(state.miss&&state.miss.code===(action.code??'UNKNOWN')&&state.miss.message===(action.message??'資料不足，沒有找到。'))?{...state,miss:{code:action.code??'UNKNOWN',message:action.message??'資料不足，沒有找到。'}}:state;
    case 'TICK': {
      if(state.phase!=='searching'||!(action.dtMs>0))return state;
      if(state.resolved) {
        const progress=Math.min(1,state.progress+action.dtMs/FINISH_MS);
        return progress>=1?{...state,progress:1,phase:'result'}:{...state,progress};
      }
      if(state.miss)return state; // stays where it is: loading screen with the reason
      const progress=state.progress+(PROGRESS_CEILING-state.progress)*(1-Math.exp(-action.dtMs/CREEP_TAU_MS));
      return {...state,progress:Math.min(PROGRESS_CEILING,progress)};
    }
    // A recorded tracking response skips the search animation: it is already complete, so wall -> result directly.
    case 'SHOW_RESULT':return state.phase==='wall'&&action.mode==='track'?{...initialPhase(),phase:'result',mode:'track',progress:1,resolved:true}:state;
    case 'SEARCH_END':return initialPhase(); // explicit user action only
    default:return state;
  }
}

// Classify what the main store currently holds for the latest request.
// pending: still loading or Q3 parsed but not yet executed; found: has something to show; miss: finished without a usable result.
export function outcomeOf(s) {
  if(s.loading)return {kind:'pending'};
  if(s.error)return {kind:'miss',code:s.error.code??'UNKNOWN',message:s.error.message??'目前無法取得資料（UNKNOWN）。'};
  if(s.seeds)return {kind:'found',mode:'track'}; // start-observation choice is shown by the Q2 view
  if(s.q2) {
    const hit=Array.isArray(s.q2.timeline)&&s.q2.timeline.some(x=>x.kind==='ON_CAMERA');
    return hit?{kind:'found',mode:'track'}:{kind:'miss',code:s.q2.status??'UNKNOWN',message:'沒有找到相符的畫面；不代表目標不存在。'};
  }
  if(s.q1) {
    const m=wallModel(s.q1);
    return m.groups.matches.length?{kind:'found',mode:'find'}:{kind:'miss',code:s.q1.status??'UNKNOWN',message:m.message};
  }
  if(s.q3) {
    if(s.q3.status==='PARSED')return {kind:'pending'};
    return {kind:'miss',code:s.q3.status??'UNKNOWN',message:parsePresentation(s.q3).message};
  }
  return {kind:'idle'};
}

// The phase action for a just-loaded recording: only a RECORDED Q2 with tracking data leaves the wall (Q1 and empty recordings keep it).
export function recordedResultAction(s) {
  if(s.responseOrigin!=='RECORDED'||s.task!=='q2'||!s.q2)return null;
  const o=outcomeOf({loading:false,error:null,seeds:null,q2:s.q2});
  return o.kind==='found'?{type:'SHOW_RESULT',mode:o.mode}:null;
}

// Watches the main store while a search is active. `armed` flips once the request actually starts loading, so a stale
// previous response is never mistaken for the new result.
export function attachPhase(mainStore,phaseStore) {
  const sync=()=>{
    const p=phaseStore.getState();if(p.phase!=='searching')return;
    const s=mainStore.getState();
    if(!p.armed){if(s.loading)phaseStore.dispatch({type:'SEARCH_ARMED'});return;}
    const o=outcomeOf(s);
    if(o.kind==='found')phaseStore.dispatch({type:'SEARCH_FOUND',mode:o.mode});
    else if(o.kind==='miss')phaseStore.dispatch({type:'SEARCH_MISS',code:o.code,message:o.message});
  };
  const unsubMain=mainStore.subscribe(sync);const unsubPhase=phaseStore.subscribe(sync);
  return ()=>{unsubMain();unsubPhase();};
}

export function createPhaseStore(init=initialPhase()) {
  let state=init;const listeners=new Set();
  return {getState:()=>state,subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},
    dispatch(action){const next=phaseReduce(state,action);if(next===state)return state;state=next;for(const fn of [...listeners])fn(state,action);return state;}};
}
export const progressPercent=p=>Math.round(Math.min(1,Math.max(0,p))*100);

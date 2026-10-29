// Single state + pure reducer for the v2 workbench (design §6.1, V2-1 task card). No DOM.
// Switching `main` (2D/3D) must not change any other field.

import { SPEEDS, clampTMs, maxTMs } from './clock.mjs';
import {canPlay} from './q-playback.mjs';
import { GRID_SIZES } from './layout.mjs';
import { isValidated,freezeDeep,responseKind } from './q-validate.mjs';

const LEGACY_MODES = Object.freeze(['browse', 'find', 'demo']);
export const MODES = Object.freeze(['q1','q2']);
export const MAINS = Object.freeze(['2d', '3d']);
export const RAILS = Object.freeze(['pinned', 'overlay', 'rail']);
export const PANEL_SECTIONS = Object.freeze(['find', 'demo', 'evidence', 'layers', 'prov']);
export const DEMO_STEPS = Object.freeze([1, 2, 3, 4, 5, 6, 7]);

export function initialState(overrides = {}) {
  const rail = overrides.rail === 'rail' ? 'rail' : 'pinned';
  return {
    mode: 'browse', // retained for the unmounted legacy v2 views
    task: 'q1', tUs: 0, playbackMode: 'multi', switchMode: 'RULE_ONLY',
    reviewMode: false, responseOrigin:null, recordedAt:null, bootstrap: null, activeRun: null, q1: null, q2: null, q3: null,
    lastRequest: null, loading: false, error: null, artifacts: Object.freeze({}), seeds: null,
    main: '2d',
    rail,
    railPref: rail, // last non-floating choice; the only rail value persisted
    panelSection: 'evidence',
    tMs: 0,
    playing: false,
    speed: 1,
    selection: null,
    pin: null,
    tempPin: null, // { id, prevPin } while a click-trace pin is active
    query: null,
    preQuery: null, // snapshot taken when entering find from browse
    demoStep: null,
    size: 4,
    grid: null, // owned by V2-3 (player-grid state)
    run: null, // { run_id, fps, duration_s } once a source is loaded
    ...overrides,
    ...{ rail, railPref: rail },
  };
}

function withRail(state, rail) {
  return { ...state, rail, railPref: rail === 'overlay' ? state.railPref : rail };
}

function openPanel(state, section) {
  const next = PANEL_SECTIONS.includes(section) ? { ...state, panelSection: section } : state;
  return next.rail === 'rail' ? withRail(next, 'overlay') : next;
}

function setMode(state, mode) {
  if (!LEGACY_MODES.includes(mode) || mode === state.mode) return state;
  let next = { ...state, mode };
  if (mode === 'find' && state.mode === 'browse' && state.preQuery === null) {
    next.preQuery = { tMs: state.tMs, size: state.size, pin: state.pin, tempPin: state.tempPin, grid: state.grid };
  }
  if (mode !== 'demo' && state.mode === 'demo') next.demoStep = null;
  return next;
}

function legacyReduce(state, action) {
  switch (action.type) {
    case 'SET_MODE':
      return setMode(state, action.mode);

    case 'RETURN_FROM_QUERY': {
      const snap = state.preQuery;
      if (!snap) return state;
      return { ...state, ...snap, mode: 'browse', preQuery: null };
    }

    case 'REENTER_QUERY':
      return state.query ? setMode(state, 'find') : state;

    case 'SET_MAIN':
      return MAINS.includes(action.main) && action.main !== state.main ? { ...state, main: action.main } : state;

    case 'TOGGLE_MAIN':
      return { ...state, main: state.main === '2d' ? '3d' : '2d' };

    // Rail (sidebar): pinned | overlay | rail(collapsed)
    case 'SET_RAIL':
      return RAILS.includes(action.rail) ? withRail(state, action.rail) : state;

    case 'TOGGLE_BURGER': // ≡: pinned -> collapsed, collapsed -> floating, floating -> collapsed
      return withRail(state, state.rail === 'rail' ? 'overlay' : 'rail');

    case 'TOGGLE_PIN_RAIL': // `[`: pinned <-> collapsed (floating closes to collapsed)
      return withRail(state, state.rail === 'pinned' ? 'rail' : state.rail === 'rail' ? 'pinned' : 'rail');

    case 'ESCAPE':
    case 'MAIN_POINTER': // a click on the main area closes the floating panel; the click itself still goes through
      return state.rail === 'overlay' ? withRail(state, 'rail') : state;

    case 'OPEN_PANEL':
      return openPanel(state, action.section);

    case 'ICON_CLICK': {
      const id = action.id;
      if (id === 'find' || id === 'demo') return openPanel(setMode(state, id), id);
      return openPanel(state, id);
    }

    // Time
    case 'SET_RUN': {
      const run = action.run;
      return { ...state, run, tMs: run ? clampTMs(state.tMs, run.duration_s) : state.tMs, playing: false };
    }

    case 'SET_T':
      return { ...state, tMs: state.run ? clampTMs(action.tMs, state.run.duration_s) : Math.max(0, Math.trunc(action.tMs)) };

    case 'PLAY': {
      if (!state.run) return state;
      const atEnd = state.tMs >= maxTMs(state.run.duration_s);
      return { ...state, playing: true, tMs: atEnd ? 0 : state.tMs };
    }
    case 'PAUSE':
      return state.playing ? { ...state, playing: false } : state;
    case 'TOGGLE_PLAY':
      return legacyReduce(state, { type: state.playing ? 'PAUSE' : 'PLAY' });

    case 'SET_SPEED':
      return SPEEDS.includes(action.speed) ? { ...state, speed: action.speed } : state;

    // Selection and pinning
    case 'SELECT':
      return { ...state, selection: action.selection ?? null };

    case 'PIN': // user pin supersedes any temporary pin
      return { ...state, pin: action.id ?? null, tempPin: null };

    case 'TEMP_PIN':
      return { ...state, tempPin: { id: action.id, prevPin: state.tempPin ? state.tempPin.prevPin : state.pin }, pin: action.id };

    case 'CLEAR_TEMP_PIN':
      return state.tempPin ? { ...state, pin: state.tempPin.prevPin, tempPin: null } : state;

    case 'SET_SIZE':
      return GRID_SIZES.includes(action.size) ? { ...state, size: action.size } : state;

    case 'SET_GRID':
      return { ...state, grid: action.grid };

    case 'SET_QUERY':
      return { ...state, query: action.query };

    case 'SET_DEMO_STEP':
      return { ...state, demoStep: DEMO_STEPS.includes(action.step) ? action.step : null };

    default:
      return state;
  }
}

export function reduce(state,action) {
  if(['PLAY','PAUSE','TOGGLE_PLAY'].includes(action.type)&&(state.activeRun||state.q2)) {
    const bounds=state.task==='q2'&&state.q2?[state.q2.timeline[0]?.range_us[0]??0,state.q2.timeline.at(-1)?.range_us[1]??0]:state.selection?.kind==='Q1_SEGMENT'?state.selection.range_us:[0,state.activeRun?.clock_mapping?.source_duration_us??0];
    const [start,end]=bounds;
    const playing=action.type==='PLAY'||action.type==='TOGGLE_PLAY'&&!state.playing;
    if(!end||(playing&&!canPlay(state)))return state;
    const tUs=playing&&state.tUs>=end?start:state.tUs;return {...state,playing,tUs,tMs:tUs/1000};
  }
  switch(action.type) {
    case 'SET_TASK':return MODES.includes(action.task)?{...state,task:action.task}:state;
    case 'SET_PLAYBACK_MODE':return ['multi','single'].includes(action.value)?{...state,playbackMode:action.value}:state;
    case 'SET_SWITCH_MODE':return ['RULE_ONLY','AGENT_SEQUENTIAL'].includes(action.value)?{...state,switchMode:action.value}:state;
    case 'SET_Q_BOOTSTRAP':return {...state,bootstrap:action.data,error:null};
    case 'SET_Q_RUN':return {...state,responseOrigin:null,recordedKind:null,recordedAt:null,switchMode:'RULE_ONLY',activeRun:action.run,tUs:0,tMs:0,playing:false,q1:null,q2:null,q3:null,artifacts:Object.freeze({}),seeds:null,error:null};
    case 'Q_LOADING':return {...state,responseOrigin:null,recordedKind:null,recordedAt:null,task:['q1','q2'].includes(action.kind)?action.kind:state.task,q3:action.keepParse?state.q3:null,loading:true,error:null,lastRequest:freezeDeep(structuredClone(action.request)),seeds:null,q1:null,q2:null,artifacts:Object.freeze({}),playing:false};
    case 'Q_ERROR':return {...state,loading:false,error:action.error,playing:false};
    case 'Q_SEEDS':return {...state,loading:false,seeds:action.data};
    case 'Q_RESPONSE': {
      if(!isValidated(action.data)||!MODES.concat('q3').includes(action.kind))return state;
      try{if(responseKind(action.data)!==action.kind)return state;}catch{return state;}
      const next={...state,responseOrigin:action.source_origin??state.responseOrigin,recordedAt:action.recorded_at??state.recordedAt,recordedKind:action.source_kind??state.recordedKind,[action.kind]:action.data,loading:false,error:null,seeds:null};
      if(action.kind==='q2'){next.task='q2';next.artifacts=Object.freeze({});next.tUs=action.data.timeline[0]?.range_us[0]??0;next.tMs=next.tUs/1000;next.playing=false;}
      if(action.kind==='q1')next.task='q1';return next;
    }
    case 'Q_ARTIFACTS':return action.for_hash===state.q2?.output_sha256?{...state,artifacts:freezeDeep(action.data)}:state;
    case 'SET_T_US': {
      if(!Number.isSafeInteger(action.tUs)||action.tUs<0)return state;
      const max=state.activeRun?.clock_mapping?.source_duration_us??state.q2?.timeline.at(-1)?.range_us[1]??action.tUs;
      const value=Math.min(max,action.tUs);return {...state,tUs:value,tMs:value/1000};
    }
    default: {
      const next=legacyReduce(state,action);
      return next!==state&&next.tMs!==state.tMs?{...next,tUs:Math.round(next.tMs*1000)}:next;
    }
  }
}

export function createStore(init = initialState()) {
  let state = init;
  const listeners = new Set();
  return {
    getState: () => state,
    dispatch(action) {
      const next = reduce(state, action);
      if (next === state) return state;
      const prev = state;
      state = next;
      for (const fn of [...listeners]) fn(state, prev, action);
      return state;
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}

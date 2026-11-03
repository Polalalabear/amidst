// Monitor room: pure model. No DOM, no network, no ground truth. The wall plays pre-recorded RGB only;
// a camera without RGB stays MISSING, it is never replaced by a still or a repeated picture.
export const MAX_WALL_CAMERAS=8;
export const SPEEDS=Object.freeze([0.5,1,2,4]);
export const SETTINGS_KEY='amidst.monitor-room.v1';
export const DEFAULT_SETTINGS=Object.freeze({selection:null,playing:true,speed:1,startUs:0,loop:true,cameras:null,restart:0});

// 2..8 cameras auto-layout; 1 and >8 are handled too (the cap is applied by wallCameras).
export function gridFor(count){
  const n=Math.max(0,Math.floor(count));if(!n)return {cols:0,rows:0};
  const cols=n<=2?n:n<=4?2:n<=6?3:4;
  return {cols,rows:Math.ceil(n/cols)};
}

const finite=x=>typeof x==='number'&&Number.isFinite(x);
export function normalizeSettings(raw){
  const r=raw&&typeof raw==='object'?raw:{},d=DEFAULT_SETTINGS;
  const sel=r.selection,selection=sel&&typeof sel==='object'&&(
    (sel.kind==='run'&&typeof sel.scene_id==='string'&&typeof sel.run_id==='string')||(sel.kind==='recording'&&typeof sel.recording_id==='string'))
    ?(sel.kind==='run'?{kind:'run',scene_id:sel.scene_id,run_id:sel.run_id}:{kind:'recording',recording_id:sel.recording_id}):null;
  return {selection,playing:typeof r.playing==='boolean'?r.playing:d.playing,
    speed:SPEEDS.includes(r.speed)?r.speed:d.speed,
    startUs:Number.isInteger(r.startUs)&&r.startUs>=0?r.startUs:d.startUs,
    loop:typeof r.loop==='boolean'?r.loop:d.loop,
    cameras:Array.isArray(r.cameras)&&r.cameras.every(x=>typeof x==='string')?[...new Set(r.cameras)]:null,
    restart:Number.isInteger(r.restart)&&r.restart>=0?r.restart:d.restart};
}

export function createSettingsStore(storage,{key=SETTINGS_KEY,listen=null}={}){
  const read=()=>{try{const t=storage?.getItem(key);return normalizeSettings(t?JSON.parse(t):null);}catch{return normalizeSettings(null);}};
  let value=read();const subs=new Set();
  const emit=()=>{for(const fn of subs)fn(value);};
  // Another tab (the admin page) wrote the key: re-read and tell the wall.
  const stop=listen?.(()=>{value=read();emit();});
  return {get:()=>value,
    set(patch){value=normalizeSettings({...value,...patch});try{storage?.setItem(key,JSON.stringify(value));}catch{}emit();return value;},
    restart(){return this.set({restart:value.restart+1});},
    subscribe(fn){subs.add(fn);return()=>subs.delete(fn);},
    destroy(){stop?.();subs.clear();}};
}

// Which run the selection means. A recording only names its scope after it has been replayed (scopeOf).
export function resolveRun(bootstrap,selection,scopeOf=()=>null){
  const runs=bootstrap?.runs??[];if(!runs.length)return null;
  if(selection?.kind==='run')return runs.find(r=>r.scene_id===selection.scene_id&&r.run_id===selection.run_id)??null;
  if(selection?.kind==='recording'){const scope=scopeOf(selection.recording_id);return scope?runs.find(r=>r.scene_id===scope.scene_id&&r.run_id===scope.run_id)??null:null;}
  return runs.reduce((best,r)=>(r.camera_ids?.length??0)>(best.camera_ids?.length??0)?r:best,runs[0]);
}

// camera_ids of the run, optionally narrowed by the admin subset, capped at 8, in run order.
export function wallCameras(run,subset=null){
  const all=run?.camera_ids??[];
  const chosen=subset?all.filter(c=>subset.includes(c)):all;
  return chosen.slice(0,MAX_WALL_CAMERAS);
}

export function frameIntervalUs(run,cameras=null){
  const per=(run?.sampling?.per_camera??[]).filter(x=>!cameras||cameras.includes(x.camera_id)).map(x=>x.source_frame_interval_us).filter(x=>Number.isInteger(x)&&x>0);
  return per.length?Math.min(...per):null;
}
export const durationUs=run=>run?.clock_mapping?.source_duration_us??0;
export const stampFor=(tUs,interval)=>Math.floor(tUs/interval)*interval;

// Advance the wall clock by wall-time elapsed. `loop` wraps to startUs; otherwise it holds on the last frame.
export function advanceClock(tUs,elapsedMs,{speed,startUs,durationUs:end,loop}){
  if(!(end>0))return {tUs:0,ended:true};
  const next=tUs+Math.round(elapsedMs*1000*speed);
  if(next<end)return {tUs:Math.max(0,next),ended:false};
  if(loop){const span=Math.max(1,end-startUs);return {tUs:startUs+((next-startUs)%span),ended:false};}
  return {tUs:Math.max(0,end-1),ended:true};
}

// One entry per tile. `frames` maps camera -> last presented status ('READY' | anything else). Unknown until probed.
export function tileEntries(cameras,frames=new Map()){
  return cameras.map(camera_id=>{const status=frames.get(camera_id);
    return {camera_id,status:status===undefined?'PENDING':status==='READY'?'READY':'MISSING'};});
}

// Frames skipped between two presented stamps (a late frame is dropped, never shown stretched).
export function skippedFrames(prevStamp,stamp,interval,{wrapped=false}={}){
  if(prevStamp===null||wrapped||!interval||stamp<=prevStamp)return 0;
  return Math.max(0,Math.round((stamp-prevStamp)/interval)-1);
}

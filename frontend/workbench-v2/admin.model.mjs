// Admin page: catalog of recorded footage and recorded responses from the existing bootstrap. Pure; no GT, no media.
import {frameIntervalUs,durationUs} from './monitor-room-model.mjs';

export function runCatalog(bootstrap){
  return (bootstrap?.runs??[]).map(run=>{const interval=frameIntervalUs(run);
    return {kind:'run',key:`${run.scene_id}/${run.run_id}`,scene_id:run.scene_id,run_id:run.run_id,
      // Human-readable title is not in the API yet (waiting for Codex interface -T): show the IDs.
      title:run.title??`${run.scene_id} · ${run.run_id}`,titleMissing:!run.title,
      camera_ids:[...(run.camera_ids??[])],duration_us:durationUs(run),fps:interval?Math.round(1e6/interval*100)/100:null,
      source_kind:run.source_kind??'UNKNOWN'};});
}
export function recordingCatalog(bootstrap){
  return (bootstrap?.recordings??[]).map(r=>({kind:'recording',key:r.recording_id,recording_id:r.recording_id,
    title:r.title??r.recording_id,titleMissing:!r.title,recorded_at:r.recorded_at??null,source_kind:r.source_kind??'UNKNOWN',
    response_kind:r.response_kind??'UNKNOWN',switch_mode:r.switch_mode??null}));
}

const has=(hay,needle)=>!needle||String(hay).toLowerCase().includes(String(needle).trim().toLowerCase());
// from_us / to_us: source-time window in microseconds; a run matches when its [0,duration) overlaps it.
export function filterRuns(items,{scene='',camera='',source_kind='',from_us=null,to_us=null}={}){
  return items.filter(x=>has(`${x.scene_id} ${x.run_id} ${x.title}`,scene)
    &&(!camera||x.camera_ids.some(c=>has(c,camera)))
    &&(!source_kind||x.source_kind===source_kind)
    &&(from_us===null||x.duration_us>from_us)&&(to_us===null||to_us>=0));
}
// from / to: ISO date or datetime strings compared against recorded_at; recordings without a time never match a time filter.
export function filterRecordings(items,{text='',source_kind='',from=null,to=null}={}){
  const t=s=>{const v=Date.parse(s);return Number.isNaN(v)?null:v;};
  const lo=from?t(from):null,hi=to?t(to):null;
  return items.filter(x=>has(`${x.recording_id} ${x.title}`,text)&&(!source_kind||x.source_kind===source_kind)&&(()=>{
    if(lo===null&&hi===null)return true;const at=x.recorded_at?t(x.recorded_at):null;if(at===null)return false;
    return (lo===null||at>=lo)&&(hi===null||at<=hi);})());
}

// "h:mm:ss" / "m:ss" / plain seconds -> microseconds (integer), or null when the text is not a time.
export function parseTimecode(text){
  const s=String(text??'').trim();if(!s)return null;
  const parts=s.split(':');if(parts.length>3||parts.some(p=>!/^\d+(\.\d+)?$/.test(p)))return null;
  const sec=parts.reduce((acc,p)=>acc*60+Number(p),0);return Math.round(sec*1e6);
}
export function formatDuration(us){const s=Math.round(us/1e6);return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;}

// What the admin page writes when the user picks something. One entry point, so the wall and the tests agree.
export function selectionFor(item){
  return item.kind==='run'?{kind:'run',scene_id:item.scene_id,run_id:item.run_id}:{kind:'recording',recording_id:item.recording_id};
}
export function isSelected(item,selection){
  if(!selection)return false;
  return item.kind==='run'?selection.kind==='run'&&selection.scene_id===item.scene_id&&selection.run_id===item.run_id
    :selection.kind==='recording'&&selection.recording_id===item.recording_id;
}

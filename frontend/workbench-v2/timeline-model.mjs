// L2-3 long timeline: pure view-window math. All times are SOURCE integer microseconds.
const need=(ok,code)=>{if(!ok)throw new Error(code);};
const int=Number.isSafeInteger;
export const MIN_SPAN_US=1000000;
export function createView(duration,range=null){
  need(int(duration)&&duration>0,'DURATION_INVALID');const r=range??[0,duration];
  need(int(r[0])&&int(r[1])&&r[0]>=0&&r[1]<=duration&&r[1]>r[0],'VIEW_RANGE_INVALID');return {duration,range:[r[0],r[1]]};
}
function clamp(view,start,span){const min=Math.min(MIN_SPAN_US,view.duration);const s=Math.round(Math.max(min,Math.min(view.duration,span)));const a=Math.round(Math.max(0,Math.min(view.duration-s,start)));return {duration:view.duration,range:[a,a+s]};}
export const span=v=>v.range[1]-v.range[0];
// factor>1 zooms in. The source time under anchorUs keeps its fraction of the window.
export function zoom(view,factor,anchorUs){
  need(factor>0&&Number.isFinite(factor),'ZOOM_FACTOR_INVALID');const old=span(view),next=old/factor;
  const a=Math.max(view.range[0],Math.min(view.range[1],anchorUs)),frac=(a-view.range[0])/old;return clamp(view,a-frac*next,next);
}
export function pan(view,deltaUs){return clamp(view,view.range[0]+deltaUs,span(view));}
export function fit(view,range,padFraction=0.1){const w=range[1]-range[0];need(w>0,'FIT_RANGE_INVALID');const pad=w*padFraction;return clamp(view,range[0]-pad,w+2*pad);}
export function centerOn(view,t){return clamp(view,t-span(view)/2,span(view));}
export const timeToX=(view,t,width)=>(t-view.range[0])/span(view)*width;
export const xToTime=(view,x,width)=>Math.round(view.range[0]+x/width*span(view));
export const isVisible=(view,t)=>t>=view.range[0]&&t<view.range[1];
// Follow mode: when the playhead leaves the window, re-center the window on it (center, not page-flip, so it works for forward play and backward seeks alike).
export function followPlayhead(view,t){return isVisible(view,t)?view:centerOn(view,t);}
export function zoomLevel(view){return view.duration/span(view);}
const STEPS=[1e6,2e6,5e6,10e6,15e6,30e6,60e6,120e6,300e6,600e6,900e6,1800e6,3600e6,7200e6];
// Ticks at a "nice" step so labels are at least minPx apart.
export function ticks(view,widthPx,minPx=80){
  const want=span(view)/(widthPx/minPx),step=STEPS.find(x=>x>=want)??STEPS.at(-1);const out=[];
  for(let t=Math.ceil(view.range[0]/step)*step;t<view.range[1];t+=step)out.push({t,left:(t-view.range[0])/span(view)*100,major:t%(step*5)===0});return {step_us:step,ticks:out};
}
export function formatTick(t,step){const s=Math.floor(t/1e6),h=Math.floor(s/3600),m=Math.floor(s%3600/60),sec=s%60,p=n=>String(n).padStart(2,'0');return step>=60e6?`${h}h${p(m)}m`:`${p(h)}:${p(m)}:${p(sec)}`;}
// Marker layout: events within minPx of a cluster's first event merge into one cluster (count + member ids), so zooming out never overlaps labels.
export function layoutMarkers(events,view,widthPx,minPx=14){
  const vis=events.filter(e=>isVisible(view,e.t_us)).sort((a,b)=>a.t_us-b.t_us||String(a.id).localeCompare(String(b.id)));
  const clusters=[];for(const e of vis){const x=timeToX(view,e.t_us,widthPx),last=clusters.at(-1);
    if(last&&x-last.x_start<minPx){last.members.push(e);last.x_end=x;}else clusters.push({x_start:x,x_end:x,members:[e]});}
  return clusters.map(c=>{const first=c.members[0];return {t_us:first.t_us,left:(c.x_start)/widthPx*100,count:c.members.length,ids:c.members.map(m=>m.id),kinds:[...new Set(c.members.map(m=>m.kind))],kind:c.members.length===1?first.kind:'CLUSTER',label:c.members.length===1?first.label:`${c.members.length} 件`};});
}
// Next / previous event strictly after / before t (for keyboard jumps).
export function neighborEvent(events,t,dir){const s=[...events].sort((a,b)=>a.t_us-b.t_us);return dir>0?s.find(e=>e.t_us>t)??null:[...s].reverse().find(e=>e.t_us<t)??null;}
// Segments clipped to the window as percentages; segments that cannot be seen at this zoom are dropped.
export function clipSegments(segments,view){const w=span(view);return segments.filter(s=>s.range_us[1]>view.range[0]&&s.range_us[0]<view.range[1]).map(s=>{const a=Math.max(s.range_us[0],view.range[0]),b=Math.min(s.range_us[1],view.range[1]);return {...s,left:(a-view.range[0])/w*100,width:(b-a)/w*100};});}

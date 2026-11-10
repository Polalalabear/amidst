// Camera-frame corner label. Line 1: `<camera> · <virtual time>（UTC+8）` = the run's declared demo-clock start + source time (never this machine's wall clock).
// Line 2 (secondary, system view only): `+<elapsed> s · DECLARED_DEMO_CLOCK`. No declared clock => the virtual time is UNKNOWN (no date is assumed).
import {virtualTime,DECLARED_TAG} from './q-time.mjs';
let clock=null;
export function setStampClock(mapping){clock=mapping??null;}
const isSourceUs=t=>Number.isSafeInteger(t)&&t>=0;
const elapsed=us=>`${Math.floor(us/1000000)}.${String(Math.floor(us%1000000/10000)).padStart(2,'0')} s`;
export function stampParts(camera,sourceUs){
  const name=typeof camera==='string'&&camera?camera:'UNKNOWN';
  if(!isSourceUs(sourceUs))return {main:`${name} · UNKNOWN`,sub:''};
  const v=virtualTime(sourceUs,clock);
  return {main:`${name} · ${v?`${v.text}（${v.tz}）`:'UNKNOWN'}`,sub:`+${elapsed(sourceUs)} · ${v?(v.declared?DECLARED_TAG:'CLOCK_UNDECLARED'):'CLOCK_MAPPING_MISSING'}`};
}
export function stampText(camera,sourceUs){const p=stampParts(camera,sourceUs);return p.sub?`${p.main}\n${p.sub}`:p.main;}
// One label per frame cell, set only when that cell's own frame changes. Drawn by CSS (::before of [data-stamp]).
export function setStamp(target,camera,sourceUs){if(!target)return;const p=stampParts(camera,sourceUs);target.dataset.stamp=p.sub?`${p.main}\n${p.sub}`:p.main;target.dataset.stampSimple=p.main;}
// A frame whose RGB failed to load shows the failure text and an UNKNOWN stamp, never the requested time (same rule as q-playback).
export function failStamp(target,camera,text){if(!target)return;target.textContent=text;setStamp(target,camera,null);}

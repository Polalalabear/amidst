// Camera-frame corner label: `<camera> · <seconds> s`. Source time only (µs from run start); no wall clock (CLOCK_MAPPING_MISSING stays UNKNOWN).
const isSourceUs=t=>Number.isSafeInteger(t)&&t>=0;
export function stampText(camera,sourceUs){
  const name=typeof camera==='string'&&camera?camera:'UNKNOWN';
  if(!isSourceUs(sourceUs))return `${name} · UNKNOWN`;
  return `${name} · ${Math.floor(sourceUs/1000000)}.${String(Math.floor(sourceUs%1000000/10000)).padStart(2,'0')} s`;
}
// One label per frame cell, set only when that cell's own frame changes. Drawn by CSS (::before of [data-stamp]).
export function setStamp(target,camera,sourceUs){if(target)target.dataset.stamp=stampText(camera,sourceUs);}

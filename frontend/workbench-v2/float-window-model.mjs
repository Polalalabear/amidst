// Pure state of the floating 俯視圖 window: open/closed + position, persisted per viewer in localStorage.
// Default is closed so the window never covers a camera tile; every storage access is wrapped and falls back to the default.
export const STORAGE_KEY='amidst.workbench-v2.track-map-float.v1';
export const DEFAULT_STATE=Object.freeze({open:false,pos:null});  // pos null = CSS default (bottom-right)
export const defaultStorage=()=>{try{return globalThis.localStorage??null;}catch{return null;}};
const isNum=x=>typeof x==='number'&&Number.isFinite(x);
export function clampPos(pos,size,bounds) {
  const maxX=Math.max(0,bounds.width-size.width),maxY=Math.max(0,bounds.height-size.height);
  return {x:Math.min(Math.max(0,pos.x),maxX),y:Math.min(Math.max(0,pos.y),maxY)};
}
export function loadState(storage=defaultStorage()) {
  try {
    const raw=storage?.getItem(STORAGE_KEY);if(!raw)return {...DEFAULT_STATE};
    const v=JSON.parse(raw);
    return {open:v?.open===true,pos:isNum(v?.pos?.x)&&isNum(v?.pos?.y)?{x:v.pos.x,y:v.pos.y}:null};
  } catch {return {...DEFAULT_STATE};}
}
export function saveState(state,storage=defaultStorage()) {
  try {storage.setItem(STORAGE_KEY,JSON.stringify({open:state.open===true,pos:state.pos}));return true;} catch {return false;}
}
export const toggled=state=>({...state,open:!state.open});
export const moved=(state,pos,size,bounds)=>({...state,pos:clampPos(pos,size,bounds)});
// Ignore the shortcut while typing in a field.
export function isToggleKey(e) {
  if(!e||e.ctrlKey||e.metaKey||e.altKey||String(e.key).toLowerCase()!=='m')return false;
  const t=e.target,tag=String(t?.tagName??'').toUpperCase();
  return !(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT'||t?.isContentEditable);
}

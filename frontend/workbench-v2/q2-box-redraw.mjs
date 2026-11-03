// OBS boxes sit in % of the camera container and depend on its object-fit:contain letterbox, so they are re-laid out whenever the container is resized (e.g. the track-map dock opening) as well as on every new frame.
import {placeBox} from './q2-session-model.mjs';
export function paintBoxes(target,img,observations,create){
  for(const old of [...target.querySelectorAll('.q2-box')])old.remove();
  for(const o of observations){
    const box=placeBox(o.bbox_xyxy_px,img.naturalWidth,img.naturalHeight,target.clientWidth,target.clientHeight);if(!box)continue;
    const n=create('span','OBS','q2-box');for(const [k,v] of Object.entries({left:box.left,top:box.top,width:box.right-box.left,height:box.bottom-box.top}))n.style[k]=v+'%';target.append(n);
  }
}
// `entries` maps target -> {img,observations} for the frame currently shown; a target that is BUFFERING (boxes cleared by playback.pending) or shows text is skipped.
export function watchBoxes(target,entries,create,ResizeObserverImpl=globalThis.ResizeObserver){
  if(typeof ResizeObserverImpl!=='function')return ()=>{};
  const ro=new ResizeObserverImpl(()=>{const e=entries.get(target);if(e&&target.dataset?.status==='READY'&&e.img.parentNode===target)paintBoxes(target,e.img,e.observations,create);});
  ro.observe(target);return ()=>ro.disconnect();
}

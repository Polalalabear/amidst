// Observer-only browser instrumentation. This does not alter the player clock.
export function probe({kind='viewer',targetSourceUs=null,targetCamera=null}={}){
 const result=window.__mediaBench={kind,active:false,start:null,end:null,raf:[],promotions:[],paints:[],decode:[],targetSourceUs,targetCamera,targetFrame:null,availabilityAt:null,completeAt:null,nativeCompleteAt:null,visibility:[],errors:[]};
 const previous=new Map(),decodeVersions=new WeakMap();
 function meta(img,url=img.currentSrc||img.src){
  const m=url?.match(/\/media\/([^/]+)\/([^/]+)\/(\d+)\.png/);
  if(m)return {camera:m[2],index:Number(m[3]),sourceUs:null,url};
  if(img.dataset.camera&&img.dataset.frameIndex)return {camera:img.dataset.camera,index:Number(img.dataset.frameIndex),sourceUs:Number(img.dataset.sourceUs),url};
  return {camera:null,index:null,sourceUs:null,url};
 }
 const known=new Map();
 const visible=img=>{const r=img.getBoundingClientRect();return getComputedStyle(img).visibility!=='hidden'&&r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth;};
 function availability(){if(result.active&&result.targetSourceUs!==null&&result.availabilityAt===null&&Number(document.querySelector('#q-scrub')?.value)>=result.targetSourceUs)result.availabilityAt=performance.now();}
 function observe(img){
  if(!(img instanceof HTMLImageElement))return;
  img.setAttribute('elementtiming','media-bench');
  const url=img.currentSrc||img.src;if(!url)return;
  known.set(url,meta(img,url));
  if(decodeVersions.get(img)===url)return;decodeVersions.set(img,url);
  const began=performance.now();img.decode().then(()=>{if(result.active)result.decode.push({...meta(img,url),start:began,end:performance.now()});}).catch(()=>{});
 }
 new MutationObserver(mutations=>{
  for(const m of mutations){
   if(m.target instanceof HTMLImageElement)observe(m.target);
   for(const n of m.addedNodes)if(n instanceof Element){if(n instanceof HTMLImageElement)observe(n);for(const img of n.querySelectorAll('img'))observe(img);}
  }
  availability();
 }).observe(document,{childList:true,subtree:true,attributes:true,attributeFilter:['src']});
 if(PerformanceObserver.supportedEntryTypes.includes('element'))new PerformanceObserver(list=>{
  for(const e of list.getEntries())if(e.name==='image-paint'&&e.renderTime&&result.start!==null&&e.renderTime>=result.start){
   const m=known.get(e.url)??(e.element?meta(e.element,e.url):{});result.paints.push({...m,renderTime:e.renderTime,loadTime:e.loadTime,width:e.intersectionRect.width,height:e.intersectionRect.height});
   if(kind==='legacy'&&result.nativeCompleteAt===null&&result.availabilityAt!==null&&m.camera===result.targetCamera&&m.index>=result.targetFrame&&e.renderTime>=result.availabilityAt-8)result.nativeCompleteAt=e.renderTime;
  }
 }).observe({type:'element',buffered:true});
 document.addEventListener('visibilitychange',()=>result.visibility.push({t:performance.now(),state:document.visibilityState}));
 function tick(now){
  if(result.active){
   result.raf.push(now);
   const selector=kind==='viewer'?'#grid img':kind==='legacy'?'.q2-screen .q2-media img':'#core-tracking-slot img';
   for(const img of document.querySelectorAll(selector)){
    if(!img.complete||!img.naturalWidth||!visible(img))continue;
    const m=meta(img);if(m.camera===null)continue;known.set(m.url,m);
    const key=m.camera+':'+m.index;if(previous.get(m.camera)!==key){previous.set(m.camera,key);result.promotions.push({...m,t:now});}
   }
   if(result.targetSourceUs!==null){
    availability();
    const images=[...document.querySelectorAll(selector)].filter(i=>i.complete&&i.naturalWidth&&visible(i));
    const active=kind==='core'?document.querySelector('.q-core-active-cam-id')?.textContent:document.querySelector('.q2-camera[data-active="true"] h3')?.textContent?.split(' · ')[0];
    if(result.availabilityAt!==null&&active===result.targetCamera&&images.some(i=>kind==='core'||i.dataset.camera===result.targetCamera&&Number(i.dataset.frameIndex)>=result.targetFrame)){
     if(result.completeAt===null)result.completeAt=performance.now();
    }
   }
   if(kind==='viewer'){
    const last=Number(document.querySelector('#scrub')?.max),frame=Number(document.querySelector('#scrub')?.value);
    const imgs=[...document.querySelectorAll('#grid img')];
    if(frame===last&&imgs.length&&imgs.every(i=>i.complete&&i.naturalWidth&&meta(i).index===last)){result.end=now;result.active=false;}
   }
  }
  requestAnimationFrame(tick);
 }
 requestAnimationFrame(tick);
 result.begin=()=>{result.start=performance.now();result.active=true;previous.clear();};
}

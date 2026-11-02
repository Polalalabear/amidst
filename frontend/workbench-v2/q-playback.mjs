// Pixel buffering only. No detections, identities, time interpolation or crossfades.
export function lastSourceTime(tUs,start,end){return Math.max(start,Math.min(tUs,end-1));}
export function mediaSettled(tiles){return !!tiles.length&&tiles.every(x=>x.status&&x.status!=='BUFFERING'&&(x.status!=='READY'||x.imageReady));}
export function playbackDelta(s,elapsedMs,settled){if(!settled)return 0;const intervals=s.activeRun?.sampling?.per_camera?.map(x=>x.source_frame_interval_us)??[];return intervals.length?Math.min(elapsedMs,Math.min(...intervals)/(1000*s.speed)):0;}
export function canPlay(s){return !s.loading&&(s.task==='q2'?!!s.q2?.timeline.length:s.selection?.kind==='Q1_SEGMENT'&&!!s.q1);}
export function playbackScope(run){return JSON.stringify([run?.scene_id,run?.run_id,run?.detection_index_sha256,run?.clock_mapping?.content_sha256]);}
export function createFrameBuffer(api,{decode=decodeTile,now=()=>performance.now(),limit=96,maxBytes=67108864}={}){
  let scope=null,epoch=0,decodedBytes=0;const frames=new Map(),pixels=new Map();
  const stats={requests:0,media_loads:0,errors:0,missing_tiles:0,cache_hits:0,evictions:0,decoded_bytes:0,peak_decoded_bytes:0,frame_entries:0,pixel_entries:0,request_ms:[],decode_ms:[]};
  const measure=()=>{stats.decoded_bytes=decodedBytes;stats.peak_decoded_bytes=Math.max(stats.peak_decoded_bytes,decodedBytes);stats.frame_entries=frames.size;stats.pixel_entries=pixels.size;};
  function collect(p){if(p.refs===0&&p.value){p.value.release?.();decodedBytes-=p.bytes;if(pixels.get(p.key)===p)pixels.delete(p.key);p.value=null;measure();}}
  function evict(k){const f=frames.get(k);if(!f)return;frames.delete(k);f.evicted=true;for(const p of f.pins){p.refs--;collect(p);}stats.evictions++;measure();}
  function trim(bytes=0,except=null){for(const [k,f] of frames){if(decodedBytes+bytes<=maxBytes&&frames.size<=limit)break;if(f===except||!f.done||f.users)continue;evict(k);}measure();return decodedBytes+bytes<=maxBytes;}
  function reset(run){const next=playbackScope(run);if(next===scope)return;scope=next;epoch++;for(const k of [...frames.keys()])evict(k);for(const p of pixels.values())collect(p);measure();}
  function key(run,t,cameras){return JSON.stringify([playbackScope(run),t,[...cameras].sort()]);}
  async function prepare(run,t,cameras){reset(run);const k=key(run,t,cameras);let f=frames.get(k);if(f){stats.cache_hits++;frames.delete(k);frames.set(k,f);}else{
    const version=epoch;f={pins:new Set(),done:false,evicted:false,users:0};frames.set(k,f);
    f.promise=(async()=>{const started=now();stats.requests++;const result=await api.frames(run,t,cameras);stats.request_ms.push(now()-started);if(version!==epoch)throw Error('STALE_RGB_SCOPE');
      const answer=new Map();for(const camera of cameras){const tile=result.data?.tiles?.find(x=>x.camera_id===camera);if(!result.ok||tile?.status!=='READY'||!tile.media_url){stats.missing_tiles++;answer.set(camera,{status:tile?.status??'MISSING'});continue;}
        const pk=tile.served_sha256??tile.file_sha256??tile.media_url;let p=pixels.get(pk);
        if(!p){p={key:pk,refs:0,value:null,bytes:0};pixels.set(pk,p);stats.media_loads++;const began=now();
          p.promise=Promise.resolve().then(()=>decode(tile)).then(value=>{const size=(value.image?.naturalWidth??0)*(value.image?.naturalHeight??0)*4;
            if(version!==epoch||!trim(size,f)){value.release?.();throw Error(version!==epoch?'STALE_RGB_SCOPE':'RGB_ACTIVE_LEASE_LIMIT');}
            p.value=value;p.bytes=size;decodedBytes+=size;stats.decode_ms.push(now()-began);measure();return value;
          }).catch(error=>{if(pixels.get(pk)===p)pixels.delete(pk);throw error;});
        }
        if(!f.pins.has(p)){f.pins.add(p);p.refs++;}
        try{const value=await p.promise;if(version!==epoch)throw Error('STALE_RGB_SCOPE');answer.set(camera,{status:'READY',image:value,tile,pixel:p});}
        catch(error){stats.errors++;answer.set(camera,{status:'MISSING',error:error.message});}
      }f.done=true;return answer;
    })().catch(error=>{evict(k);throw error;});
  }
  f.users++;let answer;try{answer=await f.promise;}finally{f.users--;}const result=new Map(answer),held=[];for(const frame of result.values())if(frame.status==='READY'&&frame.pixel.value){frame.pixel.refs++;held.push(frame.pixel);}
  let released=false;result.release=()=>{if(released)return;released=true;for(const p of held){p.refs--;collect(p);}trim();};trim(0,f);return result;
  }
  return {prepare,prefetch:async(...args)=>{const result=await prepare(...args);result.release();},stats,reset,destroy(){reset(null);for(const p of pixels.values())collect(p);}};
}
async function decodeTile(tile){
  if(!/^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/.test(tile.media_url))throw Error('MEDIA_URL');
  const response=await fetch(tile.media_url,{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(5000)});if(!response.ok)throw Error('RGB_HTTP_'+response.status);
  const bytes=await response.arrayBuffer();if(bytes.byteLength>16777216)throw Error('RGB_TOO_LARGE');
  const pin=tile.served_sha256??tile.file_sha256;if(pin){const actual=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');if(actual!==pin)throw Error('RGB_PIN_MISMATCH');}
  const url=URL.createObjectURL(new Blob([bytes],{type:'image/png'}));const image=new Image();image.src=url;
  try{await image.decode();if(!image.naturalWidth||image.naturalWidth*image.naturalHeight>4194304)throw Error('RGB_DECODE_SIZE');return {image,url,release:()=>URL.revokeObjectURL(url)};}catch(error){URL.revokeObjectURL(url);throw error;}
}
export function createPlayback({api,store,root,onReady=()=>{}}){
  const buffer=createFrameBuffer(api),cells=new WeakMap(),panel=document.createElement('details');panel.id='q-playback-data';panel.style.cssText='font-size:11px;max-width:100%;overflow:auto';
  const title=document.createElement('summary');title.textContent='播放量測與素材說明';const note=document.createElement('p');note.textContent='顯示來源 RGB 採樣，不補造中間影像。動態工程來源為 8 秒、20 fps 的逐格人物位移與步態。舊靜態素材錄製仍屬靜態延展；RAF 為瀏覽器取樣，物理螢幕 fps 未量測。';
  const pre=document.createElement('pre');pre.id='q-playback-metrics';pre.style.cssText='white-space:pre-wrap;max-height:300px;overflow:auto';panel.append(title,note,pre);root.querySelector('#q-notice').after(panel);
  let report=null,last=null,started=null,previous=null,dead=false,lastMainKey=null;
  const history=[];
  const paint=()=>{pre.textContent=JSON.stringify({schema_version:'q-demo.browser-playback.v1',physical_display_fps:null,current:report,completed:history,buffer:buffer.stats},null,2);};
  function finish(s){if(!report)return;report.wall_duration_ms=performance.now()-started;report.end_source_us=s.tUs;report.completed=s.tUs>=report.range_us[1];report.raf_hz=report.raf_samples/(report.wall_duration_ms/1000);history.push(structuredClone(report));if(history.length>16)history.shift();report=null;paint();}
  const un=store.subscribe((s,prior)=>{if(s.playing&&!prior.playing){started=performance.now();previous=null;lastMainKey=null;const range=s.task==='q2'?[s.q2.timeline[0].range_us[0],s.q2.timeline.at(-1).range_us[1]]:s.selection.range_us;report={range_us:range,start_source_us:s.tUs,speed:s.speed,mode:s.task==='q2'?s.playbackMode:'q1',main_frame_samples:[],raf_samples:0,no_decoded_main_samples:0,buffering_samples:0,swaps:[],max_raf_gap_ms:0,active_camera_transitions:[],source_kind:s.activeRun?.source_kind??null};}if(prior.playing&&!s.playing)finish(s);});
  function sample(now){if(dead)return;if(report){report.raf_samples++;if(previous!==null)report.max_raf_gap_ms=Math.max(report.max_raf_gap_ms,now-previous);previous=now;const active=root.querySelector('.q2-camera[data-active="true"] h3')?.textContent?.split(' · ')[0];if(active&&report.active_camera_transitions.at(-1)?.camera!==active)report.active_camera_transitions.push({camera:active,source_us:store.getState().tUs,wall_elapsed_ms:performance.now()-started});const selector=store.getState().task==='q2'?'.q2-screen .q2-media':'.q1-playback .q1-media';const targets=[...root.querySelectorAll(selector)].filter(x=>getComputedStyle(x).visibility!=='hidden'&&x.getClientRects().length>0);if(!targets.length||targets.some(x=>!x.querySelector('img')?.naturalWidth))report.no_decoded_main_samples++;if(targets.some(x=>x.dataset.status==='BUFFERING'))report.buffering_samples++;const visible=targets.map(x=>{const img=x.querySelector('img');return {camera:img?.dataset.camera??null,source_us:img?.dataset.sourceUs?Number(img.dataset.sourceUs):null,frame_index:img?.dataset.frameIndex?Number(img.dataset.frameIndex):null,status:x.dataset.status};});const mainKey=JSON.stringify(visible);if(mainKey!==lastMainKey){lastMainKey=mainKey;report.main_frame_samples.push({wall_elapsed_ms:performance.now()-started,clock_source_us:store.getState().tUs,tiles:visible});}}if(last===null||now-last>=250){last=now;paint();}raf=requestAnimationFrame(sample);}
  let raf=requestAnimationFrame(sample);paint();
  async function present(target,frame,{camera,timestamp,alive=()=>true,onDraw=()=>{}}={}){
    const version=(cells.get(target)??0)+1;cells.set(target,version);target.dataset.status='BUFFERING';
    // Never let an old observation impersonate the newly requested source timestamp.
    for(const old of target.querySelectorAll('.q2-box,.q1-box'))old.remove();
    const began=performance.now();if(frame?.status!=='READY'){target.replaceChildren(document.createTextNode(`${frame?.status??'MISSING'} · 沒有可用的 RGB`));target.dataset.status=frame?.status??'MISSING';delete target.dataset.sourceUs;onReady();return;}
    const img=frame.image.image.cloneNode();img.alt=`${camera} · ${(timestamp/1e6).toFixed(6)} s`;
    try{await img.decode();if(dead||!alive()||cells.get(target)!==version)return;img.dataset.camera=camera;img.dataset.sourceUs=String(timestamp);img.dataset.frameIndex=String(frame.tile.frame_index);target.replaceChildren(img);target.dataset.status='READY';target.dataset.sourceUs=String(timestamp);onDraw(img);onReady();if(report)report.swaps.push({camera,source_us:timestamp,frame_index:frame.tile.frame_index,wall_elapsed_ms:performance.now()-started,clock_source_us:store.getState().tUs,decode_to_swap_ms:performance.now()-began});}
    catch{if(alive()&&cells.get(target)===version){target.textContent='MISSING · RGB 解碼失敗';target.dataset.status='MISSING';}}
  }
  const pending=target=>{target.dataset.status='BUFFERING';for(const box of target.querySelectorAll('.q2-box,.q1-box'))box.remove();};
  const clockReady=()=>{const selector=store.getState().task==='q2'?'.q2-screen .q2-media':'.q1-playback .q1-media';const targets=[...root.querySelectorAll(selector)].filter(x=>getComputedStyle(x).visibility!=='hidden'&&x.getClientRects().length>0);return mediaSettled(targets.map(x=>({status:x.dataset.status,imageReady:!!x.querySelector('img')?.naturalWidth})));};
  return {buffer,present,pending,paint,clockReady,viewReady:onReady,destroy(){dead=true;cancelAnimationFrame(raf);un();buffer.destroy();panel.remove();}};
}

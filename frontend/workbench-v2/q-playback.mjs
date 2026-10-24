// Pixel buffering only. No detections, identities, time interpolation or crossfades.
export function lastSourceTime(tUs,start,end){return Math.max(start,Math.min(tUs,end-1));}
export function canPlay(s){return !s.loading&&(s.task==='q2'?!!s.q2?.timeline.length:s.selection?.kind==='Q1_SEGMENT'&&!!s.q1);}
export function playbackScope(run){return JSON.stringify([run?.scene_id,run?.run_id,run?.detection_index_sha256,run?.clock_mapping?.content_sha256]);}
export function createFrameBuffer(api,{decode=decodeTile,now=()=>performance.now(),limit=96}={}){
  let scope=null,epoch=0,decodedBytes=0;const frames=new Map(),pixels=new Map(),stats={requests:0,media_loads:0,errors:0,cache_hits:0,request_ms:[],decode_ms:[]};
  function reset(run){const next=playbackScope(run);if(next===scope)return;scope=next;epoch++;decodedBytes=0;frames.clear();for(const p of pixels.values())p.then(x=>x.release?.()).catch(()=>{});pixels.clear();}
  function key(run,t,cameras){return JSON.stringify([playbackScope(run),t,[...cameras].sort()]);}
  async function prepare(run,t,cameras){reset(run);const k=key(run,t,cameras);if(frames.has(k)){stats.cache_hits++;return frames.get(k);}if(frames.size>=limit){const oldest=frames.keys().next().value;frames.delete(oldest);}
    const version=epoch,promise=(async()=>{const started=now();stats.requests++;const result=await api.frames(run,t,cameras);stats.request_ms.push(now()-started);if(version!==epoch)throw Error('STALE_RGB_SCOPE');
      const answer=new Map();for(const camera of cameras){const tile=result.data?.tiles?.find(x=>x.camera_id===camera);if(!result.ok||tile?.status!=='READY'||!tile.media_url){answer.set(camera,{status:tile?.status??'MISSING'});continue;}
        const pin=tile.served_sha256??tile.file_sha256,pk=pin??tile.media_url;
        if(!pixels.has(pk)){stats.media_loads++;const began=now();pixels.set(pk,Promise.resolve().then(()=>decode(tile)).then(value=>{if(version!==epoch){value.release?.();throw Error('STALE_RGB_SCOPE');}const size=(value.image?.naturalWidth??0)*(value.image?.naturalHeight??0)*4;if(decodedBytes+size>67108864){value.release?.();throw Error('RGB_BUFFER_64_MIB_LIMIT');}decodedBytes+=size;stats.decode_ms.push(now()-began);return value;}).catch(e=>{pixels.delete(pk);throw e;}));}
        try{const image=await pixels.get(pk);if(version!==epoch)throw Error('STALE_RGB_SCOPE');answer.set(camera,{status:'READY',image,tile});}catch(error){stats.errors++;answer.set(camera,{status:'MISSING',error:error.message});}
      }return answer;
    })();frames.set(k,promise);return promise;
  }
  return {prepare,stats,reset,destroy(){epoch++;for(const p of pixels.values())p.then(x=>x.release?.()).catch(()=>{});frames.clear();pixels.clear();}};
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
  const title=document.createElement('summary');title.textContent='播放量測與素材說明';const note=document.createElement('p');note.textContent='SYNTHETIC 工程素材為兩張靜態 RGB 的時間延展；不代表連續人物動作。RAF 為瀏覽器取樣，物理螢幕 fps 未量測。';
  const pre=document.createElement('pre');pre.id='q-playback-metrics';pre.style.cssText='white-space:pre-wrap;max-height:300px;overflow:auto';panel.append(title,note,pre);root.querySelector('#q-notice').after(panel);
  let report=null,last=null,started=null,previous=null,dead=false;
  const history=[];
  const paint=()=>{pre.textContent=JSON.stringify({schema_version:'q-demo.browser-playback.v1',physical_display_fps:null,current:report,completed:history,buffer:buffer.stats},null,2);};
  function finish(s){if(!report)return;report.wall_duration_ms=performance.now()-started;report.end_source_us=s.tUs;report.completed=s.tUs>=report.range_us[1];report.raf_hz=report.raf_samples/(report.wall_duration_ms/1000);history.push(structuredClone(report));if(history.length>16)history.shift();report=null;paint();}
  const un=store.subscribe((s,prior)=>{if(s.playing&&!prior.playing){started=performance.now();previous=null;const range=s.task==='q2'?[s.q2.timeline[0].range_us[0],s.q2.timeline.at(-1).range_us[1]]:s.selection.range_us;report={range_us:range,start_source_us:s.tUs,speed:s.speed,mode:s.task==='q2'?s.playbackMode:'q1',raf_samples:0,no_decoded_main_samples:0,buffering_samples:0,swaps:[],max_raf_gap_ms:0,active_camera_transitions:[],source_kind:s.activeRun?.source_kind??null};}if(prior.playing&&!s.playing)finish(s);});
  function sample(now){if(dead)return;if(report){report.raf_samples++;if(previous!==null)report.max_raf_gap_ms=Math.max(report.max_raf_gap_ms,now-previous);previous=now;const active=root.querySelector('.q2-camera[data-active="true"] h3')?.textContent?.split(' · ')[0];if(active&&report.active_camera_transitions.at(-1)?.camera!==active)report.active_camera_transitions.push({camera:active,source_us:store.getState().tUs,wall_elapsed_ms:performance.now()-started});const selector=store.getState().task==='q2'?'.q2-screen .q2-media':'.q1-playback .q1-media';const targets=[...root.querySelectorAll(selector)];if(!targets.length||targets.some(x=>!x.querySelector('img')?.naturalWidth))report.no_decoded_main_samples++;if(targets.some(x=>x.dataset.status==='BUFFERING'))report.buffering_samples++;}if(last===null||now-last>=250){last=now;paint();}raf=requestAnimationFrame(sample);}
  let raf=requestAnimationFrame(sample);paint();
  async function present(target,frame,{camera,timestamp,alive=()=>true,onDraw=()=>{}}={}){
    const version=(cells.get(target)??0)+1;cells.set(target,version);target.dataset.status='BUFFERING';
    // Never let an old observation impersonate the newly requested source timestamp.
    for(const old of target.querySelectorAll('.q2-box,.q1-box'))old.remove();
    const began=performance.now();if(frame?.status!=='READY'){target.replaceChildren(document.createTextNode(`${frame?.status??'MISSING'} · 沒有可用的 RGB`));target.dataset.status=frame?.status??'MISSING';return;}
    const img=frame.image.image.cloneNode();img.alt=`${camera} · ${(timestamp/1e6).toFixed(6)} s`;
    try{await img.decode();if(dead||!alive()||cells.get(target)!==version)return;img.dataset.sourceUs=String(timestamp);img.dataset.frameIndex=String(frame.tile.frame_index);target.replaceChildren(img);target.dataset.status='READY';target.dataset.sourceUs=String(timestamp);onDraw(img);onReady();if(report)report.swaps.push({camera,source_us:timestamp,frame_index:frame.tile.frame_index,wall_elapsed_ms:performance.now()-started,clock_source_us:store.getState().tUs,decode_to_swap_ms:performance.now()-began});}
    catch{if(alive()&&cells.get(target)===version){target.textContent='MISSING · RGB 解碼失敗';target.dataset.status='MISSING';}}
  }
  return {buffer,present,paint,destroy(){dead=true;cancelAnimationFrame(raf);un();buffer.destroy();panel.remove();}};
}

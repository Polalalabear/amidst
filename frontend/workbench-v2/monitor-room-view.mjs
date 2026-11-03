// Monitor room view: all cameras of one run playing pre-recorded RGB on one shared clock.
// Own clock and own frame buffer, so it does not depend on Q1 segments, the Q2 timeline or the store's playback.
// Hosts (app.mjs, UI-A phase machine, admin preview) drive it with setVisible()/destroy(); nothing here reads GT.
import {createFrameBuffer} from './q-playback.mjs';
import {formatSource} from './q-time.mjs';
import {setStamp} from './cam-stamp.mjs';
import {gridFor,wallCameras,resolveRun,frameIntervalUs,durationUs,stampFor,advanceClock,tileEntries,skippedFrames,normalizeSettings} from './monitor-room-model.mjs';

const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const PREFETCH=2,MAX_BYTES=201326592;

export function mountMonitorRoom(host,{api,settings,controls=true}){
  const head=el('div',undefined,'mr-head'),title=el('strong','監控牆'),meta=el('span','載入中','mr-meta'),clock=el('span','','mr-clock mono');
  const toggle=el('button','Ⅱ 暫停','ibtn mr-toggle');toggle.hidden=!controls;
  head.append(title,meta,el('span',undefined,'spacer'),clock,toggle);
  const grid=el('div',undefined,'mr-grid'),note=el('p','','note mr-note'),stats=el('details',undefined,'mr-stats'),statsPre=el('pre');
  stats.append(el('summary','播放量測'),statsPre);host.classList.add('monitor-room');host.replaceChildren(head,grid,note,stats);

  const buffer=createFrameBuffer(api,{maxBytes:MAX_BYTES});
  let bootstrap=null,run=null,cameras=[],tiles=new Map(),frames=new Map(),visible=true,dead=false,raf=null;
  let tUs=0,last=null,restart=-1,inflight=false,lastStamp=null,wrapped=false,activeSel='',presentedAt=null;
  const scopes=new Map(),metrics={cameras:0,presented:0,skipped:0,max_raf_gap_ms:0,raf_samples:0,started_ms:null,present_ms:[]};

  const current=()=>normalizeSettings(settings.get());
  function report(){
    const wall=metrics.started_ms===null?0:(performance.now()-metrics.started_ms)/1000;
    statsPre.textContent=JSON.stringify({cameras:metrics.cameras,presented_ticks:metrics.presented,skipped_frames:metrics.skipped,
      effective_tick_hz:wall>0?Math.round(metrics.presented/wall*10)/10:null,raf_hz:wall>0?Math.round(metrics.raf_samples/wall*10)/10:null,
      max_raf_gap_ms:Math.round(metrics.max_raf_gap_ms),median_present_ms:median(metrics.present_ms),buffer:buffer.stats},null,2);
  }
  const median=a=>a.length?[...a].sort((x,y)=>x-y)[a.length>>1]:null;

  function buildTiles(){
    grid.replaceChildren();tiles=new Map();frames=new Map();
    const {cols}=gridFor(cameras.length);grid.style.gridTemplateColumns=cols?`repeat(${cols},minmax(0,1fr))`:'none';
    grid.dataset.count=String(cameras.length);grid.dataset.cols=String(cols);
    for(const camera of cameras){
      const tile=el('article',undefined,'mr-tile'),label=el('div',undefined,'mr-label'),name=el('b',camera),state=el('span','…','mr-state'),media=el('div','等待畫面…','mr-media');
      tile.dataset.camera=camera;tile.dataset.status='PENDING';setStamp(media,camera,null);label.append(name,state);tile.append(label,media);grid.append(tile);tiles.set(camera,{tile,state,media});
    }
    metrics.cameras=cameras.length;
  }
  function paintStatus(){
    for(const e of tileEntries(cameras,frames)){const t=tiles.get(e.camera_id);if(!t)continue;t.tile.dataset.status=e.status;t.state.textContent=e.status==='READY'?formatSource(lastStamp??0):e.status==='MISSING'?'MISSING':'…';}
  }

  async function ensureScope(sel){
    if(sel?.kind!=='recording'||scopes.has(sel.recording_id))return;
    scopes.set(sel.recording_id,null);const result=await api.replay(sel.recording_id);
    const scope=result.ok?result.data?.resolved_scope:null;
    scopes.set(sel.recording_id,scope?{scene_id:scope.scene_id,run_id:scope.run_ids?.[0]}:{scene_id:null,run_id:null});
  }
  async function select(){
    const s=current(),key=JSON.stringify([s.selection,s.cameras]);
    if(key===activeSel)return;activeSel=key;
    await ensureScope(s.selection);if(dead||key!==activeSel)return;
    run=resolveRun(bootstrap,s.selection,id=>scopes.get(id)??null);cameras=wallCameras(run,s.cameras);
    buildTiles();lastStamp=null;presentedAt=null;seek(s);
    if(!run){meta.textContent=bootstrap?'UNKNOWN · 沒有可播放的來源':'載入中';note.textContent=s.selection?.kind==='recording'&&scopes.get(s.selection.recording_id)?.scene_id===null?'UNKNOWN · 這筆錄製回應沒有可對應的來源影片。':'';return;}
    meta.textContent=`${cameras.length} 台鏡頭 · ${run.source_kind??'UNKNOWN'} · ${run.scene_id}`;
    note.textContent=cameras.length<(run.camera_ids?.length??0)?`顯示 ${cameras.length} / ${run.camera_ids.length} 台（後台已篩選或超過上限 8 台）。`:'';
  }
  function seek(s){tUs=Math.min(s.startUs,Math.max(0,durationUs(run)-1));lastStamp=null;presentedAt=null;wrapped=false;}

  async function show(stamp){
    inflight=true;const began=performance.now();
    try{
      const result=await buffer.prepare(run,stamp,cameras);
      if(dead||!visible){result.release();return;}
      for(const camera of cameras){const t=tiles.get(camera),frame=result.get(camera);
        frames.set(camera,frame?.status==='READY'?'READY':frame?.status??'MISSING');
        if(frame?.status==='READY'){const img=frame.image.image.cloneNode();img.alt=`${camera} · ${formatSource(stamp)}`;img.dataset.sourceUs=String(stamp);try{await img.decode();}catch{}t.media.replaceChildren(img);setStamp(t.media,camera,stamp);}
        else{t.media.textContent=`MISSING · 沒有可用的 RGB`;setStamp(t.media,camera,null);}}
      result.release();
      metrics.skipped+=skippedFrames(presentedAt,stamp,frameIntervalUs(run,cameras),{wrapped});wrapped=false;presentedAt=stamp;lastStamp=stamp;metrics.presented++;metrics.present_ms.push(performance.now()-began);
      if(metrics.present_ms.length>200)metrics.present_ms.shift();paintStatus();
      const interval=frameIntervalUs(run,cameras);
      for(let k=1;k<=PREFETCH;k++){const t=stamp+interval*k;if(t<durationUs(run))buffer.prefetch(run,t,cameras).catch(()=>{});}
    }catch{ for(const camera of cameras)frames.set(camera,'MISSING');paintStatus(); }
    finally{inflight=false;}
  }

  function frame(now){
    if(dead)return;raf=requestAnimationFrame(frame);
    if(!visible)return;
    metrics.raf_samples++;if(last!==null)metrics.max_raf_gap_ms=Math.max(metrics.max_raf_gap_ms,now-last);
    const s=current();
    if(s.restart!==restart){restart=s.restart;if(run)seek(s);}
    if(!bootstrap)return;select();
    toggle.textContent=s.playing?'Ⅱ 暫停':'▶ 播放';
    if(!run||!cameras.length){last=now;return;}
    const interval=frameIntervalUs(run,cameras);if(!interval){note.textContent='UNKNOWN · 缺少取樣間隔，無法播放。';last=now;return;}
    if(metrics.started_ms===null)metrics.started_ms=performance.now();
    if(s.playing&&last!==null&&lastStamp!==null){const before=tUs,next=advanceClock(tUs,now-last,{speed:s.speed,startUs:s.startUs,durationUs:durationUs(run),loop:s.loop});tUs=next.tUs;if(tUs<before)wrapped=true;}
    last=now;
    const stamp=stampFor(tUs,interval);clock.textContent=formatSource(tUs);
    // Late frames are dropped, not queued: one request in flight at a time.
    if(!inflight&&stamp!==lastStamp)show(stamp);
    if(raf!==null&&metrics.raf_samples%30===0)report();
  }
  toggle.onclick=()=>settings.set({playing:!current().playing});
  const unsub=settings.subscribe(()=>{select();});
  raf=requestAnimationFrame(frame);

  return {
    setBootstrap(b){bootstrap=b;activeSel='';select();},
    // UI-A hides the wall while searching: hidden = no clock, no requests, memory kept until destroy().
    setVisible(v){visible=!!v;host.hidden=!visible;if(visible)last=null;},
    isVisible:()=>visible,
    metrics:()=>({...metrics,cameras:cameras.length,tiles:[...tiles.keys()]}),
    report,
    destroy(){dead=true;cancelAnimationFrame(raf);unsub();buffer.destroy();host.replaceChildren();host.classList.remove('monitor-room');},
  };
}

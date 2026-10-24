import {lastSourceTime} from './q-playback.mjs';
import {sessionModel,camerasFor,observedAt,placeBox} from './q2-session-model.mjs';
import {mount as mountTimeline} from './q2-timeline-view.mjs';import {renderEvidence} from './q4-evidence-view.mjs';
import {formatSource} from './q-time.mjs';import {contentHash} from './q-validate.mjs';import {layoutFor} from './player-grid.mjs';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export function mount(context){
  const {store,slots,api,execute,playback}=context,root=slots.session,timeline=mountTimeline(context);let pendingCommit=null;let currentGrid=null,currentCells=null,lastFrameKey='',frameGeneration=0,statusTime=null;let key='',generation=0,dead=false,page=0,observationHash=null,observations=[],abortObservations=0,artifactSet=null,evidenceToolHashes={},hashEpoch=0;
  async function primeObservations(response){
    const batch=++abortObservations;observations=[];const ids=[...new Set(response.timeline.flatMap(x=>x.observation_ids??[]))];if(ids.length>4096)return;
    let i=0;await Promise.all(Array.from({length:Math.min(4,ids.length)},async()=>{while(i<ids.length&&!dead&&batch===abortObservations){const id=ids[i++],item=await api.artifact(response,'observation',id);if(item.ok&&batch===abortObservations)observations.push(item.data);}}));
    if(!dead&&batch===abortObservations){key='';render(store.getState());}
  }
  async function frames(grid,model,s,ids,version,secondary=new Map()){
    let cells=currentCells;if(grid!==currentGrid){currentGrid=grid;cells=new Map();currentCells=cells;lastFrameKey='';
      for(const camera of ids){const tile=el('article',undefined,'q2-camera');tile.dataset.active=String(camera===model.camera);tile.append(el('h3',`${camera}${camera===model.camera?' · 目前畫面':''}`));const media=el('div','取得來源畫面…','q2-media');tile.append(media);grid.append(tile);cells.set(camera,[{target:media,boxes:true}]);}
      if(!ids.length){grid.append(el('p','UNKNOWN · 沒有資料'));pendingCommit?.();return;}
      for(const [camera,target] of secondary){if(!cells.has(camera))cells.set(camera,[]);cells.get(camera).push({target,boxes:false});}
    }
    const interval=Math.min(...s.activeRun.sampling.per_camera.map(x=>x.source_frame_interval_us));
    const stamp=Math.floor(model.timestamp_us/interval)*interval,frameKey=JSON.stringify([version,stamp]);if(frameKey===lastFrameKey)return;lastFrameKey=frameKey;const frameVersion=++frameGeneration;
    const alive=()=>!dead&&version===generation&&frameVersion===frameGeneration;
    for(const entries of cells.values())for(const {target} of entries)playback.pending(target);
    const requested=[...cells.keys()];for(let offset=0;offset<requested.length;offset+=8){
      const chunk=requested.slice(offset,offset+8),result=await playback.buffer.prepare(s.activeRun,stamp,chunk);if(!alive()){result.release();return;}
      const presentations=[];for(const camera of chunk)for(const {target,boxes} of cells.get(camera))presentations.push(playback.present(target,result.get(camera),{camera,timestamp:stamp,alive,onDraw:img=>{
        for(const o of boxes?observedAt(model,observations,camera,stamp):[]){
          const box=placeBox(o.bbox_xyxy_px,img.naturalWidth,img.naturalHeight,target.clientWidth,target.clientHeight);if(!box)continue;const n=el('span','OBS','q2-box');for(const [k,v] of Object.entries({left:box.left,top:box.top,width:box.right-box.left,height:box.bottom-box.top}))n.style[k]=v+'%';target.append(n);
        }
      }}));
      try{await Promise.all(presentations);}finally{result.release();}if(!alive())return;pendingCommit?.();
      // Six source frames at 20 fps / two cameras fit under the 64 MiB pixel cap.
      for(let t=stamp+interval;t<=stamp+Math.min(300000,interval*6)&&t<s.activeRun.clock_mapping.source_duration_us;t+=interval)playback.buffer.prefetch(s.activeRun,t,chunk).catch(()=>{});
    }
  }
  function render(s){
    if(s.seeds&&s.task!=='q2'){store.dispatch({type:'SET_TASK',task:'q2'});return;}if(s.task!=='q2')return;
    const interval=Math.min(...(s.activeRun?.sampling.per_camera.map(x=>x.source_frame_interval_us)??[1]));
    const shown=s.q2?lastSourceTime(s.tUs,s.q2.timeline[0]?.range_us[0]??0,s.q2.timeline.at(-1)?.range_us[1]??1):s.tUs;
    let model=null;try{if(s.q2)model=sessionModel(s.q2,shown,{...s.artifacts,review:s.reviewMode,evidenceToolHashes,inspectionId:s.selection?.kind==='INSPECT_DECISION'?s.selection.decision_id:null});}catch{}
    if(s.reviewMode&&artifactSet!==s.artifacts){artifactSet=s.artifacts;const current=s.artifacts;evidenceToolHashes={};Promise.all(Object.values(current.evidence??{}).map(async e=>[await contentHash(e),e.evidence_sha256])).then(entries=>{if(!dead&&artifactSet===current){evidenceToolHashes=Object.fromEntries(entries);hashEpoch++;key='';render(store.getState());}}).catch(()=>{});}
    const next=JSON.stringify([hashEpoch,s.q2?.output_sha256,s.seeds,s.playbackMode,s.size,model?.state,model?.camera,model?.decision?.decision_id,s.selection,s.artifacts.decisions?.length,page,s.loading,s.activeRun?.run_id]);if(next===key){if(model&&currentGrid){statusTime.textContent=`${model.camera??'UNKNOWN'} · ${formatSource(s.tUs)} · ${s.tUs>=s.q2.timeline.at(-1).range_us[1]?'播放結束 · 最後合法影格 · ':''}身分未確認`;frames(currentGrid,model,s,camerasFor(model,s.activeRun,{mode:s.playbackMode,size:s.size,page}),generation);}return;}key=next;const version=++generation;
    // Keep the visible view until its replacement has decoded RGB (including state/camera switches).
    for(const old of root.querySelectorAll('.q2-session[data-pending]'))old.remove();
    for(const target of root.querySelectorAll('.q2-screen .q2-media'))playback.pending(target);
    const wrap=el('div',undefined,'q2-session');wrap.dataset.pending='true';wrap.style.cssText='position:absolute;inset:0;visibility:hidden';root.style.position='relative';root.append(wrap);
    pendingCommit=()=>{if(dead||version!==generation)return;delete wrap.dataset.pending;wrap.style.cssText='';root.replaceChildren(wrap);pendingCommit=null;};
    if(s.seeds){wrap.append(el('h3','選擇起點觀測'));for(const c of s.seeds.candidates){const b=el('button',`${formatSource(c.timestamp_us)} · ${c.camera_id} · ${c.observation_id}`);b.onclick=()=>execute(s.lastRequest,{selected_observation_id:c.observation_id});wrap.append(b);}pendingCommit?.();return;}
    if(!s.q2){wrap.append(el('p','尚未載入事件；請先選擇起點觀測。'));pendingCommit?.();return;}
    if(s.q2.output_sha256!==observationHash){observationHash=s.q2.output_sha256;page=0;primeObservations(s.q2);}
    const m=model;if(!m){wrap.append(el('p','UNKNOWN · 決策／GAP 資料不完整'));pendingCommit?.();return;}
    const status=el('div',undefined,'q2-state');statusTime=el('span',`${m.camera??'UNKNOWN'} · ${formatSource(s.tUs)} · 身分未確認`);status.append(el('strong',m.message),statusTime);if(s.reviewMode)status.append(el('span',`${m.state} · ${s.q2.status} · ${s.q2.decision_source}${s.q2.fallback_reason?' · '+s.q2.fallback_reason:''}`));wrap.append(status);
    const body=el('div',undefined,'q2-body'),main=el('div',undefined,'q2-screen');body.append(main);wrap.append(body);const ids=camerasFor(m,s.activeRun,{mode:s.playbackMode,size:s.size,page});main.style.gridTemplateColumns=`repeat(${s.playbackMode==='single'?1:layoutFor(s.size).cols},minmax(0,1fr))`;main.style.gridTemplateRows=`repeat(${s.playbackMode==='single'?1:layoutFor(s.size).rows},minmax(0,1fr))`;const candidateCells=new Map();
    if(s.playbackMode==='multi'){const count=Math.ceil((s.activeRun?.camera_ids.length??0)/s.size),nav=el('div',undefined,'q2-pages'),prev=el('button','上一組鏡頭'),next=el('button','下一組鏡頭');prev.disabled=page<=0;next.disabled=page>=count-1;prev.onclick=()=>{page--;key='';render(store.getState());};next.onclick=()=>{page++;key='';render(store.getState());};nav.append(prev,el('span',`${page+1}／${Math.max(1,count)}`),next);wrap.append(nav);}
    if(s.reviewMode){const aside=el('aside',undefined,'q2-candidates');aside.append(el('h3','候選與證據（錄製）'));body.append(aside);if(!m.candidates.length)aside.append(el('p',m.state==='PLAYING'?'PLAYING：沒有搜尋候選':m.state==='TEMP_LOST'?'暫失：尚未搜尋':'沒有可用候選紀錄'));
      if(m.snapshot)aside.append(el('p',`出口 ${m.snapshot.exit_resolution} · 截斷 ${m.snapshot.truncated_count} · 排除轉移 ${m.snapshot.excluded_transitions.length}`));
      for(const c of m.candidates){const card=el('details',undefined,'q2-candidate'),summary=el('summary',`#${c.rank} ${c.camera_id} · ${c.result?.action??c.evaluation}`),meta=el('p',`${c.relation} · [${formatSource(c.window_us[0])}, ${formatSource(c.window_us[1])}) · ${c.result?.decided_by??'尚未決定'} · ${c.result?.exclusion_reason??''}`),proof=el('div');renderEvidence(proof,c.evidence,{api,run:s.activeRun,alive:()=>!dead&&version===generation});const peek=el('div','同時刻畫面 · 僅供檢視，非證據','q2-candidate-frame');candidateCells.set(c.camera_id,peek);card.append(summary,meta,peek,proof);aside.append(card);}
    }
    frames(main,m,s,ids,version,candidateCells);
  }
  const unsub=store.subscribe(render);render(store.getState());return {destroy(){dead=true;generation++;abortObservations++;unsub();timeline.destroy();root.replaceChildren();}};
}

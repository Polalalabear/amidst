import {lastSourceTime} from './q-playback.mjs';
import {wallModel,seedRequest,segmentSelection,coverageText,overlayBoxes} from './q1-wall-model.mjs';
import {renderProvenance} from './provenance-bar.mjs';
import {formatSource} from './q-time.mjs';
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};
export function mount({store,slots,api,execute,playback}) {
  const root=slots.wall;let liveTarget=null,liveTitle=null,liveTick=null;let response=null,page=0,generation=0,lastKey='',destroyed=false;
  async function image(container,s,result,segment,version){
    const rep=segment.representative;container.textContent='MISSING · 代表畫面尚未取得';
    const grant=await api.mediaGrant(rep.media_token);if(destroyed||version!==generation)return;
    const tile=grant.data?.tiles?.[0];if(!grant.ok||!tile){container.textContent='MISSING · 沒有可用的 RGB';return;}
    const img=el('img');img.alt=`${result.camera_id} 代表觀測`;img.src=tile.media_url;container.replaceChildren(img);
    const observations=[];for(const id of rep.observation_ids){const v=await api.artifact(s.q1,'observation',id);if(v.ok)observations.push(v.data);}
    if(destroyed||version!==generation)return;
    const draw=()=>{if(version!==generation)return;for(const prior of container.querySelectorAll('.q1-box'))prior.remove();for(const b of overlayBoxes(observations,{width:img.naturalWidth,height:img.naturalHeight,containerWidth:container.clientWidth,containerHeight:container.clientHeight,frameRef:rep.frame_ref,cameraId:result.camera_id})){
      const box=el('span','OBS','q1-box');box.style.left=b.left+'%';box.style.top=b.top+'%';box.style.width=b.right-b.left+'%';box.style.height=b.bottom-b.top+'%';box.title=b.observation_id;container.append(box);
    }};img.onload=draw;if(img.complete&&img.naturalWidth)draw();img.onerror=()=>{if(version===generation)container.textContent='MISSING · RGB 載入失敗';};
  }
  async function liveSegment(container,s,version){const selected=s.selection;if(selected?.kind!=='Q1_SEGMENT')return;
    const interval=s.activeRun.sampling.per_camera.find(x=>x.camera_id===selected.camera_id).source_frame_interval_us;
    const stamp=Math.floor(lastSourceTime(s.tUs,...selected.range_us)/interval)*interval;
    if(liveTitle)liveTitle.textContent=`${selected.camera_id} · ${formatSource(s.tUs)}${s.tUs>=selected.range_us[1]?' · 播放結束 · 最後合法影格':''}`;
    if(liveTick===stamp)return;liveTick=stamp;
    playback.pending(container);const result=await playback.buffer.prepare(s.activeRun,stamp,[selected.camera_id]);if(destroyed||version!==generation||stamp!==liveTick)return;
    playback.present(container,result.get(selected.camera_id),{camera:selected.camera_id,timestamp:stamp,alive:()=>!destroyed&&version===generation&&stamp===liveTick});
    for(let t=stamp+interval;t<=stamp+1000000&&t<selected.range_us[1];t+=interval)playback.buffer.prepare(s.activeRun,t,[selected.camera_id]).catch(()=>{});
  }
  function render(s){
    if(s.task!=='q1')return;if(s.q1!==response){response=s.q1;page=0;if(s.selection){store.dispatch({type:'SELECT',selection:null});return;}}const selected=s.selection?.kind==='Q1_SEGMENT'?s.selection:null;
    const key=JSON.stringify([s.q1?.output_sha256,s.size,page,s.reviewMode,selected,s.loading,s.activeRun?.run_id]);if(key===lastKey){if(selected&&liveTarget)liveSegment(liveTarget,s,generation);return;}lastKey=key;liveTarget=null;liveTick=null;
    const version=++generation;root.replaceChildren();const wrap=el('div',undefined,'q1-wall');root.append(wrap);const m=wallModel(response,{size:s.size,page});page=m.page;
    const head=el('p',m.message,'q1-message');wrap.append(head);if(!response)return;
    const count=el('p',`本回應 ${m.returned}／總數 ${m.total} · ${m.ranking}`,'q1-count');wrap.append(count);
    const group=el('section',undefined,'q1-match');wrap.append(group);
    const title=el('div',undefined,'q1-section-head');title.append(el('strong','相符'));
    const previous=el('button','上一頁'),next=el('button','下一頁');previous.disabled=page===0;next.disabled=page>=m.pages-1;
    previous.onclick=()=>{page--;lastKey='';render(store.getState());};next.onclick=()=>{page++;lastKey='';render(store.getState());};title.append(previous,el('span',`${page+1}／${m.pages}`),next);group.append(title);
    const grid=el('div',undefined,'q1-grid');grid.style.gridTemplateColumns=`repeat(${m.layout?.cols??1},minmax(0,1fr))`;grid.style.gridTemplateRows=`repeat(${m.layout?.rows??1},minmax(0,1fr))`;group.append(grid);
    for(const result of m.tiles){const card=el('article',undefined,'q1-card');grid.append(card);if(!result){card.append(el('span','無更多相符鏡頭'));continue;}
      card.append(el('h3',`#${result.rank} ${result.camera_id}`));const media=el('div',undefined,'q1-media');card.append(media);
      const segment=result.matched_segments[0];if(segment)image(media,s,result,segment,version);else media.textContent='UNKNOWN · 無代表畫面';
      card.append(el('p',coverageText(result.coverage),'q1-coverage'));
      const list=el('div',undefined,'q1-segments');card.append(list);
      for(const seg of result.matched_segments){const row=el('div',undefined,'q1-segment');row.append(el('span',`OBS [${formatSource(seg.range_us[0])}, ${formatSource(seg.range_us[1])}) · ${seg.matched_frames}/${seg.evaluated_frames}`));
        const play=el('button','播放片段');play.onclick=async()=>{store.dispatch({type:'PAUSE'});const selection=segmentSelection(result,seg);store.dispatch({type:'SELECT',selection});store.dispatch({type:'SET_T_US',tUs:seg.range_us[0]});const frame=await playback.buffer.prepare(s.activeRun,seg.range_us[0],[result.camera_id]);if(store.getState().selection===selection&&frame.get(result.camera_id)?.status==='READY'){await playback.present(liveTarget,frame.get(result.camera_id),{camera:result.camera_id,timestamp:seg.range_us[0],alive:()=>store.getState().selection===selection});store.dispatch({type:'PLAY'});}};row.append(play);
        const ids=seg.representative.observation_ids;
        for(const id of ids){const seed=el('button',ids.length===1?'設為 Q2 起點':`Q2 起點 ${id}`);seed.onclick=()=>{try{execute(seedRequest(response,result,seg,s.activeRun,api.getSession(),s.switchMode,id));}catch(e){head.textContent=`無法執行 · ${e.message}`;}};row.append(seed);}list.append(row);
      }
    }
    for(const [label,items] of [['已推論、條件不符',m.groups.noMatch],['未評估',m.groups.notEvaluated]]){const section=el('section',undefined,'q1-none');section.append(el('strong',label));for(const item of items)section.append(el('p',`${item.camera_id} · ${coverageText(item.coverage)}`));if(!items.length)section.append(el('span','（無）'));wrap.append(section);}
    if(m.nextCursor){const more=el('button',`載入更多（總數 ${m.total}）`);more.onclick=()=>execute({...s.lastRequest,cursor:m.nextCursor});wrap.append(more);}
    if(selected&&response===s.q1){const panel=el('section',undefined,'q1-playback');liveTitle=el('strong',`${selected.camera_id} · ${formatSource(s.tUs)}`);panel.append(liveTitle);const frame=el('div',undefined,'q1-media');liveTarget=frame;panel.append(frame);const close=el('button','回結果牆');close.onclick=()=>{store.dispatch({type:'PAUSE'});store.dispatch({type:'SELECT',selection:null});};panel.append(close);wrap.append(panel);liveSegment(frame,s,version);}
    const prov=el('div',undefined,'q1-provenance');renderProvenance(prov,response,{review:s.reviewMode});wrap.append(prov);
  }
  const unsub=store.subscribe(render);render(store.getState());return {destroy(){destroyed=true;generation++;unsub();root.replaceChildren();}};
}

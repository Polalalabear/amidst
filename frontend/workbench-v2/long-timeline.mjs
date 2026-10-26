import {createView,zoom,pan,fit,centerOn,xToTime,timeToX,ticks,formatTick,layoutMarkers,neighborEvent,span,isVisible,followPlayhead} from './timeline-model.mjs';
import {wallLayout,wallCells,summary,lanes,longestClips,STATES} from './monitor-wall-model.mjs';
import {formatSource} from './q-time.mjs';
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};
const CLIP_MIN_US=120e6;
async function main(){
  let fx;try{const r=await fetch('fixtures/long_timeline_synthetic.json');if(!r.ok)throw new Error(r.status);fx=await r.json();}catch(e){$('error').textContent=`UNKNOWN · 無法載入 fixture（${e.message}）`;return;}
  if(fx.fixture_marker!=='FIXTURE'||fx.cameras.length>8){$('error').textContent='UNKNOWN · fixture 邊界不符';return;}
  const D=fx.source_duration_us;let view=createView(D),t=0,timer=null;const followOn=()=>$('follow').checked;
  const stage=$('stage'),pxWidth=()=>stage.clientWidth-(parseFloat(getComputedStyle(stage).paddingLeft)||0);
  const setView=v=>{view=v;draw();};const seek=x=>{t=Math.max(0,Math.min(D-1,Math.round(x)));drawLight();};
  const follow=()=>{if(followOn()&&!isVisible(view,t))setView(followPlayhead(view,t));};
  function drawOverview(){const o=$('overview-events');o.replaceChildren();for(const e of fx.events){const i=el('i');i.style.left=e.t_us/D*100+'%';o.append(i);}
    const w=$('overview-window');w.style.left=view.range[0]/D*100+'%';w.style.width=span(view)/D*100+'%';}
  function drawRuler(){const r=$('ruler');r.replaceChildren();const tk=ticks(view,pxWidth());for(const x of tk.ticks){const s=el('span',formatTick(x.t,tk.step_us));s.style.left=x.left+'%';r.append(s);}}
  function drawEvents(){const box=$('events');box.replaceChildren();for(const m of layoutMarkers(fx.events,view,pxWidth(),26)){
    const b=el('button',m.count>1?String(m.count):'●',m.kind);b.style.left=m.left+'%';b.title=m.count>1?`${m.label}（點擊放大聚焦）`:`${m.label} · ${formatSource(m.t_us)}`;b.dataset.kind=m.kind;
    b.onclick=()=>{if(m.count>1){const ts=m.ids.map(id=>fx.events.find(e=>e.id===id).t_us);const a=Math.min(...ts),z=Math.max(...ts);setView(fit(view,[a,Math.max(z,a+MIN)],0.5));seek(a);}else{setView(centerOn(view,m.t_us));seek(m.t_us);}};box.append(b);}}
  const MIN=5e6;
  function drawLanes(){const box=$('lanes');box.replaceChildren();for(const l of lanes(fx.cameras,fx.q1_clips,view)){const row=el('div',undefined,'lane');row.append(el('label',l.camera_id));
    for(const s of l.states){const d=el('div',undefined,`seg ${s.state}`);d.style.left=s.left+'%';d.style.width=s.width+'%';d.title=`${l.camera_id} ${s.state} [${formatSource(s.range_us[0])}, ${formatSource(s.range_us[1])})`;row.append(d);}
    for(const s of l.q1){const d=el('div',undefined,'seg q1');d.style.left=s.left+'%';d.style.width=s.width+'%';d.title=`Q1 命中 ${s.matched_frames}/${s.evaluated_frames}`;row.append(d);}box.append(row);}}
  function drawWall(){const cells=wallCells(fx.cameras,t),lay=wallLayout(cells.length),w=$('wall');w.replaceChildren();w.style.gridTemplateColumns=`repeat(${lay.cols},minmax(0,1fr))`;
    for(const c of cells){const d=el('div',undefined,'cell');d.dataset.state=c.state;d.append(el('strong',c.camera_id),el('span',c.label));
      const hit=(fx.q1_clips[c.camera_id]??[]).find(s=>s.range_us[0]<=t&&t<s.range_us[1]);if(hit)d.append(el('em','Q1 命中片段內'));
      if(c.segment_range_us)d.append(el('small',`[${formatSource(c.segment_range_us[0])}, ${formatSource(c.segment_range_us[1])})`));w.append(d);}
    const s=summary(cells);$('wall-summary').textContent=STATES.map(k=>`${k} ${s[k]}`).join(' · ')+' · 無 RGB（合成資料）';$('wall-time').textContent=formatSource(t);}
  function drawClips(){const box=$('clips');box.replaceChildren();const clips=longestClips(fx.q1_clips,CLIP_MIN_US);if(!clips.length){box.textContent='（無長片段）';return;}
    for(const c of clips){const row=el('div',undefined,'clip');const b=el('button',`${c.camera_id} ${formatSource(c.range_us[0])} → ${formatSource(c.range_us[1])}`);b.onclick=()=>{setView(fit(view,c.range_us,0.15));seek(c.range_us[0]);};
      const bar=el('div',undefined,'bar'),i=el('i');i.style.left=c.range_us[0]/D*100+'%';i.style.width=(c.range_us[1]-c.range_us[0])/D*100+'%';bar.append(i);row.append(b,bar);box.append(row);}}
  function drawHead(){const left=timeToX(view,t,pxWidth());const ph=$('playhead');ph.style.display=isVisible(view,t)?'':'none';ph.style.left=`calc(${(parseFloat(getComputedStyle(stage).paddingLeft)||0)}px + ${left}px)`;
    $('overview-head').style.left=t/D*100+'%';$('clock').textContent=formatSource(t);}
  function drawLight(){drawHead();drawWall();}
  function draw(){$('window').textContent=`視窗 ${formatSource(view.range[0])} – ${formatSource(view.range[1])}（${(D/span(view)).toFixed(1)}×）`;drawOverview();drawRuler();drawEvents();drawLanes();drawHead();drawWall();}
  const anchorFrom=e=>{const r=stage.getBoundingClientRect(),pad=parseFloat(getComputedStyle(stage).paddingLeft)||0;return xToTime(view,Math.max(0,Math.min(pxWidth(),e.clientX-r.left-pad)),pxWidth());};
  const mid=()=>Math.round((view.range[0]+view.range[1])/2);
  $('zin').onclick=()=>setView(zoom(view,2,isVisible(view,t)?t:mid()));$('zout').onclick=()=>setView(zoom(view,.5,isVisible(view,t)?t:mid()));
  $('zall').onclick=()=>setView(createView(D));
  $('zevt').onclick=()=>{const e=neighborEvent(fx.events,t-1,1)??fx.events[0];if(e){setView(fit(view,[Math.max(0,e.t_us-30e6),e.t_us+30e6],0));seek(e.t_us);}};
  $('next').onclick=()=>{const e=neighborEvent(fx.events,t,1);if(e){seek(e.t_us);if(!isVisible(view,e.t_us))setView(centerOn(view,e.t_us));else draw();}};
  $('prev').onclick=()=>{const e=neighborEvent(fx.events,t,-1);if(e){seek(e.t_us);if(!isVisible(view,e.t_us))setView(centerOn(view,e.t_us));else draw();}};
  // Plain wheel scrolls the page; zoom only with Ctrl/⌘ (also pinch on trackpads). Horizontal wheel pans.
  stage.addEventListener('wheel',e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();setView(zoom(view,e.deltaY<0?1.5:1/1.5,anchorFrom(e)));}else if(Math.abs(e.deltaX)>Math.abs(e.deltaY)){e.preventDefault();setView(pan(view,e.deltaX/pxWidth()*span(view)));}},{passive:false});
  let drag=null;stage.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;drag={x:e.clientX,range:view.range,moved:false};stage.setPointerCapture(e.pointerId);});
  stage.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x;if(Math.abs(dx)>3)drag.moved=true;if(drag.moved)setView(pan({...view,range:drag.range},-dx/pxWidth()*(drag.range[1]-drag.range[0])));});
  stage.addEventListener('pointerup',e=>{if(drag&&!drag.moved)seek(anchorFrom(e));drag=null;});
  $('overview').addEventListener('click',e=>{const r=$('overview').getBoundingClientRect();setView(centerOn(view,(e.clientX-r.left)/r.width*D));});
  document.addEventListener('keydown',e=>{if(e.target.matches('select,input'))return;if(e.key==='+'||e.key==='=')$('zin').click();else if(e.key==='-')$('zout').click();else if(e.key==='ArrowRight')$('next').click();else if(e.key==='ArrowLeft')$('prev').click();});
  $('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;$('play').textContent='播放';return;}$('play').textContent='暫停';let last=performance.now();
    timer=setInterval(()=>{const now=performance.now(),dt=now-last;last=now;const next=t+dt*1000*Number($('speed').value);if(next>=D){seek(D-1);follow();$('play').click();return;}seek(next);follow();},100);};
  window.addEventListener('resize',draw);drawClips();draw();window.__longTimeline={get view(){return view;},get t(){return t;}};
}
main();

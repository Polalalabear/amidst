import {timelineModel} from './q2-timeline-model.mjs';import {formatSource} from './q-time.mjs';
export function mount({store,slots}) {
  const root=slots.timeline;let key='';
  function render(s){const next=JSON.stringify([s.task,s.q2?.output_sha256,s.artifacts.decisions?.length,s.reviewMode]);if(next===key)return;key=next;root.replaceChildren();if(s.task!=='q2'||!s.q2)return;
    const m=timelineModel(s.q2,s.artifacts.decisions??[],{review:s.reviewMode}),track=document.createElement('div');track.className='q2-track';root.append(track);
    for(const item of m.segments){const b=document.createElement('button');b.className=`q2-track-segment q2-track-${item.kind.toLowerCase()}`;b.style.left=item.left+'%';b.style.width=item.width+'%';b.textContent=item.label;b.title=`[${formatSource(item.range_us[0])}, ${formatSource(item.range_us[1])})`;b.onclick=()=>{store.dispatch({type:'PAUSE'});store.dispatch({type:'SELECT',selection:null});store.dispatch({type:'SET_T_US',tUs:item.range_us[0]});};track.append(b);}
    if(s.reviewMode){const points=document.createElement('div');points.className='q2-points';root.append(points);const groups=new Map();for(const p of m.points){let group=groups.get(p.source_time_us);if(!group){group=document.createElement('div');group.className='q2-point-group';group.style.left=p.left+'%';if(p.left>90)group.style.transform='translateX(-100%)';groups.set(p.source_time_us,group);points.append(group);}const b=document.createElement('button');b.className='q2-point';b.textContent=`◆${p.step_index}`;b.title=`${formatSource(p.source_time_us)} · ${p.decided_by} · ${p.action??'狀態'}${p.accepted?'':' · 拒絕'}`;b.onclick=()=>{store.dispatch({type:'PAUSE'});store.dispatch({type:'SET_T_US',tUs:p.source_time_us});store.dispatch({type:'SELECT',selection:{kind:'INSPECT_DECISION',decision_id:p.decision_id}});};group.append(b);}}
  }
  const unsub=store.subscribe(render);render(store.getState());return {destroy(){unsub();root.replaceChildren();}};
}

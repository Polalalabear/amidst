import {parseRaw,contentHash,noPrivate,freezeDeep} from './q-validate.mjs';
const need=(ok,code)=>{if(!ok)throw new Error(code);};
export async function validateSuite(text){
  const suite=parseRaw(text);noPrivate(suite);
  need(suite.schema_version==='q-demo.event-mode-suite.v1'&&suite.source_kind==='SYNTHETIC'&&suite.counts_for_acceptance===false&&suite.provider_kind==='MECHANICAL_FAKE_PROVIDER'&&Array.isArray(suite.cases)&&suite.cases.length>0,'SUITE_BOUNDARY');
  need(await contentHash(suite,{excludeRoot:['content_sha256']})===suite.content_sha256,'SUITE_HASH');
  for(const c of suite.cases){const r=c.comparison;need(c.offline_trace_replay_equal===true&&c.provider_kind==='MECHANICAL_FAKE_PROVIDER'&&r.schema_version==='q-demo.event-mode-comparison.v1'&&r.source_kind==='SYNTHETIC'&&r.counts_for_acceptance===false&&r.gt_read===false&&r.identity_verdict==='UNCONFIRMED'&&r.accuracy===null,'COMPARISON_BOUNDARY');
    need(Number.isSafeInteger(r.lost_after_us)&&r.lost_after_us>0&&r.threshold_status==='EXPERIMENT_ONLY_NOT_APPROVED','LOST_POLICY');
    need(await contentHash(r,{excludeRoot:['content_sha256']})===r.content_sha256,'COMPARISON_HASH');
    need(r.modes.length===2&&r.modes[0].mode==='BACKEND_FLAGS'&&r.modes[1].mode==='AGENT_DECISIONS','MODES');
    for(const m of r.modes){need(await contentHash(m,{excludeRoot:['content_sha256']})===m.content_sha256,'MODE_HASH');
      need(await contentHash(m.response,{excludeRoot:['output_sha256','stats']})===m.response.output_sha256&&m.response.identity_verdict==='UNCONFIRMED'&&m.response.provenance.gt_read===false,'RESPONSE_HASH');
      need(JSON.stringify(m.response.resolved_scope)===JSON.stringify(r.scope),'SOURCE_SCOPE');
      for(const f of m.flags)need(['FOUND','LOST'].includes(f.type)&&f.source_output_sha256===m.response.output_sha256&&await contentHash(f,{excludeRoot:['content_sha256']})===f.content_sha256&&f.absence_verdict==='UNKNOWN','FLAG_PIN');
    }
  }return freezeDeep(suite);
}
export function stateAt(mode,timeUs){
  const timeline=mode.response.timeline,visible=timeline.find(s=>s.range_us[0]<=timeUs&&timeUs<s.range_us[1]);
  const prior=timeline.filter(s=>s.kind==='ON_CAMERA'&&s.range_us[0]<=timeUs).at(-1);
  const flags=mode.flags.filter(f=>f.timestamp_us<=timeUs),last=flags.at(-1);
  return {camera:visible?.kind==='ON_CAMERA'?visible.camera_id:prior?.camera_id??'UNKNOWN',supported:visible?.kind==='ON_CAMERA',lost:last?.type==='LOST',flags};
}
export function comparisonEnd(report){return Math.max(0,...report.modes.flatMap(m=>m.response.timeline.map(s=>s.range_us[1])));}
const names={supported_candidate:'候選有支持',empty_first_candidate:'首候選無觀測，後候選有支持',no_candidate_observations:'候選持續無觀測',temporary_loss_recovery:'短暫失聯後原鏡頭恢復',provider_failure:'Agent provider 故障兜底'};
export async function mount(root=document){
  const $=s=>root.querySelector(s);let suite,current,t=0,playing=false,previous=null,raf;
  function stop(){playing=false;previous=null;$('#play').textContent='播放';}
  function render(){if(!current)return;const end=comparisonEnd(current.comparison);$('#scrub').max=String(Math.max(0,end-1));$('#scrub').value=String(t);$('#time').textContent=(t/1e6).toFixed(6)+' s';
    $('#source').textContent=`來源 ${current.comparison.scope.scene_id} / ${current.comparison.scope.run_ids.join(', ')} · 追丟期限 ${current.comparison.lost_after_us/1e6} s（僅實驗值）`;
    $('#panels').replaceChildren();for(const m of current.comparison.modes){if($('#mode').value!=='both'&&$('#mode').value!==m.mode)continue;const v=stateAt(m,t),a=root.createElement('article'),h=root.createElement('h2');h.textContent=m.mode==='BACKEND_FLAGS'?'後端 FOUND／LOST':'Agent 候選決策';a.append(h);
      const camera=root.createElement('div');camera.className='camera';const label=root.createElement('div');label.textContent='鏡頭 '+v.camera;const missing=root.createElement('small');missing.textContent='RGB MISSING · 合成程式回應重播';label.append(missing);camera.append(label);a.append(camera);
      const note=root.createElement('p');note.className='notification';note.textContent=v.lost?'LOST：追丟目標，保留目前鏡頭':v.supported?'有觀測支持，繼續播放':'搜尋中，保留目前鏡頭';a.append(note);
      const dl=root.createElement('dl');for(const [label,value] of [['模型呼叫',m.metrics.provider_calls],['取證次數',m.metrics.evidence_queries],['切鏡次數',m.metrics.switches],['追丟提示',m.metrics.lost_notifications],['故障兜底',m.metrics.fallback_used?'是':'否']]){const dt=root.createElement('dt'),dd=root.createElement('dd');dt.textContent=label+'（整段）';dd.textContent=String(value);dl.append(dt,dd);}a.append(dl);
      const list=root.createElement('ol');for(const f of v.flags){const li=root.createElement('li');li.textContent=`${(f.timestamp_us/1e6).toFixed(6)} s · ${f.type} · ${f.camera_id}${f.switch?' · 硬切':''}`;list.append(li);}a.append(list);$('#panels').append(a);}
  }
  try{const response=await fetch('comparison.json',{cache:'no-store'});need(response.ok,'REPORT_NOT_AVAILABLE');suite=await validateSuite(await response.text());
    for(const c of suite.cases){const o=root.createElement('option');o.value=c.case_id;o.textContent=names[c.case_id]??c.case_id;$('#case').append(o);}current=suite.cases[0];render();
  }catch(e){$('#error').textContent='比較資料不可用：'+e.message;$('#play').disabled=true;return;}
  $('#case').onchange=()=>{stop();current=suite.cases.find(c=>c.case_id===$('#case').value);t=0;render();};$('#mode').onchange=render;
  $('#scrub').oninput=()=>{stop();t=Number($('#scrub').value);render();};$('#restart').onclick=()=>{stop();t=0;render();};$('#play').onclick=()=>{playing=!playing;previous=null;if(t>=comparisonEnd(current.comparison)-1)t=0;$('#play').textContent=playing?'暫停':'播放';render();};
  function frame(now){if(playing&&previous!==null){const end=comparisonEnd(current.comparison);t=Math.min(Math.max(0,end-1),t+Math.round((now-previous)*1000));if(t>=end-1)stop();render();}previous=now;raf=requestAnimationFrame(frame);}raf=requestAnimationFrame(frame);
  return {destroy(){cancelAnimationFrame(raf);stop();}};
}
if(typeof document!=='undefined')mount();

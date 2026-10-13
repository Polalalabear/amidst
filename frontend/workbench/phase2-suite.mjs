import {presentationJSON} from './presentation-data.mjs';

const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list=value=>Array.isArray(value)?value:[];
const states={READY:'準備執行',RUNNING:'本機模型調查中',NEEDS_CLARIFICATION:'需要補充線索',COMPLETED:'流程完成・回答待核對',
  STOPPED:'已停止',FAILED:'執行失敗',BUDGET_EXHAUSTED:'已達執行預算',RESUME_REQUIRED:'請恢復調查'};
const ruleNames={REGION_ENTRY:'區域進入',REGION_EXIT:'區域離開',SUSTAINED_DWELL:'持續停留'};
const evidence=value=>'<details class="technical"><summary>來源與驗證收據</summary><pre>'+h(presentationJSON(value))+'</pre></details>';
export function validateSuiteContext(snapshot,context){
  if(context.schema_version!=='workbench.phase2-suite.v1'||context.scene_id!==snapshot.scene_id)throw Error('整合服務與目前場景不一致。');
  if(context.status==='UNAVAILABLE')return context;
  if(context.source_run_id!==snapshot.run_id||context.source_sha256!==snapshot.source_hash)throw Error('整合服務的來源版本不一致。');
  for(const [kind,part] of [['research',context.research],['agent',context.agent]]){
    if(!part)continue;const b=part.binding;
    if(b?.scene_id!==snapshot.scene_id||b.source_sha256!==context.source_sha256||
      (kind==='research'?b.source_run_id:b.run_id)!==snapshot.run_id||
      (context.observation_mode&&(kind==='research'?b.mode:b.observation_mode)!==context.observation_mode))
      throw Error('研究或模型調查的來源／模式綁定不一致。');
  }
  if(context.storage&&context.storage.backend!=='POSTGRESQL')throw Error('本機保存服務未使用已核准的資料庫。');
  return context;
}
export function validateAgentCase(context,record,mode){
  const wanted=context.agent?.binding,b=record.binding;
  if(record.schema_version!=='local.agent.case.v1'||!wanted||
    ['scene_id','run_id','run_ref','source_ref','source_sha256','freeze_ref','product_freeze_ref','config_sha256']
      .some(key=>b?.[key]!==wanted[key])||b.observation_mode!==mode||b.decision_stage!=='RESULTS')
    throw Error('模型調查與目前來源、模式或凍結版本不一致。');
  return record;
}
export function validateSuiteWindow(start,end,range){
  if(!Number.isFinite(start)||!Number.isFinite(end)||start<range[0]||end>range[1]||end<start||end-start>120)
    throw Error('請指定來源範圍內、最長 120 秒的時間窗。');
  return [start,end];
}
export function agentResultHTML(record){
  const receipts=list(record.tool_receipts),answer=record.answer;
  const truncated=receipts.some(r=>r.result?.data?.retrieval?.truncated===true||r.result?.presentation_truncated===true);
  const cameras=list(record.camera_refs).map(ref=>list(record.binding?.cameras).find(c=>c.camera_ref===ref)?.camera_id??ref);
  return '<h3>'+h(states[record.state]??record.state)+'</h3>'+
    (cameras.length?'<p>此調查：'+h(cameras.join('、'))+' · '+h(list(record.time_range).join('–'))+' 秒</p>':'')+
    (record.question?'<p class="notice">'+h(record.question)+'</p>':'')+
    (answer?'<p class="agent-answer">'+h(typeof answer==='string'?answer:answer.text)+'</p>':'')+
    (answer?'<p class="notice">回答是模型解讀；請核對引用中的原始資料、未定候選與身分限制。</p>':'')+
    (truncated?'<p class="notice warning">工具結果有截斷或省略，請查看查詢收據；本次回答不代表全部事件。</p>':'')+
    (record.waiting_for_model?'<p class="notice">正在等待本機服務就緒，會自動核對狀態並繼續。</p>':'')+
    '<p>已完成 '+receipts.length+' 次工具查詢；候選與未定狀態保留。</p>'+
    (record.error_code?'<p class="notice warning">'+h(record.error_code)+'</p>':'')+
    (receipts.length?'<details><summary>查詢證據與引用（'+receipts.length+'）</summary>'+receipts.map(r=>
      '<article class="result-card"><h4>'+h(r.tool)+' · '+h(r.receipt_ref)+'</h4>'+evidence(r)+'</article>').join('')+'</details>':'')+
    evidence({binding:record.binding,metrics:record.metrics,model_identity:record.model_identity,answer,
      storage_receipt:record.storage_receipt,model_receipts:record.model_receipts});
}

export function researchDiagnosticsHTML(result,mode='photos_plus_observations'){
  if(result.status!=='CERTIFIED_AGGREGATE')return '<p>尚未取得已綁定發布版本的評估。</p>'+evidence(result);
  const e=result.evaluation,base=e.variants?.baseline?.[mode],selected=e.variants?.selected?.[mode];
  if(!base||!selected)return evidence(result);
  const metrics=[['身分切換',r=>r.pixels_and_local_identity?.within_local_track_id_switches],
    ['碎片化（已偵測有標籤 contacts）',r=>r.pixel_population?.fragmented_track_count],
    ['混合身分 tracks',r=>r.pixel_population?.mixed_known_identity_tracks],
    ['單點 tracks',r=>r.pixel_population?.single_measurement_track_count],
    ['detector contacts',r=>r.pixels_and_local_identity?.measurement_count],
    ['有標籤／可見分母',r=>r.pixels_and_local_identity?.bounded_labeled_measurements+'／'+r.pixels_and_local_identity?.eligible_visible_actor_contacts],
    ['偵測 precision／recall',r=>r.pixels_and_local_identity?.bounded_detection_precision+'／'+r.pixels_and_local_identity?.one_to_one_visible_contact_recall]];
  return '<p class="notice warning">05 尚未達可接受的精度改善。本頁使用研究基線；開發集選出的實驗在固定測試上遭拒絕，保留其退步與全部分母。</p>'+
    '<div class="gallery-table"><table><thead><tr><th>量測</th><th>使用中基線</th><th>被拒絕實驗</th></tr></thead><tbody>'+metrics.map(([label,value])=>
    '<tr><th>'+h(label)+'</th><td>'+h(value(base)??'N/A')+'</td><td>'+h(value(selected)??'N/A')+'</td></tr>').join('')+'</tbody></table></div>'+
    '<p>此測試來源先前已公開使用，並非新的密封 holdout。新區域規則缺少獨立事件 reference，其精度為 N/A；受控合成邏輯測試與本輪實測分開記錄。</p>'+associationDiagnosticsHTML(base)+evidence(result);
}

export function associationDiagnosticsHTML(row){
  const ablations=row.association_feature_ablations??{},full=ablations.full,without=ablations.without_appearance;
  if(!full||!without)return '';
  const same=full.candidate_pool_sha256===without.candidate_pool_sha256&&
    full.eligible_query_count===without.eligible_query_count&&full.true_link_count===without.true_link_count;
  if(!same)return '<p class="notice warning">候選池不同，沒有呈現外觀效果的成對比較。</p>';
  const groups=[['完整外觀／時間／空間',full],['移除外觀',without]];
  const n=v=>typeof v==='number'?v.toFixed(3):'N/A';
  return '<h3>09 · 合成關聯診斷</h3><p>同一候選池；分母 '+h(full.eligible_query_count)+' 個可比較 query／'+h(full.true_link_count)+' 個同身分可行片段對。R@K 是條件式候選命中，包含已產生的片段；不代表完整人物召回、真實 ReID 或機率。</p>'+
    '<div class="gallery-table"><table><thead><tr><th>比較</th><th>R@1</th><th>R@3</th><th>R@5</th><th>pair錯接／漏接／未定</th></tr></thead><tbody>'+groups.map(([label,g])=>
    '<tr><th>'+h(label)+'</th>'+['1','3','5'].map(k=>'<td>'+n(g.identity_candidate_recall_at_k?.[k])+'</td>').join('')+'<td>'+h(g.pair_level_false_merge_count)+'／'+h(g.pair_level_missed_link_count)+'／'+h(g.unresolved_link_count)+'</td></tr>').join('')+'</tbody></table></div>';
}

/** One bounded scene, original source media and true local-model progress. */
export class Phase2SuitePanel{
  constructor(container,{call,snapshot,mediaURL}){
    Object.assign(this,{container,call,snapshot,mediaURL,closed:false,epoch:0,agentEpoch:0,context:null,
      record:null,mode:'photos_plus_observations',pollTimer:null,busy:false});
    this.initialize().catch(e=>this.error(e));
  }
  q(selector){return this.container.querySelector(selector);}
  current(epoch=this.epoch,agentEpoch=null){return !this.closed&&epoch===this.epoch&&(agentEpoch===null||agentEpoch===this.agentEpoch);}
  async request(action,payload={},agentEpoch=null){
    const epoch=this.epoch;if(!this.current(epoch,agentEpoch))throw Error('SESSION_CHANGED');
    const result=await this.call('suite_'+action,{...payload,observation_mode:this.mode});
    if(!this.current(epoch,agentEpoch))throw Error('SESSION_CHANGED');return result;
  }
  error(error){if(!this.closed&&error.message!=='SESSION_CHANGED')this.q('[data-suite-error]').textContent=error.message;}
  async initialize(){
    this.container.innerHTML='<div data-suite-error class="inline-error" role="status"></div>'+
      '<section class="panel"><div class="panel-head"><div><h2>自然語言調查（本機原型）</h2><p>指定鏡頭與時間，以本機模型逐步查詢並引用來源。</p></div></div><div class="panel-body" data-agent-body>正在核對來源與本機模型。</div></section>'+
      '<section class="panel"><div class="panel-head"><div><h2>合成品質與單人事件</h2><p>獨立精度實驗、關聯診斷、區域出入與持續停留。</p></div></div><div class="panel-body" data-research-body>正在核對凍結實驗。</div></section>'+
      '<section class="panel"><div class="panel-head"><div><h2>保存與恢復</h2><p>查詢證據與調查狀態保存在同一個本機來源範圍。</p></div></div><div class="panel-body" data-storage-body></div></section>';
    const context=await this.request('context');this.context=validateSuiteContext(this.snapshot,context);
    this.renderAgent();this.renderResearch();this.renderStorage();
    if(context.agent){const result=await this.request('agent_list');this.renderHistory(result.items);}
  }
  renderStorage(){
    const s=this.context.storage;
    this.q('[data-storage-body]').innerHTML=s?'<p>本機 PostgreSQL 已接入實際查詢與調查保存。</p><p>凍結來源匯入：'+h(this.context.storage_import?.status??'未提供')+'</p>'+evidence(s):
      '<p class="notice warning">本機資料庫尚未接入，模型調查不可開始。</p>';
  }
  renderAgent(){
    const ctx=this.context.agent,body=this.q('[data-agent-body]');
    if(!ctx){body.innerHTML='<p>此場景尚未提供已凍結的本機模型調查來源。</p>';return;}
    const b=ctx.binding,cameras=list(b.cameras);
    body.innerHTML='<p>模型查詢既有凍結事件與軌跡，保留候選及未定；本批區域規則與品質結果由下方研究查詢呈現。模型只讀公開資料，回答引用實際工具收據。</p>'+
      '<form data-agent-form><div class="suite-scope"><label class="field"><span>觀測模式</span><select data-agent-mode>'+['photos_plus_observations','photos_only'].map(m=>
      '<option value="'+m+'" '+(m===this.mode?'selected':'')+'>'+(m==='photos_only'?'照片模式':'照片與觀測')+'</option>').join('')+'</select></label>'+
      '<label class="field"><span>鏡頭</span><select data-agent-camera>'+cameras.map(c=>'<option value="'+h(c.camera_ref)+'">'+h(c.camera_id)+'</option>').join('')+'</select></label>'+
      '<label class="field"><span>開始（秒）</span><input data-agent-start type="number" step="any" value="'+h(b.time_range[0])+'"></label>'+
      '<label class="field"><span>結束（秒）</span><input data-agent-end type="number" step="any" value="'+h(Math.min(b.time_range[1],b.time_range[0]+30))+'"></label></div>'+
      '<label class="field"><span>中文或英文調查需求</span><textarea data-agent-message maxlength="3000" required placeholder="請查看此鏡頭在指定時間內的事件，保留未定與替代，並引用證據。"></textarea></label>'+
      '<button class="btn primary" type="submit">開始本機調查</button></form>'+
      '<div class="toolbar"><button class="btn" data-agent-stop disabled>停止</button><button class="btn" data-agent-resume disabled>恢復</button><button class="btn" data-agent-refresh>更新紀錄</button></div>'+
      '<form data-agent-reply hidden><label class="field"><span>補充線索</span><textarea data-agent-reply-message maxlength="3000" required></textarea></label><button class="btn" type="submit">補充並繼續</button></form>'+
      '<div data-agent-result role="status" aria-live="polite"></div><div data-agent-history></div>'+evidence({model:ctx.model_identity,policy:ctx.policy});
    this.q('[data-agent-form]').onsubmit=e=>{e.preventDefault();this.start().catch(e=>this.error(e));};
    this.q('[data-agent-mode]').onchange=()=>this.changeMode(this.q('[data-agent-mode]').value).catch(e=>this.error(e));
    this.q('[data-agent-stop]').onclick=()=>this.control('stop').catch(e=>this.error(e));
    this.q('[data-agent-resume]').onclick=()=>this.control('resume').catch(e=>this.error(e));
    this.q('[data-agent-refresh]').onclick=()=>this.loadHistory().catch(e=>this.error(e));
    this.q('[data-agent-reply]').onsubmit=e=>{e.preventDefault();this.reply().catch(e=>this.error(e));};
  }
  recoveryKey(){return 'amidst-local-agent:'+this.snapshot.scene_id+':'+this.snapshot.source_hash+':'+this.mode;}
  remember(record){if(record.recovery_token)try{globalThis.localStorage?.setItem(this.recoveryKey(),JSON.stringify({agent_ref:record.agent_ref,recovery_token:record.recovery_token}));}catch{}}
  async loadHistory(){const result=await this.request('agent_list');this.renderHistory(result.items);}
  renderHistory(items){
    const body=this.q('[data-agent-history]');if(!body)return;
    let recovery=null;try{recovery=JSON.parse(globalThis.localStorage?.getItem(this.recoveryKey())??'null');}catch{}
    body.innerHTML='<details><summary>已保存的調查（'+list(items).length+'）</summary>'+list(items).map(r=>'<p><button class="micro-link" data-agent-open="'+h(r.agent_ref)+'">'+h(states[r.state]??r.state)+' · '+h(r.agent_ref)+'</button></p>').join('')+'</details>'+
      (recovery?'<button class="btn" data-agent-recover>恢復此瀏覽器保存的調查</button>':'');
    body.querySelectorAll('[data-agent-open]').forEach(el=>{el.onclick=()=>this.open(el.dataset.agentOpen).catch(e=>this.error(e));});
    const button=body.querySelector('[data-agent-recover]');if(button)button.onclick=()=>this.recover(recovery).catch(e=>this.error(e));
  }
  async changeMode(mode){
    if(['READY','RUNNING'].includes(this.record?.state))await this.control('stop');
    clearTimeout(this.pollTimer);this.agentEpoch++;this.epoch++;this.record=null;this.mode=mode;
    this.context=validateSuiteContext(this.snapshot,await this.request('context'));this.renderAgent();this.renderResearch();if(this.context.agent)await this.loadHistory();
  }
  async start(){
    if(this.busy)return;this.busy=true;
    try{
      if(['READY','RUNNING'].includes(this.record?.state))await this.control('stop');
      const time_range=validateSuiteWindow(Number(this.q('[data-agent-start]').value),Number(this.q('[data-agent-end]').value),this.context.agent.binding.time_range);
      const message=this.q('[data-agent-message]').value.trim();if(!message)throw Error('請輸入調查需求。');
      const camera_refs=[this.q('[data-agent-camera]').value];const epoch=++this.agentEpoch;
      this.accept(await this.request('agent_start',{message,camera_refs,time_range},epoch));await this.drive(epoch);
    }finally{this.busy=false;}
  }
  accept(record){
    validateAgentCase(this.context,record,this.mode);this.record=record;this.remember(record);
    this.q('[data-agent-result]').innerHTML=agentResultHTML(record);
    this.q('[data-agent-stop]').disabled=!['READY','RUNNING','NEEDS_CLARIFICATION'].includes(record.state);
    this.q('[data-agent-resume]').disabled=!['STOPPED','FAILED','RESUME_REQUIRED'].includes(record.state);
    this.q('[data-agent-reply]').hidden=record.state!=='NEEDS_CLARIFICATION';
  }
  async drive(epoch=this.agentEpoch){
    if(!this.current(this.epoch,epoch)||!this.record)return;
    if(this.record.state==='READY'){
      const ref=this.record.agent_ref;
      try{
        this.accept(await this.request('agent_advance',{agent_ref:ref},epoch));this.waitSince=0;
      }catch(error){
        // The public API intentionally groups safe ValueError codes. Re-read the
        // owner-bound case before waiting; source/mode/model mismatches never retry.
        if(error.code!=='INVALID_OR_STALE_REQUEST')throw error;
        const latest=await this.request('agent_get',{agent_ref:ref},epoch);
        if(latest.agent_ref!==ref||latest.model_version_current!==true)throw error;
        validateAgentCase(this.context,latest,this.mode);
        if(latest.state==='READY'){
          this.waitSince ||= Date.now();
          if(Date.now()-this.waitSince>180000)throw Error('本機服務仍未就緒，請稍後更新調查紀錄。');
          latest.waiting_for_model=true;
        }
        this.accept(latest);
      }
    }
    if(this.record.state==='RUNNING'||(this.record.state==='READY'&&this.record.waiting_for_model)){
      clearTimeout(this.pollTimer);this.pollTimer=setTimeout(()=>this.poll(epoch).catch(e=>this.error(e)),1200);
    }
  }
  async poll(epoch){
    if(!this.current(this.epoch,epoch))return;
    this.accept(await this.request('agent_get',{agent_ref:this.record.agent_ref},epoch));await this.drive(epoch);
  }
  async control(action){
    if(!this.record)return;clearTimeout(this.pollTimer);const epoch=++this.agentEpoch;
    this.waitSince=0;this.q('[data-suite-error]').textContent='';
    this.accept(await this.request('agent_'+action,{agent_ref:this.record.agent_ref},epoch));
    if(action==='resume')await this.drive(epoch);
  }
  async reply(){
    const message=this.q('[data-agent-reply-message]').value.trim();if(!message)throw Error('請輸入補充線索。');
    const epoch=++this.agentEpoch;this.accept(await this.request('agent_reply',{agent_ref:this.record.agent_ref,message},epoch));await this.drive(epoch);
  }
  async open(ref){
    clearTimeout(this.pollTimer);const epoch=++this.agentEpoch;
    this.accept(await this.request('agent_get',{agent_ref:ref},epoch));await this.drive(epoch);
  }
  async recover(credentials){
    clearTimeout(this.pollTimer);const epoch=++this.agentEpoch;
    this.accept(await this.request('agent_recover',credentials,epoch));
    await this.drive(epoch);
  }
  renderResearch(){
    const ctx=this.context.research,body=this.q('[data-research-body]');
    if(!ctx){body.innerHTML='<p>此場景沒有接入本批次的合成研究實驗。</p>';return;}
    const cameras=list(this.snapshot.cameras),range=this.context.agent?.binding.time_range??this.snapshot.time_range??[0,0];
    body.innerHTML='<p class="notice warning">05 的實驗未通過精度改善門檻；目前事件與診斷使用基線。</p><p>09 只提供合成關聯假說，排名是原候選池順序，不是身分機率；10 僅區域出入與持續停留，沒有獨立事件精度認證。</p>'+
      '<button class="btn" data-suite-diagnostics>查看精度與錯誤分母</button><div data-suite-diagnostics-body></div>'+
      '<form data-suite-query><div class="suite-scope"><label class="field"><span>鏡頭</span><select data-suite-camera>'+cameras.map(c=>'<option value="'+h(c.camera_id??c.id)+'">'+h(c.camera_id??c.id)+'</option>').join('')+'</select></label>'+
      '<label class="field"><span>開始（秒）</span><input data-suite-start type="number" step="any" value="'+range[0]+'"></label><label class="field"><span>結束（秒）</span><input data-suite-end type="number" step="any" value="'+Math.min(range[1],range[0]+30)+'"></label></div><button class="btn" type="submit">查詢單人事件與診斷</button></form>'+
      '<div data-suite-query-result></div><div data-suite-event-result></div>'+evidence(ctx);
    this.q('[data-suite-diagnostics]').onclick=()=>this.diagnostics().catch(e=>this.error(e));
    this.q('[data-suite-query]').onsubmit=e=>{e.preventDefault();this.query().catch(e=>this.error(e));};
  }
  async diagnostics(){const r=await this.request('diagnostics');this.q('[data-suite-diagnostics-body]').innerHTML=researchDiagnosticsHTML(r,r.binding?.mode??this.mode);}
  async query(){
    const start=Number(this.q('[data-suite-start]').value),end=Number(this.q('[data-suite-end]').value);
    validateSuiteWindow(start,end,this.context.agent?.binding.time_range??this.snapshot.time_range??[0,0]);
    const result=await this.request('query',{camera_id:this.q('[data-suite-camera]').value,start,end});
    if(result.binding?.freeze_ref!==this.context.research.binding.freeze_ref)throw Error('查詢結果與研究凍結版本不一致。');
    const events=list(result.events);this.q('[data-suite-query-result]').innerHTML='<p>本次取得 '+events.length+' 個規則候選；查詢截斷與未定保留於收據。</p>'+events.map(e=>
      '<article class="result-card"><h4>'+h(ruleNames[e.kind]??e.kind??e.event_type)+' · '+h(e.support_state==='SUPPORTED'?'觀測支持':e.support_state==='UNKNOWN'?'未定':e.support_state??e.state)+'</h4><p>'+h(e.region_id??'')+' · '+h(list(e.time_range).join('–'))+' 秒 · '+(e.support_state==='UNKNOWN'?'證據不足，尚未觸發':e.active?'候選仍活動':'已結束或撤回')+'</p><button class="btn" data-suite-event="'+h(e.event_ref)+'">查看觸發、撤回與原影格</button></article>').join('')+evidence(result);
    this.q('[data-suite-query-result]').querySelectorAll('[data-suite-event]').forEach(el=>{el.onclick=()=>this.event(el.dataset.suiteEvent).catch(e=>this.error(e));});
  }
  async event(event_ref){
    const result=await this.request('event',{event_ref}),event=result.event??result;
    this.q('[data-suite-event-result]').innerHTML='<h3>單人規則候選</h3>'+evidence(result)+list(event.source_frames).slice(0,5).map(f=>
      '<figure><img loading="lazy" style="max-width:200px" src="'+h(this.mediaURL(f.media_ref??f.frame_ref))+'" alt="原合成來源影格"><figcaption>'+h(f.camera_id)+' · '+h(f.timestamp)+' 秒 · 原來源影格</figcaption></figure>').join('');
  }
  dispose(){
    if(!this.closed&&['READY','RUNNING','NEEDS_CLARIFICATION'].includes(this.record?.state))
      Promise.resolve(this.call('suite_agent_stop',{agent_ref:this.record.agent_ref,observation_mode:this.mode})).catch(()=>{});
    this.closed=true;this.epoch++;this.agentEpoch++;clearTimeout(this.pollTimer);
  }
}

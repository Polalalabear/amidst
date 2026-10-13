import {presentationJSON} from './presentation-data.mjs';

const h=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const list=value=>Array.isArray(value)?value:[];
const technical=(label,value)=>'<details class="technical"><summary>'+h(label)+'</summary><pre>'+h(presentationJSON(value))+'</pre></details>';
const statusNames={QUEUED:'等待執行',RUNNING:'執行中',CANCEL_REQUESTED:'正在停止',COMPLETED:'已完成',
  CANCELLED:'已停止',FAILED:'執行失敗',INTERRUPTED:'執行已中斷',ACTIVE:'作答中',SUBMITTED:'已提交',
  STOPPED:'任務已停止',RESUME_REQUIRED:'需要恢復憑證',
  UNAVAILABLE:'此場景尚未接入',UNKNOWN:'證據不足／未定'};
export const runStudyStatus=value=>statusNames[value]??String(value??'尚未開始');
export const activeRunState=value=>['QUEUED','RUNNING','CANCEL_REQUESTED'].includes(value);
export const runStudySceneSupported=snapshot=>snapshot?.scene_id==='synthetic-lab';
export function validateStudyAnswer(task,answer){
  if(answer?.unknown===true&&Object.keys(answer).length===1)return {unknown:true};
  const type=task.answer_type;
  if(type==='timestamp'&&Object.keys(answer??{}).length===1&&Number.isFinite(answer.timestamp)&&
    answer.timestamp>=task.time_range[0]&&answer.timestamp<=task.time_range[1])return {...answer};
  if(type==='presence'&&Object.keys(answer??{}).length===1&&['PRESENT','MISSING'].includes(answer.presence))return {...answer};
  if(type==='count'&&Object.keys(answer??{}).length===1&&Number.isInteger(answer.count)&&answer.count>=0&&answer.count<=64)return {...answer};
  const labels=list(task.targets).map(target=>target.label);
  if(type==='order'&&Object.keys(answer??{}).length===1&&Array.isArray(answer.order)&&
    answer.order.length===labels.length&&new Set(answer.order).size===labels.length&&answer.order.every(label=>labels.includes(label)))
    return {order:[...answer.order]};
  throw Error('請提供符合此任務的答案，或選擇證據不足／未定。');
}
const parameterNames={appearance_max_distance:'外觀距離上限',max_speed_m_s:'速度上限（m/s）',
  max_sample_gap_s:'同鏡頭量測缺口（秒）',max_association_gap_s:'跨鏡頭關聯缺口（秒）',
  max_overlap_separation_m:'重疊位置距離上限（m）',projection_uncertainty_m:'投影設定範圍（m）'};
const countNames={frames:'來源影格',measurements:'量測',local_tracks:'局部 tracks',observations:'片段',
  events:'事件候選',gaps:'缺口',candidates:'替代路線'};
const number=value=>typeof value==='number'&&Number.isFinite(value)?String(value):'N/A';
const taskFamily=family=>({earliest_registered_frame:'最早來源影格',registered_frame_count:'來源影格數量',
  exact_registration_presence:'指定秒數影格登錄',source_frame_order:'來源影格先後'})[family]??family;
export function studyTaskPrompt(task){
  const scope=list(task.camera_ids).join('／')+'，'+list(task.time_range).join('–')+' 秒';
  if(task.family==='earliest_registered_frame')return scope+'：找出範圍內最早登錄的原來源影格秒數。只核對來源登錄，不辨識人物。';
  if(task.family==='registered_frame_count')return scope+'：計算範圍內已登錄的原來源影格數量；不計算人物、量測或推論事件。';
  if(task.family==='source_frame_order')return scope+'：開啟參考 '+list(task.targets).map(target=>target.label).join('／')+'，依來源秒數由早到晚排列。';
  const exact=String(task.prompt??'').match(/at exactly ([0-9.eE+-]+) seconds/);
  if(task.family==='exact_registration_presence'&&exact)return scope+'：此鏡頭是否在精確的 '+exact[1]+' 秒登錄原來源影格？判定的是影格登錄，與畫面中是否有目標不同。';
  return task.prompt??'未提供任務說明。';
}
const freshKey=()=>globalThis.crypto?.randomUUID?.()??Date.now()+'-'+Math.random().toString(16).slice(2);
export function validateRunParameters(context,parameters){
  const supported=context.supported_parameters??{};
  if(Object.keys(parameters).length!==Object.keys(supported).length||
    Object.entries(parameters).some(([name,value])=>!supported[name]||!Number.isFinite(value)||
      value<supported[name].min||value>supported[name].max))throw Error('請使用此場景允許範圍內的參數。');
  return {...parameters};
}
export function validateRunResult(context,job,result){
  if(job.state!=='COMPLETED'||job.result_available!==true||result.schema_version!=='workbench.synthetic-run-result.v1'||result.view_only!==true||
    result.formal_phase1_acceptance!==false||result.scene_id!==context.scene_id||
    result.source_run_id!==context.source_run_id||result.source_sha256!==context.source_sha256||
    ['job_ref','new_run_id','annotation_version','annotation_sha256','input_sha256','config_sha256']
      .some(field=>result[field]!==job[field]))throw Error('新 run 結果與來源或設定版本不一致。');
  return result;
}
const xyPoints=points=>list(points).map(point=>Array.isArray(point)?point:point?.world_position)
  .filter(point=>Array.isArray(point)&&point.length>=2&&point.slice(0,2).every(Number.isFinite));
export function runTrajectoryHTML(event){
  const projected=xyPoints(event.projected_path),routes=list(event.candidates).map(candidate=>xyPoints(candidate.polyline));
  const points=[...projected,...routes.flat()];
  if(!points.length)return '<p class="status-text">此事件沒有可繪製的位置；不補造動線。</p>';
  const minX=Math.min(...points.map(point=>point[0])),maxX=Math.max(...points.map(point=>point[0]));
  const minY=Math.min(...points.map(point=>point[1])),maxY=Math.max(...points.map(point=>point[1]));
  const span=Math.max(maxX-minX,maxY-minY,.1),x=value=>20+(value-minX)*120/span,y=value=>140-(value-minY)*120/span;
  const colors=['#df9d32','#a586ee','#74cdbb','#eb7981'];
  return '<figure><svg viewBox="0 0 240 160" width="320" role="img" aria-label="來源投影點與盲區替代路線的 XY 示意">'+
    '<rect width="240" height="160" fill="#111b25"/>'+routes.map((route,index)=>route.length>=2?'<polyline points="'+
    route.map(point=>x(point[0])+','+y(point[1])).join(' ')+'" fill="none" stroke="'+colors[index%colors.length]+'" stroke-width="2" stroke-dasharray="5 4"/>':'').join('')+
    projected.map(point=>'<circle cx="'+x(point[0])+'" cy="'+y(point[1])+'" r="3" fill="#6bbde8"/>').join('')+
    '</svg><figcaption>XY 示意 · 藍點為來源投影，虛線為盲區替代。合成設定、唯讀，未確認人物或實際動線。</figcaption></figure>';
}
export function runComparisonHTML(result,mediaURL=null){
  const comparison=result.comparison??{};
  const observations=new Map(list(result.observations).map(observation=>[observation.observation_ref,observation]));
  return '<p class="notice">本次只比較同源合成流程的輸出數量；數量變化不代表精度或正式驗收改善。</p>'+
    '<div class="gallery-table"><table><thead><tr><th>項目</th><th>原凍結結果</th><th>新 run</th><th>差異</th></tr></thead><tbody>'+
    Object.entries(countNames).map(([key,label])=>'<tr><th scope="row">'+h(label)+'</th><td>'+number(comparison.baseline?.[key])+
      '</td><td>'+number(comparison.new?.[key])+'</td><td>'+number(comparison.delta?.[key])+'</td></tr>').join('')+
    '</tbody></table></div><details class="wide-section"><summary>新 run 的 '+list(result.events).length+' 個事件與全部替代、來源影格</summary>'+list(result.events).map((event,index)=>
      '<article class="result-card"><h4>事件候選 '+(index+1)+' · '+h(event.kind??'未分類')+'</h4><p>'+h(list(event.camera_ids).join('／'))+
      ' · '+h(list(event.time_range).join('–'))+' 秒 · '+list(event.candidates).length+' 條替代／'+list(event.trajectories).length+' 個時間假說</p>'+
      '<p>'+h(event.uncertainty??'合成來源與候選，尚未確認人物身分。')+'</p>'+runTrajectoryHTML({...event,
        projected_path:event.projected_path??list(event.observation_refs).flatMap(ref=>list(observations.get(ref)?.projected_path))})+
      (list(event.candidates).length?'<div class="gallery-table"><table><thead><tr><th>原順序</th><th>長度（m）</th><th>最低／估計時間（秒）</th><th>約束狀態</th></tr></thead><tbody>'+list(event.candidates).map((candidate,i)=>
      '<tr><th>替代 '+(i+1)+'</th><td>'+number(candidate.path_length)+'</td><td>'+number(candidate.minimum_travel_time)+'／'+number(candidate.estimated_travel_time)+
      '</td><td>'+h(list(candidate.feasibility_flags).join('／')||'未提供')+'</td></tr>').join('')+'</tbody></table></div>':'<p>此事件未提供路線候選；保留缺失。</p>')+
      (mediaURL?list(event.source_frames).slice(0,2).map(frame=>'<figure><img loading="lazy" style="max-width:160px" src="'+h(mediaURL(frame.frame_ref))+
      '" alt="'+h(frame.camera_id)+' 原來源影格"><figcaption>'+h(frame.camera_id)+' · '+number(frame.timestamp)+' 秒 · 原來源影格</figcaption></figure>').join('')+
      (list(event.source_frames).length>2?'<p>畫面顯示前 2 個來源影格；完整 references 保留在來源收據。</p>':''):'')+'</article>').join('')+
    (!list(result.events).length?'<p>新 run 沒有事件候選；未推定人物或行為不存在。</p>':'')+
    '</details>'+technical('新 run 來源、設定與可回看的候選',result);
}
export function studyReportHTML(report){
  const metrics=report.metrics??{},correctness={NOT_SUBMITTED:'尚未提交',CORRECT:'正確',INCORRECT:'不正確',UNKNOWN:'證據不足／未定'}[metrics.correctness]??'未提供';
  const rows=[['作答時間（秒）',Number.isFinite(metrics.duration_ms)?metrics.duration_ms/1000:null],
    ['鏡頭查看請求次數',metrics.camera_view_count],['影格開啟請求次數',metrics.frame_open_count],['不同鏡頭數',metrics.distinct_camera_count],
    ['答案修正次數',metrics.correction_count],['輔助證據開啟次數',metrics.evidence_open_count],['已完成分母',metrics.completed_denominator],
    ['流程有效的完成分母',metrics.eligible_completed_denominator],['正確答案',metrics.correct_count],
    ['未定答案',metrics.unresolved_count],['排除的紀錄',metrics.protocol_excluded_count],['排除的恢復缺口（秒）',Number.isFinite(metrics.excluded_resume_gap_ms)?metrics.excluded_resume_gap_ms/1000:null]];
  return '<h3>本次任務報告 · '+h(report.mode==='manual'?'人工搜尋':'輔助調查')+'</h3><p>'+h(studyTaskPrompt(report.task??{}))+'</p><p>答案正確性：'+h(correctness)+
    ' · '+h(runStudyStatus(report.status))+' · '+(report.protocol_valid?'流程紀錄有效':'流程紀錄排除或尚未完成')+'</p>'+
    '<div class="gallery-table"><table><tbody>'+rows.map(([label,value])=>'<tr><th scope="row">'+h(label)+'</th><td>'+number(value)+'</td></tr>').join('')+'</tbody></table></div>'+
    '<p>本次為準備與演練紀錄；沒有宣稱實際操作員驗收或調查效率改善。人工與輔助方式須使用相同來源與任務才可比較。</p>'+studyComparisonHTML(report.comparison)+
    technical('固定來源、分母與比較範圍',{study_ref:report.study_ref,binding:report.binding,phase:report.phase,
      actual_operator_acceptance:report.actual_operator_acceptance,protocol_valid:report.protocol_valid,comparison:report.comparison,metrics});
}
export function studyComparisonHTML(comparison){
  if(!comparison||comparison.same_binding!==true||comparison.same_task!==true)return '<p>尚未取得相同來源與任務的成對紀錄。</p>';
  const duration=mode=>{
    const values=list(mode.correct_duration_ms);
    return comparison.eligible_for_duration_comparison&&values.length&&values.every(value=>Number.isFinite(value)&&value>=0)?
      (values.reduce((sum,value)=>sum+value,0)/values.length/1000).toFixed(3):'N/A';
  };
  return '<h4>同任務、同來源的人工／輔助紀錄</h4><div class="gallery-table"><table><thead><tr><th>方式</th><th>嘗試數</th><th>完成／有效分母</th><th>正確／不正確／未定</th><th>排除／停止</th><th>正確有效完成的平均秒數</th></tr></thead><tbody>'+['manual','assisted'].map(name=>{
    const mode=comparison.modes?.[name]??{};
    return '<tr><th>'+(name==='manual'?'人工搜尋':'輔助調查')+'</th><td>'+number(mode.attempt_count)+'</td><td>'+number(mode.completed_denominator)+'／'+number(mode.eligible_completed_denominator)+
      '</td><td>'+number(mode.correct_count)+'／'+number(mode.incorrect_count)+'／'+number(mode.unresolved_count)+'</td><td>'+number(mode.protocol_excluded_count)+'／'+number(mode.stopped_count)+
      '</td><td>'+duration(mode)+'</td></tr>';}).join('')+'</tbody></table></div><p>重複任務的學習效應尚未控制；這些準備紀錄不建立效率改善結論。未定與排除仍各自列出。</p>';
}

/** Separate new-run execution and voluntary operator-study views, scoped to one panel. */
export class RunStudyPanel {
  constructor(container,{call,snapshot,mediaURL,reviewVersion=0}){
    Object.assign(this,{container,call,snapshot,mediaURL,reviewVersion,closed:false,serial:1,
      runEpoch:0,studyEpoch:0,pollTimer:null,runContext:null,studyContext:null,
      job:null,jobs:[],runResult:null,attempt:null,studyReport:null,studyFrames:[],
      selectedStudyMode:'manual',runBusy:false,studyBusy:false,manualStudyPending:false,runRequests:new Set(),
      runImageRequests:new Set(),imageLoads:new WeakMap()});
    this.initialize().catch(error=>this.error(error));
  }
  q(selector){return this.container.querySelector(selector);}
  token(section){return {serial:this.serial,section,epoch:this[section+'Epoch']};}
  current(token){return !this.closed&&this.serial===token.serial&&this[token.section+'Epoch']===token.epoch;}
  check(token){if(!this.current(token))throw Error('SESSION_CHANGED');}
  async request(action,payload={},token=this.token('run')){
    this.check(token);
    if(action.startsWith('run_')&&this.manualBlocked())throw Error('人工搜尋任務進行中，新 run 查詢與結果暫停。');
    const operation=Promise.resolve(this.call(action,payload));
    if(action.startsWith('run_'))this.runRequests.add(operation);
    try{const result=await operation;this.check(token);return result;}
    finally{this.runRequests.delete(operation);}
  }
  error(error,section=null){
    if(this.closed||error.message==='SESSION_CHANGED')return;
    const box=this.q(section==='run'?'[data-run-error]':section==='study'?'[data-study-error]':'[data-run-study-error]');
    if(box)box.textContent=error.message;
  }
  async initialize(){
    this.render();
    if(!runStudySceneSupported(this.snapshot))return;
    // Discover an unfinished manual trial before any assisted run access can contaminate it.
    try{await this.loadStudyContext();}catch(error){this.error(error,'study');}
    if(this.closed)return;
    if(this.manualBlocked())this.q('[data-run-body]').textContent='有未完成的人工搜尋任務；新 run 查詢與結果暫停。請先恢復或停止該任務。';
    else try{await this.loadRunContext();}catch(error){this.error(error,'run');}
  }
  render(){
    const supported=runStudySceneSupported(this.snapshot);
    this.container.innerHTML='<div data-run-study-error class="inline-error" role="status"></div>'+
      '<section class="panel"><div class="panel-head"><div><h2>04 · 修改後的新 run</h2><p>版本與參數另存，原凍結結果保留。</p></div></div><div class="panel-body"><div data-run-error class="inline-error" role="status"></div><div data-run-body>'+
      (supported?'正在讀取此場景的執行能力。':'此場景尚未接入新 run；目前只支援雙鏡頭基礎實驗室。')+
      '</div></div></section><section class="panel wide-section"><div class="panel-head"><div><h2>06 · 操作員評測準備</h2><p>以相同任務記錄人工搜尋與輔助調查的操作與答案。</p></div></div><div class="panel-body"><div data-study-error class="inline-error" role="status"></div><div data-study-body>'+
      (supported?'正在讀取固定任務與資料範圍。':'此場景尚未接入評測；沒有建立操作者試驗或替代評測結果。')+
      '</div></div></section>';
  }
  version(){return typeof this.reviewVersion==='function'?this.reviewVersion():this.reviewVersion;}
  async loadRunContext(){
    const token=this.token('run'),context=await this.request('run_context',{},token);
    if(context.available!==true){this.q('[data-run-body]').textContent='此場景尚未提供可執行的新 run。';return;}
    if(context.schema_version!=='workbench.synthetic-jobs.v1'||context.scene_id!==this.snapshot.scene_id||
      context.source_run_id!==this.snapshot.run_id)throw Error('新 run 能力與場景來源不一致。');
    this.runContext=context;this.renderRun();await this.loadJobs(token);
  }
  renderRun(){
    const c=this.runContext,version=Number.isInteger(this.version())?this.version():c.current_annotation_version;
    this.q('[data-run-body]').innerHTML='<p>建立獨立的新 run；目前只處理 E0 合成 RGB、量測、關聯與候選。來源影格及既有凍結結果保留。</p>'+
      '<form data-run-form><label class="field"><span>人工修改版本</span><input data-run-version type="number" min="0" max="'+h(c.current_annotation_version)+'" step="1" value="'+h(version)+'" required></label>'+
      '<div class="port-grid">'+Object.entries(c.supported_parameters).map(([name,spec])=>'<label class="field"><span>'+h(parameterNames[name]??name)+
      '</span><input data-run-param="'+h(name)+'" type="number" min="'+h(spec.min)+'" max="'+h(spec.max)+'" step="any" value="'+h(spec.default)+'" required></label>').join('')+'</div>'+
      '<p class="status-text">使用選定版本的支撐面、區域及鏡頭投影設定。參數是工程設定，沒有人體或機率認證。</p><button class="btn primary" data-run-start type="submit">建立並執行新 run</button></form>'+
      '<div class="investigation-controls"><button class="btn" data-run-stop disabled>停止目前工作</button><button class="btn" data-run-refresh>更新狀態</button><button class="btn" data-run-history-refresh>載入歷史</button></div>'+
      '<label class="field"><span>保存的新 run</span><select data-run-history><option value="">尚未載入</option></select></label><button class="btn" data-run-open>開啟保存結果</button>'+
      '<div data-run-status>尚未建立新 run。</div><div data-run-comparison></div>'+technical('執行能力與來源',c);
    this.q('[data-run-form]').onsubmit=event=>{event.preventDefault();this.action('run',()=>this.startRun());};
    this.q('[data-run-stop]').onclick=()=>this.action('run',()=>this.stopRun());
    this.q('[data-run-refresh]').onclick=()=>this.action('run',()=>this.refreshRun());
    this.q('[data-run-history-refresh]').onclick=()=>this.action('run',()=>this.loadJobs());
    this.q('[data-run-open]').onclick=()=>this.action('run',()=>this.openJob());
  }
  async action(section,callback){
    if(this[section+'Busy'])return;
    this[section+'Busy']=true;const token=this.token(section);this.controls();
    this.q(section==='run'?'[data-run-error]':'[data-study-error]').textContent='';
    try{await callback();}catch(error){if(!this.closed&&this.serial===token.serial)this.error(error,section);}
    finally{this[section+'Busy']=false;if(!this.closed)this.controls();}
  }
  controls(){
    const active=activeRunState(this.job?.state);
    const studying=this.attempt?.status==='RUNNING';
    const manual=this.manualBlocked(),unfinished=list(this.studies).some(study=>['RUNNING','RESUME_REQUIRED'].includes(study.status));
    const states={'[data-run-start]':manual||this.runBusy||active,'[data-run-stop]':manual||this.runBusy||!active,
      '[data-run-refresh]':manual||this.runBusy||!this.job,'[data-run-open]':manual||this.runBusy,
      '[data-run-history-refresh]':manual||this.runBusy,'[data-run-version]':manual||this.runBusy,
      '[data-study-start]':this.studyBusy||studying||unfinished,'[data-study-stop]':this.studyBusy||!studying,
      '[data-study-mode]':this.studyBusy||studying,'[data-study-task]':this.studyBusy||studying,
      '[data-study-history-refresh]':this.studyBusy,'[data-study-history-report]':this.studyBusy||studying,
      '[data-study-resume]':this.studyBusy||studying,'[data-study-stop-saved]':this.studyBusy||studying,
      '[data-study-submit]':this.studyBusy||!studying,
      '[data-study-view-source]':this.studyBusy||!studying,'[data-study-correction]':this.studyBusy||!studying,
      '[data-study-evidence]':this.studyBusy||!studying};
    for(const [selector,disabled] of Object.entries(states)){const element=this.q(selector);if(element)element.disabled=disabled;}
    this.container.querySelectorAll('[data-study-target]').forEach(button=>{button.disabled=this.studyBusy||!studying;});
    this.container.querySelectorAll('[data-run-param]').forEach(input=>{input.disabled=manual||this.runBusy;});
  }
  manualBlocked(){return this.manualStudyPending||this.attempt?.mode==='manual'&&this.attempt.status==='RUNNING';}
  trackRunImage(image){
    if(image.complete)return Promise.resolve();
    if(this.imageLoads.has(image))return this.imageLoads.get(image);
    let finish;
    const operation=new Promise(resolve=>{
      finish=()=>{image.removeEventListener('load',finish);image.removeEventListener('error',finish);
        this.runImageRequests.delete(operation);resolve();};
      image.addEventListener('load',finish,{once:true});image.addEventListener('error',finish,{once:true});
    });
    this.imageLoads.set(image,operation);this.runImageRequests.add(operation);
    // Closed lazy sections have not requested their images yet; settle them before the trial.
    image.loading='eager';if(image.complete)finish();
    return operation;
  }
  async pauseRunForStudy({drainImages=true}={}){
    this.manualStudyPending=true;this.runEpoch++;clearTimeout(this.pollTimer);this.pollTimer=null;
    const comparison=this.q('[data-run-comparison]');if(comparison)comparison.hidden=true;
    this.controls();
    if(drainImages)this.container.querySelectorAll('[data-run-comparison] img').forEach(image=>this.trackRunImage(image));
    const pending=[...this.runRequests,...(drainImages?this.runImageRequests:[])];
    let timeout;
    try{
      await Promise.race([Promise.allSettled(pending),new Promise((_,reject)=>{
        timeout=setTimeout(()=>reject(Error('來源影格或舊工作請求尚未結束；本次任務尚未開始，請稍後再試。')),10000);})]);
      if(!this.closed)comparison?.replaceChildren();
    }finally{clearTimeout(timeout);}
  }
  async releaseRunAfterStudy(){
    this.manualStudyPending=false;if(this.closed)return;
    if(!this.runContext){try{await this.loadRunContext();}catch(error){this.error(error,'run');}}
    else if(this.runResult)this.q('[data-run-comparison]').innerHTML=runComparisonHTML(this.runResult,this.mediaURL);
    if(this.q('[data-run-comparison]'))this.q('[data-run-comparison]').hidden=false;
    this.controls();this.schedulePoll();
  }
  async reconcileRunPause(token){
    if(!this.current(token))return;
    try{
      await this.loadStudies(token);this.check(token);
      const activeManual=this.attempt?.mode==='manual'&&this.attempt.status==='RUNNING'||
        this.studies.some(study=>study.mode==='manual'&&['RUNNING','RESUME_REQUIRED'].includes(study.status));
      if(activeManual){this.manualStudyPending=true;this.controls();}
      else await this.releaseRunAfterStudy();
    }catch{
      // A failed read cannot prove the server did not create or restore a manual trial.
      if(this.current(token)){this.manualStudyPending=true;this.controls();}
    }
  }
  assertJob(job){
    if(!this.runContext||job.scene_id!==this.snapshot.scene_id||job.source_run_id!==this.runContext.source_run_id||
      typeof job.job_ref!=='string')throw Error('工作與目前場景來源不一致。');
    return job;
  }
  async startRun(){
    const parameters=Object.fromEntries([...this.container.querySelectorAll('[data-run-param]')]
      .map(input=>[input.dataset.runParam,Number(input.value)]));
    validateRunParameters(this.runContext,parameters);
    const annotation_version=Number(this.q('[data-run-version]').value);
    if(!Number.isInteger(annotation_version)||annotation_version<0||annotation_version>this.runContext.current_annotation_version)
      throw Error('請選取有效的人工修改版本。');
    const input={annotation_version,parameters},fingerprint=JSON.stringify(input);
    if(this.pendingStart?.fingerprint!==fingerprint)this.pendingStart={fingerprint,idempotency_key:freshKey()};
    clearTimeout(this.pollTimer);this.pollTimer=null;this.runEpoch++;
    const token=this.token('run');this.runResult=null;this.q('[data-run-comparison]').replaceChildren();
    const job=await this.request('run_start',{...input,idempotency_key:this.pendingStart.idempotency_key},token);
    this.check(token);this.job=this.assertJob(job);this.pendingStart=null;
    this.showRunStatus();await this.loadJobs(token);this.schedulePoll();
  }
  showRunStatus(){
    if(!this.job)return;
    const job=this.job,progress=job.progress??{};
    this.q('[data-run-status]').innerHTML='<p><strong>'+h(runStudyStatus(job.state))+'</strong> · 人工修改版本 '+h(job.annotation_version)+
      ' · '+number(progress.completed)+'／'+number(progress.total)+' 階段</p>'+
      (job.failure_code?'<p class="notice warning">工作未完成，請檢查本次工作收據。</p>':'')+
      '<p>停止請求會保留已有工作狀態；只有完成並核對的結果可以開啟比較。</p>'+technical('工作收據、來源及執行階段',job);
    this.controls();
  }
  async loadJobs(token=this.token('run')){
    const result=await this.request('run_list',{},token);this.jobs=list(result.items).map(job=>this.assertJob(job));
    this.q('[data-run-history]').innerHTML='<option value="">選擇保存的新 run</option>'+this.jobs.map((job,index)=>
      '<option value="'+h(job.job_ref)+'">工作 '+(index+1)+' · 版本 '+h(job.annotation_version)+' · '+h(runStudyStatus(job.state))+'</option>').join('');
    if(this.job)this.q('[data-run-history]').value=this.job.job_ref;
  }
  async openJob(){
    const ref=this.q('[data-run-history]').value;if(!ref)throw Error('請先選取保存的新 run。');
    clearTimeout(this.pollTimer);this.pollTimer=null;this.runEpoch++;
    const token=this.token('run');this.runResult=null;this.q('[data-run-comparison]').replaceChildren();
    const job=await this.request('run_get',{job_ref:ref},token);this.job=this.assertJob(job);
    if(job.job_ref!==ref)throw Error('工作 reference 不一致。');
    this.showRunStatus();if(job.result_available)await this.loadRunResult(token);this.schedulePoll();
  }
  async refreshRun(token=this.token('run')){
    if(!this.job)throw Error('請先建立或開啟新 run。');
    const ref=this.job.job_ref,job=await this.request('run_get',{job_ref:ref},token);
    if(job.job_ref!==ref)throw Error('工作 reference 不一致。');
    this.job=this.assertJob(job);this.showRunStatus();
    if(job.result_available&&!this.runResult)await this.loadRunResult(token);
    return job;
  }
  async loadRunResult(token=this.token('run')){
    const job=this.job,result=await this.request('run_result',{job_ref:job.job_ref},token);
    if(this.job?.job_ref!==job.job_ref)throw Error('SESSION_CHANGED');
    this.runResult=validateRunResult(this.runContext,job,result);
    this.q('[data-run-comparison]').innerHTML=runComparisonHTML(this.runResult,this.mediaURL);this.q('[data-run-comparison]').hidden=false;
  }
  schedulePoll(){
    clearTimeout(this.pollTimer);this.pollTimer=null;
    if(this.closed||this.manualBlocked()||!activeRunState(this.job?.state))return;
    const token=this.token('run');
    this.pollTimer=setTimeout(async()=>{
      this.pollTimer=null;if(!this.current(token))return;
      try{await this.refreshRun(token);}catch(error){if(this.current(token))this.error(error,'run');}
      if(this.current(token))this.schedulePoll();
    },1500);
  }
  async stopRun(){
    if(!this.job||!activeRunState(this.job.state))throw Error('目前沒有可停止的工作。');
    const ref=this.job.job_ref;clearTimeout(this.pollTimer);this.pollTimer=null;this.runEpoch++;
    const token=this.token('run'),job=await this.request('run_cancel',{job_ref:ref},token);
    if(job.job_ref!==ref)throw Error('工作 reference 不一致。');
    this.job=this.assertJob(job);this.showRunStatus();this.schedulePoll();
  }
  async loadStudyContext(){
    const token=this.token('study'),context=await this.request('operator_study_context',{},token);
    if(context.available!==true){this.q('[data-study-body]').textContent='此場景尚未提供固定任務評測。';return;}
    if(context.schema_version!=='operator.study.context.v1'||context.status!=='PREPARATION_REHEARSAL'||
      context.binding?.scene_id!==this.snapshot.scene_id||context.binding?.run_id!==this.snapshot.run_id)
      throw Error('評測任務與目前場景來源不一致。');
    this.studyContext=context;this.renderStudy();await this.loadStudies(token);
  }
  renderStudy(){
    const c=this.studyContext;
    this.q('[data-study-body]').innerHTML='<p class="notice">固定任務的準備與演練；這些紀錄不等於實際操作員驗收、精度改善或正式研究通過。</p>'+
      '<label class="field"><span>固定任務</span><select data-study-task>'+list(c.tasks).map((task,index)=>
      '<option value="'+h(task.task_ref)+'">任務 '+(index+1)+' · '+h(taskFamily(task.family))+'</option>').join('')+'</select></label>'+
      '<label class="field"><span>作業方式</span><select data-study-mode><option value="manual">人工搜尋 · 原來源影格</option><option value="assisted">輔助調查 · 登錄時間證據</option></select></label>'+
      '<p data-study-mode-note>人工搜尋僅顯示原來源影格；提交前不顯示參考答案或輔助摘要。</p><p data-study-prompt></p>'+
      '<button class="btn primary" data-study-start>開始本次任務</button><button class="btn" data-study-stop disabled>停止本次任務</button>'+
      '<div data-study-status>尚未開始任務。</div><div data-study-navigation></div><div data-study-view></div><div data-study-answer></div><div data-study-report></div>'+
      '<details class="technical"><summary>恢復憑證（只供本機恢復，不會寫入報告）</summary><label class="field"><span>本次紀錄 reference</span><input data-study-current-ref readonly></label><label class="field"><span>本次恢復憑證</span><input data-study-current-token type="password" readonly></label><button class="btn small" data-study-token-toggle>顯示／隱藏本次憑證</button></details>'+
      '<div class="wide-section"><label class="field"><span>保存的任務紀錄</span><select data-study-history><option value="">尚未載入</option></select></label>'+
      '<button class="btn" data-study-history-refresh>載入任務紀錄</button><button class="btn" data-study-history-report>查看已提交紀錄</button><button class="btn" data-study-stop-saved>停止選取的未完成紀錄</button>'+
      '<details class="technical"><summary>跨工作台連線恢復</summary><label class="field"><span>保存的紀錄 reference（目前清單沒有時填入）</span><input data-study-recovery-ref autocomplete="off"></label>'+
      '<label class="field"><span>要恢復的紀錄憑證</span><input data-study-recovery-input type="password" autocomplete="off"></label><button class="btn" data-study-resume>以憑證恢復任務或報告</button></details></div>'+technical('固定任務的來源及評測契約',{binding:c.binding,status:c.status});
    this.q('[data-study-task]').onchange=()=>this.studyPreview();
    this.q('[data-study-mode]').onchange=()=>this.changeStudyMode(this.q('[data-study-mode]').value);
    for(const [selector,action] of [['[data-study-start]',()=>this.startStudy()],['[data-study-stop]',()=>this.stopStudy()],
      ['[data-study-history-refresh]',()=>this.loadStudies()],['[data-study-history-report]',()=>this.openStudyReport()],
      ['[data-study-stop-saved]',()=>this.stopSavedStudy()],['[data-study-resume]',()=>this.resumeStudy()]])
      this.q(selector).onclick=()=>this.action('study',action);
    this.q('[data-study-token-toggle]').onclick=()=>{const field=this.q('[data-study-current-token]');field.type=field.type==='password'?'text':'password';};
    this.studyPreview();this.controls();
  }
  studyPreview(){
    const task=list(this.studyContext?.tasks).find(task=>task.task_ref===this.q('[data-study-task]')?.value)??list(this.studyContext?.tasks)[0];
    if(task)this.q('[data-study-prompt]').textContent=studyTaskPrompt(task);
  }
  changeStudyMode(mode){
    if(!['manual','assisted'].includes(mode)||this.attempt?.status==='RUNNING')throw Error('請先完成或停止目前任務。');
    this.studyEpoch++;this.selectedStudyMode=mode;this.attempt=null;this.studyReport=null;this.studyFrame=null;this.studyAssistance=null;
    this.recoveryToken=null;this.q('[data-study-current-token]').value='';
    for(const selector of ['[data-study-navigation]','[data-study-view]','[data-study-answer]','[data-study-report]'])this.q(selector).replaceChildren();
    this.q('[data-study-status]').textContent='尚未開始任務。';
    this.q('[data-study-mode-note]').textContent=mode==='manual'?'人工搜尋僅顯示原來源影格；提交前不顯示參考答案或輔助摘要。':
      '輔助方式可按需查看同來源的登錄影格時間；登錄資訊不確認人物或行為。';
    this.controls();
  }
  assertStudy(data,{ref=null,mode=null}={}){
    const binding=this.studyContext?.binding;
    if(!binding||Object.keys(binding).some(key=>data.binding?.[key]!==binding[key])||
      data.phase!=='PREPARATION_REHEARSAL'||data.actual_operator_acceptance!==false||
      ref&&data.study_ref!==ref||mode&&data.mode!==mode||
      !list(this.studyContext.tasks).some(task=>task.task_ref===data.task?.task_ref))
      throw Error('任務紀錄與來源、作業方式或評測契約不一致。');
    return data;
  }
  async startStudy(){
    if(this.attempt?.status==='RUNNING')throw Error('請先完成或停止目前任務。');
    const task=list(this.studyContext.tasks).find(task=>task.task_ref===this.q('[data-study-task]').value);
    const mode=this.q('[data-study-mode]').value;
    if(!task||!['manual','assisted'].includes(mode))throw Error('請選取有效的任務與作業方式。');
    this.studyEpoch++;const token=this.token('study');this.clearStudyView();
    let data;
    try{
      if(mode==='manual'){await this.pauseRunForStudy();this.check(token);}
      data=await this.request('operator_study_start',{task_ref:task.task_ref,mode},token);
    }
    catch(error){if(mode==='manual')await this.reconcileRunPause(token);throw error;}
    this.attempt=this.assertStudy(data,{mode});this.selectedStudyMode=mode;this.recoveryToken=data.recovery_token??null;
    this.q('[data-study-current-ref]').value=data.study_ref;
    this.q('[data-study-current-token]').value=this.recoveryToken??'';
    this.showStudy();await this.loadStudies(token);
  }
  clearStudyView(){
    this.studyReport=null;this.studyFrame=null;this.studyAssistance=null;
    for(const selector of ['[data-study-navigation]','[data-study-view]','[data-study-answer]','[data-study-report]'])this.q(selector)?.replaceChildren();
  }
  showStudy(){
    const data=this.attempt;if(!data)return;
    this.q('[data-study-status]').innerHTML='<p><strong>'+h(runStudyStatus(data.status))+'</strong> · '+
      h(data.mode==='manual'?'人工搜尋':'輔助調查')+'</p><p>'+h(studyTaskPrompt(data.task))+'</p>'+technical('任務與固定來源',{study_ref:data.study_ref,
      binding:data.binding,phase:data.phase,protocol_valid:data.protocol_valid,status:data.status});
    this.q('[data-study-task]').value=data.task.task_ref;this.q('[data-study-mode]').value=data.mode;
    if(data.status==='RUNNING'){this.renderStudyNavigation();this.renderStudyAnswer();}
    else{this.q('[data-study-navigation]').replaceChildren();this.q('[data-study-answer]').replaceChildren();}
    this.controls();
  }
  renderStudyNavigation(){
    const task=this.attempt.task;
    this.q('[data-study-navigation]').innerHTML='<label class="field"><span>本任務鏡頭</span><select data-study-camera>'+list(task.camera_ids).map(camera=>
      '<option value="'+h(camera)+'">'+h(camera)+'</option>').join('')+'</select></label><label class="field"><span>來源秒數（'+h(task.time_range.join('–'))+'）</span>'+
      '<input data-study-timestamp type="number" step="any" min="'+h(task.time_range[0])+'" max="'+h(task.time_range[1])+'" value="'+h(task.time_range[0])+'"></label>'+
      '<button class="btn primary" data-study-view-source>查看來源影格</button><div class="investigation-controls">'+list(task.targets).map((target,index)=>
      '<button class="btn" data-study-target="'+index+'">查看參考 '+h(target.label)+' · '+h(target.camera_id)+'</button>').join('')+'</div>';
    this.q('[data-study-view-source]').onclick=()=>this.action('study',()=>this.viewStudy());
    this.container.querySelectorAll('[data-study-target]').forEach(button=>button.onclick=()=>this.action('study',()=>{
      const target=task.targets[Number(button.dataset.studyTarget)];return this.viewStudy({frame_ref:target.frame_ref});}));
  }
  async viewStudy(selection=null){
    if(this.attempt?.status!=='RUNNING')throw Error('請先開始或恢復本次任務。');
    const task=this.attempt.task,mode=this.attempt.mode,ref=this.attempt.study_ref;
    if(!selection){
      const camera_id=this.q('[data-study-camera]').value,raw=this.q('[data-study-timestamp]').value,timestamp=Number(raw);
      if(!raw.trim()||!list(task.camera_ids).includes(camera_id)||!Number.isFinite(timestamp)||timestamp<task.time_range[0]||timestamp>task.time_range[1])
        throw Error('請選取此任務允許的鏡頭與時間。');
      selection={camera_id,timestamp};
    }else if(!list(task.targets).some(target=>target.frame_ref===selection.frame_ref))throw Error('參考影格不屬於此任務。');
    const token=this.token('study'),result=await this.request('operator_study_view',{study_ref:ref,...selection},token),frame=result.frame;
    if(this.attempt?.study_ref!==ref||!frame||result.schema_version!=='operator.study.view.v1'||
      result.study_ref!==ref||result.mode!==mode||result.phase!=='PREPARATION_REHEARSAL'||
      Object.keys(this.studyContext.binding).some(key=>result.binding?.[key]!==this.studyContext.binding[key])||
      !list(task.camera_ids).includes(frame.camera_id)||!Number.isFinite(frame.timestamp)||frame.timestamp<task.time_range[0]||frame.timestamp>task.time_range[1]||
      mode==='manual'&&result.assistance!==null&&result.assistance!==undefined)
      throw Error('來源影格或作業方式不符合本次任務；不顯示結果。');
    this.studyFrame=frame;this.studyAssistance=mode==='assisted'?result.assistance:null;
    this.q('[data-study-view]').innerHTML='<figure><img style="max-width:360px;width:100%" src="'+h(this.mediaURL(frame.media_ref,ref))+
      '" alt="'+h(frame.camera_id)+' 原來源影格"><figcaption>'+h(frame.camera_id)+' · 原來源 '+number(frame.timestamp)+' 秒</figcaption></figure>'+
      '<p>此影格開啟與鏡頭查看由後端計入本次紀錄。</p><button class="btn" data-study-correction>記錄一次答案修正</button>'+
      (mode==='assisted'&&this.studyAssistance?'<button class="btn" data-study-evidence>查看本影格的登錄時間證據</button><div data-study-assistance></div>':'');
    this.q('[data-study-correction]').onclick=()=>this.action('study',()=>this.recordStudy('correction'));
    if(mode==='assisted'&&this.studyAssistance)this.q('[data-study-evidence]').onclick=()=>this.action('study',()=>this.recordStudy('evidence_open'));
    this.controls();
  }
  async recordStudy(action){
    if(this.attempt?.status!=='RUNNING'||!this.studyFrame)throw Error('請先查看此任務的來源影格。');
    if(!['correction','evidence_open'].includes(action)||action==='evidence_open'&&
      (this.attempt.mode!=='assisted'||!this.studyAssistance))throw Error('此方式沒有可查看的輔助證據。');
    const ref=this.attempt.study_ref,frame=this.studyFrame,assistance=this.studyAssistance,token=this.token('study');
    const payload=action==='evidence_open'?{study_ref:ref,action,evidence_ref:assistance.evidence_ref}:
      {study_ref:ref,action,camera_id:frame.camera_id,frame_ref:frame.frame_ref};
    const result=await this.request('operator_study_record',payload,token);
    this.attempt=this.assertStudy(result,{ref,mode:this.attempt.mode});
    if(action==='evidence_open')this.q('[data-study-assistance]').innerHTML='<p>此鏡頭登錄的來源影格秒數：'+
      h(list(assistance.registered_timestamps).join('、'))+'。登錄時間不確認人物或行為。</p>';
    else this.q('[data-study-status]').innerHTML+='<p>已記錄一次答案修正。</p>';
  }
  renderStudyAnswer(){
    const task=this.attempt.task;
    const input=task.answer_type==='timestamp'?'<label class="field"><span>回答秒數</span><input data-study-answer-value type="number" step="any" min="'+h(task.time_range[0])+'" max="'+h(task.time_range[1])+'"></label>':
      task.answer_type==='presence'?'<label class="field"><span>是否存在指定來源影格</span><select data-study-answer-value><option value="">請選擇</option><option value="PRESENT">存在</option><option value="MISSING">缺失</option></select></label>':
      task.answer_type==='count'?'<label class="field"><span>回答數量</span><input data-study-answer-value type="number" min="0" max="64" step="1"></label>':
      '<label class="field"><span>參考順序（由早到晚）</span><select data-study-answer-value><option value="">請選擇</option>'+[
        list(task.targets).map(target=>target.label),list(task.targets).map(target=>target.label).reverse()].map(labels=>
        '<option value="'+h(labels.join(','))+'">'+h(labels.join(' → '))+'</option>').join('')+'</select></label>';
    this.q('[data-study-answer]').innerHTML='<h3>本次答案</h3>'+input+
      '<label class="seed-item"><input data-study-unknown type="checkbox"><span>證據不足／未定（UNKNOWN）</span></label>'+
      '<button class="btn primary" data-study-submit>提交本次答案並保存紀錄</button><p>提交後才顯示答案正確性；未定保留於完成分母中。</p>';
    this.q('[data-study-submit]').onclick=()=>this.action('study',()=>this.submitStudy());
  }
  async submitStudy(){
    if(this.attempt?.status!=='RUNNING')throw Error('請先開始或恢復本次任務。');
    const task=this.attempt.task,unknown=this.q('[data-study-unknown]').checked,raw=this.q('[data-study-answer-value]').value;
    let answer;
    if(unknown)answer={unknown:true};else if(!raw.trim())throw Error('請填寫答案或選擇證據不足／未定。');
    else answer=task.answer_type==='timestamp'?{timestamp:Number(raw)}:task.answer_type==='presence'?{presence:raw}:
      task.answer_type==='count'?{count:Number(raw)}:{order:raw.split(',').map(value=>value.trim())};
    validateStudyAnswer(task,answer);
    const ref=this.attempt.study_ref,mode=this.attempt.mode,token=this.token('study');
    const result=await this.request('operator_study_submit',{study_ref:ref,answer},token);
    this.attempt=this.assertStudy(result,{ref,mode});this.manualStudyPending=false;this.showStudy();
    await this.loadStudyReport(ref,token);await this.loadStudies(token);await this.releaseRunAfterStudy();
  }
  async stopStudy(){
    if(this.attempt?.status!=='RUNNING')throw Error('目前沒有可停止的任務。');
    const ref=this.attempt.study_ref,mode=this.attempt.mode;this.studyEpoch++;const token=this.token('study');
    const data=await this.request('operator_study_stop',{study_ref:ref},token);
    this.attempt=this.assertStudy(data,{ref,mode});this.manualStudyPending=false;this.showStudy();await this.loadStudies(token);await this.releaseRunAfterStudy();
  }
  async loadStudies(token=this.token('study')){
    const result=await this.request('operator_study_list',{},token);this.studies=list(result.items);
    if(this.studies.some(study=>study.mode==='manual'&&['RUNNING','RESUME_REQUIRED'].includes(study.status)))await this.pauseRunForStudy({drainImages:false});
    this.q('[data-study-history]').innerHTML='<option value="">選擇保存的任務紀錄</option>'+this.studies.map((study,index)=>
      '<option value="'+h(study.study_ref)+'">紀錄 '+(index+1)+' · '+h(study.mode==='manual'?'人工搜尋':'輔助調查')+' · '+h(runStudyStatus(study.status))+'</option>').join('');
    if(this.attempt)this.q('[data-study-history]').value=this.attempt.study_ref;
    this.controls();
  }
  async stopSavedStudy(){
    if(this.attempt?.status==='RUNNING')throw Error('請先提交或停止目前任務。');
    const ref=this.q('[data-study-history]').value,entry=list(this.studies).find(study=>study.study_ref===ref);
    if(!entry||!['RUNNING','RESUME_REQUIRED'].includes(entry.status))throw Error('請選取未完成的任務紀錄。');
    this.studyEpoch++;const token=this.token('study'),data=await this.request('operator_study_stop',{study_ref:ref},token);
    this.attempt=this.assertStudy(data,{ref});this.manualStudyPending=false;this.showStudy();await this.loadStudies(token);await this.releaseRunAfterStudy();
  }
  async openStudyReport(){
    if(this.attempt?.status==='RUNNING')throw Error('請先提交或停止本次任務。');
    const ref=this.q('[data-study-history]').value;if(!ref)throw Error('請選取保存的任務紀錄。');
    this.studyEpoch++;const token=this.token('study');this.clearStudyView();await this.loadStudyReport(ref,token);
  }
  async loadStudyReport(ref,token=this.token('study')){
    const data=await this.request('operator_study_report',{study_ref:ref},token);
    const report=this.assertStudy(data,{ref});
    if(report.status==='RUNNING')throw Error('請先提交本次答案；執行中不顯示評分或輔助摘要。');
    this.studyReport=report;this.q('[data-study-report]').innerHTML=studyReportHTML(report);
    this.renderIssuedStudyFrames(report);
  }
  async resumeStudy(){
    if(this.attempt?.status==='RUNNING')throw Error('請先提交或停止目前任務。');
    const ref=this.q('[data-study-recovery-ref]').value.trim()||this.q('[data-study-history]').value,recovery_token=this.q('[data-study-recovery-input]').value.trim();
    if(!ref||!recovery_token)throw Error('請選取未完成紀錄並輸入其恢復憑證。');
    this.studyEpoch++;const token=this.token('study');this.clearStudyView();
    let data;
    try{await this.pauseRunForStudy();this.check(token);data=await this.request('operator_study_resume',{study_ref:ref,recovery_token},token);}
    catch(error){await this.reconcileRunPause(token);throw error;}
    this.attempt=this.assertStudy(data,{ref});this.selectedStudyMode=data.mode;this.recoveryToken=recovery_token;
    this.q('[data-study-current-ref]').value=data.study_ref;
    this.q('[data-study-current-token]').value=recovery_token;this.q('[data-study-recovery-input]').value='';this.showStudy();
    if(data.status!=='RUNNING'){
      this.studyReport=data;this.q('[data-study-report]').innerHTML=studyReportHTML(data);
      this.renderIssuedStudyFrames(data);await this.loadStudies(token);await this.releaseRunAfterStudy();
    }else if(data.mode==='assisted')await this.releaseRunAfterStudy();
  }
  renderIssuedStudyFrames(report){
    this.q('[data-study-view]').innerHTML=list(report.issued_frames).map(frame=>'<figure><img style="max-width:260px;width:100%" src="'+
      h(this.mediaURL(frame.media_ref,report.study_ref))+'" alt="'+h(frame.camera_id)+' 已查閱的原來源影格"><figcaption>'+h(frame.camera_id)+
      ' · 原來源 '+number(frame.timestamp)+' 秒 · 已查閱紀錄，唯讀</figcaption></figure>').join('');
  }
  dispose(){this.closed=true;this.serial++;this.runEpoch++;this.studyEpoch++;clearTimeout(this.pollTimer);this.pollTimer=null;}
}

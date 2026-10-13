const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=(value,digits=0)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits):'N/A';
const modeName=mode=>({'photos_only':'僅照片','photos_plus_observations':'照片＋影像量測'})[mode]??mode;
const variantName=variant=>({baseline:'原基線',end_to_end:'v2 完整組合',pixel_only:'追蹤更新',appearance_only:'外觀特徵',prior_only:'時空先驗',features_full:'外觀＋時空',behavior_only:'行為更新',motion_diagnostic:'運動診斷'})[variant]??variant;
const kindName=kind=>({ENTER:'進門',EXIT:'出門',CORNER:'轉角',DWELL:'停留',POSSIBLE_WANDERING:'可能遊蕩'})[kind]??kind;
const list=value=>Array.isArray(value)?value:[];
const rate=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=1;
const rank=row=>row.association?.rank_recall_at_k?.['1']??row.association?.rank_recall_at_k?.RecallAt1??null;

function metricRows(rows,comparisons){
  return rows.map(row=>{
    const p=row.population??{},pixels=row.pixels??{},a=row.association??{};
    const comparison=comparisons.find(item=>item.mode===row.mode&&item.variant===row.variant);
    const comparable=row.variant==='baseline'||comparison?.population_comparable===true;
    return `<tr><th scope="row">${escape(variantName(row.variant))}</th><td>${number(p.measurement_count)}／${number(p.track_count)}／${number(p.segment_count)}</td><td>${number(p.eligible_queries)}／${number(p.eligible_pair_positives)}／${number(p.pair_count)}</td><td>${number(pixels.id_switches)}／${number(pixels.fragmented_tracks)}</td><td>${number(a.pair_precision,3)}／${number(a.pair_recall,3)}</td><td>${number(rank(row),3)}</td><td>${number(pixels.contact_recall,3)}／${number(pixels.ground_rms_m,3)}</td><td>${comparable?'同基線母體':'母體改變，分開解讀'}</td></tr>`;
  }).join('');
}

function fixedPoolChart(rows,comparisons){
  const eligible=rows.filter(row=>row.variant==='baseline'||comparisons.some(item=>item.mode===row.mode&&item.variant===row.variant&&item.population_comparable===true)).filter(row=>rate(rank(row)));
  if(eligible.length<2)return '<p class="status-text">目前沒有兩組已認證的相同母體數值可作並列圖。</p>';
  return `<figure class="accuracy-chart"><figcaption>相同已認證母體的 Recall@1</figcaption>${eligible.map(row=>`<div class="accuracy-bar-row"><span>${escape(variantName(row.variant))}</span><meter min="0" max="1" value="${rank(row)}" aria-label="${escape(variantName(row.variant))} Recall@1"></meter><strong>${number(rank(row),3)}</strong></div>`).join('')}</figure>`;
}

function regressionName(metric){
  const behavior=/^(ENTER|EXIT|CORNER|DWELL|POSSIBLE_WANDERING)_(false_positive|recall)$/.exec(metric);
  if(behavior)return kindName(behavior[1])+(behavior[2]==='false_positive'?'誤報':'召回率');
  const rank=/^rank_at_(\d+)_vs_(.+)$/.exec(metric);
  if(rank)return 'Recall@'+rank[1]+' 相較'+({'without_space':'移除空間先驗','without_time':'移除時間先驗','without_appearance':'移除外觀特徵','only_appearance':'僅外觀特徵'})[rank[2]];
  const appearance=/^appearance_at_(\d+)_vs_handcrafted$/.exec(metric);
  if(appearance)return '外觀 Recall@'+appearance[1]+' 相較原手工特徵';
  return metric;
}

function regressionsHTML(evaluation){
  const names={fragmented_tracks:'追蹤碎片',mixed_tracks:'混合人物片段',records_read:'讀取紀錄數',index_entries_touched:'索引觸及數',false_positive:'行為誤報',rank_recall_below_best_ablation:'排名低於最佳消融'};
  const rows=list(evaluation.regressions).filter(row=>row.variant==='end_to_end');
  if(!rows.length)return '';
  return `<details class="technical" open><summary>v2 完整組合的退步與成本增加</summary><ul>${rows.map(row=>`<li>${escape(modeName(row.mode))} · ${escape(names[row.metric]??regressionName(row.metric))}：${number(row.baseline,Number.isInteger(row.baseline)&&Number.isInteger(row.value)?0:3)} → ${number(row.value,Number.isInteger(row.baseline)&&Number.isInteger(row.value)?0:3)}${row.population_comparable?'':'；母體改變，分開解讀'}</li>`).join('')}</ul></details>`;
}

function behaviorTable(rows){
  const selected=rows.filter(row=>['baseline','end_to_end'].includes(row.variant));
  return `<details class="technical"><summary>基線與 v2 完整組合的行為誤報、漏報與未定</summary><div class="accuracy-table-scroll"><table class="accuracy-table"><thead><tr><th>版本</th><th>事件</th><th>參考事件分母</th><th>TP／FP／FN</th><th>未定</th><th>Precision／Recall</th></tr></thead><tbody>${selected.flatMap(row=>Object.entries(row.behavior?.per_kind??{}).map(([kind,m])=>`<tr><th scope="row">${escape(variantName(row.variant))}</th><td>${escape(kindName(kind))}</td><td>${number(m.reference_count)}</td><td>${number(m.true_positive)}／${number(m.false_positive)}／${number(m.false_negative)}</td><td>${number(m.unresolved)}</td><td>${number(m.precision,3)}／${number(m.recall,3)}</td></tr>`)).join('')}</tbody></table></div><p>v2 未定事件：${number(selected.find(row=>row.variant==='end_to_end')?.behavior?.unknown_count)}；未定與漏報均保留。</p></details>`;
}

/** Render only the independently certified aggregate DTO, never raw evaluation data. */
export function accuracyEvaluationHTML(evaluation){
  if(evaluation?.schema_version!=='workbench.accuracy-evaluation.v1'||evaluation.status!=='CERTIFIED_LOCAL_SYNTHETIC')
    return '<p class="notice warning">此場景沒有可顯示的已認證精度摘要。</p>';
  const variants=list(evaluation.variants),comparisons=list(evaluation.comparisons);
  const binding=evaluation.binding??{};
  return `<div class="accuracy-evaluation"><p class="notice">已認證本機合成研究摘要 · 完整正式驗收尚未完成 · 測試資料非封存盲測</p><p>實驗：${escape(binding.experiment_id)} · 來源 run：${escape(binding.source_run_id)}</p><p class="status-text">每列保留自己的量測、追蹤、查詢與正例分母。母體改變的版本分開解讀；圖表只列母體相同的結果。</p>${regressionsHTML(evaluation)}${list(evaluation.modes).map(mode=>{
    const rows=variants.filter(row=>row.mode===mode);
    return `<section class="accuracy-mode"><h3>${escape(modeName(mode))}</h3><div class="accuracy-table-scroll"><table class="accuracy-table"><thead><tr><th>版本</th><th>量測／tracks／片段</th><th>查詢／正例／pairs</th><th>ID switch／碎片</th><th>關聯 P／R</th><th>Recall@1</th><th>接地 recall／RMS m</th><th>比較範圍</th></tr></thead><tbody>${metricRows(rows,comparisons)}</tbody></table></div>${fixedPoolChart(rows,comparisons)}${behaviorTable(rows)}</section>`;
  }).join('')}<details class="technical"><summary>母體與來源認證摘要</summary><pre>${escape(JSON.stringify({binding,populations:variants.map(row=>({mode:row.mode,variant:row.variant,...row.population,freeze_sha256:row.freeze_sha256})),comparisons,regressions:list(evaluation.regressions),limitations:list(evaluation.limitations)},null,2))}</pre></details></div>`;
}

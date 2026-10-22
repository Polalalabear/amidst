// Evidence uses the shared palette; execution states use ink and line/symbols.
export const Q_STATES=Object.freeze({
  PLAYING:Object.freeze({label:'觀測延續',symbol:'—',color:'--ink'}),
  TEMP_LOST:Object.freeze({label:'暫失',symbol:'┄',color:'--ink'}),
  SEARCHING:Object.freeze({label:'搜尋中',symbol:'⋯',color:'--ink'}),
  SWITCHING:Object.freeze({label:'切換',symbol:'│',color:'--ink'}),
  RETURNED_TO_ORIGIN:Object.freeze({label:'回到原鏡頭',symbol:'↩',color:'--ink'}),
  ENDED:Object.freeze({label:'結束',symbol:'■',color:'--ink'}),
});
export const Q_DECIDERS=Object.freeze({AGENT:'AG',RULE_ONLY:'ⓡ 規則',RULE_FALLBACK:'ⓡ 規則兜底',USER:'使用者'});
export const Q_LEGEND=Object.freeze([
  Object.freeze({code:'OBS',label:'觀測',color:'--obs',line:'solid'}),
  Object.freeze({code:'INF',label:'推論',color:'--int',line:'dashed'}),
  Object.freeze({code:'MISS',label:'MISSING',color:'--miss',line:'hatch'}),
  Object.freeze({code:'UNK',label:'UNKNOWN',color:'--unk',line:'dotted'}),
]);
export function sourcePresentation(origin,kind='UNKNOWN') {
  const synthetic=origin==='SYNTHETIC_FIXTURE'||String(kind).includes('SYNTHETIC');
  const pilot=String(kind).includes('PILOT');
  if(synthetic)return {label:origin==='SYNTHETIC_FIXTURE'?origin:origin+' · SYNTHETIC',note:'程式試用來源 · 排除正式評估',visible:true};
  if(pilot)return {label:origin+' · PILOT',note:'試用來源 · 排除正式評估',visible:true};
  return {label:origin,note:origin==='RECORDED'?'錄製回應 · 依原始來源與 hash 重播':origin==='LIVE'?'註冊來源 · 身分未確認':'資料尚未準備好',visible:origin!=='LIVE'};
}

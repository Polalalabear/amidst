import {formatSource} from './q-time.mjs';import {placeBox} from './q2-session-model.mjs';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export function evidenceModel(evidence){
  if(!evidence)return {message:'NOT_EVALUATED · 尚未取得證據',unknown:true};
  const messages={NO_PERSON_DETECTED:'窗內已推論的格都沒有人物框（不代表目標不在那裡）',NOT_EVALUATED:'UNKNOWN · 未評估',PARTIAL_EVIDENCE:'UNKNOWN · 證據不完整',MATCH_STRONG:'INF · 條件相符的候選觀測，身分未確認',MATCH_WEAK:'INF · 弱條件相符，身分未確認',PERSON_NO_COLOR_MATCH:'INF · 有人物框，顏色條件不符',PERSON_COLOR_UNKNOWN:'UNKNOWN · 人物顏色無法判定'};
  return {message:messages[evidence.target_presence]??'UNKNOWN · 無法判定',unknown:['NOT_EVALUATED','PARTIAL_EVIDENCE','PERSON_COLOR_UNKNOWN'].includes(evidence.target_presence),raw:evidence};
}
export function renderEvidence(root,evidence,{api,run,alive=()=>true}={}){
  root.replaceChildren();const m=evidenceModel(evidence);root.className=`q4-evidence${m.unknown?' q4-unknown':''}`;root.append(el('p',m.message));if(!evidence)return;
  const e=evidence;root.append(el('p',`${e.target_presence} · 窗 [${formatSource(e.window_us[0])}, ${formatSource(e.window_us[1])})`));root.append(el('p',`已推論 ${e.frames.evaluated} · 未取樣 ${e.frames.not_sampled} · 未推論 ${e.frames.not_inferred} · MISSING ${e.frames.missing}`));
  root.append(el('p',`相符觀測 ${e.matching_observation_count} · 第一次相符 ${e.first_match_us===null?'UNKNOWN':formatSource(e.first_match_us)} · ${e.evidence_sha256}`));
  for(const observation of e.best_observations){const line=el('div',undefined,'q4-observation');line.append(el('p',`OBS ${formatSource(observation.timestamp_us)} · score ${observation.score} · ${observation.color_verdict===null?'無查色條件':observation.color_verdict} · ${observation.observation_id}`));const button=el('button','檢視證據影格');button.onclick=async()=>{
      const target=el('div','取得中…','q4-frame');line.append(target);button.disabled=true;const result=await api.frames(run,observation.timestamp_us,[e.camera_id]);if(!alive())return;const tile=result.data?.tiles?.[0];if(tile?.status!=='READY'||!tile.media_url){target.textContent=`${tile?.status??'MISSING'} · 證據 RGB 不可用`;return;}
      const img=el('img');img.alt=`${e.camera_id} ${formatSource(observation.timestamp_us)} 觀測`;img.src=tile.media_url;target.replaceChildren(img);img.onload=()=>{if(!alive())return;const b=placeBox(observation.bbox_xyxy_px,img.naturalWidth,img.naturalHeight,target.clientWidth,target.clientHeight);if(b){const box=el('span','OBS','q4-box');for(const [key,value] of Object.entries({left:b.left,top:b.top,width:b.right-b.left,height:b.bottom-b.top}))box.style[key]=value+'%';target.append(box);}};img.onerror=()=>{target.textContent='MISSING · RGB 載入失敗';};
    };line.append(button);root.append(line);}
}

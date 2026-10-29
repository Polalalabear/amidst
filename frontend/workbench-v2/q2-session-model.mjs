import {inside} from './q-time.mjs';
export function segmentAt(response,tUs){return response?.timeline?.find(x=>inside(tUs,x.range_us))??null;}
export function decisionAt(decisions,tUs,inspectionId=null){
  const selected=inspectionId&&decisions.find(x=>x.decision_id===inspectionId&&x.source_time_us===tUs);if(selected)return selected;
  return decisions.filter(x=>x.source_time_us<=tUs).sort((a,b)=>a.source_time_us-b.source_time_us||a.step_index-b.step_index).at(-1)??null;
}
export function sessionModel(response,tUs,{decisions=[],snapshots={},evidence={},review=false,inspectionId=null,evidenceToolHashes={}}={}) {
  const segment=segmentAt(response,tUs);
  const blank={state:'UNKNOWN',camera:null,timestamp_us:tUs,position:null,drawBoxes:false,observation_ids:[],candidates:[],decision:null,message:'UNKNOWN · 沒有資料'};
  if(!segment)return blank;
  const decision=decisionAt(decisions,tUs,inspectionId);
  if(decision?.decided_by==='RULE_FALLBACK'&&!decision.fallback_reason)throw new Error('FALLBACK_REASON_REQUIRED');
  if(segment.kind==='GAP'&&segment.position!==null)throw new Error('GAP_POSITION_FORBIDDEN');
  let state=segment.kind==='ON_CAMERA'?'PLAYING':decision&&['TEMP_LOST','SEARCHING','RETURNED_TO_ORIGIN'].includes(decision.state_after)?decision.state_after:null;
  // Without a journal the distinct GAP substate is unknown, never guessed from an array of names.
  if(!state)state='GAP';
  const snapshot=review&&decision?.candidate_snapshot_sha256?snapshots[decision.candidate_snapshot_sha256]:null;
  const prior=review&&decision?decisions.filter(x=>x.searching_index===decision.searching_index&&x.step_index<=decision.step_index&&x.source_time_us<=tUs):[];
  const considered=new Map(prior.flatMap(x=>x.candidates_considered).map(x=>[x.candidate_ref,x]));
  const knownHashes=new Set([...considered.values()].map(x=>x.evidence_sha256));
  for(const d of prior)for(const call of d.tool_calls??[])if(call.tool==='get_candidate_evidence')knownHashes.add(evidenceToolHashes[call.response_sha256]??call.response_sha256);
  const candidates=review&&snapshot&&['SEARCHING','RETURNED_TO_ORIGIN'].includes(state)?snapshot.candidates.map(c=>{
    const result=considered.get(c.candidate_ref),proof=Object.values(evidence).find(e=>knownHashes.has(e.evidence_sha256)&&e.candidate_ref===c.candidate_ref);
    return {...c,result:result??null,evidence:proof??null,evaluation:result?'RECORDED':proof?'EVIDENCE_FETCHED':'NOT_EVALUATED'};
  }):[];
  const labels={PLAYING:'畫面中的觀測',TEMP_LOST:'暫失 · 觀測缺失',SEARCHING:'暫失 · 搜尋中',RETURNED_TO_ORIGIN:'回到原鏡頭',GAP:'畫面暫無相符觀測'};
  return {state,camera:segment.kind==='ON_CAMERA'?segment.camera_id:segment.camera_shown,timestamp_us:tUs,position:null,
    drawBoxes:segment.kind==='ON_CAMERA',observation_ids:segment.kind==='ON_CAMERA'?segment.observation_ids:[],candidates,
    segment,decision:review?decision:null,snapshot:review?snapshot:null,message:review?labels[state]:segment.kind==='ON_CAMERA'?'畫面中的觀測':'畫面暫無相符觀測'};
}
export function camerasFor(model,run,{mode='single',size=4,page=0}={}) {
  if(!model.camera)return [];if(mode==='single')return [model.camera];
  const ids=run?.camera_ids??[];return ids.slice(Math.max(0,page)*size,(Math.max(0,page)+1)*size);
}
export function observedAt(model,observations,cameraId,frameUs){
  if(!model.drawBoxes||cameraId!==model.camera)return [];
  const allowed=new Set(model.observation_ids);return observations.filter(x=>allowed.has(x.observation_id)&&x.camera_id===cameraId&&x.timestamp_us===frameUs);
}
export function placeBox(raw,width,height,cw,ch){
  if(!Array.isArray(raw)||raw.length!==4||!raw.every(Number.isFinite)||![width,height,cw,ch].every(x=>x>0))return null;
  const [l,t,r,b]=raw,scale=Math.min(cw/width,ch/height),px=(cw-width*scale)/2,py=(ch-height*scale)/2;
  const box={left:(px+Math.max(0,l)*scale)/cw*100,top:(py+Math.max(0,t)*scale)/ch*100,right:(px+Math.min(width,r)*scale)/cw*100,bottom:(py+Math.min(height,b)*scale)/ch*100};
  return box.right>box.left&&box.bottom>box.top?box:null;
}

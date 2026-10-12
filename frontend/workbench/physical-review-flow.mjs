import {validatePhysicalReviewResponse,validatePhysicalReviewInput} from './physical-review.mjs';

export function invalidatePhysicalReview(target) {
  target.physicalReviewEpoch=(target.physicalReviewEpoch??0)+1;
  target.physicalReviewResult=null;target.physicalReviewPending=false;
  target.physicalReviewError=null;target.physicalReviewSelected=null;
  target.physicalReviewSelection=null;
}
export function physicalReviewRequestIsCurrent(target,ticket) {
  return target.role==='research'&&target.sceneEpoch===ticket.sceneEpoch&&target.sceneId===ticket.sceneId&&
    target.session?.session_ref===ticket.sessionRef&&target.physicalReviewEpoch===ticket.reviewEpoch;
}
function ticket(target) {
  return {sceneEpoch:target.sceneEpoch,sceneId:target.sceneId,
    sessionRef:target.session?.session_ref,reviewEpoch:target.physicalReviewEpoch};
}
export async function runPhysicalReviewLoad(target,selection,send) {
  target.physicalReviewEpoch=(target.physicalReviewEpoch??0)+1;
  target.physicalReviewPending=true;target.physicalReviewError=null;
  target.physicalReviewSelection={camera_ids:[...selection.camera_ids],start:selection.start,end:selection.end};
  const current=ticket(target),snapshot=target.snapshot;
  try {
    const result=await send({scene_id:current.sceneId,camera_ids:[...selection.camera_ids],start:selection.start,end:selection.end});
    if(!physicalReviewRequestIsCurrent(target,current))return false;
    validatePhysicalReviewResponse(result,snapshot);
    if(JSON.stringify([...result.selection.camera_ids].sort())!==JSON.stringify([...selection.camera_ids].sort())||
      result.selection.time_range[0]!==selection.start||result.selection.time_range[1]!==selection.end||
      !Number.isInteger(result.review_state?.revision)||result.review_state.revision<0||result.post_confirmation_rerun_performed!==false)
      throw Error('人工核對範圍或修訂版本不相符。');
    const selected=target.physicalReviewSelected;
    target.physicalReviewResult=result;
    target.physicalReviewSelected=result.items.some(item=>item.item_ref===selected)?selected:result.items[0]?.item_ref??null;
    target.physicalReviewPending=false;
    return true;
  } catch(error) {
    if(!physicalReviewRequestIsCurrent(target,current))return false;
    target.physicalReviewResult=null;target.physicalReviewPending=false;
    target.physicalReviewError=error.message;throw error;
  }
}
export async function runPhysicalReviewSave(target,payload,send) {
  validatePhysicalReviewInput(payload);
  const current=ticket(target),result=target.physicalReviewResult;
  if(!result||payload.review_sha256!==result.review_sha256||payload.expected_revision!==result.review_state?.revision||
    !result.items.some(item=>item.item_ref===payload.item_ref))throw Error('人工核對來源或修訂已更新，請重新載入。');
  const saved=await send({...payload,scene_id:current.sceneId});
  if(!physicalReviewRequestIsCurrent(target,current)||target.physicalReviewResult!==result)return false;
  if(saved.authority_changed!==false||saved.rerun_authorized!==false||saved.post_confirmation_rerun_performed!==false||
    saved.review_state?.review_sha256!==result.review_sha256||saved.review_state?.revision!==payload.expected_revision+1||
    saved.record?.decision?.item_ref!==payload.item_ref||saved.record?.formal_approval!==false)
    throw Error('本機人工修訂回應不符合來源與權限契約。');
  target.physicalReviewResult={...result,review_state:saved.review_state};
  target.physicalReviewError=null;
  return true;
}

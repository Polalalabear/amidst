const list=value=>Array.isArray(value)?value:[];
const unique=items=>[...new Set(items.filter(value=>typeof value==='string'&&value))];
const interval=value=>{
  const range=Array.isArray(value)?value:[value?.start,value?.end];
  if(range.length!==2||!range.every(Number.isFinite)||range[0]<0||range[1]<range[0])
    throw Error('INVALID_INVESTIGATION_RANGE');
  return [...range];
};
const windowInSource=(value,source)=>{
  const range=interval(value),bounds=interval(source);
  if(range[0]<bounds[0]||range[1]>bounds[1]||range[1]-range[0]>120)
    throw Error('INVALID_INVESTIGATION_RANGE');
  return range;
};
const timestampInSource=(value,bounds,fallback)=>{
  const timestamp=value??fallback;
  if(!Number.isFinite(timestamp)||timestamp<bounds[0]||timestamp>bounds[1])
    throw Error('INVALID_INVESTIGATION_TIMESTAMP');
  return timestamp;
};
const cameraSelection=(ids,available,fallback)=>{
  const requested=unique(ids);
  if(requested.some(id=>!available.includes(id)))throw Error('INVESTIGATION_CAMERA_DENIED');
  const selected=requested.length?requested:[fallback];
  if(!selected[0]||selected.length>4)throw Error('INVESTIGATION_CAMERA_DENIED');
  return selected;
};
const assertScene=(scope,sceneId,runId)=>{
  if(scope.scene_id!==undefined&&scope.scene_id!==sceneId||
    scope.run_id!==undefined&&scope.run_id!==runId)throw Error('INVESTIGATION_SCOPE_MISMATCH');
};

/** Copy the shared workspace selection without carrying opaque evidence references. */
export function workspaceInvestigationScope(snapshot,selection={}){
  const available=list(snapshot.cameras).map(camera=>camera.camera_id);
  const bounds=interval(snapshot.time_range);
  const timeRange=windowInSource(selection.time_range??[
    selection.start??bounds[0],selection.end??Math.min(bounds[1],bounds[0]+10)],bounds);
  const cameraIds=cameraSelection([selection.camera_id??selection.cameraId,
    ...list(selection.camera_ids??selection.cameraIds)],available,available[0]);
  assertScene(selection,snapshot.scene_id,snapshot.run_id);
  return {scene_id:snapshot.scene_id,run_id:snapshot.run_id,camera_id:cameraIds[0],
    camera_ids:cameraIds,time_range:timeRange,
    timestamp:timestampInSource(selection.timestamp,bounds,timeRange[0]),
    ...(selection.observation_mode?{observation_mode:selection.observation_mode}:{})};
}

/** Resolve camera references only after the adapter supplies the actual frozen context. */
export function normalizeInvestigationScope(context,selection={}){
  const sceneId=context.scene_id,runId=context.source.run_id;
  assertScene(selection,sceneId,runId);
  if(selection.observation_mode&&selection.observation_mode!==context.observation_mode||
    selection.run_ref&&selection.run_ref!==context.product_context.run_ref||
    selection.freeze_ref&&selection.freeze_ref!==context.product_context.product_freeze_ref)
    throw Error('INVESTIGATION_SCOPE_MISMATCH');
  const bounds=interval(context.source.time_range);
  const timeRange=windowInSource(selection.time_range??[bounds[0],Math.min(bounds[1],bounds[0]+10)],bounds);
  const available=list(context.cameras).map(camera=>camera.camera_id);
  const cameraIds=cameraSelection([selection.camera_id,...list(selection.camera_ids)],available,available[0]);
  const camera=context.cameras.find(item=>item.camera_id===cameraIds[0]);
  return {scene_id:sceneId,run_id:runId,run_ref:context.product_context.run_ref,
    freeze_ref:context.product_context.product_freeze_ref,observation_mode:context.observation_mode,
    camera_id:camera.camera_id,camera_ids:cameraIds,camera_ref:camera.camera_ref,
    time_range:timeRange,timestamp:timestampInSource(selection.timestamp,bounds,timeRange[0])};
}

/** Restore a saved plan exactly, or refuse it before any UI or query uses its scope. */
export function savedInvestigationScope(context,plan,previous={}){
  const binding=plan.binding;
  if(!binding||binding.session_ref!==context.product_context.session_ref||
    binding.freeze_ref!==context.product_context.product_freeze_ref||
    binding.observation_mode!==context.observation_mode)throw Error('PRODUCT_BINDING_DENIED');
  const camera=context.cameras.find(item=>item.camera_ref===plan.camera_ref);
  if(!camera)throw Error('REFERENCE_DENIED');
  return normalizeInvestigationScope(context,{...previous,camera_id:camera.camera_id,
    time_range:windowInSource(plan.time_range,context.source.time_range),timestamp:plan.time_range[0]});
}

/** Convert a returned panel scope back to the shared workspace's field names. */
export function investigationWorkspaceScope(snapshot,scope){
  const selection=workspaceInvestigationScope(snapshot,scope);
  return {cameraId:selection.camera_id,cameraIds:selection.camera_ids,
    start:selection.time_range[0],end:selection.time_range[1],timestamp:selection.timestamp};
}

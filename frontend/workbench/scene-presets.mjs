// K3: scene presets, contact_quality flags and per-scene layer availability. Pure helpers shared by app, 3D scene and 2D overlays.
// contact_quality is a QUALITY_FLAG_ONLY_POSITION_UNCHANGED field: it changes only how a point is drawn and labelled, never where.
export const CONTACT_FLAG_TAG='接地點不可靠';
export const CONTACT_UNEVALUATED_TAG='接地未評估';
const list=value=>Array.isArray(value)?value:[];
// Same rule as app.mjs normalizeRange; kept local so the 3D scene can import this module without the app.
function normalizeRange(value) {
  const start=Number(Array.isArray(value)?value[0]:value?.start??0),end=Number(Array.isArray(value)?value[1]:value?.end??start);
  return Number.isFinite(start)&&Number.isFinite(end)&&end>=start?[start,end]:[0,0];
}
const text=value=>typeof value==='string'&&value?value:null;

// FLAGGED: hollow/dashed marker plus the short tag and reasons. PASS: drawn normally. NOT_EVALUATED: neutral tag.
// A sample without the field (or an unknown status) is drawn exactly as before.
export function contactQualityStyle(quality) {
  const status=text(quality?.status),reasons=list(quality?.reasons).map(text).filter(Boolean);
  if(status==='FLAGGED')return {status,marker:'flagged',hollow:true,dashed:true,tag:CONTACT_FLAG_TAG,reasons,
    label:`${CONTACT_FLAG_TAG}${reasons.length?'（'+reasons.join('、')+'）':''}`};
  if(status==='NOT_EVALUATED')return {status,marker:'neutral',hollow:false,dashed:false,tag:CONTACT_UNEVALUATED_TAG,reasons,
    label:`${CONTACT_UNEVALUATED_TAG}${reasons.length?'（'+reasons.join('、')+'）':''}`};
  return {status:status==='PASS'?'PASS':null,marker:'normal',hollow:false,dashed:false,tag:null,reasons:[],label:''};
}
// Adds a style next to the sample; every other field (world_position, bbox, contact pixel, timestamp) is the same value.
export const styleContactSample=sample=>({...sample,contact_style:contactQualityStyle(sample?.contact_quality)});

// Inspector lines for the samples shown at one tick: only FLAGGED and NOT_EVALUATED produce a line.
export function contactQualityReadout(samples,{cameraLabel=id=>id??'鏡頭未知'}={}) {
  const seen=new Set();
  return list(samples).flatMap(sample=>{
    const style=contactQualityStyle(sample?.contact_quality);if(!style.tag)return [];
    const line=`${style.label} · ${cameraLabel(sample.camera_id??null)} · ${Number.isFinite(sample.timestamp)?sample.timestamp.toFixed(1)+' s':'時間未知'}`;
    if(seen.has(line))return [];seen.add(line);return [line];
  });
}

// Layers the backend may mark UNAVAILABLE per scene (snapshot.layer_availability.<layer>.status).
export const GATED_LAYERS=['motion','association','physical_source','physical'];
export const LAYER_LABELS={motion:'位置與速度曲線',association:'跨鏡頭關聯',physical_source:'物理來源',physical:'物理篩選與人工確認'};
export const unavailableNotice=reason=>`此場景未提供：${text(reason)??'UNKNOWN'}`;
export function layerAvailability(snapshot,layer) {
  const row=snapshot?.layer_availability?.[layer];
  if(row?.status==='UNAVAILABLE')return {layer,available:false,reason:text(row.reason)??'UNKNOWN',notice:unavailableNotice(row.reason)};
  return {layer,available:true,reason:null,notice:''};
}
export const unavailableLayers=snapshot=>GATED_LAYERS.map(layer=>layerAvailability(snapshot,layer)).filter(row=>!row.available);
// Controls that read a gated layer. A control is disabled when any of its layers is unavailable for this scene.
export const CONTROL_LAYERS={'motion-reconstruct':['motion'],'cross-camera-reconstruct':['association'],'physical-reconstruct':['physical_source','physical'],'physical-review':['physical_source','physical']};
export function controlGate(snapshot,control) {
  const blocked=list(CONTROL_LAYERS[control]).map(layer=>layerAvailability(snapshot,layer)).find(row=>!row.available);
  return blocked?{disabled:true,layer:blocked.layer,reason:blocked.reason,notice:blocked.notice}:{disabled:false,layer:null,reason:null,notice:''};
}

// Backend order is the preset order; an explicit default wins when it names a listed scene.
export function defaultSceneId(bootstrap) {
  const scenes=list(bootstrap?.scenes);
  return scenes.find(scene=>scene.scene_id===bootstrap?.default_scene_id)?.scene_id??scenes[0]?.scene_id??null;
}
const inRange=(value,[start,end])=>Number.isFinite(value)&&value>=start-1e-9&&value<=end+1e-9;
// Entry state for a loaded scene. The playback timestamp is kept across a scene switch when it lies in the new range;
// otherwise demo_defaults.selected_timestamp (when in range) or the range start is used. demo_defaults also set the
// cameras, query window and Top-K. Nothing is borrowed from the previous scene except the timestamp value.
export function sceneEntryState(snapshot,{previousTimestamp=null,frameQuery=false}={}) {
  const range=normalizeRange(snapshot?.time_range),cameraIds=list(snapshot?.cameras).map(camera=>camera.camera_id);
  const demo=snapshot?.demo_defaults&&typeof snapshot.demo_defaults==='object'?snapshot.demo_defaults:null;
  const demoCameras=list(demo?.camera_ids).filter(id=>cameraIds.includes(id));
  const demoWindow=Array.isArray(demo?.time_range)?normalizeRange(demo.time_range):null;
  const window=demoWindow&&demoWindow[1]>demoWindow[0]&&inRange(demoWindow[0],range)&&inRange(demoWindow[1],range)?demoWindow:range;
  const selected=inRange(demo?.selected_timestamp,range)?demo.selected_timestamp:null;
  const kept=previousTimestamp!==null&&inRange(previousTimestamp,range);
  const timestamp=kept?previousTimestamp:selected??range[0];
  const cameras=demoCameras.length?demoCameras:cameraIds.slice(0,3);
  const topK=Number.isInteger(demo?.top_k)&&demo.top_k>=1&&demo.top_k<=5?demo.top_k:3;
  return {timestamp,timestampSource:kept?'KEPT':selected!==null?'DEMO_DEFAULT':'RANGE_START',
    start:range[0],end:Math.min(range[1],range[0]+10),cameraId:cameras[0]??null,cameraIds:cameras,
    frameQuerySelection:frameQuery?{camera_ids:[...cameras],start:window[0],end:window[1],target_timestamp:selected??(window[0]+window[1])/2,top_k:topK,behavior_intent:'walking'}:null,
    demoObservationRef:text(demo?.observation_ref)};
}

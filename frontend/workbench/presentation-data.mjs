// IDs remain in canonical records and request payloads. Only their presentation is redacted.
const eventKey = key => /(?:^|_)event_(?:id|ref|ids|refs)$|^(?:selected_event|active_event_refs)$/i.test(key);
const eventToken = /\b(?:(?:event|evt):[A-Za-z0-9_.:\/-]+|event_[A-Za-z0-9_]+)/g;
export function presentationData(value) {
  const refs = new Set();
  const collect = item => {
    if (!item || typeof item !== 'object') return;
    for (const [key, child] of Object.entries(item)) {
      if (eventKey(key) || (key === 'record_ref' && (item.kind === 'EVENT'||item.record_kind === 'EVENT'))) {
        for (const ref of Array.isArray(child) ? child : [child]) if (typeof ref === 'string') refs.add(ref);
      }
      collect(child);
    }
  };
  collect(value);
  const clean = item => {
    if (typeof item === 'string') {
      let text = item.replace(eventToken, '事件識別碼（見 log）');
      for (const ref of refs) if (ref) text = text.split(ref).join('事件識別碼（見 log）');
      return text;
    }
    if (Array.isArray(item)) return item.map(clean);
    if (!item || typeof item !== 'object') return item;
    return Object.fromEntries(Object.entries(item)
      .filter(([key]) => !eventKey(key) && !(key === 'record_ref' && (item.kind === 'EVENT'||item.record_kind === 'EVENT')))
      .map(([key, child]) => [key, clean(child)]));
  };
  return clean(value);
}
export const presentationJSON = value => JSON.stringify(presentationData(value), null, 2);

export function requestIsCurrent(state, ticket) {
  return state.sceneEpoch === ticket.sceneEpoch && state.queryEpoch === ticket.queryEpoch &&
    (ticket.guideEpoch === undefined || state.guideEpoch === ticket.guideEpoch);
}

export function updateGuidanceInputs(target, values) {
  target.guideEpoch=(target.guideEpoch??0)+1;
  target.guide=null;
  target.guideSelection=Object.fromEntries(['label','camera_id','start','end','behavior','top_k']
    .filter(key=>key in values).map(key=>[key,values[key]]));
}

export async function prepareFrames(frames, urlFor, {decode = defaultDecode, current = () => true} = {}) {
  await Promise.all(frames.map(async frame => {
    const ref = frame.media_ref ?? frame.ref;
    if (ref) await decode(urlFor(ref));
  }));
  return current();
}
// decode() can stay pending indefinitely (throttled or unfocused documents); a bounded wait keeps frame updates from stalling.
export const DECODE_TIMEOUT_MS = 600;
export function boundedDecode(decoding, timeoutMs = DECODE_TIMEOUT_MS) {
  let timer;
  const timeout = new Promise(resolve => { timer = setTimeout(resolve, timeoutMs); });
  return Promise.race([Promise.resolve(decoding).catch(() => {}), timeout]).finally(() => clearTimeout(timer));
}
async function defaultDecode(url) {
  const image = new Image(); image.src = url;
  // A failed or slow decode never blocks; the <img> element still loads or shows its own failure.
  await boundedDecode(image.decode());
}

// Preserve exact canvas, image and panel nodes while updating surrounding controls.
export function retainElements(root, markup, selectors) {
  const retained = selectors.map(selector => [selector, root.querySelector(selector)]);
  root.innerHTML = markup;
  for (const [selector, node] of retained) {
    const replacement = root.querySelector(selector);
    if (node && replacement) replacement.replaceWith(node);
  }
}

export function relationGraph(graph) {
  const nodes = (graph?.nodes ?? []).filter(node => typeof (node.node_id ?? node.id) === 'string' &&
    Array.isArray(node.position ?? node.world_position) && (node.position ?? node.world_position).length === 3 &&
    (node.position ?? node.world_position).every(Number.isFinite))
    .map(node => ({...node, id:node.node_id ?? node.id, position:node.position ?? node.world_position}));
  const ids = new Set(nodes.map(node => node.id));
  const edges = (graph?.edges ?? []).map(edge => ({...edge, from:edge.from ?? edge.source ?? edge.source_id ?? edge.from_node_id,
    to:edge.to ?? edge.target ?? edge.target_id ?? edge.to_node_id}))
    .filter(edge => ids.has(edge.from) && ids.has(edge.to));
  return {nodes, edges, presentation_only:true};
}

export function guidanceGraph(input, snapshot, {showRelations=false}={}) {
  const objects=snapshot?.objects??[];
  const nodes=(input?.navigation_nodes??[]).flatMap(node=>{
    const object=objects.find(item=>item.kind===node.kind && (item.object_id===node.resource_id ||item.object_id===node.kind.toLowerCase()+':'+node.resource_id ||
      item.properties?.region_id===node.resource_id || item.properties?.camera_id===node.resource_id));
    const points=(object?.geometry?.points??[]).filter(point=>Array.isArray(point)&&point.length===3&&point.every(Number.isFinite));
    const camera=(snapshot?.cameras??[]).find(item=>item.camera_id===node.resource_id);
    const position=points.length?[0,1,2].map(axis=>points.reduce((total,point)=>total+point[axis],0)/points.length):camera?.position;
    if(!Array.isArray(position)||position.length!==3||!position.every(Number.isFinite))return [];
    return [{id:node.node_ref,position,label:object?.label??camera?.label??node.resource_id,kind:node.kind,resource_id:node.resource_id}];
  });
  const edges=(input?.navigation_edges??[]).map(edge=>({from:edge.from_ref,to:edge.to_ref,relation:edge.relation,
    label:({CONFIGURED_CAMERA_LINK:'預設鏡頭連結',REGISTERED_COVERAGE:'登錄涵蓋關聯',CONFIGURED_REGION_LINK:'預設區域連結'})[edge.relation]??edge.relation}));
  return {...relationGraph({nodes,edges}),focus_node_id:nodes.find(node=>node.kind==='CAMERA'&&node.resource_id===input?.selection?.camera_id)?.id??null,
    show_relation_captions:showRelations};
}

export function graphCaptionPlan(graph,{nodeBudget=3,edgeBudget=2}={}) {
  const data=relationGraph(graph),byId=new Map(data.nodes.map(node=>[node.id,node]));
  const focus=byId.get(graph?.focus_node_id);
  if(!focus)return {...data,nodeCaptions:[],edgeCaptions:[]};
  const nodeCaptions=[focus];
  const edgeCaptions=graph.show_relation_captions?data.edges.filter(edge=>edge.from===focus.id||edge.to===focus.id).slice(0,edgeBudget):[];
  for(const edge of edgeCaptions){
    const other=byId.get(edge.from===focus.id?edge.to:edge.from);
    if(other&&!nodeCaptions.includes(other)&&nodeCaptions.length<nodeBudget)nodeCaptions.push(other);
  }
  return {...data,nodeCaptions:nodeCaptions.slice(0,nodeBudget),edgeCaptions};
}

// K3: scene presets, contact_quality flags and per-scene layer availability. Pure helpers shared by app, 3D scene and 2D overlays
// (kept in this served module: the workbench static allowlist is backend-owned).
// contact_quality is a QUALITY_FLAG_ONLY_POSITION_UNCHANGED field: it changes only how a point is drawn and labelled, never where.
export const CONTACT_FLAG_TAG='接地點不可靠';
export const CONTACT_UNEVALUATED_TAG='接地未評估';
export const CONTACT_UNKNOWN_STATUS_TAG='品質狀態未知';
const qualityList=value=>Array.isArray(value)?value:[];
// Same rule as app.mjs normalizeRange; kept local so the 3D scene can import this module without the app.
function normalizeSceneRange(value) {
  const start=Number(Array.isArray(value)?value[0]:value?.start??0),end=Number(Array.isArray(value)?value[1]:value?.end??start);
  return Number.isFinite(start)&&Number.isFinite(end)&&end>=start?[start,end]:[0,0];
}
const qualityText=value=>typeof value==='string'&&value?value:null;

// FLAGGED: hollow/dashed marker plus the short tag and reasons. PASS: drawn normally. NOT_EVALUATED: neutral tag.
// A sample without the field is drawn exactly as before. An unrecognised status is drawn like PASS (same position and marker)
// and only gets the neutral tag 品質狀態未知.
export function contactQualityStyle(quality) {
  const status=qualityText(quality?.status),reasons=qualityList(quality?.reasons).map(qualityText).filter(Boolean);
  if(status==='FLAGGED')return {status,marker:'flagged',hollow:true,dashed:true,tag:CONTACT_FLAG_TAG,reasons,
    label:`${CONTACT_FLAG_TAG}${reasons.length?'（'+reasons.join('、')+'）':''}`};
  if(status==='NOT_EVALUATED')return {status,marker:'neutral',hollow:false,dashed:false,tag:CONTACT_UNEVALUATED_TAG,reasons,
    label:`${CONTACT_UNEVALUATED_TAG}${reasons.length?'（'+reasons.join('、')+'）':''}`};
  if(status&&status!=='PASS')return {status:null,marker:'normal',hollow:false,dashed:false,tag:CONTACT_UNKNOWN_STATUS_TAG,reasons:[],label:CONTACT_UNKNOWN_STATUS_TAG};
  return {status:status==='PASS'?'PASS':null,marker:'normal',hollow:false,dashed:false,tag:null,reasons:[],label:''};
}
// Adds a style next to the sample; every other field (world_position, bbox, contact pixel, timestamp) is the same value.
export const styleContactSample=sample=>({...sample,contact_style:contactQualityStyle(sample?.contact_quality)});

// Inspector lines for the samples shown at one tick: only FLAGGED and NOT_EVALUATED produce a line.
export function contactQualityReadout(samples,{cameraLabel=id=>id??'鏡頭未知'}={}) {
  const seen=new Set();
  return qualityList(samples).flatMap(sample=>{
    const style=contactQualityStyle(sample?.contact_quality);if(!style.tag)return [];
    const line=`${style.label} · ${cameraLabel(sample.camera_id??null)} · ${Number.isFinite(sample.timestamp)?sample.timestamp.toFixed(1)+' s':'時間未知'}`;
    if(seen.has(line))return [];seen.add(line);return [line];
  });
}

// Layers the backend may mark UNAVAILABLE per scene (snapshot.layer_availability.<layer>.status).
export const GATED_LAYERS=['motion','association','physical_source','physical'];
export const LAYER_LABELS={motion:'位置與速度曲線',association:'跨鏡頭關聯',physical_source:'物理來源',physical:'物理篩選與人工確認'};
export const unavailableNotice=reason=>`此場景未提供：${qualityText(reason)??'UNKNOWN'}`;
export function layerAvailability(snapshot,layer) {
  const row=snapshot?.layer_availability?.[layer];
  if(row?.status==='UNAVAILABLE')return {layer,available:false,reason:qualityText(row.reason)??'UNKNOWN',notice:unavailableNotice(row.reason)};
  return {layer,available:true,reason:null,notice:''};
}
export const unavailableLayers=snapshot=>GATED_LAYERS.map(layer=>layerAvailability(snapshot,layer)).filter(row=>!row.available);
// Controls that read a gated layer. A control is disabled when any of its layers is unavailable for this scene.
// Known gaps (not changed here): the server's physical_cross_camera_reconstruction checks only `physical`, while the frontend is
// stricter and requires physical_source + physical. The server's target_reconstruction maps to `association`; when K4/C4b
// connect it, add its control to this table.
export const CONTROL_LAYERS={'motion-reconstruct':['motion'],'cross-camera-reconstruct':['association'],'physical-reconstruct':['physical_source','physical'],'physical-review':['physical_source','physical']};
export function controlGate(snapshot,control) {
  const blocked=qualityList(CONTROL_LAYERS[control]).map(layer=>layerAvailability(snapshot,layer)).find(row=>!row.available);
  return blocked?{disabled:true,layer:blocked.layer,reason:blocked.reason,notice:blocked.notice}:{disabled:false,layer:null,reason:null,notice:''};
}

// Scenes marked available:false are never selected. An explicit default_scene_id wins when it names a usable scene. The bootstrap
// currently has no default_scene_id, so the fallback path (first usable scene, in backend preset order) is the normal one.
// Returns null when no scene is usable; the caller shows an error.
export const sceneUsable=scene=>scene?.available!==false;
export function defaultSceneId(bootstrap) {
  const scenes=qualityList(bootstrap?.scenes).filter(sceneUsable);
  return scenes.find(scene=>scene.scene_id===bootstrap?.default_scene_id)?.scene_id??scenes[0]?.scene_id??null;
}
// Option label for the scene selector; an unavailable scene is disabled and names its reason.
export const sceneOptionLabel=scene=>sceneUsable(scene)?(scene.label??scene.scene_id):`${scene.label??scene.scene_id}（不可用：${qualityText(scene.reason)??'UNKNOWN'}）`;
const inSceneRange=(value,[start,end])=>Number.isFinite(value)&&value>=start-1e-9&&value<=end+1e-9;
// Entry state for a loaded scene. The playback timestamp is kept across a scene switch when it lies in the new range;
// otherwise demo_defaults.selected_timestamp (when in range) or the range start is used. demo_defaults also set the
// cameras, query window and Top-K. Nothing is borrowed from the previous scene except the timestamp value.
export function sceneEntryState(snapshot,{previousTimestamp=null,frameQuery=false}={}) {
  const range=normalizeSceneRange(snapshot?.time_range),cameraIds=qualityList(snapshot?.cameras).map(camera=>camera.camera_id);
  const demo=snapshot?.demo_defaults&&typeof snapshot.demo_defaults==='object'?snapshot.demo_defaults:null;
  const demoCameras=qualityList(demo?.camera_ids).filter(id=>cameraIds.includes(id));
  const demoWindow=Array.isArray(demo?.time_range)?normalizeSceneRange(demo.time_range):null;
  const window=demoWindow&&demoWindow[1]>demoWindow[0]&&inSceneRange(demoWindow[0],range)&&inSceneRange(demoWindow[1],range)?demoWindow:range;
  const selected=inSceneRange(demo?.selected_timestamp,range)?demo.selected_timestamp:null;
  const kept=previousTimestamp!==null&&inSceneRange(previousTimestamp,range);
  const timestamp=kept?previousTimestamp:selected??range[0];
  const cameras=demoCameras.length?demoCameras:cameraIds.slice(0,3);
  const topK=Number.isInteger(demo?.top_k)&&demo.top_k>=1&&demo.top_k<=5?demo.top_k:3;
  return {timestamp,timestampSource:kept?'KEPT':selected!==null?'DEMO_DEFAULT':'RANGE_START',
    start:range[0],end:Math.min(range[1],Math.max(range[0]+10,timestamp)),cameraId:cameras[0]??null,cameraIds:cameras,
    frameQuerySelection:frameQuery?{camera_ids:[...cameras],start:window[0],end:window[1],target_timestamp:selected??(window[0]+window[1])/2,top_k:topK,behavior_intent:'walking'}:null,
    demoObservationRef:qualityText(demo?.observation_ref)};
}

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

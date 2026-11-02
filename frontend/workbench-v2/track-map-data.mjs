// Data adapter for the 俯視圖. Uses the backend routes of DEMO_UI_SUPPORT_V1 when they answer; otherwise labelled SYNTHETIC
// stand-ins from fixtures/track-map/synthetic.json. Only same-origin /api/ routes are ever called (no external API from the
// front end) and no route is retried or polled. Stand-ins read the timeline only up to as_of_us.
import {observedPath} from './track-map-model.mjs';
export const ROUTES=Object.freeze({map:'/api/q_camera_map',physical:'/api/q_physical_prediction',external:'/api/q_external_prediction'});
const MISSING=new Set([404,405,501,503]);
const sec=us=>Math.floor(us/1e6);
export function syntheticPhysical(fixture,timeline,asOfUs) {
  const path=observedPath(timeline,asOfUs);
  if(!fixture||!path.current)return null;
  const rows=fixture.prediction_table?.[path.current]??[];
  return {schema_version:'q-demo.physical-prediction.v1',as_of_us:asOfUs,last_camera_id:path.current,last_observed_us:path.lastObservedUs,
    candidates:rows.map((r,i)=>({camera_id:r.camera_id,rank:i+1,relation:r.relation,confidence:r.confidence,path_traversability:'UNKNOWN',path_has_unknown_state:true,
      window_us:[path.lastObservedUs+r.hop_window_us[0],path.lastObservedUs+r.hop_window_us[1]]})),
    status:rows.length?'PREDICTED':'NO_CANDIDATE',graph_approval_status:'DRAFT',direction:{status:'UNKNOWN'},used_for:'DISPLAY_ONLY',identity_verdict:'UNCONFIRMED',physical_navigation:'UNKNOWN',gt_read:false};
}
export function syntheticExternal(fixture,timeline,asOfUs) {
  const path=observedPath(timeline,asOfUs),row=path.current?fixture?.external_replay?.[path.current]:null;
  const base={schema_version:'q-demo.external-prediction.v1',as_of_us:asOfUs,used_for:'DISPLAY_ONLY',scoring_use:false,identity_verdict:'UNCONFIRMED',gt_read:false};
  return row?{...base,status:'AVAILABLE',reason:null,candidates:row.candidates}:{...base,status:'UNAVAILABLE',reason:'REPLAY_MISS',candidates:[]};
}
export function createTrackMapData({fetchImpl=globalThis.fetch,getSession=()=>null,fixture=null,offline=false}={}) {
  const dead=new Set(),cache=new Map();
  async function post(route,payload) {
    if(offline||dead.has(route)||typeof fetchImpl!=='function')return null;
    try {
      const r=await fetchImpl(route,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_ref:getSession(),...payload})});
      if(!r.ok){if(MISSING.has(r.status))dead.add(route);return null;}
      return JSON.parse(await r.text());
    }catch{dead.add(route);return null;}
  }
  const once=(key,make)=>{if(!cache.has(key))cache.set(key,make());return cache.get(key);};
  return {
    cameraMap:({scene_id,run_id})=>once(`map:${scene_id}:${run_id}`,async()=>{
      const doc=await post(ROUTES.map,{scene_id,run_id});
      return doc?.schema_version==='q-demo.camera-map.v1'?{origin:'API',doc}:{origin:'SYNTHETIC',doc:fixture?.camera_map??null};
    }),
    physical:async({responseRef,asOfUs,timeline})=>{
      const doc=await post(ROUTES.physical,{response_ref:responseRef,as_of_us:asOfUs});
      return doc?.schema_version==='q-demo.physical-prediction.v1'?{origin:'API',doc}:{origin:'SYNTHETIC',doc:syntheticPhysical(fixture,timeline,asOfUs)};
    },
    // One logical call per (response, second): the backend de-duplicates the same key and the front end never retries.
    external:({responseRef,asOfUs,timeline})=>once(`ext:${responseRef}:${sec(asOfUs)}`,async()=>{
      const doc=await post(ROUTES.external,{response_ref:responseRef,as_of_us:asOfUs});
      if(doc?.schema_version==='q-demo.external-prediction.v1')return {origin:'API',doc};
      // D109-3: with a backend, no delivered route / no recorded response → 外部推測不可用. The labelled SYNTHETIC replay fixture
      // is only for the explicit no-backend fixture mode (offline), never as a stand-in for a denied or missing route.
      if(offline)return {origin:'SYNTHETIC',doc:syntheticExternal(fixture,timeline,asOfUs)};
      return {origin:'API',doc:{schema_version:'q-demo.external-prediction.v1',as_of_us:asOfUs,used_for:'DISPLAY_ONLY',scoring_use:false,identity_verdict:'UNCONFIRMED',gt_read:false,status:'UNAVAILABLE',reason:'ROUTE_UNAVAILABLE',candidates:[]}};
    }),
    forget(){cache.clear();},
  };
}

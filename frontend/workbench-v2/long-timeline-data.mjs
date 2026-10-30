// Read-only view projection. No renderer, script, evaluation, or GT inputs.
import {parseRaw,canonicalJSON,contentHash,sha256Hex,validateQResponse,checkDecision,integer,validRange} from './q-validate.mjs';
import {validateClock} from './q-time.mjs';
export const P1_V4 = Object.freeze({
  manifest_sha256:'6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7',
  recording:'data/recordings/2777741d96ac9aff5bffb2f61a4d2938.json',
  index:'data/registry/index/detection_index.json', clock:'data/registry/clock.json',
});
const need=(ok,code)=>{if(!ok)throw new Error(code);};
const has=(range,t)=>range[0]<=t&&t<range[1];
const intersect=(a,b)=>[Math.max(a[0],b[0]),Math.min(a[1],b[1])];
const label=v=>typeof v==='string'&&v.length>0;

// Only allowlisted properties are accessed here, including on nested objects.
// Caller validates hashes/schema before projection; this function rechecks view bindings.
export function projectRecordedTimeline({response,index,clock,observations,decisions}) {
  need(response.identity_verdict==='UNCONFIRMED'&&response.provenance?.gt_read===false&&index.provenance?.gt_read===false,'INFERENCE_BOUNDARY');
  const scope=response.resolved_scope,D=clock.source_duration_us;
  need(integer(D)&&D>0&&clock.t0_us===0,'SOURCE_RANGE');
  need(scope.run_ids?.length===1&&scope.run_ids[0]===index.run_id&&index.run_id===clock.run_id&&scope.scene_id===index.scene_id&&scope.scene_revision===index.scene_revision,'SCOPE_MISMATCH');
  need(scope.clock_ids?.length===1&&scope.clock_ids[0]===clock.clock_id&&clock.clock_id===index.clock_id&&scope.clock_mapping_sha256===clock.content_sha256&&scope.detection_index_sha256===index.content_sha256&&scope.detection_index_id===index.index_id,'PIN_BINDING');
  const range=r=>{need(validRange(r)&&r[1]<=D,'SOURCE_INTEGER_RANGE');return [r[0],r[1]];};
  const requested=(scope.resolved_source_ranges_us??[]).map(r=>{need(r.run_id===index.run_id,'SCOPE_MISMATCH');return range(r.range_us);});
  need(requested.length>0,'SCOPE_MISSING');
  const ids=scope.camera_ids;need(Array.isArray(ids)&&ids.length>0&&ids.length<=8&&ids.every(label)&&new Set(ids).size===ids.length,'CAMERA_SCOPE');
  const samples=index.sampling?.per_camera;need(Array.isArray(samples),'INDEX_COVERAGE');
  const timeline=response.timeline;need(Array.isArray(timeline),'TIMELINE_REQUIRED');
  let end=0;
  for(const s of timeline){const r=range(s.range_us);need(r[0]>=end&&['ON_CAMERA','GAP'].includes(s.kind),'TIMELINE_ORDER');end=r[1];need(ids.includes(s.kind==='GAP'?s.camera_shown:s.camera_id),'CAMERA_SCOPE');}
  const cameras=ids.map(camera_id=>{
    const rows=samples.filter(c=>c.camera_id===camera_id);need(rows.length===1,'INDEX_CAMERA');const sample=rows[0];
    need(integer(sample.index_interval_us)&&sample.index_interval_us>0,'INDEX_INTERVAL');
    const inferred=(sample.inferred_ranges_us??[]).map(range),absent=(sample.not_inferred??[]).map(n=>({range_us:range(n.range_us),reason:n.reason}));
    const claims=[];
    const add=(r,state)=>{for(const q of requested){const clipped=intersect(r,q);if(clipped[0]<clipped[1])claims.push({range_us:clipped,state});}};
    for(const a of absent)add(a.range_us,a.reason==='MISSING'?'MISSING':'UNKNOWN');
    for(const s of timeline){
      if(s.kind==='GAP'&&s.camera_shown===camera_id){need(s.position===null,'GAP_POSITION');for(const covered of inferred){const r=intersect(s.range_us,covered);if(r[0]<r[1])add(r,'GAP');}}
      if(s.kind==='ON_CAMERA'&&s.camera_id===camera_id){
        need(Array.isArray(s.observation_ids),'OBSERVATION_REFS');
        for(const id of s.observation_ids){const obs=observations?.[id];need(obs&&obs.observation_id===id&&obs.camera_id===camera_id&&integer(obs.timestamp_us)&&has(s.range_us,obs.timestamp_us),'OBSERVATION_BINDING');
          const cell=[obs.timestamp_us,Math.min(D,obs.timestamp_us+sample.index_interval_us,s.range_us[1])];
          for(const covered of inferred){const r=intersect(cell,covered);if(r[0]<r[1])add(r,'OBSERVED');}
        }
      }
    }
    const points=[...new Set([0,D,...claims.flatMap(c=>c.range_us)])].sort((a,b)=>a-b),segments=[];
    for(let i=1;i<points.length;i++){
      const r=[points[i-1],points[i]],states=new Set(claims.filter(c=>has(c.range_us,r[0])).map(c=>c.state));
      need(states.size<=1,'COVERAGE_CONFLICT');const state=[...states][0]??'UNKNOWN',last=segments.at(-1);
      if(last?.state===state)last.range_us[1]=r[1];else segments.push({range_us:r,state});
    }
    return {camera_id,segments};
  });
  const events=[];
  for(const d of decisions){
    need(d.session_id===response.session_id&&integer(d.source_time_us)&&d.source_time_us<=D,'DECISION_SCOPE');
    if(!d.accepted)continue;
    const action=d.executed_action;
    const t=action&&d.decision_time_us!==null?d.decision_time_us:d.source_time_us;
    need(integer(t)&&t<=d.source_time_us,'DECISION_TIME');
    if(t===D)continue; // End boundary is not a playable frame.
    need(label(d.decision_id)&&label(d.state_after),'DECISION_FIELDS');
    events.push({id:d.decision_id,t_us:t,kind:action||d.state_after,
      label:action?`${action} · ${d.decided_by} · source ${d.source_time_us} µs`:`${d.state_after} · ${d.decided_by}`});
  }
  need(new Set(events.map(e=>e.id)).size===events.length,'DECISION_ID');
  events.sort((a,b)=>a.t_us-b.t_us||a.id.localeCompare(b.id));
  return {source_duration_us:D,cameras,events,q1_clips:{},identity_verdict:'UNCONFIRMED',run_id:index.run_id};
}

// Raw JSON preserves Python float lexemes. It is parsed/hashed for integrity;
// only projectRecordedTimeline's allowlist reaches the view model.
export async function decodeRecordedTimeline({recordingRaw,indexRaw,clockRaw}) {
  const recording=parseRaw(recordingRaw),index=parseRaw(indexRaw);
  need(recording.schema_version==='q-demo.api-recording.v1'&&recording.data_origin==='RECORDED','RECORDING_SCHEMA');
  need(await contentHash(recording,{excludeRoot:['content_sha256']})===recording.content_sha256,'RECORDING_HASH');
  need(index.schema_version==='q-demo.detection-index.v1'&&await contentHash(index,{excludeRoot:['content_sha256','index_id']})===index.content_sha256,'INDEX_HASH');
  const clockResult=await validateClock(clockRaw);need(clockResult.ok,clockResult.error?.code??'CLOCK_INVALID');const clock=clockResult.data;
  const result=await validateQResponse('q2',canonicalJSON(recording.response),{run_id:recording.run_id,scene_id:recording.scene_id});
  need(result.ok,result.error?.code??'RESPONSE_INVALID');
  const response=result.data;
  need(typeof recording.decisions==='string'&&await sha256Hex(recording.decisions)===response.decisions_sha256,'JOURNAL_HASH');
  const decisions=[];
  for(const line of recording.decisions.split('\n').filter(Boolean)){const row=parseRaw(line);await checkDecision(row,response.session_id,decisions.length,decisions);decisions.push(row);}
  return projectRecordedTimeline({response,index,clock,observations:recording.observations,decisions});
}

// #329 and CX-8 formal freezes are not delivered/selected here. The only
// production file-selection fallback currently registered is the pinned P1 v4.
// A self-declared FORMAL flag or a caller-provided hash cannot grant authority.
export async function loadP1Recording(files) {
  need(await sha256Hex(files.manifestRaw)===P1_V4.manifest_sha256,'SOURCE_UNSELECTED');
  const manifest=parseRaw(files.manifestRaw);
  need(manifest.formal_eligible===false&&manifest.gt_read===false,'ENGINEERING_ONLY');
  for(const [key,path] of [['recordingRaw',P1_V4.recording],['indexRaw',P1_V4.index],['clockRaw',P1_V4.clock]]){
    const pin=manifest.files?.[path],raw=files[key];
    need(pin&&typeof raw==='string'&&new TextEncoder().encode(raw).length===pin.bytes&&await sha256Hex(raw)===pin.sha256,'FILE_PIN_MISMATCH');
  }
  const view=await decodeRecordedTimeline(files);
  return {...view,origin:'ENGINEERING · P1 v4 · RECORDED · source_kind=SYNTHETIC',
    note:'P1 工程錄製（2 台鏡頭、8 秒）；正式複雜事件與 r004 凍結輸出尚未到位。僅顯示已錄製回應與索引覆蓋，無 RGB。'};
}

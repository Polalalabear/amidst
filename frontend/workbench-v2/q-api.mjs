// Same Q requests for Demo/review. Source selection never falls back to fixtures.
import { createEpoch,apiError,errorFromBody,validateBootstrap as legacyBootstrap } from './api.mjs';
import { parseRaw,checkRequest,validateQResponse,contentHash,sha256Hex,noPrivate,freezeDeep,isValidated,checkDecision } from './q-validate.mjs';
import { validateClock } from './q-time.mjs';
export const FIXTURE_ORIGIN='SYNTHETIC_FIXTURE';
const files=Object.freeze({q1:['q1-ready','q1-partial','q1-no-match','q1-out-of-range'],q2:['q2-rule','q2-agent','q2-no-support'],q3:['q3-parsed','q3-clarification','q3-unsupported','q3-failed']});
const paths=Object.freeze({q1:'/api/q1_camera_search',q2:'/api/q2_session',q3:'/api/q3_parse'});
const equalRequest=(a,b)=>{const clean=q=>Object.fromEntries(Object.entries(q).filter(([k])=>!['session_ref','origin'].includes(k)));return JSON.stringify(clean(a))===JSON.stringify(clean(b));};
function stable(value){if(Array.isArray(value))return value.map(stable);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])]));return value;}
const matches=(a,b)=>equalRequest(stable(a),stable(b));
const need=(ok,code)=>{if(!ok)throw new Error(code);};

export async function validateQBootstrap(input) {
  try {
    const b=typeof input==='string'?parseRaw(input):parseRaw(JSON.stringify(input));
    if(b.schema_version==='controlled-scene.bootstrap.v1'){legacyBootstrap(b);throw new Error('Q_BOOTSTRAP_NOT_AVAILABLE');}
    need(b.schema_version==='q-demo.api-bootstrap.v1'&&b.gt_read===false&&b.identity_verdict==='UNCONFIRMED','BOOTSTRAP_BOUNDARY');
    need(['LIVE','RECORDED','UNAVAILABLE',FIXTURE_ORIGIN].includes(b.data_origin)&&['AVAILABLE','NOT_READY'].includes(b.status),'BOOTSTRAP_STATUS');
    need(b.default_switch_mode==='RULE_ONLY'&&Array.isArray(b.runs)&&Array.isArray(b.recordings),'BOOTSTRAP_FIELDS');noPrivate(b);
    for(const run of b.runs){need(typeof run.scene_id==='string'&&typeof run.run_id==='string'&&Array.isArray(run.camera_ids)&&new Set(run.camera_ids).size===run.camera_ids.length,'BOOTSTRAP_SCOPE');
      if(run.clock_mapping){const c=await validateClock(run.clock_mapping);need(c.ok&&c.data.run_id===run.run_id,'CLOCK_MAPPING_INVALID');}
      need(run.query_defaults&&run.sampling&&Number.isFinite(run.index_score_floor),'QUERY_SETTINGS_MISSING');
      const catalog=run.supported_classes;need(catalog&&await contentHash(catalog,{excludeRoot:['content_sha256','stats']})===catalog.content_sha256,'CLASS_CATALOG_PIN');
    }
    return {ok:true,data:freezeDeep(b)};
  }catch(error){return apiError(error.message);}
}

export function buildQ1(run,session,args={}) {
  const q={schema_version:'q-demo.q1-request.v1',session_ref:session,scene_id:run.scene_id,run_ids:[run.run_id],
    time:{kind:'SOURCE',run_id:run.run_id,range_us:[0,run.clock_mapping.source_duration_us]},
    condition:{class_label:'person',min_count_per_frame:run.query_defaults.min_count_per_frame,color:null,query_min_score:run.query_defaults.query_min_score},
    camera_ids:null,region_ids:null,page_size:run.query_defaults.page_size,cursor:null,origin:'MANUAL',...args};checkRequest('q1',q);return q;
}
export function buildQ2(run,session,seed,args={}) {
  const q={schema_version:'q-demo.q2-request.v1',session_ref:session,scene_id:run.scene_id,run_ids:[run.run_id],
    time:{kind:'SOURCE',run_id:run.run_id,range_us:[0,run.clock_mapping.source_duration_us]},seed,switch_mode:'RULE_ONLY',parameter_set_id:run.parameter_set_id,...args};checkRequest('q2',q);return q;
}
export function buildQ3(run,session,text,parserMode='RULE_ONLY') {
  const q={schema_version:'q-demo.q3-parse-request.v1',session_ref:session,text,locale:'zh-TW',context:{scene_id:run.scene_id,run_ids:[run.run_id],clock_mapping_sha256:run.clock_mapping?.content_sha256??null},parser_mode:parserMode};checkRequest('q3',q);return q;
}

export function createQApi({fetchImpl=globalThis.fetch,source='SERVER',fixtureBase='/workbench-v2/fixtures/',role='research'}={}) {
  need(['SERVER',FIXTURE_ORIGIN].includes(source),'SOURCE_INVALID');
  const epoch=createEpoch(),packs=new Map(),requests=[];let origin=source,session=null,bootstrapData=null,activeJob=null;
  async function raw(path,payload) {
    const options=payload===undefined?{method:'GET',credentials:'same-origin',cache:'no-store'}:{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
    const response=await fetchImpl(path,options);const text=await response.text();
    if(!response.ok){let body;try{body=parseRaw(text);}catch{throw new Error('HTTP_'+response.status);}
      throw new Error(body.error_code??errorFromBody(body,response.status).error?.code??'HTTP_'+response.status);}
    return text;
  }
  async function pack(name) {
    if(packs.has(name))return packs.get(name);
    need(Object.values(files).flat().includes(name),'FIXTURE_NOT_ALLOWLISTED');
    const doc=parseRaw(await raw(fixtureBase+name+'.json'));
    need(doc.schema_version==='q-demo.ui-fixture.v1'&&doc.data_origin===FIXTURE_ORIGIN&&doc.fixture_id.startsWith('FICT_')&&Array.isArray(doc.cases),'FIXTURE_ORIGIN');
    packs.set(name,freezeDeep(doc));return doc;
  }
  async function bootstrap() {
    try {
      let text;
      if(source===FIXTURE_ORIGIN){const wrapper=parseRaw(await raw(fixtureBase+'q-bootstrap.json'));need(wrapper.data_origin===FIXTURE_ORIGIN,'FIXTURE_ORIGIN');text=wrapper.bootstrap_json;}
      else text=await raw('/api/q_bootstrap');
      const result=await validateQBootstrap(text);if(!result.ok)return result;
      need(source===FIXTURE_ORIGIN?result.data.data_origin===FIXTURE_ORIGIN:result.data.data_origin!==FIXTURE_ORIGIN,'DATA_ORIGIN_MISMATCH');
      bootstrapData=result.data;origin=result.data.data_origin;return result;
    }catch(error){return apiError(error.message);}
  }
  async function createSession() {
    if(source===FIXTURE_ORIGIN){session='FICT_UI_SESSION';return {ok:true,data:{session_ref:session,role}};}
    try{const body=parseRaw(await raw('/api/session',{role}));need(typeof body.session_ref==='string','SESSION_INVALID');session=body.session_ref;return {ok:true,data:freezeDeep(body)};}
    catch(error){return apiError(error.message);}
  }
  async function initialRequest(kind,name=files[kind]?.[0]) {
    need(source===FIXTURE_ORIGIN,'FIXTURE_ONLY');const doc=await pack(name);const q=parseRaw(doc.cases[0].request_json);q.session_ref=session;return q;
  }
  async function bindResponse(kind,request,response,selected) {
    const scope=kind==='q3'?request.context:request;
    const run=bootstrapData?.runs.find(x=>x.scene_id===scope.scene_id&&x.run_id===scope.run_ids[0]);
    need(run,'REQUEST_RUN_NOT_BOOTSTRAPPED');const r=response.resolved_scope;
    need(r.scene_revision===run.scene_revision,'RESPONSE_BINDING');
    for(const [actual,expected] of [[r.parameter_set_sha256,run.parameter_set_sha256],[r.clock_mapping_sha256,run.clock_mapping?.content_sha256??null]])if(actual!==null)need(actual===expected,'RESPONSE_BINDING');
    if(['READY','NO_MATCH','PARTIAL','COMPLETE','NO_SEED','ENDED_BY_LIMIT'].includes(response.status))need(r.parameter_set_sha256===run.parameter_set_sha256&&r.clock_mapping_sha256===(run.clock_mapping?.content_sha256??null),'RESPONSE_BINDING');
    if(kind!=='q3')need(r.detection_index_sha256===run.detection_index_sha256,'RESPONSE_BINDING');
    if(kind==='q1'){
      const normalized=JSON.parse(JSON.stringify(request));delete normalized.origin;delete normalized.cursor;
      const label=normalized.condition.class_label;
      normalized.condition.class_label=Object.entries(run.supported_classes.aliases).find(([key])=>key.toLowerCase()===label.toLowerCase())?.[1]??label;
      const digest=await contentHash({request:normalized,bindings:{index:run.detection_index_sha256,aliases:run.supported_classes.content_sha256,parameters:run.parameter_set_sha256,clock:run.clock_mapping?.content_sha256??null}});
      need(response.query_sha256===digest&&response.query_id==='q1-'+digest.slice(0,16),'QUERY_BINDING');
    }
    if(kind==='q2'){
      const digest=await contentHash({request:JSON.parse(JSON.stringify(request)),index:run.detection_index_sha256,region:run.region_graph_sha256,camera:run.camera_graph_sha256,
        clock:run.clock_mapping?.content_sha256??null,parameters:run.parameter_set_sha256,media:run.media_scope_sha256,selected_seed:selected});
      need(response.session_id==='sess-'+digest.slice(0,16),'SESSION_BINDING');
      if(request.switch_mode==='RULE_ONLY')need(!response.agent_attempted&&!response.agent_used&&!response.fallback_used,'RULE_ONLY_FLAGS');
    }
  }
  async function query(kind,request,{selected_observation_id=null}={}) {
    const token=epoch.begin('query');requests.push(freezeDeep(structuredClone(request)));
    try {
      checkRequest(kind,request);let text;
      if(source===FIXTURE_ORIGIN){
        for(const name of files[kind]){const doc=await pack(name);const entry=doc.cases.find(x=>matches(parseRaw(x.request_json),request)&&(kind!=='q2'||(x.selected_observation_id??null)===selected_observation_id));if(entry){text=entry.response_json;break;}}
        need(text,'FIXTURE_REQUEST_NOT_RECORDED');
      }else{
        need(origin==='LIVE','RECORDED_READ_ONLY');
        if(kind==='q2'){
          let job=await startSession(request,selected_observation_id);need(job.ok,job.error?.code??'JOB_FAILED');
          const id=job.data.session_id;activeJob=id;
          try{
            while(job.data.status==='RUNNING'&&epoch.isCurrent('query',token)){
              await new Promise(resolve=>setTimeout(resolve,150));
              job=await pollSession(id);need(job.ok,job.error?.code??'JOB_FAILED');
            }
            if(!epoch.isCurrent('query',token))return apiError('STALE_RESPONSE');
            need(job.data.status==='COMPLETE',job.data.error_code??'JOB_FAILED');text=JSON.stringify(job.data.response);
          }finally{if(activeJob===id)activeJob=null;}
        }else text=await raw(paths[kind],request);
      }
      if(!epoch.isCurrent('query',token))return apiError('STALE_RESPONSE');
      const scope=kind==='q3'?request.context:request;
      const result=await validateQResponse(kind,text,{scene_id:scope.scene_id,run_id:scope.run_ids[0]});
      if(result.ok&&source!==FIXTURE_ORIGIN)await bindResponse(kind,request,result.data,selected_observation_id);
      return epoch.isCurrent('query',token)?result:apiError('STALE_RESPONSE');
    }catch(error){return apiError(error.message);}
  }
  async function fixtureArtifact(response,kind,ref) {
    for(const name of (response.schema_version==='q-demo.q1-response.v1'?files.q1:files.q2)){const doc=await pack(name);for(const c of doc.cases){const r=parseRaw(c.response_json);if((r.session_id??r.output_sha256)!==(response.session_id??response.output_sha256))continue;
      const a=c.artifacts??{};if(kind==='decisions'||kind==='links')return {jsonl:a[kind]??''};
      const rows=a[kind]??{};if(Object.hasOwn(rows,ref))return parseRaw(rows[ref]);}}
    throw new Error('ARTIFACT_NOT_ISSUED');
  }
  async function artifact(response,kind,ref) {
    try {
      need(isValidated(response),'UNVALIDATED_RESPONSE');
      let data=source===FIXTURE_ORIGIN?await fixtureArtifact(response,kind,ref):parseRaw(await raw('/api/q2_artifact',{session_ref:session,response_ref:response.session_id??response.output_sha256,kind,ref}));
      if(kind==='decisions'||kind==='links'){
        need(ref===response[kind+'_ref']&&typeof data.jsonl==='string'&&await sha256Hex(data.jsonl)===response[kind+'_sha256'],'JOURNAL_PIN');
        if(kind==='decisions'){
          data=data.jsonl.split('\n').filter(Boolean).map(parseRaw);
          for(const [i,row] of data.entries())await checkDecision(row,response.session_id,i,data.slice(0,i));
        }else data=data.jsonl.split('\n').filter(Boolean).map(parseRaw);
      }else if(kind==='snapshot')need(await contentHash(data,{excludeRoot:['candidate_snapshot_sha256','stats'],stripCandidateRefs:true})===ref&&data.candidate_snapshot_sha256===ref,'SNAPSHOT_PIN');
      else if(kind==='evidence')need(await contentHash(data,{excludeRoot:['evidence_sha256','stats']})===ref&&data.evidence_sha256===ref,'EVIDENCE_PIN');
      else if(kind==='observation')need(data.observation_id===ref&&Array.isArray(data.bbox_xyxy_px)&&data.bbox_xyxy_px.length===4&&data.bbox_xyxy_px.every(Number.isFinite),'OBSERVATION_PIN');
      else throw new Error('ARTIFACT_KIND');
      noPrivate(data);return {ok:true,data:freezeDeep(data)};
    }catch(error){return apiError(error.message);}
  }
  async function seedCandidates(request) {
    const token=epoch.begin('query');
    try {
      checkRequest('q2',request);let data;
      if(source===FIXTURE_ORIGIN){
        for(const name of files.q2){const doc=await pack(name);const entry=doc.cases.find(x=>matches(parseRaw(x.request_json),request));if(entry?.seed_candidates_json){data=parseRaw(entry.seed_candidates_json);break;}}
        need(data,'FIXTURE_REQUEST_NOT_RECORDED');
      }else data=parseRaw(await raw('/api/q2_seed_candidates',request));
      if(!epoch.isCurrent('query',token))return apiError('STALE_RESPONSE');
      need(data.schema_version==='q-demo.seed-candidates.v1'&&['CHOICE_REQUIRED','AVAILABLE','UNAVAILABLE'].includes(data.status)&&data.gt_read===false&&data.identity_verdict==='UNCONFIRMED'&&Array.isArray(data.candidates),'SEED_CANDIDATES');
      if(source!==FIXTURE_ORIGIN)need(data.request_sha256===await contentHash(request),'SEED_REQUEST_BINDING');
      need(new Set(data.candidates.map(c=>c.observation_id)).size===data.candidates.length&&data.candidates.every(c=>typeof c.observation_id==='string'&&typeof c.camera_id==='string'&&Number.isSafeInteger(c.timestamp_us)&&c.timestamp_us>=0&&Number.isFinite(c.score)&&c.score>=0&&c.score<=1),'SEED_CANDIDATES');
      noPrivate(data);return epoch.isCurrent('query',token)?{ok:true,data:freezeDeep(data)}:apiError('STALE_RESPONSE');
    }catch(error){return apiError(error.message);}
  }
  async function startSession(request,selected_observation_id=null) {
    try {checkRequest('q2',request);need(source!==FIXTURE_ORIGIN&&origin==='LIVE','LIVE_JOB_ONLY');
      const data=parseRaw(await raw('/api/q2_start_session',{request,selected_observation_id}));
      need(data.schema_version==='q-demo.session-job.v1'&&['RUNNING','COMPLETE','FAILED','STOPPED'].includes(data.status)&&typeof data.session_id==='string','JOB_SCHEMA');
      return {ok:true,data:freezeDeep(data)};
    }catch(error){return apiError(error.message);}
  }
  async function pollSession(response_ref) {
    try {need(source!==FIXTURE_ORIGIN&&origin==='LIVE','LIVE_JOB_ONLY');const data=parseRaw(await raw('/api/q2_poll_session',{session_ref:session,response_ref}));
      need(data.schema_version==='q-demo.session-job.v1'&&data.session_id===response_ref&&['RUNNING','COMPLETE','FAILED','STOPPED'].includes(data.status),'JOB_SCHEMA');
      if(data.status==='COMPLETE'){const checked=await validateQResponse('q2',data.response);if(!checked.ok)return checked;return {ok:true,data:freezeDeep({...data,response:checked.data})};}
      return {ok:true,data:freezeDeep(data)};
    }catch(error){return apiError(error.message);}
  }
  async function stopSession(response_ref=activeJob) {
    try{need(source!==FIXTURE_ORIGIN&&origin==='LIVE'&&typeof response_ref==='string','NO_ACTIVE_JOB');
      const data=parseRaw(await raw('/api/q2_stop_session',{session_ref:session,response_ref}));
      need(data.schema_version==='q-demo.stop-receipt.v1'&&data.session_id===response_ref&&data.reason==='USER_STOPPED'&&data.provider_cancelled===null,'STOP_RECEIPT');
      need(await sha256Hex(data.decisions_jsonl)===data.decisions_sha256&&await sha256Hex(data.links_jsonl)===data.links_sha256,'STOP_JOURNAL_PIN');
      epoch.begin('query');if(activeJob===response_ref)activeJob=null;return {ok:true,data:freezeDeep(data)};
    }catch(error){return apiError(error.message);}
  }
  async function manualSeed(response_ref,observation_id,{restartAgent=false}={}) {
    try {need(source!==FIXTURE_ORIGIN&&origin==='LIVE','LIVE_JOB_ONLY');const data=parseRaw(await raw('/api/q_manual_seed',{session_ref:session,response_ref,observation_id,restart_agent:restartAgent}));
      need(data.schema_version==='q-demo.manual-selection.v1'&&data.status==='QUEUED'&&data.gt_read===false,'MANUAL_SELECTION');return {ok:true,data:freezeDeep(data)};
    }catch(error){return apiError(error.message);}
  }
  async function replay(recording_id) {
    try{need(source!==FIXTURE_ORIGIN&&['LIVE','RECORDED'].includes(origin)&&bootstrapData?.recordings.some(x=>x.recording_id===recording_id),'RECORDED_ONLY');const text=await raw('/api/q_recorded_response',{session_ref:session,recording_id});const value=parseRaw(text);const kind=value.schema_version==='q-demo.q1-response.v1'?'q1':value.schema_version==='q-demo.q2-response.v1'?'q2':'q3';const checked=await validateQResponse(kind,text);if(!checked.ok)return checked;const scope=checked.data.resolved_scope,run=bootstrapData?.runs.find(r=>r.scene_id===scope.scene_id&&scope.run_ids?.includes(r.run_id));if(run){need(scope.scene_revision===run.scene_revision,'REPLAY_SOURCE_BINDING');for(const [field,pin] of Object.entries({detection_index_sha256:run.detection_index_sha256,parameter_set_sha256:run.parameter_set_sha256,clock_mapping_sha256:run.clock_mapping?.content_sha256??null,region_graph_sha256:run.region_graph_sha256,camera_graph_sha256:run.camera_graph_sha256}))if(scope[field]!=null)need(scope[field]===pin,'REPLAY_SOURCE_BINDING');}return checked;}
    catch(error){return apiError(error.message);}
  }
  async function frames(run,timestamp_us,camera_ids) {
    try {
      if(source===FIXTURE_ORIGIN)return {ok:true,data:freezeDeep({data_origin:FIXTURE_ORIGIN,tiles:camera_ids.map(camera_id=>({camera_id,status:'MISSING',reason:'FIXTURE_HAS_NO_RGB',media_url:null}))})};
      const data=parseRaw(await raw('/api/q_frames',{session_ref:session,scene_id:run.scene_id,run_id:run.run_id,timestamp_us,camera_ids}));
      need(data.schema_version==='controlled-scene.synced-frames.v1'&&data.provenance?.gt_read===false&&data.identity_verdict==='UNCONFIRMED'&&data.resolved_scope?.scene_id===run.scene_id&&data.resolved_scope?.run_id===run.run_id,'RGB_SCOPE');
      for(const tile of data.tiles){need(camera_ids.includes(tile.camera_id),'RGB_CAMERA');if(tile.media_url)need(/^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/.test(tile.media_url),'MEDIA_URL');}
      return {ok:true,data:freezeDeep(data)};
    }catch(error){return apiError(error.message);}
  }
  async function mediaGrant(media_token) {
    try{need(source!==FIXTURE_ORIGIN,'FIXTURE_HAS_NO_RGB');const data=parseRaw(await raw('/api/q_media_grant',{session_ref:session,media_token}));const tile=data.tiles?.[0];need(tile?.status==='READY'&&/^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/.test(tile.media_url),'MEDIA_URL');return {ok:true,data:freezeDeep(data)};}
    catch(error){return apiError(error.message);}
  }
  return Object.freeze({bootstrap,createSession,query,artifact,replay,frames,mediaGrant,initialRequest,seedCandidates,startSession,pollSession,stopSession,manualSeed,activeJob:()=>activeJob,
    getSession:()=>session,getBootstrap:()=>bootstrapData,getOrigin:()=>origin,getRequests:()=>Object.freeze([...requests]),invalidate:()=>epoch.begin('query')});
}

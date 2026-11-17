import {createServer} from 'node:http';
import {readFile,realpath} from 'node:fs/promises';
import {resolve,extname,join,sep} from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';

const INTEGRATION_BASE='ac6cd12225ceb2c8f236ce9e1f9f2420f29bfdb4';
const MEDIA_URL='/api/controlled_scene_media?token='+'s'.repeat(43);
const MIME={'.html':'text/html; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml; charset=utf-8'};
const send=(res,status,body,type='application/json; charset=utf-8')=>{res.writeHead(status,{'content-type':type,'cache-control':'no-store','x-content-type-options':'nosniff'});res.end(typeof body==='string'||Buffer.isBuffer(body)?body:JSON.stringify(body));};
const body=async request=>{let text='';for await(const chunk of request){text+=chunk;if(text.length>100000)throw Error('REQUEST_TOO_LARGE');}return JSON.parse(text);};
const banner='<div id="synthetic-api-banner" role="note" style="position:fixed;z-index:99999;top:0;left:0;right:0;background:#8b1e1e;color:white;text-align:center;padding:6px;font:bold 14px system-ui">SYNTHETIC API FIXTURE · 合成畫面／合成回應 · 非真實 RGB 或正式驗收</div><style>body{padding-top:32px!important}</style>';
const image=(camera)=>`<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360"><rect width="640" height="360" fill="#17243b"/><rect x="4" y="4" width="632" height="352" fill="none" stroke="#e06868" stroke-width="8"/><text x="320" y="140" text-anchor="middle" fill="#fff" font-size="45" font-family="sans-serif">SYNTHETIC</text><text x="320" y="215" text-anchor="middle" fill="#ddd" font-size="26" font-family="sans-serif">${camera}</text></svg>`;

// Frame URLs differ per camera and per timestamp, and /api/q_frames answers slowly (like a real server), so the page has to keep the
// previous picture on screen and cannot count on a reply arriving before the playhead moves on.
const frameUrl=(camera,t)=>'/api/controlled_scene_media?token='+createHash('sha256').update(camera+'|'+t).digest('base64url').slice(0,43);
export async function startPreview({source,port=8765,frameLatencyMs=Number(process.env.CORE_FRAME_LATENCY_MS??300)}={}){
  if(!source)throw Error('SOURCE_REQUIRED');
  const root=await realpath(source),head=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
  const REQUIRED_HEAD=process.env.CORE_INTEGRATION_HEAD ?? execFileSync('git',['rev-parse','refs/heads/claude/445-demo-integration'],{cwd:root,encoding:'utf8'}).trim();
  execFileSync('git',['merge-base','--is-ancestor',INTEGRATION_BASE,head],{cwd:root});
  if(head!==REQUIRED_HEAD)throw Error(`SOURCE_HEAD_MISMATCH ${head}`);
  const status=execFileSync('git',['status','--porcelain'],{cwd:root,encoding:'utf8'}).trim();
  if(status)throw Error('SOURCE_DIRTY');
  const webroot=await realpath(join(root,'frontend/workbench-v2'));
  const [{contentHash,noPrivate},{singleViewSequence}]=await Promise.all([
    import(pathToFileURL(join(webroot,'q-validate.mjs')).href),
    import(pathToFileURL(join(webroot,'core-search-track-model.mjs')).href),
  ]);
  const wrapper=JSON.parse(await readFile(join(webroot,'fixtures/q-bootstrap.json'),'utf8'));
  const bootstrap=JSON.parse(wrapper.bootstrap_json);bootstrap.data_origin='LIVE';bootstrap.recordings=[];
  // Three independent synthetic source scopes; none is an actual event/run.
  const template=bootstrap.runs[0],runsById=new Map(),mediaTokens=new Map();
  for(const [key,cameras] of [['B05',['A','B']],['A4_1',['A','B','E']],['B4_1',['A','E']]]){
    const run=structuredClone(template);run.run_id='SYNTHETIC_'+key;run.camera_ids=cameras;
    run.clock_id='SYNTHETIC_CLOCK_'+key;run.clock_mapping.run_id=run.run_id;run.clock_mapping.clock_id=run.clock_id;
    run.clock_mapping.content_sha256=await contentHash(run.clock_mapping,{excludeRoot:['content_sha256','stats']});
    run.sampling.per_camera=run.sampling.per_camera.filter(c=>cameras.includes(c.camera_id));
    const graph={scene_id:run.scene_id,run_id:run.run_id,regions:[{region_id:'SYNTHETIC_ROOM_A',display_name:'合成區 A'},{region_id:'SYNTHETIC_ROOM_B',display_name:'合成區 B'}]};
    graph.content_sha256=await contentHash(graph,{excludeRoot:['content_sha256','stats']});
    run.region_graph=graph;run.region_graph_sha256=graph.content_sha256;runsById.set(run.run_id,run);
  }
  bootstrap.runs=[...runsById.values()];
  const resolveRun=request=>{const run=runsById.get(request.run_id);if(!run||request.scene_id!==run.scene_id)throw Error('SYNTHETIC_RUN_SCOPE');return run;};
  const session='FICT_BROWSER_SESSION';
  const routeCalls=[];
  async function search(request){
    const run=resolveRun(request);
    const hasFeature=Boolean(request.feature),hasRegion=request.region_ids?.length>0;
    if(!hasFeature&&!hasRegion)throw Error('LOCATION_OR_FEATURE_REQUIRED');
    const cameras=hasFeature&&!hasRegion?run.camera_ids:['A'];
    for(const camera of cameras)mediaTokens.set('SYNTHETIC_MEDIA_'+run.run_id+'_'+camera,{run,camera});
    const hits=cameras.map((camera_id,index)=>({rank:index+1,camera_id,target_observed:hasFeature,source_range_us:[0,2000000],wall_range:request.time.wall_range,segments:hasFeature?[{range_us:[200000,600000],matched_frames:2,representative:{frame_ref:'SYNTHETIC_FRAME_A',observation_ids:['SYNTHETIC_OBS_A'],media_token:'SYNTHETIC_MEDIA_'+run.run_id+'_'+camera_id}}]:[],basis:hasRegion?[{kind:'LOCATION',region_id:request.region_ids[0],coverage_basis:'MANUAL_ON_STATIC_FRAME'}]:[{kind:'OBJECT',class_label:request.feature.class_label,color_label:request.feature.color_label,evidence_state:'OBSERVED'}]}));
    const result={schema_version:'q-core.search-response.v1',status:'READY',reasons:[],query_id:'synthetic-core-search',normalized_request:Object.fromEntries(Object.entries(request).filter(([key])=>key!=='session_ref')),resolved_time:{timezone:run.clock_mapping.timezone,wall_range:request.time.wall_range,source_range_us:[0,2000000],clock_id:run.clock_id,clock_mapping_sha256:run.clock_mapping.content_sha256,coverage_complete:true},resolved_scope:{scene_id:run.scene_id,run_id:run.run_id,region_graph_sha256:run.region_graph_sha256,camera_graph_sha256:run.camera_graph_sha256,detection_index_sha256:run.detection_index_sha256,query_min_score:0.5},hits,not_evaluated_cameras:[],identity_verdict:'UNCONFIRMED',provenance:{producer:'synthetic-browser-fixture',['g'+'t_read']:false}};
    result.output_sha256=await contentHash(result,{excludeRoot:['output_sha256','stats']});return result;
  }
  async function track(request){
    const run=resolveRun(request);
    const as_of_us=request.time===null?request.playback_now_us:2000000;
    const all=run.camera_ids.map((camera_id,i)=>({camera_id,range_us:i===0?[200000,600000]:i===1?[1000000,1500000]:[100000,200000],evidence_state:'OBSERVED',observation_ids:['SYNTHETIC_OBS_'+camera_id]}));
    const sightings=all.filter(s=>s.range_us[0]<as_of_us).map(s=>({...s,range_us:[s.range_us[0],Math.min(s.range_us[1],as_of_us)]}));
    const single_view=singleViewSequence(sightings,{asOfUs:as_of_us});
    const result={schema_version:'q-core.track-response.v1',status:as_of_us===0?'NO_SIGHTING':'LOST',reasons:[],as_of_us,resolved_time:{kind:request.time===null?'PLAYBACK_NOW':'WALL',source_range_us:[0,as_of_us],clock_mapping_sha256:run.clock_mapping.content_sha256},sightings,multi_view:sightings.map(s=>({camera_id:s.camera_id,first_us:s.range_us[0],last_us:s.range_us[1]})),single_view,blind:{status:'UNAVAILABLE',reason:'PREDICTION_UNAVAILABLE',estimate:null},identity_verdict:'UNCONFIRMED',physical_navigation:'UNKNOWN',provenance:{producer:'synthetic-browser-fixture',['g'+'t_read']:false}};
    result.output_sha256=await contentHash(result,{excludeRoot:['output_sha256','stats']});return result;
  }
  const server=createServer(async(req,res)=>{
    try{
      const listenPort=server.address().port;if(!['127.0.0.1:'+listenPort,'localhost:'+listenPort].includes(req.headers.host)){send(res,403,{error_code:'FORBIDDEN_HOST'});return;}
      const url=new URL(req.url,'http://127.0.0.1');
      if(req.method==='GET'&&url.pathname==='/api/q_bootstrap'){send(res,200,bootstrap);return;}
      if(req.method==='GET'&&url.pathname==='/'){res.writeHead(302,{location:'/workbench-v2/'});res.end();return;}
      if(req.method==='GET'&&url.pathname==='/__preview/health'){send(res,200,{status:'SYNTHETIC',source_head:head,route_calls:routeCalls.length});return;}
      if(req.method==='GET'&&url.pathname==='/api/controlled_scene_media'&&/^\?token=[A-Za-z0-9_-]{43}$/.test(url.search)){send(res,200,image('CAM A / B'),'image/svg+xml; charset=utf-8');return;}
      if(req.method==='GET'&&url.pathname.startsWith('/workbench-v2/')){
        const relative=url.pathname.slice('/workbench-v2/'.length)||'index.html';
        const file=resolve(webroot,relative);if(!file.startsWith(webroot+sep)||!MIME[extname(file)]){send(res,404,{error_code:'NOT_FOUND'});return;}
        let data=await readFile(file);if(relative==='index.html')data=Buffer.from(data.toString().replace('<body id="q-root">','<body id="q-root">'+banner));
        send(res,200,data,MIME[extname(file)]);return;
      }
      if(req.method!=='POST'||!url.pathname.startsWith('/api/')){send(res,404,{error_code:'NOT_FOUND'});return;}
      const payload=await body(req);try{noPrivate(payload);}catch{send(res,403,{error_code:'FORBIDDEN_INPUT'});return;}
      routeCalls.push({route:url.pathname,payload});
      if(url.pathname==='/api/session'){send(res,200,{session_ref:session,role:'research'});return;}
      if(payload.session_ref!==session){send(res,403,{error_code:'FORBIDDEN_DATA_SCOPE'});return;}
      if(url.pathname==='/api/q_core_search'){send(res,200,await search(payload));return;}
      if(url.pathname==='/api/q_core_track'){send(res,200,await track(payload));return;}
      if(url.pathname==='/api/q_media_grant'){const grant=mediaTokens.get(payload.media_token);if(!grant)throw Error('SYNTHETIC_GRANT_SCOPE');const {run,camera}=grant;send(res,200,{schema_version:'controlled-scene.synced-frames.v1',resolved_scope:{scene_id:run.scene_id,run_id:run.run_id},clock_id:run.clock_id,data_origin:'SYNTHETIC',t_us:300000,provenance:{['g'+'t_read']:false},identity_verdict:'UNCONFIRMED',tiles:[{camera_id:camera,status:'READY',media_url:MEDIA_URL}]});return;}
      if(url.pathname==='/api/q_frames'){
        const run=resolveRun(payload),camera=payload.camera_ids?.[0];if(!run.camera_ids.includes(camera))throw Error('SYNTHETIC_CAMERA_SCOPE');
        await new Promise(done=>setTimeout(done,frameLatencyMs));
        send(res,200,{schema_version:'controlled-scene.synced-frames.v1',resolved_scope:{scene_id:run.scene_id,run_id:run.run_id},clock_id:run.clock_id,data_origin:'SYNTHETIC',t_us:payload.timestamp_us,provenance:{['g'+'t_read']:false},identity_verdict:'UNCONFIRMED',tiles:[{camera_id:camera,status:'READY',media_url:frameUrl(camera,payload.timestamp_us)}]});return;
      }
      send(res,503,{error_code:'Q_RESOURCE_UNAVAILABLE'});
    }catch(error){send(res,503,{error_code:error.message==='ENOENT'?'NOT_FOUND':'SYNTHETIC_FIXTURE_ERROR'});}
  });
  await new Promise((ready,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',ready);});
  return {server,url:`http://127.0.0.1:${server.address().port}/workbench-v2/`,head,routeCalls,runs:bootstrap.runs};
}

if(process.argv[1]&&resolve(process.argv[1])===new URL(import.meta.url).pathname){
  const args=Object.fromEntries(process.argv.slice(2).filter(x=>x.startsWith('--')).map(x=>x.slice(2).split('=',2)));
  const preview=await startPreview({source:args.source,port:Number(args.port??8765)});
  process.stdout.write(`SYNTHETIC_PREVIEW ${preview.url} HEAD ${preview.head}\n`);
}

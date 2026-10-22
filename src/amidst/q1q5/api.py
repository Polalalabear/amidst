"""Q-line route adapter for the existing same-origin workbench, never a server.

The server owns registry pins, session authorization and run bindings. Query
payloads cannot select files or inference inputs. Recorded playback preserves
original domain response bytes/hashes and uses separate, authorized RGB grants.
"""
from copy import deepcopy
from dataclasses import dataclass,replace
from datetime import datetime,UTC
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import threading

from amidst.q1q5.store import canonical_hash,_json,_safe_content

POST_ROUTES=frozenset({'q1_camera_search','q3_parse','q2_session','q2_start_session','q2_poll_session','q2_seed_candidates','q2_select_seed','q2_artifact','q_media_grant','q_frames','q_record_response','q_recorded_response','q_manual_seed'})
GET_ROUTES=frozenset({'q_bootstrap'})
ROUTES=POST_ROUTES|GET_ROUTES
Q_STATIC_FILES=frozenset({
    'q-api.mjs','q-validate.mjs','q-time.mjs','q-tokens.mjs','q1-wall-model.mjs','q1-wall-view.mjs',
    'q3-bar-model.mjs','q3-bar-view.mjs','provenance-bar.mjs','q2-session-model.mjs','q2-view.mjs',
    'q2-timeline-model.mjs','q2-timeline-view.mjs','q4-evidence-view.mjs','q5-log-model.mjs','q5-log-view.mjs',
    'review/review-model.mjs','review/review-view.mjs','review/fixtures/expectations.synthetic.json',
    *('fixtures/'+name+'.json' for name in ['q-bootstrap','q1-ready','q1-partial','q1-no-match','q1-out-of-range',
        'q3-parsed','q3-clarification','q3-unsupported','q3-failed','q2-rule','q2-agent','q2-no-support'])})
Q_STATIC_PATHS=frozenset('/workbench-v2/'+name for name in Q_STATIC_FILES)


def static_response(repo,path):
    from amidst.workbench.product_bridge import BinaryResponse
    check(path in Q_STATIC_PATHS,'FORBIDDEN_DATA_SCOPE',403)
    source=Path(repo).resolve()/'frontend/workbench-v2'/path.removeprefix('/workbench-v2/')
    try:raw=regular(source,16777216)
    except (FileNotFoundError,OSError):return BinaryResponse(404,'application/json',(),raw_json({'error_code':'Q_ASSET_NOT_MATERIALIZED'}))
    return BinaryResponse(200,'text/javascript' if path.endswith('.mjs') else 'application/json',(),raw)



class APIError(ValueError):
    def __init__(self,code,status=422):self.code=code;self.status=status;super().__init__(code)


def check(ok,code='FORBIDDEN_INFERENCE_INPUT',status=422):
    if not ok:raise APIError(code,status)


def raw_json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()


def regular(path,maximum):
    path=Path(path)
    check(path.is_absolute() and path.resolve()==path,'DataIntegrityError',409)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd);check(stat.S_ISREG(info.st_mode) and info.st_size<=maximum,'DataIntegrityError',409)
        data=b''
        while len(data)<=maximum:
            chunk=os.read(fd,min(65536,maximum+1-len(data)))
            if not chunk:break
            data+=chunk
        check(len(data)==info.st_size and len(data)<=maximum,'DataIntegrityError',409);return data
    finally:os.close(fd)


@dataclass(frozen=True)
class QRun:
    bindings: object
    aliases: dict
    aliases_sha256: str
    catalog: dict
    parse_settings: object
    q3_options: dict
    agent_factory: object | None
    source_kind: str


class RecordingStore:
    """Explicit private root, append-only files, trusted load pins, no discovery."""
    def __init__(self,root,*,repo_root,max_bytes):
        self.root=Path(root);self.repo=Path(repo_root).resolve();self.max_bytes=max_bytes
        check(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir()
            and not self.root.is_relative_to(self.repo),'DataIntegrityError',409)
        check(type(max_bytes) is int and max_bytes>0,'DataIntegrityError',409)
    def save(self,bundle):
        import shutil
        check(shutil.disk_usage(self.root).free>=8*1024**3,'DISK_SPACE_BELOW_8_GIB',503)
        data=deepcopy(bundle);data['schema_version']='q-demo.api-recording.v1';data['data_origin']='RECORDED'
        data['recorded_at']=datetime.now(UTC).isoformat();data.pop('content_sha256',None);data['content_sha256']=canonical_hash(data)
        raw=raw_json(data);check(len(raw)<=self.max_bytes,'RECORDING_SIZE_LIMIT',409)
        name=secrets.token_hex(16)+'.json';target=self.root/name
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb') as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
        except Exception:
            # Retain incomplete artifact for audit; never remove an existing file.
            raise
        return {'recording_id':name[:-5],'file':name,'file_sha256':sha(raw)},data
    def load(self,pin):
        check(isinstance(pin,dict) and set(pin)=={'recording_id','file','file_sha256'}
            and re.fullmatch(r'[0-9a-f]{32}',pin['recording_id']) and pin['file']==pin['recording_id']+'.json','DataIntegrityError',409)
        raw=regular(self.root/pin['file'],self.max_bytes);check(sha(raw)==pin['file_sha256'],'DataIntegrityError',409)
        data=_json(raw);check(data.get('schema_version')=='q-demo.api-recording.v1' and data.get('data_origin')=='RECORDED'
            and data.get('content_sha256')==canonical_hash(data,exclude=('content_sha256',)),'DataIntegrityError',409)
        return data


class QAPI:
    def __init__(self,runs=(),*,max_responses,max_media_refs,recording_store=None,recordings=(),rgb_api=None):
        check(type(max_responses) is int and max_responses>0 and type(max_media_refs) is int and max_media_refs>0,'DataIntegrityError',409)
        self.runs={};self.rgb_api=rgb_api;self.max_responses=max_responses;self.max_media_refs=max_media_refs
        self.recording_store=recording_store;self.recordings={};self.responses={};self.media_refs={};self._frame_refs={};self._active={};self._jobs={};self._recorded_responses={};self._lock=threading.RLock()
        for run in runs:
            m=run.bindings.index.manifest;key=(m['scene_id'],m['run_id']);check(key not in self.runs,'DataIntegrityError',409)
            check(canonical_hash(run.aliases,exclude=('content_sha256','stats'))==run.aliases_sha256
                and run.aliases['content_sha256']==run.aliases_sha256,'DataIntegrityError',409)
            check(run.parse_settings.parameter_set_sha256==run.bindings.parameter_sha256
                and run.parse_settings.parameter_set_id==run.bindings.parameter_set['parameter_set_id']
                and {x['camera_id'] for x in m['sampling']['per_camera']}<=set(run.catalog['camera_ids']),'DataIntegrityError',409)
            check(run.catalog['scene_id']==m['scene_id'] and run.catalog['run_id']==m['run_id'],'DataIntegrityError',409)
            b=run.bindings
            owned=replace(b,index=deepcopy(b.index),graphs=deepcopy(b.graphs),parameter_set=deepcopy(b.parameter_set),media_ranges_by_camera=deepcopy(b.media_ranges_by_camera))
            self.runs[key]=replace(run,bindings=owned,aliases=deepcopy(run.aliases),catalog=deepcopy(run.catalog),q3_options=dict(run.q3_options))
        for pin in recordings:
            check(recording_store is not None,'DataIntegrityError',409);data=recording_store.load(pin)
            self._verify_bundle(data);self.recordings[pin['recording_id']]=(deepcopy(pin),data)

    def bootstrap(self):
        rows=[]
        for (scene,run_id),run in sorted(self.runs.items()):
            m=run.bindings.index.manifest
            rows.append({'scene_id':scene,'run_id':run_id,'clock_id':m['clock_id'],'camera_ids':sorted(x['camera_id'] for x in m['sampling']['per_camera']),
                'detection_index_sha256':run.bindings.index_sha256,'parameter_set_id':run.bindings.parameter_set['parameter_set_id'],
                'clock_mapping':dict(run.bindings.clock.document) if run.bindings.clock else None,'source_kind':run.source_kind,
                'supported_classes_ref':'supported-classes:'+run.aliases_sha256,'supported_classes':deepcopy(run.aliases),
                'sampling':deepcopy(m['sampling']),'index_score_floor':m['detector']['index_score_floor'],
                'parameter_approval':deepcopy(run.bindings.parameter_set['approval']),
                'query_defaults':{name:getattr(run.parse_settings,name) for name in ['query_min_score','min_count_per_frame','min_verdict','page_size']},
                'agent_available':callable(run.agent_factory),'q3_llm_available':run.q3_options.get('provider') is not None})
        recorded=[{'recording_id':key,'recorded_at':data['recorded_at'],'source_kind':data['source_kind'],
            'scene_id':data['scene_id'],'run_id':data['run_id'],'response_kind':data['response']['schema_version'],'output_sha256':data['response']['output_sha256']}
            for key,(_,data) in sorted(self.recordings.items())]
        return {'schema_version':'q-demo.api-bootstrap.v1','data_origin':'RECORDED' if recorded else 'LIVE' if rows else 'UNAVAILABLE',
            'status':'AVAILABLE' if rows or recorded else 'NOT_READY','reason':None if rows or recorded else 'Q_REGISTRY_NOT_CONFIGURED',
            'runs':rows,'recordings':recorded,'default_switch_mode':'RULE_ONLY','gt_read':False,'identity_verdict':'UNCONFIRMED'}

    def _authorize(self,token,scene,authorize,*,audit=False):
        check(isinstance(token,str) and bool(token) and isinstance(scene,str) and bool(scene),'FORBIDDEN_DATA_SCOPE',403)
        try:authorize(token,scene,audit=audit)
        except Exception:raise APIError('FORBIDDEN_DATA_SCOPE',403) from None

    def _run(self,payload,authorize):
        scene=payload.get('scene_id');ids=payload.get('run_ids')
        self._authorize(payload.get('session_ref'),scene,authorize)
        check(isinstance(ids,list) and len(ids)==1 and isinstance(ids[0],str),'FORBIDDEN_DATA_SCOPE',403)
        check((scene,ids[0]) in self.runs,'Q_RUN_NOT_CONFIGURED',503);return self.runs[(scene,ids[0])]

    def _summary(self,run,oid):
        m=run.bindings.index.manifest
        for row in run.bindings.index.records:
            for o in row['detections'] or []:
                if o['observation_id']==oid:return {'observation_id':oid,'frame_ref':row['frame_ref'],'timestamp_us':row['timestamp_us'],
                    'camera_id':row['camera_id'],'class_label':o['class_label'],'bbox_xyxy_px':deepcopy(o['bbox_xyxy_px']),'score':o['score'],'color':deepcopy(o.get('color'))}
        raise APIError('FORBIDDEN_DATA_SCOPE',403)

    def _media_ref(self,token,run,frame):
        b=run.bindings;m=b.index.manifest
        rows=[r for r in b.index.records if r['frame_ref']==frame];check(len(rows)==1,'DataIntegrityError',409);row=rows[0]
        key=(token,frame,b.index_sha256)
        with self._lock:
            if key in self._frame_refs:return self._frame_refs[key]
            check(len(self.media_refs)<self.max_media_refs,'Q_MEDIA_REFERENCE_LIMIT',409)
            # This stable ID is a lookup reference, never bearer authorization.
            # Resolution requires the issuing session and a fresh scene check.
            ref='media-ref:'+canonical_hash({'frame_ref':frame,'index_sha256':b.index_sha256})
            self.media_refs[(token,ref)]={'scene_id':m['scene_id'],'run_id':m['run_id'],'clock_id':m['clock_id'],'camera_id':row['camera_id'],
                'frame_index':row['frame_index'],'timestamp_us':row['timestamp_us'],'source_rgb_sha256':row['rgb_file_sha256']}
            self._frame_refs[key]=ref;return ref

    def _bundle(self,request,response,run,result=None,*,agent_trace=None,provider_audit=()):
        obs=set()
        if result:
            obs.update(x['observation_id'] for x in result.seed_candidates)
            for segment in response['timeline']:obs.update(segment.get('observation_ids',[]))
            for e in result.evidence:
                obs.update(o['observation_id'] for o in e['best_observations'])
                if e['entry_observation_id']:obs.add(e['entry_observation_id'])
        with self._lock:
            media={ref:deepcopy(info) for (token,ref),info in self.media_refs.items() if token==request['session_ref']
                and info['scene_id']==request.get('scene_id',run.catalog['scene_id']) and info['run_id']==run.catalog['run_id']}
        return {'scene_id':run.catalog['scene_id'],'run_id':run.catalog['run_id'],'source_kind':run.source_kind,
            'request':{k:deepcopy(v) for k,v in request.items() if k!='session_ref'},'request_sha256':canonical_hash(request),'response':deepcopy(response),
            'decisions':result.decisions_bytes.decode() if result else '', 'links':result.links_bytes.decode() if result else '',
            'snapshots':list(deepcopy(result.snapshots)) if result else [],'evidence':list(deepcopy(result.evidence)) if result else [],
            'observations':{oid:self._summary(run,oid) for oid in sorted(obs)},'media_refs':media,
            'agent_trace':deepcopy(agent_trace),'q3_provider_audit':list(deepcopy(provider_audit))}

    def _verify_bundle(self,bundle):
        _safe_content(bundle);response=bundle['response']
        check(response.get('output_sha256')==canonical_hash(response,exclude=('output_sha256','stats'))
            and response.get('identity_verdict')=='UNCONFIRMED' and response.get('provenance',{}).get('gt_read') is False,'DataIntegrityError',409)
        scope=response.get('resolved_scope') or {};check(scope.get('scene_id')==bundle['scene_id'] and scope.get('run_ids')==[bundle['run_id']],'DataIntegrityError',409)
        if response['schema_version']=='q-demo.q2-response.v1':
            check(sha(bundle['decisions'].encode())==response['decisions_sha256'] and sha(bundle['links'].encode())==response['links_sha256'],'DataIntegrityError',409)
            for line in bundle['decisions'].splitlines():
                row=_json(line.encode());check(row['session_id']==response['session_id'] and row['content_sha256']==canonical_hash(row,exclude=('content_sha256','stats')),'DataIntegrityError',409)
        for evidence in bundle['evidence']:check(evidence['evidence_sha256']==canonical_hash(evidence,exclude=('evidence_sha256','stats')),'DataIntegrityError',409)
        trace=bundle.get('agent_trace')
        if trace is not None:check(trace.get('session_id')==response.get('session_id') and trace.get('content_sha256')==canonical_hash(trace,exclude=('content_sha256',)),'DataIntegrityError',409)
        for audit in bundle.get('q3_provider_audit',[]):check(audit.get('content_sha256')==canonical_hash(audit,exclude=('content_sha256','stats')),'DataIntegrityError',409)


    def _save_response(self,token,bundle):
        self._verify_bundle(bundle);ref=bundle['response'].get('session_id') or bundle['response']['output_sha256']
        key=(token,ref)
        with self._lock:
            check(key in self.responses or len(self.responses)<self.max_responses,'Q_RESPONSE_LIMIT',409)
            if key in self.responses:check(self.responses[key]['response']['output_sha256']==bundle['response']['output_sha256'],'DataIntegrityError',409)
            self.responses[key]=deepcopy(bundle)
        return ref

    def _controller(self,request,run,selected=None):
        from amidst.q1q5.q4_evidence import candidate_evidence
        from amidst.q1q5.q5_controller import RuleController
        args={'bindings':run.bindings,'evidence_provider':lambda i,s,r,c:candidate_evidence(i,s,r,**c),'selected_observation_id':selected}
        if request['switch_mode']=='AGENT_SEQUENTIAL':
            check(callable(run.agent_factory),'AGENT_ADAPTER_NOT_CONFIGURED',503);return run.agent_factory(request,**args)
        return RuleController(request,**args)

    def call(self,action,payload,authorize):
        check(action in POST_ROUTES,'FORBIDDEN_DATA_SCOPE',403);check(isinstance(payload,dict),'FORBIDDEN_INFERENCE_INPUT');_safe_content(payload)
        if action=='q3_parse':
            check(isinstance(payload.get('context'),dict),'FORBIDDEN_INFERENCE_INPUT')
            scope=payload['context'];request_scope={'session_ref':payload.get('session_ref'),'scene_id':scope.get('scene_id'),'run_ids':scope.get('run_ids')}
            run=self._run(request_scope,authorize)
            from amidst.q1q5.q3_parse import parse_query
            response,audit=parse_query(payload,catalog=run.catalog,settings=run.parse_settings,clock_mapping=run.bindings.clock,**run.q3_options)
            self._save_response(payload['session_ref'],self._bundle(payload,response,run,provider_audit=audit));return response
        if action=='q1_camera_search':
            run=self._run(payload,authorize);b=run.bindings
            from amidst.q1q5.q1_search import search_cameras
            response=search_cameras(payload,index=b.index,expected_index_sha256=b.index_sha256,aliases=run.aliases,expected_aliases_sha256=run.aliases_sha256,
                clock_mapping=b.clock,parameter_set=b.parameter_set,expected_parameter_sha256=b.parameter_sha256,
                camera_catalog_ids=run.catalog['camera_ids'],graphs=b.graphs,
                media_token_for_frame=lambda frame:self._media_ref(payload['session_ref'],run,frame))
            self._save_response(payload['session_ref'],self._bundle(payload,response,run));return response
        if action=='q2_start_session':
            check(set(payload)=={'request','selected_observation_id'} and isinstance(payload['request'],dict)
                and (payload['selected_observation_id'] is None or isinstance(payload['selected_observation_id'],str)))
            request=payload['request'];run=self._run(request,authorize);controller=self._controller(request,run,payload['selected_observation_id'])
            key=(request['session_ref'],controller.session_id)
            with self._lock:
                if key in self.responses:
                    return {'schema_version':'q-demo.session-job.v1','session_id':controller.session_id,'status':'COMPLETE','response':deepcopy(self.responses[key]['response']),'error_code':None}
                if key in self._jobs:return deepcopy(self._jobs[key]['public'])
                check(not self._active and len(self._jobs)<self.max_responses,'Q_JOB_LIMIT',409)
                public={'schema_version':'q-demo.session-job.v1','session_id':controller.session_id,'status':'RUNNING','response':None,'error_code':None}
                self._jobs[key]={'scene_id':request['scene_id'],'public':public};self._active[key]=controller
                def execute():
                    try:
                        result=controller.run();bundle=self._bundle(request,result.response,run,result,agent_trace=controller.trace() if hasattr(controller,'trace') else None)
                        self._save_response(request['session_ref'],bundle)
                        with self._lock:self._jobs[key]['public'].update(status='COMPLETE',response=deepcopy(result.response))
                    except Exception:
                        with self._lock:self._jobs[key]['public'].update(status='FAILED',error_code='Q_SESSION_FAILED')
                    finally:
                        with self._lock:self._active.pop(key,None)
                threading.Thread(target=execute,name='q-session-worker',daemon=True).start()
                return deepcopy(public)
        if action=='q2_poll_session':
            check(set(payload)=={'session_ref','response_ref'} and isinstance(payload['response_ref'],str))
            with self._lock:
                entry=self._jobs.get((payload['session_ref'],payload['response_ref']));check(entry is not None,'FORBIDDEN_DATA_SCOPE',403)
                self._authorize(payload['session_ref'],entry['scene_id'],authorize);return deepcopy(entry['public'])
        if action in {'q2_session','q2_seed_candidates','q2_select_seed'}:
            selected=None
            if action=='q2_select_seed':
                check(set(payload)=={'request','selected_observation_id'} and isinstance(payload['request'],dict) and isinstance(payload['selected_observation_id'],str))
                selected=payload['selected_observation_id'];payload=payload['request']
            run=self._run(payload,authorize);controller=self._controller(payload,run,selected)
            if action=='q2_seed_candidates':
                reason=controller._prepare()
                if reason is None:controller._seed_candidates()
                return {'schema_version':'q-demo.seed-candidates.v1','status':'CHOICE_REQUIRED' if len(controller.seeds)>1 else 'AVAILABLE' if controller.seeds else 'UNAVAILABLE',
                    'reason':reason,'request_sha256':canonical_hash(payload),'candidates':deepcopy(controller.seeds),'gt_read':False,'identity_verdict':'UNCONFIRMED'}
            key=(payload['session_ref'],controller.session_id)
            with self._lock:
                if key in self.responses:return deepcopy(self.responses[key]['response'])
                check(key not in self._active,'Q_SESSION_RUNNING',409);self._active[key]=controller
            try:result=controller.run()
            finally:
                with self._lock:self._active.pop(key,None)
            bundle=self._bundle(payload,result.response,run,result,agent_trace=controller.trace() if hasattr(controller,'trace') else None);self._save_response(payload['session_ref'],bundle);return deepcopy(result.response)
        if action=='q_recorded_response':
            check(set(payload)=={'session_ref','recording_id'} and isinstance(payload['recording_id'],str));entry=self.recordings.get(payload['recording_id'])
            check(entry is not None,'FORBIDDEN_DATA_SCOPE',403);_,bundle=entry
            self._authorize(payload['session_ref'],bundle['scene_id'],authorize);self._verify_bundle(bundle)
            with self._lock:
                for ref,info in bundle['media_refs'].items():
                    check(len(self.media_refs)<self.max_media_refs or (payload['session_ref'],ref) in self.media_refs,'Q_MEDIA_REFERENCE_LIMIT',409)
                    self.media_refs[(payload['session_ref'],ref)]=deepcopy(info)
            self._save_response(payload['session_ref'],bundle);return deepcopy(bundle['response'])
        if action in {'q2_artifact','q_record_response','q_manual_seed'}:
            fields={'session_ref','response_ref'}|({'kind','ref'} if action=='q2_artifact' else {'observation_id'} if action=='q_manual_seed' else set())
            check(set(payload)==fields and isinstance(payload['response_ref'],str));key=(payload['session_ref'],payload['response_ref'])
            if action=='q_manual_seed':
                with self._lock:controller=self._active.get(key)
                check(controller is not None,'Q_SESSION_NOT_RUNNING',409)
                self._authorize(payload['session_ref'],controller.request['scene_id'],authorize);controller.request_manual_seed(payload['observation_id'])
                return {'schema_version':'q-demo.manual-selection.v1','status':'QUEUED','gt_read':False}
            bundle=self.responses.get(key);check(bundle is not None,'FORBIDDEN_DATA_SCOPE',403);self._authorize(payload['session_ref'],bundle['scene_id'],authorize,audit=action=='q_record_response' or payload.get('kind')!='observation')
            if action=='q_record_response':
                check(self.recording_store is not None,'Q_RECORDING_NOT_CONFIGURED',503)
                with self._lock:
                    if key in self._recorded_responses:pin,data=self._recorded_responses[key]
                    else:
                        check(len(self.recordings)<self.max_responses,'Q_RECORDING_LIMIT',409)
                        pin,data=self.recording_store.save(bundle);self.recordings[pin['recording_id']]=(pin,data);self._recorded_responses[key]=(pin,data)
                return {'schema_version':'q-demo.recording-receipt.v1',**pin,'recorded_at':data['recorded_at'],'response_sha256':bundle['response']['output_sha256'],'gt_read':False}
            kind=payload['kind'];ref=payload['ref'];response=bundle['response']
            check(isinstance(kind,str) and isinstance(ref,str),'FORBIDDEN_INFERENCE_INPUT')
            if kind in {'decisions','links'}:
                check(ref==response.get(kind+'_ref'),'FORBIDDEN_DATA_SCOPE',403)
                return {'schema_version':'q-demo.journal.v1','kind':kind,'file_sha256':sha(bundle[kind].encode()),'jsonl':bundle[kind]}
            if kind=='observation':
                check(ref in bundle['observations'],'FORBIDDEN_DATA_SCOPE',403);return deepcopy(bundle['observations'][ref])
            values=bundle['snapshots'] if kind=='snapshot' else bundle['evidence'] if kind=='evidence' else []
            match=[x for x in values if x.get('candidate_snapshot_sha256' if kind=='snapshot' else 'evidence_sha256')==ref]
            check(len(match)==1,'FORBIDDEN_DATA_SCOPE',403);return deepcopy(match[0])
        if action=='q_media_grant':
            check(set(payload)=={'session_ref','media_token'} and isinstance(payload['media_token'],str));info=self.media_refs.get((payload['session_ref'],payload['media_token']))
            check(info is not None,'FORBIDDEN_DATA_SCOPE',403);self._authorize(payload['session_ref'],info['scene_id'],authorize)
            return self._frames(payload['session_ref'],info['scene_id'],info['run_id'],info['timestamp_us'],[info['camera_id']],expected=info)
        if action=='q_frames':
            check(set(payload)=={'session_ref','scene_id','run_id','timestamp_us','camera_ids'});self._authorize(payload['session_ref'],payload['scene_id'],authorize)
            run=self.runs.get((payload['scene_id'],payload['run_id']));check(run is not None,'Q_RUN_NOT_CONFIGURED',503)
            check(isinstance(payload['camera_ids'],list) and payload['camera_ids'] and all(isinstance(x,str) for x in payload['camera_ids'])
                and set(payload['camera_ids'])<={x['camera_id'] for x in run.bindings.index.manifest['sampling']['per_camera']},'FORBIDDEN_DATA_SCOPE',403)
            return self._frames(payload['session_ref'],payload['scene_id'],payload['run_id'],payload['timestamp_us'],payload['camera_ids'])
        raise APIError('FORBIDDEN_DATA_SCOPE',403)

    def _frames(self,token,scene,run_id,timestamp,cameras,expected=None):
        check(type(timestamp) is int and timestamp>=0);check(self.rgb_api is not None,'Q_RGB_NOT_CONFIGURED',503)
        result=self.rgb_api.call('synced_frames',{'schema_version':'controlled-scene.synced-frames-request.v1','session_ref':token,'scene_id':scene,
            'run_id':run_id,'t_s':timestamp/1000000,'camera_ids':cameras})
        check(result['resolved_scope']['scene_id']==scene and result['resolved_scope']['run_id']==run_id,'DataIntegrityError',409)
        live=self.runs.get((scene,run_id))
        if live is not None:
            m=live.bindings.index.manifest
            check(result['clock_id']==m['clock_id'] and len(result['tiles'])==len(cameras)
                and {tile['camera_id'] for tile in result['tiles']}==set(cameras),'DataIntegrityError',409)
            metadata={x['camera_id']:x for x in m['sampling']['per_camera']}
            for tile in result['tiles']:
                if tile.get('status')!='READY':continue
                camera=tile['camera_id'];check(camera in metadata,'Q_FRAME_NOT_INDEX_BOUND',503)
                frame=timestamp//metadata[camera]['source_frame_interval_us']
                rows=[row for row in live.bindings.index.records if row['camera_id']==camera and row['frame_index']==frame]
                check(len(rows)==1 and tile['frame_index']==frame and tile['file_sha256']==rows[0]['rgb_file_sha256'],'DataIntegrityError',409)
        if expected:
            check(result['clock_id']==expected['clock_id'] and len(result['tiles'])==1,'DataIntegrityError',409);tile=result['tiles'][0]
            check(tile.get('status')=='READY' and tile['camera_id']==expected['camera_id'] and tile['frame_index']==expected['frame_index']
                and tile['file_sha256']==expected['source_rgb_sha256'],'DataIntegrityError',409)
        return result

    def dispatch(self,environ,authorize):
        """Existing Application already validates the loopback Host header."""
        from amidst.workbench.product_bridge import BinaryResponse
        status=200
        try:
            host=environ.get('HTTP_HOST','');origin=environ.get('HTTP_ORIGIN')
            check(origin in {None,'http://'+host} and environ.get('HTTP_SEC_FETCH_SITE')!='cross-site','FORBIDDEN_DATA_SCOPE',403)
            action=environ.get('PATH_INFO','').removeprefix('/api/');method=environ.get('REQUEST_METHOD')
            check(not environ.get('QUERY_STRING'),'FORBIDDEN_INFERENCE_INPUT')
            if method=='GET' and action=='q_bootstrap':data=self.bootstrap()
            else:
                check(method=='POST' and action in POST_ROUTES,'FORBIDDEN_DATA_SCOPE',403)
                check(environ.get('CONTENT_TYPE','').split(';')[0]=='application/json','FORBIDDEN_INFERENCE_INPUT')
                length=int(environ.get('CONTENT_LENGTH','0'));check(0<length<=65536,'FORBIDDEN_INFERENCE_INPUT')
                raw=environ['wsgi.input'].read(length);check(len(raw)==length,'FORBIDDEN_INFERENCE_INPUT')
                try:payload=_json(raw)
                except ValueError:raise APIError('FORBIDDEN_INFERENCE_INPUT',422) from None
                data=self.call(action,payload,authorize)
            body=raw_json(data)
        except APIError as error:status=error.status;body=raw_json({'error_code':error.code})
        except (ValueError,TypeError,KeyError,AttributeError) as error:
            code=getattr(error,'code','FORBIDDEN_INFERENCE_INPUT')
            status=403 if code=='FORBIDDEN_DATA_SCOPE' else 409 if code=='DataIntegrityError' else 422
            body=raw_json({'error_code':code if code in {'FORBIDDEN_DATA_SCOPE','DataIntegrityError','FORBIDDEN_INFERENCE_INPUT'} else 'FORBIDDEN_INFERENCE_INPUT'})
        except (OSError,RuntimeError):status=503;body=raw_json({'error_code':'Q_RESOURCE_UNAVAILABLE'})
        return BinaryResponse(status,'application/json; charset=utf-8',(),body)


def from_environment(rgb_api,repo_root):
    """An absent registry is NOT_READY, never an implicit synthetic fallback.

    Private configuration is pinned by a separately supplied file hash. All
    inference documents then pass through the existing read-only JsonRunStore.
    No directories, model downloads, rendering or dataset discovery occur here.
    """
    path=os.environ.get('AMIDST_Q1Q5_REGISTRY');pin=os.environ.get('AMIDST_Q1Q5_REGISTRY_SHA256')
    if not path and not pin:return QAPI(max_responses=128,max_media_refs=4096,rgb_api=rgb_api)
    check(path and pin and re.fullmatch(r'[0-9a-f]{64}',pin),'DataIntegrityError',409)
    raw=regular(Path(path),16777216);check(sha(raw)==pin,'DataIntegrityError',409);config=_json(raw)
    fields={'schema_version','data_root','documents','runs','recording_root','recordings','limits','content_sha256'}
    check(set(config)==fields and config['schema_version']=='q-demo.api-registry.v1'
        and config['content_sha256']==canonical_hash(config,exclude=('content_sha256',)),'DataIntegrityError',409)
    from amidst.q1q5.store import JsonRunStore,DocumentPin
    from amidst.q1q5.clock_mapping import ClockMapping
    from amidst.q1q5.graphs import load_graphs
    from amidst.q1q5.q3_parse import ParseSettings
    from amidst.q1q5.q5_controller import RuntimeBindings
    store=JsonRunStore(Path(config['data_root']),{ref:DocumentPin(**value) for ref,value in config['documents'].items()})
    runs=[]
    for item in config['runs']:
        check(set(item)=={'index_ref','clock_ref','region_ref','camera_ref','parameter_ref','aliases_ref','catalog_ref','parse_settings','media_ranges_by_camera','media_scope_sha256','source_kind'},'DataIntegrityError',409)
        index=store.load_detection_index(item['index_ref']);clock=ClockMapping(store.load_document(item['clock_ref']))
        r=store.load_document(item['region_ref']);c=store.load_document(item['camera_ref']);graphs=load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'])
        ps=store.load_document(item['parameter_ref']);aliases=store.load_document(item['aliases_ref']);catalog_doc=store.load_document(item['catalog_ref'])
        check(catalog_doc.get('schema_version')=='q-demo.parse-catalog.v1','DataIntegrityError',409);catalog={k:v for k,v in catalog_doc.items() if k not in {'schema_version','content_sha256'}}
        b=RuntimeBindings(index,index.manifest['content_sha256'],graphs,r['content_sha256'],c['content_sha256'],clock,clock.content_sha256,ps,ps['content_sha256'],item['media_ranges_by_camera'],item['media_scope_sha256'])
        runs.append(QRun(b,aliases,aliases['content_sha256'],catalog,ParseSettings(**item['parse_settings']),{},None,item['source_kind']))
    limits=config['limits'];check(set(limits)=={'max_responses','max_media_refs','max_recording_bytes'},'DataIntegrityError',409)
    recordings=RecordingStore(config['recording_root'],repo_root=repo_root,max_bytes=limits['max_recording_bytes']) if config['recording_root'] is not None else None
    return QAPI(runs,max_responses=limits['max_responses'],max_media_refs=limits['max_media_refs'],recording_store=recordings,recordings=config['recordings'],rgb_api=rgb_api)

"""Q API adapter tests; mechanical SYNTHETIC inputs, no network or formal labels."""
from copy import deepcopy
from dataclasses import replace
import io,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from amidst.q1q5.api import QAPI,QRun,RecordingStore,APIError,raw_json,sha,from_environment
from amidst.q1q5.q3_parse import ParseSettings
from amidst.q1q5.store import canonical_hash
from test_q5_controller import fixture,seal_parameters,request as q2_request,seed_id
from test_q1_search import aliases,request as q1_request
from test_q5_agent import bindings as agent_bindings,settings as agent_settings,PolicyProvider,auto

TOKEN='SYNTHETIC_SESSION_A';OTHER='SYNTHETIC_SESSION_B'


def authorize(token,scene,*,audit=False):
    if token not in {TOKEN,OTHER} or scene!='SYNTHETIC_SCENE':raise ValueError('denied')


def run_binding(b=None,agent=False):
    b=b or (agent_bindings() if agent else fixture());p=deepcopy(b.parameter_set)
    p['parameters'] += [{'name':k,'value':v,'unit':'SYNTHETIC','status':'APPROVED','proposed_by':'SYNTHETIC','proposal_ref':'synthetic://test'} for k,v in [('q3_max_llm_attempts',2),('q3_llm_timeout_ms',2000)]]
    p['parameters'].append({'name':'segment_merge_gap_us','value':0,'unit':'us','status':'APPROVED','proposed_by':'SYNTHETIC','proposal_ref':'synthetic://test'})
    seal_parameters(p);b=replace(b,parameter_set=p,parameter_sha256=p['content_sha256'])
    a=aliases(b.index);catalog={'scene_id':'SYNTHETIC_SCENE','scene_revision':'rSYN','run_id':b.clock.run_id,
        'class_labels':['person','car'],'color_labels':['red','blue'],'camera_ids':['A','B'],'region_ids':['R1','R2'],
        'class_aliases':{'人':'person','車':'car'},'color_aliases':{'紅':'red','藍':'blue'},'camera_aliases':{'A':'A','B':'B'},'region_aliases':{'R1':'R1','R2':'R2'},'class_map_sha256':a['class_map_sha256']}
    factory=None
    if agent:
        from amidst.q1q5.q5_agent import AgentController
        provider=PolicyProvider(auto)
        factory=lambda q,**args:AgentController(q,**args,provider=provider,agent_settings=agent_settings(),round_scheduler=lambda *x:None,clock=lambda:0)
    return QRun(b,a,a['content_sha256'],catalog,ParseSettings(.5,1,'STRONG',20,'RULE_ONLY',p['parameter_set_id'],p['content_sha256'],2,2000),{},factory,'SYNTHETIC')


def q1(run,token=TOKEN):
    q=q1_request();q.update(session_ref=token,run_ids=[run.bindings.clock.run_id]);q['time']={'kind':'SOURCE','run_id':run.bindings.clock.run_id,'range_us':[0,2000000]};return q


def q2(run,token=TOKEN):
    q=q2_request(run.bindings);q['session_ref']=token;return q


def api_fixture(tmp_path=None,agent=False,**kwargs):
    run=run_binding(agent=agent);store=RecordingStore(tmp_path,repo_root=Path(__file__).parents[2],max_bytes=4000000) if tmp_path else None
    return QAPI([run],max_responses=128,max_media_refs=4096,recording_store=store,**kwargs),run


def selected(api,run):return api.call('q2_select_seed',{'request':q2(run),'selected_observation_id':seed_id(run.bindings)},authorize)


def test_unconfigured_default_is_explicit_not_ready_and_no_model_activation(monkeypatch):
    monkeypatch.delenv('AMIDST_Q1Q5_REGISTRY',raising=False);monkeypatch.delenv('AMIDST_Q1Q5_REGISTRY_SHA256',raising=False)
    api=from_environment(None,Path(__file__).parents[2]);b=api.bootstrap()
    assert b['status']=='NOT_READY' and b['data_origin']=='UNAVAILABLE' and not b['runs'] and b['default_switch_mode']=='RULE_ONLY'


def test_search_uses_stable_non_bearer_references_and_origin_invariance_across_servers():
    api,run=api_fixture();a=api.call('q1_camera_search',q1(run),authorize)
    q=q1(run);q['origin']='Q3_PARSED';b=api.call('q1_camera_search',q,authorize)
    fresh,_=api_fixture();c=fresh.call('q1_camera_search',q1(run),authorize)
    assert a==b==c and a['status']=='READY' and len(a['results'])==2
    token=a['results'][0]['matched_segments'][0]['representative']['media_token'];assert token.startswith('media-ref:')
    with pytest.raises(APIError):api.call('q_media_grant',{'session_ref':OTHER,'media_token':token},authorize)


def test_pagination_records_distinct_outputs_without_overwriting_query_id():
    api,run=api_fixture();q=q1(run);q['page_size']=1;a=api.call('q1_camera_search',q,authorize)
    q['cursor']=a['next_cursor'];b=api.call('q1_camera_search',q,authorize)
    assert a['query_id']==b['query_id'] and a['output_sha256']!=b['output_sha256'] and len(api.responses)==2


def test_seed_candidates_and_explicit_selection_do_not_auto_choose():
    api,run=api_fixture();candidates=api.call('q2_seed_candidates',q2(run),authorize)
    assert candidates['status']=='CHOICE_REQUIRED' and len(candidates['candidates'])>1 and not api.responses
    response=api.call('q2_session',q2(run),authorize);assert response['reason']=='SEED_SELECTION_REQUIRED' and response['timeline']==[]
    response=selected(api,run);assert response['status']=='COMPLETE' and response['timeline'][-1]['camera_id']=='B'


def test_immutable_session_artifacts_are_authorized_and_only_produced_refs_are_readable():
    api,run=api_fixture();r=selected(api,run);base={'session_ref':TOKEN,'response_ref':r['session_id']}
    d=api.call('q2_artifact',base|{'kind':'decisions','ref':r['decisions_ref']},authorize)
    assert sha(d['jsonl'].encode())==d['file_sha256']==r['decisions_sha256']
    first=api.responses[(TOKEN,r['session_id'])]['evidence'][0]
    assert api.call('q2_artifact',base|{'kind':'evidence','ref':first['evidence_sha256']},authorize)==first
    oid=r['timeline'][0]['observation_ids'][0]
    assert api.call('q2_artifact',base|{'kind':'observation','ref':oid},authorize)['bbox_xyxy_px']
    for bad in [base|{'kind':'evidence','ref':'foreign'},base|{'session_ref':OTHER,'kind':'decisions','ref':r['decisions_ref']},base|{'kind':'links','ref':'../../private/file'}]:
        with pytest.raises(APIError):api.call('q2_artifact',bad,authorize)
    d['jsonl']='mutated';assert api.responses[(TOKEN,r['session_id'])]['decisions']


def test_same_q2_execution_is_idempotent_and_does_not_call_agent_again():
    api,run=api_fixture(agent=True);q=q2(run);q['switch_mode']='AGENT_SEQUENTIAL';payload={'request':q,'selected_observation_id':seed_id(run.bindings)}
    a=api.call('q2_select_seed',payload,authorize);b=api.call('q2_select_seed',payload,authorize)
    assert a==b and a['agent_used'] and a['decision_source']=='AGENT'


def test_recording_is_outside_repo_append_only_and_replays_original_response_under_new_session(tmp_path):
    api,run=api_fixture(tmp_path);r=selected(api,run)
    pin=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':r['session_id']},authorize)
    path=tmp_path/pin['file'];before=path.read_bytes();assert sha(before)==pin['file_sha256']
    data=json.loads(before);assert 'session_ref' not in data['request'] and TOKEN not in before.decode()
    descriptor={k:pin[k] for k in ['recording_id','file','file_sha256']}
    replay=QAPI(max_responses=128,max_media_refs=4096,recording_store=api.recording_store,recordings=[descriptor])
    assert replay.bootstrap()['data_origin']=='RECORDED'
    played=replay.call('q_recorded_response',{'session_ref':OTHER,'recording_id':pin['recording_id']},authorize)
    assert played==r and sha(path.read_bytes())==pin['file_sha256'] and path.read_bytes()==before
    d=replay.call('q2_artifact',{'session_ref':OTHER,'response_ref':r['session_id'],'kind':'links','ref':r['links_ref']},authorize)
    assert d['file_sha256']==r['links_sha256']


def test_recording_refuses_tampered_bytes_or_self_hash_even_with_new_file_pin(tmp_path):
    api,run=api_fixture(tmp_path);r=selected(api,run);pin=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':r['session_id']},authorize)
    descriptor={k:pin[k] for k in ['recording_id','file','file_sha256']};path=tmp_path/pin['file'];data=json.loads(path.read_bytes());data['response']['status']='NO_SEED';path.write_bytes(raw_json(data))
    for descriptor in [descriptor,descriptor|{'file_sha256':sha(path.read_bytes())}]:
        with pytest.raises(APIError):QAPI(max_responses=128,max_media_refs=4096,recording_store=api.recording_store,recordings=[descriptor])


def test_recording_root_and_links_are_not_followed(tmp_path):
    with pytest.raises(APIError):RecordingStore(Path(__file__).parents[2],repo_root=Path(__file__).parents[2],max_bytes=1000)
    real=tmp_path/'real';real.mkdir();link=tmp_path/'link';link.symlink_to(real,target_is_directory=True)
    with pytest.raises(APIError):RecordingStore(link,repo_root=Path(__file__).parents[2],max_bytes=1000)


class FakeRGB:
    def __init__(self,run,corrupt=None):self.run=run;self.corrupt=corrupt;self.calls=[]
    def call(self,action,p):
        self.calls.append((action,deepcopy(p)));index=int(p['t_s']*5)
        rows=[r for r in self.run.bindings.index.records if r['camera_id'] in p['camera_ids'] and r['frame_index']==index]
        tiles=[{'status':'READY','camera_id':r['camera_id'],'frame_index':index,'file_sha256':r['rgb_file_sha256'],'media_url':'/api/controlled_scene_media?token=SYNTHETIC'} for r in rows]
        r={'schema_version':'controlled-scene.synced-frames.v1','resolved_scope':{'scene_id':p['scene_id'],'run_id':p['run_id']},'clock_id':self.run.bindings.clock.clock_id,'tiles':tiles}
        if self.corrupt=='hash':r['tiles'][0]['file_sha256']='0'*64
        if self.corrupt=='frame':r['tiles'][0]['frame_index']+=1
        if self.corrupt=='clock':r['clock_id']='foreign'
        if self.corrupt=='run':r['resolved_scope']['run_id']='foreign'
        return r


def test_media_resolution_calls_existing_rgb_adapter_and_checks_index_rgb_pin():
    api,run=api_fixture();rgb=FakeRGB(run);api.rgb_api=rgb
    r=api.call('q1_camera_search',q1(run),authorize);rep=r['results'][0]['matched_segments'][0]['representative']
    grant=api.call('q_media_grant',{'session_ref':TOKEN,'media_token':rep['media_token']},authorize)
    assert grant['tiles'][0]['media_url'].startswith('/api/controlled_scene_media?token=') and rgb.calls[0][0]=='synced_frames'
    assert rgb.calls[0][1]['session_ref']==TOKEN and rgb.calls[0][1]['run_id']==run.bindings.clock.run_id


@pytest.mark.parametrize('corrupt',['hash','frame','clock','run'])
def test_rgb_source_mismatch_fails_closed(corrupt):
    api,run=api_fixture();api.rgb_api=FakeRGB(run,corrupt)
    r=api.call('q1_camera_search',q1(run),authorize);rep=r['results'][0]['matched_segments'][0]['representative']
    with pytest.raises(APIError):api.call('q_media_grant',{'session_ref':TOKEN,'media_token':rep['media_token']},authorize)


def test_q3_is_parser_only_and_client_executes_only_parsed_result():
    api,run=api_fixture();q={'schema_version':'q-demo.q3-parse-request.v1','session_ref':TOKEN,'text':'車13:00:00到13:00:01','locale':'zh-TW',
        'context':{'scene_id':run.catalog['scene_id'],'run_ids':[run.catalog['run_id']],'clock_mapping_sha256':run.bindings.clock_sha256},'parser_mode':'RULE_ONLY'}
    r=api.call('q3_parse',q,authorize);assert r['status']=='PARSED' and r['structured_query']['schema_version']=='q-demo.q1-request.v1'
    assert len(api.responses)==1
    result=api.call('q1_camera_search',r['structured_query'],authorize);assert result['status']=='NO_MATCH' and len(api.responses)==2


@pytest.mark.parametrize('change',[{'actor_id':'forbidden'},{'session_ref':'foreign'},{'scene_id':'foreign'},{'run_ids':['foreign']},{'index_path':'/private/secret'}])
def test_client_cannot_select_hidden_inputs_or_foreign_scope(change):
    api,run=api_fixture()
    with pytest.raises((APIError,ValueError)):api.call('q1_camera_search',q1(run)|change,authorize)


def test_wsgi_existing_host_session_boundary_is_preserved(tmp_path):
    from amidst.workbench.service import Application
    api,run=api_fixture()
    workbench=SimpleNamespace(_session=lambda token:SimpleNamespace(scene_ids={'SYNTHETIC_SCENE'},role='research') if token in {TOKEN,OTHER} else (_ for _ in ()).throw(ValueError('denied')))
    app=Application(workbench,tmp_path,q_api=api)
    def call(path,payload=None,**updates):
        raw=raw_json(payload or {});env={'HTTP_HOST':'127.0.0.1:9999','SERVER_PORT':'9999','REQUEST_METHOD':'POST','PATH_INFO':path,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),'QUERY_STRING':''};env.update(updates)
        captured={};out=b''.join(app(env,lambda status,headers:captured.update(status=status,headers=dict(headers))))
        return captured,json.loads(out)
    a,r=call('/api/q1_camera_search',q1(run));assert a['status']=='200 OK' and r['status']=='READY'
    assert a['headers']['Cache-Control']=='no-store' and a['headers']['Referrer-Policy']=='no-referrer'
    for updates in [{'HTTP_HOST':'evil.example','SERVER_PORT':'80'},{'HTTP_ORIGIN':'http://evil.example'},{'HTTP_SEC_FETCH_SITE':'cross-site'}]:
        result,_=call('/api/q1_camera_search',q1(run),**updates);assert result['status'].startswith('403')
    result,r=call('/api/q1_camera_search',q1(run)|{'session_ref':'foreign'});assert result['status'].startswith('403')
    result,r=call('/api/q_bootstrap',REQUEST_METHOD='GET');assert result['status']=='200 OK' and r['default_switch_mode']=='RULE_ONLY'
    result,r=call('/api/q1_camera_search',q1(run)|{'event_script':{}});assert result['status'].startswith('422')


def test_duplicate_json_and_oversize_requests_fail_closed():
    api,_=api_fixture()
    for raw,length in [(b'{"session_ref":"a","session_ref":"b"}',35),(b'{}',65537)]:
        r=api.dispatch({'HTTP_HOST':'localhost','PATH_INFO':'/api/q1_camera_search','REQUEST_METHOD':'POST','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(length),'wsgi.input':io.BytesIO(raw)},authorize)
        assert r.status==422


def test_active_manual_selection_requires_same_session_and_does_not_rewind():
    api,run=api_fixture();calls=[]
    controller=SimpleNamespace(request={'scene_id':'SYNTHETIC_SCENE'},request_manual_seed=calls.append)
    api._active[(TOKEN,'running-SYNTHETIC')]=controller
    assert api.call('q_manual_seed',{'session_ref':TOKEN,'response_ref':'running-SYNTHETIC','observation_id':'obs-visible'},authorize)['status']=='QUEUED'
    assert calls==['obs-visible']
    with pytest.raises(APIError):api.call('q_manual_seed',{'session_ref':OTHER,'response_ref':'running-SYNTHETIC','observation_id':'obs-visible'},authorize)


def test_record_response_is_idempotent_and_records_once(tmp_path):
    api,run=api_fixture(tmp_path);r=selected(api,run);q={'session_ref':TOKEN,'response_ref':r['session_id']}
    a=api.call('q_record_response',q,authorize);b=api.call('q_record_response',q,authorize)
    assert a==b and len(list(tmp_path.glob('*.json')))==1


def test_recording_stops_below_user_disk_threshold(tmp_path,monkeypatch):
    import shutil
    monkeypatch.setattr(shutil,'disk_usage',lambda p:SimpleNamespace(free=8*1024**3-1))
    api,run=api_fixture(tmp_path);r=selected(api,run)
    with pytest.raises(APIError) as e:api.call('q_record_response',{'session_ref':TOKEN,'response_ref':r['session_id']},authorize)
    assert e.value.code=='DISK_SPACE_BELOW_8_GIB' and list(tmp_path.iterdir())==[]


def test_background_job_accepts_manual_control_while_single_http_entry_is_idle():
    import threading,time
    from amidst.q1q5.q5_agent import AgentController
    entered=threading.Event();release=threading.Event();run=run_binding(agent=True)
    def on_tick(t,c):
        if t==200000:entered.set();assert release.wait(3)
    def factory(q,**args):return AgentController(q,**args,provider=PolicyProvider(auto),agent_settings=agent_settings(),round_scheduler=lambda *args:None,clock=lambda:0,on_tick=on_tick)
    run=replace(run,agent_factory=factory);api=QAPI([run],max_responses=128,max_media_refs=4096)
    q=q2(run);q['switch_mode']='AGENT_SEQUENTIAL';job=api.call('q2_start_session',{'request':q,'selected_observation_id':seed_id(run.bindings)},authorize)
    try:
        assert entered.wait(3) and job['status']=='RUNNING'
        base={'session_ref':TOKEN,'response_ref':job['session_id']}
        assert api.call('q2_poll_session',base,authorize)['status']=='RUNNING'
        with pytest.raises(APIError):api.call('q2_poll_session',base|{'session_ref':OTHER},authorize)
        assert api.call('q_manual_seed',base|{'observation_id':seed_id(run.bindings,'B',5)},authorize)['status']=='QUEUED'
    finally:release.set()
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        result=api.call('q2_poll_session',base,authorize)
        if result['status']!='RUNNING':break
        time.sleep(.005)
    assert result['status']=='COMPLETE' and result['response']['timeline'][-1]['camera_id']=='B'
    assert not result['response']['agent_attempted'] and result['response']['timeline'][-1]['entered_by']=='USER_SELECTION'


def test_registry_loads_only_exact_pinned_safe_documents(tmp_path,monkeypatch):
    from dataclasses import asdict
    from amidst.q1q5.q5_controller import jsonl
    run=run_binding();b=run.bindings;documents={}
    def document(ref,value):
        path=tmp_path/(ref+'.json');raw=raw_json(value);path.write_bytes(raw)
        documents[ref]={'path':path.name,'file_sha256':sha(raw),'schema_version':value['schema_version'],'content_sha256':value.get('content_sha256')}
    document('index',b.index.manifest);record_path=tmp_path/b.index.manifest['records_ref'];record_path.write_bytes(jsonl(b.index.records))
    documents['records']={'path':record_path.name,'file_sha256':sha(record_path.read_bytes()),'schema_version':'q-demo.detection-record.v1'}
    for ref,value in [('clock',dict(b.clock.document)),('region',b.graphs.region),('camera',b.graphs.camera),('parameter',b.parameter_set),('aliases',run.aliases)]:document(ref,value)
    catalog={'schema_version':'q-demo.parse-catalog.v1',**run.catalog};catalog['content_sha256']=canonical_hash(catalog);document('catalog',catalog)
    config={'schema_version':'q-demo.api-registry.v1','data_root':str(tmp_path),'documents':documents,'runs':[{'index_ref':'index','clock_ref':'clock','region_ref':'region','camera_ref':'camera','parameter_ref':'parameter','aliases_ref':'aliases','catalog_ref':'catalog',
        'parse_settings':asdict(run.parse_settings),'media_ranges_by_camera':b.media_ranges_by_camera,'media_scope_sha256':b.media_scope_sha256,'source_kind':'SYNTHETIC'}],
        'recording_root':None,'recordings':[],'limits':{'max_responses':128,'max_media_refs':4096,'max_recording_bytes':4000000}}
    config['content_sha256']=canonical_hash(config);path=tmp_path/'registry.json';path.write_bytes(raw_json(config))
    monkeypatch.setenv('AMIDST_Q1Q5_REGISTRY',str(path));monkeypatch.setenv('AMIDST_Q1Q5_REGISTRY_SHA256',sha(path.read_bytes()))
    api=from_environment(None,Path(__file__).parents[2]);assert api.bootstrap()['runs'][0]['run_id']==b.clock.run_id
    assert api.call('q1_camera_search',q1(run),authorize)['status']=='READY'
    record_path.write_bytes(b'tampered')
    with pytest.raises(ValueError):from_environment(None,Path(__file__).parents[2])


def test_registry_missing_or_changed_pin_does_not_silently_fall_back(tmp_path,monkeypatch):
    path=tmp_path/'config.json';path.write_bytes(b'{}');monkeypatch.setenv('AMIDST_Q1Q5_REGISTRY',str(path))
    for pin in [None,'0'*64]:
        if pin is None:monkeypatch.delenv('AMIDST_Q1Q5_REGISTRY_SHA256',raising=False)
        else:monkeypatch.setenv('AMIDST_Q1Q5_REGISTRY_SHA256',pin)
        with pytest.raises(APIError):from_environment(None,Path(__file__).parents[2])


def test_arbitrary_frame_requests_keep_exact_camera_run_clock_and_rgb_binding():
    api,run=api_fixture();api.rgb_api=FakeRGB(run)
    q={'session_ref':TOKEN,'scene_id':run.catalog['scene_id'],'run_id':run.catalog['run_id'],'timestamp_us':1100000,'camera_ids':['B','A']}
    assert len(api.call('q_frames',q,authorize)['tiles'])==2
    api.rgb_api.corrupt='hash'
    with pytest.raises(APIError):api.call('q_frames',q,authorize)
    with pytest.raises(APIError):api.call('q_frames',q|{'camera_ids':['foreign']},authorize)


def test_recorded_q2_keeps_full_agent_trace_for_offline_reexecution(tmp_path):
    api,run=api_fixture(tmp_path,agent=True);q=q2(run);q['switch_mode']='AGENT_SEQUENTIAL'
    r=api.call('q2_select_seed',{'request':q,'selected_observation_id':seed_id(run.bindings)},authorize)
    pin=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':r['session_id']},authorize)
    saved=json.loads((tmp_path/pin['file']).read_bytes());trace=saved['agent_trace']
    assert trace['events'] and trace['events'][0]['record']['prompt']
    assert trace['content_sha256']==canonical_hash(trace,exclude=('content_sha256',))
    with pytest.raises(APIError):api.call('q2_artifact',{'session_ref':TOKEN,'response_ref':r['session_id'],'kind':'agent_trace','ref':trace['content_sha256']},authorize)


def test_recorded_replay_can_be_recorded_again_without_stale_self_hash(tmp_path):
    api,run=api_fixture(tmp_path);r=selected(api,run);pin=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':r['session_id']},authorize)
    played=api.call('q_recorded_response',{'session_ref':OTHER,'recording_id':pin['recording_id']},authorize)
    again=api.call('q_record_response',{'session_ref':OTHER,'response_ref':played['session_id']},authorize)
    assert api.recording_store.load({k:again[k] for k in ['recording_id','file','file_sha256']})['response']==r


def test_q_static_program_allowlist_never_reads_tests_arbitrary_files_or_links(tmp_path):
    from amidst.q1q5.api import Q_STATIC_PATHS,static_response
    folder=tmp_path/'frontend/workbench-v2';folder.mkdir(parents=True);(folder/'q-api.mjs').write_text('export const SYNTHETIC=true;')
    assert static_response(tmp_path,'/workbench-v2/q-api.mjs').status==200
    assert '/workbench-v2/q-api.test.mjs' not in Q_STATIC_PATHS
    for path in ['/workbench-v2/../../secret','/workbench-v2/review/answers.json','/workbench-v2/q-api.test.mjs']:
        with pytest.raises(APIError):static_response(tmp_path,path)
    (folder/'q-time.mjs').symlink_to(folder/'q-api.mjs')
    with pytest.raises(APIError):static_response(tmp_path,'/workbench-v2/q-time.mjs')


def test_research_role_is_server_checked_for_audit_even_when_mode_claims_review(tmp_path):
    from amidst.workbench.service import Application
    api,run=api_fixture();r=selected(api,run)
    app=Application(SimpleNamespace(_session=lambda token:SimpleNamespace(scene_ids={'SYNTHETIC_SCENE'},role='management')),tmp_path,q_api=api)
    payload={'session_ref':TOKEN,'response_ref':r['session_id'],'kind':'decisions','ref':r['decisions_ref']};raw=raw_json(payload)
    env={'HTTP_HOST':'127.0.0.1:9999','SERVER_PORT':'9999','REQUEST_METHOD':'POST','PATH_INFO':'/api/q2_artifact','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
    captured={};out=b''.join(app(env,lambda status,headers:captured.update(status=status)))
    assert captured['status'].startswith('403') and json.loads(out)['error_code']=='FORBIDDEN_DATA_SCOPE'


def test_bootstrap_exposes_pinned_sampling_and_explicit_query_settings_for_ui():
    api,run=api_fixture();b=api.bootstrap()['runs'][0]
    assert b['sampling']==run.bindings.index.manifest['sampling']
    assert b['query_defaults']=={'query_min_score':.5,'min_count_per_frame':1,'min_verdict':'STRONG','page_size':20}
    assert not b['agent_available'] and not b['q3_llm_available']
    b['sampling']['stride_samples']=99;assert run.bindings.index.manifest['sampling']['stride_samples']==1


def test_bootstrap_provides_full_runtime_pins_for_client_request_response_binding():
    api,run=api_fixture();b=api.bootstrap()['runs'][0]
    assert b['scene_revision']==run.bindings.index.manifest['scene_revision']
    assert b['parameter_set_sha256']==run.bindings.parameter_sha256
    assert b['region_graph_sha256']==run.bindings.region_graph_sha256
    assert b['camera_graph_sha256']==run.bindings.camera_graph_sha256
    assert b['media_scope_sha256']==run.bindings.media_scope_sha256


def test_q1_representative_observations_are_readable_only_for_the_producing_query():
    api,run=api_fixture();r=api.call('q1_camera_search',q1(run),authorize)
    oid=r['results'][0]['matched_segments'][0]['representative']['observation_ids'][0]
    q={'session_ref':TOKEN,'response_ref':r['output_sha256'],'kind':'observation','ref':oid}
    assert api.call('q2_artifact',q,authorize)['observation_id']==oid
    with pytest.raises(APIError):api.call('q2_artifact',q|{'session_ref':OTHER},authorize)


def test_live_registry_and_recordings_coexist_without_disabling_queries_or_replaying_a_provider(tmp_path):
    api,run=api_fixture(tmp_path,agent=True);original=selected(api,run)
    receipt=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':original['session_id']},authorize)
    bootstrap=api.bootstrap();assert bootstrap['data_origin']=='LIVE' and len(bootstrap['recordings'])==1
    assert api.call('q1_camera_search',q1(run),authorize)['status']=='READY'
    played=api.call('q_recorded_response',{'session_ref':OTHER,'recording_id':receipt['recording_id']},authorize)
    assert played==original and api.bootstrap()['data_origin']=='LIVE'
    journal=api.call('q2_artifact',{'session_ref':OTHER,'response_ref':original['session_id'],'kind':'decisions','ref':original['decisions_ref']},authorize)
    assert journal['file_sha256']==original['decisions_sha256']


def test_recorded_response_cannot_bind_frames_to_a_changed_live_run_with_the_same_id(tmp_path):
    api,run=api_fixture(tmp_path);r=selected(api,run)
    receipt=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':r['session_id']},authorize)
    ps=deepcopy(run.bindings.parameter_set);next(x for x in ps['parameters'] if x['name']=='segment_merge_gap_us')['value']=1000000
    seal_parameters(ps);b=replace(run.bindings,parameter_set=ps,parameter_sha256=ps['content_sha256'])
    changed=replace(run,bindings=b,parse_settings=replace(run.parse_settings,parameter_set_id=ps['parameter_set_id'],parameter_set_sha256=ps['content_sha256']))
    pin={key:receipt[key] for key in ['recording_id','file','file_sha256']}
    mixed=QAPI([changed],max_responses=128,max_media_refs=4096,recording_store=api.recording_store,recordings=[pin])
    with pytest.raises(APIError,match='DataIntegrityError'):
        mixed.call('q_recorded_response',{'session_ref':OTHER,'recording_id':pin['recording_id']},authorize)

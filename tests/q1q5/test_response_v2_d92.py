"""D92 wire, literal defaults and unchanged v1 playback; SYNTHETIC inputs only."""
import hashlib
import json
import shutil
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from test_api import OTHER, TOKEN, api_fixture, authorize, q1, q2, run_binding
from test_q3_parse import request, run
from test_q5_controller import seed_id

from amidst.contracts.q_demo import validate
from amidst.q1q5.api import APIError, QAPI, RecordingStore, raw_json
from amidst.q1q5.store import canonical_hash


def parse_request(binding, text):
    return {'schema_version':'q-demo.q3-parse-request.v1','session_ref':TOKEN,
            'text':text,'locale':'zh-TW','parser_mode':'RULE_ONLY',
            'context':{'scene_id':binding.catalog['scene_id'],'run_ids':[binding.catalog['run_id']],
                       'clock_mapping_sha256':binding.bindings.clock_sha256}}


@pytest.mark.parametrize('text,kind',[
    ('紅色的人','q1'),('那個人','q1'),('找紅衣人','q1'),
    ('跟著紅衣人','q2'),('追蹤那個人','q2'),('紅色的人去了哪裡','q2'),
])
def test_time_free_closed_sentence_uses_selected_run_and_deterministic_intent(text,kind):
    response,_=run(request(text))
    assert response['status']=='PARSED'
    assert response['structured_query']['schema_version']==f'q-demo.{kind}-request.v1'
    assert response['structured_query']['time']=={'kind':'SOURCE','run_id':'RUN_SYN','range_us':[0,30000000]}
    assert response['resolved_scope']['time_range_source']=='DEFAULT_SELECTED_RUN'
    assert response['resolved_scope']['resolved_source_ranges_us']==[{'run_id':'RUN_SYN','range_us':[0,30000000]}]
    assert response['reasons']==[] and response['reason'] is None
    assert not validate(response,'q-demo.q3-parse-response.v2')


@pytest.mark.parametrize('text',[
    '紅藍人','人車','人13:00','人2026-11-01','人現在','人25:00到26:00',
    '跟著車','跟著人哪些鏡頭','拿著物品的人','找他','色的人',
])
def test_incomplete_ambiguous_or_unsupported_sentence_never_defaults(text):
    response,_=run(request(text))
    assert response['status']!='PARSED' and response['structured_query'] is None
    assert response['resolved_scope']['time_range_source'] is None


def test_explicit_wall_time_stays_explicit_and_missing_clock_or_multi_run_cannot_default():
    response,_=run(request('紅衣人13:00:00到13:00:10'))
    assert response['structured_query']['schema_version']=='q-demo.q1-request.v1'
    assert response['resolved_scope']['time_range_source']=='EXPLICIT_WALL'
    assert response['structured_query']['time']['kind']=='WALL'
    req=request('人');req['context']['clock_mapping_sha256']=None
    missing,_=run(req,clock_mapping=None)
    assert missing['reason']=='CLOCK_MAPPING_MISSING'
    assert missing['resolved_scope']['time_range_source'] is None
    req=request('人');req['context']['run_ids'].append('OTHER_RUN')
    multi,_=run(req)
    assert multi['reason']=='MULTI_RUN_SCOPE_UNRESOLVED'
    assert multi['resolved_scope']['time_range_source'] is None


def test_q1_default_receipt_changes_only_output_provenance_not_d80_query_lineage():
    api,binding=api_fixture()
    parsed=api.call('q3_parse',parse_request(binding,'人'),authorize)
    req=parsed['structured_query']
    default=api.call('q1_camera_search',{'request':req,'parse_response_ref':parsed['output_sha256']},authorize)
    explicit=api.call('q1_camera_search',req,authorize)
    assert default['query_sha256']==explicit['query_sha256']
    assert default['query_id']==explicit['query_id']
    assert default['resolved_scope']['time_range_source']=='DEFAULT_SELECTED_RUN'
    assert explicit['resolved_scope']['time_range_source']=='EXPLICIT_SOURCE'
    assert default['output_sha256']!=explicit['output_sha256']
    assert not validate(default,'q-demo.q1-response.v2')
    assert set(req)=={'schema_version','session_ref','scene_id','run_ids','time','condition',
                      'camera_ids','region_ids','page_size','cursor','origin'}
    normalized={k:v for k,v in req.items() if k not in {'origin','cursor'}}
    b=binding.bindings
    assert default['query_sha256']==canonical_hash({'request':normalized,'bindings':{
        'index':b.index_sha256,'aliases':binding.aliases_sha256,'parameters':b.parameter_sha256,'clock':b.clock_sha256}})


def test_q2_default_receipt_survives_seed_selection_and_does_not_alias_explicit_session():
    api,binding=api_fixture()
    parsed=api.call('q3_parse',parse_request(binding,'跟著人'),authorize)
    req=parsed['structured_query']
    default=api.call('q2_select_seed',{'request':req,'selected_observation_id':seed_id(binding.bindings),
                    'parse_response_ref':parsed['output_sha256']},authorize)
    explicit=api.call('q2_select_seed',{'request':req,'selected_observation_id':seed_id(binding.bindings)},authorize)
    assert default['resolved_scope']['time_range_source']=='DEFAULT_SELECTED_RUN'
    assert explicit['resolved_scope']['time_range_source']=='EXPLICIT_SOURCE'
    assert default['session_id']!=explicit['session_id']
    assert not validate(default,'q-demo.q2-response.v2')
    bundle=api.responses[(TOKEN,default['session_id'])]
    assert hashlib.sha256(bundle['links'].encode()).hexdigest()==default['links_sha256']
    assert all(json.loads(line)['schema_version']=='q-demo.link-record.v2' for line in bundle['links'].splitlines())


@pytest.mark.parametrize('tamper',['foreign_session','changed_request','unknown_ref'])
def test_parse_provenance_requires_same_session_exact_query_and_saved_receipt(tamper):
    api,binding=api_fixture()
    parsed=api.call('q3_parse',parse_request(binding,'人'),authorize)
    req=deepcopy(parsed['structured_query']);reference=parsed['output_sha256']
    if tamper=='foreign_session':req['session_ref']=OTHER
    elif tamper=='changed_request':req['condition']['query_min_score']=.6
    else:reference='a'*64
    with pytest.raises(APIError):
        api.call('q1_camera_search',{'request':req,'parse_response_ref':reference},authorize)


@pytest.mark.parametrize('kind',['q1','q2','q3'])
@pytest.mark.parametrize('mutation',['missing_source','extra_reason','unknown_source','null_source'])
def test_v2_scope_is_closed_and_source_is_required(kind,mutation):
    api,binding=api_fixture()
    if kind=='q1':response=api.call('q1_camera_search',q1(binding),authorize)
    elif kind=='q2':response=api.call('q2_session',q2(binding),authorize)
    else:response=api.call('q3_parse',parse_request(binding,'人'),authorize)
    changed=deepcopy(response);scope=changed['resolved_scope']
    if mutation=='missing_source':del scope['time_range_source']
    elif mutation=='extra_reason':scope['time_range_reason']='DEFAULT'
    elif mutation=='unknown_source':scope['time_range_source']='INFERRED_DEFAULT'
    else:scope['time_range_source']=None
    assert validate(changed,response['schema_version'])


def test_three_original_v1_recordings_replay_without_migration_or_rehash(tmp_path):
    frozen=Path(__file__).parent/'fixtures/d92_v1_recordings'
    pins=json.loads((frozen/'pins.json').read_bytes())
    for pin in pins:shutil.copyfile(frozen/pin['file'],tmp_path/pin['file'])
    store=RecordingStore(tmp_path,repo_root=Path(__file__).parents[2],max_bytes=4000000)
    api=QAPI(max_responses=128,max_media_refs=4096,recording_store=store,recordings=pins)
    versions=set()
    for pin in pins:
        before=(tmp_path/pin['file']).read_bytes()
        assert hashlib.sha256(before).hexdigest()==pin['file_sha256']
        original=json.loads(before)['response'];versions.add(original['schema_version'])
        repeated=api.call('q_recorded_response',{'session_ref':TOKEN,'recording_id':pin['recording_id']},authorize)
        assert repeated==original and raw_json(repeated)==raw_json(original)
        assert 'time_range_source' not in repeated['resolved_scope']
        assert canonical_hash(repeated,exclude=('output_sha256','stats'))==original['output_sha256']
        assert (tmp_path/pin['file']).read_bytes()==before
    assert versions=={'q-demo.q1-response.v1','q-demo.q2-response.v1','q-demo.q3-parse-response.v1'}


def test_v2_recording_rejects_tampered_q2_journal_even_with_rehashed_response():
    api,binding=api_fixture()
    r=api.call('q2_select_seed',{'request':q2(binding),'selected_observation_id':seed_id(binding.bindings)},authorize)
    bundle=deepcopy(api.responses[(TOKEN,r['session_id'])]);bundle['links']+='{}\n'
    with pytest.raises(APIError,match='DataIntegrityError'):api._verify_bundle(bundle)


def test_default_q1_pagination_keeps_parent_receipt_and_d80_lineage():
    binding=run_binding();binding=replace(binding,parse_settings=replace(binding.parse_settings,page_size=1))
    api=QAPI([binding],max_responses=128,max_media_refs=4096)
    parsed=api.call('q3_parse',parse_request(binding,'人'),authorize)
    req=deepcopy(parsed['structured_query'])
    first=api.call('q1_camera_search',{'request':req,'parse_response_ref':parsed['output_sha256']},authorize)
    assert first['next_cursor'] is not None
    req['cursor']=first['next_cursor']
    second=api.call('q1_camera_search',{'request':req,'parse_response_ref':parsed['output_sha256']},authorize)
    assert second['query_id']==first['query_id'] and second['results'][0]['camera_id']!=first['results'][0]['camera_id']
    assert second['resolved_scope']['time_range_source']=='DEFAULT_SELECTED_RUN'


@pytest.mark.parametrize('kind',['q1','q2'])
def test_default_receipt_is_recorded_and_kernel_and_api_replay_are_exact(tmp_path,kind):
    from amidst.q1q5.baseline_runner import replay_kernel
    api,binding=api_fixture(tmp_path)
    parsed=api.call('q3_parse',parse_request(binding,'人' if kind=='q1' else '跟著人'),authorize)
    req=parsed['structured_query'];selected=None
    if kind=='q1':
        response=api.call('q1_camera_search',{'request':req,'parse_response_ref':parsed['output_sha256']},authorize)
    else:
        selected=seed_id(binding.bindings)
        response=api.call('q2_select_seed',{'request':req,'selected_observation_id':selected,
                         'parse_response_ref':parsed['output_sha256']},authorize)
    ref=response.get('session_id',response['output_sha256']);bundle=api.responses[(TOKEN,ref)]
    assert bundle['parse_response']==parsed and bundle['parse_receipt_ref']==parsed['output_sha256']
    assert replay_kernel(bundle,req,binding,selected,authorize)['output_equal']
    pin=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':ref},authorize)
    descriptor={k:pin[k] for k in ['recording_id','file','file_sha256']}
    replay=QAPI(max_responses=128,max_media_refs=4096,recording_store=api.recording_store,recordings=[descriptor])
    repeated=replay.call('q_recorded_response',{'session_ref':TOKEN,'recording_id':pin['recording_id']},authorize)
    assert repeated==response
    tampered=deepcopy(bundle);tampered.pop('parse_response');tampered.pop('parse_receipt_ref')
    with pytest.raises(APIError):api._verify_bundle(tampered)


def test_api_registered_multi_run_clarification_is_saved_and_replayed_without_execution(tmp_path):
    from test_q5_controller import repin, seal_parameters
    from amidst.q1q5.clock_mapping import ClockMapping
    from amidst.q1q5.store import DetectionSnapshot
    first=run_binding();b=first.bindings
    manifest=deepcopy(b.index.manifest);manifest['run_id']='OTHER_SYNTHETIC_RUN'
    rows=deepcopy(list(b.index.records))
    for row in rows:row['frame_ref']=row['frame_ref'].replace(b.clock.run_id,manifest['run_id'])
    index=repin(DetectionSnapshot(manifest,tuple(rows)))
    declaration=dict(b.clock.document);declaration['run_id']=manifest['run_id']
    declaration['content_sha256']=canonical_hash(declaration,exclude=('content_sha256',))
    mapping=ClockMapping(declaration);params=deepcopy(b.parameter_set)
    params['applies_to']['run_ids']=[manifest['run_id']]
    params['applies_to']['detection_index_ids']=[index.manifest['index_id']];seal_parameters(params)
    second=run_binding(b=replace(b,index=index,index_sha256=index.manifest['content_sha256'],
        clock=mapping,clock_sha256=mapping.content_sha256,parameter_set=params,parameter_sha256=params['content_sha256']))
    store=RecordingStore(tmp_path,repo_root=Path(__file__).parents[2],max_bytes=4000000)
    api=QAPI([first,second],max_responses=128,max_media_refs=4096,recording_store=store)
    query=parse_request(first,'人');query['context']['run_ids'].append(manifest['run_id'])
    response=api.call('q3_parse',query,authorize)
    assert response['status']=='NEEDS_CLARIFICATION' and response['reason']=='MULTI_RUN_SCOPE_UNRESOLVED'
    assert response['structured_query'] is None and response['resolved_scope']['time_range_source'] is None
    assert not response['agent_attempted'] and not response['llm_parse_used']
    receipt=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':response['output_sha256']},authorize)
    replayed=api.call('q_recorded_response',{'session_ref':TOKEN,'recording_id':receipt['recording_id']},authorize)
    assert replayed==response and not api._active


@pytest.mark.parametrize('text', ['跟著', '追蹤那個', '去了哪裡'])
def test_tracking_without_a_target_asks_instead_of_rejecting_the_class(text):
    response, _ = run(request(text))
    assert response['status'] == 'NEEDS_CLARIFICATION'
    assert response['reason'] == 'AMBIGUOUS_QUERY'
    assert response['structured_query'] is None
    assert response['resolved_scope']['time_range_source'] is None


@pytest.mark.parametrize('kind', ['q1', 'q2', 'q3-parse'])
def test_v1_kernel_reexecution_requires_historical_product_without_migrating_bundle(kind):
    from amidst.q1q5.baseline_runner import replay_kernel
    frozen = Path(__file__).parent / 'fixtures/d92_v1_recordings'
    bundles = [json.loads(p.read_bytes()) for p in frozen.glob('*.json') if p.name != 'pins.json']
    bundle = next(x for x in bundles if x['response']['schema_version'] == f'q-demo.{kind}-response.v1')
    before = deepcopy(bundle)
    with pytest.raises(ValueError, match='^V1_KERNEL_REPLAY_REQUIRES_PINNED_PRODUCT$'):
        replay_kernel(bundle, None, None, None, None)
    assert bundle == before


@pytest.mark.parametrize('kind', ['q1', 'q2'])
@pytest.mark.parametrize('outside', [False, True])
def test_explicit_wall_receipt_and_direct_execution_keep_explicit_source(kind, outside):
    api, binding = api_fixture()
    times = '14:00:00到14:00:01' if outside else '13:00:00到13:00:01'
    parsed = api.call('q3_parse', parse_request(binding, ('人' if kind == 'q1' else '跟著人') + times), authorize)
    assert parsed['status'] == 'PARSED'
    req = parsed['structured_query']
    payload = {'request': req, 'parse_response_ref': parsed['output_sha256']}
    if kind == 'q1':
        response = api.call('q1_camera_search', payload, authorize)
        direct = api.call('q1_camera_search', req, authorize)
    else:
        response = api.call('q2_select_seed', dict(payload, selected_observation_id=seed_id(binding.bindings)), authorize)
        direct = api.call('q2_select_seed', dict(request=req, selected_observation_id=seed_id(binding.bindings)), authorize)
    assert response['resolved_scope']['time_range_source'] == 'EXPLICIT_WALL'
    assert direct['resolved_scope']['time_range_source'] == 'EXPLICIT_WALL'
    if outside:
        assert response['status'] == ('OUT_OF_RANGE' if kind == 'q1' else 'UNKNOWN')
        if kind == 'q2':
            assert response['reason'] == 'TIME_OUT_OF_RANGE'


@pytest.mark.parametrize('kind', ['q1', 'q2', 'q3'])
def test_single_run_recorded_response_cannot_omit_scene_revision_even_with_rehashed_output(kind):
    api, binding = api_fixture()
    if kind == 'q1':
        response = api.call('q1_camera_search', q1(binding), authorize)
    elif kind == 'q2':
        response = api.call('q2_select_seed', dict(request=q2(binding), selected_observation_id=seed_id(binding.bindings)), authorize)
    else:
        response = api.call('q3_parse', parse_request(binding, '人'), authorize)
    key = (TOKEN, response.get('session_id', response['output_sha256']))
    bundle = deepcopy(api.responses[key])
    bundle['response']['resolved_scope']['scene_revision'] = None
    bundle['response']['output_sha256'] = canonical_hash(bundle['response'], exclude=('output_sha256', 'stats'))
    api.recordings['tampered'] = (None, bundle)
    with pytest.raises(APIError, match='DataIntegrityError'):
        api.call('q_recorded_response', dict(session_ref=TOKEN, recording_id='tampered'), authorize)

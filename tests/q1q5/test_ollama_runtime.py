"""Pinned runtime/replay wiring on mechanical inputs, no live model in unit tests."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import pytest
from amidst.q1q5.ollama_runtime import (validate_config, bind_runs, load_config, configure_environment,
    SourceIntervalScheduler, RecordedParseProvider, RuntimeConfigError)
from amidst.q1q5.api import QAPI
from amidst.q1q5.q3_parse import parse_query
from amidst.q1q5.store import canonical_hash
from test_api import run_binding, q2, selected, authorize, TOKEN
from test_q5_agent import PolicyProvider, auto
from test_q3_parse import request as parse_request, run as parse_run, provider as parse_provider, ALIASES
from amidst.q1q5.q3_rules import parse_rule


def config(run=None):
    run = run or run_binding(agent=True); b = run.bindings; m = b.index.manifest
    template = lambda text, version: {'text': text, 'version': version, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
    doc = {'schema_version': 'q-demo.ollama-runtime.v1', 'applies_to': {'scene_id': m['scene_id'], 'scene_revision': m['scene_revision'],
           'run_id': m['run_id'], 'detection_index_sha256': b.index_sha256, 'parameter_set_sha256': b.parameter_sha256, 'clock_mapping_sha256': b.clock_sha256},
           'base_url': 'http://127.0.0.1:11437', 'model': 'qwen2.5:7b-instruct', 'model_digest': 'a'*64,
           'options': {'temperature': 0, 'seed': 7}, 'enable_q3': True, 'enable_q5': True,
           'q3_template': template('SYNTHETIC PARSER', 'q3-parse.v1'), 'q5_template': template('SYNTHETIC AGENT', 'q5-agent-v1'),
           'agent_authorization_ref': 'SYNTHETIC_G3'}
    return seal(doc)


def seal(doc):
    doc['content_sha256'] = canonical_hash(doc, exclude=('content_sha256',)); return doc


@pytest.mark.parametrize('change', [lambda d:d.update(base_url='https://example.com'), lambda d:d.update(base_url='http://user@127.0.0.1'),
    lambda d:d.update(model='another-model'), lambda d:d.update(model_digest=None), lambda d:d.update(enable_q3=1),
    lambda d:d['q3_template'].update(text='changed'), lambda d:d['q3_template'].update(version='wrong'),
    lambda d:d['applies_to'].pop('clock_mapping_sha256'), lambda d:d.update(options={'unbounded':1})])
def test_invalid_remote_model_prompt_flags_and_scope_rejected(change):
    d=config();change(d);seal(d)
    with pytest.raises(ValueError):validate_config(d)


def test_config_self_hash_and_file_pin_are_independent(tmp_path):
    doc=config();path=tmp_path/'runtime.json';path.write_text(json.dumps(doc));pin=hashlib.sha256(path.read_bytes()).hexdigest()
    assert load_config(path,pin)==doc
    with pytest.raises(ValueError):load_config(path,'0'*64)
    changed=deepcopy(doc);changed['model_digest']='b'*64;path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):load_config(path,hashlib.sha256(path.read_bytes()).hexdigest())


def test_symlink_runtime_is_not_followed(tmp_path):
    target=tmp_path/'runtime.json';target.write_text(json.dumps(config()));link=tmp_path/'link.json';link.symlink_to(target)
    with pytest.raises(ValueError):load_config(link,hashlib.sha256(target.read_bytes()).hexdigest())


@pytest.mark.parametrize('field',['scene_revision','detection_index_sha256','parameter_set_sha256','clock_mapping_sha256','run_id'])
def test_bound_run_pin_mismatch_is_rejected_before_factory(field):
    run=run_binding(agent=True);d=config(run);d['applies_to'][field]='OTHER';seal(d);calls=[]
    with pytest.raises(ValueError):bind_runs([run],d,provider_factory=lambda url:calls.append(url))
    assert calls==[]


def test_startup_binds_both_capabilities_without_model_calls_and_rule_mode_stays_model_free():
    run=run_binding(agent=True);provider=PolicyProvider(auto)
    bound=bind_runs([run],config(run),provider_factory=lambda url:provider,scheduler_factory=lambda:lambda *x:None)[0]
    assert not provider.requests and bound.q3_options['expected_digest']=='a'*64 and callable(bound.agent_factory)
    api=QAPI([bound],max_responses=128,max_media_refs=4096)
    b=api.bootstrap()['runs'][0];assert b['q3_llm_available'] and b['agent_available']
    result=selected(api,bound);assert not provider.requests and not result['agent_attempted']
    q=q2(bound);q['switch_mode']='AGENT_SEQUENTIAL'
    from test_api import seed_id
    result=api.call('q2_select_seed',{'request':q,'selected_observation_id':seed_id(bound.bindings)},authorize)
    assert len(provider.requests)==2 and result['agent_used']


def test_explicit_disable_removes_old_provider_and_factory():
    run=run_binding(agent=True);d=config(run);d.update(enable_q3=False,enable_q5=False);seal(d)
    bound=bind_runs([run],d,provider_factory=lambda url:object())[0]
    assert bound.q3_options=={} and bound.agent_factory is None


def test_source_scheduler_waits_between_calls_but_not_new_episode():
    ticks=[0.0];sleeps=[]
    def sleep(value):sleeps.append(value);ticks[0]+=value
    scheduler=SourceIntervalScheduler(clock=lambda:ticks[0],sleep=sleep)
    scheduler(1,0,400000);ticks[0]=.1;scheduler(1,1,400000);scheduler(2,0,400000)
    assert sleeps==pytest.approx([.3])
    with pytest.raises(ValueError):scheduler(2,1,0)


def test_environment_absent_does_nothing_but_partial_configuration_fails(monkeypatch):
    monkeypatch.delenv('AMIDST_Q1Q5_OLLAMA_RUNTIME',raising=False);monkeypatch.delenv('AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256',raising=False)
    runs=[run_binding()];assert configure_environment(runs) is runs
    monkeypatch.setenv('AMIDST_Q1Q5_OLLAMA_RUNTIME','/explicit/runtime.json')
    with pytest.raises(ValueError):configure_environment(runs)


def test_q3_exact_audit_replay_and_wrong_input_rejection():
    req=parse_request(mode='LLM_WITH_RULE_FALLBACK');output=parse_rule(req['text'],**ALIASES).output
    args={'provider':parse_provider(output),'prompt_template':'SYNTHETIC TEMPLATE','model':'SYNTHETIC','options':{},'expected_digest':'a'*64}
    response,audit=parse_run(req,**args);replay=RecordedParseProvider(audit,expected_sha256=canonical_hash(audit));args['provider']=replay
    repeated,_=parse_run(req,**args);replay.assert_consumed();assert response==repeated
    replay=RecordedParseProvider(audit,expected_sha256=canonical_hash(audit))
    with pytest.raises(ValueError):replay.generate(model='SYNTHETIC',prompt='different',template='SYNTHETIC TEMPLATE',template_version='q3-parse.v1',options={},timeout_ms=2000,expected_digest='a'*64)
    with pytest.raises(ValueError):RecordedParseProvider(audit,expected_sha256='0'*64)


def test_q3_failed_provider_replays_fallback_without_contacting_model():
    from amidst.q1q5.llm_provider import FakeProvider
    req=parse_request(mode='LLM_WITH_RULE_FALLBACK');args={'provider':FakeProvider([TimeoutError()]),'prompt_template':'SYNTHETIC TEMPLATE','model':'SYNTHETIC','options':{}}
    response,audit=parse_run(req,**args);replay=RecordedParseProvider(audit,expected_sha256=canonical_hash(audit));args['provider']=replay
    repeated,_=parse_run(req,**args);replay.assert_consumed();assert response==repeated and repeated['fallback_used']


@pytest.mark.parametrize('timeout',[False,True])
def test_runtime_q3_api_records_replays_and_rejects_changed_nested_audit(tmp_path,timeout):
    from amidst.q1q5.llm_provider import FakeProvider
    from amidst.q1q5.api import RecordingStore, APIError
    from pathlib import Path
    run=run_binding(agent=True)
    text='車13:00:00到13:00:01'
    output=parse_rule(text,**{k:run.catalog[k] for k in ['class_aliases','color_aliases','camera_aliases','region_aliases']}).output
    tags=json.dumps({'models':[{'name':'qwen2.5:7b-instruct','digest':'a'*64}]}).encode()
    body=json.dumps({'model':'qwen2.5:7b-instruct','response':json.dumps(output),'done':True}).encode()
    provider=FakeProvider([TimeoutError()] if timeout else [tags,body,tags])
    bound=bind_runs([run],config(run),provider_factory=lambda url:provider)[0]
    api=QAPI([bound],max_responses=128,max_media_refs=4096,recording_store=RecordingStore(tmp_path,repo_root=Path(__file__).parents[2],max_bytes=4000000))
    req={'schema_version':'q-demo.q3-parse-request.v1','session_ref':TOKEN,'text':text,'locale':'zh-TW',
         'context':{'scene_id':run.catalog['scene_id'],'run_ids':[run.catalog['run_id']],'clock_mapping_sha256':run.bindings.clock_sha256},'parser_mode':'LLM_WITH_RULE_FALLBACK'}
    response=api.call('q3_parse',req,authorize)
    assert response['fallback_used'] is timeout and response['llm_parse_used'] is not timeout
    bundle=api.responses[(TOKEN,response['output_sha256'])]
    pin=api.call('q_record_response',{'session_ref':TOKEN,'response_ref':response['output_sha256']},authorize)
    replay=QAPI(max_responses=128,max_media_refs=4096,recording_store=api.recording_store,recordings=[{k:pin[k] for k in ['recording_id','file','file_sha256']}])
    assert replay.call('q_recorded_response',{'session_ref':TOKEN,'recording_id':pin['recording_id']},authorize)==response
    changed=deepcopy(bundle);changed['q3_provider_audit'][0]['provider_record']['validation']='TAMPERED'
    with pytest.raises(APIError):api._verify_bundle(changed)

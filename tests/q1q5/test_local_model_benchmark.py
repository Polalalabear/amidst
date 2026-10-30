"""Mechanical benchmark protocol tests; no downloads, model or formal labels."""
import importlib.util
import hashlib,json
from pathlib import Path
from copy import deepcopy
import pytest
from amidst.q1q5.llm_provider import FakeTransport,ProviderError
from amidst.q1q5.store import canonical_hash
from test_api import run_binding

spec=importlib.util.spec_from_file_location('local_model_benchmark',Path(__file__).parents[2]/'scripts/benchmark_q1q5_local_models.py')
bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
MODEL='qwen3:1.7b-q4_K_M';PIN='a'*64

def raw(doc):return json.dumps(doc).encode()
def tags(digest=PIN):return raw({'models':[{'name':MODEL,'digest':digest}]})
def ps(name=MODEL):return raw({'models':[{'name':name,'digest':PIN}]})
def envelope(**changes):
    d={'model':MODEL,'done':True,'done_reason':'stop','message':{'role':'assistant','content':'{"tool":"get_search_context","arguments":{}}'}};d.update(changes);return raw(d)
def args():return dict(model=MODEL,prompt='T\n{"context":{}}',template='T',template_version='SYNTHETIC',options={'temperature':.7,'seed':7},timeout_ms=2000,expected_digest=PIN)
def transport(body=None):return FakeTransport([tags(),ps(),envelope() if body is None else body,tags(),ps()])


def test_native_messages_preserve_literal_chinese_and_catalog():
    prompt='T\nCLOSED_CATALOG={"class_labels":["car"]}\nUSER_TEXT="\\u8eca13:00:00"'
    m=bench.messages(prompt,'T')
    assert m==[{'role':'system','content':'T\nCLOSED_CATALOG={"class_labels":["car"]}'},{'role':'user','content':'車13:00:00'}]


@pytest.mark.parametrize('prompt',['not framed','T\nnot JSON','T\nCLOSED_CATALOG={}\nUSER_TEXT=1','T\n{"ground_truth":{}}'])
def test_bad_framing_or_forbidden_input_is_rejected(prompt):
    with pytest.raises(ValueError):bench.messages(prompt,'T')


def test_native_payload_records_non_thinking_wire_hash_and_separate_caller_hash():
    t=transport();p=bench.NativeChatProvider(t,context_tokens=4096,token_cap=256,clock=lambda:0);request=args();r=p.generate(**request)
    payload=t.calls[2][2]
    assert t.calls[2][1]=='/api/chat' and payload['think'] is False and payload['format']=='json'
    assert payload['options']['num_ctx']==4096 and payload['options']['num_predict']==256
    assert r.record['input_sha256']==canonical_hash(payload) and r.record['caller_request_sha256']==canonical_hash(request)
    assert r.record['protocol']=='q-demo.native-chat-benchmark.v1' and 'raw' not in payload
    assert request==args() and r.record['model_digest']==PIN


def test_successful_call_is_exactly_replayable_without_transport():
    p=bench.NativeChatProvider(transport(),context_tokens=4096,token_cap=128,clock=lambda:0);result=p.generate(**args())
    replay=bench.ReplayChatProvider(p.events,expected_sha256=canonical_hash(p.events));repeated=replay.generate(**args());replay.assert_consumed()
    assert result.record==repeated.record and result.text==repeated.text
    with pytest.raises(ValueError):replay.generate(**args())


def test_replay_rejects_changed_inputs_and_independent_audit_pin():
    p=bench.NativeChatProvider(transport(),context_tokens=4096,token_cap=128,clock=lambda:0);p.generate(**args())
    with pytest.raises(ValueError):bench.ReplayChatProvider(p.events,expected_sha256='0'*64)
    replay=bench.ReplayChatProvider(p.events,expected_sha256=canonical_hash(p.events));request=args();request['timeout_ms']=3000
    with pytest.raises(ValueError):replay.generate(**request)


@pytest.mark.parametrize('body',[envelope(done_reason='length'),envelope(message={'role':'assistant','content':'{}','thinking':'reasoning'}),envelope(message={'role':'assistant','content':'','tool_calls':[{}]}),envelope(model='other')])
def test_incomplete_thinking_or_wrong_model_output_is_not_accepted(body):
    t=transport(body);p=bench.NativeChatProvider(t,context_tokens=4096,token_cap=128,clock=lambda:0)
    with pytest.raises(ProviderError) as e:p.generate(**args())
    assert e.value.code=='INVALID_RESPONSE'


def test_wrong_model_pin_stops_before_task_generation():
    t=FakeTransport([tags('b'*64)]);p=bench.NativeChatProvider(t,context_tokens=4096,token_cap=128,clock=lambda:0)
    with pytest.raises(ProviderError):p.generate(**args())
    assert [call[:2] for call in t.calls]==[('GET','/api/tags')]


def test_another_active_model_is_never_evicted_for_a_trial():
    t=FakeTransport([tags(),ps('other')]);p=bench.NativeChatProvider(t,context_tokens=4096,token_cap=128,clock=lambda:0)
    with pytest.raises(ProviderError):p.generate(**args())
    assert all(call[0]=='GET' for call in t.calls)


def test_timeout_remains_failure_and_replays_without_hidden_retry():
    t=FakeTransport([TimeoutError()]);p=bench.NativeChatProvider(t,context_tokens=4096,token_cap=128,clock=lambda:0)
    with pytest.raises(ProviderError) as first:p.generate(**args())
    replay=bench.ReplayChatProvider(p.events,expected_sha256=canonical_hash(p.events))
    with pytest.raises(ProviderError) as repeated:replay.generate(**args())
    replay.assert_consumed();assert first.value.code==repeated.value.code=='PROVIDER_TIMEOUT' and len(t.calls)==1


def test_deadline_also_includes_post_generation_metadata_checks():
    clock=[0.0]
    class LateTransport(FakeTransport):
        def request(self,*a):
            value=super().request(*a)
            if len(self.calls)==5:clock[0]=3.0
            return value
    t=LateTransport([tags(),ps(),envelope(),tags(),ps()]);p=bench.NativeChatProvider(t,context_tokens=4096,token_cap=128,clock=lambda:clock[0])
    with pytest.raises(ProviderError) as e:p.generate(**args())
    assert e.value.code=='PROVIDER_TIMEOUT'


@pytest.mark.parametrize('tokens,context',[(257,4096),(0,4096),(128,32768)])
def test_resource_caps_require_bounded_explicit_values(tokens,context):
    with pytest.raises(ValueError):bench.NativeChatProvider(FakeTransport([]),context_tokens=context,token_cap=tokens)


def test_diagnostic_bounds_clone_only_synthetic_fixture_without_touching_original():
    run=run_binding(agent=True);before=deepcopy(run.bindings.parameter_set)
    changed,overrides=bench.diagnostic_run(run,call_ms=30000,total_ms=90000)
    assert run.bindings.parameter_set==before and changed.bindings.parameter_set is not run.bindings.parameter_set
    assert changed.parse_settings.q3_llm_timeout_ms==30000 and overrides['research_interval_us']==1000000
    assert changed.bindings.parameter_sha256!=run.bindings.parameter_sha256
    from dataclasses import replace
    with pytest.raises(ValueError):bench.diagnostic_run(replace(run,source_kind='ACTUAL_BLENDER'),call_ms=30000,total_ms=90000)


def test_native_provider_runs_real_q5_tools_guard_and_exact_recorded_replay():
    from test_q5_agent import auto
    from test_api import q2,seed_id
    from amidst.q1q5.q5_agent import AgentController,AgentSettings,RecordedProvider
    from amidst.q1q5.q4_evidence import candidate_evidence
    class PolicyTransport:
        def __init__(self):self.count=0
        def request(self,method,path,payload,timeout):
            if path=='/api/tags':return tags()
            if path=='/api/ps':return ps()
            assert path=='/api/chat';self.count+=1
            output=auto(json.loads(payload['messages'][1]['content']),self.count)
            return envelope(message={'role':'assistant','content':json.dumps(output)})
    run=run_binding(agent=True);b=run.bindings;q=q2(run);q['switch_mode']='AGENT_SEQUENTIAL'
    settings=AgentSettings(MODEL,PIN,{'temperature':.7,'seed':7},'T',hashlib.sha256(b'T').hexdigest(),'SYNTHETIC','SYNTHETIC')
    transport=PolicyTransport();provider=bench.NativeChatProvider(transport,context_tokens=4096,token_cap=256,clock=lambda:0)
    kwargs=dict(bindings=b,evidence_provider=lambda idx,s,r,c:candidate_evidence(idx,s,r,**c),selected_observation_id=seed_id(b),agent_settings=settings)
    c=AgentController(q,provider=provider,round_scheduler=lambda *a:None,**kwargs);result=c.run()
    assert transport.count==2 and result.response['agent_used'] and not result.response['fallback_used']
    replay=RecordedProvider(c.trace(),expected_sha256=c.trace()['content_sha256']);again=AgentController(q,provider=replay,clock=replay.clock,round_scheduler=lambda *a:None,**kwargs).run();replay.assert_consumed()
    assert result.decisions_bytes==again.decisions_bytes and result.links_bytes==again.links_bytes
    assert result.response['output_sha256']==again.response['output_sha256']


def test_native_q3_parser_receipt_replays_without_any_model_connection():
    from amidst.q1q5.q3_parse import parse_query
    from amidst.q1q5.q3_rules import parse_rule
    run=run_binding();text='車13:00:00到13:00:01';output=parse_rule(text,**{k:run.catalog[k] for k in ['class_aliases','color_aliases','camera_aliases','region_aliases']}).output
    t=transport(envelope(message={'role':'assistant','content':json.dumps(output)}))
    provider=bench.NativeChatProvider(t,context_tokens=4096,token_cap=256,clock=lambda:0)
    req={'schema_version':'q-demo.q3-parse-request.v1','session_ref':'SYNTHETIC','text':text,'locale':'zh-TW','context':{'scene_id':run.catalog['scene_id'],'run_ids':[run.catalog['run_id']],'clock_mapping_sha256':run.bindings.clock_sha256},'parser_mode':'LLM_WITH_RULE_FALLBACK'}
    kwargs=dict(catalog=run.catalog,settings=run.parse_settings,clock_mapping=run.bindings.clock,prompt_template='T',model=MODEL,options={'temperature':.7,'seed':7},expected_digest=PIN)
    response,_=parse_query(req,provider=provider,**kwargs);assert response['llm_parse_used'] and response['status']=='PARSED'
    replay=bench.ReplayChatProvider(provider.events,expected_sha256=canonical_hash(provider.events));again,_=parse_query(req,provider=replay,**kwargs);replay.assert_consumed();assert response==again

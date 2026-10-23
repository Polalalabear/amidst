"""Management diagnostics stay outside task budgets and product acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path
from copy import deepcopy
import pytest
from amidst.q1q5.store import canonical_hash
from amidst.q1q5.llm_provider import FakeTransport, _object
from test_api import api_fixture, selected
from test_q3_parse import provider as parse_provider, request as parse_request, run as parse_run, ALIASES
from amidst.q1q5.q3_rules import parse_rule

spec=importlib.util.spec_from_file_location('qwen_diagnostics',Path(__file__).parents[2]/'scripts/diagnose_q1q5_ollama.py')
diag=importlib.util.module_from_spec(spec);spec.loader.exec_module(diag)
MODEL='qwen2.5:7b-instruct';PIN='a'*64


def raw(doc):return json.dumps(doc).encode()
def tag(digest=PIN):return raw({'models':[{'name':MODEL,'digest':digest}]})
def active(digest=PIN,name=MODEL):return raw({'models':[{'name':name,'digest':digest}]})
def ready():return raw({'model':MODEL,'done':True,'done_reason':'load','response':''})


@pytest.mark.parametrize('changes',[{'timeout_ms':0},{'timeout_ms':30001},{'timeout_ms':True},{'keep_alive_seconds':0},{'keep_alive_seconds':301},{'digest':'bad'},{'model':'other'}])
def test_invalid_management_arguments_do_not_contact_server(changes):
    t=FakeTransport([]);args=dict(model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300);args.update(changes)
    with pytest.raises(ValueError):diag.preload_model(t,**args)
    assert t.calls==[]


def test_digest_mismatch_stops_before_load_and_never_pulls():
    t=FakeTransport([tag('b'*64)])
    with pytest.raises(ValueError):diag.preload_model(t,model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300)
    assert [x[:2] for x in t.calls]==[('GET','/api/tags')]


def test_another_active_model_yields_without_eviction_or_reload():
    t=FakeTransport([tag(),active(name='other')])
    with pytest.raises(ValueError):diag.preload_model(t,model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300)
    assert all(x[0]=='GET' for x in t.calls)


def test_loaded_target_is_observed_without_extending_keep_alive():
    t=FakeTransport([tag(),active()]);r=diag.preload_model(t,model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300,clock=lambda:0)
    assert r['status']=='LOADED_OBSERVED' and not r['preload_request_sent'] and not r['inference_budgets_changed']
    assert all(x[0]=='GET' for x in t.calls)


def test_empty_prompt_load_rechecks_digest_and_running_model():
    t=FakeTransport([tag(),raw({'models':[]}),ready(),tag(),active()]);r=diag.preload_model(t,model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300,clock=lambda:0)
    assert r['preload_request_sent'] and r['management_only']
    assert t.calls[2][2]=={'model':MODEL,'prompt':'','stream':False,'keep_alive':'300s'}
    assert all(call[1] not in {'/api/pull','/api/delete'} for call in t.calls)


@pytest.mark.parametrize('response',[{'model':MODEL,'done':True,'done_reason':'stop','response':'answer'}, {'model':MODEL,'done':False,'done_reason':'load','response':''}])
def test_preload_cannot_generate_an_answer_or_report_unfinished_load(response):
    t=FakeTransport([tag(),raw({'models':[]}),raw(response)])
    with pytest.raises(ValueError):diag.preload_model(t,model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300,clock=lambda:0)
    assert len(t.calls)==3


@pytest.mark.parametrize('tail',[[tag('b'*64)],[tag(),raw({'models':[]})]])
def test_preload_drift_or_missing_loaded_model_fails_closed(tail):
    t=FakeTransport([tag(),raw({'models':[]}),ready(),*tail])
    with pytest.raises(ValueError):diag.preload_model(t,model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300,clock=lambda:0)


def test_management_deadline_includes_metadata_before_generation():
    values=iter([0,.001,31]);t=FakeTransport([tag()])
    with pytest.raises(TimeoutError):diag.preload_model(t,model=MODEL,digest=PIN,timeout_ms=30000,keep_alive_seconds=300,clock=lambda:next(values))
    assert [x[0] for x in t.calls]==['GET']


def test_probe_file_pin_and_synthetic_scope_reject_before_measurement(tmp_path):
    api,run=api_fixture(agent=True);response=selected(api,run);bundle=deepcopy(api.responses[('SYNTHETIC_SESSION_A',response['session_id'])])
    path=tmp_path/'bundle.json';path.write_bytes(raw(bundle));pin=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):diag.pinned_record(path,'0'*64,'q5',model=MODEL,digest=PIN,template='SYNTHETIC')
    bundle['source_kind']='ACTUAL_BLENDER';path.write_bytes(raw(bundle));pin=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):diag.pinned_record(path,pin,'q5',model=MODEL,digest=PIN,template='SYNTHETIC')


class Capture(FakeTransport):
    def __init__(self,responses):super().__init__(responses);self.envelopes=[]
    def request(self,*args):
        value=super().request(*args)
        if args[1]=='/api/generate':self.envelopes.append(_object(value))
        return value


def source_record():
    req=parse_request(mode='LLM_WITH_RULE_FALLBACK');output=parse_rule(req['text'],**ALIASES).output
    _,audit=parse_run(req,provider=parse_provider(output),prompt_template='SYNTHETIC TEMPLATE',model='SYNTHETIC',options={})
    return audit[0]['provider_record'],req['text'],output


def test_longer_timing_is_diagnostic_even_with_valid_output_and_exact_input():
    old,text,output=source_record();tags=raw({'models':[{'name':'SYNTHETIC','digest':PIN}]})
    body=raw({'model':'SYNTHETIC','done':True,'response':json.dumps(output),'eval_count':80,'eval_duration':14000000000})
    t=Capture([tags,body,tags]);r,record,envelopes=diag.measure_record(t,old,template='SYNTHETIC TEMPLATE',timeout_ms=15000,text=text)
    assert r['diagnostic_only'] and not r['production_or_evaluation_accepted'] and not r['inference_budgets_changed']
    assert r['source_probe_timeout_ms']==2000 and r['diagnostic_timeout_ms']==15000 and old['timeout_ms']==2000
    assert r['input_sha256_unchanged'] and r['q3_literal_check']=='VALID_LITERAL_SCHEMA_ONLY'
    assert not r['q5_task_guard_executed'] and r['metrics']['eval_count']==80 and 'output_sha256' not in r


def test_provider_envelope_does_not_hide_invalid_q3_task_output():
    old,text,output=source_record();output['class_term']='person';tags=raw({'models':[{'name':'SYNTHETIC','digest':PIN}]})
    t=Capture([tags,raw({'model':'SYNTHETIC','done':True,'response':json.dumps(output)}),tags])
    r,_,_=diag.measure_record(t,old,template='SYNTHETIC TEMPLATE',timeout_ms=15000,text=text)
    assert r['validation']=='PROVIDER_VALIDATED' and r['q3_literal_check']=='INVALID_LITERAL_SCHEMA_OR_SUBSTRING'
    assert not r['production_or_evaluation_accepted']


def test_timing_timeout_is_retained_and_no_hidden_retry():
    old,_,_=source_record();t=Capture([TimeoutError()]);r,_,envelopes=diag.measure_record(t,old,template='SYNTHETIC TEMPLATE',timeout_ms=15000)
    assert r['validation']=='PROVIDER_TIMEOUT' and len(t.calls)==1 and not envelopes


@pytest.mark.parametrize('extra',[['--preload'],['--preload-timeout-ms','1'],['--preload','--preload-timeout-ms','30001','--keep-alive-seconds','300'],['--measure-timeout-ms','0']])
def test_cli_invalid_bounds_stop_before_transport_or_output(tmp_path,monkeypatch,extra):
    import sys
    path=tmp_path/'new-output';created=[]
    monkeypatch.setattr(diag,'DiagnosticTransport',lambda url:created.append(url))
    monkeypatch.setattr(sys,'argv',['diagnose','--base-url','http://127.0.0.1:11437','--model',MODEL,'--model-digest',PIN,'--output',str(path),*extra])
    with pytest.raises(SystemExit):diag.main()
    assert not path.exists() and created==[]


def test_exact_pinned_q3_bundle_from_api_loads_and_template_or_input_drift_rejects(tmp_path):
    from dataclasses import replace
    from amidst.q1q5.api import QAPI
    from amidst.q1q5.llm_provider import FakeProvider
    from test_api import run_binding,authorize,TOKEN
    run=run_binding();template='SYNTHETIC TEMPLATE';text='車13:00:00到13:00:01'
    output=parse_rule(text,**{k:run.catalog[k] for k in ['class_aliases','color_aliases','camera_aliases','region_aliases']}).output
    provider=FakeProvider([tag(),raw({'model':MODEL,'done':True,'response':json.dumps(output)}),tag()])
    run=replace(run,q3_options={'provider':provider,'prompt_template':template,'model':MODEL,'options':{},'expected_digest':PIN})
    api=QAPI([run],max_responses=128,max_media_refs=4096)
    req={'schema_version':'q-demo.q3-parse-request.v1','session_ref':TOKEN,'text':text,'locale':'zh-TW','context':{'scene_id':run.catalog['scene_id'],'run_ids':[run.catalog['run_id']],'clock_mapping_sha256':run.bindings.clock_sha256},'parser_mode':'LLM_WITH_RULE_FALLBACK'}
    response=api.call('q3_parse',req,authorize);bundle=api.responses[(TOKEN,response['output_sha256'])]
    path=tmp_path/'q3.json';path.write_bytes(raw(bundle));pin=hashlib.sha256(path.read_bytes()).hexdigest()
    read,record=diag.pinned_record(path,pin,'q3',model=MODEL,digest=PIN,template=template)
    assert read==bundle and record['model_digest']==PIN
    with pytest.raises(ValueError):diag.pinned_record(path,pin,'q3',model=MODEL,digest=PIN,template='different')
    changed=deepcopy(bundle);changed['q3_provider_audit'][0]['provider_record']['prompt']='tampered';path.write_bytes(raw(changed))
    with pytest.raises(ValueError):diag.pinned_record(path,hashlib.sha256(path.read_bytes()).hexdigest(),'q3',model=MODEL,digest=PIN,template=template)


def test_cli_measurement_without_preload_cannot_compete_with_another_loaded_model(tmp_path,monkeypatch):
    import sys
    out=tmp_path/'new-output';transport=Capture([tag(),active(name='other'),active(name='other')])
    monkeypatch.setattr(diag,'DiagnosticTransport',lambda url:transport)
    monkeypatch.setattr(diag,'pinned_record',lambda *args,**kwargs:({'request':{'text':'SYNTHETIC'}},{}))
    monkeypatch.setattr(sys,'argv',['diagnose','--base-url','http://127.0.0.1:11437','--model',MODEL,'--model-digest',PIN,'--output',str(out),
        '--q3-bundle',str(tmp_path/'pinned.json'),'--q3-bundle-sha256',PIN,'--measure-timeout-ms','15000'])
    with pytest.raises(ValueError):diag.main()
    assert all(call[0]=='GET' for call in transport.calls)
    assert (out/'ERROR.json').exists() and not (out/'REPORT.json').exists()

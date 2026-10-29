"""SYNTHETIC strict schema/literal/scope/provider tests; no human testset reads."""
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from test_q3_rules import ALIASES

from amidst.q1q5.clock_mapping import ClockMapping
from amidst.q1q5.llm_provider import FakeProvider
from amidst.q1q5.q3_parse import ParseError, ParseSettings, parse_query, validate_literal_output
from amidst.q1q5.q3_rules import parse_rule
from amidst.q1q5.store import canonical_hash

H='a'*64

def clock():
    d={'schema_version':'q-demo.clock-mapping.v1','run_id':'RUN_SYN','clock_id':'CLOCK_SYN','timezone':'Asia/Taipei','wall_origin':'2026-11-01T13:00:00+08:00','mapping_kind':'DECLARED_DEMO_CLOCK','t0_us':0,'rate':1,'source_duration_us':30000000,'mapping_version':'SYNTHETIC','declaration_source':'SYNTHETIC','declared_by':'SYNTHETIC','declared_at':'2026-10-21T00:00:00+08:00'}
    d['content_sha256']=canonical_hash(d);return ClockMapping(d)


def catalog():
    return {'scene_id':'SYNTHETIC','scene_revision':'rSYN','run_id':'RUN_SYN','class_labels':['person','car'],'color_labels':['red','blue'],'camera_ids':['A'],'region_ids':['R'],'class_map_sha256':H,**deepcopy(ALIASES)}


def settings():return ParseSettings(.3,1,'STRONG',20,'RULE_ONLY','pset:q-demo:'+H[:16],H,2,2000)


def request(text='車13:00:00到13:00:10',mode='RULE_ONLY'):
    return {'schema_version':'q-demo.q3-parse-request.v1','session_ref':'SYNTHETIC','text':text,'locale':'zh-TW','context':{'scene_id':'SYNTHETIC','run_ids':['RUN_SYN'],'clock_mapping_sha256':clock().content_sha256},'parser_mode':mode}


def run(req=None,**kwargs):
    args=dict(catalog=catalog(),settings=settings(),clock_mapping=clock());args.update(kwargs)
    return parse_query(req or request(),**args)


def provider(output):
    tags=json.dumps({'models':[{'name':'SYNTHETIC','digest':H}]}).encode()
    body=json.dumps({'model':'SYNTHETIC','done':True,'response':json.dumps(output)}).encode()
    return FakeProvider([tags,body,tags])


def test_rule_query_and_hash_repeat_without_agent_or_default_parameters():
    response,audit=run();assert response['status']=='PARSED' and response['parsed_by']=='RULE' and audit==()
    q=response['structured_query'];assert q['condition']['class_label']=='car' and q['time']['wall_range']==['2026-11-01T13:00:00+08:00','2026-11-01T13:00:10+08:00']
    assert not response['agent_used'] and not response['llm_parse_used']
    assert canonical_hash(response,exclude=('output_sha256','stats'))==response['output_sha256'] and run()[0]==response


def test_person_builds_q2_with_explicit_rule_only_and_parameter_ref():
    r,_=run(request('紅衣人13:00:00到13:00:10'))
    assert r['structured_query']['schema_version']=='q-demo.q2-request.v1'
    assert r['structured_query']['seed']['color']=={'label':'red','min_verdict':'STRONG'}
    assert r['structured_query']['switch_mode']=='RULE_ONLY'


@pytest.mark.parametrize('text,status',[('樹13:00:00到13:00:10','UNSUPPORTED_CLASS'),('紅車13:00:00到13:00:10','UNSUPPORTED_CONDITION'),('人','NEEDS_CLARIFICATION'),('找他','NEEDS_CLARIFICATION'),('xyzzy','PARSE_FAILED'),('戴眼鏡的人13:00:00到13:00:10','UNSUPPORTED_CONDITION'),('拿著物品的人13:00:00到13:00:10','NEEDS_CLARIFICATION'),('車13:00:10到13:00:00','TIME_EXPRESSION_INVALID')])
def test_nonparsed_never_executes_or_has_structured_query(text,status):
    r,_=run(request(text));assert r['status']==status and r['structured_query'] is None


def test_missing_clock_asks_without_guessing_current_date():
    req=request();req['context']['clock_mapping_sha256']=None;r,_=run(req,clock_mapping=None)
    assert r['status']=='NEEDS_CLARIFICATION' and r['reason']=='CLOCK_MAPPING_MISSING' and r['structured_query'] is None


def test_llm_literal_output_is_accepted_but_does_not_set_agent_used():
    req=request(mode='LLM_WITH_RULE_FALLBACK');parsed=parse_rule(req['text'],**ALIASES).output
    r,audit=run(req,provider=provider(parsed),prompt_template='SYNTHETIC TEMPLATE',model='SYNTHETIC',options={'temperature':0,'seed':7})
    assert r['status']=='PARSED' and r['llm_parse_used'] and not r['agent_used'] and not r['fallback_used']
    assert len(audit)==1 and audit[0]['provider_record']['content_sha256']==canonical_hash(audit[0]['provider_record'],exclude=('content_sha256','stats'))


def test_provider_unavailable_falls_back_without_model_or_hidden_retry():
    r,audit=run(request(mode='LLM_WITH_RULE_FALLBACK'),provider=None)
    assert r['status']=='PARSED' and r['fallback_used'] and r['fallback_reason']=='PROVIDER_UNAVAILABLE' and audit==()


def test_provider_timeout_keeps_audit_and_rule_parse():
    r,audit=run(request(mode='LLM_WITH_RULE_FALLBACK'),provider=FakeProvider([TimeoutError()]),prompt_template='SYNTHETIC TEMPLATE',model='SYNTHETIC',options={})
    assert r['fallback_reason']=='PROVIDER_TIMEOUT' and r['parsed_by']=='RULE' and r['llm_call']['attempts']==1
    assert len(audit)==1 and r['llm_call']['model_digest'] is None


def test_invalid_llm_retries_only_explicit_bound_then_rule_fallback():
    req=request(mode='LLM_WITH_RULE_FALLBACK');bad=parse_rule(req['text'],**ALIASES).output;bad['class_term']='person'
    tags=json.dumps({'models':[{'name':'SYNTHETIC','digest':H}]}).encode();body=json.dumps({'model':'SYNTHETIC','done':True,'response':json.dumps(bad)}).encode()
    r,audit=run(req,provider=FakeProvider([tags,body,tags]*2),prompt_template='SYNTHETIC TEMPLATE',model='SYNTHETIC',options={})
    assert r['fallback_reason']=='INVALID_RESPONSE' and r['llm_call']['attempts']==2 and len(audit)==2
    assert r['status']=='PARSED' and r['parsed_by']=='RULE'
    for a in audit:assert a['provider_record']['content_sha256']==canonical_hash(a['provider_record'],exclude=('content_sha256','stats'))


@pytest.mark.parametrize('change',[{'actor_id':'GT'},{'parser_mode':'OTHER'},{'locale':'UNKNOWN'},{'text':''}])
def test_request_overreach_rejected_before_provider(change):
    req=request();req.update(change)
    with pytest.raises(ParseError):run(req)


def test_clock_pin_alias_scope_and_llm_bounds_are_fail_closed():
    req=request();req['context']['clock_mapping_sha256']='b'*64
    with pytest.raises(ParseError):run(req)
    c=catalog();c['class_aliases']['樹']='tree'
    with pytest.raises(ParseError):run(catalog=c)
    with pytest.raises(ParseError):run(request(mode='LLM_WITH_RULE_FALLBACK'),settings=replace(settings(),q3_max_llm_attempts=None))


@pytest.mark.parametrize('change',[{'extra':'x'},{'needs_clarification':'true'},{'class_term':'person'},{'time_literal':{'start':'13:00','end':'13:10','date':'2026-11-01'}}])
def test_llm_extra_fields_types_or_nonliteral_words_refused(change):
    output=parse_rule('車13:00到13:10',**ALIASES).output;output.update(change)
    with pytest.raises(ValueError):validate_literal_output(output,'車13:00到13:10')



def test_schema_valid_model_cannot_erase_explicit_color_condition():
    req=request('紅車13:00:00到13:00:10',mode='LLM_WITH_RULE_FALLBACK')
    bad=parse_rule(req['text'],**ALIASES).output;bad['color_term']=None
    tags=json.dumps({'models':[{'name':'SYNTHETIC','digest':H}]}).encode()
    body=json.dumps({'model':'SYNTHETIC','done':True,'response':json.dumps(bad)}).encode()
    r,audit=run(req,provider=FakeProvider([tags,body,tags]*2),prompt_template='SYNTHETIC TEMPLATE',model='SYNTHETIC',options={})
    assert r['status']=='UNSUPPORTED_CONDITION' and r['structured_query'] is None
    assert r['fallback_reason']=='INVALID_RESPONSE' and len(audit)==2

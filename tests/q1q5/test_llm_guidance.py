"""Guided formats preserve task guards, source pins and old replay semantics."""
from pathlib import Path
import importlib.util,json,hashlib
from copy import deepcopy
import pytest
from amidst.contracts.q_demo.mini_schema import Validator

ValidationError=ValueError
def validate(value,schema):
    errors=Validator(lambda name:schema).validate(value,"guidance")
    if errors:raise ValueError(str(errors))
from amidst.q1q5.llm_guidance import q3_schema,workflow,q5_schema,Q3_MARKER,Q5_MARKER
from amidst.q1q5.llm_provider import generation_request,FakeProvider,QWEN3_MODEL,GUIDED_PROTOCOL
from amidst.q1q5.store import canonical_hash
ROOT=Path(__file__).parents[2]


def test_q3_schema_rejects_wrong_time_and_null_arrays_without_teaching_answers():
    from test_q3_parse import ALIASES,request
    from amidst.q1q5.q3_rules import parse_rule
    good=parse_rule(request()['text'],**ALIASES).output;validate(good,q3_schema())
    for field,value in [('time_literal','13:00:00'),('camera_terms',None),('region_terms',None),('unknown',True)]:
        bad=deepcopy(good);bad[field]=value
        with pytest.raises(ValidationError):validate(bad,q3_schema())


def context():
    return {'session_id':'S','decision_id':'D','candidate_snapshot_sha256':'a'*64,'next_candidate_rank':1,
        'candidates':[{'rank':1,'candidate_ref':'C1'},{'rank':2,'candidate_ref':'C2'}]}


def evidence(presence='MATCH_STRONG',refs=True):
    return {'candidate_ref':'C1','target_presence':presence,'entry_observation_id':'O' if refs and presence=='MATCH_STRONG' else None,
        'best_observations':[{'observation_id':'O'}] if refs else []}


def test_workflow_does_not_offer_redundant_context_or_observation_calls():
    c=context();w=workflow(c,{},[{'tool':'get_observation_summary'}]);schema=q5_schema({'context':c,'workflow':w})
    validate({'tool':'get_candidate_evidence','arguments':{'session_id':'S','decision_id':'D','candidate_ref':'C1'}},schema)
    for tool,args in [('get_observation_summary',{'session_id':'S','observation_id':'O'}),('get_search_context',{'session_id':'S','decision_id':'D'}),('get_candidate_evidence',{'session_id':'S','decision_id':'D','candidate_ref':'C2'})]:
        with pytest.raises(ValidationError):validate({'tool':tool,'arguments':args},schema)
    assert 'get_observation_summary' in w['completed_tools'] and w['phase']=='FETCH_CANDIDATE_EVIDENCE'


@pytest.mark.parametrize('presence,refs,actions',[('MATCH_STRONG',True,{'SWITCH','NEXT_CANDIDATE','RETURN_TO_ORIGIN'}),('UNKNOWN',True,{'NEXT_CANDIDATE','RETURN_TO_ORIGIN'}),('NO_OBSERVATION',False,{'RETURN_TO_ORIGIN'})])
def test_schema_does_not_offer_switch_without_strong_entry_or_empty_next(presence,refs,actions):
    c=context();w=workflow(c,{'C1':evidence(presence,refs)},[])
    assert set(w['allowed_next_outputs'])==actions
    base={'schema_version':'q-demo.agent-decision.v1','session_id':'S','decision_id':'D','candidate_snapshot_sha256':'a'*64,'rationale':'Stop without a cut.'}
    for action in actions:
        validate({**base,'rationale':{'RETURN_TO_ORIGIN':'Stop without a cut.','NEXT_CANDIDATE':'Continue to next candidate.','SWITCH':'Strong observed evidence.'}[action],'action':action,'candidate_ref':None if action=='RETURN_TO_ORIGIN' else 'C1','cited_observation_ids':[] if action=='RETURN_TO_ORIGIN' else ['O']},q5_schema({'context':c,'workflow':w}))
    with pytest.raises(ValidationError):validate({**base,'action':'SWITCH','candidate_ref':'C1','cited_observation_ids':['foreign']},q5_schema({'context':c,'workflow':w}))


def test_native_v2_wires_actual_json_schema_and_distinct_protocol():
    template=(ROOT/'configs/q1q5/prompts/q3_parse_v2.txt').read_text();prompt=template+'\nCLOSED_CATALOG={}\nUSER_TEXT="車"'
    path,wire=generation_request(QWEN3_MODEL,prompt,template,{'temperature':0});assert path=='/api/chat' and wire['format']==q3_schema({},'車') and wire['think'] is False
    tags=json.dumps({'models':[{'name':QWEN3_MODEL,'digest':'a'*64}]}).encode();body=json.dumps({'model':QWEN3_MODEL,'done':True,'done_reason':'stop','message':{'role':'assistant','content':'{}'}}).encode()
    result=FakeProvider([tags,body,tags]).generate(model=QWEN3_MODEL,prompt=prompt,template=template,template_version='q3-parse.v2',options={'temperature':0},timeout_ms=2000,expected_digest='a'*64)
    assert result.record['protocol']==GUIDED_PROTOCOL and result.record['wire_request']==wire
    assert result.record['input_sha256']==canonical_hash(wire)


def test_v2_q3_keeps_literal_guard_even_if_json_schema_passes():
    from test_q3_parse import run,request,ALIASES
    from amidst.q1q5.q3_rules import parse_rule
    template=(ROOT/'configs/q1q5/prompts/q3_parse_v2.txt').read_text();req=request(mode='LLM_WITH_RULE_FALLBACK');good=parse_rule(req['text'],**ALIASES).output;good['class_term']='person';validate(good,q3_schema())
    tags=json.dumps({'models':[{'name':QWEN3_MODEL,'digest':'a'*64}]}).encode();body=json.dumps({'model':QWEN3_MODEL,'done':True,'done_reason':'stop','message':{'role':'assistant','content':json.dumps(good)}}).encode()
    result,audit=run(req,provider=FakeProvider([tags,body,tags]*2),prompt_template=template,prompt_template_version='q3-parse.v2',model=QWEN3_MODEL,options={},expected_digest='a'*64)
    assert not result['llm_parse_used'] and result['fallback_reason']=='INVALID_RESPONSE' and audit[0]['task_validation_errors']


def test_measurement_page_parser_uses_actual_page_size_not_fixed_four_k():
    spec=importlib.util.spec_from_file_location('contention',ROOT/'scripts/measure_q1q5_contention.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    page,values=m.page_stats('Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 12.\nSwapouts: 7.\n')
    assert page==16384 and values['Pages free']==12 and values['Swapouts']==7


def test_grounding_uses_only_closed_aliases_and_literal_time_date_spans():
    s=q3_schema({'class_aliases':{'車':'car','人':'person'},'color_aliases':{'紅':'red'},'camera_aliases':{'A':'A'},'region_aliases':{}},'車13:00:00到13:00:01')['properties']
    assert s['class_term']=={'enum':['車']} and s['color_term']=={'const':None}
    assert s['time_literal']['properties']['date']=={'const':None}
    assert s['time_literal']['properties']['start']['enum']==[None,'13:00:00','13:00:01']
    assert s['camera_terms']['maxItems']==0


def test_alias_grounding_preserves_user_case_instead_of_catalog_spelling():
    schema=q3_schema({'camera_aliases':{'A':'A'}},'a13:00:00到13:00:01')
    assert schema['properties']['camera_terms']['items']['enum']==['a']


def test_schema_build_time_is_inside_the_provider_deadline(monkeypatch):
    import amidst.q1q5.llm_provider as module
    clock=[0.0];original=module.generation_request
    def slow(*args):
        result=original(*args);clock[0]=3.0;return result
    monkeypatch.setattr(module,'generation_request',slow)
    p=FakeProvider([],clock=lambda:clock[0]);template=Q3_MARKER+' Parse.'
    with pytest.raises(module.ProviderError) as error:
        p.generate(model=QWEN3_MODEL,prompt=template+'\nCLOSED_CATALOG={}\nUSER_TEXT="車"',template=template,template_version='q3-parse.v2',options={},timeout_ms=2000,expected_digest='a'*64)
    assert error.value.code=='PROVIDER_TIMEOUT' and p.transport.calls==[]

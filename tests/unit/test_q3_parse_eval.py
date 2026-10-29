"""Mechanical scoring probes use existing owner fixtures; no new human testset."""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import pytest
from amidst.evaluation.q1_query_eval import EvaluationError,PinnedSchemas,canonical,decode,sha
from amidst.evaluation.q3_parse_eval import clock_catalog,prediction_rows,evaluate
H='a'*64


@pytest.fixture(scope='module')
def kit():
    root=Path(os.environ['Q1Q5_KIT_ROOT']).resolve();folder=root/'tests/fixtures/q1q5_conformance/SYNTHETIC/valid'
    return root,PinnedSchemas(root/'src/amidst/contracts/q_demo'),clock_catalog({'schema_version':'q-demo.eval-clock-catalog.v1','mappings':[decode((folder/'clock_mapping.json').read_bytes())]})


def pair(kit,name='q3_llm',cid='MECHANICAL'):
    folder=kit[0]/'tests/fixtures/q1q5_conformance/SYNTHETIC/valid'
    response=decode((folder/(name+'.response.json')).read_bytes());request=decode((folder/(name+'.request.json')).read_bytes())
    raw_path=folder/(name+'.llm_output.json')
    if not raw_path.exists():raw_path=folder/'q3_llm.llm_output.json'
    llm=decode(raw_path.read_bytes())
    case={'id':cid,'text':request['text'],'category':'SYNTHETIC_MECHANICAL','expected_llm_output':llm,
          'expected_status':response['status'],'expected_structured_query':deepcopy(response['structured_query'])}
    return case,{'id':cid,'response':response,'llm_output':llm}


def rehash(response):response['output_sha256']=sha(canonical({k:v for k,v in response.items() if k not in {'output_sha256','stats'}}))


def score(kit,cases=None,preds=None,**kwargs):
    c,p=pair(kit);args=dict(cases_sha256=H,predictions_sha256=H,schemas=kit[1],clocks=kit[2],clocks_sha256=H,evaluation_eligible=True,authority_sha256=H);args.update(kwargs)
    return evaluate([c] if cases is None else cases,[p] if preds is None else preds,**args)


def test_semantic_and_literal_fields_all_match_mechanical_fixture(kit):
    r=score(kit);assert r['formal_case_count']==1 and r['status_accuracy']['value']==1
    assert all(v['value']==1 for v in r['field_accuracy'].values()) and all(v['value']==1 for v in r['literal_field_accuracy'].values())
    assert r==score(kit) and r['output_sha256']==sha(canonical({k:v for k,v in r.items() if k!='output_sha256'}))


def test_source_microseconds_equal_wall_conversion_not_string_comparison(kit):
    c,p=pair(kit);mapping=kit[2]['RUN_X'];wall=c['expected_structured_query']['time']['wall_range']
    c['expected_structured_query']['time']={'kind':'SOURCE','run_id':'RUN_X','range_us':[mapping.wall_to_source(x) for x in wall]}
    assert score(kit,[c],[p])['field_accuracy']['time_us']['value']==1
    p['response']['structured_query']['time']['wall_range'][1]='2026-11-01T13:00:20.999999+08:00';rehash(p['response'])
    assert score(kit,[c],[p])['field_accuracy']['time_us']['value']==0


def test_time_outside_run_is_not_clipped_to_hide_difference(kit):
    c,p=pair(kit);c['expected_structured_query']['time']['wall_range'][1]='2026-11-01T14:00:00+08:00'
    p['response']['structured_query']['time']['wall_range'][1]='2026-11-01T15:00:00+08:00';rehash(p['response'])
    assert score(kit,[c],[p])['field_accuracy']['time_us']['value']==0


def test_missing_clock_or_precise_expected_is_invalid_case_not_fabricated_answer(kit):
    r=score(kit,clocks={});assert r['invalid_cases'] and r['formal_case_count']==0
    c,p=pair(kit);c['expected_llm_output']=None;r=score(kit,[c],[p]);assert r['invalid_cases']


def test_missing_raw_intermediate_marks_literal_unavailable(kit):
    c,p=pair(kit);p.pop('llm_output');r=score(kit,[c],[p])
    assert r['field_accuracy']['class']['value']==1 and r['literal_field_accuracy']['class_term']['value'] is None
    assert r['raw_llm_output_availability']['value']==0


def test_missing_invalid_extra_and_duplicate_predictions(kit):
    c,p=pair(kit);r=score(kit,[c],[]);assert r['missing_prediction_ids']==['MECHANICAL'] and r['status_accuracy']['value']==0
    wrong={**p,'id':'EXTRA'};r=score(kit,[c],[wrong]);assert r['extra_prediction_ids']==['EXTRA']
    p['response']={'status':'PARSED'};r=score(kit,[c],[p]);assert r['schema_validity']['value']==0
    with pytest.raises(EvaluationError):score(kit,[c],[p,p])


def test_refusal_precision_recall_and_wrong_refusal_kind_status(kit):
    c,p=pair(kit,'q3_clarify');r=score(kit,[c],[p]);assert r['refusal']['TP']==1 and r['refusal']['recall']['value']==1
    p['response']['status']='PARSE_FAILED';rehash(p['response']);r=score(kit,[c],[p]);assert r['status_accuracy']['value']==0 and r['refusal']['TP']==1


def test_nonparsed_with_query_is_not_executed_or_credited(kit):
    c,p=pair(kit,'q3_clarify');p['response']['structured_query']=pair(kit)[1]['response']['structured_query'];rehash(p['response']);r=score(kit,[c],[p])
    assert r['status_accuracy']['value']==0


def test_hash_failure_and_pilot_have_no_false_credit(kit):
    c,p=pair(kit);p['response']['output_sha256']='0'*64;r=score(kit,[c],[p]);assert r['hash_validity']['value']==0 and r['status_accuracy']['value']==0
    r=score(kit,evaluation_eligible=False);assert r['formal_case_count']==0 and r['status_accuracy']['value'] is None


def test_fallback_rate_uses_valid_prediction_denominator(kit):
    c,p=pair(kit,'q3_fallback');r=score(kit,[c],[p]);assert r['fallback_rate']['value']==1


def test_explicit_layouts_and_order_count_gate(kit):
    c,p=pair(kit);assert prediction_rows([c],[p['response']],'dataset-order')==[{'id':c['id'],'response':p['response']}]
    with pytest.raises(EvaluationError):prediction_rows([c],[],'dataset-order')
    assert prediction_rows([c],[p],'id-wrapper')==[p]


def test_duplicate_or_wrong_clock_catalog_rejected(kit):
    mapping=dict(kit[2]['RUN_X'].document)
    with pytest.raises(EvaluationError):clock_catalog({'schema_version':'q-demo.eval-clock-catalog.v1','mappings':[mapping,mapping]})
    with pytest.raises(EvaluationError):clock_catalog({})


def test_cli_pins_authority_and_creates_only_new_report(kit,tmp_path):
    spec=importlib.util.spec_from_file_location('q3_eval_cli',Path(__file__).resolve().parents[2]/'scripts/eval_q3_parse.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);c,p=pair(kit)
    values={'queries':canonical(c)+b'\n','predictions':canonical(p)+b'\n','clocks':canonical({'schema_version':'q-demo.eval-clock-catalog.v1','mappings':[dict(kit[2]['RUN_X'].document)]})}
    values['dataset-receipt']=canonical({'schema_version':'q-demo.synthetic-evaluation-dataset.v1','kind':'SYNTHETIC','cases_sha256':sha(values['queries'])})
    args=[]
    for name,raw in values.items():
        file=tmp_path/(name+'.json');file.write_bytes(raw);args.extend(['--'+name,str(file),'--'+name+'-sha256',sha(raw)])
    args+=['--schemas',str(kit[0]/'src/amidst/contracts/q_demo'),'--prediction-layout','id-wrapper','--output',str(tmp_path/'report.json')]
    assert module.main(args)==0 and decode((tmp_path/'report.json').read_bytes())['status_accuracy']['value']==1
    with pytest.raises(SystemExit):module.main(args)

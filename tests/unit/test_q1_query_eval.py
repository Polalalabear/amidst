"""Mechanical scoring probes using owner-supplied #127 fixtures, not a question bank."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import pytest
from amidst.evaluation.q1_query_eval import (
    EvaluationError,PinnedSchemas,canonical,decode,rows,sha,dataset_eligibility,evaluate,
)
H='a'*64


@pytest.fixture(scope='module')
def kit():
    root=Path(os.environ['Q1Q5_KIT_ROOT']).resolve()
    return root,PinnedSchemas(root/'src/amidst/contracts/q_demo')


def pair(kit,name='q1_ready',cid='MECHANICAL'):
    root,schemas=kit;folder=root/'tests/fixtures/q1q5_conformance/SYNTHETIC/valid'
    request=decode((folder/(name+'.request.json')).read_bytes());response=decode((folder/(name+'.response.json')).read_bytes())
    core={k:deepcopy(response[k]) for k in ['status','reason','results','no_match_cameras','not_evaluated_cameras']}
    case={'id':cid,'index_ref':'SYNTHETIC_FIXTURE_ONLY','request':request,'expected_response_core':core}
    return case,{'id':cid,'response':response}


def score(kit,cases=None,predictions=None,eligible=True):
    c,p=pair(kit)
    return evaluate([c] if cases is None else cases,[p] if predictions is None else predictions,
                    cases_sha256=H,predictions_sha256=H,schemas=kit[1],evaluation_eligible=eligible,authority_sha256=H)


def rehash(response):response['output_sha256']=sha(canonical({k:v for k,v in response.items() if k not in {'output_sha256','stats'}}))


def test_identity_mechanical_probe_uses_full_schema_and_reproduces_hash(kit):
    r=score(kit);assert r['formal_case_count']==1 and r['metrics']['status']['value']==1
    assert all(x['value']==1 for x in r['metrics'].values()) and r['camera_micro_recall']['value']==1
    assert r==score(kit) and r['output_sha256']==sha(canonical({k:v for k,v in r.items() if k!='output_sha256'}))


def test_wrong_status_and_dropped_camera_measured_separately(kit):
    c,p=pair(kit);p['response']['status']='PARTIAL';p['response']['results']=[];p['response']['returned_count']=0;p['response']['results_total']=0;rehash(p['response']);r=score(kit,[c],[p])
    assert r['metrics']['status']['value']==0 and r['camera_micro_recall']['value']==0


def test_schema_invalid_prediction_is_not_treated_as_valid_partial_answer(kit):
    c,p=pair(kit);p['response']={'status':'READY'};r=score(kit,[c],[p])
    assert r['metrics']['schema']['value']==0 and r['metrics']['status']['value']==0 and r['details'][0]['schema_errors']


def test_canonical_hash_mismatch_is_not_scored_as_correct(kit):
    c,p=pair(kit);p['response']['output_sha256']='0'*64;r=score(kit,[c],[p])
    assert r['metrics']['schema']['value']==1 and r['metrics']['hash']['value']==0
    assert r['metrics']['status']['value']==0 and r['details'][0]['integrity_errors']


def test_missing_extra_and_duplicate_predictions_explicit(kit):
    c,p=pair(kit);extra={**p,'id':'EXTRA'};r=score(kit,[c],[extra])
    assert r['missing_prediction_ids']==['MECHANICAL'] and r['extra_prediction_ids']==['EXTRA']
    assert r['metrics']['status']['value']==0
    with pytest.raises(EvaluationError):score(kit,[c],[p,p])
    with pytest.raises(EvaluationError):score(kit,[c,c],[p])


def test_missing_precise_human_core_is_invalid_not_model_error(kit):
    c,p=pair(kit);c['expected_response_core']={'status':'READY'};r=score(kit,[c],[p])
    assert r['invalid_cases'][0]['status']=='INVALID' and r['formal_case_count']==0 and r['metrics']['status']['value'] is None


def test_pilot_cannot_enter_formal_denominators(kit):
    r=score(kit,eligible=False);assert r['formal_case_count']==0 and r['valid_case_count']==1
    assert r['status']=='NO_FORMAL_CASES' and r['metrics']['schema']['value'] is None


def test_none_categories_confusion_detected(kit):
    c,p=pair(kit,'q1_nomatch');p['response']['not_evaluated_cameras']=p['response']['no_match_cameras'];p['response']['no_match_cameras']=[];rehash(p['response']);r=score(kit,[c],[p])
    # Full schema rejects an object with the wrong category fields; either way no credit.
    assert r['metrics']['none_categories']['value']==0


def test_origin_pair_identical_output_passes_and_changed_hash_fails(kit):
    c,p=pair(kit);c2=deepcopy(c);c2['id']='SECOND';c2['request']['origin']='PREFILL';p2={**deepcopy(p),'id':'SECOND'}
    r=score(kit,[c,c2],[p,p2]);assert r['origin_invariance']['value']==1
    p2['response']['reason']='SYNTHETIC_DIFFERENCE';rehash(p2['response']);assert score(kit,[c,c2],[p,p2])['origin_invariance']['value']==0


def test_order_and_coverage_are_separate_metrics(kit):
    c,p=pair(kit);p['response']['results'][0]['coverage']['evaluated_frames']+=1;rehash(p['response']);r=score(kit,[c],[p])
    assert r['metrics']['coverage']['value']==0 and r['metrics']['order']['value']==1


@pytest.mark.parametrize('change',[{'pack_version':'v1','evaluation_eligible':False},{'evaluation_eligible':True},{'output_files_sha256':{'cases_v1.jsonl':'0'*64}}])
def test_receipt_scope_and_pilot_tamper_rejected(change):
    r={'schema_version':'team-review-import.v1','pack_version':'v0-pilot','evaluation_eligible':False,'output_files_sha256':{'cases_v1.jsonl':H}};r.update(change)
    with pytest.raises(EvaluationError):dataset_eligibility(r,cases_sha256=H,filename='cases_v1.jsonl')


def test_verified_pilot_receipt_retains_ineligibility():
    r={'schema_version':'team-review-import.v1','pack_version':'v0-pilot','evaluation_eligible':False,'output_files_sha256':{'cases_v1.jsonl':H}}
    assert dataset_eligibility(r,cases_sha256=H,filename='cases_v1.jsonl') is False


def test_readonly_schema_pins_reject_modified_file(kit,tmp_path):
    root=kit[0]/'src/amidst/contracts/q_demo';copy=tmp_path/'schemas';shutil.copytree(root,copy)
    (copy/'schemas/q1-response.v1.schema.json').write_text('{}')
    with pytest.raises(EvaluationError):PinnedSchemas(copy)


@pytest.mark.parametrize('raw',[b'{"id":"x","id":"y"}',b'NaN',b'{}\n\n',b'[]\n'])
def test_invalid_jsonl_fails_closed(raw):
    with pytest.raises(EvaluationError):rows(raw)


@pytest.mark.parametrize('name',['q1_nomatch','q1_partial','q1_unsupported','q1_oor','q1_color_car'])
def test_owner_fixture_core_projection_and_full_prediction_schema(kit,name):
    c,p=pair(kit,name);r=score(kit,[c],[p])
    assert not r['invalid_cases'] and r['metrics']['status']['value']==1 and r['metrics']['schema']['value']==1


def test_incomplete_expected_counters_cannot_claim_ready(kit):
    c,p=pair(kit);c['expected_response_core']['results'][0]['coverage']['missing_frames']=1
    assert score(kit,[c],[p])['invalid_cases']


def test_cli_uses_authority_pin_and_refuses_report_overwrite(kit,tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('q1_eval_cli',Path(__file__).resolve().parents[2]/'scripts/eval_q1_query.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    c,p=pair(kit);cases=tmp_path/'cases.jsonl';pred=tmp_path/'predictions.jsonl';record=tmp_path/'authority.json';out=tmp_path/'report.json'
    cases.write_bytes(canonical(c)+b'\n');pred.write_bytes(canonical(p)+b'\n')
    record.write_bytes(canonical({'schema_version':'q-demo.synthetic-evaluation-dataset.v1','kind':'SYNTHETIC','cases_sha256':sha(cases.read_bytes())}))
    args=['--cases',str(cases),'--cases-sha256',sha(cases.read_bytes()),'--predictions',str(pred),'--predictions-sha256',sha(pred.read_bytes()),'--dataset-receipt',str(record),'--dataset-receipt-sha256',sha(record.read_bytes()),'--schemas',str(kit[0]/'src/amidst/contracts/q_demo'),'--output',str(out)]
    assert module.main(args)==0 and decode(out.read_bytes())['metrics']['status']['value']==1
    with pytest.raises(SystemExit):module.main(args)
    args[-1]=str(tmp_path/'other.json');pred.write_bytes(pred.read_bytes()+b' ')
    with pytest.raises(SystemExit):module.main(args)
    assert not (tmp_path/'other.json').exists()

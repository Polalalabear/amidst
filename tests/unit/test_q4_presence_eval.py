"""Mechanical synthetic counters and pin tests; no authored question/answer bank."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from amidst.evaluation.q4_presence_eval import (
    EvaluationError, canonical, decode_jsonl, score_reviews, select_claims, sha,
)
H = 'a' * 64


def manifest(pilot=False):
    return {'schema_version':'team-review-pack.v1','version':'v0-pilot' if pilot else 'v1',
            'evaluation_eligible':not pilot,'samples':[
                {'sample_id':str(i),'run_id':'SYNTHETIC_RUN','camera_id':'SYNTHETIC_CAM',
                 'frame_index':i,'rgb_file_sha256':H,'prediction_sha256':H,'system_positive':i<2}
                for i in range(4)]}


def reviews(pilot=False):
    # T/F here exercises truth-table arithmetic, not image labels or questions.
    return [dict(sample,schema_version='q4-tf-review.v1',frame_ref=f"frame:SYNTHETIC_RUN:SYNTHETIC_CAM:{i}",
                 pilot=pilot,evaluation_eligible=not pilot,statement='SYNTHETIC frozen predicate',
                 answer='T' if i%2==0 else 'F') for i,sample in enumerate(manifest(pilot)['samples'])]


def score(rows=None,m=None):
    return score_reviews(reviews() if rows is None else rows,manifest() if m is None else m,
                         reviews_sha256=H,manifest_sha256=H)


def claims():
    return [dict(run_id='SYNTHETIC_RUN',clock_id='SYNTHETIC_CLOCK',camera_id='SYNTHETIC_CAM',
                 frame_index=i,polarity=i%2==0,statement='SYNTHETIC predicate',
                 prediction_ref='SYNTHETIC',prediction_sha256=H,rgb_file_sha256=H) for i in range(12)]


def test_four_truth_table_cells_include_false_negative_on_negative_statement():
    r=score();assert r['confusion']=={'TP':1,'FP':1,'TN':1,'FN':1}
    assert r['precision']==r['recall']=={'numerator':1,'denominator':2,'value':.5}
    assert r['accuracy']['value']==.5 and r['formal_decided_count']==4
    assert r==score() and sha(canonical({k:v for k,v in r.items() if k!='output_sha256'}))==r['output_sha256']


def test_uncertain_excluded_and_never_auto_false_or_negative():
    rows=reviews();rows[0]['answer']='不確定';r=score(rows)
    assert r['formal_decided_count']==3 and r['excluded']['uncertain']==1 and r['confusion']['TP']==0
    assert r['review_coverage']['value']==1 and r['formal_decided_coverage']['value']==.75


def test_pilot_never_enters_formal_denominator_even_with_decided_labels():
    r=score(reviews(True),manifest(True));assert r['status']=='NO_FORMAL_LABELS'
    assert r['formal_decided_count']==0 and r['excluded']['pilot']==4 and r['precision']['value'] is None


def test_missing_and_all_missing_reviews_are_explicit():
    r=score(reviews()[:1]);assert r['missing_review_count']==3 and r['review_coverage']['value']==.25
    r=score([]);assert r['missing_review_count']==4 and r['formal_decided_count']==0 and r['accuracy']['value'] is None
    assert decode_jsonl(b'')==[]


@pytest.mark.parametrize('case',['duplicate','unknown','frame','rgb','prediction','polarity','truth_type','pilot','answer','schema','statement'])
def test_tampered_or_invalid_return_cannot_be_scored(case):
    rows=reviews()
    if case=='duplicate':rows.append(deepcopy(rows[0]))
    elif case=='unknown':rows[0]['sample_id']='OUTSIDE'
    else:
        field,value={'frame':('frame_ref','frame:OTHER'), 'rgb':('rgb_file_sha256','b'*64),
                     'prediction':('prediction_sha256','b'*64),'polarity':('system_positive',False),
                     'truth_type':('system_positive',1),'pilot':('pilot',True),
                     'answer':('answer','yes'),'schema':('schema_version','OTHER'),'statement':('statement','')}[case]
        rows[0][field]=value
    with pytest.raises(EvaluationError):score(rows)


def test_balanced_sampling_is_reproducible_order_independent_without_replacement():
    rows=claims();a=select_claims(rows,count=8,seed='predeclared',claims_sha256=H)
    b=select_claims(list(reversed(rows)),count=8,seed='predeclared',claims_sha256=H)
    assert a==b and a['actual']==8 and sum(x['polarity'] for x in a['selected'])==4
    assert len({x['frame_index'] for x in a['selected']})==8


def test_stratum_shortfall_reduces_both_pools_and_reports_missing():
    rows=claims()[:3];r=select_claims(rows,count=8,seed='SYNTHETIC',claims_sha256=H)
    assert r['actual']==2 and r['shortfall']==6


@pytest.mark.parametrize('case',['duplicate','one_stratum','answers','gt','missing_pin','count','seed','not_object'])
def test_sampler_refuses_invalid_scope_and_answer_informed_input(case):
    rows=claims();kw=dict(count=4,seed='SYNTHETIC',claims_sha256=H)
    if case=='duplicate':rows.append(deepcopy(rows[0]))
    elif case=='one_stratum':rows=[x for x in rows if x['polarity']]
    elif case=='answers':rows[0]['answer']='T'
    elif case=='gt':rows[0]['actor_id']='FORBIDDEN'
    elif case=='missing_pin':rows[0]['rgb_file_sha256']=None
    elif case=='count':kw['count']=3
    elif case=='seed':kw['seed']=''
    elif case=='not_object':rows=[None]
    with pytest.raises(EvaluationError):select_claims(rows,**kw)


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}\n',b'{}\n\n',b'[]\n',b'{"x":NaN}\n'])
def test_jsonl_rejects_duplicate_blank_nonobject_and_nonfinite(raw):
    with pytest.raises(EvaluationError):decode_jsonl(raw)


def cli():
    path=Path(__file__).resolve().parents[2]/'scripts/eval_q4_presence.py'
    spec=importlib.util.spec_from_file_location('q4_eval_cli',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_cli_checks_exact_bytes_and_refuses_existing_report(tmp_path):
    m=tmp_path/'manifest.json';r=tmp_path/'reviews.jsonl';out=tmp_path/'report.json'
    m.write_bytes(canonical(manifest()));r.write_bytes(b''.join(canonical(x)+b'\n' for x in reviews()))
    args=['score','--reviews',str(r),'--reviews-sha256',sha(r.read_bytes()),'--manifest',str(m),'--manifest-sha256',sha(m.read_bytes()),'--output',str(out)]
    assert cli().main(args)==0 and json.loads(out.read_bytes())['confusion']['FN']==1
    with pytest.raises(SystemExit):cli().main(args)
    out2=tmp_path/'bad.json';args[-1]=str(out2);r.write_bytes(r.read_bytes()+b' ')
    with pytest.raises(SystemExit):cli().main(args)
    assert not out2.exists()


def test_pilot_version_cannot_be_relabelled_as_formal():
    m=manifest(True);m['evaluation_eligible']=True
    with pytest.raises(EvaluationError):score(reviews(),m)

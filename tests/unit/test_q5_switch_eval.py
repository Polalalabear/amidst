"""Mechanical timestamps/actions only; no demo question or script answer bank."""
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from amidst.evaluation.q5_switch_eval import (
    EvaluationError,
    canonical,
    compare_script,
    digest,
    freeze_output,
    sha,
)


def outputs():
    row={'schema_version':'q-demo.decision-record.v1','session_id':'SYNTHETIC','decision_id':'D',
         'step_index':0,'source_time_us':30,'decision_time_us':20,'executed_action':'SWITCH',
         'executed_candidate_ref':'SYNTHETIC_CANDIDATE','entry_observation_id':'SYNTHETIC_OBSERVATION',
         'accepted':True,'decided_by':'RULE_ONLY','stats':{'latency_ms':{'fallback':9}}}
    row['content_sha256']=digest(row,'content_sha256');raw=canonical(row)+b'\n'
    response={'schema_version':'q-demo.q2-response.v1','session_id':'SYNTHETIC','status':'COMPLETE',
              'resolved_scope':{'run_ids':['SYNTHETIC_RUN'],'clock_ids':['SYNTHETIC_CLOCK'],'resolved_source_ranges_us':[{'run_id':'SYNTHETIC_RUN','range_us':[0,60]}]},
              'decisions_sha256':sha(raw),'agent_used':False,'fallback_used':False,
              'timeline':[{'segment_id':'S','kind':'ON_CAMERA','range_us':[30,60],
                           'entered_by':'SWITCH','decision_id':'D','camera_id':'C',
                           'observation_ids':['SYNTHETIC_OBSERVATION']}]}
    response['output_sha256']=digest(response,'output_sha256');return response,[row]


def freeze(response=None,records=None):
    r,rows=outputs();r=response or r;rows=rows if records is None else records
    raw=b''.join(canonical(row)+b'\n' for row in rows);r=deepcopy(r);r['decisions_sha256']=sha(raw);r['output_sha256']=digest(r,'output_sha256');rr=canonical(r)
    return freeze_output(rr,raw,expected_response_sha256=sha(rr),expected_decisions_sha256=sha(raw))


def script(action='SWITCH'):
    return {'schema_version':'q5-evaluation-script.v1','status':'PROPOSED','approval_ref':None,
            'run_id':'SYNTHETIC_RUN','clock_id':'SYNTHETIC_CLOCK','events':[
                {'event_id':'MECHANICAL','action':action,'decision_window_us':[20,21],
                 'entry_window_us':[30,31],'allowed_camera_ids':['C']}]}


def compare(frozen=None,doc=None):
    raw=canonical(doc or script());return compare_script(frozen or freeze(),raw,expected_script_sha256=sha(raw))


def test_v2_explicit_time_scores_and_default_run_keeps_observations_without_score():
    r,records=outputs();r['schema_version']='q-demo.q2-response.v2'
    r['resolved_scope'].update(requested_time={'kind':'SOURCE','run_id':'SYNTHETIC_RUN','range_us':[0,60]},
                               time_range_source='EXPLICIT_SOURCE')
    report=compare(freeze(r,records));assert report['event_match_ratio']['value']==1
    r['resolved_scope']['time_range_source']='DEFAULT_SELECTED_RUN'
    report=compare(freeze(r,records));assert report['status']=='NOT_SCORED_DEFAULT_SELECTED_RUN'
    assert report['event_match_ratio']['denominator']==0 and report['matched_events']==0
    assert report['events'][0]['observed'] and report['events'][0]['reason']=='DEFAULT_SELECTED_RUN'
    assert report['coverage_missing_event_ids']==[]


@pytest.mark.parametrize('source',[None,'EXPLICIT_WALL','wrong'])
def test_v2_missing_or_mismatched_time_origin_fails_closed(source):
    r,records=outputs();r['schema_version']='q-demo.q2-response.v2'
    r['resolved_scope']['requested_time']={'kind':'SOURCE','run_id':'SYNTHETIC_RUN','range_us':[0,60]}
    if source is not None:r['resolved_scope']['time_range_source']=source
    with pytest.raises(EvaluationError,match='time_range_source'):freeze(r,records)


def test_camera_and_entry_time_match_reports_measurement_without_approval():
    r=compare();assert r['matched_events']==1 and r['script_status']=='PROPOSED'
    assert r['status']=='MEASURED_PROPOSED_SCRIPT' and r['acceptance_threshold'] is None
    assert r==compare() and r['output_sha256']==digest(r,'output_sha256')


@pytest.mark.parametrize('change',[{'allowed_camera_ids':['OTHER']},{'entry_window_us':[31,32]},{'decision_window_us':[21,22]}])
def test_wrong_camera_time_and_missing_decision_fail_event_comparison(change):
    d=script();d['events'][0].update(change);r=compare(doc=d);assert r['matched_events']==0


def test_no_switch_window_catches_unwanted_switch_and_other_windows_report_extras():
    r=compare(doc=script('NO_SWITCH'));assert r['matched_events']==0
    d=script('NO_SWITCH');d['events'][0]['decision_window_us']=[0,10];r=compare(doc=d)
    assert r['matched_events']==1 and r['uncovered_executed_count']==1


def test_return_action_compared_without_inventing_destination_or_identity():
    r,rows=outputs();rows[0].update(executed_action='RETURN_TO_ORIGIN',entry_observation_id=None,executed_candidate_ref=None)
    rows[0]['content_sha256']=digest(rows[0],'content_sha256');r['timeline']=[]
    result=compare(freeze(r,rows),script('RETURN_TO_ORIGIN'));assert result['matched_events']==1


@pytest.mark.parametrize('case',['file_pin','response_hash','decision_hash','rejected','backdate','session','step','frame_entry','missing_entry','orphan_entry'])
def test_integrity_failures_never_turn_into_bad_accuracy(case):
    r,rows=outputs()
    if case=='file_pin':
        with pytest.raises(EvaluationError):freeze_output(canonical(r),canonical(rows[0])+b'\n',expected_response_sha256='0'*64,expected_decisions_sha256='0'*64)
        return
    if case=='response_hash':
        r['output_sha256']='0'*64;raw=canonical(rows[0])+b'\n'
        with pytest.raises(EvaluationError):freeze_output(canonical(r),raw,expected_response_sha256=sha(canonical(r)),expected_decisions_sha256=sha(raw))
        return
    if case=='decision_hash':rows[0]['content_sha256']='0'*64
    elif case=='rejected':rows[0]['accepted']=False
    elif case=='backdate':rows[0]['source_time_us']=19
    elif case=='session':rows[0]['session_id']='OTHER'
    elif case=='step':rows.append(deepcopy(rows[0]))
    elif case=='frame_entry':r['timeline'][0]['observation_ids']=['OTHER']
    elif case=='missing_entry':r['timeline']=[]
    elif case=='orphan_entry':rows[0]['executed_action']=None
    if case!='decision_hash':
        for row in rows:row['content_sha256']=digest(row,'content_sha256')
    with pytest.raises(EvaluationError):compare(freeze(r,rows))


@pytest.mark.parametrize('case',['scope','overlap','no_camera','no_entry_window','unapproved_ref','schema','script_pin'])
def test_ambiguous_or_unpinned_script_rejected(case):
    d=script()
    if case=='scope':d['clock_id']='OTHER'
    elif case=='overlap':d['events'].append({**d['events'][0],'event_id':'SECOND'})
    elif case=='no_camera':d['events'][0]['allowed_camera_ids']=[]
    elif case=='no_entry_window':d['events'][0]['entry_window_us']=None
    elif case=='unapproved_ref':d['status']='APPROVED'
    elif case=='schema':d['schema_version']='production-event-script'
    else:
        with pytest.raises(EvaluationError):compare_script(freeze(),canonical(d),expected_script_sha256='0'*64)
        return
    with pytest.raises(EvaluationError):compare(doc=d)


def test_approved_script_is_measured_only_with_explicit_approval_ref():
    d=script();d.update(status='APPROVED',approval_ref='SYNTHETIC_APPROVAL')
    assert compare(doc=d)['status']=='MEASURED_APPROVED_SCRIPT'


def test_cli_does_not_open_script_when_output_pin_fails(tmp_path,monkeypatch):
    path=Path(__file__).resolve().parents[2]/'scripts/eval_q5_switch.py'
    spec=importlib.util.spec_from_file_location('q5_eval_cli',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    r,rows=outputs();response=tmp_path/'response.json';decisions=tmp_path/'decisions.jsonl';secret=tmp_path/'script.json'
    response.write_bytes(canonical(r));decisions.write_bytes(canonical(rows[0])+b'\n')
    original=Path.read_bytes;opened=[]
    def read(file):opened.append(file);return original(file)
    monkeypatch.setattr(Path,'read_bytes',read)
    with pytest.raises(SystemExit):module.main(['--response',str(response),'--response-sha256','0'*64,
        '--decisions',str(decisions),'--decisions-sha256','0'*64,'--script',str(secret),
        '--script-sha256','0'*64,'--output',str(tmp_path/'report.json')])
    assert secret not in opened


def test_script_window_outside_query_is_scope_error_not_model_failure():
    d=script();d['events'][0]['decision_window_us']=[60,70]
    with pytest.raises(EvaluationError):compare(doc=d)


def test_timeline_overlap_and_scripted_gap_position_rejected():
    r,rows=outputs();r['timeline'].append({'kind':'GAP','range_us':[40,50],'position':[1,2]})
    with pytest.raises(EvaluationError):compare(freeze(r,rows))


@pytest.mark.parametrize('empty',[True,False])
def test_no_switch_empty_or_interrupted_session_is_not_a_correct_negative(empty):
    r,rows=outputs();r['timeline']=[]
    rows=[] if empty else rows
    if rows:
        rows[0].update(executed_action=None,decision_time_us=None,source_time_us=10)
        rows[0]['content_sha256']=digest(rows[0],'content_sha256')
    result=compare(freeze(r,rows),script('NO_SWITCH'))
    assert result['decision_count']==len(rows)
    assert result['events'][0]['match'] is None
    assert result['events'][0]['reason']=='COVERAGE_MISSING'
    assert result['event_match_ratio']=={'numerator':0,'denominator':0,'value':None}


def test_no_switch_with_explicit_window_end_coverage_is_scoreable():
    r,rows=outputs();r['timeline']=[]
    rows[0].update(executed_action=None,decision_time_us=None,source_time_us=21)
    rows[0]['content_sha256']=digest(rows[0],'content_sha256')
    result=compare(freeze(r,rows),script('NO_SWITCH'))
    assert result['matched_events']==1 and result['event_match_ratio']['denominator']==1
    assert result['by_decided_by']['OTHER']['event_match_ratio']['value']==1
    assert result['fallback_only_event_match_ratio']['denominator']==0


@pytest.mark.parametrize('status',['UNKNOWN','NO_SEED','ENDED_BY_LIMIT','PARTIAL','FAILED',None])
def test_non_complete_response_cannot_be_scored(status):
    r,rows=outputs();r['status']=status
    with pytest.raises(EvaluationError,match='Only COMPLETE'):
        freeze(r,rows)


def test_rejected_return_cannot_be_scored_as_an_executed_return():
    r,rows=outputs();r['timeline']=[]
    rows[0].update(executed_action='RETURN_TO_ORIGIN',accepted=False)
    rows[0]['content_sha256']=digest(rows[0],'content_sha256')
    with pytest.raises(EvaluationError,match='Rejected return'):
        freeze(r,rows)


@pytest.mark.parametrize('source,group',[('RULE_ONLY','RULE_ONLY'),('AGENT','AGENT'),
                                      ('RULE_FALLBACK','FALLBACK'),('FALLBACK','FALLBACK')])
def test_decision_source_has_separate_counts_and_event_denominators(source,group):
    r,rows=outputs();rows[0]['decided_by']=source
    rows[0]['content_sha256']=digest(rows[0],'content_sha256')
    result=compare(freeze(r,rows))
    assert result['events'][0]['observed'][0]['decided_by']==source
    assert result['by_decided_by'][group]['decision_count']==1
    assert result['by_decided_by'][group]['event_match_ratio']['value']==1
    assert result['fallback_only_event_match_ratio']['denominator']==int(group=='FALLBACK')
    assert result['non_fallback_event_match_ratio']['denominator']==int(group!='FALLBACK')


@pytest.mark.parametrize('failure',['response_hash','decisions_binding'])
def test_cli_does_not_read_script_when_frozen_content_or_binding_fails(tmp_path,monkeypatch,failure):
    path=Path(__file__).resolve().parents[2]/'scripts/eval_q5_switch.py'
    spec=importlib.util.spec_from_file_location('q5_eval_cli_binding',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    r,rows=outputs();decisions_raw=canonical(rows[0])+b'\n'
    if failure=='response_hash':r['output_sha256']='0'*64
    else:
        r['decisions_sha256']='0'*64;r['output_sha256']=digest(r,'output_sha256')
    response=tmp_path/'response.json';decisions=tmp_path/'decisions.jsonl';secret=tmp_path/'script.json'
    response.write_bytes(canonical(r));decisions.write_bytes(decisions_raw)
    original=Path.read_bytes;opened=[]
    def read(file):opened.append(file);return original(file)
    monkeypatch.setattr(Path,'read_bytes',read)
    with pytest.raises(SystemExit):module.main(['--response',str(response),
        '--response-sha256',sha(canonical(r)),'--decisions',str(decisions),
        '--decisions-sha256',sha(decisions_raw),'--script',str(secret),
        '--script-sha256','0'*64,'--output',str(tmp_path/'report.json')])
    assert secret not in opened


def test_runtime_does_not_import_evaluation_modules():
    import ast
    runtime=Path(__file__).resolve().parents[2]/'src/amidst/q1q5'
    files=list(runtime.rglob('*.py'));assert files
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node,ast.Import):
                assert all(not alias.name.startswith('amidst.evaluation') for alias in node.names),path
            elif isinstance(node,ast.ImportFrom):
                assert not (node.module or '').startswith(('amidst.evaluation','evaluation')),path

"""Mechanical timestamps/actions only; no demo question or script answer bank."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest
from amidst.evaluation.q5_switch_eval import (
    EvaluationError,canonical,digest,sha,freeze_output,compare_script,
)


def outputs():
    row={'schema_version':'q-demo.decision-record.v1','session_id':'SYNTHETIC','decision_id':'D',
         'step_index':0,'source_time_us':30,'decision_time_us':20,'executed_action':'SWITCH',
         'executed_candidate_ref':'SYNTHETIC_CANDIDATE','entry_observation_id':'SYNTHETIC_OBSERVATION',
         'accepted':True,'decided_by':'RULE_ONLY','stats':{'latency_ms':{'fallback':9}}}
    row['content_sha256']=digest(row,'content_sha256');raw=canonical(row)+b'\n'
    response={'schema_version':'q-demo.q2-response.v1','session_id':'SYNTHETIC',
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

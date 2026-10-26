"""D78 engineering checks; independent labels and identity truth stay unknown."""
import json
import threading
import time

import pytest
from test_api import OTHER, TOKEN, api_fixture, authorize, q2
from test_linker import linker, observation, record
from test_q5_agent import PolicyProvider, auto, run_agent
from test_q5_controller import file_hash, seed_id
from test_q5_controller import run as rule_run

from amidst.q1q5.api import APIError
from amidst.q1q5.linker import LinkError
from amidst.q1q5.store import canonical_hash


def moving():
    tracker = linker()
    tracker.step(record(1, obs=[observation(1, box=[4, 0, 14, 10])]))
    tracker.step(record(2))
    tracker.step(record(3, 'MISSING'))
    return tracker


def test_prediction_reacquires_at_600ms_without_fabricating_missing_boxes():
    tracker = moving()
    result = tracker.step(record(4, obs=[observation(4, box=[16, 0, 26, 10])]))
    audit = result.link['matching_audit']
    assert result.state == 'PLAYING' and result.link['gap_samples'] == 2
    assert audit['method'] == 'CENTER_TRANSLATION_V1' and audit['event'] == 'REACQUIRED'
    assert audit['actual_pair_iou'] == result.link['iou'] == 0
    assert audit['reference_iou'] == 1
    assert audit['elapsed_us'] == 600000 and audit['reference_bbox_xyxy_px'] == [16,0,26,10]
    assert [o['timestamp_us'] for o in audit['source_observations']] == [0,200000]
    assert result.link['next_observation_id'] == observation(4)['observation_id']
    assert tracker.history[-1][0] == 800000 and audit['identity_verdict'] == 'UNCONFIRMED'


@pytest.mark.parametrize('score,verdict,label',[(.399,'STRONG','person'),(.9,'STRONG','car')])
def test_motion_cannot_bypass_score_or_class(score,verdict,label):
    tracker=moving()
    r=tracker.step(record(4,obs=[observation(4,box=[16,0,26,10],score=score,verdict=verdict,label=label)]))
    assert r.state=='SEARCHING' and r.link['next_observation_id'] is None
    with pytest.raises(LinkError,match='Segment ended'):
        tracker.step(record(5,obs=[observation(5)]))


def test_prediction_ambiguity_never_selects_one_candidate():
    tracker=moving()
    r=tracker.step(record(4,obs=[observation(4,i,box=[16,0,26,10]) for i in [0,1]]))
    assert r.state=='SEARCHING' and r.link['decision']=='AMBIGUOUS_LINK'
    assert len(r.ambiguous_observation_ids)==2 and r.link['next_observation_id'] is None


def test_single_history_cannot_invent_velocity_and_normal_link_is_unchanged():
    tracker=linker()
    r=tracker.step(record(1,obs=[observation(1,box=[20,0,30,10])]))
    assert r.state=='TEMP_LOST' and 'matching_audit' not in r.link
    tracker=linker();r=tracker.step(record(1,obs=[observation(1)]))
    assert r.state=='PLAYING' and 'matching_audit' not in r.link


@pytest.mark.parametrize('agent',[False,True])
def test_switch_has_two_stages_one_choice_and_cause_binding(agent):
    result=run_agent()[1] if agent else rule_run()[0]
    rows=[json.loads(x) for x in result.decisions_bytes.splitlines()]
    switch=next(d for d in rows if d['executed_action']=='SWITCH')
    entry=next(d for d in rows if d.get('cause_decision_id')==switch['decision_id'])
    assert (switch['state_before'],switch['state_after'])==('SEARCHING','SWITCHING')
    assert (entry['state_before'],entry['state_after'])==('SWITCHING','PLAYING')
    for key in ['candidate_snapshot_sha256','entry_observation_id','executed_candidate_ref','decision_time_us']:
        assert switch[key]==entry[key]
    assert switch['source_time_us']<=entry['source_time_us'] and entry['executed_action'] is None
    assert switch['session_agent_rounds_used']==entry['session_agent_rounds_used']
    assert file_hash(result.decisions_bytes)==result.response['decisions_sha256']
    assert canonical_hash(result.response,exclude=('output_sha256','stats'))==result.response['output_sha256']


def wait_for(predicate):
    deadline=time.monotonic()+5
    while not predicate():
        assert time.monotonic()<deadline
        time.sleep(.005)


@pytest.mark.parametrize('blocked_phase',['provider','publication'])
def test_stop_generation_rejects_late_worker_and_preserves_stop_journal(blocked_phase):
    api,run=api_fixture(agent=True);entered,release=threading.Event(),threading.Event()
    original_controller,original_bundle=api._controller,api._bundle
    controllers=[]
    def controller(*args,**kwargs):
        value=original_controller(*args,**kwargs);controllers.append(value)
        if blocked_phase=='provider':
            original=value.provider.generate
            def delayed(**kw):
                entered.set();assert release.wait(5);return original(**kw)
            value.provider.generate=delayed
        return value
    def bundle(*args,**kwargs):
        if blocked_phase=='publication':entered.set();assert release.wait(5)
        return original_bundle(*args,**kwargs)
    api._controller,api._bundle=controller,bundle
    request=q2(run);request['switch_mode']='AGENT_SEQUENTIAL'
    job=api.call('q2_start_session',{'request':request,'selected_observation_id':seed_id(run.bindings)},authorize)
    base={'session_ref':TOKEN,'response_ref':job['session_id']}
    try:
        assert entered.wait(5)
        with pytest.raises(APIError):api.call('q2_stop_session',base|{'session_ref':OTHER},authorize)
        receipt=api.call('q2_stop_session',base,authorize)
        assert receipt['provider_cancelled'] is None and receipt['generation']==1
        assert receipt==api.call('q2_stop_session',base,authorize)
        assert file_hash(receipt['decisions_jsonl'].encode())==receipt['decisions_sha256']
        stopped=[json.loads(x) for x in receipt['decisions_jsonl'].splitlines()]
        assert stopped[-1]['decided_by']=='USER' and stopped[-1]['control_reason']=='USER_STOPPED'
        counters=(receipt['searching_index'],receipt['session_agent_rounds_used'])
    finally:release.set()
    wait_for(lambda:not api._active)
    polled=api.call('q2_poll_session',base,authorize)
    assert polled['status']=='STOPPED' and polled['response'] is None and not api.responses
    assert (controllers[0].searching_index,controllers[0].session_agent_rounds_used)==counters
    assert controllers[0].decisions==stopped


def test_controller_returns_from_temp_lost_using_actual_tracker_observation():
    from test_q5_controller import fixture
    result,_=rule_run(fixture({'A':{0:'STRONG',1:'STRONG',3:'STRONG',4:'STRONG'}}))
    rows=[json.loads(x) for x in result.decisions_bytes.splitlines()]
    recovery=next(d for d in rows if d['state_before']=='TEMP_LOST' and d['state_after']=='PLAYING')
    assert recovery['entry_observation_id']==seed_id(fixture({'A':{0:'STRONG',1:'STRONG',3:'STRONG',4:'STRONG'}}),'A',3)
    assert result.response['reason']!='DataIntegrityError'


@pytest.mark.parametrize('restart',[False,True])
def test_manual_restart_is_explicit_and_preserves_session_counters(restart):
    from test_q5_agent import bindings, settings
    from test_q5_controller import port, request

    from amidst.q1q5.q5_agent import AgentController
    b=bindings();q=request(b);q['switch_mode']='AGENT_SEQUENTIAL'
    c=AgentController(q,bindings=b,evidence_provider=port([]),selected_observation_id=seed_id(b),
        provider=PolicyProvider(auto),agent_settings=settings(),round_scheduler=lambda *args:None,clock=lambda:0)
    assert c._prepare() is None;c._seed_candidates();c._running=True
    c.fallback_reason='PROVIDER_TIMEOUT';c.searching_index=2;c.session_agent_rounds_used=7
    c.request_manual_seed(seed_id(b,'A',1),restart_agent=restart)
    c._apply_manual('PLAYING')
    assert c.searching_index==3 and c.session_agent_rounds_used==7
    assert c.fallback_reason==(None if restart else 'PROVIDER_TIMEOUT')

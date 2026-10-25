"""SYNTHETIC policy/replay tests; no Ollama, human questions or event scripts."""
from copy import deepcopy
from dataclasses import replace
import hashlib,json
from pathlib import Path
import pytest
from amidst.q1q5.q5_agent import AgentController,AgentSettings,RecordedProvider,ReplayMismatch
from amidst.q1q5.llm_provider import FakeProvider
from amidst.q1q5.store import canonical_hash
from test_q5_controller import fixture,request,seed_id,port,seal_parameters,change_parameter

TEMPLATE=(Path(__file__).resolve().parents[2]/'configs/q1q5/prompts/q5_agent_v1.txt').read_text()
MODEL='qwen2.5:7b-instruct';DIGEST='a'*64


def settings(**changes):
    return AgentSettings(**({'model':MODEL,'model_digest':DIGEST,'options':{'temperature':0,'seed':7},'template':TEMPLATE,
        'template_sha256':hashlib.sha256(TEMPLATE.encode()).hexdigest(),'template_version':'q5-agent-v1','authorization_ref':'SYNTHETIC_G3'}|changes))


def bindings(pattern=None,cameras=('A','B'),**params):
    b=fixture(pattern,cameras=cameras);p=deepcopy(b.parameter_set)
    p['parameters'] += [{'name':k,'value':v,'status':'APPROVED','unit':'SYNTHETIC','proposed_by':'SYNTHETIC','proposal_ref':'synthetic://test'} for k,v in {'agent_call_timeout_ms':2000,'agent_max_illegal_submissions':2,'session_max_agent_rounds':20}.items()]
    for row in p['parameters']:
        if row['name'] in params:row['value']=params[row['name']]
    seal_parameters(p);return replace(b,parameter_set=p,parameter_sha256=p['content_sha256'])


class PolicyProvider:
    """Builds mechanical tool output from the actual prompt, then runs the real
    thin provider envelope/digest checks through FakeProvider."""
    def __init__(self,policy):self.policy=policy;self.requests=[];self.audits=[]
    def generate(self,**args):
        self.requests.append(deepcopy(args));payload=json.loads(args['prompt'].split('\n')[-1]);output=self.policy(payload,len(self.requests))
        if isinstance(output,Exception):responses=[output]
        else:
            raw=output if isinstance(output,str) else json.dumps(output)
            tags=json.dumps({'models':[{'name':MODEL,'digest':DIGEST}]}).encode()
            responses=[tags,json.dumps({'model':MODEL,'done':True,'response':raw}).encode(),tags]
        result=FakeProvider(responses,clock=lambda:0).generate(**args);self.audits.append(result.record);return result


def auto(payload,n,action='SWITCH',candidate_index=None):
    context=payload['context'];last=payload['last_tool_result'];base={k:context[k] for k in ['session_id','decision_id']}
    if action=='RETURN_TO_ORIGIN':
        candidate=None;cited=[]
    elif last.get('schema_version')!='q-demo.candidate-evidence.v1':
        c=context['candidates'][context['next_candidate_rank']-1 if candidate_index is None else candidate_index]
        return {'tool':'get_candidate_evidence','arguments':base|{'candidate_ref':c['candidate_ref']}}
    else:candidate=last['candidate_ref'];cited=[last['entry_observation_id'] or last['best_observations'][0]['observation_id']]
    return {'schema_version':'q-demo.agent-decision.v1',**base,'candidate_snapshot_sha256':context['candidate_snapshot_sha256'],
        'action':action,'candidate_ref':candidate,'cited_observation_ids':cited,'rationale':'SYNTHETIC cited evidence supports this action'}


def run_agent(b=None,policy=auto,provider=None,clock=lambda:0,agent_settings=None,mode='AGENT_SEQUENTIAL',scheduler=None,evidence=None):
    b=b or bindings();q=request(b);q['switch_mode']=mode;calls=[];provider=provider or PolicyProvider(policy)
    controller=AgentController(q,bindings=b,evidence_provider=evidence or port(calls),selected_observation_id=seed_id(b),
        provider=provider,agent_settings=agent_settings or settings(),round_scheduler=scheduler or (lambda *args:None),clock=clock)
    return controller,controller.run(),provider,calls


def decisions(r):return [json.loads(x) for x in r.decisions_bytes.splitlines()]


def test_agent_fetches_then_proposes_and_controller_guards_real_entry():
    c,r,p,calls=run_agent();assert len(p.requests)==2 and calls==[('B',800000)]
    assert r.response['agent_attempted'] and r.response['agent_used'] and not r.response['fallback_used']
    assert r.response['decision_source']=='AGENT' and r.response['timeline'][-1]['camera_id']=='B'
    d=next(d for d in decisions(r) if d['executed_action']=='SWITCH')
    assert d['session_agent_rounds_used']==2 and d['rounds_used']==2 and len(d['llm_calls'])==2
    assert d['source_time_us']==1000000 and d['entry_observation_id']
    assert all('images' not in x and 'event_script' not in x['prompt'] for x in p.requests)


def test_agent_can_choose_return_without_fetching_and_stays_at_current_source():
    c,r,p,calls=run_agent(policy=lambda x,n:auto(x,n,'RETURN_TO_ORIGIN'))
    assert calls==[] and r.response['agent_used'] and r.response['decision_source']=='AGENT'
    assert all(d['executed_action']!='SWITCH' for d in decisions(r))
    assert next(d for d in decisions(r) if d['executed_action']=='RETURN_TO_ORIGIN')['source_time_us']==800000


@pytest.mark.parametrize('output,reason',[(TimeoutError(),'PROVIDER_TIMEOUT'),(ConnectionError(),'PROVIDER_UNAVAILABLE'),('not JSON','INVALID_RESPONSE'),('{"tool":"bogus","arguments":{}}','INVALID_RESPONSE')])
def test_provider_and_invalid_output_failures_transfer_entire_session(output,reason):
    b=bindings({'A':{0:'STRONG',1:'STRONG'}},agent_max_rounds=4)
    c,r,p,calls=run_agent(b,policy=lambda x,n:output)
    assert len(p.requests)==1 and r.response['fallback_reason']==reason and r.response['fallback_used'] and not r.response['agent_used']
    assert len(r.snapshots)>1 and len(calls)>1 and r.response['agent_attempted']
    assert all(d['decided_by']=='RULE_FALLBACK' for d in decisions(r) if d['executed_action'] is not None)


def test_rule_only_and_unauthorized_never_call_provider():
    for mode,config in [('RULE_ONLY',settings()),('AGENT_SEQUENTIAL',settings(authorization_ref=None))]:
        c,r,p,calls=run_agent(mode=mode,agent_settings=config)
        assert not p.requests and not r.response['agent_attempted'] and not r.response['agent_used']
        assert r.response['fallback_reason']==('MODE_NOT_AUTHORIZED' if mode=='AGENT_SEQUENTIAL' else None)


def test_round_limit_falls_back_reusing_fetched_evidence_and_does_not_end_session():
    c,r,p,calls=run_agent(bindings(agent_max_rounds=1));assert len(p.requests)==1 and calls==[('B',800000)]
    assert r.response['status']=='COMPLETE' and r.response['fallback_reason']=='ROUND_LIMIT' and r.response['decision_source']=='RULE_FALLBACK'


def test_session_agent_limit_is_not_research_or_rule_execution_limit():
    c,r,p,calls=run_agent(bindings({'A':{0:'STRONG',1:'STRONG'}},session_max_agent_rounds=1))
    assert len(p.requests)==1 and len(r.snapshots)>1 and len(calls)>1 and r.response['fallback_reason']=='ROUND_LIMIT'


def test_illegal_rank_submission_counts_rounds_and_limit_then_rule_suffix():
    def wrong(payload,n):return auto(payload,n,candidate_index=1)
    c,r,p,calls=run_agent(bindings(cameras=('A','B','E')),policy=wrong)
    assert len(p.requests)==2 and r.response['fallback_reason']=='ILLEGAL_CANDIDATE'
    rejected=[d for d in decisions(r) if not d['accepted']]
    assert [d['rejection_code'] for d in rejected]==['ILLEGAL_ORDER','ILLEGAL_ORDER']
    assert rejected[-1]['session_agent_rounds_used']==2 and calls==[('B',800000)]


def test_accepted_agent_next_is_preserved_and_fallback_starts_at_remaining_cursor():
    pattern={'A':{0:'STRONG',1:'STRONG'},'B':{i:'STRONG' for i in range(5,10)},'E':{i:'STRONG' for i in range(6,10)}}
    def policy(payload,n):return auto(payload,n,'NEXT_CANDIDATE')
    c,r,p,calls=run_agent(bindings(pattern,cameras=('A','B','E'),agent_max_rounds=2),policy=policy)
    assert calls==[('B',800000),('E',800000)] and r.response['timeline'][-1]['camera_id']=='E'
    assert r.response['agent_used'] and r.response['fallback_used'] and r.response['fallback_reason']=='ROUND_LIMIT'
    actions=[d for d in decisions(r) if d['executed_action'] is not None]
    assert [d['executed_action'] for d in actions]==['NEXT_CANDIDATE','SWITCH']
    assert [d['decided_by'] for d in actions]==['AGENT','RULE_FALLBACK']


def test_total_time_includes_evidence_and_provider_wait_without_aborting_rule():
    class Clock:
        def __init__(self):self.value=0
        def __call__(self):return self.value
    clock=Clock();calls=[]
    def slow(*args):clock.value+=6;return port(calls)(*args)
    c,r,p,_=run_agent(clock=clock,evidence=slow)
    assert len(p.requests)==1 and r.response['fallback_reason']=='TIME_BUDGET' and r.response['status']=='COMPLETE'
    assert calls==[('B',800000)]


def test_recorded_replay_has_no_network_and_exact_journals_outputs_and_calls():
    c,r,p,_=run_agent();trace=c.trace();replay=RecordedProvider(trace,expected_sha256=trace['content_sha256'])
    again,rr,_,_=run_agent(provider=replay,clock=replay.clock);replay.assert_consumed()
    assert r.response['output_sha256']==rr.response['output_sha256'] and r.decisions_bytes==rr.decisions_bytes and r.links_bytes==rr.links_bytes
    assert again.trace()==trace


def test_recorded_replay_preserves_error_and_fallback_without_connecting_model():
    c,r,p,_=run_agent(policy=lambda x,n:TimeoutError());trace=c.trace();replay=RecordedProvider(trace,expected_sha256=trace['content_sha256'])
    _,rr,_,_=run_agent(provider=replay,clock=replay.clock);replay.assert_consumed()
    assert rr.response['output_sha256']==r.response['output_sha256'] and rr.decisions_bytes==r.decisions_bytes


@pytest.mark.parametrize('change',['hash','prompt','scope','clock','model'])
def test_replay_refuses_tampered_or_foreign_trace(change):
    c,r,p,_=run_agent();trace=c.trace()
    if change=='hash':trace['events'][0]['text']='tampered'
    elif change=='clock':trace['clock_ticks'][1]=-1
    elif change=='scope':trace['session_id']='foreign'
    elif change=='prompt':trace['events'][0]['request']['prompt']='foreign'
    else:trace['events'][0]['request']['model']='foreign'
    if change!='hash':trace['content_sha256']=canonical_hash(trace,exclude=('content_sha256',))
    with pytest.raises((ControllerError,ReplayMismatch)):
        replay=RecordedProvider(trace,expected_sha256=trace['content_sha256']);_,rr,_,_=run_agent(provider=replay,clock=replay.clock)
        replay.assert_consumed()


from amidst.q1q5.q5_controller import ControllerError


def test_no_transition_candidates_is_normal_return_without_false_agent_limit():
    b=bindings(cameras=('A',));c,r,p,calls=run_agent(b)
    assert not p.requests and not calls and not r.response['fallback_used'] and not r.response['agent_attempted']
    assert any(d['executed_action']=='RETURN_TO_ORIGIN' for d in decisions(r))


def test_agent_can_decline_even_strong_candidate_and_exhaustion_is_not_failure():
    c,r,p,calls=run_agent(policy=lambda x,n:auto(x,n,'NEXT_CANDIDATE'))
    assert len(p.requests)==2*len(r.snapshots) and r.response['agent_used'] and not r.response['fallback_used']
    assert [d['executed_action'] for d in decisions(r) if d['executed_action'] is not None][:2]==['NEXT_CANDIDATE','RETURN_TO_ORIGIN']


def test_agent_cannot_choose_weak_candidate_and_limit_falls_back_without_cut():
    b=bindings({'A':{0:'STRONG',1:'STRONG'},'B':{i:'WEAK' for i in range(5,10)}},agent_max_rounds=4,agent_max_illegal_submissions=1)
    c,r,p,calls=run_agent(b)
    assert r.response['fallback_reason']=='ILLEGAL_CANDIDATE' and not any(d['executed_action']=='SWITCH' for d in decisions(r))
    assert next(d for d in decisions(r) if not d['accepted'])['rejection_code']=='INSUFFICIENT_EVIDENCE'


def test_provider_timeout_uses_remaining_episode_budget():
    class Clock:
        value=0
        def __call__(self):return self.value
    clock=Clock()
    def pace(*args):clock.value+=4.5
    c,r,p,calls=run_agent(clock=clock,scheduler=pace)
    assert p.requests[0]['timeout_ms']==500 and len(p.requests)==1 and r.response['fallback_reason']=='TIME_BUDGET'


def test_manual_override_during_provider_call_cannot_execute_stale_agent_switch():
    b=bindings(cameras=('A','B','E'));pattern={'A':{0:'STRONG',1:'STRONG'},'B':{i:'STRONG' for i in range(5,10)},'E':{i:'STRONG' for i in range(6,10)}}
    b=bindings(pattern,cameras=('A','B','E'));holder={}
    def policy(payload,n):
        if n==2:holder['controller'].request_manual_seed(seed_id(b,'E',6))
        return auto(payload,n)
    provider=PolicyProvider(policy);q=request(b);q['switch_mode']='AGENT_SEQUENTIAL'
    c=AgentController(q,bindings=b,evidence_provider=port([]),selected_observation_id=seed_id(b),provider=provider,
        agent_settings=settings(),round_scheduler=lambda *args:None,clock=lambda:0);holder['controller']=c;r=c.run()
    assert r.response['timeline'][-1]['camera_id']=='E' and not any(d['executed_action']=='SWITCH' for d in decisions(r))
    assert r.response['agent_attempted'] and not r.response['agent_used']
    rejected=[d for d in decisions(r) if not d['accepted']]
    assert rejected[0]['rejection_code']=='USER_OVERRIDE' and len(rejected[0]['llm_calls'])==2
    manual=[d for d in decisions(r) if d['decided_by']=='USER' and d['searching_index']==2]
    assert manual and all(d['session_agent_rounds_used']==2 and d['rounds_used']==0 for d in manual)


def test_agent_bound_parameters_must_be_explicit_and_approved_before_seed():
    b=bindings();b=change_parameter(b,'agent_max_illegal_submissions',status='PROPOSED')
    c,r,p,calls=run_agent(b);assert r.response['status']=='PARTIAL' and r.response['reason']=='PARAMETERS_NOT_APPROVED'
    assert not r.seed_candidates and not p.requests


def test_provider_audit_tampering_cannot_authorize_cut():
    class Tampered(PolicyProvider):
        def generate(self,**args):
            r=super().generate(**args);r.record['prompt_sha256']='0'*64;return r
    c,r,p,calls=run_agent(provider=Tampered(auto))
    assert r.response['status']=='UNKNOWN' and r.response['reason']=='DataIntegrityError'
    assert not any(d['executed_action']=='SWITCH' for d in decisions(r))


def test_recorded_replay_preserves_total_budget_abort_after_expensive_evidence():
    class Clock:
        value=0
        def __call__(self):return self.value
    clock=Clock();calls=[]
    def slow(*args):clock.value+=6;return port(calls)(*args)
    c,r,p,_=run_agent(clock=clock,evidence=slow);trace=c.trace();replay=RecordedProvider(trace,expected_sha256=trace['content_sha256'])
    _,rr,_,_=run_agent(provider=replay,clock=replay.clock);replay.assert_consumed()
    assert r.response['output_sha256']==rr.response['output_sha256'] and r.decisions_bytes==rr.decisions_bytes


def test_metadata_sampling_and_template_pins_fail_before_model():
    for changes in [{'template_sha256':'0'*64},{'model_digest':'not a hash'},{'options':{'images':1}}]:
        with pytest.raises(ControllerError):settings(**changes)


def test_accepted_agent_journal_retains_exact_citations_rationale_and_decision_slot():
    c,r,p,_=run_agent()
    d=next(d for d in decisions(r) if d['executed_action']=='SWITCH')
    assert d['submitted']['decision_id']==d['decision_id'] and d['submitted']['rationale']
    assert d['submitted']['cited_observation_ids']==[d['entry_observation_id']]


def test_after_rejection_next_prompt_uses_new_slot_without_refetch_or_cursor_skip():
    def policy(payload,n):
        if n==2:
            d=auto(payload,n);d['cited_observation_ids']=['foreign'];return d
        if n==3:
            context=payload['context'];e=context['candidates'][context['next_candidate_rank']-1]
            d={'schema_version':'q-demo.agent-decision.v1',**{k:context[k] for k in ['session_id','decision_id']},
               'candidate_snapshot_sha256':context['candidate_snapshot_sha256'],'action':'SWITCH','candidate_ref':e['candidate_ref'],
               'cited_observation_ids':[seed_id(b,'B',5)],'rationale':'SYNTHETIC current fetched entry'}
            return d
        return auto(payload,n)
    b=bindings(agent_max_rounds=3);c,r,p,calls=run_agent(b,policy=policy)
    assert r.response['decision_source']=='AGENT' and not r.response['fallback_used'] and calls==[('B',800000)]
    submitted=[d for d in decisions(r) if d['submitted'] is not None]
    assert len(submitted)==2 and all(d['submitted']['decision_id']==d['decision_id'] for d in submitted)


def test_unexpected_provider_failure_is_recorded_and_rule_takes_entire_session():
    class Broken:
        calls=0
        def generate(self,**args):self.calls+=1;raise RuntimeError('sensitive path must not be copied')
    provider=Broken();c,r,_,_=run_agent(bindings({'A':{0:'STRONG',1:'STRONG'}}),provider=provider)
    assert provider.calls==1 and len(r.snapshots)>1 and r.response['fallback_reason']=='PROVIDER_UNAVAILABLE'
    assert 'sensitive' not in json.dumps(c.trace())
    trace=c.trace();replay=RecordedProvider(trace,expected_sha256=trace['content_sha256'])
    _,rr,_,_=run_agent(bindings({'A':{0:'STRONG',1:'STRONG'}}),provider=replay,clock=replay.clock);replay.assert_consumed()
    assert r.decisions_bytes==rr.decisions_bytes and r.response['output_sha256']==rr.response['output_sha256']


def test_agent_switch_keeps_unqueried_candidates_in_audit_without_fake_action():
    c,r,p,calls=run_agent(bindings(cameras=('A','B','E')))
    tail=[x for x in r.diagnostics if x.get('reason')=='NOT_SELECTED_AFTER_AGENT_DECISION']
    assert len(tail)==1 and tail[0]['target_presence']=='NOT_EVALUATED' and tail[0]['evidence_sha256'] is None


def test_guided_profile_tracks_tool_progress_and_replays_exactly():
    from amidst.contracts.q_demo.mini_schema import Validator
    from amidst.q1q5.llm_guidance import q5_schema
    text=(Path(__file__).parents[2]/'configs/q1q5/prompts/q5_agent_v2.txt').read_text()
    config=settings(template=text,template_sha256=hashlib.sha256(text.encode()).hexdigest(),template_version='q5-agent-v2')
    seen=[]
    def policy(payload,n):
        assert 'workflow' in payload;seen.append(payload['workflow']['phase'])
        output=auto(payload,n)
        if output.get('schema_version')=='q-demo.agent-decision.v1':output['rationale']={'RETURN_TO_ORIGIN':'Stop without a cut.','NEXT_CANDIDATE':'Continue to next candidate.','SWITCH':'Strong observed evidence.'}[output['action']]
        assert not Validator(lambda name:q5_schema(payload)).validate(output,"guided")
        return output
    c,r,p,_=run_agent(policy=policy,agent_settings=config)
    assert seen==['FETCH_CANDIDATE_EVIDENCE','SUBMIT_DECISION'] and r.response['agent_used']
    trace=c.trace();replay=RecordedProvider(trace,expected_sha256=trace['content_sha256'])
    _,rr,_,_=run_agent(provider=replay,clock=replay.clock,agent_settings=config);replay.assert_consumed()
    assert r.decisions_bytes==rr.decisions_bytes and r.links_bytes==rr.links_bytes and r.response['output_sha256']==rr.response['output_sha256']


def test_guidance_cannot_weaken_switch_guard_if_provider_ignores_schema():
    text=(Path(__file__).parents[2]/'configs/q1q5/prompts/q5_agent_v2.txt').read_text()
    cfg=settings(template=text,template_sha256=hashlib.sha256(text.encode()).hexdigest(),template_version='q5-agent-v2')
    def illegal(payload,n):
        d=auto(payload,n,'RETURN_TO_ORIGIN');d.update(action='SWITCH',candidate_ref=payload['context']['candidates'][0]['candidate_ref'],cited_observation_ids=['invented'])
        return d
    c,r,p,_=run_agent(policy=illegal,agent_settings=cfg)
    assert not r.response['agent_used'] and r.response['fallback_used']
    assert all(x['decided_by']!='AGENT' for x in decisions(r) if x['executed_action']=='SWITCH')

"""Typed-tool adversarial checks using synthetic index observations only."""
from copy import deepcopy

import pytest
from amidst.q1q5.agent_tools import AgentTools
from amidst.q1q5.q5_controller import RuleController
from test_q5_controller import fixture, port, request, seed_id


def tools_fixture(pattern=None,cameras=('A','B')):
    b=fixture(pattern,cameras=cameras);calls=[]
    c=RuleController(request(b),bindings=b,evidence_provider=port(calls),selected_observation_id=seed_id(b))
    assert c._prepare() is None;c._seed_candidates();row,o=c.observations[seed_id(b)]
    c.current_camera='A';c._search_last_observation=o['observation_id'];s=c._snapshot('A',o,400000)
    return AgentTools(c,s,800000,'decision-SYNTHETIC',lambda:{'rounds':3,'session_rounds':9,'budget_ms':5000}),calls


def base(t):return {'session_id':t.controller.session_id,'decision_id':t.decision_id}
def fetch(t,ref=None):return t.dispatch('get_candidate_evidence',base(t)|{'candidate_ref':ref or t.current()['candidate_ref']})
def proposal(t,action='SWITCH'):
    c=t.current();e=t.fetched.get(c['candidate_ref']) if c else None
    return {'schema_version':'q-demo.agent-decision.v2',**base(t),'candidate_snapshot_sha256':t.snapshot['candidate_snapshot_sha256'],
            'action':action,'candidate_ref':None if action=='RETURN_TO_ORIGIN' else c['candidate_ref'],
            'cited_observation_ids':[] if action=='RETURN_TO_ORIGIN' else [e['entry_observation_id'] or (e['best_observations'][0]['observation_id'] if e['best_observations'] else e['evidence_sha256'])],
            'rationale':'SYNTHETIC evidence supports this bounded action'}


def test_context_exposes_only_last_observation_and_immutable_candidate_copy():
    t,_=tools_fixture();context=t.dispatch('get_search_context',base(t));oid=context['last_observation']['observation_id']
    context['candidates'][0]['rank']=99
    assert t.current()['rank']==1 and t.dispatch('get_observation_summary',{'session_id':t.controller.session_id,'observation_id':oid})['observation_id']==oid
    assert t.dispatch('get_observation_summary',{'session_id':t.controller.session_id,'observation_id':seed_id(t.controller.bindings,'B',5)})['rejection_code']=='UNKNOWN_REF'


def test_evidence_requires_rank_order_and_cannot_be_fetched_twice():
    t,calls=tools_fixture(cameras=('A','B','E'));ref=t.snapshot['candidates'][1]['candidate_ref']
    assert fetch(t,ref)['rejection_code']=='ILLEGAL_ORDER' and not calls
    first=fetch(t);assert first['target_presence']=='MATCH_STRONG' and calls==[('B',800000)]
    assert fetch(t)['rejection_code']=='ILLEGAL_ORDER' and len(calls)==1
    oid=first['entry_observation_id'];assert t.dispatch('get_observation_summary',{'session_id':t.controller.session_id,'observation_id':oid})['timestamp_us']==1000000


def test_accepted_switch_is_proposal_only_and_closes_tool_cursor():
    t,_=tools_fixture();fetch(t);p=proposal(t);result=t.dispatch('submit_decision',p)
    assert result=={'accepted':True,'rejection_code':None,'executed_action':'SWITCH'}
    assert t.controller.current_camera=='A' and not t.controller.decisions
    assert fetch(t)['rejection_code']=='ILLEGAL_ORDER'


def test_next_advances_only_after_valid_submission():
    t,_=tools_fixture(cameras=('A','B','E'));fetch(t);p=proposal(t,'NEXT_CANDIDATE')
    bad=deepcopy(p);bad['cited_observation_ids']=['fabricated']
    assert t.dispatch('submit_decision',bad)['rejection_code']=='UNCITED_OR_FOREIGN_REF' and t.cursor==0
    assert t.dispatch('submit_decision',p)['accepted'] and t.cursor==1
    assert fetch(t)['target_presence']=='NO_PERSON_DETECTED'


@pytest.mark.parametrize('change,code',[
    ({'session_id':'foreign'},'UNKNOWN_REF'),({'decision_id':'old'},'STALE_SNAPSHOT'),
    ({'candidate_snapshot_sha256':'0'*64},'STALE_SNAPSHOT'),({'candidate_ref':'fake'},'UNKNOWN_REF'),
    ({'cited_observation_ids':[]},'UNCITED_OR_FOREIGN_REF'),({'cited_observation_ids':['foreign']},'UNCITED_OR_FOREIGN_REF'),
    ({'rationale':'same person confirmed'},'SCHEMA_INVALID'),({'rationale':'/Users/private/file'},'SCHEMA_INVALID'),
    ({'extra':1},'SCHEMA_INVALID'),({'action':'DELETE'},'SCHEMA_INVALID')])
def test_illegal_submissions_do_not_advance_or_cut(change,code):
    t,_=tools_fixture();fetch(t);p=proposal(t)|change
    assert t.dispatch('submit_decision',p)['rejection_code']==code and t.cursor==0 and not t.controller.timeline


def test_switch_without_fetch_and_below_guard_are_rejected():
    t,_=tools_fixture();p={'schema_version':'q-demo.agent-decision.v2',**base(t),'candidate_snapshot_sha256':t.snapshot['candidate_snapshot_sha256'],'action':'SWITCH','candidate_ref':t.current()['candidate_ref'],'cited_observation_ids':['fake'],'rationale':'x'}
    assert t.dispatch('submit_decision',p)['rejection_code']=='EVIDENCE_NOT_FETCHED'
    t,_=tools_fixture({'A':{0:'STRONG',1:'STRONG'},'B':{i:'WEAK' for i in range(5,10)}});fetch(t)
    assert t.dispatch('submit_decision',proposal(t))['rejection_code']=='INSUFFICIENT_EVIDENCE'


def test_return_needs_no_evidence_or_citations_and_unknown_fields_fail():
    t,calls=tools_fixture();assert t.dispatch('submit_decision',proposal(t,'RETURN_TO_ORIGIN'))['accepted'] and not calls
    t,_=tools_fixture();assert t.dispatch('get_search_context',base(t)|{'event_script':{}})['rejection_code']=='SCHEMA_INVALID'

@pytest.mark.parametrize('value',[None,[],{}, {'tool':'x'}, {'action':[]}])
def test_malformed_tool_arguments_never_advance(value):
    t,_=tools_fixture();assert t.dispatch('submit_decision',value)['rejection_code']=='SCHEMA_INVALID' and t.cursor==0


def test_next_cannot_use_empty_citation_for_no_person_evidence():
    t,_=tools_fixture({'A':{0:'STRONG',1:'STRONG'}});fetch(t)
    p={'schema_version':'q-demo.agent-decision.v2',**base(t),'candidate_snapshot_sha256':t.snapshot['candidate_snapshot_sha256'],
        'action':'NEXT_CANDIDATE','candidate_ref':t.current()['candidate_ref'],'cited_observation_ids':[],'rationale':'x'}
    assert t.dispatch('submit_decision',p)['rejection_code']=='UNCITED_OR_FOREIGN_REF'


def test_v2_empty_evidence_allows_next_by_evidence_hash_only():
    t,_=tools_fixture({'A':{0:'STRONG',1:'STRONG'}});e=fetch(t)
    assert e['best_observations']==[] and e['entry_observation_id'] is None
    p=proposal(t,'NEXT_CANDIDATE')
    assert p['cited_observation_ids']==[e['evidence_sha256']]
    assert t.dispatch('submit_decision',p)['accepted'] and t.cursor==1


@pytest.mark.parametrize('with_observations',[False,True])
def test_snapshot_hash_never_suffices_for_next_citation(with_observations):
    t,_=tools_fixture(None if with_observations else {'A':{0:'STRONG',1:'STRONG'}});fetch(t)
    p=proposal(t,'NEXT_CANDIDATE');p['cited_observation_ids']=[t.snapshot['candidate_snapshot_sha256']]
    assert t.dispatch('submit_decision',p)['rejection_code']=='UNCITED_OR_FOREIGN_REF'
    assert t.cursor==0 and not t.proposals


@pytest.mark.parametrize('action',['NEXT_CANDIDATE','SWITCH'])
def test_real_observations_require_observation_citations_instead_of_evidence_hash(action):
    t,_=tools_fixture();e=fetch(t);p=proposal(t,action)
    assert e['best_observations'] or e['entry_observation_id'] is not None
    p['cited_observation_ids']=[e['evidence_sha256']]
    assert t.dispatch('submit_decision',p)['rejection_code']=='UNCITED_OR_FOREIGN_REF'
    assert t.cursor==0 and not t.closed


@pytest.mark.parametrize('action',['NEXT_CANDIDATE','SWITCH'])
@pytest.mark.parametrize('value,code',[(None,'EVIDENCE_HASH_MISSING'),('','EVIDENCE_HASH_MISSING'),
                                     ('A'*64,'EVIDENCE_HASH_INVALID'),(42,'EVIDENCE_HASH_INVALID')])
def test_missing_or_invalid_evidence_hash_fails_closed_for_decisions(action,value,code):
    t,_=tools_fixture();fetch(t);p=proposal(t,action)
    if value is None:t.fetched[t.current()['candidate_ref']].pop('evidence_sha256')
    else:t.fetched[t.current()['candidate_ref']]['evidence_sha256']=value
    assert t.dispatch('submit_decision',p)['rejection_code']==code
    assert t.cursor==0 and not t.closed and not t.proposals
    assert t.dispatch('submit_decision',proposal(t,'RETURN_TO_ORIGIN'))['accepted']


def test_schema_v1_is_not_silently_accepted_after_citation_contract_upgrade():
    t,_=tools_fixture();fetch(t);p=proposal(t);p['schema_version']='q-demo.agent-decision.v1'
    assert t.dispatch('submit_decision',p)['rejection_code']=='SCHEMA_INVALID'
    assert t.cursor==0 and not t.closed

"""D73 contract behavior; synthetic context only, no human testset."""
import pytest
from test_agent_tools import base, fetch, tools_fixture
from test_q1_search import request as q1_request
from test_q1_search import search
from test_q3_parse import request, run

from amidst.q1q5.store import canonical_hash


@pytest.mark.parametrize('citation',['evidence','snapshot'])
def test_next_accepts_exact_fetched_empty_evidence_but_switch_does_not(citation):
    t,_=tools_fixture({'A':{0:'STRONG',1:'STRONG'}});e=fetch(t)
    ref=e['evidence_sha256'] if citation=='evidence' else t.snapshot['candidate_snapshot_sha256']
    value={'schema_version':'q-demo.agent-decision.v1',**base(t),
        'candidate_snapshot_sha256':t.snapshot['candidate_snapshot_sha256'],'action':'SWITCH',
        'candidate_ref':t.current()['candidate_ref'],'cited_observation_ids':[ref],'rationale':'Fetched negative evidence.'}
    assert not t.dispatch('submit_decision',value)['accepted']
    value['action']='NEXT_CANDIDATE'
    assert t.dispatch('submit_decision',value)['accepted'] and t.cursor==1


def test_snapshot_citation_does_not_bypass_fetch_or_allow_foreign_digest():
    t,_=tools_fixture({'A':{0:'STRONG',1:'STRONG'}})
    p={'schema_version':'q-demo.agent-decision.v1',**base(t),'candidate_snapshot_sha256':t.snapshot['candidate_snapshot_sha256'],
       'action':'NEXT_CANDIDATE','candidate_ref':t.current()['candidate_ref'],
       'cited_observation_ids':[t.snapshot['candidate_snapshot_sha256']],'rationale':'Snapshot'}
    assert t.dispatch('submit_decision',p)['rejection_code']=='EVIDENCE_NOT_FETCHED'
    fetch(t);p['cited_observation_ids']=['0'*64]
    assert t.dispatch('submit_decision',p)['rejection_code']=='UNCITED_OR_FOREIGN_REF'


def test_multi_run_q3_clarifies_without_provider_or_fabricated_mapping():
    q=request(mode='LLM_WITH_RULE_FALLBACK');q['context']['run_ids'].append('RUN_OTHER')
    r,audit=run(q)
    assert r['status']=='NEEDS_CLARIFICATION' and r['reason']=='MULTI_RUN_SCOPE_UNRESOLVED'
    assert r['structured_query'] is None and r['resolved_scope']['clock_mapping_sha256'] is None and not audit
    assert r['clarification']['options']==[{'label':v,'value':v} for v in q['context']['run_ids']]
    assert r['reasons']==[r['reason']]
    assert canonical_hash(r,exclude=('output_sha256','stats'))==r['output_sha256']


def test_multi_run_q1_unknown_instead_of_choosing_first_run():
    q=q1_request();q['run_ids'].append('RUN_OTHER');r=search(q)
    assert r['status']=='UNKNOWN' and not r['results'] and r['reasons']==['MULTI_RUN_SCOPE_UNRESOLVED']

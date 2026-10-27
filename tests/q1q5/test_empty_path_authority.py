"""No vacuous walkability grant from zero-edge paths; SYNTHETIC fixtures only."""
from copy import deepcopy

import pytest
from test_graphs import fixture, load, load_scope, scope_fixture, seal

from amidst.q1q5.candidates import transition_candidates
from amidst.q1q5.store import canonical_hash


@pytest.mark.parametrize('declared',['APPROVED_WALKABLE','TOPOLOGICAL_ONLY'])
@pytest.mark.parametrize('approved',[False,True])
@pytest.mark.parametrize('with_scope',[False,True])
def test_zero_edge_is_effectively_unknown_and_never_a_candidate(declared,approved,with_scope):
    r,c=fixture()
    c['cameras'][3]['covered_regions'][0]['region_id']='R1'
    transition=c['transitions'][0]
    transition.update(region_path=['R1'],edge_path=[],region_hops=0,
                      path_traversability=declared,path_has_unknown_state=False)
    if approved:
        for graph in (r,c):graph.update(approval_status='APPROVED',approval_ref='SYNTHETIC_TEST_ONLY')
    seal(r,c)
    if with_scope:
        scope,pin=scope_fixture(r,c);bundle=load_scope(r,c,scope,pin)
    else:bundle=load(r,c)
    originals=deepcopy((r,c))
    assert bundle.transition_authorities['T_A_D']=={
        'path_traversability':'UNKNOWN','path_has_unknown_state':True,
        'reason':'SAME_REGION_TRANSITION_NOT_APPROVED'}
    result=transition_candidates(bundle,from_camera_id='A',last_bbox_xyxy_px=[10,10,30,30],
        session_id='SYNTHETIC',top_k=3,window_us=[0,6000000],exit_boundary_inclusive=True,
        allowed_camera_ids=[row['camera_id'] for row in c['cameras']])
    assert all(row['camera_id']!='D' for row in result['candidates'])
    row=next(row for row in result['excluded_transitions'] if row['transition_id']=='T_A_D')
    assert row['reason']==('GRAPH_NOT_APPROVED' if with_scope and not approved
                          else 'SAME_REGION_TRANSITION_NOT_APPROVED')
    # Never repair/relabel the frozen declaration or silently recalculate its pin.
    assert (r,c)==originals and bundle.camera==c and bundle.region==r
    assert canonical_hash(bundle.camera,exclude=('graph_id','content_sha256','stats'))==c['content_sha256']


def test_nonempty_synthetic_approved_edges_keep_existing_ranking():
    r,c=fixture();bundle=load(r,c)
    assert bundle.transition_authorities['T_A_D']['path_traversability']=='APPROVED_WALKABLE'
    view=bundle.transition_authorities;view['T_A_D']['path_traversability']='UNKNOWN'
    assert bundle.transition_authorities['T_A_D']['path_traversability']=='APPROVED_WALKABLE'

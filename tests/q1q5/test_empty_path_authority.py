"""No vacuous walkability grant from zero-edge paths; SYNTHETIC fixtures only."""
from copy import deepcopy

import pytest
from test_graphs import fixture, load, load_scope, scope_fixture, seal

from amidst.q1q5.candidates import transition_candidates
from amidst.q1q5.graphs import GraphError
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
        'reason':('TOPOLOGICAL_ONLY_EDGE' if declared=='TOPOLOGICAL_ONLY'
                  else 'SAME_REGION_TRANSITION_NOT_APPROVED')}
    result=transition_candidates(bundle,from_camera_id='A',last_bbox_xyxy_px=[10,10,30,30],
        session_id='SYNTHETIC',top_k=3,window_us=[0,6000000],exit_boundary_inclusive=True,
        allowed_camera_ids=[row['camera_id'] for row in c['cameras']])
    assert all(row['camera_id']!='D' for row in result['candidates'])
    row=next(row for row in result['excluded_transitions'] if row['transition_id']=='T_A_D')
    assert row['reason']==('GRAPH_NOT_APPROVED' if with_scope and not approved
                          else ('TOPOLOGICAL_ONLY_EDGE' if declared=='TOPOLOGICAL_ONLY'
                                else 'SAME_REGION_TRANSITION_NOT_APPROVED'))
    # Never repair/relabel the frozen declaration or silently recalculate its pin.
    assert (r,c)==originals and bundle.camera==c and bundle.region==r
    assert canonical_hash(bundle.camera,exclude=('graph_id','content_sha256','stats'))==c['content_sha256']


def test_nonempty_synthetic_approved_edges_keep_existing_ranking():
    r,c=fixture();bundle=load(r,c)
    assert bundle.transition_authorities['T_A_D']['path_traversability']=='APPROVED_WALKABLE'
    view=bundle.transition_authorities;view['T_A_D']['path_traversability']='UNKNOWN'
    assert bundle.transition_authorities['T_A_D']['path_traversability']=='APPROVED_WALKABLE'


@pytest.mark.parametrize('declared,unknown',[
    ('UNKNOWN',False), ('OPEN',False), ('APPROVED_WALKABLE',None),
    ('APPROVED_WALKABLE',0), ('TOPOLOGICAL_ONLY','true'),
])
def test_illegal_empty_path_declaration_fails_in_both_validators(declared,unknown):
    from amidst.evaluation.q1q5_graph_check import path_authority_declaration_valid
    r,c=fixture();c['cameras'][3]['covered_regions'][0]['region_id']='R1'
    t=c['transitions'][0]
    t.update(region_path=['R1'],edge_path=[],region_hops=0,
             path_traversability=declared,path_has_unknown_state=unknown)
    seal(r,c)
    assert not path_authority_declaration_valid(t,[])
    with pytest.raises(GraphError,match='Invalid historical empty-path declaration'):
        load(r,c)


@pytest.mark.parametrize('declared',['APPROVED_WALKABLE','TOPOLOGICAL_ONLY'])
@pytest.mark.parametrize('unknown',[False,True])
def test_empty_declaration_is_metadata_not_authority_in_both_validators(declared,unknown):
    from amidst.evaluation.q1q5_graph_check import path_authority_declaration_valid
    r,c=fixture();c['cameras'][3]['covered_regions'][0]['region_id']='R1'
    t=c['transitions'][0]
    t.update(region_path=['R1'],edge_path=[],region_hops=0,
             path_traversability=declared,path_has_unknown_state=unknown)
    seal(r,c)
    assert path_authority_declaration_valid(t,[])
    assert load(r,c).transition_authorities[t['transition_id']]['path_traversability']=='UNKNOWN'


@pytest.mark.parametrize('edge_path',[None,'',(),{}])
def test_non_list_edge_path_fails_closed(edge_path):
    r,c=fixture();t=c['transitions'][0]
    t.update(region_path=['R1'],edge_path=edge_path,region_hops=0)
    seal(r,c)
    with pytest.raises(GraphError):
        load(r,c)


def test_pinned_r004_v3_m1_is_unknown_and_scope_rejection_has_priority():
    import hashlib
    import json
    from pathlib import Path
    from amidst.q1q5.graphs import load_graphs
    root=Path(__file__).resolve().parents[2]/'configs/q1q5/graphs/r004'
    r=json.loads((root/'region_graph_v3.json').read_bytes())
    c=json.loads((root/'camera_graph_v3.json').read_bytes())
    raw=(root/'tracking_scope_v3.json').read_bytes();scope=json.loads(raw)
    bundle=load_graphs(r,c,region_sha256=r['content_sha256'],camera_sha256=c['content_sha256'],
                       tracking_scope=scope,tracking_scope_sha256=hashlib.sha256(raw).hexdigest(),
                       tracking_scope_bytes=raw)
    for source,target in [('CAM_W1','CAM_W2'),('CAM_W2','CAM_W1')]:
        tid='T_'+source+'__'+target
        assert bundle.transition_authorities[tid]['path_traversability']=='UNKNOWN'
        camera=next(v for v in c['cameras'] if v['camera_id']==source)
        polygon=camera['exit_zones'][0]['roi_polygon_px']
        x=sum(v[0] for v in polygon)/len(polygon)
        y=sum(v[1] for v in polygon)/len(polygon)
        result=transition_candidates(bundle,from_camera_id=source,last_bbox_xyxy_px=[x-1,y-2,x+1,y],
            session_id='STATIC_M1_CHECK',top_k=3,window_us=[0,6000000],exit_boundary_inclusive=True,
            allowed_camera_ids=[v['camera_id'] for v in c['cameras']])
        assert not result['candidates']
        assert tid in {v['transition_id'] for v in result['excluded_transitions']}
        assert all(v['reason']=='GRAPH_NOT_APPROVED' for v in result['excluded_transitions'])

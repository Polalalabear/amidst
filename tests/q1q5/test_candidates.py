"""SYNTHETIC D28 ordering and snapshot replay checks."""
from copy import deepcopy
import pytest
from amidst.q1q5.candidates import transition_candidates
from amidst.q1q5.graphs import GraphError
from amidst.q1q5.store import canonical_hash
from test_graphs import fixture,seal,load


def run(r=None,c=None,**kwargs):
    if r is None:r,c=fixture()
    args=dict(from_camera_id='A',last_bbox_xyxy_px=[10,10,30,30],session_id='SYNTHETIC',top_k=3,window_us=[0,6000000],exit_boundary_inclusive=True);args.update(kwargs)
    return transition_candidates(load(r,c),**args)


def test_d28_order_topological_exclusion_and_canonical_snapshot():
    d=run();assert [x['camera_id'] for x in d['candidates']]==['D','B','E']
    assert d['excluded_transitions']==[{'transition_id':'T_A_C','reason':'TOPOLOGICAL_ONLY_EDGE'}]
    digest=d['candidate_snapshot_sha256'];pre=deepcopy(d);pre.pop('candidate_snapshot_sha256')
    for n,c in enumerate(pre['candidates'],1):assert c.pop('candidate_ref')==f'cand:{digest[:16]}:{n}'
    assert canonical_hash(pre)==digest and run()==d


def test_unknown_tier_wins_before_unknown_edge_and_missing_area_is_last():
    r,c=fixture();r['edges'][0]['state']='UNKNOWN'
    for t in c['transitions']:
        if t['edge_path']:t['path_has_unknown_state']=True
    c['transitions'][1]['relation']='UNKNOWN';seal(r,c)
    d=run(r,c);assert [v['camera_id'] for v in d['candidates']]==['D','E','B']
    assert [v['ranking_basis']['relation_tier'] for v in d['candidates']]==[1,3,4]


def test_zero_area_precedes_missing_area_and_camera_id_breaks_exact_ties():
    r,c=fixture();t=c['transitions'][1];t.update(relation='OVERLAP',ranking_area_m2=0);seal(r,c)
    assert [v['camera_id'] for v in run(r,c)['candidates']]==['D','B','E']
    c['transitions'][0]['ranking_area_m2']=0;seal(r,c)
    assert [v['camera_id'] for v in run(r,c)['candidates']]==['B','D','E']


def test_truncation_counts_unique_cameras_not_routes():
    r,c=fixture();t=deepcopy(c['transitions'][0]);t['transition_id']='ZZ_DUP';c['transitions'].append(t);seal(r,c)
    d=run(r,c,top_k=1);assert d['truncated'] and not d['candidate_set_complete'] and d['truncated_count']==2
    assert d['candidates'][0]['alternative_transition_ids']==['ZZ_DUP']


def test_input_order_does_not_change_snapshot_or_route_representative():
    r,c=fixture();t=deepcopy(c['transitions'][0]);t['transition_id']='ZZ_DUP';c['transitions'].append(t);seal(r,c);one=run(r,c)
    c['transitions'].reverse();c['cameras'].reverse();seal(r,c)
    assert run(r,c)==one


@pytest.mark.parametrize('box',[[120,120,140,140],[0,0,20,0.1]])
def test_no_hit_uses_all_exits_and_marks_ambiguity(box):
    d=run(last_bbox_xyxy_px=box)
    assert d['exit_resolution']=='AMBIGUOUS' if box[0]>100 else d['exit_resolution']=='UNIQUE'
    assert len(d['candidates'])==3


def test_boundary_policy_is_explicit_and_multiple_hit_uses_union():
    assert run(last_bbox_xyxy_px=[0,0,20,100])['exit_resolution']=='UNIQUE'
    assert run(last_bbox_xyxy_px=[0,0,20,100],exit_boundary_inclusive=False)['exit_resolution']=='AMBIGUOUS'
    r,c=fixture();z=deepcopy(c['cameras'][0]['exit_zones'][0]);z['exit_zone_id']='A:second';c['cameras'][0]['exit_zones'].append(z);seal(r,c)
    assert run(r,c)['exit_resolution']=='AMBIGUOUS'


@pytest.mark.parametrize('change',[{'top_k':0},{'top_k':True},{'exit_boundary_inclusive':None},{'window_us':[1,1]},{'window_us':[0,1.0]},{'last_bbox_xyxy_px':[0,0,0,1]},{'last_bbox_xyxy_px':[0,0,float('nan'),1]},{'from_camera_id':'MISSING'}])
def test_invalid_inputs_fail_closed(change):
    with pytest.raises(GraphError):run(**change)


def test_run_camera_scope_filters_before_top_k_and_truncation():
    # Global rank 1 is D; a run without D still receives B, not an empty top-1.
    d=run(top_k=1,allowed_camera_ids=['A','B','E'])
    assert [v['camera_id'] for v in d['candidates']]==['B'] and d['truncated_count']==1
    assert not d['excluded_transitions']  # C is outside this run, not searched.
    assert run(top_k=1,allowed_camera_ids=['E','B','A'])==d


def test_run_with_only_origin_has_empty_candidate_set_without_outside_camera_leak():
    d=run(allowed_camera_ids=['A']);assert not d['candidates'] and not d['excluded_transitions'] and not d['truncated']


@pytest.mark.parametrize('scope',[[],['B'],['A','OUTSIDE'],['A','A'],['A',None],'A'])
def test_invalid_run_scope_never_falls_back_to_all_graph_cameras(scope):
    with pytest.raises(GraphError):run(allowed_camera_ids=scope)

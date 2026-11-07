import ast
from dataclasses import fields
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path

import pytest

from amidst.q1q5 import cross_camera_demo as model
from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, response, single_view_sequence

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('cross_demo_runner', ROOT/'scripts/run_cross_camera_demo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
VECTORS = json.loads((Path(__file__).parent/'fixtures/cross_camera_core_vectors.synthetic.json').read_text())['vectors']


def track(camera, times, color='red'):
    return Track(camera, 'synthetic:' + camera, tuple(Observation(camera, t, f'{camera}:{t}', .7,
                          frozenset([color]) if color else frozenset()) for t in times))


def replay(tracks, edges=None, now=1_600_000, params=None):
    return response(tracks, edges if edges is not None else {('A', 'B'): 'A_TO_B'},
                    as_of_us=now, parameters=params or Parameters(), clock_mapping_sha256='a'*64)


@pytest.mark.parametrize('vector', VECTORS, ids=lambda v: v['id'])
def test_410_shared_vectors(vector):
    assert single_view_sequence(vector['sightings'], as_of_us=vector['as_of_us']) == vector['single_view']


def test_real_observations_required_for_graph_handoff_and_gap():
    result, events, audit = replay([track('A', [0, 200_000]), track('B', [800_000, 1_000_000])])
    assert [s['kind'] for s in result['single_view']] == ['ON_CAMERA', 'GAP', 'ON_CAMERA', 'LOST']
    assert result['single_view'][1] == dict(kind='GAP', camera_id=None, range_us=[400_000,800_000], evidence_state='UNKNOWN')
    assert len(events) == 1 and events[0]['transition_id'] == 'A_TO_B'
    assert events[0]['identity_verdict'] == result['identity_verdict'] == 'UNCONFIRMED'
    assert result['blind']['estimate'] is None and 'GRAPH_NOT_APPROVED' in result['reasons']
    assert audit[0]['evidence_state'] == 'INFERRED'


@pytest.mark.parametrize('edges,color,params,reason', [
    ({},'red',Parameters(),'NO_DIRECT_TRANSITION'),
    ({('B','A'):'REVERSE_ONLY'},'red',Parameters(),'NO_DIRECT_TRANSITION'),
    ({('A','B'):'AB'},'blue',Parameters(),'COLOR_NOT_COMPATIBLE'),
    ({('A','B'):'AB'},None,Parameters(),'COLOR_NOT_COMPATIBLE'),
    ({('A','B'):'AB'},'red',Parameters(handoff_max_gap_us=399_999),'HANDOFF_WINDOW_EXCEEDED'),
])
def test_rejected_candidates_are_not_sightings(edges, color, params, reason):
    result, events, audit = replay([track('A',[0,200_000]),track('B',[800_000],color=color)],edges,params=params)
    assert not events and [s['camera_id'] for s in result['sightings']] == ['A']
    assert audit[0]['reason'] == reason


def test_gap_boundary_inclusive():
    result, events, _ = replay([track('A',[0,200_000]),track('B',[800_000])],params=Parameters(handoff_max_gap_us=400_000))
    assert len(events) == 1


def test_current_camera_still_observed_does_not_switch():
    result, events, audit = replay([track('A',[0,200_000,400_000]),track('B',[400_000])])
    assert not events and audit[0]['reason'] == 'CURRENT_CAMERA_STILL_OBSERVED'


def test_two_equal_seed_candidates_do_not_pick_identity_by_camera_name():
    result, events, _ = replay([track('A',[0]),track('B',[0])])
    assert not result['sightings'] and not events
    assert 'ASSOCIATION_AMBIGUOUS' in result['reasons']


def test_two_simultaneous_handoffs_fail_unknown():
    result, events, audit = replay([track('A',[0]),track('B',[800_000]),track('C',[800_000])],
                                  {('A','B'):'AB',('A','C'):'AC'})
    assert not events and all(a['reason']=='AMBIGUOUS_HANDOFF' for a in audit)
    assert {s['camera_id'] for s in result['sightings']} == {'A'}


def test_future_observations_never_change_past_cut():
    before = replay([track('A',[0,200_000]),track('B',[800_000])],now=600_000)
    after = replay([track('A',[0,200_000,2_000_000]),track('B',[800_000,2_200_000]),track('C',[3_000_000])],now=600_000)
    assert before == after
    assert not before[1] and before[0]['single_view'][-1]['kind'] == 'LOST'


def test_as_of_is_strict_and_does_not_use_candidate_frame_at_boundary():
    tracks=[track('A',[0]),track('B',[800_000])]
    assert not replay(tracks,now=800_000)[1]
    assert len(replay(tracks,now=1_000_000)[1]) == 1


def test_missing_samples_not_filled_with_observed_interpolation():
    result,_,_=replay([track('A',[0,400_000])])
    assert result['single_view'][1]['kind']=='GAP'
    assert result['single_view'][1]['range_us']==[200_000,400_000]


def test_graph_never_fabricates_a_camera_observation():
    result,events,_=replay([track('A',[0])],{('A','B'):'AB'})
    assert not events and len(result['sightings'])==1 and result['status']=='LOST'


def test_inference_has_no_file_network_or_script_imports():
    tree=ast.parse(Path(model.__file__).read_text())
    assert all(node.module in {'dataclasses','datetime','itertools'} for node in ast.walk(tree) if isinstance(node,ast.ImportFrom))
    assert not any(isinstance(node,ast.Import) for node in ast.walk(tree))
    assert {f.name for f in fields(Observation)} == {'camera_id','timestamp_us','observation_id','score','colors'}


def test_inference_runs_when_all_file_opens_are_denied(monkeypatch):
    def denied(*args, **kwargs):raise AssertionError('Inference attempted file access')
    with monkeypatch.context() as patch:
        patch.setattr('builtins.open',denied);patch.setattr(io,'open',denied);patch.setattr(os,'open',denied)
        result,events,_=replay([track('A',[0]),track('B',[800_000])])
    assert len(events)==1 and result['physical_navigation']=='UNKNOWN'


@pytest.mark.parametrize('key',['ground_truth','gt_private','event_script','renderer_trajectory','visibility','depth','gt_secret_ref'])
def test_protected_inputs_rejected_before_inference(key):
    with pytest.raises(ValueError,match='FORBIDDEN_INPUT'):
        runner.reject_protected({'nested':[{key:'/unreadable/sentinel'}]})


def test_extra_input_role_is_rejected_before_any_file_open(monkeypatch):
    def denied(*args,**kwargs):raise AssertionError('Unexpected file read')
    monkeypatch.setattr(runner,'read_pin',denied)
    with pytest.raises(ValueError,match='EXACT_INPUT_ROLES'):
        runner.load_run({'label':'A4-1','inputs':{**{k:{} for k in runner.ROLES},'event_script':{}}},{},{},Parameters())


def test_pinned_loader_hash_mismatch_and_symlink(tmp_path):
    path=tmp_path/'input.json';path.write_text('{}')
    with pytest.raises(ValueError,match='BYTE_PIN_MISMATCH'):
        runner.read_pin({'path':str(path),'sha256':'a'*64})
    link=tmp_path/'linked.json';link.symlink_to(path)
    with pytest.raises(ValueError,match='CANONICAL_FILE_REQUIRED'):
        runner.read_pin({'path':str(link),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})


@pytest.mark.parametrize('values',[{'handoff_max_gap_us':-1},{'min_score':float('nan')},{'color_rule':'IGNORE'},{'parameter_mode':'APPROVED'}])
def test_no_parameter_approval_or_unbounded_fallback(values):
    with pytest.raises(ValueError):Parameters(**values)


def test_declared_clock_microseconds_and_rollover():
    clock=dict(timezone='Asia/Taipei',rate=1,t0_us=0,wall_origin='2026-11-01T23:59:59+08:00')
    assert model.declared_wall(clock,1_200_000)=='2026-11-02T00:00:00.200000+08:00'
    with pytest.raises(ValueError):model.declared_wall(dict(clock,wall_origin='2026-11-01T00:00:00+00:00'),0)

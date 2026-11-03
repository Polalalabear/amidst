"""Analytic static interval checks, no scene/actor/media inputs."""
import importlib.util
from pathlib import Path

import pytest

SPEC=importlib.util.spec_from_file_location('d92_static',Path(__file__).parents[2]/'scripts/check_r004_d92_static_projection.py')
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_known_triangle_shadow_interval_is_analytic():
    origin=[0,0,0];triangle=([1,-.5,-1],[1,.5,-1],[1,0,1])
    a,b=[2,-2,0],[2,2,0]
    # The triangle at x=1 blocks target y in [-.5,.5] on x=2.
    result=module.interval(module.shadow_values(origin,triangle,a),module.shadow_values(origin,triangle,b))
    assert result==pytest.approx([.375,.625])
    planes=module.make_shadow_planes(origin,[triangle])[0]
    assert [module.dot(n,a)+offset for n,offset in planes]==pytest.approx(module.shadow_values(origin,triangle,a))


def test_union_and_complement_preserve_static_visibility_holes():
    assert module.unblocked([0,1],[[.2,.4],[.3,.6],[.8,1.2]])==[[0,.2],[.6,.8]]
    assert module.unblocked(None,[])==[]
    assert module.interval([-1,-1],[1,-1]) is None


def test_camera_coplanar_and_degenerate_faces_cannot_claim_blocking_authority():
    assert module.shadow_values([0,0,0],([0,-1,0],[0,1,0],[0,0,1]),[2,0,0]) is None
    assert module.shadow_values([0,0,0],([1,0,0],[1,0,0],[1,1,0]),[2,0,0]) is None


def test_clock_mapping_uses_arc_length_across_unequal_legs():
    camera={'camera_to_world':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],
            'clip_start':0.1,'clip_end':10,'fx':1,'fy':1,'cx':1,'cy':1,'width':2,'height':2}
    route=[[-4,0,-2],[0,0,-2],[0,1,-2]]
    row=module.visible_intervals(camera,[],route,0,time_range_s=(10,20))
    assert row['frustum_intervals_s'][0]==pytest.approx([14,20])
    assert row['unoccluded_witness_intervals_s'][0]==pytest.approx([14,20])
    shifted=module.visible_intervals(camera,[],route,0,time_range_s=(10,20),offset_xy=(0.5,0))
    assert shifted['unoccluded_witness_intervals_s'][0]==pytest.approx([13,20])
    with pytest.raises(ValueError,match='positive route'):
        module.visible_intervals(camera,[],[[0,0,-2],[0,0,-2]],0)


def test_speed_time_bounds_include_both_remaining_and_elapsed_distance():
    assert module.speed_time_bounds(2.25,4.05)==pytest.approx([37.5,37.8])
    assert module.speed_time_bounds(0,4.05)==pytest.approx([36,36])
    assert module.speed_time_bounds(4.05,4.05)==pytest.approx([39,39])
    assert module.speed_time_bounds(2,5) is None  # 5 m cannot fit 3 s at <=1.5 m/s.
    assert module.speed_time_bounds(1,2) is None  # Also enforce the 0.8 m/s lower bound.
    with pytest.raises(ValueError,match='invalid distance'):
        module.speed_time_bounds(5,4.05)
    with pytest.raises(ValueError,match='invalid distance'):
        module.speed_time_bounds(2,4.05,speed_limits=(1.5,0.8))


def test_whole_body_necessary_condition_requires_simultaneous_samples():
    assert module.intersect_interval_sets([[[36,38]],[[37,39]]])==[[37,38]]
    assert module.intersect_interval_sets([[[36,37]],[[37,39]]])==[]
    assert module.intersect_interval_sets([[[36,39]],[]])==[]


def test_cards_sha_mismatch_fails_before_parsing_static_scene(tmp_path,monkeypatch):
    static=tmp_path/'safe_static';static.mkdir()
    paths={'catalog':static/'cameras.json','geometry':static/'static_geometry.PROPOSED.json',
           'patches':tmp_path/'patches.json','cards':tmp_path/'cards.md'}
    for path in paths.values():path.write_text('{}')
    pins={key:module.sha(path) for key,path in paths.items()}
    monkeypatch.setattr(module,'PINS',pins)
    paths['cards'].write_text('wrong cards head')
    with pytest.raises(ValueError,match='pin mismatch: cards'):
        module.audit(tmp_path,paths['patches'],paths['cards'])

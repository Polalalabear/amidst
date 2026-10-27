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

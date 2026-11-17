"""Focused kinematic properties, not formal physical-navigation acceptance."""
import importlib.util
import math
import subprocess
import sys
from pathlib import Path

import pytest

P=Path(__file__).resolve().parents[2]/'scripts/r004_natural_walk.py'
spec=importlib.util.spec_from_file_location('r004_natural_walk',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def plan():
    return m.WalkPlan([{'t_us':0,'xy':[0,0]},{'t_us':10_000_000,'xy':[10,0]},
                       {'t_us':12_000_000,'xy':[10,0]}])


def test_planted_foot_has_fixed_world_position():
    p=plan()
    poses=[p.pose(t) for t in [2.15,2.20,2.25]]
    for side in [1,-1]:
        active=[q for q in poses if q['legs'][side]['support']]
        if len(active)>=2:
            feet=[m.add(q['root'],m.rotate(q['legs'][side]['ankle'],q['yaw'])) for q in active]
            assert max(m.norm(m.sub(x,feet[0])) for x in feet)<1e-9
    assert any(sum(q['legs'][side]['support'] for q in poses)>=2 for side in [1,-1])


def test_leg_lengths_floor_and_root_positions_over_whole_walk():
    p=plan()
    for n in range(181):
        t=n/15
        q=p.pose(t)
        assert q['root']==pytest.approx((min(t,10),0,0))
        for leg in q['legs'].values():
            assert m.norm(m.sub(leg['hip'],leg['knee']))==pytest.approx(.40)
            assert m.norm(m.sub(leg['knee'],leg['ankle']))==pytest.approx(.38)
            assert leg['foot'][2]-.05 >= -1e-9


def test_holds_have_no_oscillation_or_lifted_feet():
    a,b=plan().pose(10.5),plan().pose(11.5)
    assert a['legs']==b['legs']
    assert a['arms']==b['arms']
    assert a['weight']==b['weight']==0
    assert all(l['foot'][2]==pytest.approx(.05) for l in a['legs'].values())


def test_ik_rejects_stretching():
    with pytest.raises(ValueError,match='unreachable'):
        m.two_link((0,0,0),(0,0,2),.4,.38)


def test_turn_heading_is_continuous_without_changing_waypoint_time():
    p=m.WalkPlan([{'t_us':0,'xy':[0,0]},{'t_us':2_000_000,'xy':[2,0]},
                  {'t_us':4_000_000,'xy':[2,2]}])
    assert p.pose(2)['root']==pytest.approx((2,0,0))
    assert p.pose(2)['yaw']==pytest.approx(math.pi/4)
    assert abs(p.yaw(2.001)-p.yaw(1.999))<.02


def test_pose_is_independent_of_frame_sampling_and_call_order():
    p=plan()
    a=p.pose(2.4)
    for t in [8.1,.2,2.0]:
        p.pose(t)
    assert a==p.pose(2.4)


def test_source_floor_step_does_not_change_root_height():
    p=m.WalkPlan([{'t_us':0,'xy':[0,0],'z_m':-.06},
                  {'t_us':1_000_000,'xy':[1,0],'z_m':-.06},
                  {'t_us':1_050_000,'xy':[1,0],'z_m':0},
                  {'t_us':3_000_000,'xy':[3,0],'z_m':0}])
    assert p.pose(1.025)['root']==pytest.approx((1,0,-.03))
    assert p.pose(1.05)['root']==pytest.approx((1,0,0))


def test_walk_bends_less_than_the_saved_exaggerated_reference():
    points=[{'t_us':0,'xy':[0,0]},{'t_us':10_000_000,'xy':[10,0]}]
    walk=m.WalkPlan(points)
    old=m.WalkPlan(points,profile='exaggerated_reference')
    def peak_flex(plan):
        peak=0.
        for n in range(15,135):
            for leg in plan.pose(n/15)['legs'].values():
                upper=m.unit(m.sub(leg['knee'],leg['hip']))
                lower=m.unit(m.sub(leg['ankle'],leg['knee']))
                peak=max(peak,math.degrees(math.acos(max(-1.,min(1.,m.dot(upper,lower))))))
        return peak
    assert peak_flex(walk)<35
    assert peak_flex(walk)<peak_flex(old)-20
    assert walk.profile['foot_lift_m']<old.profile['foot_lift_m']/4


def test_arm_lead_matches_opposite_foot_without_reversing_forearms():
    p=plan()
    for n in range(15,135):
        q=p.pose(n/15)
        for side in [1,-1]:
            arm=q['arms'][side]
            opposite_lead=q['legs'][-side]['ankle'][0]-q['legs'][side]['ankle'][0]
            hand_lead=arm['wrist'][0]-arm['shoulder'][0]
            assert hand_lead*opposite_lead>=-1e-10
            assert arm['wrist'][0]>arm['elbow'][0]
            assert m.norm(m.sub(arm['shoulder'],arm['elbow']))==pytest.approx(.26)
            assert m.norm(m.sub(arm['elbow'],arm['wrist']))==pytest.approx(.24)


def test_arm_direction_uses_body_local_forward_after_turning():
    p=m.WalkPlan([{'t_us':0,'xy':[0,0]},{'t_us':10_000_000,'xy':[0,10]}])
    q=p.pose(2.0)
    assert q['yaw']==pytest.approx(math.pi/2)
    for side in [1,-1]:
        arm=q['arms'][side]
        forearm_world=m.rotate(m.sub(arm['wrist'],arm['elbow']),q['yaw'])
        assert forearm_world[1]>0


@pytest.mark.parametrize('script_name',[
    'produce_r004_natural_walk_full.py','package_r004_natural_walk_full.py'])
def test_full_cli_refuses_to_modify_frozen_delivery(tmp_path,script_name):
    art=tmp_path/'artifacts'
    evidence=art/'evidence/frozen'
    evidence.mkdir(parents=True)
    marker=evidence/'FULL_MANIFEST.json'
    marker.write_text('{"frozen":true}\n')
    data=art/'data/r004-4actor-natural-walk-test'
    data.mkdir(parents=True)
    original=marker.read_bytes()
    args=[sys.executable,'-B',str(P.with_name(script_name)),
          '--artifacts-root',str(art),'--evidence-root',str(evidence),'--data-root',str(data)]
    if script_name.startswith('produce_'):
        args+=['--repo',str(P.parents[1]),'--stage','preflight']
    else:
        args+=['--ffmpeg',str(tmp_path/'ffmpeg-not-invoked')]
    result=subprocess.run(args,capture_output=True,text=True)
    assert result.returncode!=0 and 'frozen output' in result.stderr
    assert marker.read_bytes()==original
    assert sorted(p.name for p in evidence.iterdir())==['FULL_MANIFEST.json']
    assert not list(data.iterdir())

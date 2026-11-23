"""Synthetic pixels and calibration stubs only; neutral continuation must not consult rule gates."""
from copy import deepcopy

from amidst.live_mode.aopen.neutral import NeutralTracker, box_iou, chain_box

BOX = [10, 10, 30, 90]


class Projection:
    def ground(self, cam, u, v, w, h):
        return [u / 10, v / 10]


def test_follow_max_iou_ignores_colour_score_and_never_switches():
    n = NeutralTracker(Projection())
    n.adopt(0, 'A', BOX, 'AGENT_SELECT')
    target = deepcopy(n.target)
    dets = {'A': [{'bbox': [11, 10, 31, 90], 'color': 'blue', 'score': 0.01},
                  {'bbox': [15, 10, 35, 90], 'color': 'red', 'score': 1.0}],
            'B': [{'bbox': BOX, 'score': 1}]}
    out, status = n.step(1, target, dets)
    assert status == 'FOLLOWING' and out['box'] == [11, 10, 31, 90]
    assert out['camera_id'] == 'A' and out['est_xy'] == [2.1, 9.0]
    assert target['box'] == BOX  # caller input is preserved
    for tick, expected in [(2, 'COASTING'), (3, 'COASTING'), (4, 'LOST')]:
        _, status = n.step(tick, n.target, {'B': [{'bbox': BOX}]})
        assert status == expected
    assert n.tracking() == {'state': 'LOST', 'active_cam': None, 'est_xy': None, 'lost_ticks': 1, 'box': None}


def test_exact_iou_boundary_and_no_chain_coasting():
    a, b = [0, 0, 13, 10], [7, 0, 20, 10]
    assert box_iou(a, b) == 0.3
    n = NeutralTracker(Projection())
    n.adopt(0, 'A', a, 'AGENT_OWN_BOX')
    assert n.step(1, n.target, {'A': [{'bbox': b}]})[1] == 'FOLLOWING'
    assert chain_box(a, 'A', [{'A': [{'bbox': b}]}]) == b
    assert chain_box(a, 'A', [{'B': [{'bbox': b}]}]) is None
    assert chain_box(a, 'A', [{'A': []}, {'A': [{'bbox': a}]}]) is None


def test_hold_exact_ten_ticks_no_automatic_reacquisition_and_restart():
    n = NeutralTracker(Projection())
    assert not n.occlude(0, 'A')
    n.adopt(0, 'A', BOX, 'AGENT_SELECT')
    assert not n.occlude(1, 'B')
    assert n.occlude(1, 'A')
    for tick in range(1, 11):
        n.step(tick, n.target, {'A': [{'bbox': BOX}]})
        assert n.status == 'OCCLUDED_HOLD'
        assert n.tracking()['box'] is None and n.tracking()['est_xy'] == [2, 9]
    n.step(11, n.target, {'A': [{'bbox': BOX}]})
    assert n.status == 'LOST' and n.target is None
    n.adopt(12, 'A', BOX, 'AGENT_SELECT')
    n.occlude(13, 'A')
    n.occlude(20, 'A')
    n.step(29, n.target, {})
    assert n.status == 'OCCLUDED_HOLD'
    n.step(30, n.target, {})
    assert n.status == 'LOST'


def test_projection_failure_preserves_previous_or_hides_without_one():
    class Failing:
        point = None
        def ground(self, *args):
            return self.point
    p = Failing()
    n = NeutralTracker(p)
    n.adopt(0, 'A', BOX, 'AGENT_OWN_BOX')
    assert n.reason == 'NO_GROUND_POINT' and n.tracking()['state'] == 'LOST'
    p.point = [1, 2]
    n.step(1, n.target, {'A': [{'bbox': BOX}]})
    p.point = None
    n.step(2, n.target, {'A': [{'bbox': BOX}]})
    assert n.tracking()['est_xy'] == [1, 2]
    n.occlude(3, 'A')
    n.adopt(4, 'B', BOX, 'AGENT_SELECT')
    assert n.status == 'FOLLOWING' and n.target['hold_until'] is None
    n.clear()
    assert n.tracking()['state'] == 'LOST'

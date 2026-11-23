"""Session-colour propagation; no model, network or scene truth."""
from types import SimpleNamespace

import pytest

from amidst.live_mode.advisor import LiveDecider
from amidst.live_mode.scheduler import CameraScheduler
from amidst.live_mode.server import State
from amidst.live_mode.candidates import TrackSelection
from amidst.live_mode.tracker import Tracker


def scheduler(color='red'):
    return CameraScheduler({'cameras': [{'camera_id': c} for c in 'AB'], 'transitions': []}, target_color=color)


@pytest.mark.parametrize('color,other', [('red', 'blue'), ('blue', 'red')])
def test_recent_memory_follows_selected_colour_and_clears_on_change(color, other):
    s = scheduler(color)
    s.observe({'A': [{'color': color}], 'B': [{'color': other}]}, 1)
    assert s.plan('B', 0, ['A', 'B'], t_s=1)['camera_ids'] == ['A', 'B']
    s.set_target_color(other)
    assert s.plan('B', 0, ['A', 'B'], t_s=1)['camera_ids'] == ['B']
    s.observe({'A': [{'color': color}]}, 1)
    assert s.plan('B', 0, ['A', 'B'], t_s=1)['camera_ids'] == ['B']


@pytest.mark.parametrize('color,other', [('red', 'blue'), ('blue', 'red')])
def test_old_advisor_candidates_follow_session_colour(color, other):
    seen = []
    people = SimpleNamespace(update=lambda t, rows: seen.extend(rows) or [])
    adv = SimpleNamespace(poll=lambda: None, reference=None, busy=lambda: False, pending_ms=lambda: None)
    d = LiveDecider('review', adv, people, target_color=color)
    rows = [{'color': c, 'est_xy': [1, 0]} for c in [color, other]]
    d.step(0, 0, SimpleNamespace(), {'state': 'LOST'}, {'A': rows}, {})
    assert d.any_color and [r[1]['color'] for r in seen] == [color]


def test_session_reset_propagates_colour_to_scheduler_and_new_decider():
    s = State.__new__(State)
    s.selection = TrackSelection()
    s.selection.start('blue', False)
    s.scheduler = scheduler()
    s._new_tracker = lambda color: SimpleNamespace(target_color=color)
    s._new_decider = lambda: SimpleNamespace(target_color=s.selection.color)
    s._clear_target()
    assert s.scheduler.target_color == s.tracker.target_color == s.decider.target_color == 'blue'


@pytest.mark.parametrize('color,other', [('red', 'blue'), ('blue', 'red')])
def test_return_in_gate_recovers_but_wrong_colour_or_distant_return_do_not(color, other):
    t = Tracker(SimpleNamespace(ground=lambda *_: None), gate_m=4, target_color=color)
    t.seed({'tick': 0, 'cam': 'A', 'est_xy': [0, 0]}, 0, 'USER_PICK')
    assert t.update(1, {'A': []}, (320, 180), .5, projected=True)['lost_ticks'] == 1
    def row(c, x):
        return {'A': [{'color': c, 'bbox': [0, 0, 10, 20], 'score': .9, 'est_xy': [x, 0]}]}
    assert t.update(2, row(color, 5), (320, 180), 23.5, projected=True)['lost_ticks'] == 2
    assert t.update(3, row(other, 1), (320, 180), 24, projected=True)['lost_ticks'] == 3
    assert t.update(4, row(color, 1), (320, 180), 24.5, projected=True)['lost_ticks'] == 0


def test_server_factory_passes_blue_to_legacy_advisor():
    s = State.__new__(State)
    s.selection = SimpleNamespace(color='blue')
    s.guard = None
    s.args = SimpleNamespace(advisor='review', advisor_provider='fake', advisor_fake_delay_s=0,
                             advisor_model='sol6.1', advisor_timeout_s=5, gate_m=4,
                             advisor_lost_min_candidates=2, advisor_apply='reseed')
    assert s._new_decider().target_color == 'blue'

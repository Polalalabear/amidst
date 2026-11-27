"""E8 closed-loop decider (#780): synthetic tracker state only; the real-data B1 reproduction (V2) runs in SMOKE."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'evaluation'))

from amidst.evaluation import e8_handoff as H  # noqa: E402

CANDS = [{'camera_id': 'CAM_A', 'detection_id': 'D1', 'box': [0, 0, 10, 40], 'score': .9, 'colors': ['red'], 'ground_xy': [0.0, 0.0]},
         {'camera_id': 'CAM_B', 'detection_id': 'D1', 'box': [0, 0, 10, 40], 'score': .8, 'colors': ['red'], 'ground_xy': [3.0, 0.0]}]
OUT = {'CAM_A': [{'bbox': [0, 0, 10, 40], 'est_xy': [0.0, 0.0]}], 'CAM_B': [{'bbox': [0, 0, 10, 40], 'est_xy': [3.0, 0.0]}]}


def tracker():
    return SimpleNamespace(est=[0.0, 0.0], state='TRACKING', lost=0, active='CAM_A', last_seen={}, t_seen=0.0)


def tracking(state='TRACKING', lost=0, events=()):
    return {'state': state, 'active_cam': 'CAM_A', 'est_xy': [0.0, 0.0], 'lost_ticks': lost, 'events': list(events)}


def make(answers, latency='ZERO_LATENCY', lat=0.0):
    it = iter(answers)
    return H.E8HandoffDecider(lambda req: (next(it), None, lat), case_id='C', dataset_group='e3', camera_ids=['CAM_A', 'CAM_B'],
                              cands_by_tick={t: CANDS for t in range(100)}, level='L2', scene=None, scene_sha256=None, latency=latency)


def test_triggers_and_gaps():
    d = make([{'answer': 'KEEP'}] * 20)
    tr = tracker()
    d.step(0, 0.0, tr, tracking(), OUT, {})            # acquires; T-1 estimate now known
    d.step(1, 0.2, tr, tracking(), OUT, {})            # ambiguous: 2 red within 4 m, 3 m apart
    d.step(2, 0.4, tr, tracking(events=[{'type': 'SWITCH'}]), OUT, {})   # inside the 1 s global gap: no ask
    d.step(6, 1.2, tr, tracking(lost=2), OUT, {})
    d.step(8, 1.6, tr, tracking(lost=4), OUT, {})      # gap
    d.step(11, 2.2, tr, tracking(lost=7), OUT, {})     # lost repeat after 1 s
    assert [(e['tick'], e['trigger']) for e in d.log] == [(1, 'AMBIGUOUS'), (6, 'LOST'), (11, 'LOST')]


def test_no_ask_before_acquire_and_b1_display():
    d = make([])
    d.step(0, 0.0, tracker(), {'state': 'SEARCHING', 'lost_ticks': 3, 'events': []}, OUT, {})
    assert d.log == []
    assert H.b1_display(tracking(), OUT) == {'camera_id': 'CAM_A', 'detection_id': 'D1'}
    assert H.b1_display(tracking(lost=1), OUT) is None


def test_select_and_not_visible_apply():
    d = make([{'answer': 'SELECT', 'option': 'B'}, {'answer': 'NOT_VISIBLE', 'option': None}, {'answer': 'KEEP', 'option': None}])
    tr = tracker()
    d.step(0, 0.0, tr, tracking(), OUT, {})
    t1 = d.step(1, 0.2, tr, tracking(), OUT, {})
    assert tr.active == 'CAM_B' and t1['est_xy'] == [3.0, 0.0] and t1['decision_source'] == 'AGENT'
    assert any(e['type'] == 'SWITCH' and e['detail']['by'] == 'AGENT' for e in t1['events'])
    t6 = d.step(6, 1.2, tr, tracking(lost=2), OUT, {})
    assert tr.state == 'LOST' and t6['state'] == 'LOST'
    assert d.step(9, 1.8, tr, tracking(), OUT, {})['state'] == 'LOST'          # suppressed for 1.0 s
    assert d.step(11, 2.2, tr, tracking(), OUT, {})['state'] == 'TRACKING'


def test_measured_chain_and_expiry():
    d = make([{'answer': 'SELECT', 'option': 'B'}], latency='MEASURED', lat=0.5)
    tr = tracker()
    d.step(0, 0.0, tr, tracking(), OUT, {})
    d.step(1, 0.2, tr, tracking(), OUT, {})
    assert d.pending['due'] == 4 and tr.active == 'CAM_A'
    moved = {'CAM_A': OUT['CAM_A'], 'CAM_B': [{'bbox': [1, 0, 11, 40], 'est_xy': [3.0, 0.0]}]}
    for t in (2, 3, 4):
        d.step(t, t * 0.2, tr, tracking(), moved, {})
    assert d.log[0]['applied'] == 'SELECT' and d.log[0]['applied_tick'] == 4 and tr.active == 'CAM_B'
    d2 = make([{'answer': 'SELECT', 'option': 'B'}], latency='MEASURED', lat=0.5)
    tr2 = tracker()
    d2.step(0, 0.0, tr2, tracking(), OUT, {})
    d2.step(1, 0.2, tr2, tracking(), OUT, {})
    gone = {'CAM_A': OUT['CAM_A'], 'CAM_B': [{'bbox': [200, 0, 210, 40], 'est_xy': [9.0, 0.0]}]}
    for t in (2, 3, 4):
        d2.step(t, t * 0.2, tr2, tracking(), gone, {})
    assert d2.log[0]['applied'] == 'EXPIRED' and tr2.active == 'CAM_A'


def test_b1_reproduced_reports_first_diff():
    a = [{'tracking': {'x': 1}}, {'tracking': {'x': 2}}]
    assert H.b1_reproduced(a, a)['ok']
    assert H.b1_reproduced(a, [a[0], {'tracking': {'x': 3}}])['first_diff_index'] == 1

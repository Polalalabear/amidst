"""E4 (#681): conditional Agent override on the LIVE path (no network, no model, no ground truth). SYNTHETIC tracks only."""
import json
import types

import pytest

from amidst.live_mode.people import PeopleTracker
from amidst.live_mode.service_decider_e4 import E4_EXTRA, N_STABLE, ServiceLiveDeciderE4, parse_e4
from amidst.q1q5 import agent_service as ag

Image = pytest.importorskip("PIL.Image")
SCENE = {'schema_version': 'SYNTHETIC', 'cameras': [{'camera_id': 'W1'}, {'camera_id': 'W2'}], 'overlaps': [], 'incomplete': []}


def det(x0, color='red', xy=(0, 0), score=0.9):
    return {'bbox': [x0, 40, x0 + 20, 100], 'score': score, 'color': color, 'est_xy': list(xy)}


def tracker():
    return types.SimpleNamespace(est=None, state='TRACKING', lost=0, active='W1', last_seen={}, t_seen=0.0)


def frames():
    return {'W1': Image.new('RGB', (320, 180)), 'W2': Image.new('RGB', (320, 180))}


class Fake:
    def __init__(self, answer):
        self.answer, self.bodies = answer, []

    def __call__(self, body):
        self.bodies.append(body)
        a = self.answer(body) if callable(self.answer) else self.answer
        return {'text': json.dumps(a), 'usage': {'input_tokens': 10, 'output_tokens': 5}, 'latency_s': 0.0}


def decider(answer, **kw):
    t = [0.0]
    d = ServiceLiveDeciderE4(Fake(answer), PeopleTracker(), SCENE, run_async=False, clock=lambda: t[0], min_interval_s=0.0, **kw)
    d.reference = b'\xff\xd8ref'
    return d, t


def tracking(xy=(0, 0), lost_ticks=0, state='TRACKING'):
    return {'state': state, 'active_cam': 'W1', 'est_xy': list(xy), 'lost_ticks': lost_ticks, 'events': [], 'target': {'color': 'red'}}


def warm_up(d, t, tr, n=N_STABLE, xy=(0, 0)):
    """n stable rule ticks on W1 with the red target at xy; returns the last tick number."""
    for i in range(n):
        t[0] = 0.2 * (i + 1)
        d.step(i + 1, t[0], tr, tracking(xy), {'W1': [det(10, 'red', xy)], 'W2': []}, frames())
    return n


SELECT_W2 = {'answer': 'SELECT', 'camera_id': 'W2', 'detection_id': 'D1', 'confidence': 'medium', 'next_camera_ranking': ['W2', 'W1'],
             'reason_codes': ['SAME'], 'reason': 'x'}


def test_trusted_track_keeps_select_as_candidate_only_and_ambiguity_is_not_asked():
    d, t = decider(SELECT_W2)
    tr = tracker()
    n = warm_up(d, t, tr)
    assert d.trusted and d.memory[0] == [0, 0]
    asked = len(d.transport.bodies)
    # a second red person 2 m away (AMBIGUOUS in E3): no question while trusted, until the 4 s recheck
    t[0] = 0.2 * (n + 1)
    d.step(n + 1, t[0], tr, tracking(), {'W1': [det(10, 'red', (0, 0)), det(80, 'red', (2, 0))], 'W2': []}, frames())
    assert len(d.transport.bodies) == asked
    d.last_t = -10.0                                                     # force the recheck
    t[0] += 0.2
    d.step(n + 2, t[0], tr, tracking(), {'W1': [det(10, 'red')], 'W2': [det(50, 'red', (1, 0))]}, frames())
    t[0] += 0.2
    out = d.step(n + 3, t[0], tr, tracking(), {'W1': [det(10, 'red')], 'W2': [det(50, 'red', (1, 0))]}, frames())
    last = out['advisor']['last']
    assert last['validation'] == 'CANDIDATE_ONLY_TRUSTED' and not last['applied'] and tr.active == 'W1'
    assert out['advisor']['next_camera_ranking'] == ['W2', 'W1']           # ranking even for a SELECT (d)


def _lost_after_trust(answer, target_xy, color='red'):
    d, t = decider(answer)
    tr = tracker()
    n = warm_up(d, t, tr)
    dets = {'W1': [], 'W2': [det(50, color, target_xy)]}
    t[0] = 0.2 * (n + 1)
    d.step(n + 1, t[0], tr, tracking(lost_ticks=3, state='LOST'), dets, frames())     # LOST -> ask
    t[0] += 0.2
    out = d.step(n + 2, t[0], tr, tracking(lost_ticks=4, state='LOST'), dets, frames())
    return d, tr, out


def test_lost_select_of_a_reachable_red_person_is_applied():
    d, tr, out = _lost_after_trust(SELECT_W2, (1.0, 0))
    assert out['advisor']['last']['validation'] == 'APPLIED' and tr.active == 'W2' and out['state'] == 'TRACKING'
    rec = d.records[-1]
    assert rec['detection_id'] == 'D1' and rec['pid'] is not None


def test_lost_select_of_an_unreachable_person_is_rejected():
    d, tr, out = _lost_after_trust(SELECT_W2, (20.0, 0))                   # 20 m away 0.4 s after the last trusted tick
    assert out['advisor']['last']['validation'] == 'UNREACHABLE' and not out['advisor']['last']['applied'] and tr.active == 'W1'


@pytest.mark.parametrize('conf,expected', [('medium', 'APPEARANCE'), ('high', 'APPLIED')])
def test_colour_mismatch_needs_high_confidence(conf, expected):
    _d, _tr, out = _lost_after_trust({**SELECT_W2, 'confidence': conf}, (1.0, 0), color='blue')
    assert out['advisor']['last']['validation'] == expected


def test_without_memory_a_select_needs_high_confidence():
    d, t = decider(SELECT_W2)
    tr = tracker()
    dets = {'W1': [], 'W2': [det(50, 'red', (1, 0))]}
    d.step(1, 0.2, tr, tracking(lost_ticks=3, state='LOST'), dets, frames())
    out = d.step(2, 0.4, tr, tracking(lost_ticks=4, state='LOST'), dets, frames())
    assert d.memory is None and out['advisor']['last']['validation'] == 'MEMORY_EXPIRED_LOW_CONFIDENCE'


def test_not_visible_is_ignored_while_trusted_and_uncertain_is_its_own_answer():
    d, t = decider({'answer': 'NOT_VISIBLE', 'next_camera_ranking': ['W2'], 'reason_codes': [], 'reason': ''})
    tr = tracker()
    warm_up(d, t, tr, n=N_STABLE + 1)                                      # the first DEGRADED question is answered while trusted
    assert d.records and d.records[-1]['validation'] == 'NOT_VISIBLE_IGNORED_TRUSTED'
    inp = ag.DecisionInput(scene_context=SCENE, t_s=0.0, candidates=[], seed_colors=('red',), reference_jpeg=None, frames=[],
                           rule_display=None, rule_answer=None, last_camera='W1')
    ans, err = parse_e4(json.dumps({'answer': 'UNCERTAIN', 'next_camera_ranking': ['W2', 'NOPE', 'W2', 'W1']}), inp)
    assert err is None and ans['answer'] == 'UNCERTAIN' and ans['next_camera_ranking'] == ['W2', 'W1']
    ans, _ = parse_e4(json.dumps({'answer': 'NOT_VISIBLE', 'next_camera_hint': 'W2'}), inp)
    assert ans['next_camera_ranking'] == ['W2'] and ans['ranking_supplied'] is False


def test_request_has_e4_addendum_and_the_call_record_keeps_candidates_and_text():
    d, tr, _out = _lost_after_trust(SELECT_W2, (1.0, 0))
    body = d.transport.bodies[-1]
    assert body['input'][0]['content'][0]['text'].endswith(E4_EXTRA)
    log = d.calls_log[-1]
    assert log['candidate_list'][0]['detection_id'] == 'D1' and log['candidate_list'][0]['camera_id'] == 'W2'
    assert 'DETECTIONS' in log['variable_text'] and set(log['images']) == {'W1', 'W2'}
    assert d.records[-1]['prefix_sha256'] and d.records[-1]['trusted'] is False and d.records[-1]['lost'] is True

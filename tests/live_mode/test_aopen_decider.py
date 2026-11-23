"""E5 contract tests: local fake responses only. No model, network or evaluation annotations."""
import json

import pytest
from PIL import Image

from amidst.live_mode.aopen.decider import AOpenDecider, E5_EXTRA, parse_answer
from amidst.q1q5 import agent_service as ag

BOX = [10, 10, 30, 90]
SCENE = {'cameras': [{'camera_id': c} for c in ('A', 'B', 'C', 'D')]}


class Projection:
    def ground(self, *args):
        return [1, 2]


def answer(kind='SELECT', **kw):
    return {'answer': kind, 'camera_id': 'A', 'detection_id': 'D1', 'box_xyxy': BOX,
            'next_camera_ranking': ['B', 'A'], 'confidence': 'medium', **kw}


def transport(*docs, latency=0):
    todo = iter(docs)
    def run(body):
        x = next(todo)
        if isinstance(x, Exception):
            raise x
        return {'text': x if isinstance(x, str) else json.dumps(x), 'latency_s': latency,
                'usage': {'input_tokens': 10, 'output_tokens': 5}}
    return run


def new(*docs, **kw):
    return AOpenDecider(transport(*docs), SCENE, Projection(), call_cap=kw.pop('call_cap', len(docs)), **kw)


@pytest.fixture
def frames():
    images = {c: Image.new('RGB', (320, 180), 'black') for c in ('A', 'B', 'C', 'D')}
    yield images
    for im in images.values():
        im.close()


def dets():
    return {'A': [{'bbox': list(BOX), 'score': 0.15, 'color': 'blue', 'est_xy': [1, 2]}],
            'B': [{'bbox': [50, 10, 70, 90], 'score': 0.16, 'color': 'red', 'est_xy': [8, 8]}]}


def rule(acquire=False, **kw):
    return {'state': 'LOST', 'active_cam': 'A', 'est_xy': [1, 2], 'lost_ticks': 99,
            'events': [{'type': 'ACQUIRE'}] if acquire else [], **kw}


def step(d, frames, tick, **kw):
    return d.step(tick, kw.pop('detections', dets()), frames, kw.pop('rule_state', rule(tick == 0)))


def test_no_seed_no_call_and_first_call_at_b1_acquire(frames):
    d = new(answer())
    assert step(d, frames, 0, rule_state=rule())['tracking']['state'] == 'LOST'
    assert d.calls == []
    row = step(d, frames, 1, rule_state=rule(True))
    assert d.calls[0]['kind'] == 'FIRST' and d.calls[0]['ask_tick'] == d.seed_tick == 1
    assert row['tracking']['state'] == 'LOST'
    row = step(d, frames, 2)
    assert row['tracking']['active_cam'] == 'A' and row['decision_source'] == 'AGENT'
    assert d.calls[0]['applied'] and d.calls[0]['detection_id'] == 'D1'
    assert d.calls[0]['request']['candidate_list'][0]['rule_eligible'] is False


@pytest.mark.parametrize('kind', ['SELECT', 'OWN_BOX'])
def test_agent_takes_over_any_camera_without_rule_gate(frames, kind):
    d = new(answer(kind, camera_id='B', box_xyxy=[100, 20, 140, 150]))
    d.neutral.adopt(-1, 'A', BOX, 'AGENT_SELECT')
    step(d, frames, 0)
    row = step(d, frames, 1, rule_state=rule(state='LOST', active_cam='A'))
    expected = [50, 10, 70, 90] if kind == 'SELECT' else [100, 20, 140, 150]
    assert row['tracking']['active_cam'] == 'B' and row['tracking']['box'] == expected
    assert row['tracking']['lost_ticks'] == 0 and d.calls[0]['source'] == 'AGENT'
    assert any(e['type'] == 'SWITCH' for e in row['events'])


def test_uncertain_keeps_target_not_visible_clears_and_ranking_updates(frames):
    d = new(answer(), answer('UNCERTAIN', next_camera_ranking=[]), answer('NOT_VISIBLE', next_camera_ranking=['C']))
    step(d, frames, 0)
    for tick in range(1, 12):
        row = step(d, frames, tick)
    assert row['tracking']['active_cam'] == 'A' and row['ranking'] == []
    assert d.calls[1]['applied'] is False and d.calls[1]['fallback_reason'] is None
    for tick in range(12, 22):
        row = step(d, frames, tick)
    assert row['tracking']['state'] == 'LOST' and row['ranking'] == ['C']
    assert d.calls[2]['applied'] is True


def test_occluded_hold_uncertain_does_not_extend_and_no_reacquire(frames):
    d = new(answer('STILL_HERE_OCCLUDED'), answer('UNCERTAIN'))
    d.neutral.adopt(-1, 'A', BOX, 'AGENT_SELECT')
    step(d, frames, 0)
    for tick in range(1, 11):
        row = step(d, frames, tick)
        assert row['tracking']['box'] is None and row['neutral_status'] == 'OCCLUDED_HOLD'
    row = step(d, frames, 11)
    assert row['tracking']['state'] == 'LOST' and d.calls[1]['answer'] == 'UNCERTAIN'
    assert d.calls[1]['applied'] is False


@pytest.mark.parametrize('existing,cam', [(False, 'A'), (True, 'B')])
def test_occluded_no_target_or_other_camera(frames, existing, cam):
    d = new(answer('STILL_HERE_OCCLUDED', camera_id=cam))
    if existing:
        d.neutral.adopt(-1, 'A', BOX, 'AGENT_SELECT')
    step(d, frames, 0)
    row = step(d, frames, 1)
    assert d.calls[0]['fallback_reason'] == 'OCCLUDED_NO_TARGET' and not d.calls[0]['applied']
    assert row['tracking']['active_cam'] == ('A' if existing else None)


def test_call_cap_is_one_event_and_lost_early_respects_min_interval(frames):
    d = new(answer('NOT_VISIBLE'), answer('NOT_VISIBLE'))
    rows = [step(d, frames, t) for t in range(25)]
    assert [r['ask_tick'] for r in d.calls] == [0, 5]
    caps = [(r['tick'], e) for r in rows for e in r['events'] if e['type'] == 'CALL_CAP_REACHED']
    assert len(caps) == 1 and caps[0][0] == 5 and len(d.calls) == 2
    assert all(c['fallback_reason'] != 'CALL_CAP_REACHED' for c in d.calls)


def test_request_numbering_ranking_order_scene_prompt_and_complete_log(frames):
    d = new(answer('NOT_VISIBLE', next_camera_ranking=['C', 'B']), answer('UNCERTAIN'))
    for tick in range(6):
        step(d, frames, tick)
    r = d.calls[1]['request']
    assert list(r['images']) == ['C', 'B', 'A', 'D']
    assert [(x['camera_id'], x['detection_id']) for x in r['candidate_list']] == [('B', 'D1'), ('A', 'D1')]
    assert r['reference'] and len(r['prefix_sha256']) == 64 and 'AO_STATE=' in r['variable_text']
    assert 'score>=0.3' not in r['variable_text']
    inp, body, req = d.build_input(6, frames, dets(), rule())
    assert E5_EXTRA in body['input'][0]['content'][0]['text']
    assert 'SCENE_CONTEXT=' in body['input'][0]['content'][0]['text']
    assert '320x180' in E5_EXTRA and len(req['body_sha256']) == 64
    assert req['rule_state'] == {'state': 'LOST', 'active_cam': 'A', 'lost_ticks': 99}
    assert inp.scene_context == SCENE


@pytest.mark.parametrize('latency,apply_tick', [(0, 1), (0.4, 3), (1.0, 6)])
@pytest.mark.parametrize('kind', ['SELECT', 'OWN_BOX'])
def test_aol_one_inflight_strict_arrival_and_chain(frames, latency, apply_tick, kind):
    d = AOpenDecider(transport(answer(kind), latency=latency), SCENE, Projection(), mode='simlive', call_cap=1)
    rows = [step(d, frames, t) for t in range(apply_tick + 1)]
    assert all(r['tracking']['state'] == 'LOST' for r in rows[:-1])
    assert rows[-1]['tracking']['active_cam'] == 'A' and d.calls[0]['applied']
    assert d.calls[0]['ticks_chained'] == apply_tick and len(d.calls) == 1


@pytest.mark.parametrize('kind', ['SELECT', 'OWN_BOX'])
def test_aol_expired_on_any_chain_gap_including_arrival_tick(frames, kind):
    d = AOpenDecider(transport(answer(kind), latency=0.4), SCENE, Projection(), mode='simlive', call_cap=1)
    step(d, frames, 0)
    step(d, frames, 1)
    step(d, frames, 2)
    row = step(d, frames, 3, detections={'A': [], 'B': dets()['B']})
    assert row['tracking']['state'] == 'LOST'
    assert d.calls[0]['fallback_reason'] == 'EXPIRED' and d.calls[0]['source'] == 'NEUTRAL'


@pytest.mark.parametrize('exception,reason', [(TimeoutError('timed out'), 'PROVIDER_TIMEOUT'),
    (RuntimeError('server unavailable'), 'PROVIDER_ERROR'),
    (PermissionError('GUARD_DENIED:TOTAL_BUDGET'), 'CALL_BUDGET_EXHAUSTED'),
    (PermissionError('NO_API_KEY'), 'PROVIDER_ERROR')])
def test_transport_errors_keep_neutral_target(frames, exception, reason):
    d = new(exception)
    d.neutral.adopt(-1, 'A', BOX, 'AGENT_SELECT')
    step(d, frames, 0)
    row = step(d, frames, 1)
    assert row['tracking']['active_cam'] == 'A' and d.calls[0]['fallback_reason'] == reason
    assert d.calls[0]['source'] == 'NEUTRAL' and d.calls[0]['applied'] is False


def test_timeout_and_budget_denial_no_more_attempts(frames):
    d = AOpenDecider(transport(answer(), latency=31), SCENE, Projection(), call_cap=1)
    step(d, frames, 0); step(d, frames, 1)
    assert d.calls[0]['fallback_reason'] == 'PROVIDER_TIMEOUT'
    d = new(PermissionError('GUARD_DENIED:TOTAL_BUDGET'), answer(), call_cap=10)
    for tick in range(30):
        step(d, frames, tick)
    assert len(d.calls) == 1 and d.budget_exhausted


@pytest.fixture
def inp():
    return ag.DecisionInput(SCENE, 0, [ag.Candidate('D1', 'A', tuple(BOX), .15, 'person')], frames=[('A', b'x'), ('B', b'x'), ('C', b'x'), ('D', b'x')])


@pytest.mark.parametrize('raw,expected', [('oops', 'FORMAT_INVALID'), ('[]', 'FORMAT_INVALID'), ('null', 'FORMAT_INVALID'),
    ('{"answer":[]}', 'FORMAT_INVALID'), ('{"answer":"BAD"}', 'FORMAT_INVALID'),
    (json.dumps(answer(detection_id='D99')), 'UNKNOWN_DETECTION'),
    (json.dumps(answer(camera_id='Z')), 'UNKNOWN_DETECTION'),
    (json.dumps(answer('STILL_HERE_OCCLUDED', camera_id='Z')), 'BAD_CAMERA'),
    (json.dumps(answer('STILL_HERE_OCCLUDED', camera_id=[])), 'BAD_CAMERA')])
def test_format_error_classes(inp, raw, expected):
    assert parse_answer(raw, inp) == (None, expected)


@pytest.mark.parametrize('box', [None, [], [0, 0, 10], [-1, 0, 10, 20], [10, 0, 10, 20], [0, 0, 321, 10],
    [0, 0, 10, 181], [True, 0, 10, 20], ['0', 0, 10, 20], [0, 0, float('nan'), 20], [0, 0, float('inf'), 20]])
def test_bad_own_boxes(inp, box):
    assert parse_answer(json.dumps(answer('OWN_BOX', box_xyxy=box)), inp)[1] == 'BAD_OWN_BOX'


def test_full_size_own_box_and_ranking_filter_hint_diagnostic_only(inp):
    a, err = parse_answer(json.dumps(answer('OWN_BOX', box_xyxy=[0, 0, 320, 180],
        next_camera_ranking=['B', 'B', {}, 'Z', 'A', 'C', 'D'], reason_codes=list('abcdef'))), inp)
    assert err is None and a['box_xyxy'] == [0, 0, 320, 180]
    assert a['next_camera_ranking'] == ['B', 'A', 'C'] and len(a['reason_codes']) == 4
    for rank in (None, [], ['Z'], 'B'):
        doc = answer(next_camera_ranking=rank, next_camera_hint='B')
        a, err = parse_answer(json.dumps(doc), inp)
        assert err is None and a['ranking_supplied'] is False and a['next_camera_ranking'] == []
        assert a['next_camera_hint_raw'] == 'B'


def test_strict_arrival_at_nonzero_call_time(frames):
    d = AOpenDecider(transport(answer(), latency=0.4), SCENE, Projection(), mode='simlive', call_cap=1)
    step(d, frames, 3, rule_state=rule(True))
    step(d, frames, 4)
    assert step(d, frames, 5)['tracking']['state'] == 'LOST'  # t=1.0 equals t_call+.4
    assert step(d, frames, 6)['tracking']['active_cam'] == 'A'


def test_bad_own_box_huge_integer_is_format_rejection(inp):
    assert parse_answer(json.dumps(answer('OWN_BOX', box_xyxy=[0, 0, 10**500, 10])), inp)[1] == 'BAD_OWN_BOX'

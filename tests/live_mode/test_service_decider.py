"""F3 (#657): LIVE agent mode through agent_service (no network, no model, no ground truth)."""
import json
import types

import pytest

from amidst.live_mode.people import PeopleTracker
from amidst.live_mode.service_decider import ServiceLiveDecider, guarded_responses_transport

Image = pytest.importorskip("PIL.Image")
SCENE = {'schema_version': 'SYNTHETIC', 'cameras': [{'camera_id': 'W1'}, {'camera_id': 'W2'}], 'overlaps': [], 'incomplete': []}


def det(x0, color='blue', xy=(0, 0)):
    return {'bbox': [x0, 40, x0 + 20, 100], 'score': 0.9, 'color': color, 'est_xy': list(xy)}


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
        if isinstance(a, Exception):
            raise a
        return {'text': json.dumps(a), 'usage': {'input_tokens': 10, 'output_tokens': 5}, 'latency_s': 0.0}


def decider(answer, **kw):
    t = [0.0]
    d = ServiceLiveDecider(Fake(answer), PeopleTracker(), SCENE, run_async=False, clock=lambda: t[0], min_interval_s=0.0, **kw)
    d.reference = b'\xff\xd8ref'
    return d, t


def lost(tick, t_s):
    return {'state': 'LOST', 'active_cam': 'W1', 'est_xy': [0, 0], 'lost_ticks': 3, 'events': [], 'target': {'color': 'red'}}


def test_lost_with_zero_people_still_asks_and_not_visible_is_recorded():
    d, _t = decider({'answer': 'NOT_VISIBLE', 'next_camera_hint': 'W2', 'reason_codes': ['GONE'], 'reason': 'x'})
    d.prev_est = [0, 0]
    out = d.step(1, 1.0, tracker(), lost(1, 1.0), {'W1': [], 'W2': []}, frames())
    assert len(d.transport.bodies) == 1                                          # asked with nobody in view (C7: LiveDecider needs >= 2)
    out = d.step(2, 1.2, tracker(), lost(2, 1.2), {'W1': [], 'W2': []}, frames())
    assert out['advisor']['last']['answer'] == 'NOT_VISIBLE' and out['advisor']['next_camera_hint'] == 'W2'
    assert out['decision_source'] == 'AGENT' and d.records[0]['source'] == 'AGENT'


def test_single_non_red_person_is_a_candidate_and_a_select_moves_the_tracker():
    def pick(body):
        return {'answer': 'SELECT', 'camera_id': 'W2', 'detection_id': 'D1', 'reason_codes': ['SAME'], 'reason': 'x'}
    d, _t = decider(pick)
    d.prev_est = [0, 0]
    tr = tracker()
    dets = {'W1': [], 'W2': [det(50, 'blue', (4, 0))]}
    d.step(1, 1.0, tr, lost(1, 1.0), dets, frames())
    text = d.transport.bodies[0]['input'][-1]['content'][0]['text']
    assert '- W2 D1: person' in text and 'COLOUR_NO_MATCH' in text                 # blue person listed, colour gate as information
    out = d.step(2, 1.1, tr, lost(2, 1.1), dets, frames())
    assert out['state'] == 'TRACKING' and out['active_cam'] == 'W2' and tr.active == 'W2' and out['est_xy'] == [4, 0]
    assert out['advisor']['last']['applied'] and any(e['type'] == 'SWITCH' and e['detail']['by'] == 'AGENT' for e in out['events'])


def test_request_has_scene_context_and_every_camera_frame():
    d, _t = decider({'answer': 'NOT_VISIBLE', 'reason_codes': [], 'reason': ''})
    d.prev_est = [0, 0]
    d.step(1, 1.0, tracker(), lost(1, 1.0), {'W1': [det(10, 'red')], 'W2': []}, frames())
    body = d.transport.bodies[0]
    assert 'SCENE_CONTEXT_SHA256=' in body['input'][0]['content'][0]['text']
    imgs = [p for p in body['input'][-1]['content'] if p['type'] == 'input_image']
    assert len(imgs) == 2                                                             # W1 and W2, not only the camera with a candidate


def test_tracked_target_is_rechecked_periodically_even_with_one_person():
    d, t = decider({'answer': 'STILL_HERE_OCCLUDED', 'camera_id': 'W1', 'reason_codes': [], 'reason': ''}, recheck_s=4.0)
    tracking = {'state': 'TRACKING', 'active_cam': 'W1', 'est_xy': [0, 0], 'lost_ticks': 0, 'events': [], 'target': {'color': 'red'}}
    d.prev_est = [0, 0]
    d.last_t = 0.0
    d.step(1, 1.0, tracker(), dict(tracking), {'W1': [det(10, 'red')]}, frames())
    assert d.transport.bodies == []                                                   # 1 s since the last answer: no question
    d.step(2, 5.0, tracker(), dict(tracking), {'W1': [det(10, 'red')]}, frames())
    assert len(d.transport.bodies) == 1


@pytest.mark.parametrize('exc,code', [(PermissionError('GUARD_DENIED:TOTAL_BUDGET'), 'CALL_BUDGET_EXHAUSTED'),
                                      (PermissionError('NO_API_KEY'), 'MODE_NOT_AUTHORIZED'), (RuntimeError('boom'), 'PROVIDER_UNAVAILABLE')])
def test_failures_fall_back_to_the_rule_with_reason(exc, code):
    d, _t = decider(exc)
    d.prev_est = [0, 0]
    d.step(1, 1.0, tracker(), lost(1, 1.0), {'W1': []}, frames())
    out = d.step(2, 1.1, tracker(), lost(2, 1.1), {'W1': []}, frames())
    assert out['decision_source'] == 'RULE_FALLBACK' and out['fallback_reason'] == code and out['state'] == 'LOST'


def test_guarded_transport_goes_through_apiguard_and_reads_the_key_only_inside():
    seen = {}

    class Guard:
        def run(self, caller, model, est, max_out, fn):
            seen.update(caller=caller, model=model, est=est)
            v = fn()[0]
            return types.SimpleNamespace(allowed=True, value=v, reason=None)

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({'output': [{'content': [{'type': 'output_text', 'text': '{"answer":"NOT_VISIBLE"}'}]}],
                               'usage': {'input_tokens': 7, 'output_tokens': 3}}).encode()

    def opener(req, timeout):
        seen['auth'] = req.headers['Authorization']
        return Resp()
    tr = guarded_responses_transport(Guard(), 'gpt-6.1-terra', 5.0, env={'OPENAI_API_KEY': 'sk-test'}, opener=opener)
    out = tr({'model': 'gpt-6.1-terra', 'max_output_tokens': 100,
              'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'x' * 30}, {'type': 'input_image', 'image_url': 'data:'}]}]})
    assert out['text'] == '{"answer":"NOT_VISIBLE"}' and seen['caller'] == 'live_agent' and seen['est'] >= 1100 and seen['auth'] == 'Bearer sk-test'

    class Deny(Guard):
        def run(self, *a):
            return types.SimpleNamespace(allowed=False, value=None, reason='TOTAL_BUDGET')
    with pytest.raises(PermissionError):
        guarded_responses_transport(Deny(), 'm', 1.0, env={'OPENAI_API_KEY': 'k'})({'model': 'm', 'max_output_tokens': 1, 'input': []})


def test_switch_accepts_agent_mode():
    from amidst.live_mode.llm_switch import resolve
    r = resolve('agent', 'fake')
    assert r['effective'] == 'agent' and r['available']


@pytest.mark.parametrize('answer', [
    {'answer': 'SELECT', 'camera_id': 'W2', 'detection_id': 'D1', 'reason_codes': [], 'reason': ''},
    {'answer': 'NOT_VISIBLE', 'reason_codes': [], 'reason': ''},
])
def test_completed_reply_after_deadline_is_not_applied(answer):
    d, clock = decider(answer, timeout_s=1)
    tr = tracker()
    dets = {'W2': [det(10, xy=(8, 0))]}
    d.step(1, 1, tr, lost(1, 1), dets, frames())
    clock[0] = 1.01
    out = d.step(2, 1.5, tr, lost(2, 1.5), dets, frames())
    assert out['decision_source'] == 'RULE_FALLBACK'
    assert out['fallback_reason'] == 'TIME_BUDGET'
    assert out['state'] == 'LOST' and tr.active == 'W1'
    assert not out['advisor']['last']['applied']
    assert len(out['advisor']['last']['request_sha256']) == 64


def test_decision_record_has_reproducible_request_hash_without_storing_body():
    import hashlib
    d, _ = decider({'answer': 'NOT_VISIBLE', 'reason_codes': [], 'reason': ''})
    d.step(1, 1, tracker(), lost(1, 1), {}, frames())
    d.step(2, 1.5, tracker(), lost(2, 1.5), {}, frames())
    body = d.transport.bodies[0]
    expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    assert d.records[0]['request_sha256'] == expected
    assert d.records[0]['identity_verdict'] == 'UNCONFIRMED'
    assert 'input' not in d.records[0]


def test_transport_dry_run_precedes_guard_and_reserves_uncached_cost(tmp_path):
    from amidst.q1q5.api_budget import ApiGuard, GuardConfig
    g = ApiGuard(GuardConfig(enabled=True, max_usd_total=1, prices={'m': {
        'input_usd_per_mtok': 1, 'output_usd_per_mtok': 5, 'cached_input_usd_per_mtok': 0.05}}), usage_dir=tmp_path)
    transport = guarded_responses_transport(g, 'm', 1, env={}, opener=lambda *_a, **_k: pytest.fail('no network'))
    with pytest.raises(PermissionError, match='NO_API_KEY'):
        transport({'model': 'm', 'max_output_tokens': 100, 'input': []})
    assert transport.last_estimate['est_cost_per_call_usd'] == pytest.approx(0.001)


def test_invalid_agent_reply_falls_back_without_moving_rule_tracker():
    d, _ = decider({'answer': 'SELECT', 'camera_id': 'W2', 'detection_id': 'NOT_A_DETECTION'})
    tr = tracker()
    d.step(1, 1, tr, lost(1, 1), {'W2': [det(10, xy=(8, 0))]}, frames())
    out = d.step(2, 1.1, tr, lost(2, 1.1), {'W2': [det(10, xy=(8, 0))]}, frames())
    assert out['decision_source'] == 'RULE_FALLBACK' and out['fallback_reason'] == 'INVALID_RESPONSE'
    assert tr.active == 'W1' and out['state'] == 'LOST'

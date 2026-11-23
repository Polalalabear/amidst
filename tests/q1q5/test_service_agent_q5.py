"""F3 (#657): 8785 Agent mode through agent_service. SYNTHETIC index, fake transport, no network, no GT."""
import json
import re
from dataclasses import replace

import pytest
from test_q5_agent import bindings
from test_q5_controller import port, request, seed_id

import amidst.q1q5.q5_controller as qc
from amidst.q1q5 import openai_gateway as og
from amidst.q1q5.q5_controller import RuleController
from amidst.q1q5.service_agent_q5 import ServiceAgentController, ServiceAgentFactory
from amidst.q1q5.store import canonical_hash

SCENE = {'schema_version': 'SYNTHETIC', 'cameras': [{'camera_id': 'A'}, {'camera_id': 'B'}], 'overlaps': [], 'incomplete': ['SYNTHETIC']}
FORBIDDEN = ('ground_truth', 'gt_', 'visibility', 'depth', 'trajectory')


def _detections(body):
    text = body['input'][-1]['content'][0]['text']
    return re.findall(r'^- (\S+) (D\d+): (\S+) score ([\d.]+) .* rule_eligible=(\w+) gate=(\S+)', text, re.M)


class Fake:
    """Answers from the variable layer of the real request body."""

    def __init__(self, policy):
        self.policy, self.bodies = policy, []

    def __call__(self, body):
        self.bodies.append(body)
        out = self.policy(body, _detections(body))
        if isinstance(out, Exception):
            raise out
        return {'text': json.dumps(out), 'usage': {'input_tokens': 100, 'cached_tokens': 0, 'cache_write_tokens': 0, 'output_tokens': 20},
                'latency_s': 0.01}


def select_b(body, dets):
    b = [d for d in dets if d[0] == 'B']
    if not b:
        return {'answer': 'NOT_VISIBLE', 'next_camera_hint': 'B', 'reason_codes': ['NO_B'], 'reason': 'not visible'}
    return {'answer': 'SELECT', 'camera_id': 'B', 'detection_id': b[0][1], 'confidence': 'medium', 'reason_codes': ['SAME_SHAPE'], 'reason': 'b'}


def run(b, mode='AGENT_SEQUENTIAL', transport=None, cls=ServiceAgentController, **kw):
    q = request(b)
    q['switch_mode'] = mode
    calls = []
    args = dict(bindings=b, evidence_provider=port(calls), selected_observation_id=seed_id(b))
    c = RuleController(q, **args) if cls is RuleController else cls(q, transport=transport, scene_context=SCENE, **args, **kw)
    return c.run(), c


def decisions(result):
    return [json.loads(x) for x in result.decisions_bytes.splitlines()]


def test_rule_mode_is_byte_identical_to_rule_controller_and_never_calls_the_model():
    b = bindings()
    fake = Fake(select_b)
    rule, _ = run(b, 'RULE_ONLY', cls=RuleController)
    svc, c = run(b, 'RULE_ONLY', transport=fake)
    assert svc.decisions_bytes == rule.decisions_bytes and svc.links_bytes == rule.links_bytes
    assert svc.response['output_sha256'] == rule.response['output_sha256']
    assert fake.bodies == [] and c.agent_records == [] and not svc.response['agent_attempted']


def test_agent_answer_is_adopted_over_the_colour_gate_with_rule_override_recorded():
    b = bindings({'A': {0: 'STRONG', 1: 'STRONG'}, 'B': {i: 'NONE' for i in range(5, 10)}})
    rule, _ = run(b, 'RULE_ONLY', cls=RuleController)
    assert not any(d['executed_action'] == 'SWITCH' for d in decisions(rule))      # the rule never cuts to B (colour NONE)
    fake = Fake(select_b)
    res, c = run(b, transport=fake)
    rows = decisions(res)
    sw = [d for d in rows if d['executed_action'] == 'SWITCH']
    assert sw and sw[0]['decided_by'] == 'AGENT' and len(sw[0]['llm_calls']) == 1 and sw[0]['llm_calls'][0]['validation'] == 'PASS'
    ans = sw[0]['submitted']['agent_answer']
    assert ans['answer'] == 'SELECT' and ans['reason_codes'][0].startswith('RULE_OVERRIDE:') and 'COLOUR_NO_MATCH' in ans['reason_codes'][0]
    assert sw[0]['submitted']['rule_answer']['action'] == 'RETURN_TO_ORIGIN'
    assert sw[0]['entry_observation_id'].split(':')[2] == 'B'
    seg = [s for s in res.response['timeline'] if s['kind'] == 'ON_CAMERA' and s['camera_id'] == 'B']
    assert seg and seg[0]['decided_by'] == 'AGENT' and seg[0]['decision_id'] == sw[0]['decision_id']
    assert res.response['agent_used'] and res.response['agent_attempted'] and not res.response['fallback_used']
    tr = c.trace()
    assert tr['content_sha256'] == canonical_hash(tr, exclude=('content_sha256',)) and tr['records'][0]['agent_used']


def test_x1_empty_rule_snapshot_still_asks_the_agent_and_it_may_switch(monkeypatch):
    original = qc.transition_candidates

    def unapproved(*a, **k):                         # the rule view when the graph scope is not approved (candidates.py L63-71)
        s = original(*a, **k)
        s['excluded_transitions'] += [{'transition_id': c['transition_id'], 'reason': 'GRAPH_NOT_APPROVED'} for c in s['candidates']]
        s['candidates'] = []
        s['candidate_set_complete'] = True
        s.pop('candidate_snapshot_sha256')
        s['candidate_snapshot_sha256'] = canonical_hash(s)
        return s
    monkeypatch.setattr(qc, 'transition_candidates', unapproved)
    b = bindings()
    rule, _ = run(b, 'RULE_ONLY', cls=RuleController)
    assert not any(d['executed_action'] == 'SWITCH' for d in decisions(rule))
    fake = Fake(select_b)
    res, _c = run(b, transport=fake)
    sw = [d for d in decisions(res) if d['executed_action'] == 'SWITCH']
    assert fake.bodies and sw and sw[0]['decided_by'] == 'AGENT'
    assert sw[0]['executed_candidate_ref'] is None and sw[0]['submitted']['in_rule_snapshot'] is False


def test_failure_falls_back_to_the_rule_answer_with_contract_reason():
    b = bindings()
    res, c = run(b, transport=Fake(lambda body, d: og.GatewayServiceError('TIMEOUT')))
    rows = decisions(res)
    sw = [d for d in rows if d['executed_action'] == 'SWITCH']
    rule, _ = run(b, 'RULE_ONLY', cls=RuleController)
    rule_sw = [d for d in decisions(rule) if d['executed_action'] == 'SWITCH']
    assert sw and sw[0]['decided_by'] == 'RULE_FALLBACK' and sw[0]['entry_observation_id'] == rule_sw[0]['entry_observation_id']
    assert sw[0]['fallback_reason'] == 'PROVIDER_TIMEOUT' and sw[0]['llm_calls'][0]['validation'].startswith('TRANSPORT:')
    assert res.response['fallback_used'] and res.response['fallback_reason'] == 'PROVIDER_TIMEOUT' and not res.response['agent_used']


@pytest.mark.parametrize('reply,code', [('not json', 'INVALID_RESPONSE'), (og.GatewayServiceError('GUARD_NOT_APPROVED'), 'MODE_NOT_AUTHORIZED'),
                                        (og.GatewayServiceError('GATEWAY_OFFLINE'), 'PROVIDER_UNAVAILABLE')])
def test_fallback_codes_are_from_the_closed_list(reply, code):
    def policy(body, dets):
        return reply
    fake = Fake(policy)
    if isinstance(reply, str):
        fake = lambda body: {'text': reply, 'usage': {}}   # noqa: E731
    res, _ = run(bindings(), transport=fake)
    assert res.response['fallback_reason'] == code


def test_not_visible_keeps_searching_decided_by_the_agent():
    res, _ = run(bindings(), transport=Fake(lambda body, d: {'answer': 'NOT_VISIBLE', 'next_camera_hint': 'B', 'reason_codes': ['GONE'], 'reason': 'x'}))
    rows = decisions(res)
    back = [d for d in rows if d['executed_action'] == 'RETURN_TO_ORIGIN']
    assert back and all(d['decided_by'] == 'AGENT' and d['submitted']['agent_answer']['answer'] == 'NOT_VISIBLE' for d in back)
    assert back[0]['submitted']['agent_answer']['next_camera_hint'] == 'B'
    assert not any(d['executed_action'] == 'SWITCH' for d in rows)


def test_request_lists_every_camera_and_class_with_gates_and_carries_no_gt():
    fake = Fake(select_b)
    run(bindings({'A': {0: 'STRONG', 1: 'STRONG'}, 'B': {i: 'NONE' for i in range(5, 10)}}), transport=fake)
    body = next(b for b in fake.bodies if any(d[0] == 'B' for d in _detections(b)))   # first search: B has no box yet
    dets = _detections(body)
    assert {d[0] for d in dets} >= {'B'} and any(d[4] == 'false' and 'COLOUR_NO_MATCH' in d[5] for d in dets)
    prefix = body['input'][0]['content'][0]['text']
    assert 'SCENE_CONTEXT_SHA256=' in prefix and body['prompt_cache_key']
    blob = json.dumps(body).lower()
    assert not any(k in blob for k in FORBIDDEN)


def test_session_round_limit_hands_over_to_the_rule():
    b = bindings({'A': {0: 'STRONG', 1: 'STRONG'}, 'B': {i: 'NONE' for i in range(5, 10)}}, session_max_agent_rounds=1)
    fake = Fake(lambda body, d: {'answer': 'NOT_VISIBLE', 'reason_codes': [], 'reason': ''})
    res, c = run(b, transport=fake)
    assert len(fake.bodies) == 1 and res.response['fallback_reason'] in (None, 'ROUND_LIMIT')
    assert c.fallback_reason == 'ROUND_LIMIT' or len([d for d in decisions(res) if d['searching_index']]) <= 1


def test_factory_builds_service_controller_and_reports_availability(tmp_path):
    t = og.GatewayResponsesTransport(tmp_path / 'q', wall=lambda: 0.0)
    f = ServiceAgentFactory(t, scene_context=SCENE)
    assert f.availability() == (False, 'GATEWAY_OFFLINE')
    b = bindings()
    q = request(b)
    q['switch_mode'] = 'AGENT_SEQUENTIAL'
    c = f(q, bindings=b, evidence_provider=port([]), selected_observation_id=seed_id(b))
    assert isinstance(c, ServiceAgentController) and c.scene_context is SCENE


def test_gateway_service_channel_round_trip_through_apiguard(tmp_path):
    from test_openai_gateway import SECRET, guard
    queue = tmp_path / 'q'
    calls = []

    def fake_responses(body, timeout_s, env):
        assert env['OPENAI_API_KEY'] == SECRET and body['model'] == og.API_MODEL
        calls.append(body)
        return {'text': '{"answer":"NOT_VISIBLE"}', 'usage': {'input_tokens': 900, 'cached_tokens': 0, 'cache_write_tokens': 0, 'output_tokens': 10},
                'response_id': 'r', 'status': 'completed', 'latency_s': 0.1}
    worker = og.GatewayWorker(queue, guard(tmp_path), call_responses=fake_responses, env={'OPENAI_API_KEY': SECRET})
    worker.write_status()
    t = og.GatewayResponsesTransport(queue, timeout_ms=5000, sleep=lambda s: worker.process_once())
    body = {'model': og.API_MODEL, 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'hello JSON'}]}], 'max_output_tokens': 100}
    out = t(body)
    assert out['text'] == '{"answer":"NOT_VISIBLE"}' and calls == [body]
    assert og.service_token_estimate({'input': [{'content': [{'type': 'input_image'}, {'type': 'input_text', 'text': 'x' * 30}]}]}) >= 1100
    bad = dict(body, input=[{'role': 'user', 'content': [{'type': 'input_text', 'text': 'see /Users/someone/file'}]}])
    with pytest.raises(og.GatewayError):
        t(bad)


def test_configure_environment_with_service_binds_service_factories(tmp_path):
    from test_openai_gateway import run_binding
    rs = [run_binding(), run_binding(agent=True)]
    out = og.configure_environment(rs, tmp_path / 'q', env={'AMIDST_RECORDED_AGENT': 'openai'}, service=lambda run: {'scene_context': SCENE})
    assert all(isinstance(r.agent_factory, ServiceAgentFactory) and r.agent_factory.scene_context is SCENE for r in out)
    assert og.configure_environment(rs, tmp_path / 'q', env={}, service=lambda run: {}) == tuple(rs)
    assert replace  # imported for fixtures parity

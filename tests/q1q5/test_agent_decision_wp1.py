"""WP1 gate for docs/design/AGENT_DECISION_V1.md: contract, validators, rule decider, caps.

No LLM, provider or network is used: providers are scripted fakes returning Attempt objects.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from amidst.q1q5 import agent_decision as ad
from amidst.q1q5.agent_decision import AgentDecisionError, Attempt, CallBudget, RuleDecider
from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, associate

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'docs/contracts/schemas/q-core.agent-decision.v1.schema.json').read_text())
PARAMS_SCHEMA = json.loads((ROOT / 'docs/contracts/schemas/q-core.agent-decision-params.v1.schema.json').read_text())
FORMAL = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1.json').read_text())
EXPLORATORY = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1_exploratory.json').read_text())
MODULE = ROOT / 'src/amidst/q1q5/agent_decision.py'
STAGE = 'PILOT_AND_CONSISTENCY'
COMMON_V2 = ROOT / 'src/amidst/contracts/q_demo/schemas/common.v2.schema.json'
PRE_D168_COMMON_V2_SHA256 = 'bbc998ed811cd1678e4e1544b8eed0e0183a45f43bd14711165c358604d65283'
V2_REASONS_AFTER_D168 = ['ROUND_LIMIT', 'TIME_BUDGET', 'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT', 'INVALID_RESPONSE',
                         'ILLEGAL_CANDIDATE', 'EXPLANATION_INVALID', 'MODE_NOT_AUTHORIZED',
                         'CALL_BUDGET_EXHAUSTED', 'REPLAY_MISS']
D = SCHEMA['$defs']


# ------------------------------------------------------------------ fixtures

def scores(lo=.5, mid=.7, hi=.9, n=5):
    return {'n': n, 'min': lo, 'median': mid, 'max': hi}


def view(id_, camera='CAM_A', first=0, last=1_000_000, colors=('red',)):
    return {'id': id_, 'camera_id': camera, 'first_seen_us': first, 'last_seen_us': last,
            'colors': list(colors), 'scores': scores(), 'continuation_fraction': .1}


def cand(id_, camera='CAM_B', eligible=True, gap=400_000):
    return dict(view(id_, camera, 1_600_000, 1_800_000), gap_us=gap, graph_edge=True,
                link_kind='CROSS_CAMERA_HANDOFF', rule_eligible=eligible)


def dp1(*candidates, rule_answer=None):
    candidates = list(candidates) or [cand('B1')]
    req = {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP1, 'as_of_us': 2_000_000,
           'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B']]},
           'current': view('A1'), 'candidates': candidates, 'rule_answer': 'ABSTAIN',
           'identity_verdict': 'UNCONFIRMED'}
    req['rule_answer'] = rule_answer or RuleDecider().answer(req)
    return req


def dp3():
    return {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP3, 'as_of_us': 2_000_000,
            'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': []},
            'current': view('A1'), 'rule_answer': 'ACCEPT_SEGMENT', 'identity_verdict': 'UNCONFIRMED',
            'segment': {'start_us': 400_000, 'end_us': 800_000, 'n_frames': 3, 'box_scores': scores(.3, .35, .4)}}


def select(id_='B1'):
    return {'action': 'SELECT', 'candidate_id': id_, 'reason_codes': ['GRAPH_EDGE', 'SHORT_GAP'],
            'rationale': 'single edge-connected candidate with a short gap'}


ABSTAIN_RESP = {'action': 'ABSTAIN', 'reason_codes': ['INSUFFICIENT_EVIDENCE'], 'rationale': ''}
REJECT_RESP = {'action': 'REJECT_SEGMENT', 'reason_codes': ['LOW_SCORE'], 'rationale': 'low box scores'}


class Script:
    """Scripted fake provider: returns the queued Attempts in order and logs the call args."""

    def __init__(self, *attempts):
        self.queue = list(attempts)
        self.calls = []

    def __call__(self, request, *, timeout_ms, max_output_tokens):
        self.calls.append({'timeout_ms': timeout_ms, 'max_output_tokens': max_output_tokens})
        return self.queue.pop(0)


def ok(response, wall=300.0, p=1000, c=60):
    return Attempt('OK', wall, response, p, c)


def timeout(wall=2000.0):
    return Attempt('TIMEOUT', wall)


def run(request, script, *, params=FORMAL, mode='AGENT_LIVE', budget=None, model='astra6', stage=STAGE):
    budget = budget or CallBudget(params, stage)
    record = ad.decide(request, mode=mode, params=params, budget=budget, model=model, call=script,
                       provider_kind='OPENAI')
    ad.validate_record(record)
    assert record['identity_verdict'] == 'UNCONFIRMED'
    return record


# ------------------------------------------------------------------ 1. contract

def test_schema_is_v1_not_draft_and_names_pending_enums():
    assert SCHEMA['$id'] == 'q-core.agent-decision.v1' and SCHEMA['status'] == 'V1'
    assert 'DRAFT' not in SCHEMA['title'] and 'DRAFT' not in SCHEMA['description']
    assert not (ROOT / 'docs/contracts/schemas/q-core.agent-decision.v1.draft.schema.json').exists()
    assert SCHEMA['added_to_common_v2']['fallback_reason'] == list(ad.FALLBACK_REASONS_NEW)


def test_schema_and_validator_constants_agree():
    """The repo has no jsonschema dependency; pin every closed value the validator relies on."""
    assert D['mode']['enum'] == list(ad.MODES) and D['mode']['default'] == ad.DEFAULT_MODE == 'OFF'
    assert D['decision_point']['enum'] == list(ad.DECISION_POINTS)
    assert D['color']['enum'] == list(ad.COLORS)
    assert D['identity_verdict'] == {'const': 'UNCONFIRMED'}
    for name, regex in (('opaque_id', ad.OPAQUE_ID), ('camera_id', ad.CAMERA_ID), ('answer', ad.ANSWER),
                        ('sha256', ad.SHA256)):
        assert D[name]['pattern'].lstrip('^').rstrip('$') == regex.pattern.removesuffix(r'\Z')
    req = D['request']
    assert set(req['required']) == ad.REQUEST_REQUIRED and set(req['properties']) == ad.REQUEST_KEYS
    assert req['properties']['schema_version']['const'] == ad.REQUEST_SCHEMA_VERSION
    assert req['properties']['candidates']['maxItems'] == ad.MAX_CANDIDATES
    assert req['properties']['topology']['properties']['edges']['maxItems'] == ad.MAX_EDGES
    assert set(D['track_view']['required']) == ad.TRACK_KEYS
    assert set(D['track_view']['required']) | set(D['handoff_candidate']['required']) == ad.CANDIDATE_KEYS
    assert D['handoff_candidate']['properties']['link_kind']['enum'] == list(ad.LINK_KINDS)
    resp = D['response']
    assert set(resp['required']) == ad.RESPONSE_REQUIRED and set(resp['properties']) == ad.RESPONSE_KEYS
    assert resp['properties']['rationale']['maxLength'] == ad.RATIONALE_MAX
    assert resp['properties']['reason_codes']['items']['enum'] == list(ad.REASON_CODES)
    assert resp['properties']['reason_codes']['maxItems'] == ad.MAX_REASON_CODES
    assert set(resp['properties']['action']['enum']) == {a for v in ad.ACTIONS.values() for a in v}
    rec = D['record']
    assert set(rec['required']) == set(rec['properties']) == ad.RECORD_KEYS
    assert rec['properties']['schema_version']['const'] == ad.RECORD_SCHEMA_VERSION
    assert rec['properties']['decision_source']['enum'] == list(ad.DECISION_SOURCES)
    assert rec['properties']['fallback_reason']['enum'] == list(ad.FALLBACK_REASONS) + [None]
    assert rec['properties']['budget_layer']['enum'] == list(ad.BUDGET_LAYERS) + [None]
    assert set(rec['properties']['provider']['properties']) == ad.PROVIDER_KEYS
    assert rec['properties']['provider']['properties']['kind']['enum'] == list(ad.PROVIDER_KINDS)
    att = rec['properties']['attempts']
    assert att['maxItems'] == 3 and set(att['items']['properties']) == ad.ATTEMPT_KEYS
    assert att['items']['properties']['outcome']['enum'] == list(ad.ATTEMPT_OUTCOMES)
    common = json.loads(COMMON_V2.read_text())
    assert common['$defs']['fallback_reason']['anyOf'][0]['enum'] == V2_REASONS_AFTER_D168
    assert set(ad.FALLBACK_REASONS) <= set(V2_REASONS_AFTER_D168)


def test_common_v2_change_is_additive_and_old_data_stays_valid():
    """D168: removing exactly the two new enum lines restores the pre-D168 bytes (old pin).

    So every other definition is byte-identical, the old enum is a prefix of the new one,
    and any document valid under the old common.v2 is still valid."""
    raw = COMMON_V2.read_bytes().decode()
    new_lines = '            "MODE_NOT_AUTHORIZED",\n            "CALL_BUDGET_EXHAUSTED",\n            "REPLAY_MISS"\n'
    assert raw.count(new_lines) == 1
    old = raw.replace(new_lines, '            "MODE_NOT_AUTHORIZED"\n')
    assert hashlib.sha256(old.encode()).hexdigest() == PRE_D168_COMMON_V2_SHA256
    old_enum = json.loads(old)['$defs']['fallback_reason']['anyOf'][0]['enum']
    assert V2_REASONS_AFTER_D168[:len(old_enum)] == old_enum
    from amidst.evaluation.response_versions import V2_SCHEMA_PINS, v2_schema_documents
    assert V2_SCHEMA_PINS['common.v2.schema.json'] == hashlib.sha256(raw.encode()).hexdigest()
    docs = v2_schema_documents()  # every pinned v2 response schema still loads against the new bytes
    assert docs['common.v2.schema.json']['$defs']['fallback_reason']['anyOf'][1] == {'type': 'null'}


def test_params_schema_and_validator_agree():
    assert set(PARAMS_SCHEMA['required']) == set(PARAMS_SCHEMA['properties']) - {'note'}
    assert PARAMS_SCHEMA['properties']['schema_version']['const'] == ad.PARAMS_SCHEMA_VERSION
    assert PARAMS_SCHEMA['properties']['mode']['const'] == 'OFF'
    assert PARAMS_SCHEMA['$defs']['model']['properties']['config_id']['enum'] == list(ad.MODELS)
    assert set(FORMAL) <= set(PARAMS_SCHEMA['properties'])
    for params in (FORMAL, EXPLORATORY):
        ad.validate_params(params)
    bad = copy.deepcopy(FORMAL)
    bad['extra'] = 1
    with pytest.raises(AgentDecisionError, match='PARAMS_INVALID'):
        ad.validate_params(bad)


def test_committed_parameter_sets_match_d165_d166():
    assert [m['config_id'] for m in FORMAL['models']] == ['astra6', 'sol6.1', 'terra6.1']
    assert all(m['api_model_id'] is None for m in FORMAL['models'])
    assert FORMAL['report_group'] == 'FORMAL' and EXPLORATORY['report_group'] == 'EXPLORATORY'
    assert FORMAL['per_call'] == {'timeout_ms': 2000, 'max_output_tokens': 300, 'max_retries_on_429_5xx': 1}
    assert FORMAL['per_step'] == {'budget_ms': 5000, 'max_rounds': 3}
    assert FORMAL['per_session'] == {'max_rounds': 12}
    assert FORMAL['rate'] == {'max_concurrent': 1, 'max_requests_per_minute': 30}
    assert FORMAL['budget_usd'] == 100 and FORMAL['price_table'] is None
    assert EXPLORATORY['per_call']['timeout_ms'] == 10_000
    assert FORMAL['stages'][STAGE]['approved'] is True and FORMAL['stages'][STAGE]['max_calls'] == 288
    assert FORMAL['stages']['FORMAL']['approved'] is False
    assert all(not s['approved'] for s in EXPLORATORY['stages'].values())
    assert ad.parameter_set_sha256(FORMAL) != ad.parameter_set_sha256(EXPLORATORY)


def test_approved_stage_needs_every_cap():
    bad = copy.deepcopy(FORMAL)
    bad['stages']['FORMAL']['approved'] = True
    bad['stages']['FORMAL']['approval_ref'] = 'x'
    with pytest.raises(AgentDecisionError, match='approved stage'):
        ad.validate_params(bad)


# ------------------------------------------------------------------ 2. request vectors

def test_positive_request_vectors():
    ad.validate_request(dp1())
    ad.validate_request(dp1(cand('B1'), cand('C2', 'CAM_C')))
    ad.validate_request(dp1(cand('B1'), cand('C2', 'CAM_C', eligible=False)))
    ad.validate_request(dp3())


def _mut(fn, base=dp1):
    req = base()
    fn(req)
    return req


NEG_REQUESTS = {
    'gt_key': (lambda r: r.update(gt={}), 'FORBIDDEN_INFERENCE_INPUT'),
    'gt_prefixed_nested': (lambda r: r['current'].update(gt_actor=1), 'FORBIDDEN_INFERENCE_INPUT'),
    'gt_private': (lambda r: r['topology'].update({'gt_private': 'x'}), 'FORBIDDEN_INFERENCE_INPUT'),
    'ground_truth': (lambda r: r.update({'ground_truth': 1}), 'FORBIDDEN_INFERENCE_INPUT'),
    'actor_id_in_candidate': (lambda r: r['candidates'][0].update(actor_id='p1'), 'FORBIDDEN_INFERENCE_INPUT'),
    'visibility': (lambda r: r['current'].update({'visib' 'ility': 1}), 'FORBIDDEN_INFERENCE_INPUT'),
    'depth': (lambda r: r.update({'dep' 'th': 1}), 'FORBIDDEN_INFERENCE_INPUT'),
    'trajectory': (lambda r: r.update({'traject' 'ory': []}), 'FORBIDDEN_INFERENCE_INPUT'),
    'raw_track_ref': (lambda r: r['candidates'][0].update(track_ref='synthetic:B'), 'FORBIDDEN_INFERENCE_INPUT'),
    'file_path': (lambda r: r.update(file_path='/x'), 'FORBIDDEN_INFERENCE_INPUT'),
    'identity_field': (lambda r: r.update(identity='same'), 'FORBIDDEN_INFERENCE_INPUT'),
    'identity_confirmed': (lambda r: r.update(identity_verdict='CONFIRMED'), 'REQUEST_INVALID'),
    'extra_key': (lambda r: r.update(note='hi'), 'REQUEST_INVALID'),
    'extra_key_in_current': (lambda r: r['current'].update(gap_us=0), 'REQUEST_INVALID'),
    'missing_key': (lambda r: r.pop('topology'), 'REQUEST_INVALID'),
    'schema_version': (lambda r: r.update(schema_version='q-core.agent-decision-request.v0'), 'REQUEST_INVALID'),
    'rule_answer_not_in_list': (lambda r: r.update(rule_answer='Z9'), 'REQUEST_INVALID'),
    'duplicate_candidate_ids': (lambda r: r.update(candidates=[cand('B1'), cand('B1', 'CAM_C')]), 'REQUEST_INVALID'),
    'current_id_reused': (lambda r: r['candidates'][0].update(id='A1'), 'REQUEST_INVALID'),
    'non_opaque_id': (lambda r: r['candidates'][0].update(id='track_7'), 'REQUEST_INVALID'),
    'bad_camera_id': (lambda r: r['current'].update(camera_id='cam-a'), 'REQUEST_INVALID'),
    'future_observation': (lambda r: r['candidates'][0].update(last_seen_us=2_000_000), 'REQUEST_INVALID'),
    'score_order': (lambda r: r['current'].update(scores=scores(.9, .5, .7)), 'REQUEST_INVALID'),
    'bool_as_int': (lambda r: r.update(as_of_us=True), 'REQUEST_INVALID'),
    'unknown_color': (lambda r: r['current'].update(colors=['pink']), 'REQUEST_INVALID'),
    'too_many_candidates': (lambda r: r.update(candidates=[cand(f'B{i}') for i in range(9)], rule_answer='ABSTAIN'), 'REQUEST_INVALID'),
    'dp1_with_segment': (lambda r: r.update(segment=dp3()['segment']), 'REQUEST_INVALID'),
    'graph_edge_not_bool': (lambda r: r['candidates'][0].update(graph_edge=1), 'REQUEST_INVALID'),
}


@pytest.mark.parametrize('name', sorted(NEG_REQUESTS))
def test_negative_request_vectors(name):
    fn, code = NEG_REQUESTS[name]
    with pytest.raises(AgentDecisionError) as err:
        ad.validate_request(_mut(fn))
    assert err.value.code == code


@pytest.mark.parametrize('fn', [
    lambda r: r.update(candidates=[cand('B1')]),
    lambda r: r.update(rule_answer='ABSTAIN'),
    lambda r: r['segment'].update(end_us=2_000_001),
    lambda r: r.pop('segment'),
])
def test_negative_dp3_request_vectors(fn):
    with pytest.raises(AgentDecisionError, match='REQUEST_INVALID'):
        ad.validate_request(_mut(fn, dp3))


# ------------------------------------------------------------------ 3. response vectors

def test_positive_response_vectors():
    two = dp1(cand('B1'), cand('C2', 'CAM_C'))
    assert ad.validate_response(select('C2'), two) == 'C2'
    assert ad.validate_response(ABSTAIN_RESP, two) == 'ABSTAIN'
    assert ad.validate_response(REJECT_RESP, dp3()) == 'REJECT_SEGMENT'
    assert ad.validate_response(dict(REJECT_RESP, action='ACCEPT_SEGMENT'), dp3()) == 'ACCEPT_SEGMENT'
    assert ad.validate_response(dict(select(), rationale='x' * 240), dp1()) == 'B1'


NEG_RESPONSES = {
    'id_not_in_list': (dp1, select('Z9'), 'ILLEGAL_CANDIDATE'),
    'rule_ineligible_id': (lambda: dp1(cand('B1'), cand('C2', 'CAM_C', eligible=False)), select('C2'), 'ILLEGAL_CANDIDATE'),
    'rationale_too_long': (dp1, dict(select(), rationale='x' * 241), 'INVALID_RESPONSE'),
    'extra_key': (dp1, dict(select(), confidence=.9), 'INVALID_RESPONSE'),
    'identity_field': (dp1, dict(select(), identity='SAME_PERSON'), 'INVALID_RESPONSE'),
    'identity_verdict_field': (dp1, dict(select(), identity_verdict='CONFIRMED'), 'INVALID_RESPONSE'),
    'actor_id': (dp1, dict(select(), actor_id='p1'), 'INVALID_RESPONSE'),
    'gt_key': (dp1, dict(select(), gt_match=True), 'INVALID_RESPONSE'),
    'unknown_reason_code': (dp1, dict(select(), reason_codes=['VIBES']), 'INVALID_RESPONSE'),
    'no_reason_code': (dp1, dict(select(), reason_codes=[]), 'INVALID_RESPONSE'),
    'five_reason_codes': (dp1, dict(select(), reason_codes=list(ad.REASON_CODES[:5])), 'INVALID_RESPONSE'),
    'duplicate_reason_code': (dp1, dict(select(), reason_codes=['GRAPH_EDGE', 'GRAPH_EDGE']), 'INVALID_RESPONSE'),
    'select_without_id': (dp1, {k: v for k, v in select().items() if k != 'candidate_id'}, 'INVALID_RESPONSE'),
    'abstain_with_id': (dp1, dict(ABSTAIN_RESP, candidate_id='B1'), 'INVALID_RESPONSE'),
    'dp1_segment_action': (dp1, REJECT_RESP, 'INVALID_RESPONSE'),
    'dp3_select': (dp3, select(), 'INVALID_RESPONSE'),
    'dp3_abstain': (dp3, ABSTAIN_RESP, 'INVALID_RESPONSE'),
    'not_an_object': (dp1, 'B1', 'INVALID_RESPONSE'),
    'rationale_not_string': (dp1, dict(select(), rationale=3), 'INVALID_RESPONSE'),
}


@pytest.mark.parametrize('name', sorted(NEG_RESPONSES))
def test_negative_response_vectors(name):
    make, response, code = NEG_RESPONSES[name]
    with pytest.raises(AgentDecisionError) as err:
        ad.validate_response(response, make())
    assert err.value.code == code


# ------------------------------------------------------------------ 4. rule decider

def test_rule_decider_matches_associate_rule():
    def track(camera, times, color='red'):
        return Track(camera, 'synthetic:' + camera, tuple(
            Observation(camera, t, f'{camera}:{t}', .7, frozenset([color])) for t in times))
    edges = {('A', 'B'): 'AB', ('A', 'C'): 'AC'}
    p = Parameters()
    _, single_events, single_audit = associate([track('A', [0, 200_000]), track('B', [800_000])], edges,
                                               as_of_us=1_600_000, parameters=p)
    _, amb_events, amb_audit = associate([track('A', [0, 200_000]), track('B', [800_000]), track('C', [800_000])],
                                         edges, as_of_us=1_600_000, parameters=p)
    _, col_events, col_audit = associate([track('A', [0, 200_000]), track('B', [800_000], 'blue')], edges,
                                         as_of_us=1_600_000, parameters=p)

    def request_from(audit):
        rows = [r for r in audit if 'to_track_ref' in r and r.get('gap_us') is not None]
        cands = [dict(cand(f'B{i + 1}', eligible=r['reason'] in ('DEMO_ASSOCIATION_HYPOTHESIS', 'AMBIGUOUS_HANDOFF')),
                      gap_us=r['gap_us']) for i, r in enumerate(rows)]
        return dp1(*cands)
    assert len(single_events) == 1 and RuleDecider().answer(request_from(single_audit)) == 'B1'
    assert not amb_events and RuleDecider().answer(request_from(amb_audit)) == 'ABSTAIN'
    assert not col_events and RuleDecider().answer(request_from(col_audit)) == 'ABSTAIN'
    assert RuleDecider().answer(dp3()) == 'ACCEPT_SEGMENT'


# ------------------------------------------------------------------ 5. §2.3 table, one test per row

def test_row_mode_off_is_rule_only_and_default():
    script = Script()
    record = ad.decide(dp1(), params=FORMAL, call=script, budget=CallBudget(FORMAL, STAGE), model='astra6',
                       provider_kind='OPENAI')
    ad.validate_record(record)
    assert record['mode'] == 'OFF' and record['decision_source'] == 'RULE_ONLY'
    assert record['fallback_reason'] is None and record['final_answer'] == 'B1' and not script.calls


def test_row_rule_only_mode():
    record = run(dp1(), Script(), mode='RULE_ONLY')
    assert record['decision_source'] == 'RULE_ONLY' and record['attempts'] == []


@pytest.mark.parametrize('kwargs', [
    {'model': 'gpt-x'},                       # model not configured
    {'call': None},                           # no provider
    {'provider_kind': 'NONE'},
    {'budget': None},
])
def test_row_mode_not_authorized(kwargs):
    base = dict(mode='AGENT_LIVE', params=FORMAL, budget=CallBudget(FORMAL, STAGE), model='astra6',
                call=Script(ok(select())), provider_kind='OPENAI')
    base.update(kwargs)
    if base['model'] not in ad.MODELS:
        base['budget'] = CallBudget(FORMAL, STAGE)
    record = ad.decide(dp1(), **base)
    ad.validate_record(record)
    assert record['decision_source'] == 'RULE_FALLBACK' and record['fallback_reason'] == 'MODE_NOT_AUTHORIZED'
    assert record['final_answer'] == record['rule_answer'] and record['attempts'] == []


def test_row_mode_not_authorized_when_stage_locked():
    script = Script(ok(select()))
    record = run(dp1(), script, stage='FORMAL')
    assert record['fallback_reason'] == 'MODE_NOT_AUTHORIZED' and not script.calls


def test_row_single_call_timeout_is_retried_and_recorded():
    two = dp1(cand('B1'), cand('C2', 'CAM_C'))
    record = run(two, Script(timeout(), ok(select('C2'))))
    assert record['decision_source'] == 'AGENT' and record['final_answer'] == 'C2' and record['rule_answer'] == 'ABSTAIN'
    assert [a['outcome'] for a in record['attempts']] == ['PROVIDER_TIMEOUT', 'OK']
    assert record['fallback_reason'] is None


def test_row_round_limit():
    script = Script(timeout(), Attempt('RETRYABLE', 100.0), timeout())
    record = run(dp1(), script)
    assert record['fallback_reason'] == 'ROUND_LIMIT' and len(record['attempts']) == 3
    assert record['final_answer'] == 'B1'


def test_row_time_budget():
    script = Script(timeout(), timeout(), timeout(1000.0))
    record = run(dp1(), script)
    assert [c['timeout_ms'] for c in script.calls] == [2000, 2000, 1000]
    assert record['fallback_reason'] == 'TIME_BUDGET'


def test_row_call_budget_exhausted_session():
    budget = CallBudget(FORMAL, STAGE)
    budget.begin_session()
    for _ in range(12):
        assert run(dp1(), Script(ok(select())), budget=budget)['decision_source'] == 'AGENT'
    record = run(dp1(), Script(ok(select())), budget=budget)
    assert record['fallback_reason'] == 'CALL_BUDGET_EXHAUSTED' and record['budget_layer'] == 'SESSION_ROUNDS'


def test_row_provider_unavailable():
    record = run(dp1(), Script(Attempt('UNAVAILABLE', 5.0)))
    assert record['fallback_reason'] == 'PROVIDER_UNAVAILABLE'
    assert [a['outcome'] for a in record['attempts']] == ['PROVIDER_UNAVAILABLE']


def test_row_replay_miss():
    record = run(dp1(), Script(Attempt('REPLAY_MISS', 0.0)), mode='AGENT_REPLAY')
    assert record['fallback_reason'] == 'REPLAY_MISS' and record['mode'] == 'AGENT_REPLAY'


def test_row_invalid_response():
    record = run(dp1(), Script(ok(dict(select(), identity='SAME'))))
    assert record['fallback_reason'] == 'INVALID_RESPONSE' and record['attempts'][-1]['outcome'] == 'INVALID_RESPONSE'


def _deep(n):
    node = 'x'
    for _ in range(n):
        node = [node]
    return node


@pytest.mark.parametrize('name,payload', [
    ('nan', lambda: dict(select(), rationale=float('nan'))),
    ('infinity', lambda: dict(select(), rationale=float('inf'))),
    ('neg_infinity', lambda: dict(select(), rationale=float('-inf'))),
    ('set', lambda: dict(select(), reason_codes={'A'})),
    ('unserializable_object', lambda: dict(select(), rationale=object())),
    ('bytes', lambda: dict(select(), rationale=b'x')),
    ('non_string_key', lambda: {1: 'x'}),
    ('nesting_33', lambda: {'x': _deep(32)}),
    ('nesting_5000', lambda: {'x': _deep(5000)}),
])
def test_row_hostile_response_falls_back_instead_of_raising(name, payload):
    record = run(dp1(), Script(ok(payload())))
    assert record['decision_source'] == 'RULE_FALLBACK' and record['fallback_reason'] == 'INVALID_RESPONSE'
    assert record['attempts'][-1]['outcome'] == 'INVALID_RESPONSE'
    assert record['attempts'][-1]['response_sha256'] is None


def test_response_nesting_limit_boundary():
    ad.check_json_safe({'x': _deep(ad.MAX_RESPONSE_NESTING - 2)})
    with pytest.raises(AgentDecisionError, match='nesting'):
        ad.check_json_safe({'x': _deep(ad.MAX_RESPONSE_NESTING - 1)})


@pytest.mark.parametrize('path,value', [
    (('per_call', 'timeout_ms'), 60_001), (('per_call', 'max_output_tokens'), 4097),
    (('per_step', 'budget_ms'), 60_001), (('per_session', 'max_rounds'), 101),
    (('prompt_tokens_per_call_estimate',), 200_001),
])
def test_params_upper_bounds(path, value):
    bad = copy.deepcopy(FORMAL)
    node = bad
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(AgentDecisionError, match='above maximum'):
        ad.validate_params(bad)
    spec = PARAMS_SCHEMA['properties']
    for key in path:  # the schema carries the same maximum as the validator
        spec = spec[key] if key in spec else spec['properties'][key]
    assert spec['maximum'] == value - 1


def test_row_illegal_candidate():
    record = run(dp1(), Script(ok(select('Z9'))))
    assert record['fallback_reason'] == 'ILLEGAL_CANDIDATE' and record['final_answer'] == 'B1'


def test_dp3_agent_reject_and_identity_constant():
    record = run(dp3(), Script(ok(REJECT_RESP)))
    assert record['decision_source'] == 'AGENT' and record['final_answer'] == 'REJECT_SEGMENT'
    assert record['rule_answer'] == 'ACCEPT_SEGMENT' and record['identity_verdict'] == 'UNCONFIRMED'


# ------------------------------------------------------------------ 6. layered caps

def test_per_call_limits_are_passed_to_provider():
    script = Script(ok(select()))
    run(dp1(), script)
    assert script.calls == [{'timeout_ms': 2000, 'max_output_tokens': 300}]
    explo = copy.deepcopy(EXPLORATORY)
    explo['stages']['EXPLORATORY'].update(approved=True, approval_ref='test', max_calls=10, max_tokens=10**6,
                                          per_model_max_calls=10, per_model_max_tokens=10**6)
    script = Script(ok(select()))
    run(dp1(), script, params=explo, stage='EXPLORATORY')
    assert script.calls == [{'timeout_ms': 10_000, 'max_output_tokens': 300}]


def test_late_ok_response_is_discarded_as_timeout():
    record = run(dp1(), Script(ok(select(), wall=2500.0), ok(ABSTAIN_RESP)))
    assert [a['outcome'] for a in record['attempts']] == ['PROVIDER_TIMEOUT', 'OK']
    assert record['final_answer'] == 'ABSTAIN'


def test_one_retry_on_429_5xx_counts_toward_caps():
    budget = CallBudget(FORMAL, STAGE)
    record = run(dp1(), Script(Attempt('RETRYABLE', 50.0), ok(select())), budget=budget)
    assert record['decision_source'] == 'AGENT' and budget.stage_calls == 2 and budget.model_calls['astra6'] == 2
    record = run(dp1(), Script(Attempt('RETRYABLE', 50.0), Attempt('RETRYABLE', 50.0)))
    assert record['fallback_reason'] == 'PROVIDER_UNAVAILABLE' and len(record['attempts']) == 2


def _small(**caps):
    params = copy.deepcopy(FORMAL)
    params['stages'][STAGE].update(caps)
    return params


def test_model_call_cap_is_sticky_per_model():
    params = _small(per_model_max_calls=2)
    budget = CallBudget(params, STAGE)
    for _ in range(2):
        assert run(dp1(), Script(ok(select())), params=params, budget=budget)['decision_source'] == 'AGENT'
    for _ in range(2):
        rec = run(dp1(), Script(ok(select())), params=params, budget=budget)
        assert rec['fallback_reason'] == 'CALL_BUDGET_EXHAUSTED' and rec['budget_layer'] == 'MODEL_CALLS'
    assert run(dp1(), Script(ok(select())), params=params, budget=budget, model='sol6.1')['decision_source'] == 'AGENT'


def test_model_token_cap_charges_estimate_when_usage_missing():
    params = _small(per_model_max_tokens=3600)
    budget = CallBudget(params, STAGE)
    run(dp1(), Script(Attempt('OK', 100.0, select())), params=params, budget=budget)  # no usage -> 1800
    assert budget.model_tokens['astra6'] == 1800
    run(dp1(), Script(ok(select(), p=1700, c=100)), params=params, budget=budget)
    rec = run(dp1(), Script(ok(select())), params=params, budget=budget)
    assert rec['budget_layer'] == 'MODEL_TOKENS'


def test_stage_call_and_token_caps_stop_every_model():
    params = _small(max_calls=1)
    budget = CallBudget(params, STAGE)
    run(dp1(), Script(ok(select())), params=params, budget=budget)
    for model in ad.MODELS:
        assert run(dp1(), Script(ok(select())), params=params, budget=budget, model=model)['budget_layer'] == 'STAGE_CALLS'
    params = _small(max_tokens=2000)
    budget = CallBudget(params, STAGE)
    run(dp1(), Script(ok(select())), params=params, budget=budget)
    assert run(dp1(), Script(ok(select())), params=params, budget=budget, model='terra6.1')['budget_layer'] == 'STAGE_TOKENS'


def test_total_usd_only_enforced_with_dated_price_table():
    params = copy.deepcopy(FORMAL)
    params['budget_usd'] = 0.002
    budget = CallBudget(params, STAGE)
    for _ in range(3):
        assert run(dp1(), Script(ok(select())), params=params, budget=budget)['decision_source'] == 'AGENT'
    assert budget.spent_usd == 0.0 and not budget.usd_enforced
    params['price_table'] = {'date': '2026-11-09', 'source': 'TEST_FIXTURE_NOT_A_REAL_PRICE', 'currency': 'USD',
                             'models': {m: {'input_usd_per_mtok': 1.0, 'output_usd_per_mtok': 1.0} for m in ad.MODELS}}
    budget = CallBudget(params, STAGE)
    assert run(dp1(), Script(ok(select(), p=1000, c=0)), params=params, budget=budget)['decision_source'] == 'AGENT'
    rec = run(dp1(), Script(ok(select())), params=params, budget=budget)
    assert rec['budget_layer'] == 'TOTAL_USD'
    bad = copy.deepcopy(params)
    del bad['price_table']['source']
    with pytest.raises(AgentDecisionError, match='PARAMS_INVALID'):
        CallBudget(bad, STAGE)


def test_replay_never_charges_live_caps_but_keeps_session_cap():
    params = _small(max_calls=1)
    budget = CallBudget(params, STAGE)
    for _ in range(5):
        assert run(dp1(), Script(ok(select())), params=params, budget=budget, mode='AGENT_REPLAY')['decision_source'] == 'AGENT'
    assert budget.stage_calls == 0 and budget.session_rounds == 5


def test_rate_one_in_flight_and_thirty_per_minute():
    budget = CallBudget(FORMAL, STAGE)
    for i in range(30):
        assert budget.rate_wait_ms(i * 100) == 0
        budget.note_start(i * 100)
        budget.note_end()
    assert budget.rate_wait_ms(3000) == 57_000
    with pytest.raises(AgentDecisionError, match='RATE_INVALID'):
        budget.note_start(3000)
    assert budget.rate_wait_ms(60_000) == 0
    budget.note_start(60_000)
    with pytest.raises(AgentDecisionError, match='RATE_INVALID'):
        budget.note_start(60_100)  # still in flight


def test_replay_is_deterministic():
    shas = set()
    for _ in range(3):
        record = run(dp1(cand('B1'), cand('C2', 'CAM_C')), Script(timeout(), ok(select('C2'))), mode='AGENT_REPLAY')
        shas.add(ad.request_sha256(record))  # canonical hash of the whole record
    assert len(shas) == 1


def test_request_hash_ignores_candidate_order():
    a = dp1(cand('B1'), cand('C2', 'CAM_C'))
    b = dp1(cand('C2', 'CAM_C'), cand('B1'))
    assert ad.request_sha256(a) == ad.request_sha256(b)


# ------------------------------------------------------------------ 7. dry run

def test_dry_run_matches_hand_calculation():
    pilot = ad.dry_run_estimate(FORMAL, questions=16, k=1, stage=STAGE)
    consistency = ad.dry_run_estimate(FORMAL, questions=16, k=5, stage=STAGE)
    assert pilot['calls'] == 16 * 1 * 3 == 48 and pilot['calls_per_model'] == 16
    assert consistency['calls'] == 16 * 5 * 3 == 240 and consistency['calls_per_model'] == 80
    assert pilot['calls'] + consistency['calls'] == FORMAL['stages'][STAGE]['max_calls'] == 288
    assert pilot['tokens_per_call'] == 1500 + 300 and pilot['tokens'] == 48 * 1800
    assert pilot['fits_stage'] and consistency['fits_stage'] and pilot['usd'] is None
    both = ad.dry_run_estimate(FORMAL, questions=16, k=6, stage=STAGE)  # pilot + consistency together
    assert both['calls'] == 288 and both['fits_stage']
    worst = ad.dry_run_estimate(FORMAL, questions=16, k=1, rounds=3, stage=STAGE)
    assert worst['calls'] == 144
    assert not ad.dry_run_estimate(FORMAL, questions=17, k=6, stage=STAGE)['fits_stage']
    assert ad.dry_run_estimate(FORMAL, questions=16, k=1, stage='FORMAL')['fits_stage'] is False
    with pytest.raises(AgentDecisionError):
        ad.dry_run_estimate(FORMAL, questions=16, k=1, rounds=4)


# ------------------------------------------------------------------ 8. default OFF, no side effects

def test_existing_path_does_not_import_agent_decision():
    pattern = re.compile(r'agent_decision\b')
    offenders = []
    for root in ('src', 'scripts'):
        for path in (ROOT / root).rglob('*.py'):
            if path in (MODULE, MODULE.with_name('agent_wiring.py')):  # WP2's opt-in wiring is the one importer
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                         [node.module or ''] + [a.name for a in node.names] if isinstance(node, ast.ImportFrom) else [])
                if any(pattern.search(n) for n in names):
                    offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_import_has_no_side_effects_on_associate():
    code = (
        'import sys, json\n'
        'from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, response\n'
        'def t(c, ts): return Track(c, "s:"+c, tuple(Observation(c, x, f"{c}:{x}", .7, frozenset(["red"])) for x in ts))\n'
        'args = ([t("A",[0,200000]), t("B",[800000]), t("C",[800000,1000000])], {("A","B"):"AB"})\n'
        'kw = dict(as_of_us=1600000, parameters=Parameters(), clock_mapping_sha256="a"*64)\n'
        'before = json.dumps(response(*args, **kw), sort_keys=True, default=str)\n'
        'mods = set(sys.modules)\n'
        'import amidst.q1q5.agent_decision as ad\n'
        'after = json.dumps(response(*args, **kw), sort_keys=True, default=str)\n'
        'new = sorted(set(sys.modules) - mods)\n'
        'print(json.dumps({"same": before == after, "new": new, "default": ad.DEFAULT_MODE}))\n'
    )
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True,
                         cwd=ROOT, env={'PYTHONPATH': str(ROOT / 'src'), 'PATH': ''})
    result = json.loads(out.stdout)
    assert result['same'] and result['default'] == 'OFF'
    banned = ('socket', 'ssl', 'http', 'urllib', 'requests', 'httpx', 'openai', 'subprocess', 'asyncio')
    assert not [m for m in result['new'] if m.split('.')[0] in banned]


# ------------------------------------------------------------------ 9. GT isolation (static)

def test_module_reads_no_gt_files_or_environment():
    source = MODULE.read_text(encoding='utf-8')
    tree = ast.parse(source)
    allowed = {'__future__', 'collections', 'collections.abc', 'dataclasses', 'hashlib', 'json', 're'}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports <= allowed, imports - allowed
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not calls & {'open', 'exec', 'eval', '__import__', 'input'}
    assert not attrs & {'read_text', 'read_bytes', 'environ', 'getenv', 'urlopen', 'connect', 'system', 'popen'}
    rules = json.loads((ROOT / 'configs/architecture/inference_import_rules_v1.json').read_text())
    guard = re.compile(rules['forbidden_string_pattern'])
    hits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and guard.search(n.value)]
    assert hits == []
    assert 'OPENAI_API_KEY' not in source

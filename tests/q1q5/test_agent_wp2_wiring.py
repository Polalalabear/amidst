"""Agent decision WP2: associate() wiring. Default OFF is byte-identical to ddce2aa (golden hash);
agent ON uses only WP1's decide()/fallback with fake providers (no network, no API key)."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

from amidst.q1q5 import agent_decision as ad
from amidst.q1q5 import agent_wiring, cross_camera_demo
from amidst.q1q5.agent_decision import Attempt, CallBudget
from amidst.q1q5.agent_wiring import AgentDecider
from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, response

ROOT = Path(__file__).resolve().parents[2]
PARAMS = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1.json').read_text())
# sha256 of the canonical JSON of golden_payload() computed on mainline/q1q5 @ ddce2aa (before WP2): 36 runs,
# 94 audit rows, 14 events, covering every rule branch of associate().
GOLDEN_SHA256 = '598fa419e89f0e3136fa57e469273588d4339baee551574fc70fb171b32cdab7'

EDGES = {('CAM_A', 'CAM_B'): 'A_TO_B', ('CAM_B', 'CAM_C'): 'B_TO_C'}
STEP = 200_000


def trk(camera, ref, times, color='red', score=.7, cont=(), colors_by_time=None):
    obs = []
    for t in times:
        kind = 'BOX_CONTINUATION' if t in cont else 'PERSON_DETECTION'
        colors = frozenset() if kind == 'BOX_CONTINUATION' else frozenset(
            [colors_by_time.get(t, color)] if colors_by_time else ([color] if color else []))
        obs.append(Observation(camera, t, f'{ref}:{t}', score, colors, evidence_kind=kind))
    return Track(camera, ref, tuple(obs))


def scenarios():
    grid = lambda a, b: list(range(a, b, STEP))
    return {
        'single_handoff': [trk('CAM_A', 'a', grid(0, 1_000_000)), trk('CAM_B', 'b', grid(1_600_000, 3_000_000))],
        'ambiguous_two': [trk('CAM_A', 'a', grid(0, 600_000)), trk('CAM_B', 'b', grid(1_000_000, 2_000_000)),
                          trk('CAM_C', 'c', grid(1_000_000, 2_200_000))],
        'ambiguous_then_resolved': [trk('CAM_A', 'a', grid(0, 600_000)), trk('CAM_B', 'b', grid(1_000_000, 1_400_000)),
                                    trk('CAM_C', 'c', grid(1_000_000, 2_200_000))],
        'colour_mismatch': [trk('CAM_A', 'a', grid(0, 600_000)), trk('CAM_B', 'b', grid(1_000_000, 2_000_000), color='blue')],
        'continuations': [trk('CAM_A', 'a', grid(0, 2_000_000), cont=set(grid(600_000, 1_200_000))),
                          trk('CAM_B', 'b', grid(2_400_000, 4_000_000), cont=set(grid(3_000_000, 3_600_000)), score=.5)],
        'same_camera_reacq': [trk('CAM_A', 'a1', grid(0, 600_000)), trk('CAM_A', 'a2', grid(1_400_000, 2_400_000))],
        'late_no_edge': [trk('CAM_A', 'a', grid(0, 600_000)), trk('CAM_C', 'c', grid(9_000_000, 10_000_000))],
        'overlap_still_observed': [trk('CAM_A', 'a', grid(0, 2_000_000)), trk('CAM_B', 'b', grid(400_000, 2_400_000))],
        'first_seed_ambiguous': [trk('CAM_A', 'a', grid(0, 800_000)), trk('CAM_B', 'b', grid(0, 800_000))],
    }


def golden_payload(**extra):
    out = {}
    for name, tracks in scenarios().items():
        for as_of in (400_000, 1_600_000, 2_600_000, 5_000_000):
            result, events, audit = response(tracks, EDGES, as_of_us=as_of, parameters=Parameters(),
                                             clock_mapping_sha256='a' * 64, **extra)
            out[f'{name}@{as_of}'] = {'response': result, 'events': events, 'audit': audit}
    return out


def golden_sha256(**extra):
    blob = json.dumps(golden_payload(**extra), sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return hashlib.sha256(blob).hexdigest()




# ------------------------------------------------------------------ helpers

STAGE = 'FORMAL'


def ok(resp, wall=300.0):
    return Attempt('OK', wall, resp, 1000, 60)


def sel(id_):
    return {'action': 'SELECT', 'candidate_id': id_, 'reason_codes': ['GRAPH_EDGE'], 'rationale': 'edge'}


ABSTAIN = {'action': 'ABSTAIN', 'reason_codes': ['INSUFFICIENT_EVIDENCE'], 'rationale': ''}
REJECT = {'action': 'REJECT_SEGMENT', 'reason_codes': ['LOW_SCORE'], 'rationale': 'low'}
ACCEPT = {'action': 'ACCEPT_SEGMENT', 'reason_codes': ['HIGH_SCORE'], 'rationale': 'ok'}


class Fake:
    """Fake provider: `rule(request) -> response dict | Attempt`; logs every request it sees."""

    def __init__(self, rule):
        self.rule, self.requests = rule, []

    def __call__(self, request, *, timeout_ms, max_output_tokens):
        self.requests.append(request)
        out = self.rule(request)
        return out if isinstance(out, Attempt) else ok(out)


def decider(fake, mode='AGENT_REPLAY', params=PARAMS, budget=None):
    return AgentDecider(params=params, mode=mode, budget=budget or CallBudget(params, STAGE), model='astra6',
                        call=fake, provider_kind='OPENAI')


def run(name, as_of, **kw):
    return response(scenarios()[name], EDGES, as_of_us=as_of, parameters=Parameters(),
                    clock_mapping_sha256='a' * 64, **kw)


def reasons(audit):
    return [row['reason'] for row in audit]


def pick_camera(camera):
    def rule(request):
        for c in request['candidates']:
            if c['camera_id'] == camera and c['rule_eligible']:
                return sel(c['id'])
        return ABSTAIN
    return rule


# ------------------------------------------------------------------ 1. default OFF is byte-identical

def test_golden_default_is_byte_identical_to_ddce2aa():
    assert golden_sha256() == GOLDEN_SHA256


@pytest.mark.parametrize('mode', ['OFF', 'RULE_ONLY'])
def test_golden_with_off_decider_injected_is_byte_identical_and_never_calls_provider(mode):
    fake = Fake(lambda r: pytest.fail('provider must not be called'))
    assert golden_sha256(decider=decider(fake, mode=mode)) == GOLDEN_SHA256
    assert not fake.requests


def test_default_mode_constant_is_off():
    assert ad.DEFAULT_MODE == 'OFF'
    assert AgentDecider(params=PARAMS).mode == 'OFF'


# ------------------------------------------------------------------ 2. agent ON, fake provider

def test_dp1_select_resolves_an_ambiguity_the_rule_abstains_on():
    rule_result, rule_events, _ = run('ambiguous_two', 1_800_000)
    assert not rule_events
    fake = Fake(pick_camera('CAM_C'))
    result, events, audit = run('ambiguous_two', 1_800_000, decider=decider(fake))
    assert len(events) == 1 and events[0]['to_camera_id'] == 'CAM_C' and events[0]['reason'] == 'AGENT_ASSOCIATION_HYPOTHESIS'
    assert events[0]['identity_verdict'] == 'UNCONFIRMED' and result['identity_verdict'] == 'UNCONFIRMED'
    assert 'AGENT_NOT_SELECTED' in reasons(audit) and 'AMBIGUOUS_HANDOFF' not in reasons(audit)
    selected = [s for s in result['sightings'] if s['selected_for_single_view']]
    assert {s['camera_id'] for s in selected} == {'CAM_A', 'CAM_C'}
    records = [row['record'] for row in audit if row['reason'] == 'AGENT_DECISION_RECORD']
    assert records and all(r['decision_source'] == 'AGENT' and r['mode'] == 'AGENT_REPLAY' for r in records)
    for r in records:
        ad.validate_record(r)


def test_dp1_abstain_on_single_candidate_rejects_the_handoff():
    fake = Fake(lambda r: ABSTAIN)
    result, events, audit = run('single_handoff', 3_000_000, decider=decider(fake))
    assert not events and 'AGENT_REJECTED_HANDOFF' in reasons(audit) and 'DEMO_ASSOCIATION_HYPOTHESIS' not in reasons(audit)
    assert all(s['camera_id'] == 'CAM_A' for s in result['sightings'] if s['selected_for_single_view'])


def test_dp1_abstain_on_ambiguity_keeps_the_rule_labels():
    _, rule_events, rule_audit = run('ambiguous_two', 1_800_000)
    fake = Fake(lambda r: ABSTAIN)
    _, events, audit = run('ambiguous_two', 1_800_000, decider=decider(fake))
    assert events == rule_events
    assert reasons(audit).count('AMBIGUOUS_HANDOFF') == reasons(rule_audit).count('AMBIGUOUS_HANDOFF')


def test_dp1_select_equal_to_rule_matches_rule_chain():
    rule_result, rule_events, _ = run('single_handoff', 3_000_000)
    fake = Fake(lambda r: sel([c for c in r['candidates'] if c['rule_eligible']][0]['id']))
    result, events, _ = run('single_handoff', 3_000_000, decider=decider(fake))
    assert [e['to_track_ref'] for e in events] == [e['to_track_ref'] for e in rule_events]
    assert result['sightings'] == rule_result['sightings']


def test_dp3_reject_drops_the_segment_from_the_selected_chain():
    rule_result, _, _ = run('continuations', 4_200_000)
    fake = Fake(lambda r: REJECT if r['decision_point'] == ad.DP3 else ABSTAIN if False else
                sel([c for c in r['candidates'] if c['rule_eligible']][0]['id']))
    result, _, audit = run('continuations', 4_200_000, decider=decider(fake))
    dp3 = [r for r in fake.requests if r['decision_point'] == ad.DP3]
    assert len(dp3) == 2 and all(r['segment']['n_frames'] >= 1 for r in dp3)
    chosen = lambda res: {oid for s in res['sightings'] if s['selected_for_single_view'] for oid in s['observation_ids']}
    removed = chosen(rule_result) - chosen(result)
    assert removed and all(o.split(':')[1] in {str(t) for t in range(600_000, 1_200_000, STEP)} | {str(t) for t in range(3_000_000, 3_600_000, STEP)}
                           for o in removed)
    assert 'BOX_CONTINUATION' in reasons(audit)  # rejected boxes stay visible as unassociated local candidates


def test_dp3_accept_equals_rule():
    rule_result, rule_events, _ = run('continuations', 4_200_000)
    fake = Fake(lambda r: ACCEPT if r['decision_point'] == ad.DP3 else
                sel([c for c in r['candidates'] if c['rule_eligible']][0]['id']))
    result, events, _ = run('continuations', 4_200_000, decider=decider(fake))
    assert result['sightings'] == rule_result['sightings'] and len(events) == len(rule_events)


# ------------------------------------------------------------------ 3. WP1 fallback rules are the only fallback

@pytest.mark.parametrize('attempt,reason', [
    (Attempt('UNAVAILABLE', 5.0), 'PROVIDER_UNAVAILABLE'),
    (Attempt('REPLAY_MISS', 1.0), 'REPLAY_MISS'),
    (ok({'action': 'SELECT', 'candidate_id': 'Z9', 'reason_codes': ['GRAPH_EDGE'], 'rationale': ''}), 'ILLEGAL_CANDIDATE'),
    (ok({'junk': 1}), 'INVALID_RESPONSE'),
])
def test_provider_failures_fall_back_to_the_exact_rule_output(attempt, reason):
    for name, as_of in (('single_handoff', 3_000_000), ('ambiguous_two', 2_600_000), ('continuations', 4_200_000)):
        base = run(name, as_of)
        result, events, audit = run(name, as_of, decider=decider(Fake(lambda r: attempt)))
        assert result['sightings'] == base[0]['sightings'] and events == base[1]
        assert result['single_view'] == base[0]['single_view']
        agent_rows = [a for a in audit if a['reason'] == 'AGENT_DECISION_RECORD']
        assert agent_rows and all(a['decision_source'] == 'RULE_FALLBACK' for a in agent_rows)
        for a in agent_rows:  # a candidate id is meaningless for a DP3 request: that is INVALID_RESPONSE
            dp3_swap = reason == 'ILLEGAL_CANDIDATE' and a['decision_point'] == ad.DP3
            assert a['fallback_reason'] == ('INVALID_RESPONSE' if dp3_swap else reason)
        assert [a for a in audit if a['reason'] != 'AGENT_DECISION_RECORD'] == base[2]


def test_session_budget_exhaustion_falls_back_with_call_budget_exhausted():
    params = json.loads(json.dumps(PARAMS))
    params['per_session']['max_rounds'] = 1
    fake = Fake(lambda r: ABSTAIN)
    _, _, audit = run('continuations', 4_200_000, decider=decider(fake, params=params))
    rows = [a for a in audit if a['reason'] == 'AGENT_DECISION_RECORD']
    assert len(fake.requests) == 1 and len(rows) > 1
    assert {a['fallback_reason'] for a in rows[1:]} == {'CALL_BUDGET_EXHAUSTED'}


def test_live_mode_without_an_approved_stage_never_calls_the_provider():
    fake = Fake(lambda r: pytest.fail('provider must not be called'))
    result, events, audit = run('single_handoff', 3_000_000, decider=decider(fake, mode='AGENT_LIVE'))
    base = run('single_handoff', 3_000_000)
    assert events == base[1] and not fake.requests
    assert {a['fallback_reason'] for a in audit if a['reason'] == 'AGENT_DECISION_RECORD'} == {'MODE_NOT_AUTHORIZED'}


def test_replay_run_is_deterministic():
    one = run('ambiguous_two', 2_600_000, decider=decider(Fake(pick_camera('CAM_C'))))
    two = run('ambiguous_two', 2_600_000, decider=decider(Fake(pick_camera('CAM_C'))))
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)


# ------------------------------------------------------------------ 4. requests: causal, opaque, no protected keys

def test_requests_are_opaque_causal_and_validate():
    secret = 'SECRETREF_'
    tracks = [Track(t.camera_id, secret + t.track_ref, t.observations) for t in scenarios()['ambiguous_two']]
    fake = Fake(pick_camera('CAM_C'))
    response(tracks, EDGES, as_of_us=2_600_000, parameters=Parameters(), clock_mapping_sha256='a' * 64,
             decider=decider(fake))
    assert fake.requests
    for request in fake.requests:
        ad.validate_request(request)  # includes the FORBIDDEN-key scan and the causal first<=last<as_of rule
        text = json.dumps(request)
        assert secret not in text and 'observation' not in text and 'track_ref' not in text
        assert request['identity_verdict'] == 'UNCONFIRMED'
        assert all(c['last_seen_us'] <= request['as_of_us'] - STEP for c in request['candidates'])


def test_request_never_includes_observations_after_the_decision_time():
    fake = Fake(pick_camera('CAM_C'))
    run('ambiguous_two', 5_000_000, decider=decider(fake))
    first = fake.requests[0]
    assert first['as_of_us'] == 1_000_000 + STEP  # decision at the first shared sample, later frames excluded
    assert all(c['last_seen_us'] == 1_000_000 for c in first['candidates'])


def test_future_samples_do_not_change_an_earlier_agent_decision():
    short = run('ambiguous_two', 1_400_000, decider=decider(Fake(pick_camera('CAM_C'))))
    long = run('ambiguous_two', 5_000_000, decider=decider(Fake(pick_camera('CAM_C'))))
    assert short[1][0]['to_track_ref'] == long[1][0]['to_track_ref']


def test_unbuildable_request_falls_back_and_is_audited_not_raised():
    bad = [Track('CAM_A', 'a', (Observation('CAM_A', 0, 'a:0', .7, frozenset(['red'])),
                                Observation('CAM_A', 200_000, 'a:200000', .7, frozenset(['red'])))),
           Track('CAM_B', 'b', (Observation('CAM_B', 1_000_000, 'b:1', 1.5, frozenset(['red'])),))]
    fake = Fake(lambda r: pytest.fail('provider must not be called'))
    base = response(bad, EDGES, as_of_us=2_000_000, parameters=Parameters(), clock_mapping_sha256='a' * 64)
    result, events, audit = response(bad, EDGES, as_of_us=2_000_000, parameters=Parameters(),
                                     clock_mapping_sha256='a' * 64, decider=decider(fake))
    assert events == base[1] and 'AGENT_REQUEST_REJECTED' in reasons(audit) and not fake.requests


# ------------------------------------------------------------------ 5. isolation / static

def test_wiring_module_has_no_io_environment_or_gt_access():
    source = Path(agent_wiring.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules <= {'__future__', 'collections.abc', 're', 'statistics', 'amidst.q1q5'}
    assert not any(token in source for token in ('open(', 'environ', 'getenv', 'OPENAI', 'api_key', 'gt_private'))


def test_cross_camera_demo_stays_import_free_and_decider_optional():
    path = Path(cross_camera_demo.__file__)
    tree = ast.parse(path.read_text())
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))
    assert all(n.module in {'dataclasses', 'datetime', 'itertools'} for n in ast.walk(tree) if isinstance(n, ast.ImportFrom))
    import inspect
    assert inspect.signature(cross_camera_demo.associate).parameters['decider'].default is None
    assert inspect.signature(cross_camera_demo.response).parameters['decider'].default is None

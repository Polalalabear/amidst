"""Acceptance gates for DP4 attention ranking (D210, D214, contract DP4_ATTENTION_RANKING_V1.md).

Rule gates run against ``amidst.q1q5.attention_ranking`` and PASS today. API and Agent gates are
``xfail(strict=True)``: they fail until Argon (N3) delivers ``amidst.q1q5.attention_api.ApiRanker``
and ``amidst.q1q5.attention_agent.AgentRanker``. Argon turns them into PASS without editing any
assertion, and removes the two markers (API_GATE, AGENT_GATE) together with the last gate of each
group. Strict xfail makes an XPASS that still carries the marker fail CI.

Synthetic data only: no GT, renders, media or network. Fake clients return ``agent_decision.Attempt``.
"""
import ast
import copy
import json
from pathlib import Path

import pytest

from amidst.q1q5 import attention_ranking as ar
from amidst.q1q5.agent_decision import Attempt

ROOT = Path(__file__).resolve().parents[2]
ISSUE = 'N3 (DP4 API and Agent, Argon)'
API_GATE = pytest.mark.xfail(strict=True, reason=f'awaiting {ISSUE}: attention_api.ApiRanker')
AGENT_GATE = pytest.mark.xfail(strict=True, reason=f'awaiting {ISSUE}: attention_agent.AgentRanker')

SEEN = 10_000_000
PRICE = (1.0, 4.0)  # USD per million input / output tokens (synthetic)


# ------------------------------------------------------------------ fixtures

def _zone(zone_id, x0, x1, edge):
    return {'exit_zone_id': zone_id, 'roi_polygon_px': [[x0, 150], [x1, 150], [x1, 260], [x0, 260]],
            'leads_to_edge_ids': [edge], 'mapping_basis': 'MANUAL_ON_STATIC_FRAME'}


def _transition(src, dst, via):
    return {'transition_id': f'T_{src}__{dst}', 'from_camera_id': src, 'to_camera_id': dst,
            'via_exit_zone_ids': [via], 'relation': 'UNKNOWN', 'region_hops': 1,
            'nominal_path_length_m': None, 'path_traversability': 'TOPOLOGICAL_ONLY',
            'path_has_unknown_state': True}


def corridor_graph():
    """A - B - C in a line; B has a left and a right exit; D is an unconnected node."""
    cams = [
        {'camera_id': 'CAM_A', 'exit_zones': [_zone('A:X_R', 580, 640, 'E_AB')]},
        {'camera_id': 'CAM_B', 'exit_zones': [_zone('B:X_L', 0, 60, 'E_AB'), _zone('B:X_R', 580, 640, 'E_BC')]},
        {'camera_id': 'CAM_C', 'exit_zones': [_zone('C:X_L', 0, 60, 'E_BC')]},
        {'camera_id': 'CAM_D', 'exit_zones': []},
    ]
    trans = [_transition('CAM_B', 'CAM_A', 'B:X_L'), _transition('CAM_B', 'CAM_C', 'B:X_R'),
             _transition('CAM_A', 'CAM_B', 'A:X_R'), _transition('CAM_C', 'CAM_B', 'C:X_L')]
    return {'schema_version': 'q-demo.camera-transition-graph.v1', 'approval_status': 'DRAFT',
            'cameras': cams, 'transitions': trans}


def make_request(direction='right', elapsed_us=2_000_000, summaries=None, camera='CAM_B'):
    step = 20 if direction == 'right' else -20
    start = 300 if direction == 'right' else 330
    boxes = [{'time_us': SEEN - (4 - i) * 200_000,
              'bbox_xyxy_px': [start + step * i * 2, 100, start + step * i * 2 + 40, 200]} for i in range(5)]
    last = boxes.pop()
    return {'schema_version': ar.REQUEST_SCHEMA, 'as_of_us': SEEN + elapsed_us, 'elapsed_us': elapsed_us,
            'last_observation': {'camera_id': camera, 'time_us': SEEN, 'bbox_xyxy_px': last['bbox_xyxy_px'],
                                 'recent_boxes': boxes, 'direction_estimate': None},
            'graph': corridor_graph(), 'camera_summaries': summaries or []}


def tops(response, n=1):
    return [r['camera_id'] for r in response['ranking'][:n]]


def good_ranking(request):
    return [{'camera_id': n, 'score': round(1 - i * 0.1, 3), 'reason': 'MODEL_RANKED'}
            for i, n in enumerate(ar.validate_request(request))]


# ------------------------------------------------------------------ Rule gates (PASS)

def test_rule_straight_corridor_front_neighbor_first():
    right = ar.rank_attention(make_request('right'))
    assert tops(right) == ['CAM_C']
    ar.validate_response(right, make_request('right'))
    assert right['method'] == 'RULE' and right['steps'] == 0 and right['cost_usd'] == 0.0
    assert right['latency_ms'] >= 0 and right['fallback_reason'] is None
    assert right['ranking'][0]['reason'] == 'EXIT_ALIGNED'


def test_rule_turning_back_updates_ranking():
    assert tops(ar.rank_attention(make_request('right'))) == ['CAM_C']
    assert tops(ar.rank_attention(make_request('left'))) == ['CAM_A']


def test_rule_still_in_view_keeps_current_camera_first():
    resp = ar.rank_attention(make_request('right', elapsed_us=300_000))
    assert resp['ranking'][0] == {'camera_id': 'CAM_B', 'score': 1.0, 'reason': 'STILL_IN_VIEW'}
    assert tops(resp, 2)[1] == 'CAM_C'


def test_rule_negative_evidence_prunes_empty_camera():
    window_end = SEEN + 8_000_000
    empty = {'camera_id': 'CAM_C', 'coverage_end_us': window_end, 'person_detections_since_last_obs': 0}
    request = make_request('right', elapsed_us=8_000_000, summaries=[empty])
    resp = ar.rank_attention(request)
    row = next(r for r in resp['ranking'] if r['camera_id'] == 'CAM_C')
    assert row['score'] == 0.0 and row['reason'] == 'NEGATIVE_EVIDENCE'
    assert tops(resp)[0] != 'CAM_C'
    # partial coverage only demotes; a camera that did see people is not pruned
    partial = dict(empty, coverage_end_us=SEEN + 4_000_000)
    resp = ar.rank_attention(make_request('right', elapsed_us=4_000_000, summaries=[partial]))
    row = next(r for r in resp['ranking'] if r['camera_id'] == 'CAM_C')
    assert 0 < row['score'] < 0.6
    seen_people = dict(empty, person_detections_since_last_obs=2)
    resp = ar.rank_attention(make_request('right', elapsed_us=8_000_000, summaries=[seen_people]))
    assert next(r for r in resp['ranking'] if r['camera_id'] == 'CAM_C')['reason'] != 'NEGATIVE_EVIDENCE'


def test_rule_overdue_lowers_score():
    on_time = ar.rank_attention(make_request('right', elapsed_us=2_000_000))
    late = ar.rank_attention(make_request('right', elapsed_us=12_000_000))
    def pick(resp):
        return next(r for r in resp['ranking'] if r['camera_id'] == 'CAM_C')

    assert pick(late)['score'] < pick(on_time)['score'] and pick(late)['reason'] == 'OVERDUE'


def test_rule_output_only_graph_nodes_and_covers_all():
    request = make_request('right')
    resp = ar.rank_attention(request)
    nodes = set(ar.graph_nodes(request['graph']))
    assert {r['camera_id'] for r in resp['ranking']} == nodes
    assert len(resp['ranking']) == len(nodes)
    assert next(r for r in resp['ranking'] if r['camera_id'] == 'CAM_D')['reason'] == 'NOT_ADJACENT'


def test_rule_is_deterministic_apart_from_latency():
    a = ar.rank_attention(make_request('left'))
    b = ar.rank_attention(make_request('left'))
    assert a['ranking'] == b['ranking']


FORBIDDEN_CASES = [('top', 'ground_truth'), ('top', 'gt_camera'), ('last_observation', 'visibility'),
                   ('last_observation', 'depth'), ('last_observation', 'renderer_trajectory'),
                   ('top', 'operator_person_id'), ('top', 'operator_position'), ('summary', 'world_xy'),
                   ('summary', 'person_id'), ('graph', 'actor_id'), ('top', 'truth_camera_id')]


@pytest.mark.parametrize('where,key', FORBIDDEN_CASES)
def test_rule_rejects_forbidden_fields(where, key):
    request = make_request('right', summaries=[{'camera_id': 'CAM_C', 'coverage_end_us': SEEN,
                                                'person_detections_since_last_obs': 0}])
    target = {'top': request, 'last_observation': request['last_observation'], 'graph': request['graph'],
              'summary': request['camera_summaries'][0]}[where]
    target[key] = 1
    with pytest.raises(ar.AttentionInputError) as err:
        ar.rank_attention(request)
    assert err.value.code == 'FORBIDDEN_INFERENCE_INPUT'


@pytest.mark.parametrize('mutate,code', [
    (lambda r: r.update(extra=1), 'UNKNOWN_OR_MISSING_FIELD'),
    (lambda r: r.update(elapsed_us=5), 'ELAPSED_MISMATCH'),
    (lambda r: r['last_observation'].update(camera_id='CAM_Z'), 'CAMERA_NOT_IN_GRAPH'),
    (lambda r: r['last_observation'].update(time_us=r['as_of_us'] + 1), 'FUTURE_INPUT'),
    (lambda r: r['camera_summaries'].append({'camera_id': 'CAM_Z', 'coverage_end_us': 0,
                                             'person_detections_since_last_obs': 0}), 'INVALID_SUMMARY'),
    (lambda r: r['camera_summaries'].append({'camera_id': 'CAM_A', 'coverage_end_us': r['as_of_us'] + 1,
                                             'person_detections_since_last_obs': 0}), 'FUTURE_INPUT'),
])
def test_rule_rejects_malformed_requests(mutate, code):
    request = make_request('right')
    mutate(request)
    with pytest.raises(ar.AttentionInputError) as err:
        ar.rank_attention(request)
    assert err.value.code == code


def test_rule_on_pinned_r004_graph_returns_only_graph_nodes():
    graph = json.loads((ROOT / 'configs/q1q5/graphs/r004/camera_graph_v3.json').read_text(encoding='utf-8'))
    request = {'schema_version': ar.REQUEST_SCHEMA, 'as_of_us': 5_000_000, 'elapsed_us': 2_000_000,
               'last_observation': {'camera_id': 'CAM_W1', 'time_us': 3_000_000,
                                    'bbox_xyxy_px': [300, 200, 340, 300]},
               'graph': graph, 'camera_summaries': []}
    resp = ar.rank_attention(request)
    ar.validate_response(resp, request)
    assert {r['camera_id'] for r in resp['ranking']} == {c['camera_id'] for c in graph['cameras']}


def test_fallback_reasons_match_agent_decision():
    from amidst.q1q5 import agent_decision
    assert ar.FALLBACK_REASONS == agent_decision.FALLBACK_REASONS


def test_rule_does_not_touch_associate():
    # attention_api.py / attention_agent.py (N3) must import the shared contract module; nothing else may.
    own = {'attention_ranking.py', 'attention_api.py', 'attention_agent.py'}
    for path in (ROOT / 'src/amidst').rglob('*.py'):
        if path.name not in own:
            assert 'attention_ranking' not in path.read_text(encoding='utf-8'), path
    for name in ('attention_api', 'attention_agent'):
        for path in (ROOT / 'src/amidst').rglob('*.py'):
            if path.name not in own:
                assert name not in path.read_text(encoding='utf-8'), path
    import amidst.q1q5.cross_camera_demo as demo
    assert not hasattr(demo, 'attention_ranking')


def test_response_validator_rejects_bad_documents():
    request = make_request('right')
    good = ar.rank_attention(request)
    ar.validate_response(good, request)

    def broken(mutate):
        doc = copy.deepcopy(good)
        mutate(doc)
        with pytest.raises(ar.AttentionInputError):
            ar.validate_response(doc, request)

    broken(lambda d: d['ranking'][0].update(camera_id='CAM_Z'))
    broken(lambda d: d['ranking'].append(dict(d['ranking'][0])))
    broken(lambda d: d['ranking'].reverse())
    broken(lambda d: d['ranking'][0].update(reason='BECAUSE'))
    broken(lambda d: d['ranking'][0].update(score=1.5))
    broken(lambda d: d.update(extra=1))
    broken(lambda d: d.pop('latency_ms'))
    broken(lambda d: d.update(method='API', fallback_reason='PROVIDER_TIMEOUT'))
    broken(lambda d: d.update(steps=-1))
    broken(lambda d: d.update(fallback_reason='NOPE'))


def test_metrics_hit_lead_and_false_switch():
    def resp(top, second):
        return {'ranking': [{'camera_id': top}, {'camera_id': second}, {'camera_id': 'CAM_D'}]}
    assert ar.hit_at_k(resp('CAM_A', 'CAM_C'), 'CAM_C', 1) is False
    assert ar.hit_at_k(resp('CAM_A', 'CAM_C'), 'CAM_C', 3) is True
    updates = [(1, resp('CAM_A', 'CAM_C')), (2, resp('CAM_C', 'CAM_A')), (3, resp('CAM_C', 'CAM_A'))]
    assert ar.lead_time_us(updates, 'CAM_C', 10) == 8
    assert ar.false_switches(updates, 'CAM_C', 10) == 0
    updates = [(1, resp('CAM_C', 'CAM_A')), (2, resp('CAM_A', 'CAM_C')), (3, resp('CAM_D', 'CAM_C')),
               (4, resp('CAM_C', 'CAM_A'))]
    assert ar.lead_time_us(updates, 'CAM_C', 10) == 6   # top-1 correct again only from t=4
    assert ar.false_switches(updates, 'CAM_C', 10) == 2  # C->A and A->D, not D->C
    assert ar.lead_time_us([(1, resp('CAM_A', 'CAM_C'))], 'CAM_C', 10) is None
    assert ar.lead_time_us([(11, resp('CAM_C', 'CAM_A'))], 'CAM_C', 10) is None


# ------------------------------------------------------------------ fake clients

class FakeClient:
    """Plays a list of Attempt objects; records every request it receives."""
    def __init__(self, attempts):
        self.attempts, self.seen = list(attempts), []

    def __call__(self, request, *, timeout_ms, max_output_tokens):
        self.seen.append(copy.deepcopy(request))
        return self.attempts[min(len(self.seen) - 1, len(self.attempts) - 1)]


def ok(response, wall_ms=120.0, tokens=(1000, 100)):
    return Attempt('OK', wall_ms, response, tokens[0], tokens[1])


def api_ranker(client, **kw):
    from amidst.q1q5.attention_api import ApiRanker
    return ApiRanker(client, timeout_ms=3000, max_output_tokens=512, price_per_mtok=PRICE, **kw)


def agent_ranker(client, **kw):
    from amidst.q1q5.attention_agent import AgentRanker
    return AgentRanker(client, max_steps=kw.pop('max_steps', 4), budget_usd=kw.pop('budget_usd', 0.02),
                       timeout_ms=3000, max_output_tokens=512, price_per_mtok=PRICE, **kw)


def assert_rule_fallback(resp, request, reason, requested):
    ar.validate_response(resp, request)
    assert resp['method'] == 'RULE' and resp['requested_method'] == requested
    assert resp['fallback_reason'] == reason
    assert resp['ranking'] == ar.rank_attention(request)['ranking']


def tool(name, **args):
    return {'action': 'TOOL', 'tool': name, 'args': args}


# ------------------------------------------------------------------ API gates (xfail until N3)

@API_GATE
def test_api_gate_valid_response_has_latency_cost_steps():
    request = make_request('right')
    client = FakeClient([ok({'ranking': good_ranking(request)}, wall_ms=250.0, tokens=(2000, 200))])
    resp = api_ranker(client).rank(request)
    ar.validate_response(resp, request)
    assert resp['method'] == 'API' and resp['requested_method'] == 'API' and resp['fallback_reason'] is None
    assert resp['steps'] == 1 and len(client.seen) == 1
    assert resp['latency_ms'] == pytest.approx(250.0)
    assert resp['cost_usd'] == pytest.approx((2000 * PRICE[0] + 200 * PRICE[1]) / 1e6)


@API_GATE
def test_api_gate_cost_unknown_without_price_table():
    from amidst.q1q5.attention_api import ApiRanker
    request = make_request('right')
    resp = ApiRanker(FakeClient([ok({'ranking': good_ranking(request)})]), timeout_ms=3000,
                     max_output_tokens=512, price_per_mtok=None).rank(request)
    assert resp['method'] == 'API' and resp['cost_usd'] is None


@API_GATE
def test_api_gate_timeout_falls_back_to_rule():
    request = make_request('left')
    resp = api_ranker(FakeClient([Attempt('TIMEOUT', 3000.0)])).rank(request)
    assert_rule_fallback(resp, request, 'PROVIDER_TIMEOUT', 'API')
    assert resp['latency_ms'] >= 3000.0


@API_GATE
@pytest.mark.parametrize('payload,reason', [
    ({'ranking': 'nonsense'}, 'INVALID_RESPONSE'),
    ({'ranking': [{'camera_id': 'CAM_C', 'score': 2, 'reason': 'MODEL_RANKED'}]}, 'INVALID_RESPONSE'),
    ({'ranking': [{'camera_id': 'CAM_Z', 'score': 0.9, 'reason': 'MODEL_RANKED'}]}, 'ILLEGAL_CANDIDATE'),
    (None, 'INVALID_RESPONSE'),
])
def test_api_gate_invalid_output_falls_back_to_rule(payload, reason):
    request = make_request('right')
    resp = api_ranker(FakeClient([ok(payload)])).rank(request)
    assert_rule_fallback(resp, request, reason, 'API')


@API_GATE
def test_api_gate_unavailable_falls_back_and_never_raises():
    request = make_request('right')
    resp = api_ranker(FakeClient([Attempt('UNAVAILABLE', 5.0)])).rank(request)
    assert_rule_fallback(resp, request, 'PROVIDER_UNAVAILABLE', 'API')


@API_GATE
def test_api_gate_request_to_client_has_no_forbidden_fields():
    request = make_request('right')
    client = FakeClient([ok({'ranking': good_ranking(request)})])
    api_ranker(client).rank(request)
    for sent in client.seen:
        ar.scan_forbidden(sent)


@API_GATE
def test_api_gate_forbidden_input_rejected_before_any_call():
    request = make_request('right')
    request['operator_person_id'] = 'P7'
    client = FakeClient([ok({'ranking': good_ranking(make_request('right'))})])
    with pytest.raises(ar.AttentionInputError):
        api_ranker(client).rank(request)
    assert client.seen == []


# ------------------------------------------------------------------ Agent gates (xfail until N3)

@AGENT_GATE
def test_agent_gate_tool_loop_then_final_answer():
    request = make_request('right')
    client = FakeClient([ok(tool('get_graph_neighbors', camera_id='CAM_B')),
                         ok(tool('get_recent_detections', camera_id='CAM_C')),
                         ok({'action': 'FINAL', 'ranking': good_ranking(request)}, wall_ms=100.0)])
    resp = agent_ranker(client).rank(request)
    ar.validate_response(resp, request)
    assert resp['method'] == 'AGENT' and resp['fallback_reason'] is None
    assert resp['steps'] == 3 and len(client.seen) == 3
    assert resp['latency_ms'] >= 3 * 100.0 * 0.99
    assert resp['cost_usd'] == pytest.approx(3 * (1000 * PRICE[0] + 100 * PRICE[1]) / 1e6)


@AGENT_GATE
def test_agent_gate_update_hypothesis_tool_is_allowed():
    request = make_request('right')
    client = FakeClient([ok(tool('update_hypothesis', ranking=good_ranking(request))),
                         ok({'action': 'FINAL', 'ranking': good_ranking(request)})])
    resp = agent_ranker(client).rank(request)
    assert resp['method'] == 'AGENT' and resp['steps'] == 2


@AGENT_GATE
def test_agent_gate_step_limit_falls_back_to_rule():
    request = make_request('right')
    client = FakeClient([ok(tool('get_graph_neighbors', camera_id='CAM_B'))])  # never answers
    resp = agent_ranker(client, max_steps=4).rank(request)
    assert_rule_fallback(resp, request, 'ROUND_LIMIT', 'AGENT')
    assert resp['steps'] == 4 and len(client.seen) == 4


@AGENT_GATE
def test_agent_gate_budget_limit_falls_back_to_rule():
    request = make_request('right')
    expensive = ok(tool('get_graph_neighbors', camera_id='CAM_B'), tokens=(20_000, 2_000))  # $0.028 > cap
    resp = agent_ranker(FakeClient([expensive]), budget_usd=0.02).rank(request)
    assert_rule_fallback(resp, request, 'CALL_BUDGET_EXHAUSTED', 'AGENT')
    assert resp['cost_usd'] <= 0.02 + 0.03  # at most one over-cap call is ever paid for
    assert resp['steps'] == 1


@AGENT_GATE
def test_agent_gate_timeout_falls_back_to_rule():
    request = make_request('left')
    resp = agent_ranker(FakeClient([Attempt('TIMEOUT', 3000.0)])).rank(request)
    assert_rule_fallback(resp, request, 'PROVIDER_TIMEOUT', 'AGENT')


@AGENT_GATE
def test_agent_gate_unknown_tool_falls_back_without_running_it():
    request = make_request('right')
    client = FakeClient([ok(tool('read_file', path='/etc/passwd'))])
    resp = agent_ranker(client).rank(request)
    assert_rule_fallback(resp, request, 'INVALID_RESPONSE', 'AGENT')
    assert len(client.seen) == 1


@AGENT_GATE
def test_agent_gate_tool_argument_outside_graph_falls_back():
    request = make_request('right')
    resp = agent_ranker(FakeClient([ok(tool('get_recent_detections', camera_id='CAM_Z'))])).rank(request)
    assert_rule_fallback(resp, request, 'ILLEGAL_CANDIDATE', 'AGENT')


@AGENT_GATE
def test_agent_gate_final_ranking_outside_graph_falls_back():
    request = make_request('right')
    bad = [{'camera_id': 'CAM_Z', 'score': 0.9, 'reason': 'MODEL_RANKED'}]
    resp = agent_ranker(FakeClient([ok({'action': 'FINAL', 'ranking': bad})])).rank(request)
    assert_rule_fallback(resp, request, 'ILLEGAL_CANDIDATE', 'AGENT')


@AGENT_GATE
def test_agent_gate_model_sees_no_forbidden_fields_in_any_turn():
    summaries = [{'camera_id': 'CAM_C', 'coverage_end_us': SEEN + 1_000_000,
                  'person_detections_since_last_obs': 1, 'last_person_detection_us': SEEN + 500_000,
                  'max_score': 0.8}]
    request = make_request('right', summaries=summaries)
    client = FakeClient([ok(tool('get_graph_neighbors', camera_id='CAM_B')),
                         ok(tool('get_recent_detections', camera_id='CAM_C')),
                         ok({'action': 'FINAL', 'ranking': good_ranking(request)})])
    agent_ranker(client).rank(request)
    assert len(client.seen) == 3
    for sent in client.seen:
        ar.scan_forbidden(sent)


@AGENT_GATE
def test_agent_gate_tool_list_is_exactly_the_contract_list():
    from amidst.q1q5.attention_agent import TOOL_NAMES
    assert tuple(TOOL_NAMES) == ar.AGENT_TOOLS


# ------------------------------------------------------------------ self-tests

def test_selftest_markers_are_strict_and_kept_or_removed_per_group():
    tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    for group, prefix, expected in (('API_GATE', 'test_api_gate_', 7), ('AGENT_GATE', 'test_agent_gate_', 10)):
        gates = [n for n in functions if n.name.startswith(prefix)]
        assert len(gates) == expected and len({n.name for n in gates}) == expected
        marked = sum(any(isinstance(d, ast.Name) and d.id == group for d in n.decorator_list) for n in gates)
        assert marked in (0, expected), f'{group}: keep or remove all markers together'
        definitions = [n.value for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == group for t in n.targets)]
        assert len(definitions) <= 1
        if marked:
            assert len(definitions) == 1
        for value in definitions:
            assert ast.unparse(value.func) == 'pytest.mark.xfail'
            assert any(k.arg == 'strict' and isinstance(k.value, ast.Constant) and k.value.value is True
                       for k in value.keywords)
    # no marker on anything outside the gate functions
    for node in functions:
        if not node.name.startswith(('test_api_gate_', 'test_agent_gate_')):
            assert not any(isinstance(d, ast.Name) and d.id in ('API_GATE', 'AGENT_GATE')
                           for d in node.decorator_list), node.name


def test_selftest_fake_client_and_helpers_discriminate():
    request = make_request('right')
    client = FakeClient([ok({'x': 1}), Attempt('TIMEOUT', 1.0)])
    assert client(request, timeout_ms=1, max_output_tokens=1).response == {'x': 1}
    assert client(request, timeout_ms=1, max_output_tokens=1).outcome == 'TIMEOUT'
    assert client(request, timeout_ms=1, max_output_tokens=1).outcome == 'TIMEOUT'  # repeats the last
    assert len(client.seen) == 3
    doc = ar.rank_attention(request)
    doc['method'] = 'API'
    with pytest.raises(AssertionError):
        assert_rule_fallback(doc, request, 'PROVIDER_TIMEOUT', 'API')
    bad = dict(request, operator_position=[1, 2])
    with pytest.raises(ar.AttentionInputError):
        ar.scan_forbidden(bad)
    assert [r['camera_id'] for r in good_ranking(request)] == ['CAM_A', 'CAM_B', 'CAM_C', 'CAM_D']

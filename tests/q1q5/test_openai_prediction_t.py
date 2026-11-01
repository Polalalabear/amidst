"""DEMO-UI-D-T: OpenAI overhead-view prediction adapter (D107; DEMO_UI_SUPPORT_V1 §5). Test-first; Codex implements.

Every test uses a fake transport and a fake key; sockets are blocked. The real
OPENAI_API_KEY is never read: the adapter receives an explicit ``env`` mapping.
"""
import hashlib
import json
import logging
import socket

import pytest
from demo_ui_support_helpers import FORBIDDEN_TOKENS, require_module, require_route, walk_keys

CODE = 'OPENAI_ADAPTER_IMPLEMENTATION_MISSING'
KEY = 'sk-SYNTHETIC-NOT-A-REAL-KEY-0123456789abcdef'
ENV = {'OPENAI_API_KEY': KEY}
URL = 'https://api.openai.com/v1/chat/completions'
AVAILABLE_LABEL = '外部模型推測（非系統判斷）'
UNAVAILABLE_LABEL = '外部推測不可用'
RESULT_KEYS = {'schema_version', 'status', 'reason', 'label', 'fallback', 'candidates', 'request_sha256', 'source',
               'attempts', 'model', 'used_for', 'scoring_use', 'identity_verdict', 'gt_read'}
REQUEST_KEYS = {'schema_version', 'as_of_us', 'topology', 'observed', 'last_exit', 'candidate_camera_ids'}
RECORDING_KEYS = {'schema_version', 'request_sha256', 'request', 'response', 'model'}
GOOD = {'candidates': [{'camera_id': 'B', 'likelihood': 'MEDIUM', 'reason': '沿東側出口方向'}]}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('NETWORK_BLOCKED_IN_TEST')
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket.socket, 'connect_ex', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)


def module():
    return require_module('AMIDST_OPENAI_PREDICTION_MODULE', 'amidst.q1q5.openai_prediction', CODE,
                          ('OpenAIPredictionAdapter', 'build_prediction_request'))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def completion(content):
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return json.dumps({'id': 'synthetic', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text}}]}).encode()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Transport:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes); self.calls = []

    def __call__(self, *, url, headers, body, timeout_s):
        self.calls.append({'url': url, 'headers': dict(headers), 'body': body, 'timeout_s': timeout_s})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome() if callable(outcome) else outcome


def camera_map():
    return {'schema_version': 'q-demo.camera-map.v1', 'scene_id': 'SYNTHETIC_SCENE', 'run_id': 'SYNTHETIC_RUN',
            'cameras': [
                {'camera_id': 'A', 'role': 'TRACKING', 'in_graph': True,
                 'exits': [{'exit_zone_id': 'A:east', 'leads_to_edge_ids': ['E1']}],
                 'display_position': {'status': 'CALIBRATED_STATIC', 'xy_m': [2.0, -5.5], 'basis_ref': 'x', 'basis_sha256': 'a' * 64}},
                {'camera_id': 'B', 'role': 'TRACKING', 'in_graph': True, 'exits': [], 'display_position': None},
                {'camera_id': 'C', 'role': 'TRACKING', 'in_graph': True, 'exits': [], 'display_position': None}],
            'transitions': [
                {'transition_id': 'T_A_B', 'from_camera_id': 'A', 'to_camera_id': 'B', 'relation': 'BLIND_GAP',
                 'via_exit_zone_ids': ['A:east'], 'region_path': ['R1', 'R2'], 'authority': 'DRAFT'},
                {'transition_id': 'T_A_C', 'from_camera_id': 'A', 'to_camera_id': 'C', 'relation': 'UNKNOWN',
                 'via_exit_zone_ids': [], 'region_path': ['R1', 'R3'], 'authority': 'DRAFT'}]}


def request(as_of=600_000, observed=None):
    observed = observed or [{'camera_id': 'A', 'range_us': [0, 400_000]}, {'camera_id': 'B', 'range_us': [1_000_000, 2_000_000]}]
    return module().build_prediction_request(camera_map=camera_map(), observed=observed, as_of_us=as_of,
                                             last_exit={'camera_id': 'A', 'exit_zone_id': 'A:east', 'direction_status': 'KNOWN'})


def adapter(transport=None, **kwargs):
    args = dict(enabled=True, mode='LIVE', model='test-model', transport=transport, env=ENV, clock=Clock(),
                timeout_s=5.0, max_calls_per_session=6)
    args.update(kwargs)
    return module().OpenAIPredictionAdapter(**args)


def predict(a, req=None, session='S1', query='Q1'):
    return a.predict(session_id=session, query_id=query, request=req if req is not None else request())


def assert_unavailable(result, reason):
    assert set(result) == RESULT_KEYS
    assert result['status'] == 'UNAVAILABLE' and result['reason'] == reason
    assert result['label'] == UNAVAILABLE_LABEL and result['fallback'] == 'PHYSICAL_PREDICTION'
    assert result['candidates'] == [] and result['scoring_use'] is False


# --- request builder (structured whitelist only) ---

def test_request_is_structured_whitelist_with_no_future_data():
    req = request()
    assert set(req) == REQUEST_KEYS and req['schema_version'] == 'q-demo.external-prediction-request.v1'
    assert set(req['topology']) == {'cameras', 'transitions'}
    assert all(set(c) == {'camera_id', 'role', 'exit_zone_ids'} for c in req['topology']['cameras'])
    assert all(set(t) == {'from_camera_id', 'to_camera_id', 'relation', 'via_exit_zone_ids'} for t in req['topology']['transitions'])
    assert req['observed'] == [{'camera_id': 'A', 'range_us': [0, 400_000]}]
    assert req['last_exit'] == {'camera_id': 'A', 'exit_zone_id': 'A:east', 'direction_status': 'KNOWN'}
    assert req['candidate_camera_ids'] == ['B', 'C']
    keys = set(walk_keys(req))
    assert not keys & {'display_position', 'xy_m', 'region_path', 'authority', 'basis_ref', 'scene_id', 'run_id'}
    text = canonical(req)
    assert not any(token in text for token in FORBIDDEN_TOKENS)


def test_straddling_segment_is_clipped_to_as_of():
    req = request(as_of=600_000, observed=[{'camera_id': 'A', 'range_us': [0, 800_000]}])
    assert req['observed'] == [{'camera_id': 'A', 'range_us': [0, 600_000]}]


@pytest.mark.parametrize('where', ['observed', 'camera_map', 'last_exit'])
def test_builder_refuses_forbidden_inputs(where):
    m = module(); cmap = camera_map(); observed = [{'camera_id': 'A', 'range_us': [0, 400_000]}]
    last = {'camera_id': 'A', 'exit_zone_id': 'A:east', 'direction_status': 'KNOWN'}
    {'observed': lambda: observed[0].update(renderer_trajectory=[[0, 0]]),
     'camera_map': lambda: cmap['cameras'][0].update(ground_truth={'x': 1}),
     'last_exit': lambda: last.update(gt_exit='A:east')}[where]()
    with pytest.raises(ValueError) as err:
        m.build_prediction_request(camera_map=cmap, observed=observed, as_of_us=600_000, last_exit=last)
    assert getattr(err.value, 'code', None) == 'FORBIDDEN_INFERENCE_INPUT'


# --- default off, key handling ---

def test_disabled_by_default_and_without_key():
    t = Transport()
    assert_unavailable(predict(module().OpenAIPredictionAdapter(transport=t, env=ENV)), 'DISABLED')
    assert_unavailable(predict(adapter(t, env={})), 'API_KEY_MISSING')
    assert t.calls == []


def test_success_sends_only_canonical_payload_and_labels_external_guess():
    t = Transport(completion(GOOD)); req = request(); result = predict(adapter(t), req)
    assert set(result) == RESULT_KEYS and result['status'] == 'AVAILABLE' and result['reason'] is None
    assert result['label'] == AVAILABLE_LABEL and result['fallback'] is None and result['source'] == 'LIVE'
    assert result['candidates'] == GOOD['candidates'] and result['attempts'] == 1 and result['model'] == 'test-model'
    assert result['used_for'] == 'DISPLAY_ONLY' and result['scoring_use'] is False
    assert result['identity_verdict'] == 'UNCONFIRMED' and result['gt_read'] is False
    assert result['request_sha256'] == hashlib.sha256(canonical(req).encode()).hexdigest()
    (call,) = t.calls
    assert call['url'] == URL and call['headers']['Authorization'] == 'Bearer ' + KEY
    assert 0 < call['timeout_s'] <= 5.0
    body = call['body'].decode()
    assert KEY not in body and json.loads(body)['model'] == 'test-model'
    contents = [m['content'] for m in json.loads(body)['messages'] if isinstance(m.get('content'), str)]
    assert canonical(req) in contents
    for token in ('image_url', 'input_image', '"type":"image', 'data:image', *FORBIDDEN_TOKENS):
        assert token not in body


# --- limits: timeout, retry, per-search, cache, session lock ---

def test_timeout_falls_back_without_retry():
    t = Transport(TimeoutError('slow'))
    result = predict(adapter(t))
    assert_unavailable(result, 'TIMEOUT'); assert result['attempts'] == 1 and len(t.calls) == 1


def test_late_response_after_deadline_is_discarded():
    clock = Clock()

    def late():
        clock.t += 6.0
        return completion(GOOD)
    t = Transport(late, completion(GOOD))
    result = predict(adapter(t, clock=clock))
    assert_unavailable(result, 'TIMEOUT'); assert len(t.calls) == 1


def test_one_retry_after_transport_error():
    t = Transport(ConnectionError('reset'), completion(GOOD))
    result = predict(adapter(t))
    assert result['status'] == 'AVAILABLE' and result['attempts'] == 2


def test_retry_limit_is_one():
    t = Transport(ConnectionError('reset'), ConnectionError('reset'), completion(GOOD))
    result = predict(adapter(t))
    assert_unavailable(result, 'TRANSPORT_ERROR'); assert result['attempts'] == 2 and len(t.calls) == 2


@pytest.mark.parametrize('raw', [
    b'not json',
    completion('not json'),
    completion({'candidates': [], 'extra': 1}),
    completion({'candidates': [{'camera_id': 'Z', 'likelihood': 'LOW', 'reason': 'x'}]}),
    completion({'candidates': [{'camera_id': 'B', 'likelihood': 'CERTAIN', 'reason': 'x'}]}),
    completion({'candidates': [{'camera_id': c, 'likelihood': 'LOW', 'reason': 'x'} for c in ['B', 'C', 'B', 'C']]}),
    completion({'candidates': [{'camera_id': 'B', 'likelihood': 'LOW', 'reason': 'x' * 201}]}),
    completion({'candidates': [{'camera_id': 'B', 'likelihood': 'LOW', 'reason': 'x', 'path': [[0, 0]]}]}),
    completion({'candidates': 'B'}),
    json.dumps({'choices': []}).encode(),
])
def test_malformed_responses_fall_back_after_one_retry(raw):
    t = Transport(raw, raw)
    result = predict(adapter(t))
    assert_unavailable(result, 'RESPONSE_SCHEMA_INVALID'); assert len(t.calls) == 2


def test_at_most_one_call_per_search():
    t = Transport(completion(GOOD)); a = adapter(t)
    first = predict(a); again = predict(a)
    assert len(t.calls) == 1 and again['candidates'] == first['candidates']
    assert again['source'] == 'CACHE' and again['attempts'] == 0
    f = Transport(ConnectionError('x'), ConnectionError('x')); b = adapter(f)
    predict(b, query='Q9'); assert_unavailable(predict(b, query='Q9'), 'TRANSPORT_ERROR')
    assert len(f.calls) == 2


def test_identical_request_is_served_from_cache():
    t = Transport(completion(GOOD)); a = adapter(t)
    predict(a, query='Q1'); cached = predict(a, query='Q2')
    assert len(t.calls) == 1 and cached['status'] == 'AVAILABLE' and cached['source'] == 'CACHE'


def test_session_call_cap_locks_further_calls():
    t = Transport(ConnectionError('x'), ConnectionError('x'), completion(GOOD), completion(GOOD))
    a = adapter(t, max_calls_per_session=2)
    predict(a, query='Q1')
    locked = predict(a, req=request(as_of=700_000), query='Q2')
    assert_unavailable(locked, 'SESSION_CALL_LIMIT_LOCKED'); assert locked['attempts'] == 0 and len(t.calls) == 2
    assert_unavailable(predict(a, req=request(as_of=800_000), query='Q3'), 'SESSION_CALL_LIMIT_LOCKED')
    assert predict(a, session='S2', query='Q1')['status'] == 'AVAILABLE'
    single = Transport(ConnectionError('x'), completion(GOOD))
    one = predict(adapter(single, max_calls_per_session=1))
    assert_unavailable(one, 'TRANSPORT_ERROR'); assert len(single.calls) == 1


# --- request validation inside the adapter ---

def test_adapter_refuses_non_whitelisted_or_future_requests_without_calling():
    t = Transport(); a = adapter(t)
    extra = dict(request(), image_url='data:image/png;base64,AAAA')
    assert_unavailable(predict(a, extra, query='Q1'), 'REQUEST_NOT_WHITELISTED')
    nested = request(); nested['observed'][0]['depth'] = 1.0
    assert_unavailable(predict(a, nested, query='Q2'), 'REQUEST_NOT_WHITELISTED')
    future = request(); future['observed'][0]['range_us'] = [0, 900_000]
    assert_unavailable(predict(a, future, query='Q3'), 'FUTURE_DATA_IN_REQUEST')
    assert t.calls == []


# --- key never leaves the Authorization header ---

def test_key_never_appears_in_results_logs_recordings_or_reprs(caplog):
    caplog.set_level(logging.DEBUG)
    records = []
    t = Transport(completion(GOOD), ConnectionError(f'denied for {KEY}'), ConnectionError(f'Bearer {KEY}'))
    a = adapter(t, recorder=records.append)
    outputs = [predict(a, query='Q1'), predict(a, req=request(as_of=700_000), query='Q2')]
    blob = ''.join(json.dumps(o, ensure_ascii=False) for o in outputs) + json.dumps(records, ensure_ascii=False)
    blob += caplog.text + repr(a) + str(a)
    assert KEY not in blob and records
    assert all(set(r) == RECORDING_KEYS for r in records)
    assert not any(k.lower() in {'headers', 'authorization', 'api_key'} for r in records for k in walk_keys(r))


# --- recorded replay for the demo ---

def test_replay_reproduces_recorded_answers_without_transport_or_key():
    records = []
    predict(adapter(Transport(completion(GOOD)), recorder=records.append))
    explode = Transport(AssertionError('transport must not be used in replay'))
    r = predict(adapter(explode, mode='REPLAY', env={}, replay=records))
    assert r['status'] == 'AVAILABLE' and r['source'] == 'REPLAY' and r['attempts'] == 0
    assert r['candidates'] == GOOD['candidates'] and r['label'] == AVAILABLE_LABEL and explode.calls == []
    miss = predict(adapter(explode, mode='REPLAY', env={}, replay=records), req=request(as_of=700_000))
    assert_unavailable(miss, 'REPLAY_MISS')
    assert_unavailable(predict(adapter(explode, mode='REPLAY', env={}, replay=records, enabled=False)), 'DISABLED')


def test_tampered_replay_records_are_refused():
    records = []
    predict(adapter(Transport(completion(GOOD)), recorder=records.append))
    bad = [dict(records[0], request_sha256='0' * 64)]
    with pytest.raises(ValueError):
        adapter(None, mode='REPLAY', env={}, replay=bad)
    worse = [dict(records[0], response={'candidates': [{'camera_id': 'Z', 'likelihood': 'LOW', 'reason': 'x'}]})]
    with pytest.raises(ValueError):
        adapter(None, mode='REPLAY', env={}, replay=worse)


@pytest.mark.parametrize('kwargs', [{'timeout_s': 6.0}, {'timeout_s': 0}, {'mode': 'STREAM'}, {'max_calls_per_session': 0}])
def test_invalid_configuration_is_refused(kwargs):
    with pytest.raises(ValueError):
        adapter(Transport(), **kwargs)


# --- API wiring: off unless the server configures an adapter ---

def test_api_route_defaults_off_and_falls_back():
    module(); require_route('q_external_prediction', CODE)
    from test_api import TOKEN, api_fixture, authorize, selected
    api, run = api_fixture(); r = selected(api, run)
    assert api.bootstrap()['external_prediction'] == {'enabled': False, 'mode': 'OFF'}
    result = api.call('q_external_prediction', {'session_ref': TOKEN, 'response_ref': r['session_id'], 'as_of_us': 500_000}, authorize)
    assert_unavailable(result, 'DISABLED')

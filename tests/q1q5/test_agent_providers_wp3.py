"""WP3 gate: OpenAI (astra6/sol6.1/terra6.1) and Ollama loopback provider adapters (#511).

All tests use fake transports, fake clocks and fake API keys; zero real network calls or sleeps.
"""
from __future__ import annotations

import ast
import copy
import io
import json
import logging
from pathlib import Path
import re
import socket
import time
import urllib.error

import pytest

from amidst.q1q5 import agent_decision as ad
from amidst.q1q5 import agent_providers as ap
from amidst.q1q5.agent_decision import AgentDecisionError, CallBudget, RuleDecider
from amidst.q1q5.agent_providers import FakeClock, OllamaProvider, OpenAIProvider
from amidst.q1q5.agent_recording import JSONLRecorder
from amidst.q1q5.agent_wiring import AgentDecider
from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, associate, response

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'docs/contracts/schemas/q-core.agent-decision.v1.schema.json').read_text(encoding='utf-8'))
FORMAL = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1.json').read_text(encoding='utf-8'))
EXPLORATORY = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1_exploratory.json').read_text(encoding='utf-8'))
STAGE = 'PILOT_AND_CONSISTENCY'
FAKE_KEY = 'sk-test-FAKE-WP3-SECRET-987654321'


def _scores(lo=0.5, mid=0.7, hi=0.9, n=5) -> dict:
    return {'n': n, 'min': lo, 'median': mid, 'max': hi}


def _view(id_: str, camera: str = 'CAM_A', first: int = 0, last: int = 1_000_000, colors=('red',)) -> dict:
    return {
        'id': id_,
        'camera_id': camera,
        'first_seen_us': first,
        'last_seen_us': last,
        'colors': list(colors),
        'scores': _scores(),
        'continuation_fraction': 0.1,
    }


def _cand(id_: str, camera: str = 'CAM_B', eligible: bool = True, gap: int = 400_000) -> dict:
    return dict(
        _view(id_, camera, 1_600_000, 1_800_000),
        gap_us=gap,
        graph_edge=True,
        link_kind='CROSS_CAMERA_HANDOFF',
        rule_eligible=eligible,
    )


def _dp1(*candidates) -> dict:
    cands = list(candidates) or [_cand('B1'), _cand('C2', 'CAM_C')]
    req = {
        'schema_version': ad.REQUEST_SCHEMA_VERSION,
        'decision_point': ad.DP1,
        'as_of_us': 2_000_000,
        'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B'], ['CAM_A', 'CAM_C']]},
        'current': _view('A1'),
        'candidates': cands,
        'rule_answer': 'ABSTAIN',
        'identity_verdict': 'UNCONFIRMED',
    }
    req['rule_answer'] = RuleDecider().answer(req)
    return req


def _select(id_: str = 'C2') -> dict:
    return {
        'action': 'SELECT',
        'candidate_id': id_,
        'reason_codes': ['GRAPH_EDGE', 'SHORT_GAP'],
        'rationale': 'selected candidate on connected camera',
    }


def _openai_envelope(
    content_obj: object,
    *,
    model: str = 'astra6-2026-11-10',
    prompt_tokens: int = 1200,
    completion_tokens: int = 45,
) -> bytes:
    content_str = content_obj if isinstance(content_obj, str) else json.dumps(content_obj)
    return json.dumps({
        'id': 'chatcmpl-fake-1',
        'model': model,
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content_str}}],
        'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens},
    }).encode('utf-8')


class ScriptedTransport:
    """Fake HTTP transport that records requests and replays scripted responses/exceptions."""

    def __init__(self, *steps, clock: FakeClock | None = None):
        self.steps = list(steps)
        self.clock = clock
        self.calls: list[dict] = []

    def __call__(self, *, url: str, headers: dict, body: bytes | None = None, timeout_s: float = 2.0, **kw):
        self.calls.append({
            'url': url,
            'headers': dict(headers),
            'body': json.loads(body.decode('utf-8')) if isinstance(body, (bytes, bytearray)) and body else body,
            'timeout_s': timeout_s,
        })
        step = self.steps.pop(0) if self.steps else (200, _openai_envelope(_select()))
        if callable(step) and not isinstance(step, type):
            return step(url=url, headers=headers, body=body, timeout_s=timeout_s)
        if isinstance(step, tuple) and len(step) == 2 and isinstance(step[0], BaseException) and self.clock is not None:
            exc, advance_ms = step
            self.clock.advance_ms(advance_ms)
            raise exc
        if isinstance(step, BaseException):
            raise step
        if isinstance(step, type) and issubclass(step, BaseException):
            raise step('simulated transport error')
        if isinstance(step, tuple) and len(step) == 3 and self.clock is not None:
            status, payload, advance_ms = step
            self.clock.advance_ms(advance_ms)
            return status, payload
        return step


def _http_error(code: int, msg: str = 'error') -> urllib.error.HTTPError:
    return urllib.error.HTTPError('https://api.openai.com/v1/chat/completions', code, msg, {}, io.BytesIO(b'{}'))


# ------------------------------------------------------------------ 1. OpenAI happy path + AgentDecider wiring

def test_openai_valid_json_returns_agent_decision_and_tokens():
    clock = FakeClock()
    transport = ScriptedTransport((200, _openai_envelope(_select('C2'), prompt_tokens=1150, completion_tokens=42), 180.0), clock=clock)
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
        seed=7,
        temperature=0.0,
    )
    record = ad.decide(
        _dp1(),
        mode='AGENT_LIVE',
        params=FORMAL,
        budget=budget,
        model='astra6',
        call=provider,
        provider_kind='OPENAI',
        provider_meta=provider.provider_meta(),
    )
    ad.validate_record(record)
    assert record['decision_source'] == 'AGENT'
    assert record['final_answer'] == 'C2'
    assert record['rule_answer'] == 'ABSTAIN'
    assert len(record['attempts']) == 1
    att = record['attempts'][0]
    assert att['outcome'] == 'OK'
    assert att['prompt_tokens'] == 1150 and att['completion_tokens'] == 42
    assert att['wall_ms'] == 180.0
    assert provider.last_api_model_id == 'astra6-2026-11-10'
    sent = transport.calls[0]['body']
    assert sent['response_format']['type'] == 'json_schema'
    assert sent['response_format']['json_schema']['schema'] == SCHEMA['$defs']['response']
    assert sent['max_output_tokens'] == 300


def test_openai_adapter_wires_into_agent_decider_end_to_end():
    clock = FakeClock()
    transport = ScriptedTransport((200, _openai_envelope(_select('B2'), prompt_tokens=900, completion_tokens=30), 120.0), clock=clock)
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='sol6.1',
        params=FORMAL,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    decider = AgentDecider(
        params=FORMAL,
        mode='AGENT_LIVE',
        budget=budget,
        model='sol6.1',
        call=provider,
        provider_kind='OPENAI',
    )
    tracks = [
        Track('CAM_A', 'a', (Observation('CAM_A', 0, 'a:0', 0.8, frozenset(['red'])),
                             Observation('CAM_A', 200_000, 'a:1', 0.8, frozenset(['red'])))),
        Track('CAM_B', 'b', (Observation('CAM_B', 600_000, 'b:0', 0.8, frozenset(['red'])),
                             Observation('CAM_B', 800_000, 'b:1', 0.8, frozenset(['red'])))),
        Track('CAM_C', 'c', (Observation('CAM_C', 600_000, 'c:0', 0.85, frozenset(['red'])),
                             Observation('CAM_C', 800_000, 'c:1', 0.85, frozenset(['red'])))),
    ]
    edges = {('CAM_A', 'CAM_B'): 'AB', ('CAM_A', 'CAM_C'): 'AC'}
    _, events, audit = associate(tracks, edges, as_of_us=1_000_000, parameters=Parameters(), decider=decider)
    assert len(events) == 1 and events[0]['to_camera_id'] == 'CAM_C'
    assert events[0]['reason'] == 'AGENT_ASSOCIATION_HYPOTHESIS'
    assert len(transport.calls) == 1


# ------------------------------------------------------------------ 2. Timeouts, ROUND_LIMIT, TIME_BUDGET

def test_timeout_three_times_hits_round_limit():
    clock = FakeClock()
    transport = ScriptedTransport(
        (TimeoutError('timed out 1'), 1200.0),
        (socket.timeout('timed out 2'), 1200.0),
        (200, _openai_envelope(_select('C2')), 2100.0),  # late response > 2000 ms timeout
        clock=clock,
    )
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    record = ad.decide(
        _dp1(),
        mode='AGENT_LIVE',
        params=FORMAL,
        budget=budget,
        model='astra6',
        call=provider,
        provider_kind='OPENAI',
    )
    ad.validate_record(record)
    assert record['decision_source'] == 'RULE_FALLBACK'
    assert record['fallback_reason'] == 'ROUND_LIMIT'
    assert [a['outcome'] for a in record['attempts']] == ['PROVIDER_TIMEOUT', 'PROVIDER_TIMEOUT', 'PROVIDER_TIMEOUT']
    # Late response on attempt 3 is discarded, so response_sha256 is None
    assert all(a['response_sha256'] is None for a in record['attempts'])


def test_cumulative_wall_ms_over_5000_hits_time_budget():
    clock = FakeClock()
    transport = ScriptedTransport(
        (200, _openai_envelope(_select('C2')), 2500.0),
        (200, _openai_envelope(_select('C2')), 2600.0),
        clock=clock,
    )
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    record = ad.decide(
        _dp1(),
        mode='AGENT_LIVE',
        params=FORMAL,
        budget=budget,
        model='astra6',
        call=provider,
        provider_kind='OPENAI',
    )
    ad.validate_record(record)
    assert record['decision_source'] == 'RULE_FALLBACK'
    assert record['fallback_reason'] == 'TIME_BUDGET'
    assert len(record['attempts']) == 2
    assert [a['outcome'] for a in record['attempts']] == ['PROVIDER_TIMEOUT', 'PROVIDER_TIMEOUT']


# ------------------------------------------------------------------ 3. Malformed response & illegal candidate

@pytest.mark.parametrize('bad_payload', [
    b'not-json-at-all{{{',
    _openai_envelope({'action': 'SELECT', 'reason_codes': ['GRAPH_EDGE'], 'rationale': 'missing candidate_id'}),
    _openai_envelope({'action': 'SELECT', 'candidate_id': 'B1', 'reason_codes': ['UNKNOWN_CODE'], 'rationale': 'bad code'}),
    _openai_envelope({'action': 'SELECT', 'candidate_id': 'B1', 'reason_codes': ['GRAPH_EDGE'], 'rationale': 'ok', 'extra': 1}),
])
def test_malformed_response_falls_back_as_invalid_response(bad_payload):
    clock = FakeClock()
    transport = ScriptedTransport((200, bad_payload, 90.0), clock=clock)
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    record = ad.decide(
        _dp1(),
        mode='AGENT_LIVE',
        params=FORMAL,
        budget=budget,
        model='astra6',
        call=provider,
        provider_kind='OPENAI',
    )
    ad.validate_record(record)
    assert record['decision_source'] == 'RULE_FALLBACK'
    assert record['fallback_reason'] == 'INVALID_RESPONSE'
    assert record['attempts'][-1]['outcome'] == 'INVALID_RESPONSE'


def test_candidate_id_not_in_request_falls_back_as_illegal_candidate():
    clock = FakeClock()
    transport = ScriptedTransport((200, _openai_envelope(_select('Z9')), 80.0), clock=clock)
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    record = ad.decide(
        _dp1(),
        mode='AGENT_LIVE',
        params=FORMAL,
        budget=budget,
        model='astra6',
        call=provider,
        provider_kind='OPENAI',
    )
    ad.validate_record(record)
    assert record['decision_source'] == 'RULE_FALLBACK'
    assert record['fallback_reason'] == 'ILLEGAL_CANDIDATE'
    assert record['attempts'][-1]['outcome'] == 'ILLEGAL_CANDIDATE'


# ------------------------------------------------------------------ 4. Unreachable & 429/5xx retry policy

def test_unreachable_and_429_5xx_retry_policy():
    clock = FakeClock()
    # 1) Unreachable connection error -> PROVIDER_UNAVAILABLE
    t_unavail = ScriptedTransport(ConnectionError('connection refused'), clock=clock)
    p_unavail = OpenAIProvider(
        model='astra6', params=FORMAL, transport=t_unavail,
        env={'OPENAI_API_KEY': FAKE_KEY}, clock_ms=clock.now_ms, sleep_ms=clock.sleep_ms,
    )
    rec1 = ad.decide(
        _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=CallBudget(FORMAL, STAGE),
        model='astra6', call=p_unavail, provider_kind='OPENAI',
    )
    assert rec1['fallback_reason'] == 'PROVIDER_UNAVAILABLE'
    assert len(t_unavail.calls) == 1

    # 2) 429 or 503 once then success -> AGENT (2 attempts)
    for err_status in (429, 503):
        t_retry_ok = ScriptedTransport(
            _http_error(err_status),
            (200, _openai_envelope(_select('C2')), 100.0),
            clock=clock,
        )
        p_retry_ok = OpenAIProvider(
            model='astra6', params=FORMAL, transport=t_retry_ok,
            env={'OPENAI_API_KEY': FAKE_KEY}, clock_ms=clock.now_ms, sleep_ms=clock.sleep_ms,
        )
        rec_ok = ad.decide(
            _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=CallBudget(FORMAL, STAGE),
            model='astra6', call=p_retry_ok, provider_kind='OPENAI',
        )
        assert rec_ok['decision_source'] == 'AGENT' and rec_ok['final_answer'] == 'C2'
        assert [a['outcome'] for a in rec_ok['attempts']] == ['PROVIDER_RETRYABLE_ERROR', 'OK']
        assert len(t_retry_ok.calls) == 2

    # 3) 429 twice -> PROVIDER_UNAVAILABLE, and adapter makes zero extra retries on its own
    t_retry_fail = ScriptedTransport(_http_error(429), _http_error(429), _http_error(429), clock=clock)
    p_retry_fail = OpenAIProvider(
        model='astra6', params=FORMAL, transport=t_retry_fail,
        env={'OPENAI_API_KEY': FAKE_KEY}, clock_ms=clock.now_ms, sleep_ms=clock.sleep_ms,
    )
    rec_fail = ad.decide(
        _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=CallBudget(FORMAL, STAGE),
        model='astra6', call=p_retry_fail, provider_kind='OPENAI',
    )
    assert rec_fail['decision_source'] == 'RULE_FALLBACK'
    assert rec_fail['fallback_reason'] == 'PROVIDER_UNAVAILABLE'
    assert len(rec_fail['attempts']) == 2
    assert len(t_retry_fail.calls) == 2  # strictly 2 calls (initial + 1 retry controlled by decide())


# ------------------------------------------------------------------ 5. All budget cap layers

@pytest.mark.parametrize('expected_layer,mutate', [
    ('SESSION_ROUNDS', lambda p: p['per_session'].update(max_rounds=1)),
    ('MODEL_CALLS', lambda p: p['stages'][STAGE].update(per_model_max_calls=1)),
    ('MODEL_TOKENS', lambda p: p['stages'][STAGE].update(per_model_max_tokens=1800)),
    ('STAGE_CALLS', lambda p: p['stages'][STAGE].update(max_calls=1)),
    ('STAGE_TOKENS', lambda p: p['stages'][STAGE].update(max_tokens=1800)),
    (
        'TOTAL_USD',
        lambda p: p.update(
            budget_usd=0.002,
            price_table={
                'date': '2026-11-10',
                'source': 'FAKE_TEST_PRICE_TABLE_FIXTURE',
                'currency': 'USD',
                'models': {m: {'input_usd_per_mtok': 1.0, 'output_usd_per_mtok': 1.0} for m in ad.MODELS},
            },
        ),
    ),
])
def test_every_budget_cap_layer_exhaustion_stops_transport_calls(expected_layer, mutate):
    params = copy.deepcopy(FORMAL)
    mutate(params)
    clock = FakeClock()
    transport = ScriptedTransport(
        (200, _openai_envelope(_select('C2'), prompt_tokens=1500, completion_tokens=300), 50.0),
        (200, _openai_envelope(_select('C2'), prompt_tokens=1500, completion_tokens=300), 50.0),
        (200, _openai_envelope(_select('C2'), prompt_tokens=1500, completion_tokens=300), 50.0),
        clock=clock,
    )
    budget = CallBudget(params, STAGE)
    budget.begin_session()
    provider = OpenAIProvider(
        model='astra6',
        params=params,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    first = ad.decide(
        _dp1(), mode='AGENT_LIVE', params=params, budget=budget,
        model='astra6', call=provider, provider_kind='OPENAI',
    )
    assert first['decision_source'] == 'AGENT'
    assert len(transport.calls) == 1

    # Next two steps must hit CALL_BUDGET_EXHAUSTED with the exact layer and never invoke transport
    for _ in range(2):
        later = ad.decide(
            _dp1(), mode='AGENT_LIVE', params=params, budget=budget,
            model='astra6', call=provider, provider_kind='OPENAI',
        )
        ad.validate_record(later)
        assert later['decision_source'] == 'RULE_FALLBACK'
        assert later['fallback_reason'] == 'CALL_BUDGET_EXHAUSTED'
        assert later['budget_layer'] == expected_layer
        assert later['attempts'] == []
    assert len(transport.calls) == 1


# ------------------------------------------------------------------ 6. Rate limiting & max_concurrent=1

def test_rate_limit_delays_31st_request_in_same_minute_and_enforces_single_concurrency(monkeypatch):
    monkeypatch.setattr(time, 'sleep', lambda *_: pytest.fail('real time.sleep must not be called'))
    clock = FakeClock(initial_ms=0.0)
    budget = CallBudget(FORMAL, STAGE)
    in_flight_seen: list[bool] = []

    def transport_fn(*, url, headers, body, timeout_s):
        in_flight_seen.append(budget._in_flight)
        # Attempting a second concurrent call while one is in flight must raise RATE_INVALID
        if len(in_flight_seen) == 1:
            with pytest.raises(AgentDecisionError, match='RATE_INVALID'):
                provider.call(_dp1(), timeout_ms=2000, max_output_tokens=300)
        clock.advance_ms(10.0)
        return 200, _openai_envelope(_select('C2'))

    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport_fn,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )

    for i in range(30):
        budget.begin_session()
        rec = ad.decide(
            _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=budget,
            model='astra6', call=provider, provider_kind='OPENAI',
        )
        assert rec['decision_source'] == 'AGENT'
        clock.advance_ms(90.0)  # 100 ms per request -> 30 requests take 3000 ms (< 60,000 ms)

    assert clock.slept_ms == []
    assert clock.now_ms() == 3000.0

    # 31st request within the same minute must wait 60_000 - 3000 = 57_000 ms on the fake clock
    budget.begin_session()
    rec31 = ad.decide(
        _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=budget,
        model='astra6', call=provider, provider_kind='OPENAI',
    )
    assert rec31['decision_source'] == 'AGENT'
    assert clock.slept_ms == [57_000]
    assert clock.now_ms() == 60_010.0
    assert all(in_flight_seen) and not budget._in_flight


# ------------------------------------------------------------------ 7. Unapproved stage calls transport 0 times

def test_unapproved_stage_in_agent_live_calls_transport_zero_times():
    clock = FakeClock()
    transport = ScriptedTransport((200, _openai_envelope(_select('C2'))), clock=clock)
    budget = CallBudget(FORMAL, 'FORMAL')  # approved=false
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    record = ad.decide(
        _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=budget,
        model='astra6', call=provider, provider_kind='OPENAI',
    )
    assert record['decision_source'] == 'RULE_FALLBACK'
    assert record['fallback_reason'] == 'MODE_NOT_AUTHORIZED'
    assert len(transport.calls) == 0


# ------------------------------------------------------------------ 8. API key header & zero-leak guarantee

def test_openai_api_key_in_authorization_header_and_never_leaked(tmp_path, caplog):
    clock = FakeClock()
    rec_file = tmp_path / 'recorded.jsonl'
    env = {'OPENAI_API_KEY': FAKE_KEY}
    recorder = JSONLRecorder(rec_file, env=env)
    transport = ScriptedTransport(
        (200, _openai_envelope(_select('C2')), 100.0),
        RuntimeError(f'boom without leaking {FAKE_KEY[:4]}'),
        clock=clock,
    )
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env=env,
        budget=budget,
        recorder=recorder,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )

    with caplog.at_level(logging.DEBUG):
        rec_ok = ad.decide(
            _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=budget,
            model='astra6', call=provider, provider_kind='OPENAI',
        )
        rec_err = ad.decide(
            _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=budget,
            model='astra6', call=provider, provider_kind='OPENAI',
        )

    assert rec_ok['decision_source'] == 'AGENT'
    assert rec_err['fallback_reason'] == 'PROVIDER_UNAVAILABLE'
    assert transport.calls[0]['headers']['Authorization'] == f'Bearer {FAKE_KEY}'

    assert FAKE_KEY not in repr(provider) and FAKE_KEY not in str(provider)
    assert FAKE_KEY not in repr(recorder) and FAKE_KEY not in str(recorder)
    assert FAKE_KEY not in caplog.text
    assert FAKE_KEY not in rec_file.read_text(encoding='utf-8')
    assert FAKE_KEY not in json.dumps(rec_ok) and FAKE_KEY not in json.dumps(rec_err)


def test_missing_openai_api_key_returns_unavailable_without_raising():
    clock = FakeClock()
    transport = ScriptedTransport((200, _openai_envelope(_select('C2'))), clock=clock)
    budget = CallBudget(FORMAL, STAGE)
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=transport,
        env={},  # no OPENAI_API_KEY
        budget=budget,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    record = ad.decide(
        _dp1(), mode='AGENT_LIVE', params=FORMAL, budget=budget,
        model='astra6', call=provider, provider_kind='OPENAI',
    )
    ad.validate_record(record)
    assert record['decision_source'] == 'RULE_FALLBACK'
    assert record['fallback_reason'] == 'PROVIDER_UNAVAILABLE'
    assert [a['outcome'] for a in record['attempts']] == ['PROVIDER_UNAVAILABLE']
    assert len(transport.calls) == 0


# ------------------------------------------------------------------ 9. Ollama loopback & format schema

@pytest.mark.parametrize('bad_endpoint', [
    'http://192.168.1.10:11434',
    'http://10.0.0.1:11434',
    'http://0.0.0.0:11434',
    'http://example.com:11434',
    'https://127.0.0.1:11434',
    'http://user:pass@127.0.0.1:11434',
    'http://127.0.0.1:11434/v1',
])
def test_ollama_rejects_non_loopback_endpoints(bad_endpoint):
    with pytest.raises(AgentDecisionError, match='OLLAMA_ENDPOINT_INVALID'):
        OllamaProvider(model='qwen3:1.7b-q4_K_M', endpoint=bad_endpoint)


def test_ollama_loopback_sends_response_schema_and_records_model_digest(tmp_path):
    clock = FakeClock()
    fake_digest = '3d0b7905' + 'a' * 56
    tags_resp = json.dumps({'models': [{'name': 'qwen3:1.7b-q4_K_M', 'digest': f'sha256:{fake_digest}'}]}).encode('utf-8')
    chat_resp = json.dumps({
        'model': 'qwen3:1.7b-q4_K_M',
        'done': True,
        'message': {'role': 'assistant', 'content': json.dumps(_select('C2'))},
        'prompt_eval_count': 800,
        'eval_count': 35,
    }).encode('utf-8')
    transport = ScriptedTransport((200, tags_resp), (200, chat_resp, 240.0), clock=clock)
    recorder = JSONLRecorder(tmp_path / 'ollama.jsonl')

    # Test-only parameter set fixture mapping config_id 'astra6' for decide() authorization
    test_params = copy.deepcopy(FORMAL)
    budget = CallBudget(test_params, STAGE)
    provider = OllamaProvider(
        model='qwen3:1.7b-q4_K_M',
        endpoint='http://127.0.0.1:11434',
        transport=transport,
        budget=budget,
        recorder=recorder,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    assert provider.fetch_model_digest() == fake_digest

    record = ad.decide(
        _dp1(),
        mode='AGENT_LIVE',
        params=test_params,
        budget=budget,
        model='astra6',
        call=provider,
        provider_kind='OLLAMA_LOOPBACK',
        provider_meta=provider.provider_meta(),
    )
    ad.validate_record(record)
    assert record['decision_source'] == 'AGENT'
    assert record['final_answer'] == 'C2'
    assert record['provider']['kind'] == 'OLLAMA_LOOPBACK'
    assert record['provider']['model_digest'] == fake_digest

    chat_call = transport.calls[1]
    assert chat_call['url'] == 'http://127.0.0.1:11434/api/chat'
    assert chat_call['body']['format'] == SCHEMA['$defs']['response']
    entries = recorder.entries()
    assert len(entries) == 1 and entries[0]['model_digest'] == fake_digest


# ------------------------------------------------------------------ 10. Static isolation & default OFF check

def test_static_only_wp3_files_import_new_modules_and_default_off_unchanged():
    wp3_files = {
        ROOT / 'src/amidst/q1q5/agent_providers.py',
        ROOT / 'src/amidst/q1q5/agent_recording.py',
        ROOT / 'scripts/agent_decision/run_provider.py',
    }
    pattern = re.compile(r'\b(?:agent_providers|agent_recording)\b')
    offenders = []
    for folder in ('src', 'scripts'):
        for path in (ROOT / folder).rglob('*.py'):
            if path in wp3_files:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                names = (
                    [a.name for a in node.names] if isinstance(node, ast.Import) else
                    [node.module or ''] + [a.name for a in node.names] if isinstance(node, ast.ImportFrom) else []
                )
                if any(pattern.search(n) for n in names):
                    offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []

    # Verify default mode OFF leaves associate() and response() outputs untouched
    assert ad.DEFAULT_MODE == 'OFF'
    tracks = [
        Track('CAM_A', 'a', (Observation('CAM_A', 0, 'a:0', 0.7, frozenset(['red'])),)),
        Track('CAM_B', 'b', (Observation('CAM_B', 400_000, 'b:0', 0.7, frozenset(['red'])),)),
    ]
    edges = {('CAM_A', 'CAM_B'): 'AB'}
    base_out = response(tracks, edges, as_of_us=800_000, parameters=Parameters(), clock_mapping_sha256='a' * 64)
    off_decider = AgentDecider(params=FORMAL)
    with_off = response(
        tracks, edges, as_of_us=800_000, parameters=Parameters(),
        clock_mapping_sha256='a' * 64, decider=off_decider,
    )
    assert base_out == with_off
    assert ap.RESPONSE_SCHEMA == SCHEMA['$defs']['response']

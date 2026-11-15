"""WP5 v3 fixes (2026-11-16): response repair + debug fields, NL agreement metric, GPU residency sampling, ledger tokens.
No network, no key, no Ollama (fake transports)."""
import importlib
import json
import urllib.error

import pytest

wp5 = importlib.import_module('amidst.agent_eval.wp5')
fake = importlib.import_module('amidst.agent_eval.wp5_fake')
runner = importlib.import_module('amidst.agent_eval.wp5_runner')
chk = importlib.import_module('amidst.agent_eval.wp5_colab_checks')
ap = importlib.import_module('amidst.q1q5.agent_providers')
ab = importlib.import_module('amidst.q1q5.api_budget')
ad = importlib.import_module('amidst.q1q5.agent_decision')


def _ollama_reply(content, **extra):
    def transport(*, url, headers, body=None, timeout_s=2.0, **kw):
        text = content if isinstance(content, str) else json.dumps(content)
        return 200, json.dumps({'message': {'content': text}, 'prompt_eval_count': 300, 'eval_count': 40, **extra}).encode()
    return transport


def _call(content, req=None):
    p = ap.OllamaProvider(model='qwen2.5:7b-instruct-q4_K_M', transport=_ollama_reply(content))
    return p, p.call(req or fake.dp1_request(0), timeout_ms=2000, max_output_tokens=300)


# ---- 1. INVALID_RESPONSE: repair of the constraints the model-facing schema cannot express ---------------------------
@pytest.mark.parametrize('bad,note', [
    ({'action': 'ABSTAIN', 'candidate_id': '', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x'}, 'DROPPED_CANDIDATE_ID_NON_SELECT'),
    ({'action': 'ABSTAIN', 'candidate_id': 'B1', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x'}, 'DROPPED_CANDIDATE_ID_NON_SELECT'),
    ({'action': 'ABSTAIN', 'reason_codes': ['LOW_SCORE', 'LOW_SCORE'], 'rationale': 'x'}, 'DEDUPED_REASON_CODES'),
])
def test_repairable_reply_becomes_valid_and_is_flagged(bad, note):
    req = fake.dp1_request(0)
    with pytest.raises(ad.AgentDecisionError):
        ad.validate_response(bad, req)                      # the raw reply really is INVALID_RESPONSE
    p, attempt = _call(bad, req)
    assert ad.validate_response(attempt.response, req) == 'ABSTAIN'
    assert p.last_diag['normalized'] == [note]
    assert p.last_diag['invalid_before_repair'].startswith('INVALID_RESPONSE') and p.last_diag['invalid_after_repair'] is None
    assert p.last_diag['raw_head'].startswith('{')


@pytest.mark.parametrize('bad', [
    {'action': 'SELECT', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x'},                          # SELECT without id
    {'action': 'SELECT', 'candidate_id': '', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x'},      # empty id with SELECT
    {'action': 'ABSTAIN', 'reason_codes': ['MADE_UP'], 'rationale': 'x'},                           # bad enum
    {'action': 'ABSTAIN', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x', 'extra': 1},             # extra key
    {'action': 'ABSTAIN', 'reason_codes': [], 'rationale': 'x'},
])
def test_unrepairable_reply_stays_invalid_with_reason(bad):
    req = fake.dp1_request(0)
    p, attempt = _call(bad, req)
    with pytest.raises(ad.AgentDecisionError):
        ad.validate_response(attempt.response, req)
    assert p.last_diag['invalid_after_repair'].startswith('INVALID_RESPONSE')


def test_raw_head_is_model_output_only_and_truncated():
    long_reply = {'action': 'ABSTAIN', 'reason_codes': ['LOW_SCORE'], 'rationale': 'y' * 1000}
    req = fake.dp1_request(0)
    p, _ = _call(long_reply, req)
    head = p.last_diag['raw_head']
    assert len(head) == ap.RAW_HEAD_CHARS and 'current' not in head and 'candidates' not in head
    assert p.last_diag['invalid_before_repair'].endswith('rationale')


def test_non_json_reply_is_reported_not_raised():
    p, attempt = _call('here is my answer: ABSTAIN')
    assert attempt.response is None
    assert p.last_diag['raw_head'] == 'here is my answer: ABSTAIN' and p.last_diag['invalid_after_repair'] == 'NO_JSON_OBJECT'


def test_execute_call_row_carries_debug_fields_and_decide_uses_repaired_answer():
    cfg = wp5.load_config()
    reply = {'action': 'ABSTAIN', 'candidate_id': '', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x'}
    prov = ap.OllamaProvider(model='qwen2.5:7b-instruct-q4_K_M', transport=_ollama_reply(reply))
    ctx = wp5.Context(decision_provider=lambda m: prov.call, dp4_ranker=None, nl_client=None, price_table={})
    rows = wp5.run_set(ctx, cfg, 'pilot', wp5.select_questions(fake.synthetic_rows(2), {'DP1': 1}), guard=wp5.LocalCapGuard(max_usd=None),
                       models=['qwen2.5:7b-instruct-q4_K_M'], types=['DP1'], approval_ref='TEST')
    r = rows[0]
    assert r['decision_source'] == 'AGENT' and r['normalized'] == ['DROPPED_CANDIDATE_ID_NON_SELECT']
    assert r['invalid_before_repair'].startswith('INVALID_RESPONSE') and r['invalid_after_repair'] is None and r['raw_head']


def test_openai_provider_exposes_http_error_and_diag():
    def transport(*, url, headers, body=None, timeout_s=2.0, **kw):
        raise urllib.error.HTTPError(url, 400, 'Bad', {}, _Body(b'{"error":"nope"}'))
    p = ap.OpenAIProvider(model='terra6.1', api_model_id='gpt-6.1-terra', transport=transport, env={'OPENAI_API_KEY': 'sk-test-FAKE'})
    assert p.call(fake.dp1_request(0), timeout_ms=2000, max_output_tokens=300).outcome == ad.CALL_UNAVAILABLE
    assert p.last_error['http_status'] == 400 and 'nope' in p.last_error['detail'] and p.last_diag is None
    body = {'choices': [{'message': {'content': json.dumps({'action': 'ABSTAIN', 'candidate_id': '', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x'})}}],
            'usage': {'prompt_tokens': 594, 'completion_tokens': 116}}
    p2 = ap.OpenAIProvider(model='terra6.1', api_model_id='gpt-6.1-terra', transport=lambda **kw: (200, json.dumps(body).encode()),
                           env={'OPENAI_API_KEY': 'sk-test-FAKE'})
    a = p2.call(fake.dp1_request(0), timeout_ms=2000, max_output_tokens=300)
    assert ad.validate_response(a.response, fake.dp1_request(0)) == 'ABSTAIN' and p2.last_diag['normalized'] == ['DROPPED_CANDIDATE_ID_NON_SELECT']
    assert (a.prompt_tokens, a.completion_tokens) == (594, 116)


class _Body:
    def __init__(self, b):
        self._b = b

    def read(self, *a):
        return self._b

    def close(self):
        pass


# ---- 3. NL agreement metric -------------------------------------------------------------------------------------------
RULE = {'action': '追蹤', 'location': ['R2'], 'target': ['person', 'blue'], 'time': None, 'unrecognized': ['第37段']}


def test_nl_agreement_ignores_unrecognized_and_order():
    ans = dict(RULE, target=['blue', 'person'], unrecognized=['追蹤藍衣的人 從大廳 第37段'])
    ok, per = wp5.nl_agreement(ans, RULE)
    assert ok and all(per.values()) and set(per) == {'action', 'location', 'target', 'time'}


def test_nl_agreement_reports_which_field_differs():
    ok, per = wp5.nl_agreement(dict(RULE, target=['person'], action='查找'), RULE)   # what both Colab models did
    assert not ok and per == {'action': False, 'location': True, 'target': False, 'time': True}


# ---- 2. GPU residency while loaded ----------------------------------------------------------------------------------
HEADER = 'NAME    ID    SIZE    PROCESSOR    CONTEXT    RUNNER    UNTIL'
M = 'qwen2.5:7b-instruct-q4_K_M'


def test_gpu_sampling_retries_past_header_only_ps_and_parses_processor():
    seq = iter([HEADER, HEADER, f'{HEADER}\n{M}  845dbda0  5.6 GB  100% GPU  4096  ollama runner  4 minutes from now'])
    out = chk.sample_gpu_residency(M, cli_ps=lambda: next(seq), api_ps=lambda: {'models': []}, sleep=lambda s: None)
    assert out['ok'] and out['gpu_percent'] == 100 and out['source'] == 'ollama ps' and out['n_samples'] == 3


def test_gpu_sampling_header_only_is_not_ok_and_keeps_samples():
    out = chk.sample_gpu_residency(M, cli_ps=lambda: HEADER, api_ps=lambda: {'models': []}, tries=3, sleep=lambda s: None)
    assert not out['ok'] and out['gpu_percent'] is None and out['n_samples'] == 3 and out['samples'][0]['cli_text'] == HEADER


def test_gpu_sampling_cpu_split_is_not_ok():
    line = f'{HEADER}\n{M}  845d  9 GB  35%/65% CPU/GPU  4096  r  4 minutes from now'
    out = chk.sample_gpu_residency(M, cli_ps=lambda: line, api_ps=lambda: {'models': []}, tries=2, sleep=lambda s: None)
    assert not out['ok'] and out['gpu_percent'] == 65


def test_api_ps_is_a_second_source():
    doc = {'models': [{'name': M, 'size': 6_000_000_000, 'size_vram': 6_000_000_000}]}
    out = chk.sample_gpu_residency(M, cli_ps=lambda: HEADER, api_ps=lambda: doc, sleep=lambda s: None)
    assert out['ok'] and out['source'] == '/api/ps' and out['gpu_percent'] == 100
    half = {'models': [{'name': M, 'size': 100, 'size_vram': 40}]}
    assert chk.gpu_from_api_ps(half, M)['gpu_percent'] == 40 and not chk.gpu_from_api_ps(half, M)['ok']


def test_sampling_runs_while_the_request_is_in_flight():
    state = {'busy': False}
    import threading
    started, release = threading.Event(), threading.Event()

    def during():
        state['busy'] = True
        started.set()
        release.wait(5)
        state['busy'] = False
        return {'ok': True}

    def cli():
        started.wait(5)
        assert state['busy']       # sampled while the request has not finished
        release.set()
        return f'{HEADER}\n{M}  d  5 GB  100% GPU  4096  r  1 minute from now'
    out = chk.sample_gpu_residency(M, cli_ps=cli, api_ps=lambda: {}, during=during, sleep=lambda s: None)
    assert out['ok'] and out['during_result'] == {'ok': True}


# ---- 4. ledger tokens -------------------------------------------------------------------------------------------------
def _guard(tmp_path):
    table = wp5.load_json('configs/agent_eval/wp5_price_table_v1.json')
    return ab.ApiGuard(ab.GuardConfig(enabled=True, max_usd_total=3, max_usd_per_day=3, max_calls_per_day=60, max_calls_per_min=100,
                                      prices=runner.wp5_prices(table)), usage_dir=tmp_path)


def _rows(g):
    return [json.loads(ln) for ln in g.ledger_path.read_text().splitlines()]


def test_ledger_records_tokens_of_answered_call(tmp_path):
    cfg, g = wp5.load_config(), _guard(tmp_path)
    body = {'choices': [{'message': {'content': json.dumps({'action': 'ABSTAIN', 'reason_codes': ['LOW_SCORE'], 'rationale': 'x'})}}],
            'usage': {'prompt_tokens': 594, 'completion_tokens': 116}}
    p = ap.OpenAIProvider(model='terra6.1', api_model_id='gpt-6.1-terra', transport=lambda **kw: (200, json.dumps(body).encode()), env={'OPENAI_API_KEY': 'sk-test-FAKE'})
    call = runner.guarded_decision_call(g, cfg, wp5.model_by_id(cfg, 'terra6.1'), p.call)
    assert call.provider is p
    call(fake.dp1_request(0), timeout_ms=2000, max_output_tokens=300)
    r = _rows(g)[0]
    assert (r['prompt_tokens'], r['completion_tokens']) == (594, 116) and r['est_cost_usd'] == pytest.approx((594 * 1 + 116 * 5) / 1e6, rel=1e-3)


def test_ledger_records_zero_for_http_400_rejection_not_worst_case(tmp_path):
    cfg, g = wp5.load_config(), _guard(tmp_path)

    def transport(*, url, headers, body=None, timeout_s=2.0, **kw):
        raise urllib.error.HTTPError(url, 400, 'Bad', {}, _Body(b'{}'))
    p = ap.OpenAIProvider(model='terra6.1', api_model_id='gpt-6.1-terra', transport=transport, env={'OPENAI_API_KEY': 'sk-test-FAKE'})
    runner.guarded_decision_call(g, cfg, wp5.model_by_id(cfg, 'terra6.1'), p.call)(fake.dp1_request(0), timeout_ms=2000, max_output_tokens=300)
    r = _rows(g)[0]
    assert (r['prompt_tokens'], r['completion_tokens'], r['est_cost_usd']) == (0, 0, 0.0)


def test_ledger_charges_worst_case_when_status_is_429_or_timeout(tmp_path):
    cfg, g = wp5.load_config(), _guard(tmp_path)

    def transport(*, url, headers, body=None, timeout_s=2.0, **kw):
        raise urllib.error.HTTPError(url, 429, 'Slow', {}, _Body(b'{}'))
    p = ap.OpenAIProvider(model='terra6.1', api_model_id='gpt-6.1-terra', transport=transport, env={'OPENAI_API_KEY': 'sk-test-FAKE'})
    runner.guarded_decision_call(g, cfg, wp5.model_by_id(cfg, 'terra6.1'), p.call)(fake.dp1_request(0), timeout_ms=2000, max_output_tokens=300)
    r = _rows(g)[0]
    assert r['prompt_tokens'] is None and r['est_cost_usd'] > 0

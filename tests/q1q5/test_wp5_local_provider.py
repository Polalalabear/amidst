"""WP5 local-model arm: DP1/DP3/NL must all reach the (fake) Ollama, and a never-called model type is a FAILED run.

Regression for the Colab L4 pilot v1 (2026-11-15): DP1/DP3 were 100% PROVIDER_UNAVAILABLE in ~35 ms (the model was never
called) because the ``format`` schema sent to Ollama still held a dangling ``$ref``. The fake below is strict in the same
way: it answers HTTP 400 when ``format`` contains ``$ref``. No network, no key, no real Ollama."""
import importlib
import json
import urllib.error

import pytest

wp5 = importlib.import_module('amidst.agent_eval.wp5')
fake = importlib.import_module('amidst.agent_eval.wp5_fake')
runner = importlib.import_module('amidst.agent_eval.wp5_runner')
ap = importlib.import_module('amidst.q1q5.agent_providers')
nlp = importlib.import_module('amidst.q1q5.nl_query_parse')

MODEL = 'qwen2.5:7b-instruct-q4_K_M'


def _nl_answers(rows):
    out = {}
    for r in rows:
        if r['task_type'] == 'NL':
            q = wp5.normalize_question(r)
            out[r['text']] = nlp.parse_rules(q['text'], q['vocab'])
    return out


class StrictFakeOllama:
    def __init__(self, rows):
        self.nl, self.calls = _nl_answers(rows), []

    def __call__(self, *, url, headers, body=None, timeout_s=2.0, **kw):
        if url.endswith('/api/tags'):
            return 200, json.dumps({'models': []}).encode()
        payload = json.loads(body)
        if '$ref' in json.dumps(payload['format']):
            raise urllib.error.HTTPError(url, 400, 'Bad Request', {}, _Body(b'{"error":"invalid JSON schema in format"}'))
        user = payload['messages'][-1]['content']
        if 'reason_codes' in payload['format'].get('properties', {}):
            req = json.loads(user)
            self.calls.append(req['decision_point'])
            answer = {'action': req['rule_answer'] if req['rule_answer'] in ('ABSTAIN', 'ACCEPT_SEGMENT', 'REJECT_SEGMENT') else 'SELECT',
                      'reason_codes': ['HIGH_SCORE'], 'rationale': 'fake'}
            if answer['action'] == 'SELECT':
                answer['candidate_id'] = req['rule_answer']
        else:
            self.calls.append('NL')
            answer = self.nl[json.loads(user)['text']]
        return 200, json.dumps({'message': {'content': json.dumps(answer)}, 'prompt_eval_count': 280, 'eval_count': 70}).encode()


class _Body:
    def __init__(self, b):
        self._b = b

    def read(self, *a):
        return self._b

    def close(self):
        pass


def _questions(tmp_path):
    rows = fake.synthetic_rows(4)
    q = tmp_path / 'q.jsonl'
    q.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    return q, rows


def _run(tmp_path, arm='colab_l4'):
    q, rows = _questions(tmp_path)
    t = StrictFakeOllama(rows)
    out = tmp_path / 'out'
    return t, out, q


def test_response_schema_sent_to_ollama_is_self_contained():
    assert '$ref' in json.dumps(ap.RESPONSE_SCHEMA)          # the contract slice really is dangling
    fmt = ap.OllamaProvider(model=MODEL)._response_schema
    text = json.dumps(fmt)
    assert '$ref' not in text and '"if"' not in text and 'uniqueItems' not in text
    assert fmt['properties']['candidate_id']['pattern'] == '^[A-Z]{1,2}[0-9]{1,3}$'
    assert fmt['required'] == ['action', 'reason_codes', 'rationale']


@pytest.mark.parametrize('arm', ['colab_l4', 'windows'])
def test_local_arm_calls_provider_for_dp1_dp3_and_nl(tmp_path, monkeypatch, arm):
    t, out, q = _run(tmp_path)
    monkeypatch.setattr(ap, 'default_http_transport', t)
    rc = runner.main(['--set', 'pilot', '--live', '--arm', arm, '--questions', str(q), '--models', MODEL, '--skip-types', 'DP4',
                      '--out', str(out)])
    assert rc == 0
    rows = [json.loads(x) for x in (out / 'calls.jsonl').read_text(encoding='utf-8').splitlines()]
    assert {r['task_type'] for r in rows} == {'DP1', 'DP3', 'NL'}
    for typ in ('DP1', 'DP3', 'NL'):
        rs = [r for r in rows if r['task_type'] == typ]
        assert rs and all(r['decision_source'] == ('LOCAL' if typ == 'NL' else 'AGENT') for r in rs), typ  # DP success is AGENT (ad.decide), NL is LOCAL
        assert all(r['fallback_reason'] is None and r['prompt_tokens'] == 280 for r in rs), typ
    assert len(t.calls) == 3 * 4 * 6 and 'NL' in t.calls and sum(c != 'NL' for c in t.calls) == 2 * 4 * 6   # 4 questions x 6 rounds x 3 types, one call each
    summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'OK' and summary['failures'] == []


def test_dp_type_never_reaching_the_provider_is_a_failed_run(tmp_path, monkeypatch, capsys):
    q, rows = _questions(tmp_path)
    good = StrictFakeOllama(rows)

    def only_nl(*, url, headers, body=None, timeout_s=2.0, **kw):
        if body and 'reason_codes' in json.loads(body)['format'].get('properties', {}):
            raise urllib.error.HTTPError(url, 400, 'Bad Request', {}, _Body(b'{"error":"schema"}'))
        return good(url=url, headers=headers, body=body, timeout_s=timeout_s)

    monkeypatch.setattr(ap, 'default_http_transport', only_nl)
    out = tmp_path / 'bad'
    rc = runner.main(['--set', 'pilot', '--live', '--arm', 'colab_l4', '--questions', str(q), '--models', MODEL, '--skip-types', 'DP4',
                      '--out', str(out)])
    assert rc == 3
    summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'FAILED'
    assert any('DP1' in m and '100% PROVIDER_UNAVAILABLE' in m and '400' in m for m in summary['failures'])
    assert any('DP3' in m for m in summary['failures']) and not any(' NL' in m for m in summary['failures'])
    assert json.loads((out / 'MANIFEST.json').read_text())['status'] == 'FAILED'
    assert 'RUN FAILED' in capsys.readouterr().err
    assert (out / 'summary.md').read_text(encoding='utf-8').startswith('**RUN FAILED')


def _cell(t, n, unavailable, other=0):
    return {'report_group': 'FORMAL', 'model': MODEL, 'task_type': t, 'n_ok': n, 'provider_unavailable_rate': unavailable / n,
            'fallback_rate': (unavailable + other) / n, 'fallback_reasons': {}, 'provider_error_sample': None}


def test_partial_fallback_is_a_warning_not_a_failure():
    failures, warnings = wp5.health_check([_cell('DP1', 10, 3), _cell('DP3', 10, 1), _cell('NL', 10, 0)])
    assert failures == [] and len(warnings) == 1 and 'DP1' in warnings[0]
    failures, _ = wp5.health_check([_cell('DP1', 10, 10)])
    assert len(failures) == 1


# ---- notebook helper checks (wp5_colab_checks) ----
PS = """NAME                          ID              SIZE      PROCESSOR    UNTIL
qwen2.5:7b-instruct-q4_K_M    845dbda0ea48    5.1 GB    100% GPU     4 minutes from now
llama3.1:8b-instruct-q4_K_M   46e0c10c039e    6.0 GB    48%/52% CPU/GPU    4 minutes from now
"""


def test_ollama_ps_gpu_residency():
    chk = importlib.import_module('amidst.agent_eval.wp5_colab_checks')
    assert chk.gpu_residency(PS, MODEL)['ok'] is True
    split = chk.gpu_residency(PS, 'llama3.1:8b-instruct-q4_K_M')
    assert split['ok'] is False and split['gpu_percent'] == 52
    assert chk.gpu_residency('NAME ID\n', MODEL)['ok'] is False                      # not listed -> not ok
    assert chk.gpu_residency('NAME\nx:1  a  1 GB  100% CPU  now\n', 'x:1')['gpu_percent'] == 0


def test_probe_dp1_reports_http_status_when_the_provider_fails(monkeypatch):
    chk = importlib.import_module('amidst.agent_eval.wp5_colab_checks')

    def bad(*, url, headers, body=None, timeout_s=2.0, **kw):
        raise urllib.error.HTTPError(url, 400, 'Bad Request', {}, _Body(b'{"error":"invalid JSON schema in format"}'))
    monkeypatch.setattr(ap, 'default_http_transport', bad)
    res = chk.probe_dp1(MODEL)
    assert res['ok'] is False and res['outcome'] == 'UNAVAILABLE' and res['http_status'] == 400 and 'invalid JSON schema' in res['detail']
    monkeypatch.setattr(ap, 'default_http_transport', StrictFakeOllama(fake.synthetic_rows(1)))
    assert chk.probe_dp1(MODEL)['ok'] is True


def test_fallback_report_flags_types_over_threshold(tmp_path):
    chk = importlib.import_module('amidst.agent_eval.wp5_colab_checks')
    rows = [{'outcome': 'OK', 'model_kind': 'LOCAL', 'task_type': 'DP1', 'decision_source': 'RULE_FALLBACK', 'fallback_reason': 'PROVIDER_UNAVAILABLE'}] * 4
    rows += [{'outcome': 'OK', 'model_kind': 'LOCAL', 'task_type': 'DP3', 'decision_source': 'AGENT', 'fallback_reason': None}] * 3
    rows += [{'outcome': 'OK', 'model_kind': 'LOCAL', 'task_type': 'DP3', 'decision_source': 'RULE_FALLBACK', 'fallback_reason': 'TIMEOUT'}]
    p = tmp_path / 'calls.jsonl'
    p.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    rep = chk.fallback_report(p)
    assert rep['never_called'] == ['DP1'] and rep['flagged'] == ['DP1', 'DP3']          # DP3 25% > 20%
    assert rep['types']['DP3']['reasons'] == {'TIMEOUT': 1}

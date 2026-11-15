"""WP5 evaluation harness: plan arithmetic, fake-client flow, summary shape, guard hook, LIVE gates. No network, no key, no GT."""
import copy
import importlib
import json
from pathlib import Path

import pytest

wp5 = importlib.import_module('amidst.agent_eval.wp5')
fake = importlib.import_module('amidst.agent_eval.wp5_fake')
runner = importlib.import_module('amidst.agent_eval.wp5_runner')
ad = importlib.import_module('amidst.q1q5.agent_decision')
ar = importlib.import_module('amidst.q1q5.attention_ranking')

ROOT = Path(__file__).resolve().parents[2]
CFG = wp5.load_config()
TABLE = wp5.load_json(CFG['price_table_path'])


def _pinned(tmp_path):
    t = dict(TABLE, status='PINNED', date='2026-11-15', source='unit-test-fixture')
    p = tmp_path / 'prices.json'
    p.write_text(json.dumps(t), encoding='utf-8')
    return p


def _rows(out):
    return [json.loads(x) for x in (out / 'calls.jsonl').read_text(encoding='utf-8').splitlines()]


def test_config_valid_and_pilot_is_288_openai_calls():
    est = wp5.estimate_set(CFG, 'pilot', TABLE)
    assert est['openai_calls_nominal'] == 288
    per = {r['model']: r for r in est['models']}
    assert per['rule']['model_calls_nominal'] == 0 and per['rule']['step_executions'] == 96
    assert per['qwen2.5:7b-instruct-q4_K_M']['usd_nominal'] == 0.0
    assert wp5.plan_set(CFG, 'pilot', models=['astra6'])[0]['calls_by_type'] == {'DP1': 24, 'DP3': 24, 'DP4': 24, 'NL': 24}
    f = wp5.estimate_set(CFG, 'formal', TABLE)
    assert f['openai_calls_nominal'] == 140 * 3 * 3
    assert f['openai_usd_nominal'] < f['openai_usd_worst'] < 100
    assert CFG['timeout_profiles']['formal']['per_call_ms'] == 2000 and CFG['timeout_profiles']['relaxed']['per_call_ms'] == 10000
    for prof in CFG['timeout_profiles'].values():
        p = wp5.load_json(prof['params_path'])
        assert p['per_call']['timeout_ms'] == prof['per_call_ms'] and p['per_step']['budget_ms'] == prof['per_step_ms']


def test_unknown_price_gives_null_not_zero():
    est = wp5.estimate_set(CFG, 'pilot', None)
    assert est['openai_usd_nominal'] is None and est['price_status'] == 'NONE'


def test_synthetic_questions_are_valid_and_unique():
    rows = fake.synthetic_rows(40)
    qs = wp5.select_questions(rows, {'DP1': 30, 'DP3': 30, 'DP4': 40, 'NL': 40})
    assert len(qs) == 140
    for r in rows:
        if r['task_type'] == 'DP4':
            ar.validate_request(r['request'])


def test_dry_run_default_makes_no_calls(tmp_path):
    assert runner.main(['--set', 'pilot', '--out', str(tmp_path)]) == 0
    d = json.loads((tmp_path / 'estimate.json').read_text())
    assert d['provider_calls'] == 0 and d['mode'] == 'DRY_RUN'
    assert not (tmp_path / 'calls.jsonl').exists()


def test_fake_pilot_flow_rows_summary_and_order(tmp_path):
    assert runner.main(['--set', 'pilot', '--fake', '--out', str(tmp_path)]) == 0
    rows = _rows(tmp_path)
    assert len(rows) == 6 * 96
    openai = [r for r in rows if r['model_kind'] == 'OPENAI']
    assert len(openai) == 288 and all(r['outcome'] == 'OK' for r in rows)
    assert {r['phase'] for r in rows} == {'pilot', 'consistency'}
    for r in rows:
        assert r['latency_ms'] is not None and 'accuracy_correct' in r and r['accuracy_correct'] is None
        assert not any(k.startswith('gt_') for k in r)
    # fake tokens equal the estimates, so measured spend equals the plan arithmetic
    est = wp5.estimate_set(CFG, 'pilot', TABLE)
    spent = sum(r['cost_usd'] for r in openai if r['cost_usd'] is not None)
    assert spent == pytest.approx(est['openai_usd_nominal'] - 0.0, rel=0.6)  # fake completions are half of max
    s = json.loads((tmp_path / 'summary.json').read_text())
    cell = next(c for c in s['cells'] if c['model'] == 'astra6' and c['task_type'] == 'DP4')
    assert list(cell)[-1] == 'accuracy_recorded_only'
    assert list(cell).index('latency_ms') < list(cell).index('cost_usd') < list(cell).index('timeout_fallback')
    assert cell['latency_ms']['p50'] <= cell['latency_ms']['p95'] and cell['n_ok'] == 24
    assert len(s['cells']) == 6 * 4
    assert 'p95' in (tmp_path / 'summary.md').read_text()
    assert json.loads((tmp_path / 'MANIFEST.json').read_text())['mode'] == 'FAKE'


def test_timeout_fallback_is_recorded_and_rated(tmp_path):
    assert runner.main(['--set', 'pilot', '--fake', '--fake-timeout-every', '3', '--models', 'astra6',
                        '--out', str(tmp_path)]) == 0
    rows = _rows(tmp_path)
    assert any(r['timed_out_fallback'] for r in rows)
    s = json.loads((tmp_path / 'summary.json').read_text())
    assert any(c['timeout_fallback']['rate'] for c in s['cells'])
    dp1 = [r for r in rows if r['task_type'] == 'DP1' and r['timed_out_fallback']]
    assert dp1 and all(r['decision_source'] in ('AGENT', 'RULE_FALLBACK') for r in dp1)


def test_forbidden_keys_in_a_question_reject_the_batch():
    bad = fake.dp1_request(0)
    bad['current'] = dict(bad['current'], truth_camera_id='CAM_B')
    with pytest.raises(ad.AgentDecisionError):
        wp5.normalize_question({'task_type': 'DP1', 'request': bad})
    bad4 = fake.dp4_request(0)
    bad4['truth'] = 1
    with pytest.raises(Exception):
        wp5.normalize_question({'task_type': 'DP4', 'request': bad4})


def test_questions_short_is_an_error_not_a_silent_shrink():
    with pytest.raises(wp5.Wp5Error, match='QUESTIONS_SHORT'):
        wp5.select_questions(fake.synthetic_rows(2), {'DP1': 4})


class _BlockAfter:
    name = 'TEST_GUARD'

    def __init__(self, n):
        self.n, self.seen, self.recorded = n, 0, 0

    def preflight(self, plan):
        return None

    def reserve(self, **kw):
        self.seen += 1
        return 'TOTAL_USD' if self.seen > self.n else None

    def record(self, **kw):
        self.recorded += 1


def test_guard_hook_blocks_before_the_call_and_rule_bypasses_it():
    ctx, backend = fake.fake_context(CFG, TABLE)
    qs = wp5.select_questions(fake.synthetic_rows(4), CFG['sets']['pilot']['questions_per_type'])
    g = _BlockAfter(5)
    rows = wp5.run_set(ctx, CFG, 'pilot', qs, guard=g, models=['rule', 'astra6'])
    blocked = [r for r in rows if r['outcome'] == 'GUARD_BLOCKED']
    assert len(blocked) == 96 - 5 and g.recorded == 5 and backend.calls == 5
    assert all(r['model'] == 'astra6' and r['guard_reason'] == 'TOTAL_USD' and r['latency_ms'] is None for r in blocked)
    assert sum(r['model'] == 'rule' and r['outcome'] == 'OK' for r in rows) == 96
    cell = next(c for c in wp5.summarize_rows(rows)['cells'] if c['model'] == 'astra6' and c['task_type'] == 'DP1')
    assert cell['n_guard_blocked'] > 0 and cell['n_ok'] + cell['n_guard_blocked'] == cell['n_rows']


def test_live_gates_refuse(tmp_path, capsys):
    base = ['--set', 'pilot', '--live', '--out', str(tmp_path / 'o')]
    assert runner.main(base) == 2 and 'LIVE_NEEDS_APPROVAL' in capsys.readouterr().err
    assert runner.main(base + ['--approved-usd', '10']) == 2 and 'LIVE_NEEDS_PINNED_PRICES' in capsys.readouterr().err
    pin = ['--price-table', str(_pinned(tmp_path)), '--approved-usd', '10']
    assert runner.main(base + pin) == 2 and 'LIVE_NEEDS_ARM' in capsys.readouterr().err
    assert runner.main(base + pin + ['--arm', 'mac']) == 2 and 'LIVE_NEEDS_QUESTIONS' in capsys.readouterr().err
    assert runner.main(base + pin + ['--arm', 'colab_l4', '--questions', 'x', '--models', 'astra6']) == 2
    assert 'NO_MODELS' in capsys.readouterr().err
    assert runner.main(base + ['--price-table', str(_pinned(tmp_path)), '--approved-usd', '0.01', '--arm', 'mac',
                               '--questions', 'x']) == 2
    assert 'LIVE_GUARD_REFUSED' in capsys.readouterr().err
    q = tmp_path / 'q.jsonl'
    q.write_text(''.join(json.dumps(r) + '\n' for r in fake.synthetic_rows(4)), encoding='utf-8')
    assert runner.main(base + pin + ['--arm', 'mac', '--questions', str(q)]) == 2
    assert 'DP4_LIVE_NOT_WIRED' in capsys.readouterr().err


def test_live_with_injected_clients_obeys_the_cap(tmp_path):
    ctx, backend = fake.fake_context(CFG, wp5.load_json(_pinned(tmp_path)))
    q = tmp_path / 'q.jsonl'
    q.write_text(''.join(json.dumps(r) + '\n' for r in fake.synthetic_rows(4)), encoding='utf-8')
    out = tmp_path / 'live'
    rc = runner.main(['--set', 'pilot', '--live', '--arm', 'mac', '--questions', str(q), '--approved-usd', '1.5',
                      '--price-table', str(_pinned(tmp_path)), '--models', 'astra6,rule', '--out', str(out)], context=ctx)
    assert rc == 0
    m = json.loads((out / 'MANIFEST.json').read_text())
    assert m['mode'] == 'LIVE' and m['guard_spent_usd'] <= 1.5 and m['guard'].startswith('LOCAL_CAP_GUARD')
    assert 'approved USD 1.5' in m['approval_ref']


def test_decision_side_never_imports_scoring_or_reads_env():
    for name in ('wp5', 'wp5_runner', 'wp5_fake'):
        text = (ROOT / 'src/amidst/agent_eval' / f'{name}.py').read_text(encoding='utf-8')
        assert 'import amidst.agent_eval_scoring' not in text and 'from amidst.agent_eval_scoring' not in text
        assert 'os.environ' not in text and 'getenv' not in text


def test_colab_local_only_run_needs_no_money_gate(tmp_path):
    ctx, _ = fake.fake_context(CFG, TABLE)
    q = tmp_path / 'q.jsonl'
    q.write_text(''.join(json.dumps(r) + '\n' for r in fake.synthetic_rows(4)), encoding='utf-8')
    out = tmp_path / 'colab'
    rc = runner.main(['--set', 'pilot', '--live', '--arm', 'colab_l4', '--questions', str(q),
                      '--models', 'qwen2.5:7b-instruct-q4_K_M', '--out', str(out)], context=ctx)
    assert rc == 0
    rows = _rows(out)
    assert len(rows) == 96 and {r['model'] for r in rows} == {'qwen2.5:7b-instruct-q4_K_M'}
    assert all(r['cost_usd'] == 0.0 for r in rows)
    assert json.loads((out / 'MANIFEST.json').read_text())['approval_ref'].startswith('NO_SPEND')


# ---- every paid OpenAI call goes through ApiGuard (review fix) ----
def _api_guard(tmp_path, **kw):
    ab = importlib.import_module('amidst.q1q5.api_budget')
    cfg = ab.GuardConfig(enabled=True, max_usd_total=kw.pop('total', 1.0), max_calls_per_min=100, max_calls_per_day=1000,
                         prices={'astra6': {'input_usd_per_mtok': 5.0, 'output_usd_per_mtok': 15.0}}, **kw)
    return ab.ApiGuard(cfg, usage_dir=tmp_path)


def test_openai_decision_call_is_gated_and_ledgered(tmp_path):
    cfg = wp5.load_config()
    model = wp5.model_by_id(cfg, 'astra6')
    seen = []

    def inner(request, *, timeout_ms, max_output_tokens):
        seen.append(1)
        return ad.Attempt(ad.CALL_OK, 5.0, {}, 100, 20)
    req = fake.synthetic_rows(1)[0]
    req = req.get('request', req)
    g = _api_guard(tmp_path)
    call = runner.guarded_decision_call(g, cfg, model, inner)
    att = call(req, timeout_ms=2000, max_output_tokens=300)
    assert att.outcome == ad.CALL_OK and seen == [1]
    assert 'wp5_decision' in g.ledger_path.read_text()
    closed = _api_guard(tmp_path / 'z', total=0.0)
    att = runner.guarded_decision_call(closed, cfg, model, inner)(req, timeout_ms=2000, max_output_tokens=300)
    assert att.outcome == ad.CALL_UNAVAILABLE and seen == [1]   # denied: inner never ran


def test_live_context_refuses_openai_without_api_guard():
    cfg = wp5.load_config()
    ctx = runner.live_context(cfg, wp5.load_json(cfg['price_table_path']), None)
    with pytest.raises(wp5.Wp5Error) as e:
        ctx.decision_provider(wp5.model_by_id(cfg, 'astra6'))
    assert e.value.code == 'LIVE_NEEDS_API_GUARD'
    with pytest.raises(wp5.Wp5Error):
        ctx.nl_client(wp5.model_by_id(cfg, 'astra6'))


def test_make_api_guard_is_closed_unless_approved_and_priced(tmp_path):
    g = runner.make_api_guard({'models': {'astra6': {'input_usd_per_mtok': 1.0, 'output_usd_per_mtok': 2.0}}}, 3.0,
                              env={'AMIDST_API_USAGE_DIR': str(tmp_path)})
    assert g.config.enabled and g.config.max_usd_total == 3.0 and 'astra6' in g.config.prices

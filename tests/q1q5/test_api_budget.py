import json
import subprocess
import sys
from pathlib import Path

import pytest

from amidst.q1q5 import api_budget as ab
from amidst.q1q5 import nl_query_parse as nlp

PRICES = {'astra6': {'input_usd_per_mtok': 1.0, 'output_usd_per_mtok': 2.0}}
FAKE_KEY = 'sk-test-SECRET-1234567890'


def guard(tmp_path, now=None, **kw):
    base = dict(enabled=True, max_usd_total=10.0, prices=PRICES)
    base.update(kw)
    clock = (lambda: now[0]) if now else (lambda: 1_800_000_000.0)
    return ab.ApiGuard(ab.GuardConfig(**base), usage_dir=tmp_path, clock=clock)


def ok(pt=100, ct=50):
    return lambda: ('v', pt, ct)


def test_default_config_is_closed_and_zero():
    c = ab.GuardConfig.from_env({})
    assert c.enabled is False and c.max_usd_total == 0.0


def test_server_off_denies_and_never_calls(tmp_path):
    g = ab.ApiGuard(ab.GuardConfig(prices=PRICES), usage_dir=tmp_path)
    called = []
    r = g.run('t', 'astra6', 100, 50, lambda: called.append(1) or ('v', 1, 1))
    assert (r.allowed, r.reason, called) == (False, 'API_DISABLED', [])


def test_total_zero_denies_everything(tmp_path):
    g = guard(tmp_path, max_usd_total=0.0)
    assert g.run('t', 'astra6', 10, 10, ok()).reason == 'TOTAL_BUDGET'


def test_unpriced_model_denied(tmp_path):
    assert guard(tmp_path).run('t', 'sol6.1', 10, 10, ok()).reason == 'PRICE_UNKNOWN'


def test_per_call_caps(tmp_path):
    g = guard(tmp_path, max_tokens_per_call=100)
    assert g.run('t', 'astra6', 90, 20, ok()).reason == 'PER_CALL_TOKEN_CAP'
    g = guard(tmp_path, max_usd_per_call=0.0001)
    assert g.run('t', 'astra6', 1000, 1000, ok()).reason == 'PER_CALL_COST_CAP'


def test_rate_limit_then_recovers(tmp_path):
    now = [1_800_000_000.0]
    g = guard(tmp_path, now, max_calls_per_min=2)
    assert g.run('t', 'astra6', 10, 10, ok()).allowed and g.run('t', 'astra6', 10, 10, ok()).allowed
    assert g.run('t', 'astra6', 10, 10, ok()).reason == 'RATE_LIMIT'
    now[0] += 61
    assert g.run('t', 'astra6', 10, 10, ok()).allowed


def test_daily_caps(tmp_path):
    g = guard(tmp_path, max_calls_per_day=2)
    g.run('t', 'astra6', 10, 10, ok())
    g.run('t', 'astra6', 10, 10, ok())
    assert g.run('t', 'astra6', 10, 10, ok()).reason == 'DAILY_CALL_CAP'
    g = guard(tmp_path / 'b', max_usd_per_day=0.0005)
    assert g.run('t', 'astra6', 100, 100, ok(100, 100)).allowed   # 0.0003
    assert g.run('t', 'astra6', 100, 100, ok(100, 100)).reason == 'DAILY_COST_CAP'


def test_total_budget_counts_ledger_across_restarts(tmp_path):
    g = guard(tmp_path, max_usd_total=0.0005)
    assert g.run('t', 'astra6', 100, 100, ok(100, 100)).allowed
    g2 = guard(tmp_path, max_usd_total=0.0005)   # new process, same ledger
    assert g2.run('t', 'astra6', 100, 100, ok()).reason == 'TOTAL_BUDGET'


def test_error_is_charged_at_estimate_and_reraised(tmp_path):
    g = guard(tmp_path)

    def boom():
        raise RuntimeError('x')
    with pytest.raises(RuntimeError):
        g.run('t', 'astra6', 1000, 1000, boom)
    row = json.loads(g.ledger_path.read_text().splitlines()[-1])
    assert row['outcome'] == 'ERROR' and row['est_cost_usd'] == pytest.approx(0.003)


def test_ledger_has_no_key_or_prompt_and_only_whitelisted_fields(tmp_path):
    g = guard(tmp_path)
    g.run('nl_parse', 'astra6', 10, 10, ok())
    g.run('nl_parse', 'astra6', 10**6, 10, ok())   # denied row
    text = g.ledger_path.read_text()
    assert FAKE_KEY not in text
    for line in text.splitlines():
        assert set(json.loads(line)) == {'ts', 'caller', 'model', 'outcome', 'reason', 'prompt_tokens', 'completion_tokens', 'est_cost_usd'}
    with pytest.raises(ValueError):
        g.run('bad caller with key ' + FAKE_KEY, 'astra6', 1, 1, ok())


def test_dry_run_estimate_math_and_cap_report():
    out = ab.estimate_run(questions=16, model='astra6', avg_prompt_tokens=1500, avg_output_tokens=300, calls_per_question=3,
                          prices=PRICES, config=ab.GuardConfig())
    assert out['calls'] == 48 and out['est_cost_per_call_usd'] == pytest.approx(0.0021) and out['est_total_usd'] == pytest.approx(0.1008)
    assert 'TOTAL_BUDGET' in out['would_exceed']
    assert ab.estimate_run(questions=1, model='nope', avg_prompt_tokens=1, avg_output_tokens=1, prices=PRICES)['price_known'] is False


def test_dry_run_cli(tmp_path):
    pf = tmp_path / 'p.json'
    pf.write_text(json.dumps({'models': PRICES}))
    root = Path(__file__).resolve().parents[2]
    r = subprocess.run([sys.executable, str(root / 'scripts/api_budget_estimate.py'), '--questions', '10', '--model', 'astra6',
                        '--avg-prompt-tokens', '1000', '--avg-output-tokens', '200', '--prices-file', str(pf)],
                       capture_output=True, text=True, check=True, env={'PATH': '/usr/bin:/bin'})
    assert json.loads(r.stdout)['est_total_usd'] == pytest.approx(0.014)


# ---- NL wiring -------------------------------------------------------------------------------------------------
class FakeNl:
    model = 'astra6'

    def parse(self, text, vocab, timeout_ms):
        return nlp.ClientResult({'action': None, 'location': [], 'target': [], 'time': None, 'unrecognized': []}, 100, 50, 0.0002)


VOCAB = type('V', (), {'region_ids': (), 'target_labels': ()})()


def test_nl_server_off_falls_back_with_reason(tmp_path):
    env = {'OPENAI_API_KEY': FAKE_KEY}   # key present but server switch absent
    clients = nlp.clients_from_environment(env, guard=ab.ApiGuard(ab.GuardConfig.from_env(env), usage_dir=tmp_path))
    assert isinstance(clients['API'], ab.DisabledApiClient)
    with pytest.raises(nlp.NlClientError) as e:
        clients['API'].parse('找人', None, 1000)
    assert e.value.code == 'API_DISABLED'


def test_nl_guarded_client_denies_with_total_zero_and_allows_when_set(tmp_path):
    g = guard(tmp_path, max_usd_total=0.0)
    c = ab.GuardedNlClient(FakeNl(), g)
    with pytest.raises(nlp.NlClientError) as e:
        c.parse('找人', VOCAB, 1000)
    assert e.value.code == 'TOTAL_BUDGET'
    c = ab.GuardedNlClient(FakeNl(), guard(tmp_path / 'b'))
    assert c.parse('找人', VOCAB, 1000).prompt_tokens == 100


# ---- review fixes ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('bad', [{'input_usd_per_mtok': float('nan'), 'output_usd_per_mtok': 1}, {'input_usd_per_mtok': -1, 'output_usd_per_mtok': 1},
                                 {'input_usd_per_mtok': float('inf'), 'output_usd_per_mtok': 1}, {'input_usd_per_mtok': 'x', 'output_usd_per_mtok': 1}])
def test_bad_price_is_unknown_not_free(tmp_path, bad):
    g = guard(tmp_path, prices={'astra6': bad})
    assert g.run('t', 'astra6', 10, 10, ok()).reason == 'PRICE_UNKNOWN'


def test_negative_reported_usage_is_charged_worst_case(tmp_path):
    g = guard(tmp_path)
    g.run('t', 'astra6', 1000, 1000, lambda: ('v', -10**6, -10**6))
    assert json.loads(g.ledger_path.read_text().splitlines()[-1])['est_cost_usd'] == pytest.approx(0.003)


def test_ledger_write_failure_keeps_counting(tmp_path):
    ro = tmp_path / 'ro'
    ro.mkdir()
    ro.chmod(0o555)   # ledger missing and not creatable -> every append fails
    try:
        g = ab.ApiGuard(ab.GuardConfig(enabled=True, max_usd_total=0.0005, prices=PRICES), usage_dir=ro)
        if (ro / 'probe').exists() or not _unwritable(ro):
            pytest.skip('directory permissions not enforced (root?)')
        assert g.run('t', 'astra6', 100, 100, ok(100, 100)).allowed
        assert g.run('t', 'astra6', 100, 100, ok(100, 100)).reason == 'TOTAL_BUDGET'
    finally:
        ro.chmod(0o755)


def test_unreadable_ledger_denies(tmp_path):
    g = guard(tmp_path)
    g.ledger_path.mkdir()   # exists but is a directory -> read fails with OSError
    called = []
    r = g.run('t', 'astra6', 10, 10, lambda: called.append(1) or ('v', 1, 1))
    assert (r.allowed, r.reason, called) == (False, 'LEDGER_UNAVAILABLE', [])


def test_concurrent_calls_never_exceed_total(tmp_path):
    import threading
    import time
    g = guard(tmp_path, max_usd_total=0.0007, max_calls_per_min=1000, max_calls_per_day=1000)   # each call reserves 0.0003 -> at most 2 fit

    def slow():
        time.sleep(0.05)
        return 'v', 100, 100
    results = []
    ts = [threading.Thread(target=lambda: results.append(g.run('t', 'astra6', 100, 100, slow))) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sum(r.allowed for r in results) == 2


def test_shared_guard_is_one_instance_per_config():
    env = {'AMIDST_API_ENABLED': '1', 'AMIDST_API_MAX_USD_TOTAL': '1'}
    assert ab.shared_guard(env) is ab.shared_guard(dict(env))


def _unwritable(d):
    try:
        (d / 'probe').write_text('x')
    except OSError:
        return True
    (d / 'probe').unlink()
    return False

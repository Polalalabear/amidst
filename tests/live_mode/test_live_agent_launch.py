"""Startup resource limits and runtime isolation, without starting a process."""
import importlib.util
from pathlib import Path

import pytest

p = Path(__file__).resolve().parents[2] / 'scripts/operations/start_live_agent_8791.py'
spec = importlib.util.spec_from_file_location('live_agent_launch', p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('budget', [0, -1, 3.01, float('inf')])
def test_launch_refuses_budget_outside_e5_live_allowance(budget):
    with pytest.raises(ValueError, match='MAX_3_USD'):
        module.settings('/runtime', '/local', '/scratch/out', '/python', budget)


def test_launch_uses_existing_runtime_and_scratch_ledger():
    cmd, env = module.settings('/runtime', '/local', '/scratch/out', '/python')
    assert env['PYTHONPATH'].split(':')[0] == '/runtime/src'
    assert env['AMIDST_API_USAGE_DIR'] == '/scratch/out/usage'
    assert env['AMIDST_API_MAX_USD_TOTAL'] == env['AMIDST_API_MAX_USD_PER_DAY'] == '3.0'
    assert cmd[cmd.index('--advisor') + 1] == 'agent'
    assert cmd[cmd.index('--advisor-model') + 1] == 'terra6.1'
    with pytest.raises(ValueError, match='SCRATCHPAD'):
        module.settings('/runtime', '/local', '/local/evidence', '/python')


def test_launcher_never_binds_demo_pin_port():
    with pytest.raises(ValueError, match='RESERVED_PORT'):
        module.settings('/runtime', '/local', '/scratch/out', '/python', port=8785)



def preview_config(**overrides):
    from amidst.q1q5.api_budget import GuardConfig
    cfg = {'enabled': True, 'max_usd_total': 3, 'max_usd_per_day': 3,
           'max_usd_per_call': .2, 'max_tokens_per_call': 40000, 'max_calls_per_day': 200,
           'prices': {'gpt-6.1-terra': {'input_usd_per_mtok': 1, 'output_usd_per_mtok': 5}}}
    return GuardConfig(**(cfg | overrides))


def test_budget_preview_is_read_only_and_uses_public_estimator(tmp_path):
    reason, estimate = module.budget_preview(preview_config(), tmp_path)
    assert reason is None and estimate == .0275 and not list(tmp_path.iterdir())


@pytest.mark.parametrize('overrides,expected', [({'enabled': False}, 'API_DISABLED'),
    ({'prices': {}}, 'PRICE_UNKNOWN'), ({'max_tokens_per_call': 10}, 'PER_CALL_TOKEN_CAP'),
    ({'max_usd_per_call': .01}, 'PER_CALL_COST_CAP'), ({'max_usd_total': .01}, 'TOTAL_BUDGET')])
def test_budget_preview_refuses_estimated_limits(tmp_path, overrides, expected):
    assert module.budget_preview(preview_config(**overrides), tmp_path)[0] == expected


@pytest.mark.parametrize('ts,cost,overrides,expected', [
    ('2026-11-22', 2.99, {}, 'TOTAL_BUDGET'), ('2026-11-23', 2.99, {}, 'DAILY_COST_CAP'),
    ('2026-11-23', .01, {'max_calls_per_day': 1}, 'DAILY_CALL_CAP')])
def test_budget_preview_counts_existing_ledger_without_new_rows(tmp_path, ts, cost, overrides, expected):
    import json
    from datetime import datetime, timezone
    ledger = tmp_path / 'usage.jsonl'
    ledger.write_text(json.dumps({'outcome': 'OK', 'ts': ts, 'est_cost_usd': cost}) + '\n')
    before = ledger.read_bytes()
    assert module.budget_preview(preview_config(**overrides), tmp_path,
                                 now=datetime(2026, 11, 23, tzinfo=timezone.utc))[0] == expected
    assert ledger.read_bytes() == before


def test_budget_preview_fails_closed_for_unreadable_ledger(tmp_path):
    (tmp_path / 'usage.jsonl').mkdir()
    assert module.budget_preview(preview_config(), tmp_path)[0] == 'LEDGER_UNAVAILABLE'


def test_launcher_dry_run_avoids_private_guard_methods_and_processes(tmp_path, monkeypatch, capsys):
    import json
    from amidst.q1q5 import api_budget
    def forbidden(*args, **kw):
        pytest.fail('dry-run must not instantiate/run a guard or start a process')
    monkeypatch.setattr(api_budget, 'ApiGuard', forbidden)
    monkeypatch.setattr(module.subprocess, 'Popen', forbidden)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *args, **kw: module.APPROVED_RUNTIME_SHA + '\n')
    out = tmp_path / 'out'
    monkeypatch.setattr(module.sys, 'argv', ['launcher', '--runtime', str(tmp_path / 'runtime'),
        '--local-root', str(tmp_path / 'data'), '--output', str(out), '--python', '/python'])
    module.main()
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['allowed'] and receipt['api_calls'] == 0 and receipt['runtime_sha'] == module.APPROVED_RUNTIME_SHA
    assert not (out / 'usage').exists()

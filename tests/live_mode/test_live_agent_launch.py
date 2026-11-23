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

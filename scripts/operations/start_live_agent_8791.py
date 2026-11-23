"""D357: launch the existing LIVE runtime, with a scratch-only USD 3 ledger.

Default is a dry-run. Never deploys the working branch's LIVE fixes.
"""
from __future__ import annotations
import argparse
import dataclasses
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


APPROVED_RUNTIME_SHA = 'c988ed607cb2941bde2b84688f9675213efd2a98'


def budget_preview(cfg, usage_dir, *, now=None):
    """Read-only preflight using public estimates/configuration and the JSONL ledger format.

    Does not call ApiGuard private methods, create ledger rows or reserve any money. The runtime
    ApiGuard still authoritatively checks every paid attempt (including concurrent spend).
    """
    from amidst.q1q5.api_budget import LEDGER_NAME, estimate_run
    estimate = estimate_run(questions=1, model='gpt-6.1-terra', avg_prompt_tokens=20000,
                            avg_output_tokens=1500, prices=cfg.prices, config=cfg)
    cost = estimate['est_cost_per_call_usd']
    if not cfg.enabled:
        return 'API_DISABLED', cost
    if not estimate['price_known']:
        return 'PRICE_UNKNOWN', cost
    if estimate['would_exceed']:
        return estimate['would_exceed'][0], cost
    today = (now or datetime.now(timezone.utc)).strftime('%Y-%m-%d')
    try:
        lines = (Path(usage_dir) / LEDGER_NAME).read_text().splitlines()
    except FileNotFoundError:
        lines = []
    except OSError:
        return 'LEDGER_UNAVAILABLE', cost
    total, daily, calls = 0.0, 0.0, 0
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue  # same tolerant JSONL format as ApiGuard; no credential or prompt is read
        if not isinstance(row, dict) or row.get('outcome') == 'DENIED':
            continue
        spent = row.get('est_cost_usd')
        if not isinstance(spent, (int, float)):
            continue
        total += spent
        if str(row.get('ts', ''))[:10] == today:
            daily += spent
            calls += 1
    if calls >= cfg.max_calls_per_day:
        return 'DAILY_CALL_CAP', cost
    if daily + cost > cfg.max_usd_per_day:
        return 'DAILY_COST_CAP', cost
    if total + cost > cfg.max_usd_total:
        return 'TOTAL_BUDGET', cost
    return None, cost


def settings(runtime, local_root, output, python, budget=3.0, port=8791):
    if port == 8785 or not 1 <= port <= 65535:
        raise ValueError('INVALID_OR_RESERVED_PORT')
    if not 0 < budget <= 3:
        raise ValueError('E5_PENDING_LIVE_BUDGET_MAX_3_USD')
    runtime, local_root, output = map(lambda p: Path(p).resolve(), (runtime, local_root, output))
    if output.is_relative_to(local_root):
        raise ValueError('OUTPUT_MUST_BE_IN_SCRATCHPAD')
    env = dict(os.environ)
    env.pop('AMIDST_API_CONFIG_FILE', None)
    env.pop('AMIDST_API_PRICES_FILE', None)
    env.update(PYTHONPATH=f'{runtime / "src"}:{local_root / "data/q1q5-dynamic-baseline-v1_20261025/runtime-deps"}',
               AMIDST_ARTIFACTS=str(output), AMIDST_API_ENABLED='1',
               AMIDST_API_MAX_USD_TOTAL=str(budget), AMIDST_API_MAX_USD_PER_DAY=str(budget),
               AMIDST_API_MAX_USD_PER_CALL='0.2', AMIDST_API_MAX_TOKENS_PER_CALL='40000',
               AMIDST_API_MAX_CALLS_PER_DAY='200', AMIDST_API_MAX_CALLS_PER_MIN='15',
               AMIDST_API_USAGE_DIR=str(output / 'usage'))
    cmd = [str(python), '-B', '-m', 'amidst.live_mode.server', '--port', str(port), '--device', 'mps', '--threads', '4',
           '--models', str(local_root / 'data/demo-owned-v1/models/rtdetr'),
           '--cameras', str(local_root / 'data/r004-build-v2-20261021/safe_static/cameras.json'),
           '--assets', str(local_root / 'data/live-assets-20261115'),
           '--advisor', 'agent', '--advisor-model', 'terra6.1', '--advisor-provider', 'openai', '--advisor-timeout-s', '15']
    return cmd, env


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'local-root', 'output', 'python'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--budget-usd', type=float, default=3)
    p.add_argument('--port', type=int, default=8791)
    p.add_argument('--start', action='store_true')
    a = p.parse_args()
    cmd, env = settings(a.runtime, a.local_root, a.output, a.python, a.budget_usd, a.port)
    sys.path.insert(0, str(a.runtime.resolve() / 'src'))
    from amidst.q1q5.api_budget import GuardConfig
    from amidst.live_mode.advisor import MODELS as ADVISOR_MODELS
    prices = {m[0]: {'input_usd_per_mtok': m[1], 'output_usd_per_mtok': m[2]} for m in ADVISOR_MODELS.values()}
    cfg = dataclasses.replace(GuardConfig.from_env(env), prices=prices)
    reason, estimated = budget_preview(cfg, env['AMIDST_API_USAGE_DIR'])
    receipt = {'dry_run': True, 'allowed': reason is None, 'reason': reason, 'estimated_call_usd': estimated,
               'cap_usd': cfg.max_usd_total, 'api_calls': 0, 'runtime_sha': subprocess.check_output(
                   ['git', '-C', str(a.runtime), 'rev-parse', 'HEAD'], text=True).strip()}
    if receipt['runtime_sha'] != APPROVED_RUNTIME_SHA:
        raise SystemExit('UNAPPROVED_RUNTIME_SHA')
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / 'dry-run.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if a.start:
        if reason or not os.environ.get('OPENAI_API_KEY', '').strip():
            raise SystemExit('GUARD_DENIED_OR_NO_API_KEY')
        with (a.output / 'server.log').open('ab') as log:
            proc = subprocess.Popen(cmd, env=env, cwd=a.runtime, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        receipt.update(started=True, pid=proc.pid, port=a.port)
        (a.output / 'launch.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()

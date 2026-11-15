#!/usr/bin/env python3
"""Dry-run cost estimate for a paid-API run (no network, no key). Show the output to the user before any LIVE run.

  python3 scripts/api_budget_estimate.py --questions 16 --model astra6 --avg-prompt-tokens 1500 --avg-output-tokens 300 \
      --calls-per-question 3 --prices-file prices.json
Prices come from --prices-file or AMIDST_API_PRICES_FILE ({"models": {id: {"input_usd_per_mtok", "output_usd_per_mtok"}}}).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5 import api_budget as ab  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--questions', type=int, required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--avg-prompt-tokens', type=int, required=True)
    p.add_argument('--avg-output-tokens', type=int, required=True)
    p.add_argument('--calls-per-question', type=int, default=1)
    p.add_argument('--prices-file')
    a = p.parse_args(argv)
    if min(a.questions, a.avg_prompt_tokens, a.avg_output_tokens, a.calls_per_question) < 0:
        p.error('values must be non-negative')
    prices = None
    pf = a.prices_file or os.environ.get('AMIDST_API_PRICES_FILE')
    if pf:
        prices = json.loads(Path(pf).read_text('utf-8')).get('models')
    cfg = ab.GuardConfig.from_env()
    out = ab.estimate_run(questions=a.questions, model=a.model, avg_prompt_tokens=a.avg_prompt_tokens, avg_output_tokens=a.avg_output_tokens,
                          calls_per_question=a.calls_per_question, prices=prices, config=cfg)
    out['server_enabled'] = cfg.enabled
    out['server_total_budget_usd'] = cfg.max_usd_total
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

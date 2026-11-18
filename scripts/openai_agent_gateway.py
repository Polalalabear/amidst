"""#601 OpenAI Agent gateway for the recorded-data demo (8785). Run it in its own terminal, NOT inside the demo process.

The demo process cannot open sockets (D269 audit hook). This process makes the paid call: it serves the file queue under
the demo's owned ``state/agent-gateway`` directory, and every call goes through ApiGuard (AMIDST_API_* env, D165/D166).
Without AMIDST_API_ENABLED=1 and AMIDST_API_MAX_USD_TOTAL>0 it stays up but reports GUARD_NOT_APPROVED, so the demo falls
back to rules. OPENAI_API_KEY is read only from this process's environment at call time and never printed.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from amidst.q1q5.api_budget import ApiGuard, GuardConfig   # noqa: E402
from amidst.q1q5.openai_gateway import API_MODEL, PRICES, QUEUE_DIRNAME, GatewayWorker   # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--queue-dir', type=Path, help='default: <owned state_root>/agent-gateway of configs/demo_integration_local.json')
    p.add_argument('--model', default=API_MODEL, choices=sorted(PRICES))
    args = p.parse_args()
    queue = args.queue_dir
    if queue is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from demo_dependency_config import configuration, owned_path
        config, root = configuration(None)
        queue = owned_path(root, config['state_root']) / QUEUE_DIRNAME
    cfg = GuardConfig.from_env()
    if cfg.prices is None:   # D237 prices keyed by API model id
        cfg = dataclasses.replace(cfg, prices={m: {'input_usd_per_mtok': a, 'output_usd_per_mtok': b} for m, (a, b) in PRICES.items()})
    worker = GatewayWorker(queue, ApiGuard(cfg), models=(args.model,))
    st = worker.write_status()
    print(json.dumps({'queue_dir': str(queue), 'guard_approved': st['guard_approved'], 'key_present': st['key_present'], 'models': st['models']}), flush=True)
    worker.serve_forever()


if __name__ == '__main__':
    main()

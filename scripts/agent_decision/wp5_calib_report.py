"""WP5 OpenAI calibration (D237): per-model x per-type token/cost/latency stats and cost projections.

Reads LOCAL run output (``runs/*/calls.jsonl`` + ``guard-ledger/usage.jsonl``); stdlib only; no key; no GT.
    python scripts/agent_decision/wp5_calib_report.py <evidence dir> [price table json]
Measured = from the runs. Projected = measured mean tokens x question counts, +-2 standard errors of the completion mean.
"""
from __future__ import annotations

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

TYPES = ('DP1', 'DP3', 'NL')
MODELS = ('terra6.1', 'sol6.1', 'astra6')
CONFIG_PROMPT_EST = {'DP1': 1500, 'DP3': 1000, 'DP4': 2500, 'NL': 700}   # configs/agent_eval/wp5_v1.json
# steps per model: pilot = 4 questions x (1 + 5 repeats); formal = DP1 30, DP3 30, NL 40 (DP4 40) x 3 repeats
SETS = {'pilot': {'DP1': 24, 'DP3': 24, 'NL': 24, 'DP4': 24}, 'formal': {'DP1': 90, 'DP3': 90, 'NL': 120, 'DP4': 120}}


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    i = int(k)
    j = min(i + 1, len(xs) - 1)
    return xs[i] + (xs[j] - xs[i]) * (k - i)


def main(argv):
    root = Path(argv[1])
    price = json.loads(Path(argv[2] if len(argv) > 2 else 'configs/agent_eval/wp5_price_table_v1.json').read_text())['models']
    rows = [json.loads(ln) for f in sorted(glob.glob(str(root / 'runs/*/calls.jsonl'))) for ln in open(f)]
    ledger = [json.loads(ln) for ln in open(root / 'guard-ledger/usage.jsonl')]
    g = defaultdict(list)
    for r in rows:
        g[(r['model'], r['task_type'])].append(r)
    out = ['### Measured per model x type (steps with token usage)', '',
           '| model | type | n | prompt tok | completion tok mean (sd) | USD/call mean | latency p50 ms | latency p95 ms | valid answer |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    stat = {}
    for m in MODELS:
        for t in TYPES:
            v = g[(m, t)]
            pt = [r['prompt_tokens'] for r in v if r['prompt_tokens'] is not None]
            ct = [r['completion_tokens'] for r in v if r['completion_tokens'] is not None]
            cs = [r['cost_usd'] for r in v if r['cost_usd'] is not None]
            lat = [r['latency_ms'] for r in v]
            ok = sum(1 for r in v if r['decision_source'] in ('AGENT', 'API'))
            stat[(m, t)] = (st.mean(pt), st.mean(ct), len(ct))
            out.append(f"| {m} | {t} | {len(v)} | {st.mean(pt):.0f} | {st.mean(ct):.0f} ({st.pstdev(ct):.0f}) | {st.mean(cs):.5f} | "
                       f"{pct(lat, .5):.0f} | {pct(lat, .95):.0f} | {ok}/{len(v)} |")
    sd = {}
    for t in TYPES:  # pooled within-model sd of completion tokens
        cts = {m: [x['completion_tokens'] for x in g[(m, t)] if x['completion_tokens'] is not None] for m in MODELS}
        dev = [c - st.mean(v) for v in cts.values() for c in v]
        dof = sum(len(v) - 1 for v in cts.values())
        sd[t] = math.sqrt(sum(d * d for d in dev) / dof)

    def cost(m, t, n, prompt=None, mult=1.0):
        pt, ct, k = stat[(m, t)]
        pt = prompt if prompt is not None else pt
        per = (pt * price[m]['input_usd_per_mtok'] + ct * price[m]['output_usd_per_mtok']) / 1e6
        err = 2 * sd[t] / math.sqrt(k) * price[m]['output_usd_per_mtok'] / 1e6
        return n * per * mult, n * err

    out += ['', '### Projection per model (DP1+DP3+NL only; DP4 unmeasured)', '',
            '| set | model | calls | synthetic-prompt USD (+-2 SE) | config-prompt-estimate USD (upper) |', '| --- | --- | ---: | ---: | ---: |']
    proj = {}
    for s, counts in SETS.items():
        for m in MODELS:
            n = sum(counts[t] for t in TYPES)
            a = [cost(m, t, counts[t]) for t in TYPES]
            b = [cost(m, t, counts[t], prompt=CONFIG_PROMPT_EST[t]) for t in TYPES]
            proj[(s, m)] = (sum(x[0] for x in a), sum(x[1] for x in a), sum(x[0] for x in b))
            out.append(f"| {s} | {m} | {n} | {proj[(s, m)][0]:.3f} +- {proj[(s, m)][1]:.3f} | {proj[(s, m)][2]:.3f} |")
    ok_rows = [r for r in ledger if r['outcome'] == 'OK' and r['prompt_tokens'] is not None]
    unbilled = [r for r in ledger if r['outcome'] == 'OK' and r['prompt_tokens'] is None]
    out += ['', '### Guard ledger', '',
            f"- rows {len(ledger)}: OK with usage {len(ok_rows)}, OK without usage (HTTP 400 rejected before any model run) {len(unbilled)}, "
            f"DENIED {sum(r['outcome'] == 'DENIED' for r in ledger)}, ERROR {sum(r['outcome'] == 'ERROR' for r in ledger)}",
            f"- ledger total (est_cost_usd, upper bound): {sum(r['est_cost_usd'] or 0 for r in ledger):.4f} USD",
            f"- billed-usage cost (rows with token usage, at PINNED prices): "
            f"{sum((r['prompt_tokens'] * price[r['model']]['input_usd_per_mtok'] + r['completion_tokens'] * price[r['model']]['output_usd_per_mtok']) / 1e6 for r in ok_rows):.4f} USD",
            f"- tokens: prompt {sum(r['prompt_tokens'] for r in ok_rows)}, completion {sum(r['completion_tokens'] for r in ok_rows)}"]
    print('\n'.join(out))


if __name__ == '__main__':
    main(sys.argv)

#!/usr/bin/env python3
"""F4 (#658, D352) rerun selection. Reads ONLY each run's calls[].fallback_reason (no score, no GT): a (segment, arm) whose runs
have any call denied by the ApiGuard cap (CALL_BUDGET_EXHAUSTED) is rerun with all K runs, so the K runs of one arm share one
condition. A3 is rerun on every segment for a separate reason (preregistration §7 implementation), listed apart."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--a3', action='store_true', help='also list every A3 (segment, arm) for the §7 rerun')
    a = ap.parse_args()
    budget, a3 = [], []
    for case_dir in sorted(p for p in a.runs.iterdir() if p.is_dir() and p.name.startswith('E3-')):
        arms = {}
        for f in sorted(case_dir.glob('A*.json')):
            doc = json.loads(f.read_text())
            n = sum(1 for c in doc.get('calls') or [] if c.get('fallback_reason') == 'CALL_BUDGET_EXHAUSTED')
            arms.setdefault(doc['arm'], []).append({'file': f.name, 'budget_denied_calls': n, 'calls': len(doc.get('calls') or [])})
        for arm, runs in sorted(arms.items()):
            if any(r['budget_denied_calls'] for r in runs):
                budget.append({'case_id': case_dir.name, 'arm': arm, 'runs': runs})
            elif a.a3 and arm == 'A3':
                a3.append({'case_id': case_dir.name, 'arm': arm, 'runs': runs})
    print(json.dumps({'schema_version': 'e3-f4.rerun-list.v1', 'runs_folder': a.runs.name, 'rule': 'any CALL_BUDGET_EXHAUSTED -> rerun all K',
                      'budget_denied': budget, 'a3_section7': a3}, indent=1))


if __name__ == '__main__':
    main()

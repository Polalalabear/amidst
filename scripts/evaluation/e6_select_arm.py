#!/usr/bin/env python3
"""E6 batch-3 group selection (prereg 2.2) and the formal-run gate. Scoring side only: GT is read here, never by inference.

Subcommands
  select       score the K=1 diagnostic runs of the pool {DEANCHOR, DEANCHOR_HIST, DEANCHOR_HIST_SUM} on E3-A1/E3-B1/E3-C1,
               apply the hard-coded rule and write the batch-3 freeze receipt (never overwritten).
  formal-gate  refuse unless the receipt exists and the formal dry-run estimates fit USD 32 and the cumulative cap (prereg 7.1).

Rule (prereg 2.2, written once, no tuning):
  eligibility  format-return rate <= 0.20, provider-error rate <= 0.10, GT-isolation violations == 0, no CALL_BUDGET_EXHAUSTED,
               all three cases present and scorable. None eligible -> exit 3 (stop, fix the implementation).
  ranking      level 1 wrong-person seconds (sum, tie within 1.0 s of the lowest) -> level 2 blind false-lock seconds (sum, tie within
               1.0 s of the lowest) -> level 3 mean per-segment follow rate (tie within 0.01 of the highest) -> level 4 simplest
               (DEANCHOR > DEANCHOR_HIST > DEANCHOR_HIST_SUM). Each level keeps every group within the tolerance of the best one.
Metrics use the pinned single-tick definitions (src/amidst/evaluation/e3_scoring.py through e3_f4_score.run_scores, primary criterion).
Identity stays UNCONFIRMED. No paid call, no model import, no GT in any output other than aggregate seconds/rates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from amidst.evaluation.e7_scoring_bridge import FORBIDDEN_GT_FIELDS  # noqa: E402

SCHEMA = 'e6.batch3-freeze.v1'
POOL = ('DEANCHOR', 'DEANCHOR_HIST', 'DEANCHOR_HIST_SUM')          # simplest first (prereg 2.2 step 4)
DIAG_CASES = ('E3-A1', 'E3-B1', 'E3-C1')                            # prereg 5.1
FORMAT_RETURN_MAX, PROVIDER_ERROR_MAX = 0.20, 0.10
TIE_WP_S, TIE_FL_S, TIE_FOLLOW = 1.0, 1.0, 0.01
FORMAL_CAP_USD, PROJECT_CAP_USD, BASE_SPEND_USD = 32.0, 90.0, 38.17  # prereg 7.1, D375
EPS = 1e-9
EXIT_NO_ELIGIBLE, EXIT_GATE = 3, 4
GT_TEXT = re.compile(r'gt_[a-z_]+|ground[ _]truth', re.I)
PROMPT_FILES = ('src/amidst/live_mode/aopen/arms.py', 'src/amidst/live_mode/aopen/decider.py',
                'configs/evaluation/e6_arms_v1.json', 'docs/evaluation/E6_PREREGISTRATION_DRAFT.md')


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


# ------------------------------------------------------------------ GT isolation check of one run document
def gt_violations(doc) -> list[str]:
    """Paths of forbidden GT keys anywhere in the run log, plus GT words inside prompt-side text (calls[].request.variable_text).
    Model free text (reason, summary) is data, not a key, and is not scanned."""
    found: list[str] = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in FORBIDDEN_GT_FIELDS or str(k).startswith('gt_'):
                    found.append(f'{path}.{k}' if path else str(k))
                walk(v, f'{path}.{k}' if path else str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
    walk(doc, '')
    for i, c in enumerate(doc.get('calls') or []):
        text = ((c or {}).get('request') or {}).get('variable_text')
        if isinstance(text, str) and GT_TEXT.search(text):
            found.append(f'calls[{i}].request.variable_text')
    return found


# ------------------------------------------------------------------ pure selection core
def eligibility(m: dict) -> list[str]:
    """Reasons a group fails the hard gate (empty = eligible). ``m`` = aggregated diagnostic metrics of one group."""
    why = []
    if m.get('missing_cases'):
        why.append('MISSING_CASES:' + ','.join(m['missing_cases']))
    if m.get('unscorable'):
        why.append('UNSCORABLE:' + ','.join(m['unscorable']))
    if m.get('format_return_rate') is None or m['format_return_rate'] > FORMAT_RETURN_MAX + EPS:
        why.append(f"FORMAT_RETURN_RATE:{m.get('format_return_rate')}>{FORMAT_RETURN_MAX}")
    if m.get('provider_error_rate') is None or m['provider_error_rate'] > PROVIDER_ERROR_MAX + EPS:
        why.append(f"PROVIDER_ERROR_RATE:{m.get('provider_error_rate')}>{PROVIDER_ERROR_MAX}")
    if m.get('gt_violations'):
        why.append(f"GT_ISOLATION_VIOLATIONS:{len(m['gt_violations'])}")
    if m.get('budget_denied'):
        why.append(f"CALL_BUDGET_EXHAUSTED:{m['budget_denied']}")
    return why


def choose(metrics: dict[str, dict]) -> tuple[str | None, list[dict], dict]:
    """Apply prereg 2.2 to ``{arm: metrics}``. Returns (selected, level trace, {arm: ineligibility reasons})."""
    ineligible = {a: eligibility(metrics[a]) for a in POOL if a in metrics}
    ineligible.update({a: ['NOT_RUN'] for a in POOL if a not in metrics})
    alive = [a for a in POOL if not ineligible[a]]
    trace = []
    if not alive:
        return None, trace, ineligible
    levels = (('wrong_person_s', 'min', TIE_WP_S), ('blind_false_lock_s', 'min', TIE_FL_S), ('follow_rate', 'max', TIE_FOLLOW))
    for key, direction, tol in levels:
        if len(alive) == 1:
            break
        vals = {a: metrics[a][key] for a in alive}
        best = min(vals.values()) if direction == 'min' else max(vals.values())
        keep = [a for a in alive if (vals[a] - best <= tol + EPS if direction == 'min' else best - vals[a] <= tol + EPS)]
        trace.append({'level': key, 'direction': direction, 'tolerance': tol, 'values': vals, 'best': best, 'kept': keep})
        alive = keep
    selected = alive[0]                       # POOL order = simplest first, so a remaining tie goes to the simplest
    if len(alive) > 1:
        trace.append({'level': 'simplicity', 'kept': alive, 'order': list(POOL)})
    return selected, trace, ineligible


def aggregate_arm(arm: str, per_case: dict[str, dict], cases=DIAG_CASES) -> dict:
    """``per_case[cid]``: {'wrong_person_s','false_lock_s','follow_rate','lost_s','calls','format_rejected','provider_errors',
    'budget_denied','gt_violations'} or {'unscorable': reason}. Sums seconds, averages segment follow rates, pools call rates."""
    missing = [c for c in cases if c not in per_case]
    bad = [f'{c}:{v["unscorable"]}' for c, v in per_case.items() if 'unscorable' in v]
    ok = [v for c, v in per_case.items() if c in cases and 'unscorable' not in v]
    calls = sum(v['calls'] for v in ok)
    follows = [v['follow_rate'] for v in ok if v['follow_rate'] is not None]
    return {'arm': arm, 'cases': sorted(per_case), 'missing_cases': missing, 'unscorable': bad,
            'wrong_person_s': round(sum(v['wrong_person_s'] for v in ok), 3),
            'blind_false_lock_s': round(sum(v['false_lock_s'] for v in ok), 3),
            'lost_s': round(sum(v['lost_s'] for v in ok), 3),
            'follow_rate': round(sum(follows) / len(follows), 4) if follows else None,
            'calls': calls, 'format_rejected': sum(v['format_rejected'] for v in ok), 'provider_errors': sum(v['provider_errors'] for v in ok),
            'budget_denied': sum(v['budget_denied'] for v in ok),
            'format_return_rate': round(sum(v['format_rejected'] for v in ok) / calls, 4) if calls else (0.0 if ok else None),
            'provider_error_rate': round(sum(v['provider_errors'] for v in ok) / calls, 4) if calls else (0.0 if ok else None),
            'gt_violations': [x for v in ok for x in v['gt_violations']]}


# ------------------------------------------------------------------ scoring-side loader (reads GT; uses the pinned scorer)
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def score_sources(sources, scorer_path: Path, cases=DIAG_CASES):
    """sources: [(root, catalog, runs)]. Returns ({arm: {case: per-case dict}}, {file: sha256}, scorer sha)."""
    E5 = sys.modules.get('e5_score') or _load('e5_score', HERE / 'e5_score.py')
    F = E5.F
    S = F.load_scorer(scorer_path)
    per: dict[str, dict[str, dict]] = {}
    files: dict[str, str] = {}
    for root, cat_path, runs in sources:
        root, cat_path, runs = Path(root), Path(cat_path), Path(runs)
        for case in json.loads(cat_path.read_text())['cases']:
            cid = case['case_id']
            if cid not in cases or not (runs / cid).is_dir():
                continue
            raw = (root / case['gt_path']).read_bytes()
            if sha_bytes(raw) != case['gt_sha256']:
                raise SystemExit('GT_PIN_MISMATCH ' + cid)
            a_log = json.loads(raw)
            for p in sorted((runs / cid).glob('*.json')):
                body = p.read_bytes()
                files[str(p)] = sha_bytes(body)
                doc = json.loads(body)
                arm = doc.get('arm')
                calls = E5.normalize_calls(doc.get('calls') or [], doc.get('rows') or [])
                viol = gt_violations(doc)
                try:
                    r = F.run_scores(S, case, a_log, doc)['primary']
                    if not r.get('available') or r.get('gt_unknown_stop'):
                        raise ValueError('METRICS_UNAVAILABLE')
                    entry = {'wrong_person_s': r['wrong_person_s'], 'false_lock_s': r['false_lock_s'], 'follow_rate': r['follow_rate'],
                             'lost_s': r['lost_s'], 'visible_s': r['visible_s']}
                except Exception as exc:  # reference arms (B1/AO/R-N) may not be scorable here; a pool arm that fails is ineligible
                    entry = {'unscorable': type(exc).__name__ + ':' + str(exc)[:80]}
                entry.update(calls=calls['calls'], format_rejected=calls['format_rejected'],
                             provider_errors=calls['provider_errors'], budget_denied=calls['budget_denied'], gt_violations=viol)
                per.setdefault(arm, {})[cid] = entry
    return per, files, F.SCORER_SHA


# ------------------------------------------------------------------ receipt
def git_head(repo: Path) -> tuple[str, bool]:
    sha = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=no'],
                                capture_output=True, text=True, check=True).stdout.strip())
    return sha, dirty


def file_hashes(repo: Path, rels=PROMPT_FILES) -> dict:
    return {r: (sha_bytes((repo / r).read_bytes()) if (repo / r).is_file() else 'UNKNOWN_FILE_ABSENT') for r in rels}


def estimate_total(doc) -> float:  # kept for PRECHECK.json style documents
    """USD upper bound from an ``e6_arms_run.py --dry-run`` / PRECHECK.json document."""
    if 'estimate' in doc and isinstance(doc['estimate'], dict):
        doc = doc['estimate']
    v = doc.get('est_total_usd_upper_bound')
    if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
        raise ValueError('ESTIMATE_MISSING')
    return float(v)


def e5_dryrun_total(text: str) -> float:
    """Sum est_total_usd of the ``DRY_RUN <case> {json}`` lines printed by ``e5_run.py`` (AO_ORIG)."""
    total, n = 0.0, 0
    for line in text.splitlines():
        if line.startswith('DRY_RUN '):
            doc = json.loads(line.split(' ', 2)[2])
            if not isinstance(doc.get('est_total_usd'), (int, float)):
                raise ValueError('E5_ESTIMATE_PRICE_UNKNOWN')
            total += doc['est_total_usd']
            n += 1
    if not n:
        raise ValueError('E5_ESTIMATE_MISSING')
    return round(total, 6)


def build_receipt(*, selected, trace, ineligible, metrics, sources_sha, scorer_sha, commit, repo, formal_estimate, created=None, extra=None):
    return {'schema_version': SCHEMA, 'SELECTED_AGENT': selected, 'identity': 'UNCONFIRMED',
            'created_utc': created or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'rule': 'E6_PREREGISTRATION_DRAFT.md 2.2 (hard gate, wrong-person s > blind false-lock s > follow rate > simplicity)',
            'pool': list(POOL), 'diagnostic_cases': list(DIAG_CASES), 'k': 1,
            'tolerances': {'wrong_person_s': TIE_WP_S, 'blind_false_lock_s': TIE_FL_S, 'follow_rate': TIE_FOLLOW,
                           'format_return_max': FORMAT_RETURN_MAX, 'provider_error_max': PROVIDER_ERROR_MAX},
            'metrics': {a: {k: v for k, v in m.items() if k != 'gt_violations'} | {'gt_violation_count': len(m['gt_violations'])}
                        for a, m in metrics.items()},
            'ineligible': {a: r for a, r in ineligible.items() if r}, 'levels': trace,
            'code_commit_sha': commit, 'prompt_and_config_sha256': file_hashes(repo),
            'params': (extra or {}).get('params', {}), 'prompt_extra_sha256': (extra or {}).get('prompt_extra_sha256'),
            'scorer_sha256': scorer_sha, 'diagnostic_run_files_sha256': sources_sha,
            'formal_dry_run_estimate': formal_estimate, 'note': 'frozen: do not re-select after seeing formal outputs (prereg 0.2)'}


REQUIRED_RECEIPT_KEYS = ('SELECTED_AGENT', 'code_commit_sha', 'prompt_and_config_sha256', 'params', 'formal_dry_run_estimate', 'scorer_sha256')


def validate_receipt(r: dict) -> None:
    if not isinstance(r, dict) or r.get('schema_version') != SCHEMA:
        raise ValueError('RECEIPT_SCHEMA')
    miss = [k for k in REQUIRED_RECEIPT_KEYS if k not in r]
    if miss:
        raise ValueError('RECEIPT_MISSING:' + ','.join(miss))
    if r['SELECTED_AGENT'] not in POOL:
        raise ValueError('RECEIPT_SELECTED_AGENT_NOT_IN_POOL')
    if not re.fullmatch(r'[0-9a-f]{40}', str(r['code_commit_sha'])):
        raise ValueError('RECEIPT_COMMIT_SHA')
    if not isinstance(r['formal_dry_run_estimate'], dict) or not isinstance(r['formal_dry_run_estimate'].get('total_usd_upper_bound'), (int, float)):
        raise ValueError('RECEIPT_ESTIMATE')


def ledger_new_usd(dirs) -> float:
    """Sum est_cost_usd of non-DENIED rows of every ledger dir/file (same rule as run_all.sh Stage 1)."""
    total = 0.0
    for d in dirs:
        p = Path(d)
        p = p if p.is_file() else p / 'usage.jsonl'
        if not p.is_file():
            continue
        for line in p.read_text('utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            v = row.get('est_cost_usd') if isinstance(row, dict) else None
            if isinstance(row, dict) and row.get('outcome') != 'DENIED' and isinstance(v, (int, float)) and not isinstance(v, bool):
                total += v
    return total


def formal_gate(receipt: dict, agent_estimates: dict[str, float], *, base=BASE_SPEND_USD, cap=PROJECT_CAP_USD, formal_cap=FORMAL_CAP_USD,
                new_ledger=0.0) -> dict:
    """Raise SystemExit(EXIT_GATE) text via ValueError when a precondition fails. Returns the figures when it passes."""
    validate_receipt(receipt)
    need = {'AO_ORIG', 'DEANCHOR'} | ({receipt['SELECTED_AGENT']} if receipt['SELECTED_AGENT'] != 'DEANCHOR' else set())
    missing = sorted(need - set(agent_estimates))
    if missing:
        raise ValueError('FORMAL_ESTIMATE_MISSING:' + ','.join(missing))
    total = round(sum(agent_estimates[a] for a in need), 6)
    if total > formal_cap + EPS:
        raise ValueError(f'FORMAL_OVER_CAP: {total} > {formal_cap}')
    cumulative = round(base + new_ledger + total, 6)
    if cumulative > cap + EPS:
        raise ValueError(f'CUMULATIVE_OVER_CAP: {base} + {new_ledger:.4f} + {total} > {cap}')
    budget = {g: math.ceil(agent_estimates[g] * 100 - 1e-9) / 100 for g in sorted(need)}     # ApiGuard cap per group = estimate, in cents
    return {'groups': sorted(need), 'per_group_budget_usd': budget, 'agent_arms_budget_usd': round(sum(v for g, v in budget.items() if g != 'AO_ORIG'), 2),
            'formal_total_usd_upper_bound': total, 'cumulative_usd_upper_bound': cumulative,
            'base_usd': base, 'new_ledger_usd': round(new_ledger, 6), 'cap_usd': cap, 'formal_cap_usd': formal_cap}


# ------------------------------------------------------------------ CLI
def cmd_select(a) -> int:
    out = Path(a.out)
    target = out / 'BATCH3_FREEZE.json'
    if target.exists():
        print('FROZEN_RECEIPT_EXISTS: not re-selecting (prereg 0.2)', target, file=sys.stderr)
        return 0 if a.skip_if_exists else 2
    sources = [tuple(s) for s in a.source]
    per, files, scorer_sha = score_sources(sources, a.scorer)
    metrics = {arm: aggregate_arm(arm, per[arm]) for arm in per if arm in POOL}
    selected, trace, ineligible = choose(metrics)
    refs = {arm: aggregate_arm(arm, per[arm]) for arm in per if arm not in POOL}
    print(json.dumps({'metrics': {k: {x: y for x, y in v.items() if x != 'gt_violations'} for k, v in metrics.items()},
                      'reference_arms_info_only': {k: {x: y for x, y in v.items() if x != 'gt_violations'} for k, v in refs.items()},
                      'ineligible': ineligible, 'trace': trace}, indent=1, ensure_ascii=False, default=list))
    if selected is None:
        print('NO_ELIGIBLE_GROUP: stop and fix the implementation; do not enter batch 3 (prereg 2.2.2)', file=sys.stderr)
        return EXIT_NO_ELIGIBLE
    est_doc = json.loads(Path(a.formal_estimate).read_text())
    per_arm_est = {k: float(v['estimate_upper_bound']['est_total_usd']) for k, v in (est_doc.get('arms') or {}).items()}
    ao = e5_dryrun_total(Path(a.ao_estimate).read_text()) if a.ao_estimate else None
    formal_estimate = {'source': str(a.formal_estimate), 'k': est_doc.get('k'), 'cases': est_doc.get('cases'),
                       'per_agent_arm_usd': per_arm_est, 'AO_ORIG_usd': ao, 'total_usd_upper_bound': round(
                           sum(per_arm_est.get(g, 0.0) for g in ({'DEANCHOR', selected})) + (ao or 0.0), 6),
                       'AO_ORIG_estimate_source': str(a.ao_estimate) if a.ao_estimate else 'UNKNOWN'}
    if a.code_commit:
        commit, dirty = a.code_commit, False
    else:
        commit, dirty = git_head(ROOT)
        if dirty and not a.allow_dirty:
            print('WORKTREE_DIRTY: tracked files differ from HEAD; commit first or pass --allow-dirty', file=sys.stderr)
            return 2
    docs = [json.loads(Path(p).read_text()) for p in files if Path(p).name.startswith(selected + '.')]
    cfg = docs[0].get('config', {}) if docs else {}
    extra = {'params': {'arm': selected, 'config': cfg, 'model': cfg.get('model')}, 'prompt_extra_sha256': docs[0].get('prompt_extra_sha256') if docs else None}
    receipt = build_receipt(selected=selected, trace=trace, ineligible=ineligible, metrics=metrics,
                            sources_sha=files, scorer_sha=scorer_sha, commit=commit, repo=ROOT,
                            formal_estimate=formal_estimate, extra=extra) | {'worktree_dirty': dirty}
    validate_receipt(receipt)
    out.mkdir(parents=True, exist_ok=True)
    with target.open('x') as f:
        json.dump(receipt, f, indent=1, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    (out / 'MANIFEST.sha256').write_text(f'{sha_bytes(target.read_bytes())}  BATCH3_FREEZE.json\n')
    print('SELECTED_AGENT', selected, 'receipt', target)
    return 0


def cmd_gate(a) -> int:
    receipt_path = Path(a.receipt)
    if not receipt_path.is_file():
        print(f'FROZEN_RECEIPT_MISSING: {receipt_path}', file=sys.stderr)
        return EXIT_GATE
    receipt = json.loads(receipt_path.read_text())
    est = {}
    if a.arms_estimate:
        doc = json.loads(Path(a.arms_estimate).read_text())
        est.update({k: float(v['estimate_upper_bound']['est_total_usd']) for k, v in (doc.get('arms') or {}).items()})
    if a.ao_estimate:
        est['AO_ORIG'] = e5_dryrun_total(Path(a.ao_estimate).read_text())
    try:
        res = formal_gate(receipt, est, base=a.base, cap=a.cap, new_ledger=ledger_new_usd(a.ledger or []))
    except ValueError as exc:
        print('FORMAL_GATE_FAIL', exc, file=sys.stderr)
        return EXIT_GATE
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=1) + '\n')
    print('FORMAL_GATE_PASS', json.dumps(res))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('select')
    s.add_argument('--source', nargs=3, action='append', required=True, metavar=('ROOT', 'CATALOG', 'RUNS'),
                   help='E3 root, case catalog and runs folder (<runs>/<case>/<ARM>.k1.json); repeat. Non-pool arms are info only.')
    s.add_argument('--scorer', type=Path, default=ROOT / 'src/amidst/evaluation/e3_scoring.py')
    s.add_argument('--formal-estimate', type=Path, required=True, help='e6_arms_run.py --dry-run JSON for the 12 formal cases, K=3, arms DEANCHOR..')
    s.add_argument('--ao-estimate', type=Path, help='captured stdout of e5_run.py --dry-run for the formal cases (AO_ORIG, K=3)')
    s.add_argument('--out', type=Path, required=True)
    s.add_argument('--code-commit', help='40-hex commit of the code that produced the runs (default: git HEAD of this repo, must be clean)')
    s.add_argument('--allow-dirty', action='store_true')
    s.add_argument('--skip-if-exists', action='store_true')
    g = sub.add_parser('formal-gate')
    g.add_argument('--receipt', type=Path, required=True)
    g.add_argument('--arms-estimate', type=Path, help='e6_arms_run.py --dry-run JSON (formal cases, K=3)')
    g.add_argument('--ao-estimate', type=Path, help='captured stdout of e5_run.py --dry-run (formal cases, K=3, AO_ORIG)')
    g.add_argument('--ledger', nargs='*', help='ledger dirs (usage.jsonl) whose rows count as new spend')
    g.add_argument('--out', type=Path, help='write the gate result (groups, per-group ApiGuard budgets) for run_all.sh')
    g.add_argument('--base', type=float, default=BASE_SPEND_USD)
    g.add_argument('--cap', type=float, default=PROJECT_CAP_USD)
    a = ap.parse_args(argv)
    return cmd_select(a) if a.cmd == 'select' else cmd_gate(a)


if __name__ == '__main__':
    raise SystemExit(main())

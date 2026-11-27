"""E6 scoring + verdict CLI (scoring side; #721 G6, D402). Reads GT, so it lives here and not in the inference modules.

  uv run python -B scripts/evaluation/e6_verdict_run.py --frozen-spec configs/evaluation/e6_scenarios_frozen_v1.json \
      --gt-root <formal recording root> --runs <b1 runs> <ao_orig runs> <arms runs> --selected-agent <GROUP | --receipt BATCH3_FREEZE.json> \
      --out <dir>

``--runs`` takes one or more run roots laid out as ``<root>/<case>/<anything>.json`` (e3_f4_run B1 logs, e5_run AO logs, e6_arms_run logs);
each log's ``arm`` names its group (``AO`` -> AO_ORIG). The pinned scorer (e3_scoring.py, SHA-256 acacce39...) is loaded through
e3_f4_score.load_scorer; GT files are checked against the frozen spec's gt_sha256. Per segment: wrong-person s, blind false-lock s
(= scorer false_lock_s), lost s, follow rate; per decision point: the prereg 3.2 full-tracking window (15 ticks = 3.0 s from the decision
tick) judged by the frozen ``gt_regime``. Output: verdict_e6.json, VERDICT_E6.md, scored_inputs.json, MANIFEST.sha256.
single_dp_acc needs the separate paired K=1 snapshot run (not produced by 2c), so ``single_correct`` stays None here (UNKNOWN, not reported).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from amidst.evaluation import e6_verdict as V  # noqa: E402

TICK_US = 200_000
WINDOW_TICKS = 15
ARM_TO_GROUP = {'AO': 'AO_ORIG'}
DISPLAYED_NOT = ('BLIND_OK', 'LOST')


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def load_frozen(path):
    spec = json.loads(Path(path).read_text())
    if 'FROZEN' not in str(spec.get('status', '')):
        raise SystemExit('FROZEN_SPEC_NOT_FROZEN: ' + str(spec.get('status')))
    return spec


def collect_runs(run_roots, cases):
    """-> {(case, group): [run docs]} from every run root; a case folder missing in a root is simply absent."""
    runs = {}
    for root in run_roots:
        for cid in cases:
            d = Path(root) / cid
            if not d.is_dir():
                continue
            for f in sorted(d.glob('*.json')):
                doc = json.loads(f.read_text())
                if not isinstance(doc, dict) or 'rows' not in doc or 'arm' not in doc:
                    continue
                runs.setdefault((cid, ARM_TO_GROUP.get(doc['arm'], doc['arm'])), []).append(doc)
    return runs


def window_ticks(classes, tick):
    out = []
    for k in range(tick, tick + WINDOW_TICKS):
        if k in classes:
            out.append({'cls': classes[k], 'displayed': classes[k] not in DISPLAYED_NOT})
    return out


def score(frozen, gt_root, run_roots, S, run_scores, groups):
    """Build the verdict_e6 input rows. ``run_scores`` is e3_f4_score.run_scores (injectable for tests)."""
    gt_root = Path(gt_root)
    segments, points, quality = [], [], {}
    cases = [c['case_id'] for c in frozen['formal_cases']]
    runs = collect_runs(run_roots, cases)
    for c in frozen['formal_cases']:
        cid = c['case_id']
        raw = (gt_root / c['gt_path']).read_bytes()
        if sha_bytes(raw) != c['gt_sha256']:
            raise SystemExit('GT_PIN_MISMATCH ' + cid)
        a_log = json.loads(raw)
        dps = c['actual_decision_points']
        case = {'case_id': cid, 'decision_points': [{'tick': d['tick'], 'type': d['type'], 'timestamp_us': d['tick'] * TICK_US,
                                                      'evaluation_window_us': [d['tick'] * TICK_US, (d['tick'] + WINDOW_TICKS) * TICK_US]}
                                                     for d in dps]}
        for g in groups:
            docs = runs.get((cid, g))
            if not docs:
                raise SystemExit(f'RUNS_MISSING {cid} {g}')
            scored = [run_scores(S, case, a_log, d) for d in docs]
            prims = [s['primary'] for s in scored]
            if any(not p.get('available') or p.get('follow_rate') is None for p in prims):
                raise SystemExit(f'SCORE_UNAVAILABLE {cid} {g}')
            segments.append({'case_id': cid, 'family_id': c['family_id'], 'group': g,
                             'wrong_person_s': [p['wrong_person_s'] for p in prims], 'blind_false_lock_s': [p['false_lock_s'] for p in prims],
                             'lost_s': [p['lost_s'] for p in prims], 'follow_rate': [p['follow_rate'] for p in prims],
                             'visible_ticks': [p['visible_ticks'] for p in prims]})
            for d in dps:
                flags = [V.full_track_dp_correct(d['gt_regime'], window_ticks(s['classes'], d['tick'])) for s in scored]
                points.append({'dp_id': d['dp_id'], 'case_id': cid, 'family_id': c['family_id'], 'group': g, 'gt_regime': d['gt_regime'],
                               'full_track_correct': flags, 'single_correct': None})
            q = quality.setdefault(g, {'runs': 0, 'calls': 0, 'error': 0, 'timeout': 0, 'budget_denied': 0})
            q['runs'] += len(scored)
            for s in scored:
                for k in ('calls', 'error', 'timeout', 'budget_denied'):
                    q[k] += s['api_breakdown'][k]
    for q in quality.values():
        q['provider_error_rate'] = round((q['error'] + q['timeout']) / q['calls'], 4) if q['calls'] else 0.0
    return segments, points, quality


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frozen-spec', type=Path, required=True)
    ap.add_argument('--gt-root', type=Path, required=True)
    ap.add_argument('--runs', type=Path, nargs='+', required=True)
    ap.add_argument('--selected-agent')
    ap.add_argument('--receipt', type=Path, help='BATCH3_FREEZE.json (SELECTED_AGENT is read from it)')
    ap.add_argument('--scorer', type=Path, default=ROOT / 'src/amidst/evaluation/e3_scoring.py')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(argv)
    selected = a.selected_agent
    if a.receipt:
        selected = json.loads(a.receipt.read_text())['SELECTED_AGENT']
    if not selected:
        ap.error('--selected-agent or --receipt is required')
    import e3_f4_score as F4
    S = F4.load_scorer(a.scorer)
    groups = sorted({'B1', 'AO_ORIG', 'DEANCHOR', selected})
    frozen = load_frozen(a.frozen_spec)
    segments, points, quality = score(frozen, a.gt_root, a.runs, S, F4.run_scores, groups)
    verdict = V.verdict_e6(segments, points, selected_agent=selected)
    verdict['data_quality'] = quality
    verdict['frozen_spec_sha256'] = sha_bytes(a.frozen_spec.read_bytes())
    verdict['scorer_sha256'] = F4.SCORER_SHA
    out = a.out
    if (out / 'verdict_e6.json').exists():
        raise SystemExit('OUTPUT_EXISTS: ' + str(out / 'verdict_e6.json'))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'verdict_e6.json').write_text(json.dumps(verdict, indent=1, sort_keys=True, allow_nan=False))
    (out / 'VERDICT_E6.md').write_text(V.render_markdown(verdict))
    (out / 'scored_inputs.json').write_text(json.dumps({'segments': segments, 'decision_points': points}, sort_keys=True, allow_nan=False))
    (out / 'MANIFEST.sha256').write_text(''.join(f'{sha_bytes((out / n).read_bytes())}  {n}\n'
                                                for n in ('verdict_e6.json', 'VERDICT_E6.md', 'scored_inputs.json')))
    print(json.dumps({'status': verdict['status'], 'M': verdict['M'], 'N_dp': verdict['N_dp'],
                      'verdicts': {h: x['verdict'] for h, x in verdict['hypotheses'].items()}}))
    return 0


if __name__ == '__main__':
    main()

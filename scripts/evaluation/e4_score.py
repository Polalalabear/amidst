"""E4 (#681) scoring: A2E4 against B1 and E3 A2 with the pinned E3 scorer (acacce39...), preregistration
docs/evaluation/E4_PREREGISTRATION_20261123.md §4-§5. Reuses ``e3_f4_score.run_scores`` (K runs scored one by one, then averaged;
decision points by majority; segment-cluster bootstrap). Every H7 verdict is EXPLORATORY by design (§0).

  python -B scripts/evaluation/e4_score.py --scorer <e3_scoring.py> \
     --source <E3 root> <catalog> <E3 runs> <E4 runs> [--source ...] --out report.json --table per-segment.md
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e3_f4_score', ROOT / 'scripts/evaluation/e3_f4_score.py')
F4 = importlib.util.module_from_spec(_spec)
sys.modules['e3_f4_score'] = F4
_spec.loader.exec_module(F4)

ARMS = ('B1', 'B2', 'A2', 'A2E4')
NONINF_S = 17.1          # §5 H7a (ii): 15 % of B1's 114.0 s
FOLLOW_MARGIN = 0.05
H7C_YES, H7C_NO = 56, 20  # ranked reappearance points out of 111


def h7a(vs_a2, vs_b1):
    i_yes, i_no = vs_a2['wp_diff_ci'][1] < 0, vs_a2['wp_diff_ci'][0] >= 0
    ii_yes = vs_b1['wp_diff_ci'][1] < NONINF_S and vs_b1['follow_diff_ci'][0] > -FOLLOW_MARGIN
    ii_no = vs_b1['wp_diff_ci'][0] > NONINF_S
    v = 'SUPPORTED' if i_yes and ii_yes else 'NOT_SUPPORTED' if i_no or ii_no else 'INCONCLUSIVE'
    return {'verdict': v, 'label': 'EXPLORATORY', 'i_better_than_e3_a2': i_yes, 'ii_noninferior_to_b1': ii_yes,
            'note': 'BETTER_THAN_E3_BUT_NONINFERIORITY_NOT_SHOWN' if i_yes and not ii_yes and v != 'NOT_SUPPORTED' else None}


def h7b(vs_a2):
    ci = vs_a2['fl_diff_ci']
    return {'verdict': 'SUPPORTED' if ci[1] < 0 else 'NOT_SUPPORTED' if ci[0] >= 0 else 'INCONCLUSIVE', 'label': 'EXPLORATORY'}


def h7c(ranked, total):
    v = 'SUPPORTED' if ranked >= H7C_YES else 'NOT_SUPPORTED' if ranked < H7C_NO else 'INCONCLUSIVE'
    return {'verdict': v, 'label': 'EXPLORATORY', 'ranked': ranked, 'total': total}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', nargs='+', action='append', required=True, metavar='ROOT CATALOG RUNS...')
    ap.add_argument('--scorer', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--table', type=Path, default=None)
    a = ap.parse_args()
    S = F4.load_scorer(a.scorer)
    per, cases, catalogs = {}, [], {}
    for src in a.source:
        root, cat_path, runs = Path(src[0]), Path(src[1]), [Path(x) for x in src[2:]]
        catalog = json.loads(cat_path.read_text())
        catalogs[cat_path.name] = hashlib.sha256(cat_path.read_bytes()).hexdigest()
        for case in catalog['cases']:
            cid = case['case_id']
            raw = (root / case['gt_path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != case['gt_sha256']:
                raise SystemExit('GT_PIN_MISMATCH ' + cid)
            a_log = json.loads(raw)
            docs = [json.loads(f.read_text()) for r in runs if (r / cid).is_dir() for f in sorted((r / cid).glob('*.json'))]
            docs = [d for d in docs if d['arm'] in ARMS]
            if not docs:
                continue
            cases.append(case)
            missed = F4.missed_ticks(S, root, case, a_log)
            b1 = next((d for d in docs if d['arm'] == 'B1'), None)
            b1_class = F4.run_scores(S, case, a_log, b1)['classes'] if b1 else {}
            for d in docs:
                r = F4.run_scores(S, case, a_log, d, b1_class, missed)
                r['validation'] = Counter(c.get('validation') for c in d.get('calls') or [] if c.get('validation'))
                per.setdefault((cid, d['arm']), []).append(r)
    has = lambda cid, arm: (cid, arm) in per
    mean = F4.mean

    def seg(cid, arm, crit='primary'):
        ms = [r[crit] for r in per[(cid, arm)] if r[crit].get('available')]
        if not ms:
            return None
        return {'wp_s': mean([m['wrong_person_s'] for m in ms]), 'fl_s': mean([m['false_lock_s'] for m in ms]),
                'lost_s': mean([m['lost_s'] for m in ms]), 'visible': mean([m['visible_ticks'] for m in ms]),
                'correct': mean([m['follow_rate'] * m['visible_ticks'] for m in ms if m['follow_rate'] is not None]),
                'gt_unknown_stop': any(m.get('gt_unknown_stop') for m in ms)}

    def dpm(cid, arm):
        rs = per[(cid, arm)]
        return [S.majority([r['decision_points'][i]['correct'] for r in rs]) for i in range(len(rs[0]['decision_points']))]

    def compare(x, y, crit='primary'):
        cl = {c['case_id']: (seg(c['case_id'], x, crit), seg(c['case_id'], y, crit)) for c in cases if has(c['case_id'], x) and has(c['case_id'], y)}
        cl = {k: v for k, v in cl.items() if v[0] and v[1]}
        wp = lambda vs: sum(p['wp_s'] - q['wp_s'] for p, q in vs)
        fl = lambda vs: sum(p['fl_s'] - q['fl_s'] for p, q in vs)
        fr = lambda vs: sum(p['correct'] for p, _ in vs) / sum(p['visible'] for p, _ in vs) - sum(q['correct'] for _, q in vs) / sum(q['visible'] for _, q in vs)
        vals = list(cl.values())
        pairs = [pq for c in cases if c['case_id'] in cl for pq in zip(dpm(c['case_id'], x), dpm(c['case_id'], y))]
        return {'wp_diff': round(wp(vals), 3), 'wp_diff_ci': S.cluster_bootstrap(cl, wp), 'fl_diff': round(fl(vals), 3),
                'fl_diff_ci': S.cluster_bootstrap(cl, fl), 'follow_diff': round(fr(vals), 4), 'follow_diff_ci': S.cluster_bootstrap(cl, fr),
                'mcnemar': S.mcnemar(pairs), 'n_points': len(pairs), 'n_segments': len(cl)}

    report = {'schema_version': 'e4.report.v1', 'scorer_sha256': F4.SCORER_SHA, 'catalog_sha256': catalogs, 'identity': 'UNCONFIRMED',
              'label': 'EXPLORATORY (E4 preregistration §0)', 'cases': [c['case_id'] for c in cases], 'per_arm': {}, 'per_case': {},
              'comparisons': {}, 'verdicts': {}, 'stop': {'gt_unknown': [], 'api_errors': []}}
    for arm in ARMS:
        ac = [c for c in cases if has(c['case_id'], arm)]
        if not ac:
            continue
        segs = [seg(c['case_id'], arm) for c in ac]
        flat = [d for c in ac for r in per[(c['case_id'], arm)] for d in r['decision_points'] if 'topk' in d]
        brk = [r['api_breakdown'] for c in ac for r in per[(c['case_id'], arm)]]
        dp = sum((dpm(c['case_id'], arm) for c in ac), [])
        val = Counter()
        for c in ac:
            for r in per[(c['case_id'], arm)]:
                val.update(r['validation'])
        report['per_arm'][arm] = {
            'segments': len(ac), 'wrong_person_s': round(sum(s['wp_s'] for s in segs), 3), 'false_lock_s': round(sum(s['fl_s'] for s in segs), 3),
            'lost_s': round(sum(s['lost_s'] for s in segs), 3), 'follow_rate': round(sum(s['correct'] for s in segs) / sum(s['visible'] for s in segs), 4),
            'dp_correct': sum(dp), 'dp_total': len(dp), 'ranked': sum(1 for d in flat if d['topk']['ranked']), 'reappear_total': len(flat),
            'top1': sum(d['topk']['hit1'] for d in flat), 'top3': sum(d['topk']['hit3'] for d in flat),
            'random_top1': round(mean([d['topk']['random1'] for d in flat]) or 0, 4),
            'api': {k: sum(b[k] for b in brk) for k in ('calls', 'applied', 'agent_not_applied', 'timeout', 'error', 'budget_denied', 'answered_no_effect')} if brk and 'calls' in brk[0] else None,
            'validation': dict(val)}
        for c in ac:
            s = seg(c['case_id'], arm)
            report['per_case'][f"{c['case_id']}|{arm}"] = {'family': c['family'], **s, 'dp': dpm(c['case_id'], arm), 'k': len(per[(c['case_id'], arm)])}
            if s['gt_unknown_stop']:
                report['stop']['gt_unknown'].append(f"{c['case_id']}|{arm}")
            for r in per[(c['case_id'], arm)]:
                if r['api_breakdown'].get('error_stop'):
                    report['stop']['api_errors'].append({'run': f"{c['case_id']}|{arm}|k{r['k']}", **{k: r['api_breakdown'][k] for k in ('calls', 'error', 'error_rate')}})
    for x, y in [('A2E4', 'A2'), ('A2E4', 'B1'), ('A2', 'B1'), ('A2E4', 'B2')]:
        if x in report['per_arm'] and y in report['per_arm']:
            report['comparisons'][f'{x}-{y}'] = compare(x, y)
    if 'A2E4' in report['per_arm'] and 'B1' in report['per_arm']:
        report['robustness_iou_conservative'] = {'label': 'ROBUSTNESS ONLY; verdicts unchanged', 'A2E4-B1': compare('A2E4', 'B1', 'iou_conservative')}
    cmp, pa = report['comparisons'], report['per_arm']
    if 'A2E4-A2' in cmp and 'A2E4-B1' in cmp:
        report['verdicts']['H7a'] = h7a(cmp['A2E4-A2'], cmp['A2E4-B1'])
        report['verdicts']['H7b'] = h7b(cmp['A2E4-A2'])
    if 'A2E4' in pa:
        report['verdicts']['H7c'] = h7c(pa['A2E4']['ranked'], pa['A2E4']['reappear_total'])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=list))
    if a.table:
        lines = ['| 段 | 類 | 組 | K | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對（多數決） |', '|---|---|---|---|---|---|---|---|---|']
        for c in cases:
            for arm in ARMS:
                p = report['per_case'].get(f"{c['case_id']}|{arm}")
                if p:
                    lines.append(f"| {c['case_id']} | {c['family']} | {arm} | {p['k']} | {p['wp_s']:.2f} | {p['correct'] / p['visible']:.3f} | "
                                 f"{p['lost_s']:.2f} | {p['fl_s']:.2f} | {sum(p['dp'])}/{len(p['dp'])} |")
        a.table.write_text('\n'.join(lines) + '\n')
    print('WROTE', a.out, 'segments', len(cases), 'arms', list(pa), 'stop', json.dumps({k: len(v) for k, v in report['stop'].items()}))


if __name__ == '__main__':
    main()

"""F4 (#658) E3 scoring. Scoring side: reads the B logs from e3_f4_run.py, the private case catalog and the GT sidecars.

The scorer is loaded from ``--scorer`` and must have SHA-256 acacce39… (the PR #662 merge version, preregistration §6.0).
Per run: ``ticks_from_live(a, b, target, tick_us=200000, size=(320, 180))`` -> metrics (primary and IoU), decision-point
correctness, camera top-k at reappearance points. Per arm: K runs averaged per tick metric; decision points by K=3 majority.
Comparisons: cluster bootstrap over segments (2000, seed 660), McNemar on decision points, verdict_h1 / h2 / h4.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

SCORER_SHA = 'acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08'
TICK_US, SIZE, N_CAMS = 200_000, (320, 180), 8
REAPPEAR = {'REAPPEAR', 'BRANCH_RETURN', 'SCREEN_RETURN'}
D_EXIT = {'TRUE_EXIT_APPROACH', 'TRUE_EXIT_BOUNDARY'}


def load_scorer(path: Path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SCORER_SHA:
        raise SystemExit('SCORER_SHA_MISMATCH')
    spec = importlib.util.spec_from_file_location('e3_scoring_pinned', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def run_scores(S, case, a_log, b_doc):
    target = a_log['actor_id']
    ticks = S.ticks_from_live(a_log['ticks'], b_doc['rows'], target, tick_us=TICK_US, size=SIZE)
    prim, iou = S.metrics(ticks, 'primary', TICK_US), S.metrics(ticks, 'iou', TICK_US)
    vis = {}
    for r in a_log['ticks']:
        gt = next((x for x in r.get('actors') or [] if x['id'] == target), None)
        vis[r['tick']] = frozenset(gt.get('gt_visible') or []) if gt and gt.get('present') else frozenset()
    rank = {r['tick']: r.get('ranking') or [] for r in b_doc['rows']}
    dps = []
    for d in case['decision_points']:
        ok = S.decision_point_correct(ticks, d['timestamp_us'])
        ok_iou = S.decision_point_correct(ticks, d['timestamp_us'], criterion='iou') if iou.get('available') else None
        item = {'tick': d['tick'], 'type': d['type'], 'correct': ok, 'correct_iou': ok_iou}
        if d['type'] in REAPPEAR:
            first = next((t for t in sorted(vis) if t >= d['tick'] and vis[t]), None)
            ranked = rank.get(d['tick'] - 1, [])
            item['topk'] = {'ranked': ranked[:3], 'visible': sorted(vis[first]) if first is not None else [],
                            'hit1': first is not None and bool(set(ranked[:1]) & vis[first]),
                            'hit3': first is not None and bool(set(ranked[:3]) & vis[first]),
                            'random1': S.random_topk(N_CAMS, len(vis[first]), 1) if first is not None else None}
        dps.append(item)
    calls = b_doc.get('calls') or []
    return {'primary': prim, 'iou': iou, 'decision_points': dps, 'n_ticks': len(ticks),
            'api': {'calls': len(calls), 'answered': sum(1 for c in calls if c.get('source') == 'AGENT'),
                    'applied': sum(1 for c in calls if c.get('applied')),
                    'fallback': sum(1 for c in calls if c.get('source') == 'RULE_FALLBACK'),
                    'latency_ms': [round(c['model_latency_s'] * 1000) for c in calls if c.get('model_latency_s') is not None],
                    'expired': sum(1 for c in calls if c.get('source') == 'RULE_FALLBACK' and c.get('fallback_reason') == 'TIME_BUDGET'),
                    'input_tokens': sum((c.get('usage') or {}).get('input_tokens', 0) for c in calls),
                    'output_tokens': sum((c.get('usage') or {}).get('output_tokens', 0) for c in calls)}}


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True, help='E3_ROOT')
    ap.add_argument('--catalog', type=Path, required=True, help='configs/evaluation/e3_live_cases_v1.json (main)')
    ap.add_argument('--scorer', type=Path, required=True)
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    S = load_scorer(a.scorer)
    catalog = json.loads(a.catalog.read_text())
    per = {}            # (case, arm) -> [run scores]
    for case in catalog['cases']:
        cid = case['case_id']
        a_raw = (a.root / case['gt_path']).read_bytes()
        if hashlib.sha256(a_raw).hexdigest() != case['gt_sha256']:
            raise SystemExit('GT_PIN_MISMATCH ' + cid)
        a_log = json.loads(a_raw)
        for f in sorted((a.runs / cid).glob('*.json')) if (a.runs / cid).is_dir() else []:
            b = json.loads(f.read_text())
            per.setdefault((cid, b['arm']), []).append(run_scores(S, case, a_log, b))
    arms = sorted({k[1] for k in per})
    cases = [c for c in catalog['cases'] if all((c['case_id'], arm) in per for arm in arms)]
    fam = {c['case_id']: c['family'] for c in cases}

    def seg(cid, arm, crit='primary'):
        rs = per[(cid, arm)]
        ms = [r[crit] for r in rs if r[crit].get('available')]
        if not ms:
            return None
        return {'wp_s': mean([m['wrong_person_s'] for m in ms]), 'correct': mean([m['follow_rate'] * m['visible_ticks'] for m in ms if m['follow_rate'] is not None]),
                'visible': mean([m['visible_ticks'] for m in ms]), 'lost_s': mean([m['lost_s'] for m in ms]),
                'false_lock_s': mean([m['false_lock_s'] for m in ms]), 'gt_unknown_stop': any(m['gt_unknown_stop'] for m in ms),
                'reacq_median_s': mean([m['reacquire']['median_s'] for m in ms])}

    def dp_majority(cid, arm, key='correct'):
        rs = per[(cid, arm)]
        return [S.majority([r['decision_points'][i][key] for r in rs]) for i in range(len(rs[0]['decision_points']))]

    def compare(arm_a, arm_b, crit='primary'):
        clusters = {}
        for c in cases:
            sa, sb = seg(c['case_id'], arm_a, crit), seg(c['case_id'], arm_b, crit)
            if sa and sb:
                clusters[c['case_id']] = (sa, sb)
        if not clusters:
            return None
        wp = lambda vs: sum(x[0]['wp_s'] - x[1]['wp_s'] for x in vs)
        fr = lambda vs: (sum(x[0]['correct'] for x in vs) / sum(x[0]['visible'] for x in vs)) - (sum(x[1]['correct'] for x in vs) / sum(x[1]['visible'] for x in vs))
        vals = list(clusters.values())
        pairs = []
        for c in cases:
            pairs += list(zip(dp_majority(c['case_id'], arm_a), dp_majority(c['case_id'], arm_b)))
        return {'wp_diff': round(wp(vals), 3), 'wp_diff_ci': S.cluster_bootstrap(clusters, wp), 'follow_diff': round(fr(vals), 4),
                'follow_diff_ci': S.cluster_bootstrap(clusters, fr), 'mcnemar': S.mcnemar(pairs), 'n_points': len(pairs),
                'n_segments': len(clusters)}

    report = {'schema_version': 'e3-f4.report.v1', 'scorer_sha256': SCORER_SHA, 'catalog_sha256': hashlib.sha256(a.catalog.read_bytes()).hexdigest(),
              'cases': [c['case_id'] for c in cases], 'arms': arms, 'identity': 'UNCONFIRMED', 'per_case': {}, 'per_arm': {}, 'comparisons': {},
              'verdicts': {}}
    for c in cases:
        for arm in arms:
            report['per_case'][f"{c['case_id']}|{arm}"] = {'family': c['family'], 'primary': seg(c['case_id'], arm), 'iou': seg(c['case_id'], arm, 'iou'),
                                                           'dp_majority': dp_majority(c['case_id'], arm), 'k': len(per[(c['case_id'], arm)]),
                                                           'api': [r['api'] for r in per[(c['case_id'], arm)]]}
    for arm in arms:
        segs = [seg(c['case_id'], arm) for c in cases]
        dpm = sum((dp_majority(c['case_id'], arm) for c in cases), [])
        top = [dp for c in cases for r in per[(c['case_id'], arm)][:1] for dp in r['decision_points'] if 'topk' in dp]
        tops = [[dp for dp in r['decision_points'] if 'topk' in dp] for c in cases for r in per[(c['case_id'], arm)]]
        flat = [d for t in tops for d in t]
        api = [r['api'] for c in cases for r in per[(c['case_id'], arm)]]
        lat = sorted(x for a_ in api for x in a_['latency_ms'])
        report['per_arm'][arm] = {
            'wrong_person_s': round(sum(s['wp_s'] for s in segs), 3), 'follow_rate': round(sum(s['correct'] for s in segs) / sum(s['visible'] for s in segs), 4),
            'lost_s': round(sum(s['lost_s'] for s in segs), 3), 'false_lock_s': round(sum(s['false_lock_s'] for s in segs), 3),
            'dp_correct': sum(dpm), 'dp_total': len(dpm), 'gt_unknown_stop': any(s['gt_unknown_stop'] for s in segs),
            'by_family': {f: {'wrong_person_s': round(sum(seg(c['case_id'], arm)['wp_s'] for c in cases if c['family'] == f), 3),
                              'dp_correct': sum(sum(dp_majority(c['case_id'], arm)) for c in cases if c['family'] == f),
                              'dp_total': sum(len(dp_majority(c['case_id'], arm)) for c in cases if c['family'] == f)} for f in sorted(set(fam.values()))},
            'top1': (sum(d['topk']['hit1'] for d in flat), len(flat)), 'top3': (sum(d['topk']['hit3'] for d in flat), len(flat)),
            'random_top1': round(mean([d['topk']['random1'] for d in flat]) or 0, 4),
            'api': {'calls': sum(x['calls'] for x in api), 'applied': sum(x['applied'] for x in api), 'fallback': sum(x['fallback'] for x in api), 'expired_or_unapplied': sum(x['expired'] for x in api),
                    'latency_ms_p50': lat[len(lat) // 2] if lat else None, 'latency_ms_p95': lat[min(len(lat) - 1, int(.95 * len(lat)))] if lat else None,
                    'input_tokens': sum(x['input_tokens'] for x in api), 'output_tokens': sum(x['output_tokens'] for x in api)}}
    for x, y in [('A2', 'B1'), ('A3', 'B1'), ('A1', 'B1'), ('A2', 'B2'), ('B2', 'B1'), ('A2', 'A1')]:
        if x in arms and y in arms:
            report['comparisons'][f'{x}-{y}'] = compare(x, y)
            report['comparisons'][f'{x}-{y}|iou'] = compare(x, y, 'iou')
    cmp = report['comparisons']
    if 'A2-B1' in cmp:
        c = cmp['A2-B1']; ci = cmp.get('A2-B1|iou') or {}
        report['verdicts']['H1'] = S.verdict_h1(c['wp_diff_ci'], c['follow_diff_ci'], c['mcnemar'], c['n_points'], c['n_segments'], ci.get('follow_diff'))
    if 'A3-B1' in cmp:
        c = cmp['A3-B1']
        report['verdicts']['H1_secondary_A3'] = S.verdict_h1(c['wp_diff_ci'], c['follow_diff_ci'], c['mcnemar'], c['n_points'], c['n_segments'])
    if 'A1-B1' in cmp and 'A2-B2' in cmp:
        dcl = {}
        for cc in cases:
            idx = [i for i, d in enumerate(cc['decision_points']) if d['type'] in D_EXIT]
            if idx:
                a2, b2 = dp_majority(cc['case_id'], 'A2'), dp_majority(cc['case_id'], 'B2')
                dcl[cc['case_id']] = [(a2[i], b2[i]) for i in idx]
        dstat = lambda vs: (sum(a for v in vs for a, _ in v) - sum(b for v in vs for _, b in v)) / max(1, sum(len(v) for v in vs))
        dci = S.cluster_bootstrap(dcl, dstat) if dcl else [0.0, 0.0]
        report['verdicts']['H2'] = S.verdict_h2(cmp['A1-B1']['wp_diff_ci'], cmp['A2-B2']['wp_diff_ci'], dci, cmp['A2-B1']['n_points'], cmp['A2-B1']['n_segments'])
        report['verdicts']['H2']['d_exit_diff_ci'] = dci
    if 'A2' in arms and 'A1' in arms:
        def tclusters(arm):
            return {c['case_id']: [d['topk']['hit1'] for r in per[(c['case_id'], arm)] for d in r['decision_points'] if 'topk' in d] for c in cases}
        t2, t1 = tclusters('A2'), tclusters('A1')
        both = {k: (t2[k], t1[k]) for k in t2 if t2[k]}
        diff = lambda vs: sum(sum(a) for a, _ in vs) / max(1, sum(len(a) for a, _ in vs)) - sum(sum(b) for _, b in vs) / max(1, sum(len(b) for _, b in vs))
        rate2 = lambda vs: sum(sum(a) for a, _ in vs) / max(1, sum(len(a) for a, _ in vs))
        pa2, pa1 = report['per_arm']['A2'], report['per_arm']['A1']
        lat2 = mean([seg(c['case_id'], 'A2')['reacq_median_s'] for c in cases]); lat1 = mean([seg(c['case_id'], 'A1')['reacq_median_s'] for c in cases])
        n_re = sum(1 for c in cases for d in c['decision_points'] if d['type'] in REAPPEAR)
        report['verdicts']['H4'] = S.verdict_h4(S.cluster_bootstrap(both, diff) or [0, 0], pa2['top1'][0] / max(1, pa2['top1'][1]), pa2['random_top1'],
                                                S.cluster_bootstrap(both, rate2) or [0, 0], lat2, lat1, n_re)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=list))
    print(json.dumps({k: report[k] for k in ('per_arm', 'verdicts')}, ensure_ascii=False, default=list)[:6000])


if __name__ == '__main__':
    main()

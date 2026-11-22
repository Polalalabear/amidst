"""F4 (#658) E3 scoring. Scoring side: reads the B logs from e3_f4_run.py, the private case catalog and the GT sidecars.

The scorer is loaded from ``--scorer`` and must have SHA-256 acacce39… (the PR #662 merge version, preregistration §6.0).
Per run: ``ticks_from_live(a, b, target, tick_us=200000, size=(320, 180))`` -> metrics (primary and IoU), decision-point
correctness, camera top-k at reappearance points. Per arm: K runs averaged per tick metric; decision points by K=3 majority.
Comparisons: cluster bootstrap over segments (2000, seed 660), McNemar on decision points, verdict_h1 / h2 / h4.
Each comparison uses the segments where both arms ran (A3 only has the original 9; D349). D350 adds the H2 supplementary
diagnostics (supplementary, never a verdict input), the API outcome breakdown (applied / not applied / expired / timeout / error)
and the A1/A2 image parity check (preregistration §9). Several ``--source ROOT CATALOG RUNS`` triples are scored together.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

SCORER_SHA = 'acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08'
TICK_US, SIZE, N_CAMS = 200_000, (320, 180), 8
REAPPEAR = {'REAPPEAR', 'BRANCH_RETURN', 'SCREEN_RETURN'}
D_EXIT = {'TRUE_EXIT_APPROACH', 'TRUE_EXIT_BOUNDARY'}
BAD = {'WRONG_PERSON', 'WRONG_CAMERA'}
ERROR_CAP = 0.10      # preregistration §9: API errors or timeouts > 10 % in any arm and segment -> stop


def missed_ticks(S, root: Path, case, a_log):
    """Ticks where the GT target is visible in a camera whose frozen index has no detection centre inside the projected body box
    (any class, score >= 0.3): the detector missed the target there (D350 diagnostic 2)."""
    m = json.loads((root / 'indexes' / case['case_id'] / 'detection_index.json').read_text())
    idx = {}
    for r in map(json.loads, (root / 'indexes' / case['case_id'] / m['records_ref']).read_text().splitlines()):
        idx[(r['camera_id'], r['frame_index'])] = [d['bbox_xyxy_px'] for d in r['detections'] if d['score'] >= 0.3]
    out = set()
    for r in a_log['ticks']:
        gt = next((x for x in r.get('actors') or [] if x['id'] == a_log['actor_id']), None)
        if not gt or not gt.get('present'):
            continue
        for cam in gt.get('gt_visible') or []:
            body = (gt.get('gt_boxes') or {}).get(cam)
            if body and not any(S.center_in(b, body) for b in idx.get((cam, r['tick']), [])):
                out.add(r['tick'])
                break
    return out


def api_breakdown(calls):
    """Per run: applied / not applied (answer arrived but not executable) / expired (A3) / timeout / provider or format error /
    budget denial. Error rate = (timeout + error) / calls; 'not applied' is a successful call (Opus #666) and is not an error."""
    out = {'calls': len(calls), 'applied': 0, 'agent_not_applied': 0, 'expired': 0, 'timeout': 0, 'error': 0, 'budget_denied': 0,
           'answered_no_effect': 0, 'error_reasons': {}}
    for c in calls:
        r = c.get('fallback_reason')
        if c.get('applied'):
            out['applied'] += 1
        elif r == 'EXPIRED':
            out['expired'] += 1
        elif r == 'CALL_BUDGET_EXHAUSTED':
            out['budget_denied'] += 1
        elif r == 'TIME_BUDGET' and c.get('answer'):
            out['agent_not_applied'] += 1
        elif r == 'TIME_BUDGET':
            out['timeout'] += 1
        elif r:
            out['error'] += 1
            out['error_reasons'][r] = out['error_reasons'].get(r, 0) + 1
        else:
            out['answered_no_effect'] += 1          # NOT_VISIBLE / STILL_HERE / OWN_BOX recorded: answered, no box change
    out['error_rate'] = round((out['timeout'] + out['error']) / out['calls'], 4) if out['calls'] else 0.0
    out['error_stop'] = out['error_rate'] > ERROR_CAP or out['budget_denied'] > 0
    return out


def diagnostics(S, case, ticks, b1_class, missed):
    """D350 H2 supplementary diagnostics for one run (supplementary analysis; never changes a §6 verdict)."""
    by = {t.t_us // TICK_US: t for t in ticks}
    cls = {k: S.classify(t) for k, t in by.items()}
    out = {}
    dps = {d['type']: d for d in case['decision_points']}
    occ = next((e for e in case.get('diagnostic_events') or [] if e['type'] == 'SCREEN_OCCLUSION'), None)
    if occ and 'SCREEN_RETURN' in dps and 'SCREEN_BEFORE_OCCLUSION' in dps:            # 1. occlusion keep rate (D)
        cams = set(dps['SCREEN_BEFORE_OCCLUSION']['cameras'])
        win = [k for k in range(occ['tick'], dps['SCREEN_RETURN']['tick']) if k in by]
        kept = [k for k in win if by[k].shown_camera in cams and cls[k] not in BAD | {'FALSE_LOCK'}]
        out['occlusion'] = {'ticks': len(win), 'kept': len(kept), 'keep_rate': round(len(kept) / len(win), 4) if win else None,
                            'false_lock_s': round(sum(cls[k] == 'FALSE_LOCK' for k in win) * TICK_US / 1e6, 2)}
    lost_missed = [k for k in sorted(missed) if b1_class.get(k) == 'LOST' and k in by]  # 2. detector-miss rescue (all)
    rescued = [k for k in lost_missed if cls[k] == 'CORRECT']
    out['miss_rescue'] = {'rule_lost_on_missed_ticks': len(lost_missed), 'rescued': len(rescued),
                          'rescued_own_box': 0, 'rescued_detection_box': len(rescued),
                          'rate': round(len(rescued) / len(lost_missed), 4) if lost_missed else None}
    ex = []                                                                            # 3. exit judgement (D)
    for d in case['decision_points']:
        if d['type'] in D_EXIT:
            w0, w1 = d['evaluation_window_us']
            stale = sum(1 for k, t in by.items() if w0 <= t.t_us <= w1 and t.shown_camera is not None and t.shown_camera not in t.visible)
            ex.append({'tick': d['tick'], 'type': d['type'], 'correct': S.decision_point_correct(ticks, d['timestamp_us']),
                       'stale_old_camera_s': round(stale * TICK_US / 1e6, 2)})
    if ex:
        out['exit'] = ex
    switches = wrong = 0                                                               # 4. wrong switches (all)
    prev = None
    for k in sorted(by):
        cam = by[k].shown_camera
        if cam is not None and cam != prev:
            switches += 1
            wrong += cls[k] in BAD
        prev = cam
    out['switches'] = {'total': switches, 'wrong': wrong}
    return out


def load_scorer(path: Path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SCORER_SHA:
        raise SystemExit('SCORER_SHA_MISMATCH')
    spec = importlib.util.spec_from_file_location('e3_scoring_pinned', path)
    m = importlib.util.module_from_spec(spec)
    sys.modules['e3_scoring_pinned'] = m      # dataclasses need the module registered
    spec.loader.exec_module(m)
    return m


def run_scores(S, case, a_log, b_doc, b1_class=None, missed=frozenset()):
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
    return {'primary': prim, 'iou': iou, 'decision_points': dps, 'n_ticks': len(ticks), 'k': b_doc.get('k'),
            'classes': {t.t_us // TICK_US: S.classify(t) for t in ticks},
            'diag': diagnostics(S, case, ticks, b1_class or {}, missed), 'api_breakdown': api_breakdown(calls),
            'images': {c['request']['t_s']: c['request']['images'] for c in calls if c.get('request')},
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
    ap.add_argument('--source', nargs=3, action='append', required=True, metavar=('ROOT', 'CATALOG', 'RUNS'),
                    help='E3 root, its case catalog (cases[].gt_path/gt_sha256/decision_points) and the runs folder; repeatable')
    ap.add_argument('--scorer', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--table', type=Path, default=None, help='per-segment Markdown table')
    a = ap.parse_args()
    S = load_scorer(a.scorer)
    per, all_cases, catalogs = {}, [], {}            # per: (case, arm) -> [run scores]
    for root, cat_path, runs in a.source:
        root, cat_path, runs = Path(root), Path(cat_path), Path(runs)
        catalog = json.loads(cat_path.read_text())
        catalogs[str(cat_path.name)] = hashlib.sha256(cat_path.read_bytes()).hexdigest()
        for case in catalog['cases']:
            cid = case['case_id']
            a_raw = (root / case['gt_path']).read_bytes()
            if hashlib.sha256(a_raw).hexdigest() != case['gt_sha256']:
                raise SystemExit('GT_PIN_MISMATCH ' + cid)
            a_log = json.loads(a_raw)
            files = sorted((runs / cid).glob('*.json')) if (runs / cid).is_dir() else []
            if not files:
                continue
            all_cases.append(case)
            missed = missed_ticks(S, root, case, a_log)
            docs = [json.loads(f.read_text()) for f in files]
            b1 = next((d for d in docs if d['arm'] == 'B1'), None)
            b1_class = run_scores(S, case, a_log, b1)['classes'] if b1 else {}
            for b in docs:
                per.setdefault((cid, b['arm']), []).append(run_scores(S, case, a_log, b, b1_class, missed))
    arms = sorted({k[1] for k in per})
    cases = all_cases
    fam = {c['case_id']: c['family'] for c in cases}
    has = lambda cid, arm: (cid, arm) in per

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
        common = [c for c in cases if has(c['case_id'], arm_a) and has(c['case_id'], arm_b)]
        for c in common:
            sa, sb = seg(c['case_id'], arm_a, crit), seg(c['case_id'], arm_b, crit)
            if sa and sb:
                clusters[c['case_id']] = (sa, sb)
        if not clusters:
            return None
        wp = lambda vs: sum(x[0]['wp_s'] - x[1]['wp_s'] for x in vs)
        fr = lambda vs: (sum(x[0]['correct'] for x in vs) / sum(x[0]['visible'] for x in vs)) - (sum(x[1]['correct'] for x in vs) / sum(x[1]['visible'] for x in vs))
        vals = list(clusters.values())
        pairs = []
        for c in common:
            pairs += list(zip(dp_majority(c['case_id'], arm_a), dp_majority(c['case_id'], arm_b)))
        return {'wp_diff': round(wp(vals), 3), 'wp_diff_ci': S.cluster_bootstrap(clusters, wp), 'follow_diff': round(fr(vals), 4),
                'follow_diff_ci': S.cluster_bootstrap(clusters, fr), 'mcnemar': S.mcnemar(pairs), 'n_points': len(pairs),
                'n_segments': len(clusters), 'segments': sorted(clusters)}

    report = {'schema_version': 'e3-f4.report.v2', 'scorer_sha256': SCORER_SHA, 'catalog_sha256': catalogs,
              'cases': [c['case_id'] for c in cases], 'arms': arms, 'identity': 'UNCONFIRMED', 'per_case': {}, 'per_arm': {}, 'comparisons': {},
              'verdicts': {}}
    report['stop'] = {'gt_unknown': [], 'api_errors': [], 'image_parity': []}
    for c in cases:
        for arm in arms:
            if not has(c['case_id'], arm):
                continue
            rs = per[(c['case_id'], arm)]
            report['per_case'][f"{c['case_id']}|{arm}"] = {'family': c['family'], 'primary': seg(c['case_id'], arm), 'iou': seg(c['case_id'], arm, 'iou'),
                                                           'dp_majority': dp_majority(c['case_id'], arm), 'k': len(rs),
                                                           'api': [r['api'] for r in rs], 'api_breakdown': [r['api_breakdown'] for r in rs],
                                                           'diag_per_run': [r['diag'] for r in rs]}
            if (seg(c['case_id'], arm) or {}).get('gt_unknown_stop'):
                report['stop']['gt_unknown'].append(f"{c['case_id']}|{arm}")
            for r in rs:
                if r['api_breakdown']['error_stop']:
                    report['stop']['api_errors'].append({'run': f"{c['case_id']}|{arm}|k{r['k']}", **{k: r['api_breakdown'][k] for k in ('calls', 'timeout', 'error', 'budget_denied', 'error_rate')}})
        if has(c['case_id'], 'A1') and has(c['case_id'], 'A2'):                    # §9: A1/A2 images identical at the same capture time
            for r1, r2 in zip(sorted(per[(c['case_id'], 'A1')], key=lambda r: r['k']), sorted(per[(c['case_id'], 'A2')], key=lambda r: r['k'])):
                same_t = set(r1['images']) & set(r2['images'])
                bad = [t for t in same_t if r1['images'][t] != r2['images'][t]]
                report['stop']['image_parity'].append({'case': c['case_id'], 'k': r1['k'], 'shared_times': len(same_t), 'mismatch': len(bad)})
    for arm in arms:
        acases = [c for c in cases if has(c['case_id'], arm)]
        segs = [seg(c['case_id'], arm) for c in acases]
        dpm = sum((dp_majority(c['case_id'], arm) for c in acases), [])
        tops = [[dp for dp in r['decision_points'] if 'topk' in dp] for c in acases for r in per[(c['case_id'], arm)]]
        flat = [d for t in tops for d in t]
        api = [r['api'] for c in acases for r in per[(c['case_id'], arm)]]
        brk = [r['api_breakdown'] for c in acases for r in per[(c['case_id'], arm)]]
        lat = sorted(x for a_ in api for x in a_['latency_ms'])
        report['per_arm'][arm] = {
            'wrong_person_s': round(sum(s['wp_s'] for s in segs), 3), 'follow_rate': round(sum(s['correct'] for s in segs) / sum(s['visible'] for s in segs), 4),
            'lost_s': round(sum(s['lost_s'] for s in segs), 3), 'false_lock_s': round(sum(s['false_lock_s'] for s in segs), 3),
            'dp_correct': sum(dpm), 'dp_total': len(dpm), 'gt_unknown_stop': any(s['gt_unknown_stop'] for s in segs),
            'segments': [c['case_id'] for c in acases],
            'by_family': {f: {'wrong_person_s': round(sum(seg(c['case_id'], arm)['wp_s'] for c in acases if c['family'] == f), 3),
                              'dp_correct': sum(sum(dp_majority(c['case_id'], arm)) for c in acases if c['family'] == f),
                              'dp_total': sum(len(dp_majority(c['case_id'], arm)) for c in acases if c['family'] == f)}
                          for f in sorted({c['family'] for c in acases})},
            'api_breakdown': {k: sum(b[k] for b in brk) for k in ('calls', 'applied', 'agent_not_applied', 'expired', 'timeout', 'error', 'budget_denied', 'answered_no_effect')},
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
            if idx and has(cc['case_id'], 'A2') and has(cc['case_id'], 'B2'):
                a2, b2 = dp_majority(cc['case_id'], 'A2'), dp_majority(cc['case_id'], 'B2')
                dcl[cc['case_id']] = [(a2[i], b2[i]) for i in idx]
        dstat = lambda vs: (sum(a for v in vs for a, _ in v) - sum(b for v in vs for _, b in v)) / max(1, sum(len(v) for v in vs))
        dci = S.cluster_bootstrap(dcl, dstat) if dcl else [0.0, 0.0]
        report['verdicts']['H2'] = S.verdict_h2(cmp['A1-B1']['wp_diff_ci'], cmp['A2-B2']['wp_diff_ci'], dci, cmp['A2-B1']['n_points'], cmp['A2-B1']['n_segments'])
        report['verdicts']['H2']['d_exit_diff_ci'] = dci
    if 'A2' in arms and 'A1' in arms:
        def tclusters(arm):
            return {c['case_id']: [d['topk']['hit1'] for r in per[(c['case_id'], arm)] for d in r['decision_points'] if 'topk' in d]
                    for c in cases if has(c['case_id'], 'A1') and has(c['case_id'], 'A2')}
        t2, t1 = tclusters('A2'), tclusters('A1')
        both = {k: (t2[k], t1[k]) for k in t2 if t2[k]}
        diff = lambda vs: sum(sum(a) for a, _ in vs) / max(1, sum(len(a) for a, _ in vs)) - sum(sum(b) for _, b in vs) / max(1, sum(len(b) for _, b in vs))
        rate2 = lambda vs: sum(sum(a) for a, _ in vs) / max(1, sum(len(a) for a, _ in vs))
        pa2, pa1 = report['per_arm']['A2'], report['per_arm']['A1']
        h4c = [c for c in cases if has(c['case_id'], 'A1') and has(c['case_id'], 'A2')]
        lat2 = mean([seg(c['case_id'], 'A2')['reacq_median_s'] for c in h4c]); lat1 = mean([seg(c['case_id'], 'A1')['reacq_median_s'] for c in h4c])
        n_re = sum(1 for c in h4c for d in c['decision_points'] if d['type'] in REAPPEAR)
        report['verdicts']['H4'] = S.verdict_h4(S.cluster_bootstrap(both, diff) or [0, 0], pa2['top1'][0] / max(1, pa2['top1'][1]), pa2['random_top1'],
                                                S.cluster_bootstrap(both, rate2) or [0, 0], lat2, lat1, n_re)
    report['diagnostics_h2'] = {}                                                  # D350: per segment and arm (K mean + each run)
    for c in cases:
        for arm in arms:
            if not has(c['case_id'], arm):
                continue
            ds = [r['diag'] for r in per[(c['case_id'], arm)]]
            row = {'switches_wrong': mean([d['switches']['wrong'] for d in ds]), 'switches_total': mean([d['switches']['total'] for d in ds]),
                   'miss_rule_lost': ds[0]['miss_rescue']['rule_lost_on_missed_ticks'], 'miss_rescued': mean([d['miss_rescue']['rescued'] for d in ds])}
            if 'occlusion' in ds[0]:
                row['occlusion_keep_rate'] = mean([d['occlusion']['keep_rate'] for d in ds])
                row['occlusion_false_lock_s'] = mean([d['occlusion']['false_lock_s'] for d in ds])
            if 'exit' in ds[0]:
                row['exit_correct_majority'] = [S.majority([d['exit'][i]['correct'] for d in ds]) for i in range(len(ds[0]['exit']))]
                row['exit_stale_old_camera_s'] = mean([sum(e['stale_old_camera_s'] for e in d['exit']) for d in ds])
            row['per_run'] = ds
            report['diagnostics_h2'][f"{c['case_id']}|{arm}"] = row
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=list))
    if a.table:
        lines = ['| 段 | 類 | 組 | K | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對（多數決） | 錯誤切鏡／總切鏡 | 漏偵測補救 | 遮擋維持率 | 離開判斷對 |',
                 '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        f2 = lambda v, n=2: '—' if v is None else (f'{v:.{n}f}' if isinstance(v, float) else str(v))
        for c in cases:
            for arm in arms:
                key = f"{c['case_id']}|{arm}"
                if key not in report['per_case']:
                    continue
                pc, dg = report['per_case'][key], report['diagnostics_h2'][key]
                p = pc['primary'] or {}
                fr = p['correct'] / p['visible'] if p.get('visible') else None
                ex = dg.get('exit_correct_majority')
                lines.append(f"| {c['case_id']} | {c['family']} | {arm} | {pc['k']} | {f2(p.get('wp_s'))} | {f2(fr, 3)} | {f2(p.get('lost_s'))} | "
                             f"{f2(p.get('false_lock_s'))} | {sum(pc['dp_majority'])}/{len(pc['dp_majority'])} | {f2(dg['switches_wrong'], 1)}/{f2(dg['switches_total'], 1)} | "
                             f"{f2(dg['miss_rescued'], 1)}/{dg['miss_rule_lost']} | {f2(dg.get('occlusion_keep_rate'), 3)} | {'—' if ex is None else f'{sum(ex)}/{len(ex)}'} |")
        a.table.write_text('\n'.join(lines) + '\n')
    print('WROTE', a.out, 'segments', len(cases), 'arms', arms, 'stop', json.dumps({k: len(v) for k, v in report['stop'].items()}))


if __name__ == '__main__':
    main()

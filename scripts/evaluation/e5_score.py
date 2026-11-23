"""E5 (#684) scoring wrapper for the A-open arms (AO offline, AOL simulated live) against B1/B2 (E3 runs, not rerun).

Scoring side only. Reads ``e5.b-log.v1`` files from ``e5_run.py`` (contract docs/contracts/E5_AOPEN_INTERFACE_V1.md §7) and the E3
B logs, plus the private GT sidecars exactly as ``e3_f4_score`` does. Tracking is scored by ``e3_f4_score.run_scores`` (imported, never
modified; it reads ``rows[].tracking`` and ``rows[].ranking`` only, an empty ranking is a miss for H8c). The E5 API categories of
contract §7 are normalised here, because ``e3_f4_score.api_breakdown`` knows only the E3 reasons (it would count OCCLUDED_NO_TARGET
as an error). Verdicts follow preregistration §5 (docs/evaluation/E5_PREREGISTRATION_20261123.md): H8a = ``verdict_h1`` of the pinned
scorer, H8b / H8c as written there, H8d = AOL vs B1 judged apart (K=1). No threshold is invented here; what the preregistration does
not define is reported as UNKNOWN. Identity stays UNCONFIRMED.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


F = sys.modules.get('e3_f4_score') or _load('e3_f4_score', HERE / 'e3_f4_score.py')

SCHEMA_IN, SCHEMA_OUT = 'e5.b-log.v1', 'e5.report.v1'
E5_ARMS = ('AO', 'AOL')
PROVIDER_ERRORS = ('PROVIDER_TIMEOUT', 'PROVIDER_ERROR')            # contract §7 table; preregistration §7 10 % stop (D352: missing data)
FORMAT_REJECTS = ('FORMAT_INVALID', 'UNKNOWN_DETECTION', 'BAD_OWN_BOX', 'BAD_CAMERA')   # pilot 20 % gate
BUDGET_DENIED = 'CALL_BUDGET_EXHAUSTED'
EXPIRED = 'EXPIRED'                                                # AOL only
OCCLUDED_NO_TARGET = 'OCCLUDED_NO_TARGET'                          # a valid call, not an error
CALL_CAP_EVENT = 'CALL_CAP_REACHED'                                # control event in rows[].events, never a call
PROVIDER_ERROR_CAP = 0.10                                          # preregistration §7
FORMAT_RETURN_CAP = 0.20                                           # preregistration §7 (pilot)
KNOWN_REASONS = set(PROVIDER_ERRORS) | set(FORMAT_REJECTS) | {BUDGET_DENIED, EXPIRED, OCCLUDED_NO_TARGET}


def normalize_calls(calls, rows=()):
    """Contract §7 categories for one run. Rates are over ``calls[]`` (CALL_CAP_REACHED is an event, not a call)."""
    n = len(calls)
    out = {'calls': n, 'provider_timeout': 0, 'provider_error': 0, 'format_rejected': 0, 'format_reasons': {}, 'budget_denied': 0,
           'expired': 0, 'occluded_no_target': 0, 'unknown_reasons': {}, 'applied': 0, 'valid_calls': 0, 'answer_counts': {}}
    for c in calls:
        r = c.get('fallback_reason')
        if c.get('applied'):
            out['applied'] += 1
        if r == 'PROVIDER_TIMEOUT':
            out['provider_timeout'] += 1
        elif r == 'PROVIDER_ERROR':
            out['provider_error'] += 1
        elif r in FORMAT_REJECTS:
            out['format_rejected'] += 1
            out['format_reasons'][r] = out['format_reasons'].get(r, 0) + 1
        elif r == BUDGET_DENIED:
            out['budget_denied'] += 1
        elif r == EXPIRED:
            out['expired'] += 1
        elif r == OCCLUDED_NO_TARGET:
            out['occluded_no_target'] += 1          # valid call: the Agent answered, the answer just had nothing to attach to
        elif r:
            out['unknown_reasons'][r] = out['unknown_reasons'].get(r, 0) + 1
        if r in PROVIDER_ERRORS or r in FORMAT_REJECTS or r == BUDGET_DENIED or (r and r not in KNOWN_REASONS):
            continue
        out['valid_calls'] += 1
        a = c.get('answer')
        if a:
            out['answer_counts'][a] = out['answer_counts'].get(a, 0) + 1
    out['provider_errors'] = out['provider_timeout'] + out['provider_error']
    out['call_cap_reached'] = sum(1 for r in rows for e in r.get('events') or [] if e.get('type') == CALL_CAP_EVENT)
    out['provider_error_rate'] = round(out['provider_errors'] / n, 4) if n else 0.0
    out['format_return_rate'] = round(out['format_rejected'] / n, 4) if n else 0.0
    out['provider_error_stop'] = out['provider_error_rate'] > PROVIDER_ERROR_CAP     # D352: missing data, not excluded, not rerun
    out['format_return_flag'] = out['format_return_rate'] > FORMAT_RETURN_CAP         # pilot gate: fix prompt/parser, no paid rerun
    out['rerun_needed_budget'] = out['budget_denied'] > 0                            # D352 rerun rule (all K, old files kept)
    return out


def run_e5(S, case, a_log, doc, b1_class=None, missed=frozenset()):
    """``e3_f4_score.run_scores`` plus the E5 call normalisation (the E3 ``api_breakdown`` in the result is ignored for E5 arms)."""
    if doc.get('arm') in E5_ARMS and doc.get('schema_version') != SCHEMA_IN:
        raise ValueError(f"SCHEMA_MISMATCH {doc.get('schema_version')}")
    r = F.run_scores(S, case, a_log, doc, b1_class, missed)
    if doc.get('arm') in E5_ARMS:
        r['e5'] = normalize_calls(doc.get('calls') or [], doc.get('rows') or [])
        r.pop('api_breakdown', None)
        if doc['arm'] == 'AO' and r['e5']['expired']:
            r['e5']['arm_warning'] = 'EXPIRED_IN_OFFLINE_ARM'
    return r


def mean(xs):
    return F.mean(xs)


def verdict_h8b(fl_diff_ci, S):
    """Preregistration H8b: supported when the AO - B1 blind-lock-seconds interval is wholly below 0, not supported when wholly above."""
    s = fl_diff_ci and S.side(fl_diff_ci)
    v = None if fl_diff_ci is None else {'below': 'SUPPORTED', 'above': 'NOT_SUPPORTED'}.get(s, 'INCONCLUSIVE')
    return _v(v, {'false_lock_diff_side': s, 'ci': fl_diff_ci})


def verdict_h8c(top1_diff_ci, ao_top1, ao_random_top1):
    """Preregistration H8c: supported when the lower bound > 0; not supported when the upper bound < 0 or AO top-1 <= random expectation
    (checked first, as ``verdict_h1`` checks 'against' first); otherwise inconclusive."""
    if top1_diff_ci is None or ao_top1 is None:
        return _v(None, {'reason': 'NO_REAPPEARANCE_POINTS'})
    against = top1_diff_ci[1] < 0 or (ao_random_top1 is not None and ao_top1 <= ao_random_top1)
    ok = top1_diff_ci[0] > 0
    v = 'NOT_SUPPORTED' if against else 'SUPPORTED' if ok else 'INCONCLUSIVE'
    return _v(v, {'top1_diff_ci': top1_diff_ci, 'ao_top1': round(ao_top1, 4), 'random_top1': ao_random_top1})


def _v(verdict, reasons, **extra):
    zh = {'SUPPORTED': '成立', 'NOT_SUPPORTED': '不成立', 'INCONCLUSIVE': '無法判斷', 'EXPLORATORY': '探索性', None: 'UNKNOWN'}
    return {'verdict': verdict or 'UNKNOWN', 'verdict_zh': zh[verdict], 'reasons': reasons, **extra}


def build_report(S, cases, per, catalogs=None):
    """``per``: (case_id, arm) -> [run score dicts]. Returns the E5 report dict (preregistration §5, §8)."""
    arms = sorted({k[1] for k in per})
    has = lambda cid, arm: (cid, arm) in per
    fam = {c['case_id']: c['family'] for c in cases}

    def seg(cid, arm, crit='primary'):
        ms = [r[crit] for r in per[(cid, arm)] if r[crit].get('available')]
        if not ms:
            return None
        return {'wp_s': mean([m['wrong_person_s'] for m in ms]),
                'correct': mean([m['follow_rate'] * m['visible_ticks'] for m in ms if m['follow_rate'] is not None]),
                'visible': mean([m['visible_ticks'] for m in ms]), 'lost_s': mean([m['lost_s'] for m in ms]),
                'false_lock_s': mean([m['false_lock_s'] for m in ms]), 'gt_unknown_stop': any(m['gt_unknown_stop'] for m in ms)}

    def dpm(cid, arm):
        rs = per[(cid, arm)]
        return [S.majority([r['decision_points'][i]['correct'] for r in rs]) for i in range(len(rs[0]['decision_points']))]

    def compare(x, y, crit='primary'):
        clusters = {}
        for c in cases:
            if has(c['case_id'], x) and has(c['case_id'], y):
                sa, sb = seg(c['case_id'], x, crit), seg(c['case_id'], y, crit)
                if sa and sb:
                    clusters[c['case_id']] = (sa, sb)
        if not clusters:
            return None
        wp = lambda vs: sum(a['wp_s'] - b['wp_s'] for a, b in vs)
        fl = lambda vs: sum(a['false_lock_s'] - b['false_lock_s'] for a, b in vs)
        fr = lambda vs: (sum(a['correct'] for a, _ in vs) / sum(a['visible'] for a, _ in vs)) - (sum(b['correct'] for _, b in vs) / sum(b['visible'] for _, b in vs))
        pairs = [p for cid in clusters for p in zip(dpm(cid, x), dpm(cid, y))]
        vals = list(clusters.values())
        return {'wp_diff': round(wp(vals), 3), 'wp_diff_ci': S.cluster_bootstrap(clusters, wp),
                'false_lock_diff': round(fl(vals), 3), 'false_lock_diff_ci': S.cluster_bootstrap(clusters, fl),
                'follow_diff': round(fr(vals), 4), 'follow_diff_ci': S.cluster_bootstrap(clusters, fr), 'mcnemar': S.mcnemar(pairs),
                'n_points': len(pairs), 'n_segments': len(clusters), 'segments': sorted(clusters)}

    def topk(x, y):
        """Per-segment (x hits, y hits) lists over the reappearance points of every K run; pooled-rate difference x - y."""
        cl, rand = {}, []
        for c in cases:
            cid = c['case_id']
            if not (has(cid, x) and has(cid, y)):
                continue
            h = lambda arm, key: [d['topk'][key] for r in per[(cid, arm)] for d in r['decision_points'] if 'topk' in d]
            a1, a3, b1, b3 = h(x, 'hit1'), h(x, 'hit3'), h(y, 'hit1'), h(y, 'hit3')
            if a1 and b1:
                cl[cid] = (a1, b1, a3, b3)
            rand += [d['topk']['random1'] for r in per[(cid, x)] for d in r['decision_points'] if 'topk' in d and d['topk']['random1'] is not None]
        if not cl:
            return None
        rate = lambda vs, i: sum(sum(v[i]) for v in vs) / max(1, sum(len(v[i]) for v in vs))
        diff1 = lambda vs: rate(vs, 0) - rate(vs, 1)
        vals = list(cl.values())
        return {'top1_diff': round(diff1(vals), 4), 'top1_diff_ci': S.cluster_bootstrap(cl, diff1), 'x_top1': rate(vals, 0), 'y_top1': rate(vals, 1),
                'x_top3': rate(vals, 2), 'y_top3': rate(vals, 3), 'x_points': sum(len(v[0]) for v in vals), 'y_points': sum(len(v[1]) for v in vals),
                'x_random_top1': round(mean(rand) or 0.0, 4), 'n_segments': len(cl)}

    report = {'schema_version': SCHEMA_OUT, 'scorer_sha256': F.SCORER_SHA, 'catalog_sha256': catalogs or {}, 'identity': 'UNCONFIRMED',
              'cases': [c['case_id'] for c in cases], 'arms': arms, 'per_case': {}, 'per_arm': {}, 'comparisons': {}, 'verdicts': {}, 'stop': {}}
    stop = {'provider_error_runs': [], 'format_return_runs': [], 'budget_denied_runs': [], 'gt_unknown': [], 'unknown_reasons': []}
    for c in cases:
        for arm in arms:
            if not has(c['case_id'], arm):
                continue
            rs = per[(c['case_id'], arm)]
            e5 = [r['e5'] for r in rs if 'e5' in r]
            report['per_case'][f"{c['case_id']}|{arm}"] = {'family': c['family'], 'k': len(rs), 'primary': seg(c['case_id'], arm), 'dp_majority': dpm(c['case_id'], arm),
                                                           'e5_calls': e5 or None}
            if (seg(c['case_id'], arm) or {}).get('gt_unknown_stop'):
                stop['gt_unknown'].append(f"{c['case_id']}|{arm}")
            for r in rs:
                if 'e5' not in r:
                    continue
                run = f"{c['case_id']}|{arm}|k{r['k']}"
                e = r['e5']
                if e['provider_error_stop']:
                    stop['provider_error_runs'].append({'run': run, 'rate': e['provider_error_rate'], 'calls': e['calls']})
                if e['format_return_flag']:
                    stop['format_return_runs'].append({'run': run, 'rate': e['format_return_rate'], 'calls': e['calls']})
                if e['rerun_needed_budget']:
                    stop['budget_denied_runs'].append({'run': run, 'budget_denied': e['budget_denied']})
                if e['unknown_reasons']:
                    stop['unknown_reasons'].append({'run': run, 'reasons': e['unknown_reasons']})
    report['stop'] = stop
    keys = ('calls', 'provider_timeout', 'provider_error', 'provider_errors', 'format_rejected', 'budget_denied', 'expired', 'occluded_no_target',
            'applied', 'valid_calls', 'call_cap_reached')
    for arm in arms:
        acases = [c for c in cases if has(c['case_id'], arm)]
        segs = [seg(c['case_id'], arm) for c in acases]
        dps = sum((dpm(c['case_id'], arm) for c in acases), [])
        flat = [d for c in acases for r in per[(c['case_id'], arm)] for d in r['decision_points'] if 'topk' in d]
        runs = [r for c in acases for r in per[(c['case_id'], arm)]]
        e5 = [r['e5'] for r in runs if 'e5' in r]
        lat = sorted(x for r in runs for x in r['api']['latency_ms'])
        pa = {'segments': [c['case_id'] for c in acases], 'wrong_person_s': round(sum(s['wp_s'] for s in segs), 3),
              'follow_rate': round(sum(s['correct'] for s in segs) / sum(s['visible'] for s in segs), 4), 'lost_s': round(sum(s['lost_s'] for s in segs), 3),
              'false_lock_s': round(sum(s['false_lock_s'] for s in segs), 3), 'dp_correct': sum(dps), 'dp_total': len(dps),
              'top1': (sum(d['topk']['hit1'] for d in flat), len(flat)), 'top3': (sum(d['topk']['hit3'] for d in flat), len(flat)),
              'random_top1': round(mean([d['topk']['random1'] for d in flat if d['topk']['random1'] is not None]) or 0.0, 4),
              'ranked_points': sum(1 for d in flat if d['topk']['ranked']),
              'latency_ms_p50': lat[len(lat) // 2] if lat else None, 'latency_ms_p95': lat[min(len(lat) - 1, int(.95 * len(lat)))] if lat else None,
              'input_tokens': sum(r['api']['input_tokens'] for r in runs), 'output_tokens': sum(r['api']['output_tokens'] for r in runs),
              'cost_usd': 'UNKNOWN (not in the run log; read the ApiGuard ledger)'}
        if e5:
            pa['e5_calls'] = {k: sum(e[k] for e in e5) for k in keys}
            n = pa['e5_calls']['calls']
            pa['e5_calls']['provider_error_rate'] = round(pa['e5_calls']['provider_errors'] / n, 4) if n else 0.0
            pa['e5_calls']['format_return_rate'] = round(pa['e5_calls']['format_rejected'] / n, 4) if n else 0.0
            ans = {}
            for e in e5:
                for k, v in e['answer_counts'].items():
                    ans[k] = ans.get(k, 0) + v
            pa['e5_calls']['answer_counts'] = ans
        report['per_arm'][arm] = pa
    for x in ('AO', 'AOL'):
        if x in arms and 'B1' in arms:
            report['comparisons'][f'{x}-B1'] = compare(x, 'B1')
            report['comparisons'][f'{x}-B1|iou'] = compare(x, 'B1', 'iou')
            report['comparisons'][f'{x}-B1|topk'] = topk(x, 'B1')
            ic = compare(x, 'B1', 'iou_conservative')
            report['comparisons'][f'{x}-B1|iou_conservative'] = ic and {k: ic[k] for k in ('follow_diff', 'follow_diff_ci', 'wp_diff', 'wp_diff_ci', 'n_segments')}
    if 'AO' in arms and 'B2' in arms:
        report['comparisons']['B2-B1'] = compare('B2', 'B1') if 'B1' in arms else None   # attached only, no verdict
    cmp = report['comparisons']
    for x, h_main, h_b, h_c in (('AO', 'H8a', 'H8b', 'H8c'), ('AOL', 'H8d', None, None)):
        c = cmp.get(f'{x}-B1')
        if not c:
            continue
        iou_cons = cmp.get(f'{x}-B1|iou_conservative') or {}
        v = S.verdict_h1(c['wp_diff_ci'], c['follow_diff_ci'], c['mcnemar'], c['n_points'], c['n_segments'], iou_cons.get('follow_diff'))
        v['n_points'], v['n_segments'] = c['n_points'], c['n_segments']
        if x == 'AOL':
            v['note'] = 'K=1 (preregistration §5 H8d); judged apart from AO'
        report['verdicts'][h_main] = v
        if h_b:
            report['verdicts'][h_b] = verdict_h8b(c['false_lock_diff_ci'], S)
        if h_c:
            t = cmp.get(f'{x}-B1|topk')
            report['verdicts'][h_c] = verdict_h8c(t and t['top1_diff_ci'], t and t['x_top1'], t and t['x_random_top1'])
            if t:
                report['verdicts'][h_c]['denominator'] = {'AO_points': t['x_points'], 'B1_points': t['y_points']}
    if 'AOL' not in arms:
        report['verdicts']['H8d'] = _v(None, {'reason': 'NOT_RUN'}, note='未執行')
    return report


def render_md(report):
    """Human-readable skeleton for docs/operations/E5_REPORT_*.md (the tables only; the report itself is written separately)."""
    f = lambda v, n=2: '—' if v is None else (f'{v:.{n}f}' if isinstance(v, float) else str(v))
    L = ['<!-- generated by scripts/evaluation/e5_score.py; skeleton only -->', '## 判定（預登 §5；評分器 SHA-256 ' + report['scorer_sha256'][:8] + '…）', '',
         '| 假設 | 判定 | 說明 |', '|---|---|---|']
    for h in ('H8a', 'H8b', 'H8c', 'H8d'):
        v = report['verdicts'].get(h)
        if v:
            L.append(f"| {h} | {v['verdict_zh']}（{v['verdict']}） | {json.dumps(v.get('reasons'), ensure_ascii=False, default=list)}{'；' + v['note'] if v.get('note') else ''} |")
    L += ['', '## 組別合計', '', '| 組 | 段數 | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對 | top-1 | top-3 | 有排名點 | 延遲 p50／p95 ms | 輸入／輸出 token |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for arm, a in report['per_arm'].items():
        L.append(f"| {arm} | {len(a['segments'])} | {f(a['wrong_person_s'])} | {f(a['follow_rate'], 3)} | {f(a['lost_s'])} | {f(a['false_lock_s'])} | {a['dp_correct']}/{a['dp_total']} | "
                 f"{a['top1'][0]}/{a['top1'][1]} | {a['top3'][0]}/{a['top3'][1]} | {a['ranked_points']} | {f(a['latency_ms_p50'], 0)}／{f(a['latency_ms_p95'], 0)} | {a['input_tokens']}／{a['output_tokens']} |")
    L += ['', '## 呼叫分類（契約 §7）', '', '| 組 | 呼叫 | 有效 | 套用 | provider 錯誤（逾時／其他） | 錯誤率 | 格式退回 | 退回率 | 預算拒絕 | EXPIRED | OCCLUDED_NO_TARGET | CALL_CAP_REACHED | 回答分佈 |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for arm, a in report['per_arm'].items():
        e = a.get('e5_calls')
        if e:
            L.append(f"| {arm} | {e['calls']} | {e['valid_calls']} | {e['applied']} | {e['provider_errors']}（{e['provider_timeout']}／{e['provider_error']}） | {e['provider_error_rate']:.4f} | "
                     f"{e['format_rejected']} | {e['format_return_rate']:.4f} | {e['budget_denied']} | {e['expired']} | {e['occluded_no_target']} | {e['call_cap_reached']} | {json.dumps(e['answer_counts'], ensure_ascii=False)} |")
    s = report['stop']
    L += ['', '## 停止旗標', '', f"- provider 錯誤 > 10%（D352，缺漏資料，不排除、不重跑）：{len(s['provider_error_runs'])} 個執行 {json.dumps(s['provider_error_runs'], ensure_ascii=False)}",
          f"- 格式退回 > 20%（試跑門檻）：{len(s['format_return_runs'])} 個執行 {json.dumps(s['format_return_runs'], ensure_ascii=False)}",
          f"- 預算拒絕（D352：K 次全部重跑，舊檔保留）：{len(s['budget_denied_runs'])} 個執行 {json.dumps(s['budget_denied_runs'], ensure_ascii=False)}",
          f"- GT_UNKNOWN 超過門檻：{json.dumps(s['gt_unknown'], ensure_ascii=False)}",
          f"- 契約表以外的 fallback_reason：{json.dumps(s['unknown_reasons'], ensure_ascii=False)}", '',
          '## 逐段', '', '| 段 | 組 | K | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對（多數決） | CALL_CAP_REACHED（各次合計） |', '|---|---|---|---|---|---|---|---|---|']
    for key, pc in report['per_case'].items():
        cid, arm = key.split('|')
        p = pc['primary'] or {}
        fr = p['correct'] / p['visible'] if p.get('visible') else None
        cap = sum(e['call_cap_reached'] for e in pc['e5_calls']) if pc['e5_calls'] else '—'
        L.append(f"| {cid} | {arm} | {pc['k']} | {f(p.get('wp_s'))} | {f(fr, 3)} | {f(p.get('lost_s'))} | {f(p.get('false_lock_s'))} | {sum(pc['dp_majority'])}/{len(pc['dp_majority'])} | {cap} |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', nargs=3, action='append', required=True, metavar=('ROOT', 'CATALOG', 'RUNS'),
                    help='E3 root, its case catalog and a runs folder (<runs>/<case>/*.json); repeat for the E3 B1/B2 runs and the E5 runs')
    ap.add_argument('--scorer', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--md', type=Path, default=None, help='Markdown skeleton for docs/operations/E5_REPORT_*.md')
    a = ap.parse_args()
    S = F.load_scorer(a.scorer)
    docs_by_case, case_by_id, a_logs, roots, catalogs = {}, {}, {}, {}, {}
    for root, cat_path, runs in a.source:
        root, cat_path, runs = Path(root), Path(cat_path), Path(runs)
        catalog = json.loads(cat_path.read_text())
        catalogs[cat_path.name] = hashlib.sha256(cat_path.read_bytes()).hexdigest()
        for case in catalog['cases']:
            cid = case['case_id']
            raw = (root / case['gt_path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != case['gt_sha256']:
                raise SystemExit('GT_PIN_MISMATCH ' + cid)
            files = sorted((runs / cid).glob('*.json')) if (runs / cid).is_dir() else []
            if not files:
                continue
            case_by_id[cid], a_logs[cid], roots[cid] = case, json.loads(raw), root
            docs_by_case.setdefault(cid, []).extend(json.loads(p.read_text()) for p in files)
    per, cases = {}, []
    for cid, docs in docs_by_case.items():
        case = case_by_id[cid]
        cases.append(case)
        missed = F.missed_ticks(S, roots[cid], case, a_logs[cid])
        b1 = next((d for d in docs if d['arm'] == 'B1'), None)
        b1_class = F.run_scores(S, case, a_logs[cid], b1)['classes'] if b1 else {}
        for d in docs:
            per.setdefault((cid, d['arm']), []).append(run_e5(S, case, a_logs[cid], d, b1_class, missed))
    report = build_report(S, cases, per, catalogs)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=list))
    if a.md:
        a.md.write_text(render_md(report))
    print('WROTE', a.out, 'segments', len(cases), 'arms', report['arms'], 'stop', json.dumps({k: len(v) for k, v in report['stop'].items()}))


if __name__ == '__main__':
    main()

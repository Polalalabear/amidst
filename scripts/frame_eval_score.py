"""W1 (#644) scoring: per-frame outcomes, per-stratum metrics, cluster-bootstrap paired differences, chart. GT only here (scoring side)."""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'scripts'))
import run_frame_eval as R  # noqa: E402
from amidst.evaluation import frame_eval as fe  # noqa: E402
from amidst.evaluation import gt_scoring_r004 as sc  # noqa: E402
from amidst.q1q5.openai_gateway import PRICES  # noqa: E402

POS = ['easy_visible', 'partial_occluded', 'partial_edge', 'far_small', 'lowscore_person', 'nonperson_class', 'visible_nobox']
NEG = ['neg_absent', 'neg_occluded', 'neg_with_similar']
HARD = ['partial_occluded', 'far_small', 'lowscore_person', 'nonperson_class', 'visible_nobox']
ARMS = {'rule': 'a 規則(HSV紅)', 'rule_nocolor': 'a\' 規則(不看顏色)', 'terra_vision_free': 'b 看圖+自畫框', 'terra_text': 'c 不給圖',
        'terra_vision_pick': 'd 看圖只選框', 'sol_vision_free': 'b-sol 看圖+自畫框'}
OUTS = ('TP', 'FP_wrong_box', 'FP_absent', 'FN', 'TN')
N_BOOT = 2000


def key(f):
    return (f['event'], f['camera'], f['t_us'])


def load():
    smp = R.load_sample()
    dets = {l: R.load_dets(l) for l in R.LABELS}
    labs = {(f['event'], f['camera'], f['t_us']): f['lab'] for f in json.load(open(R.OUT / 'frames_all_labels.json'))}
    gts = {l: sc.gt_traj(l) for l in R.LABELS}
    frames = {}
    for f in smp['frames']:
        k = key(f)
        ds = dets[f['event']][(f['camera'], f['t_us'])]
        body = sc.t_body(f['camera'], gts[f['event']][f['t_us']]) if f['t_us'] in gts[f['event']] else None
        frames[k] = {'dets': ds, 'by_id': {d['id']: d for d in ds}, 'lab': labs[k], 'body': body, 'strata': f['strata']}
    return smp, frames


def outcome_fracs(frames):
    """arm -> frame key -> {'out': {OUT: fraction over k}, 'iou': [..], 'lat': [..], 'tok': [(pt, ct, cached)], 'invalid': n}."""
    res = defaultdict(dict)
    for name, kw in (('rule', True), ('rule_nocolor', False)):
        for k, fr in frames.items():
            o = fe.score_frame(fe.rule_answer(fr['dets'], 'red', kw), fr['by_id'], fr['lab'], fr['body'])
            res[name][k] = {'out': {o['out']: 1.0}, 'iou': [o['iou']] if o['iou'] is not None else [], 'lat': [], 'tok': [], 'invalid': 0, 'src': [o['src']]}
    for f in sorted(R.OUT.glob('answers_*_k*.json')):
        d = json.loads(f.read_text())
        arm = f'{d["model"]}_{d["arm"]}'
        for a in d['answers']:
            k = key(a)
            fr = frames[k]
            ans = a.get('answer') if not a.get('error') else None
            o = fe.score_frame(ans, fr['by_id'], fr['lab'], fr['body'])
            if o['out'] == 'INVALID':   # no answer at all: counts as "not present"
                o = {'out': 'FN' if fr['lab']['present'] else 'TN', 'iou': None, 'src': None}
                inv = 1
            else:
                inv = 0
            cur = res[arm].setdefault(k, {'out': defaultdict(float), 'iou': [], 'lat': [], 'tok': [], 'invalid': 0, 'src': [], 'n': 0})
            cur['out'][o['out']] += 1
            cur['n'] += 1
            cur['invalid'] += inv
            if o['iou'] is not None:
                cur['iou'].append(o['iou'])
            cur['src'].append(o['src'])
            if a.get('latency_s'):
                cur['lat'].append(a['latency_s'])
            cur['tok'].append((a.get('prompt_tokens') or 0, a.get('completion_tokens') or 0, a.get('cached_tokens') or 0, d['api_model']))
    for arm, m in res.items():
        for k, cur in m.items():
            n = cur.get('n', 1)
            cur['out'] = {o: cur['out'].get(o, 0) / n for o in OUTS}
    return res


def sums(arm_res, keys):
    s = dict.fromkeys(OUTS, 0.0)
    for k in keys:
        for o, v in arm_res[k]['out'].items():
            s[o] += v
    return s


def metrics_from(s):
    tp, fpw, fpa, fn, tn = (s[o] for o in OUTS)
    p = tp / (tp + fpw + fpa) if tp + fpw + fpa else None
    r = tp / (tp + fpw + fn) if tp + fpw + fn else None
    f1 = (2 * p * r / (p + r) if p + r else 0.0) if p is not None and r is not None else None
    return {'precision': p, 'recall': r, 'f1': f1, 'tn_rate': tn / (tn + fpa) if tn + fpa else None, 'wrong_box_rate': fpw / (tp + fpw) if tp + fpw else None}


def cluster_of(k):
    return (k[0], k[1], k[2] // 5_000_000)


def boot(frames_by_set, stat_fn, n_boot=N_BOOT, seed=7):
    """stat_fn(resampled key lists dict set->[keys]) -> float|None; cluster bootstrap over 5 s blocks, all sets resampled together."""
    allk = sorted({k for ks in frames_by_set.values() for k in ks})
    cl = defaultdict(list)
    for k in allk:
        cl[cluster_of(k)].append(k)
    cids = sorted(cl)
    members = {s: set(ks) for s, ks in frames_by_set.items()}
    rng = random.Random(seed)
    est = []
    for _ in range(n_boot):
        pick = [cids[rng.randrange(len(cids))] for _ in cids]
        rs = {s: [k for c in pick for k in cl[c] if k in members[s]] for s in frames_by_set}
        v = stat_fn(rs)
        if v is not None:
            est.append(v)
    est.sort()
    if not est:
        return None
    return [round(est[int(.025 * len(est))], 3), round(est[min(len(est) - 1, int(.975 * len(est)))], 3)]


def main():
    smp, frames = load()
    res = outcome_fracs(frames)
    strata = defaultdict(list)
    for k, fr in frames.items():
        for s in fr['strata']:
            strata[s].append(k)
    neg_keys = sorted({k for s in NEG for k in strata[s]})
    all_keys = sorted(frames)
    arms = [a for a in ARMS if a in res and len(res[a]) == len(frames)]
    out = {'arms': arms, 'n_frames': len(frames), 'strata_n': {s: len(v) for s, v in strata.items()}, 'tercile_body_h_px': smp['tercile_body_h_px'],
           'available': {s: v['available'] for s, v in smp['per_stratum'].items()}}
    tab = {}
    for a in arms:
        t = {}
        for s in POS:
            ks = strata[s]
            if not ks:
                continue
            m = metrics_from(sums(res[a], ks))
            mp = metrics_from(sums(res[a], sorted(set(ks) | set(neg_keys))))
            t[s] = {'n': len(ks), 'recall': m['recall'], 'wrong_box_rate': m['wrong_box_rate'], 'precision_with_neg': mp['precision'], 'f1_with_neg': mp['f1']}
            ious = [i for k in ks for i in res[a][k]['iou']]
            t[s]['mean_iou_when_present_answer'] = round(sum(ious) / len(ious), 3) if ious else None
            own = [x for k in ks for x in res[a][k].get('src', [])]
            t[s]['own_box_share_of_answers'] = round(sum(x == 'OWN' for x in own) / max(1, sum(x in ('OWN', 'DET') for x in own)), 3)
        for s in NEG:
            ks = strata[s]
            if ks:
                m = metrics_from(sums(res[a], ks))
                t[s] = {'n': len(ks), 'tn_rate': m['tn_rate']}
        t['ALL'] = {'n': len(all_keys), **metrics_from(sums(res[a], all_keys))}
        lat = [x for k in res[a] for x in res[a][k]['lat']]
        toks = [x for k in res[a] for x in res[a][k]['tok']]
        t['cost'] = {'calls': len(toks), 'usd': round(sum(pt * PRICES[m][0] / 1e6 + ct * PRICES[m][1] / 1e6 for pt, ct, _c, m in toks), 3),
                     'prompt_tokens': sum(x[0] for x in toks), 'cached_tokens': sum(x[2] for x in toks),
                     'lat_p50': round(fe.percentile(lat, .5), 2) if lat else None, 'lat_p95': round(fe.percentile(lat, .95), 2) if lat else None,
                     'invalid_calls': sum(res[a][k]['invalid'] for k in res[a])}
        tab[a] = t
    out['table'] = tab

    def pair_recall(a, b, s):
        def stat(rs):
            ka = rs['s']
            if not ka:
                return None
            ma, mb = metrics_from(sums(res[a], ka)), metrics_from(sums(res[b], ka))
            return None if ma['recall'] is None else mb['recall'] - ma['recall']
        base = stat({'s': strata[s]})
        return {'diff': round(base, 3), 'ci95': boot({'s': strata[s]}, stat)} if base is not None else None

    def pair_prec(a, b, s):
        keys = sorted(set(strata[s]) | set(neg_keys))
        def stat(rs):
            ka = rs['s']
            pa, pb = metrics_from(sums(res[a], ka))['precision'], metrics_from(sums(res[b], ka))['precision']
            return None if pa is None or pb is None else pb - pa
        base = stat({'s': keys})
        return {'diff': round(base, 3), 'ci95': boot({'s': keys}, stat)} if base is not None else None

    def pair_tn(a, b, s):
        def stat(rs):
            ka = rs['s']
            return metrics_from(sums(res[b], ka))['tn_rate'] - metrics_from(sums(res[a], ka))['tn_rate'] if ka else None
        base = stat({'s': strata[s]})
        return {'diff': round(base, 3), 'ci95': boot({'s': strata[s]}, stat)}

    pairs = {}
    for a, b in (('rule', 'terra_vision_free'), ('rule', 'terra_text'), ('terra_text', 'terra_vision_free'), ('terra_vision_pick', 'terra_vision_free'),
                 ('rule', 'terra_vision_pick'), ('rule', 'sol_vision_free')):
        if a in arms and b in arms:
            p = {'recall': {s: pair_recall(a, b, s) for s in POS if strata[s]},
                 'precision_with_neg': {s: pair_prec(a, b, s) for s in POS if strata[s]},
                 'tn_rate': {s: pair_tn(a, b, s) for s in NEG if strata[s]}}
            pa = lambda ks: metrics_from(sums(res[a], ks))['f1']  # noqa: E731
            p['f1_all'] = {'diff': round(metrics_from(sums(res[b], all_keys))['f1'] - metrics_from(sums(res[a], all_keys))['f1'], 3)}
            pairs[f'{a}->{b}'] = p
    out['pairs'] = pairs
    # overall (stratified-sample) metrics with cluster-bootstrap CI, and paired overall differences
    out['overall_ci'] = {}
    for a in arms:
        o = {}
        for m in ('precision', 'recall', 'f1'):
            o[m] = {'est': round(metrics_from(sums(res[a], all_keys))[m], 3),
                    'ci95': boot({'s': all_keys}, lambda rs, a=a, m=m: metrics_from(sums(res[a], rs['s']))[m])}
        out['overall_ci'][a] = o
    out['overall_pairs'] = {}
    for a, b in (('rule', 'terra_vision_free'), ('rule', 'terra_text'), ('terra_text', 'terra_vision_free'), ('terra_vision_pick', 'terra_vision_free'), ('rule', 'sol_vision_free')):
        if a in arms and b in arms:
            out['overall_pairs'][f'{a}->{b}'] = {m: {'diff': round(metrics_from(sums(res[b], all_keys))[m] - metrics_from(sums(res[a], all_keys))[m], 3),
                'ci95': boot({'s': all_keys}, lambda rs, a=a, b=b, m=m: metrics_from(sums(res[b], rs['s']))[m] - metrics_from(sums(res[a], rs['s']))[m])} for m in ('precision', 'recall', 'f1')}
    # false-presence analysis of the free-box vision arm on negatives
    fpa = {}
    for arm in ('terra_vision_free', 'sol_vision_free'):
        if arm not in arms:
            continue
        rows = []
        for k in neg_keys:
            if res[arm][k]['out']['FP_absent'] > 0:
                rows.append({'frame': list(k), 'fp_share': round(res[arm][k]['out']['FP_absent'], 2), 'strata': frames[k]['strata'],
                             'n_red_person_boxes': frames[k]['lab']['n_other_red_persons'], 'src': sorted({x for x in res[arm][k]['src'] if x})})
        fpa[arm] = {'n_frames_with_any_fp': len(rows), 'by_camera': {c: sum(1 for r in rows if r['frame'][1] == c) for c in {r['frame'][1] for r in rows}}, 'rows': rows}
    out['fp_absent_analysis'] = fpa
    (R.OUT / 'w1_scores.json').write_text(json.dumps(out, indent=1))
    chart(out)
    print(json.dumps({'table': {a: {s: v for s, v in t.items() if s in POS + NEG + ['ALL', 'cost']} for a, t in tab.items()}}, indent=1)[:200])
    print('wrote', R.OUT / 'w1_scores.json')


def chart(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['PingFang TC', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    arms = [a for a in ('rule', 'terra_vision_free', 'terra_vision_pick', 'terra_text') if a in out['table']]
    cols = {'rule': '#7f8c8d', 'terra_vision_free': '#e67e22', 'terra_vision_pick': '#2c7fb8', 'terra_text': '#27ae60'}
    names = {'rule': 'a rule (RT-DETR+HSV)', 'terra_vision_free': 'b vision, free box', 'terra_vision_pick': 'd vision, pick box', 'terra_text': 'c no image'}
    ss = [s for s in POS if s in out['table']['rule']]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), gridspec_kw={'width_ratios': [3, 1.3]})
    ax = axes[0]
    w = 0.2
    for i, a in enumerate(arms):
        ax.bar([j + i * w for j in range(len(ss))], [out['table'][a][s]['f1_with_neg'] or 0 for s in ss], w, label=names[a], color=cols[a])
    ax.set_xticks([j + 1.5 * w for j in range(len(ss))])
    ax.set_xticklabels([f'{s}\n(n={out["table"]["rule"][s]["n"]})' for s in ss], fontsize=7)
    ax.set_ylabel('F1 (stratum + all negatives)')
    ax.set_ylim(0, 1)
    ax.legend(fontsize=7, ncol=4, loc='upper center', bbox_to_anchor=(0.5, -0.2), frameon=False)
    ax.set_title('Per-stratum F1 (frame level)', fontsize=9)
    ax2 = axes[1]
    ns = [s for s in NEG if s in out['table']['rule']]
    for i, a in enumerate(arms):
        ax2.bar([j + i * w for j in range(len(ns))], [out['table'][a][s]['tn_rate'] or 0 for s in ns], w, color=cols[a])
    ax2.set_xticks([j + 1.5 * w for j in range(len(ns))])
    ax2.set_xticklabels([f'{s}\n(n={out["table"]["rule"][s]["n"]})' for s in ns], fontsize=7)
    ax2.set_ylim(0, 1.05)
    ax2.set_title('"Not visible" correct rate (negatives)', fontsize=9)
    fig.tight_layout()
    fig.savefig(R.OUT / 'fig_f1_by_stratum.png', dpi=110)
    print('chart', (R.OUT / 'fig_f1_by_stratum.png').stat().st_size)


if __name__ == '__main__':
    main()

"""E8 scoring (#780; design docs/evaluation/E8_DESIGN_V1.md §2.9, §3.6, §5). SCORING SIDE: never imported by inference code.

Part 1 (open loop): each inference record carries the display its answer resolves to (``e8_requests.display_of``, computed without GT).
Here it is judged with ``e6_verdict.single_dp_correct`` against the label-only answer table (Colab, provisional regimes) or the GT
regime (Mac, final). Per (group, level) a decision point is correct by the majority over the three candidate orders.
Statistics reuse e6_verdict (sign-flip, family units, tolerance shifts) and agent_eval_scoring.metrics (general Holm, cluster bootstrap).
Identity stays UNCONFIRMED: "correct" only means the shown box lies on the labelled target.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from amidst.agent_eval_scoring.metrics import cluster_bootstrap_ci, holm_bonferroni
from amidst.evaluation import e6_verdict as V
from amidst.evaluation import e8_requests as R

SEED = 20261128
N_PERM = N_BOOT = 10000
ALPHA = 0.05
WRONG_PERSON_MARGIN_S = 14.0           # H2, total over the 28 segments (design §5.2, Q4)
MODELS = ('laya_text', 'laya_typed', 'qwen3b', 'qwen7b')
MODEL_LEVELS = {'laya_text': ('L0', 'L0c', 'L1', 'L2', 'L3'), 'laya_typed': ('L0', 'L0c', 'L1', 'L2', 'L3'),
                'qwen3b': ('L0', 'L0c', 'L1', 'L2', 'L3', 'L4'), 'qwen7b': ('L0', 'L0c', 'L1', 'L2', 'L3', 'L4', 'L3F')}
H1 = {'H1a': ('laya_typed', 'L2'), 'H1b': ('laya_typed', 'L3'), 'H1c': ('qwen7b', 'L2'), 'H1d': ('qwen7b', 'L3')}
H1_REF = ('FIRST_RED', 'L1')
S1 = {f'S1_{m}_{b}-{a}': (m, b, a) for m in ('laya_typed', 'qwen7b') for a, b in (('L0c', 'L1'), ('L1', 'L2'), ('L2', 'L3'))}
S1['S1_qwen7b_L4-L3'] = ('qwen7b', 'L4', 'L3')
S2 = {f'S2_{m}_{lv}': (m, lv) for m in ('laya_typed', 'qwen7b') for lv in ('L2', 'L3')}
S2_REF = ('NEAREST_RED', 'L2')


# ------------------------------------------------------------------------------------------------ regimes and single answers
def regime_from_label(entry: dict) -> str:
    """Colab (provisional): the label table cannot tell TRUE_DEPARTURE from FULL_BLIND."""
    return 'FULL_BLIND' if entry['expected_answer'] == 'NOT_VISIBLE' else 'VISIBLE'


def regime_from_gt(actor: dict | None) -> str:
    """Mac (final): target absent -> TRUE_DEPARTURE; present but seen by no camera -> FULL_BLIND; else VISIBLE."""
    if not actor or not actor.get('present'):
        return 'TRUE_DEPARTURE'
    return 'VISIBLE' if actor.get('gt_visible') else 'FULL_BLIND'


def answer_code(display: dict) -> str | None:
    """Resolved display -> the answer vocabulary of single_dp_correct."""
    kind = display['kind']
    if kind == 'BOX':
        return 'SELECT'
    if kind == 'NEEDS_MAC':
        return 'OWN_BOX'
    if kind == 'NONE':
        return 'NOT_VISIBLE' if display.get('via') == 'NOT_VISIBLE' else 'UNCERTAIN'
    return None


def hit_of(display: dict, entry: dict, own_box_hit: bool | None = None) -> bool | None:
    if display['kind'] == 'BOX':
        return display['detection_id'] in (entry.get('expected_detection_ids') or {}).get(display['camera_id'], [])
    if display['kind'] == 'NEEDS_MAC':
        return own_box_hit
    return False


def judge(display: dict, entry: dict, regime: str, own_box_hit: bool | None = None) -> bool | None:
    """True/False, or None when an OWN_BOX answer still needs the Mac GT box (NEEDS_MAC_SCORING)."""
    code = answer_code(display)
    hit = hit_of(display, entry, own_box_hit)
    if code == 'OWN_BOX' and regime == 'VISIBLE' and hit is None:
        return None
    return V.single_dp_correct(regime, code, hit_gt=bool(hit))


# ------------------------------------------------------------------------------------------------ records
def baseline_records(requests: Iterable[dict]) -> list[dict]:
    """Zero-inference groups from the requests themselves, each at its information level (design §2.8)."""
    out = []
    for req in requests:
        for policy, level in R.BASELINE_LEVEL.items():
            if req['level'] != level:
                continue
            ans = R.baseline_answer(policy, req)
            out.append(record(req, policy, ans, None))
    return out


def record(req: dict, group: str, ans: dict | None, err: str | None, **extra) -> dict:
    """One scored-ready record. ``first_option``: the chosen option is the first in this order (position bias, §5.4)."""
    disp = R.display_of(ans, req)
    first = None
    if ans is not None and ans.get('answer') == 'SELECT':
        if 'option' in ans and req.get('options'):
            first = ans['option'] == req['options'][0]['key']
        elif req.get('e7') and req['e7']['candidates']:
            c0 = req['e7']['candidates'][0]
            first = (ans.get('camera_id'), ans.get('detection_id')) == (c0['camera_id'], c0['detection_id'])
    return {'request_id': req['request_id'], 'base_id': req['base_id'], 'case_id': req['case_id'], 'group': group, 'level': req['level'],
            'perm': req['perm'], 'answer': ans and ans.get('answer'), 'error': err, 'display': disp, 'first_option': first, **extra}


def cells(records: Iterable[dict], table: dict, regime_of: dict, own_box: dict | None = None) -> dict:
    """{(group, level): {base_id: {'perms': {perm: bool|None}, 'majority': bool|None}}}. None = unresolved OWN_BOX."""
    out: dict = defaultdict(dict)
    for r in records:
        b = r['base_id']
        c = judge(r['display'], table[b], regime_of[b], (own_box or {}).get(r['request_id']))
        out[(r['group'], r['level'])].setdefault(b, {'perms': {}})['perms'][r['perm']] = c
    for cell in out.values():
        for v in cell.values():
            flags = list(v['perms'].values())
            v['majority'] = None if any(f is None for f in flags) else V.majority(flags)
            v['mean'] = None if any(f is None for f in flags) else sum(flags) / len(flags)
    return dict(out)


def accuracy(cell: dict) -> dict:
    resolved = [v for v in cell.values() if v['majority'] is not None]
    n = len(resolved)
    return {'n': len(cell), 'n_resolved': n, 'needs_mac': len(cell) - n,
            'majority_acc': sum(v['majority'] for v in resolved) / n if n else None,
            'mean_acc': sum(v['mean'] for v in resolved) / n if n else None}


# ------------------------------------------------------------------------------------------------ statistics
def paired(cell_a: dict, cell_b: dict, family_of: dict) -> dict:
    """Family-level paired accuracy differences (a - b), majority scores; decision points unresolved in either cell are dropped."""
    keys = sorted(k for k in cell_a if k in cell_b and cell_a[k]['majority'] is not None and cell_b[k]['majority'] is not None)
    fam = defaultdict(list)
    for k in keys:
        fam[family_of[k]].append(int(cell_a[k]['majority']) - int(cell_b[k]['majority']))
    families = sorted(fam)
    x = [sum(fam[f]) / len(fam[f]) for f in families]
    b = sum(1 for k in keys if cell_a[k]['majority'] and not cell_b[k]['majority'])
    c = sum(1 for k in keys if cell_b[k]['majority'] and not cell_a[k]['majority'])
    return {'n_dp': len(keys), 'families': families, 'x': x, 'items': [(family_of[k], int(cell_a[k]['majority']) - int(cell_b[k]['majority']))
                                                                        for k in keys], 'discordant': [b, c]}


def compare(cell_a: dict, cell_b: dict, family_of: dict, *, two_sided: bool = False) -> dict:
    pr = paired(cell_a, cell_b, family_of)
    if not pr['x']:
        return {'n_dp': 0, 'M': 0, 'p': 1.0, 'p_reverse': 1.0, 'diff': None, 'ci95': None, 'mcnemar_p': 1.0}
    if two_sided:
        p = V.sign_flip_p_two_sided(pr['x'], seed=SEED, n_perm=N_PERM)
        p_rev = p
    else:
        p = V.sign_flip_p(pr['x'], seed=SEED, n_perm=N_PERM)
        p_rev = V.sign_flip_p([-v for v in pr['x']], seed=SEED, n_perm=N_PERM)
    boot = cluster_bootstrap_ci(pr['items'], n_boot=N_BOOT, seed=SEED)
    return {'n_dp': pr['n_dp'], 'M': len(pr['families']), 'diff': sum(v for _, v in pr['items']) / pr['n_dp'], 'family_x': pr['x'],
            'p': p, 'p_reverse': p_rev, 'ci95': boot['ci95'], 'mcnemar_p': V.mcnemar_exact_p(*pr['discordant']), 'discordant': pr['discordant']}


def status_of(res: dict, rejected: bool, m: int) -> str:
    if res['n_dp'] < V.MIN_DP or res['M'] < V.MIN_FAMILIES:
        return 'EXPLORATORY'
    if rejected:
        return 'SUPPORTED'
    if res['p_reverse'] <= ALPHA / m:            # reverse direction, Bonferroni (design §5.1)
        return 'NOT_SUPPORTED'
    return 'INCONCLUSIVE'


def h2_test(segments: list[dict], dps: list[dict], test: str = 'SELECTED', ref: str = 'B1') -> dict:
    """Intersection-union non-inferiority (design §5.2 H2): follow >= -0.05, wrong-person total <= +14.0 s, blind false-lock <= +5.0 s.
    ``segments``/``dps`` in the e6_verdict row format (group, family_id, case_id, follow_rate, visible_ticks, wrong_person_s,
    blind_false_lock_s / full_track_correct)."""
    units = V._group_family_units(segments, dps)
    families = sorted(set(units[test]) & set(units[ref]))
    m = len(families)
    d = V._diffs(units, test, ref, families)
    s = V._shifted(d, m, V.TAU_BLIND_S)
    x = {'follow': s['C2'], 'wrong_person': [WRONG_PERSON_MARGIN_S / m - v for v in d['wp']], 'blind_false_lock': s['C4']}
    comps = {k: {'x': v, 'p': V.sign_flip_p(v, seed=SEED, n_perm=N_PERM)} for k, v in x.items()}
    n_dp = sum(units[test][f]['dp_n'] for f in families)
    return {'M': m, 'n_dp': n_dp, 'components': comps, 'p': max(c['p'] for c in comps.values()),
            'observed': {'follow_diff_mean': sum(d['follow']) / m, 'wrong_person_diff_sum_s': sum(d['wp']),
                         'blind_false_lock_diff_sum_s': sum(d['bfl'])}, 'p_reverse': 1.0}


def primary_verdict(cellmap: dict, family_of: dict, h2: dict | None = None) -> dict:
    """H1a-d (+ H2 when given), Holm m = 5 one-sided."""
    ref = cellmap.get(H1_REF, {})
    res = {h: compare(cellmap.get(g, {}), ref, family_of) for h, g in H1.items()}
    ps = {h: r['p'] for h, r in res.items()}
    if h2 is not None:
        res['H2'] = h2
        ps['H2'] = h2['p']
    holm = holm_bonferroni(ps, alpha=ALPHA)
    m = 5
    return {h: {**r, 'p_holm': holm[h]['p_holm'], 'status': status_of(r, holm[h]['reject'], m)} for h, r in res.items()} | \
        {'_holm_m': m, '_note': 'H2 missing: Holm over H1 only' if h2 is None else 'Holm over H1a-d and H2'}


def secondary_verdict(cellmap: dict, family_of: dict, s3: dict | None = None, s4: dict | None = None) -> dict:
    """S1 (7) + S2 (4) two-sided, + S3/S4 when given; Holm m = 13."""
    res = {k: compare(cellmap.get((mdl, b), {}), cellmap.get((mdl, a), {}), family_of, two_sided=True) for k, (mdl, b, a) in S1.items()}
    res |= {k: compare(cellmap.get(g, {}), cellmap.get(S2_REF, {}), family_of, two_sided=True) for k, g in S2.items()}
    for k, v in (('S3', s3), ('S4', s4)):
        if v is not None:
            res[k] = v
    holm = holm_bonferroni({k: r['p'] for k, r in res.items()}, alpha=ALPHA)
    return {k: {**r, 'p_holm': holm[k]['p_holm'], 'status': status_of(r, holm[k]['reject'], 13)} for k, r in res.items()}


# ------------------------------------------------------------------------------------------------ group selection (design §3.5)
def select_groups(cellmap: dict) -> dict:
    """Best text level k* per model (L0c-L3), then SELECTED. Ties: mean accuracy, lower level, model order."""
    best = {}
    for mdl in MODELS:
        cands = []
        for lv in R.TEXT_LEVELS:
            if (mdl, lv) in cellmap:
                a = accuracy(cellmap[(mdl, lv)])
                if a['majority_acc'] is not None:
                    cands.append((-a['majority_acc'], -a['mean_acc'], R.TEXT_LEVELS.index(lv), lv, a))
        if cands:
            best[mdl] = min(cands)
    if not best:
        return {'per_model': {}, 'selected': None}
    sel = min(best, key=lambda mdl: best[mdl][:3] + (MODELS.index(mdl),))
    return {'per_model': {m: {'level': v[3], **v[4]} for m, v in best.items()}, 'selected': {'model': sel, 'level': best[sel][3]}}


# ------------------------------------------------------------------------------------------------ exploratory (design §5.4)
def position_bias(records: Iterable[dict]) -> dict:
    """First-option rate per (group, level, perm) among SELECT answers; agreement of the displayed box across the three orders."""
    first, disp = defaultdict(lambda: [0, 0]), defaultdict(dict)
    for r in records:
        if r['first_option'] is not None:
            f = first[(r['group'], r['level'], r['perm'])]
            f[0] += bool(r['first_option'])
            f[1] += 1
        d = r['display']
        disp[(r['group'], r['level'])].setdefault(r['base_id'], {})[r['perm']] = (d['kind'], d.get('camera_id'), d.get('detection_id'))
    agree = {}
    for k, by in disp.items():
        full = [v for v in by.values() if len(v) == len(R.PERMS)]
        agree[k] = sum(len(set(v.values())) == 1 for v in full) / len(full) if full else None
    return {'first_option_rate': {f'{g}|{lv}|{p}': (a / n if n else None) for (g, lv, p), (a, n) in sorted(first.items())},
            'order_agreement': {f'{g}|{lv}': v for (g, lv), v in sorted(agree.items())}}


def random_expectation(requests: Iterable[dict], table: dict, regime_of: dict) -> float:
    """Theoretical RANDOM accuracy: uniform over the options and NOT_VISIBLE, averaged over the p0 requests at L0c."""
    vals = []
    for req in requests:
        if req['level'] != 'L0c' or req['perm'] != 'p0':
            continue
        b, n = req['base_id'], len(req['options']) + 1
        ok = sum(bool(judge({'kind': 'BOX', 'camera_id': o['camera_id'], 'detection_id': o['detection_id']}, table[b], regime_of[b]))
                 for o in req['options'])
        ok += bool(judge({'kind': 'NONE', 'via': 'NOT_VISIBLE'}, table[b], regime_of[b]))
        vals.append(ok / n)
    return sum(vals) / len(vals) if vals else float('nan')


def summary(records: list[dict], requests: list[dict], table: dict, regime_of: dict, family_of: dict, *, own_box: dict | None = None,
            h2: dict | None = None) -> dict[str, Any]:
    """Everything the Colab cell 7 / the Mac command reports for Part 1."""
    allrec = records + baseline_records(requests)
    cm = cells(allrec, table, regime_of, own_box)
    return {'schema': 'e8_part1_summary_v1', 'seed': SEED, 'accuracy': {f'{g}|{lv}': accuracy(c) for (g, lv), c in sorted(cm.items())},
            'primary': primary_verdict(cm, family_of, h2), 'secondary': secondary_verdict(cm, family_of),
            'selection': select_groups(cm), 'position_bias': position_bias(allrec),
            'random_expectation': random_expectation(requests, table, regime_of), 'identity': 'UNCONFIRMED',
            'regimes': dict(sorted(_count(regime_of.values()).items()))}


def _count(vals) -> dict:
    out: dict = defaultdict(int)
    for v in vals:
        out[v] += 1
    return dict(out)


__all__ = ['regime_from_label', 'regime_from_gt', 'judge', 'record', 'baseline_records', 'cells', 'accuracy', 'compare', 'h2_test',
           'primary_verdict', 'secondary_verdict', 'select_groups', 'position_bias', 'random_expectation', 'summary']

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
            out.append(R.make_record(req, policy, ans, None))
    return out


def own_box_key(r: dict) -> tuple[str, str, str, str]:
    """Unique key of one answer: every model / group answers the same request ids, so the request id alone collides (#785)."""
    return (r['group'], r['level'], r['perm'], r['request_id'])


def cells(records: Iterable[dict], table: dict, regime_of: dict, own_box: dict | None = None) -> dict:
    """{(group, level): {base_id: {'perms': {perm: bool|None}, 'majority': bool|None}}}. None = unresolved OWN_BOX."""
    out: dict = defaultdict(dict)
    for r in records:
        b = r['base_id']
        c = judge(r['display'], table[b], regime_of[b], (own_box or {}).get(own_box_key(r)))
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
            h2: dict | None = None, s3: dict | None = None, s4: dict | None = None) -> dict[str, Any]:
    """Everything the Colab cell 7 / the Mac command reports for Part 1."""
    allrec = records + baseline_records(requests)
    cm = cells(allrec, table, regime_of, own_box)
    return {'schema': 'e8_part1_summary_v1', 'seed': SEED, 'accuracy': {f'{g}|{lv}': accuracy(c) for (g, lv), c in sorted(cm.items())},
            'primary': primary_verdict(cm, family_of, h2), 'secondary': secondary_verdict(cm, family_of, s3, s4),
            'union_answerable': union_answerable(cm, table),
            'selection': select_groups(cm), 'position_bias': position_bias(allrec),
            'random_expectation': random_expectation(requests, table, regime_of), 'identity': 'UNCONFIRMED',
            'regimes': dict(sorted(_count(regime_of.values()).items()))}


def _count(vals) -> dict:
    out: dict = defaultdict(int)
    for v in vals:
        out[v] += 1
    return dict(out)


# ------------------------------------------------------------------------------------------------ Part 2 extras (design §3.6, §5.3)
EARLY_WINDOW_TICKS = 15
EARLY_MISS_TICKS = 16          # no CORRECT tick within 3 s -> 3.2 s


def first_correct(classes: dict, tick: int) -> int:
    return next((k - tick for k in range(tick, tick + EARLY_WINDOW_TICKS) if classes.get(k) == 'CORRECT'), EARLY_MISS_TICKS)


def early_switch_s(classes_test: dict, classes_ref: dict, tick: int) -> float:
    """Seconds the tested group reaches CORRECT earlier than the reference (positive = earlier)."""
    return round((first_correct(classes_ref, tick) - first_correct(classes_test, tick)) * R.TICK_S, 3)


def family_two_sided(items: list[tuple[str, float]]) -> dict:
    fam = defaultdict(list)
    for f, v in items:
        fam[f].append(v)
    x = [sum(v) / len(v) for _, v in sorted(fam.items())]
    if not x:
        return {'M': 0, 'n_dp': 0, 'p': 1.0, 'p_reverse': 1.0, 'diff': None}
    p = V.sign_flip_p_two_sided(x, seed=SEED, n_perm=N_PERM)
    vals = sorted(v for _, v in items)
    return {'M': len(x), 'n_dp': len(items), 'p': p, 'p_reverse': p, 'diff': sum(vals) / len(vals), 'median': vals[len(vals) // 2],
            'family_x': x}


def s3_test(segments: list[dict], test: str = 'SELECTED', ref: str = 'B1') -> dict:
    """S3: wrong-person seconds lower than B1 (two-sided family sign-flip on B1 - test; positive favours the test group)."""
    by = {(r['group'], r['case_id']): r for r in segments}
    items = [(r['family_id'], V._mean(by[(ref, r['case_id'])]['wrong_person_s']) - V._mean(r['wrong_person_s']))
             for r in segments if r['group'] == test and (ref, r['case_id']) in by]
    res = family_two_sided(items)
    res['n_dp'] = max(res['n_dp'], V.MIN_DP)   # segment-level test: the decision-point threshold does not apply
    return res


def s4_test(items: list[tuple[str, float]]) -> dict:
    """S4: early-switch seconds (median > 0); items = (family, seconds) over visible decision points."""
    return family_two_sided(items)


def conclusion(primary: dict, secondary: dict, *, union_answerable: float | None = None, first_option: dict | None = None) -> str:
    """Design §5.5, in table order."""
    h1 = any(primary.get(h, {}).get('status') == 'SUPPORTED' for h in H1)
    h2 = primary.get('H2', {}).get('status') == 'SUPPORTED'
    s2_agent = any(v.get('status') == 'SUPPORTED' and (v.get('diff') or 0) > 0 for k, v in secondary.items() if k.startswith('S2_'))
    s2_rule = any(v.get('status') == 'SUPPORTED' and (v.get('diff') or 0) < 0 for k, v in secondary.items() if k.startswith('S2_'))
    if h2 and h1 and s2_agent:
        return 'AGENT_BETTER_THAN_RULE'
    if h2 and h1:
        return 'BEATS_COLOUR_HEURISTIC_CLOSED_LOOP_NOT_WORSE'
    if h2:
        return 'CLOSED_LOOP_NOT_WORSE_SINGLE_POINT_NOT_BETTER'
    s2_flat = all(v.get('p_holm', 1) >= ALPHA and abs(v.get('diff') or 0) < 0.05 for k, v in secondary.items() if k.startswith('S2_'))
    if s2_flat and union_answerable is not None and union_answerable < 0.80:
        return 'INSUFFICIENT_INFORMATION'
    if s2_rule and first_option and any(v is not None and v > 0.5 for v in first_option.values()):
        return 'MODEL_TOO_SMALL'
    return 'INCONCLUSIVE'


def union_answerable(cellmap: dict, table: dict) -> float | None:
    """Share of answerable decision points (detector misses, label UNCERTAIN, excluded) that any group/level answered correctly."""
    keys = {k for c in cellmap.values() for k in c if table.get(k, {}).get('expected_answer') != 'UNCERTAIN'}
    if not keys:
        return None
    ok = [k for k in keys if any(c.get(k, {}).get('majority') for c in cellmap.values())]
    return len(ok) / len(keys)


def unified_section(results: dict) -> dict:
    """Compact ``e8`` section for unified_analysis_v1 (figures read only this)."""
    p1 = results['part1']
    return {'schema': 'e8_unified_v1', 'conclusion': results.get('conclusion'),
            'accuracy': {k: v['majority_acc'] for k, v in p1['accuracy'].items()},
            'accuracy_mean': {k: v['mean_acc'] for k, v in p1['accuracy'].items()},
            'first_option_rate': p1['position_bias']['first_option_rate'],
            'order_agreement': p1['position_bias']['order_agreement'],
            'verdicts': {k: v.get('status') for k, v in {**p1['primary'], **p1['secondary']}.items() if isinstance(v, dict)},
            'selection': p1['selection'], 'part2': results.get('part2', {}).get('per_group', {}),
            'early_switch_s': results.get('part2', {}).get('early_switch_s', {}), 'identity_status': 'UNCONFIRMED'}


__all__ = ['own_box_key', 'regime_from_label', 'regime_from_gt', 'judge', 'baseline_records', 'cells', 'accuracy', 'compare', 'h2_test',
           'primary_verdict', 'secondary_verdict', 'select_groups', 'position_bias', 'random_expectation', 'summary',
           'early_switch_s', 's3_test', 's4_test', 'conclusion', 'union_answerable', 'unified_section']

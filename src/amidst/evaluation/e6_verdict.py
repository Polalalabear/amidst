"""E6 verdict (preregistration docs/evaluation/E6_PREREGISTRATION_DRAFT.md sections 3.1-3.2 and 4; #721 G6). Scoring side.

Standard library only. ``e3_scoring.py`` (the frozen E3/E5 scorer, SHA-256 acacce39...) is neither imported nor changed; this module takes
its per-segment numbers as input and judges them with the E6 rules:

* independent unit = scenario family (same-family segments are summed / denominator-weighted into one unit), M families;
* N_dp >= 40 and M >= 8, otherwise EXPLORATORY (never lowered);
* two hypotheses: P1 = DEANCHOR vs AO_ORIG, P2 = SELECTED_AGENT vs B1; each is an intersection-union test of four one-sided components
  (C1 wrong-person s lower, C2 follow-rate non-inferior by 0.05, C3 fixed-decision-point accuracy higher, C4 blind false-lock sum <= +5.0 s);
* component p = family-level paired sign-flip test (all 2^M flips for M <= 12, else random.Random(20261124) with 10000 flips),
  p_h = max over components; companions: skew, paired t, exact sign test, SKEW_SENSITIVITY_FLAG;
* family cluster bootstrap B = 10000, seed 20261124, 97.5 % (Holm step 1) and 95.0 % (step 2) percentile intervals;
* Holm (0.0125 then 0.025) in the supported direction, and in the reverse direction with a Bonferroni factor 4; else INCONCLUSIVE.

Identity stays UNCONFIRMED: "correct" only means the shown box or estimate lies on the GT target (GT is scoring-side input, never inference).
Input rows (``segments``/``decision_points``) are produced by the scorer; values may be a number/bool or a list of K replicate values
(seconds and rates are averaged, decision points are K-majority voted: strictly more than half correct).
"""
from __future__ import annotations

import itertools
import math
import random
from collections import defaultdict

SCHEMA = 'e6.verdict.v1'
SEED = 20261124
N_BOOT = 10000
N_PERM = 10000
ALPHA_STEP1, ALPHA_STEP2 = 0.0125, 0.025
CI_STEP1, CI_STEP2 = 97.5, 95.0
FOLLOW_MARGIN = 0.05
TAU_BLIND_S = 5.0
MIN_DP, MIN_FAMILIES = 40, 8
SKEW_LIMIT = 1.0
GROUP_REFERENCE_P1, GROUP_TEST_P1 = 'AO_ORIG', 'DEANCHOR'
GROUP_REFERENCE_P2 = 'B1'
REGIMES = ('VISIBLE', 'FULL_BLIND', 'TRUE_DEPARTURE')
COMPONENTS = ('C1', 'C2', 'C3', 'C4')
P2_NOT_SUPPORTED_TEXT = '改良後仍未證實優於現有規則'


# ---- decision-point truth tables (prereg 3.2) -------------------------------------------------------------------------------
def full_track_dp_correct(gt_regime, window):
    """Full-tracking 3.0 s window. ``window`` = per-tick dicts {'cls': e3 tick class, 'displayed': bool}. Errors/timeouts are the caller's
    ticks (nothing shown), never excluded."""
    if gt_regime not in REGIMES:
        raise ValueError('BAD_GT_REGIME')
    if not window:
        raise ValueError('EMPTY_WINDOW')
    cls = [t['cls'] for t in window]
    if gt_regime == 'VISIBLE':
        return 'CORRECT' in cls and not any(c in ('WRONG_PERSON', 'WRONG_CAMERA') for c in cls)
    if gt_regime == 'FULL_BLIND':
        return 'FALSE_LOCK' not in cls
    return not any(bool(t['displayed']) for t in window)


def single_dp_correct(gt_regime, answer, *, hit_gt=False):
    """Single paired answer at the decision point. API errors, timeouts and format rejections are ``answer=None`` = wrong."""
    if gt_regime not in REGIMES:
        raise ValueError('BAD_GT_REGIME')
    if gt_regime == 'VISIBLE':
        return answer in ('SELECT', 'OWN_BOX') and bool(hit_gt)
    if gt_regime == 'FULL_BLIND':
        return answer in ('NOT_VISIBLE', 'UNCERTAIN')
    return answer == 'NOT_VISIBLE'


def majority(flags):
    """K-majority vote: strictly more than half True. A scalar passes through; an empty list is wrong."""
    if isinstance(flags, (list, tuple)):
        return len(flags) > 0 and sum(bool(f) for f in flags) * 2 > len(flags)
    return bool(flags)


def _mean(v):
    if isinstance(v, (list, tuple)):
        if not v:
            raise ValueError('EMPTY_REPLICATES')
        return sum(float(x) for x in v) / len(v)
    return float(v)


# ---- statistics (standard library) --------------------------------------------------------------------------------------------
def sign_flip_p_two_sided(x, *, seed=SEED, n_perm=N_PERM):
    """Two-sided sign-flip p (|T(s)| >= |T_obs|); exact for M <= 12, else seeded Monte Carlo. Uncorrected; exploratory use only."""
    m = len(x)
    if m == 0:
        raise ValueError('NO_FAMILIES')
    t_obs = abs(sum(x))
    tol = 1e-9 * max(1.0, sum(abs(v) for v in x))
    if m <= 12:
        return sum(abs(sum(s * v for s, v in zip(signs, x))) >= t_obs - tol
                   for signs in itertools.product((1.0, -1.0), repeat=m)) / 2 ** m
    rng = random.Random(seed)
    hits = sum(abs(sum((v if rng.random() < 0.5 else -v) for v in x)) >= t_obs - tol for _ in range(n_perm))
    return (1 + hits) / (n_perm + 1)


def sign_flip_p(x, *, seed=SEED, n_perm=N_PERM):
    """One-sided p for H1: location > 0 under the symmetric null. Exact (all 2^M flips) for M <= 12, else Monte Carlo."""
    m = len(x)
    if m == 0:
        raise ValueError('NO_FAMILIES')
    t_obs = sum(x)
    tol = 1e-9 * max(1.0, sum(abs(v) for v in x))
    if m <= 12:
        count = 0
        for signs in itertools.product((1.0, -1.0), repeat=m):
            if sum(s * v for s, v in zip(signs, x)) >= t_obs - tol:
                count += 1
        return count / 2 ** m
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        if sum((v if rng.random() < 0.5 else -v) for v in x) >= t_obs - tol:
            hits += 1
    return (1 + hits) / (n_perm + 1)


def skewness(x):
    m = len(x)
    mean = sum(x) / m
    m2 = sum((v - mean) ** 2 for v in x) / m
    if m2 < 1e-18:
        return 0.0
    return (sum((v - mean) ** 3 for v in x) / m) / m2 ** 1.5


def _betacf(a, b, x):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return h


def _betainc(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    front = math.exp(ln_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t, df):
    """P(T >= t) for Student's t with ``df`` degrees of freedom."""
    p_half = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return p_half if t > 0 else 1.0 - p_half


def paired_t_p(x):
    """One-sided paired t (mean > 0), df = M - 1."""
    m = len(x)
    if m < 2:
        return 1.0
    mean = sum(x) / m
    var = sum((v - mean) ** 2 for v in x) / (m - 1)
    if var <= 1e-18:
        return 0.0 if mean > 1e-12 else (0.5 if abs(mean) <= 1e-12 else 1.0)
    return t_sf(mean / math.sqrt(var / m), m - 1)


def sign_test_p(x):
    """Exact one-sided sign test (median > 0); zeros dropped."""
    nz = [v for v in x if abs(v) > 1e-12]
    n = len(nz)
    if n == 0:
        return 1.0
    pos = sum(v > 0 for v in nz)
    return sum(math.comb(n, k) for k in range(pos, n + 1)) / 2 ** n


def mcnemar_exact_p(b, c):
    """Two-sided exact McNemar on discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n)


def _percentile(sorted_vals, q):
    pos = q / 100.0 * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _ci(values, level):
    s = sorted(values)
    tail = (100.0 - level) / 2.0
    return [_percentile(s, tail), _percentile(s, 100.0 - tail)]


# ---- family units -------------------------------------------------------------------------------------------------------------
def _group_family_units(segments, decision_points):
    seg = defaultdict(lambda: defaultdict(lambda: {'wp': 0.0, 'bfl': 0.0, 'lost': 0.0, 'fnum': 0.0, 'fden': 0.0, 'segments': []}))
    for r in segments:
        u = seg[r['group']][r['family_id']]
        w = _mean(r['visible_ticks'])
        u['wp'] += _mean(r['wrong_person_s'])
        u['bfl'] += _mean(r['blind_false_lock_s'])
        u['lost'] += _mean(r.get('lost_s', 0.0))
        u['fnum'] += _mean(r['follow_rate']) * w
        u['fden'] += w
        u['segments'].append(r['case_id'])
    dps = defaultdict(lambda: defaultdict(lambda: {'n': 0, 'full': 0, 'single_n': 0, 'single': 0}))
    for r in decision_points:
        u = dps[r['group']][r['family_id']]
        u['n'] += 1
        u['full'] += majority(r['full_track_correct'])
        if r.get('single_correct') is not None:
            u['single_n'] += 1
            u['single'] += majority(r['single_correct'])
    out = {}
    for g in set(seg) | set(dps):
        out[g] = {}
        for fam in set(seg[g]) | set(dps[g]):
            s, d = seg[g][fam], dps[g][fam]
            if s['fden'] <= 0 or d['n'] == 0:
                raise ValueError(f'MISSING_DATA:{g}:{fam}')
            out[g][fam] = {'wrong_person_s': s['wp'], 'blind_false_lock_s': s['bfl'], 'lost_s': s['lost'],
                           'follow_rate': s['fnum'] / s['fden'], 'visible_ticks': s['fden'],
                           'full_track_dp_acc': d['full'] / d['n'], 'dp_n': d['n'], 'dp_full_correct': d['full'],
                           'single_dp_acc': (d['single'] / d['single_n']) if d['single_n'] else None}
    return out


def _diffs(units, test, ref, families):
    d = {'wp': [], 'follow': [], 'dp': [], 'bfl': []}
    for fam in families:
        a, b = units[test][fam], units[ref][fam]
        d['wp'].append(a['wrong_person_s'] - b['wrong_person_s'])
        d['follow'].append(a['follow_rate'] - b['follow_rate'])
        d['dp'].append(a['full_track_dp_acc'] - b['full_track_dp_acc'])
        d['bfl'].append(a['blind_false_lock_s'] - b['blind_false_lock_s'])
    return d


def _shifted(d, m, tau):
    """x_j per component, positive = favours the tested group."""
    return {'C1': [-v for v in d['wp']], 'C2': [v + FOLLOW_MARGIN for v in d['follow']], 'C3': list(d['dp']),
            'C4': [tau / m - v for v in d['bfl']]}


def _shifted_negative(d, m, tau):
    """x_j for the reverse (degradation) tests: positive = worse than the tolerance."""
    return {'C1': list(d['wp']), 'C2': [-FOLLOW_MARGIN - v for v in d['follow']], 'C3': [-v for v in d['dp']],
            'C4': [v - tau / m for v in d['bfl']]}


def _boundary_ok(ci, comp):
    lo, hi = ci
    return {'C1': hi < 0, 'C2': lo > -FOLLOW_MARGIN, 'C3': lo > 0, 'C4': hi <= TAU_BLIND_S}[comp]


def _comp_stats(d):
    return {'C1': sum(d['wp']), 'C2': sum(d['follow']) / len(d['follow']), 'C3': sum(d['dp']) / len(d['dp']), 'C4': sum(d['bfl'])}


def _hypothesis(units, test, ref, families, boot_rng_indices, tau):
    m = len(families)
    d = _diffs(units, test, ref, families)
    pos, neg = _shifted(d, m, tau), _shifted_negative(d, m, tau)
    comps, neg_p = {}, {}
    for c in COMPONENTS:
        comps[c] = {'p_flip': sign_flip_p(pos[c]), 'p_t': paired_t_p(pos[c]), 'p_sign': sign_test_p(pos[c]),
                    'skew': skewness(pos[c]), 'x': [round(v, 9) for v in pos[c]], 'observed': _comp_stats(d)[c]}
        neg_p[c] = sign_flip_p(neg[c])
    boots = {c: [] for c in COMPONENTS}
    for idx in boot_rng_indices:
        sub = {k: [v[i] for i in idx] for k, v in d.items()}
        s = _comp_stats(sub)
        for c in COMPONENTS:
            boots[c].append(s[c])
    for c in COMPONENTS:
        comps[c]['ci_97_5'] = _ci(boots[c], CI_STEP1)
        comps[c]['ci_95_0'] = _ci(boots[c], CI_STEP2)
        comps[c]['boundary_ok_97_5'] = _boundary_ok(comps[c]['ci_97_5'], c)
        comps[c]['boundary_ok_95_0'] = _boundary_ok(comps[c]['ci_95_0'], c)
        comps[c]['p_flip_negative'] = neg_p[c]
    p_h = max(comps[c]['p_flip'] for c in COMPONENTS)
    p_neg = min(1.0, 4 * min(neg_p.values()))
    return {'test_group': test, 'reference_group': ref, 'components': comps, 'p_h': p_h, 'p_negative': p_neg,
            'diffs': {k: [round(v, 9) for v in vals] for k, vals in d.items()},
            'S5_blind_ci_upper_lt_0': {'97.5': comps['C4']['ci_97_5'][1] < 0, '95.0': comps['C4']['ci_95_0'][1] < 0}}


def _holm(p_by_h, ok_by_h_level):
    """Returns {h: bool}. p_by_h: {h: p}; ok_by_h_level: {h: (ok_at_step1, ok_at_step2)} (CI-boundary conditions; (True, True) for none)."""
    order = sorted(p_by_h, key=lambda h: (p_by_h[h], h))
    passed = {h: False for h in order}
    first, second = order[0], order[1]
    if p_by_h[first] <= ALPHA_STEP1 and ok_by_h_level[first][0]:
        passed[first] = True
        if p_by_h[second] <= ALPHA_STEP2 and ok_by_h_level[second][1]:
            passed[second] = True
    return passed, {first: 1, second: 2}


def ablation_comparison(units, selected, families):
    """D403 exploratory paired comparison of each ablation group (``<selected>+<ABLATION>``) with the selected agent.
    Differences are ablation - selected per family; p is the uncorrected two-sided sign-flip p. EXPLORATORY, never part of Holm."""
    out = {}
    for g in sorted(g for g in units if g.startswith(selected + '+')):
        if set(units[g]) != set(units[selected]):
            raise ValueError('FAMILY_MISMATCH_ABLATION:' + g)
        d = _diffs(units, g, selected, families)
        obs = _comp_stats(d)
        names = {'C1': 'wrong_person_s', 'C2': 'follow_rate', 'C3': 'full_track_dp_acc', 'C4': 'blind_false_lock_s'}
        raw = {'C1': d['wp'], 'C2': d['follow'], 'C3': d['dp'], 'C4': d['bfl']}
        out[g] = {'EXPLORATORY': True, 'in_holm': False, 'reference': selected, 'M': len(families),
                  'paired_difference_ablation_minus_selected': {
                      names[c]: {'observed': obs[c], 'aggregate': 'sum over families' if c in ('C1', 'C4') else 'mean over families',
                                 'p_two_sided_uncorrected': sign_flip_p_two_sided(raw[c]), 'family_differences': [round(v, 9) for v in raw[c]]}
                      for c in COMPONENTS}}
    return out


def _group_report(units, families):
    rep = {}
    for g, fams in units.items():
        sel = [fams[f] for f in families if f in fams]
        if not sel:
            continue
        den = sum(u['visible_ticks'] for u in sel)
        n = sum(u['dp_n'] for u in sel)
        rep[g] = {'wrong_person_s': sum(u['wrong_person_s'] for u in sel), 'blind_false_lock_s': sum(u['blind_false_lock_s'] for u in sel),
                  'lost_s': sum(u['lost_s'] for u in sel),
                  'follow_rate': sum(u['follow_rate'] * u['visible_ticks'] for u in sel) / den,
                  'full_track_dp_acc': sum(u['dp_full_correct'] for u in sel) / n, 'dp_n': n}
    return rep


def verdict_e6(segments, decision_points, *, selected_agent='DEANCHOR', n_boot=N_BOOT, seed=SEED, tau_blind_s=TAU_BLIND_S):
    """Judge P1 (DEANCHOR vs AO_ORIG) and P2 (selected_agent vs B1). Returns a plain dict; see module docstring."""
    groups_needed = {GROUP_TEST_P1, GROUP_REFERENCE_P1, selected_agent, GROUP_REFERENCE_P2}
    units = _group_family_units(segments, decision_points)
    missing = groups_needed - set(units)
    if missing:
        raise ValueError('MISSING_GROUPS:' + ','.join(sorted(missing)))
    fam_sets = [set(units[g]) for g in groups_needed]
    if any(s != fam_sets[0] for s in fam_sets):
        raise ValueError('FAMILY_MISMATCH')
    families = sorted(fam_sets[0])
    m = len(families)
    dp_ids = {g: {r['dp_id'] for r in decision_points if r['group'] == g} for g in groups_needed}
    if any(s != dp_ids[GROUP_REFERENCE_P2] for s in dp_ids.values()):
        raise ValueError('DECISION_POINT_MISMATCH')
    n_dp = len(dp_ids[GROUP_REFERENCE_P2])
    for g in sorted(g for g in units if g.startswith(selected_agent + '+')):          # D403: an ablation must cover the same families and points
        if set(units[g]) != set(units[selected_agent]):
            raise ValueError('FAMILY_MISMATCH_ABLATION:' + g)
        if {r['dp_id'] for r in decision_points if r['group'] == g} != dp_ids[selected_agent]:
            raise ValueError('DECISION_POINT_MISMATCH_ABLATION:' + g)
    exploratory = n_dp < MIN_DP or m < MIN_FAMILIES

    rng = random.Random(seed)
    idx_draws = [[rng.randrange(m) for _ in range(m)] for _ in range(n_boot)]
    hyp = {'P1': _hypothesis(units, GROUP_TEST_P1, GROUP_REFERENCE_P1, families, idx_draws, tau_blind_s),
           'P2': _hypothesis(units, selected_agent, GROUP_REFERENCE_P2, families, idx_draws, tau_blind_s)}

    ok = {h: (all(v['components'][c]['boundary_ok_97_5'] for c in COMPONENTS),
              all(v['components'][c]['boundary_ok_95_0'] for c in COMPONENTS)) for h, v in hyp.items()}
    supported, ranks = _holm({h: v['p_h'] for h, v in hyp.items()}, ok)
    not_supported, neg_ranks = _holm({h: v['p_negative'] for h, v in hyp.items()}, {h: (True, True) for h in hyp})

    flagged = {}
    for h, v in hyp.items():
        alpha = ALPHA_STEP1 if ranks[h] == 1 else ALPHA_STEP2
        flagged[h] = [c for c in COMPONENTS
                      if abs(v['components'][c]['skew']) > SKEW_LIMIT
                      and (v['components'][c]['p_t'] <= alpha) != (v['components'][c]['p_flip'] <= alpha)]
        v['holm_rank'] = ranks[h]
        v['holm_alpha'] = alpha
        v['holm_negative_rank'] = neg_ranks[h]
        v['skew_flag_components'] = flagged[h]
        v['verdict_if_formal'] = 'SUPPORTED' if supported[h] else 'NOT_SUPPORTED' if not_supported[h] else 'INCONCLUSIVE'
        v['verdict'] = 'EXPLORATORY' if exploratory else v['verdict_if_formal']
        v['holm_positive_passed'] = supported[h]
        v['holm_negative_passed'] = not_supported[h]
    p2_text = None if hyp['P2']['verdict_if_formal'] == 'SUPPORTED' else P2_NOT_SUPPORTED_TEXT

    # strata (reporting only) and the single-point paired answer (reporting only; never part of C3)
    strata, single = {}, {}
    for g in sorted(groups_needed):
        rows = [r for r in decision_points if r['group'] == g]
        for name, regimes in (('VISIBLE', ('VISIBLE',)), ('FULL_BLIND+TRUE_DEPARTURE', ('FULL_BLIND', 'TRUE_DEPARTURE'))):
            sel = [r for r in rows if r['gt_regime'] in regimes]
            strata.setdefault(g, {})[name] = {'n': len(sel), 'full_track_dp_acc': (sum(majority(r['full_track_correct']) for r in sel) / len(sel))
                                              if sel else None}
        sr = [r for r in rows if r.get('single_correct') is not None]
        single[g] = {'n': len(sr), 'single_dp_acc': (sum(majority(r['single_correct']) for r in sr) / len(sr)) if sr else None}
    mc = {}
    for h, (t, r_) in (('P1', (GROUP_TEST_P1, GROUP_REFERENCE_P1)), ('P2', (selected_agent, GROUP_REFERENCE_P2))):
        a = {x['dp_id']: majority(x['single_correct']) for x in decision_points if x['group'] == t and x.get('single_correct') is not None}
        b = {x['dp_id']: majority(x['single_correct']) for x in decision_points if x['group'] == r_ and x.get('single_correct') is not None}
        shared = sorted(set(a) & set(b))
        only_a = sum(a[k] and not b[k] for k in shared)
        only_b = sum(b[k] and not a[k] for k in shared)
        mc[h] = {'n_paired': len(shared), 'test_only_correct': only_a, 'reference_only_correct': only_b, 'p_two_sided': mcnemar_exact_p(only_a, only_b)}

    return {'schema_version': SCHEMA, 'identity': 'UNCONFIRMED', 'status': 'EXPLORATORY' if exploratory else 'FORMAL',
            'M': m, 'N_dp': n_dp, 'families': families, 'selected_agent': selected_agent,
            'thresholds': {'alpha_step1': ALPHA_STEP1, 'alpha_step2': ALPHA_STEP2, 'follow_margin': FOLLOW_MARGIN,
                           'tau_blind_s': tau_blind_s, 'min_dp': MIN_DP, 'min_families': MIN_FAMILIES, 'seed': seed, 'n_boot': n_boot},
            'hypotheses': hyp, 'SKEW_SENSITIVITY_FLAG': any(flagged.values()), 'skew_flag_components': flagged,
            'groups': _group_report(units, families), 'strata_full_track_dp_acc': strata, 'single_dp_acc': single, 'single_dp_mcnemar': mc,
            'ablations': ablation_comparison(units, selected_agent, families),
            'must_report': p2_text,
            'notes': ['full_track_dp_acc is the only C3 endpoint; single_dp_acc and McNemar are separate diagnostics',
                      'bootstrap intervals are percentile approximations, sign-flip exactness needs the symmetric null (prereg 4.3)']}


def render_markdown(v):
    """Plain Markdown summary of a ``verdict_e6`` result (numbers only; no interpretation beyond the preregistered verdict words)."""
    f = lambda x, n=3: 'n/a' if x is None else f'{x:.{n}f}'
    lines = ['# E6 verdict', '', f"- status: **{v['status']}** (M = {v['M']} families, N_dp = {v['N_dp']}; thresholds: N_dp >= {MIN_DP}, M >= {MIN_FAMILIES})",
             f"- selected agent group: {v['selected_agent']}; identity: {v['identity']}",
             f"- SKEW_SENSITIVITY_FLAG: {v['SKEW_SENSITIVITY_FLAG']} {v['skew_flag_components']}"]
    if v['must_report']:
        lines.append(f"- **{v['must_report']}**")
    lines += ['', '## Hypotheses (Holm 0.0125 / 0.025, one-sided)', '',
              '| h | test vs reference | verdict | formal-if | p_h (IUT max) | p_negative | Holm rank |', '|---|---|---|---|---|---|---|']
    for h, x in v['hypotheses'].items():
        lines.append(f"| {h} | {x['test_group']} vs {x['reference_group']} | {x['verdict']} | {x['verdict_if_formal']} | {f(x['p_h'], 5)} | "
                     f"{f(x['p_negative'], 5)} | {x['holm_rank']} |")
    for h, x in v['hypotheses'].items():
        lines += ['', f'### {h} components', '', '| comp | observed | p_flip | p_t | p_sign | skew | 97.5% CI | 95.0% CI |', '|---|---|---|---|---|---|---|---|']
        for c in COMPONENTS:
            y = x['components'][c]
            lines.append(f"| {c} | {f(y['observed'])} | {f(y['p_flip'], 5)} | {f(y['p_t'], 5)} | {f(y['p_sign'], 5)} | {f(y['skew'], 2)} | "
                         f"[{f(y['ci_97_5'][0])}, {f(y['ci_97_5'][1])}] | [{f(y['ci_95_0'][0])}, {f(y['ci_95_0'][1])}] |")
    lines += ['', '## Groups (family-aggregated)', '', '| group | wrong-person s | blind false-lock s | lost s | follow rate | full-track dp acc | dp n |', '|---|---|---|---|---|---|---|']
    for g, x in sorted(v['groups'].items()):
        lines.append(f"| {g} | {f(x['wrong_person_s'], 1)} | {f(x['blind_false_lock_s'], 1)} | {f(x['lost_s'], 1)} | {f(x['follow_rate'])} | "
                     f"{f(x['full_track_dp_acc'])} | {x['dp_n']} |")
    lines += ['', '## Decision-point strata (full-track accuracy)', '', '| group | VISIBLE | FULL_BLIND + TRUE_DEPARTURE |', '|---|---|---|']
    for g, x in sorted(v['strata_full_track_dp_acc'].items()):
        a, b = x['VISIBLE'], x['FULL_BLIND+TRUE_DEPARTURE']
        lines.append(f"| {g} | {f(a['full_track_dp_acc'])} (n={a['n']}) | {f(b['full_track_dp_acc'])} (n={b['n']}) |")
    lines += ['', '## Single-point paired answer (separate diagnostic, not part of C3)', '']
    for g, x in sorted(v['single_dp_acc'].items()):
        lines.append(f"- {g}: n = {x['n']}, accuracy = {f(x['single_dp_acc'])}")
    if v.get('ablations') or v.get('ablations_skipped'):
        lines += ['', '## Ablations (D403; EXPLORATORY, uncorrected, not in Holm)', '']
        for g, x in sorted((v.get('ablations') or {}).items()):
            lines += [f"### {g} vs {x['reference']} (M = {x['M']})", '', '| metric | ablation - selected | aggregate | p (two-sided, uncorrected sign-flip) |', '|---|---|---|---|']
            for name, y in x['paired_difference_ablation_minus_selected'].items():
                lines.append(f"| {name} | {f(y['observed'])} | {y['aggregate']} | {f(y['p_two_sided_uncorrected'], 5)} |")
            lines.append('')
        for sk in v.get('ablations_skipped') or []:
            lines.append(f"- skipped: {sk['root']} -> {sk['status']} ({sk['reason']})")
    lines += ['']
    lines += [f"- {n}" for n in v['notes']]
    return '\n'.join(lines) + '\n'

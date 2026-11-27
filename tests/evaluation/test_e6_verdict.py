"""E6 verdict (#721 G6): synthetic data only; every decision branch of the preregistration (sections 3.1-3.2 and 4)."""
import ast
import hashlib
import math
import random
from pathlib import Path

import pytest

from amidst.evaluation import e6_verdict as V

REPO = Path(__file__).resolve().parents[2]
SEL = 'DEANCHOR_HIST'
GROUPS = ('B1', 'AO_ORIG', 'DEANCHOR', SEL)


def build(m=12, dps=4, spec=None, regimes=('VISIBLE', 'VISIBLE', 'FULL_BLIND', 'TRUE_DEPARTURE')):
    """spec[group](i) -> dict(wp, bfl, follow, dp_ok). One segment per family; ``dps`` decision points per segment."""
    segs, pts = [], []
    for g in GROUPS:
        for i in range(m):
            s = spec[g](i)
            fam, case = f'E6-F{i + 1:02d}', f'E6-S{i + 1:02d}'
            segs.append({'case_id': case, 'family_id': fam, 'group': g, 'wrong_person_s': s['wp'], 'blind_false_lock_s': s['bfl'],
                         'lost_s': s.get('lost', 1.0), 'follow_rate': s['follow'], 'visible_ticks': 100})
            for j in range(dps):
                pts.append({'dp_id': f'{case}-DP{j + 1}', 'case_id': case, 'family_id': fam, 'group': g,
                            'gt_regime': regimes[j % len(regimes)], 'full_track_correct': j < s['dp_ok'],
                            'single_correct': j < s['dp_ok']})
    return segs, pts


def ref(wp=20.0, bfl=2.0, follow=0.6, dp_ok=2):
    return lambda i: {'wp': wp + (i % 3) * 0.5, 'bfl': bfl, 'follow': follow, 'dp_ok': dp_ok}


def better(wp=8.0, bfl=2.0, follow=0.7, dp_ok=4):
    return lambda i: {'wp': wp + (i % 4) * 0.4, 'bfl': bfl, 'follow': follow + (i % 2) * 0.01, 'dp_ok': dp_ok}


def worse(wp=40.0, bfl=2.0, follow=0.6, dp_ok=2):
    return lambda i: {'wp': wp + (i % 3), 'bfl': bfl, 'follow': follow, 'dp_ok': dp_ok}


def run(spec, **kw):
    segs, pts = build(spec=spec, **{k: kw.pop(k) for k in ('m', 'dps', 'regimes') if k in kw})
    return V.verdict_e6(segs, pts, selected_agent=SEL, **kw)


# ---- truth tables ---------------------------------------------------------------------------------------------------------------
def w(*cls, shown=True):
    return [{'cls': c, 'displayed': shown} for c in cls]


def test_full_track_visible():
    assert V.full_track_dp_correct('VISIBLE', w('LOST', 'CORRECT', 'LOST'))
    assert V.full_track_dp_correct('VISIBLE', w('CORRECT', 'MISLOCALIZED'))                 # mislocalized is not wrong-person/camera
    assert not V.full_track_dp_correct('VISIBLE', w('LOST', 'LOST'))                         # never correct
    assert not V.full_track_dp_correct('VISIBLE', w('CORRECT', 'WRONG_PERSON'))
    assert not V.full_track_dp_correct('VISIBLE', w('CORRECT', 'WRONG_CAMERA'))


def test_full_track_full_blind_and_departure():
    assert V.full_track_dp_correct('FULL_BLIND', w('BLIND_OK', 'LOST', 'BLIND_OK'))
    assert V.full_track_dp_correct('FULL_BLIND', w('BLIND_OK', 'BLIND_HOLD'))
    assert not V.full_track_dp_correct('FULL_BLIND', w('BLIND_OK', 'FALSE_LOCK'))
    assert V.full_track_dp_correct('TRUE_DEPARTURE', w('BLIND_OK', 'BLIND_OK', shown=False))
    assert not V.full_track_dp_correct('TRUE_DEPARTURE', [{'cls': 'FALSE_LOCK', 'displayed': True}, {'cls': 'BLIND_OK', 'displayed': False}])
    with pytest.raises(ValueError):
        V.full_track_dp_correct('SOMETHING', w('CORRECT'))
    with pytest.raises(ValueError):
        V.full_track_dp_correct('VISIBLE', [])


@pytest.mark.parametrize('regime,answer,hit,ok', [
    ('VISIBLE', 'SELECT', True, True), ('VISIBLE', 'OWN_BOX', True, True), ('VISIBLE', 'SELECT', False, False),
    ('VISIBLE', 'NOT_VISIBLE', False, False), ('VISIBLE', 'UNCERTAIN', True, False), ('VISIBLE', 'STILL_HERE_OCCLUDED', True, False),
    ('VISIBLE', None, True, False),
    ('FULL_BLIND', 'NOT_VISIBLE', False, True), ('FULL_BLIND', 'UNCERTAIN', False, True), ('FULL_BLIND', 'SELECT', True, False),
    ('FULL_BLIND', 'OWN_BOX', False, False), ('FULL_BLIND', 'STILL_HERE_OCCLUDED', False, False), ('FULL_BLIND', None, False, False),
    ('TRUE_DEPARTURE', 'NOT_VISIBLE', False, True), ('TRUE_DEPARTURE', 'UNCERTAIN', False, False), ('TRUE_DEPARTURE', 'SELECT', False, False),
    ('TRUE_DEPARTURE', 'STILL_HERE_OCCLUDED', False, False), ('TRUE_DEPARTURE', None, False, False)])
def test_single_dp_truth_table(regime, answer, hit, ok):
    assert V.single_dp_correct(regime, answer, hit_gt=hit) is ok


def test_majority_vote():
    assert V.majority([True, True, False]) and not V.majority([True, False, False])
    assert not V.majority([True, False]) and not V.majority([]) and V.majority(True) and not V.majority(False)
    assert V.majority([True, True, True, False]) and not V.majority([True, True, False, False])


# ---- statistics -----------------------------------------------------------------------------------------------------------------
def test_sign_flip_exact_values():
    assert V.sign_flip_p([1, 2, 3]) == 1 / 8
    assert V.sign_flip_p([1.0] * 12) == 1 / 4096
    assert V.sign_flip_p([-1.0, -2.0, -3.0]) == 1.0
    assert V.sign_flip_p([1, -1]) == 0.75                    # flips: ++ 0 vs T=0 -> three of four >= 0
    assert V.sign_flip_p([0.0, 0.0, 0.0]) == 1.0


def test_sign_flip_monte_carlo_for_large_m_is_seeded():
    x = [1.0] * 13
    p = V.sign_flip_p(x)
    assert p == V.sign_flip_p(x) and 1 / 10001 <= p <= 5 / 10001         # (1 + hits) / (n_perm + 1): all-positive flips are ~1 in 8192 draws
    assert V.sign_flip_p([1.0, -1.0] * 7) == V.sign_flip_p([1.0, -1.0] * 7)
    rng = random.Random(1)
    mixed = [rng.uniform(-1, 1) for _ in range(14)]
    assert 0 < V.sign_flip_p(mixed) <= 1


def test_student_t_tail_matches_the_prereg_critical_values():
    assert V.t_sf(2.593, 11) == pytest.approx(0.0125, abs=3e-4)
    assert V.t_sf(2.201, 11) == pytest.approx(0.025, abs=3e-4)
    assert V.t_sf(0.0, 11) == pytest.approx(0.5) and V.t_sf(-2.201, 11) == pytest.approx(0.975, abs=3e-4)
    assert V.t_sf(1.0, 1) == pytest.approx(0.25, abs=1e-9)                              # Cauchy


def test_paired_t_sign_skew_and_mcnemar():
    assert V.paired_t_p([1.0] * 5) == 0.0 and V.paired_t_p([0.0] * 5) == 0.5 and V.paired_t_p([-1.0] * 5) == 1.0 and V.paired_t_p([1.0]) == 1.0
    assert V.paired_t_p([1, 2, 3, 4, 5]) < 0.02
    assert V.sign_test_p([1, 2, 3, -1, 0]) == pytest.approx(5 / 16)          # zero dropped: P(Bin(4, .5) >= 3)
    assert V.sign_test_p([0, 0]) == 1.0
    assert V.skewness([1, 2, 3]) == pytest.approx(0.0) and V.skewness([1, 1, 1]) == 0.0 and V.skewness([1] * 11 + [100]) > 1.0
    assert V.mcnemar_exact_p(0, 0) == 1.0 and V.mcnemar_exact_p(5, 0) == pytest.approx(2 / 32) and V.mcnemar_exact_p(3, 3) == 1.0


def test_percentile_interval_and_determinism():
    vals = list(range(101))
    assert V._ci(vals, 95.0) == [2.5, 97.5] and V._ci(vals, 97.5) == [1.25, 98.75]
    a = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)}, n_boot=500)
    b = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)}, n_boot=500)
    assert a == b
    c = a['hypotheses']['P1']['components']['C1']
    assert c['ci_97_5'][0] <= c['ci_95_0'][0] <= c['ci_95_0'][1] <= c['ci_97_5'][1]


# ---- Holm gating ----------------------------------------------------------------------------------------------------------------
def test_holm_first_step_gates_both():
    passed, ranks = V._holm({'P1': 0.001, 'P2': 0.02}, {'P1': (True, True), 'P2': (True, True)})
    assert passed == {'P1': True, 'P2': True} and ranks == {'P1': 1, 'P2': 2}
    passed, _ = V._holm({'P1': 0.001, 'P2': 0.02}, {'P1': (False, True), 'P2': (True, True)})        # step-1 CI boundary fails
    assert passed == {'P1': False, 'P2': False}
    passed, _ = V._holm({'P1': 0.0126, 'P2': 0.0001}, {'P1': (True, True), 'P2': (True, True)})      # rank 1 is P2
    assert passed == {'P1': True, 'P2': True}
    passed, _ = V._holm({'P1': 0.02, 'P2': 0.03}, {'P1': (True, True), 'P2': (True, True)})          # step 1 fails: none
    assert passed == {'P1': False, 'P2': False}
    passed, _ = V._holm({'P1': 0.001, 'P2': 0.026}, {'P1': (True, True), 'P2': (True, True)})        # step 2 p too large
    assert passed == {'P1': True, 'P2': False}
    passed, _ = V._holm({'P1': 0.001, 'P2': 0.02}, {'P1': (True, True), 'P2': (True, False)})        # step-2 CI (95.0) boundary fails
    assert passed == {'P1': True, 'P2': False}


# ---- full verdict branches ------------------------------------------------------------------------------------------------------
def test_both_supported():
    out = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)})
    assert out['status'] == 'FORMAL' and out['M'] == 12 and out['N_dp'] == 48 and out['identity'] == 'UNCONFIRMED'
    p1, p2 = out['hypotheses']['P1'], out['hypotheses']['P2']
    assert p1['verdict'] == p2['verdict'] == 'SUPPORTED'
    assert p1['p_h'] == pytest.approx(1 / 4096) and {p1['holm_rank'], p2['holm_rank']} == {1, 2}
    assert out['must_report'] is None and not out['SKEW_SENSITIVITY_FLAG']
    for c in V.COMPONENTS:
        assert p1['components'][c]['boundary_ok_97_5'] and p2['components'][c]['boundary_ok_95_0']
    assert out['groups']['B1']['follow_rate'] == pytest.approx(0.6)
    assert out['strata_full_track_dp_acc']['DEANCHOR']['VISIBLE']['n'] == 24
    assert out['strata_full_track_dp_acc']['DEANCHOR']['FULL_BLIND+TRUE_DEPARTURE']['n'] == 24


def test_p1_supported_p2_inconclusive_and_the_mandatory_sentence():
    flat = lambda i: {'wp': 20.0 + (i % 3) * 0.5, 'bfl': 2.0, 'follow': 0.6, 'dp_ok': 2}
    out = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: flat})
    assert out['hypotheses']['P1']['verdict'] == 'SUPPORTED'
    assert out['hypotheses']['P2']['verdict'] == 'INCONCLUSIVE'
    assert out['hypotheses']['P2']['holm_negative_passed'] is False
    assert out['must_report'] == '改良後仍未證實優於現有規則'


def test_c4_blind_false_lock_tolerance_blocks_support():
    bad_blind = lambda i: {'wp': 8.0 + (i % 4) * 0.4, 'bfl': 2.0 + 3.0, 'follow': 0.7, 'dp_ok': 4}     # +3 s per family = +36 s total
    out = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: bad_blind})
    p2 = out['hypotheses']['P2']
    assert p2['verdict'] != 'SUPPORTED' and p2['components']['C4']['p_flip'] > 0.9
    assert p2['verdict'] == 'NOT_SUPPORTED'                                                          # C4 degradation is significant (4 * 1/4096)
    assert out['must_report'] == '改良後仍未證實優於現有規則'


def test_follow_rate_collapse_blocks_support():
    low_follow = lambda i: {'wp': 8.0 + (i % 4) * 0.4, 'bfl': 2.0, 'follow': 0.3, 'dp_ok': 4}          # -0.3 < -0.05 margin
    out = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: low_follow})
    assert out['hypotheses']['P2']['verdict'] == 'NOT_SUPPORTED'


def test_both_not_supported():
    out = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': worse(), SEL: worse(wp=50.0)})
    p1, p2 = out['hypotheses']['P1'], out['hypotheses']['P2']
    assert p1['verdict'] == p2['verdict'] == 'NOT_SUPPORTED'
    assert p1['p_negative'] == pytest.approx(4 / 4096) and p1['holm_negative_passed'] and p2['holm_negative_passed']
    assert not p1['holm_positive_passed']
    assert out['must_report'] == '改良後仍未證實優於現有規則'


def test_inconclusive_when_nothing_is_significant():
    noisy = lambda sign: (lambda i: {'wp': 20.0 + sign * (-1) ** i * 5, 'bfl': 2.0, 'follow': 0.6, 'dp_ok': 2 + (i % 2) * sign})
    out = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': noisy(1), SEL: noisy(1)})
    assert out['hypotheses']['P1']['verdict'] == out['hypotheses']['P2']['verdict'] == 'INCONCLUSIVE'
    assert not any(out['hypotheses'][h][k] for h in ('P1', 'P2') for k in ('holm_positive_passed', 'holm_negative_passed'))


def test_exploratory_when_too_few_families_or_points():
    spec = {'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)}
    few_fam = run(spec, m=7)
    assert few_fam['status'] == 'EXPLORATORY' and few_fam['M'] == 7 and few_fam['N_dp'] == 28
    assert few_fam['hypotheses']['P1']['verdict'] == 'EXPLORATORY' and few_fam['hypotheses']['P1']['verdict_if_formal'] == 'SUPPORTED'
    few_dp = run(spec, m=12, dps=3)                                                                   # 36 < 40 points, M fine
    assert few_dp['status'] == 'EXPLORATORY' and few_dp['M'] == 12 and few_dp['N_dp'] == 36
    boundary = run(spec, m=10, dps=4)                                                                 # M = 10 >= 8 and 40 points: formal
    assert boundary['status'] == 'FORMAL' and boundary['N_dp'] == 40
    m8 = run(spec, m=8, dps=5)
    assert m8['status'] == 'FORMAL' and m8['M'] == 8


def test_skew_sensitivity_flag_when_flip_and_t_disagree():
    def skewed(i):
        return {'wp': 20.0 - (100.0 if i == 0 else 1.0), 'bfl': 2.0, 'follow': 0.7, 'dp_ok': 4}
    out = run({'B1': ref(wp=20.0), 'AO_ORIG': ref(wp=20.0), 'DEANCHOR': skewed, SEL: better(wp=6.0)})
    p1 = out['hypotheses']['P1']
    c1 = p1['components']['C1']
    assert abs(c1['skew']) > 1 and c1['p_flip'] <= 0.0125 < c1['p_t']
    assert out['SKEW_SENSITIVITY_FLAG'] and 'C1' in p1['skew_flag_components'] and out['skew_flag_components']['P2'] == []


def test_same_family_segments_are_one_unit():
    segs, pts = build(spec={'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)})
    extra = [dict(r, case_id=r['case_id'] + 'b') for r in segs if r['family_id'] == 'E6-F01']
    extra_pts = [dict(r, dp_id=r['dp_id'] + 'b', case_id=r['case_id'] + 'b') for r in pts if r['family_id'] == 'E6-F01']
    out = V.verdict_e6(segs + extra, pts + extra_pts, selected_agent=SEL)
    assert out['M'] == 12 and out['N_dp'] == 52
    one = [r for r in segs if r['family_id'] == 'E6-F01' and r['group'] == 'B1'][0]['wrong_person_s']
    base = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)})
    assert out['groups']['B1']['wrong_person_s'] == pytest.approx(base['groups']['B1']['wrong_person_s'] + one)    # summed, not averaged


def test_replicates_are_averaged_and_voted():
    segs, pts = build(spec={'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)})
    for r in segs:
        if r['group'] == 'DEANCHOR':
            r['wrong_person_s'] = [r['wrong_person_s'] - 1, r['wrong_person_s'] + 1, r['wrong_person_s']]
    for r in pts:
        if r['group'] == 'DEANCHOR':
            r['full_track_correct'] = [r['full_track_correct']] * 3
            r['single_correct'] = None
    out = V.verdict_e6(segs, pts, selected_agent=SEL)
    base = run({'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)})
    assert out['groups']['DEANCHOR']['wrong_person_s'] == pytest.approx(base['groups']['DEANCHOR']['wrong_person_s'])
    assert out['single_dp_acc']['DEANCHOR']['n'] == 0 and out['single_dp_mcnemar']['P1']['n_paired'] == 0


def test_selected_agent_may_be_deanchor():
    segs, pts = build(spec={'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better()})
    out = V.verdict_e6([r for r in segs if r['group'] != SEL], [r for r in pts if r['group'] != SEL], selected_agent='DEANCHOR')
    assert out['hypotheses']['P2']['test_group'] == 'DEANCHOR' and out['hypotheses']['P1']['test_group'] == 'DEANCHOR'


def test_single_dp_is_reported_separately_and_does_not_change_c3():
    spec = {'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)}
    segs, pts = build(spec=spec)
    for r in pts:
        r['single_correct'] = False
    out = V.verdict_e6(segs, pts, selected_agent=SEL)
    assert out['hypotheses']['P1']['verdict'] == 'SUPPORTED'
    assert out['single_dp_acc']['DEANCHOR']['single_dp_acc'] == 0.0 and out['single_dp_mcnemar']['P1']['p_two_sided'] == 1.0


def test_input_errors():
    segs, pts = build(spec={'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better()})
    with pytest.raises(ValueError, match='MISSING_GROUPS'):
        V.verdict_e6([r for r in segs if r['group'] != 'B1'], [r for r in pts if r['group'] != 'B1'], selected_agent=SEL)
    with pytest.raises(ValueError, match='FAMILY_MISMATCH'):
        V.verdict_e6([r for r in segs if not (r['group'] == 'B1' and r['family_id'] == 'E6-F03')],
                     [r for r in pts if not (r['group'] == 'B1' and r['family_id'] == 'E6-F03')], selected_agent=SEL)
    with pytest.raises(ValueError, match='MISSING_DATA'):
        V.verdict_e6([r for r in segs if not (r['group'] == 'B1' and r['family_id'] == 'E6-F03')], pts, selected_agent=SEL)
    with pytest.raises(ValueError, match='DECISION_POINT_MISMATCH'):
        V.verdict_e6(segs, [r for r in pts if not (r['group'] == 'AO_ORIG' and r['dp_id'].endswith('DP1'))], selected_agent=SEL)


# ---- scorer untouched, standard library only --------------------------------------------------------------------------------------
def test_e3_scorer_is_untouched():
    raw = (REPO / 'src/amidst/evaluation/e3_scoring.py').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08'


def test_verdict_module_imports_only_the_standard_library():
    tree = ast.parse((REPO / 'src/amidst/evaluation/e6_verdict.py').read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or '').split('.')[0])
    assert mods <= {'__future__', 'itertools', 'math', 'random', 'collections'}, mods


# ---- D403 ablation comparison (exploratory, not in Holm) ------------------------------------------------------------------------
def ablated(segs, pts, group, d_wp=0.0, d_follow=0.0, bad_dp=False):
    seg2 = [dict(r, group=group, wrong_person_s=r['wrong_person_s'] + d_wp, follow_rate=r['follow_rate'] + d_follow) for r in segs if r['group'] == SEL]
    pts2 = [dict(r, group=group, full_track_correct=(False if bad_dp else r['full_track_correct'])) for r in pts if r['group'] == SEL]
    return seg2, pts2


def test_two_sided_sign_flip():
    assert V.sign_flip_p_two_sided([1, 1, 1]) == 0.25 and V.sign_flip_p_two_sided([1, -1]) == 1.0 and V.sign_flip_p_two_sided([0.0] * 3) == 1.0
    assert V.sign_flip_p_two_sided([-1.0] * 12) == 2 / 4096
    x = [1.0] * 13
    assert V.sign_flip_p_two_sided(x) == V.sign_flip_p_two_sided(x) and 0 < V.sign_flip_p_two_sided(x) < 0.01


def test_ablation_comparison_is_exploratory_and_leaves_the_verdict_alone():
    spec = {'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better(wp=6.0)}
    segs, pts = build(spec=spec)
    base = V.verdict_e6(segs, pts, selected_agent=SEL)
    s2, p2 = ablated(segs, pts, SEL + '+NO_IMAGE', d_wp=5.0, d_follow=-0.1, bad_dp=True)
    s3, p3 = ablated(segs, pts, SEL + '+NO_SPATIAL')
    out = V.verdict_e6(segs + s2 + s3, pts + p2 + p3, selected_agent=SEL)
    assert out['hypotheses'] == base['hypotheses'] and out['must_report'] == base['must_report'] and out['status'] == base['status']
    assert set(out['ablations']) == {SEL + '+NO_IMAGE', SEL + '+NO_SPATIAL'} and base['ablations'] == {}
    ni = out['ablations'][SEL + '+NO_IMAGE']
    assert ni['EXPLORATORY'] is True and ni['in_holm'] is False and ni['reference'] == SEL and ni['M'] == 12
    d = ni['paired_difference_ablation_minus_selected']
    assert d['wrong_person_s']['observed'] == pytest.approx(60.0) and d['wrong_person_s']['aggregate'] == 'sum over families'
    assert d['wrong_person_s']['p_two_sided_uncorrected'] == pytest.approx(2 / 4096)
    assert d['follow_rate']['observed'] == pytest.approx(-0.1) and d['follow_rate']['aggregate'] == 'mean over families'
    assert d['full_track_dp_acc']['observed'] == pytest.approx(-1.0)
    ns = out['ablations'][SEL + '+NO_SPATIAL']['paired_difference_ablation_minus_selected']
    assert ns['wrong_person_s']['observed'] == 0 and ns['wrong_person_s']['p_two_sided_uncorrected'] == 1.0
    md = V.render_markdown(dict(out, ablations_skipped=[{'root': 'r', 'status': 'BUDGET_SKIPPED', 'reason': 'x'}]))
    assert 'Ablations (D403; EXPLORATORY' in md and 'BUDGET_SKIPPED' in md and 'NO_IMAGE' in md


def test_ablation_family_mismatch_is_an_error():
    spec = {'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better()}
    segs, pts = build(spec=spec)
    s2, p2 = ablated(segs, pts, SEL + '+NO_IMAGE')
    with pytest.raises(ValueError, match='FAMILY_MISMATCH_ABLATION'):
        V.verdict_e6(segs + [r for r in s2 if r['family_id'] != 'E6-F02'], pts + [r for r in p2 if r['family_id'] != 'E6-F02'], selected_agent=SEL)


def test_ablation_decision_point_ids_must_match_the_selected_agent():
    spec = {'B1': ref(), 'AO_ORIG': ref(), 'DEANCHOR': better(), SEL: better()}
    segs, pts = build(spec=spec)
    s2, p2 = ablated(segs, pts, SEL + '+NO_SPATIAL')
    V.verdict_e6(segs + s2, pts + p2, selected_agent=SEL)                                              # same ids: fine
    with pytest.raises(ValueError, match='DECISION_POINT_MISMATCH_ABLATION:' + SEL + r'\+NO_SPATIAL'):
        V.verdict_e6(segs + s2, pts + p2[:-1], selected_agent=SEL)                                      # one decision point missing
    renamed = [dict(r, dp_id=r['dp_id'] + 'x') if r['dp_id'].endswith('DP1') else r for r in p2]
    with pytest.raises(ValueError, match='DECISION_POINT_MISMATCH_ABLATION'):
        V.verdict_e6(segs + s2, pts + renamed, selected_agent=SEL)

"""E8 scoring (#780): synthetic records only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'evaluation'))

from amidst.evaluation import e8_requests as R  # noqa: E402
from amidst.evaluation import e8_score as S  # noqa: E402

SNAP = {'state': 'TRACKING', 'active_cam': 'CAM_A', 'est_xy': [0.0, 0.0], 'lost_ticks': 0, 'seen_ago_s': 0.0}
CANDS = [{'camera_id': 'CAM_A', 'detection_id': 'D1', 'box': [0, 0, 10, 40], 'score': .9, 'colors': [], 'ground_xy': [5.0, 0.0]},
         {'camera_id': 'CAM_A', 'detection_id': 'D2', 'box': [50, 0, 60, 40], 'score': .5, 'colors': ['red'], 'ground_xy': [0.5, 0.0]}]
ENTRY = {'expected_answer': 'SELECT', 'expected_camera_ids': ['CAM_A'], 'expected_detection_ids': {'CAM_A': ['D2']}}


def req(case, tick, level, perm, keep=None):
    return R.build_request(case_id=case, dataset_group='e3', tick=tick, level=level, perm=perm, cands=CANDS, camera_ids=['CAM_A'],
                           snapshot=SNAP, keep_display=keep, scene=None)


def test_judge_truth_table():
    box_hit = {'kind': 'BOX', 'camera_id': 'CAM_A', 'detection_id': 'D2'}
    keep_none = {'kind': 'NONE', 'via': 'KEEP'}
    nv = {'kind': 'NONE', 'via': 'NOT_VISIBLE'}
    assert S.judge(box_hit, ENTRY, 'VISIBLE') is True
    assert S.judge({**box_hit, 'detection_id': 'D1'}, ENTRY, 'VISIBLE') is False
    assert S.judge(keep_none, ENTRY, 'FULL_BLIND') is True and S.judge(keep_none, ENTRY, 'TRUE_DEPARTURE') is False
    assert S.judge(nv, ENTRY, 'TRUE_DEPARTURE') is True
    assert S.judge({'kind': 'INVALID'}, ENTRY, 'FULL_BLIND') is False
    assert S.judge({'kind': 'NEEDS_MAC', 'camera_id': 'CAM_A'}, ENTRY, 'VISIBLE') is None
    assert S.judge({'kind': 'NEEDS_MAC', 'camera_id': 'CAM_A'}, ENTRY, 'VISIBLE', own_box_hit=True) is True
    assert S.regime_from_gt(None) == 'TRUE_DEPARTURE' and S.regime_from_gt({'present': True, 'gt_visible': []}) == 'FULL_BLIND'
    assert S.regime_from_label({'expected_answer': 'UNCERTAIN'}) == 'VISIBLE'


def test_majority_and_baselines():
    reqs = [req('E3-X1', 5, lv, p, keep={'camera_id': 'CAM_A', 'detection_id': 'D1'}) for lv in ('L0c', 'L1', 'L2') for p in R.PERMS]
    recs = S.baseline_records(reqs)
    groups = {(r['group'], r['level']) for r in recs}
    assert groups == {('FIRST', 'L0c'), ('RANDOM', 'L0c'), ('B1', 'L0c'), ('FIRST_RED', 'L1'), ('NEAREST_RED', 'L2')}
    cm = S.cells(recs, {'E3-X1|t5': ENTRY}, {'E3-X1|t5': 'VISIBLE'})
    assert cm[('FIRST', 'L0c')]['E3-X1|t5']['perms'] == {'p0': False, 'p1': True, 'p2': cm[('FIRST', 'L0c')]['E3-X1|t5']['perms']['p2']}
    assert cm[('FIRST_RED', 'L1')]['E3-X1|t5']['majority'] is True and cm[('B1', 'L0c')]['E3-X1|t5']['majority'] is False
    assert cm[('NEAREST_RED', 'L2')]['E3-X1|t5']['majority'] is True
    pb = S.position_bias(recs)
    assert pb['first_option_rate']['FIRST|L0c|p0'] == 1.0 and pb['order_agreement']['FIRST_RED|L1'] == 1.0


def _cell(flags):
    return {f'b{i}': {'perms': {}, 'majority': f, 'mean': float(f)} for i, f in enumerate(flags)}


def test_compare_and_primary():
    fam = {f'b{i}': f'F{i % 16:02d}' for i in range(48)}
    good, bad = _cell([True] * 48), _cell([i % 4 == 0 for i in range(48)])
    cm = {('laya_typed', 'L2'): good, ('laya_typed', 'L3'): bad, ('qwen7b', 'L2'): bad, ('qwen7b', 'L3'): bad, S.H1_REF: bad}
    v = S.primary_verdict(cm, fam)
    assert v['H1a']['status'] == 'SUPPORTED' and v['H1a']['M'] == 16 and v['H1a']['n_dp'] == 48
    assert v['H1b']['status'] == 'INCONCLUSIVE' and v['H1b']['diff'] == 0
    small = S.compare(_cell([True] * 10), _cell([False] * 10), {f'b{i}': 'F' for i in range(10)})
    assert S.status_of(small, True, 5) == 'EXPLORATORY'


def test_select_groups_tie_rules():
    cm = {('laya_typed', 'L2'): _cell([True, True, False]), ('laya_typed', 'L1'): _cell([True, True, False]),
          ('qwen7b', 'L3'): _cell([True, True, False]), ('qwen3b', 'L3'): _cell([True, False, False])}
    sel = S.select_groups(cm)
    assert sel['per_model']['laya_typed']['level'] == 'L1'
    assert sel['selected'] == {'model': 'laya_typed', 'level': 'L1'}


def test_h2_noninferiority():
    segs, dps = [], []
    for i in range(16):
        for g, wp in (('B1', 1.0), ('SELECTED', 1.2)):
            segs.append({'group': g, 'family_id': f'F{i}', 'case_id': f'C{i}', 'follow_rate': 0.8, 'visible_ticks': 100,
                         'wrong_person_s': wp, 'blind_false_lock_s': 0.0})
            dps.append({'group': g, 'family_id': f'F{i}', 'full_track_correct': True})
    h = S.h2_test(segs, dps)
    assert h['M'] == 16 and round(h['observed']['wrong_person_diff_sum_s'], 6) == 3.2
    assert h['p'] < 0.01
    segs_bad = [dict(s, wrong_person_s=s['wrong_person_s'] + (2.0 if s['group'] == 'SELECTED' else 0)) for s in segs]
    assert S.h2_test(segs_bad, dps)['p'] > 0.5


def test_early_switch_conclusion_and_unified_section():
    ref = {10: 'WRONG', 11: 'WRONG', 12: 'CORRECT'}
    test = {10: 'CORRECT'}
    assert S.first_correct(test, 10) == 0 and S.first_correct(ref, 10) == 2
    assert S.early_switch_s(test, ref, 10) == round(2 * R.TICK_S, 3) and S.early_switch_s(ref, test, 10) < 0
    sup = {'status': 'SUPPORTED'}
    prim = {'H1a': sup, 'H2': sup}
    assert S.conclusion(prim, {'S2_qwen7b_L2': {'status': 'SUPPORTED', 'diff': 0.1}}) == 'AGENT_BETTER_THAN_RULE'
    assert S.conclusion(prim, {'S2_qwen7b_L2': {'status': 'INCONCLUSIVE', 'diff': 0.1}}) == 'BEATS_COLOUR_HEURISTIC_CLOSED_LOOP_NOT_WORSE'
    assert S.conclusion({'H2': sup}, {}) == 'CLOSED_LOOP_NOT_WORSE_SINGLE_POINT_NOT_BETTER'
    flat = {'S2_qwen7b_L2': {'p_holm': 0.5, 'diff': 0.0}}
    assert S.conclusion({}, flat, union_answerable=0.7) == 'INSUFFICIENT_INFORMATION'
    rule_wins = {'S2_qwen7b_L2': {'status': 'SUPPORTED', 'diff': -0.2, 'p_holm': 0.001}}
    assert S.conclusion({}, rule_wins, first_option={'qwen7b|L2|p0': 0.9}) == 'MODEL_TOO_SMALL'
    assert S.conclusion({}, rule_wins) == 'INCONCLUSIVE'
    table = {'b0': {'expected_answer': 'SELECT'}, 'b1': {'expected_answer': 'UNCERTAIN'}, 'b2': {'expected_answer': 'KEEP'}}
    cm = {('A', 'L1'): {'b0': {'majority': True}, 'b1': {'majority': False}, 'b2': {'majority': False}}}
    assert S.union_answerable(cm, table) == 0.5
    res = {'conclusion': 'INCONCLUSIVE', 'part1': {'accuracy': {'A|L1': {'majority_acc': .5, 'mean_acc': .4}},
                                                   'position_bias': {'first_option_rate': {}, 'order_agreement': {}},
                                                   'primary': {'H1a': {'status': 'EXPLORATORY'}, 'note': 'x'}, 'secondary': {},
                                                   'selection': {'selected': None}},
           'part2': {'per_group': {'B1': {'follow_rate': .7}}, 'early_switch_s': {}}}
    sec = S.unified_section(res)
    assert sec['schema'] == 'e8_unified_v1' and sec['verdicts'] == {'H1a': 'EXPLORATORY'} and sec['identity_status'] == 'UNCONFIRMED'

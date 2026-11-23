"""F1 (#660): unified E3 scorer. Synthetic inputs only (no LOCAL assets, no GT files)."""
import ast
from pathlib import Path

import pytest

from amidst.evaluation import e3_scoring as e3

ROOT = Path(__file__).resolve().parents[2]
BODY = (100.0, 100.0, 160.0, 300.0)          # GT target body box (60 x 200 px)
PERSON = (98.0, 105.0, 158.0, 295.0)         # tight person box: IoU high
TINY = (120.0, 120.0, 135.0, 140.0)          # small box centred on the target (the W2 "sports ball" case)
OTHER = (400.0, 100.0, 460.0, 300.0)         # someone else


def tick(t=0, cam='C1', boxes=(PERSON,), visible=('C1',), body=BODY, **kw):
    kw.setdefault('tick_us', 200_000)
    return e3.Tick(t, cam, boxes=tuple(boxes), visible=frozenset(visible), body=body, size=(960, 540), **kw)


def live(a, b, **kw):
    return e3.ticks_from_live(a, b, 'T', tick_us=kw.pop('tick_us', 50_000), size=kw.pop('size', (960, 540)))


def test_judge_box_same_for_index_and_own_boxes_and_iou_subset_of_primary():
    j = e3.judge_box(PERSON, BODY, (960, 540))
    assert j['primary'] and j['iou_hit'] and j['iou'] > 0.8
    t = e3.judge_box(TINY, BODY, (960, 540))
    assert t['center_in'] and t['primary'] and not t['iou_hit']
    o = e3.judge_box(OTHER, BODY, (960, 540))
    assert not o['primary'] and not o['iou_hit']
    assert not e3.judge_box(PERSON, None)['primary']


def test_body_is_clipped_to_image_before_iou():
    body = (-100.0, 100.0, 60.0, 300.0)       # 100 px of the body lies left of the image
    box = (0.0, 100.0, 60.0, 300.0)            # the visible part, exactly
    assert e3.judge_box(box, body, (960, 540))['iou'] == pytest.approx(1.0)
    assert e3.judge_box(box, body, None)['iou'] < 0.4


@pytest.mark.parametrize('tk,primary,iou', [
    (tick(), 'CORRECT', 'CORRECT'),
    (tick(boxes=(TINY,)), 'CORRECT', 'MISLOCALIZED'),
    (tick(boxes=(OTHER,)), 'WRONG_PERSON', 'WRONG_PERSON'),
    (tick(cam='C2', body=None), 'WRONG_CAMERA', 'WRONG_CAMERA'),
    (tick(cam=None, boxes=()), 'LOST', 'LOST'),
    (tick(visible=()), 'FALSE_LOCK', 'FALSE_LOCK'),
    (tick(cam=None, boxes=(), visible=()), 'BLIND_OK', 'BLIND_OK'),
    (tick(boxes=(), visible=(), hold_ok=True), 'BLIND_HOLD', 'BLIND_HOLD'),
    (tick(boxes=(), visible=('C1',)), 'CORRECT', 'CORRECT'),
    (tick(boxes=(), visible=('C2',), hold_ok=True), 'CORRECT', 'CORRECT'),
    (tick(boxes=(), visible=('C2',)), 'WRONG_CAMERA', 'WRONG_CAMERA'),
    (tick(boxes=(OTHER, PERSON)), 'CORRECT', 'CORRECT'),
])
def test_classify_four_error_classes(tk, primary, iou):
    assert e3.classify(tk, 'primary') == primary
    assert e3.classify(tk, 'iou') == iou


def test_metrics_denominator_is_gt_visible_time_and_shares_sum_to_one():
    ticks = [tick(0), tick(200_000, boxes=(TINY,)), tick(400_000, boxes=(OTHER,)), tick(600_000, cam=None, boxes=()),
             tick(800_000, cam='C2', body=None), tick(1_000_000, visible=()), tick(1_200_000, cam=None, boxes=(), visible=())]
    s = e3.score_event(ticks)
    p, i = s['primary'], s['iou']
    assert p['visible_ticks'] == 5 and p['visible_s'] == pytest.approx(1.0)
    assert p['follow_rate'] == pytest.approx(2 / 5) and i['follow_rate'] == pytest.approx(1 / 5)
    for m in (p, i):
        assert m['follow_rate'] + sum(m['error_share'].values()) == pytest.approx(1.0)
    assert p['wrong_person_s'] == pytest.approx(0.4)          # WRONG_PERSON + WRONG_CAMERA
    assert i['mislocalized_s'] == pytest.approx(0.2) and p['mislocalized_s'] == 0
    assert p['lost_s'] == pytest.approx(0.2) and p['false_lock_s'] == pytest.approx(0.2)
    assert p['follow_rate'] <= 1.0


def test_blind_hold_is_neither_correct_nor_error():
    ticks = [tick(0), tick(200_000, boxes=(), visible=(), hold_ok=True), tick(400_000)]
    m = e3.metrics(ticks)
    assert m['follow_rate'] == 1.0 and m['visible_ticks'] == 2 and m['counts']['BLIND_HOLD'] == 1 and m['false_lock_s'] == 0


def test_reacquire_latency_uses_visible_time_and_censors():
    ticks = [tick(0), tick(200_000, cam=None, boxes=()), tick(400_000, cam=None, boxes=(), visible=()),
             tick(600_000, cam=None, boxes=()), tick(800_000), tick(1_000_000, boxes=(OTHER,))]
    eps = e3.reacquire_episodes(ticks, [e3.classify(t) for t in ticks], 200_000)
    assert [e['latency_s'] for e in eps] == [pytest.approx(0.4), pytest.approx(0.2)]
    assert [e['censored'] for e in eps] == [False, True]
    m = e3.metrics(ticks)
    assert m['reacquire']['episodes'] == 2 and m['reacquire']['censored'] == 1 and m['reacquire']['median_s'] == pytest.approx(0.4)


def test_camera_topk_with_random_expectation():
    items = [(['C1', 'C2', 'C3'], {'C3'}, 5), (['C2', 'C1', 'C4'], {'C2'}, 5), (['C1'], set(), 5)]
    r = e3.camera_topk(items)
    assert r['n'] == 2 and r['top1'] == 1 and r['top3'] == 2
    assert r['random_top1_rate'] == pytest.approx(0.2) and r['random_top3_rate'] == pytest.approx(0.6)
    assert e3.random_topk(5, 2, 3) == pytest.approx(1 - 1 / 10)


def test_frame_outcomes_and_prf_share_the_box_judgement():
    outs = [e3.frame_outcome(True, PERSON, True, BODY), e3.frame_outcome(True, TINY, True, BODY),
            e3.frame_outcome(True, PERSON, False, None), e3.frame_outcome(False, None, True, BODY), e3.frame_outcome(False, None, False, None)]
    assert outs == ['TP', 'TP', 'FP_absent', 'FN', 'TN']
    assert e3.frame_outcome(True, TINY, True, BODY, criterion='iou') == 'FP_wrong_box'
    r = e3.frame_prf(outs)
    assert r['precision'] == pytest.approx(2 / 3) and r['recall'] == pytest.approx(2 / 3)


def test_api_stats():
    r = e3.api_stats([{'latency_s': 1.0, 'cost_usd': 0.01, 'adopted': True}, {'latency_s': 3.0, 'cost_usd': 0.03, 'adopted': False},
                      {'error': 'TIMEOUT'}])
    assert r['decisions'] == 3 and r['errors'] == 1 and r['adoption_rate'] == pytest.approx(1 / 3, abs=1e-4)
    assert r['latency_p50_s'] == pytest.approx(2.0) and r['cost_usd_total'] == pytest.approx(0.04)


def _live(est, cam='C1', state='TRACKING', box=None, gt_boxes=None, vis=('C1',), other_xy=(9.0, 9.0)):
    a = [{'tick': 1, 't_capture': 50, 'actors': [{'id': 'T', 'present': True, 'xy': [1.0, 1.0], 'gt_visible': list(vis),
                                                 **({'gt_boxes': gt_boxes} if gt_boxes else {})},
                                                {'id': 'A', 'present': True, 'xy': list(other_xy), 'gt_visible': ['C1']}]}]
    tr = {'state': state, 'active_cam': cam, 'est_xy': est, 'lost_ticks': 0}
    if box:
        tr['box'] = box
    return a, [{'tick': 1, 't_capture': 50, 't_resp': 60, 'tracking': tr}]


def test_live_positional_adapter_reads_live_ab_logs():
    a, b = _live([1.2, 1.1])
    [t] = live(a, b)
    assert e3.classify(t) == 'CORRECT' and e3.classify(t, 'iou') is None
    assert e3.score_event([t])['iou'] == {'criterion': 'iou', 'available': False, 'reason': 'NO_BOX_FOR_IOU', 'ticks': 1}
    a, b = _live([9.1, 9.0])
    assert e3.classify(live(a, b)[0]) == 'WRONG_PERSON'
    a, b = _live([5.0, 5.0])
    assert e3.classify(live(a, b)[0]) == 'MISLOCALIZED'
    a, b = _live(None, state='LOST')
    assert e3.classify(live(a, b)[0]) == 'LOST'
    a, b = _live([5.0, 5.0], cam='C2')
    assert e3.classify(live(a, b)[0]) == 'WRONG_CAMERA'


def test_live_adapter_uses_boxes_when_logged():
    a, b = _live([1.2, 1.1], box=list(TINY), gt_boxes={'C1': list(BODY)})
    [t] = live(a, b)
    assert e3.classify(t) == 'CORRECT' and e3.classify(t, 'iou') == 'MISLOCALIZED'


def _imports(path):
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or '')
    return names


def test_inference_side_never_imports_the_scorer_or_gt():
    """GT isolation (DEVELOPMENT_RULES): inference packages must not import any evaluation module (scorer, GT loader)."""
    offenders = []
    for pkg in ('q1q5', 'live_mode'):
        for path in (ROOT / 'src/amidst' / pkg).rglob('*.py'):
            if any(n == 'amidst.evaluation' or n.startswith('amidst.evaluation.') for n in _imports(path)):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, offenders


def test_scorer_module_is_pure():
    names = _imports(ROOT / 'src/amidst/evaluation/e3_scoring.py')
    assert set(names) <= {'__future__', 'math', 'random', 'statistics', 'collections', 'dataclasses'}, names


def test_decision_point_window_mcnemar_and_bootstrap():
    ticks = [tick(0, cam=None, boxes=()), tick(1_000_000), tick(2_000_000)]
    assert e3.decision_point_correct(ticks, 0)
    assert not e3.decision_point_correct(ticks + [tick(2_800_000, boxes=(OTHER,))], 0)
    assert not e3.decision_point_correct([tick(0, cam=None, boxes=())], 0)
    assert e3.decision_point_correct([tick(0, boxes=(TINY,))], 0) and not e3.decision_point_correct([tick(0, boxes=(TINY,))], 0, criterion='iou')
    assert e3.majority([True, True, False]) and not e3.majority([True, False, False]) and not e3.majority([True, False])
    m = e3.mcnemar([(True, False)] * 9 + [(False, True)] + [(True, True)] * 5)
    assert m['agent_only'] == 9 and m['baseline_only'] == 1 and m['favours'] == 'agent' and m['p'] == pytest.approx(22 / 1024)
    assert e3.mcnemar([(True, True)])['p'] == 1.0
    ci = e3.cluster_bootstrap({'s1': 1.0, 's2': 2.0, 's3': 3.0}, lambda xs: sum(xs) / len(xs))
    assert 1.0 <= ci[0] <= ci[1] <= 3.0
    assert ci == e3.cluster_bootstrap({'s1': 1.0, 's2': 2.0, 's3': 3.0}, lambda xs: sum(xs) / len(xs))


# --------------------------------------------------------------------------------------------- #662 Opus 5: tick_us, size, GT_UNKNOWN
def test_tick_us_has_no_default_and_must_agree():
    bare = [e3.Tick(0, 'C1', boxes=(PERSON,), visible=frozenset({'C1'}), body=BODY, size=(960, 540))]
    with pytest.raises(ValueError, match='TICK_US_REQUIRED'):
        e3.metrics(bare)
    assert e3.metrics(bare, tick_us=200_000)['visible_s'] == pytest.approx(0.2)
    with pytest.raises(ValueError, match='TICK_US_MISMATCH'):
        e3.metrics([tick(0)], tick_us=50_000)
    with pytest.raises(ValueError, match='TICK_US_MIXED'):
        e3.metrics([tick(0), tick(200_000, tick_us=50_000)])


def test_live_adapter_requires_tick_us_and_size_and_counts_50ms_seconds():
    a, b = _live([1.2, 1.1])
    with pytest.raises(TypeError):
        e3.ticks_from_live(a, b, 'T')
    with pytest.raises(ValueError, match='SIZE_REQUIRED'):
        e3.ticks_from_live(a, b, 'T', tick_us=50_000, size=None)
    rows_a, rows_b = [], []
    for k in range(20):                                   # 20 LIVE ticks of 50 ms = 1.0 s visible
        ak, bk = _live([1.2, 1.1])
        ak[0]['tick'] = bk[0]['tick'] = k
        rows_a += ak
        rows_b += bk
    ts = live(rows_a, rows_b)
    assert all(t.tick_us == 50_000 and t.size == (960, 540) for t in ts)
    m = e3.metrics(ts)
    assert m['visible_s'] == pytest.approx(1.0) and m['tick_s'] == pytest.approx(0.05)


def test_live_adapter_clips_gt_box_with_size():
    a, b = _live([1.2, 1.1], box=[300.0, 100.0, 320.0, 300.0], gt_boxes={'C1': [300.0, 100.0, 400.0, 300.0]})
    [t] = live(a, b, size=(320, 180))
    assert e3.judge_box(t.boxes[0], t.body, t.size)['iou'] > e3.judge_box(t.boxes[0], t.body)['iou']


def test_missing_gt_box_is_gt_unknown_not_wrong_person_and_stops_above_5_percent():
    t_unknown = tick(boxes=(OTHER,), body=None)
    assert e3.classify(t_unknown) == 'GT_UNKNOWN' and e3.classify(t_unknown, 'iou') == 'GT_UNKNOWN'
    ticks = [tick(i * 200_000) for i in range(19)] + [tick(19 * 200_000, body=None)]
    m = e3.metrics(ticks)
    assert m['visible_ticks'] == 19 and m['follow_rate'] == 1.0 and m['wrong_person_s'] == 0
    assert m['counts']['GT_UNKNOWN'] == 1 and m['gt_unknown_share'] == pytest.approx(0.05) and m['gt_unknown_stop'] is False
    m = e3.metrics(ticks[:9] + [tick(9 * 200_000, body=None)])
    assert m['gt_unknown_stop'] is True
    a, b = _live([1.2, 1.1], box=list(PERSON), gt_boxes={'C2': list(BODY)})   # A row lacks the shown camera's GT box
    assert e3.classify(live(a, b)[0]) == 'GT_UNKNOWN'


def test_bootstrap_level_widens_interval():
    data = {f's{i}': float(i % 5) for i in range(12)}
    mean = (lambda xs: sum(xs) / len(xs))
    lo95, hi95 = e3.cluster_bootstrap(data, mean)
    lo99, hi99 = e3.cluster_bootstrap(data, mean, level=0.99)
    assert lo99 <= lo95 and hi99 >= hi95


# --------------------------------------------------------------------------------------------- verdicts (preregistration §6)
MC_AGENT = {'p': 0.01, 'favours': 'agent'}
MC_NONE = {'p': 0.5, 'favours': None}
MC_RULE = {'p': 0.01, 'favours': 'baseline'}


def test_h1_supported_only_when_all_three_conditions_hold():
    ok = dict(wp_diff_ci=(-3.0, -0.5), follow_diff_ci=(-0.02, 0.1), mc=MC_AGENT, n_points=40, n_segments=8)
    assert e3.verdict_h1(**ok)['verdict'] == e3.SUPPORTED
    assert e3.verdict_h1(**{**ok, 'wp_diff_ci': (-3.0, 0.2)})['verdict'] == e3.INCONCLUSIVE      # condition 1 missing
    assert e3.verdict_h1(**{**ok, 'follow_diff_ci': (-0.08, 0.1)})['verdict'] == e3.INCONCLUSIVE   # condition 2 missing
    assert e3.verdict_h1(**{**ok, 'mc': MC_NONE})['verdict'] == e3.INCONCLUSIVE                     # condition 3 missing


def test_h1_not_supported_and_exploratory_and_robustness_note():
    base = dict(follow_diff_ci=(-0.02, 0.1), mc=MC_NONE, n_points=40, n_segments=8)
    assert e3.verdict_h1(wp_diff_ci=(0.1, 2.0), **base)['verdict'] == e3.NOT_SUPPORTED
    assert e3.verdict_h1(wp_diff_ci=(-1, 1), **{**base, 'follow_diff_ci': (-0.3, -0.06)})['verdict'] == e3.NOT_SUPPORTED
    assert e3.verdict_h1(wp_diff_ci=(-1, 1), **{**base, 'mc': MC_RULE})['verdict'] == e3.NOT_SUPPORTED
    r = e3.verdict_h1(wp_diff_ci=(-3.0, -0.5), follow_diff_ci=(-0.02, 0.1), mc=MC_AGENT, n_points=38, n_segments=9)
    assert r['verdict'] == e3.EXPLORATORY and r['would_be'] == e3.SUPPORTED and r['verdict_zh'] == '探索性'
    r = e3.verdict_h1(wp_diff_ci=(-3.0, -0.5), follow_diff_ci=(-0.02, 0.1), mc=MC_AGENT, n_points=40, n_segments=7)
    assert r['verdict'] == e3.EXPLORATORY
    r = e3.verdict_h1(wp_diff_ci=(-3.0, -0.5), follow_diff_ci=(-0.02, 0.1), mc=MC_AGENT, n_points=40, n_segments=8,
                      iou_follow_diff=-0.08)
    assert r['verdict'] == e3.SUPPORTED and r['robustness'] == 'DEPENDS_ON_BOX_CRITERION'


@pytest.mark.parametrize('a1b1,a2b2,expected', [
    ((-2, -0.1), (-2, -0.1), e3.SUPPORTED),
    ((-1, 1), (-2, -0.1), e3.NOT_SUPPORTED),       # interaction: gain only with spatial info
    ((-2, -0.1), (-1, 1), e3.INCONCLUSIVE),
    ((-1, 1), (-1, 1), e3.INCONCLUSIVE),           # no difference observed
    ((0.1, 2), (-2, -0.1), e3.NOT_SUPPORTED),      # Agent worse in one comparison
    ((-2, -0.1), (0.1, 2), e3.NOT_SUPPORTED),
    ((0.1, 2), (-1, 1), e3.NOT_SUPPORTED),
])
def test_h2_combination_table(a1b1, a2b2, expected):
    r = e3.verdict_h2(a1b1, a2b2, d_exit_diff_ci=(-0.02, 0.2), n_points=40, n_segments=8)
    assert r['verdict'] == expected


def test_h2_needs_d_class_exit_condition_and_sample():
    assert e3.verdict_h2((-2, -0.1), (-2, -0.1), (-0.1, 0.2), 40, 8)['verdict'] == e3.INCONCLUSIVE
    assert e3.verdict_h2((-2, -0.1), (-2, -0.1), (-0.02, 0.2), 38, 9)['verdict'] == e3.EXPLORATORY


def test_h4_w2_b41_data_is_not_supported_and_small_sample_is_exploratory():
    # W2 B4-1 Agent A: top-1 8/40 with random expectation 10/40, top-3 37/40 (top-3 never counts)
    w2 = dict(top1_diff_ci=(0.05, 0.3), a2_top1_rate=8 / 40, a2_random_top1_rate=10 / 40, a2_top1_ci=(0.1, 0.33),
              a2_latency_median=1.0, a1_latency_median=2.0)
    assert e3.verdict_h4(**w2, n_reappear=40)['verdict'] == e3.NOT_SUPPORTED
    r = e3.verdict_h4(**w2, n_reappear=3)
    assert r['verdict'] == e3.EXPLORATORY and r['would_be'] == e3.NOT_SUPPORTED
    assert e3.verdict_h4(**w2, n_reappear=29)['verdict'] == e3.EXPLORATORY


def test_h4_supported_needs_top1_gain_above_random_and_faster():
    good = dict(top1_diff_ci=(0.05, 0.3), a2_top1_rate=0.6, a2_random_top1_rate=0.25, a2_top1_ci=(0.45, 0.75),
                a2_latency_median=1.0, a1_latency_median=2.0, n_reappear=30)
    assert e3.verdict_h4(**good)['verdict'] == e3.SUPPORTED
    assert e3.verdict_h4(**{**good, 'top1_diff_ci': (-0.05, 0.3)})['verdict'] == e3.NOT_SUPPORTED
    assert e3.verdict_h4(**{**good, 'a2_top1_ci': (0.2, 0.75)})['verdict'] == e3.INCONCLUSIVE
    assert e3.verdict_h4(**{**good, 'a2_latency_median': 3.0})['verdict'] == e3.INCONCLUSIVE


def test_h5_layers_bonferroni_precision_and_sample():
    up, flat, down = (0.02, 0.2), (-0.1, 0.1), (-0.2, -0.02)
    L = lambda *cis, n=60: {k: {'n': n, 'recall_diff_ci': ci} for k, ci in zip(e3.H5_LAYERS, cis)}
    assert e3.verdict_h5(L(up, up, flat, flat, flat), (-0.03, 0.02))['verdict'] == e3.SUPPORTED
    assert e3.verdict_h5(L(up, up, flat, flat, flat), (-0.08, 0.02))['verdict'] == e3.INCONCLUSIVE   # precision lower <= -0.05
    assert e3.verdict_h5(L(up, up, flat, flat, flat), (-0.2, -0.06))['verdict'] == e3.NOT_SUPPORTED
    assert e3.verdict_h5(L(up, flat, flat, flat, flat), (-0.03, 0.02))['verdict'] == e3.INCONCLUSIVE
    assert e3.verdict_h5(L(down, down, flat, flat, flat), (-0.03, 0.02))['verdict'] == e3.NOT_SUPPORTED
    small = L(up, up, flat, flat, flat, n=49)
    small['similar_clothing']['n'] = 60
    r = e3.verdict_h5(small, (-0.03, 0.02))
    assert r['verdict'] == e3.EXPLORATORY and r['reasons']['judged_layers'] == ['similar_clothing']
    assert e3.H5_LEVEL == 0.99

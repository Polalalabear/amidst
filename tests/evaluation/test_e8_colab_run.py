"""E8 Colab orchestration (#780): grouping, the §6.3 4 h rule, resumable checkpoints and SMOKE backends (no models, no GPU)."""
from amidst.evaluation import e8_colab_run as C
from amidst.evaluation import e8_requests as R

SNAP = {'state': 'TRACKING', 'active_cam': 'CAM_A', 'est_xy': [0.0, 0.0], 'lost_ticks': 0, 'seen_ago_s': 0.0}
CANDS = [{'camera_id': 'CAM_A', 'detection_id': 'D1', 'box': [0, 0, 10, 40], 'score': .9, 'colors': ['red'], 'ground_xy': [1.0, 0.0]},
         {'camera_id': 'CAM_A', 'detection_id': 'D2', 'box': [50, 0, 60, 40], 'score': .5, 'colors': [], 'ground_xy': [3.0, 0.0]}]


def _reqs(levels=('L0', 'L1', 'L2')):
    return [R.build_request(case_id='E3-X1', dataset_group='e3', tick=5, level=lv, perm=p, cands=CANDS, camera_ids=['CAM_A'],
                            snapshot=SNAP, keep_display=None, scene=None) for lv in levels for p in R.PERMS]


def test_part1_groups_and_l0_fallback():
    reqs = _reqs(('L1', 'L2'))
    reqs += [dict(r, level='L0') for r in reqs if r['level'] == 'L1']      # grouping reads only level/perm (L0 needs an E7 row)
    full = C.part1_groups(reqs, 'qwen7b')
    assert [(lv, p) for lv, p, _ in full] == [(lv, p) for lv in ('L0', 'L1', 'L2') for p in R.PERMS]
    cut = C.part1_groups(reqs, 'qwen7b', qwen_l0_p0_only=True)
    assert [(lv, p) for lv, p, _ in cut if lv == 'L0'] == [('L0', 'p0')] and len(cut) == len(full) - 2
    assert len(C.part1_groups(reqs, 'laya_text', qwen_l0_p0_only=True)) == len(full)     # the fallback cuts Qwen L0 only
    slow = {'qwen3b': {'L0': 600.0, 'text': 1.0}, 'qwen7b': {'L0': 600.0, 'text': 1.0}}
    h_full = C.projected_hours(reqs, slow, part2_cases=0)
    h_cut = C.projected_hours(reqs, slow, part2_cases=0, qwen_l0_p0_only=True)
    assert h_full > h_cut and round((h_full - h_cut) * 3600) == 2 * 2 * 600


def test_run_group_resumes_from_checkpoint(tmp_path):
    reqs = [r for r in _reqs(('L1',)) if r['perm'] == 'p0']
    calls = []

    def ask(req):
        calls.append(req['request_id'])
        return R.baseline_answer('FIRST_RED', req), None, 0.01
    fp = {'pack': 'x'}
    res, resumed = C.run_group('laya_text', 'L1', 'p0', reqs, ask, tmp_path, fp)
    assert not resumed and res['n'] == 1 and res['format_invalid'] == 0 and len(calls) == 1
    again, resumed = C.run_group('laya_text', 'L1', 'p0', reqs, ask, tmp_path, fp)
    assert resumed and again == res and len(calls) == 1
    _, resumed = C.run_group('laya_text', 'L1', 'p0', reqs, ask, tmp_path, {'pack': 'y'})   # new fingerprint re-runs
    assert not resumed and len(calls) == 2


def test_smoke_backends_are_deterministic_and_parse():
    req = _reqs(('L2',))[0]
    state, questions, _ = R.render_laya(req)
    assert C.smoke_laya(state, questions) == C.smoke_laya(state, questions)
    ans, err = R.answer_with_laya(req, C.smoke_laya)
    assert err is None and ans is not None
    ans, err = R.answer_with_vlm(req, C.smoke_vlm)
    assert err is None and ans['answer'] in ('SELECT', 'KEEP', 'NOT_VISIBLE')
    assert C.baseline_ask('NEAREST_RED')(req)[0] == R.baseline_answer('NEAREST_RED', req)

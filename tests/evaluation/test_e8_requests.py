"""E8 request assembly (#780): synthetic fixtures only (no local dataset, no GT)."""
import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'evaluation'))

from amidst.evaluation import e8_requests as R  # noqa: E402
from amidst.evaluation.e7_decider_eval import build_laya_state_and_questions, parse_ao_json_response  # noqa: E402

SNAP = {'state': 'TRACKING', 'active_cam': 'CAM_A', 'est_xy': [0.0, 0.0], 'lost_ticks': 0, 'seen_ago_s': 0.0}
SCENE = {'camera_transitions': [{'from': 'CAM_A', 'to': 'CAM_B'}], 'overlaps': [{'cameras': ['CAM_A', 'CAM_C'], 'overlap_iou': 0.3}],
         'cameras': [{'camera_id': 'CAM_A', 'ground_footprint_polygon_xy_m': [[-1, -1], [1, -1], [1, 1], [-1, 1]]},
                     {'camera_id': 'CAM_B', 'ground_footprint_polygon_xy_m': [[3, -1], [5, -1], [5, 1], [3, 1]]}]}


def cand(cam, did, box, colors=('red',), xy=(0.0, 0.0), score=0.5):
    return {'camera_id': cam, 'detection_id': did, 'box': list(box), 'score': score, 'colors': list(colors),
            'ground_xy': list(xy) if xy is not None else None}


CANDS = [cand('CAM_A', 'D1', [0, 0, 10, 40], xy=(0.2, 0.0)),
         cand('CAM_B', 'D1', [0, 0, 10, 60], colors=('blue',), xy=(0.9, 0.0)),    # merges with A/D1 (0.7 m), taller -> representative
         cand('CAM_A', 'D2', [50, 0, 60, 40], colors=(), xy=(0.5, 0.0)),            # same camera as A/D1: never merges
         cand('CAM_C', 'D1', [0, 0, 10, 30], xy=(9.0, 0.0))]


def req(level, perm='p0', **kw):
    base = dict(case_id='E3-X1', dataset_group='g', tick=5, level=level, perm=perm, cands=CANDS, camera_ids=['CAM_A', 'CAM_B', 'CAM_C'],
                snapshot=SNAP, keep_display={'camera_id': 'CAM_A', 'detection_id': 'D1'}, scene=SCENE)
    base.update(kw)
    return R.build_request(**base)


def test_letters_and_perms():
    assert R.letters(3) == ['A', 'B', 'C'] and R.letters(28)[26:] == ['AA', 'AB']
    xs = list(range(10))
    assert R.permute(xs, 'p1', 'b') == xs[::-1]
    assert R.permute(xs, 'p2', 'b') == R.permute(xs, 'p2', 'b') != xs
    assert sorted(R.permute(xs, 'p2', 'b')) == xs


def test_merge_options():
    m = R.merge_options(CANDS)
    assert len(m) == 3
    assert m[0]['camera_id'] == 'CAM_B' and m[0]['members'] == [['CAM_A', 'D1'], ['CAM_B', 'D1']]
    assert m[0]['colors'] == ['blue', 'red']
    assert m[1]['members'] == [['CAM_A', 'D2']]


def test_levels_are_masked():
    r0c, r1, r2, r3 = (req(lv) for lv in ('L0c', 'L1', 'L2', 'L3'))
    assert 'colors' not in r0c['options'][0] and 'target_color' not in r0c and 'snapshot' not in r0c
    assert 'colors' in r1['options'][0] and 'distance_m' not in r1['options'][0] and 'snapshot' not in r1
    assert r2['options'][0]['distance_m'] == 0.9 and r2['snapshot'] == SNAP and 'relation' not in r2['options'][0]
    rel = {o['camera_id']: o['relation'] for o in r3['options']}
    assert rel == {'CAM_B': 'adj', 'CAM_A': 'same', 'CAM_C': 'ovl'}
    assert r3['scene_summary']['footprint_dist_m'] == {'CAM_A': 0.0, 'CAM_B': 3.0}
    for r in (r0c, r1, r2, r3):
        assert r['keep_display'] and r['identity'] == 'UNCONFIRMED'
        assert not ({'expected_answer', 'gt_regime', 'hit_gt'} & set(json.dumps(r).split('"')))


def test_render_laya_levels():
    s, q, om = R.render_laya(req('L3'))
    crit = q['pick']['criteria']
    assert list(crit)[-2:] == ['KEEP', 'NOT_VISIBLE'] and om['KEEP'] == {'answer': 'KEEP', 'option': None}
    assert crit['A'] == 'blue+red 0.9m B adj .50'
    assert list(s) == ['target', 'last', 'options', 'graph', 'now_s']
    s0, q0, _ = R.render_laya(req('L0c'))
    assert q0['pick']['criteria']['A'] == 'B .50' and q0['pick']['instructions'] == R.LAYA_QUESTION[0]
    assert list(s0) == ['options', 'now_s']
    with pytest.raises(ValueError):
        R.render_laya(req('L4'))


def e7_row():
    return {'variable_text': 'NOW t=1.0s.\nDETECTIONS ...', 'camera_ids': ['CAM_A'],
            'candidates': [{'box': [0, 0, 10, 40], 'camera_id': 'CAM_A', 'class_label': 'person', 'colors': ['red'], 'detection_id': 'D1',
                            'score': 0.5}]}


def test_l0_is_exact_e7():
    r = req('L0', e7_row=e7_row())
    assert set(r) >= {'e7', 'keep_display'} and 'options' not in r
    assert R.render_laya(r) == build_laya_state_and_questions(R.e7_decider_request(r))
    v = R.render_vlm(r)
    assert v['max_new_tokens'] == 256 and 'DETECTIONS ...' in v['text']
    parsed, err = parse_ao_json_response('{"answer":"UNCERTAIN"}', ('CAM_A',), tuple(e7_row()['candidates']), (320, 180))
    ans, _ = R.from_e7_parsed(parsed, err)
    assert R.display_of(ans, r)['via'] == 'KEEP'


def test_render_vlm_and_parse():
    r = req('L2')
    v = R.render_vlm(r)
    assert 'TRACKER_STATE=' in v['text'] and '- KEEP: keep current target A' in v['text'] and v['images'] == []
    ok, err = R.parse_e8_answer('```json\n{"answer":"SELECT","option":"B","confidence":"low"}\n```', r)
    assert err is None and R.display_of(ok, r) == {'kind': 'BOX', 'camera_id': 'CAM_A', 'detection_id': 'D2', 'via': 'SELECT'}
    assert R.parse_e8_answer('{"answer":"SELECT","option":"Z"}', r) == (None, 'UNKNOWN_OPTION')
    assert R.parse_e8_answer('nope', r) == (None, 'FORMAT_INVALID')
    nv, _ = R.parse_e8_answer('{"answer":"NOT_VISIBLE","option":"A"}', r)
    assert nv['option'] is None and R.display_of(nv, r)['kind'] == 'NONE'
    assert R.display_of(None, r)['kind'] == 'INVALID'
    r4 = req('L4', image_refs={'reference': 'img/ref.jpg', 'frames': {'CAM_B': 'img/b.jpg', 'CAM_A': 'img/a.jpg'}})
    assert [p for _, p in R.render_vlm(r4)['images']] == ['img/ref.jpg', 'img/a.jpg', 'img/b.jpg']


def test_laya_choice_answer():
    _, _, om = R.render_laya(req('L1'))
    assert R.laya_choice_answer({'choice': 'NOT_VISIBLE', 'confidence': 0.4}, om)[0] == {'answer': 'NOT_VISIBLE', 'option': None,
                                                                                       'confidence': 0.4}
    assert R.laya_choice_answer({'choice': 'Q'}, om) == (None, 'LAYA_INVALID_CHOICE')


def test_baselines():
    r = req('L2', perm='p1')     # reversed: C/D1 (red, 9 m) first
    keys = {o['key']: o for o in r['options']}
    assert keys[R.baseline_answer('FIRST', r)['option']]['camera_id'] == 'CAM_C'
    assert keys[R.baseline_answer('FIRST_RED', r)['option']]['camera_id'] == 'CAM_C'
    assert keys[R.baseline_answer('NEAREST_RED', r)['option']]['camera_id'] == 'CAM_B'
    assert R.baseline_answer('B1', r) == {'answer': 'KEEP', 'option': None}
    assert R.baseline_answer('RANDOM', r) == R.baseline_answer('RANDOM', r)
    empty = req('L2', cands=[])
    assert R.baseline_answer('FIRST_RED', empty)['answer'] == 'NOT_VISIBLE'


def test_no_duplicate_definitions():
    """Must-fix 1 (#780): E8 modules import existing functions; none redefines a name already defined in the reused modules."""
    reused = ['src/amidst/evaluation/e7_decider_eval.py', 'src/amidst/evaluation/e7_scoring_bridge.py', 'src/amidst/q1q5/agent_service.py',
              'src/amidst/live_mode/aopen/arms.py', 'scripts/evaluation/build_e7_colab_pack.py', 'scripts/evaluation/e3_f4_run.py',
              'src/amidst/evaluation/e6_verdict.py', 'scripts/evaluation/e3_f4_score.py', 'src/amidst/evaluation/e7_colab_runtime.py',
              'scripts/evaluation/generate_unified_analysis.py']
    e8 = sorted(p for p in ['src/amidst/evaluation/e8_requests.py', 'src/amidst/evaluation/e8_score.py',
                            'src/amidst/evaluation/e8_handoff.py', 'scripts/evaluation/build_e8_colab_pack.py',
                            'src/amidst/evaluation/e8_colab_run.py', 'scripts/evaluation/e8_score_run.py'] if (ROOT / p).exists())

    def defs(p):
        tree = ast.parse((ROOT / p).read_text())
        return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith('_') and n.name != 'main'}  # main = CLI entry point
    existing = set().union(*(defs(p) for p in reused if (ROOT / p).exists()))
    for p in e8:
        assert not (defs(p) & existing), (p, defs(p) & existing)


def test_inference_side_does_not_import_scoring():
    """Design §4.4 (D385/D417): inference-side E8 code never imports scoring modules."""
    banned = ('e3_scoring', 'e7_scoring_bridge', 'e6_verdict', 'e8_score', 'e3_f4_score')
    for p in ('src/amidst/evaluation/e8_requests.py', 'src/amidst/evaluation/e8_handoff.py', 'src/amidst/evaluation/e8_colab_run.py'):
        if (ROOT / p).exists():
            tree = ast.parse((ROOT / p).read_text())
            mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
            assert not [m for m in mods if any(b in m for b in banned)], p


def test_model_glue_and_truncation():
    r = req('L2')
    ans, err = R.answer_with_laya(r, lambda state, q: {'choice': 'B', 'confidence': 0.7})
    assert err is None and ans == {'answer': 'SELECT', 'option': 'B', 'confidence': 0.7}
    ans, err = R.answer_with_vlm(r, lambda system, text, images, n: '{"answer":"KEEP","option":null}')
    assert R.display_of(ans, r)['via'] == 'KEEP'
    r0 = req('L0', e7_row=e7_row())
    ans0, err0 = R.answer_with_laya(r0, lambda state, q: {'choice': 'SELECT:CAM_A|D1'})
    assert err0 is None and R.display_of(ans0, r0)['detection_id'] == 'D1'
    assert R.answer_with_laya(r0, lambda state, q: None)[0] is None
    s, q, _ = R.render_laya(r)
    t = R.laya_truncation(s, q, lambda text: text.split(), 'laya_text')
    assert t['n_options'] == 5 and not t['options_shrunk'] and t['approximate']
    big = R.laya_truncation(s, {'pick': {'instructions': 'x', 'criteria': {str(i): 'w ' * 60 for i in range(10)}}}, str.split, 'laya_text')
    assert big['options_shrunk'] and big['per_option_budget'] == 17

"""E8 Mac scorer (#780 / #785 review M1, O2, O3): a missing SELECTED group fails loudly; model groups are reported as sensitivity."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'evaluation'))

import e8_score_run as SR  # noqa: E402

SEL = {'model': 'qwen7b', 'level': 'L3'}


def test_missing_selected_lists_model_level_and_latency():
    groups = {'B1': {}, 'B1+qwen7b@L2': {}, 'B1+qwen7b@L2+MEASURED': {}, 'B1+laya_typed@L1': {}}
    miss = SR.missing_selected(SEL, groups)
    assert [(m['model'], m['level'], m['latency']) for m in miss] == [('qwen7b', 'L3', 'ZERO_LATENCY'), ('qwen7b', 'L3', 'MEASURED')]
    assert SR.missing_selected(SEL, {**groups, 'B1+qwen7b@L3': {}, 'B1+qwen7b@L3+MEASURED': {}}) == []
    assert SR.missing_selected(None, groups) == []
    hint = SR.rerun_hint(miss)
    assert 'RUN_MODELS = ["qwen7b"]' in hint and 'RUN_PART2 = True' in hint and '"level": "L3"' in hint
    assert SR.MODEL_GROUP.match('B1+qwen7b@L3') and not SR.MODEL_GROUP.match('B1+qwen7b@L3+MEASURED')
    assert not SR.MODEL_GROUP.match('B1+NEAREST_RED')


def test_part2_hypotheses_against_b1():
    segs, pts, classes, dps = [], [], {'B1': {}, 'B1+qwen7b@L3': {}}, []
    for i in range(16):
        cid = f'C{i}'
        for g, wp in (('B1', 1.0), ('B1+qwen7b@L3', 1.2)):
            segs.append({'group': g, 'family_id': f'F{i}', 'case_id': cid, 'follow_rate': 0.8, 'visible_ticks': 100,
                         'wrong_person_s': wp, 'blind_false_lock_s': 0.0})
            pts.append({'group': g, 'family_id': f'F{i}', 'full_track_correct': True})
            classes[g][cid] = {10: 'CORRECT'}
        dps.append({'case_id': cid, 'base_id': f'{cid}|t10', 'tick': 10})
    out = SR.part2_hypotheses('B1+qwen7b@L3', segs, pts, classes, dps, {d['base_id']: 'VISIBLE' for d in dps},
                              {f'C{i}': f'F{i}' for i in range(16)})
    assert out['H2']['M'] == 16 and out['H2']['p'] < 0.01 and out['S3']['M'] == 16 and out['S4']['diff'] == 0


def _results(status):
    res = {'conclusion': 'INCONCLUSIVE', 'regime_counts': {}, 'limitations': SR.LIMITATIONS, 'identity_status': 'UNCONFIRMED',
           'status': status,
           'part1': {'accuracy': {}, 'primary': {}, 'secondary': {}, 'selection': {'selected': SEL},
                     'position_bias': {'first_option_rate': {}, 'order_agreement': {}}},
           'part2': {'per_group': {}, 'selected_group': 'B1+qwen7b@L3', 'early_switch_s': {},
                     'sensitivity_model_groups': {'B1+qwen7b@L2': {'is_selected': False, 'metrics': {'follow_rate': .7, 'wrong_person_s': 9.0},
                                                                     'H2': {'p': 0.2}, 'S3': {'p': 0.5}, 'S4': {'median': 0.0}}}}}
    if status == 'SELECTED_GROUP_MISSING':
        miss = SR.missing_selected(SEL, {'B1': {}})
        res.update(conclusion='SELECTED_GROUP_MISSING', selected_group_missing=miss, rerun_hint=SR.rerun_hint(miss))
    return res


def test_main_exits_nonzero_and_flags_top_of_outputs(tmp_path, monkeypatch, capsys):
    for status, code in (('SELECTED_GROUP_MISSING', SR.EXIT_SELECTED_GROUP_MISSING), ('OK', 0)):
        monkeypatch.setattr(SR, 'score', lambda run, pack, mac, _s=status: _results(_s))
        out = tmp_path / status
        assert SR.main(['--run', str(tmp_path), '--pack', str(tmp_path), '--mac-index', str(tmp_path / 'i.json'), '--out', str(out)]) == code
        md = next(out.glob('E8_RESULTS_*.md')).read_text()
        doc = json.loads(next(out.glob('E8_RESULTS_*.json')).read_text())
        assert '## Part 2 sensitivity' in md and 'B1+qwen7b@L2' in md and '## Limitations' in md and 'selection bias' in md
        if code:
            assert md.splitlines()[2].startswith('> **SELECTED_GROUP_MISSING**') and 'qwen7b @ L3 (ZERO_LATENCY)' in md
            assert doc['conclusion'] == 'SELECTED_GROUP_MISSING' and doc['selected_group_missing'][0]['level'] == 'L3'
            assert 'SELECTED_GROUP_MISSING' in capsys.readouterr().err
        else:
            assert '> **SELECTED_GROUP_MISSING**' not in md and doc['status'] == 'OK'


def test_own_box_hits_keyed_per_model(monkeypatch):
    """#785: the Mac OWN_BOX judgement must not overwrite one model's answer with another's for the same request id."""
    monkeypatch.setattr(SR, 'judge_box', lambda box, body, size: {'primary': box[0] < 50})
    actors = {'E3-X1': {5: {'gt_visible': ['CAM_A'], 'gt_boxes': {'CAM_A': [0, 0, 10, 40]}}}}
    recs = [{'request_id': 'E3-X1|t5|L0|p0', 'base_id': 'E3-X1|t5', 'case_id': 'E3-X1', 'group': g, 'level': 'L0', 'perm': 'p0',
             'display': {'kind': 'NEEDS_MAC', 'camera_id': 'CAM_A', 'box_xyxy': box}}
            for g, box in (('qwen3b', [0, 0, 10, 40]), ('qwen7b', [100, 0, 110, 40]))]
    hits = SR.own_box_hits(recs, actors)
    assert hits == {('qwen3b', 'L0', 'p0', 'E3-X1|t5|L0|p0'): True, ('qwen7b', 'L0', 'p0', 'E3-X1|t5|L0|p0'): False}


def test_run_deviations_records_the_gpu_per_round(tmp_path):
    (tmp_path / 'r').mkdir()
    assert SR.run_deviations(tmp_path / 'r')[0] == ['RUN_NOTES_MISSING: GPU and notebook deviations unknown']
    r1 = {'run_label': 'r1', 'deviations': ['[r1] 4h rule: projected 4.6 h > 4.0 h on NVIDIA L4 for this round; qwen3b L0 runs p0 only'],
          'hardware': {'gpu_name': 'NVIDIA L4', 'gpu_vram_mb': 23034, 'actual_accelerated_dtype': 'bf16'}, 'qwen_l0_p0_only': {'qwen3b': True}}
    old = {'deviations': ['4h rule: old notebook wording'], 'hardware': {'gpu_name': 'NVIDIA A100-SXM4-40GB'}}
    (tmp_path / 'r' / 'RUN_NOTES.json').write_text(json.dumps(r1))
    (tmp_path / 'r' / 'RUN_NOTES_r1.json').write_text(json.dumps(r1))                       # same notes twice -> counted once
    (tmp_path / 'r' / 'e8-run-20261128').mkdir()
    (tmp_path / 'r' / 'e8-run-20261128' / 'RUN_NOTES.json').write_text(json.dumps(old))     # an old-notebook round, labelled by folder
    devs, info = SR.run_deviations(tmp_path / 'r')
    assert sorted(info) == ['e8-run-20261128', 'r1']
    assert info['r1']['gpu_name'] == 'NVIDIA L4' and info['r1']['qwen_l0_p0_only'] == {'qwen3b': True}
    assert sum('NVIDIA L4' in d and 'A100' in d and d.startswith('[r1] GPU') for d in devs) == 1
    assert '[e8-run-20261128] notebook: 4h rule: old notebook wording' in devs and devs.count(r1['deviations'][0]) == 1
    assert not any(d.startswith('[e8-run-20261128] GPU') for d in devs)                     # A100: no GPU deviation


def test_two_rounds_checkpoints_are_merged_without_double_counting(tmp_path):
    def cp(d, party, mode, res):
        (d / 'checkpoints').mkdir(parents=True, exist_ok=True)
        (d / 'checkpoints' / f'{party}__{mode}.json').write_text(json.dumps({'party_id': party, 'mode': mode, 'result': res}))
    rec = lambda g: {'group': g, 'level': 'L2', 'perm': 'p0', 'request_id': 'x|L2|p0'}  # noqa: E731
    r1, r2 = tmp_path / 'r1' / 'e8-run-20261128-r1', tmp_path / 'r2' / 'e8-run-20261128-r2'
    cp(r1, 'qwen3b', 'L2_p0', {'records': [rec('qwen3b')]})
    cp(r1, 'B1+FIRST_RED', 'part2_ZERO_LATENCY', {'group': 'B1+FIRST_RED', 'latency': 'ZERO_LATENCY', 'blogs': {}})
    for party, mode, res in (('qwen3b', 'L2_p0', {'records': [rec('qwen3b')]}),          # round 2 zip also carries round 1's checkpoints
                             ('qwen7b', 'L2_p0', {'records': [rec('qwen7b')]}),
                             ('B1+FIRST_RED', 'part2_ZERO_LATENCY', {'group': 'B1+FIRST_RED', 'latency': 'ZERO_LATENCY', 'blogs': {}})):
        cp(r2, party, mode, res)
    for runs in ([tmp_path / 'r1', tmp_path / 'r2'], [tmp_path / 'r2']):
        recs, part2 = SR.load_checkpoints(runs)
        assert sorted(r['group'] for r in recs) == ['qwen3b', 'qwen7b'] and list(part2) == ['B1+FIRST_RED|ZERO_LATENCY']
    miss = SR.missing_part1_cells(recs)
    assert {'model': 'qwen7b', 'level': 'L4', 'perm': 'p0'} in miss and {'model': 'qwen7b', 'level': 'L2', 'perm': 'p0'} not in miss

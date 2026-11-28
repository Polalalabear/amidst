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

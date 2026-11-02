"""評分端；與推論隔離。D105 reporting/admission with SYNTHETIC inputs only."""
from pathlib import Path
import os
import subprocess
import sys

import pytest

from test_q5_switch_eval_v2 import inputs, native_arguments, v1


ROOT = Path(__file__).resolve().parents[2]


def test_settled_bytes_match_recorded_decision_and_default_remains_pending():
    raw = (ROOT / 'configs/evaluation/q5_v2_decisions_u6_20261101.json').read_bytes()
    assert v1.sha(raw) == '0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e'
    selected = v1.load_json(raw)
    assert {k for k, value in selected.items() if value == 'PENDING_USER'} == {'U-D1', 'U-D2', 'U-D4'}
    assert set(v1.load_json((ROOT / 'configs/evaluation/q5_v2_decisions.json').read_bytes()).values()) == {'PENDING_USER'}


def mixed_inputs():
    data = inputs('standard')
    event = data['script']['events'][0]
    event.update(plan_anchor_us={'t_X': 0, 't_N_by_camera': {}}, decision_window_us=[0, 1600000],
                 entry_windows_us={'CAM_EXT_CLEAR': {'kind': 'OVERLAP', 'range_us': [0, 1600000]}})
    data['records'][0]['source_time_us'] = 600000
    data['records'][1].update(source_time_us=600000, decision_time_us=600000)
    data['response']['timeline'][0].update(camera_id='CAM_EXT_CLEAR', range_us=[600000, 12000000])
    data['script']['events'].append({'event_id': 'SYNTHETIC_STANDARD_AFTER_OVERLAP', 'event_class': 'STANDARD',
        'action': 'NO_SWITCH', 'plan_anchor_us': {'t_X': 2000000}, 'decision_window_us': [2000000, 3000000]})
    return data


def test_mixed_main_and_unselected_overlap_are_labeled_and_unscored_explicitly():
    module, frozen, raw, args = native_arguments(mixed_inputs(), controls=False)
    report = module.compare_script(frozen, raw, **args)
    first, second = report['events']
    assert first['reason'] == 'OVERLAP_AUTHORITY_UNSELECTED'
    assert first['overlap_label'] == 'OVERLAP_P_OV2_UNVERIFIED'
    assert first['pending_decisions'] == []
    assert second['match'] is True
    assert report['event_count'] == 2 and report['scored_event_count'] == 1
    assert report['has_unscored_events'] is True
    assert report['not_scored'] == {'OVERLAP_AUTHORITY_UNSELECTED': [first['event_id']]}
    assert report['event_match_ratio']['denominator'] == report['standard_event_match_ratio']['denominator'] == 1
    for key in ('overlap_ratio', 'partial_overlap_ratio'):
        assert report[key]['overlap_label'] == 'OVERLAP_P_OV2_UNVERIFIED'
    assert all('not_scored' in value for value in report['by_event_class'].values())


def test_settled_long_event_reports_only_relevant_pending_keys():
    module, frozen, raw, args = native_arguments(inputs())
    selected = (ROOT / 'configs/evaluation/q5_v2_decisions_u6_20261101.json').read_bytes()
    report = module.compare_script(frozen, raw, **{**args, 'decisions_raw': selected,
        'expected_decisions_config_sha256': v1.sha(selected)})
    row = report['events'][0]
    assert row['match'] is None and row['pending_decisions'] == ['U-D1']
    assert report['by_event_class']['LONG_GAP']['not_scored'] == 1


def test_standard_return_at_link_gap_is_rejected():
    from amidst.evaluation import q5_switch_eval_v2 as module
    selected = module.config(b'{}')
    with pytest.raises(module.EvaluationError, match='exceed L'):
        module.derive_plan_event({'action': 'RETURN_TO_ORIGIN', 'plan_anchor_us': {'t_X': 1000000, 't_N': 1600000}},
            0, [0, 10000000], (200000, 600000, 6000000, 1000000, 6), selected)


def test_return_prewindow_truncation_cannot_hide_opening_action():
    from amidst.evaluation import q5_switch_eval_v2 as module
    with pytest.raises(module.EvaluationError, match='prewindow'):
        module.derive_plan_event({'action': 'RETURN_TO_ORIGIN', 'plan_anchor_us': {'t_X': 1000000, 't_N': 2600000}},
            1800000, [0, 10000000], (200000, 600000, 6000000, 1000000, 6), module.config(b'{}'))


def test_cli_uses_settled_default_and_rejects_unpinned_override(tmp_path):
    fixture = ROOT / 'tests/fixtures/q5_v2/SYNTHETIC'
    paths = {name: fixture / f'standard.{name}.SYNTHETIC.{suffix}'
             for name, suffix in [('response', 'json'), ('decisions', 'jsonl'), ('script', 'json')]}
    paths.update(parameters=fixture / 'parameter_set.SYNTHETIC.json', plan=fixture / 'plan.SYNTHETIC.json')
    command = [sys.executable, str(ROOT / 'scripts/score_q5_v2.py')]
    for name, path in paths.items():
        command += ['--' + name, str(path), '--' + name + '-sha256', v1.sha(path.read_bytes())]
    output = tmp_path / 'report.json'
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run(command + ['--output', str(output)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert v1.load_json(output.read_bytes())['decisions_config_sha256'] == '0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e'
    target = tmp_path / 'must-not-exist.json'
    result = subprocess.run(command + ['--decisions-config', str(ROOT / 'configs/evaluation/q5_v2_decisions.json'),
        '--output', str(target)], env=env, capture_output=True, text=True)
    assert result.returncode == 2 and not target.exists()

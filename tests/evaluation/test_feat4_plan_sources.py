"""評分端；與推論隔離。D105 plan-only arithmetic; no real observations."""
import json
from pathlib import Path

from amidst.evaluation import q5_switch_eval_v2 as scorer

ROOT = Path(__file__).resolve().parents[2]


def test_u7_source_stays_on_original_pr_and_all_five_plans_pin_it():
    assert not (ROOT / 'docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md').exists()
    plans = [json.loads((ROOT / f'configs/evaluation/l2_{key}_script_plan_v2.json').read_bytes())
             for key in ('rr', 'rr_b', 'lg', 'pe1', 'ov1')]
    for plan in plans:
        assert '#261 b5302a0ad9a1895d728946d824854b6001b6b66a' in plan['scenario_card']
        assert '02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b' in plan['scenario_card']
        assert plan['status'] == 'UNFROZEN' and plan['approval_ref'] is None
        assert plan['run_id'] == plan['clock_id'] == 'UNKNOWN'
    first, second = plans[:2]
    assert first['query_range_us'] == [0, 14000000]
    assert second['query_range_us'] == [14000000, 28000000]
    assert first['source_duration_us'] == second['source_duration_us'] == 30000000
    assert 'observation_id MISSING' in second['planned_times_note']


def test_rr_two_request_budgets_use_absolute_source_time_without_session_reset():
    selected = scorer.config((ROOT / 'configs/evaluation/q5_v2_decisions_u6_20261101.json').read_bytes())
    params = (200000, 600000, 6000000, 1000000, 6)
    counts = []
    for key in ('rr', 'rr_b'):
        plan = json.loads((ROOT / f'configs/evaluation/l2_{key}_script_plan_v2.json').read_bytes())
        previous, searches = plan['query_range_us'][0], 0
        for row in plan['events']:
            event = {'action': row['action'], 'plan_anchor_us': {'t_X': row['t_x_us'], 't_N': row['t_n_us']}}
            derived, count, _ = scorer.derive_plan_event(event, previous, plan['query_range_us'], params, selected)
            assert derived['event_class'] == row['event_class']
            previous = derived['decision_window_us'][1]; searches += count
        counts.append(searches)
    assert counts == [2, 3] and all(count <= 4 for count in counts)

"""Translate CQ-33-T's test inputs to the real adapter; never read golden values."""
from pathlib import Path

from amidst.evaluation import q5_switch_eval as v1


def translate(inputs):
    original = inputs['plan']; events = []
    for source in original['events']:
        event = {k: v for k, v in source.items() if k not in {'t_X_us', 't_N_us', 't_prev_end_us'}}
        event['t_x_us'] = source.get('t_X_us')
        if 't_N_us' in source:
            event['t_n_us'] = source['t_N_us']
        events.append(event)
    plan = {'schema_version': 'q5-script-plan.v' + str(original['version_under_test']),
            'status': 'UNFROZEN', 'plan_id': inputs['case_id'],
            'run_id': original['run_id'], 'clock_id': original['clock_id'],
            'geometry_status': original['geometry_status'], 'query_range_us': original['session_query_range_us'],
            'source_duration_us': original['session_query_range_us'][1], 'events': events}
    names = {'RECOMPUTE': 'RECOMPUTE_AND_REJECT', 'REJECT_EARLY_VISIBLE': 'REJECT_EARLY_BLIND',
             'CLAMPED_START': 'CLAMPED_WINDOW_START', 'SYNTHETIC_PLAN_CHECK_ONLY': 'PLAN_CHECK_ONLY'}
    config = {k: names.get(v, v) for k, v in inputs['test_only_selections'].items() if k != 'human_approval_verified'}
    return v1.canonical(plan), v1.canonical(inputs['parameters']), v1.canonical(config)


def exercise_case(*, inputs, implementation):
    plan, params, selected = translate(inputs)
    result = {'implementation_file_sha256': v1.sha(Path(implementation.__file__).read_bytes()), 'human_approval_verified': False}
    try:
        script, searches = implementation.generate_script(plan, expected_plan_sha256=v1.sha(plan),
            parameters_raw=params, expected_parameters_sha256=v1.sha(params), decisions_raw=selected,
            expected_decisions_sha256=v1.sha(selected), plan_path='SYNTHETIC_TEST_ONLY',
            synthetic_controls=implementation.SyntheticPlanInputs())
        return {**result, 'rejected': False, 'native_script': script, 'planned_searching': searches}
    except implementation.PlanError as error:
        return {**result, 'rejected': True, 'native_script': None, 'error_category': error.category}

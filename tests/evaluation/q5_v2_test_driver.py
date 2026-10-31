"""Test-only binding to the real v2 scorer; no golden values or scoring logic."""
from pathlib import Path
from amidst.evaluation import q5_switch_eval as v1


def exercise_case(name, *, inputs, implementation):
    common = {'implementation_invoked': False, 'implementation_file_sha256': v1.sha(Path(implementation.__file__).read_bytes()),
              'human_approval_verified': False}
    if name == 'dispatch_v1':
        common['implementation_invoked'] = True
        try:
            report = implementation.compare_script(inputs['frozen'], inputs['script_raw'], expected_script_sha256=inputs['expected_script_sha256'])
            return {**common, 'native_report': report}
        except v1.EvaluationError as error:
            return {**common, 'rejected': True, 'native_report': None, 'error_type': type(error).__name__, 'error_message': str(error)}
    raw, pins = inputs['raw'], inputs['pins']
    selections = {key: value.removeprefix('TEST_ONLY:') for key, value in inputs['decisions'].items()}
    selected_raw = v1.canonical(selections)
    plan = v1.canonical(inputs['plan']) + b'\n'
    context = inputs.get('binding_context', {})
    controls = implementation.SyntheticControls(tuple(context.get('pair', ())), context.get('exit_strip_present', False))
    try:
        common['implementation_invoked'] = True
        if name == 'freeze_file_order':
            paths = dict(inputs['paths'])
            # Plan is an explicit test input, never a discovered private path.
            plan_path = paths['script'].parent / 'SYNTHETIC_plan.json'
            plan_path.write_bytes(plan); paths['plan'] = plan_path
            report = implementation.score_files(paths, {**pins, 'plan': v1.sha(plan)}, decisions_raw=selected_raw, synthetic_controls=controls)
        else:
            frozen = implementation.freeze_output(raw['response'], raw['decisions'], expected_response_sha256=pins['response'], expected_decisions_sha256=pins['decisions'])
            report = implementation.compare_script(frozen, raw['script'], expected_script_sha256=pins['script'],
                parameters_raw=raw['parameters'], expected_parameters_sha256=pins['parameters'],
                plan_raw=plan, expected_plan_sha256=v1.sha(plan), decisions_raw=selected_raw,
                expected_decisions_config_sha256=v1.sha(selected_raw), synthetic_controls=controls)
        observations = {'events': report['events'], 'status': report['status'], 'main_ratio': report['event_match_ratio'],
            'standard_event_match_ratio': report.get('standard_event_match_ratio'), 'overlap_ratio': report['overlap_ratio'],
            'partial_ratio': report['partial_ratio'], 'cutoff_us': report['cutoff_us']}
        if name == 'searching_count':
            observations['searching_count'] = implementation.searching_count(inputs['records'], inputs['searching_window_us'])
        return {**common, 'native_report': report, 'observations': observations}
    except implementation.EvaluationError as error:
        return {**common, 'rejected': True, 'native_report': None, 'observations': {'error_category': error.category}}

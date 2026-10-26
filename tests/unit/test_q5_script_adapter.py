"""Plan -> script adapter: reference windows from the r004 A4/B4 scenario card plus a scorer smoke test."""
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from amidst.evaluation.q5_script_adapter import (
    SCOPE_STATEMENT,
    PlanError,
    derive_windows,
    dumps,
    generate_script,
    load_plan,
    precheck,
)
from amidst.evaluation.q5_switch_eval import canonical, compare_script, digest, freeze_output, sha

ROOT = Path(__file__).resolve().parents[2]
S = 1_000_000


def plan_of(name):
    return load_plan((ROOT / 'configs/evaluation' / ('r004_%s_script_plan_v1.json' % name)).read_bytes())


def windows(plan):
    derived, errors = derive_windows(plan)
    assert not errors
    return {e['event_id']: e for e in derived}


def sec(pair):
    return [x / S for x in pair]


def test_a4_reference_windows():
    w = windows(plan_of('a4_1'))
    assert sec(w['A4-c1']['decision_window_us']) == [5.0, 12.0]
    assert sec(w['A4-c1']['entry_window_us']) == [10.4, 12.0]
    assert sec(w['A4-n1']['decision_window_us']) == [12.0, 22.0]   # yields to A4-e's untruncated start 23.0
    assert sec(w['A4-e']['decision_window_us']) == [23.0, 30.0]
    assert sec(w['A4-e']['entry_window_us']) == [28.4, 30.0]
    assert sec(w['A4-c2']['decision_window_us']) == [33.0, 40.0]
    assert sec(w['A4-c2']['entry_window_us']) == [38.4, 40.0]


def test_b4_reference_windows():
    w = windows(plan_of('b4_1'))
    assert sec(w['B4-n1']['decision_window_us']) == [0.0, 8.0]     # starts at query start, yields to B4-b start 8.0
    assert sec(w['B4-b']['decision_window_us']) == [8.0, 15.0]
    assert sec(w['B4-b']['entry_window_us']) == [13.4, 15.0]
    assert sec(w['B4-d']['decision_window_us']) == [18.0, 25.0]
    assert sec(w['B4-e']['decision_window_us']) == [26.0, 33.0]
    assert sec(w['B4-e']['entry_window_us']) == [31.4, 33.0]


@pytest.mark.parametrize('name', ['a4_1', 'b4_1'])
def test_card_plans_pass_precheck(name):
    report = precheck(plan_of(name))
    assert report['ok'] and not report['errors'] and report['planned_searching'] == 3
    assert report['scope_statement'] == SCOPE_STATEMENT
    assert all(type(x) is int for e in report['events'] for k in ('decision_window_us', 'entry_window_us') for x in e.get(k, []))


def test_truncation_by_previous_window():
    plan = plan_of('a4_1')
    plan['events'][1]['t_x_us'] = 13 * S   # NO_SWITCH yields: end = min(19, 23)
    plan['events'][0]['t_n_us'] = 11 * S
    w = windows(plan)
    assert sec(w['A4-n1']['decision_window_us']) == [12.0, 19.0]


def mutated(name, index, **changes):
    plan = deepcopy(plan_of(name))
    plan['events'][index].update(changes)
    return plan


@pytest.mark.parametrize('plan,needle', [
    (mutated('a4_1', 0, t_x_us=5_700_000), 'SWITCH gap'),          # 5.3 s > 5.2 s
    (mutated('a4_1', 0, t_x_us=10_500_000), 'lower bound'),        # 0.5 s
    (mutated('a4_1', 3, t_x_us=33_000_000), 'S1 dwell'),
    (mutated('a4_1', 3, t_x_us=31_500_000, t_n_us=34_500_000), 'S2'),
    (mutated('a4_1', 1, t_x_us=12_000_000), 'S4'),
    (mutated('b4_1', 2, t_n_us=21_500_000, t_x_us=18_500_000), 'S2'),
    (mutated('b4_1', 0, t_x_us=1_000_000), 'S6'),
])
def test_precheck_rejects(plan, needle):
    report = precheck(plan)
    assert not report['ok'] and any(needle in e for e in report['errors'])
    with pytest.raises(PlanError) as exc:
        generate_script(plan, formal=False)
    assert needle in str(exc.value)


def test_return_loss_limit_and_search_cap():
    plan = plan_of('a4_1')
    plan['events'][2].update(action='RETURN_TO_ORIGIN', allowed_camera_ids=[], t_n_us=27_800_000)   # loss 1.8 s
    assert any('RETURN loss' in e for e in precheck(plan)['errors'])
    plan['events'][2]['t_n_us'] = 27_600_000   # 1.6 s passes the loss rule
    assert not any('RETURN loss' in e for e in precheck(plan)['errors'])
    plan = plan_of('a4_1')
    extra = deepcopy(plan['events'][3])
    extra.update(event_id='A4-x', t_x_us=44 * S, t_n_us=47 * S)
    plan['events'].append(extra)
    assert any('planned SEARCHING 4' in e for e in precheck(plan)['errors'])


def test_ns_last_and_overlap_rejected():
    plan = plan_of('a4_1')
    plan['events'] = plan['events'][:2]
    assert any('S5' in e for e in precheck(plan)['errors'])
    plan = plan_of('a4_1')
    plan['events'][2]['t_n_us'] = 29 * S
    plan['events'][3].update(t_n_us=35 * S, t_x_us=32 * S)
    errors = precheck(plan)['errors']
    assert any('S2' in e for e in errors)


def test_formal_refuses_placeholders_and_unfrozen():
    plan = plan_of('b4_1')
    assert plan['run_id'] == plan['clock_id'] == 'UNKNOWN' and plan['status'] == 'PLANNED'
    with pytest.raises(PlanError) as exc:
        generate_script(plan, formal=True)
    assert 'run_id' in str(exc.value) and 'clock_id' in str(exc.value) and 'FROZEN' in str(exc.value)
    plan.update(run_id='RUN', clock_id='CLK')
    with pytest.raises(PlanError):
        generate_script(plan, formal=True)
    plan['status'] = 'FROZEN'
    script = generate_script(plan, formal=True)
    assert script['generator_mode'] == 'FORMAL' and script['status'] == 'PROPOSED'
    plan['approval_ref'] = 'https://example.invalid/approval'
    assert generate_script(plan, formal=True)['status'] == 'APPROVED'


def test_generated_script_shape():
    plan = plan_of('a4_1')
    plan.update(run_id='RUN', clock_id='CLK')
    script = generate_script(plan, formal=False)
    assert script['schema_version'] == 'q5-evaluation-script.v1' and script['generator_mode'] == 'PREVIEW'
    assert SCOPE_STATEMENT in script['scope_statement']
    by_id = {e['event_id']: e for e in script['events']}
    assert by_id['A4-n1'].keys() == {'event_id', 'action', 'decision_window_us'}
    assert by_id['A4-e']['allowed_camera_ids'] == ['CAM_EXT_CAR', 'CAM_EXT_CLEAR']
    assert dumps(script) == dumps(generate_script(plan, formal=False))


def test_scorer_smoke_reads_generated_script():
    plan = plan_of('b4_1')
    plan.update(run_id='RUN', clock_id='CLK')
    script_raw = dumps(generate_script(plan, formal=False)).encode()
    # synthetic decisions: one SWITCH inside each SWITCH window, entry inside entry window
    picks = [('B4-b', 'CAM_BRANCH', 11_800_000, 14_100_000), ('B4-d', 'CAM_W2', 21_800_000, 24_100_000),
             ('B4-e', 'CAM_R101_IN', 30_800_000, 32_100_000)]
    rows, timeline = [], []
    for i, (eid, cam, decision, entry) in enumerate(picks):
        row = {'schema_version': 'q-demo.decision-record.v1', 'session_id': 'SYN', 'decision_id': 'D%d' % i, 'step_index': i,
               'source_time_us': decision, 'decision_time_us': decision, 'executed_action': 'SWITCH',
               'executed_candidate_ref': 'C%d' % i, 'entry_observation_id': 'O%d' % i, 'accepted': True, 'decided_by': 'RULE_ONLY'}
        row['content_sha256'] = digest(row, 'content_sha256')
        rows.append(row)
        timeline.append({'segment_id': 'S%d' % i, 'kind': 'ON_CAMERA', 'range_us': [entry, entry + 1_000_000], 'entered_by': 'SWITCH',
                         'decision_id': 'D%d' % i, 'camera_id': cam, 'observation_ids': ['O%d' % i]})
    last = {'schema_version': 'q-demo.decision-record.v1', 'session_id': 'SYN', 'decision_id': 'DEND', 'step_index': 3,
            'source_time_us': 34_000_000, 'decision_time_us': None, 'executed_action': None}
    last['content_sha256'] = digest(last, 'content_sha256')
    rows.append(last)
    raw = b''.join(canonical(r) + b'\n' for r in rows)
    response = {'schema_version': 'q-demo.q2-response.v1', 'session_id': 'SYN', 'status': 'COMPLETE',
                'resolved_scope': {'run_ids': ['RUN'], 'clock_ids': ['CLK'],
                                   'resolved_source_ranges_us': [{'run_id': 'RUN', 'range_us': plan['query_range_us']}]},
                'decisions_sha256': sha(raw), 'agent_used': False, 'fallback_used': False, 'timeline': timeline}
    response['output_sha256'] = digest(response, 'output_sha256')
    response_raw = canonical(response)
    frozen = freeze_output(response_raw, raw, expected_response_sha256=sha(response_raw), expected_decisions_sha256=sha(raw))
    report = compare_script(frozen, script_raw, expected_script_sha256=sha(script_raw))
    assert report['event_count'] == 4 and report['matched_events'] == 4
    assert report['uncovered_executed_count'] == 0
    assert report['script_status'] == 'PROPOSED'


def test_cli_rejects_formal_without_output(tmp_path):
    spec = importlib.util.spec_from_file_location('gen_q5_script', ROOT / 'scripts/gen_q5_script.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan_path = ROOT / 'configs/evaluation/r004_a4_1_script_plan_v1.json'
    out = tmp_path / 'script.json'
    with pytest.raises(SystemExit) as exc:
        module.main(['--plan', str(plan_path), '--output', str(out), '--formal'])
    assert exc.value.code == 2 and not out.exists()
    report = tmp_path / 'report.json'
    assert module.main(['--plan', str(plan_path), '--output', str(out), '--report', str(report)]) == 0
    assert out.exists() and report.exists()

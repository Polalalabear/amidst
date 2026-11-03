"""Plan -> script adapter: reference windows from the r004 A4/B4 scenario card plus a scorer smoke test."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from amidst.evaluation.q5_script_adapter import (
    D89_APPROVAL_URL,
    SCOPE_STATEMENT,
    PlanError,
    derive_windows,
    dumps,
    generate_script,
    is_unknown,
    load_plan,
    plan_content_sha256,
    precheck,
)
from amidst.evaluation.q5_switch_eval import canonical, compare_script, digest, freeze_output, sha

ROOT = Path(__file__).resolve().parents[2]
S = 1_000_000
D92_URL = 'https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633'


def current_plan(name):
    return load_plan((ROOT / 'configs/evaluation' / ('r004_%s_script_plan_v1.json' % name)).read_bytes())


def plan_of(name):
    """D92 reference fixture, retaining the old conditional event for window regressions."""
    plan = current_plan(name)
    pending = plan['unscored_events'].pop()
    pending['scoring_status'] = 'SCORED'
    plan['events'].append(pending)
    return plan


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
    assert 'A4-e' not in w   # D92: unscored, removed from the plan
    assert sec(w['A4-n1']['decision_window_us']) == [12.0, 22.0]   # t_X + W = 22.0 < A4-c2's untruncated start 33.0
    assert sec(w['A4-c2']['decision_window_us']) == [33.0, 40.0]
    assert sec(w['A4-c2']['entry_window_us']) == [38.4, 40.0]


def test_b4_reference_windows():
    w = windows(plan_of('b4_1'))
    assert sec(w['B4-n1']['decision_window_us']) == [0.0, 8.0]     # starts at query start, yields to B4-b start 8.0
    assert sec(w['B4-b']['decision_window_us']) == [8.0, 15.0]
    assert sec(w['B4-b']['entry_window_us']) == [13.4, 15.0]
    assert 'B4-d' not in w   # D92: unscored, removed from the plan
    assert sec(w['B4-e']['decision_window_us']) == [26.0, 33.0]
    assert sec(w['B4-e']['entry_window_us']) == [31.4, 33.0]


@pytest.mark.parametrize('name', ['a4_1', 'b4_1'])
def test_card_plans_pass_precheck(name):
    report = precheck(plan_of(name))
    assert report['ok'] and not report['errors'] and report['planned_searching'] == 3
    assert report['scored_planned_searching'] == 2 and report['total_planned_searching'] == 3
    assert report['scope_statement'] == SCOPE_STATEMENT
    assert all(type(x) is int for e in report['events'] for k in ('decision_window_us', 'entry_window_us') for x in e.get(k, []))


def test_truncation_by_previous_window():
    plan = plan_of('a4_1')
    plan['events'][1]['t_x_us'] = 13 * S   # NO_SWITCH end = min(t_X + W = 19, next untruncated start 33)
    plan['events'][0]['t_n_us'] = 11 * S
    w = windows(plan)
    assert sec(w['A4-n1']['decision_window_us']) == [12.0, 19.0]


def mutated(name, index, **changes):
    plan = deepcopy(plan_of(name))
    plan['events'][index].update(changes)
    return plan


def without_ns(name, index, **changes):
    """Drop the NO_SWITCH (event 1) so the two SWITCH events are adjacent, then mutate."""
    plan = deepcopy(plan_of(name))
    del plan['events'][1]
    plan['events'][index].update(changes)
    return plan


@pytest.mark.parametrize('plan,needle', [
    (mutated('a4_1', 0, t_x_us=5_700_000), 'SWITCH gap'),          # 5.3 s > 5.2 s
    (mutated('a4_1', 0, t_x_us=10_500_000), 'lower bound'),        # 0.5 s
    (without_ns('a4_1', 1, t_x_us=14_000_000, t_n_us=17_000_000), 'S1 dwell'),
    (without_ns('a4_1', 1, t_x_us=15_000_000, t_n_us=18_000_000), 'S2'),
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
    plan['events'][2].update(action='RETURN_TO_ORIGIN', allowed_camera_ids=[], t_n_us=37_800_000)   # t_X 36.0 s: loss 1.8 s
    assert any('RETURN loss' in e for e in precheck(plan)['errors'])
    plan['events'][2]['t_n_us'] = 37_600_000   # 1.6 s passes the loss rule
    assert not any('RETURN loss' in e for e in precheck(plan)['errors'])
    plan = plan_of('a4_1')
    for name, t_x, t_n in (('A4-x', 44, 47), ('A4-y', 45, 48)):
        extra = deepcopy(plan['events'][2])
        extra.update(event_id=name, t_x_us=t_x * S, t_n_us=t_n * S)
        plan['events'].append(extra)
    assert any('planned SEARCHING 5' in e for e in precheck(plan)['errors'])


def test_ns_last_and_overlap_rejected():
    plan = plan_of('a4_1')
    plan['events'] = plan['events'][:2]
    plan['unscored_events'] = []
    assert any('S5' in e for e in precheck(plan)['errors'])
    plan = without_ns('a4_1', 1, t_n_us=18 * S, t_x_us=15 * S)
    errors = precheck(plan)['errors']
    assert any('S2' in e for e in errors)


def test_formal_refuses_placeholders_and_unfrozen():
    plan = plan_of('b4_1')
    assert plan['status'] == 'PLANNED'
    plan.update(run_id='UNKNOWN', clock_id='UNKNOWN')
    with pytest.raises(PlanError) as exc:
        generate_script(plan, formal=True)
    assert 'run_id' in str(exc.value) and 'clock_id' in str(exc.value) and 'FROZEN' in str(exc.value)
    plan.update(run_id='RUN', clock_id='CLK')
    with pytest.raises(PlanError):
        generate_script(plan, formal=True)
    plan['status'] = 'FROZEN'
    with pytest.raises(PlanError) as exc:
        generate_script(plan, formal=True)
    assert 'approval_ref' in str(exc.value)
    plan['approval_ref'] = good_ref(plan)
    script = generate_script(plan, formal=True)
    assert script['generator_mode'] == 'FORMAL' and script['status'] == 'APPROVED' and script['approval_ref'] == plan['approval_ref']


def good_ref(plan):
    return '%s sha256:%s' % (D89_APPROVAL_URL, plan_content_sha256(plan))


def frozen(name='b4_1'):
    plan = plan_of(name)
    plan.update(run_id='RUN', clock_id='CLK', status='FROZEN')
    return plan


def test_shipped_plans_carry_d89_d92_ref_and_formal_still_refused():
    expected = {'a4_1': ('ctrl-lcorr-s1-a4-5fps-v1-r004', 'clock:r004:a4:declared-demo:v1', 'A4-e'),
                'b4_1': ('ctrl-lcorr-s1-b4-5fps-v1-r004', 'clock:r004:b4:declared-demo:v1', 'B4-d')}
    for name, (run_id, clock_id, dropped) in expected.items():
        plan = current_plan(name)
        assert (plan['run_id'], plan['clock_id']) == (run_id, clock_id)   # #238 head f159ac8
        assert D89_APPROVAL_URL in plan['approval_ref'] and D92_URL in plan['approval_ref']
        assert plan['approval_ref'].endswith('sha256:' + plan_content_sha256(plan))
        assert dropped not in [e['event_id'] for e in plan['events']]
        assert plan['unscored_events'][0]['event_id'] == dropped and plan['unscored_events'][0]['ref'] == D92_URL
        with pytest.raises(PlanError):
            generate_script(plan, formal=True)
        assert generate_script(plan, formal=False)['approval_ref'] is None


@pytest.mark.parametrize('ref', [1, True, ['x'], {}, None, '', '   ', 'https://example.invalid/approval',
                                 D89_APPROVAL_URL, D89_APPROVAL_URL + ' sha256:' + '0' * 64])
def test_formal_rejects_bad_approval_ref(ref):
    plan = frozen()
    plan['approval_ref'] = ref
    with pytest.raises(PlanError) as exc:
        generate_script(plan, formal=True)
    assert 'approval_ref' in str(exc.value)


def test_formal_rejects_link_only_or_hash_only():
    plan = frozen()
    digest_hex = plan_content_sha256(plan)
    plan['approval_ref'] = digest_hex
    assert 'D89 link' in str(pytest.raises(PlanError, generate_script, plan, formal=True).value)
    plan['approval_ref'] = D89_APPROVAL_URL + ' sha256:' + digest_hex[:-1]
    assert 'SHA-256' in str(pytest.raises(PlanError, generate_script, plan, formal=True).value)


def test_hash_excludes_approval_ref_but_covers_content():
    plan = frozen()
    base = plan_content_sha256(plan)
    plan['approval_ref'] = 'anything'
    assert plan_content_sha256(plan) == base
    plan['approval_ref'] = good_ref(plan)
    assert generate_script(plan, formal=True)['status'] == 'APPROVED'
    plan['events'][0]['note'] = 'edited after approval'   # approval no longer matches the content
    with pytest.raises(PlanError) as exc:
        generate_script(plan, formal=True)
    assert 'SHA-256' in str(exc.value)


@pytest.mark.parametrize('value', ['unknown', 'Unknown', ' UNKNOWN ', '\tunknown\n', '', '   ', None])
def test_unknown_is_case_and_space_insensitive(value):
    assert is_unknown(value)
    for key in ('run_id', 'clock_id'):
        plan = frozen()
        plan[key] = value
        plan['approval_ref'] = good_ref(plan)
        with pytest.raises(PlanError) as exc:
            generate_script(plan, formal=True)
        assert key in str(exc.value)


def test_known_values_are_not_unknown():
    assert not is_unknown('RUN') and not is_unknown('unknown-1')


@pytest.mark.parametrize('plan', [[], [1], 'x', 3, None])
def test_non_dict_plan_is_rejected(plan):
    assert precheck(plan)['ok'] is False
    with pytest.raises(PlanError):
        generate_script(plan, formal=False)
    with pytest.raises(PlanError):
        generate_script(plan, formal=True)


@pytest.mark.parametrize('raw', [b'[]', b'[1,2]', b'"x"', b'3', b'null'])
def test_load_plan_rejects_non_object(raw):
    with pytest.raises(PlanError):
        load_plan(raw)


@pytest.mark.parametrize('key,value', [('run_id', None), ('clock_id', None), ('run_id', 7), ('clock_id', ['C'])])
@pytest.mark.parametrize('formal', [False, True])
def test_missing_or_non_string_ids_are_rejected(key, value, formal):
    plan = frozen()
    if value is None:
        del plan[key]
    else:
        plan[key] = value
    with pytest.raises(PlanError) as exc:
        generate_script(plan, formal=formal)
    assert key in str(exc.value)


def test_cli_prints_rejected_not_traceback(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location('gen_q5_script', ROOT / 'scripts/gen_q5_script.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = {'list.json': '[]', 'norun.json': json.dumps({k: v for k, v in plan_of('a4_1').items() if k != 'run_id'})}
    for name, text in cases.items():
        path = tmp_path / name
        path.write_text(text)
        with pytest.raises(SystemExit) as exc:
            module.main(['--plan', str(path), '--output', str(tmp_path / ('out_' + name))])
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert err.startswith('REJECTED:') and 'Traceback' not in err


def test_generated_script_shape():
    plan = plan_of('a4_1')
    plan.update(run_id='RUN', clock_id='CLK')
    script = generate_script(plan, formal=False)
    assert script['schema_version'] == 'q5-evaluation-script.v1' and script['generator_mode'] == 'PREVIEW'
    assert SCOPE_STATEMENT in script['scope_statement']
    by_id = {e['event_id']: e for e in script['events']}
    assert by_id['A4-n1'].keys() == {'event_id', 'action', 'decision_window_us'}
    assert 'A4-e' not in by_id and by_id['A4-c1']['allowed_camera_ids'] == ['CAM_W1']
    assert dumps(script) == dumps(generate_script(plan, formal=False))


def test_scorer_smoke_reads_generated_script():
    plan = plan_of('b4_1')
    plan.update(run_id='RUN', clock_id='CLK')
    script_raw = dumps(generate_script(plan, formal=False)).encode()
    # synthetic decisions: one SWITCH inside each SWITCH window, entry inside entry window
    picks = [('B4-b', 'CAM_BRANCH', 11_800_000, 14_100_000), ('B4-e', 'CAM_R101_IN', 30_800_000, 32_100_000)]
    rows, timeline = [], []
    for i, (eid, cam, decision, entry) in enumerate(picks):
        row = {'schema_version': 'q-demo.decision-record.v1', 'session_id': 'SYN', 'decision_id': 'D%d' % i, 'step_index': i,
               'source_time_us': decision, 'decision_time_us': decision, 'executed_action': 'SWITCH',
               'executed_candidate_ref': 'C%d' % i, 'entry_observation_id': 'O%d' % i, 'accepted': True, 'decided_by': 'RULE_ONLY'}
        row['content_sha256'] = digest(row, 'content_sha256')
        rows.append(row)
        timeline.append({'segment_id': 'S%d' % i, 'kind': 'ON_CAMERA', 'range_us': [entry, entry + 1_000_000], 'entered_by': 'SWITCH',
                         'decision_id': 'D%d' % i, 'camera_id': cam, 'observation_ids': ['O%d' % i]})
    last = {'schema_version': 'q-demo.decision-record.v1', 'session_id': 'SYN', 'decision_id': 'DEND', 'step_index': 2,
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
    assert report['event_count'] == 3 and report['matched_events'] == 3
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


@pytest.mark.parametrize('version', [None, '', 'q5-script-plan.v0', 'q5-script-plan.v2', 1])
def test_plan_schema_fails_closed(version):
    plan = current_plan('b4_1')
    plan['schema_version'] = version
    assert precheck(plan)['ok'] is False
    assert derive_windows(plan)[0] is None
    with pytest.raises(PlanError, match='schema_version'):
        generate_script(plan, formal=False)


@pytest.mark.parametrize('name,pending,scored', [
    ('a4_1', 'A4-c2', {'A4-c1', 'A4-n1'}),
    ('b4_1', 'B4-e', {'B4-b', 'B4-n1'}),
])
def test_d96_pending_events_are_excluded_without_lowering_search_budget(name, pending, scored):
    plan = current_plan(name)
    report = precheck(plan)
    assert report['ok'], report['errors']
    assert report['scored_planned_searching'] == 1
    assert report['planned_searching'] == report['total_planned_searching'] == 3
    assert len(report['unscored_event_ids']) == 2 and pending in report['unscored_event_ids']
    assert {e['event_id'] for e in generate_script(plan, formal=False)['events']} == scored
    assert '暫失 < 1.8 s' in report['scope_statement']
    # A non-scoring marker also excludes an event when stored inside `events`.
    plan['events'].append(plan['unscored_events'].pop())
    assert {e['event_id'] for e in generate_script(plan, formal=False)['events']} == scored
    assert precheck(plan)['total_planned_searching'] == 3


def test_two_scored_and_two_unscored_searches_exceed_budget():
    plan = plan_of('a4_1')
    extra = deepcopy(plan['unscored_events'][0])
    extra.update(event_id='A4-extra', t_x_us=42*S, t_n_us=45*S)
    plan['unscored_events'].append(extra)
    report = precheck(plan)
    assert report['scored_planned_searching'] == 2 and report['total_planned_searching'] == 4
    assert not report['ok'] and 'planned SEARCHING 4 > 3' in report['errors']


def test_unscored_a4_e_still_supports_ns_s5_without_c2():
    plan = current_plan('a4_1')
    plan['unscored_events'] = plan['unscored_events'][:1]  # only A4-e remains after A4-n1
    report = precheck(plan)
    assert report['ok'], report['errors']
    assert report['scored_planned_searching'] == 1 and report['total_planned_searching'] == 2
    assert {e['event_id'] for e in generate_script(plan, formal=False)['events']} == {'A4-c1', 'A4-n1'}


@pytest.mark.parametrize('change,needle', [
    ({'event_id':'A4-c1'}, 'duplicate event_id'),
    ({'t_x_us':None}, 't_x_us'),
    ({'t_n_us':None}, 't_n_us'),
    ({'scoring_status':'TYPO'}, 'scoring_status'),
    ({'scoring_status':'SCORED'}, 'cannot declare SCORED'),
])
def test_unscored_schedule_is_validated(change, needle):
    plan = current_plan('a4_1')
    plan['unscored_events'][0].update(change)
    with pytest.raises(PlanError, match=needle):
        generate_script(plan, formal=False)


def test_unscored_schedule_is_hash_bound():
    plan = frozen()
    plan['approval_ref'] = good_ref(plan)
    plan['unscored_events'][0]['t_x_us'] += 200_000
    with pytest.raises(PlanError, match='SHA-256'):
        generate_script(plan, formal=True)

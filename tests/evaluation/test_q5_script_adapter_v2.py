"""評分端；與推論隔離。CQ-33-T uses synthetic plans, never authority or rendered evidence.

The driver is an explicit TEST-ONLY translator, not a proposed production API.
It must call the real adapter and return its native script without rewriting it.
"""
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
FIXTURE = ROOT / 'tests/fixtures/l2_script_plans/SYNTHETIC/cases.SYNTHETIC.json'
CASES = json.loads(FIXTURE.read_bytes())
POSITIVES = CASES['positive']
NEGATIVES = CASES['negative']


def required_module():
    path = ROOT / 'src/amidst/evaluation/q5_script_adapter_v2.py'
    if not path.is_file():
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ33_IMPLEMENTATION_MISSING')
        pytest.importorskip('amidst.evaluation.q5_script_adapter_v2', reason='CQ33_IMPLEMENTATION_MISSING')
        pytest.skip('CQ33_LOCAL_IMPLEMENTATION_MISSING')
    return importlib.import_module('amidst.evaluation.q5_script_adapter_v2')


def exercise(case):
    implementation = required_module()
    selected = os.environ.get('AMIDST_Q5_ADAPTER_V2_DRIVER')
    if not selected:
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ33_TEST_DRIVER_UNBOUND')
        pytest.skip('CQ33_TEST_DRIVER_UNBOUND')
    # A selected driver with broken imports is an actual error, not a missing implementation skip.
    driver = importlib.import_module(selected)
    data = deepcopy(case)
    # The adapter/driver never receives the golden answer or expected error category.
    for key in ('expected_script_fields', 'expected_planned_searching', 'expected_rejection_category'):
        data.pop(key, None)
    path = Path(implementation.__file__).resolve()
    invoked = []
    old_profile = sys.getprofile()

    def trace(frame, event, arg):
        if event == 'call' and Path(frame.f_code.co_filename).resolve() == path:
            invoked.append(frame.f_code.co_name)

    try:
        sys.setprofile(trace)
        result = driver.exercise_case(inputs=data, implementation=implementation)
    except (pytest.skip.Exception, pytest.xfail.Exception):
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ33_REQUIRED_DRIVER_BINDING_MISSING')
        raise
    finally:
        sys.setprofile(old_profile)
    assert invoked, 'Driver must invoke the real v2 adapter, not a stub or fixture echo'
    assert result['implementation_file_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result['human_approval_verified'] is False
    return result


def assert_subset(actual, expected):
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        for key, value in expected.items():
            assert key in actual
            assert_subset(actual[key], value)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected)
        for a, e in zip(actual, expected):
            assert_subset(a, e)
    else:
        assert actual == expected and type(actual) is type(expected)


def forbidden_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            lower = key.lower()
            if any(word in lower for word in ('renderer', 'visibility', 'depth', 'trajectory')) or lower in {'gt', 'ground_truth', 't_l_us', 't_v_us', 'plan_checks_only'}:
                yield key
            yield from forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from forbidden_keys(item)


def assert_rejected(result, category):
    assert result['rejected'] is True
    assert result.get('native_script') is None
    assert result['error_category'] == category


def test_fixture_independent_hand_calculation_and_synthetic_boundaries():
    raw = FIXTURE.read_text()
    assert not any(token in raw for token in ('/Users/', '/private/', '.blend', 'approval_ref": "https:'))
    assert len(POSITIVES) == len(NEGATIVES) == 4
    assert {c['card_kind'] for c in POSITIVES} == {'RR', 'LG', 'PE1', 'OV1'}
    assert all(c['fixture_role'] == 'SYNTHETIC_ONLY' and c['case_id'].startswith('SYNTHETIC-') for c in POSITIVES + NEGATIVES)
    # Independent literals: seconds converted to integer microseconds. No implementation formula is imported.
    assert [e['decision_window_us'] for e in POSITIVES[0]['expected_script_fields']['events']] == [[1200000, 8200000], [11200000, 18200000]]
    assert POSITIVES[1]['expected_script_fields']['events'][0]['decision_window_us'] == [9200000, 18400000]
    assert POSITIVES[2]['expected_script_fields']['events'][0]['entry_windows_us'] == {
        'SYNTHETIC-CAM-A': {'kind': 'BLIND', 'range_us': [12400000, 14000000]},
        'SYNTHETIC-CAM-B': {'kind': 'BLIND', 'range_us': [13800000, 15400000]}}
    assert POSITIVES[3]['expected_script_fields']['events'][0]['decision_window_us'] == [4600000, 11600000]
    for case in POSITIVES:
        expected = case['expected_script_fields']; binding = expected['parameter_binding']
        raw_params = json.dumps(case['parameters'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert binding['parameter_set_sha256'] == hashlib.sha256(raw_params).hexdigest()
        assert not list(forbidden_keys(expected))
        assert case['test_only_selections']['U-D10'] == 'PENDING_USER'
    # LG negative isolates budget: g=8 consumes 4; no accidental early-visible violation.
    camera = NEGATIVES[1]['plan']['events'][0]['cameras']['SYNTHETIC-CAM-N']
    assert camera['plan_checks_only']['t_V_us'] >= camera['t_N_us'] - 600000


@pytest.mark.parametrize('case', POSITIVES, ids=lambda c: c['case_id'])
def test_each_card_produces_exact_hand_calculated_v2_windows(case):
    result = exercise(case)
    assert result['rejected'] is False
    script = result['native_script']
    assert_subset(script, case['expected_script_fields'])
    assert script['parameter_binding'] == case['expected_script_fields']['parameter_binding']
    assert result['planned_searching'] == case['expected_planned_searching']
    assert not list(forbidden_keys(script))


@pytest.mark.parametrize('case', NEGATIVES, ids=lambda c: c['case_id'])
def test_d94_early_visible_budget_and_blocked_geometry_reject(case):
    assert_rejected(exercise(case), case['expected_rejection_category'])


@pytest.mark.parametrize('duration,klass,window,returns', [
    (1600000, 'STANDARD', [1600000, 8600000], None),
    (1800000, 'LONG_LOSS', [1800000, 8800000], 2),
])
def test_d94_endpoints_remain_distinct(duration, klass, window, returns):
    case = deepcopy(POSITIVES[0]); case['plan']['events'] = case['plan']['events'][:1]
    case['plan']['events'][0]['t_N_us'] = 6000000 + duration
    result = exercise(case)
    assert result['rejected'] is False
    event = result['native_script']['events'][0]
    assert event['event_class'] == klass and event['decision_window_us'] == window
    assert result['planned_searching'] == (1 if returns is None else returns)
    if returns is not None:
        assert event['return_count_max'] == returns


def test_unselected_proposed_rules_fail_closed():
    case = deepcopy(POSITIVES[1]); case['test_only_selections'] = {}
    assert_rejected(exercise(case), 'PROPOSED_RULE_UNSELECTED')


def test_v1_is_rejected_or_explicitly_dispatched_without_conversion():
    case = deepcopy(POSITIVES[0]); case['plan']['version_under_test'] = 1
    result = exercise(case)
    if result['rejected']:
        assert_rejected(result, 'VERSION_UNSUPPORTED')
    else:
        assert result['dispatched_version'] == 'v1'
        assert result['native_script']['schema_version'] == 'q5-evaluation-script.v1'


def native_case(case=None):
    from q5_adapter_v2_test_driver import translate
    from amidst.evaluation import q5_switch_eval as v1
    module = required_module()
    plan, params, config = translate(deepcopy(case or POSITIVES[0]))
    args = dict(expected_plan_sha256=v1.sha(plan), parameters_raw=params,
        expected_parameters_sha256=v1.sha(params), decisions_raw=config,
        expected_decisions_sha256=v1.sha(config), plan_path='SYNTHETIC_TEST_ONLY',
        synthetic_controls=module.SyntheticPlanInputs())
    return module, plan, args


@pytest.mark.parametrize('which', ['plan', 'parameters', 'decisions'])
def test_native_adapter_requires_each_input_byte_pin(which):
    module, plan, args = native_case()
    args['expected_' + which + '_sha256'] = '0' * 64
    with pytest.raises(module.PlanError, match='pin mismatch'):
        module.generate_script(plan, **args)


def test_native_adapter_does_not_promote_frozen_or_synthetic_authority():
    from amidst.evaluation import q5_switch_eval as v1
    module, raw, args = native_case()
    with pytest.raises(module.PlanError) as formal:
        module.generate_script(raw, **args, formal=True)
    assert formal.value.category == 'HUMAN_APPROVAL_UNSELECTED'
    doc = json.loads(raw); doc.update(status='FROZEN', approval_ref='https://example.invalid/self-authored')
    changed = v1.canonical(doc)
    with pytest.raises(module.PlanError) as frozen:
        module.generate_script(changed, **{**args, 'expected_plan_sha256':v1.sha(changed)})
    assert frozen.value.category == 'HUMAN_APPROVAL_UNSELECTED'
    doc.update(status='UNFROZEN', run_id='ctrl-r004-UNKNOWN')
    changed = v1.canonical(doc)
    with pytest.raises(module.PlanError) as real:
        module.generate_script(changed, **{**args, 'expected_plan_sha256':v1.sha(changed)})
    assert real.value.category == 'SYNTHETIC_SCOPE_REQUIRED'


def test_native_adapter_ignores_forged_previous_end_and_drops_private_checks():
    from amidst.evaluation import q5_switch_eval as v1
    module, raw, args = native_case(POSITIVES[2])
    doc = json.loads(raw); event = doc['events'][0]
    event.update(t_prev_end_us=999999999, renderer_private_bait='DO_NOT_COPY')
    changed = v1.canonical(doc)
    actual, count = module.generate_script(changed, **{**args, 'expected_plan_sha256':v1.sha(changed)})
    assert actual['events'][0]['decision_window_us'] == [7000000,15400000]
    assert count == 1 and not list(forbidden_keys(actual))
    assert 't_prev_end_us' not in actual['events'][0]


def test_adapter_and_scorer_roundtrip_with_real_parameter_document():
    from amidst.evaluation import q5_switch_eval as v1, q5_switch_eval_v2 as scorer
    module = required_module(); fixtures = ROOT / 'tests/fixtures/q5_v2/SYNTHETIC'
    params = (fixtures/'parameter_set.SYNTHETIC.json').read_bytes()
    source = json.loads((fixtures/'phase.script.SYNTHETIC.json').read_bytes())
    plan = {'schema_version':module.PLAN_SCHEMA, 'status':'UNFROZEN', 'plan_id':'SYNTHETIC_ROUNDTRIP',
        'run_id':source['run_id'], 'clock_id':source['clock_id'], 'query_range_us':[0,12000000],
        'source_duration_us':12000000, 'geometry_status':'SYNTHETIC_FEASIBLE',
        'parameter_binding':source['parameter_binding'], 'events':[{'event_id':'SYNTHETIC_LONG_GAP',
        'action':'SWITCH','t_x_us':0,'cameras':{'SYNTHETIC_C':{'kind':'BLIND','t_N_us':6800000,
        'plan_checks_only':{'t_L_us':0,'t_V_us':6400000,'evidence_kind':'SYNTHETIC_PLAN_CHECK_ONLY'}}}}]}
    selections = {k:v.removeprefix('TEST_ONLY:') for k,v in json.loads((fixtures/'CASES.SYNTHETIC.json').read_bytes())['test_only_selections'].items()}
    selections['UK-8'] = 'PLAN_CHECK_ONLY'
    raw, config = v1.canonical(plan), v1.canonical(selections)
    script, count = module.generate_script(raw, expected_plan_sha256=v1.sha(raw), parameters_raw=params,
        expected_parameters_sha256=v1.sha(params), decisions_raw=config, expected_decisions_sha256=v1.sha(config),
        plan_path='SYNTHETIC_ROUNDTRIP', synthetic_controls=module.SyntheticPlanInputs())
    assert count == 3 and script['parameter_binding'] == source['parameter_binding']
    assert script['events'] == source['events']
    response = (fixtures/'phase.response.SYNTHETIC.json').read_bytes()
    decisions = (fixtures/'phase.decisions.SYNTHETIC.jsonl').read_bytes()
    frozen = scorer.freeze_output(response, decisions, expected_response_sha256=v1.sha(response), expected_decisions_sha256=v1.sha(decisions))
    script_raw = v1.canonical(script)
    report = scorer.compare_script(frozen, script_raw, expected_script_sha256=v1.sha(script_raw), parameters_raw=params,
        expected_parameters_sha256=v1.sha(params), plan_raw=raw, expected_plan_sha256=v1.sha(raw),
        decisions_raw=config, expected_decisions_config_sha256=v1.sha(config))
    assert report['event_match_ratio'] == {'numerator':1,'denominator':1,'value':1.0}
    assert report['human_approval_verified'] is report['formal_accepted'] is False


@pytest.mark.parametrize('card,event_ids', [('rr',['RR-a1','RR-a2','RR-b1','RR-b2']),('lg',['LG-1']),('pe1',['PE1-d']),('ov1',['OV1-a','OV1-b'])])
def test_d99_plan_drafts_preserve_unknown_and_default_refusal(card, event_ids):
    from amidst.evaluation import q5_switch_eval as v1
    module = required_module()
    raw = (ROOT/f'configs/evaluation/l2_{card}_script_plan_v2.json').read_bytes()
    plan = json.loads(raw)
    assert plan['status'] == 'UNFROZEN' and plan['approval_ref'] is None
    assert plan['run_id'] == plan['clock_id'] == plan['parameter_binding']['parameter_set_sha256'] == 'UNKNOWN'
    assert [e['event_id'] for e in plan['events']] == event_ids
    if card == 'rr': assert [e['event_class'] for e in plan['events'][2:]] == ['UNKNOWN','UNKNOWN']
    config = (ROOT/'configs/evaluation/q5_v2_decisions.json').read_bytes()
    with pytest.raises(module.PlanError) as pending:
        module.generate_script(raw, expected_plan_sha256=v1.sha(raw), parameters_raw=b'{}',
            expected_parameters_sha256=v1.sha(b'{}'), decisions_raw=config,
            expected_decisions_sha256=v1.sha(config),plan_path='UNFROZEN')
    assert pending.value.category == 'PROPOSED_RULE_UNSELECTED'


def test_producer_cli_refuses_default_and_formal_but_emits_explicit_return_preview(tmp_path):
    from amidst.evaluation import q5_switch_eval as v1
    module, raw, args = native_case()
    plan = json.loads(raw); plan.update(run_id='SYNTHETIC_RUN', clock_id='SYNTHETIC_CLOCK')
    fixtures = ROOT/'tests/fixtures/q5_v2/SYNTHETIC'
    params = (fixtures/'parameter_set.SYNTHETIC.json').read_bytes()
    def command(config):
        docs={'plan':v1.canonical(plan),'parameters':params,'decisions-config':config}
        result=[sys.executable,str(ROOT/'scripts/gen_q5_script_v2.py')]
        for key,value in docs.items():
            path=tmp_path/(key+'.json'); path.write_bytes(value)
            result.extend(['--'+key,str(path),'--'+key+'-sha256',v1.sha(value)])
        return result+['--output',str(tmp_path/'preview.json')]
    environment={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
    pending=command(b'{}')
    result=subprocess.run(pending,env=environment,capture_output=True,text=True)
    assert result.returncode == 2 and 'PROPOSED_RULE_UNSELECTED' in result.stderr
    output=tmp_path/'preview.json'; assert not output.exists()
    selected=command(args['decisions_raw'])
    formal=subprocess.run(selected+['--formal'],env=environment,capture_output=True,text=True)
    assert formal.returncode == 2 and 'HUMAN_APPROVAL_UNSELECTED' in formal.stderr
    assert not output.exists()
    result=subprocess.run(selected,env=environment,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    first=output.read_bytes(); script=json.loads(first)
    assert script['status']=='PROPOSED' and script['approval_ref'] is None and not list(forbidden_keys(script))
    repeat=subprocess.run(selected,env=environment,capture_output=True,text=True)
    assert repeat.returncode == 2 and output.read_bytes()==first

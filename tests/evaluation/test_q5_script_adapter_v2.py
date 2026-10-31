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

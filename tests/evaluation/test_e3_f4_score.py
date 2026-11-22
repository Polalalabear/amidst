"""F4 (#658) scoring helpers: API outcome breakdown and the D350 H2 supplementary diagnostics. SYNTHETIC ticks only."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m          # dataclasses need the module registered
    spec.loader.exec_module(m)
    return m


F4 = load('e3_f4_score', ROOT / 'scripts/evaluation/e3_f4_score.py')
SCORER = ROOT / 'src/amidst/evaluation/e3_scoring.py'


def test_api_breakdown_separates_not_applied_from_errors():
    calls = [{'applied': True, 'source': 'AGENT'},
             {'applied': False, 'source': 'RULE_FALLBACK', 'fallback_reason': 'TIME_BUDGET', 'answer': 'SELECT'},   # answered, not executable
             {'applied': False, 'source': 'RULE_FALLBACK', 'fallback_reason': 'TIME_BUDGET', 'answer': None},       # real timeout
             {'applied': False, 'source': 'RULE_FALLBACK', 'fallback_reason': 'EXPIRED', 'answer': 'SELECT'},
             {'applied': False, 'source': 'RULE_FALLBACK', 'fallback_reason': 'PROVIDER_UNAVAILABLE', 'answer': None},
             {'applied': False, 'source': 'AGENT', 'fallback_reason': None, 'answer': 'NOT_VISIBLE'}]
    b = F4.api_breakdown(calls)
    assert (b['applied'], b['agent_not_applied'], b['timeout'], b['expired'], b['error'], b['answered_no_effect']) == (1, 1, 1, 1, 1, 1)
    assert b['error_rate'] == round(1 / 6, 4) and b['error_stop'] is True and b['error_reasons'] == {'PROVIDER_UNAVAILABLE': 1}
    assert F4.api_breakdown([{'applied': False, 'fallback_reason': 'TIME_BUDGET', 'answer': None}] * 5)['error_stop'] is False   # D352
    assert F4.api_breakdown([{'applied': False, 'fallback_reason': 'CALL_BUDGET_EXHAUSTED'}] + [{'applied': True}] * 20)['error_stop'] is True


@pytest.mark.skipif(not SCORER.is_file(), reason='e3_scoring.py (PR #662) not in this checkout')
def test_diagnostics_occlusion_rescue_exit_and_switches():
    S = load('e3_scoring', SCORER)
    T = lambda k, cam, vis, box=None, body=None: S.Tick(k * F4.TICK_US, cam, boxes=(box,) if box else (), visible=frozenset(vis),
                                                       body=body, size=F4.SIZE, tick_us=F4.TICK_US)
    B = (10, 10, 40, 90)
    ticks = [T(0, 'W2', {'W2'}, B, B),            # correct on W2
             T(1, 'W2', set()),                   # occluded, held on W2 camera-only -> FALSE_LOCK (no hold_ok)
             T(2, None, set()),                   # occluded, nothing shown
             T(3, 'W1', {'W2'}, B, None),         # switch to a camera that cannot see the target -> wrong switch
             T(4, 'W2', {'W2'}, B, B),            # switch back, correct
             T(5, None, {'R'})]                   # target left to R, nothing shown
    case = {'decision_points': [{'type': 'SCREEN_BEFORE_OCCLUSION', 'tick': 0, 'cameras': ['W2'], 'timestamp_us': 0, 'evaluation_window_us': [0, 600000]},
                                {'type': 'SCREEN_RETURN', 'tick': 3, 'cameras': ['W2'], 'timestamp_us': 600000, 'evaluation_window_us': [600000, 800000]},
                                {'type': 'TRUE_EXIT_BOUNDARY', 'tick': 4, 'cameras': ['R'], 'timestamp_us': 800000, 'evaluation_window_us': [800000, 1000000]}],
            'diagnostic_events': [{'type': 'SCREEN_OCCLUSION', 'tick': 1}]}
    d = F4.diagnostics(S, case, ticks, b1_class={4: 'LOST', 5: 'LOST'}, missed={4, 5})
    assert d['occlusion']['ticks'] == 2 and d['occlusion']['kept'] == 0 and d['occlusion']['false_lock_s'] == 0.2
    assert d['miss_rescue'] == {'rule_lost_on_missed_ticks': 2, 'rescued': 1, 'rescued_own_box': 0, 'rescued_detection_box': 1, 'rate': 0.5}
    assert d['switches'] == {'total': 3, 'wrong': 1}
    assert [e['type'] for e in d['exit']] == ['TRUE_EXIT_BOUNDARY'] and d['exit'][0]['stale_old_camera_s'] == 0.0

"""E4 (#681) H7 verdict rules, preregistration §5 (SYNTHETIC intervals only)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('e4_score', ROOT / 'scripts/evaluation/e4_score.py')
E4 = importlib.util.module_from_spec(spec)
sys.modules['e4_score'] = E4
spec.loader.exec_module(E4)


def cmp(wp, follow=(-0.01, 0.02), fl=(-1, 1)):
    return {'wp_diff_ci': list(wp), 'follow_diff_ci': list(follow), 'fl_diff_ci': list(fl)}


def test_h7a_needs_both_better_than_e3_and_noninferior_to_b1():
    assert E4.h7a(cmp((-90, -20)), cmp((-10, 15)))['verdict'] == 'SUPPORTED'
    r = E4.h7a(cmp((-90, -20)), cmp((5, 40)))                     # better than E3, B1 interval crosses the +17.1 s margin
    assert r['verdict'] == 'INCONCLUSIVE' and r['note'] == 'BETTER_THAN_E3_BUT_NONINFERIORITY_NOT_SHOWN'
    assert E4.h7a(cmp((-90, -20)), cmp((-10, 15), follow=(-0.08, 0.0)))['verdict'] == 'INCONCLUSIVE'
    assert E4.h7a(cmp((0, 30)), cmp((-10, 15)))['verdict'] == 'NOT_SUPPORTED'
    assert E4.h7a(cmp((-90, -20)), cmp((18, 60)))['verdict'] == 'NOT_SUPPORTED'
    assert E4.h7a(cmp((-30, 5)), cmp((-10, 15)))['verdict'] == 'INCONCLUSIVE'


def test_h7b_and_h7c_thresholds():
    assert E4.h7b(cmp((0, 0), fl=(-40, -1)))['verdict'] == 'SUPPORTED'
    assert E4.h7b(cmp((0, 0), fl=(0, 10)))['verdict'] == 'NOT_SUPPORTED'
    assert E4.h7b(cmp((0, 0), fl=(-5, 5)))['verdict'] == 'INCONCLUSIVE'
    assert [E4.h7c(n, 111)['verdict'] for n in (56, 55, 20, 19)] == ['SUPPORTED', 'INCONCLUSIVE', 'INCONCLUSIVE', 'NOT_SUPPORTED']

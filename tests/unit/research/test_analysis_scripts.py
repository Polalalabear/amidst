"""Research analysis scripts on SYNTHETIC fixtures only (no real run, no GT, no experiment)."""
import csv
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'scripts/research'))
import _common as c  # noqa: E402
import analyze_experiments as ax  # noqa: E402
import build_baseline_table as bt  # noqa: E402

FX = REPO / 'tests/fixtures/research'
B = ['--bootstrap-b', '200']


def table(path):
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def test_fixtures_are_labelled_synthetic_and_small():
    files = sorted(FX.iterdir())
    assert files and all(f.name.startswith('SYNTHETIC_') for f in files)
    assert sum(f.stat().st_size for f in files) < 200_000
    for f in files:
        if f.suffix == '.json':
            assert json.loads(f.read_text(encoding='utf-8'))['source_class'] == 'SYNTHETIC'


def test_stats_helpers():
    assert c.sign_test_one_sided(0, 0) is None
    assert c.sign_test_one_sided(9, 1) == pytest.approx(11 / 1024)
    assert c.percentile_nr([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9
    lo, hi = c.wilson(5, 10)
    assert lo < 50 < hi
    one = c.prop({'r': [1, 0, 1, 1]})
    assert one['ci_method'] == 'wilson' and one['n'] == 4
    assert c.prop({})['pct'] == c.UNKNOWN
    two = c.prop({'a': [1, 1], 'b': [0, 1]}, b=200)
    assert two['ci_method'] == 'cluster_bootstrap' and two == c.prop({'a': [1, 1], 'b': [0, 1]}, b=200)
    assert c.median_stat({'only': [1, 2, 3]})['lo'] == c.UNKNOWN


def test_baseline_table_shows_unknown_and_does_not_impute(tmp_path):
    assert bt.main([str(FX / 'SYNTHETIC_baseline_results.json'), '--out', str(tmp_path), *B]) == 0
    rows = {(r['row'], r['run_id']): r for r in table(tmp_path / 'baseline_B1.csv')}
    a, b = rows[('request', 'SYNTHETIC-A')], rows[('request', 'SYNTHETIC-B')]
    assert (a['n_events_scored'], a['n_events_not_scored'], a['not_scored_breakdown']) == ('4', '1', 'LONG_GAP:1')
    assert a['C_evt_pct'] == '50.0000' and a['C_evt_method'] == 'wilson'
    assert b['n_match_unknown'] == '1' and b['n_events_scored'] == '3'  # unknown match left out of the denominator
    assert b['FS_per_min'] == c.UNKNOWN and a['FS_per_min'] != c.UNKNOWN  # scoped_minutes UNKNOWN
    assert a['L_sw_lo'] == c.UNKNOWN  # one cluster: no bootstrap CI for the median
    assert a['L_sw_n_unknown'] == '1' and a['L_sw_n'] == '1'  # UNKNOWN latency not imputed
    total = rows[('TOTAL:ALL', 'ALL')]
    assert total['C_evt_method'] == 'cluster_bootstrap' and total['n_events_scored'] == '7'
    assert total['fps'] == c.UNKNOWN
    assert 'SYNTHETIC' in (tmp_path / 'baseline_B1.md').read_text(encoding='utf-8')
    for name in ('G-B1_c_evt', 'G-B2_l_sw', 'G-B3_coverage'):
        assert (tmp_path / f'{name}.png').stat().st_size > 1000 and (tmp_path / f'{name}.svg').stat().st_size > 1000


def test_baseline_outputs_are_deterministic(tmp_path):
    for sub in ('x', 'y'):
        bt.main([str(FX / 'SYNTHETIC_baseline_results.json'), '--out', str(tmp_path / sub), *B])
    for name in ('baseline_B1.csv', 'baseline_B1.md', 'G-B1_c_evt.svg'):
        assert (tmp_path / 'x' / name).read_bytes() == (tmp_path / 'y' / name).read_bytes()


def test_baseline_with_no_rule_only_runs_is_empty_not_invented(tmp_path):
    data = json.loads((FX / 'SYNTHETIC_baseline_results.json').read_text(encoding='utf-8'))
    data['runs'] = []
    src = tmp_path / 'in.json'
    src.write_text(json.dumps(data), encoding='utf-8')
    assert bt.main([str(src), '--out', str(tmp_path / 'o'), *B]) == 0
    assert table(tmp_path / 'o' / 'baseline_B1.csv') == []
    assert not list((tmp_path / 'o').glob('*.png'))


def test_contract_and_experiment_mismatch_are_rejected(tmp_path):
    with pytest.raises(SystemExit):
        ax.main(['m2', str(FX / 'SYNTHETIC_m1_results.json'), '--out', str(tmp_path)])
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({'contract': 'other', 'experiment': 'M2', 'source_class': 'SYNTHETIC'}))
    with pytest.raises(SystemExit):
        ax.main(['m2', str(bad), '--out', str(tmp_path)])


def test_m1_excludes_unfair_pairs_and_leaves_verdict_unknown(tmp_path):
    assert ax.main(['m1', str(FX / 'SYNTHETIC_m1_results.json'), '--out', str(tmp_path), *B]) == 0
    t2 = table(tmp_path / 'm1_M1-2.csv')[0]
    assert 'pair:INVALID_COMPARISON:parameter_set_sha256=1' in t2['excluded_counts']
    assert 'SYNTHETIC-D:INVALID_COMPARISON' in (tmp_path / 'm1_M1-2.md').read_text(encoding='utf-8')  # named, not scored
    n, tie, w, l = (int(t2[k]) for k in ('n_pairs', 'n_tie', 'n_agent_better', 'n_rule_better'))
    assert n == tie + w + l and n == 18
    assert t2['verdict'] == c.UNKNOWN and t2['p_holm'] == c.UNKNOWN and t2['gate_FB'] == 'FAIL'
    arms = {r['arm']: r for r in table(tmp_path / 'm1_M1-1.csv')}
    assert arms['RULE_ONLY']['TO_pct'] == 'n/a'
    assert arms['AGENT_SEQUENTIAL']['tokens_per_call'] == c.UNKNOWN  # tokens UNKNOWN in the input
    for name in ('G-M1a_paired', 'G-M1b_decision_source', 'G-M1d_latency_ecdf', 'G-M1e_failure_rates'):
        assert (tmp_path / f'{name}.png').exists() and (tmp_path / f'{name}.svg').exists()


def test_m1_relaxed_arm_without_data_is_marked_not_compared(tmp_path):
    ax.main(['m1', str(FX / 'SYNTHETIC_m1_results.json'), '--out', str(tmp_path), '--agent-arm', 'AGENT_SEQUENTIAL_RELAXED', *B])
    t2 = table(tmp_path / 'm1_M1-2_relaxed.csv')[0]
    assert t2['n_pairs'] == '0' and t2['verdict'] == 'EXPLORATORY_NOT_IN_H1' and t2['diff_C_evt_pp'] == c.UNKNOWN


def test_m2(tmp_path):
    ax.main(['m2', str(FX / 'SYNTHETIC_m2_results.json'), '--out', str(tmp_path)])
    row = table(tmp_path / 'm2_M2-1.csv')[0]
    assert row['n_std_both_scored'] == '12' and row['n_disagree'] == '1' and 'SYN-STD-5:SYN-RULE-1' in row['disagree_rule_refs']
    assert float(row['A_std_pct']) == pytest.approx(100 * 11 / 12, abs=1e-3) and row['gate_A_std_ge_99'] == 'FAIL'
    assert row['n_not_scored_expected_unknown'] == '1' and float(row['L_ns_pct']) == 75.0
    assert (tmp_path / 'G-M2a_confusion.svg').exists()


def test_m3_reads_only_eligible_rows(tmp_path):
    ax.main(['m3', str(FX / 'SYNTHETIC_m3_results.json'), '--queries', str(FX / 'SYNTHETIC_m3_queries_eligible.csv'), '--out', str(tmp_path), *B])
    rows = table(tmp_path / 'm3_M3-1.csv')
    assert {r['wording_type'] for r in rows} == {'ALL', 'P', 'T', 'V'}
    assert {r['n_questions_scored'] for r in rows if r['wording_type'] == 'ALL'} == {'36'}  # out-of-set result row dropped
    assert 'dropped' in (tmp_path / 'm3_M3-1.md').read_text(encoding='utf-8')
    assert table(tmp_path / 'm3_M3-2.csv')[0]['verdict'] == c.UNKNOWN
    assert (tmp_path / 'G-M3e_wording.png').exists()


@pytest.mark.parametrize('queries', ['SYNTHETIC_m3_queries_draft_all_false.csv', 'SYNTHETIC_m3_queries_draft_no_flag_column.csv'])
def test_m3_unapproved_set_gives_empty_output_and_warning(tmp_path, capsys, queries):
    ax.main(['m3', str(FX / 'SYNTHETIC_m3_results.json'), '--queries', str(FX / queries), '--out', str(tmp_path)])
    assert '評測集未核定' in capsys.readouterr().out
    assert table(tmp_path / 'm3_M3-1.csv') == []
    assert '評測集未核定' in (tmp_path / 'm3_M3-1.md').read_text(encoding='utf-8')
    assert sorted(p.name for p in tmp_path.iterdir()) == ['m3_M3-1.csv', 'm3_M3-1.md']  # no charts, no other tables


def test_m4_exploratory_and_unknown_size(tmp_path):
    ax.main(['m4', str(FX / 'SYNTHETIC_m4_results.json'), '--out', str(tmp_path), *B])
    rows = table(tmp_path / 'm4_M4-1.csv')
    big = [r for r in rows if r['model'] == 'SYN-model-large']
    assert all(r['llm_loaded_size_gib'] == c.UNKNOWN for r in big)
    q3 = [r for r in rows if r['module'] == 'Q3']
    assert all(r['baseline_pct'] == c.UNKNOWN and r['diff_pp'] == c.UNKNOWN for r in q3)
    assert 'EXPLORATORY' in (tmp_path / 'm4_M4-1.md').read_text(encoding='utf-8')
    assert (tmp_path / 'G-M4_Q2.svg').exists() and (tmp_path / 'G-M4_Q3.svg').exists()

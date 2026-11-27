"""E6 batch-3 selector and formal gate (prereg 2.2 / 7.1): synthetic metrics only, no GT, no model, no network."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from amidst.evaluation.e7_scoring_bridge import FORBIDDEN_GT_FIELDS

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e6_select_arm', ROOT / 'scripts/evaluation/e6_select_arm.py')
M = importlib.util.module_from_spec(_spec)
sys.modules['e6_select_arm'] = M
_spec.loader.exec_module(M)

SHA = 'a' * 40
PINNED = ('src/amidst/live_mode/aopen/decider.py', 'docs/evaluation/E6_PREREGISTRATION_DRAFT.md')


@pytest.fixture(autouse=True)
def pinned_files(monkeypatch):
    monkeypatch.setattr(M, 'PROMPT_FILES', PINNED)       # arms.py only exists once #746 is on main


def per_case(wp, fl, follow, calls=40, fmt=0, prov=0, viol=(), budget=0):
    return {'wrong_person_s': wp, 'false_lock_s': fl, 'follow_rate': follow, 'lost_s': 0.0, 'calls': calls,
            'format_rejected': fmt, 'provider_errors': prov, 'budget_denied': budget, 'gt_violations': list(viol)}


def arm(name, wp, fl, follow, **kw):
    """Spread the totals over the three diagnostic cases."""
    return M.aggregate_arm(name, {c: per_case(wp / 3, fl / 3, follow, **kw) for c in M.DIAG_CASES})


def pick(**by_arm):
    metrics = {n: arm(n, *v[:3], **(v[3] if len(v) > 3 else {})) for n, v in by_arm.items()}
    return M.choose(metrics)


# ---------------------------------------------------------------- hard gate
def test_gate_thresholds_inclusive():
    ok = arm('DEANCHOR', 10, 5, 0.5, calls=100, fmt=20, prov=10)         # exactly 20 % and 10 %: allowed
    assert M.eligibility(ok) == []
    assert any(r.startswith('FORMAT_RETURN') for r in M.eligibility(arm('DEANCHOR', 1, 1, 1, calls=100, fmt=21)))
    assert any(r.startswith('PROVIDER_ERROR') for r in M.eligibility(arm('DEANCHOR', 1, 1, 1, calls=100, prov=11)))


def test_gt_violation_makes_ineligible():
    m = arm('DEANCHOR', 1, 1, 1, viol=['calls[0].request.gt_boxes'])
    assert any(r.startswith('GT_ISOLATION_VIOLATIONS') for r in M.eligibility(m))


def test_budget_exhausted_and_missing_case_ineligible():
    assert any(r.startswith('CALL_BUDGET_EXHAUSTED') for r in M.eligibility(arm('DEANCHOR', 1, 1, 1, budget=1)))
    two = M.aggregate_arm('DEANCHOR', {c: per_case(1, 1, 1) for c in M.DIAG_CASES[:2]})
    assert M.eligibility(two)[0].startswith('MISSING_CASES')


def test_none_eligible_returns_none():
    sel, trace, inel = pick(DEANCHOR=(1, 1, 1, {'calls': 100, 'fmt': 50}), DEANCHOR_HIST=(1, 1, 1, {'calls': 100, 'prov': 50}))
    assert sel is None and inel['DEANCHOR_HIST_SUM'] == ['NOT_RUN']


def test_ineligible_group_cannot_win_even_if_best():
    sel, *_ = pick(DEANCHOR=(50, 9, 0.3), DEANCHOR_HIST=(1, 0, 0.99, {'viol': ['x']}), DEANCHOR_HIST_SUM=(40, 9, 0.3))
    assert sel == 'DEANCHOR_HIST_SUM'


# ---------------------------------------------------------------- four ordered levels
def test_level1_wrong_person_decides_beyond_tolerance():
    sel, *_ = pick(DEANCHOR=(30.0, 0, 0.5), DEANCHOR_HIST=(28.9, 50, 0.1), DEANCHOR_HIST_SUM=(40, 0, 0.9))
    assert sel == 'DEANCHOR_HIST'                  # 1.1 s better wins at level 1 although worse on blind lock and follow


def test_level1_tie_within_1s_goes_to_level2():
    sel, trace, _ = pick(DEANCHOR=(30.0, 9.0, 0.5), DEANCHOR_HIST=(29.0, 3.0, 0.5), DEANCHOR_HIST_SUM=(60, 0, 0.9))
    assert sel == 'DEANCHOR_HIST'                  # exactly 1.0 s apart is a tie; level 2 picks the lower blind lock
    assert trace[0]['kept'] == ['DEANCHOR', 'DEANCHOR_HIST'] and trace[1]['level'] == 'blind_false_lock_s'


def test_level2_tie_goes_to_level3_follow_rate():
    sel, trace, _ = pick(DEANCHOR=(30, 5.0, 0.60), DEANCHOR_HIST=(30, 5.9, 0.75), DEANCHOR_HIST_SUM=(30, 5.5, 0.70))
    assert sel == 'DEANCHOR_HIST'
    assert [t['level'] for t in trace] == ['wrong_person_s', 'blind_false_lock_s', 'follow_rate']


def test_level3_follow_tie_goes_to_simplicity():
    sel, trace, _ = pick(DEANCHOR=(30, 5, 0.700), DEANCHOR_HIST=(30, 5, 0.709), DEANCHOR_HIST_SUM=(30, 5, 0.705))
    assert sel == 'DEANCHOR' and trace[-1]['level'] == 'simplicity'
    sel, *_ = pick(DEANCHOR_HIST=(30, 5, 0.70), DEANCHOR_HIST_SUM=(30, 5, 0.70))
    assert sel == 'DEANCHOR_HIST'                   # simpler of the remaining two


def test_follow_difference_over_tolerance_wins():
    sel, *_ = pick(DEANCHOR=(30, 5, 0.70), DEANCHOR_HIST=(30, 5, 0.72))
    assert sel == 'DEANCHOR_HIST'


def test_levels_are_lexicographic_not_a_sum():
    sel, *_ = pick(DEANCHOR=(20.0, 99, 0.0), DEANCHOR_HIST=(25.0, 0, 1.0))
    assert sel == 'DEANCHOR'


# ---------------------------------------------------------------- GT isolation scan
def test_gt_violations_keys_and_prompt_text():
    clean = {'calls': [{'request': {'variable_text': 'NOW t=1.0s. DETECTIONS ...'}, 'reason': 'depth of field visibility is fine'}]}
    assert M.gt_violations(clean) == []                      # model free text is data, not scanned
    assert M.gt_violations({'rows': [{'x': {'gt_visible': []}}]}) == ['rows[0].x.gt_visible']
    assert M.gt_violations({'calls': [{'request': {'variable_text': 'hint gt_body_box=[1,2,3,4]'}}]})
    for key in FORBIDDEN_GT_FIELDS:
        assert M.gt_violations({'a': {key: 1}}), key


# ---------------------------------------------------------------- receipt and CLI
def estimate_files(tmp, deanchor=2.4, hist=2.6, summ=2.7, ao=6.0):
    arms = {n: {'estimate_upper_bound': {'est_total_usd': v}} for n, v in
            (('DEANCHOR', deanchor), ('DEANCHOR_HIST', hist), ('DEANCHOR_HIST_SUM', summ))}
    p = tmp / 'arms.json'
    p.write_text(json.dumps({'k': 3, 'cases': ['E6-S01'], 'arms': arms}))
    q = tmp / 'ao.txt'
    q.write_text(f'DRY_RUN E6-S01 {json.dumps({"est_total_usd": ao / 2})}\nDRY_RUN E6-S02 {json.dumps({"est_total_usd": ao / 2})}\nRUN x\n')
    return p, q


def fake_sources(monkeypatch, metrics_by_arm, tmp=None):
    per = {n: {c: per_case(*v[:3]) | {'wrong_person_s': v[0] / 3, 'false_lock_s': v[1] / 3} for c in M.DIAG_CASES}
           for n, v in metrics_by_arm.items()}
    files = {}
    for n in metrics_by_arm:
        f = (tmp or Path('/nonexistent')) / f'{n}.k1.json'
        if tmp:
            f.write_text(json.dumps({'arm': n, 'config': {'model': 'm', 'poll_s': 2.0}, 'prompt_extra_sha256': 'c' * 64}))
        files[str(f)] = 'f' * 64
    monkeypatch.setattr(M, 'score_sources', lambda sources, scorer: (per, files, 'b' * 64))


def run_select(tmp, extra=()):
    p, q = estimate_files(tmp)
    return M.main(['select', '--source', 'r', 'c', 'x', '--formal-estimate', str(p), '--ao-estimate', str(q), '--out', str(tmp / 'freeze'),
                   '--code-commit', SHA, *extra])


def test_select_writes_receipt_with_required_fields_and_no_gt(tmp_path, monkeypatch, capsys):
    fake_sources(monkeypatch, {'DEANCHOR': (30, 5, .6), 'DEANCHOR_HIST': (10, 5, .6), 'DEANCHOR_HIST_SUM': (20, 5, .6)}, tmp_path)
    assert run_select(tmp_path) == 0
    r = json.loads((tmp_path / 'freeze/BATCH3_FREEZE.json').read_text())
    M.validate_receipt(r)
    assert r['SELECTED_AGENT'] == 'DEANCHOR_HIST' and r['code_commit_sha'] == SHA and r['identity'] == 'UNCONFIRMED'
    assert r['prompt_and_config_sha256'] and 'params' in r and r['scorer_sha256'] == 'b' * 64
    est = r['formal_dry_run_estimate']
    assert est['AO_ORIG_usd'] == 6.0 and est['total_usd_upper_bound'] == round(2.4 + 2.6 + 6.0, 6)    # DEANCHOR + selected + AO_ORIG
    assert [t['level'] for t in r['levels']][0] == 'wrong_person_s'
    assert (tmp_path / 'freeze/MANIFEST.sha256').read_text().startswith(M.sha_bytes((tmp_path / 'freeze/BATCH3_FREEZE.json').read_bytes()))

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert not set(keys(r)) & FORBIDDEN_GT_FIELDS


def test_select_selected_deanchor_counts_once_in_estimate(tmp_path, monkeypatch):
    fake_sources(monkeypatch, {'DEANCHOR': (10, 5, .6), 'DEANCHOR_HIST': (30, 5, .6)}, tmp_path)
    assert run_select(tmp_path) == 0
    r = json.loads((tmp_path / 'freeze/BATCH3_FREEZE.json').read_text())
    assert r['SELECTED_AGENT'] == 'DEANCHOR' and r['formal_dry_run_estimate']['total_usd_upper_bound'] == round(2.4 + 6.0, 6)


def test_receipt_never_overwritten(tmp_path, monkeypatch):
    fake_sources(monkeypatch, {'DEANCHOR': (30, 5, .6)}, tmp_path)
    assert run_select(tmp_path) == 0
    before = (tmp_path / 'freeze/BATCH3_FREEZE.json').read_bytes()
    fake_sources(monkeypatch, {'DEANCHOR': (99, 9, .1), 'DEANCHOR_HIST': (1, 1, .9)}, tmp_path)
    assert run_select(tmp_path) == 2
    assert run_select(tmp_path, ['--skip-if-exists']) == 0
    assert (tmp_path / 'freeze/BATCH3_FREEZE.json').read_bytes() == before


def test_select_exits_nonzero_when_no_group_passes(tmp_path, monkeypatch):
    fake_sources(monkeypatch, {'DEANCHOR': (30, 5, .6)}, tmp_path)
    monkeypatch.setattr(M, 'eligibility', lambda m: ['FORMAT_RETURN_RATE:0.5>0.2'])
    assert run_select(tmp_path) == M.EXIT_NO_ELIGIBLE
    assert not (tmp_path / 'freeze/BATCH3_FREEZE.json').exists()


# ---------------------------------------------------------------- formal gate (prereg 7.1)
def receipt(selected='DEANCHOR_HIST'):
    return {'schema_version': M.SCHEMA, 'SELECTED_AGENT': selected, 'code_commit_sha': SHA, 'prompt_and_config_sha256': {},
            'params': {}, 'scorer_sha256': 'b' * 64, 'formal_dry_run_estimate': {'total_usd_upper_bound': 11.0}}


def test_gate_passes_within_caps_and_reports_groups():
    r = M.formal_gate(receipt(), {'AO_ORIG': 6.0, 'DEANCHOR': 2.4, 'DEANCHOR_HIST': 2.6})
    assert r['groups'] == ['AO_ORIG', 'DEANCHOR', 'DEANCHOR_HIST'] and r['formal_total_usd_upper_bound'] == 11.0
    assert r['cumulative_usd_upper_bound'] == round(38.17 + 11.0, 6)


def test_gate_formal_cap_45_boundary():                                      # D404: 32 -> 45
    assert M.FORMAL_CAP_USD == 45.0
    assert M.formal_gate(receipt('DEANCHOR'), {'AO_ORIG': 25.0, 'DEANCHOR': 20.0})['formal_total_usd_upper_bound'] == 45.0
    with pytest.raises(ValueError, match='FORMAL_OVER_CAP'):
        M.formal_gate(receipt('DEANCHOR'), {'AO_ORIG': 25.0, 'DEANCHOR': 20.01})
    # the observed E6 dry-run (AO_ORIG 8.68 + DEANCHOR 16.11 + HIST_SUM 18.95 = 43.74) now fits
    assert M.formal_gate(receipt('DEANCHOR_HIST_SUM'), {'AO_ORIG': 8.6829, 'DEANCHOR': 16.1064, 'DEANCHOR_HIST_SUM': 18.9532})['formal_total_usd_upper_bound'] == 43.7425


def test_gate_cumulative_cap_90_with_ledger():
    est = {'AO_ORIG': 6.0, 'DEANCHOR': 2.4}
    assert M.formal_gate(receipt('DEANCHOR'), est, new_ledger=43.43)['cumulative_usd_upper_bound'] == 90.0      # 38.17 + 43.43 + 8.4 = 90
    with pytest.raises(ValueError, match='CUMULATIVE_OVER_CAP'):
        M.formal_gate(receipt('DEANCHOR'), est, new_ledger=43.44)


def test_gate_requires_every_needed_estimate_and_valid_receipt():
    with pytest.raises(ValueError, match='FORMAL_ESTIMATE_MISSING:AO_ORIG'):
        M.formal_gate(receipt('DEANCHOR'), {'DEANCHOR': 2.0})
    with pytest.raises(ValueError, match='FORMAL_ESTIMATE_MISSING:DEANCHOR_HIST_SUM'):
        M.formal_gate(receipt('DEANCHOR_HIST_SUM'), {'AO_ORIG': 1, 'DEANCHOR': 1})
    bad = receipt() | {'SELECTED_AGENT': 'AO_ORIG'}
    with pytest.raises(ValueError, match='NOT_IN_POOL'):
        M.formal_gate(bad, {})
    with pytest.raises(ValueError, match='RECEIPT_MISSING'):
        M.validate_receipt({'schema_version': M.SCHEMA})


def test_gate_cli_missing_receipt_and_pass(tmp_path, capsys):
    assert M.main(['formal-gate', '--receipt', str(tmp_path / 'nope.json')]) == M.EXIT_GATE
    (tmp_path / 'r.json').write_text(json.dumps(receipt('DEANCHOR')))
    p, q = estimate_files(tmp_path)
    ledger = tmp_path / 'led'
    ledger.mkdir()
    (ledger / 'usage.jsonl').write_text(json.dumps({'est_cost_usd': 1.5}) + '\n' + json.dumps({'est_cost_usd': 9.0, 'outcome': 'DENIED'}) + '\n')
    assert M.main(['formal-gate', '--receipt', str(tmp_path / 'r.json'), '--arms-estimate', str(p), '--ao-estimate', str(q),
                   '--ledger', str(ledger)]) == 0
    assert '"new_ledger_usd": 1.5' in capsys.readouterr().out
    assert M.main(['formal-gate', '--receipt', str(tmp_path / 'r.json'), '--arms-estimate', str(p)]) == M.EXIT_GATE   # no AO_ORIG estimate


def test_e5_dryrun_total_parses_and_rejects_unknown_price():
    assert M.e5_dryrun_total('DRY_RUN a {"est_total_usd": 1.5}\nDRY_RUN b {"est_total_usd": 2.0}\n') == 3.5
    with pytest.raises(ValueError):
        M.e5_dryrun_total('DRY_RUN a {"est_total_usd": null}')
    with pytest.raises(ValueError):
        M.e5_dryrun_total('no lines')


# ---------------------------------------------------------------- P2: follow-rate tolerance boundary, ledger fail closed
def test_follow_difference_exactly_0_01_is_a_tie_and_just_over_wins():
    sel, trace, _ = pick(DEANCHOR=(30, 5, 0.70), DEANCHOR_HIST=(30, 5, 0.71))
    assert sel == 'DEANCHOR' and trace[-1]['level'] == 'simplicity'            # exactly 0.01 apart: tie -> simplest
    sel, *_ = pick(DEANCHOR=(30, 5, 0.70), DEANCHOR_HIST=(30, 5, 0.7101))
    assert sel == 'DEANCHOR_HIST'
    sel, *_ = pick(DEANCHOR=(30, 5, 0.6999), DEANCHOR_HIST=(30, 5, 0.7099))
    assert sel == 'DEANCHOR'


def test_ledger_required_fails_closed(tmp_path):
    with pytest.raises(ValueError, match='LEDGER_REQUIRED'):
        M.ledger_new_usd([], require=True)
    with pytest.raises(ValueError, match='LEDGER_REQUIRED'):
        M.ledger_new_usd([tmp_path / 'nope'], require=True)
    assert M.ledger_new_usd([tmp_path / 'nope']) == 0.0                         # dry-run style: tolerated
    (tmp_path / 'usage.jsonl').write_text('')
    assert M.ledger_new_usd([tmp_path], require=True) == 0.0                    # an existing empty ledger is a real 0


def test_gate_cli_require_ledger(tmp_path, capsys):
    (tmp_path / 'r.json').write_text(json.dumps(receipt('DEANCHOR')))
    p, q = estimate_files(tmp_path)
    base = ['formal-gate', '--receipt', str(tmp_path / 'r.json'), '--arms-estimate', str(p), '--ao-estimate', str(q)]
    assert M.main(base + ['--require-ledger']) == M.EXIT_GATE                   # no ledger at all
    assert M.main(base + ['--ledger', str(tmp_path / 'missing'), '--require-ledger']) == M.EXIT_GATE
    assert M.main(base + ['--ledger', str(tmp_path / 'missing')]) == 0           # dry-run style
    (tmp_path / 'usage.jsonl').write_text('')
    assert M.main(base + ['--ledger', str(tmp_path), '--require-ledger']) == 0


# ---------------------------------------------------------------- verify-freeze (D402 mechanical batch-3 gate) and budget-check
def frozen_world(tmp_path, monkeypatch, selected_metrics=None):
    """Select once (writes a real receipt) and return everything verify_freeze needs, with the same scored inputs."""
    metrics = selected_metrics or {'DEANCHOR': (30, 5, .6), 'DEANCHOR_HIST': (10, 5, .6), 'DEANCHOR_HIST_SUM': (20, 5, .6)}
    fake_sources(monkeypatch, metrics, tmp_path)
    assert run_select(tmp_path) == 0
    receipt = json.loads((tmp_path / 'freeze/BATCH3_FREEZE.json').read_text())
    per = {n: {c: per_case(*v[:3]) | {'wrong_person_s': v[0] / 3, 'false_lock_s': v[1] / 3} for c in M.DIAG_CASES} for n, v in metrics.items()}
    files = {str(tmp_path / f'{n}.k1.json'): 'f' * 64 for n in metrics}
    kw = dict(sources=[('r', 'c', 'x')], scorer=Path('s'), agent_estimates={'AO_ORIG': 6.0, 'DEANCHOR': 2.4, 'DEANCHOR_HIST': 2.6, 'DEANCHOR_HIST_SUM': 2.7},
              artifact_root=tmp_path, frozen_spec=tmp_path / 'spec.json', ledgers=[tmp_path], head=SHA, dirty=False, repo=ROOT,
              score_fn=lambda sources, scorer: (per, files, 'b' * 64), separation=lambda r, s: (True, 'PASS'))
    (tmp_path / 'usage.jsonl').write_text('')
    return receipt, kw, per


def test_verify_freeze_passes_when_everything_matches(tmp_path, monkeypatch):
    receipt, kw, _ = frozen_world(tmp_path, monkeypatch)
    r = M.verify_freeze(receipt, **kw)
    assert r['ok'] and all(c['ok'] for c in r['checks'].values()), r['checks']
    assert set(r['checks']) >= {'receipt_valid', 'selection_recomputed', 'metrics_equal', 'levels_equal', 'diagnostic_files_unchanged', 'scorer_sha',
                                'prompt_and_config_sha', 'commit_matches_head', 'formal_separation', 'formal_dry_run_le_45_and_cumulative_le_90'}
    assert r['gate']['groups'] == ['AO_ORIG', 'DEANCHOR', 'DEANCHOR_HIST'] and r['gate']['per_group_budget_usd']['AO_ORIG'] == 6.0


@pytest.mark.parametrize('field', ['SELECTED_AGENT', 'metrics', 'levels', 'scorer_sha256', 'diagnostic_run_files_sha256', 'prompt_and_config_sha256', 'code_commit_sha'])
def test_verify_freeze_fails_on_tampered_receipt_field(tmp_path, monkeypatch, field):
    receipt, kw, _ = frozen_world(tmp_path, monkeypatch)
    bad = json.loads(json.dumps(receipt))
    if field == 'SELECTED_AGENT':
        bad[field] = 'DEANCHOR'
    elif field == 'metrics':
        bad[field]['DEANCHOR']['wrong_person_s'] += 1
    elif field == 'levels':
        bad[field][0]['kept'] = ['DEANCHOR']
    elif field == 'prompt_and_config_sha256':
        bad[field][PINNED[0]] = '0' * 64
    elif field == 'code_commit_sha':
        bad[field] = 'c' * 40
    else:
        bad[field] = {'x': 'y'} if field.endswith('files_sha256') else 'e' * 64
    r = M.verify_freeze(bad, **kw)
    assert not r['ok']
    failing = {n for n, c in r['checks'].items() if not c['ok']}
    assert failing, field


def test_verify_freeze_detects_changed_scores_dirty_tree_separation_and_budget(tmp_path, monkeypatch):
    receipt, kw, per = frozen_world(tmp_path, monkeypatch)
    changed = json.loads(json.dumps(per))
    changed['DEANCHOR_HIST']['E3-A1']['wrong_person_s'] = 99.0
    r = M.verify_freeze(receipt, **(kw | {'score_fn': lambda s, sc: (changed, {k: 'f' * 64 for k in []}, 'b' * 64)}))
    assert not r['checks']['metrics_equal']['ok'] and not r['checks']['diagnostic_files_unchanged']['ok'] and not r['ok']
    assert not M.verify_freeze(receipt, **(kw | {'dirty': True}))['checks']['commit_matches_head']['ok']
    assert not M.verify_freeze(receipt, **(kw | {'separation': lambda r_, s_: (False, 'FORMAL_UNITS_BELOW_MIN')}))['checks']['formal_separation']['ok']
    big = kw['agent_estimates'] | {'AO_ORIG': 50.0}
    r = M.verify_freeze(receipt, **(kw | {'agent_estimates': big}))
    assert not r['checks']['formal_dry_run_le_45_and_cumulative_le_90']['ok'] and r['gate'] is None
    r = M.verify_freeze(receipt, **(kw | {'ledgers': [tmp_path / 'missing']}))
    assert 'LEDGER_REQUIRED' in r['checks']['formal_dry_run_le_45_and_cumulative_le_90']['detail']


def test_verify_freeze_runs_every_check_and_cli_exit_6(tmp_path, monkeypatch, capsys):
    receipt, kw, _ = frozen_world(tmp_path, monkeypatch)
    bad = dict(receipt, SELECTED_AGENT='DEANCHOR_HIST_SUM')
    r = M.verify_freeze(bad, **kw)
    assert len(r['checks']) >= 9 and not r['ok']                                   # no short-circuit: the record lists all
    # CLI: missing receipt -> exit 6 and a record
    rc = M.main(['verify-freeze', '--receipt', str(tmp_path / 'none.json'), '--source', 'r', 'c', 'x', '--artifact-root', str(tmp_path),
                 '--frozen-spec', str(tmp_path / 'spec.json')])
    assert rc == M.EXIT_BATCH3 == 6
    rec = json.loads((tmp_path / 'VERIFY_FREEZE.json').read_text())
    assert rec['ok'] is False and 'receipt_exists' in rec['checks']


def test_select_refuses_freezing_when_prompt_file_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(M, 'PROMPT_FILES', PINNED + ('src/amidst/live_mode/aopen/arms_does_not_exist.py',))
    fake_sources(monkeypatch, {'DEANCHOR': (30, 5, .6)}, tmp_path)
    assert run_select(tmp_path) == 2 and not (tmp_path / 'freeze/BATCH3_FREEZE.json').exists()


def test_budget_check_skips_when_cumulative_would_exceed_cap(tmp_path, capsys):
    est = tmp_path / 'e.json'
    est.write_text(json.dumps({'est_total_usd_upper_bound': 10.0}))
    led = tmp_path / 'led'
    led.mkdir()
    (led / 'usage.jsonl').write_text(json.dumps({'est_cost_usd': 41.45 - 38.17}) + '\n')
    base = ['budget-check', '--estimate', str(est), '--ledger', str(led)]
    assert M.main(base) == 0                                               # 38.17 + 3.28 + 10 = 51.45
    assert M.main(base + ['--cap', '51.44']) == M.EXIT_BUDGET_SKIP == 7
    assert 'BUDGET_SKIPPED' in capsys.readouterr().out
    assert M.main(['budget-check', '--estimate', str(est), '--ledger', str(tmp_path / 'nope')]) == M.EXIT_GATE      # missing ledger fails closed

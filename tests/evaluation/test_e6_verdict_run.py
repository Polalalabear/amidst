"""E6 verdict CLI plumbing (#721 G6, D402): synthetic GT files, fake per-run scoring. No model, network or real recording."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts' / 'evaluation'))
import e3_f4_score as F4  # noqa: E402
import e6_verdict_run as C  # noqa: E402

SEL = 'DEANCHOR_HIST'
REGIMES = ['VISIBLE', 'VISIBLE', 'FULL_BLIND', 'TRUE_DEPARTURE']
TICKS = [10, 110, 210, 310]
GOOD = {'DEANCHOR', SEL}


def build_world(tmp_path, bad_sha=False, status='FROZEN_PRE_SCORING_D399'):
    gt = tmp_path / 'gt'
    (gt / 'gt-boxes').mkdir(parents=True)
    cases = []
    for i in range(1, 13):
        cid = f'E6-S{i:02d}'
        raw = json.dumps({'actor_id': 'T', 'ticks': [], 'case': cid}).encode()
        (gt / 'gt-boxes' / f'{cid}.a-log.json').write_bytes(raw)
        cases.append({'case_id': cid, 'family_id': f'E6-F{i:02d}', 'gt_path': f'gt-boxes/{cid}.a-log.json',
                      'gt_sha256': '0' * 64 if bad_sha and i == 3 else hashlib.sha256(raw).hexdigest(),
                      'actual_decision_points': [{'dp_id': f'{cid}-DP{j + 1}', 'type': 'X', 'tick': TICKS[j], 'gt_regime': REGIMES[j]}
                                                 for j in range(4)]})
    spec = tmp_path / 'frozen.json'
    spec.write_text(json.dumps({'status': status, 'formal_cases': cases}))
    runs = {}
    for name, arm, k in (('b1', 'B1', 1), ('ao', 'AO', 3), ('arms', 'DEANCHOR', 3), ('arms', SEL, 3)):
        root = tmp_path / 'runs' / name
        for c in cases:
            (root / c['case_id']).mkdir(parents=True, exist_ok=True)
            for n in range(1, k + 1):
                doc = {'arm': arm, 'k': n, 'case_id': c['case_id'], 'rows': [], 'calls': []}
                (root / c['case_id'] / f'{arm}.k{n}.json').write_text(json.dumps(doc))
        runs[name] = root
    return spec, gt, [runs['b1'], runs['ao'], runs['arms']]


def fake_run_scores(S, case, a_log, doc):
    ok = doc['arm'] in GOOD
    classes = {}
    for k in range(0, 400):
        classes[k] = 'BLIND_OK'
    for t in (10, 110):
        for k in range(t, t + 15):
            classes[k] = 'CORRECT' if ok else 'WRONG_PERSON'
    for t in (210, 310):
        for k in range(t, t + 15):
            classes[k] = 'BLIND_OK' if ok else 'FALSE_LOCK'
    prim = {'available': True, 'wrong_person_s': 8.0 + doc['k'] if ok else 20.0, 'false_lock_s': 2.0, 'lost_s': 1.0,
            'follow_rate': 0.7 if ok else 0.6, 'visible_ticks': 100}
    return {'primary': prim, 'classes': classes, 'api_breakdown': {'calls': 10, 'error': 1 if doc['arm'] == 'DEANCHOR' else 0, 'timeout': 0,
                                                                    'budget_denied': 0}}


@pytest.fixture
def fake_scorer(monkeypatch):
    monkeypatch.setattr(F4, 'run_scores', fake_run_scores)


def argv(spec, gt, runs, out, *extra):
    return ['--frozen-spec', str(spec), '--gt-root', str(gt), '--runs', *map(str, runs), '--out', str(out), *extra]


def test_cli_end_to_end_with_fake_scoring(tmp_path, fake_scorer, capsys):
    spec, gt, runs = build_world(tmp_path)
    out = tmp_path / 'out'
    C.main(argv(spec, gt, runs, out, '--selected-agent', SEL))
    v = json.loads((out / 'verdict_e6.json').read_text())
    assert v['status'] == 'FORMAL' and v['M'] == 12 and v['N_dp'] == 48 and v['selected_agent'] == SEL
    assert v['hypotheses']['P1']['verdict'] == v['hypotheses']['P2']['verdict'] == 'SUPPORTED'
    assert v['groups']['AO_ORIG']['dp_n'] == 48 and v['groups']['AO_ORIG']['full_track_dp_acc'] == 0.0
    assert v['groups']['DEANCHOR']['full_track_dp_acc'] == 1.0
    assert v['groups']['DEANCHOR']['wrong_person_s'] == pytest.approx(12 * 10.0)                   # K=3 mean of 9, 10, 11 = 10 per family
    assert v['data_quality']['DEANCHOR']['runs'] == 36 and v['data_quality']['DEANCHOR']['provider_error_rate'] == 0.1
    assert v['scorer_sha256'] == F4.SCORER_SHA and len(v['frozen_spec_sha256']) == 64
    md = (out / 'VERDICT_E6.md').read_text()
    assert '# E6 verdict' in md and 'SUPPORTED' in md and 'DEANCHOR_HIST' in md
    inputs = json.loads((out / 'scored_inputs.json').read_text())
    assert all(p['single_correct'] is None for p in inputs['decision_points'])
    assert all(len(p['full_track_correct']) == (1 if p['group'] == 'B1' else 3) for p in inputs['decision_points'])
    for line in (out / 'MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ')
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert json.loads(capsys.readouterr().out)['verdicts'] == {'P1': 'SUPPORTED', 'P2': 'SUPPORTED'}
    with pytest.raises(SystemExit, match='OUTPUT_EXISTS'):
        C.main(argv(spec, gt, runs, out, '--selected-agent', SEL))


def test_selected_agent_from_receipt(tmp_path, fake_scorer):
    spec, gt, runs = build_world(tmp_path)
    receipt = tmp_path / 'BATCH3_FREEZE.json'
    receipt.write_text(json.dumps({'SELECTED_AGENT': SEL}))
    C.main(argv(spec, gt, runs, tmp_path / 'out', '--receipt', str(receipt)))
    assert json.loads((tmp_path / 'out' / 'verdict_e6.json').read_text())['selected_agent'] == SEL


def test_missing_runs_pin_mismatch_and_unfrozen_spec_stop(tmp_path, fake_scorer):
    spec, gt, runs = build_world(tmp_path)
    with pytest.raises(SystemExit, match='RUNS_MISSING E6-S01 DEANCHOR'):
        C.main(argv(spec, gt, runs[:2], tmp_path / 'o1', '--selected-agent', SEL))
    with pytest.raises(SystemExit):
        C.main(argv(spec, gt, runs, tmp_path / 'o2'))                                              # no selected agent
    spec2, gt2, runs2 = build_world(tmp_path / 'b', bad_sha=True)
    with pytest.raises(SystemExit, match='GT_PIN_MISMATCH E6-S03'):
        C.main(argv(spec2, gt2, runs2, tmp_path / 'o3', '--selected-agent', SEL))
    spec3, gt3, runs3 = build_world(tmp_path / 'c', status='DRAFT')
    with pytest.raises(SystemExit, match='FROZEN_SPEC_NOT_FROZEN'):
        C.main(argv(spec3, gt3, runs3, tmp_path / 'o4', '--selected-agent', SEL))
    assert not (tmp_path / 'o1').exists() and not (tmp_path / 'o3').exists()                       # nothing written when a stop happens


def test_window_is_fifteen_ticks_and_marks_displayed():
    classes = {k: 'BLIND_OK' for k in range(100)}
    classes[50] = 'FALSE_LOCK'
    classes[64] = 'FALSE_LOCK'
    classes[65] = 'FALSE_LOCK'                    # outside the 15-tick window starting at 50
    w = C.window_ticks(classes, 50)
    assert len(w) == 15 and w[0] == {'cls': 'FALSE_LOCK', 'displayed': True} and w[1]['displayed'] is False and w[14]['displayed'] is True
    assert len(C.window_ticks(classes, 95)) == 5          # clipped at the end of the log


def test_arm_names_map_to_groups(tmp_path):
    spec, gt, runs = build_world(tmp_path)
    got = C.collect_runs(runs, ['E6-S01'])
    assert set(got) == {('E6-S01', 'B1'), ('E6-S01', 'AO_ORIG'), ('E6-S01', 'DEANCHOR'), ('E6-S01', SEL)}
    assert [len(v) for k, v in sorted(got.items())] == [3, 3, 3, 1] or sorted(len(v) for v in got.values()) == [1, 3, 3, 3]

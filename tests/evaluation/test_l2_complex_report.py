"""評分端；與推論隔離。CQ-36-T synthetic aggregate checks and required native integration."""
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import check_l2_report as checker

FIXTURES = ROOT / 'tests/fixtures/l2_report/SYNTHETIC'


def paths(root, mode='RECOMMENDED'):
    return (root / f'report.{mode}.SYNTHETIC.json', root / 'inputs.SYNTHETIC.json', root / f'decisions.{mode}.SYNTHETIC.json')


def load(path):
    return json.loads(path.read_bytes())


def write(path, doc):
    path.write_bytes(checker.canonical(doc) + b'\n')


def projected(mode):
    _, receipt, decisions = paths(FIXTURES, mode)
    return checker.aggregate(receipt, decisions, synthetic_profile=checker.PROFILE)


@pytest.mark.parametrize('mode', ['PENDING', 'RECOMMENDED'])
def test_checker_positive_fixtures(mode):
    result = checker.check(*paths(FIXTURES, mode), synthetic_profile=checker.PROFILE)
    assert result['status'] == 'VALID_SYNTHETIC_PROJECTION'
    assert result['native_scorer_executed'] is result['human_approval_verified'] is False


def assert_pending(report):
    assert report['pending_event_count'] == 6
    assert set(report['metrics']) == {'COMPLETE/ALL', 'COMPLETE/STANDARD'}
    assert report['metrics']['COMPLETE/ALL']['matched'] == 1
    assert report['metrics']['COMPLETE/ALL']['total'] == 2
    assert report['metrics']['COMPLETE/ALL']['ratio'] == 0.5
    assert all(e['event_class'] == 'STANDARD' for e in report['events'] if e['matched'] is not None)
    assert all(e['bucket'].startswith('NOT_SCORED_PENDING_DECISION') for e in report['events'] if e['matched'] is None)


def assert_recommended(report):
    expected = {'COMPLETE/ALL': (3, 4, 0.75), 'COMPLETE/STANDARD': (1, 2, 0.5),
                'COMPLETE/LONG_GAP': (1, 1, 1.0), 'COMPLETE/LONG_LOSS': (1, 1, 1.0),
                'COMPLETE/OVERLAP_P_OV2_UNVERIFIED/ALL': (0, 1, 0.0),
                'MEASURED_PARTIAL_ENDED_BY_LIMIT/ALL': (1, 2, 0.5),
                'MEASURED_PARTIAL_ENDED_BY_LIMIT/OVERLAP_P_OV2_UNVERIFIED/ALL': (1, 1, 1.0)}
    for key, values in expected.items():
        row = report['metrics'][key]
        assert (row['matched'], row['total'], row['ratio']) == values
    assert report['pending_event_count'] == 0
    assert all('OVERLAP_P_OV2_UNVERIFIED' in e['bucket'] for e in report['events'] if e['entry_kind'] == 'OVERLAP')


def test_independent_counts_keep_overlap_and_partial_out_of_complete_main():
    assert_pending(projected('PENDING'))
    assert_recommended(projected('RECOMMENDED'))


def test_all_numbers_bound_to_exact_input_and_decision_bytes():
    a, b = projected('PENDING'), projected('RECOMMENDED')
    assert a['content_sha256'] != b['content_sha256']
    for report, mode in [(a, 'PENDING'), (b, 'RECOMMENDED')]:
        _, receipt, decisions = paths(FIXTURES, mode)
        p = report['provenance']
        assert p['inputs_sha256'] == checker.sha(receipt.read_bytes())
        assert p['decisions_sha256'] == checker.sha(decisions.read_bytes())
        assert all(m['provenance'] == p for m in report['metrics'].values())
        assert all(e['provenance'] == p for e in report['events'])
        assert report['content_sha256'] == checker.sha(checker.canonical({k:v for k,v in report.items() if k != 'content_sha256'}))


def test_rehashed_tampered_report_is_rejected():
    _, inputs, decisions = paths(FIXTURES)
    with pytest.raises(checker.CheckError, match='REPORT_RECOMPUTE_MISMATCH'):
        checker.check(FIXTURES / 'report.TAMPERED.SYNTHETIC.json', inputs, decisions, synthetic_profile=checker.PROFILE)


@pytest.mark.parametrize('mutation,reason', [('input', 'INPUT_PIN_MISMATCH'), ('decisions', 'REPORT_RECOMPUTE_MISMATCH'),
    ('symlink', 'REGULAR_CANONICAL_FILE_REQUIRED'), ('escape', 'INPUT_PATH_UNSAFE'),
    ('identity', 'FORBIDDEN_CLAIM'), ('navigation', 'FORBIDDEN_CLAIM'), ('extra', 'REPORT_RECOMPUTE_MISMATCH'),
    ('duplicate', 'DUPLICATE_JSON_KEY')])
def test_fail_closed_counterexamples(tmp_path, mutation, reason):
    root = tmp_path / 'SYNTHETIC'; shutil.copytree(FIXTURES, root)
    report, inputs, decisions = paths(root)
    if mutation == 'input':
        source = root / 'scored_events.SYNTHETIC.json'; source.write_bytes(source.read_bytes()+b' ')
    elif mutation == 'decisions':
        decisions.write_bytes(decisions.read_bytes()+b' ')
    elif mutation == 'symlink':
        source = root / 'script.SYNTHETIC.json'; original = root / 'saved.json'; source.rename(original); source.symlink_to(original)
    elif mutation == 'escape':
        doc = load(inputs); doc['files']['script']['path'] = '../escape.json'; write(inputs, doc)
    elif mutation == 'duplicate':
        report.write_bytes(b'{"fixture_role":1,"fixture_role":2}')
    else:
        doc = load(report); doc['claim'] = {'identity':'身分確認', 'navigation':'可通行', 'extra':'unexpected'}[mutation]; write(report, doc)
    with pytest.raises(checker.CheckError, match=reason):
        checker.check(report, inputs, decisions, synthetic_profile=checker.PROFILE)


def test_checker_default_never_interprets_production_wire():
    with pytest.raises(checker.CheckError, match='PRODUCTION_PROFILE_UNSELECTED'):
        checker.check(Path('missing'), Path('missing'), Path('missing'))


@pytest.mark.parametrize('mode,profile,code,status', [('RECOMMENDED',True,0,'VALID_SYNTHETIC_PROJECTION'), ('TAMPERED',True,1,'FAIL'), ('RECOMMENDED',False,1,'FAIL')])
def test_cli_positive_negative_and_default(mode, profile, code, status):
    report, inputs, decisions = paths(FIXTURES)
    report = report.with_name(f'report.{mode}.SYNTHETIC.json')
    args = [sys.executable, str(ROOT/'scripts/check_l2_report.py'), '--report', str(report), '--inputs', str(inputs), '--decisions', str(decisions)]
    if profile:
        args += ['--synthetic-profile', checker.PROFILE]
    run = subprocess.run(args, text=True, capture_output=True)
    assert run.returncode == code and json.loads(run.stdout)['status'] == status


def native(mode):
    module_name = os.environ.get('AMIDST_L2_REPORT_MODULE', 'amidst.evaluation.l2_complex_report')
    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ36_IMPLEMENTATION_MISSING')
        pytest.importorskip(module_name, reason='CQ36_IMPLEMENTATION_MISSING')
    implementation = importlib.import_module(module_name)
    selected = os.environ.get('AMIDST_L2_REPORT_DRIVER')
    if not selected:
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ36_TEST_DRIVER_UNBOUND')
        pytest.skip('CQ36_TEST_DRIVER_UNBOUND')
    driver = importlib.import_module(selected)
    _, inputs, decisions = paths(FIXTURES, mode)
    # No golden report enters the driver. It must exercise the native report/scorer path.
    path = Path(implementation.__file__).resolve(); invoked = []
    previous = sys.getprofile()
    def trace(frame, event, arg):
        if event == 'call' and Path(frame.f_code.co_filename).resolve() == path:
            invoked.append(frame.f_code.co_name)
    try:
        sys.setprofile(trace)
        result = driver.exercise_case(implementation=implementation, inputs_path=inputs, decisions_path=decisions)
    except (pytest.skip.Exception, pytest.xfail.Exception):
        if os.environ.get('AMIDST_REQUIRE_IMPL') == '1':
            pytest.fail('CQ36_REQUIRED_DRIVER_BINDING_MISSING')
        raise
    finally:
        sys.setprofile(previous)
    assert invoked and result['implementation_file_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result['human_approval_verified'] is False and result['native_scorer_executed'] is True
    assert isinstance(result['native_report'], dict)
    assert not any(w in json.dumps(result['native_report'], ensure_ascii=False) for w in ('身分確認','可通行'))
    return result


@pytest.mark.parametrize('mode', ['PENDING', 'RECOMMENDED'])
def test_native_report_respects_pending_overlap_and_limit(mode):
    result = native(mode)
    (assert_pending if mode == 'PENDING' else assert_recommended)(result['observations'])


def test_native_numbers_have_pins_and_settings_change_report_hash():
    a, b = native('PENDING'), native('RECOMMENDED')
    assert checker.sha(checker.canonical(a['native_report'])) != checker.sha(checker.canonical(b['native_report']))
    for result, mode in [(a,'PENDING'),(b,'RECOMMENDED')]:
        expected = projected(mode)['provenance']
        report = result['observations']
        assert report['provenance'] == expected
        assert all(row['provenance'] == expected for row in report['metrics'].values())


def test_native_synthetic_artifact_pins_and_journal_hashes():
    manifest = load(FIXTURES / 'native_inputs.SYNTHETIC.json')
    assert len(manifest['cases']) == 8
    for case in manifest['cases']:
        artifacts = case['artifacts']
        assert set(artifacts) == {'script','response','journal','parameters','plan'}
        docs = {}
        for kind, ref in artifacts.items():
            raw = (FIXTURES / ref['path']).read_bytes()
            assert checker.sha(raw) == ref['sha256'] == manifest['files'][ref['path']]
            if kind != 'journal':
                docs[kind] = json.loads(raw)
        script, response = docs['script'], docs['response']
        assert script['schema_version'] == 'q5-evaluation-script.v2'
        assert script['status'] == 'PROPOSED' and script['approval_ref'] is None
        assert script['events'][0]['event_id'] == case['event_id']
        assert script['plan_ref']['sha256'] == artifacts['plan']['sha256']
        assert script['parameter_binding']['parameter_set_sha256'] == docs['parameters']['content_sha256']
        assert response['decisions_sha256'] == artifacts['journal']['sha256']
        assert response['output_sha256'] == checker.sha(checker.canonical({k:v for k,v in response.items() if k not in {'output_sha256','stats'}}))
        rows = [json.loads(line) for line in (FIXTURES / artifacts['journal']['path']).read_bytes().splitlines()]
        assert [r['step_index'] for r in rows] == list(range(len(rows)))
        for row in rows:
            assert row['content_sha256'] == checker.sha(checker.canonical({k:v for k,v in row.items() if k not in {'content_sha256','stats'}}))

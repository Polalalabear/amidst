"""ARCH-T (#307): synthetic Git repos; no source assets or evaluation truth."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/check_architecture_guard.py'


def git(root, *args):
    return subprocess.check_output(
        ['git', '-C', str(root), '-c', 'user.name=SYNTHETIC',
         '-c', 'user.email=synthetic@example.invalid', *args], stderr=subprocess.PIPE,
    ).decode().strip()


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def commit(root):
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'SYNTHETIC checkpoint')
    return git(root, 'rev-parse', 'HEAD')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'SYNTHETIC'
    root.mkdir()
    git(root, 'init', '-q')
    write(root, 'AUTHORITY.md', 'SYNTHETIC authority\n')
    write(root, 'src/amidst/q1q5/example.py', 'VALUE = 1\n')
    base = commit(root)
    config = tmp_path / 'SYNTHETIC-policy'
    config.mkdir()
    (config / 'authority_pins_v1.json').write_text(json.dumps({
        'issue_ref': '#306', 'pins': [
            {'path': 'AUTHORITY.md', 'ref': base,
             'sha256': digest('SYNTHETIC authority\n'), 'status': 'SYNTHETIC'},
        ],
    }))
    (config / 'schema_registry_v1.json').write_text(json.dumps({
        'issue_ref': '#307', 'schemas': [
            {'value': 'synthetic.example.v1', 'source_paths': ['configs/example.json'],
             'issue_ref': '#307'},
        ],
    }))
    (config / 'inference_import_rules_v1.json').write_text(json.dumps({
        'issue_ref': '#307', 'baseline_ref': base,
        'python_roots': ['src/amidst/q1q5'], 'javascript_roots': ['frontend/workbench-v2'],
        'forbidden_import_prefixes': [
            'amidst.evaluation.q5_switch_eval', 'amidst.evaluation.q5_script_adapter',
        ],
        'forbidden_string_pattern': r'(?i)(?:ground_truth|gt_|visibility|depth|trajectory|renderer_track)',
        'baseline': [],
    }))
    return root, config, base


def run(repo, *args):
    root, config, base = repo
    assert SCRIPT.exists(), 'ARCH_IMPLEMENTATION_MISSING'
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--repo', str(root), '--base', base,
         '--config-dir', str(config), *args], capture_output=True, text=True,
    )
    assert result.returncode in {0, 1}, result.stderr
    return result, json.loads(result.stdout)


def finding_codes(report, check):
    return {hit['code'] for hit in report['checks'][check]['findings']}


def edit_policy(repo, name, change):
    path = repo[1] / name
    doc = json.loads(path.read_text())
    change(doc)
    path.write_text(json.dumps(doc))


def test_synthetic_baseline_passes_and_writes_report(repo, tmp_path):
    output = tmp_path / 'report.json'
    result, report = run(repo, '--report', str(output))
    assert result.returncode == 0 and report['status'] == 'PASS'
    assert set(report['checks']) == {'authority', 'inference', 'schemas'}
    assert all(check['status'] == 'PASS' for check in report['checks'].values())
    assert json.loads(output.read_bytes()) == report


def test_changed_authority_and_unknown_bytes_fail(repo):
    write(repo[0], 'AUTHORITY.md', 'SYNTHETIC changed\n')
    commit(repo[0])
    result, report = run(repo)
    assert result.returncode == 1
    assert finding_codes(report, 'authority') == {'AUTHORITY_CHANGED', 'AUTHORITY_DRIFT'}


def test_recognized_authority_bytes_still_need_explicit_allow(repo):
    value = 'SYNTHETIC approved alternative\n'
    edit_policy(repo, 'authority_pins_v1.json', lambda d: d['pins'].append({
        'path': 'AUTHORITY.md', 'ref': '#306 SYNTHETIC alternative',
        'sha256': digest(value), 'status': 'SYNTHETIC',
    }))
    write(repo[0], 'AUTHORITY.md', value)
    commit(repo[0])
    result, report = run(repo)
    assert result.returncode == 1
    assert finding_codes(report, 'authority') == {'AUTHORITY_CHANGED'}
    result, report = run(repo, '--allow', 'AUTHORITY.md')
    assert result.returncode == 0 and report['checks']['authority']['allowed_changes'] == ['AUTHORITY.md']


def test_allow_does_not_hide_unknown_authority_bytes(repo):
    write(repo[0], 'AUTHORITY.md', 'SYNTHETIC unrecognized\n')
    commit(repo[0])
    result, report = run(repo, '--allow', 'AUTHORITY.md')
    assert result.returncode == 1
    assert finding_codes(report, 'authority') == {'AUTHORITY_DRIFT'}


def test_commit_bound_exception_does_not_widen_baseline_pin(repo):
    root = repo[0]
    git(root, 'checkout', '-qb', 'synthetic-exception')
    replacement = 'SYNTHETIC bounded exception\n'
    write(root, 'AUTHORITY.md', replacement)
    future = commit(root)
    git(root, 'checkout', '-q', repo[2])
    def modify(doc):
        doc['pins'][0]['superseded_by_commit'] = future
        doc['pins'].append({'path': 'AUTHORITY.md', 'ref': '#306 SYNTHETIC exception',
                            'sha256': digest(replacement), 'status': 'SYNTHETIC',
                            'requires_commit': future})
    edit_policy(repo, 'authority_pins_v1.json', modify)
    assert run(repo)[0].returncode == 0
    # Copying future bytes before the designated commit is present does not authorize them.
    write(root, 'AUTHORITY.md', replacement)
    assert run(repo)[0].returncode == 1
    write(root, 'AUTHORITY.md', 'SYNTHETIC authority\n')
    git(root, 'checkout', '-q', future)
    assert run(repo, '--allow', 'AUTHORITY.md')[0].returncode == 0
    # After the designated exception lands, the old bytes are no longer accepted.
    write(root, 'AUTHORITY.md', 'SYNTHETIC authority\n')
    assert run(repo, '--allow', 'AUTHORITY.md')[0].returncode == 1


def test_uncommitted_authority_drift_is_detected(repo):
    write(repo[0], 'AUTHORITY.md', 'SYNTHETIC dirty\n')
    result, report = run(repo)
    assert result.returncode == 1
    assert finding_codes(report, 'authority') == {'AUTHORITY_DRIFT'}


def historical_policy(repo, retired=None):
    def modify(doc):
        doc['pins'][0]['sha256'] = digest('SYNTHETIC rc5\n')
        old = {'path': 'AUTHORITY.md', 'ref': repo[2], 'status': 'SYNTHETIC historical',
               'sha256': digest('SYNTHETIC authority\n'), 'unchanged_since_commit': repo[2]}
        if retired:
            old['superseded_by_commit'] = retired
        doc['pins'].append(old)
    edit_policy(repo, 'authority_pins_v1.json', modify)


def test_historical_pin_accepts_only_unchanged_path(repo):
    historical_policy(repo)
    assert run(repo)[0].returncode == 0
    write(repo[0], 'AUTHORITY.md', 'SYNTHETIC changed HEAD\n')
    commit(repo[0])
    # A dirty restoration cannot revive a historical pin after HEAD changed it.
    write(repo[0], 'AUTHORITY.md', 'SYNTHETIC authority\n')
    result, report = run(repo, '--allow', 'AUTHORITY.md')
    assert result.returncode == 1
    assert finding_codes(report, 'authority') == {'AUTHORITY_DRIFT'}


def test_historical_pin_retires_when_designated_commit_enters_history(repo):
    git(repo[0], 'checkout', '-qb', 'SYNTHETIC-rc5')
    write(repo[0], 'OTHER.txt', 'SYNTHETIC designated kit commit\n')
    future = commit(repo[0])
    git(repo[0], 'checkout', '-q', repo[2])
    historical_policy(repo, retired=future)
    assert run(repo)[0].returncode == 0
    git(repo[0], 'checkout', '-q', future)
    result, report = run(repo)
    assert result.returncode == 1
    assert finding_codes(report, 'authority') == {'AUTHORITY_DRIFT'}
    write(repo[0], 'AUTHORITY.md', 'SYNTHETIC rc5\n')
    commit(repo[0])
    assert run(repo, '--allow', 'AUTHORITY.md')[0].returncode == 0


def test_missing_historical_baseline_fails_closed(repo):
    historical_policy(repo)
    edit_policy(repo, 'authority_pins_v1.json', lambda d: d['pins'][-1].update(
        unchanged_since_commit='1' * 40))
    assert run(repo)[0].returncode == 1


def test_deleted_authority_cannot_evade_protection(repo):
    (repo[0] / 'AUTHORITY.md').unlink()
    commit(repo[0])
    result, report = run(repo)
    assert result.returncode == 1 and 'AUTHORITY_CHANGED' in finding_codes(report, 'authority')


def test_pin_for_symlink_uses_link_bytes_without_reading_target(repo, tmp_path):
    outside = tmp_path / 'SYNTHETIC-target.md'
    outside.write_text('SYNTHETIC mutable content\n')
    link = repo[0] / 'RULE.md'
    link.symlink_to(outside)
    edit_policy(repo, 'authority_pins_v1.json', lambda d: d['pins'].append({
        'path': 'RULE.md', 'ref': '#306 SYNTHETIC symlink',
        'sha256': digest(str(outside)), 'status': 'SYNTHETIC',
    }))
    assert run(repo)[0].returncode == 0
    outside.write_text('SYNTHETIC changed target\n')
    assert run(repo)[0].returncode == 0


@pytest.mark.parametrize('source', [
    'import amidst.evaluation.q5_switch_eval as scoring\n',
    'from amidst.evaluation.q5_script_adapter import adapt\n',
    'from amidst.evaluation import q5_switch_eval_v2\n',
    'from ..evaluation import q5_script_adapter\n',
    'import importlib\nscoring = importlib.import_module("amidst.evaluation.q5_switch_eval")\n',
])
def test_forbidden_inference_imports_fail(repo, source):
    write(repo[0], 'src/amidst/q1q5/example.py', source)
    result, report = run(repo)
    assert result.returncode == 1
    assert 'FORBIDDEN_IMPORT' in finding_codes(report, 'inference')


@pytest.mark.parametrize('literal', ['ground_truth.json', 'gt_tracks.json', 'visibility', 'depth_map', 'trajectory', 'renderer_track'])
def test_new_python_forbidden_literal_fails(repo, literal):
    write(repo[0], 'src/amidst/q1q5/example.py', f'VALUE = {literal!r}\n')
    result, report = run(repo)
    assert result.returncode == 1
    assert 'FORBIDDEN_STRING' in finding_codes(report, 'inference')


def test_existing_finding_is_bounded_by_exact_signature_and_count(repo):
    source = 'VALUE = "visibility"\n'
    write(repo[0], 'src/amidst/q1q5/example.py', source)
    edit_policy(repo, 'inference_import_rules_v1.json', lambda d: d['baseline'].append({
        'path': 'src/amidst/q1q5/example.py', 'kind': 'python_string',
        'sha256': digest('python_string\0visibility'), 'count': 1,
        'reason': 'SYNTHETIC existing at the frozen baseline; no new occurrence authorized',
    }))
    assert run(repo)[0].returncode == 0
    write(repo[0], 'src/amidst/q1q5/example.py', '\n\n' + source)
    assert run(repo)[0].returncode == 0
    write(repo[0], 'src/amidst/q1q5/example.py', source + 'OTHER = "visibility"\n')
    result, report = run(repo)
    assert result.returncode == 1
    assert 'FORBIDDEN_STRING' in finding_codes(report, 'inference')


def test_new_javascript_hit_fails(repo):
    write(repo[0], 'frontend/workbench-v2/example.mjs', 'const x = response.depth;\n')
    result, report = run(repo)
    assert result.returncode == 1
    assert 'FORBIDDEN_STRING' in finding_codes(report, 'inference')


def test_python_syntax_error_fails_closed(repo):
    write(repo[0], 'src/amidst/q1q5/example.py', 'def invalid(:\n')
    result, report = run(repo)
    assert result.returncode == 1
    assert 'INFERENCE_PARSE_ERROR' in finding_codes(report, 'inference')


@pytest.mark.parametrize('path, source', [
    ('configs/example.json', '{"schema_version":"synthetic.new.v1"}\n'),
    ('src/module.py', 'SCHEMA_VERSION = "synthetic.new.v1"\n'),
    ('frontend/workbench-v2/example.mjs', 'const x = {schema_version: "synthetic.new.v1"};\n'),
    ('docs/contracts/SYNTHETIC.md', '{"schema_version":"synthetic.new.v1"}\n'),
])
def test_new_schema_literal_requires_registry(repo, path, source):
    write(repo[0], path, source)
    result, report = run(repo)
    assert result.returncode == 1
    assert 'SCHEMA_UNREGISTERED' in finding_codes(report, 'schemas')


def test_registered_schema_passes_without_granting_approval(repo):
    write(repo[0], 'configs/example.json', '{"schema_version":"synthetic.example.v1"}\n')
    assert run(repo)[0].returncode == 0


def test_new_registry_entry_needs_issue_ref(repo):
    edit_policy(repo, 'schema_registry_v1.json', lambda d: d['schemas'].append({
        'value': 'synthetic.new.v1', 'source_paths': ['configs/new.json'],
    }))
    result, report = run(repo)
    assert result.returncode == 1
    assert 'REGISTRY_ENTRY_INVALID' in finding_codes(report, 'schemas')


def test_symlink_source_is_not_scanned_outside_repo(repo, tmp_path):
    outside = tmp_path / 'SYNTHETIC-outside.py'
    outside.write_text('VALUE = "ground_truth"\n')
    (repo[0] / 'src/amidst/q1q5/linked.py').symlink_to(outside)
    result, report = run(repo)
    assert result.returncode == 1
    assert 'INFERENCE_SYMLINK' in finding_codes(report, 'inference')


def test_invalid_base_or_policy_never_returns_pass(repo):
    result, report = run(repo, '--base', 'SYNTHETIC-nonexistent-ref')
    assert result.returncode == 1 and report['status'] == 'FAIL'
    (repo[1] / 'authority_pins_v1.json').write_text('{')
    result, report = run(repo)
    assert result.returncode == 1 and report['status'] == 'FAIL'

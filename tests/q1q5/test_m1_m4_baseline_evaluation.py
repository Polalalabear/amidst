"""Pure synthetic boundary checks for #425; no repository data-pack access."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.research.experiment_env as env_mod
import scripts.research.run_m1_m4_baseline_evaluation as runner


def synthetic_pack(tmp_path: Path) -> dict:
    """Small metadata-only fixture, with no real pack path or payload."""
    marker = tmp_path / 'synthetic-fixture.json'
    marker.write_text('{"source_class":"SYNTHETIC"}\n')
    return {'pack_id': 'SYNTHETIC_ONLY', 'role': 'SYNTHETIC_FIXTURE',
            'locator': marker.name, 'manifest_sha256': runner.sha256_file(marker),
            'file_count': 1, 'total_bytes': marker.stat().st_size,
            'formal_eligible': False, 'gt_read': False, 'source_class': 'SYNTHETIC'}


def test_real_pack_verification_is_not_implemented_and_does_not_read(tmp_path):
    pack = tmp_path / 'p1-v4-stripped'
    pack.mkdir()
    (pack / 'SAFE_PACK_MANIFEST.json').write_text('{}')
    with pytest.raises(RuntimeError, match='SAFE_PACK_VERIFICATION_NOT_IMPLEMENTED:NOT_RUN'):
        runner.verify_safe_packs(tmp_path)


def test_synthetic_environment_is_valid_but_gt_scan_not_run(tmp_path):
    manifest, env_sha = runner.generate_environment_manifest(safe_packs=[synthetic_pack(tmp_path)])
    assert manifest['source_class'] == 'SYNTHETIC'
    assert manifest['gt_isolation']['gt_path_scan'] == 'NOT_RUN'
    assert manifest['models']['llm']['llm_digest'] == 'UNKNOWN'
    assert manifest['models']['llm']['ollama_version'] == 'UNKNOWN'
    assert manifest['models']['detector']['detector_weights_sha256'] == 'UNKNOWN'
    assert env_mod.validate(manifest) == []
    assert env_mod.canonical_sha256(manifest) == env_sha
    with pytest.raises(ValueError, match='SYNTHETIC_MANIFEST_REQUIRES_SYNTHETIC_INPUTS'):
        runner.generate_environment_manifest(safe_packs=[{'source_class': 'ENGINEERING'}])
    with pytest.raises(ValueError, match='SYNTHETIC_MANIFEST_REQUIRES_SYNTHETIC_INPUTS'):
        runner.generate_environment_manifest(source_class='ENGINEERING', safe_packs=[])


def test_fixed_numbers_are_only_synthetic_fixture(tmp_path):
    pack = synthetic_pack(tmp_path)
    _, env_sha = runner.generate_environment_manifest(safe_packs=[pack])
    result = runner.generate_synthetic_fixture([pack], env_sha)
    assert result['source_class'] == 'SYNTHETIC'
    assert result['data_nature'] == 'SYNTHETIC_TEST_FIXTURE'
    assert set(result['evaluations']) == {'RULE_ONLY', 'M1', 'M2', 'M3', 'M4'}
    assert result['evaluations']['RULE_ONLY']['status'] == 'SYNTHETIC_FIXTURE_VALIDATED'
    assert result['evaluations']['RULE_ONLY']['gates']['GT_isolation'] == 'NOT_RUN'
    assert result['evaluations']['M4']['gates']['resource_efficiency'] == 'NOT_RUN'
    assert result == runner.generate_synthetic_fixture([pack], env_sha)


def test_synthetic_fixture_rejects_engineering_and_unpinned_inputs(tmp_path):
    pack = synthetic_pack(tmp_path)
    _, env_sha = runner.generate_environment_manifest(safe_packs=[pack])
    with pytest.raises(ValueError, match='SYNTHETIC_FIXTURE_REQUIRES_SYNTHETIC_INPUTS'):
        runner.generate_synthetic_fixture([{**pack, 'source_class': 'ENGINEERING'}], env_sha)
    with pytest.raises(ValueError, match='SYNTHETIC_FIXTURE_ENV_SHA_INVALID'):
        runner.generate_synthetic_fixture([pack], 'synthetic-not-a-sha')
    with pytest.raises(RuntimeError, match='REAL_M1_M4_EVALUATION_NOT_RUN'):
        runner.evaluate_baseline_and_models([pack], env_sha)
    with pytest.raises(RuntimeError, match='LEGACY_M1_M4_REPORT_UNVERIFIED:NOT_RUN'):
        runner.generate_analysis_report_markdown()


def test_committed_results_are_explicitly_synthetic():
    path = Path(__file__).resolve().parents[2] / 'docs/evaluation/M1_M4_BASELINE_RAW_RESULTS_20261104.json'
    result = json.loads(path.read_text())
    assert result['source_class'] == 'SYNTHETIC'
    assert result['data_nature'] == 'SYNTHETIC_TEST_FIXTURE'
    assert result['empirical_benchmark'] is False


def test_cli_requires_synthetic_mode_and_separates_file_and_content_hash(tmp_path):
    output = tmp_path / 'fixture-output'
    with pytest.raises(SystemExit) as exc:
        runner.main(['--out-dir', str(output)])
    assert exc.value.code == 2 and not output.exists()
    assert runner.main(['--synthetic-fixture', '--out-dir', str(output)]) == 0
    env_file = output / 'M1_M4_BASELINE_ENV_MANIFEST_20261104.json'
    env = json.loads(env_file.read_text())
    report = (output / 'M1_M4_BASELINE_ANALYSIS_REPORT_20261104.md').read_text()
    assert env['gt_isolation']['gt_path_scan'] == 'NOT_RUN'
    assert f'Environment canonical SHA-256: `{env_mod.canonical_sha256(env)}`' in report
    assert f'Environment file SHA-256: `{runner.sha256_file(env_file)}`' in report
    assert 'real evaluation: NOT_RUN' in report
    assert 'Table and chart generation: NOT_RUN' in report

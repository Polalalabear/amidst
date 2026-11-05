"""Automated tests for W-A6 Colab one-click notebook (#424) and colab_oneclick_runner."""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / 'scripts/research') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scripts/research'))
if str(REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'src'))

import colab_oneclick_runner as runner  # noqa: E402
import experiment_env as env_mod  # noqa: E402

NOTEBOOK_PATH = REPO_ROOT / 'notebooks/amidst_q1q5_colab_oneclick.ipynb'
RUN_LOG_PATH = REPO_ROOT / 'docs/operations/COLAB_ONECLICK_RUN_LOG_20261104.md'
CJK_PATTERN = re.compile(r'[\u4e00-\u9fff]')


def _load_notebook() -> dict:
    assert NOTEBOOK_PATH.is_file(), f'Notebook missing at {NOTEBOOK_PATH}'
    return json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8'))


def test_notebook_is_valid_nbformat_v4_with_chinese_comments_and_outputs():
    nb = _load_notebook()
    assert nb.get('nbformat') == 4
    assert isinstance(nb.get('nbformat_minor'), int) and nb['nbformat_minor'] >= 0
    cells = nb.get('cells', [])
    assert len(cells) >= 10

    code_cells = [c for c in cells if c.get('cell_type') == 'code']
    md_cells = [c for c in cells if c.get('cell_type') == 'markdown']
    assert len(code_cells) == 5
    assert len(md_cells) >= 5

    for idx, cell in enumerate(code_cells, 1):
        source_text = ''.join(cell.get('source', []))
        comment_lines = [line for line in source_text.splitlines() if line.strip().startswith('#')]
        assert comment_lines, f'Code cell {idx} has no comment lines'
        assert any(CJK_PATTERN.search(line) for line in comment_lines), (
            f'Code cell {idx} must include Traditional Chinese explanatory comments'
        )
        assert cell.get('execution_count') == idx
        outputs = cell.get('outputs', [])
        assert outputs, f'Code cell {idx} must have populated execution outputs'
        stdout_text = ''.join(outputs[0].get('text', []))
        parsed = json.loads(stdout_text)
        assert isinstance(parsed, dict)

    for idx, cell in enumerate(md_cells, 1):
        md_text = ''.join(cell.get('source', []))
        assert CJK_PATTERN.search(md_text), f'Markdown cell {idx} must contain Traditional Chinese explanation'


def test_environment_inspection_validates_against_experiment_env_v1():
    rep = runner.inspect_environment(deterministic=True)
    manifest = rep['env_manifest']
    assert manifest['schema_version'] == 'amidst.experiment-env.v1'
    assert rep['validation_errors'] == []
    assert env_mod.validate(manifest) == []
    assert len(rep['env_manifest_sha256']) == 64
    assert manifest['gt_isolation']['inference_read_gt'] is False
    assert manifest['source_class'] == 'SYNTHETIC'


def test_api_key_check_never_prints_or_logs_secret_values(capsys):
    fake_openai = 'sk-proj-SUPER-SECRET-VALUE-999999'
    fake_gemini = 'AIzaSy-SUPER-SECRET-GEMINI-888888'
    rep = runner.check_api_keys(
        env_mapping={
            'OPENAI_API_KEY': fake_openai,
            'ANTHROPIC_API_KEY': '   ',
        },
        userdata_getter=lambda name: fake_gemini if name == 'GEMINI_API_KEY' else None,
    )
    captured = capsys.readouterr()
    serialized = json.dumps(rep, ensure_ascii=False)
    nb_raw = NOTEBOOK_PATH.read_text(encoding='utf-8')

    assert fake_openai not in serialized
    assert fake_gemini not in serialized
    assert fake_openai not in captured.out and fake_openai not in captured.err
    assert fake_gemini not in captured.out and fake_gemini not in captured.err
    assert 'sk-' not in nb_raw and 'AIza' not in nb_raw

    assert rep['keys_status'] == {
        'OPENAI_API_KEY': 'PRESENT',
        'GEMINI_API_KEY': 'PRESENT',
        'ANTHROPIC_API_KEY': 'MISSING',
        'OLLAMA_HOST': 'MISSING',
    }
    assert rep['any_key_present'] is True
    assert rep['secret_values_logged'] is False


def test_data_pack_sha256_verification_and_gt_private_rejection(tmp_path):
    # 1. Missing real pack falls back to SYNTHETIC and marks real_data_status UNKNOWN
    fallback = runner.verify_data_pack(
        pack_dir=tmp_path / 'nonexistent_wc5_pack',
        allow_synthetic_fallback=True,
    )
    assert fallback['real_data_status'] == 'UNKNOWN'
    assert fallback['active_data_mode'] == 'SYNTHETIC'
    assert fallback['source_class'] == 'SYNTHETIC'
    assert fallback['gt_path_scan'] == 'PASS'
    assert fallback['sha256_verified'] is True
    assert len(fallback['files_verified']) == 6

    # 2. Valid pack with matching MANIFEST.json SHA-256 passes
    valid_pack = tmp_path / 'valid_wc5_pack'
    valid_pack.mkdir()
    sample_file = valid_pack / 'observations.json'
    sample_bytes = b'{"source_class": "ENGINEERING", "items": [1, 2, 3]}\n'
    sample_file.write_bytes(sample_bytes)
    sample_sha = runner.sha256_bytes(sample_bytes)
    (valid_pack / 'MANIFEST.json').write_text(
        json.dumps({'files': [{'path': 'observations.json', 'sha256': sample_sha}]}),
        encoding='utf-8',
    )
    verified = runner.verify_data_pack(pack_dir=valid_pack, allow_synthetic_fallback=False)
    assert verified['real_data_status'] == 'VERIFIED'
    assert verified['active_data_mode'] == 'REAL_WC5_PACK'
    assert verified['sha256_verified'] is True
    assert verified['gt_path_scan'] == 'PASS'

    # 3. Corrupted file / SHA-256 mismatch is rejected
    sample_file.write_bytes(b'{"corrupted": true}\n')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        runner.verify_data_pack(pack_dir=valid_pack, allow_synthetic_fallback=False)

    # 4. Pack containing gt_private directory or file is strictly rejected
    bad_pack = tmp_path / 'bad_gt_pack'
    (bad_pack / 'gt_private').mkdir(parents=True)
    (bad_pack / 'gt_private/secret_tracks.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match=r'gt_private|Forbidden GT'):
        runner.verify_data_pack(pack_dir=bad_pack, allow_synthetic_fallback=False)

    # 5. Path traversal attack via expected_hashes or MANIFEST is rejected
    outside_canary = tmp_path / 'outside_canary.txt'
    outside_canary.write_text('canary', encoding='utf-8')
    outside_sha = runner.sha256_file(outside_canary)
    with pytest.raises(ValueError, match=r"Path traversal|\.\."):
        runner.verify_data_pack(
            pack_dir=valid_pack,
            expected_hashes={'../outside_canary.txt': outside_sha},
            allow_synthetic_fallback=False,
        )

    # 6. Symlink inside pack targeting an outside canary is rejected
    symlink_pack = tmp_path / 'symlink_pack'
    symlink_pack.mkdir()
    try:
        os.symlink(outside_canary, symlink_pack / 'alias.txt')
        symlink_supported = True
    except OSError:
        symlink_supported = False

    if symlink_supported:
        with pytest.raises(ValueError, match=r"[Ss]ymlink"):
            runner.verify_data_pack(
                pack_dir=symlink_pack,
                expected_hashes={'alias.txt': outside_sha},
                allow_synthetic_fallback=False,
            )

    # 7. Absolute paths are rejected
    with pytest.raises(ValueError, match=r"[Aa]bsolute path"):
        runner.verify_data_pack(
            pack_dir=valid_pack,
            expected_hashes={'/etc/passwd': '0' * 64},
            allow_synthetic_fallback=False,
        )

    # 8. Disallowed file extension is rejected
    with pytest.raises(ValueError, match=r"[Dd]isallowed file suffix"):
        runner.verify_data_pack(
            pack_dir=valid_pack,
            expected_hashes={'malicious.exe': '0' * 64},
            allow_synthetic_fallback=False,
        )


def test_synthetic_results_never_upgraded_by_verified_dummy_pack(tmp_path):
    # Dummy pack containing only dummy.txt
    dummy_pack = tmp_path / 'dummy_pack'
    dummy_pack.mkdir()
    dummy_file = dummy_pack / 'dummy.txt'
    dummy_bytes = b'dummy payload\n'
    dummy_file.write_bytes(dummy_bytes)
    dummy_sha = runner.sha256_bytes(dummy_bytes)
    (dummy_pack / 'MANIFEST.json').write_text(
        json.dumps({'files': [{'path': 'dummy.txt', 'sha256': dummy_sha}]}),
        encoding='utf-8',
    )
    verified_pack = runner.verify_data_pack(pack_dir=dummy_pack, allow_synthetic_fallback=False)
    assert verified_pack['real_data_status'] == 'VERIFIED'
    assert verified_pack['sha256_verified'] is True

    # Even with a VERIFIED data pack on disk, export_analysis_bundle on fixtures remains SYNTHETIC and UNKNOWN
    env_rep = runner.inspect_environment(deterministic=True)
    cp_rep = runner.run_checkpointed_experiments(
        tmp_path / 'checkpoints/cp.jsonl',
        config_sha256=env_rep['env_manifest']['parameter_set']['parameter_set_sha256'],
        max_units_to_run=10,
    )
    export_rep = runner.export_analysis_bundle(
        tmp_path / 'exports',
        env_manifest=env_rep['env_manifest'],
        env_manifest_sha256=env_rep['env_manifest_sha256'],
        data_pack_report=verified_pack,
        checkpoint_report=cp_rep,
        bootstrap_b=50,
    )

    assert export_rep['source_class'] == 'SYNTHETIC'
    assert export_rep['real_data_status'] == 'UNKNOWN'
    assert export_rep['real_data_adapter_status'] == 'NOT_IMPLEMENTED'
    for row in export_rep['summary_rows']:
        assert row['source_class'] == 'SYNTHETIC'
        assert row['real_data_status'] == 'UNKNOWN'

    manifest_path = Path(export_rep['export_manifest_path'])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['source_class'] == 'SYNTHETIC'
    assert manifest['real_data_status'] == 'UNKNOWN'
    assert manifest['real_data_adapter_status'] == 'NOT_IMPLEMENTED'


def test_checkpoint_resume_skips_completed_units_and_recomputes_on_config_change(tmp_path):
    cp_path = tmp_path / 'checkpoints/experiment_checkpoint.jsonl'
    cfg_a = 'aaaa' * 16
    cfg_b = 'bbbb' * 16

    # Step 1: Run first 10 units and interrupt
    part1 = runner.run_checkpointed_experiments(cp_path, config_sha256=cfg_a, max_units_to_run=10)
    assert part1['interrupted'] is True
    assert part1['executed_now'] == 10
    assert part1['skipped_from_checkpoint'] == 0
    assert part1['completed_total'] == 10

    # Step 2: Resume next 15 units; first 10 must be skipped
    part2 = runner.run_checkpointed_experiments(cp_path, config_sha256=cfg_a, max_units_to_run=15)
    assert part2['interrupted'] is True
    assert part2['skipped_from_checkpoint'] == 10
    assert part2['executed_now'] == 15
    assert part2['completed_total'] == 25

    # Step 3: Resume to completion; first 25 must be skipped
    full = runner.run_checkpointed_experiments(cp_path, config_sha256=cfg_a, max_units_to_run=None)
    assert full['interrupted'] is False
    assert full['skipped_from_checkpoint'] == 25
    assert full['executed_now'] == full['total_units'] - 25
    assert full['completed_total'] == full['total_units'] == 251

    # Step 4: Re-running completed checkpoint skips 100% of units
    rerun = runner.run_checkpointed_experiments(cp_path, config_sha256=cfg_a, max_units_to_run=None)
    assert rerun['skipped_from_checkpoint'] == 251
    assert rerun['executed_now'] == 0
    assert rerun['checkpoint_sha256'] == full['checkpoint_sha256']

    # Step 5: Changing config_sha256 does not falsely skip under old config
    diff_cfg = runner.run_checkpointed_experiments(cp_path, config_sha256=cfg_b, max_units_to_run=5)
    assert diff_cfg['skipped_from_checkpoint'] == 0
    assert diff_cfg['executed_now'] == 5


def test_export_and_notebook_cells_execute_end_to_end_on_synthetic(tmp_path, monkeypatch):
    monkeypatch.setenv('AMIDST_COLAB_WORKDIR', str(tmp_path / 'nb_workdir'))
    monkeypatch.setenv('AMIDST_WC5_SAFE_PACK_DIR', str(tmp_path / 'missing_wc5_pack'))

    nb = _load_notebook()
    ns: dict[str, object] = {'__name__': '__main__'}
    for cell in nb['cells']:
        if cell.get('cell_type') == 'code':
            code_str = ''.join(cell.get('source', []))
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code_str, f"<{cell.get('id', 'cell')}>", 'exec'), ns)

    export_report = ns['export_report']
    assert isinstance(export_report, dict)
    assert export_report['real_data_status'] == 'UNKNOWN'
    assert export_report['source_class'] == 'SYNTHETIC'

    export_dir = tmp_path / 'nb_workdir/exports'
    summary_csv = export_dir / 'colab_oneclick_summary.csv'
    summary_png = export_dir / 'colab_oneclick_summary.png'
    manifest_json = export_dir / 'EXPORT_MANIFEST.json'

    assert summary_csv.is_file() and summary_csv.stat().st_size > 200
    assert summary_png.is_file() and summary_png.stat().st_size > 5000
    assert manifest_json.is_file()

    with summary_csv.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 7
    assert all(r['real_data_status'] == 'UNKNOWN' for r in rows)
    assert all(r['source_class'] == 'SYNTHETIC' for r in rows)

    manifest = json.loads(manifest_json.read_text(encoding='utf-8'))
    assert manifest['real_data_status'] == 'UNKNOWN'
    assert manifest['source_class'] == 'SYNTHETIC'
    assert len(manifest['files']) == 42

    # Check run log exists and records real_data_status: UNKNOWN and key hashes
    assert RUN_LOG_PATH.is_file()
    log_text = RUN_LOG_PATH.read_text(encoding='utf-8')
    assert 'UNKNOWN (awaiting #416 W-C5 safe pack)' in log_text
    assert 'source_class = "SYNTHETIC"' in log_text
    assert export_report['summary_csv_sha256'] in log_text
    assert len(export_report['export_manifest_sha256']) == 64
    assert re.fullmatch(r'[0-9a-f]{64}', export_report['export_manifest_sha256'])
    assert export_report['export_manifest_sha256'] == manifest['export_manifest_sha256']


def test_notebook_cell4_preserves_existing_checkpoint(tmp_path, monkeypatch):
    workdir = tmp_path / 'nb_preserve'
    monkeypatch.setenv('AMIDST_COLAB_WORKDIR', str(workdir))
    cp_dir = workdir / 'checkpoints'
    cp_dir.mkdir(parents=True)
    cp_path = cp_dir / 'experiment_checkpoint.jsonl'

    # Pre-populate checkpoint with 251 completed records
    env_rep = runner.inspect_environment(deterministic=True)
    cfg_sha = env_rep['env_manifest']['parameter_set']['parameter_set_sha256']
    runner.run_checkpointed_experiments(cp_path, config_sha256=cfg_sha, max_units_to_run=None)
    assert cp_path.is_file()
    initial_sha = runner.sha256_file(cp_path)

    # Execute Cell 4 of the notebook in a namespace with env_report
    nb = _load_notebook()
    code_cell_4 = [c for c in nb['cells'] if c.get('id') == 'code-cell-4'][0]
    ns: dict[str, object] = {
        '__name__': '__main__',
        'WORKDIR': workdir,
        'runner': runner,
        'env_report': env_rep,
        'json': json,
    }
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(''.join(code_cell_4['source']), '<code-cell-4>', 'exec'), ns)

    # Checkpoint must NOT be deleted; all units must be skipped
    assert cp_path.is_file()
    assert runner.sha256_file(cp_path) == initial_sha
    rep = ns['checkpoint_report']
    assert isinstance(rep, dict)
    assert rep['skipped_from_checkpoint'] == 251
    assert rep['executed_now'] == 0
    assert rep['completed_total'] == 251

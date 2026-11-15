"""WP5 Colab L4 / Windows local-model packs: composition, scan, and a dry-run from inside the pack."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from amidst.agent_eval import windows_pack, wp5_pack, wp5_runner

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def packs(tmp_path_factory):
    base = tmp_path_factory.mktemp('packs')
    return {t: wp5_pack.build_wp5_pack(base / f'wp5-pack_{t}', repo_root=ROOT, target=t, commit='a' * 40, per_type=4) for t in wp5_pack.TARGETS}


@pytest.mark.parametrize('target', wp5_pack.TARGETS)
def test_pack_is_valid_clean_and_has_required_sections(packs, target):
    d = Path(packs[target]['dir'])
    assert windows_pack.verify_pack(d) == (True, [])
    readme = (d / 'README.md').read_text(encoding='utf-8')
    for section in ('## 工作內容', '## 要上傳的檔案', '## 操作步驟', '## 要提交項目'):
        assert section in readme
    assert (d / 'RETURN' / 'README.txt').read_text(encoding='utf-8').count('wp5_<set>_') >= 1
    for f in d.rglob('*'):
        if f.is_file():
            text = f.read_text(encoding='utf-8')
            assert wp5_pack._SECRET.search(text) is None and wp5_pack._HOME.search(text) is None, f
    assert not any(p.name.startswith(('gt_', 'scoring_private')) for p in d.rglob('*'))


def test_zip_is_deterministic_and_safe(packs, tmp_path):
    z = Path(packs['colab_l4']['zip'])
    again = wp5_pack.build_wp5_pack(tmp_path / 'wp5-pack_colab_l4', repo_root=ROOT, target='colab_l4', commit='a' * 40, per_type=4)
    assert again['zip_sha256'] == packs['colab_l4']['zip_sha256']
    with zipfile.ZipFile(z) as zf:
        assert all(not n.startswith('/') and '..' not in n for n in zf.namelist())


def test_target_specific_entry(packs):
    assert (Path(packs['colab_l4']['dir']) / wp5_pack.NOTEBOOK).is_file() and not (Path(packs['colab_l4']['dir']) / 'run.py').exists()
    assert (Path(packs['windows']['dir']) / 'run.py').is_file()
    info = json.loads((Path(packs['windows']['dir']) / 'PACK_INFO.json').read_text())
    assert info['latency_reportable'] is False and info['question_class'] == 'SYNTHETIC'


@pytest.mark.parametrize('target,arm', [('colab_l4', 'colab_l4'), ('windows', 'windows')])
def test_dry_run_inside_pack_makes_no_calls_and_reads_no_key(packs, tmp_path, target, arm):
    d = Path(packs[target]['dir'])
    env = {k: v for k, v in os.environ.items() if k not in ('OPENAI_API_KEY', 'PYTHONPATH', 'AMIDST_ROOT')}
    env['PYTHONPATH'] = str(d / 'src')
    out = tmp_path / 'dry'
    r = subprocess.run([sys.executable, '-s', '-m', 'amidst.agent_eval.wp5_runner', '--set', 'pilot', '--arm', arm, '--skip-types', 'DP4',
                        '--out', str(out)], cwd=d, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    est = json.loads((out / 'estimate.json').read_text())
    assert est['provider_calls'] == 0 and est['mode'] == 'DRY_RUN'


def test_windows_arm_selects_local_models_only():
    cfg = json.loads((ROOT / 'configs/agent_eval/wp5_v1.json').read_text())
    args = wp5_runner.build_parser().parse_args(['--set', 'pilot', '--arm', 'windows', '--out', 'x'])
    models, _ = wp5_runner._select(cfg, args)
    assert models == list(wp5_pack.LOCAL_MODELS)

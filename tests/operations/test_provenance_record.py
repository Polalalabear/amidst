import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import provenance_record as pr  # noqa: E402


def make_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    for cmd in (['init', '-q'], ['config', 'user.email', 'a@b.c'], ['config', 'user.name', 'n']):
        subprocess.run(['git', '-C', str(repo), *cmd], check=True)
    (repo / 'f.txt').write_text('x')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'c'], check=True)
    return repo


def run_cli(repo, *extra):
    return subprocess.run([sys.executable, str(ROOT / 'scripts/provenance_record.py'), '--repo', str(repo), '--skip-gpu-probe', *extra],
                          capture_output=True, text=True)


def test_schema_and_input_hash(tmp_path):
    repo = make_repo(tmp_path)
    data = tmp_path / 'data.bin'
    data.write_bytes(b'abc' * 1000)
    out = run_cli(repo, '--input', str(data), '--model-file', str(data), '--ollama-model', 'no-such-model:1')
    assert out.returncode == 0, out.stderr
    rec = json.loads(out.stdout)
    assert rec['schema_version'] == 'amidst.provenance-record.v1'
    want = hashlib.sha256(b'abc' * 1000).hexdigest()
    assert rec['inputs'][0]['sha256'] == want and rec['models'][0]['sha256'] == want
    assert rec['models'][1]['digest'] == 'UNKNOWN'
    assert rec['git']['dirty'] is False and len(rec['git']['head_sha']) == 40
    assert rec['run']['finished_at_utc'].endswith('Z')
    for key in ('os', 'cpu', 'memory_bytes', 'gpu', 'python', 'packages', 'node'):
        assert key in rec['environment']


def test_dirty_is_flagged(tmp_path):
    repo = make_repo(tmp_path)
    (repo / 'new.txt').write_text('y')
    rec = json.loads(run_cli(repo).stdout)
    assert rec['git']['dirty'] is True and rec['git']['dirty_entries'] == 1
    assert 'DIRTY' in rec['git']['working_tree']


def test_directory_hash_and_ollama_digest():
    assert pr.ollama_digest('m', {'models': [{'name': 'm:latest', 'digest': 'sha256:ab'}]}) == 'sha256:ab'
    assert pr.ollama_digest('x', {'models': []}) == 'UNKNOWN'


def test_no_secret_or_env_in_output(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-SECRETVALUE123456')
    monkeypatch.setenv('MY_TOKEN', 'tok-SECRETVALUE654321')
    out = run_cli(repo, '--command', 'python run.py --api-key sk-ant-INLINEKEY123456 TOKEN=abcdef123')
    assert out.returncode == 0
    assert 'SECRETVALUE' not in out.stdout and 'INLINEKEY' not in out.stdout and 'abcdef123' not in out.stdout
    assert '[REDACTED]' in out.stdout
    assert 'ANTHROPIC_API_KEY' not in out.stdout


@pytest.mark.parametrize('rel', ['gt_private/x.json', 'ground_truth/a.json', 'run/visibility.json',
                                 'run/depth_map.npy', 'run/trajectory.csv'])
def test_gt_paths_rejected(tmp_path, rel):
    repo = make_repo(tmp_path)
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{}')
    out = run_cli(repo, '--input', str(target))
    assert out.returncode == 2 and 'FORBIDDEN_PATH' in out.stderr and not out.stdout


def test_gt_symlink_and_directory_member_rejected(tmp_path):
    repo = make_repo(tmp_path)
    (tmp_path / 'gt_private').mkdir()
    (tmp_path / 'gt_private' / 'a.txt').write_text('1')
    link = tmp_path / 'innocent.txt'
    link.symlink_to(tmp_path / 'gt_private' / 'a.txt')
    assert run_cli(repo, '--input', str(link)).returncode == 2
    d = tmp_path / 'bundle'
    d.mkdir()
    (d / 'ok.txt').write_text('1')
    (d / 'depth.png').write_text('1')
    assert run_cli(repo, '--input', str(d)).returncode == 2


def test_schema_registered():
    reg = json.loads((ROOT / 'configs/architecture/schema_registry_v1.json').read_text())
    assert 'amidst.provenance-record.v1' in {s['value'] for s in reg['schemas']}

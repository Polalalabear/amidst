"""D171: owned_root is repo-relative; an explicit AMIDST_DEMO_HOME still wins."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import demo_dependency_config as cfg  # noqa: E402


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    for key in ('AMIDST_ROOT', 'AMIDST_DEMO_HOME'):
        monkeypatch.delenv(key, raising=False)
    value = json.loads((REPO / 'configs/demo_integration_local.json').read_text())
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(value))
    return path


def test_shipped_config_is_repo_relative():
    value = json.loads((REPO / 'configs/demo_integration_local.json').read_text())
    assert value['owned_root'] == 'local/data/demo-owned-v1'


def test_relative_owned_root_resolves_against_amidst_root(tmp_path, monkeypatch, config_path):
    monkeypatch.setenv('AMIDST_ROOT', str(tmp_path / 'root'))
    with pytest.raises(ValueError, match='OWNED_ROOT_NOT_FOUND.*AMIDST_DEMO_HOME'):
        cfg.configuration(config_path)
    owned = tmp_path / 'root/local/data/demo-owned-v1'
    owned.mkdir(parents=True)
    _, root = cfg.configuration(config_path)
    assert root == owned.resolve()


def test_explicit_home_wins_and_symlink_is_not_canonical(tmp_path, monkeypatch, config_path):
    real, link = tmp_path / 'real', tmp_path / 'link'
    real.mkdir()
    link.symlink_to(real)
    monkeypatch.setenv('AMIDST_DEMO_HOME', str(real))
    assert cfg.configuration(config_path)[1] == real
    monkeypatch.setenv('AMIDST_DEMO_HOME', str(link))
    with pytest.raises(ValueError, match='CANONICAL_OWNED_ROOT_REQUIRED'):
        cfg.configuration(config_path)


def test_node_runtime_rule_matches_python():
    source = (REPO / 'tests/browser/core-preview/owned-runtime.mjs').read_text()
    assert 'OWNED_ROOT_NOT_FOUND' in source and 'AMIDST_ROOT' in source


def _git(cwd, *args):
    subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True)


def test_demo_pin_check_and_approve(tmp_path, monkeypatch):
    import demo_pin
    repo = tmp_path / 'repo'
    repo.mkdir()
    _git(repo, 'init', '-q')
    (repo / '.gitignore').write_text('/local/\n')
    _git(repo, 'add', '.gitignore')
    _git(repo, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '-m', 'one')
    monkeypatch.setattr(demo_pin, 'REPO', repo)
    monkeypatch.setattr(demo_pin, 'PIN', repo / 'local/demo-pin.json')
    monkeypatch.delenv('AMIDST_DEMO_ALLOW_UNPINNED', raising=False)
    assert demo_pin.check() == 0  # no pin yet
    bad = tmp_path / 'gate-fail.txt'
    bad.write_text('unit PASS\ncore-e2e FAIL(see log)\n')
    with pytest.raises(SystemExit, match='GATE_NOT_PASSING'):
        demo_pin.approve('user', bad)
    good = tmp_path / 'gate.txt'
    good.write_text('unit PASS\ncore-e2e PASS\n')
    assert demo_pin.approve('user', good) == 0
    assert demo_pin.check() == 0
    (repo / 'new.txt').write_text('x')
    assert demo_pin.check() == 1  # dirty tree
    _git(repo, 'add', 'new.txt')
    _git(repo, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '-m', 'two')
    assert demo_pin.check() == 1  # HEAD moved
    monkeypatch.setenv('AMIDST_DEMO_ALLOW_UNPINNED', '1')
    assert demo_pin.check() == 0

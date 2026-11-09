from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from amidst import paths

HOME = '/Users/tester'
MAP = {'entries': [
    {'old': '~/amidst-artifacts', 'new': 'local/evidence'},
    {'old': '~/amidst-artifacts/demo-owned-v1', 'new': 'local/data/demo-owned-v1'},
    {'old': '~/amidst-artifacts/d133-bench-pilot', 'new': 'local/archive/d133-bench-pilot'},
    {'old': '/Users/tester/Developer/amidst', 'new': 'local/archive/office-canonical'},
]}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ('AMIDST_ROOT', 'AMIDST_DEMO_HOME', 'AMIDST_ARTIFACTS'):
        monkeypatch.delenv(key, raising=False)


def test_root_defaults_to_repository_and_env_overrides(tmp_path, monkeypatch):
    assert paths.amidst_root() == Path(paths.__file__).resolve().parents[2]
    monkeypatch.setenv('AMIDST_ROOT', str(tmp_path))
    assert paths.amidst_root() == tmp_path.resolve()
    assert paths.data_dir() == tmp_path.resolve() / 'local/data'
    assert paths.evidence_dir() == tmp_path.resolve() / 'local/evidence'
    assert paths.archive_dir() == tmp_path.resolve() / 'local/archive'


def test_local_dir_falls_back_to_shared_clone_source(tmp_path, monkeypatch):
    source, clone = tmp_path / 'src', tmp_path / 'clone'
    (source / 'local').mkdir(parents=True)
    (clone / '.git/objects/info').mkdir(parents=True)
    (clone / '.git/objects/info/alternates').write_text(str(source / '.git/objects') + '\n')
    monkeypatch.setenv('AMIDST_ROOT', str(clone))
    assert paths.local_dir() == (source / 'local').resolve()
    (clone / 'local').mkdir()
    assert paths.local_dir() == (clone / 'local').resolve()


def test_owned_root_order_and_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv('AMIDST_ROOT', str(tmp_path))
    with pytest.raises(ValueError, match='OWNED_ROOT_NOT_FOUND.*AMIDST_DEMO_HOME'):
        paths.demo_owned_root('local/data/demo-owned-v1')
    default = tmp_path / 'local/data/demo-owned-v1'
    default.mkdir(parents=True)
    assert paths.demo_owned_root('local/data/demo-owned-v1') == default.resolve()
    explicit = tmp_path / 'elsewhere'
    explicit.mkdir()
    monkeypatch.setenv('AMIDST_DEMO_HOME', str(explicit))
    assert paths.demo_owned_root('local/data/demo-owned-v1') == explicit
    monkeypatch.setenv('AMIDST_DEMO_HOME', 'elsewhere')  # relative: against the root
    assert paths.demo_owned_root() == explicit.resolve()


def test_owned_root_keeps_symlink_visible_for_canonical_check(tmp_path, monkeypatch):
    real, link = tmp_path / 'real', tmp_path / 'link'
    real.mkdir()
    link.symlink_to(real)
    monkeypatch.setenv('AMIDST_DEMO_HOME', str(link))
    assert paths.demo_owned_root() == link and link.resolve() != link


def test_artifacts_output_root(tmp_path, monkeypatch):
    monkeypatch.setenv('AMIDST_ROOT', str(tmp_path))
    assert paths.artifacts_output_root() == tmp_path.resolve() / 'local/evidence'
    monkeypatch.setenv('AMIDST_ARTIFACTS', str(tmp_path / 'out'))
    assert paths.artifacts_output_root() == (tmp_path / 'out').resolve()


def test_locate_artifact_unique_missing_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv('AMIDST_ROOT', str(tmp_path))
    (tmp_path / 'local/data/a').mkdir(parents=True)
    (tmp_path / 'local/evidence/b').mkdir(parents=True)
    (tmp_path / 'local/archive/b').mkdir(parents=True)
    assert paths.locate_artifact('a') == (tmp_path / 'local/data/a').resolve()
    with pytest.raises(paths.ArtifactNotFound):
        paths.locate_artifact('c')
    with pytest.raises(paths.ArtifactAmbiguous):
        paths.locate_artifact('b')
    for bad in ('/abs', '../x', ''):
        with pytest.raises(ValueError):
            paths.locate_artifact(bad)


def test_resolve_legacy_longest_prefix_and_component_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv('AMIDST_ROOT', str(tmp_path))
    root = tmp_path.resolve()
    f = lambda p: paths.resolve_legacy(p, home=HOME, path_map=MAP)
    assert f('~/amidst-artifacts/demo-owned-v1/data/x') == root / 'local/data/demo-owned-v1/data/x'
    assert f('/Users/tester/amidst-artifacts/demo-owned-v1') == root / 'local/data/demo-owned-v1'
    assert f('~/amidst-artifacts/other/y') == root / 'local/evidence/other/y'
    assert f('~/amidst-artifacts/d133-bench-pilot/z') == root / 'local/archive/d133-bench-pilot/z'
    assert f('~/amidst-artifacts/d133-bench') == root / 'local/evidence/d133-bench'
    assert f('~/amidst-artifactsX/y') is None
    assert f('/Users/tester/Developer/amidst-q1q5/a') is None
    assert f('/Users/tester/Developer/amidst/blender/a.blend') == root / 'local/archive/office-canonical/blender/a.blend'


def test_shipped_map_is_well_formed():
    data = paths.json.loads(paths.PATH_MAP.read_text())
    olds = [e['old'] for e in data['entries']]
    assert len(olds) == len(set(olds)) == 171
    assert all(not e['new'].startswith('/') and '..' not in e['new'].split('/') for e in data['entries'])


def test_windows_paths_use_component_rules():
    rel = paths.relative_to_root
    assert rel(PureWindowsPath('C:/Amidst/local/data/x'), PureWindowsPath('c:\\amidst')) == 'local/data/x'
    assert rel(PureWindowsPath('C:/AmidstOther/x'), PureWindowsPath('C:/Amidst')) is None
    assert rel(PureWindowsPath('D:/Amidst/x'), PureWindowsPath('C:/Amidst')) is None
    assert rel(r'C:\Amidst\local\y', r'C:\Amidst') == 'local/y'
    assert rel(PureWindowsPath('C:/Amidst'), PureWindowsPath('C:/Amidst')) == ''
    assert rel(PurePosixPath('/a/b'), PureWindowsPath('C:/a')) is None
    assert rel(PurePosixPath('/Users/a/b'), PurePosixPath('/Users/a')) == 'b'
    assert rel(PurePosixPath('/Users/ab'), PurePosixPath('/Users/a')) is None
    assert paths.resolve_legacy(PureWindowsPath('C:/Users/tester/amidst-artifacts/x'), home=HOME, path_map=MAP) is None

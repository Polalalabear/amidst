import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('clar', ROOT / 'scripts/check_local_artifact_refs.py')
clar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clar)
H = 'a' * 64


def codes(text, name='x.md'):
    return [(f['code'], f['line']) for f in clar.scan_text(name, text)]


def test_valid_ref_with_sha_passes():
    assert codes(f'Source: `local/evidence/run-1/MANIFEST.json` SHA-256 {H}') == []
    assert codes(f'| `$AMIDST_ARTIFACTS/x/y` | 12 files | {H} |') == []


def test_valid_ref_without_sha_flagged():
    assert codes('Source: `local/data/demo-owned-v1/`') == [('LOCAL_REF_NO_SHA', 1)]
    assert codes('see $AMIDST_ARTIFACTS/foo/bar.png') == [('LOCAL_REF_NO_SHA', 1)]


def test_explicit_exemption_phrases():
    assert codes('`local/archive/old/` 無法重建') == []
    assert codes('`local/archive/old/` not applicable') == []


def test_forbidden_paths_flagged():
    for bad in ['/tmp/x', '/private/tmp/x', '/Users/someone/amidst/a', '~/amidst-artifacts/r1',
                '~/Developer/amidst', '$HOME/amidst-demo-state/run']:
        assert ('BAD_LOCAL_PATH', 1) in codes(f'path {bad} {H}'), bad


def test_ignore_marker_and_fence():
    assert codes('never use ~/amidst-artifacts <!-- local-ref-ignore -->') == []
    fenced = '```bash\nls local/evidence/x\n```\n'
    assert codes(fenced) == []  # commands in fences need no SHA
    assert codes('```bash\nrm ~/amidst-artifacts/x\n```') == [('BAD_LOCAL_PATH', 2)]


def test_table_row_is_one_line():
    text = f'| a | b |\n| --- | --- |\n| `local/evidence/a` | {H} |\n| `local/evidence/b` | - |\n'
    assert codes(text) == [('LOCAL_REF_NO_SHA', 4)]


def test_json_window():
    text = '{\n "path": "local/evidence/a/b.json",\n "sha256": "%s"\n}\n' % H
    assert codes(text, 'x.json') == []
    assert codes('{\n "path": "local/evidence/a/b.json"\n}\n', 'x.json') == [('LOCAL_REF_NO_SHA', 2)]


def test_main_warn_vs_strict(tmp_path):
    (tmp_path / 'd.md').write_text('`local/data/x`\n')
    argv = ['--repo', str(tmp_path), '--files', 'd.md']
    assert clar.main(argv) == 0
    assert clar.main(argv + ['--strict']) == 1


def test_changed_files_uses_diff(tmp_path):
    def git(*a):
        subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True,
                       capture_output=True)
    git('init', '-q', '-b', 'main')
    (tmp_path / 'a.md').write_text('x\n')
    git('add', '.'); git('commit', '-qm', 'a')
    git('checkout', '-qb', 'f')
    (tmp_path / 'b.md').write_text('x\n'); (tmp_path / 'c.py').write_text('x\n')
    git('add', '.'); git('commit', '-qm', 'b')
    assert clar.changed_files(tmp_path, 'main') == ['b.md']

"""D138 artifact ledger: structure, schema/tool sync, registry entry, and tool behaviour on a temp tree."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / 'configs/provenance/artifact_ledger_v1.json'
SCHEMA = ROOT / 'configs/provenance/artifact_ledger_v1.schema.json'
REGISTRY = ROOT / 'configs/architecture/schema_registry_v1.json'
VALUE = 'amidst.artifact-ledger.v1'

spec = importlib.util.spec_from_file_location('artifact_ledger', ROOT / 'scripts/artifact_ledger.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


@pytest.fixture(scope='module')
def ledger():
    return json.loads(LEDGER.read_text(encoding='utf-8'))


def test_ledger_validates(ledger):
    assert tool.validate(ledger) == []
    assert ledger['schema_version'] == VALUE
    assert len(ledger['entries']) >= 100


def test_schema_enums_match_tool():
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    entry = schema['$defs']['entry']
    props = entry['properties']
    assert tuple(props['type']['enum']) == tool.TYPES
    assert tuple(props['disposition']['enum']) == tool.DISPOSITIONS
    assert tuple(props['rebuildable']['enum']) == tool.REBUILDABLE
    assert tuple(props['hash']['properties']['policy']['enum']) == tool.HASH_POLICIES
    assert tuple(props['hash']['properties']['completeness']['enum']) == tool.COMPLETENESS
    assert schema['properties']['schema_version']['const'] == tool.SCHEMA_VERSION == VALUE
    # every field the tool requires is required by the schema too
    for key in ('id', 'path', 'type', 'disposition', 'purpose', 'referenced_by', 'retain_reason', 'rebuildable',
                'size_bytes', 'file_count', 'hash', 'safety'):
        assert key in entry['required']
    assert tuple(props['safety']['properties']['status']['enum']) == tool.SAFETY_STATUS
    assert tuple(props['safety']['properties']['checks']['required']) == tool.SAFETY_CHECKS


def test_schema_registered_with_existing_sources():
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    items = [x for x in registry['schemas'] if x['value'] == VALUE]
    assert len(items) == 1
    assert items[0]['issue_ref'] == '#93'
    for path in items[0]['source_paths']:
        assert (ROOT / path).exists(), path


def test_gt_and_raw_boundaries(ledger):
    for e in ledger['entries']:
        parts = Path(e['path'].replace('~/', '/h/')).parts
        assert not (set(parts) & tool.EXCLUDED_DIR_NAMES), e['id']
        if e['type'] == 'raw_data':
            assert e['hash']['policy'] in ('full', 'files_only', 'path_size_only'), e['id']
        if e['disposition'] == 'deletable':
            assert e['type'] != 'raw_data', e['id']
    cx = [e for e in ledger['entries'] if e['id'].startswith('ART-r004-cx7')]
    assert cx and all(e['hash'].get('excluded') for e in cx)
    for e in cx:
        assert all(x['path'].rstrip('/').endswith('gt_private') for x in e['hash']['excluded'])


def test_complete_entries_have_digests_and_parent_ids_resolve(ledger):
    ids = {e['id'] for e in ledger['entries']}
    assert len(ids) == len(ledger['entries'])
    for e in ledger['entries']:
        h = e['hash']
        if h['completeness'] == 'complete':
            assert re.fullmatch(r'[0-9a-f]{64}', h.get('sha256') or h.get('manifest_sha256') or '')
        if 'parent_id' in e:
            assert e['parent_id'] in ids
        if e['disposition'] == 'deletable' and e['type'] != 'cache':
            assert h['completeness'] == 'complete', e['id']


def test_manifest_is_deterministic_and_excludes_gt(tmp_path):
    root = tmp_path / 'run'
    (root / 'a').mkdir(parents=True)
    (root / 'gt_private').mkdir()
    (root / 'a' / 'x.txt').write_bytes(b'hello')
    (root / 'b.txt').write_bytes(b'world')
    (root / 'gt_private' / 'secret.bin').write_bytes(b'S' * 100)
    entry = {'id': 't', 'path': str(root), 'hash': {'policy': 'full'}}
    one = tool.compute_entry(entry)
    two = tool.compute_entry(entry, workers=1)
    assert one == two
    assert one['file_count'] == 2 and one['size_bytes'] == 10
    assert one['excluded_file_count'] == 1 and one['excluded_size_bytes'] == 100
    rows = [('a/x.txt', tool.hashlib.sha256(b'hello').hexdigest()), ('b.txt', tool.hashlib.sha256(b'world').hexdigest())]
    assert one['hash']['manifest_sha256'] == tool.manifest_digest(rows[::-1])
    # changing a byte changes the manifest; adding a file in gt_private does not
    (root / 'gt_private' / 'more.bin').write_bytes(b'x')
    assert tool.compute_entry(entry)['hash']['manifest_sha256'] == one['hash']['manifest_sha256']
    (root / 'b.txt').write_bytes(b'World')
    assert tool.compute_entry(entry)['hash']['manifest_sha256'] != one['hash']['manifest_sha256']


def test_single_file_and_missing_path(tmp_path):
    f = tmp_path / 'f.bin'
    f.write_bytes(b'abc')
    comp = tool.compute_entry({'id': 'f', 'path': str(f), 'hash': {'policy': 'full'}})
    assert comp['hash']['sha256'] == tool.hashlib.sha256(b'abc').hexdigest()
    gone = tool.compute_entry({'id': 'g', 'path': str(tmp_path / 'none'), 'hash': {'policy': 'full'}})
    assert gone['size_bytes'] is None and gone['hash']['completeness'] == 'not_computed'


def test_verify_detects_mismatch(tmp_path):
    root = tmp_path / 'tree'
    root.mkdir()
    (root / 'f.txt').write_bytes(b'one')
    entry = {'id': 'ART-test', 'path': str(root), 'type': 'derived_data', 'disposition': 'keep_original',
             'purpose': 'p', 'referenced_by': ['UNKNOWN'], 'retain_reason': 'r', 'rebuildable': 'yes',
             'size_bytes': None, 'file_count': None, 'hash': {'policy': 'full', 'completeness': 'not_computed'},
             'safety': {'status': 'KEEP', 'reason': 'x', 'checks': {k: 'unknown' for k in tool.SAFETY_CHECKS}}}
    ledger = {'schema_version': VALUE, 'generated_at': '2026-11-09', 'issue_ref': '#93', 'decision_ref': 'D138',
              'baseline_ref': '0' * 40, 'rules': {}, 'entries': [entry]}
    path = tmp_path / 'ledger.json'
    tool.dump(ledger, path)
    assert tool.main(['compute', '--ledger', str(path)]) == 0
    assert tool.main(['validate', '--ledger', str(path)]) == 0
    assert tool.main(['verify', '--ledger', str(path)]) == 0
    (root / 'f.txt').write_bytes(b'two')
    assert tool.main(['verify', '--ledger', str(path)]) == 1


def test_validate_rejects_bad_entries(ledger):
    bad = json.loads(json.dumps(ledger))
    bad['entries'][0]['disposition'] = 'delete_now'
    bad['entries'][1]['hash']['sha256'] = 'xyz'
    errors = tool.validate(bad)
    assert any('disposition' in e for e in errors) and any('sha256' in e for e in errors)


def test_safety_rules(ledger):
    for e in ledger['entries']:
        sf = e['safety']
        assert sf['status'] in tool.SAFETY_STATUS
        assert set(sf['checks']) == set(tool.SAFETY_CHECKS)
        if e['disposition'] == 'deletable':
            assert sf['status'] == 'SAFE', e['id']
        if sf['status'] == 'SAFE':
            assert all(v == 'pass' for v in sf['checks'].values()), e['id']
            assert sf['verify_commands'] and sf['restore'], e['id']
            assert e['type'] not in ('raw_data', 'evidence', 'code_checkout', 'git_ref'), e['id']
        if e['type'] in ('raw_data', 'code_checkout', 'git_ref'):
            assert sf['status'] != 'SAFE', e['id']
    keep = {e['id']: e for e in ledger['entries']}
    # D157: running 8785 service and owned package, and referenced D133 proxies, are never SAFE
    for key in ('ART-demo-owned-v1', 'CO-demo', 'ENV-demo-venv', 'ART-d133-proxies-v2-jpeg', 'ART-d133-proxies-v2-webp',
                'LOC-shared-cleanroom', 'SCR-claude-scratch-root'):
        assert keep[key]['safety']['status'] == 'KEEP', key
        assert keep[key]['disposition'] != 'deletable', key


def test_validate_safety_rejects_unsafe_deletable(ledger):
    bad = json.loads(json.dumps(ledger))
    target = next(e for e in bad['entries'] if e['disposition'] == 'deletable')
    target['safety']['status'] = 'KEEP'
    assert any('deletable requires safety SAFE' in x for x in tool.validate(bad))
    bad = json.loads(json.dumps(ledger))
    target = next(e for e in bad['entries'] if e['safety']['status'] == 'SAFE')
    target['safety']['checks']['running_services'] = 'unknown'
    assert any('SAFE requires all checks pass' in x for x in tool.validate(bad))
    bad = json.loads(json.dumps(ledger))
    target = next(e for e in bad['entries'] if e['safety']['status'] == 'SAFE')
    target['safety'].pop('restore')
    assert any('verify_commands and restore' in x for x in tool.validate(bad))
    bad = json.loads(json.dumps(ledger))
    next(e for e in bad['entries'] if e['type'] == 'raw_data')['safety']['status'] = 'SAFE'
    assert any('raw_data can never be SAFE' in x for x in tool.validate(bad))

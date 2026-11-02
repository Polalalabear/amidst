"""D112 mechanical projection, using only explicitly TEST-only input pins."""
import json

import pytest

from test_check_handoff_pack import SCRIPT, encode, make_zip, module, put, repin, sha


TEST_PINS = {'frozen_test_input': sha(b'SYNTHETIC ONLY')}


def fixture(tmp_path):
    root = tmp_path / 'SYNTHETIC_BASELINE'
    put(root, 'README.txt', ('工作內容\n要提交項目\n操作\n不要改\n_INCOMPLETE\n'
        'RETURN/評測結果_姓名_YYYY-MM-DD.json\n'
        '本包只含 Baseline（ENGINEERING）；複雜事件半部未包含\n').encode())
    put(root, 'RETURN/README.txt', b'SYNTHETIC ONLY\n')
    # Include the checker itself: the forbidden-content scanner must accept it.
    put(root, 'tools/verify_pack.py', SCRIPT.read_bytes())
    put(root, 'frozen/baseline.json', encode({'source_class': 'ENGINEERING', 'fixture_role': 'SYNTHETIC_ONLY'}))
    put(root, 'MANIFEST.json', encode({'schema_version': 'team-review-pack.v1',
        'version': 'v0-pilot', 'evaluation_eligible': False, 'samples': [],
        'pack_kind': 'team-model-eval', 'source_class': 'ENGINEERING', 'halves': ['baseline'],
        'return_file': 'RETURN/評測結果_姓名_YYYY-MM-DD.json', 'source_pins': TEST_PINS,
        'files': {}, 'editable_files': {}}))
    repin(root)
    return root


def check(root, *, pack=None, returned=None, pins=TEST_PINS):
    checker = module()
    checker.TEAM_EVAL_SOURCE_PINS = pins
    return checker.inspect_pack(pack or root, profile='team-eval',
        manifest_sha256=sha((root / 'MANIFEST.json').read_bytes()), returned_json=returned)


def returned(root, tmp_path):
    path = tmp_path / 'RETURN.json'
    path.write_bytes(encode({'projection': 'TEAM_EVAL_BASELINE_V0_PILOT',
        'schema_candidate': 'team-eval-return.v1',
        'pack_manifest_sha256': sha((root / 'MANIFEST.json').read_bytes()),
        'environment': {'python_version': '3.12.12', 'isolated': True, 'platform': 'SYNTHETIC'},
        'halves': {'baseline': {'status': 'COMPLETE'}},
        'output_sha256': {'baseline': sha(b'SYNTHETIC')},
        'return_files': {'baseline': 'returned/baseline.json'}}))
    return path


def test_baseline_only_directory_zip_and_return(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path / 'pack.zip'
    make_zip(root, output, prefix='baseline/')
    for pack in (root, output):
        result = check(root, pack=pack, returned=returned(root, tmp_path))
        assert result['status'] == 'VALID', result
        assert result['production_profile'] == 'TEAM_EVAL_BASELINE_V0_PILOT'
        assert result['returned_json_checked'] is True
        assert result['return_payload_bytes_verified'] is False
        assert result['release_authorized'] is False
        assert result['evaluation_eligible_verified'] is False
        assert result['packed_verifier_executed'] is False


@pytest.mark.parametrize('field,value,code', [
    ('version', 'v1', 'PROFILE_UNSELECTED'),
    ('evaluation_eligible', True, 'PROFILE_UNSELECTED'),
    ('source_pins', {'frozen_test_input': '0' * 64}, 'PROFILE_UNSELECTED'),
    ('source_pins', {}, 'PROFILE_UNSELECTED'),
    ('halves', ['baseline', 'complex'], 'HALF_NOT_IN_PACK'),
    ('halves', [], 'HALF_NOT_IN_PACK'),
    ('editable_files', {'A_文字情境/情境.csv': {}}, 'MANIFEST_FIELDS_INVALID'),
    ('source_class', 'FORMAL', 'MANIFEST_FIELDS_INVALID'),
])
def test_production_manifest_mismatch(tmp_path, field, value, code):
    root = fixture(tmp_path)
    path = root / 'MANIFEST.json'
    doc = json.loads(path.read_bytes()); doc[field] = value
    path.write_bytes(encode(doc))
    assert check(root)['code'] == code


def test_unselected_source_inventory_stays_closed(tmp_path):
    root = fixture(tmp_path)
    assert check(root, pins={})['code'] == 'PROFILE_UNSELECTED'


@pytest.mark.parametrize('name', ['complex/placeholder.txt', 'frozen/complex.json'])
def test_complex_payload_or_placeholder_invalid(tmp_path, name):
    root = fixture(tmp_path)
    put(root, name, b'{}'); repin(root)
    assert check(root)['code'] == 'HALF_NOT_IN_PACK'


def test_complex_empty_directory_invalid(tmp_path):
    root = fixture(tmp_path)
    (root / 'complex').mkdir()
    assert check(root)['code'] == 'EMPTY_DIRECTORY'


def test_complex_nested_output_invalid(tmp_path):
    root = fixture(tmp_path)
    put(root, 'frozen/baseline.json', encode({'outputs': {'complex': None}})); repin(root)
    assert check(root)['code'] == 'HALF_NOT_IN_PACK'


@pytest.mark.parametrize('field', ['halves', 'output_sha256', 'return_files'])
@pytest.mark.parametrize('value', [None, '', 0])
def test_any_complex_return_key_invalid(tmp_path, field, value):
    root = fixture(tmp_path); path = returned(root, tmp_path)
    doc = json.loads(path.read_bytes()); doc[field]['complex'] = value
    path.write_bytes(encode(doc))
    assert check(root, returned=path)['code'] == 'HALF_NOT_IN_PACK'


@pytest.mark.parametrize('field', ['halves', 'output_sha256', 'return_files'])
def test_missing_baseline_return_invalid(tmp_path, field):
    root = fixture(tmp_path); path = returned(root, tmp_path)
    doc = json.loads(path.read_bytes()); doc[field] = {}
    path.write_bytes(encode(doc))
    assert check(root, returned=path)['code'] == 'HALF_NOT_IN_PACK'


@pytest.mark.parametrize('field,value', [('python_version', '3.13.0'), ('isolated', False), ('platform', '')])
def test_return_environment_invalid(tmp_path, field, value):
    root = fixture(tmp_path); path = returned(root, tmp_path)
    doc = json.loads(path.read_bytes()); doc['environment'][field] = value
    path.write_bytes(encode(doc))
    assert check(root, returned=path)['code'] == 'RETURN_ENVIRONMENT_INVALID'


def test_production_requires_explicit_manifest_pin(tmp_path):
    root = fixture(tmp_path); checker = module(); checker.TEAM_EVAL_SOURCE_PINS = TEST_PINS
    assert checker.inspect_pack(root, profile='team-eval')['code'] == 'PROFILE_UNSELECTED'


def test_payload_change_and_forbidden_content_still_rejected(tmp_path):
    root = fixture(tmp_path)
    put(root, 'frozen/baseline.json', b'{"visibility": true}')
    assert check(root)['code'] == 'FILE_SHA_MISMATCH'
    repin(root)
    assert check(root)['code'] == 'FORBIDDEN_CONTENT'


def test_required_readme_notice(tmp_path):
    root = fixture(tmp_path)
    path = root / 'README.txt'
    path.write_text(path.read_text().replace('本包只含 Baseline（ENGINEERING）；複雜事件半部未包含', ''))
    repin(root)
    assert check(root)['code'] == 'README_INCOMPLETE'


def false_flag_fixture(tmp_path, mutation=None):
    root = fixture(tmp_path)
    doc = {'fixture_role': 'SYNTHETIC_ONLY', 'response': {'provenance': {'gt_read': False}}}
    if mutation == 'wrong-path':
        del doc['response']['provenance']['gt_read']; doc['gt_read'] = False
    elif mutation == 'extra-key':
        doc['response']['provenance']['gt_actor_id'] = 'SYNTHETIC'
    elif mutation == 'string-bait':
        doc['note'] = 'SYNTHETIC "gt_actor_id": "bait"'
    elif mutation in ('true', 'string', 'zero', 'null'):
        doc['response']['provenance']['gt_read'] = {'true': True, 'string': 'false', 'zero': 0, 'null': None}[mutation]
    raw = b' \n' + encode(doc) + b'\n'
    pins = {'SYNTHETIC/frozen.json': sha(raw)}
    put(root, 'payload/baseline.json', b'[' + raw + b']\n')
    (root / 'frozen/baseline.json').unlink()
    path = root / 'MANIFEST.json'; manifest = json.loads(path.read_bytes()); manifest['source_pins'] = pins
    path.write_bytes(encode(manifest)); repin(root)
    return root, pins


def test_false_flag_exact_pinned_collection_passes_directory_and_zip(tmp_path):
    root, pins = false_flag_fixture(tmp_path)
    before = (root / 'payload/baseline.json').read_bytes()
    output = tmp_path / 'SYNTHETIC.zip'; make_zip(root, output)
    for pack in (root, output):
        assert check(root, pack=pack, pins=pins)['status'] == 'VALID'
    assert (root / 'payload/baseline.json').read_bytes() == before


@pytest.mark.parametrize('mutation', ['true', 'string', 'zero', 'null', 'wrong-path', 'extra-key', 'string-bait'])
def test_false_flag_restrictions_even_with_matching_test_pin(tmp_path, mutation):
    root, pins = false_flag_fixture(tmp_path, mutation)
    assert check(root, pins=pins)['code'] == 'FORBIDDEN_CONTENT'


def test_false_flag_unpinned_bytes_and_unlisted_location_rejected(tmp_path):
    root, pins = false_flag_fixture(tmp_path)
    path = root / 'payload/baseline.json'
    before = path.read_bytes()
    path.write_bytes(before.replace(b'SYNTHETIC_ONLY', b'SYNTHETIC_CHANGED')); repin(root)
    assert check(root, pins=pins)['code'] == 'FORBIDDEN_CONTENT'
    path.write_bytes(before)
    path.rename(root / 'frozen/baseline.json'); repin(root)
    assert check(root, pins=pins)['code'] == 'FORBIDDEN_CONTENT'


def test_false_flag_without_production_profile_is_rejected(tmp_path):
    root, pins = false_flag_fixture(tmp_path)
    checker = module(); checker.TEAM_EVAL_SOURCE_PINS = pins
    with pytest.raises(checker.PackCheckError, match='FORBIDDEN_CONTENT'):
        checker.scan({'payload/baseline.json': (root / 'payload/baseline.json').read_bytes()})

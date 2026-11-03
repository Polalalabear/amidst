"""D112-1 Baseline-only projection tests, all inputs SYNTHETIC; no actual P1 acceptance."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from amidst.q1q5 import team_eval_pack as pack
from test_check_handoff_pack import module as handoff_checker

DATA = Path(__file__).parents[1] / 'fixtures/team_eval_pack/SYNTHETIC/baseline.frozen.SYNTHETIC.json'


def build(tmp_path, **kwargs):
    ref = {'baseline': {'path': DATA, 'sha256': pack.sha(DATA.read_bytes())}}
    return pack.build_pack(tmp_path / 'SYNTHETIC-baseline', ref, profile=pack.BASELINE, **kwargs)


def run(result):
    root = Path(result['root'])
    command = [sys.executable, '-I', str(root / 'tools/team_eval.py'), '--profile', pack.BASELINE,
               '--manifest-sha256', result['manifest_sha256']]
    completed = subprocess.run(command, cwd=root.parent, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    return root, json.loads((root / pack.RETURN).read_bytes())


def test_baseline_only_native_replay_and_return_are_valid(tmp_path):
    result = build(tmp_path)
    manifest = result['manifest']
    assert manifest['halves'] == ['baseline'] and manifest['editable_files'] == {}
    assert manifest['source_class'] == 'ENGINEERING' and manifest['evaluation_eligible'] is False
    root, returned = run(result)
    assert (root / returned['return_files']['baseline']).read_bytes() == DATA.read_bytes()
    assert returned['halves'] == {'baseline': {'status': 'COMPLETE'}}
    assert set(returned['output_sha256']) == set(returned['return_files']) == {'baseline'}
    assert pack.validate_return(root, root / pack.RETURN, result['manifest_sha256'], profile=pack.BASELINE)['status'] == 'VALID'
    assert not any('complex' in p.name for p in root.rglob('*'))


def test_native_baseline_return_is_readable_by_shared_profile(tmp_path):
    result = build(tmp_path)
    archive = tmp_path / 'SYNTHETIC.zip'
    pack.write_zip(result['root'], archive)
    root, _ = run(result)
    checker = handoff_checker()
    # Explicit TEST-only inventory; never selects or changes production constants.
    checker.TEAM_EVAL_SOURCE_PINS = result['manifest']['source_pins']
    checked = checker.inspect_pack(archive, profile='team-eval',
        manifest_sha256=result['manifest_sha256'], returned_json=root / pack.RETURN)
    assert checked['status'] == 'VALID' and checked['returned_json_checked'] is True
    assert checked['release_authorized'] is False and checked['return_payload_bytes_verified'] is False


@pytest.mark.parametrize('field', ['halves', 'output_sha256', 'return_files', 'root'])
def test_complex_presence_is_invalid_even_when_other_fields_are_valid(tmp_path, field):
    result = build(tmp_path)
    root, returned = run(result)
    if field == 'halves':
        returned[field]['complex'] = {'status': 'COMPLETE'}
    elif field == 'root':
        returned['complex'] = None
    else:
        returned[field]['complex'] = None
    checked = pack.validate_return_document(returned, manifest_sha256=result['manifest_sha256'],
              halves=['baseline'], profile=pack.BASELINE, root=root)
    assert checked['status'] == 'INVALID' and checked['reason_category'] == 'HALF_NOT_IN_PACK'


@pytest.mark.parametrize('field,reason', [('pack_manifest_sha256', 'MANIFEST_PIN_MISMATCH'),
                                        ('environment', 'ENVIRONMENT_INVALID'),
                                        ('output_sha256', 'RETURN_FIELDS_MISSING')])
def test_required_return_metadata_is_checked_before_files(tmp_path, field, reason):
    result = build(tmp_path)
    root, returned = run(result)
    del returned[field]
    checked = pack.validate_return_document(returned, manifest_sha256=result['manifest_sha256'],
              halves=['baseline'], profile=pack.BASELINE, root=root)
    assert checked['status'] == 'INVALID' and checked['reason_category'] == reason


def test_halves_cannot_disagree_with_manifest(tmp_path):
    result = build(tmp_path)
    root, returned = run(result)
    returned['halves'] = []
    assert pack.validate_return_document(returned, manifest_sha256=result['manifest_sha256'],
        halves=['baseline'], profile=pack.BASELINE, root=root)['reason_category'] == 'HALF_NOT_IN_PACK'


@pytest.mark.parametrize('kwargs', [{'version': 'v1'}, {'evaluation_eligible': True}])
def test_formal_flags_remain_unselected(tmp_path, kwargs):
    with pytest.raises(pack.PackError, match='PROFILE_UNSELECTED'):
        build(tmp_path, **kwargs)
    assert not (tmp_path / 'SYNTHETIC-baseline').exists()


def test_modified_manifest_cannot_select_formal_or_complex(tmp_path):
    result = build(tmp_path)
    root = Path(result['root'])
    for update, reason in [({'version': 'v1'}, 'PROFILE_UNSELECTED'),
                           ({'evaluation_eligible': True}, 'PROFILE_UNSELECTED'),
                           ({'halves': ['baseline', 'complex']}, 'HALF_NOT_IN_PACK')]:
        changed = copy.deepcopy(result['manifest'])
        changed.update(update)
        raw = pack.encode(changed)
        (root / 'MANIFEST.json').write_bytes(raw)
        checked = pack.verify_pack(root, pack.sha(raw), profile=pack.BASELINE)
        assert checked['status'] == 'INVALID' and checked['reason_category'] == reason


def test_zip_is_deterministic_and_manifest_bytes_are_stable(tmp_path):
    first = build(tmp_path)
    another = tmp_path / 'another'
    another.mkdir()
    second = build(another)
    assert first['manifest_sha256'] == second['manifest_sha256']
    pin1 = pack.write_zip(first['root'], tmp_path / 'first.zip')
    pin2 = pack.write_zip(second['root'], tmp_path / 'second.zip')
    assert pin1 == pin2


def test_baseline_collection_preserves_all_source_bytes_and_pins(tmp_path):
    raw = DATA.read_bytes()
    refs = [{'path': DATA, 'sha256': pack.sha(raw), 'source_name': name}
            for name in ['SYNTHETIC/a.json', 'SYNTHETIC/b.json']]
    result = pack.build_pack(tmp_path / 'SYNTHETIC-collection', {'baseline': refs}, profile=pack.BASELINE)
    assert result['manifest']['source_pins'] == {ref['source_name']: ref['sha256'] for ref in refs}
    root, returned = run(result)
    output = (root / returned['return_files']['baseline']).read_bytes()
    assert output == b'[' + raw + b',' + raw + b']\n'
    assert len(json.loads(output)) == 2


@pytest.mark.parametrize('payload', [b'{"depth":1}', b'{"\\u0064epth":1}', b'{"location":"/Users/example"}',
                                    b'{"GT":1}', b'{"\\u0047T":1}'])
def test_plain_and_escaped_forbidden_payload_is_rejected(payload):
    with pytest.raises(pack.PackError, match='FORBIDDEN_CONTENT'):
        pack.scan_payload(payload)

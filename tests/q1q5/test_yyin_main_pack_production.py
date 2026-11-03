"""D105 s2 pilot path and neutral labels; all fixtures remain TEST-ONLY."""
import importlib.util
import json
from pathlib import Path
import sys
import struct
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_handoff_pack as checker
from make_synthetic_yyin_pack_inputs import make
from amidst.q1q5 import yyin_main_pack as builder


@pytest.fixture
def inputs(tmp_path):
    config = json.loads(make(tmp_path / 'SYNTHETIC_INPUTS').read_bytes())
    return config


def selected_test_only_pins(monkeypatch, config):
    monkeypatch.setattr(builder, 'PINS', {name: config[name]['sha256'] for name in builder.PINS})
    monkeypatch.setattr(builder, 'SOURCE_MANIFEST', config['source_pack']['manifest_sha256'])
    freeze = json.loads(Path(config['catalog_receipt']['path']).read_bytes())
    monkeypatch.setattr(builder, 'CATALOG', freeze['catalog_sha256'])


def test_real_path_requires_the_frozen_sources_before_any_output(inputs, tmp_path):
    with pytest.raises(builder.PackError, match='UNSELECTED_SOURCE_PACK'):
        builder.build_pack(tmp_path / 'REJECTED', inputs=inputs)
    assert not (tmp_path / 'REJECTED').exists()


@pytest.mark.parametrize('version,eligible', [('v1', True), ('v1', False), ('v0-pilot', True)])
def test_unselected_version_or_formal_eligibility_fails_before_output(inputs, tmp_path, version, eligible):
    with pytest.raises(builder.PackError, match='CONTRACT_UNSELECTED'):
        builder.build_pack(tmp_path / 'REJECTED', inputs=inputs, version=version, evaluation_eligible=eligible)
    assert not (tmp_path / 'REJECTED').exists()


def test_selected_pilot_keeps_wire_neutral_camera_names_and_sources_immutable(inputs, tmp_path, monkeypatch):
    selected_test_only_pins(monkeypatch, inputs)
    source = Path(inputs['source_pack']['path'])
    before = {p: p.read_bytes() for p in source.rglob('*') if p.is_file()}
    receipt = builder.build_pack(tmp_path / 'TEST_ONLY_PILOT', inputs=inputs)
    root = Path(receipt['pack_path'])
    manifest = json.loads((root / 'MANIFEST.json').read_bytes())
    assert manifest['version'] == 'v0-pilot' and manifest['evaluation_eligible'] is False
    data = json.loads((root / 'DATA.json').read_bytes())
    assert [c['camera_id'] for c in data['cameras']] == [f'鏡頭{i}' for i in range(1, 9)]
    for path in root.rglob('*'):
        if path.is_file() and path.suffix != '.png':
            assert not any(cam.encode() in path.read_bytes() for cam in builder.CAMERAS)
    assert len(receipt['camera_aliases']) == 8 and receipt['release_authorized'] is False
    assert all(path.read_bytes() == raw for path, raw in before.items())
    monkeypatch.setattr(checker, 'YYIN_SOURCE_PINS', manifest['source_pins'])
    checked = checker.inspect_pack(Path(receipt['zip_path']), profile='yyin-main', manifest_sha256=receipt['manifest_sha256'])
    assert checked['status'] == 'VALID' and checked['production_profile'] == 'yyin-main'
    assert checked['release_authorized'] is False and checked['human_approval_verified'] is False
    assert checker.inspect_pack(root, profile='yyin-main')['code'] == 'PROFILE_UNSELECTED'


def test_checker_columns_equal_importer_wire_verbatim():
    spec = importlib.util.spec_from_file_location('return_importer', ROOT / 'scripts/import_team_review_pack.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert checker.TEXT_COLUMNS == module.TEXT_COLUMNS
    assert checker.REVIEW_COLUMNS == module.REVIEW_COLUMNS


def test_png_sanitization_preserves_idat_bytes_and_original_input(inputs):
    original = (Path(inputs['source_pack']['path']) / 'images/static/CAM_ENTRY.png').read_bytes()
    tag, text = b'tEXt', b'Comment\x00private test metadata'
    chunk = struct.pack('>I', len(text)) + tag + text + struct.pack('>I', zlib.crc32(tag + text))
    marked = original[:-12] + chunk + original[-12:]
    assert builder.public_png(marked) == original
    assert marked.endswith(original[-12:]) and chunk in marked

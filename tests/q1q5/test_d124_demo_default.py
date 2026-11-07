"""Synthetic boundaries for the explicitly non-formal D124 demo adapter."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from amidst.q1q5 import demo_default_index as demo


def raw(value):
    return json.dumps(value, sort_keys=True).encode()


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = tmp_path / 'safe'
    root.mkdir()
    inventory, paths = {}, []
    def put(name, value, binary=False):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value if binary else raw(value))
        inventory[name] = demo.sha(p.read_bytes())
        return inventory[name]
    catalog = put('provenance/camera_catalog.json', {'cameras': [{'camera_id': 'SYN_CAM', 'width': 960, 'height': 540}]})
    for label in ['A4-1', 'B4-1']:
        run = 'SYNTHETIC-' + label
        rgb = f'rgb/{run}/SYN_CAM/frame_000000.png'
        pin = put(rgb, b'SYNTHETIC_PIXEL_BYTES', True)
        clock = f'clocks/{label}.json'
        clock_pin = put(clock, {'run_id': run, 'clock_id': 'clock:' + run, 'source_duration_us': 200000})
        desc = f'runs/{label}.json'
        desc_pin = put(desc, {'run_id': run, 'clock_ref': clock, 'catalog_sha256': catalog,
            'camera_ids': ['SYN_CAM'], 'sampling': {'fps': 5}, 'frames': [
                {'camera_id': 'SYN_CAM', 'frame_index': 0, 'filename': rgb, 'file_sha256': pin}]})
        paths.append(desc)
        if label == 'A4-1':
            cfg = {'profile': 'DEMO_DEFAULT', 'formal_eligible': False, 'run_descriptor': desc,
                'run_descriptor_sha256': desc_pin, 'clock_sha256': clock_pin, 'catalog_sha256': catalog,
                'run_id': run, 'clock_id': 'clock:' + run, 'scene_id': 'SYNTHETIC_SCENE', 'scene_revision': 'r004'}
    bundle = raw({'files': inventory, 'runs': paths})
    (root / 'MANIFEST.json').write_bytes(bundle)
    monkeypatch.setattr(demo, 'EXPECTED_BUNDLE_SHA256', demo.sha(bundle))
    cfg['safe_manifest_sha256'] = demo.sha(bundle)
    return root, cfg


def test_projection_only_opens_pinned_metadata(fixture, monkeypatch):
    root, cfg = fixture
    seen = []
    read = demo.read_pinned
    def observe(*a, **kw):
        seen.append(a[1]); return read(*a, **kw)
    monkeypatch.setattr(demo, 'read_pinned', observe)
    run = demo.D124DemoRun(root, cfg)
    assert not any(x.endswith('.png') for x in seen)
    assert run.source_projection['formal_eligible'] is False
    assert run.source_projection['profile'] == 'DEMO_DEFAULT'
    assert run.read_rgb('SYN_CAM', 0) == b'SYNTHETIC_PIXEL_BYTES'


@pytest.mark.parametrize('field,value', [('profile', 'APPROVED'), ('formal_eligible', True),
    ('safe_manifest_sha256', '0'*64), ('run_descriptor_sha256', '0'*64),
    ('clock_sha256', '0'*64), ('catalog_sha256', '0'*64), ('run_id', 'OTHER'), ('clock_id', 'OTHER')])
def test_binding_and_authority_fail_closed(fixture, field, value):
    root, cfg = fixture
    with pytest.raises(demo.DemoIndexError): demo.D124DemoRun(root, {**cfg, field: value})


def test_pixel_change_rejected(fixture):
    root, cfg = fixture
    run = demo.D124DemoRun(root, cfg)
    (root / f'rgb/{cfg["run_id"]}/SYN_CAM/frame_000000.png').write_bytes(b'changed')
    with pytest.raises(demo.DemoIndexError, match='PIN_MISMATCH'): run.read_rgb('SYN_CAM', 0)


def test_symlink_rejected_before_any_pixel_read(fixture):
    root, cfg = fixture
    p = root / f'rgb/{cfg["run_id"]}/SYN_CAM/frame_000000.png'
    other = root.parent / 'other.png'
    other.write_bytes(p.read_bytes())
    p.unlink(); p.symlink_to(other)
    with pytest.raises(demo.DemoIndexError, match='SYMLINK'): demo.D124DemoRun(root, cfg)


@pytest.mark.parametrize('name', ['../outside.json', 'gt_private/x.json', '/absolute.json', 'rgb/../../x.json'])
def test_forbidden_paths_never_opened(tmp_path, name):
    with pytest.raises(demo.DemoIndexError): demo.safe_path(tmp_path, name)


def test_disk_gate(fixture, monkeypatch):
    root, cfg = fixture
    run = demo.D124DemoRun(root, cfg)
    monkeypatch.setattr(demo.shutil, 'disk_usage', lambda _: SimpleNamespace(free=demo.MIN_FREE_BYTES-1))
    with pytest.raises(demo.DemoIndexError, match='LOW_DISK'): run.read_rgb('SYN_CAM', 0)

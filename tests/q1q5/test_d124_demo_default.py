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


def checker_module():
    import importlib.util
    p = Path(__file__).resolve().parents[2] / 'scripts/check_d124_demo_default.py'
    spec = importlib.util.spec_from_file_location('_demo_checker_test', p)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def synthetic_tracking_input():
    params = {'link_max_gap_us':600000, 'link_max_gap_samples':2, 'link_iou_min':0.3,
        'link_center_dist_max_diag_ratio':0.5, 'link_min_score':0.4,
        'link_color_rule':'NOT_NONE', 'link_ambiguity_margin':0.05}
    cfg = {'run_id':'SYNTHETIC_RUN', 'clock_id':'SYNTHETIC_CLOCK', 'stride_samples':1,
        'index_grid_origin_frame':0, 'parameters':[{'name':k,'value':v,'status':'DEMO_DEFAULT'} for k,v in params.items()]}
    manifest = {'index_id':'detidx:r004:SYNTHETIC_RUN:0123456789abcdef',
        'sampling':{'per_camera':[{'camera_id':'SYN_CAM'}]}}
    rows = []
    for i in [0,1]:
        rows.append({'frame_ref':f'SYNTHETIC_FRAME_{i}','camera_id':'SYN_CAM','frame_index':i,
            'timestamp_us':200000*i,'frame_state':'INFERRED', 'detections':[
                {'observation_id':f'obs:0123456789abcdef:SYN_CAM:{i}:0', 'class_label':'person',
                 'score':0.9,'bbox_xyxy_px':[0,0,20,40],'color':None}]})
    return cfg,manifest,rows


def test_demo_local_linker_does_not_claim_cross_camera_identity():
    module=checker_module();cfg,manifest,rows=synthetic_tracking_input()
    doc=module.local_rule_tracks(manifest,b'\n'.join(raw(r) for r in rows),cfg)
    assert doc['formal_eligible'] is False
    assert doc['cross_camera_association']=='NOT_EVALUATED'
    assert doc['tracks'][0]['steps'][0]['state']=='PLAYING'


def test_ambiguous_first_seed_is_unknown():
    module=checker_module();cfg,manifest,rows=synthetic_tracking_input()
    other={**rows[0]['detections'][0], 'observation_id':'obs:0123456789abcdef:SYN_CAM:0:1'}
    rows[0]['detections'].append(other)
    doc=module.local_rule_tracks(manifest,b'\n'.join(raw(r) for r in rows),cfg)
    assert doc['tracks'][0]['status']=='UNKNOWN_AMBIGUOUS_SEED'
    assert doc['tracks'][0]['seed'] is None


def test_checker_rejects_changed_record_bytes(tmp_path):
    module=checker_module();cfg,manifest,rows=synthetic_tracking_input()
    record_raw=b'\n'.join(raw(r) for r in rows)
    manifest.update(scene_id='SYNTHETIC',run_id=cfg['run_id'],clock_id=cfg['clock_id'],scene_revision='r004',
        detector={'index_score_floor':0.3},records_file_sha256=demo.sha(record_raw))
    cfg.update(scene_id='SYNTHETIC',scene_revision='r004',index_score_floor=0.3)
    index_raw=raw(manifest)
    receipt={'profile':'DEMO_DEFAULT','formal_eligible':False,'index_manifest_sha256':demo.sha(index_raw),
        'records_file_sha256':demo.sha(record_raw)}
    (tmp_path/'demo_default_receipt.json').write_bytes(raw(receipt))
    (tmp_path/'detection_index.json').write_bytes(index_raw)
    (tmp_path/'detection_index.records.jsonl').write_bytes(record_raw+b'\n')
    with pytest.raises(demo.DemoIndexError,match='RECORDS_BYTE_PIN'):
        module.read_bound(tmp_path,cfg)

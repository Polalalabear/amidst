"""#415 focused CLI/path/pin tests. Synthetic inputs; no Blender/model/GT reads."""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
common = importlib.import_module('r004_local_common')
renderer = importlib.import_module('render_cx7')
projector = importlib.import_module('project_cx7_safe_bundle')
SCRIPTS = ['build_preview', 'build_static_v2', 'render_previews', 'measure_preview',
           'render_cx7', 'project_cx7_safe_bundle']


@pytest.mark.parametrize('script', SCRIPTS)
def test_help_without_blender_or_model(script, tmp_path):
    result = subprocess.run([sys.executable, '-S', str(ROOT / 'scripts' / f'{script}.py'), '--help'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--execute' in result.stdout and '--output' in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('script', ['build_preview', 'build_static_v2', 'render_previews'])
def test_unauthorized_build_and_preview_do_not_open_source(script, tmp_path):
    module = importlib.import_module(script)
    with pytest.raises(ValueError, match='EXECUTION_AUTHORIZATION_REQUIRED'):
        module.main(['--source', str(tmp_path / 'absent.blend'), '--output', str(tmp_path / 'new')])
    assert not (tmp_path / 'new').exists()


def test_measure_requires_authorization_before_opening_inputs(tmp_path):
    module = importlib.import_module('measure_preview')
    with pytest.raises(ValueError, match='EXECUTION_AUTHORIZATION_REQUIRED'):
        module.main(['--index', str(tmp_path/'index.json'), '--index-sha256', 'a'*64,
                     '--official-zip', str(tmp_path/'code.zip'), '--model-source', str(tmp_path/'code'),
                     '--weights', str(tmp_path/'weights.pth'), '--output', str(tmp_path/'new')])
    assert not list(tmp_path.iterdir())


def test_measure_reporting_percentiles_preserve_missing():
    module = importlib.import_module('measure_preview')
    assert module.percentile([], .5) is None
    assert module.percentile([10, 30, 20, 40], .25) == 17.5


@pytest.mark.parametrize('name', ['gt_private/a.json', 'GT/source.json', 'trajectory/a.json',
                                 'visibility.json', '../escape.json', '/absolute.json', 'C:\\escape.json'])
def test_rejected_manifest_paths_do_not_open_files(name, tmp_path):
    with pytest.raises(ValueError):
        projector.child(tmp_path, name)


def test_symlink_and_existing_output_are_rejected(tmp_path):
    source = tmp_path/'original'
    source.mkdir()
    link = tmp_path/'alias'
    link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match='SYMLINK'):
        common.checked_path(link/'file')
    with pytest.raises(ValueError, match='OUTPUT_ALREADY_EXISTS'):
        common.new_output(source)


def test_pinned_read_preserves_input_and_rejects_wrong_hash(tmp_path):
    p = tmp_path/'source.json'
    p.write_bytes(b'{"synthetic": true}')
    pin = common.file_sha(p)
    assert common.pinned(p, pin) == p.read_bytes()
    with pytest.raises(ValueError, match='INPUT_SHA256_MISMATCH'):
        common.pinned(p, '0'*64)
    assert common.file_sha(p) == pin


def test_disk_floor_and_reserve(monkeypatch, tmp_path):
    from types import SimpleNamespace
    monkeypatch.setattr(common.shutil, 'disk_usage', lambda _: SimpleNamespace(free=common.MIN_FREE_BYTES))
    assert common.disk(tmp_path) == common.MIN_FREE_BYTES
    with pytest.raises(ValueError, match='DISK_BELOW'):
        common.disk(tmp_path, 1)


@pytest.mark.parametrize('scenario,frames,cameras', [('A4-1',250,4),('B4-1',210,5)])
def test_renderer_reads_only_repo_authoring_and_safe_camera_pins(scenario, frames, cameras, capsys):
    freeze, scope, plan, catalog, clock = renderer.load_inputs(ROOT, scenario,
        ROOT/'configs/q1q5/authoring/r004_v2_static_cameras.json')
    assert scope['source_duration_us']//scope['sample_interval_us'] == frames
    assert len(plan['render_camera_ids']) == cameras
    renderer.main(['--scenario',scenario,'--check-only'])
    result=json.loads(capsys.readouterr().out)
    assert result['rendered'] is False and result['status']=='INPUT_PINS_VERIFIED'


def test_renderer_missing_static_front_stops_before_blender_or_source(tmp_path):
    with pytest.raises(ValueError,match='STATIC_MODEL_INPUT_REQUIRED'):
        renderer.main(['--scenario','A4-1','--execute','--authorization-ref','SYNTHETIC_ONLY',
                       '--source',str(tmp_path/'absent.blend'),'--output',str(tmp_path/'new')])
    assert not list(tmp_path.iterdir())


def test_authored_interpolation_turn_stop_and_boundaries():
    points = [{'planned_source_time_us': t, 'foot_anchor_world_m': p} for t,p in
              [(0,[0,0,0]),(10,[2,0,0]),(20,[2,0,0]),(30,[2,2,0])]]
    renderer.validate_points(points,30)
    assert renderer.sample_pose(points,5,'+X') == ([1.,0.,0.],0.)
    assert renderer.sample_pose(points,15,'+X') == ([2.,0.,0.],0.)
    position,yaw=renderer.sample_pose(points,20,'+X')
    assert position==[2.,0.,0.] and yaw==pytest.approx(renderer.math.pi/2)
    with pytest.raises(ValueError,match='NO_EXTRAPOLATION'):
        renderer.sample_pose(points,30,'+X')
    with pytest.raises(ValueError,match='STATIC_FRONT_AXIS_REQUIRED'):
        renderer.sample_pose(points,5,'UNKNOWN')


def test_control_point_validation_rejects_unsorted_or_nonfinite():
    points=[{'planned_source_time_us':0,'foot_anchor_world_m':[0,0,0]},
            {'planned_source_time_us':0,'foot_anchor_world_m':[0,0,0]}]
    with pytest.raises(ValueError,match='CONTROL_TIME_INVALID'):
        renderer.validate_points(points,10)
    points[1]={'planned_source_time_us':10,'foot_anchor_world_m':[0,float('nan'),0]}
    with pytest.raises(ValueError,match='CONTROL_POINT_INVALID'):
        renderer.validate_points(points,10)


def png_chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))


def test_new_producer_sanitizes_png_without_changing_pixels():
    ihdr=png_chunk(b'IHDR',struct.pack('>IIBBBBB',960,540,8,2,0,0,0))
    compressed=zlib.compress((b'\x00'+b'\x10\x20\x30'*960)*540)
    idat=png_chunk(b'IDAT',compressed)
    raw=b'\x89PNG\r\n\x1a\n'+ihdr+png_chunk(b'tEXt',b'synthetic\0metadata')+idat+png_chunk(b'IEND',b'')
    clean=renderer.sanitize_png(raw)
    assert b'tEXt' not in clean and idat in clean
    with pytest.raises(ValueError,match='PNG_CRC_INVALID'):
        renderer.sanitize_png(raw[:-1]+bytes([raw[-1]^1]))


def test_safe_projection_requires_authorization_before_reading(tmp_path):
    with pytest.raises(ValueError, match='EXECUTION_AUTHORIZATION_REQUIRED'):
        projector.main(['--source-bundle',str(tmp_path/'source'),'--receipt',str(tmp_path/'receipt.json'),
                        '--receipt-sha256','0'*64,'--output',str(tmp_path/'new')])
    assert not list(tmp_path.iterdir())


def test_static_camera_copy_preserves_historical_bytes_and_math():
    path=ROOT/'configs/q1q5/authoring/r004_v2_static_cameras.json'
    assert common.file_sha(path)=='3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f'
    doc=json.loads(path.read_bytes())
    assert doc['run_bindings']==[] and len(doc['cameras'])==8
    for camera in doc['cameras']:
        pin=camera['calibration_sha256']
        assert common.canonical_hash({k:v for k,v in camera.items() if k!='calibration_sha256'})==pin
        assert camera['fx']==pytest.approx(960*camera['focal_length_mm']/camera['sensor_width_mm'])
        assert camera['static_validity']['status']=='NOT_EVALUATED'
        assert camera['convention']=='BLENDER_NEG_Z_UP_Y'


def test_new_render_refuses_to_invent_a_clock_before_opening_source(tmp_path):
    with pytest.raises(ValueError, match='NEW_CLOCK_DECLARATION_REQUIRED'):
        renderer.main(['--scenario','A4-1','--execute','--authorization-ref','SYNTHETIC_ONLY',
            '--source',str(tmp_path/'absent.blend'),'--output',str(tmp_path/'new'),
            '--run-id','NEW_SYNTHETIC_RUN','--actor-prefix','SYNTHETIC_MODEL',
            '--front-axis','+X','--front-axis-ref','SYNTHETIC_STATIC_DECISION'])
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('change,code', [({'run_id':'FOREIGN'},'NEW_CLOCK_SCOPE_MISMATCH'),
    ({'clock_id':'OLD_CLOCK'},'NEW_CLOCK_SCOPE_MISMATCH'),
    ({'wall_origin':'OTHER_MAPPING'},'CLOCK_MAPPING_CHANGED')])
def test_new_clock_scope_rejected_before_blender_or_source(change, code, tmp_path, monkeypatch):
    old={'run_id':'OLD_RUN','clock_id':'OLD_CLOCK','mapping_kind':'DECLARED_DEMO_CLOCK',
         'timezone':'Asia/Taipei','wall_origin':'2026-11-01T14:00:00+08:00',
         't0_us':0,'rate':1,'source_duration_us':100}
    monkeypatch.setattr(renderer,'load_inputs',lambda *a: ({},{},
        {'declared_run_context':{'run_id':'OLD_RUN'}},{},old))
    clock=tmp_path/'configs/q1q5/clocks/new.json'
    clock.parent.mkdir(parents=True)
    clock.write_text(json.dumps({**old,'run_id':'NEW_RUN','clock_id':'NEW_CLOCK',**change}))
    with pytest.raises(ValueError,match=code):
        renderer.main(['--scenario','A4-1','--execute','--authorization-ref','SYNTHETIC_ONLY',
            '--repo',str(tmp_path),'--source',str(tmp_path/'absent.blend'),'--output',str(tmp_path/'new'),
            '--run-id','NEW_RUN','--clock',str(clock),'--clock-sha256',common.file_sha(clock),
            '--actor-prefix','SYNTHETIC_MODEL','--front-axis','+X','--front-axis-ref','SYNTHETIC_STATIC_DECISION'])
    assert not (tmp_path/'new').exists()

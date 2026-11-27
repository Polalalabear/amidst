"""E6 formal detection wrapper: manifest verification, isolation, parity gate, receipt. Synthetic files and a fake index.py runner
(no torch, no weights, no GT)."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e6_detect_formal', ROOT / 'scripts/evaluation/e6_detect_formal.py')
D = importlib.util.module_from_spec(_spec)
sys.modules['e6_detect_formal'] = D
_spec.loader.exec_module(D)

CAMS = ['CAM_A', 'CAM_B']
DETECTOR = {'family': 'RT-DETR', 'device': 'mps', 'weights_file_sha256': 'w' * 64, 'index_score_floor': 0.05,
            'class_map': {'content_sha256': 'c' * 64}, 'config_sha256': 'k' * 64}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def make_recording(tmp, cases=('E6-S01', 'E6-S02'), n=3):
    rec = tmp / 'rec'
    lines = {}
    for cid in cases:
        wire = []
        for t in range(n + 1):
            frames = []
            for cam in CAMS:
                rel = f'pixels/{cid}/{t:05d}-{cam}.jpg'
                p = rec / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(f'{cid}{t}{cam}'.encode())
                frames.append({'cam': cam, 'bytes': 5, 'sha256': sha(p.read_bytes()), 'path': rel})
            wire.append({'tick': t, 'frames': frames})
        (rec / f'{cid}.replay1.wire.json').write_text(json.dumps(wire))
        (rec / f'{cid}.case.json').write_text('{"expected": "GT"}')           # GT-bearing files that must never be cloned
        (rec / 'gt-boxes').mkdir(exist_ok=True)
        (rec / 'gt-boxes' / f'{cid}.a-log.json').write_text('{"gt_boxes": 1}')
    (rec / 'e6_scenarios_frozen_v1.json').write_text(json.dumps({'formal_cases': [{'case_id': c} for c in cases]}))
    for p in sorted(rec.rglob('*')):
        if p.is_file():
            lines[p.relative_to(rec).as_posix()] = sha(p.read_bytes())
    (rec / 'MANIFEST.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in lines.items()))
    return rec


def fake_runner(detector=None, extra_key=False):
    def runner(out, models, cases, device, deps):
        for cid in cases:
            d = out / 'indexes' / cid
            d.mkdir(parents=True)
            rec_line = {'frame_index': 0, 'camera_id': 'CAM_A', 'rgb_file_sha256': 'x', 'detections': [
                {'class_label': 'person', 'score': 0.9, 'bbox_xyxy_px': [1, 2, 3, 4]}]}
            (d / 'detection_index.records.jsonl').write_text(json.dumps(rec_line) + '\n')
            doc = {'schema_version': 's', 'scene_revision': 'r', 'detector': detector or DETECTOR, 'color_method': {'version': 'upper-hsv-v1'},
                   'sampling': {'fps': 5, 'image_size_px': [320, 180]}, 'records_ref': 'detection_index.records.jsonl',
                   'content_sha256': 'i' * 64, 'rgb_index_sha256': 'g' * 64, 'run_id': cid, **({'extra': 1} if extra_key else {})}
            (d / 'detection_index.json').write_text(json.dumps(doc))
            (d / 'production.json').write_text(json.dumps({'frames': 8, 'elapsed_s': 1.23, 'gt_read': False,
                                                           'index_file_sha256': 'f' * 64, 'records_file_sha256': 'r' * 64}))
    return runner


def reference(tmp):
    d = tmp / 'ref'
    d.mkdir()
    (d / 'detection_index.records.jsonl').write_text(json.dumps({'frame_index': 0, 'camera_id': 'CAM_A', 'rgb_file_sha256': 'x', 'detections': [
        {'class_label': 'person', 'score': 0.5, 'bbox_xyxy_px': [0, 0, 1, 1]}]}) + '\n')
    (d / 'detection_index.json').write_text(json.dumps({'schema_version': 's', 'scene_revision': 'r', 'detector': DETECTOR,
                                                        'color_method': {'version': 'upper-hsv-v1'}, 'sampling': {'fps': 5, 'image_size_px': [320, 180]},
                                                        'records_ref': 'detection_index.records.jsonl', 'content_sha256': 'z', 'rgb_index_sha256': 'y',
                                                        'run_id': 'E3-A1'}))
    return d / 'detection_index.json'


def args(tmp, rec, **kw):
    models = tmp / 'models'
    models.mkdir(exist_ok=True)
    (models / 'rtdetr_r18vd_dec3_6x_coco_from_paddle.pth').write_bytes(b'weights')
    ns = dict(recording=rec, out=tmp / 'det', models=models, runtime_deps=None, spec=None, reference_index=None, cases=None,
              device='mps', min_free_gib=0.0)
    ns.update(kw)
    return type('A', (), ns)()


def patch_weights(monkeypatch, tmp):
    ref = reference(tmp)
    d = json.loads(ref.read_text())
    d['detector'] = DETECTOR | {'weights_file_sha256': sha(b'weights')}
    ref.write_text(json.dumps(d))
    detector = DETECTOR | {'weights_file_sha256': sha(b'weights')}
    return ref, detector


def test_clones_only_wire_and_pixels_never_case_or_gt(tmp_path, monkeypatch):
    rec = make_recording(tmp_path)
    monkeypatch.setattr(D, 'git_head', lambda: 'a' * 40)
    r = D.run(args(tmp_path, rec), runner=fake_runner())
    out = tmp_path / 'det'
    names = {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
    assert 'E6-S01.replay1.wire.json' in names and 'pixels/E6-S01/00000-CAM_A.jpg' in names
    assert not any('case.json' in n or 'a-log' in n or 'gt-boxes' in n or 'frozen' in n for n in names - {'DETECTION_RECEIPT.json'} if not n.startswith('indexes'))
    assert D.isolation_violations(out) == []
    assert set(r['cases']) == {'E6-S01', 'E6-S02'} and r['gt_read'] is False and r['paid_calls'] == 0
    assert (tmp_path / 'rec/E6-S01.case.json').read_text() == '{"expected": "GT"}'       # recording untouched


def test_manifest_mismatch_and_missing_stop_before_detection(tmp_path):
    rec = make_recording(tmp_path)
    called = []
    (rec / 'pixels/E6-S01/00001-CAM_B.jpg').write_bytes(b'tampered')
    with pytest.raises(D.DetectionError, match='MANIFEST_SHA_MISMATCH'):
        D.run(args(tmp_path, rec), runner=lambda *a: called.append(1))
    assert not called
    rec2 = make_recording(tmp_path / 'b')
    lines = [ln for ln in (rec2 / 'MANIFEST.sha256').read_text().splitlines() if '00002-CAM_A' not in ln or 'S02' in ln]
    (rec2 / 'MANIFEST.sha256').write_text('\n'.join(lines) + '\n')
    with pytest.raises(D.DetectionError, match='NOT_IN_MANIFEST'):
        D.run(args(tmp_path / 'b', rec2), runner=lambda *a: called.append(1))


def test_unknown_case_and_disk_guard(tmp_path):
    rec = make_recording(tmp_path)
    with pytest.raises(D.DetectionError, match='NOT_FORMAL_CASES'):
        D.run(args(tmp_path, rec, cases=['E3-A1']), runner=fake_runner())
    with pytest.raises(D.DetectionError, match='DISK_LOW'):
        D.run(args(tmp_path, rec, min_free_gib=10 ** 9), runner=fake_runner())


def test_parity_ok_then_receipt_fields(tmp_path, monkeypatch):
    rec = make_recording(tmp_path)
    ref, detector = patch_weights(monkeypatch, tmp_path)
    monkeypatch.setattr(D, 'git_head', lambda: 'b' * 40)
    r = D.run(args(tmp_path, rec, reference_index=ref, cases=['E6-S01']), runner=fake_runner(detector))
    assert r['parity_with_e3']['differences'] == []
    assert r['weights_file_sha256_verified'] == sha(b'weights') and r['code_commit_sha'] == 'b' * 40 and r['device'] == 'mps'
    assert r['cases']['E6-S01']['person_detections_retained'] == 1 and r['cases']['E6-S01']['gt_read'] is False
    assert 'scripts/evaluation/e3_cases/index.py' in r['code_sha256']
    assert json.loads((tmp_path / 'det/DETECTION_RECEIPT.json').read_text())['schema_version'] == D.SCHEMA


def test_parity_failures_stop_without_receipt(tmp_path, monkeypatch):
    rec = make_recording(tmp_path)
    ref, detector = patch_weights(monkeypatch, tmp_path)
    for name, kw, msg in (('a', {'detector': detector | {'index_score_floor': 0.15}}, 'index_score_floor'),
                          ('b', {'detector': detector, 'extra_key': True}, 'top_level_keys')):
        t = tmp_path / name
        rec_n = make_recording(t)
        ref_n, _ = patch_weights(monkeypatch, t)
        with pytest.raises(D.DetectionError, match=msg):
            D.run(args(t, rec_n, reference_index=ref_n, cases=['E6-S01']), runner=fake_runner(**kw))
        assert not (t / 'det/DETECTION_RECEIPT.json').exists()
    # weights different from the reference
    t = tmp_path / 'w'
    rec_w = make_recording(t)
    ref_w, det_w = patch_weights(monkeypatch, t)
    a = args(t, rec_w, reference_index=ref_w, cases=['E6-S01'])
    (t / 'models' / 'rtdetr_r18vd_dec3_6x_coco_from_paddle.pth').write_bytes(b'other')
    with pytest.raises(D.DetectionError, match='weights_file_sha256'):
        D.run(a, runner=fake_runner(det_w))


def test_device_difference_is_allowed_but_recorded(tmp_path, monkeypatch):
    rec = make_recording(tmp_path)
    ref, detector = patch_weights(monkeypatch, tmp_path)
    r = D.run(args(tmp_path, rec, reference_index=ref, cases=['E6-S01'], device='cpu'), runner=fake_runner(detector | {'device': 'cpu'}))
    assert r['device'] == 'cpu' and r['parity_with_e3']['differences'] == []


def test_rerun_skips_existing_cases_and_runs_the_rest(tmp_path):
    rec = make_recording(tmp_path)
    seen = []
    base = fake_runner()
    D.run(args(tmp_path, rec, cases=['E6-S01']), runner=lambda o, m, c, d, r: (seen.append(list(c)), base(o, m, c, d, r)))
    D.run(args(tmp_path, rec), runner=lambda o, m, c, d, r: (seen.append(list(c)), base(o, m, c, d, r)))
    assert seen == [['E6-S01'], ['E6-S02']]


def test_isolation_violation_detected(tmp_path):
    (tmp_path / 'gt-boxes').mkdir()
    (tmp_path / 'E6-S01.a-log.json').write_text('{}')
    assert D.isolation_violations(tmp_path) == ['E6-S01.a-log.json', 'gt-boxes/'] or set(D.isolation_violations(tmp_path)) == {'E6-S01.a-log.json', 'gt-boxes/'}


def test_incomplete_index_dir_is_moved_aside_and_redone(tmp_path):
    rec = make_recording(tmp_path)
    seen = []
    base = fake_runner()
    D.run(args(tmp_path, rec, cases=['E6-S01']), runner=lambda o, m, c, d, r: (seen.append(list(c)), base(o, m, c, d, r)))
    (tmp_path / 'det/indexes/E6-S01/production.json').unlink()             # crash after write_index, before production.json
    D.run(args(tmp_path, rec, cases=['E6-S01']), runner=lambda o, m, c, d, r: (seen.append(list(c)), base(o, m, c, d, r)))
    assert seen == [['E6-S01'], ['E6-S01']]                                 # redone, not skipped
    assert (tmp_path / 'det/indexes/E6-S01/production.json').is_file()
    assert len(list((tmp_path / 'det/_incomplete').iterdir())) == 1          # kept, not deleted


# ---------------------------------------------------------------- portable copy (CI runs on Linux: no `cp -c`)
def test_clone_uses_cp_c_only_on_macos_and_reflink_elsewhere(monkeypatch, tmp_path):
    src = tmp_path / 's.bin'
    src.write_bytes(b'abc')
    seen = []

    class R:
        returncode = 0
        stderr = b''

    def fake_run(cmd, capture_output):
        seen.append(cmd)
        Path(cmd[-1]).write_bytes(Path(cmd[-2]).read_bytes())
        return R()
    monkeypatch.setattr(D.subprocess, 'run', fake_run)
    monkeypatch.setattr(D.sys, 'platform', 'darwin')
    assert D.clone(src, tmp_path / 'a.bin') == 'apfs_clone' and seen[-1][:2] == ['cp', '-c']
    monkeypatch.setattr(D.sys, 'platform', 'linux')
    assert D.clone(src, tmp_path / 'b.bin') == 'reflink_auto' and seen[-1][:2] == ['cp', '--reflink=auto']
    assert (tmp_path / 'b.bin').read_bytes() == b'abc'


def test_clone_falls_back_to_plain_copy_when_cp_fails_or_is_missing(monkeypatch, tmp_path):
    (tmp_path / 'd').mkdir()
    (tmp_path / 'd' / 'x.jpg').write_bytes(b'xyz')
    src = tmp_path / 'f.json'
    src.write_text('{}')

    class Bad:
        returncode = 1
        stderr = b"cp: invalid option -- 'c'"
    monkeypatch.setattr(D.subprocess, 'run', lambda cmd, capture_output: Bad())
    assert D.clone(src, tmp_path / 'o/f.json') == 'copy' and (tmp_path / 'o/f.json').read_text() == '{}'
    assert D.clone(tmp_path / 'd', tmp_path / 'o/d', recursive=True) == 'copy' and (tmp_path / 'o/d/x.jpg').read_bytes() == b'xyz'

    def boom(cmd, capture_output):
        raise FileNotFoundError('cp')
    monkeypatch.setattr(D.subprocess, 'run', boom)
    assert D.clone(src, tmp_path / 'o2/f.json') == 'copy'


def test_clone_failure_in_cp_leaves_no_half_copy_and_total_failure_is_reported(monkeypatch, tmp_path):
    src = tmp_path / 's'
    src.mkdir()
    (src / 'a').write_bytes(b'1')

    class Bad:
        returncode = 1
        stderr = b'x'

    def partial(cmd, capture_output):
        Path(cmd[-1]).mkdir(parents=True)                     # cp died after creating the target dir
        (Path(cmd[-1]) / 'half').write_bytes(b'?')
        return Bad()
    monkeypatch.setattr(D.subprocess, 'run', partial)
    D.clone(src, tmp_path / 'out', recursive=True)
    assert sorted(p.name for p in (tmp_path / 'out').iterdir()) == ['a']           # the half copy was removed before the fallback copy
    with pytest.raises(D.DetectionError, match='COPY_FAILED'):
        D.clone(tmp_path / 'missing', tmp_path / 'nope')


def test_receipt_records_copy_modes(tmp_path, monkeypatch):
    rec = make_recording(tmp_path)
    monkeypatch.setattr(D, 'git_head', lambda: 'a' * 40)
    monkeypatch.setattr(D.sys, 'platform', 'linux')
    r = D.run(args(tmp_path, rec, cases=['E6-S01']), runner=fake_runner())
    assert sum(r['input_copy_modes_this_run'].values()) == 2 and set(r['input_copy_modes_this_run']) <= {'reflink_auto', 'copy'}

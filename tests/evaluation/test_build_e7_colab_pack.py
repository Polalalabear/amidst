"""E7 Colab pack builder: synthetic fixtures only (no local dataset, no GT from disk)."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from amidst.evaluation.e7_decider_eval import verify_manifest_sha256
from amidst.evaluation.e7_scoring_bridge import FORBIDDEN_GT_FIELDS, verify_colab_pack_pre_upload

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('build_e7_colab_pack', ROOT / 'scripts/evaluation/build_e7_colab_pack.py')
B = importlib.util.module_from_spec(_spec)
sys.modules['build_e7_colab_pack'] = B
_spec.loader.exec_module(B)

CAMS = ['CAM_A', 'CAM_B']
HIT = [20.0, 30.0, 60.0, 120.0]       # overlaps GT body in CAM_A
MISS = [200.0, 30.0, 240.0, 120.0]


def make_root(tmp, case='E3-X1', n_ticks=25):
    root = tmp / 'src_root'
    (root / 'indexes' / case).mkdir(parents=True)
    ticks = []
    for t in range(n_ticks):
        paths = {}
        for cam in CAMS:
            p = root / 'rgb' / case / cam / f'{t:06d}.png'
            p.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', B.SIZE, (t, 0, 0)).save(p)
            paths[cam] = p
        ticks.append((t, {'CAM_A': [{'bbox': HIT, 'score': 0.9, 'color': 'red'}, {'bbox': MISS, 'score': 0.4}],
                          'CAM_B': []}, paths))
    return root, ticks


def gt_loader_factory(visible_from=10, hidden_from=20, detector_miss_tick=10):
    def gt_loader(_root, _case):
        out = {}
        for t in range(25):
            vis = visible_from <= t < hidden_from
            body = [18.0, 28.0, 62.0, 125.0]
            out[t] = {'id': 'T', 'present': True, 'xy': [1.2, 3.4], 'gt_visible': ['CAM_A'] if vis else [],
                      'gt_boxes': {'CAM_A': body} if vis else {}}
        # a tick whose GT body is far from every candidate: detector miss
        out[detector_miss_tick]['gt_boxes'] = {'CAM_A': [100.0, 100.0, 130.0, 170.0]}
        return out
    return gt_loader


@pytest.fixture()
def built(tmp_path):
    root, ticks = make_root(tmp_path)
    report = tmp_path / 'e5.json'
    report.write_text(json.dumps({'per_arm': {'B1': {'n': 1}}}))
    out = tmp_path / 'pack'
    res = B.build_pack(out, [root], stride=5, e5_report=report, source_commit='abc123',
                       case_loader=lambda r, c: (ticks, CAMS), gt_loader=gt_loader_factory())
    return out, res


def test_pack_structure_and_gate(built):
    out, res = built
    for rel in ('requests/e3_16_segments.jsonl', 'scoring_only/answer_table.json', 'PACK_INFO.json',
                'MANIFEST.sha256', 'baselines/e5_report_frozen.json', 'frames/E3-X1/CAM_A/000010.png'):
        assert (out / rel).is_file(), rel
    assert res['gate']['status'] == 'OK'
    assert verify_colab_pack_pre_upload(out)['status'] == 'OK'
    assert res['requests'] == 5 and res['answer_entries'] == 5      # ticks 0,5,10,15,20


def test_requests_have_no_gt_and_match_decider_schema(built):
    out, _ = built
    rows = [json.loads(line) for line in (out / 'requests/e3_16_segments.jsonl').read_text().splitlines()]
    allowed = {'request_id', 'case_id', 'dataset_group', 'tick', 'camera_ids', 'variable_text', 'candidates', 'image_paths'}
    for r in rows:
        assert set(r) == allowed
        assert r['dataset_group'] == 'e3_16_segments'
        for c in r['candidates']:
            assert set(c) == {'detection_id', 'camera_id', 'box', 'score', 'class_label', 'colors'}
        for rel in r['image_paths'].values():
            assert (out / rel).is_file()

    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    text = (out / 'requests/e3_16_segments.jsonl').read_text()
    for r in rows:
        assert not (set(keys(r)) & FORBIDDEN_GT_FIELDS)
    for secret in ('1.2', '3.4', '28.0, 62.0', 'expected'):   # actor xy / GT body coordinates never appear
        assert secret not in text


def test_answer_table_is_label_only_and_correct(built):
    out, _ = built
    table = json.loads((out / 'scoring_only/answer_table.json').read_text())
    assert set(table['E3-X1|t0']) == {'request_id', 'case_id', 'tick', 'expected_answer',
                                      'expected_camera_ids', 'expected_detection_ids'}
    assert table['E3-X1|t0']['expected_answer'] == 'NOT_VISIBLE'
    assert table['E3-X1|t0']['expected_camera_ids'] == []
    assert table['E3-X1|t15']['expected_answer'] == 'SELECT'
    assert table['E3-X1|t15']['expected_detection_ids'] == {'CAM_A': ['D1']}   # D2 is the distractor
    assert table['E3-X1|t10']['expected_answer'] == 'UNCERTAIN'                # visible, detector miss
    assert table['E3-X1|t10']['expected_camera_ids'] == ['CAM_A']
    assert table['E3-X1|t20']['expected_answer'] == 'NOT_VISIBLE'
    assert B.json.dumps(table).count('gt_') == 0


def test_manifest_correct_and_detects_tamper(built):
    out, _ = built
    assert verify_manifest_sha256(out)
    lines = (out / 'MANIFEST.sha256').read_text().splitlines()
    names = [ln.split('  ', 1)[1] for ln in lines]
    assert 'MANIFEST.sha256' not in names and names == sorted(names)
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file() and p.name != 'MANIFEST.sha256')
    assert names == files
    for ln in lines:
        digest, rel = ln.split('  ', 1)
        assert digest == hashlib.sha256((out / rel).read_bytes()).hexdigest()
    (out / 'requests/e3_16_segments.jsonl').write_text('tampered\n')
    with pytest.raises(Exception):
        verify_manifest_sha256(out)


def test_frames_are_not_byte_copied_when_clone_available(built):
    out, res = built
    assert sum(res['frame_copy_modes'].values()) == 5 * 2
    assert set(res['frame_copy_modes']) <= {'clone', 'hardlink'}


def test_forbidden_gt_field_in_answer_rejected_and_pack_discarded(tmp_path, monkeypatch):
    root, ticks = make_root(tmp_path)
    real = B.expected_for_tick

    def leaky(c, g):
        return {**real(c, g), 'gt_regime': 'FULL'}
    monkeypatch.setattr(B, 'expected_for_tick', leaky)
    out = tmp_path / 'pack'
    with pytest.raises(ValueError, match='D385_FORBIDDEN_GT_FIELD'):
        B.build_pack(out, [root], stride=5, case_loader=lambda r, c: (ticks, CAMS), gt_loader=gt_loader_factory())
    assert not out.exists()


def test_numeric_box_in_answer_rejected(tmp_path, monkeypatch):
    root, ticks = make_root(tmp_path)
    monkeypatch.setattr(B, 'expected_for_tick', lambda c, g: {
        'expected_answer': 'SELECT', 'expected_camera_ids': ['CAM_A'], 'expected_detection_ids': {'CAM_A': [[1, 2, 3, 4]]}})
    out = tmp_path / 'pack'
    with pytest.raises(ValueError, match='D385_INVALID_ANSWER_VALUE'):
        B.build_pack(out, [root], stride=5, case_loader=lambda r, c: (ticks, CAMS), gt_loader=gt_loader_factory())
    assert not out.exists()


def test_gt_in_e5_report_discards_pack(tmp_path):
    root, ticks = make_root(tmp_path)
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({'per_arm': {}, 'x': {'gt_boxes': {}}}))
    out = tmp_path / 'pack'
    with pytest.raises(ValueError, match='D385_FORBIDDEN_GT_FIELD'):
        B.build_pack(out, [root], stride=5, e5_report=bad, case_loader=lambda r, c: (ticks, CAMS),
                     gt_loader=gt_loader_factory())
    assert not out.exists()


def test_gate_failure_discards_pack(tmp_path, monkeypatch):
    root, ticks = make_root(tmp_path)
    monkeypatch.setattr(B, 'verify_colab_pack_pre_upload', lambda p: (_ for _ in ()).throw(ValueError('GATE')))
    out = tmp_path / 'pack'
    with pytest.raises(ValueError, match='GATE'):
        B.build_pack(out, [root], stride=5, case_loader=lambda r, c: (ticks, CAMS), gt_loader=gt_loader_factory())
    assert not out.exists()


def test_refuses_existing_out_and_bad_stride(tmp_path):
    root, ticks = make_root(tmp_path)
    (tmp_path / 'pack').mkdir()
    with pytest.raises(FileExistsError):
        B.build_pack(tmp_path / 'pack', [root], case_loader=lambda r, c: (ticks, CAMS), gt_loader=gt_loader_factory())
    with pytest.raises(ValueError, match='BAD_STRIDE'):
        B.build_case('c', ticks, CAMS, {}, 0)


def test_target_absent_actor_is_not_visible():
    cands = B.candidates_for_tick({'CAM_A': [{'bbox': HIT, 'score': 0.9}]}, CAMS)
    assert B.expected_for_tick(cands, None)['expected_answer'] == 'NOT_VISIBLE'
    assert B.expected_for_tick(cands, {'present': False, 'gt_visible': ['CAM_A'],
                                       'gt_boxes': {'CAM_A': HIT}})['expected_answer'] == 'NOT_VISIBLE'

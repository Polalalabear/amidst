"""Bounded local static RGB probe. This module never reads graph or GT data."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import time

from amidst.q1q5.detection_index import OfficialRTDetrR18

CAMERAS = ('CAM_R101_IN', 'CAM_R102_IN', 'CAM_R103_IN', 'CAM_R104_IN', 'CAM_CORR_W', 'CAM_CORR_E')
THRESHOLD = 0.30
WEIGHT_SHA256 = '3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0'
RECEIPT_SHA256 = '0f6b279e4d535959aad7bff769022f6fcf0a2257e2aca922f6f9fa0fac1ea3bd'
MODEL_CONFIG_SHA256 = '529ef3db2f006bf2ece36bc980406a549f6e3a85601aff03e740f8b264c49213'


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_bytes(path: Path, expected: str, size: int | None = None) -> bytes:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('SYMLINK_INPUT')
    raw = path.read_bytes()
    if (size is not None and len(raw) != size) or sha256(raw) != expected:
        raise ValueError('INPUT_PIN_MISMATCH')
    return raw


def validate_frames(root: Path, receipt: dict) -> list[dict]:
    if receipt.get('scene_id') != 'office_expanded_r005' or receipt.get('preview_revision') != 'v2':
        raise ValueError('RECEIPT_SCENE_MISMATCH')
    rendered = receipt['rendered']
    if len(rendered) != 7 or {row['camera_id'] for row in rendered} != {*CAMERAS, 'HUMAN_LAYOUT'}:
        raise ValueError('RECEIPT_ALLOWLIST_MISMATCH')
    result = []
    for row in rendered:
        camera = row['camera_id']
        relative = f'rgb/{camera}.png' if camera in CAMERAS else 'human_layout/overview.png'
        purpose = 'STATIC_CAMERA_RGB' if camera in CAMERAS else 'HUMAN_LAYOUT_ONLY'
        if row['file'] != relative or row['purpose'] != purpose:
            raise ValueError('RECEIPT_PURPOSE_MISMATCH')
        item = receipt['files'][relative]
        if item['sha256'] != row['sha256']:
            raise ValueError('RECEIPT_PIN_MISMATCH')
        if camera in CAMERAS:
            raw = safe_bytes(root / relative, row['sha256'], item['bytes'])
            result.append({'camera_id': camera, 'file': relative, 'sha256': sha256(raw), 'bytes': len(raw), 'raw': raw})
    return sorted(result, key=lambda x: CAMERAS.index(x['camera_id']))


def validate_model_source(config: dict) -> tuple[Path, Path, dict]:
    source = Path(config['source_root'])
    weights = Path(config['weights'])
    if any(p.is_symlink() for p in (source, *source.parents, weights, *weights.parents)):
        raise ValueError('SYMLINK_MODEL_INPUT')
    expected = config['source_hashes']
    files = list((source / 'src').rglob('*.py'))
    if any(p.is_symlink() for p in (source / 'src').rglob('*')):
        raise ValueError('SYMLINK_MODEL_SOURCE')
    actual = {p.relative_to(source).as_posix(): sha256(p.read_bytes()) for p in files}
    if len(actual) != 49 or actual != expected:
        raise ValueError('MODEL_SOURCE_PIN_MISMATCH')
    if weights.stat().st_size != 81_001_853 or sha256(weights.read_bytes()) != WEIGHT_SHA256:
        raise ValueError('MODEL_WEIGHT_PIN_MISMATCH')
    return source, weights, actual


def run_probe(root: Path, receipt_path: Path, config_path: Path, output: Path) -> dict:
    from PIL import Image, __version__ as pillow_version
    import numpy
    import torch
    import torchvision

    if output.exists():
        raise ValueError('OUTPUT_EXISTS')
    if os.statvfs(output.parent).f_bavail * os.statvfs(output.parent).f_frsize < 8 * 1024**3:
        raise ValueError('LOW_DISK')
    receipt_raw = safe_bytes(receipt_path, RECEIPT_SHA256)
    frames = validate_frames(root, json.loads(receipt_raw))
    config_raw = safe_bytes(config_path, MODEL_CONFIG_SHA256)
    config = json.loads(config_raw)
    source, weights, source_hashes = validate_model_source(config)
    durations = {}
    def observe(stage, operation):
        start = time.perf_counter_ns()
        value = operation()
        durations[stage] = durations.get(stage, 0) + (time.perf_counter_ns() - start)
        return value
    start = time.perf_counter_ns()
    detector = OfficialRTDetrR18(source, weights, source_hashes=source_hashes,
                                seed=7, threads=2, observer=observe)
    cold_load_ns = time.perf_counter_ns() - start
    output.mkdir(parents=False, exist_ok=False)
    rows = []
    with (output / 'raw_top300.jsonl').open('x', encoding='utf-8') as stream:
        for frame in frames:
            from PIL import Image
            with Image.open(io.BytesIO(frame['raw'])) as opened:
                if opened.format != 'PNG':
                    raise ValueError('NOT_PNG')
                image = opened.convert('RGB')
            dimensions = [image.width, image.height]
            durations.clear()
            start = time.perf_counter_ns()
            predictions = detector(image)
            elapsed_ns = time.perf_counter_ns() - start
            image.close()
            if len(predictions) != 300:
                raise ValueError('NOT_TOP300')
            for p in predictions:
                p['class_label'] = detector.class_labels[p['class_id']]
            record = {'camera_id': frame['camera_id'], 'file_sha256': frame['sha256'],
                      'image_size_px': dimensions, 'detections': predictions}
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
            shown = [p for p in predictions if p['score'] >= THRESHOLD]
            rows.append({'camera_id': frame['camera_id'], 'file_sha256': frame['sha256'],
                         'raw_count': len(predictions), 'shown_count': len(shown),
                         'status': 'DETECTED' if shown else 'NOT_DETECTED_AT_DISPLAY_THRESHOLD',
                         'shown': shown,
                         'timing_ns': {'total': elapsed_ns, **durations}})
    raw_hash = sha256((output / 'raw_top300.jsonl').read_bytes())
    report = {'status': 'ENGINEERING_ONLY', 'scene_id': 'office_expanded_r005',
              'display_threshold': THRESHOLD, 'not_detected_is_absence': False,
              'seed': 7, 'threads': 2, 'device': 'cpu', 'dtype': 'FP32',
              'receipt_sha256': RECEIPT_SHA256, 'model_config_sha256': sha256(config_raw),
              'model_source_hashes': source_hashes, 'source_git_head': 'UNKNOWN',
              'legacy_acceptance_source_head': 'f1d13cebc7c9437fb27ebf8450b5c43d01d7d77b',
              'adapter_reported_code_source': detector.metadata['code_source'],
              'adapter_file_sha256': sha256(Path(__import__('amidst.q1q5.detection_index', fromlist=['x']).__file__).read_bytes()),
              'weights_sha256': WEIGHT_SHA256,
              'runtime': {'torch': torch.__version__, 'torchvision': torchvision.__version__,
                          'PIL': pillow_version, 'numpy': numpy.__version__,
                          'torch_file': torch.__file__, 'torchvision_file': torchvision.__file__},
              'detector_metadata': detector.metadata, 'cold_load_ns': cold_load_ns,
              'raw_top300_sha256': raw_hash, 'human_layout': 'SKIPPED_HUMAN_LAYOUT_ONLY',
              'human_approval_verified': False, 'coverage_basis': 'NOT_EVALUATED',
              'rows': rows}
    (output / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
    return report

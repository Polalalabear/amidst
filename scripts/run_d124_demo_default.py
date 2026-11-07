#!/usr/bin/env python3
"""Explicit D124 DEMO_DEFAULT real-RGB index run; never a production gate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5.demo_default_index import D124DemoRun, DemoIndexError, free_space, loads, sha  # noqa: E402
from amidst.q1q5.detection_index import OfficialRTDetrR18, build_detection_index  # noqa: E402
from amidst.q1q5.hsv_color import HSVConfig  # noqa: E402


def load_config(path: Path, pin: str):
    raw = path.read_bytes()
    if sha(raw) != pin:
        raise DemoIndexError('CONFIG_BYTE_PIN_MISMATCH')
    config = loads(raw)
    required = {'profile', 'formal_eligible', 'safe_manifest_sha256', 'run_descriptor',
                'run_descriptor_sha256', 'clock_sha256', 'catalog_sha256', 'run_id',
                'clock_id', 'scene_id', 'scene_revision', 'stride_samples',
                'index_grid_origin_frame', 'index_score_floor', 'hsv_config',
                'model_source_hashes_sha256', 'weights_sha256'}
    if not required <= set(config):
        raise DemoIndexError('CONFIG_EXACT_FIELDS_REQUIRED')
    if config['weights_sha256'] != '3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0':
        raise DemoIndexError('OFFICIAL_WEIGHTS_PIN_REQUIRED')
    return config


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--permit-real-rgb', action='store_true')
    p.add_argument('--demo-default', action='store_true')
    for name in ('config', 'config-sha256', 'safe-bundle', 'model-source',
                 'source-hashes', 'weights', 'out-dir'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--threads', type=int, required=True)
    a = p.parse_args(argv)
    if not (a.permit_real_rgb and a.demo_default):
        p.error('REAL_RGB_AND_DEMO_DEFAULT_EXPLICIT_FLAGS_REQUIRED')
    output = Path(a.out_dir).absolute()
    if output.exists():
        p.error('OUTPUT_EXISTS')
    config = load_config(Path(a.config), a.config_sha256)
    run = D124DemoRun(Path(a.safe_bundle), config)
    source_hashes_raw = Path(a.source_hashes).read_bytes()
    if sha(source_hashes_raw) != config['model_source_hashes_sha256']:
        raise DemoIndexError('MODEL_SOURCE_HASHES_PIN_MISMATCH')
    source_hashes = loads(source_hashes_raw)
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise DemoIndexError('MODEL_SOURCE_HASHES_REQUIRED')
    color = HSVConfig(**config['hsv_config'])
    events = []
    frames_seen = 0
    minimum_free = free_space(output.parent)
    import subprocess
    source_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1], text=True).strip()
    source_pins = {name: sha((Path(__file__).resolve().parents[1] / name).read_bytes()) for name in ['scripts/run_d124_demo_default.py', 'src/amidst/q1q5/demo_default_index.py', 'src/amidst/q1q5/detection_index.py', 'src/amidst/q1q5/hsv_color.py']}
    if a.seed != config.get('seed') or a.threads != config.get('threads'):
        raise DemoIndexError('EXECUTION_PARAMETER_MISMATCH')
    def observe(stage, operation):
        nonlocal minimum_free, frames_seen
        minimum_free = min(minimum_free, free_space(output.parent))
        start = time.monotonic_ns()
        try:
            result = operation()
        except Exception as exc:
            events.append({'stage': stage, 'elapsed_ns': time.monotonic_ns()-start,
                           'status': 'ERROR', 'error_type': type(exc).__name__})
            raise
        events.append({'stage': stage, 'elapsed_ns': time.monotonic_ns()-start, 'status': 'OK'})
        if stage == 'rgb_read':
            frames_seen += 1
            if frames_seen % 50 == 0:
                print(json.dumps({'progress_frames': frames_seen, 'run_id': config['run_id'], 'minimum_free_bytes': minimum_free}), flush=True)
        return result
    free_space(output.parent)
    predictor = OfficialRTDetrR18(Path(a.model_source), Path(a.weights),
                                  source_hashes=source_hashes, seed=a.seed,
                                  threads=a.threads, observer=observe)
    artifact = build_detection_index(run, predictor, scene_revision=config['scene_revision'],
        stride_samples=config['stride_samples'],
        index_grid_origin_frame=config['index_grid_origin_frame'],
        index_score_floor=config['index_score_floor'], color_config=color, observer=observe)
    receipt = {'profile': 'DEMO_DEFAULT', 'formal_eligible': False,
               'qt25t_cx8t': 'DEMO_PROFILE_ONLY', 'production_gate': 'NOT_RUN',
               'cross_camera_tracking': 'NOT_EVALUATED', 'config_file_sha256': a.config_sha256,
               'source': run.source_projection, 'index_manifest_sha256': None,
               'records_file_sha256': sha(artifact.records_bytes), 'observer_log_sha256': None,
               'model_source_hashes_file_sha256': sha(source_hashes_raw),
               'weights_file_sha256': config['weights_sha256'],
               'model_seed': a.seed, 'model_threads': a.threads,
               'stats': artifact.stats, 'source_head': source_head, 'source_files_sha256': source_pins, 'minimum_free_bytes': minimum_free, 'complete_parameters': config.get('parameters', []), 'parameter_mode': 'DEMO_DEFAULT', 'formal_run_allowed': False}
    index_raw = json.dumps(artifact.manifest, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    receipt['index_manifest_sha256'] = sha(index_raw)
    log_raw = b''.join(json.dumps(e, sort_keys=True, separators=(',', ':')).encode()+b'\n' for e in events)
    receipt['observer_log_sha256'] = sha(log_raw)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in [('detection_index.records.jsonl', artifact.records_bytes),
                      ('detection_index.json', index_raw), ('observer.jsonl', log_raw),
                      ('demo_default_receipt.json', json.dumps(receipt, sort_keys=True, indent=2).encode()+b'\n')]:
        free_space(output)
        with (output / name).open('xb') as stream:
            stream.write(raw)
    print(json.dumps({'status': 'DEMO_DEFAULT', 'output': str(output),
                      'index_manifest_sha256': receipt['index_manifest_sha256'],
                      'production_gate': 'NOT_RUN', 'cross_camera_tracking': 'NOT_EVALUATED'}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

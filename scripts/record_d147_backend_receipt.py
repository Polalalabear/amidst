#!/usr/bin/env python3
"""Record D147-D150 real backend responses from the explicitly owned demo.

Read-only indexed replay; no inference, human reference, rendering or GT inputs.
Raw responses stay LOCAL; the compact receipt is suitable for a regression pin.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from demo_dependency_config import configuration, owned_path
from serve_demo_integration import Demo

ROOT = Path(__file__).resolve().parents[1]
PRODUCERS = ['scripts/serve_demo_integration.py', 'src/amidst/q1q5/cross_camera_demo.py',
             'src/amidst/q1q5/demo_local_tracks.py']


def record(output):
    output.mkdir(parents=True, exist_ok=True)
    config, home = configuration()
    state = Path(tempfile.mkdtemp(prefix='d147-state-', dir=output)) / 'state'
    demo = Demo(owned_path(home, config['artifacts_root']), owned_path(home, config['p1_bundle']), state,
                job_path=owned_path(home, config['cross_camera_job']),
                job_pin=config['cross_camera_job_sha256'], owned_root=home)
    receipt = {'receipt_role': 'IMPLEMENTATION_REGRESSION_PIN',
               'receipt_role_note': 'Recorded from this implementation; catches regressions, does not prove '
                                    'correctness. Re-record after any parameter or producer change.',
               'decision_refs': ['#93 D147', '#93 D148', '#93 D149', '#93 D150'],
               'base_commit': '5c901e5dff96c5e324a747987747c47623c3b15a',
               'source_files_sha256': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in PRODUCERS},
               'inference_run': False, 'formal_eligible': False, 'runs': []}
    token = demo.call('session', {'role': 'demo'})['session_ref']
    for label in ['A4-1', 'B4-1']:
        run = next(r for r in demo.api.runs.values() if r.title.startswith(label+' '))
        key = run.catalog['scene_id'], run.catalog['run_id']
        result = demo.call('q_core_track', {'schema_version': 'q-core.track-request.v1', 'session_ref': token,
            'scene_id': key[0], 'run_id': key[1], 'feature': {'class_label': 'person', 'color_label': None},
            'region_ids': [], 'time': None, 'playback_now_us': run.bindings.clock.duration_us})
        (output/(label+'-track-response.json')).write_text(json.dumps(result, indent=2)+'\n')
        candidates = demo.cross[key]
        receipt['runs'].append({'label': label, 'run_id': key[1],
            'index_content_sha256': run.bindings.index_sha256,
            'records_file_sha256': run.bindings.index.manifest['records_file_sha256'],
            'output_sha256': result['output_sha256'], 'single_view': result['single_view'],
            'cameras': [{'camera_id': camera,
                'candidate_segments': sum(t.camera_id == camera for t in candidates),
                'candidate_observations': sum(len(t.observations) for t in candidates if t.camera_id == camera),
                'box_continuation_observations': sum(o.evidence_kind == 'BOX_CONTINUATION' for t in candidates
                    if t.camera_id == camera for o in t.observations)} for camera in sorted(run.catalog['camera_ids'])]})
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='LOCAL response directory')
    parser.add_argument('--receipt', type=Path, required=True, help='Compact JSON regression receipt')
    args = parser.parse_args()
    receipt = record(args.out)
    args.receipt.write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()

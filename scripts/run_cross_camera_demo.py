"""Pinned, LOCAL-only #417 DEMO_DEFAULT cross-camera replay. No pixels/models."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess

from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, declared_wall, response

ROLES = {'index', 'records', 'local_tracks', 'receipt', 'config', 'clock'}
ROW_FIELDS = {'frame_ref', 'camera_id', 'frame_index', 'timestamp_us', 'rgb_file_sha256',
              'frame_state', 'state_reason', 'detections'}
DETECTION_FIELDS = {'bbox_xyxy_px', 'class_id', 'class_label', 'color', 'observation_id', 'score'}
FORBIDDEN = {'gt', 'ground_truth', 'gt_private', 'event_script', 'script_path', 'scenario',
             'renderer_trajectory', 'renderer_track', 'trajectory', 'visibility', 'depth', 'actor_id'}
MIN_FREE = 8 * 1024**3


def require(value, code):
    if not value:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def loads(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'DUPLICATE_KEY')
            obj[key] = value
        return obj
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def reject_protected(value):
    if isinstance(value, dict):
        require(not FORBIDDEN.intersection(str(k).lower() for k in value), 'FORBIDDEN_INPUT')
        require(not any(str(k).lower().startswith('gt_') and k != 'gt_read' for k in value), 'FORBIDDEN_INPUT')
        for item in value.values():
            reject_protected(item)
    elif isinstance(value, list):
        for item in value:
            reject_protected(item)


def read_pin(entry, *, basename=None):
    require(set(entry) == {'path', 'sha256'}, 'INPUT_REFERENCE_FIELDS')
    path = Path(entry['path'])
    require(path.is_absolute() and path.resolve() == path
            and all(not p.is_symlink() for p in (path, *path.parents)), 'CANONICAL_FILE_REQUIRED')
    require(not FORBIDDEN.intersection(part.lower() for part in path.parts), 'FORBIDDEN_PATH')
    require(basename is None or path.name == basename, 'INPUT_ROLE_FILENAME')
    require(isinstance(entry['sha256'], str) and len(entry['sha256']) == 64, 'PIN_REQUIRED')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 8_000_000, 'REGULAR_BOUNDED_FILE')
        raw = stream.read(8_000_001)
    require(len(raw) == info.st_size and sha(raw) == entry['sha256'], 'BYTE_PIN_MISMATCH')
    return raw


def load_run(spec, graph, binding, parameters):
    require(set(spec) == {'label', 'inputs'} and set(spec['inputs']) == ROLES, 'EXACT_INPUT_ROLES')
    names = {'index': 'detection_index.json', 'records': 'detection_index.records.jsonl',
             'local_tracks': 'cx8_rule_only.json', 'receipt': 'demo_default_receipt.json',
             'config': spec['label'] + '-config.json',
             'clock': 'r004_' + ('a4' if spec['label'] == 'A4-1' else 'b4') + '_d124_v1.json'}
    raw = {role: read_pin(ref, basename=names[role]) for role, ref in spec['inputs'].items()}
    index, local, receipt, config, clock = (loads(raw[role]) for role in
                                          ['index', 'local_tracks', 'receipt', 'config', 'clock'])
    for doc in [local, config]:
        reject_protected(doc)
    require(config['profile'] == 'DEMO_DEFAULT' and config['formal_eligible'] is False
            and local['parameter_mode'] == 'DEMO_DEFAULT' and local['formal_eligible'] is False,
            'DEMO_AUTHORITY_REQUIRED')
    require(local['scope'] == 'CAMERA_LOCAL_SELECTED_SEED' and local['mode'] == 'RULE_ONLY'
            and local['identity_verdict'] == 'UNCONFIRMED', 'LOCAL_TRACK_SCOPE')
    require(index['provenance'].get('gt_read') is False, 'SOURCE_PROVENANCE')
    require(index['records_file_sha256'] == sha(raw['records']) == local['source_records_sha256'],
            'RECORDS_BINDING')
    require(sha(canonical(index)) == local['source_index_sha256']
            and sha(raw['index']) == receipt['index_manifest_sha256'], 'INDEX_BINDING')
    require(index['content_sha256'] == sha(canonical({k: v for k, v in index.items()
                                                    if k not in {'index_id', 'content_sha256'}})), 'INDEX_CONTENT_PIN')
    require(sha(canonical(config)) == local['config_content_sha256']
            and sha(raw['config']) == receipt['config_file_sha256'], 'PARAMETER_BINDING')
    values = {p['name']: p['value'] for p in config['parameters']}
    require(parameters.min_score == values['link_min_score']
            and parameters.handoff_max_gap_us == values['search_window_us']
            and parameters.color_rule == values['link_color_rule'], 'DEMO_PARAMETER_DRIFT')
    require(index['scene_id'] == config['scene_id'] == receipt['source']['scene_id'] == binding['index_scene_id']
            and graph['scene_id'] == binding['graph_scene_id']
            and index['scene_revision'] == config['scene_revision'] == graph['scene_revision'] == 'r004'
            and receipt['source']['catalog_sha256'] == graph['camera_catalog_sha256'] == binding['catalog_sha256'],
            'EXPLICIT_GRAPH_SOURCE_BINDING')
    require(index['run_id'] == config['run_id'] == clock['run_id'] == receipt['source']['run_id']
            and index['clock_id'] == config['clock_id'] == clock['clock_id'], 'RUN_CLOCK_BINDING')
    require(sha(raw['clock']) == config['clock_sha256'] == receipt['source']['clock_sha256'], 'CLOCK_BYTE_PIN')
    require(clock['content_sha256'] == sha(canonical({k: v for k, v in clock.items() if k != 'content_sha256'})), 'CLOCK_CONTENT_PIN')
    require(parameters.sample_interval_us == 1_000_000 // receipt['source']['fps'], 'SAMPLE_INTERVAL')
    observations, seen_frames = {}, set()
    camera_ids = {c['camera_id'] for c in index['sampling']['per_camera']}
    for line in raw['records'].splitlines():
        if not line:
            continue
        row = loads(line)
        require(set(row) <= ROW_FIELDS, 'CLOSED_SOURCE_ROW')
        reject_protected(row)
        require(row['camera_id'] in camera_ids and type(row['frame_index']) is int
                and row['frame_index'] >= 0 and row['timestamp_us'] == row['frame_index'] * parameters.sample_interval_us
                and row['frame_ref'] == f"frame:{index['run_id']}:{row['camera_id']}:{row['frame_index']}"
                and row['frame_ref'] not in seen_frames, 'SOURCE_SAMPLE_BINDING')
        seen_frames.add(row['frame_ref'])
        for detection in row.get('detections') or []:
            require(row['frame_state'] == 'INFERRED' and set(detection) <= DETECTION_FIELDS, 'CLOSED_DETECTION')
            oid = detection['observation_id']
            require(oid not in observations and math.isfinite(detection['score']), 'OBSERVATION_UNIQUE_FINITE')
            colors = detection.get('color') or {}
            require(set(colors.get('verdicts', {})) <= {'red', 'orange', 'yellow', 'green', 'blue', 'purple'}, 'COLOR_VOCABULARY')
            labels = frozenset(k for k, v in colors.get('verdicts', {}).items() if v in {'WEAK', 'STRONG'})
            observations[oid] = (row, detection, labels)
    tracks = []
    require(len({t['camera_id'] for t in local['tracks']}) == len(local['tracks'])
            and {t['camera_id'] for t in local['tracks']} == camera_ids, 'LOCAL_CAMERA_SET')
    for track in local['tracks']:
        require(set(track) == {'camera_id', 'seed', 'status', 'steps'}, 'CLOSED_LOCAL_TRACK')
        if track['seed'] is None:
            require(not track['steps'], 'EMPTY_TRACK_WITH_STEPS')
            continue
        seed = track['seed']
        pairs = [(seed['observation_id'], seed['timestamp_us'])]
        for step in track['steps']:
            if step['link']['decision'] == 'LINKED':
                pairs.append((step['link']['next_observation_id'], step['timestamp_us']))
        projected = []
        for oid, timestamp in pairs:
            require(oid in observations, 'LINKED_OBSERVATION_MISSING')
            row, detection, labels = observations[oid]
            require(row['camera_id'] == track['camera_id'] and row['timestamp_us'] == timestamp
                    and detection['class_label'] == 'person' and detection['score'] >= parameters.min_score,
                    'LINKED_OBSERVATION_BINDING')
            projected.append(Observation(track['camera_id'], timestamp, oid, detection['score'], labels))
        require(seed['frame_ref'] == observations[seed['observation_id']][0]['frame_ref'], 'SEED_FRAME_BINDING')
        tracks.append(Track(track['camera_id'], 'local-seed:' + seed['observation_id'], tuple(projected)))
    return tracks, clock, index


def run_job(job_path, job_sha256, out_dir):
    source_root = Path(__file__).resolve().parents[1]
    source_paths = [Path(__file__).resolve(), source_root/'src/amidst/q1q5/cross_camera_demo.py']
    executed_files = {str(p.relative_to(source_root)): sha(p.read_bytes()) for p in source_paths}
    executed_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source_root, text=True).strip()
    job = loads(read_pin({'path': str(job_path), 'sha256': job_sha256}))
    require(set(job) == {'profile', 'formal_eligible', 'source_pr_head', 'graph', 'graph_binding', 'parameters', 'runs'}, 'CLOSED_JOB')
    require(job['profile'] == 'DEMO_DEFAULT' and job['formal_eligible'] is False
            and job['source_pr_head'] == 'a786bde58c616f12766c55bb3172c37728c65ef8', 'SOURCE_475_HEAD')
    require({r['label'] for r in job['runs']} == {'A4-1', 'B4-1'} and len(job['runs']) == 2, 'EXACT_RUNS')
    require(set(job['graph_binding']) == {'index_scene_id', 'graph_scene_id', 'catalog_sha256'}, 'CLOSED_GRAPH_BINDING')
    parameters = Parameters(**job['parameters'])
    graph_raw = read_pin(job['graph'], basename='camera_graph_v3_1.json')
    graph = loads(graph_raw)
    require(graph['approval_status'] == 'DRAFT' and graph['scene_revision'] == 'r004', 'GRAPH_DEMO_ONLY')
    require(graph['content_sha256'] == sha(canonical({k: v for k, v in graph.items()
                       if k not in {'graph_id', 'content_sha256', 'stats'}})), 'GRAPH_CONTENT_PIN')
    transitions = {}
    for edge in graph['transitions']:
        reject_protected(edge)
        key = edge['from_camera_id'], edge['to_camera_id']
        require(key not in transitions and all(isinstance(x, str) and x for x in (*key, edge['transition_id'])), 'TRANSITION_UNIQUE')
        transitions[key] = edge['transition_id']
    loaded = [(spec, *load_run(spec, graph, job['graph_binding'], parameters)) for spec in job['runs']]
    out_dir = Path(out_dir)
    require(out_dir.is_absolute() and out_dir.resolve() == out_dir and not out_dir.exists(), 'NEW_CANONICAL_OUTPUT_REQUIRED')
    require(shutil.disk_usage(out_dir.parent).free >= MIN_FREE, 'LOW_DISK')
    out_dir.mkdir()
    summary = []
    def write(path, raw):
        require(shutil.disk_usage(path.parent).free >= MIN_FREE, 'LOW_DISK')
        with path.open('xb') as stream:
            stream.write(raw)
        return {'bytes': len(raw), 'sha256': sha(raw)}
    for spec, tracks, clock, index in loaded:
        folder = out_dir / spec['label']
        folder.mkdir()
        duration = clock['source_duration_us']
        final, events, audit = response(tracks, transitions, as_of_us=duration, parameters=parameters,
                                        clock_mapping_sha256=clock['content_sha256'])
        final['provenance'] = {'producer': 'demo-cross-camera-local-linker', 'gt_read': False,
                               'source_pr_head': job['source_pr_head'], 'parameter_mode': 'DEMO_DEFAULT',
                               'formal_eligible': False, 'camera_graph_sha256': graph['content_sha256'],
                               'source_index_sha256': spec['inputs']['index']['sha256']}
        final['output_sha256'] = sha(canonical(final))
        points, responses = [], []
        for time in range(0, duration + 1, parameters.sample_interval_us):
            current, _, _ = response(tracks, transitions, as_of_us=time, parameters=parameters,
                                      clock_mapping_sha256=clock['content_sha256'])
            last = current['single_view'][-1] if current['single_view'] else None
            current['provenance'] = final['provenance']
            current['output_sha256'] = sha(canonical(current))
            responses.append(current)
            points.append({'as_of_us': time, 'evidence_cutoff_exclusive_us': time,
                           'declared_wall_time': declared_wall(clock, time), 'status': current['status'],
                           'current_camera_id': last['camera_id'] if last else None,
                           'kind': last['kind'] if last else 'NO_SIGHTING',
                           'evidence_state': last['evidence_state'] if last else 'UNKNOWN',
                           'identity_verdict': 'UNCONFIRMED'})
        for event in events:
            event['declared_wall_time'] = declared_wall(clock, event['timestamp_us'])
        files = {}
        for name, value in [('track-response.json', final), ('single-view.json', final['single_view']),
                            ('switch-events.json', events), ('association-audit.json', audit)]:
            files[name] = write(folder / name, canonical(value) + b'\n')
        files['timeline.jsonl'] = write(folder / 'timeline.jsonl', b''.join(canonical(p) + b'\n' for p in points))
        files['responses.jsonl'] = write(folder / 'responses.jsonl', b''.join(canonical(p) + b'\n' for p in responses))
        receipt = {'profile': 'DEMO_DEFAULT', 'formal_eligible': False, 'parameters': asdict(parameters),
                   'source_pr_head': job['source_pr_head'], 'job_sha256': job_sha256,
                   'inputs': spec['inputs'], 'graph': job['graph'], 'graph_binding': job['graph_binding'],
                   'run_id': index['run_id'], 'clock_id': clock['clock_id'], 'files': files,
                   'source_code_sha256': executed_files, 'executed_source_head': executed_head,
                   'verified': 'Source pins, local observations and contract vectors; no identity accuracy claim',
                   'not_verified': ['Formal parameters', 'physical navigation', 'full workbench integration']}
        require(executed_files == {str(p.relative_to(source_root)): sha(p.read_bytes()) for p in source_paths}, 'EXECUTED_SOURCE_CHANGED')
        write(folder / 'receipt.json', canonical(receipt) + b'\n')
        summary.append({'label': spec['label'], 'run_id': index['run_id'], 'switches': len(events),
                        'single_view': final['single_view'], 'timeline_points': len(points),
                        'status': final['status'], 'files': files})
    write(out_dir / 'summary.json', canonical(summary) + b'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--job-sha256', required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_job(args.job, args.job_sha256, args.out_dir), indent=2))

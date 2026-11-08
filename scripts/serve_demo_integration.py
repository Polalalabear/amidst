"""#445 local, source-pinned P1/D124/static workbench. No model or rendering."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import time

from amidst.q1q5.api import QAPI, QRun, _safe_request
from amidst.q1q5.clock_mapping import ClockMapping, resolve_wall_range
from amidst.q1q5.core_query import validate_track_request, _blind_for_track
from amidst.q1q5.cross_camera_demo import Parameters, response as cross_response
from amidst.q1q5.graphs import GraphBundle
from amidst.q1q5.p1_workbench import P1, binary, public_png, require, server
from amidst.q1q5.q3_parse import ParseSettings
from amidst.q1q5.q5_controller import RuntimeBindings
from amidst.q1q5.scene_graphs import load_scene_graphs
from amidst.q1q5.store import DetectionSnapshot, DocumentPin, JsonRunStore, canonical_hash
from run_cross_camera_demo import read_pin, loads, load_run
from demo_dependency_config import configuration, owned_path, resolve_job

REPO = Path(__file__).resolve().parents[1]
P1_PIN = '6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7'
MEDIA_PIN = 'ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01'
REPORT_PIN = '0915d54d585fcbd8e89575bf1ab43dec0ae3b8e85839b8e59704fa9d03b6b021'


def pinned(path, pin):
    return read_pin({'path': str(path), 'sha256': pin})


def seal(doc, prefix=None):
    excluded = ('content_sha256', 'stats', 'graph_id', 'parameter_set_id', 'index_id')
    doc['content_sha256'] = canonical_hash(doc, exclude=excluded)
    if prefix:
        key = 'parameter_set_id' if prefix == 'pset:q-demo' else 'index_id' if prefix.startswith('detidx:') else 'graph_id'
        doc[key] = prefix + ':' + doc['content_sha256'][:16]
    return doc


def aliases(index):
    doc = json.loads((REPO / 'configs/q1q5/class_alias_v1.json').read_bytes())
    doc['color_vocabulary'] = deepcopy(index.manifest['color_method']['color_vocabulary'])
    return seal(doc)


def parameters(index, values):
    m = index.manifest
    unique = {}
    for row in values:
        require(row['name'] not in unique or unique[row['name']] == row, 'CONFLICTING_PARAMETER')
        unique[row['name']] = row
    return seal({'schema_version': 'q-demo.parameter-set.v1',
        'applies_to': {'scene_revision': m['scene_revision'], 'run_ids': [m['run_id']],
                      'detection_index_ids': [m['index_id']],
                      'index_interval_us': m['sampling']['per_camera'][0]['index_interval_us']},
        'approval': {'status': 'DEMO_DEFAULT', 'approval_ref': None, 'approved_by': None},
        'parameters': deepcopy(list(unique.values()))}, 'pset:q-demo')


def qrun(index, clock, graphs, params, title, source_kind):
    m = index.manifest; a = aliases(index)
    cameras = [c['camera_id'] for c in m['sampling']['per_camera']]
    ranges = {c: [[0, clock.duration_us]] for c in cameras}
    b = RuntimeBindings(index, m['content_sha256'], graphs,
        graphs.region['content_sha256'], graphs.camera['content_sha256'],
        clock, clock.content_sha256, params, params['content_sha256'], ranges, canonical_hash(ranges))
    catalog = {'scene_id': m['scene_id'], 'scene_revision': m['scene_revision'], 'run_id': m['run_id'],
        'camera_ids': cameras, 'region_ids': [r['region_id'] for r in graphs.region['regions']],
        'class_labels': a['class_labels'], 'class_aliases': a['aliases'],
        'color_labels': a['color_vocabulary']['labels'], 'color_aliases': a['color_aliases'],
        'camera_aliases': {c: c for c in cameras}, 'region_aliases': {},
        'class_map_sha256': a['class_map_sha256']}
    values = {v['name']: v['value'] for v in params['parameters']}
    settings = ParseSettings(values.get('query_min_score', .3), 1, 'STRONG', 20, 'RULE_ONLY',
                             params['parameter_set_id'], params['content_sha256'], 2, 2000)
    return QRun(b, a, a['content_sha256'], catalog, settings, {}, None, source_kind, title)


def scene_projection(graphs, scene_id, binding):
    """An explicit per-demo scene-name projection; original graph bytes stay pinned."""
    r, c = graphs.region, graphs.camera
    for doc in (r, c):
        doc['scene_id'] = scene_id
        doc['inputs'].append({'ref': 'demo-scene-binding:' + canonical_hash(binding), 'sha256': canonical_hash(binding)})
    seal(r, 'rgraph:r004:static'); c['region_graph_sha256'] = r['content_sha256']
    seal(c, 'cgraph:r004:static')
    return GraphBundle(r, c)


class Media:
    def __init__(self, p1, authorize):
        self.p1, self.authorize = p1, authorize
        self.frames, self.grants = {}, {}

    def call(self, action, payload):
        key = payload['scene_id'], payload['run_id']
        if key == (self.p1.run.manifest['scene_id'], self.p1.run.manifest['run_id']):
            result = self.p1.call(action, payload)
            result['t_us'] = round(payload['t_s'] * 1_000_000)
            result['output_sha256'] = canonical_hash({**result, 'tiles': [
                {**t, 'media_url': None} for t in result['tiles']]}, exclude=('output_sha256', 'stats'))
            return result
        self.authorize(payload['session_ref'], key[0])
        stamp = round(payload['t_s'] * 1_000_000)
        require(action == 'synced_frames' and type(stamp) is int and stamp >= 0, 'MEDIA_SCOPE')
        require(key in self.frames, 'MEDIA_SCOPE')
        interval, by_camera, clock_id = self.frames[key]; tiles = []
        for camera in payload['camera_ids']:
            require(camera in by_camera, 'MEDIA_CAMERA_SCOPE')
            entry = by_camera[camera].get(stamp // interval)
            tile = {'camera_id': camera, 'status': 'OUT_OF_RANGE', 'media_url': None, 'frame_ref': None}
            if entry:
                path, pin = entry; raw = public_png(binary(path, pin)); token = secrets.token_urlsafe(32)
                self.grants = {k: v for k, v in self.grants.items() if v[3] > time.monotonic()}
                require(len(self.grants) < 4096, 'MEDIA_GRANT_LIMIT')
                self.grants[token] = (path, pin, payload['session_ref'], time.monotonic() + 60, key[0])
                frame = stamp // interval
                tile.update(status='READY', frame_ref=f'frame:{key[1]}:{camera}:{frame}', frame_index=frame,
                    timestamp_s=frame*interval/1_000_000, file_sha256=pin,
                    served_sha256=hashlib.sha256(raw).hexdigest(), media_token_ttl_s=60,
                    media_url='/api/controlled_scene_media?token=' + token)
            tiles.append(tile)
        result = {'schema_version': 'controlled-scene.synced-frames.v1', 'status': 'READY',
            'data_origin': 'ACTUAL_BLENDER', 'rgb_source_kind': 'ACTUAL_BLENDER',
            'resolved_scope': {'scene_id': key[0], 'run_id': key[1]},
            'clock_id': clock_id, 't_us': stamp, 'tiles': tiles, 'identity_verdict': 'UNCONFIRMED',
            'provenance': {'gt_read': False, 'producer': 'demo-integration-safe-rgb'}}
        result['output_sha256'] = canonical_hash({**result, 'tiles': [{**t, 'media_url': None} for t in tiles]})
        return result

    def media(self, token):
        if token not in self.grants:
            return self.p1.media(token)
        path, pin, session, expires, scene = self.grants[token]
        require(time.monotonic() < expires, 'MEDIA_TOKEN_EXPIRED'); self.authorize(session, scene)
        return public_png(binary(path, pin))


class Demo(P1):
    def __init__(self, artifacts, p1_bundle, state, *, job_path, job_pin, owned_root):
        super().__init__(p1_bundle, P1_PIN, state, ui_root=REPO / 'frontend/workbench-v2')
        base = list(self.api.runs.values())[0]
        runs = [replace(base, title='B-05 · P1 v4 · SYNTHETIC RGB')]
        self.rgb = Media(self.rgb, self.authorize)
        self.cross = {}; self.transitions = {}; self.positions = {}
        job = resolve_job(loads(pinned(job_path, job_pin)), owned_root)
        graph = loads(read_pin(job['graph']))
        graphs = load_scene_graphs('r004')
        require(graph == graphs.camera, 'JOB_GRAPH_MISMATCH')
        self.transitions = {(t['from_camera_id'], t['to_camera_id']): t['transition_id'] for t in graph['transitions']}
        self.cross_params = Parameters(**job['parameters'])
        media_root = artifacts/'r004-cx7r-20261104-01a19f8b/bundle/safe_bundle'
        manifest = loads(pinned(media_root/'manifest.json', MEDIA_PIN))
        catalog = loads(pinned(media_root/'provenance/camera_catalog.json', manifest['files']['provenance/camera_catalog.json']))
        require(manifest['files']['provenance/camera_catalog.json'] == job['graph_binding']['catalog_sha256'], 'STATIC_CATALOG_BINDING')
        positions = {c['camera_id']: {'xy_m': [c['camera_to_world'][0][3], c['camera_to_world'][1][3]],
            'basis_ref': 'calibration:' + c['camera_id'], 'basis_sha256': c['calibration_sha256']} for c in catalog['cameras'] if c['camera_id'] in {r['camera_id'] for r in graph['cameras']}}
        for spec in job['runs']:
            tracks, clock_doc, m = load_run(spec, graph, job['graph_binding'], self.cross_params)
            root = Path(spec['inputs']['index']['path']).parent
            store = JsonRunStore(root, {
                'index': DocumentPin('detection_index.json', spec['inputs']['index']['sha256'], m['schema_version'], m['content_sha256']),
                'records': DocumentPin(m['records_ref'], spec['inputs']['records']['sha256'], 'q-demo.detection-record.v1')})
            index = store.load_detection_index('index'); clock = ClockMapping(clock_doc)
            values = loads(read_pin(spec['inputs']['config']))['parameters']
            params = parameters(index, values)
            g = scene_projection(graphs, m['scene_id'], job['graph_binding'])
            run = qrun(index, clock, g, params, spec['label'] + ' · D124 · ACTUAL_BLENDER · 自動種子', 'ACTUAL_BLENDER')
            runs.append(run); key = m['scene_id'], m['run_id']; self.cross[key] = tracks; self.positions[key] = positions
            rel = 'runs/' + spec['label'] + '.json'; data = loads(pinned(media_root/rel, manifest['files'][rel]))
            require(data['run_id'] == m['run_id'] and data['catalog_sha256'] == job['graph_binding']['catalog_sha256'], 'RGB_INDEX_BINDING')
            by_camera = {c: {} for c in data['camera_ids']}
            records = {(r['camera_id'], r['frame_index']): r['rgb_file_sha256'] for r in index.records}
            for f in data['frames']:
                name = f['filename']; pin = f['file_sha256']
                require(name == f"rgb/{m['run_id']}/{f['camera_id']}/frame_{f['frame_index']:06d}.png"
                        and manifest['files'][name] == pin == records[(f['camera_id'], f['frame_index'])], 'RGB_INDEX_FRAME_PIN')
                by_camera[f['camera_id']][f['frame_index']] = (media_root/name, pin)
            self.rgb.frames[key] = 200_000, by_camera, m['clock_id']
        self.add_static(artifacts, runs)
        self.api = QAPI(runs, max_responses=128, max_media_refs=4096, rgb_api=self.rgb, camera_display_positions=self.positions)
        self.scenes = {r.catalog['scene_id'] for r in runs}

    def add_static(self, artifacts, runs):
        report = loads(pinned(artifacts/'d129-464-r005-probe-20261105-a/report.json', REPORT_PIN))
        g = load_scene_graphs('r005'); r, c = g.region, g.camera
        # Display/search adapter only; never used as an approved runtime tracking GraphBundle.
        r['schema_version'] = 'q-demo.region-graph.v1'; seal(r, 'rgraph:r005:static')
        c['schema_version'] = 'q-demo.camera-transition-graph.v1'; c['region_graph_sha256'] = r['content_sha256']; seal(c, 'cgraph:r005:static')
        graphs = GraphBundle(r, c); scene = r['scene_id']; run_id = 'r005-static-reviewed-v2'; clock_id = 'r005-static-declared-clock'
        clock_doc = {'schema_version': 'q-demo.clock-mapping.v1', 'run_id': run_id, 'clock_id': clock_id,
            'timezone': 'Asia/Taipei', 'wall_origin': '2026-11-07T12:00:00+08:00', 't0_us': 0, 'rate': 1,
            'source_duration_us': 1_000_000, 'mapping_kind': 'DECLARED_DEMO_CLOCK', 'mapping_version': 'static-v1',
            'declaration_source': 'STATIC_FRAME_DEMO_SLOT_NOT_CAPTURE_TIME', 'declared_by': 'Codex', 'declared_at': '2026-11-08T00:00:00+08:00'}
        clock = ClockMapping(seal(clock_doc)); rows = []; metadata = []; by_camera = {}
        for row in report['rows']:
            cid = row['camera_id']; detections = []
            for i, d in enumerate(row['shown']):
                detections.append({**d, 'observation_id': f'r005-static:{cid}:{i}', 'color': None})
            rows.append({'frame_ref': f'frame:{run_id}:{cid}:0', 'camera_id': cid, 'frame_index': 0,
                'timestamp_us': 0, 'rgb_file_sha256': row['file_sha256'], 'frame_state': 'INFERRED',
                'state_reason': None, 'detections': detections})
            metadata.append({'camera_id': cid, 'index_grid_origin_frame': 0, 'index_interval_us': 1_000_000,
                'source_frame_interval_us': 1_000_000, 'stride_samples': 1,
                'sampled_ranges_us': [[0, 1_000_000]], 'inferred_ranges_us': [[0, 1_000_000]], 'not_inferred': []})
            by_camera[cid] = {0: (artifacts/'d127-418-office-expanded-r005-preview-v2/rgb'/f'{cid}.png', row['file_sha256'])}
        color = {'version': 'STATIC_NO_COLOR', 'labels': []}; seal(color)
        m = {'schema_version': 'q-demo.detection-index.v1', 'scene_id': scene, 'scene_revision': 'r005',
            'run_id': run_id, 'clock_id': clock_id, 'detector': {**report['detector_metadata'], 'index_score_floor': .3},
            'color_method': {'version': 'STATIC_NO_COLOR', 'applies_to_classes': [], 'color_vocabulary': color},
            'sampling': {'policy': 'EVERY_NTH_SAMPLE', 'stride_samples': 1, 'per_camera': metadata},
            'source_report_sha256': REPORT_PIN,
            'provenance': {'producer': 'static-probe-report-adapter', 'gt_read': False}}
        index_key = canonical_hash(m)[:16]
        m['index_id'] = 'detidx:r005:' + run_id + ':' + index_key
        for row in rows:
            for ordinal, detection in enumerate(row['detections']):
                detection['observation_id'] = f"obs:{index_key}:{row['camera_id']}:0:{ordinal}"
        m['records_ref'] = 'static-probe-derived.records.jsonl'
        m['records_file_sha256'] = hashlib.sha256(b''.join(
            json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()+b'\n' for row in rows)).hexdigest()
        seal(m); index = DetectionSnapshot(m, tuple(rows))
        values = [{'name': k, 'value': v, 'status': 'DEMO_DEFAULT', 'unit': None,
                   'proposed_by': 'Codex', 'proposal_ref': 'issue:445'} for k, v in [('query_min_score', .3), ('segment_merge_gap_us', 0)]]
        runs.append(qrun(index, clock, graphs, parameters(index, values), 'r005 · 六張靜態圖 · 人工區域／模型候選', 'ACTUAL_BLENDER'))
        self.rgb.frames[(scene, run_id)] = 1_000_000, by_camera, clock_id

    def bootstrap(self):
        value = super().bootstrap()
        value['demo_integration'] = True
        for row in value['runs']:
            run = self.api.runs[(row['scene_id'], row['run_id'])]
            row['region_graph'] = run.bindings.graphs.region
            row['camera_map'] = self.api._camera_map(row['scene_id'], row['run_id'])
        return value

    def authorize(self, token, scene, *, audit=False):
        require(token in self.sessions and scene in self.sessions[token], 'FORBIDDEN_DATA_SCOPE')

    def call(self, action, payload):
        if action == 'session':
            require(set(payload) == {'role'} and payload['role'] in {'research', 'reviewer', 'demo'}, 'SESSION_ROLE')
            token = secrets.token_urlsafe(32); self.sessions[token] = self.scenes
            return {'session_ref': token, 'role': payload['role']}
        key = payload.get('scene_id'), payload.get('run_id')
        if action != 'q_core_track' or key not in self.cross:
            return self.api.call(action, payload, self.authorize)
        _safe_request(payload); self.authorize(payload['session_ref'], key[0]); run = self.api.runs[key]; b = run.bindings
        normalized = validate_track_request(payload, region_ids=run.catalog['region_ids'],
            class_labels=run.catalog['class_labels'], class_aliases=run.catalog['class_aliases'],
            color_labels=run.catalog['color_labels'], clock_mapping=b.clock)
        # The approved demo replay fixes automatic seed policy; arbitrary filters are unavailable.
        require(normalized['feature'] == {'class_label': 'person', 'color_label': None}
                and not normalized['region_ids'], 'AUTOMATIC_SEED_PRESET_ONLY')
        if normalized['time'] is None:
            stamp = normalized['playback_now_us']
        else:
            resolved = resolve_wall_range([b.clock], *normalized['time']['wall_range'])
            require(bool(resolved.ranges) and resolved.ranges[0].range_us[0] == 0, 'AUTOMATIC_SEED_PRESET_ONLY')
            stamp = resolved.ranges[0].range_us[1]
        require(0 <= stamp <= b.clock.duration_us, 'TIME_SCOPE')
        doc, _, _ = cross_response(self.cross[key], self.transitions, as_of_us=stamp,
            parameters=self.cross_params, clock_mapping_sha256=b.clock_sha256)
        doc['resolved_scope'] = {'scene_id': key[0], 'run_id': key[1], 'detection_index_sha256': b.index_sha256}
        doc['provenance'] = {'producer': 'demo-cross-camera-local-linker', 'gt_read': False,
            'parameter_mode': 'DEMO_DEFAULT', 'formal_eligible': False, 'seed_policy': 'AUTOMATIC_EARLIEST_LOCAL_SEED'}
        if doc['single_view'] and doc['single_view'][-1]['kind'] in {'GAP', 'LOST'}:
            doc['blind'] = _blind_for_track(run, doc['sightings'], stamp, self.positions[key])
        doc['output_sha256'] = canonical_hash(doc, exclude=('output_sha256', 'stats'))
        return doc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path)
    p.add_argument('--port', type=int, default=8785)
    args = p.parse_args(); config, root = configuration(args.config)
    state_root = owned_path(root, config['state_root']); state_root.mkdir(exist_ok=True)
    state = Path(tempfile.mkdtemp(prefix='run-', dir=state_root))/'state'
    app = Demo(owned_path(root, config['artifacts_root']), owned_path(root, config['p1_bundle']), state,
        job_path=owned_path(root, config['cross_camera_job']), job_pin=config['cross_camera_job_sha256'], owned_root=root)
    with server(app, args.port) as http:
        print(json.dumps({'url': f'http://127.0.0.1:{http.server_port}/workbench-v2/',
                          'state_root': str(state), 'runs': [r['title'] for r in app.bootstrap()['runs']]}, ensure_ascii=False), flush=True)
        http.serve_forever(poll_interval=.2)


if __name__ == '__main__':
    main()

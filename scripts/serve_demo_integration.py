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
from amidst.q1q5.graphs import GraphBundle, load_graphs
from amidst.q1q5.p1_workbench import P1, binary, public_png, require, server
from amidst.q1q5.q3_parse import ParseSettings
from amidst.q1q5.q5_controller import RuntimeBindings
from amidst.q1q5.scene_graphs import load_scene_graphs
from amidst.q1q5.scene_annotations import bind_annotations
from amidst.q1q5.store import DetectionSnapshot, DocumentPin, JsonRunStore, canonical_hash
from run_cross_camera_demo import read_pin, loads, load_run
from demo_dependency_config import configuration, owned_path, resolve_job, install_owned_io_guard
from demo_eightcam import RUN_ID as EIGHTCAM_RUN, RUN_SPECS, prepare_eightcam, source_error_code
from demo_estimate import estimate_track

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


DEMO_APPROVED_ROWS = ('query_min_score', 'top_k', 'search_window_us', 'research_interval_us', 'session_max_research_rounds',
    'switch_min_presence', 'evidence_max_observations', 'fallback_budget_ms', 'exit_rule', 'link_iou_min',
    'link_center_dist_max_diag_ratio', 'link_max_gap_us', 'link_min_score', 'link_color_rule', 'link_ambiguity_margin')
DEMO_APPROVAL_REF = 'user-chat:2026-11-19:coordinator-option-A (CL-B16 #620)'


def demo_approved(params):
    """CL-B16 (#620): the Q5 controller refuses to track unless the parameter set is APPROVED. For the 8785 recorded demo only,
    the user (2026-11-19, coordinator conversation, option A) allowed treating the A4-1/B4-1 DEMO_DEFAULT set as APPROVED. This
    does not change the pinned parameter files and is not a research/formal acceptance."""
    p = deepcopy(params)
    by = {row['name']: row for row in p['parameters']}
    boundary = by.get('exit_boundary_inclusive')
    require(boundary is not None and type(boundary.get('value')) is bool, 'DEMO_EXIT_BOUNDARY_MISSING')
    for name in DEMO_APPROVED_ROWS:   # only the rows the Q5 controller checks; every other row keeps its own status
        row = by.get(name)
        if row is not None and row.get('status') == 'DEMO_DEFAULT' and row.get('value') is not None:
            row['status'] = 'APPROVED'
            row['proposal_ref'] = row.get('proposal_ref') or DEMO_APPROVAL_REF
    rule = by.get('exit_rule')   # same rule, spelled the way the Q5 controller reads it (method + boundary_inclusive)
    if rule is not None and rule.get('value') == 'BBOX_BOTTOM_MIDPOINT_IN_ROI':
        rule['value'] = {'method': 'BBOX_BOTTOM_MIDPOINT', 'boundary_inclusive': boundary['value']}
    p['approval'] = {'status': 'APPROVED', 'approval_ref': DEMO_APPROVAL_REF, 'approved_by': 'user-demo-only'}
    return seal(p, 'pset:q-demo')


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
    if graphs.tracking_scope is None:
        return GraphBundle(r, c)
    # CL-B16 (#620): the graphs still carry their tracking-scope pins, so dropping the scope made every Q2 session on
    # A4-1/B4-1 answer TRACKING_SCOPE_MISSING (rule and Agent alike). Re-attach the byte-pinned scope and re-verify it.
    return load_graphs(r, c, region_sha256=r['content_sha256'], camera_sha256=c['content_sha256'],
                       tracking_scope=graphs.tracking_scope, tracking_scope_sha256=graphs.tracking_scope_sha256,
                       tracking_scope_bytes=graphs.tracking_scope_bytes)


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
    def __init__(self, artifacts, p1_bundle, state, *, job_path, job_pin, owned_root,
                 eightcam=None, eightcam_reason='ROOT_NOT_CONFIGURED', eightcam_required=True, agent_queue=None):
        super().__init__(p1_bundle, P1_PIN, state, ui_root=REPO / 'frontend/workbench-v2')
        base = list(self.api.runs.values())[0]
        runs = [replace(base, title='B-05 · P1 v4 · SYNTHETIC RGB')]
        self.rgb = Media(self.rgb, self.authorize)
        self.core_track_keys = {(base.catalog['scene_id'], base.catalog['run_id'])}
        self.cross = {}; self.transitions = {}; self.positions = {}; agent_scenes = {}
        self.calibrations = {}
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
            params = demo_approved(parameters(index, values))
            g = scene_projection(graphs, m['scene_id'], job['graph_binding'])
            run = qrun(index, clock, g, params, spec['label'] + ' · D124 · ACTUAL_BLENDER · 自動種子', 'ACTUAL_BLENDER')
            runs.append(run); key = m['scene_id'], m['run_id']; self.cross[key] = tracks; self.positions[key] = positions
            self.calibrations[key] = (catalog, job['graph_binding']['catalog_sha256'])
            agent_scenes[key] = (catalog, manifest['files']['provenance/camera_catalog.json'])
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
        self.eightcam_status = {'run_id': EIGHTCAM_RUN, 'status': 'UNKNOWN', 'reason': eightcam_reason}
        if eightcam is not None:
            try:
                loaded = [(source, *self.load_eightcam(source, graphs))
                          for source in eightcam.sources]
            except (ValueError, OSError, TypeError, KeyError) as exc:
                if eightcam_required:
                    raise
                self.eightcam_status['reason'] = source_error_code(exc)
            else:
                for source, added, frames, camera_positions, calibration in loaded:
                    key = (added.catalog['scene_id'], source.run_id)
                    runs.append(added)
                    self.core_track_keys.add(key)
                    self.rgb.frames[key] = frames
                    self.positions[key] = camera_positions
                    self.calibrations[key] = calibration
                    agent_scenes[key] = calibration
                self.eightcam_status.update(status='READY', reason=None)
        runs = [bind_annotations(run, REPO / "configs/q1q5/scene_annotations_v1.json") for run in runs]
        if agent_queue is not None:   # #601: default off; AMIDST_RECORDED_AGENT=openai binds the OpenAI-gateway Agent (no socket in this process)
            from amidst.q1q5.openai_gateway import configure_environment
            runs = list(configure_environment(runs, agent_queue, service=self.agent_service(graphs, agent_scenes)))
        self.api = QAPI(runs, max_responses=512, max_media_refs=4096, rgb_api=self.rgb,
                        camera_display_positions=self.positions, track_estimator=self.estimate)
        self.scenes = {r.catalog['scene_id'] for r in runs}

    @staticmethod
    def load_eightcam(eightcam, graphs):
        index, clock, settings, catalog, camera_graph, frames = eightcam.load()
        require(camera_graph == graphs.camera, 'EIGHTCAM_GRAPH_BINDING')
        bound = scene_projection(graphs, index.manifest['scene_id'], {
            'camera_catalog_sha256': settings['catalog_sha256'],
            'clock_sha256': settings['clock_sha256'],
            'run_id': eightcam.run_id,
        })
        params = parameters(index, settings['parameters'])
        run = qrun(index, clock, bound, params, eightcam.title, 'ACTUAL_BLENDER')
        positions = {
            c['camera_id']: {'xy_m': [c['camera_to_world'][0][3], c['camera_to_world'][1][3]],
                             'basis_ref': 'calibration:'+c['camera_id'],
                             'basis_sha256': c['calibration_sha256']}
            for c in catalog['cameras']
        }
        return run, frames, positions, (catalog, settings['catalog_sha256'])

    def track_decider(self, key, run):
        """One ServiceTrackDecider per run (its answer cache makes replays free). None + reason when the Agent cannot run."""
        from amidst.q1q5.openai_gateway import agent_status
        from amidst.q1q5.service_agent_q5 import ServiceAgentFactory
        from amidst.q1q5.service_agent_track import ServiceTrackDecider
        factory = run.agent_factory
        if not isinstance(factory, ServiceAgentFactory):
            return None, 'AGENT_NOT_CONFIGURED'
        ok, reason = agent_status(run)
        if not ok:
            return None, reason
        cache = self.__dict__.setdefault('track_deciders', {})
        if key not in cache:
            cache[key] = ServiceTrackDecider(factory.transport, run.bindings.index.records, scene_context=factory.scene_context,
                                             frame_reader=factory.frame_reader, model=factory.model)
        return cache[key], None

    def agent_service(self, graphs, agent_scenes):
        """F3 (#657): per-run agent_service inputs. scene_context from the pinned r004 graphs + the run's catalog + D346 walls; frames from
        the server's pinned RGB table. A run without a catalog gets no scene_context (requests say SCENE_CONTEXT_INCOMPLETE)."""
        from amidst.q1q5.service_agent_q5 import pinned_frame_reader, r004_scene_context

        def service(run):
            key = (run.catalog['scene_id'], run.catalog['run_id'])
            out = {}
            if key in agent_scenes:
                catalog, catalog_sha = agent_scenes[key]
                ids = {x['camera_id'] for x in run.bindings.index.manifest['sampling']['per_camera']} & {c['camera_id'] for c in catalog['cameras']}
                out['scene_context'] = r004_scene_context(graphs, catalog, catalog_sha, ids, REPO)
            if key in self.rgb.frames:
                out['frame_reader'] = pinned_frame_reader(self.rgb.frames[key][1])
            elif key == (self.rgb.p1.run.manifest['scene_id'], self.rgb.p1.run.manifest['run_id']):
                # B-05 uses its existing hash-checked RGB reader. Its synthetic
                # graph exists, but calibrated geometry is unavailable: disclose it.
                from amidst.q1q5 import scene_context as sx
                b = run.bindings
                ctx = sx.build(b.graphs.region, b.graphs.camera, {'cameras': []},
                               source_sha256={'region_graph.content_sha256': b.region_graph_sha256,
                                              'camera_graph.content_sha256': b.camera_graph_sha256})
                ctx['cameras'] = [{'camera_id': cid, 'position_xyz_m': 'UNKNOWN', 'yaw_deg_0_is_plus_x': 'UNKNOWN',
                                   'fov_h_deg': 'UNKNOWN', 'ground_footprint_polygon_xy_m': 'UNKNOWN',
                                   'entry_zones': c.get('entry_zones', []), 'exit_zones': [
                                       {k: z[k] for k in ('exit_zone_id', 'roi_polygon_px', 'leads_to_edge_ids')} for z in c.get('exit_zones', [])]}
                                  for cid in run.catalog['camera_ids'] for c in b.graphs.camera['cameras'] if c['camera_id'] == cid]
                ctx['incomplete'].extend(['SCENE_CONTEXT_INCOMPLETE:CALIBRATION_POSITION_HEADING_FOV_FOOTPRINT_OVERLAPS:' + cid
                                          for cid in run.catalog['camera_ids']])
                sx.assert_no_forbidden(ctx)
                out.update(scene_context=ctx, frame_reader=self.rgb.p1.run.read_rgb)
            return out
        return service

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
        value['eightcam'] = self.eightcam_status.copy()
        value['eightcam_runs'] = [
            {'label': label + '-8CAM', 'run_id': spec['run_id'],
             'status': self.eightcam_status['status'], 'reason': self.eightcam_status['reason']}
            for label, spec in RUN_SPECS.items()
        ] + [
            {'label': label + '-8CAM', 'run_id': None, 'status': 'UNKNOWN',
             'reason': 'NO_PINNED_EIGHTCAM_SOURCE_IN_APPROVED_BUNDLE'}
            for label in ('B-05', 'r005')
        ]
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
        if action == 'q_core_track' and key in self.core_track_keys:
            from amidst.q1q5.service_core_track import core_track
            _safe_request(payload); self.authorize(payload['session_ref'], key[0])
            run = self.api.runs[key]
            decider, why = self.track_decider(key, run) if payload.get('switch_mode') == 'AGENT_SEQUENTIAL' else (None, None)
            doc = core_track(payload, run, decider=decider, unavailable_reason=why,
                             demo_default=key[1] in {s['run_id'] for s in RUN_SPECS.values()},
                             display_positions=self.positions.get(key))
            return self.with_estimate(key, doc)
        if action != 'q_core_track' or key not in self.cross:
            if action == 'q_core_track':
                require('manual_seed' not in payload, 'MANUAL_SEED_UNSUPPORTED')
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
        agent_mode = normalized.get('switch_mode') == 'AGENT_SEQUENTIAL'
        decider, why = self.track_decider(key, run) if agent_mode else (None, None)
        ms = normalized.get('manual_seed')
        if ms is not None:
            require(any(t.track_ref == ms['track_ref'] for t in self.cross[key]) and ms['at_us'] <= stamp, 'MANUAL_SEED_UNKNOWN')
        doc, _, _ = cross_response(self.cross[key], self.transitions, as_of_us=stamp,
            parameters=self.cross_params, clock_mapping_sha256=b.clock_sha256, decider=decider,
            manual=(ms['track_ref'], ms['at_us']) if ms else None)
        if ms is not None:
            doc['manual_seed'] = dict(ms, applied=any(r.get('reason') == 'OPERATOR_SELECTION' for r in doc['association_audit']))
        if agent_mode:   # F3 (#657): which decisions the Agent made and whether they were adopted (association_audit has every row)
            rows = [r for r in doc['association_audit'] if r.get('reason') == 'AGENT_SERVICE_DECISION']
            doc['agent'] = {'switch_mode': 'AGENT_SEQUENTIAL', 'available': decider is not None, 'unavailable_reason': why,
                            'decisions': len(rows), 'adopted': sum(1 for r in rows if r.get('adopted_track_ref')),
                            'fallbacks': sum(1 for r in rows if r.get('fallback_reason')), 'model_calls_total': decider.calls if decider else 0,
                            'agent_used': any(e.get('reason') == 'AGENT_ASSOCIATION_HYPOTHESIS' for e in doc['association_audit'])}
        doc['resolved_scope'] = {'scene_id': key[0], 'run_id': key[1], 'detection_index_sha256': b.index_sha256}
        doc['provenance'] = {'producer': 'demo-cross-camera-local-linker', 'gt_read': False,
            'parameter_mode': 'DEMO_DEFAULT', 'formal_eligible': False, 'seed_policy': 'AUTOMATIC_EARLIEST_LOCAL_SEED',
            'replay_policy': 'D147_D148', 'seed_min_score': .3, 'continuation_min_score': .3,
            'max_area_ratio': 12, 'same_camera_merge_gap_us': 600_000}
        if doc['single_view'] and doc['single_view'][-1]['kind'] in {'GAP', 'LOST'}:
            doc['blind'] = _blind_for_track(run, doc['sightings'], stamp, self.positions[key])
        return self.with_estimate(key, doc)

    def with_estimate(self, key, doc):
        run = self.api.runs[key]
        doc['estimate'] = self.estimate(run, doc)
        doc['output_sha256'] = canonical_hash(doc, exclude=('output_sha256', 'stats'))
        return doc

    def estimate(self, run, doc):
        key = run.catalog['scene_id'], run.catalog['run_id']
        catalog, pin = self.calibrations.get(key, (None, None))
        return estimate_track(
            run.bindings.index.records, doc, catalog, catalog_sha256=pin,
            index_sha256=run.bindings.index_sha256, clock_id=run.bindings.clock.clock_id)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path)
    p.add_argument('--port', type=int, default=8785)
    p.add_argument('--root-8cam', type=Path, help='Existing #529 safe bundle for A4-1/B4-1-8CAM')
    p.add_argument('--auto-root-8cam', type=Path, help='Optional launcher-discovered A4-1/B4-1-8CAM bundle')
    args = p.parse_args(); config, root = configuration(args.config)
    eightcam_required = args.root_8cam is not None
    eightcam, reason = prepare_eightcam(args.root_8cam or args.auto_root_8cam, required=eightcam_required)
    app = None
    install_owned_io_guard(root, approved_read_files=eightcam.read_files if eightcam else (),
                           approved_reads_active=lambda: app is None or app.eightcam_status['status'] == 'READY')
    state_root = owned_path(root, config['state_root']); state_root.mkdir(exist_ok=True)
    state = Path(tempfile.mkdtemp(prefix='run-', dir=state_root))/'state'
    app = Demo(owned_path(root, config['artifacts_root']), owned_path(root, config['p1_bundle']), state,
        job_path=owned_path(root, config['cross_camera_job']), job_pin=config['cross_camera_job_sha256'], owned_root=root,
        eightcam=eightcam, eightcam_reason=reason, eightcam_required=eightcam_required,
        agent_queue=state_root/'agent-gateway')
    with server(app, args.port) as http:
        print(json.dumps({'url': f'http://127.0.0.1:{http.server_port}/workbench-v2/',
                          'state_root': str(state), 'runs': [r['title'] for r in app.bootstrap()['runs']],
                          'eightcam': app.eightcam_status}, ensure_ascii=False), flush=True)
        http.serve_forever(poll_interval=.2)


if __name__ == '__main__':
    main()

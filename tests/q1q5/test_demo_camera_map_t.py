"""DEMO-UI-A-T: camera map for the overhead view (DEMO_UI_SUPPORT_V1 §2). Test-first; Codex implements."""
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

import pytest
from demo_ui_support_helpers import missing, require_module, require_route, walk_keys
from test_api import OTHER, TOKEN, api_fixture, authorize, selected

from amidst.q1q5.api import QAPI, APIError
from amidst.q1q5.store import canonical_hash

ROOT = Path(__file__).resolve().parents[2]
CODE = 'CAMERA_MAP_IMPLEMENTATION_MISSING'
P1_AUDIT = ROOT / 'docs/history/q1q5_ab_gap_20261025/audit.json'
P1_AUDIT_SHA256 = '80fe6aee4e8f778d22b18b4f1184600eda20abbf5691db83a761aaf5336408a4'
R004 = ROOT / 'configs/q1q5/graphs/r004'
R004_V3_1_PINS = {  # #306 A17 (camera, region) and #294@0c34287 (tracking scope), file-byte SHA-256
    'camera_graph_v3_1.json': 'e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409',
    'region_graph_v3_1.json': 'a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1',
    'tracking_scope_v3_1.json': 'ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a',
}
TOP_KEYS = {'schema_version', 'scene_id', 'scene_revision', 'run_id', 'graph', 'layout', 'display_note', 'cameras',
            'regions', 'edges', 'transitions', 'identity_verdict', 'physical_navigation', 'gt_read', 'content_sha256'}
GRAPH_KEYS = {'camera_graph_sha256', 'region_graph_sha256', 'camera_graph_id', 'approval_status', 'approval_ref',
              'tracking_scope_sha256', 'tracking_scope_status', 'g4_approved'}
CAMERA_KEYS = {'camera_id', 'in_graph', 'role', 'covered_region_ids', 'exits', 'display_position'}
POSITION_KEYS = {'status', 'xy_m', 'basis_ref', 'basis_sha256'}
TRANSITION_KEYS = {'transition_id', 'from_camera_id', 'to_camera_id', 'relation', 'path_traversability',
                   'path_has_unknown_state', 'via_exit_zone_ids', 'to_entry_zone_ids', 'edge_path', 'region_path',
                   'edge_states', 'authority'}


def module():
    return require_module('AMIDST_CAMERA_MAP_MODULE', 'amidst.q1q5.camera_map', CODE, ('build_camera_map', 'CameraMapError'))


def synthetic_inputs(run=None):
    if run is None:
        _, run = api_fixture()
    b = run.bindings
    return {'scene_id': run.catalog['scene_id'], 'run_id': run.catalog['run_id'],
            'camera_graph': b.graphs.camera, 'region_graph': b.graphs.region,
            'camera_graph_sha256': b.camera_graph_sha256, 'region_graph_sha256': b.region_graph_sha256,
            'run_camera_ids': ['A', 'B']}


def p1_inputs():
    raw = P1_AUDIT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == P1_AUDIT_SHA256
    audit = json.loads(raw)
    graphs = audit['graph_caveat']
    positions = {cid: {'xy_m': cal['position'][:2],
                       'basis_ref': 'docs/history/q1q5_ab_gap_20261025/audit.json#camera_calibration',
                       'basis_sha256': P1_AUDIT_SHA256}
                 for cid, cal in audit['camera_calibration'].items()}
    return {'scene_id': audit['scene_id'], 'run_id': audit['run_id'],
            'camera_graph': graphs['camera_graph'], 'region_graph': graphs['region_graph'],
            'camera_graph_sha256': graphs['camera_graph']['content_sha256'],
            'region_graph_sha256': graphs['region_graph']['content_sha256'],
            'run_camera_ids': ['A', 'B']}, positions


def error_code(excinfo):
    return getattr(excinfo.value, 'code', None)


def test_synthetic_map_has_whitelisted_shape_and_honest_labels():
    m = module(); doc = m.build_camera_map(**synthetic_inputs())
    assert set(doc) == TOP_KEYS and doc['schema_version'] == 'q-demo.camera-map.v1'
    assert set(doc['graph']) == GRAPH_KEYS
    assert doc['identity_verdict'] == 'UNCONFIRMED' and doc['physical_navigation'] == 'UNKNOWN' and doc['gt_read'] is False
    assert [c['camera_id'] for c in doc['cameras']] == ['A', 'B']
    for camera in doc['cameras']:
        assert set(camera) == CAMERA_KEYS and set(camera['display_position']) == POSITION_KEYS
        assert camera['display_position']['status'] == 'UNKNOWN' and camera['display_position']['xy_m'] is None
        assert all(set(e) == {'exit_zone_id', 'leads_to_edge_ids'} for e in camera['exits'])
    assert doc['layout'] == 'NODE_GRAPH' and doc['display_note'] == '示意圖，非實際座標'
    assert all(set(t) == TRANSITION_KEYS for t in doc['transitions'])
    assert [t['transition_id'] for t in doc['transitions']] == sorted(t['transition_id'] for t in doc['transitions'])
    keys = set(walk_keys(doc))
    assert not keys & {'roi_polygon_px', 'static_frame_ref', 'static_frame_sha256', 'calibration_sha256', 'visibility_ref'}
    assert doc['content_sha256'] == canonical_hash(doc, exclude=('content_sha256',))


def test_pins_and_forbidden_inputs_fail_closed():
    m = module(); good = synthetic_inputs()
    with pytest.raises(ValueError) as err:
        m.build_camera_map(**dict(good, camera_graph_sha256='0' * 64))
    assert error_code(err) == 'GRAPH_PIN_MISMATCH'
    tampered = deepcopy(good['camera_graph']); tampered['transitions'][0]['relation'] = 'OVERLAP'
    with pytest.raises(ValueError) as err:
        m.build_camera_map(**dict(good, camera_graph=tampered))
    assert error_code(err) == 'GRAPH_PIN_MISMATCH'
    for key in ('renderer_trajectory', 'ground_truth', 'depth', 'actor_id'):
        bad = deepcopy(good['camera_graph']); bad['cameras'][0][key] = 'SYNTHETIC'
        with pytest.raises(ValueError) as err:
            m.build_camera_map(**dict(good, camera_graph=bad))
        assert error_code(err) == 'FORBIDDEN_INFERENCE_INPUT'


def test_run_camera_outside_graph_is_listed_without_topology():
    doc = module().build_camera_map(**dict(synthetic_inputs(), run_camera_ids=['A', 'B', 'CAM_X']))
    extra = next(c for c in doc['cameras'] if c['camera_id'] == 'CAM_X')
    assert extra['in_graph'] is False and extra['role'] == 'NOT_IN_GRAPH' and extra['exits'] == []
    assert all('CAM_X' not in (t['from_camera_id'], t['to_camera_id']) for t in doc['transitions'])


def test_p1_static_calibration_positions_give_metric_layout():
    m = module(); inputs, positions = p1_inputs()
    doc = m.build_camera_map(**inputs, display_positions=positions)
    assert doc['layout'] == 'METRIC_STATIC'
    by = {c['camera_id']: c['display_position'] for c in doc['cameras']}
    assert by['A'] == {'status': 'CALIBRATED_STATIC', 'xy_m': [2.0, -5.5],
                       'basis_ref': 'docs/history/q1q5_ab_gap_20261025/audit.json#camera_calibration',
                       'basis_sha256': P1_AUDIT_SHA256}
    assert by['B']['xy_m'] == [16.0, -5.5]
    assert doc['graph']['approval_ref'] == 'SYNTHETIC_ENGINEERING_ONLY'
    partial = m.build_camera_map(**inputs, display_positions={'A': positions['A']})
    assert partial['layout'] == 'NODE_GRAPH'
    assert {c['camera_id']: c['display_position']['status'] for c in partial['cameras']} == {'A': 'CALIBRATED_STATIC', 'B': 'UNKNOWN'}


@pytest.mark.parametrize('change,code', [
    (lambda p: p.update(Z=dict(p['A'])), 'DISPLAY_POSITION_INVALID'),
    (lambda p: p['A'].update(xy_m=[math.nan, 0.0]), 'DISPLAY_POSITION_INVALID'),
    (lambda p: p['A'].update(xy_m=[1.0]), 'DISPLAY_POSITION_INVALID'),
    (lambda p: p['A'].update(basis_ref='private/gt/camera_poses.json'), 'FORBIDDEN_INFERENCE_INPUT'),
    (lambda p: p['A'].update(basis_ref='renders/renderer_trajectory.json'), 'FORBIDDEN_INFERENCE_INPUT'),
])
def test_display_positions_are_validated(change, code):
    m = module(); inputs, positions = p1_inputs(); change(positions)
    with pytest.raises(ValueError) as err:
        m.build_camera_map(**inputs, display_positions=positions)
    assert error_code(err) == code


def test_pinned_r004_v3_1_keeps_draft_and_unknown_states():
    m = module()
    paths = {name: R004 / name for name in R004_V3_1_PINS}
    if not all(p.is_file() for p in paths.values()):
        missing('R004_V3_1_GRAPH_NOT_IN_TREE')
    raw = {name: p.read_bytes() for name, p in paths.items()}
    for name, digest in R004_V3_1_PINS.items():
        assert hashlib.sha256(raw[name]).hexdigest() == digest, name
    camera, region, scope = (json.loads(raw[n]) for n in R004_V3_1_PINS)
    run_ids = json.loads((ROOT / 'configs/q1q5/runs/r004_a4_v1.json').read_bytes())['camera_ids']
    doc = m.build_camera_map(scene_id=camera['scene_id'], run_id='r004_a4_v1', camera_graph=camera, region_graph=region,
                             camera_graph_sha256=camera['content_sha256'], region_graph_sha256=region['content_sha256'],
                             run_camera_ids=run_ids, tracking_scope=scope,
                             tracking_scope_sha256=R004_V3_1_PINS['tracking_scope_v3_1.json'])
    assert doc['graph']['approval_status'] == 'DRAFT' and doc['graph']['g4_approved'] is False
    assert doc['graph']['tracking_scope_status'] == 'PROPOSED'
    assert len(doc['transitions']) == 22 and {t['authority'] for t in doc['transitions']} == {'DRAFT'}
    w = next(t for t in doc['transitions'] if t['transition_id'] == 'T_CAM_W1__CAM_W2')
    assert w['path_traversability'] == 'APPROVED_WALKABLE' and w['authority'] == 'DRAFT'
    assert {e['state'] for e in doc['edges']} == {'UNKNOWN'}
    roles = {c['camera_id']: c['role'] for c in doc['cameras']}
    assert roles['CAM_ENTRY'] == 'QUERY_ONLY' and len(roles) == 8
    assert {c['display_position']['status'] for c in doc['cameras']} == {'UNKNOWN'} and doc['layout'] == 'NODE_GRAPH'


def test_map_is_deterministic_and_order_independent():
    m = module(); inputs = synthetic_inputs()
    reordered = dict(inputs, run_camera_ids=['B', 'A', 'B'])
    assert m.build_camera_map(**inputs) == m.build_camera_map(**reordered) == m.build_camera_map(**deepcopy(inputs))


def test_api_serves_live_run_map_bound_to_bootstrap_pins():
    module(); require_route('q_camera_map', CODE)
    api, run = api_fixture()
    row = api.bootstrap()['runs'][0]
    payload = {'session_ref': TOKEN, 'scene_id': row['scene_id'], 'run_id': row['run_id']}
    doc = api.call('q_camera_map', payload, authorize)
    assert doc['graph']['camera_graph_sha256'] == row['camera_graph_sha256']
    assert doc['graph']['region_graph_sha256'] == row['region_graph_sha256']
    assert {c['camera_id'] for c in doc['cameras']} >= set(row['camera_ids'])
    with pytest.raises(APIError) as err:
        api.call('q_camera_map', dict(payload, session_ref='SYNTHETIC_UNKNOWN'), authorize)
    assert err.value.status == 403
    with pytest.raises(APIError) as err:
        api.call('q_camera_map', dict(payload, run_id='NO_SUCH_RUN'), authorize)
    assert (err.value.code, err.value.status) == ('Q_RUN_NOT_CONFIGURED', 503)
    with pytest.raises(APIError) as err:
        api.call('q_camera_map', dict(payload, camera_graph='configs/x.json'), authorize)
    assert err.value.status in {403, 422}


def test_api_applies_configured_display_positions():
    module(); require_route('q_camera_map', CODE)
    positions = {'A': {'xy_m': [0.0, 0.0], 'basis_ref': 'synthetic://static', 'basis_sha256': 'a' * 64},
                 'B': {'xy_m': [5.0, 0.0], 'basis_ref': 'synthetic://static', 'basis_sha256': 'a' * 64}}
    api, _ = api_fixture(camera_display_positions={('SYNTHETIC_SCENE', 'SYNTHETIC_RUN'): positions})
    doc = api.call('q_camera_map', {'session_ref': OTHER, 'scene_id': 'SYNTHETIC_SCENE', 'run_id': 'SYNTHETIC_RUN'}, authorize)
    assert doc['layout'] == 'METRIC_STATIC'


def test_recorded_only_mode_serves_verified_prebuilt_map(tmp_path):
    m = module(); require_route('q_camera_map', CODE)
    api, run = api_fixture(tmp_path); r = selected(api, run)
    pin = api.call('q_record_response', {'session_ref': TOKEN, 'response_ref': r['session_id']}, authorize)
    descriptor = {k: pin[k] for k in ['recording_id', 'file', 'file_sha256']}
    doc = m.build_camera_map(**synthetic_inputs(run))
    replay = QAPI(max_responses=8, max_media_refs=64, recording_store=api.recording_store,
                  recordings=[descriptor], camera_maps=[doc])
    assert replay.bootstrap()['camera_maps'] == [{'scene_id': 'SYNTHETIC_SCENE', 'run_id': 'SYNTHETIC_RUN', 'layout': 'NODE_GRAPH'}]
    served = replay.call('q_camera_map', {'session_ref': OTHER, 'scene_id': 'SYNTHETIC_SCENE', 'run_id': 'SYNTHETIC_RUN'}, authorize)
    assert served == doc
    tampered = deepcopy(doc); tampered['layout'] = 'METRIC_STATIC'
    with pytest.raises(APIError) as err:
        QAPI(max_responses=8, max_media_refs=64, recording_store=api.recording_store, recordings=[descriptor], camera_maps=[tampered])
    assert err.value.status == 409
    other = deepcopy(doc); other['graph']['camera_graph_sha256'] = 'b' * 64
    other['content_sha256'] = canonical_hash(other, exclude=('content_sha256',))
    with pytest.raises(APIError) as err:
        QAPI(max_responses=8, max_media_refs=64, recording_store=api.recording_store, recordings=[descriptor], camera_maps=[other])
    assert err.value.status == 409

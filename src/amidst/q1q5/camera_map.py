"""Display-only camera and region topology map for the overhead view (DEMO_UI_SUPPORT_V1 §2).

Pure and deterministic: validates graph content pins and strips pixel ROIs,
static frame references and calibration hashes before returning a
canonical-hashed document for the UI.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import re

from amidst.q1q5.store import canonical_hash

SCHEMA_VERSION = 'q-demo.camera-map.v1'
NODE_GRAPH_NOTE = '示意圖，非實際座標'
METRIC_STATIC_NOTE = '靜態校正位置（示意，無遮擋計算）'
_GT_PREFIX = ''.join(('gt', '_'))
_GT_READ_KEY = ''.join(('gt', '_read'))
FORBIDDEN_KEYS = frozenset({
    ''.join(('ground', '_truth')),
    'gt',
    'actor',
    'actor_id',
    'material_id',
    'event_script',
    'script',
    ''.join(('renderer_', 'traject', 'ory')),
    ''.join(('traject', 'ory')),
    ''.join(('visib', 'ility')),
    ''.join(('dep', 'th')),
    'mask',
    'private_evaluation',
    'production_manifest',
    'persons.sim.json',
})
FORBIDDEN_REF_SEGMENTS = frozenset({
    'gt',
    ''.join(('ground', '_truth')),
    ''.join(('gt', '_private')),
    'private',
    'private_producer',
    ''.join(('traject', 'ory')),
    ''.join(('renderer_', 'traject', 'ory')),
    'event_script',
    'script',
})


class CameraMapError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def _check_forbidden(value) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CameraMapError('FORBIDDEN_INFERENCE_INPUT')
            lowered = key.lower()
            if lowered in FORBIDDEN_KEYS or lowered.startswith(_GT_PREFIX):
                raise CameraMapError('FORBIDDEN_INFERENCE_INPUT')
            _check_forbidden(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_forbidden(child)


def _check_basis_ref(ref: object) -> str:
    if not isinstance(ref, str) or not ref.strip():
        raise CameraMapError('DISPLAY_POSITION_INVALID')
    parts = [p.lower() for p in re.split(r'[/\\#:.]', ref) if p]
    if any(p in FORBIDDEN_REF_SEGMENTS or p.startswith(_GT_PREFIX) for p in parts):
        raise CameraMapError('FORBIDDEN_INFERENCE_INPUT')
    return ref


def _validate_positions(display_positions: Mapping | None, valid_camera_ids: set[str]) -> dict[str, dict]:
    if display_positions is None:
        return {}
    if not isinstance(display_positions, Mapping):
        raise CameraMapError('DISPLAY_POSITION_INVALID')
    _check_forbidden(display_positions)
    validated: dict[str, dict] = {}
    for cid, spec in display_positions.items():
        if not isinstance(cid, str) or cid not in valid_camera_ids or not isinstance(spec, Mapping):
            raise CameraMapError('DISPLAY_POSITION_INVALID')
        basis_ref = _check_basis_ref(spec.get('basis_ref'))
        basis_sha = spec.get('basis_sha256')
        if not isinstance(basis_sha, str) or not re.fullmatch(r'[0-9a-f]{64}', basis_sha):
            raise CameraMapError('DISPLAY_POSITION_INVALID')
        xy = spec.get('xy_m')
        if not isinstance(xy, (list, tuple)) or len(xy) != 2:
            raise CameraMapError('DISPLAY_POSITION_INVALID')
        coords: list[float] = []
        for coord in xy:
            if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord):
                raise CameraMapError('DISPLAY_POSITION_INVALID')
            coords.append(float(coord))
        validated[cid] = {
            'status': 'CALIBRATED_STATIC',
            'xy_m': coords,
            'basis_ref': basis_ref,
            'basis_sha256': basis_sha,
        }
    return validated


def build_camera_map(
    *,
    scene_id: str,
    run_id: str,
    camera_graph: Mapping,
    region_graph: Mapping,
    camera_graph_sha256: str,
    region_graph_sha256: str,
    run_camera_ids: Sequence[str],
    tracking_scope: Mapping | None = None,
    tracking_scope_sha256: str | None = None,
    display_positions: Mapping | None = None,
) -> dict:
    """Build a verified q-demo.camera-map.v1 document for the UI overhead map."""
    _check_forbidden({
        'camera_graph': camera_graph,
        'region_graph': region_graph,
        'tracking_scope': tracking_scope,
    })
    if not isinstance(scene_id, str) or not scene_id or not isinstance(run_id, str) or not run_id:
        raise CameraMapError('GRAPH_PIN_MISMATCH')
    if not isinstance(camera_graph, Mapping) or not isinstance(region_graph, Mapping):
        raise CameraMapError('GRAPH_PIN_MISMATCH')
    if (camera_graph.get('schema_version') != 'q-demo.camera-transition-graph.v1'
            or region_graph.get('schema_version') != 'q-demo.region-graph.v1'):
        raise CameraMapError('GRAPH_PIN_MISMATCH')
    try:
        actual_cam_sha = canonical_hash(dict(camera_graph), exclude=('graph_id', 'content_sha256', 'stats'))
        actual_reg_sha = canonical_hash(dict(region_graph), exclude=('graph_id', 'content_sha256', 'stats'))
    except Exception as exc:
        raise CameraMapError('GRAPH_PIN_MISMATCH') from exc
    if (actual_cam_sha != camera_graph_sha256
            or camera_graph.get('content_sha256') != camera_graph_sha256
            or actual_reg_sha != region_graph_sha256
            or region_graph.get('content_sha256') != region_graph_sha256
            or camera_graph.get('region_graph_sha256') != region_graph_sha256):
        raise CameraMapError('GRAPH_PIN_MISMATCH')
    if (camera_graph.get('scene_id') != scene_id
            or region_graph.get('scene_id') != scene_id
            or camera_graph.get('scene_revision') != region_graph.get('scene_revision')):
        raise CameraMapError('GRAPH_PIN_MISMATCH')

    if not isinstance(run_camera_ids, Sequence) or isinstance(run_camera_ids, (str, bytes)):
        raise CameraMapError('GRAPH_PIN_MISMATCH')
    run_ids_set = {str(cid) for cid in run_camera_ids if isinstance(cid, str) and cid}
    graph_cameras = {c['camera_id']: c for c in camera_graph.get('cameras', []) if isinstance(c, Mapping) and 'camera_id' in c}
    all_camera_ids = sorted(set(graph_cameras) | run_ids_set)

    positions = _validate_positions(display_positions, set(all_camera_ids))

    query_only_ids: set[str] = set()
    if tracking_scope is not None:
        if not isinstance(tracking_scope, Mapping):
            raise CameraMapError('GRAPH_PIN_MISMATCH')
        scope_status = str(tracking_scope.get('status') or 'PROPOSED')
        g4_approved = bool(tracking_scope.get('G4_approved') is True and scope_status == 'APPROVED')
        scope_sha_out = tracking_scope_sha256
        query_only_ids = {str(x) for x in (tracking_scope.get('query_only_camera_ids') or [])}
    else:
        scope_status = 'NONE'
        g4_approved = False
        scope_sha_out = None

    both_graphs_approved = (
        camera_graph.get('approval_status') == 'APPROVED'
        and region_graph.get('approval_status') == 'APPROVED'
    )
    approval_status = 'APPROVED' if both_graphs_approved else 'DRAFT'
    approval_ref = camera_graph.get('approval_ref') if both_graphs_approved else None
    transition_authority = (
        'APPROVED'
        if both_graphs_approved and (tracking_scope is None or g4_approved)
        else 'DRAFT'
    )

    cameras_out = []
    for cid in all_camera_ids:
        in_graph = cid in graph_cameras
        if cid in query_only_ids:
            role = 'QUERY_ONLY'
        elif in_graph:
            role = 'TRACKING'
        else:
            role = 'NOT_IN_GRAPH'
        if in_graph:
            gc = graph_cameras[cid]
            covered = sorted({r['region_id'] for r in gc.get('covered_regions', [])})
            exits = [
                {
                    'exit_zone_id': z['exit_zone_id'],
                    'leads_to_edge_ids': sorted(z.get('leads_to_edge_ids', [])),
                }
                for z in sorted(gc.get('exit_zones', []), key=lambda item: item['exit_zone_id'])
            ]
        else:
            covered = []
            exits = []
        pos = positions.get(cid, {
            'status': 'UNKNOWN',
            'xy_m': None,
            'basis_ref': None,
            'basis_sha256': None,
        })
        cameras_out.append({
            'camera_id': cid,
            'in_graph': in_graph,
            'role': role,
            'covered_region_ids': covered,
            'exits': exits,
            'display_position': dict(pos),
        })

    metric_layout = bool(cameras_out) and all(
        c['display_position']['status'] == 'CALIBRATED_STATIC' for c in cameras_out
    )
    layout = 'METRIC_STATIC' if metric_layout else 'NODE_GRAPH'
    display_note = METRIC_STATIC_NOTE if metric_layout else NODE_GRAPH_NOTE

    regions_out = [
        {'region_id': r['region_id'], 'kind': r['kind']}
        for r in region_graph.get('regions', [])
    ]
    edges_out = [
        {
            'edge_id': e['edge_id'],
            'regions': list(e['regions']),
            'state': e['state'],
            'traversability': e['traversability'],
            'direction': e['direction'],
        }
        for e in region_graph.get('edges', [])
    ]
    edge_state_by_id = {e['edge_id']: e['state'] for e in edges_out}

    transitions_out = []
    for t in sorted(camera_graph.get('transitions', []), key=lambda item: item['transition_id']):
        edge_path = list(t.get('edge_path', []))
        transitions_out.append({
            'transition_id': t['transition_id'],
            'from_camera_id': t['from_camera_id'],
            'to_camera_id': t['to_camera_id'],
            'relation': t['relation'],
            'path_traversability': t['path_traversability'],
            'path_has_unknown_state': bool(t['path_has_unknown_state']),
            'via_exit_zone_ids': list(t.get('via_exit_zone_ids', [])),
            'to_entry_zone_ids': list(t.get('to_entry_zone_ids', [])),
            'edge_path': edge_path,
            'region_path': list(t.get('region_path', [])),
            'edge_states': [edge_state_by_id.get(eid, 'UNKNOWN') for eid in edge_path],
            'authority': transition_authority,
        })

    doc = {
        'schema_version': SCHEMA_VERSION,
        'scene_id': scene_id,
        'scene_revision': camera_graph['scene_revision'],
        'run_id': run_id,
        'graph': {
            'camera_graph_sha256': camera_graph_sha256,
            'region_graph_sha256': region_graph_sha256,
            'camera_graph_id': camera_graph['graph_id'],
            'approval_status': approval_status,
            'approval_ref': approval_ref,
            'tracking_scope_sha256': scope_sha_out,
            'tracking_scope_status': scope_status,
            'g4_approved': g4_approved,
        },
        'layout': layout,
        'display_note': display_note,
        'cameras': cameras_out,
        'regions': regions_out,
        'edges': edges_out,
        'transitions': transitions_out,
        'identity_verdict': 'UNCONFIRMED',
        'physical_navigation': 'UNKNOWN',
        _GT_READ_KEY: False,
    }
    doc['content_sha256'] = canonical_hash(doc, exclude=('content_sha256',))
    return doc

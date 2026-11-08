"""PROPOSED scene-selected search metadata; r005 is not a runtime GraphBundle.

Only allowlisted small JSON is read. Pending coverage never grants a location hit.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path

from amidst.q1q5.graphs import (
    GraphError, _digest, _document, _fields, _require, _safe, _text, _unique, _zones, load_graphs,
)
from amidst.q1q5.store import _json

ROOT = Path(__file__).resolve().parents[3] / 'configs/q1q5/graphs'
R005 = 'office_expanded_r005'
R004 = 'controlled_scene_v1_s001'
R005_MANIFEST_SHA256 = '01fe6b8a55d04cfafc1178aee1facc4340c7370703b9bb3fe942dcc72cf7ec7e'
R004_PINS = {
    'region_graph_v3_1.json': 'a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1',
    'camera_graph_v3_1.json': 'e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409',
    'tracking_scope_v3_1.json': 'ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a',
}


@dataclass(frozen=True)
class SceneGraphs:
    """Search configuration copies, without a runtime candidate/authority grant."""
    _region: dict
    _camera: dict

    @property
    def region(self):
        return deepcopy(self._region)

    @property
    def camera(self):
        return deepcopy(self._camera)


def _read(directory, name, expected):
    path = directory / name
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise GraphError('Symlink graph input', 'GRAPH_SOURCE_UNSAFE')
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise GraphError('Required graph evidence missing', 'GRAPH_EVIDENCE_MISSING') from exc
    if hashlib.sha256(raw).hexdigest() != expected:
        raise GraphError('Graph byte pin mismatch', 'GRAPH_PIN_MISMATCH')
    try:
        return _json(raw), raw
    except ValueError as exc:
        raise GraphError('Malformed graph JSON', 'GRAPH_JSON_INVALID') from exc


def _pending_graphs(region, camera, pins):
    """Validate the distinct pending schema directly; never re-seal or adapt it."""
    _document(region, 'office-search.region-skeleton.v1', 'rgraph', pins['region_content_sha256'])
    _document(camera, 'office-search.camera-skeleton.v1', 'cgraph', pins['camera_content_sha256'])
    for graph in (region, camera):
        _require(graph['scene_id'] == R005 and graph['scene_revision'] == 'r005'
                 and graph['approval_status'] == 'DRAFT' and graph['approval_ref'] is None,
                 'Pending skeleton cannot grant approval')
        _require(not any(x['ref'].startswith('static-review:') for x in graph['inputs']),
                 'Pending skeleton cannot claim coverage review')
    _require(camera['region_graph_sha256'] == region['content_sha256']
             and camera['inputs'] == region['inputs']
             and _digest(region['scene_static_sha256'])
             and _digest(camera['camera_catalog_sha256']), 'Cross graph/source pin')
    regions = _unique(region['regions'], 'region_id')
    edges = _unique(region['edges'], 'edge_id')
    cameras = _unique(camera['cameras'], 'camera_id')
    _require(bool(regions) and bool(cameras), 'Empty skeleton')
    for node in regions.values():
        _fields(node, ('region_id', 'kind', 'floor_id', 'walk_ids', 'polygon_ref', 'polygon_sha256'))
        _require(node['kind'] in {'ROOM', 'CORRIDOR_SEGMENT'} and _text(node['floor_id'])
                 and isinstance(node['walk_ids'], list) and all(_text(x) for x in node['walk_ids'])
                 and _text(node['polygon_ref']) and _digest(node['polygon_sha256']), 'Invalid region provenance')
    for edge in edges.values():
        _fields(edge, ('edge_id', 'regions', 'via', 'direction', 'state', 'traversability', 'basis_refs'))
        _fields(edge['via'], ('kind', 'ref'))
        _require(edge['via']['kind'] in {'PORTAL', 'ADJACENT'} and _text(edge['via']['ref']), 'Invalid edge basis')
        _require(len(edge['regions']) == 2 and len(set(edge['regions'])) == 2
                 and set(edge['regions']) <= regions.keys() and edge['state'] == 'UNKNOWN'
                 and edge['traversability'] == 'TOPOLOGICAL_ONLY'
                 and edge['direction'] == 'BIDIRECTIONAL' and bool(edge['basis_refs']), 'Invalid pending edge')
    zones = {}
    for row in cameras.values():
        _fields(row, ('camera_id', 'calibration_sha256', 'covered_regions', 'exit_zones', 'entry_zones'))
        _require(_digest(row['calibration_sha256']), 'Missing calibration pin')
        _require(isinstance(row['covered_regions'], list) and bool(row['covered_regions']), 'Pending coverage required')
        seen = set()
        for cover in row['covered_regions']:
            _fields(cover, ('region_id', 'basis', 'visibility_ref', 'visible_area_m2'))
            _require(cover['region_id'] in regions and cover['region_id'] not in seen
                     and cover['basis'] == 'NOT_EVALUATED' and cover['visibility_ref'] is None
                     and cover['visible_area_m2'] is None, 'Invalid pending coverage')
            seen.add(cover['region_id'])
        _require(bool(row['exit_zones']), 'Exit required')
        zones[row['camera_id']] = (
            _zones(row['exit_zones'], 'exit_zone_id', exits=True, edges=edges),
            _zones(row['entry_zones'], 'entry_zone_id', exits=False, edges=edges),
        )
    for t in _unique(camera['transitions'], 'transition_id').values():
        _fields(t, ('transition_id', 'from_camera_id', 'to_camera_id', 'via_exit_zone_ids',
                    'to_entry_zone_ids', 'region_path', 'edge_path', 'relation', 'region_hops',
                    'path_traversability', 'path_has_unknown_state', 'ranking_area_m2',
                    'ranking_area_refs', 'nominal_path_length_m', 'basis_refs'))
        a, b = t['from_camera_id'], t['to_camera_id']
        _require(a in cameras and b in cameras and a != b, 'Invalid transition cameras')
        _require(bool(t['via_exit_zone_ids']) and set(t['via_exit_zone_ids']) <= zones[a][0].keys()
                 and bool(t['to_entry_zone_ids']) and set(t['to_entry_zone_ids']) <= zones[b][1].keys(),
                 'Invalid transition zones')
        path, eids = t['region_path'], t['edge_path']
        _require(len(path) >= 2 and len(eids) == len(path) - 1
                 and set(path) <= regions.keys() and type(t['region_hops']) is int and t['region_hops'] == len(eids)
                 and path[0] in {x['region_id'] for x in cameras[a]['covered_regions']}
                 and path[-1] in {x['region_id'] for x in cameras[b]['covered_regions']}
                 and bool(t['basis_refs']), 'Invalid transition path')
        for left, right, eid in zip(path, path[1:], eids):
            _require(eid in edges and set(edges[eid]['regions']) == {left, right}, 'Invalid path edge')
        _require(eids[0] in {eid for zid in t['via_exit_zone_ids'] for eid in zones[a][0][zid]['leads_to_edge_ids']},
                 'Path does not follow exit')
        _require(t['relation'] == 'UNKNOWN' and t['path_traversability'] == 'TOPOLOGICAL_ONLY'
                 and t['path_has_unknown_state'] is True and t['ranking_area_m2'] is None
                 and t['ranking_area_refs'] == [] and t['nominal_path_length_m'] is None,
                 'Pending transition cannot grant ranking or physical authority')
    return SceneGraphs(deepcopy(region), deepcopy(camera))


def load_scene_graphs(scene_id, *, graph_root=None, run_scene_id=None):
    """Select the pinned r004/v3_1 or r005 search skeleton by scene ID.

    graph_root is a repository graph directory for isolated verification. Trusted
    byte pins remain fixed in this module, including when a root is supplied.
    run_scene_id, when supplied, must be the canonical scene ID (not an alias).
    """
    selected = {'r004': R004, R004: R004, 'r005': R005, R005: R005}.get(scene_id)
    if selected is None:
        raise GraphError('Unsupported scene', 'SCENE_UNKNOWN')
    if run_scene_id is not None and run_scene_id != selected:
        raise GraphError('Run scene mismatch', 'SCENE_RUN_MISMATCH')
    root = Path(graph_root) if graph_root is not None else ROOT
    if selected == R004:
        docs = {name: _read(root / 'r004', name, pin) for name, pin in R004_PINS.items()}
        r, c, scope = [docs[name][0] for name in R004_PINS]
        checked = load_graphs(r, c, region_sha256=r['content_sha256'], camera_sha256=c['content_sha256'],
                              tracking_scope=scope, tracking_scope_bytes=docs['tracking_scope_v3_1.json'][1],
                              tracking_scope_sha256=R004_PINS['tracking_scope_v3_1.json'])
        return SceneGraphs(checked.region, checked.camera)
    directory = root / R005 / 'search_skeleton'
    pins, _ = _read(directory, 'source_pins.json', R005_MANIFEST_SHA256)
    try:
        _safe(pins)
        r, c = [_read(directory, name, pins['files'][name])[0]
                for name in ('region_graph.json', 'camera_graph.json')]
        return _pending_graphs(r, c, pins)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise GraphError('Malformed skeleton', 'GRAPH_SKELETON_INVALID') from exc


def location_coverage(graphs, region_ids, *, run_camera_ids):
    """#410 location_hits shape; pending basis is explicitly unevaluated.

    This helper does not perform object search, clocks, HTTP or identity linking.
    """
    regions = {r['region_id'] for r in graphs.region['regions']}
    if not set(region_ids) <= regions:
        raise GraphError('Unknown region', 'REGION_UNKNOWN')
    hits, pending = {}, []
    for camera in sorted(graphs.camera['cameras'], key=lambda row: row['camera_id']):
        covers = [row for row in camera['covered_regions'] if row['region_id'] in region_ids]
        if not covers:
            continue
        cid = camera['camera_id']
        if cid not in run_camera_ids:
            pending.append({'camera_id': cid, 'reason': 'CAMERA_NOT_IN_RUN'})
            continue
        manual = [row for row in covers if row['basis'] == 'MANUAL_ON_STATIC_FRAME']
        if manual:
            hits[cid] = [{'kind': 'LOCATION', 'region_id': row['region_id'],
                          'coverage_basis': row['basis'], 'visibility_ref': row['visibility_ref']} for row in manual]
        else:
            pending.append({'camera_id': cid, 'reason': 'COVERAGE_BASIS_UNSUPPORTED'})
    return {'hits': hits, 'not_evaluated': pending}


def room_coverage_pending(graphs):
    rooms = {r['region_id'] for r in graphs.region['regions'] if r['kind'] == 'ROOM'}
    covered = {r['region_id'] for c in graphs.camera['cameras'] for r in c['covered_regions']
               if r['basis'] == 'MANUAL_ON_STATIC_FRAME'}
    return 'SCENE_ROOM_COVERAGE_PENDING' if rooms - covered else None

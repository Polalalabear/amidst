"""Pinned static graph validation. Loading never grants physical authority.

D71 requires an exit on every camera. No media, event script or model imports.
"""
import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass

from amidst.q1q5.store import canonical_hash


class GraphError(ValueError):
    def __init__(self, message, code="DataIntegrityError"):
        self.code = code
        super().__init__(message)


def _require(condition, message):
    if not condition:
        raise GraphError(message)


def _fields(doc, required, optional=()):
    _require(isinstance(doc, dict) and set(required) <= doc.keys()
             and doc.keys() <= set(required) | set(optional), "Unknown or missing graph field")


def _text(value):
    return isinstance(value, str) and bool(value) and not value.startswith(("/", "file:"))


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _safe(value):
    if isinstance(value, dict):
        forbidden = {"gt", "ground_truth", "actor_id", "material_id", "event_script",
                     "persons.sim.json", "renderer_trajectory", "depth", "mask", "detections",
                     "detection_index", "event_route", "visibility", "renderer_visibility"}
        _require(not forbidden.intersection(k.lower() for k in value), "Forbidden graph input")
        for child in value.values():
            _safe(child)
    elif isinstance(value, list):
        for child in value:
            _safe(child)
    elif isinstance(value, str):
        _require(not value.startswith(("/Users/", "/private/", "/tmp/", "file:")),
                 "Local paths forbidden")


def _unique(items, key):
    _require(isinstance(items, list), "Expected graph array")
    result = {}
    for item in items:
        _require(isinstance(item, dict) and _text(item.get(key)), "Missing graph ID")
        _require(item[key] not in result, "Duplicate graph ID")
        result[item[key]] = item
    return result


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _zones(items, key, *, exits, edges):
    zones = _unique(items, key)
    for z in zones.values():
        if exits:
            _fields(z, (key, 'roi_polygon_px', 'leads_to_edge_ids', 'mapping_basis'),
                    ('static_frame_ref', 'static_frame_sha256'))
        else:
            _fields(z, (key, 'roi_polygon_px'))
        poly = z.get("roi_polygon_px")
        _require(isinstance(poly, list) and len(poly) >= 3 and all(
            isinstance(v, list) and len(v) == 2 and all(_number(x) for x in v) for v in poly),
            "Invalid ROI polygon")
        area2 = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(poly, poly[1:]+poly[:1], strict=True))
        _require(abs(area2) > 0 and len({tuple(v) for v in poly}) >= 3, "Degenerate ROI")
        if exits:
            _require(z.get("mapping_basis") in {"MANUAL_ON_STATIC_FRAME", "STATIC_CALIBRATION_PROJECTION"},
                     "Invalid exit mapping basis")
            _require(_text(z.get("static_frame_ref")) and _digest(z.get("static_frame_sha256")),
                     "Missing static ROI provenance")
            _require(isinstance(z.get("leads_to_edge_ids"), list) and z["leads_to_edge_ids"]
                     and set(z["leads_to_edge_ids"]) <= edges.keys(), "Invalid exit edge ref")
    return zones


def _document(doc, schema, prefix, expected):
    _require(isinstance(doc, dict), "Graph object required")
    _safe(doc)
    common = ('schema_version', 'graph_id', 'scene_id', 'scene_revision',
              'approval_status', 'approval_ref', 'inputs', 'content_sha256')
    extra = ('scene_static_sha256', 'regions', 'edges') if prefix == 'rgraph' else (
        'region_graph_sha256', 'camera_catalog_sha256', 'cameras', 'transitions')
    _fields(doc, common + extra, ('stats',))
    _require(doc.get("schema_version") == schema and _digest(expected), "Graph schema/pin required")
    try:
        digest = canonical_hash(doc, exclude=("graph_id", "content_sha256", "stats"))
    except (ValueError, TypeError) as exc:
        raise GraphError('Invalid canonical graph value') from exc
    _require(digest == expected == doc.get("content_sha256"), "Graph content pin mismatch")
    _require(_text(doc.get("scene_id")) and _text(doc.get("scene_revision")), "Scene required")
    _require(doc.get("graph_id") == f"{prefix}:{doc['scene_revision']}:static:{digest[:16]}",
             "Graph derived ID mismatch")
    _require(doc.get("approval_status") in {"APPROVED", "DRAFT"}, "Invalid approval status")
    if doc["approval_status"] == "APPROVED":
        _require(_text(doc.get("approval_ref")), "Approved graph needs approval ref")
    else:
        _require(doc.get("approval_ref") is None, "Draft cannot claim approval")
    _require(isinstance(doc.get("inputs"), list) and doc["inputs"], "Static inputs required")
    for item in doc["inputs"]:
        _fields(item, ('ref', 'sha256'))
        _require(_text(item.get("ref")) and _digest(item.get("sha256")), "Invalid input pin")


@dataclass(frozen=True)
class GraphBundle:
    """Private copies; callers receive copies so a checked graph cannot be mutated."""
    _region: dict
    _camera: dict
    _tracking_scope: dict | None = None
    _tracking_scope_sha256: str | None = None

    @property
    def region(self):
        return deepcopy(self._region)

    @property
    def camera(self):
        return deepcopy(self._camera)

    @property
    def tracking_scope(self):
        return deepcopy(self._tracking_scope)

    @property
    def tracking_scope_sha256(self):
        return self._tracking_scope_sha256

    @property
    def approval_status(self):
        return "APPROVED" if all(d["approval_status"] == "APPROVED"
                                 for d in (self._region, self._camera)) else "DRAFT"


def load_graphs(region_graph, camera_graph, *, region_sha256, camera_sha256,
                tracking_scope=None, tracking_scope_sha256=None):
    """Validate already allowlisted metadata, fail closed before generating candidates.

    Expected content pins must come from trusted configuration. This checks declared
    approval references, not the truth or scope of the human approval itself.
    """
    r, c = deepcopy(region_graph), deepcopy(camera_graph)
    try:
        _document(r, "q-demo.region-graph.v1", "rgraph", region_sha256)
        _document(c, "q-demo.camera-transition-graph.v1", "cgraph", camera_sha256)
        _require(c.get("region_graph_sha256") == region_sha256, "Cross-graph hash mismatch")
        _require(_digest(r.get("scene_static_sha256")) and _digest(c.get("camera_catalog_sha256")),
                 "Missing static/catalog pin")
        _require(all(r[k] == c[k] for k in ("scene_id", "scene_revision")), "Cross-scene graph")
        regions = _unique(r["regions"], "region_id")
        edges = _unique(r["edges"], "edge_id")
        for node in regions.values():
            _fields(node, ('region_id', 'kind', 'floor_id', 'walk_ids', 'polygon_ref', 'polygon_sha256'))
            _require(node["kind"] in {"OUTDOOR", "ENTRANCE", "CORRIDOR_SEGMENT", "CORNER", "ROOM", "STAIR_LANDING"}, "Invalid region kind")
            _require(_text(node["floor_id"]) and isinstance(node["walk_ids"], list)
                     and all(_text(x) for x in node["walk_ids"])
                     and _text(node["polygon_ref"]) and _digest(node["polygon_sha256"]),
                     "Missing region provenance")
        for edge in edges.values():
            _fields(edge, ('edge_id', 'regions', 'via', 'direction', 'state', 'traversability',
                           'basis_refs'), ('from', 'to'))
            _fields(edge['via'], ('kind', 'ref'))
            pair = edge["regions"]
            _require(isinstance(pair, list) and len(pair) == 2 and len(set(pair)) == 2
                     and set(pair) <= regions.keys(), "Invalid edge regions")
            _require(edge["state"] in {"OPEN", "CLOSED", "UNKNOWN"}
                     and edge["traversability"] in {"APPROVED_WALKABLE", "TOPOLOGICAL_ONLY"},
                     "Invalid edge state/authority")
            _require(edge["direction"] in {"BIDIRECTIONAL", "ONE_WAY"}, "Invalid direction")
            if edge["direction"] == "ONE_WAY":
                _require(edge["from"] in pair and edge["to"] in pair and edge["from"] != edge["to"],
                         "Invalid directed edge")
            _require(edge["via"]["kind"] in {"ADJACENT", "PORTAL", "STAIR"}
                     and _text(edge["via"]["ref"]) and bool(edge["basis_refs"]), "Missing edge basis")
        cameras = _unique(c["cameras"], "camera_id")
        zone_maps = {}
        for camera in cameras.values():
            _fields(camera, ('camera_id', 'calibration_sha256', 'covered_regions', 'exit_zones', 'entry_zones'))
            _require(_digest(camera["calibration_sha256"]), "Camera calibration pin required")
            if not camera.get("exit_zones"):
                raise GraphError("Every camera requires exit_zones", "EXIT_ZONES_MISSING")
            ex = _zones(camera["exit_zones"], "exit_zone_id", exits=True, edges=edges)
            en = _zones(camera["entry_zones"], "entry_zone_id", exits=False, edges=edges)
            zone_maps[camera["camera_id"]] = (ex, en)
            for cover in camera["covered_regions"]:
                _fields(cover, ('region_id', 'basis', 'visibility_ref', 'visible_area_m2'))
                _require(cover["region_id"] in regions and cover["basis"] in
                         {"STATIC_VISIBILITY_INDEX", "MANUAL_ON_STATIC_FRAME"}
                         and _text(cover["visibility_ref"]), "Invalid camera region reference")
                _require(cover["visible_area_m2"] is None or _number(cover["visible_area_m2"]),
                         "Invalid visible area")
        transitions = _unique(c["transitions"], "transition_id")
        for t in transitions.values():
            _fields(t, ('transition_id', 'from_camera_id', 'to_camera_id', 'via_exit_zone_ids',
                        'to_entry_zone_ids', 'region_path', 'edge_path', 'relation', 'region_hops',
                        'path_traversability', 'path_has_unknown_state', 'ranking_area_m2',
                        'ranking_area_refs', 'nominal_path_length_m', 'basis_refs'))
            a, b = t["from_camera_id"], t["to_camera_id"]
            _require(a in cameras and b in cameras and a != b, "Invalid transition camera")
            _require(isinstance(t["via_exit_zone_ids"], list) and t["via_exit_zone_ids"]
                     and set(t["via_exit_zone_ids"]) <= zone_maps[a][0].keys(), "Invalid exit ref")
            _require(set(t["to_entry_zone_ids"]) <= zone_maps[b][1].keys(), "Invalid entry ref")
            path, eids = t["region_path"], t["edge_path"]
            _require(len(path) >= 1 and len(eids) == len(path)-1 and set(path) <= regions.keys(),
                     "Invalid region path")
            _require(type(t["region_hops"]) is int and t["region_hops"] == len(eids), "Invalid hops")
            walks = []
            for left, right, eid in zip(path, path[1:], eids, strict=False):
                _require(eid in edges, "Missing path edge")
                edge = edges[eid];walks.append(edge)
                _require(set(edge["regions"]) == {left, right} and edge["state"] != "CLOSED",
                         "Noncontiguous or closed path")
                if edge["direction"] == "ONE_WAY":
                    _require((left, right) == (edge["from"], edge["to"]), "Wrong directed path")
            if t['relation'] != 'UNKNOWN':
                _require(path[0] in {v['region_id'] for v in cameras[a]['covered_regions']}
                         and path[-1] in {v['region_id'] for v in cameras[b]['covered_regions']},
                         "Path endpoints outside covered regions")
            if eids:
                _require(eids[0] in {eid for zid in t['via_exit_zone_ids']
                                    for eid in zone_maps[a][0][zid]['leads_to_edge_ids']},
                         "Path does not follow declared exit")
            weakest = "TOPOLOGICAL_ONLY" if any(e["traversability"] == "TOPOLOGICAL_ONLY" for e in walks) else "APPROVED_WALKABLE"
            unknown = any(e["state"] == "UNKNOWN" for e in walks)
            _require(t["path_traversability"] == weakest and type(t["path_has_unknown_state"]) is bool
                     and t["path_has_unknown_state"] == unknown, "Path authority/state mismatch")
            _require(t["relation"] in {"UNKNOWN", "OVERLAP", "BLIND_GAP"}, "Invalid relation")
            area = t["ranking_area_m2"]
            _require(area is None or (_number(area) and bool(t["ranking_area_refs"])), "Invalid ranking area basis")
            _require(t["nominal_path_length_m"] is None or _number(t["nominal_path_length_m"]), "Invalid path length")
            _require(bool(t["basis_refs"]), "Transition basis required")
        scope = _tracking_scope(r, c, tracking_scope, tracking_scope_sha256)
        return GraphBundle(r, c, scope, tracking_scope_sha256)
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError) as exc:
        raise GraphError("Malformed static graph") from exc


def _tracking_scope(region, camera, supplied, expected):
    pins = [[item for item in graph['inputs'] if item['ref'].startswith('tracking-scope:')]
            for graph in (region, camera)]
    if supplied is None:
        if any(pins):
            raise GraphError('Declared tracking scope is unavailable', 'TRACKING_SCOPE_MISSING')
        _require(expected is None, 'Scope hash without a scope document')
        return None
    _require(all(len(values) == 1 for values in pins) and pins[0] == pins[1],
             'Tracking scope must have one identical pin in both graphs')
    scope = deepcopy(supplied)
    _safe(scope)
    _fields(scope, ('schema_version', 'status', 'G4_approved', 'query_camera_ids',
                    'tracking_camera_ids', 'query_only_camera_ids', 'directed_pairs',
                    'north_floor_y_gt_12', 'overlap_pairs_deferred'))
    _require(scope['schema_version'] == 'q-demo.r004-tracking-scope.v3'
             and scope['status'] in {'PROPOSED', 'FROZEN', 'APPROVED'}
             and type(scope['G4_approved']) is bool, 'Invalid tracking scope schema/status')
    # The v3 producer pins canonical JSON followed by one LF, not a content_sha256.
    raw = json.dumps(scope, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                     allow_nan=False).encode() + b'\n'
    _require(_digest(expected) and hashlib.sha256(raw).hexdigest() == expected
             and pins[0][0]['sha256'] == expected, 'Tracking scope byte pin mismatch')
    if any(graph['approval_status'] == 'APPROVED' for graph in (region, camera)):
        _require(scope['G4_approved'] is True and scope['status'] in {'FROZEN', 'APPROVED'},
                 'Approved graph requires a frozen scope with G4 approval')
    sets = []
    for name in ('query_camera_ids', 'tracking_camera_ids', 'query_only_camera_ids'):
        values = scope[name]
        _require(isinstance(values, list) and all(_text(x) for x in values)
                 and len(values) == len(set(values)), 'Invalid tracking camera IDs')
        sets.append(set(values))
    query, tracking, query_only = sets
    _require(bool(tracking) and tracking == {x['camera_id'] for x in camera['cameras']}
             and not tracking.intersection(query_only) and query == tracking | query_only,
             'Tracking/query camera partition mismatch')
    transitions = {x['transition_id']: x for x in camera['transitions']}
    seen, referenced = set(), set()
    _require(isinstance(scope['directed_pairs'], list), 'Directed scope pairs required')
    for row in scope['directed_pairs']:
        _fields(row, ('from_camera_id', 'to_camera_id', 'disposition'),
                ('reason', 'transition_id'))
        pair = row['from_camera_id'], row['to_camera_id']
        _require(pair[0] in query and pair[1] in query and pair[0] != pair[1]
                 and pair not in seen, 'Invalid/duplicate directed scope pair')
        seen.add(pair)
        if row['disposition'] == 'TRANSITION':
            tid = row.get('transition_id')
            _require(tid in transitions and pair == (transitions[tid]['from_camera_id'],
                      transitions[tid]['to_camera_id']) and tid not in referenced
                     and 'reason' not in row, 'Scope transition reference mismatch')
            referenced.add(tid)
        else:
            _require(row['disposition'] == 'EXCLUDED' and _text(row.get('reason'))
                     and 'transition_id' not in row, 'Excluded scope pair needs reason')
    _require(seen == {(a, b) for a in query for b in query if a != b}
             and referenced == set(transitions), 'Incomplete directed scope matrix')
    return scope


def load_pinned_graphs(store, region_ref, camera_ref, *, tracking_scope=None,
                       tracking_scope_sha256=None):
    r, c = store.load_document(region_ref), store.load_document(camera_ref)
    return load_graphs(r, c, region_sha256=r["content_sha256"], camera_sha256=c["content_sha256"],
                       tracking_scope=tracking_scope, tracking_scope_sha256=tracking_scope_sha256)

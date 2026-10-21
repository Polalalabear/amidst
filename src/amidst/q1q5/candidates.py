"""D28 candidates from validated static graphs; no detector or LLM inputs."""
from copy import deepcopy
import math

from amidst.q1q5.graphs import GraphBundle, GraphError, _require
from amidst.q1q5.store import canonical_hash


def _inside(point, poly, inclusive):
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:]+poly[:1]):
        cross = (x-ax)*(by-ay)-(y-ay)*(bx-ax)
        if cross == 0 and min(ax,bx) <= x <= max(ax,bx) and min(ay,by) <= y <= max(ay,by):
            return inclusive
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside


def transition_candidates(graphs: GraphBundle, *, from_camera_id, last_bbox_xyxy_px,
                          session_id, top_k, window_us, exit_boundary_inclusive, allowed_camera_ids=None):
    """Caller supplies approved exit rule/parameters and source-bound time window.

    Multiple routes to one camera use the best D28 key; exact-key ties retain the
    canonical transition-ID order solely for reproducible representation, not rank.
    An explicit run camera scope is applied before ranking and top-k. None retains
    the original all-graph API; runtime callers must pass their pinned run scope.
    """
    _require(isinstance(graphs, GraphBundle), "Validated GraphBundle required")
    _require(type(top_k) is int and top_k > 0, "Explicit positive top_k required")
    _require(type(exit_boundary_inclusive) is bool, "Explicit ROI boundary policy required")
    _require(isinstance(session_id, str) and bool(session_id), "Session required")
    _require(isinstance(window_us, (list,tuple)) and len(window_us) == 2
             and all(type(v) is int and v >= 0 for v in window_us) and window_us[0] < window_us[1],
             "Explicit nonempty integer source window required")
    _require(isinstance(last_bbox_xyxy_px, (list,tuple)) and len(last_bbox_xyxy_px) == 4
             and all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in last_bbox_xyxy_px),
             "Invalid last observed bbox")
    x0,y0,x1,y1 = last_bbox_xyxy_px
    _require(x0 < x1 and y0 < y1, "Empty last observed bbox")
    camera_graph = graphs.camera
    cameras = {c['camera_id']: c for c in camera_graph['cameras']}
    _require(from_camera_id in cameras, "Origin not in camera graph")
    if allowed_camera_ids is None:
        allowed = set(cameras)
    else:
        _require(isinstance(allowed_camera_ids, (list, tuple, set, frozenset))
                 and bool(allowed_camera_ids)
                 and all(isinstance(v, str) and v for v in allowed_camera_ids),
                 'Explicit nonempty run camera scope required')
        allowed = set(allowed_camera_ids)
        _require(len(allowed) == len(allowed_camera_ids) and allowed <= cameras.keys()
                 and from_camera_id in allowed, 'Run camera scope outside graph/origin')
    zones = cameras[from_camera_id]['exit_zones']
    if not zones:
        raise GraphError("Every camera requires exit_zones", "EXIT_ZONES_MISSING")
    hit = [z['exit_zone_id'] for z in zones if _inside(((x0+x1)/2,y1),z['roi_polygon_px'],exit_boundary_inclusive)]
    resolution = 'UNIQUE' if len(hit) == 1 else 'AMBIGUOUS'
    selected = set(hit if len(hit) == 1 else [z['exit_zone_id'] for z in zones])
    def rank(t):
        tier = 4 if t['relation'] == 'UNKNOWN' else (3 if t['path_has_unknown_state'] else (1 if t['relation'] == 'OVERLAP' else 2))
        area = t['ranking_area_m2']
        return (tier, area is None, 0 if area is None else -area, t['to_camera_id'])
    groups, excluded = {}, []
    for t in sorted(camera_graph['transitions'],key=lambda t:t['transition_id']):
        if (t['from_camera_id'] != from_camera_id or t['to_camera_id'] not in allowed
                or not selected.intersection(t['via_exit_zone_ids'])):
            continue
        if t['path_traversability'] == 'TOPOLOGICAL_ONLY':
            excluded.append({'transition_id':t['transition_id'],'reason':'TOPOLOGICAL_ONLY_EDGE'})
            continue
        groups.setdefault(t['to_camera_id'],[]).append(t)
    unique=[]
    for values in groups.values():
        values.sort(key=rank);t=values[0];tier=rank(t)[0]
        unique.append({'camera_id':t['to_camera_id'],'relation':t['relation'],
                       'transition_id':t['transition_id'],'region_path':deepcopy(t['region_path']),
                       'window_us':list(window_us),'path_traversability':t['path_traversability'],
                       'path_has_unknown_state':t['path_has_unknown_state'],
                       'ranking_basis':{'relation_tier':tier,'overlap_area_m2':t['ranking_area_m2'],
                                        'camera_id':t['to_camera_id']},
                       'alternative_transition_ids':sorted(v['transition_id'] for v in values[1:])})
    unique.sort(key=lambda c:(c['ranking_basis']['relation_tier'],
                             c['ranking_basis']['overlap_area_m2'] is None,
                             -(c['ranking_basis']['overlap_area_m2'] or 0),c['camera_id']))
    n=max(0,len(unique)-top_k);candidates=unique[:top_k]
    for i,c in enumerate(candidates,1):c['rank']=i
    snapshot={'schema_version':'q-demo.candidate-snapshot.v1','session_id':session_id,
              'exit_resolution':resolution,'candidates':candidates,'excluded_transitions':excluded,
              'candidate_set_complete':n == 0,'truncated':n > 0,'truncated_count':n}
    digest=canonical_hash(snapshot)
    snapshot['candidate_snapshot_sha256']=digest
    for c in candidates:c['candidate_ref']=f"cand:{digest[:16]}:{c['rank']}"
    return snapshot

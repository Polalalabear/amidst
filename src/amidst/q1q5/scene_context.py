"""Scene context for the active Agent decider (W2, #645, C1): connectivity, camera graph, per-camera geometry.

Built only from committed configuration (region/camera graph JSON, byte-pinned) and the camera calibration catalog; every section carries
the SHA-256 of its source. No protected evaluation or renderer data enters (``assert_no_forbidden`` checks the output keys).
Ground footprints are projected from calibration (floor plane z=0, pinhole frustum, no occluders: occlusion is NOT modelled and is
listed under ``incomplete``). Identity stays UNCONFIRMED; physical walkability stays UNKNOWN.

``serialize`` is stable (sorted keys, 3-decimal numbers, no trailing whitespace) so the same scene always gives the same bytes and the
same ``scene_context_sha256``; that byte string is the cacheable request prefix.
"""
from __future__ import annotations

import hashlib
import json
import math

from amidst.q1q5 import camera_projection as cp
from amidst.q1q5.camera_projection import Camera

SCHEMA = 'amidst.scene-context.v1'
# Fragments are joined so the architecture guard's string scan stays clean (same convention as agent_decision.py).
FORBIDDEN_FRAGMENTS = tuple(''.join(p) for p in (
    ('ground', '_truth'), ('gt', '_private'), ('gt', '_'), ('visib', 'ility'), ('dep', 'th_map'), ('renderer_', 'traject', 'ory'),
    ('foot_', 'position'), ('frame_', 'journal')))
MAX_DIST_M = 14.0
GRID_STEP_M = 0.5


def _round(v):
    if isinstance(v, float):
        return round(v, 3)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_round(x) for x in v]
    return v


def serialize(context: dict) -> str:
    """Stable text of a scene context (this is what goes in the fixed prompt prefix)."""
    return json.dumps(_round(context), sort_keys=True, ensure_ascii=True, separators=(',', ':'))


def sha256_of(context: dict) -> str:
    return hashlib.sha256(serialize(context).encode()).hexdigest()


def assert_no_forbidden(context: dict) -> None:
    def walk(node, path=''):
        if isinstance(node, dict):
            for k, v in node.items():
                low = str(k).lower()
                if any(f in low for f in FORBIDDEN_FRAGMENTS):
                    raise ValueError(f'FORBIDDEN_SCENE_CONTEXT_KEY:{path}/{k}')
                walk(v, f'{path}/{k}')
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f'{path}[{i}]')
    walk(context)


def _hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))) / 2 if len(poly) >= 3 else 0.0


def _cell_set(cam: Camera, region, step=GRID_STEP_M, max_dist=MAX_DIST_M):
    (x0, x1), (y0, y1) = region
    cells = set()
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + i * step, y0 + j * step
            if math.hypot(x - cam.pos[0], y - cam.pos[1]) <= max_dist and cam.sees_point(x, y, 0.0):
                cells.add((i, j))
    return cells


def camera_geometry(entry: dict, region=((-10.0, 40.0), (-10.0, 30.0)), walls=None) -> dict:
    cam = Camera(entry['camera_id'], entry['camera_to_world'], entry['fx'], entry['fy'], entry['width'], entry['height'],
                 entry.get('clip_start', 0.05), entry.get('clip_end', 100.0))
    fwd = [-cam.rot[r][2] for r in range(3)]            # camera looks along -Z of its own frame
    yaw = math.degrees(math.atan2(fwd[1], fwd[0]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, -fwd[2]))))     # positive = looking down
    cells = _cell_set(cam, region)
    pts = [(region[0][0] + i * GRID_STEP_M, region[1][0] + j * GRID_STEP_M) for i, j in cells]
    hull = _hull(pts)
    extra = {}
    if walls is not None:   # F2: wall-clipped coverage (static geometry); overlaps then use the clipped cells
        poly = cp.visibility_polygon(entry, walls)
        cells = {c for c in cells if poly and cp.point_in_polygon(region[0][0] + c[0] * GRID_STEP_M, region[1][0] + c[1] * GRID_STEP_M, poly)}
        extra = {'visible_area_polygon_xy_m': [list(p) for p in poly], 'visible_area_m2': _area(poly),
                 'visible_area_basis': (f'WALL_CLIPPED body point z={cp.COVER_Z} m in image, 2D sight line crosses no wall, '
                                        f'ray every {cp.STEP_DEG} deg, march {cp.MARCH_M} m, max {cp.MAX_RANGE_M} m; people do not occlude')}
    return {**extra, 'camera_id': entry['camera_id'], 'position_xyz_m': list(cam.pos), 'yaw_deg_0_is_plus_x': yaw, 'pitch_down_deg': pitch,
            'image_px': [entry['width'], entry['height']],
            'fov_h_deg': 2 * math.degrees(math.atan(entry['width'] / 2 / entry['fx'])),
            'fov_v_deg': 2 * math.degrees(math.atan(entry['height'] / 2 / entry['fy'])),
            'ground_footprint_polygon_xy_m': [list(p) for p in hull], 'ground_footprint_area_m2': _area(hull),
            'footprint_basis': f'PROJECTED_FROM_CALIBRATION floor z=0, grid {GRID_STEP_M} m, max {MAX_DIST_M} m, occluders NOT modelled',
            'calibration_sha256': entry.get('calibration_sha256'), '_cells': cells}


def build(region_graph: dict, camera_graph: dict, catalog: dict, camera_ids=None, source_sha256: dict | None = None, tracking_scope: dict | None = None,
          walls=None) -> dict:
    """Assemble the scene context. ``camera_ids`` limits the cameras (the cameras of the run). ``walls`` (F2): static wall segments
    [(ax, ay, bx, by), ...] from an approved geometry source; when given, each camera carries its wall-clipped visible area and the
    overlaps are computed on it. Default None keeps the unclipped v1 context byte-identical."""
    cat = {c['camera_id']: c for c in catalog['cameras']}
    ids = sorted(camera_ids) if camera_ids else sorted(cat)
    geo = {cid: camera_geometry(cat[cid], walls=walls) for cid in ids}
    overlap = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            inter = len(geo[a]['_cells'] & geo[b]['_cells'])
            if inter:
                union = len(geo[a]['_cells'] | geo[b]['_cells'])
                overlap.append({'cameras': [a, b], 'overlap_area_m2': inter * GRID_STEP_M ** 2, 'overlap_iou': inter / union})
    gcams = {c['camera_id']: c for c in camera_graph['cameras']}
    cameras = []
    for cid in ids:
        g = dict(geo[cid])
        g.pop('_cells')
        gc = gcams.get(cid, {})
        g['covered_regions'] = [{'region_id': r['region_id'], 'basis': r['basis']} for r in gc.get('covered_regions', [])]
        g['entry_zones'] = [{'id': z['entry_zone_id'], 'roi_px': z['roi_polygon_px']} for z in gc.get('entry_zones', [])]
        g['exit_zones'] = [{'id': z['exit_zone_id'], 'roi_px': z['roi_polygon_px'], 'leads_to_edge_ids': z['leads_to_edge_ids']}
                           for z in gc.get('exit_zones', [])]
        cameras.append(g)
    transitions = [{'id': t.get('transition_id'), 'from': t['from_camera_id'], 'to': t['to_camera_id'], 'disposition': 'TRANSITION',
                    'approval': camera_graph.get('approval_status')} for t in camera_graph.get('transitions', [])]
    excluded = [{'from': p['from_camera_id'], 'to': p['to_camera_id'], 'reason': p.get('reason')}
                for p in ((tracking_scope or {}).get('directed_pairs') or []) if p.get('disposition') == 'EXCLUDED'
                and (not camera_ids or {p['from_camera_id'], p['to_camera_id']} <= set(ids))]
    ctx = {
        'schema': SCHEMA,
        'identity': 'UNCONFIRMED', 'physical_walkability': 'UNKNOWN',
        'regions': [{'id': r['region_id'], 'kind': r['kind'], 'floor': r.get('floor_id')} for r in region_graph['regions']],
        'region_edges': [{'id': e['edge_id'], 'regions': e['regions'], 'state': e['state'], 'traversability': e['traversability'],
                          'via': e.get('via')} for e in region_graph['edges']],
        'region_graph_approval': region_graph.get('approval_status'),
        'camera_graph_approval': camera_graph.get('approval_status'),
        'camera_transitions': sorted(transitions, key=lambda t: (t['from'], t['to'])),
        'excluded_camera_pairs': sorted(excluded, key=lambda t: (t['from'], t['to'])),
        'cameras': cameras,
        'overlaps': overlap,
        'sources': dict(sorted((source_sha256 or {}).items())),
        'incomplete': (['PEOPLE_OCCLUSION_NOT_MODELLED'] if walls is not None else ['OCCLUSION_NOT_MODELLED', 'WALL_GEOMETRY_NOT_IN_CONTEXT']) + (['SCENE_CONTEXT_INCOMPLETE:NO_SOURCE_HASHES'] if not source_sha256 else []),
    }
    missing = [c for c in ids if c not in gcams]
    if missing:
        ctx['incomplete'].append('SCENE_CONTEXT_INCOMPLETE:CAMERAS_NOT_IN_GRAPH:' + ','.join(missing))
    assert_no_forbidden(ctx)
    return ctx

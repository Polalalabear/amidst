"""Script-level actor clearance checker for authored multi-actor scenario drafts (D198, D207).

Usage: python scripts/design/check_actor_clearance.py <scenario.json> [--out report.json]

Pure Python, standard library only, no network. File I/O: the input/output paths and, when the
draft declares "geometry_ref", that repo-relative 2D scene geometry JSON
(docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json: wall/screen/vehicle segments, full-height
occluders, camera catalog matrices). Input is an authored scenario draft (planning waypoints
only). It never reads renders, renderer output, detections or private scoring data, and its
verdicts say nothing about physical navigation, which stays UNKNOWN.

Checks per run:
  pair_distance   every pair of present actors keeps centre distance >= min_pair_distance_m.
                  Evaluated on the 5 fps grid, on subdivisions of each grid interval, and
                  exactly (closed form) between all breakpoints, so a crossing that happens
                  between grid points is still caught.
  side_by_side    inside a declared corridor, whenever two actors are side by side
                  (|along offset| <= side_by_side_along_m) their lateral offset must be
                  >= min_side_by_side_lateral_m (same-direction or opposite-direction passing).
  doors           one actor at a time in a door's passage zone, and passage reference times
                  of two actors at the same door at least door_min_stagger_us apart.
  walls           centre distance to declared wall/furniture segments >= min_wall_clearance_m,
                  computed analytically per leg (segment-to-segment distance, exact minimum and
                  its time), not by sampling. walls may be a segment list, null (UNKNOWN) or
                  "FROM_GEOMETRY" (the geometry_ref clearance_segments). Optional
                  advisory_boundaries are reported separately and never change the verdict.
  spawn_exit      (D207) every actor's first and last presence is out of view of every render
                  camera of the run, unless it is present at t=0 with a written
                  present_at_t0_note, or stays until duration_us (recording end counts as exit).
                  Pure geometry: a vertical body prism (body_radius_m, body_height_m, 8 sides)
                  is OUT_OF_FRUSTUM when one frustum plane excludes all its corners, or
                  WALL_OCCLUDED when one full-height occluder separates the camera from the whole
                  footprint in XY. A corner inside the frustum with no occluder on its sight line
                  is IN_VIEW (FAIL); anything else is UNKNOWN. Other actors and partial-height
                  objects never count as occluders, so the check can only err towards FAIL/UNKNOWN.
                  UNKNOWN when the draft has no geometry or omits render_camera_ids; an explicit
                  empty render_camera_ids list means nothing is rendered (PASS).
  seed            no non-target actor is present before seed.exclusive_until_us.
  speed           no leg faster than max_speed_m_s.

Verdict: FAIL if any check fails, else UNKNOWN if any check is UNKNOWN, else PASS.
Exit codes: 0 PASS, 1 FAIL, 2 invalid input, 3 UNKNOWN.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys

DEFAULT_RULES = {
    'sample_interval_us': 200_000,
    'subdivisions': 10,
    'min_pair_distance_m': 0.6,
    'min_side_by_side_lateral_m': 0.8,
    'side_by_side_along_m': 0.6,
    'door_zone_half_depth_m': 0.5,
    'door_min_stagger_us': 1_500_000,
    'min_wall_clearance_m': 0.35,
    'max_speed_m_s': 1.6,
    'body_radius_m': 0.35,
    'body_height_m': 1.85,
}
ROOT = __import__('pathlib').Path(__file__).resolve().parents[2]
EPS = 1e-9


class ScenarioError(ValueError):
    pass


# ---------------------------------------------------------------- geometry helpers

def _num(value, what):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ScenarioError(f'{what} must be a finite number')
    return float(value)


def _xy(value, what):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ScenarioError(f'{what} must be [x, y] or [x, y, z]')
    return (_num(value[0], what), _num(value[1], what))


def _seg_point_distance(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 <= EPS:
        return math.hypot(p[0] - ax, p[1] - ay)
    u = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    return math.hypot(p[0] - (ax + u * dx), p[1] - (ay + u * dy))


class Actor:
    def __init__(self, raw):
        if not isinstance(raw, dict) or not isinstance(raw.get('actor_id'), str) or not raw['actor_id']:
            raise ScenarioError('every actor needs a non-empty actor_id')
        self.actor_id = raw['actor_id']
        points = raw.get('waypoints')
        if not isinstance(points, list) or len(points) < 1:
            raise ScenarioError(f'{self.actor_id}: waypoints must be a non-empty list')
        self.times, self.points, self.holds = [], [], []
        for i, wp in enumerate(points):
            t = wp.get('t_us') if isinstance(wp, dict) else None
            if type(t) is not int or t < 0:
                raise ScenarioError(f'{self.actor_id}: waypoint {i} t_us must be a non-negative integer')
            if self.times and t <= self.times[-1]:
                raise ScenarioError(f'{self.actor_id}: waypoint times must strictly increase')
            self.times.append(t)
            self.points.append(_xy(wp.get('xy'), f'{self.actor_id} waypoint {i} xy'))
            self.holds.append(wp.get('hold_reason'))

    @property
    def start(self):
        return self.times[0]

    @property
    def end(self):
        return self.times[-1]

    def present(self, t):
        return self.start <= t <= self.end

    def at(self, t):
        """Linear interpolation between waypoints; None when the actor is not present."""
        if not self.present(t):
            return None
        lo, hi = 0, len(self.times) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.times[mid] <= t:
                lo = mid
            else:
                hi = mid
        if hi == lo or t <= self.times[lo]:
            return self.points[lo]
        if t >= self.times[hi]:
            return self.points[hi]
        f = (t - self.times[lo]) / (self.times[hi] - self.times[lo])
        (x0, y0), (x1, y1) = self.points[lo], self.points[hi]
        return (x0 + f * (x1 - x0), y0 + f * (y1 - y0))

    def legs(self):
        for i in range(len(self.times) - 1):
            (x0, y0), (x1, y1) = self.points[i], self.points[i + 1]
            dt = (self.times[i + 1] - self.times[i]) / 1e6
            yield i, math.hypot(x1 - x0, y1 - y0) / dt


# ---------------------------------------------------------------- time bases

def grid_times(start, end, step):
    first = -(-start // step) * step
    return list(range(first, end + 1, step))


def dense_times(start, end, step, subdivisions, extra):
    out = set()
    for g in grid_times(start - start % step, end, step):
        for k in range(subdivisions):
            t = g + (step * k) // subdivisions
            if start <= t <= end:
                out.add(t)
    out.update(t for t in extra if start <= t <= end)
    out.update((start, end))
    return sorted(out)


def _exact_min_between(a, b, t0, t1):
    """Exact minimum centre distance on [t0, t1] where both actors move linearly."""
    p0, q0 = a.at(t0), b.at(t0)
    p1, q1 = a.at(t1), b.at(t1)
    d0 = (p0[0] - q0[0], p0[1] - q0[1])
    d1 = (p1[0] - q1[0], p1[1] - q1[1])
    v = (d1[0] - d0[0], d1[1] - d0[1])
    vv = v[0] * v[0] + v[1] * v[1]
    u = 0.0 if vv <= EPS else max(0.0, min(1.0, -(d0[0] * v[0] + d0[1] * v[1]) / vv))
    return math.hypot(d0[0] + u * v[0], d0[1] + u * v[1]), t0 + u * (t1 - t0)


# ---------------------------------------------------------------- checks

def check_pairs(actors, rules):
    step, thr = rules['sample_interval_us'], rules['min_pair_distance_m']
    rows = []
    for a, b in itertools.combinations(actors, 2):
        start, end = max(a.start, b.start), min(a.end, b.end)
        if start > end:
            rows.append({'pair': [a.actor_id, b.actor_id], 'overlap_us': None, 'status': 'PASS',
                         'note': 'NEVER_PRESENT_TOGETHER'})
            continue
        grid = [t for t in grid_times(start, end, step)]
        grid_min = min(((math.dist(a.at(t), b.at(t)), t) for t in grid), default=(None, None))
        times = dense_times(start, end, step, rules['subdivisions'], a.times + b.times)
        best = (math.inf, None)
        for t0, t1 in zip(times, times[1:]):
            best = min(best, _exact_min_between(a, b, t0, t1))
        if len(times) == 1:
            best = (math.dist(a.at(start), b.at(start)), start)
        refined, at = best
        status = 'PASS' if refined >= thr - EPS else 'FAIL'
        rows.append({
            'pair': [a.actor_id, b.actor_id], 'overlap_us': [start, end],
            'min_distance_m': round(refined, 4), 'min_at_us': int(round(at)),
            'grid_min_distance_m': None if grid_min[0] is None else round(grid_min[0], 4),
            'grid_min_at_us': grid_min[1],
            'caught_only_by_interpolation': bool(status == 'FAIL' and grid_min[0] is not None
                                                 and grid_min[0] >= thr - EPS),
            'status': status})
    return {'threshold_m': thr, 'pairs': rows,
            'status': 'FAIL' if any(r['status'] == 'FAIL' for r in rows) else 'PASS'}


def _inside(box, p):
    (x0, x1), (y0, y1) = box
    return x0 - EPS <= p[0] <= x1 + EPS and y0 - EPS <= p[1] <= y1 + EPS


def check_side_by_side(actors, corridors, rules):
    if not corridors:
        return {'status': 'PASS', 'note': 'NO_CORRIDORS_DECLARED', 'pairs': []}
    step = rules['sample_interval_us']
    along_thr, lat_thr = rules['side_by_side_along_m'], rules['min_side_by_side_lateral_m']
    rows = []
    for a, b in itertools.combinations(actors, 2):
        start, end = max(a.start, b.start), min(a.end, b.end)
        if start > end:
            continue
        times = dense_times(start, end, step, rules['subdivisions'], a.times + b.times)
        worst = None
        for c in corridors:
            ai = 0 if c['along_axis'] == 'x' else 1
            li = 1 - ai
            for t in times:
                p, q = a.at(t), b.at(t)
                if not (_inside(c['bounds'], p) and _inside(c['bounds'], q)):
                    continue
                if abs(p[ai] - q[ai]) > along_thr + EPS:
                    continue
                lateral = abs(p[li] - q[li])
                if worst is None or lateral < worst[0]:
                    worst = (lateral, t, c['corridor_id'])
        if worst is not None:
            rows.append({'pair': [a.actor_id, b.actor_id], 'corridor_id': worst[2],
                         'min_lateral_m': round(worst[0], 4), 'at_us': worst[1],
                         'status': 'PASS' if worst[0] >= lat_thr - EPS else 'FAIL'})
    return {'threshold_m': lat_thr, 'side_by_side_along_m': along_thr, 'pairs': rows,
            'status': 'FAIL' if any(r['status'] == 'FAIL' for r in rows) else 'PASS'}


def _door_frame(door):
    cx, cy = door['center']
    nx, ny = door['normal']
    norm = math.hypot(nx, ny)
    nx, ny = nx / norm, ny / norm
    return cx, cy, nx, ny, -ny, nx


def door_passages(actor, door, rules):
    cx, cy, nx, ny, tx, ty = _door_frame(door)
    half_depth, half_width = rules['door_zone_half_depth_m'], door['width_m'] / 2
    times = dense_times(actor.start, actor.end, rules['sample_interval_us'],
                        rules['subdivisions'], actor.times)
    passages, current, prev = [], None, None
    for t in times:
        x, y = actor.at(t)
        n = (x - cx) * nx + (y - cy) * ny
        s = (x - cx) * tx + (y - cy) * ty
        inside = abs(n) <= half_depth + EPS and abs(s) <= half_width + EPS
        if inside:
            if current is None:
                current = {'enter_us': t, 'exit_us': t, 'side': 0, 'crossings': [],
                           'min_ref_us': t, 'abs_n_min': abs(n)}
            current['exit_us'] = t
            if abs(n) < current['abs_n_min'] - EPS:
                current['abs_n_min'], current['min_ref_us'] = abs(n), t
            side = 1 if n > EPS else -1 if n < -EPS else 0
            if side:
                if current['side'] and side != current['side']:
                    # interpolate the plane crossing between the previous sample and this one
                    pt, pn = prev
                    f = pn / (pn - n) if abs(pn - n) > EPS else 0.0
                    current['crossings'].append(int(round(pt + f * (t - pt))))
                current['side'] = side
        elif current is not None:
            passages.append(current)
            current = None
        prev = (t, n)
    if current is not None:
        passages.append(current)
    out = []
    for p in passages:
        refs = p['crossings'] or [p['min_ref_us']]
        out.append({'actor_id': actor.actor_id, 'enter_us': p['enter_us'], 'exit_us': p['exit_us'],
                    'ref_us': refs[0], 'crossing_refs_us': p['crossings'],
                    'kind': f"CROSS_X{len(p['crossings'])}" if p['crossings'] else 'ENTER_NO_CROSS'})
    return out


def check_doors(actors, doors, rules):
    stagger = rules['door_min_stagger_us']
    reports = []
    for door in doors:
        passages = sorted((p for a in actors for p in door_passages(a, door, rules)),
                          key=lambda p: (p['enter_us'], p['actor_id']))
        conflicts = []
        for p, q in itertools.combinations(passages, 2):
            if p['actor_id'] == q['actor_id']:
                continue
            first, second = (p, q) if p['enter_us'] <= q['enter_us'] else (q, p)
            clear_gap = second['enter_us'] - first['exit_us']
            ref_gap = min(abs(r2 - r1) for r1 in (first['crossing_refs_us'] or [first['ref_us']])
                          for r2 in (second['crossing_refs_us'] or [second['ref_us']]))
            codes = []
            if clear_gap < 0:
                codes.append('SIMULTANEOUS_OCCUPANCY')
            if ref_gap < stagger:
                codes.append('STAGGER_TOO_SHORT')
            if codes:
                conflicts.append({'actors': [first['actor_id'], second['actor_id']], 'codes': codes,
                                  'clear_gap_us': clear_gap, 'ref_gap_us': ref_gap,
                                  'first_ref_us': first['ref_us'], 'second_ref_us': second['ref_us']})
        reports.append({'door_id': door['door_id'], 'width_m': door['width_m'],
                        'geometry_status': door.get('geometry_status', 'DECLARED'),
                        'passages': passages, 'conflicts': conflicts,
                        'status': 'FAIL' if conflicts else 'PASS'})
    return {'door_min_stagger_us': stagger, 'zone_half_depth_m': rules['door_zone_half_depth_m'],
            'doors': reports,
            'status': 'FAIL' if any(d['status'] == 'FAIL' for d in reports) else 'PASS'}


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _proj_param(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 <= EPS:
        return 0.0
    return max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))


def path_segment_min(p0, p1, a, b):
    """Exact minimum distance between path p0->p1 and static segment a-b; returns (d, u on path)."""
    d1, d2 = _cross(a, b, p0), _cross(a, b, p1)
    d3, d4 = _cross(p0, p1, a), _cross(p0, p1, b)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return 0.0, d1 / (d1 - d2)
    cands = [(_seg_point_distance(p0, a, b), 0.0), (_seg_point_distance(p1, a, b), 1.0)]
    for q in (a, b):
        u = _proj_param(q, p0, p1)
        pt = (p0[0] + u * (p1[0] - p0[0]), p0[1] + u * (p1[1] - p0[1]))
        cands.append((math.hypot(q[0] - pt[0], q[1] - pt[1]), u))
    return min(cands)


def _clearance(actors, segments, rules):
    """Analytic per-leg minimum (actors move linearly between waypoints, so this is exact)."""
    thr = rules['min_wall_clearance_m']
    rows = []
    for a in actors:
        legs = [(a.times[i], a.times[i + 1], a.points[i], a.points[i + 1]) for i in range(len(a.times) - 1)]
        if not legs:
            legs = [(a.times[0], a.times[0], a.points[0], a.points[0])]
        best = (math.inf, None, None, None)
        for t0, t1, p0, p1 in legs:
            for seg in segments:
                d, u = path_segment_min(p0, p1, seg['a'], seg['b'])
                if d < best[0] - EPS:
                    pos = (p0[0] + u * (p1[0] - p0[0]), p0[1] + u * (p1[1] - p0[1]))
                    best = (d, int(round(t0 + u * (t1 - t0))), seg['segment_id'], pos)
        rows.append({'actor_id': a.actor_id,
                     'min_clearance_m': None if best[1] is None else round(best[0], 4),
                     'at_us': best[1], 'segment_id': best[2],
                     'position_xy': None if best[3] is None else [round(best[3][0], 4), round(best[3][1], 4)],
                     'pass': best[0] >= thr - EPS})
    return thr, rows


def check_walls(actors, walls, advisory, rules):
    result = {'threshold_m': rules['min_wall_clearance_m'], 'method': 'ANALYTIC_SEGMENT_DISTANCE_PER_LEG'}
    if walls is None:
        result.update(status='UNKNOWN', reason='NO_WALL_OR_FURNITURE_GEOMETRY_DECLARED', actors=[])
    else:
        _, rows = _clearance(actors, walls, rules)
        for r in rows:
            r['status'] = 'PASS' if r.pop('pass') else 'FAIL'
        result.update(actors=rows, status='FAIL' if any(r['status'] == 'FAIL' for r in rows) else 'PASS')
    if advisory:
        _, rows = _clearance(actors, advisory, rules)
        for r in rows:
            r['advisory'] = 'ADVISORY_PASS' if r.pop('pass') else 'ADVISORY_FAIL'
        result['advisory'] = {'note': 'ADVISORY_ONLY_NOT_WALL_GEOMETRY_DOES_NOT_CHANGE_VERDICT',
                              'actors': rows}
    return result


def _camera_status(cam, foot_xy, floor_z, rules, occluders):
    m = cam['camera_to_world']
    rot = [[m[j][i] for j in range(3)] for i in range(3)]          # world -> camera rotation
    origin = (m[0][3], m[1][3], m[2][3])
    r = rules['body_radius_m'] / math.cos(math.pi / 8)            # octagon circumscribing the body circle
    corners = []
    for k in range(8):
        ang = 2 * math.pi * k / 8
        x, y = foot_xy[0] + r * math.cos(ang), foot_xy[1] + r * math.sin(ang)
        for z in (floor_z, floor_z + rules['body_height_m']):
            corners.append((x, y, z))
    vals = []
    for p in corners:
        d = (p[0] - origin[0], p[1] - origin[1], p[2] - origin[2])
        q = [sum(rot[i][k] * d[k] for k in range(3)) for i in range(3)]
        depth = -q[2]
        vals.append((depth - cam['clip_start'], cam['clip_end'] - depth,
                     cam['fx'] * q[0] + cam['cx'] * depth, (cam['width'] - cam['cx']) * depth - cam['fx'] * q[0],
                     cam['cy'] * depth - cam['fy'] * q[1], (cam['height'] - cam['cy']) * depth + cam['fy'] * q[1]))
    if any(all(v[i] < 0 for v in vals) for i in range(6)):
        return 'OUT_OF_FRUSTUM', None
    cxy = origin[:2]
    foot = [(p[0], p[1]) for p in corners[::2]]
    for occ in occluders:
        a, b = occ['a'], occ['b']
        sc = _cross(a, b, cxy)
        if abs(sc) > EPS and all(_cross(a, b, f) * sc < 0 and _cross(cxy, f, a) * _cross(cxy, f, b) <= 0 for f in foot):
            return 'WALL_OCCLUDED', occ['occluder_id']
    for p, v in zip(corners, vals):
        if min(v) >= 0:
            blocked = False
            for occ in occluders:
                a, b = occ['a'], occ['b']
                if (_cross(a, b, cxy) * _cross(a, b, p) < 0) and (_cross(cxy, p, a) * _cross(cxy, p, b) < 0):
                    blocked = True
                    break
            if not blocked:
                return 'IN_VIEW', [round(c, 3) for c in p]
    return 'UNKNOWN', None


def _floor_z(floors, xy):
    tops = [f['top_z_m'] for f in floors
            if min(f['x_m']) - EPS <= xy[0] <= max(f['x_m']) + EPS and min(f['y_m']) - EPS <= xy[1] <= max(f['y_m']) + EPS]
    return max(tops) if tops else 0.0


def endpoint_visibility(xy, cameras, floors, occluders, rules):
    rows = []
    for cam in cameras:
        status, why = _camera_status(cam, xy, _floor_z(floors, xy), rules, occluders)
        row = {'camera_id': cam['camera_id'], 'status': status}
        if status == 'WALL_OCCLUDED':
            row['occluder_id'] = why
        elif status == 'IN_VIEW':
            row['witness_corner_world_m'] = why
        rows.append(row)
    states = {r['status'] for r in rows}
    verdict = 'FAIL' if 'IN_VIEW' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'PASS'
    return verdict, rows


def check_spawn_exit(actors, run, rules):
    geo, cam_ids = run.get('geometry'), run.get('render_camera_ids')
    if cam_ids == []:
        return {'status': 'PASS', 'note': 'RUN_DECLARES_NO_RENDER_CAMERAS', 'actors': []}
    if not geo or not cam_ids:
        return {'status': 'UNKNOWN', 'reason': 'NO_GEOMETRY_OR_RENDER_CAMERAS_DECLARED', 'actors': []}
    by_id = {c['camera_id']: c for c in geo['cameras']}
    missing = [c for c in cam_ids if c not in by_id]
    if missing:
        raise ScenarioError(f'render cameras not in geometry catalog: {missing}')
    cameras = [by_id[c] for c in cam_ids]
    floors, occluders = geo.get('floors', []), geo.get('occluders_full_height', [])
    step, duration = rules['sample_interval_us'], run.get('duration_us')
    rows = []
    for a in actors:
        for which in ('first', 'last'):
            t = a.start if which == 'first' else a.end
            row = {'actor_id': a.actor_id, 'endpoint': which, 't_us': t}
            if which == 'first' and t == 0:
                note = run['notes'].get(a.actor_id)
                row.update(kind='PRESENT_AT_T0', note=note,
                           status='PASS' if isinstance(note, str) and note.strip() else 'FAIL')
            elif which == 'last' and duration is not None and t == duration:
                row.update(kind='STAYS_TO_RECORDING_END', status='PASS')
            else:
                # the exact endpoint plus the nearest render frame on the presence side
                frame = (-(-t // step) * step) if which == 'first' else (t // step) * step
                times = sorted({t, frame}) if a.present(frame) else [t]
                checks = []
                for tt in times:
                    xy = a.at(tt)
                    verdict, cams = endpoint_visibility(xy, cameras, floors, occluders, rules)
                    checks.append({'t_us': tt, 'xy': [round(xy[0], 4), round(xy[1], 4)], 'status': verdict, 'cameras': cams})
                states = {c['status'] for c in checks}
                row.update(kind='SPAWN' if which == 'first' else 'DESPAWN', samples=checks,
                           status='FAIL' if 'FAIL' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'PASS')
            rows.append(row)
    states = {r['status'] for r in rows}
    return {'render_camera_ids': cam_ids, 'body_radius_m': rules['body_radius_m'],
            'body_height_m': rules['body_height_m'], 'occlusion': 'FULL_HEIGHT_STATIC_WALLS_2D_ONLY',
            'actors': rows,
            'status': 'FAIL' if 'FAIL' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'PASS'}


def check_seed(actors, seed):
    if not seed:
        return {'status': 'PASS', 'note': 'NO_SEED_RULE_DECLARED'}
    until = seed['exclusive_until_us']
    early = [{'actor_id': a.actor_id, 'first_present_us': a.start}
             for a in actors if a.actor_id != seed['actor_id'] and a.start < until]
    return {'seed_actor_id': seed['actor_id'], 'exclusive_until_us': until, 'violations': early,
            'status': 'FAIL' if early else 'PASS'}


def check_speed(actors, rules):
    cap = rules['max_speed_m_s']
    rows = []
    for a in actors:
        legs = list(a.legs())
        top = max(legs, key=lambda x: x[1], default=(None, 0.0))
        rows.append({'actor_id': a.actor_id, 'max_speed_m_s': round(top[1], 4), 'leg_index': top[0],
                     'status': 'PASS' if top[1] <= cap + EPS else 'FAIL'})
    return {'max_speed_m_s': cap, 'actors': rows,
            'status': 'FAIL' if any(r['status'] == 'FAIL' for r in rows) else 'PASS'}


# ---------------------------------------------------------------- parsing and driver

def _segments(raw, what):
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ScenarioError(f'{what} must be a list of segments or null')
    out = []
    for i, seg in enumerate(raw):
        if not isinstance(seg, dict):
            raise ScenarioError(f'{what}[{i}] must be an object')
        out.append({'segment_id': str(seg.get('segment_id', f'{what}[{i}]')),
                    'a': _xy(seg.get('a'), f'{what}[{i}].a'), 'b': _xy(seg.get('b'), f'{what}[{i}].b')})
    return out


def load_geometry(ref, base_dir=None):
    path = __import__('pathlib').Path(ref)
    if not path.is_absolute():
        path = (__import__('pathlib').Path(base_dir) if base_dir else ROOT) / path
    with open(path, encoding='utf-8') as fh:
        geo = json.load(fh)
    for key in ('clearance_segments', 'occluders_full_height', 'cameras'):
        if not isinstance(geo.get(key), list) or not geo[key]:
            raise ScenarioError(f'geometry {ref}: {key} must be a non-empty list')
    return geo


def parse_run(raw, base_rules, geometry=None):
    if not isinstance(raw, dict):
        raise ScenarioError('run must be an object')
    rules = dict(base_rules)
    for key, value in (raw.get('rules') or {}).items():
        if key not in DEFAULT_RULES:
            raise ScenarioError(f'unknown rule {key}')
        rules[key] = value
    for key in ('sample_interval_us', 'subdivisions', 'door_min_stagger_us'):
        if type(rules[key]) is not int or rules[key] <= 0:
            raise ScenarioError(f'rule {key} must be a positive integer')
    actors = [Actor(a) for a in raw.get('actors') or []]
    if len(actors) < 1:
        raise ScenarioError('run needs at least one actor')
    if len({a.actor_id for a in actors}) != len(actors):
        raise ScenarioError('actor_id values must be unique')
    duration = raw.get('duration_us')
    if duration is not None and (type(duration) is not int or any(a.end > duration for a in actors)):
        raise ScenarioError('duration_us must be an integer covering every waypoint')
    doors = []
    for i, d in enumerate(raw.get('doors') or []):
        normal = _xy(d.get('normal_xy'), f'doors[{i}].normal_xy')
        if math.hypot(*normal) <= EPS:
            raise ScenarioError(f'doors[{i}].normal_xy must be non-zero')
        doors.append({'door_id': str(d.get('door_id', f'door{i}')), 'center': _xy(d.get('center_xy'), f'doors[{i}].center_xy'),
                      'normal': normal, 'width_m': _num(d.get('width_m'), f'doors[{i}].width_m'),
                      'geometry_status': d.get('geometry_status', 'DECLARED')})
    corridors = []
    for i, c in enumerate(raw.get('corridors') or []):
        b = c.get('bounds_xy')
        if c.get('along_axis') not in ('x', 'y') or not isinstance(b, list) or len(b) != 2:
            raise ScenarioError(f'corridors[{i}] needs along_axis x|y and bounds_xy [[x0,x1],[y0,y1]]')
        bounds = tuple(tuple(sorted((_num(r[0], 'bounds'), _num(r[1], 'bounds')))) for r in b)
        corridors.append({'corridor_id': str(c.get('corridor_id', f'corridor{i}')),
                          'along_axis': c['along_axis'], 'bounds': bounds})
    if 'walls' not in raw:
        raise ScenarioError('run must declare walls (a list of segments, "FROM_GEOMETRY", or null when UNKNOWN)')
    walls = raw['walls']
    if walls == 'FROM_GEOMETRY':
        if geometry is None:
            raise ScenarioError('walls FROM_GEOMETRY needs a document geometry_ref')
        walls = geometry['clearance_segments']
    cam_ids = raw.get('render_camera_ids')
    if cam_ids is not None and (not isinstance(cam_ids, list) or not all(isinstance(c, str) for c in cam_ids)):
        raise ScenarioError('render_camera_ids must be a list of camera ids')
    notes = {a['actor_id']: a.get('present_at_t0_note') for a in raw.get('actors') or [] if isinstance(a, dict)}
    seed = raw.get('seed')
    if seed is not None and (not isinstance(seed, dict) or type(seed.get('exclusive_until_us')) is not int
                             or seed.get('actor_id') not in {a.actor_id for a in actors}):
        raise ScenarioError('seed needs a known actor_id and integer exclusive_until_us')
    return {'run_id': str(raw.get('run_id', 'run')), 'rules': rules, 'actors': actors, 'doors': doors,
            'corridors': corridors, 'walls': _segments(walls, 'walls'),
            'advisory': _segments(raw.get('advisory_boundaries'), 'advisory_boundaries'), 'seed': seed,
            'duration_us': duration, 'geometry': geometry, 'render_camera_ids': cam_ids, 'notes': notes}


def check_run(run):
    actors, rules = run['actors'], run['rules']
    checks = {
        'pair_distance': check_pairs(actors, rules),
        'side_by_side': check_side_by_side(actors, run['corridors'], rules),
        'doors': check_doors(actors, run['doors'], rules),
        'walls': check_walls(actors, run['walls'], run['advisory'], rules),
        'spawn_exit': check_spawn_exit(actors, run, rules),
        'seed': check_seed(actors, run['seed']),
        'speed': check_speed(actors, rules),
    }
    states = {c['status'] for c in checks.values()}
    verdict = 'FAIL' if 'FAIL' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'PASS'
    return {'run_id': run['run_id'], 'verdict': verdict,
            'check_status': {k: v['status'] for k, v in checks.items()},
            'physical_navigation': 'UNKNOWN', 'rules': rules, 'checks': checks}


def check_document(doc, geometry=None, base_dir=None):
    """geometry: an already-loaded geometry dict; otherwise doc['geometry_ref'] is loaded
    (relative to base_dir, default the repository root)."""
    if not isinstance(doc, dict):
        raise ScenarioError('document must be a JSON object')
    if geometry is None and doc.get('geometry_ref'):
        geometry = load_geometry(doc['geometry_ref'], base_dir)
    base = dict(DEFAULT_RULES)
    for key, value in (doc.get('rules') or {}).items():
        if key not in DEFAULT_RULES:
            raise ScenarioError(f'unknown rule {key}')
        base[key] = value
    raw_runs = doc['runs'] if isinstance(doc.get('runs'), list) else [doc]
    runs = [check_run(parse_run(r, base, geometry)) for r in raw_runs]
    states = {r['verdict'] for r in runs}
    verdict = 'FAIL' if 'FAIL' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'PASS'
    out = {'checker': 'scripts/design/check_actor_clearance.py', 'verdict': verdict,
           'physical_navigation': 'UNKNOWN', 'runs': runs}
    if geometry is not None:
        out['geometry'] = {'ref': doc.get('geometry_ref'), 'schema': geometry.get('schema'),
                           'provenance': geometry.get('provenance')}
    return out


def summary_lines(report):
    lines = [f"verdict {report['verdict']} (physical navigation UNKNOWN)"]
    for run in report['runs']:
        lines.append(f"[{run['run_id']}] {run['verdict']} {run['check_status']}")
        for row in run['checks']['pair_distance']['pairs']:
            if 'min_distance_m' in row:
                lines.append(f"  pair {row['pair'][0]}-{row['pair'][1]}: min {row['min_distance_m']} m "
                             f"@ {row['min_at_us'] / 1e6:.3f} s ({row['status']})")
        for row in run['checks']['walls'].get('actors', []):
            lines.append(f"  wall {row['actor_id']}: min {row['min_clearance_m']} m @ "
                         f"{(row['at_us'] or 0) / 1e6:.3f} s {row['segment_id']} ({row['status']})")
        for row in run['checks']['spawn_exit'].get('actors', []):
            if row['status'] != 'PASS' or row['kind'] in ('SPAWN', 'DESPAWN'):
                lines.append(f"  {row['endpoint']} {row['actor_id']} {row['kind']} @ {row['t_us'] / 1e6:.2f} s: {row['status']}")
        for door in run['checks']['doors']['doors']:
            refs = ', '.join(f"{p['actor_id']}@" + '/'.join(f'{r / 1e6:.2f}s' for r in (p['crossing_refs_us'] or [p['ref_us']]))
                             for p in door['passages'])
            lines.append(f"  door {door['door_id']}: {door['status']} passages [{refs}]")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('scenario')
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    try:
        with open(args.scenario, encoding='utf-8') as fh:
            doc = json.load(fh)
        report = check_document(doc)
    except (OSError, json.JSONDecodeError, ScenarioError, KeyError, TypeError) as exc:
        print(json.dumps({'verdict': 'INVALID_INPUT', 'error': f'{type(exc).__name__}: {exc}'}))
        return 2
    text = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    print('\n'.join(summary_lines(report)))
    return {'PASS': 0, 'FAIL': 1, 'UNKNOWN': 3}[report['verdict']]


if __name__ == '__main__':
    sys.exit(main())

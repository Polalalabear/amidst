"""Display-only physical next-camera prediction for the tracking overhead view.

Pure and deterministic: the caller passes detection boxes, the pinned camera graph
and optional static display positions; nothing is read from disk. Inputs are the
target's last observed camera/time, its image-plane motion from detection boxes and
the graph's exits/transitions. Ground Truth, renderer trajectories, visibility,
depth and scripts are refused. Boxes after ``as_of_us`` are dropped, so a replay at
time t never sees later evidence. The output is a sketch for the UI (contract
DEMO_UI_SUPPORT_V1 §6), not a Q5 decision, a score input, an identity claim or a
walkable path; physical navigation stays UNKNOWN.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

SCHEMA_VERSION = 'q-demo.physical-prediction.v1'
DISPLAY_LABEL = '物理預測（示意，非實際路徑）'
CONFIDENCE_LABELS = {'HIGH': '較高', 'MEDIUM': '中', 'LOW': '低', 'UNKNOWN': '未知'}
FORBIDDEN_KEYS = frozenset({
    'ground_truth', 'gt', 'actor', 'actor_id', 'material_id', 'event_script', 'script',
    'renderer_trajectory', 'trajectory', 'visibility', 'depth', 'mask', 'private_evaluation',
    'production_manifest', 'persons.sim.json',
})
_RELATION_ORDER = {'OVERLAP': 0, 'BLIND_GAP': 1, 'UNKNOWN': 2}


class PredictionInputError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PredictionParams:
    """PROPOSED defaults; not an approved parameter set (see contract §6.3)."""
    min_samples: int = 3
    max_sample_span_us: int = 2_000_000
    min_speed_px_s: float = 20.0
    aligned_cosine: float = 0.5
    per_hop_window_us: tuple[int, int] = (1_000_000, 8_000_000)
    speed_range_m_s: tuple[float, float] = (0.5, 2.0)
    max_candidates: int = 3


DEFAULT_PARAMS = PredictionParams()


def _check_forbidden(value):
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PredictionInputError('NON_STRING_KEY')
            lowered = key.lower()
            if lowered in FORBIDDEN_KEYS or lowered.startswith('gt_'):
                raise PredictionInputError('FORBIDDEN_INFERENCE_INPUT')
            _check_forbidden(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_forbidden(child)


def _int(value, code):
    if type(value) is not int or value < 0:
        raise PredictionInputError(code)
    return value


def _number(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PredictionInputError(code)
    return float(value)


def _round(value, digits=6):
    return round(float(value), digits) + 0.0


def _canonical_hash(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _foot(box):
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise PredictionInputError('INVALID_BBOX')
    x1, y1, x2, y2 = (_number(v, 'INVALID_BBOX') for v in box)
    if x2 < x1 or y2 < y1:
        raise PredictionInputError('INVALID_BBOX')
    return (x1 + x2) / 2.0, y2


def _velocity(samples, params):
    """Least-squares image velocity (px/s) of the bbox foot point."""
    times = sorted({t for t, _ in samples})
    if len(times) < params.min_samples:
        return None
    t0 = samples[0][0]
    ts = [(t - t0) / 1e6 for t, _ in samples]
    mean_t = sum(ts) / len(ts)
    denom = sum((t - mean_t) ** 2 for t in ts)
    if denom <= 0:
        return None
    result = []
    for axis in (0, 1):
        values = [p[axis] for _, p in samples]
        mean_v = sum(values) / len(values)
        pairs = zip(ts, values, strict=True)
        result.append(sum((t - mean_t) * (v - mean_v) for t, v in pairs) / denom)
    return result[0], result[1]


def _inside(point, polygon):
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cross:
                inside = not inside
    return inside


def _polygon(zone):
    raw = zone.get('roi_polygon_px')
    if not isinstance(raw, list) or len(raw) < 3:
        raise PredictionInputError('INVALID_EXIT_ZONE')
    return [(_number(p[0], 'INVALID_EXIT_ZONE'), _number(p[1], 'INVALID_EXIT_ZONE')) for p in raw]


def _rank_exits(camera, foot, velocity, params):
    rows = []
    for zone in camera.get('exit_zones', []):
        zone_id = zone.get('exit_zone_id')
        if not isinstance(zone_id, str) or not zone_id:
            raise PredictionInputError('INVALID_EXIT_ZONE')
        polygon = _polygon(zone)
        cx = sum(p[0] for p in polygon) / len(polygon)
        cy = sum(p[1] for p in polygon) / len(polygon)
        inside = foot is not None and _inside(foot, polygon)
        cosine = None
        if velocity is not None and foot is not None:
            dx, dy = cx - foot[0], cy - foot[1]
            dist = math.hypot(dx, dy)
            speed = math.hypot(*velocity)
            cosine = 1.0 if dist < 1e-9 else (velocity[0] * dx + velocity[1] * dy) / (speed * dist)
        if velocity is not None:
            aligned = inside or (cosine is not None and cosine >= params.aligned_cosine)
            match = 'ALIGNED' if aligned else 'NOT_ALIGNED'
        else:
            match = 'LAST_POSITION_INSIDE' if inside else 'UNRANKED'
        rows.append({'exit_zone_id': zone_id,
                     'leads_to_edge_ids': sorted(zone.get('leads_to_edge_ids', [])),
                     'last_position_inside': inside,
                     'direction_cosine': None if cosine is None else _round(cosine),
                     'match': match})
    def order(row):
        cosine = row['direction_cosine']
        return (not row['last_position_inside'], -(cosine if cosine is not None else -2.0),
                row['exit_zone_id'])
    rows.sort(key=order)
    for index, row in enumerate(rows, 1):
        row['rank'] = index
    return rows


def _window(transition, last_observed_us, params):
    hops = transition.get('region_hops')
    if type(hops) is not int or hops < 1:
        hops = max(1, len(transition.get('region_path') or []) - 1)
    length = transition.get('nominal_path_length_m')
    overlap = transition.get('relation') == 'OVERLAP'
    numeric = isinstance(length, (int, float)) and not isinstance(length, bool)
    if numeric and math.isfinite(length) and length > 0:
        vmin, vmax = params.speed_range_m_s
        start = 0 if overlap else int(math.floor(length / vmax * 1e6))
        end = int(math.ceil(length / vmin * 1e6))
        basis = 'NOMINAL_LENGTH_AND_SPEED_RANGE'
    else:
        low, high = params.per_hop_window_us
        start = 0 if overlap else hops * low
        end = hops * high
        basis = 'PARAMETER_PER_HOP'
    return [last_observed_us + start, last_observed_us + end], basis


def predict_next_cameras(*, last_camera_id: str, last_observed_us: int, as_of_us: int,
                         boxes: Sequence[Mapping], camera_graph: Mapping,
                         display_positions: Mapping[str, Sequence[float]] | None = None,
                         params: PredictionParams | None = None) -> dict:
    """Return a hashed, display-only prediction document (contract §6)."""
    params = params or DEFAULT_PARAMS
    _check_forbidden({'boxes': list(boxes), 'camera_graph': camera_graph,
                      'display_positions': dict(display_positions or {})})
    if not isinstance(last_camera_id, str) or not last_camera_id:
        raise PredictionInputError('INVALID_CAMERA_ID')
    last_observed_us = _int(last_observed_us, 'INVALID_TIME')
    as_of_us = _int(as_of_us, 'INVALID_TIME')
    if last_observed_us > as_of_us:
        raise PredictionInputError('FUTURE_INPUT')
    if (not isinstance(camera_graph, Mapping)
            or camera_graph.get('schema_version') != 'q-demo.camera-transition-graph.v1'):
        raise PredictionInputError('INVALID_CAMERA_GRAPH')

    dropped = 0
    samples = []
    for box in boxes:
        if not isinstance(box, Mapping):
            raise PredictionInputError('INVALID_BOX')
        t = _int(box.get('source_time_us'), 'INVALID_TIME')
        if t > as_of_us:
            dropped += 1
            continue
        if box.get('camera_id') != last_camera_id or t > last_observed_us:
            continue
        if last_observed_us - t > params.max_sample_span_us:
            continue
        samples.append((t, _foot(box.get('bbox_xyxy_px'))))
    samples.sort(key=lambda s: (s[0], s[1]))
    foot = samples[-1][1] if samples else None
    velocity = _velocity(samples, params) if samples else None
    speed = None if velocity is None else math.hypot(*velocity)
    if velocity is not None and speed < params.min_speed_px_s:
        velocity = None
    direction = {'status': 'KNOWN' if velocity is not None else 'UNKNOWN',
                 'image_velocity_px_s': (None if velocity is None
                                         else [_round(velocity[0], 3), _round(velocity[1], 3)]),
                 'samples_used': len(samples), 'basis': 'DETECTION_BBOX_FOOT_POINT'}

    cameras = {c.get('camera_id'): c for c in camera_graph.get('cameras', [])}
    positions = {}
    for key, value in (display_positions or {}).items():
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise PredictionInputError('INVALID_DISPLAY_POSITION')
        positions[key] = [_round(_number(value[0], 'INVALID_DISPLAY_POSITION'), 3),
                          _round(_number(value[1], 'INVALID_DISPLAY_POSITION'), 3)]

    doc = {'schema_version': SCHEMA_VERSION, 'as_of_us': as_of_us,
           'last_camera_id': last_camera_id, 'last_observed_us': last_observed_us,
           'direction': direction, 'exits': [], 'candidates': [],
           'truncated_count': 0, 'inputs_after_as_of_dropped': dropped,
           'graph_approval_status': camera_graph.get('approval_status'),
           'parameter_status': 'PROPOSED_DEFAULT', 'display_label': DISPLAY_LABEL,
           'used_for': 'DISPLAY_ONLY',
           'identity_verdict': 'UNCONFIRMED', 'physical_navigation': 'UNKNOWN', 'gt_read': False}
    camera = cameras.get(last_camera_id)
    if camera is None:
        doc['status'] = 'CAMERA_NOT_IN_GRAPH'
        doc['content_sha256'] = _canonical_hash(doc)
        return doc

    exits = _rank_exits(camera, foot, velocity, params)
    doc['exits'] = exits
    by_exit = {row['exit_zone_id']: row for row in exits}
    top = exits[0]['exit_zone_id'] if exits else None
    graph_approved = camera_graph.get('approval_status') == 'APPROVED'
    rows = []
    for transition in camera_graph.get('transitions', []):
        if transition.get('from_camera_id') != last_camera_id:
            continue
        via = [z for z in transition.get('via_exit_zone_ids', []) if z in by_exit]
        best = min(via, key=lambda z: by_exit[z]['rank']) if via else None
        rank = by_exit[best]['rank'] if best else len(exits) + 1
        relation = _RELATION_ORDER.get(transition.get('relation'), 3)
        rows.append((rank, relation, transition.get('transition_id'), best, transition))
    rows.sort(key=lambda r: (r[0], r[1], str(r[2])))
    per_top_exit = sum(1 for r in rows if r[3] is not None and r[3] == top)

    candidates = []
    for _, _, transition_id, best, transition in rows:
        exit_row = by_exit.get(best) if best else None
        match = exit_row['match'] if exit_row else 'NO_EXIT_ZONE'
        if velocity is None and match != 'LAST_POSITION_INSIDE':
            confidence = 'UNKNOWN'
        elif best is not None and best == top and match in {'ALIGNED', 'LAST_POSITION_INSIDE'}:
            confidence = 'MEDIUM'
            if (graph_approved and velocity is not None and per_top_exit == 1
                    and transition.get('path_traversability') == 'APPROVED_WALKABLE'
                    and transition.get('path_has_unknown_state') is False):
                confidence = 'HIGH'
        else:
            confidence = 'LOW'
        window, basis = _window(transition, last_observed_us, params)
        to_camera = transition.get('to_camera_id')
        sketch = None
        if last_camera_id in positions and to_camera in positions:
            sketch = [positions[last_camera_id], positions[to_camera]]
        candidates.append({
            'camera_id': to_camera, 'transition_id': transition_id, 'via_exit_zone_id': best,
            'exit_match': match, 'relation': transition.get('relation'),
            'path_traversability': transition.get('path_traversability'),
            'path_has_unknown_state': transition.get('path_has_unknown_state'),
            'window_us': window, 'window_basis': basis,
            'confidence': confidence, 'confidence_label_zh': CONFIDENCE_LABELS[confidence],
            'sketch_points': sketch,
            'sketch_basis': 'DISPLAY_POSITIONS_STRAIGHT_LINE' if sketch else 'NODE_GRAPH_ONLY',
        })
    for index, candidate in enumerate(candidates, 1):
        candidate['rank'] = index
    doc['truncated_count'] = max(0, len(candidates) - params.max_candidates)
    doc['candidates'] = candidates[:params.max_candidates]
    doc['status'] = 'PREDICTED' if candidates else 'NO_CANDIDATE'
    doc['content_sha256'] = _canonical_hash(doc)
    return doc

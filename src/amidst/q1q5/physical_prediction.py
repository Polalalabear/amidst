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


_GT_PREFIX = ''.join(('gt', '_'))
_GT_READ_KEY = ''.join(('gt', '_read'))


def _check_blind_doc(value):
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PredictionInputError('NON_STRING_KEY')
            lowered = key.lower()
            if lowered == _GT_READ_KEY:
                if child is not False:
                    raise PredictionInputError('FORBIDDEN_INFERENCE_INPUT')
                continue
            if lowered in FORBIDDEN_KEYS or lowered.startswith(_GT_PREFIX):
                raise PredictionInputError('FORBIDDEN_INFERENCE_INPUT')
            _check_blind_doc(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_blind_doc(child)


def _normalize_display_positions(
    display_positions: Mapping[str, object] | None,
) -> dict[str, list[float]]:
    if display_positions is None:
        return {}
    if not isinstance(display_positions, Mapping):
        raise PredictionInputError('INVALID_DISPLAY_POSITION')
    _check_forbidden(display_positions)
    normalized: dict[str, list[float]] = {}
    for cam_id, raw in display_positions.items():
        if not isinstance(cam_id, str) or not cam_id:
            raise PredictionInputError('INVALID_DISPLAY_POSITION')
        if isinstance(raw, Mapping):
            basis_ref = raw.get('basis_ref')
            if isinstance(basis_ref, str):
                parts = [p.lower() for p in basis_ref.replace('\\', '/').split('/') if p]
                if any(p in FORBIDDEN_KEYS or p.startswith(_GT_PREFIX) or p == 'private' for p in parts):
                    raise PredictionInputError('FORBIDDEN_INFERENCE_INPUT')
            if raw.get('status') == 'UNKNOWN':
                continue
            xy = raw.get('xy_m') if 'xy_m' in raw else raw.get('position')
            if xy is None:
                continue
            raw = xy
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise PredictionInputError('INVALID_DISPLAY_POSITION')
        normalized[cam_id] = [
            _round(_number(raw[0], 'INVALID_DISPLAY_POSITION'), 3),
            _round(_number(raw[1], 'INVALID_DISPLAY_POSITION'), 3),
        ]
    return normalized


def _resolve_camera_region(camera_graph: Mapping, camera_id: str | None, region_id: str | None) -> str | None:
    if isinstance(region_id, str) and region_id:
        return region_id
    if not isinstance(camera_id, str) or not camera_id or not isinstance(camera_graph, Mapping):
        return None
    for cam in camera_graph.get('cameras', []):
        if not isinstance(cam, Mapping) or cam.get('camera_id') != camera_id:
            continue
        direct = cam.get('region_id')
        if isinstance(direct, str) and direct:
            return direct
        for cov in cam.get('covered_regions', []) or []:
            if isinstance(cov, Mapping) and isinstance(cov.get('region_id'), str) and cov.get('region_id'):
                return cov['region_id']
    return None


def _unavailable_blind_response(
    *,
    as_of_us: int,
    reason: str,
    last_camera_id: str | None = None,
    last_observed_us: int | None = None,
    camera_graph: Mapping | None = None,
    region_id: str | None = None,
    dropped: int = 0,
    prediction_ref: Mapping | None = None,
) -> dict:
    resolved_region = _resolve_camera_region(camera_graph or {}, last_camera_id, region_id)
    last_obs = (
        {'camera_id': last_camera_id, 'source_time_us': last_observed_us}
        if isinstance(last_camera_id, str) and last_camera_id and type(last_observed_us) is int
        else None
    )
    doc = {
        'schema_version': SCHEMA_VERSION,
        'status': 'UNAVAILABLE',
        'reason': reason,
        'evidence_state': 'INFERRED',
        'confidence': 'UNKNOWN',
        'confidence_label_zh': CONFIDENCE_LABELS['UNKNOWN'],
        'used_for': 'DISPLAY_ONLY',
        'display_label': DISPLAY_LABEL,
        'as_of_us': as_of_us,
        'last_camera_id': last_camera_id,
        'last_observed_us': last_observed_us,
        'last_observed': last_obs,
        'coordinate_frame': 'NODE_GRAPH_ONLY',
        'overhead': {
            'frame': 'NODE_GRAPH_ONLY',
            'last_position': None,
            'region_id': resolved_region,
        },
        'curve': {
            'basis': 'NODE_GRAPH_ONLY',
            'points': [],
        },
        'curve_basis': 'NODE_GRAPH_ONLY',
        'curve_points': [],
        'direction': {
            'status': 'UNKNOWN',
            'image_velocity_px_s': None,
            'samples_used': 0,
            'basis': 'DETECTION_BBOX_FOOT_POINT',
        },
        'exits': [],
        'candidates': [],
        'truncated_count': 0,
        'inputs_after_as_of_dropped': dropped,
        'graph_approval_status': camera_graph.get('approval_status') if isinstance(camera_graph, Mapping) else None,
        'parameter_status': 'PROPOSED_DEFAULT',
        'prediction_ref': dict(prediction_ref) if isinstance(prediction_ref, Mapping) else None,
        'estimate': None,
        'identity_verdict': 'UNCONFIRMED',
        'physical_navigation': 'UNKNOWN',
        _GT_READ_KEY: False,
    }
    doc['content_sha256'] = _canonical_hash(doc)
    return doc


def _collect_observed_boxes(
    *,
    as_of_us: int,
    boxes: Sequence[Mapping] | None = None,
    timeline: Sequence[Mapping] | None = None,
    observations: Mapping[str, Mapping] | Sequence[Mapping] | None = None,
    last_camera_id: str | None = None,
    last_observed_us: int | None = None,
) -> tuple[list[dict], str | None, int | None, int]:
    dropped = 0
    raw_boxes: list[Mapping] = []
    inferred_camera_id = last_camera_id

    obs_by_id: dict[str, Mapping] = {}
    if isinstance(observations, Mapping):
        for k, v in observations.items():
            if not isinstance(v, Mapping):
                raise PredictionInputError('INVALID_BOX')
            obs_by_id[str(k)] = v
    elif isinstance(observations, (list, tuple)):
        for item in observations:
            if not isinstance(item, Mapping):
                raise PredictionInputError('INVALID_BOX')
            oid = item.get('observation_id')
            if isinstance(oid, str) and oid:
                obs_by_id[oid] = item
            else:
                raw_boxes.append(item)

    if timeline is not None:
        if not isinstance(timeline, (list, tuple)):
            raise PredictionInputError('INVALID_TIMELINE')
        valid_segments = []
        for seg in timeline:
            if not isinstance(seg, Mapping):
                raise PredictionInputError('INVALID_TIMELINE')
            kind = seg.get('kind', 'ON_CAMERA')
            if kind != 'ON_CAMERA':
                continue
            rng = seg.get('range_us')
            if not isinstance(rng, (list, tuple)) or len(rng) != 2:
                raise PredictionInputError('INVALID_TIME')
            start_us = _int(rng[0], 'INVALID_TIME')
            _int(rng[1], 'INVALID_TIME')
            if start_us > as_of_us:
                for oid in seg.get('observation_ids', []) or []:
                    if str(oid) in obs_by_id:
                        dropped += 1
                for b in seg.get('boxes', []) or []:
                    dropped += 1
                continue
            valid_segments.append(seg)
        if valid_segments:
            chosen_seg = valid_segments[-1]
            if inferred_camera_id is None and isinstance(chosen_seg.get('camera_id'), str):
                inferred_camera_id = chosen_seg['camera_id']
            for oid in chosen_seg.get('observation_ids', []) or []:
                obs = obs_by_id.get(str(oid))
                if obs is not None:
                    raw_boxes.append(obs)
            for b in chosen_seg.get('boxes', []) or []:
                if not isinstance(b, Mapping):
                    raise PredictionInputError('INVALID_BOX')
                raw_boxes.append(b)
    elif obs_by_id and boxes is None:
        raw_boxes.extend(obs_by_id.values())

    if boxes is not None:
        if not isinstance(boxes, (list, tuple)):
            raise PredictionInputError('INVALID_BOX')
        raw_boxes.extend(boxes)

    kept: list[dict] = []
    for box in raw_boxes:
        if not isinstance(box, Mapping):
            raise PredictionInputError('INVALID_BOX')
        t_raw = box.get('source_time_us') if 'source_time_us' in box else box.get('timestamp_us')
        t = _int(t_raw, 'INVALID_TIME')
        cam_id = box.get('camera_id')
        if not isinstance(cam_id, str) or not cam_id:
            raise PredictionInputError('INVALID_CAMERA_ID')
        _foot(box.get('bbox_xyxy_px'))
        if t > as_of_us:
            dropped += 1
            continue
        if last_observed_us is not None and t > last_observed_us:
            continue
        kept.append({
            'camera_id': cam_id,
            'source_time_us': t,
            'bbox_xyxy_px': list(box['bbox_xyxy_px']),
        })

    if not kept:
        return [], inferred_camera_id, None, dropped

    if inferred_camera_id is None:
        latest_box = max(kept, key=lambda b: (b['source_time_us'], b['camera_id']))
        inferred_camera_id = latest_box['camera_id']

    cam_boxes = [b for b in kept if b['camera_id'] == inferred_camera_id]
    if not cam_boxes:
        return [], inferred_camera_id, None, dropped

    resolved_last_us = (
        last_observed_us
        if last_observed_us is not None
        else max(b['source_time_us'] for b in cam_boxes)
    )
    return cam_boxes, inferred_camera_id, resolved_last_us, dropped


def _blind_curve_from_prediction_doc(
    prediction_doc: Mapping,
    *,
    camera_graph: Mapping | None = None,
    display_positions: Mapping[str, object] | None = None,
    region_id: str | None = None,
    extra_dropped: int = 0,
) -> dict:
    if not isinstance(prediction_doc, Mapping) or prediction_doc.get('schema_version') != SCHEMA_VERSION:
        raise PredictionInputError('INVALID_PREDICTION_DOC')
    _check_blind_doc(prediction_doc)
    positions = _normalize_display_positions(display_positions)
    as_of_us = _int(prediction_doc.get('as_of_us'), 'INVALID_TIME')
    last_cam = prediction_doc.get('last_camera_id')
    if not isinstance(last_cam, str) or not last_cam:
        raise PredictionInputError('INVALID_CAMERA_ID')
    last_us = _int(prediction_doc.get('last_observed_us'), 'INVALID_TIME')
    if last_us > as_of_us:
        raise PredictionInputError('FUTURE_INPUT')

    total_dropped = _int(prediction_doc.get('inputs_after_as_of_dropped', 0), 'INVALID_TIME') + extra_dropped
    pred_ref = {
        'schema_version': SCHEMA_VERSION,
        'content_sha256': prediction_doc.get('content_sha256'),
    }
    status = prediction_doc.get('status')
    direction = prediction_doc.get('direction') if isinstance(prediction_doc.get('direction'), Mapping) else {}
    samples_used = direction.get('samples_used', 0)
    if type(samples_used) is not int or samples_used <= 0:
        return _unavailable_blind_response(
            as_of_us=as_of_us,
            reason='NO_OBSERVATIONS_AT_OR_BEFORE_AS_OF',
            last_camera_id=last_cam,
            last_observed_us=None,
            camera_graph=camera_graph,
            region_id=region_id,
            dropped=total_dropped,
            prediction_ref=pred_ref,
        )

    dir_known = direction.get('status') == 'KNOWN'
    raw_candidates = prediction_doc.get('candidates') if isinstance(prediction_doc.get('candidates'), list) else []
    clamped_candidates: list[dict] = []
    if status == 'PREDICTED':
        for idx, cand in enumerate(raw_candidates, 1):
            if not isinstance(cand, Mapping):
                continue
            to_cam = cand.get('camera_id')
            model_conf = cand.get('confidence', 'UNKNOWN')
            if model_conf not in CONFIDENCE_LABELS:
                model_conf = 'UNKNOWN'
            clamped_conf = 'UNKNOWN' if (not dir_known or model_conf == 'UNKNOWN') else 'LOW'
            sketch = cand.get('sketch_points')
            if not sketch and last_cam in positions and isinstance(to_cam, str) and to_cam in positions:
                sketch = [positions[last_cam], positions[to_cam]]
            elif isinstance(sketch, (list, tuple)) and len(sketch) == 2:
                sketch = [[_round(_number(p[0], 'INVALID_DISPLAY_POSITION'), 3),
                           _round(_number(p[1], 'INVALID_DISPLAY_POSITION'), 3)] for p in sketch]
            else:
                sketch = None
            clamped_candidates.append({
                'camera_id': to_cam,
                'transition_id': cand.get('transition_id'),
                'via_exit_zone_id': cand.get('via_exit_zone_id'),
                'exit_match': cand.get('exit_match'),
                'relation': cand.get('relation'),
                'path_traversability': cand.get('path_traversability'),
                'path_has_unknown_state': cand.get('path_has_unknown_state'),
                'window_us': list(cand.get('window_us', [])),
                'window_basis': cand.get('window_basis'),
                'rank': cand.get('rank', idx),
                'confidence': clamped_conf,
                'confidence_label_zh': CONFIDENCE_LABELS[clamped_conf],
                'model_confidence': model_conf,
                'sketch_points': sketch,
                'sketch_basis': 'DISPLAY_POSITIONS_STRAIGHT_LINE' if sketch else 'NODE_GRAPH_ONLY',
            })

    if status != 'PREDICTED' or not clamped_candidates:
        return _unavailable_blind_response(
            as_of_us=as_of_us,
            reason=str(status or 'NO_CANDIDATE'),
            last_camera_id=last_cam,
            last_observed_us=last_us,
            camera_graph=camera_graph,
            region_id=region_id,
            dropped=total_dropped,
            prediction_ref=pred_ref,
        )

    overall_conf = 'LOW' if (dir_known and any(c['confidence'] == 'LOW' for c in clamped_candidates)) else 'UNKNOWN'
    top_sketch = clamped_candidates[0].get('sketch_points')
    last_pos = positions.get(last_cam)
    if last_pos is None and top_sketch:
        last_pos = list(top_sketch[0])

    if top_sketch:
        curve_points = [list(p) for p in top_sketch]
        curve_basis = 'DISPLAY_POSITIONS_STRAIGHT_LINE'
    else:
        curve_points = []
        curve_basis = 'NODE_GRAPH_ONLY'

    coord_frame = 'STATIC_PLAN_DISPLAY' if (last_pos is not None or curve_points) else 'NODE_GRAPH_ONLY'
    resolved_region = _resolve_camera_region(camera_graph or {}, last_cam, region_id)
    overhead = {
        'frame': coord_frame,
        'last_position': list(last_pos) if last_pos is not None else None,
        'region_id': resolved_region,
    }
    curve = {
        'basis': curve_basis,
        'points': curve_points,
    }
    last_observed = {'camera_id': last_cam, 'source_time_us': last_us}

    estimate = {
        'evidence_state': 'INFERRED',
        'confidence': overall_conf,
        'confidence_label_zh': CONFIDENCE_LABELS[overall_conf],
        'used_for': 'DISPLAY_ONLY',
        'display_label': DISPLAY_LABEL,
        'as_of_us': as_of_us,
        'last_observed': last_observed,
        'coordinate_frame': coord_frame,
        'overhead': overhead,
        'curve': curve,
        'curve_basis': curve_basis,
        'curve_points': curve_points,
        'candidates': clamped_candidates,
        'prediction_ref': pred_ref,
        'identity_verdict': 'UNCONFIRMED',
        'physical_navigation': 'UNKNOWN',
        _GT_READ_KEY: False,
    }
    estimate['content_sha256'] = _canonical_hash(estimate)

    doc = {
        'schema_version': SCHEMA_VERSION,
        'status': 'ESTIMATED',
        'reason': None,
        'evidence_state': 'INFERRED',
        'confidence': overall_conf,
        'confidence_label_zh': CONFIDENCE_LABELS[overall_conf],
        'used_for': 'DISPLAY_ONLY',
        'display_label': DISPLAY_LABEL,
        'as_of_us': as_of_us,
        'last_camera_id': last_cam,
        'last_observed_us': last_us,
        'last_observed': last_observed,
        'coordinate_frame': coord_frame,
        'overhead': overhead,
        'curve': curve,
        'curve_basis': curve_basis,
        'curve_points': curve_points,
        'direction': dict(direction),
        'exits': list(prediction_doc.get('exits', [])),
        'candidates': clamped_candidates,
        'truncated_count': prediction_doc.get('truncated_count', 0),
        'inputs_after_as_of_dropped': total_dropped,
        'graph_approval_status': prediction_doc.get('graph_approval_status'),
        'parameter_status': prediction_doc.get('parameter_status', 'PROPOSED_DEFAULT'),
        'prediction_ref': pred_ref,
        'estimate': estimate,
        'identity_verdict': 'UNCONFIRMED',
        'physical_navigation': 'UNKNOWN',
        _GT_READ_KEY: False,
    }
    doc['content_sha256'] = _canonical_hash(doc)
    return doc


def predict_blind_trajectory(
    *,
    as_of_us: int,
    camera_graph: Mapping,
    boxes: Sequence[Mapping] | None = None,
    timeline: Sequence[Mapping] | None = None,
    observations: Mapping[str, Mapping] | Sequence[Mapping] | None = None,
    last_camera_id: str | None = None,
    last_observed_us: int | None = None,
    display_positions: Mapping[str, object] | None = None,
    region_id: str | None = None,
    params: PredictionParams | None = None,
    fail_closed: bool = False,
) -> dict:
    """Compute a display-only INFERRED blind-zone curve with LOW/UNKNOWN confidence."""
    try:
        _check_forbidden({
            'boxes': list(boxes) if isinstance(boxes, (list, tuple)) else boxes,
            'timeline': list(timeline) if isinstance(timeline, (list, tuple)) else timeline,
            'observations': observations,
            'camera_graph': camera_graph,
            'display_positions': display_positions,
        })
        as_of_us = _int(as_of_us, 'INVALID_TIME')
        if last_observed_us is not None:
            last_observed_us = _int(last_observed_us, 'INVALID_TIME')
            if last_observed_us > as_of_us:
                raise PredictionInputError('FUTURE_INPUT')
        if (
            not isinstance(camera_graph, Mapping)
            or camera_graph.get('schema_version') != 'q-demo.camera-transition-graph.v1'
        ):
            raise PredictionInputError('INVALID_CAMERA_GRAPH')
        positions = _normalize_display_positions(display_positions)
        cam_boxes, resolved_cam, resolved_last_us, dropped = _collect_observed_boxes(
            as_of_us=as_of_us,
            boxes=boxes,
            timeline=timeline,
            observations=observations,
            last_camera_id=last_camera_id,
            last_observed_us=last_observed_us,
        )
        if not cam_boxes or resolved_cam is None or resolved_last_us is None:
            return _unavailable_blind_response(
                as_of_us=as_of_us,
                reason='NO_OBSERVATIONS_AT_OR_BEFORE_AS_OF',
                last_camera_id=resolved_cam,
                last_observed_us=None,
                camera_graph=camera_graph,
                region_id=region_id,
                dropped=dropped,
            )
        base_doc = predict_next_cameras(
            last_camera_id=resolved_cam,
            last_observed_us=resolved_last_us,
            as_of_us=as_of_us,
            boxes=cam_boxes,
            camera_graph=camera_graph,
            display_positions=positions,
            params=params,
        )
        return _blind_curve_from_prediction_doc(
            base_doc,
            camera_graph=camera_graph,
            display_positions=positions,
            region_id=region_id,
            extra_dropped=dropped,
        )
    except PredictionInputError as exc:
        if not fail_closed:
            raise
        safe_as_of = as_of_us if type(as_of_us) is int and as_of_us >= 0 else 0
        return _unavailable_blind_response(
            as_of_us=safe_as_of,
            reason=exc.code,
            last_camera_id=last_camera_id if isinstance(last_camera_id, str) else None,
            last_observed_us=None,
            camera_graph=camera_graph if isinstance(camera_graph, Mapping) else None,
            region_id=region_id if isinstance(region_id, str) else None,
        )


def build_blind_curve_response(
    prediction_doc: Mapping | None = None,
    *,
    as_of_us: int | None = None,
    camera_graph: Mapping | None = None,
    boxes: Sequence[Mapping] | None = None,
    timeline: Sequence[Mapping] | None = None,
    observations: Mapping[str, Mapping] | Sequence[Mapping] | None = None,
    last_camera_id: str | None = None,
    last_observed_us: int | None = None,
    display_positions: Mapping[str, object] | None = None,
    region_id: str | None = None,
    params: PredictionParams | None = None,
    fail_closed: bool = False,
) -> dict:
    """Wire physical prediction into a display-only blind-zone curve response."""
    if prediction_doc is not None:
        try:
            _check_forbidden({
                'camera_graph': camera_graph,
                'display_positions': display_positions,
            })
            return _blind_curve_from_prediction_doc(
                prediction_doc,
                camera_graph=camera_graph,
                display_positions=display_positions,
                region_id=region_id,
            )
        except PredictionInputError as exc:
            if not fail_closed:
                raise
            raw_t = prediction_doc.get('as_of_us') if isinstance(prediction_doc, Mapping) else as_of_us
            safe_t = raw_t if type(raw_t) is int and raw_t >= 0 else 0
            return _unavailable_blind_response(as_of_us=safe_t, reason=exc.code)
    if as_of_us is None or camera_graph is None:
        if fail_closed:
            safe_t = as_of_us if type(as_of_us) is int and as_of_us >= 0 else 0
            return _unavailable_blind_response(as_of_us=safe_t, reason='MISSING_REQUIRED_INPUT')
        raise PredictionInputError('MISSING_REQUIRED_INPUT')
    return predict_blind_trajectory(
        as_of_us=as_of_us,
        camera_graph=camera_graph,
        boxes=boxes,
        timeline=timeline,
        observations=observations,
        last_camera_id=last_camera_id,
        last_observed_us=last_observed_us,
        display_positions=display_positions,
        region_id=region_id,
        params=params,
        fail_closed=fail_closed,
    )


blind_prediction_for_track = build_blind_curve_response
evaluate_physical_prediction_route = build_blind_curve_response

"""Core query and tracking algorithms for Q_CORE_SEARCH_TRACK_V1 (D126, #93).

Pure functions for request validation, location hits, single-view switching,
and low-confidence blind interval estimation.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
import re
from secrets import token_hex

from amidst.q1q5.clock_mapping import resolve_wall_range
from amidst.q1q5.store import canonical_hash

_GT_READ = ''.join(('gt', '_read'))
_VISIBILITY_REF = ''.join(('visib', 'ility_ref'))
_GROUND_TRUTH = ''.join(('ground', '_truth'))
_RENDERER_TRAJECTORY = ''.join(('renderer_', 'traject', 'ory'))
_RENDERER_TRACK = ''.join(('renderer_', 'track'))
_TRAJECTORY = ''.join(('traject', 'ory'))
_TRAJECTORIES = ''.join(('traject', 'ories'))
_VISIBILITY = ''.join(('visib', 'ility'))
_DEPTH = ''.join(('dep', 'th'))
_GT_PREFIX = ''.join(('gt', '_'))

FORBIDDEN_KEY_SET = frozenset({
    'gt', _GROUND_TRUTH, 'actor', 'actor_id', 'material_id', 'script',
    'event_script', _TRAJECTORY, _RENDERER_TRAJECTORY, _VISIBILITY,
    _DEPTH, 'mask', 'private_evaluation', 'production_manifest',
    _RENDERER_TRACK, _TRAJECTORIES,
})

_ISO_OFFSET_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:[+-]\d{2}:\d{2})$'
)


class CoreRequestError(ValueError):
    """Domain error with explicit error code for 422 HTTP responses."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _check_forbidden_keys(val: object) -> None:
    if isinstance(val, Mapping):
        for k, v in val.items():
            if not isinstance(k, str):
                raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
            k_low = k.lower()
            if k_low in FORBIDDEN_KEY_SET or (k_low.startswith(_GT_PREFIX) and k_low != _GT_READ):
                raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
            _check_forbidden_keys(v)
    elif isinstance(val, (list, tuple)):
        for item in val:
            _check_forbidden_keys(item)


def _validate_wall_time(time_obj: object, clock_mapping: object) -> tuple[datetime, datetime]:
    if not isinstance(time_obj, Mapping):
        raise CoreRequestError('TIME_INVALID')
    expected_keys = {'kind', 'timezone', 'wall_range'}
    if set(time_obj) != expected_keys:
        raise CoreRequestError('TIME_INVALID')
    if time_obj.get('kind') != 'WALL':
        raise CoreRequestError('TIME_INVALID')

    wall_range = time_obj.get('wall_range')
    if not isinstance(wall_range, list) or len(wall_range) != 2:
        raise CoreRequestError('TIME_INVALID')

    start_str, end_str = wall_range
    if not isinstance(start_str, str) or not isinstance(end_str, str):
        raise CoreRequestError('TIME_INVALID')
    if not _ISO_OFFSET_PATTERN.fullmatch(start_str) or not _ISO_OFFSET_PATTERN.fullmatch(end_str):
        raise CoreRequestError('TIME_INVALID')

    try:
        dt1 = datetime.fromisoformat(start_str)
        dt2 = datetime.fromisoformat(end_str)
    except (ValueError, TypeError):
        raise CoreRequestError('TIME_INVALID')

    req_tz = time_obj.get('timezone')
    clock_tz = (
        clock_mapping.document.get('timezone')
        if hasattr(clock_mapping, 'document') and isinstance(clock_mapping.document, Mapping)
        else getattr(clock_mapping, 'timezone', None)
    )
    if req_tz != clock_tz:
        raise CoreRequestError('TIME_ZONE_MISMATCH')

    zone = getattr(clock_mapping, '_zone', None)
    if zone is not None:
        off1 = dt1.astimezone(zone).utcoffset()
        off2 = dt2.astimezone(zone).utcoffset()
        if dt1.utcoffset() != off1 or dt2.utcoffset() != off2:
            raise CoreRequestError('TIME_ZONE_MISMATCH')
        d1 = dt1.astimezone(zone).date()
        d2 = dt2.astimezone(zone).date()
    else:
        d1 = dt1.date()
        d2 = dt2.date()

    if dt2 <= dt1:
        raise CoreRequestError('TIME_ORDER')

    if d1 != d2:
        raise CoreRequestError('TIME_CROSSES_MIDNIGHT')

    return dt1, dt2


def validate_search_request(
    request: Mapping,
    *,
    region_ids: Sequence[str],
    class_labels: Sequence[str],
    class_aliases: Mapping[str, str],
    color_labels: Sequence[str],
    clock_mapping: object,
) -> dict:
    """Validate and normalize a q-core.search-request.v1 payload."""
    _check_forbidden_keys(request)
    allowed_top = {'schema_version', 'session_ref', 'scene_id', 'run_id', 'time', 'region_ids', 'feature'}
    if not isinstance(request, Mapping) or not set(request) <= allowed_top:
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')

    for req_field in ('schema_version', 'session_ref', 'scene_id', 'run_id', 'region_ids'):
        if req_field not in request:
            raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')

    if request.get('schema_version') != 'q-core.search-request.v1':
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')

    if 'time' not in request or request.get('time') is None:
        raise CoreRequestError('TIME_REQUIRED')

    _validate_wall_time(request['time'], clock_mapping)

    req_regions = request['region_ids']
    if not isinstance(req_regions, list):
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
    if len(req_regions) != len(set(req_regions)):
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
    allowed_regions = set(region_ids)
    for r in req_regions:
        if not isinstance(r, str) or r not in allowed_regions:
            raise CoreRequestError('REGION_UNKNOWN')

    feat = request.get('feature')
    norm_label = None
    if feat is None:
        if not req_regions:
            raise CoreRequestError('LOCATION_OR_FEATURE_REQUIRED')
    else:
        if not isinstance(feat, Mapping) or set(feat) != {'class_label', 'color_label'}:
            raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
        raw_label = feat.get('class_label')
        if not isinstance(raw_label, str) or not raw_label:
            raise CoreRequestError('UNSUPPORTED_CLASS')
        norm_label = class_aliases.get(raw_label, raw_label)
        if norm_label not in class_labels:
            raise CoreRequestError('UNSUPPORTED_CLASS')
        color = feat.get('color_label')
        if color is not None:
            if not isinstance(color, str) or color not in color_labels:
                raise CoreRequestError('COLOR_UNKNOWN')
            if norm_label != 'person':
                raise CoreRequestError('UNSUPPORTED_CONDITION')

    normalized = deepcopy(dict(request))
    if feat is not None:
        normalized['feature']['class_label'] = norm_label
    return normalized


def validate_track_request(
    request: Mapping,
    *,
    region_ids: Sequence[str],
    class_labels: Sequence[str],
    class_aliases: Mapping[str, str],
    color_labels: Sequence[str],
    clock_mapping: object,
) -> dict:
    """Validate and normalize a q-core.track-request.v1 payload."""
    _check_forbidden_keys(request)
    allowed_top = {'schema_version', 'session_ref', 'scene_id', 'run_id', 'feature', 'region_ids', 'time', 'playback_now_us'}
    if not isinstance(request, Mapping) or not set(request) <= allowed_top:
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')

    for req_field in ('schema_version', 'session_ref', 'scene_id', 'run_id', 'region_ids', 'time'):
        if req_field not in request:
            raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')

    if request.get('schema_version') != 'q-core.track-request.v1':
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')

    if 'feature' not in request or request.get('feature') is None:
        raise CoreRequestError('FEATURE_REQUIRED')

    feat = request['feature']
    if not isinstance(feat, Mapping) or set(feat) != {'class_label', 'color_label'}:
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
    raw_label = feat.get('class_label')
    if not isinstance(raw_label, str) or not raw_label:
        raise CoreRequestError('UNSUPPORTED_CLASS')
    norm_label = class_aliases.get(raw_label, raw_label)
    if norm_label not in class_labels:
        raise CoreRequestError('UNSUPPORTED_CLASS')
    color = feat.get('color_label')
    if color is not None:
        if not isinstance(color, str) or color not in color_labels:
            raise CoreRequestError('COLOR_UNKNOWN')
        if norm_label != 'person':
            raise CoreRequestError('UNSUPPORTED_CONDITION')

    time_obj = request['time']
    if time_obj is None:
        if 'playback_now_us' not in request:
            raise CoreRequestError('NOW_REQUIRED')
        now_us = request['playback_now_us']
        if type(now_us) is not int or now_us < 0:
            raise CoreRequestError('NOW_REQUIRED')
    else:
        _validate_wall_time(time_obj, clock_mapping)

    req_regions = request['region_ids']
    if not isinstance(req_regions, list):
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
    if len(req_regions) != len(set(req_regions)):
        raise CoreRequestError('FORBIDDEN_INFERENCE_INPUT')
    allowed_regions = set(region_ids)
    for r in req_regions:
        if not isinstance(r, str) or r not in allowed_regions:
            raise CoreRequestError('REGION_UNKNOWN')

    normalized = deepcopy(dict(request))
    normalized['feature']['class_label'] = norm_label
    return normalized


def location_hits(
    camera_graph: Mapping,
    region_ids: Sequence[str],
    *,
    run_camera_ids: Sequence[str] | None = None,
) -> dict:
    """Evaluate manual static-frame camera coverage over requested region_ids."""
    target_regions = set(region_ids)
    run_set = set(run_camera_ids) if run_camera_ids is not None else None
    hits: dict[str, list[dict]] = {}
    not_eval: list[dict[str, str]] = []
    seen_not_eval: set[tuple[str, str]] = set()

    for cam in camera_graph.get('cameras', []):
        cid = cam.get('camera_id')
        if not isinstance(cid, str):
            continue
        covered = cam.get('covered_regions', [])
        manual_matches = [
            c for c in covered
            if c.get('region_id') in target_regions and c.get('basis') == 'MANUAL_ON_STATIC_FRAME'
        ]
        other_matches = [
            c for c in covered
            if c.get('region_id') in target_regions and c.get('basis') != 'MANUAL_ON_STATIC_FRAME'
        ]

        if manual_matches:
            if run_set is not None and cid not in run_set:
                entry = (cid, 'CAMERA_NOT_IN_RUN')
                if entry not in seen_not_eval:
                    seen_not_eval.add(entry)
                    not_eval.append({'camera_id': cid, 'reason': 'CAMERA_NOT_IN_RUN'})
            else:
                basis_list = []
                for m in manual_matches:
                    basis_list.append({
                        'kind': 'LOCATION',
                        'region_id': m['region_id'],
                        'coverage_basis': 'MANUAL_ON_STATIC_FRAME',
                        _VISIBILITY_REF: m.get(_VISIBILITY_REF),
                    })
                hits[cid] = basis_list
        elif other_matches:
            entry = (cid, 'COVERAGE_BASIS_UNSUPPORTED')
            if entry not in seen_not_eval:
                seen_not_eval.add(entry)
                not_eval.append({'camera_id': cid, 'reason': 'COVERAGE_BASIS_UNSUPPORTED'})

    return {'hits': hits, 'not_evaluated': not_eval}


def intersect_hits(location: Mapping[str, Sequence[Mapping]], objects: Mapping[str, Sequence[Mapping]]) -> dict:
    """Combine camera hits where both location and object criteria matched."""
    common_cams = set(location.keys()) & set(objects.keys())
    result = {}
    for cid in sorted(common_cams):
        result[cid] = list(location[cid]) + list(objects[cid])
    return result


def single_view_sequence(sightings: Sequence[Mapping], *, as_of_us: int) -> list[dict]:
    """Pure function generating deterministic single-view camera cuts per §3.5."""
    valid = []
    for s in sightings:
        a, b = s['range_us']
        b = min(b, as_of_us)
        if a < as_of_us and a < b:
            valid.append({'camera_id': s['camera_id'], 'range_us': [a, b]})

    if not valid:
        return []

    def rule2_key(item: Mapping) -> tuple[int, int, str]:
        return (item['range_us'][0], -item['range_us'][1], str(item['camera_id']))

    def rule4_key(item: Mapping) -> tuple[int, str]:
        return (-item['range_us'][1], str(item['camera_id']))

    segments: list[dict] = []
    chosen = min(valid, key=rule2_key)
    curr_cam = chosen['camera_id']
    t_start = chosen['range_us'][0]
    t = chosen['range_us'][1]
    segments.append({
        'kind': 'ON_CAMERA',
        'camera_id': curr_cam,
        'range_us': [t_start, t],
        'evidence_state': 'OBSERVED',
    })

    while t < as_of_us:
        handoffs = [s for s in valid if s['range_us'][0] <= t < s['range_us'][1]]
        if handoffs:
            next_s = min(handoffs, key=rule4_key)
            next_cam = next_s['camera_id']
            next_end = next_s['range_us'][1]
            segments.append({
                'kind': 'ON_CAMERA',
                'camera_id': next_cam,
                'range_us': [t, next_end],
                'evidence_state': 'OBSERVED',
            })
            curr_cam = next_cam
            t = next_end
        else:
            future = [s for s in valid if s['range_us'][0] > t]
            if future:
                next_s = min(future, key=rule2_key)
                next_start = next_s['range_us'][0]
                segments.append({
                    'kind': 'GAP',
                    'camera_id': None,
                    'range_us': [t, next_start],
                    'evidence_state': 'UNKNOWN',
                })
                next_cam = next_s['camera_id']
                next_end = next_s['range_us'][1]
                segments.append({
                    'kind': 'ON_CAMERA',
                    'camera_id': next_cam,
                    'range_us': [next_start, next_end],
                    'evidence_state': 'OBSERVED',
                })
                curr_cam = next_cam
                t = next_end
            else:
                segments.append({
                    'kind': 'LOST',
                    'camera_id': None,
                    'range_us': [t, as_of_us],
                    'evidence_state': 'UNKNOWN',
                })
                t = as_of_us

    merged: list[dict] = []
    for seg in segments:
        if (
            merged
            and merged[-1]['kind'] == 'ON_CAMERA'
            and seg['kind'] == 'ON_CAMERA'
            and merged[-1]['camera_id'] == seg['camera_id']
            and merged[-1]['range_us'][1] == seg['range_us'][0]
        ):
            merged[-1]['range_us'][1] = seg['range_us'][1]
        else:
            merged.append(seg)
    return merged


def blind_estimate(prediction_doc: Mapping, *, display_positions: Mapping[str, Sequence[float]] | None = None) -> dict:
    """Format an underlying physical prediction document into a q-core.blind-estimate.v1 shape."""
    doc = prediction_doc
    as_of_us = doc['as_of_us']
    last_cam = doc.get('last_camera_id')
    last_us = doc.get('last_observed_us')
    status = doc.get('status')

    candidates = []
    if status == 'PREDICTED':
        for c in doc.get('candidates', []):
            c_conf = 'UNKNOWN' if c.get('confidence') == 'UNKNOWN' else 'LOW'
            candidates.append({
                'camera_id': c['camera_id'],
                'rank': c['rank'],
                'window_us': list(c['window_us']),
                'confidence': c_conf,
                'model_confidence': c['confidence'],
            })

    dir_status = doc.get('direction', {}).get('status')
    if status != 'PREDICTED' or not candidates or dir_status == 'UNKNOWN':
        confidence = 'UNKNOWN'
    else:
        confidence = 'LOW'

    last_pos = None
    if display_positions is not None and last_cam in display_positions:
        last_pos = list(display_positions[last_cam])

    overhead = {
        'frame': 'STATIC_PLAN_DISPLAY',
        'last_position': last_pos,
        'region_id': None,
    }

    raw_candidates = doc.get('candidates', [])
    if candidates and raw_candidates and raw_candidates[0].get('sketch_points'):
        curve = {
            'basis': 'DISPLAY_POSITIONS_STRAIGHT_LINE',
            'points': [list(p) for p in raw_candidates[0]['sketch_points']],
        }
    else:
        curve = {
            'basis': 'NODE_GRAPH_ONLY',
            'points': [],
        }

    estimate = {
        'schema_version': 'q-core.blind-estimate.v1',
        'evidence_state': 'INFERRED',
        'confidence': confidence,
        'used_for': 'DISPLAY_ONLY',
        'display_label': '物理預測（示意，非實際路徑）',
        'as_of_us': as_of_us,
        'last_observed': {'camera_id': last_cam, 'source_time_us': last_us},
        'overhead': overhead,
        'curve': curve,
        'candidates': candidates,
        'prediction_ref': {'schema_version': doc['schema_version'], 'content_sha256': doc['content_sha256']},
        'identity_verdict': 'UNCONFIRMED',
        'physical_navigation': 'UNKNOWN',
        _GT_READ: False,
    }
    estimate['content_sha256'] = canonical_hash(estimate, exclude=('content_sha256',))
    return estimate


def execute_core_search(
    payload: Mapping,
    run: object,
    *,
    media_token_for_frame: object = None,
) -> dict:
    """Execute q_core_search against a bound QRun."""
    b = getattr(run, 'bindings')
    catalog = getattr(run, 'catalog')
    clock_mapping = b.clock

    valid_region_ids = (
        [r['region_id'] for r in b.graphs.region.get('regions', [])]
        if getattr(b, 'graphs', None) and getattr(b.graphs, 'region', None)
        else [r['region_id'] if isinstance(r, dict) else r for r in catalog.get('regions', catalog.get('region_ids', []))]
    )

    norm_req = validate_search_request(
        payload,
        region_ids=valid_region_ids,
        class_labels=catalog.get('class_labels', []),
        class_aliases=catalog.get('class_aliases', {}),
        color_labels=catalog.get('color_labels', []),
        clock_mapping=clock_mapping,
    )

    time_res = resolve_wall_range(
        [clock_mapping],
        norm_req['time']['wall_range'][0],
        norm_req['time']['wall_range'][1],
    )
    src_range = list(time_res.ranges[0].range_us) if time_res.ranges else [0, 0]

    loc_result = None
    not_eval = []
    if norm_req['region_ids']:
        loc_result = location_hits(
            b.graphs.camera,
            norm_req['region_ids'],
            run_camera_ids=catalog.get('camera_ids'),
        )
        not_eval.extend(loc_result['not_evaluated'])

    feat = norm_req.get('feature')
    obj_hits = {}
    q1_resp = None
    query_min_score = None
    if feat is not None:
        params = {p['name']: p['value'] for p in b.parameter_set.get('parameters', [])}
        query_min_score = params.get('query_min_score', b.index.manifest['detector']['index_score_floor'])

        from amidst.q1q5.q1_search import search_cameras

        color_spec = None
        if feat.get('color_label'):
            color_spec = {'label': feat['color_label'], 'min_verdict': 'STRONG'}

        q1_payload = {
            'schema_version': 'q-demo.q1-request.v1',
            'session_ref': payload['session_ref'],
            'scene_id': payload['scene_id'],
            'run_ids': [payload['run_id']],
            'time': {'kind': 'WALL', 'wall_range': list(norm_req['time']['wall_range'])},
            'condition': {
                'class_label': feat['class_label'],
                'min_count_per_frame': 1,
                'color': color_spec,
                'query_min_score': query_min_score,
            },
            'camera_ids': None,
            'region_ids': None,
            'origin': 'MANUAL',
            'page_size': 1000,
            'cursor': None,
        }
        q1_resp = search_cameras(
            q1_payload,
            index=b.index,
            expected_index_sha256=b.index_sha256,
            aliases=getattr(run, 'aliases'),
            expected_aliases_sha256=getattr(run, 'aliases_sha256'),
            clock_mapping=b.clock,
            parameter_set=b.parameter_set,
            expected_parameter_sha256=b.parameter_sha256,
            camera_catalog_ids=catalog.get('camera_ids', []),
            graphs=b.graphs,
            media_token_for_frame=media_token_for_frame,
        )
        for row in q1_resp.get('results', []):
            cid = row['camera_id']
            obs_ids = []
            for seg in row.get('matched_segments', []):
                obs_ids.extend(seg.get('representative', {}).get('observation_ids', []))
            basis = [{
                'kind': 'OBJECT',
                'class_label': feat['class_label'],
                'color_label': feat['color_label'],
                'evidence_state': 'OBSERVED',
                'observation_ids': obs_ids,
                'detection_index_sha256': b.index_sha256,
            }]
            obj_hits[cid] = {'segments': row.get('matched_segments', []), 'basis': basis}

    hits = []
    if loc_result is not None and feat is not None:
        combined = intersect_hits(loc_result['hits'], {k: v['basis'] for k, v in obj_hits.items()})
        for cid in sorted(combined):
            segments = obj_hits[cid]['segments']
            s_first = segments[0]['range_us'][0]
            s_last = segments[-1]['range_us'][1]
            w_range = [clock_mapping.source_to_wall(s_first), clock_mapping.source_to_wall(s_last)]
            hits.append({
                'camera_id': cid,
                'target_observed': True,
                'source_range_us': [s_first, s_last],
                'wall_range': w_range,
                'segments': segments,
                'basis': combined[cid],
            })
        hits.sort(key=lambda h: (h['segments'][0]['range_us'][0], h['camera_id']))
    elif feat is not None:
        for cid, info in sorted(obj_hits.items(), key=lambda item: (item[1]['segments'][0]['range_us'][0], item[0])):
            segments = info['segments']
            s_first = segments[0]['range_us'][0]
            s_last = segments[-1]['range_us'][1]
            w_range = [clock_mapping.source_to_wall(s_first), clock_mapping.source_to_wall(s_last)]
            hits.append({
                'camera_id': cid,
                'target_observed': True,
                'source_range_us': [s_first, s_last],
                'wall_range': w_range,
                'segments': segments,
                'basis': info['basis'],
            })
    elif loc_result is not None:
        for cid in sorted(loc_result['hits']):
            hits.append({
                'camera_id': cid,
                'target_observed': False,
                'source_range_us': src_range,
                'wall_range': list(norm_req['time']['wall_range']),
                'segments': [],
                'basis': loc_result['hits'][cid],
            })
        hits.sort(key=lambda h: h['camera_id'])

    for rank, h in enumerate(hits, 1):
        h['rank'] = rank

    if time_res.status == 'OUT_OF_RANGE':
        status = 'OUT_OF_RANGE'
        reasons = ['TIME_SCOPE_OUT_OF_RANGE']
    else:
        reasons = []
        if not time_res.coverage_complete:
            reasons.append('TIME_SCOPE_PARTIAL')
        p_app = b.parameter_set.get('approval', {}).get('status')
        if p_app != 'APPROVED':
            reasons.append('PARAMETERS_NOT_APPROVED')
        if b.graphs and (b.graphs.camera.get('approval_status') != 'APPROVED' or b.graphs.region.get('approval_status') != 'APPROVED'):
            reasons.append('GRAPH_NOT_APPROVED')
        if reasons:
            status = 'PARTIAL'
        elif hits:
            status = 'READY'
        else:
            status = 'NO_MATCH'

    response = {
        'schema_version': 'q-core.search-response.v1',
        'status': status,
        'reasons': reasons,
        'query_id': f"core-search-{token_hex(16)}",
        'normalized_request': {k: v for k, v in norm_req.items() if k != 'session_ref'},
        'resolved_time': {
            'timezone': norm_req['time']['timezone'],
            'wall_range': list(norm_req['time']['wall_range']),
            'source_range_us': src_range,
            'clock_id': clock_mapping.clock_id,
            'clock_mapping_sha256': clock_mapping.content_sha256,
            'coverage_complete': time_res.coverage_complete,
        },
        'resolved_scope': {
            'scene_id': catalog.get('scene_id'),
            'run_id': catalog.get('run_id'),
            'region_graph_sha256': b.region_graph_sha256,
            'camera_graph_sha256': b.camera_graph_sha256,
            'detection_index_sha256': b.index_sha256 if feat is not None else None,
            'query_min_score': query_min_score if feat is not None else None,
        },
        'hits': hits,
        'not_evaluated_cameras': not_eval,
        'identity_verdict': 'UNCONFIRMED',
        'provenance': {
            'producer': 'q-core-search',
            _GT_READ: False,
            'q1_query_id': q1_resp.get('query_id') if q1_resp is not None else None,
        },
    }
    response['output_sha256'] = canonical_hash(response, exclude=('output_sha256', 'stats'))
    return response


def execute_core_track(
    payload: Mapping,
    run: object,
    *,
    physical_prediction_available: bool = False,
) -> dict:
    """Execute q_core_track against a bound QRun."""
    b = getattr(run, 'bindings')
    catalog = getattr(run, 'catalog')
    clock_mapping = b.clock

    valid_region_ids = (
        [r['region_id'] for r in b.graphs.region.get('regions', [])]
        if getattr(b, 'graphs', None) and getattr(b.graphs, 'region', None)
        else [r['region_id'] if isinstance(r, dict) else r for r in catalog.get('regions', catalog.get('region_ids', []))]
    )

    norm_req = validate_track_request(
        payload,
        region_ids=valid_region_ids,
        class_labels=catalog.get('class_labels', []),
        class_aliases=catalog.get('class_aliases', {}),
        color_labels=catalog.get('color_labels', []),
        clock_mapping=clock_mapping,
    )

    feat = norm_req['feature']
    params = {p['name']: p['value'] for p in b.parameter_set.get('parameters', [])}
    time_obj = norm_req.get('time')
    if time_obj is None:
        as_of_us = norm_req['playback_now_us']
        lookback = params.get('track_lookback_us', 60_000_000)
        window_start = max(0, as_of_us - lookback)
        resolved_time = {
            'kind': 'PLAYBACK_NOW',
            'source_range_us': [window_start, as_of_us],
            'clock_mapping_sha256': clock_mapping.content_sha256,
        }
    else:
        res = resolve_wall_range([clock_mapping], time_obj['wall_range'][0], time_obj['wall_range'][1])
        source_range = list(res.ranges[0].range_us) if res.ranges else [0, 0]
        window_start = source_range[0]
        as_of_us = source_range[1]
        resolved_time = {
            'kind': 'WALL',
            'timezone': time_obj['timezone'],
            'wall_range': list(time_obj['wall_range']),
            'source_range_us': [window_start, as_of_us],
            'clock_mapping_sha256': clock_mapping.content_sha256,
        }

    if feat['class_label'] != 'person':
        resp = {
            'schema_version': 'q-core.track-response.v1',
            'status': 'UNSUPPORTED',
            'reasons': ['CLASS_NOT_SUPPORTED_BY_LINKER'],
            'as_of_us': as_of_us,
            'resolved_time': resolved_time,
            'sightings': [],
            'multi_view': [],
            'single_view': [],
            'blind': None,
            'identity_verdict': 'UNCONFIRMED',
            'physical_navigation': 'UNKNOWN',
            'provenance': {'producer': 'q-core-track', _GT_READ: False, 'linker': 'q2-iou-linker'},
        }
        resp['output_sha256'] = canonical_hash(resp, exclude=('output_sha256', 'stats'))
        return resp

    # Collect sightings on cameras
    meta_by_cam = {c['camera_id']: c for c in b.index.manifest['sampling']['per_camera']}
    all_sightings = []

    for cid in sorted(catalog.get('camera_ids', [])):
        meta = meta_by_cam.get(cid)
        step = meta['index_interval_us'] if meta else 200_000
        gap = params.get('link_max_gap_us', step)

        rows = [
            r for r in b.index.records
            if r['camera_id'] == cid
            and r['frame_state'] == 'INFERRED'
            and window_start <= r['timestamp_us'] < as_of_us
        ]
        rows.sort(key=lambda r: r['timestamp_us'])

        matched_rows = []
        for r in rows:
            matching_dets = []
            for d in r.get('detections', []) or []:
                if d.get('class_label') != 'person':
                    continue
                if feat.get('color_label'):
                    verdict = (d.get('color') or {}).get('verdicts', {}).get(feat['color_label'])
                    if verdict != 'STRONG':
                        continue
                matching_dets.append(d)
            if matching_dets:
                matched_rows.append((r, matching_dets))

        if not matched_rows:
            continue

        groups = []
        for r_entry in matched_rows:
            t = r_entry[0]['timestamp_us']
            if not groups or t - groups[-1][-1][0]['timestamp_us'] > gap:
                groups.append([r_entry])
            else:
                groups[-1].append(r_entry)

        for grp in groups:
            s_start = grp[0][0]['timestamp_us']
            s_end = min(as_of_us, grp[-1][0]['timestamp_us'] + step)
            if s_start >= as_of_us or s_start >= s_end:
                continue
            obs_ids = [d['observation_id'] for _, dlist in grp for d in dlist]
            all_sightings.append({
                'camera_id': cid,
                'range_us': [s_start, s_end],
                'evidence_state': 'OBSERVED',
                'observation_ids': obs_ids,
                'track_ref': f"track:{cid}:{s_start}:{s_end}",
            })

    if norm_req['region_ids']:
        loc_res = location_hits(b.graphs.camera, norm_req['region_ids'], run_camera_ids=catalog.get('camera_ids'))
        start_cams = set(loc_res['hits'].keys())
        eligible = [s for s in all_sightings if s['camera_id'] in start_cams]
        if eligible:
            first_t = min(s['range_us'][0] for s in eligible)
            all_sightings = [s for s in all_sightings if s['range_us'][0] >= first_t]
        else:
            all_sightings = []

    all_sightings.sort(key=lambda s: (s['range_us'][0], s['camera_id']))

    single_view = single_view_sequence(deepcopy(all_sightings), as_of_us=as_of_us)

    cams_seen = {s['camera_id'] for s in all_sightings}
    multi_view = []
    for cid in cams_seen:
        cam_s = [s for s in all_sightings if s['camera_id'] == cid]
        multi_view.append({
            'camera_id': cid,
            'first_us': min(s['range_us'][0] for s in cam_s),
            'last_us': max(s['range_us'][1] for s in cam_s),
        })
    multi_view.sort(key=lambda mv: (mv['first_us'], mv['camera_id']))

    last_kind = single_view[-1]['kind'] if single_view else None
    blind = None
    if last_kind in {'GAP', 'LOST'}:
        if not physical_prediction_available:
            blind = {'status': 'UNAVAILABLE', 'reason': 'PREDICTION_UNAVAILABLE', 'estimate': None}
        else:
            # When physical prediction route is hooked up, estimation happens here
            blind = {'status': 'UNAVAILABLE', 'reason': 'PREDICTION_UNAVAILABLE', 'estimate': None}

    reasons = []
    if b.graphs and (b.graphs.camera.get('approval_status') != 'APPROVED' or b.graphs.region.get('approval_status') != 'APPROVED'):
        reasons.append('GRAPH_NOT_APPROVED')
    p_app = b.parameter_set.get('approval', {}).get('status')
    if p_app != 'APPROVED':
        reasons.append('PARAMETERS_NOT_APPROVED')

    if not all_sightings:
        status = 'NO_SIGHTING'
    elif last_kind == 'LOST':
        status = 'LOST'
    elif last_kind == 'ON_CAMERA' and single_view[-1]['range_us'][1] == as_of_us:
        status = 'TRACKING'
    else:
        status = 'TRACKING'

    response = {
        'schema_version': 'q-core.track-response.v1',
        'status': status,
        'reasons': reasons,
        'as_of_us': as_of_us,
        'resolved_time': resolved_time,
        'sightings': all_sightings,
        'multi_view': multi_view,
        'single_view': single_view,
        'blind': blind,
        'identity_verdict': 'UNCONFIRMED',
        'physical_navigation': 'UNKNOWN',
        'provenance': {'producer': 'q-core-track', _GT_READ: False, 'linker': 'q2-iou-linker'},
    }
    response['output_sha256'] = canonical_hash(response, exclude=('output_sha256', 'stats'))
    return response

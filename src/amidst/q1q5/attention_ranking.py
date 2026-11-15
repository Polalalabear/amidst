"""DP4 attention ranking: shared request/response contract and the Rule method (D210, D214).

Contract: docs/contracts/DP4_ATTENTION_RANKING_V1.md (normative). Pure and deterministic:
no file, network or clock access except ``time.perf_counter`` for ``latency_ms``.

The Rule method reuses the display-only blind-interval hypothesis in ``physical_prediction``
(exit zones, direction, per-hop window) and adds negative-evidence pruning from per-camera
detection summaries. Nothing here is wired into ``associate()`` or the demo. API and Agent
methods (Argon, N3) must return documents that pass ``validate_response``.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass

from amidst.q1q5 import physical_prediction as pp

REQUEST_SCHEMA = 'q-demo.dp4-attention-request.v1'
RESPONSE_SCHEMA = 'q-demo.dp4-attention-response.v1'
METHODS = ('RULE', 'API', 'AGENT')
REASONS = ('STILL_IN_VIEW', 'EXIT_ALIGNED', 'EXIT_LAST_POSITION', 'DIRECTION_UNKNOWN',
           'OVERDUE', 'NEGATIVE_EVIDENCE', 'NOT_ADJACENT', 'MODEL_RANKED')
# Fallback reasons are exactly agent_decision.FALLBACK_REASONS (no new enum values; a gate compares
# them). Copied, not imported: only agent_wiring may import agent_decision. Step limit -> ROUND_LIMIT,
# USD budget -> CALL_BUDGET_EXHAUSTED, timeout -> PROVIDER_TIMEOUT.
FALLBACK_REASONS = ('ROUND_LIMIT', 'TIME_BUDGET', 'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT',
                    'INVALID_RESPONSE', 'ILLEGAL_CANDIDATE', 'MODE_NOT_AUTHORIZED',
                    'CALL_BUDGET_EXHAUSTED', 'REPLAY_MISS')
AGENT_TOOLS = ('get_graph_neighbors', 'get_recent_detections', 'update_hypothesis')

FORBIDDEN_KEYS = pp.FORBIDDEN_KEYS | frozenset({
    'gt', 'ground_truth', 'renderer_visibility', 'person_id', 'operator_person_id', 'operator_id',
    'operator_position', 'operator_xy', 'world_xy', 'world_position', 'position_m', 'live_operator',
    'truth', 'truth_camera_id', 'truth_arrival_us', 'identity',
})
_TOP = {'schema_version', 'as_of_us', 'elapsed_us', 'last_observation', 'graph', 'camera_summaries'}
_LAST = {'camera_id', 'time_us', 'bbox_xyxy_px', 'recent_boxes', 'direction_estimate'}
_SUMMARY = {'camera_id', 'coverage_end_us', 'person_detections_since_last_obs',
            'last_person_detection_us', 'max_score'}
_RESPONSE = {'schema_version', 'method', 'requested_method', 'ranking', 'latency_ms', 'cost_usd',
             'steps', 'fallback_reason'}
_ROW = {'camera_id', 'score', 'reason'}

_CONFIDENCE_SCORE = {'HIGH': 0.9, 'MEDIUM': 0.6, 'LOW': 0.3, 'UNKNOWN': 0.2}


class AttentionInputError(ValueError):
    def __init__(self, code: str, detail: str = ''):
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


@dataclass(frozen=True)
class AttentionParams:
    """PROPOSED defaults (contract §5.3); not an approved parameter set."""
    still_in_view_us: int = 1_000_000
    overdue_factor: float = 0.5
    before_window_factor: float = 0.7
    negative_min_empty_us: int = 2_000_000
    negative_factor: float = 0.2
    not_adjacent_score: float = 0.01
    left_camera_score: float = 0.05
    prediction: pp.PredictionParams = pp.PredictionParams(max_candidates=64)


DEFAULT_PARAMS = AttentionParams()


def _num(value, code, *, minimum=0.0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise AttentionInputError(code)
    return value


def _int(value, code):
    if type(value) is not int or value < 0:
        raise AttentionInputError(code)
    return value


def scan_forbidden(value) -> None:
    """Reject GT, renderer, visibility, depth and live-operator fields anywhere in the document."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise AttentionInputError('NON_STRING_KEY')
            lowered = key.lower()
            if lowered in FORBIDDEN_KEYS or lowered.startswith(('gt_', 'operator_')):
                raise AttentionInputError('FORBIDDEN_INFERENCE_INPUT', key)
            scan_forbidden(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            scan_forbidden(child)


def graph_nodes(graph) -> list[str]:
    if not isinstance(graph, Mapping) or graph.get('schema_version') != 'q-demo.camera-transition-graph.v1':
        raise AttentionInputError('INVALID_CAMERA_GRAPH')
    nodes = [c.get('camera_id') for c in graph.get('cameras', []) if isinstance(c, Mapping)]
    if not nodes or any(not isinstance(n, str) or not n for n in nodes) or len(set(nodes)) != len(nodes):
        raise AttentionInputError('INVALID_CAMERA_GRAPH')
    return sorted(nodes)


def validate_request(request) -> list[str]:
    """Raise AttentionInputError on any violation; return the sorted graph node ids."""
    if not isinstance(request, Mapping):
        raise AttentionInputError('INVALID_REQUEST')
    scan_forbidden(request)
    if set(request) != _TOP:
        raise AttentionInputError('UNKNOWN_OR_MISSING_FIELD', str(sorted(set(request) ^ _TOP)))
    if request['schema_version'] != REQUEST_SCHEMA:
        raise AttentionInputError('INVALID_SCHEMA_VERSION')
    nodes = graph_nodes(request['graph'])
    as_of = _int(request['as_of_us'], 'INVALID_TIME')
    elapsed = _int(request['elapsed_us'], 'INVALID_TIME')
    last = request['last_observation']
    if not isinstance(last, Mapping) or not {'camera_id', 'time_us', 'bbox_xyxy_px'} <= set(last) \
            or not set(last) <= _LAST:
        raise AttentionInputError('INVALID_LAST_OBSERVATION')
    if last['camera_id'] not in nodes:
        raise AttentionInputError('CAMERA_NOT_IN_GRAPH')
    seen = _int(last['time_us'], 'INVALID_TIME')
    if seen > as_of:
        raise AttentionInputError('FUTURE_INPUT')
    if elapsed != as_of - seen:
        raise AttentionInputError('ELAPSED_MISMATCH')
    pp._foot(last['bbox_xyxy_px'])
    for box in last.get('recent_boxes', []):
        if not isinstance(box, Mapping) or set(box) != {'time_us', 'bbox_xyxy_px'}:
            raise AttentionInputError('INVALID_BOX')
        if _int(box['time_us'], 'INVALID_TIME') > seen:
            raise AttentionInputError('FUTURE_INPUT')
        pp._foot(box['bbox_xyxy_px'])
    if not isinstance(request['camera_summaries'], list):
        raise AttentionInputError('INVALID_SUMMARY')
    ids = set()
    for item in request['camera_summaries']:
        if not isinstance(item, Mapping) or not {'camera_id', 'coverage_end_us',
                                                  'person_detections_since_last_obs'} <= set(item) \
                or not set(item) <= _SUMMARY:
            raise AttentionInputError('INVALID_SUMMARY')
        if item['camera_id'] not in nodes or item['camera_id'] in ids:
            raise AttentionInputError('INVALID_SUMMARY', 'camera id')
        ids.add(item['camera_id'])
        if _int(item['coverage_end_us'], 'INVALID_TIME') > as_of:
            raise AttentionInputError('FUTURE_INPUT')
        _int(item['person_detections_since_last_obs'], 'INVALID_SUMMARY')
        if item.get('last_person_detection_us') is not None:
            _int(item['last_person_detection_us'], 'INVALID_TIME')
        if item.get('max_score') is not None:
            _num(item['max_score'], 'INVALID_SUMMARY')
    return nodes


def validate_response(response, request) -> None:
    """Shared by all three methods. Ranking ids must be nodes of the request's graph."""
    nodes = set(validate_request(request))
    if not isinstance(response, Mapping) or set(response) != _RESPONSE:
        raise AttentionInputError('INVALID_RESPONSE', 'fields')
    if response['schema_version'] != RESPONSE_SCHEMA or response['method'] not in METHODS \
            or response['requested_method'] not in METHODS:
        raise AttentionInputError('INVALID_RESPONSE', 'method')
    rows = response['ranking']
    if not isinstance(rows, list) or not rows:
        raise AttentionInputError('INVALID_RESPONSE', 'ranking')
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _ROW:
            raise AttentionInputError('INVALID_RESPONSE', 'row')
        if type(row['score']) not in (int, float) or not 0 <= row['score'] <= 1 \
                or not math.isfinite(row['score']) or row['reason'] not in REASONS:
            raise AttentionInputError('INVALID_RESPONSE', 'score/reason')
        if not isinstance(row['camera_id'], str) or row['camera_id'] not in nodes or row['camera_id'] in seen:
            raise AttentionInputError('ILLEGAL_CANDIDATE', str(row['camera_id']))
        seen.add(row['camera_id'])
    scores = [r['score'] for r in rows]
    if scores != sorted(scores, reverse=True):
        raise AttentionInputError('INVALID_RESPONSE', 'not sorted by score')
    if type(response['latency_ms']) not in (int, float) or response['latency_ms'] < 0:
        raise AttentionInputError('INVALID_RESPONSE', 'latency_ms')
    cost = response['cost_usd']
    if cost is not None and (type(cost) not in (int, float) or cost < 0):
        raise AttentionInputError('INVALID_RESPONSE', 'cost_usd')
    if type(response['steps']) is not int or response['steps'] < 0:
        raise AttentionInputError('INVALID_RESPONSE', 'steps')
    if response['fallback_reason'] is not None and response['fallback_reason'] not in FALLBACK_REASONS:
        raise AttentionInputError('INVALID_RESPONSE', 'fallback_reason')
    if response['method'] != 'RULE' and response['fallback_reason'] is not None:
        raise AttentionInputError('INVALID_RESPONSE', 'fallback must report method RULE')


def request_sha256(request: Mapping) -> str:
    blob = json.dumps(request, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def rank_attention(request: Mapping, *, params: AttentionParams = DEFAULT_PARAMS,
                   requested_method: str = 'RULE', fallback_reason: str | None = None) -> dict:
    """Rule method: fixed-formula ranking of every graph node. Same request -> same ranking."""
    started = time.perf_counter()
    nodes = validate_request(request)
    last = request['last_observation']
    cam, seen, as_of = last['camera_id'], last['time_us'], request['as_of_us']
    boxes = [{'camera_id': cam, 'source_time_us': b['time_us'], 'bbox_xyxy_px': b['bbox_xyxy_px']}
             for b in last.get('recent_boxes', [])]
    boxes.append({'camera_id': cam, 'source_time_us': seen, 'bbox_xyxy_px': last['bbox_xyxy_px']})
    doc = pp.predict_next_cameras(last_camera_id=cam, last_observed_us=seen, as_of_us=as_of,
                                  boxes=boxes, camera_graph=request['graph'], params=params.prediction)
    summaries = {s['camera_id']: s for s in request['camera_summaries']}
    scores: dict[str, tuple[float, str]] = {}
    for cand in doc['candidates']:
        target = cand['camera_id']
        if target == cam or target in scores:
            continue
        start, end = cand['window_us']
        score = _CONFIDENCE_SCORE[cand['confidence']]
        if cand['exit_match'] in ('ALIGNED',):
            reason = 'EXIT_ALIGNED'
        elif cand['exit_match'] == 'LAST_POSITION_INSIDE':
            reason = 'EXIT_LAST_POSITION'
        else:
            reason = 'DIRECTION_UNKNOWN' if doc['direction']['status'] == 'UNKNOWN' else 'EXIT_ALIGNED'
        if as_of < start:
            score *= params.before_window_factor
        elif as_of > end:
            score *= params.overdue_factor
            reason = 'OVERDUE'
        info = summaries.get(target)
        if info is not None and info['person_detections_since_last_obs'] == 0:
            empty = info['coverage_end_us'] - max(start, seen)
            if empty >= params.negative_min_empty_us:
                covered_all = info['coverage_end_us'] >= end
                score = 0.0 if covered_all else score * params.negative_factor
                reason = 'NEGATIVE_EVIDENCE'
        scores[target] = (round(score, 6), reason)
    if request['elapsed_us'] <= params.still_in_view_us:
        scores[cam] = (1.0, 'STILL_IN_VIEW')
    else:
        scores[cam] = (params.left_camera_score, 'OVERDUE')
    for node in nodes:
        scores.setdefault(node, (params.not_adjacent_score, 'NOT_ADJACENT'))
    ranking = [{'camera_id': n, 'score': s, 'reason': r} for n, (s, r) in scores.items()]
    ranking.sort(key=lambda row: (-row['score'], row['camera_id']))
    return {'schema_version': RESPONSE_SCHEMA, 'method': 'RULE', 'requested_method': requested_method,
            'ranking': ranking, 'latency_ms': round((time.perf_counter() - started) * 1000, 3),
            'cost_usd': 0.0, 'steps': 0, 'fallback_reason': fallback_reason}


# ------------------------------------------------------------------ metrics (scoring only)

def hit_at_k(response: Mapping, truth_camera_id: str, k: int) -> bool:
    """Top-k hit. ``truth_camera_id`` comes from the scoring module, never from a request."""
    return truth_camera_id in [r['camera_id'] for r in response['ranking'][:k]]


def lead_time_us(updates: list[tuple[int, Mapping]], truth_camera_id: str, arrival_us: int) -> int | None:
    """Arrival minus the earliest ``as_of_us`` from which top-1 stays the truth camera until arrival.

    ``updates`` is [(as_of_us, response)] in time order, all with as_of_us < arrival_us.
    None when the truth camera is not top-1 in the last update before arrival.
    """
    earliest = None
    for as_of, response in updates:
        if as_of >= arrival_us:
            break
        if response['ranking'][0]['camera_id'] == truth_camera_id:
            earliest = as_of if earliest is None else earliest
        else:
            earliest = None
    return None if earliest is None else arrival_us - earliest


def false_switches(updates: list[tuple[int, Mapping]], truth_camera_id: str, arrival_us: int) -> int:
    """Number of top-1 changes before arrival whose new top-1 is not the truth camera."""
    count, previous = 0, None
    for as_of, response in updates:
        if as_of >= arrival_us:
            break
        top = response['ranking'][0]['camera_id']
        if previous is not None and top != previous and top != truth_camera_id:
            count += 1
        previous = top
    return count

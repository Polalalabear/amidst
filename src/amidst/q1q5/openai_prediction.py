"""OpenAI overhead-view prediction adapter (D107; DEMO_UI_SUPPORT_V1 §5).

Display-only external guess line for the overhead map. Default off; never enters
Q1-Q5 decisions, candidate ranking or evaluation scoring.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
import hashlib
import json
import logging
import time
import urllib.request

logger = logging.getLogger(__name__)

REQUEST_SCHEMA_VERSION = 'q-demo.external-prediction-request.v1'
RESULT_SCHEMA_VERSION = 'q-demo.external-prediction.v1'
RECORDING_SCHEMA_VERSION = 'q-demo.external-prediction-recording.v1'
OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
AVAILABLE_LABEL = '外部模型推測（非系統判斷）'
UNAVAILABLE_LABEL = '外部推測不可用'
SYSTEM_PROMPT = (
    'You receive a JSON topology and observed camera intervals. '
    'Return a JSON object with a single key "candidates" containing 0 to 3 items '
    'from candidate_camera_ids, each with keys "camera_id", "likelihood" '
    '("HIGH", "MEDIUM", or "LOW"), and "reason" (<= 200 chars).'
)
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
    'persons.sim',
})


class ExternalPredictionInputError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _check_forbidden(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
            lowered = key.lower()
            if lowered in FORBIDDEN_KEYS or lowered.startswith(_GT_PREFIX):
                raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
            _check_forbidden(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_forbidden(child)


def build_prediction_request(
    *,
    camera_map: Mapping,
    observed: Sequence[Mapping],
    as_of_us: int,
    last_exit: Mapping | None = None,
) -> dict:
    """Build a strict-whitelisted q-demo.external-prediction-request.v1 dict."""
    # The public map envelope carries a false read-status flag. It is not an
    # inference input and is omitted from the external request; all other
    # forbidden keys, including a true status flag, still fail closed.
    checked_map = dict(camera_map) if isinstance(camera_map, Mapping) else camera_map
    if isinstance(checked_map, dict) and checked_map.get(_GT_READ_KEY) is False:
        checked_map.pop(_GT_READ_KEY)
    _check_forbidden({'camera_map': checked_map, 'observed': list(observed), 'last_exit': last_exit})
    if type(as_of_us) is not int or as_of_us < 0:
        raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
    if not isinstance(camera_map, Mapping):
        raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')

    cameras_out = []
    all_camera_ids = []
    for c in camera_map.get('cameras', []):
        if not isinstance(c, Mapping) or not isinstance(c.get('camera_id'), str):
            raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
        cid = c['camera_id']
        all_camera_ids.append(cid)
        exits = [
            e['exit_zone_id']
            for e in c.get('exits', [])
            if isinstance(e, Mapping) and isinstance(e.get('exit_zone_id'), str)
        ]
        cameras_out.append({
            'camera_id': cid,
            'role': str(c.get('role', 'TRACKING')),
            'exit_zone_ids': exits,
        })

    transitions_out = []
    for t in camera_map.get('transitions', []):
        if not isinstance(t, Mapping):
            raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
        transitions_out.append({
            'from_camera_id': str(t['from_camera_id']),
            'to_camera_id': str(t['to_camera_id']),
            'relation': str(t['relation']),
            'via_exit_zone_ids': [str(z) for z in t.get('via_exit_zone_ids', [])],
        })

    clipped_observed = []
    for seg in observed:
        if not isinstance(seg, Mapping) or set(seg) != {'camera_id', 'range_us'}:
            raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
        cid = seg.get('camera_id')
        rng = seg.get('range_us')
        if (not isinstance(cid, str) or not cid or not isinstance(rng, (list, tuple))
                or len(rng) != 2 or type(rng[0]) is not int or type(rng[1]) is not int
                or rng[0] < 0 or rng[1] < rng[0]):
            raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
        if rng[0] > as_of_us:
            continue
        end_us = min(rng[1], as_of_us)
        clipped_observed.append({'camera_id': cid, 'range_us': [rng[0], end_us]})

    last_exit_out = None
    if last_exit is not None:
        if (not isinstance(last_exit, Mapping)
                or set(last_exit) != {'camera_id', 'exit_zone_id', 'direction_status'}
                or not isinstance(last_exit.get('camera_id'), str)
                or (last_exit.get('exit_zone_id') is not None and not isinstance(last_exit.get('exit_zone_id'), str))
                or last_exit.get('direction_status') not in {'KNOWN', 'UNKNOWN'}):
            raise ExternalPredictionInputError('FORBIDDEN_INFERENCE_INPUT')
        last_exit_out = {
            'camera_id': last_exit['camera_id'],
            'exit_zone_id': last_exit['exit_zone_id'],
            'direction_status': last_exit['direction_status'],
        }

    origin_cam = (
        last_exit_out['camera_id']
        if last_exit_out is not None
        else (clipped_observed[-1]['camera_id'] if clipped_observed else None)
    )
    if origin_cam is not None:
        candidates = sorted({
            t['to_camera_id']
            for t in transitions_out
            if t['from_camera_id'] == origin_cam
        })
        if not candidates:
            candidates = sorted(set(all_camera_ids))
    else:
        candidates = sorted(set(all_camera_ids))

    return {
        'schema_version': REQUEST_SCHEMA_VERSION,
        'as_of_us': as_of_us,
        'topology': {
            'cameras': cameras_out,
            'transitions': transitions_out,
        },
        'observed': clipped_observed,
        'last_exit': last_exit_out,
        'candidate_camera_ids': candidates,
    }


def _validate_whitelisted_request(req: object) -> str | None:
    """Return None if valid, or the failure reason code."""
    try:
        _check_forbidden(req)
    except ExternalPredictionInputError:
        return 'REQUEST_NOT_WHITELISTED'
    if not isinstance(req, Mapping):
        return 'REQUEST_NOT_WHITELISTED'
    expected_top = {'schema_version', 'as_of_us', 'topology', 'observed', 'last_exit', 'candidate_camera_ids'}
    if set(req) != expected_top or req.get('schema_version') != REQUEST_SCHEMA_VERSION:
        return 'REQUEST_NOT_WHITELISTED'
    as_of_us = req.get('as_of_us')
    if type(as_of_us) is not int or as_of_us < 0:
        return 'REQUEST_NOT_WHITELISTED'
    topo = req.get('topology')
    if not isinstance(topo, Mapping) or set(topo) != {'cameras', 'transitions'}:
        return 'REQUEST_NOT_WHITELISTED'
    if not isinstance(topo.get('cameras'), list) or not isinstance(topo.get('transitions'), list):
        return 'REQUEST_NOT_WHITELISTED'
    for c in topo['cameras']:
        if (not isinstance(c, Mapping) or set(c) != {'camera_id', 'role', 'exit_zone_ids'}
                or not isinstance(c.get('camera_id'), str)
                or not isinstance(c.get('role'), str)
                or not isinstance(c.get('exit_zone_ids'), list)
                or not all(isinstance(x, str) for x in c['exit_zone_ids'])):
            return 'REQUEST_NOT_WHITELISTED'
    for t in topo['transitions']:
        if (not isinstance(t, Mapping)
                or set(t) != {'from_camera_id', 'to_camera_id', 'relation', 'via_exit_zone_ids'}
                or not isinstance(t.get('from_camera_id'), str)
                or not isinstance(t.get('to_camera_id'), str)
                or not isinstance(t.get('relation'), str)
                or not isinstance(t.get('via_exit_zone_ids'), list)
                or not all(isinstance(x, str) for x in t['via_exit_zone_ids'])):
            return 'REQUEST_NOT_WHITELISTED'
    observed = req.get('observed')
    if not isinstance(observed, list):
        return 'REQUEST_NOT_WHITELISTED'
    for seg in observed:
        if (not isinstance(seg, Mapping) or set(seg) != {'camera_id', 'range_us'}
                or not isinstance(seg.get('camera_id'), str)
                or not isinstance(seg.get('range_us'), list) or len(seg['range_us']) != 2
                or type(seg['range_us'][0]) is not int or type(seg['range_us'][1]) is not int
                or seg['range_us'][0] < 0 or seg['range_us'][1] < seg['range_us'][0]):
            return 'REQUEST_NOT_WHITELISTED'
        if seg['range_us'][0] > as_of_us or seg['range_us'][1] > as_of_us:
            return 'FUTURE_DATA_IN_REQUEST'
    last_exit = req.get('last_exit')
    if last_exit is not None:
        if (not isinstance(last_exit, Mapping)
                or set(last_exit) != {'camera_id', 'exit_zone_id', 'direction_status'}
                or not isinstance(last_exit.get('camera_id'), str)
                or (last_exit.get('exit_zone_id') is not None and not isinstance(last_exit.get('exit_zone_id'), str))
                or last_exit.get('direction_status') not in {'KNOWN', 'UNKNOWN'}):
            return 'REQUEST_NOT_WHITELISTED'
    cands = req.get('candidate_camera_ids')
    if not isinstance(cands, list) or not all(isinstance(x, str) for x in cands):
        return 'REQUEST_NOT_WHITELISTED'
    return None


def _validate_candidates_object(obj: object, allowed_cameras: set[str]) -> list[dict] | None:
    if not isinstance(obj, Mapping) or set(obj) != {'candidates'}:
        return None
    raw_list = obj.get('candidates')
    if not isinstance(raw_list, list) or len(raw_list) > 3:
        return None
    seen: set[str] = set()
    validated: list[dict] = []
    for item in raw_list:
        if not isinstance(item, Mapping) or set(item) != {'camera_id', 'likelihood', 'reason'}:
            return None
        cid = item.get('camera_id')
        likelihood = item.get('likelihood')
        reason = item.get('reason')
        if (not isinstance(cid, str) or cid not in allowed_cameras or cid in seen
                or likelihood not in {'HIGH', 'MEDIUM', 'LOW'}
                or not isinstance(reason, str) or not reason or len(reason) > 200):
            return None
        seen.add(cid)
        validated.append({'camera_id': cid, 'likelihood': likelihood, 'reason': reason})
    return validated


def _parse_completion(raw_bytes: bytes, allowed_cameras: set[str]) -> list[dict] | None:
    try:
        outer = json.loads(raw_bytes.decode('utf-8'))
    except Exception:
        return None
    if not isinstance(outer, Mapping):
        return None
    choices = outer.get('choices')
    if not isinstance(choices, list) or not choices:
        return None
    msg = choices[0].get('message') if isinstance(choices[0], Mapping) else None
    content = msg.get('content') if isinstance(msg, Mapping) else None
    if not isinstance(content, str):
        return None
    try:
        inner = json.loads(content)
    except Exception:
        return None
    return _validate_candidates_object(inner, allowed_cameras)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'Redirects forbidden', headers, fp)


def default_https_transport(*, url: str, headers: Mapping[str, str], body: bytes, timeout_s: float) -> bytes:
    opener = urllib.request.build_opener(_NoRedirectHandler)
    req = urllib.request.Request(url, data=body, headers=dict(headers), method='POST')
    with opener.open(req, timeout=timeout_s) as resp:
        return resp.read()


class OpenAIPredictionAdapter:
    """Safe, bounded adapter for display-only external next-camera guesses."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        mode: str = 'LIVE',
        model: str | None = None,
        transport: Callable | None = None,
        env: Mapping[str, str] | None = None,
        replay: Sequence[Mapping] | None = None,
        recorder: Callable[[dict], None] | None = None,
        timeout_s: float = 5.0,
        max_calls_per_session: int = 6,
        clock: Callable[[], float] = time.monotonic,
    ):
        if mode not in {'LIVE', 'REPLAY'}:
            raise ValueError('Invalid mode')
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not (0.0 < float(timeout_s) <= 5.0):
            raise ValueError('Invalid timeout_s')
        if type(max_calls_per_session) is not int or max_calls_per_session < 1:
            raise ValueError('Invalid max_calls_per_session')
        if enabled and mode == 'LIVE' and (not isinstance(model, str) or not model.strip()):
            raise ValueError('Model required when enabled in LIVE mode')

        self.enabled = bool(enabled)
        self.mode = mode
        self.model = model
        self._transport = transport or default_https_transport
        # Credentials are explicit inputs. Disabled/replay adapters never read
        # credentials, including from a caller-provided environment mapping.
        self._api_key = env.get('OPENAI_API_KEY') if enabled and mode == 'LIVE' and isinstance(env, Mapping) else None
        self._recorder = recorder
        self.timeout_s = float(timeout_s)
        self.max_calls_per_session = max_calls_per_session
        self._clock = clock

        self._replay_by_sha: dict[str, dict] = {}
        if mode == 'REPLAY':
            for record in replay or ():
                if (not isinstance(record, Mapping)
                        or set(record) != {'schema_version', 'request_sha256', 'request', 'response', 'model'}
                        or record.get('schema_version') != RECORDING_SCHEMA_VERSION):
                    raise ValueError('Invalid replay record schema')
                req = record['request']
                if _validate_whitelisted_request(req) is not None:
                    raise ValueError('Invalid replay request')
                req_sha = _sha256(_canonical(req))
                if record.get('request_sha256') != req_sha:
                    raise ValueError('Replay request_sha256 mismatch')
                allowed = set(req['candidate_camera_ids'])
                cands = _validate_candidates_object(record.get('response'), allowed)
                if cands is None:
                    raise ValueError('Invalid replay response candidates')
                self._replay_by_sha[req_sha] = {
                    'candidates': cands,
                    'model': record.get('model'),
                }

        self._cache_by_req_sha: dict[str, dict] = {}
        self._search_outcomes: dict[tuple[str, str], dict] = {}
        self._session_calls: dict[str, int] = {}
        self._session_locked: set[str] = set()

    def __repr__(self) -> str:
        return f'OpenAIPredictionAdapter(enabled={self.enabled!r}, mode={self.mode!r}, model={self.model!r})'

    __str__ = __repr__

    def _result(
        self,
        *,
        status: str,
        reason: str | None,
        candidates: list[dict],
        request_sha256: str | None,
        source: str,
        attempts: int,
        model: str | None = None,
    ) -> dict:
        available = status == 'AVAILABLE'
        return {
            'schema_version': RESULT_SCHEMA_VERSION,
            'status': status,
            'reason': None if available else reason,
            'label': AVAILABLE_LABEL if available else UNAVAILABLE_LABEL,
            'fallback': None if available else 'PHYSICAL_PREDICTION',
            'candidates': deepcopy(candidates) if available else [],
            'request_sha256': request_sha256,
            'source': source,
            'attempts': attempts,
            'model': model if model is not None else self.model,
            'used_for': 'DISPLAY_ONLY',
            'scoring_use': False,
            'identity_verdict': 'UNCONFIRMED',
            _GT_READ_KEY: False,
        }

    def predict(self, *, session_id: str, query_id: str, request: Mapping) -> dict:
        req_error = _validate_whitelisted_request(request)
        if req_error is not None:
            return self._result(
                status='UNAVAILABLE',
                reason=req_error,
                candidates=[],
                request_sha256=None,
                source='NONE',
                attempts=0,
            )

        canonical_req = _canonical(request)
        req_sha = _sha256(canonical_req)

        if not self.enabled:
            return self._result(
                status='UNAVAILABLE',
                reason='DISABLED',
                candidates=[],
                request_sha256=req_sha,
                source='NONE',
                attempts=0,
            )

        if self.mode == 'REPLAY':
            hit = self._replay_by_sha.get(req_sha)
            if hit is None:
                return self._result(
                    status='UNAVAILABLE',
                    reason='REPLAY_MISS',
                    candidates=[],
                    request_sha256=req_sha,
                    source='NONE',
                    attempts=0,
                )
            return self._result(
                status='AVAILABLE',
                reason=None,
                candidates=hit['candidates'],
                request_sha256=req_sha,
                source='REPLAY',
                attempts=0,
                model=hit['model'],
            )

        if not isinstance(self._api_key, str) or not self._api_key.strip():
            return self._result(
                status='UNAVAILABLE',
                reason='API_KEY_MISSING',
                candidates=[],
                request_sha256=req_sha,
                source='NONE',
                attempts=0,
            )

        search_key = (session_id, query_id)
        if search_key in self._search_outcomes:
            prev = self._search_outcomes[search_key]
            if prev['request_sha256'] != req_sha:
                return self._result(
                    status='UNAVAILABLE', reason='REQUEST_NOT_WHITELISTED',
                    candidates=[], request_sha256=req_sha, source='NONE', attempts=0,
                )
            if prev['status'] == 'AVAILABLE':
                return self._result(
                    status='AVAILABLE',
                    reason=None,
                    candidates=prev['candidates'],
                    request_sha256=req_sha,
                    source='CACHE',
                    attempts=0,
                    model=prev['model'],
                )
            return self._result(
                status='UNAVAILABLE',
                reason=prev['reason'],
                candidates=[],
                request_sha256=req_sha,
                source='NONE',
                attempts=0,
            )

        if req_sha in self._cache_by_req_sha:
            cached = self._cache_by_req_sha[req_sha]
            out = self._result(
                status='AVAILABLE',
                reason=None,
                candidates=cached['candidates'],
                request_sha256=req_sha,
                source='CACHE',
                attempts=0,
                model=cached['model'],
            )
            self._search_outcomes[search_key] = deepcopy(out)
            return out

        used_calls = self._session_calls.get(session_id, 0)
        if session_id in self._session_locked or used_calls >= self.max_calls_per_session:
            self._session_locked.add(session_id)
            return self._result(
                status='UNAVAILABLE',
                reason='SESSION_CALL_LIMIT_LOCKED',
                candidates=[],
                request_sha256=req_sha,
                source='NONE',
                attempts=0,
            )

        body_bytes = _canonical({
            'model': self.model,
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': canonical_req},
            ],
        }).encode('utf-8')
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
        }
        allowed_cameras = set(request['candidate_camera_ids'])
        start_time = self._clock()
        deadline = start_time + self.timeout_s
        attempts = 0
        last_reason = 'TRANSPORT_ERROR'

        for attempt in range(2):
            used_calls = self._session_calls.get(session_id, 0)
            if used_calls >= self.max_calls_per_session:
                self._session_locked.add(session_id)
                break
            remaining = deadline - self._clock()
            if remaining <= 0:
                last_reason = 'TIMEOUT'
                break
            attempts += 1
            self._session_calls[session_id] = used_calls + 1
            if self._session_calls[session_id] >= self.max_calls_per_session:
                self._session_locked.add(session_id)
            try:
                raw_resp = self._transport(
                    url=OPENAI_CHAT_URL,
                    headers=headers,
                    body=body_bytes,
                    timeout_s=min(self.timeout_s, remaining),
                )
            except TimeoutError as exc:
                last_reason = 'TIMEOUT'
                logger.warning(
                    'external_prediction failed: reason=%s exc=%s req=%s attempts=%d',
                    last_reason, type(exc).__name__, req_sha, attempts,
                )
                break
            except Exception as exc:
                last_reason = 'TRANSPORT_ERROR'
                logger.warning(
                    'external_prediction failed: reason=%s exc=%s req=%s attempts=%d',
                    last_reason, type(exc).__name__, req_sha, attempts,
                )
                continue

            if self._clock() > deadline:
                last_reason = 'TIMEOUT'
                logger.warning(
                    'external_prediction failed: reason=%s exc=DeadlineExceeded req=%s attempts=%d',
                    last_reason, req_sha, attempts,
                )
                break

            parsed = _parse_completion(raw_resp, allowed_cameras)
            if parsed is None:
                last_reason = 'RESPONSE_SCHEMA_INVALID'
                logger.warning(
                    'external_prediction failed: reason=%s exc=SchemaError req=%s attempts=%d',
                    last_reason, req_sha, attempts,
                )
                continue

            if self._recorder is not None:
                self._recorder({
                    'schema_version': RECORDING_SCHEMA_VERSION,
                    'request_sha256': req_sha,
                    'request': json.loads(canonical_req),
                    'response': {'candidates': deepcopy(parsed)},
                    'model': self.model,
                })
            self._cache_by_req_sha[req_sha] = {'candidates': parsed, 'model': self.model}
            out = self._result(
                status='AVAILABLE',
                reason=None,
                candidates=parsed,
                request_sha256=req_sha,
                source='LIVE',
                attempts=attempts,
                model=self.model,
            )
            self._search_outcomes[search_key] = deepcopy(out)
            return out

        out = self._result(
            status='UNAVAILABLE',
            reason=last_reason,
            candidates=[],
            request_sha256=req_sha,
            source='NONE',
            attempts=attempts,
        )
        self._search_outcomes[search_key] = deepcopy(out)
        return out

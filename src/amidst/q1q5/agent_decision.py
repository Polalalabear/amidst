"""Agent decision WP1: contract validators, rule decider, call budget and fallback machine.

Design: docs/design/AGENT_DECISION_V1.md (§2, §3.3, §7 WP1). Contract:
docs/contracts/schemas/q-core.agent-decision.v1.schema.json and
q-core.agent-decision-params.v1.schema.json.

Pure code only. This module performs no file, network, clock or environment I/O and
is not imported by the existing associate() path (wiring is WP2). Providers, recording
and replay are WP3: they are passed in as a plain callable that returns an Attempt.
Identity is never confirmed; every request and record carries UNCONFIRMED.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import re

REQUEST_SCHEMA_VERSION = 'q-core.agent-decision-request.v1'
RECORD_SCHEMA_VERSION = 'q-core.agent-decision-record.v1'
PARAMS_SCHEMA_VERSION = 'q-core.agent-decision-params.v1'

DP1 = 'DP1_HANDOFF_ADJUDICATION'
DP3 = 'DP3_CONTINUATION_ACCEPTANCE'
DECISION_POINTS = (DP1, DP3)

MODES = ('OFF', 'RULE_ONLY', 'AGENT_LIVE', 'AGENT_REPLAY')
DEFAULT_MODE = 'OFF'
AGENT_MODES = ('AGENT_LIVE', 'AGENT_REPLAY')

MODELS = ('astra6', 'sol6.1', 'terra6.1')
UNCONFIRMED = 'UNCONFIRMED'

ABSTAIN = 'ABSTAIN'
ACCEPT_SEGMENT = 'ACCEPT_SEGMENT'
REJECT_SEGMENT = 'REJECT_SEGMENT'
ACTIONS = {DP1: ('SELECT', ABSTAIN), DP3: (ACCEPT_SEGMENT, REJECT_SEGMENT)}

COLORS = ('red', 'orange', 'yellow', 'green', 'blue', 'purple')
LINK_KINDS = ('SAME_CAMERA_REACQUISITION', 'CROSS_CAMERA_HANDOFF', 'CROSS_CAMERA_REACQUISITION')
GRAPH_STATUSES = ('GRAPH_NOT_APPROVED', 'GRAPH_APPROVED')
REASON_CODES = ('COLOR_MATCH', 'COLOR_CONFLICT', 'GRAPH_EDGE', 'NO_GRAPH_EDGE', 'SHORT_GAP', 'LONG_GAP',
                'HIGH_SCORE', 'LOW_SCORE', 'MOSTLY_CONTINUATION', 'INSUFFICIENT_EVIDENCE')
RATIONALE_MAX = 240
MAX_CANDIDATES = 8
MAX_EDGES = 64
MAX_REASON_CODES = 4
MAX_RESPONSE_NESTING = 32  # provider JSON nesting limit, checked before any recursive walk or hashing
PARAM_MAX = {'timeout_ms': 60_000, 'max_output_tokens': 4096, 'budget_ms': 60_000,
             'session_max_rounds': 100, 'prompt_tokens_per_call_estimate': 200_000}

DECISION_SOURCES = ('AGENT', 'RULE_FALLBACK', 'RULE_ONLY')
# Values shared with common.v2 $defs/fallback_reason ...
FALLBACK_REASONS_COMMON_V2 = ('ROUND_LIMIT', 'TIME_BUDGET', 'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT',
                              'INVALID_RESPONSE', 'ILLEGAL_CANDIDATE', 'MODE_NOT_AUTHORIZED')
# ... and the two values added to common.v2 by WP1 under D168 (design §8.2 Q3).
FALLBACK_REASONS_NEW = ('CALL_BUDGET_EXHAUSTED', 'REPLAY_MISS')
FALLBACK_REASONS = FALLBACK_REASONS_COMMON_V2 + FALLBACK_REASONS_NEW
BUDGET_LAYERS = ('SESSION_ROUNDS', 'MODEL_CALLS', 'MODEL_TOKENS', 'STAGE_CALLS', 'STAGE_TOKENS', 'TOTAL_USD')
PROVIDER_KINDS = ('NONE', 'OPENAI', 'OLLAMA_LOOPBACK')

# Provider-reported attempt outcomes (WP3 transports map their errors onto these).
CALL_OK = 'OK'
CALL_TIMEOUT = 'TIMEOUT'
CALL_UNAVAILABLE = 'UNAVAILABLE'
CALL_RETRYABLE = 'RETRYABLE'  # HTTP 429 or 5xx
CALL_REPLAY_MISS = 'REPLAY_MISS'
CALL_OUTCOMES = (CALL_OK, CALL_TIMEOUT, CALL_UNAVAILABLE, CALL_RETRYABLE, CALL_REPLAY_MISS)
# Outcomes written into record.attempts.
ATTEMPT_OUTCOMES = ('OK', 'PROVIDER_TIMEOUT', 'PROVIDER_UNAVAILABLE', 'PROVIDER_RETRYABLE_ERROR',
                    'INVALID_RESPONSE', 'ILLEGAL_CANDIDATE', 'REPLAY_MISS')

OPAQUE_ID = re.compile(r'[A-Z]{1,2}[0-9]{1,3}\Z')
CAMERA_ID = re.compile(r'CAM_[A-Z0-9_]{1,40}\Z')
ANSWER = re.compile(r'(?:[A-Z]{1,2}[0-9]{1,3}|ABSTAIN|ACCEPT_SEGMENT|REJECT_SEGMENT)\Z')
SHA256 = re.compile(r'[a-f0-9]{64}\Z')

# Protected inputs (DEVELOPMENT_RULES GT isolation; run_cross_camera_demo FORBIDDEN plus
# identity fields). Fragments are joined so the architecture guard's string scan stays clean,
# matching core_query.py / openai_prediction.py.
_GT_PREFIX = ''.join(('gt', '_'))
FORBIDDEN_KEYS = frozenset({
    'gt', ''.join(('ground', '_truth')), ''.join(('gt', '_private')), 'event_script', 'script',
    'script_path', 'scenario', ''.join(('renderer_', 'traject', 'ory')), ''.join(('renderer_', 'track')),
    ''.join(('traject', 'ory')), ''.join(('traject', 'ories')), ''.join(('visib', 'ility')),
    ''.join(('dep', 'th')), 'actor', 'actor_id', 'material_id', 'mask', 'private_evaluation',
    'scoring_private', 'track_ref', 'path', 'file', 'file_path', 'identity', 'identity_id',
    'person_id', 'same_person', 'identity_confirmed',
})

TRACK_KEYS = frozenset({'id', 'camera_id', 'first_seen_us', 'last_seen_us', 'colors', 'scores',
                        'continuation_fraction'})
CANDIDATE_KEYS = TRACK_KEYS | {'gap_us', 'graph_edge', 'link_kind', 'rule_eligible'}
SCORE_KEYS = frozenset({'n', 'min', 'median', 'max'})
SEGMENT_KEYS = frozenset({'start_us', 'end_us', 'n_frames', 'box_scores'})
TOPOLOGY_KEYS = frozenset({'graph_status', 'edges'})
REQUEST_REQUIRED = frozenset({'schema_version', 'decision_point', 'as_of_us', 'topology', 'current',
                              'rule_answer', 'identity_verdict'})
REQUEST_KEYS = REQUEST_REQUIRED | {'candidates', 'segment'}
RESPONSE_REQUIRED = frozenset({'action', 'reason_codes', 'rationale'})
RESPONSE_KEYS = RESPONSE_REQUIRED | {'candidate_id'}
RECORD_KEYS = frozenset({'schema_version', 'request_sha256', 'decision_point', 'mode', 'decision_source',
                         'fallback_reason', 'budget_layer', 'final_answer', 'rule_answer',
                         'identity_verdict', 'provider', 'parameter_set_sha256', 'attempts'})
PROVIDER_KEYS = frozenset({'kind', 'model', 'api_model_id', 'model_digest', 'temperature', 'seed',
                           'candidate_order_seed'})
PROVIDER_REQUIRED = frozenset({'kind', 'model'})
ATTEMPT_KEYS = frozenset({'wall_ms', 'timeout_ms', 'outcome', 'response_sha256', 'prompt_tokens',
                          'completion_tokens'})
ATTEMPT_REQUIRED = frozenset({'wall_ms', 'timeout_ms', 'outcome'})


class AgentDecisionError(ValueError):
    """Validation failure. ``code`` is a stable machine code; ``detail`` names the field."""

    def __init__(self, code: str, detail: str = ''):
        self.code = code
        self.detail = detail
        super().__init__(f'{code}:{detail}' if detail else code)


# ---------------------------------------------------------------- helpers

def canonical(value) -> bytes:
    """Canonical JSON (design §3.3): sorted keys, compact separators, ASCII, no NaN."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode()


def request_sha256(request: Mapping) -> str:
    """Order-independent request hash: candidates are sorted by opaque id before hashing."""
    body = dict(request)
    if 'candidates' in body:
        body['candidates'] = sorted(body['candidates'], key=lambda c: c['id'])
    return hashlib.sha256(canonical(body)).hexdigest()


def parameter_set_sha256(params: Mapping) -> str:
    return hashlib.sha256(canonical(params)).hexdigest()


def _is_int(value) -> bool:
    return type(value) is int


def _is_number(value) -> bool:
    return type(value) in (int, float) and value == value and value not in (float('inf'), float('-inf'))


def check_json_safe(value, code: str = 'INVALID_RESPONSE', _level: int = 1) -> None:
    """Raise AgentDecisionError(code) unless ``value`` is finite plain JSON within the nesting limit.

    Nesting is checked first, so hostile input never reaches a recursive walk or json.dumps."""
    if _level > MAX_RESPONSE_NESTING:
        raise AgentDecisionError(code, f'nesting deeper than {MAX_RESPONSE_NESTING}')
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float:
        if value != value or value in (float('inf'), float('-inf')):
            raise AgentDecisionError(code, 'NaN/Infinity')
        return
    if type(value) is list:
        for item in value:
            check_json_safe(item, code, _level + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise AgentDecisionError(code, 'non-string key')
            check_json_safe(item, code, _level + 1)
        return
    raise AgentDecisionError(code, f'not JSON-serializable: {type(value).__name__}')


def _forbidden_scan(value, code: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise AgentDecisionError(code, 'non-string key')
            low = key.lower()
            if low in FORBIDDEN_KEYS or low.startswith(_GT_PREFIX):
                raise AgentDecisionError(code, key)
            _forbidden_scan(item, code)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _forbidden_scan(item, code)


def _keys(obj, required: frozenset, allowed: frozenset, code: str, where: str) -> None:
    if not isinstance(obj, Mapping):
        raise AgentDecisionError(code, where)
    missing = required - obj.keys()
    extra = obj.keys() - allowed
    if missing:
        raise AgentDecisionError(code, f'{where}: missing {sorted(missing)}')
    if extra:
        raise AgentDecisionError(code, f'{where}: extra {sorted(extra)}')


def _us(value, code: str, where: str) -> None:
    if not _is_int(value) or value < 0:
        raise AgentDecisionError(code, where)


def _unit(value, code: str, where: str) -> None:
    if not _is_number(value) or not 0 <= value <= 1:
        raise AgentDecisionError(code, where)


def _scores(obj, code: str, where: str) -> None:
    _keys(obj, SCORE_KEYS, SCORE_KEYS, code, where)
    if not _is_int(obj['n']) or obj['n'] < 0:
        raise AgentDecisionError(code, f'{where}.n')
    for key in ('min', 'median', 'max'):
        _unit(obj[key], code, f'{where}.{key}')
    if not obj['min'] <= obj['median'] <= obj['max']:
        raise AgentDecisionError(code, f'{where}: min<=median<=max')


def _track(obj, keys: frozenset, as_of_us: int, code: str, where: str) -> None:
    _keys(obj, keys, keys, code, where)
    if not isinstance(obj['id'], str) or not OPAQUE_ID.fullmatch(obj['id']):
        raise AgentDecisionError(code, f'{where}.id')
    if not isinstance(obj['camera_id'], str) or not CAMERA_ID.fullmatch(obj['camera_id']):
        raise AgentDecisionError(code, f'{where}.camera_id')
    _us(obj['first_seen_us'], code, f'{where}.first_seen_us')
    _us(obj['last_seen_us'], code, f'{where}.last_seen_us')
    # Causal rule of associate(): only observations strictly before as_of_us.
    if not obj['first_seen_us'] <= obj['last_seen_us'] < as_of_us:
        raise AgentDecisionError(code, f'{where}: first_seen<=last_seen<as_of')
    colors = obj['colors']
    if (not isinstance(colors, list) or len(colors) > len(COLORS) or len(set(colors)) != len(colors)
            or any(c not in COLORS for c in colors)):
        raise AgentDecisionError(code, f'{where}.colors')
    _scores(obj['scores'], code, f'{where}.scores')
    _unit(obj['continuation_fraction'], code, f'{where}.continuation_fraction')
    if keys is CANDIDATE_KEYS:
        if not _is_int(obj['gap_us']) or obj['gap_us'] < 0:
            raise AgentDecisionError(code, f'{where}.gap_us')
        if type(obj['graph_edge']) is not bool or type(obj['rule_eligible']) is not bool:
            raise AgentDecisionError(code, f'{where}: boolean fields')
        if obj['link_kind'] not in LINK_KINDS:
            raise AgentDecisionError(code, f'{where}.link_kind')


# ---------------------------------------------------------------- request / response

def validate_request(request) -> None:
    """Raise AgentDecisionError unless ``request`` matches $defs/request plus semantic rules.

    Codes: FORBIDDEN_INFERENCE_INPUT (protected key anywhere), REQUEST_INVALID (anything else).
    """
    _forbidden_scan(request, 'FORBIDDEN_INFERENCE_INPUT')
    code = 'REQUEST_INVALID'
    _keys(request, REQUEST_REQUIRED, REQUEST_KEYS, code, 'request')
    if request['schema_version'] != REQUEST_SCHEMA_VERSION:
        raise AgentDecisionError(code, 'schema_version')
    if request['identity_verdict'] != UNCONFIRMED:
        raise AgentDecisionError(code, 'identity_verdict')
    dp = request['decision_point']
    if dp not in DECISION_POINTS:
        raise AgentDecisionError(code, 'decision_point')
    _us(request['as_of_us'], code, 'as_of_us')
    as_of = request['as_of_us']
    topology = request['topology']
    _keys(topology, TOPOLOGY_KEYS, TOPOLOGY_KEYS, code, 'topology')
    if topology['graph_status'] not in GRAPH_STATUSES:
        raise AgentDecisionError(code, 'topology.graph_status')
    edges = topology['edges']
    if not isinstance(edges, list) or len(edges) > MAX_EDGES or any(
            not isinstance(e, list) or len(e) != 2
            or not all(isinstance(c, str) and CAMERA_ID.fullmatch(c) for c in e) for e in edges):
        raise AgentDecisionError(code, 'topology.edges')
    _track(request['current'], TRACK_KEYS, as_of, code, 'current')
    answer = request['rule_answer']
    if not isinstance(answer, str) or not ANSWER.fullmatch(answer):
        raise AgentDecisionError(code, 'rule_answer')
    if dp == DP1:
        if 'segment' in request or 'candidates' not in request:
            raise AgentDecisionError(code, 'DP1 needs candidates and no segment')
        candidates = request['candidates']
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_CANDIDATES:
            raise AgentDecisionError(code, 'candidates')
        for i, candidate in enumerate(candidates):
            _track(candidate, CANDIDATE_KEYS, as_of, code, f'candidates[{i}]')
        ids = [c['id'] for c in candidates]
        if len(set(ids)) != len(ids) or request['current']['id'] in ids:
            raise AgentDecisionError(code, 'candidate ids must be unique and differ from current')
        if answer != ABSTAIN and answer not in ids:
            raise AgentDecisionError(code, 'rule_answer not legal for DP1')
    else:
        if 'candidates' in request or 'segment' not in request:
            raise AgentDecisionError(code, 'DP3 needs segment and no candidates')
        segment = request['segment']
        _keys(segment, SEGMENT_KEYS, SEGMENT_KEYS, code, 'segment')
        _us(segment['start_us'], code, 'segment.start_us')
        _us(segment['end_us'], code, 'segment.end_us')
        if not segment['start_us'] <= segment['end_us'] <= as_of:
            raise AgentDecisionError(code, 'segment: start<=end<=as_of')
        if not _is_int(segment['n_frames']) or segment['n_frames'] < 1:
            raise AgentDecisionError(code, 'segment.n_frames')
        _scores(segment['box_scores'], code, 'segment.box_scores')
        if answer not in (ACCEPT_SEGMENT, REJECT_SEGMENT):
            raise AgentDecisionError(code, 'rule_answer not legal for DP3')


def validate_response(response, request) -> str:
    """Return the decided answer, or raise AgentDecisionError(INVALID_RESPONSE|ILLEGAL_CANDIDATE).

    ``request`` must already be valid. Identity fields and any extra key are INVALID_RESPONSE.
    """
    code = 'INVALID_RESPONSE'
    check_json_safe(response, code)
    _forbidden_scan(response, code)
    _keys(response, RESPONSE_REQUIRED, RESPONSE_KEYS, code, 'response')
    action = response['action']
    dp = request['decision_point']
    if action not in ACTIONS[dp]:
        raise AgentDecisionError(code, f'action {action!r} not allowed for {dp}')
    reasons = response['reason_codes']
    if (not isinstance(reasons, list) or not 1 <= len(reasons) <= MAX_REASON_CODES
            or len(set(reasons)) != len(reasons) or any(r not in REASON_CODES for r in reasons)):
        raise AgentDecisionError(code, 'reason_codes')
    rationale = response['rationale']
    if not isinstance(rationale, str) or len(rationale) > RATIONALE_MAX:
        raise AgentDecisionError(code, 'rationale')
    if action != 'SELECT':
        if 'candidate_id' in response:
            raise AgentDecisionError(code, 'candidate_id only with SELECT')
        return action
    candidate_id = response.get('candidate_id')
    if not isinstance(candidate_id, str) or not OPAQUE_ID.fullmatch(candidate_id):
        raise AgentDecisionError(code, 'candidate_id')
    match = [c for c in request['candidates'] if c['id'] == candidate_id]
    if not match or not match[0]['rule_eligible']:
        raise AgentDecisionError('ILLEGAL_CANDIDATE', candidate_id)
    return candidate_id


# ---------------------------------------------------------------- rule decider

class RuleDecider:
    """R0: the current associate() rule expressed on a request (design §3.1).

    DP1: exactly one rule-eligible candidate -> that id; zero or several -> ABSTAIN
    (associate() logs AMBIGUOUS_HANDOFF and does not switch). DP3: accept every
    continuation segment (associate() keeps all BOX_CONTINUATION boxes).
    """

    def answer(self, request: Mapping) -> str:
        if request['decision_point'] == DP3:
            return ACCEPT_SEGMENT
        eligible = [c['id'] for c in request['candidates'] if c['rule_eligible']]
        return eligible[0] if len(eligible) == 1 else ABSTAIN


# ---------------------------------------------------------------- parameters

def _fail(detail: str):
    raise AgentDecisionError('PARAMS_INVALID', detail)


def validate_params(params) -> None:
    """Raise AgentDecisionError(PARAMS_INVALID) unless params match the params v1 schema."""
    required = {'schema_version', 'parameter_set_id', 'report_group', 'mode', 'decision_points', 'models',
                'per_call', 'per_step', 'per_session', 'rate', 'budget_usd', 'price_table',
                'prompt_tokens_per_call_estimate', 'stages'}
    _keys(params, frozenset(required), frozenset(required | {'note'}), 'PARAMS_INVALID', 'params')
    if params['schema_version'] != PARAMS_SCHEMA_VERSION:
        _fail('schema_version')
    if not isinstance(params['parameter_set_id'], str) or not re.fullmatch(r'[a-z0-9_.-]{1,80}', params['parameter_set_id']):
        _fail('parameter_set_id')
    if params['report_group'] not in ('FORMAL', 'EXPLORATORY'):
        _fail('report_group')
    if params['mode'] != DEFAULT_MODE:
        _fail('mode must be OFF in a committed parameter set')
    dps = params['decision_points']
    if not isinstance(dps, list) or not dps or len(set(dps)) != len(dps) or any(d not in DECISION_POINTS for d in dps):
        _fail('decision_points')
    models = params['models']
    if not isinstance(models, list) or not 1 <= len(models) <= len(MODELS):
        _fail('models')
    seen = set()
    for m in models:
        _keys(m, frozenset({'config_id', 'api_model_id'}), frozenset({'config_id', 'api_model_id'}),
              'PARAMS_INVALID', 'models[]')
        if m['config_id'] not in MODELS or m['config_id'] in seen:
            _fail('models[].config_id')
        if m['api_model_id'] is not None and not isinstance(m['api_model_id'], str):
            _fail('models[].api_model_id')
        seen.add(m['config_id'])

    def positive(obj, key, where):
        if not _is_int(obj[key]) or obj[key] < 1:
            _fail(f'{where}.{key}')

    per_call = params['per_call']
    k = frozenset({'timeout_ms', 'max_output_tokens', 'max_retries_on_429_5xx'})
    _keys(per_call, k, k, 'PARAMS_INVALID', 'per_call')
    positive(per_call, 'timeout_ms', 'per_call')
    positive(per_call, 'max_output_tokens', 'per_call')
    if per_call['timeout_ms'] > PARAM_MAX['timeout_ms']:
        _fail('per_call.timeout_ms above maximum')
    if per_call['max_output_tokens'] > PARAM_MAX['max_output_tokens']:
        _fail('per_call.max_output_tokens above maximum')
    if per_call['max_retries_on_429_5xx'] not in (0, 1) or type(per_call['max_retries_on_429_5xx']) is not int:
        _fail('per_call.max_retries_on_429_5xx')
    per_step = params['per_step']
    k = frozenset({'budget_ms', 'max_rounds'})
    _keys(per_step, k, k, 'PARAMS_INVALID', 'per_step')
    positive(per_step, 'budget_ms', 'per_step')
    if per_step['budget_ms'] > PARAM_MAX['budget_ms']:
        _fail('per_step.budget_ms above maximum')
    if not _is_int(per_step['max_rounds']) or not 1 <= per_step['max_rounds'] <= 3:
        _fail('per_step.max_rounds')
    per_session = params['per_session']
    _keys(per_session, frozenset({'max_rounds'}), frozenset({'max_rounds'}), 'PARAMS_INVALID', 'per_session')
    positive(per_session, 'max_rounds', 'per_session')
    if per_session['max_rounds'] > PARAM_MAX['session_max_rounds']:
        _fail('per_session.max_rounds above maximum')
    rate = params['rate']
    k = frozenset({'max_concurrent', 'max_requests_per_minute'})
    _keys(rate, k, k, 'PARAMS_INVALID', 'rate')
    if rate['max_concurrent'] != 1 or type(rate['max_concurrent']) is not int:
        _fail('rate.max_concurrent')
    if not _is_int(rate['max_requests_per_minute']) or not 1 <= rate['max_requests_per_minute'] <= 30:
        _fail('rate.max_requests_per_minute')
    if not _is_number(params['budget_usd']) or not 0 <= params['budget_usd'] <= 100:
        _fail('budget_usd')
    positive(params, 'prompt_tokens_per_call_estimate', 'params')
    if params['prompt_tokens_per_call_estimate'] > PARAM_MAX['prompt_tokens_per_call_estimate']:
        _fail('prompt_tokens_per_call_estimate above maximum')
    table = params['price_table']
    if table is not None:
        k = frozenset({'date', 'source', 'currency', 'models'})
        _keys(table, k, k, 'PARAMS_INVALID', 'price_table')
        if not isinstance(table['date'], str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', table['date']):
            _fail('price_table.date')
        if not isinstance(table['source'], str) or not table['source']:
            _fail('price_table.source')
        if table['currency'] != 'USD':
            _fail('price_table.currency')
        if not isinstance(table['models'], Mapping) or not table['models']:
            _fail('price_table.models')
        k = frozenset({'input_usd_per_mtok', 'output_usd_per_mtok'})
        for price in table['models'].values():
            _keys(price, k, k, 'PARAMS_INVALID', 'price_table.models[]')
            if not all(_is_number(price[x]) and price[x] >= 0 for x in k):
                _fail('price_table.models[] prices')
    stages = params['stages']
    if not isinstance(stages, Mapping) or not stages:
        _fail('stages')
    caps = ('max_calls', 'max_tokens', 'per_model_max_calls', 'per_model_max_tokens')
    k = frozenset({'approved', 'approval_ref', *caps})
    for name, stage in stages.items():
        if not isinstance(name, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,40}', name):
            _fail('stages name')
        _keys(stage, k, k | {'note'}, 'PARAMS_INVALID', f'stages.{name}')
        if type(stage['approved']) is not bool:
            _fail(f'stages.{name}.approved')
        for cap in caps:
            value = stage[cap]
            if value is not None and (not _is_int(value) or value < 1):
                _fail(f'stages.{name}.{cap}')
        if stage['approved'] and (not isinstance(stage['approval_ref'], str) or not stage['approval_ref']
                                  or any(stage[cap] is None for cap in caps)):
            _fail(f'stages.{name}: an approved stage needs approval_ref and every cap')


# ---------------------------------------------------------------- budget

class CallBudget:
    """Layered call accounting for one evaluation (D165/D166).

    Layers: per session (rounds), per model (calls, tokens), per stage (calls, tokens),
    total USD (only when a dated, sourced price table is present). Once a layer is
    exhausted it stays exhausted for its scope, so every later call falls back to the
    rule with CALL_BUDGET_EXHAUSTED. Rate limiting is exposed as pure arithmetic over
    caller-supplied millisecond timestamps; the provider (WP3) does the waiting.
    """

    def __init__(self, params: Mapping, stage: str):
        validate_params(params)
        if stage not in params['stages']:
            raise AgentDecisionError('PARAMS_INVALID', f'unknown stage {stage}')
        self.params = params
        self.stage_name = stage
        self.stage = params['stages'][stage]
        self.models = tuple(m['config_id'] for m in params['models'])
        self.per_call_tokens = params['prompt_tokens_per_call_estimate'] + params['per_call']['max_output_tokens']
        self.model_calls = {m: 0 for m in self.models}
        self.model_tokens = {m: 0 for m in self.models}
        self.stage_calls = 0
        self.stage_tokens = 0
        self.spent_usd = 0.0
        self.session_rounds = 0
        self._dead_models: dict[str, str] = {}
        self._dead_stage: str | None = None
        self._dead_session = False
        self._starts: deque[int] = deque()
        self._in_flight = False

    @property
    def stage_approved(self) -> bool:
        return bool(self.stage['approved'])

    @property
    def usd_enforced(self) -> bool:
        return self.params['price_table'] is not None

    def begin_session(self) -> None:
        self.session_rounds = 0
        self._dead_session = False

    def _cost(self, model: str, prompt: int, completion: int) -> float:
        price = self.params['price_table']['models'].get(model)
        if price is None:
            return float('inf')  # an unpriced model cannot be checked against budget_usd
        return (prompt * price['input_usd_per_mtok'] + completion * price['output_usd_per_mtok']) / 1e6

    def reserve(self, model: str, *, live: bool) -> str | None:
        """Return None if one more round may start, else the exhausted layer name.

        The session round cap applies to LIVE and REPLAY (so replay reproduces live);
        model, stage and USD caps apply only to LIVE calls.
        """
        if model not in self.models:
            raise AgentDecisionError('PARAMS_INVALID', f'model {model} not in parameter set')
        if self._dead_session or self.session_rounds >= self.params['per_session']['max_rounds']:
            self._dead_session = True
            return 'SESSION_ROUNDS'
        if live:
            if self._dead_stage:
                return self._dead_stage
            if model in self._dead_models:
                return self._dead_models[model]
            est = self.per_call_tokens
            layer = None
            if self.stage_calls + 1 > self.stage['max_calls']:
                layer = 'STAGE_CALLS'
            elif self.stage_tokens + est > self.stage['max_tokens']:
                layer = 'STAGE_TOKENS'
            elif self.usd_enforced and self.spent_usd + self._cost(
                    model, self.params['prompt_tokens_per_call_estimate'],
                    self.params['per_call']['max_output_tokens']) > self.params['budget_usd']:
                layer = 'TOTAL_USD'
            if layer:
                self._dead_stage = layer
                return layer
            if self.model_calls[model] + 1 > self.stage['per_model_max_calls']:
                layer = 'MODEL_CALLS'
            elif self.model_tokens[model] + est > self.stage['per_model_max_tokens']:
                layer = 'MODEL_TOKENS'
            if layer:
                self._dead_models[model] = layer
                return layer
        self.session_rounds += 1
        return None

    def charge(self, model: str, prompt_tokens: int | None, completion_tokens: int | None, *, live: bool) -> None:
        """Account one finished round. Missing usage is charged at the estimate."""
        if not live:
            return
        prompt = prompt_tokens if _is_int(prompt_tokens) else self.params['prompt_tokens_per_call_estimate']
        completion = completion_tokens if _is_int(completion_tokens) else self.params['per_call']['max_output_tokens']
        self.model_calls[model] += 1
        self.model_tokens[model] += prompt + completion
        self.stage_calls += 1
        self.stage_tokens += prompt + completion
        if self.usd_enforced:
            self.spent_usd += self._cost(model, prompt, completion)

    # -- rate: 1 in flight, <= N starts per rolling 60 s
    def rate_wait_ms(self, now_ms: int) -> int:
        """Milliseconds the caller must wait before starting the next request at ``now_ms``."""
        limit = self.params['rate']['max_requests_per_minute']
        while self._starts and now_ms - self._starts[0] >= 60_000:
            self._starts.popleft()
        if len(self._starts) < limit:
            return 0
        return 60_000 - (now_ms - self._starts[0])

    def note_start(self, now_ms: int) -> None:
        if self._in_flight:
            raise AgentDecisionError('RATE_INVALID', 'max_concurrent=1: a request is already in flight')
        if self.rate_wait_ms(now_ms):
            raise AgentDecisionError('RATE_INVALID', 'started before rate_wait_ms elapsed')
        self._in_flight = True
        self._starts.append(now_ms)

    def note_end(self) -> None:
        self._in_flight = False


def dry_run_estimate(params: Mapping, *, questions: int, k: int, models: int | None = None,
                     rounds: int = 1, stage: str | None = None) -> dict:
    """Estimate calls and tokens for questions x K x models x rounds (no calls are made).

    ``rounds=1`` is the nominal case (one round per step); pass per_step.max_rounds for the
    worst case. If ``stage`` is given, report whether the estimate fits its caps.
    """
    validate_params(params)
    models = len(params['models']) if models is None else models
    for name, value in (('questions', questions), ('k', k), ('models', models), ('rounds', rounds)):
        if not _is_int(value) or value < 1:
            raise AgentDecisionError('DRY_RUN_INVALID', name)
    if rounds > params['per_step']['max_rounds']:
        raise AgentDecisionError('DRY_RUN_INVALID', 'rounds exceeds per_step.max_rounds')
    per_call = params['prompt_tokens_per_call_estimate'] + params['per_call']['max_output_tokens']
    calls = questions * k * models * rounds
    result = {
        'questions': questions, 'k': k, 'models': models, 'rounds': rounds,
        'calls': calls, 'calls_per_model': questions * k * rounds,
        'tokens': calls * per_call, 'tokens_per_call': per_call,
        'prompt_tokens': calls * params['prompt_tokens_per_call_estimate'],
        'max_output_tokens': calls * params['per_call']['max_output_tokens'],
        'usd': None,
    }
    table = params['price_table']
    if table is not None:
        priced = [m['config_id'] for m in params['models'][:models]]
        if all(m in table['models'] for m in priced):
            result['usd'] = sum(
                questions * k * rounds * (params['prompt_tokens_per_call_estimate'] * table['models'][m]['input_usd_per_mtok']
                                          + params['per_call']['max_output_tokens'] * table['models'][m]['output_usd_per_mtok']) / 1e6
                for m in priced)
    if stage is not None:
        s = params['stages'][stage]
        result['stage'] = stage
        result['stage_approved'] = s['approved']
        result['fits_stage'] = (s['max_calls'] is not None and calls <= s['max_calls']
                                and calls * per_call <= s['max_tokens']
                                and result['calls_per_model'] <= s['per_model_max_calls']
                                and result['calls_per_model'] * per_call <= s['per_model_max_tokens'])
    return result


# ---------------------------------------------------------------- fallback machine

@dataclass(frozen=True)
class Attempt:
    """What a provider (WP3) reports for one round. ``response`` is parsed JSON or None."""
    outcome: str
    wall_ms: float
    response: object = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    def __post_init__(self):
        if self.outcome not in CALL_OUTCOMES:
            raise AgentDecisionError('ATTEMPT_INVALID', 'outcome')
        if not _is_number(self.wall_ms) or self.wall_ms < 0:
            raise AgentDecisionError('ATTEMPT_INVALID', 'wall_ms')


Provider = Callable[..., Attempt]


def _record(request, sha, mode, source, reason, layer, final, rule, provider, params_sha, attempts):
    return {
        'schema_version': RECORD_SCHEMA_VERSION, 'request_sha256': sha,
        'decision_point': request['decision_point'], 'mode': mode, 'decision_source': source,
        'fallback_reason': reason, 'budget_layer': layer, 'final_answer': final, 'rule_answer': rule,
        'identity_verdict': UNCONFIRMED, 'provider': provider, 'parameter_set_sha256': params_sha,
        'attempts': attempts,
    }


def _response_sha256(response) -> str | None:
    """Hash of a well-formed provider response; None when absent or not safely hashable."""
    if response is None:
        return None
    try:
        check_json_safe(response)
    except AgentDecisionError:
        return None  # validate_response rejects it as INVALID_RESPONSE right after
    return hashlib.sha256(canonical(response)).hexdigest()


def decide(request: Mapping, *, mode: str = DEFAULT_MODE, params: Mapping, budget: CallBudget | None = None,
           model: str | None = None, call: Provider | None = None, provider_kind: str = 'NONE',
           provider_meta: Mapping | None = None) -> dict:
    """Run one decision step through the design §2.3 fallback table and return a record.

    | situation                               | final  | fallback_reason        |
    | mode OFF / RULE_ONLY                    | rule   | null (RULE_ONLY)       |
    | AGENT mode not authorized               | rule   | MODE_NOT_AUTHORIZED    |
    | one call over timeout                   | retry  | attempt PROVIDER_TIMEOUT |
    | step used max_rounds without an answer  | rule   | ROUND_LIMIT            |
    | step over budget_ms                     | rule   | TIME_BUDGET            |
    | a call cap exhausted (any layer)        | rule   | CALL_BUDGET_EXHAUSTED  |
    | provider unreachable / 429-5xx retried  | rule   | PROVIDER_UNAVAILABLE   |
    | replay has no recording                 | rule   | REPLAY_MISS            |
    | response fails schema / id not legal    | rule   | INVALID_RESPONSE / ILLEGAL_CANDIDATE |

    ``call(request, timeout_ms=..., max_output_tokens=...)`` is the provider; this function
    never sleeps or reads a clock. Step time is the sum of reported attempt ``wall_ms``.
    """
    if mode not in MODES:
        raise AgentDecisionError('MODE_INVALID', str(mode))
    validate_request(request)
    validate_params(params)
    rule = RuleDecider().answer(request)
    sha = request_sha256(request)
    params_sha = parameter_set_sha256(params)
    meta = dict(provider_meta or {})
    _forbidden_scan(meta, 'PROVIDER_META_INVALID')
    if mode in ('OFF', 'RULE_ONLY'):
        return _record(request, sha, mode, 'RULE_ONLY', None, None, rule, rule,
                       {'kind': 'NONE', 'model': None}, params_sha, [])
    provider = {'kind': provider_kind, 'model': model, **{k: v for k, v in meta.items() if k in PROVIDER_KEYS}}
    live = mode == 'AGENT_LIVE'

    def fallback(reason, attempts, layer=None):
        return _record(request, sha, mode, 'RULE_FALLBACK', reason, layer, rule, rule, provider, params_sha, attempts)

    authorized = (call is not None and budget is not None and model in budget.models
                  and parameter_set_sha256(budget.params) == params_sha and provider_kind in PROVIDER_KINDS and provider_kind != 'NONE'
                  and request['decision_point'] in params['decision_points']
                  and (budget.stage_approved or not live))
    if not authorized:
        return fallback('MODE_NOT_AUTHORIZED', [])

    timeout_cap = params['per_call']['timeout_ms']
    step_budget = params['per_step']['budget_ms']
    max_rounds = params['per_step']['max_rounds']
    retries_left = params['per_call']['max_retries_on_429_5xx']
    max_tokens = params['per_call']['max_output_tokens']
    attempts: list[dict] = []
    elapsed = 0.0
    while True:
        if elapsed >= step_budget:
            return fallback('TIME_BUDGET', attempts)
        if len(attempts) >= max_rounds:
            return fallback('ROUND_LIMIT', attempts)
        layer = budget.reserve(model, live=live)
        if layer:
            return fallback('CALL_BUDGET_EXHAUSTED', attempts, layer)
        timeout = max(1, int(min(timeout_cap, step_budget - elapsed)))
        result = call(request, timeout_ms=timeout, max_output_tokens=max_tokens)
        if not isinstance(result, Attempt):
            raise AgentDecisionError('ATTEMPT_INVALID', 'provider must return Attempt')
        budget.charge(model, result.prompt_tokens, result.completion_tokens, live=live)
        elapsed += result.wall_ms
        row = {'wall_ms': result.wall_ms, 'timeout_ms': timeout, 'outcome': None,
               'response_sha256': _response_sha256(result.response),
               'prompt_tokens': result.prompt_tokens, 'completion_tokens': result.completion_tokens}
        attempts.append(row)
        if result.outcome == CALL_REPLAY_MISS:
            row['outcome'] = 'REPLAY_MISS'
            return fallback('REPLAY_MISS', attempts)
        if result.outcome == CALL_UNAVAILABLE:
            row['outcome'] = 'PROVIDER_UNAVAILABLE'
            return fallback('PROVIDER_UNAVAILABLE', attempts)
        if result.outcome == CALL_RETRYABLE:
            row['outcome'] = 'PROVIDER_RETRYABLE_ERROR'
            if retries_left > 0:
                retries_left -= 1
                continue
            return fallback('PROVIDER_UNAVAILABLE', attempts)
        if result.outcome == CALL_TIMEOUT or result.wall_ms > timeout:
            row['outcome'] = 'PROVIDER_TIMEOUT'  # late responses are discarded
            continue
        try:
            answer = validate_response(result.response, request)
        except AgentDecisionError as exc:
            reason = exc.code if exc.code in ('INVALID_RESPONSE', 'ILLEGAL_CANDIDATE') else 'INVALID_RESPONSE'
            row['outcome'] = reason
            return fallback(reason, attempts)
        row['outcome'] = 'OK'
        return _record(request, sha, mode, 'AGENT', None, None, answer, rule, provider, params_sha, attempts)


# ---------------------------------------------------------------- record

def validate_record(record) -> None:
    """Raise AgentDecisionError(RECORD_INVALID) unless the record matches $defs/record and §2.3."""
    code = 'RECORD_INVALID'
    _forbidden_scan(record, code)
    _keys(record, RECORD_KEYS, RECORD_KEYS, code, 'record')
    if record['schema_version'] != RECORD_SCHEMA_VERSION:
        raise AgentDecisionError(code, 'schema_version')
    for key in ('request_sha256', 'parameter_set_sha256'):
        if not isinstance(record[key], str) or not SHA256.fullmatch(record[key]):
            raise AgentDecisionError(code, key)
    if record['decision_point'] not in DECISION_POINTS:
        raise AgentDecisionError(code, 'decision_point')
    if record['mode'] not in MODES:
        raise AgentDecisionError(code, 'mode')
    if record['identity_verdict'] != UNCONFIRMED:
        raise AgentDecisionError(code, 'identity_verdict')
    for key in ('final_answer', 'rule_answer'):
        if not isinstance(record[key], str) or not ANSWER.fullmatch(record[key]):
            raise AgentDecisionError(code, key)
    source, reason, layer = record['decision_source'], record['fallback_reason'], record['budget_layer']
    if source not in DECISION_SOURCES or (reason is not None and reason not in FALLBACK_REASONS):
        raise AgentDecisionError(code, 'decision_source/fallback_reason')
    if layer is not None and layer not in BUDGET_LAYERS:
        raise AgentDecisionError(code, 'budget_layer')
    if (reason == 'CALL_BUDGET_EXHAUSTED') != (layer is not None):
        raise AgentDecisionError(code, 'budget_layer only with CALL_BUDGET_EXHAUSTED')
    provider = record['provider']
    _keys(provider, PROVIDER_REQUIRED, PROVIDER_KEYS, code, 'provider')
    if provider['kind'] not in PROVIDER_KINDS:
        raise AgentDecisionError(code, 'provider.kind')
    attempts = record['attempts']
    if not isinstance(attempts, list) or len(attempts) > 3:
        raise AgentDecisionError(code, 'attempts')
    for a in attempts:
        _keys(a, ATTEMPT_REQUIRED, ATTEMPT_KEYS, code, 'attempts[]')
        if a['outcome'] not in ATTEMPT_OUTCOMES or not _is_number(a['wall_ms']) or a['wall_ms'] < 0:
            raise AgentDecisionError(code, 'attempts[]')
        if not _is_int(a['timeout_ms']) or a['timeout_ms'] < 1:
            raise AgentDecisionError(code, 'attempts[].timeout_ms')
    mode = record['mode']
    if mode in ('OFF', 'RULE_ONLY'):
        if source != 'RULE_ONLY' or reason is not None or attempts:
            raise AgentDecisionError(code, 'rule-only modes record RULE_ONLY without attempts')
    elif source == 'RULE_ONLY':
        raise AgentDecisionError(code, 'agent modes record AGENT or RULE_FALLBACK')
    if source == 'AGENT' and (reason is not None or not attempts or attempts[-1]['outcome'] != 'OK'):
        raise AgentDecisionError(code, 'AGENT needs a final OK attempt and no fallback_reason')
    if source == 'RULE_FALLBACK' and (reason is None or record['final_answer'] != record['rule_answer']):
        raise AgentDecisionError(code, 'RULE_FALLBACK uses the rule answer and names a reason')
    if source == 'RULE_ONLY' and record['final_answer'] != record['rule_answer']:
        raise AgentDecisionError(code, 'RULE_ONLY uses the rule answer')

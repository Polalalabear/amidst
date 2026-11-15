"""N1: one-sentence query -> structured tag fields. Contract: docs/contracts/NL_QUERY_PARSE_V1.md.

Fallback chain API -> LOCAL -> RULES. Every answer (model or rules) passes ``validate_parse`` against the run's closed
catalog vocabulary before it is returned. ``parse_rules`` is a pure function and works alone. Transport/extraction helpers
are the #526 adapter pieces from ``agent_providers``; the API key is read from the environment at call time on the server only.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import logging
import math
import os
import re
import time

from amidst.q1q5 import agent_providers as ap
from amidst.q1q5.agent_wiring import ad
from amidst.q1q5.q3_rules import GRAMMAR, TRACKING_VERBS, _terms

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 'q-demo.nl-query-parse.v1'
MODES = ('API', 'LOCAL', 'RULES')
ACTIONS = ('查找', '追蹤')
FIELDS = ('action', 'location', 'target', 'time', 'unrecognized')
MAX_TEXT = 200
MAX_UNRECOGNIZED = 16
MAX_PIECE = 64
MAX_SECONDS = 10 * 86400   # elapsed source time cap (10 days): a typed or model-made 1e150 is not a time range
DEFAULT_TIMEOUT_MS = 2500


class NlSchemaError(ValueError):
    pass


class NlClientError(RuntimeError):
    """code: NOT_CONFIGURED | TIMEOUT | UNAVAILABLE | SCHEMA_REJECTED | a guard denial (api_budget.REASONS, e.g. API_DISABLED)"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class NlVocabulary:
    class_labels: tuple
    color_labels: tuple
    region_ids: tuple
    class_aliases: Mapping
    color_aliases: Mapping
    region_aliases: Mapping

    @property
    def target_labels(self) -> tuple:
        return (*self.class_labels, *self.color_labels)


def vocabulary_from_catalog(catalog: Mapping) -> NlVocabulary:
    """The run's server catalog is the one vocabulary (same source as Q3 and the tag panel menus)."""
    def aliases(values, table):
        out = {v: v for v in values}
        out.update({k: v for k, v in table.items() if v in values})
        return out
    classes, colors, regions = tuple(catalog['class_labels']), tuple(catalog['color_labels']), tuple(catalog['region_ids'])
    return NlVocabulary(classes, colors, regions, aliases(classes, catalog.get('class_aliases', {})),
                        aliases(colors, catalog.get('color_aliases', {})), aliases(regions, catalog.get('region_aliases', {})))


# ---- validation ------------------------------------------------------------------------------------------------
def _num(x):
    return type(x) in (int, float) and math.isfinite(x)


def validate_parse(obj, vocab: NlVocabulary) -> dict:
    if not isinstance(obj, dict) or set(obj) != set(FIELDS):
        raise NlSchemaError('keys')
    if obj['action'] is not None and obj['action'] not in ACTIONS:
        raise NlSchemaError('action')
    for key, allowed in (('location', vocab.region_ids), ('target', vocab.target_labels)):
        v = obj[key]
        if not isinstance(v, list) or any(not isinstance(i, str) or i not in allowed for i in v) or len(set(v)) != len(v):
            raise NlSchemaError(key)
    t = obj['time']
    if t is not None:
        if not isinstance(t, dict) or set(t) != {'start', 'end'} or not (_num(t['start']) and _num(t['end'])) or not 0 <= t['start'] < t['end'] <= MAX_SECONDS:
            raise NlSchemaError('time')
    u = obj['unrecognized']
    if not isinstance(u, list) or len(u) > MAX_UNRECOGNIZED or any(not isinstance(i, str) or not i or len(i) > MAX_PIECE for i in u):
        raise NlSchemaError('unrecognized')
    return {'action': obj['action'], 'location': list(obj['location']), 'target': list(obj['target']),
            'time': None if t is None else {'start': t['start'], 'end': t['end']}, 'unrecognized': list(u)}


# ---- RULES (pure) ----------------------------------------------------------------------------------------------
_TIME = re.compile(r'\d+:\d{2}(?::\d{2})?(?:\.\d+)?|\d+\s*分(?:\s*\d+\s*秒)?|\d+(?:\.\d+)?\s*秒')
_FIND = ('查找', '查詢', '搜尋', '尋找', '找出', '找', '哪些鏡頭', '哪幾台', '哪台', '拍到')
_TRACK = (*TRACKING_VERBS, '追')
_FILLERS = tuple(sorted({*GRAMMAR, *_FIND, *_TRACK, '請', '一下', '出現', '看看', '查'}, key=len, reverse=True))


def _seconds(token: str):
    token = token.replace(' ', '')
    if ':' in token:
        parts = token.split(':')
        nums = [float(p) for p in parts]
        if len(parts) > 2 and (nums[1] >= 60 or nums[2] >= 60) or len(parts) == 2 and nums[1] >= 60:
            return None
        total = 0.0
        for n in nums:
            total = total * 60 + n
    elif '分' in token:
        m, _, s = token.partition('分')
        total = int(m) * 60 + (int(s.rstrip('秒')) if s.rstrip('秒') else 0)
    else:
        total = float(token.rstrip('秒'))
    return int(total) if float(total).is_integer() else total


def parse_rules(text: str, vocab: NlVocabulary) -> dict:
    """Fixed-pattern parser. Pure: no I/O, no clock, no model. Unknown pieces go to ``unrecognized``; nothing is guessed."""
    text = str(text)
    mask = [False] * len(text)

    def hide(a, b):
        mask[a:b] = [True] * (b - a)
    groups = []
    for aliases in (vocab.class_aliases, vocab.color_aliases, vocab.region_aliases):
        found = _terms(text, aliases)
        groups.append(found)
        for a, b, _, _ in found:
            hide(a, b)
    for _, end, term, _ in groups[1]:
        if not term.endswith('色') and text[end:end + 1] == '色':
            hide(end, end + 1)
    times = list(_TIME.finditer(text))
    for m in times:
        hide(m.start(), m.end())
    rest = ''.join(' ' if hidden else ch for ch, hidden in zip(text, mask, strict=True))
    for phrase in _FILLERS:
        rest = rest.replace(phrase, ' ')
    pieces = list(dict.fromkeys(p for p in rest.split() if p))
    window = None
    spans = [(m.group(), _seconds(m.group())) for m in times]
    if len(spans) == 2 and all(s is not None and s <= MAX_SECONDS for _, s in spans) and spans[0][1] < spans[1][1]:
        window = {'start': spans[0][1], 'end': spans[1][1]}
    else:
        pieces.extend(t for t, _ in spans)

    def uniq(items):
        return list(dict.fromkeys(items))
    action = '追蹤' if any(v in text for v in _TRACK) else '查找' if any(v in text for v in _FIND) else None
    return {'action': action, 'location': uniq(x[3] for x in groups[2]),
            'target': uniq([x[3] for x in groups[0]] + [x[3] for x in groups[1]]), 'time': window,
            'unrecognized': [p[:MAX_PIECE] for p in pieces][:MAX_UNRECOGNIZED]}


# ---- model clients (#526 adapter helpers) ----------------------------------------------------------------------
@dataclass(frozen=True)
class ClientResult:
    parsed: object
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None


def response_schema(vocab: NlVocabulary) -> dict:
    strs = lambda enum: {'type': 'array', 'items': {'type': 'string', 'enum': list(enum)}}  # noqa: E731
    num = {'type': 'number'}
    return {'type': 'object', 'additionalProperties': False, 'required': list(FIELDS), 'properties': {
        'action': {'type': ['string', 'null'], 'enum': [*ACTIONS, None]},
        'location': strs(vocab.region_ids), 'target': strs(vocab.target_labels),
        'time': {'type': ['object', 'null'], 'additionalProperties': False, 'required': ['start', 'end'], 'properties': {'start': num, 'end': num}},
        'unrecognized': {'type': 'array', 'items': {'type': 'string'}}}}


SYSTEM_PROMPT = ('Parse one Chinese sentence into the JSON schema. action: 查找 (find cameras) or 追蹤 (follow one person) or null if the sentence has no cue. '
                 'location/target values must be canonical ids from the vocabulary; use the aliases to map words. time: elapsed seconds {start,end}, or null unless '
                 'both ends are given. Put every piece you cannot map into unrecognized. Never guess a nearest value.')


def _request_doc(text: str, vocab: NlVocabulary) -> dict:
    return {'text': text, 'vocabulary': {'location': dict(vocab.region_aliases), 'target': {**vocab.class_aliases, **vocab.color_aliases}}}


def request_sha256(text: str, vocab: NlVocabulary) -> str:
    return hashlib.sha256(ad.canonical(_request_doc(text, vocab))).hexdigest()


def _call(transport, url, headers, body, timeout_ms, clock):
    start = clock()
    try:
        raw = transport(url=url, headers=headers, body=body, timeout_s=timeout_ms / 1000.0)
    except Exception as exc:  # noqa: BLE001
        if ap._is_timeout_exception(exc):
            raise NlClientError('TIMEOUT') from None
        raise NlClientError('UNAVAILABLE') from None
    finally:
        headers.clear()
    status, data, _ = ap._normalize_transport_output(raw)
    if not 200 <= status < 300:
        raise NlClientError('UNAVAILABLE')
    ok, doc = ap._parse_json_bytes(data)
    if not ok or not isinstance(doc, Mapping):
        raise NlClientError('SCHEMA_REJECTED')
    return doc, (clock() - start) * 1000.0


def _record(client, text, vocab, parsed, usage, wall_ms):
    if client._recorder is None:
        return
    try:
        client._recorder({'request_sha256': request_sha256(text, vocab), 'response': parsed, 'provider': client.provider_kind, 'model': client.model,
                          'usage': {'prompt_tokens': usage[0], 'completion_tokens': usage[1]}, 'wall_ms': wall_ms})
    except Exception as exc:  # noqa: BLE001
        logger.warning('nl_query_parse: recording row rejected: %s', type(exc).__name__)


class OpenAINlClient:
    name = 'API'
    provider_kind = 'OPENAI'

    def __init__(self, *, model='astra6', transport: Callable | None = None, env: Mapping | None = None, prices: Mapping | None = None,
                 recorder: Callable | None = None, endpoint: str = ap.OPENAI_CHAT_URL, clock: Callable[[], float] = time.monotonic):
        if model not in ad.MODELS:
            raise ValueError(f'model must be one of {ad.MODELS}')
        self.model, self._transport, self._env, self._prices = model, transport or ap.default_http_transport, env, dict(prices or {})
        self._recorder, self.endpoint, self._clock = recorder, endpoint, clock

    def __repr__(self):
        return f'OpenAINlClient(model={self.model!r})'

    def _key(self):
        key = (self._env if self._env is not None else os.environ).get('OPENAI_API_KEY')
        return key.strip() if isinstance(key, str) and key.strip() else None

    def parse(self, text, vocab, timeout_ms) -> ClientResult:
        key = self._key()
        if key is None:
            raise NlClientError('NOT_CONFIGURED')
        payload = {'model': self.model, 'messages': [{'role': 'system', 'content': SYSTEM_PROMPT},
                   {'role': 'user', 'content': ad.canonical(_request_doc(text, vocab)).decode('ascii')}],
                   'response_format': {'type': 'json_schema', 'json_schema': {'name': 'nl_query_parse_v1', 'strict': True, 'schema': response_schema(vocab)}}}
        headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        del key
        doc, wall_ms = _call(self._transport, self.endpoint, headers, ad.canonical(payload), timeout_ms, self._clock)
        parsed = ap._extract_openai_response_object(doc)
        usage = ap._extract_tokens(doc)
        price = self._prices.get(self.model)
        cost = None
        if price and None not in usage:
            cost = (usage[0] * price['input_usd_per_mtok'] + usage[1] * price['output_usd_per_mtok']) / 1e6
        _record(self, text, vocab, parsed, usage, wall_ms)
        return ClientResult(parsed, *usage, cost)


class OllamaNlClient:
    name = 'LOCAL'
    provider_kind = 'OLLAMA_LOOPBACK'

    def __init__(self, *, model: str, endpoint: str = ap.DEFAULT_OLLAMA_ENDPOINT, transport: Callable | None = None,
                 recorder: Callable | None = None, clock: Callable[[], float] = time.monotonic):
        self.endpoint = ap.validate_ollama_endpoint(endpoint)
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,100}', model):
            raise ValueError('invalid Ollama model name')
        self.model, self._transport, self._recorder, self._clock = model, transport or ap.default_http_transport, recorder, clock

    def parse(self, text, vocab, timeout_ms) -> ClientResult:
        payload = {'model': self.model, 'stream': False, 'format': response_schema(vocab), 'options': {'temperature': 0},
                   'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': ad.canonical(_request_doc(text, vocab)).decode('ascii')}]}
        doc, wall_ms = _call(self._transport, f'{self.endpoint}/api/chat', {'Content-Type': 'application/json'}, ad.canonical(payload), timeout_ms, self._clock)
        parsed = ap._extract_ollama_response_object(doc)
        usage = ap._extract_tokens(doc)
        _record(self, text, vocab, parsed, usage, wall_ms)
        return ClientResult(parsed, *usage, 0.0)


class ReplayNlClient:
    """Answers from recorded rows (request hash -> answer); a miss is UNAVAILABLE. Never calls anything."""

    def __init__(self, name: str, rows):
        self.name, self._rows = name, {r['request_sha256']: r for r in rows}

    def parse(self, text, vocab, timeout_ms) -> ClientResult:
        row = self._rows.get(request_sha256(text, vocab))
        if row is None:
            raise NlClientError('UNAVAILABLE')
        usage = row.get('usage') or {}
        return ClientResult(row['response'], usage.get('prompt_tokens'), usage.get('completion_tokens'), 0.0)


def pinned_prices(params: Mapping | None) -> dict:
    table = (params or {}).get('price_table')
    return dict(table['models']) if isinstance(table, Mapping) and isinstance(table.get('models'), Mapping) else {}


def clients_from_environment(env: Mapping | None = None, guard=None) -> dict:
    """Server-side wiring from environment. A layer without configuration is simply absent (-> NOT_CONFIGURED). The key is never read here.
    The paid layer always goes through the shared spend guard (api_budget): server switch off (default) -> API_DISABLED."""
    from amidst.q1q5 import api_budget as ab
    env = os.environ if env is None else env
    guard = guard if guard is not None else ab.shared_guard(env)
    out = {}
    if not guard.config.enabled:
        out['API'] = ab.DisabledApiClient()
    elif env.get('OPENAI_API_KEY', '').strip():
        try:
            out['API'] = ab.GuardedNlClient(OpenAINlClient(model=env.get('AMIDST_NL_OPENAI_MODEL', 'astra6'), env=env, prices=guard.config.prices), guard)
        except ValueError:
            pass
    if env.get('AMIDST_NL_OLLAMA_MODEL'):
        try:
            out['LOCAL'] = OllamaNlClient(model=env['AMIDST_NL_OLLAMA_MODEL'], endpoint=env.get('AMIDST_NL_OLLAMA_ENDPOINT', ap.DEFAULT_OLLAMA_ENDPOINT))
        except (ValueError, ad.AgentDecisionError):
            pass
    return out


# ---- orchestration ---------------------------------------------------------------------------------------------
def parse_nl_query(text, vocab: NlVocabulary, *, mode: str = 'RULES', api=None, local=None, timeout_ms: int = DEFAULT_TIMEOUT_MS,
                   clock: Callable[[], float] = time.monotonic) -> dict:
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_TEXT:
        raise ValueError('text must be 1..200 characters')
    if mode not in MODES:
        raise ValueError('mode')
    text = text.strip()
    t_start = clock()
    chain = {'API': [('API', api), ('LOCAL', local)], 'LOCAL': [('LOCAL', local)], 'RULES': []}[mode]
    trail, costs = [], []
    result = None
    for name, client in chain:
        if client is None:
            trail.append({'parser': name, 'outcome': 'NOT_CONFIGURED', 'latency_ms': 0.0})
            continue
        s = clock()
        outcome, parsed = 'OK', None
        cost = 0.0 if name == 'LOCAL' else None   # an attempted paid call whose cost is not reported stays unknown
        try:
            res = client.parse(text, vocab, timeout_ms)
            cost = res.cost_usd
            parsed = validate_parse(res.parsed, vocab)
        except NlClientError as exc:
            outcome = exc.code
        except NlSchemaError:
            outcome = 'SCHEMA_REJECTED'
        except Exception:  # noqa: BLE001
            outcome = 'UNAVAILABLE'
        elapsed = (clock() - s) * 1000.0
        if outcome == 'OK' and elapsed > timeout_ms:
            outcome, parsed = 'TIMEOUT', None
        trail.append({'parser': name, 'outcome': outcome, 'latency_ms': round(elapsed, 3)})
        costs.append(cost)
        if outcome == 'OK':
            result = (name, parsed)
            break
    if result is None:
        s = clock()
        parsed = validate_parse(parse_rules(text, vocab), vocab)
        trail.append({'parser': 'RULES', 'outcome': 'OK', 'latency_ms': round((clock() - s) * 1000.0, 3)})
        costs.append(0.0)
        result = ('RULES', parsed)
    total_cost = None if any(c is None for c in costs) else round(sum(costs), 9)
    return {'schema_version': SCHEMA_VERSION, **result[1], 'parser': result[0], 'latency_ms': round((clock() - t_start) * 1000.0, 3),
            'cost_usd': total_cost, 'fallback_trail': trail}

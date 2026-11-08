"""Epic D path (b): one natural-language sentence -> query-window options (docs/specs/EPIC_D_AGENTIC_V1.md §3-§7).

The result only pre-fills the case1/case2 query window; nothing is executed here and the user must confirm in the UI.
Inputs are the sentence plus a closed server catalog (class/color/region labels). No private evaluation, script or rendering data
can enter: requests are whitelisted and scanned for forbidden keys. Provider kinds: RECORDED (default,
offline replay), OLLAMA (loopback only), OPENAI (off unless enabled; key read only from the environment and never
stored or echoed) and NONE (rules only). Every outcome carries a step trace ``q-core.agent-trace.v1`` and the labels
EXPLORATORY / UNCONFIRMED. Same recording + same input => byte-identical response.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from copy import deepcopy
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from amidst.q1q5.clock_mapping import ClockMappingError, _literal
from amidst.q1q5.llm_provider import CallResult, ProviderError
from amidst.q1q5.openai_prediction import FORBIDDEN_KEYS, default_https_transport
from amidst.q1q5.q3_parse import _strict_object, validate_literal_output
from amidst.q1q5.q3_rules import parse_rule
from amidst.q1q5.store import canonical_hash

REQUEST_SCHEMA = 'q-core.nl-parse-request.v1'
RESPONSE_SCHEMA = 'q-core.nl-parse-response.v1'
TRACE_SCHEMA = 'q-core.agent-trace.v1'
RECORDING_SCHEMA = 'q-core.agent-recording.v1'
TEMPLATE_VERSION = 'q3-parse.v2'
TEMPLATE_PATH = Path(__file__).resolve().parents[3] / 'configs/q1q5/prompts/q3_parse_v2.txt'
FIXTURE_RECORDING = Path(__file__).resolve().parents[3] / 'configs/epicd/nl_recording_synthetic_fixture_v1.json'
SYNTHETIC_FIXTURE = 'SYNTHETIC_FIXTURE'
QWEN_RECORDED = 'QWEN3_RECORDED'
KINDS = ('search', 'track')
PROVIDER_KINDS = ('RECORDED', 'OLLAMA', 'OPENAI', 'NONE')
GT_READ = ''.join(('gt', '_read'))
GT_PREFIX = ''.join(('gt', '_'))
# PROPOSED engineering defaults, not measured parameters (C-2 pending): Qwen3 1.7B median was 5.8 s untruncated (Q3).
DEFAULT_BUDGET = {'call_timeout_ms': 15000, 'total_budget_ms': 15000, 'max_steps': 2, 'source': 'PROPOSED_C2_PENDING'}

_COLOR_ZH = {'紅': 'red', '藍': 'blue', '黑': 'black', '白': 'white', '綠': 'green', '黃': 'yellow', '灰': 'gray',
             '橘': 'orange', '紫': 'purple', '棕': 'brown', '粉紅': 'pink'}
_CLASS_ZH = {'人': 'person', '人物': 'person', '行人': 'person', '筆電': 'laptop', '筆記型電腦': 'laptop',
             '背包': 'backpack', '椅子': 'chair', '車': 'car', '車輛': 'car', '水瓶': 'bottle', '杯子': 'cup',
             '手機': 'cell_phone'}
_TZ = ZoneInfo('Asia/Taipei')
_DAY = date(2026, 1, 1)
_LLM_CATALOG_FIELDS = ('class_labels', 'color_labels', 'camera_ids', 'region_ids',
                       'class_aliases', 'color_aliases', 'camera_aliases', 'region_aliases')


class NlParseError(ValueError):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)


class ReplayMismatch(NlParseError):
    def __init__(self, message='Recorded provider input mismatch'):
        super().__init__('REPLAY_MISS', message)


def _check_forbidden(value):
    if isinstance(value, dict):
        for key, child in value.items():
            low = str(key).lower()
            if low in FORBIDDEN_KEYS or low.startswith(GT_PREFIX):
                raise NlParseError('FORBIDDEN_INFERENCE_INPUT')
            _check_forbidden(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_forbidden(child)


def _template():
    return TEMPLATE_PATH.read_text(encoding='utf-8').rstrip('\n')


def template_sha256():
    import hashlib
    return hashlib.sha256(_template().encode()).hexdigest()


# ---- catalog -----------------------------------------------------------------------------------------------------
def catalog_from_run_summary(run):
    """Closed catalog from one q_bootstrap run row (same source the UI menus use). Labels outside it never pass."""
    classes = (run.get('supported_classes') or {})
    class_labels = list(classes.get('class_labels') or [])
    color_labels = list((classes.get('color_vocabulary') or {}).get('labels') or [])
    class_aliases = {k: v for k, v in (classes.get('aliases') or {}).items() if v in class_labels}
    class_aliases.update({k: v for k, v in _CLASS_ZH.items() if v in class_labels})
    color_aliases = {k: v for k, v in _COLOR_ZH.items() if v in color_labels}
    color_aliases.update({k: k for k in color_labels})
    rows = ((run.get('region_catalog') or {}).get('regions')
            or [{'region_id': r.get('region_id'), 'label': r.get('display_name')}
                for r in (run.get('region_graph') or {}).get('regions', run.get('regions') or [])])
    region_ids, region_aliases = [], {}
    for row in rows:
        rid = row.get('region_id')
        if not isinstance(rid, str) or not rid:
            continue
        region_ids.append(rid)
        region_aliases[rid] = rid
        label = row.get('label') or row.get('display_name')
        if isinstance(label, str) and label:
            region_aliases[label] = rid
    class_aliases.update({k: k for k in class_labels})
    return normalize_catalog({'class_labels': class_labels, 'color_labels': color_labels, 'region_ids': region_ids,
                              'class_aliases': class_aliases, 'color_aliases': color_aliases,
                              'region_aliases': region_aliases})


def normalize_catalog(raw):
    if not isinstance(raw, dict):
        raise NlParseError('CATALOG_INVALID')
    c = {'class_labels': [], 'color_labels': [], 'camera_ids': [], 'region_ids': [], 'class_aliases': {},
         'color_aliases': {}, 'camera_aliases': {}, 'region_aliases': {}}
    for key in c:
        if key in raw:
            c[key] = deepcopy(raw[key])
    for key in ('class_labels', 'color_labels', 'camera_ids', 'region_ids'):
        if not isinstance(c[key], list) or any(not isinstance(v, str) or not v for v in c[key]):
            raise NlParseError('CATALOG_INVALID')
    for table, values in (('class_aliases', 'class_labels'), ('color_aliases', 'color_labels'),
                          ('camera_aliases', 'camera_ids'), ('region_aliases', 'region_ids')):
        if not isinstance(c[table], dict) or any(not isinstance(k, str) or not k or v not in c[values]
                                                 for k, v in c[table].items()):
            raise NlParseError('CATALOG_INVALID')
    _check_forbidden(c)
    return c


# ---- literals -> form --------------------------------------------------------------------------------------------
def normalize_clock(literal, inherited=None):
    """'下午一點半' -> ('13:30:00', '下午'). Chinese twelve-hour literals need 上午/下午 (same rule as Q3)."""
    when, period = _literal(literal, _DAY, _TZ, inherited)
    return when.astimezone(_TZ).strftime('%H:%M:%S'), period


def _lookup(table, term):
    return next((v for k, v in table.items() if term is not None and k.casefold() == term.casefold()), None)


def build_form(kind, output, catalog):
    """Q3 literal object -> ({start,end,regionIds,classLabel,colorLabel}, missing, warnings) or (None, reason, detail)."""
    cls = color = None
    if output['class_term'] is not None:
        cls = _lookup(catalog['class_aliases'], output['class_term'])
        if cls is None:
            return None, 'CLASS_NOT_IN_CATALOG', [output['class_term']]
    if output['color_term'] is not None:
        color = _lookup(catalog['color_aliases'], output['color_term'])
        if color is None:
            return None, 'COLOR_NOT_IN_CATALOG', [output['color_term']]
        if cls is None and 'person' in catalog['class_labels']:
            cls = 'person'
        if cls != 'person':
            return None, 'COLOR_REQUIRES_PERSON', [output['color_term']]
    regions = [_lookup(catalog['region_aliases'], t) for t in output['region_terms']]
    if any(r is None for r in regions):
        return None, 'REGION_NOT_IN_CATALOG', [t for t, r in zip(output['region_terms'], regions) if r is None]
    warnings = []
    tl = output['time_literal']
    start = end = ''
    try:
        period = None
        if tl['start']:
            start, period = normalize_clock(tl['start'])
        if tl['end'] and kind == 'search':
            end, _ = normalize_clock(tl['end'], period)
        elif tl['end']:
            warnings.append('追蹤只需要開始時間，已忽略結束時間')
    except ClockMappingError as exc:
        return None, 'TIME_EXPRESSION_INVALID', [str(exc)]
    if tl['date']:
        warnings.append('日期只用於展示時鐘，已忽略')
    if output['camera_terms']:
        warnings.append('查詢窗沒有鏡頭選項，已忽略鏡頭')
    form = {'start': start, 'end': end, 'regionIds': sorted(set(regions)), 'classLabel': cls or '', 'colorLabel': color or ''}
    if not (start or end or form['regionIds'] or form['classLabel']):
        return None, 'NOTHING_PARSED', []
    missing = []
    if kind == 'search':
        if not start or not end:
            missing.append('time')
        if not form['regionIds'] and not form['classLabel']:
            missing.append('regionOrFeature')
    elif not form['classLabel']:
        missing.append('feature')
    return form, missing, warnings


# ---- providers ---------------------------------------------------------------------------------------------------
def _request_for_hash(model, prompt, template, template_version, options):
    import hashlib
    return {'model': model, 'prompt': prompt, 'template_sha256': hashlib.sha256(template.encode()).hexdigest(),
            'template_version': template_version, 'options': dict(options)}


class NoneProvider:
    kind = 'NONE'

    def __init__(self):
        self.info = {'kind': 'NONE', 'model': None, 'model_digest': None, 'options': {}, 'recorded': False,
                     'synthetic_fixture': False, 'recording_id': None, 'recording_sha256': None}

    def generate(self, **_):
        raise ProviderError('PROVIDER_UNAVAILABLE', {})


class RecordedNlProvider:
    """Offline replay. Looks a call up by request hash; an unknown or edited request is a ReplayMismatch, never repaired."""
    kind = 'RECORDED'

    def __init__(self, recording, *, sequential=False):
        try:
            self._load(recording, sequential)
        except ReplayMismatch:
            raise
        except (KeyError, TypeError, AttributeError, ValueError):
            raise ReplayMismatch('Recording is malformed') from None

    def _load(self, recording, sequential):
        if not isinstance(recording, dict) or recording.get('schema_version') != RECORDING_SCHEMA:
            raise ReplayMismatch('Not a q-core.agent-recording.v1')
        if canonical_hash(recording, exclude=('content_sha256',)) != recording.get('content_sha256'):
            raise ReplayMismatch('Recording content hash mismatch')
        if not isinstance(recording.get('entries'), list):
            raise ReplayMismatch('Recording entries missing')
        for entry in recording['entries']:
            if canonical_hash(entry['request']) != entry['request_sha256']:
                raise ReplayMismatch('Recording request hash mismatch')
        self.recording, self.sequential, self.cursor, self.used = deepcopy(recording), sequential, 0, set()
        p = recording['provider']
        self.info = {'kind': 'RECORDED', 'model': p['model'], 'model_digest': p.get('model_digest'),
                     'options': dict(p.get('options') or {}), 'recorded': True,
                     'synthetic_fixture': recording['data_origin'] == SYNTHETIC_FIXTURE,
                     'recording_id': recording['recording_id'], 'recording_sha256': recording['content_sha256'],
                     'data_origin': recording['data_origin'], 'recorded_kind': p['kind']}

    @classmethod
    def from_file(cls, path, **kw):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')), **kw)

    def generate(self, *, model, prompt, template, template_version, options, timeout_ms=None, expected_digest=None):
        request = _request_for_hash(model, prompt, template, template_version, options)
        want = canonical_hash(request)
        entries = self.recording['entries']
        if self.sequential:
            if self.cursor >= len(entries):
                raise ReplayMismatch('Recorded provider exhausted')
            index = self.cursor
        else:
            index = next((i for i, e in enumerate(entries) if e['request_sha256'] == want), None)
        if index is None or entries[index]['request_sha256'] != want or entries[index]['request'] != request:
            raise ReplayMismatch()
        entry = entries[index]
        self.cursor += 1
        self.used.add(index)
        import hashlib
        record = {'model': model, 'model_digest': self.info['model_digest'], 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                  'raw_output_sha256': hashlib.sha256(entry['raw_output'].encode()).hexdigest() if entry['raw_output'] is not None else None,
                  'stats': {'latency_ms': entry['latency_ms']}}
        if entry['error_code'] is not None:
            raise ProviderError(entry['error_code'], record)
        return CallResult(entry['raw_output'], record)

    def assert_consumed(self):
        if len(self.used) != len(self.recording['entries']):
            raise ReplayMismatch('Unused recorded entries')


class OllamaNlProvider:
    """Local Qwen3 through the existing pinned OllamaProvider (loopback transport only)."""
    kind = 'OLLAMA'

    def __init__(self, provider, *, model, options, model_digest=None):
        self._provider = provider
        self.info = {'kind': 'OLLAMA', 'model': model, 'model_digest': model_digest, 'options': dict(options),
                     'recorded': False, 'synthetic_fixture': False, 'recording_id': None, 'recording_sha256': None}

    def generate(self, **kw):
        return self._provider.generate(**kw)


class OpenAINlProvider:
    """Disabled by default. The key is read from the environment only when enabled=True and is never stored in any
    record, trace, recording, log or repr. Sends only the closed catalog and the user's sentence."""
    kind = 'OPENAI'
    URL = 'https://api.openai.com/v1/chat/completions'

    def __init__(self, *, enabled=False, model=None, env=None, transport=None, options=None):
        self.enabled = bool(enabled)
        self.model = model
        self._transport = transport or default_https_transport
        self._key = None
        if self.enabled:
            source = os.environ if env is None else env
            value = source.get('OPENAI_API_KEY')
            self._key = value if isinstance(value, str) and value.strip() else None
        self.info = {'kind': 'OPENAI', 'model': model, 'model_digest': None, 'options': dict(options or {'temperature': 0}),
                     'recorded': False, 'synthetic_fixture': False, 'recording_id': None, 'recording_sha256': None}

    def __repr__(self):
        return f'OpenAINlProvider(enabled={self.enabled}, model={self.model!r})'

    def generate(self, *, model, prompt, template, template_version, options, timeout_ms, expected_digest=None):
        import hashlib
        if not self.enabled:
            raise ProviderError('DISABLED', {})
        if not self._key or not self.model:
            raise ProviderError('PROVIDER_UNAVAILABLE', {})
        suffix = prompt[len(template) + 1:]
        catalog, encoded = suffix.split('\nUSER_TEXT=', 1)
        body = json.dumps({'model': self.model, 'temperature': options.get('temperature', 0), 'response_format': {'type': 'json_object'},
                           'messages': [{'role': 'system', 'content': template + '\n' + catalog},
                                        {'role': 'user', 'content': json.loads(encoded)}]}, ensure_ascii=True).encode()
        record = {'model': self.model, 'model_digest': None, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                  'raw_output_sha256': None}
        start = time.monotonic()
        try:
            raw = self._transport(url=self.URL, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self._key},
                                  body=body, timeout_s=timeout_ms / 1000)
            output = json.loads(raw)['choices'][0]['message']['content']
            if not isinstance(output, str) or not output.strip():
                raise ValueError
        except TimeoutError:
            record['stats'] = {'latency_ms': (time.monotonic() - start) * 1000}
            raise ProviderError('PROVIDER_TIMEOUT', record) from None
        except (ValueError, KeyError, IndexError, TypeError):
            record['stats'] = {'latency_ms': (time.monotonic() - start) * 1000}
            raise ProviderError('INVALID_RESPONSE', record) from None
        except Exception:  # network/HTTP errors: never echo the exception (may contain headers)
            record['stats'] = {'latency_ms': (time.monotonic() - start) * 1000}
            raise ProviderError('PROVIDER_UNAVAILABLE', record) from None
        record['raw_output_sha256'] = hashlib.sha256(output.encode()).hexdigest()
        record['stats'] = {'latency_ms': (time.monotonic() - start) * 1000}
        return CallResult(output, record)


def default_provider(env=None):
    """Provider chosen by AMIDST_NL_PROVIDER (RECORDED default). OPENAI additionally needs AMIDST_NL_OPENAI_ENABLED=1."""
    env = os.environ if env is None else env
    mode = env.get('AMIDST_NL_PROVIDER', 'RECORDED')
    if mode not in PROVIDER_KINDS:
        raise NlParseError('PROVIDER_INVALID')
    if mode == 'NONE':
        return NoneProvider()
    if mode == 'RECORDED':
        path = env.get('AMIDST_NL_RECORDING')
        return RecordedNlProvider.from_file(Path(path) if path else FIXTURE_RECORDING)
    if mode == 'OPENAI':
        return OpenAINlProvider(enabled=env.get('AMIDST_NL_OPENAI_ENABLED') == '1', model=env.get('AMIDST_NL_OPENAI_MODEL'), env=env)
    from amidst.q1q5.llm_provider import QWEN3_MODEL, LocalHTTPTransport, OllamaProvider
    return OllamaNlProvider(OllamaProvider(LocalHTTPTransport(env.get('AMIDST_NL_OLLAMA_URL', 'http://127.0.0.1:11434'))),
                            model=env.get('AMIDST_NL_OLLAMA_MODEL', QWEN3_MODEL), options={'temperature': 0, 'seed': 7, 'num_predict': 256})


class UnavailableProvider:
    """Stands in when the configured provider cannot be built (missing/corrupt recording, bad mode): every call
    degrades to the rules with ``code`` as the reason instead of failing the request."""

    def __init__(self, kind, code):
        self.kind, self.code = kind, code
        self.info = {'kind': kind, 'model': None, 'model_digest': None, 'options': {}, 'recorded': kind == 'RECORDED',
                     'synthetic_fixture': False, 'recording_id': None, 'recording_sha256': None}

    def generate(self, **_):
        raise ProviderError(self.code, {})


def safe_default_provider(env=None):
    """default_provider() that never raises: a build failure becomes an UnavailableProvider (reason shown, rules used)."""
    env = os.environ if env is None else env
    try:
        return default_provider(env)
    except NlParseError as exc:
        code = exc.code if exc.code == 'REPLAY_MISS' else 'PROVIDER_UNAVAILABLE'
    except Exception:  # missing file, bad JSON, unreachable config: never echo the message (may hold paths)
        code = 'PROVIDER_UNAVAILABLE'
    mode = env.get('AMIDST_NL_PROVIDER', 'RECORDED')
    return UnavailableProvider(mode if mode in PROVIDER_KINDS and mode != 'NONE' else 'RECORDED', code)


# ---- orchestration -----------------------------------------------------------------------------------------------
def build_prompt(text, catalog):
    return (_template() + '\nCLOSED_CATALOG=' + json.dumps({k: catalog[k] for k in _LLM_CATALOG_FIELDS}, ensure_ascii=True, sort_keys=True)
            + '\nUSER_TEXT=' + json.dumps(text, ensure_ascii=True))


def _reason_of(code):
    code = str(code)
    if 'TIMEOUT' in code:
        return 'TIMEOUT'
    if code in {'INVALID_RESPONSE', 'DISABLED', 'REPLAY_MISS', 'ILLEGAL_TOOL', 'TIME_BUDGET'}:
        return code
    return 'PROVIDER_UNAVAILABLE'


def _check_llm_output(output, rules, text, catalog):
    """Strict JSON + literal-only validation (shared with Q3); the model may add terms the rules missed but may not
    drop or change what the rules found."""
    checked = validate_literal_output(output, text)
    for field, table in (('class_term', 'class_aliases'), ('color_term', 'color_aliases')):
        known = _lookup(catalog[table], rules[field])
        if known is not None and known != _lookup(catalog[table], checked[field]):
            raise ValueError('LLM dropped/changed explicit ' + field)
    for field, table in (('camera_terms', 'camera_aliases'), ('region_terms', 'region_aliases')):
        known = {_lookup(catalog[table], v) for v in rules[field]} - {None}
        if known and known != {_lookup(catalog[table], v) for v in checked[field]}:
            raise ValueError('LLM dropped/changed explicit scope')
    for key, value in rules['time_literal'].items():
        if value is not None and checked['time_literal'][key] != value:
            raise ValueError('LLM changed explicit time')
    return checked


def _step(index, decided_by, arguments, input_refs, llm_call, summary, fallback_reason, result=None):
    return {'step': index, 'decided_by': decided_by, 'tool': 'propose_query', 'arguments': arguments, 'input_refs': input_refs,
            'llm_call': llm_call, 'result_sha256': canonical_hash(result if result is not None else {'arguments': arguments, 'validation': (llm_call or {}).get('validation')}),
            'result_summary': summary, 'fallback_reason': fallback_reason}


def _summary(form, missing, kind):
    if form is None:
        return '沒有可填入的選項'
    parts = [p for p in (form['classLabel'], form['colorLabel'], '、'.join(form['regionIds']),
                         (form['start'] + ('→' + form['end'] if form['end'] else '')) if form['start'] else '') if p]
    return ' / '.join(parts) + (' · 尚缺 ' + '、'.join(missing) if missing else '')


def parse_nl_options(request, *, catalog, provider=None, budget=None):
    """Return a q-core.nl-parse-response.v1 dict. Never raises for model trouble: it degrades to rules, then to the manual menu."""
    keys = {'schema_version', 'session_ref', 'scene_id', 'run_id', 'kind', 'text'}
    if not isinstance(request, dict) or set(request) != keys or request['schema_version'] != REQUEST_SCHEMA:
        raise NlParseError('INVALID_REQUEST')
    _check_forbidden(request)
    kind, text = request['kind'], request['text']
    if kind not in KINDS or not isinstance(text, str) or not text.strip() or len(text) > 200:
        raise NlParseError('INVALID_REQUEST')
    catalog = normalize_catalog(catalog)
    provider = provider or NoneProvider()
    budget = {**DEFAULT_BUDGET, **(budget or {})}
    info = deepcopy(provider.info)
    rules = parse_rule(text, allow_missing_time=True, class_aliases=catalog['class_aliases'], color_aliases=catalog['color_aliases'],
                       camera_aliases=catalog['camera_aliases'], region_aliases=catalog['region_aliases'])
    steps, fallback, decided_by = [], None, 'RULE'
    form = missing = warnings = None
    reason = None
    llm_form = None
    if rules.unsupported_condition:
        reason = 'UNSUPPORTED_CONDITION'
    elif rules.output['intent'] in {'EXPLAIN', 'UNSUPPORTED'}:
        reason = 'INTENT_NOT_EXECUTABLE'
    elif info['kind'] != 'NONE':
        prompt = build_prompt(text, catalog)
        template = _template()
        call = {'request_sha256': canonical_hash(_request_for_hash(info['model'], prompt, template, TEMPLATE_VERSION, info['options'])),
                'raw_output_sha256': None, 'latency_ms': None, 'validation': 'OK'}
        started = time.monotonic()
        try:
            result = provider.generate(model=info['model'], prompt=prompt, template=template, template_version=TEMPLATE_VERSION,
                                       options=info['options'], timeout_ms=budget['call_timeout_ms'], expected_digest=info['model_digest'])
            record = result.record
            call['raw_output_sha256'] = record.get('raw_output_sha256')
            call['latency_ms'] = (record.get('stats') or {}).get('latency_ms', (time.monotonic() - started) * 1000)
            if call['latency_ms'] is not None and call['latency_ms'] > budget['total_budget_ms']:
                raise ProviderError('TIME_BUDGET', record)   # answer arrived after the budget: it is not used (spec §6 rule 2)
            checked = _check_llm_output(_strict_object(result.text), rules.output, text, catalog)
            llm_form, missing, warnings = build_form(kind, checked, catalog)
            if llm_form is None:  # model proposed terms outside the closed catalog
                raise ValueError(missing)
        except ProviderError as exc:
            fallback = _reason_of(exc.code)
            call['validation'] = fallback if fallback in {'TIMEOUT', 'INVALID_RESPONSE'} else fallback
            rec = exc.record or {}
            call['raw_output_sha256'] = rec.get('raw_output_sha256')
            call['latency_ms'] = (rec.get('stats') or {}).get('latency_ms')
        except ReplayMismatch:
            fallback, call['validation'] = 'REPLAY_MISS', 'INVALID_RESPONSE'
        except (ValueError, TypeError, KeyError):
            fallback, call['validation'] = 'INVALID_RESPONSE', 'INVALID_RESPONSE'
        except Exception:  # a provider that fails in any other way (never echo the message: it may hold paths or headers)
            fallback, call['validation'] = 'PROVIDER_UNAVAILABLE', 'PROVIDER_UNAVAILABLE'
        if llm_form is not None:
            form, decided_by = llm_form, 'LLM'
            steps.append(_step(0, 'LLM', form, [], call, _summary(form, missing, kind), None, result=form))
        else:
            steps.append(_step(0, 'LLM', None, [], call, 'LLM 沒有給出可用結果', fallback))
    detail = []
    if form is None and reason is None:
        form, missing, warnings = build_form(kind, rules.output, catalog)
        if form is None:
            reason, detail = missing, warnings
    if form is not None and not steps or form is not None and steps[-1]['arguments'] is None:
        decided_by = 'RULE_FALLBACK' if fallback else 'RULE'
        refs = [steps[0]['result_sha256']] if steps else []
        steps.append(_step(len(steps), decided_by, form, refs, None, _summary(form, missing, kind), fallback, result=form))
    elif form is None:
        decided_by = 'RULE_FALLBACK' if fallback else 'RULE'
        fallback = fallback or reason
        refs = [steps[0]['result_sha256']] if steps else []
        steps.append(_step(len(steps), decided_by, None, refs, None, '退回手動選單', fallback))
    manual_reason = reason if form is None else None
    ignored = list(rules.unparsed)
    outcome = {'status': 'PROPOSED' if form is not None else 'MANUAL', 'camera_id': None,
               'decided_by': decided_by if form is not None else 'RULE_FALLBACK' if fallback else 'RULE'}
    trace = {'schema_version': TRACE_SCHEMA, 'path': 'NL_TO_OPTIONS',
             'trigger': {'text_sha256': canonical_hash(text), 'kind': kind, 'catalog_sha256': canonical_hash(catalog)},
             'provider': {'kind': info['kind'], 'model': info['model'], 'model_digest': info['model_digest'], 'template_sha256': template_sha256(),
                          'options': info['options'], 'recording_id': info['recording_id'], 'recording_sha256': info['recording_sha256'],
                          'data_origin': info.get('data_origin')},
             'budget': dict(budget), 'steps': steps, 'outcome': outcome,
             'labels': {'evidence': 'EXPLORATORY', 'identity_verdict': 'UNCONFIRMED', GT_READ: False}}
    trace['trace_id'] = 'nlt-' + canonical_hash(trace)[:16]
    trace['content_sha256'] = canonical_hash(trace, exclude=('content_sha256',))
    response = {'schema_version': RESPONSE_SCHEMA, 'status': 'PARSED' if form is not None else 'FALLBACK_MANUAL', 'kind': kind,
                'scene_id': request['scene_id'], 'run_id': request['run_id'], 'text_sha256': trace['trigger']['text_sha256'],
                'form': form, 'missing': list(missing or []) if form is not None else [], 'warnings': list(warnings or []) if form is not None else [],
                'ignored_terms': ignored, 'decided_by': outcome['decided_by'], 'fallback_reason': fallback,
                'manual_reason': manual_reason, 'manual_detail': list(detail) if form is None else [],
                'provider': {'kind': info['kind'], 'model': info['model'], 'recorded': info['recorded'],
                             'synthetic_fixture': info['synthetic_fixture'], 'data_origin': info.get('data_origin'),
                             'recording_id': info['recording_id'], 'recording_sha256': info['recording_sha256'],
                             'latency_ms': (steps[0]['llm_call'] or {}).get('latency_ms') if steps and steps[0]['llm_call'] else None},
                'requires_confirmation': True, 'executed': False, 'trace': trace,
                'labels': {'evidence': 'EXPLORATORY', 'identity_verdict': 'UNCONFIRMED', GT_READ: False}}
    response['output_sha256'] = canonical_hash(response, exclude=('output_sha256',))
    return response


# ---- recording ---------------------------------------------------------------------------------------------------
def make_recording(*, recording_id, data_origin, provider_info, entries, note=None):
    rec = {'schema_version': RECORDING_SCHEMA, 'recording_id': recording_id, 'data_origin': data_origin, 'note': note,
           'provider': {'kind': provider_info['kind'], 'model': provider_info['model'], 'model_digest': provider_info.get('model_digest'),
                        'options': provider_info['options']},
           'template_sha256': template_sha256(), 'entries': entries}
    rec['content_sha256'] = canonical_hash(rec, exclude=('content_sha256',))
    return rec


def recorded_entry(model, prompt, options, raw_output, latency_ms, error_code=None):
    request = _request_for_hash(model, prompt, _template(), TEMPLATE_VERSION, options)
    return {'request_sha256': canonical_hash(request), 'request': request, 'raw_output': raw_output,
            'latency_ms': latency_ms, 'error_code': error_code}


# ---- stdin/stdout adapter for the synthetic preview server -------------------------------------------------------
def _main(argv):
    if argv[1:] != ['replay']:
        sys.stderr.write('usage: python -m amidst.q1q5.nl_options replay < {request, run, recording?}\n')
        return 2
    payload = json.load(sys.stdin)
    provider = RecordedNlProvider.from_file(payload['recording']) if payload.get('recording') else safe_default_provider()
    sys.stdout.write(json.dumps(parse_nl_options(payload['request'], catalog=catalog_from_run_summary(payload['run']), provider=provider),
                                ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv))

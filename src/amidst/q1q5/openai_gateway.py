"""Recorded-mode (8785) OpenAI Agent through a file-queue gateway (#601, D306).

The 8785 process runs under an audit hook that raises on ``socket.connect`` and ``subprocess.Popen`` (D269). That hook is
not changed. The paid call is made by a separate process (``scripts/openai_agent_gateway.py``); the two sides talk through
files in an owned directory, which the hook allows:

    <queue>/requests/<id>.json    8785 -> gateway   system/user text, model, deadline (no key, no file paths)
    <queue>/responses/<id>.json   gateway -> 8785   text or a coded refusal
    <queue>/status.json           gateway heartbeat, ApiGuard approved?, key present? (a boolean, never the key)

Only the gateway reads ``OPENAI_API_KEY`` and every paid call goes through ``ApiGuard``. Off by default: the factory is
bound only when ``AMIDST_RECORDED_AGENT=openai`` is set on the 8785 process. Any refusal, timeout or bad reply reaches
``AgentController`` as a ``ProviderError`` and becomes the rule fallback with ``fallback_reason`` set.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import time
import urllib.error

from amidst.q1q5.llm_provider import CallResult, ProviderError
from amidst.q1q5.q5_agent import AgentController, AgentSettings
from amidst.q1q5.store import canonical_hash

ENV_SWITCH = 'AMIDST_RECORDED_AGENT'
API_MODEL = 'gpt-6.1-terra'            # D237 default
PRICES = {'gpt-6.1-sol': (2.0, 10.0), 'gpt-6.1-terra': (1.0, 5.0), 'gpt-6-astra': (10.0, 50.0)}   # USD per Mtok (D237)
AUTH_REF = 'issue:601#D306'
CALLER = 'recorded_agent'
QUEUE_DIRNAME = 'agent-gateway'
HEARTBEAT_MAX_AGE_S = 10.0
MAX_OUTPUT_TOKENS = 256
MAX_REQUEST_BYTES = 262_144
PROVIDER_KIND = 'OPENAI_VIA_GATEWAY'
TEMPLATE_REL = 'configs/q1q5/prompts/q5_agent_v2.txt'
_ID = re.compile(r'[A-Za-z0-9_-]{8,64}')
_LOCAL_PATH = re.compile(r'/Users/|/private/|/tmp/|[A-Za-z]:\\')

# Reason shown to the operator when the Agent option is unavailable (bootstrap ``agent_unavailable_reason``).
REASON_TEXT = {'GATEWAY_OFFLINE': 'OpenAI gateway 沒有在執行', 'GUARD_NOT_APPROVED': '後台沒有核准付費呼叫（花費護欄關閉或額度為 0）',
               'NO_API_KEY': 'gateway 沒有設定 API key', 'MODEL_NOT_ENABLED': 'gateway 沒有啟用此模型'}
# gateway/provider reason -> code that AgentController records as fallback_reason (already in the workbench whitelist)
_FALLBACK = {'GATEWAY_OFFLINE': 'PROVIDER_UNAVAILABLE', 'GUARD_NOT_APPROVED': 'MODE_NOT_AUTHORIZED', 'NO_API_KEY': 'MODE_NOT_AUTHORIZED',
             'MODEL_NOT_ENABLED': 'MODE_NOT_AUTHORIZED', 'DENIED': 'MODE_NOT_AUTHORIZED', 'TIMEOUT': 'PROVIDER_TIMEOUT',
             'ERROR': 'PROVIDER_UNAVAILABLE', 'INVALID': 'INVALID_RESPONSE'}

# The five parameters AgentController needs, with the values and proposal refs already APPROVED for A4-1/B4-1
# (configs/q1q5/parameter_set_v1.json). Added only to a run that lacks them, and only when the switch is on.
_REF88 = 'https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432'
_REF93 = 'https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288'
AGENT_PARAMETERS = (('agent_max_rounds', 3, 'count', _REF88), ('agent_total_budget_ms', 5000, 'ms', _REF88),
                    ('agent_call_timeout_ms', 2000, 'ms', _REF88), ('agent_max_illegal_submissions', 2, 'count', _REF93),
                    ('session_max_agent_rounds', 12, 'count', _REF93))


class GatewayError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise GatewayError(message)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def model_pin(api_model: str = API_MODEL) -> str:
    """AgentSettings needs a 64-hex model pin. OpenAI exposes no weight digest, so the pin is the hash of the model id
    (identity of the requested model, not of the weights); records say so through ``provider_kind``."""
    return _sha('openai:' + api_model)


def _write_json(path: Path, doc: dict) -> None:
    tmp = path.with_name('.' + path.name + '.tmp')
    tmp.write_text(json.dumps(doc, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)


def _read_json(path: Path, limit: int = MAX_REQUEST_BYTES) -> dict:
    raw = path.read_bytes()
    _require(len(raw) <= limit, 'file too large')
    doc = json.loads(raw)
    _require(isinstance(doc, dict), 'object required')
    return doc


def queue_paths(queue_dir) -> tuple[Path, Path, Path]:
    q = Path(queue_dir)
    return q / 'requests', q / 'responses', q / 'status.json'


def ensure_queue(queue_dir) -> None:
    for sub in queue_paths(queue_dir)[:2]:
        sub.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------------------------------------------------
# 8785 side: provider
# ---------------------------------------------------------------------------------------------------------------------
class GatewayProvider:
    """``generate`` with the Ollama-provider signature ``AgentController`` expects. Never opens a socket."""

    def __init__(self, queue_dir, *, clock=time.monotonic, wall=time.time, sleep=time.sleep, poll_s: float = 0.02,
                 api_model: str = API_MODEL):
        self.queue_dir, self.clock, self.wall, self.sleep, self.poll_s, self.api_model = Path(queue_dir), clock, wall, sleep, poll_s, api_model

    def status(self) -> dict | None:
        try:
            return _read_json(queue_paths(self.queue_dir)[2], 65536)
        except (OSError, ValueError):
            return None

    def availability(self) -> tuple[bool, str | None]:
        """(usable, reason). Reads only the heartbeat file; costs nothing."""
        st = self.status()
        if not st or not isinstance(st.get('heartbeat_unix'), (int, float)) or self.wall() - st['heartbeat_unix'] > HEARTBEAT_MAX_AGE_S:
            return False, 'GATEWAY_OFFLINE'
        if st.get('guard_approved') is not True:
            return False, 'GUARD_NOT_APPROVED'
        if st.get('key_present') is not True:
            return False, 'NO_API_KEY'
        if self.api_model not in (st.get('models') or []):
            return False, 'MODEL_NOT_ENABLED'
        return True, None

    def generate(self, *, model, prompt, template, template_version, options, timeout_ms, expected_digest=None) -> CallResult:
        _require(isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]+', model), 'Invalid model tag')
        _require(all(isinstance(v, str) and v for v in (prompt, template, template_version)) and prompt.startswith(template + '\n'),
                 'Prompt and versioned template are required')
        _require(type(timeout_ms) is int and timeout_ms > 0, 'Caller must supply a positive timeout')
        _require(not _LOCAL_PATH.search(prompt + template), 'Local paths are forbidden in prompts')   # same boundary guard as the Ollama provider
        start = self.clock()
        wire = {'model': self.api_model, 'system': template, 'user': prompt[len(template) + 1:],
                'max_output_tokens': MAX_OUTPUT_TOKENS}
        record = {'model': model, 'model_digest': None, 'prompt': prompt, 'prompt_sha256': _sha(prompt),
                  'prompt_template_version': template_version, 'prompt_template_sha256': _sha(template),
                  'sampling': dict(options), 'input_sha256': canonical_hash(wire), 'raw_output': None, 'raw_output_sha256': None,
                  'response_body_sha256': None, 'validation': 'NOT_RUN', 'validation_errors': [], 'timeout_ms': timeout_ms,
                  'timed_out': False, 'provider_kind': PROVIDER_KIND, 'api_model_id': self.api_model,
                  'prompt_tokens': None, 'completion_tokens': None}

        def finish(code):
            out = dict(record)
            out['validation'] = code
            out['stats'] = {'latency_ms': max(0, (self.clock() - start) * 1000)}
            out['content_sha256'] = canonical_hash(out, exclude=('content_sha256', 'stats'))
            return out

        def refuse(reason):
            code = _FALLBACK[reason]
            record['validation_errors'] = [reason]
            record['timed_out'] = reason == 'TIMEOUT'
            raise ProviderError(code, finish(code))

        ok, reason = self.availability()
        if not ok:
            refuse(reason)
        req_dir, resp_dir, _ = queue_paths(self.queue_dir)
        rid = secrets.token_hex(12)
        _write_json(req_dir / f'{rid}.json', {'schema_version': 'q-demo.agent-gateway-request.v1', 'id': rid, **wire,
                                              'deadline_unix': self.wall() + timeout_ms / 1000})
        resp_path = resp_dir / f'{rid}.json'
        deadline = start + timeout_ms / 1000
        while True:
            try:
                doc = _read_json(resp_path)
                break
            except (OSError, ValueError):
                pass
            if self.clock() >= deadline:
                try:
                    (req_dir / f'{rid}.json').unlink()
                except OSError:
                    pass
                refuse('TIMEOUT')
            self.sleep(self.poll_s)
        try:
            resp_path.unlink()
        except OSError:
            pass
        record['prompt_tokens'], record['completion_tokens'] = (doc.get(k) if type(doc.get(k)) is int else None for k in ('prompt_tokens', 'completion_tokens'))
        if isinstance(doc.get('api_model_id'), str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,100}', doc['api_model_id']):
            record['api_model_id'] = doc['api_model_id']
        if self.clock() > deadline:
            refuse('TIMEOUT')
        text = doc.get('text')
        if doc.get('status') != 'OK':
            record['validation_errors'] = [str(doc.get('reason'))[:60] if isinstance(doc.get('reason'), str) else 'UNKNOWN']
            code = _FALLBACK.get(doc.get('status'), 'PROVIDER_UNAVAILABLE')
            raise ProviderError(code, finish(code))
        if not isinstance(text, str) or not text.strip():
            refuse('INVALID')
        record['model_digest'] = expected_digest if expected_digest is not None else model_pin(self.api_model)
        record['raw_output'], record['raw_output_sha256'] = text, _sha(text)
        record['response_body_sha256'] = canonical_hash({k: doc.get(k) for k in ('status', 'text', 'prompt_tokens', 'completion_tokens', 'api_model_id')})
        return CallResult(text, finish('PROVIDER_VALIDATED'))


# ---------------------------------------------------------------------------------------------------------------------
# 8785 side: wiring
# ---------------------------------------------------------------------------------------------------------------------
class GatewayAgentFactory:
    """``run.agent_factory``. ``availability()`` lets the bootstrap say honestly whether the Agent option can work now."""

    def __init__(self, provider: GatewayProvider, settings: AgentSettings):
        self.provider, self.settings = provider, settings

    def __call__(self, request, **kwargs):
        # Recorded replay: no wall-clock pacing between rounds; the approved per-call and total budgets still apply.
        return AgentController(request, provider=self.provider, agent_settings=self.settings, round_scheduler=lambda *a: None, **kwargs)

    def availability(self):
        return self.provider.availability()


def load_settings(repo_root=None, api_model: str = API_MODEL) -> AgentSettings:
    from amidst.q1q5.llm_guidance import Q5_MARKER
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    text = (root / TEMPLATE_REL).read_text(encoding='utf-8')
    _require(text.startswith(Q5_MARKER) and not _LOCAL_PATH.search(text), 'Q5 template mismatch')
    return AgentSettings(api_model, model_pin(api_model), {'temperature': 0, 'num_predict': MAX_OUTPUT_TOKENS}, text, _sha(text),
                         'q5-agent-v2', AUTH_REF)


def ensure_agent_parameters(run):
    """Add the approved agent parameters a run lacks (same values/refs as the A4-1 config) and re-seal its parameter set.
    A run that already has them is returned unchanged."""
    b = run.bindings
    ps = deepcopy(b.parameter_set)
    have = {p['name']: p for p in ps['parameters']}
    missing = [x for x in AGENT_PARAMETERS if x[0] not in have]
    if not missing:
        return run
    for name, value, unit, ref in missing:
        ps['parameters'].append({'name': name, 'value': value, 'unit': unit, 'status': 'APPROVED', 'proposed_by': 'codex', 'proposal_ref': ref})
    ps['content_sha256'] = canonical_hash(ps, exclude=('content_sha256', 'stats', 'graph_id', 'parameter_set_id', 'index_id'))
    ps['parameter_set_id'] = ps['parameter_set_id'].rsplit(':', 1)[0] + ':' + ps['content_sha256'][:16]
    settings = replace(run.parse_settings, parameter_set_id=ps['parameter_set_id'], parameter_set_sha256=ps['content_sha256'])
    return replace(run, bindings=replace(b, parameter_set=ps, parameter_sha256=ps['content_sha256']), parse_settings=settings)


def bind_openai_agent(runs, queue_dir, *, provider: GatewayProvider | None = None, settings: AgentSettings | None = None):
    """Give every run an OpenAI-gateway ``agent_factory`` (previous factories are replaced). Makes no network or file call."""
    provider = provider or GatewayProvider(queue_dir)
    factory = GatewayAgentFactory(provider, settings or load_settings())
    return tuple(replace(ensure_agent_parameters(run), agent_factory=factory) for run in runs)


def configure_environment(runs, queue_dir, env=None):
    """Default off. ``AMIDST_RECORDED_AGENT=openai`` turns it on; any other non-empty value is an error, never a silent no-op."""
    env = os.environ if env is None else env
    value = env.get(ENV_SWITCH, '')
    if value in ('', 'off'):
        return tuple(runs)
    _require(value == 'openai', f'{ENV_SWITCH} must be unset, off or openai')
    return bind_openai_agent(runs, queue_dir)


def agent_status(run) -> tuple[bool, str | None]:
    """(agent_available, reason) for the bootstrap. A factory without ``availability`` (Ollama, tests) is always available."""
    factory = run.agent_factory
    if not callable(factory):
        return False, None
    check = getattr(factory, 'availability', None)
    if check is None:
        return True, None
    ok, reason = check()
    return bool(ok), reason


# ---------------------------------------------------------------------------------------------------------------------
# gateway side (separate process; the only code that holds the key and touches the network)
# ---------------------------------------------------------------------------------------------------------------------
def openai_chat(system: str, user: str, api_model: str, max_output_tokens: int, timeout_s: float, env) -> tuple[str, int | None, int | None, str]:
    """One chat completion. Reads the key only here, inside ``ApiGuard.run``. Returns (text, prompt_tokens, completion_tokens, api_model)."""
    from amidst.q1q5.agent_providers import OPENAI_CHAT_URL, default_http_transport
    key = env.get('OPENAI_API_KEY')
    if not isinstance(key, str) or not key.strip():
        raise PermissionError('NO_API_KEY')
    if 'json' not in system.lower():   # json_object mode requires the word JSON in the messages
        system += '\nRespond with a single JSON object.'
    body = json.dumps({'model': api_model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                       'max_completion_tokens': int(max_output_tokens), 'response_format': {'type': 'json_object'}}).encode()
    status, raw = default_http_transport(url=OPENAI_CHAT_URL, headers={'Authorization': 'Bearer ' + key.strip(), 'Content-Type': 'application/json'},
                                         body=body, timeout_s=timeout_s)
    data = json.loads(raw)
    choice = data['choices'][0]
    _require(choice.get('finish_reason') == 'stop' and isinstance(choice['message'].get('content'), str), 'incomplete reply')
    usage = data.get('usage') or {}
    pt, ct = usage.get('prompt_tokens'), usage.get('completion_tokens')
    return choice['message']['content'], pt if type(pt) is int else None, ct if type(ct) is int else None, str(data.get('model') or api_model)


class GatewayWorker:
    """Serves the queue. ``call`` is injectable so tests never touch the network."""

    def __init__(self, queue_dir, guard, *, call=openai_chat, env=None, wall=time.time, models=(API_MODEL,)):
        self.queue_dir, self.guard, self.call, self.wall, self.models = Path(queue_dir), guard, call, wall, tuple(models)
        self.env = os.environ if env is None else env
        ensure_queue(self.queue_dir)

    def write_status(self) -> dict:
        cfg = self.guard.config
        st = {'schema_version': 'q-demo.agent-gateway-status.v1', 'heartbeat_unix': self.wall(),
              'guard_approved': bool(cfg.enabled and cfg.max_usd_total > 0), 'key_present': bool(self.env.get('OPENAI_API_KEY')),
              'models': list(self.models)}
        _write_json(queue_paths(self.queue_dir)[2], st)
        return st

    def _respond(self, rid, **doc):
        _write_json(queue_paths(self.queue_dir)[1] / f'{rid}.json', {'id': rid, **doc})

    def handle(self, path: Path) -> str:
        """Process one request file; returns the outcome word. The request file is always removed."""
        try:
            req = _read_json(path)
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            return 'BAD_REQUEST'
        path.unlink(missing_ok=True)
        rid = req.get('id')
        try:
            _require(isinstance(rid, str) and _ID.fullmatch(rid) and path.stem == rid, 'bad id')
            _require(req.get('schema_version') == 'q-demo.agent-gateway-request.v1' and req.get('model') in self.models, 'bad model')
            system, user = req.get('system'), req.get('user')
            _require(isinstance(system, str) and isinstance(user, str) and system and user, 'bad text')
            _require(not _LOCAL_PATH.search(system + user), 'local path in prompt')
            max_out = req.get('max_output_tokens')
            _require(type(max_out) is int and 1 <= max_out <= MAX_OUTPUT_TOKENS, 'bad token cap')
            deadline = req.get('deadline_unix')
            _require(isinstance(deadline, (int, float)), 'bad deadline')
        except GatewayError:
            if isinstance(rid, str) and _ID.fullmatch(rid):
                self._respond(rid, status='ERROR', reason='BAD_REQUEST')
            return 'BAD_REQUEST'
        remaining = deadline - self.wall()
        if remaining <= 0:   # the 8785 side already gave up: spend nothing
            return 'STALE'
        if not self.env.get('OPENAI_API_KEY'):   # refuse before ApiGuard so a keyless attempt is never charged
            return self._late(rid, deadline, 'DENIED', 'NO_API_KEY')
        est_prompt = (len(system) + len(user)) // 3 + 50
        api_model = req['model']

        usage = {}

        def fn():
            text, pt, ct, served = self.call(system, user, api_model, max_out, max(0.5, remaining), self.env)
            usage.update(prompt_tokens=pt, completion_tokens=ct)
            return {'text': text, 'api_model_id': served}, pt, ct

        try:
            out = self.guard.run(CALLER, api_model, est_prompt, max_out, fn)
        except (socket.timeout, TimeoutError):
            return self._late(rid, deadline, 'TIMEOUT', 'TIMEOUT')
        except urllib.error.URLError as exc:
            timed_out = isinstance(exc.reason, (socket.timeout, TimeoutError))
            return self._late(rid, deadline, 'TIMEOUT' if timed_out else 'ERROR', 'TIMEOUT' if timed_out else 'URL_ERROR')
        except urllib.error.HTTPError as exc:   # never echo bodies or messages: they can carry request details
            return self._late(rid, deadline, 'ERROR', f'HTTP_{exc.code}')
        except PermissionError:
            return self._late(rid, deadline, 'DENIED', 'NO_API_KEY')
        except Exception as exc:  # noqa: BLE001 - operational fault; only the class name leaves this process
            return self._late(rid, deadline, 'ERROR', type(exc).__name__[:40])
        if not out.allowed:
            return self._late(rid, deadline, 'DENIED', out.reason)
        return self._late(rid, deadline, 'OK', None, text=out.value['text'], api_model_id=out.value['api_model_id'], **usage)

    def _late(self, rid, deadline, status, reason, **extra):
        if self.wall() <= deadline + 1.0:   # the reader is gone after its deadline; do not leave orphan files
            self._respond(rid, status=status, reason=reason, **extra)
        return status

    def process_once(self) -> int:
        n = 0
        for path in sorted(queue_paths(self.queue_dir)[0].glob('*.json')):
            self.handle(path)
            n += 1
        return n

    def serve_forever(self, poll_s: float = 0.05, heartbeat_s: float = 2.0, sleep=time.sleep):   # pragma: no cover - loop
        last = 0.0
        while True:
            if self.wall() - last >= heartbeat_s:
                self.write_status()
                last = self.wall()
            if not self.process_once():
                sleep(poll_s)

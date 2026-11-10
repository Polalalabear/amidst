"""Agent decision WP3: OpenAI and Ollama loopback provider adapters.

Design: docs/design/AGENT_DECISION_V1.md (§2.2, §2.3, §3.3, §6.1, §7 WP3).
Supplies call(request, *, timeout_ms, max_output_tokens) -> Attempt callables for
WP1's decide() and WP2's AgentDecider. Standard library only; no external SDKs.
OPENAI_API_KEY is read from the environment only at the moment a live HTTP request
is dispatched and never appears in logs, recordings, exceptions or repr().
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
import json
import logging
import os
from pathlib import Path
import re
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from amidst.paths import PACKAGE_ROOT, amidst_root
from amidst.q1q5.agent_wiring import ad

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_OLLAMA_ENDPOINT = 'http://127.0.0.1:11434'
LOOPBACK_HOSTS = frozenset({'127.0.0.1', 'localhost', '::1'})
SCHEMA_REL_PATH = 'docs/contracts/schemas/q-core.agent-decision.v1.schema.json'
SYSTEM_PROMPT = (
    'You are a bounded cross-camera adjudication assistant. '
    'Select a rule-eligible candidate id or ABSTAIN for DP1, or ACCEPT_SEGMENT/REJECT_SEGMENT for DP3. '
    'Respond strictly with a JSON object matching the response schema.'
)


def load_response_schema(root: Path | None = None) -> dict:
    """Load $defs/response from the v1 contract schema."""
    base = root if root is not None else amidst_root()
    candidate = base / SCHEMA_REL_PATH
    if not candidate.exists():
        candidate = PACKAGE_ROOT / SCHEMA_REL_PATH
    doc = json.loads(candidate.read_text(encoding='utf-8'))
    return copy.deepcopy(doc['$defs']['response'])


RESPONSE_SCHEMA = load_response_schema()


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'Redirects forbidden', headers, fp)


def default_http_transport(
    *,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None = None,
    timeout_s: float = 2.0,
    method: str = 'POST',
) -> tuple[int, bytes]:
    """Standard-library HTTP/HTTPS transport with redirects disabled."""
    opener = urllib.request.build_opener(_NoRedirectHandler)
    req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    with opener.open(req, timeout=timeout_s) as resp:
        status = getattr(resp, 'status', 200)
        return int(status), resp.read(2_000_000)


class FakeClock:
    """Deterministic millisecond clock and sleep spy for rate-limit and timeout tests."""

    def __init__(self, initial_ms: float = 0.0):
        self._now_ms = float(initial_ms)
        self.slept_ms: list[int] = []

    def now_ms(self) -> float:
        return self._now_ms

    def advance_ms(self, delta_ms: float) -> None:
        self._now_ms += float(delta_ms)

    def sleep_ms(self, duration_ms: int) -> None:
        ms = int(duration_ms)
        self.slept_ms.append(ms)
        self._now_ms += ms

    __call__ = now_ms


def _default_clock_ms() -> float:
    return time.monotonic() * 1000.0


def _default_sleep_ms(duration_ms: int) -> None:
    if duration_ms > 0:
        time.sleep(duration_ms / 1000.0)


def _is_timeout_exception(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout)):
        return True
    return False


def _status_outcome(status: int) -> str:
    if status == 429 or 500 <= status < 600:
        return ad.CALL_RETRYABLE
    if 200 <= status < 300:
        return ad.CALL_OK
    return ad.CALL_UNAVAILABLE


def _normalize_transport_output(raw) -> tuple[int, object, float | None]:
    """Normalize transport return value into (http_status, parsed_or_raw_body, reported_wall_ms)."""
    if isinstance(raw, tuple) and len(raw) == 2:
        status, body = raw
        return int(status), body, None
    if isinstance(raw, tuple) and len(raw) == 3:
        status, body, wall_ms = raw
        return int(status), body, float(wall_ms) if wall_ms is not None else None
    if isinstance(raw, Mapping) and 'status' in raw and ('body' in raw or 'response' in raw or 'json' in raw):
        status = int(raw['status'])
        body = raw.get('body', raw.get('json', raw.get('response')))
        wall = raw.get('wall_ms')
        return status, body, float(wall) if wall is not None else None
    return 200, raw, None


def _parse_json_bytes(body) -> tuple[bool, object]:
    if isinstance(body, (bytes, bytearray)):
        try:
            return True, json.loads(body.decode('utf-8'))
        except Exception:
            return False, None
    if isinstance(body, str):
        try:
            return True, json.loads(body)
        except Exception:
            return False, None
    if isinstance(body, Mapping):
        return True, dict(body)
    return False, body


def _extract_tokens(data: Mapping) -> tuple[int | None, int | None]:
    usage = data.get('usage')
    if isinstance(usage, Mapping):
        p = usage.get('prompt_tokens')
        c = usage.get('completion_tokens')
        return (p if type(p) is int and p >= 0 else None,
                c if type(c) is int and c >= 0 else None)
    p = data.get('prompt_eval_count', data.get('prompt_tokens'))
    c = data.get('eval_count', data.get('completion_tokens'))
    return (p if type(p) is int and p >= 0 else None,
            c if type(c) is int and c >= 0 else None)


def _apply_rate_gate(
    budget: ad.CallBudget | None,
    clock_ms: Callable[[], float],
    sleep_ms: Callable[[int], None],
) -> None:
    if budget is None:
        return
    now_ms = int(clock_ms())
    wait_ms = budget.rate_wait_ms(now_ms)
    if wait_ms > 0:
        sleep_ms(wait_ms)
        after_ms = int(clock_ms())
        now_ms = max(after_ms, now_ms + wait_ms)
    budget.note_start(now_ms)


def validate_ollama_endpoint(endpoint: str) -> str:
    """Ensure endpoint is an HTTP loopback URL (127.0.0.1, localhost, or ::1)."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ad.AgentDecisionError('OLLAMA_ENDPOINT_INVALID', 'empty endpoint')
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != 'http'
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {'', '/'}
    ):
        raise ad.AgentDecisionError('OLLAMA_ENDPOINT_INVALID', 'loopback http endpoint required')
    return endpoint.rstrip('/')


class OpenAIProvider:
    """OpenAI structured-output adapter for WP1 decide() (provider_kind='OPENAI')."""

    provider_kind = 'OPENAI'

    def __init__(
        self,
        *,
        model: str,
        params: Mapping | None = None,
        api_model_id: str | None = None,
        endpoint: str = OPENAI_CHAT_URL,
        transport: Callable | None = None,
        env: Mapping[str, str] | None = None,
        budget: ad.CallBudget | None = None,
        recorder: Callable[[dict], None] | None = None,
        seed: int | None = None,
        temperature: float | None = None,
        candidate_order_seed: int | None = None,
        clock_ms: Callable[[], float] | None = None,
        sleep_ms: Callable[[int], None] | None = None,
        response_schema: Mapping | None = None,
    ):
        if model not in ad.MODELS:
            raise ad.AgentDecisionError('PARAMS_INVALID', f'OpenAI model {model!r} must be one of {ad.MODELS}')
        if params is not None:
            ad.validate_params(params)
            configured = {m['config_id']: m.get('api_model_id') for m in params['models']}
            if model not in configured:
                raise ad.AgentDecisionError('PARAMS_INVALID', f'model {model!r} not in params')
            if api_model_id is None:
                api_model_id = configured[model]
        if seed is not None and type(seed) is not int:
            raise ad.AgentDecisionError('PARAMS_INVALID', 'seed must be int or None')
        if temperature is not None and (type(temperature) not in (int, float) or not (0.0 <= float(temperature) <= 2.0)):
            raise ad.AgentDecisionError('PARAMS_INVALID', 'temperature must be in [0, 2]')
        if candidate_order_seed is not None and type(candidate_order_seed) is not int:
            raise ad.AgentDecisionError('PARAMS_INVALID', 'candidate_order_seed must be int or None')

        self.model = model
        self.configured_api_model_id = api_model_id
        self.last_api_model_id: str | None = api_model_id
        self.endpoint = endpoint
        self._transport = transport or default_http_transport
        self._env = env
        self._budget = budget
        self._recorder = recorder
        self.seed = seed
        self.temperature = float(temperature) if temperature is not None else None
        self.candidate_order_seed = candidate_order_seed
        self._clock_ms = clock_ms or _default_clock_ms
        self._sleep_ms = sleep_ms or _default_sleep_ms
        self._response_schema = copy.deepcopy(dict(response_schema)) if response_schema is not None else copy.deepcopy(RESPONSE_SCHEMA)

    def __repr__(self) -> str:
        return (
            f'OpenAIProvider(model={self.model!r}, '
            f'configured_api_model_id={self.configured_api_model_id!r}, '
            f'seed={self.seed!r}, temperature={self.temperature!r})'
        )

    __str__ = __repr__

    def _read_api_key_now(self) -> str | None:
        source = self._env if self._env is not None else os.environ
        key = source.get('OPENAI_API_KEY')
        if not isinstance(key, str) or not key.strip():
            return None
        return key.strip()

    def provider_meta(self) -> dict:
        meta: dict[str, object] = {'api_model_id': self.last_api_model_id}
        if self.seed is not None:
            meta['seed'] = self.seed
        if self.temperature is not None:
            meta['temperature'] = self.temperature
        if self.candidate_order_seed is not None:
            meta['candidate_order_seed'] = self.candidate_order_seed
        return meta

    def _build_payload(self, request: Mapping, *, max_output_tokens: int) -> dict:
        canonical_req = ad.canonical(request).decode('ascii')
        payload: dict[str, object] = {
            'model': self.configured_api_model_id or self.model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': canonical_req},
            ],
            'max_output_tokens': int(max_output_tokens),
            'max_completion_tokens': int(max_output_tokens),
            'response_format': {
                'type': 'json_schema',
                'json_schema': {
                    'name': 'agent_decision_response_v1',
                    'strict': True,
                    'schema': copy.deepcopy(self._response_schema),
                },
            },
        }
        if self.seed is not None:
            payload['seed'] = self.seed
        if self.temperature is not None:
            payload['temperature'] = self.temperature
        return payload

    def call(self, request: Mapping, *, timeout_ms: int, max_output_tokens: int) -> ad.Attempt:
        ad.validate_request(request)
        if type(timeout_ms) is not int or timeout_ms < 1:
            raise ad.AgentDecisionError('ATTEMPT_INVALID', 'timeout_ms')
        if type(max_output_tokens) is not int or max_output_tokens < 1:
            raise ad.AgentDecisionError('ATTEMPT_INVALID', 'max_output_tokens')

        api_key = self._read_api_key_now()
        if api_key is None:
            logger.warning('openai_provider: OPENAI_API_KEY is not set; returning UNAVAILABLE')
            return ad.Attempt(ad.CALL_UNAVAILABLE, 0.0)

        payload = self._build_payload(request, max_output_tokens=max_output_tokens)
        body_bytes = ad.canonical(payload)
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        # Delete local reference to api_key immediately so only headers holds it during transport
        del api_key

        _apply_rate_gate(self._budget, self._clock_ms, self._sleep_ms)
        start_ms = float(self._clock_ms())
        try:
            raw_out = self._transport(
                url=self.endpoint,
                headers=headers,
                body=body_bytes,
                timeout_s=timeout_ms / 1000.0,
            )
        except urllib.error.HTTPError as exc:
            wall_ms = max(0.0, float(self._clock_ms()) - start_ms)
            outcome = _status_outcome(int(exc.code))
            logger.warning('openai_provider http error: status=%d outcome=%s', int(exc.code), outcome)
            return ad.Attempt(outcome, wall_ms)
        except BaseException as exc:
            wall_ms = max(0.0, float(self._clock_ms()) - start_ms)
            if _is_timeout_exception(exc):
                if wall_ms <= 0.0:
                    wall_ms = float(timeout_ms)
                logger.warning('openai_provider timeout: exc=%s', type(exc).__name__)
                return ad.Attempt(ad.CALL_TIMEOUT, wall_ms)
            if isinstance(exc, ad.AgentDecisionError):
                raise
            logger.warning('openai_provider transport unavailable: exc=%s', type(exc).__name__)
            return ad.Attempt(ad.CALL_UNAVAILABLE, wall_ms)
        finally:
            headers.clear()
            if self._budget is not None:
                self._budget.note_end()

        elapsed_ms = max(0.0, float(self._clock_ms()) - start_ms)
        status, raw_body, reported_wall = _normalize_transport_output(raw_out)
        wall_ms = reported_wall if reported_wall is not None else elapsed_ms
        outcome = _status_outcome(status)
        if outcome != ad.CALL_OK:
            return ad.Attempt(outcome, wall_ms)

        if wall_ms > timeout_ms:
            return ad.Attempt(ad.CALL_TIMEOUT, wall_ms)

        ok_json, data = _parse_json_bytes(raw_body)
        if not ok_json or not isinstance(data, Mapping):
            return ad.Attempt(ad.CALL_OK, wall_ms, None)

        prompt_tokens, completion_tokens = _extract_tokens(data)
        if isinstance(data.get('model'), str) and data['model'].strip():
            self.last_api_model_id = data['model'].strip()

        parsed_response = _extract_openai_response_object(data)
        attempt = ad.Attempt(ad.CALL_OK, wall_ms, parsed_response, prompt_tokens, completion_tokens)
        if self._recorder is not None:
            self._recorder({
                'request_sha256': ad.request_sha256(request),
                'request': copy.deepcopy(dict(request)),
                'response': copy.deepcopy(parsed_response),
                'provider': self.provider_kind,
                'model': self.model,
                'api_model_id': self.last_api_model_id,
                'model_digest': None,
                'seed': self.seed,
                'temperature': self.temperature,
                'candidate_order_seed': self.candidate_order_seed,
                'wall_ms': wall_ms,
                'usage': {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                },
            })
        return attempt

    __call__ = call


def _extract_openai_response_object(data: Mapping) -> object:
    if 'choices' in data:
        choices = data.get('choices')
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            return None
        message = choices[0].get('message')
        if not isinstance(message, Mapping):
            return None
        if 'parsed' in message and message['parsed'] is not None:
            return message['parsed']
        content = message.get('content')
        if isinstance(content, Mapping):
            return dict(content)
        if isinstance(content, str):
            try:
                return json.loads(content)
            except Exception:
                return None
        return None
    if 'response' in data and isinstance(data['response'], Mapping):
        return dict(data['response'])
    if 'action' in data or 'reason_codes' in data or 'rationale' in data:
        return dict(data)
    return dict(data)


class OllamaProvider:
    """Loopback-only Ollama structured-output adapter for WP1 decide() (provider_kind='OLLAMA_LOOPBACK')."""

    provider_kind = 'OLLAMA_LOOPBACK'

    def __init__(
        self,
        *,
        model: str,
        endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
        model_digest: str | None = None,
        transport: Callable | None = None,
        budget: ad.CallBudget | None = None,
        recorder: Callable[[dict], None] | None = None,
        seed: int | None = None,
        temperature: float | None = None,
        candidate_order_seed: int | None = None,
        clock_ms: Callable[[], float] | None = None,
        sleep_ms: Callable[[int], None] | None = None,
        response_schema: Mapping | None = None,
    ):
        self.endpoint = validate_ollama_endpoint(endpoint)
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,100}', model):
            raise ad.AgentDecisionError('PARAMS_INVALID', 'invalid Ollama model name')
        if model_digest is not None and (not isinstance(model_digest, str) or not model_digest.strip()):
            raise ad.AgentDecisionError('PARAMS_INVALID', 'invalid model_digest')
        if seed is not None and type(seed) is not int:
            raise ad.AgentDecisionError('PARAMS_INVALID', 'seed must be int or None')
        if temperature is not None and (type(temperature) not in (int, float) or not (0.0 <= float(temperature) <= 2.0)):
            raise ad.AgentDecisionError('PARAMS_INVALID', 'temperature must be in [0, 2]')
        if candidate_order_seed is not None and type(candidate_order_seed) is not int:
            raise ad.AgentDecisionError('PARAMS_INVALID', 'candidate_order_seed must be int or None')

        self.model = model
        self.model_digest: str | None = model_digest.removeprefix('sha256:') if isinstance(model_digest, str) else None
        self._transport = transport or default_http_transport
        self._budget = budget
        self._recorder = recorder
        self.seed = seed
        self.temperature = float(temperature) if temperature is not None else None
        self.candidate_order_seed = candidate_order_seed
        self._clock_ms = clock_ms or _default_clock_ms
        self._sleep_ms = sleep_ms or _default_sleep_ms
        self._response_schema = copy.deepcopy(dict(response_schema)) if response_schema is not None else copy.deepcopy(RESPONSE_SCHEMA)

    def __repr__(self) -> str:
        return (
            f'OllamaProvider(model={self.model!r}, endpoint={self.endpoint!r}, '
            f'model_digest={self.model_digest!r})'
        )

    __str__ = __repr__

    def provider_meta(self) -> dict:
        meta: dict[str, object] = {'model_digest': self.model_digest}
        if self.seed is not None:
            meta['seed'] = self.seed
        if self.temperature is not None:
            meta['temperature'] = self.temperature
        if self.candidate_order_seed is not None:
            meta['candidate_order_seed'] = self.candidate_order_seed
        return meta

    def fetch_model_digest(self, *, timeout_ms: int = 2000) -> str | None:
        """Query /api/tags on the loopback endpoint to resolve and record model_digest."""
        try:
            raw_out = self._transport(
                url=f'{self.endpoint}/api/tags',
                headers={'Accept': 'application/json'},
                body=None,
                timeout_s=max(0.1, timeout_ms / 1000.0),
            )
        except TypeError:
            raw_out = self._transport(
                url=f'{self.endpoint}/api/tags',
                headers={'Accept': 'application/json'},
                body=b'',
                timeout_s=max(0.1, timeout_ms / 1000.0),
            )
        except BaseException:
            return self.model_digest
        status, raw_body, _ = _normalize_transport_output(raw_out)
        if status != 200:
            return self.model_digest
        ok_json, data = _parse_json_bytes(raw_body)
        if not ok_json or not isinstance(data, Mapping):
            return self.model_digest
        models = data.get('models')
        if isinstance(models, list):
            for entry in models:
                if isinstance(entry, Mapping) and entry.get('name') in {self.model, f'{self.model}:latest'}:
                    digest = entry.get('digest')
                    if isinstance(digest, str) and digest.strip():
                        self.model_digest = digest.strip().removeprefix('sha256:')
                        break
        return self.model_digest

    def _build_payload(self, request: Mapping, *, max_output_tokens: int) -> dict:
        canonical_req = ad.canonical(request).decode('ascii')
        options: dict[str, object] = {'num_predict': int(max_output_tokens)}
        if self.seed is not None:
            options['seed'] = self.seed
        if self.temperature is not None:
            options['temperature'] = self.temperature
        return {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': canonical_req},
            ],
            'stream': False,
            'format': copy.deepcopy(self._response_schema),
            'max_output_tokens': int(max_output_tokens),
            'options': options,
        }

    def call(self, request: Mapping, *, timeout_ms: int, max_output_tokens: int) -> ad.Attempt:
        ad.validate_request(request)
        if type(timeout_ms) is not int or timeout_ms < 1:
            raise ad.AgentDecisionError('ATTEMPT_INVALID', 'timeout_ms')
        if type(max_output_tokens) is not int or max_output_tokens < 1:
            raise ad.AgentDecisionError('ATTEMPT_INVALID', 'max_output_tokens')

        payload = self._build_payload(request, max_output_tokens=max_output_tokens)
        body_bytes = ad.canonical(payload)
        headers = {'Content-Type': 'application/json'}

        _apply_rate_gate(self._budget, self._clock_ms, self._sleep_ms)
        start_ms = float(self._clock_ms())
        try:
            raw_out = self._transport(
                url=f'{self.endpoint}/api/chat',
                headers=headers,
                body=body_bytes,
                timeout_s=timeout_ms / 1000.0,
            )
        except urllib.error.HTTPError as exc:
            wall_ms = max(0.0, float(self._clock_ms()) - start_ms)
            outcome = _status_outcome(int(exc.code))
            return ad.Attempt(outcome, wall_ms)
        except BaseException as exc:
            wall_ms = max(0.0, float(self._clock_ms()) - start_ms)
            if _is_timeout_exception(exc):
                if wall_ms <= 0.0:
                    wall_ms = float(timeout_ms)
                return ad.Attempt(ad.CALL_TIMEOUT, wall_ms)
            if isinstance(exc, ad.AgentDecisionError):
                raise
            return ad.Attempt(ad.CALL_UNAVAILABLE, wall_ms)
        finally:
            if self._budget is not None:
                self._budget.note_end()

        elapsed_ms = max(0.0, float(self._clock_ms()) - start_ms)
        status, raw_body, reported_wall = _normalize_transport_output(raw_out)
        wall_ms = reported_wall if reported_wall is not None else elapsed_ms
        outcome = _status_outcome(status)
        if outcome != ad.CALL_OK:
            return ad.Attempt(outcome, wall_ms)

        if wall_ms > timeout_ms:
            return ad.Attempt(ad.CALL_TIMEOUT, wall_ms)

        ok_json, data = _parse_json_bytes(raw_body)
        if not ok_json or not isinstance(data, Mapping):
            return ad.Attempt(ad.CALL_OK, wall_ms, None)

        digest = data.get('model_digest') or data.get('digest')
        if isinstance(digest, str) and digest.strip():
            self.model_digest = digest.strip().removeprefix('sha256:')

        prompt_tokens, completion_tokens = _extract_tokens(data)
        parsed_response = _extract_ollama_response_object(data)
        attempt = ad.Attempt(ad.CALL_OK, wall_ms, parsed_response, prompt_tokens, completion_tokens)
        if self._recorder is not None:
            self._recorder({
                'request_sha256': ad.request_sha256(request),
                'request': copy.deepcopy(dict(request)),
                'response': copy.deepcopy(parsed_response),
                'provider': self.provider_kind,
                'model': self.model,
                'api_model_id': None,
                'model_digest': self.model_digest,
                'seed': self.seed,
                'temperature': self.temperature,
                'candidate_order_seed': self.candidate_order_seed,
                'wall_ms': wall_ms,
                'usage': {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                },
            })
        return attempt

    __call__ = call


def _extract_ollama_response_object(data: Mapping) -> object:
    if 'message' in data and isinstance(data['message'], Mapping):
        content = data['message'].get('content')
        if isinstance(content, Mapping):
            return dict(content)
        if isinstance(content, str):
            try:
                return json.loads(content)
            except Exception:
                return None
        return None
    if 'response' in data:
        resp = data['response']
        if isinstance(resp, Mapping):
            return dict(resp)
        if isinstance(resp, str):
            try:
                return json.loads(resp)
            except Exception:
                return None
    if 'action' in data or 'reason_codes' in data or 'rationale' in data:
        return dict(data)
    return dict(data)

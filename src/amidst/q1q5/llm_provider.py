"""Local Ollama boundary for Q3/Q5; no Agent initialization or model downloads.

Callers own prompt construction from authorized runtime inputs and strict task-schema
validation. PROVIDER_VALIDATED means the transport envelope passed, not that model
claims or a Q3/Q5 decision were accepted. Tags are checked before and after generation;
this detects changes but is not an atomic server-side model lock.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def _object(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def bad_constant(_):
        raise ValueError("Non-finite JSON")

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=bad_constant)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


class Transport(Protocol):
    def request(self, method: str, path: str, payload: dict | None,
                timeout_s: float) -> bytes: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalHTTPTransport:
    """Loopback literal only; proxies and redirects cannot reach external services."""

    def __init__(self, base_url: str, *, max_response_bytes: int = 1_048_576):
        url = urlsplit(base_url)
        host = url.hostname
        if host == "localhost":
            host = "127.0.0.1"
        try:
            local = ipaddress.ip_address(host or "").is_loopback
            port = url.port or 11434
        except ValueError as exc:
            raise ValueError("Invalid local Ollama address") from exc
        if (url.scheme != "http" or not local or url.username or url.password
                or url.path not in ("", "/") or url.query or url.fragment):
            raise ValueError("Ollama must use an HTTP loopback address")
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            raise ValueError("Invalid response size limit")
        self.base_url = f"http://{'[' + host + ']' if ':' in host else host}:{port}"
        self.max_response_bytes = max_response_bytes
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, method, path, payload, timeout_s):
        if (method, path) not in (("GET", "/api/tags"), ("POST", "/api/generate")):
            raise ValueError("Unsupported Ollama operation")
        data = None if payload is None else _canonical(payload)
        request = Request(self.base_url + path, data=data, method=method,
                          headers={"Content-Type": "application/json"})
        with self.opener.open(request, timeout=timeout_s) as response:
            raw = response.read(self.max_response_bytes + 1)
        if len(raw) > self.max_response_bytes:
            raise ValueError("Ollama response exceeds configured limit")
        return raw


@dataclass(frozen=True)
class CallResult:
    text: str | None
    record: dict


class ProviderError(RuntimeError):
    def __init__(self, code: str, record: dict):
        self.code, self.record = code, record
        super().__init__(code)


class FakeTransport:
    """Scripted transport. All requests, including digest checks, are inspectable."""

    def __init__(self, responses: list[bytes | Exception]):
        self.responses = list(responses)
        self.calls: list[tuple] = []

    def request(self, method, path, payload, timeout_s):
        self.calls.append((method, path, payload, timeout_s))
        if not self.responses:
            raise AssertionError("Unexpected provider request")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class OllamaProvider:
    def __init__(self, transport: Transport, *, clock: Callable[[], float] = time.monotonic):
        self.transport, self.clock = transport, clock

    def generate(self, *, model: str, prompt: str, template: str, template_version: str,
                 options: dict, timeout_ms: int, expected_digest: str | None = None) -> CallResult:
        """One call, including metadata checks, under one caller-supplied budget.

        No retry, JSON repair, sampling defaults or schema acceptance is hidden here.
        Failure records remain available in ProviderError.record for caller fallback logs.
        """
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]+", model):
            raise ValueError("Invalid model tag")
        if not all(isinstance(v, str) and v for v in (prompt, template, template_version)):
            raise ValueError("Prompt and versioned template are required")
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("Caller must supply a positive timeout")
        if expected_digest is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ValueError("Invalid expected digest")
        allowed = {"temperature", "seed", "top_k", "top_p", "num_predict", "repeat_penalty"}
        if (not isinstance(options, dict) or options.keys() - allowed
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in options.values())):
            raise ValueError("Unsupported sampling options")
        # Boundary guard, not a claim to detect semantic GT leakage in arbitrary prose.
        if re.search(r"/Users/|/private/|/tmp/|[A-Za-z]:\\", prompt + template):
            raise ValueError("Local paths are forbidden in prompts")
        options = dict(options)
        payload = {"model": model, "prompt": prompt, "raw": True, "stream": False,
                   "format": "json", "options": options}
        start = self.clock()
        record = {
            "model": model, "model_digest": None, "prompt": prompt,
            "prompt_sha256": _hash(prompt.encode()), "prompt_template_version": template_version,
            "prompt_template_sha256": _hash(template.encode()), "sampling": options,
            "input_sha256": _hash(_canonical(payload)), "raw_output": None,
            "raw_output_sha256": None, "response_body_sha256": None,
            "validation": "NOT_RUN", "validation_errors": [], "timeout_ms": timeout_ms,
            "timed_out": False,
        }

        def finish(code):
            result = dict(record)
            result["validation"] = code
            result["stats"] = {"latency_ms": max(0, (self.clock() - start) * 1000)}
            result["content_sha256"] = _hash(
                _canonical({k: v for k, v in result.items() if k != "stats"}))
            return result

        def request(method, path, body=None):
            remaining = timeout_ms / 1000 - (self.clock() - start)
            if remaining <= 0:
                raise TimeoutError()
            raw = self.transport.request(method, path, body, remaining)
            if not isinstance(raw, bytes):
                raise ValueError("Transport must return bytes")
            if self.clock() - start >= timeout_ms / 1000:
                raise TimeoutError()
            return raw

        def digest():
            metadata = _object(request("GET", "/api/tags"))
            models = metadata.get("models")
            if not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
                raise ValueError("Invalid model inventory")
            matches = [m for m in models if m.get("name") == model or m.get("model") == model]
            if not matches:
                raise ConnectionError("Model not available locally")
            if len(matches) != 1 or not isinstance(matches[0].get("digest"), str):
                raise ValueError("Ambiguous model metadata")
            value = matches[0]["digest"]
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("Invalid model digest")
            return value

        try:
            before = digest()
            record["model_digest"] = before
            if expected_digest is not None and before != expected_digest:
                raise ValueError("Model digest does not match pin")
            raw = request("POST", "/api/generate", payload)
            record["response_body_sha256"] = _hash(raw)
            envelope = _object(raw)
            output = envelope.get("response")
            if isinstance(output, str):
                record["raw_output"] = output
                record["raw_output_sha256"] = _hash(output.encode())
            if (envelope.get("model") != model or envelope.get("done") is not True
                    or "error" in envelope or not isinstance(output, str) or not output.strip()):
                raise ValueError("Invalid generation envelope")
            if digest() != before:
                raise ValueError("Model tag changed during generation")
        except Exception as exc:
            if isinstance(exc, (TimeoutError, URLError)) and (
                    isinstance(exc, TimeoutError) or isinstance(exc.reason, TimeoutError)):
                code = "PROVIDER_TIMEOUT"
                record["timed_out"] = True
            elif isinstance(exc, (HTTPError, URLError, OSError, ConnectionError)):
                code = "PROVIDER_UNAVAILABLE"
            elif isinstance(exc, (ValueError, UnicodeError, TypeError)):
                code = "INVALID_RESPONSE"
            else:
                raise
            # Never expose exception messages containing addresses or local file paths.
            record["validation_errors"] = [code]
            raise ProviderError(code, finish(code)) from None
        return CallResult(output, finish("PROVIDER_VALIDATED"))


class FakeProvider(OllamaProvider):
    """Same envelope/audit behavior with scripted local bytes and zero networking."""

    def __init__(self, responses: list[bytes | Exception], *, clock=time.monotonic):
        super().__init__(FakeTransport(responses), clock=clock)

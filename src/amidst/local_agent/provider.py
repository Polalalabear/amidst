"""Pinned Ollama loopback transport with actual runtime token accounting."""

from __future__ import annotations

import http.client
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from .contracts import AgentDenied, ModelAction


@dataclass(frozen=True)
class ModelCompletion:
    action: ModelAction | None
    prompt_tokens: int
    output_tokens: int
    duration_ms: float
    model: str
    model_digest: str
    provider: str = "OLLAMA_LOOPBACK"
    error_code: str | None = None


class AgentProvider(Protocol):
    def identity(self) -> dict[str, Any]: ...

    def complete(self, messages: list[dict[str, str]], *, max_output_tokens: int,
                 action_schema: dict[str, Any] | None = None
                 ) -> ModelCompletion: ...


class OllamaProvider:
    def __init__(self, endpoint: str, model: str, *, model_digest: str,
                 timeout_seconds: float = 120, context_tokens: int = 8192) -> None:
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
            raise AgentDenied("AGENT_LOOPBACK_ENDPOINT_REQUIRED")
        if (not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", model)
            or not re.fullmatch(r"(?:sha256:)?[a-f0-9]{64}", model_digest)
            or not 1 <= timeout_seconds <= 180 or context_tokens not in {4096, 8192}):
            raise AgentDenied("AGENT_PINNED_MODEL_REQUIRED")
        self.host, self.port = parsed.hostname, parsed.port or 80
        self.model = model
        self.model_digest = model_digest.removeprefix("sha256:")
        self.timeout = timeout_seconds
        self.context_tokens = context_tokens

    def configured_identity(self) -> dict[str, Any]:
        """Server configuration only; version guards do not block on transport."""
        return {"provider": "OLLAMA_LOOPBACK", "model": self.model,
                "model_digest": self.model_digest, "context_tokens": self.context_tokens,
                "external_model_calls": False}

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
            connection.request("GET" if payload is None else "POST", path, body=body,
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise AgentDenied("AGENT_MODEL_UNAVAILABLE")
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise AgentDenied("AGENT_MODEL_RESPONSE_TOO_LARGE")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise AgentDenied("AGENT_INVALID_MODEL_RESPONSE")
            return result
        except AgentDenied:
            raise
        except (OSError, http.client.HTTPException, ValueError):
            raise AgentDenied("AGENT_MODEL_UNAVAILABLE") from None
        finally:
            connection.close()

    def identity(self) -> dict[str, Any]:
        models = self._request("/api/tags").get("models", ())
        found = next((m for m in models if isinstance(m, dict)
                      and m.get("name") == self.model), None)
        if found is None or str(found.get("digest", "")).removeprefix("sha256:") != (
            self.model_digest
        ):
            raise AgentDenied("AGENT_MODEL_BINDING_CHANGED")
        return self.configured_identity()

    def complete(self, messages: list[dict[str, str]], *, max_output_tokens: int,
                 action_schema: dict[str, Any] | None = None
                 ) -> ModelCompletion:
        self.identity()
        started = time.monotonic()
        response = self._request("/api/chat", {
            "model": self.model, "messages": messages, "stream": False,
            "format": action_schema or ModelAction.model_json_schema(),
            "options": {"temperature": 0, "seed": 0, "num_ctx": self.context_tokens,
                        "num_predict": max_output_tokens}, "keep_alive": "10m",
        })
        try:
            if response.get("model") != self.model or response.get("done") is not True:
                raise ValueError("incomplete or different model")
            content = response["message"]["content"]
            prompt_tokens = response["prompt_eval_count"]
            output_tokens = response["eval_count"]
            if any(type(v) is not int or v < 0 for v in (prompt_tokens, output_tokens)):
                raise ValueError("actual counts required")
            if output_tokens > max_output_tokens:
                raise ValueError("output budget exceeded")
        except (ValueError, KeyError, TypeError):
            raise AgentDenied("AGENT_INVALID_MODEL_RESPONSE") from None
        try:
            action = ModelAction.model_validate_json(content)
            error_code = None
        except (ValueError, TypeError):
            # The request actually ran: preserve reported usage even when JSON/action is rejected.
            action, error_code = None, "AGENT_INVALID_MODEL_RESPONSE"
        self.identity()
        return ModelCompletion(action, prompt_tokens, output_tokens,
                               (time.monotonic() - started) * 1000,
                               self.model, self.model_digest, error_code=error_code)

"""DP4 attention ranking: single-call API ranker (D210, D214, N3).

Contract: docs/contracts/DP4_ATTENTION_RANKING_V1.md (§3, §4.2).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
import math

from amidst.q1q5 import attention_ranking as ar

_OUTCOMES = ('OK', 'TIMEOUT', 'UNAVAILABLE', 'RETRYABLE', 'REPLAY_MISS')


def attempt_cost_usd(
    prompt_tokens: object,
    completion_tokens: object,
    price_per_mtok: tuple[float, float] | None,
) -> tuple[float, bool]:
    """Return (cost_usd, known) for a single model call."""
    if price_per_mtok is None:
        return 0.0, False
    if type(prompt_tokens) is not int or prompt_tokens < 0:
        return 0.0, False
    if type(completion_tokens) is not int or completion_tokens < 0:
        return 0.0, False
    in_price, out_price = float(price_per_mtok[0]), float(price_per_mtok[1])
    cost = (prompt_tokens * in_price + completion_tokens * out_price) / 1e6
    if not math.isfinite(cost) or cost < 0:
        return 0.0, False
    return cost, True


def rule_fallback(
    request: Mapping,
    *,
    params: ar.AttentionParams,
    requested_method: str,
    fallback_reason: str,
    wall_ms: float,
    cost_usd: float | None,
    steps: int,
) -> dict:
    """Fall back to the deterministic Rule ranker while preserving latency, cost and step count."""
    resp = ar.rank_attention(
        request,
        params=params,
        requested_method=requested_method,
        fallback_reason=fallback_reason,
    )
    resp['latency_ms'] = round(float(wall_ms) + float(resp['latency_ms']), 3)
    resp['cost_usd'] = cost_usd
    resp['steps'] = steps
    ar.validate_response(resp, request)
    return resp


class ApiRanker:
    """Single-call DP4 ranker backed by a WP2/WP3 provider callable."""

    def __init__(
        self,
        call: Callable[..., object],
        *,
        timeout_ms: int = 3000,
        max_output_tokens: int = 512,
        price_per_mtok: tuple[float, float] | None = None,
        params: ar.AttentionParams = ar.DEFAULT_PARAMS,
    ) -> None:
        self.call = call
        self.timeout_ms = timeout_ms
        self.max_output_tokens = max_output_tokens
        self.price_per_mtok = price_per_mtok
        self.params = params

    def rank(self, request: Mapping) -> dict:
        ar.validate_request(request)
        payload = copy.deepcopy(dict(request))
        ar.scan_forbidden(payload)
        try:
            attempt = self.call(
                payload,
                timeout_ms=self.timeout_ms,
                max_output_tokens=self.max_output_tokens,
            )
        except Exception:
            return rule_fallback(
                request,
                params=self.params,
                requested_method='API',
                fallback_reason='PROVIDER_UNAVAILABLE',
                wall_ms=0.0,
                cost_usd=None,
                steps=1,
            )

        outcome = getattr(attempt, 'outcome', None)
        wall_ms = getattr(attempt, 'wall_ms', None)
        if outcome not in _OUTCOMES or type(wall_ms) not in (int, float) or not math.isfinite(wall_ms) or wall_ms < 0:
            return rule_fallback(
                request,
                params=self.params,
                requested_method='API',
                fallback_reason='INVALID_RESPONSE',
                wall_ms=0.0,
                cost_usd=None,
                steps=1,
            )

        cost_val, cost_known = attempt_cost_usd(
            getattr(attempt, 'prompt_tokens', None),
            getattr(attempt, 'completion_tokens', None),
            self.price_per_mtok,
        )
        cost_usd = cost_val if cost_known else None

        if outcome == 'TIMEOUT' or wall_ms > self.timeout_ms:
            return rule_fallback(
                request,
                params=self.params,
                requested_method='API',
                fallback_reason='PROVIDER_TIMEOUT',
                wall_ms=float(wall_ms),
                cost_usd=cost_usd,
                steps=1,
            )
        if outcome in ('UNAVAILABLE', 'RETRYABLE'):
            return rule_fallback(
                request,
                params=self.params,
                requested_method='API',
                fallback_reason='PROVIDER_UNAVAILABLE',
                wall_ms=float(wall_ms),
                cost_usd=cost_usd,
                steps=1,
            )
        if outcome == 'REPLAY_MISS':
            return rule_fallback(
                request,
                params=self.params,
                requested_method='API',
                fallback_reason='REPLAY_MISS',
                wall_ms=float(wall_ms),
                cost_usd=cost_usd,
                steps=1,
            )

        raw = getattr(attempt, 'response', None)
        if not isinstance(raw, Mapping) or set(raw) != {'ranking'}:
            return rule_fallback(
                request,
                params=self.params,
                requested_method='API',
                fallback_reason='INVALID_RESPONSE',
                wall_ms=float(wall_ms),
                cost_usd=cost_usd,
                steps=1,
            )

        resp = {
            'schema_version': ar.RESPONSE_SCHEMA,
            'method': 'API',
            'requested_method': 'API',
            'ranking': copy.deepcopy(raw['ranking']),
            'latency_ms': round(float(wall_ms), 3),
            'cost_usd': cost_usd,
            'steps': 1,
            'fallback_reason': None,
        }
        try:
            ar.validate_response(resp, request)
        except ar.AttentionInputError as exc:
            reason = 'ILLEGAL_CANDIDATE' if exc.code == 'ILLEGAL_CANDIDATE' else 'INVALID_RESPONSE'
            return rule_fallback(
                request,
                params=self.params,
                requested_method='API',
                fallback_reason=reason,
                wall_ms=float(wall_ms),
                cost_usd=cost_usd,
                steps=1,
            )
        return resp

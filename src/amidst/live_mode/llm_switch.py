"""The workbench's "LLM decision" switch for live mode (docs/design/LIVE_MODE_LLM_DECISION_V1.md, A6, D242).

The switch only *requests* a mode (off / review / lead). This module decides what the backend actually does:

- ``off`` (the default): no decider, no request leaves the backend, the rule tracker output is what it was before.
- ``review`` / ``lead``: used only when a provider is usable. Otherwise the effective mode stays ``off`` (rules) and the
  reason is reported, never swallowed.

A paid provider is usable only when the *server* approved it (ApiGuard: AMIDST_API_ENABLED and a total budget above 0) and
the key exists in the environment. The key itself is never read or reported here, only whether it is set. The fake
provider has no network and no cost and is always usable.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

MODES = ("off", "review", "lead")

# reason -> (code, text shown to the operator). Codes reuse the advisor's fallback_reason vocabulary where one exists.
REASONS = {
    "BAD_MODE": ("BAD_MODE", "不認得的模式，已維持關閉"),
    "GUARD_NOT_APPROVED": ("MODE_NOT_AUTHORIZED", "後台沒有核准付費呼叫（花費護欄關閉或額度為 0），改用規則"),
    "NO_API_KEY": ("PROVIDER_UNAVAILABLE", "後台沒有設定 API key，改用規則"),
}


def resolve(requested: str, provider: str, env: Mapping | None = None, guard_cfg=None) -> dict:
    """What the backend will do for a request. ``guard_cfg`` is an ApiGuard GuardConfig (None = read the environment)."""
    env = os.environ if env is None else env
    if requested not in MODES:
        code, text = REASONS["BAD_MODE"]
        return {"requested": "off", "effective": "off", "available": False, "reason": "BAD_MODE", "reason_code": code, "reason_text": text}
    if requested == "off":
        return {"requested": "off", "effective": "off", "available": True, "reason": None, "reason_code": None, "reason_text": None}
    reason = None
    if provider != "fake":
        if guard_cfg is None:
            from amidst.q1q5.api_budget import GuardConfig
            guard_cfg = GuardConfig.from_env(env)
        if not (guard_cfg.enabled and guard_cfg.max_usd_total > 0):
            reason = "GUARD_NOT_APPROVED"
        elif not env.get("OPENAI_API_KEY"):
            reason = "NO_API_KEY"
    if reason:
        code, text = REASONS[reason]
        return {"requested": requested, "effective": "off", "available": False, "reason": reason, "reason_code": code, "reason_text": text}
    return {"requested": requested, "effective": requested, "available": True, "reason": None, "reason_code": None, "reason_text": None}


def allowed_origins(ports) -> frozenset:
    """Browser origins allowed to read and set /config from another page (the workbench): loopback on the given ports only."""
    return frozenset(f"http://{h}:{int(p)}" for p in ports for h in ("127.0.0.1", "localhost"))


def cors_headers(origin: str | None, allowed: frozenset) -> dict:
    """CORS headers for /config. Never ``*``: only an origin on the allow-list is echoed back."""
    if origin and origin in allowed:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "600"}
    return {}

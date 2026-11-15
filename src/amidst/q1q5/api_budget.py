"""Shared paid-API spend guard (D165/D166). NL parse, DP4 and WP5 all call paid adapters through ``ApiGuard``.

Default is OFF and USD 0: nothing paid runs unless the *server* opts in via environment (or a server-side JSON file named by
``AMIDST_API_CONFIG_FILE``) and sets a total budget above zero. The browser's ``mode=API`` only *requests* the paid layer.
A denial never raises: ``run`` returns ``GuardResult(allowed=False, reason=...)`` and the caller falls back.

Environment (all server side):
  AMIDST_API_ENABLED            "1" to allow paid calls (default off)
  AMIDST_API_MAX_USD_TOTAL      lifetime cap in USD (default 0 -> every call denied)
  AMIDST_API_MAX_USD_PER_DAY    default 5        AMIDST_API_MAX_CALLS_PER_DAY  default 200
  AMIDST_API_MAX_USD_PER_CALL   default 0.05     AMIDST_API_MAX_TOKENS_PER_CALL default 4000 (prompt + max output)
  AMIDST_API_MAX_CALLS_PER_MIN  default 10
  AMIDST_API_PRICES_FILE        JSON {"models": {id: {"input_usd_per_mtok": x, "output_usd_per_mtok": y}}}
                                (same shape as the ``price_table`` in agent_decision params); no price -> PRICE_UNKNOWN -> denied
  AMIDST_API_USAGE_DIR          ledger dir (default <repo>/local/evidence/api-usage)

Ledger rows (JSONL, ``usage.jsonl``) hold only: ts, caller, model, outcome, reason, prompt_tokens, completion_tokens,
est_cost_usd. Never a key, header, prompt or response. Unknown usage is charged at the worst-case estimate.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REASONS = ('API_DISABLED', 'PRICE_UNKNOWN', 'PER_CALL_TOKEN_CAP', 'PER_CALL_COST_CAP', 'RATE_LIMIT', 'DAILY_CALL_CAP',
           'DAILY_COST_CAP', 'TOTAL_BUDGET')
_CALLER = re.compile(r'[A-Za-z0-9_.:-]{1,64}')
_MODEL = re.compile(r'[A-Za-z0-9_.:/-]{1,100}')
LEDGER_NAME = 'usage.jsonl'


def default_usage_dir() -> Path:
    return Path(__file__).resolve().parents[3] / 'local' / 'evidence' / 'api-usage'


@dataclass(frozen=True)
class GuardConfig:
    enabled: bool = False
    max_usd_total: float = 0.0
    max_usd_per_day: float = 5.0
    max_calls_per_day: int = 200
    max_usd_per_call: float = 0.05
    max_tokens_per_call: int = 4000
    max_calls_per_min: int = 10
    prices: Mapping | None = None

    @classmethod
    def from_env(cls, env: Mapping | None = None) -> 'GuardConfig':
        env = os.environ if env is None else env
        values: dict = {}
        path = env.get('AMIDST_API_CONFIG_FILE')
        if path:
            try:
                doc = json.loads(Path(path).read_text('utf-8'))
                values.update(doc if isinstance(doc, dict) else {})
            except (OSError, ValueError):
                return cls()   # unreadable server config -> stay closed
        for key, name in (('enabled', 'ENABLED'), ('max_usd_total', 'MAX_USD_TOTAL'), ('max_usd_per_day', 'MAX_USD_PER_DAY'),
                          ('max_calls_per_day', 'MAX_CALLS_PER_DAY'), ('max_usd_per_call', 'MAX_USD_PER_CALL'),
                          ('max_tokens_per_call', 'MAX_TOKENS_PER_CALL'), ('max_calls_per_min', 'MAX_CALLS_PER_MIN')):
            if env.get(f'AMIDST_API_{name}') not in (None, ''):
                values[key] = env[f'AMIDST_API_{name}']
        prices = values.get('prices')
        pf = env.get('AMIDST_API_PRICES_FILE')
        if pf:
            try:
                prices = json.loads(Path(pf).read_text('utf-8')).get('models')
            except (OSError, ValueError, AttributeError):
                prices = None
        try:
            return cls(enabled=str(values.get('enabled', '')).strip().lower() in ('1', 'true', 'yes'),
                       max_usd_total=max(0.0, float(values.get('max_usd_total', 0))),
                       max_usd_per_day=max(0.0, float(values.get('max_usd_per_day', 5))),
                       max_calls_per_day=max(0, int(float(values.get('max_calls_per_day', 200)))),
                       max_usd_per_call=max(0.0, float(values.get('max_usd_per_call', 0.05))),
                       max_tokens_per_call=max(0, int(float(values.get('max_tokens_per_call', 4000)))),
                       max_calls_per_min=max(0, int(float(values.get('max_calls_per_min', 10)))),
                       prices=prices if isinstance(prices, Mapping) else None)
        except (TypeError, ValueError):
            return cls()


def estimate_cost(prices: Mapping | None, model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    price = (prices or {}).get(model)
    try:
        return (prompt_tokens * float(price['input_usd_per_mtok']) + completion_tokens * float(price['output_usd_per_mtok'])) / 1e6
    except (TypeError, KeyError, ValueError):
        return None


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str | None = None   # one of REASONS when denied
    value: object = None
    est_cost_usd: float | None = None


class ApiGuard:
    def __init__(self, config: GuardConfig | None = None, *, usage_dir: Path | str | None = None,
                 clock: Callable[[], float] = time.time):
        self.config = config if config is not None else GuardConfig.from_env()
        self.usage_dir = Path(usage_dir) if usage_dir is not None else Path(os.environ.get('AMIDST_API_USAGE_DIR') or default_usage_dir())
        self._clock, self._lock = clock, threading.Lock()
        self._starts: deque = deque()   # call start times (s) for the per-minute window
        self._pending_usd = 0.0
        self._pending_calls = 0

    @property
    def ledger_path(self) -> Path:
        return self.usage_dir / LEDGER_NAME

    # -- ledger -----------------------------------------------------------------------------------------------
    def _rows(self) -> list[dict]:
        try:
            lines = self.ledger_path.read_text('utf-8').splitlines()
        except OSError:
            return []
        rows = []
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def _append(self, row: dict) -> None:
        try:
            self.usage_dir.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + '\n')
        except OSError:
            pass   # ledger failure must not break the demo; spend state then falls back to in-memory pending only

    def _row(self, caller, model, outcome, reason, pt, ct, cost) -> dict:
        return {'ts': datetime.fromtimestamp(self._clock(), timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'caller': caller, 'model': model,
                'outcome': outcome, 'reason': reason, 'prompt_tokens': pt, 'completion_tokens': ct,
                'est_cost_usd': None if cost is None else round(cost, 9)}

    # -- gate -------------------------------------------------------------------------------------------------
    def _check(self, model, est_prompt, max_out) -> tuple[str | None, float | None]:
        c = self.config
        if not c.enabled:
            return 'API_DISABLED', None
        cost = estimate_cost(c.prices, model, est_prompt, max_out)
        if cost is None:
            return 'PRICE_UNKNOWN', None
        if est_prompt + max_out > c.max_tokens_per_call:
            return 'PER_CALL_TOKEN_CAP', cost
        if cost > c.max_usd_per_call:
            return 'PER_CALL_COST_CAP', cost
        now = self._clock()
        while self._starts and now - self._starts[0] >= 60:
            self._starts.popleft()
        if len(self._starts) >= c.max_calls_per_min:
            return 'RATE_LIMIT', cost
        today = datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%d')
        total = self._pending_usd
        day_cost, day_calls = self._pending_usd, self._pending_calls
        for r in self._rows():
            if r.get('outcome') == 'DENIED' or not isinstance(r.get('est_cost_usd'), (int, float)):
                continue
            total += r['est_cost_usd']
            if str(r.get('ts', ''))[:10] == today:
                day_cost += r['est_cost_usd']
                day_calls += 1
        if day_calls >= c.max_calls_per_day:
            return 'DAILY_CALL_CAP', cost
        if day_cost + cost > c.max_usd_per_day:
            return 'DAILY_COST_CAP', cost
        if total + cost > c.max_usd_total:
            return 'TOTAL_BUDGET', cost
        return None, cost

    def run(self, caller: str, model: str, est_prompt_tokens: int, max_output_tokens: int,
            fn: Callable[[], tuple[object, int | None, int | None]]) -> GuardResult:
        """Gate and run one paid call. ``fn`` returns ``(value, prompt_tokens, completion_tokens)`` (None = unknown, charged at
        the worst-case estimate). A denial returns ``allowed=False``; an exception from ``fn`` is charged at the estimate and re-raised."""
        if not (isinstance(caller, str) and _CALLER.fullmatch(caller) and isinstance(model, str) and _MODEL.fullmatch(model)):
            raise ValueError('invalid caller or model')
        est_prompt, max_out = max(0, int(est_prompt_tokens)), max(0, int(max_output_tokens))
        with self._lock:
            reason, cost = self._check(model, est_prompt, max_out)
            if reason is not None:
                self._append(self._row(caller, model, 'DENIED', reason, None, None, None))
                return GuardResult(False, reason, None, cost)
            self._starts.append(self._clock())
            self._pending_usd += cost
            self._pending_calls += 1
        value, pt, ct, outcome, error = None, None, None, 'OK', None
        try:
            value, pt, ct = fn()
        except BaseException as exc:  # noqa: BLE001
            outcome, error = 'ERROR', exc
        actual = estimate_cost(self.config.prices, model, pt, ct) if isinstance(pt, int) and isinstance(ct, int) else None
        charged = cost if actual is None else actual
        with self._lock:
            self._pending_usd = max(0.0, self._pending_usd - cost)
            self._pending_calls = max(0, self._pending_calls - 1)
            self._append(self._row(caller, model, outcome, None, pt if isinstance(pt, int) else None,
                                   ct if isinstance(ct, int) else None, charged))
        if error is not None:
            raise error
        return GuardResult(True, None, value, charged)


_SHARED: dict = {}


def shared_guard(env: Mapping | None = None) -> ApiGuard:
    """Process-wide guard so the per-minute window survives across requests; rebuilt when the server config changes."""
    cfg = GuardConfig.from_env(env)
    key = (cfg.enabled, cfg.max_usd_total, cfg.max_usd_per_day, cfg.max_calls_per_day, cfg.max_usd_per_call, cfg.max_tokens_per_call,
           cfg.max_calls_per_min, json.dumps(cfg.prices, sort_keys=True, default=str))
    if _SHARED.get('key') != key:
        _SHARED.update(key=key, guard=ApiGuard(cfg))
    return _SHARED['guard']


# ---- dry-run estimate (WP5: show to the user before LIVE) ------------------------------------------------------
def estimate_run(*, questions: int, model: str, avg_prompt_tokens: int, avg_output_tokens: int, calls_per_question: int = 1,
                 prices: Mapping | None = None, config: GuardConfig | None = None) -> dict:
    calls = questions * calls_per_question
    per_call = estimate_cost(prices, model, avg_prompt_tokens, avg_output_tokens)
    out = {'model': model, 'questions': questions, 'calls': calls, 'avg_prompt_tokens': avg_prompt_tokens,
           'avg_output_tokens': avg_output_tokens, 'price_known': per_call is not None,
           'est_cost_per_call_usd': None if per_call is None else round(per_call, 6),
           'est_total_usd': None if per_call is None else round(per_call * calls, 6),
           'total_tokens': calls * (avg_prompt_tokens + avg_output_tokens)}
    if config is not None and per_call is not None:
        out['would_exceed'] = [name for name, hit in (
            ('PER_CALL_TOKEN_CAP', avg_prompt_tokens + avg_output_tokens > config.max_tokens_per_call),
            ('PER_CALL_COST_CAP', per_call > config.max_usd_per_call),
            ('DAILY_CALL_CAP', calls > config.max_calls_per_day),
            ('DAILY_COST_CAP', per_call * calls > config.max_usd_per_day),
            ('TOTAL_BUDGET', per_call * calls > config.max_usd_total)) if hit]
    return out


# ---- NL parse client wrapper -----------------------------------------------------------------------------------
class GuardedNlClient:
    """Wraps a paid NL client (``.parse(text, vocab, timeout_ms)``). Denial -> NlClientError(reason), so the chain falls back
    to the next layer and the reason shows in ``fallback_trail``. ``None`` ``inner`` = key absent (NOT_CONFIGURED upstream)."""
    name = 'API'

    def __init__(self, inner, guard: ApiGuard, *, caller: str = 'nl_parse', max_output_tokens: int = 400):
        self.inner, self.guard, self.caller, self.max_output_tokens = inner, guard, caller, max_output_tokens
        self.model = getattr(inner, 'model', 'unknown')

    def __repr__(self):
        return f'GuardedNlClient({self.inner!r})'

    def parse(self, text, vocab, timeout_ms):
        from amidst.q1q5.nl_query_parse import NlClientError
        est_prompt = 400 + len(text) // 2 + 20 * (len(getattr(vocab, 'region_ids', ())) + len(getattr(vocab, 'target_labels', ())))

        def call():
            res = self.inner.parse(text, vocab, timeout_ms)
            return res, res.prompt_tokens, res.completion_tokens
        out = self.guard.run(self.caller, self.model, est_prompt, self.max_output_tokens, call)
        if not out.allowed:
            raise NlClientError(out.reason)
        return out.value


class DisabledApiClient:
    """Stands in for the paid layer when the server has it off: always denies with API_DISABLED."""
    name = 'API'

    def parse(self, text, vocab, timeout_ms):
        from amidst.q1q5.nl_query_parse import NlClientError
        raise NlClientError('API_DISABLED')

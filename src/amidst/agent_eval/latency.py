"""Latency grouping and nearest-rank percentile summary (WP5 / #515)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

GROUPS: tuple[str, str] = ('tracking_formal', 'search_relaxed')
KINDS: tuple[str, str] = ('call', 'step')

_ROOT = Path(__file__).resolve().parents[3]
FORMAL_PARAMS_PATH = _ROOT / 'configs/q1q5/agent_decision_params_v1.json'
EXPLORATORY_PARAMS_PATH = _ROOT / 'configs/q1q5/agent_decision_params_v1_exploratory.json'


def _extract_group_limits(params: Mapping[str, Any]) -> dict[str, int]:
    per_call = params.get('per_call') or {}
    per_step = params.get('per_step') or {}
    return {
        'timeout_ms': int(per_call['timeout_ms']),
        'budget_ms': int(per_step['budget_ms']),
        'max_rounds': int(per_step['max_rounds']),
    }


def group_params(
    *,
    formal_path: Path | str | None = None,
    exploratory_path: Path | str | None = None,
) -> dict[str, dict[str, int]]:
    """Return timeout/budget/max_rounds for tracking_formal and search_relaxed separately."""
    f_path = Path(formal_path) if formal_path is not None else FORMAL_PARAMS_PATH
    e_path = Path(exploratory_path) if exploratory_path is not None else EXPLORATORY_PARAMS_PATH
    formal = json.loads(f_path.read_text(encoding='utf-8'))
    exploratory = json.loads(e_path.read_text(encoding='utf-8'))
    return {
        'tracking_formal': _extract_group_limits(formal),
        'search_relaxed': _extract_group_limits(exploratory),
    }


def nearest_rank_percentile(sorted_values: list[int | float], p: int) -> int | float:
    """Nearest-rank percentile: sorted_values[ceil(p/100 * n) - 1]."""
    if not sorted_values:
        raise ValueError('cannot compute percentile of empty sequence')
    if not 1 <= p <= 100:
        raise ValueError(f'percentile must be in [1, 100], got {p}')
    n = len(sorted_values)
    idx = -(-p * n // 100) - 1
    return sorted_values[idx]


def summarize(samples: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, dict[str, int | float]]]:
    """Summarize call and step latency per group without mixing tracking_formal and search_relaxed."""
    buckets: dict[str, dict[str, list[int | float]]] = {g: {} for g in GROUPS}
    for sample in samples:
        if not isinstance(sample, Mapping):
            raise ValueError('each latency sample must be a mapping')
        group = sample.get('group')
        if group not in GROUPS:
            raise ValueError(f'unknown latency group: {group!r}; expected one of {GROUPS}')
        kind = sample.get('kind')
        if kind not in KINDS:
            raise ValueError(f'unknown latency kind: {kind!r}; expected one of {KINDS}')
        wall_ms = sample.get('wall_ms')
        if not isinstance(wall_ms, (int, float)) or isinstance(wall_ms, bool) or wall_ms < 0:
            raise ValueError(f'invalid wall_ms: {wall_ms!r}')
        buckets[group].setdefault(kind, []).append(wall_ms)

    out: dict[str, dict[str, dict[str, int | float]]] = {g: {} for g in GROUPS}
    for group in GROUPS:
        for kind, values in buckets[group].items():
            if not values:
                continue
            s = sorted(values)
            out[group][kind] = {
                'n': len(s),
                'p50': nearest_rank_percentile(s, 50),
                'p90': nearest_rank_percentile(s, 90),
                'p99': nearest_rank_percentile(s, 99),
            }
    return out

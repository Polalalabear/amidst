"""Colab/Windows run checks for the WP5 local-model arm (stdlib only; shipped inside the pack).

Three checks the notebook runs so a bad run is visible at once instead of after the whole pilot:
``gpu_residency`` (is the warmed model 100% on the GPU, from ``ollama ps``), ``probe_dp1`` (does one real DP1 request reach
the model), and ``fallback_report`` (per task type, how many rows fell back to the rule, and why).
The Colab "no GPU used" banner only watches this Python process, which never uses CUDA: Ollama does the GPU work in its own
server process, so ``ollama ps`` and ``nvidia-smi`` are the checks that count."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MAX_FALLBACK_RATE = 0.2
_GPU_ONLY = re.compile(r'(\d+)%\s*GPU\b')
_SPLIT = re.compile(r'(\d+)%\s*/\s*(\d+)%\s*CPU/GPU')
_CPU_ONLY = re.compile(r'(\d+)%\s*CPU\b')


def parse_ollama_ps(text: str) -> list[dict[str, Any]]:
    """Rows of ``ollama ps``: name and the PROCESSOR column as ``gpu_percent`` (None when it cannot be read)."""
    rows = []
    for line in text.splitlines()[1:]:
        if not line.strip():
            continue
        name = line.split()[0]
        gpu = None
        if m := _SPLIT.search(line):
            gpu = int(m.group(2))
        elif m := _GPU_ONLY.search(line):
            gpu = int(m.group(1))
        elif m := _CPU_ONLY.search(line):
            gpu = 100 - int(m.group(1))
        rows.append({'name': name, 'gpu_percent': gpu, 'line': line.strip()})
    return rows


def gpu_residency(ps_text: str, model: str) -> dict[str, Any]:
    """``ok`` only when ``ollama ps`` lists ``model`` and shows it 100% on the GPU."""
    for row in parse_ollama_ps(ps_text):
        if row['name'] == model or row['name'] == f'{model}:latest':
            return dict(row, ok=row['gpu_percent'] == 100)
    return {'name': model, 'gpu_percent': None, 'line': None, 'ok': False}


def probe_dp1(model: str, *, endpoint: str = 'http://127.0.0.1:11434', timeout_ms: int = 60000) -> dict[str, Any]:
    """Send one synthetic DP1 request through the same provider the runner uses. ``ok`` means the model answered
    (not that the answer is right); otherwise ``http_status``/``detail`` say why the provider returned UNAVAILABLE."""
    from amidst.agent_eval import wp5_fake
    from amidst.q1q5 import agent_providers as prov
    provider = prov.OllamaProvider(model=model, endpoint=endpoint)
    attempt = provider.call(wp5_fake.dp1_request(0), timeout_ms=timeout_ms, max_output_tokens=120)
    err = provider.last_error or {}
    return {'ok': attempt.outcome == 'OK' and attempt.response is not None, 'outcome': attempt.outcome,
            'wall_ms': attempt.wall_ms, 'prompt_tokens': attempt.prompt_tokens, 'completion_tokens': attempt.completion_tokens,
            'http_status': err.get('http_status'), 'detail': err.get('detail')}


def fallback_report(calls_jsonl: Path | str, threshold: float = MAX_FALLBACK_RATE) -> dict[str, Any]:
    """Per task type: rows, rule-fallback rate, reasons and sources. ``flagged`` lists types above ``threshold``;
    a type with every row PROVIDER_UNAVAILABLE is ``never_called``."""
    types: dict[str, dict[str, Any]] = {}
    for line in Path(calls_jsonl).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('outcome') != 'OK' or r.get('model_kind') == 'RULE':
            continue
        t = types.setdefault(r['task_type'], {'n': 0, 'fallback': 0, 'unavailable': 0, 'reasons': {}, 'sources': {}})
        t['n'] += 1
        t['sources'][r['decision_source']] = t['sources'].get(r['decision_source'], 0) + 1
        if r.get('fallback_reason'):
            t['fallback'] += 1
            t['reasons'][r['fallback_reason']] = t['reasons'].get(r['fallback_reason'], 0) + 1
        if r.get('fallback_reason') == 'PROVIDER_UNAVAILABLE':
            t['unavailable'] += 1
    for t in types.values():
        t['rate'] = t['fallback'] / t['n'] if t['n'] else None
        t['never_called'] = bool(t['n']) and t['unavailable'] == t['n']
    return {'threshold': threshold, 'types': types,
            'flagged': sorted(k for k, t in types.items() if (t['rate'] or 0.0) > threshold),
            'never_called': sorted(k for k, t in types.items() if t['never_called'])}

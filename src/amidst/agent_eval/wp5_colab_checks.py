"""Colab/Windows run checks for the WP5 local-model arm (stdlib only; shipped inside the pack).

Three checks the notebook runs so a bad run is visible at once instead of after the whole pilot:
``gpu_residency`` (is the warmed model 100% on the GPU, from ``ollama ps``), ``probe_dp1`` (does one real DP1 request reach
the model), and ``fallback_report`` (per task type, how many rows fell back to the rule, and why).
The Colab "no GPU used" banner only watches this Python process, which never uses CUDA: Ollama does the GPU work in its own
server process, so ``ollama ps`` and ``nvidia-smi`` are the checks that count."""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

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


def gpu_from_api_ps(doc: Any, model: str) -> dict[str, Any]:
    """GPU share from Ollama's ``/api/ps`` JSON (``size_vram / size``): the authoritative source; the CLI table is only a view of it."""
    for m in (doc.get('models') or []) if isinstance(doc, dict) else []:
        if isinstance(m, dict) and m.get('name') in (model, f'{model}:latest'):
            size, vram = m.get('size'), m.get('size_vram')
            if isinstance(size, int) and size > 0 and isinstance(vram, int):
                return {'name': m['name'], 'gpu_percent': round(100 * min(vram, size) / size), 'size': size, 'size_vram': vram,
                        'ok': vram >= size}
    return {'name': model, 'gpu_percent': None, 'ok': False}


def _cli_ps() -> str:
    return subprocess.run(['ollama', 'ps'], capture_output=True, text=True, timeout=15).stdout


def _api_ps(endpoint: str = 'http://127.0.0.1:11434') -> Any:
    return json.loads(urllib.request.urlopen(f'{endpoint}/api/ps', timeout=5).read())


def sample_gpu_residency(model: str, *, cli_ps: Callable[[], str] = _cli_ps, api_ps: Callable[[], Any] = _api_ps,
                         tries: int = 10, interval_s: float = 0.5, sleep: Callable[[float], None] = time.sleep,
                         during: Callable[[], Any] | None = None) -> dict[str, Any]:
    """Sample ``ollama ps`` / ``/api/ps`` WHILE THE MODEL IS LOADED, retrying until it is listed.

    WP5 (Colab v2): ``ollama ps`` was read after the model had already been unloaded and only the header line was captured, so
    the GPU was never confirmed. Call this right after a warm-up that used ``keep_alive`` (see ``KEEP_ALIVE``), or pass
    ``during`` (e.g. a probe request): it runs in a thread and the samples are taken while it is in flight. ``ok`` is True when
    either source shows the model 100% on the GPU; ``samples`` keeps the raw text so a miss is diagnosable."""
    box: dict[str, Any] = {}
    worker = None
    if during is not None:
        worker = threading.Thread(target=lambda: box.setdefault('during', during()), daemon=True)
        worker.start()
    samples: list[dict[str, Any]] = []
    best: dict[str, Any] = {'name': model, 'gpu_percent': None, 'line': None, 'ok': False, 'source': None}
    for i in range(tries):
        text, doc, err = '', None, None
        try:
            text = cli_ps()
        except Exception as exc:  # noqa: BLE001
            err = f'cli:{type(exc).__name__}'
        try:
            doc = api_ps()
        except Exception as exc:  # noqa: BLE001
            err = (err or '') + f' api:{type(exc).__name__}'
        cli, api = gpu_residency(text, model), gpu_from_api_ps(doc, model)
        samples.append({'try': i, 'cli_text': text, 'cli_gpu_percent': cli['gpu_percent'], 'api_gpu_percent': api['gpu_percent'], 'error': err})
        if cli['gpu_percent'] is not None or api['gpu_percent'] is not None:
            best = dict(cli if cli['gpu_percent'] is not None else api, ok=bool(cli['ok'] or api['ok']),
                        source='ollama ps' if cli['gpu_percent'] is not None else '/api/ps',
                        api_gpu_percent=api['gpu_percent'], cli_gpu_percent=cli['gpu_percent'])
            if best['ok']:
                break
        if worker is not None and not worker.is_alive() and i >= 1 and best['gpu_percent'] is None:
            sleep(interval_s)   # probe finished; one more look, then give up
        sleep(interval_s)
    if worker is not None:
        worker.join(timeout=120)
    return dict(best, samples=samples[-5:], n_samples=len(samples), during_result=box.get('during'))


KEEP_ALIVE = '10m'   # warm-up keep_alive so the model is still resident when ``ollama ps`` runs


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

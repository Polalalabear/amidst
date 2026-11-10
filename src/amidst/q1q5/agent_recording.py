"""Agent decision WP3: JSONL recording writer and offline REPLAY provider.

Design: docs/design/AGENT_DECISION_V1.md (§3.3, §6.1, §7 WP3).
Canonical JSON follows agent_decision.canonical() (sort_keys=True, compact separators,
ensure_ascii=True). Replay looks up responses by order-independent request_sha256 and
never touches the network or charges live budget caps.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
import copy
import hashlib
import json
import os
from pathlib import Path
import re

from amidst.q1q5.agent_wiring import ad

RECORDING_KEYS = frozenset({
    'request_sha256',
    'request',
    'response',
    'provider',
    'model',
    'api_model_id',
    'model_digest',
    'seed',
    'temperature',
    'candidate_order_seed',
    'wall_ms',
    'usage',
})
USAGE_KEYS = frozenset({'prompt_tokens', 'completion_tokens'})
ALLOWED_PROVIDERS = frozenset({'OPENAI', 'OLLAMA_LOOPBACK'})

_SECRET_PATTERN = re.compile(r'(?:\bsk-[A-Za-z0-9_-]{6,}|\bBearer\s+\S+)')
_PATH_PATTERN = re.compile(
    r'(?:^/[^/\s]+|^~/|^[A-Za-z]:[\\/]|^\\\\|[\\/][^\\/\s]+\.(?:json|jsonl|py|blend|mp4|png|jpg)\b)'
)


def _scan_strings_for_leaks(value, *, secret_values: tuple[str, ...]) -> None:
    if isinstance(value, str):
        for secret in secret_values:
            if secret and secret in value:
                raise ad.AgentDecisionError('FORBIDDEN_INFERENCE_INPUT', 'secret value in recording')
        if _SECRET_PATTERN.search(value):
            raise ad.AgentDecisionError('FORBIDDEN_INFERENCE_INPUT', 'secret token pattern in recording')
        if _PATH_PATTERN.search(value):
            raise ad.AgentDecisionError('FORBIDDEN_INFERENCE_INPUT', 'filesystem path in recording')
        return
    if isinstance(value, Mapping):
        for k, v in value.items():
            if isinstance(k, str):
                _scan_strings_for_leaks(k, secret_values=secret_values)
            _scan_strings_for_leaks(v, secret_values=secret_values)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _scan_strings_for_leaks(item, secret_values=secret_values)


def validate_recording_entry(entry: Mapping, *, env: Mapping[str, str] | None = None) -> dict:
    """Validate one §3.3 recording row and return a normalized copy."""
    ad.check_json_safe(entry, 'RECORDING_INVALID')
    ad._forbidden_scan(entry, 'FORBIDDEN_INFERENCE_INPUT')
    ad._keys(entry, RECORDING_KEYS, RECORDING_KEYS, 'RECORDING_INVALID', 'recording')

    req = entry['request']
    ad.validate_request(req)
    expected_sha = ad.request_sha256(req)
    if entry['request_sha256'] != expected_sha:
        raise ad.AgentDecisionError('RECORDING_INVALID', 'request_sha256 mismatch')

    if entry['provider'] not in ALLOWED_PROVIDERS:
        raise ad.AgentDecisionError('RECORDING_INVALID', 'provider')
    if not isinstance(entry['model'], str) or not entry['model'].strip():
        raise ad.AgentDecisionError('RECORDING_INVALID', 'model')
    if entry['api_model_id'] is not None and not isinstance(entry['api_model_id'], str):
        raise ad.AgentDecisionError('RECORDING_INVALID', 'api_model_id')
    if entry['model_digest'] is not None and not isinstance(entry['model_digest'], str):
        raise ad.AgentDecisionError('RECORDING_INVALID', 'model_digest')
    if entry['seed'] is not None and type(entry['seed']) is not int:
        raise ad.AgentDecisionError('RECORDING_INVALID', 'seed')
    if entry['temperature'] is not None and not ad._is_number(entry['temperature']):
        raise ad.AgentDecisionError('RECORDING_INVALID', 'temperature')
    if entry['candidate_order_seed'] is not None and type(entry['candidate_order_seed']) is not int:
        raise ad.AgentDecisionError('RECORDING_INVALID', 'candidate_order_seed')
    if not ad._is_number(entry['wall_ms']) or entry['wall_ms'] < 0:
        raise ad.AgentDecisionError('RECORDING_INVALID', 'wall_ms')

    usage = entry['usage']
    ad._keys(usage, USAGE_KEYS, USAGE_KEYS, 'RECORDING_INVALID', 'recording.usage')
    for tok_key in USAGE_KEYS:
        tok_val = usage[tok_key]
        if tok_val is not None and (type(tok_val) is not int or tok_val < 0):
            raise ad.AgentDecisionError('RECORDING_INVALID', f'recording.usage.{tok_key}')

    env_map = env if env is not None else os.environ
    active_key = env_map.get('OPENAI_API_KEY', '') if isinstance(env_map, Mapping) else ''
    secrets = (active_key.strip(),) if isinstance(active_key, str) and active_key.strip() else ()
    _scan_strings_for_leaks(entry, secret_values=secrets)

    return copy.deepcopy(dict(entry))


def recording_sha256(recording_file: str | Path) -> str:
    """Return the hex SHA-256 of a JSONL recording file."""
    return hashlib.sha256(Path(recording_file).read_bytes()).hexdigest()


def load_recordings(
    source: str | Path | Iterable[Mapping],
    *,
    env: Mapping[str, str] | None = None,
) -> list[dict]:
    """Load and validate recording entries from a JSONL file path or an iterable of dicts."""
    if isinstance(source, (str, Path)):
        raw_text = Path(source).read_text(encoding='utf-8')
        rows: list[dict] = []
        for idx, line in enumerate(raw_text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except Exception as exc:
                raise ad.AgentDecisionError('RECORDING_INVALID', f'line {idx}: invalid JSON') from exc
            rows.append(validate_recording_entry(parsed, env=env))
        return rows
    return [validate_recording_entry(item, env=env) for item in source]


class JSONLRecorder:
    """Append-only canonical JSONL recorder for WP3 live provider calls."""

    def __init__(self, target_file: str | Path, *, env: Mapping[str, str] | None = None):
        if not isinstance(target_file, (str, Path)) or not str(target_file).strip():
            raise ad.AgentDecisionError('RECORDING_INVALID', 'target_file required')
        self._target = Path(target_file)
        self._env = env
        self.count = 0

    @property
    def target_file(self) -> Path:
        return self._target

    def __repr__(self) -> str:
        return f'JSONLRecorder(count={self.count})'

    __str__ = __repr__

    def record(self, entry: Mapping) -> dict:
        validated = validate_recording_entry(entry, env=self._env)
        line_bytes = ad.canonical(validated) + b'\n'
        self._target.parent.mkdir(parents=True, exist_ok=True)
        with self._target.open('ab') as fh:
            fh.write(line_bytes)
        self.count += 1
        return validated

    __call__ = record

    def sha256(self) -> str:
        """Return SHA-256 of the recorded JSONL file bytes."""
        if not self._target.is_file():
            return hashlib.sha256(b'').hexdigest()
        return recording_sha256(self._target)

    def entries(self) -> list[dict]:
        if not self._target.is_file():
            return []
        return load_recordings(self._target, env=self._env)


class ReplayProvider:
    """Offline REPLAY provider: looks up recorded attempts by request_sha256 with zero network I/O."""

    def __init__(
        self,
        source: str | Path | Iterable[Mapping],
        *,
        env: Mapping[str, str] | None = None,
    ):
        entries = load_recordings(source, env=env)
        self._by_sha: dict[str, list[dict]] = defaultdict(list)
        for item in entries:
            self._by_sha[item['request_sha256']].append(item)
        self._cursors: dict[str, int] = defaultdict(int)
        self.calls: list[dict] = []

    def __repr__(self) -> str:
        return f'ReplayProvider(unique_requests={len(self._by_sha)}, calls={len(self.calls)})'

    __str__ = __repr__

    def reset(self) -> None:
        self._cursors.clear()
        self.calls.clear()

    def call(self, request: Mapping, *, timeout_ms: int, max_output_tokens: int) -> ad.Attempt:
        ad.validate_request(request)
        if type(timeout_ms) is not int or timeout_ms < 1:
            raise ad.AgentDecisionError('ATTEMPT_INVALID', 'timeout_ms')
        if type(max_output_tokens) is not int or max_output_tokens < 1:
            raise ad.AgentDecisionError('ATTEMPT_INVALID', 'max_output_tokens')

        sha = ad.request_sha256(request)
        self.calls.append({
            'request_sha256': sha,
            'timeout_ms': timeout_ms,
            'max_output_tokens': max_output_tokens,
        })
        bucket = self._by_sha.get(sha)
        if not bucket:
            return ad.Attempt(ad.CALL_REPLAY_MISS, 0.0)

        idx = self._cursors[sha] % len(bucket)
        self._cursors[sha] += 1
        entry = bucket[idx]
        wall_ms = float(entry['wall_ms'])
        if wall_ms > timeout_ms:
            return ad.Attempt(ad.CALL_TIMEOUT, wall_ms)
        usage = entry['usage']
        return ad.Attempt(
            ad.CALL_OK,
            wall_ms,
            copy.deepcopy(entry['response']),
            usage.get('prompt_tokens'),
            usage.get('completion_tokens'),
        )

    __call__ = call

#!/usr/bin/env python3
"""CLI entrypoint for Agent decision WP3 provider dry-run, live recording and replay.

Design: docs/design/AGENT_DECISION_V1.md (§2.3, §3.3, §6.1, §7 WP3).
Default mode is DRY_RUN: prints call and token estimates via dry_run_estimate() and makes
zero provider/transport calls without reading OPENAI_API_KEY. LIVE mode requires --live and
is refused whenever the stage is not approved or the estimate exceeds stage caps.
All relative paths resolve against amidst.paths.amidst_root() (D171 / #509).
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
from pathlib import Path, PureWindowsPath
import sys

from amidst.paths import amidst_root
from amidst.q1q5.agent_providers import DEFAULT_OLLAMA_ENDPOINT, OllamaProvider, OpenAIProvider
from amidst.q1q5.agent_recording import JSONLRecorder, ReplayProvider
from amidst.q1q5.agent_wiring import ad

DEFAULT_PARAMS_REL = 'configs/q1q5/agent_decision_params_v1.json'
DEFAULT_STAGE = 'PILOT_AND_CONSISTENCY'
DEFAULT_QUESTIONS = 16


def resolve_repo_path(raw: str | Path, *, root: Path | None = None) -> Path:
    """Resolve a path relative to amidst_root() across Windows and POSIX."""
    base = root if root is not None else amidst_root()
    if isinstance(raw, Path):
        if raw.is_absolute():
            return raw
        text = str(raw)
    else:
        text = str(raw).strip()
        win = PureWindowsPath(text)
        if win.is_absolute():
            return Path(text)
        p = Path(text)
        if p.is_absolute():
            return p
    normalized = text.replace('\\', '/')
    candidate = base / Path(normalized)
    if candidate.exists() or not Path(normalized).exists():
        return candidate
    return Path(normalized).resolve()


def _load_requests_from_jsonl(file_path: Path) -> list[dict]:
    requests: list[dict] = []
    for idx, line in enumerate(file_path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        req = row['request'] if isinstance(row, Mapping) and 'request' in row and 'schema_version' not in row else (
            row['request'] if isinstance(row, Mapping) and 'request' in row and isinstance(row['request'], Mapping) else row
        )
        ad.validate_request(req)
        requests.append(dict(req))
    return requests


def _parse_questions_arg(
    questions_arg: str | None,
    requests_arg: str | None,
    *,
    root: Path,
) -> tuple[int, list[dict] | None, Path | None]:
    if requests_arg is not None:
        req_path = resolve_repo_path(requests_arg, root=root)
        reqs = _load_requests_from_jsonl(req_path)
        return len(reqs), reqs, req_path
    if questions_arg is None:
        return DEFAULT_QUESTIONS, None, None
    text = str(questions_arg).strip()
    if text.isdigit():
        return int(text), None, None
    req_path = resolve_repo_path(text, root=root)
    reqs = _load_requests_from_jsonl(req_path)
    return len(reqs), reqs, req_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--params', default=DEFAULT_PARAMS_REL, help='Parameter set JSON path (repo-relative or absolute)')
    parser.add_argument('--stage', default=DEFAULT_STAGE, help='Evaluation stage name in parameter set')
    parser.add_argument('--questions', default=None, help='Number of questions (int) or path to requests JSONL')
    parser.add_argument('--requests', default=None, help='Path to requests JSONL file')
    parser.add_argument('--k', type=int, default=1, help='Runs per question (default: 1)')
    parser.add_argument('--models', type=int, default=None, help='Number of models to estimate (default: all in params)')
    parser.add_argument('--rounds', type=int, default=1, help='Rounds per step for estimate (default: 1)')
    parser.add_argument('--model', default='astra6', help='Model config_id for live/replay execution')
    parser.add_argument('--provider-kind', default='OPENAI', choices=['OPENAI', 'OLLAMA_LOOPBACK'])
    parser.add_argument('--ollama-endpoint', default=DEFAULT_OLLAMA_ENDPOINT)
    parser.add_argument('--recording', default=None, help='Caller-supplied JSONL recording file path')
    parser.add_argument('--out', default=None, help='Optional output file or directory for run summary JSON')
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--dry-run', action='store_true', help='Estimate calls/tokens only; make zero calls (default)')
    mode_group.add_argument('--live', action='store_true', help='Execute live provider calls (requires approved stage)')
    mode_group.add_argument('--replay', action='store_true', help='Replay from --recording JSONL with zero network calls')
    return parser


def _write_out_file(out_arg: str | None, payload: Mapping, *, root: Path, default_name: str) -> None:
    if not out_arg:
        return
    target = resolve_repo_path(out_arg, root=root)
    if target.is_dir() or str(out_arg).endswith(('/', '\\')) or target.suffix == '':
        target.mkdir(parents=True, exist_ok=True)
        target = target / default_name
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(ad.canonical(payload) + b'\n')


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: Callable | None = None,
    provider: Callable | None = None,
    env: Mapping[str, str] | None = None,
    clock_ms: Callable[[], float] | None = None,
    sleep_ms: Callable[[int], None] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = amidst_root()

    try:
        params_path = resolve_repo_path(args.params, root=root)
        params = json.loads(params_path.read_text(encoding='utf-8'))
        ad.validate_params(params)
        n_questions, loaded_requests, _ = _parse_questions_arg(args.questions, args.requests, root=root)
        estimate = ad.dry_run_estimate(
            params,
            questions=n_questions,
            k=args.k,
            models=args.models,
            rounds=args.rounds,
            stage=args.stage,
        )
    except Exception as exc:
        err = {'status': 'ERROR', 'code': getattr(exc, 'code', type(exc).__name__), 'detail': str(exc)}
        print(ad.canonical(err).decode('ascii'))
        return 2

    if not args.live and not args.replay:
        report = {
            'mode': 'DRY_RUN',
            'provider_calls': 0,
            **estimate,
            'estimate': estimate,
        }
        _write_out_file(args.out, report, root=root, default_name='dry_run.json')
        print(ad.canonical(report).decode('ascii'))
        return 0

    if args.live:
        if not estimate.get('stage_approved') or not estimate.get('fits_stage'):
            refusal = {
                'mode': 'AGENT_LIVE',
                'status': 'REFUSED',
                'reason': 'MODE_NOT_AUTHORIZED' if not estimate.get('stage_approved') else 'CALL_BUDGET_EXHAUSTED',
                'provider_calls': 0,
                **estimate,
                'estimate': estimate,
            }
            _write_out_file(args.out, refusal, root=root, default_name='live_refused.json')
            print(ad.canonical(refusal).decode('ascii'))
            return 2
        if not loaded_requests or not args.recording:
            refusal = {
                'mode': 'AGENT_LIVE',
                'status': 'REFUSED',
                'reason': 'MISSING_REQUESTS_OR_RECORDING_PATH',
                'provider_calls': 0,
            }
            print(ad.canonical(refusal).decode('ascii'))
            return 2

        rec_path = resolve_repo_path(args.recording, root=root)
        recorder = JSONLRecorder(rec_path, env=env)
        budget = ad.CallBudget(params, args.stage)
        budget.begin_session()
        if provider is not None:
            call_fn = provider
            meta: dict[str, object] = {}
        elif args.provider_kind == 'OPENAI':
            adapter = OpenAIProvider(
                model=args.model,
                params=params,
                transport=transport,
                env=env,
                budget=budget,
                recorder=recorder,
                clock_ms=clock_ms,
                sleep_ms=sleep_ms,
            )
            call_fn = adapter
            meta = adapter.provider_meta()
        else:
            adapter = OllamaProvider(
                model=args.model,
                endpoint=args.ollama_endpoint,
                transport=transport,
                budget=budget,
                recorder=recorder,
                clock_ms=clock_ms,
                sleep_ms=sleep_ms,
            )
            call_fn = adapter
            meta = adapter.provider_meta()

        records = []
        for req in loaded_requests:
            rec = ad.decide(
                req,
                mode='AGENT_LIVE',
                params=params,
                budget=budget,
                model=args.model,
                call=call_fn,
                provider_kind=args.provider_kind,
                provider_meta=meta,
            )
            records.append(rec)
        summary = {
            'mode': 'AGENT_LIVE',
            'status': 'OK',
            'decisions': len(records),
            'recording_sha256': recorder.sha256(),
        }
        _write_out_file(args.out, summary, root=root, default_name='live_summary.json')
        print(ad.canonical(summary).decode('ascii'))
        return 0

    if not loaded_requests or not args.recording:
        refusal = {
            'mode': 'AGENT_REPLAY',
            'status': 'REFUSED',
            'reason': 'MISSING_REQUESTS_OR_RECORDING_PATH',
        }
        print(ad.canonical(refusal).decode('ascii'))
        return 2

    rec_path = resolve_repo_path(args.recording, root=root)
    replay_provider = provider if provider is not None else ReplayProvider(rec_path, env=env)
    budget = ad.CallBudget(params, args.stage)
    budget.begin_session()
    records = []
    for req in loaded_requests:
        rec = ad.decide(
            req,
            mode='AGENT_REPLAY',
            params=params,
            budget=budget,
            model=args.model,
            call=replay_provider,
            provider_kind=args.provider_kind,
        )
        records.append(rec)
    summary = {
        'mode': 'AGENT_REPLAY',
        'status': 'OK',
        'decisions': len(records),
        'records_sha256': hashlib.sha256(ad.canonical(records)).hexdigest(),
    }
    _write_out_file(args.out, summary, root=root, default_name='replay_summary.json')
    print(ad.canonical(summary).decode('ascii'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

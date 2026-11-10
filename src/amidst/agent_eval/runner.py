"""Evaluation runner with default DRY_RUN, stage gate, and Colab helpers (WP5 / #515)."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from amidst.agent_eval import latency as latency_mod

_ad = importlib.import_module('amidst.q1q5.agent_decision')


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_questions(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        req = row.get('request', row)
        _ad.validate_request(req)
        rows.append(row)
    return rows


def detect_colab_gpu(nvidia_smi_output: str) -> dict[str, Any]:
    """Check GPU model from nvidia-smi output; disable formal latency claim if not L4."""
    lines = [ln.strip() for ln in (nvidia_smi_output or '').splitlines() if ln.strip()]
    gpu_name = lines[0] if lines else 'UNKNOWN'
    is_l4 = 'L4' in gpu_name.upper()
    return {
        'gpu_name': gpu_name,
        'is_l4': is_l4,
        'measure_latency': is_l4,
        'status': 'L4_VERIFIED' if is_l4 else 'NON_L4_DECISIONS_ONLY',
        'note': (
            'L4 GPU verified; formal latency measurement enabled.'
            if is_l4
            else 'Non-L4 GPU detected; recording decisions only (formal latency disabled).'
        ),
    }


def verify_ollama_models(
    models_txt: str,
    api_tags_response: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify Ollama /api/tags against models.txt and lock model digests and q4_K_M quantization."""
    expected = [
        ln.strip()
        for ln in (models_txt or '').splitlines()
        if ln.strip() and not ln.strip().startswith('#')
    ]
    installed = {
        str(m.get('name') or m.get('model') or ''): m
        for m in (api_tags_response.get('models') or [])
        if isinstance(m, Mapping)
    }
    locked: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    non_q4: list[str] = []
    for spec in expected:
        name, _, pinned_digest = spec.partition('@')
        name = name.strip()
        pinned_digest = pinned_digest.strip()
        info = installed.get(name)
        if info is None:
            missing.append(name)
            continue
        digest = str(info.get('digest') or '')
        details = info.get('details') if isinstance(info.get('details'), Mapping) else {}
        quant = str(details.get('quantization_level') or '')
        if 'q4_k_m' not in name.lower() and 'q4_k_m' not in quant.lower():
            non_q4.append(name)
        if pinned_digest and digest and pinned_digest != digest:
            missing.append(f'{name} (digest mismatch: expected {pinned_digest}, got {digest})')
            continue
        locked[name] = {
            'digest': digest,
            'quantization_level': quant or ('q4_K_M' if 'q4_k_m' in name.lower() else 'UNKNOWN'),
            'size': info.get('size'),
        }
    return {
        'valid': not missing and not non_q4,
        'locked_models': locked,
        'missing_or_mismatched': missing,
        'non_q4_k_m': non_q4,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='amidst.agent_eval.runner',
        description='Run Agent evaluation in DRY_RUN (default) or stage-gated LIVE mode.',
    )
    parser.add_argument('--questions', required=True, help='Path to requests_v1.jsonl')
    parser.add_argument('--params', required=True, help='Path to agent_decision_params_v1.json')
    parser.add_argument('--stage', required=True, help='Stage name in params["stages"]')
    parser.add_argument('--out', required=True, help='Output directory')
    parser.add_argument('--k', type=int, default=1, help='Repetitions per question (default: 1)')
    parser.add_argument('--live', action='store_true', help='Enable LIVE mode (requires approved stage)')
    parser.add_argument('--model', default=None, help='Single model override (defaults to params["models"])')
    parser.add_argument(
        '--group',
        default='tracking_formal',
        choices=list(latency_mod.GROUPS),
        help='Latency group (tracking_formal or search_relaxed)',
    )
    return parser


def main(argv: Sequence[str] | None = None, *, provider: Any = None) -> int:
    """Run evaluation CLI without reading OPENAI_API_KEY from os.environ."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    q_path = Path(args.questions)
    p_path = Path(args.params)
    out_dir = Path(args.out)

    params_bytes = p_path.read_bytes()
    params = json.loads(params_bytes.decode('utf-8'))
    questions = _load_questions(q_path)

    if args.stage not in (params.get('stages') or {}):
        return 1

    estimate = _ad.dry_run_estimate(
        params,
        questions=len(questions),
        k=args.k,
        stage=args.stage,
    )

    if not args.live:
        out_dir.mkdir(parents=True, exist_ok=True)
        dry_report = {
            'mode': 'DRY_RUN',
            'provider_calls': 0,
            'estimate': estimate,
        }
        (out_dir / 'dry_run.json').write_bytes(_ad.canonical(dry_report) + b'\n')
        return 0

    stage_cfg = params['stages'][args.stage]
    if not stage_cfg.get('approved', False) or not estimate.get('fits_stage', False):
        return 1
    if provider is None:
        return 1

    models = [args.model] if args.model else [
        m['config_id'] if isinstance(m, Mapping) else str(m)
        for m in (params.get('models') or [])
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    budget = _ad.CallBudget(params, args.stage)

    recordings: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    latency_samples: list[dict[str, Any]] = []

    for model_name in models:
        for q_row in questions:
            req = q_row.get('request', q_row)
            req_sha = q_row.get('request_sha256') or _ad.request_sha256(req)
            for run_idx in range(args.k):
                budget.begin_session()
                rec = _ad.decide(
                    req,
                    mode='AGENT_LIVE',
                    params=params,
                    budget=budget,
                    model=model_name,
                    call=provider,
                    provider_kind='OPENAI',
                )
                rec_copy = dict(rec)
                rec_copy['run_index'] = run_idx
                recordings.append(rec_copy)
                attempts = rec.get('attempts') or []
                step_wall_ms = sum(
                    float(a.get('wall_ms', 0.0))
                    for a in attempts
                    if isinstance(a, Mapping)
                )
                decisions.append({
                    'request_sha256': req_sha,
                    'model': model_name,
                    'run_index': run_idx,
                    'answer': rec['final_answer'],
                    'source': rec['decision_source'],
                    'fallback_reason': rec['fallback_reason'],
                    'rounds_used': len(attempts),
                    'wall_ms': step_wall_ms,
                })
                latency_samples.append({
                    'group': args.group,
                    'kind': 'step',
                    'wall_ms': step_wall_ms,
                })
                for a_rec in attempts:
                    if isinstance(a_rec, Mapping) and isinstance(a_rec.get('wall_ms'), (int, float)):
                        latency_samples.append({
                            'group': args.group,
                            'kind': 'call',
                            'wall_ms': a_rec['wall_ms'],
                        })

    rec_bytes = b''.join(_ad.canonical(r) + b'\n' for r in recordings)
    dec_bytes = b''.join(_ad.canonical(d) + b'\n' for d in decisions)
    lat_summary = latency_mod.summarize(latency_samples)
    lat_bytes = _ad.canonical(lat_summary) + b'\n'

    (out_dir / 'recordings.jsonl').write_bytes(rec_bytes)
    (out_dir / 'decisions.jsonl').write_bytes(dec_bytes)
    (out_dir / 'latency.json').write_bytes(lat_bytes)

    manifest = {
        'mode': 'LIVE',
        'stage': args.stage,
        'group': args.group,
        'k': args.k,
        'models': models,
        'n_questions': len(questions),
        'n_decisions': len(decisions),
        'params_sha256': _sha256_bytes(_ad.canonical(params)),
        'questions_sha256': _sha256_bytes(q_path.read_bytes()),
        'recordings_sha256': _sha256_bytes(rec_bytes),
        'decisions_sha256': _sha256_bytes(dec_bytes),
        'latency_sha256': _sha256_bytes(lat_bytes),
    }
    (out_dir / 'MANIFEST.json').write_bytes(_ad.canonical(manifest) + b'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

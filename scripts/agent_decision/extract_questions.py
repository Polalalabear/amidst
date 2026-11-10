#!/usr/bin/env python3
"""Extract Agent decision question bank (and optional S2 synthetic questions) without modifying response() (#515)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from amidst.agent_eval import question_bank as qb
from amidst.agent_eval import synthetic_perturbation as sp


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='extract_questions.py',
        description='Build Agent evaluation question bank (requests_v1.jsonl + MANIFEST.json).',
    )
    parser.add_argument('--requests', required=True, help='Input JSON or JSONL of AgentRequests')
    parser.add_argument('--out', required=True, help='Output directory for requests_v1.jsonl and MANIFEST.json')
    parser.add_argument('--commit', required=True, help='Git commit SHA')
    parser.add_argument('--params', help='Path to agent_decision_params_v1.json (or pass --params-sha256)')
    parser.add_argument('--params-sha256', help='Explicit params SHA-256 hex')
    parser.add_argument('--scene', help='Path to scene file (or pass --scene-sha256)')
    parser.add_argument('--scene-sha256', help='Explicit scene SHA-256 hex')
    parser.add_argument('--source-run', required=True, help='Source run identifier')
    parser.add_argument('--question-class', default='REAL', choices=['REAL', 'SYNTHETIC_PERTURBATION'])
    parser.add_argument('--safe-index', help='Optional safe_index.json path to also generate S2 synthetic questions')
    parser.add_argument('--s2-seed', type=int, default=7, help='Seed for S2 synthetic generation')
    parser.add_argument('--s2-per-point', type=int, default=2, help='Synthetic variants per DP1 question')
    parser.add_argument('--s2-out', help='Output directory for S2 synthetic questions (defaults to <out>/s2)')
    return parser


def _load_requests(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return []
    if path.suffix == '.jsonl':
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        data = json.loads(text)
        rows = data if isinstance(data, list) else data.get('requests', [])
    return [r.get('request', r) for r in rows]


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    params_sha = args.params_sha256 or (_sha256_file(Path(args.params)) if args.params else '')
    scene_sha = args.scene_sha256 or (_sha256_file(Path(args.scene)) if args.scene else '')
    if not params_sha or not scene_sha:
        parser.error('must provide --params/--params-sha256 and --scene/--scene-sha256')

    requests = _load_requests(Path(args.requests))
    questions = qb.build_questions(
        requests,
        commit=args.commit,
        params_sha256=params_sha,
        scene_sha256=scene_sha,
        source_run=args.source_run,
        question_class=args.question_class,
    )
    out_dir = Path(args.out)
    qb.write_question_bank(questions, out_dir)

    if args.safe_index:
        dp1_questions = [q for q in questions if q['decision_point'] == 'DP1']
        s2_out = Path(args.s2_out) if args.s2_out else (out_dir / 's2')
        sp.generate_synthetic(
            dp1_questions,
            safe_index_path=Path(args.safe_index),
            seed=args.s2_seed,
            per_point=args.s2_per_point,
            out_dir=s2_out,
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

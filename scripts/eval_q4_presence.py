"""Evaluation-only Q4 sample plan / imported T/F scoring; never loads GT or RGB."""
import argparse
import json
from pathlib import Path

from amidst.evaluation.q4_presence_eval import (
    EvaluationError, canonical, decode_jsonl, score_reviews, select_claims, sha,
)


def pinned(path, digest):
    raw = Path(path).read_bytes()
    if sha(raw) != digest:
        raise EvaluationError('Input file pin mismatch')
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    sample = commands.add_parser('sample')
    sample.add_argument('--claims', required=True)
    sample.add_argument('--claims-sha256', required=True)
    sample.add_argument('--count', required=True, type=int)
    sample.add_argument('--seed', required=True)
    score = commands.add_parser('score')
    for name in ['reviews', 'reviews-sha256', 'manifest', 'manifest-sha256']:
        score.add_argument('--' + name, required=True)
    for sub in [sample, score]:
        sub.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'sample':
            rows = decode_jsonl(pinned(args.claims, args.claims_sha256))
            report = select_claims(rows, count=args.count, seed=args.seed, claims_sha256=args.claims_sha256)
        else:
            rows = decode_jsonl(pinned(args.reviews, args.reviews_sha256))
            manifest = json.loads(pinned(args.manifest, args.manifest_sha256))
            report = score_reviews(rows, manifest, reviews_sha256=args.reviews_sha256,
                                   manifest_sha256=args.manifest_sha256)
        # Exclusive creation preserves frozen reports; no overwriting a prior run.
        with Path(args.output).open('xb') as stream:
            stream.write(canonical(report) + b'\n')
    except (EvaluationError, OSError, ValueError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

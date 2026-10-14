"""Run the isolated, approved Case 2/3 experiment stages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amidst.finalization.scoped_export import freeze_export
from amidst.finalization.scoped_pipeline import evaluate_scoped_dataset, infer_scoped_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="stage", required=True)
    freeze = commands.add_parser("freeze-export")
    freeze.add_argument("--config", type=Path, required=True)
    freeze.add_argument("--source", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--experiment", type=Path, required=True)
    infer = commands.add_parser("infer")
    infer.add_argument("--dataset", type=Path, required=True)
    infer.add_argument("--config", type=Path, required=True)
    infer.add_argument("--output", type=Path, required=True)
    infer.add_argument("--reordered", action="store_true")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--dataset", type=Path, required=True)
    evaluate.add_argument("--inference", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.stage == "freeze-export":
        result = freeze_export(
            args.config, args.source, args.output, root=root, experiment_path=args.experiment
        )
    elif args.stage == "infer":
        result = infer_scoped_dataset(
            args.dataset, args.config, args.output, root=root, reordered=args.reordered
        )
    else:
        result = evaluate_scoped_dataset(args.dataset, args.inference, args.output, root=root)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

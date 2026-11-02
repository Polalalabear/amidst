#!/usr/bin/env python3
"""Build the LOCAL CQ-27 framework; never send or approve a package."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from amidst.q1q5.yyin_main_pack import PackError, build_pack, load


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True, help="LOCAL source paths and explicit file pins")
    parser.add_argument("--synthetic-only", action="store_true", help="Explicit test fixtures, never formal data")
    parser.add_argument("--s1-inputs", type=Path, help="Explicit review source directory and receipt pin")
    args = parser.parse_args(argv)
    try:
        result = build_pack(args.output, inputs=load(args.inputs.read_bytes()), synthetic_only=args.synthetic_only,
                            s1_inputs=load(args.s1_inputs.read_bytes()) if args.s1_inputs else None)
    except (PackError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc), "release_authorized": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

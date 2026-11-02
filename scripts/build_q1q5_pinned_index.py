"""Prepare or explicitly execute one frozen r004 registration, without discovery."""

import argparse
from pathlib import Path

from amidst.q1q5.baseline_runner import save
from amidst.q1q5.production_plan import document, prepare, produce


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "plan-sha256", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--binding")
    parser.add_argument("--binding-sha256")
    parser.add_argument("--permit-real-rgb", action="store_true")
    args = parser.parse_args(argv)
    plan = document({"path": args.plan, "file_sha256": args.plan_sha256})
    if not args.permit_real_rgb:
        save(Path(args.output), prepare(plan))
        return 2
    if not args.binding or not args.binding_sha256:
        parser.error("Pinned frozen binding required before real production")
    binding = document({"path": args.binding, "file_sha256": args.binding_sha256})
    produce(plan, binding, Path(args.output), permit_real_rgb=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only production preflight; writes one new private report, never RGB/index."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from amidst.q1q5.production_preflight import inspect_protocol, inspect_review_metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--review-manifest", type=Path)
    parser.add_argument("--review-manifest-sha256")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if bool(args.review_manifest) != bool(args.review_manifest_sha256):
        parser.error("review manifest and independent file pin required together")
    if (
        not args.output.is_absolute()
        or args.output.resolve() != args.output
        or not args.output.parent.is_dir()
        or args.output.exists()
    ):
        parser.error("new canonical output file with existing parent required")
    before = subprocess.check_output(["df", "-k", str(args.output.parent)], text=True)
    report = inspect_protocol(
        args.protocol, args.protocol_sha256, repo=args.repo, data_root=args.data_root
    )
    if args.review_manifest:
        report["review_context"] = inspect_review_metadata(
            args.review_manifest, args.review_manifest_sha256
        )
    report["df_before_k"] = before
    report["df_after_k"] = subprocess.check_output(["df", "-k", str(args.output.parent)], text=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(report, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "reason": report["reason"],
                "checks": len(report["checks"]),
            }
        )
    )
    return 2 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

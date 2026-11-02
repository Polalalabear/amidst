#!/usr/bin/env python3
"""Contract-conformance checks for Q1–Q5 (docs/contracts/Q1_Q2_FIRST_DEMO_V1.md, DRAFT).

Checks the contract layer only (schemas, closed lists, invariants). It does not judge recognition
quality or whether the demo story is right; that is the job of the human review page.

  --recorded DIR                      check recorded request/response/context JSON files
  --base-url http://127.0.0.1:PORT    POST the request files in --requests to a loopback backend
                                      (needs --endpoint-map: the contract defines no endpoints)

Exit code 0 only when the overall result is PASS (or INCOMPLETE with --allow-incomplete);
1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from amidst.evaluation.q1q5_conformance import (
    Doc,
    build_report,
    exit_code,
    fetch_backend,
    file_sha256,
    list_checks,
    load_directory,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--recorded", type=Path, help="directory of recorded JSON / JSONL documents")
    mode.add_argument("--base-url", help="loopback backend, e.g. http://127.0.0.1:8000")
    p.add_argument(
        "--requests",
        type=Path,
        help="(base-url mode) directory with request files and context documents",
    )
    p.add_argument(
        "--endpoint-map",
        type=Path,
        help="(base-url mode) JSON {schema_version: path}; the contract defines none",
    )
    p.add_argument(
        "--probe-forbidden",
        action="store_true",
        help="(base-url mode) also send each request with a forbidden extra field; expect HTTP 422",
    )
    p.add_argument(
        "--params",
        type=Path,
        help="parameter_set.json (contract §11); unset values -> SKIPPED_PARAM_UNSET",
    )
    p.add_argument("--only", help="comma-separated check ids to run")
    p.add_argument("--output", type=Path, help="write the JSON report here (default: stdout)")
    p.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="exit 0 when the only gaps are SKIPPED_PARAM_UNSET (never hides FAIL)",
    )
    p.add_argument("--list-checks", action="store_true", help="print the check registry and exit")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_checks:
        print(json.dumps(list_checks(), ensure_ascii=False, indent=2))
        return 0
    if not args.recorded and not args.base_url:
        print("error: choose --recorded DIR or --base-url URL", file=sys.stderr)
        return 1
    only = set(args.only.split(",")) if args.only else None
    gaps: list[dict] = []
    try:
        if args.recorded:
            docs, mode = load_directory(args.recorded), "recorded"
        else:
            if not args.requests or not args.endpoint_map:
                print(
                    "error: --base-url needs --requests DIR and --endpoint-map FILE "
                    "(the contract defines no endpoints, U04)",
                    file=sys.stderr,
                )
                return 1
            docs, mode = load_directory(args.requests), "base-url"
            endpoint_map = json.loads(args.endpoint_map.read_text(encoding="utf-8"))
            responses, gaps = fetch_backend(args.base_url, docs, endpoint_map, args.probe_forbidden)
            docs += responses
        params_file = None
        if args.params:
            raw = json.loads(args.params.read_text(encoding="utf-8"))
            params_file = (args.params.name, file_sha256(args.params))
            docs = [d for d in docs if d.kind != "parameter_set"]
            docs.append(
                Doc(args.params.name, "parameter_set", raw, params_file[1], args.params.stem, "")
            )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    report = build_report(docs, mode, params_file=params_file, only=only, extra_findings=gaps)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    summary = report["summary"]
    print(
        f"[q1q5-conformance] overall={summary['overall']} {summary['by_status']}", file=sys.stderr
    )
    return exit_code(report, args.allow_incomplete)


if __name__ == "__main__":
    sys.exit(main())

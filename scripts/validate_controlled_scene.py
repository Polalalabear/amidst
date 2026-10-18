"""Validate a controlled-scene safe bundle against the contract and the CS-B design (E package).

Reads only ``scene_static.json``, ``manifest.json``, ``cameras.json``, ``rgb_index.json`` and
``runtime_profile.json`` from the given safe-bundle directory.  It never opens private data, GT,
masks or images.  Exit code: 0 PASS, 1 FAIL, 2 usage error.

    PYTHONPATH=src python scripts/validate_controlled_scene.py \
        --safe-dir data/pilot/controlled_scene_v1/runs/<run_id>/safe_bundle \
        --output /path/outside/the/bundle/report.json [--param min_clearance_m=0.1] [--no-design]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from amidst.evaluation.map_verification import ensure_output_outside_inputs
from amidst.scene_markers import ValidationParams, validate_safe_bundle
from amidst.scene_markers.contract import SAFE_FILENAMES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--safe-dir",
        type=Path,
        required=True,
        help="safe bundle directory (runs/<run_id>/safe_bundle)",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        help="marker template (default: configs/controlled_scene_v1_marker_template.json)",
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a tolerance/threshold (repeatable)",
    )
    parser.add_argument(
        "--no-design",
        action="store_true",
        help="skip the design-reference layer; contract rules only",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write the JSON report here (must be outside the safe bundle)",
    )
    args = parser.parse_args(argv)

    overrides: dict[str, str] = {}
    for item in args.param:
        key, sep, value = item.partition("=")
        if not sep:
            parser.error(f"--param expects KEY=VALUE, got {item!r}")
        overrides[key] = value
    try:
        params = ValidationParams.from_overrides(overrides)
        if args.output is not None:
            ensure_output_outside_inputs(
                args.output, [args.safe_dir / name for name in SAFE_FILENAMES.values()]
            )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = validate_safe_bundle(
        args.safe_dir, template_path=args.template, params=params, design=not args.no_design
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    summary = report["summary"]
    print(
        f"{report['status']}: {summary['rules_failed']} rule(s) failed, {summary['errors']} "
        f"error(s), {summary['rules_skipped']} skipped",
        file=sys.stderr,
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

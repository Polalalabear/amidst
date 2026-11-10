#!/usr/bin/env python3
"""RQ1 ground-contact report from a frozen contact-control validation run (read-only inputs)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from amidst.engineering.contact_rq1 import (
    ALL_CAMERAS,
    DEFAULT_MAX_SPEED_M_S,
    build_report,
    load_errors,
    paired_errors,
)
from amidst.engineering.contact_rq1_charts import (
    coverage_rejection_chart,
    error_distribution_chart,
    error_over_time_chart,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--errors", type=Path, required=True, help="auditorium/errors.csv")
    parser.add_argument(
        "--auditorium-comparison", type=Path, required=True, help="auditorium-comparison.csv"
    )
    parser.add_argument(
        "--office-comparison", type=Path, required=True, help="office-comparison.csv"
    )
    parser.add_argument("--visibility", type=Path, required=True, help="auditorium/visibility.csv")
    parser.add_argument("--evaluation", type=Path, required=True, help="auditorium/evaluation.json")
    parser.add_argument("--receipt", type=Path, required=True, help="receipt.json")
    parser.add_argument("--report", type=Path, required=True, help="output JSON report path")
    parser.add_argument("--chart-dir", type=Path, required=True, help="output directory for PNGs")
    parser.add_argument("--max-speed", type=float, default=DEFAULT_MAX_SPEED_M_S)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs = [
        args.errors,
        args.auditorium_comparison,
        args.office_comparison,
        args.visibility,
        args.evaluation,
        args.receipt,
    ]
    input_dirs = {path.resolve().parent for path in inputs}
    for output in (args.report.resolve().parent, args.chart_dir.resolve()):
        if output in input_dirs:
            raise SystemExit(f"refusing to write into an input directory: {output}")

    report = build_report(
        errors_csv=args.errors,
        auditorium_comparison_csv=args.auditorium_comparison,
        office_comparison_csv=args.office_comparison,
        visibility_csv=args.visibility,
        evaluation_json=args.evaluation,
        receipt_json=args.receipt,
        max_speed_m_s=args.max_speed,
    )
    args.chart_dir.mkdir(parents=True, exist_ok=True)
    error_rows = load_errors(args.errors)
    charts = [
        error_over_time_chart(error_rows, args.chart_dir / "rq1_error_over_time.png"),
        error_distribution_chart(
            paired_errors(error_rows), args.chart_dir / "rq1_error_distribution.png"
        ),
        coverage_rejection_chart(report, args.chart_dir / "rq1_coverage_rejection.png"),
    ]
    report["charts"] = [chart.name for chart in charts]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    errors = report["auditorium"]["errors"][ALL_CAMERAS]["paired"]
    coverage = report["auditorium"]["coverage"]["v2"][ALL_CAMERAS]
    office = report["office"][ALL_CAMERAS]
    print(
        f"paired n={errors['v1']['count']}: mean {errors['v1']['mean_m']:.3f} -> "
        f"{errors['v2']['mean_m']:.3f} m, max {errors['v1']['max_m']:.3f} -> "
        f"{errors['v2']['max_m']:.3f} m"
    )
    print(f"v2 coverage {coverage['with_position']}/{coverage['total']} timestamps")
    print(f"office positions {office['v1_positions']} -> {office['v2_kept']}")
    print(f"crosscheck all_match={report['crosscheck']['all_match']}")
    print(f"report {args.report}")
    for chart in charts:
        print(f"chart {chart}")
    return 0 if report["crosscheck"]["all_match"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""Validate independent review bytes; missing annotations return exit 2, never invented answers."""

import argparse
from pathlib import Path

from amidst.evaluation.q1_query_eval import PinnedSchemas
from amidst.evaluation.q3_review_import import import_review, read_csv, score_review
from amidst.q1q5.production_preflight import read_pinned, strict_json


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["review", "candidates", "freeze", "scope"]:
        p.add_argument("--" + name, type=Path, required=True)
        p.add_argument("--" + name + "-sha256", required=True)
    p.add_argument("--schema-kit", type=Path, required=True)
    p.add_argument("--new-version", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--predictions", type=Path)
    p.add_argument("--predictions-sha256")
    p.add_argument("--evaluation-authority", type=Path)
    p.add_argument("--evaluation-authority-sha256")
    p.add_argument("--permit-evaluation", action="store_true")
    a = p.parse_args(argv)
    rows = read_csv(a.review, a.review_sha256)
    candidates = [
        strict_json(line) for line in read_pinned(a.candidates, a.candidates_sha256).splitlines()
    ]
    report = import_review(
        rows,
        candidates,
        strict_json(read_pinned(a.freeze, a.freeze_sha256)),
        strict_json(read_pinned(a.scope, a.scope_sha256)),
        version=a.new_version,
        schemas=PinnedSchemas(a.schema_kit),
        review_pin=a.review_sha256,
        candidate_pin=a.candidates_sha256,
        scope_pin=a.scope_sha256,
        output=a.output,
    )
    print(report["status"])
    if any(
        [
            a.predictions,
            a.predictions_sha256,
            a.evaluation_authority,
            a.evaluation_authority_sha256,
            a.permit_evaluation,
        ]
    ):
        if not all(
            [
                a.predictions,
                a.predictions_sha256,
                a.evaluation_authority,
                a.evaluation_authority_sha256,
                a.permit_evaluation,
            ]
        ):
            p.error("explicit predictions / evaluation authority pins and permit all required")
        score_review(
            a.output,
            report,
            strict_json(read_pinned(a.scope, a.scope_sha256)),
            schemas=PinnedSchemas(a.schema_kit),
            scope_pin=a.scope_sha256,
            predictions=a.predictions,
            predictions_pin=a.predictions_sha256,
            authority=a.evaluation_authority,
            authority_pin=a.evaluation_authority_sha256,
            permit=a.permit_evaluation,
        )
    return 0 if report["status"] == "VALIDATED_REVIEW_BYTES" else 2


if __name__ == "__main__":
    raise SystemExit(main())

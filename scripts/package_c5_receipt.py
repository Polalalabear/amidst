"""Package complete derived API evidence losslessly with a small review receipt."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

from amidst.engineering.registry import content_hash


def region_comparison(before, after):
    """Count complete source-map lattice cells, summed over time and union in XY."""

    def extent(response):
        rows, union = [], set()
        sizes = {r["cell_size_m"] for r in response["reachable_regions"]}
        if len(sizes) != 1:
            raise ValueError("REGION_CELL_SIZE_UNAVAILABLE")
        size = next(iter(sizes))
        for region in response["reachable_regions"]:
            if region.get("truncated") is not False:
                raise ValueError("REGION_SAMPLES_TRUNCATED")
            cells = {tuple(xy) for xy in region["samples"]}
            if abs(len(cells) * size**2 - region["area_m2"]) > 1e-6:
                raise ValueError("REGION_AREA_COUNT_MISMATCH")
            union.update(cells)
            rows.append(
                {
                    "timestamp_s": region["timestamp_s"],
                    "cells": len(cells),
                    "area_m2": region["area_m2"],
                }
            )
        return {
            "per_timestamp": rows,
            "sum_cells": sum(r["cells"] for r in rows),
            "sum_area_m2": sum(r["area_m2"] for r in rows),
            "union_cells": len(union),
            "union_area_m2": len(union) * size**2,
            "cell_size_m": size,
        }

    first, last = extent(before), extent(after)
    return {
        "before": first,
        "after": last,
        "cells_removed_sum": first["sum_cells"] - last["sum_cells"],
        "cells_removed_union": first["union_cells"] - last["union_cells"],
        "sum_reduction_percent": 100 * (1 - last["sum_cells"] / first["sum_cells"])
        if first["sum_cells"]
        else None,
        "union_reduction_percent": 100 * (1 - last["union_cells"] / first["union_cells"])
        if first["union_cells"]
        else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "output", "receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.receipt.exists():
        raise FileExistsError("OUTPUT_EXISTS")
    raw = args.input.read_bytes()
    payload = json.loads(raw)
    if payload["output_sha256"] != content_hash(
        {k: v for k, v in payload.items() if k != "output_sha256"}
    ):
        raise ValueError("FULL_RESPONSE_HASH_MISMATCH")
    compressed = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9
    ) as stream:
        stream.write(raw)
    data = compressed.getvalue()
    if gzip.decompress(data) != raw:
        raise RuntimeError("LOSSLESS_CHECK_FAILED")
    with args.output.open("xb") as stream:
        stream.write(data)
    b = payload["initial"]["blind_hypotheses"]
    f = payload["retrieval_feedback_rerun"]["blind_hypotheses"]
    retrieval = payload["retrieval"]
    without = payload["without_negative_evidence"]["blind_hypotheses"]
    before_area = sum(r["area_m2"] for r in without["reachable_regions"])
    after_area = sum(r["area_m2"] for r in b["reachable_regions"])
    summary = {
        "schema_version": "office-demo.c5-result-receipt.v1",
        "source_sha256": payload["source_sha256"],
        "run_id": payload["run_id"],
        "gt_read": False,
        "original_missing_null_count": payload["original_missing_null_count"],
        "visibility_index_summary": payload.get("visibility_index_summary"),
        "negative_evidence_comparison": {
            "without_mode": without["negative_evidence_mode"],
            "with_mode": b["negative_evidence_mode"],
            "without_hypotheses": len(without["hypotheses"]),
            "with_hypotheses": len(b["hypotheses"]),
            "without_output_sha256": without["output_sha256"],
            "with_output_sha256": b["output_sha256"],
            "sum_region_area_before_m2": before_area,
            "sum_region_area_after_m2": after_area,
            "region_area_reduction_percent": 100 * (1 - after_area / before_area)
            if before_area
            else None,
            "interpretation": "NEGATIVE_EVIDENCE_APPLIED_BEFORE_HYPOTHESIS_GENERATION",
            "detector_contrast_and_partial_occlusion_misses": "NOT_VERIFIED",
        },
        "region_comparison_by_origin": {
            "BLIND_INTERVAL_BASELINE": region_comparison(without, b),
            "RETRIEVAL_FEEDBACK_ADDITIONAL_TO_BASELINE": region_comparison(b, f),
        },
        "complete_artifact": {
            "filename": args.output.name,
            "gzip_sha256": hashlib.sha256(data).hexdigest(),
            "decoded_sha256": hashlib.sha256(raw).hexdigest(),
            "decoded_canonical_sha256": payload["output_sha256"],
            "gzip_mtime": 0,
            "gzip_filename": "",
        },
        "initial": {
            "status": b["status"],
            "reason": b["reason"],
            "hypotheses": len(b["hypotheses"]),
            "regions": len(b["reachable_regions"]),
            "output_sha256": b["output_sha256"],
            "negative_evidence_applied": b["negative_evidence_applied"],
            "speed_checks": [h["checks"]["speed"] for h in b["hypotheses"]],
            "unseen_checks": [h["checks"]["unseen"] for h in b["hypotheses"]],
        },
        "retrieval": {
            "query_id": retrieval["query_id"],
            "stats": retrieval["stats"],
            "frame_evaluations": retrieval["frame_evaluations"],
            "frame_outcomes": retrieval["frame_outcomes"],
            "invalid_applied_frame_keys": retrieval["invalid_applied_frame_keys"],
            "entry_fingerprints": [
                {
                    "negative_evidence_ref": e["negative_evidence_ref"],
                    "origin": e["origin"],
                    "sha256": e["sha256"],
                }
                for e in retrieval["negative_evidence_candidates"]
            ],
        },
        "feedback": {
            "status": f["status"],
            "output_sha256": f["output_sha256"],
            "negative_evidence_applied": f["negative_evidence_applied"],
            "pruning_log": f["pruning_log"],
            "pruned_hypotheses": len(f["pruned_hypotheses"]),
            "chain_verified": payload["retrieval_feedback_rerun"]["pruning_convergence"][
                "chain_verified"
            ],
            "conversion": payload["retrieval_feedback_rerun"]["review_evidence"][
                "feedback_conversion"
            ],
            "applied_frame_keys": payload["retrieval_feedback_rerun"]["review_evidence"][
                "applied_frame_keys"
            ],
        },
        "restricted_policy_engine_status": payload["initial"]["review_evidence"][
            "restricted_policy_engine_status"
        ],
        "packager_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    summary["output_sha256"] = content_hash(summary)
    with args.receipt.open("x") as stream:
        json.dump(summary, stream, indent=2)
        stream.write("\n")
    print(json.dumps(summary["complete_artifact"]))


if __name__ == "__main__":
    main()

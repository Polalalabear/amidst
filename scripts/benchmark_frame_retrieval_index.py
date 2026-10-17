"""Synthetic 10^5/10^6 metadata scale test; no RGB, source or demo evidence."""

import argparse
import gc
import json
import statistics
import time
from pathlib import Path

from amidst.workbench.frame_retrieval import FrameRetrievalIndex


class SyntheticEvaluations:
    def get(self, ref, default=None):
        return {
            "frame_available": True,
            "rgb_hash_verified": True,
            "provenance_ok": True,
            "perception_evaluated": False,
            "measurement_count": None,
            "detection_producer": {"producer": "SYNTHETIC_METADATA_ONLY", "version": "v1"},
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    metrics = []
    for count in (100000, 1000000):
        started = time.perf_counter()
        records = [
            {
                "frame_ref": f"scale-frame:{i}",
                "camera_id": "SYNTHETIC_CAMERA",
                "timestamp_s": i * 0.2,
            }
            for i in range(count)
        ]
        entry = {
            "camera_id": "SYNTHETIC_CAMERA",
            "visibility_ref": "synthetic:frustum-only",
            "method": "FRUSTUM_ONLY",
            "floor_z_m": 0.0,
            "polygons": [],
        }
        index = FrameRetrievalIndex(
            records,
            SyntheticEvaluations(),
            [entry],
            index_sha256="0" * 64,
            provenance={"synthetic": True, "gt_read": False},
            interval_s=[4.6, 8.2],
        )
        build = time.perf_counter() - started
        times = []
        read_counts = []
        for _ in range(100):
            started = time.perf_counter()
            r = index.query(
                {
                    "query_kind": "TIME_RANGE",
                    "hypothesis": None,
                    "time_range_s": [4.8, 8.0],
                    "camera_ids": None,
                    "max_frames": 64,
                }
            )
            times.append((time.perf_counter() - started) * 1000)
            read_counts.append(r["stats"]["frame_records_read"])
            assert not r["negative_evidence_candidates"] and r["status"] == "READY"
        metrics.append(
            {
                "frame_records": count,
                "build_s": build,
                "queries": 100,
                "query_latency_ms": {
                    "p50": statistics.median(times),
                    "p95": sorted(times)[94],
                    "max": max(times),
                },
                "frame_records_read_range": [min(read_counts), max(read_counts)],
                "rgb_io": "NOT_MEASURED_METADATA_ONLY",
                "geometry_raycast": "NOT_RUN",
                "demo_input_eligible": False,
            }
        )
        del index, records
        gc.collect()
    result = {"fixture_kind": "SYNTHETIC_SCALE_NOT_DEMO_OR_NEGATIVE_EVIDENCE", "metrics": metrics}
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

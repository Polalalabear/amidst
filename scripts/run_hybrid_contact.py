"""Freeze C4a outputs before optional annotation-only diagnostic comparison.

No GT, renderer trajectory, visibility or depth is read. The optional coarse
annotation is read only AFTER predictions and hashes have been materialized;
it is not an input to the estimator or a source-derived clipping map.
"""

import argparse
import hashlib
import json
from pathlib import Path

from office_demo_backend import DEFAULT_CONFIG, load_scene
from shapely.geometry import LineString, MultiPoint, Point

from amidst.engineering.registry import content_hash


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostic-geometry", type=Path)
    parser.add_argument("--diagnostic-output", type=Path)
    args = parser.parse_args()
    if args.output.exists() or (args.diagnostic_output and args.diagnostic_output.exists()):
        raise FileExistsError("OUTPUT_EXISTS")
    if bool(args.diagnostic_geometry) != bool(args.diagnostic_output):
        raise ValueError("DIAGNOSTIC_REQUIRES_SEPARATE_OUTPUT")
    if args.output.resolve().is_relative_to(args.bundle.resolve()) or (
        args.diagnostic_output
        and args.diagnostic_output.resolve().is_relative_to(args.bundle.resolve())
    ):
        raise ValueError("OUTPUT_INSIDE_INPUT_BUNDLE")
    scene = load_scene(args.bundle, json.loads(args.fixture.read_text()))
    observations = [
        r
        for camera in sorted(scene.index._camera_ids)
        for r in scene.query(camera, 0, 9.8)["observations"]
    ]
    predictions = {
        "schema_version": "office-demo.hybrid-contact-predictions.v1",
        "run_id": scene.run_id,
        "source_sha256": scene.source_hash,
        "safe_inputs_sha256": sha(args.bundle / "safe_inputs.json"),
        "fixture_sha256": sha(args.fixture),
        "producer_sha256": sha(__file__),
        "estimator_sha256": sha(
            Path(__file__).resolve().parents[1] / "src/amidst/engineering/hybrid_contact.py"
        ),
        "dependencies_sha256": {
            name: sha(Path(__file__).resolve().parents[1] / name)
            for name in (
                "src/amidst/workbench/contact_scene.py",
                "src/amidst/engineering/perception_v2.py",
                "src/amidst/geometry/inverse_projection.py",
                "src/amidst/engineering/registry.py",
                "configs/hybrid_contact_v1.json",
            )
        },
        "gt_read": False,
        "geometry_clipping": "NOT_AVAILABLE_PENDING_C7",
        "observations": [r["ground_estimate"] for r in observations],
    }
    with args.output.open("x") as stream:
        json.dump(predictions, stream, indent=2, allow_nan=False)
        stream.write("\n")
    frozen_hash = sha(args.output)
    summary = {
        "observation_count": len(observations),
        "point_count": sum(r["ground_estimate"]["estimate_kind"] == "POINT" for r in observations),
        "segment_count": sum(
            r["ground_estimate"]["estimate_kind"] == "SEGMENT" for r in observations
        ),
    }
    if args.diagnostic_geometry:
        geometry = json.loads(args.diagnostic_geometry.read_text())
        if geometry["source_sha256"] != scene.source_hash:
            raise ValueError("DIAGNOSTIC_SOURCE_MISMATCH")
        obstacle = next(
            r for r in geometry["surfaces"] if r["surface_id"] == "OBSTACLE_1F_OFFICE_01"
        )
        scale = geometry["unit_scale_m"]
        polygon = MultiPoint(
            [(p[0] * scale, p[1] * scale) for p in obstacle["vertices"]]
        ).convex_hull
        records = []
        for row in observations:
            if row["observation_ref"] not in {
                "observation:add9f687d311742321e80dff",
                "observation:997166541f223b4f923d8bff",
            }:
                continue
            estimate = row["ground_estimate"]
            diag = estimate["diagnostics"]
            segment = None
            if diag.get("raw_near_m") is not None:
                segment = LineString([diag["raw_near_m"][:2], diag["raw_far_m"][:2]])
            records.append(
                {
                    "observation_ref": row["observation_ref"],
                    "timestamp_s": row["timestamp"],
                    "camera_id": row["camera_id"],
                    "status": estimate["status"],
                    "estimate_kind": estimate["estimate_kind"],
                    "reason": estimate["reason"],
                    "raw_interval_length_m": diag["raw_interval_length_m"],
                    "segment_too_long": estimate["reason"] == "SEGMENT_TOO_LONG",
                    "legacy_v1_point_in_annotation": polygon.covers(
                        Point(row["world_position"][:2])
                    ),
                    "raw_interval_intersection_annotation_length_m": None
                    if segment is None
                    else segment.intersection(polygon).length,
                }
            )
        receipt = {
            "schema_version": "office-demo.c4a-endpoint-diagnostic.v1",
            "authority": "DIAGNOSTIC_ONLY_NOT_ESTIMATOR_INPUT",
            "predictions_sha256": frozen_hash,
            "geometry_sha256": sha(args.diagnostic_geometry),
            "annotation_id": obstacle["surface_id"],
            "annotation_xy_bounds_m": list(polygon.bounds),
            "source_sha256": scene.source_hash,
            "producer_sha256": sha(__file__),
            "gt_read": False,
            "annotation_loaded_after_prediction_freeze": True,
            "endpoints": records,
            "summary": summary,
        }
        receipt["output_sha256"] = content_hash(receipt)
        with args.diagnostic_output.open("x") as stream:
            json.dump(receipt, stream, indent=2, allow_nan=False)
            stream.write("\n")
        if sha(args.output) != frozen_hash:
            raise RuntimeError("FROZEN_PREDICTIONS_CHANGED")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

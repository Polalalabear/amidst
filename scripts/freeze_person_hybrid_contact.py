"""Freeze C4a outputs from pinned RGB/calibration only; no GT or C7 clips.

Fixture and contact config may be explicitly exported from the deferred C6
branch. Reading them here does not register a preset or move C6 code/assets.
"""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from amidst.engineering.hybrid_contact import k1_endpoint_eligibility
from amidst.engineering.perception_v2 import ContactConfig
from amidst.engineering.registry import content_hash
from amidst.workbench.blender_scene import ValidationRunPin
from amidst.workbench.contact_scene import ContactQualityScene


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frame_table(scene, estimates):
    """Include empty frame slots without inventing C4a observations for them."""
    rows = []
    observations = {r["observation_ref"]: r for r in scene.index.observations}
    by_frame = {}
    for observation in observations.values():
        by_frame.setdefault(observation["frame_ref"], []).append(observation)
    for frame in sorted(scene.index.frame_records, key=lambda f: (f["timestamp"], f["camera_id"])):
        found = by_frame.get(frame["frame_ref"], [])
        for observation in found or [None]:
            estimate = None if observation is None else estimates[observation["observation_ref"]]
            bbox = None if observation is None else observation.get("bbox_xyxy")
            head = None if bbox is None else [(bbox[0] + bbox[2] - 1) / 2, bbox[1]]
            length = None if estimate is None else (estimate.get("segment") or {}).get("length_m")
            rows.append(
                {
                    "timestamp_s": frame["timestamp"],
                    "camera": frame["camera_id"],
                    "frame_ref": frame["frame_ref"],
                    "observation_ref": None
                    if observation is None
                    else observation["observation_ref"],
                    "status": "NO_OBSERVATION"
                    if estimate is None
                    else (
                        estimate["estimate_kind"] if estimate["status"] == "READY" else "UNKNOWN"
                    ),
                    "estimator_status": None if estimate is None else estimate["status"],
                    "interval_length_m": length,
                    "reasons": ["NO_RGB_COMPONENT"]
                    if estimate is None
                    else ([] if estimate["reason"] is None else [estimate["reason"]]),
                    "contact_quality_reasons": None
                    if estimate is None
                    else estimate["contact_quality"]["reasons"],
                    "head_anchor_px": head,
                    "head_anchor_used": estimate is not None
                    and estimate["diagnostics"]["raw_interval_length_m"] is not None,
                    "k1_endpoint": {"eligible": False, "reasons": ["NO_OBSERVATION"]}
                    if estimate is None
                    else k1_endpoint_eligibility(estimate),
                }
            )
    return rows


def summary(estimates, rows, cameras, floor_z):
    values = list(estimates.values())
    lengths = [g["segment"]["length_m"] for g in values if g["estimate_kind"] == "SEGMENT"]
    by_camera = {}
    for camera in cameras:
        origin = [camera["calibration"]["camera_to_world"][a][3] for a in range(3)]
        records = []
        for g in values:
            if g["camera_id"] != camera["camera_id"] or g["timestamp_s"] != 8.6:
                continue
            segment = g.get("segment")
            distances = (
                None
                if segment is None
                else [math.dist(origin[:2], segment[k][:2]) for k in ("near_m", "far_m")]
            )
            records.append(
                {
                    "observation_ref": g["observation_ref"],
                    "head_anchor_px": g["image_anchor_px"],
                    "horizontal_distance_to_height_interval_m": distances,
                    "horizontal_distance_at_declared_nominal_height_m": None
                    if distances is None
                    else sum(distances) / 2,
                    "distance_basis": "CALIBRATED_HEAD_RAY_PLUS_DECLARED_HEIGHT_NOT_GT",
                    "unique_actual_target_distance_m": "UNKNOWN_NO_GT_USED",
                }
            )
        by_camera[camera["camera_id"]] = {
            "origin_m": origin,
            "height_above_floor_m": origin[2] - floor_z,
            "timestamp_8_6_calibrated_interval": records,
        }
    return {
        "observation_count": len(values),
        "counts": {
            kind: sum(
                (g["estimate_kind"] if g["status"] == "READY" else "UNKNOWN") == kind
                for g in values
            )
            for kind in ("POINT", "SEGMENT", "UNKNOWN")
        },
        "unknown_reasons": dict(Counter(g["reason"] for g in values if g["status"] == "UNKNOWN")),
        "contact_quality_reasons": dict(
            Counter(reason for g in values for reason in g["contact_quality"]["reasons"])
        ),
        "interval_length_range_m": [min(lengths), max(lengths)] if lengths else None,
        "k1_eligible_count": sum(k1_endpoint_eligibility(g)["eligible"] for g in values),
        "k1_withheld_reasons": dict(
            Counter(reason for g in values for reason in k1_endpoint_eligibility(g)["reasons"])
        ),
        "frame_table_rows": len(rows),
        "empty_frame_slots": sum(r["observation_ref"] is None for r in rows),
        "camera_geometry": by_camera,
        "focus_rows": [
            r
            for r in rows
            if (r["camera"].endswith("FRONT") and 3.4 <= r["timestamp_s"] <= 4.4)
            or (r["camera"].endswith("REAR") and 8.6 <= r["timestamp_s"] <= 9.6)
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in (
        "bundle",
        "fixture",
        "contact-config",
        "hybrid-config",
        "output",
        "summary",
        "table",
    ):
        parser.add_argument("--" + key, required=True, type=Path)
    args = parser.parse_args()
    outputs = [args.output, args.summary, args.table]
    if len({p.resolve() for p in outputs}) != 3 or any(p.exists() for p in outputs):
        raise FileExistsError("OUTPUT_EXISTS_OR_ALIASED")
    if any(p.resolve().is_relative_to(args.bundle.resolve()) for p in outputs):
        raise ValueError("OUTPUT_INSIDE_INPUT_BUNDLE")
    fixture = json.loads(args.fixture.read_text())
    hybrid = json.loads(args.hybrid_config.read_text())
    contact = ContactConfig.model_validate_json(args.contact_config.read_text())
    if sha(args.contact_config) != fixture["contact_config_sha256"]:
        raise ValueError("CONTACT_CONFIG_HASH_MISMATCH")
    pin = ValidationRunPin(**fixture["validation_pin"])
    scene = ContactQualityScene(
        args.bundle,
        validation_pin=pin,
        contact_config=contact,
        perception_version=contact.version,
        hybrid_config=hybrid,
        hybrid_config_sha256=sha(args.hybrid_config),
    )
    if scene.run_id != fixture["run_id"] or scene.source_hash != fixture["source_sha256"]:
        raise ValueError("FIXTURE_SOURCE_OR_RUN_MISMATCH")
    if sha(args.bundle / "safe_inputs.json") != fixture["safe_inputs_sha256"]:
        raise ValueError("FIXTURE_SAFE_INPUTS_MISMATCH")
    estimates = scene._ground_estimates
    rows = frame_table(scene, estimates)
    payload = {
        "schema_version": "office-demo.person-hybrid-predictions.v1",
        "run_id": scene.run_id,
        "clock_id": scene._inputs["source_binding"]["clock_id"],
        "sampling_hz": fixture["sampling_hz"],
        "source_sha256": scene.source_hash,
        "safe_inputs_sha256": sha(args.bundle / "safe_inputs.json"),
        "fixture_sha256": sha(args.fixture),
        "contact_config_sha256": sha(args.contact_config),
        "hybrid_config_sha256": sha(args.hybrid_config),
        "producer_sha256": sha(__file__),
        "dependencies_sha256": {
            p: sha(p)
            for p in (
                "src/amidst/engineering/hybrid_contact.py",
                "src/amidst/workbench/contact_scene.py",
                "src/amidst/engineering/perception_v2.py",
                "src/amidst/geometry/inverse_projection.py",
                "src/amidst/engineering/registry.py",
                "src/amidst/workbench/blender_scene.py",
            )
        },
        "gt_read": False,
        "geometry_clipping": "NOT_AVAILABLE_NOT_APPLIED",
        "r1_status": "PENDING_COORDINATOR_DECISION_LOW_INCIDENCE_ONLY_NOT_K1_ENDPOINTS",
        "original_observation_states": dict(Counter(r["state"] for r in scene.index.observations)),
        "original_observation_null_positions": sum(
            r["world_position"] is None for r in scene.index.observations
        ),
        "observations": sorted(
            estimates.values(),
            key=lambda g: (g["timestamp_s"], g["camera_id"], g["observation_ref"]),
        ),
        "endpoint_eligibility": {
            ref: k1_endpoint_eligibility(g) for ref, g in sorted(estimates.items())
        },
    }
    payload["output_sha256"] = content_hash(payload)
    with args.output.open("x") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
    frozen_sha = sha(args.output)
    # Summary and table consume only the already frozen estimates and calibration.
    result = summary(
        estimates, rows, scene._inputs["cameras"], scene._inputs["floor_plane"]["point"][2]
    )
    result.update(predictions_sha256=frozen_sha, gt_read=False, producer_sha256=sha(__file__))
    result["output_sha256"] = content_hash(result)
    with args.summary.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    table = {"predictions_sha256": frozen_sha, "rows": rows, "gt_read": False}
    table["output_sha256"] = content_hash(table)
    with args.table.open("x") as stream:
        json.dump(table, stream, indent=2, allow_nan=False)
        stream.write("\n")
    if sha(args.output) != frozen_sha:
        raise RuntimeError("FROZEN_PREDICTIONS_CHANGED")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "observation_count",
                    "counts",
                    "unknown_reasons",
                    "interval_length_range_m",
                    "k1_eligible_count",
                    "k1_withheld_reasons",
                )
            }
        )
    )


if __name__ == "__main__":
    main()

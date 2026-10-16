#!/usr/bin/env python3
"""Versioned RGB regression or post-hoc evaluation; outputs are exclusive-create."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from amidst.engineering.perception_v2 import ContactConfig, produce_contact_v2
from amidst.workbench.frame_baseline import BaselineFrameIndex


def predict(inputs, config):
    old = BaselineFrameIndex(inputs)
    before = old.snapshot()
    result = produce_contact_v2(inputs, config)
    original = old.observations
    for frame in result["frames"]:
        frame["old_components"] = [r for r in original if r["frame_ref"] == frame["frame_ref"]]
    result["old_baseline_unchanged"] = old.snapshot() == before
    result["old_observation_count"] = len(original)
    result["old_projected_count"] = sum(r["world_position"] is not None for r in original)
    result["speed_transitions"] = speed_transitions(result["frames"], config.max_speed_m_s)
    return result


def speed_transitions(frames, cap):
    transitions = []
    for camera_id in sorted({r["camera_id"] for r in frames}):
        camera_rows = [r for r in frames if r["camera_id"] == camera_id]
        for a, b in zip(camera_rows, camera_rows[1:]):
            dt = b["timestamp"] - a["timestamp"]
            old = []
            for x in a["old_components"]:
                for y in b["old_components"]:
                    if x["track_ref"] == y["track_ref"] and x["world_position"] and y["world_position"]:
                        speed = math.dist(x["world_position"], y["world_position"]) / dt
                        old.append({"speed_m_s": speed, "exceeds_cap": speed > cap})
            av = [r for r in a["components"] if r["world_position"] is not None]
            bv = [r for r in b["components"] if r["world_position"] is not None]
            # No inferred identity association across multiple components or missing frames.
            speed = math.dist(av[0]["world_position"], bv[0]["world_position"]) / dt if len(av) == len(bv) == 1 else None
            transitions.append({"camera_id": camera_id, "from_frame_ref": a["frame_ref"],
                                "from_timestamp": a["timestamp"], "to_timestamp": b["timestamp"],
                                "old": old, "new_speed_m_s": speed,
                                "new_status": "SPEED_CAP" if speed is not None and speed > cap else
                                              "SUPPORTED_PAIR" if speed is not None else "MISSING_OR_AMBIGUOUS",
                                "new_rejection_reasons": sorted({r for f in (a,b) for c in f["components"] for r in c["reasons"]})})
    return transitions


def evaluate(prediction, dataset, plan):
    """Evaluation only: never called from the RGB producer."""
    scale = 0.0247
    if dataset["source_scene"]["sha256_before"] != prediction["source_binding"]["source_sha256"]:
        raise ValueError("EVALUATION_SOURCE_MISMATCH")
    if not plan.get("contact_visibility_policy") or len(dataset["timestamps"]) != 50:
        raise ValueError("EVALUATION_REQUIRES_COMPLETE_CONTACT_CONTROL")
    points = {(r["camera_id"], r["timestamp"]): r for r in prediction["frames"]}
    series = []
    for frame, planned in zip(dataset["timestamps"], plan["samples"], strict=True):
        if frame["timestamp"] != planned["timestamp"] or math.dist(frame["ground_truth"]["foot_position"], planned["foot_position"]) > 1e-6:
            raise ValueError("EVALUATION_PLAN_MISMATCH")
        truth = [v * scale for v in planned["foot_position"]]
        for visibility in planned["camera_visibility"]:
            camera_id = visibility["camera_id"]
            prediction_frame = points[camera_id, frame["timestamp"]]
            errors = {}
            for label, rows in (("v1", prediction_frame["old_components"]), ("v2", prediction_frame["components"])):
                errors[label] = [math.dist(r["world_position"], truth) if r["world_position"] is not None else None for r in rows]
            series.append({"frame_id": frame["index"], "timestamp": frame["timestamp"], "camera_id": camera_id,
                           "middle_visible": visibility["status"] == "visible", "bottom_visible": visibility["bottom_status"] == "visible",
                           "bottom_incidence": visibility["bottom_incidence"], "errors_m": errors,
                           "v2_reasons": [c["reasons"] for c in prediction_frame["components"]]})
    summaries = {}
    for version in ("v1", "v2"):
        errors = [e for row in series for e in row["errors_m"][version] if e is not None]
        summaries[version] = {"projected_count": len(errors), "mean_m": sum(errors)/len(errors) if errors else None,
                              "max_m": max(errors) if errors else None}
    paired = [r for r in series if len(r["errors_m"]["v1"]) == len(r["errors_m"]["v2"]) == 1
              and r["errors_m"]["v1"][0] is not None and r["errors_m"]["v2"][0] is not None]
    paired_summary = {}
    for version in ("v1", "v2"):
        values = [r["errors_m"][version][0] for r in paired]
        paired_summary[version] = {"count": len(values), "mean_m": sum(values)/len(values) if values else None,
                                   "max_m": max(values) if values else None}
    bottom = {(r["camera_id"],r["timestamp"]):r["bottom_visible"] for r in series}
    jumps = [r for r in prediction["speed_transitions"] if r["new_status"] == "SPEED_CAP" and
             bottom[r["camera_id"], r["from_timestamp"]] and bottom[r["camera_id"], r["to_timestamp"]]]
    return {"scope": "POSTHOC_EVALUATION_ONLY", "summary": summaries,
            "paired_same_frames": paired_summary,
            "comparison_note": "ALL_PROJECTION_SUMMARIES_HAVE_DIFFERENT_COVERAGE_USE_PAIRED_FOR_ACCURACY_COMPARISON",
            "time_series": series,
            "bottom_visible_speed_cap_transitions": jumps,
            "acceptance": "PASS" if not jumps and summaries["v2"]["projected_count"] else "FAIL_OR_NO_VALID_PROJECTIONS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    predict_parser = sub.add_parser("predict")
    predict_parser.add_argument("--safe-inputs", type=Path, required=True)
    predict_parser.add_argument("--config", type=Path, required=True)
    evaluation_parser = sub.add_parser("evaluate")
    evaluation_parser.add_argument("--predictions", type=Path, required=True)
    evaluation_parser.add_argument("--dataset", type=Path, required=True)
    evaluation_parser.add_argument("--plan", type=Path, required=True)
    for command in (predict_parser, evaluation_parser):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.command == "predict":
        raw = args.safe_inputs.read_bytes()
        result = predict(json.loads(raw), ContactConfig.model_validate_json(args.config.read_bytes()))
        result["safe_inputs_sha256"] = hashlib.sha256(raw).hexdigest()
        result["config_sha256"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
    else:
        raw = args.dataset.read_bytes()
        prediction = json.loads(args.predictions.read_bytes())
        if hashlib.sha256(raw).hexdigest() != prediction["source_binding"]["dataset_sha256"]:
            raise ValueError("EVALUATION_DATASET_HASH_MISMATCH")
        result = evaluate(prediction, json.loads(raw), json.loads(args.plan.read_bytes()))
        result["prediction_sha256"] = hashlib.sha256(args.predictions.read_bytes()).hexdigest()
        result["plan_sha256"] = hashlib.sha256(args.plan.read_bytes()).hexdigest()
        result["evaluator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        result["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()

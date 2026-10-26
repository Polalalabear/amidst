"""Read-only, offline evidence extraction for the frozen engineering A/B gap.

This does not estimate visibility, identity, trajectories, or correctness.
Only the explicitly pinned safe inputs below are opened; RGB is hash-checked.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

ROOT = "run/baseline/worker-3/sample-0/q5/"
REC = ROOT + "recorded/"
FILES = {
    "rgb": "dynamic-rgb-v2/safe/rgb.json",
    "static": "dynamic-rgb-v2/safe/static.json",
    "index": "run/prepared/index/detection_index.json",
    "records": "run/prepared/index/detection_index.records.jsonl",
    "response": ROOT + "response.json",
    "parameters": REC + "parameter_set.json",
    "camera_graph": REC + "camera_graph.json",
    "region_graph": REC + "region_graph.json",
    "links": REC + "sess-5418220d5a6886da.links.jsonl",
    "decisions": REC + "sess-5418220d5a6886da.decisions.jsonl",
    "switch_evidence": REC + "6.evidence.json",
    "switch_snapshot": REC + "6.snapshot.json",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_pin(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f"SHA256_MISMATCH: {path.name}")
    return raw


def within(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("PATH_OUTSIDE_SAFE_ROOT")
    return path


def extract(bundle: Path, pins: dict) -> tuple[dict, list[dict]]:
    if set(pins["files"]) != set(FILES.values()):
        raise ValueError("UNEXPECTED_INPUT_SET")
    raw = {key: read_pin(within(bundle, name), pins["files"][name]) for key, name in FILES.items()}
    obj = {
        key: (
            [json.loads(line) for line in value.splitlines()]
            if key in {"records", "links", "decisions"}
            else json.loads(value)
        )
        for key, value in raw.items()
    }
    rgb, static, index, response = (obj[k] for k in ("rgb", "static", "index", "response"))
    run, scene, clock = (pins[k] for k in ("run_id", "scene_id", "clock_id"))
    for value in [rgb, index]:
        if (value["run_id"], value["scene_id"], value["clock_id"]) != (run, scene, clock):
            raise ValueError("SOURCE_SCOPE_MISMATCH")
    if static["scene_id"] != scene or response["resolved_scope"]["run_ids"] != [run]:
        raise ValueError("RESPONSE_STATIC_SCOPE_MISMATCH")
    if (
        rgb["static_file_sha256"] != digest(raw["static"])
        or index["rgb_index_sha256"] != digest(raw["rgb"])
        or index["records_file_sha256"] != digest(raw["records"])
    ):
        raise ValueError("CROSS_PIN_MISMATCH")
    if index["detector"]["index_score_floor"] != 0.3:
        raise ValueError("INDEX_FLOOR_CHANGED")
    if response["decision_source"] != "RULE_ONLY" or response["identity_verdict"] != "UNCONFIRMED":
        raise ValueError("RESPONSE_MODE_CHANGED")
    params = {p["name"]: p["value"] for p in obj["parameters"]["parameters"]}
    if params["query_min_score"] != 0.5 or params["link_min_score"] != 0.4:
        raise ValueError("THRESHOLD_CHANGED")
    manifest = {}
    for frame in rgb["records"]:
        key = (frame["camera_id"], frame["frame_index"])
        if key in manifest:
            raise ValueError("DUPLICATE_RGB_FRAME")
        timestamp = Decimal(str(frame["timestamp_s"])) * 1_000_000
        if timestamp != key[1] * 50_000:
            raise ValueError("RGB_CLOCK_GRID_MISMATCH")
        read_pin(within(bundle / "dynamic-rgb-v2/safe", frame["rgb_ref"]), frame["file_sha256"])
        manifest[key] = frame
    expected = {(c, f) for c in ["A", "B"] for f in range(160)}
    if set(manifest) != expected:
        raise ValueError("INCOMPLETE_RGB_GRID")
    indexed = {}
    for record in obj["records"]:
        key = (record["camera_id"], record["frame_index"])
        if key in indexed:
            raise ValueError("DUPLICATE_INDEX_FRAME")
        if key not in manifest or record["timestamp_us"] != key[1] * 50_000:
            raise ValueError("INDEX_CLOCK_GRID_MISMATCH")
        if record["rgb_file_sha256"] != manifest[key]["file_sha256"]:
            raise ValueError("INDEX_RGB_PIN_MISMATCH")
        if record["frame_state"] != "INFERRED":
            raise ValueError("INDEX_NOT_INFERRED")
        indexed[key] = record
    if set(indexed) != expected:
        raise ValueError("INCOMPLETE_INDEX_GRID")
    timeline = response["timeline"]
    cursor = 0
    for segment in timeline:
        start, end = segment["range_us"]
        if start != cursor or end <= start or start % 50_000 or end % 50_000:
            raise ValueError("TIMELINE_GRID_OR_COVERAGE_MISMATCH")
        cursor = end
    if cursor != 8_000_000:
        raise ValueError("TIMELINE_COVERAGE_INCOMPLETE")
    rows, person_detections = [], []
    for (cam, frame), record in sorted(indexed.items()):
        t = record["timestamp_us"]
        segment = next(s for s in timeline if s["range_us"][0] <= t < s["range_us"][1])
        people = [d for d in record["detections"] if d["class_label"] == "person"]
        for det in people:
            if not 0.3 <= det["score"] <= 1:
                raise ValueError("INVALID_STORED_PERSON_SCORE")
            person_detections.append(
                {
                    "camera_id": cam,
                    "frame_index": frame,
                    "timestamp_us": t,
                    **{k: det[k] for k in ["observation_id", "score", "bbox_xyxy_px"]},
                }
            )
        supported = set(segment.get("observation_ids", []))
        rows.append(
            {
                "camera_id": cam,
                "frame_index": frame,
                "timestamp_us": t,
                "frame_ref": record["frame_ref"],
                "rgb_sha256": record["rgb_file_sha256"],
                "rgb_ref": manifest[cam, frame]["rgb_ref"],
                "frame_state": record["frame_state"],
                "person_count_ge_0_3": len(people),
                "person_count_ge_0_4": sum(d["score"] >= 0.4 for d in people),
                "person_count_ge_0_5": sum(d["score"] >= 0.5 for d in people),
                "best_person_score": max((d["score"] for d in people), default=None),
                "controller_kind": segment["kind"],
                "camera_shown": segment.get("camera_id", segment.get("camera_shown")),
                "supported_observations": sum(d["observation_id"] in supported for d in people),
                "visual_presence": "UNREVIEWED",
            }
        )
    a = [x for x in rows if x["camera_id"] == "A" and x["person_count_ge_0_3"]]
    b = [x for x in rows if x["camera_id"] == "B" and x["person_count_ge_0_3"]]
    last_a, first_b = a[-1], b[0]
    no_person_grid = sorted(
        {
            x["timestamp_us"]
            for x in rows
            if last_a["timestamp_us"] < x["timestamp_us"] < first_b["timestamp_us"]
        }
    )
    no_person_set = set(no_person_grid)
    if any(x["person_count_ge_0_3"] for x in rows if x["timestamp_us"] in no_person_set):
        raise ValueError("NOT_A_BOTH_CAMERA_DETECTION_GAP")
    before, after = last_a["timestamp_us"], first_b["timestamp_us"]
    switch = [d for d in obj["decisions"] if d["executed_action"] == "SWITCH"]
    report = {
        "schema_version": "q-demo.ab-gap-review.v1",
        "scene_id": scene,
        "run_id": run,
        "clock_id": clock,
        "source_pins": pins["files"],
        "source_blend_sha256": static["source_blend_file_sha256"],
        "review_range_us": [2_750_000, 5_250_000],
        "sampling": {
            "frame_interval_us": 50_000,
            "fps": 20,
            "rgb_verified": len(rows),
            "index_inferred": len(indexed),
            "missing_rgb": 0,
        },
        "detector": index["detector"],
        "parameters": params,
        "camera_calibration": static["cameras"],
        "image_size_px": static["image_size_px"],
        "detection_gap": {
            "last_a_stored_person": last_a,
            "first_b_stored_person": first_b,
            "between_detection_timestamps_us": after - before,
            "zero_stored_person_sample_interval_us": [before + 50_000, after],
            "time_samples": len(no_person_grid),
            "camera_frames": len(no_person_grid) * 2,
            "meaning": "No stored person >=0.3 in either camera; not proof of visual absence.",
        },
        "controller_timeline": timeline,
        "decisions_through_switch": [d for d in obj["decisions"] if d["source_time_us"] <= after],
        "links_through_a_loss": [r for r in obj["links"] if r["camera_id"] == "A"],
        "switch": switch,
        "switch_evidence": obj["switch_evidence"],
        "switch_snapshot": obj["switch_snapshot"],
        "graph_caveat": {
            "camera_graph": obj["camera_graph"],
            "region_graph": obj["region_graph"],
            "authority": "SYNTHETIC_ENGINEERING_ONLY; full-image exit ROI; no physical approval",
        },
        "person_detections": person_detections,
        "visual_blind_interval_us": None,
        "physical_blind_interval_us": None,
        "identity_verdict": "UNCONFIRMED",
        "correctness": None,
        "gt_or_private_motion_read": False,
        "new_model_calls": 0,
        "new_renders": 0,
    }
    return report, rows


def csv_bytes(rows: list[dict]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--pins-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pins = json.loads(read_pin(args.pins, args.pins_sha256))
    if args.output.exists() or args.output.resolve().is_relative_to(args.bundle.resolve()):
        raise ValueError("OUTPUT_MUST_BE_NEW_AND_OUTSIDE_SOURCE_BUNDLE")
    report, rows = extract(args.bundle, pins)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (args.output / "frames.csv").write_bytes(csv_bytes(rows))
    print(json.dumps({"rgb_verified": len(rows), "detection_gap": report["detection_gap"]}))


if __name__ == "__main__":
    main()

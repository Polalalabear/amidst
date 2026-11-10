"""Produce a hash-bound diagnostic for explicitly selected person observations.

This is not a local linker or a target tracker. It does not infer associations,
interpolate gaps, generate cross-camera handoffs or authorize physical navigation.
Missing approved parameters, selection, or source binding yields UNKNOWN with no
segments. A valid diagnostic contains only the selected source sample intervals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

from amidst.paths import artifacts_output_root

MIN_FREE_BYTES = 8 * 1024 ** 3
SCHEMA = "cx8-rule-tracking.v1"
BINDING_FIELDS = ("scene_id", "run_id", "clock_id", "rgb_index_sha256")


def require_free_space(path, minimum=MIN_FREE_BYTES):
    free = shutil.disk_usage(path).free
    if free < minimum:
        raise SystemExit(f"Insufficient disk space (D118): {free} bytes free, need {minimum}")
    return free


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def content_hash(value, exclude=()):
    body = {k: v for k, v in value.items() if k not in exclude}
    return digest(json.dumps(body, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode())


def is_sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def build_receipt(records_bytes, *, manifest_bytes=None, manifest_sha256=None,
                  expected_binding=None, selected_target=None, parameter_set=None):
    """Validate provenance before emitting explicit observations, never handoffs."""
    receipt = {
        "schema": SCHEMA, "mode": "RULE_ONLY", "status": "UNKNOWN",
        "scope": "SELECTED_OBSERVATIONS_DIAGNOSTIC", "identity": "UNCONFIRMED",
        "physical_navigation": "UNKNOWN", "cross_camera_association": "NOT_EVALUATED",
        "binding": None, "selected_target_ref": None, "parameters_sha256": None,
        "source_records_sha256": digest(records_bytes), "segments": [], "switches": [],
    }

    def unknown(reason):
        return {**receipt, "reason": reason}

    if not manifest_bytes or not is_sha256(manifest_sha256) or not expected_binding:
        return unknown("SOURCE_BINDING_REQUIRED")
    if digest(manifest_bytes) != manifest_sha256:
        return unknown("MANIFEST_HASH_MISMATCH")
    try:
        manifest = json.loads(manifest_bytes)
        if (manifest.get("schema_version") != "q-demo.detection-index.v1"
                or manifest.get("provenance", {}).get("gt_read") is not False
                or manifest.get("content_sha256") != content_hash(manifest, ("index_id", "content_sha256"))
                or not all(isinstance(manifest.get(k), str) and manifest[k] for k in BINDING_FIELDS)
                or not is_sha256(manifest["rgb_index_sha256"])
                or any(manifest[k] != expected_binding.get(k) for k in BINDING_FIELDS)):
            return unknown("SOURCE_BINDING_MISMATCH")
        records_sha = receipt["source_records_sha256"]
        if manifest.get("records_file_sha256") != records_sha:
            return unknown("RECORDS_HASH_MISMATCH")
        if (not isinstance(parameter_set, dict)
                or parameter_set.get("approval", {}).get("status") != "APPROVED"
                or parameter_set.get("content_sha256") != content_hash(
                    parameter_set, ("content_sha256", "parameter_set_id"))):
            return unknown("PARAMETERS_NOT_APPROVED")
        params = {p["name"]: p["value"] for p in parameter_set.get("parameters", [])
                  if p.get("status") == "APPROVED"}
        floor = params.get("query_min_score")
        index_floor = manifest.get("detector", {}).get("index_score_floor")
        if (type(floor) not in (int, float) or not math.isfinite(floor) or not 0 <= floor <= 1
                or type(index_floor) not in (int, float) or not math.isfinite(index_floor)
                or floor < index_floor):
            return unknown("PARAMETERS_NOT_APPROVED")
        if (not isinstance(selected_target, dict)
                or selected_target.get("class_label") != "person"
                or selected_target.get("source_records_sha256") != records_sha
                or not isinstance(selected_target.get("selection_ref"), str)
                or not selected_target["selection_ref"]):
            return unknown("SELECTED_TARGET_REQUIRED")
        selected_ids = selected_target.get("observation_ids")
        if (not isinstance(selected_ids, list) or not selected_ids
                or any(not isinstance(x, str) or not x for x in selected_ids)
                or len(selected_ids) != len(set(selected_ids))):
            return unknown("SELECTED_TARGET_REQUIRED")
        cameras = {p["camera_id"]: p for p in manifest["sampling"]["per_camera"]}
        rows = [json.loads(line) for line in records_bytes.splitlines() if line.strip()]
        observations, seen_frames, seen_observations = {}, set(), set()
        allowed_row_fields = {"frame_ref", "camera_id", "frame_index", "timestamp_us",
                              "rgb_file_sha256", "frame_state", "state_reason", "detections"}
        for row in rows:
            if not isinstance(row, dict) or set(row) - allowed_row_fields:
                return unknown("INVALID_SOURCE_RECORDS")
            camera, index, ts = row.get("camera_id"), row.get("frame_index"), row.get("timestamp_us")
            if camera not in cameras or type(index) is not int or index < 0 or type(ts) is not int or ts < 0:
                return unknown("INVALID_SOURCE_RECORDS")
            sampling = cameras[camera]
            interval = sampling["source_frame_interval_us"]
            ref = f"frame:{manifest['run_id']}:{camera}:{index}"
            if (type(interval) is not int or interval <= 0 or ts != index * interval
                    or row.get("frame_ref") != ref or ref in seen_frames
                    or not any(a <= ts and ts + interval <= b for a, b in sampling["sampled_ranges_us"])):
                return unknown("SOURCE_BINDING_MISMATCH")
            seen_frames.add(ref)
            state, detections = row.get("frame_state"), row.get("detections")
            if state not in {"INFERRED", "MISSING", "NOT_SAMPLED", "NOT_INFERRED"}:
                return unknown("INVALID_SOURCE_RECORDS")
            if state != "INFERRED":
                if detections not in (None, []):
                    return unknown("INVALID_SOURCE_RECORDS")
                continue
            if not isinstance(detections, list) or not is_sha256(row.get("rgb_file_sha256")):
                return unknown("INVALID_SOURCE_RECORDS")
            for detection in detections:
                oid, score = detection.get("observation_id"), detection.get("score")
                if (not isinstance(oid, str) or not oid or oid in seen_observations
                        or type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
                    return unknown("INVALID_SOURCE_RECORDS")
                seen_observations.add(oid)
                if oid in selected_ids and detection.get("class_label") == "person" and score >= floor:
                    observations[oid] = {"camera_id": camera, "start_us": ts, "end_us": ts + interval,
                                         "evidence_state": "OBSERVED", "frame_ref": ref,
                                         "observation_id": oid}
        if set(observations) != set(selected_ids):
            return unknown("SELECTED_OBSERVATIONS_UNAVAILABLE")
        segments = sorted(observations.values(), key=lambda s: (s["start_us"], s["camera_id"], s["observation_id"]))
        for i, segment in enumerate(segments):
            segment["segment_id"] = f"selected:{manifest['run_id']}:{i}"
        return {**receipt, "status": "AVAILABLE", "reason": None,
                "binding": {**{k: manifest[k] for k in BINDING_FIELDS}, "manifest_sha256": manifest_sha256},
                "selected_target_ref": selected_target["selection_ref"],
                "parameters_sha256": parameter_set["content_sha256"], "segments": segments}
    except (KeyError, TypeError, ValueError, AttributeError):
        return unknown("INVALID_SOURCE_RECORDS")


def read_pinned(path, pin):
    path = Path(path).absolute()
    if any(part.lower() == "gt_private" for part in path.parts):
        raise ValueError("Private evidence is not a diagnostic input")
    if path.resolve() != path or not path.is_file():
        raise ValueError("Pinned input must be a canonical regular file")
    raw = path.read_bytes()
    if not is_sha256(pin) or digest(raw) != pin:
        raise ValueError("Pinned input hash mismatch")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "records", "manifest", "manifest-sha256", "run-id", "scene-id",
                 "clock-id", "rgb-index-sha256", "output"):
        parser.add_argument("--" + name, required=True)
    for name in ("selection", "selection-sha256", "parameters", "parameters-sha256"):
        parser.add_argument("--" + name)
    args = parser.parse_args(argv)
    repo, output = Path(args.repo).resolve(), Path(args.output).absolute()
    allowed = artifacts_output_root()
    if output.resolve() != output or not output.is_relative_to(allowed) or output.is_relative_to(repo):
        parser.error("Output must be canonical and under the artifacts output root (AMIDST_ARTIFACTS, default local/evidence), outside repo")
    if output.exists():
        parser.error("Output exists; refusing to overwrite")
    try:
        manifest_raw = read_pinned(args.manifest, args.manifest_sha256)
        manifest = json.loads(manifest_raw)
        records_raw = read_pinned(args.records, manifest["records_file_sha256"])
        selection = json.loads(read_pinned(args.selection, args.selection_sha256)) if args.selection else None
        parameters = json.loads(read_pinned(args.parameters, args.parameters_sha256)) if args.parameters else None
        receipt = build_receipt(records_raw, manifest_bytes=manifest_raw, manifest_sha256=args.manifest_sha256,
                                expected_binding={"scene_id": args.scene_id, "run_id": args.run_id,
                                                  "clock_id": args.clock_id, "rgb_index_sha256": args.rgb_index_sha256},
                                selected_target=selection, parameter_set=parameters)
        require_free_space(output.parent if output.parent.exists() else repo)
        output.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(output, flags, 0o600), "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2, allow_nan=False)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": receipt["status"], "reason": receipt["reason"],
                      "segments": len(receipt["segments"]), "switches": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

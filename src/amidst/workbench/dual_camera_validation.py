"""Isolated RGB experiment inference. No renderer trajectory or evaluation input."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.engineering.perception import RGBFrame, produce_perception
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def load_inputs(path: Path) -> dict:
    value = json.loads(path.read_text())
    if value["schema_version"] != "dual-camera.rgb-inputs.v1":
        raise ValueError("EXPERIMENT_INPUT_SCHEMA")
    # Explicit input allowlist; renderer metadata cannot enter inference.
    keys = (
        "schema_version",
        "source_sha256",
        "scale_sha256",
        "metres_per_bu",
        "run_id",
        "clock_id",
        "camera_time_offsets_s",
        "calibration_version",
        "calibration_sha256",
        "cameras",
        "floor_plane",
        "frames",
    )
    value = {key: value[key] for key in keys}
    digest = hashlib.sha256(json.dumps(value["cameras"], sort_keys=True).encode()).hexdigest()
    if digest != value["calibration_sha256"]:
        raise ValueError("CALIBRATION_HASH_MISMATCH")
    seen = set()
    for frame in value["frames"]:
        identity = (frame["camera_id"], frame["timestamp"])
        if identity in seen:
            raise ValueError("DUPLICATE_CAMERA_TIME")
        seen.add(identity)
        relative = Path(frame["rgb_ref"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("RGB_PATH_DENIED")
        source = (path.parent / relative).resolve()
        if not source.is_relative_to(path.parent.resolve()):
            raise ValueError("RGB_PATH_DENIED")
        if file_sha(source) != frame["sha256"]:
            raise ValueError("RGB_HASH_MISMATCH")
    return value


def project_pixel(projector, pixel, timestamp=0):
    try:
        point = projector.project_frame(
            ObservationFrame(
                frame_id=0,
                timestamp=timestamp,
                target_id="rgb-component",
                camera_id=projector.camera.camera_id,
                status=VisibilityStatus.OBSERVED,
                point_2d=tuple(pixel),
                provenance=Provenance.OBSERVED,
            )
        )
        return list(point.world_position)
    except InverseProjectionError:
        return None


def baseline(inputs_path: Path, destination: Path) -> dict:
    inputs = load_inputs(inputs_path)
    frames = [
        RGBFrame(
            media_ref=f"{r['camera_id']}:{r['frame_index']}",
            camera_id=r["camera_id"],
            timestamp=r["timestamp"],
            path=inputs_path.parent / r["rgb_ref"],
            sha256=r["sha256"],
            width=r["width"],
            height=r["height"],
        )
        for r in inputs["frames"]
    ]
    pixels = produce_perception(frames, model_id="dual-camera-validation", run_id=inputs["run_id"])
    plane = Plane(plane_id="approved-source-floor", **inputs["floor_plane"])
    projectors = {
        r["camera_id"]: InverseProjectionService(Camera.model_validate(r["calibration"]), plane)
        for r in inputs["cameras"]
    }
    by_frame = defaultdict(list)
    for m in pixels.measurements:
        by_frame[m.frame_ref].append(
            {
                **m.model_dump(mode="json"),
                "world_position": project_pixel(
                    projectors[m.camera_id], m.contact_pixel, m.timestamp
                ),
            }
        )
    rows = [
        {**r, "observations": by_frame[f"{r['camera_id']}:{r['frame_index']}"]}
        for r in inputs["frames"]
    ]
    result = {
        "schema_version": "dual-camera.baseline.v1",
        "method": pixels.producer_version + "+existing-inverse-projection",
        "inputs_sha256": file_sha(inputs_path),
        "producer_sha256": pixels.producer_sha256,
        "frames": rows,
        "tracks": [t.model_dump(mode="json") for t in pixels.tracks],
        "statuses": [s.model_dump(mode="json") for s in pixels.frame_statuses],
    }
    write_new(destination, result)
    return result

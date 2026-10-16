#!/usr/bin/env python3
"""RGB-only contact QA PoC; never replaces canonical observations or identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.engineering.perception import _components
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService
from amidst.workbench.frame_baseline import BaselineFrameIndex

ANCHORS = (0.4, 0.6, 1.8, 2.0, 2.2, 4.4, 5.0, 8.6)


def components8(mask):
    """Diagnostic alternative; same >30 mask and >=28 pixels, diagonal adjacency added."""
    remaining = mask.copy()
    height, width = remaining.shape
    result = []
    for y, x in zip(*np.nonzero(mask), strict=True):
        y, x = int(y), int(x)
        if not remaining[y, x]:
            continue
        remaining[y, x] = False
        queue, pixels = deque([(y, x)]), []
        while queue:
            py, px = queue.popleft()
            pixels.append((py, px))
            for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
                ny, nx = py + dy, px + dx
                if 0 <= ny < height and 0 <= nx < width and remaining[ny, nx]:
                    remaining[ny, nx] = False
                    queue.append((ny, nx))
        if len(pixels) >= 28:
            coordinates = np.asarray(pixels, dtype=np.int64)
            ymin, xmin = coordinates.min(axis=0)
            ymax, xmax = coordinates.max(axis=0)
            result.append((int(xmin), int(ymin), int(xmax) + 1, int(ymax) + 1, coordinates))
    return sorted(result, key=lambda row: (row[0], row[1]))


def project(projector, contact):
    try:
        row = projector.project_frame(
            ObservationFrame(
                frame_id=0,
                timestamp=0,
                target_id="diagnostic-proxy",
                camera_id=projector.camera.camera_id,
                status=VisibilityStatus.OBSERVED,
                point_2d=contact,
                provenance=Provenance.OBSERVED,
            )
        )
        return list(row.world_position)
    except InverseProjectionError:
        return None


def contact_diagnostic(component, projector):
    xmin, ymin, xmax, ymax, coordinates = component
    contact = [(xmin + xmax - 1) / 2, float(ymax - 1)]
    bottom_x = coordinates[coordinates[:, 0] == ymax - 1, 1]
    raw = project(projector, contact)
    perturbations = []
    for du, dv in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        point = project(projector, (contact[0] + du, contact[1] + dv))
        perturbations.append(
            {
                "delta_pixel": [du, dv],
                "proxy_world_position": point,
                "distance_m": math.dist(raw, point) if raw and point else None,
            }
        )
    return {
        "bbox_xyxy": [xmin, ymin, xmax, ymax],
        "contact_pixel": contact,
        "pixel_count": len(coordinates),
        "bottom_support_x": bottom_x.tolist(),
        "bbox_contact_to_nearest_bottom_mask_pixel_px": float(np.min(abs(bottom_x - contact[0]))),
        "proxy_world_position": raw,
        "pixel_perturbations": perturbations,
        "visible_bottom_median_pixel": [float(np.median(bottom_x)), contact[1]],
        "visible_bottom_median_proxy_world_position": project(
            projector, (float(np.median(bottom_x)), contact[1])
        ),
        "visible_bottom_is_feet": False,
        "sensitivity_is_error_bound": False,
        "ground_contact": "UNKNOWN",
        "position_use": "WITHHOLD_AS_PERSON_GROUND_POSITION",
        "proposed_person_world_position": None,
        "reason": "VISIBLE_MASK_BOTTOM_IS_NOT_VERIFIED_GROUND_CONTACT",
    }


def diagnose(inputs, anchors=ANCHORS):
    """Only camera/RGB/floor fields are read; index enforces hashes and safe allowlist."""
    index = BaselineFrameIndex(inputs)
    baseline = index.snapshot()
    rows, samples = index.observations, []
    plane = Plane(
        plane_id="contact-qa-floor",
        point=inputs["floor_plane"]["point"],
        normal=inputs["floor_plane"]["normal"],
        floor_id="1F",
    )
    cameras = {
        row["camera_id"]: Camera.model_validate(row["calibration"]) for row in inputs["cameras"]
    }
    for camera_id, camera in sorted(cameras.items()):
        frames = sorted(
            (row for row in inputs["frames"] if row["camera_id"] == camera_id),
            key=lambda row: row["timestamp"],
        )
        images = []
        for frame in frames:
            payload = Path(frame["local_path"]).read_bytes()
            if hashlib.sha256(payload).hexdigest() != frame["sha256"]:
                raise ValueError("RGB_HASH_MISMATCH")
            with Image.open(frame["local_path"]) as image:
                images.append(np.asarray(image.convert("RGB")).copy())
        background = np.median(np.stack(images), axis=0).astype(np.int16)
        projector = InverseProjectionService(camera, plane)
        for frame, image in zip(frames, images, strict=True):
            if frame["timestamp"] not in anchors:
                continue
            difference = np.max(abs(image.astype(np.int16) - background), axis=2)
            original = [
                row
                for row in rows
                if row["camera_id"] == camera_id and row["timestamp"] == frame["timestamp"]
            ]
            four = _components(difference > 30)
            assert len(four) == len(original)
            diagnostics = [contact_diagnostic(row, projector) for row in four]
            for diagnostic, raw in zip(diagnostics, original, strict=True):
                assert diagnostic["contact_pixel"] == raw["contact_pixel"]
                if raw["world_position"] is not None:
                    assert (
                        math.dist(diagnostic["proxy_world_position"], raw["world_position"]) < 1e-9
                    )
            samples.append(
                {
                    "camera_id": camera_id,
                    "timestamp": frame["timestamp"],
                    "frame_ref": frame["frame_ref"],
                    "source_image_sha256": frame["sha256"],
                    "raw_observations": original,
                    "raw_contact_diagnostics": diagnostics,
                    "mask8_proxy_alternatives": [
                        contact_diagnostic(row, projector) for row in components8(difference > 30)
                    ],
                    "threshold_ge30_component_count": len(_components(difference >= 30)),
                    "quality": "NO_MEASUREMENT" if not original else "GROUND_POSITION_UNKNOWN",
                    "proposed_person_world_position": None,
                    "canonical_replacement": False,
                    "temporal_identity_link_created": False,
                }
            )
    jumps = []
    for camera in cameras:
        local = sorted(
            (row for row in rows if row["camera_id"] == camera),
            key=lambda row: (row["timestamp"], row["observation_ref"]),
        )
        for before, after in zip(local, local[1:], strict=False):
            if (before["timestamp"], after["timestamp"]) not in (
                (0.4, 0.6),
                (1.8, 2.0),
                (2.0, 2.2),
            ):
                continue
            if before["world_position"] is None or after["world_position"] is None:
                continue
            distance = math.dist(before["world_position"], after["world_position"])
            jumps.append(
                {
                    "camera_id": camera,
                    "from_s": before["timestamp"],
                    "to_s": after["timestamp"],
                    "distance_m": distance,
                    "apparent_speed_m_s": distance / (after["timestamp"] - before["timestamp"]),
                    "same_local_pixel_track": before["track_ref"] == after["track_ref"],
                    "confirmed_identity_continuity": False,
                    "proposed_person_distance_m": None,
                }
            )
    assert index.snapshot() == baseline
    return {
        "schema_version": "office-contact-qa-poc.v1",
        "authority": "DIAGNOSTIC_ONLY_NOT_CANONICAL",
        "gt_used": False,
        "canonical_observations_unchanged": True,
        "source_binding": baseline["source_binding"],
        "calibration_sha256": baseline["calibration_sha256"],
        "floor_plane": baseline["floor_plane"],
        "producer_sha256": baseline["producer_sha256"],
        "baseline_sha256": baseline["baseline_sha256"],
        "method_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "samples": samples,
        "raw_jumps": jumps,
        "accuracy_improvement": "UNKNOWN",
        "limitation": "Mask topology and pixel sensitivity do not reveal occluded feet; "
        "no ground truth error metric or certified feasible region is available.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safe-inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = json.loads(args.safe_inputs.read_bytes())
    report = diagnose(inputs)
    report["safe_inputs_sha256"] = hashlib.sha256(args.safe_inputs.read_bytes()).hexdigest()
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(f"CONTACT_QA={args.output} ACCURACY_IMPROVEMENT=UNKNOWN CANONICAL_UNCHANGED=YES")


if __name__ == "__main__":
    main()

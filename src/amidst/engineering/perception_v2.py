"""Versioned RGB contact measurements; no renderer or trajectory input.

Height consistency is a configured synthetic-target assumption, not proof of feet.
Rejected positions remain missing and this producer never interpolates them.
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService
from amidst.workbench.frame_baseline import _Inputs

VERSION = "rgb-mask-contact-v2"


class ContactConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["rgb-mask-contact-v2"] = VERSION
    difference_threshold: int = Field(default=30, ge=0, le=255)
    min_pixels: int = Field(default=28, ge=1)
    min_incidence: FiniteFloat = Field(default=0.25, gt=0, le=1)
    assumed_target_height_m: FiniteFloat = Field(gt=0)
    assumed_target_radius_m: FiniteFloat = Field(gt=0)
    height_tolerance_px: FiniteFloat = Field(default=3, ge=0)
    pixel_perturbation: FiniteFloat = Field(default=1, gt=0)
    max_speed_m_s: FiniteFloat = Field(default=8, gt=0)
    target_basis: str = "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT"


def components8(mask: np.ndarray, min_pixels: int = 28) -> list[np.ndarray]:
    """Diagonal adjacency can merge touching objects; no identity is asserted."""
    remaining = np.asarray(mask, dtype=bool).copy()
    height, width = remaining.shape
    result = []
    for y, x in zip(*np.nonzero(remaining), strict=True):
        if not remaining[y, x]:
            continue
        queue, pixels = deque([(int(y), int(x))]), []
        remaining[y, x] = False
        while queue:
            py, px = queue.popleft()
            pixels.append((py, px))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = py + dy, px + dx
                    if (dy or dx) and 0 <= ny < height and 0 <= nx < width and remaining[ny, nx]:
                        remaining[ny, nx] = False
                        queue.append((ny, nx))
        if len(pixels) >= min_pixels:
            result.append(np.asarray(pixels, dtype=np.int64))
    return sorted(result, key=lambda row: (int(row[:, 1].min()), int(row[:, 0].min())))


def project_pixel(service: InverseProjectionService, pixel: tuple[float, float]):
    return service.project_frame(ObservationFrame(
        frame_id=0, timestamp=0, target_id="rgb-contact-v2", camera_id=service.camera.camera_id,
        status=VisibilityStatus.OBSERVED, point_2d=pixel, provenance=Provenance.OBSERVED,
    ))


def world_pixel(camera: Camera, position: np.ndarray) -> np.ndarray:
    matrix = np.asarray(camera.camera_to_world)
    local = matrix[:3, :3].T @ (position - matrix[:3, 3])
    if local[2] >= 0:
        raise ValueError("HEIGHT_MODEL_BEHIND_CAMERA")
    return np.array([camera.cx + camera.fx * local[0] / -local[2],
                     camera.cy - camera.fy * local[1] / -local[2]])


def pixel_sensitivity(service: InverseProjectionService, pixel, step: float = 1) -> dict:
    base = project_pixel(service, pixel)
    samples = []
    for du, dv in ((-step, 0), (step, 0), (0, -step), (0, step),
                   (-step, -step), (-step, step), (step, -step), (step, step)):
        point = project_pixel(service, (pixel[0] + du, pixel[1] + dv))
        samples.append({"delta_px": [du, dv], "displacement_m": float(np.linalg.norm(
            np.asarray(point.world_position) - base.world_position))})
    return {"pixel_step": step, "samples": samples,
            "max_displacement_m": max(row["displacement_m"] for row in samples),
            "interpretation": "PIXEL_SENSITIVITY_NOT_TOTAL_ERROR_OR_CONFIDENCE_BOUND"}


def measure_component(coordinates: np.ndarray, service: InverseProjectionService,
                      config: ContactConfig) -> dict[str, Any]:
    ys, xs = coordinates.T
    bottom, top = int(ys.max()), int(ys.min())
    contact = (float(np.median(xs[ys == bottom])), float(bottom))
    top_pixel = np.array([float(np.median(xs[ys == top])), float(top)])
    reasons: list[str] = []
    result: dict[str, Any] = {
        "status": "MISSING", "position_kind": "MISSING", "world_position": None,
        "contact_pixel": list(contact), "top_pixel": top_pixel.tolist(),
        "bbox_xyxy": [int(xs.min()), top, int(xs.max()) + 1, bottom + 1],
        "pixel_count": len(xs), "incidence": None, "pixel_sensitivity": None,
        "height_model_residual_px": None, "reasons": reasons,
        "contact_authority": "RGB_MASK_PROXY_WITH_CONFIGURED_HEIGHT_CONSISTENCY",
        "identity_verdict": "UNKNOWN", "occlusion_verdict": "UNKNOWN",
        "inferred_position": None, "interpolation_allowed": False,
    }
    if xs.min() == 0 or ys.min() == 0 or xs.max() == service.camera.width - 1 or bottom == service.camera.height - 1:
        reasons.append("TOUCHES_IMAGE_EDGE")
    try:
        point = project_pixel(service, contact)
        result["incidence"] = point.projection_quality
        if point.projection_quality < config.min_incidence:
            reasons.append("LOW_INCIDENCE")
        # At the proposed bottom, a full upright configured target must reach its
        # visible top. Radius projects to a tolerance because the mask bottom is
        # the visible cylinder rim, not its hidden central foot.
        normal = np.asarray(service.plane.normal)
        foot = np.asarray(point.world_position)
        predicted = world_pixel(service.camera, foot + normal * config.assumed_target_height_m)
        tangent = np.cross(normal, [1, 0, 0] if abs(normal[0]) < 0.9 else [0, 1, 0])
        tangent /= np.linalg.norm(tangent)
        second = np.cross(normal, tangent)
        offsets = [v * config.assumed_target_radius_m for v in (tangent, -tangent, second, -second)]
        top_world = foot + normal * config.assumed_target_height_m
        radius_px = max(np.linalg.norm(world_pixel(service.camera, center + offset) - world_pixel(service.camera, center))
                        for center in (foot, top_world) for offset in offsets)
        # Perspective can slant an upright target across the image; include that
        # configured-height displacement before testing whether the mask is wide.
        width_limit = (abs(predicted[0] - contact[0]) + 2 * radius_px
                       + 2 * config.height_tolerance_px)
        result["configured_width_limit_px"] = width_limit
        if int(xs.max()) - int(xs.min()) + 1 > width_limit:
            reasons.append("AMBIGUOUS_MERGE")
        residual = float(np.linalg.norm(predicted - top_pixel))
        result["height_model_residual_px"] = residual
        result["height_model_tolerance_px"] = config.height_tolerance_px + radius_px
        if residual > config.height_tolerance_px + radius_px:
            reasons.append("CONTACT_OCCLUDED")
            result["occlusion_verdict"] = "SUSPECTED_FROM_CONFIGURED_HEIGHT_MISMATCH"
        try:
            result["pixel_sensitivity"] = pixel_sensitivity(service, contact, config.pixel_perturbation)
        except InverseProjectionError as error:
            reasons.append("PERTURBATION_" + error.failure.value)
        if not reasons:
            result.update(status="OBSERVED", position_kind="PROJECTED_OBSERVATION",
                          world_position=list(point.world_position))
    except InverseProjectionError as error:
        reasons.append(error.failure.value)
    except ValueError as error:
        reasons.append(str(error))
    return result


def produce_contact_v2(inputs: dict, config: ContactConfig) -> dict:
    """Strict allowlist: safe RGB/calibration/floor only; no truth is accessed."""
    value = _Inputs.model_validate(inputs)
    if value.floor_plane.source_sha256 != value.source_binding.source_sha256:
        raise ValueError("FLOOR_SOURCE_MISMATCH")
    keys = [(f.camera_id, f.timestamp) for f in value.frames]
    if len(keys) != len(set(keys)) or len({f.frame_ref for f in value.frames}) != len(keys):
        raise ValueError("FRAME_IMPORT_DUPLICATE")
    plane = Plane(plane_id="contact-v2-floor", point=value.floor_plane.point,
                  normal=value.floor_plane.normal, floor_id=value.floor_plane.floor_id)
    cameras = {row.camera_id: row.calibration for row in value.cameras}
    records = []
    for camera_id, camera in sorted(cameras.items()):
        service = InverseProjectionService(camera, plane)
        frames = sorted((f for f in value.frames if f.camera_id == camera_id), key=lambda f: f.timestamp)
        images, issues = {}, {}
        for frame in frames:
            try:
                raw = frame.local_path.read_bytes()
                if sha256(raw).hexdigest() != frame.sha256 or len(raw) != frame.byte_count:
                    raise ValueError("RGB_HASH_MISMATCH")
                with Image.open(BytesIO(raw)) as image:
                    if image.mode != "RGB" or image.size != (frame.width, frame.height) or image.size != (camera.width, camera.height):
                        raise ValueError("INVALID_RGB_DIMENSIONS")
                    images[frame.frame_ref] = np.asarray(image).copy()
            except (OSError, ValueError) as error:
                issues[frame.frame_ref] = str(error)
        background = np.median(np.stack(list(images.values())), axis=0).astype(np.int16) if images else None
        for frame in frames:
            common = {"camera_id": camera_id, "timestamp": float(frame.timestamp),
                      "frame_ref": frame.frame_ref, "source_image_sha256": frame.sha256}
            if frame.frame_ref in issues:
                records.append(dict(common, status="MISSING", position_kind="MISSING", world_position=None,
                                    components=[], reasons=[issues[frame.frame_ref]]))
                continue
            difference = np.max(abs(images[frame.frame_ref].astype(np.int16) - background), axis=2)
            components = components8(difference > config.difference_threshold, config.min_pixels)
            measured = [measure_component(c, service, config) for c in components]
            for index, row in enumerate(measured):
                row["component_ref"] = f"{VERSION}:{frame.frame_ref}:{index}"
            records.append(dict(common, status="MEASURED" if measured else "MISSING",
                                components=measured, reasons=[] if measured else ["NO_DETECTION"]))
    return {"producer_version": VERSION, "producer_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "config": config.model_dump(), "source_binding": value.source_binding.model_dump(),
            "calibration_sha256": sha256(json_bytes([c.model_dump(mode="json") for c in value.cameras])).hexdigest(),
            "floor_sha256": sha256(json_bytes(value.floor_plane.model_dump(mode="json"))).hexdigest(),
            "gt_used": False, "inferred_positions_enabled": False, "interpolation_enabled": False,
            "complete": all(not any(reason != "NO_DETECTION" for reason in r["reasons"]) for r in records),
            "frames": records}


def json_bytes(value: Any) -> bytes:
    import json
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()

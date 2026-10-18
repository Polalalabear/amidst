"""Same-observation hybrid contact projection, without GT or endpoint selection.

Draft K0 interval-observation v1. Clipping masks must be independently resolved
source-derived geometry. An obstacle footprint alone is NOT a foot-hidden mask.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from shapely.geometry import LineString, mapping

from amidst.domain.camera import Camera
from amidst.domain.geometry import Plane
from amidst.engineering.perception_v2 import pixel_sensitivity, project_pixel
from amidst.engineering.registry import content_hash
from amidst.geometry.inverse_projection import (
    InverseProjectionError,
    InverseProjectionFailure,
    InverseProjectionService,
)

Json = dict[str, Any]
DECLARATION_SOURCE = "PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT"


def k1_endpoint_eligibility(estimate):
    """D17 guard: LOW_INCIDENCE-only cannot use an occlusion constraint.

    C4a eligibility is separate from K1 map/clock and identity acceptance.
    Never selects or substitutes another observation.
    """
    reasons = []
    if estimate["status"] != "READY":
        reasons.append(estimate["reason"] or "C4A_NOT_READY")
    quality_reasons = set((estimate.get("contact_quality") or {}).get("reasons", []))
    if quality_reasons & {"AMBIGUOUS_MERGE", "TOUCHES_IMAGE_EDGE"}:
        reasons.append("D8_HEAD_ANCHOR_UNRELIABLE")
    if estimate["status"] == "READY" and estimate["basis"] not in {
        "FOOT_POINT",
        "HEAD_RAY_HEIGHT_PRIOR",
        "FOOT_RAY_PIXEL_BAND",
    }:
        reasons.append("UNSUPPORTED_BASIS")
    if estimate["status"] == "READY" and quality_reasons == {"LOW_INCIDENCE"}:
        if estimate["basis"] != "FOOT_RAY_PIXEL_BAND":
            reasons.append("V1_1_FOOT_BAND_REQUIRED")
        occlusion = [
            c for c in estimate.get("constraints_applied", []) if c["kind"] == "OCCLUDER_BEHIND"
        ]
        if (
            len(occlusion) != 1
            or occlusion[0]["effect"] != "NOT_APPLICABLE"
            or any(occlusion[0].get(k) is not None for k in ("ref", "ref_sha256"))
            or occlusion[0].get("length_before_m") != occlusion[0].get("length_after_m")
        ):
            reasons.append("D17_OCCLUDER_BEHIND_NOT_APPLICABLE")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "scope": "C4A_ONLY_NOT_K1_MAP_CLOCK_OR_IDENTITY_ACCEPTANCE",
        "endpoint_substitution": "NOT_PERFORMED",
    }


@dataclass(frozen=True)
class SourceClip:
    """Resolved source geometry; occluder masks are camera-specific foot shadows.

    `geometry` is the KEEP mask. Walkable UNKNOWN areas are retained by union,
    with their intersection length reported separately. No semantic annotations.
    """

    ref: str
    ref_sha256: str
    source_sha256: str
    geometry: Any
    floor_z_m: float
    body_radius_m: float
    unknown_geometry: Any = None
    tier: str = "SOURCE_DERIVED"
    camera_id: str | None = None
    meaning: str = "WALKABLE_AREA"

    def digest(self):
        return content_hash(
            {
                "source_sha256": self.source_sha256,
                "geometry": mapping(self.geometry),
                "unknown_geometry": None
                if self.unknown_geometry is None
                else mapping(self.unknown_geometry),
                "floor_z_m": self.floor_z_m,
                "body_radius_m": self.body_radius_m,
                "tier": self.tier,
                "camera_id": self.camera_id,
                "meaning": self.meaning,
            }
        )


def _prior(config, run_id, *, foot_band=False):
    declaration = copy.deepcopy(config["runs"].get(run_id))
    claimed = declaration.pop("declaration_sha256", None) if declaration else None
    if claimed is not None and claimed != content_hash(declaration):
        raise ValueError("FOOT_BAND_UNAVAILABLE" if foot_band else "HEIGHT_PRIOR_UNAVAILABLE")
    if not declaration or declaration["declaration_source"] != DECLARATION_SOURCE:
        raise ValueError("HEIGHT_PRIOR_UNAVAILABLE")
    if foot_band:
        k, radius = declaration.get("foot_anchor_band_px"), declaration.get("body_radius_m")
        if (
            not all(type(v) in (int, float) and math.isfinite(v) for v in (k, radius))
            or k < 1
            or radius <= 0
            or declaration["target_proxy"]["radius_m"] != radius
        ):
            raise ValueError("FOOT_BAND_UNAVAILABLE")
        return {**declaration, "declaration_sha256": content_hash(declaration)}
    prior = declaration["head_height_prior"]
    height, tolerance = prior["nominal_m"], prior["tolerance_m"]
    radius = declaration["body_radius_m"]
    if (
        not all(type(v) in (int, float) and math.isfinite(v) for v in (height, tolerance, radius))
        or not 0 < tolerance < height
        or radius <= 0
        or declaration["target_proxy"]["height_m"] != height
        or declaration["target_proxy"]["radius_m"] != radius
    ):
        raise ValueError("HEIGHT_PRIOR_UNAVAILABLE")
    if (
        declaration["target_proxy"]["label"] != "SYNTHETIC_CYLINDER_NOT_HUMAN_SIZED"
        and height + tolerance > 2.5
    ):
        raise ValueError("HEIGHT_PRIOR_UNAVAILABLE")
    return {**declaration, "declaration_sha256": content_hash(declaration)}


def _height_segment(service, pixel, prior):
    origin = np.asarray(service.camera.camera_to_world)[:3, 3]
    floor = service.plane.point[2]
    maximum = prior["nominal_m"] + prior["tolerance_m"]
    if origin[2] <= floor + maximum:
        raise ValueError("HEAD_RAY_NOT_DESCENDING")
    # Direction is computed with exactly the shared calibrated camera convention.
    u, v = pixel
    camera = service.camera
    direction = np.asarray(camera.camera_to_world)[:3, :3] @ np.array(
        [(u - camera.cx) / camera.fx, (camera.cy - v) / camera.fy, -1.0]
    )
    direction /= np.linalg.norm(direction)
    if direction[2] >= 0:
        raise ValueError("HEAD_RAY_NOT_DESCENDING")
    endpoints = []
    for height in (maximum, prior["nominal_m"] - prior["tolerance_m"]):
        plane = service.plane.model_copy(
            update={"point": (service.plane.point[0], service.plane.point[1], floor + height)}
        )
        point = project_pixel(InverseProjectionService(service.camera, plane), pixel)
        position = list(point.world_position)
        if position[2] >= origin[2]:
            raise ValueError("HEAD_RAY_NOT_DESCENDING")
        position[2] = floor
        endpoints.append(position)
    return endpoints, origin.tolist(), direction.tolist()


def _foot_segment(service, pixel, declaration):
    k, radius = declaration["foot_anchor_band_px"], declaration["body_radius_m"]
    u, v = pixel
    raw = [list(project_pixel(service, (u, v + delta)).world_position) for delta in (k, -k)]
    delta = np.asarray(raw[1][:2]) - np.asarray(raw[0][:2])
    length = np.linalg.norm(delta)
    if length <= 1e-12:
        raise InverseProjectionError(
            InverseProjectionFailure.NUMERICAL_FAILURE, "DEGENERATE_FOOT_BAND"
        )
    extended = copy.deepcopy(raw)
    extended[1][:2] = (np.asarray(raw[1][:2]) + radius * delta / length).tolist()
    return raw, extended


def estimate_contact(
    observation: Json,
    component: Json | None,
    quality: Json | None,
    camera: Camera,
    plane: Plane,
    provenance: Json,
    config: Json,
    *,
    occluder: SourceClip | None = None,
    walkable: SourceClip | None = None,
) -> Json:
    """Only image/calibration/declarations and source-derived clip masks enter.

    Returns a sibling field. Never changes observation world_position, state,
    contact flags, track or timestamp. No search for substitute endpoints.
    """
    anchor = copy.deepcopy(observation.get("contact_pixel"))
    result = {
        "schema_version": "office-demo.interval-observation.v1",
        "observation_ref": observation["observation_ref"],
        "camera_id": observation["camera_id"],
        "timestamp_s": observation["timestamp"],
        "status": "UNKNOWN",
        "reason": None,
        "evidence_state": "PROJECTED_OBSERVATION",
        "estimate_kind": "NONE",
        "basis": "NONE",
        "point_m": None,
        "segment": None,
        "image_anchor_px": anchor,
        "pixel_sensitivity_m": None,
        "constraints_applied": [],
        "contact_quality": copy.deepcopy(quality),
        "authority": "PROJECTION_ONLY_NOT_POSITION_AUTHORITY",
        "identity_verdict": "UNCONFIRMED",
        "physical_authority": "UNKNOWN",
        "provenance": copy.deepcopy(provenance),
        "diagnostics": {
            "endpoint_substitution": "NOT_PERFORMED",
            "raw_interval_length_m": None,
            "raw_coordinates_use": "DIAGNOSTIC_ONLY_NOT_POSITION_OR_ENDPOINT",
            "raw_coordinates_usable_as_position": False,
            "raw_coordinates_usable_as_endpoint": False,
        },
    }

    def finish(reason=None):
        result["reason"] = reason
        if reason:
            result.update(
                status="UNKNOWN",
                estimate_kind="NONE",
                basis="NONE",
                point_m=None,
                segment=None,
                pixel_sensitivity_m=None,
            )
        result["output_sha256"] = content_hash(result)
        return result

    if (
        provenance.get("gt_read") is not False
        or provenance.get("source_sha256") != config["source_sha256"]
        or camera.camera_id != observation["camera_id"]
    ):
        return finish("PROVENANCE_MISMATCH")
    if tuple(plane.normal) != (0, 0, 1):
        return finish("PROJECTION_FAILED")
    foot_band = (
        quality is not None
        and quality["status"] == "FLAGGED"
        and set(quality["reasons"]) == {"LOW_INCIDENCE"}
    )
    try:
        declaration = _prior(config, provenance["run_ref"], foot_band=foot_band)
    except (KeyError, TypeError, ValueError):
        return finish("FOOT_BAND_UNAVAILABLE" if foot_band else "HEIGHT_PRIOR_UNAVAILABLE")
    result["provenance"]["run_parameters"] = declaration
    if quality is None:
        return finish("CONTACT_QUALITY_MISSING")
    if quality["status"] == "NOT_EVALUATED":
        return finish("CONTACT_QUALITY_NOT_EVALUATED")
    reasons = set(quality["reasons"])
    if reasons & {"AMBIGUOUS_MERGE", "TOUCHES_IMAGE_EDGE"}:
        return finish("HEAD_ANCHOR_UNRELIABLE")
    try:
        service = InverseProjectionService(camera, plane)
    except InverseProjectionError:
        return finish("PROJECTION_FAILED")
    if quality["status"] == "PASS":
        if reasons or component is None or component.get("world_position") is None:
            return finish("PROJECTION_FAILED")
        anchor = component["contact_pixel"]
        result["image_anchor_px"] = list(anchor)
        try:
            point = list(project_pixel(service, tuple(anchor)).world_position)
            sensitivity = pixel_sensitivity(service, tuple(anchor))["max_displacement_m"]
        except InverseProjectionError:
            return finish("PROJECTION_FAILED")
        if not np.allclose(point, component["world_position"], rtol=0, atol=1e-9):
            return finish("PROVENANCE_MISMATCH")
        if (
            quality["pixel_sensitivity_m"] is None
            or abs(sensitivity - quality["pixel_sensitivity_m"]) > 1e-6
        ):
            return finish("PIXEL_SENSITIVITY_UNAVAILABLE")
        result.update(
            status="READY",
            estimate_kind="POINT",
            basis="FOOT_POINT",
            point_m=point,
            pixel_sensitivity_m=sensitivity,
        )
        return finish()
    if (
        quality["status"] != "FLAGGED"
        or not reasons
        or not reasons <= {"LOW_INCIDENCE", "CONTACT_OCCLUDED"}
    ):
        return finish("HEAD_ANCHOR_UNRELIABLE")
    if component is None:
        return finish("HEAD_ANCHOR_UNRELIABLE")
    # Use only the uniquely matched component; no cross-basis fallback.
    prior = declaration.get("head_height_prior")
    origin = np.asarray(service.camera.camera_to_world)[:3, 3].tolist()
    direction = None
    try:
        if foot_band:
            anchor = tuple(component["contact_pixel"])
            raw, extended = _foot_segment(service, anchor, declaration)
            incidence = project_pixel(service, anchor).projection_quality
        else:
            xmin, ymin, xmax, _ = component["bbox_xyxy"]
            anchor = ((xmin + xmax - 1) / 2, ymin)
            raw, origin, direction = _height_segment(service, anchor, prior)
            extended = raw
    except InverseProjectionError:
        return finish("PROJECTION_FAILED")
    except ValueError as error:
        return finish(str(error))
    result["image_anchor_px"] = list(anchor)
    length = math.dist(raw[0], raw[1])
    result["diagnostics"]["raw_interval_length_m"] = length
    result["diagnostics"]["raw_near_m"], result["diagnostics"]["raw_far_m"] = raw
    line = LineString([p[:2] for p in extended])
    constraints = result["constraints_applied"]
    constraints.append(
        {
            "kind": "FOOT_RAY_PIXEL_BAND" if foot_band else "HEIGHT_PRIOR",
            "ref": declaration["declaration_ref"],
            "ref_sha256": declaration["declaration_sha256"],
            "effect": "BOUNDED",
            "length_before_m": None,
            "length_after_m": line.length,
            "walkable_unknown_length_m": None,
        }
    )
    # D17: a visible foot at low incidence has no foot-hidden premise.
    applicable_occluder = occluder if "CONTACT_OCCLUDED" in reasons else None
    for kind, clip in (("OCCLUDER_BEHIND", applicable_occluder), ("WALKABLE_AREA", walkable)):
        before = line.length
        unknown = None
        step = {
            "kind": kind,
            "ref": clip.ref if clip else None,
            "ref_sha256": clip.ref_sha256 if clip else None,
            "effect": "NOT_AVAILABLE",
            "length_before_m": before,
            "length_after_m": before,
            "walkable_unknown_length_m": unknown,
        }
        constraints.append(step)
        if kind == "OCCLUDER_BEHIND" and "CONTACT_OCCLUDED" not in reasons:
            step["effect"] = "NOT_APPLICABLE"
            continue
        if clip is None:
            continue
        if (
            clip.tier != "SOURCE_DERIVED"
            or clip.source_sha256 != provenance["source_sha256"]
            or clip.ref_sha256 != clip.digest()
            or clip.floor_z_m != plane.point[2]
            or clip.body_radius_m != declaration["body_radius_m"]
            or not clip.geometry.is_valid
            or (
                kind == "OCCLUDER_BEHIND"
                and (
                    clip.camera_id != camera.camera_id
                    or clip.meaning != "FOOT_HIDDEN_FROM_THIS_CAMERA"
                )
            )
            or (kind == "WALKABLE_AREA" and clip.meaning != "WALKABLE_AREA")
        ):
            return finish("PROVENANCE_MISMATCH")
        result["provenance"]["annotation_sha256"][
            "occluders" if kind == "OCCLUDER_BEHIND" else "walkable"
        ] = clip.ref_sha256
        mask = clip.geometry
        if kind == "WALKABLE_AREA" and clip.unknown_geometry is not None:
            if not clip.unknown_geometry.is_valid:
                return finish("PROVENANCE_MISMATCH")
            mask = mask.union(clip.unknown_geometry)
        previous = line
        line = line.intersection(mask)
        step.update(
            effect="NO_CHANGE" if line.equals(previous) else "CLIPPED",
            length_after_m=line.length,
        )
        if line.is_empty or line.length <= 1e-10:
            step["effect"] = "EMPTIED"
            return finish("SEGMENT_EMPTY_AFTER_CONSTRAINTS")
        if line.geom_type != "LineString":
            return finish("SEGMENT_NON_CONTIGUOUS")
        if kind == "WALKABLE_AREA":
            step["walkable_unknown_length_m"] = (
                0
                if clip.unknown_geometry is None
                else line.intersection(clip.unknown_geometry).length
            )
    result["diagnostics"]["clipped_interval_length_m"] = line.length
    if line.length > config["max_segment_length_m"]:
        return finish("SEGMENT_TOO_LONG")
    try:
        displacements = []
        for du, dv in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            shifted_anchor = (anchor[0] + du, anchor[1] + dv)
            if foot_band:
                _, shifted = _foot_segment(service, shifted_anchor, declaration)
            else:
                shifted, _, _ = _height_segment(service, shifted_anchor, prior)
            shifted_line = LineString([p[:2] for p in shifted])
            for kind, clip in (
                ("OCCLUDER_BEHIND", applicable_occluder),
                ("WALKABLE_AREA", walkable),
            ):
                if clip is None:
                    continue
                mask = clip.geometry
                if kind == "WALKABLE_AREA" and clip.unknown_geometry is not None:
                    mask = mask.union(clip.unknown_geometry)
                shifted_line = shifted_line.intersection(mask)
                if shifted_line.is_empty or shifted_line.geom_type != "LineString":
                    raise ValueError("PIXEL_SENSITIVITY_UNAVAILABLE")
            base_ends = sorted(
                (line.coords[0], line.coords[-1]), key=lambda p: math.dist(p, origin[:2])
            )
            shifted_ends = sorted(
                (shifted_line.coords[0], shifted_line.coords[-1]),
                key=lambda p: math.dist(p, origin[:2]),
            )
            displacements.extend(
                math.dist(a, b) for a, b in zip(base_ends, shifted_ends, strict=True)
            )
        sensitivity = max(displacements)
    except (InverseProjectionError, ValueError):
        return finish("PIXEL_SENSITIVITY_UNAVAILABLE")
    points = [[x, y, plane.point[2]] for x, y in (line.coords[0], line.coords[-1])]
    points.sort(key=lambda p: math.hypot(p[0] - origin[0], p[1] - origin[1]))
    result.update(
        status="READY",
        estimate_kind="SEGMENT",
        basis="FOOT_RAY_PIXEL_BAND" if foot_band else "HEAD_RAY_HEIGHT_PRIOR",
        pixel_sensitivity_m=sensitivity,
        segment={
            "near_m": points[0],
            "far_m": points[1],
            "length_m": line.length,
            "raw_near_m": raw[0],
            "raw_far_m": raw[1],
            "height_prior": None
            if foot_band
            else {
                "nominal_m": prior["nominal_m"],
                "tolerance_m": prior["tolerance_m"],
                "min_m": prior["nominal_m"] - prior["tolerance_m"],
                "max_m": prior["nominal_m"] + prior["tolerance_m"],
                "source": DECLARATION_SOURCE,
                "declaration_ref": declaration["declaration_ref"],
            },
            "foot_band": {
                "band_px": declaration["foot_anchor_band_px"],
                "body_radius_m": declaration["body_radius_m"],
                "anchor_incidence": incidence,
                "source": DECLARATION_SOURCE,
                "declaration_ref": declaration["declaration_ref"],
            }
            if foot_band
            else None,
            "ray_origin_m": None if foot_band else origin,
            "ray_direction": direction,
        },
    )
    return finish()

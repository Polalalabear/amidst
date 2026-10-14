"""Bind the unchanged projection composer to exact approved scoped evidence.

Only strict 2D observations, an independent source context and the intact approved
union provider enter this adapter. Computational pilot labels remain diagnostic;
the separate wrapper records the actual source authority. Every raw frame and
projection is retained, including unavailable or outside-union points. Physical
consumers own their subsequent eligibility checks.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from amidst.datasets.pilot import (
    PilotInferenceContext,
    PilotObservationExport,
    PilotZoneContext,
)
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.geometry import Plane
from amidst.domain.observation import ProjectedPoint
from amidst.finalization.scoped_authority import (
    ScopeCameraLandmarkBinding,
    ScopedUnionPhysicalProvider,
)
from amidst.finalization.scoped_route_inventory import (
    ScopedRouteAuthorityBinding,
    _check_authority,
)
from amidst.observation.aggregation import validate_stream_model
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_units import native_projected_point_to_metres
from amidst.scene_geometry import Digest, GeometryModel

NO_PLANE = "EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION"

# Preserved producers at the original finalization checkpoint; new adapters may
# not silently replace their method/conditioning/uncertainty policy.
PROJECTOR_SHA256 = {
    "phase1_projection_policy.py":
        "f6f7546641e26e4c154e0cd693e57597ac294ccb042fd0ad74441cc32a0786d6",
    "projection_multiview_model.py":
        "63f170bfd40b06583bbb0841976a82d49df37e988d4d1d461f07fb5bc3a803ea",
    "projection_mitigation_policy.py":
        "a1f595ec1e6e9a63c10de8ea8571cae8b118771e93b7459dace5616d38a6448a",
    "projection_uncertainty_model.py":
        "fadf8ddc6859024a61fa41f4f7fc27a7795ee6be99c6786ad760fc7e7234ebfc",
}


class ScopedSourceContext(GeometryModel):
    """The source export's allowlisted inference context; no recipe/reference fields."""

    schema_version: Literal["phase1-scoped-source-context-v1"]
    source_id: str = Field(min_length=1)
    source_sha256: Digest
    spatial_context_id: str = Field(min_length=1)
    scope_id: str = Field(min_length=1)
    authority: ScopedRouteAuthorityBinding
    camera_bindings: tuple[ScopeCameraLandmarkBinding, ...] = Field(min_length=2, max_length=3)
    coordinate_units: Literal["BLENDER_NATIVE_UNITS"]
    metres_per_blender_unit: float = Field(gt=0, allow_inf_nan=False)
    observations_sha256: Digest
    config_file_sha256: Digest
    export_lock_file_sha256: Digest
    ground_truth_available_to_inference: Literal[False]

    @model_validator(mode="after")
    def unique_cameras(self) -> ScopedSourceContext:
        if len({b.camera.camera_id for b in self.camera_bindings}) != len(self.camera_bindings):
            raise ValueError("scoped source calibration camera identities must be unique")
        return self

    @property
    def plane_id(self) -> str:
        return "SCOPED_LANDMARK_PLANE:" + self.scope_id


@dataclass(frozen=True, slots=True)
class ScopedProjectionResult:
    context: ScopedSourceContext
    computation_context: PilotInferenceContext
    native_frames: FrameSampleDataset
    frames: FrameSampleDataset
    sidecar: dict[str, Any]


def _producer_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    actual = {name: hashlib.sha256((root / "scripts" / name).read_bytes()).hexdigest()
              for name in PROJECTOR_SHA256}
    if actual != PROJECTOR_SHA256:
        raise ValueError("original projection producer bytes differ from the preserved policy")
    return {"scripts/" + name: value for name, value in actual.items()}


@lru_cache(maxsize=1)
def _composer() -> Any:
    path = Path(__file__).resolve().parents[3] / "scripts" / "phase1_projection_policy.py"
    spec = importlib.util.spec_from_file_location("amidst_scoped_original_projection", path)
    if spec is None or spec.loader is None:
        raise ValueError("original projection composer is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _computation_context(
    context: ScopedSourceContext, observations: PilotObservationExport,
    provider: ScopedUnionPhysicalProvider,
) -> PilotInferenceContext:
    _check_authority(provider, context.authority)
    if context.source_sha256 != provider.source_sha256 or (
        context.scope_id != provider.scope_id
        or context.metres_per_blender_unit != provider.contract.scale.metres_per_blender_unit
        or observations.source_asset_sha256 != context.source_sha256
        or not provider.proposal.requested_projection_authority
    ):
        raise ValueError("scoped projection source/scope/scale differs from approved authority")
    approved = {b.camera.camera_id: b for b in provider.proposal.camera_landmark_bindings}
    bindings = sorted(context.camera_bindings, key=lambda b: b.camera.camera_id)
    if any(approved.get(b.camera.camera_id) != b for b in bindings):
        raise ValueError("scoped projection calibration/landmark differs from exact approval")
    if {f.camera_id for f in observations.frames} != {b.camera.camera_id for b in bindings}:
        raise ValueError("scoped observation camera set differs from its source context")
    first = bindings[0]
    if any(
        b.landmark_offset_bu != first.landmark_offset_bu
        or b.projection_plane_point_bu != first.projection_plane_point_bu
        or b.projection_plane_normal != first.projection_plane_normal
        for b in bindings
    ):
        raise ValueError("unchanged composer requires one common approved rigid landmark plane")
    floor = provider.proposal.floor
    if first.floor_id != floor.floor_id or first.projection_plane_point_bu[2] != (
        floor.point[2] + first.landmark_offset_bu[2]
    ) or first.landmark_offset_bu[:2] != (0., 0.):
        raise ValueError("scoped rigid landmark plane differs from approved source support")
    zone_id = "SCOPED_UNION:" + context.scope_id
    cells = provider.proposal.cells
    return PilotInferenceContext(
        label=observations.label, data_kind="SYNTHETIC", site_id=observations.site_id,
        source_id=context.source_id, spatial_context_id=context.spatial_context_id,
        source_asset_sha256=context.source_sha256, observations_sha256=context.observations_sha256,
        cameras=tuple(b.camera for b in bindings),
        plane=Plane(
            plane_id=context.plane_id, point=first.projection_plane_point_bu,
            normal=first.projection_plane_normal, floor_id=floor.floor_id, zone_id=zone_id,
        ),
        zone=PilotZoneContext(
            floor_id=floor.floor_id, zone_id=zone_id, walkable_object_id=context.scope_id,
            bounds_min=(min(c.rectangle_xy_bu[0] for c in cells),
                        min(c.rectangle_xy_bu[1] for c in cells), floor.point[2]),
            bounds_max=(max(c.rectangle_xy_bu[2] for c in cells),
                        max(c.rectangle_xy_bu[3] for c in cells), floor.point[2]),
            authority="ANNOTATION_AABB_ONLY_PROVISIONAL",
        ),
    )


def _preserved_frames(
    dataset: FrameSampleDataset, observations: PilotObservationExport,
    computation: PilotInferenceContext,
) -> None:
    originals = {(f.camera_id, f.frame_id, f.timestamp, f.target_id): f
                 for f in observations.frames}
    if len(originals) != len(observations.frames) or len(dataset.samples) != len(originals):
        raise ValueError("scoped projection must retain every distinct original frame")
    seen = set()
    for sample in dataset.samples:
        identity = sample.camera_id, sample.frame_id, sample.timestamp, sample.target_id
        if identity not in originals or identity in seen:
            raise ValueError("scoped projected frame identities differ from source evidence")
        seen.add(identity)
        frame = originals[identity]
        if sample.binding != computation.binding or (
            sample.uv != frame.point_2d or sample.visibility != frame.status
            or sample.provenance != frame.provenance or sample.gap_reason != frame.gap_reason
            or sample.occluder_id != frame.occluder_id
        ):
            raise ValueError("scoped projection changed raw source evidence")


def project_scoped_observations(
    observations: bytes, context: bytes, provider: ScopedUnionPhysicalProvider,
) -> ScopedProjectionResult:
    """Project exact input bytes, then subtract only approved Z and convert BU→SI.

    This in-memory API does not open simulation, evaluation, recipes or references.
    Source inputs must be raw bytes so their exact file digests remain verifiable.
    No point is clipped, snapped or removed; outside-scope consumption fails later
    at the intact physical provider rather than changing the evidence population.
    """
    if not isinstance(observations, bytes) or not isinstance(context, bytes):
        raise TypeError("scoped projection requires exact observations/context bytes")
    source = ScopedSourceContext.model_validate_json(context)
    if hashlib.sha256(observations).hexdigest() != source.observations_sha256:
        raise ValueError("scoped observations SHA256 differs from source context binding")
    evidence = PilotObservationExport.model_validate_json(observations)
    computation = _computation_context(source, evidence, provider)
    producers = _producer_hashes()
    composer = _composer()
    policy_projection = composer.project_export(computation, evidence)
    native_frames = validate_stream_model(
        composer.project_policy_frames(evidence, computation), FrameSampleDataset,
    )
    _preserved_frames(native_frames, evidence, computation)
    if policy_projection["ground_truth_read"] is not False or (
        policy_projection["source_asset_sha256"] != source.source_sha256
        or policy_projection["observations_sha256"] != source.observations_sha256
        or policy_projection["retained_evidence_count"] != len(evidence.frames)
    ):
        raise ValueError("original projection sidecar differs from preserved source evidence")
    rows = {(row["timestamp"], row["frame_id"], row["target_id"]): row
            for row in policy_projection["rows"]}
    offsets = {b.camera.camera_id: b.landmark_offset_bu[2] for b in source.camera_bindings}
    samples, conversions = [], []
    for sample in native_frames.samples:
        point = sample.projected_point
        converted = None
        if point is not None:
            row = rows[sample.timestamp, sample.frame_id, sample.target_id]
            if point.plane_id not in {source.plane_id, NO_PLANE} or (
                point.floor_id != computation.zone.floor_id
                or point.zone_id != computation.zone.zone_id
                or row["ground_truth_read"] is not False
                or row["selection_uses_ground_truth"] is not False
            ):
                raise ValueError("scoped projection method/plane/floor provenance differs")
            if point.plane_id == NO_PLANE:
                if row["method"] != "EXACT_TIME_MULTIVIEW" or (
                    point.camera_id not in row["selected_camera_ids"]
                ):
                    raise ValueError("no-plane point must retain its exact-time pair evidence")
                expected = row["selected_world_position"]
            else:
                plane = next(item["conditioning"] for item in row["fixed_plane_sidecars"]
                             if item["conditioning"]["camera_id"] == point.camera_id)
                expected = plane["projected_point"]["world_position"]
            if tuple(expected) != point.world_position:
                raise ValueError("projected point differs from the unchanged method sidecar")
            p = point.world_position
            shifted = ProjectedPoint.model_validate(point.model_dump(mode="python") | {
                "world_position": (p[0], p[1], p[2] - offsets[sample.camera_id]),
            })
            converted = native_projected_point_to_metres(
                shifted, provider.contract.scale, source_asset_sha256=source.source_sha256,
            )
            conversions.append({
                "sample_id": sample.sample_id, "plane_id": point.plane_id,
                "native_landmark_position_bu": point.world_position,
                "offset_bu": offsets[sample.camera_id],
                "native_floor_contact_position_bu": shifted.world_position,
                "floor_contact_position_m": converted.world_position,
            })
        samples.append(type(sample).model_validate(sample.model_dump(mode="python") | {
            "projected_point": None if converted is None else converted.model_dump(mode="python"),
        }))
    frames = FrameSampleDataset(samples=tuple(samples))
    _preserved_frames(frames, evidence, computation)
    sidecar = {
        "schema_version": "phase1-scoped-source-projection-v1",
        "status": "APPROVED_SOURCE_BINDING_PROJECTED_FORMAL_CASE_READINESS_PENDING",
        "source_id": source.source_id, "spatial_context_id": source.spatial_context_id,
        "source_sha256": source.source_sha256, "scope_id": source.scope_id,
        "source_asset_sha256": source.source_sha256,
        "observations_sha256": source.observations_sha256,
        "authority": source.authority.model_dump(mode="json"),
        "camera_bindings": [b.model_dump(mode="json") for b in source.camera_bindings],
        "observations_file_sha256": source.observations_sha256,
        "context_file_sha256": hashlib.sha256(context).hexdigest(),
        "context_content_sha256": content_sha256(source.model_dump(mode="json")),
        "config_file_sha256": source.config_file_sha256,
        "export_lock_file_sha256": source.export_lock_file_sha256,
        "computation_context_content_sha256": content_sha256(computation.model_dump(mode="json")),
        "native_frames_content_sha256": content_sha256(native_frames.model_dump(mode="json")),
        "frames_content_sha256": content_sha256(frames.model_dump(mode="json")),
        "projection_producer_hashes": producers,
        "policy_projection": policy_projection,
        "rows": policy_projection["rows"],
        "conversion": "SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY_THEN_BU_TO_SI",
        "coordinate_units": "METRES_AFTER_NATIVE_PROJECTION",
        "point_conversions": conversions,
        "retained_evidence_count": len(frames.samples), "ground_truth_read": False,
        "sample_rejection_count": 0, "clipping_or_snapping_applied": False,
        "outside_union_points": "RETAINED_PHYSICAL_CONSUMER_MUST_VALIDATE",
        "computational_literals_relabelled": False, "formal_case_readiness": False,
    }
    return ScopedProjectionResult(source, computation, native_frames, frames, sidecar)

"""Scoped source projection tests on synthetic approved geometry, never school truth."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from pydantic import ValidationError
from test_scoped_authority import _decision, _inputs

from amidst.datasets.pilot import PILOT_LABEL
from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.finalization.scoped_authority import (
    ScopeCameraLandmarkBinding,
    ScopedUnionPhysicalProvider,
    apply_scope_approval,
    contract_content_sha256,
    load_scoped_authority,
)
from amidst.finalization.scoped_projection import NO_PLANE, project_scoped_observations
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.scene_geometry import GeometryAuthorityError
from amidst.simulation.virtual_camera import project_world


@pytest.fixture(scope="module")
def approved() -> ScopedUnionPhysicalProvider:
    proposal, evidence, old_contract, numerics = _inputs()
    # A declared synthetic scale of 2 m/BU makes accidental identity conversion
    # detectable while retaining ample source support/body guards in the fixture.
    contract = PhysicalPolicyContract(
        old_contract.policy,
        old_contract.scale.model_copy(update={"metres_per_blender_unit": 2.}),
        old_contract.runtime,
    )
    scale = contract.scale.model_dump(mode="json")
    evidence = evidence | {
        "architectural_scale": scale,
        "architectural_scale_content_sha256": content_sha256(scale),
    }
    cameras = tuple(Camera(
        camera_id="synthetic-source-" + identity,
        camera_to_world=((1., 0., 0., x), (0., 1., 0., 5.),
                         (0., 0., 1., 10.), (0., 0., 0., 1.)),
        fx=100., fy=100., cx=500., cy=500., width=1000, height=1000, floor_id="1F",
    ) for identity, x in (("a", 2.), ("b", 8.)))
    camera_export = {"source_sha256": proposal.pins.source_sha256,
                     "cameras": [c.model_dump(mode="json") for c in cameras]}
    bindings = tuple(ScopeCameraLandmarkBinding(
        camera=camera, calibration_content_sha256=content_sha256(camera.model_dump(mode="json")),
        source_camera_export_content_sha256=content_sha256(camera_export), floor_id="1F",
        landmark_offset_bu=(0., 0., 1.), projection_plane_point_bu=(0., 0., 1.),
    ) for camera in cameras)
    proposal = proposal.model_copy(update={
        "pins": proposal.pins.model_copy(update={
            "physical_contract_content_sha256": contract_content_sha256(contract),
            "evidence_content_sha256": content_sha256(evidence),
            "camera_export_content_sha256": content_sha256(camera_export),
        }), "camera_landmark_bindings": bindings, "requested_projection_authority": True,
    })
    decision = _decision(proposal)
    certificate, detail = apply_scope_approval(
        proposal, decision, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_proposal_content_sha256=content_sha256(proposal.model_dump(mode="json")),
        expected_decision_content_sha256=content_sha256(decision.model_dump(mode="json")),
        camera_export=camera_export,
    )
    assert certificate is not None, detail
    return load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
        camera_export=camera_export,
    )


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def _inputs_for(
    provider: ScopedUnionPhysicalProvider, *, outside: bool = False,
) -> tuple[bytes, bytes]:
    cameras = provider.proposal.camera_landmark_bindings
    positions = ((2.25, 2.25, 1.), (2.25, 2.25, 1.), (7.75, 2.25, 1.))
    frames = []
    for index, position in enumerate(positions):
        for camera_index, binding in enumerate(cameras):
            observed = index == 0 or (index == 2 and camera_index == 0)
            point = (5., 5., 1.) if outside else position
            projected = project_world(binding.camera, point)
            assert projected.point_2d is not None
            frames.append(ObservationFrame(
                frame_id=index, timestamp=index * .2, target_id="synthetic-target",
                camera_id=binding.camera.camera_id,
                status="OBSERVED" if observed else "GAP",
                point_2d=projected.point_2d if observed else None,
                provenance=Provenance.OBSERVED if observed else None,
                gap_reason=None if observed else "OCCLUDED",
                occluder_id=None if observed else "synthetic-source-occluder",
            ).model_dump(mode="json"))
    observations = _bytes({
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "site_id": "synthetic-scoped-source",
        "source_asset_sha256": provider.source_sha256, "frames": frames,
    })
    cert = provider.certificate
    authority = ScopedRouteAuthorityBinding(
        pins=cert.pins, proposal_content_sha256=cert.proposal_content_sha256,
        decision_content_sha256=cert.human_decision_content_sha256,
        certificate_content_sha256=provider.certificate_content_sha256,
        union_wkb_sha256=cert.union_wkb_sha256,
    )
    context = _bytes({
        "schema_version": "phase1-scoped-source-context-v1", "source_id": "synthetic-fresh-source",
        "spatial_context_id": "synthetic-fresh-context", "source_sha256": provider.source_sha256,
        "scope_id": provider.scope_id, "authority": authority.model_dump(mode="json"),
        "camera_bindings": [c.model_dump(mode="json") for c in cameras],
        "coordinate_units": "BLENDER_NATIVE_UNITS", "metres_per_blender_unit": 2.,
        "observations_sha256": hashlib.sha256(observations).hexdigest(),
        "config_file_sha256": "c" * 64, "export_lock_file_sha256": "d" * 64,
        "ground_truth_available_to_inference": False,
    })
    return observations, context


def test_original_multiview_first_fallback_raw_gaps_and_diagnostic_literals_survive(
    approved: ScopedUnionPhysicalProvider,
) -> None:
    observations, context = _inputs_for(approved)
    result = project_scoped_observations(observations, context, approved)
    rows = result.sidecar["rows"]
    assert [row["method"] for row in rows] == [
        "EXACT_TIME_MULTIVIEW", "UNAVAILABLE", "SINGLE_VIEW_FIXED_PLANE",
    ]
    assert result.computation_context.label == PILOT_LABEL
    assert result.computation_context.scale_authority == "UNVERIFIED"
    assert result.computation_context.zone.authority == "ANNOTATION_AABB_ONLY_PROVISIONAL"
    assert result.sidecar["policy_projection"]["policy_status"] == (
        "PROVISIONAL_NOT_APPROVED_SCHOOL_CAMERA_PLANE_BINDING"
    )
    assert result.sidecar["computational_literals_relabelled"] is False
    assert result.sidecar["formal_case_readiness"] is False
    assert len(result.frames.samples) == len(result.native_frames.samples) == 6
    assert sum(s.projected_point is not None for s in result.frames.samples) == 3
    for row in rows:
        assert row["ground_truth_read"] is row["selection_uses_ground_truth"] is False
        assert row["evidence_rejected_by_confidence"] == 0
        assert row["uncertainty"]["status"] == "UNAVAILABLE"
    assert rows[0]["uncertainty"]["reason"] == "MULTIVIEW_COVARIANCE_NOT_MODELED"
    assert rows[2]["uncertainty"]["reason"] == "PIXEL_SIGMA_NOT_DECLARED"
    for sample in result.frames.samples:
        if sample.visibility == VisibilityStatus.GAP:
            assert sample.projected_point is sample.uv is sample.provenance is None
            assert sample.occluder_id == "synthetic-source-occluder"
        else:
            assert sample.projected_point is not None
            expected_plane = NO_PLANE if sample.frame_id == 0 else result.context.plane_id
            assert sample.projected_point.plane_id == expected_plane
    assert rows[0]["selected_camera_ids"] == ["synthetic-source-a", "synthetic-source-b"]


def test_offset_then_si_preserves_raw_identity_and_exact_file_hash_binding(
    approved: ScopedUnionPhysicalProvider,
) -> None:
    observations, context = _inputs_for(approved)
    result = project_scoped_observations(observations, context, approved)
    for original, converted in zip(
        result.native_frames.samples, result.frames.samples, strict=True,
    ):
        assert converted.model_dump(exclude={"projected_point"}) == (
            original.model_dump(exclude={"projected_point"})
        )
        if original.projected_point is not None:
            assert converted.projected_point is not None
            native = original.projected_point.world_position
            assert converted.projected_point.world_position == (
                native[0] * 2., native[1] * 2., (native[2] - 1.) * 2.,
            )
            assert converted.projected_point.model_dump(exclude={"world_position"}) == (
                original.projected_point.model_dump(exclude={"world_position"})
            )
    assert result.sidecar["observations_file_sha256"] == hashlib.sha256(observations).hexdigest()
    assert result.sidecar["context_file_sha256"] == hashlib.sha256(context).hexdigest()
    assert result.sidecar["frames_content_sha256"] == content_sha256(
        result.frames.model_dump(mode="json"),
    )


def test_outside_union_projection_is_retained_and_not_snapped_to_support(
    approved: ScopedUnionPhysicalProvider,
) -> None:
    observations, context = _inputs_for(approved, outside=True)
    result = project_scoped_observations(observations, context, approved)
    assert len(result.frames.samples) == 6
    point = next(s.projected_point for s in result.frames.samples if s.frame_id == 2)
    assert point is not None
    assert point.world_position == pytest.approx((10., 10., 0.))
    native = tuple(v / 2 for v in point.world_position)
    with pytest.raises(GeometryAuthorityError, match="UNION_OR_HOLE"):
        approved.validate_polyline((native, native))
    assert result.sidecar["clipping_or_snapping_applied"] is False
    assert result.sidecar["sample_rejection_count"] == 0


@pytest.mark.parametrize("field", ["ground_truth", "reference", "waypoints", "evaluation"])
def test_extra_context_or_observation_hidden_fields_are_rejected(
    approved: ScopedUnionPhysicalProvider, field: str,
) -> None:
    observations, context = _inputs_for(approved)
    changed_context = json.loads(context) | {field: []}
    with pytest.raises(ValidationError):
        project_scoped_observations(observations, _bytes(changed_context), approved)
    changed_observations = _bytes(json.loads(observations) | {field: []})
    changed_context = json.loads(context) | {
        "observations_sha256": hashlib.sha256(changed_observations).hexdigest(),
    }
    with pytest.raises(ValidationError):
        project_scoped_observations(changed_observations, _bytes(changed_context), approved)


@pytest.mark.parametrize("change", ["source", "scale", "authority", "camera", "landmark"])
def test_unapproved_source_scale_or_binding_changes_fail_closed(
    approved: ScopedUnionPhysicalProvider, change: str,
) -> None:
    observations, context = _inputs_for(approved)
    changed = json.loads(context)
    if change == "source":
        changed["source_sha256"] = "0" * 64
    elif change == "scale":
        changed["metres_per_blender_unit"] = 1.
    elif change == "authority":
        changed["authority"]["union_wkb_sha256"] = "0" * 64
    elif change == "camera":
        binding = changed["camera_bindings"][0]
        binding["camera"]["camera_to_world"][0][3] += .1
        binding["calibration_content_sha256"] = content_sha256(binding["camera"])
    else:
        changed["camera_bindings"][0]["landmark_offset_bu"][2] = .9
        changed["camera_bindings"][0]["projection_plane_point_bu"][2] = .9
    with pytest.raises(ValueError):
        project_scoped_observations(observations, _bytes(changed), approved)


def test_exact_byte_digest_and_intact_provider_are_required(
    approved: ScopedUnionPhysicalProvider,
) -> None:
    observations, context = _inputs_for(approved)
    with pytest.raises(ValueError, match="SHA256"):
        project_scoped_observations(observations + b" ", context, approved)
    with pytest.raises(TypeError, match="exact observations/context bytes"):
        project_scoped_observations(json.loads(observations), context, approved)
    bare_certificate: Any = approved.certificate
    with pytest.raises(TypeError, match="intact approved union"):
        project_scoped_observations(observations, context, bare_certificate)


def test_reordered_input_retains_the_same_projection_population_and_selection(
    approved: ScopedUnionPhysicalProvider,
) -> None:
    observations, context = _inputs_for(approved)
    expected = project_scoped_observations(observations, context, approved)
    document = json.loads(observations)
    document["frames"].reverse()
    reordered = _bytes(document)
    context_document = json.loads(context)
    context_document["observations_sha256"] = hashlib.sha256(reordered).hexdigest()
    actual = project_scoped_observations(reordered, _bytes(context_document), approved)
    def comparable(result: Any) -> list[dict[str, Any]]:
        frames = result.frames.model_dump(mode="json")["samples"]
        for frame in frames:
            point = frame["projected_point"]
            if point is not None and point["plane_id"] == NO_PLANE:
                # The unchanged producer intentionally binds pair IDs to the
                # exact observations-file digest, which changed with byte order.
                point.pop("point_id")
        return frames

    assert comparable(actual) == comparable(expected)
    assert actual.sidecar["rows"][0]["selected_multiview_hypothesis_id"] != (
        expected.sidecar["rows"][0]["selected_multiview_hypothesis_id"]
    )
    assert [(r["method"], r["selected_camera_ids"], r["selected_world_position"])
            for r in actual.sidecar["rows"]] == [
        (r["method"], r["selected_camera_ids"], r["selected_world_position"])
        for r in expected.sidecar["rows"]
    ]

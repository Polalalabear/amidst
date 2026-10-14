"""Independent source-binding and HOLD tests on synthetic approved geometry only."""

from types import SimpleNamespace
from typing import Any

import pytest
from test_physical_collision import _numerics
from test_reviewed_collision import _bound_provider
from test_scoped_authority import _decision, _inputs

from amidst.benchmark.baselines import BaselineUnavailableError
from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.observation import ProjectedPoint
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.stream import RawProjectedFrameSample, StreamBinding
from amidst.domain.topology import CameraTransition, CameraTransitionType
from amidst.domain.trajectory import TerminationReason
from amidst.finalization.formal_route_inventory import build_scoped_visibility_network
from amidst.finalization.reviewed_collision import collision_bundle_from_provider
from amidst.finalization.scoped_authority import (
    ScopeCameraLandmarkBinding,
    ScopedUnionPhysicalProvider,
    apply_scope_approval,
    load_scoped_authority,
)
from amidst.finalization.scoped_class_search import produce_scoped_class_candidates
from amidst.finalization.scoped_inference import (
    ScopedBudgetLineage,
    ScopedInferenceConfig,
    bind_scoped_gaps,
    build_scoped_case_pipeline,
    build_scoped_navigation,
    run_scoped_baseline,
)
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256


@pytest.fixture(scope="module")
def approved() -> tuple[ScopedUnionPhysicalProvider, ScopedInferenceConfig, StreamBinding]:
    proposal, evidence, contract, numerics = _inputs()
    camera = Camera(
        camera_id="SYNTHETIC_SOURCE_CAMERA",
        camera_to_world=(
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 3.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
        fx=100.0,
        fy=100.0,
        cx=50.0,
        cy=50.0,
        width=100,
        height=100,
        floor_id="1F",
    )
    camera_two = camera.model_copy(
        update={
            "camera_id": "SYNTHETIC_SOURCE_CAMERA_2",
            "camera_to_world": (
                (1.0, 0.0, 0.0, 1.0),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 3.0),
                (0.0, 0.0, 0.0, 1.0),
            ),
        }
    )
    export = {
        "source_sha256": proposal.pins.source_sha256,
        "cameras": [item.model_dump(mode="json") for item in (camera, camera_two)],
    }
    camera_bindings = tuple(
        ScopeCameraLandmarkBinding(
            camera=item,
            calibration_content_sha256=content_sha256(item.model_dump(mode="json")),
            source_camera_export_content_sha256=content_sha256(export),
            floor_id="1F",
            landmark_offset_bu=(0.0, 0.0, 1.0),
            projection_plane_point_bu=(0.0, 0.0, 1.0),
        )
        for item in (camera, camera_two)
    )
    proposal = proposal.model_copy(
        update={
            "pins": proposal.pins.model_copy(
                update={"camera_export_content_sha256": content_sha256(export)}
            ),
            "camera_landmark_bindings": camera_bindings,
            "requested_projection_authority": True,
        }
    )
    decision = _decision(proposal)
    certificate, detail = apply_scope_approval(
        proposal,
        decision,
        evidence,
        contract,
        numerics,
        expected_pins=proposal.pins,
        expected_proposal_content_sha256=content_sha256(proposal.model_dump(mode="json")),
        expected_decision_content_sha256=content_sha256(decision.model_dump(mode="json")),
        camera_export=export,
    )
    assert certificate is not None, detail
    provider = load_scoped_authority(
        proposal,
        decision,
        certificate,
        evidence,
        contract,
        numerics,
        expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
        camera_export=export,
    )
    authority = ScopedRouteAuthorityBinding(
        pins=proposal.pins,
        proposal_content_sha256=certificate.proposal_content_sha256,
        decision_content_sha256=certificate.human_decision_content_sha256,
        certificate_content_sha256=provider.certificate_content_sha256,
        union_wkb_sha256=certificate.union_wkb_sha256,
    )
    policy = GraphSearchPolicy(
        max_candidate_paths=3,
        max_search_nodes=1000,
        max_path_length_m=30.0,
        max_search_time_s=10.0,
        max_branch_factor=32,
        max_detour_ratio=2.0,
    )
    config = ScopedInferenceConfig(
        authority=authority,
        fresh_export_config_sha256="c" * 64,
        source_camera_plane_ids={
            item.camera_id: "synthetic-pinned-landmark-plane" for item in (camera, camera_two)
        },
        metres_per_blender_unit=contract.scale.metres_per_blender_unit,
        movement=MovementConstraints(max_speed_m_s=2.0),
        search_policy=policy,
        budget_lineage=ScopedBudgetLineage(
            parent_inference_lock_content_sha256="d" * 64, parent_search_policy=policy
        ),
    )
    binding = StreamBinding(
        source_id="synthetic-fresh-source",
        spatial_context_id="synthetic-fresh-context",
        source_asset_sha256=provider.source_sha256,
    )
    return provider, config, binding


def _samples(
    binding: StreamBinding, *, three_segments: bool = True
) -> tuple[RawProjectedFrameSample, ...]:
    positions = {0: (2.25, 2.25, 0.0), 2: (4.0, 2.25, 0.0), 4: (7.75, 2.25, 0.0)}
    if not three_segments:
        positions = {0: (2.25, 5.0, 0.0), 4: (7.75, 5.0, 0.0)}
    values = []
    for index in range(5):
        common = dict(
            sample_id=f"source-frame-{index}",
            **binding.model_dump(mode="python"),
            target_id="source-target",
            camera_id="SYNTHETIC_SOURCE_CAMERA",
            timestamp=float(index * 5),
            frame_id=index,
        )
        if index in positions:
            values.append(
                RawProjectedFrameSample(
                    **common,
                    uv=(50.0, 50.0),
                    visibility=VisibilityStatus.OBSERVED,
                    provenance=Provenance.OBSERVED,
                    projected_point=ProjectedPoint(
                        point_id=f"source-projected-{index}",
                        camera_id="SYNTHETIC_SOURCE_CAMERA",
                        plane_id="synthetic-pinned-landmark-plane",
                        timestamp=float(index * 5),
                        world_position=positions[index],
                        floor_id="1F",
                    ),
                )
            )
        else:
            values.append(
                RawProjectedFrameSample(
                    **common,
                    uv=None,
                    visibility=VisibilityStatus.GAP,
                    provenance=None,
                    gap_reason=GapReason.GEOMETRY_UNCERTAIN,
                )
            )
    return tuple(values)


def test_visible_recovery_creates_two_independent_hold_gaps_and_preserves_every_sample(
    approved: Any,
) -> None:
    provider, config, binding = approved
    samples = _samples(binding)
    aggregation = aggregate_frames(samples, config.aggregation_policy)
    gaps = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)
    assert len(gaps) == 2
    assert gaps[0].end == gaps[1].start
    assert gaps[0].interior_gap_sample_ids == ("source-frame-1",)
    assert gaps[1].interior_gap_sample_ids == ("source-frame-3",)
    assert len(aggregation.samples) == 5
    assert all(gap.camera_handoffs == 0 and gap.ground_truth_read is False for gap in gaps)


def test_same_camera_consumer_uses_actual_camera_without_a_self_transition_or_alias(
    approved: Any,
) -> None:
    provider, config, binding = approved
    aggregation = aggregate_frames(_samples(binding), config.aggregation_policy)
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[0]
    navigation = build_scoped_navigation(gap, provider, config)
    pipeline = build_scoped_case_pipeline(gap, navigation, provider, config)
    assert [node.camera_id for node in pipeline.topology.nodes] == ["SYNTHETIC_SOURCE_CAMERA"]
    assert pipeline.topology.transitions == ()
    run = run_scoped_baseline(
        gap,
        navigation,
        "spatiotemporal",
        aggregation=aggregation,
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        clock=lambda: 0.0,
    )
    assert run.core_factors.camera_topology_filter is False
    assert run.topology_constraint == "SOURCE_BOUND_SAME_CAMERA_HOLD"
    assert run.bound_gap.start == gap.start and run.bound_gap.end == gap.end
    assert run.timed_result.candidates
    assert all(
        "SOURCE_BOUND_SAME_CAMERA_HOLD" in c.feasibility_flags for c in run.timed_result.candidates
    )
    assert all(
        "TOPOLOGY_AUTHORIZED" not in c.feasibility_flags for c in run.timed_result.candidates
    )
    assert run.case_protocol_readiness_claimed is False
    assert run.continuous_source_route_classes_exhaustive is False


def test_core_same_camera_transition_rejection_is_unchanged() -> None:
    with pytest.raises(ValueError, match="same-camera transitions"):
        CameraTransition(
            transition_id="not-a-handoff",
            from_camera_id="REAL_SOURCE_CAMERA",
            to_camera_id="REAL_SOURCE_CAMERA",
            transition_type=CameraTransitionType.ADJACENT,
            navigation_from_node_id="a",
            navigation_to_node_id="b",
            navigation_edge_ids=("edge",),
        )


def test_source_hole_is_never_replaced_with_endpoint_shortcut(approved: Any) -> None:
    provider, config, binding = approved
    aggregation = aggregate_frames(
        _samples(binding, three_segments=False), config.aggregation_policy
    )
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[0]
    navigation = build_scoped_navigation(gap, provider, config)
    for polyline in navigation.source_edge_polylines_bu.values():
        assert provider.validate_polyline(polyline)
    direct = (navigation.endpoint_positions_bu[0], navigation.endpoint_positions_bu[1])
    assert direct not in navigation.source_edge_polylines_bu.values()


@pytest.mark.parametrize(
    "field",
    [
        "proposal_content_sha256",
        "decision_content_sha256",
        "certificate_content_sha256",
        "union_wkb_sha256",
    ],
)
def test_authority_hash_substitution_refused_before_any_gap_claim(
    approved: Any, field: str
) -> None:
    provider, config, binding = approved
    changed = config.model_copy(
        update={"authority": config.authority.model_copy(update={field: "f" * 64})}
    )
    with pytest.raises(ValueError, match="pins differ"):
        bind_scoped_gaps(
            aggregate_frames(_samples(binding)), provider, changed, expected_stream_binding=binding
        )


def test_wrong_raw_source_or_camera_plane_refused(approved: Any) -> None:
    provider, config, binding = approved
    foreign = binding.model_copy(update={"source_id": "another-source"})
    with pytest.raises(ValueError, match="source/context binding"):
        bind_scoped_gaps(
            aggregate_frames(_samples(foreign)), provider, config, expected_stream_binding=binding
        )
    changed = config.model_copy(
        update={
            "source_camera_plane_ids": config.source_camera_plane_ids
            | {
                "SYNTHETIC_SOURCE_CAMERA": "alias-plane",
            }
        }
    )
    with pytest.raises(ValueError, match="plane/floor"):
        bind_scoped_gaps(
            aggregate_frames(_samples(binding)), provider, changed, expected_stream_binding=binding
        )


def test_sparse_timestamp_hole_without_gap_marker_is_not_invented_evidence(approved: Any) -> None:
    provider, config, binding = approved
    samples = tuple(
        sample for sample in _samples(binding) if sample.visibility == VisibilityStatus.OBSERVED
    )
    # Canonical aggregation of sparse visible samples retains one segment under
    # its default no-threshold policy, so there is no source GAP to consume.
    assert (
        bind_scoped_gaps(
            aggregate_frames(samples), provider, config, expected_stream_binding=binding
        )
        == ()
    )


def test_unbound_gap_receipt_cannot_merge_two_gaps_over_visible_recovery(approved: Any) -> None:
    provider, config, binding = approved
    aggregation = aggregate_frames(_samples(binding))
    gaps = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)
    merged = gaps[0].model_copy(
        update={"end": gaps[1].end, "interior_gap_sample_ids": ("source-frame-1", "source-frame-3")}
    )
    navigation = build_scoped_navigation(merged, provider, config)
    with pytest.raises(ValueError, match="fresh source aggregation"):
        run_scoped_baseline(
            merged,
            navigation,
            "spatiotemporal",
            aggregation=aggregation,
            provider=provider,
            config=config,
            frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        )


@pytest.mark.parametrize("ablation", ["remove_topology", "remove_collision"])
def test_unavailable_factor_ablation_cannot_remove_source_binding_or_union_body_guard(
    approved: Any,
    ablation: str,
) -> None:
    provider, config, binding = approved
    aggregation = aggregate_frames(_samples(binding))
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[0]
    with pytest.raises(BaselineUnavailableError):
        run_scoped_baseline(
            gap,
            build_scoped_navigation(gap, provider, config),
            "spatiotemporal",
            aggregation=aggregation,
            provider=provider,
            config=config,
            frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
            ablation_id=ablation,
        )


def test_budget_change_requires_exact_parent_lineage(approved: Any) -> None:
    _, config, _ = approved
    changed = config.model_dump(mode="python")
    changed["search_policy"] = config.search_policy.model_copy(update={"max_branch_factor": 3})
    with pytest.raises(ValueError, match="budget differs"):
        ScopedInferenceConfig.model_validate(changed)
    changed["budget_lineage"] = config.budget_lineage.model_copy(
        update={
            "changed_search_fields": ("max_branch_factor",),
            "change_reason": "frozen test stress schedule",
        }
    )
    assert ScopedInferenceConfig.model_validate(changed).search_policy.max_branch_factor == 3


def test_raw_core_branch_budget_termination_is_preserved(approved: Any) -> None:
    provider, config, binding = approved
    policy = config.search_policy.model_copy(update={"max_branch_factor": 1})
    config = ScopedInferenceConfig.model_validate(
        config.model_dump(mode="python")
        | {
            "search_policy": policy,
            "budget_lineage": config.budget_lineage.model_copy(
                update={
                    "changed_search_fields": ("max_branch_factor",),
                    "change_reason": "synthetic stress fixture",
                }
            ),
        }
    )
    aggregation = aggregate_frames(_samples(binding))
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[0]
    run = run_scoped_baseline(
        gap,
        build_scoped_navigation(gap, provider, config),
        "spatiotemporal",
        aggregation=aggregation,
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        clock=lambda: 0.0,
    )
    assert run.timed_result.termination_reason == TerminationReason.MAX_BRANCH_FACTOR
    assert run.timed_result.complete is False
    assert not run.timed_result.candidates


def test_known_collision_ablation_preserves_intact_union_and_receipt(approved: Any) -> None:
    provider, config, binding = approved
    config = ScopedInferenceConfig.model_validate(
        config.model_dump(mode="python")
        | {
            "search_policy": config.search_policy.model_copy(update={"max_search_nodes": 24}),
            "budget_lineage": config.budget_lineage.model_copy(
                update={
                    "changed_search_fields": ("max_search_nodes",),
                    "change_reason": "bounded known-collision rejection fixture",
                }
            ),
        }
    )
    synthetic_authority = SimpleNamespace(source_sha256=provider.source_sha256, provider=provider)
    bundle = collision_bundle_from_provider(
        _bound_provider(synthetic_authority),
        provider.contract,
        _numerics(),
        floor_ids=("1F",),
        manifest_sha256="a" * 64,
        local_certificate_content_sha256=provider.certificate_content_sha256,
        semantic_receipt_content_sha256=provider.semantic_review_content_sha256,
    )
    samples = tuple(
        sample.model_copy(
            update={
                "projected_point": sample.projected_point.model_copy(
                    update={
                        "world_position": (4.75 if sample.frame_id == 2 else 5.25, 2.25, 0.0),
                    }
                )
            }
        )
        if sample.frame_id in {2, 4} and sample.projected_point is not None
        else sample
        for sample in _samples(binding)
    )
    aggregation = aggregate_frames(samples)
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[1]
    navigation = build_scoped_navigation(gap, provider, config)
    common = dict(
        aggregation=aggregation,
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        collision_bundle=bundle,
        clock=lambda: 0.0,
    )
    applied = run_scoped_baseline(gap, navigation, "spatiotemporal", **common)
    removed = run_scoped_baseline(
        gap, navigation, "spatiotemporal", ablation_id="remove_collision", **common
    )
    assert applied.collision_filter_enabled is True
    assert any(record.state == "REJECTED" for record in applied.physical_records)
    assert removed.collision_filter_enabled is False
    assert removed.collision_filter_status == "AVAILABLE"
    assert removed.collision_consumer_receipt == applied.collision_consumer_receipt
    assert removed.timed_result.candidates
    for candidate in removed.timed_result.candidates:
        assert provider.validate_polyline(candidate.polyline)


def _multiview_samples_and_sidecar(approved: Any) -> tuple[Any, dict[str, Any]]:
    provider, _, binding = approved
    samples = tuple(
        sample.model_copy(
            update={
                "projected_point": sample.projected_point.model_copy(
                    update={
                        "plane_id": "EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION",
                    }
                ),
            }
        )
        if sample.projected_point is not None
        else sample
        for sample in _samples(binding)
    )
    calibration_sha = content_sha256(
        [
            item.camera.model_dump(mode="json")
            for item in sorted(
                provider.proposal.camera_landmark_bindings, key=lambda item: item.camera.camera_id
            )
        ]
    )
    rows = []
    for sample in samples:
        if sample.projected_point is None:
            continue
        p = sample.projected_point.world_position
        rows.append(
            {
                "timestamp": sample.timestamp,
                "frame_id": sample.frame_id,
                "target_id": sample.target_id,
                "source_id": binding.source_id,
                "spatial_context_id": binding.spatial_context_id,
                "source_asset_sha256": provider.source_sha256,
                "observations_sha256": "9" * 64,
                "camera_calibration_sha256": calibration_sha,
                "method": "EXACT_TIME_MULTIVIEW",
                "ground_truth_read": False,
                "selection_uses_ground_truth": False,
                "selected_camera_ids": ["SYNTHETIC_SOURCE_CAMERA", "SYNTHETIC_SOURCE_CAMERA_2"],
                "selected_world_position": [p[0], p[1], p[2] + 1.0],
                "input_evidence": [
                    {
                        "camera_id": identity,
                        "timestamp": sample.timestamp,
                        "frame_id": sample.frame_id,
                        "target_id": sample.target_id,
                        "status": "OBSERVED",
                        "point_2d": list(sample.uv),
                    }
                    for identity in ("SYNTHETIC_SOURCE_CAMERA", "SYNTHETIC_SOURCE_CAMERA_2")
                ],
            }
        )
    return samples, {
        "source_asset_sha256": provider.source_sha256,
        "observations_sha256": "9" * 64,
        "ground_truth_read": False,
        "rows": rows,
    }


def test_exact_time_no_plane_literal_requires_and_preserves_source_projection_receipt(
    approved: Any,
) -> None:
    provider, config, binding = approved
    samples, sidecar = _multiview_samples_and_sidecar(approved)
    aggregation = aggregate_frames(samples)
    with pytest.raises(ValueError, match="projection sidecar"):
        bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)
    gaps = bind_scoped_gaps(
        aggregation,
        provider,
        config,
        expected_stream_binding=binding,
        projection_sidecar=sidecar,
        projection_observations_sha256="9" * 64,
    )
    assert len(gaps) == 2
    assert gaps[0].start.observation.projected_path[-1].plane_id == (
        "EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION"
    )
    assert gaps[0].projection_sidecar_content_sha256 == content_sha256(sidecar)


@pytest.mark.parametrize("changed", ["gt", "camera", "pixels", "time", "calibration"])
def test_no_plane_sidecar_cannot_fabricate_multiview_source_evidence(
    approved: Any,
    changed: str,
) -> None:
    provider, config, binding = approved
    samples, sidecar = _multiview_samples_and_sidecar(approved)
    row = sidecar["rows"][0]
    if changed == "gt":
        row["selection_uses_ground_truth"] = True
    elif changed == "camera":
        row["selected_camera_ids"] = ["SYNTHETIC_SOURCE_CAMERA", "FABRICATED_CAMERA_ALIAS"]
    elif changed == "pixels":
        row["input_evidence"][0]["point_2d"] = [51.0, 50.0]
    elif changed == "time":
        row["timestamp"] = 0.1
    else:
        row["camera_calibration_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="multiview"):
        bind_scoped_gaps(
            aggregate_frames(samples),
            provider,
            config,
            expected_stream_binding=binding,
            projection_sidecar=sidecar,
            projection_observations_sha256="9" * 64,
        )


def test_production_class_transport_preserves_actual_camera_and_class_lineage(
    approved: Any,
) -> None:
    provider, config, binding = approved
    aggregation = aggregate_frames(_samples(binding, three_segments=False))
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[0]
    navigation = build_scoped_navigation(gap, provider, config)
    network, mapping = build_scoped_visibility_network(
        provider,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_ids=(gap.start.observation.camera_id,),
        spatial_context_id=binding.spatial_context_id,
    )
    classes = produce_scoped_class_candidates(
        provider,
        network,
        mapping,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_id=gap.start.observation.camera_id,
        gap_duration_s=20.0,
        movement=config.movement,
        policy=config.search_policy,
        clock=lambda: 0.0,
    )
    run = run_scoped_baseline(
        gap,
        navigation,
        "spatiotemporal",
        aggregation=aggregation,
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        class_candidates=classes,
        clock=lambda: 0.0,
    )
    assert run.production_class_search == classes
    assert run.class_generation_complete == classes.complete
    assert run.class_selection_truncated == (len(classes.classes) > run.requested_k)
    assert run.macro_navigation_content_sha256 is not None
    assert run.camera_handoffs == 0
    assert run.timed_result.candidates
    forged = classes.model_copy(
        update={
            "classes": (
                classes.classes[0].model_copy(
                    update={
                        "winding_signature": classes.classes[0].winding_signature + 100,
                    }
                ),
                *classes.classes[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="actual source winding"):
        run_scoped_baseline(
            gap,
            navigation,
            "spatiotemporal",
            aggregation=aggregation,
            provider=provider,
            config=config,
            frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
            class_candidates=forged,
            clock=lambda: 0.0,
        )
    # A consumer of the wrong query/factor cannot substitute labels even when
    # endpoints happen to match. The independently generated mask remains bound.
    with pytest.raises(ValueError, match="source/GAP/budget/factors"):
        run_scoped_baseline(
            gap,
            navigation,
            "spatiotemporal",
            aggregation=aggregation,
            provider=provider,
            config=config,
            frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
            class_candidates=classes,
            ablation_id="remove_travel_time",
            clock=lambda: 0.0,
        )

"""Evaluation boundaries and independent populations on synthetic source fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_physical_collision import _numerics
from test_reviewed_collision import _bound_provider
from test_scoped_inference import _samples
from test_scoped_inference import approved as scoped_approved

from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.metric_config import MetricConfig
from amidst.finalization.formal_route_inventory import (
    build_scoped_visibility_network,
    enumerate_visibility_route_classes,
)
from amidst.finalization.reviewed_collision import collision_bundle_from_provider
from amidst.finalization.reviewed_pipeline import freeze_inference
from amidst.finalization.reviewed_reference_movement import (
    EXPECTED_PROPOSAL,
    POLICY_ID,
    ReferenceMovementApproval,
    build_reference_annotation_document,
    reference_content_sha256,
)
from amidst.finalization.scoped_class_search import produce_scoped_class_candidates
from amidst.finalization.scoped_evaluation import evaluate_scoped_run
from amidst.finalization.scoped_inference import (
    bind_scoped_gaps,
    build_scoped_navigation,
    run_scoped_baseline,
)
from amidst.finalization.source_class_eligibility import (
    certify_source_class_eligibility_intervals,
)
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.scene_geometry import SceneGeometrySnapshot


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def _reference_approval(provider: Any) -> ReferenceMovementApproval:
    pins = provider.certificate.pins
    receipt = {
        "schema_version": "phase1-reference-movement-approval-v1",
        "decision": "APPROVE",
        "policy_id": POLICY_ID,
        "human_approval_id": "SYNTHETIC_TEST_ONLY_NOT_SCHOOL_APPROVAL",
        "human_approval_text": "SYNTHETIC_REFERENCE_POLICY_FIXTURE_ONLY",
        "approved_at": "2026-10-07T15:35:00Z",
        "locked_before_simulation_and_evaluation": True,
        "original_hr01_hr04_profiles_modified": False,
        "old_results_relabelled": False,
        "source_sha256": provider.source_sha256,
        "protocol_sha256": pins.protocol_sha256,
        "original_human_decisions_sha256": pins.original_human_decisions_sha256,
        "proposal_file_sha256": "c" * 64,
        "proposal_content_sha256": reference_content_sha256(EXPECTED_PROPOSAL),
    }
    result = ReferenceMovementApproval(
        receipt_json=json.dumps(receipt),
        receipt_content_sha256=reference_content_sha256(receipt),
        proposal_file_sha256=receipt["proposal_file_sha256"],
        proposal_content_sha256=receipt["proposal_content_sha256"],
        source_sha256=provider.source_sha256,
        protocol_sha256=pins.protocol_sha256,
        original_human_decisions_sha256=pins.original_human_decisions_sha256,
    )
    result.validate()
    return result


def _collision_bundle(provider: Any) -> Any:
    original = _bound_provider(
        SimpleNamespace(source_sha256=provider.source_sha256, provider=provider)
    )
    document = original.geometry.model_dump(mode="json")
    for surface in document["surfaces"]:
        for point in surface["vertices"]:
            point[0] -= 2.0  # x=3 cuts the independently tested route x=2.25→4.
    geometry = SceneGeometrySnapshot.model_validate_json(json.dumps(document))
    geometry_sha = canonical_geometry_sha256(geometry)
    resolution = PhysicalAuthorityResolution.model_validate_json(
        json.dumps(
            original.resolution.model_dump(mode="json") | {"geometry_sha256": geometry_sha},
        )
    )
    consumer = ReadOnlyPhysicalAuthorityProvider(
        geometry,
        resolution,
        provider.source_sha256,
        geometry_sha,
    )
    return collision_bundle_from_provider(
        consumer,
        provider.contract,
        _numerics(),
        floor_ids=("1F",),
        manifest_sha256="a" * 64,
        local_certificate_content_sha256=provider.certificate_content_sha256,
        semantic_receipt_content_sha256=provider.semantic_review_content_sha256,
    )


@pytest.fixture(scope="module")
def inputs() -> dict[str, Any]:
    provider, config, binding = scoped_approved.__wrapped__()
    frames = FrameSampleDataset(samples=_samples(binding))
    aggregation = aggregate_frames(frames.samples, config.aggregation_policy)
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[0]
    navigation = build_scoped_navigation(gap, provider, config)
    run = run_scoped_baseline(
        gap,
        navigation,
        "shortest_path",
        aggregation=aggregation,
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        clock=lambda: 0.0,
    )
    network, _ = build_scoped_visibility_network(
        provider,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_ids=(gap.start.observation.camera_id,),
        spatial_context_id=binding.spatial_context_id,
    )
    inventory = enumerate_visibility_route_classes(
        provider,
        network,
        navigation.source_edge_polylines_bu,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_id=gap.start.observation.camera_id,
        gap_duration_s=10.0,
        movement=config.movement,
        policy=config.search_policy,
        travel_time_filter=False,
        clock=lambda: 0.0,
    )
    sidecar = {
        "ground_truth_read": False,
        "source_asset_sha256": provider.source_sha256,
        "observations_sha256": "b" * 64,
        "authority": config.authority.model_dump(mode="json"),
        "frames_content_sha256": content_sha256(frames.model_dump(mode="json")),
        "config_file_sha256": config.fresh_export_config_sha256,
        "camera_bindings": [
            b.model_dump(mode="json") for b in provider.proposal.camera_landmark_bindings
        ],
        "rows": [
            {
                "timestamp": s.timestamp,
                "selected_world_position": None
                if s.projected_point is None
                else (
                    s.projected_point.world_position[0],
                    s.projected_point.world_position[1],
                    s.projected_point.world_position[2] + 1.0,
                ),
            }
            for s in frames.samples
        ],
    }
    a, b, c = (2.25, 2.25, 0.0), (4.0, 2.25, 0.0), (7.75, 2.25, 0.0)
    samples = []
    for index in range(101):
        time = index / 5.0
        if time <= 9.125:
            position = a
        elif time <= 10.0:
            position = tuple(
                x + (time - 9.125) / 0.875 * (y - x) for x, y in zip(a, b, strict=True)
            )
        else:
            position = tuple(x + (time - 10.0) / 10.0 * (y - x) for x, y in zip(b, c, strict=True))
        samples.append({"timestamp": time, "position": position, "floor_id": "1F"})
    truth = {
        "provenance": "GROUND_TRUTH",
        "source_sha256": provider.source_sha256,
        "spatial_context_id": binding.spatial_context_id,
        "target_id": run.event.target_id,
        "coordinate_units": "BLENDER_NATIVE_UNITS",
        "samples": samples,
    }
    approval = _reference_approval(provider)
    annotations = build_reference_annotation_document(
        [
            {"timestamp": 0.0, "position": a},
            {"timestamp": 9.125, "position": a},
            {"timestamp": 10.0, "position": b},
            {"timestamp": 20.0, "position": c},
        ],
        approval,
        target_id=run.event.target_id,
        trajectory_id="synthetic-reference",
        dataset_version="SYNTHETIC_FRESH_EVALUATION_ONLY",
    )
    metrics = MetricConfig(k_values=(1, 2, 3), coverage_epsilon_m=0.5, collision_tolerance_m=0.001)
    return dict(
        provider=provider,
        config=config,
        frames=frames,
        navigation=navigation,
        run=run,
        inventory=inventory,
        sidecar=sidecar,
        truth=truth,
        approval=approval,
        annotations=annotations,
        metric_config=metrics,
        aggregation=aggregation,
    )


def _freeze(
    inputs: dict[str, Any],
    directory: Path,
    *,
    run: Any = None,
    inventory: Any = None,
    source_eligibility: Any = None,
) -> dict[str, str]:
    directory.mkdir()
    values = {
        "run": (run or inputs["run"]).model_dump(mode="json"),
        "inventory": (inventory or inputs["inventory"]).model_dump(mode="json"),
        "projection": inputs["sidecar"],
        "config": inputs["config"].model_dump(mode="json"),
        "navigation": inputs["navigation"].model_dump(mode="json"),
        "frames": inputs["frames"].model_dump(mode="json"),
        "metrics": inputs["metric_config"].model_dump(mode="json"),
    }
    if source_eligibility is not None:
        values["source_eligibility"] = source_eligibility.model_dump(mode="json")
    paths = {}
    for role, value in values.items():
        paths[role] = role + ".json"
        (directory / paths[role]).write_bytes(_bytes(value))
    freeze_inference(directory, dataset_manifest_sha256="a" * 64, config_sha256="b" * 64)
    return paths


def _evaluate(
    inputs: dict[str, Any], directory: Path, paths: dict[str, str], **changes: Any
) -> dict[str, Any]:
    arguments = dict(
        run=inputs["run"],
        truth_loader=lambda: _bytes(inputs["truth"]),
        sidecar=inputs["sidecar"],
        inventory=inputs["inventory"],
        metric_config=inputs["metric_config"],
        provider=inputs["provider"],
        inference_directory=directory,
        frozen_input_paths=paths,
        config=inputs["config"],
        navigation=inputs["navigation"],
        frames=inputs["frames"],
        dataset_version="SYNTHETIC_FRESH_EVALUATION_ONLY",
        runtime_s=0.01,
        annotations_loader=lambda: _bytes(inputs["annotations"]),
        reference_approval=inputs["approval"],
    )
    arguments.update(changes)
    return evaluate_scoped_run(**arguments)


def _source_certificate(inputs: dict[str, Any]) -> Any:
    provider, config = inputs["provider"], inputs["config"]
    run, navigation = inputs["run"], inputs["navigation"]
    network, _ = build_scoped_visibility_network(
        provider,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_ids=(run.gap_binding.start.observation.camera_id,),
        spatial_context_id=run.gap_binding.binding.spatial_context_id,
    )
    return certify_source_class_eligibility_intervals(
        provider,
        network,
        navigation.source_edge_polylines_bu,
        expected_binding=run.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_id=run.gap_binding.start.observation.camera_id,
        gap_duration_s=run.event.time_range[1] - run.event.time_range[0],
        movement=config.movement,
        policy=config.search_policy,
        travel_time_filter=run.core_factors.travel_time_filter,
        clock=lambda: 0.0,
    )


def test_source_interval_denominator_requires_frozen_query_and_independent_regeneration(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    certificate = _source_certificate(inputs)
    assert certificate.recall_denominator_complete is True
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory, source_eligibility=certificate)
    result = _evaluate(inputs, directory, paths, source_eligibility=certificate)
    assert result["feasible_candidate_recall"] == 1.0
    assert result["source_eligible_class_count"] == certificate.source_eligible_class_count
    assert result["source_recall_population"] == certificate.population_scope
    assert result["source_metric_cover_scope"] == certificate.metric_cover_scope
    assert result["source_eligibility_content_sha256"] == content_sha256(
        certificate.model_dump(mode="json")
    )


def test_changed_source_interval_query_is_rejected_before_reference_loader(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    certificate = _source_certificate(inputs).model_copy(
        update={"query_content_sha256": "f" * 64},
    )
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory, source_eligibility=certificate)
    calls = []

    def hidden() -> bytes:
        calls.append("reference-opened")
        raise AssertionError("GT must remain unopened on a mismatched source query")

    with pytest.raises(ValueError, match="authority/query/endpoint/factor pins differ"):
        _evaluate(
            inputs,
            directory,
            paths,
            source_eligibility=certificate,
            truth_loader=hidden,
            annotations_loader=hidden,
        )
    assert calls == []


def test_truncated_inventory_still_requires_its_actual_frozen_source_query(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    inventory = inputs["inventory"].model_copy(
        update={
            "complete": False,
            "termination_reason": "MAX_EXPANDED_STATES",
            "declared_graph_class_inventory_exhaustive": False,
            "source_route_class_inventory_exhaustive": False,
            "query_content_sha256": "f" * 64,
        }
    )
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory, inventory=inventory)
    calls = []

    def hidden() -> bytes:
        calls.append("reference-opened")
        raise AssertionError("incomplete inventories still require the actual source query")

    with pytest.raises(ValueError, match="source/geometry/actual eligibility differs"):
        _evaluate(inputs, directory, paths, inventory=inventory, truth_loader=hidden)
    assert calls == []


def test_gt_and_annotation_loaders_are_unopened_when_freeze_is_missing_or_changed(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory)
    (directory / "run.json").write_text("{}\n")
    calls = []

    def hidden() -> bytes:
        calls.append("hidden-reference-opened")
        raise AssertionError("GT must remain unopened on a failed freeze")

    with pytest.raises(ValueError, match="changed after freeze"):
        _evaluate(inputs, directory, paths, truth_loader=hidden, annotations_loader=hidden)
    assert calls == []


def test_first_timing_remains_primary_when_reference_prefers_dwell_and_k_is_distinct_routes(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory)
    result = _evaluate(inputs, directory, paths)
    event = inputs["run"].event
    assert len(event.candidates) == 1 and len(event.trajectories) == 2
    assert result["ade_m"] > 0.5
    assert result["travel_time_error_s"] == pytest.approx(9.125)
    assert result["primary_hypothesis_id"] == event.trajectories[0].hypothesis_id
    scored = result["computation_result"]["evaluations"][0]["trajectory_metrics"]
    assert scored[1]["ade_m"] < 1e-10
    assert all(row["coverage_at_k"] is False for row in result["metrics_at_k"].values())
    assert all(
        row["selected_route_count"] == 1 for row in result["computation_result"]["evaluations"]
    )
    assert result["primary_selection_uses_ground_truth"] is False
    assert result["metric_config"]["formal_benchmark_status"] == "UNRESOLVED"


def test_projection_uses_dynamic_binding_and_all_timing_body_segments_are_counted(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory)
    result = _evaluate(inputs, directory, paths)
    assert result["projection_error_sample_count"] == 3
    assert result["projection_error_population"] == "ALL_MATCHED_VISIBLE_PROJECTED_SOURCE_FRAMES"
    assert result["projection_error_m"] == pytest.approx(0.0, abs=1e-12)
    assert result["physical_segment_count"] == 3
    assert result["source_scope_violation_segment_count"] == 0
    # Complete body certificates cannot fabricate an independent collision result.
    assert result["collision_rate"] is None
    assert result["independent_collision_evaluator_retained"] is False
    assert result["impossible_transition_rate"] is None
    assert result["transition_count"] == 0
    assert result["same_camera_hold_status"].startswith("VALID_SOURCE_BOUND_HOLD")
    assert result["source_bound_hold_relation_count"] == 1
    assert result["source_bound_hold_relation_invalid_rate"] == 0.0
    assert result["actual_camera_handoff_count"] == 0
    assert result["camera_handoff_only_impossible_transition_rate"] is None
    relation = result["source_bound_hold_relation_inventory"]
    assert relation["candidate_outputs_used_to_build_inventory"] is False
    assert relation["core_self_transition_created"] is False


def test_independent_collision_evaluation_survives_remove_collision_and_includes_dwell(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    provider, config, navigation = inputs["provider"], inputs["config"], inputs["navigation"]
    collisions = _collision_bundle(provider)
    run = run_scoped_baseline(
        inputs["run"].gap_binding,
        navigation,
        "spatiotemporal",
        ablation_id="remove_collision",
        aggregation=inputs["aggregation"],
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        collision_bundle=collisions,
        clock=lambda: 0.0,
    )
    network, _ = build_scoped_visibility_network(
        provider,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_ids=(run.gap_binding.start.observation.camera_id,),
        spatial_context_id=run.gap_binding.binding.spatial_context_id,
    )
    inventory = enumerate_visibility_route_classes(
        provider,
        network,
        navigation.source_edge_polylines_bu,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_id=run.gap_binding.start.observation.camera_id,
        gap_duration_s=10.0,
        movement=config.movement,
        policy=config.search_policy,
        travel_time_filter=True,
        clock=lambda: 0.0,
    )
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory, run=run, inventory=inventory)
    result = _evaluate(
        inputs, directory, paths, run=run, inventory=inventory, collision_bundle=collisions
    )
    assert result["inference_collision_filter_enabled"] is False
    assert result["independent_collision_evaluator_retained"] is True
    assert result["collision_segment_count"] > 0
    assert result["collision_rate"] > 0
    assert result["constraint_violation_rate"] > 0
    assert result["known_collision_evaluation"]["segment_count"] == result["physical_segment_count"]
    assert result["known_collision_evaluation"]["tested_triangles"] > 0


def test_truncated_denominator_is_na_and_never_becomes_predictions(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    inventory = inputs["inventory"].model_copy(
        update={
            "complete": False,
            "termination_reason": "MAX_EXPANDED_STATES",
            "declared_graph_class_inventory_exhaustive": False,
            "source_route_class_inventory_exhaustive": False,
        }
    )
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory, inventory=inventory)
    result = _evaluate(inputs, directory, paths, inventory=inventory)
    assert result["feasible_candidate_recall"] is None
    assert result["feasible_candidate_recall_denominator"] is None
    assert result["feasible_candidate_recall_status"] == "N/A_TRUNCATED_INDEPENDENT_INVENTORY"
    assert result["oracle_routes_used_as_predictions"] is False
    assert result["candidate_count"] == len(inputs["run"].event.candidates)


def test_complete_source_recall_is_independently_signed_and_missing_reference_is_na(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory)
    result = _evaluate(
        inputs,
        directory,
        paths,
        truth_loader=lambda: None,
        annotations_loader=None,
        reference_approval=None,
    )
    assert result["feasible_candidate_recall"] == 1
    assert result["source_class_inventory_exhaustive"] is True
    assert result["class_signature_method"] == "INDEPENDENT_EXACT_SOURCE_RAY_CROSSING"
    assert result["status"] == "NO_REFERENCE"
    assert result["ade_m"] is None
    assert all(row["coverage_at_k"] is None for row in result["metrics_at_k"].values())


def test_mismatched_reference_source_is_rejected_after_safe_freeze_boundary(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory)
    poisoned = inputs["truth"] | {"source_sha256": "0" * 64}
    with pytest.raises(ValueError, match="reference target/source/context/floor"):
        _evaluate(inputs, directory, paths, truth_loader=lambda: _bytes(poisoned))


def test_changed_metric_config_cannot_open_reference_or_override_approved_epsilon(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    directory = tmp_path / "inference"
    paths = _freeze(inputs, directory)
    changed = inputs["metric_config"].model_copy(update={"coverage_epsilon_m": 1.0})

    def hidden() -> bytes:
        raise AssertionError("changed metrics must not load reference")

    with pytest.raises(ValueError, match="approved HR03"):
        _evaluate(inputs, directory, paths, metric_config=changed, truth_loader=hidden)


def test_geometry_recall_counts_emitted_routes_before_unavailable_timing_is_removed(
    inputs: dict[str, Any],
    tmp_path: Path,
) -> None:
    provider, config = inputs["provider"], inputs["config"]
    binding = inputs["frames"].samples[0].binding
    samples = []
    for sample in _samples(binding, three_segments=False):
        timestamp = sample.timestamp / 4
        point = sample.projected_point
        if point is not None:
            point = point.model_copy(
                update={
                    "timestamp": timestamp,
                    "world_position": (point.world_position[0], 4.5, 0.0),
                }
            )
        samples.append(sample.model_copy(update={"timestamp": timestamp, "projected_point": point}))
    frames = FrameSampleDataset(samples=tuple(samples))
    aggregation = aggregate_frames(frames.samples, config.aggregation_policy)
    gap = bind_scoped_gaps(aggregation, provider, config, expected_stream_binding=binding)[0]
    navigation = build_scoped_navigation(gap, provider, config)
    network, _ = build_scoped_visibility_network(
        provider,
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_ids=(gap.start.observation.camera_id,),
        spatial_context_id=binding.spatial_context_id,
    )
    arguments = dict(
        expected_binding=config.authority,
        start_bu=navigation.endpoint_positions_bu[0],
        end_bu=navigation.endpoint_positions_bu[1],
        camera_id=gap.start.observation.camera_id,
        gap_duration_s=5.0,
        movement=config.movement,
        policy=config.search_policy,
        travel_time_filter=False,
        clock=lambda: 0.0,
    )
    production = produce_scoped_class_candidates(
        provider,
        network,
        navigation.source_edge_polylines_bu,
        **arguments,
    )
    run = run_scoped_baseline(
        gap,
        navigation,
        "geometry",
        aggregation=aggregation,
        provider=provider,
        config=config,
        frozen_config_sha256=content_sha256(config.model_dump(mode="json")),
        class_candidates=production,
        clock=lambda: 0.0,
    )
    assert len(run.geometric_result.routes) == 2
    assert len(run.event.candidates) == 1
    assert len(run.timing_unavailable_route_ids) == 1
    inventory = enumerate_visibility_route_classes(
        provider,
        network,
        navigation.source_edge_polylines_bu,
        **arguments,
    )
    changed = inputs | {
        "frames": frames,
        "aggregation": aggregation,
        "navigation": navigation,
        "run": run,
        "inventory": inventory,
        "sidecar": inputs["sidecar"]
        | {
            "frames_content_sha256": content_sha256(frames.model_dump(mode="json")),
        },
    }
    directory = tmp_path / "inference"
    paths = _freeze(changed, directory)
    result = _evaluate(
        changed, directory, paths, truth_loader=lambda: None, annotations_loader=None
    )
    assert result["candidate_count"] == 2
    assert result["timed_candidate_count"] == 1
    assert result["timing_unavailable_route_count"] == 1
    assert result["feasible_candidate_recall"] == 1.0
    assert result["feasible_candidate_recall_numerator"] == 2
    assert result["feasible_candidate_recall_denominator"] == 2
    assert len(result["predicted_class_signatures"]) == 2
    assert result["source_bound_hold_relation_count"] == 1

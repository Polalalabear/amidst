"""Post-freeze scoped metrics with independent class and physical populations.

Reference loaders are called only after every frozen inference input is verified.
The original configured metrics and reference helpers retain their diagnostic
literals; this wrapper records approved source/metric authority independently.
Oracle representatives never become emitted predictions, timings never become
route K, and missing or incomplete populations remain unavailable.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from amidst.domain.common import Timestamp, Vec3
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.evidence import VisibilityStatus
from amidst.domain.metric_config import MetricConfig
from amidst.evaluation.configured import evaluate_configured_trajectories
from amidst.evaluation.metrics import _authorized_segment
from amidst.finalization.formal_route_inventory import (
    WindingClassInventory,
    _exceeds,
    _prepare_scoped_operation,
    build_scoped_visibility_network,
    enumerate_visibility_route_classes,
    source_hole_witness,
    source_winding_crossing,
)
from amidst.finalization.reviewed_collision import (
    ReviewedCollisionBundle,
    evaluate_reviewed_known_collisions,
)
from amidst.finalization.reviewed_pipeline import (
    additional_metrics,
    digest,
    evaluation_reference,
    require_inference_freeze,
    safe_artifact,
)
from amidst.finalization.reviewed_reference_movement import (
    ReferenceMovementApproval,
    evaluate_reference_movement,
)
from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider
from amidst.finalization.scoped_inference import (
    ScopedBaselineRun,
    ScopedInferenceConfig,
    ScopedNavigationGraph,
    build_scoped_case_pipeline,
)
from amidst.finalization.source_class_eligibility import (
    SourceClassEligibilityCertificate,
    certify_source_class_eligibility_intervals,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import Coordinate, Digest, GeometryAuthorityError, GeometryModel

type FrozenInputPath = str | tuple[str, str]
type ReferenceLoader = Callable[[], bytes | None]


class ScopedTruthSample(GeometryModel):
    timestamp: Timestamp
    position: Vec3
    floor_id: str = Field(min_length=1)


class ScopedGroundTruth(GeometryModel):
    provenance: Literal["GROUND_TRUTH"]
    source_sha256: Digest
    spatial_context_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    coordinate_units: Literal["BLENDER_NATIVE_UNITS"]
    samples: tuple[ScopedTruthSample, ...] = Field(min_length=2)
    trajectory_id: str | None = None
    sample_source: Literal["BLENDER_EVALUATED", "CONFIGURATION_SAMPLER"] = "CONFIGURATION_SAMPLER"

    @model_validator(mode="after")
    def ordered_samples(self) -> Self:
        if any(b.timestamp <= a.timestamp for a, b in pairwise(self.samples)):
            raise ValueError("source Ground Truth timestamps must remain strictly ordered")
        return self


def _frozen_inputs(
    directory: Path,
    paths: Mapping[str, FrozenInputPath],
    values: Mapping[str, object],
) -> dict[str, Any]:
    freeze = require_inference_freeze(directory)
    if set(paths) != set(values):
        raise ValueError("scoped evaluation requires every exact frozen input role")
    for role, expected in values.items():
        descriptor = paths[role]
        relative, field = (descriptor, None) if isinstance(descriptor, str) else descriptor
        if Path(relative).parts[0] in {"evaluation", "simulation"}:
            raise ValueError(
                "evaluation input roles cannot open reference partitions before freeze"
            )
        path = safe_artifact(directory, relative)
        if relative not in freeze["artifacts"] or digest(path) != freeze["artifacts"][relative]:
            raise ValueError("scoped evaluation input is not covered by the inference freeze")
        document = json.loads(path.read_bytes())
        if field is not None:
            document = document[field]
        if content_sha256(document) != content_sha256(expected):
            raise ValueError("scoped evaluation value differs from frozen input role: " + role)
    return freeze


def _approved_metrics(metrics: MetricConfig, provider: ScopedUnionPhysicalProvider) -> MetricConfig:
    metrics = MetricConfig.model_validate(metrics.model_dump(mode="python"))
    if (
        metrics.k_values != (1, 2, 3)
        or metrics.coverage_epsilon_m != 0.5
        or (
            metrics.trajectory_distance_metric != "ADE"
            or metrics.coverage_comparison != "STRICTLY_LESS_THAN"
            or metrics.collision_tolerance_m != provider.contract.parameter("collision_tolerance_m")
            or metrics.constraint_speed_relative_tolerance != 1e-12
            or metrics.constraint_corridor_tolerance_m != 1e-6
        )
    ):
        raise ValueError("scoped MetricConfig differs from preserved approved HR03/numerics")
    return metrics


def _source_mapping(
    navigation: ScopedNavigationGraph,
    provider: ScopedUnionPhysicalProvider,
) -> dict[Vec3, Coordinate]:
    scale = provider.contract.scale.metres_per_blender_unit
    result: dict[Vec3, Coordinate] = {}
    graph_edges = {e.edge_id: e for e in navigation.graph.edges}
    if set(graph_edges) != set(navigation.source_edge_polylines_bu):
        raise ValueError("physical evaluation requires the complete saved source-edge mapping")
    for identity, points in navigation.source_edge_polylines_bu.items():
        normalized = tuple((p[0] * scale, p[1] * scale, p[2] * scale) for p in points)
        if normalized != graph_edges[identity].polyline:
            raise ValueError("evaluation graph differs from exact source-coordinate normalization")
        for native, metric in zip(points, normalized, strict=True):
            if metric in result and result[metric] != native:
                raise ValueError("source-coordinate witnesses must be unambiguous at SI boundaries")
            result[metric] = native
    for native in navigation.endpoint_positions_bu:
        metric = native[0] * scale, native[1] * scale, native[2] * scale
        if metric in result and result[metric] != native:
            raise ValueError("endpoint source-coordinate witness differs from its navigation edge")
        result[metric] = native
    return result


def _independent_inventory(
    inventory: WindingClassInventory,
    run: ScopedBaselineRun,
    navigation: ScopedNavigationGraph,
    config: ScopedInferenceConfig,
    provider: ScopedUnionPhysicalProvider,
) -> None:
    build_scoped_case_pipeline(run.gap_binding, navigation, provider, config)
    query = {
        "start_bu": navigation.endpoint_positions_bu[0],
        "end_bu": navigation.endpoint_positions_bu[1],
        "camera_id": run.gap_binding.start.observation.camera_id,
        "gap_duration_s": run.event.time_range[1] - run.event.time_range[0],
        "policy": config.search_policy.model_dump(mode="json"),
        "movement": config.movement.model_dump(mode="json"),
        "travel_time_filter": run.core_factors.travel_time_filter,
        "class_definition": "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST",
    }
    if inventory.authority != run.authority or (
        inventory.navigation_content_sha256
        != content_sha256(navigation.graph.model_dump(mode="json"))
        or inventory.source_edge_geometry_content_sha256
        != content_sha256(
            navigation.source_edge_polylines_bu,
        )
        or inventory.policy != config.search_policy
        or inventory.movement != config.movement
        or inventory.travel_time_filter != run.core_factors.travel_time_filter
        or inventory.query_content_sha256 != content_sha256(query)
        or inventory.endpoint_z_bu != tuple(p[2] for p in navigation.endpoint_positions_bu)
        or inventory.source_boundary_z_bu != provider.proposal.floor.point[2]
        or inventory.exact_hole_witness_xy_bu
        != source_hole_witness(provider, navigation.source_edge_polylines_bu)
    ):
        raise ValueError("independent inventory source/geometry/actual eligibility differs")
    if inventory.complete:
        network, source = build_scoped_visibility_network(
            provider,
            expected_binding=run.authority,
            start_bu=navigation.endpoint_positions_bu[0],
            end_bu=navigation.endpoint_positions_bu[1],
            camera_ids=(run.gap_binding.start.observation.camera_id,),
            spatial_context_id=run.gap_binding.binding.spatial_context_id,
        )
        if network.navigation.config != navigation.graph or (
            source != navigation.source_edge_polylines_bu
        ):
            raise ValueError("inventory regeneration source network differs from saved mapping")
        regenerated = enumerate_visibility_route_classes(
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
            budget=inventory.budget,
            clock=lambda: 0.0,
        )
        if regenerated != inventory:
            raise ValueError("complete class inventory differs from independent regeneration")


def _source_eligibility(
    certificate: SourceClassEligibilityCertificate,
    run: ScopedBaselineRun,
    navigation: ScopedNavigationGraph,
    config: ScopedInferenceConfig,
    inventory: WindingClassInventory,
    provider: ScopedUnionPhysicalProvider,
) -> SourceClassEligibilityCertificate:
    certificate = SourceClassEligibilityCertificate.model_validate_json(
        certificate.model_dump_json()
    )
    if certificate.authority != run.authority or (
        certificate.query_content_sha256 != inventory.query_content_sha256
        or certificate.navigation_content_sha256 != inventory.navigation_content_sha256
        or certificate.source_edge_geometry_content_sha256
        != inventory.source_edge_geometry_content_sha256
        or certificate.endpoint_positions_bu != navigation.endpoint_positions_bu
        or certificate.source_boundary_z_bu != provider.proposal.floor.point[2]
        or certificate.policy != config.search_policy
        or certificate.movement != config.movement
        or certificate.travel_time_filter != run.core_factors.travel_time_filter
        or certificate.exact_hole_witness_xy_bu != inventory.exact_hole_witness_xy_bu
    ):
        raise ValueError("source class eligibility authority/query/endpoint/factor pins differ")
    if certificate.recall_denominator_complete:
        network, _ = build_scoped_visibility_network(
            provider,
            expected_binding=run.authority,
            start_bu=navigation.endpoint_positions_bu[0],
            end_bu=navigation.endpoint_positions_bu[1],
            camera_ids=(run.gap_binding.start.observation.camera_id,),
            spatial_context_id=run.gap_binding.binding.spatial_context_id,
        )
        regenerated = certify_source_class_eligibility_intervals(
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
            budget=certificate.budget,
            clock=lambda: 0.0,
        )
        if regenerated != certificate:
            raise ValueError(
                "source class eligibility differs from independent interval regeneration"
            )
    return certificate


def _class_recall(
    run: ScopedBaselineRun,
    inventory: WindingClassInventory,
    mapping: Mapping[Vec3, Coordinate],
    provider: ScopedUnionPhysicalProvider,
    certificate: SourceClassEligibilityCertificate | None,
) -> dict[str, Any]:
    prepared = _prepare_scoped_operation(provider, run.authority)
    predicted = set()
    signatures = []
    for candidate in run.geometric_result.routes:
        if any(point not in mapping for point in candidate.polyline):
            raise ValueError("prediction introduced coordinates absent from saved source witnesses")
        source = tuple(mapping[p] for p in candidate.polyline)
        prepared.validate_polyline(source)
        signature = sum(
            source_winding_crossing(a, b, inventory.exact_hole_witness_xy_bu)
            for a, b in pairwise(source)
        )
        predicted.add(signature)
        signatures.append({"candidate_id": candidate.candidate_id, "winding_signature": signature})
    eligible = {route.winding_signature for route in inventory.routes}
    numerator = len(predicted & eligible) if inventory.complete else None
    denominator = len(eligible) if inventory.complete else None
    graph_recall = numerator / denominator if numerator is not None and denominator else None
    original_source_complete = (
        inventory.complete and inventory.source_route_class_inventory_exhaustive
    )
    source_complete = (
        original_source_complete
        if certificate is None
        else (certificate.recall_denominator_complete)
    )
    source_eligible = (
        eligible if certificate is None else set(certificate.eligible_winding_signatures)
    )
    source_numerator = len(predicted & source_eligible) if source_complete else None
    source_denominator = len(source_eligible) if source_complete else None
    source_recall = (
        source_numerator / source_denominator
        if source_numerator is not None and (source_denominator)
        else None
    )
    return {
        "feasible_candidate_recall": source_recall,
        "feasible_candidate_recall_numerator": source_numerator,
        "feasible_candidate_recall_denominator": source_denominator,
        "feasible_candidate_recall_status": (
            "AVAILABLE_EXHAUSTIVE_SOURCE_CANONICAL_CLASSES"
            if source_complete and source_denominator
            else "N/A_EMPTY_ELIGIBLE_CLASS_UNIVERSE"
            if source_complete
            else "N/A_TRUNCATED_INDEPENDENT_INVENTORY"
            if not inventory.complete
            else "N/A_SOURCE_CLASS_ELIGIBILITY_INTERVAL_UNDECIDABLE"
            if certificate is not None
            else "N/A_SOURCE_METRIC_CLASS_COVERAGE_NOT_PROVEN"
        ),
        "declared_graph_class_recall": graph_recall,
        "declared_graph_class_recall_numerator": numerator,
        "declared_graph_class_recall_denominator": denominator,
        "source_class_inventory_exhaustive": source_complete,
        "original_source_class_inventory_exhaustive": original_source_complete,
        "source_eligible_class_count": source_denominator,
        "source_metric_cover_scope": inventory.metric_cover_scope
        if certificate is None
        else certificate.metric_cover_scope,
        "declared_graph_class_inventory_exhaustive": inventory.complete,
        "inventory_metric_cover_scope": inventory.metric_cover_scope,
        "inventory_termination_reason": inventory.termination_reason,
        "inventory_content_sha256": content_sha256(inventory.model_dump(mode="json")),
        "predicted_class_signatures": signatures,
        "oracle_routes_used_as_predictions": False,
        "class_signature_method": "INDEPENDENT_EXACT_SOURCE_RAY_CROSSING",
        "source_recall_population": inventory.class_definition
        if certificate is None
        else certificate.population_scope,
        "source_eligibility_content_sha256": None
        if certificate is None
        else content_sha256(
            certificate.model_dump(mode="json"),
        ),
    }


def _physical_metrics(
    run: ScopedBaselineRun,
    navigation: ScopedNavigationGraph,
    config: ScopedInferenceConfig,
    metrics: MetricConfig,
    provider: ScopedUnionPhysicalProvider,
    mapping: Mapping[Vec3, Coordinate],
    collisions: ReviewedCollisionBundle | None,
) -> dict[str, Any]:
    prepared = _prepare_scoped_operation(provider, run.authority)
    collision_snapshot = None
    if collisions is not None:
        collision_snapshot = collisions.validate_bindings(
            source_sha256=provider.source_sha256,
            local_certificate_content_sha256=provider.certificate_content_sha256,
            semantic_receipt_content_sha256=provider.semantic_review_content_sha256,
            floor_ids=(provider.proposal.floor.floor_id,),
            contract=provider.contract,
        )
        if run.collision_consumer_receipt is not None and content_sha256(
            run.collision_consumer_receipt,
        ) != content_sha256(collision_snapshot.receipt()):
            raise ValueError("run collision receipt differs from independent evaluation authority")
    corridor = tuple(pair for edge in navigation.graph.edges for pair in pairwise(edge.polyline))
    corridor += tuple((node.position, node.position) for node in navigation.graph.nodes)
    count = domain_failures = collision_count = unknown = speed_count = violation_count = 0
    records = []
    for hypothesis in run.event.trajectories:
        for ordinal, (a, b) in enumerate(pairwise(hypothesis.timed_points)):
            count += 1
            start, end = a.world_position, b.world_position
            if start not in mapping or end not in mapping:
                raise ValueError("timed segment lacks its exact saved source-coordinate mapping")
            reasons: tuple[str, ...] = ()
            try:
                prepared.validate_polyline((mapping[start], mapping[end]))
            except GeometryAuthorityError as error:
                reasons = error.reasons
            domain_failures += bool(reasons)
            state = "NOT_EVALUATED" if collision_snapshot is None else "RETAINED"
            if collision_snapshot is not None:
                for consumer in collision_snapshot.consumers:
                    decision = consumer.validate((start, end))
                    if decision.state != "RETAINED":
                        state = decision.state
                        break
            collision_count += state == "REJECTED"
            unknown += state in {"UNVALIDATED", "NOT_EVALUATED"}
            speed = math.dist(start, end) / (b.timestamp - a.timestamp)
            overspeed = speed > config.movement.max_speed_m_s and not math.isclose(
                speed,
                config.movement.max_speed_m_s,
                rel_tol=metrics.constraint_speed_relative_tolerance,
                abs_tol=0.0,
            )
            speed_count += overspeed
            corridor_invalid = not _authorized_segment(
                start,
                end,
                corridor,
                metrics.constraint_corridor_tolerance_m,
            )
            invalid = bool(reasons) or overspeed or corridor_invalid or state == "REJECTED"
            violation_count += invalid
            records.append(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "segment_index": ordinal,
                    "source_scope_reasons": reasons,
                    "collision_state": state,
                    "speed_violation": overspeed,
                    "corridor_violation": corridor_invalid,
                    "constraint_violation": invalid,
                }
            )
    known = (
        None if collisions is None else evaluate_reviewed_known_collisions(run.event, collisions)
    )
    if known is not None and (
        known["segment_count"] != count
        or known["known_collision_segment_count"] != collision_count
        or known["unvalidated_segment_count"] != unknown
    ):
        raise ValueError("independent original collision evaluator population differs")
    available = count > 0 and not unknown and not domain_failures
    return {
        "physical_segment_count": count,
        "physical_population": "ALL_EMITTED_TIMING_SEGMENTS_INCLUDING_DWELL",
        "source_scope_violation_segment_count": domain_failures,
        "source_scope_segment_records": records,
        "collision_segment_count": collision_count if collision_snapshot is not None else None,
        "collision_unvalidated_segment_count": unknown,
        "collision_rate": collision_count / count if available else None,
        "collision_status": "AVAILABLE_COMPLETE_SCOPED_BODY_AND_INDEPENDENT_KNOWN_COLLIDERS"
        if available
        else "N/A_UNVALIDATED_OR_MISSING_INDEPENDENT_COLLISION_POPULATION",
        "constraint_violation_segment_count": violation_count,
        "constraint_violation_rate": violation_count / count if count and not unknown else None,
        "speed_violation_segment_count": speed_count,
        "known_collision_evaluation": known,
        "independent_collision_evaluator_retained": collisions is not None,
        "inference_collision_filter_enabled": run.collision_filter_enabled,
        "unit_boundary_policy": "EXACT_SAVED_SOURCE_COORDINATES_NO_SI_DIVISION_SNAP_OR_EPSILON",
    }


def _reference_adapter(truth: ScopedGroundTruth, scale: float) -> dict[str, Any]:
    """Only adapt the original helpers' declared 0.0247 scale; retain actual inputs."""
    return {
        "provenance": "GROUND_TRUTH",
        "source_asset_sha256": truth.source_sha256,
        "spatial_context_id": truth.spatial_context_id,
        "target_id": truth.target_id,
        "trajectory_id": truth.trajectory_id or "scoped-reference:" + truth.spatial_context_id,
        "sample_source": truth.sample_source,
        "samples": [
            {
                "timestamp": s.timestamp,
                "floor_id": s.floor_id,
                "position": [v * (scale / 0.0247) for v in s.position],
            }
            for s in truth.samples
        ],
    }


def _hold_relation_metrics(
    run: ScopedBaselineRun,
    navigation: ScopedNavigationGraph,
    config: ScopedInferenceConfig,
    provider: ScopedUnionPhysicalProvider,
    mapping: Mapping[Vec3, Coordinate],
) -> dict[str, Any]:
    """Check source-bound HOLD independently without inventing a camera transition.

    Protocol v1 requires N/A when no transition is declared. The identity HOLD
    relation therefore retains a separately named population and denominator.
    """
    gap = run.gap_binding
    start, end = gap.start.observation, gap.end.observation
    cameras = {b.camera.camera_id: b for b in provider.proposal.camera_landmark_bindings}
    first, last = start.projected_path[-1], end.projected_path[0]
    if (
        start.camera_id != end.camera_id
        or start.camera_id not in cameras
        or (
            first.floor_id != provider.proposal.floor.floor_id
            or last.floor_id != provider.proposal.floor.floor_id
            or first.camera_id != start.camera_id
            or last.camera_id != end.camera_id
            or first.timestamp != start.end_time
            or last.timestamp != end.start_time
            or start.end_time >= end.start_time
        )
    ):
        raise ValueError("independent HOLD relation lacks approved ordered camera/floor anchors")
    inventory = {
        "schema_version": "phase1-independent-source-hold-relation-v1",
        "authority": run.authority.model_dump(mode="json"),
        "binding": gap.binding.model_dump(mode="json"),
        "start": gap.start.model_dump(mode="json"),
        "end": gap.end.model_dump(mode="json"),
        "native_endpoint_positions_bu": navigation.endpoint_positions_bu,
        "source_camera_landmark_content_sha256": content_sha256(
            cameras[start.camera_id].model_dump(mode="json"),
        ),
        "relation_type": "DIRECTED_OBSERVED_ENDPOINT_SAME_CAMERA_FLOOR_IDENTITY_HOLD",
        "candidate_outputs_used_to_build_inventory": False,
        "actual_camera_handoff_count": 0,
        "core_self_transition_created": False,
    }
    prepared = _prepare_scoped_operation(provider, run.authority)
    failures = []
    for candidate in run.event.candidates:
        reasons = []
        if candidate.start_observation_id != start.observation_id or (
            candidate.end_observation_id != end.observation_id
            or candidate.polyline[0] != first.world_position
            or candidate.polyline[-1] != last.world_position
        ):
            reasons.append("WRONG_SOURCE_OBSERVATION_DIRECTION_OR_ANCHORS")
        if any(point not in mapping for point in candidate.polyline):
            reasons.append("MISSING_EXACT_SOURCE_COORDINATE_WITNESS")
        else:
            try:
                prepared.validate_polyline(tuple(mapping[p] for p in candidate.polyline))
            except GeometryAuthorityError as error:
                reasons.extend(error.reasons)
        if _exceeds(
            math.fsum(math.dist(a, b) for a, b in pairwise(candidate.polyline))
            / config.movement.max_speed_m_s,
            end.start_time - start.end_time,
        ):
            reasons.append("SOURCE_HOLD_ROUTE_EXCEEDS_APPROVED_SPEED_TIME")
        if reasons:
            failures.append({"candidate_id": candidate.candidate_id, "reasons": reasons})
    count = len(run.event.candidates)
    return {
        "source_bound_hold_relation_invalid_rate": len(failures) / count if count else None,
        "source_bound_hold_relation_count": count,
        "source_bound_hold_relation_invalid_count": len(failures),
        "source_bound_hold_relation_population": "TIMED_DISTINCT_CANDIDATES_ONLY",
        "source_bound_hold_relation_inventory": inventory,
        "source_bound_hold_relation_inventory_content_sha256": content_sha256(inventory),
        "source_bound_hold_relation_failures": failures,
        "same_camera_hold_status": "INVALID_SOURCE_BOUND_HOLD_RELATIONS"
        if failures
        else (
            "VALID_SOURCE_BOUND_HOLD_WITHOUT_FABRICATED_HANDOFF"
            if count
            else "N/A_NO_EMITTED_HOLD_RELATIONS"
        ),
        "actual_camera_handoff_count": 0,
        "camera_handoff_only_impossible_transition_rate": None,
        "camera_handoff_only_transition_count": 0,
    }


def evaluate_scoped_run(
    run: ScopedBaselineRun,
    truth_loader: ReferenceLoader,
    sidecar: dict[str, Any],
    inventory: WindingClassInventory,
    metric_config: MetricConfig,
    provider: ScopedUnionPhysicalProvider,
    *,
    inference_directory: Path,
    frozen_input_paths: Mapping[str, FrozenInputPath],
    config: ScopedInferenceConfig,
    navigation: ScopedNavigationGraph,
    frames: FrameSampleDataset,
    dataset_version: str,
    runtime_s: float | None = None,
    collision_bundle: ReviewedCollisionBundle | None = None,
    annotations_loader: ReferenceLoader | None = None,
    reference_approval: ReferenceMovementApproval | None = None,
    source_eligibility: SourceClassEligibilityCertificate | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Verify frozen predictions first; then invoke evaluation-only reference loaders."""
    run = ScopedBaselineRun.model_validate_json(run.model_dump_json())
    inventory = WindingClassInventory.model_validate_json(inventory.model_dump_json())
    config = ScopedInferenceConfig.model_validate_json(config.model_dump_json())
    navigation = ScopedNavigationGraph.model_validate_json(navigation.model_dump_json())
    frames = FrameSampleDataset.model_validate(frames.model_dump(mode="python"))
    metric_config = _approved_metrics(metric_config, provider)
    frozen_values: dict[str, object] = {
        "run": run.model_dump(mode="json"),
        "projection": sidecar,
        "inventory": inventory.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
        "navigation": navigation.model_dump(mode="json"),
        "frames": frames.model_dump(mode="json"),
        "metrics": metric_config.model_dump(mode="json"),
    }
    if source_eligibility is not None:
        frozen_values["source_eligibility"] = source_eligibility.model_dump(mode="json")
    freeze = _frozen_inputs(inference_directory, frozen_input_paths, frozen_values)
    _prepare_scoped_operation(provider, run.authority)
    if (
        run.authority != config.authority
        or navigation.authority != config.authority
        or (
            run.frozen_config_sha256 != content_sha256(config.model_dump(mode="json"))
            or run.navigation_content_sha256 != content_sha256(navigation.model_dump(mode="json"))
            or run.gap_binding.config_content_sha256 != run.frozen_config_sha256
            or run.bound_gap.event != run.event
            or run.bound_gap.start != run.gap_binding.start
            or run.bound_gap.end != run.gap_binding.end
            or sidecar.get("ground_truth_read") is not False
            or sidecar.get("source_asset_sha256") != provider.source_sha256
            or sidecar.get("authority") != run.authority.model_dump(mode="json")
            or sidecar.get("frames_content_sha256")
            != content_sha256(frames.model_dump(mode="json"))
            or sidecar.get("config_file_sha256") != config.fresh_export_config_sha256
            or any(s.binding != run.gap_binding.binding for s in frames.samples)
        )
    ):
        raise ValueError("scoped evaluation source/context/config/event binding differs")
    first_ids = tuple(dict.fromkeys(t.candidate_id for t in run.event.trajectories))
    if first_ids != tuple(c.candidate_id for c in run.event.candidates):
        raise ValueError("timing hypotheses must retain frozen distinct candidate order")
    unavailable = tuple(
        route.candidate_id
        for route in run.geometric_result.routes
        if route.timing_status == "UNAVAILABLE"
    )
    if unavailable != run.timing_unavailable_route_ids or (
        tuple(c.candidate_id for c in run.event.candidates)
        != tuple(
            r.candidate_id for r in run.geometric_result.routes if r.timing_status == "FEASIBLE"
        )
    ):
        raise ValueError("timed/unavailable populations differ from frozen geometric routes")
    _independent_inventory(inventory, run, navigation, config, provider)
    if source_eligibility is not None:
        source_eligibility = _source_eligibility(
            source_eligibility,
            run,
            navigation,
            config,
            inventory,
            provider,
        )
    mapping = _source_mapping(navigation, provider)
    recall = _class_recall(run, inventory, mapping, provider, source_eligibility)
    physical = _physical_metrics(
        run, navigation, config, metric_config, provider, mapping, collision_bundle
    )
    hold = _hold_relation_metrics(run, navigation, config, provider, mapping)
    if runtime_s is not None and (
        isinstance(runtime_s, bool) or not math.isfinite(runtime_s) or runtime_s < 0
    ):
        raise ValueError("measured inference runtime must be finite and nonnegative")
    if reference_approval is not None:
        reference_approval.validate()
        if reference_approval.source_sha256 != provider.source_sha256 or (
            reference_approval.protocol_sha256 != run.authority.pins.protocol_sha256
            or reference_approval.original_human_decisions_sha256
            != run.authority.pins.original_human_decisions_sha256
        ):
            raise ValueError("reference movement approval differs from original source/HR/protocol")
    # No reference/annotation loader can be called above this boundary.
    raw_truth = truth_loader()
    truth = None if raw_truth is None else ScopedGroundTruth.model_validate_json(raw_truth)
    if truth is not None and (
        truth.source_sha256 != provider.source_sha256
        or truth.target_id != run.event.target_id
        or truth.spatial_context_id != run.gap_binding.binding.spatial_context_id
        or any(s.floor_id != provider.proposal.floor.floor_id for s in truth.samples)
    ):
        raise ValueError("evaluation reference target/source/context/floor differs")
    computed, extra = None, {}
    at_k: dict[str, dict[str, Any]] = {
        str(k): {"min_ade_at_k_m": None, "min_fde_at_k_m": None, "coverage_at_k": None}
        for k in metric_config.k_values
    }
    primary_ade = primary_fde = None
    if truth is not None:
        reference_document = _reference_adapter(
            truth, provider.contract.scale.metres_per_blender_unit
        )
        reference = evaluation_reference(reference_document, run.event, seed=seed)
        computed = evaluate_configured_trajectories(
            run.event.trajectories,
            reference,
            metric_config,
            constraints=ConstraintConfig(
                max_speed_m_s=config.movement.max_speed_m_s, navigation_graph=navigation.graph
            ),
        )
        at_k = {
            str(r.config.k_routes): {
                "min_ade_at_k_m": r.min_ade_at_k_m,
                "min_fde_at_k_m": r.min_fde_at_k_m,
                "coverage_at_k": r.coverage_at_k,
            }
            for r in computed.evaluations
        }
        primary = computed.evaluations[0].trajectory_metrics
        if primary:
            primary_ade, primary_fde = primary[0].ade_m, primary[0].fde_m
        # Reuse the original additional-metric helper for primary path length;
        # its projection population remains a separate diagnostic below.
        bindings = sidecar["camera_bindings"]
        offset = bindings[0]["landmark_offset_bu"][2]
        scale_adapter = provider.contract.scale.metres_per_blender_unit / 0.0247
        producer = sidecar.get("policy_projection", sidecar)
        legacy_rows = [
            dict(
                row,
                selected_world_position=None
                if row["selected_world_position"] is None
                else [v * scale_adapter for v in row["selected_world_position"]],
            )
            for row in producer["rows"]
        ]
        extra = additional_metrics(
            {"rows": legacy_rows},
            reference_document,
            run,
            source_bound_offset_bu=offset * scale_adapter,
        )
        by_time = {s.timestamp: s.position for s in truth.samples}
        errors = [
            math.dist(
                s.projected_point.world_position,
                tuple(
                    v * (provider.contract.scale.metres_per_blender_unit)
                    for v in by_time[s.timestamp]
                ),
            )
            for s in frames.samples
            if s.visibility == VisibilityStatus.OBSERVED
            and s.projected_point is not None
            and s.timestamp in by_time
        ]
        extra["policy_selected_projection_error_m"] = extra["projection_error_m"]
        extra["policy_selected_projection_error_sample_count"] = extra[
            "projection_error_sample_count"
        ]
        extra.update(
            projection_error_m=math.fsum(errors) / len(errors) if errors else None,
            projection_error_sample_count=len(errors),
            projection_error_population="ALL_MATCHED_VISIBLE_PROJECTED_SOURCE_FRAMES",
            projection_error_missing_sample_count=sum(
                s.visibility == VisibilityStatus.OBSERVED
                and (s.projected_point is None or s.timestamp not in by_time)
                for s in frames.samples
            ),
        )
    if annotations_loader is not None and reference_approval is not None:
        annotation_raw = annotations_loader()
        if annotation_raw is not None:
            extra.update(
                evaluate_reference_movement(
                    run.event,
                    json.loads(annotation_raw),
                    reference_approval,
                    expected_dataset_version=dataset_version,
                )
            )
    extra.setdefault("projection_error_m", None)
    extra.setdefault("path_length_error_m", None)
    extra.setdefault("travel_time_error_s", None)
    extra.setdefault("travel_time_error_status", "N/A_APPROVED_REFERENCE_MOVEMENT_NOT_SUPPLIED")
    return {
        "schema_version": "phase1-scoped-evaluation-v1",
        "result_type": "BLENDER_RESEARCH_RESULT",
        "status": "EVALUATED" if truth else "NO_REFERENCE",
        "source_sha256": provider.source_sha256,
        "scope_id": provider.scope_id,
        "authority": run.authority.model_dump(mode="json"),
        "inference_freeze_file_sha256": digest(inference_directory / "inference_freeze.json"),
        "inference_freeze": freeze,
        "ground_truth_loaded_after_inference_freeze": truth is not None,
        "reference_file_sha256": None
        if raw_truth is None
        else hashlib.sha256(raw_truth).hexdigest(),
        "metric_authority": "APPROVED_ORIGINAL_HR03_PROFILE_SEPARATE_FROM_CORE_LITERALS",
        "metric_config": metric_config.model_dump(mode="json"),
        "computation_result": None if computed is None else computed.model_dump(mode="json"),
        "ade_m": primary_ade,
        "fde_m": primary_fde,
        "metrics_at_k": at_k,
        "candidate_count": len(run.geometric_result.routes),
        "candidate_count_population": "EMITTED_DISTINCT_GEOMETRIC_ROUTES_BEFORE_TIMING_EXPANSION",
        "timed_candidate_count": len(run.event.candidates),
        "timing_unavailable_route_ids": unavailable,
        "timing_unavailable_route_count": len(unavailable),
        "timing_hypothesis_count": len(run.event.trajectories),
        "search_nodes": run.geometric_result.expanded_nodes,
        "termination_reason": run.event.termination_reason.value,
        "search_complete": run.geometric_result.complete,
        "runtime_s": runtime_s,
        "runtime_population": "CALLER_MEASURED_INFERENCE_EXCLUDING_EVALUATION",
        "impossible_transition_rate": None,
        "impossible_transition_count": 0,
        "transition_count": 0,
        "impossible_transition_status": "N/A_NO_DECLARED_CAMERA_OR_FLOOR_TRANSITIONS",
        "transition_population": "DECLARED_CAMERA_FLOOR_TRANSITIONS_OF_DISTINCT_ROUTES",
        "primary_selection_uses_ground_truth": False,
        "formal_case_readiness": False,
        **recall,
        **physical,
        **hold,
        **extra,
    }

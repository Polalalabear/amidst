"""Source-bound same-camera recovery over an intact approved cell union.

The core camera-transition schema still rejects self transitions. HOLD is a
separate constant-camera evidence constraint; its navigation search uses the
existing graph traversal without inventing a handoff. The finite visibility
grammar below is explicit, and never claims continuous route-class completeness
or protocol/portal readiness. No simulation recipe, GT or reference is an input.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from itertools import pairwise
from time import monotonic
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from amidst.benchmark.baselines import (
    BaselineUnavailableError,
    RoutePhysicalRecord,
    require_supported_baseline,
)
from amidst.domain.common import DomainModel, Provenance, Vec3
from amidst.domain.evidence import VisibilityStatus
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationGraphConfig,
)
from amidst.domain.pipeline import InferenceInput, PipelineConfig
from amidst.domain.reconstruction import ReconstructionPolicy
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.stream import (
    AggregationPolicy,
    BoundGapEvent,
    BoundObservation,
    ObservationAggregation,
    RawProjectedFrameSample,
    StreamBinding,
)
from amidst.domain.topology import CameraTopologyConfig, CameraTopologyNode
from amidst.domain.trajectory import Event, ReconstructionResult
from amidst.finalization.formal_route_inventory import _prepare_scoped_operation
from amidst.finalization.reviewed_collision import ReviewedCollisionBundle
from amidst.finalization.scoped_authority import (
    ScopedUnionPhysicalProvider,
    _physical,
    _segment_interval,
)
from amidst.finalization.scoped_class_search import (
    ScopedClassSearchResult,
    build_class_macro_network,
    class_search_query,
)
from amidst.finalization.scoped_route_inventory import (
    ScopedRouteAuthorityBinding,
)
from amidst.graph.engine import GeometricSearchResult, GraphFactorMask, SpatiotemporalGraphEngine
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_collision import CylinderCollisionConsumer
from amidst.reconstruction.blind_gap import BlindGapReconstructor
from amidst.scene_geometry import Coordinate, Digest


class ScopedBudgetLineage(DomainModel):
    """Every deviation from the separately pinned parent budget is explicit."""

    parent_inference_lock_content_sha256: Digest
    parent_search_policy: GraphSearchPolicy
    changed_search_fields: tuple[str, ...] = ()
    change_reason: str | None = None

    @model_validator(mode="after")
    def declared_fields(self) -> Self:
        if len(set(self.changed_search_fields)) != len(self.changed_search_fields) or any(
            name not in GraphSearchPolicy.model_fields for name in self.changed_search_fields
        ):
            raise ValueError("budget lineage requires unique declared search-policy fields")
        if self.changed_search_fields and not self.change_reason:
            raise ValueError("a changed frozen stress budget requires its explicit reason")
        return self


class ScopedInferenceConfig(DomainModel):
    schema_version: Literal["phase1-scoped-inference-config-v1"] = (
        "phase1-scoped-inference-config-v1"
    )
    authority: ScopedRouteAuthorityBinding
    fresh_export_config_sha256: Digest
    source_camera_plane_ids: dict[str, str]
    metres_per_blender_unit: float = Field(gt=0, allow_inf_nan=False)
    movement: MovementConstraints
    search_policy: GraphSearchPolicy
    reconstruction_policy: ReconstructionPolicy = ReconstructionPolicy()
    aggregation_policy: AggregationPolicy = AggregationPolicy()
    budget_lineage: ScopedBudgetLineage
    ground_truth_read: Literal[False] = False
    graph_grammar: Literal["EXACT_APPROVED_UNION_BOUNDARY_VISIBILITY_GRAPH"] = (
        "EXACT_APPROVED_UNION_BOUNDARY_VISIBILITY_GRAPH"
    )

    @model_validator(mode="after")
    def locked_budget_and_planes(self) -> Self:
        if not self.source_camera_plane_ids or any(
            not camera or not plane for camera, plane in self.source_camera_plane_ids.items()
        ):
            raise ValueError("scoped inference requires explicit source-camera plane identities")
        parent = self.budget_lineage.parent_search_policy.model_dump(mode="json")
        actual = self.search_policy.model_dump(mode="json")
        changed = {name for name in parent if parent[name] != actual[name]}
        if changed != set(self.budget_lineage.changed_search_fields):
            raise ValueError("frozen search budget differs from its exact declared lineage")
        return self


class ScopedGapBinding(DomainModel):
    schema_version: Literal["phase1-scoped-same-camera-gap-v1"] = "phase1-scoped-same-camera-gap-v1"
    gap_id: str
    authority: ScopedRouteAuthorityBinding
    binding: StreamBinding
    start: BoundObservation
    end: BoundObservation
    interior_gap_sample_ids: tuple[str, ...] = Field(min_length=1)
    aggregation_content_sha256: Digest
    config_content_sha256: Digest
    source_camera_landmark_content_sha256: Digest
    projection_sidecar_content_sha256: Digest | None = None
    projection_observations_sha256: Digest | None = None
    topology_constraint: Literal["SOURCE_BOUND_SAME_CAMERA_HOLD"] = "SOURCE_BOUND_SAME_CAMERA_HOLD"
    camera_handoffs: Literal[0] = 0
    interior_coverage: Literal["ALL_SUPPLIED_SOURCE_SAMPLES"] = "ALL_SUPPLIED_SOURCE_SAMPLES"
    ground_truth_read: Literal[False] = False

    @model_validator(mode="after")
    def independent_same_camera_gap(self) -> Self:
        a, b = self.start.observation, self.end.observation
        if (
            self.start.binding != self.binding
            or self.end.binding != self.binding
            or (
                a.camera_id != b.camera_id
                or a.target_id != b.target_id
                or a.observation_id == b.observation_id
                or a.end_time >= b.start_time
            )
        ):
            raise ValueError(
                "HOLD requires independent ordered same-source/camera/target endpoints"
            )
        return self


def validate_scoped_inference_config(
    config: ScopedInferenceConfig,
    provider: ScopedUnionPhysicalProvider,
) -> ScopedInferenceConfig:
    prepared = _prepare_scoped_operation(provider, config.authority)
    return _validate_scoped_config(config, prepared.provider)


def _validate_scoped_config(
    config: ScopedInferenceConfig,
    provider: ScopedUnionPhysicalProvider,
) -> ScopedInferenceConfig:
    config = ScopedInferenceConfig.model_validate_json(config.model_dump_json())
    cameras = provider.proposal.camera_landmark_bindings
    if not provider.proposal.requested_projection_authority or (
        set(config.source_camera_plane_ids) != {item.camera.camera_id for item in cameras}
        or config.metres_per_blender_unit != provider.contract.scale.metres_per_blender_unit
    ):
        raise ValueError("scoped inference differs from exact approved camera/scale authority")
    return config


def bind_scoped_gaps(
    aggregation: ObservationAggregation,
    provider: ScopedUnionPhysicalProvider,
    config: ScopedInferenceConfig,
    *,
    expected_stream_binding: StreamBinding,
    projection_sidecar: Mapping[str, Any] | None = None,
    projection_observations_sha256: str | None = None,
) -> tuple[ScopedGapBinding, ...]:
    """Preserve every visible recovery and produce separate consecutive GAPs.

    A source-bound visible segment between two gaps cannot be merged away. Sparse
    sampling breaks without an explicit missing sample are not invented GAPs.
    Schedule completeness remains a separate exporter/dataset validation gate.
    """
    prepared = _prepare_scoped_operation(provider, config.authority)
    provider = prepared.provider
    config = _validate_scoped_config(config, provider)
    binding = StreamBinding.model_validate(expected_stream_binding.model_dump())
    if binding.source_asset_sha256 != provider.source_sha256 or binding.data_kind != "SYNTHETIC":
        raise ValueError("scoped stream differs from the independently pinned synthetic source")
    aggregation = ObservationAggregation.model_validate(aggregation.model_dump())
    if (
        aggregation.policy != config.aggregation_policy
        or aggregate_frames(
            aggregation.samples,
            aggregation.policy,
        )
        != aggregation
    ):
        raise ValueError("HOLD requires the unmodified canonical source evidence partition")
    if any(sample.binding != binding for sample in aggregation.samples):
        raise ValueError("scoped GAP raw sample source/context binding differs")
    cameras = {item.camera.camera_id: item for item in provider.proposal.camera_landmark_bindings}
    # Check every observed frame, retaining even out-of-union observations. Only
    # the endpoints of a consumed local GAP require local physical authority.
    for sample in aggregation.samples:
        if sample.camera_id not in cameras:
            raise ValueError("HOLD sample camera lacks exact approved source calibration")
        point = sample.projected_point
        if sample.visibility == VisibilityStatus.OBSERVED:
            if sample.uv is None or sample.provenance != Provenance.OBSERVED or point is None:
                raise ValueError(
                    "HOLD visible recovery requires actual pixels and projected evidence"
                )
            if point.floor_id != provider.proposal.floor.floor_id:
                raise ValueError("HOLD projection plane/floor differs from source authority")
            if point.plane_id == "EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION":
                _validate_multiview_sample(
                    sample,
                    projection_sidecar,
                    provider,
                    binding,
                    projection_observations_sha256,
                )
            elif point.plane_id != config.source_camera_plane_ids[sample.camera_id]:
                raise ValueError("HOLD projection plane/floor differs from source authority")
    groups: dict[tuple[str, str], list[BoundObservation]] = {}
    for item in aggregation.observations:
        if item.binding != binding or item.observation.provenance != Provenance.PROJECTED:
            raise ValueError("HOLD observations must retain the source-bound projected evidence")
        key = item.observation.target_id, item.observation.camera_id
        groups.setdefault(key, []).append(item)
    gaps = []
    aggregation_sha = content_sha256(aggregation.model_dump(mode="json"))
    config_sha = content_sha256(config.model_dump(mode="json"))
    for (target_id, camera_id), items in sorted(groups.items()):
        ordered = sorted(
            items,
            key=lambda item: (
                item.observation.start_time,
                item.observation.end_time,
                item.observation.observation_id,
            ),
        )
        for start, end in pairwise(ordered):
            a, b = start.observation, end.observation
            interior = tuple(
                sample
                for sample in aggregation.samples
                if sample.target_id == target_id
                and sample.camera_id == camera_id
                and a.end_time < sample.timestamp < b.start_time
            )
            if not interior:
                continue
            if any(sample.visibility != VisibilityStatus.GAP for sample in interior):
                raise ValueError("HOLD cannot merge away a visible recovery inside a GAP")
            if any(
                sample.target_id == target_id
                and sample.camera_id != camera_id
                and sample.visibility == VisibilityStatus.OBSERVED
                and a.end_time < sample.timestamp < b.start_time
                for sample in aggregation.samples
            ):
                # A camera-local missing interval is not a globally blind GAP
                # when another actual camera observes the same target inside it.
                continue
            points = a.projected_path[-1], b.projected_path[0]
            if points[0].timestamp != a.end_time or points[1].timestamp != b.start_time:
                raise ValueError(
                    "HOLD endpoints must be actual boundary samples, not extrapolations"
                )
            ratio = config.metres_per_blender_unit
            for point in points:
                p = point.world_position
                native = (p[0] / ratio, p[1] / ratio, p[2] / ratio)
                prepared.validate_polyline((native, native))
            identity = content_sha256(
                {
                    "binding": binding.model_dump(mode="json"),
                    "start": start.model_dump(mode="json"),
                    "end": end.model_dump(mode="json"),
                    "interior_gap_sample_ids": [sample.sample_id for sample in interior],
                }
            )
            gaps.append(
                ScopedGapBinding(
                    gap_id="scoped-gap:" + identity[:24],
                    authority=config.authority,
                    binding=binding,
                    start=start,
                    end=end,
                    interior_gap_sample_ids=tuple(sample.sample_id for sample in interior),
                    aggregation_content_sha256=aggregation_sha,
                    config_content_sha256=config_sha,
                    source_camera_landmark_content_sha256=content_sha256(
                        cameras[camera_id].model_dump(mode="json"),
                    ),
                    projection_sidecar_content_sha256=(
                        None if projection_sidecar is None else content_sha256(projection_sidecar)
                    ),
                    projection_observations_sha256=projection_observations_sha256,
                )
            )
    return tuple(
        sorted(
            gaps,
            key=lambda gap: (
                gap.start.observation.end_time,
                gap.end.observation.start_time,
                gap.gap_id,
            ),
        )
    )


def _validate_multiview_sample(
    sample: RawProjectedFrameSample,
    sidecar: Mapping[str, Any] | None,
    provider: ScopedUnionPhysicalProvider,
    binding: StreamBinding,
    observations_sha256: str | None,
) -> None:
    """Retain the no-plane literal only with exact source-calibrated pair evidence."""
    if sidecar is None or observations_sha256 is None:
        raise ValueError("no-plane HOLD requires its source-bound exact-time projection sidecar")
    producer = sidecar.get(
        "policy_projection",
        sidecar.get(
            "raw_producer_result",
            sidecar.get("rawproducer_result", sidecar),
        ),
    )
    if (
        not isinstance(producer, Mapping)
        or producer.get("ground_truth_read") is not False
        or (
            producer.get("source_asset_sha256") != provider.source_sha256
            or producer.get("observations_sha256") != observations_sha256
        )
    ):
        raise ValueError("multiview projection sidecar source/input/GT binding differs")
    rows = producer.get("rows")
    if not isinstance(rows, list):
        raise ValueError("multiview HOLD requires exact-time producer rows")
    selected = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and (row.get("timestamp"), row.get("frame_id"), row.get("target_id"))
        == (sample.timestamp, sample.frame_id, sample.target_id)
    ]
    if len(selected) != 1:
        raise ValueError("multiview HOLD requires one unambiguous actual source-time row")
    row = selected[0]
    camera_bindings = {
        item.camera.camera_id: item for item in provider.proposal.camera_landmark_bindings
    }
    camera_ids = row.get("selected_camera_ids")
    if (
        not isinstance(camera_ids, list)
        or len(camera_ids) < 2
        or (
            len(set(camera_ids)) != len(camera_ids)
            or sample.camera_id not in camera_ids
            or any(identity not in camera_bindings for identity in camera_ids)
            or row.get("method") != "EXACT_TIME_MULTIVIEW"
            or row.get("ground_truth_read") is not False
            or row.get("selection_uses_ground_truth") is not False
            or row.get("source_asset_sha256") != provider.source_sha256
            or row.get("observations_sha256") != observations_sha256
            or row.get("source_id") != binding.source_id
            or row.get("spatial_context_id") != binding.spatial_context_id
            or row.get("camera_calibration_sha256")
            != content_sha256(
                [
                    camera_bindings[identity].camera.model_dump(mode="json")
                    for identity in sorted(camera_bindings)
                ]
            )
        )
    ):
        raise ValueError("multiview HOLD row differs from exact approved source-camera evidence")
    evidence = row.get("input_evidence")
    for identity in camera_ids:
        pair_inputs = (
            [
                value
                for value in evidence
                if isinstance(value, Mapping) and value.get("camera_id") == identity
            ]
            if isinstance(evidence, list)
            else []
        )
        if len(pair_inputs) != 1:
            raise ValueError("multiview HOLD requires each selected camera's actual pixel evidence")
        value = pair_inputs[0]
        pixels = value.get("point_2d")
        if (
            (value.get("timestamp"), value.get("frame_id"), value.get("target_id"))
            != (
                sample.timestamp,
                sample.frame_id,
                sample.target_id,
            )
            or value.get("status") != "OBSERVED"
            or not isinstance(pixels, (list, tuple))
            or (
                len(pixels) != 2
                or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in pixels
                )
            )
        ):
            raise ValueError("multiview HOLD pair must preserve exact-time visible source pixels")
    visible = (
        [
            value
            for value in evidence
            if isinstance(value, Mapping) and (value.get("camera_id") == sample.camera_id)
        ]
        if isinstance(evidence, list)
        else []
    )
    if len(visible) != 1 or (
        visible[0].get("target_id") != sample.target_id
        or visible[0].get("timestamp") != sample.timestamp
        or visible[0].get("frame_id") != sample.frame_id
        or visible[0].get("status") != "OBSERVED"
        or tuple(visible[0].get("point_2d") or ()) != sample.uv
    ):
        raise ValueError("multiview HOLD must preserve actual source pixels without invention")
    position = row.get("selected_world_position")
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        raise ValueError("multiview HOLD requires the original selected geometric point")
    assert sample.projected_point is not None
    offset = camera_bindings[sample.camera_id].landmark_offset_bu[2]
    ratio = provider.contract.scale.metres_per_blender_unit
    expected_position = (position[0] * ratio, position[1] * ratio, (position[2] - offset) * ratio)
    if sample.projected_point.world_position != expected_position:
        raise ValueError("multiview HOLD projection differs from approved landmark conversion")


class ScopedNavigationGraph(DomainModel):
    """The entire finite grammar, its exact source geometry and unit mapping."""

    authority: ScopedRouteAuthorityBinding
    gap_content_sha256: Digest
    graph: NavigationGraphConfig
    source_edge_polylines_bu: dict[str, tuple[Coordinate, ...]]
    edge_support_cell_ids: dict[str, tuple[str, ...]]
    endpoint_positions_bu: tuple[Coordinate, Coordinate]
    start_node_id: str
    end_node_id: str
    continuous_source_route_classes_exhaustive: Literal[False] = False
    portal_roles_granted: Literal[False] = False
    ground_truth_read: Literal[False] = False


def build_scoped_navigation(
    gap: ScopedGapBinding,
    provider: ScopedUnionPhysicalProvider,
    config: ScopedInferenceConfig,
    *,
    endpoint_positions_bu: tuple[Coordinate, Coordinate] | None = None,
) -> ScopedNavigationGraph:
    """Use the independently shared exact-union boundary visibility grammar.

    These source-cell connectors are navigation grammar, not portal semantics.
    Every directed edge retains its exact source polyline. Repeated edges remain
    legal in core bounded traversal; this builder does not enumerate simple paths.
    """
    from amidst.finalization.formal_route_inventory import _build_scoped_visibility_network

    prepared = _prepare_scoped_operation(provider, config.authority)
    provider = prepared.provider
    config = _validate_scoped_config(config, provider)
    gap = ScopedGapBinding.model_validate(gap.model_dump())
    if gap.authority != config.authority or gap.config_content_sha256 != content_sha256(
        config.model_dump(mode="json"),
    ):
        raise ValueError("scoped graph GAP differs from its frozen authority/config")
    ratio = config.metres_per_blender_unit
    first = gap.start.observation.projected_path[-1].world_position
    last = gap.end.observation.projected_path[0].world_position
    native = endpoint_positions_bu or (
        (first[0] / ratio, first[1] / ratio, first[2] / ratio),
        (last[0] / ratio, last[1] / ratio, last[2] / ratio),
    )
    if tuple(tuple(v * ratio for v in p) for p in native) != (first, last):
        raise ValueError("scoped graph exact BU to SI mapping differs from projected endpoints")
    for point in native:
        prepared.validate_polyline((point, point))
    network, polylines = _build_scoped_visibility_network(
        prepared,
        start_bu=native[0],
        end_bu=native[1],
        camera_ids=(gap.start.observation.camera_id,),
        spatial_context_id=gap.binding.spatial_context_id,
    )
    graph = network.navigation.config
    support: dict[str, tuple[str, ...]] = {}
    for identity, points in polylines.items():
        support[identity] = tuple(
            sorted(
                cell.cell_id
                for cell, proof in zip(
                    provider.proposal.cells,
                    provider.certificate.cells,
                    strict=True,
                )
                if _segment_interval(points[0], points[-1], _physical(proof).footpoint_bounds_bu)
                is not None
            )
        )
    start_node_id = network.navigation.locate_node(first, provider.proposal.floor.floor_id)
    end_node_id = network.navigation.locate_node(last, provider.proposal.floor.floor_id)
    if start_node_id is None or end_node_id is None:
        raise ValueError("exact source graph must contain both unsnapped projected endpoints")
    return ScopedNavigationGraph(
        authority=config.authority,
        gap_content_sha256=content_sha256(gap.model_dump(mode="json")),
        graph=graph,
        source_edge_polylines_bu=polylines,
        edge_support_cell_ids=support,
        endpoint_positions_bu=native,
        start_node_id=start_node_id,
        end_node_id=end_node_id,
    )


def build_scoped_case_pipeline(
    gap: ScopedGapBinding,
    navigation: ScopedNavigationGraph,
    provider: ScopedUnionPhysicalProvider,
    config: ScopedInferenceConfig,
) -> PipelineConfig:
    prepared = _prepare_scoped_operation(provider, config.authority)
    provider = prepared.provider
    config = _validate_scoped_config(config, provider)
    checked = build_scoped_navigation(
        gap, provider, config, endpoint_positions_bu=navigation.endpoint_positions_bu
    )
    if checked != navigation:
        raise ValueError("scoped navigation differs from exact frozen cell grammar/provenance")
    camera_id = gap.start.observation.camera_id
    cameras = {
        item.camera.camera_id: item.camera for item in provider.proposal.camera_landmark_bindings
    }
    if camera_id != gap.end.observation.camera_id or camera_id not in cameras:
        raise ValueError("HOLD cannot fabricate a source-camera alias or handoff")
    topology = CameraTopologyConfig(
        topology_id="scoped-hold:" + content_sha256(gap.model_dump(mode="json"))[:24],
        navigation_graph_id=navigation.graph.graph_id,
        spatial_context_id=gap.binding.spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED,
        source_asset_sha256=provider.source_sha256,
        nodes=(
            CameraTopologyNode(
                camera_id=camera_id,
                floor_id=provider.proposal.floor.floor_id,
                zone_id=cameras[camera_id].zone_id,
            ),
        ),
        transitions=(),
    )
    NavigationNetwork(NavigationGraph(navigation.graph), CameraTopologyGraph(topology))
    return PipelineConfig(
        navigation=navigation.graph,
        topology=topology,
        movement=config.movement,
        search_policy=config.search_policy,
        reconstruction_policy=config.reconstruction_policy,
    )


class ScopedBaselineRun(DomainModel):
    schema_version: Literal["phase1-scoped-baseline-run-v1"] = "phase1-scoped-baseline-run-v1"
    result_type: Literal["SCOPED_INFERENCE"] = "SCOPED_INFERENCE"
    method_id: str
    ablation_id: str | None
    authority: ScopedRouteAuthorityBinding
    frozen_config_sha256: Digest
    gap_binding: ScopedGapBinding
    navigation_content_sha256: Digest
    budget_lineage: ScopedBudgetLineage
    core_factors: GraphFactorMask
    topology_constraint: Literal["SOURCE_BOUND_SAME_CAMERA_HOLD"] = "SOURCE_BOUND_SAME_CAMERA_HOLD"
    camera_handoffs: Literal[0] = 0
    requested_k: int
    geometric_result: GeometricSearchResult
    timed_result: ReconstructionResult
    event: Event
    bound_gap: BoundGapEvent
    timing_unavailable_route_ids: tuple[str, ...]
    timed_metrics_status: Literal["AVAILABLE", "N/A_TIMING_UNAVAILABLE"]
    physical_records: tuple[RoutePhysicalRecord, ...]
    physical_scope_id: str
    production_class_search: ScopedClassSearchResult | None = None
    macro_navigation_content_sha256: Digest | None = None
    class_generation_complete: bool | None = None
    class_selection_truncated: bool | None = None
    collision_consumer_receipt: dict[str, Any] | None = None
    collision_filter_enabled: bool = False
    collision_filter_status: Literal["AVAILABLE", "N/A_NO_SEPARATE_APPROVED_COLLISION_CONSUMER"] = (
        "N/A_NO_SEPARATE_APPROVED_COLLISION_CONSUMER"
    )
    case_protocol_readiness_claimed: Literal[False] = False
    continuous_source_route_classes_exhaustive: Literal[False] = False
    ground_truth_read: Literal[False] = False


def run_scoped_baseline(
    gap: ScopedGapBinding,
    navigation: ScopedNavigationGraph,
    method_id: str,
    *,
    aggregation: ObservationAggregation,
    provider: ScopedUnionPhysicalProvider,
    config: ScopedInferenceConfig,
    frozen_config_sha256: str,
    ablation_id: str | None = None,
    collision_bundle: ReviewedCollisionBundle | None = None,
    projection_sidecar: Mapping[str, Any] | None = None,
    projection_observations_sha256: str | None = None,
    class_candidates: ScopedClassSearchResult | None = None,
    clock: Callable[[], float] = monotonic,
) -> ScopedBaselineRun:
    """Reuse core search/timing, while keeping HOLD and disabled core filter explicit."""
    prepared = _prepare_scoped_operation(provider, config.authority)
    provider = prepared.provider
    config = _validate_scoped_config(config, provider)
    if content_sha256(config.model_dump(mode="json")) != frozen_config_sha256:
        raise ValueError("scoped inference config differs from the pre-evaluation freeze")
    actual_gaps = bind_scoped_gaps(
        aggregation,
        provider,
        config,
        expected_stream_binding=gap.binding,
        projection_sidecar=projection_sidecar,
        projection_observations_sha256=projection_observations_sha256,
    )
    if gap not in actual_gaps:
        raise ValueError(
            "scoped GAP endpoints/recovery/interior differ from fresh source aggregation"
        )
    if ablation_id == "remove_topology":
        raise BaselineUnavailableError(
            ablation_id, ("SAME_CAMERA_HOLD_IS_SOURCE_BINDING_NOT_CAMERA_HANDOFF_FILTER",)
        )
    collision_consumers: tuple[CylinderCollisionConsumer, ...] = ()
    collision_receipt = None
    if collision_bundle is not None:
        snapshot = collision_bundle.validate_bindings(
            source_sha256=provider.source_sha256,
            local_certificate_content_sha256=provider.certificate_content_sha256,
            semantic_receipt_content_sha256=provider.semantic_review_content_sha256,
            floor_ids=(provider.proposal.floor.floor_id,),
            contract=provider.contract,
        )
        collision_consumers = snapshot.consumers
        collision_receipt = snapshot.receipt()
    if ablation_id == "remove_collision" and not collision_consumers:
        raise BaselineUnavailableError(
            ablation_id, ("NO_SEPARATE_APPROVED_COLLISION_FACTOR_UNION_BODY_GUARD_MUST_REMAIN",)
        )
    collision_enabled = bool(collision_consumers) and ablation_id != "remove_collision"
    capability = require_supported_baseline(method_id, ablation_id=ablation_id)
    assert capability.current_mask is not None
    factors = GraphFactorMask(
        travel_time_filter=(
            False
            if ablation_id == "remove_travel_time"
            else capability.current_mask.travel_time_filter
        ),
        camera_topology_filter=False,
    )
    pipeline = build_scoped_case_pipeline(gap, navigation, provider, config)
    macro_navigation_sha = None
    if class_candidates is not None:
        from amidst.finalization.formal_route_inventory import (
            _build_scoped_visibility_network,
            _source_hole_witness,
            source_winding_crossing,
        )

        if type(class_candidates) is not ScopedClassSearchResult:
            raise TypeError("class consumer requires production labels, never oracle outputs")
        class_candidates = ScopedClassSearchResult.model_validate_json(
            class_candidates.model_dump_json(),
        )
        visible_network, source_edges = _build_scoped_visibility_network(
            prepared,
            start_bu=navigation.endpoint_positions_bu[0],
            end_bu=navigation.endpoint_positions_bu[1],
            camera_ids=(gap.start.observation.camera_id,),
            spatial_context_id=gap.binding.spatial_context_id,
        )
        expected_query = class_search_query(
            start_bu=navigation.endpoint_positions_bu[0],
            end_bu=navigation.endpoint_positions_bu[1],
            camera_id=gap.start.observation.camera_id,
            gap_duration_s=(
                gap.end.observation.projected_path[0].timestamp
                - gap.start.observation.projected_path[-1].timestamp
            ),
            movement=config.movement,
            policy=config.search_policy,
            travel_time_filter=factors.travel_time_filter,
        )
        if class_candidates.authority != config.authority or (
            class_candidates.query_content_sha256 != content_sha256(expected_query)
            or class_candidates.source_edge_geometry_content_sha256 != content_sha256(source_edges)
            or class_candidates.navigation_content_sha256
            != content_sha256(
                visible_network.navigation.config.model_dump(mode="json"),
            )
            or class_candidates.metres_per_blender_unit != config.metres_per_blender_unit
        ):
            raise ValueError("production class labels differ from frozen source/GAP/budget/factors")
        witness = _source_hole_witness(prepared.provider, source_edges)
        if class_candidates.exact_hole_witness_xy_bu != witness:
            raise ValueError("production class witness differs from exact source-hole geometry")
        for item in class_candidates.classes:
            winding = sum(
                source_winding_crossing(a, b, witness) for a, b in pairwise(item.polyline_bu)
            )
            if winding != item.winding_signature:
                raise ValueError("production class label differs from its actual source winding")
        macro_network, _, _ = build_class_macro_network(class_candidates, visible_network)
        macro_navigation_sha = content_sha256(
            macro_network.navigation.config.model_dump(mode="json")
        )
        pipeline = PipelineConfig(
            navigation=macro_network.navigation.config,
            topology=macro_network.topology.config,
            movement=config.movement,
            search_policy=config.search_policy,
            reconstruction_policy=config.reconstruction_policy,
        )
    inputs = InferenceInput(
        dataset_id=gap.binding.source_id,
        random_seed=42,
        start_observation=gap.start.observation,
        end_observation=gap.end.observation,
        **pipeline.model_dump(mode="python"),
    )
    # Preserve the exact source coordinate for every graph point. Dividing an SI
    # boundary back to BU can move it outside an exact cell by one binary64 ULP.
    source_by_si: dict[Vec3, Coordinate] = {}
    ratio = config.metres_per_blender_unit
    for polyline in navigation.source_edge_polylines_bu.values():
        for point in polyline:
            source_by_si[(point[0] * ratio, point[1] * ratio, point[2] * ratio)] = point
    for point in navigation.endpoint_positions_bu:
        source_by_si[(point[0] * ratio, point[1] * ratio, point[2] * ratio)] = point
    records: list[RoutePhysicalRecord] = []

    def validate_route(polyline: tuple[Vec3, ...]) -> bool:
        if any(point not in source_by_si for point in polyline):
            raise ValueError("core route introduced a point outside exact scoped source geometry")
        prepared.validate_polyline(tuple(source_by_si[point] for point in polyline))
        if collision_enabled:
            for consumer in collision_consumers:
                decision = consumer.validate(polyline)
                if decision.state != "RETAINED":
                    records.append(
                        RoutePhysicalRecord(
                            polyline_m=polyline,
                            state=decision.state,
                            reasons=decision.reasons,
                        )
                    )
                    return False
        records.append(RoutePhysicalRecord(polyline_m=polyline, state="RETAINED"))
        return True

    network = NavigationNetwork(
        NavigationGraph(inputs.navigation), CameraTopologyGraph(inputs.topology)
    )
    engine = SpatiotemporalGraphEngine(
        network,
        inputs.movement,
        inputs.search_policy,
        clock=clock,
        factors=factors,
        route_filter=validate_route,
    )
    requested = config.search_policy.max_candidate_paths
    selected = (
        1 if capability.baseline_id == "A" or ablation_id == "shortest_path_only" else requested
    )
    geometry = engine.propose_geometric_routes(
        inputs.start_observation, inputs.end_observation, max_paths=selected
    )
    candidates = tuple(
        candidate
        for route in geometry.routes
        if (candidate := engine.timed_candidate(route)) is not None
    )
    # Keep the original disabled-core-filter flag as well as the independently
    # proven HOLD. Neither the candidate nor the run claims a camera handoff.
    candidates = tuple(
        candidate.model_copy(
            update={
                "feasibility_flags": (
                    "SOURCE_BOUND_SAME_CAMERA_HOLD",
                    "NO_CAMERA_HANDOFF",
                    *candidate.feasibility_flags,
                )
            }
        )
        for candidate in candidates
    )
    timed = ReconstructionResult(
        candidates=candidates,
        termination_reason=geometry.termination_reason,
        expanded_nodes=geometry.expanded_nodes,
        complete=geometry.complete,
        rejection_reasons=geometry.rejection_reasons,
    )
    event = BlindGapReconstructor(config.reconstruction_policy).reconstruct_gap(
        inputs.start_observation,
        inputs.end_observation,
        timed,
    )
    bound = BoundGapEvent(
        binding=gap.binding, start=gap.start, end=gap.end, search_result=timed, event=event
    )
    unavailable = tuple(
        route.candidate_id for route in geometry.routes if route.timing_status == "UNAVAILABLE"
    )
    return ScopedBaselineRun(
        method_id=method_id,
        ablation_id=ablation_id,
        authority=config.authority,
        frozen_config_sha256=frozen_config_sha256,
        gap_binding=gap,
        navigation_content_sha256=content_sha256(navigation.model_dump(mode="json")),
        budget_lineage=config.budget_lineage,
        core_factors=factors,
        requested_k=requested,
        geometric_result=geometry,
        timed_result=timed,
        event=event,
        bound_gap=bound,
        timing_unavailable_route_ids=unavailable,
        timed_metrics_status="N/A_TIMING_UNAVAILABLE" if unavailable else "AVAILABLE",
        physical_records=tuple(records),
        physical_scope_id=provider.scope_id,
        production_class_search=class_candidates,
        macro_navigation_content_sha256=macro_navigation_sha,
        class_generation_complete=(None if class_candidates is None else class_candidates.complete),
        class_selection_truncated=(
            None
            if class_candidates is None
            else len(class_candidates.classes) > config.search_policy.max_candidate_paths
        ),
        collision_consumer_receipt=collision_receipt,
        collision_filter_enabled=collision_enabled,
        collision_filter_status=(
            "AVAILABLE" if collision_consumers else "N/A_NO_SEPARATE_APPROVED_COLLISION_CONSUMER"
        ),
    )

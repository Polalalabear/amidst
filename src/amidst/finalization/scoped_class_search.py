"""Production canonical-class search, separate from the independent Dijkstra oracle.

A FIFO label-correcting relaxation works on the public source visibility graph.
It shares only exact source geometry/winding primitives with the reference
inventory. No reference inventory, GT, evaluation or recipe is an input.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable, Mapping
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, Vec3
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import CameraTopologyConfig
from amidst.finalization.formal_route_inventory import (
    _build_scoped_visibility_network,
    _prepare_scoped_operation,
    _source_hole_witness,
    source_winding_crossing,
)
from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import Coordinate, Digest


class ClassGenerationBudget(DomainModel):
    max_processed_labels: int = Field(default=100_000, gt=0)
    max_pending_labels: int = Field(default=100_000, gt=0)
    max_elapsed_s: FiniteFloat = Field(default=30, gt=0)


class ProducedClassPath(DomainModel):
    winding_signature: int
    source_edge_ids: tuple[str, ...] = Field(min_length=1)
    polyline_bu: tuple[Coordinate, ...] = Field(min_length=2)
    polyline_m: tuple[Vec3, ...] = Field(min_length=2)
    path_length_m: FiniteFloat = Field(gt=0)
    minimum_travel_time_s: FiniteFloat = Field(gt=0)
    timing_status: Literal["FEASIBLE", "UNAVAILABLE"]


class ScopedClassSearchResult(DomainModel):
    schema_version: Literal["phase1-production-canonical-class-search-v1"] = (
        "phase1-production-canonical-class-search-v1"
    )
    authority: ScopedRouteAuthorityBinding
    navigation_content_sha256: Digest
    topology_content_sha256: Digest
    source_edge_geometry_content_sha256: Digest
    query_content_sha256: Digest
    class_definition: Literal["FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST"] = (
        "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST"
    )
    production_algorithm: Literal["FIFO_LABEL_CORRECTING_RELAXATION"] = (
        "FIFO_LABEL_CORRECTING_RELAXATION"
    )
    start_bu: Coordinate
    end_bu: Coordinate
    camera_id: str
    gap_duration_s: FiniteFloat = Field(gt=0)
    metres_per_blender_unit: FiniteFloat = Field(gt=0)
    source_boundary_z_bu: FiniteFloat
    geometry_grammar: Literal["FLOOR_BOUNDARY_VISIBILITY_REPRESENTATIVE_GRAPH"] = (
        "FLOOR_BOUNDARY_VISIBILITY_REPRESENTATIVE_GRAPH"
    )
    movement: MovementConstraints
    policy: GraphSearchPolicy
    travel_time_filter: bool
    generation_budget: ClassGenerationBudget
    exact_hole_witness_xy_bu: tuple[str, str]
    classes: tuple[ProducedClassPath, ...]
    complete: bool
    termination_reason: Literal[
        "COMPLETE", "MAX_PROCESSED_LABELS", "MAX_PENDING_LABELS", "TIMEOUT",
    ]
    processed_labels: int = Field(ge=0)
    pending_labels: int = Field(ge=0)
    successful_relaxations: int = Field(ge=0)
    oracle_outputs_read: Literal[False] = False
    ground_truth_read: Literal[False] = False
    raw_core_budgets_modified: Literal[False] = False
    class_definition_requires_pre_evaluation_freeze: Literal[True] = True
    formal_case_readiness: Literal[False] = False

    @model_validator(mode="after")
    def class_and_geometry_contract(self) -> Self:
        if self.complete != (self.termination_reason == "COMPLETE"):
            raise ValueError("production class completion must match its termination")
        if len({item.winding_signature for item in self.classes}) != len(self.classes):
            raise ValueError("timing and null-winding walks cannot add class candidates")
        ratio = float(self.metres_per_blender_unit)
        for item in self.classes:
            if (item.polyline_bu[0], item.polyline_bu[-1]) != (self.start_bu, self.end_bu) or (
                item.polyline_m != tuple((p[0] * ratio, p[1] * ratio, p[2] * ratio)
                                        for p in item.polyline_bu)
            ):
                raise ValueError("production class path must retain exact source endpoints/scale")
        query = class_search_query(
            start_bu=self.start_bu, end_bu=self.end_bu, camera_id=self.camera_id,
            gap_duration_s=self.gap_duration_s, movement=self.movement, policy=self.policy,
            travel_time_filter=self.travel_time_filter,
        )
        if content_sha256(query) != self.query_content_sha256:
            raise ValueError("production class result query lineage differs")
        return self


def class_search_query(
    *, start_bu: Coordinate, end_bu: Coordinate, camera_id: str, gap_duration_s: float,
    movement: MovementConstraints, policy: GraphSearchPolicy, travel_time_filter: bool,
) -> dict[str, object]:
    """Explicit public source query for frozen producer lineage checks."""
    return {
        "start_bu": start_bu, "end_bu": end_bu, "camera_id": camera_id,
        "gap_duration_s": gap_duration_s, "movement": movement.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"), "travel_time_filter": travel_time_filter,
        "class_definition": "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST",
    }


def _over(value: float, bound: float) -> bool:
    return value > bound and value - bound > max(
        1e-12, 4 * max(math.ulp(value), math.ulp(bound)),
    )


def produce_scoped_class_candidates(
    provider: ScopedUnionPhysicalProvider, visibility_network: NavigationNetwork,
    source_edge_polylines_bu: Mapping[str, tuple[Coordinate, ...]], *,
    expected_binding: ScopedRouteAuthorityBinding, start_bu: Coordinate, end_bu: Coordinate,
    camera_id: str, gap_duration_s: float, movement: MovementConstraints,
    policy: GraphSearchPolicy, travel_time_filter: bool = True,
    generation_budget: ClassGenerationBudget | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> ScopedClassSearchResult:
    """Independently relax every reachable (node, winding) shortest-path label.

    Inference Top-K/search caps remain unchanged. This independent production
    generation budget has its own truncation receipt; partial labels cannot be
    advertised as a completed canonical-class generation.
    """
    prepared = _prepare_scoped_operation(provider, expected_binding)
    provider = prepared.provider
    rebuilt, mapping = _build_scoped_visibility_network(
        prepared, start_bu=start_bu, end_bu=end_bu,
        camera_ids=tuple(node.camera_id for node in visibility_network.topology.config.nodes),
        spatial_context_id=visibility_network.navigation.config.spatial_context_id,
    )
    if rebuilt.navigation.config != visibility_network.navigation.config or (
        rebuilt.topology.config != visibility_network.topology.config
        or mapping != dict(source_edge_polylines_bu)
    ):
        raise ValueError("production requires the complete pinned source visibility mapping")
    visibility_network = rebuilt
    if camera_id not in {node.camera_id for node in visibility_network.topology.config.nodes}:
        raise ValueError("production HOLD requires an actual approved source camera")
    if isinstance(gap_duration_s, bool) or not math.isfinite(gap_duration_s) or gap_duration_s <= 0:
        raise ValueError("observed GAP must be finite and positive")
    if not isinstance(travel_time_filter, bool):
        raise ValueError("production time factor must be boolean")
    movement = MovementConstraints.model_validate(movement.model_dump(mode="python"))
    policy = GraphSearchPolicy.model_validate(policy.model_dump(mode="python"))
    generation_budget = ClassGenerationBudget.model_validate(
        (generation_budget or ClassGenerationBudget()).model_dump(mode="python"),
    )
    witness = _source_hole_witness(provider, mapping)
    distances = {edge.edge_id: math.fsum(math.dist(a, b) for a, b in pairwise(edge.polyline))
                 for edge in visibility_network.navigation.config.edges}
    increments = {edge_id: sum(source_winding_crossing(a, b, witness)
                              for a, b in pairwise(points))
                  for edge_id, points in mapping.items()}
    time_ceiling = float(gap_duration_s) * float(movement.max_speed_m_s)
    if not math.isfinite(time_ceiling):
        raise ValueError("production speed distance ceiling must be finite")
    # Unlike the reference's priority queue, this is a FIFO label-correcting worklist.
    start_identity = "endpoint:start", 0
    queue = deque([start_identity])
    enqueued = {start_identity}
    labels: dict[tuple[str, int], tuple[float, tuple[str, ...]]] = {start_identity: (0., ())}
    processed, relaxations = 0, 0
    started = float(clock())
    last_time = started
    termination: Literal[
        "COMPLETE", "MAX_PROCESSED_LABELS", "MAX_PENDING_LABELS", "TIMEOUT",
    ] = "COMPLETE"
    while queue:
        now = float(clock())
        if not math.isfinite(started) or not math.isfinite(now) or now < last_time:
            raise ValueError("production generation clock must be finite and monotonic")
        last_time = now
        if now - started >= generation_budget.max_elapsed_s:
            termination = "TIMEOUT"
            break
        if processed >= generation_budget.max_processed_labels:
            termination = "MAX_PROCESSED_LABELS"
            break
        node_id, winding = queue.popleft()
        enqueued.remove((node_id, winding))
        processed += 1
        _, current_edges = labels[(node_id, winding)]
        for edge in visibility_network.navigation.outgoing_edges(node_id):
            proposed_edges = (*current_edges, edge.edge_id)
            proposed_distance = math.fsum(distances[identity] for identity in proposed_edges)
            if not math.isfinite(proposed_distance):
                raise ValueError("production label distance must remain finite")
            if _over(proposed_distance, policy.max_path_length_m) or (
                travel_time_filter and _over(proposed_distance, time_ceiling)
            ):
                continue
            next_identity = edge.to_node_id, winding + increments[edge.edge_id]
            proposed = proposed_distance, proposed_edges
            if next_identity in labels and labels[next_identity] <= proposed:
                continue
            if next_identity not in enqueued:
                if len(queue) >= generation_budget.max_pending_labels:
                    termination = "MAX_PENDING_LABELS"
                    break
                enqueued.add(next_identity)
                queue.append(next_identity)
            labels[next_identity] = proposed
            relaxations += 1
        if termination != "COMPLETE":
            break
    endpoint_labels = [(winding, distance, edge_ids)
                       for (node_id, winding), (distance, edge_ids) in labels.items()
                       if node_id == "endpoint:end"]
    shortest = min((distance for _, distance, _ in endpoint_labels), default=None)
    classes: list[ProducedClassPath] = []
    if shortest is not None:
        detour_limit = shortest * float(policy.max_detour_ratio)
        if not math.isfinite(detour_limit):
            raise ValueError("production detour ceiling must remain finite")
        for winding, distance, edge_ids in endpoint_labels:
            if _over(distance, detour_limit):
                continue
            path = visibility_network.navigation.path_from_edge_ids("endpoint:start", edge_ids)
            native = list(mapping[edge_ids[0]])
            for edge_id in edge_ids[1:]:
                native.extend(mapping[edge_id][1:])
            prepared.validate_polyline(tuple(native))
            minimum_time = distance / float(movement.max_speed_m_s)
            feasible = not _over(minimum_time, float(gap_duration_s))
            if travel_time_filter and not feasible:
                continue
            classes.append(ProducedClassPath(
                winding_signature=winding, source_edge_ids=edge_ids,
                polyline_bu=tuple(native), polyline_m=path.polyline,
                path_length_m=distance,
                minimum_travel_time_s=(min(minimum_time, gap_duration_s)
                                       if feasible else minimum_time),
                timing_status="FEASIBLE" if feasible else "UNAVAILABLE",
            ))
    query = class_search_query(
        start_bu=start_bu, end_bu=end_bu, camera_id=camera_id, gap_duration_s=gap_duration_s,
        movement=movement, policy=policy, travel_time_filter=travel_time_filter,
    )
    return ScopedClassSearchResult(
        authority=expected_binding,
        navigation_content_sha256=content_sha256(
            visibility_network.navigation.config.model_dump(mode="json"),
        ), topology_content_sha256=content_sha256(
            visibility_network.topology.config.model_dump(mode="json"),
        ), source_edge_geometry_content_sha256=content_sha256(dict(mapping)),
        query_content_sha256=content_sha256(query), start_bu=start_bu, end_bu=end_bu,
        camera_id=camera_id, gap_duration_s=gap_duration_s,
        metres_per_blender_unit=provider.contract.scale.metres_per_blender_unit,
        source_boundary_z_bu=provider.proposal.floor.point[2],
        movement=movement, policy=policy, travel_time_filter=travel_time_filter,
        generation_budget=generation_budget, exact_hole_witness_xy_bu=witness,
        classes=tuple(sorted(classes, key=lambda item: (item.path_length_m,
                                                       item.source_edge_ids,
                                                       item.winding_signature))),
        complete=termination == "COMPLETE", termination_reason=termination,
        processed_labels=processed, pending_labels=len(queue), successful_relaxations=relaxations,
    )


def build_class_macro_network(
    result: ScopedClassSearchResult, visibility_network: NavigationNetwork,
) -> tuple[NavigationNetwork, dict[str, tuple[Coordinate, ...]], dict[str, int]]:
    """Transport selected physical class paths through unchanged core Graph search.

    Internal navigation nodes have class/occurrence IDs while keeping their exact
    physical positions. The actual source camera has no alias or handoff. Splitting
    polylines into positive segments retains valid repeated winding coordinates
    without violating the original single-edge no-repeated-point contract.
    """
    result = ScopedClassSearchResult.model_validate_json(result.model_dump_json())
    if content_sha256(visibility_network.navigation.config.model_dump(mode="json")) != (
        result.navigation_content_sha256
    ) or content_sha256(visibility_network.topology.config.model_dump(mode="json")) != (
        result.topology_content_sha256
    ):
        raise ValueError("macro graph source visibility lineage differs from production result")
    ratio = float(result.metres_per_blender_unit)
    floor_id = visibility_network.navigation.node("endpoint:start").floor_id
    selected = result.classes[:result.policy.max_candidate_paths]
    nodes = [NavigationNode(
        node_id=identity, position=(point[0] * ratio, point[1] * ratio, point[2] * ratio),
        floor_id=floor_id,
    ) for identity, point in (("endpoint:start", result.start_bu), ("endpoint:end", result.end_bu))]
    edges: list[NavigationEdge] = []
    source_edges: dict[str, tuple[Coordinate, ...]] = {}
    class_for_edge: dict[str, int] = {}
    for class_index, item in enumerate(selected):
        raw_path = visibility_network.navigation.path_from_edge_ids(
            "endpoint:start", item.source_edge_ids,
        )
        if raw_path.polyline != item.polyline_m or raw_path.distance_m != item.path_length_m:
            raise ValueError("macro class must preserve the original physical source path/length")
        if any(point in (item.polyline_m[0], item.polyline_m[-1])
               for point in item.polyline_m[1:-1]):
            raise ValueError("canonical class path cannot alias a physical endpoint internally")
        node_ids = ["endpoint:start"]
        for index, position in enumerate(item.polyline_m[1:-1], start=1):
            identity = f"class:{item.winding_signature}:point:{index}"
            nodes.append(NavigationNode(node_id=identity, position=position, floor_id=floor_id))
            node_ids.append(identity)
        node_ids.append("endpoint:end")
        for segment_index, ((a_id, b_id), (a, b), (source_a, source_b)) in enumerate(zip(
            pairwise(node_ids), pairwise(item.polyline_m), pairwise(item.polyline_bu), strict=True,
        )):
            edge_id = f"class-macro:{class_index}:{segment_index}"
            edges.append(NavigationEdge(edge_id=edge_id, from_node_id=a_id, to_node_id=b_id,
                                        polyline=(a, b)))
            source_edges[edge_id] = source_a, source_b
            class_for_edge[edge_id] = item.winding_signature
    graph_id = f"scoped-class-macro:{content_sha256(result.model_dump(mode='json'))}"
    nav = NavigationGraph(NavigationGraphConfig(
        graph_id=graph_id,
        spatial_context_id=visibility_network.navigation.config.spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED,
        source_asset_sha256=visibility_network.navigation.config.source_asset_sha256,
        nodes=tuple(nodes), edges=tuple(edges),
    ))
    topology = CameraTopologyGraph(CameraTopologyConfig(
        **visibility_network.topology.config.model_dump(mode="python", exclude={
            "topology_id", "navigation_graph_id",
        }), topology_id=f"actual-camera-class-hold:{result.query_content_sha256}",
        navigation_graph_id=graph_id,
    ))
    return NavigationNetwork(nav, topology), source_edges, class_for_edge

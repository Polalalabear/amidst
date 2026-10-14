"""Independent bounded directed-walk inventory, without inference results or GT.

The denominator is the supplied navigation graph's eligible edge sequences, not
all continuous paths in a school or all homotopy classes. Repeated nodes/edges
and walks that leave a previously reached endpoint are retained. Positive edge
lengths and the length ceiling make this universe finite; separate oracle safety
limits must never be mistaken for an exhaustive denominator.
"""

from __future__ import annotations

import heapq
import math
import time
from collections import deque
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator
from shapely import from_wkb
from shapely.geometry import Polygon

from amidst.domain.common import DomainModel, Vec3
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import CameraTopologyConfig, CameraTopologyNode
from amidst.finalization.scoped_authority import (
    ScopedUnionPhysicalProvider,
    _physical,
    _segment_interval,
)
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import Coordinate, Digest, GeometryAuthorityError


class InventoryBudget(DomainModel):
    """Oracle resource bounds, independent of inference Top-K/search budgets."""

    max_expanded_states: int = Field(default=100_000, gt=0)
    max_pending_states: int = Field(default=100_000, gt=0)
    max_elapsed_s: FiniteFloat = Field(default=30, gt=0)


class InventoryRoute(DomainModel):
    edge_ids: tuple[str, ...]
    transition_ids: tuple[str, ...]
    polyline_m: tuple[Vec3, ...] = Field(min_length=2)
    path_length_m: FiniteFloat = Field(ge=0)
    minimum_travel_time_s: FiniteFloat = Field(ge=0)
    timing_status: Literal["FEASIBLE", "UNAVAILABLE"]


class FormalRouteInventory(DomainModel):
    schema_version: Literal["phase1-independent-directed-walk-inventory-v1"] = (
        "phase1-independent-directed-walk-inventory-v1"
    )
    navigation_content_sha256: Digest
    topology_content_sha256: Digest
    query_content_sha256: Digest
    authority: ScopedRouteAuthorityBinding | None = None
    source_edge_geometry_content_sha256: Digest | None = None
    inventory_scope: Literal["SUPPLIED_CANONICAL_GRAPH_ELIGIBLE_EDGE_SEQUENCES"] = (
        "SUPPLIED_CANONICAL_GRAPH_ELIGIBLE_EDGE_SEQUENCES"
    )
    routes: tuple[InventoryRoute, ...]
    complete: bool
    termination_reason: Literal[
        "COMPLETE", "MAX_EXPANDED_STATES", "MAX_PENDING_STATES", "TIMEOUT",
    ]
    expanded_states: int = Field(ge=0)
    pending_states: int = Field(ge=0)
    maximum_out_degree_seen: int = Field(ge=0)
    shortest_eligible_length_m: FiniteFloat | None = None
    detour_eligibility_certified: bool
    positive_edge_length_minimum_m: FiniteFloat | None = None
    policy: GraphSearchPolicy
    movement: MovementConstraints
    budget: InventoryBudget
    camera_topology_filter: bool
    travel_time_filter: bool
    inference_top_k_not_applied_to_denominator: Literal[True] = True
    repeated_edges_allowed: Literal[True] = True
    endpoint_is_not_absorbing: Literal[True] = True
    source_route_class_inventory_exhaustive: Literal[False] = False
    formal_case_readiness: Literal[False] = False
    graph_outputs_read: Literal[False] = False
    ground_truth_read: Literal[False] = False
    new_semantic_authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def consistent_completeness(self) -> Self:
        if self.complete != (self.termination_reason == "COMPLETE"):
            raise ValueError("inventory completeness must match its termination")
        if self.complete and self.pending_states:
            raise ValueError("exhaustive inventory cannot retain unexplored states")
        if self.detour_eligibility_certified != self.complete:
            raise ValueError("detour eligibility requires a complete shortest-route denominator")
        if len({route.edge_ids for route in self.routes}) != len(self.routes):
            raise ValueError("inventory denominator uses unique edge sequences")
        return self


def _exceeds(value: float, limit: float) -> bool:
    """Independently specified original Graph binary64 comparison contract."""
    tolerance = max(1e-12, 4 * max(math.ulp(value), math.ulp(limit)))
    return value > limit and value - limit > tolerance


def _finite_positive(value: float, label: str) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return float(value)


def enumerate_graph_route_inventory(
    network: NavigationNetwork, *, start_node_id: str, end_node_id: str,
    start_camera_id: str, end_camera_id: str, gap_duration_s: float,
    movement: MovementConstraints, policy: GraphSearchPolicy,
    camera_topology_filter: bool = True, travel_time_filter: bool = True,
    budget: InventoryBudget | None = None, clock: Callable[[], float] = time.monotonic,
) -> FormalRouteInventory:
    """Enumerate input graph walks with identical length/speed/detour/camera masks.

    This breadth-first oracle does not call the Graph engine, inspect its Top-K
    output or forbid repeated edges. Inference candidate/node/time/branch budgets
    are retained as metadata, not applied to this independent denominator. Only
    oracle resource exhaustion makes the inventory incomplete. Detour eligibility
    is applied after enumeration relative to the minimum *eligible* route length.
    """
    if not isinstance(network, NavigationNetwork):
        raise TypeError("inventory requires an intact NavigationNetwork")
    network = NavigationNetwork(
        NavigationGraph(network.navigation.config), CameraTopologyGraph(network.topology.config),
    )
    movement = MovementConstraints.model_validate(movement.model_dump(mode="python"))
    policy = GraphSearchPolicy.model_validate(policy.model_dump(mode="python"))
    budget = InventoryBudget.model_validate((budget or InventoryBudget()).model_dump(mode="python"))
    gap = _finite_positive(gap_duration_s, "observed GAP")
    if not isinstance(camera_topology_filter, bool) or not isinstance(travel_time_filter, bool):
        raise ValueError("inventory factor masks must be booleans")
    nav, topo = network.navigation.config, network.topology.config
    nodes = {node.node_id: node for node in nav.nodes}
    edges = {edge.edge_id: edge for edge in nav.edges}
    for node_id, camera_id in ((start_node_id, start_camera_id), (end_node_id, end_camera_id)):
        node = network.navigation.node(node_id)
        if node.floor_id != network.topology.node(camera_id).floor_id:
            raise ValueError("inventory endpoint camera and navigation floors differ")
    lengths = {
        edge.edge_id: math.fsum(math.dist(a, b) for a, b in pairwise(edge.polyline))
        for edge in nav.edges
    }
    allowed_by_speed = gap * float(movement.max_speed_m_s)
    if not math.isfinite(allowed_by_speed):
        raise ValueError("maximum traversable distance must be finite")
    cap = float(policy.max_path_length_m)
    started = float(clock())
    if not math.isfinite(started):
        raise ValueError("inventory clock must be finite")
    last_time = started
    # The complete edge sequence is part of identity: there is no visited-node DFS.
    queue: deque[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = deque([
        (start_camera_id, start_node_id, (), ()),
    ])
    seen: set[tuple[str, str, tuple[str, ...]]] = {(start_camera_id, start_node_id, ())}
    found: dict[tuple[str, ...], InventoryRoute] = {}
    expanded, maximum_degree = 0, 0
    termination: Literal[
        "COMPLETE", "MAX_EXPANDED_STATES", "MAX_PENDING_STATES", "TIMEOUT",
    ] = "COMPLETE"

    def geometry(sequence: tuple[str, ...]) -> tuple[tuple[Vec3, ...], float]:
        if not sequence:
            point = nodes[start_node_id].position
            return (point, point), 0.0
        points = list(edges[sequence[0]].polyline)
        for edge_id in sequence[1:]:
            points.extend(edges[edge_id].polyline[1:])
        distance = math.fsum(lengths[edge_id] for edge_id in sequence)
        if not math.isfinite(distance):
            raise ValueError("inventory path length must remain finite")
        return tuple(points), distance

    while queue:
        now = float(clock())
        if not math.isfinite(now) or now < last_time:
            raise ValueError("inventory clock must be finite and monotonic")
        last_time = now
        if now - started >= float(budget.max_elapsed_s):
            termination = "TIMEOUT"
            break
        if expanded >= budget.max_expanded_states:
            termination = "MAX_EXPANDED_STATES"
            break
        camera_id, node_id, sequence, transition_ids = queue.popleft()
        expanded += 1
        if node_id == end_node_id and (not camera_topology_filter or camera_id == end_camera_id):
            polyline, distance = geometry(sequence)
            minimum_time = distance / float(movement.max_speed_m_s)
            if not math.isfinite(minimum_time):
                raise ValueError("minimum travel time must remain finite")
            feasible = not _exceeds(minimum_time, gap)
            if feasible or not travel_time_filter:
                found.setdefault(sequence, InventoryRoute(
                    edge_ids=sequence, transition_ids=transition_ids, polyline_m=polyline,
                    path_length_m=distance,
                    minimum_travel_time_s=min(minimum_time, gap) if feasible else minimum_time,
                    timing_status="FEASIBLE" if feasible else "UNAVAILABLE",
                ))
        steps: tuple[tuple[str, str, tuple[str, ...], str | None], ...]
        if camera_topology_filter:
            steps = tuple(
                (transition.to_camera_id, transition.navigation_to_node_id,
                 transition.navigation_edge_ids, transition.transition_id)
                for transition in network.topology.outgoing_transitions(camera_id)
                if transition.navigation_from_node_id == node_id
            )
        else:
            steps = tuple((camera_id, edge.to_node_id, (edge.edge_id,), None)
                          for edge in network.navigation.outgoing_edges(node_id))
        maximum_degree = max(maximum_degree, len(steps))
        for next_camera, next_node, step_edges, transition_id in steps:
            new_sequence = (*sequence, *step_edges)
            _, distance = geometry(new_sequence)
            if _exceeds(distance, cap) or (
                travel_time_filter and _exceeds(distance, allowed_by_speed)
            ):
                continue
            key = next_camera, next_node, new_sequence
            if key in seen:
                continue
            if len(queue) >= budget.max_pending_states:
                termination = "MAX_PENDING_STATES"
                break
            seen.add(key)
            next_transitions = transition_ids if transition_id is None else (
                *transition_ids, transition_id,
            )
            queue.append((next_camera, next_node, new_sequence, next_transitions))
        if termination != "COMPLETE":
            # Even if the queue is empty, the refused next state is unexamined.
            break
    shortest = min((float(route.path_length_m) for route in found.values()), default=None)
    if shortest is not None:
        detour_cap = cap if shortest == 0 else shortest * float(policy.max_detour_ratio)
        if not math.isfinite(detour_cap):
            raise ValueError("maximum detour distance must remain finite")
        routes = tuple(sorted(
            (route for route in found.values() if not _exceeds(route.path_length_m, detour_cap)),
            key=lambda route: (route.path_length_m, route.edge_ids, route.transition_ids),
        ))
    else:
        routes = ()
    query = {
        "start_node_id": start_node_id, "end_node_id": end_node_id,
        "start_camera_id": start_camera_id, "end_camera_id": end_camera_id,
        "gap_duration_s": gap, "movement": movement.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"),
        "camera_topology_filter": camera_topology_filter, "travel_time_filter": travel_time_filter,
    }
    return FormalRouteInventory(
        navigation_content_sha256=content_sha256(nav.model_dump(mode="json")),
        topology_content_sha256=content_sha256(topo.model_dump(mode="json")),
        query_content_sha256=content_sha256(query), routes=routes,
        complete=termination == "COMPLETE", termination_reason=termination,
        expanded_states=expanded, pending_states=len(queue), maximum_out_degree_seen=maximum_degree,
        shortest_eligible_length_m=shortest,
        detour_eligibility_certified=termination == "COMPLETE",
        positive_edge_length_minimum_m=min(lengths.values(), default=None),
        policy=policy, movement=movement, budget=budget,
        camera_topology_filter=camera_topology_filter, travel_time_filter=travel_time_filter,
    )


def enumerate_formal_routes(
    provider: ScopedUnionPhysicalProvider, network: NavigationNetwork,
    source_edge_polylines_bu: Mapping[str, tuple[Coordinate, ...]], *,
    expected_binding: ScopedRouteAuthorityBinding,
    start_node_id: str, end_node_id: str, start_camera_id: str, end_camera_id: str,
    gap_duration_s: float, movement: MovementConstraints, policy: GraphSearchPolicy,
    camera_topology_filter: bool = True, travel_time_filter: bool = True,
    budget: InventoryBudget | None = None, clock: Callable[[], float] = time.monotonic,
) -> FormalRouteInventory:
    """Bind every graph segment to the existing approved union and exact SI scale.

    This certifies supplied graph geometry, not camera handoff/portal semantics or
    continuous route-class completeness. Disabled camera filtering retains its
    explicit factor identity; the caller must separately certify HOLD structure.
    """
    if not isinstance(provider, ScopedUnionPhysicalProvider):
        raise TypeError("formal inventory requires the intact approved union provider")
    prepared = _prepare_scoped_operation(provider, expected_binding)
    provider = prepared.provider
    binding = ScopedRouteAuthorityBinding(
        pins=provider.certificate.pins,
        proposal_content_sha256=provider.certificate.proposal_content_sha256,
        decision_content_sha256=provider.certificate.human_decision_content_sha256,
        certificate_content_sha256=provider.certificate_content_sha256,
        union_wkb_sha256=provider.certificate.union_wkb_sha256,
    )
    expected = ScopedRouteAuthorityBinding.model_validate_json(expected_binding.model_dump_json())
    if binding != expected:
        raise ValueError("formal inventory source/proposal/approval/certificate pins differ")
    if network.navigation.config.source_asset_sha256 != provider.source_sha256 or (
        network.topology.config.source_asset_sha256 != provider.source_sha256
    ):
        raise ValueError("inventory graph source differs from approved source")
    approved_cameras = {
        item.camera.camera_id for item in provider.proposal.camera_landmark_bindings
    }
    camera_ids = {node.camera_id for node in network.topology.config.nodes}
    if not camera_ids <= approved_cameras:
        raise ValueError("inventory graph camera lacks approved calibration/landmark binding")
    floor_id = provider.proposal.floor.floor_id
    if any(node.floor_id != floor_id for node in network.navigation.config.nodes) or any(
        node.floor_id != floor_id for node in network.topology.config.nodes
    ):
        raise ValueError("inventory graph leaves the approved same-floor scope")
    scale = float(provider.contract.scale.metres_per_blender_unit)
    graph_edges = {edge.edge_id: edge for edge in network.navigation.config.edges}
    if set(source_edge_polylines_bu) != set(graph_edges):
        raise ValueError("source geometry mapping must cover exactly every navigation edge")
    for edge_id, points_bu in source_edge_polylines_bu.items():
        prepared.validate_polyline(points_bu)
        normalized = tuple(tuple(value * scale for value in point) for point in points_bu)
        if normalized != graph_edges[edge_id].polyline:
            raise ValueError("navigation edge differs from exact source-BU to SI normalization")
    # Empty-edge endpoint paths still require physical scope coverage.
    for node_id in (start_node_id, end_node_id):
        position = network.navigation.node(node_id).position
        mapped = [point for edge_id, points in source_edge_polylines_bu.items()
                  for point, normalized in zip(points, graph_edges[edge_id].polyline, strict=True)
                  if normalized == position]
        if not mapped:
            raise ValueError("endpoint node requires an explicit source-edge geometry witness")
        prepared.validate_polyline((mapped[0], mapped[0]))
    inventory = enumerate_graph_route_inventory(
        network, start_node_id=start_node_id, end_node_id=end_node_id,
        start_camera_id=start_camera_id, end_camera_id=end_camera_id,
        gap_duration_s=gap_duration_s, movement=movement, policy=policy,
        camera_topology_filter=camera_topology_filter, travel_time_filter=travel_time_filter,
        budget=budget, clock=clock,
    )
    return inventory.model_copy(update={
        "authority": binding,
        "source_edge_geometry_content_sha256": content_sha256(dict(source_edge_polylines_bu)),
    })


def graph_edge_sequence_recall(
    inventory: FormalRouteInventory, emitted_sequences: tuple[tuple[str, ...], ...],
) -> dict[str, object]:
    """Calculate graph-universe recall only after independent inventory completion."""
    inventory = FormalRouteInventory.model_validate_json(inventory.model_dump_json())
    if not inventory.complete:
        return {"status": "N/A_TRUNCATED_INDEPENDENT_INVENTORY", "recall": None,
                "denominator": None, "matched": None}
    eligible = {route.edge_ids for route in inventory.routes}
    matched = len(eligible & set(emitted_sequences))
    return {"status": "AVAILABLE_SUPPLIED_GRAPH_EDGE_SEQUENCES" if eligible else (
                "N/A_EMPTY_ELIGIBLE_GRAPH_UNIVERSE"),
            "recall": matched / len(eligible) if eligible else None,
            "denominator": len(eligible), "matched": matched,
            "source_route_class_recall": None}


def _approved_binding(
    provider: ScopedUnionPhysicalProvider, expected: ScopedRouteAuthorityBinding,
) -> None:
    provider.validate()
    actual = ScopedRouteAuthorityBinding(
        pins=provider.certificate.pins,
        proposal_content_sha256=provider.certificate.proposal_content_sha256,
        decision_content_sha256=provider.certificate.human_decision_content_sha256,
        certificate_content_sha256=provider.certificate_content_sha256,
        union_wkb_sha256=provider.certificate.union_wkb_sha256,
    )
    if actual != ScopedRouteAuthorityBinding.model_validate_json(expected.model_dump_json()):
        raise ValueError("visibility graph source/proposal/approval/certificate pins differ")


@dataclass(frozen=True, slots=True)
class _PreparedScopedOperation:
    """Private detached intact authority, valid only inside one public operation."""

    provider: ScopedUnionPhysicalProvider

    def validate_polyline(self, points: tuple[Coordinate, ...]) -> bool:
        if len(points) < 2 or any(
            len(point) != 3 or any(isinstance(v, bool) or not math.isfinite(v) for v in point)
            for point in points
        ):
            raise ValueError("prepared scope requires at least two finite 3D footpoints")
        for start, end in pairwise(points):
            intervals = sorted(
                interval for proof in self.provider.certificate.cells
                if (interval := _segment_interval(
                    start, end, _physical(proof).footpoint_bounds_bu,
                )) is not None
            )
            covered = Fraction(0)
            for low, high in intervals:
                if low > covered:
                    break
                covered = max(covered, high)
            if not intervals or intervals[0][0] > 0 or covered < 1:
                raise GeometryAuthorityError(("OUTSIDE_APPROVED_LOCAL_UNION_OR_HOLE",))
            if not self.provider.domain.validate_segment(start, end).valid:
                raise GeometryAuthorityError(("OFF_APPROVED_BODY_CLEAR_WALKABLE",))
        return True


def _prepare_scoped_operation(
    provider: ScopedUnionPhysicalProvider, expected: ScopedRouteAuthorityBinding,
) -> _PreparedScopedOperation:
    _approved_binding(provider, expected)
    # Every semantic wrapper/certificate and the original support-domain model
    # remain intact. No caller can pass this snapshot instead of public authority.
    return _PreparedScopedOperation(deepcopy(provider))


def _segment_in_cells(
    start: Coordinate, end: Coordinate, provider: ScopedUnionPhysicalProvider,
) -> bool:
    """Exact rational segment coverage by closed approved rectangles, without epsilon."""
    a, b = tuple(Fraction(value) for value in start), tuple(Fraction(value) for value in end)
    intervals: list[tuple[Fraction, Fraction]] = []
    for cell in provider.proposal.cells:
        rectangle = tuple(Fraction(value) for value in cell.rectangle_xy_bu)
        low, high = Fraction(0), Fraction(1)
        for axis in range(2):
            delta = b[axis] - a[axis]
            if delta == 0:
                if not rectangle[axis] <= a[axis] <= rectangle[axis + 2]:
                    low, high = Fraction(1), Fraction(0)
                    break
            else:
                first = (rectangle[axis] - a[axis]) / delta
                last = (rectangle[axis + 2] - a[axis]) / delta
                low, high = max(low, min(first, last)), min(high, max(first, last))
        if low <= high:
            intervals.append((low, high))
    covered = Fraction(0)
    for low, high in sorted(intervals):
        if low > covered:
            break
        covered = max(covered, high)
    return bool(intervals) and sorted(intervals)[0][0] <= 0 and covered >= 1


def build_scoped_visibility_network(
    provider: ScopedUnionPhysicalProvider, *, expected_binding: ScopedRouteAuthorityBinding,
    start_bu: Coordinate, end_bu: Coordinate, camera_ids: tuple[str, ...],
    spatial_context_id: str,
) -> tuple[NavigationNetwork, dict[str, tuple[Coordinate, ...]]]:
    """Build all exact union-boundary vertices and all approved visible pair edges.

    Every polygon vertex is retained, including collinear vertices; endpoints are
    separate GT-free public inputs. Geometry stays in the exact approved union.
    No camera handoff is invented: topology has actual calibrated cameras and no
    transitions. Consumers must explicitly use geometric/HOLD factor semantics.
    """
    prepared = _prepare_scoped_operation(provider, expected_binding)
    return _build_scoped_visibility_network(
        prepared, start_bu=start_bu, end_bu=end_bu, camera_ids=camera_ids,
        spatial_context_id=spatial_context_id,
    )


def _build_scoped_visibility_network(
    prepared: _PreparedScopedOperation, *, start_bu: Coordinate, end_bu: Coordinate,
    camera_ids: tuple[str, ...], spatial_context_id: str,
) -> tuple[NavigationNetwork, dict[str, tuple[Coordinate, ...]]]:
    provider = prepared.provider
    union = from_wkb(bytes.fromhex(provider.certificate.union_wkb_hex))
    if not isinstance(union, Polygon) or not union.is_valid:
        raise ValueError("visibility mapping requires one valid approved polygon")
    z = provider.proposal.floor.point[2]
    if start_bu == end_bu:
        raise ValueError("visibility mapping requires distinct source endpoints")
    prepared.validate_polyline((start_bu, start_bu))
    prepared.validate_polyline((end_bu, end_bu))
    approved_cameras = {
        item.camera.camera_id for item in provider.proposal.camera_landmark_bindings
    }
    if not camera_ids or len(set(camera_ids)) != len(camera_ids) or not (
        set(camera_ids) <= approved_cameras
    ):
        raise ValueError("visibility mapping requires actual approved camera bindings")
    xs = {value for cell in provider.proposal.cells for value in (
        cell.rectangle_xy_bu[0], cell.rectangle_xy_bu[2],
    )}
    ys = {value for cell in provider.proposal.cells for value in (
        cell.rectangle_xy_bu[1], cell.rectangle_xy_bu[3],
    )}
    points: dict[str, Coordinate] = {"endpoint:start": start_bu, "endpoint:end": end_bu}
    for ring in (union.exterior, *union.interiors):
        for x, y in ring.coords[:-1]:
            if x not in xs or y not in ys:
                raise ValueError("union vertex is not an exact original cell-boundary intersection")
            point = float(x), float(y), z
            if point not in points.values():
                points[f"boundary:{content_sha256(point)}"] = point
    scale = float(provider.contract.scale.metres_per_blender_unit)
    nodes = tuple(NavigationNode(
        node_id=node_id, position=(point[0] * scale, point[1] * scale, point[2] * scale),
        floor_id=provider.proposal.floor.floor_id,
    ) for node_id, point in sorted(points.items()))
    node_by_id = {node.node_id: node for node in nodes}
    edges: list[NavigationEdge] = []
    source_edges: dict[str, tuple[Coordinate, ...]] = {}
    for from_id, start in sorted(points.items()):
        for to_id, end in sorted(points.items()):
            if from_id == to_id or not _segment_in_cells(start, end, provider):
                continue
            # A visible-in-union segment contradicting its numerical physical
            # provider stops mapping; it cannot silently become a missing edge.
            prepared.validate_polyline((start, end))
            edge_id = f"visibility:{content_sha256((from_id, to_id))}"
            source_edges[edge_id] = start, end
            edges.append(NavigationEdge(
                edge_id=edge_id, from_node_id=from_id, to_node_id=to_id,
                polyline=(node_by_id[from_id].position, node_by_id[to_id].position),
            ))
    graph_id = f"source-visibility:{content_sha256((points, source_edges))}"
    navigation = NavigationGraph(NavigationGraphConfig(
        graph_id=graph_id, spatial_context_id=spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED, source_asset_sha256=provider.source_sha256,
        nodes=nodes, edges=tuple(edges),
    ))
    topology = CameraTopologyGraph(CameraTopologyConfig(
        topology_id=f"actual-camera-hold:{content_sha256(sorted(camera_ids))}",
        navigation_graph_id=graph_id, spatial_context_id=spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED, source_asset_sha256=provider.source_sha256,
        nodes=tuple(CameraTopologyNode(camera_id=camera_id,
                                     floor_id=provider.proposal.floor.floor_id)
                    for camera_id in sorted(camera_ids)),
    ))
    return NavigationNetwork(navigation, topology), source_edges


class WindingClassRoute(DomainModel):
    winding_signature: int
    shortest_representative: InventoryRoute


class WindingClassInventory(DomainModel):
    schema_version: Literal["phase1-one-hole-canonical-shortest-winding-inventory-v1"] = (
        "phase1-one-hole-canonical-shortest-winding-inventory-v1"
    )
    authority: ScopedRouteAuthorityBinding
    navigation_content_sha256: Digest
    source_edge_geometry_content_sha256: Digest
    query_content_sha256: Digest
    class_definition: Literal["FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST"] = (
        "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST"
    )
    camera_eligibility: Literal["ACTUAL_SAME_CAMERA_HOLD_NO_DECLARED_TRANSITIONS"] = (
        "ACTUAL_SAME_CAMERA_HOLD_NO_DECLARED_TRANSITIONS"
    )
    source_union_hole_count: Literal[1] = 1
    endpoint_z_bu: tuple[FiniteFloat, FiniteFloat]
    source_boundary_z_bu: FiniteFloat
    metric_cover_scope: Literal[
        "CLOSED_FIXED_PLANE_POLYGON",
        "DECLARED_FLOOR_BOUNDARY_VISIBILITY_REPRESENTATIVE_GRAPH",
    ]
    source_mapping_method: Literal[
        "CLOSED_POLYGON_ALL_BOUNDARY_VERTICES_ALL_EXACT_VISIBLE_PAIRS",
    ] = "CLOSED_POLYGON_ALL_BOUNDARY_VERTICES_ALL_EXACT_VISIBLE_PAIRS"
    exact_hole_witness_xy_bu: tuple[str, str]
    routes: tuple[WindingClassRoute, ...]
    complete: bool
    termination_reason: Literal[
        "COMPLETE", "MAX_EXPANDED_STATES", "MAX_PENDING_STATES", "TIMEOUT",
    ]
    expanded_lifted_states: int
    declared_graph_class_inventory_exhaustive: bool
    source_route_class_inventory_exhaustive: bool
    policy: GraphSearchPolicy
    movement: MovementConstraints
    budget: InventoryBudget
    travel_time_filter: bool
    raw_graph_edge_sequences_redefined: Literal[False] = False
    class_definition_requires_pre_evaluation_freeze: Literal[True] = True
    formal_case_readiness: Literal[False] = False
    ground_truth_read: Literal[False] = False

    @model_validator(mode="after")
    def complete_class_denominator(self) -> Self:
        if self.complete != (self.termination_reason == "COMPLETE") or (
            self.declared_graph_class_inventory_exhaustive != self.complete
            or self.source_route_class_inventory_exhaustive != (
                self.complete and self.metric_cover_scope == "CLOSED_FIXED_PLANE_POLYGON"
            )
        ):
            raise ValueError("winding class completeness must agree with termination")
        if len({route.winding_signature for route in self.routes}) != len(self.routes):
            raise ValueError("timing and null-winding backtracks cannot increase class count")
        return self


def _ray_crossing(
    start: Coordinate, end: Coordinate, witness: tuple[Fraction, Fraction],
) -> int:
    ax, ay = Fraction(start[0]), Fraction(start[1])
    bx, by = Fraction(end[0]), Fraction(end[1])
    cross = (bx - ax) * (witness[1] - ay) - (by - ay) * (witness[0] - ax)
    return int(ay <= witness[1] < by and cross > 0) - int(by <= witness[1] < ay and cross < 0)


def source_winding_crossing(
    start_bu: Coordinate, end_bu: Coordinate, exact_witness_xy_bu: tuple[str, str],
) -> int:
    """Public exact geometry primitive, shared without sharing search results."""
    return _ray_crossing(start_bu, end_bu, (
        Fraction(exact_witness_xy_bu[0]), Fraction(exact_witness_xy_bu[1]),
    ))


def source_hole_witness(
    provider: ScopedUnionPhysicalProvider,
    source_edge_polylines_bu: Mapping[str, tuple[Coordinate, ...]],
) -> tuple[str, str]:
    """Choose an exact one-hole ray witness independently of inference or GT."""
    provider.validate()
    return _source_hole_witness(provider, source_edge_polylines_bu)


def _source_hole_witness(
    provider: ScopedUnionPhysicalProvider,
    source_edge_polylines_bu: Mapping[str, tuple[Coordinate, ...]],
) -> tuple[str, str]:
    union = from_wkb(bytes.fromhex(provider.certificate.union_wkb_hex))
    if not isinstance(union, Polygon) or len(union.interiors) != 1:
        raise ValueError("integer winding completeness requires exactly one source union hole")
    boundary = tuple((float(x), float(y), provider.proposal.floor.point[2])
                     for x, y in union.interiors[0].coords)
    xs = sorted({Fraction(point[0]) for point in boundary})
    ys = sorted({Fraction(point[1]) for points in source_edge_polylines_bu.values()
                 for point in points})
    witnesses = [((a + b) / 2, (c + d) / 2) for a, b in pairwise(xs)
                 for c, d in pairwise(ys)
                 if sum(_ray_crossing(s, e, ((a + b) / 2, (c + d) / 2))
                        for s, e in pairwise(boundary))]
    if not witnesses:
        raise ValueError("source hole lacks an exact open arrangement witness")
    witness = min(witnesses)
    return str(witness[0]), str(witness[1])


def enumerate_visibility_route_classes(
    provider: ScopedUnionPhysicalProvider, network: NavigationNetwork,
    source_edge_polylines_bu: Mapping[str, tuple[Coordinate, ...]], *,
    expected_binding: ScopedRouteAuthorityBinding, start_bu: Coordinate, end_bu: Coordinate,
    camera_id: str, gap_duration_s: float, movement: MovementConstraints,
    policy: GraphSearchPolicy, travel_time_filter: bool = True,
    budget: InventoryBudget | None = None, clock: Callable[[], float] = time.monotonic,
) -> WindingClassInventory:
    """Find every eligible shortest one-hole class on the complete visibility graph.

    A shortest path in a closed polygonal domain can bend only at boundary
    vertices: a bend in free interior admits a shorter local chord in its class.
    The all-vertices/all-visible-pairs graph therefore retains a shortest member
    of each fixed-endpoint homotopy class. For this single-hole union, integer
    winding is its complete class invariant. Dijkstra on (node, winding) avoids
    exponentially many null-winding backtracks while retaining arbitrary winding.
    This is an additive frozen class definition, never an alteration of raw
    Graph edge-sequence counts. With off-plane endpoint residuals accepted by the
    original physical guard, completeness covers only the declared graph whose
    internal boundary vertices stay at source floor Z, not the entire 3D Z band.
    Camera/portal semantics remain separate gates.
    """
    prepared = _prepare_scoped_operation(provider, expected_binding)
    provider = prepared.provider
    reconstructed, source_reconstructed = _build_scoped_visibility_network(
        prepared, start_bu=start_bu, end_bu=end_bu,
        camera_ids=tuple(node.camera_id for node in network.topology.config.nodes),
        spatial_context_id=network.navigation.config.spatial_context_id,
    )
    if reconstructed.navigation.config != network.navigation.config or (
        reconstructed.topology.config != network.topology.config
        or source_reconstructed != dict(source_edge_polylines_bu)
    ):
        raise ValueError("class inventory requires the complete source visibility mapping")
    network = reconstructed
    source_edge_polylines_bu = source_reconstructed
    if camera_id not in {node.camera_id for node in network.topology.config.nodes}:
        raise ValueError("HOLD inventory camera lacks actual approved source binding")
    # An exact arrangement-cell interior point avoids Shapely midpoint rounding
    # and avoids every graph vertex's ray height, including public endpoints.
    exact_witness = _source_hole_witness(prepared.provider, source_edge_polylines_bu)
    witness = Fraction(exact_witness[0]), Fraction(exact_witness[1])
    gap = _finite_positive(gap_duration_s, "observed GAP")
    movement = MovementConstraints.model_validate(movement.model_dump(mode="python"))
    policy = GraphSearchPolicy.model_validate(policy.model_dump(mode="python"))
    budget = InventoryBudget.model_validate((budget or InventoryBudget()).model_dump(mode="python"))
    lengths = {edge.edge_id: math.fsum(math.dist(a, b) for a, b in pairwise(edge.polyline))
               for edge in network.navigation.config.edges}
    crossings = {edge_id: sum(_ray_crossing(a, b, witness) for a, b in pairwise(points))
                 for edge_id, points in source_edge_polylines_bu.items()}
    cap = float(policy.max_path_length_m)
    speed_cap = gap * float(movement.max_speed_m_s)
    if not math.isfinite(speed_cap):
        raise ValueError("maximum traversable distance must be finite")
    queue: list[tuple[float, tuple[str, ...], str, int]] = [(0., (), "endpoint:start", 0)]
    best: dict[tuple[str, int], tuple[float, tuple[str, ...]]] = {("endpoint:start", 0): (0., ())}
    found: dict[int, InventoryRoute] = {}
    started = float(clock())
    last_time = started
    expanded = 0
    termination: Literal[
        "COMPLETE", "MAX_EXPANDED_STATES", "MAX_PENDING_STATES", "TIMEOUT",
    ] = "COMPLETE"
    shortest: float | None = None
    while queue:
        now = float(clock())
        if not math.isfinite(now) or not math.isfinite(started) or now < last_time:
            raise ValueError("class inventory clock must be finite and monotonic")
        last_time = now
        if now - started >= budget.max_elapsed_s:
            termination = "TIMEOUT"
            break
        distance, sequence, node_id, winding = heapq.heappop(queue)
        if best.get((node_id, winding)) != (distance, sequence):
            continue
        if expanded >= budget.max_expanded_states:
            termination = "MAX_EXPANDED_STATES"
            break
        expanded += 1
        if shortest is not None and _exceeds(distance, shortest * policy.max_detour_ratio):
            break
        if node_id == "endpoint:end":
            path = network.navigation.path_from_edge_ids("endpoint:start", sequence)
            minimum_time = distance / float(movement.max_speed_m_s)
            feasible = not _exceeds(minimum_time, gap)
            if not travel_time_filter or feasible:
                found.setdefault(winding, InventoryRoute(
                    edge_ids=sequence, transition_ids=(), polyline_m=path.polyline,
                    path_length_m=distance,
                    minimum_travel_time_s=min(minimum_time, gap) if feasible else minimum_time,
                    timing_status="FEASIBLE" if feasible else "UNAVAILABLE",
                ))
                if shortest is None:
                    shortest = distance
                    if not math.isfinite(shortest * policy.max_detour_ratio):
                        raise ValueError("maximum detour distance must be finite")
        for edge in network.navigation.outgoing_edges(node_id):
            next_sequence = (*sequence, edge.edge_id)
            next_distance = math.fsum(lengths[edge_id] for edge_id in next_sequence)
            if _exceeds(next_distance, cap) or (
                travel_time_filter and _exceeds(next_distance, speed_cap)
            ) or (shortest is not None and _exceeds(
                next_distance, shortest * policy.max_detour_ratio,
            )):
                continue
            next_winding = winding + crossings[edge.edge_id]
            identity = edge.to_node_id, next_winding
            candidate = next_distance, next_sequence
            if identity not in best or candidate < best[identity]:
                if len(queue) >= budget.max_pending_states:
                    termination = "MAX_PENDING_STATES"
                    break
                best[identity] = candidate
                heapq.heappush(queue, (*candidate, edge.to_node_id, next_winding))
        if termination != "COMPLETE":
            break
    query = {"start_bu": start_bu, "end_bu": end_bu, "camera_id": camera_id,
             "gap_duration_s": gap, "policy": policy.model_dump(mode="json"),
             "movement": movement.model_dump(mode="json"), "travel_time_filter": travel_time_filter,
             "class_definition": "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST"}
    return WindingClassInventory(
        authority=expected_binding,
        navigation_content_sha256=content_sha256(network.navigation.config.model_dump(mode="json")),
        source_edge_geometry_content_sha256=content_sha256(dict(source_edge_polylines_bu)),
        query_content_sha256=content_sha256(query),
        exact_hole_witness_xy_bu=(str(witness[0]), str(witness[1])),
        routes=tuple(WindingClassRoute(winding_signature=winding, shortest_representative=route)
                     for winding, route in sorted(found.items(), key=lambda item: (
                         item[1].path_length_m, item[1].edge_ids, item[0],
                     ))), complete=termination == "COMPLETE", termination_reason=termination,
        expanded_lifted_states=expanded, policy=policy, movement=movement,
        travel_time_filter=travel_time_filter, budget=budget,
        endpoint_z_bu=(start_bu[2], end_bu[2]),
        source_boundary_z_bu=provider.proposal.floor.point[2],
        metric_cover_scope=("CLOSED_FIXED_PLANE_POLYGON" if start_bu[2] == end_bu[2] == (
            provider.proposal.floor.point[2]
        ) else "DECLARED_FLOOR_BOUNDARY_VISIBILITY_REPRESENTATIVE_GRAPH"),
        declared_graph_class_inventory_exhaustive=termination == "COMPLETE",
        source_route_class_inventory_exhaustive=termination == "COMPLETE" and (
            start_bu[2] == end_bu[2] == provider.proposal.floor.point[2]
        ),
    )

"""Source-class eligibility intervals without changing actual projected endpoints.

XY geodesics lower-bound every 3D source path in its winding class. Existing
source-valid 3D representatives upper-bound that class's shortest path. Outward
binary64 bounds use exact squared coordinate differences, never a new research
epsilon. The original Graph comparison determines interval decidability.
"""

from __future__ import annotations

import heapq
import math
import time
from collections.abc import Callable, Mapping
from fractions import Fraction
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.finalization.formal_route_inventory import (
    InventoryBudget,
    _build_scoped_visibility_network,
    _prepare_scoped_operation,
    _source_hole_witness,
    source_winding_crossing,
)
from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.navigation.network import NavigationNetwork
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import Coordinate, Digest


class SourceClassEligibilityInterval(DomainModel):
    winding_signature: int
    xy_geodesic_lower_m: FiniteFloat = Field(ge=0)
    minkowski_3d_lower_m: FiniteFloat = Field(ge=0)
    source_valid_3d_upper_m: FiniteFloat | None = None
    xy_lower_edge_ids: tuple[str, ...]
    source_upper_edge_ids: tuple[str, ...] | None = None
    verdict: Literal["ELIGIBLE", "INELIGIBLE", "UNDECIDABLE"]


class SourceClassEligibilityCertificate(DomainModel):
    schema_version: Literal["phase1-source-class-eligibility-interval-certificate-v1"] = (
        "phase1-source-class-eligibility-interval-certificate-v1"
    )
    authority: ScopedRouteAuthorityBinding
    navigation_content_sha256: Digest
    source_edge_geometry_content_sha256: Digest
    query_content_sha256: Digest
    exact_hole_witness_xy_bu: tuple[str, str]
    endpoint_positions_bu: tuple[Coordinate, Coordinate]
    source_boundary_z_bu: FiniteFloat
    policy: GraphSearchPolicy
    movement: MovementConstraints
    travel_time_filter: bool
    budget: InventoryBudget
    global_shortest_lower_m: FiniteFloat | None
    global_source_valid_shortest_upper_m: FiniteFloat | None
    safe_xy_enumeration_ceiling_m: FiniteFloat | None
    definitely_eligible_ceiling_m: FiniteFloat | None
    possibly_eligible_ceiling_m: FiniteFloat | None
    class_intervals: tuple[SourceClassEligibilityInterval, ...]
    eligible_winding_signatures: tuple[int, ...]
    ambiguous_winding_signatures: tuple[int, ...]
    xy_inventory_complete: bool
    source_valid_3d_upper_inventory_complete: bool
    recall_denominator_complete: bool
    source_eligible_class_count: int | None = Field(default=None, ge=0)
    metric_cover_scope: Literal[
        "XY_LOWER_SOURCE_VALID_3D_UPPER_ELIGIBILITY_INTERVAL_CERTIFIED",
        "SOURCE_CLASS_ELIGIBILITY_INTERVAL_UNDECIDABLE",
    ]
    numerical_bounds: Literal["EXACT_SQUARED_NORMS_OUTWARD_BINARY64_NO_NEW_EPSILON"] = (
        "EXACT_SQUARED_NORMS_OUTWARD_BINARY64_NO_NEW_EPSILON"
    )
    population_scope: Literal["SAME_APPROVED_UNION_FIXED_ENDPOINT_SOURCE_WINDING_CLASSES"] = (
        "SAME_APPROVED_UNION_FIXED_ENDPOINT_SOURCE_WINDING_CLASSES"
    )
    xy_population_content_sha256: Digest
    source_3d_upper_population_content_sha256: Digest
    phase_receipts: dict[str, dict[str, object]]
    candidate_endpoint_positions_modified: Literal[False] = False
    source_z_band_shortest_exactness_claimed: Literal[False] = False
    ground_truth_read: Literal[False] = False
    production_outputs_read: Literal[False] = False
    formal_case_readiness: Literal[False] = False

    @model_validator(mode="after")
    def denominator_contract(self) -> Self:
        expected = (
            self.xy_inventory_complete and self.source_valid_3d_upper_inventory_complete
            and not self.ambiguous_winding_signatures
        )
        if self.recall_denominator_complete != expected or (
            self.source_eligible_class_count != (
                len(self.eligible_winding_signatures) if expected else None
            )
        ):
            raise ValueError("source recall denominator requires exhaustive decidable intervals")
        if self.metric_cover_scope != (
            "XY_LOWER_SOURCE_VALID_3D_UPPER_ELIGIBILITY_INTERVAL_CERTIFIED" if expected
            else "SOURCE_CLASS_ELIGIBILITY_INTERVAL_UNDECIDABLE"
        ):
            raise ValueError("metric-cover status must match denominator completeness")
        return self


def _float_bound(value: Fraction, *, upper: bool) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("source interval bounds must remain finite")
    direction = math.inf if upper else -math.inf
    while (Fraction(result) < value) if upper else (Fraction(result) > value):
        result = math.nextafter(result, direction)
    return result


def _sqrt_bound(squared: Fraction, *, upper: bool) -> float:
    if squared == 0:
        return 0.
    # Rational squared quantities can underflow/overflow when cast before sqrt.
    # Decimal is used only for the initial estimate; exact rational inequalities
    # below determine the outward result, without a precision-based tolerance.
    from decimal import Decimal, localcontext
    with localcontext() as context:
        context.prec = 80
        estimate = (Decimal(squared.numerator) / Decimal(squared.denominator)).sqrt()
        result = float(estimate)
    if not math.isfinite(result):
        raise ValueError("source norm bounds must remain finite")
    direction = math.inf if upper else -math.inf
    while ((Fraction(result) ** 2 < squared) if upper else (Fraction(result) ** 2 > squared)):
        result = math.nextafter(result, direction)
    return result


def _over(value: float, bound: float) -> bool:
    return value > bound and value - bound > max(
        1e-12, 4 * max(math.ulp(value), math.ulp(bound)),
    )


def _metric_labels(
    network: NavigationNetwork, weights: dict[str, Fraction], increments: dict[str, int], *,
    ceiling: float | None, budget: InventoryBudget, clock: Callable[[], float],
    first_endpoint_only: bool = False,
) -> tuple[dict[int, tuple[Fraction, tuple[str, ...]]], dict[str, object]]:
    # Min-hop before lexical tie makes nonnegative XY zero cycles stable. Actual
    # positive 3D edges are retained in both populations, including vertical edges.
    queue: list[tuple[Fraction, int, tuple[str, ...], str, int]] = [
        (Fraction(0), 0, (), "endpoint:start", 0),
    ]
    best: dict[tuple[str, int], tuple[Fraction, int, tuple[str, ...]]] = {
        ("endpoint:start", 0): (Fraction(0), 0, ()),
    }
    found: dict[int, tuple[Fraction, tuple[str, ...]]] = {}
    expanded = 0
    started = float(clock())
    last_time = started
    status = "COMPLETE"
    while queue:
        now = float(clock())
        if not math.isfinite(now) or not math.isfinite(started) or now < last_time:
            raise ValueError("interval inventory clock must be finite and monotonic")
        last_time = now
        if now - started >= budget.max_elapsed_s:
            status = "TIMEOUT"
            break
        distance, hops, sequence, node_id, winding = heapq.heappop(queue)
        if best.get((node_id, winding)) != (distance, hops, sequence):
            continue
        if expanded >= budget.max_expanded_states:
            status = "MAX_EXPANDED_STATES"
            break
        expanded += 1
        if node_id == "endpoint:end":
            found.setdefault(winding, (distance, sequence))
            if first_endpoint_only:
                break
        for edge in network.navigation.outgoing_edges(node_id):
            proposed = distance + weights[edge.edge_id]
            if ceiling is not None and _over(_float_bound(proposed, upper=False), ceiling):
                continue
            signature = winding + increments[edge.edge_id]
            next_sequence = (*sequence, edge.edge_id)
            key = edge.to_node_id, signature
            label = proposed, hops + 1, next_sequence
            if key in best and best[key] <= label:
                continue
            if len(queue) >= budget.max_pending_states:
                status = "MAX_PENDING_STATES"
                break
            best[key] = label
            heapq.heappush(queue, (*label, edge.to_node_id, signature))
        if status != "COMPLETE":
            break
    return found, {"status": status, "complete": status == "COMPLETE",
                   "expanded_states": expanded, "pending_states": len(queue),
                   "first_endpoint_only": first_endpoint_only}


def certify_source_class_eligibility_intervals(
    provider: ScopedUnionPhysicalProvider, network: NavigationNetwork,
    source_edge_polylines_bu: Mapping[str, tuple[Coordinate, ...]], *,
    expected_binding: ScopedRouteAuthorityBinding, start_bu: Coordinate, end_bu: Coordinate,
    camera_id: str, gap_duration_s: float, movement: MovementConstraints,
    policy: GraphSearchPolicy, travel_time_filter: bool = True,
    budget: InventoryBudget | None = None, clock: Callable[[], float] = time.monotonic,
) -> SourceClassEligibilityCertificate:
    """Classify source eligibility only where XY/3D intervals resolve every class.

    Global shortest length is enclosed by the minimum planar/Minkowski lower and
    a valid 3D representative upper. A class upper below every lower eligibility
    ceiling proves eligibility; a class lower above any upper ceiling proves
    ineligibility. Remaining overlap yields N/A, never a fabricated denominator.
    """
    prepared = _prepare_scoped_operation(provider, expected_binding)
    provider = prepared.provider
    rebuilt, mapping = _build_scoped_visibility_network(
        prepared, start_bu=start_bu, end_bu=end_bu,
        camera_ids=tuple(node.camera_id for node in network.topology.config.nodes),
        spatial_context_id=network.navigation.config.spatial_context_id,
    )
    if rebuilt.navigation.config != network.navigation.config or (
        rebuilt.topology.config != network.topology.config
        or mapping != dict(source_edge_polylines_bu)
    ):
        raise ValueError("interval certificate requires complete pinned source visibility mapping")
    network = rebuilt
    if camera_id not in {node.camera_id for node in network.topology.config.nodes}:
        raise ValueError("interval certificate requires an actual approved HOLD camera")
    if isinstance(gap_duration_s, bool) or not math.isfinite(gap_duration_s) or gap_duration_s <= 0:
        raise ValueError("interval GAP must be finite and positive")
    if not isinstance(travel_time_filter, bool):
        raise ValueError("interval time factor must be boolean")
    movement = MovementConstraints.model_validate(movement.model_dump(mode="python"))
    policy = GraphSearchPolicy.model_validate(policy.model_dump(mode="python"))
    budget = InventoryBudget.model_validate((budget or InventoryBudget()).model_dump(mode="python"))
    witness = _source_hole_witness(provider, mapping)
    increments = {edge_id: sum(source_winding_crossing(a, b, witness)
                              for a, b in pairwise(points))
                  for edge_id, points in mapping.items()}
    lower_weights: dict[str, Fraction] = {}
    upper_weights: dict[str, Fraction] = {}
    for edge in network.navigation.config.edges:
        xy_lower, physical_upper = Fraction(0), Fraction(0)
        for start, end in pairwise(edge.polyline):
            delta = tuple(Fraction(end[axis]) - Fraction(start[axis]) for axis in range(3))
            xy_lower += Fraction(_sqrt_bound(delta[0] ** 2 + delta[1] ** 2, upper=False))
            physical_upper += Fraction(_sqrt_bound(
                sum((value ** 2 for value in delta), start=Fraction(0)), upper=True,
            ))
        lower_weights[edge.edge_id], upper_weights[edge.edge_id] = xy_lower, physical_upper
    global_upper_paths, global_receipt = _metric_labels(
        network, upper_weights, increments, ceiling=None, budget=budget, clock=clock,
        first_endpoint_only=True,
    )
    global_upper = _float_bound(min((value[0] for value in global_upper_paths.values()),
                                  default=Fraction(0)), upper=True) if global_upper_paths else None
    hard_ceiling = float(policy.max_path_length_m)
    if travel_time_filter:
        time_ceiling = float(gap_duration_s) * float(movement.max_speed_m_s)
        if not math.isfinite(time_ceiling):
            raise ValueError("interval speed ceiling must remain finite")
        hard_ceiling = min(hard_ceiling, time_ceiling)
    if global_upper is not None:
        detour_upper = _float_bound(Fraction(global_upper) * Fraction(policy.max_detour_ratio),
                                   upper=True)
        safe_ceiling = min(hard_ceiling, detour_upper)
    else:
        safe_ceiling = hard_ceiling
    xy_paths, xy_receipt = _metric_labels(
        network, lower_weights, increments, ceiling=safe_ceiling, budget=budget, clock=clock,
    )
    upper_paths, upper_receipt = _metric_labels(
        network, upper_weights, increments, ceiling=safe_ceiling, budget=budget, clock=clock,
    )
    start_z = Fraction(network.navigation.node("endpoint:start").position[2])
    end_z = Fraction(network.navigation.node("endpoint:end").position[2])
    lowers = {signature: _sqrt_bound(distance ** 2 + (end_z - start_z) ** 2, upper=False)
              for signature, (distance, _) in xy_paths.items()}
    global_lower = min(lowers.values(), default=None)
    definitely_eligible = min(hard_ceiling, _float_bound(
        Fraction(global_lower) * Fraction(policy.max_detour_ratio), upper=False,
    )) if global_lower is not None else None
    possibly_eligible = safe_ceiling
    intervals = []
    for signature, (xy_lower, sequence) in sorted(xy_paths.items()):
        upper_record = upper_paths.get(signature)
        upper = _float_bound(upper_record[0], upper=True) if upper_record is not None else None
        lower = lowers[signature]
        if _over(lower, possibly_eligible):
            verdict: Literal["ELIGIBLE", "INELIGIBLE", "UNDECIDABLE"] = "INELIGIBLE"
        elif upper is not None and definitely_eligible is not None and not _over(
            upper, definitely_eligible,
        ):
            verdict = "ELIGIBLE"
        else:
            verdict = "UNDECIDABLE"
        intervals.append(SourceClassEligibilityInterval(
            winding_signature=signature, xy_geodesic_lower_m=_float_bound(xy_lower, upper=False),
            minkowski_3d_lower_m=lower, source_valid_3d_upper_m=upper,
            xy_lower_edge_ids=sequence,
            source_upper_edge_ids=upper_record[1] if upper_record else None, verdict=verdict,
        ))
    eligible = tuple(item.winding_signature for item in intervals if item.verdict == "ELIGIBLE")
    ambiguous = tuple(item.winding_signature for item in intervals if item.verdict == "UNDECIDABLE")
    xy_complete = bool(xy_receipt["complete"]) and bool(global_receipt["complete"])
    upper_complete = bool(upper_receipt["complete"]) and bool(global_receipt["complete"])
    complete = xy_complete and upper_complete and not ambiguous
    query = {"start_bu": start_bu, "end_bu": end_bu, "camera_id": camera_id,
             "gap_duration_s": gap_duration_s, "movement": movement.model_dump(mode="json"),
             "policy": policy.model_dump(mode="json"), "travel_time_filter": travel_time_filter,
             "class_definition": "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST"}
    return SourceClassEligibilityCertificate(
        authority=expected_binding,
        navigation_content_sha256=content_sha256(network.navigation.config.model_dump(mode="json")),
        source_edge_geometry_content_sha256=content_sha256(mapping),
        query_content_sha256=content_sha256(query), exact_hole_witness_xy_bu=witness,
        endpoint_positions_bu=(start_bu, end_bu),
        source_boundary_z_bu=provider.proposal.floor.point[2],
        policy=policy, movement=movement, travel_time_filter=travel_time_filter, budget=budget,
        global_shortest_lower_m=global_lower, global_source_valid_shortest_upper_m=global_upper,
        safe_xy_enumeration_ceiling_m=safe_ceiling,
        definitely_eligible_ceiling_m=definitely_eligible,
        possibly_eligible_ceiling_m=possibly_eligible, class_intervals=tuple(intervals),
        eligible_winding_signatures=eligible, ambiguous_winding_signatures=ambiguous,
        xy_inventory_complete=xy_complete, source_valid_3d_upper_inventory_complete=upper_complete,
        recall_denominator_complete=complete, source_eligible_class_count=len(eligible) if complete
        else None, metric_cover_scope=(
            "XY_LOWER_SOURCE_VALID_3D_UPPER_ELIGIBILITY_INTERVAL_CERTIFIED" if complete
            else "SOURCE_CLASS_ELIGIBILITY_INTERVAL_UNDECIDABLE"
        ), xy_population_content_sha256=content_sha256([
            (signature, str(distance), edges)
            for signature, (distance, edges) in sorted(xy_paths.items())
        ]), source_3d_upper_population_content_sha256=content_sha256([
            (signature, str(distance), edges)
            for signature, (distance, edges) in sorted(upper_paths.items())
        ]), phase_receipts={"global_upper": global_receipt, "xy_lower": xy_receipt,
                           "source_valid_3d_upper": upper_receipt},
    )

"""Off-plane source eligibility uses bounds, never snapped candidate endpoints."""

from fractions import Fraction
from typing import Any

import pytest
from test_formal_route_inventory import approved_ring as approved_ring

from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.finalization.formal_route_inventory import (
    InventoryBudget,
    build_scoped_visibility_network,
)
from amidst.finalization.source_class_eligibility import (
    _float_bound,
    _sqrt_bound,
    certify_source_class_eligibility_intervals,
)


def _certificate(approved_ring: Any, *, residual: float = .0009,
                 end_xy: tuple[float, float] = (7.75, 5.),
                 max_length: float = 100., budget: InventoryBudget | None = None) -> Any:
    provider, binding = approved_ring
    start, end = (2.25, 5., residual), (*end_xy, -residual)
    network, mapping = build_scoped_visibility_network(
        provider, expected_binding=binding, start_bu=start, end_bu=end, camera_ids=("A",),
        spatial_context_id="SYNTHETIC_SOURCE_INTERVAL_TEST",
    )
    result = certify_source_class_eligibility_intervals(
        provider, network, mapping, expected_binding=binding, start_bu=start, end_bu=end,
        camera_id="A", gap_duration_s=100., movement=MovementConstraints(max_speed_m_s=1.),
        policy=GraphSearchPolicy(max_path_length_m=max_length, max_detour_ratio=2.),
        budget=budget, clock=lambda: 0.,
    )
    return result, network


@pytest.mark.parametrize("squared", [
    Fraction(2), Fraction(1, 10 ** 640), Fraction(10 ** 600),
    Fraction.from_float(.0009) ** 2,
])
def test_outward_norm_bounds_use_exact_inequalities_without_epsilon(squared: Fraction) -> None:
    lower = _sqrt_bound(squared, upper=False)
    upper = _sqrt_bound(squared, upper=True)
    assert Fraction(lower) ** 2 <= squared <= Fraction(upper) ** 2
    assert lower <= upper


def test_rational_sum_bounds_are_directed() -> None:
    value = Fraction(1, 10)
    assert Fraction(_float_bound(value, upper=False)) <= value
    assert Fraction(_float_bound(value, upper=True)) >= value


def test_larger_legal_z_residual_keeps_two_eligible_classes_and_real_endpoints(
    approved_ring: Any,
) -> None:
    result, network = _certificate(approved_ring)
    assert result.recall_denominator_complete and result.source_eligible_class_count == 2
    assert result.metric_cover_scope == (
        "XY_LOWER_SOURCE_VALID_3D_UPPER_ELIGIBILITY_INTERVAL_CERTIFIED"
    )
    assert not result.ambiguous_winding_signatures
    assert result.xy_inventory_complete and result.source_valid_3d_upper_inventory_complete
    assert network.navigation.node("endpoint:start").position[2] == .0009
    assert network.navigation.node("endpoint:end").position[2] == -.0009
    assert result.candidate_endpoint_positions_modified is False
    assert result.source_z_band_shortest_exactness_claimed is False
    for item in result.class_intervals:
        assert item.verdict == "ELIGIBLE"
        assert item.xy_geodesic_lower_m < item.minkowski_3d_lower_m
        assert item.source_valid_3d_upper_m is not None
        assert item.minkowski_3d_lower_m <= item.source_valid_3d_upper_m


def test_near_threshold_overlap_is_undecidable_not_zero_or_fabricated_recall(
    approved_ring: Any,
) -> None:
    wide, _ = _certificate(approved_ring)
    interval = wide.class_intervals[0]
    assert interval.source_valid_3d_upper_m is not None
    threshold = (interval.minkowski_3d_lower_m + interval.source_valid_3d_upper_m) / 2
    ambiguous, _ = _certificate(approved_ring, max_length=threshold)
    assert ambiguous.xy_inventory_complete and ambiguous.source_valid_3d_upper_inventory_complete
    assert not ambiguous.recall_denominator_complete
    assert ambiguous.source_eligible_class_count is None
    assert ambiguous.ambiguous_winding_signatures
    assert all(item.verdict == "UNDECIDABLE" for item in ambiguous.class_intervals)


def test_lower_above_threshold_certifies_empty_eligible_population(approved_ring: Any) -> None:
    wide, _ = _certificate(approved_ring)
    interval = wide.class_intervals[0]
    threshold = (interval.xy_geodesic_lower_m + interval.minkowski_3d_lower_m) / 2
    empty, _ = _certificate(approved_ring, max_length=threshold)
    assert empty.recall_denominator_complete and empty.source_eligible_class_count == 0
    assert all(item.verdict == "INELIGIBLE" for item in empty.class_intervals)


def test_positive_vertical_edge_keeps_zero_xy_label_stable(approved_ring: Any) -> None:
    result, network = _certificate(approved_ring, end_xy=(2.25, 5.))
    assert result.recall_denominator_complete and result.source_eligible_class_count == 1
    assert result.class_intervals[0].xy_geodesic_lower_m == 0.
    assert result.class_intervals[0].minkowski_3d_lower_m > 0.
    direct = [edge for edge in network.navigation.config.edges if edge.from_node_id == (
        "endpoint:start"
    ) and edge.to_node_id == "endpoint:end"]
    assert direct and network.navigation.edge_length(direct[0].edge_id) > 0.
    assert result.phase_receipts["xy_lower"]["expanded_states"] < 100


def test_interval_oracle_budget_truncation_keeps_denominator_unavailable(
    approved_ring: Any,
) -> None:
    result, _ = _certificate(approved_ring, budget=InventoryBudget(max_expanded_states=2))
    assert not result.recall_denominator_complete
    assert result.source_eligible_class_count is None
    assert not result.xy_inventory_complete or not result.source_valid_3d_upper_inventory_complete

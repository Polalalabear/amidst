"""Production class relaxation is independent from its reference inventory."""

from typing import Any

import pytest
from test_formal_route_inventory import (
    _classes,
)
from test_formal_route_inventory import (
    approved_ring as approved_ring,
)
from test_formal_route_inventory import (
    visibility_ring as visibility_ring,
)
from test_graph_engine import _endpoints

import amidst.finalization.formal_route_inventory as reference_inventory
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.trajectory import TerminationReason
from amidst.finalization.scoped_class_search import (
    ClassGenerationBudget,
    ScopedClassSearchResult,
    build_class_macro_network,
    produce_scoped_class_candidates,
)
from amidst.graph.engine import GraphFactorMask, SpatiotemporalGraphEngine
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.reconstruction.blind_gap import BlindGapReconstructor


def _produce(visibility_ring: Any, **changes: Any) -> ScopedClassSearchResult:
    provider, binding, network, mapping = visibility_ring
    args = dict(
        expected_binding=binding, start_bu=(2.25, 5., 0.), end_bu=(7.75, 5., 0.),
        camera_id="A", gap_duration_s=100., movement=MovementConstraints(max_speed_m_s=1.),
        policy=GraphSearchPolicy(max_path_length_m=100., max_detour_ratio=2.), clock=lambda: 0.,
    )
    args.update(changes)
    return produce_scoped_class_candidates(provider, network, mapping, **args)


def test_fifo_production_matches_independent_shortest_winding_denominator(
    visibility_ring: Any,
) -> None:
    production = _produce(visibility_ring, policy=GraphSearchPolicy(
        max_path_length_m=100., max_detour_ratio=2., max_branch_factor=3,
    ))
    reference = _classes(visibility_ring, policy=production.policy)
    assert production.complete
    assert production.production_algorithm == "FIFO_LABEL_CORRECTING_RELAXATION"
    assert production.oracle_outputs_read is False
    assert production.ground_truth_read is False
    assert len(production.classes) == 2
    assert [(item.winding_signature, item.path_length_m, item.source_edge_ids)
            for item in production.classes] == [
        (item.winding_signature, item.shortest_representative.path_length_m,
         item.shortest_representative.edge_ids) for item in reference.routes
    ]
    assert production.processed_labels != reference.expanded_lifted_states


def test_production_runs_when_reference_search_is_disabled(
    visibility_ring: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("production read reference inventory output")
    monkeypatch.setattr(reference_inventory, "enumerate_visibility_route_classes", forbidden)
    monkeypatch.setattr(reference_inventory, "enumerate_graph_route_inventory", forbidden)
    assert len(_produce(visibility_ring).classes) == 2


def test_true_higher_winding_classes_are_produced_without_null_backtrack_candidates(
    visibility_ring: Any,
) -> None:
    policy = GraphSearchPolicy(max_path_length_m=100., max_detour_ratio=4.)
    production = _produce(visibility_ring, policy=policy)
    reference = _classes(visibility_ring, policy=policy)
    assert production.complete and len(production.classes) > 2
    assert {item.winding_signature for item in production.classes} == {
        item.winding_signature for item in reference.routes
    }
    assert len({item.winding_signature for item in production.classes}) == len(production.classes)


def test_macro_keeps_exact_physical_paths_and_core_budgets_while_raw_search_is_retained(
    visibility_ring: Any,
) -> None:
    provider, _, visibility, _ = visibility_ring
    production = _produce(visibility_ring, policy=GraphSearchPolicy(
        max_path_length_m=100., max_detour_ratio=2., max_branch_factor=3,
    ))
    macro, source_edges, class_for_edge = build_class_macro_network(production, visibility)
    assert not macro.topology.config.transitions
    assert {node.camera_id for node in macro.topology.config.nodes} == {"A"}
    assert all(provider.validate_polyline(points) for points in source_edges.values())
    assert set(source_edges) == set(class_for_edge)
    ratio = production.metres_per_blender_unit
    start, end = _endpoints(
        start_position=(2.25 * ratio, 5. * ratio, 0.),
        end_position=(7.75 * ratio, 5. * ratio, 0.), start_camera="A", end_camera="A",
        start_time=1., end_time=101.,
    )
    factors = GraphFactorMask(camera_topology_filter=False)
    raw = SpatiotemporalGraphEngine(
        visibility, production.movement, production.policy, factors=factors, clock=lambda: 0.,
    ).propose_geometric_routes(start, end)
    assert raw.termination_reason == TerminationReason.MAX_BRANCH_FACTOR
    engine = SpatiotemporalGraphEngine(macro, production.movement, production.policy,
                                     factors=factors, clock=lambda: 0.)
    geometry = engine.propose_geometric_routes(start, end)
    assert geometry.complete and len(geometry.routes) == 2
    expected_by_signature = {item.winding_signature: item for item in production.classes}
    for route in geometry.routes:
        signatures = {class_for_edge[edge_id] for edge_id in route.navmesh_corridor}
        assert len(signatures) == 1
        original = expected_by_signature[next(iter(signatures))]
        assert route.polyline == original.polyline_m
        assert route.path_length == original.path_length_m
    # Timing generation remains the original reconstructor, including alternatives.
    from amidst.domain.trajectory import ReconstructionResult
    timed = ReconstructionResult(
        candidates=tuple(engine.timed_candidate(route) for route in geometry.routes),
        termination_reason=geometry.termination_reason, complete=geometry.complete,
        expanded_nodes=geometry.expanded_nodes,
    )
    event = BlindGapReconstructor().reconstruct_gap(start, end, timed)
    assert len({hypothesis.candidate_id for hypothesis in event.trajectories}) == 2


def test_macro_caps_classes_at_original_top_k_without_faking_generation_completeness(
    visibility_ring: Any,
) -> None:
    production = _produce(visibility_ring, policy=GraphSearchPolicy(
        max_candidate_paths=3, max_path_length_m=100., max_detour_ratio=4.,
    ))
    assert len(production.classes) > 3
    macro, _, labels = build_class_macro_network(production, visibility_ring[2])
    assert len(set(labels.values())) == 3
    assert max(len(macro.navigation.outgoing_edges(node.node_id))
               for node in macro.navigation.config.nodes) <= 3
    assert production.policy.max_candidate_paths == 3


def test_generation_truncation_and_query_tampering_are_explicit(visibility_ring: Any) -> None:
    result = _produce(
        visibility_ring, generation_budget=ClassGenerationBudget(max_processed_labels=2),
    )
    assert not result.complete and result.termination_reason == "MAX_PROCESSED_LABELS"
    assert result.pending_labels > 0
    with pytest.raises(ValueError, match="query lineage"):
        ScopedClassSearchResult.model_validate_json(result.model_copy(update={
            "gap_duration_s": 101.,
        }).model_dump_json())


def test_macro_rejects_changed_source_graph_or_fabricated_class_geometry(
    visibility_ring: Any,
) -> None:
    result = _produce(visibility_ring)
    visibility = visibility_ring[2]
    changed = NavigationNetwork(NavigationGraph(visibility.navigation.config.model_copy(update={
        "graph_id": "unrelated",
    })), CameraTopologyGraph(visibility.topology.config.model_copy(update={
        "navigation_graph_id": "unrelated",
    })))
    with pytest.raises(ValueError, match="lineage"):
        build_class_macro_network(result, changed)
    path = result.classes[0].model_copy(update={"path_length_m": 1.})
    changed_result = result.model_copy(update={"classes": (path, *result.classes[1:])})
    with pytest.raises(ValueError, match="physical source path/length"):
        build_class_macro_network(changed_result, visibility)

"""Independent graph-universe denominators retain loops, masks and truncation."""

from typing import Any

import pytest
from test_graph_engine import _edge, _endpoints, _network, _node, _transition
from test_scoped_authority import _decision, _inputs

from amidst.domain.camera import Camera
from amidst.domain.navigation import NavigationDataKind, NavigationGraphConfig
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import CameraTopologyConfig, CameraTopologyNode
from amidst.domain.trajectory import TerminationReason
from amidst.finalization.formal_route_inventory import (
    InventoryBudget,
    build_scoped_visibility_network,
    enumerate_formal_routes,
    enumerate_graph_route_inventory,
    enumerate_visibility_route_classes,
    graph_edge_sequence_recall,
)
from amidst.finalization.scoped_authority import (
    ScopeCameraLandmarkBinding,
    ScopedUnionPhysicalProvider,
    apply_scope_approval,
    load_scoped_authority,
)
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.graph.engine import SpatiotemporalGraphEngine
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import GeometryAuthorityError


def _loop_network() -> NavigationNetwork:
    start, end = _node("s", (0., 0., 0.)), _node("e", (1., 0., 0.))
    return _network(
        (start, end), (_edge("forward", start, end), _edge("back", end, start)),
        (CameraTopologyNode(camera_id="A", floor_id="1F"),
         CameraTopologyNode(camera_id="B", floor_id="1F")),
        (_transition("ab", "A", "B", "s", "e", ("forward",)),
         _transition("ba", "B", "A", "e", "s", ("back",))),
    )


def _inventory(network: NavigationNetwork | None = None, **changes: Any) -> Any:
    args = dict(
        start_node_id="s", end_node_id="e", start_camera_id="A", end_camera_id="B",
        gap_duration_s=10., movement=MovementConstraints(max_speed_m_s=1.),
        policy=GraphSearchPolicy(max_candidate_paths=1, max_path_length_m=3., max_detour_ratio=3),
        clock=lambda: 0.,
    )
    args.update(changes)
    return enumerate_graph_route_inventory(network or _loop_network(), **args)


def test_loop_after_endpoint_and_repeated_edge_are_in_denominator_beyond_top_k() -> None:
    network = _loop_network()
    inventory = _inventory(network)
    assert inventory.complete
    assert [route.edge_ids for route in inventory.routes] == [
        ("forward",), ("forward", "back", "forward"),
    ]
    assert inventory.routes[1].transition_ids == ("ab", "ba", "ab")
    assert inventory.maximum_out_degree_seen == 1
    assert inventory.source_route_class_inventory_exhaustive is False
    assert inventory.formal_case_readiness is False
    start, end = _endpoints(end_position=(1., 0., 0.), start_camera="A", end_camera="B")
    graph = SpatiotemporalGraphEngine(
        network, inventory.movement, inventory.policy, clock=lambda: 0.,
    )
    result = graph.propose_geometric_routes(start, end, max_paths=1)
    assert result.termination_reason == TerminationReason.MAX_PATHS_REACHED
    assert graph_edge_sequence_recall(
        inventory, tuple(route.navmesh_corridor for route in result.routes),
    ) == {"status": "AVAILABLE_SUPPLIED_GRAPH_EDGE_SEQUENCES", "recall": .5,
          "denominator": 2, "matched": 1, "source_route_class_recall": None}


@pytest.mark.parametrize("ratio, expected", [(1., 1), (2., 1), (3., 2)])
def test_actual_detour_ratio_filters_repeated_walks(ratio: float, expected: int) -> None:
    inventory = _inventory(policy=GraphSearchPolicy(max_path_length_m=3., max_detour_ratio=ratio))
    assert inventory.complete and inventory.detour_eligibility_certified
    assert inventory.shortest_eligible_length_m == 1.
    assert len(inventory.routes) == expected


def test_speed_mask_retains_untimed_infeasible_routes_without_changing_gap() -> None:
    movement = MovementConstraints(max_speed_m_s=.5)
    timed = _inventory(gap_duration_s=1., movement=movement)
    unmasked = _inventory(gap_duration_s=1., movement=movement, travel_time_filter=False)
    assert timed.complete and not timed.routes
    assert len(unmasked.routes) == 2
    assert all(route.timing_status == "UNAVAILABLE" for route in unmasked.routes)
    assert unmasked.routes[0].minimum_travel_time_s == 2.
    assert unmasked.query_content_sha256 != timed.query_content_sha256
    assert graph_edge_sequence_recall(timed, ()) == {
        "status": "N/A_EMPTY_ELIGIBLE_GRAPH_UNIVERSE", "recall": None,
        "denominator": 0, "matched": 0, "source_route_class_recall": None,
    }


def test_camera_mask_and_same_actual_camera_hold_have_different_universes() -> None:
    network = _loop_network()
    masked = _inventory(network, end_camera_id="A")
    hold = _inventory(network, end_camera_id="A", camera_topology_filter=False)
    assert not masked.routes
    assert len(hold.routes) == 2
    assert all(route.transition_ids == () for route in hold.routes)
    assert hold.query_content_sha256 != masked.query_content_sha256


@pytest.mark.parametrize("extra, eligible", [(5e-13, True), (1e-8, False)])
def test_original_ulp_speed_and_length_comparison_is_preserved(
    extra: float, eligible: bool,
) -> None:
    start, end = _node("s", (0., 0., 0.)), _node("e", (1. + extra, 0., 0.))
    network = _network(
        (start, end), (_edge("forward", start, end),),
        (CameraTopologyNode(camera_id="A", floor_id="1F"),
         CameraTopologyNode(camera_id="B", floor_id="1F")),
        (_transition("ab", "A", "B", "s", "e", ("forward",)),),
    )
    inventory = _inventory(
        network, gap_duration_s=1., policy=GraphSearchPolicy(max_path_length_m=1.),
    )
    assert bool(inventory.routes) is eligible
    if eligible:
        assert inventory.routes[0].minimum_travel_time_s == 1.


def test_inventory_safety_truncation_never_supplies_recall_denominator() -> None:
    truncated = _inventory(budget=InventoryBudget(max_expanded_states=2))
    assert truncated.routes
    assert truncated.complete is False and truncated.detour_eligibility_certified is False
    assert truncated.termination_reason == "MAX_EXPANDED_STATES"
    assert graph_edge_sequence_recall(truncated, (("forward",),)) == {
        "status": "N/A_TRUNCATED_INDEPENDENT_INVENTORY", "recall": None,
        "denominator": None, "matched": None,
    }


def test_pending_state_cap_is_truncation_and_inference_branch_cap_is_separate() -> None:
    start, end = _node("s", (0., 0., 0.)), _node("e", (1., 0., 0.))
    network = _network(
        (start, end), (_edge("a", start, end), _edge("b", start, end)),
        (CameraTopologyNode(camera_id="A", floor_id="1F"),
         CameraTopologyNode(camera_id="B", floor_id="1F")),
        (_transition("a", "A", "B", "s", "e", ("a",)),
         _transition("b", "A", "B", "s", "e", ("b",))),
    )
    truncated = _inventory(network, budget=InventoryBudget(max_pending_states=1))
    assert truncated.termination_reason == "MAX_PENDING_STATES" and not truncated.complete
    full = _inventory(network, policy=GraphSearchPolicy(max_branch_factor=1))
    assert full.maximum_out_degree_seen == 2 and full.complete and len(full.routes) == 2


def test_timeout_invalid_clock_and_invalid_gap_fail_honestly() -> None:
    times = iter((0., 2.))
    inventory = _inventory(clock=lambda: next(times), budget=InventoryBudget(max_elapsed_s=1.))
    assert not inventory.complete and inventory.termination_reason == "TIMEOUT"
    backwards = iter((0., 1., .5))
    with pytest.raises(ValueError, match="monotonic"):
        _inventory(clock=lambda: next(backwards))
    for gap in (0., -1., float("nan"), True):
        with pytest.raises(ValueError, match="GAP"):
            _inventory(gap_duration_s=gap)


def test_inventory_has_no_engine_dependency_and_input_order_does_not_change_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(SpatiotemporalGraphEngine, "propose_geometric_routes",
                        lambda *args, **kwargs: pytest.fail("oracle read Graph output"))
    original = _inventory()
    network = _loop_network()
    shuffled = NavigationNetwork(
        NavigationGraph(network.navigation.config.model_copy(update={
            "nodes": tuple(reversed(network.navigation.config.nodes)),
            "edges": tuple(reversed(network.navigation.config.edges)),
        })), CameraTopologyGraph(network.topology.config.model_copy(update={
            "nodes": tuple(reversed(network.topology.config.nodes)),
            "transitions": tuple(reversed(network.topology.config.transitions)),
        })),
    )
    assert _inventory(shuffled).routes == original.routes
    assert original.ground_truth_read is False and original.graph_outputs_read is False


@pytest.fixture(scope="module")
def approved_ring() -> tuple[ScopedUnionPhysicalProvider, ScopedRouteAuthorityBinding]:
    proposal, evidence, contract, numerics = _inputs()
    camera = Camera(
        camera_id="A", camera_to_world=(
            (1., 0., 0., 0.), (0., 1., 0., 0.), (0., 0., 1., 3.), (0., 0., 0., 1.),
        ), fx=100., fy=100., cx=50., cy=50., width=100, height=100, floor_id="1F",
    )
    export = {"source_sha256": proposal.pins.source_sha256,
              "cameras": [camera.model_dump(mode="json")]}
    camera_binding = ScopeCameraLandmarkBinding(
        camera=camera, calibration_content_sha256=content_sha256(camera.model_dump(mode="json")),
        source_camera_export_content_sha256=content_sha256(export), floor_id="1F",
        landmark_offset_bu=(0., 0., 1.), projection_plane_point_bu=(0., 0., 1.),
    )
    proposal = proposal.model_copy(update={
        "pins": proposal.pins.model_copy(update={
            "camera_export_content_sha256": content_sha256(export),
        }), "camera_landmark_bindings": (camera_binding,), "requested_projection_authority": True,
    })
    decision = _decision(proposal)
    certificate, detail = apply_scope_approval(
        proposal, decision, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_proposal_content_sha256=content_sha256(proposal.model_dump(mode="json")),
        expected_decision_content_sha256=content_sha256(decision.model_dump(mode="json")),
        camera_export=export,
    )
    assert certificate is not None, detail
    provider = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
        camera_export=export,
    )
    return provider, ScopedRouteAuthorityBinding(
        pins=proposal.pins, proposal_content_sha256=certificate.proposal_content_sha256,
        decision_content_sha256=certificate.human_decision_content_sha256,
        certificate_content_sha256=provider.certificate_content_sha256,
        union_wkb_sha256=certificate.union_wkb_sha256,
    )


def _formal(
    approved_ring: tuple[ScopedUnionPhysicalProvider, ScopedRouteAuthorityBinding], *,
    hole_shortcut: bool = False, scale_mismatch: bool = False, source_mismatch: bool = False,
    binding_mismatch: bool = False, missing_geometry: bool = False,
) -> Any:
    provider, binding = approved_ring
    scale = float(provider.contract.scale.metres_per_blender_unit)
    points = ((2.25, 5., 0.), (7.75, 5., 0.)) if hole_shortcut else (
        (2.25, 5., 0.), (2.25, 2.25, 0.), (7.75, 2.25, 0.), (7.75, 5., 0.),
    )
    normalized = tuple(tuple(value * scale for value in point) for point in points)
    start, end = _node("s", normalized[0]), _node("e", normalized[-1])
    edge = _edge("route", start, end, points=normalized)
    source = "f" * 64 if source_mismatch else provider.source_sha256
    network = NavigationNetwork(NavigationGraph(NavigationGraphConfig(
        graph_id="source-bound-ring", spatial_context_id="ring", source_asset_sha256=source,
        data_kind=NavigationDataKind.CONFIGURED, nodes=(start, end), edges=(edge,),
    )), CameraTopologyGraph(CameraTopologyConfig(
        topology_id="same-camera", navigation_graph_id="source-bound-ring",
        spatial_context_id="ring",
        source_asset_sha256=source, data_kind=NavigationDataKind.CONFIGURED,
        nodes=(CameraTopologyNode(camera_id="A", floor_id="1F"),),
    )))
    if scale_mismatch:
        points = tuple((x + .01, y, z) for x, y, z in points)
    return enumerate_formal_routes(
        provider, network, {} if missing_geometry else {"route": points},
        expected_binding=binding.model_copy(update={"union_wkb_sha256": "f" * 64})
        if binding_mismatch else binding,
        start_node_id="s", end_node_id="e", start_camera_id="A", end_camera_id="A",
        gap_duration_s=100., movement=MovementConstraints(max_speed_m_s=1.),
        policy=GraphSearchPolicy(max_path_length_m=100.), camera_topology_filter=False,
        clock=lambda: 0.,
    )


def test_formal_wrapper_binds_approved_geometry_scale_and_actual_camera(approved_ring: Any) -> None:
    inventory = _formal(approved_ring)
    assert inventory.complete and len(inventory.routes) == 1
    assert inventory.authority == approved_ring[1]
    assert inventory.source_edge_geometry_content_sha256
    assert inventory.routes[0].transition_ids == ()
    assert inventory.formal_case_readiness is False


@pytest.mark.parametrize("changes, message", [
    ({"source_mismatch": True}, "source differs"),
    ({"binding_mismatch": True}, "pins differ"),
    ({"missing_geometry": True}, "exactly every"),
    ({"scale_mismatch": True}, "normalization"),
])
def test_formal_wrapper_refuses_fabricated_provenance_or_incomplete_mapping(
    approved_ring: Any, changes: dict[str, bool], message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _formal(approved_ring, **changes)


def test_formal_wrapper_refuses_shortcut_through_approved_union_hole(approved_ring: Any) -> None:
    with pytest.raises(GeometryAuthorityError, match="UNION_OR_HOLE"):
        _formal(approved_ring, hole_shortcut=True)


@pytest.fixture(scope="module")
def visibility_ring(approved_ring: Any) -> Any:
    provider, binding = approved_ring
    network, mapping = build_scoped_visibility_network(
        provider, expected_binding=binding, start_bu=(2.25, 5., 0.), end_bu=(7.75, 5., 0.),
        camera_ids=("A",), spatial_context_id="SYNTHETIC_RING_VISIBILITY_TEST",
    )
    return provider, binding, network, mapping


def _classes(visibility_ring: Any, **changes: Any) -> Any:
    provider, binding, network, mapping = visibility_ring
    args = dict(
        expected_binding=binding, start_bu=(2.25, 5., 0.), end_bu=(7.75, 5., 0.),
        camera_id="A", gap_duration_s=100., movement=MovementConstraints(max_speed_m_s=1.),
        policy=GraphSearchPolicy(max_path_length_m=100., max_detour_ratio=2.), clock=lambda: 0.,
    )
    args.update(changes)
    return enumerate_visibility_route_classes(provider, network, mapping, **args)


def test_complete_visibility_mapping_keeps_every_boundary_vertex_and_no_hole_shortcut(
    visibility_ring: Any,
) -> None:
    provider, binding, network, mapping = visibility_ring
    assert len(network.navigation.config.nodes) > 10
    assert not network.topology.config.transitions
    assert all(provider.validate_polyline(points) for points in mapping.values())
    assert not any(edge.from_node_id == "endpoint:start" and edge.to_node_id == "endpoint:end"
                   for edge in network.navigation.config.edges)
    assert {edge.edge_id for edge in network.navigation.config.edges} == set(mapping)
    assert network.navigation.config.source_asset_sha256 == binding.pins.source_sha256


def test_lifted_winding_inventory_returns_shortest_classes_not_null_backtracks(
    visibility_ring: Any,
) -> None:
    inventory = _classes(visibility_ring)
    assert inventory.complete and inventory.source_route_class_inventory_exhaustive
    assert len(inventory.routes) == 2
    signatures = sorted(route.winding_signature for route in inventory.routes)
    assert signatures[1] - signatures[0] == 1
    assert inventory.formal_case_readiness is False
    assert inventory.raw_graph_edge_sequences_redefined is False
    assert inventory.expanded_lifted_states < 200
    assert all(route.shortest_representative.timing_status == "FEASIBLE"
               for route in inventory.routes)


def test_class_inventory_does_not_prune_real_higher_winding_classes(
    visibility_ring: Any,
) -> None:
    two = _classes(visibility_ring)
    wider = _classes(visibility_ring, policy=GraphSearchPolicy(
        max_path_length_m=100., max_detour_ratio=4.,
    ))
    assert wider.complete and len(wider.routes) > len(two.routes)
    assert len({route.winding_signature for route in wider.routes}) == len(wider.routes)
    assert wider.routes[0].shortest_representative.path_length_m == (
        two.routes[0].shortest_representative.path_length_m
    )


def test_class_inventory_truncation_and_missing_visibility_edge_never_certify_exhaustive(
    visibility_ring: Any,
) -> None:
    truncated = _classes(visibility_ring, budget=InventoryBudget(max_expanded_states=2))
    assert not truncated.complete and not truncated.source_route_class_inventory_exhaustive
    provider, binding, network, mapping = visibility_ring
    changed = NavigationNetwork(NavigationGraph(network.navigation.config.model_copy(update={
        "edges": network.navigation.config.edges[1:],
    })), network.topology)
    with pytest.raises(ValueError, match="complete source visibility mapping"):
        _classes((provider, binding, changed, mapping))


def test_original_contact_band_retains_endpoint_z_without_claiming_entire_3d_metric_cover(
    approved_ring: Any,
) -> None:
    provider, binding = approved_ring
    residual = provider.domain.contact_tolerance_bu / 2
    start, end = (2.25, 5., residual), (7.75, 5., -residual)
    assert provider.validate_polyline((start, start))
    assert provider.validate_polyline((end, end))
    network, mapping = build_scoped_visibility_network(
        provider, expected_binding=binding, start_bu=start, end_bu=end,
        camera_ids=("A",), spatial_context_id="EXACT_SOURCE_Z_RESIDUAL_TEST",
    )
    inventory = enumerate_visibility_route_classes(
        provider, network, mapping, expected_binding=binding, start_bu=start, end_bu=end,
        camera_id="A", gap_duration_s=100., movement=MovementConstraints(max_speed_m_s=1.),
        policy=GraphSearchPolicy(max_path_length_m=100.), clock=lambda: 0.,
    )
    assert inventory.complete and inventory.declared_graph_class_inventory_exhaustive
    assert inventory.source_route_class_inventory_exhaustive is False
    assert inventory.metric_cover_scope == "DECLARED_FLOOR_BOUNDARY_VISIBILITY_REPRESENTATIVE_GRAPH"
    assert inventory.endpoint_z_bu == (residual, -residual)
    assert network.navigation.node("endpoint:start").position[2] == (
        residual * provider.contract.scale.metres_per_blender_unit
    )

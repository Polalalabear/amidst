"""Simulation-planner route policy, without reading Blender or any GT files."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "c6_planner", ROOT / "scripts/plan_office_demo_feasibility.py"
)
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)
CONFIG = {
    "max_route_length_m": 18,
    "min_blind_length_m": 1,
    "min_control_length_m": 3,
    "max_gap_routes": 15,
    "max_controls": 5,
}


def graph_for(path):
    graph = {n: [] for n in path}
    for a, b in zip(path, path[1:], strict=False):
        graph[a].append(b)
        graph[b].append(a)
    return graph


def test_blind_span_requires_visible_endpoints_and_one_contiguous_gap():
    assert planner.gap_span([True, False, False, True]) == (1, 2)
    for flags in (
        [],
        [True],
        [False, True],
        [True, False],
        [True, False, True, False, True],
        [True, True],
    ):
        assert planner.gap_span(flags) is None


def test_gap_route_preserves_all_camera_blindness_and_visible_approach():
    path = [(i, 0) for i in range(12)]
    graph = graph_for(path)
    seen = {n: [0] if n[0] < 4 else [1] if n[0] > 7 else [] for n in graph}
    routes, _, pool, boundary = planner.find_routes(graph, seen, 0.5, CONFIG)
    assert routes and pool > 0 and boundary == 2
    for route in routes:
        flags = [bool(seen[n]) for n in route]
        assert flags[:3] == flags[-3:] == [True, True, True]
        first, last = planner.gap_span(flags)
        assert all(not seen[n] for n in route[first : last + 1])
        assert all(b in graph[a] for a, b in zip(route, route[1:], strict=False))


def test_blocked_edge_does_not_become_a_gap_route():
    path = [(i, 0) for i in range(12)]
    graph = graph_for(path)
    graph[5, 0].remove((6, 0))
    graph[6, 0].remove((5, 0))
    seen = {n: [0] if n[0] < 4 or n[0] > 7 else [] for n in graph}
    assert planner.find_routes(graph, seen, 0.5, CONFIG)[0] == []


def test_route_may_turn_in_the_blind_interval():
    path = [(i, 0) for i in range(6)] + [(5, i) for i in range(1, 7)]
    graph = graph_for(path)
    seen = {n: [0] if i < 4 else [1] if i > 7 else [] for i, n in enumerate(path)}
    routes = planner.find_routes(graph, seen, 0.5, CONFIG)[0]
    assert routes and all(planner.turns(route) == 1 for route in routes)
    assert planner.turns([(0, 0), (1, 0), (2, 0)]) == 0


def test_controls_require_every_node_visible_and_every_edge_available():
    path = [(i, 0) for i in range(12)]
    graph = graph_for(path)
    seen = {n: [0] for n in graph}
    controls = planner.find_routes(graph, seen, 0.5, CONFIG)[1]
    assert controls and all(len(p) == 7 for p in controls)
    graph[5, 0].remove((6, 0))
    graph[6, 0].remove((5, 0))
    assert planner.find_routes(graph, seen, 0.5, CONFIG)[1] == []
    seen[5, 0] = []
    assert planner.find_routes(graph_for(path), seen, 0.5, CONFIG)[1] == []


def test_maximum_length_and_minimum_blind_length_are_enforced():
    path = [(i, 0) for i in range(12)]
    graph = graph_for(path)
    seen = {n: [0] if n[0] < 4 or n[0] > 7 else [] for n in graph}
    assert planner.find_routes(graph, seen, 0.5, {**CONFIG, "max_route_length_m": 2})[0] == []
    assert planner.find_routes(graph, seen, 0.5, {**CONFIG, "min_blind_length_m": 5})[0] == []


def test_search_is_deterministic_and_does_not_mutate_inputs():
    path = [(i, 0) for i in range(12)]
    graph = graph_for(path)
    original = {n: list(edges) for n, edges in graph.items()}
    seen = {n: [0] if n[0] < 4 or n[0] > 7 else [] for n in graph}
    first = planner.find_routes(graph, seen, 0.5, CONFIG)
    assert first == planner.find_routes(dict(reversed(list(graph.items()))), seen, 0.5, CONFIG)
    assert graph == original


def test_controls_use_stricter_probe_visibility_without_changing_gap_visibility():
    path = [(i, 0) for i in range(12)]
    graph = graph_for(path)
    seen = {n: [0] for n in graph}
    strict = {n: [] for n in graph}
    assert planner.find_routes(graph, seen, 0.5, CONFIG)[1]
    assert planner.find_routes(graph, seen, 0.5, CONFIG, strict)[1] == []
    # Each sample visible to *some* camera is not a same-camera control.
    strict = {n: [n[0] % 2] for n in graph}
    assert planner.find_routes(graph, seen, 0.5, CONFIG, strict)[1] == []

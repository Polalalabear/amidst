"""Simulation-planner route policy, without reading Blender or any GT files."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "c6_planner", ROOT / "scripts/plan_office_demo_feasibility.py"
)
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)
screen_spec = importlib.util.spec_from_file_location(
    "c6_prescreen", ROOT / "scripts/c6_prescreen.py"
)
screen = importlib.util.module_from_spec(screen_spec)
screen_spec.loader.exec_module(screen)
POLICY = json.loads((ROOT / "configs/c6_prescreen_v2.json").read_text())["prescreen"]
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


@pytest.mark.parametrize(
    "ndc,blocker,expected",
    [
        ((0.5, 0.5, 5), "wall", "OCCLUDED"),
        ((1.0, 0.5, 5), None, "OUTSIDE_FOV"),
        ((0.5, 0.5, 11), None, "CLIPPED"),
        ((0.5, 0.5, -1), None, "CLIPPED"),
        ((0.5, 0.5, 5), None, "VISIBLE"),
    ],
)
def test_visibility_separates_frustum_clip_and_occlusion(ndc, blocker, expected):
    calls = []

    def cast():
        calls.append(True)
        return blocker

    result = screen.probe_visibility(ndc, 0.1, 10, cast)
    assert result["status"] == expected
    assert bool(calls) == (expected in {"VISIBLE", "OCCLUDED"})


def example_record():
    samples = []
    for i in range(33):
        distance = i / 4
        visible = distance <= 2 or distance >= 5
        camera = "A" if distance <= 2 else "B"
        probes = [{"status": "VISIBLE" if visible else "OCCLUDED", "incidence": 0.4}]
        probes *= 3
        samples.append(
            {
                "distance_m": distance,
                "foot_position_m": [distance, 0, 0.5],
                "rays": [probes],
                "visible_cameras": [camera] if visible else [],
                "v2_bottom_eligible_cameras": [camera] if visible else [],
            }
        )
    return {"candidate_id": "example", "length_m": 8, "samples": samples}


def test_prescreen_accepts_exact_one_second_at_speed_upper_and_checks_window_lower():
    record = example_record()
    result = screen.classify_route(record, POLICY)
    assert result["qualified"] and result["both_endpoints_ground_qualified"]
    assert (
        result["blind_adjacent_ground_segments"]["approach"]["minimum_duration_s_at_speed_upper"]
        == 1
    )
    assert result["cross_camera"] and result["turns_in_blind"] == 0
    record["length_m"] = 10.1
    assert (
        "MAX_WINDOW_EXCEEDED_AT_SPEED_BAND_LOWER"
        in screen.classify_route(record, POLICY)["reasons"]
    )


def test_endpoint_pass_does_not_hide_unqualified_blind_adjacent_segment():
    record = example_record()
    record["samples"][8]["rays"][0][0] = {"status": "OCCLUDED", "incidence": 0.4}
    record["samples"][8]["v2_bottom_eligible_cameras"] = []
    result = screen.classify_route(record, POLICY)
    assert result["both_endpoints_ground_qualified"]
    assert "BLIND_ADJACENT_QUALIFIED_SEGMENT_TOO_SHORT" in result["reasons"]


def test_any_head_or_torso_visible_prevents_blind_classification():
    assert screen.is_visible(
        [[{"status": "OCCLUDED"}, {"status": "VISIBLE"}, {"status": "OUTSIDE_FOV"}]]
    )
    assert not screen.is_visible(
        [[{"status": "OCCLUDED"}, {"status": "CLIPPED"}, {"status": "OUTSIDE_FOV"}]]
    )


def test_staircase_is_simplified_for_turn_measurement_only():
    points = [(0, 0), (0.5, 0), (0.5, 0.5), (1, 0.5), (1, 1)]
    original = list(points)
    assert screen.simplified_indices(points, 0.4) == [0, 4]
    assert points == original
    assert screen.simplified_indices([(0, 0), (3, 0), (3, 3)], 0.4) == [0, 1, 2]


def test_only_simplified_turns_inside_blind_interval_are_counted():
    record = example_record()
    for s in record["samples"]:
        d = s["distance_m"]
        s["foot_position_m"] = [min(d, 3), max(0, d - 3), 0.5]
    result = screen.classify_route(record, POLICY)
    assert result["turns_in_blind"] == 1
    assert not result["simplified_path_used_for_motion"]
    for s in record["samples"]:
        d = s["distance_m"]
        s["foot_position_m"] = [min(d, 1), max(0, d - 1), 0.5]
    assert screen.classify_route(record, POLICY)["turns_in_blind"] == 0


def test_selection_does_not_fill_with_rejected_or_same_camera_majority():
    records = []
    for i in range(10):
        r = copy.deepcopy(example_record())
        r["candidate_id"] = str(i)
        for sample in r["samples"]:
            sample["foot_position_m"][1] += i
        r["prescreen"] = screen.classify_route(r, POLICY)
        if i > 1:
            r["prescreen"]["cross_camera"] = False
        if i == 9:
            r["prescreen"]["qualified"] = False
        records.append(r)
    chosen = screen.select_benchmarks(records, POLICY)
    assert all(r["prescreen"]["qualified"] for r in chosen)
    assert sum(r["prescreen"]["cross_camera"] for r in chosen) / len(chosen) >= 0.6
    assert [r["benchmark_id"] for r in chosen] == [
        f"c6-benchmark-{i:03}" for i in range(1, len(chosen) + 1)
    ]


def test_actual_fixed_nominal_schedule_controls_window_without_changing_speed_band():
    record = example_record()
    for sample in record["samples"]:
        sample["distance_m"] *= 11 / 8
        sample["foot_position_m"][0] *= 11 / 8
    record["length_m"] = 11
    policy = {**POLICY, "window_basis": "FIXED_NOMINAL_RENDER_SCHEDULE"}
    result = screen.classify_route(record, policy)
    assert result["qualified"]
    assert result["duration_s_at_speed_band_lower"] == 11
    assert result["configured_render_speed_m_s"] == 1.5
    assert result["configured_render_duration_s"] == 11 / 1.5
    assert not screen.classify_route(record, POLICY)["qualified"]
    for sample in record["samples"]:
        sample["distance_m"] *= 15.1 / 11
        sample["foot_position_m"][0] *= 15.1 / 11
    record["length_m"] = 15.1
    assert not screen.classify_route(record, policy)["qualified"]


def test_blind_waypoint_search_adds_source_side_cross_camera_route_variations():
    graph = {(x, y): [] for x in range(16) for y in range(7)}
    for n in graph:
        graph[n] = [m for m in planner.neighbors(n) if m in graph]
    seen = {n: [0] if n[0] <= 4 else [1] if n[0] >= 11 else [] for n in graph}
    policy = {
        **POLICY,
        "window_basis": "FIXED_NOMINAL_RENDER_SCHEDULE",
        "max_candidate_records": 512,
        "max_waypoints_per_pair": 8,
    }
    shortest, _, _ = screen.search_paths(graph, seen, seen, 0.5, policy)
    varied, _, _ = screen.search_paths(
        graph, seen, seen, 0.5, {**policy, "blind_waypoint_search": True}
    )
    assert len(varied) > len(shortest)
    for path in varied:
        assert planner.gap_span([bool(seen[n]) for n in path])
        assert (len(path) - 1) * 0.5 / policy["nominal_speed_m_s"] <= 10
        assert all(b in graph[a] for a, b in zip(path, path[1:], strict=False))

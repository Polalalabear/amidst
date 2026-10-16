"""Synthetic-map unit tests for the K1 blind-interval hypothesis module.

All maps and endpoints here are synthetic test geometry (metres), not Office data.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import shapely
from shapely.geometry import LineString, Point, box

from amidst.blind_hypothesis import (
    REQUEST_SCHEMA,
    FloorMapDescriptor,
    HypothesisRequestError,
    PolygonFloorMap,
    canonical_sha256,
    generate_blind_hypotheses,
    polygon_floor_map,
    verify_output_sha256,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "blind_hypothesis_v1.json"
DESCRIPTOR = FloorMapDescriptor(
    kind="SYNTHETIC_TEST",
    map_ref="synthetic:test-map",
    sha256="0" * 64,
    walkable_ref="synthetic:walk",
    portal_ref="synthetic:portal",
    floor_id="F",
)
SCENE = "synthetic-test"


def _config(**overrides: Any) -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text())
    config["scenes"][SCENE] = {"time_step_s": 0.2, "body_radius_m": 0.25}
    for key, value in overrides.items():
        config[key] = value
    return config


def _obstacle_room() -> PolygonFloorMap:
    room = box(0, 0, 10, 6).difference(box(4, 1.5, 6, 4.5))
    return PolygonFloorMap(DESCRIPTOR, 0.0, {"WALK_ROOM": room}, {})


def _two_rooms(bridge: str) -> PolygonFloorMap:
    """Rooms A (x 0-4) and B (x 4.4-8.4) separated by a 0.4 m wall gap.

    ``bridge``: ``"portal"`` adds a portal footprint over the gap (no walkable
    surface), ``"threshold"`` adds a walkable threshold surface plus a portal,
    ``"none"`` leaves the wall closed.
    """

    regions = {
        "WALK_A": [[0, 0], [4, 0], [4, 4], [0, 4]],
        "WALK_B": [[4.4, 0], [8.4, 0], [8.4, 4], [4.4, 4]],
    }
    portals = {}
    if bridge in ("portal", "threshold"):
        portals["PORTAL_A_B"] = [[3.9, 1.5], [4.5, 1.5], [4.5, 2.5], [3.9, 2.5]]
    if bridge == "threshold":
        regions["WALK_A_B_THRESHOLD"] = [[4, 1.5], [4.4, 1.5], [4.4, 2.5], [4, 2.5]]
    return polygon_floor_map(descriptor=DESCRIPTOR, floor_z_m=0.0, regions=regions, portals=portals)


def _estimate(ref: str, t: float, kind: str = "POINT", **fields: Any) -> dict[str, Any]:
    estimate: dict[str, Any] = {
        "schema_version": "office-demo.interval-observation.v1",
        "observation_ref": ref,
        "camera_id": "CAM_TEST",
        "timestamp_s": t,
        "status": "READY",
        "reason": None,
        "evidence_state": "PROJECTED_OBSERVATION",
        "estimate_kind": kind,
        "point_m": None,
        "segment": None,
        "pixel_sensitivity_m": 0.1,
        "contact_quality": {"status": "PASS"},
        "provenance": {"gt_read": False},
    }
    estimate.update(fields)
    return estimate


def _endpoint(ref: str, t: float, xy: tuple[float, float], **estimate: Any) -> dict[str, Any]:
    fields = {"point_m": [xy[0], xy[1], 0.0], **estimate}
    return {
        "observation_ref": ref,
        "camera_id": "CAM_TEST",
        "timestamp_s": t,
        "evidence_state": "PROJECTED_OBSERVATION",
        "ground_estimate": _estimate(ref, t, **fields),
    }


def _request(start: dict[str, Any], end: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    request = {
        "schema_version": REQUEST_SCHEMA,
        "session_ref": "session:test",
        "scene_id": SCENE,
        "candidate_ref": None,
        "start": start,
        "end": end,
        "top_k": 3,
        "negative_evidence": [],
        "previous_response_sha256": None,
    }
    request.update(overrides)
    return request


def _negative(
    ref: str, times: list[float], polygons: list[list[list[float]]], **overrides: Any
) -> dict[str, Any]:
    entry = {
        "negative_evidence_ref": ref,
        "origin": "BLIND_INTERVAL_BASELINE",
        "camera_id": "CAM_TEST_2",
        "frame_refs": [{"frame_ref": f"frame:{ref}:{t}", "timestamp_s": t} for t in times],
        "visibility_ref": f"visibility:{ref}",
        "detection_result": "NO_DETECTION",
        "detection_producer": {"producer": "test-perception", "version": "v2"},
        "retrieval_query_id": None,
        "sha256": "1" * 64,
        "visible_floor": {"method": "SOURCE_MESH_RAYCAST", "polygons": polygons},
    }
    entry.update(overrides)
    return entry


def _run(
    request: dict[str, Any], floor_map: PolygonFloorMap | None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    return generate_blind_hypotheses(
        request,
        config=config if config is not None else _config(),
        config_sha256="c" * 64,
        floor_map=floor_map,
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
    )


def _gap_times(start: float, end: float, dt: float = 0.2) -> list[float]:
    return [round(start + i * dt, 6) for i in range(1, round((end - start) / dt))]


def _obstacle_request(**overrides: Any) -> dict[str, Any]:
    return _request(
        _endpoint("obs:a", 0.0, (1.0, 3.0)), _endpoint("obs:b", 6.0, (9.0, 3.0)), **overrides
    )


def test_ready_response_contract_and_authority_fields() -> None:
    response = _run(_obstacle_request(), _obstacle_room())

    assert response["status"] == "READY" and response["reason"] is None
    assert response["schema_version"] == "workbench.blind-hypothesis.v1"
    assert response["evidence_state"] == "INFERRED_HYPOTHESIS"
    assert response["ranking_basis"] == "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY"
    assert response["physical_authority"] == "UNKNOWN"
    assert response["identity_verdict"] == "UNCONFIRMED"
    assert response["agent_used"] is False
    assert response["reconstruction_rng"] == "NOT_USED"
    assert response["provenance"]["gt_read"] is False
    assert response["configuration"]["speed_range_m_s"]["source"] == "CONFIGURED_NOT_GT"
    assert response["interval"] == {
        "start_s": 0.0,
        "end_s": 6.0,
        "duration_s": 6.0,
        "start_observation_ref": "obs:a",
        "end_observation_ref": "obs:b",
    }
    assert verify_output_sha256(response)

    times = _gap_times(0.0, 6.0)
    assert [region["timestamp_s"] for region in response["reachable_regions"]] == times
    hypotheses = response["hypotheses"]
    assert 1 <= len(hypotheses) <= 3
    assert [h["rank"] for h in hypotheses] == list(range(1, len(hypotheses) + 1))
    scores = [h["plausibility"]["score"] for h in hypotheses]
    assert scores == sorted(scores, reverse=True)
    for hypothesis in hypotheses:
        assert hypothesis["status"] == "ACTIVE" and hypothesis["physical_authority"] == "UNKNOWN"
        assert [s["timestamp_s"] for s in hypothesis["samples"]] == times  # no endpoint samples
        assert {s["evidence_state"] for s in hypothesis["samples"]} == {"INFERRED_HYPOTHESIS"}
        assert hypothesis["checks"]["speed"]["result"] == "PASS"
        assert hypothesis["checks"]["speed"]["max_step_speed_m_s"] <= 2.0 + 1e-9
        assert hypothesis["checks"]["walkable"]["result"] == "PASS"
        # No negative evidence supplied: nothing establishes "unseen".
        assert hypothesis["checks"]["unseen"]["result"] == "UNKNOWN"
        assert hypothesis["plausibility"]["basis"] == "CONFIGURED_PLAUSIBILITY_NOT_PROBABILITY"
        # Samples lie on the constant-speed route, within one lattice snap of
        # the reachable region at the same time.
        snap = 0.25 * math.sqrt(2) / 2 + 1e-6
        for sample, region in zip(
            hypothesis["samples"], response["reachable_regions"], strict=True
        ):
            assert min(math.dist(sample["position_m"][:2], xy) for xy in region["samples"]) <= snap


def test_deterministic_and_hash_bound() -> None:
    first = _run(_obstacle_request(), _obstacle_room())
    second = _run(_obstacle_request(), _obstacle_room())
    assert first == second
    tampered = copy.deepcopy(first)
    tampered["hypotheses"][0]["plausibility"]["score"] += 1.0
    assert not verify_output_sha256(tampered)
    body = {k: v for k, v in first.items() if k != "output_sha256"}
    assert first["output_sha256"] == canonical_sha256(body)


def test_representatives_are_diverse_around_obstacle() -> None:
    hypotheses = _run(_obstacle_request(), _obstacle_room())["hypotheses"]
    assert len(hypotheses) == 3
    for i, a in enumerate(hypotheses):
        for b in hypotheses[i + 1 :]:
            separation = max(
                math.dist(sa["position_m"], sb["position_m"])
                for sa, sb in zip(a["samples"], b["samples"], strict=True)
            )
            assert separation >= 0.75
    # Both sides of the obstacle (x 4-6, y 1.5-4.5) are represented at t = 3.0 s.
    sides = set()
    for hypothesis in hypotheses:
        x, y, _ = next(s for s in hypothesis["samples"] if s["timestamp_s"] == 3.0)["position_m"]
        assert not (4 < x < 6 and 1.5 < y < 4.5)
        sides.add("north" if y >= 4.5 else "south" if y <= 1.5 else "beside")
    assert {"north", "south"} <= sides


@pytest.mark.parametrize("bridge", ["portal", "threshold"])
def test_portal_is_required_between_regions(bridge: str) -> None:
    start, end = _endpoint("obs:a", 0.0, (1.0, 2.0)), _endpoint("obs:b", 6.0, (7.5, 2.0))
    joined = _run(_request(start, end), _two_rooms(bridge))
    assert joined["status"] == "READY"
    assert all(h["portal_sequence"] == ["PORTAL_A_B"] for h in joined["hypotheses"])
    for hypothesis in joined["hypotheses"]:
        crossing = [
            s["position_m"][1] for s in hypothesis["samples"] if 4.0 < s["position_m"][0] < 4.4
        ]
        assert all(1.5 <= y <= 2.5 for y in crossing)  # through the doorway only


def test_closed_wall_is_not_crossed() -> None:
    start, end = _endpoint("obs:a", 0.0, (1.0, 2.0)), _endpoint("obs:b", 6.0, (7.5, 2.0))
    separated = _run(_request(start, end), _two_rooms("none"))
    assert separated["status"] == "UNKNOWN"
    assert separated["reason"] == "ENDPOINTS_UNREACHABLE"
    assert separated["hypotheses"] == [] and separated["reachable_regions"] == []


def test_speed_bound_makes_far_endpoint_unreachable() -> None:
    start, end = _endpoint("obs:a", 0.0, (1.0, 2.0)), _endpoint("obs:b", 2.0, (8.0, 2.0))
    response = _run(_request(start, end), _two_rooms("threshold"))
    assert response["status"] == "UNKNOWN"
    assert response["reason"] == "ENDPOINTS_UNREACHABLE"


def test_reachable_region_grows_then_shrinks_and_is_bounded_by_speed() -> None:
    response = _run(_obstacle_request(), _obstacle_room())
    regions = response["reachable_regions"]
    assert regions[0]["kind"] == "SAMPLE_SET" and regions[0]["polygons"] is None
    assert regions[0]["cell_size_m"] == 0.25
    assert max(r["area_m2"] for r in regions) > regions[0]["area_m2"]
    assert max(r["area_m2"] for r in regions) > regions[-1]["area_m2"]
    # First step: every cell is within one step of travel from the start disc
    # (max speed 2 m/s * 0.2 s, metric factor and the full-diagonal reach slack).
    reach = 2.0 * 0.2 * 1.0824 + 0.1 + 0.25 * math.sqrt(2)
    assert all(math.dist(xy, (1.0, 3.0)) <= reach + 1e-9 for xy in regions[0]["samples"])
    for region in regions:
        assert region["evidence_state"] == "INFERRED_HYPOTHESIS" and region["truncated"] is False


def test_negative_evidence_prunes_visible_floor() -> None:
    times = _gap_times(0.0, 6.0)
    south_aisle = [[[3.0, 0.0], [7.0, 0.0], [7.0, 2.0], [3.0, 2.0]]]
    request = _obstacle_request(negative_evidence=[_negative("negev:south", times, south_aisle)])
    response = _run(request, _obstacle_room())

    assert response["status"] == "READY"
    assert response["negative_evidence_applied"] == ["negev:south"]
    removed = next(t for t in response["trace"] if t["step"] == "UNSEEN_MASK_APPLIED")
    assert removed["cells_removed"] > 0
    for hypothesis in response["hypotheses"]:
        assert hypothesis["checks"]["unseen"]["result"] == "PASS"
        assert hypothesis["checks"]["unseen"]["conflicts"] == []
        x, y, _ = next(s for s in hypothesis["samples"] if s["timestamp_s"] == 3.0)["position_m"]
        assert y >= 4.5  # only the unseen north side remains
    # Reachable regions exclude cells whose whole square (half diagonal 0.177 m) plus
    # body disc (r = 0.25) is inside the footprint (x 3-7, y 0-2): erosion 0.427 m,
    # i.e. centres in x 3.427-6.573, y 0.427-1.573 (lattice centres 3.5-6.5, 0.5-1.5).
    for region in response["reachable_regions"]:
        assert not any(3.427 <= x <= 6.573 and 0.427 <= y <= 1.573 for x, y in region["samples"])


def test_empty_visible_floor_prunes_nothing_but_establishes_unseen() -> None:
    times = _gap_times(0.0, 6.0)
    baseline = [
        _negative("negev:front", times, [], camera_id="CAM_FRONT"),
        _negative("negev:rear", times, [], camera_id="CAM_REAR"),
    ]
    with_evidence = _run(_obstacle_request(negative_evidence=baseline), _obstacle_room())
    without = _run(_obstacle_request(), _obstacle_room())

    assert with_evidence["rejected_counts"]["unseen"] == 0
    removed = next(t for t in with_evidence["trace"] if t["step"] == "UNSEEN_MASK_APPLIED")
    assert removed["cells_removed"] == 0
    assert with_evidence["reachable_regions"] == without["reachable_regions"]
    assert {h["checks"]["unseen"]["result"] for h in with_evidence["hypotheses"]} == {"PASS"}


def test_partial_negative_evidence_coverage_keeps_unseen_unknown() -> None:
    times = _gap_times(0.0, 6.0)
    request = _obstacle_request(negative_evidence=[_negative("negev:one", times[:3], [])])
    response = _run(request, _obstacle_room())
    for hypothesis in response["hypotheses"]:
        assert hypothesis["checks"]["unseen"]["result"] == "UNKNOWN"
        assert hypothesis["checks"]["unseen"]["steps_without_negative_evidence"] == len(times) - 3


def test_negative_evidence_covering_everything_empties_region() -> None:
    times = _gap_times(0.0, 6.0)
    everything = [[[-1.0, -1.0], [11.0, -1.0], [11.0, 7.0], [-1.0, 7.0]]]
    request = _obstacle_request(negative_evidence=[_negative("negev:all", times[5:8], everything)])
    response = _run(request, _obstacle_room())
    assert response["status"] == "UNKNOWN"
    assert response["reason"] == "REACHABLE_SET_EMPTY"
    assert response["hypotheses"] == [] and response["reachable_regions"] == []


@pytest.mark.parametrize(
    "override",
    [
        {"visible_floor": {"method": "RENDERER_VISIBILITY", "polygons": []}},
        {"detection_result": "UNKNOWN"},
        {"origin": "GROUND_TRUTH"},
        {"frame_refs": [{"frame_ref": "frame:x", "timestamp_s": 6.0}]},  # endpoint, not gap
        {"frame_refs": []},
    ],
)
def test_invalid_negative_evidence_fails_closed(override: dict[str, Any]) -> None:
    entry = _negative("negev:bad", _gap_times(0.0, 6.0), [], **override)
    response = _run(_obstacle_request(negative_evidence=[entry]), _obstacle_room())
    assert response["status"] == "UNKNOWN"
    assert response["reason"] == "NEGATIVE_EVIDENCE_INVALID"


def test_duplicate_negative_evidence_ref_fails_closed() -> None:
    times = _gap_times(0.0, 6.0)
    entries = [_negative("negev:dup", times, []), _negative("negev:dup", times, [])]
    response = _run(_obstacle_request(negative_evidence=entries), _obstacle_room())
    assert response["reason"] == "NEGATIVE_EVIDENCE_INVALID"


@pytest.mark.parametrize(
    ("estimate", "problem"),
    [
        ({"contact_quality": {"status": "FLAGGED"}}, "POINT_WITHOUT_CONTACT_QUALITY_PASS"),
        (
            {"status": "UNKNOWN", "reason": "HEAD_ANCHOR_UNRELIABLE"},
            "GROUND_ESTIMATE_UNKNOWN:HEAD_ANCHOR_UNRELIABLE",
        ),
        ({"provenance": {"gt_read": True}}, "GROUND_ESTIMATE_GT_READ_NOT_FALSE"),
        ({"observation_ref": "obs:other"}, "GROUND_ESTIMATE_OBSERVATION_MISMATCH"),
        ({"estimate_kind": "NONE"}, "ESTIMATE_KIND_NONE"),
    ],
)
def test_unusable_endpoint_fails_closed(estimate: dict[str, Any], problem: str) -> None:
    request = _request(
        _endpoint("obs:a", 0.0, (1.0, 3.0), **estimate), _endpoint("obs:b", 6.0, (9.0, 3.0))
    )
    response = _run(request, _obstacle_room())
    assert response["status"] == "UNKNOWN" and response["reason"] == "ENDPOINT_UNUSABLE"
    assert {"step": "ENDPOINT_REJECTED", "endpoint": "start", "problem": problem} in response[
        "trace"
    ]


def test_missing_ground_estimate_is_endpoint_unusable() -> None:
    end = _endpoint("obs:b", 6.0, (9.0, 3.0))
    end["ground_estimate"] = None
    response = _run(_request(_endpoint("obs:a", 0.0, (1.0, 3.0)), end), _obstacle_room())
    assert response["reason"] == "ENDPOINT_UNUSABLE"
    assert {
        "step": "ENDPOINT_REJECTED",
        "endpoint": "end",
        "problem": "GROUND_ESTIMATE_NOT_PRODUCED",
    } in response["trace"]


def test_endpoint_outside_walkable_fails_closed() -> None:
    # (5, 3) is inside the obstacle hole; disc radius 0.1 m reaches no lattice cell.
    request = _request(_endpoint("obs:a", 0.0, (5.0, 3.0)), _endpoint("obs:b", 6.0, (9.0, 3.0)))
    response = _run(request, _obstacle_room())
    assert response["reason"] == "ENDPOINT_OUTSIDE_WALKABLE"


def test_floor_z_mismatch_is_provenance_mismatch() -> None:
    start = _endpoint("obs:a", 0.0, (1.0, 3.0), point_m=[1.0, 3.0, 0.5])
    response = _run(_request(start, _endpoint("obs:b", 6.0, (9.0, 3.0))), _obstacle_room())
    assert response["reason"] == "PROVENANCE_MISMATCH"


def test_segment_endpoint_is_used_as_whole_region() -> None:
    segment = {"near_m": [0.5, 2.0, 0.0], "far_m": [0.5, 4.0, 0.0]}
    start = _endpoint(
        "obs:a", 0.0, (0.0, 0.0), estimate_kind="SEGMENT", point_m=None, segment=segment
    )
    response = _run(_request(start, _endpoint("obs:b", 6.0, (9.0, 3.0))), _obstacle_room())
    assert response["status"] == "READY"
    first = response["reachable_regions"][0]["samples"]
    ys = [y for _, y in first]
    assert min(ys) < 2.0 and max(ys) > 4.0  # spans the whole segment, not its midpoint


@pytest.mark.parametrize(
    ("start_t", "end_t", "reason"),
    [
        (0.0, 0.0, "INTERVAL_INVALID"),
        (0.0, 6.1, "INTERVAL_INVALID"),  # off the 0.2 s clock grid
        (0.0, 0.2, "INTERVAL_INVALID"),  # no interior clock step
        (0.0, 20.2, "INTERVAL_TOO_LONG"),
    ],
)
def test_interval_rules(start_t: float, end_t: float, reason: str) -> None:
    request = _request(
        _endpoint("obs:a", start_t, (1.0, 3.0)), _endpoint("obs:b", end_t, (9.0, 3.0))
    )
    response = _run(request, _obstacle_room())
    assert response["status"] == "UNKNOWN" and response["reason"] == reason


@pytest.mark.parametrize(
    "speed",
    [
        {"min": 0.0, "max": 9.0, "source": "CONFIGURED_NOT_GT"},
        {"min": 2.0, "max": 2.0, "source": "CONFIGURED_NOT_GT"},
        {"min": 0.0, "max": 2.0, "source": "GROUND_TRUTH"},
        {"min": 0.0, "source": "CONFIGURED_NOT_GT"},
    ],
)
def test_invalid_speed_config_fails_closed(speed: dict[str, Any]) -> None:
    response = _run(_obstacle_request(), _obstacle_room(), _config(speed_range_m_s=speed))
    assert response["status"] == "UNKNOWN" and response["reason"] == "SPEED_CONFIG_UNAVAILABLE"


def test_missing_floor_map_fails_closed() -> None:
    response = _run(_obstacle_request(), None)
    assert response["reason"] == "WALKABLE_ANNOTATION_UNAVAILABLE"


def test_min_speed_is_checked_on_returned_paths() -> None:
    config = _config()
    config["speed_range_m_s"] = {"min": 1.0, "max": 2.0, "source": "CONFIGURED_NOT_GT"}
    request = _request(_endpoint("obs:a", 0.0, (1.0, 3.0)), _endpoint("obs:b", 4.0, (3.0, 3.0)))
    response = _run(request, _obstacle_room(), config)
    assert response["rejected_counts"]["speed"] > 0
    for hypothesis in response["hypotheses"]:
        assert hypothesis["checks"]["speed"]["mean_speed_m_s"] >= 1.0


def test_pruning_rerun_is_not_silently_ignored() -> None:
    # K5 implemented the re-run: a hash without the previous response to verify it
    # against fails closed (never ignored, never PRUNING_RERUN_NOT_IMPLEMENTED).
    response = _run(_obstacle_request(previous_response_sha256="f" * 64), _obstacle_room())
    assert response["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"


def test_deadline_fails_closed() -> None:
    response = generate_blind_hypotheses(
        _obstacle_request(),
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={},
        should_stop=lambda: True,
    )
    assert response["reason"] == "SEARCH_BUDGET_EXHAUSTED"


def test_request_cannot_carry_gt_or_overrides() -> None:
    request = _obstacle_request()
    request["ground_truth_trajectory"] = [[0.0, 1.0, 3.0]]
    with pytest.raises(HypothesisRequestError):
        _run(request, _obstacle_room())
    for top_k in (0, 6, True, 2.0):
        with pytest.raises(HypothesisRequestError):
            _run(_obstacle_request(top_k=top_k), _obstacle_room())


# ----------------------------------------------------------------- review fixes (PR #33)


def _trace_step(response: dict[str, Any], step: str) -> list[dict[str, Any]]:
    return [item for item in response["trace"] if item["step"] == step]


def _polygon_vertices(polygon: Any) -> list[tuple[float, float]]:
    parts = list(polygon.geoms) if hasattr(polygon, "geoms") else [polygon]
    vertices: list[tuple[float, float]] = []
    for part in parts:
        vertices += list(part.exterior.coords)[:-1]
        for ring in part.interiors:
            vertices += list(ring.coords)[:-1]
    return vertices


def _exact_geodesic(polygon: Any, source: tuple[float, float], probes: np.ndarray) -> np.ndarray:
    """Exact Euclidean geodesic distance inside ``polygon`` by visibility graph."""

    walk = polygon.buffer(1e-9)
    shapely.prepare(walk)
    nodes = [source, *_polygon_vertices(polygon)]
    count = len(nodes)
    visible = [[False] * count for _ in range(count)]
    for i in range(count):
        for j in range(i + 1, count):
            line = LineString([nodes[i], nodes[j]]) if nodes[i] != nodes[j] else None
            visible[i][j] = visible[j][i] = line is None or bool(walk.covers(line))
    dist = [math.inf] * count
    dist[0] = 0.0
    done = [False] * count
    for _ in range(count):
        u = min((k for k in range(count) if not done[k]), key=lambda k: dist[k])
        if dist[u] == math.inf:
            break
        done[u] = True
        for v in range(count):
            if visible[u][v]:
                dist[v] = min(dist[v], dist[u] + math.dist(nodes[u], nodes[v]))
    best = np.full(len(probes), math.inf)
    for node, base in zip(nodes, dist, strict=True):
        if base == math.inf:
            continue
        pairs = np.stack([np.broadcast_to(np.array(node), probes.shape), probes], axis=1)
        sees = shapely.covers(walk, shapely.linestrings(pairs))
        reach = base + np.hypot(probes[:, 0] - node[0], probes[:, 1] - node[1])
        best = np.where(sees, np.minimum(best, reach), best)
    return best


ZIGZAG = (
    box(0, 0, 8, 6)
    .difference(box(1.51, 0, 2.37, 4.6))
    .difference(box(3.63, 1.41, 4.49, 6))
    .difference(box(5.77, 0, 6.61, 4.55))
)


@pytest.mark.parametrize(
    ("label", "polygon", "start_xy", "end_xy", "end_t"),
    [
        # Concave-corner starts from the Opus stage-2 review of PR #33.
        (
            "obstacle-corner",
            box(0, 0, 10, 6).difference(box(4, 1.5, 6, 4.5)),
            (3.9, 1.4),
            (3.9, 4.6),
            4.0,
        ),
        ("zigzag-corner-loop", ZIGZAG, (2.43, 4.66), (2.43, 4.66), 3.0),
        ("zigzag-corner-far", ZIGZAG, (2.43, 4.66), (7.5, 1.0), 10.0),
    ],
)
def test_reachable_regions_cover_the_exact_continuous_reachable_set(
    label: str,
    polygon: Any,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    end_t: float,
) -> None:
    """Conservativeness: every grid square holding a point that satisfies both the
    forward and the backward exact geodesic bound is in R(t_i) (contract §4.4/§4.8).
    The previous snap-sized slack missed squares at concave corners."""

    floor_map = PolygonFloorMap(DESCRIPTOR, 0.0, {"WALK": polygon}, {})
    response = _run(
        _request(
            _endpoint("obs:a", 0.0, start_xy, pixel_sensitivity_m=0.01),
            _endpoint("obs:b", end_t, end_xy, pixel_sensitivity_m=0.01),
        ),
        floor_map,
    )
    assert response["status"] == "READY", label
    assert response["configuration"]["reach_slack_m"] == pytest.approx(
        0.25 * math.sqrt(2), abs=1e-6
    )

    minx, miny, maxx, maxy = polygon.bounds
    gx, gy = np.meshgrid(
        np.arange(minx + 0.05, maxx, 0.1), np.arange(miny + 0.05, maxy, 0.1), indexing="ij"
    )
    probes = np.stack([gx.ravel(), gy.ravel()], axis=1)
    probes = probes[shapely.covers(polygon, shapely.points(probes))]
    from_start = _exact_geodesic(polygon, start_xy, probes)
    from_end = _exact_geodesic(polygon, end_xy, probes)
    checked = 0
    for region in response["reachable_regions"]:
        t = region["timestamp_s"]
        cells = {(round(x / 0.25), round(y / 0.25)) for x, y in region["samples"]}
        inside = (from_start <= 2.0 * t - 0.01 + 1e-9) & (
            from_end <= 2.0 * (end_t - t) - 0.01 + 1e-9
        )
        for px, py in probes[inside]:
            cell = (round(px / 0.25), round(py / 0.25))
            if not polygon.covers(Point(cell[0] * 0.25, cell[1] * 0.25)):
                continue  # centre off the map: no cell exists (contract §4 rule 1)
            checked += 1
            assert cell in cells, (label, t, (px, py))
    assert checked > 1000


def test_endpoint_outside_map_is_not_snapped() -> None:
    # Disc (r = 0.1 m) centred 0.25 m left of the map: 0.15 m clear of it. The old
    # half-diagonal tolerance (0.177 m) accepted this and reported a route.
    request = _request(_endpoint("obs:a", 0.0, (-0.25, 3.0)), _endpoint("obs:b", 6.0, (9.0, 3.0)))
    response = _run(request, _obstacle_room())
    assert response["status"] == "UNKNOWN" and response["reason"] == "ENDPOINT_OUTSIDE_WALKABLE"
    assert response["hypotheses"] == []
    detail = next(item for item in response["trace"] if item["step"] == "FAIL_CLOSED")
    assert detail["endpoint"] == "start" and detail["distance_to_walkable_m"] == pytest.approx(0.15)


def _thin_wall_room() -> PolygonFloorMap:
    # 0.11 m wall (x 2.02-2.13) open only above y = 5.05; the room is 8 x 6 m.
    room = box(0, 0, 8, 6).difference(box(2.02, 0, 2.13, 5.05))
    return PolygonFloorMap(DESCRIPTOR, 0.0, {"WALK_ROOM": room}, {})


def test_thin_wall_is_not_crossed_by_a_seed_or_anchor() -> None:
    # Straight-line gap 0.62 m, but the walk round the wall end is about 8.4 m.
    start, end = _endpoint("obs:a", 0.0, (1.98, 1.0)), _endpoint("obs:b", 1.0, (2.6, 1.0))
    blocked = _run(_request(start, end), _thin_wall_room())
    assert blocked["status"] == "UNKNOWN", "false READY across a 0.11 m wall"
    assert blocked["reason"] == "ENDPOINTS_UNREACHABLE"

    # With time to walk round, every returned route stays on the map and above the wall end.
    around = _run(
        _request(_endpoint("obs:a", 0.0, (1.98, 1.0)), _endpoint("obs:b", 6.0, (2.6, 1.0))),
        _thin_wall_room(),
    )
    assert around["status"] == "READY"
    for hypothesis in around["hypotheses"]:
        assert hypothesis["checks"]["walkable"]["result"] == "PASS"
        assert max(y for _, y, _ in (s["position_m"] for s in hypothesis["samples"])) > 5.05
        wall = box(2.02, 0.0, 2.13, 5.05)
        points = [tuple(p[:2]) for p in hypothesis["route_m"]]
        assert not LineString(points).intersects(wall.buffer(-1e-6))


def test_anchors_lie_in_the_endpoint_region_on_the_map() -> None:
    response = _run(_obstacle_request(), _obstacle_room())
    for hypothesis in response["hypotheses"]:
        first, last = hypothesis["route_m"][0], hypothesis["route_m"][-1]
        assert math.dist(first[:2], (1.0, 3.0)) <= 0.1 + 1e-6
        assert math.dist(last[:2], (9.0, 3.0)) <= 0.1 + 1e-6


def test_empty_room_samples_are_inside_region_cells() -> None:
    room = PolygonFloorMap(DESCRIPTOR, 0.0, {"WALK_ROOM": box(0, 0, 10, 6)}, {})
    response = _run(_obstacle_request(top_k=5), room)
    consistency = _trace_step(response, "SAMPLE_REGION_CONSISTENCY")
    assert len(consistency) == 1
    assert consistency[0]["samples_checked"] == 29 * len(response["hypotheses"]) > 0
    assert consistency[0]["samples_outside_region_cell"] == 0


def test_region_mask_never_prunes_the_cell_of_a_passing_sample() -> None:
    times = _gap_times(0.0, 6.0)
    south_aisle = [[[3.0, 0.0], [7.0, 0.0], [7.0, 2.0], [3.0, 2.0]]]
    request = _obstacle_request(
        top_k=5, negative_evidence=[_negative("negev:south", times, south_aisle)]
    )
    response = _run(request, _obstacle_room())
    assert response["status"] == "READY"
    assert _trace_step(response, "SAMPLE_REGION_CONSISTENCY")[0]["samples_outside_region_cell"] == 0


def test_endpoint_cells_trace_reports_seeds() -> None:
    response = _run(_obstacle_request(), _obstacle_room())
    entries = {item["endpoint"]: item for item in _trace_step(response, "ENDPOINT_CELLS")}
    assert set(entries) == {"start", "end"}
    for item in entries.values():
        assert item["seed_cells"] > 0
        assert item["min_cell_offset_m"] is not None and item["min_cell_offset_m"] >= 0.0


def test_empty_region_reason_follows_whether_it_is_empty_without_the_unseen_mask() -> None:
    corridor = PolygonFloorMap(DESCRIPTOR, 0.0, {"WALK_C": box(0, 0, 20, 1)}, {})
    times = _gap_times(0.0, 3.0)
    footprint = [[[3.0, -1.0], [6.0, -1.0], [6.0, 2.0], [3.0, 2.0]]]
    start, end = _endpoint("obs:a", 0.0, (0.5, 0.5)), _endpoint("obs:b", 3.0, (6.5, 0.5))

    # Reachable on its own, emptied by the evidence: REACHABLE_SET_EMPTY.
    assert _run(_request(start, end), corridor)["status"] == "READY"
    blocked = _run(
        _request(start, end, negative_evidence=[_negative("negev:corridor", times, footprint)]),
        corridor,
    )
    assert blocked["reason"] == "REACHABLE_SET_EMPTY"
    assert _trace_step(blocked, "UNSEEN_MASK_APPLIED")[0]["cells_removed"] > 0

    # Unreachable at the speed limit even without evidence: ENDPOINTS_UNREACHABLE,
    # with or without evidence supplied.
    far = _endpoint("obs:b", 3.0, (9.5, 0.5))
    for evidence in ([], [_negative("negev:corridor", times, footprint)]):
        response = _run(_request(start, far, negative_evidence=evidence), corridor)
        assert response["reason"] == "ENDPOINTS_UNREACHABLE"


def test_region_truncation_keeps_evenly_spaced_cells() -> None:
    config = _config()
    config["limits"] = {**config["limits"], "max_region_samples": 20}
    room = PolygonFloorMap(DESCRIPTOR, 0.0, {"WALK_ROOM": box(0, 0, 10, 6)}, {})
    full = _run(_obstacle_request(), room)
    cut = _run(_obstacle_request(), room, config)
    assert "MAX_REGION_SAMPLES" in cut["limits"]["hit"]
    wide = max(
        range(len(full["reachable_regions"])), key=lambda i: full["reachable_regions"][i]["area_m2"]
    )
    region, reference = cut["reachable_regions"][wide], full["reachable_regions"][wide]
    assert region["truncated"] is True and len(region["samples"]) == 20
    assert region["area_m2"] == reference["area_m2"]  # area counts all cells, not the kept ones
    xs_full = [x for x, _ in reference["samples"]]
    xs_cut = [x for x, _ in region["samples"]]
    assert min(xs_cut) - min(xs_full) <= 0.5 and max(xs_full) - max(xs_cut) <= 0.5
    assert set(map(tuple, region["samples"])) <= set(map(tuple, reference["samples"]))


def test_failed_candidates_do_not_exclude_nearby_via_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    from amidst.blind_hypothesis import engine

    config = _config()
    config["limits"] = {**config["limits"], "max_candidate_paths": 100000}
    room = _obstacle_room()
    baseline = _trace_step(_run(_obstacle_request(), room, config), "ROUTE_POOL_BUILT")[0]

    original = engine._hypothesis
    calls = {"count": 0}

    def failing_first(*args: Any, **kwargs: Any) -> dict[str, Any]:
        candidate = original(*args, **kwargs)
        calls["count"] += 1
        if calls["count"] <= 10:  # the best routes fail, as if they hit negative evidence
            candidate["checks"]["unseen"]["result"] = "FAIL"
        return candidate

    monkeypatch.setattr(engine, "_hypothesis", failing_first)
    patched = _trace_step(_run(_obstacle_request(), room, config), "ROUTE_POOL_BUILT")[0]
    # A failed route would have excluded its 0.75 m neighbourhood; now it only excludes
    # one grid step, so alternatives next to it are still generated.
    assert patched["candidates"] > baseline["candidates"]
    assert (
        patched["via_cells_excluded_by_separation"] < baseline["via_cells_excluded_by_separation"]
    )


# ------------------------------------------------------------ D11: walkable UNKNOWN regions


def _seating_map() -> PolygonFloorMap:
    """Room A (x 0-4, walkable) overlapping a walkable-UNKNOWN seating area (x 3.5-8)."""

    return polygon_floor_map(
        descriptor=DESCRIPTOR,
        floor_z_m=0.0,
        regions={"WALK_A": [[0, 0], [4, 0], [4, 4], [0, 4]]},
        unknown_regions={"AREA_SEATING": [[3.5, 0], [8, 0], [8, 4], [3.5, 4]]},
        region_tiers={"WALK_A": "ANNOTATION_ONLY"},
    )


def test_unknown_region_is_passable_but_the_path_is_marked_unconfirmed() -> None:
    start, end = _endpoint("obs:a", 0.0, (1.0, 2.0)), _endpoint("obs:b", 6.0, (7.0, 2.0))
    response = _run(_request(start, end), _seating_map())
    assert response["status"] == "READY"
    assert response["hypotheses"]
    for hypothesis in response["hypotheses"]:
        walkable = hypothesis["checks"]["walkable"]
        assert walkable["result"] == "UNKNOWN" and walkable["violations"] == []
        assert walkable["unconfirmed_area_crossed"] is True
        segments = walkable["segments"]
        assert len(segments) == len(hypothesis["samples"]) + 1  # endpoint links included
        assert segments[0]["from_timestamp_s"] == 0.0 and segments[-1]["to_timestamp_s"] == 6.0
        by_label = {item["walkable"] for item in segments}
        assert by_label == {"TRUE", "UNKNOWN"}
        assert segments[0]["walkable"] == "TRUE" and segments[-1]["walkable"] == "UNKNOWN"
        for item in segments:
            if item["walkable"] == "UNKNOWN":
                assert "AREA_SEATING" in item["area_refs"] and "UNKNOWN" in item["tiers"]
        assert segments[0]["tiers"] == ["ANNOTATION_ONLY"]
        # An UNKNOWN-area route is kept (ACTIVE), never promoted to PASS.
        assert hypothesis["status"] == "ACTIVE"
    assert response["reason"] is None


def test_unknown_region_cells_are_flagged_in_reachable_regions() -> None:
    start, end = _endpoint("obs:a", 0.0, (1.0, 2.0)), _endpoint("obs:b", 6.0, (7.0, 2.0))
    response = _run(_request(start, end), _seating_map())
    flagged = 0
    for region in response["reachable_regions"]:
        indices = region["walkable_unknown_sample_indices"]
        flagged += len(indices)
        for index, (x, _) in enumerate(region["samples"]):
            # Cells in the overlap (x <= 4) belong to the confirmed room first.
            assert (index in indices) == (x > 4.0 + 1e-9)
    assert flagged > 0


def test_confirmed_only_path_is_not_marked_unconfirmed() -> None:
    start, end = _endpoint("obs:a", 0.0, (0.5, 2.0)), _endpoint("obs:b", 2.0, (3.0, 2.0))
    response = _run(_request(start, end), _seating_map())
    assert response["status"] == "READY"
    for hypothesis in response["hypotheses"]:
        walkable = hypothesis["checks"]["walkable"]
        assert walkable["result"] == "PASS" and walkable["unconfirmed_area_crossed"] is False
        assert {item["walkable"] for item in walkable["segments"]} == {"TRUE"}


def test_endpoint_inside_unknown_region_is_valid_and_its_link_is_unknown() -> None:
    start, end = _endpoint("obs:a", 0.0, (6.0, 2.0)), _endpoint("obs:b", 3.0, (7.5, 2.0))
    response = _run(_request(start, end), _seating_map())
    assert response["status"] == "READY"
    for hypothesis in response["hypotheses"]:
        segments = hypothesis["checks"]["walkable"]["segments"]
        assert segments[0]["walkable"] == "UNKNOWN" and segments[-1]["walkable"] == "UNKNOWN"


def test_unknown_region_does_not_make_the_outside_of_the_map_walkable() -> None:
    start, end = _endpoint("obs:a", 0.0, (1.0, 2.0)), _endpoint("obs:b", 6.0, (9.0, 2.0))
    response = _run(_request(start, end), _seating_map())
    assert response["reason"] == "ENDPOINT_OUTSIDE_WALKABLE"


def test_unknown_region_map_validation() -> None:
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    with pytest.raises(Exception, match="unique"):
        polygon_floor_map(
            descriptor=DESCRIPTOR,
            floor_z_m=0.0,
            regions={"X": square},
            unknown_regions={"X": square},
        )
    with pytest.raises(Exception, match="tier UNKNOWN"):
        polygon_floor_map(
            descriptor=DESCRIPTOR,
            floor_z_m=0.0,
            regions={"A": square},
            unknown_regions={"U": [[2, 0], [3, 0], [3, 1], [2, 1]]},
            region_tiers={"U": "SOURCE_DERIVED"},
        )


# ---------------------------------------------------------- D7: endpoint substitution (§3.1.1)


def _substitution(side: str, **overrides: Any) -> dict[str, Any]:
    outward = -0.2 if side == "start" else 0.2
    original_t = 0.2 if side == "start" else 5.8
    record: dict[str, Any] = {
        "rule": "SAME_TRACK_NEAREST_USABLE_OUTWARD_V1",
        "track_ref": "UNKNOWN",
        "original": {
            "observation_ref": f"obs:orig-{side}",
            "timestamp_s": original_t,
            "ground_estimate_status": "UNKNOWN",
            "ground_estimate_reason": "HEAD_ANCHOR_UNRELIABLE",
        },
        "substitute": {
            "observation_ref": "obs:a" if side == "start" else "obs:b",
            "timestamp_s": round(original_t + outward, 6),
        },
        "time_offset_s": outward,
        "max_offset_s": 1.0,
        "skipped_observation_refs": [],
    }
    record.update(overrides)
    return record


def _substituted_request(side: str, **overrides: Any) -> dict[str, Any]:
    """Interval 0.0-6.0 s whose ``side`` endpoint is the substitute of an observation
    0.2 s inside; the endpoint fields (ref, time, estimate) are the substitute's."""

    request = _obstacle_request()
    request[side]["substitution"] = _substitution(side, **overrides)
    return request


@pytest.mark.parametrize("side", ["start", "end"])
def test_substituted_endpoint_is_accepted_and_echoed_unchanged(side: str) -> None:
    response = _run(_substituted_request(side), _obstacle_room())
    assert response["status"] == "READY"  # not blocked by GROUND_ESTIMATE_OBSERVATION_MISMATCH
    assert not _trace_step(response, "ENDPOINT_REJECTED")
    assert response["interval"]["start_s"] == 0.0 and response["interval"]["end_s"] == 6.0
    record = _substitution(side)
    entry = response["endpoint_substitutions"][0]
    assert len(response["endpoint_substitutions"]) == 1
    assert entry == {
        "endpoint": side.upper(),
        "original_observation_ref": record["original"]["observation_ref"],
        "original_timestamp_s": record["original"]["timestamp_s"],
        "original_reason": "HEAD_ANCHOR_UNRELIABLE",
        "substitute_observation_ref": record["substitute"]["observation_ref"],
        "substitute_timestamp_s": record["substitute"]["timestamp_s"],
        "time_offset_s": record["time_offset_s"],
        "max_offset_s": 1.0,
        "rule": record["rule"],
        "track_ref": "UNKNOWN",
        "skipped_observation_refs": [],
    }
    step = _trace_step(response, "ENDPOINT_SUBSTITUTED")
    assert step == [
        {
            "step": "ENDPOINT_SUBSTITUTED",
            "endpoint": side.upper(),
            "original_timestamp_s": record["original"]["timestamp_s"],
            "substitute_timestamp_s": record["substitute"]["timestamp_s"],
            "time_offset_s": record["time_offset_s"],
        }
    ]
    assert verify_output_sha256(response)


def test_unsubstituted_response_has_empty_substitution_list() -> None:
    explicit_null = _obstacle_request()
    explicit_null["start"]["substitution"] = None
    for request in (_obstacle_request(), explicit_null):
        response = _run(request, _obstacle_room())
        assert response["status"] == "READY" and response["endpoint_substitutions"] == []


def test_substitution_does_not_excuse_a_mismatched_estimate() -> None:
    request = _substituted_request("start")
    request["start"]["ground_estimate"]["observation_ref"] = "obs:orig-start"  # original's estimate
    response = _run(request, _obstacle_room())
    assert response["reason"] == "ENDPOINT_UNUSABLE"
    assert _trace_step(response, "ENDPOINT_REJECTED")[0]["problem"] == (
        "GROUND_ESTIMATE_OBSERVATION_MISMATCH"
    )


@pytest.mark.parametrize(
    ("side", "override", "problem"),
    [
        ("start", {"time_offset_s": 0.2, "original": None}, "SHAPE"),
        ("start", {"rule": "NEAREST_ANY"}, "RULE"),
        ("start", {"time_offset_s": 0.2}, "TIME_OFFSET_INCONSISTENT"),
        ("end", {"time_offset_s": -0.2}, "TIME_OFFSET_INCONSISTENT"),
        ("start", {"max_offset_s": 2.0}, "MAX_OFFSET_INCONSISTENT"),
        ("start", {"skipped_observation_refs": "none"}, "SHAPE"),
        ("start", {"surprise": 1}, "SHAPE"),
    ],
)
def test_invalid_substitution_fails_closed(
    side: str, override: dict[str, Any], problem: str
) -> None:
    response = _run(_substituted_request(side, **override), _obstacle_room())
    assert response["status"] == "UNKNOWN" and response["reason"] == "ENDPOINT_SUBSTITUTION_INVALID"
    assert response["hypotheses"] == [] and response["endpoint_substitutions"] == []
    assert next(i for i in response["trace"] if i["step"] == "FAIL_CLOSED")["problem"] == problem


def test_substitution_must_be_outward_within_limit_and_from_an_unknown_original() -> None:
    inward = _substituted_request("start")
    inward["start"]["substitution"]["original"]["timestamp_s"] = -0.2  # substitute is *inside*
    inward["start"]["substitution"]["time_offset_s"] = 0.2
    too_far = _substituted_request("end")
    too_far["end"]["substitution"]["original"]["timestamp_s"] = 4.7
    too_far["end"]["substitution"]["time_offset_s"] = 1.3
    usable_original = _substituted_request("start")
    usable_original["start"]["substitution"]["original"]["ground_estimate_status"] = "READY"
    same_ref = _substituted_request("start")
    same_ref["start"]["substitution"]["original"]["observation_ref"] = "obs:a"
    cases = {
        "NOT_OUTWARD": inward,
        "OFFSET_TOO_LARGE": too_far,
        "ORIGINAL_NOT_UNKNOWN": usable_original,
        "SUBSTITUTE_NOT_THE_ENDPOINT": same_ref,
    }
    for problem, request in cases.items():
        response = _run(request, _obstacle_room())
        assert response["reason"] == "ENDPOINT_SUBSTITUTION_INVALID", problem
        assert (
            next(i for i in response["trace"] if i["step"] == "FAIL_CLOSED")["problem"] == problem
        )

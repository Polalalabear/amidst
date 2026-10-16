"""Synthetic-map unit tests for the K1 blind-interval hypothesis module.

All maps and endpoints here are synthetic test geometry (metres), not Office data.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest
from shapely.geometry import box

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
    # (max speed 2 m/s * 0.2 s, metric factor and one half-diagonal of snapping).
    reach = 2.0 * 0.2 * 1.0824 + 0.1 + 0.25 * math.sqrt(2) / 2
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
    # Reachable regions exclude cells whose body disc (r = 0.25) is fully inside
    # the footprint (x 3-7, y 0-2), i.e. centres in x 3.25-6.75, y 0.25-1.75.
    for region in response["reachable_regions"]:
        assert not any(3.25 <= x <= 6.75 and 0.25 <= y <= 1.75 for x, y in region["samples"])


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
    response = _run(_obstacle_request(previous_response_sha256="f" * 64), _obstacle_room())
    assert response["reason"] == "PRUNING_RERUN_NOT_IMPLEMENTED"


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

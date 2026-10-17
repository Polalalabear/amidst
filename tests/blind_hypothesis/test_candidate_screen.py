"""K8c tests: S2 cross-camera candidate screen (``candidate_screen``).

All geometry is synthetic test data (metres) shaped like K8 design S2: one table in
a room, FRONT endpoint west of it. No Office asset, GT or renderer trajectory.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from shapely.geometry import box

from amidst.blind_hypothesis import (
    FloorMapDescriptor,
    HypothesisRequestError,
    PolygonFloorMap,
    canonical_sha256,
    verify_output_sha256,
)
from amidst.blind_hypothesis import candidate_screen as screen
from amidst.blind_hypothesis.candidate_screen import screen_cross_camera_candidates

ROOT = Path(__file__).resolve().parents[2]
SCENE = "synthetic-k8c"
DESCRIPTOR = FloorMapDescriptor(
    kind="SYNTHETIC_TEST",
    map_ref="synthetic:k8c-map",
    sha256="0" * 64,
    walkable_ref="synthetic:walk",
    portal_ref="synthetic:portal",
    floor_id="F",
)
SOURCE_BINDING = {"run_ref": "run:k8c-synthetic", "clock_id": "SYNTHETIC_5HZ"}
FRONT_XY = (38.60, 49.93)
REAR_XY = (45.20, 49.93)


def _config() -> dict[str, Any]:
    config = json.loads((ROOT / "configs" / "blind_hypothesis_v1.json").read_text())
    config["scenes"][SCENE] = {"time_step_s": 0.2, "body_radius_m": 0.25}
    return config


def _room() -> PolygonFloorMap:
    # Table (hole) between FRONT and REAR; north/south corridors around it.
    room = box(20, 38, 50, 55).difference(box(39.67, 49.14, 44.05, 50.71))
    return PolygonFloorMap(DESCRIPTOR, 0.0, {"WALK_ROOM": room}, {})


def _endpoint(ref: str, camera: str, t: float, xy: tuple[float, float]) -> dict[str, Any]:
    return {
        "observation_ref": ref,
        "camera_id": camera,
        "timestamp_s": t,
        "evidence_state": "PROJECTED_OBSERVATION",
        "ground_estimate": {
            "schema_version": "office-demo.interval-observation.v1",
            "observation_ref": ref,
            "camera_id": camera,
            "timestamp_s": t,
            "status": "READY",
            "reason": None,
            "evidence_state": "PROJECTED_OBSERVATION",
            "estimate_kind": "POINT",
            "point_m": [xy[0], xy[1], 0.0],
            "segment": None,
            "pixel_sensitivity_m": 0.15,
            "contact_quality": {"status": "PASS"},
            "provenance": {"gt_read": False, "data_origin": "SYNTHETIC"},
        },
    }


def _front() -> dict[str, Any]:
    return _endpoint("obs:front", "SYN_CAM_A", 10.0, FRONT_XY)


def _candidate(ref: str, t: float, xy: tuple[float, float] = REAR_XY) -> dict[str, Any]:
    return {"candidate_ref": ref, "end": _endpoint(f"obs:{ref}", "SYN_CAM_B", t, xy)}


def _base(**overrides: Any) -> dict[str, Any]:
    base = {
        "session_ref": "session:k8c",
        "scene_id": SCENE,
        "top_k": 3,
        "negative_evidence": [],
    }
    base.update(overrides)
    return base


def _screen(
    candidates: list[dict[str, Any]],
    *,
    start: dict[str, Any] | None = None,
    base: dict[str, Any] | None = None,
    floor_map: PolygonFloorMap | None = None,
) -> dict[str, Any]:
    return screen_cross_camera_candidates(
        start if start is not None else _front(),
        candidates,
        base_request=base if base is not None else _base(),
        config=_config(),
        config_sha256="c" * 64,
        floor_map=floor_map if floor_map is not None else _room(),
        source_binding=SOURCE_BINDING,
    )


def _one(candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return _screen([candidate], **kwargs)["results"][0]


def _blanket_negative_evidence(times: list[float]) -> dict[str, Any]:
    """A no-detection entry whose visible floor covers the whole room at every step."""

    entry = {
        "negative_evidence_ref": "neg:all",
        "origin": "BLIND_INTERVAL_BASELINE",
        "camera_id": "SYN_CAM_C",
        "frame_refs": [{"frame_ref": f"frame:{t}", "timestamp_s": t} for t in times],
        "visibility_ref": "visibility:all",
        "detection_result": "NO_DETECTION",
        "detection_producer": {"producer": "test-perception", "version": "v1"},
        "retrieval_query_id": None,
        "visible_floor": {
            "method": "SOURCE_MESH_RAYCAST",
            "polygons": [[[20, 38], [50, 38], [50, 55], [20, 55]]],
        },
    }
    entry["sha256"] = canonical_sha256(entry)
    return entry


# --------------------------------------------------------------- §4.1 mapping table


def test_ready_with_hypotheses_is_reachable() -> None:
    row = _one(_candidate("R1", 16.0))
    assert row["verdict"] == screen.REACHABLE
    assert (row["k1_status"], row["k1_reason"]) == ("READY", None)
    assert row["reason_code"] == screen.REASON_K1_READY
    assert row["k1_hypothesis_count"] >= 1
    assert row["straight_line_m"] is None


def test_endpoints_unreachable_by_straight_line_is_unreachable_under_config() -> None:
    # R2: gap well above 2.0 m/s x 6.0 s = 12 m.
    row = _one(_candidate("R2", 16.0, (27.0, 40.0)))
    assert row["verdict"] == screen.UNREACHABLE_UNDER_CONFIG
    assert row["k1_reason"] == "ENDPOINTS_UNREACHABLE"
    assert row["reason_code"] == screen.REASON_STRAIGHT_LINE
    assert row["straight_line_m"] is not None and row["straight_line_m"] > 12.0
    assert row["empty_at_s"] is None


def test_endpoints_unreachable_by_empty_reach_is_unreachable_under_config() -> None:
    # Two rooms split by a closed wall gap: the straight-line gap is tiny (inside the
    # speed bound) but the geodesic reach bound never links them (empty_at_s branch).
    rooms = PolygonFloorMap(
        DESCRIPTOR,
        0.0,
        {"WALK_A": box(20, 38, 30, 55), "WALK_B": box(30.4, 38, 40, 55)},
        {},
    )
    start = _endpoint("obs:front", "SYN_CAM_A", 10.0, (29.5, 45.0))
    candidate = _candidate("R4", 16.0, (30.9, 45.0))
    row = _one(candidate, start=start, floor_map=rooms)
    assert row["k1_reason"] == "ENDPOINTS_UNREACHABLE"
    assert row["verdict"] == screen.UNREACHABLE_UNDER_CONFIG
    assert row["reason_code"] == screen.REASON_REACH_EMPTY_BY_SPEED
    assert row["straight_line_m"] is None and row["empty_at_s"]


def test_reachable_set_empty_with_negative_evidence_is_its_own_verdict() -> None:
    times = [round(10.0 + 0.2 * i, 6) for i in range(1, 29)]
    base = _base(negative_evidence=[_blanket_negative_evidence(times)])
    row = _one(_candidate("R1", 16.0), base=base)
    assert row["k1_reason"] == "REACHABLE_SET_EMPTY"
    assert row["verdict"] == screen.UNREACHABLE_UNDER_CONFIG_AND_EVIDENCE
    assert row["reason_code"] == screen.REASON_REACH_EMPTY_BY_EVIDENCE
    # The same pair without evidence stays reachable: the exclusion is evidence-driven.
    assert _one(_candidate("R1", 16.0))["verdict"] == screen.REACHABLE


def test_no_hypothesis_passed_checks_is_undetermined_not_excluded() -> None:
    # R3: the reach bound is non-empty but no sampled route passes the speed check.
    row = _one(_candidate("R3", 13.2))
    assert row["k1_reason"] == "NO_HYPOTHESIS_PASSED_CHECKS"
    assert row["verdict"] == screen.UNDETERMINED
    assert row["reason_code"] == screen.REASON_SAMPLED_POOL_NOT_PROOF


def test_other_unknown_reasons_are_undetermined() -> None:
    unusable = _candidate("RU", 16.0)
    unusable["end"]["ground_estimate"] = None
    too_long = _candidate("RL", 10.0 + 500.0)
    for candidate, reason in ((unusable, "ENDPOINT_UNUSABLE"), (too_long, "INTERVAL_TOO_LONG")):
        row = _one(candidate)
        assert row["k1_reason"] == reason
        assert row["verdict"] == screen.UNDETERMINED
        assert row["reason_code"] == screen.REASON_NOT_A_REACHABILITY_RESULT


def test_endpoint_outside_walkable_is_undetermined() -> None:
    row = _one(_candidate("RO", 16.0, (80.0, 80.0)))
    assert row["k1_reason"] == "ENDPOINT_OUTSIDE_WALKABLE"
    assert row["verdict"] == screen.UNDETERMINED


def test_ready_without_hypotheses_and_unknown_status_fail_closed() -> None:
    # Not covered by §4.1 (UNKNOWN in the spec): fail closed to UNDETERMINED.
    assert screen._verdict({"status": "READY", "hypotheses": [], "reason": None})[:2] == (
        screen.UNDETERMINED,
        screen.REASON_READY_WITHOUT_HYPOTHESES,
    )
    assert screen._verdict({"status": "WEIRD"})[:2] == (
        screen.UNDETERMINED,
        screen.REASON_STATUS_UNRECOGNISED,
    )
    assert screen._verdict({"status": "UNKNOWN", "reason": "ENDPOINTS_UNREACHABLE"})[:2] == (
        screen.UNREACHABLE_UNDER_CONFIG,
        screen.REASON_UNREACHABLE_UNSPECIFIED,
    )


# ------------------------------------------------------------------- invariants


def test_identity_is_always_unconfirmed_and_authority_unknown() -> None:
    out = _screen([_candidate("R1", 16.0), _candidate("R2", 16.0, (27.0, 40.0))])
    assert out["identity_verdict"] == "UNCONFIRMED"
    assert out["physical_authority"] == "UNKNOWN"
    assert out["gt_read"] is False
    assert out["verdict_basis"] == "CONFIGURED_SPEED_RANGE_NOT_PROBABILITY"
    assert all(row["identity_verdict"] == "UNCONFIRMED" for row in out["results"])
    assert not any("probab" in key or "score" in key for row in out["results"] for key in row)


def test_deterministic_and_sealed() -> None:
    candidates = [_candidate("R1", 16.0), _candidate("R3", 13.2)]
    first, second = _screen(candidates), _screen(copy.deepcopy(candidates))
    assert first == second
    body = {k: v for k, v in first.items() if k != "output_sha256"}
    assert first["output_sha256"] == canonical_sha256(body)


def test_inputs_not_mutated_and_order_kept() -> None:
    candidates = [_candidate("R3", 13.2), _candidate("R1", 16.0)]
    start, base = _front(), _base()
    snapshot = copy.deepcopy((start, candidates, base))
    out = _screen(candidates, start=start, base=base)
    assert (start, candidates, base) == snapshot
    assert [row["candidate_ref"] for row in out["results"]] == ["R3", "R1"]


def test_k1_response_hash_is_the_k1_output_hash() -> None:
    from amidst.blind_hypothesis import generate_blind_hypotheses

    candidate = _candidate("R1", 16.0)
    request = {
        "schema_version": "office-demo.blind-hypothesis-request.v1",
        "session_ref": "session:k8c",
        "scene_id": SCENE,
        "candidate_ref": "R1",
        "start": _front(),
        "end": candidate["end"],
        "top_k": 3,
        "negative_evidence": [],
        "previous_response_sha256": None,
    }
    response = generate_blind_hypotheses(
        request,
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_room(),
        source_binding=SOURCE_BINDING,
    )
    assert verify_output_sha256(response)
    assert _one(candidate)["k1_response_sha256"] == response["output_sha256"]


# ----------------------------------------------------------- input rejection (no GT)


@pytest.mark.parametrize("field", ["ground_truth", "gt_trajectory", "visibility", "depth"])
def test_base_request_rejects_gt_or_trajectory_fields(field: str) -> None:
    with pytest.raises(HypothesisRequestError, match="base_request"):
        _screen([_candidate("R1", 16.0)], base=_base(**{field: [[0, 0]]}))


@pytest.mark.parametrize("field", ["ground_truth", "trajectory", "true_position"])
def test_candidate_rejects_gt_or_trajectory_fields(field: str) -> None:
    candidate = _candidate("R1", 16.0)
    candidate[field] = [[1.0, 2.0]]
    with pytest.raises(HypothesisRequestError, match="candidates"):
        _screen([candidate])


def test_endpoint_with_extra_field_is_rejected_by_k1() -> None:
    candidate = _candidate("R1", 16.0)
    candidate["end"]["gt_position"] = [1.0, 2.0, 0.0]
    with pytest.raises(HypothesisRequestError, match="candidate R1"):
        _screen([candidate])


def test_duplicate_or_blank_candidate_refs_are_rejected() -> None:
    with pytest.raises(HypothesisRequestError, match="unique"):
        _screen([_candidate("R1", 16.0), _candidate("R1", 17.0)])
    with pytest.raises(HypothesisRequestError, match="candidate_ref"):
        _screen([_candidate("", 16.0)])


# ------------------------------------------------------- S2 integration (three verdicts)


def test_s2_three_candidates_give_three_verdicts() -> None:
    out = _screen(
        [
            _candidate("R1", 16.0),
            _candidate("R2", 16.0, (27.0, 40.0)),
            _candidate("R3", 13.2),
        ]
    )
    verdicts = {row["candidate_ref"]: row["verdict"] for row in out["results"]}
    assert verdicts == {
        "R1": screen.REACHABLE,
        "R2": screen.UNREACHABLE_UNDER_CONFIG,
        "R3": screen.UNDETERMINED,
    }
    # The excluded candidate is only excluded under the configured speed bound.
    r2 = out["results"][1]
    assert r2["reason_code"] == screen.REASON_STRAIGHT_LINE
    assert out["verdict_basis"] == "CONFIGURED_SPEED_RANGE_NOT_PROBABILITY"

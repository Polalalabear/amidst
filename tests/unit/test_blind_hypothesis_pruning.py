"""Pruning re-run, retrieval-to-evidence conversion and convergence summary (task K5).

Synthetic maps and MOCK, contract-shaped retrieval responses only; no Office data and
no real retrieval API (C5 is not delivered). Map and request helpers come from
``test_blind_hypothesis``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from test_blind_hypothesis import (
    _gap_times,
    _negative,
    _obstacle_request,
    _obstacle_room,
    _run,
)

from amidst.blind_hypothesis import (
    applied_frame_keys_from_request,
    canonical_sha256,
    generate_blind_hypotheses,
    negative_evidence_from_retrieval,
    pruning_convergence_summary,
    verify_output_sha256,
)

ROOT = Path(__file__).resolve().parents[2]
SOUTH_AISLE = [[3.0, 0.0], [7.0, 0.0], [7.0, 2.0], [3.0, 2.0]]
NORTH_AISLE = [[3.0, 4.0], [7.0, 4.0], [7.0, 6.0], [3.0, 6.0]]
WHOLE_ROOM = [[-1.0, -1.0], [11.0, -1.0], [11.0, 7.0], [-1.0, 7.0]]
WINDOW = [2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6]
FLOOR_Z = 0.0
DETECTOR = {
    "producer": "mock-perception",
    "version": "v2",
    "difference_threshold": 20,
    "min_pixels": 28,
}


# ----------------------------------------------------------------------- helpers


def _evaluation(count: int | None = 0, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "frame_available": True,
        "rgb_hash_verified": True,
        "provenance_ok": True,
        "perception_evaluated": True,
        "measurement_count": count,
        "detection_producer": dict(DETECTOR),
    }
    record.update(overrides)
    return record


def _frame(ref: str, t: float, method: str = "SOURCE_MESH_RAYCAST") -> dict[str, Any]:
    return {
        "frame_ref": ref,
        "timestamp_s": t,
        "reason": {
            "kind": "REACHABLE_REGION_IN_VIEW",
            "footprint_method": method,
            "walkable_status": "TRUE",
        },
    }


def _retrieval(
    times: list[float],
    *,
    camera: str = "CAM_REAR",
    method: str = "SOURCE_MESH_RAYCAST",
    substitutions: list[dict[str, Any]] | None = None,
    interval: tuple[float, float] | None = (0.0, 6.0),
) -> dict[str, Any]:
    query: dict[str, Any] = {"query_kind": "HYPOTHESIS", "endpoint_substitutions": substitutions}
    if interval is not None:
        query["hypothesis_interval"] = {"start_s": interval[0], "end_s": interval[1]}
    return {
        "schema_version": "workbench.frame-retrieval.v1",
        "status": "READY",
        "reason": None,
        "query_id": "frq:mock",
        "query": query,
        "results": [
            {
                "camera_id": camera,
                "visibility_ref": f"visidx:{camera}",
                "method": method,
                "windows": [
                    {
                        "start_s": times[0],
                        "end_s": times[-1],
                        "frames": [_frame(f"frame:{camera}:{t}", t, method) for t in times],
                    }
                ],
            }
        ],
    }


def _evaluations(response: dict[str, Any], **overrides: Any) -> dict[str, dict[str, Any]]:
    return {
        f["frame_ref"]: _evaluation(**overrides)
        for r in response["results"]
        for w in r["windows"]
        for f in w["frames"]
    }


def _visibility(polygons: list[list[list[float]]], camera: str = "CAM_REAR") -> dict[str, Any]:
    return {
        f"visidx:{camera}": {
            "method": "SOURCE_MESH_RAYCAST",
            "floor_z_m": FLOOR_Z,
            "polygons": polygons,
            "index_sha256": "a" * 64,
            "visibility_rule": "FOOT_AND_TORSO_PROBES_VISIBLE",
            "detectability": {"detector": dict(DETECTOR)},
        }
    }


def _candidates(
    polygons: list[list[list[float]]], times: list[float] = WINDOW, **kwargs: Any
) -> list[dict[str, Any]]:
    response = _retrieval(times, **kwargs)
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response),
        visibility_entries=_visibility(polygons),
    )
    return result["negative_evidence_candidates"]


def _rerun(
    previous: dict[str, Any], evidence: list[dict[str, Any]], **request: Any
) -> dict[str, Any]:
    from test_blind_hypothesis import _config

    return generate_blind_hypotheses(
        _obstacle_request(
            negative_evidence=evidence,
            previous_response_sha256=previous["output_sha256"],
            **request,
        ),
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
        previous_response=previous,
    )


def _y_at(hypothesis: dict[str, Any], t: float) -> float:
    return next(s for s in hypothesis["samples"] if s["timestamp_s"] == t)["position_m"][1]


@pytest.fixture(scope="module")
def first() -> dict[str, Any]:
    return _run(_obstacle_request(), _obstacle_room())


@pytest.fixture(scope="module")
def south_candidates() -> list[dict[str, Any]]:
    return _candidates([SOUTH_AISLE])


@pytest.fixture(scope="module")
def pruned(first: dict[str, Any], south_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return _rerun(first, south_candidates)


# ------------------------------------------------------------ pruning re-run (§6)


def test_new_evidence_prunes_the_southern_route_and_shrinks_the_region(
    first: dict[str, Any], pruned: dict[str, Any]
) -> None:
    assert pruned["status"] == "READY" and verify_output_sha256(pruned)
    south = {h["hypothesis_ref"] for h in first["hypotheses"] if _y_at(h, 3.0) < 2.0}
    assert south, "the synthetic map must offer a southern route"

    assert {h["hypothesis_ref"] for h in pruned["pruned_hypotheses"]} == south
    for record in pruned["pruned_hypotheses"]:
        assert record["status"] == "PRUNED" and record["rank"] is None
        assert record["pruned_by"] == pruned["pruning_log"][0]["pruning_ref"]
        assert record["checks"]["unseen"]["result"] == "FAIL"
        assert {c["negative_evidence_ref"] for c in record["checks"]["unseen"]["conflicts"]} == {
            pruned["negative_evidence_applied"][0]
        }
    survivors = [h for h in pruned["hypotheses"] if h["hypothesis_ref"] not in south]
    assert survivors == pruned["hypotheses"]  # no pruned path is ACTIVE again
    assert all(h["status"] == "ACTIVE" for h in pruned["hypotheses"])
    assert [h["rank"] for h in pruned["hypotheses"]] == list(range(1, len(survivors) + 1))
    assert {h["hypothesis_ref"] for h in pruned["hypotheses"]} & {
        h["hypothesis_ref"] for h in first["hypotheses"]
    }, "surviving northern paths keep their stable refs"

    (entry,) = pruned["pruning_log"]
    assert entry["pruning_ref"].startswith("pruning:") and entry["order"] == 1
    assert entry["negative_evidence_ref"] == pruned["negative_evidence_applied"][0]
    assert entry["camera_id"] == "CAM_REAR" and entry["time_window_s"] == [2.4, 3.6]
    assert entry["hypotheses_pruned"] == sorted(south)
    assert entry["previous_response_sha256"] == first["output_sha256"]
    assert entry["region_area_after_m2"] < entry["region_area_before_m2"]

    before = {r["timestamp_s"]: r["area_m2"] for r in first["reachable_regions"]}
    after = {r["timestamp_s"]: r["area_m2"] for r in pruned["reachable_regions"]}
    assert all(after[t] < before[t] for t in WINDOW)
    assert all(after[t] == before[t] for t in before if t not in WINDOW)
    assert pruned["reason"] is None
    assert any(s["step"] == "PRUNING_RERUN" for s in pruned["trace"])


def test_pruning_never_reports_the_transitional_reason(pruned: dict[str, Any]) -> None:
    assert "PRUNING_RERUN_NOT_IMPLEMENTED" not in json.dumps(pruned)


def test_empty_polygons_prune_nothing(first: dict[str, Any]) -> None:
    candidates = _candidates([])
    assert candidates[0]["visible_floor"]["polygons"] == []
    result = _rerun(first, candidates)

    assert result["status"] == "READY"
    assert result["pruned_hypotheses"] == []
    assert [h["hypothesis_ref"] for h in result["hypotheses"]] == [
        h["hypothesis_ref"] for h in first["hypotheses"]
    ]
    assert result["reachable_regions"] == first["reachable_regions"]
    (entry,) = result["pruning_log"]
    assert entry["hypotheses_pruned"] == []
    # No footprint to subtract: the area is still the real mean region area over the
    # entry's steps, not 0.0.
    steps = [r["area_m2"] for r in first["reachable_regions"] if r["timestamp_s"] in WINDOW]
    expected = round(sum(steps) / len(steps), 6)
    assert expected > 0
    assert entry["region_area_before_m2"] == entry["region_area_after_m2"] == expected


def test_footprint_eroded_away_still_reports_the_real_area(first: dict[str, Any]) -> None:
    sliver = [[[3.0, 3.0], [3.3, 3.0], [3.3, 3.3], [3.0, 3.3]]]  # smaller than the erosion
    result = _rerun(first, _candidates(sliver))
    (entry,) = result["pruning_log"]
    assert entry["region_area_before_m2"] == entry["region_area_after_m2"] > 0
    assert result["pruned_hypotheses"] == []


def test_pruning_log_is_appended_across_chained_reruns(
    first: dict[str, Any], pruned: dict[str, Any], south_candidates: list[dict[str, Any]]
) -> None:
    north = _candidates([NORTH_AISLE], [3.8, 4.0, 4.2, 4.4])
    # Every northern path is also visible there, so use a footprint that spares the
    # remaining routes' corridor while still acting: a second camera, same shape.
    north[0]["camera_id"] = "CAM_REAR_2"
    north[0]["sha256"] = canonical_sha256({k: v for k, v in north[0].items() if k != "sha256"})
    second = _rerun(pruned, [*south_candidates, north[0]])

    assert second["negative_evidence_applied"] == [
        south_candidates[0]["negative_evidence_ref"],
        north[0]["negative_evidence_ref"],
    ]
    assert second["pruning_log"][0] == pruned["pruning_log"][0]  # carried over unchanged
    assert [e["order"] for e in second["pruning_log"]] == [1, 2]
    assert second["pruning_log"][1]["previous_response_sha256"] == pruned["output_sha256"]
    assert second["pruning_log"][1]["negative_evidence_ref"] == north[0]["negative_evidence_ref"]
    # Paths pruned in the earlier step are not listed again (only this step's).
    first_pruned = {h["hypothesis_ref"] for h in pruned["pruned_hypotheses"]}
    assert not first_pruned & {h["hypothesis_ref"] for h in second["pruned_hypotheses"]}


def test_reachable_set_emptied_by_evidence_fails_closed_without_relaxing(
    first: dict[str, Any],
) -> None:
    candidates = _candidates([WHOLE_ROOM], [3.0])
    result = _rerun(first, candidates)

    assert result["status"] == "UNKNOWN" and result["reason"] == "REACHABLE_SET_EMPTY"
    assert result["hypotheses"] == [] and result["reachable_regions"] == []
    assert result["pruned_hypotheses"] == [] and result["pruning_log"] == []
    detail = next(s for s in result["trace"] if s["step"] == "FAIL_CLOSED")
    assert detail["empty_at_s"] == [3.0]
    assert detail["first_emptying_negative_evidence_ref"] == candidates[0]["negative_evidence_ref"]


def test_rerun_is_deterministic(
    first: dict[str, Any], south_candidates: list[dict[str, Any]]
) -> None:
    one = _rerun(copy.deepcopy(first), copy.deepcopy(south_candidates))
    two = _rerun(copy.deepcopy(first), copy.deepcopy(south_candidates))
    assert one == two
    assert one["output_sha256"] == two["output_sha256"]
    assert canonical_sha256(one) == canonical_sha256(two)


# ------------------------------------------------- append-only and hash verification


def test_previous_response_object_is_required(
    first: dict[str, Any], south_candidates: list[dict[str, Any]]
) -> None:
    from test_blind_hypothesis import _config

    response = generate_blind_hypotheses(
        _obstacle_request(
            negative_evidence=south_candidates, previous_response_sha256=first["output_sha256"]
        ),
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
    )
    assert response["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    detail = next(s for s in response["trace"] if s["step"] == "FAIL_CLOSED")
    assert detail["problem"] == "PREVIOUS_RESPONSE_MISSING"


def test_tampered_previous_response_is_rejected(
    first: dict[str, Any], south_candidates: list[dict[str, Any]]
) -> None:
    tampered = copy.deepcopy(first)
    tampered["hypotheses"][0]["rank"] = 9  # edited after sealing
    result = _rerun(tampered, south_candidates)
    assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    assert next(s for s in result["trace"] if s["step"] == "FAIL_CLOSED")["problem"] == (
        "PREVIOUS_RESPONSE_HASH_MISMATCH"
    )


def test_request_hash_must_identify_the_previous_response(
    first: dict[str, Any], south_candidates: list[dict[str, Any]]
) -> None:
    from test_blind_hypothesis import _config

    result = generate_blind_hypotheses(
        _obstacle_request(negative_evidence=south_candidates, previous_response_sha256="f" * 64),
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
        previous_response=first,
    )
    assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    assert next(s for s in result["trace"] if s["step"] == "FAIL_CLOSED")["problem"] == (
        "PREVIOUS_RESPONSE_HASH_MISMATCH"
    )


def _first_with(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _run(_obstacle_request(negative_evidence=evidence), _obstacle_room())


def test_dropping_or_reordering_old_evidence_is_not_append_only(
    south_candidates: list[dict[str, Any]],
) -> None:
    old = _negative("negev:old", _gap_times(0.0, 6.0), [])
    previous = _first_with([old])
    for evidence in ([], [south_candidates[0]], [south_candidates[0], old]):
        result = _rerun(previous, evidence)
        assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY", evidence
        assert next(s for s in result["trace"] if s["step"] == "FAIL_CLOSED")["problem"] == (
            "EVIDENCE_NOT_A_PREFIX_EXTENSION"
        )


def test_editing_an_old_entry_in_place_is_not_append_only(
    south_candidates: list[dict[str, Any]],
) -> None:
    old = _negative("negev:old", _gap_times(0.0, 6.0), [])
    previous = _first_with([old])
    edited = {**old, "sha256": "2" * 64}  # same ref, different content hash
    result = _rerun(previous, [edited, south_candidates[0]])
    assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"


def test_appending_after_old_evidence_is_accepted(south_candidates: list[dict[str, Any]]) -> None:
    old = _negative("negev:old", _gap_times(0.0, 6.0), [])
    previous = _first_with([old])
    result = _rerun(previous, [old, south_candidates[0]])
    assert result["status"] == "READY"
    assert result["negative_evidence_applied"] == [
        "negev:old",
        south_candidates[0]["negative_evidence_ref"],
    ]
    (entry,) = result["pruning_log"]
    assert entry["order"] == 2  # position in the full evidence list


def test_unknown_previous_response_cannot_be_extended(
    south_candidates: list[dict[str, Any]],
) -> None:
    unknown = _run(
        _obstacle_request(negative_evidence=_candidates([WHOLE_ROOM], [3.0])), _obstacle_room()
    )
    assert unknown["status"] == "UNKNOWN"
    result = _rerun(unknown, south_candidates)
    assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    assert next(s for s in result["trace"] if s["step"] == "FAIL_CLOSED")["problem"] == (
        "PREVIOUS_RESPONSE_NOT_READY"
    )


def _rerun_with(
    previous: dict[str, Any], request: dict[str, Any], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    from test_blind_hypothesis import _config

    request = {
        **request,
        "negative_evidence": evidence,
        "previous_response_sha256": previous["output_sha256"],
    }
    return generate_blind_hypotheses(
        request,
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
        previous_response=previous,
    )


def _problem(response: dict[str, Any]) -> str:
    return next(s for s in response["trace"] if s["step"] == "FAIL_CLOSED")["problem"]


def test_rerun_must_repeat_the_same_request(
    first: dict[str, Any], south_candidates: list[dict[str, Any]]
) -> None:
    from test_blind_hypothesis import _endpoint, _request

    moved_end = _request(_endpoint("obs:a", 0.0, (1.0, 3.0)), _endpoint("obs:b", 6.0, (9.0, 2.0)))
    longer = _request(_endpoint("obs:a", 0.0, (1.0, 3.0)), _endpoint("obs:b", 6.2, (9.0, 3.0)))
    moved_start_only = _obstacle_request()
    moved_start_only["start"]["ground_estimate"]["point_m"] = [1.0, 3.5, 0.0]
    for request in (moved_end, longer, moved_start_only):
        result = _rerun_with(first, request, south_candidates)
        assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
        assert _problem(result) == "REQUEST_CHANGED"
    # top_k and the evidence list are the only fields a re-run may change.
    assert _rerun_with(first, _obstacle_request(top_k=1), south_candidates)["status"] == "READY"


def test_rerun_requires_the_request_fingerprint_of_the_previous_response(
    first: dict[str, Any], south_candidates: list[dict[str, Any]]
) -> None:
    from amidst.blind_hypothesis.engine import _seal

    legacy = copy.deepcopy(first)
    legacy["trace"] = [s for s in legacy["trace"] if s["step"] != "REQUEST_FINGERPRINT"]
    _seal(legacy)
    result = _rerun(legacy, south_candidates)
    assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    assert _problem(result) == "PREVIOUS_REQUEST_FINGERPRINT_MISSING"


def test_entry_content_is_checked_against_its_hash(
    south_candidates: list[dict[str, Any]],
) -> None:
    old = _negative("negev:old", _gap_times(0.0, 6.0), [])
    previous = _first_with([old])

    # Old entry: same ref and claimed sha256, different footprint.
    forged = copy.deepcopy(old)
    forged["visible_floor"]["polygons"] = [SOUTH_AISLE]
    result = _rerun(previous, [forged, south_candidates[0]])
    assert result["reason"] == "NEGATIVE_EVIDENCE_INVALID" and _problem(result) == "SHA256_MISMATCH"

    # New entry: content changed after hashing.
    bad_new = copy.deepcopy(south_candidates[0])
    bad_new["visible_floor"]["polygons"] = [NORTH_AISLE]
    result = _rerun(previous, [old, bad_new])
    assert result["reason"] == "NEGATIVE_EVIDENCE_INVALID" and _problem(result) == "SHA256_MISMATCH"

    # First runs are checked too.
    assert _first_with([forged])["reason"] == "NEGATIVE_EVIDENCE_INVALID"
    unsealed = copy.deepcopy(old)
    unsealed["sha256"] = "1" * 64
    assert _first_with([unsealed])["reason"] == "NEGATIVE_EVIDENCE_INVALID"


# ---------------------------------------------------- retrieval to negative evidence


def test_no_detection_frames_become_one_entry_per_camera() -> None:
    response = _retrieval(WINDOW)
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response),
        visibility_entries=_visibility([SOUTH_AISLE]),
    )
    (entry,) = result["negative_evidence_candidates"]
    assert entry["origin"] == "RETRIEVAL_FEEDBACK" and entry["detection_result"] == "NO_DETECTION"
    assert entry["retrieval_query_id"] == "frq:mock" and entry["camera_id"] == "CAM_REAR"
    assert entry["visibility_ref"] == "visidx:CAM_REAR"
    assert [f["timestamp_s"] for f in entry["frame_refs"]] == WINDOW
    assert entry["frame_refs"][0]["frame_ref"] == "frame:CAM_REAR:2.4"
    assert entry["detection_producer"] == {"producer": "mock-perception", "version": "v2"}
    assert entry["visible_floor"] == {
        "method": "SOURCE_MESH_RAYCAST",
        "floor_z_m": FLOOR_Z,
        "polygons": [SOUTH_AISLE],
        "index_sha256": "a" * 64,
    }
    body = {k: v for k, v in entry.items() if k != "sha256"}
    assert entry["sha256"] == canonical_sha256(body)
    assert all(row["negative_evidence_eligible"] for row in result["frame_outcomes"])


def test_one_entry_per_camera_and_deterministic() -> None:
    rear, front = _retrieval(WINDOW), _retrieval(WINDOW[:3], camera="CAM_FRONT")
    response = {**rear, "results": [*rear["results"], *front["results"]]}
    evaluations = {**_evaluations(rear), **_evaluations(front)}
    visibility = {**_visibility([SOUTH_AISLE]), **_visibility([], "CAM_FRONT")}
    args = {"frame_evaluations": evaluations, "visibility_entries": visibility}
    one = negative_evidence_from_retrieval(response, **args)
    two = negative_evidence_from_retrieval(copy.deepcopy(response), **copy.deepcopy(args))
    assert one == two
    assert [e["camera_id"] for e in one["negative_evidence_candidates"]] == [
        "CAM_FRONT",
        "CAM_REAR",
    ]
    refs = [e["negative_evidence_ref"] for e in one["negative_evidence_candidates"]]
    assert len(set(refs)) == 2


def test_detection_present_frames_are_never_negative_evidence() -> None:
    response = _retrieval(WINDOW)
    evaluations = _evaluations(response)
    evaluations["frame:CAM_REAR:3.0"] = _evaluation(count=2)
    result = negative_evidence_from_retrieval(
        response, frame_evaluations=evaluations, visibility_entries=_visibility([SOUTH_AISLE])
    )
    rows = {r["frame_ref"]: r for r in result["frame_outcomes"]}
    assert rows["frame:CAM_REAR:3.0"]["outcome"] == "DETECTION_PRESENT"
    assert rows["frame:CAM_REAR:3.0"]["negative_evidence_eligible"] is False
    (entry,) = result["negative_evidence_candidates"]
    assert 3.0 not in [f["timestamp_s"] for f in entry["frame_refs"]]
    assert len(entry["frame_refs"]) == len(WINDOW) - 1

    only_detection = {k: _evaluation(count=1) for k in evaluations}
    none = negative_evidence_from_retrieval(
        response, frame_evaluations=only_detection, visibility_entries=_visibility([SOUTH_AISLE])
    )
    assert none["negative_evidence_candidates"] == []


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"frame_available": False}, "FRAME_UNAVAILABLE"),
        ({"rgb_hash_verified": False}, "RGB_HASH_NOT_VERIFIED"),
        ({"perception_evaluated": False}, "PERCEPTION_NOT_EVALUATED"),
        ({"provenance_ok": False}, "PROVENANCE_MISMATCH"),
        ({"measurement_count": None}, "MEASUREMENT_COUNT_UNKNOWN"),
        ({"measurement_count": True}, "MEASUREMENT_COUNT_UNKNOWN"),
        ({"measurement_count": -1}, "MEASUREMENT_COUNT_UNKNOWN"),
        ({"rgb_hash_verified": 1}, "RGB_HASH_NOT_VERIFIED"),  # only exactly True counts
    ],
)
def test_unverified_or_unevaluated_frames_are_unknown_not_absent(
    overrides: dict[str, Any], reason: str
) -> None:
    response = _retrieval(WINDOW)
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response, **overrides),
        visibility_entries=_visibility([SOUTH_AISLE]),
    )
    assert result["negative_evidence_candidates"] == []
    assert {r["outcome"] for r in result["frame_outcomes"]} == {"UNKNOWN"}
    assert {r["reason"] for r in result["frame_outcomes"]} == {reason}


def test_frame_without_a_perception_record_is_unknown() -> None:
    response = _retrieval(WINDOW)
    evaluations = _evaluations(response)
    del evaluations["frame:CAM_REAR:2.8"]
    result = negative_evidence_from_retrieval(
        response, frame_evaluations=evaluations, visibility_entries=_visibility([SOUTH_AISLE])
    )
    rows = {r["frame_ref"]: r for r in result["frame_outcomes"]}
    assert rows["frame:CAM_REAR:2.8"]["reason"] == "FRAME_EVALUATION_MISSING"
    (entry,) = result["negative_evidence_candidates"]
    assert len(entry["frame_refs"]) == len(WINDOW) - 1


def test_frustum_only_footprint_is_unknown() -> None:
    for frame_level in (False, True):
        response = _retrieval(WINDOW, method="FRUSTUM_ONLY")
        if frame_level:  # frames say FRUSTUM_ONLY while the camera block claims raycast
            response = _retrieval(WINDOW)
            for frame in response["results"][0]["windows"][0]["frames"]:
                frame["reason"]["footprint_method"] = "FRUSTUM_ONLY"
        result = negative_evidence_from_retrieval(
            response,
            frame_evaluations=_evaluations(response),
            visibility_entries=_visibility([SOUTH_AISLE]),
        )
        assert result["negative_evidence_candidates"] == []
        assert {r["reason"] for r in result["frame_outcomes"]} == {
            "FOOTPRINT_NOT_SOURCE_MESH_RAYCAST"
        }


def test_unresolved_or_wrong_method_visibility_entry_is_unknown() -> None:
    response = _retrieval(WINDOW)
    bad = {
        "visidx:CAM_REAR": {
            **_visibility([SOUTH_AISLE])["visidx:CAM_REAR"],
            "method": "FRUSTUM_ONLY",
        }
    }
    for visibility in ({}, bad):
        result = negative_evidence_from_retrieval(
            response, frame_evaluations=_evaluations(response), visibility_entries=visibility
        )
        assert result["negative_evidence_candidates"] == []
        assert {r["reason"] for r in result["frame_outcomes"]} == {"VISIBILITY_ENTRY_UNRESOLVED"}


def test_endpoint_frames_are_never_negative_evidence() -> None:
    times = [0.0, 0.2, 3.0, 5.8, 6.0]
    response = _retrieval(times)
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response),
        visibility_entries=_visibility([SOUTH_AISLE]),
    )
    rows = {r["timestamp_s"]: r for r in result["frame_outcomes"]}
    assert rows[0.0]["reason"] == rows[6.0]["reason"] == "OUTSIDE_OPEN_INTERVAL"
    assert (
        not rows[0.0]["negative_evidence_eligible"] and not rows[6.0]["negative_evidence_eligible"]
    )
    (entry,) = result["negative_evidence_candidates"]
    assert [f["timestamp_s"] for f in entry["frame_refs"]] == [0.2, 3.0, 5.8]


def test_substituted_original_endpoint_frame_is_detection_present() -> None:
    # D7: the interval starts at the substitute (0.0 s); the original, unusable start
    # (1.0 s) lies inside it and shows the flagged observation.
    substitution = {"endpoint": "START", "original_timestamp_s": 1.0, "substitute_timestamp_s": 0.0}
    response = _retrieval([0.6, 0.8, 1.0, 1.2, 1.4], substitutions=[substitution])
    evaluations = _evaluations(response)  # the (wrong) perception record says NO_DETECTION
    result = negative_evidence_from_retrieval(
        response, frame_evaluations=evaluations, visibility_entries=_visibility([SOUTH_AISLE])
    )
    rows = {r["timestamp_s"]: r for r in result["frame_outcomes"]}
    assert rows[1.0]["outcome"] == "DETECTION_PRESENT"
    assert rows[1.0]["reason"] == "ORIGINAL_ENDPOINT_FRAME"
    (entry,) = result["negative_evidence_candidates"]
    assert [f["timestamp_s"] for f in entry["frame_refs"]] == [0.6, 0.8, 1.2, 1.4]


def test_interval_unknown_or_not_ready_yields_nothing() -> None:
    response = _retrieval(WINDOW, interval=None)
    args = {
        "frame_evaluations": _evaluations(response),
        "visibility_entries": _visibility([SOUTH_AISLE]),
    }
    assert negative_evidence_from_retrieval(response, **args)["negative_evidence_candidates"] == []
    explicit = negative_evidence_from_retrieval(response, interval_s=(0.0, 6.0), **args)
    assert len(explicit["negative_evidence_candidates"]) == 1
    not_ready = {**_retrieval(WINDOW), "status": "UNKNOWN", "reason": "TIME_RANGE_INVALID"}
    assert negative_evidence_from_retrieval(not_ready, **args)["negative_evidence_candidates"] == []


def test_unknown_frame_ref_cannot_be_keyed() -> None:
    response = _retrieval(WINDOW)
    for frame in response["results"][0]["windows"][0]["frames"]:
        frame["frame_ref"] = "UNKNOWN"  # contract OPEN FR-Q3
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations={"UNKNOWN": _evaluation()},
        visibility_entries=_visibility([SOUTH_AISLE]),
    )
    assert result["negative_evidence_candidates"] == []
    assert {r["reason"] for r in result["frame_outcomes"]} == {"FRAME_REF_UNKNOWN"}


def test_already_applied_candidates_are_skipped(south_candidates: list[dict[str, Any]]) -> None:
    response = _retrieval(WINDOW)
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response),
        visibility_entries=_visibility([SOUTH_AISLE]),
        applied_negative_evidence_refs={south_candidates[0]["negative_evidence_ref"]},
    )
    assert result["negative_evidence_candidates"] == []
    assert result["skipped_already_applied"] == [south_candidates[0]["negative_evidence_ref"]]


# ------------------------------------------- frame-level de-duplication and rule (D21)


def _baseline_over(times: list[float], **overrides: Any) -> dict[str, Any]:
    """A BLIND_INTERVAL_BASELINE entry holding the frames a retrieval would also return."""

    fields: dict[str, Any] = {
        "camera_id": "CAM_REAR",
        "visibility_ref": "visidx:CAM_REAR",
        "frame_refs": [{"frame_ref": f"frame:CAM_REAR:{t}", "timestamp_s": t} for t in times],
        "detection_producer": {"producer": "mock-perception", "version": "v2"},
    }
    fields.update(overrides)
    return _negative("negev:baseline", times, [SOUTH_AISLE], **fields)


def _convert(applied: Any = (), **kwargs: Any) -> dict[str, Any]:
    response = _retrieval(WINDOW)
    return negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response),
        visibility_entries=kwargs.pop("visibility", _visibility([SOUTH_AISLE])),
        applied_frame_keys=applied,
        **kwargs,
    )


def test_applied_frame_keys_come_from_any_origin() -> None:
    baseline = _baseline_over(WINDOW[:2])
    assert baseline["origin"] == "BLIND_INTERVAL_BASELINE"
    expected = {
        ("CAM_REAR", f"frame:CAM_REAR:{t}", "visidx:CAM_REAR", "mock-perception", "v2")
        for t in WINDOW[:2]
    }
    request = _obstacle_request(negative_evidence=[baseline])
    assert applied_frame_keys_from_request(request) == expected
    assert applied_frame_keys_from_request([baseline]) == expected
    retrieval_entry = _candidates([SOUTH_AISLE])[0]
    assert len(applied_frame_keys_from_request([baseline, retrieval_entry])) == len(WINDOW)
    assert applied_frame_keys_from_request(_obstacle_request()) == set()
    assert (
        applied_frame_keys_from_request([None, {"frame_refs": "x"}, {"frame_refs": [1]}]) == set()
    )


def test_frames_already_applied_by_the_request_are_not_applied_again() -> None:
    applied = applied_frame_keys_from_request([_baseline_over(WINDOW[:3])])
    result = _convert(applied)
    (entry,) = result["negative_evidence_candidates"]
    assert [f["timestamp_s"] for f in entry["frame_refs"]] == WINDOW[3:]
    rows = {r["timestamp_s"]: r for r in result["frame_outcomes"]}
    for t in WINDOW[:3]:
        assert rows[t]["outcome"] == "NO_DETECTION"
        assert rows[t]["reason"] == "ALREADY_APPLIED_FRAME"
        assert rows[t]["negative_evidence_eligible"] is False
    assert all(rows[t]["negative_evidence_eligible"] for t in WINDOW[3:])

    everything = _convert(applied_frame_keys_from_request([_baseline_over(WINDOW)]))
    assert everything["negative_evidence_candidates"] == []
    assert {r["reason"] for r in everything["frame_outcomes"]} == {"ALREADY_APPLIED_FRAME"}


def test_duplicate_application_leaves_no_empty_pruning_record(first: dict[str, Any]) -> None:
    baseline = _baseline_over(WINDOW)
    previous = _first_with([baseline])
    result = _convert(applied_frame_keys_from_request([baseline]))
    assert result["negative_evidence_candidates"] == []
    rerun = _rerun(previous, [baseline, *result["negative_evidence_candidates"]])
    assert rerun["status"] == "READY" and rerun["pruning_log"] == []


def test_same_frame_from_another_producer_or_version_is_not_a_duplicate() -> None:
    for producer in (
        {"producer": "other-perception", "version": "v2"},
        {"producer": "mock-perception", "version": "v3"},
    ):
        applied = applied_frame_keys_from_request(
            [_baseline_over(WINDOW, detection_producer=producer)]
        )
        (entry,) = _convert(applied)["negative_evidence_candidates"]
        assert len(entry["frame_refs"]) == len(WINDOW)
    other_camera = applied_frame_keys_from_request([_baseline_over(WINDOW, camera_id="CAM_FRONT")])
    assert len(_convert(other_camera)["negative_evidence_candidates"][0]["frame_refs"]) == len(
        WINDOW
    )
    other_footprint = applied_frame_keys_from_request(
        [_baseline_over(WINDOW, visibility_ref="v:x")]
    )
    assert len(_convert(other_footprint)["negative_evidence_candidates"][0]["frame_refs"]) == len(
        WINDOW
    )


def test_applied_frame_keys_accept_plain_tuples_and_stay_deterministic() -> None:
    keys = [("CAM_REAR", "frame:CAM_REAR:2.4", "visidx:CAM_REAR", "mock-perception", "v2")]
    one, two = _convert(keys), _convert(list(reversed(keys)))
    assert one == two
    assert len(one["negative_evidence_candidates"][0]["frame_refs"]) == len(WINDOW) - 1


@pytest.mark.parametrize("rule", [None, "FOOT_PROBE_VISIBLE", "", 3])
def test_visibility_rule_must_be_foot_and_torso(rule: Any) -> None:
    visibility = _visibility([SOUTH_AISLE])
    entry = visibility["visidx:CAM_REAR"]
    if rule is None:
        del entry["visibility_rule"]  # an older index entry
    else:
        entry["visibility_rule"] = rule
    result = _convert(visibility=visibility)
    assert result["negative_evidence_candidates"] == []
    assert {r["outcome"] for r in result["frame_outcomes"]} == {"UNKNOWN"}
    assert {r["reason"] for r in result["frame_outcomes"]} == {"VISIBILITY_RULE_NOT_ELIGIBLE"}


def test_detection_present_is_still_reported_when_the_rule_is_missing() -> None:
    response = _retrieval(WINDOW)
    visibility = _visibility([SOUTH_AISLE])
    del visibility["visidx:CAM_REAR"]["visibility_rule"]
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response, measurement_count=1),
        visibility_entries=visibility,
    )
    assert {r["outcome"] for r in result["frame_outcomes"]} == {"DETECTION_PRESENT"}


# ----------------------------------- detector parameters (contract §6.1) and bad keys


def _mismatch_cases() -> list[Any]:
    def entry_without(key: str) -> Any:
        def mutate(entry: dict[str, Any]) -> None:
            del entry[key]

        return mutate

    def detector(**changes: Any) -> Any:
        def mutate(entry: dict[str, Any]) -> None:
            entry["detectability"]["detector"].update(changes)

        return mutate

    def drop_detector_key(key: str) -> Any:
        def mutate(entry: dict[str, Any]) -> None:
            del entry["detectability"]["detector"][key]

        return mutate

    return [
        pytest.param(entry_without("detectability"), id="no-detectability"),
        pytest.param(lambda e: e.update(detectability={}), id="no-detector"),
        pytest.param(lambda e: e.update(detectability={"detector": "x"}), id="detector-not-map"),
        pytest.param(detector(producer="other"), id="producer"),
        pytest.param(detector(version="v9"), id="version"),
        pytest.param(detector(difference_threshold=21), id="difference-threshold"),
        pytest.param(detector(min_pixels=30), id="min-pixels"),
        pytest.param(detector(difference_threshold=20.0), id="threshold-type-int-vs-float"),
        pytest.param(detector(min_pixels=True), id="min-pixels-bool"),
        pytest.param(drop_detector_key("min_pixels"), id="detector-lacks-min-pixels"),
    ]


@pytest.mark.parametrize("mutate", _mismatch_cases())
def test_detector_parameters_must_match_the_perception_run(mutate: Any) -> None:
    visibility = _visibility([SOUTH_AISLE])
    mutate(visibility["visidx:CAM_REAR"])
    result = _convert(visibility=visibility)
    assert result["negative_evidence_candidates"] == []
    assert {r["outcome"] for r in result["frame_outcomes"]} == {"UNKNOWN"}
    assert {r["reason"] for r in result["frame_outcomes"]} == {"DETECTOR_PARAMETERS_MISMATCH"}
    assert not any(r["negative_evidence_eligible"] for r in result["frame_outcomes"])


@pytest.mark.parametrize(
    "producer",
    [
        {"producer": "mock-perception", "version": "v2"},  # no thresholds recorded
        {**DETECTOR, "difference_threshold": 25},
        {**DETECTOR, "min_pixels": 40},
        {**DETECTOR, "version": "v3"},
    ],
)
def test_frame_producer_must_match_the_index_detector(producer: dict[str, Any]) -> None:
    response = _retrieval(WINDOW)
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response, detection_producer=producer),
        visibility_entries=_visibility([SOUTH_AISLE]),
    )
    assert result["negative_evidence_candidates"] == []
    assert {r["reason"] for r in result["frame_outcomes"]} == {"DETECTOR_PARAMETERS_MISMATCH"}


def test_matching_detector_is_eligible_and_entry_keeps_the_contract_producer_shape() -> None:
    (entry,) = _convert()["negative_evidence_candidates"]
    assert entry["detection_producer"] == {"producer": "mock-perception", "version": "v2"}


def test_detection_present_does_not_depend_on_detector_parameters() -> None:
    response = _retrieval(WINDOW)
    visibility = _visibility([SOUTH_AISLE])
    del visibility["visidx:CAM_REAR"]["detectability"]
    result = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response, measurement_count=1),
        visibility_entries=visibility,
    )
    assert {r["outcome"] for r in result["frame_outcomes"]} == {"DETECTION_PRESENT"}


GOOD_KEY = ("CAM_REAR", "frame:CAM_REAR:2.4", "visidx:CAM_REAR", "mock-perception", "v2")


@pytest.mark.parametrize(
    "bad",
    [
        ("CAM_REAR", "frame:CAM_REAR:2.6", "visidx:CAM_REAR", "mock-perception"),  # 4 items
        (*GOOD_KEY, "extra"),  # 6 items
        (),
        ("CAM_REAR", 2.6, "visidx:CAM_REAR", "mock-perception", "v2"),  # not strings
        "abcde",  # a string is not a key
        7,
        None,
    ],
)
def test_malformed_applied_frame_keys_do_not_crash_and_are_reported(bad: Any) -> None:
    result = _convert([bad, GOOD_KEY])
    (entry,) = result["negative_evidence_candidates"]
    assert [f["timestamp_s"] for f in entry["frame_refs"]] == WINDOW[1:]  # good key still applied
    (invalid,) = result["invalid_applied_frame_keys"]
    assert invalid["reason"] == "APPLIED_FRAME_KEY_MALFORMED"
    rows = {r["timestamp_s"]: r for r in result["frame_outcomes"]}
    assert rows[2.4]["reason"] == "ALREADY_APPLIED_FRAME"
    assert rows[2.6]["negative_evidence_eligible"] is True


def test_well_formed_applied_frame_keys_report_no_invalid_keys() -> None:
    assert _convert([GOOD_KEY])["invalid_applied_frame_keys"] == []
    assert _convert()["invalid_applied_frame_keys"] == []


# ------------------------------------------------------------- convergence summary


def test_convergence_summary_reports_area_and_pruning_per_step(
    first: dict[str, Any], pruned: dict[str, Any]
) -> None:
    summary = pruning_convergence_summary([first, pruned])
    assert summary["chain_verified"] is True
    assert summary["basis"] == "REACHABLE_REGION_AREA_NOT_PROBABILITY"
    assert [s["response_sha256"] for s in summary["steps"]] == [
        first["output_sha256"],
        pruned["output_sha256"],
    ]
    assert summary["steps"][0]["hypotheses_pruned"] == 0
    assert summary["steps"][1]["hypotheses_pruned"] == len(pruned["pruned_hypotheses"]) > 0
    assert summary["steps"][1]["pruning_log"] == pruned["pruning_log"]
    assert summary["totals"]["hypotheses_pruned"] == len(pruned["pruned_hypotheses"])
    assert summary["totals"]["negative_evidence_steps"] == 1
    assert 0 < summary["totals"]["mean_area_ratio"] < 1
    removed = {p["timestamp_s"]: p["area_removed_m2"] for p in summary["per_timestamp"]}
    assert all(removed[t] > 0 for t in WINDOW)
    assert all(v == 0 for t, v in removed.items() if t not in WINDOW)
    assert len(summary["per_timestamp"]) == len(first["reachable_regions"])


def test_convergence_summary_flags_a_broken_chain(
    first: dict[str, Any], pruned: dict[str, Any]
) -> None:
    assert pruning_convergence_summary([pruned, first])["chain_verified"] is False
    tampered = copy.deepcopy(pruned)
    tampered["pruning_log"][0]["region_area_after_m2"] = 0.0
    assert pruning_convergence_summary([first, tampered])["chain_verified"] is False
    assert pruning_convergence_summary([])["chain_verified"] is False


# ----------------------------------------------------------------------- mock fixture

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "blind_hypothesis_pruning_mock_v1.json"
GENERATOR_PATH = ROOT / "scripts" / "generate_blind_pruning_mock_fixture.py"


def _generator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "generate_blind_pruning_mock_fixture", GENERATOR_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mock_fixture_is_labelled_hash_chained_and_reproducible() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text())
    assert fixture["fixture_note"] == "MOCK, contract-shaped, not real data"
    steps = fixture["steps"]
    assert len(steps) >= 3 and steps[0]["negative_evidence"] == []
    previous_hash = None
    for step in steps:
        response = step["response"]
        assert verify_output_sha256(response)
        assert step["response_sha256"] == response["output_sha256"]
        assert step["request_previous_response_sha256"] == previous_hash
        previous_hash = response["output_sha256"]
    assert fixture["convergence"]["chain_verified"] is True
    assert fixture["convergence"] == pruning_convergence_summary([s["response"] for s in steps])
    assert any(step["response"]["pruned_hypotheses"] for step in steps)
    assert _generator().build_fixture() == fixture

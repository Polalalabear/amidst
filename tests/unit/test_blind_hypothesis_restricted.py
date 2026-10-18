"""Restricted-policy layer (D15, contract v1.1 §3.2.1) in the K1 engine.

Synthetic maps; the layer uses the row format of C7's ``load_restricted_policy`` return
value (``restricted_ref`` + ``restricted_regions`` with GeoJSON geometry). The layer
adds labels only: reachability, check results and ranking must not change.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from shapely.geometry import box, mapping
from test_blind_hypothesis import (
    DESCRIPTOR,
    _config,
    _endpoint,
    _gap_times,
    _negative,
    _obstacle_request,
    _obstacle_room,
    _request,
    _run,
)
from test_blind_hypothesis_pruning import SOUTH_AISLE, _candidates

from amidst.blind_hypothesis import (
    PolygonFloorMap,
    RestrictedLayerError,
    canonical_sha256,
    generate_blind_hypotheses,
    parse_restricted_layer,
    polygon_floor_map,
    verify_output_sha256,
)

POLICY_SHA = "ab" * 32
RESTRICTED = "RESTRICTED_POLICY"
BAD_HASH = "f" * 64


def _row(region_id: str, geometry: Any, **overrides: Any) -> dict[str, Any]:
    row = {
        "region_id": region_id,
        "tier": RESTRICTED,
        "geometry": mapping(geometry) if hasattr(geometry, "geom_type") else geometry,
        "source_annotation_ref": "synthetic:annotation",
        "source_annotation_record_sha256": "1" * 64,
        "source_annotation_file_sha256": "2" * 64,
        "confirmation_ref": f"synthetic:confirm-{region_id}",
        "decision": "D15",
        "physical_obstacle": False,
        "affects_walkability": False,
        "affects_ranking": False,
    }
    row.update(overrides)
    return row


def _layer(*rows: dict[str, Any], **ref: Any) -> dict[str, Any]:
    return {
        "restricted_ref": {
            "map_ref": "restricted-policy:" + POLICY_SHA[:24],
            "sha256": POLICY_SHA,
            "source": "USER_CONFIRMED_ANNOTATION",
            "tier": RESTRICTED,
            **ref,
        },
        "restricted_regions": list(rows),
    }


MIDDLE = "restricted:middle"
OUTSIDE = "restricted:outside-map"


def _room() -> PolygonFloorMap:
    """Room 8 x 4 m, tier SOURCE_DERIVED (like the C7 small test map)."""

    return polygon_floor_map(
        descriptor=DESCRIPTOR,
        floor_z_m=0.0,
        regions={"physical:room": [[0, 0], [8, 0], [8, 4], [0, 4]]},
        region_tiers={"physical:room": "SOURCE_DERIVED"},
    )


def _seating() -> PolygonFloorMap:
    """Walkable room A (x 0-4, ANNOTATION_ONLY) overlapping a walkable-UNKNOWN area (x 3.5-8)."""

    return polygon_floor_map(
        descriptor=DESCRIPTOR,
        floor_z_m=0.0,
        regions={"WALK_A": [[0, 0], [4, 0], [4, 4], [0, 4]]},
        unknown_regions={"AREA_SEATING": [[3.5, 0], [8, 0], [8, 4], [3.5, 4]]},
        region_tiers={"WALK_A": "ANNOTATION_ONLY"},
    )


def _crossing_request() -> dict[str, Any]:
    return _request(_endpoint("obs:a", 0.0, (1.0, 2.0)), _endpoint("obs:b", 6.0, (7.0, 2.0)))


def _west_request() -> dict[str, Any]:
    """Stays in x <= 2.5: never reaches the restricted band at x 3-5."""

    return _request(_endpoint("obs:a", 0.0, (0.5, 2.0)), _endpoint("obs:b", 2.0, (2.5, 2.0)))


def _go(
    request: dict[str, Any], floor_map: PolygonFloorMap, layer: dict[str, Any] | None, **kw: Any
) -> dict[str, Any]:
    return generate_blind_hypotheses(
        request,
        config=_config(),
        config_sha256="c" * 64,
        floor_map=floor_map,
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
        restricted_layer=layer,
        **kw,
    )


def _problem(response: dict[str, Any]) -> str | None:
    step = next(s for s in response["trace"] if s["step"] == "FAIL_CLOSED")
    return step.get("problem")


def _strip(value: Any) -> Any:
    """Drop every field that the restricted layer adds, and the hashes derived from them."""

    drop = {
        "restricted_ref",
        "restricted_area_crossed",
        "restricted_policy_sample_indices",
        "output_sha256",
    }
    if isinstance(value, dict):
        out = {k: _strip(v) for k, v in value.items() if k not in drop}
        if "tiers" in out:
            out["tiers"] = [t for t in out["tiers"] if t != RESTRICTED]
        if "area_refs" in out:
            out["area_refs"] = [r for r in out["area_refs"] if not r.startswith("restricted:")]
        return out
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


# ------------------------------------------------------- (a)-(c): labels and echo


@pytest.fixture(scope="module")
def crossing() -> dict[str, Any]:
    return _go(_crossing_request(), _room(), _layer(_row(MIDDLE, box(3, 0, 5, 4))))


def test_path_through_a_restricted_region_is_labelled(crossing: dict[str, Any]) -> None:
    assert crossing["status"] == "READY" and crossing["hypotheses"]
    for hypothesis in crossing["hypotheses"]:
        walkable = hypothesis["checks"]["walkable"]
        assert walkable["restricted_area_crossed"] is True  # (a)
        assert walkable["result"] == "PASS" and walkable["unconfirmed_area_crossed"] is False
        flagged = []
        for item in walkable["segments"]:
            assert item["walkable"] == "TRUE"  # the policy never touches walkable
            assert "physical:room" in item["area_refs"]
            assert "SOURCE_DERIVED" in item["tiers"]  # (d) physical tier is kept, not replaced
            if RESTRICTED in item["tiers"]:
                flagged.append(item)
                assert MIDDLE in item["area_refs"]
                assert item["tiers"] == sorted(["SOURCE_DERIVED", RESTRICTED])
            else:
                assert MIDDLE not in item["area_refs"] and item["tiers"] == ["SOURCE_DERIVED"]
        assert flagged and len(flagged) < len(walkable["segments"])  # (b) in segments[].tiers
        # The first link ends west of x = 3, the last starts east of x = 5.
        assert RESTRICTED not in walkable["segments"][0]["tiers"]
        assert RESTRICTED not in walkable["segments"][-1]["tiers"]


def test_layer_is_echoed_with_its_hash(crossing: dict[str, Any]) -> None:
    ref = crossing["configuration"]["restricted_ref"]  # (c)
    assert ref == {
        "map_ref": "restricted-policy:" + POLICY_SHA[:24],
        "sha256": POLICY_SHA,
        "source": "USER_CONFIRMED_ANNOTATION",
        "tier": RESTRICTED,
    }
    assert crossing["provenance"]["annotation_sha256"]["restricted"] == POLICY_SHA
    assert crossing["configuration"]["walkable_ref"]["annotation_ref"] == "synthetic:walk"
    step = next(s for s in crossing["trace"] if s["step"] == "RESTRICTED_POLICY_LAYER")
    assert step["region_ids"] == [MIDDLE] and step["effect"] == "LABELS_ONLY"
    assert step["confirmation_refs"] == [f"synthetic:confirm-{MIDDLE}"]
    assert verify_output_sha256(crossing)


def test_reachable_region_cells_in_the_restricted_region_are_flagged(
    crossing: dict[str, Any],
) -> None:
    flagged = 0
    for region in crossing["reachable_regions"]:
        indices = set(region["restricted_policy_sample_indices"])
        flagged += len(indices)
        for index, (x, _) in enumerate(region["samples"]):
            assert (index in indices) == (3.0 - 1e-9 <= x <= 5.0 + 1e-9)  # labels only
    assert flagged > 0


def test_path_that_stays_outside_is_not_labelled() -> None:
    response = _go(_west_request(), _room(), _layer(_row(MIDDLE, box(3, 0, 5, 4))))
    assert response["status"] == "READY" and response["hypotheses"]
    for hypothesis in response["hypotheses"]:
        walkable = hypothesis["checks"]["walkable"]
        assert walkable["restricted_area_crossed"] is False
        assert all(RESTRICTED not in item["tiers"] for item in walkable["segments"])
        assert all(MIDDLE not in item["area_refs"] for item in walkable["segments"])


def test_without_a_layer_the_fields_exist_but_are_empty() -> None:
    response = _go(_crossing_request(), _room(), None)
    assert response["configuration"]["restricted_ref"] is None
    assert response["provenance"]["annotation_sha256"]["restricted"] is None
    assert not any(s["step"] == "RESTRICTED_POLICY_LAYER" for s in response["trace"])
    for hypothesis in response["hypotheses"]:
        walkable = hypothesis["checks"]["walkable"]
        assert walkable["restricted_area_crossed"] is False
        assert all(RESTRICTED not in item["tiers"] for item in walkable["segments"])
    for region in response["reachable_regions"]:
        assert region["restricted_policy_sample_indices"] == []


# ------------------------------------------------------------ labels only, no effect


def test_the_layer_changes_labels_only(crossing: dict[str, Any]) -> None:
    plain = _go(_crossing_request(), _room(), None)
    assert plain["status"] == crossing["status"] == "READY"
    assert plain["output_sha256"] != crossing["output_sha256"]
    # Same hypotheses (refs, ranks, samples, scores, results), same reachable regions
    # and areas, same counters: only the restricted fields and tier/area labels differ.
    assert [h["hypothesis_ref"] for h in plain["hypotheses"]] == [
        h["hypothesis_ref"] for h in crossing["hypotheses"]
    ]
    for key in ("rejected_counts", "limits", "negative_evidence_applied", "reason"):
        assert plain[key] == crossing[key]
    assert [r["area_m2"] for r in plain["reachable_regions"]] == [
        r["area_m2"] for r in crossing["reachable_regions"]
    ]
    for a, b in zip(plain["reachable_regions"], crossing["reachable_regions"], strict=True):
        assert a["samples"] == b["samples"] and a["truncated"] == b["truncated"]
    for a, b in zip(plain["hypotheses"], crossing["hypotheses"], strict=True):
        assert a["rank"] == b["rank"] and a["plausibility"] == b["plausibility"]
        assert a["samples"] == b["samples"] and a["route_m"] == b["route_m"]
        assert a["checks"]["speed"] == b["checks"]["speed"]
        assert a["checks"]["unseen"] == b["checks"]["unseen"]
        assert a["checks"]["walkable"]["result"] == b["checks"]["walkable"]["result"]
        for sa, sb in zip(
            a["checks"]["walkable"]["segments"], b["checks"]["walkable"]["segments"], strict=True
        ):
            assert (sa["from_timestamp_s"], sa["to_timestamp_s"], sa["walkable"]) == (
                sb["from_timestamp_s"],
                sb["to_timestamp_s"],
                sb["walkable"],
            )
            assert [r for r in sb["area_refs"] if r != MIDDLE] == sa["area_refs"]
            assert [t for t in sb["tiers"] if t != RESTRICTED] == sa["tiers"]


def test_restricted_region_is_not_subtracted_even_when_it_covers_the_whole_route() -> None:
    # A restricted band that spans every route between the endpoints.
    layer = _layer(_row(MIDDLE, box(0, 0, 8, 4)))
    plain = _go(_crossing_request(), _room(), None)
    labelled = _go(_crossing_request(), _room(), layer)
    assert labelled["status"] == "READY"
    assert _strip(labelled["hypotheses"]) == _strip(plain["hypotheses"])
    assert [r["area_m2"] for r in labelled["reachable_regions"]] == [
        r["area_m2"] for r in plain["reachable_regions"]
    ]
    for region in labelled["reachable_regions"]:
        assert region["restricted_policy_sample_indices"] == list(range(len(region["samples"])))
    assert all(h["checks"]["walkable"]["restricted_area_crossed"] for h in labelled["hypotheses"])


def test_restricted_region_outside_the_physical_map_has_no_effect() -> None:
    layer = _layer(_row(OUTSIDE, box(20, 0, 21, 4)))
    plain = _go(_crossing_request(), _room(), None)
    labelled = _go(_crossing_request(), _room(), layer)
    assert labelled["status"] == "READY"  # it neither creates nor removes walkability
    assert _strip(labelled["hypotheses"]) == _strip(plain["hypotheses"])
    assert _strip(labelled["reachable_regions"]) == _strip(plain["reachable_regions"])
    assert labelled["configuration"]["restricted_ref"] is not None
    assert all(
        not h["checks"]["walkable"]["restricted_area_crossed"] for h in labelled["hypotheses"]
    )
    # An endpoint inside only a restricted region stays outside the walkable map.
    off_map = _request(_endpoint("obs:a", 0.0, (20.5, 2.0)), _endpoint("obs:b", 6.0, (7.0, 2.0)))
    assert _go(off_map, _room(), layer)["reason"] == "ENDPOINT_OUTSIDE_WALKABLE"


def test_restricted_region_touching_the_map_only_along_its_edge_is_ignored() -> None:
    layer = _layer(_row("restricted:edge", box(8, 0, 10, 4)))  # shares the line x = 8
    response = _go(_crossing_request(), _room(), layer)
    assert all(
        not h["checks"]["walkable"]["restricted_area_crossed"] for h in response["hypotheses"]
    )


# ------------------------------------------------ (e): overlap with walkable UNKNOWN


def test_restricted_region_over_a_walkable_unknown_area_keeps_both_labels() -> None:
    request = _crossing_request()
    plain = _go(request, _seating(), None)
    layer = _layer(_row(MIDDLE, box(3, 0, 6, 4)))  # straddles WALK_A and AREA_SEATING
    response = _go(request, _seating(), layer)
    assert response["status"] == "READY" and response["hypotheses"]
    for hypothesis in response["hypotheses"]:
        walkable = hypothesis["checks"]["walkable"]
        # The physical result is the one the seating area gives, with or without policy.
        assert walkable["result"] == "UNKNOWN" and walkable["unconfirmed_area_crossed"] is True
        assert walkable["restricted_area_crossed"] is True
        by_ref = [item for item in walkable["segments"] if MIDDLE in item["area_refs"]]
        assert any(
            item["walkable"] == "UNKNOWN" and {"UNKNOWN", RESTRICTED} <= set(item["tiers"])
            for item in by_ref
        )
        assert any(
            "ANNOTATION_ONLY" in item["tiers"] and RESTRICTED in item["tiers"] for item in by_ref
        )
    for a, b in zip(plain["hypotheses"], response["hypotheses"], strict=True):
        assert a["checks"]["walkable"]["result"] == b["checks"]["walkable"]["result"]
        assert [s["walkable"] for s in a["checks"]["walkable"]["segments"]] == [
            s["walkable"] for s in b["checks"]["walkable"]["segments"]
        ]


def test_restricted_region_lying_entirely_in_a_walkable_unknown_area_is_accepted() -> None:
    # Previously a tier on an UNKNOWN region was rejected (UNKNOWN regions need tier UNKNOWN).
    layer = _layer(_row(MIDDLE, box(5, 0, 7, 4)))
    response = _go(_crossing_request(), _seating(), layer)
    assert response["status"] == "READY"
    for hypothesis in response["hypotheses"]:
        walkable = hypothesis["checks"]["walkable"]
        assert walkable["result"] == "UNKNOWN"
        assert walkable["restricted_area_crossed"] is True
        for item in walkable["segments"]:
            if MIDDLE in item["area_refs"]:
                assert item["walkable"] == "UNKNOWN"
                assert item["tiers"] == sorted(["UNKNOWN", RESTRICTED])
    flagged = {
        i for r in response["reachable_regions"] for i in r["restricted_policy_sample_indices"]
    }
    unknown = {
        i for r in response["reachable_regions"] for i in r["walkable_unknown_sample_indices"]
    }
    assert flagged and unknown  # independent label sets on the same cells


def test_a_restricted_tier_on_a_walkable_map_region_is_rejected() -> None:
    with pytest.raises(Exception, match="restricted-policy layer"):
        polygon_floor_map(
            descriptor=DESCRIPTOR,
            floor_z_m=0.0,
            regions={"WALK_A": [[0, 0], [4, 0], [4, 4], [0, 4]]},
            region_tiers={"WALK_A": RESTRICTED},
        )


def test_several_regions_and_multipolygon_geometry() -> None:
    two = box(1.5, 0, 2, 4).union(box(6, 0, 6.5, 4))  # MultiPolygon
    layer = _layer(_row("restricted:b", two), _row("restricted:a", box(3, 0, 5, 4)))
    response = _go(_crossing_request(), _room(), layer)
    for hypothesis in response["hypotheses"]:
        refs = {r for s in hypothesis["checks"]["walkable"]["segments"] for r in s["area_refs"]}
        assert {"restricted:a", "restricted:b"} <= refs
    step = next(s for s in response["trace"] if s["step"] == "RESTRICTED_POLICY_LAYER")
    assert step["region_ids"] == ["restricted:a", "restricted:b"]


# --------------------------------------------------------------- fail-closed


def _invalid_cases() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    good = box(3, 0, 5, 4)
    bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]]}
    nan_geometry = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [float("nan"), 0], [1, 1], [0, 0]]],
    }
    cases: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
        ("LAYER_FORMAT", {"restricted_ref": _layer()["restricted_ref"]}, {}),
        ("REF_INVALID", _layer(_row(MIDDLE, good), sha256="xyz"), {}),
        ("REF_INVALID", _layer(_row(MIDDLE, good), sha256=POLICY_SHA.upper()), {}),
        ("REF_INVALID", _layer(_row(MIDDLE, good), source="ANNOTATION_ONLY"), {}),
        ("REF_INVALID", _layer(_row(MIDDLE, good), tier="UNKNOWN"), {}),
        ("REF_INVALID", _layer(_row(MIDDLE, good), map_ref=""), {}),
        ("REF_INVALID", _layer(_row(MIDDLE, good), extra="x"), {}),
        ("REGIONS_EMPTY", _layer(), {}),
        ("REGION_FORMAT", _layer(_row("", good)), {}),
        ("REGION_ID_DUPLICATE", _layer(_row(MIDDLE, good), _row(MIDDLE, good)), {}),
        ("TIER_INVALID", _layer(_row(MIDDLE, good, tier="SOURCE_DERIVED")), {}),
        ("CONFIRMATION_MISSING", _layer(_row(MIDDLE, good, confirmation_ref=None)), {}),
        ("CONFIRMATION_MISSING", _layer(_row(MIDDLE, good, confirmation_ref="  ")), {}),
        ("AUTHORITY_INVALID", _layer(_row(MIDDLE, good, physical_obstacle=True)), {}),
        ("AUTHORITY_INVALID", _layer(_row(MIDDLE, good, affects_walkability=True)), {}),
        ("AUTHORITY_INVALID", _layer(_row(MIDDLE, good, affects_ranking=True)), {}),
        ("AUTHORITY_INVALID", _layer(_row(MIDDLE, good, affects_ranking=None)), {}),
        ("GEOMETRY_INVALID", _layer(_row(MIDDLE, bowtie)), {}),
        (
            "GEOMETRY_INVALID",
            _layer(_row(MIDDLE, {"type": "LineString", "coordinates": [[0, 0], [1, 1]]})),
            {},
        ),
        ("GEOMETRY_INVALID", _layer(_row(MIDDLE, {"type": "Polygon", "coordinates": []})), {}),
        ("GEOMETRY_INVALID", _layer(_row(MIDDLE, None)), {}),
        ("GEOMETRY_INVALID", _layer(_row(MIDDLE, "POLYGON((0 0,1 0,1 1,0 0))")), {}),
        ("REGION_ID_COLLISION", _layer(_row("physical:room", good)), {}),
        (
            "SHA256_MISMATCH",
            _layer(_row(MIDDLE, good)),
            {"expected_restricted_sha256": BAD_HASH},
        ),
        ("GEOMETRY_INVALID", _layer(_row(MIDDLE, nan_geometry)), {}),
    ]
    return cases


@pytest.mark.parametrize(("problem", "layer", "extra"), _invalid_cases())
def test_invalid_layer_fails_closed(
    problem: str, layer: dict[str, Any], extra: dict[str, Any]
) -> None:
    response = _go(_crossing_request(), _room(), layer, **extra)
    assert response["status"] == "UNKNOWN"
    assert response["reason"] == "RESTRICTED_POLICY_INVALID"
    assert _problem(response) == problem
    assert response["hypotheses"] == [] and response["reachable_regions"] == []
    assert response["configuration"]["restricted_ref"] is None  # a bad layer is not echoed
    assert response["provenance"]["annotation_sha256"]["restricted"] is None
    assert verify_output_sha256(response)


def test_matching_expected_hash_is_accepted() -> None:
    layer = _layer(_row(MIDDLE, box(3, 0, 5, 4)))
    response = _go(_crossing_request(), _room(), layer, expected_restricted_sha256=POLICY_SHA)
    assert response["status"] == "READY"


def test_non_canonical_json_geometry_fails_closed() -> None:
    row = _row(MIDDLE, box(3, 0, 5, 4), note=float("nan"))  # extra field is not hashed
    assert _go(_crossing_request(), _room(), _layer(row))["status"] == "READY"
    row = _row(MIDDLE, box(3, 0, 5, 4), confirmation_ref="x")
    row["geometry"] = dict(row["geometry"], extra={1, 2})  # not JSON-serialisable
    response = _go(_crossing_request(), _room(), _layer(row))
    assert response["reason"] == "RESTRICTED_POLICY_INVALID"
    assert _problem(response) == "LAYER_NOT_CANONICAL_JSON"


def test_parse_restricted_layer_raises_with_a_problem_code() -> None:
    with pytest.raises(RestrictedLayerError) as caught:
        parse_restricted_layer(_layer(_row(MIDDLE, box(0, 0, 1, 1), tier="X")))
    assert caught.value.problem == "TIER_INVALID" and caught.value.detail == {"region_id": MIDDLE}
    assert parse_restricted_layer(_layer(_row(MIDDLE, box(0, 0, 1, 1)))).region_ids == [MIDDLE]


def test_missing_floor_map_still_reports_floor_map_error_first() -> None:
    response = _go(_crossing_request(), None, _layer(_row(MIDDLE, box(3, 0, 5, 4))))
    assert response["reason"] == "WALKABLE_ANNOTATION_UNAVAILABLE"


# ---------------------------------------------------------------- determinism


def test_deterministic_and_independent_of_row_order_and_input_mutation() -> None:
    rows = [_row("restricted:b", box(1.5, 0, 2, 4)), _row("restricted:a", box(3, 0, 5, 4))]
    layer = _layer(*rows)
    frozen = copy.deepcopy(layer)
    first = _go(_crossing_request(), _room(), layer)
    assert layer == frozen  # the module does not edit its input
    second = _go(_crossing_request(), _room(), layer)
    shuffled = _go(_crossing_request(), _room(), _layer(*reversed(rows)))
    assert first == second and first["output_sha256"] == second["output_sha256"]
    assert first["output_sha256"] == shuffled["output_sha256"]


def test_layer_with_a_different_hash_gives_a_different_response() -> None:
    a = _go(_crossing_request(), _room(), _layer(_row(MIDDLE, box(3, 0, 5, 4))))
    b = _go(_crossing_request(), _room(), _layer(_row(MIDDLE, box(3, 0, 5, 4)), sha256=BAD_HASH))
    assert a["output_sha256"] != b["output_sha256"]
    assert b["provenance"]["annotation_sha256"]["restricted"] == BAD_HASH


# ----------------------------------------------------------- K5: pruning re-run


def _rerun_request(previous: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return _obstacle_request(
        negative_evidence=evidence, previous_response_sha256=previous["output_sha256"]
    )


def _rerun(
    previous: dict[str, Any], evidence: list[dict[str, Any]], layer: dict[str, Any] | None
) -> dict[str, Any]:
    return generate_blind_hypotheses(
        _rerun_request(previous, evidence),
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
        previous_response=previous,
        restricted_layer=layer,
    )


def _first(layer: dict[str, Any] | None) -> dict[str, Any]:
    return generate_blind_hypotheses(
        _obstacle_request(),
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
        restricted_layer=layer,
    )


WEST_BAND = _layer(_row("restricted:west", box(2, 0, 3, 6)))  # every route from x=1 crosses it


def test_request_fingerprint_without_a_layer_is_the_plain_request_hash() -> None:
    from amidst.blind_hypothesis.pruning import _RERUN_VARIABLE_FIELDS

    request = _obstacle_request()
    step = next(s for s in _first(None)["trace"] if s["step"] == "REQUEST_FINGERPRINT")
    fixed = {k: v for k, v in request.items() if k not in _RERUN_VARIABLE_FIELDS}
    assert step["request_sha256"] == canonical_sha256(fixed)


def test_request_fingerprint_covers_the_layer() -> None:
    plain = _first(None)
    a = _first(WEST_BAND)
    other = _first(_layer(_row("restricted:west", box(2, 0, 3.5, 6))))
    other_ref = _first(_layer(_row("restricted:west", box(2, 0, 3, 6)), sha256=BAD_HASH))
    fingerprints = {
        r["output_sha256"]: next(s for s in r["trace"] if s["step"] == "REQUEST_FINGERPRINT")[
            "request_sha256"
        ]
        for r in (plain, a, other, other_ref)
    }
    assert len(set(fingerprints.values())) == 4


def test_pruning_rerun_keeps_the_layer_and_carries_the_labels() -> None:
    first = _first(WEST_BAND)
    assert first["status"] == "READY"
    assert all(h["checks"]["walkable"]["restricted_area_crossed"] for h in first["hypotheses"])
    result = _rerun(first, _candidates([SOUTH_AISLE]), WEST_BAND)
    assert result["status"] == "READY", result["reason"]
    assert result["configuration"]["restricted_ref"] == first["configuration"]["restricted_ref"]
    assert result["pruned_hypotheses"]
    for record in result["pruned_hypotheses"]:
        assert record["status"] == "PRUNED"
        assert record["checks"]["walkable"]["restricted_area_crossed"] is True
    assert all(h["checks"]["walkable"]["restricted_area_crossed"] for h in result["hypotheses"])
    assert verify_output_sha256(result)


@pytest.mark.parametrize(
    "later",
    [
        _layer(_row("restricted:west", box(2, 0, 3.5, 6))),  # same ref, other geometry
        _layer(_row("restricted:west", box(2, 0, 3, 6)), sha256=BAD_HASH),  # other pin
        None,  # layer dropped
    ],
)
def test_pruning_rerun_with_another_layer_is_not_the_same_request(
    later: dict[str, Any] | None,
) -> None:
    first = _first(WEST_BAND)
    result = _rerun(first, _candidates([SOUTH_AISLE]), later)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    assert _problem(result) == "REQUEST_CHANGED"


def test_pruning_rerun_cannot_add_a_layer_to_a_plain_response() -> None:
    first = _first(None)
    result = _rerun(first, _candidates([SOUTH_AISLE]), WEST_BAND)
    assert result["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    assert _problem(result) == "REQUEST_CHANGED"


def test_evidence_is_unaffected_by_the_layer() -> None:
    # Negative evidence prunes by visibility only; a restricted region does not prune.
    old = _negative("negev:old", _gap_times(0.0, 6.0), [])
    request = _obstacle_request(negative_evidence=[old])
    base = dict(
        config=_config(),
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
    )
    plain = generate_blind_hypotheses(request, **base)
    labelled = generate_blind_hypotheses(request, restricted_layer=WEST_BAND, **base)
    assert _strip(plain["hypotheses"]) == _strip(labelled["hypotheses"])
    assert _strip(plain["reachable_regions"]) == _strip(labelled["reachable_regions"])
    assert _run(request, _obstacle_room())["status"] == "READY"

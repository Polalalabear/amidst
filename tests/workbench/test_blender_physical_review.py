"""Substitute-only source fixtures; no GT, Blender process or physical reranking."""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any, cast

import pytest

import amidst.workbench.blender_physical_review as review
from amidst.workbench.blender_physical_source import PhysicalSourceInputs

SHA = "a" * 64
Json = dict[str, Any]


@pytest.fixture
def inputs(monkeypatch: pytest.MonkeyPatch) -> tuple[PhysicalSourceInputs, Json]:
    portals = [
        SimpleNamespace(
            surface_id=name,
            source_object_id=name,
            vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 2]],
            triangles=[[0, 1, 2]],
            source_face_indices=[],
            floor_ids=["1F"],
        )
        for names in review._PORTALS.values()
        for name in names
    ]
    support = SimpleNamespace(
        surface_id="support-original",
        source_object_id="floor",
        vertices=[[0, 0, 0.1], [1, 0, 0.2], [0, 1, 0.3]],
        triangles=[[0, 1, 2]],
        source_face_indices=[7],
    )
    source = SimpleNamespace(
        source_sha256=SHA,
        site_id="office",
        geometry_model_sha256="b" * 64,
        physical_source_sha256="c" * 64,
        evidence_hashes={"geometry_archive": "b" * 64},
        _geometry=SimpleNamespace(source_sha256=SHA, surfaces=portals),
        contract=SimpleNamespace(
            scale=SimpleNamespace(metres_per_blender_unit=0.1),
            portal_min_width_m=0.7,
            portal_min_height_m=1.8,
            parameter=lambda key: {"body_radius_m": 0.3, "body_height_m": 1.7}[key],
        ),
        support_domains={"1F": SimpleNamespace(support_surfaces=[support])},
        site_support_domains={
            site: SimpleNamespace(support_surfaces=[support]) for site in review._PORTALS
        },
        verify=lambda: None,
    )
    documents = (
        {"source_sha256": SHA, "pairs": []},
        {
            "source_sha256": SHA,
            "regions": [
                {
                    "walkable_id": "WALK_1F_OFFICE",
                    "review_witnesses": [
                        {
                            "reason": "DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE",
                            "source_object_id": "original-source",
                            "source_face_index": 42,
                            "triangle_bu": [[1, 2, 3], [2, 3, 4], [3, 4, 5]],
                        },
                        {
                            "reason": "UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN",
                            "source_object_id": "original-source",
                            "location_bu": [4, 5, 6],
                        },
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(review, "_documents", lambda _: copy.deepcopy(documents))
    result = {
        "schema_version": "workbench.blender-physical.v1",
        "source_binding": {
            "source_sha256": SHA,
            "site_id": "office",
            "run_id": "SUBSTITUTE_RUN",
            "dataset_sha256": "d" * 64,
            "clock_id": "SUBSTITUTE_CLOCK_SECONDS",
            "normalized_units": "METRES",
            "time_unit": "SECONDS",
        },
        "physical_source_sha256": "c" * 64,
        "physical_sha256": "e" * 64,
        "selection": {"camera_ids": ["A", "B"], "time_range": [0, 4]},
        "source_time_range": [0, 4],
        "search": {"complete": False},
        "candidates": [
            {
                "candidate_ref": "candidate:substitute",
                "paths": [
                    {
                        "camera_ids": ["A", "B"],
                        "samples": [
                            {
                                "timestamp": 0,
                                "camera_id": "A",
                                "state": "PROJECTED_OBSERVATION",
                                "world_position": [1, 2, 0.1],
                                "connect_from_previous": False,
                                "overlap_support": [],
                            },
                            {
                                "timestamp": 4,
                                "camera_id": "B",
                                "state": "PROJECTED_OBSERVATION",
                                "world_position": [3, 2, 0.1],
                                "connect_from_previous": False,
                                "overlap_support": [],
                            },
                        ],
                        "gaps": [
                            {
                                "time_range": [0, 4],
                                "reason": "CROSS_CAMERA_LONG_GAP",
                                "state": "MISSING",
                                "gap_ref": "gap:substitute",
                            }
                        ],
                    }
                ],
            }
        ],
        "baseline_candidate": None,
    }
    return cast(PhysicalSourceInputs, source), result


def _payload(index: review.BlenderPhysicalReviewIndex, decision: str = "CONFIRMED_LOCAL") -> Json:
    item = index.snapshot(["A", "B"], 0, 4)["items"][0]
    return {
        "review_sha256": index.review_sha256,
        "item_ref": item["item_ref"],
        "checks": [
            {
                "check_ref": item["checklist"][0]["check_ref"],
                "decision": decision,
                "evidence_refs": [item["geometry_refs"][0]],
                "comment": "只核對可見原來源邊界，其他未知。",
            }
        ],
    }


def test_annotation_and_partial_body_never_grant_aperture_or_global_authority(inputs: Any) -> None:
    source, result = inputs
    original = copy.deepcopy(result)
    index = review.BlenderPhysicalReviewIndex(source, result)
    value = index.snapshot(["A", "B"], 0, 4)
    assert result == original
    assert value["prior_results"]["status"] == "UNCHANGED_PRIOR_RESULTS"
    assert not value["prior_results"]["ranking_recomputed"]
    assert not value["prior_results"]["media_rerendered"]
    assert all(item["status"] == "UNKNOWN" for item in value["items"])
    assert {item["kind"] for item in value["items"]} == {
        "PORTAL_APERTURE",
        "CORRIDOR_CONNECTIVITY",
        "BODY_CLEARANCE",
    }
    annotation = next(
        row for row in value["geometry_primitives"] if row["kind"] == "SOURCE_ANNOTATION"
    )
    assert annotation["vertices"][-1] == [0, 0.1, 0.2]
    assert not annotation["is_aperture"] and not annotation["is_collider"]
    witness = next(row for row in value["geometry_primitives"] if row["kind"] == "SOURCE_WITNESS")
    assert witness["source_face_indices"] == [42]
    assert witness["vertices"][0] == [0.1, 0.2, 0.30000000000000004]
    support = next(row for row in value["geometry_primitives"] if row["kind"] == "SOURCE_TRIANGLES")
    assert len({point[2] for point in support["vertices"]}) == 3
    assert not value["source_authority_changed"] and not value["rerun_authorized"]


def test_narrow_camera_query_only_slices_clock_not_catalog_rank_or_source_refs(inputs: Any) -> None:
    source, result = inputs
    index = review.BlenderPhysicalReviewIndex(source, result)
    full = index.snapshot(["A", "B"], 0, 4)
    narrow = index.snapshot(["B"], 2, 4)
    assert full["review_sha256"] == narrow["review_sha256"]
    assert full["prior_results"] == narrow["prior_results"]
    assert full["geometry_primitives"] == narrow["geometry_primitives"]
    assert [row["item_ref"] for row in full["items"]] == [
        row["item_ref"] for row in narrow["items"]
    ]
    assert [row["camera_id"] for row in narrow["synchronized_evidence"]["samples"]] == ["B"]
    assert narrow["synchronized_evidence"]["missing_intervals"][0]["time_range"] == [2, 4]
    assert not narrow["synchronized_evidence"]["position_filled"]
    narrow["geometry_primitives"][0]["vertices"][0][0] = 999
    assert index.snapshot(["B"], 2, 4)["geometry_primitives"][0]["vertices"][0][0] != 999


def test_single_camera_excludes_other_support_and_cross_camera_interpolation(inputs: Any) -> None:
    source, result = inputs
    samples = result["candidates"][0]["paths"][0]["samples"]
    samples[0]["overlap_support"] = [{"camera_id": "B", "world_position": [1.1, 2, 0.1]}]
    samples.append(
        {
            "timestamp": 1,
            "state": "INFERRED_CROSS_CAMERA",
            "camera_id": None,
            "world_position": [1.5, 2, 0.1],
            "overlap_support": [],
        }
    )
    index = review.BlenderPhysicalReviewIndex(source, result)
    single = index.snapshot(["A"], 0, 4)["synchronized_evidence"]["samples"]
    assert len(single) == 1 and single[0]["overlap_support"] == []
    assert len(index.snapshot(["A", "B"], 0, 4)["synchronized_evidence"]["samples"]) == 3


def test_missing_camera_preserves_full_source_counts_and_explicit_display_missing(
    inputs: Any,
) -> None:
    source, result = inputs
    result["camera_coverage"] = [
        {
            "camera_id": "B",
            "time_range": [0, 4],
            "source_frame_count": 50,
            "projected_frame_count": 0,
        }
    ]
    result["candidates"] = []
    value = review.BlenderPhysicalReviewIndex(source, result).snapshot(["B"], 2, 4)
    row = value["camera_coverage"][0]
    assert row["count_scope"] == "UNCHANGED_FULL_SOURCE_PRIOR" and row["source_frame_count"] == 50
    assert row["display_time_range"] == [2, 4]
    assert value["synchronized_evidence"]["samples"] == []
    assert value["synchronized_evidence"]["missing_intervals"][0]["state"] == "MISSING"


def test_source_preview_truncation_explicit_and_site_support_stays_first(
    inputs: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, result = inputs
    surface = source.support_domains["1F"].support_surfaces[0]
    surface.triangles *= 2
    monkeypatch.setattr(review, "MAX_PREVIEW_TRIANGLES", 1)
    value = review.BlenderPhysicalReviewIndex(source, result).snapshot(["A"], 0, 4)
    assert value["geometry_coverage"]["preview_truncated"]
    preview = next(row for row in value["geometry_primitives"] if row["kind"] == "SOURCE_TRIANGLES")
    assert preview["label"] == "此 site 登錄原支持面"
    assert preview["omitted_triangle_count"] == 1 and preview["truncated"]


@pytest.mark.parametrize("site", ["classroom101", "auditorium"])
def test_other_site_has_explicit_missing_body_source_not_office_witness(
    inputs: Any, site: str
) -> None:
    source, result = inputs
    source.site_id = site
    result["source_binding"]["site_id"] = site
    value = review.BlenderPhysicalReviewIndex(source, result).snapshot(["A", "B"], 0, 4)
    body = next(item for item in value["items"] if item["kind"] == "BODY_CLEARANCE")
    assert "SITE_BODY_REGION_NOT_EXPORTED" in {row["code"] for row in body["pending_gaps"]}
    assert not any(row["kind"] == "SOURCE_WITNESS" for row in value["geometry_primitives"])


def test_partial_local_decision_is_diff_only_remaining_unknown_without_rerun(inputs: Any) -> None:
    index = review.BlenderPhysicalReviewIndex(*inputs)
    value = review.validate_review_decision(index, _payload(index))
    assert value["status"] == "LOCALLY_REVIEWED"
    assert len(value["remaining_check_refs"]) == 3
    assert value["checks"][0]["previous_decision"] == "UNKNOWN"
    assert not value["formal_approval"] and not value["rerun_authorized"]
    assert all(item["review_status"] == "PENDING" for item in index.snapshot(["A"], 0, 4)["items"])
    unknown = review.validate_review_decision(index, _payload(index, "UNKNOWN"))
    assert unknown["status"] == "UNKNOWN"
    assert len(unknown["remaining_check_refs"]) == 4


@pytest.mark.parametrize(
    "patch",
    [
        {"review_sha256": "0" * 64},
        {"item_ref": "review-item:other"},
        {"formal_approval": True},
    ],
)
def test_decision_binding_other_item_and_authority_escalation_denied(
    inputs: Any, patch: Json
) -> None:
    index = review.BlenderPhysicalReviewIndex(*inputs)
    payload = _payload(index)
    payload.update(patch)
    with pytest.raises(ValueError):
        review.validate_review_decision(index, payload)


@pytest.mark.parametrize(
    "patch",
    [
        {"decision": "APPROVED"},
        {"evidence_refs": []},
        {"comment": " "},
        {"evidence_refs": ["evidence:foreign"]},
        {"ground_truth": [1, 2, 3]},
        {"comment": "/private/tmp/source"},
        {"comment": "x" * 2001},
    ],
)
def test_confirmed_check_requires_valid_evidence_and_comment(inputs: Any, patch: Json) -> None:
    index = review.BlenderPhysicalReviewIndex(*inputs)
    payload = _payload(index)
    payload["checks"][0].update(patch)
    with pytest.raises(ValueError):
        review.validate_review_decision(index, payload)


@pytest.mark.parametrize(
    "cameras,lo,hi",
    [
        (["OTHER"], 0, 4),
        (["A", "A"], 0, 4),
        ([], 0, 4),
        (["A"], -1, 4),
        (["A"], 3, 2),
        (["A"], 0, float("nan")),
        (["A"], True, 4),
    ],
)
def test_query_scope_numeric_and_camera_guards(inputs: Any, cameras: Any, lo: Any, hi: Any) -> None:
    index = review.BlenderPhysicalReviewIndex(*inputs)
    with pytest.raises(ValueError):
        index.snapshot(cameras, lo, hi)


def test_source_stale_and_cross_site_binding_fail_closed(inputs: Any) -> None:
    source, result = inputs
    index = review.BlenderPhysicalReviewIndex(source, result)
    result["source_binding"]["site_id"] = "auditorium"
    with pytest.raises(ValueError, match="SOURCE_BINDING"):
        review.BlenderPhysicalReviewIndex(source, result)
    source.verify = lambda: (_ for _ in ()).throw(ValueError("PHYSICAL_SOURCE_STALE"))
    with pytest.raises(ValueError, match="STALE"):
        index.snapshot(["A"], 0, 4)


def test_empty_motion_keeps_review_and_missing_world_unknown(inputs: Any) -> None:
    source, result = inputs
    result["candidates"] = []
    result["baseline_candidate"] = {"candidate_ref": "candidate:empty", "paths": []}
    value = review.BlenderPhysicalReviewIndex(source, result).snapshot(["B"], 0, 4)
    assert value["status"] == "UNKNOWN"
    assert value["synchronized_evidence"]["samples"] == []
    assert not value["synchronized_evidence"]["position_filled"]


def test_budget_truncation_explicit_and_never_evidence_completeness(
    inputs: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(review, "MAX_PRIMITIVES", 1)
    value = review.BlenderPhysicalReviewIndex(*inputs).snapshot(["A"], 0, 4)
    assert len(value["geometry_primitives"]) == 1
    assert value["geometry_coverage"]["preview_truncated"]
    assert value["geometry_coverage"]["omitted_primitive_count"] > 0
    assert all(row["status"] == "UNKNOWN" for row in value["items"])


@pytest.mark.parametrize(
    "key,value",
    [
        ("ground_truth", [1, 2, 3]),
        ("local_path", "/Users/a"),
        ("trajectory", [1]),
        ("token", "secret"),
    ],
)
def test_prior_poison_fields_denied(inputs: Any, key: str, value: Any) -> None:
    source, result = inputs
    result["candidates"][0]["paths"][0][key] = value
    with pytest.raises(ValueError, match="UNSAFE"):
        review.BlenderPhysicalReviewIndex(source, result)

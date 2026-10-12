"""Independent floor-only hypotheses: provenance, physical guards and ambiguity."""
from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from amidst.engineering.registry import content_hash, opaque_ref
from amidst.workbench.blender_association import BaselineAssociationIndex

Json = dict[str, Any]


def fixture(
    specs: list[tuple[str, str, dict[float, list[float] | None]]], *,
    clocks: dict[str, list[float]] | None = None, site: str = "site-one",
) -> Json:
    """Explicit SUBSTITUTE input; no original renderer metadata or truth."""
    clocks = clocks or {cam: sorted({t for c, _, p in specs if c == cam for t in p})
                        for cam, _, _ in specs}
    frames, measurements, projections, tracks = [], [], [], []
    frame_at = {}
    for camera, times in clocks.items():
        for timestamp in times:
            ref = opaque_ref("frame", site, camera, str(timestamp))
            frame_at[camera, timestamp] = ref
            frames.append({"frame_ref": ref, "camera_id": camera, "timestamp": timestamp,
                           "source_image_sha256": "6" * 64})
    for camera, label, points in specs:
        track_ref = opaque_ref("track", site, camera, label)
        refs = []
        for timestamp, position in sorted(points.items()):
            ref = opaque_ref("observation", site, camera, label, str(timestamp))
            refs.append(ref)
            frame_ref = frame_at[camera, timestamp]
            measurements.append({
                "observation_ref": ref, "track_ref": track_ref, "frame_ref": frame_ref,
                "camera_id": camera, "timestamp": timestamp, "bbox_xyxy": [8, 10, 16, 34],
                "contact_pixel": [11.5, 33], "uncertainty": .25,
                "measurement_status": "DETECTED", "source_image_sha256": "6" * 64,
                "measurement_basis": "RGB_PIXELS",
            })
            projections.append({
                "observation_ref": ref, "frame_ref": frame_ref, "camera_id": camera,
                "timestamp": timestamp,
                "projection_status": "PROJECTED" if position is not None else "PROJECTION_MISSING",
                "projection_reason": None if position is not None else "FAR_CLIPPED",
                "world_position": position, "projection_quality": .8 if position else None,
                "geometry_authority": "SOURCE_BOUND_FLOOR_INTERSECTION_ONLY",
            })
        if refs:
            first, last = min(points), max(points)
            missing = [t for t in clocks[camera] if first < t < last and t not in points]
            tracks.append({"track_ref": track_ref, "camera_id": camera,
                           "observation_refs": refs, "timestamps": sorted(points),
                           "missing_timestamps": missing,
                           "status": "FRAGMENTED" if missing else "COMPLETE",
                           "termination_reason": "SEQUENCE_END",
                           "authority": "CAMERA_LOCAL_PIXEL_COMPONENT_TRACK"})
    digest = content_hash([frames, measurements, projections, tracks])
    return {
        "schema_version": "workbench.frame-baseline-index.v1",
        "source_binding": {"source_sha256": "1" * 64, "dataset_sha256": content_hash(site),
                           "site_id": site, "run_id": "association-fixture-v1",
                           "clock_id": "seconds", "scale_sha256": "2" * 64},
        "source_features": digest, "feature_sha256": digest,
        "calibration_sha256": "3" * 64, "producer_sha256": "4" * 64,
        "floor_plane": {"point": [0, 0, 0], "normal": [0, 0, 1], "floor_id": "1F",
                        "source_sha256": "1" * 64, "authority": "APPROVED"},
        "frames": frames, "measurements": measurements, "projected_measurements": projections,
        "local_tracks": tracks,
    }


def reconstruct(snapshot: Json, top_k: int = 3) -> Json:
    index = BaselineAssociationIndex(snapshot)
    cameras = sorted({row["camera_id"] for row in snapshot["frames"]})
    times = [row["timestamp"] for row in snapshot["frames"]]
    return index.reconstruct(cameras, min(times), max(times), top_k)


def gap_input(right_start: float = .6, right_x: float = .6) -> Json:
    return fixture([("A", "first", {0: [0, 0, 0], .2: [.2, 0, 0]}),
                    ("B", "second", {right_start: [right_x, 0, 0],
                                       right_start + .2: [right_x + .2, 0, 0]})])


def test_short_bridge_is_inferred_with_two_sources_and_baseline_is_distinct() -> None:
    result = reconstruct(gap_input(), 5)
    assert result["status"] == "READY" and len(result["candidates"]) == 2
    linked, baseline = result["candidates"]
    assert linked["score"] > baseline["score"] == 0
    assert baseline["is_unassociated_baseline"] and not baseline["selected_edge_refs"]
    path = linked["paths"][0]
    bridge = [row for row in path["samples"] if row["state"] == "INFERRED_CROSS_CAMERA"]
    assert len(bridge) == 1 and bridge[0]["world_position"] == pytest.approx([.4, 0, 0])
    assert bridge[0]["pixel_observed"] is False and bridge[0]["camera_id"] is None
    assert len(bridge[0]["source_observation_refs"]) == 2
    assert all(row["speed_m_s"] == pytest.approx(1) for row in path["velocities"])
    assert len(result["baseline_candidate"]["paths"]) == 2
    assert result["search"]["complete"] is True
    assert result["search"]["returned_top_k"] == 2
    assert result["policy"]["collision_checked"] is False
    assert result["policy"]["score_authority"] == "CONFIGURED_COMPATIBILITY_NOT_PROBABILITY"


def test_long_cross_gap_is_a_missing_association_not_a_position_curve() -> None:
    result = reconstruct(gap_input(2, 2))
    edge = result["graph"]["edges"][0]
    assert edge["bridge_missing"] is True
    assert edge["from_world_position"] == [.2, 0, 0]
    assert edge["to_world_position"] == [2, 0, 0]
    assert edge["missing_reason"] == "CROSS_CAMERA_LONG_GAP"
    path = result["candidates"][0]["paths"][0]
    middle = [row for row in path["samples"] if .2 < row["timestamp"] < 2]
    assert len(middle) == 1 and middle[0]["world_position"] is None
    assert middle[0]["state"] == "MISSING"
    assert path["gaps"][0]["time_range"] == [.2, 2]
    assert not any(row["time_range"][0] < 2 and row["time_range"][1] > .2
                   for row in path["velocities"])


def test_impossible_handoff_speed_is_rejected() -> None:
    result = reconstruct(gap_input(.4, 10))
    assert result["status"] == "NO_CROSS_CAMERA_EVIDENCE"
    assert len(result["candidates"]) == 1
    assert result["graph"]["rejected_edges"][0]["reason"] == "SPEED_CAP"


@pytest.mark.parametrize("contained", [False, True])
def test_simultaneous_or_contained_camera_evidence_is_a_real_association(contained: bool) -> None:
    a = {0: [0, 0, 0], .2: [.2, 0, 0], .4: [.4, 0, 0]}
    b = {.2: [.2, 0, 0]} if contained else copy.deepcopy(a)
    result = reconstruct(fixture([("A", "a", a), ("B", "b", b)]), 5)
    assert result["status"] == "READY" and len(result["candidates"]) == 2
    edge = result["graph"]["edges"][0]
    assert edge["kind"] in {"CROSS_CAMERA_OVERLAP", "CROSS_CAMERA_CORROBORATING_OVERLAP"}
    assert edge["overlap_support"]
    path = result["candidates"][0]["paths"][0]
    assert path["canonical_time_range"] == [0, .4]
    assert [row["timestamp"] for row in path["samples"]] == [0, .2, .4]
    assert any(row["overlap_support"] for row in path["samples"])
    assert all(row["identity_verdict"] == "UNCONFIRMED" for row in result["candidates"])


def test_compatible_overlap_preserves_both_original_positions_without_averaging() -> None:
    result = reconstruct(fixture([
        ("A", "a", {0: [0, 0, 0], .2: [.2, 0, 0], .4: [.4, 0, 0]}),
        ("B", "b", {.2: [.2, .2, 0], .4: [.4, .2, 0], .6: [.6, .2, 0]}),
    ]))
    path = result["candidates"][0]["paths"][0]
    sample = next(row for row in path["samples"] if row["timestamp"] == .2)
    assert sample["world_position"] == [.2, 0, 0]
    assert sample["overlap_support"][0]["world_position"] == [.2, .2, 0]
    assert all(row["world_position"][1] in {0, .2} for row in path["samples"])
    assert all(row["speed_m_s"] <= 8 for row in path["velocities"])


def test_overlapping_camera_conflict_does_not_match_near_arbitrary_endpoints() -> None:
    result = reconstruct(fixture([
        ("A", "a", {0: [0, 0, 0], .2: [.2, 0, 0], .4: [.4, 0, 0]}),
        ("B", "b", {.2: [1.2, 0, 0], .4: [.4, 0, 0], .6: [.6, 0, 0]}),
    ]))
    assert result["status"] == "NO_CROSS_CAMERA_EVIDENCE"
    assert result["graph"]["rejected_edges"][0]["reason"] == "OVERLAP_POSITION_CONFLICT"


def test_overlap_without_common_source_clock_samples_is_rejected() -> None:
    result = reconstruct(fixture([
        ("A", "a", {0: [0, 0, 0], .4: [.4, 0, 0]}),
        ("B", "b", {.2: [.2, 0, 0], .6: [.6, 0, 0]}),
    ]))
    assert result["graph"]["rejected_edges"][0]["reason"] == "NO_COMMON_SOURCE_CLOCK_SAMPLE"
    assert result["status"] == "NO_CROSS_CAMERA_EVIDENCE"


def test_one_to_one_assignment_retains_distinct_competing_matches() -> None:
    result = reconstruct(fixture([
        ("A", "a1", {0: [0, 0, 0], .2: [.2, 0, 0]}),
        ("A", "a2", {0: [0, .1, 0], .2: [.2, .1, 0]}),
        ("B", "b", {.6: [.6, 0, 0], .8: [.8, 0, 0]}),
    ]), 5)
    assert len(result["candidates"]) == 3
    assert [len(c["selected_edge_refs"]) for c in result["candidates"]] == [1, 1, 0]
    assert len({c["candidate_ref"] for c in result["candidates"]}) == 3


def test_pairwise_legal_edges_cannot_create_nonadjacent_overlap_conflict() -> None:
    # A/B and B/C are each within .75 m, but simultaneous A/C are 1.2 m apart.
    result = reconstruct(fixture([
        ("A", "a", {0: [0, 0, 0], .2: [.2, 0, 0], .4: [.4, 0, 0]}),
        ("B", "b", {0: [0, .6, 0], .2: [.2, .6, 0], .4: [.4, .6, 0],
                       .6: [.6, .6, 0]}),
        ("C", "c", {0: [0, 1.2, 0], .2: [.2, 1.2, 0], .4: [.4, 1.2, 0],
                       .6: [.6, 1.2, 0], .8: [.8, 1.2, 0]}),
    ]), 5)
    assert len(result["graph"]["edges"]) == 2
    assert all(len(c["selected_edge_refs"]) <= 1 for c in result["candidates"])
    assert len(result["candidates"]) == 3


def test_indirect_cross_camera_path_does_not_repair_a_local_speed_cap_gap() -> None:
    result = reconstruct(fixture([
        ("A", "broken", {0: [0, 0, 0], .2: [2, 0, 0]}),
        ("B", "b", {.1: [.5, 0, 0]}),
    ]), 5)
    assert result["summary"]["local_motion"]["gap_intervals"] == 1
    assert all(len(c["selected_edge_refs"]) <= 1 for c in result["candidates"])
    assert all(len(p["node_refs"]) <= 2 for c in result["candidates"] for p in c["paths"])


def test_narrow_windows_preserve_canonical_candidate_path_node_edge_refs() -> None:
    index = BaselineAssociationIndex(gap_input())
    full = index.reconstruct(["A", "B"], 0, .8)
    narrow = index.reconstruct(["B", "A"], .4, .8)
    assert full["association_sha256"] == narrow["association_sha256"]
    for a, b in zip(full["candidates"], narrow["candidates"], strict=True):
        assert a["candidate_ref"] == b["candidate_ref"]
        assert a["selected_edge_refs"] == b["selected_edge_refs"]
        for path in b["paths"]:
            matching = next(p for p in a["paths"] if p["path_ref"] == path["path_ref"])
            assert matching["node_refs"] == path["node_refs"]
            assert matching["canonical_time_range"] == path["canonical_time_range"]
            assert all(.4 <= p["timestamp"] <= .8 for p in path["samples"])
            if path["samples"]:
                assert path["samples"][0]["connect_from_previous"] is False
    single = index.reconstruct(["A"], 0, .8)
    assert {n["node_ref"] for n in single["graph"]["nodes"]} <= {
        n["node_ref"] for n in full["graph"]["nodes"]}
    assert single["status"] == "NO_CROSS_CAMERA_EVIDENCE"
    assert index.reconstruct(["A", "B"], 0, .8) == full


def test_absent_measurements_camera_coverage_and_no_result_are_explicit() -> None:
    data = fixture([("A", "a", {0: [0, 0, 0], .2: [.2, 0, 0]})],
                   clocks={"A": [0, .2], "B": [0, .2]})
    index = BaselineAssociationIndex(data)
    result = index.reconstruct(["A", "B"], 0, .2)
    assert result["status"] == "NO_CROSS_CAMERA_EVIDENCE" and len(result["candidates"]) == 1
    assert result["camera_coverage"][1]["state"] == "MISSING"
    empty = index.reconstruct(["B"], 0, .2)
    assert empty["status"] == "NO_RESULT" and empty["candidates"] == []
    assert index.reconstruct(["A", "B"], 2, 3)["status"] == "NO_RESULT"


def test_gt_poison_and_private_locators_do_not_enter_hash_rank_or_output() -> None:
    source = gap_input()
    baseline = reconstruct(source)
    poison = copy.deepcopy(source)
    poison["ground_truth"] = {"identity": "secret", "path": "/private/test.blend"}
    poison["actor_trajectory"] = [{"speed": 999}]
    for measurement in poison["measurements"]:
        measurement["truth_identity"] = "secret"
    result = reconstruct(poison)
    assert result == baseline
    assert "secret" not in json.dumps(result)
    assert result["agent_used"] is False and result["formal_acceptance"] is False
    json.dumps(result, allow_nan=False)


def test_source_scope_changes_all_canonical_identity_refs_without_cross_site_matching() -> None:
    a = gap_input()
    b = copy.deepcopy(a)
    b["source_binding"]["site_id"] = "another-site"
    b["source_binding"]["run_id"] = "another-run"
    ra, rb = reconstruct(a), reconstruct(b)
    assert ra["association_sha256"] != rb["association_sha256"]
    assert {n["node_ref"] for n in ra["graph"]["nodes"]}.isdisjoint(
        n["node_ref"] for n in rb["graph"]["nodes"])
    assert ra["candidates"][0]["candidate_ref"] != rb["candidates"][0]["candidate_ref"]


@pytest.mark.parametrize("top_k", [0, 6, True, 1.5, "3"])
def test_invalid_top_k_is_denied(top_k: Any) -> None:
    index = BaselineAssociationIndex(gap_input())
    with pytest.raises(ValueError, match="ASSOCIATION_TOP_K_BUDGET"):
        index.reconstruct(["A", "B"], 0, .8, top_k)


@pytest.mark.parametrize("camera_ids,start,end", [
    (["MISSING"], 0, .8), (["A", "A"], 0, .8), ([], 0, .8),
    (["A"], float("nan"), .8), (["A"], 0, float("inf")),
    (["A"], 0, 10.1), (["A"], .8, 0), (["A"], True, .8),
])
def test_camera_time_budget_and_nonfinite_values_are_denied(camera_ids, start, end) -> None:
    index = BaselineAssociationIndex(gap_input())
    with pytest.raises(ValueError):
        index.reconstruct(camera_ids, start, end)


def test_nonfinite_geometry_and_floor_mismatch_fail_closed() -> None:
    data = gap_input()
    data["projected_measurements"][0]["world_position"][0] = float("nan")
    with pytest.raises(ValueError):
        BaselineAssociationIndex(data)
    data = gap_input()
    data["floor_plane"]["source_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="MOTION_FLOOR_SOURCE_MISMATCH"):
        BaselineAssociationIndex(data)


def test_exact_cross_camera_speed_cap_is_inclusive_despite_float_interpolation() -> None:
    result = reconstruct(fixture([("A", "a", {0: [0, 0, 0]}),
                                  ("B", "b", {1: [8, 0, 0]})]))
    assert result["status"] == "READY"
    path = result["candidates"][0]["paths"][0]
    assert len(path["samples"]) == 6
    assert all(v["speed_m_s"] == pytest.approx(8) for v in path["velocities"])


def test_graph_node_budget_rejects_excess_fragmentation() -> None:
    points = {i / 10: [float(i * 2), 0, 0] for i in range(65)}
    with pytest.raises(ValueError, match="ASSOCIATION_GRAPH_NODE_BUDGET"):
        BaselineAssociationIndex(fixture([("A", "fragmented", points)]))


def test_graph_edge_budget_rejects_unbounded_candidate_pairs() -> None:
    specs = [(f"C{i % 4}", f"track{i}", {i / 10: [0, 0, 0]}) for i in range(32)]
    with pytest.raises(ValueError, match="ASSOCIATION_GRAPH_EDGE_BUDGET"):
        BaselineAssociationIndex(fixture(specs))


def test_beam_truncation_is_explicit_and_never_claims_global_optimality() -> None:
    specs = [("A", f"a{i}", {0: [i / 100, 0, 0]}) for i in range(5)]
    specs += [("B", f"b{i}", {.5: [i / 100, 0, 0]}) for i in range(5)]
    result = reconstruct(fixture(specs), 5)
    assert result["search"]["truncated"] is True
    assert result["search"]["complete"] is False
    assert result["search"]["score_optimality"] == "BOUNDED_BEAM_NOT_GLOBALLY_CERTIFIED"
    assert len(result["candidates"]) == 5
    assert len({c["candidate_ref"] for c in result["candidates"]}) == 5
    assert result["baseline_candidate"]["is_unassociated_baseline"]


def test_legal_pair_support_but_unsafe_active_timeline_is_rejected_without_import_failure() -> None:
    # Only .4 is shared; B's early point would require 9 m/s when selected at .2.
    result = reconstruct(fixture([
        ("A", "a", {0: [0, 0, 0], .4: [.4, 0, 0]}),
        ("B", "b", {.2: [1.8, 0, 0], .4: [1.1, 0, 0], .6: [1.3, 0, 0]}),
    ]))
    assert result["status"] == "NO_CROSS_CAMERA_EVIDENCE"
    assert result["search"]["prefix_route_guard_rejections"] == 1
    assert result["search"]["complete"] is False
    assert result["search"]["score_optimality"] == "PREFIX_GUARDED_NOT_GLOBALLY_CERTIFIED"
    assert result["association_result_reason"] == "NO_FEASIBLE_PREFIX_GUARDED_ROUTE"
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["is_unassociated_baseline"]

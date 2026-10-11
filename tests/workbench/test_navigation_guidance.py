"""Label navigation uses registered links and finite indexed evidence, never truth."""

from __future__ import annotations

import json
from collections import UserDict
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_scenes import fixture_scene

from amidst.engineering.local_index import CameraLink, CameraRegions, ScopedTopology
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.registry import opaque_ref, scope_parts
from amidst.workbench.navigation_guidance import (
    MAX_AGENT_INPUT_BYTES,
    MAX_CAMERAS,
    MAX_CANDIDATES,
    MAX_EDGES,
    MAX_HOPS,
    MAX_NODES,
    AgentInput,
    GuidanceIndex,
    mock_decide,
)
from amidst.workbench.scenes import SceneAdapter


class NoScan(UserDict[str, Any]):
    """Direct lookups work; any query-time dictionary/catalog iteration fails."""

    def __iter__(self):
        raise AssertionError("query scanned a catalog")

    def values(self):
        raise AssertionError("query scanned a catalog")

    def items(self):
        raise AssertionError("query scanned a catalog")


def linked_scene(tmp_path: Path, *, count: int = 4, candidate_count: int = 3,
                 dense: bool = False, complete_links: bool = False) -> SceneAdapter:
    scene = fixture_scene(tmp_path)
    base = scene.service
    scope = base.scope
    original = next(iter(base.cameras.values()))
    cameras = tuple(original.model_copy(update={
        "camera_id": f"C{i}",
        "camera_ref": opaque_ref("camera", *scope_parts(scope), f"C{i}"),
    }) for i in range(count))
    # The service registry is immutable; construct a matching replacement import.
    registry = base.store.registry.model_copy(update={"cameras": cameras})
    frames = tuple(frame.model_copy(update={
        "camera_id": "C0", "camera_ref": cameras[0].camera_ref,
    }) for frame in base.frames.values())
    registry = registry.model_copy(update={"frames": frames})
    base.store.registry = registry
    binding = base.guard.binding.model_copy(update={"registry_sha256": registry.sha256})
    from amidst.engineering.access import FreezeReceipt, SessionGuard

    guard = SessionGuard(binding)
    guard.freeze(FreezeReceipt.create(binding, {}, {}), {}, {})
    events = tuple({
        "event_ref": opaque_ref("event", str(i)), "camera_refs": [camera.camera_ref],
        "camera_ids": [camera.camera_id], "time_range": [0.0, 1.0], "region_ids": ["r"],
        "media_refs": [], "candidates": [{"candidate_id": f"order-{j}"}
                                         for j in range(candidate_count)],
        "trajectories": [{}], "complete": False, "termination_reason": "MAX_PATHS_REACHED",
        "kind": "INFERRED_GAP_ALTERNATIVES", "evidence_state": "INFERRED_GAP",
        "support_state": "GAP_ALTERNATIVES",
        "actor_identity": "MUST_NOT_LEAK", "ground_truth": "MUST_NOT_LEAK",
        "uncertainty": "/private/secret/source.blend", "feature_vector": [1, 2, 3],
    } for i, camera in enumerate(cameras))
    pairs = [(0, i) for i in range(1, count)] if dense else [
        (i, i + 1) for i in range(count - 1)]
    if complete_links:
        pairs = [(a, b) for a in range(count) for b in range(count) if a != b]
    topology = ScopedTopology(
        scope=scope, camera_ids=tuple(c.camera_id for c in cameras), topology_complete=False,
        camera_links=tuple(CameraLink(from_camera_id=f"C{a}", to_camera_id=f"C{b}")
                           for a, b in pairs),
        camera_regions=(CameraRegions(camera_id="C0", region_ids=("r",)),))
    service = LocalPilotService(base.store, scope, guard, (), events, topology)
    scene.service = service
    scene._cameras = {c.camera_id: c for c in cameras}
    # Rebuild public snapshot camera identity without inference or source rendering.
    scene._snapshot["cameras"] = [
        {"camera_id": c.camera_id, "label": c.camera_id} for c in cameras]
    return scene


def test_dataset_presets_and_user_behavior_never_imply_a_classification(tmp_path: Path) -> None:
    index = GuidanceIndex(linked_scene(tmp_path))
    presets = index.presets()
    assert presets["time_range"] == [0.0, 100.0]
    assert presets["place_id"] == "lab"
    assert presets["behaviors"] == [
        {"value": "walking", "label": "行走"},
        {"value": "running", "label": "跑步"},
        {"value": "enter_exit", "label": "出入"},
    ]
    response = index.guide("navigation", "C0", 0, 1, "running", 4)
    assert response["agent_input"]["selection"]["behavior_authority"] == "USER_SELECTED_INTENT"
    assert response["agent_output"]["behavior_verdict"] == "UNKNOWN"
    assert response["agent_output"]["confirmed_identity"] is None
    assert response["agent_output"]["provider"] == "LOCAL_MOCK"


def test_bfs_index_queries_are_deterministic_and_do_not_scan_at_request_time(
    tmp_path: Path,
) -> None:
    scene = linked_scene(tmp_path, count=6)
    index = GuidanceIndex(scene)
    # SceneAdapter.query delegates to the interval index and direct dictionaries.
    scene.service.events = NoScan(scene.service.events)
    scene.service.observations = NoScan(scene.service.observations)
    scene.service.frames = NoScan(scene.service.frames)
    result = index.guide("導航", "C0", 0, 1, top_k=4)
    assert result == index.guide("navigation", "C0", 0, 1, top_k=4)
    data = result["agent_input"]
    assert [n["resource_id"] for n in data["navigation_nodes"]
            if n["kind"] == "CAMERA"] == ["C0", "C1", "C2", "C3"]
    telemetry = data["telemetry"]
    assert telemetry["global_scan"] is False and telemetry["import_built_index"] is True
    assert telemetry["camera_queries"] == 4 and telemetry["records_read"] == 4
    assert telemetry["frames_read"] == telemetry["bytes_read"] == 0
    assert "HOP_BUDGET" in telemetry["truncation_reasons"]
    assert telemetry["graph_search_complete"] is None
    assert telemetry["scoped_inventory_complete"] is False
    assert MAX_HOPS == 3


def test_unknown_ambiguous_and_unreachable_labels_have_no_evidence_reads(tmp_path: Path) -> None:
    scene = linked_scene(tmp_path)
    scene._snapshot["cameras"][1]["label"] = "C0"
    index = GuidanceIndex(scene)
    for label, camera, reason in (
        ("find everyone /private/secret", "C0", "UNKNOWN_LABEL"),
        ("C0", "C0", "AMBIGUOUS_LABEL"),
        ("camera:C0", "C3", "LABEL_OUTSIDE_BOUNDED_GRAPH"),
    ):
        result = index.guide(label, camera, 0, 1)
        assert result["status"] == "NEEDS_INPUT"
        assert result["agent_output"]["decision"] == "NEEDS_INPUT"
        assert result["agent_output"]["selected_refs"] == []
        receipt = result["agent_input"]["telemetry"]
        assert receipt["camera_queries"] == receipt["records_read"] == 0
        assert reason in receipt["truncation_reasons"]
    assert scene.service.logs == []


def test_graph_and_context_budgets_disclose_omissions_without_unique_winner(tmp_path: Path) -> None:
    index = GuidanceIndex(linked_scene(tmp_path, count=50, candidate_count=20, dense=True))
    result = index.guide("navigation", "C0", 0, 1, top_k=2)
    data = result["agent_input"]
    receipt = data["telemetry"]
    assert receipt["graph_nodes_visited"] <= MAX_NODES
    assert receipt["graph_edges_touched"] <= MAX_EDGES
    assert receipt["camera_queries"] == MAX_CAMERAS
    assert set(receipt["truncation_reasons"]) == {
        "NODE_BUDGET", "CAMERA_QUERY_BUDGET", "FEATURE_TOP_K_BUDGET", "CANDIDATE_REF_BUDGET",
    }
    assert len(data["features"]) == len(result["agent_output"]["selected_refs"]) == 2
    for source, returned in zip(data["features"], result["agent_output"]["candidate_alternatives"],
                                strict=True):
        assert source["candidate_count"] == returned["candidate_count"] == 20
        assert len(source["ordered_candidate_refs"]) == MAX_CANDIDATES
        assert returned["ordered_candidate_refs"] == source["ordered_candidate_refs"]
        assert returned["omitted_candidate_count"] == 20 - MAX_CANDIDATES
        assert source["complete"] is False
        assert source["termination_reason"] == "MAX_PATHS_REACHED"


def test_candidate_order_gt_free_allowlist_and_registered_next_actions(tmp_path: Path) -> None:
    scene = linked_scene(tmp_path)
    before = json.dumps(scene.service.events, sort_keys=True)
    result = GuidanceIndex(scene).guide("navigation", "C0", 0, 1, top_k=4)
    exported = json.dumps(result)
    assert all(word not in exported for word in (
        "MUST_NOT_LEAK", "ground_truth", "actor_identity", "source.blend", "feature_vector",
        "camera_to_world", "polyline", "navmesh_corridor"))
    assert before == json.dumps(scene.service.events, sort_keys=True)
    for feature in result["agent_input"]["features"]:
        assert feature["ordered_candidate_refs"] == [
            opaque_ref("navcandidate", feature["record_ref"], str(i)) for i in range(3)]
        assert feature["event_kind"] == "INFERRED_GAP_ALTERNATIVES"
        assert feature["support_state"] == "GAP_ALTERNATIVES"
    supplied = {f["record_ref"] for f in result["agent_input"]["features"]}
    assert len(result["agent_output"]["next_bounded_actions"]) <= 2
    assert all(a["tool"] == "get_event_detail" and a["record_ref"] in supplied
               for a in result["agent_output"]["next_bounded_actions"])
    assert result["agent_output"] == mock_decide(result["agent_input"])
    invalid = result["agent_input"] | {"repository": "/private/source"}
    with pytest.raises(ValidationError):
        AgentInput.model_validate(invalid)
    with pytest.raises(ValidationError):
        mock_decide(invalid)


@pytest.mark.parametrize("changes,reason", [
    ({"camera_id": "foreign"}, "CAMERA_SCOPE_DENIED"),
    ({"start": 101, "end": 102}, "GUIDANCE_TIME_SCOPE_DENIED"),
    ({"start": 2, "end": 1}, "GUIDANCE_TIME_SCOPE_DENIED"),
    ({"start": float("nan")}, "GUIDANCE_TIME_SCOPE_DENIED"),
    ({"behavior": "identify"}, "GUIDANCE_BEHAVIOR_DENIED"),
    ({"top_k": 9}, "GUIDANCE_TOP_K_DENIED"),
    ({"top_k": True}, "GUIDANCE_TOP_K_DENIED"),
])
def test_untrusted_scope_and_budget_fail_before_reads(
    tmp_path: Path, changes: dict[str, Any], reason: str,
) -> None:
    scene = linked_scene(tmp_path)
    index = GuidanceIndex(scene)
    args = {"label": "navigation", "camera_id": "C0", "start": 0, "end": 1} | changes
    with pytest.raises(ValueError, match=reason):
        index.guide(**args)
    assert scene.service.logs == []


def test_input_stage_and_changed_run_fail_closed(tmp_path: Path) -> None:
    scene = linked_scene(tmp_path)
    index = GuidanceIndex(scene)
    scene.service.guard.binding = scene.service.guard.binding.model_copy(update={"run_id": "other"})
    with pytest.raises(ValueError, match="GUIDANCE_SCOPE_CHANGED"):
        index.guide("navigation", "C0", 0, 1)
    from amidst.engineering.access import SessionGuard

    scene.service.guard = SessionGuard(scene.service.guard.binding)
    with pytest.raises(ValueError, match="GUIDANCE_RESULTS_ONLY"):
        GuidanceIndex(scene)


def test_empty_local_window_stays_explicit(tmp_path: Path) -> None:
    index = GuidanceIndex(linked_scene(tmp_path))
    result = index.guide("navigation", "C0", 5, 6)
    assert result["status"] == "READY"
    assert result["agent_output"]["decision"] == "NO_SCOPED_EVIDENCE"
    assert result["agent_output"]["selected_refs"] == []
    assert result["agent_input"]["telemetry"]["records_read"] == 0


def test_dense_cycles_stop_at_the_edge_budget_and_never_duplicate_nodes(tmp_path: Path) -> None:
    result = GuidanceIndex(linked_scene(tmp_path, count=6, complete_links=True)).guide(
        "navigation", "C0", 0, 1)
    data = result["agent_input"]
    assert len({n["node_ref"] for n in data["navigation_nodes"]}) == len(data["navigation_nodes"])
    assert data["telemetry"]["graph_edges_touched"] == MAX_EDGES
    assert len(data["navigation_edges"]) == MAX_EDGES
    assert "EDGE_BUDGET" in data["telemetry"]["truncation_reasons"]


def test_camera_and_region_labels_select_registered_resources_only(tmp_path: Path) -> None:
    index = GuidanceIndex(linked_scene(tmp_path))
    camera = index.guide("camera:C2", "C0", 0, 1)
    assert camera["agent_input"]["telemetry"]["camera_queries"] == 1
    assert all(f["camera_ids"] == ["C2"] for f in camera["agent_input"]["features"])
    region = index.guide("region:r", "C0", 0, 1, top_k=4)
    assert len(region["agent_input"]["features"]) == 4
    assert all(f["region_ids"] == ["r"] for f in region["agent_input"]["features"])
    assert region["agent_input"]["selection"]["camera_id"] == "C0"


def test_source_strings_cannot_overflow_the_agent_context_budget(tmp_path: Path) -> None:
    scene = linked_scene(tmp_path)
    index = GuidanceIndex(scene)
    index._scope = index._scope.model_copy(update={"place_id": "x" * MAX_AGENT_INPUT_BYTES})
    with pytest.raises(ValueError, match="GUIDANCE_CONTEXT_BYTE_BUDGET"):
        index.guide("navigation", "C0", 0, 1)

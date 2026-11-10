"""Selected-source fallback, preserved evidence, bounds and real HTTP guards."""

from __future__ import annotations

import copy
import json

import pytest
from test_blender_association import fixture, gap_input
from test_blender_association_service import context
from test_blender_association_service import live_association as live_association
from test_blender_motion_service import post
from test_blender_scene import bundle as bundle

from amidst.workbench.blender_association import BaselineAssociationIndex
from amidst.workbench.target_reconstruction import TargetLimits, reconstruct_target


class Scene:
    scene_id = "substitute-target-test"

    def __init__(self, baseline):
        self.baseline = baseline
        self.index = BaselineAssociationIndex(baseline)
        self.calls = 0

    def snapshot(self):
        return {"baseline": copy.deepcopy(self.baseline)}

    def cross_camera_reconstruction(self, cameras, start, end, top_k=3):
        self.calls += 1
        return self.index.reconstruct(cameras, start, end, top_k)


def run(scene, ref=None, **kwargs):
    cameras = sorted({r["camera_id"] for r in scene.baseline["frames"]})
    return reconstruct_target(
        scene,
        cameras,
        0,
        3,
        3,
        ref or scene.baseline["measurements"][0]["observation_ref"],
        **kwargs,
    )


def test_selected_path_preserves_canonical_refs_original_rank_and_is_deterministic():
    scene = Scene(
        fixture(
            [
                ("A", "a1", {0: [0, 0, 0], 0.2: [0.2, 0, 0]}),
                ("A", "a2", {0: [0, 0.1, 0], 0.2: [0.2, 0.1, 0]}),
                ("B", "b", {0.6: [0.6, 0, 0], 0.8: [0.8, 0, 0]}),
            ]
        )
    )
    original = scene.index.reconstruct(["A", "B"], 0, 3, 5)
    second = original["candidates"][1]
    path = next(p for p in second["paths"] if len(p["camera_ids"]) > 1)
    origin = next(n for n in original["graph"]["nodes"] if n["node_ref"] == path["node_refs"][0])
    ref = origin["source_observation_refs"][0]
    result = run(scene, ref)
    assert result == run(scene, ref)
    assert result["status"] == "READY" and result["agent_used"] is False
    assert result["association"] == original
    assert result["selected_observation"]["observation_ref"] == ref
    assert result["target_candidates"][0]["candidate_ref"] == second["candidate_ref"]
    assert result["target_candidates"][0]["rank"] == 2
    assert result["target_candidates"][0]["paths"] == [path]
    assert result["identity_verdict"] == "UNCONFIRMED"
    assert result["constraints"]["physical_navigation_verdict"] == "UNKNOWN"
    assert result["constraints"]["model_calls"] == result["constraints"]["tool_calls"] == 0
    assert all(
        r["authority"] == "EVIDENCE_GRAPH_PROPOSAL_ONLY" for r in result["reachable_cameras"]
    )
    assert all(
        ref in p["source_observation_refs"] for c in result["target_candidates"] for p in c["paths"]
    )
    json.dumps(result, allow_nan=False)


def test_long_gap_remains_missing_with_null_positions_and_no_velocity_bridge():
    scene = Scene(gap_input(2, 2))
    result = run(scene)
    assert result["status"] == "READY"
    selected = result["target_candidates"][0]["paths"][0]
    original = result["association"]["candidates"][0]["paths"][0]
    assert selected == original
    missing = next(row for row in selected["samples"] if row["state"] == "MISSING")
    assert missing["world_position"] is None
    assert missing["missing_time_range"] == [0.2, 2]
    assert not any(
        v["time_range"][0] < 2 and v["time_range"][1] > 0.2 for v in selected["velocities"]
    )


def test_unknown_reference_never_selects_another_observation():
    scene = Scene(gap_input())
    result = run(scene, "observation:" + "f" * 24)
    assert result["status"] == "UNKNOWN" and result["reason"] == "OBSERVATION_NOT_FOUND"
    assert result["selected_observation"] is None
    assert result["target_candidates"] == [] and scene.calls == 0


def test_missing_projection_cannot_generate_a_target():
    scene = Scene(fixture([("A", "missing", {0: None}), ("B", "seen", {0.6: [0.6, 0, 0]})]))
    result = run(scene)
    assert result["status"] == "UNKNOWN" and result["reason"] == "SELECTED_PROJECTION_UNAVAILABLE"
    assert result["selected_observation"]["world_position"] is None
    assert result["association"] is None and scene.calls == 0


def test_selected_observation_requires_a_canonical_node(monkeypatch):
    scene = Scene(gap_input())
    original = scene.cross_camera_reconstruction

    def without_nodes(*args):
        value = original(*args)
        value["graph"]["nodes"] = []
        return value

    monkeypatch.setattr(scene, "cross_camera_reconstruction", without_nodes)
    result = run(scene)
    assert result["status"] == "UNKNOWN" and result["reason"] == "SELECTED_NODE_UNAVAILABLE"


@pytest.mark.parametrize("kind", ["speed", "last-camera"])
def test_no_cross_camera_continuation_returns_unknown(kind):
    scene = Scene(gap_input(0.4, 10) if kind == "speed" else gap_input())
    ref = scene.baseline["measurements"][-1]["observation_ref"] if kind == "last-camera" else None
    result = run(scene, ref)
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "NO_SELECTED_TARGET_CROSS_CAMERA_CONTINUATION"
    assert result["target_candidates"] == []
    if kind == "speed":
        assert result["association"]["graph"]["rejected_edges"][0]["reason"] == "SPEED_CAP"


def test_narrow_window_preserves_selection_ownership_and_original_refs():
    scene = Scene(gap_input(2, 2))
    ref = scene.baseline["measurements"][0]["observation_ref"]
    full = run(scene, ref)
    narrow = reconstruct_target(scene, ["B", "A"], 1, 3, 1, ref)
    assert narrow["status"] == "READY"
    assert narrow["selected_observation"] == full["selected_observation"]
    assert (
        narrow["target_candidates"][0]["candidate_ref"]
        == full["target_candidates"][0]["candidate_ref"]
    )
    assert all(
        1 <= r["timestamp"] <= 3 for r in narrow["target_candidates"][0]["paths"][0]["samples"]
    )


@pytest.mark.parametrize(
    "limits,reason",
    [
        (TargetLimits(deadline_s=0), "DEADLINE_EXCEEDED"),
        (TargetLimits(max_records_scanned=1), "SCAN_BUDGET_EXHAUSTED"),
        (TargetLimits(max_paths_scanned=0), "SCAN_BUDGET_EXHAUSTED"),
        (TargetLimits(max_expansions=0), "SCAN_BUDGET_EXHAUSTED"),
    ],
)
def test_fallback_termination_is_bounded_and_returns_no_partial_candidate(limits, reason):
    result = run(Scene(gap_input()), limits=limits)
    assert result["status"] == "UNKNOWN" and result["reason"] == reason
    assert result["target_candidates"] == [] and result["reachable_cameras"] == []
    assert result["trace"][-1]["decision"] == reason


def test_cooperative_deadline_is_checked_after_existing_association(monkeypatch):
    scene = Scene(gap_input())
    now = [0.0]
    original = scene.cross_camera_reconstruction

    def expired(*args):
        result = original(*args)
        now[0] = 3.0
        return result

    monkeypatch.setattr(scene, "cross_camera_reconstruction", expired)
    result = run(scene, clock=lambda: now[0])
    assert result["association"] is not None
    assert result["status"] == "UNKNOWN" and result["reason"] == "DEADLINE_EXCEEDED"
    assert result["target_candidates"] == []


def target_query(base, scene):
    common = context(base, scene)
    query = common | {"camera_ids": ["CAM_A", "CAM_B"], "start": 0, "end": 9.8, "top_k": 3}
    status, association = post(base, "cross_camera_reconstruction", query)
    assert status == 200
    edge = association["graph"]["edges"][0]
    origin = next(
        n for n in association["graph"]["nodes"] if n["node_ref"] == edge["from_node_ref"]
    )
    return query | {"observation_ref": origin["source_observation_refs"][0]}


def test_real_source_http_target_is_exact_scoped_repeatable_and_no_agent(live_association):
    base, scene, _, _ = live_association
    query = target_query(base, scene)
    status, result = post(base, "target_reconstruction", query)
    assert status == 200 and result["status"] == "READY"
    assert result["schema_version"] == "workbench.target-reconstruction.v1"
    assert result["selected_observation"]["observation_ref"] == query["observation_ref"]
    assert result["agent_used"] is False
    assert post(base, "target_reconstruction", query) == (200, result)
    assert all(
        query["observation_ref"] in p["source_observation_refs"]
        for c in result["target_candidates"]
        for p in c["paths"]
    )
    raw = json.dumps(result, allow_nan=False)
    assert all(word not in raw for word in ["local_path", "/private/", "ground_truth", "DO_NOT_"])
    logs_status, logs = post(base, "logs", {k: query[k] for k in ["session_ref", "scene_id"]})
    assert logs_status == 200
    assert "target_reconstruction_decision" in json.dumps(logs)


def test_real_http_target_role_scope_and_strict_request_guards(live_association):
    base, scene, _, _ = live_association
    query = target_query(base, scene)
    assert post(base, "target_reconstruction", query | context(base, scene, "management"))[0] == 403
    assert post(base, "target_reconstruction", query | {"scene_id": "other-site"})[0] == 403
    for fields in [
        {"top_k": True},
        {"top_k": "3"},
        {"top_k": 0},
        {"top_k": 6},
        {"observation_ref": 1},
        {"observation_ref": "observation:invalid"},
        {"camera_ids": ["CAM_A", "CAM_A"]},
        {"camera_ids": ["OTHER"]},
        {"start": True},
        {"end": "9.8"},
        {"end": float("nan")},
        {"start": 4, "end": 2},
        {"max_speed_m_s": 99},
        {"local_path": "/private/forbidden"},
        {"ground_truth": {"identity": "wrong"}},
        {"deadline_s": 100},
        {"target_id": "simulator-person"},
    ]:
        assert post(base, "target_reconstruction", query | fields)[0] == 400
    unknown_query = query | {"observation_ref": "observation:" + "f" * 24}
    status, result = post(base, "target_reconstruction", unknown_query)
    assert status == 200 and result["status"] == "UNKNOWN"
    assert result["selected_observation"] is None and result["target_candidates"] == []

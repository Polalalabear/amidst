"""Independent v2 investigation: original freezes, scoped revisions, no new producers."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_accuracy_scene import frozen_accuracy as frozen_accuracy
from test_product_bridge import MANAGER, RESEARCH, Access, call, payload

from amidst.engineering.access import SessionGuard
from amidst.engineering.registry import opaque_ref
from amidst.product.run import digest
from amidst.workbench.accuracy_product import load_accuracy_product_bridge
from amidst.workbench.product_bridge import BinaryResponse, BridgeDenied, ProductBridge
from amidst.workbench.scenes import load_local_camera, load_local_camera_accuracy_v2


@pytest.fixture
def accuracy_bridge(frozen_accuracy: tuple[Path, Path], tmp_path: Path) -> Iterator[ProductBridge]:
    _, output = frozen_accuracy
    scene = load_local_camera_accuracy_v2(output)
    accesses = {
        RESEARCH: Access("research", frozenset({scene.scene_id})),
        MANAGER: Access("management", frozenset({scene.scene_id})),
    }
    bridge = load_accuracy_product_bridge(output, scene, accesses.__getitem__,
                                          tmp_path / "cases.db")
    yield bridge
    bridge.close()


def trace_intent(bridge: ProductBridge) -> dict[str, object]:
    service = bridge.services["photos_plus_observations"]
    event = next(event for event in service.base.events.values() if event["candidates"])
    observation = next(row for row in service.base.observations.values()
                       if row["local_track_ref"] in event["local_track_refs"])
    return {"task": "TRACE", "camera_ref": observation["camera_refs"][0],
            "time_range": [0, 6], "seed_refs": [observation["observation_ref"]]}


def test_independent_context_and_original_mode_freezes(accuracy_bridge: ProductBridge) -> None:
    plus = call(accuracy_bridge, "context")
    only = call(accuracy_bridge, "context", observation_mode="photos_only")
    assert accuracy_bridge.runtime is None  # No manufactured E1 ProductRuntime.
    assert plus["available_modes"] == ["photos_only", "photos_plus_observations"]
    assert plus["source"]["run_id"] == only["source"]["run_id"]
    assert plus["source"]["frame_count"] == len(accuracy_bridge.scene.service.frames)
    assert plus["capabilities"]["supported_tasks"] == ["TRACE", "BEHAVIOR"]
    assert not any(plus["capabilities"][name] for name in
                   ("appearance", "stitch", "videos", "inference_execution"))
    for context in (plus, only):
        binding = context["accuracy_binding"]
        assert binding["experiment_id"] == "accuracy-workbench-fixture-v2"
        assert binding["variant"] == "end_to_end"
        assert binding["explicit_support_states"] == ["SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES"]
        mode = context["observation_mode"]
        original = accuracy_bridge.services[mode].base.context()
        assert binding["original_freeze_ref"] == original["freeze_ref"]
        assert binding["mode_config_sha256"] == accuracy_bridge.services[
            mode].base.guard.binding.config_sha256
    assert plus["product_context"]["run_ref"] != only["product_context"]["run_ref"]
    assert plus["accuracy_binding"]["original_freeze_ref"] != only[
        "accuracy_binding"]["original_freeze_ref"]
    public = json.dumps((plus, only))
    assert "source_locator" not in public and "relative_path" not in public
    assert "/Users/" not in public and "ground_truth" not in public


def test_v2_event_pages_and_details_preserve_states_candidates_and_paging(
    accuracy_bridge: ProductBridge,
) -> None:
    service = accuracy_bridge.services["photos_plus_observations"]
    returned: dict[str, Any] = {}
    for camera in service.base.cameras:
        params: dict[str, Any] = {"camera_ref": camera, "time_range": [0, 6], "limit": 2}
        while True:
            page = call(accuracy_bridge, "tool", tool="query_events", params=params)
            assert page["retrieval"]["records_read"] <= 2
            for summary in page["items"]:
                detail = call(accuracy_bridge, "tool", tool="get_event_detail",
                              params={"event_ref": summary["event_ref"]})
                raw = service.base.events[summary["event_ref"]]
                for field in ("support_state", "experiment_id", "variant", "supports",
                              "conflicts", "alternatives", "complete", "termination_reason"):
                    assert summary[field] == detail[field] == raw[field]
                assert detail["candidates"] == raw["candidates"]
                assert detail["trajectories"] == raw["trajectories"]
                returned[summary["event_ref"]] = summary
            cursor = page["retrieval"]["next_cursor"]
            if cursor is None:
                break
            params["cursor"] = cursor
    assert set(returned) == set(service.base.events)
    assert {row["support_state"] for row in returned.values()} == {
        row["support_state"] for row in service.base.events.values()}
    event = next(iter(returned))
    call(accuracy_bridge, "context", observation_mode="photos_only")
    with pytest.raises(BridgeDenied, match="INVALID_OR_UNAVAILABLE"):
        call(accuracy_bridge, "tool", tool="get_event_detail", params={"event_ref": event})


@pytest.mark.parametrize("action,fields", [
    ("context", {}), ("tool", {"tool": "list_cameras"}),
    ("intent", {"intent": {"task": "BEHAVIOR"}}), ("cases", {}),
    ("timeline", {"timestamp": 0.0}), ("videos", {}),
])
def test_research_role_is_enforced_for_v2(
    accuracy_bridge: ProductBridge, action: str, fields: dict[str, object],
) -> None:
    with pytest.raises(BridgeDenied, match="^ROLE_DENIED$"):
        call(accuracy_bridge, action, MANAGER, **fields)


@pytest.mark.parametrize("task", ["COMPARE", "MULTI_TARGET"])
def test_unimplemented_v2_workflows_are_not_granted(
    accuracy_bridge: ProductBridge, task: str,
) -> None:
    with pytest.raises(BridgeDenied, match="^TASK_UNAVAILABLE$"):
        call(accuracy_bridge, "intent", intent=trace_intent(accuracy_bridge) | {"task": task})


@pytest.mark.parametrize("tool", ["search_person_appearance", "get_stitch_hypotheses"])
def test_no_new_appearance_or_stitch_capability(accuracy_bridge: ProductBridge, tool: str) -> None:
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        call(accuracy_bridge, "tool", tool=tool)
    assert call(accuracy_bridge, "videos")["items"] == []


def test_paused_case_survives_reload_without_persisting_frozen_records(
    frozen_accuracy: tuple[Path, Path], tmp_path: Path,
) -> None:
    _, output = frozen_accuracy
    scene = load_local_camera_accuracy_v2(output)
    ledger = tmp_path / "v2-case-ledger.db"
    def access(_: str) -> Access:
        return Access("research", frozenset({scene.scene_id}))
    bridge = load_accuracy_product_bridge(output, scene, access, ledger)
    plan = call(bridge, "intent", intent=trace_intent(bridge))["plan"]
    paused = call(bridge, "execute", plan_ref=plan["plan_ref"], max_new_calls=3)
    assert paused["state"] == "PAUSED"
    stopped = call(bridge, "execute", plan_ref=plan["plan_ref"], stop=True)
    bridge.close()
    restarted = load_accuracy_product_bridge(output, scene, access, ledger)
    try:
        assert call(restarted, "case", plan_ref=plan["plan_ref"]) == stopped
        case = call(restarted, "execute", plan_ref=plan["plan_ref"], resume=True)
        assert case["state"] == "COMPLETED"
        assert case["receipts"][:3] == paused["receipts"]
        report = call(restarted, "report", plan_ref=plan["plan_ref"])
        assert report["identity_status"] == "UNRESOLVED_PROVISIONAL"
        assert report["all_alternative_refs"]
        supplement = report["accuracy_evidence"]
        assert supplement["content_sha256"] == digest({key: value for key, value in
            supplement.items() if key != "content_sha256"})
        assert supplement["binding"]["experiment_id"] == "accuracy-workbench-fixture-v2"
        assert supplement["events"]
        service = restarted.services["photos_plus_observations"]
        assert {item["event_ref"] for item in supplement["events"]} == {
            row["record_ref"] for row in report["evidence"] if row["kind"] == "EVENT"}
        for item in supplement["events"]:
            assert item["support_state"] == service.base.events[item["event_ref"]]["support_state"]
        assert case["accuracy_evidence"] == supplement
        exported = call(restarted, "export_report", report_ref=report["report_ref"])
        assert isinstance(exported, BinaryResponse)
        assert report["report_sha256"].encode() in exported.body
        assert supplement["content_sha256"].encode() in exported.body
        assert b"GAP_ALTERNATIVES" in exported.body
        review = call(restarted, "review", review={"report_ref": report["report_ref"],
            "report_sha256": report["report_sha256"], "action": "PRESERVE_AMBIGUITY",
            "reason_code": "AMBIGUOUS_EVIDENCE"})
        assert review["confirmed_global_identity"] is False
        call(restarted, "context", observation_mode="photos_only")
        assert call(restarted, "cases")["items"] == []
        with pytest.raises(BridgeDenied, match="INVALID_OR_UNAVAILABLE"):
            call(restarted, "execute", plan_ref=plan["plan_ref"])
        with sqlite3.connect(ledger) as db:
            assert db.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] > 0
    finally:
        restarted.close()


def test_v2_bindings_and_non_v2_scene_cannot_be_substituted(
    frozen_accuracy: tuple[Path, Path], tmp_path: Path,
) -> None:
    source, output = frozen_accuracy
    def access(_: str) -> Access:
        return Access("research", frozenset({"local-camera-accuracy-v2"}))
    with pytest.raises(BridgeDenied, match="ACCURACY_SCOPE_MISMATCH"):
        load_accuracy_product_bridge(output, load_local_camera(source), access,
                                     tmp_path / "case.db")
    scene = load_local_camera_accuracy_v2(output)
    scene._snapshot["experiment_id"] = "wrong-experiment"
    with pytest.raises(BridgeDenied, match="ACCURACY_SCOPE_MISMATCH"):
        load_accuracy_product_bridge(output, scene, access, tmp_path / "case.db")


def test_immutable_artifact_directories_are_not_used_as_ledger(
    frozen_accuracy: tuple[Path, Path],
) -> None:
    source, output = frozen_accuracy
    scene = load_local_camera_accuracy_v2(output)
    for ledger in (source / "cases.db", output / "cases.db"):
        with pytest.raises(BridgeDenied, match="ACCURACY_LEDGER_LOCATION_DENIED"):
            load_accuracy_product_bridge(output, scene,
                lambda _: Access("research", frozenset({scene.scene_id})), ledger)
        assert not ledger.exists()


def test_stale_stage_cross_scene_and_external_refs_fail_closed(
    accuracy_bridge: ProductBridge,
) -> None:
    with pytest.raises(BridgeDenied, match="^SCENE_DENIED$"):
        accuracy_bridge.call("context", payload(accuracy_bridge) | {"scene_id": "local-camera"})
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        call(accuracy_bridge, "tool", tool="get_event_detail",
             params={"event_ref": opaque_ref("event", "e1-other-experiment")})
    base = accuracy_bridge.services["photos_plus_observations"].base
    base.guard = SessionGuard(base.guard.binding)
    with pytest.raises(BridgeDenied, match="^PRODUCT_BINDING_DENIED$"):
        call(accuracy_bridge, "context")


def test_loading_and_investigation_do_not_read_truth_evaluation_or_run_producers(
    frozen_accuracy: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amidst.research_accuracy import run as accuracy_run

    _, output = frozen_accuracy
    scene = load_local_camera_accuracy_v2(output)
    reads = Path.read_bytes
    texts = Path.read_text
    denied = {"ground_truth.json", "recipe.json", "comparison.json", "evaluation.json"}
    def guarded_bytes(path: Path) -> bytes:
        assert path.name not in denied
        assert "evaluation" not in path.parts and "evaluation_inputs" not in path.parts
        return reads(path)
    def guarded_text(path: Path, *args: Any, **kwargs: Any) -> str:
        assert path.name not in denied
        assert "evaluation" not in path.parts and "evaluation_inputs" not in path.parts
        return texts(path, *args, **kwargs)
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("New producer invocation is forbidden")
    monkeypatch.setattr(Path, "read_bytes", guarded_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_text)
    monkeypatch.setattr(accuracy_run, "_produce", forbidden)
    monkeypatch.setattr(accuracy_run, "build_inference", forbidden)
    bridge = load_accuracy_product_bridge(output, scene,
        lambda _: Access("research", frozenset({scene.scene_id})), tmp_path / "cases.db")
    try:
        plan = call(bridge, "intent", intent=trace_intent(bridge))["plan"]
        assert call(bridge, "execute", plan_ref=plan["plan_ref"])["state"] == "COMPLETED"
        assert call(bridge, "report", plan_ref=plan["plan_ref"])["identity_status"] == (
            "UNRESOLVED_PROVISIONAL")
    finally:
        bridge.close()

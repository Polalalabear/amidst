"""Fresh synthetic ports and actual loopback HTTP, without production/raw assets."""

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest

from amidst.engineering.run import materialize_run
from amidst.workbench.reviews import ReviewStore, replay_review_delta
from amidst.workbench.scenes import load_synthetic_lab
from amidst.workbench.service import Application, Workbench
from amidst.workbench.system_ports import run_port_probe


@pytest.fixture(scope="module")
def port_result():
    return run_port_probe()


def test_fresh_ports_use_actual_pixels_projection_graph_repository_and_replay(port_result):
    assert port_result["status"] == "PASS"
    assert port_result["summary"]["passed"] == port_result["summary"]["total"] == 10
    ports = {p["port"]: p for p in port_result["ports"]}
    assert ports["source.rgb"]["output"]["rgb_frames"] == 102
    assert ports["perception.measurements"]["output"]["measurements"] > 0
    assert ports["geometry.projected"]["output"]["world_position"] is not None
    assert ports["graph.gaps"]["output"]["candidate_count"] > 0
    assert ports["repository.snapshot"]["input"]["snapshot_sha256"] == (
        ports["repository.snapshot"]["output"]["reopened_sha256"])
    assert ports["truth.isolation"]["output"]["snapshot_unchanged"] is True
    assert port_result["agent_output"]["provider"] == "LOCAL_MOCK"
    assert port_result["agent_output"]["confirmed_identity"] is None
    assert port_result["agent_input"]["telemetry"]["global_scan"] is False
    assert port_result["summary"]["operator_run_modified"] is False


def test_port_report_contains_only_delta_not_scene_copy(port_result):
    output = next(p for p in port_result["ports"] if p["port"] == "history.delta")["output"]
    delta = output["delta"]
    assert delta["schema_version"] == "workbench.scene-review-delta.v1"
    encoded = json.dumps(delta)
    assert '"objects"' not in encoded and ".blend" not in encoded
    assert "simulation/export" not in json.dumps(port_result)
    assert port_result["summary"]["blend_copies"] == 0
    assert output["needs_rerun"] is True


@pytest.fixture(scope="module")
def live_system(tmp_path_factory):
    repo = Path(__file__).parents[2]
    root = tmp_path_factory.mktemp("system-http")
    source = root / "source"
    materialize_run(source, repo / "configs/engineering/simulation_v1.json",
                    run_id="system-http-fixture-v1")
    scene = load_synthetic_lab(source)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(root / "reviews.sqlite3", {
        scene.scene_id: {k: scene.snapshot()[k] for k in keys}})
    workbench = Workbench({scene.scene_id: scene}, reviews)

    class Quiet(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    with make_server("127.0.0.1", 0, Application(workbench, repo), handler_class=Quiet) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{server.server_port}", scene, reviews
        server.shutdown()
        thread.join(timeout=5)
        assert not thread.is_alive()


def request(base, route, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(base + route, data=data,
                  headers={} if data is None else {"Content-Type": "application/json",
                                                   "Origin": base})
    try:
        with urlopen(req, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_real_http_all_boundary_actions_and_delta_replay(live_system):
    base, scene, reviews = live_system
    assert request(base, "/api/bootstrap")[0] == 200
    status, session = request(base, "/api/session", {"role": "research"})
    assert status == 200
    common = {"session_ref": session["session_ref"], "scene_id": scene.scene_id}
    status, preset = request(base, "/api/semantic_presets", common)
    assert status == 200
    assert [b["value"] for b in preset["presets"]["behaviors"]] == [
        "walking", "running", "enter_exit"]
    defaults = preset["presets"]["defaults"]
    status, guide = request(base, "/api/navigation_guide", common | defaults)
    assert status == 200 and guide["status"] == "READY"
    status, decision = request(base, "/api/agent_decision",
                               common | {"guide_ref": guide["guide_ref"]})
    assert status == 200
    assert decision["agent_input"] == guide["agent_input"]
    assert all(a["status"] == "PASS" for a in decision["executed_actions"])
    assert len(decision["executed_actions"]) <= 2
    query = {k: defaults[k] for k in ("camera_id", "start", "end")}
    status, result = request(base, "/api/query", common | query)
    assert status == 200 and result["events"]
    event_ref = result["events"][0]["event_ref"]
    assert request(base, "/api/event", common | {"event_ref": event_ref})[0] == 200
    assert request(base, "/api/timeline", common | {
        "camera_ids": [defaults["camera_id"]], "timestamp": defaults["start"]})[0] == 200
    status, log = request(base, "/api/logs", common)
    assert status == 200 and any(row.get("event_ref") == event_ref for row in log["items"])
    status, storage = request(base, "/api/storage_probe", common | {"stage": "all"})
    assert status == 200 and storage["status"] == "PASS"
    status, ports = request(base, "/api/system_ports", common)
    assert status == 200 and ports["status"] == "PASS"
    assert ports["selected_scene_used_as_input"] is False
    obj = next(o for o in scene.snapshot()["objects"] if "label" in o["editable_fields"])
    status, draft = request(base, "/api/draft", common | {
        "object_id": obj["object_id"], "changes": {"label": "HTTP差異測試"},
        "base_version": 0, "reviewer": "synthetic-http", "reason": "delta-only test"})
    assert status == 200
    validate = {"session_ref": common["session_ref"], "draft_id": draft["draft"]["draft_id"]}
    assert request(base, "/api/validate", validate)[0] == 200
    assert request(base, "/api/publish", validate | {
        "expected_version": 0, "reviewer": "synthetic-http", "reason": "delta-only test"})[0] == 200
    status, exported = request(base, "/api/export_delta", common | {"version": 1})
    assert status == 200 and exported["filename"].endswith("delta-v1.json")
    versions = reviews.state(scene.scene_id)["versions"]
    assert replay_review_delta(versions[0], exported["delta"]) == versions[1]["overlay"]


def test_real_http_rejects_manager_cross_session_and_oversized_scope(live_system):
    base, scene, _ = live_system
    _, researcher = request(base, "/api/session", {"role": "research"})
    _, manager = request(base, "/api/session", {"role": "management"})
    common = {"scene_id": scene.scene_id}
    for action in ("semantic_presets", "system_ports", "storage_probe"):
        status, _ = request(base, "/api/" + action,
                            common | {"session_ref": manager["session_ref"]})
        assert status == 403
    research = common | {"session_ref": researcher["session_ref"]}
    _, presets = request(base, "/api/semantic_presets", research)
    defaults = presets["presets"]["defaults"]
    _, guide = request(base, "/api/navigation_guide", research | defaults)
    other = request(base, "/api/session", {"role": "research"})[1]
    status, _ = request(base, "/api/agent_decision", common | {
        "session_ref": other["session_ref"], "guide_ref": guide["guide_ref"]})
    assert status == 403
    binding = scene.service.guard.binding
    try:
        scene.service.guard.binding = binding.model_copy(update={"run_id": "changed-live-run"})
        status, _ = request(base, "/api/agent_decision",
                            research | {"guide_ref": guide["guide_ref"]})
        assert status == 403
    finally:
        scene.service.guard.binding = binding
    status, _ = request(base, "/api/navigation_guide", research | defaults | {"end": 999})
    assert status == 403
    status, unknown = request(base, "/api/navigation_guide",
                              research | defaults | {"label": "unknown"})
    assert status == 200 and unknown["status"] == "NEEDS_INPUT"
    assert unknown["agent_input"]["telemetry"]["records_read"] == 0

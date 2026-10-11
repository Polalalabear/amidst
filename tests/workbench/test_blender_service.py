"""Real HTTP over a source-bound RGB fixture, with no Agent decisions."""

import json
import threading
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest
from PIL import Image

# Share the synthetic, source-bound fixture builder; original project assets are never changed.
from test_blender_scene import bundle as bundle

from amidst.workbench.blender_scene import load_blender_scene
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Workbench


@pytest.fixture
def live_blender(bundle, monkeypatch):
    root, _, repo = bundle
    scene = load_blender_scene(root)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(repo / "test-reviews.sqlite3", {
        scene.scene_id: {key: scene.snapshot()[key] for key in keys}})
    workbench = Workbench({scene.scene_id: scene}, reviews)

    def forbidden_agent(*_args, **_kwargs):
        raise AssertionError("the Blender baseline invoked an Agent")

    monkeypatch.setattr("amidst.workbench.service.mock_decide", forbidden_agent)
    monkeypatch.setattr("amidst.workbench.service.GuidanceIndex", forbidden_agent)

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


def send(base, action, payload):
    request = Request(base + "/api/" + action, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", "Origin": base})
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_real_http_baseline_query_source_frames_and_no_agent(live_blender):
    base, scene, reviews = live_blender
    status, session = send(base, "session", {"role": "research"})
    assert status == 200
    common = {"session_ref": session["session_ref"], "scene_id": scene.scene_id}
    status, snapshot = send(base, "scene", common)
    assert status == 200
    assert snapshot["snapshot"]["capabilities"]["frame_query"] is True
    assert snapshot["snapshot"]["capabilities"]["scene_review"] is False
    query = common | {"camera_ids": ["CAM_A", "CAM_B"], "start": 0, "end": 1,
                      "target_timestamp": 0.4, "top_k": 3, "behavior_intent": "running"}
    status, first = send(base, "frame_query", query)
    assert status == 200 and first["status"] == "READY"
    assert send(base, "frame_query", query) == (200, first)
    assert first["agent_used"] is False
    assert first["behavior_verdict"] == "UNKNOWN"
    assert first["selection"]["behavior_intent"] == "running"
    assert first["scope"]["scene_id"] == scene.scene_id
    assert {item["camera_id"] for item in first["items"]} == {"CAM_A", "CAM_B"}
    assert first["retrieval"]["frames_read"] == first["retrieval"]["bytes_read"] == 0
    public = json.dumps([first, snapshot])
    assert not any(value in public for value in ["/private/", "TrajectoryID", "local_path",
                                                "DO_NOT_", "ground_truth", "trajectory"])
    status, selected = send(base, "timeline", common | {"camera_ids": ["CAM_A", "CAM_B"],
                                                        "timestamp": 0.4})
    assert status == 200 and all(f["status"] == "EXACT" for f in selected["frames"])
    media_query = urlencode(common | {"ref": first["items"][0]["media_ref"]})
    with urlopen(base + "/api/media?" + media_query, timeout=60) as response:
        assert response.status == 200
        raw = response.read()
    with Image.open(BytesIO(raw)) as image:
        assert image.size == (960, 540)
        assert "File" not in image.info and "TrajectoryID" not in image.info
    assert reviews.state(scene.scene_id)["current_version"] == 0
    assert send(base, "query", common | {"camera_id": "CAM_A", "start": 0, "end": 1})[1][
        "events"] == []


def test_real_http_role_scope_and_unsupported_decision_actions(live_blender):
    base, scene, _ = live_blender
    _, session = send(base, "session", {"role": "research"})
    _, manager = send(base, "session", {"role": "management"})
    common = {"session_ref": session["session_ref"], "scene_id": scene.scene_id}
    query = common | {"camera_ids": ["CAM_A"], "start": 0, "end": 1,
                      "target_timestamp": 0.4, "top_k": 3}
    assert send(base, "frame_query", query | {"session_ref": manager["session_ref"]})[0] == 403
    assert send(base, "frame_query", query | {"scene_id": "unknown-site"})[0] == 403
    for action, extra in [
        ("semantic_presets", {}),
        ("navigation_guide", {"label": "navigation", "camera_id": "CAM_A", "start": 0,
                              "end": 1}),
        ("agent_decision", {"guide_ref": "guide-" + "0" * 64}),
        ("draft", {"object_id": "camera:CAM_A", "changes": {"label": "not permitted"},
                   "base_version": 0, "reviewer": "test", "reason": "readonly source"}),
    ]:
        assert send(base, action, common | extra)[0] == 403
    for changes in [
        {"camera_ids": ["CAM_A", "CAM_A"]}, {"camera_ids": ["CAM_UNKNOWN"]},
        {"top_k": 6}, {"top_k": True}, {"target_timestamp": float("nan")},
        {"start": 2, "end": 1}, {"end": 11}, {"target_timestamp": 2},
        {"local_path": "/private/unapproved.png"}, {"ground_truth": {"identity": "bad"}},
    ]:
        assert send(base, "frame_query", query | changes)[0] == 400


def test_real_http_changed_source_bundle_rejects_cached_results(live_blender):
    base, scene, _ = live_blender
    _, session = send(base, "session", {"role": "research"})
    common = {"session_ref": session["session_ref"], "scene_id": scene.scene_id}
    query = common | {"camera_ids": ["CAM_A"], "start": 0, "end": 1,
                      "target_timestamp": 0.4, "top_k": 3}
    assert send(base, "frame_query", query)[0] == 200
    # Disposable test-bundle mutation, not original media/model/GT.
    inputs = Path(scene.root) / "safe_inputs.json"
    inputs.write_bytes(inputs.read_bytes() + b" ")
    assert send(base, "frame_query", query)[0] == 400
    assert send(base, "timeline", common | {"camera_ids": ["CAM_A"], "timestamp": 0.4})[0] == 400

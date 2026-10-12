"""Real local HTTP scope, numeric guards and byte-range replay for motion artifacts."""

import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest
from test_blender_scene import bundle as bundle

from amidst.workbench.blender_scene import load_blender_scene
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Workbench


class IssuedArtifacts:
    """Fixed binary fixture exercises transport, independently of real encoder tests."""

    video_ref = "motionvideo:" + "a" * 24
    curve_ref = "motioncurve:" + "b" * 24
    video = bytes(range(256)) * 3

    def manifest(self, scene):
        scene.live_scope()
        return {"status": "AVAILABLE", "items": [
            {"media_ref": self.video_ref, "kind": "RECONSTRUCTION_VIDEO", "mime_type": "video/mp4",
             "time_range": [0, 9.8], "duration_s": 10, "frame_count": 50},
            {"media_ref": self.curve_ref, "kind": "POSITION_VELOCITY_CURVES",
             "mime_type": "image/png",
             "time_range": [0, 9.8]},
        ]}

    def media(self, scene, ref):
        scene.live_scope()
        if ref == self.video_ref:
            return "video/mp4", self.video
        if ref == self.curve_ref:
            return scene.media(scene.index.frame_records[0]["frame_ref"])
        raise ValueError("UNREGISTERED_ARTIFACT")


@pytest.fixture
def live_motion(bundle, monkeypatch):
    root, _, repo = bundle
    scene = load_blender_scene(root)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(repo / "motion-transport.sqlite3", {
        scene.scene_id: {k: scene.snapshot()[k] for k in keys}})
    provider = IssuedArtifacts()
    workbench = Workbench({scene.scene_id: scene}, reviews, motion_media=provider)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Motion inference must not invoke an Agent")

    monkeypatch.setattr("amidst.workbench.service.mock_decide", forbidden)
    monkeypatch.setattr("amidst.workbench.service.GuidanceIndex", forbidden)

    class Quiet(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    with make_server("127.0.0.1", 0, Application(workbench, repo), handler_class=Quiet) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        yield f"http://127.0.0.1:{server.server_port}", scene, workbench, provider
        server.shutdown()
        worker.join(timeout=5)
        assert not worker.is_alive()


def post(base, action, payload):
    request = Request(base + "/api/" + action, data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", "Origin": base})
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def get_media(base, common, ref, byte_range=None, **extra):
    query = urlencode(common | {"ref": ref} | extra)
    headers = {"Range": byte_range} if byte_range is not None else {}
    request = Request(base + "/api/motion_media?" + query, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


def context(base, scene):
    _, session = post(base, "session", {"role": "research"})
    return {"session_ref": session["session_ref"], "scene_id": scene.scene_id}


def test_real_http_motion_uses_pixel_projection_index_without_agent(live_motion):
    base, scene, _, _ = live_motion
    common = context(base, scene)
    query = common | {"camera_ids": ["CAM_A", "CAM_B"], "start": 0, "end": 9.8}
    status, result = post(base, "motion_reconstruction", query)
    assert status == 200
    assert result["schema_version"] == "workbench.blender-motion.v1"
    assert result["agent_used"] is False
    assert post(base, "motion_reconstruction", query) == (200, result)
    assert result["scope"]["scene_id"] == scene.scene_id
    assert result["artifacts"]["status"] == "AVAILABLE"
    assert result["tracks"]
    for track in result["tracks"]:
        assert track["camera_id"] in {"CAM_A", "CAM_B"}
        assert all(sample["state"] in {"PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION", "MISSING"}
                   for sample in track["samples"])
        assert all(speed["state"] == "INFERRED_FINITE_DIFFERENCE"
                   for speed in track["velocities"])
    raw = json.dumps(result, allow_nan=False)
    for forbidden in ("/private/", "local_path", "TrajectoryID", "ground_truth", "DO_NOT_",
                      "SIMULATION_RECIPE"):
        assert forbidden not in raw


def test_real_http_motion_role_camera_window_and_extra_fields_are_denied(live_motion):
    base, scene, _, _ = live_motion
    common = context(base, scene)
    query = common | {"camera_ids": ["CAM_A"], "start": 0, "end": 9.8}
    _, manager = post(base, "session", {"role": "management"})
    manager_query = query | {"session_ref": manager["session_ref"]}
    assert post(base, "motion_reconstruction", manager_query)[0] == 403
    assert post(base, "motion_reconstruction", query | {"scene_id": "other-site"})[0] == 403
    for extra in [
        {"camera_ids": ["CAM_A", "CAM_A"]}, {"camera_ids": ["OTHER"]},
        {"start": 1, "end": 0}, {"end": 11}, {"start": -1},
        {"start": True}, {"end": "9.8"}, {"end": float("nan")}, {"end": float("inf")},
        {"local_path": "/private/forbidden.mp4"}, {"ground_truth": {"position": [9, 9, 9]}},
        {"max_speed_m_s": 999},
    ]:
        assert post(base, "motion_reconstruction", query | extra)[0] == 400


def test_real_http_video_ranges_and_session_media_issuance(live_motion):
    base, scene, _, provider = live_motion
    common = context(base, scene)
    assert get_media(base, common, provider.video_ref)[0] == 403
    assert post(base, "motion_reconstruction", common | {
        "camera_ids": ["CAM_A"], "start": 0, "end": 1})[0] == 200
    status, headers, body = get_media(base, common, provider.video_ref)
    assert status == 200 and body == provider.video and headers["Accept-Ranges"] == "bytes"
    for value, expected, first, last in [
        ("bytes=0-31", provider.video[:32], 0, 31),
        ("bytes=700-", provider.video[700:], 700, 767),
        ("bytes=-16", provider.video[-16:], 752, 767),
        ("bytes=700-99999", provider.video[700:], 700, 767),
    ]:
        status, headers, body = get_media(base, common, provider.video_ref, value)
        assert status == 206 and body == expected
        assert headers["Content-Range"] == f"bytes {first}-{last}/768"
    for value in ["bytes=768-", "bytes=50-49", "bytes=-0", "bytes=", "bytes=0-1,3-4"]:
        status, headers, _ = get_media(base, common, provider.video_ref, value)
        assert status == 416 and headers["Content-Range"] == "bytes */768"
    assert get_media(base, context(base, scene), provider.video_ref)[0] == 403
    assert get_media(base, common | {"scene_id": "other-site"}, provider.video_ref)[0] == 403
    assert get_media(base, common, provider.video_ref, local_path="/private/bad")[0] == 400
    assert get_media(base, common, provider.curve_ref)[0] == 200
    assert get_media(base, common, provider.curve_ref, "bytes=0-1")[0] == 403


def test_real_http_stale_safe_input_rejects_motion_and_replay(live_motion):
    base, scene, _, provider = live_motion
    common = context(base, scene)
    query = common | {"camera_ids": ["CAM_A"], "start": 0, "end": 1}
    assert post(base, "motion_reconstruction", query)[0] == 200
    p = scene.root / "safe_inputs.json"
    p.write_bytes(p.read_bytes() + b" ")
    assert post(base, "motion_reconstruction", query)[0] == 400
    assert get_media(base, common, provider.video_ref)[0] == 400


def test_unmaterialized_replay_does_not_block_live_curves(live_motion):
    base, scene, workbench, _ = live_motion
    workbench.motion_media_provider = None
    common = context(base, scene)
    status, result = post(base, "motion_reconstruction", common | {
        "camera_ids": ["CAM_A"], "start": 0, "end": 1})
    assert status == 200 and result["tracks"]
    assert result["artifacts"] == {
        "status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED"}


def test_invalid_optional_video_keeps_curves_and_revokes_old_media(live_motion, monkeypatch):
    base, scene, _, provider = live_motion
    common = context(base, scene)
    query = common | {"camera_ids": ["CAM_A"], "start": 0, "end": 1}
    assert post(base, "motion_reconstruction", query)[0] == 200
    assert get_media(base, common, provider.video_ref)[0] == 200

    def stale(_scene):
        raise ValueError("/private/sensitive/location/invalid manifest")

    monkeypatch.setattr(provider, "manifest", stale)
    status, result = post(base, "motion_reconstruction", query)
    assert status == 200 and result["tracks"]
    assert result["artifacts"] == {"status": "UNAVAILABLE", "items": [],
                                    "reason": "INVALID_OR_STALE_ARTIFACT"}
    assert "/private/" not in json.dumps(result)
    assert get_media(base, common, provider.video_ref)[0] == 403

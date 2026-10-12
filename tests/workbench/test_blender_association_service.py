"""Real HTTP boundaries for scoped cross-camera candidates and replay bytes.

The transport fixture is deliberately not an encoded video. Real encoding and
full decode are covered independently by association-media tests/materialization.
"""

import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest
from test_blender_motion_service import post
from test_blender_scene import bundle as bundle

from amidst.workbench.blender_scene import load_blender_scene
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Workbench


class IssuedAssociationArtifacts:
    """Fixed binary bytes isolate range/session logic from the actual encoder."""

    video_ref = "cross-media:" + "c" * 24
    curve_ref = "cross-media:" + "d" * 24
    video = bytes(range(256)) * 4

    def manifest(self, scene):
        scene.live_scope()
        return {"status": "AVAILABLE", "selection": {
            "camera_ids": ["CAM_A", "CAM_B"], "time_range": [0, 9.8], "top_k": 3},
            "items": [
                {"media_ref": self.video_ref, "kind": "CROSS_CAMERA_RECONSTRUCTION_VIDEO",
                 "mime_type": "video/mp4", "time_range": [0, 9.8],
                 "duration_s": 10, "frame_count": 50},
                {"media_ref": self.curve_ref, "kind": "ASSOCIATION_POSITION_VELOCITY_CURVES",
                 "mime_type": "image/png", "time_range": [0, 9.8]},
            ]}

    def media(self, scene, ref):
        scene.live_scope()
        if ref == self.video_ref:
            return "video/mp4", self.video
        if ref == self.curve_ref:
            return scene.media(scene.index.frame_records[0]["frame_ref"])
        raise ValueError("UNREGISTERED_ARTIFACT")


@pytest.fixture
def live_association(bundle, monkeypatch):
    root, _, repo = bundle
    scene = load_blender_scene(root)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(repo / "association-transport.sqlite3", {
        scene.scene_id: {k: scene.snapshot()[k] for k in keys}})
    provider = IssuedAssociationArtifacts()
    workbench = Workbench({scene.scene_id: scene}, reviews, association_media=provider)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Cross-camera reconstruction must not invoke an Agent")

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


def context(base, scene, role="research"):
    _, session = post(base, "session", {"role": role})
    return {"session_ref": session["session_ref"], "scene_id": scene.scene_id}


def media(base, common, ref, byte_range=None, **extra):
    query = urlencode(common | {"ref": ref} | extra)
    headers = {"Range": byte_range} if byte_range is not None else {}
    request = Request(base + "/api/cross_camera_media?" + query, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


def full_query(common):
    return common | {"camera_ids": ["CAM_A", "CAM_B"], "start": 0, "end": 9.8, "top_k": 3}


def test_actual_http_candidates_preserve_projection_constraints_and_no_agent(live_association):
    base, scene, _, _ = live_association
    query = full_query(context(base, scene))
    status, result = post(base, "cross_camera_reconstruction", query)
    assert status == 200
    assert result["schema_version"] == "workbench.blender-association.v1"
    assert result["scope"]["scene_id"] == scene.scene_id
    assert result["agent_used"] is False
    assert result["artifacts"]["status"] == "AVAILABLE"
    assert post(base, "cross_camera_reconstruction", query) == (200, result)
    assert 1 <= len(result["candidates"]) <= 3
    assert len({row["candidate_ref"] for row in result["candidates"]}) == len(result["candidates"])
    assert result["baseline_candidate"]["is_unassociated_baseline"] is True
    for candidate in result["candidates"]:
        assert candidate["identity_verdict"] == "UNCONFIRMED"
        for path in candidate["paths"]:
            assert path["geometry_authority"] == "SOURCE_BOUND_FLOOR_ONLY"
            assert all(row["speed_m_s"] <= 8 for row in path["velocities"])
    raw = json.dumps(result, allow_nan=False)
    for forbidden in ("local_path", "/private/", "TrajectoryID", "ground_truth", "DO_NOT_"):
        assert forbidden not in raw


def test_http_role_scope_k_and_numeric_guards(live_association):
    base, scene, _, _ = live_association
    query = full_query(context(base, scene))
    manager = query | context(base, scene, "management")
    assert post(base, "cross_camera_reconstruction", manager)[0] == 403
    assert post(base, "cross_camera_reconstruction", query | {"scene_id": "other-site"})[0] == 403
    for fields in [
        {"top_k": 0}, {"top_k": 6}, {"top_k": True}, {"top_k": "3"},
        {"camera_ids": ["CAM_A", "CAM_A"]}, {"camera_ids": ["OTHER"]},
        {"camera_ids": []}, {"start": -1}, {"start": True}, {"end": "9.8"},
        {"start": 2, "end": 1}, {"end": 11}, {"end": float("nan")},
        {"end": float("inf")}, {"max_speed_m_s": 999},
        {"local_path": "/private/forbidden.mp4"}, {"ground_truth": {"identity": "wrong"}},
    ]:
        assert post(base, "cross_camera_reconstruction", query | fields)[0] == 400


def test_http_camera_window_and_k_do_not_rebuild_canonical_references(live_association):
    base, scene, _, _ = live_association
    query = full_query(context(base, scene))
    _, full = post(base, "cross_camera_reconstruction", query)
    _, narrow = post(base, "cross_camera_reconstruction", query | {
        "start": 2, "end": 4, "top_k": 1})
    assert narrow["selection"] == {"camera_ids": ["CAM_A", "CAM_B"],
                                   "time_range": [2, 4], "top_k": 1}
    assert narrow["association_sha256"] == full["association_sha256"]
    assert narrow["candidates"][0]["candidate_ref"] == full["candidates"][0]["candidate_ref"]
    assert all(2 <= row["timestamp"] <= 4 for path in narrow["candidates"][0]["paths"]
               for row in path["samples"])
    assert narrow["artifacts"]["selection"] == full["artifacts"]["selection"]
    _, single = post(base, "cross_camera_reconstruction", query | {"camera_ids": ["CAM_A"]})
    assert single["status"] == "NO_CROSS_CAMERA_EVIDENCE"
    assert all(path["camera_ids"] == ["CAM_A"] for row in single["candidates"]
               for path in row["paths"])


def test_actual_http_replay_issuance_ranges_and_other_sessions(live_association):
    base, scene, _, provider = live_association
    common = context(base, scene)
    assert media(base, common, provider.video_ref)[0] == 403
    assert post(base, "cross_camera_reconstruction", full_query(common))[0] == 200
    status, headers, body = media(base, common, provider.video_ref)
    assert status == 200 and body == provider.video and headers["Accept-Ranges"] == "bytes"
    for value, first, last in [
        ("bytes=0-31", 0, 31), ("bytes=-16", 1008, 1023),
        ("bytes=1000-", 1000, 1023), ("bytes=1000-999999", 1000, 1023),
    ]:
        status, headers, body = media(base, common, provider.video_ref, value)
        assert status == 206 and body == provider.video[first:last + 1]
        assert headers["Content-Range"] == f"bytes {first}-{last}/1024"
    for value in ["bytes=1024-", "bytes=-0", "bytes=8-7", "bytes=0-1,5-6"]:
        status, headers, _ = media(base, common, provider.video_ref, value)
        assert status == 416 and headers["Content-Range"] == "bytes */1024"
    assert media(base, context(base, scene), provider.video_ref)[0] == 403
    assert media(base, context(base, scene, "management"), provider.video_ref)[0] == 403
    assert media(base, common | {"scene_id": "other-site"}, provider.video_ref)[0] == 403
    assert media(base, common, provider.video_ref, local_path="/private/bad")[0] == 400
    assert media(base, common, provider.curve_ref)[0] == 200
    assert media(base, common, provider.curve_ref, "bytes=0-1")[0] == 403


def test_stale_safe_input_rejects_association_and_preissued_media(live_association):
    base, scene, _, provider = live_association
    common = context(base, scene)
    assert post(base, "cross_camera_reconstruction", full_query(common))[0] == 200
    source = scene.root / "safe_inputs.json"
    source.write_bytes(source.read_bytes() + b" ")
    assert post(base, "cross_camera_reconstruction", full_query(common))[0] == 400
    assert media(base, common, provider.video_ref)[0] == 400


def test_missing_artifact_keeps_real_candidate_data(live_association):
    base, scene, workbench, _ = live_association
    workbench.association_media_provider = None
    status, result = post(base, "cross_camera_reconstruction", full_query(context(base, scene)))
    assert status == 200 and result["candidates"]
    assert result["artifacts"] == {"status": "UNAVAILABLE", "items": [],
                                    "reason": "NOT_MATERIALIZED"}


def test_invalid_optional_artifact_revokes_old_refs_without_private_error(
    live_association, monkeypatch,
):
    base, scene, _, provider = live_association
    common = context(base, scene)
    query = full_query(common)
    assert post(base, "cross_camera_reconstruction", query)[0] == 200
    assert media(base, common, provider.video_ref)[0] == 200

    def stale(_scene):
        raise ValueError("/private/not-publishable/manifest")

    monkeypatch.setattr(provider, "manifest", stale)
    status, result = post(base, "cross_camera_reconstruction", query)
    assert status == 200 and result["candidates"]
    assert result["artifacts"] == {"status": "UNAVAILABLE", "items": [],
                                    "reason": "INVALID_OR_STALE_ARTIFACT"}
    assert "/private/" not in json.dumps(result)
    assert media(base, common, provider.video_ref)[0] == 403

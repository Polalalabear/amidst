"""Real HTTP transport guards with explicitly substitute physical verdicts.

Geometry decisions and actual encoding are tested by the independent physical
source/core/media suites. This fixture never claims source geometry approval.
"""

import copy
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest
from test_blender_motion_service import post
from test_blender_scene import bundle as bundle

from amidst.engineering.registry import content_hash
from amidst.workbench.blender_scene import load_blender_scene
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Workbench


class TransportSource:
    changed = False

    def verify(self):
        if self.changed:
            raise ValueError("/private/substitute/changed-source-must-not-leak")

    def export_safe_inputs(self):
        self.verify()
        return {"data_kind": "SUBSTITUTE", "geometry_authority": "TRANSPORT_FIXTURE_ONLY"}


class TransportPhysicalIndex:
    """Fixed verdict envelope isolates issuing/scope logic from geometry."""

    def __init__(self, base):
        self.base = base
        self.reject_all = False

    def reconstruct(self, cameras, start, end, top_k=3):
        original = self.base.reconstruct(cameras, start, end, top_k)
        rows = copy.deepcopy(original["candidates"])
        for row in rows:
            row["physical"] = {"verdict": "UNKNOWN", "reasons": [
                {"code": "FIXTURE_APERTURE_UNKNOWN", "status": "UNKNOWN",
                 "authority": "SUBSTITUTE_TRANSPORT_ONLY", "time_range": [start, end]}],
                "complete_physical_validation": False}
        rejected = []
        if rows:
            rejected = [copy.deepcopy(rows[0])]
            rejected[0]["candidate_ref"] = "transport-rejected:" + "e" * 24
            rejected[0]["physical"] = {"verdict": "REJECTED", "reasons": [
                {"code": "FIXTURE_NOMINAL_COLLISION", "status": "REJECT",
                 "authority": "SUBSTITUTE_TRANSPORT_ONLY", "time_range": [start, end]}]}
        if self.reject_all:
            rows = []
        return {**original, "schema_version": "workbench.blender-physical.v1",
                "status": "NO_PHYSICAL_CANDIDATE" if self.reject_all else original["status"],
                "physical_sha256": content_hash({"base": original["association_sha256"],
                                                  "fixture": True}),
                "base_association_sha256": original["association_sha256"],
                "candidates": rows, "rejected_candidates": rejected,
                "physical_test_data_kind": "SUBSTITUTE_TRANSPORT_ONLY"}


class TransportMedia:
    curve_ref = "physical-media:" + "a" * 24
    video_ref = "physical-media:" + "b" * 24
    video = bytes(range(256)) * 4
    broken = False

    def manifest(self, scene):
        scene.export_physical_source()
        if self.broken:
            raise ValueError("/private/substitute/stale-artifact-must-not-leak")
        return {"status": "AVAILABLE", "selection": {
            "camera_ids": ["CAM_A", "CAM_B"], "time_range": [0, 9.8], "top_k": 3},
            "items": [
                {"media_ref": self.curve_ref, "mime_type": "image/png",
                 "kind": "PHYSICAL_POSITION_VELOCITY_CURVES"},
                {"media_ref": self.video_ref, "mime_type": "video/mp4",
                 "kind": "PHYSICAL_RECONSTRUCTION_VIDEO"}]}

    def media(self, scene, ref):
        scene.export_physical_source()
        if ref == self.video_ref:
            return "video/mp4", self.video
        if ref == self.curve_ref:
            return scene.media(scene.index.frame_records[0]["frame_ref"])
        raise ValueError("UNREGISTERED_SUBSTITUTE_MEDIA")


@pytest.fixture
def physical_http(bundle, monkeypatch):
    root, _, repo = bundle
    scene = load_blender_scene(root)
    source, provider = TransportSource(), TransportMedia()
    scene._physical_source = source
    scene.physical = TransportPhysicalIndex(scene.association)
    scene._snapshot["capabilities"]["physical_cross_camera_reconstruction"] = True
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    store = ReviewStore(repo / "physical-transport.sqlite3", {
        scene.scene_id: {k: scene.snapshot()[k] for k in keys}})
    bench = Workbench({scene.scene_id: scene}, store, physical_media=provider)

    def forbidden(*args, **kwargs):
        raise AssertionError("Physical reconstruction must not invoke an Agent")

    monkeypatch.setattr("amidst.workbench.service.mock_decide", forbidden)
    monkeypatch.setattr("amidst.workbench.service.GuidanceIndex", forbidden)

    class Quiet(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    with make_server("127.0.0.1", 0, Application(bench, repo), handler_class=Quiet) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        _, session = post(f"http://127.0.0.1:{server.server_port}", "session", {"role": "research"})
        query = {"session_ref": session["session_ref"], "scene_id": scene.scene_id,
                 "camera_ids": ["CAM_A", "CAM_B"], "start": 0, "end": 9.8, "top_k": 3}
        yield f"http://127.0.0.1:{server.server_port}", query, scene, source, provider, bench
        server.shutdown()
        worker.join(timeout=5)
        assert not worker.is_alive()


def get_media(base, query, ref, byte_range=None, route="physical_cross_camera_media", **extra):
    common = {k: query[k] for k in ("session_ref", "scene_id")}
    headers = {"Range": byte_range} if byte_range is not None else {}
    request = Request(base + "/api/" + route + "?" + urlencode(common | {"ref": ref} | extra),
                      headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


def test_physical_http_preserves_verdicts_and_original_observations(physical_http):
    base, query, scene, _, _, bench = physical_http
    before = content_hash(scene.index.snapshot())
    status, result = post(base, "physical_cross_camera_reconstruction", query)
    assert status == 200 and result["schema_version"] == "workbench.blender-physical.v1"
    assert result["agent_used"] is False and result["formal_acceptance"] is False
    assert all(c["physical"]["verdict"] == "UNKNOWN" for c in result["candidates"])
    assert result["rejected_candidates"][0]["physical"]["reasons"][0]["status"] == "REJECT"
    assert result["baseline_candidate"]["is_unassociated_baseline"] is True
    assert post(base, "physical_cross_camera_reconstruction", query) == (200, result)
    assert content_hash(scene.index.snapshot()) == before
    logs = bench.sessions[query["session_ref"]].logs
    assert any(row["action"] == "physical_candidate" and row["status"] == "UNKNOWN" for row in logs)
    assert any(row["action"] == "physical_candidate" and row["status"] == "REJECTED"
               for row in logs)


def test_physical_http_is_research_scoped_and_forbids_caller_authority_and_budgets(physical_http):
    base, query, scene, _, _, _ = physical_http
    _, manager = post(base, "session", {"role": "management"})
    assert post(base, "physical_cross_camera_reconstruction", query | {
        "session_ref": manager["session_ref"]})[0] == 403
    assert post(base, "physical_cross_camera_reconstruction", query | {
        "scene_id": "other"})[0] == 403
    for fields in ({"colliders": []}, {"policy": {"body_radius_m": 0}}, {"ground_truth": {}},
                   {"local_path": "/private/forbidden"}, {"top_k": True}, {"top_k": 6},
                   {"end": float("inf")}, {"end": float("nan")}, {"end": 11},
                   {"camera_ids": ["CAM_A", "CAM_A"]}, {"camera_ids": ["OTHER"]}):
        assert post(base, "physical_cross_camera_reconstruction", query | fields)[0] == 400
    scene._snapshot["capabilities"]["physical_cross_camera_reconstruction"] = False
    assert post(base, "physical_cross_camera_reconstruction", query)[0] == 403


def test_physical_media_issuing_namespace_range_and_cross_session_guards(physical_http):
    base, query, _, _, provider, _ = physical_http
    assert get_media(base, query, provider.video_ref)[0] == 403
    post(base, "physical_cross_camera_reconstruction", query)
    assert get_media(base, query, provider.video_ref)[2] == provider.video
    status, headers, raw = get_media(base, query, provider.video_ref, "bytes=10-19")
    assert status == 206 and raw == provider.video[10:20]
    assert headers["Content-Range"] == "bytes 10-19/1024"
    assert get_media(base, query, provider.video_ref, "bytes=-10")[2] == provider.video[-10:]
    assert get_media(base, query, provider.video_ref, "bytes=9999-")[0] == 416
    assert get_media(base, query, provider.curve_ref)[0] == 200
    assert get_media(base, query, provider.curve_ref, "bytes=0-10")[0] == 403
    assert get_media(base, query, provider.video_ref, route="cross_camera_media")[0] == 403
    assert get_media(base, query, "cross-media:" + "b" * 24)[0] == 403
    assert get_media(base, query, provider.video_ref, caller_path="forbidden")[0] == 400
    _, other = post(base, "session", {"role": "research"})
    assert get_media(base, query | {"session_ref": other["session_ref"]},
                     provider.video_ref)[0] == 403
    assert get_media(base, query | {"scene_id": "other"}, provider.video_ref)[0] == 403


def test_stale_source_rejects_query_and_issued_media_without_private_error(physical_http):
    base, query, _, source, provider, _ = physical_http
    post(base, "physical_cross_camera_reconstruction", query)
    source.changed = True
    status, result = post(base, "physical_cross_camera_reconstruction", query)
    assert status == 400 and "/private/" not in str(result)
    status, _, raw = get_media(base, query, provider.video_ref)
    assert status == 400 and b"/private/" not in raw


def test_optional_stale_media_keeps_reasons_and_revokes_old_refs(physical_http):
    base, query, _, _, provider, _ = physical_http
    post(base, "physical_cross_camera_reconstruction", query)
    provider.broken = True
    status, result = post(base, "physical_cross_camera_reconstruction", query)
    assert status == 200 and result["candidates"]
    assert result["artifacts"] == {"status": "UNAVAILABLE", "items": [],
                                    "reason": "INVALID_OR_STALE_ARTIFACT"}
    assert result["candidates"][0]["physical"]["verdict"] == "UNKNOWN"
    assert get_media(base, query, provider.video_ref)[0] == 403


def test_zero_retained_keeps_rejection_and_baseline_without_fabricated_top_k(physical_http):
    base, query, scene, _, _, _ = physical_http
    scene.physical.reject_all = True
    status, result = post(base, "physical_cross_camera_reconstruction", query)
    assert status == 200 and result["candidates"] == []
    assert result["status"] == "NO_PHYSICAL_CANDIDATE"
    assert result["rejected_candidates"] and result["baseline_candidate"]

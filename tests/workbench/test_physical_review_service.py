"""SUBSTITUTE checklist transport with real indexed source-frame fixtures.

These checks never make an actual Blender human confirmation or rerun media.
"""

import copy
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest
from test_blender_motion_service import post
from test_blender_scene import bundle as bundle

from amidst.engineering.registry import content_hash
from amidst.workbench.blender_scene import load_blender_scene
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Workbench

REVIEW = "d" * 64
ITEM = "physical-review-fixture:" + "a" * 24
CHECK = "physical-review-check:" + "b" * 24


class SubstituteReviewIndex:
    stale = False
    review_sha256 = REVIEW

    def __init__(self, scene):
        self.scene = scene

    def snapshot(self, cameras, start, end):
        if self.stale:
            raise ValueError("/private/substitute/evidence-stale")
        self.scene.index._validate_cameras(cameras)
        if not 0 <= start <= end <= 9.8:
            raise ValueError("INVALID_REVIEW_TIME")
        return {"schema_version": "workbench.blender-physical-review.v1",
                "review_sha256": REVIEW, "selection": {
                    "camera_ids": cameras, "time_range": [start, end]},
                "items": [{"item_ref": ITEM, "status": "UNKNOWN", "data_kind": "SUBSTITUTE",
                           "checklist": [{"check_ref": CHECK, "status": "UNKNOWN"}]}],
                "formal_acceptance": False, "authority_changed": False,
                "rerun_authorized": False}


@pytest.fixture
def review_http(bundle, monkeypatch):
    root, _, repo = bundle
    scene = load_blender_scene(root)
    source = SubstituteReviewIndex(scene)
    scene._snapshot["capabilities"].update({"physical_review": True, "camera_frame_wall": True})

    def index():
        if source.stale:
            raise ValueError("/private/substitute/source-stale")
        return source

    monkeypatch.setattr(scene, "physical_review_index", index)

    def normalize(index, value):
        assert index is source
        if value["review_sha256"] != REVIEW or value["item_ref"] != ITEM:
            raise ValueError("SUBSTITUTE_REFERENCE_INVALID")
        if any(set(row) != {"check_ref", "decision", "evidence_refs", "comment"}
               or row["check_ref"] != CHECK for row in value["checks"]):
            raise ValueError("SUBSTITUTE_CHECK_INVALID")
        result = {**copy.deepcopy(value), "source_authority_changed": False,
                  "rerun_authorized": False, "formal_approval": False,
                  "prior_results_changed": False, "status": "LOCALLY_REVIEWED",
                  "scope": "LOCAL_ENGINEERING_REVIEW_ONLY", "source_binding": {
                      "site_id": "SUBSTITUTE"}, "remaining_check_refs": [],
                  "schema_version": "workbench.blender-physical-review-decision.v1"}
        for check in result["checks"]:
            check["previous_decision"] = "UNKNOWN"
        result["decision_sha256"] = content_hash(result)
        return result

    monkeypatch.setattr(
        "amidst.workbench.blender_physical_review.validate_review_decision", normalize)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    store = ReviewStore(repo / "review-transport.sqlite3", {
        scene.scene_id: {k: scene.snapshot()[k] for k in keys}})
    bench = Workbench({scene.scene_id: scene}, store)

    def forbidden(*args, **kwargs):
        raise AssertionError("Preparing human review must not rerank/encode or call an Agent")

    monkeypatch.setattr(scene, "physical_cross_camera_reconstruction", forbidden)
    monkeypatch.setattr("amidst.workbench.service.mock_decide", forbidden)

    class Quiet(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    application = Application(bench, repo)
    application.frontend = Path(__file__).resolve().parents[2] / "frontend/workbench"
    with make_server("127.0.0.1", 0, application, handler_class=Quiet) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        _, session = post(base, "session", {"role": "research"})
        query = {"session_ref": session["session_ref"], "scene_id": scene.scene_id,
                 "camera_ids": ["CAM_A", "CAM_B"], "start": 0, "end": 9.8}
        yield base, query, scene, source, bench
        server.shutdown()
        thread.join(timeout=5)
        assert not thread.is_alive()


def human_payload(query):
    return {k: query[k] for k in ("session_ref", "scene_id")} | {
        "review_sha256": REVIEW, "item_ref": ITEM, "expected_revision": 0,
        "reviewer": "SUBSTITUTE tester", "reason": "SUBSTITUTE checklist transport only",
        "checks": [{"check_ref": CHECK, "decision": "CONFIRMED_LOCAL",
                    "evidence_refs": ["SUBSTITUTE_EVIDENCE"], "comment": "fixture only"}]}


def test_pending_review_never_reranks_or_encodes_and_does_not_confirm(review_http):
    base, query, _, _, bench = review_http
    status, result = post(base, "physical_review", query)
    assert status == 200
    assert result["items"][0]["status"] == "UNKNOWN"
    assert result["review_state"]["revision"] == 0
    assert result["baseline_results_unchanged"] is True
    assert result["post_confirmation_rerun_performed"] is False
    assert bench.physical_review_store.state(query["scene_id"], REVIEW)["revision"] == 0


def test_human_delta_is_issued_scoped_append_only_and_exported_as_delta(review_http):
    base, query, _, _, _ = review_http
    body = human_payload(query)
    assert post(base, "physical_review_decision", body)[0] == 403
    post(base, "physical_review", query)
    status, result = post(base, "physical_review_decision", body)
    assert status == 200 and result["record"]["revision"] == 1
    assert result["authority_changed"] is False and result["rerun_authorized"] is False
    assert result["post_confirmation_rerun_performed"] is False
    assert post(base, "physical_review_decision", body)[0] == 400
    export = {k: query[k] for k in ("session_ref", "scene_id")} | {
        "review_sha256": REVIEW, "revision": 1}
    status, delta = post(base, "physical_review_delta", export)
    assert status == 200 and delta["delta"] == result["record"]
    assert "items" not in delta["delta"] and "geometry" not in delta["delta"]
    _, second = post(base, "session", {"role": "research"})
    assert post(base, "physical_review_decision", body | {
        "session_ref": second["session_ref"], "expected_revision": 1})[0] == 403


def test_review_role_input_source_and_item_guards(review_http):
    base, query, _, source, _ = review_http
    _, manager = post(base, "session", {"role": "management"})
    assert post(base, "physical_review", query | {"session_ref": manager["session_ref"]})[0] == 403
    for fields in ({"geometry": []}, {"gt": {}}, {"start": True},
                   {"camera_ids": ["CAM_A", "CAM_A"]}, {"end": 10.1}):
        assert post(base, "physical_review", query | fields)[0] == 400
    post(base, "physical_review", query)
    body = human_payload(query)
    assert post(base, "physical_review_decision", body | {
        "item_ref": "other-review-item"})[0] == 403
    assert post(base, "physical_review_decision", body | {"policy": {}})[0] == 400
    assert post(base, "physical_review_decision", body | {"expected_revision": True})[0] == 400
    source.stale = True
    status, result = post(base, "physical_review_decision", body)
    assert status == 400 and "/private/" not in str(result)


def test_temporal_wall_uses_existing_indexed_frames_without_extra_cameras(review_http):
    base, query, _, _, _ = review_http
    for count in (8, 12, 16):
        status, wall = post(base, "camera_frame_wall", query | {"slot_count": count})
        assert status == 200 and len(wall["frames"]) == count
        assert wall["source_camera_count"] == 2 and wall["temporal_mosaic"] is True
        assert [row["slot_index"] for row in wall["frames"]] == list(range(count))
        assert {row["camera_id"] for row in wall["frames"]} == {"CAM_A", "CAM_B"}
        assert wall["retrieval"]["frame_records_read"] == count
        assert wall["retrieval"]["source_rgb_scan"] is False
        assert wall["retrieval"]["global_scan"] is False
    status, wall = post(base, "camera_frame_wall", query | {
        "start": 0, "end": 0, "slot_count": 8})
    assert status == 200 and wall["unique_source_frames"] == 2
    assert sum(row["repeated_source_frame"] for row in wall["frames"]) == 6


def test_wall_role_time_camera_count_and_input_budget_guards(review_http):
    base, query, _, _, _ = review_http
    _, manager = post(base, "session", {"role": "management"})
    assert post(base, "camera_frame_wall", query | {
        "session_ref": manager["session_ref"], "slot_count": 8})[0] == 403
    for fields in ({"slot_count": 10}, {"slot_count": 17}, {"slot_count": True},
                   {"camera_ids": ["UNKNOWN"]}, {"camera_ids": ["CAM_A", "CAM_A"]},
                   {"start": 3, "end": 2}, {"end": 10}, {"gt": []}, {"timestamps": []}):
        assert post(base, "camera_frame_wall", query | fields)[0] == 400


def test_physical_review_module_is_served_as_same_origin_asset(review_http):
    base, _, _, _, _ = review_http
    request = Request(base + "/physical-review.mjs")
    try:
        with urlopen(request, timeout=10) as response:
            assert response.status == 200 and "javascript" in response.headers["Content-Type"]
    except HTTPError as error:
        pytest.fail(f"Physical review asset unavailable: {error.code}")

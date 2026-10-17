"""C4b real person API plus bounded source, endpoint, pruning and role guards."""

import copy
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import office_demo_backend as backend
import pytest
from pydantic import ValidationError
from shapely.geometry import box

from amidst.blind_hypothesis import FloorMapDescriptor, PolygonFloorMap, verify_output_sha256
from amidst.engineering.registry import content_hash
from amidst.workbench.blind_hypothesis_integration import (
    BlindHypothesisIntegration,
    bind_hypotheses,
)
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scene_errors import DataIntegrityError
from amidst.workbench.service import Application, Denied, TargetReconstructionRequest, Workbench

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "configs/office_demo_office_person_fixture_v1.json"
BINDING = "configs/office_person_hypothesis_binding_v1.json"


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    if not os.environ.get("OFFICE_TEST_ASSETS"):
        pytest.skip("OFFICE_TEST_ASSETS is required for real person integration")
    assets = Path(os.environ["OFFICE_TEST_ASSETS"])
    fixture = json.loads(FIXTURE.read_text())
    scene = backend.load_scene(
        assets / "data/engineering/office_person_20261016_v1/office",
        fixture,
        perception_version="rgb-mask-contact-v2",
    ).with_display_identity(fixture["scene_id"], "Office person", "source-bound person run")
    bind_hypotheses(scene, FIXTURE, REPO, BINDING)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(
        tmp_path_factory.mktemp("c4b") / "review.db",
        {scene.scene_id: {k: scene.snapshot()[k] for k in keys}},
    )
    workbench = Workbench({scene.scene_id: scene}, reviews)
    token = workbench.session({"role": "research"})["session_ref"]
    request = {
        "session_ref": token,
        "scene_id": scene.scene_id,
        "camera_ids": fixture["camera_ids"],
        "start": 0.0,
        "end": 9.8,
        "top_k": 3,
        "observation_ref": fixture["observation_ref"],
    }
    return scene, workbench, request


def test_real_person_additive_api_ready_without_filling_missing(live):
    scene, workbench, request = live
    original = copy.deepcopy(scene.index.observations)
    result = workbench.call("target_reconstruction", request)
    response = result["blind_hypotheses"]
    assert result["status"] == "UNKNOWN" and result["reason"] == "SELECTED_PROJECTION_UNAVAILABLE"
    assert result["selected_observation"].get("world_position") is None
    assert response["status"] == "READY" and len(response["hypotheses"]) == 3
    assert verify_output_sha256(response)
    assert response == workbench.call("target_reconstruction", request)["blind_hypotheses"]
    assert response["interval"]["start_s"] == 4.6 and response["interval"]["end_s"] == 8.2
    assert [r["timestamp_s"] for r in response["reachable_regions"]] == [
        round(4.8 + i * 0.2, 1) for i in range(17)
    ]
    assert response["endpoint_substitutions"] == []
    assert response["provenance"]["floor_map_kind"] == "SOURCE_DERIVED"
    assert response["provenance"]["run_ref"] == scene.run_id
    assert response["provenance"]["gt_read"] is False
    assert response["negative_evidence_applied"] == []
    assert (
        response["identity_verdict"] == "UNCONFIRMED"
        and response["physical_authority"] == "UNKNOWN"
    )
    assert all(h["checks"]["unseen"]["result"] == "UNKNOWN" for h in response["hypotheses"])
    review = result["review_evidence"]
    assert review["output_sha256"] == content_hash(
        {k: v for k, v in review.items() if k != "output_sha256"}
    )
    assert review["hypothesis_response_sha256"] == response["output_sha256"]
    assert review["missing_positions_filled"] is False
    assert all(r["world_position"] is None for r in review["source_observations"])
    assert (
        review["endpoints"][0]["ground_estimate"]["constraints_applied"][1]["effect"]
        == "NOT_APPLICABLE"
    )
    assert result["pruning_convergence"]["chain_verified"] is True
    assert scene.index.observations == original


@pytest.mark.parametrize("change", ["old_start", "window", "camera", "unregistered_evidence"])
def test_d18_request_scope_and_unregistered_evidence_fail_closed(live, change):
    _, workbench, request = live
    value = copy.deepcopy(request)
    if change == "old_start":
        value["observation_ref"] = "observation:a9373842c11b3e81fdecf2a8"
    elif change == "window":
        value["end"] = 8.0
    elif change == "camera":
        value["camera_ids"] = value["camera_ids"][:1]
    else:
        value["negative_evidence_refs"] = ["negative:unregistered"]
    result = workbench.call("target_reconstruction", value)["blind_hypotheses"]
    assert result["status"] == "UNKNOWN" and result["hypotheses"] == []
    assert result["reachable_regions"] == [] and verify_output_sha256(result)
    assert result["reason"] == (
        "NEGATIVE_EVIDENCE_UNAVAILABLE"
        if change == "unregistered_evidence"
        else "D18_ENDPOINT_SCOPE_MISMATCH"
    )


def test_k5_previous_response_resolves_only_in_same_session(live):
    _, workbench, request = live
    initial = workbench.call("target_reconstruction", request)["blind_hypotheses"]
    value = request | {"previous_response_sha256": initial["output_sha256"]}
    rerun = workbench.call("target_reconstruction", value)
    assert rerun["blind_hypotheses"]["status"] == "READY"
    assert rerun["blind_hypotheses"]["pruned_hypotheses"] == []
    assert rerun["pruning_convergence"]["chain_verified"] is True
    other = workbench.session({"role": "research"})["session_ref"]
    missing = workbench.call("target_reconstruction", value | {"session_ref": other})[
        "blind_hypotheses"
    ]
    assert (
        missing["status"] == "UNKNOWN" and missing["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    )
    assert any(t.get("problem") == "PREVIOUS_RESPONSE_MISSING" for t in missing["trace"])


@pytest.mark.parametrize(
    "change", ["D17", "D8", "hash", "clock", "missing_estimate", "missing_map", "missing_config"]
)
def test_inputs_fail_closed_without_substitution(live, monkeypatch, change):
    scene, workbench, request = live
    integration = scene._blind_hypothesis
    ref = request["observation_ref"]
    estimates = copy.deepcopy(scene._ground_estimates)
    if change == "missing_map":
        monkeypatch.setattr(integration, "floor_map", None)
    elif change == "missing_config":
        monkeypatch.setattr(integration, "config", {})
    elif change == "missing_estimate":
        estimates.pop(ref)
    else:
        g = estimates[ref]
        if change == "D17":
            g["constraints_applied"][1]["effect"] = "CLIPPED"
        elif change == "D8":
            g["contact_quality"]["reasons"].append("AMBIGUOUS_MERGE")
        elif change == "clock":
            g["provenance"]["clock_id"] = "wrong"
        else:
            g["segment"]["near_m"][0] += 1
        if change != "hash":
            g["output_sha256"] = content_hash({k: v for k, v in g.items() if k != "output_sha256"})
    monkeypatch.setattr(scene, "_ground_estimates", estimates)
    result = workbench.call("target_reconstruction", request)["blind_hypotheses"]
    assert result["status"] == "UNKNOWN" and result["hypotheses"] == []
    assert result["endpoint_substitutions"] == [] and verify_output_sha256(result)


def test_server_resolves_source_map_pins(live, monkeypatch, tmp_path):
    scene, _, _ = live
    import amidst.workbench.blind_hypothesis_integration as integration

    original = integration._pinned

    def tamper(repo, relative, expected):
        value = original(repo, relative, expected)
        if relative.endswith("C7_OFFICE_SOURCE_MAP_20261017.json"):
            value["variants"]["person"]["parameters"]["body_radius_m"] = 0.1482
        return value

    monkeypatch.setattr(integration, "_pinned", tamper)
    with pytest.raises(DataIntegrityError):
        bind_hypotheses(scene, FIXTURE, REPO, BINDING)
    with pytest.raises(DataIntegrityError, match="HASH_MISMATCH"):
        original(REPO, str(FIXTURE.relative_to(REPO)), "0" * 64)


def test_role_session_and_client_override_guards(live):
    _, workbench, request = live
    token = workbench.session({"role": "management"})["session_ref"]
    with pytest.raises(Denied):
        workbench.call("target_reconstruction", request | {"session_ref": token})
    with pytest.raises(Denied):
        workbench.call("target_reconstruction", request | {"scene_id": "other-run"})
    for field in ("ground_estimate", "floor_map", "speed_range_m_s", "gt", "negative_evidence"):
        with pytest.raises(ValidationError):
            workbench.call("target_reconstruction", request | {field: {}})
    assert len(workbench.sessions[request["session_ref"]].blind_responses[request["scene_id"]]) <= 8


def test_wsgi_json_transport_preserves_sealed_additive_payload(live):
    _, workbench, request = live
    raw = json.dumps(request).encode()
    app = Application(workbench, REPO)
    mime, data = app._dispatch(
        {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/target_reconstruction",
            "HTTP_HOST": "127.0.0.1:12345",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(raw)),
            "HTTP_ORIGIN": "http://127.0.0.1:12345",
            "wsgi.input": io.BytesIO(raw),
        }
    )
    assert mime.startswith("application/json")
    assert verify_output_sha256(json.loads(data)["blind_hypotheses"])


def test_k5_new_negative_evidence_prunes_only_synthetic_fixture():
    # This room, points and camera evidence are TEST ONLY; never attached to a real run.
    source = {
        "run_ref": "run:synthetic",
        "clock_id": "SYNTHETIC_5HZ",
        "source_sha256": "a" * 64,
        "safe_inputs_sha256": "b" * 64,
        "gt_read": False,
    }
    rows, estimates = [], {}
    for suffix, camera, t, x in [("a", "A", 0.0, 1.0), ("b", "B", 6.0, 9.0)]:
        ref = "observation:" + suffix * 24
        rows.append(
            {
                "observation_ref": ref,
                "camera_id": camera,
                "timestamp": t,
                "world_position": [x, 3.0, 0.0],
                "state": "PROJECTED_OBSERVATION",
            }
        )
        g = {
            "schema_version": "office-demo.interval-observation.v1",
            "observation_ref": ref,
            "camera_id": camera,
            "timestamp_s": t,
            "status": "READY",
            "reason": None,
            "estimate_kind": "POINT",
            "basis": "FOOT_POINT",
            "point_m": [x, 3.0, 0.0],
            "segment": None,
            "pixel_sensitivity_m": 0.1,
            "contact_quality": {"status": "PASS", "reasons": []},
            "evidence_state": "PROJECTED_OBSERVATION",
            "provenance": copy.deepcopy(source),
        }
        g["output_sha256"] = content_hash(g)
        estimates[ref] = g
    scene = SimpleNamespace(
        scene_id="synthetic-c4b-test",
        run_id=source["run_ref"],
        source_hash=source["source_sha256"],
        index=SimpleNamespace(observations=rows),
        _ground_estimates=estimates,
    )
    fixture = {
        "blind_interval": {
            "start_observation_ref": rows[0]["observation_ref"],
            "end_observation_ref": rows[1]["observation_ref"],
            "start_s": 0.0,
            "end_s": 6.0,
            "start_camera_id": "A",
            "end_camera_id": "B",
            "interior_time_range_s": [0.2, 5.8],
        }
    }
    config = json.loads((REPO / "configs/blind_hypothesis_v1.json").read_text())
    config["scenes"] = {scene.scene_id: {"time_step_s": 0.2, "body_radius_m": 0.25}}
    binding = {
        "clock_id": source["clock_id"],
        "source_sha256": source["source_sha256"],
        "safe_inputs_sha256": source["safe_inputs_sha256"],
        "config_sha256": content_hash(config),
        "cooperative_deadline_s": 5.0,
        "negative_evidence_status": "SYNTHETIC_TEST_ONLY",
    }
    descriptor = FloorMapDescriptor(
        "SYNTHETIC_TEST", "test:map", "0" * 64, "test:walk", "test:portal", "F"
    )
    floor = PolygonFloorMap(
        descriptor, 0.0, {"ROOM": box(0, 0, 10, 6).difference(box(4, 1.5, 6, 4.5))}, {}
    )
    integration = BlindHypothesisIntegration(scene, fixture, binding, config, floor)
    request = TargetReconstructionRequest(
        session_ref="session:synthetic-c4b-test",
        scene_id=scene.scene_id,
        camera_ids=["A", "B"],
        start=0.0,
        end=6.0,
        top_k=3,
        observation_ref=rows[0]["observation_ref"],
    )
    initial = integration.reconstruct(request)["blind_hypotheses"]
    assert initial["status"] == "READY"
    sample = initial["hypotheses"][0]["samples"][len(initial["hypotheses"][0]["samples"]) // 2]
    x, y, _ = sample["position_m"]
    t = sample["timestamp_s"]
    evidence = {
        "negative_evidence_ref": "negative:synthetic",
        "origin": "BLIND_INTERVAL_BASELINE",
        "camera_id": "SYNTHETIC_AUX",
        "frame_refs": [{"frame_ref": "frame:synthetic", "timestamp_s": t}],
        "visibility_ref": "visibility:synthetic",
        "detection_result": "NO_DETECTION",
        "detection_producer": {"producer": "synthetic-test", "version": "v1"},
        "retrieval_query_id": None,
        "visible_floor": {
            "method": "SOURCE_MESH_RAYCAST",
            "polygons": [
                [[x - 0.6, y - 0.6], [x + 0.6, y - 0.6], [x + 0.6, y + 0.6], [x - 0.6, y + 0.6]]
            ],
        },
    }
    evidence["sha256"] = content_hash(evidence)
    integration.negative_evidence[evidence["negative_evidence_ref"]] = evidence
    request = request.model_copy(
        update={
            "negative_evidence_refs": [evidence["negative_evidence_ref"]],
            "previous_response_sha256": initial["output_sha256"],
        }
    )
    rerun = integration.reconstruct(request, initial)
    response = rerun["blind_hypotheses"]
    assert response["status"] == "READY" and verify_output_sha256(response)
    assert initial["hypotheses"][0]["hypothesis_ref"] in {
        h["hypothesis_ref"] for h in response["pruned_hypotheses"]
    }
    assert response["pruning_log"] and rerun["pruning_convergence"]["chain_verified"]
    evidence["detection_result"] = "DETECTION_PRESENT"  # same ref, invalid changed content
    broken = integration.reconstruct(request, initial)["blind_hypotheses"]
    assert broken["status"] == "UNKNOWN" and broken["hypotheses"] == []

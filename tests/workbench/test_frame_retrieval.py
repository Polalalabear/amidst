"""C5 API lookup, strict frame evaluations, provenance and index-bound query work."""

import copy
import hashlib
import io
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_blind_hypothesis_integration import live as live

from amidst.engineering.registry import content_hash
from amidst.workbench.frame_retrieval import FrameRetrievalIndex, TimeFrameIndex
from amidst.workbench.scene_errors import DataIntegrityError
from amidst.workbench.service import Application, Denied


def small():
    records = [
        {"frame_ref": f"frame:{i}", "camera_id": "A", "timestamp_s": round(i * 0.2, 1)}
        for i in range(6)
    ]
    evaluations = {
        r["frame_ref"]: {
            "frame_available": True,
            "rgb_hash_verified": True,
            "provenance_ok": True,
            "perception_evaluated": True,
            "measurement_count": 1 if i == 0 else 0,
            "detection_producer": {
                "producer": "SYNTHETIC",
                "version": "v1",
                "difference_threshold": 30,
                "min_pixels": 28,
            },
        }
        for i, r in enumerate(records)
    }
    entries = [
        {
            "camera_id": "A",
            "visibility_ref": "vis:A",
            "method": "SOURCE_MESH_RAYCAST",
            "floor_z_m": 0.0,
            "visibility_rule": "FOOT_AND_TORSO_PROBES_VISIBLE",
            "negative_evidence_eligible": True,
            "detectability": {
                "min_predicted_px": 200.0,
                "required_px": 112,
                "detectability_factor": 4,
                "detector": {
                    "producer": "SYNTHETIC",
                    "version": "v1",
                    "difference_threshold": 30,
                    "min_pixels": 28,
                },
            },
            "suggestion_polygons": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
            "polygons": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
        }
    ]
    index = FrameRetrievalIndex(
        records,
        evaluations,
        entries,
        index_sha256="a" * 64,
        provenance={"run_ref": "SYNTHETIC", "gt_read": False},
        interval_s=[0.0, 1.0],
    )
    return index, {
        "query_kind": "TIME_RANGE",
        "hypothesis": None,
        "time_range_s": [0.0, 1.0],
        "camera_ids": ["A"],
        "max_frames": 64,
    }


def test_indexed_time_query_truncation_evaluations_and_stable_hash():
    index, query = small()
    result = index.query(query | {"max_frames": 3})
    assert result["status"] == "READY" and result["scan_mode"] == "INDEX"
    assert (
        result["stats"]["frames_matched_total"] == 6
        and result["stats"]["frames_suggested"] == 3
        and result["truncated"]
    )
    assert result["frame_outcomes"][0]["outcome"] == "DETECTION_PRESENT"
    assert result["frame_outcomes"][1]["outcome"] == "NO_DETECTION"
    assert result["output_sha256"] == index.query(query | {"max_frames": 3})["output_sha256"]
    body = copy.deepcopy(result)
    body.pop("output_sha256")
    body["stats"].pop("latency_ms")
    assert result["output_sha256"] == content_hash(body)
    for entry in result["negative_evidence_candidates"]:
        assert entry["sha256"] == content_hash({k: v for k, v in entry.items() if k != "sha256"})
        assert all(0 < f["timestamp_s"] < 1 for f in entry["frame_refs"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("perception_evaluated", False),
        ("provenance_ok", False),
        ("measurement_count", True),
        ("measurement_count", None),
    ],
)
def test_no_detection_is_not_assumed_from_missing_or_malformed_evaluation(field, value):
    index, query = small()
    index.evaluations["frame:1"][field] = value
    result = index.query(query)
    row = next(r for r in result["frame_outcomes"] if r["frame_ref"] == "frame:1")
    assert row["outcome"] == "UNKNOWN" and not row["negative_evidence_eligible"]
    assert not any(
        f["frame_ref"] == "frame:1"
        for e in result["negative_evidence_candidates"]
        for f in e["frame_refs"]
    )


def test_changed_rgb_file_hash_is_fatal_and_missing_file_is_unavailable(tmp_path):
    index, query = small()
    path = tmp_path / "frame.png"
    path.write_bytes(b"original")
    index.paths["frame:1"] = (path, hashlib.sha256(b"original").hexdigest())
    path.write_bytes(b"changed")
    with pytest.raises(DataIntegrityError, match="RGB_HASH_MISMATCH"):
        index.query(query)
    path.unlink()
    result = index.query(query)
    assert (
        result["stats"]["frames_unavailable"] == 1 and result["stats"]["frames_in_scope_total"] == 5
    )


def test_window_lookup_visits_only_bounded_range():
    table = TimeFrameIndex(
        [{"camera_id": "A", "timestamp_s": i * 0.2, "frame_ref": str(i)} for i in range(100000)]
    )
    _, lo, hi = table.window("A", 4.8, 8.0)
    assert hi - lo == 17


def test_actual_api_baseline_feedback_and_session_scope(live):
    scene, workbench, request = live
    initial = workbench.call("target_reconstruction", request)["blind_hypotheses"]
    assert initial["status"] == "READY" and len(initial["negative_evidence_applied"]) == 2
    assert all(
        h["checks"]["unseen"]["result"] == "PASS"
        and h["checks"]["unseen"]["steps_without_negative_evidence"] == 0
        for h in initial["hypotheses"]
    )
    query = {
        "session_ref": request["session_ref"],
        "scene_id": scene.scene_id,
        "query_kind": "TIME_RANGE",
        "time_range_s": [4.8, 8.0],
        "max_frames": 64,
    }
    retrieved = workbench.call("frame_retrieval", query)
    assert retrieved["status"] == "READY" and retrieved["stats"]["frame_records_read"] == 34
    assert len(retrieved["frame_evaluations"]) == 34 and all(
        e["measurement_count"] == 0 for e in retrieved["frame_evaluations"].values()
    )
    assert all(r["outcome"] == "NO_DETECTION" for r in retrieved["frame_outcomes"])
    assert len(retrieved["negative_evidence_candidates"]) == 2
    refs = [e["negative_evidence_ref"] for e in retrieved["negative_evidence_candidates"]]
    feedback = request | {
        "negative_evidence_refs": refs,
        "previous_response_sha256": initial["output_sha256"],
    }
    rerun = workbench.call("target_reconstruction", feedback)
    assert rerun["blind_hypotheses"]["status"] == "READY"
    assert len(rerun["blind_hypotheses"]["negative_evidence_applied"]) == 4
    assert len(rerun["blind_hypotheses"]["pruning_log"]) == 2
    assert rerun["pruning_convergence"]["chain_verified"]
    assert (
        rerun["review_evidence"]["restricted_policy_engine_status"]
        == "AWAITING_CLAUDE_K1_NATIVE_SUPPORT"
    )
    assert all(
        r["state"] == "MISSING" and r["world_position"] is None for r in scene.index.observations
    )
    other = workbench.session({"role": "research"})["session_ref"]
    with pytest.raises(Denied):
        workbench.call("target_reconstruction", feedback | {"session_ref": other})
    for use in ["PATHS", "REACHABLE_REGIONS"]:
        value = query | {
            "query_kind": "HYPOTHESIS",
            "hypothesis": {
                "response_sha256": initial["output_sha256"],
                "hypothesis_refs": [],
                "use": use,
            },
        }
        assert workbench.call("frame_retrieval", value)["status"] == "READY"
    missing = query | {
        "query_kind": "HYPOTHESIS",
        "hypothesis": {"response_sha256": "0" * 64, "hypothesis_refs": [], "use": "PATHS"},
    }
    assert workbench.call("frame_retrieval", missing)["reason"] == "HYPOTHESIS_NOT_FOUND"
    unready = copy.deepcopy(initial)
    unready["status"] = "UNKNOWN"
    unready["output_sha256"] = content_hash(
        {k: v for k, v in unready.items() if k != "output_sha256"}
    )
    assert scene._frame_retrieval.query(missing, unready)["status"] == "UNKNOWN"


def test_actual_api_transport_roles_and_override_rejection(live):
    scene, workbench, request = live
    query = {
        "session_ref": request["session_ref"],
        "scene_id": scene.scene_id,
        "query_kind": "TIME_RANGE",
        "time_range_s": [0.0, 9.8],
        "max_frames": 64,
    }
    result = workbench.call("frame_retrieval", query)
    assert result["truncated"] and result["stats"]["frames_matched_total"] == 100
    assert any(r["outcome"] == "DETECTION_PRESENT" for r in result["frame_outcomes"])
    for key in ["gt", "polygons", "visibility_entries", "file_path"]:
        with pytest.raises(ValidationError):
            workbench.call("frame_retrieval", query | {key: {}})
    management = workbench.session({"role": "management"})["session_ref"]
    with pytest.raises(Denied):
        workbench.call("frame_retrieval", query | {"session_ref": management})
    raw = json.dumps(query).encode()
    app = Application(workbench, Path(__file__).resolve().parents[2])
    mime, data = app._dispatch(
        {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/api/frame_retrieval",
            "HTTP_HOST": "127.0.0.1:1234",
            "HTTP_ORIGIN": "http://127.0.0.1:1234",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(raw)),
            "wsgi.input": io.BytesIO(raw),
        }
    )
    assert (
        mime.startswith("application/json")
        and json.loads(data)["output_sha256"] == result["output_sha256"]
    )


def test_query_budget_and_bad_scope_fail_closed(monkeypatch):
    index, query = small()
    assert index.query(query | {"time_range_s": [-1.0, 1.0]})["reason"] == "TIME_RANGE_INVALID"
    assert index.query(query | {"camera_ids": ["OTHER"]})["status"] == "UNKNOWN"
    import amidst.workbench.frame_retrieval as module

    value = [0.0]

    def clock():
        value[0] += 6.0
        return value[0]

    monkeypatch.setattr(module.time, "monotonic", clock)
    result = index.query(query)
    assert result["status"] == "UNKNOWN" and result["reason"] == "SEARCH_BUDGET_EXHAUSTED"
    assert result["results"] == [] and result["stats"]["frame_records_read"] == 0


def test_missing_index_keeps_unknown_counts_and_sealed_response(live, monkeypatch):
    scene, workbench, request = live
    monkeypatch.delattr(scene, "_frame_retrieval")
    result = workbench.call(
        "frame_retrieval",
        {
            "session_ref": request["session_ref"],
            "scene_id": scene.scene_id,
            "query_kind": "TIME_RANGE",
            "time_range_s": [4.8, 8.0],
            "max_frames": 64,
        },
    )
    assert result["status"] == "UNKNOWN" and result["reason"] == "VISIBILITY_INDEX_UNAVAILABLE"
    assert result["stats"]["frames_in_scope_total"] is None
    assert result["frame_evaluations"] == {} and result["negative_evidence_candidates"] == []
    assert result["output_sha256"]


def test_baseline_and_feedback_are_revalidated_before_k1(live, monkeypatch):
    scene, workbench, request = live
    monkeypatch.setattr(scene._blind_hypothesis, "evidence_validator", lambda entries: False)
    result = workbench.call("target_reconstruction", request)["blind_hypotheses"]
    assert result["status"] == "UNKNOWN" and result["reason"] == "NEGATIVE_EVIDENCE_UNAVAILABLE"
    assert result["hypotheses"] == [] and result["reachable_regions"] == []


@pytest.mark.parametrize(
    "change,reason",
    [
        ("rule", "VISIBILITY_RULE_NOT_ELIGIBLE"),
        ("threshold", "DETECTOR_PARAMETERS_MISMATCH"),
        ("pixels", "DETECTOR_PARAMETERS_MISMATCH"),
        ("producer", "DETECTOR_PARAMETERS_MISMATCH"),
        ("version", "DETECTOR_PARAMETERS_MISMATCH"),
        ("missing_detector", "DETECTOR_PARAMETERS_MISMATCH"),
        ("below_area", "DETECTOR_PARAMETERS_MISMATCH"),
    ],
)
def test_d21_rule_and_detector_fail_closed_without_altering_raw_evaluations(change, reason):
    index, query = small()
    if change == "rule":
        index.entries["A"]["visibility_rule"] = "ANY_PROBE_VISIBLE"
    elif change == "below_area":
        index.entries["A"]["detectability"]["min_predicted_px"] = 111
    else:
        producer = index.evaluations["frame:1"]["detection_producer"]
        key = {
            "threshold": "difference_threshold",
            "pixels": "min_pixels",
            "producer": "producer",
            "version": "version",
            "missing_detector": "min_pixels",
        }[change]
        if change == "missing_detector":
            producer.pop(key)
        else:
            producer[key] = "changed" if key in {"producer", "version"} else producer[key] + 1
    raw = copy.deepcopy(index.evaluations)
    result = index.query(query)
    row = next(r for r in result["frame_outcomes"] if r["frame_ref"] == "frame:1")
    assert row["outcome"] == "UNKNOWN" and row["reason"] == reason
    assert row["negative_evidence_eligible"] is False
    assert not any(
        f["frame_ref"] == "frame:1"
        for e in result["negative_evidence_candidates"]
        for f in e["frame_refs"]
    )
    assert result["frame_evaluations"]["frame:1"] == raw["frame:1"]
    assert index.evaluations == raw


def test_suggestion_polygons_rank_frames_but_never_enter_negative_evidence():
    index, query = small()
    index.entries["A"]["polygons"] = []
    index.visibility_entries["vis:A"]["polygons"] = []
    hypothesis = {
        "status": "READY",
        "interval": {"start_s": 0.0, "end_s": 1.0},
        "configuration": {"body_radius_m": 0.25},
        "endpoint_substitutions": [],
        "hypotheses": [
            {
                "hypothesis_ref": "hyp:test",
                "status": "ACTIVE",
                "samples": [{"timestamp_s": 0.4, "position_m": [1, 1, 0]}],
                "checks": {"walkable": {}},
            }
        ],
    }
    hypothesis["output_sha256"] = content_hash(hypothesis)
    result = index.query(
        query
        | {
            "query_kind": "HYPOTHESIS",
            "hypothesis": {
                "response_sha256": hypothesis["output_sha256"],
                "hypothesis_refs": [],
                "use": "PATHS",
            },
        },
        hypothesis,
    )
    assert result["stats"]["frames_matched_total"] == 1
    assert result["negative_evidence_candidates"]
    assert all(e["visible_floor"]["polygons"] == [] for e in result["negative_evidence_candidates"])


def test_baseline_revalidation_rejects_changed_detector_parameters():
    index, query = small()
    entries = index.baseline_entries()
    assert index.verify_evidence_frames(entries)
    index.evaluations["frame:1"]["detection_producer"]["min_pixels"] += 1
    assert not index.verify_evidence_frames(entries)

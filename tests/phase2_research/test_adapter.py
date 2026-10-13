"""Bounded query, public aggregate certification and frozen metadata refusal."""

from __future__ import annotations

import copy
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering.access import digest
from amidst.phase2_research import pipeline
from amidst.phase2_research.adapter import ResearchService


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ResearchService:
    # A read-only adapter can be exercised without manufacturing research image truth.
    adapter = ResearchService.__new__(ResearchService)
    adapter.output = tmp_path
    adapter.binding = {
        "scene_id": "lab",
        "source_run_id": "run",
        "config_sha256": "c" * 64,
        "dataset_sha256": "d" * 64,
        "freeze_ref": "f" * 64,
    }
    adapter.manifest = {"algorithms": {"known": "a" * 64}}
    monkeypatch.setattr(pipeline, "algorithms", lambda: {"known": "a" * 64})
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(adapter.manifest))
    adapter.integrity_checks = {path: sha256(path.read_bytes()).hexdigest()}
    adapter.integrity_metadata_bytes_read = 0
    adapter.expected_evaluation_sha256 = None
    adapter.cameras = {"C", "D"}
    adapter.rules_denominators = {"projected_measurements": 200}
    adapter.events = {
        f"event:{i}": {
            "event_ref": f"event:{i}",
            "camera_id": "C",
            "time_range": [i, i + 0.1],
            "kind": "REGION_ENTRY",
            "support_state": "UNKNOWN",
            "missing_evidence": ["prior"],
        }
        for i in range(200)
    }
    adapter.associations = [
        {
            "association_ref": "pair:1",
            "camera_ids": ["C", "D"],
            "time_range": [0, 10],
            "identity_confirmed": False,
            "scores_are_probabilities": False,
        }
    ]
    adapter._event_index = adapter._index(list(adapter.events.values()), key="camera_id")
    adapter._association_index = adapter._index(adapter.associations, key="camera_ids")
    return adapter


def certified(service: ResearchService) -> dict[str, Any]:
    evaluation = {
        "manifest_sha256": digest(service.manifest),
        "config_sha256": service.binding["config_sha256"],
        "dataset_sha256": service.binding["dataset_sha256"],
        "metrics": {"false_negative": 4, "unknown": 2, "denominator": 11},
    }
    receipt = {
        "manifest_sha256": digest(service.manifest),
        "evaluation_sha256": digest(evaluation),
        "algorithms": service.manifest["algorithms"],
    }
    (service.output / "evaluation.json").write_text(json.dumps(evaluation))
    (service.output / "evaluation_receipt.json").write_text(json.dumps(receipt))
    service.expected_evaluation_sha256 = digest(evaluation)
    return evaluation


def test_query_is_camera_time_bounded_and_reports_truncation(service: ResearchService) -> None:
    result = service.query("lab", "run", "C", 0, 100)
    assert len(result["events"]) == 64
    assert result["retrieval"]["event_records_read"] == 65
    assert result["retrieval"]["truncated"] is True
    assert result["retrieval"]["global_scan"] is False
    assert result["events"][0]["support_state"] == "UNKNOWN"
    assert service.query("lab", "run", "D", 0, 10)["events"] == []
    late = service.query("lab", "run", "C", 198, 199)
    assert [row["event_ref"] for row in late["events"]] == ["event:198", "event:199"]
    assert late["retrieval"]["records_read"] == 2


@pytest.mark.parametrize(
    "start,end",
    [(True, 1), (0, float("inf")), (float("nan"), 1), (-1, 1), (2, 1), (0, 121), ("0", 1)],
)
def test_unbounded_or_spoofed_time_rejected(
    service: ResearchService,
    start: Any,
    end: Any,
) -> None:
    with pytest.raises(ValueError, match="TIME_SCOPE_DENIED"):
        service.query("lab", "run", "C", start, end)


@pytest.mark.parametrize(
    "scene,run,camera", [("other", "run", "C"), ("lab", "other", "C"), ("lab", "run", "other")]
)
def test_wrong_bound_scope_rejected(
    service: ResearchService, scene: str, run: str, camera: str
) -> None:
    with pytest.raises(ValueError, match="SCOPE_DENIED"):
        service.query(scene, run, camera, 0, 1)


def test_query_and_details_cannot_mutate_cached_results(service: ResearchService) -> None:
    result = service.query("lab", "run", "C", 0, 1)
    result["events"][0]["support_state"] = "SUPPORTED"
    result["binding"]["scene_id"] = "other"
    assert service.event("lab", "run", "event:0")["event"]["support_state"] == "UNKNOWN"
    with pytest.raises(ValueError, match="EVENT_SCOPE_DENIED"):
        service.event("lab", "run", "event:other")


def test_runtime_query_does_not_load_source_rgb_or_reference(
    service: ResearchService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("runtime attempted source loader")

    monkeypatch.setattr("amidst.phase2_research.adapter._load", denied)
    monkeypatch.setattr(pipeline, "load", denied)
    result = service.query("lab", "run", "C", 0, 1)
    assert result["retrieval"]["frames_read"] == 0
    assert result["retrieval"]["rgb_bytes_read"] == 0
    assert result["retrieval"]["integrity_metadata_bytes_read"] > 0


def test_runtime_rejects_changed_metadata_and_symlink(
    service: ResearchService, tmp_path: Path
) -> None:
    original = service.output / "manifest.json"
    original.write_text('{"changed":true}')
    with pytest.raises(ValueError, match="ARTIFACT_CHANGED"):
        service.context()
    original.unlink()
    target = tmp_path / "untrusted.json"
    target.write_text(json.dumps(service.manifest))
    original.symlink_to(target)
    with pytest.raises(ValueError, match="ARTIFACT_PATH_DENIED"):
        service.context()


def test_runtime_rejects_algorithm_change(
    service: ResearchService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "algorithms", lambda: {"known": "changed"})
    with pytest.raises(ValueError, match="FREEZE_SOURCE_CHANGED"):
        service.query("lab", "run", "C", 0, 1)


def test_self_reported_aggregate_is_not_public_certificate(service: ResearchService) -> None:
    certified(service)
    service.expected_evaluation_sha256 = None
    result = service.diagnostics()
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "AGGREGATE_NOT_REGISTERED"
    assert "evaluation" not in result


def test_certified_aggregate_retains_fn_unknown_and_denominators(service: ResearchService) -> None:
    expected = certified(service)
    result = service.diagnostics()
    assert result["status"] == "CERTIFIED_AGGREGATE"
    assert result["evaluation"] == expected
    assert result["formal_phase1_acceptance"] is False
    assert result["trained_reid"] is False


def test_evaluation_receipt_certifies_serialized_integer_histograms(
    service: ResearchService,
) -> None:
    from amidst.phase2_research.evaluation import _persist_evaluation

    result = {
        "manifest_sha256": digest(service.manifest),
        "config_sha256": service.binding["config_sha256"],
        "dataset_sha256": service.binding["dataset_sha256"],
        "histogram": {2: 7, 10: 1},
    }
    persisted = _persist_evaluation(service.output, result, service.manifest)
    assert digest(result) != digest(persisted)
    service.expected_evaluation_sha256 = digest(persisted)
    assert service.diagnostics()["evaluation"]["histogram"] == {"2": 7, "10": 1}


def test_coherently_forged_aggregate_and_receipt_cannot_leak_reference(
    service: ResearchService,
) -> None:
    forged = copy.deepcopy(certified(service))
    forged["private"] = {"actor_identity": "truth", "path": "/private/reference.json"}
    (service.output / "evaluation.json").write_text(json.dumps(forged))
    receipt_path = service.output / "evaluation_receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    receipt["evaluation_sha256"] = digest(forged)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="EVALUATION_CERTIFICATE_MISMATCH"):
        service.diagnostics()


def test_evaluation_symlink_rejected_even_with_correct_digest(service: ResearchService) -> None:
    certified(service)
    path = service.output / "evaluation.json"
    renamed = service.output / "hidden.json"
    path.rename(renamed)
    path.symlink_to(renamed)
    with pytest.raises(ValueError, match="EVALUATION_PATH_DENIED"):
        service.diagnostics()


def test_registered_manifest_rejected_before_loading_any_frozen_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("amidst.phase2_research.adapter.load", lambda _: (None, None, {"x": 1}, {}))

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("certificate mismatch must fail before artifact loads")

    monkeypatch.setattr("amidst.phase2_research.adapter.frozen", denied)
    with pytest.raises(ValueError, match="MANIFEST_CERTIFICATE_MISMATCH"):
        ResearchService(
            tmp_path,
            scene_id="lab",
            variant="baseline",
            mode="photos_only",
            expected_manifest_sha256=digest({"x": 2}),
        )

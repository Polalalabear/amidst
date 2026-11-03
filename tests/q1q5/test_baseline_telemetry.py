"""Timing boundaries, failure records and real SYNTHETIC Q1/Q2 replay invariants."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_q1_search import search
from test_q5_controller import fixture, port, request, seed_id

from amidst.q1q5.baseline_telemetry import (
    MeasurementFailure,
    frame_rate,
    measure_call,
    peak_rss_bytes,
    verify_replay,
)
from amidst.q1q5.q5_controller import RuleController
from amidst.q1q5.store import canonical_hash


def test_wall_cpu_and_memory_are_separate_and_domain_object_untouched():
    value = {"domain": "unchanged"}
    wall = iter([1_000_000, 4_000_000])
    cpu = iter([100_000, 600_000])
    memory = iter([32, 64])
    result, sample = measure_call(
        lambda: value,
        wall_clock=lambda: next(wall),
        cpu_clock=lambda: next(cpu),
        memory=lambda: next(memory),
    )
    assert result is value and result == {"domain": "unchanged"}
    assert sample["wall_ms"] == 3 and sample["process_cpu_ms"] == 0.5
    assert sample["process_peak_rss_before_bytes"] == 32
    assert sample["process_peak_rss_after_bytes"] == 64
    assert sample["rss_semantics"] == "PEAK_SINCE_PROCESS_START"


def test_error_is_measured_without_persisting_exception_text_or_path():
    def fail():
        raise TimeoutError("/private/sensitive/path")

    with pytest.raises(MeasurementFailure) as caught:
        measure_call(fail, memory=lambda: None)
    sample = caught.value.sample
    assert sample["error_type"] == "TimeoutError" and sample["status"] == "ERROR"
    assert sample["rss_status"] == "UNKNOWN" and sample["wall_ms"] >= 0
    assert "sensitive" not in json.dumps(sample)


def test_backwards_clock_is_rejected():
    wall = iter([2, 1])
    with pytest.raises(ValueError, match="backwards"):
        measure_call(lambda: None, wall_clock=lambda: next(wall))


@pytest.mark.parametrize(
    "count,duration", [(None, 1), (True, 1), (-1, 1), (1, 0), (1, float("nan")), (1, float("inf"))]
)
def test_invalid_or_half_missing_fps_cannot_be_reported(count, duration):
    with pytest.raises(ValueError):
        frame_rate(completed_frames=count, elapsed_ms=duration)


def test_missing_fps_is_unknown_and_actual_fps_uses_wall_time():
    assert frame_rate(completed_frames=None, elapsed_ms=None) is None
    assert frame_rate(completed_frames=5, elapsed_ms=2000) == 2.5
    assert frame_rate(completed_frames=0, elapsed_ms=20) == 0


def test_native_rss_is_explicitly_peak_or_unknown():
    value = peak_rss_bytes()
    assert value is None or (type(value) is int and value > 0)


def test_real_q1_replay_preserves_hash_while_external_telemetry_changes():
    first, timing = measure_call(search)
    again, _ = measure_call(search)
    receipt = verify_replay(first, again)
    assert receipt["output_equal"] and receipt["journals_equal"] is None
    assert "wall_ms" not in first and "rss" not in first
    changed = deepcopy(again)
    changed["stats"] = {"telemetry_example": timing}
    assert verify_replay(first, changed) == receipt
    changed["results_total"] += 1
    with pytest.raises(ValueError):
        verify_replay(first, changed)


def test_real_rule_journal_replay_and_corruption_rejection():
    b = fixture()

    def run():
        return RuleController(
            request(b), bindings=b, evidence_provider=port([]), selected_observation_id=seed_id(b)
        ).run()

    first, _ = measure_call(run)
    replay, _ = measure_call(run)
    assert verify_replay(first, replay)["journals_equal"] is True
    with pytest.raises(ValueError, match="Journal pin"):
        verify_replay(first, replace(replay, links_bytes=b"tampered"))
    changed = deepcopy(replay.response)
    changed["provenance"]["gt_read"] = True
    changed["output_sha256"] = canonical_hash(changed, exclude=("output_sha256", "stats"))
    with pytest.raises(ValueError, match="boundary"):
        verify_replay(first, replace(replay, response=changed))


def cli():
    path = Path(__file__).resolve().parents[2] / "scripts/measure_q1q5_baseline.py"
    spec = importlib.util.spec_from_file_location("baseline_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_low_disk_stops_before_work(monkeypatch, tmp_path):
    module = cli()
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: type("Disk", (), {"free": 1})())
    with pytest.raises(RuntimeError, match="BELOW_8_GIB"):
        module.disk(tmp_path, "test")


def test_output_write_never_overwrites_existing_evidence(tmp_path):
    module = cli()
    path = tmp_path / "receipt.json"
    module.save(path, {"value": 1})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        module.save(path, {"value": 2})
    assert path.read_bytes() == original


def test_missing_worker_reports_never_produce_success(monkeypatch, tmp_path):
    module = cli()
    out = tmp_path / "missing-worker-reports"
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "measure",
            "--synthetic",
            "--lost-after-us",
            "600000",
            "--output",
            str(out),
        ],
    )
    monkeypatch.setattr(module, "disk", lambda *args: 10 * 1024**3)
    monkeypatch.setattr(
        module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr=b"")
    )
    with pytest.raises(SystemExit, match="MEASUREMENT_FAILED"):
        module.main()
    report = json.loads((out / "REPORT.json").read_text())
    assert report["status"] == "ERROR" and report["reports"] == []
    assert report["errors"] == [{"error": "INCOMPLETE_REPORTS", "completed": 0}]


@pytest.mark.parametrize(
    "case",
    [
        "supported_candidate",
        "empty_candidates",
        "temporary_loss_recovery",
        "incomplete_candidate_frames",
        "no_seed",
    ],
)
@pytest.mark.parametrize("workflow", ["ONCE_SEARCH", "CONTINUOUS_PURSUIT"])
def test_real_worker_records_three_calls_and_keeps_unmeasured_fields_null(workflow, case, tmp_path):
    module = cli()
    args = type(
        "Args",
        (),
        {
            "case": case,
            "workflow": workflow,
            "output": tmp_path,
            "warm_repeats": 2,
            "lost_after_us": 600000,
        },
    )()
    module.worker(args)
    report = json.loads((tmp_path / "telemetry.json").read_text())
    assert report["status"] == "COMPLETE" and len(report["samples"]) == 3
    assert report["content_sha256"] == canonical_hash(report, exclude=("content_sha256",))
    assert report["model_inference_fps"] is report["display_fps"] is report["accuracy"] is None
    assert not report["counts_for_acceptance"] and not report["model_connection"]
    assert all(s["provider_calls"] == 0 and s["replay"]["output_equal"] for s in report["samples"])
    assert len({s["output_sha256"] for s in report["samples"]}) == 1
    if workflow == "CONTINUOUS_PURSUIT":
        response = json.loads((tmp_path / "recorded/response.json").read_text())
        for field in ["decisions", "links"]:
            raw = (tmp_path / "recorded" / response[field + "_ref"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == response[field + "_sha256"]
        if case == "supported_candidate":
            assert report["samples"][0]["flags"] and report["samples"][0]["decisions"]
        if case == "no_seed":
            assert not report["samples"][0]["flags"]
    elif case == "incomplete_candidate_frames":
        assert report["samples"][0]["not_evaluated_cameras"]
        records = [
            json.loads(line)
            for line in (tmp_path / "recorded/detection_index.records.jsonl")
            .read_text()
            .splitlines()
        ]
        missing = [r for r in records if r["frame_state"] == "MISSING"]
        assert len(missing) == 10 and all(r["rgb_file_sha256"] is None for r in missing)

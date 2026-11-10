"""Telemetry preserves exceptions, null values and denominator semantics."""

import subprocess

import pytest

from amidst.q1q5.runtime_telemetry import ProcessSampler, StageMetrics, rss_bytes


def test_stage_preserves_integrity_exception_identity():
    error = ValueError("pin mismatch")
    m = StageMetrics()

    def fail():
        raise error

    with pytest.raises(ValueError) as caught:
        m("rgb_read", fail)
    assert caught.value is error
    assert m.report()["stages"]["rgb_read"]["successful_calls"] == 0


def test_forward_rate_uses_only_successful_forward_duration():
    m = StageMetrics()
    for stage, status, wall in [
        ("detector_forward", "COMPLETE", 10),
        ("detector_forward", "ERROR", 10),
        ("model_load", "COMPLETE", 1000),
    ]:
        m.rows.append(dict(stage=stage, status=status, wall_ms=wall, process_cpu_ms=0))
    assert m.report()["forward_fps"] == 50
    assert m.report()["display_fps"] is None


@pytest.mark.parametrize("pid", [0, -1, True, "1"])
def test_explicit_pid_required(pid):
    with pytest.raises(ValueError):
        rss_bytes(pid)


def test_unavailable_rss_is_null(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, ""))
    assert rss_bytes(123) is None


def test_sampler_joins_and_never_sums_process_peaks(monkeypatch):
    monkeypatch.setattr("amidst.q1q5.runtime_telemetry.system_snapshot", lambda: {})
    with ProcessSampler(
        {"caller": 1, "service": 2}, reader=lambda pid: None if pid == 2 else 100
    ) as s:
        pass
    report = s.report()
    assert not s.thread.is_alive()
    assert report["sampled_rss_peak_bytes"] == {"caller": 100, "service": None}
    assert report["physical_vram_peak_bytes"] is None

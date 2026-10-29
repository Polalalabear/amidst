"""Optional observation never changes index bytes or integrity failures."""

import pytest
from test_detection_index import build, safe_run

from amidst.q1q5.detection_index import IndexIntegrityError
from amidst.q1q5.runtime_telemetry import StageMetrics


def test_observer_preserves_index_bytes_and_hashes():
    plain = build()
    metrics = StageMetrics()
    timed = build(observer=metrics)
    assert timed == plain
    assert metrics.report()["stages"]["rgb_read"]["calls"] == 4
    assert metrics.report()["stages"]["upper_hsv"]["calls"] == 4


def test_observed_integrity_failure_is_still_fatal():
    run = safe_run()
    run.read_rgb = lambda *a: b"bad"
    with pytest.raises(IndexIntegrityError):
        build(run, observer=StageMetrics())

"""Optional runtime measurements kept outside immutable domain output hashes.

No model, media, GT, UI or evaluation imports. Peak RSS is a process lifetime
high-water mark, not current residency, per-call allocation or device memory.
"""

import math
import sys
import time
from collections.abc import Callable
from typing import Any


def peak_rss_bytes() -> int | None:
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return int(value)
        if sys.platform.startswith("linux"):
            return int(value * 1024)
    except (ImportError, OSError, ValueError):
        pass
    return None


class MeasurementFailure(RuntimeError):
    """Carries a completed failure measurement without storing exception text."""

    def __init__(self, sample: dict[str, Any]):
        self.sample = sample
        super().__init__(sample["error_type"])


def measure_call(
    operation: Callable[[], Any],
    *,
    wall_clock: Callable[[], int] = time.perf_counter_ns,
    cpu_clock: Callable[[], int] = time.process_time_ns,
    memory: Callable[[], int | None] = peak_rss_bytes,
) -> tuple[Any, dict[str, Any]]:
    """Measure only the operation; RSS probes and report serialization are outside."""
    before = memory()
    cpu_start = cpu_clock()
    start = wall_clock()
    error = None
    result = None
    try:
        result = operation()
    except Exception as exc:
        error = exc
    elapsed = wall_clock() - start
    cpu = cpu_clock() - cpu_start
    after = memory()
    if elapsed < 0 or cpu < 0:
        raise ValueError("Monotonic measurement clock moved backwards")
    sample = {
        "wall_ms": elapsed / 1_000_000,
        "process_cpu_ms": cpu / 1_000_000,
        "process_peak_rss_before_bytes": before,
        "process_peak_rss_after_bytes": after,
        "rss_semantics": "PEAK_SINCE_PROCESS_START",
        "rss_status": "MEASURED" if before is not None and after is not None else "UNKNOWN",
        "status": "ERROR" if error else "COMPLETE",
        "error_type": type(error).__name__ if error else None,
    }
    if error is not None:
        raise MeasurementFailure(sample) from error
    return result, sample


def frame_rate(*, completed_frames: int | None, elapsed_ms: float | None) -> float | None:
    """Only completed actual frames divided by wall duration constitute fps."""
    if completed_frames is None and elapsed_ms is None:
        return None
    if (
        type(completed_frames) is not int
        or completed_frames < 0
        or type(elapsed_ms) not in (int, float)
        or not math.isfinite(elapsed_ms)
        or elapsed_ms <= 0
    ):
        raise ValueError("Explicit frame count and positive finite duration required")
    return completed_frames * 1000 / elapsed_ms


def verify_replay(original: Any, replay: Any) -> dict[str, Any]:
    """Q1 dictionaries or Q2 result objects; equality excludes only domain stats."""
    from amidst.q1q5.store import canonical_hash

    q1 = isinstance(original, dict) and isinstance(replay, dict)
    left = original if q1 else original.response
    right = replay if q1 else replay.response
    for response in (left, right):
        if (
            response.get("output_sha256")
            != canonical_hash(response, exclude=("output_sha256", "stats"))
            or response.get("identity_verdict") != "UNCONFIRMED"
            or response.get("provenance", {}).get("gt_read") is not False
        ):
            raise ValueError("Invalid domain response or inference boundary")
    equal = left["output_sha256"] == right["output_sha256"]
    journals_equal = None
    if not q1:
        import hashlib

        for result in (original, replay):
            for field in ("decisions", "links"):
                raw = getattr(result, field + "_bytes")
                if hashlib.sha256(raw).hexdigest() != result.response[field + "_sha256"]:
                    raise ValueError("Journal pin mismatch")
        journals_equal = (
            original.decisions_bytes == replay.decisions_bytes
            and original.links_bytes == replay.links_bytes
        )
        equal = equal and journals_equal
    if not equal:
        raise ValueError("Replay domain output changed")
    return {
        "output_sha256": left["output_sha256"],
        "output_equal": True,
        "journals_equal": journals_equal,
    }

"""Opt-in stage timing and explicit-PID RSS sampling; never inference inputs."""

import os
import subprocess
import threading
import time
from collections import defaultdict

from amidst.q1q5.baseline_telemetry import MeasurementFailure, measure_call


class StageMetrics:
    def __init__(self):
        self.rows = []

    def __call__(self, name, operation):
        try:
            result, row = measure_call(operation)
        except MeasurementFailure as error:
            self.rows.append(dict(stage=name, **error.sample))
            # Measurement must not convert integrity failures into detector failures.
            raise error.__cause__ from None
        self.rows.append(dict(stage=name, **row))
        return result

    def report(self):
        groups = defaultdict(list)
        for row in self.rows:
            groups[row["stage"]].append(row)
        stages = {
            name: dict(
                calls=len(rows),
                successful_calls=sum(r["status"] == "COMPLETE" for r in rows),
                wall_ms=sum(r["wall_ms"] for r in rows),
                process_cpu_ms=sum(r["process_cpu_ms"] for r in rows),
            )
            for name, rows in groups.items()
        }
        forward = stages.get("detector_forward")
        return dict(
            stages=stages,
            rows=self.rows,
            forward_fps=(forward["successful_calls"] * 1000 / forward["wall_ms"])
            if forward and forward["wall_ms"] > 0
            else None,
            forward_fps_semantics="SUCCESSFUL_CPU_FORWARD_FRAMES_OVER_FORWARD_WALL_ONLY",
            nested_stages_are_not_additive=True,
            display_fps=None,
            display_fps_reason="REQUIRES_BROWSER_PRESENTATION_MEASUREMENT",
        )


def rss_bytes(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("EXPLICIT_PID_REQUIRED")
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True)
    text = result.stdout.strip()
    return int(text) * 1024 if result.returncode == 0 and text.isdigit() else None


def system_snapshot():
    result = {}
    for name, command in [
        ("vm_stat", ["vm_stat"]),
        ("swap_usage", ["sysctl", "-n", "vm.swapusage"]),
    ]:
        row = subprocess.run(command, capture_output=True, text=True)
        result[name] = row.stdout if row.returncode == 0 else None
    return result


class ProcessSampler:
    def __init__(self, pids=None, *, interval_s=0.1, reader=rss_bytes, clock=time.monotonic):
        if not 0.05 <= interval_s <= 5:
            raise ValueError("BOUNDED_SAMPLE_INTERVAL_REQUIRED")
        self.pids = dict(pids or {"caller": os.getpid()})
        if not self.pids or any(type(p) is not int or p <= 0 for p in self.pids.values()):
            raise ValueError("EXPLICIT_PID_REQUIRED")
        self.interval, self.reader, self.clock = interval_s, reader, clock
        self.rows = []
        self.stop = threading.Event()
        self.thread = None

    def sample(self):
        self.rows.append(
            dict(
                monotonic_s=self.clock(),
                rss_bytes={name: self.reader(pid) for name, pid in self.pids.items()},
            )
        )

    def __enter__(self):
        self.before = system_snapshot()
        self.sample()

        def run():
            while not self.stop.wait(self.interval):
                self.sample()

        self.thread = threading.Thread(target=run, name="q1q5-owned-resource-sampler", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(6)
        self.sample()
        self.after = system_snapshot()

    def report(self):
        return dict(
            sample_interval_s=self.interval,
            samples=self.rows,
            sampled_rss_peak_bytes={
                name: max(
                    (r["rss_bytes"][name] for r in self.rows if r["rss_bytes"][name] is not None),
                    default=None,
                )
                for name in self.pids
            },
            process_peaks_must_not_be_summed=True,
            system_before=self.before,
            system_after=self.after,
            physical_vram_peak_bytes=None,
            physical_vram_reason="OLLAMA_SIZE_VRAM_IS_NOT_PHYSICAL_PEAK",
        )

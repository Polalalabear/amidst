"""Run the two authorized render jobs with disk telemetry and an 8 GiB stop line."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--artifacts-root", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    root = a.artifacts_root / "data/r004-4actor-v22-20261110"
    telemetry = root / "gt_private/control"
    telemetry.mkdir(parents=True, exist_ok=True)
    for label, estimate in [("A4-1", 1.7), ("B4-1", 0.87)]:
        df = subprocess.check_output(["df", "-k", str(Path.home())], text=True)
        free = shutil.disk_usage(root).free
        if free < (8 + estimate) * 1024**3:
            raise SystemExit("STOP_START_RESERVE:" + str(free))
        run = root / label
        cmd = [
            "/Applications/Blender.app/Contents/MacOS/blender",
            "--background",
            "--disable-autoexec",
            str(
                a.artifacts_root / "data/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend"
            ),
            "--python",
            str(a.repo / "scripts/render_r004_4actor.py"),
            "--",
            "--repo",
            str(a.repo),
            "--scenario",
            str(a.repo / "docs/evaluation/R004_A4B4_SCENARIO_V2_2_4ACTOR_DRAFT.json"),
            "--geometry",
            str(a.repo / "docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json"),
            "--catalog",
            str(a.artifacts_root / "data/r004-build-v2-20261021/safe_static/cameras.json"),
            "--output",
            str(root),
            "--label",
            label,
            "--authorization-ref",
            "USER_CHAT_2026-11-10_516_FULL_PIPELINE",
        ]
        if run.exists():
            if not a.resume:
                raise SystemExit("EXISTING_RUN_NEEDS_RESUME")
            cmd.append("--resume")
        log = telemetry / (label + "-" + str(time.time_ns()) + ".log")
        started = time.monotonic()
        minimum, stopped = free, False
        with log.open("x") as stream:
            process = subprocess.Popen(
                cmd,
                cwd=a.repo,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            try:
                while process.poll() is None:
                    available = shutil.disk_usage(root).free
                    minimum = min(minimum, available)
                    if available < 8 * 1024**3:
                        stopped = True
                        os.killpg(process.pid, signal.SIGTERM)
                        break
                    time.sleep(2)
                result = process.wait(timeout=30)
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=30)
                raise
        record = {
            "label": label,
            "code_git_sha": subprocess.check_output(
                ["git", "-C", str(a.repo), "rev-parse", "HEAD"], text=True
            ).strip(),
            "before_df_k": df,
            "start_free_bytes": free,
            "end_free_bytes": shutil.disk_usage(root).free,
            "disk_min_available_bytes": minimum,
            "stopped_below_8_gib": stopped,
            "exit_code": result,
            "elapsed_s": time.monotonic() - started,
            "log_name": log.name,
        }
        with (telemetry / (label + "-" + str(time.time_ns()) + ".json")).open("x") as f:
            json.dump(record, f, indent=2)
        print(json.dumps(record), flush=True)
        if result != 0 or stopped:
            raise SystemExit("RENDER_STOPPED:" + label)


if __name__ == "__main__":
    main()

"""Finite, serial all/adaptive browser validation; graceful owned-server shutdown.

No demo process management, API credentials or paid advisor. Run in the feature clone.
"""

import argparse
import hashlib
import json
import os
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from amidst.live_mode.scheduler import DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256
from amidst.live_mode.server import FRONT, State, make_handler


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--assets", required=True)
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args()
    if a.port == 8785:
        ap.error("8785 is the pinned demo")
    a.out.mkdir(parents=True, exist_ok=True)
    latency = a.out / "latency"
    latency.mkdir(exist_ok=True)
    # Explicit reproducible runtime config; no provider/key configuration is read.
    args = SimpleNamespace(
        cameras=a.cameras,
        camera_graph=DEFAULT_GRAPH,
        graph_sha256=DEFAULT_GRAPH_SHA256,
        expand_every=1,
        schedule="all",
        models=a.models,
        device="mps",
        threads=4,
        det_resize_mode="letterbox",
        min_score=0.15,
        camera_min_scores={"CAM_ENTRY": 0.05},
        assets=a.assets,
        gate_m=4.0,
        gate_growth=0.0,
        max_gate=8.0,
        advisor="off",
        advisor_provider="fake",
        advisor_model="sol6.1",
        det_width=320,
        det_height=180,
    )
    state = State(args)
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    runtime_files = [
        "src/amidst/live_mode/scheduler.py",
        "src/amidst/live_mode/server.py",
        "frontend/live-mode/src/operator.mjs",
        "frontend/live-mode/measure/latency.mjs",
    ]
    source = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in runtime_files}
    receipt = {"head": head, "runtime_files": source, "args": config, "runs": [], "paid_calls": 0}
    (a.out / "composition.json").write_text(json.dumps(receipt, indent=2) + "\n")
    try:
        for mode in ["all", "adaptive"]:
            for route, duration, seconds in [("A4", 50, 58), ("B4", 42, 50)]:
                label = f"{mode}-{route}"
                with state.lock:
                    state.args.schedule = mode
                    state.scheduler.mode = mode
                    state.reset()
                query = (
                    f"auto={route}&run={route}-1-v2-4actor&duration={duration}"
                    "&model=glb&w=320&h=180&fps=5"
                )
                env = {
                    k: os.environ[k]
                    for k in ["PATH", "HOME", "TMPDIR", "CHROME"]
                    if k in os.environ
                }
                env.update(
                    LIVE_BASE=f"http://127.0.0.1:{server.server_port}",
                    RAW="1",
                    OUT=str(latency.resolve()),
                )
                cmd = ["node", "measure/latency.mjs", label, query, str(seconds)]
                print("START", label, flush=True)
                with (a.out / f"{label}.log").open("w") as log:
                    result = subprocess.run(
                        cmd, cwd=FRONT, env=env, stdout=log, stderr=subprocess.STDOUT
                    )
                receipt["runs"].append(
                    {"label": label, "command": cmd, "returncode": result.returncode}
                )
                (a.out / "composition.json").write_text(json.dumps(receipt, indent=2) + "\n")
                print("END", label, result.returncode, flush=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        print("OWNED_SERVER_CLOSED", flush=True)
    if any(r["returncode"] for r in receipt["runs"]):
        raise SystemExit(1)
    subprocess.run(
        [
            "node",
            "frontend/live-mode/measure/t1_analyze.mjs",
            str(latency),
            "docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()

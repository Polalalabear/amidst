"""Quality replay of fixed pixel-derived detections; GT retained only for later t1_analyze scoring.

The policy function receives no scenario, actor positions, GT visibility or prior tracking answers.
No model, network, key or paid advisor. Camera calibration and graph are hash-bound safe inputs.
"""

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

from amidst.live_mode.scheduler import (
    DEFAULT_GRAPH,
    DEFAULT_GRAPH_SHA256,
    DEFAULT_RECENT_RED_S,
    CameraScheduler,
    load_graph,
)
from amidst.live_mode.tracker import Projector, Tracker, load_cameras


def replay_safe(
    records,
    available,
    size,
    projector,
    graph,
    mode,
    expand_every,
    recent_red_s=DEFAULT_RECENT_RED_S,
):
    tracker = Tracker(projector, gate_m=4.0)
    scheduler = CameraScheduler(
        graph, mode=mode, expand_every=expand_every, recent_red_s=recent_red_s
    )
    result = []
    for i, record in enumerate(records):
        t_s = record["t_capture_ms"] / 1000
        plan = scheduler.plan(tracker.active, tracker.lost, available, t_s=t_s)
        dets = {
            c: copy.deepcopy(record["dets"][c]) for c in plan["camera_ids"] if c in record["dets"]
        }
        tracking = tracker.update(i, dets, size, record["t_capture_ms"] / 1000)
        scheduler.observe(dets, t_s)
        following = scheduler.plan(tracker.active, tracker.lost, available, t_s=t_s)
        plan["next_camera_ids"] = following["camera_ids"]
        result.append({"dets": dets, "tracking": tracking, "schedule": plan})
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", action="append", required=True, help="label=recorded directory")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cameras", type=Path, required=True)
    ap.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    ap.add_argument("--graph-sha256", default=DEFAULT_GRAPH_SHA256)
    ap.add_argument("--expand-every", type=int, default=1)
    ap.add_argument("--recent-red-s", type=float, default=DEFAULT_RECENT_RED_S)
    a = ap.parse_args()
    cameras = load_cameras(str(a.cameras))
    projector = Projector(cameras)
    graph, meta = load_graph(
        a.graph,
        a.graph_sha256,
        hashlib.sha256(a.cameras.read_bytes()).hexdigest(),
        list(projector.cams),
    )
    inventory = []
    for mode in ["all", "adaptive"]:
        folder = a.out / mode
        folder.mkdir(parents=True, exist_ok=True)
        for source in a.src:
            label, directory = source.split("=", 1)
            for p in sorted(Path(directory).glob("*.t1raw.json")):
                raw = json.loads(p.read_text())
                n = min(len(raw["ticks"]), len(raw["infer"]))
                # Source observations only: exclude old projections and evaluation fields.
                records = [
                    {
                        "t_capture_ms": raw["ticks"][i]["t_capture"],
                        "dets": {
                            c: [
                                {
                                    k: d[k]
                                    for k in ("bbox", "score", "color", "red_ratio", "blue_ratio")
                                    if k in d
                                }
                                for d in ds
                            ]
                            for c, ds in raw["infer"][i]["dets"].items()
                        },
                    }
                    for i in range(n)
                ]
                replay = replay_safe(
                    records,
                    raw["cfg"]["cams"],
                    (raw["cfg"]["w"], raw["cfg"]["h"]),
                    projector,
                    graph,
                    mode,
                    a.expand_every,
                    a.recent_red_s,
                )
                # Reattach evaluation fields only after policy/tracker processing finishes.
                out = copy.deepcopy(raw)
                for response, row in zip(out["infer"], replay, strict=False):
                    response.update(row)
                out["schedule_replay"] = {
                    "mode": mode,
                    "expand_every": a.expand_every,
                    "recent_red_s": a.recent_red_s,
                    **meta,
                    "gt_in_policy": False,
                }
                (folder / f"{label}__{p.name}").write_text(json.dumps(out))
                if mode == "all":
                    inventory.append(
                        {
                            "source": label,
                            "name": p.name,
                            "bytes": p.stat().st_size,
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        }
                    )
        subprocess.run(
            [
                "node",
                "frontend/live-mode/measure/t1_analyze.mjs",
                str(folder),
                "docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    summaries = {
        m: json.loads((a.out / m / "t1_summary.json").read_text()) for m in ["all", "adaptive"]
    }

    def compact(summary):
        return [
            {
                "label": r["label"],
                "cams": r["cams"],
                "on_target": r["evaluation_only"]["on_target"],
                "wrong_person": r["evaluation_only"]["wrong_person"],
                "lost": r["evaluation_only"]["lost"],
            }
            for r in summary["runs"]
        ]

    result = {
        "graph": meta,
        "expand_every": a.expand_every,
        "recent_red_s": a.recent_red_s,
        "source_inventory": inventory,
        "runs": {m: compact(s) for m, s in summaries.items()},
    }
    for mode, rows in result["runs"].items():
        result.setdefault("mean", {})[mode] = {
            k: sum(r[k] for r in rows) / len(rows) for k in ["on_target", "wrong_person", "lost"]
        }
    (a.out / "quality.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"n": len(inventory), "mean": result["mean"], "graph": meta}, indent=2))


if __name__ == "__main__":
    main()

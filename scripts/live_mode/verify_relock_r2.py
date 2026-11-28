"""Check R-4/R-6 on frozen D273 detections with the existing relock and scorer."""

import argparse
import json
from pathlib import Path

from replay_relock import entry_audit, inventory_file, observation_records, replay_safe, score_replays

from amidst.live_mode.relock import RelockConfig
from amidst.live_mode.scheduler import DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, load_graph
from amidst.live_mode.tracker import Projector, load_cameras


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d273", type=Path, required=True, help="D273 evidence directory")
    parser.add_argument("--cameras", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Fresh LOCAL output directory")
    args = parser.parse_args()

    paths = {
        "entry-adaptive-A4": "fresh/latency/adaptive-A4.t1raw.json",
        "entry-all-A4": "fresh/latency/all-A4.t1raw.json",
        "fixed-A4": "baseline-fixed/all/fixed__a4_route_baseline.t1raw.json",
        "fixed-B4": "baseline-fixed/all/fixed__b4_route_baseline.t1raw.json",
    }
    entries = [
        (label, args.d273 / rel, json.loads((args.d273 / rel).read_bytes()))
        for label, rel in paths.items()
    ]
    camera_source = inventory_file(args.cameras)
    projector = Projector(load_cameras(str(args.cameras)))
    graph, binding = load_graph(
        DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, camera_source["sha256"], list(projector.cams)
    )
    args.out.mkdir(parents=True)
    report = {
        "camera_source": camera_source,
        "graph": binding,
        "inputs": {label: inventory_file(path, relative_path=paths[label]) for label, path, _ in entries},
        "runs": {},
    }

    observations = [observation_records(raw) for _, _, raw in entries]
    for mode in ("all", "adaptive"):
        for relock, config in (("off", None), ("fallback", RelockConfig())):
            name = f"{mode}-{relock}"
            traces = [
                replay_safe(records, raw["cfg"]["cams"], (raw["cfg"]["w"], raw["cfg"]["h"]),
                            projector, graph, mode=mode, config=config)
                for records, (_, _, raw) in zip(observations, entries, strict=True)
            ]
            scored, rates = score_replays(entries, traces, args.out / name)
            audit = entry_audit(entries, traces, scored)
            cases = {}
            for (label, _, raw), trace in zip(entries, traces, strict=True):
                rate = rates[label]
                cases[label] = {
                    "target_visible_ticks": rate["target_visible_ticks"],
                    "on_target": rate["on_target"],
                    "lost": rate["lost"],
                    "needs_confirm_ticks": sum(row["tracking"]["state"] == "NEEDS_CONFIRM" for row in trace),
                    "protocol_violations_source": raw.get("violations"),
                    "entry": audit[label],
                }
                for entry in audit[label]:
                    i = entry["entry_tick"]
                    row = trace[i]
                    entry.update(
                        entry_scheduled="CAM_ENTRY" in row["schedule"]["camera_ids"],
                        entry_detections=len(row["dets"].get("CAM_ENTRY", [])),
                        first_entry_scheduled_tick=next(
                            (tick for tick in range(i, len(trace))
                             if "CAM_ENTRY" in trace[tick]["schedule"]["camera_ids"]),
                            None,
                        ),
                        confirm_candidates=[
                            {"cam": c["cam"], "dist_m": c["dist_m"]}
                            for c in row["tracking"].get("confirm_candidates", [])
                        ],
                    )
            report["runs"][name] = cases

    (args.out / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

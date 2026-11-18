"""D273 source-bound receipt; null baseline ENTRY locks never become a pass.

Run only after the finite validation harness closes its owned server. No inference or API.
"""

import argparse
import hashlib
import json
from pathlib import Path

from joint_detection_schedule_receipt import check_quality, entry_events
from joint_schedule_diagnostics import entry_diagnostics


def entry_gate(all_events, adaptive_events):
    if not all_events and not adaptive_events:
        return {"status": "NOT_OBSERVED", "pass": None}
    if not all_events or any(e["censored"] for e in all_events):
        return {"status": "BASELINE_TRACKER_NO_RELOCK", "pass": None}
    if len(all_events) != len(adaptive_events):
        return {"status": "UNPAIRED_EPISODES", "pass": None}
    if any(e["censored"] for e in adaptive_events):
        return {"status": "ADAPTIVE_NO_RELOCK", "pass": False}
    return {
        "status": "MEASURED",
        "pass": all(
            b["target_lock_ms"] <= a["target_lock_ms"]
            for a, b in zip(all_events, adaptive_events, strict=True)
        ),
    }


def public_runtime(composition):
    # Raw LOCAL composition retains full paths; committed receipts use its digest.
    private_paths = {"cameras", "camera_graph", "models", "assets"}
    return {
        "head": composition["head"],
        "runtime_files": composition["runtime_files"],
        "settings": {k: v for k, v in composition["args"].items() if k not in private_paths},
        "runs": composition["runs"],
        "paid_calls": composition["paid_calls"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--python-passed", type=int, required=True)
    ap.add_argument("--node-passed", type=int, required=True)
    a = ap.parse_args()
    root = a.work

    def read(p):
        return json.loads(p.read_text())

    fixed = read(root / "recent-fixed/quality.json")
    summary = read(root / "fresh/latency/t1_summary.json")["runs"]
    scores = {r["label"]: r for r in summary}
    rows = {r["label"]: r["rows"] for r in read(root / "fresh/latency/t1_rows.json")}
    live = check_quality(
        [scores[f"all-{r}"] for r in ["A4", "B4"]], [scores[f"adaptive-{r}"] for r in ["A4", "B4"]]
    )
    latency, entries, entry_details = {}, {}, {}
    for mode in ["all", "adaptive"]:
        for route in ["A4", "B4"]:
            label = f"{mode}-{route}"
            r = read(root / "fresh/latency" / f"{label}.latency.json")
            latency[label] = {
                k: r[k]
                for k in ["achieved_fps", "frame_latency_ms", "schedule", "protocol_violations"]
            }
            raw = read(root / "fresh/latency" / f"{label}.t1raw.json")
            entries[label] = entry_events(raw, rows[label])
            entry_details[label] = entry_diagnostics(raw, rows[label])
    gates = {
        route: entry_gate(entries[f"all-{route}"], entries[f"adaptive-{route}"])
        for route in ["A4", "B4"]
    }
    rq = check_quality(fixed["runs"]["all"], fixed["runs"]["adaptive"])
    manifest = root / "MANIFEST.json"
    files = [
        {
            "path": p.relative_to(root).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(root.rglob("*"))
        if p.is_file() and p != manifest
    ]
    manifest.write_text(
        json.dumps({"path_base": "local/evidence/cx552-d-20261118", "files": files}, indent=2)
        + "\n"
    )
    result = {
        "runtime": public_runtime(read(root / "fresh/composition.json")),
        "source_composition": {
            "path": "local/evidence/cx552-d-20261118/fresh/composition.json",
            "sha256": hashlib.sha256((root / "fresh/composition.json").read_bytes()).hexdigest(),
        },
        "policy": {
            "recent_red_s": 2.0,
            "default_mode": "adaptive",
            "min_score": 0.15,
            "camera_min_scores": {"CAM_ENTRY": 0.05},
            "graph_changed": False,
        },
        "fixed_rgb": rq,
        "fresh_live": live,
        "latency": latency,
        "entry_events": entries,
        "entry_tracking_diagnostics": entry_details,
        "entry_gate": gates,
        "protocol_pass": all(r["protocol_violations"] == 0 for r in latency.values()),
        "clock_fit": {r["label"]: r["clock_fit"] for r in summary},
        "visible_ticks": {
            r["label"]: r["evaluation_only"]["target_visible_ticks"] for r in summary
        },
        "focused_tests": {"python_passed": a.python_passed, "node_passed": a.node_passed},
        "artifacts": {
            "path": "local/evidence/cx552-d-20261118/MANIFEST.json",
            "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "files": len(files),
            "bytes": sum(f["bytes"] for f in files),
        },
        "paid_calls": 0,
        "gt_in_policy": False,
        "limits": [
            "fixed RGB uses two existing C source recordings, four/three cameras",
            "fresh runs have different sampling ticks and are not paired RGB experiments",
            "censored all ENTRY: baseline detector/tracker problem; scheduling gate UNKNOWN",
            "no identity, physical navigation or safety acceptance",
        ],
    }
    result["overall"] = (
        "PASS"
        if (
            all(x["on_target_pass"] and x["lost_pass"] for x in rq.values())
            and all(x["on_target_pass"] and x["lost_pass"] for x in live.values())
            and result["protocol_pass"]
            and gates["A4"]["pass"] is True
        )
        else "NOT_PASSED"
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

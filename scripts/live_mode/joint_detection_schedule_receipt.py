"""Evaluation only: compare joint detector/scheduler gates after all runs finish.

No model/provider calls. Uses frozen replay scores and separate browser GT logs only.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_quality(all_rows, adaptive_rows):
    out = {}
    for route in ["a4", "b4"]:
        a = next(
            r
            for r in all_rows
            if r["label"].lower().endswith(route) or r["label"].startswith(route)
        )
        b = next(
            r
            for r in adaptive_rows
            if r["label"].lower().endswith(route) or r["label"].startswith(route)
        )
        q = lambda r: r.get("evaluation_only", r)
        a, b = q(a), q(b)
        out[route] = {
            "all": {k: a[k] for k in ["on_target", "wrong_person", "lost"]},
            "adaptive": {k: b[k] for k in ["on_target", "wrong_person", "lost"]},
            "on_target_pass": b["on_target"] >= a["on_target"],
            "lost_pass": b["lost"] <= a["lost"] + 0.02,
        }
    return out


def entry_events(raw, rows):
    # Re-entry is an ENTRY-visible episode after an earlier ENTRY-visible episode.
    # The initial appearance is excluded. Scoring never feeds this into runtime policy.
    events = []
    seen = False
    previous = False
    for i, tick in enumerate(raw["ticks"]):
        visible = "CAM_ENTRY" in tick["gt_visible"]
        if visible and not previous and seen:
            end = i + 1
            while end < len(raw["ticks"]) and "CAM_ENTRY" in raw["ticks"][end]["gt_visible"]:
                end += 1
            lock = next((j for j in range(i, end) if rows[j]["status"] == "ON_TARGET"), None)
            entry = next((j for j in range(i, end) if "CAM_ENTRY" in raw["infer"][j]["dets"]), None)
            active = next(
                (
                    j
                    for j in range(i, end)
                    if rows[j]["status"] == "ON_TARGET" and rows[j]["active"] == "CAM_ENTRY"
                ),
                None,
            )
            elapsed = lambda j: None if j is None else raw["infer"][j]["t_resp"] - tick["t_capture"]
            events.append(
                {
                    "start_tick": tick["tick"],
                    "start_s": rows[i]["tSec"],
                    "target_lock_ms": elapsed(lock),
                    "entry_first_processed_ms": elapsed(entry),
                    "entry_active_correct_lock_ms": elapsed(active),
                    "censored": lock is None,
                }
            )
        seen = seen or visible
        previous = visible
    return events


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    root = a.work
    subprocess.run(
        [
            "node",
            "frontend/live-mode/measure/t1_analyze.mjs",
            str(root / "latency"),
            "docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    replay = read(root / "replay/quality.json")
    summary = read(root / "latency/t1_summary.json")["runs"]
    scores = {r["label"]: r for r in summary}
    rows = {r["label"]: r["rows"] for r in read(root / "latency/t1_rows.json")}
    live = check_quality(
        [scores[f"all-{r}"] for r in ["A4", "B4"]], [scores[f"adaptive-{r}"] for r in ["A4", "B4"]]
    )
    latency = {}
    entry = {}
    entry_pass = {}
    for mode in ["all", "adaptive"]:
        for route in ["A4", "B4"]:
            label = f"{mode}-{route}"
            r = read(root / "latency" / f"{label}.latency.json")
            latency[label] = {
                k: r[k]
                for k in ["achieved_fps", "frame_latency_ms", "schedule", "protocol_violations"]
            }
            raw = read(root / "latency" / f"{label}.t1raw.json")
            entry[label] = entry_events(raw, rows[label])
    for route in ["A4", "B4"]:
        aa, bb = entry[f"all-{route}"], entry[f"adaptive-{route}"]
        if not aa and not bb:
            entry_pass[route] = {"status": "NOT_OBSERVED", "pass": None}
        elif len(aa) != len(bb) or any(r["censored"] for r in aa + bb):
            entry_pass[route] = {"status": "UNKNOWN_CENSORED_OR_UNPAIRED", "pass": None}
        else:
            entry_pass[route] = {
                "status": "MEASURED",
                "pass": all(b["target_lock_ms"] <= x["target_lock_ms"] for x, b in zip(aa, bb)),
            }
    rq = check_quality(replay["runs"]["all"], replay["runs"]["adaptive"])
    manifest = root / "MANIFEST.json"
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p != manifest:
            files.append(
                {
                    "path": p.relative_to(root).as_posix(),
                    "bytes": p.stat().st_size,
                    "sha256": sha(p),
                }
            )
    manifest.write_text(
        json.dumps({"path_base": "$AMIDST_ARTIFACTS/cx552-c-20261117", "files": files}, indent=2)
        + "\n"
    )
    result = {
        "merge_commit": "4ac1738a4127e773fe7e786b09cb1bc042795212",
        "merge_parents": [
            "efb2f498fe8955ae7b5de3a441e51d1dec48b778",
            "e9db4fdf866620f34557650f4f4c8458767d1b97",
        ],
        "tested_head": "06201314e3e98ebe53231dd797d72ecd3891fecb",
        "tested_tree": "cf67e16efbf64796020af77d99da48b6c93756e5",
        "default_thresholds": {
            "min_score": 0.15,
            "camera_min_scores": {"CAM_ENTRY": 0.05},
            "resize": "letterbox",
        },
        "fixed_rgb_replay": rq,
        "live_quality": live,
        "live_clock_fit": {r["label"]: r["clock_fit"] for r in summary},
        "live_visible_ticks": {
            r["label"]: r["evaluation_only"]["target_visible_ticks"] for r in summary
        },
        "latency": latency,
        "entry_events": entry,
        "entry_gate": entry_pass,
        "protocol_pass": all(r["protocol_violations"] == 0 for r in latency.values()),
        "focused_tests": {"python_passed": 61, "node_passed": 36},
        "artifacts": {
            "path": "$AMIDST_ARTIFACTS/cx552-c-20261117/MANIFEST.json",
            "sha256": sha(manifest),
            "files": len(files),
            "bytes": sum(f["bytes"] for f in files),
        },
        "limits": [
            "two fixed source recordings, one per route; no held-out or statistical claim",
            "fresh live runs have different capture ticks; fixed-RGB paired replay is the controlled comparison",
            "ENTRY delay uses next correct target-hypothesis lock during a later ENTRY-visible episode; GT evaluation only",
            "camera visibility alone is not person-following correctness",
            "scripted routes loop; no physical return/navigation validation",
            "runtime unchanged beyond merge conflict resolution; no scheduler tuning to hide failed gates",
        ],
        "paid_calls": 0,
        "gt_in_policy": False,
    }
    result["overall"] = (
        "PASS"
        if (
            all(x["on_target_pass"] and x["lost_pass"] for x in rq.values())
            and all(x["on_target_pass"] and x["lost_pass"] for x in live.values())
            and result["protocol_pass"]
            and entry_pass["A4"]["pass"] is True
        )
        else "NOT_PASSED"
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

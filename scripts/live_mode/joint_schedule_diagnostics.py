"""Post-inference diagnostics. Never passes GT, clock fits or score labels into runtime policy."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def classify(row, response, available):
    processed = set(response["dets"])
    missing_visible = sorted(set(row["tVisible"]) - processed)
    target_observed = "T" in row["red_actors"]
    if row["status"] in ("TARGET_ABSENT", "TARGET_NOT_VISIBLE"):
        attribution = "OUTSIDE_VISIBLE_DENOMINATOR"
    elif row["status"] == "ON_TARGET":
        attribution = "ON_TARGET"
    elif target_observed:
        attribution = "TRACKER_DESPITE_TARGET_LIKE_RED_PROJECTION"
    elif missing_visible:
        attribution = "SKIPPED_VISIBLE_CAMERA_COUNTERFACTUAL_UNKNOWN"
    else:
        attribution = "DETECTOR_COLOR_OR_PROJECTION_TARGET_NOT_OBSERVED"
    return {
        **row,
        "processed": sorted(processed),
        "omitted": sorted(set(available) - processed),
        "skipped_visible": missing_visible,
        "target_like_red_observed": target_observed,
        "attribution": attribution,
    }


def paired_times(all_rows, adaptive_rows, tolerance=0.35):
    used, pairs = set(), []
    for b in adaptive_rows:
        choices = [
            (abs(a["tSec"] - b["tSec"]), i, a) for i, a in enumerate(all_rows) if i not in used
        ]
        if not choices:
            break
        delta, i, a = min(choices, key=lambda x: (x[0], x[1]))
        if delta <= tolerance:
            used.add(i)
            pairs.append(
                {
                    "all_tick": a["i"],
                    "adaptive_tick": b["i"],
                    "delta_s": delta,
                    "all_status": a["status"],
                    "adaptive_status": b["status"],
                    "all_target_observed": "T" in a["red_actors"],
                    "adaptive_target_observed": "T" in b["red_actors"],
                }
            )
    return {
        "tolerance_s": tolerance,
        "pairs": pairs,
        "unpaired_all": len(all_rows) - len(used),
        "unpaired_adaptive": len(adaptive_rows) - len(pairs),
        "status_pairs": dict(Counter(f"{p['all_status']}->{p['adaptive_status']}" for p in pairs)),
    }


def entry_diagnostics(raw, rows):
    result, previous, seen = [], False, False
    for i, tick in enumerate(raw["ticks"]):
        visible = "CAM_ENTRY" in tick["gt_visible"]
        if visible and not previous and seen:
            end = i
            while end < len(raw["ticks"]) and "CAM_ENTRY" in raw["ticks"][end]["gt_visible"]:
                end += 1
            episode = []
            for j in range(i, end):
                response = raw["infer"][j]
                gt = response.get("gt_xy")
                before = raw["infer"][j - 1]["tracking"].get("est_xy") if j else None
                candidates = [
                    d["est_xy"]
                    for ds in response["dets"].values()
                    for d in ds
                    if d.get("color") == "red"
                    and d.get("est_xy") is not None
                    and gt
                    and math.dist(d["est_xy"], gt) <= 1.5
                ]
                episode.append(
                    {
                        "tick": tick["tick"] if j == i else raw["ticks"][j]["tick"],
                        "tSec": rows[j]["tSec"],
                        "status": rows[j]["status"],
                        "target_like_red_count": len(candidates),
                        "previous_est_to_gt_m": math.dist(before, gt) if before and gt else None,
                        "nearest_target_candidate_to_previous_est_m": min(
                            (math.dist(p, before) for p in candidates), default=None
                        )
                        if before
                        else None,
                        "processed": list(response["dets"]),
                    }
                )
            lock = next((j for j in range(i, end) if rows[j]["status"] == "ON_TARGET"), None)
            result.append(
                {
                    "start_tick": tick["tick"],
                    "start_s": rows[i]["tSec"],
                    "target_lock_ms": None
                    if lock is None
                    else raw["infer"][lock]["t_resp"] - tick["t_capture"],
                    "censored": lock is None,
                    "episode": episode,
                }
            )
        previous = visible
        seen = seen or visible
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--source",
        type=Path,
        required=True,
        help="frozen C latency folder with original raw and t1 rows",
    )
    ap.add_argument(
        "--baseline", type=Path, required=True, help="old-policy replay on the frozen fresh sources"
    )
    ap.add_argument(
        "--recent", type=Path, required=True, help="new-policy replay on the same sources"
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = {x["label"]: x["rows"] for x in json.loads((a.source / "t1_rows.json").read_text())}
    outputs, entry = {}, {}
    for label, rr in rows.items():
        raw = json.loads((a.source / f"{label}.t1raw.json").read_text())
        dd = [
            classify(row, response, raw["cfg"]["cams"])
            for row, response in zip(rr, raw["infer"], strict=True)
        ]
        outputs[label] = {"counts": dict(Counter(r["attribution"] for r in dd)), "ticks": dd}
        entry[label] = entry_diagnostics(raw, rr)
    comparisons = {}
    for cohort, path in [("old_policy", a.baseline), ("recent_red", a.recent)]:
        aa = {r["label"]: r["rows"] for r in json.loads((path / "all/t1_rows.json").read_text())}
        bb = {
            r["label"]: r["rows"] for r in json.loads((path / "adaptive/t1_rows.json").read_text())
        }
        comparisons[cohort] = {
            label: [
                {"tick": x["i"], "tSec": x["tSec"], "all": x["status"], "adaptive": y["status"]}
                for x, y in zip(aa[label], bb[label], strict=True)
                if x["status"] != y["status"]
            ]
            for label in aa
        }
    inputs = [
        a.source / "t1_rows.json",
        *a.source.glob("*.t1raw.json"),
        a.baseline / "quality.json",
        a.recent / "quality.json",
    ]
    result = {
        "observed": outputs,
        "same_rgb_tick_counterfactual": comparisons,
        "post_score_clock_alignment_B4": paired_times(rows["all-B4"], rows["adaptive-B4"]),
        "entry": entry,
        "inputs": [
            {
                "name": p.name,
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in inputs
        ],
        "limits": [
            "GT and clock fitting are evaluation only; all policy runs finish before this script",
            "missing-camera detections cannot be reconstructed from the adaptive run",
            "nearest-time joins are descriptive, never same-RGB causal evidence",
            "target-like red projection is the existing engineering proxy, not confirmed identity",
        ],
        "gt_in_policy": False,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "counts": {k: v["counts"] for k, v in outputs.items()},
                "same_tick": comparisons,
                "matched_B4": len(result["post_score_clock_alignment_B4"]["pairs"]),
                "alignment_statuses": result["post_score_clock_alignment_B4"]["status_pairs"],
                "entry": {
                    k: [{kk: vv for kk, vv in e.items() if kk != "episode"} for e in v]
                    for k, v in entry.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

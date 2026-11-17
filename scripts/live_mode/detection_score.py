"""Evaluation only: preserve detect_sweep.mjs highest-IoU-then-score acceptance metric."""

import argparse
import json
from pathlib import Path

from amidst.live_mode.detector import DEFAULT_CAMERA_MIN_SCORES, DEFAULT_MIN_SCORE


def iou(a, b):
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union if union > 0 else 0


def score_recording(labels, detections):
    labels = [
        r
        for r in labels
        if round(r["inside"], 2) >= 0.6 and round(r["gt_h_px"], 1) >= 16 and r["id"] in detections
    ]

    def score(rows, thresholds):
        hits = fp = red_fp = 0
        has_colors = True
        for r in rows:
            threshold = thresholds(r["cam"])
            ds = detections[r["id"]]["dets"]
            has_colors = has_colors and all("color" in d for d in ds)
            best = max(ds, key=lambda d: iou(d["bbox"], r["bbox"]), default=None)
            # The historical sweep rounds stored IoU/score before calculating its summary.
            hits += bool(
                best
                and round(iou(best["bbox"], r["bbox"]), 2) >= 0.3
                and round(best["score"], 3) >= threshold
            )
            fps = [
                d
                for d in ds
                if iou(d["bbox"], r["bbox"]) < 0.1 and round(d["score"], 2) >= threshold
            ]
            fp += len(fps)
            red_fp += sum(d.get("color") == "red" for d in fps)
        n = len(rows)
        return {
            "n": n,
            "hits": hits,
            "rate": hits / n if n else None,
            "fp_per_frame": fp / n if n else None,
            "red_fp_per_frame": red_fp / n if n and has_colors else None,
        }

    def table(thresholds):
        empty = [v for k, v in detections.items() if k.startswith("empty_")]
        return {
            "all": score(labels, thresholds),
            "by_camera": {
                c: score([r for r in labels if r["cam"] == c], thresholds)
                for c in sorted({r["cam"] for r in labels})
            },
            "empty_fp_per_frame": sum(
                sum(d["score"] >= thresholds(k.removeprefix("empty_")) for d in v["dets"])
                for k, v in detections.items()
                if k.startswith("empty_")
            )
            / len(empty)
            if empty
            else None,
        }

    return {
        "metric": "detect_sweep.mjs: highest IoU before score threshold; IoU/score rounded 2/3 decimals; FP scores rounded 2 decimals",
        "thresholds": {
            str(t): table(lambda cam, t=t: t)
            for t in [0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35]
        },
        "calibrated_profile": {
            "min_score": DEFAULT_MIN_SCORE,
            "camera_min_scores": DEFAULT_CAMERA_MIN_SCORES,
            **table(lambda c: DEFAULT_CAMERA_MIN_SCORES.get(c, DEFAULT_MIN_SCORE)),
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, required=True)
    a = ap.parse_args()
    labels = json.loads((a.work / "recording/evaluation_labels.json").read_text())
    for p in sorted((a.work / "diagnosis").glob("*.detections.json")):
        out = p.with_name(p.name.replace(".detections.json", ".summary.json"))
        prior = json.loads(out.read_text())
        prior.update(score_recording(labels, json.loads(p.read_text())))
        out.write_text(json.dumps(prior, indent=2, allow_nan=False))
        print(p.stem, prior["thresholds"]["0.35"]["all"], prior["calibrated_profile"]["all"])


if __name__ == "__main__":
    main()

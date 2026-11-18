"""Offline RGB-only detection followed by isolated evaluation of frozen N6 frames.

No GT is passed to LiveDetector. The label file is opened only after inference.
Exploratory transforms are explicit and do not change the live configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

from amidst.live_mode.detector import LiveDetector
from amidst.live_mode.color import judge
from detection_score import score_recording


def iou(a, b):
    w, h = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area
    return area / union if union > 0 else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument(
        "--variant",
        choices=["stretch", "letterbox", "bright", "highres", "deployed"],
        default="stretch",
    )
    ap.add_argument("--only-three", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    det = LiveDetector(
        a.models, device="mps", resize_mode="letterbox" if a.variant == "deployed" else "stretch"
    )
    paths = sorted((a.recording / "rgb").glob("*.jpg"))
    paths = [p for p in paths if p.stem.endswith("_640") == (a.variant == "highres")]
    if a.only_three:
        paths = [
            p
            for p in paths
            if any(c in p.name for c in ["CAM_ENTRY", "CAM_R101_IN", "CAM_EXT_CAR"])
        ]
    results, times = {}, []
    for offset in range(0, len(paths), 3):
        files = paths[offset : offset + 3]
        imgs = [Image.open(p).convert("RGB") for p in files]
        if a.variant == "bright":
            imgs = [ImageEnhance.Brightness(im).enhance(1.5) for im in imgs]
        if a.variant == "letterbox":
            padded = []
            for im in imgs:
                canvas = Image.new("RGB", (640, 640), (114, 114, 114))
                canvas.paste(im.resize((640, 360), Image.Resampling.BILINEAR), (0, 140))
                padded.append(canvas)
            inp = padded
        else:
            inp = imgs
        t0 = time.perf_counter()
        ds, timing = det.detect(inp)
        times.append({"total_ms": (time.perf_counter() - t0) * 1000, **timing})
        for p, im, lst in zip(files, imgs, ds):
            for d in lst:
                if a.variant == "letterbox":
                    x0, y0, x1, y1 = d["bbox"]
                    d["bbox"] = [x0 / 2, (y0 - 140) / 2, x1 / 2, (y1 - 140) / 2]
                elif a.variant == "highres":
                    d["bbox"] = [v / 2 for v in d["bbox"]]
                color_image = im.resize((320, 180)) if a.variant == "highres" else im
                d.update(judge(np.asarray(color_image), d["bbox"]))
            results[p.stem.removesuffix("_640")] = {
                "dets": lst,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
        if offset % 150 == 0:
            print(f"{a.variant}: {offset}/{len(paths)}", flush=True)
    # Only now read evaluation labels; GT never reaches the detector or its preprocessing.
    labels = json.loads((a.recording / "evaluation_labels.json").read_text())
    summary = {
        "detector": det.metadata,
        "variant": a.variant,
        **score_recording(labels, results),
        "timing_ms": {
            k: {
                q: float(np.percentile([r[k] for r in times[4:]], v))
                for q, v in [("p50", 50), ("p95", 95)]
            }
            for k in times[0]
        },
    }
    (a.out / f"{a.variant}.detections.json").write_text(json.dumps(results))
    (a.out / f"{a.variant}.summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()

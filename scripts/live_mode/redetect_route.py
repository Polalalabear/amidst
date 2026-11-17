"""Run RGB-only inference on saved HTTP packets, then attach results to offline evaluation records."""

import argparse
import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image

from amidst.live_mode.color import judge
from amidst.live_mode.detector import DEFAULT_CAMERA_MIN_SCORES, DEFAULT_MIN_SCORE, LiveDetector


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recording", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--models", type=Path, required=True)
    a = ap.parse_args()
    detector = LiveDetector(a.models, device="mps")
    results = {}
    for folder in sorted((a.recording / "packets").iterdir()):
        results[folder.name] = {}
        for p in sorted(folder.glob("*.bin"), key=lambda p: int(p.stem)):
            data = p.read_bytes()
            n = struct.unpack("<I", data[:4])[0]
            header = json.loads(data[4 : 4 + n])  # only camera/time/byte lengths, no GT
            offset = 4 + n
            imgs = []
            for fr in header["frames"]:
                imgs.append(
                    Image.open(io.BytesIO(data[offset : offset + fr["bytes"]])).convert("RGB")
                )
                offset += fr["bytes"]
            dets, _ = detector.detect(imgs)
            out = {}
            for fr, im, ds in zip(header["frames"], imgs, dets):
                threshold = DEFAULT_CAMERA_MIN_SCORES.get(fr["cam"], DEFAULT_MIN_SCORE)
                ds = [d for d in ds if d["score"] >= threshold]
                for d in ds:
                    d.update(judge(np.asarray(im), d["bbox"]))
                out[fr["cam"]] = ds
            results[folder.name][header["tick"]] = out
        print(folder.name, len(results[folder.name]), flush=True)
    # Separate scoring phase: now open records that contain evaluation-only ground truth.
    a.out.mkdir(parents=True, exist_ok=True)
    for p in sorted((a.recording / "raw").glob("*.t1raw.json")):
        raw = json.loads(p.read_text())
        for response in raw["infer"]:
            response["dets"] = results[raw["label"]][response["tick"]]
        raw["redetection"] = {
            "resize": detector.resize_mode,
            "min_score": DEFAULT_MIN_SCORE,
            "camera_min_scores": DEFAULT_CAMERA_MIN_SCORES,
            "gt_in_detector": False,
        }
        (a.out / p.name).write_text(json.dumps(raw))


if __name__ == "__main__":
    main()

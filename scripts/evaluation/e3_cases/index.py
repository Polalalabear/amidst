"""#652 pixel-only RT-DETR index producer; uses the existing index format/builder.

Reads only hash-bound wire receipts and camera JPEGs, never case/GT/scenario files.
The Agent and rule must both use rgb/<case> PNGs and this same frozen index.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.detection_index import build_detection_index, content_hash, write_index
from amidst.q1q5.hsv_color import HSVConfig


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


class PixelRun:
    def __init__(self, root, case_id):
        from PIL import Image
        self.root = root
        wire = json.loads((root / f"{case_id}.replay1.wire.json").read_text())
        self.camera_ids = tuple(f["cam"] for f in wire[0]["frames"])
        if len(self.camera_ids) != 8 or len(set(self.camera_ids)) != 8:
            raise ValueError("EIGHT_CAMERAS_REQUIRED")
        self.rows = {}
        # Last capture is the endpoint guard sample, outside [0, case duration).
        for i, capture in enumerate(wire[:-1]):
            if capture["tick"] != i or capture["t_capture_ms"] != i * 200:
                raise ValueError("INVALID_CAPTURE_GRID")
            if [f["cam"] for f in capture["frames"]] != list(self.camera_ids):
                raise ValueError("INCOMPLETE_CAMERA_GRID")
            for frame in capture["frames"]:
                rel = Path(frame["path"])
                if rel.is_absolute() or ".." in rel.parts or rel.parts[:2] != ("pixels", case_id):
                    raise ValueError("UNSAFE_PIXEL_PATH")
                raw = (root / rel).read_bytes()
                if sha(raw) != frame["sha256"]:
                    raise ValueError("JPEG_HASH_MISMATCH")
                target = Path("rgb") / case_id / frame["cam"] / f"{i:05d}.png"
                image = Image.open(io.BytesIO(raw)).convert("RGB")
                if image.size != (320, 180):
                    raise ValueError("SOURCE_DIMENSIONS")
                png = io.BytesIO(); image.save(png, format="PNG")
                png_bytes = png.getvalue()
                destination = root / target
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and destination.read_bytes() != png_bytes:
                    raise ValueError("PNG_OVERWRITE_REFUSED")
                if not destination.exists():
                    destination.write_bytes(png_bytes)
                # PNG is lossless relative to the exact decoded camera JPEG pixels.
                if Image.open(io.BytesIO(png_bytes)).convert("RGB").tobytes() != image.tobytes():
                    raise ValueError("PIXEL_CONVERSION_MISMATCH")
                image.close()
                self.rows[frame["cam"], i] = {
                    "camera_id": frame["cam"], "frame_index": i, "timestamp_s": i / 5,
                    "file_sha256": sha(png_bytes), "relative_path": target.as_posix(),
                    "source_jpeg_sha256": frame["sha256"],
                }
        count = len(wire) - 1
        rgb = {"schema_version": "controlled-scene.rgb-index.v1", "run_id": case_id,
               "clock_id": f"live-{case_id}-5hz-v1", "records": [self.rows[k] for k in sorted(self.rows)],
               "missing": [], "provenance": {"gt_read": False, "conversion": "JPEG_DECODE_TO_LOSSLESS_PNG"}}
        rgb_path = root / "rgb" / case_id / "rgb_index.json"
        dump(rgb_path, rgb)
        self.files = {"rgb_index": rgb}
        self.manifest = {"scene_id": "r004-live-n6", "run_id": case_id, "clock_id": rgb["clock_id"],
                         "sampling": {"fps": 5, "duration_s": count / 5,
                                      "sample_count_per_camera": count, "image_size_px": [320, 180]},
                         "allowlist": [{"role": "rgb_index", "file_sha256": sha(rgb_path.read_bytes())}]}

    def rgb_record(self, camera, frame):
        return self.rows.get((camera, frame))

    def read_rgb(self, camera, frame):
        row = self.rows[camera, frame]
        raw = (self.root / row["relative_path"]).read_bytes()
        if sha(raw) != row["file_sha256"]:
            raise ValueError("RGB_PIN_MISMATCH")
        return raw


class FrozenPredictions:
    def __init__(self, detector, rows):
        self.class_labels = detector.base.class_labels
        self.metadata = copy.deepcopy(detector.metadata)
        self.metadata["config_sha256"] = content_hash({"base": self.metadata["config_sha256"],
             "preprocess": self.metadata["input_preprocess"], "device": self.metadata["device"],
             "scope": "PERSON_ONLY", "minimum_retained_score": .05})
        self.rows = rows
        self.index = 0

    def __call__(self, image):
        row = self.rows[self.index]
        if sha(image.tobytes()) != row["decoded_rgb_sha256"]:
            raise ValueError("PREDICTION_PIXEL_MISMATCH")
        self.index += 1
        return [{"class_id": 0, "bbox_xyxy_px": d["bbox"], "score": d["score"]}
                for d in row["detections"]]


def main():
    from PIL import Image
    from amidst.live_mode.detector import LiveDetector
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument("--cases", nargs="+", required=True)
    ap.add_argument("--device", default="mps", choices=["cpu", "mps"])
    args = ap.parse_args()
    detector = LiveDetector(args.models, device=args.device, threads=4, resize_mode="letterbox")
    # Existing D131 upper-HSV evidence format; LIVE B1's area-ratio judge is
    # separately replayed with its existing .2 threshold, never relabelled as this method.
    hsv = HSVConfig("upper-hsv-v1", .5, 8, .2, .2, .2, .6, .3, 12,
                    {"red": [[.95, .05]], "blue": [[.5, .72]]})
    for case_id in args.cases:
        output = args.root / "indexes" / case_id
        if output.exists():
            raise ValueError(f"INDEX_ALREADY_EXISTS:{case_id}")
        started = time.monotonic()
        run = PixelRun(args.root, case_id)
        raw_path = args.root / "predictions" / f"{case_id}.jsonl"
        prior = [json.loads(x) for x in raw_path.read_text().splitlines()] if raw_path.exists() else []
        ordered = [run.rows[k] for k in sorted(run.rows)]
        if len(prior) > len(ordered) or any(p["rgb_file_sha256"] != r["file_sha256"] for p, r in zip(prior, ordered)):
            raise ValueError("PREDICTION_CACHE_SOURCE_MISMATCH")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        predictions = list(prior)
        with raw_path.open("a") as stream:
            for offset in range(len(prior), len(ordered), 4):
                rows = ordered[offset:offset + 4]
                images = [Image.open(args.root / r["relative_path"]).convert("RGB") for r in rows]
                detections, _ = detector.detect(images)
                for row, image, dets in zip(rows, images, detections, strict=True):
                    p = {"rgb_file_sha256": row["file_sha256"], "decoded_rgb_sha256": sha(image.tobytes()),
                         "camera_id": row["camera_id"], "frame_index": row["frame_index"], "detections": dets}
                    stream.write(json.dumps(p, allow_nan=False) + "\n")
                    predictions.append(p); image.close()
                stream.flush()
                if offset % 100 == 0:
                    print(case_id, "detected", offset, "/", len(ordered), flush=True)
        predictor = FrozenPredictions(detector, predictions)
        artifact = build_detection_index(run, predictor, scene_revision="r004-live-e3-v1", stride_samples=1,
               index_grid_origin_frame=0, index_score_floor=.05, color_config=hsv)
        if predictor.index != len(ordered):
            raise ValueError("INDEX_PREDICTION_COVERAGE")
        write_index(artifact, output)
        dump(output / "production.json", {"case_id": case_id, "frames": len(ordered),
             "elapsed_s": time.monotonic() - started, "device": args.device,
             "index_file_sha256": sha((output / "detection_index.json").read_bytes()),
             "records_file_sha256": artifact.manifest["records_file_sha256"],
             "stats": artifact.stats, "gt_read": False})
        print("INDEX_COMPLETE", case_id, len(ordered), flush=True)


if __name__ == "__main__":
    main()

"""Offline, source-bound detection index producer (#86 §4). No query-time inference."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from amidst.q1q5.hsv_color import HSVConfig, summarize_upper_hsv


class IndexIntegrityError(ValueError):
    code = "DataIntegrityError"


def observed(observer, stage, operation):
    return observer(stage, operation) if observer is not None else operation()


def content_hash(value, exclude=()):
    return hashlib.sha256(json.dumps(
        {k: v for k, v in value.items() if k not in exclude}, sort_keys=True,
        separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode()).hexdigest()


def _ranges(cells):
    result = []
    for a, b in cells:
        if result and result[-1][1] == a:
            result[-1][1] = b
        else:
            result.append([a, b])
    return result


@dataclass(frozen=True)
class IndexArtifact:
    manifest: dict
    records_bytes: bytes
    stats: dict


def build_detection_index(run, predictor, *, scene_revision: str, stride_samples: int,
                          index_grid_origin_frame: int, index_score_floor: float,
                          color_config: HSVConfig, observer=None) -> IndexArtifact:
    """Consume the existing RGB_PLAYBACK SafeRun adapter (or a SYNTHETIC test double).

    predictor(image) -> iterable of {class_id, bbox_xyxy_px, score}; predictor must
    expose actual class_labels and detector metadata. No model or threshold fallback.
    Only one source PNG is decoded at a time. Missing pins fail before model calls.
    """
    from PIL import Image

    if (type(stride_samples) is not int or stride_samples < 1
            or type(index_grid_origin_frame) is not int or index_grid_origin_frame < 0
            or type(index_score_floor) not in (int, float)
            or not math.isfinite(index_score_floor) or not 0 <= index_score_floor <= 1):
        raise IndexIntegrityError("Explicit valid sampling/score parameters required")
    sampling = run.manifest["sampling"]
    interval = Fraction(1_000_000, 1) / Fraction(str(sampling["fps"]))
    duration = Fraction(str(sampling["duration_s"])) * 1_000_000
    count = sampling["sample_count_per_camera"]
    if interval.denominator != 1 or duration.denominator != 1 or count * interval != duration:
        raise IndexIntegrityError("Invalid source grid")
    interval, duration = int(interval), int(duration)
    if index_grid_origin_frame >= count:
        raise IndexIntegrityError("Empty index grid")
    step = interval * stride_samples
    labels = tuple(predictor.class_labels)
    detector = copy.deepcopy(predictor.metadata)
    if (len(set(labels)) != len(labels) or not labels
            or detector["load"]["num_classes"] != len(labels)
            or detector["load"]["strict"] is not True
            or detector["class_map"]["num_classes"] != len(labels)
            or detector["nms"] != {"applied": False, "iou": None}):
        raise IndexIntegrityError("Detector/class-map metadata mismatch")
    detector["index_score_floor"] = index_score_floor
    detector["config_sha256"] = content_hash({
        "model_config_sha256": detector["config_sha256"], "index_score_floor": index_score_floor,
        "nms": detector["nms"],
    })
    class_body = {"version": detector["class_map"]["version"], "labels": list(labels)}
    if detector["class_map"]["content_sha256"] != content_hash(class_body):
        raise IndexIntegrityError("Class map content hash mismatch")
    rgb_pin = next(e["file_sha256"] for e in run.manifest["allowlist"]
                   if e["role"] == "rgb_index")
    missing = {(r["camera_id"], r["frame_index"]) for r in run.files["rgb_index"]["missing"]}
    method_hash = color_config.content_sha256
    vocabulary = {"version": color_config.version, "labels": list(color_config.bands)}
    vocabulary["content_sha256"] = content_hash(vocabulary)
    manifest = {"schema_version": "q-demo.detection-index.v1", "scene_id": run.manifest["scene_id"],
                "scene_revision": scene_revision, "run_id": run.manifest["run_id"],
                "clock_id": run.manifest["clock_id"], "rgb_index_sha256": rgb_pin,
                "detector": detector,
                "color_method": {"version": color_config.version, "content_sha256": method_hash,
                                 "applies_to_classes": ["person"], "color_vocabulary": vocabulary},
                "sampling": {"policy": "EVERY_NTH_SAMPLE", "stride_samples": stride_samples,
                             "per_camera": []},
                "provenance": {"producer": "q1q5-detection-indexer", "producer_version": "1",
                               "gt_read": False}}
    records, calls = [], 0
    for camera in sorted(run.camera_ids):
        inferred, absent = [], []
        for i in range(count):
            timestamp = i * interval
            meta = run.rgb_record(camera, i)
            if meta is None and (camera, i) not in missing:
                raise IndexIntegrityError("Unlisted source frame is not MISSING")
            if meta is not None and (Fraction(str(meta["timestamp_s"])) * 1_000_000 != timestamp
                                     or (camera, i) in missing):
                raise IndexIntegrityError("Source grid/pin mismatch")
            row = {"frame_ref": f"frame:{manifest['run_id']}:{camera}:{i}", "camera_id": camera,
                   "frame_index": i, "timestamp_us": timestamp,
                   "rgb_file_sha256": meta["file_sha256"] if meta else None,
                   "frame_state": "NOT_SAMPLED", "state_reason": None, "detections": None}
            selected = i >= index_grid_origin_frame and (i-index_grid_origin_frame) % stride_samples == 0
            if selected:
                cell = [timestamp, min(duration, timestamp + step)]
                if meta is None:
                    row["frame_state"] = "MISSING"
                    absent.append({"range_us": cell, "reason": "MISSING"})
                else:
                    raw = observed(observer, "rgb_read", lambda: run.read_rgb(camera, i))
                    if raw is None or observed(observer, "rgb_hash", lambda: hashlib.sha256(raw).hexdigest()) != meta["file_sha256"]:
                        raise IndexIntegrityError("Pinned RGB missing or hash mismatch")
                    try:
                        with Image.open(io.BytesIO(raw)) as source:
                            if source.format != "PNG" or list(source.size) != sampling["image_size_px"]:
                                raise IndexIntegrityError("PNG/calibration dimensions mismatch")
                            image = observed(observer, "rgb_decode", lambda: source.convert("RGB"))
                    except OSError as exc:
                        raise IndexIntegrityError("Invalid pinned PNG") from exc
                    try:
                        calls += 1
                        predictions = list(predictor(image))
                    except RuntimeError:
                        row.update(frame_state="NOT_INFERRED", state_reason="DETECTOR_FAILED")
                        absent.append({"range_us": cell, "reason": "DETECTOR_FAILED"})
                    else:
                        detections = []
                        for prediction in predictions:
                            cid, box, score = (prediction["class_id"], prediction["bbox_xyxy_px"],
                                               prediction["score"])
                            if (type(cid) is not int or not 0 <= cid < len(labels)
                                    or type(score) not in (int, float) or not math.isfinite(score)
                                    or not 0 <= score <= 1 or len(box) != 4
                                    or any(type(x) not in (int, float) or not math.isfinite(x) for x in box)
                                    or box[2] <= box[0] or box[3] <= box[1]):
                                raise IndexIntegrityError("Invalid detector output")
                            if score < index_score_floor:
                                continue
                            color = observed(observer, "upper_hsv", lambda: summarize_upper_hsv(image, box, color_config)) if labels[cid] == "person" else None
                            detections.append({"class_id": cid, "class_label": labels[cid],
                                               "bbox_xyxy_px": list(map(float, box)),
                                               "score": float(score), "color": color})
                        detections.sort(key=lambda d: (-d["score"], tuple(d["bbox_xyxy_px"])))
                        row.update(frame_state="INFERRED", detections=detections)
                        inferred.append(cell)
                    image.close()
            records.append(row)
        manifest["sampling"]["per_camera"].append({
            "camera_id": camera, "sampled_ranges_us": [[index_grid_origin_frame * interval, duration]],
            "inferred_ranges_us": _ranges(inferred), "not_inferred": absent,
            "source_frame_interval_us": interval, "stride_samples": stride_samples,
            "index_interval_us": step, "index_grid_origin_frame": index_grid_origin_frame,
        })
    if color_config.content_sha256 != method_hash:
        raise IndexIntegrityError("Color configuration mutated during production")
    key = content_hash(manifest)[:16]
    manifest["index_id"] = f"detidx:{scene_revision}:{manifest['run_id']}:{key}"
    for row in records:
        for ordinal, detection in enumerate(row["detections"] or []):
            detection["observation_id"] = f"obs:{key}:{row['camera_id']}:{row['frame_index']}:{ordinal}"
    raw = observed(observer, "index_encode", lambda: b"".join((json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                              allow_nan=False) + "\n").encode() for r in records))
    manifest.update(records_ref="detection_index.records.jsonl",
                    records_file_sha256=hashlib.sha256(raw).hexdigest())
    manifest["content_sha256"] = content_hash(manifest, ("index_id",))
    return IndexArtifact(manifest, raw, {"model_calls": calls, "frames": len(records)})


def write_index(artifact: IndexArtifact, output: Path) -> None:
    """A new directory only; publish the manifest last, never overwrite an index."""
    output.mkdir(parents=True, exist_ok=False)
    with (output / "detection_index.records.jsonl").open("xb") as stream:
        stream.write(artifact.records_bytes)
    with (output / "detection_index.json").open("x") as stream:
        json.dump(artifact.manifest, stream, sort_keys=True, ensure_ascii=True, allow_nan=False)


class OfficialRTDetrR18:
    """Strict official R18 adapter. Constructor performs real model loading.

    Caller supplies trusted hashes for every Python source file in the preexisting
    official rtdetr_pytorch tree. No download, training imports or alternate model.
    """

    def __init__(self, source_root: Path, weights: Path, *, source_hashes: dict,
                 seed: int, threads: int, observer=None):
        self.observer = observer
        import ast
        import importlib
        import sys
        import types

        expected_weight = "3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0"
        source_root = source_root.resolve()
        if any(p.is_symlink() for p in (source_root / "src").rglob("*")):
            raise IndexIntegrityError("Symlinked model code is forbidden")
        actual = {p.relative_to(source_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (source_root / "src").rglob("*.py") if not p.is_symlink()}
        if not actual or actual != source_hashes or "src" in sys.modules:
            raise IndexIntegrityError("Official source hashes missing/mismatched or namespace busy")
        digest = hashlib.sha256()
        with weights.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_weight:
            raise IndexIntegrityError("Official weight hash mismatch")
        for name, relative in [("src", "src"), ("src.core", "src/core"),
                               ("src.nn", "src/nn"), ("src.nn.backbone", "src/nn/backbone"),
                               ("src.zoo", "src/zoo"), ("src.zoo.rtdetr", "src/zoo/rtdetr")]:
            module = types.ModuleType(name)
            module.__path__ = [str(source_root / relative)]
            sys.modules[name] = module
        utils = importlib.import_module("src.core.yaml_utils")
        sys.modules["src.core"].register = utils.register
        PResNet = importlib.import_module("src.nn.backbone.presnet").PResNet
        HybridEncoder = importlib.import_module("src.zoo.rtdetr.hybrid_encoder").HybridEncoder
        Transformer = importlib.import_module("src.zoo.rtdetr.rtdetr_decoder").RTDETRTransformer
        RTDETR = importlib.import_module("src.zoo.rtdetr.rtdetr").RTDETR
        Post = importlib.import_module("src.zoo.rtdetr.rtdetr_postprocessor").RTDETRPostProcessor
        import torch
        import torchvision

        if type(seed) is not int or type(threads) is not int or threads < 1:
            raise IndexIntegrityError("Explicit seed and CPU thread count required")
        torch.set_num_threads(threads)
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True)
        model = RTDETR(PResNet(depth=18, return_idx=[1, 2, 3], freeze_at=-1,
                               freeze_norm=False, pretrained=False),
                       HybridEncoder(in_channels=[128, 256, 512], expansion=0.5,
                                     eval_spatial_size=[640, 640]),
                       Transformer(num_classes=80, feat_channels=[256, 256, 256],
                                   num_decoder_layers=3, eval_spatial_size=[640, 640]))
        checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
        state = checkpoint["ema"]["module"] if "ema" in checkpoint else checkpoint["model"]
        if state["decoder.enc_score_head.weight"].shape[0] != 80:
            raise IndexIntegrityError("Weight classification head mismatch")
        model.load_state_dict(state, strict=True)
        self.model = model.deploy().cpu().eval()
        self.post = Post(num_classes=80, remap_mscoco_category=False).deploy()
        class_path = source_root / "src/data/coco/coco_dataset.py"
        tree = ast.parse(class_path.read_text())
        labels = next(ast.literal_eval(node.value) for node in tree.body
                      if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
                          and t.id == "mscoco_category2name" for t in node.targets))
        self.class_labels = tuple(labels.values())
        if len(self.class_labels) != 80 or self.class_labels[0] != "person":
            raise IndexIntegrityError("Official class map mismatch")
        self.metadata = {
            "family": "RT-DETR", "variant": "rtdetr_r18vd_dec3_6x_coco_from_paddle",
            "framework": "torch", "framework_version": torch.__version__,
            "torchvision_version": torchvision.__version__, "weights_file": weights.name,
            "weights_file_bytes": weights.stat().st_size, "weights_file_sha256": expected_weight,
            "weights_source": "https://github.com/lyuwenyu/storage/releases/download/v0.1/"
                              "rtdetr_r18vd_dec3_6x_coco_from_paddle.pth",
            "weights_license": {"code": "Apache-2.0", "training_data_terms": "UNKNOWN"},
            "code_source": {"repo": "lyuwenyu/RT-DETR",
                            "commit": "df2a96c8c3a098567a1149bf0248da6efe6d495d"},
            "load": {"strict": True, "num_classes": 80},
            "class_map": {"version": "coco80-v1", "num_classes": 80,
                          "source_file_sha256": hashlib.sha256(class_path.read_bytes()).hexdigest(),
                          "content_sha256": content_hash({"version": "coco80-v1",
                                                         "labels": list(self.class_labels)})},
            "input_preprocess": {"resize_policy": "PIL_BILINEAR_STRETCH",
                                 "input_size_px": [640, 640], "color": "RGB",
                                 "scale": "1/255", "dtype": "FP32"},
            "config_sha256": content_hash({"source_files": source_hashes, "seed": seed,
                                           "threads": threads, "variant": "official-r18"}),
            "postprocess": {"top_k_queries": 300}, "nms": {"applied": False, "iou": None},
            "device": "cpu",
        }

    def __call__(self, image):
        import numpy as np
        import torch
        from PIL import Image
        def preprocess():
            tensor = torch.from_numpy(np.array(image.resize((640, 640), Image.Resampling.BILINEAR)))
            return tensor.permute(2, 0, 1).float().div(255)[None]
        tensor = observed(self.observer, "detector_preprocess", preprocess)
        with torch.inference_mode():
            output = observed(self.observer, "detector_forward", lambda: self.model(tensor))
            if output["pred_logits"].shape[-1] != len(self.class_labels):
                raise IndexIntegrityError("Model output dimension mismatch")
            labels, boxes, scores = observed(self.observer, "detector_postprocess", lambda: self.post(output, torch.tensor([[image.width, image.height]])))
        return [{"class_id": int(label), "bbox_xyxy_px": box.tolist(), "score": float(score)}
                for label, box, score in zip(labels[0], boxes[0], scores[0], strict=True)]

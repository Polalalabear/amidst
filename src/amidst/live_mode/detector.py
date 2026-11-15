"""Batched RT-DETR R18 person detector for virtual-camera frames (spike).

Reuses the strict official adapter from amidst.q1q5.detection_index for loading (hash-checked
weights and source), then runs batched forward passes. For the spike the model may be moved to MPS
and deterministic mode is switched off for speed; this is NOT the pinned engineering configuration.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np

PERSON = 0


def _hashes(source: Path) -> dict:
    return {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (source / "src").rglob("*.py") if not p.is_symlink()}


class LiveDetector:
    def __init__(self, models_root: Path, device: str = "cpu", threads: int = 4):
        import torch
        from amidst.q1q5.detection_index import OfficialRTDetrR18

        source = models_root / "source" / "rtdetr_pytorch"
        weights = models_root / "rtdetr_r18vd_dec3_6x_coco_from_paddle.pth"
        self.base = OfficialRTDetrR18(source, weights, source_hashes=_hashes(source), seed=7, threads=threads)
        torch.use_deterministic_algorithms(False)
        self.torch = torch
        self.device = device
        if device != "cpu":
            self.base.model.to(device)
            self.base.post.to(device)
        self.threshold = 0.05  # keep low; callers filter (rates are reported per threshold)

    def detect(self, images: list) -> tuple[list[list[dict]], dict]:
        """images: list of PIL RGB images (any size). Returns person detections per image."""
        from PIL import Image
        torch = self.torch
        t0 = time.perf_counter()
        batch = np.stack([np.asarray(im.resize((640, 640), Image.Resampling.BILINEAR)) for im in images])
        x = torch.from_numpy(batch).permute(0, 3, 1, 2).float().div(255).to(self.device)
        sizes = torch.tensor([[im.width, im.height] for im in images], device=self.device)
        t1 = time.perf_counter()
        with torch.inference_mode():
            out = self.base.model(x)
            labels, boxes, scores = self.base.post(out, sizes)
            if self.device != "cpu":
                getattr(torch, self.device).synchronize()
        t2 = time.perf_counter()
        labels, boxes, scores = labels.cpu().numpy(), boxes.cpu().numpy(), scores.cpu().numpy()
        res = []
        for i in range(len(images)):
            keep = (labels[i] == PERSON) & (scores[i] >= self.threshold)
            res.append([{"bbox": boxes[i][j].tolist(), "score": float(scores[i][j])}
                        for j in np.nonzero(keep)[0]])
        return res, {"preprocess": (t1 - t0) * 1e3, "forward": (t2 - t1) * 1e3,
                     "post": (time.perf_counter() - t2) * 1e3}

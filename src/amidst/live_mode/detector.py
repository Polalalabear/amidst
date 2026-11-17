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
DEFAULT_MIN_SCORE = 0.15
DEFAULT_CAMERA_MIN_SCORES = {'CAM_ENTRY': 0.05}


def prepare_image(image, resize_mode: str):
    """Return square model RGB and its inverse transform; no camera/GT inputs."""
    from PIL import Image

    width, height = image.size
    if resize_mode == 'stretch':
        return image.resize((640, 640), Image.Resampling.BILINEAR), (width, height, 640, 640, 0, 0)
    if resize_mode != 'letterbox':
        raise ValueError(f'unknown resize_mode: {resize_mode}')
    scale = min(640 / width, 640 / height)
    rw, rh = max(1, round(width * scale)), max(1, round(height * scale))
    left, top = (640 - rw) // 2, (640 - rh) // 2
    canvas = Image.new('RGB', (640, 640), (114, 114, 114))
    canvas.paste(image.resize((rw, rh), Image.Resampling.BILINEAR), (left, top))
    return canvas, (width, height, rw, rh, left, top)


def source_box(box, transform):
    """Undo padding/scaling before HSV or projection; reject boxes wholly in padding."""
    width, height, rw, rh, left, top = transform
    x0, y0, x1, y1 = box
    result = [max(0.0, min(width, (x0-left)*width/rw)),
              max(0.0, min(height, (y0-top)*height/rh)),
              max(0.0, min(width, (x1-left)*width/rw)),
              max(0.0, min(height, (y1-top)*height/rh))]
    return result if result[2] > result[0] and result[3] > result[1] else None


def _hashes(source: Path) -> dict:
    return {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (source / "src").rglob("*.py") if not p.is_symlink()}


class LiveDetector:
    def __init__(self, models_root: Path, device: str = "cpu", threads: int = 4,
                 resize_mode: str = 'letterbox'):
        import torch
        from amidst.q1q5.detection_index import OfficialRTDetrR18

        source = models_root / "source" / "rtdetr_pytorch"
        weights = models_root / "rtdetr_r18vd_dec3_6x_coco_from_paddle.pth"
        self.base = OfficialRTDetrR18(source, weights, source_hashes=_hashes(source), seed=7, threads=threads)
        torch.use_deterministic_algorithms(False)
        self.torch = torch
        self.device = device
        if resize_mode not in ('letterbox', 'stretch'):
            raise ValueError(f'unknown resize_mode: {resize_mode}')
        self.resize_mode = resize_mode
        self.metadata = {**self.base.metadata, 'device': device,
                         'input_preprocess': {'resize_policy': resize_mode, 'input_size_px': [640, 640],
                                              'padding_rgb': [114, 114, 114] if resize_mode == 'letterbox' else None,
                                              'color': 'RGB', 'scale': '1/255', 'dtype': 'FP32'}}
        if device != "cpu":
            self.base.model.to(device)
            self.base.post.to(device)
        self.threshold = 0.05  # keep low; callers filter (rates are reported per threshold)

    def detect(self, images: list) -> tuple[list[list[dict]], dict]:
        """images: list of PIL RGB images (any size). Returns person detections per image."""
        torch = self.torch
        t0 = time.perf_counter()
        prepared = [prepare_image(im, self.resize_mode) for im in images]
        batch = np.stack([np.asarray(im) for im, _ in prepared])
        x = torch.from_numpy(batch).permute(0, 3, 1, 2).float().div(255).to(self.device)
        sizes = torch.tensor([[640, 640]] * len(images), device=self.device)
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
            lst = []
            for j in np.nonzero(keep)[0]:
                box = source_box(boxes[i][j].tolist(), prepared[i][1])
                if box is not None:
                    lst.append({"bbox": box, "score": float(scores[i][j])})
            res.append(lst)
        return res, {"preprocess": (t1 - t0) * 1e3, "forward": (t2 - t1) * 1e3,
                     "post": (time.perf_counter() - t2) * 1e3}

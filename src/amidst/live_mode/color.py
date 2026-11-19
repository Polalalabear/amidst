"""HSV clothing judgement following the D131 demo config (crop top 50% of the box)."""
from __future__ import annotations

import colorsys

import numpy as np

CFG = {"red_band": (0.95, 0.05), "blue_band": (0.5, 0.72), "crop_ratio": 0.5, "s_min": 0.2,
       "v_min": 0.2, "min_pixels": 64, "strong": 0.6, "weak": 0.3}


def _hsv(arr: np.ndarray):
    x = arr.astype(np.float32) / 255.0
    mx, mn = x.max(-1), x.min(-1)
    d = mx - mn
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    h = np.zeros_like(mx)
    m = d > 1e-6
    rc = m & (mx == r); gc = m & (mx == g) & ~rc; bc = m & ~rc & ~gc
    h[rc] = ((g - b)[rc] / d[rc]) % 6
    h[gc] = (b - r)[gc] / d[gc] + 2
    h[bc] = (r - g)[bc] / d[bc] + 4
    h = h / 6.0
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def judge(rgb: np.ndarray, bbox: list, weak: float | None = None) -> dict:
    """weak: minimum clothing-colour share of the crop (default CFG['weak']); #619 measures its effect on far people."""
    weak = CFG["weak"] if weak is None else weak
    x0, y0, x1, y1 = [int(round(v)) for v in bbox]
    H, W = rgb.shape[:2]
    x0, x1 = max(0, x0), min(W, x1)
    y0 = max(0, y0); y1 = min(H, y0 + int((int(round(bbox[3])) - y0) * CFG["crop_ratio"]))
    crop = rgb[y0:y1, x0:x1]
    if crop.size == 0:
        return {"color": "none", "red_ratio": 0.0, "blue_ratio": 0.0}
    h, s, v = _hsv(crop)
    ok = (s >= CFG["s_min"]) & (v >= CFG["v_min"])
    n = max(int(ok.sum()), 1)
    red = ok & ((h >= CFG["red_band"][0]) | (h <= CFG["red_band"][1]))
    blue = ok & (h >= CFG["blue_band"][0]) & (h <= CFG["blue_band"][1])
    area = crop.shape[0] * crop.shape[1]
    rr, br = float(red.sum()) / area, float(blue.sum()) / area
    # min_pixels (64 @960 px width) scales with image area, floor 8
    need = max(8, CFG["min_pixels"] * (W / 960.0) ** 2)
    label = "red" if rr >= weak and red.sum() >= need else \
        "blue" if br >= weak and blue.sum() >= need else "none"
    return {"color": label, "red_ratio": rr, "blue_ratio": br}

"""Parameterized upper-bbox HSV evidence; no thresholds or identity defaults."""
from __future__ import annotations

import colorsys
import hashlib
import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HSVConfig:
    version: str
    crop_ratio: float
    min_pixels: int
    truncation_max_ratio: float
    saturation_min: float
    value_min: float
    strong_ratio: float
    weak_ratio: float
    histogram_bins: int
    bands: dict[str, list[list[float]]]

    def __post_init__(self):
        values = [self.crop_ratio, self.truncation_max_ratio, self.saturation_min,
                  self.value_min, self.strong_ratio, self.weak_ratio]
        if (not self.version or any(type(v) not in (int, float) or not math.isfinite(v)
                                   or not 0 <= v <= 1 for v in values)
                or self.crop_ratio == 0 or self.weak_ratio > self.strong_ratio
                or type(self.min_pixels) is not int or self.min_pixels < 1
                or type(self.histogram_bins) is not int or self.histogram_bins < 1
                or not self.bands):
            raise ValueError("Invalid explicit HSV configuration")
        for label, bands in self.bands.items():
            if not label or not bands:
                raise ValueError("Every color needs explicit hue bands")
            for band in bands:
                if (len(band) != 2 or any(type(x) not in (int, float) or not math.isfinite(x)
                                         or not 0 <= x <= 1 for x in band)):
                    raise ValueError("Hue bands use normalized [0,1] values; low>high wraps")

    @property
    def content_sha256(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def summarize_upper_hsv(image, bbox, config: HSVConfig) -> dict:
    """H/S/V use colorsys [0,1]. crop_pixels counts S/V-eligible RGB pixels.

    Ratios use those eligible pixels. Inclusive hue-band bounds support wraparound.
    Geometry is clipped only for the crop; the detector bbox remains an observation.
    """
    if len(bbox) != 4 or any(not math.isfinite(float(x)) for x in bbox):
        raise ValueError("Invalid bbox")
    x0, y0, x1, y1 = map(float, bbox)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Empty bbox")
    y1 = y0 + (y1 - y0) * config.crop_ratio
    left, top = max(0, min(image.width, math.floor(x0))), max(0, min(image.height, math.floor(y0)))
    right = max(left, min(image.width, math.ceil(x1)))
    bottom = max(top, min(image.height, math.ceil(y1)))
    box = [left, top, right, bottom]
    base = {"method_version": config.version, "crop_box_xyxy_px": box, "crop_pixels": 0,
            "hsv_stats": {"hue_hist": [], "sat_mean": 0.0, "val_mean": 0.0},
            "verdicts": {label: "UNKNOWN" for label in config.bands}, "unknown_reason": None}
    area = (right - left) * (bottom - top)
    expected = (x1 - x0) * (y1 - y0)
    if area < config.min_pixels:
        base["unknown_reason"] = "CROP_TOO_SMALL"
        return base
    if max(0, 1 - area / expected) > config.truncation_max_ratio:
        base["unknown_reason"] = "CROP_TRUNCATED"
        return base
    cropped = image.crop(box).convert("RGB")
    pixels = list(cropped.get_flattened_data() if hasattr(cropped, "get_flattened_data")
                  else cropped.getdata())
    hsv = [colorsys.rgb_to_hsv(r / 255, g / 255, b / 255) for r, g, b in pixels]
    eligible = [(h, s, v) for h, s, v in hsv if s >= config.saturation_min and v >= config.value_min]
    base["crop_pixels"] = len(eligible)
    base["hsv_stats"].update(sat_mean=sum(x[1] for x in hsv) / len(hsv),
                             val_mean=sum(x[2] for x in hsv) / len(hsv))
    if len(eligible) < config.min_pixels:
        base["unknown_reason"] = "LOW_LIGHT_OR_SATURATION"
        return base
    hist = [0] * config.histogram_bins
    for h, _, _ in eligible:
        hist[min(config.histogram_bins - 1, int(h * config.histogram_bins))] += 1
    base["hsv_stats"]["hue_hist"] = [n / len(eligible) for n in hist]
    for label, bands in config.bands.items():
        count = sum(any(lo <= h <= hi if lo <= hi else h >= lo or h <= hi
                        for lo, hi in bands) for h, _, _ in eligible)
        ratio = count / len(eligible)
        base["verdicts"][label] = ("STRONG" if ratio >= config.strong_ratio
                                   else "WEAK" if ratio >= config.weak_ratio else "NONE")
    return base

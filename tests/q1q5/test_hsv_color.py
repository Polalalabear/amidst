"""Arbitrary SYNTHETIC thresholds, never production parameter proposals."""
import dataclasses

from PIL import Image
import pytest

from amidst.q1q5.hsv_color import HSVConfig, summarize_upper_hsv


def config(**changes):
    values = dict(version="SYNTHETIC-HSV", crop_ratio=0.5, min_pixels=2,
                  truncation_max_ratio=0.2, saturation_min=0.2, value_min=0.2,
                  strong_ratio=0.7, weak_ratio=0.2, histogram_bins=12,
                  bands={"red": [[0.95, 0.05]], "blue": [[0.6, 0.75]]})
    values.update(changes)
    return HSVConfig(**values)


@pytest.mark.parametrize("rgb,label", [((255, 0, 0), "red"), ((0, 0, 255), "blue")])
def test_primary_colors_and_method_hash(rgb, label):
    image = Image.new("RGB", (8, 8), rgb)
    result = summarize_upper_hsv(image, [0, 0, 8, 8], config())
    assert result["verdicts"][label] == "STRONG"
    assert result["crop_box_xyxy_px"] == [0, 0, 8, 4]
    assert result["crop_pixels"] == 32
    assert result["unknown_reason"] is None
    assert sum(result["hsv_stats"]["hue_hist"]) == 1
    assert config().content_sha256 != config(weak_ratio=0.3).content_sha256


def test_only_upper_crop_is_used_and_mixed_pixels_can_be_weak():
    image = Image.new("RGB", (8, 8), (0, 0, 255))
    for x in range(3):
        for y in range(4):
            image.putpixel((x, y), (255, 0, 0))
    result = summarize_upper_hsv(image, [0, 0, 8, 8], config())
    assert result["verdicts"] == {"red": "WEAK", "blue": "WEAK"}


@pytest.mark.parametrize("rgb,bbox,reason", [
    ((255, 0, 0), [0, 0, 1, 1], "CROP_TOO_SMALL"),
    ((255, 0, 0), [-8, 0, 8, 8], "CROP_TRUNCATED"),
    ((0, 0, 0), [0, 0, 8, 8], "LOW_LIGHT_OR_SATURATION"),
    ((255, 255, 255), [0, 0, 8, 8], "LOW_LIGHT_OR_SATURATION"),
])
def test_unknown_is_distinct_from_color_none(rgb, bbox, reason):
    result = summarize_upper_hsv(Image.new("RGB", (8, 8), rgb), bbox, config())
    assert set(result["verdicts"].values()) == {"UNKNOWN"}
    assert result["unknown_reason"] == reason


@pytest.mark.parametrize("changes", [{"crop_ratio": 0}, {"min_pixels": True},
                                    {"strong_ratio": float("nan")}, {"bands": {}},
                                    {"weak_ratio": 0.8}, {"histogram_bins": 0}])
def test_invalid_config_is_rejected(changes):
    with pytest.raises(ValueError):
        config(**changes)


def test_no_parameters_have_production_defaults():
    with pytest.raises(TypeError):
        HSVConfig()
    assert set(dataclasses.asdict(config())) == {
        "version", "crop_ratio", "min_pixels", "truncation_max_ratio", "saturation_min",
        "value_min", "strong_ratio", "weak_ratio", "histogram_bins", "bands",
    }

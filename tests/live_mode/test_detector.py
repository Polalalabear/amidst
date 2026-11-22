"""Keep live boxes in source pixels: colour crops and floor projection depend on this."""

import numpy as np
import pytest
from PIL import Image

from amidst.live_mode.candidates import TrackSelection
from amidst.live_mode.detector import prepare_image, source_box


def test_wide_frame_keeps_person_aspect_and_maps_back_to_source_pixels():
    frame = Image.new("RGB", (320, 180), (200, 20, 20))
    image, transform = prepare_image(frame, "letterbox")
    pixels = np.asarray(image)
    assert image.size == (640, 640)
    assert tuple(pixels[139, 0]) == (114, 114, 114)
    assert tuple(pixels[140, 0]) == (200, 20, 20)
    assert tuple(pixels[499, 639]) == (200, 20, 20)
    assert tuple(pixels[500, 0]) == (114, 114, 114)
    assert source_box([20, 160, 60, 340], transform) == [10, 10, 30, 100]
    assert source_box([0, 0, 640, 100], transform) is None  # padding is not a person
    assert source_box([-10, 130, 650, 510], transform) == [0, 0, 320, 180]


def test_portrait_and_rounded_resize_boxes_use_actual_resized_dimensions():
    _, transform = prepare_image(Image.new("RGB", (181, 321)), "letterbox")
    # Actual content is 361x640, with left margin 139 (one extra pixel on right).
    assert source_box([139, 0, 500, 640], transform) == pytest.approx([0, 0, 181, 321])


def test_stretch_mode_reproduces_legacy_coordinates():
    _, transform = prepare_image(Image.new("RGB", (320, 180)), "stretch")
    assert source_box([20, 64, 60, 320], transform) == pytest.approx([10, 18, 30, 90])


def test_invalid_resize_mode_is_rejected():
    with pytest.raises(ValueError, match="resize_mode"):
        prepare_image(Image.new("RGB", (320, 180)), "typo")


def test_acceptance_metric_keeps_highest_iou_before_score_filter():
    from scripts.live_mode.detection_score import score_recording

    labels = [{"id": "one", "cam": "CAM_W1", "inside": 1, "gt_h_px": 30, "bbox": [0, 0, 10, 30]}]
    # An exact low-score duplicate must not be replaced by the higher-score loose box
    # during scoring: that would silently change the 69.1% historical acceptance metric.
    detections = {
        "one": {
            "dets": [
                {"bbox": [0, 0, 10, 30], "score": 0.06},
                {"bbox": [0, 0, 12, 32], "score": 0.9},
            ]
        }
    }
    summary = score_recording(labels, detections)
    assert summary["thresholds"]["0.35"]["all"]["hits"] == 0
    assert summary["thresholds"]["0.05"]["all"]["hits"] == 1


def test_entry_threshold_does_not_lower_other_camera_thresholds():
    import io
    import threading
    from types import SimpleNamespace
    from amidst.live_mode.server import State

    state = object.__new__(State)
    state.selection = TrackSelection()
    state.args = SimpleNamespace(
        det_width=320, det_height=180, min_score=0.15, camera_min_scores={"CAM_ENTRY": 0.05}
    )
    state.lock = threading.Lock()
    state.det = SimpleNamespace(
        detect=lambda ims: ([[{"bbox": [0, 0, 20, 40], "score": 0.08}] for im in ims], {})
    )
    state._infer_tracking = lambda *args: None
    state.decider = None
    data = io.BytesIO()
    Image.new("RGB", (320, 180), "red").save(data, format="JPEG")
    out = state.infer({"tick": 0}, {"CAM_ENTRY": data.getvalue(), "CAM_W1": data.getvalue()}, True)
    assert len(out["dets"]["CAM_ENTRY"]) == 1
    assert out["dets"]["CAM_W1"] == []


def test_camera_threshold_override_validates_values():
    import argparse
    from amidst.live_mode.server import camera_min_score

    assert camera_min_score("CAM_ENTRY=0.35") == ("CAM_ENTRY", 0.35)
    for value in ["CAM_ENTRY", "=0.2", "CAM_ENTRY=nan", "CAM_ENTRY=0.01"]:
        with pytest.raises(argparse.ArgumentTypeError):
            camera_min_score(value)

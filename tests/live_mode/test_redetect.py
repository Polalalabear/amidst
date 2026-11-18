"""Counterfactual thresholds must be explicit on the same saved camera pixels."""

import io
import json
import struct
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from scripts.live_mode import redetect_route


@pytest.mark.parametrize("entry_score,expected", [(0.15, 1), (0.05, 2)])
def test_redetect_camera_override_changes_only_entry(tmp_path, monkeypatch, entry_score, expected):
    source = tmp_path / "source"
    packets = source / "packets" / "a4"
    packets.mkdir(parents=True)
    (source / "raw").mkdir()
    data = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(data, format="JPEG")
    jpeg = data.getvalue()
    header = json.dumps(
        {"tick": 7, "frames": [{"cam": c, "bytes": len(jpeg)} for c in ["CAM_ENTRY", "CAM_W1"]]}
    ).encode()
    (packets / "7.bin").write_bytes(struct.pack("<I", len(header)) + header + jpeg * 2)
    (source / "raw" / "a4.t1raw.json").write_text(
        json.dumps({"label": "a4", "infer": [{"tick": 7}]})
    )

    def detect(images):
        assert len(images) == 2 and all(im.size == (20, 20) for im in images)
        return [[{"bbox": [1, 1, 10, 18], "score": s} for s in [0.08, 0.2]] for _ in images], {}

    monkeypatch.setattr(
        redetect_route,
        "LiveDetector",
        lambda *a, **k: SimpleNamespace(detect=detect, resize_mode="letterbox"),
    )
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "redetect_route.py",
            "--recording",
            str(source),
            "--out",
            str(out),
            "--models",
            str(tmp_path / "unused-models"),
            "--min-score",
            "0.15",
            "--camera-min-score",
            f"CAM_ENTRY={entry_score}",
        ],
    )
    redetect_route.main()
    result = json.loads((out / "a4.t1raw.json").read_text())
    assert len(result["infer"][0]["dets"]["CAM_ENTRY"]) == expected
    assert len(result["infer"][0]["dets"]["CAM_W1"]) == 1
    assert result["redetection"]["camera_min_scores"] == {"CAM_ENTRY": entry_score}

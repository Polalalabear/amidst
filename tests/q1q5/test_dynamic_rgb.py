"""Dynamic grid/source authority and pixel-derived API linkage, using test doubles."""

import json
from pathlib import Path

import pytest
from test_detection_index import Detector
from test_linked_runtime import pin

from amidst.q1q5.baseline_runner import save
from amidst.q1q5.linked_runtime import build_inputs, load_rgb
from amidst.q1q5.linked_workbench import application


def fixture(root):
    from PIL import Image

    Image.new("RGB", (960, 540), "red").save(root / "frame.png")
    static = dict(
        schema_version="q-demo.dynamic-static.v1",
        scene_id="ENGINEERING_DYNAMIC_SCENE",
        revision="rSYN",
        engineering_only=True,
        cameras={"A": {}, "B": {}},
        image_size_px=[960, 540],
        source_blend_file_sha256="a" * 64,
        gt_read=False,
    )
    static_pin = save(root / "static.json", static)
    doc = dict(
        schema_version="q-demo.dynamic-rgb-run.v1",
        source_kind="SYNTHETIC",
        scene_id=static["scene_id"],
        run_id="ENGINEERING_DYNAMIC_RUN_20261025",
        clock_id="ENGINEERING_DYNAMIC_CLOCK",
        sampling=dict(fps=20, duration_s=8, sample_count_per_camera=160, image_size_px=[960, 540]),
        motion_kind="ARTICULATED_RENDERED_MOTION",
        static_ref="static.json",
        static_file_sha256=static_pin,
        identity_verdict="UNCONFIRMED",
        gt_read=False,
        records=[
            dict(
                camera_id=c,
                frame_index=i,
                timestamp_s=i / 20,
                rgb_ref="frame.png",
                file_sha256=pin(root / "frame.png"),
            )
            for c in ["A", "B"]
            for i in range(160)
        ],
    )
    save(root / "rgb.json", doc)
    return doc


@pytest.mark.parametrize("change", ["time", "duplicate", "actor", "source", "sampling", "static"])
def test_dynamic_fails_closed(tmp_path, change):
    doc = fixture(tmp_path)
    if change == "time":
        doc["records"][1]["timestamp_s"] = 0.05001
    elif change == "duplicate":
        doc["records"][-1] = doc["records"][0]
    elif change == "actor":
        doc["records"][0]["actor_id"] = "forbidden"
    elif change == "source":
        doc["run_id"] = "OTHER"
    elif change == "sampling":
        doc["sampling"]["fps"] = 5
    else:
        (tmp_path / "static.json").write_text("{}")
    (tmp_path / "rgb.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        load_rgb(tmp_path / "rgb.json", pin(tmp_path / "rgb.json"))


def test_20fps_index_and_same_source_media_scope(tmp_path, monkeypatch):
    fixture(tmp_path)
    rgb = tmp_path / "rgb.json"
    prepared = tmp_path / "prepared"
    build_inputs(
        rgb,
        pin(rgb),
        {"source_root": "unused", "weights": "unused", "source_hashes": {}},
        prepared,
        predictor_factory=lambda *a, **kw: Detector(),
    )
    monkeypatch.setenv("AMIDST_Q1Q5_REGISTRY", str(prepared / "registry.json"))
    monkeypatch.setenv("AMIDST_Q1Q5_REGISTRY_SHA256", pin(prepared / "registry.json"))
    monkeypatch.delenv("AMIDST_Q1Q5_OLLAMA_RUNTIME", raising=False)
    monkeypatch.delenv("AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256", raising=False)
    a = application(Path(__file__).resolve().parents[2], rgb, pin(rgb), tmp_path / "private")
    token = a.workbench.session(dict(role="research"))["session_ref"]
    bridge = a.q_api.rgb_api
    request = dict(
        schema_version="controlled-scene.synced-frames-request.v1",
        session_ref=token,
        scene_id=bridge.scene_id,
        run_id=bridge.run_id,
        t_s=7.999999,
        camera_ids=["A"],
    )
    result = bridge.call("synced_frames", request)
    assert result["tiles"][0]["frame_index"] == 159
    assert result["tiles"][0]["timestamp_s"] == 7.95
    assert result["clock_id"] == "ENGINEERING_DYNAMIC_CLOCK"
    request["run_id"] = "SYNTHETIC_RUN"
    with pytest.raises(ValueError):
        bridge.call("synced_frames", request)
    index = json.loads((prepared / "index/detection_index.json").read_bytes())
    assert index["sampling"]["per_camera"][0]["source_frame_interval_us"] == 50000

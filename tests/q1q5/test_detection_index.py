"""SYNTHETIC PNGs and detector outputs, never a fallback for real RGB."""
import hashlib
import io
import json
from types import SimpleNamespace

from PIL import Image
import pytest

from amidst.q1q5.detection_index import (
    IndexIntegrityError, OfficialRTDetrR18, build_detection_index, content_hash, write_index,
)
from amidst.q1q5.hsv_color import HSVConfig


def color_config():
    return HSVConfig("SYNTHETIC-HSV", 0.5, 2, 0.2, 0.2, 0.2, 0.7, 0.2, 12,
                     {"red": [[0.95, 0.05]], "blue": [[0.6, 0.75]]})


def safe_run():
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(stream, format="PNG")
    raw = stream.getvalue()
    rows = [{"camera_id": "CAM_SYN", "frame_index": i, "timestamp_s": i / 5,
             "file_sha256": hashlib.sha256(raw).hexdigest()} for i in range(4)]
    run = SimpleNamespace(
        manifest={"scene_id": "SYNTHETIC_SCENE", "run_id": "SYNTHETIC_RUN",
                  "clock_id": "SYNTHETIC_CLOCK", "allowlist": [{"role": "rgb_index",
                  "file_sha256": "1" * 64}], "sampling": {"fps": 5, "duration_s": 0.8,
                  "sample_count_per_camera": 4, "image_size_px": [8, 8]}},
        files={"rgb_index": {"missing": []}}, camera_ids={"CAM_SYN"},
        rgb_record=lambda camera, i: rows[i], read_rgb=lambda camera, i: raw,
    )
    return run


class Detector:
    class_labels = ("person", "car")
    calls = 0
    metadata = {
        "family": "SYNTHETIC", "variant": "SYNTHETIC", "framework": "SYNTHETIC",
        "framework_version": "0", "weights_file_sha256": "2" * 64,
        "weights_file": "SYNTHETIC.weights", "weights_file_bytes": 1,
        "weights_license": {"code": "SYNTHETIC", "training_data_terms": "UNKNOWN"},
        "code_source": {"repo": "synthetic/none", "commit": "0" * 40},
        "postprocess": {"top_k_queries": 300},
        "weights_source": "synthetic://none", "config_sha256": "3" * 64,
        "load": {"strict": True, "num_classes": 2},
        "class_map": {"version": "SYNTHETIC", "num_classes": 2,
                      "source_file_sha256": "4" * 64,
                      "content_sha256": content_hash({"version": "SYNTHETIC",
                                                      "labels": ["person", "car"]})},
        "input_preprocess": {"resize_policy": "SYNTHETIC", "input_size_px": [8, 8]},
        "nms": {"applied": False, "iou": None}, "device": "SYNTHETIC",
    }

    def __call__(self, image):
        self.calls += 1
        return [{"class_id": 1, "bbox_xyxy_px": [0, 0, 8, 8], "score": 0.4},
                {"class_id": 0, "bbox_xyxy_px": [0, 0, 8, 8], "score": 0.9}]


def build(run=None, predictor=None, **changes):
    settings = dict(scene_revision="rSYN", stride_samples=1, index_grid_origin_frame=0,
                    index_score_floor=0.3, color_config=color_config())
    settings.update(changes)
    return build_detection_index(run or safe_run(), predictor or Detector(), **settings)


def test_complete_index_reproducible_hashes_ids_and_source_scopes(tmp_path):
    first, second = build(), build()
    assert first.manifest == second.manifest and first.records_bytes == second.records_bytes
    records = [json.loads(line) for line in first.records_bytes.splitlines()]
    assert first.stats == {"model_calls": 4, "frames": 4}
    assert records[0]["detections"][0]["class_label"] == "person"
    assert records[0]["detections"][1]["color"] is None
    assert records[0]["detections"][0]["color"]["verdicts"]["red"] == "STRONG"
    key = first.manifest["index_id"].split(":")[-1]
    assert records[0]["detections"][0]["observation_id"] == f"obs:{key}:CAM_SYN:0:0"
    assert hashlib.sha256(first.records_bytes).hexdigest() == first.manifest["records_file_sha256"]
    write_index(first, tmp_path / "index")
    with pytest.raises(FileExistsError):
        write_index(first, tmp_path / "index")


def test_stride_changes_index_id_and_never_infers_unsampled_frames():
    model = Detector()
    result = build(predictor=model, stride_samples=2)
    records = [json.loads(line) for line in result.records_bytes.splitlines()]
    assert model.calls == 2
    assert [r["frame_state"] for r in records] == ["INFERRED", "NOT_SAMPLED"] * 2
    assert result.manifest["index_id"] != build().manifest["index_id"]


def test_declared_missing_not_inferred_and_no_detections_remain_separate():
    run = safe_run()
    original = run.rgb_record
    run.rgb_record = lambda camera, i: None if i == 1 else original(camera, i)
    run.files["rgb_index"]["missing"] = [{"camera_id": "CAM_SYN", "frame_index": 1}]
    class Partial(Detector):
        def __call__(self, image):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("SYNTHETIC failure")
            return []
    rows = [json.loads(x) for x in build(run, Partial()).records_bytes.splitlines()]
    assert [r["frame_state"] for r in rows] == ["NOT_INFERRED", "MISSING", "INFERRED", "INFERRED"]
    assert rows[0]["detections"] is None and rows[2]["detections"] == []


def test_rgb_hash_and_unlisted_missing_fail_before_model_call():
    run, model = safe_run(), Detector()
    run.read_rgb = lambda camera, i: b"tampered"
    with pytest.raises(IndexIntegrityError):
        build(run, model)
    assert model.calls == 0
    run.rgb_record = lambda camera, i: None
    with pytest.raises(IndexIntegrityError, match="Unlisted"):
        build(run, model)


def test_unknown_class_or_invalid_score_is_not_converted_to_no_detection():
    class Bad(Detector):
        def __call__(self, image):
            return [{"class_id": 999, "bbox_xyxy_px": [0, 0, 8, 8], "score": 0.9}]
    with pytest.raises(IndexIntegrityError, match="Invalid detector"):
        build(predictor=Bad())


@pytest.mark.parametrize("settings", [{"stride_samples": 0}, {"index_score_floor": None},
                                     {"index_score_floor": float("nan")},
                                     {"index_grid_origin_frame": 99}])
def test_missing_or_invalid_parameters_have_no_smoke_default(settings):
    with pytest.raises(IndexIntegrityError):
        build(**settings)


def test_official_adapter_refuses_missing_source_pins_before_loading_model(tmp_path):
    with pytest.raises(IndexIntegrityError, match="source hashes"):
        OfficialRTDetrR18(tmp_path, tmp_path / "unused.pth", source_hashes={}, seed=0, threads=1)


@pytest.mark.parametrize("permit", [False, True])
def test_cli_stops_before_asset_or_model_loading_without_approved_parameters(tmp_path, permit):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "index_cli", Path(__file__).resolve().parents[2] / "scripts/build_q1q5_detection_index.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    raw = json.dumps({"parameter_set": {"approval": {"status": "PROPOSED"}}}).encode()
    config = tmp_path / "config.json"
    config.write_bytes(raw)
    args = ["--repo", str(tmp_path), "--config", str(config), "--config-sha256",
            hashlib.sha256(raw).hexdigest(), "--run-id", "SYNTHETIC", "--weights",
            str(tmp_path / "missing.pth"), "--model-source", str(tmp_path / "missing"),
            "--output", str(tmp_path / "output")]
    if permit:
        args.append("--permit-real-rgb")
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2 and not (tmp_path / "output").exists()

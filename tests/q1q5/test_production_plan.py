"""SYNTHETIC approval bytes/PNG adapter; no formal approval or real detector."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_clock_mapping import declaration
from test_detection_index import Detector, color_config, safe_run

from amidst.q1q5.detection_index import content_hash
from amidst.q1q5.production_plan import GATES, prepare, produce, validate_binding

ROOT = Path(__file__).resolve().parents[2]


def write(root, name, doc):
    path = root / (name + ".json")
    raw = json.dumps(doc).encode()
    path.write_bytes(raw)
    return {"path": str(path), "file_sha256": hashlib.sha256(raw).hexdigest()}


def fixture(tmp_path):
    plan = json.loads((ROOT / "configs/q1q5/r004_production_v1.json").read_text())
    cameras = list(plan["camera_catalog_calibration_sha256"])[:4]
    reg = dict(
        run_root=str(tmp_path),
        manifest_sha256="a" * 64,
        scene_id="SYNTHETIC_SCENE",
        run_id="SYNTHETIC_RUN",
        source_sha256=plan["static_source_sha256"],
    )
    parameters = {
        "schema_version": "q-demo.parameter-set.v1",
        "approval": {"status": "APPROVED"},
        "applies_to": {"scene_revision": "r004", "run_ids": ["SYNTHETIC_RUN"]},
        "parameters": [
            {"name": k, "value": v, "status": "APPROVED"}
            for k, v in dict(
                index_score_floor=0.3,
                stride_samples=1,
                index_grid_origin_frame=0,
                hsv_config=vars(color_config()),
            ).items()
        ],
    }
    parameters["content_sha256"] = content_hash(parameters)
    config = dict(
        source_root=str(tmp_path),
        weights=str(tmp_path / "SYNTHETIC.pth"),
        source_hashes={"SYNTHETIC.py": "b" * 64},
        seed=7,
        threads=2,
    )
    binding = dict(
        schema_version="q-demo.index-production-binding.v1",
        label="A4",
        scene_revision="r004",
        registration=reg,
        camera_ids=cameras,
        source_range_us=[0, 30000000],
        clock_mapping=write(
            tmp_path,
            "clock",
            declaration(
                run_id=reg["run_id"], clock_id="clock:" + reg["run_id"], source_duration_us=30000000
            ),
        ),
        parameter_set=write(tmp_path, "parameters", parameters),
        detector_config=write(tmp_path, "detector", config),
        approval_receipts=[],
    )
    approve(tmp_path, binding)
    return plan, binding


def approve(root, binding):
    scope = content_hash(binding, ("approval_receipts",))
    binding["approval_receipts"] = [
        write(
            root,
            "approval-" + gate,
            dict(gate=gate, reviewer="SYNTHETIC", decision="APPROVED", scope_sha256=scope),
        )
        for gate in sorted(GATES)
    ]


def test_preparation_is_blocked_with_explicit_missing_fields(tmp_path):
    plan, _ = fixture(tmp_path)
    report = prepare(plan)
    assert report["status"] == "BLOCKED" and len(report["missing"]) == 14
    assert not report["production_performed"] and not report["human_approval_verified"]


def test_pinned_registration_accepts_new_run_without_old_r003_registry(tmp_path):
    plan, binding = fixture(tmp_path)
    reg, values, config = validate_binding(plan, binding)
    assert (
        reg["run_id"] == "SYNTHETIC_RUN"
        and values["stride_samples"] == 1
        and config["threads"] == 2
    )


@pytest.mark.parametrize(
    "change",
    ["scope", "camera", "time", "revision", "receipt", "parameter", "config", "clock", "symlink"],
)
def test_mismatches_stop_before_assets_or_model_load(tmp_path, change):
    plan, binding = fixture(tmp_path)
    if change == "scope":
        binding["registration"]["source_sha256"] = "0" * 64
    if change == "camera":
        binding["camera_ids"][0] = "FOREIGN"
    if change == "time":
        binding["source_range_us"][1] += 1
    if change == "revision":
        binding["scene_revision"] = "r003"
    if change == "receipt":
        binding["approval_receipts"].pop()
    if change == "parameter":
        Path(binding["parameter_set"]["path"]).write_text("{}")
    if change == "config":
        Path(binding["detector_config"]["path"]).write_text("{}")
    if change == "clock":
        Path(binding["clock_mapping"]["path"]).write_text("{}")
    if change == "symlink":
        link = tmp_path / "alias"
        link.symlink_to(tmp_path, target_is_directory=True)
        binding["registration"]["run_root"] = str(link)
    called = []
    with pytest.raises((ValueError, KeyError)):
        produce(
            plan,
            binding,
            tmp_path / "output",
            permit_real_rgb=True,
            run_loader=lambda _: called.append(True),
        )
    assert not called


def test_permission_is_required_even_for_complete_binding(tmp_path):
    plan, binding = fixture(tmp_path)
    with pytest.raises(ValueError, match="PERMISSION"):
        produce(plan, binding, tmp_path / "output")


def test_model_never_loads_when_rgb_scope_disagrees(tmp_path, monkeypatch):
    plan, binding = fixture(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "amidst-artifacts").mkdir()
    model = []
    with pytest.raises(ValueError, match="RGB_CAMERA_SCOPE"):
        produce(
            plan,
            binding,
            tmp_path / "amidst-artifacts/out",
            permit_real_rgb=True,
            run_loader=lambda _: safe_run(),
            predictor_factory=lambda *a, **k: model.append(True),
        )
    assert not model


def test_new_registration_end_to_end_synthetic_adapter(tmp_path, monkeypatch):
    plan, binding = fixture(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "amidst-artifacts").mkdir()
    run = safe_run()
    cameras = binding["camera_ids"]
    run.camera_ids = set(cameras)
    run.manifest["sampling"].update(duration_s=30, sample_count_per_camera=150)
    raw = run.read_rgb(None, 0)
    run.rgb_record = lambda camera, i: dict(
        camera_id=camera,
        frame_index=i,
        timestamp_s=i / 5,
        file_sha256=hashlib.sha256(raw).hexdigest(),
    )
    # Keep the real PNG's dimensions explicit in this SYNTHETIC-only plan.
    plan["image_size_px"] = [960, 540]
    import io

    from PIL import Image

    png = io.BytesIO()
    Image.new("RGB", (960, 540), "red").save(png, format="PNG")
    raw = png.getvalue()
    run.read_rgb = lambda *_: raw
    run.manifest["sampling"]["image_size_px"] = [960, 540]
    run.files["cameras"] = {
        "cameras": [
            dict(camera_id=c, calibration_sha256=plan["camera_catalog_calibration_sha256"][c])
            for c in cameras
        ]
    }
    out = tmp_path / "amidst-artifacts/new"
    artifact = produce(
        plan,
        binding,
        out,
        permit_real_rgb=True,
        run_loader=lambda _: run,
        predictor_factory=lambda *a, **k: Detector(),
    )
    assert artifact.manifest["scene_revision"] == "r004" and artifact.stats["model_calls"] == 600
    assert (out / "index/detection_index.json").is_file() and (out / "receipt.json").is_file()
    with pytest.raises(ValueError, match="NEW_CANONICAL"):
        produce(plan, binding, out, permit_real_rgb=True)


def test_low_disk_prevents_metadata_loading(tmp_path, monkeypatch):
    plan, binding = fixture(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "amidst-artifacts").mkdir()
    monkeypatch.setattr("shutil.disk_usage", lambda _: SimpleNamespace(free=8 * 1024**3 - 1))
    with pytest.raises(ValueError, match="DISK_SPACE"):
        produce(plan, binding, tmp_path / "amidst-artifacts/out", permit_real_rgb=True)
